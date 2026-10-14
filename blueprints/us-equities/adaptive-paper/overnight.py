"""BOATS REST glue and overnight admission, using the reviewed vendor SDK.

alpacahq/alpaca-py@cc4cb3b7ba50ae250e621983c2779047fb16bb28:
data/historical/stock.py:get_stock_latest_quote, data/requests.py:StockLatestQuoteRequest,
trading/client.py:get_asset. No market-data socket is constructed here.
Alpaca 24/5 Trading and Orders at Alpaca: LIMIT DAY/GTC with extended_hours;
DAY carries to 20:00 on the upcoming trade date. Local default flatten is 03:50.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import inspect
import math
from concurrent.futures import ThreadPoolExecutor

from feeds import require_qualified_quote_source
from sessions import SessionKind, extended_session_close, session_at


def overnight_config(config):
    """An opt-in REST diagnostic; entries stop at the overnight cutoff."""
    mode = config.get("quote_source", "stream")
    require_qualified_quote_source(config.get("feed"), mode)
    block = config.get("overnight")
    if block is None:
        if mode != "stream":
            raise ValueError("overnight_configuration_required")
        return None
    if (type(block) is not dict or set(block) - {"enabled", "flatten_minutes_before_pre"}
            or block.get("enabled") is not True or mode != "boats_rest"
            or config.get("extended_hours_enabled") is not True
            or config.get("regular_session_only") is not False
            or config.get("sessions", {}).get("overnight_holds", False) is not False):
        raise ValueError("unqualified_overnight_configuration")
    minutes = block.get("flatten_minutes_before_pre", 10)
    if type(minutes) is not int or not 1 <= minutes <= 60:
        raise ValueError("unqualified_overnight_configuration")
    return {"flatten_minutes_before_pre": minutes}


def overnight_bounds(now, flatten_minutes=10):
    if type(flatten_minutes) is not int or not 1 <= flatten_minutes <= 60:
        raise ValueError("unqualified_overnight_configuration")
    moment = datetime.fromtimestamp(now, timezone.utc)
    info = session_at(moment)
    if info.kind != SessionKind.OVERNIGHT:
        raise ValueError("overnight_session_unavailable")
    boundary = info.close.timestamp()
    return {"flatten_at": boundary - flatten_minutes * 60, "boundary_at": boundary,
            "day_expiry": extended_session_close(moment).timestamp()}


def overnight_quote_feed(feed, now, *, enabled=False):
    """Supported REST venue selection for an opted-in residual exit path."""
    if enabled is True and feed == "boats":
        kind = session_at(datetime.fromtimestamp(now, timezone.utc)).kind
        return "boats" if kind == SessionKind.OVERNIGHT else "sip"
    return feed


def check_overnight_order(order):
    """Order shape only; this never supplies session or risk authority."""
    if (type(order) is not dict or order.get("type") != "limit"
            or order.get("time_in_force") not in ("day", "gtc")
            or (order.get("extended_hours") is not True
                and not (order.get("side") == "sell" and order.get("reduce_only") is True
                         and order.get("extended_hours") is False))
            or order.get("order_class", "simple") != "simple"
            or any(key in order for key in ("take_profit", "stop_loss", "trail_price", "trail_percent", "legs"))):
        raise ValueError("overnight_order_contract_refused")


def overnight_dispatch_refusal(port, symbol, now, session_policy, side, *, reduce_only=False):
    """Exact native-dispatch guard, also exercisable without the native engine."""
    prefix = "exit" if side == "sell" else "entry"
    try:
        kind = session_at(datetime.fromtimestamp(now, timezone.utc)).kind
    except ValueError:
        return prefix + "_dispatch_session_classification_failed"
    if kind in (SessionKind.PRE, SessionKind.RTH, SessionKind.POST):
        if getattr(port, "overnight_enabled", False) is True:
            if side != "sell" or reduce_only is not True:
                return prefix + "_dispatch_session_unavailable"
        else:
            return None
    unavailable = prefix + "_dispatch_session_unavailable"
    if (kind not in (SessionKind.OVERNIGHT, SessionKind.PRE, SessionKind.RTH, SessionKind.POST)
            or session_policy.get("overnight_enabled") is not True
            or getattr(port, "overnight_enabled", False) is not True
            or getattr(port, "feed", None) != "boats"
            or getattr(port, "quote_source_mode", None) != "boats_rest"
            or not callable(getattr(port, "overnight_check", None))):
        return unavailable
    try:
        result = port.overnight_check(symbol, now, side)
        if result is not None:
            return unavailable
    except (ValueError, RuntimeError):
        return unavailable
    return None


class BoatsQuoteSource:
    """Concurrent per-symbol latest reads, bounded to five held/queued symbols.

    Reads use injected vendor callables; the port owns normalization, freshness
    and state delivery. A throttled sweep leaves last observations untouched,
    so they age naturally and cannot authorize orders after their timeout.
    """
    def __init__(self, symbols, quote_read, asset_read, *, concurrency=5, asset_timeout=1):
        self.symbols = tuple(dict.fromkeys(symbols))
        if (not 1 <= len(self.symbols) <= 5 or type(concurrency) is not int
                or not 1 <= concurrency <= 5):
            raise ValueError("overnight_symbol_bound")
        self.quote_read, self.asset_read = quote_read, asset_read
        if not math.isfinite(asset_timeout) or asset_timeout <= 0:
            raise ValueError("overnight_status_timeout")
        self.asset_timeout = asset_timeout
        self.assets, self.asset_at = {}, {}
        self.semaphore = asyncio.Semaphore(concurrency)
        self.retry_at, self.failures, self.last = {}, {}, {}
        self.events = []
        self.executor = ThreadPoolExecutor(max_workers=concurrency, thread_name_prefix="boats-rest")

    async def _read(self, function, symbol):
        if inspect.iscoroutinefunction(function):
            return await function(symbol)
        return await asyncio.get_running_loop().run_in_executor(self.executor, function, symbol)

    async def close(self):
        # Cancelling an asyncio wrapper cannot cancel a running SDK HTTP read.
        # Join this source's bounded workers before the port closes their Sessions.
        await asyncio.to_thread(self.executor.shutdown, wait=True, cancel_futures=True)

    async def sweep(self, now, *, symbols=None, on_asset=None, on_quote=None):
        async def one(symbol):
            if now < self.retry_at.get(symbol, 0):
                return None
            async with self.semaphore:
                try:
                    if now - self.asset_at.get(symbol, float("-inf")) >= self.asset_timeout:
                        self.assets[symbol] = await self._read(self.asset_read, symbol)
                        self.asset_at[symbol] = now
                        if on_asset is not None:
                            on_asset(self.assets[symbol])
                    asset = self.assets[symbol]
                    quote = await self._read(self.quote_read, symbol)
                except Exception as error:
                    code = getattr(error, "status_code", None)
                    if code is None:
                        code = getattr(getattr(error, "response", None), "status_code", None)
                    count = min(self.failures.get(symbol, 0) + 1, 6)
                    self.failures[symbol] = count
                    delay = min(30, 2 ** count) if code == 429 else 1
                    self.retry_at[symbol] = now + delay
                    self.events.append({"type": "overnight_poll_refused", "symbol": symbol,
                                        "reason": "rate_limited" if code == 429 else "read_failed",
                                        "retry_at": self.retry_at[symbol]})
                    return None
                self.failures.pop(symbol, None)
                self.retry_at.pop(symbol, None)
                row = {"symbol": symbol, "asset": asset, "quote": quote}
                self.last[symbol] = row
                if on_quote is not None:
                    on_quote(row)
                return row
        return [row for row in await asyncio.gather(*(one(s) for s in (self.symbols if symbols is None else symbols))) if row is not None]
