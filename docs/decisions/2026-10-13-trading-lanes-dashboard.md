# Trading lanes dashboard

The provisioned board is **Trading lanes**, UID `trading-lanes`, at
`http://127.0.0.1:21301/d/trading-lanes/trading-lanes`.
It extends the existing dashboard renderer and file provider. It does not
change any broker, paper recorder, STOP/ISSUER-HOLD file or order state.

## Sources and meaning

The projection reads only the authoritatively named receipt paths:

| Lane | Read-only source | Meaning |
| --- | --- | --- |
| A | alpaca-paper-2 lane-a receipt series | Latest completed substantive paper receipt; rates per stage minute |
| B | alpaca-paper forward-ready scheduled instances | Latest completed paper output; rates per stage minute |
| C, lanea, laneb | cc-overnight-mcp run events.jsonl and state.json | Trailing60-second submissions, actual fill/cancel events; latest own state and preflight equity |
| IBKR | trading-cc series end/start status and own exploratory paper receipts | Last session averages/wire peaks; a newer start changes status to active |
| I-llm | Own run events/state when present | Not live until a matching own receipt is present |

A/B count `submit` and `cancel` separately; native fill-event counts do not
derive from order submissions. The C arms count `entry_order`, `exit_order`
and `trail_order`; actual `entry_fill`/`exit_fill`/other declared fill
events supply fills. Symbols, order IDs and receipt paths never leave the
reader. Multiple run segments are represented by the most recently updated
run for that lane; earlier segments are not added to a current minute.

Cash use means deployed exposure divided by **account equity**. A receipt
with only `broker_cash_at_start` does not establish that denominator. It
remains Unavailable, even though the older report described it as equity.
Likewise IBKR cash delta is not realized P&L; the full paper accounting
receipt supplies realized P&L separately. Missing fields remain unavailable.
The older day rollups were inspected by schema only; this board does not
add rollup totals to the latest receipt and double count stage orders.

The observer writes a fresh numeric/enum snapshot every invocation. Source
time remains separate. A current observation is not a fresh trade. IBKR's
no-session status and last receipt time explicitly retain the previous
session; I-llm is not-live. Unavailable metrics use sentinel mappings (a
separate extreme sentinel for P&L, where -1 is a legitimate result).
Unknown status/reason text becomes a fixed Other code. No producer text
is copied into labels or log bodies.

The co-op's03:10Z browser acceptance passed at the initial render, with zero
panel errors, no No-data panels and only a WebGL console warning. The three
notes are corrected before the first PR read wave: rate units use explicit
per-minute suffixes, A/B rate titles say last stage (IBKR says last session),
and missing receipt time uses an explicit Not recorded fallback and mapping.
The co-op identified the actual blank as I-llm Last receipt time (panel72).
The final I-llm-only panel uses unformatted source Unix seconds, value text
mode and the exact -1 Not recorded mapping; other lane dates remain ISO.
The co-op's03:33:20Z final browser PASS closes all three notes and corrects
its earlier method: panel72 was below the viewport and lazily rendered.
Earlier empty observations without scrolling do not prove a formatter
failure. The field fallback tests qualify the explicit display contract,
not a reproduced historical browser defect. Initial source/mapping claims
are superseded by that bounded observation.
Independently, missing P&L uses a bounded exact-integer sentinel with Not
recorded mapping/fallback; the prior extreme exponent remains a historical
mapping only. That API exception was distinct from the observed blank panel.
The four assertions for these notes fail at fd43ba43 before the correction.
The subsequent lane-health feature is a separate follow-up under landing/PRE
priority; it is not claimed by this dashboard acceptance.

## Existing collector and refresh

`observability/trading_receipts.py` is an additional oneshot command of
the existing `ns2604-research-progress.service`. Its already enabled
30-second timer remains the sole refresh owner. There is **no new service,
timer or persistent process**.

The existing Collector0.162.0 tails the sanitized
`trading-lanes/observations.jsonl` spool through
`observability/trading-collector.yaml`. The source disables file-name/path
attributes. A dedicated transform clears resource/scope attributes, keeps
only the projection fields, replaces the body with that projection and sets
the fixed service name. Its existing `otlphttp/loki` exporter ships to the
installed Loki3.7.8. No raw receipt reaches the Collector. The spool is
private, locked, bounded and reset with copy-truncation after8MiB.

Native Collector supports several `--config` files. For an existing
operator-owned config, add the supplied overlay to its existing ExecStart;
validate both files together before restarting the existing Collector.
Retain every existing component/pipeline. The install-plan renderer adds the
dashboard to `GRAFANA_FILES`/`DASHBOARD_UIDS` and the observer command to
the existing research-progress service template.

For tonight's acceptance, temporary named `trading-lanes.conf` drop-ins
point the two existing services at this owned worktree. They are local
observability configuration, not a paper service. After the PR lands,
render/reinstall the existing observer unit from the new main and repoint
the Collector overlay to that retained checkout. Remove the temporary
observer drop-in when the base unit contains the new command, so the
projection is not run twice. No credential or environment file is needed.

## Native queries and acceptance

Numeric queries keep only the lane and selected value before unwrap.
This prevents changing structured metadata from turning each observer
snapshot into another series. Each target uses a ten-minute window,
including explicit unavailable/no-session observations. The IBKR wire
panel draws45/s governor and50/s broker cap as threshold lines, never as
measured wire values.

Local API checks verify provisioning and all65 target expressions. The
co-op separately opens the board through chrome-devtools, screenshots it,
and verifies console/network errors and every panel's recent data. An API
check alone is not a browser acceptance claim. CC alone updates
`pages/cc-now.json`.

## SOTA sources

- Grafana installed13.2.3, native health commit
  `90ffed056f0884267356c12a0eeb72a022af53f1`.
  [Version-pinned provisioning documentation](https://github.com/grafana/grafana/blob/v13.2.3/docs/sources/administration/provisioning/index.md):
  file dashboard providers, UID preservation and updateIntervalSeconds.
  The existing provider polls every30seconds.
- OTel Collector Contrib installed0.162.0:
  [filelog receiver](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/v0.162.0/receiver/filelogreceiver/README.md)
  describes file tailing, start_at, storage, file attributes and copy-truncate handling;
  [transform processor](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/v0.162.0/processor/transformprocessor/README.md)
  supplies supported keep_keys/set operations and propagate error behavior.
- [Collector configuration](https://opentelemetry.io/docs/collector/configuration/):
  multiple configuration files merge natively; existing exporters and pipelines are retained.
- Loki installed3.7.8/revision09e6ce2f:
  [LogQL range aggregations](https://grafana.com/docs/loki/v3.7.x/query/metric_queries/)
  and [label keep expressions](https://grafana.com/docs/loki/v3.7.x/query/log_queries/)
  supply the query path; live native target execution qualifies its actual syntax.
- Native nas provisioning mechanism at base
  `329985de1c8dccf0df7491373d0d9932eaa723d4`:
  `observability/ns2604_dashboards.py`,
  `config/observability_config.py` in the retained install plan, and
  `ns2604-research-progress.service/.timer`. This task extends those
  maintained paths instead of adding a second observability scheduler.

## Verification and limits

Fail-before dashboard test: rc1 because no Trading lanes board existed.
After render registration: rc0. Initial receipt seam test: rc1 because the
projection module was absent; then native receipt arithmetic/field exclusion
passes. IBKR next-session status fixture: rc1 before start-line support,
then rc0. A first23-test run found the added ExecStart preceded the existing
test's progress command; moving the addition to the end preserves the
interface and the rerun passes23tests. Later focused checks include the
next-session case separately.

Collector merged-config validation returned0 before applying the overlay.
The existing Collector stayed healthy after restart. Grafana API confirmed
provisioned72panels. All65 native target queries returned exactly one
series, after removing per-observation structured dimensions. Browser
acceptance remains the co-op's record. Real-source receipt freshness and
missing equity/reason fields remain visible; no fabricated values qualify
the board.

No inference/model comparison, broker call, live endpoint, new account,
paid data or hosting occurs in this work. Publication evidence records
counts and statuses only, without actual financial balances or private
source paths.

## Native receipt correctness correction

The local review at f0337688 (unchanged own code after the registry rebase
to8e07833e) reproduced four data defects despite passing rendering tests.
The browser acceptance was rendering/freshness/layout, not correctness of
each value. This correction preserves that evidence distinction.

| Native producer/witness | Defect before correction | Corrected behavior |
| --- | --- | --- |
| cc-overnight-mcp/calc_session.py:239 log; run-lanea-post-20261013/events.jsonl:35 preflight_refused and:57 final_flat; run-laneb-post-20261013/events.jsonl:34/:52 | Terminal/refused runs appeared Active then Stale | final_flat is Ended; preflight_refused is Blocked before freshness fallback; a later preflight_ok reopens the same run as Active |
| ibkr-lane-build/ibkr_series4.sh:43/:45 (also ibkr_series.sh:40/:42) | An end with no JSON receipt left its earlier start Active forever | End timestamp/exit code is processed independently of metrics; failed end is Blocked, and no older-session metrics are carried onto it |
| ibkr-lane-build/series_line.py:12 receipt basename | Latest-by-mtime accounting was combined with another session's rates/wire/time | Accounting comes only from the uniquely matching receipt named by the selected session's summary; missing/ambiguous binding remains unrecorded |
| cc-overnight-mcp/calc_session.py:261 trail_cancelled handler; run-rth/events.jsonl:58 trail_cancelled and:187 entry_cancelled | Actual cancellation events produced zero count | Both native cancellation names count only within the recorded trailing minute |

The native logger accepts event kinds through its own log command; the
retained emitted event files above establish the exact lifecycle/cancel
vocabulary. Tests preserve that schema's ISO timestamp and the launcher's
actual end/no-receipt/receipt-basename shape, with harmless synthetic times
and accounting values. No private event body, ID, source hash or producer
diagnostic is copied into this record.

At exact8e07833e, the four current corrected tests fail first: rc1,4tests,
7failed subcases. The native baseline source is retained separately for that
check. After the correction, the9-reader-test module passes; the PR's named
reader/dashboard/grant modules pass55tests in7.667seconds. Only these four
corrections, their regressions and record/bindings share the one released
fix commit. Lane-health changes stay on their own branch.

## Version-bound producer references

The out-of-tree producers are **unversioned**: these observations are not
repository pins. The private, sealed manifest
`ns2604-pr1106-producer-refs-20261014` binds each reference below to its
source path, SHA256, byte count and exact mtime for the original four rows.
The block-writer row uses its separately named status-producer manifest
described in the current-series correction below. The original is retained with the
lane's read-fix packet as `producer-references.json`. No producer body was
copied. Private paths, digests and diagnostic text stay out of publication.
This metadata identifies the inspected version; it does not supply a public
source checkout or independently reproduce native event/cadence evidence.

| Producer | Version-bound source reference | Inspected source locations |
| --- | --- | --- |
| calc_session.py | source-ref:ns2604-pr1106-producer-refs-20261014/calc-session | 239, 261 |
| ibkr_series4.sh | source-ref:ns2604-pr1106-producer-refs-20261014/ibkr-series4 | 43, 45 |
| ibkr_series.sh | source-ref:ns2604-pr1106-producer-refs-20261014/ibkr-series | 40, 42 |
| series_line.py | source-ref:ns2604-pr1106-producer-refs-20261014/series-line | 12 |
| ibkr_pre_series.py | source-ref:ns2604-pr1106-status-producer-refs-20261014/block-writer | 41-45, 287 |

These references qualify the earlier correctness citations above. They do
not convert the missing native witnesses into independently verified
evidence. The delta review determines whether this retained reference is
sufficient; a required repository pin would need producer-owner publication.

## Read-wave integration and paper outcome correction

The completed read wave requested the consumed-config integration repair,
paper outcome preservation and version-bound producer references. The
existing install-plan checker now validates Trading lanes through the exact
native renderer source/destination pair and its actual source asset. It
still rejects an absent asset, missing/wrong binding or omitted transport.
Paper receipt selection respects recorded outcomes independently of optional
numeric groups; absent measurements remain unavailable. Native failure
outcomes use the existing Blocked display mapping.

Primary repository source: `native-agent-stack/native-agent-stack` at
`eb1b4183a9918ed432a5ca5b0ab6c242c793b0ac`,
`evidence/artifacts/new-wsl-install-plan-20261002/check_plan.py:678-704`,
`config/observability_config.py:30-40` within that plan, and
`blueprints/us-equities/adaptive-paper/runner.py:2130-2134,2771-2778`.
The installed Grafana13.2.3 file-provider contract remains the version-pinned
upstream source listed above. No additional observability runtime is added.

Four regression tests fail against the released baseline and pass after
the correction: the consumed-config binding test, optional-measurement
outcome selection, public native failure receipt mapping and producer
reference coverage. The first three exercise installation/reader behavior;
the last guards citation coverage, not independent private source fidelity.
Reader tests use already published repository fixtures. No private
reproduction bodies, producer bytes or digests are added to public evidence.
Follow-ups concerning liveness, freshness/recovery, native witnesses, query
cost and IBKR explanatory text remain deferred to their cued work.

## Current series status correction (2026-10-14)

The CC released one status-only correction after the completed read wave.
The IBKR adapter accepts the current block completion format as well as its
retained session format. Its default discovers only top-level filenames
matching `(ibkr|rth|pre)-series-` plus eight digits and `.status`, and selects
the newest mtime (filename breaks ties);
an explicit --ibkr-status file remains a single-file override. Block receipt
diagnostics are never exported, and missing metrics remain unavailable.
No exported field or other pending review disposition changes in this round.
The mixed-format synthetic regression fails on71ac2733 and passes after.

Primary source: standalone ibkr_pre_series.py:41-45,287, the existing producer's
block completion writer, at the inspected version identified by
source-ref:ns2604-pr1106-status-producer-refs-20261014/block-writer.
The private manifest producer-references.json in the named
landscape-live-foundation.pr1106-provision-fix-20261015 packet preserves the
original status-fix path/SHA256/size/mtime binding. No source body or diagnostic
was copied. Earlier
session grammar remains bound by the producer references above. Native
file transport still follows Collector0.162.0 filelog/transform references.

## Install route and status-copy correction (2026-10-15)

The clean install's otel action now provisions the same native Trading
lanes receiver/transform/pipeline as the retained acceptance overlay. It
ships in the installed otel.yaml, so the supported single-config launch and
validation path carries the route without a manually installed drop-in.
Existing source receivers/transforms/pipelines are retained. Operator-owned
configuration custody remains with the renderer's existing refusal path.

The renderer fail-first test installs both otel and grafana into empty
synthetic roots and verifies the generated data route plus its dashboard.
Installed Contrib0.162.0 validates that generated config. The configuration
uses its pinned filelogreceiver/transformprocessor contract listed above;
no new transport or runtime service is introduced.

IBKR's No session statement now comes only from its status-code mapping.
Receipt-time and wire prose remain neutral when a newer start becomes Active.
The status-copy and block-producer-reference regressions also fail before
this correction. Producer source identity is metadata only and unversioned;
the named reference makes its inspected revision identifiable without
publishing private source bytes or digests.

## Per-lane receipt freshness correction

The CC04:21Z measurement reproduced a false Stale receipt alarm: C's
overnight unit was active, while its rounds were about five minutes apart
and the board used180seconds. The observer's30-second refresh is not the
producer's round interval. Each event lane now uses at least twice its
own measured interval. This is receipt freshness, not a unit-health probe.

| Lane | Own interval | Retained source / measurement | Stale threshold |
| --- | --- | --- | --- |
| C | About5m12s in CC's latest three rounds; cumulative median295.237915s | run-overnight-20261013/events.jsonl:3-93;91 round events,90 positive gaps | 720s, CC's12-minute limit |
| lanea | Median558.335276s | run-lanea-post-20261013/events.jsonl:3-48;18 round events,17 positive gaps | 1200s (20min) |
| laneb | Median374.841485s | run-laneb-post-20261013/events.jsonl:3-49;25 round events,24 positive gaps | 780s (13min) |
| I-llm | Unrecorded | No retained own run events at this measurement | No guessed limit; Not live without a receipt, Cadence unrecorded for non-terminal receipts |
| A / B | Not a polling inference | Own completed paper receipt status | Recorded status, last-stage rates |
| IBKR | Not a polling inference | Own native session start/end status | Recorded session status, last-session rates |

Measurement uses only native rank_round/no_selection_round timestamps, in
file order, and the median of positive adjacent gaps. It exports no source
body, account identity, source path or financial value. The retained sources
are already named above; these bounds are measured configuration for this
board, not an inference that every irregular gap is a stalled producer.
If producer cadence changes, remeasure and update that lane's bound before
claiming freshness. I-llm requires that qualification before an Active or
Stale label. Completion/refusal remains authoritative before any age rule.
Panel descriptions state each policy; no lane retains an unsupported180s
limit. Source time remains the producer time, and rates still use the actual
trailing minute even when an older receipt remains within its cadence.

At8e7cbaaa the five-minute C regression fails first (rc1, one test with
three failures at ages300/624/719seconds). After the C-only correction it
passes (rc0). The arm/unknown-cadence test then fails first (rc1, six failed
subcases); after the per-lane correction both pass. Boundary fixtures cover
the exact stale limits and preserve terminal/refused status and source time.
