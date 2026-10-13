# Bounded paper-stream backpressure and honest frozen receipts

At dbe7a8da the transport's SDK callbacks use put_nowait into a 1024-event
owner queue. The owner consumer starts before the stream threads, but an
SDK burst while that consumer cannot progress loses event 1025 and latches
queue_overflow. A flat reconciled run with no fills then reports
completed_no_signals, and successful forced recovery can upgrade a failure.
The CC's October 13 incident survey found four stream-frozen stages among
25 stages; that private operating survey is a lead, not a synthetic test result.

## Primary source and correction

alpacahq/alpaca-py v0.44.0, commit
cc4cb3b7ba50ae250e621983c2779047fb16bb28:

- alpaca/data/live/websocket.py:231-274 decodes frames and awaits dispatch;
  :367-368 awaits the registered market-data callback. :124 has the SDK's
  own max_queue=1024 default, distinct from our application-event queue.
- alpaca/trading/stream.py:170-182 awaits order-event dispatch; its handler
  is awaited in _dispatch. Its websocket defaults also use max_queue=1024.
- Python 3.12 queue.Queue.put_nowait/Full is the existing thread-safe queue
  mechanism. asyncio.sleep yields the producer's loop without blocking it.

Use the SDK's existing awaited-handler contract. Each callback keeps its
one pending raw event while the same bounded owner queue is full. It
retries after yielding for at most 10 ms, returning only after insertion,
orderly shutdown, or an explicit freeze at the existing start_timeout
deadline. No larger queue, quote coalescing, silent event drop, SDK fork or
new dependency is introduced. The SDK's independent websocket queues and
all quote freshness/watchdog checks remain in effect; backpressure cannot
turn a stale quote into a fresh one or guarantee indefinite processing.

All four channels use this path: quote, order, trading status and LULD.
Cancellation before shutdown freezes queue_enqueue_cancelled, because
delivery of the waiting event is no longer guaranteed. Timeout still
freezes queue_overflow; the existing event-loss reconciliation refusal
requires a new transport and durable recovery. The synchronous internal
enqueue seam retains its immediate fail-closed overflow behavior.

## What was reproduced, and what remains unmeasured

The real callbacks and owner consumer at dbe7a8da reproduce the loss with
one in-flight sink quote and 1025 further SDK-style arrivals. The regression
blocks that sink on an explicit barrier; a second regression synchronously
blocks the owner loop while an independent producer thread fills 1024 slots
and attempts event 1025. Both require bounded backpressure and preservation
of every quote after release, and fail on the old producer behavior.

The exact synchronous frame causing each live stall is not measured here.
The consumer is created before producer threads (transport.py:1581-1586 at
dbe7a8da; these are historical coordinates, not this patch's shifted lines).
The proposed startup ledger adoption is overnight_holds-only
(runner.py:1800), disabled in the RTH controls; halt seeding runs in a worker
thread. Awaited REST snapshots also use workers. A synchronous native
startup/ledger step, a slow sink or a short producer burst can expose the
same queue imbalance. Synthetic barrier tests establish the queue failure
and repair without claiming to profile a real broker run.

## Receipt and recovery semantics

On normally returned native outcomes, terminal stream_health.frozen=true
produces status stream_frozen, even
when reconciliation is clean, positions and orders are zero, and fills are
zero. Preserve reasons, accounting, flat proof and any recovery outcome.
The status is sticky through forced recovery, durable phase is
needs_attention and CLI exit is 3. An unhealthy run can therefore never
become a successful no-signal observation just because cleanup flattened it.
Healthy flat no-fill runs retain completed_no_signals. The co-op's registry
uses the same stream_frozen vocabulary; original operating receipts remain
unchanged and can be classified by their terminal stream_health.
Existing caught startup/reconciliation exceptions retain generic
needs_attention/exit 3; extending the specific label to those paths is a
separate exception-path follow-up, not a claim of this normal-return classifier.

## Verification boundary and follow-ups

tests/test_adaptive_paper_stream_backpressure.py is synthetic: fake SDK
construction, SDK-style callback sequencing, real queue and consumer,
no credentials or broker requests. It pins a 1025-event burst, a blocked
owner loop, all four channels, timeout and shutdown, cancellation, healthy
no-signal status, frozen status and recovery/phase/exit composition.
These tests do not demonstrate real feed throughput or broker readiness.

The first local read reproduced two gaps, corrected in one review commit.
The constructor fixture now scopes the SDK DataFeed import and protocol
factory as well as clients/streams, following the existing SDK-free transport
fixture. All nine stream tests run in the SDK-free validation interpreter.
Recovery treats queue_enqueue_cancelled as observation-integrity loss,
alongside queue_overflow, before cancellation or residual sells. A real
Ledger/fake-port regression injects the reason after a snapshot: the old
head submits an exit and reports passed; the correction submits no exit and
returns needs_attention with recovery_observation_integrity_lost.

The second local read reproduced a pending-order handoff gap: an order
received while quotes fill the queue is held only by its awaiting callback,
so a queue-only reconciliation guard could clear a stale freeze too early.
The correction counts order callbacks under the existing state lock before
insertion and retains that count until the callback ends. A successfully
inserted event overlaps with its queued representation; there is no empty
handoff interval. Reconciliation checks both callback-held and queued orders.
Tests refuse acknowledgement while one or several order callbacks wait,
while an inserted update remains queued, and until all updates are removed
for processing. The exact status label remains stream_frozen.

Follow-ups: measure owner-loop startup latency and queue occupancy on a
new pinned paper run; distinguish synchronous startup from sink delay;
measure sustained backpressure and SDK reconnect behavior. Raising the
queue capacity alone or removing fail-closed overflow is not the correction.
Retain unique-sequence FIFO evidence at the pinned SDK dispatch seam and
measure actual stop/reconnect under pressure; a review's four-channel
1025-event FIFO probe passed but is not a repository regression yet.
Today's sealed operating pin stays unchanged; a new merged pin needs new
series records and observed readiness. The separate account-sized $10000
order-ceiling follow-up is not part of this stream correction.
