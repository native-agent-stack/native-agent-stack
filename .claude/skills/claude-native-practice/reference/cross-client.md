# Claude Code and Codex: one practice, native execution per client

Ruled: command center, 2026-10-09 ~14:2xZ (layer 3 as the landing rule for every author; layers 1 and 2 here). Index: [slots.md](slots.md).

## 1. Procedure

Instructions as a short AGENTS.md map into versioned docs, and Agent Skills loaded by progressive disclosure; both clients read both.

Sources: <https://agentskills.io/specification>, <https://developers.openai.com/codex/skills>, <https://developers.openai.com/codex/guides/agents-md>, <https://openai.com/index/harness-engineering/>

## 2. Native execution

Each client runs the procedure with its own mechanism; nothing is ported between them.

Sources: <https://developers.openai.com/codex/subagents>, <https://developers.openai.com/codex/hooks>, <https://developers.openai.com/codex/noninteractive>, <https://developers.openai.com/codex/plugins>

## 3. Gate

A deep multi-agent review of every PR by the other model family, each finding given a landing-time disposition, precision tracked per family per week.

Sources: <https://claude.com/blog/code-review>, <https://www.anthropic.com/research/multiagent-systems>

## Native mechanism per client

| Need | Claude Code 2.1.296 | Codex 0.161.0 |
| --- | --- | --- |
| Delegation with fresh context | subagents (Agent tool), saved Workflows | subagents (explorer and custom agents) |
| Completion gate | Stop hook returning decision block; stop_hook_active bounds the loop | Stop hook returning decision block; stop_hook_active in the input |
| Structured headless result | `claude -p --json-schema` | `codex exec --output-schema` |
| Machine-readable event stream | `--output-format stream-json` | `codex exec --json` |
| Packaged capability | plugins (skills, agents, hooks, MCP) | `codex plugin add` (skills, MCP) |
| Native review | `/review-changes` (saved Workflow), `/code-review` in the main session | `codex review --base <ref>` or `--commit <sha>` |
| Clean-context run for an eval | a fresh subagent or `claude -p` session | `codex exec --ephemeral` |

Claude column sources: the Claude Code documentation pages the 2026-10-09 reading captured. For each citation, the URL, the capture's
sha256 and the fetch time are locators of `evidence/artifacts/claude-native-practice-20261009/claims.json`, and the line (counted by newline
in that capture) is recorded with the sha256 of its text in `evidence/artifacts/claude-native-practice-20261009/cross-client-lines.json`; a
test checks the page against both. The captures are private working papers of the reading, not in this repository: with a capture,
`sed -n '<line>p' <capture> | sha256sum` prints the recorded hash of a line that is followed by a newline (each cited line is). `/review-changes` is this repository's saved Workflow,
`examples/claude-native/workflows/review-changes.js`.

| Need | Claude Code source |
| --- | --- |
| Delegation with fresh context | [sub-agents](https://code.claude.com/docs/en/sub-agents.md) line 11, sha256 `b4e0ef9b2d9a1cba`, fetched 2026-10-09T03:39:03Z (each subagent runs in its own context window); [sub-agents](https://code.claude.com/docs/en/sub-agents.md) line 492, sha256 `b4e0ef9b2d9a1cba`, fetched 2026-10-09T03:39:03Z (the Agent tool, renamed from Task in 2.1.63); [workflows](https://code.claude.com/docs/en/workflows.md) line 204, sha256 `e55138abf9b78682`, fetched 2026-10-09T03:39:40Z (saved Workflows in the project's .claude/workflows/) |
| Completion gate | [hooks](https://code.claude.com/docs/en/hooks.md) line 2587, sha256 `3bd21d31955304d9`, fetched 2026-10-09T03:38:41Z (the Stop input carries stop_hook_active); [hooks](https://code.claude.com/docs/en/hooks.md) line 2655, sha256 `3bd21d31955304d9`, fetched 2026-10-09T03:38:41Z (decision block prevents Claude from stopping) |
| Structured headless result | [cli-reference](https://code.claude.com/docs/en/cli-reference.md) line 103, sha256 `54587c07d51da9f2`, fetched 2026-10-09T03:38:34Z (--json-schema, print mode only) |
| Machine-readable event stream | [cli-reference](https://code.claude.com/docs/en/cli-reference.md) line 112, sha256 `54587c07d51da9f2`, fetched 2026-10-09T03:38:34Z (--output-format text, json or stream-json) |
| Packaged capability | [plugins](https://code.claude.com/docs/en/plugins.md) line 9, sha256 `eb8b9f92d75d42d7`, fetched 2026-10-09T03:39:03Z (a plugin is a directory of skills, agents, hooks and MCP servers) |
| Native review | [commands](https://code.claude.com/docs/en/commands.md) line 71, sha256 `98494561aac56c11`, fetched 2026-10-09T03:41:45Z (/code-review) |
| Clean-context run for an eval | [headless](https://code.claude.com/docs/en/headless.md) line 17, sha256 `25885d2e178a9746`, fetched 2026-10-09T03:38:34Z (claude -p); [sub-agents](https://code.claude.com/docs/en/sub-agents.md) line 11, sha256 `b4e0ef9b2d9a1cba`, fetched 2026-10-09T03:39:03Z (a fresh subagent context) |
