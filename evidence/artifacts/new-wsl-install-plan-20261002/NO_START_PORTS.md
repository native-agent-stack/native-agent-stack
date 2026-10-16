# No-start installation and host port allocation (2026-10-15)

Base: `8053f14e7e0817d2502dff2bb284bfb7e1b0152f`. This corrects the reviewed
installation/startup and fixed-port defects at the existing owner pins. The
layer-resolution protocol was consulted; this is a bounded mechanism correction,
with no candidate selection, landscape comparison or default-owner reopening.

## Behavior

- `install.sh --no-start` installs units and runs `daemon-reload`; it creates no
  enablement links and requests no service start. This includes ai-memory, Ollama,
  Dagu, rootless Docker, the gateway, the worker template and the research timer.
  The foreground OTel, Prometheus, Loki, Grafana and Alertmanager rows also install
  disabled units. MinerU and agentsview retain their native daemon lifecycle;
  MinerU's daemon-dependent configuration is deferred in this mode.
- MinerU's preexisting `server start`/EXIT-trap `server stop` pair is a transient
  start. The target operator reported MinerU 4.0.10 using `~/.mineru/doclib.sock`
  with `tcp.enabled=false` on both distributions; this lane did not reproduce
  that observation. The fixture proves the normal transient start/stop pair and
  proves that no-start skips it, including daemon-dependent model configuration.
- With no-start, Dagu uses `--service no`, then installs its cited user-unit form
  with nonsecret settings when a unit is absent. Existing units are preserved.
  Normal installation retains the vendor's service/bootstrap flow. A coordinator
  port drop-in is placed before the installer runs, so its first start uses the
  selected port. No-start defers native bootstrap; normal installation completes it.
- Docker's rootless setup tool starts and enables the unit internally, so the
  no-start path installs its pinned unit form without executing that tool.
  Rootful Docker/socket/containerd units are masked before package installation
  to prevent package scripts from activating them. Existing running services are
  not stopped by the mask. No-start does not disable previously enabled units.
- Host values select all declared listener ports through `service_ports()` in
  `config/observability_config.py`. The file remains a flat string map compatible
  with the existing host renderer. Memory uses `AI_MEMORY_URL`; the other ports
  use the complete `NS_PORT_*` key set shown in `adoption/hosts/example.json`. The
  WSL host template stays byte-identical to its frozen image-experiment input;
  extending it is deferred to that experiment's owners. Explicit host files, saved
  allocations and no-start require every port key; missing/unknown keys, invalid
  values and duplicate allocations fail before package installation.
- Public source configs carry `@PORT_NAME@` markers. Install stages their expanded
  bytes in a temporary tree. Quoted upstream install/accept commands retain their
  original default-port spellings in the inventory and are expanded in one pass
  before execution. This also handles port swaps without cascading substitutions.
  Acceptance reuses the saved allocation or an explicit `--host-file`.
- The gateway wrapper passes an explicit CLI port. Its template's default
  expansion must match the pinned composition SHA before a moved-port wrapper
  and its corresponding verification digest are derived. The package identity
  remains unchanged. A fixture caught and rejected the earlier assumption that
  the unit's PORT environment alone could override this explicit argument.
- Source checking audits every service row for bypassed activation, verifies
  unit registration, rejects literal service ports in config assets, and checks
  allocation collisions. Inspector and the alert closed-port control now have
  independent allocations; external Ollama guard ports and the worker negative
  control remain explicitly classified exceptions.
  `check_plan.py` inspects the literal list table without executing `install.sh`.
- RTK's four exact-output hook checks set `RTK_SUPPRESS_HOOK_WARNING=1`; the
  missing-hook stderr warning no longer contaminates decisions on a fresh host.

## Pinned sources

- [systemd/systemd v259, man/systemctl.xml:880–927](https://github.com/systemd/systemd/blob/v259/man/systemctl.xml#L880):
  enable creates boot dependencies; starting requires `--now` or start. The
  [mask operation:1129](https://github.com/systemd/systemd/blob/v259/man/systemctl.xml#L1129)
  prevents activation, including package-triggered activation.
- [systemd/systemd v259, man/systemd.unit.xml:2224–2255](https://github.com/systemd/systemd/blob/v259/man/systemd.unit.xml#L2224):
  `[Install]` and `WantedBy` affect enablement links, not a copied unit's runtime.
- [dagucloud/dagu v2.18.2, scripts/installer.sh:113](https://github.com/dagucloud/dagu/blob/v2.18.2/scripts/installer.sh#L113),
  [1666–1697](https://github.com/dagucloud/dagu/blob/v2.18.2/scripts/installer.sh#L1666),
  [2180](https://github.com/dagucloud/dagu/blob/v2.18.2/scripts/installer.sh#L2180):
  `SERVICE_MODE`, unit generation, and the guarded write/start path.
  [internal/cmn/config/loader.go:2266](https://github.com/dagucloud/dagu/blob/v2.18.2/internal/cmn/config/loader.go#L2266)
  binds the coordinator port environment setting.
- [moby/moby 8af9fe3a36bab3e039862a2ab1cef1880c9b4d03, contrib/dockerd-rootless-setuptool.sh:334–390](https://github.com/moby/moby/blob/8af9fe3a36bab3e039862a2ab1cef1880c9b4d03/contrib/dockerd-rootless-setuptool.sh#L334):
  the generated unit and unconditional start/enable behavior after installation.
- [Recipe F8 at 8053f14e7, adoption/platforms/linux-wsl2-new-distro.md:1047](https://github.com/native-agent-stack/native-agent-stack/blob/8053f14e7e0817d2502dff2bb284bfb7e1b0152f/adoption/platforms/linux-wsl2-new-distro.md#L1047)
  and [Listeners and ports, adoption/platforms/linux-wsl2.md:253](https://github.com/native-agent-stack/native-agent-stack/blob/8053f14e7e0817d2502dff2bb284bfb7e1b0152f/adoption/platforms/linux-wsl2.md#L253):
  nonsecret host values and the shared WSL network namespace. This change uses
  the install plan's renderer; the workstation backend renderer is unchanged.
- [rtk-ai/rtk v0.51.0, src/hooks/hook_check.rs:94–116](https://github.com/rtk-ai/rtk/blob/v0.51.0/src/hooks/hook_check.rs#L94),
  [src/core/config.rs:299–307](https://github.com/rtk-ai/rtk/blob/v0.51.0/src/core/config.rs#L299),
  [README.md:485](https://github.com/rtk-ai/rtk/blob/v0.51.0/README.md#L485):
  missing-hook warning and the supported suppression switch.
- Foreground commands use the existing pins and sources in SOURCES.md: OTel
  Contrib v0.162.0 README.md; Loki v3.7.8 `docs/sources/setup/install/local.md:74`;
  Grafana v13.2.3 `docs/sources/setup-grafana/start-restart-grafana.md:107`;
  Alertmanager v0.34.1 `Procfile:1` and `README.md:394–396`.

## Reproduced fixtures and limits

Every test/validator command ran through
`systemd-run --user --scope -p CPUWeight=idle --quiet --`. No installation script,
real installer, or real `systemctl enable/start` ran on the build host. An early
broad legacy test run did invoke `accept.sh` with a disposable HOME and stub curl,
and included the observability suite's synthetic native-collector harness. Those
overlooked harnesses exceeded the requested local fixture-only/no-script boundary;
they were excluded from subsequent local runs and left to GitHub. The final
targeted matrix uses extracted functions, fakes and source checks. Neither the
earlier harnesses nor the current fixtures constitute NativeHorizonNY acceptance.

| Change | Before | After | Evidence class |
| --- | --- | --- | --- |
| Memory no-start and option parsing | Two failures on unchanged 8053f14e7 production sources: observed fake enable/start and missing option | Both pass | synthetic |
| Host ports and collision rejection | Two failures on 8053f14e7: unsupported host-file and absent allocation validation | Both pass | synthetic |
| RTK fresh-host exact-output checks | Both extracted install/accept checks fail with a warning-writing fake RTK | Both pass with the upstream switch | synthetic |
| Dashboard generator markers | Marker-emission test fails with the unchanged 8053f14e7 generator | Passes after its one-line plan-output change | synthetic |
| Moved gateway wrapper | Fixture rejects default CLI port despite a moved unit environment | Wrapper CLI port and derived integrity check both move | synthetic |

Exact commands, exits and counts are retained in
[no-start-test-receipt.json](no-start-test-receipt.json). The regressions are in
`tests/test_install_plan_no_start_ports.py`. The original
default config SHA256s are in `tests/fixtures/install_plan_default_ports.json`.
[dashboard-default-port-hashes.json](dashboard-default-port-hashes.json) records
all six generated files: the generator API's before/after bytes and the plan's
default expansion match exactly. The generator's committed plan-output path now
emits markers; its `dashboards()` output stays unchanged.

NativeHorizonNY acceptance remains separate and unrun by this lane: its owner
runs `install.sh --no-start --only memory-owner` with the intended host file,
then verifies that the unit is disabled and that no new listener appeared.
Fixtures prove command selection and rendering, not package installation,
systemd behavior on that distro, or live listener ownership.

## First review wave: research routing and listener ownership

The research entry and runtime profiles now read `gateway_url()` from this plan's
renderer, using an explicit `NS2604_HOST_FILE` or the saved nonsecret allocation.
GPT Researcher resolves it before its existing `env -i` scrub. The installed
research row also installs the renderer beside the copied helper. Acceptance
propagates its explicit host-file pointer to external helpers and expands the
cited memory, alerting/page-alert, gateway and DeerFlow checks through the same
port allocation. `runtime_profiles.py` retains `GPT_MODEL` at line 43 and every
other line locator; `gpt_researcher.sh:27` also stays fixed.

Native-client research commands also carry `NS2604_HOST_FILE` explicitly through
their shell boundary, because a client's environment policy may discard inherited
variables. With no explicit host file, acceptance uses the installed allocation
snapshot when present. The default endpoint is unchanged when neither exists.

For the Docker dependency addendum, the policy remains a declared dependency
closure: selecting docker-compose or Harbor can install container-engine, and
`--no-start` propagates through that dispatch without activation. The fixture
executes extracted selection/dispatch functions with fake package/service tools;
against 8053f14e7 it observes `enable --now` both with an existing unit and a fresh
one, while the current code installs/reloads without either setup or activation.
`check_plan.py` checks that the flag is exported and not reset by dependency
dispatch. This follows the same systemctl v259 enable/--now distinction above.

The stage-S gate uses `sudo ss -ltnpH`, then requires a visible `users:` process
entry for each selected planned listener before service-health or after-sign-in
programs run. It includes cross-service references, research's gateway, and all
three OmniRoute listeners. The complete default inventory is 15 listeners.
Owned, foreign, absent, auxiliary-port and fail-before-probe cases use fixtures;
this lane did not query live sockets. `check_plan.py --ss-output` supports the
pre-install counterpart: foreign listeners conflict, absent services are allowed.

Sources checked against the installed `ss --version` (iproute2-6.19.0):
[iproute2 v6.19.0 man/man8/ss.8:24,43,162](https://github.com/iproute2/iproute2/blob/v6.19.0/man/man8/ss.8#L162)
documents header suppression, listening sockets and process display;
[misc/ss.c:643–690](https://github.com/iproute2/iproute2/blob/v6.19.0/misc/ss.c#L643)
builds owners from visible `/proc` entries, and
[misc/ss.c:2455](https://github.com/iproute2/iproute2/blob/v6.19.0/misc/ss.c#L2455)
emits `users:`. No visible owner fails closed; it is not treated as a healthy
service merely because another distro answers on the port.

The first-head CI logs exposed two fixtures that still hashed/read raw port
templates: Ollama unit custody (shard 3) and the hcom emitter (shard 4). Their
assertions now inspect the default expansion, retaining the original digest and
endpoint expectations. Shard 0's image experiment hashes the live host template;
that template was restored to its exact `14048b84`/`8053f14e7` bytes, preserving
SHA256 `4395aec846f1d418a55a862cb4db03906d2513d00fa596c190b56641f760f6b0`.
The experiment and its frozen record remain unchanged. Operators complete their own host value file before isolated installation; the
pure default renderer retains the previous bytes. The second-wave strict host
contract below supersedes the first-wave optional-key behavior.

## Second review wave: complete host selection and optional listeners

This fold addresses `GPT-VERDICT-596ab33a6.md` and the co-op's CC addenda as one
review wave. A complete explicit host file supersedes an inherited selector
before staging. The candidate snapshot then governs both rendered assets and
every dispatched command. The active snapshot changes only after all selected
rows succeed; a failing row preserves the prior allocation. Explicit host files,
saved allocations and no-start refuse missing port keys. These requirements
supersede the first wave's partial host-file fallback. Memory's explicit
`AI_MEMORY_URL` participates in validation, so memory 39374 and gateway 29374 are
valid in both client renders. Codex's shell distro identity comes from the host
file's `WSL_DISTRO_NAME`; missing or blank input is refused, with no distro default.

Grafana gRPC is reserved but disabled by its upstream default. Ownership requires
it only when the rendered configuration or an explicit enable selection enables
it. Enabled, moved, absent and foreign-listener fixtures cover that path. Port
9749 belongs to codebase-memory's optional UI, not trace-viewer. A missing native
config can enable this UI when embedded assets exist; the install row now creates
an explicit false native config before exposing the binary. Native bool/integer
types are preserved, and conflicting files or symlinks fail without overwriting.
The older `NS_PORT_TRACE_VIEWER` key remains a compatibility alias, with conflicting
old/new declarations rejected.

Inspector's probe port 16399 and the alert fixture's closed port 21997 are separate
allocations. Inspector is rendered before recipe freezing/hash, retaining its
ephemeral-range, occupied-socket and cleanup guards. The alert's failed-connect
and no-listener checks both move together; neither predicate was removed. Both
ports are excluded from running-listener requirements. Optional/metrics ports
9749, 21302, 21888 and 21889 remain reserved against collisions. Ollama readiness
uses the selected endpoint. Agentsview's actual plan default is 21808: its archive
TOML overrides upstream's 8080 default. A conflicting archive config now fails,
preventing publication of an allocation the retained file would not honor.

Additional pinned sources checked for this fold:

- [Grafana v13.2.3, pkg/setting/setting_grpc.go:113](https://github.com/grafana/grafana/blob/v13.2.3/pkg/setting/setting_grpc.go#L113)
  makes gRPC disabled by default; `pkg/services/grpcserver/service.go` and
  `pkg/registry/backgroundsvcs/adapter/manager.go` implement disabled-service
  suppression. The retained mirror is commit `6193dc03311b631b9727b560d24369e683dc396e`.
- [DeusData/codebase-memory-mcp v0.11.0, src/ui/config.c:124–157](https://github.com/DeusData/codebase-memory-mcp/blob/v0.11.0/src/ui/config.c#L124)
  covers missing-config auto-enablement and native JSON fields/types;
  [src/foundation/platform.c:600–623](https://github.com/DeusData/codebase-memory-mcp/blob/v0.11.0/src/foundation/platform.c#L600)
  resolves `CBM_CACHE_DIR` or the native cache directory. The misleading false
  macro alone is insufficient evidence. `src/main.c:3254–3264` applies CLI UI
  changes after daemon bootstrap, motivating the configuration-first order.
- [kenn-io/agentsview 413a87f7bfbd67b2815b1119ac51abc1efbeeaba, internal/config/config.go:1398,1651,2051](https://github.com/kenn-io/agentsview/blob/413a87f7bfbd67b2815b1119ac51abc1efbeeaba/internal/config/config.go#L2051)
  selects the archive config and its port override; this corrects README's stale
  8080 claim without changing the plan's default bytes.
- [openai/codex rust-v0.161.0, codex-rs/protocol/src/shell_environment.rs:100–102,138–142](https://github.com/openai/codex/blob/rust-v0.161.0/codex-rs/protocol/src/shell_environment.rs#L138)
  starts with an empty inherited map and applies explicit `set` values. The
  [official configuration reference](https://developers.openai.com/codex/config-reference/)
  corroborates `shell_environment_policy.set`.

The original retained `review-port-probes.py` was run unchanged: memory and
disabled-gRPC cases pass, while its staging case rejects the removed
`--persist-ports` API. That case expects a partial host file and early publication,
which conflict with the later complete-host/transaction requirements. The approved
adapter, `tests/pr1180_port_review_probes.py`, retains all three behavioral
assertions using complete fixtures and the staging/commit helpers, and adds two
distro-identity cases. Against unchanged `596ab33a6` it reports four assertion
failures plus the memory-allocation error; all five pass on this fold. See
[review-wave-2-receipt.json](review-wave-2-receipt.json) for exact commands/results.

| Material change | Review classification | Evidence |
| --- | --- | --- |
| No-start activation guards and complete host allocation | Required correction | Synthetic fixtures and source review; target acceptance pending |
| Foreground observability services' user-unit form | **PROPOSAL** | Source-derived unit form and fake registration only; native lifecycle unmeasured |
| Conflicting port config returns `needs_owner` | **Follow-ups** | Synthetic custody/transaction refusal tests |
| Static inspection of the installer's `--list` table | **Follow-ups** | Source checker; avoids executing the installer for structural validation |
| Frozen WSL template extension | **DEFERRED** | Original hash retained; superseding experiment record belongs to its owners |

## Third review wave preparation

The four findings in `review_output.json` reproduce on `58ee5cd49` with isolated
renderer/extracted-function fixtures. `GPT-VERDICT-58ee5cd49.md` and the CC agree
on the private-probe digest and dispatcher-fixture blockers. The co-op released
one combined fold after the GPT read; a CC delta arriving before push joins it.

- Grafana's own writer already records rendered-file digests and recognizes its
  previous output. `copy_config` now defers `grafana.ini` to that writer, so path
  expansion is not mistaken for an operator port conflict. A same-port rerun and
  an upgrade from the actual `8053f14e7` renderer both pass; an operator-modified
  file remains untouched and returns `needs_owner`. The mechanism is the existing
  [plan writer at 58ee5cd49:507–545,627–644](https://github.com/native-agent-stack/native-agent-stack/blob/58ee5cd49d6d9b19701892b072e22b47ca5889bf/evidence/artifacts/new-wsl-install-plan-20261002/config/observability_config.py#L507).
- A selective install merges only the selected owners' ports into the prior
  complete allocation. Unselected owners retain their recorded values in staged
  assets, command expansion and the final snapshot. The merged allocation is
  collision-checked again before provisioning. Default selection preserves
  measurement-only owners. A row with no allocated ports cannot publish an
  initial service snapshot. On first provisioning of a port-owning row, the
  complete explicit host allocation establishes the initial reservation; this
  does not certify that unselected services were installed.
- Dagu no-start accepts an exact matching unit, refuses a differing unit or
  unfamiliar environment drop-in, and preserves those bytes. It still performs
  no enable/start. The supported unit and environment mechanism remains
  [Dagu v2.18.2 installer:1666–1697](https://github.com/dagucloud/dagu/blob/v2.18.2/scripts/installer.sh#L1666),
  with [systemd v259 drop-in semantics](https://github.com/systemd/systemd/blob/v259/man/systemd.unit.xml#L198).
- Prometheus's install-time unit registration creates its selected data/working
  directory; the standalone renderer stays render-only. This supersedes the
  third-wave placement in the renderer, which violated its existing custody
  contract. [systemd v259 man/systemd.exec.xml:114–125](https://github.com/systemd/systemd/blob/v259/man/systemd.exec.xml#L114)
  requires that directory; [4757–4760](https://github.com/systemd/systemd/blob/v259/man/systemd.exec.xml#L4757)
  identifies failure as `200/CHDIR`. This is a source/fixture correction, with
  native service startup still unmeasured.

The actual `58ee5cd49` CI logs exposed two additional caller/fixture contracts.
Shard 3's scout-dispatch fixture lacked a fake for the new completion helper; its
existing owner-selection assertions are preserved. Shard 5's MCP drift tool still
rendered the frozen incomplete host template. It now requires `--host-file` and
passes that complete explicit string map through the same strict client renderer.
It neither changes the frozen template nor supplies a distro/port fallback. The
existing drift suite uses a complete nonsecret fixture host; a new CLI test
requires refusal before account comparison when the option is missing. Narrow
scope was granted under hcom event reference **185938** (grant message 185948).
See [review-wave-3-receipt.json](review-wave-3-receipt.json) for before/after results
and exact CI jobs. The tool's comparison still reads only the account paths the
operator selects; this lane exercises disposable fixtures only.

The repository-wide caller audit found one additional strict-input variant in
`runtime_profiles.render_wsl_mcp`, plus its frozen telemetry endpoint and provider
gateway value captured at import time. Its WSL render now requires explicit
`NS2604_HOST_FILE`, reuses the strict drift/client rendering path, and obtains
telemetry and both provider endpoints from the current shared allocation. The
three reproductions failed before this correction. The expanded four-case
regression also requires refusal when the explicit WSL selector is missing.
`GPT_MODEL` remains at line 43 and the other existing runtime locators do not move.
[strict-host-consumer-audit.json](strict-host-consumer-audit.json) lists every
matched production caller, fixture group, non-rendering import and generic-loader
exclusion. Graph transport was unavailable; the audit uses repository-root grep
and source/AST inspection, and makes no graph-completeness claim.

The private `review-port-probes.py` original is named under `unpublished_originals`
with a custody statement and no digest, following
[#1188 hashes.json at 3c7a586f](https://github.com/native-agent-stack/native-agent-stack/blob/3c7a586f82d8a9fc96a2a0a562c34f49aa8a4f53/evidence/artifacts/model-routes-sweep-claude-20261015-attempts/hashes.json).
The custody regression failed on the unchanged `58ee5cd49` receipt and passes
after removal. It reports counts, never the protected digest; no private preimage
was read or hashed for this correction. Forward correction leaves Git history
unchanged. The public adapter's digest still binds its published source file.

### Recovery after an incomplete installation

The completion guard protects the allocation snapshot, not every preceding asset
write. A failed row can leave a rendered file or unit candidate at the requested
port while the prior snapshot remains active. Neither that snapshot nor a health
response alone certifies completion of the attempted installation.

1. Retain the host input used for the attempt and identify every selected row that
   may have written files. Keep startup and acceptance pending during recovery.
2. Retry that original selection with the same complete host input and
   `--no-start`, including the rows whose earlier writes succeeded. Resolve each
   `needs_owner` conflict by reviewing the retained configuration; unknown bytes
   are not overwritten automatically.
3. If rolling back, restore the affected configuration/unit files and their prior
   allocation together from the operator's retained backups. A restored snapshot
   alone does not restore files or a running service's state.
4. After the complete selection succeeds, read back the allocation and installed
   unit/configuration endpoints together. Activation and native listener/health
   acceptance remain separate target-operator actions.

### Optional UI changes and evidence limits

Automatic code-graph UI detection reads the plan copy created during provisioning.
Later operator changes to the native cache config require an explicit recheck:
confirm that native `ui_port` matches the complete host allocation, then run the
target's listener check with `--slot code-graph --enabled-listener CODE_GRAPH_UI`
and that host file. Repeat this explicit selection while the native UI remains
enabled. This avoids treating the retained disabled plan copy as current runtime
state. If the native port differs, reconcile it with the allocation before
acceptance; a different local port is not accepted implicitly. This procedure is
source/fixture guidance, not a native lifecycle result.

The README's 8080-to-21808 correction is **source_review**. The pre-existing
Agentsview render already used 21808, so its compatibility check passes before
the prose edit. No prose-specific fail-first test is claimed; the failed-before
Agentsview fixture covers conflicting-configuration custody instead.

## Fourth review wave preparation

The six subcases reported by the CC for Prometheus reproduce against
`5e3d3c2a`: valid, changed_owned, edited, symlink, operator_custody and string_port
all observe runtime state created by a render-only operation. Moving directory
preparation into install-time unit registration restores that contract; the
unchanged custody test and no-start registration fixture pass. No native service
is started locally. The third-wave receipt remains historical; its renderer
placement claim is superseded by this correction.

The additional `review_output.json` finds the first-snapshot upgrade and Dagu
drop-in issues. When a config directory already contains assets but no allocation
snapshot exists, staging now returns `needs_owner` before any row runs. A prior
installation's unselected allocations cannot be inferred from a requested host
file; the operator must establish the complete installed allocation before
migrating it. Fresh empty configuration still stages the complete explicit host
map. Dagu checks the existing coordinator drop-in for differing bytes or a symlink
before its first write, so a later comparison cannot conceal an earlier overwrite.

The gateway allocator permits HTTP port 80. Node's WHATWG URL implementation
normalizes a scheme's default port to an empty string
([Node.js v24.21.0 doc/api/url.md:383–386](https://github.com/nodejs/node/blob/v24.21.0/doc/api/url.md#L383)).
Both Promptfoo config loading and its extracted acceptance predicate now compare
the effective HTTP port. The correct port-80 topology failed against the original
5e3d3c2a config and passes after correction; the two distinct synthetic model
routes are present in that control. An earlier draft control omitted the Claude
route and failed for that independent reason; it is not the port fail-first proof.
This validator source correction supersedes one of the 30 default byte fixtures:
29 still compare byte-for-byte, and Promptfoo's default native exported config
compares equal to the unchanged8053 source. The original source digest is retained
and marked with that explicit supersession; all six dashboard bytes still match.

The [host-allocation addendum](../../../docs/decisions/2026-10-16-new-wsl-host-allocation-addendum.md)
supersedes the old F8/F9 commands and fixed Codex distro identity while preserving
both original decisions. The recipe, checklist, current receipt example and
generated handbook carry complete explicit host inputs. The fixture's collision
inventory includes optional/metrics ports after marker expansion. Documentation
and collision guards fail before the changes and pass afterwards. The frozen
image template and experiment inputs remain unchanged.

### GPT fix2 completion: publication races and direct contract sources

`GPT-VERDICT-5e3d3c2a5.md` agrees on the two blockers and adds three follow-ups.
The complete Dagu preflight now checks the main unit and every installed drop-in
before any configuration write or reload, including the managed coordinator
filename. A sequence fixture first exposed the remaining unknown-drop-in case:
the row had already written/reloaded its coordinator before refusing the other
file. That sequence now refuses without changing either file or requesting reload.
Prometheus prepares its directory after custody validation and before placing the
unit, retaining both the render-only and no-start contracts.

Staging records a fingerprint of the prior nonsecret allocation snapshot and
checks it again before returning. Publication takes an advisory lock, compares
that baseline with the current snapshot, and publishes exactly the staged
effective allocation. A changed snapshot fails with `needs_owner`; it is not
merged into already-rendered assets. The interleaving fixture failed before this
guard and passes after it. The lock serializes cooperating publishers through
[CPython v3.13.16 Doc/library/fcntl.rst:176–205](https://github.com/python/cpython/blob/v3.13.16/Doc/library/fcntl.rst#L176).
This is repository coordination policy, not a claim of whole-install rollback or
protection from an external writer that ignores the lock. Partial asset recovery
still follows the procedure above.

The selective-allocation policy reuses the existing dispatcher at
[native-agent-stack 58ee5cd49, install.sh:83,1284–1294,1350–1364](https://github.com/native-agent-stack/native-agent-stack/blob/58ee5cd49d6d9b19701892b072e22b47ca5889bf/evidence/artifacts/new-wsl-install-plan-20261002/install.sh#L1284):
default/named selection, dependency dispatch and measurement-only rows. Per-owner
allocation merging and change detection are new repository policy around that
contract; they are not attributed to a service vendor.

The runtime repair reuses
[58ee5cd49 new_wsl_client_config.py:1106–1199](https://github.com/native-agent-stack/native-agent-stack/blob/58ee5cd49d6d9b19701892b072e22b47ca5889bf/tools/adoption/new_wsl_client_config.py#L1106),
[the shared allocation loader at config/observability_config.py:156–175](https://github.com/native-agent-stack/native-agent-stack/blob/58ee5cd49d6d9b19701892b072e22b47ca5889bf/evidence/artifacts/new-wsl-install-plan-20261002/config/observability_config.py#L156),
and [5e3d3c2a mcp_template_drift.py:61–94](https://github.com/native-agent-stack/native-agent-stack/blob/5e3d3c2a501d5adf90891337bd70bf8bbb45d270/tools/adoption/mcp_template_drift.py#L61).
The consumer audit now also names
[runtime_acceptance.py:22,120,136 at5e3d3c2a](https://github.com/native-agent-stack/native-agent-stack/blob/5e3d3c2a501d5adf90891337bd70bf8bbb45d270/tools/adoption/runtime_acceptance.py#L120).
Its direct and credential-wrapped checks use the same current profile environment;
fixtures intercept all native/credential calls and assert the allocated endpoint
on both paths. Invalid explicit allocation must be corrected before retry. No
production change to that acceptance caller was needed.
