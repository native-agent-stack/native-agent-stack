# Prompt integrity-loss handoff and measured stream follow-ups

After #1084 landed as c67bd78bebdd48d642307e3a91d5f791a9d1aad7, one follow-up
keeps its irreversible observation-loss refusal while handing owned residuals
to fresh durable recovery promptly. No operating packet is repinned here.
Packets must not carry the integrity-loss sell refusal until the F1 correction
and its submit-budget measurement are recorded and the required review/deploy
conditions are satisfied.

## F1: leave the frozen session before retrying refused exits

run_native now ends its loop on an observation-integrity-loss reason, before
another rebalance can try an owned exit through that unusable transport.
Before breaking, it disables admissions and calls cancel_expired with
all_entries=True on the loss tick. The initial handoff patch incorrectly skipped
that cancellation; the correction restores the existing cancellation policy
before teardown or a fresh recovery start/snapshot can fail. This requests entry
cancellation; it does not claim a broker acknowledgement or fill result.
Its ordinary bounded shutdown and existing owned-residual recovery path remain,
including reconciliation, exact config and order gates.
Quote silence alone retains its prior pause/reconciliation behavior.

The resting-entry regression uses the real AdaptiveStrategy.cancel_expired
policy and GuardedSession DELETE path with a synthetic HTTP endpoint. A newly
resting buy is not yet timed out. At 9e1892b1 the loss tick reaches teardown
without requesting its cancellation; the case fails. After correction the
DELETE is observed at the loss tick, before native teardown, even when no fresh
recovery is run. Handoff remains within one tick with zero refused-exit submits.

The held-position regression uses the actual loop, real GuardedSession and
Ledger reservations, and the actual recovery routine with synthetic ports and
native lifecycle. In its virtual three-second envelope, a freeze at0.1seconds
previously left the loop running to3seconds and reserved29 submit slots for
exits that were then definitively refused before HTTP. Including the original
entry,30 of180 submit slots were active before recovery's first exit. That exit
was admitted and the fixture became flat; this is no claim of starvation.
The fixed loop hands off at0.1seconds, reserves zero refused-exit slots and
enters recovery with only the original entry's one slot used. Its first exit
is admitted and becomes flat. These observations and FIFO latency are retained
in evidence/receipts/stream-integrity-followups-20261014.json.

The original source's420-second shipped and4200-second validated envelopes
explain the exposure of the delayed handoff. This measurement does not pretend
to be a real420-second broker run or to prove the absence of starvation for
every prior state. It observes that local pre-HTTP refusals consume reservations;
the fix prevents this loop from repeatedly spending them after integrity loss.

F1 additionally requires integrity-loss SubmissionNotSent to be PERMANENT under
the exit bridge from #1091's re-scoped successor PR. #1091 is PARKED by the CC.
Permanent classification is REQUIRED and pending on that successor; its bridge
is not reimplemented here. A fail-first covering both classification and immediate
handoff must be added from its merged bytes before F1/deploy completion.

## F2: stop SDK batch processing after irreversible loss

The adopted Alpaca data consumer awaits each message in a received batch.
Giving each full-queue callback another eight-second allowance produced a
24-second receive gap for three messages. After irreversible loss the callback
now signals the SDK's supported awaited stop_ws surface, and subsequent batch
callbacks return promptly without another enqueue wait. The real pinned SDK
batch regression observes only the first eight-second deadline, followed by
zero additional wait and the SDK closing through its own consume loop.
No vendor consumer is copied or forked, and the integrity refusal stays latched.

This closes the reproduced repeated-deadline behavior after integrity loss.
It does not claim every possible healthy successful batch has a global
receive deadline, or that synthetic scheduling proves live keepalive/reconnect
performance. Stop/close failures remain failures and final teardown retains
its existing bounded handling.

## F3-F5: counter coverage, refusal diagnosis and FIFO latency

The opted combined test retains the4.05-second benchmark acceptance case and
now asserts zero stale skips. It then sends a quote older than five seconds,
asserts one skip and verifies neither delivery nor cache replacement. Removing
either parent half of the semantic union must fail this test. The counter
removal must also fail the existing stream_backpressure module. A separate
coverage-control regression fails when the old combined test accepts that
mutation; it passes only once the opted assertion exists.

The real GuardedSession POST path now preserves the fixed local integrity-loss,
quote/readiness and budget-deferred diagnoses as SubmissionNotSent. Unknown
callback/provider exception text remains masked by the generic refusal.
The definitive not-sent flag and reservation-before-guard ordering are retained;
no rejected attempt is refunded or changed into an ambiguous broker event.

FIFO items keep their existing two-field kind/raw behavior and carry private
monotonic receipt/enqueue metadata. On an order dequeue, the receipt records
count, maximum queue-only latency and maximum callback-to-consumer latency.
No order received means null maxima, not an invented zero. These fields never
set a trading number or change FIFO priority. The controlled acceptance queues
an order behind quotes and observes four seconds in both latency measures.
Real sustained throughput, shutdown delivery and reconnect acceptance remain
separate authorized native measurements.

## Primary sources and supported mechanisms

- Existing reviewed implementation and source of the defects:
  [c67bd78b runner.py:1847-1985](https://github.com/native-agent-stack/native-agent-stack/blob/c67bd78bebdd48d642307e3a91d5f791a9d1aad7/blueprints/us-equities/adaptive-paper/runner.py#L1847),
  [transport.py:957-971](https://github.com/native-agent-stack/native-agent-stack/blob/c67bd78bebdd48d642307e3a91d5f791a9d1aad7/blueprints/us-equities/adaptive-paper/transport.py#L957),
  [transport.py:1576-1661](https://github.com/native-agent-stack/native-agent-stack/blob/c67bd78bebdd48d642307e3a91d5f791a9d1aad7/blueprints/us-equities/adaptive-paper/transport.py#L1576).
  The loop, atomic Ledger budget and FIFO remain the selected implementation.
- The cancellation-order correction reuses
  [9e1892b1 native_strategy.py:1400-1422](https://github.com/native-agent-stack/native-agent-stack/blob/9e1892b142c2608b86b4e45432857fb0ab8bd70c/blueprints/us-equities/adaptive-paper/native_strategy.py#L1400)
  (all resting entries selected by all_entries=True) and
  [transport.py:946-998](https://github.com/native-agent-stack/native-agent-stack/blob/9e1892b142c2608b86b4e45432857fb0ab8bd70c/blueprints/us-equities/adaptive-paper/transport.py#L946)
  (DELETE is an allowed cancel; the integrity guard applies only to submits).
  CPython's pinned public unittest discovery/runner mechanisms, already adopted
  by scripts/run_integration_tests.py, run every tests/integration module and
  reject any skip. No replacement cancellation or test harness is introduced.
- alpacahq/alpaca-py v0.44.0 at
  [cc4cb3b7, data/live/websocket.py:222-229](https://github.com/alpacahq/alpaca-py/blob/cc4cb3b7ba50ae250e621983c2779047fb16bb28/alpaca/data/live/websocket.py#L222)
  defines the supported stop_ws signal; its
  [consume loop:238-274](https://github.com/alpacahq/alpaca-py/blob/cc4cb3b7ba50ae250e621983c2779047fb16bb28/alpaca/data/live/websocket.py#L238)
  processes the stop queue and awaits each dispatch. The trading stream uses
  [stream.py:170-182](https://github.com/alpacahq/alpaca-py/blob/cc4cb3b7ba50ae250e621983c2779047fb16bb28/alpaca/trading/stream.py#L170).
  The installed client and pinned mirror were inspected; the actual data
  consumer/dispatcher executes against synthetic websocket frames in the test.
- CPython v3.12.3 at
  [f6650f9, Lib/queue.py:133-152](https://github.com/python/cpython/blob/f6650f9ad73359051f3e558c2431a109bc016664/Lib/queue.py#L133)
  supplies the bounded FIFO; supported unittest patch.object at
  [Lib/unittest/mock.py:1632-1655](https://github.com/python/cpython/blob/f6650f9ad73359051f3e558c2431a109bc016664/Lib/unittest/mock.py#L1632)
  supplies the declared source/clock controls. No replacement queue/client,
  dependency, runtime or model is selected.

## Validation and remaining work

Each F1-F5 has an assertion-bearing fail-first on the exact landed main bytes.
F3's control also loads the old combined test because this is a coverage defect,
not a claim that its existing production counter is absent. Parent mutations
record the underlying unittest failures separately from their driver exit.
Named modules run on the pinned runtime inside a no-network namespace.
F1 handoff, the resting-entry cancellation regression and F2 SDK-batch coverage
now live in tests/integration/stream_integrity_followups.py with no skip guards.
The locked CI integration job discovers them through scripts/run_integration_tests.py,
whose runner fails on empty or skipped cases. SDK-free F3-F5 stay in the ordinary
unit module. F2 remains PARTIAL for arbitrary healthy successful batches, as above.
Synthetic native lifecycle, actual upstream SDK execution, real journal/risk
arithmetic and actual broker acceptance remain distinct evidence classes.

The historical source/measurement captures, overnight/exception classification,
legacy locator refresh and live FIFO/stop/reconnect qualification remain
Follow-ups. #1105 remains parked and its retained-budget mover prerequisite
is unrelated to this change. No operating orders, credentials, GO/STOP files,
account state or sealed operating packet are touched by these tests or this PR.
