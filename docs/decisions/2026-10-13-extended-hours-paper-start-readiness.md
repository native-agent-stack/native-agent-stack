# Extended-hours paper start readiness and stage-long benchmark liveness

The CC approved an opt-in 30-second start window and five-second selected
benchmark readiness threshold after October 13 POST runs failed or remained
admission-paused. The ordinary order-age bound remains three seconds. This
change activates no series or unit; new PRE bindings use a landed pin and
retain their own account/root/predecessor and STOP conditions.

## Evidence and primary sources

At native-agent-stack dbe7a8da1bb497570471e2b9d0dcfe56bbdc56e9,
runner.py:777-781 is the REST benchmark start gate. It runs again for paper
before constructing the stream (:2623-2640). A transport-only longer window
cannot fix its benchmark_quotes_not_ready refusal. The s3 paper receipt
had that reason and no native stream fields. The s1/s2 terminal receipts
record 300.50/300.54 seconds, 25890/10362 quotes and zero native rejections;
quote_stale was latched while terminal fresh_quotes was true. That snapshot
does not establish a whole-stage absence of fresh quotes. The private
operating receipt paths/hashes are held in coordination, not published here.

The reported benchmark ages were IWM 2.66/4.05 seconds and SPY/QQQ mostly
below 1.6. Initial threshold = ceil(max reported age) = 5; startup window =
max(2 * existing 15-second stream window, 2 * threshold) = 30. These are
initial deterministic observation bounds approved by the CC, not measured
interarrival quantiles or a guarantee of future readiness. The separately
approved SPY/QQQ config changes the regime-input mean, not the freshness rule.

Official alpacahq/alpaca-py 0.44.0,
[`cc4cb3b7ba50ae250e621983c2779047fb16bb28`](https://github.com/alpacahq/alpaca-py/blob/cc4cb3b7ba50ae250e621983c2779047fb16bb28/alpaca/data/historical/stock.py#L163),
stock.py:163-182 supplies get_stock_latest_quote with a symbol-list request.
The existing guarded read-only SDK clients, endpoint gate, request observer
and authorizer remain in use; no HTTP client or broker adapter is replaced.
data/live/websocket.py:121-128 takes the caller's websocket params; its
awaited handler at :367-368 remains unchanged.

Native LiveNodeConfig's supported timeout_connection_secs is used through
the existing native_adapter.build_node interface. Installed NautilusTrader
2.0.0rc5 is the executable test runtime; maintained upstream source is
[nautechsystems/nautilus_trader at 1b0a49d2792a9432a3aca3fcb617ce7a630d905e](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/crates/live/src/python/config.rs#L1114):
crates/live/src/python/config.rs:1114-1159 exposes the Python timeout;
[crates/live/src/node/mod.rs:433-464](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/crates/live/src/node/mod.rs#L433)
shares its deadline across data and execution client connection.
Source-review pin and installed runtime acceptance are distinct evidence.

## Scope and behavior

The only supported optional config is:

```json
"extended_hours_start_readiness": {
  "window_seconds": 30,
  "benchmark_quote_timeout_seconds": 5
}
```

Unknown/missing keys, null, booleans, floats or other values refuse at load.
It requires the coordinated extended-hours session flags. It applies only
to actual PRE/POST PAPER, never RTH, standalone preflight or recovery. Absent
blocks preserve config bytes and all default call arguments. The readiness
block is excluded from lane A's next-trial frozen trading signature beside
the session flags: opted PRE/POST and RTH trials continue the same journal
without resetting fees, cash or risk state. Recovery binds exact bytes and keeps
its existing separately registered owned-sell age semantics.

Read-only preflight polls selected benchmarks through the native SDK, no more
often than every two seconds within a monotonic 30-second window. It reserves
five GETs for the final snapshot; the cadence lengthens for larger universes
to spread the remaining request slots across the window. Every GET uses the
existing request authorization/observer and its 50-request ceiling; STOP or
the deadline refuses. Once quotes qualify, re-read account, clock, positions
and open orders, verify the same identity, then re-read benchmark quotes.
Every existing cash/entitlement/clock/session/universe/flat check still runs
on that refreshed observation. A still-stale final read refuses admission.
Startup diagnostics record window, threshold, quote-read count and refreshed
account-state proof; identifiers and credentials are not exported. Assets are
read once before the wait; they are not refreshed after polling. A request-bound
SafetyError publishes not_started with zero submitted orders.

The transport independently receives start_timeout 30 and selected-benchmark
age 5 throughout the extended-hours stage, including health and the stale-quote
watchdog. An opted PRE start refuses if duration plus cleanup plus the existing
60-second allowance crosses 09:30 ET, using the broker-time session boundary.
Only required benchmark quotes use that stream observation age;
other symbol quotes retain quote_timeout 3. Health checks the vendor quote
timestamp too, avoiding a second five-second grace period after receipt.
The native outer connection timeout becomes 40 (30 + the existing 10-second
connection allowance), so it does not cut off the inner startup wait. Only
that registered extended-hours transport may select 40; defaults stay 10.
This longer startup window interacts with #1084's original callback deadline,
which used start_timeout. Its ruled blocker commit caps that wait at eight
seconds, below the ten-second ping timeout, independently of start_timeout.
Whichever PR lands second must add a combined regression for the 30-second
readiness window with that eight-second handler bound. SDK ping settings remain unchanged.

Strategy feature freshness, RiskLimits and the final transport wire guard
still require the shipped three-second order quote. A five-second benchmark
may establish readiness without becoming an executable order price. The
pre-wire bound is independently tested for buys and sells. Existing explicit
owned-sell exit_quote_max_age_seconds is neither added nor widened here.

## Validation and practical limits

Evidence class: synthetic/local integration. Tests use official SDK request
serialization with mocked HTTP, real guarded client callbacks and native
configuration types; no broker, credential, GO, unit or account-state call.
The nine-test pre-wiring module was run against the unchanged base as a
fail-before control; the later tenth wiring test was not part of that control.
The tests pin strict schema/default/RTH scope, a 4.05-second
benchmark observation, request counts and refreshed cash proof, deadline and
STOP, selected-only stream acceptance, vendor-time aging, native outer window
and strict real final-wire refusals. Existing transport/credential/runner
tests protect default behavior.

The nine-test pre-wiring regression module on unchanged base 329985de ran
rc 1 (10 refusal failures including subcases, eight unsupported-API errors);
the same module at the implementation passed. A subsequent main-call wiring
test checks PRE/POST paper-only forwarding and no state creation at a mocked
network refusal. The bounded existing transport/credential/runner selection
ran 382 tests OK before the outer native-window change; the focused readiness
plus real native adapter selection then ran 63 tests OK after it.

Thirty seconds cannot make a sparse feed produce fresh pricing. A stage may
start and safely place no orders if benchmark features or asset quotes never
meet their unchanged execution bounds. No native paper throughput or trading
acceptance is claimed by these synthetic tests.

## Follow-ups

- New PRE series/records supersede the sealed dbe7a8da pp2b bindings only after
  this code lands and the owning operator establishes current ready checks.
- #1084 separately corrects quiet-market outcome classification, callback
  keepalive bounds and recovery event-loss checks. Neither PR deploys itself.
- #1091's whole-share sell fix is owned by the handed-over lane; no change to
  its branch is part of this PR.
- Measure actual PRE interarrival/startup distributions and request use;
  replace these initial bounds only through a new evidenced record.
- Extend refresh evidence to assets if required by a future operating protocol;
  the current final snapshot refreshes only account, clock, positions, orders and benchmarks.
- Extend branch coverage of malformed refresh responses and identity changes;
  synthetic acceptance does not establish native feed availability.

A stale executable price, default/RTH widening, old flat/account proof after
waiting, budget bypass or unbounded poll overturns this implementation.
