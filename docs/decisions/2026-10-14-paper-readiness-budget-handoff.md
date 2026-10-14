# Preserve opted startup reservations at the trading handoff

The October 14 correction transfers every active startup reservation, including
refused starts, into trading's existing request budget exactly once. With 180
retained failed-start rows and 12 successful preflight GETs, only eight further
reads fit the 200-request window. The prior implementation replayed only the
current invocation, so it allowed another 30 reads: 222 requests in that window.

The request-only root journal remains the authoritative budget after handoff.
Trading reservations also reserve there before any GET, submit or cancel;
the trading journal retains an audit mirror with source-row provenance.
The durable binding survives process restart. A second same-root start sees
the live trading spends, so 192 startup rows plus eight trading reads exhaust
the window before another readiness GET. Two journals never independently
authorize a spend after binding.

Handoff holds the destination transaction and the source BEGIN IMMEDIATE
transaction before taking the source snapshot. A source writer either commits
before that snapshot or waits; any later request remains visible to the same
authoritative limiter. Existing active trading rows are mirrored into the
source too, with reverse provenance. Source row id and resolved path bind each
audit copy exactly once. The source commits first: a fault before destination
commit can conservatively retain a spent slot without an audit copy, and retry
imports that slot once. No distributed-atomicity claim or refund is made.
Historical rows remain; only timestamps greater than now minus60 transfer.
Future rows, a direct symlink/missing source, same-file binding and a source
already bound to another request source refuse. Default unbound budgets retain
their previous behavior.

Request-only cap rotation is a separate bounded metadata transition. Only lane B
may change the two request caps, and only after every prior reservation leaves
the trailing window. The transition preserves all request rows and refuses a
journal holding trials, intents, positions, executions or fees. Every request
reservation compares cached and persisted caps inside its own SQLite write
transaction; old connections refuse after a lower-cap rotation before HTTP.
The 200-to150 interleaving allows150, never151; the local200-to30 case allows30,
never41. Lane A still refuses changed caps. The ordinary risk rotation and all order, price,
cash, fee, halt, STOP and exact-byte recovery rules remain independent.

## Primary mechanisms and correction provenance

These are local policy mechanisms, not vendor rate-limit guarantees. The CC's
October 14 ruling selected transfer without duplicate counts and expired-window
cap rotation. The public pinned engine source establishes the primitives:

| Correction | Pinned primary source | Existing mechanism / local policy |
|---|---|---|
| Retain failed-start requests | [safety.py:1541-1572 at 2ede8ead5e19a9f045ec6f04c5082636b7113313](https://github.com/native-agent-stack/native-agent-stack/blob/2ede8ead5e19a9f045ec6f04c5082636b7113313/blueprints/us-equities/adaptive-paper/safety.py#L1541) and [runner.py:2416 at the same pin](https://github.com/native-agent-stack/native-agent-stack/blob/2ede8ead5e19a9f045ec6f04c5082636b7113313/blueprints/us-equities/adaptive-paper/runner.py#L2416) | Ledger commits reservations before returning; the prior replay omitted failed invocations. This correction adds atomic import provenance. |
| Request-cap transition | [safety.py:550-571 at 2ede8ead](https://github.com/native-agent-stack/native-agent-stack/blob/2ede8ead5e19a9f045ec6f04c5082636b7113313/blueprints/us-equities/adaptive-paper/safety.py#L550) | Existing frozen-limit check; new request-only transition is allowed only after expiry and never adopts trading state. |
| Readiness signature exclusion | [runner.py:383-398 at 2ede8ead](https://github.com/native-agent-stack/native-agent-stack/blob/2ede8ead5e19a9f045ec6f04c5082636b7113313/blueprints/us-equities/adaptive-paper/runner.py#L383) | Existing next-trial signature excludes coordinated session flags; October 13 correction adds the validated observation/liveness block, not a risk field. |
| PRE planned-end refusal | [runner.py:787-832 at 2ede8ead](https://github.com/native-agent-stack/native-agent-stack/blob/2ede8ead5e19a9f045ec6f04c5082636b7113313/blueprints/us-equities/adaptive-paper/runner.py#L787) and [sessions.py at that pin](https://github.com/native-agent-stack/native-agent-stack/blob/2ede8ead5e19a9f045ec6f04c5082636b7113313/blueprints/us-equities/adaptive-paper/sessions.py) | Reuses duration plus cleanup plus the existing 60-second allowance against the broker-time PRE close. |
| Invocation request slots | [transport.py:1068-1075 at 2ede8ead](https://github.com/native-agent-stack/native-agent-stack/blob/2ede8ead5e19a9f045ec6f04c5082636b7113313/blueprints/us-equities/adaptive-paper/transport.py#L1068) | Initial N+5 GETs and five final refresh GETs are reserved under the local 50-attempt ceiling; cadence consumes only remaining slots. |
| Bound refusal receipt | [runner.py:2405-2412 at 2ede8ead](https://github.com/native-agent-stack/native-agent-stack/blob/2ede8ead5e19a9f045ec6f04c5082636b7113313/blueprints/us-equities/adaptive-paper/runner.py#L2405) and [main's preflight handler at that pin](https://github.com/native-agent-stack/native-agent-stack/blob/2ede8ead5e19a9f045ec6f04c5082636b7113313/blueprints/us-equities/adaptive-paper/runner.py#L2509) | Invocation bound refuses before GET; not_started reports zero submitted orders. Other SafetyErrors still propagate. |

Repository identity was checked through the installed GitHub client:
nameWithOwner is native-agent-stack/native-agent-stack. Earlier review packets
used its former owner name; the links above use the current canonical repository.

Fixture correction uses the supported CPython
[v3.12.3/f6650f9ad73359051f3e558c2431a109bc016664, Lib/unittest/mock.py:1632-1655](https://github.com/python/cpython/blob/f6650f9ad73359051f3e558c2431a109bc016664/Lib/unittest/mock.py#L1632)
patch.object context manager (bound at:1960). The RTH no-readiness fixture
pins runner.session_at; continuity now explicitly drives PRE and POST first,
then RTH, and invokes the real observer for broker/data reads. It asserts
forwarding, durable rows, unchanged fees/cash and exact trial digests. All four
outer-session controls pass. The two quote-age fixtures also pin vendor and
local quote clocks; elapsed host scheduling no longer chooses their age boundary.

Official quote requests still use alpacahq/alpaca-py 0.44.0 at
[cc4cb3b7ba50ae250e621983c2779047fb16bb28, stock.py:163-182](https://github.com/alpacahq/alpaca-py/blob/cc4cb3b7ba50ae250e621983c2779047fb16bb28/alpaca/data/historical/stock.py#L163).
No adapter, HTTP client, broker API or vendor library is rebuilt. SQLite
transactions use the engine's existing BEGIN IMMEDIATE / COMMIT mechanism;
the imports table and request rows commit together.

## Validation and operating limits

Evidence class is synthetic/local integration. The 180+12 fixture fails on
landed #1097: only 12 rows reach trading. The cap fixture fails with
persisted_risk_limits_differ even after expiry. New tests retain the entire
source history, pin the exact 60-second boundary, repeat imports after reopen,
and refuse partial import from future or symlinked history. Explicit PRE and
POST invocation-bound tests expect the durable readiness journal to hold 50
data_read reservations; the pinned RTH variant expects no journal. Negative
override, OVERNIGHT forwarding, changed identity and malformed final position/
order collection cases exercise previously recorded branch follow-ups.

These tests make no broker, credential, GO, unit, STOP or shared-state call.
Actual session transitions, retained native trial restore and exact-byte
recovery remain required at the next native qualification. This does not add
an account/provider-wide limiter spanning unrelated roots or other runners.
Each root retains its own journal; operator account-writer and request-window
continuity rules remain necessary. PRE records already pinned to #1097 are
not silently repinned by this PR. The CC's start spacing/refusal guard remains
until this correction lands and the operator records its successor binding.

## Follow-ups

- The second #1084/#1097 landing carries the combined 30-second readiness /
  eight-second handler regression; that prepared test belongs to #1084.
- Measure actual native session transition/restore/recovery behavior at the
  next qualification, retaining failed outcomes and exact configuration bytes.
- Measure feed interarrival and provider/account request use before replacing
  initial readiness thresholds or widening this root-local accounting scope.
- Direct-component symlink and intact lane checks do not establish ancestor-safe
  opens or tamper-proof source provenance. A symlinked parent aliases the same
  resolved journal; a manually mutated lane key is outside intact-state tests.
  Ancestor-safe opens and explicit request-journal schema/provenance remain hardening work.
- Review packets lack some historical source/measurement captures even where
  current mirrors agree. Supply pinned copies and original logs when closing
  historical provenance; synthetic tests do not fill those capture gaps.

Any forgotten reservation, duplicate import, history deletion, active-window
cap change or lane-A cap transition overturns this correction.
