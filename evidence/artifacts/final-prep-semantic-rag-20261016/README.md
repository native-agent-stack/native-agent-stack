# Semantic-rag FINAL-wave preparation — 2026-10-16

This packet prepares **foundation/semantic-rag** at repository base
`caa224140a2d04ba5f3d0ca320c487a75f9c9ea1`. It admits no FINAL state and changes
no deployed component, model route or default. The existing layer is reopened,
its angle record is missing, and its terminal state is null
([final-stack.json:7824](https://github.com/native-agent-stack/native-agent-stack/blob/caa224140a2d04ba5f3d0ca320c487a75f9c9ea1/catalogs/landscape/final-stack.json#L7824)).
The [clean-install plan:146](https://github.com/native-agent-stack/native-agent-stack/blob/caa224140a2d04ba5f3d0ca320c487a75f9c9ea1/docs/decisions/2026-10-15-new-wsl-clean-install-plan.md#L146)
names the same three winners and five carried survivors.

The concrete results are a reconciled **proposed** run identity for each winner,
2,517 passing upstream SocratiCode unit tests, six passing upstream integration
tests with synthetic vectors against isolated Qdrant, native version/help
invocations, a read-only vLLM distribution version observation, and a generated
199-package hash-bearing vLLM lock. Full semantic-role E2E and invocation remain
named gaps. C2 model arms have not yet been measured.

## F1 — one proposed run identity per winner

| Winner | Proposed run identity | Existing drift | Evidence and boundary |
| --- | --- | --- | --- |
| SocratiCode | v1.16.0 / `3d3a4a4d427cb0f29de4f5dd1360da52896f62df` | Verdict/macOS 1.14.0; Linux run/recipe 1.15.0; frozen W6 arm `2218f251…` | Existing 1.16.0 qualification receipt plus reproduced upstream unit suite. Runtime/plugin installation and the frozen comparison are distinct identities. |
| Qdrant | v1.19.1 / `6ab21cac18ebb6f4ae29102c7f8f5cc11affd5de` | Generated run row has no commit and lists only macOS provenance | Retain the existing run/frozen arm; official Linux asset digest, CLI and two upstream integration files checked. No full Qdrant recovery/cluster E2E or model-backed retrieval was run. |
| vLLM | v0.31.0 / `db9527a46873454610df6dbedf79a36d6bf1a7f6` | Verdict 0.25.0; run/manifest/recipe 0.30.0; installed metadata 0.31.0 | Recorded replacement target and metadata agree. New dependency resolution is locked, but not installed or serving-qualified. |

[pin-reconciliation.json](pin-reconciliation.json) records every required source
class: final-stack winner and run, clean-install plan, source manifest, adoption
pins where present, recipe, named version-bearing committed receipt, frozen W6
arm and current observation. Citations bind the current base and exact lines.
It distinguishes the latest named component-specific qualification from broad
receipts that mention many components without supplying this component's pin.

The existing recipe is at **line 116** in this base; earlier relays named line
118. The proposed vLLM recipe has one version, 0.31.0, and consumes the retained
lock. The live recipe and generated operational pins are not advanced from an
installation/version observation. That boundary follows
[the recorded replacement decision:19-21](https://github.com/native-agent-stack/native-agent-stack/blob/caa224140a2d04ba5f3d0ca320c487a75f9c9ea1/docs/decisions/2026-10-06-one-host-tool-default.md#L19-L21).

The carried embedder is `nvidia/Nemotron-3-Embed-1B-BF16` at full revision
`c0c9fea93ea424587517f2c59e20db9f1d6bf615`
([foundation.json:1750](https://github.com/native-agent-stack/native-agent-stack/blob/caa224140a2d04ba5f3d0ca320c487a75f9c9ea1/catalogs/landscape/foundation.json#L1750);
[primary model card at that revision](https://huggingface.co/nvidia/Nemotron-3-Embed-1B-BF16/blob/c0c9fea93ea424587517f2c59e20db9f1d6bf615/README.md)).
This is historical identity, not a new model selection. The card was read
without authorization headers; no weights were downloaded.

## Dependency reproducibility

[vllm-0.31.0.requirements.lock](vllm-0.31.0.requirements.lock) pins 199 packages
and distribution hashes. Its SHA-256 is
`cc7d568fd9368d0ba1090c4ff729daa7d3c96d23970c0d5b7c3a74faf074c05f`.
The resolver was uv 0.12.22, source
`astral-sh/uv@70fe1196a546e49148a73b1c592b2f74c33af80e`.
The input was exactly `vllm==0.31.0`, Python 3.13 on the current Linux x86_64
platform, public PyPI, no source builds, and
`--exclude-newer 2026-10-16T05:15:55Z`. The timestamp is the recorded resolver
cutoff, **not a qualification date**. No claim of reproducing an earlier
unlocked environment is made.

The proposed later scratch installation is:

```sh
uv venv --python 3.13 <isolated-scratch>/vllm-0.31.0
uv pip sync --python <isolated-scratch>/vllm-0.31.0/bin/python \
  --require-hashes vllm-0.31.0.requirements.lock
```

This uses uv's [compiled-requirements/sync contract](https://github.com/astral-sh/uv/blob/70fe1196a546e49148a73b1c592b2f74c33af80e/docs/pip/compile.md#L113-L127).
It is a proposal for the next qualification, not an executed install.
The lock is included in the ordinary OSV inventory; it is not exempted from
dependency checks.

MEMRAG-INSTALL-STATUS-20261016.md reports **36 changed transitive versions across
two 199-package installations**, despite matching core versions. This lane
retains that reported limitation without copying or hashing private freezes.
The newly generated lock contains vLLM 0.31.0, torch 2.13.0, transformers 5.17.0,
flashinfer-python 0.7.0.post1, tokenizers 0.23.3 and openai 3.31.0. Matching a
package count or those examples does not establish equality to either prior
installation.

An earlier generic-platform resolution attempt predates the byte-preserving
recorder. Its original native capture is missing, so it is a named capture gap
and supplies no measured failure claim. The native-platform resolution was
recaptured and succeeded ([native stderr](captures/vllm-resolution.stderr):2).
The lock is not a macOS/other-glibc claim.

SocratiCode used its own unchanged source lock at v1.16.0, SHA-256
`b84a66a59bdb16876f5c628188e4c78e9baa78bc8f906f666d342b5a97e3520c`
([public package-lock.json](https://github.com/giancarloerra/SocratiCode/blob/3d3a4a4d427cb0f29de4f5dd1360da52896f62df/package-lock.json)).
The official Qdrant Linux archive digest
`70a40529e2ebe0a2787d574d3a2e28437cfe94f26f24fa419f6ac57b4ae817c9`
matched its downloaded public bytes.

## E2E preparation and F2 invoke evidence

[native-checks.json](native-checks.json) contains exact in-namespace commands,
exit codes, start/end times and complete native stdout/stderr streams under
[captures](captures/). Each stream is labelled a deterministic masked derivative;
its hash covers the complete published bytes. No excerpt or generated summary
stands in for a run. The raw captures stay private and are cited by basename,
never by their private digest.

[mask_capture.py](mask_capture.py) changes only the explicitly supplied private
scratch root, private home-path and UUID tokens, preserving every other byte.
Its six synthetic controls test identity for
non-private bytes, failure/line preservation, determinism/idempotence and empty
streams in [test_semantic_rag_capture_mask.py](../../../tests/test_semantic_rag_capture_mask.py).
Two additional tests verify every published stream hash and exact native count
line. The UUID case failed before the masking correction; the publication gate
is pinned at base `scripts/validate.py:40`. Fixture point identifiers are masked
without dropping their `Bad Request` failures or result counts.
The scratch-root test also failed before the correction; it preserves the
native status, packet count and descendant path while replacing the root.
For private reproduction, run `python mask_capture.py <PRIVATE_RAW_CAPTURE>
<PUBLISHED_DERIVATIVE> --scratch-root <PRIVATE_SCRATCH_ROOT>` and compare the
complete output with the cited stream. The root is supplied privately and is
never embedded in the published masking script.
Commands use literal `/work` and `/runtime` namespace paths; their private host
mount sources are marked placeholders in the capture record. The co-op checks
private raw-to-derivative reproduction.
[invoke-evidence.json](invoke-evidence.json) separates native command execution
from actual semantic-role invocation.

| Component | Observed model-free result | Full E2E / semantic-role invocation |
| --- | --- | --- |
| SocratiCode 1.16.0 | `npm ci --no-audit --no-fund`: exit 0, 425 packages. `npm run test:unit`: exit 0, 107 files / 2,517 tests. Release-version/build checks exit 0. Two upstream integration files: exit 0, six tests. | GAP: no native-client MCP or model-backed retrieval; integration vectors are synthetic/precomputed/stubbed. |
| Qdrant 1.19.1 | Official binary `--version` and `--help`: exit 0; real scratch storage/upsert/recovery operations exercised by upstream integration tests. | GAP: no full Qdrant-native recovery/cluster suite, no real model/corpus qualification. |
| vLLM 0.31.0 | Existing distribution metadata: exit 0, 0.31.0. Hash-bearing dependency resolution: exit 0. | GAP: native `--version` exited 1 in the no-GPU sandbox during device inference; no new runtime install or model/serving call. |

SocratiCode's [CONTRIBUTING.md:29-36](https://github.com/giancarloerra/SocratiCode/blob/3d3a4a4d427cb0f29de4f5dd1360da52896f62df/CONTRIBUTING.md#L29-L36)
distinguishes model-free unit tests from Docker-dependent integration/E2E;
[CI:39-40](https://github.com/giancarloerra/SocratiCode/blob/3d3a4a4d427cb0f29de4f5dd1360da52896f62df/.github/workflows/ci.yml#L39-L40)
uses the lock-preserving install and unit commands. No upstream code was edited.
Unit tests use mocks/fixtures and do not demonstrate the deployed retrieval
path. The two integration files are selected from the upstream CI's
[no-external-embedding subset:151-187](https://github.com/giancarloerra/SocratiCode/blob/3d3a4a4d427cb0f29de4f5dd1360da52896f62df/.github/workflows/ci.yml#L151-L187).
They run real indexing/recovery/Qdrant operations with synthetic/stub vectors.
[offline-integration.sh](offline-integration.sh) is the exact script executed
inside the isolated namespace. It starts a fresh owned Qdrant, checks readiness,
runs only `partial-upsert-skip.test.ts` and
`interrupted-resume-recovery.test.ts`, then signals and waits for its owned PID.
The server's child exit code was consumed by cleanup and is explicitly missing;
the parent test command's return code and full streams are captured.

The first integration attempt stopped before tests because the isolated Qdrant
could not load CA roots ([native log](captures/qdrant-offline-first.stdout):30).
The retry mounted public CA roots read-only and kept network isolation.
Older preliminary npm setup attempts lack original native captures and are
named gaps rather than reconstructed receipts. Every relied-on unit/install,
version and resolver result was recaptured directly before publication.

Qdrant's [native CLI parser](https://github.com/qdrant/qdrant/blob/6ab21cac18ebb6f4ae29102c7f8f5cc11affd5de/src/main.rs#L70-L76)
supports help/version. The vLLM
[CLI builds command parsers before version handling](https://github.com/vllm-project/vllm/blob/db9527a46873454610df6dbedf79a36d6bf1a7f6/vllm/entrypoints/cli/main.py#L89-L99);
its failed no-GPU probe is a sandbox-bound result, not evidence that the live
server is broken. Metadata confirms installed package identity only.

All new downloads, source checkouts, dependencies and caches stayed in owned
throwaway scratch. Bubblewrap exposed only system runtime directories, the
selected language runtime and the owned scratch, with an empty environment
and no credential/config mounts. Unit tests and binary probes had isolated
network namespaces; package installation used public registry network access.
The pre-existing vLLM prefix was mounted read-only, without GPU devices.
No host install, global package, unit, account action or host/external service
connection occurred. The only server was the owned scratch Qdrant used with
synthetic vectors. Scratch remains solely for review; nothing was enabled in a host
profile. No macOS run or GPU memory qualification is claimed.

## Six-angle delta and disputes

[angle-record-draft.json](angle-record-draft.json) uses the existing
`angle-convergence/2` schema outside the live angle directory. All seven
distinct candidates derive **INSUFFICIENT**. The record retains default weights
stated at 2026-10-16T05:09:57Z before the new angle reads, and discloses prior
history visibility. Model-free checks remain A1; no new comparative A6 is
claimed. A3 consensus and A4 usage were not re-surveyed. Vendor evaluation
claims are retained as bounded sources rather than promoted to a matched
project-workload result.

[packet-selection.json](packet-selection.json) records the actual
`tools/sota-convergence/lane_packets.py` invocation. The supported CLI produces
20 foundation packets; only semantic-rag was read and projected. Its old
candidate join includes the three winner components but misses four carried
survivors. Those four are carried from final-stack and the already frozen W6
arm list, with no new discovery. The excluded older alternatives are outside
this requested delta, not silently retired.

The inherited [W6 comparison](https://github.com/native-agent-stack/native-agent-stack/blob/caa224140a2d04ba5f3d0ca320c487a75f9c9ea1/evidence/artifacts/w6-layer-verdict-20261011/comparisons/semantic-rag.json)
remains immutable: no new metrics, changed role assignments or replaced arm
pins. Its own phase label is not substituted for the current final-stack
terminal state. Three issues specifically require the co-op's two-family read:

- **Ollama split:** the later survivor list carries it, while the
  [2026-10-03 fit re-vote:91](https://github.com/native-agent-stack/native-agent-stack/blob/caa224140a2d04ba5f3d0ca320c487a75f9c9ea1/evidence/artifacts/landscape-sweep-20260926-gpt6-fit-revote-20261003/README.md#L91)
  records a merit refutation at confidence 0.90. Both facts stay visible.
- **SocratiCode pin mismatch:** proposed v1.16.0 differs from frozen
  `2218f251…`. A model-free result at one source pin cannot qualify another
  arm or change the operational run pin by implication.
- **Historical benchmark confounds:** the retained
  [SocratiCode comparison](../gap-wave2-20260923/semantic-rag/socraticode-vs-baselines.json)
  discloses traversal-order baseline ranking, identifier-rich questions,
  partial-index first-run supersession and incomplete ex-ante sealing.
  The old scores cannot become clean current-pin A6 evidence.

The named model-backed prerequisite is **C2 model arms not yet measured**.
Once C2's exact model/runtime inputs, the disposable service runner/GPU
allocation, and reviewed role/pin dispositions exist, the retained upstream
E2E and comparison can proceed in scratch. Nothing here starts or admits that
run. FINAL opening remains a separate gate.

## Verification and publication boundary

The angle draft is checked with the repository's own `validate_record` and
`derive`; source locators, complete published-stream hashes, lock identity, candidate
coverage and public-path constraints are checked before commit.
`python3 scripts/validate.py` must return 0 after registration.
The new lock is included in `.github/osv-scanner-lockfiles.json`.
The published masking rule has focused tests. No production component code or
new file under `scripts/` is introduced.

Private coordination inputs are cited by name only:
final-wave-layer-prep.brief-20261016.md, C2/PLAN.md and
MEMRAG-INSTALL-STATUS-20261016.md. No private path, hostname or digest of private
records is published. The co-op dispatches the GPT and Claude reads; this
packet neither self-reviews nor merges.
