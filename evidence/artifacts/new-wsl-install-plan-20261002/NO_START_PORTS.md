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
- Dagu uses `--service no`, then the pinned upstream user-unit form with nonsecret
  inline settings, including its coordinator port. Normal installation enables
  and starts that unit through the common guarded activation helper.
- Docker's rootless setup tool starts and enables the unit internally, so the
  no-start path installs its pinned unit form without executing that tool.
  Rootful Docker/socket/containerd units are masked before package installation
  to prevent package scripts from activating them. Existing running services are
  not stopped by the mask. No-start does not disable previously enabled units.
- Host values select all declared listener ports through `service_ports()` in
  `config/observability_config.py`. The file remains a flat string map compatible
  with the existing host renderer. Memory uses `AI_MEMORY_URL`; the other ports
  use the `NS_PORT_*` keys shown in the WSL host template. Unknown keys, invalid
  port values and duplicate allocations fail before package installation.
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
  allocation collisions. The external Ollama guard ports, synthetic alert label,
  and worker closed-port negative control remain explicitly classified exceptions.
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
`systemd-run --user --scope -p CPUWeight=idle --quiet --`. No installer script,
real installer, or real `systemctl enable/start` ran on the build host.

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
