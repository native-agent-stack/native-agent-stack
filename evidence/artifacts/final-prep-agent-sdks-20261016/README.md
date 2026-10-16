# FINAL-wave preparation: foundation / agent-sdks

This prepares one layer for the co-op's two-family review. **It admits no FINAL
layer, selects no new SDK or model, and changes no catalog.** At reviewed main
`caa224140a2d04ba5f3d0ca320c487a75f9c9ea1`, the recorded winner is Codex SDK/CLI
and the layer is reopened, with two cumulative survivors:
`agentproto/ts` and `github/copilot-sdk`.

## F1: one reconciled run pin, with all drift retained

The proposal preserves the existing Linux F1 run version and resolves its
official release source: **Codex 0.160.0 at
`a956835d020762cb2b570053af06f643a11c0ecc`** (`rust-v0.160.0`).
This is an evidence pin for the assigned run, not a claim that 0.160.0 is the
latest release or a request to downgrade the installed host.

[pin-reconciliation.json](pin-reconciliation.json) cites the exact current-main
file and line for every source, plus its JSON pointer where applicable:

| Source | Observation | Disposition |
| --- | --- | --- |
| Catalog verdict and final-stack winner | 0.155.1 | Historical winner; not silently changed. |
| Final-stack run and Linux adoption pin | 0.160.0 | Proposed run to qualify at its exact release commit. |
| macOS run conflict | 0.155.1 | Separate platform drift, not qualified by a Linux run. |
| Clean-install plan | No pin on native installer; observed 0.162.1 | Reconciliation gap; observed host version is not adoption authority. |
| Read-only host `codex --version` | 0.162.1 | Version observation only; no host config or credentials accessed. |
| Original native worker receipt | Python `openai-codex` 0.154.0 with native CLI 0.155.1 | Different historical wrapper/version; does not qualify the new TypeScript source. |
| Later committed SDK worker B3 review candidate | Python SDK and bundled CLI 0.160.0, source `a956835d` | Shares the proposed native source; its historical Python integration is distinct from this fresh upstream TypeScript test package. |
| Packet generated from the latest covering sweep manifest | 0.157.1 | Historical packet source, not current run authority. |

The earlier coordination `f1-codex-0.160.0` receipt also names this release.
Its bytes are not registered at this base; it is cited by name only, without
exporting its digest or private routing/configuration details. Fresh isolated
evidence here is independently reproducible.

## E2E: the vendor's full SDK test package

[runtime-receipt.json](runtime-receipt.json) records the actual commands, exit
codes, times and hashes of the published output projections. The isolated path
installs official `@openai/codex@0.160.0`, vendor-pinned `pnpm@10.34.5`, then the
exact source checkout's dependencies with `pnpm install --frozen-lockfile`.
The source SDK package is `0.0.0-dev` in that release tree; this receipt does
not invent a published npm SDK version or equate the historical Python wrapper
with the TypeScript SDK.

The complete upstream command is:

```sh
pnpm -r --filter ./sdk/typescript run test
```

That selects the vendor SDK package exactly as upstream CI does; it does not
filter any tests inside the package. All five suites and all 48 tests pass,
including exec, abort, streamed run, run/resume and MCP conformance. The vendor
tests spawn the real release CLI through its supported `CODEX_EXEC_PATH`
override and use their own loopback response fixtures. Fake model responses
are **synthetic**; subprocess/protocol behavior is **local integration**.
These are not real model-quality results, paid-provider acceptance or comparative
A6 evidence.

All test tools run with a closed environment, scratch HOME/CODEX_HOME and
scratch caches. No credential store, original client configuration, stage.env,
key, broker, gateway data or account surface is read. There is no host-wide
installation, service enablement or new default. Vendor code and lockfiles are
unchanged. The CLI release binary substitutes for CI's Bazel build at the same
source commit; that packaging difference is explicit.

The addendum-26 scratch-only boundary is also satisfied: all tools, npm/pnpm
dependencies, caches and test HOME/CODEX_HOME directories are confined to the
owned `/var/tmp` prefixes, including preserved failed attempts. Existing host
Node/npm executables are linked read-only into scratch. No user/global tool
path, system package or systemd unit was installed or modified. Scratch remains
only as the retained isolated test environment, not a new WSL host installation.

Two failed local npm-path bootstrap attempts and one recorder-overlap/missing
scratch-home attempt remain intact outside this checkout. The latter's full
vendor tests passed, but its malformed recorder sequence is not used as a
qualification receipt. The final run repeats the install and entire test target
through one strictly sequential pipeline; no duplicate or failed step is
suppressed. No private attempt hash or original raw diagnostics are exported.

## F2: actual native invocation, with an adoption-window gap

[invoke.json](invoke.json) binds an actual Codex 0.160.0 app-server process to
the vendor's stdio `initialize` request contract. It records the command, exit
code, measured start/end and hash of the published projected response. No
thread, turn, account, model-list or model-inference request is sent. The owned
process terminates afterward.

This proves a **local native protocol invocation**, not an adoption-now worker
run. The recorded layer requirement also includes supported structured events,
custom tools/session control and full harness layers. Skills, MCP, hooks,
memory, token efficiency, telemetry, role isolation, live cancellation/billing
cessation and recovery have not all been qualified together at this pin.
The production/adoption-window F2 requirement therefore remains a named GAP;
installation, a version command and this handshake cannot close it.

## Delta and six-angle record draft

[resolution.json](resolution.json) consumes the current catalog verdict and
wave, every covering sweep, retained returns and candidate source records.
September 29 is the latest completed covering sweep at this base. Both carried
survivors remain unresolved; earlier omission or a missing return never clears
them. No newer completed-but-unappended sweep was supplied or referenced by
these committed inputs; a newly retained one supersedes this draft before
dispatch. Existing alternatives are not resurveyed.

The native packet builder generated the source packet:

```sh
python3 tools/sota-convergence/lane_packets.py --root . \
  --out /var/tmp/ns2604-g5-agent-sdks-packets --catalog foundation \
  --manifest catalogs/sota-convergence/manifest-20260929.json \
  --checked-at 2026-10-16 --registered-receipts --manifest-newcomers
```

[lane-packet-projection.json](lane-packet-projection.json) retains only the
assigned winner and two survivors. Generating the native packets does not
dispatch a research/model lane. No self-dispatched model read occurred.

[multi-angle-draft.json](multi-angle-draft.json) reuses v2's fixed weights,
without calculating a winner or editing the registered angle file. Every
disputed dimension is explicit for the co-op's two-family adjudication:

| Angle | Retained evidence | Remaining dispute |
| --- | --- | --- |
| A1 capability at pin | Fixed upstream source and fresh full SDK tests for Codex; pinned survivor README excerpts. | Full layer screen and required application gap; no live survivor qualification. |
| A2 engineering quality | Bounded exact-commit public CI outcomes. | Release workflow versus SDK tests; failures/skips do not establish total quality. |
| A3 community consensus | Public project stars/forks only. | Popularity is not independent consensus for this role. |
| A4 net usage | Public registry download requests for SDK packages. | Cross-version requests are not unique users, provider traffic or net native usage. |
| A5 published evaluation | No matched evaluation verified at these exact pins. | Unknown is not none; no weight transfer or absence claim. |
| A6 our measured comparison | Historical workers comparison unresolved/publication-ineligible; new local vendor fixture run retained separately. | No new matched comparison; mock tests and handshake are not comparative A6. |

The committed angle record currently covers Deep Agents and Strands rather
than this winner-plus-carried-survivor set. Its bytes remain unchanged; the
draft names that coverage gap instead of claiming its scores settled this layer.

Public exact-commit CI snapshots add a concrete dispute: Codex release run
36897822835 succeeds; agentproto CI run 36517458794 succeeds while sampled
agent-command workflows are skipped; Copilot SDK build/test run 36545271671
and CodeQL run 36545270673 fail. These are bounded CI observations, not a
matched runtime failure or an automatic candidate rejection.

## Named gaps and next action

1. Reconcile the 0.155.1 / 0.157.1 / 0.160.0 / 0.162.1 source roles before any
   unified deployment pin change; macOS remains separately unqualified.
2. Establish the concrete structured-event/custom-tool/session-control gap for
   each survivor, then use the existing comparison path. No automatic install
   follows survival or this packet.
3. Complete actual adoption-window F2 through the converged harness, or retire
   the unused role with its reason. No credentialed/provider work occurs here.
4. Fill the A3/A4/A5 evidence gaps and comparative A6 only through the owning
   bounded process; co-op runs both families' reads of disputed dimensions.
5. FINAL admission stays closed through the common brief's gate chain. This PR
   prepares evidence only; it changes no terminal state, pin registry, platform
   status or model route.

The co-op and CC authority records are cited by name only. They and unpublished
read artifacts are not copied or hashed into the public tree. Public committed
source inputs are sealed in [source-seals.json](source-seals.json).

## Sources

- [openai/codex at a956835d](https://github.com/openai/codex/tree/a956835d020762cb2b570053af06f643a11c0ecc),
  `.github/workflows/sdk.yml:126-136`, `sdk/typescript/package.json`,
  `sdk/typescript/tests/testCodex.ts:6-37`, and the stdio fixture at
  `codex-rs/app-server/tests/suite/v2/connection_handling_stdio_tests.rs:72-86`.
- [Official Codex SDK documentation](https://developers.openai.com/codex/sdk):
  maintained TypeScript installation and thread lifecycle guidance, fetched
  during preparation; pinned source remains decisive for this release.
- [agentproto/ts at 08605fbe](https://github.com/agentproto/ts/tree/08605fbe43a5c71e65f9561fd1d2b92abcbe9c4c)
  and [github/copilot-sdk at f5d9685f](https://github.com/github/copilot-sdk/tree/f5d9685f55286061e12763ed15a73c4469609881):
  retained sweep pins and fixed README role excerpts; no survivor code executed.
- CPython 3.13.16 `subprocess`, `json`, `hashlib`, `selectors` and `pathlib`
  interfaces provide the recorder projections/local protocol driver; no new
  runtime dependency or research harness is introduced.
