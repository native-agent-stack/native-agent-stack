#!/usr/bin/env python3
"""Recompute the headline numbers of ibkr-pacing-evidence/1 (revision 2) from the private receipts and compare them with the document.

Revision 2 closes two defects found by a second reader in v1: (1) the `reconciliation` headline was never compared with the recomputed counters; (2) the kinds of the 38 missing orders
were a literal, not derived from the journals. v2 derives them from each missing order's journal events and the venue's refusal text.

Standard library only; deterministic; independent code path from the generator (it re-reads the receipts and journals and
re-derives each number with its own arithmetic). Prints one PASS/FAIL line per number and exits 1 if any FAIL.
Numbers that exist only as live broker reads in the session transcript (the two completed-order counts and the reqIds probe)
cannot be recomputed from files: for them the verifier checks only that the document marks them transcript-derived and that
the arithmetic relations between them and the file-derived numbers hold.

usage: python3 verify_ibkr_pacing_evidence.py EVIDENCE.json RUN_ROOT [PIN_CORE_RS]
       PIN_CORE_RS (optional): the file crates/adapters/interactive_brokers/src/execution/core.rs fetched at the pinned commit;
       when given, the cited line numbers are checked against its text.
"""
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

failures = 0


def check(name, expected, got):
    global failures
    ok = expected == got
    failures += 0 if ok else 1
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": document {expected!r} vs recomputed {got!r}"))


def close(name, expected, got, tol=0.011):
    global failures
    ok = expected is not None and got is not None and abs(expected - got) <= tol
    failures += 0 if ok else 1
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": document {expected!r} vs recomputed {got!r}"))


def receipt(root, label):
    return json.loads((root / "runs" / label / "receipt.json").read_text())


def journal(root, label):
    return [json.loads(line) for line in (root / "runs" / label / "journal.jsonl").read_text().splitlines()]


def headline(doc, ident):
    return next(h["value"] for h in doc["headline_numbers"] if h["id"] == ident)


def seconds_of(row):
    return int(datetime.fromisoformat(row["utc"]).timestamp())


def whole_run_rates(rows):
    """Independent recomputation: counted = submit + cancel; refined adds one scan per cancel of an accepted order;
    upper adds one per cancel. Returns {kind: (max over any second, best 5-second mean)}."""
    kinds = {"counted": Counter(), "refined": Counter(), "upper": Counter()}
    for row in rows:
        sec = seconds_of(row)
        if row["event"] == "submit":
            for counter in kinds.values():
                counter[sec] += 1
        elif row["event"] == "cancel":
            kinds["counted"][sec] += 1
            kinds["upper"][sec] += 2
            kinds["refined"][sec] += 1 if row.get("reason") == "unaccepted_after_1s" else 2
    out = {}
    for name, counter in kinds.items():
        secs = sorted(counter)
        best = max(sum(counter.get(s0 + k, 0) for k in range(5)) / 5 for s0 in secs)
        out[name] = {"max_1s": max(counter.values()), "best_5s_mean": round(best, 2)}
    return out


def main(argv):
    if len(argv) not in (3, 4):
        sys.stderr.write(__doc__)
        return 2
    doc = json.loads(Path(argv[1]).read_text())
    root = Path(argv[2])

    # 1. official client, rung 50: orders, seconds, rates
    r = receipt(root, "P-r1")
    rung50 = next(x for x in r["rungs"] if x["target_msgs_per_s"] == 50)
    close("official rung 50 mean counted msgs/s = 49.95", headline(doc, "official_rung50_counted_msgs_per_s_mean"), rung50["msgs_per_s_mean"])
    check("official rung 50 orders placed in the rung = 500", headline(doc, "official_rung50_orders_in_rung"), rung50["placed"])
    check("official rung 50 seconds = 20", headline(doc, "official_rung50_seconds"), rung50["seconds"])
    check("official rung 50 orders/min with cancel = placed / seconds x 60 = 1500", headline(doc, "official_rung50_orders_per_min_with_cancel"), round(rung50["placed"] / rung50["seconds"] * 60))
    check("official rung 50 messages/min = mean x 60 = 2997 (3000 rounded)", headline(doc, "official_rung50_msgs_per_min"), round(rung50["msgs_per_s_mean"] * 60))
    check("official ladder: placed, accepted, cancel-confirmed, open at end = 1650, 1650, 1650, 0",
          headline(doc, "official_ladder_orders_accepted_cancelled_open_at_end"),
          [r["orders_placed"], r["accepted"], r["cancel_confirmed"], r["final_open_orders_by_status_callbacks"]])
    check("official ladder: no refusal and no pacing code (only informational codes)", True,
          set(r["error_code_counts"]) <= {"202", "2104", "2107", "2158"} and r["stop_reason"] is None)

    # 2. adapter r6: rung 30/40/50 from the journal
    rows = journal(root, "B-r6")
    rec6 = receipt(root, "B-r6")
    for target in (30, 40, 50):
        ids = {x["coid"] for x in rows if x["event"] == "submit" and x.get("step") == "S4" and x.get("rung") == target}
        cancels = {x["coid"]: x.get("reason") for x in rows if x["event"] == "cancel" and x.get("coid") in ids}
        known = sum(1 for reason in cancels.values() if reason in ("accepted", "s3b_cancel"))
        starts = [x["utc"] for x in rows if x["event"] == "rung_start" and x.get("rung") == target]
        ends = [x["utc"] for x in rows if x["event"] == "rung_end" and x.get("rung") == target]
        from datetime import datetime
        seconds = round(datetime.fromisoformat(ends[0]).timestamp() - datetime.fromisoformat(starts[0]).timestamp())
        item = next(x for x in rec6["ladder"]["rungs"] if x["target_msgs_per_s"] == target)
        got = {
            "counted_msgs_per_s_mean": item["mean_msgs_per_s"],
            "orders_per_min_by_submits": round(len(ids) / seconds * 60),
            "orders_per_min_by_counted_rate": round(item["mean_msgs_per_s"] / 2 * 60),
            "wire_est_refined_msgs_per_s_mean": round((len(ids) + len(cancels) + known) / seconds, 2),
            "wire_est_upper_bound_msgs_per_s_mean": round((len(ids) + 2 * len(cancels)) / seconds, 2),
            "counted_times_1_5": round(item["mean_msgs_per_s"] * 1.5, 2),
        }
        want = headline(doc, f"adapter_r6_rung{target}")
        for key in got:
            close(f"adapter r6 rung {target} {key}", want[key], got[key])
    check("adapter r6 rung 30: orders/min by submits = 900 and by counted rate = 897", [900, 897],
          [headline(doc, "adapter_r6_rung30")["orders_per_min_by_submits"], headline(doc, "adapter_r6_rung30")["orders_per_min_by_counted_rate"]])
    check("adapter r6 completed with no abort, no pacing finding", [None, 0, 0],
          [rec6["abort_reason"], rec6["pacing_error_count"], len(rec6["pacing_findings"])])

    # 3. the 13 two-connection official-client tests
    names = ["E1", "E2", "T1", "T1b", "T2", "T3", "T4", "T6", "T7", "T8", "T9a", "T9b", "T10"]
    table = []
    for name in names:
        a, b = receipt(root, f"P-{name.lower()}-a"), receipt(root, f"P-{name.lower()}-b")
        table.append([name, a["orders_placed"], a["error_code_counts"].get("103", 0), b["orders_placed"], b["error_code_counts"].get("103", 0)])
    check("13 pair tests: orders and [103] counts per connection", headline(doc, "pair_tests_table"), table)
    no_poll = ["E1", "E2", "T1b", "T2", "T3", "T6"]
    check("no-poll tests: 1380 orders, 0 refusals",
          [1380, 0],
          [sum(row[1] + row[3] for row in table if row[0] in no_poll), sum(row[2] + row[4] for row in table if row[0] in no_poll)])
    check("polling tests refused the polling connection only (T4, T7, T9a)", True,
          all(row[2] > 0 and row[4] == 0 for row in table if row[0] in ("T4", "T7", "T9a")))
    check("client-scoped polling and higher-id-only polling did not refuse (T8, T9b)", True,
          all(row[2] == 0 and row[4] == 0 for row in table if row[0] in ("T8", "T9b")))

    # 4. reconciliation
    labels = sorted(p.parent.name for p in (root / "runs").glob("*/journal.jsonl"))
    submits = {label: sum(1 for x in journal(root, label) if x["event"] == "submit") for label in labels}
    total = sum(submits.values())
    missing = [x for x in (root / "journal-submitted-ids.txt.missing").read_text().split() if x]
    official = sum(receipt(root, n)["orders_placed"] for n in ("P-t1", "P-e1-a", "P-e1-b", "P-e2-a", "P-e2-b", "P-r1"))
    rec = doc["reconciliation"]
    check("journal submit events across the adapter runs = 6330", rec["journal_submit_events_total"], total)
    check("journal orders absent at the broker = 38", rec["journal_orders_missing_at_broker"], len(missing))
    check("found at broker by arithmetic = 6330 - 38 = 6292", rec["journal_orders_found_at_broker_by_arithmetic"], total - len(missing))
    check("transcript-derived broker count after the harness runs equals journal minus missing (6292)",
          [rec["broker_completed_orders_after_harness_runs"]["value"], rec["broker_completed_orders_after_harness_runs"]["source"].startswith("transcript-derived")],
          [total - len(missing), True])
    check("official-client orders placed before the second count = 2202", rec["official_client_orders_placed_before_second_count"], official)
    check("the revision block names the three superseded sealed files", sorted(doc["revision"]["supersedes"]), ["generator_sha256", "json_sha256", "verifier_sha256"])
    check("transcript-derived broker count after the official-client runs = 6292 + 2202 = 8494 (8494)",
          [rec["broker_completed_orders_after_official_client_runs"]["value"], rec["broker_completed_orders_after_official_client_runs"]["source"].startswith("transcript-derived")],
          [total - len(missing) + official, True])
    missing_set = set(missing)
    derived = Counter()
    for label in labels:
        events, reasons = {}, {}
        for row in journal(root, label):
            if row.get("coid") in missing_set:
                events.setdefault(row["coid"], set()).add(row["event"])
                if row["event"] == "order_rejected":
                    reasons[row["coid"]] = str(row.get("reason", ""))
        for coid, event_names in events.items():
            if "order_rejected" in event_names:
                text = reasons.get(coid, "")
                derived["refused_by_the_venue_notice_103" if text.startswith("Duplicate order id")
                        else "rejected_cancel_target_not_found_10147" if "that needs to be cancelled is not found" in text
                        else "rejected_other"] += 1
            elif "order_submitted" not in event_names:
                derived["journalled_but_never_reached_the_adapter"] += 1
            else:
                derived["submitted_without_a_venue_answer"] += 1
    check("every missing id is found in exactly one run journal (classified count equals the missing count)", len(missing), sum(derived.values()))
    check("the missing orders by kind, derived from the journals and the venue text", rec["journal_orders_missing_by_kind"], dict(sorted(derived.items())))
    check("headline `reconciliation` equals the five recomputed counters (journal submits, missing, found, official-client orders, broker count after)",
          headline(doc, "reconciliation"), [total, len(missing), total - len(missing), official, total - len(missing) + official])
    pair_orders = sum(receipt(root, f"P-{t.lower()}-{s}")["orders_placed"] for t in ("T1", "T1b", "T2", "T3", "T4", "T6", "T7", "T8", "T9a", "T9b", "T10") for s in ("a", "b"))
    pair_refused = sum(receipt(root, f"P-{t.lower()}-{s}")["refused_103"]["count"] for t in ("T1", "T1b", "T2", "T3", "T4", "T6", "T7", "T8", "T9a", "T9b", "T10") for s in ("a", "b"))
    third = rec["broker_completed_orders_after_pair_tests"]
    check("pair-test orders placed, refused with [103], and expected listed (receipts)",
          [rec["diagnostic_pair_test_orders_placed_after_second_count"], rec["diagnostic_pair_test_orders_refused_103"], rec["diagnostic_pair_test_orders_expected_listed_as_completed"]],
          [pair_orders, pair_refused, pair_orders - pair_refused])
    check("transcript-derived third broker count = second count + listed pair-test orders + 1 probe order (10313)",
          [third["value"], third["source"].startswith("transcript-derived"), third["equals_second_count_plus_listed_pair_orders_plus_probe_order"]],
          [total - len(missing) + official + (pair_orders - pair_refused) + 1, True, True])

    # 4b. whole-run and pair rate estimates (independent code path)
    want = headline(doc, "adapter_whole_run_rate_estimates")
    for label in ("B-r5", "B-r6"):
        got = whole_run_rates(journal(root, label))
        for kind, key in (("counted", "counted"), ("refined", "wire_refined"), ("upper", "wire_upper_bound")):
            check(f"{label} whole-run {key}: max 1 s and best 5 s mean", want[label][key], got[kind])
    want = headline(doc, "adapter_two_connection_combined_rate_estimates")
    for pair in ("m1", "m2", "m3", "m4"):
        got = whole_run_rates(journal(root, f"L0-{pair}") + journal(root, f"L1-{pair}"))
        for kind, key in (("counted", "counted"), ("refined", "wire_refined"), ("upper", "wire_upper_bound")):
            check(f"pair {pair} combined {key}: max 1 s and best 5 s mean", want[pair][key], got[kind])
    check("every two-connection adapter pair stayed at or below 50 wire msgs/s (upper bound, any 1 s)", True,
          all(want[m]["wire_upper_bound"]["max_1s"] <= 50 for m in want))
    check("B-r6 whole run exceeded 50 wire msgs/s (refined best 5 s mean) and B-r5 did not (upper best 5 s mean < 50)", [True, True],
          [headline(doc, "adapter_whole_run_rate_estimates")["B-r6"]["wire_refined"]["best_5s_mean"] > 50,
           headline(doc, "adapter_whole_run_rate_estimates")["B-r5"]["wire_upper_bound"]["best_5s_mean"] < 50])

    # 4c. cancel commands in the vendor logs: a cancel of an accepted order carries a PERM venue id, a cancel of an unaccepted order carries none
    perm_re = re.compile(r'\[CMD\]--> CancelOrder\(.*venue_order_id=Some\("PERM-[0-9]+"\)')
    none_re = re.compile(r"\[CMD\]--> CancelOrder\(.*venue_order_id=None")
    for label in ("B-r5", "B-r6", "L1-m1", "L1-m2", "L1-m4"):
        perm = none = 0
        for line in (root / "runs" / label / "vendor.log").read_text(errors="replace").splitlines():
            if "CancelOrder(" in line:
                perm += 1 if perm_re.search(line) else 0
                none += 1 if none_re.search(line) else 0
        reasons = Counter(x.get("reason") for x in journal(root, label) if x["event"] == "cancel")
        unaccepted = reasons.get("unaccepted_after_1s", 0)
        check(f"{label}: cancel commands with a PERM venue id = journal cancels of accepted orders; without = unaccepted",
              [sum(reasons.values()) - unaccepted, unaccepted], [perm, none])

    # 4d. summary groups of the official-client tests
    by = {}
    for name in names:
        a, b = receipt(root, f"P-{name.lower()}-a"), receipt(root, f"P-{name.lower()}-b")
        by[name] = (a["orders_placed"], a["error_code_counts"].get("103", 0), b["orders_placed"], b["error_code_counts"].get("103", 0))
    groups = doc["official_client_summary"]
    quiet = groups["no_open_order_polling_by_either_connection"]
    check("summary: no polling = E1,E2,T1b,T2,T3,T6: 1380 orders, 0 refusals",
          [quiet["tests"], quiet["orders"], quiet["refusals_103"]],
          [["E1", "E2", "T1b", "T2", "T3", "T6"], sum(by[t][0] + by[t][2] for t in ("E1", "E2", "T1b", "T2", "T3", "T6")), sum(by[t][1] + by[t][3] for t in ("E1", "E2", "T1b", "T2", "T3", "T6"))])
    low = groups["reqAllOpenOrders_polled_by_both_or_by_the_lower_id_connection"]
    polled = ("T4", "T7", "T9a", "T10")
    check("summary: polled by the lower-id connection (T4,T7,T9a,T10): lower side orders/refusals, higher side orders/refusals",
          [low["lower_id_connection"]["orders"], low["lower_id_connection"]["refusals_103"], low["higher_id_connection"]["orders"], low["higher_id_connection"]["refusals_103"]],
          [sum(by[t][0] for t in polled), sum(by[t][1] for t in polled), sum(by[t][2] for t in polled), sum(by[t][3] for t in polled)])
    check("summary: higher-id-only polling (T9b) and client-scoped polling (T8) refused nothing",
          [groups["reqAllOpenOrders_polled_only_by_the_higher_id_connection"]["refusals_103"], groups["client_scoped_reqOpenOrders_polled_by_both"]["refusals_103"]],
          [by["T9b"][1] + by["T9b"][3], by["T8"][1] + by["T8"][3]])
    check("summary: reused client ids with lower order ids (T1): every order refused",
          [groups["reused_client_ids_with_order_ids_below_their_earlier_ids"]["orders"], groups["reused_client_ids_with_order_ids_below_their_earlier_ids"]["refusals_103"]],
          [by["T1"][0] + by["T1"][2], by["T1"][1] + by["T1"][3]])

    # 4e. cited source lines (optional input)
    if len(argv) == 4:
        lines = Path(argv[3]).read_text().splitlines()
        cited = {381: "fn from_venue_order_id", 2387: "async fn handle_cancel_order_async", 2417: "IbOrderSelector::from_venue_order_id(venue_order_id)?",
                 2624: "async fn resolve_ib_order_id", 2637: "client.all_open_orders()"}
        for number, text in cited.items():
            check(f"pinned core.rs line {number} contains {text!r}", True, 0 < number <= len(lines) and text in lines[number - 1])
    else:
        print("SKIP cited source lines (pass the pinned core.rs as the third argument to check them)")

    # 5. document hygiene: no account-shaped token, no order reference shape, no 8+ digit integer outside version stamps
    text = Path(argv[1]).read_text()
    check("no account-code-shaped token in the document", 0, len(re.findall(r"\bDU[A-Z]?[0-9]{4,}\b", text)))
    check("no client order reference shape in the document", 0, len(re.findall(r"ibk-[0-9a-f]{8}-", text)))
    check("no IB permanent order id shape in the document", 0, len(re.findall(r"PERM-[0-9]+", text)))
    check("no dotted-quad address in the document", 0, len(re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", text)))
    big = [m for m in re.findall(r"(?<![0-9a-fA-F.])[0-9]{8,}(?![0-9a-fA-F])", text)]
    check("8+ digit integers appear only inside version/date stamps", [], [b for b in big if not b.startswith("2026101")])
    print(f"{'ALL PASS' if not failures else str(failures) + ' FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
