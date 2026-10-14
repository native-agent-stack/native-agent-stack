# V3-CHANGES: IBKR pacing evidence, revision 3

A correction of three defects in the sealed revision 2 of the generator, verifier and document. It adds no measurement and no input.
Writing began 2026-10-13T18:56:00Z (tool clock); the text was revised after the verification runs described below, by the trading-cc builder.

## Files and what stays sealed

| file | sha256 |
|---|---|
| `generate_ibkr_pacing_evidence.v3.py` | `933133afe24f128eb4226fb4c50230cb300d5e59ef8e663cc8dac0fb95a9100b` |
| `verify_ibkr_pacing_evidence.v3.py` | `c8872073cf71990e349ef77293dcef0e434b087e70091b26c6c2749cbce22630` |
| `ibkr-pacing-evidence-20261013.v3.json` | `180dd86e1848b8714ab7e5850d2989eb08217c1a0fb87f3af6493bc9006b8729` |
| `V3-CHANGES.md` | this file (no digest of itself) |

Revision 2 stays sealed and unchanged: generator `f44b595a13cf87b4ad555427000c7937cc62452076f0a3380f13338127147619`, verifier `cac1e764f429dc05575dfe8a692e74d4bcc04a8906e174e9e7b0178cf61494e3`,
JSON `25ef71020a06e1781fac0360aa8b19c564d9d146b65ea3fc6b8cb0ab62ab0c15`. Revision 1 stays sealed and unchanged: generator `56463b2622501446a9a1640c6d3065920dbd449a622457ea61f392ce6166c5a1`,
verifier `0e9fb1376a59e34cf1e3b6ba2fea30d89aad5e09db28de0b4d59792a41207468`, JSON `b492f42d335370e22f4349bf43db54f1adf4c77921b36a28300159b08c8e11fa`. README and ADDENDUM-01..04 are not edited:
where they are out of date, this file is the correction. The README's own `Verify` commands name the revision-1 files; use these for revision 3:

```
python3 -I -B generate_ibkr_pacing_evidence.v3.py RUN_ROOT > check.json && diff check.json ibkr-pacing-evidence-20261013.v3.json
python3 -I -B verify_ibkr_pacing_evidence.v3.py ibkr-pacing-evidence-20261013.v3.json RUN_ROOT [PINNED_CORE_RS]
```

Inputs are the same private run root the revision-2 generator read (receipts, journals, vendor logs, markers, the missing-id list). The revision-2 generator re-run on it prints the sealed
revision-2 JSON byte for byte (sha256 `25ef7102...`), so the inputs are intact. The revision-3 generator prints the same bytes under CPython 3.12.3, 3.13 and 3.14 and under two fixed hash seeds.

## 1. The three defects, each reproduced against the sealed revision-2 files before any fix

Found by the co-op's local review of nas#1083 at 2d433d4c. All synthetic cases below use invented ids (`syn-N`) and invented times; none comes from a run.

### D1. Per-id ownership (verifier)

Revision 2's check "every missing id is found in exactly one run journal" compared COUNTS: `len(missing)` against `sum(derived.values())`, where `derived` has one entry per (journal, id) pair that
holds an event of a missing id. It passes when one missing id is in no journal and another is in two journals of the same kind. ADDENDUM-03 described the check as "every missing id must be found in
exactly one run journal"; it did not check that per id.
- Synthetic (3 invented ids: one in no journal, one in two journals, equal kinds): the revision-2 rule compares 3 with 3 and passes; the revision-3 `ownership_problems` lists two problems.
- End to end on a private copy of the run root in which every journal row of one refused missing id was renamed to another refused missing id held by a different journal (same kind, same row and submit
  totals): the sealed revision-2 verifier passes 82 of 82 on that copy.

### D2. "Any 1 s" and "best 5 s mean" over UTC-second buckets (generator)

`window_stats` read `per_second`, a dict keyed by the UTC second of each message. 30 messages at x.990 s and 30 at (x+1).010 s give `max_1s` 30 although 60 occurred inside 0.02 s.

| synthetic case | revision 2 | revision 3 |
|---|---|---|
| D2-a: 30 submits at x.990 s, 30 at (x+1).010 s; counted `max_1s` | 30 | 60 (and `max_1s_utc_buckets` 30) |
| D2-b: 15 cancels of accepted orders at x.990 s, 15 at (x+1).010 s; counted / wire refined / wire upper `max_1s` | 15 / 30 / 30 | 30 / 60 / 60 |
| D2-c: the same with cancels of unaccepted orders (no hidden request); wire refined / wire upper `max_1s` | 15 / 30 | 30 / 60 |
| D2-d: 20 messages at x.900 s, 20 at (x+5).050 s; counted `best_5s_mean` | 4.0 | 8.0 (and `best_5s_mean_utc_buckets` 4.0) |
| D2-e control: 10 messages at .250 s and 10 exactly 1 s later; `max_1s` (a half-open window) | 10 | 10 |
| D2-f control: the second 10 start 20 microseconds before the 1 s mark; `max_1s` | 10 | 20 |
| D2-g control: an empty journal; `max_1s`, `best_5s_mean` | 0, 0.0 | 0, 0.0 |

### D3. `peak_open_orders` kept terminal orders open (generator)

`ladder_rungs` closed an order only at `order_canceled`. Four orders each submitted then rejected before the next give a peak of 4 (the correct value is 1).

| synthetic case (four orders, each submitted then closed before the next unless stated) | revision 2 | revision 3 |
|---|---|---|
| D3 `order_rejected` / `order_filled` / `order_expired` / `order_denied` / `order_cancelled` | 4 each | 1 each |
| D3 control `order_canceled` | 1 | 1 |
| D3 control: an `order_submitted` with no later event stays open | 4 | 4 |
| D3 control: `order_cancel_rejected` and `order_pending_cancel` are not terminal | 4 | 4 |
| D3 first terminal event: rejected, then a later canceled, two overlapping orders | 2 | 1 |
| D3 mixed: four open at once, one rejected, one filled, one canceled, two more submitted | 5 | 4 |
| D3 names: terminal names derived from a journal that carries `order_rejected` and `order_expired` | n/a | `order_expired`, `order_rejected` |

## 2. What revision 3 does (every changed hunk)

Generator (`diff -u` against revision 2: 17 hunks; everything outside the items below is byte-identical):
- Docstring: a revision-3 paragraph; the usage line names the v3 files. `timezone` import. Constants `EPOCH`, `US`, `TERMINAL_ORDER_EVENT_CANDIDATES`, `RATE_UNIT`.
- New `us()` (exact integer microseconds), `sliding_peak()` (two pointers over a half-open `[t, t + width)` anchored at an entry), `sliding_stats()`, `terminal_events()`.
- `window_stats()`: docstring only; its code is unchanged and now produces the `*_utc_buckets` values.
- New `message_times()`; `rate_block()` rewritten: per series `max_1s` / `best_5s_mean` are sliding values and `max_1s_utc_buckets` / `best_5s_mean_utc_buckets` are the revision-2 values;
  it exits with an error if a sliding value is ever below its bucket value (impossible by construction, kept as a guard).
- `ladder_rungs()`: terminal names derived from the run's own journal vocabulary; an order closes at its FIRST terminal event (the smallest timestamp); per rung it adds
  `max_1s_sliding_in_rung_window` and `receipt_slots_replayed_from_journal`. The `canceled` dict, and so every latency, is untouched.
- `reconciliation()`: an owner map and `journal_orders_missing_by_number_of_owner_journals`. `headline()`: the unit text of the two rate headlines (one shared constant).
- New `journal_vocabulary()`, `peak_open_orders_definition()`, `rate_window_conventions()`.
- `main()`: the vocabulary and the replay list; the two new `facts` blocks; the revision block; three caveats.

Verifier (`diff -u` against revision 2: 8 hunks; everything outside the items below is byte-identical):
- Docstring, imports, constants (window parameters, terminal-name pattern, the revision-2 and revision-1 hashes). `check()` and `close()` count their checks.
- `seconds_of()` and the bucket-only `whole_run_rates()` replaced by `us_of()`, `message_events()`, `sliding_best()` (prefix sums and bisect, a different method from the generator's two pointers),
  `whole_run_rates()` (sliding plus bucket values), `owner_map()`, `ownership_problems()`, `ladder_entries()` and `rung_peaks()` (counts with bisect over event keys, not a running sum).
- `main()`: an early FAIL if the document is not revision 3. Reconciliation: per-id ownership and the owner histogram replace the count check.
- Section 4b: the window convention is compared with the document; sliding and bucket blocks are recomputed for B-r5, B-r6, four pairs, all 19 runs and the four combined blocks; the two cap
  statements revision 2 asserted as true are replaced by comparisons of what the document says with what is recomputed (section 4), plus INFO lines.
- New sections 4f (per-rung sliding windows, and the receipts' per-second slots replayed from the journals) and 4g (terminal names against the journals' vocabulary, quantities, per-rung peaks,
  an INFO line comparing the revision-2 and revision-3 rules, the revision block). The final line prints the number of checks.

Window convention (in the JSON under `facts.rate_window_conventions`, compared by the verifier): `max_1s` is the largest number of messages of a series in any half-open interval `[t, t + 1 s)` whose start
`t` is the timestamp of a message of that series; `best_5s_mean` the same with `[t, t + 5 s)`, divided by 5 and rounded to 2 decimals; exact integer microseconds. A window can always be shifted right to
the first message it holds without losing one, so this equals the maximum over every real start time. The adapter's hidden `reqAllOpenOrders` is not separately timestamped in the journal and is placed at
its cancel row's timestamp (the same convention revision 2 used within a second). A sliding value is never below its bucket value; the generator and the verifier both enforce that.

Per-rung windows (new): rung j covers `[S4 step_enter row + j x rung_s, + the rung's recorded seconds)`, the harness's own per-second slot grid replayed from the journal. The replay equals the receipts'
`per_second_msgs` in 38 of 40 rungs; in the other two (L1-m1 rung 20, L1-m3 rung 15) it is one message higher in the first slot: a message sent in the milliseconds between the previous rung's nominal end
and the harness tick that journalled the next rung's start is not counted by the harness (its slot index, 20, falls outside the finished rung's 20-slot row), and the replay counts it in the first slot
of the new window.

## 3. Complete diff of the JSON against revision 2

A key-level diff of the revision-3 JSON against the sealed revision-2 JSON lists no path that the three defects, the convention text, the revision block or the caveats do not explain (0 unexplained).
Every `*_utc_buckets` value equals the revision-2 value of the same path (asserted for all 138 run and pair values and their 36 headline copies).

| change | paths | defect |
|---|---|---|
| `max_1s`, `best_5s_mean` of every rate block: now sliding values (old values below) | 96 changed of 138 in the run and pair blocks, and all 36 of their copies in the two rate headlines (`adapter_whole_run_rate_estimates`, `adapter_two_connection_combined_rate_estimates`) | D2 |
| `max_1s_utc_buckets`, `best_5s_mean_utc_buckets`: the old values under their correct names (new fields) | 174 | D2 |
| `max_1s_sliding_in_rung_window`, `receipt_slots_replayed_from_journal` on every adapter rung (new fields) | 80 (40 rungs) | D2 |
| headline `unit` text of the two rate headlines ("max over any 1 s" now says sliding, anchored at a message) | 2 | D2 |
| `peak_open_orders` of every adapter rung | 0 changed of 40 (see below); `facts.peak_open_orders_definition` added | D3 |
| `reconciliation.journal_orders_missing_by_number_of_owner_journals` (new): `{"0": 0, "1": 38, "2_or_more": 0}` | 1 | D1 |
| `facts.rate_window_conventions` (new) | 1 | D2 |
| `revision` (number 3, `supersedes` names the revision-2 files, `earlier_revisions`, `sealed_files`, `changes`) | 7 paths | all |
| `caveats`: three entries added (the list is one path) | 1 | D2, D3 |

Old value -> new value of every changed rate number (whole runs, then the four combined pairs; `max_1s` / `best_5s_mean`; "(unchanged)" where equal):

```
run    series            max_1s                        best_5s_mean
A-r1   counted           1 -> 2                        0.4 (unchanged)
A-r1   wire refined      2 -> 3                        0.6 (unchanged)
A-r1   wire upper bound  2 -> 3                        0.6 (unchanged)
A-r2   counted           3 -> 5                        1.0 (unchanged)
A-r2   wire refined      4 -> 6                        1.2 (unchanged)
A-r2   wire upper bound  4 -> 6                        1.2 (unchanged)
A-r3   counted / refined / upper   3, 4, 4 (unchanged)  1.0, 1.2, 1.2 (unchanged)
A-r4   counted           3 -> 5                        1.0 (unchanged)
A-r4   wire refined      3 -> 6                        1.2 (unchanged)
A-r4   wire upper bound  3 -> 6                        1.2 (unchanged)
A-r5   counted / refined / upper   5, 6, 6 (unchanged)  1.0, 1.2, 1.2 (unchanged)
A-r6   counted / refined / upper   5, 6, 6 (unchanged)  1.0, 1.2, 1.2 (unchanged)
B-r2   counted           18 (unchanged)                13.4 -> 13.6
B-r2   wire refined      26 (unchanged)                20.0 -> 20.6
B-r2   wire upper bound  26 (unchanged)                20.0 -> 20.6
B-r3   counted           31 -> 35                      30.2 -> 30.6
B-r3   wire refined      47 -> 54                      45.4 -> 46.2
B-r3   wire upper bound  47 -> 54                      45.4 -> 46.2
B-r4   counted           21 -> 24                      20.2 -> 20.8
B-r4   wire refined      32 -> 37                      30.4 -> 31.4
B-r4   wire upper bound  32 -> 37                      30.4 -> 31.4
B-r5   counted           37 -> 46                      32.6 -> 33.6
B-r5   wire refined      57 -> 69                      49.8 -> 51.2
B-r5   wire upper bound  57 -> 69                      49.8 -> 51.2
B-r6   counted           48 -> 53                      40.8 -> 42.0
B-r6   wire refined      66 -> 78                      53.8 -> 56.6
B-r6   wire upper bound  71 -> 83                      60.8 -> 63.4
L1-m1  counted           29 -> 33                      25.6 -> 26.0
L1-m1  wire refined      44 -> 52                      38.8 -> 39.4
L1-m1  wire upper bound  45 -> 53                      38.8 -> 39.6
L0-m1  counted           8 -> 10                       3.4 (unchanged)
L0-m1  wire refined      8 -> 10                       3.6 (unchanged)
L0-m1  wire upper bound  12 -> 15                      4.6 (unchanged)
L1-m2  counted           26 -> 30                      25.2 -> 25.8
L1-m2  wire refined      40 -> 47                      37.8 -> 39.0
L1-m2  wire upper bound  40 -> 47                      37.8 -> 39.0
L0-m2  counted           5 -> 7                        1.8 (unchanged)
L0-m2  wire refined      7 -> 9                        2.2 (unchanged)
L0-m2  wire upper bound  7 -> 9                        2.2 (unchanged)
L1-m3  counted           21 -> 25                      20.4 -> 20.8
L1-m3  wire refined      32 -> 40                      30.8 -> 31.6
L1-m3  wire upper bound  32 -> 40                      30.8 -> 31.6
L0-m3  all three series  0 (unchanged)                 0.0 (unchanged)   (empty journal)
L1-m4  counted           28 -> 30                      25.6 -> 26.0
L1-m4  wire refined      43 -> 47                      38.6 -> 39.4
L1-m4  wire upper bound  43 -> 47                      38.6 -> 39.4
L0-m4  counted           20 -> 23                      18.0 -> 19.2
L0-m4  wire refined      30 -> 36                      27.0 -> 27.2
L0-m4  wire upper bound  30 -> 36                      27.0 -> 28.4
pair m1  counted         29 -> 33                      25.6 -> 26.0
pair m1  wire refined    44 -> 52                      38.8 -> 39.4
pair m1  wire upper      45 -> 53                      38.8 -> 39.6
pair m2  counted         26 -> 30                      25.2 -> 25.8
pair m2  wire refined    40 -> 47                      37.8 -> 39.0
pair m2  wire upper      40 -> 47                      37.8 -> 39.0
pair m3  counted         21 -> 25                      20.4 -> 20.8
pair m3  wire refined    32 -> 40                      30.8 -> 31.6
pair m3  wire upper      32 -> 40                      30.8 -> 31.6
pair m4  counted         28 -> 35                      25.6 -> 26.0
pair m4  wire refined    43 -> 47                      38.6 -> 39.4
pair m4  wire upper      43 -> 52                      38.6 -> 39.4
```

`peak_open_orders`: no published value changes. The defect is real (section 1) but on these inputs every rung of the three runs that carry refusals (L0-m1, L0-m2, L0-m4) reached its peak before
that run's first refusal was journalled (by 0.003 s to 21 s; a private check), so the revision-3 rule gives the revision-2 value in all 40 rung entries. The verifier prints the same comparison as an
INFO line ("rungs whose peak differs between the revision-2 rule and the revision-3 rule: none") and now checks every rung's peak, which revision 2 never did.

New per-rung numbers for the rungs the claims below rely on (receipt slot maximum -> sliding maximum inside the rung's window; counted / wire refined / wire upper bound; the wire means do not change):

```
B-r5 rung 30: 31 -> 36 / 57 / 57      B-r5 rung 40: 37 -> 42 / 68 / 68      B-r5 rung 50: 38 -> 46 / 69 / 69
B-r6 rung 30: 31 -> 40 / 63 / 64      B-r6 rung 40: 44 -> 47 / 69 / 73      B-r6 rung 50: 48 -> 53 / 78 / 83
```

Across all 40 adapter rungs the sliding counted maximum is above the receipt's slot maximum in 33 and equal in 7 (never below).

## 4. Published claims that quote a per-second maximum, and whether each holds

Statements quoted when this revision was commissioned ("never above 45/s", "peak 38") are NOT in README.md, ADDENDUM-01..04 or the JSON's text; "wire about 45" is README line 74.
They are mapped below to the nearest JSON numbers.

FAIL OR CORRECTED (these were true only as UTC-bucket statements, or were mislabelled):
1. **"Every two-connection adapter pair stayed at or below 50 wire msgs/s (upper bound, any 1 s)"** (an assertion of the revision-2 verifier, 45 / 40 / 32 / 43 for m1..m4). Sliding upper bound: **m1 53,
   m2 47, m3 40, m4 52** (refined 52 / 47 / 40 / 47). It FAILS for m1 and m4; it holds for m2 and m3. The revision-3 verifier no longer asserts it; it compares the document with the recomputation.
2. **"B-r5 did not exceed 50 wire msgs/s as a best 5 s mean (upper bound)"** (revision-2 verifier, 49.8). Sliding: **51.2** (refined and upper bound). FAILS. "B-r6 exceeded 50 (refined best 5 s mean)":
   53.8 -> 56.6, holds a fortiori.
3. **"never above 45/s"** (the pairs' combined upper-bound maximum in the revision-2 JSON was 45, at m1). Sliding **53** at m1 and 52 at m4. FAILS.
4. **"peak 38"** (matches B-r5 rung 50 `counted_msgs_per_s_max`, a receipt slot counter). The largest sliding 1 s window inside that rung holds **46** counted messages (69 wire). FAILS as a peak rate.
5. Whole-run B-r5 and B-r6 `max_1s`: counted 37 -> 46 and 48 -> 53; wire refined 57 -> 69 and 66 -> 78; wire upper 57 -> 69 and 71 -> 83 (table above).
6. README line 38 ("the maximum over any single second") and the revision-2 headline `unit` ("max over any 1 s") described bucket values as sliding maxima. Corrected in the revision-3 unit text and
   conventions.
7. ADDENDUM-03 item (b) (above): the count check was described as per id. Corrected by D1.

HOLD (statements about means or counts, which a window definition does not change):
8. **"wire about 45"** (README line 74, rung 30): B-r6 rung-30 wire means 44.95 refined / 45.0 upper bound. It holds as a mean. Inside that rung's window the largest sliding 1 s window holds
   40 counted and **63 / 64 wire messages**, so the mean hides one-second bursts above 50.
9. README: rung 40 wire estimate 51.7 (refined) to 57.3 (upper bound) and rung 50 49.4 to 56.6, "three of those four estimates are above the 50 cap": means, unchanged (51.65, 57.3, 49.35, 56.55).
10. README: official client "49.95 msgs/s at rung 50", 1,500 orders a minute with cancels, 2,997 messages a minute: means and counts, unchanged. The README states no per-second maximum for the official
    client; its receipt slot maxima (30 / 42 / 46 / 51 at rungs 30 / 40 / 45 / 50) are bucket values on the probe's monotonic seconds, unchanged, and cannot be recomputed (no per-message times were kept):
    the true 1 s maximum at rung 50 is at least 51.
11. Caveat "Adapter rungs whose wire estimate exceeded 50 msgs/s ran above the cap in wire terms; no pacing text, no code 100 and no disconnect occurred": rung means, holds. The same is true in the sliding
    windows above 50: `pacing_error_count`, `code_100_lines` and `pacing_text_lines` are 0 in every adapter ladder and pair run.
12. README "the window filled (50 open)": `peak_open_orders` 50 for B-r6 rungs 40 and 50, unchanged.

Whether a sliding 1 s window above 50 wire messages is "above the cap" depends on how the Gateway counts, which this evidence does not establish; the numbers are reported as measured.

## 5. Verification

- Revision 3 verifier on the revision-3 JSON: 174 checks, 0 failures with the pinned `core.rs`; 169 checks, 0 failures without it (the cited-line check is then skipped). Revision 2 had 82 (77).
  Of the 82, three were replaced: the count check by two per-id checks, the two cap assertions by two document-against-recomputation comparisons; 91 are new (conventions, every run and pair block,
  per-rung windows and replay, terminal names and per-rung peaks, the revision block).
- Negative controls, each on a private copy of the run root (symlinks to the originals, one file written new; nothing deleted), with the revision-2 and revision-3 verifiers:

| control | revision 2 verifier | revision 3 verifier |
|---|---|---|
| NC1 swap: every row of one refused missing id renamed to a refused missing id of another journal (same kind, same totals) | 82 of 82 pass | the per-id check FAILS: position 9 has 2 owner journals (L0-m1, L0-m4), position 34 has 0; the histogram check fails too against the real-root document. A document generated from the copy (honest histogram: 1 id with no owner, 36 with one, 1 with two) fails only the per-id check. |
| NC2 burst: 20 cancel rows at x.990 s and 20 at (x+1).010 s, written into the empty L0-m3 journal copy (synthetic ids): 20 per UTC second (40 wire messages, at or below 50) but 80 wire messages in 0.02 s | the document it generates says pair m3 wire upper `max_1s` 40; 82 of 82 pass | a document generated from the copy: 174 of 174 pass (sliding 40 counted / 80 wire; buckets 21 / 40). The same document with the m3 blocks carrying the bucket numbers under `max_1s` / `best_5s_mean` (what revision 2 publishes): 6 failures, e.g. `max_1s` 40 against recomputed 80 while `max_1s_utc_buckets` agrees |
| NC3 flip: five `order_canceled` rows of rung-30 orders in B-r6 rewritten as `order_rejected` | the document it generates carries B-r6 peaks 10:2, 20:24, 30:38, 40:55, 50:55; 82 of 82 pass (peaks are not checked) | a document generated from the copy: 174 of 174 (peaks 2, 24, 33, 50, 50). A document carrying the revision-2 peaks: 1 failure, the B-r6 peak check |
| NC4 the revision-2 document given to the revision-3 verifier | n/a | FAIL "the document is revision 2; this verifier checks revision 3" |

- No verifier output line prints an order reference: the per-id lines carry the position, 8 hex digits of the id's sha256 and the owner run labels (grep for the order-reference and account shapes: 0).
- Synthetic cases (`D1`..`D3` above): every revision-2 value is the defective value recorded here and every revision-3 value is the expected one. The case script is a private helper and is not published, so no
  digest of it is published (the rule ADDENDUM-03 text revision 2 states).

## 6. Not done, and limits

- The official client's per-second maxima and `peak_open_orders` are receipt values of the probe's own run-time counters (monotonic-second buckets; an open set that keeps a [103]-refused id until its
  stale cancel is answered with 10147). They are unchanged, not recomputable here, and disclosed in the JSON.
- The wire series is a source-derived estimate (hidden `reqAllOpenOrders` per cancel of an accepted order); its sliding maxima inherit that and the cancel-row timestamp convention.
- The per-rung window replay is exact in 38 of 40 rungs and one message high in two (above); the per-rung sliding values are computed on the replayed window.
- README.md, ADDENDUM-01..04 and the revision-1 and revision-2 files are not edited. PR nas#1083 carries copies of revision 2; nothing was posted anywhere.
