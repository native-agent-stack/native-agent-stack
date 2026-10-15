#!/usr/bin/env python3
"""Display-neutral FIELDS-v1 projection. Raw identifiers exist only in memory."""
from datetime import datetime
import argparse
import fcntl
import json
import math
import os
from pathlib import Path
import re
import stat
import time
from zoneinfo import ZoneInfo


ENVELOPE = {"v", "lane", "kind", "t_ms", "seq", "run", "session", "observed_ms", "row_id"}
MIN_TIME, MAX_TIME = 1500000000000, 4102444800000
ROW_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,47}:\d{1,12}(:\d{1,4})?\Z")


def private_identity(value):
    if not isinstance(value, str):
        return False
    private = {Path.home().name.casefold(), os.uname().nodename.casefold()} - {""}
    return bool(re.search(r"(?i)(?:DU|U|F)\d{5,}", value)) or any(v in value.casefold() for v in private)
IBKR = {
    "submit": "order_key:key symbol:symbol side:side qty:num limit_price:num outside_rth:bool quote_bid:num quote_ask:num quote_arrival_ms:time quote_age_ms:int",
    "ack": "order_key:key status:status",
    "status": "order_key:key status:status filled:num remaining:num avg_fill_price:num last_fill_price:num",
    "cancel_sent": "order_key:key", "cancel_ack": "order_key:key",
    "fill": "order_key:key symbol:symbol side:side exec_qty:num exec_price:num exec_time_ms:time cum_qty:num",
    "commission": "order_key:key commission:num commission_currency:currency realized_pnl:num",
    "reject": "order_key:key code:int", "error": "code:int",
    "account": "net_liquidation:num total_cash_value:num",
    "position": "symbol:symbol qty:num avg_cost:num",
    "pnl": "daily_pnl:num unrealized_pnl:num realized_pnl:num",
    "pnl_single": "symbol:symbol position:num daily_pnl:num unrealized_pnl:num realized_pnl:num value:num",
    "wire": "messages:int peak_per_second:num total:int",
}
RANK_NUMBERS = "score move_pct rvol spread_bps quote_age_s trade_age_s vwap last bid ask band_pct range_pct fade_pct stop_pct trail_pct session_dollar_vol vol_session ref_close ret_3m_pct ret_ytd_pct"
C = {
    "rank_round": "round_key:round slots:int held:int held_symbols:symbols added_impulse:int added_trend:int round_seconds:num round_tool_calls:int",
    "rank_row": "round_key:round rank:int symbol:symbol eligible:bool group:code asset_class:code halt_prone:bool reasons:reasons reason_count:int " + " ".join(k + ":num" for k in RANK_NUMBERS.split()),
    "no_selection_round": "eligible:int ranked:int top_symbols:symbols round_seconds:num round_tool_calls:int",
    "size_check": "symbol:symbol ok:bool qty:int limit_price:num notional:num equity_cap:num drift_pct:num drift_ref_last:num quote_bid:num quote_ask:num quote_mid:num quote_age_s:num quote_time_ms:time cap_binding:code refusals:reasons",
    "entry_order": "order_key:key symbol:symbol qty:int limit_price:num move_pct:num rvol:num score:num catalyst_present:bool",
    "entry_fill": "order_key:key symbol:symbol qty:int price:num booked_qty:int booked_avg:num delta_qty:int delta_price:num repeat:bool",
    "trail_order": "order_key:key symbol:symbol",
    "exit_order": "order_key:key symbol:symbol qty:int limit_price:num reason:code",
    "exit_fill": "order_key:key symbol:symbol qty:int price:num realized_usd:num reason:code position_closed:bool remaining_qty:int booked_qty:int booked_avg:num delta_qty:int delta_price:num repeat:bool",
    "reconcile": "match:bool exit_mode:code held_count:int mismatch_count:int resting_exit_count:int",
    "preflight_ok": "equity:num adopted_symbols:symbols clock:code",
    "preflight_refused": "equity:num mismatch_count:int clock:code",
    "flatten_done": "open_orders:int positions:int",
    "final_flat": "fills:int orders:int realized_total_usd:num exit_reason_counts:counts",
}
SCHEMAS = {lane: {kind: dict(f.split(":") for f in fields.split()) for kind, fields in kinds.items()}
           for lane, kinds in (("IBKR", IBKR), ("C", C))}
STATUS = {"PendingSubmit", "PendingCancel", "PreSubmitted", "Submitted", "ApiPending", "ApiCancelled", "Cancelled", "Filled", "Inactive"}
MAX_SPOOL = 8 * 1024 * 1024


def iso_ms(value):
    if not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return int(dt.timestamp() * 1000) if dt.tzinfo is not None else None
    except (ValueError, OverflowError, OSError):
        return None


def eastern_ms(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{8} \d{2}:\d{2}:\d{2} US/Eastern", value):
        return None
    try:
        dt = datetime.strptime(value, "%Y%m%d %H:%M:%S US/Eastern").replace(tzinfo=ZoneInfo("America/New_York"))
        return int(dt.timestamp() * 1000)
    except (ValueError, OverflowError, OSError):
        return None


def convert(value, rule):
    if value is None:
        return None
    if rule == "num":
        if type(value) not in (int, float, str):
            return None
        if isinstance(value, str) and (len(value) > 200 or not re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", value)):
            return None
        try:
            number = float(value)
            return number if math.isfinite(number) and abs(number) <= 10**12 else None
        except (ValueError, TypeError, OverflowError):
            return None
    if rule in ("int", "time"):
        return value if type(value) is int and (MIN_TIME <= value <= MAX_TIME if rule == "time" else abs(value) <= 10**9) else None
    if rule == "bool":
        return value if type(value) is bool else None
    if rule == "symbol":
        return value if isinstance(value, str) and not private_identity(value) and re.fullmatch(r"[A-Z]{1,5}([.-][A-Z]{1,2})?", value) else "OTHER"
    if rule == "side":
        return value.lower() if isinstance(value, str) and value.lower() in ("buy", "sell") else "OTHER"
    if rule == "status":
        return value if isinstance(value, str) and value in STATUS else "OTHER"
    if rule == "currency":
        return value if value == "USD" else "OTHER"
    if rule == "code":
        return value if isinstance(value, str) and not private_identity(value) and re.fullmatch(r"[a-z][a-z0-9_]{0,31}", value) else "OTHER"
    if rule == "symbols":
        return [convert(v, "symbol") for v in value[:20]] if isinstance(value, list) else None
    if rule == "reasons":
        if not isinstance(value, list):
            return None
        reasons = []
        for text in value[:8]:
            if not isinstance(text, str) or private_identity(text) or re.search(r"[/\\@\"'\x00-\x1f\x7f-\x9f]", text):
                continue
            text = re.sub(r"\d+", "#", text)
            text = re.sub(r"(?<![A-Za-z0-9_.-])[A-Z]{1,5}(?:[.-][A-Z]{1,2})?(?![A-Za-z0-9_.-])", "SYM", text)
            reasons.append(text[:80])
        return reasons
    if rule == "counts":
        return {convert(k, "code"): v for k, v in value.items() if convert(v, "int") is not None} if isinstance(value, dict) else None
    if rule in ("key", "round"):
        suffix = "o" if rule == "key" else "r"
        return value if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,47}/" + suffix + r"[1-9]\d*", value) else None
    return value


class Projector:
    """One source file's joins. Rebuild by replaying that file on restart."""

    def __init__(self):
        self.orders = {}
        self.executions = {}
        self.round = 0
        self.refused = 0

    def order(self, source, run):
        ids = [(run, k, source[k]) for k in ("client_order_id", "order_id", "perm_id")
               if type(source.get(k)) in (str, int)]
        if not ids:
            return None
        existing = next((self.orders[key] for key in ids if key in self.orders), None)
        key = existing or f"{run}/o{len(set(self.orders.values())) + 1}"
        for identity in ids:
            self.orders[identity] = key
        return key

    def valid(self, row):
        if not isinstance(row, dict) or not isinstance(row.get("lane"), str) or row["lane"] not in SCHEMAS or not isinstance(row.get("kind"), str):
            return False
        schema = SCHEMAS[row["lane"]].get(row.get("kind"))
        if schema is None:
            return False
        allowed = ENVELOPE | set(schema)
        if row["lane"] == "C":
            allowed |= {"calc_version", "event_key"}
            allowed -= {"seq"}
        required = {"v", "lane", "kind", "t_ms", "run", "row_id"}
        if row["lane"] == "IBKR":
            required.add("seq")
        if not required <= set(row) <= allowed or type(row.get("v")) is not int or row["v"] != 1:
            return False
        if convert(row.get("t_ms"), "time") is None or ("observed_ms" in row and convert(row["observed_ms"], "time") is None):
            return False
        if not isinstance(row.get("row_id"), str) or not ROW_ID.fullmatch(row["row_id"]):
            return False
        if not isinstance(row.get("run"), str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,47}", row["run"]):
            return False
        if private_identity(row["run"]) or ("session" in row and private_identity(row["session"])):
            return False
        for field, pattern in (("session", r"[A-Za-z0-9_-]{1,12}"),
                               ("calc_version", r"\d+(\.\d+){1,3}"), ("event_key", r"[a-f0-9]{8,64}")):
            if field in row and (not isinstance(row[field], str) or not re.fullmatch(pattern, row[field])):
                return False
        if not row["row_id"].startswith(row["run"] + ":"):
            return False
        if any(not row[k].startswith(row["run"] + "/") for k in ("order_key", "round_key") if isinstance(row.get(k), str)):
            return False
        if "seq" in row and convert(row["seq"], "int") is None:
            return False
        for key, rule in schema.items():
            if key in row and convert(row[key], rule) != row[key]:
                return False
        return True

    def append(self, path, rows):
        if not all(self.valid(row) for row in rows):
            self.refused += 1
            return False
        try:
            payload = "".join(json.dumps(row, separators=(",", ":"), allow_nan=False) + "\n" for row in rows)
        except (ValueError, TypeError):
            self.refused += 1
            return False
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(path, os.O_CREAT | os.O_WRONLY | os.O_APPEND, 0o600)
        with os.fdopen(fd, "a", encoding="utf-8") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            os.fchmod(stream.fileno(), 0o600)
            if os.fstat(stream.fileno()).st_size > MAX_SPOOL:
                stream.truncate(0)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        return True

    def project(self, lane, source, *, run=None, observed_ms, source_offset=0, item_index=None):
        if not isinstance(source, dict) or lane not in SCHEMAS:
            self.refused += 1
            return []
        kind = source.get("kind") if lane == "IBKR" else source.get("type")
        run = source.get("trial") if lane == "IBKR" else run
        moment = iso_ms(source.get("t_utc") if lane == "IBKR" else source.get("t"))
        if not isinstance(kind, str) or kind not in SCHEMAS[lane] or not isinstance(run, str) or private_identity(run) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,47}", run) or convert(moment, "time") is None or (lane == "IBKR" and convert(source.get("seq"), "int") is None):
            self.refused += 1
            return []
        row = dict(v=1, lane=lane, kind=kind, t_ms=moment, run=run,
                   row_id=f"{run}:{source_offset}" + (f":{item_index}" if item_index is not None else ""))
        if convert(observed_ms, "time") is not None:
            row["observed_ms"] = observed_ms
        session = source.get("session") if lane == "IBKR" else source.get("segment")
        if isinstance(session, str) and not private_identity(session) and re.fullmatch(r"[A-Za-z0-9_-]{1,12}", session):
            row["session"] = session
        if lane == "IBKR" and convert(source.get("seq"), "int") is not None:
            row["seq"] = source["seq"]
        values = dict(source)
        if lane == "IBKR" and kind == "fill":
            values["exec_time_ms"] = eastern_ms(source.get("exec_time"))
        if lane == "IBKR" and kind == "submit" and isinstance(source.get("pricing_observation"), dict):
            quote = source["pricing_observation"]
            values["quote_bid"], values["quote_ask"] = quote.get("bid"), quote.get("ask")
            arrival = iso_ms(quote.get("arrival_utc"))
            values["quote_arrival_ms"] = arrival
            values["quote_age_ms"] = moment - arrival if arrival is not None else None
        if lane == "C" and kind == "size_check":
            values["quote_time_ms"] = iso_ms(source.get("quote_time"))
        key = self.order(source, run)
        if kind == "fill" and isinstance(source.get("exec_id"), str) and key:
            self.executions[source["exec_id"]] = key
        if kind == "commission":
            key = self.executions.get(source["exec_id"]) if isinstance(source.get("exec_id"), str) else None
        values["order_key"] = key
        if lane == "C":
            if kind == "rank_round":
                self.round += 1
            values["round_key"] = f"{run}/r{self.round}" if self.round else None
            for field, original in (("held_count", "held"), ("mismatch_count", "mismatches"), ("resting_exit_count", "resting_exits")):
                if isinstance(source.get(original), (list, dict)):
                    values[field] = len(source[original])
            if isinstance(source.get("added_by_group"), dict):
                for group in ("impulse", "trend"):
                    values["added_" + group] = source["added_by_group"].get(group)
            if isinstance(source.get("top"), list):
                values["top_symbols"] = [v.split()[0] for v in source["top"][:20] if isinstance(v, str) and v.split()]
            if kind == "entry_order":
                values["catalyst_present"] = bool(source.get("catalyst"))
            if isinstance(source.get("realized_usd"), dict):
                nums = [convert(v, "num") for v in source["realized_usd"].values()]
                if all(v is not None for v in nums):
                    values["realized_total_usd"] = sum(nums)
            for field, pattern in (("calc_version", r"\d+(\.\d+){1,3}"), ("event_key", r"[a-f0-9]{8,64}")):
                value = source.get("eid" if field == "event_key" else field)
                if isinstance(value, str) and re.fullmatch(pattern, value):
                    row[field] = value
        for name, rule in SCHEMAS[lane][kind].items():
            value = convert(values.get(name), rule)
            if value is not None:
                row[name] = value
        rows = [row]
        if lane == "C" and kind == "rank_round" and isinstance(source.get("rows"), list):
            for index, item in enumerate(source["rows"]):
                if isinstance(item, dict):
                    child = dict(source)
                    child.update(item)
                    child["type"] = "rank_row"
                    child.pop("rows", None)
                    rows.extend(self.project(lane, child, run=run, observed_ms=observed_ms,
                                             source_offset=source_offset, item_index=index))
        if not all(self.valid(item) for item in rows):
            self.refused += 1
            return []
        return rows


def atomic_json(path, value):
    """Durable private metadata replacement; never called on a producer path."""
    temporary = path.with_suffix(".tmp")
    fd = os.open(temporary, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        os.fchmod(stream.fileno(), 0o600)
        json.dump(value, stream, separators=(",", ":"), allow_nan=False)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class Tailer:
    """Inode/offset tail with an own-state write-ahead commit for each line.

    Checkpoints contain no raw source ids or paths. On restart a file is
    replayed from0 to reconstruct joins; only new complete lines are emitted.
    A pending commit carries sanitized bytes only, so append/checkpoint crashes
    can be recovered without adding the same line twice to the local spool.
    This guarantee ends at the spool; Collector/Loki delivery is separate.
    """

    def __init__(self, state, spool):
        self.state = Path(state)
        self.spool = Path(spool)
        self.state.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.contexts = {}
        self.checkpoint = self.state / "checkpoint.json"
        self.pending = self.state / "pending.json"

    def recover(self):
        if self.pending.exists():
            pending = json.loads(self.pending.read_text())
            self.write_payload(pending["base"], pending["payload"])
            atomic_json(self.checkpoint, pending["checkpoint"])
            self.pending.unlink()
        return json.loads(self.checkpoint.read_text()) if self.checkpoint.exists() else {"files": {}, "refused": 0, "rejected": {}}

    def write_payload(self, base, payload):
        self.spool.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(self.spool, os.O_CREAT | os.O_RDWR, 0o600)
        with os.fdopen(fd, "r+b") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            os.fchmod(stream.fileno(), 0o600)
            stream.seek(base)
            stream.truncate()
            stream.write(payload.encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())

    def commit(self, state, rows):
        payload = "".join(json.dumps(row, separators=(",", ":"), allow_nan=False) + "\n" for row in rows)
        if not payload:
            atomic_json(self.checkpoint, state)
            return
        base = self.spool.stat().st_size if self.spool.exists() else 0
        if base > MAX_SPOOL:
            base = 0
        transaction = {"base": base, "payload": payload, "checkpoint": state}
        atomic_json(self.pending, transaction)
        self.write_payload(base, payload)
        atomic_json(self.checkpoint, state)
        self.pending.unlink()

    def poll(self, lane, source, *, run=None, observed_ms):
        with (self.state / "tail.lock").open("a+b") as lock:
            os.fchmod(lock.fileno(), 0o600)
            fcntl.flock(lock, fcntl.LOCK_EX)
            state = self.recover()
            fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(fd, "rb") as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode):
                    raise ValueError("source is not a regular file")
                identity = f"{info.st_dev}:{info.st_ino}"
                saved = state["files"].get(identity, 0)
                context = self.contexts.get(identity)
                if context is None:
                    projector, offset = Projector(), 0
                else:
                    projector, offset = context
                if info.st_size < max(offset, saved):
                    raise ValueError("in-place source truncation is outside v1")
                stream.seek(offset)
                try:
                    while True:
                        start = stream.tell()
                        line = stream.readline()
                        if not line or not line.endswith(b"\n"):
                            stream.seek(start)
                            break
                        end = stream.tell()
                        try:
                            source_row = json.loads(line)
                        except (ValueError, UnicodeError):
                            source_row = None
                        before = projector.refused
                        rows = projector.project(lane, source_row, run=run, observed_ms=observed_ms, source_offset=start)
                        if end <= saved:
                            continue
                        rejected = state["rejected"].setdefault(identity, [])
                        if not rows or not all(projector.valid(row) for row in rows):
                            if end not in rejected:
                                state["refused"] += max(1, projector.refused - before)
                                rejected.append(end)
                                self.commit(state, [])
                            continue
                        state["files"][identity] = end
                        state["rejected"][identity] = []
                        self.commit(state, rows)
                    self.contexts[identity] = (projector, stream.tell())
                except BaseException:
                    self.contexts.pop(identity, None)
                    raise
            return {"refused": state["refused"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True, help="tailer's own private checkpoint directory")
    parser.add_argument("--spool", type=Path, required=True)
    parser.add_argument("--ibkr-index", type=Path, action="append", default=[])
    parser.add_argument("--ibkr-journal", type=Path, action="append", default=[])
    parser.add_argument("--calc-root", type=Path, action="append", default=[])
    args = parser.parse_args(argv)
    tailer = Tailer(args.state, args.spool)
    sources = {(lane, path, run) for lane, path, run in
               [("IBKR", p, None) for p in args.ibkr_journal]}
    refused = 0
    try:
        for index in args.ibkr_index:
            with index.open("rb") as stream:
                for line in stream:
                    if not line.endswith(b"\n"):
                        continue
                    try:
                        row = json.loads(line)
                    except (ValueError, UnicodeError):
                        continue
                    if not isinstance(row, dict) or not isinstance(row.get("journal"), str):
                        continue
                    path = Path(row["journal"])
                    if not path.is_absolute() and isinstance(row.get("state_dir"), str):
                        path = Path(row["state_dir"]) / path
                    if path.name == "ibkr-events.jsonl" and path.parent.name == "events":
                        sources.add(("IBKR", path, None))
        for root in args.calc_root:
            sources.update(("C", p, p.parent.name) for p in root.glob("run-*/events.jsonl"))
        for lane, source, run in sorted(sources, key=lambda s: (s[0], str(s[1]))):
            health = tailer.poll(lane, source, run=run, observed_ms=time.time_ns() // 10**6)
            refused = health["refused"]
        print(json.dumps({"status": "observed", "sources": len(sources), "refused": refused}))
        return 0
    except (OSError, ValueError, TypeError, OverflowError):
        print(json.dumps({"status": "projection_failed"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
