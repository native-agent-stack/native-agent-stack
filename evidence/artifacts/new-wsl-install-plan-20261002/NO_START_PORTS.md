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
