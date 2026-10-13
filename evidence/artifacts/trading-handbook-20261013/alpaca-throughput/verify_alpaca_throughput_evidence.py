#!/usr/bin/env python3
"""Verify the sanitized Alpaca throughput projection against the private raw receipts it was built from.

Independent of the generator: every headline number is recomputed here from the raw receipts (capacity run and journal, header probe receipts,
order-count observer receipt) and compared with the value the projection states. Prints one PASS/FAIL line per number; exit 0 only if all pass.
Stdlib only; no network, no credential, no clock, no environment.

usage: python3 verify_alpaca_throughput_evidence.py --evidence FILE --capacity-dir DIR --header-receipts-dir DIR --observer-receipt FILE
"""
import argparse
import hashlib
import json
import math
import re
import sys
from datetime import datetime
from decimal import Decimal, ROUND_HALF_EVEN
from pathlib import Path

RESULTS = []


def check(name, expected, got):
    ok = expected == got
    RESULTS.append(ok)
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": projection says {expected!r}, raw receipts give {got!r}"))


def q(value, places):
    return str(Decimal(str(value)).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_EVEN))


def secs(iso):
    return datetime.fromisoformat(iso).timestamp()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence", required=True)
    ap.add_argument("--capacity-dir", required=True)
    ap.add_argument("--header-receipts-dir", required=True)
    ap.add_argument("--observer-receipt", required=True)
    args = ap.parse_args(argv)

    ev = json.loads(Path(args.evidence).read_bytes())
    cap = Path(args.capacity_dir)
    a2 = json.loads((cap / "capacity-200-pre-a2.json").read_bytes())
    a1 = json.loads((cap / "capacity-200-pre-a1.json").read_bytes())
    journal = [json.loads(line) for line in (cap / "capacity-200-pre-a2.journal.jsonl").read_bytes().splitlines()]
    obs = json.loads(Path(args.observer_receipt).read_bytes())["summary"]
    run = ev["capacity_run"]

    # -- header probes (three accounts) --
    hdr = {}
    for entry in sorted(Path(args.header_receipts_dir).iterdir()):
        m = re.match(r"^readonly-limits(2?)-(lane-a|lane-b|acct-c)-[a-z0-9-]+-20261013$", entry.name)
        if m and (entry / "receipt.json").is_file():
            hdr[(("v2" if m.group(1) else "v1"), {"lane-a": "lane_a", "lane-b": "lane_b", "acct-c": "account_c"}[m.group(2)])] = \
                json.loads((entry / "receipt.json").read_bytes())
    names = ["lane_a", "lane_b", "account_c"]
    for who in names:
        seq = hdr[("v2", who)]["limit_and_remaining_in_request_order"]
        rows = [(p, int(l), int(r)) for p, l, r in seq]
        check(f"headers[{who}]: /v2/clock limit 1000", 1000, next(l for p, l, r in rows if p == "/v2/clock"))
        shared = [(p, l, r) for p, l, r in rows if p != "/v2/clock"]
        check(f"headers[{who}]: account, orders, positions limit 200 (4 requests)", [200] * 4, [l for _, l, _ in shared])
        check(f"headers[{who}]: remaining 199,198,197,196", [199, 198, 197, 196], [r for _, _, r in shared])
        proj = [(row["endpoint"], row["limit"], row["remaining"]) for row in ev["rate_limit_headers"]["accounts"][who]]
        check(f"headers[{who}]: projection rows equal receipt rows", proj, rows)
        v1 = [(r["path"], int(r["headers"]["x-ratelimit-limit"]), int(r["headers"]["x-ratelimit-remaining"])) for r in hdr[("v1", who)]["requests"]]
        check(f"headers[{who}]: v1 probe agrees (clock 1000/999, account 200/199)", [("/v2/clock", 1000, 999), ("/v2/account", 200, 199)], v1)

    # -- capacity run counts --
    st = a2["http_status_counts"]
    check("submits accepted (REST 200)", run["counts"]["submits_accepted_by_rest"], st["trading:submit:200"])
    check("cancels acknowledged (REST 204)", run["counts"]["cancel_requests"], st["trading:cancel:204"])
    check("submit and cancel counts both 496", (496, 496), (st["trading:submit:200"], st["trading:cancel:204"]))
    check("HTTP 429 total", run["counts"]["http_429_total"], a2["http_429"]["total"])
    check("HTTP 429 total is 0", 0, a2["http_429"]["total"])
    check("rejections by code empty", {}, run["counts"]["rest_rejections_by_code"])
    check("unexpected fill quantity", "0", run["counts"]["unexpected_fill_qty"])
    check("stream completeness", run["counts"]["stream_completeness"], a2["websocket"]["completeness"])
    check("orders open after cleanup", 0, run["reconciliation"]["open_orders_after_cleanup"])
    check("raw: orders open after cleanup", 0, a2["cleanup"]["open_harness_orders_after"])
    check("raw: filled probes", 0, len(a2["reconciliation"]["filled_probes"]))

    # -- windows and phase totals --
    w = a2["throughput"]["windows"]
    full = [x for x in w if x["full"]]
    check("full windows count", run["throughput"]["full_windows"], len(full))
    check("five full windows, each 180 order actions", [180] * 5, [x["order_actions"] for x in full])
    check("submits + cancels per window equals order_actions (all windows)", True, all(x["submits"] + x["cancels"] == x["order_actions"] for x in w))
    check("phase seconds", run["throughput"]["submission_phase_seconds"], a2["throughput"]["submission_phase_seconds"])
    check("order actions in phase", run["throughput"]["order_actions_in_phase"], a2["throughput"]["order_actions_in_phase"])
    check("mean per minute = round(in_phase * 60 / phase seconds, 3)", run["throughput"]["order_actions_per_minute_mean"],
          float(q(Decimal(a2["throughput"]["order_actions_in_phase"]) * 60 / Decimal(str(a2["throughput"]["submission_phase_seconds"])), 3)))
    in_phase_cancels = a2["throughput"]["order_actions_in_phase"] - a2["orders"]["rest_accepted"]
    check("in-phase cancels = in_phase - submits", ev["derived_units"]["values"]["in_phase_cancels"], in_phase_cancels)
    check("one cancel recorded in cleanup", 1, a2["cleanup"]["individual_cancels"])
    check("all cancels = in-phase cancels + cleanup cancels", a2["orders"]["cancel_requests"], in_phase_cancels + a2["cleanup"]["individual_cancels"])
    check("windows sum minus in-phase equals the cleanup cancel", (run["throughput"]["windows_total_order_actions"], 1),
          (sum(x["order_actions"] for x in w), sum(x["order_actions"] for x in w) - a2["throughput"]["order_actions_in_phase"]))

    # -- derived units, recomputed --
    dv = ev["derived_units"]["values"]
    seconds = Decimal(str(a2["throughput"]["submission_phase_seconds"]))
    wall = Decimal(str(secs(a2["provenance"]["ended_at"]) - secs(a2["started_at"]))).quantize(Decimal("0.000001"), rounding=ROUND_HALF_EVEN)
    check("orders with cancel per minute in phase", dv["orders_with_cancel_per_minute_in_phase"], q(Decimal(in_phase_cancels) * 60 / seconds, 6))
    check("submits per minute in phase", dv["submits_per_minute_in_phase"], q(Decimal(a2["orders"]["rest_accepted"]) * 60 / seconds, 6))
    check("order actions per minute in phase", dv["order_actions_per_minute_in_phase"], q(Decimal(a2["throughput"]["order_actions_in_phase"]) * 60 / seconds, 6))
    check("pair equivalents per minute, full windows", dv["pair_equivalents_per_minute_full_windows"],
          q(Decimal(sum(x["order_actions"] for x in full)) / Decimal(len(full)) / 2, 3))
    check("full-window submits mean", dv["full_window_submits_mean_per_minute"], q(Decimal(sum(x["submits"] for x in full)) / len(full), 1))
    check("full-window cancels mean", dv["full_window_cancels_mean_per_minute"], q(Decimal(sum(x["cancels"] for x in full)) / len(full), 1))
    check("wall seconds start to end", dv["wall_seconds_start_to_end_of_run"], q(wall, 6))
    check("orders with cancel per minute incl. setup and cleanup", dv["orders_with_cancel_per_minute_including_setup_and_cleanup"],
          q(Decimal(a2["orders"]["rest_accepted"]) * 60 / wall, 6))
    budget = math.floor(Decimal(min(a2["rate"]["configured_cap_per_minute"], a2["rate"]["observed_limit"])) * Decimal(str(a2["rate"]["headroom"])))
    check("request budget = floor(min(cap, observed limit) * headroom)", (dv["request_budget_per_minute_computed"], dv["request_budget_per_minute_in_receipt"]),
          (budget, a2["rate"]["budget_per_minute"]))
    check("target actions per full window = ceil(0.85 * 200)", run["limits"]["target_order_actions_per_full_window"],
          math.ceil(Decimal(str(a2["config"]["target_actions_ratio"])) * a2["rate"]["effective_limit"]))

    # -- latency fields (copied) --
    for name in ("submit_rest_ack", "submit_to_stream_ack", "submit_to_stream_terminal"):
        for key_ev, key_raw in (("p50", "p50_ms"), ("p95", "p95_ms"), ("p99", "p99_ms"), ("max", "max_ms"), ("count", "count")):
            check(f"latency {name} {key_ev}", run["latency_ms_from_receipt"][name][key_ev], a2["latency"][name][key_raw])
    check("latency has no p90 in the receipt", False, any("p90" in str(k) for blk in a2["latency"].values() for k in blk))
    check("journal intent fields carry no timing", ["client_order_id", "extended_hours", "limit_price", "qty", "seq", "type"],
          sorted({k for r in journal if r["type"] == "intent" for k in r}))
    check("journal record counts", {"start": 1, "intent": 496, "end": 1},
          {t: sum(1 for r in journal if r["type"] == t) for t in ("start", "intent", "end")})
    check("journal end: verified zero open", True, journal[-1]["verified_zero_open"])

    # -- headline block --
    hl = ev["headline"]
    check("headline: bucket limit 200 on reads of all three accounts", 200, hl["x_ratelimit_limit_account_order_position_reads"])
    check("headline: raw header receipts all report 200 on the shared reads", {200},
          {int(l) for who in names for p, l, r in hdr[("v2", who)]["limit_and_remaining_in_request_order"] if p != "/v2/clock"})
    check("headline: clock limit 1000", 1000, hl["x_ratelimit_limit_clock_read"])
    check("headline: governed budget", a2["rate"]["budget_per_minute"], hl["governed_budget_requests_per_minute"])
    check("headline: sustained orders with cancel per minute (full windows)", hl["sustained_orders_with_cancel_per_minute"],
          q(Decimal(sum(x["order_actions"] for x in full)) / Decimal(len(full)) / 2, 3))
    check("headline: sustained seconds", hl["sustained_seconds"], a2["throughput"]["submission_phase_seconds"])
    check("headline: 429 total", hl["http_429_total"], a2["http_429"]["total"])
    stderr_file = cap / "a2.stderr"
    check("stderr stream restart notices", run["counts"]["stderr_stream_restart_notices"],
          sum(1 for line in stderr_file.read_text(errors="replace").splitlines() if "restarting" in line) if stderr_file.is_file() else None)

    # -- header observations during the run --
    obs_counts = a2["observed_rate_limit_headers"]["counts_by_origin_and_limit"]
    trading_responses = sum(v for k, v in st.items() if k.startswith("trading:"))
    check("trading responses = submits + cancels + reads", trading_responses, st["trading:submit:200"] + st["trading:cancel:204"] + st["trading:read:200"])
    check("header observations: 1000 at limit 200, 1 at limit 1000", {"trading:200": 1000, "trading:1000": 1, "data:10000": 1}, obs_counts)
    check("every trading response carried the header", trading_responses, obs_counts["trading:200"] + obs_counts["trading:1000"])
    check("projection: all submit and cancel responses reported 200",
          True, run["rate_limit_headers_seen_during_run"]["write_path_reading"]["all_submit_and_cancel_responses_reported_200"]
          and 1000 in a2["preflight"]["trading_limit_headers_seen"]
          and obs_counts["trading:200"] >= st["trading:submit:200"] + st["trading:cancel:204"])
    check("min remaining on trading responses", run["rate_limit_headers_seen_during_run"]["min_remaining_by_origin"]["trading"],
          a2["observed_rate_limit_headers"]["min_remaining_by_origin"]["trading"])

    # -- independent observer --
    io = ev["independent_observer"]
    check("observer: orders listed", io["orders_listed_in_window"], obs["orders_listed_in_window"])
    check("observer: 496 listed, 496 canceled, 0 filled", (496, {"canceled": 496}, 0.0),
          (obs["orders_listed_in_window"], obs["status_counts"], obs["filled_qty_total"]))
    check("observer: submits and cancels equal the capacity receipt", (a2["orders"]["rest_accepted"], a2["orders"]["cancel_requests"]),
          (obs["submits"], obs["cancels_recorded"]))
    check("observer: all matches true", True, all(obs["matches"].values()))
    check("observer: window actions", [x["actions"] for x in io["windows"]], [x["actions"] for x in obs["windows"]])
    check("observer: first window 181 vs harness 180", (181, 180), (obs["windows"][0]["actions"], a2["throughput"]["windows"][0]["order_actions"]))

    # -- superseded attempt --
    sa = ev["superseded_attempt"]
    check("a1 status/stage/reason", (sa["status"], sa["stage"], sa["refusal_reason"]), (a1["status"], a1["stage"], a1["refusal_reason"]))
    check("a1 refused with exit code 2 and no requests", (2, 0, 0), (a1["provenance"]["exit_code"], sum(a1["http_status_counts"].values()), a1["orders"]["submit_attempts"]))
    check("a1 base URL had the path suffix, a2 did not", ("https://paper-api.alpaca.markets/v2", "https://paper-api.alpaca.markets"),
          (a1["config"]["base_url"], a2["config"]["base_url"]))
    check("a1 and a2 configs equal except base URL", True,
          {k: v for k, v in a1["config"].items() if k != "base_url"} == {k: v for k, v in a2["config"].items() if k != "base_url"})
    check("capacity.py hash differs between a1 and a2", True,
          a1["provenance"]["source_sha256"]["order-throughput/capacity.py"] != a2["provenance"]["source_sha256"]["order-throughput/capacity.py"])

    # -- digests of the private receipts listed in the projection --
    listed = {r["name"]: r for r in ev["provenance"]["private_receipts"]}
    for fname in ("capacity-200-pre-a2.json", "capacity-200-pre-a2.journal.jsonl", "capacity-200-pre-a1.json"):
        data = (cap / fname).read_bytes()
        check(f"digest {fname}", (listed[fname]["bytes"], listed[fname]["sha256"]), (len(data), hashlib.sha256(data).hexdigest()))
    data = Path(args.observer_receipt).read_bytes()
    check("digest observer receipt", (listed["order-count observer receipt (a2)"]["bytes"], listed["order-count observer receipt (a2)"]["sha256"]),
          (len(data), hashlib.sha256(data).hexdigest()))
    for (version, who), rec in sorted(hdr.items()):
        for entry in Path(args.header_receipts_dir).iterdir():
            if entry.name.startswith(f"readonly-limits{'2' if version == 'v2' else ''}-") and rec["label"] == json.loads((entry / "receipt.json").read_bytes())["label"]:
                data = (entry / "receipt.json").read_bytes()
                row = listed[f"header receipt {version} {who}"]
                check(f"digest header receipt {version} {who}", (row["bytes"], row["sha256"]), (len(data), hashlib.sha256(data).hexdigest()))

    # -- sanitization of the projection text itself --
    text = Path(args.evidence).read_text(encoding="utf-8")
    scrubbed = re.sub(r"\b(?:[0-9a-fA-F]{64}|[0-9a-fA-F]{40})\b", " ", text)
    long_runs = [r for r in re.findall(r"(?<![0-9.])[0-9]{9,}(?![0-9])", scrubbed) if not re.match(r"^1[78][0-9]{8}$", r)]
    bad = {
        "long digit runs outside digests and clock readings": len(long_runs),
        "uuid shapes": len(re.findall(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b", text)),
        "email shapes": len(re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)),
        "absolute path fragments": len(re.findall(r"/(?:home|var|run|tmp|Users|root)/", text)),
        "paper account shapes": len(re.findall(r"\bPA[0-9A-Z]{8,12}\b", text)),
        "api key id shapes": len(re.findall(r"\b(?:PK|AK|CK)[A-Z0-9]{16,20}\b", text)),
        "client order id prefix shapes": len(re.findall(r"\bcap-[0-9]{8}t[0-9]{6}-", text)),
    }
    check("projection text is free of identifier and path shapes", {k: 0 for k in bad}, bad)

    failed = RESULTS.count(False)
    print(f"{len(RESULTS) - failed} PASS, {failed} FAIL")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
