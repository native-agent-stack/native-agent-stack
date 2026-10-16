# Claude Code and Codex subscription-Muse route screen

Screen date: 2026-10-16. These lanes are TRIAL, advisory and non-gating.
The selected route is the existing OmniRoute `muse-code` subscription provider,
`mc/muse-wonder-full-1.0`. The separately labelled Meta API model remains outside
this screen. No account or provider setting is changed.

## Sources and installed runtime observations

- Claude Code native ELF 2.1.301, observed by `--version`; SHA256
  `bc1aad9982c7b59c7d889ff92595d61cf46e0a6eae074cb551d932a989bcd222`.
  Its `--help` documents `--model`, `--effort max`, `--plugin-dir`,
  `--settings`, `--setting-sources`, `--strict-mcp-config`, `--tools`,
  `--allowedTools`, `--agent`, `--permission-mode dontAsk` and streaming print
  output. It is the installed native executable, rather than a replacement
  Anthropic API client.
- Claude Code [LLM gateway](https://code.claude.com/docs/en/llm-gateway),
  [model configuration](https://code.claude.com/docs/en/model-config) and
  [CLI reference](https://code.claude.com/docs/en/cli-reference), read
  2026-10-16: native gateway URL/token environment, custom-model effort
  capability opt-in and native configuration isolation. The local token is
  the existing gateway's non-secret `local` placeholder.
- Meta [Coding agents](https://developers.meta.com/ai-tools/muse/docs/guides/coding-agents/),
  read 2026-10-16, documents Claude Code's native gateway mechanism. Its
  separately labelled API example does not establish the subscription route's
  model identity; the owner-selected `mc/` route is measured independently.
- Codex 0.162.1 native ELF, observed by `--version`; SHA256
  `628e35487d888a28f0427fc37501da529dd3d81fcbad7a2c3421c1e8670d92e1`.
  Upstream `openai/codex` rust-v0.162.1,
  `092d3acd6bec3e3a14bdc7e7a2810ab628ab759d`:
  `codex-rs/protocol/src/openai_models/reasoning_effort.rs` contains `Max`;
  `codex-rs/cli/src/marketplace_cmd.rs:45` and `:66` describe the native
  local marketplace path; `codex-rs/core-plugins/src/marketplace_add/source.rs:32`
  and `:86` implement local registration without staging the marketplace root.
  [Advanced configuration](https://developers.openai.com/codex/config-advanced/),
  read 2026-10-16, documents custom providers, base URL and Responses wire API.
  The same pin's `codex-rs/config/src/overrides.rs:17` and `:22` split
  CLI config paths on literal dots. Server override keys therefore use
  validated native bare components, and each override retains its complete
  canonical transport plus the role's exact tool grants.
  `codex-rs/config/src/mcp_types.rs:437`, `:542` and `:597` validate the
  transport while deserializing. `codex-rs/config/src/loader/mod.rs:652`
  implements strict CLI-layer validation. Native app-server configuration
  preflights retain the earlier rejected key/partial-transport attempts
  independently from the corrected preparation. Nested tables normally merge
  recursively (`codex-rs/config/src/merge.rs:57` and `:139`); this record does
  not infer a universal table-replacement rule from the failed preflight.
- Installed npm `context-mode@1.0.169`; its release tag in `mksglu/context-mode`
  resolves to `589d8214d56740a28b5f7bf63167743d586b0b40`:
  `.claude-plugin/marketplace.json`, `.claude-plugin/plugin.json`,
  `.codex-plugin/plugin.json`, `.codex-plugin/hooks.json`, `start.mjs`.
  The existing pinned package supplies native token/context hooks and skills;
  its native local registration runs only in the new profile's own state.
  npm supplies an integrity value and no gitHead. The prior retained reviewed
  `6f0cc6841c687e754059f36714a11233fda1a02b` source is later, not an asserted
  npm tarball commit. The release and retained source share the relevant Pi
  adapter bytes; artifact and source identity remain separately recorded.
- Existing host ai-memory 2.6.6, `akitaonrails/ai-memory` v2.6.6:
  [README](https://github.com/akitaonrails/ai-memory/blob/v2.6.6/README.md),
  read 2026-10-16; actual `--version`, `--help` and `hook --help` establish
  the rendered `--data-dir`, `--event`, `--agent`, `--server-url` arguments.
  The selected ELF SHA256 is
  `2f74b0195a259096fcb0588b4426835b5363eb4e44793ef15f2eb0587ab5e0b5`.
  Existing currency lineage is
  `docs/decisions/2026-10-15-new-wsl-clean-install-plan.md:684`.
  This is an existing host dependency binding, not an installation or a change
  to the memory-layer default. `new_wsl_client_config.py:1123` and
  `render_config.py:15` expose the explicit `AI_MEMORY_BIN` host-value seam.
  Profile data stays in the synthetic HOME, while this executable is selected
  by the committed host plan's `.local/bin/ai-memory` path and verified by hash.
  The tag resolves to `04a9e8f576de67e1d2282ee29415d1b0d5b979c8`;
  `crates/ai-memory-cli/src/cli.rs:94` and `:2959` declare those global/hook
  arguments, `crates/ai-memory-cli/src/lib.rs:47` dispatches the hook before
  loading configuration, and `commands/hook.rs:149` handles boundary events.
- [diegosouzapw/OmniRoute](https://github.com/diegosouzapw/OmniRoute/tree/c1e30b7676975feb298b49eff6ff58923c04b89e)
  candidate source v3.8.51,
  `src/app/api/v1/messages/route.ts`, `src/app/api/v1/responses/route.ts` and
  `chatCore.ts:1037`: the gateway supports the two native protocols and can echo
  the requested model to Claude Code and Codex. A response model field is
  runtime/gateway-reported evidence and is not independent upstream attestation.
  Source/package observations do not attest the currently loaded compiled
  gateway bytes or request rewrites. No operational settings store was read.
- Probe-only `anthropics/claude-agent-sdk-python` v0.2.168,
  [`client.py`](https://github.com/anthropics/claude-agent-sdk-python/blob/v0.2.168/src/claude_agent_sdk/client.py):
  the documented `ClaudeSDKClient.connect(None)`, `get_server_info()` and
  `get_mcp_status()` control methods initialize and inspect the selected native
  CLI without submitting a prompt. The official manylinux x86_64 wheel SHA256 is
  `be197be92549909ec62a2cee04c27f4b0a38c80f723735538a3efc352507f81d`.
  This probe dependency lives only in the profile-local venv. `cli_path` selects
  the separately qualified 2.1.301 native ELF. The official Python SDK reference
  was read 2026-10-16. This control probe does not change the lane's native
  execution mechanism.

## Adopted native mechanisms

`tools/adoption/muse_cli_harness.py` reuses
`tools/adoption/new_wsl_client_config.py`'s committed WSL analysis and renderer.
It starts with canonical settings, deny rules, hooks, managed-skill inventory,
MCP definitions, memory endpoints, token/context configuration and OTLP policy.
The two profiles have their own synthetic HOME, client config, sessions,
context-state, events and invocation receipt; no host config or account file is
read or copied. Existing managed skills are linked individually by inventory.
Unqualified optional MCP services remain excluded, matching the parent runtime
profiles. Selected roles receive their exact native tool grants. Codex's
reviewer shell sandbox is read-only; role instructions remain separate from
the shell sandbox, and MCP subprocesses retain their documented native scope.

Claude Code loads the existing pinned Context Mode package's hooks and skills
through its native `--plugin-dir`; strict MCP configuration supplies all named
canonical servers, including Context Mode. Derived role metadata maps its
canonical plugin tool names to the equivalent explicit server names, preserving
the exact action grants. Codex registers that same package as a native local marketplace in
the isolated CODEX_HOME and invokes its supported `plugin add` command. The
canonical Codex configuration retains the plugin hooks and disables its duplicate
MCP server in favour of the canonical session-bound registration. Neither
launcher uses a bare mode.

Every launch verifies the native ELF version and hash, creates a fresh owned
worktree through the existing Worktrunk helper, records private native events,
and records derived counts and the invocation's requested model separately.
Claude aliases and child defaults all select the same subscription model.
Codex selects the native Responses provider without OpenAI account auth.

The requested effort is `max` for both clients. Codex's pinned vocabulary and
Meta's documented reasoning vocabulary both admit it. Claude's native custom
model capability opt-in admits `max`. Gateway protocol conversion can normalize
the value; the receipt records requested effort only and does not assert an
unobserved upstream effort. Missing model fields remain `not-reported`.

## Qualification boundary

Model-free configuration controls establish native arguments, retained canonical
layers, environment isolation, exact role MCP grants and truthful model identity
labels. Live native tool execution, gateway protocol parity and runtime-reported
model are separate preregistered smoke measurements. A configuration render alone
does not qualify a profile or promote a default.

The first Claude inference completed the deterministic file check but failed
qualification because its strict print invocation had no Context Mode MCP
registration. Its native initialization already listed `find-skills`; the
canonical builder role has `Read` and excludes `Skill`, and its brief had not
supplied the personal skill's path. The corrected derived configuration retains
the explicit Context Mode server and maps the same four admitted role actions
to that server's native tool namespace. The next preregistered invocation names
the existing personal `find-skills/SKILL.md` for native Read, preserving role
bounds. The v4 no-prompt SDK control probe observes the native skill command and
the explicit Context Mode server connected. Its server status lists the server's
11 catalog tools; the role's exact grants remain four actions.

Codex's native app-server control preflight reuses the existing
`apply_codex_lane.AppServer` transport and official `skills/list` and
`mcpServerStatus/list` methods. Applying the exact job's corrected configuration
overrides reports `find-skills` and precisely the four Context Mode role tools:
`ctx_execute`, `ctx_execute_file`, `ctx_batch_execute`, `ctx_search`. No inference
turn is submitted by this preflight. The public
[app-server reference](https://developers.openai.com/codex/app-server/) was read
2026-10-16; protocol behavior was reproduced on the pinned native ELF.

Invocation facts distinguish tool attempts from paired successful results,
failed results and unresolved attempts. Codex started/completed records with
the same item ID count as one attempt. Error terminals are counted separately
from successful completion terminals. The legacy `tool_events` array is labelled
as attempts and is not used alone to establish a successful tool invocation.

The first actual Codex smoke is retained as UNQUALIFIED: native exit 1, 15
events, two successful native command reads, no completed edit or MCP call, and
one error terminal. After its initial successful inference/tool calls, the
native client reconnected five times and reported an SSE stream closed before
`response.completed`. The pinned client requires a Responses terminal
(`codex-rs/codex-api/src/sse/responses.rs:418`, `:558` and `:920`); this record
does not relax that consumer or infer a provider fix from configuration alone.
Its own rollout records cumulative provider usage of 23,028 input tokens, 648
output tokens including 477 reasoning tokens, and 23,676 total tokens. Its model
fields represent selected session configuration; no runtime response model was
reported, so model identity remains `not-reported`.

Subsequent generated Codex trial configurations set `request_max_retries = 0`
and `stream_max_retries = 0` through the supported provider fields. At the same
upstream pin, `codex-rs/model-provider-info/src/lib.rs:180` and `:498` show these
are optional unsigned integers and preserve explicit zero. The regression
failed before the change, and a model-free native `config/read` reproduced both
zero values. The original smoke/configuration remains unchanged; this policy
does not qualify the failed lane or authorize another inference attempt.

The first native preparations used the actual `codex-ecosystem` runtime prefix.
Fresh v2 preparations were retained when the native Claude MCP health check
exposed a missing memory-hook executable: an omitted explicit host value had
made the renderer derive an absent 2.4.1 path from that prefix. The path-control
regression failed on that rendered command before the fix. Fresh v3 preparations
use the explicit plan-selected memory binary; no existing profile was replaced.
Both native MCP discovery commands returned 0 with empty stderr. Claude's native
plugin discovery reported Context Mode connected. Codex's native configuration
discovery reported its Context Mode registration enabled, and the existing MCP
SDK 1.32.0 completed an initialize/tools-list/`ctx_execute` check against that
exact configured command. It enumerated 11 tools, returned no tool error and
computed 42. These controls made zero model calls. Per-lane private logs and
descriptors remain under the recorded versioned runtime-profile roots.
