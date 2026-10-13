#!/usr/bin/env python3
"""Build the sanitized IBKR pacing evidence document (ibkr-pacing-evidence/1, revision 2) from the private run receipts.

Revision 2 (supersedes the sealed v1 generator/JSON/verifier named in the document's `revision` block): the 38 journal orders missing at the broker are classified by their journal
events AND the venue's refusal text (35 [103] "Duplicate order id", 1 cancel-target-not-found rejection, 2 never reached the adapter), where v1 labelled all 36 rejections [103];
the third independent broker count (after the pair tests) is added as a transcript-derived value with its arithmetic relation.

Standard library only; deterministic (no clock, no environment, no randomness); it reads files under the run root passed
as the single argument and prints one JSON document (sorted keys, 1-space indent) to stdout. It never emits account
codes, client ids, order ids, order references, paths or host names: only counts, rates, latencies in milliseconds,
error-code counts, booleans and category words.

Run root layout (private): runs/<LABEL>/receipt.json (+ journal.jsonl, vendor.log for the adapter runs), runs/marker-*.json,
journal-submitted-ids.txt.missing (the journal-side order references the broker did not list; read for COUNTS only).

usage: python3 generate_ibkr_pacing_evidence.py RUN_ROOT > ibkr-pacing-evidence-20261013.json
"""
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

SCHEMA = "ibkr-pacing-evidence/1"
ADAPTER_B_RUNS = ["B-r2", "B-r3", "B-r4", "B-r5", "B-r6"]
ADAPTER_A_RUNS = ["A-r1", "A-r2", "A-r3", "A-r4", "A-r5", "A-r6"]
ADAPTER_L_PAIRS = ["m1", "m2", "m3", "m4"]
PAIR_TESTS = ["E1", "E2", "T1", "T1b", "T2", "T3", "T4", "T6", "T7", "T8", "T9a", "T9b", "T10"]

# Values that exist only in the session transcript (live broker reads, no receipt file). Marked as such in the output.
TRANSCRIPT_DERIVED = {
    "broker_completed_orders_after_harness_runs": 6292,
    "broker_completed_orders_all_sources_equals_api_only": True,
    "broker_completed_orders_after_official_client_runs": 8494,
    "broker_completed_orders_after_pair_tests": 10313,
    "reqids_probe": {
        "a_next_valid_at_connect": 1,
        "a_reqIds_before_other_connection_order": 1,
        "a_reqIds_while_other_connection_order_open": 1,
        "a_reqIds_after_other_connection_cancel": 1,
        "b_reqIds_while_its_own_order_open_minus_its_order_id": 1,
        "other_connection_order_status_while_open": "Submitted",
        "other_connection_order_status_after_cancel": "Cancelled",
    },
}

# Test designs as declared by the runner scripts' command lines (not receipt fields).
DESIGN = {
    "E1": {"order_id_scheme": "arbitrary bases 1e8+n and 2e8+n", "client_ids": "fresh", "hold_s": 0.0, "poll_all_open_orders": "none", "account_field": False, "order_ref": False, "account_updates": False},
    "E2": {"order_id_scheme": "equal bases 3e8+n on both, above every id E1 used", "client_ids": "the same two ids as E1", "hold_s": 0.0, "poll_all_open_orders": "none", "account_field": False, "order_ref": False, "account_updates": False},
    "T1": {"order_id_scheme": "client-partitioned ids restarted at 1, below the ids those clients used earlier the same day", "client_ids": "reused from an earlier adapter run", "hold_s": 0.0, "poll_all_open_orders": "none", "account_field": False, "order_ref": False, "account_updates": False},
    "T1b": {"order_id_scheme": "client-partitioned ids from 1", "client_ids": "fresh", "hold_s": 0.0, "poll_all_open_orders": "none", "account_field": False, "order_ref": False, "account_updates": False},
    "T2": {"order_id_scheme": "client-partitioned ids from 1", "client_ids": "fresh", "hold_s": "1.5 first / 3.0 second", "poll_all_open_orders": "none", "account_field": False, "order_ref": False, "account_updates": False},
    "T3": {"order_id_scheme": "client-partitioned ids from 1", "client_ids": "fresh", "hold_s": "1.5 first / 3.0 second", "poll_all_open_orders": "none", "account_field": True, "order_ref": True, "account_updates": False},
    "T4": {"order_id_scheme": "client-partitioned ids from 1", "client_ids": "fresh", "hold_s": "1.5 first / 3.0 second", "poll_all_open_orders": "reqAllOpenOrders every 1 s on both", "account_field": True, "order_ref": True, "account_updates": "snapshot every 2 s on both, plus the adapter's connect-time requests"},
    "T6": {"order_id_scheme": "client-partitioned ids from 1", "client_ids": "fresh", "hold_s": "1.5 first / 3.0 second", "poll_all_open_orders": "none", "account_field": True, "order_ref": True, "account_updates": "snapshot every 2 s on both"},
    "T7": {"order_id_scheme": "client-partitioned ids from 1", "client_ids": "fresh", "hold_s": "1.5 first / 3.0 second", "poll_all_open_orders": "reqAllOpenOrders every 1 s on both", "account_field": True, "order_ref": True, "account_updates": False},
    "T8": {"order_id_scheme": "client-partitioned ids from 1", "client_ids": "fresh", "hold_s": "1.5 first / 3.0 second", "poll_all_open_orders": "reqOpenOrders (this client only) every 1 s on both", "account_field": True, "order_ref": True, "account_updates": False},
    "T9a": {"order_id_scheme": "client-partitioned ids from 1", "client_ids": "fresh", "hold_s": "1.5 first / 3.0 second", "poll_all_open_orders": "reqAllOpenOrders every 1 s on the first (lower-id) connection only", "account_field": True, "order_ref": True, "account_updates": False},
    "T9b": {"order_id_scheme": "client-partitioned ids from 1", "client_ids": "fresh", "hold_s": "1.5 first / 3.0 second", "poll_all_open_orders": "reqAllOpenOrders every 1 s on the second (higher-id) connection only", "account_field": True, "order_ref": True, "account_updates": False},
    "T10": {"order_id_scheme": "client-partitioned ids from 1", "client_ids": "fresh", "hold_s": "1.5 first / 3.0 second", "poll_all_open_orders": "reqAllOpenOrders every 1 s on the first (lower-id) connection only; it re-seeds from reqIds after each [103]", "account_field": True, "order_ref": True, "account_updates": False},
}

# journal cancel reasons; only a cancel of an order not yet accepted carries no PERM venue id (checked against the vendor log per run)
NO_VENUE_ID_REASONS = ("unaccepted_after_1s",)
VENDOR_COUNT_PATTERNS = {
    "notice_103_duplicate_order_id": re.compile(r"\[103\]"),
    "notice_10147_cancel_not_found": re.compile(r"\[10147\]"),
    "notice_2100_account_data_unsubscribed": re.compile(r"\[2100\]"),
    "code_100_lines": re.compile(r"\[100\]"),
    "pacing_text_lines": re.compile(r"pacing", re.I),
}


def load_json(path):
    return json.loads(Path(path).read_text())


def ts(value):
    return datetime.fromisoformat(value).timestamp()


def pct(values, q):
    """Nearest rank (ceil), identical to the ladder report used for the first measurements."""
    if not values:
        return None
    values = sorted(values)
    return values[min(len(values) - 1, max(0, -(-int(q * 100) * len(values) // 100) - 1))]


def r3(value):
    return None if value is None else round(value, 3)


def lat(values):
    return {"n": len(values), "p50_ms": r3(pct(values, 0.5)), "p90_ms": r3(pct(values, 0.9)), "max_ms": r3(pct(values, 1.0))}


def journal(run_dir):
    return [json.loads(line) for line in (run_dir / "journal.jsonl").read_text().splitlines()]


CANCEL_WITH_PERM = re.compile(r'\[CMD\]--> CancelOrder\(.*venue_order_id=Some\("PERM-[0-9]+"\)')
CANCEL_WITHOUT_ID = re.compile(r"\[CMD\]--> CancelOrder\(.*venue_order_id=None")


def vendor_counts(run_dir):
    counts = Counter()
    first = {}
    for line in (run_dir / "vendor.log").read_text(errors="replace").splitlines():
        if "CancelOrder(" in line:
            if CANCEL_WITH_PERM.search(line):
                counts["cancel_commands_with_perm_venue_id"] += 1
            elif CANCEL_WITHOUT_ID.search(line):
                counts["cancel_commands_without_venue_id"] += 1
        for name, pattern in VENDOR_COUNT_PATTERNS.items():
            if pattern.search(line):
                counts[name] += 1
                if name == "notice_103_duplicate_order_id" and name not in first:
                    try:
                        first[name] = ts(line[:26].replace("Z", "") + "+00:00")
                    except ValueError:
                        pass
    names = list(VENDOR_COUNT_PATTERNS) + ["cancel_commands_with_perm_venue_id", "cancel_commands_without_venue_id"]
    return {name: counts.get(name, 0) for name in names}, first.get("notice_103_duplicate_order_id")


def per_second_wire(rows):
    """Counted = placeOrder + cancelOrder; wire(refined) = counted + one reqAllOpenOrders per cancel issued with a PERM venue id;
    wire(upper bound) = counted + one per cancel."""
    counted, refined, upper = Counter(), Counter(), Counter()
    for row in rows:
        second = int(ts(row["utc"]))
        if row["event"] == "submit":
            counted[second] += 1
            refined[second] += 1
            upper[second] += 1
        elif row["event"] == "cancel":
            counted[second] += 1
            upper[second] += 2
            refined[second] += 1 if row.get("reason") in NO_VENUE_ID_REASONS else 2
    return counted, refined, upper


def window_stats(per_second, width=5):
    seconds = sorted(per_second)
    if not seconds:
        return {"max_1s": 0, "best_5s_mean": 0.0}
    best = max(sum(per_second.get(start + k, 0) for k in range(width)) / width for start in seconds)
    return {"max_1s": max(per_second.values()), "best_5s_mean": round(best, 2)}


def rate_block(rows):
    counted, refined, upper = per_second_wire(rows)
    return {"counted_msgs_per_s": window_stats(counted), "wire_est_refined_msgs_per_s": window_stats(refined), "wire_est_upper_bound_msgs_per_s": window_stats(upper)}


def ladder_rungs(receipt, rows):
    ladder = receipt.get("ladder") or {}
    submit, accepted, cancel, canceled, rung_of, cancel_reason = {}, {}, {}, {}, {}, {}
    for row in rows:
        coid = row.get("coid")
        if row["event"] == "submit" and row.get("step") == "S4":
            submit[coid], rung_of[coid] = ts(row["utc"]), row.get("rung")
        elif row["event"] == "order_accepted" and coid in submit:
            accepted[coid] = ts(row["utc"])
        elif row["event"] == "cancel" and coid in submit:
            if coid not in cancel:
                cancel[coid] = ts(row["utc"])
                cancel_reason[coid] = row.get("reason")
        elif row["event"] == "order_canceled" and coid in submit:
            canceled[coid] = ts(row["utc"])
    events = sorted([(submit[c], 1, rung_of[c]) for c in submit] + [(canceled[c], -1, rung_of[c]) for c in canceled if c in submit])
    live, peak = 0, {}
    for _, delta, rung in events:
        live += delta
        peak[rung] = max(peak.get(rung, 0), live)
    out = []
    for rung in ladder.get("rungs", []):
        per = rung["per_second_msgs"]
        if not rung.get("submits"):
            continue
        target = rung["target_msgs_per_s"]
        ids = [c for c, v in rung_of.items() if v == target]
        acc = [(accepted[c] - submit[c]) * 1000 for c in ids if c in accepted]
        can = [(canceled[c] - cancel[c]) * 1000 for c in ids if c in canceled and c in cancel]
        seconds = len(per)
        cancels = sum(1 for c in ids if c in cancel)
        known = sum(1 for c in ids if c in cancel and cancel_reason.get(c) not in NO_VENUE_ID_REASONS)
        out.append({
            "target_msgs_per_s": target,
            "seconds": seconds,
            "orders": rung["submits"],
            "skipped_slots": rung["skipped_slots"],
            "counted_msgs_per_s_mean": rung["mean_msgs_per_s"],
            "counted_msgs_per_s_min": min(per) if per else None,
            "counted_msgs_per_s_max": max(per) if per else None,
            "orders_per_min_by_submits": round(rung["submits"] / seconds * 60) if seconds else None,
            "orders_per_min_by_counted_rate": round(rung["mean_msgs_per_s"] / 2 * 60),
            "cancels_sent": cancels,
            "cancels_with_known_venue_id": known,
            "cancels_before_acceptance": cancels - known,
            "wire_est_refined_msgs_per_s_mean": round((rung["submits"] + cancels + known) / seconds, 2) if seconds else None,
            "wire_est_upper_bound_msgs_per_s_mean": round((rung["submits"] + 2 * cancels) / seconds, 2) if seconds else None,
            "accept_ms": lat(acc),
            "cancel_ms": lat(can),
            "peak_open_orders": peak.get(target),
        })
    return out


def adapter_run(root, label):
    run_dir = root / "runs" / label
    receipt = load_json(run_dir / "receipt.json")
    rows = journal(run_dir)
    notices, first_103 = vendor_counts(run_dir)
    frozen = receipt.get("frozen", {})
    s4 = frozen.get("s4", {})
    steps = {name: {k: v for k, v in step.items() if k in ("result", "seconds", "reason", "accept_ms")} for name, step in receipt.get("steps", {}).items()}
    ids = receipt.get("client_ids", {})
    out = {
        "label": label,
        "kind": "adapter",
        "phase": receipt.get("phase"),
        "api_connections_of_the_node": len([k for k in ids if k.endswith("client_id")]),
        "order_writing_connections": 1,
        "orders_this_phase": receipt.get("orders_this_phase"),
        "event_counts": receipt.get("event_counts"),
        "abort_reason": receipt.get("abort_reason"),
        "node_error_class": receipt.get("node_error"),
        "final_open_orders": receipt.get("final_open_orders"),
        "final_net_position": receipt.get("final_net_position"),
        "fills_with_commission": receipt.get("fills_with_commission"),
        "pacing_error_count": receipt.get("pacing_error_count"),
        "steps": steps,
        "vendor_log_line_counts": notices,
        "rate_estimates_whole_run": rate_block(rows),
        "journal_submit_events": sum(1 for r in rows if r["event"] == "submit"),
        "journal_cancel_events": sum(1 for r in rows if r["event"] == "cancel"),
    }
    if receipt.get("phase") in ("B", "L") and receipt.get("ladder"):
        out["window_pairs_max"] = s4.get("inflight_pairs_max")
        out["rungs"] = ladder_rungs(receipt, rows)
        ladder = receipt["ladder"]
        out["accept_latency_all_ms"] = {k: ladder["accept_latency"][k] for k in ("n", "p50_ms", "p95_ms", "max_ms")}
        out["cancel_latency_all_ms"] = {k: ladder["cancel_latency"][k] for k in ("n", "p50_ms", "p95_ms", "max_ms")}
        out["unaccepted_cancels"] = ladder.get("unaccepted_cancels")
    return out


def first_rejection(rows):
    """1-based index, among the run's ladder submits in submission order, of the first order the venue refused; None if none."""
    submits = [r["coid"] for r in rows if r["event"] == "submit"]
    rejected = {r["coid"] for r in rows if r["event"] == "order_rejected"}
    for index, coid in enumerate(submits, 1):
        if coid in rejected:
            return index
    return None


def concurrency_pairs(root):
    """Two order-writing connections on one account; L0 uses the lower client-id partition, L1 the higher one."""
    pairs = []
    for m in ADAPTER_L_PAIRS:
        entry = {"label": m, "order_writing_connections": 2, "connections": {}}
        merged = []
        starts = {}
        for conn, name in (("lower_partition", f"L0-{m}"), ("higher_partition", f"L1-{m}")):
            run = adapter_run(root, name)
            rows = journal(root / "runs" / name)
            merged.extend(rows)
            submits = [ts(r["utc"]) for r in rows if r["event"] == "submit"]
            starts[conn] = min(submits) if submits else None
            run["first_refused_order_index"] = first_rejection(rows)
            rejections = [ts(r["utc"]) for r in rows if r["event"] == "order_rejected"]
            run["_first_rejection_t"] = min(rejections) if rejections else None
            run["_first_103_notice_t"] = vendor_counts(root / "runs" / name)[1]
            entry["connections"][conn] = run
        lower = entry["connections"]["lower_partition"]
        other_start = starts["higher_partition"]
        entry["lower_first_submit_minus_higher_first_submit_s"] = (
            round(starts["lower_partition"] - other_start, 2) if starts["lower_partition"] and other_start else None)
        entry["lower_connection_first_rejection_after_higher_first_submit_s"] = (
            round(lower["_first_rejection_t"] - other_start, 2) if lower["_first_rejection_t"] and other_start else None)
        entry["lower_connection_first_103_notice_after_higher_first_submit_s"] = (
            round(lower["_first_103_notice_t"] - other_start, 2) if lower["_first_103_notice_t"] and other_start else None)
        for run in entry["connections"].values():
            run.pop("_first_rejection_t", None)
            run.pop("_first_103_notice_t", None)
        entry["combined_rate_estimates"] = rate_block(merged)
        pairs.append(entry)
    return pairs


def official_ladder(root, label="P-r1"):
    r = load_json(root / "runs" / label / "receipt.json")
    return {
        "label": label,
        "kind": "official_client",
        "client": r["client"],
        "server_version": r["server_version"],
        "connections": 1,
        "window": r["window"],
        "orders_placed": r["orders_placed"],
        "accepted": r["accepted"],
        "cancel_confirmed": r["cancel_confirmed"],
        "open_at_end": r["final_open_orders_by_status_callbacks"],
        "stop_reason": r["stop_reason"],
        "error_code_counts": r["error_code_counts"],
        "non_info_error_texts": len(r["non_info_error_texts"]),
        "elapsed_s": r["elapsed_s"],
        "rungs": [{
            "target_msgs_per_s": x["target_msgs_per_s"],
            "seconds": x["seconds"],
            "orders": x["placed"],
            "skipped_slots": x["skipped_slots"],
            "counted_msgs_per_s_mean": x["msgs_per_s_mean"],
            "counted_msgs_per_s_min": x["msgs_per_s_min"],
            "counted_msgs_per_s_max": x["msgs_per_s_max"],
            "orders_per_min_with_cancel": x["orders_per_min_with_cancel"],
            "wire_msgs_per_s_mean_equals_counted": True,
            "accept_ms_p50_p90_max": x["accept_ms_p50_p90_max"],
            "cancel_ms_p50_p90_max": x["cancel_ms_p50_p90_max"],
            "peak_open_orders": x["peak_open"],
        } for x in r["rungs"]],
    }


def smoke(root):
    r = load_json(root / "runs" / "P-t1" / "receipt.json")
    x = r["rungs"][0]
    return {
        "label": "SMOKE", "receipt_label": "P-t1", "kind": "official_client", "connections": 1, "orders_placed": r["orders_placed"], "accepted": r["accepted"],
        "cancel_confirmed": r["cancel_confirmed"], "error_code_counts": r["error_code_counts"],
        "rung": {"target_msgs_per_s": x["target_msgs_per_s"], "seconds": x["seconds"], "counted_msgs_per_s_mean": x["msgs_per_s_mean"],
                 "accept_ms_p50_p90_max": x["accept_ms_p50_p90_max"], "cancel_ms_p50_p90_max": x["cancel_ms_p50_p90_max"]},
        "order_id_tests": [{"which": t["which"], "accepted": t["accepted"], "new_error_codes": t["new_error_codes"]} for t in r["id_tests"]],
    }


def side(r):
    x = r["rungs"][0]
    refused = r.get("refused_103") or {"count": 0, "first_id": None}
    codes = r["error_code_counts"]
    first_index = None
    if refused.get("first_id") is not None:
        first_index = refused["first_id"] - r["id_base"] + 1
    return {
        "orders_placed": r["orders_placed"],
        "accepted": r["accepted"],
        "cancel_confirmed": r["cancel_confirmed"],
        "cancelled_by_venue_202": codes.get("202", 0),
        "closed_as_not_found_10147": codes.get("10147", 0),
        "refused_103": refused.get("count", codes.get("103", 0)),
        "first_refused_order_index": first_index,
        "cancel_not_found_10147": codes.get("10147", 0),
        "stop_reason": r["stop_reason"],
        "error_code_counts": codes,
        "elapsed_s": r["elapsed_s"],
        "counted_msgs_per_s_mean": x["msgs_per_s_mean"],
        "accept_ms_p50_p90_max": x["accept_ms_p50_p90_max"],
        "cancel_ms_p50_p90_max": x["cancel_ms_p50_p90_max"],
        "peak_open_orders": x["peak_open"],
        "hold_s_recorded": r.get("hold_s"),
        "account_field_recorded": r.get("account_field_set"),
        "order_ref_recorded": r.get("order_ref_set"),
    }


def pair_tests(root):
    out = []
    for test in PAIR_TESTS:
        folder = test.lower() if test not in ("E1", "E2") else test.lower()
        ra = load_json(root / "runs" / f"P-{folder}-a" / "receipt.json")
        rb = load_json(root / "runs" / f"P-{folder}-b" / "receipt.json")
        entry = {"test": test, "receipt_labels": [f"P-{folder}-a", f"P-{folder}-b"], "kind": "official_client", "connections": 2,
                 "design_declared_by_runner": DESIGN[test], "first_connection": side(ra), "second_connection": side(rb)}
        entry["first_connection_order_ids_relative_to_second"] = (
            "lower" if ra["id_base"] < rb["id_base"] else "equal" if ra["id_base"] == rb["id_base"] else "higher")
        entry["connection_stop_rule"] = "a probe stops after 25 [103] refusals (in-flight orders can add one or two)"
        if ra.get("first_103_utc") and rb.get("first_order_utc"):
            entry["first_connection_first_103_after_second_connection_first_order_s"] = round(ts(ra["first_103_utc"]) - ts(rb["first_order_utc"]), 2)
        if ra.get("reseeds"):
            entry["note"] = ("after the first re-seed the first connection's order ids fall inside the second connection's id range; status callbacks of the "
                             "second connection's same-numbered orders, delivered by the open-order poll, are attributed to the first connection, so its "
                             "accepted and cancel_confirmed over-count; the refusal count and the cancelled_by_venue_202 count are not affected")
            entry["reseeds"] = {
                "count": len(ra["reseeds"]),
                "first_reseed_returned_id_minus_other_connection_first_order_id": ra["reseeds"][0]["returned_next_valid"] - rb["id_base"],
                "reseeds_returning_an_id_above_own_next_id": sum(1 for x in ra["reseeds"] if x["returned_is_above_own"]),
            }
        out.append(entry)
    return out


def summary_groups(pairs):
    by = {p["test"]: p for p in pairs}

    def total(tests, which):
        return {"tests": tests, "orders": sum(by[t][w]["orders_placed"] for t in tests for w in which),
                "refusals_103": sum(by[t][w]["refused_103"] for t in tests for w in which)}

    both = ("first_connection", "second_connection")
    return {
        "no_open_order_polling_by_either_connection": total(["E1", "E2", "T1b", "T2", "T3", "T6"], both),
        "reqAllOpenOrders_polled_by_both_or_by_the_lower_id_connection": {
            "tests": ["T4", "T7", "T9a", "T10"],
            "lower_id_connection": total(["T4", "T7", "T9a", "T10"], ("first_connection",)),
            "higher_id_connection": total(["T4", "T7", "T9a", "T10"], ("second_connection",)),
        },
        "reqAllOpenOrders_polled_only_by_the_higher_id_connection": total(["T9b"], both),
        "client_scoped_reqOpenOrders_polled_by_both": total(["T8"], both),
        "reused_client_ids_with_order_ids_below_their_earlier_ids": total(["T1"], both),
    }


def marker_summary(root):
    files = sorted((root / "runs").glob("marker-*.json"))
    docs = [load_json(f) for f in files]
    keys = ("all_match_DU", "exactly_one_account", "paper_marker_present", "port_is_4002", "connected")
    return {
        "marker_checks": len(docs),
        "all_exactly_one_managed_account": all(d.get("exactly_one_account") for d in docs),
        "all_paper_shaped_code": all(d.get("all_match_DU") and d.get("paper_marker_present") for d in docs),
        "all_port_is_paper_gateway_4002": all(d.get("port_is_4002") for d in docs),
        "all_connected": all(d.get("connected") for d in docs),
        "server_versions": sorted({d.get("server_version") for d in docs}),
        "booleans_checked": list(keys),
    }


def reconciliation(root, adapter_runs):
    totals = Counter()
    by_run = {}
    for run in adapter_runs:
        by_run[run["label"]] = run["journal_submit_events"]
        totals["journal_submits"] += run["journal_submit_events"]
    missing_text = (root / "journal-submitted-ids.txt.missing").read_text().split()
    missing = set(missing_text)
    kinds = Counter()
    for run in adapter_runs:
        events, reasons = {}, {}
        for row in journal(root / "runs" / run["label"]):
            if row.get("coid") in missing:
                events.setdefault(row["coid"], set()).add(row["event"])
                if row["event"] == "order_rejected":
                    reasons[row["coid"]] = str(row.get("reason", ""))
        for coid, names in events.items():
            if "order_rejected" in names:
                text = reasons.get(coid, "")
                if text.startswith("Duplicate order id"):
                    kinds["refused_by_the_venue_notice_103"] += 1
                elif "that needs to be cancelled is not found" in text:
                    kinds["rejected_cancel_target_not_found_10147"] += 1
                else:
                    kinds["rejected_other"] += 1
            elif "order_submitted" not in names:
                kinds["journalled_but_never_reached_the_adapter"] += 1
            else:
                kinds["submitted_without_a_venue_answer"] += 1
    official_orders = sum(load_json(root / "runs" / name / "receipt.json")["orders_placed"]
                          for name in ("P-t1", "P-e1-a", "P-e1-b", "P-e2-a", "P-e2-b", "P-r1"))
    diag_orders = sum(load_json(root / "runs" / f"P-{t.lower()}-{s}" / "receipt.json")["orders_placed"]
                      for t in PAIR_TESTS if t not in ("E1", "E2") for s in ("a", "b"))
    diag_refused = sum(load_json(root / "runs" / f"P-{t.lower()}-{s}" / "receipt.json")["refused_103"]["count"]
                       for t in PAIR_TESTS if t not in ("E1", "E2") for s in ("a", "b"))
    third = TRANSCRIPT_DERIVED["broker_completed_orders_after_pair_tests"]
    second = TRANSCRIPT_DERIVED["broker_completed_orders_after_official_client_runs"]
    broker_harness = TRANSCRIPT_DERIVED["broker_completed_orders_after_harness_runs"]
    return {
        "journal_submit_events_total": totals["journal_submits"],
        "journal_submit_events_by_run": by_run,
        "journal_orders_missing_at_broker": len(missing),
        "journal_orders_missing_by_kind": dict(sorted(kinds.items())),
        "journal_orders_found_at_broker_by_arithmetic": totals["journal_submits"] - len(missing),
        "broker_completed_orders_after_harness_runs": {"value": broker_harness, "source": "transcript-derived (raw-protocol reqCompletedOrders read; no receipt file)",
                                                    "equals_journal_minus_missing": broker_harness == totals["journal_submits"] - len(missing)},
        "official_client_orders_placed_before_second_count": official_orders,
        "broker_completed_orders_after_official_client_runs": {"value": TRANSCRIPT_DERIVED["broker_completed_orders_after_official_client_runs"],
                                                               "source": "transcript-derived (raw-protocol reqCompletedOrders read; no receipt file)",
                                                               "equals_first_count_plus_official_orders": TRANSCRIPT_DERIVED["broker_completed_orders_after_official_client_runs"] == broker_harness + official_orders},
        "diagnostic_pair_test_orders_placed_after_second_count": diag_orders,
        "diagnostic_pair_test_orders_refused_103": diag_refused,
        "diagnostic_pair_test_orders_expected_listed_as_completed": diag_orders - diag_refused,
        "broker_completed_orders_after_pair_tests": {"value": third, "source": "transcript-derived (raw-protocol reqCompletedOrders read; no receipt file)",
                                                     "equals_second_count_plus_listed_pair_orders_plus_probe_order": third == second + (diag_orders - diag_refused) + 1},
        "reqids_probe_orders_placed_after_second_count": {"value": 1, "source": "transcript-derived (one order, cancelled and confirmed)"},
    }


def input_inventory(root):
    """Run labels whose receipts were read (names only; sizes and digests of the private files are not published)."""
    return sorted(path.parent.name for path in (root / "runs").glob("*/receipt.json"))


def rung(run, target):
    for item in run["rungs"]:
        if item["target_msgs_per_s"] == target:
            return item
    raise KeyError(target)


def headline(adapter_b, official, pairs, recon, conc):
    r6 = next(r for r in adapter_b if r["label"] == "B-r6")
    o50 = next(x for x in official["rungs"] if x["target_msgs_per_s"] == 50)
    out = [
        {"id": "official_rung50_counted_msgs_per_s_mean", "value": o50["counted_msgs_per_s_mean"], "unit": "msgs/s", "source": "P-r1"},
        {"id": "official_rung50_orders_in_rung", "value": o50["orders"], "unit": "orders", "source": "P-r1"},
        {"id": "official_rung50_seconds", "value": o50["seconds"], "unit": "s", "source": "P-r1"},
        {"id": "official_rung50_orders_per_min_with_cancel", "value": o50["orders_per_min_with_cancel"], "unit": "orders/min", "source": "P-r1"},
        {"id": "official_rung50_msgs_per_min", "value": round(o50["counted_msgs_per_s_mean"] * 60), "unit": "msgs/min", "source": "P-r1 (mean x 60)"},
        {"id": "official_ladder_orders_accepted_cancelled_open_at_end", "value": [official["orders_placed"], official["accepted"], official["cancel_confirmed"], official["open_at_end"]], "unit": "count", "source": "P-r1"},
    ]
    for target in (30, 40, 50):
        x = rung(r6, target)
        out.append({"id": f"adapter_r6_rung{target}", "value": {
            "counted_msgs_per_s_mean": x["counted_msgs_per_s_mean"], "orders_per_min_by_submits": x["orders_per_min_by_submits"],
            "orders_per_min_by_counted_rate": x["orders_per_min_by_counted_rate"], "wire_est_refined_msgs_per_s_mean": x["wire_est_refined_msgs_per_s_mean"],
            "wire_est_upper_bound_msgs_per_s_mean": x["wire_est_upper_bound_msgs_per_s_mean"], "counted_times_1_5": round(x["counted_msgs_per_s_mean"] * 1.5, 2)},
            "unit": "mixed", "source": "B-r6 receipt + journal"})
    out.append({"id": "adapter_whole_run_rate_estimates", "value": {
        run["label"]: {"counted": run["rate_estimates_whole_run"]["counted_msgs_per_s"],
                       "wire_refined": run["rate_estimates_whole_run"]["wire_est_refined_msgs_per_s"],
                       "wire_upper_bound": run["rate_estimates_whole_run"]["wire_est_upper_bound_msgs_per_s"]}
        for run in adapter_b if run["label"] in ("B-r5", "B-r6")}, "unit": "msgs/s (max over any 1 s, best 5 s mean)", "source": "B-r5, B-r6 journals"})
    out.append({"id": "adapter_two_connection_combined_rate_estimates", "value": {
        pair["label"]: {"counted": pair["combined_rate_estimates"]["counted_msgs_per_s"],
                        "wire_refined": pair["combined_rate_estimates"]["wire_est_refined_msgs_per_s"],
                        "wire_upper_bound": pair["combined_rate_estimates"]["wire_est_upper_bound_msgs_per_s"]} for pair in conc},
        "unit": "msgs/s (max over any 1 s, best 5 s mean)", "source": "L0 + L1 journals"})
    out.append({"id": "pair_tests_table", "value": [[p["test"], p["first_connection"]["orders_placed"], p["first_connection"]["refused_103"], p["second_connection"]["orders_placed"], p["second_connection"]["refused_103"]] for p in pairs],
                "unit": "test, first orders, first refusals, second orders, second refusals", "source": "P-* receipts"})
    out.append({"id": "reconciliation", "value": [recon["journal_submit_events_total"], recon["journal_orders_missing_at_broker"], recon["journal_orders_found_at_broker_by_arithmetic"],
                                                 recon["official_client_orders_placed_before_second_count"], recon["broker_completed_orders_after_official_client_runs"]["value"]],
                "unit": "journal submits, missing at broker, found, official-client orders, broker count after", "source": "journals + transcript-derived broker counts"})
    return out


def main(argv):
    if len(argv) != 2:
        sys.stderr.write(__doc__)
        return 2
    root = Path(argv[1])
    adapter_a = [adapter_run(root, label) for label in ADAPTER_A_RUNS]
    adapter_b = [adapter_run(root, label) for label in ADAPTER_B_RUNS]
    conc = concurrency_pairs(root)
    l_runs = [run for pair in conc for run in pair["connections"].values()]
    official = official_ladder(root)
    pairs = pair_tests(root)
    recon = reconciliation(root, adapter_a + adapter_b + l_runs)
    no_poll = [p for p in pairs if p["design_declared_by_runner"]["poll_all_open_orders"] == "none" and p["test"] != "T1"]
    doc = {
        "schema": SCHEMA,
        "measured_on": "2026-10-13",
        "scope": "IBKR paper Gateway, one account; 1-share SPY BUY limit orders far below the bid, placed and cancelled: the ladders and pair tests filled nothing; the phase A step S2 is a one-share filled round trip (flat afterwards)",
        "facts": {
            "nautilus_trader_pin": "01ced2a3e7b7d25ae7b2e5c0c077bcc46192eb25",
            "nautilus_trader_pin_description": "develop 2.0.0rc7.dev20261012, CPython 3.13",
            "develop_head_compared": "ca478e42f434d2ce185493f2bb42d112a88d1ffe",
            "develop_commits_ahead_of_pin": 26,
            "ib_adapter_changes_between_pin_and_head": ["#5274 Fix Interactive Brokers order denial and position reports (3e49ffe2)",
                                                         "#5306 Fail IB order ID start above client partition (ddeba535)"],
            "upstream_issue_cited_nothing_filed": "nautechsystems/nautilus_trader#5277",
            "ib_api_server_version": 225,
            "official_client": "IB Python client 10.46.01 as vendored by the nautilus_ibapi mirror, one connection per probe",
            "paper_marker": marker_summary(root),
            "message_counting": {
                "counted": "placeOrder + cancelOrder (what the harness receipts report)",
                "wire_estimate_refined": "counted + one reqAllOpenOrders per cancel of an order that was already accepted (its cancel carries a PERM venue id; journal reasons other than unaccepted_after_1s)",
                "wire_estimate_upper_bound": "counted + one reqAllOpenOrders per cancel",
                "basis": "SOURCE-derived from the adapter's cancel path at the pin and cross-checked against the vendor logs' cancel commands; not captured on the wire",
                "official_client_probe": "placeOrder + cancelOrder only (no per-cancel request): its wire rate equals its counted rate",
            },
            "source_citations_at_the_pin": {
                "repository": "nautechsystems/nautilus_trader",
                "commit": "01ced2a3e7b7d25ae7b2e5c0c077bcc46192eb25",
                "file": "crates/adapters/interactive_brokers/src/execution/core.rs",
                "blob_url_form": "https://github.com/nautechsystems/nautilus_trader/blob/01ced2a3e7b7d25ae7b2e5c0c077bcc46192eb25/crates/adapters/interactive_brokers/src/execution/core.rs#L<line>",
                "symbols": [
                    {"symbol": "IbOrderSelector::from_venue_order_id", "definition_line": 381,
                     "what": "a venue id with the PERM- prefix becomes a PermId selector (a numeric id becomes an OrderId selector)"},
                    {"symbol": "handle_cancel_order_async", "definition_line": 2387, "selector_built_at_line": 2417, "resolve_call_line": 2429,
                     "what": "builds the selector from the cancel command's venue_order_id, or from the order id map when the command has none, and calls resolve_ib_order_id"},
                    {"symbol": "resolve_ib_order_id", "definition_line": 2624, "all_open_orders_call_line": 2637,
                     "what": "an OrderId selector returns at once; a PermId selector is resolved with client.all_open_orders(), one reqAllOpenOrders per cancel of an accepted order"},
                ],
                "same_symbols_at_develop_head_ca478e42f434d2ce185493f2bb42d112a88d1ffe": [
                    {"symbol": "IbOrderSelector::from_venue_order_id", "definition_line": 382},
                    {"symbol": "handle_cancel_order_async", "definition_line": 2409, "selector_built_at_line": 2439},
                    {"symbol": "resolve_ib_order_id", "definition_line": 2646, "all_open_orders_call_line": 2659},
                ],
                "open_order_requests_in_the_adapter_sources": {
                    "scope": "the 54 .rs files under crates/adapters/interactive_brokers/src/, string occurrences, identical at the pin and at the develop head",
                    "all_open_orders_calls": {"total": 11, "by_file": {"execution/core.rs": 5, "execution/reports.rs": 2, "execution/commands.rs": 1,
                                                                        "execution/incarnations.rs": 1, "execution/order_state.rs": 1, "execution/updates.rs": 1}},
                    "client_scoped_open_orders_calls": 0,
                },
            },
        },
        "inputs": {"receipt_run_labels": input_inventory(root), "marker_checks": marker_summary(root)["marker_checks"],
                   "note": "private; the run root is not published; names are run labels"},
        "headline_numbers": headline(adapter_b, official, pairs, recon, conc),
        "adapter_phase_a": adapter_a,
        "adapter_single_connection_ladders": adapter_b,
        "adapter_two_connection_pairs": conc,
        "official_client_ladder": official,
        "official_client_smoke": smoke(root),
        "official_client_two_connection_tests": pairs,
        "official_client_summary": summary_groups(pairs),
        "reqids_probe": {"source": "transcript-derived (probe output printed in the session; no receipt file)", **TRANSCRIPT_DERIVED["reqids_probe"]},
        "reconciliation": recon,
        "revision": {"number": 2, "supersedes": {"json_sha256": "b492f42d335370e22f4349bf43db54f1adf4c77921b36a28300159b08c8e11fa", "generator_sha256": "56463b2622501446a9a1640c6d3065920dbd449a622457ea61f392ce6166c5a1", "verifier_sha256": "0e9fb1376a59e34cf1e3b6ba2fea30d89aad5e09db28de0b4d59792a41207468"},
                     "changes": ["journal_orders_missing_by_kind: 36 rejected orders split into 35 [103] duplicate-order-id refusals and 1 cancel-target-not-found rejection (v1 labelled 36 as [103])",
                                 "reconciliation: third transcript-derived broker count (10,313) with its arithmetic relation; the pair-test order key is renamed",
                                 "caveats updated accordingly; every measured rate, latency and test count is unchanged"]},
        "caveats": [
            "The 1,500 orders a minute with cancels at 50 msgs/s was measured over one 20-second rung, not a full minute.",
            "The third wire message per order (one reqAllOpenOrders per cancel) is derived from the adapter source at the pin; it was not captured on the wire.",
            "The official client was not tested above 50 msgs/s (cap); whether the Gateway saturates between 50 and 57 is unmeasured.",
            "Adapter rungs whose wire estimate exceeded 50 msgs/s ran above the cap in wire terms; no pacing text, no code 100 and no disconnect occurred.",
            "The counted rate excludes the hidden request; the wire estimate is the cap-relevant figure.",
            "Broker-side completed-order counts (6,292 and 8,494) are live raw-protocol reads recorded in the session transcript, not receipt files.",
            "A first count attempt through a Nautilus node returned zero orders and is not used as evidence.",
            "The pair tests T1..T10 and the reqIds probe were placed after the second independent count; a third raw-protocol count (10,313) is transcript-derived and reconciles by arithmetic (ADDENDUM-01).",
            "Of the 38 journal orders absent at the broker, 35 carry the venue's [103] duplicate-order-id refusal, 1 a cancel-target-not-found rejection and 2 never reached the adapter (revision 2 corrects the v1 label of 36 as [103]).",
            "Latencies of the pair tests are single 14-30 second runs at 10 msgs/s per connection and are not a latency study.",
            "Timing offsets compare two timestamps taken on one host clock.",
        ],
    }
    json.dump(doc, sys.stdout, sort_keys=True, indent=1, ensure_ascii=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
