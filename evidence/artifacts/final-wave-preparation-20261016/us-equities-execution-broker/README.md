# Execution/broker FINAL-wave preparation: GAP draft

Prepared against native-agent-stack main
`caa224140a2d04ba5f3d0ca320c487a75f9c9ea1` on 2026-10-16. This is a
single-layer preparation record for two-family adjudication, not FINAL
admission or a new broker selection. All nine carried survivors remain
unresolved. No broker-side installation or broker/account/order call ran.

## Resolution inputs and prerequisite

The current source of truth is unambiguous:

- `catalogs/landscape/final-stack.json:9221-9297` records
  `us-equities/execution-broker` as `no-winner`, `comparison_required`, with
  nine survivors and an empty winner set. Its verdict is `pending_lanes`
  with counterbalanced disagreement, not a completed selection.
- `docs/decisions/2026-10-15-new-wsl-clean-install-plan.md:155,588` defers
  this layer to the engine comparison. Its nearby IBKR and Alpaca routes
  describe existing component roles, not winners of this layer.
- `catalogs/landscape/us-equities.json:2674-2686` and
  `evidence/artifacts/layer-verdicts-20260922/adjudication/us-equities-execution-broker-20260922.json`
  preserve the disagreement over including the unqualified native IBKR
  adapter alongside the Alpaca components. The verdict wave is identified
  by `catalogs/sota-convergence/layer-verdict-waves.json:7-13`.
- The latest matching committed sweep is `landscape-sweep-20260926`,
  `catalogs/saturation/ledger.json:2832,6776`. Its manifest and returns are
  `catalogs/sota-convergence/manifest-20260926.json` and
  `evidence/artifacts/landscape-sweep-20260926/returns.json`. The earlier
  matching sweep carried no survivors. The later sweep's nine survivors
  are all retained here, including auxiliary roles. Its retained-failure
  reopening and capped/cached research limitations remain limitations;
  survival is not a winner verdict or clean saturation.
- The co-op's `FINAL-EXECUTION-BROKER INPUTS` answer and engine comparison
  `RESUME.md` identify phase 1 as complete and phase 2 as not run. These
  coordination records are cited by name only. Phase 2 belongs to the
  co-op and requires owner-held paper credentials outside sessions and
  the approved cap. This lane neither obtains those inputs nor runs it.

No newer completed adjudication was supplied with the scope clarification.
This draft bounds its survivor accounting to the committed ledger above;
it makes no repository-wide or private-sweep completeness claim.

## F1: pin reconciliation

**Disposition: GAP-F1-NO-WINNER. Proposed layer run pin: none.** Selecting
a single broker run pin before the comparison and adjudication would invent
a winner. `candidate-pins.json` instead proposes one immutable source pin
for each carried survivor, preserving every source-vs-runtime distinction.
These are source-review proposals, not admitted install/run pins.

| Pin source on the creation base | Observation | Reconciliation |
| --- | --- | --- |
| `catalogs/landscape/final-stack.json:9233,9297` | No winner; no winner-to-run mapping | Stop winner admission until the comparison result and two-family adjudication exist |
| Clean install plan `:155,588` | No execution-broker winner; nine survivors | Agrees with the generated row |
| Global run record `catalogs/landscape/final-stack.json:10906-10914` | NautilusTrader2.0.0rc5, source1b0a49d2792a9432a3aca3fcb617ce7a630d905e | Component pin, not an execution-broker winner |
| Global run record `catalogs/landscape/final-stack.json:10421-10429` | alpaca-py0.44.0 | Component pin, not an execution-broker winner |
| Component inventory `manifests/stack.json:1440-1445,1971-1976` | alpaca-py0.44.0 and NautilusTrader2.0.0rc5 | Agrees with the global run records; inventory adoption is not this layer's adjudication |
| Packet manifest `catalogs/sota-convergence/manifest-20260926.json:15373-15470` | Historical adaptive-paper7e7eefe2, Alpaca0.44.0/sourcecc4cb3b7, LEAN Alpaca1973f616, native IBKR rc5/source1b0a49d2 | Different role/source records; their labels do not resolve the layer's counterbalanced disagreement |
| Broker boundary `catalogs/us-equities/runtime-target.json:9,55-58,158-165` | Existing rc5/Alpaca component routes; selected rc5 IBKR acceptance not established | Historical1.231.0 Python-adapter paper evidence does not qualify rc5 |
| `catalogs/landscape/lockfile-source-identities.json:7-21`; runtime lock `:1531-1538` | Nautilus version/source binding and published package artifacts | Same rc5 component pin; do not replace it with the survivor's research snapshot |
| Runtime lock `blueprints/us-equities/runtime-2604/trading-2604-runtime/uv.lock:104-105` | alpaca-py0.44.0 | Same SDK component pin |
| Scoped layer evidence `evidence/artifacts/new-wsl-layer-reviews-20261001/execution-broker.json:41,86,97,139,505,732` | rc5/source1b0a49d2, Alpaca0.44.0, historical LEAN985ef30, ib_async2.1.0 with unresolved package provenance, and no adopted Gateway image pin | Record different roles and unresolved provenance instead of treating all as one final run pin |
| Latest runtime acceptance referenced by the generated packet: `evidence/receipts/runtime-final-native-24-acceptance-20261008.json:14-24,67` | Dated24-case offline runtime acceptance, bound by `runtime-final-lock-binding-20261008.json` to the lock | Existing component/runtime evidence; explicitly excludes broker/paper and engine E2E qualification |
| Fresh metadata-only observation: `host-version-observation.txt` | Existing runtime reports Nautilus2.0.0rc5 and Alpaca0.44.0; no ibapi or ib_async distribution metadata in that runtime | No package-version drift for the two probed components; no broker import, health check, whole-host absence claim or invoke qualification |

The packet also names an older adaptive-paper source pin. That repository
glue is not silently equated with current main or a vendor adapter release.
The record above is the latest scoped evidence inspected, not a full-history
search for every later paper-service change. The runtime remains closed to
trading; its read-only metadata observation does not reopen it.

Important unresolved drift is explicit: the Nautilus survivor's source
snapshot is cd417b80, while the component run record is rc5/source1b0a49d2;
historical1.231.0/ibapi10.45.1 paper evidence does not qualify the rc5 native
adapter; ib_async's2.1.0 package-to-source identity remains unverified;
repository commits do not freeze Gateway/TWS images or their transitive
versions; Kumo advertises Nautilus1.229.0/Python3.13 rather than the recorded
rc5/Python3.12.3 runtime. No survivor is dropped because of drift, archive
status, license, popularity or omission from the packet's original candidates.

## E2E at the run pin

**Disposition: GAP-E2E-NO-ADJUDICATED-PIN; broker acceptance also has
GAP-E2E-PAPER-SESSION.** No install or upstream suite ran in this preparation:
there is no admitted layer run pin, and the co-op expressly retains the
no-install scope until phase 2. Commands, exit codes and test counts in
`preparation.json` distinguish NOT_RUN from success; an unexecuted command
has no fabricated exit code. A successful metadata read is not E2E.

When the named inputs exist, the proposed next action is to freeze the
comparison-selected adapter/package pin, then use that vendor's supported
isolated install and unchanged tests before separately scoped paper-session
acceptance. This is a **PROPOSAL**, not a queued operation by this lane.
Existing pinned source routes are retained in the October 1 review; for
example, Nautilus rc5's README install route and Makefile/workflow tests at
1b0a49d2. This record does not run them, start a gateway/container, or
substitute local mocks for broker acceptance.

## F2: invoke evidence

**Disposition: GAP-F2-NO-SELECTED-INVOKE-ROLE.** No broker component was
invoked for its execution role in this measured window. Command, exit code
and output hash are null in the F2 record because no such invocation ran.
The native stdlib metadata probe has its own real command/rc/stdout record
in `observations.json`, excluded from F2. Historical paper and offline
receipts retain their own pins/windows and are not relabelled as new invoke
evidence. A legitimate invoke needs the adjudicated pin and a separately
authorized co-op/trading-owner paper window; this lane makes no broker call.

## Six-angle delta draft and disputes

`six-angle-draft.json` covers exactly the nine carried survivors. Pinned
upstream README retrieval verifies source-level role claims only. The
six dimensions are kept separate:

| Angle | Evidence in this preparation | Disputed dimension / required input |
| --- | --- | --- |
| Capability at the pin | Primary README at each retained commit; previous scoped source/evidence records | Broker lifecycle, timing, reconciliation and causal same-task fit remain unmeasured at a selected layer pin; ibflex is an auxiliary parser, not a direct execution substitute |
| Upstream engineering quality | Pinned source descriptions, documented compatibility and historical maintenance observations; IBC's pinned README announces retirement | No fresh unchanged suite or cross-adapter failure comparison; archive/retirement metadata alone does not decide the layer |
| Community consensus | No independent user/community study at these pins supplied | Prior model votes and stars are not community consensus; remains GAP |
| Net usage | No measured adoption/retention or operational-use evidence at these pins | Popularity counters and README badges cannot establish net usage; remains GAP |
| Published evaluations | No comparable published evaluation on the required equity/order/recovery contract supplied | Marketing claims and unrelated backtests do not establish this dimension; remains GAP |
| Our measured runs | Read-only version inventory and packet preparation; historical receipts remain separately scoped | No new candidate E2E or broker invocation; comparison phase2 and later broker acceptance remain GAP |

No single angle promotes or eliminates a survivor. The co-op owns the
two-family adjudication of the marked disputes; no model read was dispatched
by this lane. The draft contains neither a FINAL admission nor a new default.

## Reproduction and primary sources

`tools/sota-convergence/lane_packets.py` at the creation base generated the
us-equities packets with the committed September26 manifest. The CLI offers
catalog selection, not one-layer selection:12 packets were emitted to
scratch, and only execution-broker was consumed for this record. This did
not dispatch research or execute another layer. `packet-receipt.json`
records the exact supported flags and scope; the other generated packets
are not part of this PR.

All nine primary source URLs and immutable commits are in
`candidate-pins.json`, alongside their published retained source-review
references. Two additional component sources checked are
[Nautilus rc5 README](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/README.md)
and [alpaca-py0.44.0 source README](https://github.com/alpacahq/alpaca-py/blob/cc4cb3b7ba50ae250e621983c2779047fb16bb28/README.md).
The metadata-only version API is native
[CPython v3.12.3 importlib.metadata](https://github.com/python/cpython/blob/v3.12.3/Lib/importlib/metadata/__init__.py).
The selected native IBKR integration source is
[the rc5 integration document](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/docs/integrations/interactive_brokers.md),
as retained by the October1 review; no broker acceptance is inferred.

This public record contains no private coordination path, host name,
credential, or fingerprint of unpublished bytes. It grants no paper/live
arming, broker access, service enablement, model route or account action.
