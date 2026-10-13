# Overnight admission and lifecycle through the supported BOATS REST SDK

Paper acceptance: **NOT_RUN**. Base: native-agent-stack
`c63c83a822f2687c3e7aed2d3b3ede0413119c9b`. This record describes the staged
implementation for the CC's 03:33Z decision (a), routed to ns-seeds by the
co-op's `overnight-arming-20261013/handoff-mizo.md` and owner-free builder brief
(SHA256 `84db2e91e9b38ae864b2b260c669f03c031fc0397499b2c75a128c0879290289`).

The trigger is an owned native LIMIT queued at a session boundary: previously
OVERNIGHT always produced `entry_dispatch_session_unavailable`. The staged
change admits only an explicitly enabled REST BOATS diagnostic, in an actual
XNYS overnight window, with fresh quote and separate broker-asset eligibility
and halt carrier, plus the exit/lifecycle paths implemented in the same tree.
Any missing precondition retains the refusal before reservation/POST. Default
stream configurations retain their existing windows and BOATS stream refusal.

The maintained upstream already ships REST latest quote and asset reads. We
use those interfaces and existing guarded HTTP Sessions, with per-symbol
bounded polling, without a BOATS websocket implementation or SDK fork. The
pinned SDK's stock stream still restricts feeds to IEX/SIP. Streaming becomes
a new candidate when a maintained SDK release admits BOATS, followed by the
same guard tests and actual authenticated acceptance; the enum alone is not
evidence of that capability.

The local default is flatten by 03:50 ET, with no planned PRE carry. Under the
CC's 2026-10-13 P1-B ruling, a residual has exit-only PRE/RTH/POST admission.
Native sell factories use NautilusTrader `reduce_only=True`; non-node recovery
uses the existing ledger's held/unreserved sell bound. PRE/POST use extended-hours
LIMIT DAY; RTH uses LIMIT DAY without extended hours. The supported REST request
selects SIP outside OVERNIGHT, and requires fresh ordinary active/tradable asset
state and standing halt checks. The existing trial/recovery cleanup deadline and
all risk history remain intact. A new entry outside OVERNIGHT is still refused.
The bounded owning-lane diagnostic remains flat by 07:45Z as defense in depth;
real SIP entitlement and residual execution acceptance remain **NOT_RUN**.
A broker accepted
entry remains resting; a halt/cutoff independently cancels it. A held halted
exit remains resting, and a foreseeable status/quote refusal preserves it
through repricing. Carry cutoff, 04:00 boundary and broker DAY expiry persist
before POST in the ledger; schema 4 prevents older engines from ignoring these
clocks. Residual positions at the boundary/expiry produce an attention and
handoff notification and freeze the instance. A flat new trial clears old
clocks; an unresolved one cannot clear them. Client trail/time/force orders are
extended-hours marketable LIMIT sells at or below bid. X1 is not admitted in
an overnight plan. Order shape supports simple DAY/GTC only in this explicit
adapter; other transports keep their DAY-only contract.

## Primary sources

- [NautilusTrader 2.0.0rc5](https://github.com/nautechsystems/nautilus_trader/tree/1b0a49d2792a9432a3aca3fcb617ce7a630d905e),
  commit `1b0a49d2792a9432a3aca3fcb617ce7a630d905e`, read first-hand:
  `python/nautilus_trader/live/clients.py:451-455` queues an order-denied event;
  it does not stop the node. `crates/live/src/python/node.rs:175-183` signals
  node stop and hosted-run shutdown. Our `NativeSession.fail` invokes this stop
  path only for exit residuals at the overnight dispatch boundary; stale entries
  are denied without liquidating another held position.
  `crates/risk/src/engine/mod.rs:727-735,743-771` defines an eligible reducing
  submission as reduce-only, opposite to an identified open position, with positive
  quantity no greater than held. `:2305-2328` applies it in REDUCING state.
  `crates/model/src/enums.rs:1987-1988` states the REDUCING contract. Native
  orders use the engine flag; recovery's existing ledger reservation enforces
  the same held-quantity semantics without a node.
  `crates/model/src/python/orders/limit.rs:260-264` exposes that constructor flag
  as the Python getter `is_reduce_only`, which native dispatch reads. A native
  entry-then-PRE-exit regression exercises the actual getter and engine.

- [alpaca-py v0.44.0](https://github.com/alpacahq/alpaca-py/tree/cc4cb3b7ba50ae250e621983c2779047fb16bb28),
  commit `cc4cb3b7ba50ae250e621983c2779047fb16bb28`:
  `alpaca/data/historical/stock.py`, `StockHistoricalDataClient.get_stock_latest_quote`;
  `alpaca/data/requests.py`, `StockLatestQuoteRequest`;
  `alpaca/data/enums.py`, `DataFeed.BOATS`;
  `alpaca/trading/client.py`, `TradingClient.get_asset`;
  `alpaca/trading/models.py`, `Asset.attributes`;
  `alpaca/data/live/stock.py:47-48`, the IEX/SIP restriction;
  `alpaca/common/rest.py`, supported request/retry behavior. The existing
  `_sdk_client` pin check, no SDK retry and guarded HTTP path remain the boundary.
- [Alpaca Orders at Alpaca](https://docs.alpaca.markets/us/docs/orders-at-alpaca.md),
  source fetched with the context-mode HTTP reader on 2026-10-13:
  extended-hours LIMIT DAY/GTC; bracket/OCO exclusions; trailing stops do not
  trigger outside regular hours. The contract never places a broker stop.
- [Alpaca 24/5 Trading](https://docs.alpaca.markets/us/docs/245-trading.md),
  source fetched on 2026-10-13; updated `2026-10-12T06:43:44Z` in that source:
  overnight eligibility/halt asset attributes, trade date and DAY carry to
  20:00 of the upcoming trading day. The local cutoff is stricter than this
  broker carry permission and is an owner policy, not a vendor fact.
- [exchange-calendars 4.13.2](https://github.com/gerrymanoim/exchange_calendars/tree/dbe38b1f6887434bbdd1a7d2df6ff8f1742a048a),
  commit `dbe38b1f6887434bbdd1a7d2df6ff8f1742a048a`:
  `exchange_calendars/exchange_calendar_xnys.py` and native session APIs;
  existing `sessions.session_at` rejects phantom holiday/weekend trade dates.
- [uet#63 Decision 2](https://github.com/seathatflowsinourveins/us-equities-trading/blob/f8c607bc1f1f0205fdc87095f47df150d2f78117/docs/decisions/2026-10-10-halt-exit-policy.md),
  pin `f8c607bc1f1f0205fdc87095f47df150d2f78117`: held exits remain resting
  during a halt. The carrier/quote freshness rules apply before any replacement.

## Evidence and remaining acceptance

The 2026-10-13 cross-family execution review superseded the earlier isolated
PRE-exit and host-local-log conclusions with reproduced same-controller and
private-preimage defects. The correction derives a SELL's current admitted
calendar close at reservation and pending revalidation and refreshes the reused
controller before recovery. It keeps immutable carry/expiry and cleanup budgets.
Residual admission precedes adaptive exit cancellation/repricing in every
session. Asset status is delivered immediately after its SDK read even when the
quote fails, and each symbol polls independently. These mechanisms still use
the pinned SDK/calendar and the engine's reduce-only flag cited above.

The privacy correction adopts `scripts/host_receipts.py:sanitize` and publishes
sanitized log preimages before computing output hashes, following the repository's
#161 published-byte rule and the CC's 16:02Z ruling. Both receipt registries bind
those published bytes; historical public source inputs stay separately available.
A generic receipt regression rejects a digest whose preimage is absent from the
published set, including an a0491701-style private-preimage publication. No
history rewrite is performed; the fast-forward correction and squash keep main
clean.

Guard evidence is synthetic, using hermetic protocol fixtures and temporary
SQLite journals, including close/reopen and the halted/unknown cutoff fixture.
The committed native dispatch method also runs in CI against protocol fixtures
without native dependencies; the actual pinned NautilusTrader runtime exercises
the native queued-BUY OVERNIGHT admission/refusal. None is a broker run.

CI-layout verification uses base CPython 3.12.3, a scratch home, `env -i`, and
the hash-locked `.github/requirements-calendar.txt` in that user's site. It keeps
alpaca-py/NautilusTrader absent. Interpreter-spawning tests are run in that layout
so a `-s` dependency regression cannot be hidden by a local native environment.
Mutation results and final run summaries are retained in the validation record.
The candidate record is
`blueprints/us-equities/adaptive-paper/overnight-arming-validation.json`.

The wire check uses the existing transport `_on_owner` hook to return an SDK
worker's final admission to the owning loop. It persists the actual wire-boundary
midpoint/clock before HTTP; execution receipts retain source execution time,
local observation time, signed midpoint slippage and latency, deduplicated by
execution identity across reopen. Missing execution timestamps keep latency
unknown. The callback and SQLite persistence are fixture-tested; no broker
clock/latency acceptance follows from them.

The actual cadence receipt (sweep wall time, per-request p50/p99), fresh BOATS
parser/account entitlement/linkage, order/fill/rejection/latency and midpoint
slippage receipts, and the owning T15 overnight diagnostic remain native
acceptance work after landing on the readiness trigger. Quote/status age at
each decision and trail-high changes are journal events; the one-second target
cadence is not a measured delivery guarantee. The order stream retains its
existing ownership; no BOATS market-data stream owner is claimed. No strategy
performance, live authority or change to frozen N2 is supplied by these tests.

## Review round two: event identity, venue scope and owner scheduling

The cancellation latch consumes Alpaca's actual `order_cancel_rejected` event,
including its `trade_updates` envelope and still-live nested order. The official
[Alpaca streaming source at 07f9c20b](https://github.com/alpacahq/alpaca-docs/blob/07f9c20b57f8e7a9162251e2edbe446094c15ef7/content/api-references/trading-api/streaming.md)
names that event; the source is dated 2022-04-20, and direct access to the current
documentation returned HTTP403 during this correction. The installed alpaca-py
v0.44.0 at the pin above accepts `Union[TradeEvent, str]` in
`alpaca/trading/models.py:633-646`. A synthetic real-shape stream test reaches
the production consumer and Controller rather than substituting a renamed event.

An asset's `overnight_halted` flag applies only in the real calendar's OVERNIGHT
session. Standing trading-status and seeded halts remain effective in every
admitted session. Fresh active/tradable carriers permit owned daytime residual
sells even if the overnight venue flag remains set; stale and missing carriers
still refuse. The scan contract adopts the already-reviewed mover child's
`overnight_minute`, opt-in rule parsing and calendar trade-date primitives.
Full mover configuration, command timing and overnight diagnostic enablement
remain with that separate child; PRE parsing and scans retain their defaults.

The owner tick schedules one tracked cancellation per live entry and returns
its cutoff/expiry decision without waiting for request budget or DELETE I/O.
The supported [Python3.12 asyncio.timeout](https://docs.python.org/3.12/library/asyncio-task.html#asyncio.timeout)
context bounds each coroutine to five seconds; timeout or broker refusal
releases its retry latch. Both native runners cancel and join these tasks before
stopping their port. This is a synthetic owner-loop guarantee, not measured
broker latency or proof that cancelling an asyncio wrapper interrupts SDK I/O.
The original transport teardown did not retain or join the synchronous SDK
DELETE worker after that timeout. Astra's pinned-SDK probe reproduced a second
DELETE and session closure while the first worker remained live. That ownership
claim is superseded by the correction below.

CC correction216 at 18:29Z withdraws correction215's proposed history rewrite.
This correction is a normal fast-forward child of448db566 and preserves published
history. Current-tree and PR-body prefix checks accept the six historical values
only as private audit inputs; the public regression derives synthetic values and
contains no blacklist. Historical public input source blobs are retained as
published preimages. Derived registry hashes are checked by their owning listing
contract rather than treated as execution inputs in the older fix receipt.
The historical SHAs remain viewable; no purge or broker acceptance is claimed.

## REST cancellation refusal

A broker DELETE refusal followed by a still-live order is a failed cancellation,
not an acknowledgement. The transport now raises its bounded TransportError for
that result, an unobserved broker identity, or missing post-DELETE finality.
The controller's tracked cancellation task releases its retry latch on that
failure. A synthetic SDK422/live lookup followed by204/canceled proves the
entry stops working at cutoff without a rejection stream message. Confirmed
terminal404/422 observations and successful204 acknowledgements remain data.
This retains Alpaca's documented DELETE semantics through the installed SDK;
no broker acceptance or cancellation-latency bound is claimed.

The CC's20:12Z cue approves one blocker commit and a leased conflict-only rebase
onto the named main base in one push. Historical public inputs that main changes
are preserved before rebasing, so old execution receipts remain verifiable.

### SDK cancellation ownership correction

Astra's real-SDK probe at ea0a51a6 and the builder's regression at published
8f64d5a4 establish the missing boundary: cancelling an asyncio await does not
interrupt a synchronous SDK DELETE. The supported CPython3.12.3 implementation
uses executor work for `asyncio.to_thread`
([threads.py:12-25](https://github.com/python/cpython/blob/f6650f9ad73359051f3e558c2431a109bc016664/Lib/asyncio/threads.py#L12-L25));
a running concurrent future cannot be cancelled
([_base.py:364-372](https://github.com/python/cpython/blob/f6650f9ad73359051f3e558c2431a109bc016664/Lib/concurrent/futures/_base.py#L364-L372)).
The installed pinned SDK's synchronous `TradingClient.cancel_order_by_id`
remains the DELETE implementation
([alpaca-py0.44.0 client.py:217](https://github.com/alpacahq/alpaca-py/blob/cc4cb3b7ba50ae250e621983c2779047fb16bb28/alpaca/trading/client.py#L217)).

The transport now retains one shielded cancellation operation per owned client
ID, including its actual concurrent future and final-state reconciliation. The
controller's five-second timeout releases only its wait; another tick awaits
that same transport operation instead of authorizing another DELETE. Its
pending latch stays set until the actual operation resolves, including if a
terminal stream observation arrives while the SDK call is still running. A late
completion still forwards the final broker observation. The owner tick remains
nonblocking and continues cutoff, expiry and flatten decisions.

On shutdown, the transport refuses new cancellations, cancels operations still
waiting for its operation lock and cancels executor futures not yet started.
It awaits started operations and their final lookups, then joins its supported
ThreadPoolExecutor before closing the SDK HTTP session
([thread.py:219-241](https://github.com/python/cpython/blob/f6650f9ad73359051f3e558c2431a109bc016664/Lib/concurrent/futures/thread.py#L219-L241)).
The copied ContextVar preserves the existing per-order budget identity. This
joins existing work; it does not claim that a running HTTP request is interruptible.

The adaptive strategy and mover book mirror the background operation's pending
mark separately from their own engine cancellation mark. When the shared
operation resolves, the next strategy pass clears only that mirrored mark;
failure therefore leaves timeout, halt, kill-switch and corporate-action cancel
paths available before the carry cutoff. A pre-existing engine cancel mark is
preserved. This closes the reader's q9 strand case under the CC's21:37Z ruling.

The real-SDK regressions control only synthetic HTTP/budget boundaries and seed
the durable fixture with the SDK's required UUID. A blocked DELETE uses the real
five-second owner timeout; a blocked budget and late completion cover the retry
and shutdown races. A queued operation is cancelled before any SDK request.
Guard-removal controls separately exercise loss of shielding and loss of queued
operation cancellation. No broker, actual credential or paper acceptance runs.
The CC's21:13Z P1-exception approval authorizes one normal forward correction on
8f64d5a4, followed by one delta review wave. The separate mover child stays held.

The combined five-case SDK module drives a real422/live lookup after a halt,
lets that operation resolve after its owner timeout, clears the halt, and drives
the production `AdaptiveStrategy.cancel_expired` method on a protocol owner.
It proves a second cancellation can start through the ordinary order-timeout
path before `flatten_at`, after the first operation has finished. The owning
reader's q9 probe is measured separately at exact8f64 and the combined sources.
Four CI-visible production-method controls cover both strategy mirrors and the
preservation of unrelated engine cancels. This is deterministic fixture evidence,
not an rc5 node or live-broker acceptance claim for that particular strand case.
