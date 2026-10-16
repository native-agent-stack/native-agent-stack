# Muse subscription routes in native harnesses

Status: proposed TRIAL mechanisms, pending two-family review. This change
implements item2 of `direction-cc-20261015T1946Z-north-star-new-wsl-takeover.addendum-24.md`,
cited by name only. Base: `fa6cf1a2360bbd1be810045819f222e4432e12bc`.

## Decision and observed result

Extend the existing `ns-run` profiles with `pi-muse` and `opencode-muse` and
explicit opt-in `claude-muse` and `codex-muse` profiles. Every route requests
`mc/muse-wonder-full-1.0` through the existing OmniRoute subscription provider.
These profiles use the harness's native agent loop, tools, configuration,
canonical role instructions, skills, memory and token/context integrations,
telemetry policy and owned Worktrunk workspace. Receipts retain native
invocation events privately and publish derived facts only.

The [preregistration](../../notes/muse-harness-trials-20261016/PREREG.md) preceded
inference. The fixed task required native root instructions and canonical skill
reads, Context Mode Python computation, native file creation, a deterministic
shell assertion, normal completion and runtime-reported model metadata. A
successful exit alone does not pass this qualification. All first attempts and
changed-configuration retries remain separate receipts.

| Lane | First attempt | Latest measured result | Disposition |
| --- | --- | --- | --- |
| ns-pi-muse | FAIL: Context Mode unavailable | PASS after supported native vendor bridge integration;117events,5successful tools | Synthetic smoke qualified; TRIAL pending review |
| ns-opencode-muse | FAIL before inference: namespace executable alias | PASS after exact executable/resource qualification;23events,5successful tools | Synthetic smoke qualified; TRIAL pending review |
| ns-claude-muse | FAIL: strict MCP omission and skill not read | PASS after explicit server/name correction;24events,5successful tools | Synthetic smoke qualified; TRIAL pending review |
| ns-codex-muse | FAIL: continuation stream lacked terminal | No retry;15events,2successful reads, one error terminal | UNQUALIFIED; no real task use |

Per-attempt [derived receipts](../../notes/muse-harness-trials-20261016/receipts/)
name exact versions, time windows, tool completions, failures and model fields.
Pi's intermediate prefix-only retry also failed and remains recorded. Native
Codex startup/skill/four-tool controls passed before its first inference, but
its subsequent protocol failure leaves the lane unqualified. Source diagnosis
does not convert that failure into a successful measurement.

No new builder campaign is assigned by this change. Once review and smoke
qualification are complete, only supplied non-gate tasks may enter a qualified
profile; every resulting change still receives two-family review. Web discovery
has not been exercised by these smokes. None of this promotes a model default,
changes a gate or opens the native Muse builder/reviewer lanes. Their separate
order-safety decision remains controlling.

## Native integration and narrow resources

Pi and OpenCode reuse `tools/adoption/runtime_profiles.py`. The selected pinned
clients are admitted by their native version commands; unsupported versions
refuse. Muse thinking/variant requests are explicitly `max`: Pi otherwise
clamps this custom model's thinking level. The configuration's context limit
is a registry default, not a measured service limit. Subscription cost remains
unpriced/null rather than being published as zero dollars.

Pi loads the existing profile-local npm Context Mode package using native
`settings.packages`. The package declares its own Pi extension and registers
its native bare action names. Its upstream `before_agent_start` waits for its
bridge before the model tool snapshot. Only the four canonical granted actions
are translated to their native names; the remaining seven are excluded by Pi's
native tool allowlist. A no-model SDK control reproduced the exact four active
actions. The generic MCP-prefix invocation tracker does not attribute a bare
bridge name to a prefixed MCP server; the derived receipt separately records
its successful native `ctx_execute` result.

OpenCode executes the admitted physical binary in the existing Bubblewrap
namespace. Its canonical local MCP commands use explicitly qualified executable
files, Python venv resources and named public Node package roots. JavaScript
entrypoints use their physical module paths so vendor-relative imports resolve.
The new inventory validates installed package pins, interpreter targets and
required dependency directories; missing or changed resources refuse. It adds
28 named public resources, not a home/install/cache ancestor. Runtime state
for npm, Serena and Semble stays inside the profile. Actual namespace discovery
connected all10 admitted canonical MCP servers and ran RTK0.51.0. Alias-read
containment remains the existing separately PARKED boundary; this record does
not expand the worktree isolation claim into hostile-code network isolation.

Claude Code and Codex reuse the canonical WSL renderer in
`tools/adoption/muse_cli_harness.py`. Each gets an owned synthetic HOME, native
configuration/session state and its own canonical managed skill links. No
native authentication or account file is copied. Claude's strict print MCP
configuration registers Context Mode directly and maps exact canonical role
grants to that native registration; plugin hooks/skills remain native. Codex
registers the existing package through its supported local marketplace and
retains complete canonical MCP transports in role-specific CLI overrides.
Its app-server control reports the canonical skill and exactly four Context
Mode actions without submitting an inference turn. The existing plan-selected
ai-memory2.6.6 executable is verified as a retained dependency; no memory-layer
default is changed. Child process context excludes ambient provider secrets.

Future Codex preparations also set the supported native provider request and
stream retry limits to0; native `config/read` verified both values without
inference. The initial failure's five reconnect messages remain in its own
receipt. Bounded future retries do not correct or qualify the stream protocol.

Runtime/gateway model fields are not independent upstream-model attestation.
The gateway can echo the requested model. Requested `max` does not establish
unobserved upstream wire effort; protocol conversion may normalize it. Both
limits remain explicit in receipts and the route screen.

## Sources at a pin

- [earendil-works/pi](https://github.com/earendil-works/pi/tree/04566631c2b51fb688486bc1f040f60d1518c126),
  1.1.0: `packages/coding-agent/docs/{cli,packages,mcp,sdk,models}.md`,
  `examples/sdk/14-codemode-mcp.ts`, model configuration and provider composer;
  native tools, local package loading, lifecycle and thinking-level mappings.
- [anomalyco/opencode](https://github.com/anomalyco/opencode/tree/53d1eabb61e21162157817bf677da0a4ad3332e3),
  1.18.35: provider configuration, `session/llm/request.ts:80-91`,
  provider transforms, native agent permissions, skill loader, MCP and export.
- [mksglu/context-mode](https://github.com/mksglu/context-mode/tree/589d8214d56740a28b5f7bf63167743d586b0b40),
  release1.0.169: `package.json:30-32`, `README.md:1015-1023`,
  `src/adapters/pi/extension.ts:607,635`, `mcp-bridge.ts:941,1023-1024`.
  Installed npm artifact integrity and absence of gitHead are recorded
  separately from source. Prior reviewed6f0cc684 is a later reference.
- [containers/bubblewrap](https://github.com/containers/bubblewrap/blob/124c4cdf4321f63ef17a1cb0ce8f9dd45bd7adbe/bwrap.xml),
  v0.11.1: named bind mounts, process namespace, session and parent-lifetime
  flags. The existing native runtime fence supplies these unchanged flags.
- [rtk-ai/rtk](https://github.com/rtk-ai/rtk/tree/e001f773f80b22b7dc4c7a79521b30e35aaef026),
  v0.51.0: vendor native Pi/OpenCode hook installers.
- Claude Code2.1.301 installed native `--help` and official
  [gateway](https://code.claude.com/docs/en/llm-gateway),
  [models](https://code.claude.com/docs/en/model-config) and
  [CLI](https://code.claude.com/docs/en/cli-reference) references, read2026-10-16.
- [openai/codex](https://github.com/openai/codex/tree/092d3acd6bec3e3a14bdc7e7a2810ab628ab759d),
  rust-v0.162.1: config overrides/transport validation, local marketplace,
  reasoning vocabulary and `codex-api/src/sse/responses.rs:418,558-562,920-923`.
  Official [advanced configuration](https://developers.openai.com/codex/config-advanced/)
  and [app-server](https://developers.openai.com/codex/app-server/) references,
  read2026-10-16.
- Probe-only [anthropics/claude-agent-sdk-python](https://github.com/anthropics/claude-agent-sdk-python/tree/v0.2.168),
  `ClaudeSDKClient.connect(None)`, `get_server_info`, `get_mcp_status`: exact
  native CLI control initialization without a model prompt.
- [diegosouzapw/OmniRoute](https://github.com/diegosouzapw/OmniRoute/tree/c1e30b7676975feb298b49eff6ff58923c04b89e),
  candidate source v3.8.51: `open-sse/config/providers/registry/muse-code/index.ts:40-47`,
  `open-sse/config/museCode.ts:17-19`, `open-sse/handlers/chatCore.ts:1037-1059`,
  Responses tool-name/effort translators. These primary source observations
  do not attest the currently loaded compiled gateway bytes or settings.
- [Route screen](../../notes/muse-harness-trials-20261016/CLI-ROUTE-SCREEN.md)
  retains the native ELF pins, ai-memory2.6.6 primary references and gateway
  candidate source. [Auxiliary inventory](../../tools/adoption/muse_auxiliary_resources.py)
  names the retained npm/Python package pins and supported state-path seams.

## Verification and overturning evidence

Model-free unit/namespace tests cover exact model dispatch, native thinking
configuration, model identity limits, cost semantics, exact role mappings,
package preservation, canonical transport overrides, environment isolation,
explicit public dependencies and tool-completion accounting. Relevant fixes
include fail-before or mutation controls. Actual smokes are a separate evidence
class; all earlier failed attempts remain available as derived receipts.
The combined named test command passed92 tests with zero skips. The
[qualification summary](../../notes/muse-harness-trials-20261016/qualification.json)
retains the exact command and control inventory.

Codex requires an evidenced protocol correction plus a fresh preregistered
changed-configuration smoke before real tasks. A later failure of any required
native layer reopens that profile's qualification. No fallback model or bare
API/loop substitute settles a missing harness layer. Current model-routes FINAL
alone may promote a default.
