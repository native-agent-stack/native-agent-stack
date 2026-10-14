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

### Second correction: enforce retained authority before startup HTTP

The next review found adjacent startup orderings that the original handoff
fix did not cover. At reviewed head
`4cd05154a094d34cdc7eb61b5a654bfdc941c95c`, a bound root already holding
192 startup plus eight trading reservations sent six more mocked GETs when
the current RTH/recovery command disabled readiness. First opted adoption
of a root with 199 existing trading spends sent twelve GETs before importing
them. Both new regressions exercise the real GuardedSession/preflight path
and canonical fingerprint/adaptive/ledger.sqlite3 layout. They fail before
the correction with six and twelve sends, respectively.

Startup now selects the durable window from retained root authority as well
as the current readiness setting. Before its first GET it reconciles existing
canonical trading request histories through the existing destination-to-source
import transaction and durable binding. The 199-spend adoption admits at most one
request; an exhausted bound root admits none. An already-open trading handle
also sees the binding, so its later reservation uses the same source. A
missing or changed retained source refuses before HTTP and is never replaced
with a fresh budget. Disabled startup on a genuinely unbound root retains
the original five broker GET reservations and default data-GET policy.

The observer marks successfully reserved attempts; replay imports their
source rows once rather than charging those GETs again. A positive bound
non-readiness test starts with seven spends, sends six GETs and retains
thirteen in each journal after replay and retry. Before knowing the broker
identity, the scan covers the canonical account journals under this selected
root. It is not a provider/account-wide limiter across unrelated roots, and
the account-writer rule remains necessary.

Linked lane-B recovery follows the current request-only cap envelope, including
a cap-only rotation between the metadata probe and transactional open or a
later reservation. Inactive-readiness startup never rotates that envelope.
Frozen trading/risk limits and exact recovery config bytes remain unchanged;
the real recovery fixture cancels a partial entry and flattens after rotation.
Startup also restricts GETs by the current invocation's exact request cap
inside the source reservation transaction. A source cap increase
therefore cannot widen a frozen lower trading cap; the30-to200 fixture refuses
the next startup read at30 without changing either envelope. This temporary
restriction applies only to GET reservations, never to an order gate.
Readiness handles still refuse stale caps. The handoff's future-row check now
takes its clock after acquiring the source write lock: an ordinary concurrent
row at1001.001 passes a1001.002 snapshot even if the caller captured1001,
while genuinely future history still refuses. The preflight/replay fixtures
pin the same clock on both sides of the transaction; elapsed host time does
not erase their synthetic request history.

Read-only exporter and dashboard budget observations now read the bound source,
not just the stale trading audit mirror. The source path must resolve to the
expected root readiness-requests.sqlite3, opens read-only and matches the
lane. Effective remaining slots also respect the frozen trading envelope.
The two-imported plus198-source fixture reports a full200 window and zero
remaining; unavailable authority omits budget gauges or marks the dashboard
ledger unavailable rather than reporting optimistic capacity.

This correction retains the selected SQLite/SDK mechanisms. Its primary source
is the actual reviewed engine at the fixed commit, not a library substitution:
[runner.py:2380-2428](https://github.com/native-agent-stack/native-agent-stack/blob/4cd05154a094d34cdc7eb61b5a654bfdc941c95c/blueprints/us-equities/adaptive-paper/runner.py#L2380)
selects the old invocation-only observer and replays after HTTP;
[safety.py:1587-1714](https://github.com/native-agent-stack/native-agent-stack/blob/4cd05154a094d34cdc7eb61b5a654bfdc941c95c/blueprints/us-equities/adaptive-paper/safety.py#L1587)
provides the reused binding, import provenance and source-first reservation;
[metrics.py:332](https://github.com/native-agent-stack/native-agent-stack/blob/4cd05154a094d34cdc7eb61b5a654bfdc941c95c/blueprints/us-equities/adaptive-paper/metrics.py#L332)
and
[live_manifest.py:104](https://github.com/native-agent-stack/native-agent-stack/blob/4cd05154a094d34cdc7eb61b5a654bfdc941c95c/blueprints/us-equities/adaptive-paper/live_manifest.py#L104)
show the previous destination-only telemetry. Exact source and the wire,
recovery, concurrent-snapshot and telemetry regressions establish the correction.
The CPython patch.object source above supplies the supported fixture seam.
No new broker API/client or rate-limit framework is introduced.

### Last bounded correction: synchronize adoption and ignore sibling cap identity

Review of937fd8f46 found two wider orderings. An observer selected while its
root was unbound kept a None callback after another invocation imported199
rows and consumed slot200, then sent six GETs. A different account's retained
150/130 request caps also caused lane-A exact-config recovery of an owned
partially filled position to fail before HTTP. Both assertion-bearing tests
fail on actual937 production: six sends and persisted_risk_limits_differ.
These are distinct from the already-closed sequential adoption and lane-B
source-cap rotation cases; they supersede the prior one-time authority
selection and sibling-envelope opening mechanisms.

Every startup callback now selects authority again inside a native root flock,
which also covers first adoption, pending unbound spends and replay. If root
authority is established before an old observer sends, that observer rebinds
or refuses under it; the exhausted200 interleaving sends zero. A disabled
callback on a genuinely unbound root retains the existing data-GET policy and
creates no readiness/trading journal or trial. Before returning for a broker
GET it instead durably records only a conservative60-second transition hold
in readiness-startup.lock. First adoption refuses until that hold expires,
including the gap after preflight and before replay or a crash/refused start.
Data GETs do not extend this broker-attempt hold. The exact59.999/60 boundary
is tested; no pending unbound request can disappear between a second
unsynchronized existence check and a send. No automatic retry is added.

The marker is coordination metadata, not a new risk or request journal; it
never changes a size, price, order cap or numeric trading state. Its sole
timestamp is derived from the actual pre-send attempt and retained with fsync
before the callback returns. Native nonblocking flock refuses a contending
startup before HTTP; replay uses the same lock. The root lock order precedes
the existing destination-to-source SQLite transaction order. Independent
linked trading continues to reserve through the same source transaction.
Same-root versions participating in this coordination are required; this is
not acceptance evidence for old concurrent writers that lack it.

Sibling histories now open existing databases without the trading constructor,
schema migration or risk-envelope access. Only schema/lane/source binding and
request/import rows participate. No SELECT of a sibling's limits, comparison
with the caller or cap adoption occurs; SQL tracing asserts that boundary.
The source budget and caller's exact limits govern startup separately. The
two-account regression retains different sibling caps and an owned partial
entry, executes real startup/replay, then synthetic cancellation and flatten,
and verifies both accounts' frozen limits unchanged. Root request envelopes
still retain their own lane/cap checks. Schema/provenance hardening remains
separate; this does not claim arbitrary unknown sibling formats are accepted.

Primary correction provenance is the exact reviewed engine at
[937fd8f46, runner.py:2380-2445](https://github.com/native-agent-stack/native-agent-stack/blob/937fd8f46ea4a3546f00144176e78d75474f6a22/blueprints/us-equities/adaptive-paper/runner.py#L2380):
one-time callback selection and the old sibling constructor are the two
reproduced mechanisms. The existing native lock pattern is
[safety.py:447-470 at that pin](https://github.com/native-agent-stack/native-agent-stack/blob/937fd8f46ea4a3546f00144176e78d75474f6a22/blueprints/us-equities/adaptive-paper/safety.py#L447),
using CPython's supported fcntl.flock with LOCK_EX/LOCK_NB and O_NOFOLLOW;
the retained import and transaction helpers at
[safety.py:1617](https://github.com/native-agent-stack/native-agent-stack/blob/937fd8f46ea4a3546f00144176e78d75474f6a22/blueprints/us-equities/adaptive-paper/safety.py#L1617)
remain the source-first/provenance mechanism. No selected SDK/limiter is
substituted or forked. Evidence remains synthetic/local integration.

The conservative pre-lock request-clock refusal remains a Follow-up; this
round does not present the corrected handoff snapshot clock as proof of every
reservation interleaving. Real broker/session restore/cancel/flatten acceptance,
historical source captures and ancestor/schema hardening remain open. Lane-B
mover startup integration is a separate P1 prerequisite before any bundle
carrying this retained-window implementation runs mover trials. Today's older
sealed operating records are not repinned by this change.

Evidence class is synthetic/local integration. The 180+12 fixture fails on
landed #1097: only 12 rows reach trading. The cap fixture fails with
persisted_risk_limits_differ even after expiry. New tests retain the entire
source history, pin the exact 60-second boundary, repeat imports after reopen,
and refuse partial import from future or symlinked history. Explicit PRE and
POST invocation-bound tests expect the durable readiness journal to hold 50
data_read reservations; the genuinely unbound RTH variant expects no journal. Negative
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
