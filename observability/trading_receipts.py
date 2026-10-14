#!/usr/bin/env python3
"""Read explicitly selected paper receipts; append only numeric/enum projections.

No broker, credential, account identifier, source path or arbitrary text is exported.
The existing research-progress oneshot invokes this writer; Collector file_log tails
the sanitized spool. Receipt files are opened read-only and never copied or hashed.
"""
import argparse
from datetime import datetime, timezone
import fcntl
import json
import math
import os
from pathlib import Path
import re
import time

LANES = ("A", "B", "C", "lanea", "laneb", "IBKR", "I-llm")
UNKNOWN_PNL = -9007199254740991
EXPORTED_FIELDS = ("lane", "observed_unix", "source_unix", "orders_per_min", "fills_per_min",
                   "cancels_per_min", "cash_use_ratio", "open_positions", "realized_pnl_usd",
                   "status_code", "ended_by_code", "wire_mean_per_s", "wire_peak_per_s")
STATUS = {"passed": 2, "completed": 2, "ended": 2, "stopped": 2, "ok": 2,
          "completed_no_signals": 2, "not_started": 0,
          "running": 1, "active": 1, "blocked": 3, "failed": 3, "error": 3}
ENDED = {"duration": 1, "duration_elapsed": 1, "duration_limit": 1, "time_limit": 1,
         "session_end": 2, "session_closed": 2, "stop": 3, "stopped": 3,
         "risk_limit": 4, "drawdown": 4, "error": 5, "failed": 5}


def number(value, default=-1):
    if isinstance(value, bool):
        return default
    try:
        result = float(value)
        return result if math.isfinite(result) and abs(result) < 1e30 else default
    except (ValueError, TypeError, OverflowError):
        return default


def timestamp(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return number(value)
    if isinstance(value, str):
        try:
            result = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return result.timestamp() if result.tzinfo else -1
        except ValueError:
            pass
    return -1


def empty(lane, now, status=0):
    if lane not in LANES:
        raise ValueError("Unsupported lane")
    row = dict.fromkeys(EXPORTED_FIELDS, -1)
    row.update(lane=lane, observed_unix=now, status_code=status, ended_by_code=0,
               realized_pnl_usd=UNKNOWN_PNL)
    return row


def ratio(numerator, denominator):
    a, b = number(numerator), number(denominator)
    return a / b if a >= 0 and b > 0 else -1


def paper_observation(lane, receipt, source_unix, observed_unix):
    row = empty(lane, observed_unix)
    seconds = number(receipt.get("elapsed_seconds"))
    requests = receipt.get("requests")
    if seconds > 0 and isinstance(requests, list):
        row["orders_per_min"] = sum(isinstance(r, dict) and r.get("kind") == "submit" for r in requests) * 60 / seconds
        row["cancels_per_min"] = sum(isinstance(r, dict) and r.get("kind") == "cancel" for r in requests) * 60 / seconds
        fills = number(receipt.get("native_fill_events"))
        if fills >= 0:
            row["fills_per_min"] = fills * 60 / seconds
    accounting = receipt.get("accounting") if isinstance(receipt.get("accounting"), dict) else {}
    row["open_positions"] = number(accounting.get("held_symbols"))
    row["realized_pnl_usd"] = number(accounting.get("realized_pnl_usd"), UNKNOWN_PNL)
    leverage = receipt.get("leverage") if isinstance(receipt.get("leverage"), dict) else {}
    # broker_cash_at_start is cash, not account equity; do not silently rename its denominator.
    equity = leverage.get("broker_equity_at_start", accounting.get("equity_usd"))
    row["cash_use_ratio"] = ratio(leverage.get("peak_gross_exposure_usd"), equity)
    row["source_unix"] = source_unix
    row["status_code"] = STATUS.get(receipt.get("status"), 99)
    row["ended_by_code"] = ENDED.get(receipt.get("ended_by"), 99 if receipt.get("ended_by") else 0)
    return row


def load(path):
    try:
        with path.open(encoding="utf-8") as stream:
            result = json.load(stream)
        return result if isinstance(result, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def paper_lane(lane, paths, now):
    for path in sorted(paths, key=lambda p: p.stat().st_mtime, reverse=True):
        receipt = load(path)
        if not isinstance(receipt.get("requests"), list) or "accounting" not in receipt:
            continue
        return paper_observation(lane, receipt, path.stat().st_mtime, now)
    return empty(lane, now)


def event_observation(lane, events, state, now, source_unix):
    row = empty(lane, now)
    counts = {"orders_per_min": 0, "fills_per_min": 0, "cancels_per_min": 0}
    equity, latest = -1, -1
    for event in events:
        if not isinstance(event, dict):
            continue
        kind = event.get("type", event.get("event", event.get("kind")))
        moment = timestamp(event.get("t", event.get("ts", event.get("utc", event.get("time")))))
        if moment > now + 5:
            continue
        latest = max(latest, moment)
        if kind == "preflight_ok":
            equity = number(event.get("equity"))
        if now - 60 < moment <= now:
            if kind in ("entry_order", "exit_order", "trail_order"):
                counts["orders_per_min"] += 1
            elif kind in ("entry_fill", "exit_fill", "trail_fill", "fill"):
                counts["fills_per_min"] += 1
            elif kind in ("cancel", "cancel_order", "order_cancelled"):
                counts["cancels_per_min"] += 1
        if kind in ("session_end", "segment_end", "stop", "ended"):
            row["status_code"] = 2
            row["ended_by_code"] = ENDED.get(event.get("ended_by", event.get("reason")), 99)
    row.update(counts)
    positions = state.get("positions")
    if isinstance(positions, dict):
        row["open_positions"] = len(positions)
        values = [number(p.get("qty")) * number(p.get("entry")) for p in positions.values()
                  if isinstance(p, dict) and number(p.get("qty")) >= 0 and number(p.get("entry")) >= 0]
        if len(values) == len(positions):
            row["cash_use_ratio"] = ratio(sum(values), equity)
    realized = state.get("realized_usd")
    if isinstance(realized, dict):
        values = [number(value, UNKNOWN_PNL) for value in realized.values()]
        row["realized_pnl_usd"] = sum(values) if all(value != UNKNOWN_PNL for value in values) else UNKNOWN_PNL
    else:
        row["realized_pnl_usd"] = number(realized, UNKNOWN_PNL)
    row["source_unix"] = latest if latest > 0 else source_unix
    if row["status_code"] != 2:
        row["status_code"] = 1 if now - row["source_unix"] < 180 else 6
    return row


def event_lane(lane, roots, now):
    candidates = [p for p in roots if (p / "events.jsonl").is_file()]
    if not candidates:
        return empty(lane, now, 5 if lane == "I-llm" else 0)
    root = max(candidates, key=lambda p: (p / "events.jsonl").stat().st_mtime)
    events = []
    try:
        with (root / "events.jsonl").open(encoding="utf-8") as stream:
            for line in stream:
                try:
                    events.append(json.loads(line))
                except ValueError:
                    continue
    except OSError:
        return empty(lane, now)
    if not events:
        return empty(lane, now)
    return event_observation(lane, events, load(root / "state.json"), now, (root / "events.jsonl").stat().st_mtime)


def ibkr_observation(summary, session_time, now):
    row = empty("IBKR", now, 4)
    row["source_unix"] = session_time
    seconds = number(summary.get("elapsed_s"))
    for metric, source in [("orders_per_min", "submits"), ("cancels_per_min", "cancels"), ("fills_per_min", "fills")]:
        value = number(summary.get(source))
        if seconds > 0 and value >= 0:
            row[metric] = value * 60 / seconds
    row["cash_use_ratio"] = number(summary.get("cash_use_peak"))
    # Status summary cash delta is not realized P&L; the full receipt supplies it separately.
    row["wire_mean_per_s"] = number(summary.get("wire_mean_per_s"))
    row["wire_peak_per_s"] = number(summary.get("wire_peak_per_s"))
    if summary.get("flat") is True:
        row["open_positions"] = 0
    row["ended_by_code"] = ENDED.get(summary.get("ended_by"), 99 if summary.get("ended_by") else 0)
    return row


def ibkr_lane(status_path, receipts_root, now):
    row = empty("IBKR", now, 4)
    started = -1
    try:
        with status_path.open(encoding="utf-8") as stream:
            for line in stream:
                # Extract only its timestamp; client IDs/state paths never enter the projection.
                start_match = re.match(r'^(\S+) session k=\d+ start ', line)
                if start_match:
                    started = max(started, timestamp(start_match[1]))
                match = re.match(r'^(\S+) session k=\d+ end rc=-?\d+ (\{.*\})\s*$', line)
                if match:
                    try:
                        summary = json.loads(match[2])
                    except ValueError:
                        continue
                    if isinstance(summary, dict):
                        row = ibkr_observation(summary, timestamp(match[1]), now)
    except OSError:
        pass
    receipts = list(receipts_root.glob('*/receipts/ibp-*-paper.json'))
    if receipts:
        path = max(receipts, key=lambda p: p.stat().st_mtime)
        receipt = load(path)
        accounting = receipt.get("accounting") if isinstance(receipt.get("accounting"), dict) else {}
        row["realized_pnl_usd"] = number(accounting.get("realized_pnl_usd"), UNKNOWN_PNL)
        row["open_positions"] = number(accounting.get("held_symbols"), row["open_positions"])
        if row["source_unix"] < 0:
            row["source_unix"] = path.stat().st_mtime
    if started > row["source_unix"] and started <= now:
        row["status_code"] = 1
        row["source_unix"] = started
        row["ended_by_code"] = 0
    return row


def collect(home, runs_root, ibkr_status, ibkr_receipts, now=None):
    now = time.time() if now is None else now
    a = paper_lane("A", list((home / '.local/state/native-agent-stack/alpaca-paper-2').glob('lane-a-*/receipts/paper-*.json')), now)
    b = paper_lane("B", list((home / '.local/state/native-agent-stack/alpaca-paper').glob('forward-ready-*/instances/*/scheduled/paper-output.json')), now)
    roots = list(runs_root.glob('run-*'))
    rows = [a, b]
    for lane in ("C", "lanea", "laneb", "I-llm"):
        selected = [p for p in roots if (lane == "C" and not any(x in p.name for x in ['lanea', 'laneb', 'illm', 'i-llm']))
                    or (lane in ['lanea', 'laneb'] and ('-' + lane + '-') in p.name)
                    or (lane == "I-llm" and any(x in p.name for x in ['illm', 'i-llm']))]
        rows.append(event_lane(lane, selected, now))
    rows.append(ibkr_lane(ibkr_status, ibkr_receipts, now))
    return sorted(rows, key=lambda row: LANES.index(row['lane']))


def append_spool(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Bounded snapshot stream; upstream file_log detects copy-truncation.
    with path.open('a+', encoding='utf-8') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        os.chmod(path, 0o600)
        stream.seek(0, os.SEEK_END)
        if stream.tell() > 8 * 1024 * 1024:
            stream.seek(0)
            stream.truncate()
        for row in rows:
            if set(row) != set(EXPORTED_FIELDS) or row['lane'] not in LANES:
                raise ValueError('Invalid projection')
            stream.write(json.dumps(row, separators=(',', ':'), allow_nan=False) + '\n')
        stream.flush()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spool', type=Path, required=True)
    parser.add_argument('--home', type=Path, default=Path.home())
    parser.add_argument('--runs-root', type=Path, default=Path('/var/tmp/cc-overnight-mcp'))
    parser.add_argument('--ibkr-status', type=Path, default=Path('/var/tmp/trading-cc-wt/ibkr-lane-build/ibkr-series-20261013.status'))
    args = parser.parse_args()
    try:
        rows = collect(args.home, args.runs_root, args.ibkr_status,
                       args.home / '.local/state/native-agent-stack/ibkr-lane-20261013/exploratory')
        append_spool(args.spool, rows)
        print(json.dumps({'status': 'observed', 'lanes': len(rows)}))
        return 0
    except (OSError, ValueError, TypeError):
        print(json.dumps({'status': 'observation_failed'}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
