# Execution-broker recapture: GAP preparation for adjudication

Creation base: native-agent-stack
`1b633d861518fa0d299279b1cfaec11d0fb47f82`. This authored narrative is not
a receipt. Native tool captures are separately labelled under `masked/`.
This replaces the rejected receipt forms of closed PR1205; it does not
reuse that PR's transcribed metadata stdout or authored packet summary.

## F1 reconciliation and bounded inputs

Every locator below refers to the creation base, not a moving branch. The
layer still has no winner: `catalogs/landscape/final-stack.json:9233,9297`.
Its comparison-required status is at9224-9225. The install plan at
`docs/decisions/2026-10-15-new-wsl-clean-install-plan.md:155,588` identifies
nine survivors and the engine-comparison prerequisite. The verdict disagreement
is retained at `catalogs/landscape/us-equities.json:2674-2686`; the verdict
wave identity is `catalogs/sota-convergence/layer-verdict-waves.json:7-10`.
These are source facts. No run pin is invented from component inventory.

The latest matching committed sweep is identified by
`catalogs/saturation/ledger.json:2832` and its layer row at6776; retained
survivors and source-review references are carried in `pins.md`. The scope
does not claim completeness over private/unappended sweeps. The co-op's
`FINAL-EXECUTION-BROKER INPUTS` answer and engine-comparison `RESUME.md`
are coordination inputs cited by name only: phase2 belongs to the co-op,
needs owner-held paper credentials outside sessions and the approved cap,
and was not run by this lane. No owner wording is reproduced.

| Component context (not layer winners) | Pin value and exact source |
| --- | --- |
| Nautilus component run record | `catalogs/landscape/final-stack.json:10906-10914`:2.0.0rc5/source1b0a49d2792a9432a3aca3fcb617ce7a630d905e |
| Alpaca SDK component run record | `catalogs/landscape/final-stack.json:10421-10429`:0.44.0 |
| Component inventory | `manifests/stack.json:1971-1973` and `:1440-1442`:same rc5 and0.44.0 versions |
| Native source binding | `catalogs/landscape/lockfile-source-identities.json:7-17`:Nautilus2.0.0rc5/source1b0a49d2 and published artifact identities |
| Package lock | `blueprints/us-equities/runtime-2604/trading-2604-runtime/uv.lock:1531-1538` and `:104-105`:rc5 and0.44.0; package artifact records are not broker acceptance |
| Scoped October1 review | `evidence/artifacts/new-wsl-layer-reviews-20261001/execution-broker.json:41,97,139`:recorded rc5/source1b0a49d2, Alpaca0.44.0 and historical LEAN985ef30; dated context only |
| Historical paper version mismatch | `catalogs/us-equities/runtime-target.json:58,63`:old1.231.0/Python IB adapter/ibapi10.45.1 paper result does not qualify the selected rc5 IBKR destination |
| rc5-bound Rust transport client | `catalogs/us-equities/runtime-target.json:122` and `docs/decisions/2026-10-13-engine-currency.md:69-71`:rc5/source1b0a49d2 uses Rust `ibapi =3.3.0`; rc6 also retains3.3.0, while the frozen develop sourceca478e42f434d2ce185493f2bb42d112a88d1ffe uses5.0.0. These are separate pins, not the historical Python ibapi10.45.1 |
| Recorded runtime acceptance | `evidence/receipts/runtime-final-native-24-acceptance-20261008.json:14,21-23`:dated24-case/rc0 statement; `:68-71` explicitly excludes broker/paper/engineE2E. No new authentication of the historical private capture |
| Installed broker package versions | GAP-NO-NATIVE-VERSION-CAPTURE in `GAPS.md`; no old transcript reused. `masked/runtime-python-version/stdout.txt:1` is only the interpreter's version |

The Nautilus survivor snapshot in `pins.md` differs from the recorded rc5
source, so no receipt is carried across those pins. Historical ib_async
package2.1.0 is a recorded version at
`evidence/artifacts/new-wsl-layer-reviews-20261001/execution-broker.json:505`,
not newly proven package-to-Git provenance. The Gateway image pin is absent
at that same record's732; a source commit is not a container-image digest.
The carried rust-ibapi sourcebe449c84efd1b52e4a296751d3d6edba2ca53552 is
separate again: its retained README cites a v3-to-v4 migration guide at
`evidence/artifacts/landscape-sweep-20260926/wboayue-rust-ibapi.json:31`.
The exact survivor's [Cargo.toml:7](https://github.com/wboayue/rust-ibapi/blob/be449c84efd1b52e4a296751d3d6edba2ca53552/Cargo.toml#L7)
declares4.2.0, while its [README.md:29-32](https://github.com/wboayue/rust-ibapi/blob/be449c84efd1b52e4a296751d3d6edba2ca53552/README.md#L29-L32)
uses a4.0 dependency example. This source/package-version context is not a
pin equivalence with rc5's exact3.3.0 or frozen develop's exact5.0.0.
Neither that guide nor the develop5.0.0 dependency proves compatibility or
broker acceptance at the rc5-bound3.3.0 client. Kumo's compatibility remains
separately sourced in `angles.md`. The potential hard disqualifiers for IBC,
nautilus_ibapi and ibflex are explicitly DISPUTED there under the existing
angle rules, not bypassed by an uncited rule that every survivor must stay.

## Four deliverables

- **F1:** GAP-NO-WINNER; the immutable survivor source proposals are in
  `pins.md:15-23`. Proposal reason: preserve the exact previously reviewed source
  while comparison/adjudication is pending, rather than silently upgrade.
- **E2E:** partial offline upstream evidence at two survivor source pins;
  `OFFLINE.md` cites native scratch install/test outputs. These offline suites
  require no paper window. Layer-selected/broker acceptance remains NOT_RUN
  with named GAPs; offline synthetic tests are not broker or account calls.
- **F2:** NOT_RUN, GAP-NO-ROLE-INVOKE (see `GAPS.md`). No component invocation
  result/hash is supplied. Version and packet captures cannot satisfy the execution role.
- **Six-angle draft:** `angles.md` covers exactly the nine carried survivors;
  each factual source value has its supporting line, and each unmeasured
  dimension is a named GAP. All disputes await co-op two-family adjudication.

## Native captures and masking custody

`CAPTURES.md` labels each published set as a **masked derivative of native
capture**. Its argv/cwd files contain marked placeholders; stdout/stderr and
rc are transformed only by the published literal byte-masking rule.
Nothing is a retyped output, generated run summary or simulated broker result.
Private raw manifests and command context stay under custody, named only;
published derivatives include actual timestamps. A path-free derivative is
byte-identical to its raw input, so its published hash also equals the raw
hash for that file. Public SHA256 entries bind published bytes; no separate
raw-manifest digest is copied or claimed hidden by the masking rule. The
co-op checks reproduction again for this fold before pushing.

The initial four sets cover packet preparation, Python `--version`, and
the masker's synthetic unit controls. This fold adds the native scratch
offline install/test and strengthened masker-control sets in `CAPTURES.md`.
These are not an assertion that every supporting publication check is in
the supplied custody set. No validator/checklist PASS result is used as
published layer evidence beyond the actual named capture files.
Packet generation's native argv and rc
are in `masked/packets/argv.json` and `rc.txt`; native stdout is retained in
full, including other catalog-row counts produced by the supported CLI.
The command emits catalog packets; only execution-broker source content is
used here. It dispatches no model research or other-layer comparison.
The `masker-tests` capture is explicitly a synthetic publication-boundary
test, not upstream broker E2E, order safety or component invocation evidence.

Scratch upstream packages were installed only in the throwaway environments
named by the masked commands. Offline tests import those scratch packages;
they do not import a closed trading runtime. No package/tool/service was
installed on the host. Trading remains closed. No credentials, broker/account/order
calls, units, GO/STOP/ISSUER-HOLD or model routes are touched. Every future
E2E/comparison/adjudication belongs in isolated scratch and needs its named
inputs; this preparation grants no installation or account authority.

## Pinned sources for the publication mechanism

- Native packet tool at the creation base:
  `tools/sota-convergence/lane_packets.py` (supported CLI captured in argv).
- [CPython v3.13.16](https://github.com/python/cpython/tree/v3.13.16),
  `Lib/re/__init__.py:287,305` (`compile`, `escape`),
  `Modules/_sre/sre.c:1424` (`Pattern.sub`),
  `Lib/pathlib/_abc.py:621,635` (`read_bytes`, `write_bytes`) and
  `Lib/subprocess.py` (`run`): supported
  byte substitution and child stream capture. No new upstream dependency.
  The recorder interpreter's native version is separately captured in
  `masked/recorder-python-version/stdout.txt:1`; the existing runtime's3.12.3
  version is distinct and no broker package version is inferred from either.
- The nine original upstream repositories and fixed commits are in `pins.md`;
  role facts are explicitly source review, not a vendor-performance claim.

The old claim table is preserved privately as `INTEGRITY-AUDIT.md`. No private
raw-manifest fingerprint is published; identity derivatives have the equal-hash
behavior explicitly described above. Missing historical capture is
GAP-OLD-CUSTODY, never a reconstructed stand-in for the old execution.
