# REST proof after a stream-only recovery refusal; clean empty scans

Date: 2026-10-15. Scope: canonical launcher glue and new recuts only.

## Trigger and decision

A flat stage can trade no symbols, leaving recovery with no quote subscription
that can become ready. The native transport then reports its stream-start
TransportError; recovery correctly leaves flatness unknown. A successful
earlier zero-count preflight does not resolve that uncertainty. Reconnecting
or retrying the same empty subscription is not a flat proof.

The CC's REST-fallback ruling supersedes the earlier retry proposal. After
the specific native stream-readiness error, the launcher may use the existing
GET-only observer only when native position/open-order/submission counts are
strict integer0/0/0, there is exactly one matching TransportError, there are
no local positions/unresolved orders or submit/cancel/exit attempts, and no
prior broker snapshot/reconciliation exists. The fixed message template and
native stream-reason allowlist reject unknown or mixed integrity/order/REST
failures. A fresh observer0/0 proof must pass the existing handoff validator.

The original native recovery receipt is preserved. If the observer fails
without emitting a result, ordinary validation uses the original failed
receipt and records flat=false; no handoff is silently repaired. A non-flat
REST answer also refuses. The existing private-marker ownership, operator
STOP preservation, active-trial retirement and handoff binding stay intact.
The120s observer budget was already reserved for the no-owned-trial fallback;
there is at most one of those two observer paths after a native attempt, so
the reviewed outer budgets remain sufficient.

An empty validated PRE scan is separately a clean no-trade outcome. The native
runner's immutable no-start receipt/rc2 remain preserved; the launcher binds
its config/scan hashes and empty selection, records an INFO no-trade event
with selected_symbols0/orders_submitted0, and returns0 to systemd. Thus the
empty scan itself does not trigger OnFailure. The receipt remains explicitly
non-trial evidence and does not certify account flatness. Existing recovery
still runs. The source scan contains no evaluated-universe count; the record
does not manufacture one.

## Primary sources

All native locators below are at base
`8053f14e7e0817d2502dff2bb284bfb7e1b0152f` in
[native-agent-stack](https://github.com/native-agent-stack/native-agent-stack/commit/8053f14e7e0817d2502dff2bb284bfb7e1b0152f).

- `tests/fixtures/seq2-launch.txt:516-520`: existing
  `no_owned_trial_to_recover` / `no_mover_trial_to_recover` GET-only
  `observe_flat.py` fallback, reused rather than replaced.
- `blueprints/us-equities/paper-flat-proof/observe_flat.py:27-49`:
  native bounded synchronous preflight, complete REST positions/orders proof,
  no order submission; failure returns2 without fabricating a successful file.
- `blueprints/us-equities/adaptive-paper/transport.py:1793-1800`:
  fixed stream-readiness TransportError and native failure-reason template.
  Its native reason producers supply the explicit allowlist; observation-loss,
  identity and order ambiguity remain excluded.
- `blueprints/us-equities/adaptive-paper/recovery.py:228-229,326-358`:
  streams start before the first snapshot/order work; native failure receipt
  retains errors, local positions/orders and unknown reconciliation.
- `blueprints/us-equities/adaptive-paper/mover_runner.py:592-601,701-703`:
  existing empty-scan no-start receipt and rc2 before credential loading.
- `blueprints/us-equities/adaptive-paper/mover_runner.py:690` and
  `exploration.py:45-51`: native receipt config digest uses the loaded mover
  config and effective RiskLimits for exploratory lane B, rather than raw
  CONFIG bytes. `mover.py:320` supplies the supported config loader.
- `blueprints/us-equities/adaptive-paper/runner.py:554`: public preflight's
  orders_submitted is fixed at zero. This field only restricts eligibility;
  account flatness rests on the fresh complete REST counts.
- `blueprints/us-equities/paper-lane-latch/r3_contract.py:31-49`:
  source-bound canonical method graft, extended with the fallback helper/call
  while retaining the source generation's recovery/latch implementation.
- [systemd259](https://github.com/systemd/systemd/blob/v259/man/systemd.unit.xml),
  OnFailure: activates on a failed unit; clean process exit avoids that failure
  for the no-trade outcome. A genuine recovery failure still remains a failure.

No new adapter, credential loader, broker transport or dependency is added.
The frozen runtime and CONFIG bytes and all already sealed packets stay intact.

## Fail-first validation and limits

### Correction to the initial #1172 candidate

At initial candidate `e111051b3f68aeacfa1b58e20b619508d3b9c535`, the
positive recovery fixtures supplied the inner engine receipt directly. They
missed two real consumer/producer boundaries. Pinned primary sources establish:

- `paper-readiness-seq3/recut.py:114-136` at the base replaces the entire
  `stop_mark` through `recover_stage` span. A helper inside that span is
  removed for direct fixture consumers. Keep it before `stop_mark`; keep a
  single helper and call when the later r3 graft consumes an already rewritten
  fixture. The landed seq3 implementation and its source pin remain unchanged.
- `adaptive-paper/runner.py:2889-2901` at the base overwrites the saved public
  recovery mode with `adaptive_paper`. RTH gating must use that public CLI
  contract, rather than the inner `official_sdk_recovery` mode. The mover
  producer retains its inner mode; missing required preflight evidence still
  refuses. No native producer or frozen runtime bytes are changed.

Correction regressions call the actual `runner.py recover` parser/main,
config loader, public-preflight summary, projection and output writer with
fixture credential/account/transport/engine boundaries. Saved output is
consumed directly, without rewriting its mode or decorating it in the test.
A successful saved CLI receipt through direct seq3 rewriting fails with the
missing-helper NameError before the fix. A real saved RTH CLI stream-refusal
receipt has adaptive_paper and integer0/0/0 but fails recovery_not_flat before
the mode correction. Both pass with the prepared corrections. The direct
stage-latch module is explicitly included in the correction test scope.

These CLI tests use scratch ledger/state and fake boundaries only. They do
not claim a native broker run or connect a lane credential/stream. Existing
inner-engine fixtures remain unit coverage, separate from this public CLI
output coverage. The initial test-set receipt is retained as its actual
limited scope, not promoted to coverage of the omitted boundaries.

The CC's same-head read also identified an incomplete downstream proof
contract: the fallback writes `stream-flat-probe.json`, but the inherited
`verify_handoff` at initial fixture:213-217 considers only the two legacy
filenames. Extend the fixed per-instance allowlist under the SAME recorded
`native_recover_sha256`; retain ownership, flatness, configuration, bundle,
trial, boot and drain checks. Graft the canonical validator into generated
packets as well as fixing the fixture. A stale legacy file must not take
priority over the exact recorded proof; no matching proof still refuses.

The next-stage regression consumes actual RTH CLI output, performs the real
GET observer recovery, then drives the real next-stage issuer and binding.
Before this correction the issuer refuses `previous_native_recover_hash`.
After it, issuance/binding pass; tampering with the stream proof still refuses
under that same hash check. Authority, clock, unit inventory and all GO/state
files in the test are SYN fixtures. This does not issue a real GO or run a unit.

### Correction to reviewed head 51369893

The exploratory empty-scan regression now uses native `command_paper` with
the published mover configuration and lane B exploratory labels, validating
the real scan, paths, effective limits/digest and no-start serializer. Before
the correction, this valid native receipt returns2 with no INFO event. The
launcher now calls the same pure `load_mover_config`/`config_digest` functions;
the existing raw CONFIG admission seal remains separate. A qualification
control also traverses the real producer, and raw-digest substitution or scan
mutation refuses without a clean no-trade event. No credentials are loaded.
Unlabelled legacy frozen producers predate `exploration.py`; their unchanged
native raw-config digest is retained without importing that newer module.
The retained legacy frozen producer was also measured with the same empty-scan
test, separately from the current producer and exploratory digest regression.

The held local proof-selection P2 and GPT's retry P2 describe the same defect:
a partial nonmatching stream receipt raises JSONDecodeError before the native
receipt bound by the handoff is reached. The bounded descriptor reader checks
regular-file type, owner and the existing64KiB cap, hashes the captured bytes,
then decodes only the matching candidate. CPython v3.12.3's supported
`os.open`/`fstat`, buffered `read(size)`, `hashlib.sha256` and `json.loads`
interfaces implement this snapshot; the regression verifies a successful
real native recovery remains admissible beside that partial stream file.

The scratch next-stage regression now fixtures `lane_latch.assert_issuer_python`
because host-interpreter qualification is a separate native gate. A simulated
CPython3.13 host fails `issuer_python_3_12_required` before this test-only fix,
then reaches the real issuer/proof/binding paths after it. Production's3.12
issuer gate is unchanged. The record also explicitly describes the replaced
handoff validator and the public preflight submission counter's limitation.

The pinned mover CLI does not publish the required preflight counters. That
missing evidence remains a refusal for this new stream-error path; no zero
counts are inferred from an empty ledger. Its ordinary no-owned-trial GET
fallback is unchanged. Operational qualification of the new path is therefore
the public RTH CLI contract exercised here, not a claim about missing PRE data.

`tests.test_lane_b_stream_flat_fallback` exercises the emitted private-latch
launcher and the actual GET observer/preflight with fixture HTTP answers.
It never reads a credential or opens a real stream. The empty-traded-symbol
case invokes native recovery with an empty fake ledger and a fake stream port,
then proves flat through the real observer. Positive/REST-path and empty-scan
cases go RED against the base; existing non-flat/non-stream refusal guards
already pass there and remain required negative coverage.

Cases cover persistent stream failure with0/0/0 and REST flat; non-flat native
preflight; failing/non-flat REST; no traded symbols; non-stream/mixed integrity
errors; malformed boolean counts; and empty-scan rc0/INFO/non-trial recording.
Adjacent latch, recovery-only acceptance, grace/order and native GET observer
tests remain required. Actual execution counts and retained logs belong in
the PR record; raw private-log fingerprints do not belong in public records.

Both review families precede installation or any new recut activation.
No builder or test connects a live stream with a lane credential during a
session. The current incident's state operation remains with trading-cc;
there is no issuer restart, STOP/HOLD edit or handoff mutation in this PR.
After approved installation, the documented native recovery path must create
its own flat handoff before the co-op restarts the issuer.
