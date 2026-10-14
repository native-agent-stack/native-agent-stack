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
