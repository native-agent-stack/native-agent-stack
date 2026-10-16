# Agent SDKs: native re-capture and unresolved FINAL preparation

This record reconciles `foundation/agent-sdks` at base
`65d66a370d9a5f129662d14c84f2820e940b3a83`. It prepares evidence and changes no
winner, catalog, default, adoption pin, registered angle score or FINAL state.

The proposed evidence run preserves Codex CLI **0.160.0**, source
`a956835d020762cb2b570053af06f643a11c0ecc` (`rust-v0.160.0`).
[pin-reconciliation.json](pin-reconciliation.json) records source-role drift and
exact supporting lines: historical winner0.155.1, historical packet0.157.1,
Linux run0.160.0, macOS0.155.1, committed historical host0.161.0 and plan
observation0.162.1. The historical host capture is cited at
`evidence/artifacts/sdk-runtime-adoption-20261008/observations.json:286-290`;
the distinct SDK surface is cited at
`docs/decisions/2026-10-08-sdk-runtime-worker-adoption.md:164`.
A fresh current-host observation remains a GAP. Python SDK/native historical evidence and this upstream TypeScript SDK
test remain separate integrations. The source SDK package is `0.0.0-dev`;
no published npm SDK version equivalence is claimed.

## Native captures and custody

[runtime-receipt.json](runtime-receipt.json) indexes eleven sequential commands.
Every `output-NN.txt` is the **complete deterministic masked derivative** of its
native stdout/stderr capture. The hash is of the published bytes, including empty
output from successful `git diff --exit-code` checks. No line selection, status
boilerplate, JSON normalization or driver-generated replacement output is used.

The raw capture remains private under the named **agent-sdks replacement
sequential run**: `steps.jsonl`, `logs/001-clone.log` through
`logs/011-source-clean-after.log`. Raw paths are supplied privately to the
co-op. Raw digests stay in the private recorder; they are not exported.
[mask_capture.py](mask_capture.py) checks those private seals and replaces only
the exact scratch-root token with `<SCRATCH_ARM>`. The no-match case preserves
bytes unchanged. Auxiliary captures replace the exact checkout, packet and
check roots with `<REVIEW_CHECKOUT>`, `<PACKET_SCRATCH>`, `<PRIVATE_CHECKS>` and
`<ADDITIONAL_CHECKS_1>` for the scoped fold checks.
Commands carry those marked placeholders; exact commands remain private.
[test_mask_capture.py](test_mask_capture.py) tests preservation with explicitly
synthetic fixtures; fixtures never stand in for native runs.

[bootstrap.sh](bootstrap.sh), [run_native.sh](run_native.sh),
[recorder.py](recorder.py) and [native_invoke.py](native_invoke.py) publish the
actual execution/capture path. The bootstrap closes the environment for the
entire pipeline, including git, using scratch HOME/caches and disabled global
git config. Existing Node/npm are linked/read only; dependencies and native CLI
are installed in isolated scratch. No host installation, service or provider
invocation. A failed initial binary-layout assumption is retained privately as
the replacement run's `attempt1`; the fresh successful sequence does not erase
that failed attempt or reuse its recorder rows.

The installation and SDK tests follow the pinned vendor commands in
`.github/workflows/sdk.yml:127` and `:136`. [claim-sources.json](claim-sources.json)
binds the actual counts to exact native output lines. The full upstream SDK
package target uses real official CLI subprocesses and vendor loopback response
fixtures. Fixture model responses are synthetic; process behavior is local
integration. No model-quality or comparative A6 result follows.

The npm lock capture retains package names, exact versions and registry integrity
metadata. The native binary hash capture can be compared with the existing
public pinned-binary record cited in `claim-sources.json`. This is byte identity
to that prior public binary, not a new release-signing attestation claim.
Full native before/after git diff captures bind the unchanged source/lock claim.

## Native invocation and F2 gap

[invoke.json](invoke.json) is **derived metadata**, indexing `output-10.txt`;
that output contains the native JSON-RPC response bytes. The driver forwards the
line verbatim before parsing/validating it. Its exit code is the driver status;
the owned app-server is terminated afterward. This is a local `initialize`
handshake only. No account, model-list, thread or turn request is made.

Production/adoption-window SDK invocation through the full converged
skills/MCP/hooks/memory/token-efficiency/telemetry/isolation/roles harness remains
a **GAP**. Cancellation, recovery and custom-tool use are not jointly qualified.
This local handshake cannot close the production F2 requirement.

## Delta and six angles

[resolution.json](resolution.json) retains all completed covering sweeps and both
carried survivors, `agentproto/ts` and `github/copilot-sdk`. Their reviewed source
pins are cited directly from committed sweep records. The native packet's null
survivor pins are left intact; they are unknown packet fields, not alternative
pins. No survivor is installed or adjudicated by this preparation.

[multi-angle-draft.json](multi-angle-draft.json) preserves the existing v2
weights with exact source-line citations. Every angle stays unknown;
no numeric score or candidate selection is computed. Survivor A1 cites its own
source review and never the Codex runtime receipt. SDK capability is separate
from full-harness qualification.

Uncaptured CI/community/registry summaries and the unsupported official-docs
fetch claim are dropped. They supply no engineering-quality, consensus or usage
conclusions. Missing evidence is a gap, not a disagreement between angles:
`disputed` is false unless opposing angle conclusions are actually retained.
No such disagreement is established here. Candidate A1 notes name their own
supported source/execution evidence. A2-A5 notes are absent where evidence is
unverified; survivor A6 notes are absent. Codex A6 explicitly classifies its
local fixture run as A1, citing the committed angle-policy line. Evaluation
uncertainty cites the existing policy that unknown is not none.

## Sources and reproduction

- [openai/codex at a956835d](https://github.com/openai/codex/tree/a956835d020762cb2b570053af06f643a11c0ecc):
  `.github/workflows/sdk.yml:127,136`, `sdk/typescript/tests/testCodex.ts:7,24`,
  `sdk/typescript/README.md:21-22,31,100,104-105`, and
  `codex-rs/app-server/tests/suite/v2/connection_handling_stdio_tests.rs:72-86`.
- [agentproto/ts at 08605fbe](https://github.com/agentproto/ts/tree/08605fbe43a5c71e65f9561fd1d2b92abcbe9c4c)
  and [github/copilot-sdk at f5d9685f](https://github.com/github/copilot-sdk/tree/f5d9685f55286061e12763ed15a73c4469609881):
  carried source-review pins and README excerpts only, no new runtime claims.
- CPython3.13 standard-library `subprocess.run/Popen`, `bytes.replace`,
  `pathlib`, `hashlib`, `selectors`, `json` and `unittest`: recorder, deterministic
  masking and offline integrity checks; no new dependency or model harness.

The co-op's **agent-sdks masked reproduction check passed**: all 17 checked
files were byte-identical (11 native outputs, four auxiliary outputs and their
two receipt indices), with all recorded output hashes, command/rc rows,
44 registrations and both test suites verified. The `pending` fields in the
receipt indices retain their precheck state; [custody-record.json](custody-record.json)
separately records this later result and the checked head. New fold captures
require their own co-op reproduction PASS at the fold head before push.
Raw captures remain private, named only.

`build_record.py` takes `--run-root <SCRATCH_ARM>`,
`--primary-root <PRIMARY_SOURCE_SCRATCH>` and `--packet-file <PACKET_FILE>`;
private source locations are supplied at invocation rather than published as
constants. The fold extends the masker with a testable auxiliary masking
function and additional check roots. Eleven native outputs remain unchanged;
the extended masker and new check derivatives undergo private re-verification.

Native `lane_packets.py` generation, offline tests and gate checks are captured by
[record_aux.py](record_aux.py), with full masked output and return code in
[check-receipts.json](check-receipts.json). Derived indices are labelled as such;
they are not native output. A missing capture remains a named GAP.

[test_recording.py](test_recording.py) tests full-byte/return-code recording,
sequential rows, invalid cwd/name rejection, missing-command failure,
non-overwrite behavior and auxiliary masking, using labelled synthetic fixtures.
The recorder's usage and failure diagnostic now name the committed filename;
the original executed script remains private. The new ledger-handle test fails
against the original recorder and passes with an explicit context manager for
the prior-ledger read. The original-script baseline has two expected regression
failures (rc1); it is retained as `fold-regression-before.txt`, not relabelled
as a passing check. The initial 20-test capture retains its ResourceWarning;
the final 21-test capture passes after the handle correction. Native component
output bytes remain unchanged. Gate outputs are indexed by check name in `check-receipts.json`;
the PR body cites only gate results with retained native captures.
