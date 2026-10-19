# Shared runner adaptive paper sells within the order envelope

The shared runner needs whole-share sell chunks within its durable order
envelope across account assignments. This exit behavior remains required
with the explore lane holding account A (`alpaca-paper-2`). The shared runner
owns this implementation and its review; account allocation does not alter
the sizing, ownership, refusal or recovery rules below.

The CC's 19:18Z D6-b read found a pre-existing exit defect: the adaptive
strategy sent a full reduction capped by policy entry shares, while the
durable ledger applies its per-order notional cap to sells too. An appreciated
position near that cap could repeatedly reach OrderDenied instead of taking
profit. Larger configured ceilings increase the exposed sizing range.

Split ordinary/forced adaptive sells and cancel-acknowledged replacements
using the existing recovery algorithm. At dispatch, take the minimum of the
requested reduction, currently owned quantity, the ledger's effective quantity
cap at the current bid and order-notional cap / actual sell limit price,
then floor that final minimum to whole shares. Construct precision-zero native
sell quantities at both ordinary and replacement dispatch. Keep one outstanding
order per symbol. Subsequent eligible
ticks recompute the remaining reduction after fills; no parallel chunks or
oversells are introduced. The policy's entry share bound no longer constrains
an owned sell. Entry sizing and admission retain their existing bounds.

Gap-stop fire-once state is consumed only if the actually submitted quantity
covers the current remaining position. A share/notional-bounded chunk keeps
the remainder protected. Replacement sizing uses the acknowledgement-time
quote, price and owned position rather than its staged quantity alone.
Existing halt, freshness, session, reconciliation and fault guards still
govern exits. If no positive representable chunk exists, record
`exit_quantity_unrepresentable` attention rather than sending a zero quantity
or reporting a successful flatten. This does not grant a new exit window.

## Sources

- Native-agent-stack at
  [`dbe7a8da1bb497570471e2b9d0dcfe56bbdc56e9`](https://github.com/native-agent-stack/native-agent-stack/blob/dbe7a8da1bb497570471e2b9d0dcfe56bbdc56e9/blueprints/us-equities/adaptive-paper/recovery.py#L271),
  recovery.py:271-277: existing decimal capacity, current-bid effective
  quantity and owned-position chunking. The native strategy already uses
  the same official order factory and ledger reservation path.
- Official
  [nautechsystems/nautilus_trader at 1b0a49d2792a9432a3aca3fcb617ce7a630d905e](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/crates/model/src/types/quantity.rs#L126),
  quantity.rs:126-168 and events/order/denied.rs:35-61: supported quantity
  precision and native denial event contract. This is a pinned maintained
  source review, not a claim that this mirror commit produced the runtime.
  Native values/callbacks are tested with installed NautilusTrader 2.0.0rc5;
  no upstream adapter or model is replaced.
- Official rc5 source at the same immutable commit,
  [crates/risk/src/engine/mod.rs:2148-2154](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/crates/risk/src/engine/mod.rs#L2148-L2154):
  native risk rejects quantities whose precision exceeds instrument size
  precision, before the whole-position-exit bounds exemption. Our existing
  `native_adapter.instrument()` binds Equity size_precision=0. The installed
  rc5 runtime reproduces this boundary; the mirror pin remains a source citation.

## Local evidence

Synthetic dispatch uses the real policy, native Quantity/Price types and
durable RiskLimits/Ledger. Only order construction capture and broker
submit/fill boundaries are simulated. No broker, credential, order or GO
call is made. Evidence class is synthetic/local integration.

At base 04f64a056cade587f804da60f6a94f7852f7624d the initial 6 tests fail
with 5 failures: at-cap 100 shares bought at 100 and bid at 110 cannot exit
without a size denial, for ordinary, fixed-mode, pending and replacement
cases; a policy entry share bound of 1 throttles the sell. The oversize-buy
refusal already passes. With chunking, take-profit submits 90 then 10
shares, reaches flat and records zero native_rejections in that capture harness.
The captured factory bypassed native risk: its fixed-mode fractional-capacity
assertion was incorrect and is superseded by the whole-share regression below.
Replacements clamp to the current position. Additional
tests cover the direct gap-stop remainder through its last chunk.

The broader existing suite initially exposed 29 old fake-ledger fixtures
without the now-required limits/position interface. They now supply real
RiskLimits and consistent held state; all prior assertions are retained.
The gap-stop truncation tests now explicitly bind their ledger share cap.

Read-only acct-v1 rejection-channel inspection found native_rejections == 0
in all 10 completed receipts (2x/4x s9-s13). The exact local paths and hashes
are retained in the coordination lane record. No denial was observed there;
the synthetic failure demonstrates the defect independently of those runs.

## Activation and follow-ups

No config with order-notional cap above 10000 runs until this sell fix lands,
unless its generated per-position allocation is <= 0.9 times its per-order
cap. That interim envelope covers moves under about 10% and must be stated
in its operating record. This PR changes no current series or pinned unit.

- D6-b's optional ceiling configs/registrations and remaining documentation
  follow-ups stay in #1088; this PR does not change the frozen defaults.
- Larger-cap operating acceptance and acct-v2 repinning happen after landing;
  simulated fills are not native paper acceptance or qualification evidence.
- D7's same-journal capital transition and #1084's stream/recovery fixes are
  separate changes with their own reviews.

A size-cap denial of a representable chunk, an oversell, a premature gap-stop
consumption or an entry-bound regression overturns this choice.

## Whole-share correction after the native risk read

The local P1 read at `17c49649040cf98abc872bbc32b9cf37a0dd93c6`
identified the missing Equity precision boundary. The new regression uses the
real AdaptiveStrategy order factory and `build_node()`'s rc5 LiveRiskEngine
with bypass=False. An observing submit override forwards every order to the
real native submission; it replaces neither the factory nor the risk engine.
Only quotes and broker fills are simulated. Startup remains flat: the fixture
first buys 100 shares at $100 through that same native path, then raises the bid
to $110, giving an actual sell limit of $109.98 and a $10,000 per-order cap.

Before the correction, fixed mode is denied with
`QUANTITY_PRECISION_EXCEEDS_MAXIMUM`, quantity `90.925622840`, precision 9,
maximum 0. The position remains 100 shares. After flooring the final minimum
and using `Quantity.from_int`, the first tick sells 90 shares and leaves 10;
the next tick sells the remainder. Both sell quantities have precision zero,
all orders stay within the cap, there are no native refusals or callback faults,
and three native fills (one entry, two exits) reach durable flat state.

The CC's #1088 read also requires above-cap take-profit splitting. A second
real-node test covers notional mode with the same appreciated position. Loading
only the frozen pre-chunk native_strategy.py at parent `04f64a056cade587f804da60f6a94f7852f7624d`
into that current fixture reproduces `order_size_cap_exceeded`; this is a
single-source regression measurement, not execution of the entire old tree.
The corrected implementation passes both real-node cases and all eight existing
sell-chunk tests (10 tests, rc0). Failed flat-startup/zero-hold fixture attempts
were corrected before the actual fail-first result and are not bug evidence.

The correction is one forward commit after reve's authored implementation.
No broker, credentials, account state, units or operating activation change.

The eight bounded sell/exit/corporate-action/native/safety/recovery/sell-age
modules pass 407 tests. The runner module executes 192 tests with one failure:
the two-second achieved-leverage 2x fixture does not exceed 1x. An isolated
frozen-parent strategy probe passes once and then reproduces a zero-fill,
zero-rejection failure; current isolated runs also fail. This does not establish
the timing cause or a regression in this correction. Existing leverage code
and assertions remain unchanged, and no all-green runner/495-suite result is
claimed. The public correction receipt records this limit for independent review.

## Round 2: committed reductions, minimum owned shares and refusal policy

Astra's FIRST read at `17c49649` found three P1 defects. The reviewer's
`review-regressions.py` ran against the round-1 tree before edits: three tests,
three failures. A 100.50 take-profit sold 99 shares but abandoned one when the
bid eased to 100.35; a definitive native refusal repeated four times; an
appreciated one-share position under a $100 cap sent no exit. The same three
reviewer assertions pass with this correction. Their fractional-sell wording
is superseded by the CC's whole-share ruling: the assertion of reaching flat
is retained, and the implementation uses one precision-zero share.

The journal's existing transactional metadata/event mechanism now retains a
per-symbol exit target, reason, completion and refusal state. A full reduction
commits target zero; a deliberately partial take-profit commits its original
remaining quantity once. The next eligible tick derives remaining reduction
from durable owned quantity, while unresolved intents and pending orders
serialize dispatch. A trigger clearing does not revoke that commitment. A
new stronger exit can lower the target; it never raises it. Confirmed fills
record completion. A completed partial target does not repeatedly halve the
remainder. The state survives strategy/journal reconstruction.

`Ledger.cancel_exit_commitment(symbol, reason=...)` is an explicit recorded
owner policy and refuses while any order for the symbol is unresolved.
Admitting a fresh buy after verified flat also records a new position cycle,
discarding only the completed reduction target, not a refusal. An explicitly
invoked recovery records its full-flat policy as a target-zero transition;
it preserves refusal state. Neither time passing nor a changed price erases
a definitive refusal.

The shared adaptive/recovery quantity rule floors normal chunks to whole
shares. When a normal chunk would be zero, one owned whole share is permitted
under the quantity ceiling even when its value exceeds the per-order notional
cap. Durable reservation still proves ownership net of outstanding sells and
logs `exit_cap_exceeded_reduce_only`. The exception admits neither an unowned
share nor a two-share over-cap order. Entry whole-share admission and all
entry ceilings remain unchanged. A fractional residual smaller than one share
is retained with attention; the earlier recovery fixture expecting a fractional
sell is explicitly superseded by this policy. This updates the earlier
all-orders-within-cap description only for the logged minimum-share exception.

Native OrderDenied carries the actual reason at pinned rc5
[crates/model/src/events/order/denied.rs:36-61](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/crates/model/src/events/order/denied.rs#L36-L61).
The callback retains that reason and defaults unknown/native contract failures
to definitive. Only exact `quote_stale`, `quote_not_fresh`, `outside_allowed_session`,
`outstanding_order_cap_reached` and `submission_rate_exceeded` reasons are
transient: at most two automatic retries after the initial refusal, at least
five seconds apart. Count and retry time persist. A confirmed fill clears a
transient refusal; budget exhaustion remains visible and blocks continuation.
Ambiguous broker submissions remain unresolved and are never marked not sent
merely to retry. Recovery reads the same refusal state and refuses automatic
repetition. `Ledger.reconcile_exit_refusal(symbol, reason=...)` explicitly
acknowledges reconciliation and cannot release while an order is unresolved.

Synthetic reviewer cases are complemented by real installed rc5 LiveNode risk
tests, including the one-share minimum, plus restore/partial-fill/cancel,
original partial-target, retry-budget, pre-wire refusal and recovery tests.
The existing native factory, risk engine, transactional journal and broker
guards remain authoritative; these changes fill the demonstrated trading
policy gap without replacing upstream implementations. No new broker call,
credential access, unit activation or paper acceptance follows from these
synthetic/local integration results. Reve's authored parent remains intact;
round 2 is one further forward commit, with P3s retained as follow-ups.

Round-2 verification: the eight native sell/adapter/runner/exit/extended-exit/
corporate-action/recovery/safety modules pass 600 tests under idle scope.
After the last refusal replay-fallback and zero-request sizing edits, the
14 targeted commitment, native-risk and recovery cases pass. The three original
reviewer assertions pass unchanged. This newer result does not erase round 1's
recorded runner timing failure or claim live broker acceptance.

## P1 exception: recognize the final pre-wire freshness reason

The local read at `16db3b36b974a73a6913ba7fdda38649d3cdd4e7`
found that the final ledger quote guard raises `quote_not_fresh`, while the
transient set recognized only `quote_stale`. A quote can age after a valid
strategy tick and before `Controller.before_submit`. Transport's proven
pre-wire rejection preserves the reason; that proof does not make a temporary
freshness failure a permanent exit-policy refusal.

Primary source at the reviewed pin:
[safety.py:834-846](https://github.com/native-agent-stack/native-agent-stack/blob/16db3b36b974a73a6913ba7fdda38649d3cdd4e7/blueprints/us-equities/adaptive-paper/safety.py#L834-L846)
raises the exact reason, [runner.py:970-989](https://github.com/native-agent-stack/native-agent-stack/blob/16db3b36b974a73a6913ba7fdda38649d3cdd4e7/blueprints/us-equities/adaptive-paper/runner.py#L970-L989)
forwards the guard failure as NativeOrderRejected, and
[native_adapter.py:793-802](https://github.com/native-agent-stack/native-agent-stack/blob/16db3b36b974a73a6913ba7fdda38649d3cdd4e7/blueprints/us-equities/adaptive-paper/native_adapter.py#L793-L802)
forwards that reason into the native rejection callback.

The correction adds only `quote_not_fresh` to the existing transient set. The
maximum two automatic retries, five-second interval, durable count, attention
and shared recovery gate are unchanged. The regression uses the real
Controller.before_submit and Ledger._check_quote with a synthetic stale
transport observation, then delivers the adapter-equivalent rejection callback.
Before the fix there is one rejection and 100 shares remain after fresh ticks.
After the fix the first fresh tick waits out the retry interval, subsequent
90- and 10-share chunks reach flat, the rejection count stays one and the
transient refusal clears on confirmed fills. No broker or new live node is
started by this test.

The three P2 findings about flat commitment completion, completed partial
targets versus scale-ins, and real-node wall-clock session isolation remain
follow-ups. This exception changes neither those paths nor their tests.

## Final structural correction and amended exit-cap rule

The local read at `c126aa6cfa3ac37a2bb759c4b2ff3c81913cde33` reproduces
the same temporary refusal one layer later. After reservation succeeds, the
real final guard can see a stale quote or a deferred request budget. At this
pin, [GuardedSession.request:952–967](https://github.com/native-agent-stack/native-agent-stack/blob/c126aa6cfa3ac37a2bb759c4b2ff3c81913cde33/blueprints/us-equities/adaptive-paper/transport.py#L952-L967)
replaces the cause with SubmissionNotSent's privacy-safe message, while
[Controller.before_request:936–968](https://github.com/native-agent-stack/native-agent-stack/blob/c126aa6cfa3ac37a2bb759c4b2ff3c81913cde33/blueprints/us-equities/adaptive-paper/runner.py#L936-L968)
is the actual final risk/budget gate. Matching more temporary strings cannot
repair a structural loss of the proven no-HTTP property.

On owned exit paths the native adapter now carries `not_sent=True` provenance
into the native rejection reason with an exit-only marker. This covers the
transport's SubmissionNotSent and the controller's earlier NativeOrderRejected.
Recovery uses the same bridge. The publisher's rc5
[OrderRejected reason field](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/crates/model/src/events/order/rejected.rs#L59-L60)
is a string, so the bridge preserves this policy fact without changing or
replacing the upstream event. Unknown hook causes remain privacy-safe and
retryable; only known value-free permanent local codes cross the guard as
such. Entry reasons, admission, dropped-entry behavior and re-decision are
unchanged.

The final CC amendment supersedes the earlier provisional permanent cap list.
Only `global_stop_latched` and `outside_allowed_session` are named permanent
pre-wire local reasons. Entry quantity/notional ceilings do not refuse an
ownership-bounded sell: the ledger first proves owned quantity net of pending
sells and records any over-entry-cap reduction. The oversell check remains.
The existing shared adaptive/recovery helper still chunks deterministically
using its conservative per-order sizing references, with a minimum whole share
when a smaller entry-size reference would otherwise strand an owned share.
No unmeasured venue limit is invented. The five-second spacing and maximum
two automatic retries remain; a third temporary refusal is durably exhausted
and becomes definitive. Actual ambiguous broker attempts remain outside this
pre-wire guarantee and cannot be released merely to retry.

Two new tests drive the real Controller, GuardedSession.request and the actual
adapter `_submit_order` forwarding method; only HTTP responses and fills are
simulated. The stale-after-reservation and actual durable-budget cases both
fail before the structural correction with all 100 shares unsold and no HTTP
call. Afterward each recovers through bounded retry, submits/fills 90 and 10
shares, reaches flat and retains only the one initial rejection. Separate
tests cover each named permanent reason, unenumerated no-HTTP causes, bounded
exhaustion, exception subclasses, and unchanged entry rejection behavior.

The #1095 exit_probe's exact sizing boundary is retained as an additional
test: one share filled at 999.99 under a 1000 entry cap, then a reduce-only sell
at 1000.10 is accepted. That one-share case already passes the c126 admission
implementation because the previous minimum-share exception covered it;
there is no invented failing-before claim. The stronger case acquires two
shares as two allowed one-share entries and then reduces both above the same
entry-size caps. It fails the unchanged c126 admission rule and passes the
amended ownership exemption. These core sizing tests use the actual controller
and ledger; #1095's separate unmerged overnight arming layer is not copied or
claimed qualified here.

Four P2s remain follow-ups: flat commitment completion before entry filtering;
completed partial targets versus later scale-ins; cleanup-budget expiry being
charged to durable refusal state; and wall-clock session isolation of the three
NativeSellRisk cases. This change does not remove invocation-budget events from
the refusal journal or repair those state/session paths. The CC closes this PR
to further implementation rounds after this final forward commit: any later
P1 is escalated for a land-or-park decision. No broker, credential, account,
unit activation or paper acceptance is introduced.

## CC 2026-10-14 02:40 correction: transient pacing, never exhaustion

This correction supersedes the earlier retry-count exhaustion policy above.
At reviewed integration head `4b3332a0a5d67a071dba296a0c399b84c12ec31a`,
the third transient refusal became definitive, stranding an exit during a
temporary quote or request-budget outage. Primary mechanism sources are that
head's `safety.py` refusal journal and durable request-budget implementation,
`runner.py::Controller.before_request`, `transport.py::GuardedSession.request`,
and the existing rc5 native rejection-string bridge cited above.

Transient causes now pace attempts indefinitely, never changing classification
by count. The journal stores `retry_at = now + max(5, known_wait_seconds)`.
The controller passes its actual durable-budget wait as numeric metadata; the
final HTTP guard preserves only the finite nonnegative duration through the
privacy-safe native reason. Raw errors remain sanitized. STOP, closed session
and refusals without no-HTTP proof retain definitive behavior. Entries retain
their rejection/drop path.

After three consecutive transient refusals the journal emits `needs_attention`
and keeps pacing. Broker acceptance resets the consecutive-refusal state before
any fill through both native accepted callbacks and the durable observation path
used by recovery. The reduction target stays intact. Replay retains the paced
deadline and attention flag; an accepted exit starts a later refusal count at one.

Three fail-first regressions on unchanged 4b3332a0 each left all 100 shares held:
continuous two-second ticks through a real 60-second durable-budget deferral,
a quote stale for 30 seconds at the final HTTP gate, and a 40-second stale
interval exercising more than three attempts with at most one attempt per five
seconds. They run the actual Controller, GuardedSession and native adapter
submission method with HTTP/fills simulated. The acceptance observation is
asserted before a fill, and prolonged staleness emits durable attention without
blocking eventual 90+10 fills. This is synthetic integration evidence, not broker
acceptance. The old tests expecting definitive exhaustion are amended to the
current rule; the historical receipts stay unchanged.

The CC requests one forward commit without a further rebase and one final review
wave. Any P1 in that wave parks the PR. NativeSellRisk's real-clock session
fixture, the synthetic STOP-code test, the legacy SELL-cap assertion and the
retained P2s remain follow-ups. The bounded test command selects only
CommittedExitRegressions from the sell-chunk file; it does not claim the three
NativeSellRisk cases pass during CLOSED sessions.

## Shared runner review and integration, 2026-10-15

PR #1091 is unparked for shared runner review. This supersedes the earlier
park-and-stop review instructions above. PR #1095's separate overnight stage
admission work follows after this PR lands on main. The current read wave
covers the full shared runner change; findings are returned as one forward
commit per round, and the CC retains landing ownership.

The eight commits at `e27551615fc4ee7857342899d239cd29c8dcdd18` were rebased
onto main `0f4ee075b2ab3af1b099d5ca1ecb8cae02ee3f5b` without conflicts,
producing `3b4ef32ca274eaa0c6143a6d47700ebc757a8137` before this wording
update. The installed CC helper's `lg_change_id`, with only
`LG_EXCLUDE=':!manifests/evidence.json'`, returned
`48b818a953a57c202c4bfa0fe50b7e83cdbb9826` for both heads. The helper is
`cc-tools/nas_land.sh`;
only its change-identity function was evaluated. `git merge-tree --write-tree
HEAD origin/main` returned rc 0. All 19 non-registry paths from both the
rebased diff and `ORIG_HEAD` had correct evidence registrations, and the
full registry had no missing or stale file hashes.

The shared runner wording update changes this decision and the sell-chunk
test module's description, with their derived hash registrations. Existing
compatibility identifiers inherited from main are retained. The production
implementation and test assertions are unchanged. The pinned local test
runtime reports CPython 3.12.3 and NautilusTrader 2.0.0rc5; the source pins and
synthetic evidence boundaries above continue to apply.

The complete sell-chunk, recovery and safety modules pass 173 tests, rc 0
(`nice -n 19 <pinned-runtime-python> -m unittest
tests.test_adaptive_paper_sell_chunks tests.test_adaptive_paper_recovery
tests.test_adaptive_paper_safety`). Their ledgers, guard files and lock roots
are temporary fixtures; broker boundaries are simulated. The existing
`systemd-run --user --scope -p CPUWeight=idle` wrapper could not connect to
the user bus in this session and started no tests, so the run used `nice`
priority 19. Removing the module description from the old and new test ASTs
produces identical trees, independently confirming unchanged assertions.

## Scoped PARK corrections and integrity handoff, 2026-10-15

The read handoff at `e63d70d87e141f2455c717347793ad3ac379d3a2` was withdrawn:
the wording change above retained the PARK record's defects. The CC's
addendum-01 authorizes one correction commit on that head, followed by full
reads from both families and a local review. It supersedes the new-PR form
of the PARK ruling; it preserves the exact correction list. #1095 follows
only after landing. The name-only input citations,
test commands and tested source hashes are retained in
[the correction receipt](../../evidence/artifacts/adaptive-paper-shared-runner-corrections-20261015/receipt.json).

The design keeps the existing native order factory, durable ledger, transport
guard and bounded recovery. Absolute allocation reductions strengthen an exit
target even when its reason is unchanged. A completed target is inactive for
a later scale-in, while a new explicit reduction starts a new commitment.
Repeated fractional take-profit signals retain their original partial target.
Reconciled flat holdings complete a target before a new entry is filtered,
including when the final sell fill arrived outside the strategy callback.

Recovery invocation guards retain proven no-HTTP transient provenance. This
includes an expired deadline before a submit coroutine begins; a timeout after
an operation starts keeps its existing ambiguity treatment. A symbol waiting
for its durable retry time yields to another eligible symbol, then waits within
the cleanup deadline for its own retry and a fresh quote. Retry counts never
become permanent, and all existing pacing remains in effect.

An actual transport integrity loss carries the value-free reason
`recovery_observation_integrity_lost` through the existing native string bridge.
Its `integrity_lost` class is permanent for that damaged observation session.
The runner ends its loop before another forced sell spends a submit slot and
hands the owned residual to fresh recovery. A healthy, successfully reconciled
recovery with no unresolved orders releases only this class. STOP, closed-session
and other definitive refusals retain their behavior. A rejected reconciliation
cannot release the integrity class. This separates a session that has lost its
order observations from a temporary invocation deadline without turning an
ambiguous submission into no-HTTP proof.

The changed mechanisms are pinned in the reviewed parent:
[target lifecycle](https://github.com/native-agent-stack/native-agent-stack/blob/e63d70d87e141f2455c717347793ad3ac379d3a2/blueprints/us-equities/adaptive-paper/native_strategy.py#L1116-L1149),
[recovery guards and retries](https://github.com/native-agent-stack/native-agent-stack/blob/e63d70d87e141f2455c717347793ad3ac379d3a2/blueprints/us-equities/adaptive-paper/recovery.py#L125-L343),
[run loop and handoff](https://github.com/native-agent-stack/native-agent-stack/blob/e63d70d87e141f2455c717347793ad3ac379d3a2/blueprints/us-equities/adaptive-paper/runner.py#L1849-L2015),
[durable refusal classification](https://github.com/native-agent-stack/native-agent-stack/blob/e63d70d87e141f2455c717347793ad3ac379d3a2/blueprints/us-equities/adaptive-paper/safety.py#L1021-L1110),
and [final HTTP guard](https://github.com/native-agent-stack/native-agent-stack/blob/e63d70d87e141f2455c717347793ad3ac379d3a2/blueprints/us-equities/adaptive-paper/transport.py#L953-L1010).
Primary upstream checks confirm the existing
[NautilusTrader rejection reason string](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/crates/model/src/events/order/rejected.rs#L59-L60),
and CPython v3.12.3's
[gen_close](https://github.com/python/cpython/blob/v3.12.3/Objects/genobject.c)
(`FRAME_CREATED` completes without executing the coroutine) and
[asyncio timeout](https://github.com/python/cpython/blob/v3.12.3/Lib/asyncio/timeouts.py)
(`Timeout.__aexit__` and `expired`). No runtime or dependency is replaced.

All ten new cases fail against untouched `e63d70d8` production with only the
new test code overlaid: rc 1, ten assertion failures, no errors or skips.

| Scoped finding | Failing-before observation | Corrected observation |
| --- | --- | --- |
| P1 same-reason lower target | 100 → 50 → 25 leaves 50 held | Sells 50 then 25, leaves 25 |
| P2 completed target after scale-in | Sells the later 49-share buy back down | Holds the new 99-share target; a later 75 target sells 24 |
| P2 flat reconciliation without callback | No new entry after confirmed flat | Restored strategy buys the requested ten shares |
| P1 recovery guards, three cases | In-try deadline, integrity loss and pre-await deadline persist definitive refusal | Each remains transient and a later fresh recovery exits |
| N1 per-symbol retry | First symbol's retry window ends recovery | Eligible symbol exits at T+1, paced symbol at T+6 |
| F1 class and recovery proof, two cases | Integrity reason becomes generic temporary; no session class | Reason survives; unhealthy reconciliation retains the class and healthy recovery releases it |
| F1 native handoff | 4.122 s with one refused native submit-budget call; recovery needs attention | 0.340 s, zero post-loss native submit-budget calls; one recovery submit at wait zero reaches flat |

The original 173-test set plus these ten cases passes: **183 tests, rc 0,
no skips**, CPython 3.12.3 and NautilusTrader 2.0.0rc5. The normal real-native
runner smoke and stream backpressure suite also pass **24 tests, rc 0**.
Full sanitized outputs are retained beside the receipt. Existing temporary
directory `ResourceWarning` output remains visible; warning-free execution
is not claimed. Ledgers, guards and lock roots are temporary fixtures, and
quotes/broker fills are simulated. The latency is measured local integration,
not a live operating bound or broker acceptance. This section supersedes the
earlier retained-follow-up descriptions for precisely the repaired findings.

## Same-wave reconciliation and complete denial policy, 2026-10-15

The full reads at `83df1bc6ad9a264b8ea034c76c6b55f969af9284` closed the
target-lifecycle, per-symbol retry and integrity-handoff changes, but found
additional refusal-class defects at that same head. CC addendum-02 authorizes
one combined forward commit; the loop stop counts failed correction commits,
not multiple findings in one review wave. This section and
[the round-two receipt](../../evidence/artifacts/adaptive-paper-shared-runner-corrections-20261015/round2/receipt.json)
supersede the previous ambiguity and fixture-isolation assurances.

A timeout after submission begins, or an ambiguous transport submission, now
creates `transient_with_reconcile` tied to its client order ID. Time passing
does not release that record. Fresh recovery must reconcile a complete healthy
snapshot and resolve outstanding orders first. A terminal canceled/unfilled
order permits a new owned exit; a confirmed fill to flat removes the old refusal
so it cannot poison a later position cycle. An attempted ID absent from the
snapshot still fails closed. The same recovery routine serves the mover's
shared journal. Foreign exceptions contribute their type to the journal, never
their message; the later receipt cannot reclassify foreign text as an
engine-authored SafetyError. Both integrity-loss breaks request resting-entry
cancellation before leaving the native loop.

The native denial policy covers all **46** members of the publisher's
`OrderDeniedReason` enum at `1b0a49d2792a9432a3aca3fcb617ce7a630d905e`.
[The complete table](../../evidence/artifacts/adaptive-paper-shared-runner-corrections-20261015/round2/native-denial-policy.json)
lists every variant, its canonical code, policy and rationale. Fifteen fixed
order-contract/configuration codes are explicitly definitive; the other 31
and every unknown code require reconciliation. The local STOP, closed-session,
known contract and documented broker-refusal allowlist remains explicit.
The integrity-loss class remains permanent for its damaged observation session.
Unknown codes no longer acquire permanent refusal status by default.

The publisher states that `OrderDenied` is local and never reaches a venue;
only the leading stable code is canonical, and diagnostic suffixes must not
drive control flow. The native callback therefore retires a never-venue
reservation first. An absent reservation, or a no-broker/no-fill `not_sent`
record, settles that local reconciliation and retains ordinary durable pacing.
The receipt records both the `transient_with_reconcile` policy and the resulting
`native_denied_never_sent` proof. This lets an expired native rate window retry
without inventing a broker attempt. Uncertain attempted submissions continue
to require the fresh snapshot/client-ID proof above. Unknown native diagnostics
are recorded as `NATIVE_DENIAL_UNKNOWN`; only known canonical codes are retained.

Primary sources checked for this correction:

- [NautilusTrader denied_reason.rs](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/crates/model/src/events/order/denied_reason.rs):
  the complete enum, its local-denial guarantee and canonical-code contract;
  [risk engine](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/crates/risk/src/engine/mod.rs#L234-L252)
  and [publisher regression](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/crates/risk/tests/risk_engine.rs#L5587-L5597)
  establish the real `RATE_LIMIT_EXCEEDED` event.
- [alpaca-py client-order lookup](https://github.com/alpacahq/alpaca-py/blob/cc4cb3b7ba50ae250e621983c2779047fb16bb28/alpaca/trading/client.py#L157-L174),
  pin `cc4cb3b7ba50ae250e621983c2779047fb16bb28`: the maintained SDK query
  used by the existing transport's recovery contract, not a replacement adapter.
- Reviewed parent `83df1bc6`: [recovery](https://github.com/native-agent-stack/native-agent-stack/blob/83df1bc6ad9a264b8ea034c76c6b55f969af9284/blueprints/us-equities/adaptive-paper/recovery.py#L125-L365),
  [refusal policy](https://github.com/native-agent-stack/native-agent-stack/blob/83df1bc6ad9a264b8ea034c76c6b55f969af9284/blueprints/us-equities/adaptive-paper/safety.py#L1055-L1110),
  [native callbacks](https://github.com/native-agent-stack/native-agent-stack/blob/83df1bc6ad9a264b8ea034c76c6b55f969af9284/blueprints/us-equities/adaptive-paper/native_strategy.py#L271-L427),
  and [handoff](https://github.com/native-agent-stack/native-agent-stack/blob/83df1bc6ad9a264b8ea034c76c6b55f969af9284/blueprints/us-equities/adaptive-paper/runner.py#L1873-L2025).
  CPython v3.12.3's `asyncio.timeouts` source cited above supplies the deadline
  boundary. No runtime, broker adapter or dependency is replaced.

The final baseline run uses untouched 83df production and the new test cases.
Its original sizing helper is retained for the test-only STOP regression,
which substitutes an active latch under a private temporary root. Twelve test
methods run: eleven fail with 58 assertion failures (including table subcases),
one no-blind-retry control passes, and none error or skip. The current pinned
runtime passes **195 tests**, comprising the previous 183 plus these twelve,
in 44.611 seconds, rc 0, no skips. The adjacent normal native-runner/stream
selection also passes **24 tests**, rc 0, in 2.831 seconds.

| Finding | Failing-before evidence | Corrected evidence |
| --- | --- | --- |
| Attempted ambiguity/deadline | Canceled, open/unfilled, mover and actual AmbiguousSubmission cases refuse later exits; a filled-flat case retains the old fuse | Reconciled terminal IDs release the uncertainty; fresh recovery sells or confirms flat |
| Foreign exception privacy | Fixture text reappears in the later SafetyError receipt | Only exception type/class persists; no fixture message in the journal or next receipt |
| Entry cancellation | Native lifecycle contains only `node_stop` | `cancel_requested` precedes `node_stop`, then fresh recovery reaches flat |
| Native rate expiry | Real rc5 denial, one share held after the window, retry false at +120 s | Same real denial, retry true at +120 s and flat after the window/pacing expire |
| Complete denial mapping | Unmapped reasons acquire definitive status; opaque suffixes persist | All 46 members and unknown fallback follow the explicit policy and canonical-code rule |
| STOP isolation | Private active runner latch causes `admissions_not_ready` before sizing | Every default binding resolves under the private helper root; the host latch is compared lexically and never inspected |

Full sanitized outputs, tested source hashes and the enum capture are retained
with the receipt. Fourteen existing temporary-directory ResourceWarnings remain
visible. These are synthetic/native integration results, not broker operating
qualification. Zero post-loss native submit calls describes the loop fixture;
an already-entered final-wire path can still spend a slot before its integrity
guard. That budget measurement, published preimages for the earlier private
review/helper bindings, stale prose locators, fractional take-profit after a
scale-in, and the mover's unsellable-share label remain P3 follow-ups. The earlier
review/helper hash captures are not silently rewritten or claimed to have newly
published preimages by this correction.

## 2026-10-15 addendum-03: re-arm partial take-profit after confirmed scale-in

The prior P3 disposition of a fractional take-profit after a scale-in is
superseded. A supported preset may select a fraction below one, so suppressing
that next exit is P1 even though registered presets currently select one.
The correction follows CC addendum-03 at `d3c3a4e97b26482fdc94170cecb6d50d3ac68cb9`
(`coordination/command-center/research-cc-role-20261008/adjudication-pr1091-e2755161-20261014.addendum-03.md`).
The CC delta and local review are cited by name and path in the round-three receipt;
these remain locally verified review inputs, not newly published preimages.

A positive confirmed buy fill now re-arms a completed partial take-profit.
The ledger removes only its target, reason and completion marker and journals
`scale_in_rearms_take_profit` in the existing fill transaction; any refusal
state survives. The pre-fill owned quantity can prove that the old target was
reached even when a reconciliation fill did not produce a native callback.
The next take-profit computes its fraction from the new owned quantity.

An unfilled reservation cannot re-arm the exit, and duplicate cumulative fill
observations cannot re-arm it twice. An unfinished partial target retains its
original remainder across chunks and a scale-in. Completed absolute rebalance
targets retain their separate lifecycle. Stop-loss and time exits still sell
the owned position after a partial take-profit and scale-in.

Every Controller fixture in `test_adaptive_paper_sell_chunks.py` now uses the
existing `patch_default_stop` helper, including the runner binding. A module
guard intercepts `os.stat`, `os.lstat`, `os.open`, `io.open` and
`builtins.open` before delegation for the lexical host-latch path. Cleanup
asserts that no test attempted such access, even if production code caught the
guard exception. The guard never resolves or probes that host path.

### Sources and bounded verification

This is a correction to the existing ledger and test fixtures, without a new
runtime or dependency selection. The authoritative implementation inputs are:

- [alpaca-py Order](https://github.com/alpacahq/alpaca-py/blob/cc4cb3b7ba50ae250e621983c2779047fb16bb28/alpaca/trading/models.py#L230-L231)
  and [TradeUpdate](https://github.com/alpacahq/alpaca-py/blob/cc4cb3b7ba50ae250e621983c2779047fb16bb28/alpaca/trading/models.py#L633-L646)
  at `cc4cb3b7ba50ae250e621983c2779047fb16bb28`: filled quantity/average,
  execution identity and position quantity. The fetched pinned
  `models.py` is byte-identical to installed alpaca-py 0.44.0, SHA256
  `0a4296847ea46c434de3fe08ef6bb82519d9442705e59b4671127ffffad3855f`.
- Existing [Ledger.record_order at d3c3a4e9](https://github.com/native-agent-stack/native-agent-stack/blob/d3c3a4e97b26482fdc94170cecb6d50d3ac68cb9/blueprints/us-equities/adaptive-paper/safety.py#L1610-L1721):
  cumulative observations advance exposure only by a positive quantity delta.
  The correction uses that established fill boundary rather than admission.
- [Native committed targets at the same parent](https://github.com/native-agent-stack/native-agent-stack/blob/d3c3a4e97b26482fdc94170cecb6d50d3ac68cb9/blueprints/us-equities/adaptive-paper/native_strategy.py#L1121-L1145)
  and [Controller STOP selection](https://github.com/native-agent-stack/native-agent-stack/blob/d3c3a4e97b26482fdc94170cecb6d50d3ac68cb9/blueprints/us-equities/adaptive-paper/runner.py#L950-L954)
  identify the two reproduced failure paths.
- [CPython v3.12.3 pathlib](https://github.com/python/cpython/blob/v3.12.3/Lib/pathlib.py#L840)
  and [unittest.mock](https://github.com/python/cpython/blob/v3.12.3/Lib/unittest/mock.py)
  supply the filesystem boundary and supported patch/cleanup machinery.

The original local-review reproduction is now an executable regression:
100 shares, sell 50 at a 50% take-profit, buy 50, then sell 50 on the next
take-profit. At unchanged d3 production the second sell is absent. A second
case reconciles the first sell without a callback, buys 25 and reconstructs
the strategy: the old code sells 25 back to its stale target; the correction
sells 37 from the new 75-share position and retains 38.

The fail-first run executes ten methods with a test-only overlay at d3:
two take-profit failures, four Controller failures blocked before their
host-latch stat, and one expected module-cleanup assertion recording those
four blocked attempts. Four controls already pass: canceled zero-fill buy,
unfinished target, stop-loss after scale-in and time exit after scale-in.
The same ten cases pass after the correction, with zero attempted host-latch
operations. All **201** requested pinned-runtime tests pass in 45.888 seconds,
rc 0, with no errors or skips; the adjacent native/stream selection passes
**24** in 2.792 seconds, rc 0. Fourteen existing temporary-directory
ResourceWarnings remain disclosed.

Full commands, output, source hashes and per-case outcomes are retained under
`evidence/artifacts/adaptive-paper-shared-runner-corrections-20261015/round3/`.
These are synthetic tests through the pinned CPython 3.12.3 and
NautilusTrader 2.0.0rc5 runtime, each command in a fresh network namespace.
They do not establish paper or broker acceptance.

The entry-side mover halted/resumed timing flake is a separate follow-up:
make that test's wait deadline-based. The optional broker-stream rejection
release remains a follow-up as well. This correction does not change either
path or any recovery behavior. The new stop condition is explicit: any P1
of any class at the next delta parks this PR and splits recovery and
sell chunks into separate PRs.

## 2026-10-15 content rebase: preserve both integrity handoffs

The content integration is against #1119's landed
`fda24cfe436310658755a75e5b6b7865512c8df1`, carrying the reviewed
`52924b028c8419b48042f80b088ec3135a0f8084` behavior. Four files conflicted:
`runner.py`, `transport.py`, `source-hashes.json` under adaptive-paper,
and `manifests/evidence.json`. The twelve existing commits retain their order.
The complete file/hunk dispositions, controls, commands and tested source hashes
are in `evidence/artifacts/adaptive-paper-shared-runner-corrections-20261015/content-rebase/`.

| File and hunk | Resolution |
| --- | --- |
| `runner.py`, first integrity check | Retain #1119's complete disable/cancel/terminal-confirmation/deadline block verbatim. It includes the incoming cancellation request. |
| `runner.py`, second check after snapshot/refresh work and before rebalance | Preserve #1091's check and combine it with the same landed bounded wait, admission disable and unconfirmed diagnostics. This caller hunk is synthesized. |
| `transport.py`, `GuardedSession.request` exception boundary | Combine #1091's typed refusal code and retry delay with #1119's three fixed local messages. Other messages remain masked. This handler hunk is synthesized. |
| `source-hashes.json` | Recompute every value from resolved bytes, including test files. |
| `manifests/evidence.json` | Retain both sides' rows, apply each replayed registration delta and hash resolved bytes. The two source heads contribute 12,083 paths, with no removals, before four new resolution artifacts. |
| `tests/integration/stream_cancel_dispatch.py` | Add a real-native mid-tick regression and a private optional injection seam; retain the existing confirmation and deadline cases. |

The cancellation helper, queue timing, loss-driven stream stop and consumer
latency mechanisms match the landed source verbatim. The reviewed
`native_strategy.py`, `native_adapter.py`, `safety.py`, `recovery.py`,
sell-chunk tests and recovery tests retain their exact reviewed bytes.
The runtime delta against the reviewed head is retained as
`content-rebase/resolved-runtime.diff`.

The new regression injects integrity loss through the real ledger mark call,
between the two health checks, while a real native submit dispatcher remains
blocked. Its production source is unchanged in each negative control:

- At 52924b02, cancellation is queued but abandoned at shutdown: zero port
  cancellation calls and one unresolved order.
- At fda24cfe, cancellation reaches terminal confirmation, but another rebalance
  runs after the loss because the branch's second check is absent.
- With the combined callers, terminal confirmation precedes stop, no further
  rebalance occurs, and no order remains unresolved. The two existing real-node
  confirmation/deadline cases pass too.

An incoming-only transport conflict choice also fails #1119's existing
no-HTTP integrity-reason regression. The combined handler passes that regression
and the complete transport/stream selection.

The source-hash correction is mechanical. At unchanged 52924b02, the dedicated
source-hash module runs eight tests with one failure: the sell-chunk test's
recorded digest names its previous bytes. Recomputing all entries makes the
same eight checks pass. The earlier publication validator result did not
establish that this separate required check passed; this correction closes
that gap rather than rewriting the historical result.

The final resolved code passes these pinned-runtime groups, all without failures,
errors or skips:

| Group | Tests | Test time |
| --- | ---: | ---: |
| Sell chunks, recovery and safety | 201 | 41.346 s |
| Transport, stream backpressure/follow-ups and readiness | 159 | 4.206 s |
| Native cancellation, stream-integrity integration and normal runner smoke | 7 | 8.959 s |

That is 367 runtime tests, plus eight source-hash checks. Complete sanitized
output and the two-source-head controls are retained in the resolution
artifacts. Fourteen existing temporary-directory ResourceWarnings remain.
These are synthetic orders, fills, sockets and broker responses; they do not
establish broker acceptance or a universal latency bound. No live unit,
credential store, live latch or host runtime lock was accessed.

Primary references are the landed
[runner](https://github.com/native-agent-stack/native-agent-stack/blob/fda24cfe436310658755a75e5b6b7865512c8df1/blueprints/us-equities/adaptive-paper/runner.py),
[transport](https://github.com/native-agent-stack/native-agent-stack/blob/fda24cfe436310658755a75e5b6b7865512c8df1/blueprints/us-equities/adaptive-paper/transport.py)
and [native cancellation fixture](https://github.com/native-agent-stack/native-agent-stack/blob/fda24cfe436310658755a75e5b6b7865512c8df1/tests/integration/stream_cancel_dispatch.py),
and the reviewed
[runner](https://github.com/native-agent-stack/native-agent-stack/blob/52924b028c8419b48042f80b088ec3135a0f8084/blueprints/us-equities/adaptive-paper/runner.py)
and [transport](https://github.com/native-agent-stack/native-agent-stack/blob/52924b028c8419b48042f80b088ec3135a0f8084/blueprints/us-equities/adaptive-paper/transport.py).
The upstream disconnect behavior is pinned in
[NautilusTrader runtime.rs](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/crates/live/src/python/runtime.rs#L685-L697)
and its [client-runtime regression](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/python/tests/unit/live/test_client_runtime.py#L193-L228).
The source mirror pin and installed NautilusTrader 2.0.0rc5 runtime remain
distinct evidence. The final Git identity, change ID and any registry-only
carry are recorded in the handoff, avoiding self-referential receipt fields.
