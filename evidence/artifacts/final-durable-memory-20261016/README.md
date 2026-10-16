# Durable-memory FINAL-wave preparation

**Propose ai-memory v2.6.6 at `04a9e8f576de67e1d2282ee29415d1b0d5b979c8` as the single run pin for qualification. The proposed layer disposition is GAP.** The release executed in an isolated scratch prefix, and two unchanged upstream test suites passed. Full upstream E2E, native-client memory invocation and the nine-candidate comparison remain incomplete. Every six-angle verdict is `INSUFFICIENT`; this record admits no FINAL winner.

The repository base is `caa224140a2d04ba5f3d0ca320c487a75f9c9ea1`. This is the bounded preparation described by the FINAL-wave common brief and the co-op's isolated-scratch rule, cited by name. The canonical catalogs, operational pins, install plan, angle directory and saturation ledger are unchanged. The co-op owns the two-family reads and adjudication.

| Deliverable | Record | Result |
| --- | --- | --- |
| F1: reconcile the run pin | [F1-run-pin.json](F1-run-pin.json) | One proposed qualification pin; every conflicting source is preserved. |
| E2E at that pin | [E2E-attempt.json](E2E-attempt.json) and [outputs](outputs/) | Publisher checksum verified; 189 hook assertions and four relay diagnostic tests passed. Full E2E is a named gap. |
| F2: native invocation | [F2-invoke.json](F2-invoke.json) | The isolated executable answered `--version` and ran `init`, both exit 0. Native-client memory calls remain unmeasured. |
| Six-angle draft | [angles-draft.json](angles-draft.json) | Nine candidates, all `INSUFFICIENT`; no final evidence admission. |
| Bounded comparison inputs | [lane-packet-delta.json](lane-packet-delta.json), [screen-delta.json](screen-delta.json) | One incumbent plus exactly eight carried survivors, preserving the existing role boundaries. |
| Proposed gap disposition | [gaps.json](gaps.json) | Explicit blockers and the next check for each; not an adjudicated terminal state. |
| Ruled metadata correction | [fold-validation.json](fold-validation.json) | Native semantic-validator failure before the correction and pass after it, plus the real corrective read times. |

## Pin reconciliation

All repository citations below are at the base commit above. The linked F1 record includes immutable source URLs and line numbers.

| Source | Value | Meaning |
| --- | --- | --- |
| `catalogs/landscape/final-stack.json:5699` | 2.3.2 | Historical winner in a reopened layer. |
| `docs/decisions/2026-10-15-new-wsl-clean-install-plan.md:133` | ai-memory, eight survivors | The layer row contains no version. |
| Same decision, `:684` | 2.6.6 live | The memory architecture narrative. Hindsight is recorded there as the research-memory alternate. |
| `adoption/new-wsl-profile.json:3004` | 2.5.2 | The install-plan row. |
| `catalogs/landscape/final-stack.json:10396` and `adoption/pins-linux-x86_64.json:156` | 2.4.1 | Derived run pin and its Linux operational source. |
| `adoption/pins-macos-arm64.json:154` | 2.3.2 | Separate macOS operational pin. |
| `evidence/artifacts/w6-layer-verdict-20261011/primary-sources.json:702-703` | 2.6.0 / `89bd8ded3c1ab8b769cf99417d038ed0364403c8` | Last committed W6 source record; its class is source review. |
| `docs/memory-landscape-maintenance.md:125,134` | 2.6.3 | Committed host history says this version ran from 2026-10-10T22:09Z; it is distinct from the later executable probe. |
| [Retained read-only version probe](outputs/host-version-readonly.txt) | 2.6.6 | Existing executable's answer only; active daemon, hook and client ownership were not probed. |

The proposed 2.6.6 pin matches the plan's stated deployed 2.x boundary and now has a fresh source screen, a verified release archive and bounded same-pin execution. Deployment does not establish merit. The separate [screen PR #1193](https://github.com/native-agent-stack/native-agent-stack/pull/1193), at `75777efa265dde1154a5524dbe69cb5dbf6eb7df`, reviewed ai-memory 3.0.0 as source only: [durable-memory.anthropic.json:10-11](https://github.com/native-agent-stack/native-agent-stack/blob/75777efa265dde1154a5524dbe69cb5dbf6eb7df/evidence/artifacts/harness-screens-20261015/durable-memory.anthropic.json#L10) binds that tag to `dbe928e3b64414c619435df887ed344ff83887a5`. Neither its screen nor the present 2.6.6 checks establishes which version should win a migration or quality comparison. `NEWER-AI-MEMORY` preserves that changed-evidence question.

The v2.6.6 annotated tag resolves through `bc79858954d4636dc0d70d960a89249515c88381` to the proposed commit. The source's `Cargo.toml:38` reports 2.6.6, and the separately downloaded release reports the same version. The archive's SHA-256 matches the publisher's sidecar. F1 records the public endpoints and digest; no private input is fingerprinted.

## What actually ran

The upstream [installation cookbook](https://github.com/akitaonrails/ai-memory/blob/04a9e8f576de67e1d2282ee29415d1b0d5b979c8/docs/install.md#L1801) describes the GitHub release archive, checksum verification and extraction. This pass fetched that publisher archive directly, verified its sidecar and extracted it into `<SCRATCH>/prefix`. `<SCRATCH>` is a marked placeholder for the isolated scratch root; exact commands are retained privately. This is a prefix install of the release binary. Sources were exported read-only from the same pinned mirror into the scratch. No host-wide tool, client configuration or service was installed or changed.

Every recorded command, exit code, start time, elapsed time and published output digest is in [E2E-attempt.json](E2E-attempt.json). Each of its 20 captures is labelled `masked_native_capture`: [mask_capture.py](mask_capture.py) replaces only the exact scratch-root byte string with `<SCRATCH>`. All other bytes, including ANSI sequences, carriage returns and empty output, are preserved. [The masking tests](../../../tests/test_final_memory_mask.py) exercise binary preservation, empty output, invalid prefixes and CLI reproduction. Raw native captures and exact command journals remain private and are cited by name only. Published SHA-256 values bind only the published derivatives. Generated configuration and test data are not opened, hashed or published.

The first unpublished capture pass is withdrawn: it used text normalization and a recorder-generated message for a missing executable. Every execution receipt here was rebuilt from a second native capture. In particular, `/usr/bin/env` itself now produces the captured missing-Cargo error. See [integrity-audit.md](integrity-audit.md) for the claim-by-claim review.

| Command / upstream entrypoint | Observed result | Limit |
| --- | --- | --- |
| Publisher archive and `.sha256` download; `sha256sum -c`; prefix extraction | All exit 0 | Qualifies archive integrity and installation only. |
| `sh tests/hooks/test_lib.sh` | 189 passed, 0 failed; exit 0 (`outputs/upstream-hook-tests.txt:187`) | Upstream isolated shell fixtures. |
| `python3 -m unittest discover -s tests/e2e -p 'test_*.py'` | Four tests passed; exit 0 (`outputs/upstream-relay-tests.txt:3,5`) | Relay diagnostic unit tests, not the actual relay E2E. |
| `/usr/bin/env cargo t --locked` | Exit 127 (`outputs/upstream-cargo-tests.txt:1`) | Cargo is unavailable; no Rust tests ran. |
| `python3 tests/e2e/external_relay_smoke.py ...` | Exit 2 during argument validation (`outputs/upstream-external-relay-e2e.txt:5`) | The release prefix has no `ai-memory-relay` executable. No E2E server started. |
| `tests/e2e/handoff_smoke.sh` | Not run | Its pinned source requires two Gemini calls and `GEMINI_API_KEY`. |
| Isolated `ai-memory --version` | `ai-memory 2.6.6`; exit 0 (`outputs/native-version.txt:1`) | Version witness. |
| Existing-host `ai-memory --version` | `ai-memory 2.6.6`; exit 0 (`outputs/host-version-readonly.txt:1`) | F1 probe only, not isolated-install or E2E evidence. |
| Isolated `ai-memory --data-dir <SCRATCH>/memory-raw init` | Exit 0 (`outputs/native-init.txt:7`); native `stat` reports four directories (`outputs/native-init-layout.txt:1-4`) | Initialization only. The generated auth-bearing config was not opened, hashed or published. |

The two version rows are separate native commands with separate raw captures. The scratch command runs `<SCRATCH>/prefix/ai-memory --version` at 05:39:08Z; the host probe runs `ai-memory --version` at 05:40:08Z. They report the same version, so identical output bytes are expected. Their exact start times and argv remain in the command journal; the co-op's private reproduction check confirmed both distinct captures.

The upstream provenance is explicit: [hook smoke instructions](https://github.com/akitaonrails/ai-memory/blob/04a9e8f576de67e1d2282ee29415d1b0d5b979c8/tests/hooks/test_lib.sh#L1), [diagnostic tests](https://github.com/akitaonrails/ai-memory/blob/04a9e8f576de67e1d2282ee29415d1b0d5b979c8/tests/e2e/test_external_relay_smoke.py#L1), [Rust test aliases](https://github.com/akitaonrails/ai-memory/blob/04a9e8f576de67e1d2282ee29415d1b0d5b979c8/.cargo/config.toml#L1), [relay binary validation](https://github.com/akitaonrails/ai-memory/blob/04a9e8f576de67e1d2282ee29415d1b0d5b979c8/tests/e2e/external_relay_smoke.py#L202), [companion build command](https://github.com/akitaonrails/ai-memory/blob/04a9e8f576de67e1d2282ee29415d1b0d5b979c8/.github/workflows/ci.yml#L98), [keyed handoff smoke](https://github.com/akitaonrails/ai-memory/blob/04a9e8f576de67e1d2282ee29415d1b0d5b979c8/tests/e2e/handoff_smoke.sh#L6), and [native initialization](https://github.com/akitaonrails/ai-memory/blob/04a9e8f576de67e1d2282ee29415d1b0d5b979c8/crates/ai-memory-cli/src/commands/init.rs#L60).

All newly installed artifacts and state remain confined to the scratch. Child commands receive scratch-local temporary/config/data/cache paths and no API credentials. Upstream tests use synthetic fixture tokens. No model was invoked, no live service was contacted, and no native Codex or Claude configuration was activated. Linux execution cannot qualify macOS or an upgrade of an existing memory store.

## The nine-candidate delta

The resolution inputs are the 09-22 verdict wave, covering 09-23/26/29 sweeps, retained returns, and the W6 resolution/comparison record. The W6 record also accounts for the later scoped completion and missing-vote history. A missing vote or omission is not a merit decision.

The packet delta was prepared with `lane_packets.py` against the 09-29 and 09-26 manifests. Those original generator invocations have no retained native capture or return-code witness, so their return codes are null and they are not execution receipts. The source-derived 09-29 packet contains the incumbent and five carried survivors; the earlier packet restores Claude Code, LangMem and Total Agent Memory. The published delta retains only these nine named inputs, with packet keys, old comparison pins, proposed source pins and fixed role checks. No general discovery or new model read ran.

| Candidate | Source boundary used here | Remaining disposition |
| --- | --- | --- |
| ai-memory | Fresh 2.6.6 source screen and isolated execution | Full E2E, native-client invocation, recovery and matched quality/cost gaps. |
| Claude Code native memory | Reuse 2.1.301 screen | Preserve `native_file_session_memory` as a dependency/control. Its whole-layer cross-client failure does not reject that narrower role. |
| LangMem | Reuse `48e3c11f5bb527282c7d5339c6a87a0b35abccfc` | Preserve `memory_management_primitives` as a dependency. A persistent backing store and role-specific lifecycle qualification remain open. |
| MemPalace | Reuse 3.11.0 screen | Deletion, recovery and platform source gaps. |
| agentmemory | Reuse 0.9.30 screen | Recovery, platform and headless source gaps. |
| tigerless-labs/agent-memory | Reuse `c395acc4708c545c4b5395f8a2cb1e3a3ababd14` | Platform source gaps. |
| Total Agent Memory | Reuse 14.9.0 screen | Recovery source gap. |
| Hindsight | Reuse 1.0.0 screen; fresh PostgreSQL recovery/dependency read | The selected route now passes the source screen. Actual recovery, native capture and matched comparison remain unrun. |
| Deja-vu | Reuse 0.22.1 coding-family screen | Source pass only; all comparative dimensions remain open. The separate research-family capture UNKNOWN is not promoted. |

The ai-memory pin differs from #1193, so its source facts were read fresh. The eight survivor pins match that screen head; their established facts are reused. Hindsight's previously UNKNOWN recovery path was read fresh. W6 source pins and roles are retained as the prior comparison boundary. The new source proposals do not amend the frozen comparison: a two-family adjudication must bind any subsequent run to the chosen versions, fixed cases and common supported model panel.

## Hindsight against ai-memory

The draft adjudication is **insufficient evidence to select a shared-memory winner**. Both remain explicit candidates; the incumbent receives no preference for already being deployed.

| Disputed dimension | ai-memory 2.6.6 | Hindsight 1.0.0 | Decision-changing check |
| --- | --- | --- | --- |
| Capture and handoffs | The source documents cross-Claude/Codex typed handoffs and zero-LLM capture (`README.md:26,59`). | The reused source screen documents native coding-agent/MCP routes (`README.md:243`). | Run identical fictional outcomes through both native-client capture paths, with one memory owner per isolated profile. |
| Recovery | SQLite/wiki online backup and guarded restore are documented (`docs/lifecycle-ops.md:20-25`). This pass initialized only an empty layout. | `hindsight-admin` documents a consistent PostgreSQL snapshot and destructive target-schema restore (`hindsight-docs/docs/developer/admin-cli.md:190-271`). | Recover the same scoped fictional history into clean targets; check deletion, history, provenance and client rebinding. |
| Backend binding | One publisher native release was verified and executed. | `hindsight-api==1.0.0` binds its slim package; `uv.lock:3443-3451` locks `pg0-embedded==0.15.2`, including Linux x86_64 and macOS arm64 wheels. No backend was installed here. | Execute the upstream backend tests at the declared dependency pin inside scratch. |
| Recall, abstention and useful learning | No matched comparative measurement at this run pin. | The README links LongMemEval and a paper, and asserts external replication (`README.md:5,44-50`). These remain vendor-reported statements here. | Compare the fixed role-specific cases, source-grounded answers, learned-write quality and complete usage under the same model panel. |
| Operational cost and context | CLI startup and fixture tests do not measure session cost. | No runtime or session-cost run in this preparation. | Measure complete capture/retrieval/maintenance and provider consumption in matched windows. |

The recovery finding is new source evidence, not a runtime success: [admin entrypoint and database boundary](https://github.com/vectorize-io/hindsight/blob/39c65ffe2f140d0c84cee58566cad8900c5b9908/hindsight-docs/docs/developer/admin-cli.md#L7), [backup contents and consistency](https://github.com/vectorize-io/hindsight/blob/39c65ffe2f140d0c84cee58566cad8900c5b9908/hindsight-docs/docs/developer/admin-cli.md#L220), [restore semantics](https://github.com/vectorize-io/hindsight/blob/39c65ffe2f140d0c84cee58566cad8900c5b9908/hindsight-docs/docs/developer/admin-cli.md#L236), [package binding](https://github.com/vectorize-io/hindsight/blob/39c65ffe2f140d0c84cee58566cad8900c5b9908/hindsight-api/pyproject.toml#L7), [pg0 lock](https://github.com/vectorize-io/hindsight/blob/39c65ffe2f140d0c84cee58566cad8900c5b9908/uv.lock#L3443), and [upstream coverage test](https://github.com/vectorize-io/hindsight/blob/39c65ffe2f140d0c84cee58566cad8900c5b9908/hindsight-api-slim/tests/test_admin_backup_restore.py#L249).

## Six-angle boundary and validation

The weights now use the repository defaults from `scripts/angle_records.py:22` at the base commit: A1 0.20, A2 0.20, A3 0.15, A4 0.15, A5 0.20 and A6 0.10. Their native statement capture precedes the actual corrective review of the retained evidence. Per-cell `read_at` values come from that readback, after the cited execution captures; they do not pretend to be the original upstream-acquisition times. No comparison was scored. Every candidate remains `INSUFFICIENT` with derived `provisional: false`; the validator reserves that flag for a converged result lacking comparative A6. Operator trial metadata is omitted together rather than asserting a private permission decision. No FINAL winner follows from the record. A licence remains a compliance note.

The earlier JSON-schema pass did not establish the declared `angle-convergence/2` semantic contract. The [captured validator run](fold-validation.json) now records the failure before correction and a pass after correction using `angle_records.validate_record` with source resolution; all nine results re-derive as `INSUFFICIENT`. Its four new masked captures are repository validation/review evidence, separate from the original 20 execution captures. The published-evaluation flag records availability of the vendor-linked work, while the unreviewed methods and comparison limits remain A5 gaps. These checks do not fill the runtime or multi-angle gaps. The CC FULL record is `MICRO-full-ea48abdd.md`, cited by name.
