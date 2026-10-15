# DISPLAY amendment: one live projection, two display arms

**Comparison id:** w6-us-equities-observability-hosting-20261011

**Amendment id:** display-v1

**Registered:** 2026-10-15T00:08:13Z, before either display arm has run

**State:** SCHEDULED for the DISPLAY subrole; no measured winner or adoption

## Relationship to the frozen comparison

This adds a display subrole to the existing comparison. The original
[preregistration](preregistration.json), SHA256
cd83fdb082cf729ef80996b3a53e17a221838955f2e67143ea6065a3666a772a,
its backend and recovery rules, and its fixture remain byte-identical.
Grafana-stack versus SigNoz and the independent rest-server/SFTP/rclone
deletion-protection subrole retain their own readiness triggers and decisions.
They start when their own inputs exist; DISPLAY does not delay them.
The cumulative restic/rest-server survivor remains in that recovery subrole.

The new evidence is the retained 2026-10-14 dashboard survey and its equal-panel
addendum, followed by a display-neutral live-projection contract and timestamp/
deduplication correction. Their exact private seals and provenance are in the
lane's amendment-input record; no private document bytes or private-document
hashes are published here. The public primary-source witnesses used below are
in [display-primary-sources.json](display-primary-sources.json). Survey
inferences and vendor claims are leads, not reproduced capability results.

The 09-22 verdict has no winners; the covering 09-26 sweep retained rest-server.
The newer completed 10-13 publication manifest is awaiting its ledger append:
its observability entries are not individually reviewed, contain no candidate
votes or measured dashboard results, and do not adjudicate that survivor away.
The 10-14 survey adds a display requirement delta, not a replacement backend
verdict. This is one comparison with independently triggered subroles.

## Readiness and frozen data boundary

**Trigger:** the live projection v1 implementation, including its v1.1
timestamp and row_id corrections, is landed, and an immutable capture of its
spool covers one complete session. A date is never a trigger.

Use the first complete session captured after that implementation lands.
Record the landing commit, projection version, session label, calendar-defined
start/end, initial cursor, ordered segment hashes and row counts privately.
Capture from before the session starts through its close; the production spool
is bounded, so its final 8 MiB alone is not a full-session capture. Missing
segments, copy-truncation gaps or an unproven initial cursor leave this input
absent. Source labels and actual data remain private.

When those two inputs exist, begin this subrole immediately. Completing the
pre-run source-pin screens, supported build/tests, artifact and instrumentation
seals is execution work at that trigger, not an extra date or an excuse to
leave ready work unstarted. An arm that fails a screen is recorded as
ineligible before installation/trial. An unavailable screen is a setup failure,
not a measured arm failure; retain and resolve it through the pinned upstream
path before a scored run. No new package, service or comparison is run by this
preregistration.

Both arms consume exactly the same ordered, deduplicated projection bytes,
with identical release times. There are no direct broker, journal, calculator,
ledger or market-data queries. Preserve optional-field absence, row_id,
observed_ms, t_ms, lane, run and order_key. Deduplicate deliveries by
(lane, row_id); never by seq, which can restart. Join orders by
(lane, run, order_key). An orphan commission/status stays visibly unmatched;
never infer a missing identity. If an identity collision carries differing
payloads, fail corpus validation instead of silently overwriting.

The input has timestamp fields distinct from bounded integer counters. Preserve
negative quote-age durations and missing fields. A zero is not a missing value.
Replay order, not sorting by source timestamps, determines arrival order;
late source timestamps remain late. Financial decimals compare numerically
without rounding in the oracle; the display may format to the declared precision
only if the underlying value remains inspectable.

## Arms and panel scope

| Arm | Fixed display and path | Required output |
| --- | --- | --- |
| D-A | Grafana v13.2.3, 6193dc03311b631b9727b560d24369e683dc396e. Existing Collector-contrib/Loki ingestion and native Grafana table transformations; the matching parent component pins apply. No additional SQL store or third-party panel. | Keyed working-orders state, fills event table, positions/account state, ranked decisions and refusal counts from available projection rows. |
| D-B | Perspective v5.6.0, 0842ad79117b0d4a589df1655f2679cad827f8a7, browser WASM indexed tables and the upstream datagrid. A minimal read-only spool feed uses the same capture; no exposed mutable Perspective server API. | The same columns, row identities, groups, missing-value indicators, filtering tasks and inspection precision as D-A. |

D-A uses upstream JSON extraction, grouping/Last and field joins. Those
capabilities are documented at its pin; the survey's claim that a SQL store is
necessarily required is not established. Whether native transforms retain the
correct state through this workload is measured. Adding SQL after seeing a
failure would change the arm and is prohibited in this run.

D-B reuses Perspective's table/index/update and viewer facilities. The only
task glue is projection-to-table mapping and a read-only data feed. Its browser
worker is a disposable replica; browser mutations must have no route to the
shared feed, spool, engine or another reader's state. Do not expose the
upstream general-purpose server Table API: its documented update calls are
write-capable. Explicit READ_ONLY configuration is necessary but does not by
itself establish server-side enforcement.

Map the same display-neutral events to the same reference state; each arm
implements that mapping independently through its own native query/table
facilities. The independent oracle is not either arm's reducer. Seal all
queries, transformations, viewer settings and minimal mapping glue before
scored replay. No plugin/store substitution or tuning after scored results.
Unsupported mandatory cells are failures, not omitted rows.

Both paths use a one-second acquisition/refresh interval where polling is
required. Every transform, buffer and polling delay counts in latency. Record
native push updates separately; do not artificially delay them to equal polling.
The data contents, release times, browser, host allocation and presentation
tasks are equal, rather than assuming equal pipeline implementations.

Existing logs, alerts and infrastructure time-series panels are shared context,
not evidence for either display arm's superiority. They remain subject to the
read-only gate. Price candles and in-bar fill markers are outside the scored
v1 scope: bar_1m has no qualified source. No bars may be fabricated from sparse
fills or ranked quotes. Lightweight Charts v5.2.1 at
b2ce010e4ad59f6556c9ed60e2b2b30feccdd2d1 is retained as a source-reviewed
candidate for that reserved panel class, not installed, retired or scored.
Adding qualified bars requires a reviewed, hashed pre-run amendment under this
same id; it does not hold the v1 blotter comparison waiting.

NautilusTrader v2.0.0rc5 at 1b0a49d2792a9432a3aca3fcb617ce7a630d905e explicitly
places UI dashboards out of scope. Engine UIs from the survey are design leads,
not additional arms or proof that a drop-in read-only product exists.

## Corpus, cases and measurement

Use one captured full session, replayed at its original inter-row timing in
three paired repetitions: A then B, B then A, A then B. Each arm starts from
empty owned display state; each repetition uses the same sealed corpus.
Fix the same browser build, 1920x1080 viewport, device scale 1 and host resource
limits before the first replay. Retain native upstream install/build/test
commands, exit codes, version/asset identities and every failed setup attempt.
Use existing upstream browser/test facilities and the repository's retained
comparison/oracle workflow. Any new common measurement driver needs a reviewed
adoption decision before scoring; this file does not claim one already exists.

The real-session report and synthetic sensitivity controls are separate.
The fixed sensitivity matrix covers initial order, acknowledgment, partial
fill, status update, cancellation, late commission, duplicate delivery,
restart with replayed rows, run-key separation, absent field, negative age,
rejected event and unknown initial history. Use fictional values through the
landed projector's own fixtures. It must detect deliberately doubled rows,
dropped final status, seq-based dedup, wrong join keys and stale display values.
These controls validate the observer; they never invent real fills or provide
native market/broker evidence.

An independent oracle applies these rules at every completed input checkpoint:
event tables contain each unique row once; keyed state uses the last delivered
value for each present field, retaining earlier fields absent from an update;
explicit terminal states leave the working set; final values and totals agree
exactly. Calc cumulative/repeat fields are not blindly summed: use supplied
delta fields for incremental totals and show repeat events without adding their
cumulative quantity twice. Publish the per-kind mapping and expected rows
before replay. If the v1 spool cannot determine a value, both displays show
unknown and that task is marked unobservable.

For latency, the origin is the monotonic instant a complete spool row becomes
readable at the comparison feed, not its broker/source t_ms. Also report
observed_ms-to-pixel wall-clock lag with clock calibration, without substituting
it for the primary metric. The endpoint is the first captured rendered frame
showing the oracle-expected value for that row's visible test cell. A network
response, DOM mutation, screenshot request or animation-frame callback alone
is not a pixel timestamp. Retain timestamped browser screencast frames and
sampled pixel/value evidence; calibrate frame interval and clock mapping before
each run. Map host/browser monotonic clocks with measured error <=20 ms.

Virtualized/off-screen cells are tested by the fixed scroll/filter tasks and
checkpoint exports. Do not count an off-screen DOM value as a visible pixel.
Updates superseded before a paint are recorded as coalesced; for each scored
visible state require the latest released value by the next checkpoint.
Sample every fifth unique row and every terminal order/fill transition for
pixel timing; select samples by row order before replay, not by observed speed.
Require at least 100 non-coalesced visible samples in the full session and at
least one natural keyed transition and fill. If absent, publish limited
coverage and do not select a display winner from synthetic replacement data.
The resulting extra-display role is unsupported in this measured window;
do not re-register a date or silently repeat until favorable activity occurs.

## Metrics and gates

| Dimension | Frozen measurement / pass condition |
| --- | --- |
| Correctness | Zero extra, missing, duplicated or misjoined rows; zero incorrect numeric/state cells in checkpoint and final exports; all mandatory sensitivity controls detected. Show unobservable cells explicitly. |
| Spool row to pixel | Per repetition and panel: nearest-rank p50/p95/p99 and maximum over sealed visible samples; p95 <=5000 ms in every repetition. A sample still absent after 30000 ms is a missed update and correctness failure. Report coalesced updates and observer error. |
| Read-only enforcement | Zero forbidden controls and zero writes/effects in isolated negative tests; exact requirements below. |
| Licence compliance | All shipped direct/transitive licences and notices retained; required user-visible attribution verified in the built artifact. Unknown licence obligations fail the gate, not merit-rank a candidate. |
| Operations cost | New long-lived processes/services, added stores, setup/recovery operator minutes, total arm CPU seconds, 50 ms sampled concurrent arm-process RSS peak, bytes read/transferred/stored, compressed delivered page bytes and clean replay/restore time. Record baseline and incremental values; include every helper/store. |
| Maintenance and upstream health | Six-angle matrix below with pinned evidence and explicit supported/gap/conflict dispositions. No stars-only or release-age-only default. |

Read-only provisioning is mandatory whichever arm wins. Lint final Grafana
JSON recursively, including field overrides, library panels and shared context:
forbid table Actions cells, any configured data action, canvas Button elements
and write-capable data links. Refuse unsanitized HTML or arbitrary plugins.
For Perspective, pin edit_mode to READ_ONLY, remove editable aliases and
editing controls, and prove the feed accepts only read operations. Exercise
manually crafted mutation requests, not just clicks. Ordinary sort/filter/
zoom operations may change only local view state.

Run these probes only against disposable test endpoints, with broker/runtime
paths absent, no credentials and no broker egress. A canary records attempted
writes, source/spool hashes remain unchanged, and a second fresh reader sees
unchanged shared data. Mutate the provisioned artifact once to add an Actions
cell and once to add a canvas Button; lint must reject both. Mutate Perspective
to EDIT and expose a write route; each negative control must fail the gate.
There is no real broker or paper-account probe in this comparison.

For Lightweight Charts, any future included artifact must retain the NOTICE
attribution and a user-visible tradingview.com link; attributionLogo covers
the link requirement only. Apache-2.0 alone does not discharge these notices.
Grafana's AGPL and Perspective's Apache-2.0 obligations are evaluated at the
pinned distribution and its actual serving/modification model.

The six-angle health record covers: (1) capability at the pin and our exact
mapping/fixtures; (2) upstream engineering quality, native tests, release
provenance and applicable unresolved advisories; (3) independent community
operational reports, with linked failures as well as endorsements; (4) actual
usage/retention evidence distinguished from downloads and stars; (5) published
evaluations with workload comparability and conflicts disclosed; (6) these
paired measured runs. Record unavailable evidence as a gap. A conflict about
correctness, readonly behavior or cost must be measured in the named case
before selection; the matrix cannot vote away a failed gate. An unresolved
material conflict prevents adoption. A missing independent evaluation is not
agreement and limits any result to this task, never a general SOTA claim.

## Fixed decision rule

First apply all correctness, coverage, latency, readonly, licence and native
screen/test gates to each arm in all three repetitions. Missing observations,
failed instrumentation and setup errors invalidate the affected pair; retain
it, correct only the upstream/setup cause, then rerun the whole pair without
changing arms, corpus, thresholds or decision rule.

If one arm qualifies, it is the measured winner for DISPLAY only. If neither
qualifies, retire this attempted display solution for the frozen task with
the failed gates recorded; do not retire the backend/recovery role or claim a
winner. No synthetic-only result qualifies an arm for a live-session claim.

If both qualify, use the median of the three per-run p95 values (L), the count
of new long-lived services over the shared baseline (S), the median concurrent
RSS peak (M) and median CPU seconds (C):

1. Select an arm with 2*L <= the other's L only if its M and C are each <=110%
   of the other's. This is a material latency win with bounded resource cost.
2. Otherwise select the arm with lower S only if its L, M and C are each <=110%
   of the other's.
3. Otherwise select the arm with M at least 10% lower only if its L and C are
   each <=110% of the other's.
4. Otherwise retain both as measured co-qualified alternatives with the
   equal/tolerance or opposing-tradeoff classification. There is no automatic
   installed-path preference. This is a completed display result; it does not
   create a second comparison or leave the display run waiting on a date.

Apply each step in both directions; select only if exactly one direction
passes. Use exact integer cross-products for thresholds, not rounded summary
percentages. Report setup/recovery time, page size and the complete health
matrix alongside the decision; do not silently add them as post-hoc rank keys.
If a health conflict remains unresolved, record the measured ranking but
withhold adoption until the specified conflicting dimension is reproduced.

FINAL for the layer still requires every winner's verdict/evidence class,
wave and next_review, actual run pins, upstream E2E and invoke or retirement
reason under the resolution protocol. A DISPLAY winner/co-qualification
does not satisfy the original backend/recovery gates. Record role-scoped
results so that completed display work is not relaunched while those roles
wait for their own inputs.

## Evidence retention and amendments

Retain the input manifest, every attempted native command, configuration and
asset seals, raw timing/frame references, per-row mismatches, observer controls,
resource samples/process membership, readonly probes, notices and all six
angle records. Publish only redacted aggregate/synthetic receipts and public
source witnesses; keep real spool rows, identifiers and private capture
fingerprints in the owned private run directory.

Hash this whole amendment before running it; its catalogue entry and decision
record carry that hash. Corrections require a new reviewed, hashed amendment
before scoring. Never edit this file after the first scored run. The
backend/recovery originals remain frozen throughout.
