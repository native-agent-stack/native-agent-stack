# V4-CHANGES: IBKR pacing evidence, revision 4

A correction of one defect in the per-rung wire means, present in revisions 1, 2 and 3 (their 40 rung values are identical). It adds no measurement and no input.
Writing began 2026-10-13T21:40:24Z (tool clock), by the trading-cc builder.

## Files and what stays sealed

| file | sha256 |
|---|---|
| `generate_ibkr_pacing_evidence.v4.py` | `d14fb1e81fabe1055d4e2a155f2fe76fbe0401dbe7bc30234ca8558d0e308f68` |
| `verify_ibkr_pacing_evidence.v4.py` | `b72e5a341915d3f1d863f8aaef9de953c690efd273ee00f1d322d1112eca7913` |
| `ibkr-pacing-evidence-20261013.v4.json` | `841ec5965caa6fa6d1b7d7ed5ddfa34af8ca38ba26028bf6226847fcad368900` |
| `V4-CHANGES.md` | this file (no digest of itself) |

Revision 3 stays sealed and unchanged: generator `933133afe24f128eb4226fb4c50230cb300d5e59ef8e663cc8dac0fb95a9100b`, verifier `c8872073cf71990e349ef77293dcef0e434b087e70091b26c6c2749cbce22630`,
JSON `180dd86e1848b8714ab7e5850d2989eb08217c1a0fb87f3af6493bc9006b8729`, `V3-CHANGES.md` `edbb14013d15b8e9164685e024ed68b02ec676f8ea3d7f83e6591f3a843cc855`.
Revision 2 stays sealed: generator `f44b595a13cf87b4ad555427000c7937cc62452076f0a3380f13338127147619`, verifier `cac1e764f429dc05575dfe8a692e74d4bcc04a8906e174e9e7b0178cf61494e3`,
JSON `25ef71020a06e1781fac0360aa8b19c564d9d146b65ea3fc6b8cb0ab62ab0c15`. Revision 1 stays sealed: generator `56463b2622501446a9a1640c6d3065920dbd449a622457ea61f392ce6166c5a1`,
verifier `0e9fb1376a59e34cf1e3b6ba2fea30d89aad5e09db28de0b4d59792a41207468`, JSON `b492f42d335370e22f4349bf43db54f1adf4c77921b36a28300159b08c8e11fa`.
README and ADDENDUM-01..04 are not edited; where they are out of date, this file and `V3-CHANGES.md` are the correction. To reproduce revision 4:

```
python3 -I -B generate_ibkr_pacing_evidence.v4.py RUN_ROOT > check.json && diff check.json ibkr-pacing-evidence-20261013.v4.json
python3 -I -B verify_ibkr_pacing_evidence.v4.py ibkr-pacing-evidence-20261013.v4.json RUN_ROOT [PINNED_CORE_RS]
```

Inputs are the same private run root every revision read. The revision-3 generator re-run on it prints the sealed revision-3 JSON byte for byte (sha256 `180dd86e...`), so the inputs are intact.

## 1. The defect, reproduced against the sealed revision-3 files before any fix

Raised as a co-op question on nas#1083. In the revision-3 generator, `ladder_rungs()` publishes for each adapter rung

- `wire_est_refined_msgs_per_s_mean = (submits + cancels + known) / seconds`
- `wire_est_upper_bound_msgs_per_s_mean = (submits + 2 x cancels) / seconds`

where `submits` is the receipt's count for the rung, `cancels` and `known` count the FIRST cancel row of each order the rung SUBMITTED wherever that cancel was sent, and `seconds` is the rung's own
recorded seconds. So a cancel sent in the next rung's window, or after the ladder, is charged to the submission rung over the submission rung's seconds although it occupies another rung's window (or
none); the cancels of the previous rung's orders that are sent inside this rung's window are charged to the previous rung; and for a rung stopped part-way the submits placed after its recorded
seconds are counted over the recorded seconds only. The per-message series (`max_1s_sliding_in_rung_window`, the whole-run and combined rate blocks) and the official-client figures are window or
message based and are NOT affected.

Synthetic cases (invented ids `syn-N`, invented times, a 2 s rung; none comes from a run), the same lines through the sealed revision-3 generator and the revision-4 generator. Values are
`refined / upper bound` per rung:

| case | what the lines say | revision 3 | revision 4 | cancels of the rung's orders: own / other rung's window / outside |
|---|---|---|---|---|
| A | rung 10 `[0, 2)` places 4 orders, the last two cancelled at 2.2 s and 2.5 s, inside rung 20's window `[2, 4)`; rung 20 places 4 and cancels all 4 inside its window | rung 10 6.0 / 6.0; rung 20 6.0 / 6.0 | rung 10 4.0 / 4.0; rung 20 8.0 / 8.0 | rung 10: 2 / 2 / 0; rung 20: 4 / 0 / 0 |
| B | one rung places 4 orders, the last two cancelled at 2.4 s and 2.8 s, after the ladder | 6.0 / 6.0 | 4.0 / 4.0 | 2 / 0 / 2 |
| C | an aborted rung: 6 submits recorded but 2 evaluated seconds; two orders placed after them, all cancelled | 9.0 / 9.0 | 6.0 / 6.0 | 4 / 0 / 2 |
| D control | every cancel inside the own window, two of them of unaccepted orders (no hidden request) | 5.0 / 6.0 | 5.0 / 6.0 | 4 / 0 / 0 |
| E | an order has a second cancel row (a retry) inside the window: a message the order attribution never counted | 6.0 / 6.0 | 7.0 / 7.0 | 4 / 0 / 0 |
| F | a rung with orders and no recorded second (no window) | null means | stops with an error | n/a |

In every case the revision-4 order-attributed values (kept under `*_by_order_rung`) equal the revision-3 values. In A the two rungs together hold 24 wire messages under both revisions (every cancel
falls inside some window), but revision 3 charges each rung 12 messages (6.0 per second) where the windows hold 8 (rung 10) and 16 (rung 20); in B and C revision 3 charges messages no window contains.

On the retained run the same arithmetic is visible in B-r6 (section 3): rung 40's 382 cancels include 16 sent in rung 50's window, rung 50's 377 include 17 sent after the ladder, and rung 30's window
holds 6 cancels of rung 20's orders.

## 2. What revision 4 does

Per-rung convention (also in the JSON under `facts.rate_window_conventions.rung_wire_means`): `wire_est_refined_msgs_per_s_mean` and `wire_est_upper_bound_msgs_per_s_mean` of an adapter rung, and of the
`adapter_r6_rung30/40/50` headline entries, are the number of messages of that series whose journal time lies inside the rung's own window `[S4 step_enter + index x rung_s, + the rung's recorded
seconds)`, divided by those seconds and rounded to 2 decimals: the same window rows and series as `max_1s_sliding_in_rung_window` (counted submit and cancel rows, plus the hidden `reqAllOpenOrders` per
cancel, refined only for a cancel of an accepted order). The revision-1-to-3 values are kept as `wire_est_refined_msgs_per_s_mean_by_order_rung` and
`wire_est_upper_bound_msgs_per_s_mean_by_order_rung`. `cancels_sent`, `cancels_with_known_venue_id` and `cancels_before_acceptance` stay order-attributed (the first cancel row of each order the rung
submitted). Three new fields, `cancels_sent_in_own_window`, `cancels_sent_in_other_rung_window` and `cancels_sent_outside_rung_windows`, classify those same first cancel rows by journal time against
every rung window of the run and sum to `cancels_sent`.

Generator (`diff -u` against revision 3: 11 hunks; everything outside the items below is byte-identical):
- Docstring and usage line; the `revision` block (number 4, `supersedes` names the revision-3 files, `earlier_revisions` 1 and 2, a `reason` paragraph, `changes`); one caveat.
- `ladder_rungs()`: a `cancel_us` map of the first cancel row's time; the windows of every rung that recorded seconds; the guard that stops with an error for a rung with orders and no window (revision 3
  fell back to null); the window means from the SAME `window` rows and `message_times(window)` series already used for `max_1s_sliding_in_rung_window`; the order-attributed values under their new
  names; the three cancel classifications (the generator stops if they do not sum to `cancels_sent`).
- `headline()`: `adapter_r6_rung30/40/50` carry the window means under the old names and the two `*_by_order_rung` values.
- `rate_window_conventions()`: `field_changes` is renamed `field_changes_in_revision_3`, `field_changes_in_revision_4` and `rung_wire_means` are added; the official-client peak note says "unchanged in
  revisions 3 and 4".

Verifier (`diff -u` against revision 3: 7 hunks; everything outside the items below is byte-identical):
- Docstring, usage, the revision-3 digests as constants, the early FAIL and the final revision check now require revision 4 (`supersedes` = revision 3, earlier = 1 and 2).
- New `rung_table()`: every rung that recorded seconds with its window.
- Section 2 (B-r6 rungs 30, 40, 50): the two wire means are derived from the window rows (summed weights over the recorded seconds, exact comparison), the two `*_by_order_rung` values from the first cancel row
  of each order. Revision 3's section 2 kept the LAST cancel row's reason in a dict and used a known-venue-id rule different from the generator's; the two differ for an order cancelled twice, which
  exists in B-r2 (2 orders), B-r5 (3), L1-m1 (2) and L1-m3 (4) but not in B-r6, so revision 3's B-r6 check was unaffected and generalising it would have failed those four runs. An INFO line prints how
  many of the four B-r6 rung-40/50 means are above 50.
- New section 4h, for EVERY rung of EVERY adapter run (revision 3 checked B-r6 rungs 30, 40 and 50 only): the two window means; the order-attributed means with `cancels_sent`,
  `cancels_with_known_venue_id` and `cancels_before_acceptance`; the three cancel classifications, recomputed from the journals and required to sum to `cancels_sent`.

## 3. Effect on the published numbers

A key-level diff of the revision-4 JSON against the sealed revision-3 JSON lists 0 unexplained paths:

| change | paths |
|---|---|
| per-rung `wire_est_refined_msgs_per_s_mean` / `wire_est_upper_bound_msgs_per_s_mean`, same name, window meaning | 63 changed of 80 (40 rungs x 2); 17 equal |
| `wire_est_*_by_order_rung`, the revision-3 values under a new name | 80 (equal to the revision-3 value in all 40 rungs) |
| `cancels_sent_in_own_window`, `cancels_sent_in_other_rung_window`, `cancels_sent_outside_rung_windows` | 120 (40 rungs) |
| headline `adapter_r6_rung30/40/50`: the two means changed, the two `*_by_order_rung` values added | 6 changed, 6 added |
| `facts.rate_window_conventions`: `field_changes` renamed, `field_changes_in_revision_4` and `rung_wire_means` added | 1 removed, 3 added |
| official-client peak note (text only), `revision` block (6 changed, 2 added), `caveats` (one entry added) | 1, 8, 1 |

No other value moves: every sliding maximum, whole-run and combined rate, peak, latency, count and test result is byte-identical to revision 3.

The three cited rungs (B-r6; the wire means in msgs/s; "messages" is the numerator before dividing by 20 s):

| rung | refined, revision 3 -> 4 | upper bound, revision 3 -> 4 | numerator, refined, revision 3 -> 4 | cancels of the rung's orders: own / other rung's window / outside |
|---|---|---|---|---|
| 30 | 44.95 -> **44.75** | 45.0 -> **44.8** | 300 + 300 + 299 = 899 -> 895 | 292 / 8 / 0 (of 300) |
| 40 | 51.65 -> **51.3** | 57.3 -> **56.5** | 382 + 382 + 269 = 1,033 -> 1,026 | 366 / 16 / 0 (of 382) |
| 50 | 49.35 -> **49.05** | 56.55 -> **56.45** | 377 + 377 + 233 = 987 -> 981 | 360 / 0 / 17 (of 377) |

Counted from the journal, the windows hold: rung 30, 300 submits and 298 cancel rows (292 of its own orders, 6 of rung 20's) plus 297 hidden requests for the cancels of accepted orders, 895 in all
(upper bound 896); rung 40, 382 submits and 374 cancel rows (366 of its own orders, 8 of rung 30's) plus 270 hidden requests, 1,026 (upper bound 1,130); rung 50, 377 submits and 376 cancel rows (360
of its own orders, 16 of rung 40's) plus 228 hidden requests, 981 (upper bound 1,129). The other B-r5 rungs that `V3-CHANGES.md` section 3 lists: rung 30 43.75 / 43.95 -> 43.35 / 43.55; rung 40
48.15 / 48.15 -> 47.85 / 47.85; rung 50 44.0 / 44.1 -> 45.25 / 45.3.

All 40 adapter rungs: 80 values, 63 changed, 17 equal, largest shift 6.0 msgs/s. The three largest, by the larger of a rung's two shifts, none of which is cited anywhere:
- L0-m4 rung 20: upper bound 32.5 -> 26.5 (-6.0), refined 29.75 -> 26.25 (-3.5); stopped after 4 recorded seconds with 50 submits recorded, 40 inside the window;
- B-r3 rung 30: 47.27 -> 44.27 (-3.0), both series; stopped after 11 recorded seconds, 180 submits recorded, 165 inside the window;
- L0-m2 rung 10: 11.0 -> 9.0 (-2.0), both series; stopped after 1 recorded second.
All seven rungs that were stopped part-way (B-r2 rung 30, B-r3 rung 30, B-r4 rung 20, L0-m1 rung 10, L0-m2 rung 10, L0-m4 rung 20, L1-m3 rung 20) changed in both values, by -0.33 to -6.0 or +0.40; of the 66
values of the 20-second rungs 49 changed, by at most 1.25 (B-r5 rung 50 refined 44.0 -> 45.25, upper 44.1 -> 45.3). Of the 6,264 first cancels of the rungs' orders 6,073 were sent in the rung's own
window, 113 in another rung's window and 78 outside every window; 33 of the 40 rungs have at least one cancel outside their own window. The 11 retry cancel rows (B-r2 2, B-r5 3, L1-m1 2, L1-m3 4)
are messages that the order attribution never counted: a window mean counts each that falls inside its window (and a hidden request for refined); 7 of the 11 do.

Every mean above 50 is the same set before and after: B-r6 rung 40 (refined, upper bound) and rung 50 (upper bound).

## 4. Published statements that quote a per-rung wire mean

README.md lines 74-77 (item 2 of "What the data shows") and the corrected text. Revision 3 and earlier:

> One adapter connection sustained about 900 orders a minute with cancels (rung 30: 897-900, wire estimate about 45 msgs/s) with accept p50 0.61 s. At rung 40 its wire estimate was 51.7 (refined)
> to 57.3 (upper bound) msgs/s and at rung 50 49.4 to 56.6, the window filled (50 open) and latency rose (accept p50 0.90-0.93 s); three of those four estimates are above the 50 cap.

With the revision-4 numbers (two decimals; `round(49.05, 1)` would print 49.0, so one decimal is not used):

> One adapter connection sustained about 900 orders a minute with cancels (rung 30: 897-900, wire estimate 44.75 (refined) to 44.8 (upper bound) msgs/s, about 45) with accept p50 0.61 s. At rung 40
> its wire estimate was 51.3 (refined) to 56.5 (upper bound) msgs/s and at rung 50 49.05 to 56.45, the window filled (50 open) and latency rose (accept p50 0.90-0.93 s); three of those four estimates
> are above the 50 cap. (Each estimate is the wire messages inside the rung's own 20 s window divided by 20 s.)

Re-check of "three of those four estimates are above the 50 cap": 51.3 and 56.5 (rung 40) and 56.45 (rung 50, upper bound) are above 50; 49.05 (rung 50, refined) is not. It holds: three of four, the same
three as before (51.65, 57.3, 56.55). "About 900 orders a minute" (897-900 are orders per minute by counted rate and by submits), "the window filled (50 open)" (`peak_open_orders` 50) and the accept
latencies are unchanged. README lines 33-37 describe the two fields as the counted rate plus the adapter's hidden request, without naming a window; the window is the one defined above.

`V3-CHANGES.md` statements that quote the revision-3 values and are corrected here: section 4 item 8 ("B-r6 rung-30 wire means 44.95 refined / 45.0 upper bound" is now 44.75 / 44.8; "wire about 45" still
holds); section 4 item 9 ("51.65, 57.3, 49.35, 56.55" is now 51.3, 56.5, 49.05, 56.45; three of four still above 50); section 3's "the wire means do not change" (true of revision 3 against revision 2, not
of revision 4). The sliding maxima of section 3 and every other number of `V3-CHANGES.md` are unchanged. ADDENDUM-01..04 quote no per-rung wire mean.

## 5. Verification

- (a) The sealed revision-3 generator re-run on the run root prints the sealed revision-3 JSON byte for byte (sha256 `180dd86e1848b871...`).
- (b) The revision-4 generator prints the same bytes (sha256 `841ec596...`) under CPython 3.12.3, 3.13.16 and 3.14.4 and under PYTHONHASHSEED 1 and 987.
- (c) The revision-4 verifier on the revision-4 JSON: 228 checks, 0 failures with the pinned `core.rs`; 223 checks, 0 failures without it (revision 3: 174 and 169). The 54 new checks are four per adapter
  run with rungs (12 runs: window means, order-attributed values with the cancel counts, the classification, its sum) and six in section 2 (two `*_by_order_rung` keys for each of three headline rungs).
  The INFO line prints "3 of 4 (rung 40 refined; rung 40 upper_bound; rung 50 upper_bound)".
- (d) Mutation tests, each editing ONE value of a copy of the revision-4 JSON; the verifier exits 1 and names exactly the stated check:

| mutation | failing check |
|---|---|
| a revision-3 value put into a headline: `adapter_r6_rung40` refined 51.3 -> 51.65 | `adapter r6 rung 40 wire_est_refined_msgs_per_s_mean (exact): document 51.65 vs recomputed 51.3` |
| one rung's wire mean shifted by 0.5: B-r5 rung 30 refined | the B-r5 per-rung window-mean check (document 43.85, recomputed 43.35) |
| one rung's wire mean shifted by 0.02 in a pair run: L1-m1 rung 20 upper bound | the L1-m1 per-rung window-mean check (document 29.27, recomputed 29.25) |
| a `*_by_order_rung` value altered in a rung: B-r6 rung 40 refined 51.65 -> 51.6 | the B-r6 order-attributed check |
| a `*_by_order_rung` value altered in a headline: `adapter_r6_rung50` upper 56.55 -> 56.5 | `adapter r6 rung 50 wire_est_upper_bound_msgs_per_s_mean_by_order_rung (exact): document 56.5 vs recomputed 56.55` |
| one cancel moved from the own-window count to the other-window count: B-r6 rung 30 | the B-r6 cancel-classification check |
| the revision number set to 3 | `the document is revision 3; this verifier checks revision 4` |
| the superseded generator digest zeroed | the revision-block check (and the 8+ digit hygiene check) |

- (e) The sealed revision-3 verifier on the revision-4 JSON: `FAIL the document is revision 4; this verifier checks revision 3 (use the verifier named for the document's revision)`, exit 1.
- The revision-4 per-rung figures were also compared with an independent recomputation by the coordinator over the same journals: 360 field comparisons (window means, order-attributed means,
  cancel counts and classification, for all 40 rungs), 0 differences.
- Synthetic cases A-F (section 1): every revision-3 value is the defective value recorded here and every revision-4 value is the expected one. The case script is a private helper and is not published,
  so no digest of it is published.
- Identity scan of the four files (home paths, state directory, user name, login, host name, account, order-reference and permanent-id shapes, addresses, long digit runs): 0 matches.

## 6. Not done, and limits

- The wire series is still a source-derived estimate (the hidden `reqAllOpenOrders` per cancel of an accepted order), stamped with its cancel row's time.
- The window means use the rung's recorded seconds; a rung stopped part-way is therefore a mean over its evaluated seconds, as `counted_msgs_per_s_mean` already is.
- The receipt's `counted_msgs_per_s_mean` is unchanged; in two rungs (L1-m1 rung 20, L1-m3 rung 15) the window holds one message more than the receipt's slots (`V3-CHANGES.md` section 2).
- The official-client figures are untouched and still not recomputable from the receipts.
- README.md, ADDENDUM-01..04 and the revision-1, -2 and -3 files are not edited. Nothing was posted anywhere.
