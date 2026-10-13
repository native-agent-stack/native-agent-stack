#!/usr/bin/env python3
"""Recompute the headline numbers of ibkr-pacing-evidence/1 (revision 4) from the private receipts and compare them with the document.

Revision 4 closes one defect found by the co-op's question on nas#1083: the per-rung wire means of revisions 1 to 3 were (submits + cancels + known) / seconds over the orders a rung
SUBMITTED, wherever their cancels were sent, so a cancel sent in the next rung's window or after the ladder was charged to the submission rung. They are now the wire messages whose journal
time lies inside the rung's own window divided by its recorded seconds. This verifier derives, for EVERY rung of EVERY adapter run (revision 3 checked B-r6 rungs 30, 40 and 50 only), the
two window means, the order-attributed values kept as `*_by_order_rung`, the cancels sent / with a known venue id / before acceptance, and where the first cancel of each rung order was
sent (own window, another rung's window, outside every window); the B-r6 headline entries are compared with the same derivation, and the revision block must say 4.
The order-attributed derivation uses the FIRST cancel row of each order (revision 3's B-r6 code kept the last row's reason in a dict, which differs for the orders that were cancelled twice).

Revision 3 closes three defects found by the co-op's review of revision 2: (1) "every missing id is found in exactly one run journal" compared COUNTS, so one id in no journal and another
in two journals passed; it is now checked id by id (an id with no owner journal, with two or more, or repeated in the list is reported by its position and 8 hex digits of its sha256, never
as text); (2) the per-second maxima were computed over UTC-second buckets; they are recomputed here over sliding windows anchored at a message, in exact integer microseconds, next to
the revision-2 bucket values, for every run, every combined pair and every adapter rung; (3) `peak_open_orders` is recomputed per rung with a rule that closes an order at its first terminal
order event (the document's terminal names are compared with the journals' own vocabulary), where revision 2 did not check it at all.
The two cap statements revision 2 asserted as true (every pair at or below 50 wire msgs/s in any 1 s; B-r5 below 50 as a best 5 s mean) are replaced by comparisons of what the document
says with what is recomputed, because under the sliding definition neither holds; V3-CHANGES.md reports the numbers.

Revision 2 closed two defects found by a second reader in v1: (1) the `reconciliation` headline was never compared with the recomputed counters; (2) the kinds of the 38 missing orders
were a literal, not derived from the journals. v2 derives them from each missing order's journal events and the venue's refusal text.

Standard library only; deterministic; independent code path from the generator (it re-reads the receipts and journals and
re-derives each number with its own arithmetic). Prints one PASS/FAIL line per number and exits 1 if any FAIL.
Numbers that exist only as live broker reads in the session transcript (the two completed-order counts and the reqIds probe)
cannot be recomputed from files: for them the verifier checks only that the document marks them transcript-derived and that
the arithmetic relations between them and the file-derived numbers hold.

usage: python3 verify_ibkr_pacing_evidence.v4.py EVIDENCE.json RUN_ROOT [PIN_CORE_RS]
       PIN_CORE_RS (optional): the file crates/adapters/interactive_brokers/src/execution/core.rs fetched at the pinned commit;
       when given, the cited line numbers are checked against its text.
"""
import hashlib
import json
import re
import sys
from bisect import bisect_left, bisect_right
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
SECOND_US = 1_000_000
WINDOW_PARAMETERS = {"max_1s_window_us": 1_000_000, "best_5s_mean_window_us": 5_000_000, "interval": "start inclusive, end exclusive",
                     "anchor": "message timestamp", "time_unit": "integer microseconds"}
TERMINAL_NAME = re.compile(r"order_(filled|canceled|cancelled|expired|denied|rejected)")
SUPERSEDED_V3 = {"json_sha256": "180dd86e1848b8714ab7e5850d2989eb08217c1a0fb87f3af6493bc9006b8729",
                 "generator_sha256": "933133afe24f128eb4226fb4c50230cb300d5e59ef8e663cc8dac0fb95a9100b",
                 "verifier_sha256": "c8872073cf71990e349ef77293dcef0e434b087e70091b26c6c2749cbce22630"}
SUPERSEDED_V2 = {"json_sha256": "25ef71020a06e1781fac0360aa8b19c564d9d146b65ea3fc6b8cb0ab62ab0c15",
                 "generator_sha256": "f44b595a13cf87b4ad555427000c7937cc62452076f0a3380f13338127147619",
                 "verifier_sha256": "cac1e764f429dc05575dfe8a692e74d4bcc04a8906e174e9e7b0178cf61494e3"}
SUPERSEDED_V1 = {"json_sha256": "b492f42d335370e22f4349bf43db54f1adf4c77921b36a28300159b08c8e11fa",
                 "generator_sha256": "56463b2622501446a9a1640c6d3065920dbd449a622457ea61f392ce6166c5a1",
                 "verifier_sha256": "0e9fb1376a59e34cf1e3b6ba2fea30d89aad5e09db28de0b4d59792a41207468"}

failures = 0
checks = 0


def check(name, expected, got):
    global failures, checks
    ok = expected == got
    checks += 1
    failures += 0 if ok else 1
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": document {expected!r} vs recomputed {got!r}"))


def close(name, expected, got, tol=0.011):
    global failures, checks
    ok = expected is not None and got is not None and abs(expected - got) <= tol
    checks += 1
    failures += 0 if ok else 1
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": document {expected!r} vs recomputed {got!r}"))


def receipt(root, label):
    return json.loads((root / "runs" / label / "receipt.json").read_text())


def journal(root, label):
    return [json.loads(line) for line in (root / "runs" / label / "journal.jsonl").read_text().splitlines()]


def headline(doc, ident):
    return next(h["value"] for h in doc["headline_numbers"] if h["id"] == ident)


def us_of(row):
    """Exact integer microseconds since the Unix epoch of a journal row's `utc` (never floating-point seconds)."""
    return (datetime.fromisoformat(row["utc"]) - EPOCH) // timedelta(microseconds=1)


def message_events(rows):
    """{kind: [(microseconds, weight)]}: counted = submit + cancel; refined adds one scan per cancel of an accepted order;
    upper adds one per cancel. The hidden scan carries its cancel row's timestamp (the journal does not timestamp it)."""
    events = {"counted": [], "refined": [], "upper": []}
    for row in rows:
        if row["event"] == "submit":
            t = us_of(row)
            for series in events.values():
                series.append((t, 1))
        elif row["event"] == "cancel":
            t = us_of(row)
            events["counted"].append((t, 1))
            events["upper"].append((t, 2))
            events["refined"].append((t, 1 if row.get("reason") == "unaccepted_after_1s" else 2))
    return events


def sliding_best(events, width):
    """Largest total weight inside any half-open [t, t + width) whose start t is an event time: prefix sums and bisect over the sorted events
    (a different method from the generator's two pointers)."""
    events = sorted(events)
    times = [t for t, _ in events]
    prefix = [0]
    for _, weight in events:
        prefix.append(prefix[-1] + weight)
    best = 0
    for t in times:
        best = max(best, prefix[bisect_left(times, t + width)] - prefix[bisect_left(times, t)])
    return best


def whole_run_rates(rows):
    """Independent recomputation of a rate block. Returns {kind: {max_1s, best_5s_mean}} over sliding windows anchored at a message,
    plus the revision-2 values over UTC-second buckets as max_1s_utc_buckets / best_5s_mean_utc_buckets."""
    out = {}
    for name, events in message_events(rows).items():
        buckets = Counter()
        for t, weight in events:
            buckets[t // SECOND_US] += weight
        best_bucket = max((sum(buckets.get(s0 + k, 0) for k in range(5)) / 5 for s0 in buckets), default=0.0)
        out[name] = {"max_1s": sliding_best(events, SECOND_US), "best_5s_mean": round(sliding_best(events, 5 * SECOND_US) / 5, 2),
                     "max_1s_utc_buckets": max(buckets.values(), default=0), "best_5s_mean_utc_buckets": round(best_bucket, 2)}
    return out


def owner_map(missing, rows_by_label):
    """{missing id: sorted run labels whose journal holds at least one row of that id}."""
    wanted = set(missing)
    owners = {coid: [] for coid in wanted}
    for label, rows in rows_by_label.items():
        for coid in {row.get("coid") for row in rows} & wanted:
            owners[coid].append(label)
    return {coid: sorted(labels) for coid, labels in owners.items()}


def ownership_problems(missing, owners):
    """One line per position of the missing list whose id has no owner journal, two or more, or repeats an earlier position.
    The id itself is never printed: only its 0-based position, 8 hex digits of its sha256 and the owner run labels."""
    problems, seen = [], set()
    for position, coid in enumerate(missing):
        digest = hashlib.sha256(coid.encode()).hexdigest()[:8]
        labels = owners.get(coid, [])
        if coid in seen:
            problems.append(f"position {position} (sha256 {digest}) repeats an earlier position of the list")
        seen.add(coid)
        if len(labels) != 1:
            problems.append(f"position {position} (sha256 {digest}) has {len(labels)} owner journals {labels}")
    return problems


def ladder_entries(rec, rows):
    """For each ladder rung of the receipt that placed orders: (target, window start in microseconds, seconds, the receipt's per-second slots).
    Rung j starts at the S4 step_enter row's timestamp plus j x the frozen rung_s and lasts the seconds the receipt recorded."""
    rung_s = rec["frozen"]["s4"]["rung_s"]
    enter = next(us_of(row) for row in rows if row["event"] == "step_enter" and row.get("step") == "S4")
    return [(rung["target_msgs_per_s"], enter + index * rung_s * SECOND_US, len(rung["per_second_msgs"]), rung["per_second_msgs"])
            for index, rung in enumerate(rec["ladder"]["rungs"]) if rung.get("submits")]


def rung_table(rec, rows):
    """Every ladder rung of the receipt that recorded seconds: {target: (index, window start, window stop in microseconds, the receipt's per-second slots, the receipt's submits)}.
    Rung j starts at the S4 step_enter row's timestamp plus j x the frozen rung_s and lasts the seconds the receipt recorded; a rung with no recorded second has no window."""
    rung_s = rec["frozen"]["s4"]["rung_s"]
    enter = next(us_of(row) for row in rows if row["event"] == "step_enter" and row.get("step") == "S4")
    return {rung["target_msgs_per_s"]: (index, enter + index * rung_s * SECOND_US, enter + (index * rung_s + len(rung["per_second_msgs"])) * SECOND_US,
                                        rung["per_second_msgs"], rung.get("submits"))
            for index, rung in enumerate(rec["ladder"]["rungs"]) if rung["per_second_msgs"]}


def rung_peaks(rows, terminal):
    """Peak open step-S4 orders per rung target. An order is open from its submit row to its first terminal event. With keys (microseconds, +1 submit / -1 terminal event,
    rung), the count after an event e is (starts with key <= key_e) - (terminal events with key <= key_e), so terminal events sort before submits at equal times;
    a rung's peak is the largest count at any event of its own orders."""
    starts, first_end = {}, {}
    for row in rows:
        if row["event"] == "submit" and row.get("step") == "S4":
            starts[row["coid"]] = (us_of(row), 1, row.get("rung"))
    for row in rows:
        coid = row.get("coid")
        if row["event"] in terminal and coid in starts:
            t = us_of(row)
            first_end[coid] = min(t, first_end.get(coid, t))
    start_keys = sorted(starts.values())
    end_keys = sorted((first_end[coid], -1, starts[coid][2]) for coid in first_end)
    peak = {}
    for key in start_keys + end_keys:
        live = bisect_right(start_keys, key) - bisect_right(end_keys, key)
        peak[key[2]] = max(peak.get(key[2], 0), live)
    return peak


def main(argv):
    if len(argv) not in (3, 4):
        sys.stderr.write(__doc__)
        return 2
    doc = json.loads(Path(argv[1]).read_text())
    root = Path(argv[2])
    if doc.get("revision", {}).get("number") != 4:
        print(f"FAIL the document is revision {doc.get('revision', {}).get('number')!r}; this verifier checks revision 4 (use the verifier named for the document's revision)")
        return 1

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

    # 2. adapter r6: rung 30/40/50 from the journal. The two wire means are the messages inside the rung's own window over its recorded seconds (revision 4);
    #    the *_by_order_rung values keep the order attribution of revisions 1 to 3 (the first cancel row of each order the rung submitted, wherever it was sent).
    rows = journal(root, "B-r6")
    rec6 = receipt(root, "B-r6")
    table6 = rung_table(rec6, rows)
    for target in (30, 40, 50):
        ids = {x["coid"] for x in rows if x["event"] == "submit" and x.get("step") == "S4" and x.get("rung") == target}
        first_cancel = {}
        for x in rows:
            if x["event"] == "cancel" and x.get("coid") in ids and x["coid"] not in first_cancel:
                first_cancel[x["coid"]] = x.get("reason")
        known = sum(1 for reason in first_cancel.values() if reason != "unaccepted_after_1s")
        starts = [x["utc"] for x in rows if x["event"] == "rung_start" and x.get("rung") == target]
        ends = [x["utc"] for x in rows if x["event"] == "rung_end" and x.get("rung") == target]
        from datetime import datetime
        seconds = round(datetime.fromisoformat(ends[0]).timestamp() - datetime.fromisoformat(starts[0]).timestamp())
        item = next(x for x in rec6["ladder"]["rungs"] if x["target_msgs_per_s"] == target)
        _, w_start, w_stop, w_per, _ = table6[target]
        w_events = message_events([x for x in rows if x["event"] in ("submit", "cancel") and x.get("step") == "S4" and w_start <= us_of(x) < w_stop])
        got = {
            "counted_msgs_per_s_mean": item["mean_msgs_per_s"],
            "orders_per_min_by_submits": round(len(ids) / seconds * 60),
            "orders_per_min_by_counted_rate": round(item["mean_msgs_per_s"] / 2 * 60),
            "wire_est_refined_msgs_per_s_mean": round(sum(w for _, w in w_events["refined"]) / len(w_per), 2),
            "wire_est_upper_bound_msgs_per_s_mean": round(sum(w for _, w in w_events["upper"]) / len(w_per), 2),
            "wire_est_refined_msgs_per_s_mean_by_order_rung": round((len(ids) + len(first_cancel) + known) / len(w_per), 2),
            "wire_est_upper_bound_msgs_per_s_mean_by_order_rung": round((len(ids) + 2 * len(first_cancel)) / len(w_per), 2),
            "counted_times_1_5": round(item["mean_msgs_per_s"] * 1.5, 2),
        }
        want = headline(doc, f"adapter_r6_rung{target}")
        for key in got:
            if key.startswith("wire_est"):
                check(f"adapter r6 rung {target} {key} (exact)", want.get(key), got[key])
            else:
                close(f"adapter r6 rung {target} {key}", want.get(key), got[key])
    above_50 = [f"rung {t} {kind}" for t in (40, 50) for kind in ("refined", "upper_bound")
                if headline(doc, f"adapter_r6_rung{t}")[f"wire_est_{kind}_msgs_per_s_mean"] > 50]
    print(f"INFO B-r6 rung 40 and rung 50 wire means above 50 msgs/s: {len(above_50)} of 4 ({'; '.join(above_50)})")
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
    rows_by_label = {label: journal(root, label) for label in labels}
    derived = Counter()
    for label in labels:
        events, reasons = {}, {}
        for row in rows_by_label[label]:
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
    owners = owner_map(missing, rows_by_label)
    check("every missing id has exactly one owner run journal (an id with none, with two or more, or repeated in the list is listed by position and sha256 prefix)",
          [], ownership_problems(missing, owners))
    owner_histogram = Counter(min(len(owners.get(coid, [])), 2) for coid in missing_set)
    check("the missing ids by number of owner journals (0, 1, 2 or more)", rec["journal_orders_missing_by_number_of_owner_journals"],
          {"0": owner_histogram[0], "1": owner_histogram[1], "2_or_more": owner_histogram[2]})
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

    # 4b. whole-run and pair rate estimates (independent code path): sliding maxima next to the revision-2 UTC-bucket values
    check("the window convention of the document equals the verifier's (1 s and 5 s windows, start inclusive and end exclusive, anchored at a message, integer microseconds)",
          WINDOW_PARAMETERS, doc["facts"]["rate_window_conventions"]["parameters"])
    kind_keys = (("counted", "counted_msgs_per_s"), ("refined", "wire_est_refined_msgs_per_s"), ("upper", "wire_est_upper_bound_msgs_per_s"))
    headline_keys = (("counted", "counted"), ("refined", "wire_refined"), ("upper", "wire_upper_bound"))
    want = headline(doc, "adapter_whole_run_rate_estimates")
    got_runs = {}
    for label in ("B-r5", "B-r6"):
        got = got_runs[label] = whole_run_rates(rows_by_label[label])
        for kind, key in headline_keys:
            check(f"{label} whole-run {key}: sliding max 1 s and best 5 s mean, and the UTC-bucket values", want[label][key], got[kind])
    want_pairs = headline(doc, "adapter_two_connection_combined_rate_estimates")
    got_pairs = {}
    for pair in ("m1", "m2", "m3", "m4"):
        got = got_pairs[pair] = whole_run_rates(rows_by_label[f"L0-{pair}"] + rows_by_label[f"L1-{pair}"])
        for kind, key in headline_keys:
            check(f"pair {pair} combined {key}: sliding max 1 s and best 5 s mean, and the UTC-bucket values", want_pairs[pair][key], got[kind])
    every_run = (list(doc["adapter_phase_a"]) + list(doc["adapter_single_connection_ladders"])
                 + [run for pair in doc["adapter_two_connection_pairs"] for run in pair["connections"].values()])
    below = []
    for run in every_run:
        got = whole_run_rates(rows_by_label[run["label"]])
        check(f"{run['label']} rate_estimates_whole_run (counted, refined, upper bound: sliding and UTC-bucket values)", run["rate_estimates_whole_run"],
              {key: got[kind] for kind, key in kind_keys})
        below += [f"{run['label']}/{kind}" for kind, _ in kind_keys if got[kind]["max_1s"] < got[kind]["max_1s_utc_buckets"]
                  or got[kind]["best_5s_mean"] < got[kind]["best_5s_mean_utc_buckets"]]
    for pair in doc["adapter_two_connection_pairs"]:
        got = whole_run_rates(rows_by_label[f"L0-{pair['label']}"] + rows_by_label[f"L1-{pair['label']}"])
        check(f"pair {pair['label']} combined_rate_estimates (sliding and UTC-bucket values)", pair["combined_rate_estimates"], {key: got[kind] for kind, key in kind_keys})
    check("a sliding maximum is never below its UTC-bucket value, in any recomputed run block", [], below)
    # The 50 msgs/s cap relation is a statement about the numbers, so it is compared with what the document says, not asserted: the revision-2 verifier asserted
    # "pairs at or below 50 (upper bound, any 1 s)" and "B-r5 below 50 as a best 5 s mean"; under the sliding definition neither holds (see V3-CHANGES.md).
    over_doc = {m: sorted(k for k, _ in headline_keys if want_pairs[m][dict(headline_keys)[k]]["max_1s"] > 50) for m in want_pairs}
    over_got = {m: sorted(k for k, _ in headline_keys if got_pairs[m][k]["max_1s"] > 50) for m in got_pairs}
    check("two-connection pairs, series above 50 msgs/s in some sliding 1 s window: document numbers vs recomputed", over_doc, over_got)
    over5_doc = {m: sorted(k for k, _ in headline_keys if want[m][dict(headline_keys)[k]]["best_5s_mean"] > 50) for m in want}
    over5_got = {m: sorted(k for k, _ in headline_keys if got_runs[m][k]["best_5s_mean"] > 50) for m in got_runs}
    check("B-r5, B-r6, series whose best sliding 5 s mean exceeded 50 msgs/s: document numbers vs recomputed", over5_doc, over5_got)
    print("INFO pairs with a series above 50 msgs/s in some sliding 1 s window:", {m: v for m, v in over_got.items() if v})
    print("INFO whole runs with a series whose best sliding 5 s mean exceeded 50 msgs/s:", {m: v for m, v in over5_got.items() if v})

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

    # 4f. per-rung sliding windows, and the receipts' per-second slots replayed from the journal (which anchors the rung windows)
    replay_rungs = replay_equal = replay_largest = 0
    for run in every_run:
        if "rungs" not in run:
            continue
        label, rows = run["label"], rows_by_label[run["label"]]
        entries = ladder_entries(receipt(root, label), rows)
        want_rungs = {item["target_msgs_per_s"]: item for item in run["rungs"]}
        check(f"{label}: ladder rungs that placed orders = the document's rungs", sorted(target for target, _, _, _ in entries), sorted(want_rungs))
        got_sliding, got_replay = {}, {}
        for target, start, seconds, per in entries:
            window = [r for r in rows if r["event"] in ("submit", "cancel") and r.get("step") == "S4" and start <= us_of(r) < start + seconds * SECOND_US]
            events = message_events(window)
            got_sliding[target] = {"counted": sliding_best(events["counted"], SECOND_US), "wire_est_refined": sliding_best(events["refined"], SECOND_US),
                                   "wire_est_upper_bound": sliding_best(events["upper"], SECOND_US)}
            slots = Counter((us_of(r) - start) // SECOND_US for r in window)
            difference = max(abs(slots.get(k, 0) - per[k]) for k in range(seconds))
            got_replay[target] = {"equal": difference == 0, "max_abs_slot_difference": difference}
            replay_rungs += 1
            replay_equal += 1 if difference == 0 else 0
            replay_largest = max(replay_largest, difference)
        check(f"{label}: max_1s_sliding_in_rung_window per rung (counted, refined, upper bound)",
              {t: want_rungs[t]["max_1s_sliding_in_rung_window"] for t in sorted(want_rungs)}, got_sliding)
        check(f"{label}: the receipt's per-second slots replayed from the journal, per rung",
              {t: want_rungs[t]["receipt_slots_replayed_from_journal"] for t in sorted(want_rungs)}, got_replay)
        check(f"{label}: the receipt's own per-second maximum is not above the sliding maximum, per rung", [],
              [target for target, _, _, per in entries if max(per) > got_sliding[target]["counted"]])
    replay_doc = doc["facts"]["rate_window_conventions"]["rung_window_replay"]
    check("replay of the receipts' per-second slots from the journals: rungs, rungs equal, largest slot difference",
          [replay_doc["rungs"], replay_doc["slots_equal_to_the_receipts_per_second_counters"], replay_doc["largest_slot_difference_in_messages"]],
          [replay_rungs, replay_equal, replay_largest])

    # 4g. peak_open_orders: the terminal names from the journals' own vocabulary, then the per-rung peaks (the revision-2 verifier did not check them)
    vocabulary = sorted({row["event"] for rows in rows_by_label.values() for row in rows})
    terminal = sorted(name for name in vocabulary if TERMINAL_NAME.fullmatch(name))
    definition = doc["facts"]["peak_open_orders_definition"]
    check("peak_open_orders: terminal event names = the journals' event names of the form order_(filled|canceled|cancelled|expired|denied|rejected)",
          definition["terminal_event_names"], terminal)
    check("peak_open_orders: the document lists the journals' whole event vocabulary", definition["journal_event_vocabulary"], vocabulary)
    check("peak_open_orders: order events that are not terminal (a refused cancel and a pending cancel among them)",
          definition["order_event_names_not_terminal"], sorted(name for name in vocabulary if name.startswith("order_") and name not in terminal))
    check("peak_open_orders: every ladder order has quantity 1, so an order_filled is a complete fill", definition["ladder_order_quantities"],
          sorted({row.get("qty") for rows in rows_by_label.values() for row in rows if row["event"] == "submit" and row.get("step") == "S4"}))
    moved = []
    for run in every_run:
        if "rungs" in run:
            peaks = rung_peaks(rows_by_label[run["label"]], terminal)
            check(f"{run['label']}: peak_open_orders per rung (an order is open from its submit row to its first terminal order event)",
                  {item["target_msgs_per_s"]: item["peak_open_orders"] for item in run["rungs"]},
                  {item["target_msgs_per_s"]: peaks.get(item["target_msgs_per_s"]) for item in run["rungs"]})
            old_rule = rung_peaks(rows_by_label[run["label"]], {"order_canceled"})
            moved += [f"{run['label']}/{target}: {old_rule.get(target)} -> {peaks.get(target)}" for target in sorted(peaks) if old_rule.get(target) != peaks[target]]
    print("INFO rungs whose peak differs between the revision-2 rule (only order_canceled closes an order) and the revision-3 rule:", moved or "none")

    # 4h. per-rung wire means over the rung's own window, the order-attributed values, and where the first cancel of each of the rung's orders was sent (revision 4)
    for run in every_run:
        if "rungs" not in run:
            continue
        label, rows = run["label"], rows_by_label[run["label"]]
        table = rung_table(receipt(root, label), rows)
        want_rungs = {item["target_msgs_per_s"]: item for item in run["rungs"]}
        submit_rung, first_cancel = {}, {}
        for row in rows:
            coid = row.get("coid")
            if row["event"] == "submit" and row.get("step") == "S4":
                submit_rung[coid] = row.get("rung")
            elif row["event"] == "cancel" and coid in submit_rung and coid not in first_cancel:
                first_cancel[coid] = row
        got_means, got_order, got_class = {}, {}, {}
        for target in sorted(want_rungs):
            index, start, stop, per, _ = table[target]
            seconds = len(per)
            weights = message_events([r for r in rows if r["event"] in ("submit", "cancel") and r.get("step") == "S4" and start <= us_of(r) < stop])
            got_means[target] = [round(sum(w for _, w in weights["refined"]) / seconds, 2), round(sum(w for _, w in weights["upper"]) / seconds, 2)]
            ids = [coid for coid, rung_target in submit_rung.items() if rung_target == target]
            sent = [first_cancel[coid] for coid in ids if coid in first_cancel]
            known = sum(1 for r in sent if r.get("reason") != "unaccepted_after_1s")
            got_order[target] = [round((len(ids) + len(sent) + known) / seconds, 2), round((len(ids) + 2 * len(sent)) / seconds, 2), len(sent), known, len(sent) - known]
            others = [(lo, hi) for j, lo, hi, _, _ in table.values() if j != index]
            own = sum(1 for r in sent if start <= us_of(r) < stop)
            other = sum(1 for r in sent if not start <= us_of(r) < stop and any(lo <= us_of(r) < hi for lo, hi in others))
            outside = sum(1 for r in sent if not start <= us_of(r) < stop and not any(lo <= us_of(r) < hi for lo, hi in others))
            got_class[target] = [own, other, outside]
        check(f"{label}: per-rung wire means over the rung's own window (refined, upper bound)",
              {t: [want_rungs[t]["wire_est_refined_msgs_per_s_mean"], want_rungs[t]["wire_est_upper_bound_msgs_per_s_mean"]] for t in sorted(want_rungs)}, got_means)
        check(f"{label}: order-attributed means and the cancels sent / with a known venue id / before acceptance, per rung",
              {t: [want_rungs[t]["wire_est_refined_msgs_per_s_mean_by_order_rung"], want_rungs[t]["wire_est_upper_bound_msgs_per_s_mean_by_order_rung"], want_rungs[t]["cancels_sent"],
                   want_rungs[t]["cancels_with_known_venue_id"], want_rungs[t]["cancels_before_acceptance"]] for t in sorted(want_rungs)}, got_order)
        check(f"{label}: where the first cancel of each rung order was sent (own window, another rung's window, outside every window), per rung",
              {t: [want_rungs[t]["cancels_sent_in_own_window"], want_rungs[t]["cancels_sent_in_other_rung_window"], want_rungs[t]["cancels_sent_outside_rung_windows"]]
               for t in sorted(want_rungs)}, got_class)
        check(f"{label}: the three cancel classifications sum to cancels_sent, per rung", [],
              [t for t in sorted(want_rungs) if sum(got_class[t]) != got_order[t][2]])
    check("revision 4: the block names the revision-3 files it supersedes by hash and the revisions 1 and 2 before them",
          [doc["revision"]["number"], doc["revision"]["supersedes"], doc["revision"]["earlier_revisions"]], [4, SUPERSEDED_V3, {"1": SUPERSEDED_V1, "2": SUPERSEDED_V2}])

    # 5. document hygiene: no account-shaped token, no order reference shape, no 8+ digit integer outside version stamps
    text = Path(argv[1]).read_text()
    check("no account-code-shaped token in the document", 0, len(re.findall(r"\bDU[A-Z]?[0-9]{4,}\b", text)))
    check("no client order reference shape in the document", 0, len(re.findall(r"ibk-[0-9a-f]{8}-", text)))
    check("no IB permanent order id shape in the document", 0, len(re.findall(r"PERM-[0-9]+", text)))
    check("no dotted-quad address in the document", 0, len(re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", text)))
    big = [m for m in re.findall(r"(?<![0-9a-fA-F.])[0-9]{8,}(?![0-9a-fA-F])", text)]
    check("8+ digit integers appear only inside version/date stamps", [], [b for b in big if not b.startswith("2026101")])
    print(f"{checks} checks, {checks - failures} passed, {failures} failed")
    print(f"{'ALL PASS' if not failures else str(failures) + ' FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
