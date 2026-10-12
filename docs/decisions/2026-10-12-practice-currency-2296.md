# The Claude native-practice skill moves from client 2.1.295 to 2.1.296, 2026-10-12 (CPA-V-09)

Status: decided by reading the release's own entries. The converged Claude practice audit (group CPA-V-09, accepted as the work queue by the command center's ruling of 2026-10-12T13:38:12Z) found the skill's pages and
`slots.json` at 2.1.295 while the installed client, and the repository's own upstream-surface baseline, are at 2.1.296. This record is the delta the skill's step 2 asks for, and it changes no default.

## Context

- `claude --version` prints `2.1.296 (Claude Code)`; `catalogs/foundation/upstream-surface-baseline.json` (`versions.claude_code`, resolved by `8b1ef0c37` on 2026-10-11) says 2.1.296; the pages and `slots.json` said 2.1.295, checked 2026-10-09.
  The new-host install pin (`adoption/pins-linux-x86_64.json`) is a different thing, a minimum version of 2.1.295, and is not touched.
- The skill's rule (`SKILL.md` step 2): when the installed client is newer than a page's version, read the CHANGELOG entries between the two for that slot's area, and treat a row as current only if none changes the
  behaviour its default depends on. A routing or compaction default changes only after its own paired run.

## The delta

`anthropics/claude-code@3deb873687379f0c199a69fdaccc65f0865f7a29` `CHANGELOG.md`, section 2.1.296, lines 5 to 83: 79 entries, each assigned to exactly one row below.

| Lines | What | Slots and decision |
| --- | --- | --- |
| 6 | `autoCompactWindow` in subagent frontmatter and `--agents` definitions | `context-compaction`, `subagent-definitions`: evidence added; no definition of ours sets it and no paired run supports an earlier window, so the default is unchanged |
| 7 | `CLAUDE_CODE_WORKFLOW_SUBAGENT_MODEL` runs every workflow agent on one model | `model-effort-routing`, `background-workflows`: evidence and a note that it is unset; it would pin one model for all workflow agents, which the per-role route does not do |
| 59 | `--debug` names unrecognized frontmatter fields of custom agent files | `subagent-definitions`: evidence and a note (a way to catch a misspelt field) |
| 65 | the default limit on MCP tool descriptions and server instructions is 4,096 characters, was 2,048 | `mcp-config-tool-search`: evidence and a note; the knob (`CLAUDE_CODE_MAX_MCP_DESCRIPTION_LENGTH`, L1522) stays unset |
| 13, 15, 61, 63 | headless sessions no longer start an MCP server switched off for the folder; a managed-settings `forceLoginMethod: gateway` regression; `--debug` logs hooks with command, outcome and duration; `/cost` prices Sonnet 5.5 cache reads at $0.10 per million (was $0.20) | read, rows unchanged. L15 concerns managed settings, so it does not settle the user-settings scope that the `native-clients` row calls unconfirmed. L63 means client-reported Sonnet 5.5 costs before and after 2.1.296 are not like for like on the cache-read part; the `usage-cost-monitoring` row already calls the counters estimates |
| 11, 12, 18, 19, 20, 23, 24, 27, 34, 35, 36, 39, 47, 48, 49, 50, 62 | fixes of managed-settings hooks, resumed subagents, altered hook output, secret redaction, an interrupt in a `UserPromptSubmit` hook, plugin SessionStart hooks, workflow nesting and CRLF, interrupted-turn resume, `BASH_ARGV0` permission checks, non-UTF-8 edits, OpenTelemetry `git_commit_id`, transcript garbage collection and `claude purge` | bug fixes: no slot default depends on the behaviour that was fixed |
| 8, 10 | `CLAUDE_CODE_OVERLOADED_RETRY_MAX_DELAY_MS`; the Read tool's `allow_large` option | new options no row selects |
| 37, 38, 66 | the `←` key moving a session to the background | an interactive key; the practice's background routes are `claude --bg` and the supervisor, not the key |
| 9, 28, 29, 30, 31, 32, 44, 45, 46 | plugin and marketplace machinery, mods, skills synced from claude.ai | not relied on beyond the installed plugins, whose defaults these fixes do not alter |
| 5, 14, 16, 17, 57, 58 | the Claude apps gateway, `--teleport`, token counts behind gateways | not used on this host |
| 25, 26, 33, 41, 42, 43, 67-83 | self-hosted runners, cloud sessions, Code Review, Claude Tag, the VS Code extension | not used on this host |
| 21, 22, 40, 51, 52, 53, 54, 55, 56, 60, 64 | terminal and display fixes, Windows and PowerShell fixes, auto mode's display, the bundled dataviz skill | not applicable to a Linux terminal host, or no row |

## Decision

1. **The pages and `slots.json` move to 2.1.296, checked 2026-10-12.** The `Client` stamp of every layer page, the `slots.md` index line and the Claude Code column header of the cross-client table change; `client_version` and
   `checked_at` of `slots.json` change with them. Mentions of 2.1.295 that are history stay: `onFailure: "block"` arrived in 2.1.295, a measurement was taken on 2.1.295, and a changelog line cited at v2.1.295.
2. **Five rows gain the evidence of the entries that touch them, and a note** (above). No default, route, alternative or overturn condition changes. The snapshot manifest's label (`evidence/artifacts/claude-native-practice-20261009/claude-native-slot-manifest.json`, `current_decision_source`) follows the new `slots.json`: its sha256 and the four rows
   that now differ in `evidence` (`context-compaction`, `mcp-config-tool-search`, `model-effort-routing`, `subagent-definitions`; `background-workflows` was already listed).
3. **The drift note of `workers.md` is re-measured.** On 2026-10-12 the 11 user-scope agent copies equal `adoption/agents/claude` byte for byte (the 2026-10-09 note counted four that differed) and the four host-only definitions
   remain (`codebase-memory`, `codebase-memory-auditor`, `codebase-memory-scout`, `semble-search`, installed by their vendors). That 4 of 11 bodies point at paths only this repository has was measured on 2026-10-09 and is not re-measured here.
   Detecting the drift class is CPA-V-10, a separate change.
4. **A test pins the version.** `tests/test_native_practice_currency.py` compares `slots.json` and every page's stamp with the repository's upstream-surface baseline and fails at 2.1.295; it also checks that this table assigns
   every line from 5 to 83 of the section once.

## Alternatives

- **Bump the stamps only.** Rejected: the stamp says the rows were checked against the release, and four entries touch five of them.
- **Change a default on the strength of an entry.** Rejected by the rule above: `autoCompactWindow` and `CLAUDE_CODE_WORKFLOW_SUBAGENT_MODEL` are routing and compaction levers, and each needs its own paired run.
- **Move the install pin to 2.1.296.** Not this change: the pin is a minimum version for new hosts and moves with the bootstrap's own acceptance.

## What this does not cover

Entries after 2.1.296 (the installed client is 2.1.296); a re-read of each row's primary sources (the pages' "Primary sources" lists stay as read on 2026-10-09); the Codex side of the cross-client table (0.161.0 there; the baseline
says rust-v0.162.1); the verification that each "bug fix" row has no dependent default beyond the rows named, which rests on a reading of the entry text and not on a run.

## Overturn conditions

- A paired same-task run showing an earlier subagent compaction window, or one model for all workflow agents, at quality parity and lower cost: the `context-compaction` or `model-effort-routing` default changes by its own record.
- A later release that changes the behaviour a default above depends on: its own delta.

## Sources

- `anthropics/claude-code@3deb873687379f0c199a69fdaccc65f0865f7a29` `CHANGELOG.md` L5-L83 (2.1.296), L65 and L1522 (the description cap and its knob), L87 (2.1.295 `onFailure: "block"`).
- The converged practice audit, group CPA-V-09 (the command center's ruling of 2026-10-12T13:38:12Z accepted the converged set as the work queue; a coordination record, cited by name and time).
- `catalogs/foundation/upstream-surface-baseline.json` (`versions.claude_code` 2.1.296), `.claude/skills/claude-native-practice/SKILL.md` (the currency rule), `docs/decisions/2026-10-09-claude-code-native-practice.md` (the skill's record).
