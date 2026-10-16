# Token-efficiency FINAL-wave preparation — 2026-10-16

This prepares the three recorded winners at one proposed run pin each: **RTK
0.51.0**, **Headroom 0.40.0**, and **ccusage 20.0.26**. It retains native scratch
installation/test/invocation captures and a delta-only six-angle draft for those
winners plus all five carried survivors. It admits no FINAL state, changes no
default, and does not edit the catalogs or angle records.

The source snapshot is main at `caa224140a2d04ba5f3d0ca320c487a75f9c9ea1`, fetched
when this work started. The layer is reopened, its angle record is missing, and
the FINAL gate remains closed. [resolution-inputs.json](resolution-inputs.json)
records the protocol, verdict wave, covering sweep, carried survivors and the
supported lane-packet command. [generator-token-efficiency.json](generator-token-efficiency.json)
is the producer's complete layer output at that snapshot; the
[native command capture](captures/lane-packet-generation.typescript):1-5 and
[byte comparison](captures/packet-output-binding.typescript):1-5 bind it.
[project_packet.py](project_packet.py) filters only by the eight named
repositories to produce [lane-packet.json](lane-packet.json), preserving every
candidate field, including `pin` and all 11/22/27 ccusage/Headroom/RTK receipts.
Other historical candidates in the generator output are provenance inputs only.
No alternatives were re-surveyed and no new candidates were proposed.

## F1: reconciled run pins

| Component | Historical verdict | Proposed run pin and source commit | Evidence |
| --- | --- | --- | --- |
| RTK | 0.49.0 | 0.51.0 — `e001f773f80b22b7dc4c7a79521b30e35aaef026` | Run, stack and both platform manifests agree; captured installed-host version agrees. |
| Headroom | 0.37.0 | 0.40.0 — `855390d6110e0bbb199d9b97025baac16c2f5cf3` | Run, stack and platform manifests agree; the prior 0.40.0 record was metadata-only, so fresh bounded execution is retained here. |
| ccusage | 20.0.24 | 20.0.26 — `d9821088b98aa536c7a385aa1a4579d6fa02269b` | Run, stack and platform manifests agree; captured installed-host version agrees. |

[pin-reconciliation.json](pin-reconciliation.json) cites each version's exact
value line at the source snapshot. The clean-install plan's token-efficiency row
names the three drifted winners but does not itself provide their versions.
Historical receipts and verdicts keep their original pins and limitations.

The native host probes are separate from the scratch probes:
[RTK](captures/installed-rtk-version.typescript),
[Headroom](captures/installed-headroom-version.typescript), and
[ccusage](captures/installed-ccusage-version.typescript), each with command at
line 1, returned version at line 2, and native return code at line 4. These probes
read only already-installed versions; no new candidate was installed on the host.

## E2E scope and native capture custody

[masked-captures.json](masked-captures.json) indexes **23 actual native
transcripts**. Twenty-one return 0; the intentional RTK child-exit control returns
7 and the packet regression before the fix returns 1. util-linux `script`
records the exact command and return code natively.
[CAPTURE-INTEGRITY.md](CAPTURE-INTEGRITY.md) explains private raw custody,
deterministic masking and the published masker/test. Hashes bind published bytes
only. The initial set passed the private review named
“MASKED-REPRO CHECK PASS foundation/token-efficiency, 2026-10-16”.
The fold replaces four captures and adds five. Its independent reproduction
passed in “#1221 FOLD PRIVATE CHECK PASS, 2026-10-16”: all 23 derivatives match,
staged capture blobs equal the reviewed files, and 11 synthetic controls pass.
[FOLD-REVIEW.md](FOLD-REVIEW.md) maps the corrections and native controls.

All new installs, source exports, caches and run state are kept in an isolated
scratch subtree. The native command headers show explicit install prefixes and
the bubblewrap filesystem contract. Candidate test/invoke runs have networking
unshared. The whole host home is not mounted; two specific mise toolchain paths
under `<host-home>` are mounted read-only at `/bootstrap/node` and
`/bootstrap/uv`, as every bwrap header shows. No credential directory is mounted.
Installers fetch only public package/release
artifacts. No credentials, model calls, live services, host hooks, units or broker
sessions are used. [The native source binding](captures/source-export-bindings.typescript):1-12
compares complete `git archive` exports to the executed source trees at the
three stated pins (607/2573/501 files) and compares the copied Headroom tests.
The fresh test captures mount their source/test inputs read-only.

| Component | Upstream supported path at the pin | Captured scope |
| --- | --- | --- |
| RTK | [install.sh:9,172](https://github.com/rtk-ai/rtk/blob/e001f773f80b22b7dc4c7a79521b30e35aaef026/install.sh#L172) accepts `RTK_INSTALL_DIR` and `RTK_VERSION`; [README:95](https://github.com/rtk-ai/rtk/blob/e001f773f80b22b7dc4c7a79521b30e35aaef026/README.md#L95) documents the installer. | Fresh vendor release install with shell tracing: [capture](captures/rtk-install.typescript):47,51 finishes downloads before hashing at :61; published EXPECTED :58 equals ACTUAL :63. Version :90 and rc :104 are native. Full Rust suite was not run. |
| Headroom | [README:91](https://github.com/headroomlabs-ai/headroom/blob/855390d6110e0bbb199d9b97025baac16c2f5cf3/README.md#L91) documents isolated `uv tool install`; [pyproject.toml:246](https://github.com/headroomlabs-ai/headroom/blob/855390d6110e0bbb199d9b97025baac16c2f5cf3/pyproject.toml#L246) defines the MCP extra; [CONTRIBUTING:79](https://github.com/headroomlabs-ai/headroom/blob/855390d6110e0bbb199d9b97025baac16c2f5cf3/CONTRIBUTING.md#L79) uses pytest. | Fresh `headroom-ai[mcp]==0.40.0` tool environment; unmodified upstream CCR test file; upstream seeded lexical-token benchmark. No proxy/MCP server or native ONNX detector qualification. |
| ccusage | [installation.md:58](https://github.com/ccusage/ccusage/blob/d9821088b98aa536c7a385aa1a4579d6fa02269b/docs/guide/installation.md#L58) documents npm install; [justfile:52](https://github.com/ccusage/ccusage/blob/d9821088b98aa536c7a385aa1a4579d6fa02269b/justfile#L52) gives the exact Node test command; [environment-variables:124](https://github.com/ccusage/ccusage/blob/d9821088b98aa536c7a385aa1a4579d6fa02269b/docs/guide/environment-variables.md#L124) documents offline mode. | Fresh npm scratch prefix with native package/version and offline fixture smokes. The 34 Node tests execute the separately pinned source tree, not the installed package. Full Rust/parser coverage was not run. |

The Headroom tests run from a test-only directory. Its complete copied
`tests/` tree, including `conftest.py`, matches the pinned archive
([binding](captures/source-export-bindings.typescript):8); imports resolve to
the installed wheel. The lexical benchmark uses the upstream seed and a
public tokenizer vocabulary cached before execution; its captured command keeps
networking blocked. The earlier uncaptured exact-command draft and estimator
fallback output are not used as substitutes for these fresh transcripts.

## Simulation results and F2 limits

| Native operation | Captured result | Boundary |
| --- | --- | --- |
| RTK preview and recovery | [preview](captures/rtk-preview.typescript) returns the requested ten lines; [recovery](captures/rtk-recovery.typescript):1-6 runs `cmp`, reports 2047 bytes for both copies and matching public-fixture hashes. [exit-control](captures/rtk-exit-control.typescript):3 records rc 7. | **SIMULATION.** Direct reread recovery is not automatic SQLite recall or live hook integration; a truncated preview is not semantic-completeness proof. |
| Headroom CCR tests | [capture](captures/headroom-ccr-tests.typescript):3 reports 15 passed; :5 records rc 0. | **SIMULATION / upstream unit tests.** Not production traffic or model-quality evidence. |
| Headroom seeded corpus | [capture](captures/headroom-benchmark.typescript):13,23 reports 178024 → 104261 lexical tokens; :2 identifies TiktokenCounter and :3 identifies pure-Python content detection. | **SIMULATION.** Both shown configurations return the same table. No provider savings, quality parity or live-session result is claimed. |
| ccusage Node tests | [capture](captures/ccusage-node-tests.typescript):44,46,47,49 reports 34 tests, 34 pass, 0 fail and 0 skipped. | **SIMULATION / upstream unit tests.** Only the upstream Node target, not every native adapter. |
| ccusage synthetic report | [capture](captures/ccusage-fixture-report.typescript):28-33 reports 100 input, 20 output, 30 cache-creation, 40 cache-read, 190 total and 0.01 cost. | **SIMULATION.** Values originate in [the published fixture](fixtures/claude-session.jsonl):1. The cost is not an observed bill. |

[execution-receipt.json](execution-receipt.json) connects every claim to the
native transcript and exact output lines. [invoke-evidence.json](invoke-evidence.json)
shows bounded native component invocation, with a named **production adoption
window GAP**. The co-op must decide whether dated historical use evidence meets
its named F2 window, or request separately authorized native-session capture.
The final-stack schema has not been changed.

## Six-angle draft and disputed dimensions

[multi-angle-draft.json](multi-angle-draft.json) contains A1 capability, A2
engineering quality, A3 community consensus, A4 net usage, A5 publications and A6
outcomes for all eight candidates. Scores remain null where the evidence is
missing or disputed. The existing policy weights are recorded, not newly chosen
from these results. All new install, test and simulation evidence is assigned
to A1 only. A2 remains a separate evidence gap; A6 cites historical outcomes or
comparative gaps, with no new smoke references
([policy](../../../docs/decisions/2026-10-12-angle-records-final-check.md):240-241).

The co-op's two-family reads need to resolve these distinct questions:

- Whether the three proposed pins reconcile the current role without extending
  old qualification boundaries.
- Whether RTK's historical narrow one-client study and current recovery smoke
  support the requested role, given cache, modality and extraction confounds.
- Whether Headroom's prior omission-notice/detector concerns are resolved at
  0.40.0. CCR tests and lexical reductions alone cannot answer this.
- Whether ccusage's complete attempt/child/source accounting can be established;
  fixture totals and list-price estimates do not answer that question.
- How to adjudicate all five survivors. MCP Compressor and Klavis have explicitly
  missing GPT fit returns; a missing return does not retire a survivor or permit
  a trial. Klavis retains the historical maintenance rejection; its reconsideration
  requires an evidenced supersession. Sqz,
  Paritok and agent-console retain their earlier disputed comparison questions.
- What independent community, usage and publication evidence is still required
  for multi-angle convergence. This preparation does not re-survey those fields.

Current-pin macOS execution, live adoption-window evidence, and a fresh
randomized task-quality/complete-provider-use comparison remain named gaps. The
safe disposition is **GAP pending co-op adjudication**, not FINAL.

## Validation and review custody

All artifact files are registered through the existing
`scripts.host_receipts.register_file` function. Repository validation runs with
`python3 scripts/validate.py` before commit. No new implementation script is added
under `scripts/`. The masking script and synthetic tests belong to this evidence
bundle. No raw private transcript, raw digest, host name or personal home path is
published. Private direction/review records are cited by name only.

The co-op owns private reproduction and both family reads. This lane does not
dispatch a model read, merge the PR, enable a service, or promote a default.
