# Addendum: explicit host allocation for new WSL provisioning (2026-10-16)

**Supersedes:** the F8/F9 host-value and command instructions in
[2026-10-01-new-wsl-distro-recipe.md](2026-10-01-new-wsl-distro-recipe.md),
including its historical command table, and the fixed NativeStack2604 identity
in the 2026-10-08 amendments of
[2026-10-02-new-wsl-client-configuration.md](2026-10-02-new-wsl-client-configuration.md).
Those dated records remain unchanged. Their historical host observations do not
establish identity, ports or acceptance for another distribution.

The current install/client contract requires a complete nonsecret string-map
host file. Every `NS_PORT_*` allocation is explicit; `AI_MEMORY_URL` may supply
the memory port. `WSL_DISTRO_NAME` must name the target distribution and cannot
be missing or blank. The Codex shell policy renders that field under
`inherit = "none"`; NativeStack2604 is an example host value, not an implicit
default for a new distro.

The nine-field `host.new-distro.json.template` and its image experiment remain
frozen. They provide an initial path template only. Extend the private rendered
host file using the keys of `adoption/hosts/example.json`, allocate all ports
against the shared namespace, and validate the complete result before F9.
The collector has no fixed-port exception. Optional listeners, metrics ports and
temporary/closed fixtures participate in collision checks even when they are
not expected to be listening. Template extension remains **DEFERRED** to a
superseding experiment record by its owners; this addendum does not refreeze it.

F9 provisions with `--no-start --host-file`, runs only post-install acceptance,
then configures clients from that same host file before sign-in. Native service
activation and fresh listener/health checks are later target-operator actions.
No running or enabled service is disabled by no-start. Existing installations
without a complete allocation snapshot require custody reconciliation before
selective migration; a requested allocation is not proof of an installed port.

The live recipe, first-boot checklist, generated handbook and current synthetic
receipt example use the replacement rows below. Other historical recipe command
rows remain applicable. These are instructions and source/fixture evidence,
not a new host acceptance receipt.

## Pinned sources

- [systemd/systemd v259, man/systemctl.xml:880–927](https://github.com/systemd/systemd/blob/v259/man/systemctl.xml#L880)
  and [man/systemd.unit.xml:2224–2255](https://github.com/systemd/systemd/blob/v259/man/systemd.unit.xml#L2224):
  enablement links and separate start semantics.
- [openai/codex rust-v0.161.0, codex-rs/protocol/src/shell_environment.rs:100–102,138–142](https://github.com/openai/codex/blob/rust-v0.161.0/codex-rs/protocol/src/shell_environment.rs#L138):
  explicit environment values after empty inheritance.
- [Native stack 5e3d3c2a, config/observability_config.py](https://github.com/native-agent-stack/native-agent-stack/blob/5e3d3c2a501d5adf90891337bd70bf8bbb45d270/evidence/artifacts/new-wsl-install-plan-20261002/config/observability_config.py#L64)
  and [new_wsl_client_config.py:1106](https://github.com/native-agent-stack/native-agent-stack/blob/5e3d3c2a501d5adf90891337bd70bf8bbb45d270/tools/adoption/new_wsl_client_config.py#L1106):
  the complete allocation and explicit identity contracts this documentation follows.
- [Listeners and ports at8053f14e7, linux-wsl2.md:253](https://github.com/native-agent-stack/native-agent-stack/blob/8053f14e7e0817d2502dff2bb284bfb7e1b0152f/adoption/platforms/linux-wsl2.md#L253):
  the WSL shared namespace. The install plan uses its own renderer, not the
  workstation backend renderer.

## Command table

Only F8/F9 rows are superseded. Every other row remains in the original record.

| Step | Shell | Command | Proof |
| --- | --- | --- | --- |
| F8 | sh | `cd ~/code/native-agent-stack` | Complete private host values and current allocation preflight; no service activation |
| F8 | sh | `python3 -c 'import string, sys; sys.stdout.write(string.Template(open(sys.argv[1], encoding="utf-8").read()).substitute(WSL_USER=sys.argv[2]))' adoption/templates/wsl/host.new-distro.json.template "$(id -un)" > 'adoption/hosts/<host>.json'` | Complete private host values and current allocation preflight; no service activation |
| F8 | sh | `python3 -m json.tool 'adoption/hosts/<host>.json'` | Complete private host values and current allocation preflight; no service activation |
| F8 | sh | `git check-ignore 'adoption/hosts/<host>.json'` | Complete private host values and current allocation preflight; no service activation |
| F8 | sh | `ss -ltnH > /tmp/native-stack-port-preflight.txt` | Complete private host values and current allocation preflight; no service activation |
| F8 | sh | `python3 -B evidence/artifacts/new-wsl-install-plan-20261002/check_plan.py --host-file 'adoption/hosts/<host>.json' --ss-output /tmp/native-stack-port-preflight.txt` | Complete private host values and current allocation preflight; no service activation |
| F9 | sh | `cd ~/code/native-agent-stack` | No-start provisioning/post-install or strict client wiring; exit 0, skips are not acceptance |
| F9 | sh | `bash evidence/artifacts/new-wsl-install-plan-20261002/install.sh --no-start --host-file 'adoption/hosts/<host>.json'` | No-start provisioning/post-install or strict client wiring; exit 0, skips are not acceptance |
| F9 | sh | `bash evidence/artifacts/new-wsl-install-plan-20261002/accept.sh --host-file 'adoption/hosts/<host>.json'` | No-start provisioning/post-install or strict client wiring; exit 0, skips are not acceptance |
| F9 | sh | `python3 -B tools/adoption/new_wsl_client_config.py --check` | No-start provisioning/post-install or strict client wiring; exit 0, skips are not acceptance |
| F9 | sh | `python3 -B tools/adoption/new_wsl_client_config.py --apply --host '<host>'` | No-start provisioning/post-install or strict client wiring; exit 0, skips are not acceptance |

## Validation boundary

The failed-before documentation checks expose the missing addendum, incomplete
checklist and hostless F9 commands at5e3d3c2a. The port-inventory regression exposes
the lost21302/21888/21889 markers. Production host/config parsing and service-state
fixtures remain separate from these documentation checks. Neither the template
nor the original decision records was rewritten.
