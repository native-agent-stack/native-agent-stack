# Native-client FINAL preparation at exact run pins

Status: preparation for two-family review. No FINAL admission or active pin change.

This record proposes **Claude Code 2.1.301** and **Codex 0.162.1** as the exact
pins for subsequent native-client measurement. Fresh, isolated vendor-native
installations completed at both versions; offline version/help commands also
completed. The actual process streams are retained as labelled masked native
captures. Authenticated task E2E, full tool invocation, recovery and comparative
A6 remain explicit gaps.

## F1: reconcile the run pins

Repository path:line references in this table refer to source base
`1b633d861518fa0d299279b1cfaec11d0fb47f82`. New capture references are relative
to `evidence/artifacts/final-native-clients-prep-20261016/`. The full derived
reconciliation is [pin-reconciliation.json](../../evidence/artifacts/final-native-clients-prep-20261016/pin-reconciliation.json).

| Source | Claude Code | Codex |
| --- | --- | --- |
| `catalogs/landscape/final-stack.json:10497`, `:10541`, `:10536` | Generated run 2.1.295 | Generated run 0.160.0; separate macOS conflict 0.155.1 |
| Same file, `:6992` / `:7014` | Verdict 2.1.278 | Verdict 0.155.1 |
| `adoption/pins-linux-x86_64.json:106` / `:54` | 2.1.295; minimum matching at line 118 | 0.160.0 |
| `adoption/pins-macos-arm64.json:86` / `:60` | 2.1.295; minimum matching at line 100 | 0.155.1 |
| `evidence/artifacts/new-wsl-install-plan-20261002/install-plan.json:13` / `:54` | Reviewed release v2.1.287; line 47 says it is not a runtime lock | Reviewed release rust-v0.160.0; line 96 says it is not locked |
| `docs/decisions/2026-10-15-new-wsl-clean-install-plan.md:140` | F1, E2E and invoke gaps | F1, E2E and invoke gaps |
| Same decision, `:700`, `:701`, `:1027`, `:964` | Earlier 2.1.295/2.1.300 observations are superseded by 2.1.301 | Observed 0.162.1; the installer row does not freeze its runtime |
| `catalogs/landscape/angles/foundation-native-clients.json:39` / `:168` | Earlier public source commit `3deb873687379f0c199a69fdaccc65f0865f7a29` | `092d3acd6bec3e3a14bdc7e7a2810ab628ab759d`, matching rust-v0.162.1 |
| Pin-bearing registered native CLI evidence | `evidence/receipts/native-sdk-role-mcp-followup-20261002.json:1`: staged 2.1.288 | `evidence/receipts/codex-01592-host-finalization-20260930.json:23`: 0.159.2 |
| Fresh existing-client version capture | `native/host-claude-native-version.stdout.txt:1`: 2.1.301, rc at `native/index.json:1159` | `native/host-codex-version.stdout.txt:1`: 0.162.1, rc at `native/index.json:1211` |
| Fresh scratch version capture | `native/claude-version.stdout.txt:1`: **2.1.301** | `native/codex-version.stdout.txt:1`: **0.162.1** |

The newest commit touching any receipt registered to either component is
`7742970d31e384b478a0a23af79940c6e12d9b2c`, the artifact index rather than a
native client qualification. The exact native Git outputs are
`native/latest-evidence-claude-code.stdout.txt:1` and
`native/latest-evidence-codex.stdout.txt:1`; each line 3 names that index.
The registered pin-bearing records are distinguished in the table. Commit
recency does not establish execution recency or stronger qualification.

The co-op also supplied F1 input from `HARNESS-INSTALL-STATUS-20261016.md`,
cited by name only: the reviewed installer releases differed from the reported
installed 2.1.301 / 0.162.1. The source record's exact lines were not supplied
to this lane, so that other-host observation remains attributed. Its public
release-binary digests now have separate, fresh scratch verification:

| Public release binary | SHA-256 | Fresh native source |
| --- | --- | --- |
| Claude Code 2.1.301 Linux x64 | `bc1aad9982c7b59c7d889ff92595d61cf46e0a6eae074cb551d932a989bcd222` | `native/claude-installed-sha256.stdout.txt:1` |
| Codex 0.162.1-x86_64-unknown-linux-musl standalone | `628e35487d888a28f0427fc37501da529dd3d81fcbad7a2c3421c1e8670d92e1` | `native/codex-installed-sha256.stdout.txt:1` |

The proposals align the clean-install record with exact-version scratch
observations. Minimum floors, unversioned installer invocations and older role
receipts do not substitute for this run pin. Old run/verdict/source pins and the
macOS gap remain explicit. Adoption files, catalog winners, angle scores,
routes and the generated final stack are unchanged.

## Native captures and E2E-partial boundary

[native/index.json](../../evidence/artifacts/final-native-clients-prep-20261016/native/index.json)
contains the marked command placeholders, native return codes, timestamps and
published output hashes. Each hash has a published preimage. The private
originals retain exact argv/cwd and raw byte streams. The published
[masker](../../evidence/artifacts/final-native-clients-prep-20261016/mask_native.py)
changes only explicit literal paths/identity spellings. It preserves all other
bytes, including ANSI escapes, CR/LF, invalid UTF-8 and missing final newlines.
Its [tests](../../tests/test_native_client_capture_custody.py) use synthetic
fixtures and are labelled as custody controls, not client outcome measurements.

| Observed execution | Native source | Native rc source |
| --- | --- | --- |
| Claude vendor manifest signature/key | `native/claude-manifest-verify.stderr.txt:3`; `native/claude-key-fingerprint.stdout.txt:3` | `native/index.json:418`: 0 |
| Claude native install 2.1.301 | `native/claude-native-install.stdout.txt:7` | `native/index.json:513`: 0 |
| Codex upstream installer, explicit 0.162.1 | `native/codex-native-install.stdout.txt:9` | `native/index.json:988`: 0 |
| Claude version and help, network disabled | `native/claude-version.stdout.txt:1`; `native/claude-help.stdout.txt:1` | `native/index.json:676` and `:160`: 0 |
| Codex version and help, network disabled | `native/codex-version.stdout.txt:1`; `native/codex-help.stdout.txt:1` | `native/index.json:1108` and `:765`: 0 |
| Original existing-host launcher version probe | `native/host-claude-version.stderr.txt:1`: missing home setting under the scrubbed environment | `native/index.json:1185`: 127 |
| Separate direct native version probe | `native/host-claude-native-version.stdout.txt:1`: 2.1.301 | `native/index.json:1159`: 0 |
| Fail-first recorder and masker controls | `native/red-recorder-control.stderr.txt:1`; `native/red-mask-control.stderr.txt:1` | `native/index.json:1542` and `:1516`: 1 |
| Synthetic custody suite | `native/green-capture-controls.stderr.txt:9`, `:11`: six tests, OK | `native/index.json:1134`: 0 |

[capture-summary.json](../../evidence/artifacts/final-native-clients-prep-20261016/capture-summary.json)
is explicitly **derived analysis**, not native output. Its aggregate counts are
computed from the capture index and cannot replace a missing stream. No upstream
unit/integration suite or authenticated model task was run.

The earlier preparation discarded its raw streams after normalization. Its
two resolver-namespace failures and one missing-`awk` namespace failure remain
disclosed historical observations with a named capture gap. Those logs are not
included as qualifying receipts. The fresh observations above are separate
native executions; no inverse masking reconstructs the missing originals.

All new binaries and installation state remain in isolated scratch profiles.
The namespace makes the host root read-only, masks host homes/runtime sockets,
and clears inherited environment. A scratch profile is mounted over the
unchanged caller-home pathname. Version/help smokes additionally disable
networking. Existing host probes only request `--version`. No host installation,
service activation, account login, broker call or host runtime lock is involved.

## Named gaps and their closure

| Gap | What was not run and why | What closes it |
| --- | --- | --- |
| `native-clients-authenticated-task` | A native model task; requires a credential-bearing account | A `credential_run`-fenced native harness task under a CC cap, retaining command, rc, output and task oracle |
| `native-clients-full-tool-invoke` | Full model/tool execution; version/help are readiness only | A fenced full-layer harness invocation under a CC cap, retaining native tool events and effects |
| `native-clients-session-recovery` | Same-session/thread recovery at these pins; requires an authenticated task | Existing recovery fixtures under the fence and cap, retaining identity, unchanged checkpoint and checkpoint-once checks |
| `native-clients-A6` | A paired comparative outcome run; no admitted credential-bearing arms were run | A preregistered paired harness run with fixed decision rule, the fence/cap and measured public receipts |
| `native-clients-macos` | Neither proposed pin ran on macOS in this preparation | Exact-pin vendor install/smoke on an admitted macOS worker, with fencing for authenticated portions |
| `native-clients-original-capture-history` | Missing originals from the earlier normalized-only attempt | Preserve the historical gap; use fresh separate observations, never reconstruct originals |

F2 records actual native readiness commands plus the workload-invocation gap.
Installation and help output do not qualify that workload. A6 remains pending.

## Multi-angle delta

[multi-angle-draft.json](../../evidence/artifacts/final-native-clients-prep-20261016/multi-angle-draft.json)
carries the existing six-angle weights and comparison-candidate values with
supporting path:line sources. No scores are recomputed. A1 gains bounded
install/readiness evidence; A2 retains engineering-quality limitations; A3
distinguishes community scale from consensus; A4 retains the limits of download
and opt-in traffic proxies; A5 retains benchmark model/version confounds;
A6 remains pending. Every disputed dimension is named for the co-op's two-family
reads. No single angle decides.

The actual `lane_packets.py` invocation is retained at
`native/index.json:1224`, rc 0 at line 1249. Its output
`native/lane-packets.stdout.txt:1` reports 20 generated foundation packets.
The full native-client packet remains private by the name
`foundation__native-clients.json`; only this layer is prepared. This is a
delta over the existing winner and carried-candidate records, not a new survey.

The last retained sweep covering native-clients remains
`landscape-sweep-20260929`; the newer retained `landscape-sweep-20261009-pine`
return covers backtesting-engine. The earlier missing GPT fit vote for Pi was
not a merits refutation. Its later retained GPT refutation, with Claude dissent,
is substantive disposition under the existing all-not-refuted rule, not positive
two-family agreement. The draft names those exact retained vote references.

The Gemini custody question remains explicit: the 2026-09-23 manifest retains a
substantive fit-refutation excerpt but not full vote returns. Later omission
does not settle whether that excerpt meets the protocol. The readers should
resolve that bounded custody question or request retained adjudication at its
cited historical pin. No returned Gemini survival vote or fresh screen is claimed.

The existing overturn condition remains a demonstrated native event/tool/recovery
gap and an executed same-task, same-account supported alternative. The co-op
dispatches the two-family reads. FINAL remains closed until the gate chain and
required qualification evidence are satisfied.

## SOTA sources

- `openai/codex`, `rust-v0.162.1`, peeled commit
  `092d3acd6bec3e3a14bdc7e7a2810ab628ab759d`:
  [native installer](https://github.com/openai/codex/blob/092d3acd6bec3e3a14bdc7e7a2810ab628ab759d/scripts/install/install.sh)
  and [README](https://github.com/openai/codex/blob/092d3acd6bec3e3a14bdc7e7a2810ab628ab759d/README.md).
  Native tag resolution: `native/codex-public-tag.stdout.txt:2`.
- `anthropics/claude-code`, `v2.1.301`, public source commit
  `03b5892ee77de289bcd5dfa39f541525ade74aff`:
  [CHANGELOG](https://github.com/anthropics/claude-code/blob/03b5892ee77de289bcd5dfa39f541525ade74aff/CHANGELOG.md),
  [native installation](https://code.claude.com/docs/en/setup#install-a-specific-version)
  and [release integrity](https://code.claude.com/docs/en/setup#binary-integrity-and-code-signing).
  Native tag resolution: `native/claude-public-tag.stdout.txt:1`.
  The vendor [manifest](https://downloads.claude.ai/claude-code-releases/2.1.301/manifest.json)
  identifies the binary build separately from the documentation tag.
- CPython `v3.13.16):
  [subprocess.run](https://github.com/python/cpython/blob/v3.13.16/Lib/subprocess.py),
  [bytes regex substitution](https://github.com/python/cpython/blob/v3.13.16/Lib/re/__init__.py)
  and [file_digest](https://github.com/python/cpython/blob/v3.13.16/Lib/hashlib.py).
  These upstream primitives implement the recorder/masker. Interpreter outputs
  are `native/python-version.stdout.txt:1` and
  `native/system-python-version.stdout.txt:1`; test fixtures are synthetic.
- OpenAI's [native version smoke](https://developers.openai.com/cookbook/examples/codex/using_goals_in_codex)
  and the repository [layer-resolution protocol](2026-10-11-layer-resolution-protocol.md).
