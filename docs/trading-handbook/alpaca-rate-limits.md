# Alpaca rate limits: requests, orders and measured scope

Alpaca's documented request budget and a measured paper-order workload are
different quantities. The official support excerpt supplies the documented
limit; the approved [2026-10-13 measurement projection](../../evidence/artifacts/trading-handbook-20261013/alpaca-throughput/alpaca-throughput-evidence-20261013.json)
supplies the observed headers, requests and order-count check below. No broker
or data request was repeated to write this handbook.

## Alpaca: count requests before counting orders

Alpaca's official support article states “200 requests per minute, per
account.” The visible article date is December 2022; it was read for this
handbook on 2026-10-13. The exact visible sentence and its source URL are
retained in the [public source excerpt](../../evidence/artifacts/handbook-budget-throughput-20261013/alpaca-support-excerpt.json).

A placement and its separate cancellation consume two request operations.
Under a 200-request budget, 100 such pairs per minute is an arithmetic upper
bound before any other requests. A place-only workload has a different unit;
neither arithmetic bound establishes achieved order throughput or fills.
The support article's account-level scope does not demonstrate aggregate
simultaneous throughput across several accounts.

The scope is per account in the vendor documentation. Sharing that bucket
across keys or connections was not measured in these runs. Keep that
documented claim separate from observed response headers.
[Projection: `not_measured`](../../evidence/artifacts/trading-handbook-20261013/alpaca-throughput/alpaca-throughput-evidence-20261013.json).

## Observed response headers

Read-only probes on three paper accounts reported `x-ratelimit-limit: 200`
for account, order-list and position reads. The remaining budget decreased
199, 198, 197, 196 across successive requests, supporting a shared bucket for
those endpoints. The clock read separately reported 1000. These are measured
headers, not a guarantee of sustained order or fill throughput.
[Projection: `rate_limit_headers.summary`](../../evidence/artifacts/trading-handbook-20261013/alpaca-throughput/alpaca-throughput-evidence-20261013.json).

## Measured submit-and-cancel workload

The retained run used one paper account in premarket, one liquid ETF and
non-marketable one-share limit orders, with individual cancellations and
extended-hours enabled. Its request governor retained 20 requests of
headroom from the 200 limit, admitting a budget of 180 per minute. This is a
bounded workload observation, not regular-session or strategy acceptance.
[Projection: `capacity_run.workload`, `capacity_run.session_class` and
`capacity_run.limits`](../../evidence/artifacts/trading-handbook-20261013/alpaca-throughput/alpaca-throughput-evidence-20261013.json).

| Measurement | Recorded value | Projection field |
| --- | --- | --- |
| Accepted submissions and acknowledged cancels | 496 submits + 496 cancels | `capacity_run.counts` |
| HTTP 429 responses | 0 | `capacity_run.counts.http_429_total` |
| Consecutive full one-minute windows | 5, each with 180 completed submit/cancel actions | `capacity_run.throughput` |
| Submit-and-cancel pair equivalents | 90.000 per full minute | `derived_units.values.pair_equivalents_per_minute_full_windows` |
| Limit on every submit/cancel response | 200 | `capacity_run.rate_limit_headers_seen_during_run.write_path_reading` |
| Separate observer count | 496 listed, 496 canceled, 0 filled | `independent_observer` |

Table source: [approved measurement JSON](../../evidence/artifacts/trading-handbook-20261013/alpaca-throughput/alpaca-throughput-evidence-20261013.json).

The first full harness window contained 92 submits and 88 cancels; later full
windows contained 90 of each. Thus 90 pair equivalents describes the request
unit, not exactly 90 completed pairs in every boundary-aligned window. The
submission phase recorded 991 actions over 330.002 seconds; one cleanup
cancel brings the window totals to 992. The observer used different window
alignment and saw 181 actions in its first full window, while matching the
overall counts. Its listing check does not independently verify latency.
[Projection: `capacity_run.throughput`, `derived_units.values` and
`independent_observer.window_difference_note`](../../evidence/artifacts/trading-handbook-20261013/alpaca-throughput/alpaca-throughput-evidence-20261013.json).

The latency record retains p50, p95, p99 and maximum values; p90 is
**NOT_RECORDED**, and raw per-request latency samples are unavailable. The
harness's acceptance flag is self-reported; the separately retained observer
supports order counts only. Neither is a strategy-profit or realistic-live-
execution result.
[Projection: `capacity_run.latency_ms_from_receipt`, `headline.p90_latency`,
`caveats` and `not_measured`](../../evidence/artifacts/trading-handbook-20261013/alpaca-throughput/alpaca-throughput-evidence-20261013.json).

## Still unmeasured

Place-only capacity, the HTTP 429 onset, rates above the governed 180-request
budget, simultaneous multi-account writes, regular-session behavior and p90
remain unmeasured or unrecorded in this projection. A zero-429 result at the
governed rate does not establish the refusal threshold. The
[separate #1082 probe](https://github.com/native-agent-stack/native-agent-stack/pull/1082)
is pending work for place-only capacity and the 429 onset; its future results
must retain their own workload and window.
[Projection: `not_measured`](../../evidence/artifacts/trading-handbook-20261013/alpaca-throughput/alpaca-throughput-evidence-20261013.json).

IBKR pacing belongs to the separately owned `ibkr-pacing.md` page in
[handbook PR #1083](https://github.com/native-agent-stack/native-agent-stack/pull/1083).
Its client/adapter observations and causal diagnosis are outside this page's
Alpaca scope; use the reviewed page when that change lands.
