"""A6 deterministic admission contract. No broker, engine, credential or clock IO.

Sources: CC accepted spec8eb20e2e/addendumcf63eb57; D4 canonical rounding;
CPython Decimal.quantize directional rounding. Budget checks are admission
ceilings, never a replacement for the engine/vendor transport pacing.
"""
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation, ROUND_FLOOR, ROUND_CEILING
import hashlib
import json
import os
from pathlib import Path
import re
import threading

D = Decimal
CLIENT_ID_PREFIX = "a6-"      # every client order id this arm creates; the restart re-derivation and the open-order classification use it
PAYLOAD_KEYS = frozenset({"symbol", "qty", "side", "type", "time_in_force",
                          "limit_price", "extended_hours", "client_order_id"})


class GuardRefusal(ValueError):
    """Bounded reason only; never echo a model value or a broker exception."""


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       allow_nan=False) + "\n").encode()


def dec(value):
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise GuardRefusal("number")
    try:
        result = D(value)
    except InvalidOperation:
        raise GuardRefusal("number") from None
    if not result.is_finite():
        raise GuardRefusal("number")
    return result


def rounded(price, side):
    price = dec(price)
    if price <= 0 or side not in ("buy", "sell"):
        raise GuardRefusal("rounding_input")
    tick = D("0.01") if price >= 1 else D("0.0001")
    return price.quantize(tick, rounding=ROUND_FLOOR if side == "buy" else ROUND_CEILING)


@dataclass(frozen=True)
class Intent:
    symbol: str
    side: str
    sizing: str = "entry"
    asset_type: str = "stock"
    # Kept solely for C4 invariance tests. Never read, journaled or forwarded.
    model_hints: object = field(default=None, compare=False, repr=False)


@dataclass(frozen=True)
class QuoteSnapshot:
    bid: Decimal
    ask: Decimal
    quote_ns: int
    trade_ns: int
    session: str
    clock_ns: int


@dataclass(frozen=True)
class AccountState:
    equity: Decimal
    positions: dict
    open_orders: tuple = ()
    reconciled: bool = True


@dataclass(frozen=True)
class Decision:
    symbol: str
    side: str
    qty: int
    limit_price: Decimal
    extended_hours: bool
    client_order_id: str
    reservation: str

    def payload(self):
        return {"symbol": self.symbol, "side": self.side, "qty": str(self.qty),
                "type": "limit", "time_in_force": "day",
                "limit_price": str(self.limit_price), "extended_hours": self.extended_hours,
                "client_order_id": self.client_order_id}


@dataclass(frozen=True)
class Refusal:
    code: str


class Journal:
    """Exclusive single-writer append-only hash chain with fsync before writes.

    On restart unresolved submissions/decisions block admission until the
    operator supplies reconciled terminal facts; no automatic retry exists.
    """
    def __init__(self, path):
        self.unusable = False
        self.path = Path(path)
        if self.path.is_symlink():
            raise GuardRefusal("journal")
        flags = os.O_RDWR | os.O_APPEND | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
        try:
            self.fd = os.open(self.path, flags, 0o600)
            if os.fstat(self.fd).st_mode & 0o077:
                raise GuardRefusal("journal_mode")
            if os.name != "posix":
                raise GuardRefusal("journal_lock_platform")
            import fcntl
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with os.fdopen(os.dup(self.fd), "rb") as stream:
                raw = stream.read()
            self.rows, self.previous = [], "0" * 64
            for line in raw.splitlines(keepends=True):
                row = json.loads(line)
                if line != encode(row) or row.get("previous") != self.previous:
                    raise GuardRefusal("journal_chain")
                self.rows.append(row)
                self.previous = hashlib.sha256(line).hexdigest()
            if raw and not raw.endswith(b"\n"):
                raise GuardRefusal("journal_chain")
        except (OSError, ValueError):
            if hasattr(self, "fd"):
                os.close(self.fd)
            raise GuardRefusal("journal") from None

    def append(self, event):
        if self.unusable:
            raise GuardRefusal("journal_write")
        row = dict(event, previous=self.previous, sequence=len(self.rows) + 1)
        raw = encode(row)
        try:
            if os.write(self.fd, raw) != len(raw):
                raise OSError("short append")
            os.fsync(self.fd)
        except OSError:
            self.unusable = True
            raise GuardRefusal("journal_write") from None
        self.rows.append(row)
        self.previous = hashlib.sha256(raw).hexdigest()

    def close(self):
        os.close(self.fd)


class Governor:
    def __init__(self, caps_path, journal):
        try:
            raw = Path(caps_path).read_bytes()
            self.caps = json.loads(raw)
            self.caps_hash = hashlib.sha256(raw).hexdigest()
            self._validate_caps()
        except (OSError, TypeError, ValueError, KeyError, AttributeError):
            raise GuardRefusal("caps") from None
        self.journal = journal
        self.lock = threading.RLock()
        self.reservations = {}
        self.deadlines = {}
        self.outstanding = {}
        self.requests = []
        self.submits = []
        self.last_now = -1
        self.serial = len(journal.rows)
        self.submitted = set()
        for row in journal.rows:
            if row.get("caps_sha256") != self.caps_hash:
                raise GuardRefusal("journal_caps_binding")
            key = row.get("client_order_id")
            if row.get("event") in ("decision", "submit") and key:
                self.outstanding[key] = row.get("payload", self.outstanding.get(key, {}))
            if row.get("event") == "submit" and key:
                self.submitted.add(key)
            if row.get("event") == "reconciled" and key:
                self.outstanding.pop(key, None)
            if row.get("event") == "budget":
                self.last_now = max(self.last_now, row["now_ns"])
                self.requests.extend([row["now_ns"]] * row["request_units"])
                self.submits.extend([row["now_ns"]] * row["submit_units"])
        self.recovery_required = bool(self.outstanding)

    def _validate_caps(self):
        c = self.caps
        expected = {"max_names", "max_notional_usd_per_name", "whole_shares", "max_spread_bps",
                    "ask_min_usd", "ask_max_usd", "quote_max_age_seconds", "trade_max_age_seconds",
                    "max_requests_per_minute", "max_submits_per_minute", "collar", "short_sales",
                    "order_types", "time_in_force", "sessions"}
        if set(c) != expected:
            raise GuardRefusal("caps")
        for key in ("max_names", "quote_max_age_seconds", "trade_max_age_seconds",
                    "max_requests_per_minute", "max_submits_per_minute"):
            if type(c[key]) is not int or c[key] <= 0:
                raise GuardRefusal("caps")
        for key in ("max_notional_usd_per_name", "max_spread_bps", "ask_min_usd", "ask_max_usd"):
            if dec(c[key]) <= 0:
                raise GuardRefusal("caps")
        if (c["whole_shares"] is not True or c["short_sales"] is not False
                or c["order_types"] != ["limit"] or c["time_in_force"] != ["day"]
                or c["sessions"] != {"PRE": True, "RTH": False, "POST": True, "OVERNIGHT": True}
                or any(type(value) is not bool for value in c["sessions"].values())
                or set(c["collar"]) != {"regular_bps", "extended_bps_over_spread"}
                or any(dec(x) <= 0 for x in c["collar"].values())
                or dec(c["ask_min_usd"]) > dec(c["ask_max_usd"])):
            raise GuardRefusal("caps")

    def record(self, event, **fields):
        self.journal.append(dict(event=event, caps_sha256=self.caps_hash, **fields))

    def refuse(self, code):
        self.record("refusal", reason=code)
        return Refusal(code)

    def reject(self, code):
        self.refuse(code)
        raise GuardRefusal(code)

    def _time(self, now):
        if type(now) is not int or now < 0 or now < self.last_now:
            self.reject("clock")
        self.last_now = now

    def budget(self, now, *, submit=False, units=4):
        """Reserve worst-case SDK attempts (alpaca-py rest.py:127-135).

        Default client retry ceiling is three retries. Never sleep/retry here;
        reserving four attempts is conservative and preserves actual limits.
        """
        self._time(now)
        if type(units) is not int or not 1 <= units <= 4:
            self.reject("retry_cap")
        self.requests = [x for x in self.requests if x > now - 60_000_000_000]
        self.submits = [x for x in self.submits if x > now - 60_000_000_000]
        if (len(self.requests) + units > self.caps["max_requests_per_minute"]
                or submit and len(self.submits) + units > self.caps["max_submits_per_minute"]):
            self.reject("request_budget")
        self.record("budget", now_ns=now, request_units=units, submit_units=units if submit else 0)
        self.requests.extend([now] * units)
        if submit:
            self.submits.extend([now] * units)

    def decide(self, intent, quote, account, now):
        with self.lock:
            try:
                return self._decide(intent, quote, account, now)
            except GuardRefusal as error:
                return self.refuse(str(error))
            except (AttributeError, TypeError, ValueError, KeyError, ArithmeticError):
                return self.refuse("input")

    def _decide(self, intent, quote, account, now):
        if self.recovery_required:
            raise GuardRefusal("reconciliation_required")
        if (not isinstance(intent, Intent) or intent.asset_type != "stock"
                or not isinstance(intent.symbol, str) or not re.fullmatch(r"[A-Z][A-Z0-9.-]{0,14}", intent.symbol)):
            raise GuardRefusal("stock_only")
        if intent.side not in ("buy", "sell") or intent.sizing != ("entry" if intent.side == "buy" else "exit_all"):
            raise GuardRefusal("intent")
        if quote.session not in self.caps["sessions"]:
            raise GuardRefusal("session")
        self._time(now)
        checks = [(quote.clock_ns, 250_000_000, "clock"),
                  (quote.quote_ns, self.caps["quote_max_age_seconds"] * 10**9, "stale_quote")]
        if intent.side == "buy":      # CC ruling 2026-10-13 12:30Z (a): an exit needs a fresh two-sided quote, not a recent print
            checks.append((quote.trade_ns, self.caps["trade_max_age_seconds"] * 10**9, "stale_trade"))
        for value, age, reason in checks:
            if type(value) is not int or not 0 <= now - value <= age:
                raise GuardRefusal(reason)
        # CC ruling (c): an unknown open order refuses entries but never the exit of a held position; our own working order is covered by `outstanding` and `recovery_required`
        if account.reconciled is not True or (intent.side == "buy" and account.open_orders):
            raise GuardRefusal("account_reconciliation")
        if self.outstanding:
            raise GuardRefusal("pending_outcome")
        equity, bid, ask = dec(account.equity), dec(quote.bid), dec(quote.ask)
        # Astra B1 (ca52c176): an exit is sized from the held quantity and priced from the bid, so account equity gates entries only (a long position stays exitable at zero or negative equity)
        if bid <= 0 or ask < bid or (intent.side == "buy" and equity <= 0):
            raise GuardRefusal("quote_account")
        if intent.side == "buy" and not dec(self.caps["ask_min_usd"]) <= ask <= dec(self.caps["ask_max_usd"]):
            raise GuardRefusal("ask_band")
        mid = (bid + ask) / 2
        spread = (ask - bid) / mid * 10000
        if intent.side == "buy" and spread > dec(self.caps["max_spread_bps"]):
            raise GuardRefusal("spread")
        positions = {symbol: dec(qty) for symbol, qty in account.positions.items()}
        held = positions if intent.side == "buy" else {intent.symbol: positions.get(intent.symbol, D(0))}      # CC ruling (b): an exit needs an integral quantity only for the symbol it sells
        if any(qty < 0 or qty != qty.to_integral_value() for qty in held.values()):
            raise GuardRefusal("position")
        if intent.side == "buy":
            names = {symbol for symbol, qty in positions.items() if qty}
            if intent.symbol not in names and len(names) >= self.caps["max_names"]:
                raise GuardRefusal("name_cap")
            if positions.get(intent.symbol, 0):
                raise GuardRefusal("existing_position")
        price = rounded(ask if intent.side == "buy" else bid, intent.side)
        collar = dec(self.caps["collar"]["regular_bps"]) if quote.session == "RTH" else spread + dec(self.caps["collar"]["extended_bps_over_spread"])
        if price <= 0 or (intent.side == "buy" and abs(price - mid) / mid * 10000 > collar):
            raise GuardRefusal("collar")
        if intent.side == "buy":
            limit = min(dec(self.caps["max_notional_usd_per_name"]), equity)
            qty = int((limit / price).to_integral_value(rounding=ROUND_FLOOR))
        else:
            qty = int(positions.get(intent.symbol, 0))
        if qty <= 0:
            raise GuardRefusal("quantity")
        if intent.side == "buy" and qty * price > limit:
            raise GuardRefusal("notional_cap")
        if intent.side == "sell" and qty > positions.get(intent.symbol, 0):
            raise GuardRefusal("short_sale")
        self.serial += 1
        cid = CLIENT_ID_PREFIX + str(self.serial).zfill(12)
        decision = Decision(intent.symbol, intent.side, qty, price,
                            self.caps["sessions"][quote.session], cid, cid)
        self.record("decision", client_order_id=cid, payload=decision.payload(), reason="allowed")
        self.reservations[cid] = decision.payload()
        quote_deadline = quote.quote_ns + self.caps["quote_max_age_seconds"] * 10**9
        self.deadlines[cid] = quote_deadline if intent.side == "sell" else min(
            quote_deadline, quote.trade_ns + self.caps["trade_max_age_seconds"] * 10**9)      # CC ruling (a): an exit's deadline comes from the quote alone
        self.outstanding[cid] = decision.payload()
        return decision

    def consume(self, payload, token, now):
        self._time(now)
        if type(now) is not int or now > self.deadlines.get(token, -1):
            self.reject("reservation_expired")
        expected = self.reservations.get(token)
        if expected is None or payload != expected:
            self.reject("reservation")
        del self.reservations[token]
        self.deadlines.pop(token,None)
        self.record("submit", client_order_id=token, payload=payload, outcome="pending")
        self.submitted.add(token)

    def outcome(self, token, result):
        self.record("outcome", client_order_id=token, outcome=result)
        # Even an SDK response is not a reconciled position/fill snapshot.
        if result == "unknown":
            self.recovery_required = True

    def is_ours(self, entry):
        """An open order is ours when its client order id carries the arm prefix and appears in the journal's submit rows."""
        cid = entry.get("client_order_id") if isinstance(entry, dict) else getattr(entry, "client_order_id", entry)
        return isinstance(cid, str) and cid.startswith(CLIENT_ID_PREFIX) and cid in self.submitted

    def reconcile(self, client_order_id, *, terminal, account):
        with self.lock:
            if (terminal not in ("filled", "canceled", "rejected", "expired", "not_sent")
                    or account.reconciled is not True or any(self.is_ours(entry) for entry in account.open_orders)
                    or client_order_id not in self.outstanding):
                self.reject("reconciliation_required")
            self.record("reconciled", client_order_id=client_order_id, outcome=terminal)
            self.outstanding.pop(client_order_id)
            self.reservations.pop(client_order_id, None)
            self.deadlines.pop(client_order_id, None)
            self.recovery_required = bool(self.outstanding)
