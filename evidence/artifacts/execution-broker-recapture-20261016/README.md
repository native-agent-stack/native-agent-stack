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
| Recorded runtime acceptance | `evidence/receipts/runtime-final-native-24-acceptance-20261008.json:14,21-23`:dated24-case/rc0 statement; `:68-71` explicitly excludes broker/paper/engineE2E. No new authentication of the historical private capture |
| Installed broker package versions | GAP-NO-NATIVE-VERSION-CAPTURE in `GAPS.md`; no old transcript reused. `masked/runtime-python-version/stdout.txt:1` is only the interpreter's version |

The Nautilus survivor snapshot in `pins.md` differs from the recorded rc5
source, so no receipt is carried across those pins. Historical ib_async
package2.1.0 is a recorded version at
`evidence/artifacts/new-wsl-layer-reviews-20261001/execution-broker.json:505`,
not newly proven package-to-Git provenance. The Gateway image pin is absent
at that same record's732; a source commit is not a container-image digest.
Kumo's source-described compatibility is separately cited in `angles.md`.
No survivor is retired by a version mismatch, license, popularity or omission.

## Four deliverables

- **F1:** GAP-NO-WINNER; the immutable survivor source proposals are in
  `pins.md:3-11`. Proposal reason: preserve the exact previously reviewed source
  while comparison/adjudication is pending, rather than silently upgrade.
- **E2E:** NOT_RUN, GAP-NO-SELECTED-PIN/GAP-PAPER-SESSION. No install, suite,
  test count or passing result is represented. See `GAPS.md:18-25` for named inputs.
- **F2:** NOT_RUN, GAP-NO-ROLE-INVOKE (`GAPS.md:27-33`). No component invocation
  result/hash is supplied. Version and packet captures cannot satisfy the execution role.
- **Six-angle draft:** `angles.md` covers exactly the nine carried survivors;
  each factual source value has its supporting line, and each unmeasured
  dimension is a named GAP. All disputes await co-op two-family adjudication.

## Native captures and masking custody

`CAPTURES.md` labels each published set as a **masked derivative of native
capture**. Its argv/cwd files contain marked placeholders; stdout/stderr and
rc are transformed only by the published literal byte-masking rule.
Nothing is a retyped output, generated run summary or simulated broker result.
Raw commands, cwd, rc, native stdout/stderr and raw hashes remain private,
named only. The co-op checks exact reproduction before a new PR opens.
Public SHA256 entries bind only published derivative files in this tree.

The only fresh publication invocations are packet preparation, Python `--version`, and
the masker's synthetic unit controls. Packet generation's native argv and rc
are in `masked/packets/argv.json` and `rc.txt`; native stdout is retained in
full, including other catalog-row counts produced by the supported CLI.
The command emits catalog packets; only execution-broker source content is
used here. It dispatches no model research or other-layer comparison.
The `masker-tests` capture is explicitly a synthetic publication-boundary
test, not upstream broker E2E, order safety or component invocation evidence.

No installed broker module was imported. No package/tool/service was installed
on the host or in scratch; all files created for preparation are scratch or
review records. Trading remains closed. No credentials, broker/account/order
calls, units, GO/STOP/ISSUER-HOLD or model routes are touched. Every future
E2E/comparison/adjudication belongs in isolated scratch and needs its named
inputs; this preparation grants no installation or account authority.

## Pinned sources for the publication mechanism

- Native packet tool at the creation base:
  `tools/sota-convergence/lane_packets.py` (supported CLI captured in argv).
- [CPython v3.13.16](https://github.com/python/cpython/tree/v3.13.16),
  `Lib/re/__init__.py` (`escape`, `compile`, `sub`), `Lib/pathlib.py`
  (`read_bytes`, `write_bytes`) and `Lib/subprocess.py` (`run`): supported
  byte substitution and child stream capture. No new upstream dependency.
  The recorder interpreter's native version is separately captured in
  `masked/recorder-python-version/stdout.txt:1`; the existing runtime's3.12.3
  version is distinct and no broker package version is inferred from either.
- The nine original upstream repositories and fixed commits are in `pins.md`;
  role facts are explicitly source review, not a vendor-performance claim.

The old claim table is preserved privately as `INTEGRITY-AUDIT.md`. No private
capture fingerprint or prefix is published. Missing historical capture is
GAP-OLD-CUSTODY, never a reconstructed stand-in for the old execution.
