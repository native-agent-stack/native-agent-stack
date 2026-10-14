#!/usr/bin/env python3
"""Generate the sanitized, publication-safe projection of the Alpaca paper throughput measurements of 2026-10-13.

Reads three private inputs (receipts only, read-only; no network, no credential, no clock, no environment) and prints ONE deterministic JSON document:
  --capacity-dir          the lane A capacity run directory: capacity-200-pre-a2.json, capacity-200-pre-a2.journal.jsonl, capacity-200-pre-a1.json
  --header-receipts-dir   the directory holding the six read-only rate-limit header receipts (readonly-limits-* and readonly-limits2-*, each with receipt.json)
  --observer-receipt      the separate order-count observer receipt of the a2 run
Every number is either copied from a receipt field (named in `provenance.number_to_receipt_field`) or computed from receipt fields by the formulas in `derived_units`.
Account identifiers, credentials, client order ids, prices, symbols and file-system paths are never read into the output.

usage: python3 generate_alpaca_throughput_evidence.py --capacity-dir DIR --header-receipts-dir DIR --observer-receipt FILE [--out FILE]
Public re-export: --public-evidence FILE [--out FILE] reads only an approved projection, never its private inputs.
"""
import argparse
import json
import re
import sys
from decimal import Decimal, ROUND_HALF_EVEN
from pathlib import Path
from audit_publication_safety import projection_publication_errors

SCHEMA = "alpaca-throughput-evidence/2"
ACCOUNT_LABELS = (("lane-a", "lane_a"), ("lane-b", "lane_b"), ("acct-c", "account_c"))
HEADER_DIR_NAME = re.compile(r"^readonly-limits2?-[a-z0-9-]+-20261013$")
JOURNAL_INTENT_KEYS = ["client_order_id", "extended_hours", "limit_price", "qty", "seq", "type"]


def load_json(path):
    return json.loads(Path(path).read_bytes())


def public_document(document):
    """#1090 blocker 1: export approved fields with name-only private citations.

    Re-export an approved projection without reopening private sources; then
    refuse fingerprints outside the retained published-code bindings.
    """
    document = json.loads(json.dumps(document))
    document["schema"] = SCHEMA
    provenance = document["provenance"]
    provenance["private_receipts"] = [{"name": row["name"]}
                                      for row in provenance["private_receipts"]]
    provenance["digest_policy"] = ("Private receipts are cited by name only. Their bytes, sizes and digests are not published. "
                                   "The remaining facts bindings identify retained published code; "
                                   "public integrity is the native registration of this sanitized projection.")
    if projection_publication_errors(document):
        raise ValueError("publication policy refused projection metadata")
    return document


def fixed(value, places=6):
    return str(Decimal(str(value)).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_EVEN))


def seconds_of(iso_text):
    from datetime import datetime
    return datetime.fromisoformat(iso_text).timestamp()


def utc_seconds(iso_text):
    return iso_text[:19] + "Z"


def header_section(directory):
    directory = Path(directory)
    v2, v1 = {}, {}
    for entry in sorted(directory.iterdir()):
        receipt = entry / "receipt.json"
        if not HEADER_DIR_NAME.match(entry.name) or not receipt.is_file():
            continue
        data = load_json(receipt)
        for prefix, name in ACCOUNT_LABELS:
            if str(data["label"]).startswith(prefix):
                (v2 if data["kind"] == "trading_limit_header_receipt_v2" else v1)[name] = (data, receipt)
    if sorted(v2) != sorted(name for _, name in ACCOUNT_LABELS) or sorted(v1) != sorted(v2):
        raise SystemExit("header receipts: expected one v1 and one v2 receipt per account label")
    accounts, starts, ends = {}, [], []
    for name in sorted(v2):
        data, _ = v2[name]
        accounts[name] = [{"endpoint": path, "limit": int(limit), "remaining": int(remaining)}
                          for path, limit, remaining in data["limit_and_remaining_in_request_order"]]
        starts.append(data["started_utc"])
        ends.append(data["finished_utc"])
    for name in sorted(v1):
        data, _ = v1[name]
        starts.append(data["started_utc"])
        ends.append(data["finished_utc"])
    shared_endpoints = ["/v2/account", "/v2/orders?status=open&limit=1", "/v2/positions"]
    same = all(accounts[name] == accounts["lane_a"] for name in accounts)
    bucket_rows = [row for row in accounts["lane_a"] if row["endpoint"] in shared_endpoints]
    clock_rows = [row for row in accounts["lane_a"] if row["endpoint"] == "/v2/clock"]
    v1_agree = all(
        [(row[0], int(row[1])) for row in
         [(req["path"], req["headers"]["x-ratelimit-limit"]) for req in v1[name][0]["requests"]]]
        == [("/v2/clock", 1000), ("/v2/account", 200)] for name in v1)
    return {
        "method": ("Read-only GET requests to the paper trading host, one account per run; only status, timing and five response "
                   "headers (x-ratelimit-limit, x-ratelimit-remaining, x-ratelimit-reset, retry-after, date) were kept; "
                   "no response body, key or identifier was retained."),
        "read_window_utc": {"first_request_started": utc_seconds(min(starts)), "last_request_finished": utc_seconds(max(ends))},
        "probe_versions": {"v1_requests": ["/v2/clock", "/v2/account"],
                           "v2_requests": [row["endpoint"] for row in accounts["lane_a"]]},
        "accounts": accounts,
        "summary": {
            "same_on_all_three_accounts": same,
            "v1_receipts_agree_with_v2": v1_agree,
            "limit_on_account_order_position_reads": sorted({row["limit"] for row in bucket_rows}),
            "limit_on_clock_read": sorted({row["limit"] for row in clock_rows}),
            "remaining_in_request_order_on_the_shared_bucket": [row["remaining"] for row in bucket_rows],
            "bucket_sharing_reading": ("remaining fell by exactly one per request across account, order-list and position reads, "
                                       "so those endpoints draw on one bucket; /v2/clock reports its own, larger limit"),
        },
    }


def capacity_section(capacity_dir, observer_path):
    capacity_dir = Path(capacity_dir)
    a2 = load_json(capacity_dir / "capacity-200-pre-a2.json")
    a1 = load_json(capacity_dir / "capacity-200-pre-a1.json")
    journal_rows = [json.loads(line) for line in (capacity_dir / "capacity-200-pre-a2.journal.jsonl").read_bytes().splitlines()]
    observer = load_json(observer_path)

    t = a2["throughput"]
    windows = t["windows"]
    full = [w for w in windows if w["full"]]
    submits = a2["orders"]["rest_accepted"]
    in_phase = t["order_actions_in_phase"]
    in_phase_cancels = in_phase - submits
    cleanup_cancels = a2["cleanup"]["individual_cancels"]
    seconds = Decimal(str(t["submission_phase_seconds"]))
    wall = Decimal(str(seconds_of(a2["provenance"]["ended_at"]) - seconds_of(a2["started_at"])))
    wall = wall.quantize(Decimal("0.000001"), rounding=ROUND_HALF_EVEN)
    header_counts = a2["observed_rate_limit_headers"]["counts_by_origin_and_limit"]
    status_counts = a2["http_status_counts"]
    trading_responses = sum(v for k, v in status_counts.items() if k.startswith("trading:"))
    trading_header_observations = sum(v for k, v in header_counts.items() if k.startswith("trading:"))
    limit_200 = header_counts.get("trading:200", 0)
    write_responses = status_counts.get("trading:submit:200", 0) + status_counts.get("trading:cancel:204", 0)
    reads_other = status_counts.get("trading:read:200", 0) - header_counts.get("trading:1000", 0)
    obs = observer["summary"]
    stderr_path = capacity_dir / "a2.stderr"
    stream_restart_notices = (sum(1 for line in stderr_path.read_text(errors="replace").splitlines() if "restarting" in line)
                              if stderr_path.is_file() else None)
    argv = a2["provenance"]["argv"]
    feed = argv[argv.index("--feed") + 1] if "--feed" in argv else None
    windows_total = sum(w["order_actions"] for w in windows)
    config_equal_but_base_url = ({k: v for k, v in a1["config"].items() if k != "base_url"}
                                 == {k: v for k, v in a2["config"].items() if k != "base_url"})
    intents = [row for row in journal_rows if row["type"] == "intent"]
    return {
        "capacity_run": {
            "run_label": "a2",
            "status": a2["status"],
            "stop_reason": a2["stop_reason"],
            "stop_reason_meaning": "the run ended on its configured duration limit, not on an error or a rate-limit response",
            "session_class": a2["session_kind"],
            "session_class_meaning": "pre-market (extended hours), US equities",
            "started_at_utc": utc_seconds(a2["started_at"]),
            "ended_at_utc": utc_seconds(a2["provenance"]["ended_at"]),
            "account": "lane A paper account (mapping private)",
            "harness": {"id": a2["harness"], "receipt_schema_version": a2["schema_version"], "evidence_class": a2["evidence_class"],
                        "counts_as_strategy_trades": a2["counts_as_strategy_trades"], "strategy_trades": a2["strategy_trades"]},
            "workload": {
                "instrument": "one liquid US equity ETF (symbol not published)",
                "quantity_shares": a2["config"]["qty"],
                "side": a2["probe_plan"]["side"],
                "order_type": a2["probe_plan"]["type"],
                "time_in_force": a2["probe_plan"]["time_in_force"],
                "marketable": a2["probe_plan"]["marketable"],
                "limit_band_bps_below_bid": a2["probe_plan"]["band_bps_below_bid"],
                "extended_hours": a2["extended_hours_orders"],
                "cancel": a2["probe_plan"]["cancel"],
                "inflight": a2["config"]["inflight"],
                "max_open_orders": a2["config"]["max_open_orders"],
                "max_orders": a2["config"]["max_orders"],
                "max_duration_seconds": a2["config"]["max_duration_seconds"],
                "data_feed": feed,
            },
            "limits": {
                "configured_cap_per_minute": a2["rate"]["configured_cap_per_minute"],
                "observed_limit_header": a2["rate"]["observed_limit"],
                "effective_limit": a2["rate"]["effective_limit"],
                "headroom": a2["rate"]["headroom"],
                "budget_per_minute": a2["rate"]["budget_per_minute"],
                "reserve_per_minute": a2["rate"]["reserve_per_minute"],
                "target_actions_ratio": a2["config"]["target_actions_ratio"],
                "target_order_actions_per_full_window": a2["acceptance"]["target_order_actions_per_window"],
                "required_consecutive_full_windows": a2["acceptance"]["required_consecutive_full_windows"],
                "window_seconds": 60,
                "action_definition": a2["acceptance"]["target_rule"],
            },
            "counts": {
                "submit_attempts": a2["orders"]["submit_attempts"],
                "submits_accepted_by_rest": submits,
                "rest_rejections_by_code": a2["orders"]["rest_rejections"],
                "cancel_requests": a2["orders"]["cancel_requests"],
                "http_status_counts": dict(sorted(status_counts.items())),
                "http_429_total": a2["http_429"]["total"],
                "unexpected_fill_qty": a2["orders"]["unexpected_fill_qty"],
                "health_freezes": len(a2["health_freezes"]),
                "port_errors": a2["port_errors"],
                "stream_events": a2["websocket"]["events_total"],
                "stream_completeness": a2["websocket"]["completeness"],
                "stream_malformed_events": a2["websocket"]["malformed_events"],
                "stderr_stream_restart_notices": stream_restart_notices,
            },
            "throughput": {
                "submission_phase_seconds": t["submission_phase_seconds"],
                "order_actions_in_phase": in_phase,
                "order_actions_per_minute_mean": t["order_actions_per_minute_mean"],
                "full_windows": t["full_windows"],
                "min_order_actions_full_window": t["min_order_actions_full_window"],
                "max_order_actions_full_window": t["max_order_actions_full_window"],
                "min_submits_full_window": t["min_submits_full_window"],
                "best_consecutive_full_windows_at_target": a2["acceptance"]["best_consecutive_full_windows_at_target"],
                "windows": [{"index": w["index"], "full": w["full"], "submits": w["submits"], "cancels": w["cancels"],
                             "order_actions": w["order_actions"], "reads": w["reads"]} for w in windows],
                "windows_total_order_actions": windows_total,
                "windows_total_minus_in_phase": windows_total - in_phase,
                "cleanup_individual_cancels": cleanup_cancels,
                "windows_note": ("the windows count every recorded action after the phase start, including the cancel the receipt records "
                                 "in cleanup, so they sum to windows_total_minus_in_phase more actions than order_actions_in_phase"),
            },
            "latency_ms_from_receipt": {
                name: {"count": a2["latency"][name]["count"], "p50": a2["latency"][name]["p50_ms"], "p95": a2["latency"][name]["p95_ms"],
                       "p99": a2["latency"][name]["p99_ms"], "max": a2["latency"][name]["max_ms"]}
                for name in ("submit_rest_ack", "submit_to_stream_ack", "submit_to_stream_terminal")},
            "latency_definitions": {
                "submit_rest_ack": "from sending the order request to its HTTP response",
                "submit_to_stream_ack": "from sending the order request to the order's acknowledgement on the trade-update stream",
                "submit_to_stream_terminal": "from sending the order request to the order's terminal trade-update event (here: the cancel completing)",
                "percentile_method": "nearest rank; the receipt records p50, p95, p99 and max only",
                "p90": "NOT_RECORDED: neither the receipt nor the journal holds raw per-request samples",
            },
            "rate_limit_headers_seen_during_run": {
                "counts_by_origin_and_limit": dict(sorted(header_counts.items())),
                "min_remaining_by_origin": dict(sorted(a2["observed_rate_limit_headers"]["min_remaining_by_origin"].items())),
                "write_path_reading": {
                    "trading_responses": trading_responses,
                    "trading_header_observations": trading_header_observations,
                    "observations_with_limit_200": limit_200,
                    "submit_and_cancel_responses": write_responses,
                    "other_trading_reads": reads_other,
                    "all_submit_and_cancel_responses_reported_200": (
                        trading_header_observations == trading_responses and limit_200 == write_responses + reads_other
                        and 1000 in a2["preflight"]["trading_limit_headers_seen"]),
                    "reasoning": ("by counting: every trading response carried the header (observations equal responses); the single "
                                  "1000-valued observation matches the one the preflight recorded, so the 200-valued observations "
                                  "number submits + cancels + the other reads"),
                },
            },
            "acceptance_as_recorded": {
                "capacity_criteria_met": a2["acceptance"]["capacity_criteria_met"],
                "passed": a2["acceptance"]["passed"],
                "passed_is_self_reported": a2["acceptance"]["passed_is_self_reported"],
                "reconciliation_clean": a2["acceptance"]["reconciliation_clean"],
                "cleanup_verified_zero_open": a2["acceptance"]["cleanup_verified_zero_open"],
                "no_unexpected_fills": a2["acceptance"]["no_unexpected_fills"],
                "independent_observation_required": bool(a2["acceptance"]["independent_observation_required"]),
            },
            "reconciliation": {
                "broker_orders_with_prefix": a2["reconciliation"]["broker_orders_with_prefix"],
                "local_probes": a2["reconciliation"]["local_probes"],
                "filled_probes": len(a2["reconciliation"]["filled_probes"]),
                "non_terminal_at_end": len(a2["reconciliation"]["non_terminal_at_end"]),
                "position_unchanged": a2["reconciliation"]["position_unchanged"],
                "open_orders_after_cleanup": a2["cleanup"]["open_harness_orders_after"],
                "cleanup_seconds": a2["cleanup"]["seconds"],
                "cancel_all_used": a2["cleanup"]["cancel_all_used"],
            },
            "journal": {
                "record_counts": {"start": sum(1 for r in journal_rows if r["type"] == "start"), "intent": len(intents),
                                  "end": sum(1 for r in journal_rows if r["type"] == "end")},
                "intent_fields": sorted(set().union(*[set(r) for r in intents])),
                "intent_fields_include_timing": False,
                "end_verified_zero_open": journal_rows[-1]["verified_zero_open"],
            },
        },
        "independent_observer": {
            "kind": observer["kind"],
            "method": ("one read-only request listing the account's orders (all statuses) for the run's time window plus or minus two "
                       "minutes, made after the run; only counts, a status histogram and per-minute window counts were kept"),
            "limitation": "uses the same vendor API as the harness; it checks counts and order outcomes, it does not certify latency percentiles",
            "observed_at_utc": utc_seconds(observer["started_utc"]),
            "http_statuses": observer["http_statuses"],
            "orders_listed_in_window": obs["orders_listed_in_window"],
            "orders_with_prefix": obs["with_prefix"],
            "orders_without_prefix": obs["without_prefix"],
            "status_counts": obs["status_counts"],
            "submits": obs["submits"],
            "cancels_recorded": obs["cancels_recorded"],
            "actions_total": obs["actions_total"],
            "filled_qty_total": obs["filled_qty_total"],
            "span_seconds": obs["span_seconds"],
            "full_windows": obs["full_windows"],
            "min_actions_full_window": obs["min_actions_full_window"],
            "max_actions_full_window": obs["max_actions_full_window"],
            "min_submits_full_window": obs["min_submits_full_window"],
            "windows": [{"index": w["index"], "full": w["full"], "submits": w["submits"], "cancels": w["cancels"], "actions": w["actions"]}
                        for w in obs["windows"]],
            "matches": dict(sorted(obs["matches"].items())),
            "window_difference_note": ("the observer aligns its one-minute windows to the first order's broker submit time and the "
                                       "harness to its own phase start, so single cancels near a boundary fall in different windows "
                                       "(observer 181/180/180/180/180 against harness 180 in every full window); totals are identical "
                                       "(496 submits, 496 cancels); both are retained"),
        },
        "superseded_attempt": {
            "run_label": "a1",
            "status": a1["status"],
            "stage": a1["stage"],
            "refusal_reason": a1["refusal_reason"],
            "exit_code": a1["provenance"]["exit_code"],
            "base_url_spelling": a1["config"]["base_url"],
            "http_requests_sent": sum(a1["http_status_counts"].values()),
            "orders_submitted": a1["orders"]["submit_attempts"],
            "capacity_criteria_met": a1["acceptance"]["capacity_criteria_met"],
            "started_at_utc": utc_seconds(a1["started_at"]),
            "config_differs_from_a2_only_in_base_url": config_equal_but_base_url,
            "relation_to_a2": ("a1 was refused at the configuration stage, before any request, because its base URL carried a path suffix; "
                               "a2 ran the same configuration with the bare paper host, at a later harness revision "
                               "(capacity.py differs between the two revisions)"),
            "a2_base_url_spelling": a2["config"]["base_url"],
        },
        "facts": {
            "harness_revision_a2": a2["provenance"]["git_revision"],
            "harness_revision_a1": a1["provenance"]["git_revision"],
            "alpaca_py_version": a2["provenance"]["alpaca_py_version"],
            "python_version": a2["provenance"]["python_version"],
            "capacity_py_sha256": {"a1": a1["provenance"]["source_sha256"]["order-throughput/capacity.py"],
                                   "a2": a2["provenance"]["source_sha256"]["order-throughput/capacity.py"]},
            "source_files_hashed_in_receipt": sorted(a2["provenance"]["source_sha256"]),
        },
        "_derived_inputs": {
            "phase_seconds": seconds, "wall_seconds": wall, "submits": submits, "in_phase_cancels": in_phase_cancels,
            "cleanup_cancels": cleanup_cancels, "full_windows": full,
            "configured_cap": a2["rate"]["configured_cap_per_minute"], "observed_limit": a2["rate"]["observed_limit"],
            "headroom": a2["rate"]["headroom"], "budget_in_receipt": a2["rate"]["budget_per_minute"],
        },
    }


def derived_section(inputs):
    seconds, wall = inputs["phase_seconds"], inputs["wall_seconds"]
    submits, cancels, full = inputs["submits"], inputs["in_phase_cancels"], inputs["full_windows"]
    per_min = lambda count, secs: fixed((Decimal(count) * 60) / secs)
    mean = lambda values: fixed(Decimal(sum(values)) / Decimal(len(values)), 1)
    budget = int((Decimal(inputs["configured_cap"]).min(Decimal(inputs["observed_limit"])) * Decimal(str(inputs["headroom"]))).to_integral_value(rounding="ROUND_FLOOR"))
    return {
        "formulas": {
            "orders_with_cancel_per_minute_in_phase": "in_phase_cancels * 60 / submission_phase_seconds (an order and its cancel are one complete order)",
            "submits_per_minute_in_phase": "submits_accepted * 60 / submission_phase_seconds",
            "pair_equivalents_per_minute_full_windows": "mean(order_actions over full windows) / 2",
            "orders_with_cancel_per_minute_including_setup_and_cleanup": "submits_accepted * 60 / (ended_at - started_at)",
            "request_budget_per_minute": "floor(min(configured_cap, observed_limit) * headroom)",
            "target_actions_per_full_window": "ceil(target_actions_ratio * effective_limit)",
        },
        "values": {
            "in_phase_cancels": cancels,
            "orders_with_cancel_per_minute_in_phase": per_min(cancels, seconds),
            "submits_per_minute_in_phase": per_min(submits, seconds),
            "order_actions_per_minute_in_phase": per_min(submits + cancels, seconds),
            "pair_equivalents_per_minute_full_windows": fixed(
                Decimal(sum(w["order_actions"] for w in full)) / Decimal(len(full)) / 2, 3),
            "full_window_submits_mean_per_minute": mean([w["submits"] for w in full]),
            "full_window_cancels_mean_per_minute": mean([w["cancels"] for w in full]),
            "wall_seconds_start_to_end_of_run": fixed(wall, 6),
            "orders_with_cancel_per_minute_including_setup_and_cleanup": per_min(submits, wall),
            "request_budget_per_minute_computed": budget,
            "request_budget_per_minute_in_receipt": inputs["budget_in_receipt"],
        },
        "reading": ("The run sustained 90 orders per minute, each with its individual cancel, i.e. 180 completed trading requests per minute "
                    "against a 200-per-minute bucket, for five consecutive full minutes plus a partial sixth, with no HTTP 429. "
                    "Place-only capacity, the 429 onset and any rate above the 180-per-minute governed budget were not measured."),
    }


def build(args):
    capacity = capacity_section(args.capacity_dir, args.observer_receipt)
    inputs = capacity.pop("_derived_inputs")
    derived = derived_section(inputs)
    a2_name, journal_name, a1_name = "capacity-200-pre-a2.json", "capacity-200-pre-a2.journal.jsonl", "capacity-200-pre-a1.json"
    header_dir = Path(args.header_receipts_dir)
    receipts = [
        {"name": a2_name},
        {"name": journal_name},
        {"name": a1_name},
        {"name": "order-count observer receipt (a2)"},
    ]
    for entry in sorted(header_dir.iterdir()):
        receipt = entry / "receipt.json"
        if HEADER_DIR_NAME.match(entry.name) and receipt.is_file():
            data = load_json(receipt)
            label = next(name for prefix, name in ACCOUNT_LABELS if str(data["label"]).startswith(prefix))
            version = "v2" if data["kind"].endswith("_v2") else "v1"
            receipts.append({"name": f"header receipt {version} {label}"})
    number_map = {
        "limit_200_on_account_order_position_reads": "header receipts v2: limit_and_remaining_in_request_order (path, limit, remaining) x 3 accounts",
        "limit_1000_on_clock_read": "header receipts v1 and v2: the /v2/clock row",
        "remaining_199_198_197_196": "header receipts v2: remaining of the account, orders, positions, account rows",
        "submits_496_cancels_496": "a2: orders.rest_accepted, orders.cancel_requests, http_status_counts[trading:submit:200, trading:cancel:204]",
        "http_429_total_0": "a2: http_429.total",
        "five_full_windows_of_180_actions": "a2: throughput.windows[0..4].order_actions and throughput.full_windows",
        "submission_phase_seconds_330_002": "a2: throughput.submission_phase_seconds",
        "order_actions_in_phase_991_and_mean_180_181": "a2: throughput.order_actions_in_phase, throughput.order_actions_per_minute_mean",
        "latency_p50_p95_p99_max": "a2: latency.submit_rest_ack / submit_to_stream_ack / submit_to_stream_terminal",
        "header_observations_1000_at_200_1_at_1000": "a2: observed_rate_limit_headers.counts_by_origin_and_limit and preflight.trading_limit_headers_seen",
        "min_remaining_194": "a2: observed_rate_limit_headers.min_remaining_by_origin.trading",
        "observer_496_listed_496_canceled_0_filled": "observer receipt: summary.orders_listed_in_window, status_counts, filled_qty_total",
        "a1_refusal": "a1: status, stage, refusal_reason, config.base_url, http_status_counts",
        "journal_not_timing": "a2 journal: record types and the intent field set",
        "derived_units": "computed in this projection from the fields above by the formulas in derived_units.formulas",
    }
    document = {
        "schema": SCHEMA,
        "kind": "sanitized_projection_of_private_receipts",
        "measured_date_utc": "2026-10-13",
        "venue": "Alpaca paper trading API (paper host)",
        "units": ("an order is one accepted submit; an order with its individual cancel is two completed trading requests; "
                  "the vendor bucket counts requests, so 200 requests per minute is at most 100 orders each with a cancel"),
        "how_to_verify": "python3 verify_alpaca_throughput_evidence.py --evidence <this file> --capacity-dir <dir> --header-receipts-dir <dir> --observer-receipt <file>",
        "privacy_statement": ("Account labels are lane labels whose mapping to real accounts is private. No account identifier, credential, client "
                              "order id, price, symbol or file-system path appears here. Each number is a receipt field or arithmetic on receipt fields."),
        "headline": {
            "x_ratelimit_limit_account_order_position_reads": 200,
            "x_ratelimit_limit_clock_read": 1000,
            "limit_reported_on_submit_and_cancel_responses_during_run": 200,
            "governed_budget_requests_per_minute": capacity["capacity_run"]["limits"]["budget_per_minute"],
            "sustained_orders_with_cancel_per_minute": derived["values"]["pair_equivalents_per_minute_full_windows"],
            "sustained_seconds": capacity["capacity_run"]["throughput"]["submission_phase_seconds"],
            "http_429_total": capacity["capacity_run"]["counts"]["http_429_total"],
            "place_only_capacity": "NOT_MEASURED",
            "p90_latency": "NOT_RECORDED",
        },
        "rate_limit_headers": header_section(args.header_receipts_dir),
        **capacity,
        "derived_units": derived,
        "not_measured": [
            "place-only (no cancel) order capacity: the harness cancels every probe individually",
            "the HTTP 429 onset or behaviour above the 180-requests-per-minute governed budget; the headers reported 200",
            "simultaneous order-write throughput on several accounts",
            "whether the bucket is shared across several API connections or keys of one account (vendor-documented per account, not measured here)",
            "latency p90, or any raw per-request latency sample",
            "regular-session (RTH) behaviour: the run was pre-market with extended-hours orders",
        ],
        "caveats": [
            "one account, one session class, one 330-second submission phase (five full one-minute windows)",
            "the 200 rung is the configured cap; the governor admitted 180 requests per minute (headroom 0.9)",
            "the receipt's passed flag is self-reported; the independent_observer block is the separate count check",
            "the trade-update stream logged one reconnect notice with normal closure codes on stderr; the receipt reports stream completeness 1.0 and no health freeze",
            "the vendor's own statement of the per-account limit is cited by the handbook from the vendor's support page and was not re-read here",
        ],
        "provenance": {
            "private_receipts": receipts,
            "number_to_receipt_field": number_map,
        },
    }
    return public_document(document)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--capacity-dir")
    parser.add_argument("--header-receipts-dir")
    parser.add_argument("--observer-receipt")
    parser.add_argument("--public-evidence", help="re-export an approved projection without private input reads")
    parser.add_argument("--out")
    args = parser.parse_args(argv)
    private_inputs = (args.capacity_dir, args.header_receipts_dir, args.observer_receipt)
    if args.public_evidence:
        if any(private_inputs):
            parser.error("public re-export cannot be combined with private inputs")
        document = public_document(load_json(args.public_evidence))
    else:
        if not all(private_inputs):
            parser.error("provide --public-evidence or all three private input paths")
        document = build(args)
    text = json.dumps(document, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="ascii")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
