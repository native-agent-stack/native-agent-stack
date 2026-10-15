# The Claude native-practice skill moves from client 2.1.295 to 2.1.300, 2026-10-15

Status: decided by reading the releases' own entries; this record changes no default. It supersedes the unmerged record of #1053,
`docs/decisions/2026-10-12-practice-currency-2296.md` on branch `claude/cc-native-practice-currency-2296-20261012` at `213a9b4d8`,
which brought the skill to 2.1.296 only. The command center's ruling of 2026-10-15 marked #1053 superseded and asked for one currency
change from 2.1.295 to 2.1.300 that carries its delta; its 2.1.296 assignments are carried below at their new line numbers.

## Context

- `claude --version` printed `2.1.300 (Claude Code)` on 2026-10-15. The pages and `slots.json` said 2.1.295, checked 2026-10-09.
- `catalogs/foundation/upstream-surface-baseline.json` (`versions.claude_code`) still says 2.1.296 on main; #1155 (open) re-baselines it
  at 2.1.300. Until it lands, the stamp follows the installed client, and the test takes the newer of the two.
- The new-host install pin (`adoption/pins-linux-x86_64.json`) is a minimum version (2.1.295 here; #1128, open, raises it to 2.1.300)
  and is not touched.
- The skill's rule (`SKILL.md` step 2): when the installed client is newer than a page's version, read the CHANGELOG entries between
  the two for that slot's area, and treat a row as current only if none changes the behaviour its default depends on.

## The source

`anthropics/claude-code@94506ff0d3bd9185f1752da36e968775021fb48f` `CHANGELOG.md`, sha256
`8c6fdbbd692bd9b2e108e9946948aa77200b6c8ffec4f807ea9c8cee92545139` (fetched 2026-10-15 with
`gh api "repos/anthropics/claude-code/contents/CHANGELOG.md?ref=94506ff0d3bd9185f1752da36e968775021fb48f" -H "Accept: application/vnd.github.raw"`).
Its sections: 2.1.300 at L3 (entries L5-L92), 2.1.299 at L94 (entries L96-L285), 2.1.296 at L287 (entries L289-L367). There is no
2.1.297 or 2.1.298 section, so those versions have no entries. 357 entries in all, every one a line of its own.

#1053 read the same 2.1.296 section at `anthropics/claude-code@3deb873687379f0c199a69fdaccc65f0865f7a29` (sha256
`0383b383e05c30b7592c512ea3356104cbc3a799d028d36204033175ff256a51`), lines 5-83. From its line 3 on, that file equals this one 284 lines
lower, byte for byte, so #1053's line N is line N+284 here: its L6, L7, L59 and L65 are L290, L291, L343 and L349, the description-cap
knob L1522 is L1806, and the 2.1.295 `onFailure: "block"` entry L87 is L371. The evidence strings below cite this file as
`CHANGELOG@v2.1.300 L<n>`, with the entry's own version first in the parentheses.

## Categories

Each entry has exactly one category, the line #1053 drew:

- **Touches a slot:** an added or changed behaviour, knob or limit inside a row's mechanism that the row needs a note for to stay
  complete, including a change that meets the row's own overturn condition. Where no open pull request changes the row, it gains the
  entry as evidence and a note here; where one does, the entry is listed as an overlap and not applied.
- **Adjacent:** bears on a fact, an alternative or a rejection a named row states, without the row needing new text. Rows unchanged.
- **No slot, pure bug fix:** restores documented behaviour that no row's default, route or notes depend on.
- **No slot, out of scope:** a surface this host does not use (mods, cloud and Cowork sessions, Remote Control, Claude Desktop and the
  Claude apps gateway, Claude Tag, Code Review, self-hosted runners, the VS Code extension, Windows and macOS), display and input of
  the interactive terminal, or an option in an area no row covers.

## Counts

| Version | Section | Entries | Touches a slot | Adjacent | No slot: pure bug fix | No slot: out of scope |
| --- | --- | --- | --- | --- | --- | --- |
| 2.1.300 | L5-L92 | 88 | 4 | 5 | 17 | 62 |
| 2.1.299 | L96-L285 | 190 | 11 | 27 | 37 | 115 |
| 2.1.298 | none | 0 | 0 | 0 | 0 | 0 |
| 2.1.297 | none | 0 | 0 | 0 | 0 | 0 |
| 2.1.296 | L289-L367 | 79 | 4 | 4 | 17 | 54 |
| All | | 357 | 19 | 36 | 71 | 231 |

Of the 19 entries that touch a slot, 13 are applied to six rows here and 6 touch only rows that open pull requests change (see Overlaps).

## The delta

| Lines | Version | Category | Slots | What, and why |
| --- | --- | --- | --- | --- |
| 65 | 2.1.300 | touches | `background-workflows` | A background session resumes a carried workflow through the Workflow tool's approval instead of running it from the handoff file. It meets the row's overturn condition (Workflow resume); the default stands; evidence, a note, and a proposed route addition below |
| 66 | 2.1.300 | touches | `checkpoints-rewind` | Local transcripts also record each API request's system prompt, tools and parameters. The row's retention note covers what transcripts keep; evidence and a note |
| 69 | 2.1.300 | touches | `hooks` | `updatedInput` from PreToolUse and PermissionRequest hooks is validated like Claude's own input. The template's rewriting hook, `rtk hook claude` (rtk 0.51.0), returned only Bash input keys for a sample call (measured 2026-10-15, not in a session); evidence and a note |
| 6 | 2.1.300 | touches | `usage-cost-monitoring` (overlap #1158) | The OpenTelemetry `api_request` event gains `cache_creation_5m_tokens` and `cache_creation_1h_tokens`. The usage row reads those events; listed for #1158, not applied. `prompt-caching` is adjacent: the split makes its route's TTL buckets observable from the collector, not measured here |
| 10 | 2.1.300 | adjacent | `usage-cost-monitoring` | GenAI semantic-convention attributes on trace spans; the row's default exports metrics and events, not traces |
| 22 | 2.1.300 | adjacent | `mcp-config-tool-search` | A fix for `ENABLE_TOOL_SEARCH=auto` turning off mid-conversation; the row does not set `auto` (it rejects `auto:N` and routes `true`) |
| 32 | 2.1.300 | adjacent | `hooks` | Agent hooks honour their `model`, and an unavailable model now falls back to the caller's instead of allowing the action; the row already rejects prompt and agent hooks as guards |
| 33 | 2.1.300 | adjacent | `worktrees` | `--worktree` could start from the wrong commit when a tag or branch was named like a commit ID; it bears on the exact base of the row's `--worktree` alternatives, whose M49 probe is owed |
| 60 | 2.1.300 | adjacent | `headless-sdk` | Exit force-kills background commands still running 1.5 seconds after being stopped; no route relies on a background command outliving its session |
| 14, 15, 17, 19, 26, 27, 28, 35, 37, 40, 41, 42, 44, 45, 47, 48, 50 | 2.1.300 | no slot: pure bug fix | none | The `/autocompact` warning, SessionEnd hooks at exit, `claude agents` pull-request status, `/tasks`, transcript writes after a crash or with U+2028 and U+2029, plugin worktree hooks under `--worktree`, scratchpad paths, `--worktree` in a bare repository's worktree, an MCP input-schema refusal, headless resume after a compaction (two entries), MCP tools after a compaction, polling a background command, `claude daemon stop` (two entries), deferred tools on resume. No row depends on the fixed behaviour |
| 5, 7, 8, 11, 12, 30, 31, 39, 56 | 2.1.300 | no slot: out of scope | none | The mods API and the plugin-authoring skill's mod sharing: no slot covers mods, and `hooks` rejects plugin mods as guards |
| 9 | 2.1.300 | no slot: out of scope | none | `/advisor` on Claude Platform on AWS; the clause after the semicolon describes that platform, which this host does not use |
| 13, 18, 49, 52, 53, 55, 68 | 2.1.300 | no slot: out of scope | none | Cloud and Cowork sessions |
| 24, 36, 43, 70 | 2.1.300 | no slot: out of scope | none | Remote Control and Claude Desktop's diff view |
| 59, 61, 62 | 2.1.300 | no slot: out of scope | none | Claude Desktop, `claude gateway` and host-managed providers |
| 23 | 2.1.300 | no slot: out of scope | none | Organization login policy (`forceLoginOrgUUID`) |
| 25, 58 | 2.1.300 | no slot: out of scope | none | Artifacts |
| 29, 34 | 2.1.300 | no slot: out of scope | none | git's reftable ref storage; this repository uses the files backend (`git rev-parse --show-ref-format`) |
| 54 | 2.1.300 | no slot: out of scope | none | Self-hosted runners |
| 16, 20, 21, 51, 67 | 2.1.300 | no slot: out of scope | none | Help text, display and input of the interactive terminal |
| 38, 46, 57, 63, 64 | 2.1.300 | no slot: out of scope | none | Editor integrated terminals, TLS-inspecting proxies, Claude 3 models, Managed Agents in the `claude-api` skill, and gzip request bodies (`CLAUDE_CODE_GZIP_REQUEST_BODIES` keeps the unset disposition of `docs/decisions/2026-10-06-harness-context-budget-refresh.md`) |
| 71-82 | 2.1.300 | no slot: out of scope | none | [VSCode] |
| 83, 84 | 2.1.300 | no slot: out of scope | none | [Cloud sessions] |
| 85 | 2.1.300 | no slot: out of scope | none | [Remote Control] |
| 86-90 | 2.1.300 | no slot: out of scope | none | [Claude Tag] |
| 91, 92 | 2.1.300 | no slot: out of scope | none | [Code Review] |
| 97, 98 | 2.1.299 | touches | `context-compaction` | Idle compaction in the terminal (a conversation of 200K or more tokens idle for about 54 minutes is compacted before its one-hour cache expires), `CLAUDE_CODE_IDLE_COMPACT_MIN_TOKENS` and `idleCompaction: false`. It meets the row's overturn condition (a release changes compaction); neither knob is set on the host or the template (checked 2026-10-15); the default stands; evidence, a note, and a proposed route addition below |
| 245 | 2.1.299 | touches | `background-workflows` | A value a workflow script hands back may nest at most 28,000 levels (100,000 before), refused with an error. It meets the row's overturn condition (Workflow limits); the route does not rely on the depth; evidence and a note |
| 253 | 2.1.299 | touches | `settings-permissions` | An MCP allow rule reaches only the server it names. It meets the row's overturn condition (rule evaluation); every `mcp__` rule in the host's user settings and the repository's settings files names a whole tool (checked 2026-10-15); evidence and a note |
| 257 | 2.1.299 | touches | `mcp-config-tool-search` | Anthropic's first-party MCP servers at api.anthropic.com reach Claude with descriptions and instructions uncut, an exception to the 4,096-character cap of L349; evidence and a note |
| 262, 263 | 2.1.299 | touches | `hooks` | `UserPromptSubmit` hooks run before a skill or custom command expands, and a skill's own `UserPromptSubmit` hook first sees the prompt after the invoking one. The template's only `UserPromptSubmit` hook resets a counter and never blocks; alternative 2 (skill-scoped hooks) is affected; evidence and a note |
| 129, 134 | 2.1.299 | touches | `sandbox` (overlap #1129, #1160) | Sandboxed commands on WSL2 failing to create `/mnt/c/Program Files/ClaudeCode`, and an empty `.config.json` a sandboxed command left in the config directory: fixes of the vendor sandbox's side effects on this kind of host, the class #1129 records in the row's notes. Listed, not applied |
| 171 | 2.1.299 | touches | `headless-sdk` (overlap #1157) | `claude -p` named nothing when a settings file failed validation; text-output runs now list the file and the invalid entry on stderr. The route carries the deny list and guard hooks through `--settings`, and the entry names text-output runs only. Listed, not applied |
| 254 | 2.1.299 | touches | `subagent-definitions` (overlap #1142) | Agent `tools:` lists take only the named MCP server's tools. The route carries each role's `tools` allowlist; the 22 definitions in `.claude/agents` and `adoption/agents/claude` name tools, not bare servers (checked 2026-10-15). Listed, not applied |
| 104 | 2.1.299 | adjacent | `model-effort-routing` | `/effort` and `/fast` in agent view set what new background sessions start with; lanes launch with flags |
| 106 | 2.1.299 | adjacent | `settings-permissions` | A one-time note when plan mode will not ask before most edits because bypass permissions is available, the host's standing mode |
| 112 | 2.1.299 | adjacent | `usage-cost-monitoring` | `/usage` warnings for max effort, workflows, always-on context and large tool results, in the row's interactive checks |
| 114 | 2.1.299 | adjacent | `context-compaction` | A gateway-specific model name behind a custom base URL ended in a failed compaction near 200K tokens: the case alternative 2 (a per-model `/autocompact` window behind a 200K gateway) works around |
| 122, 202, 203, 236 | 2.1.299 | adjacent | `sandbox` | Sandbox fixes: writes into a `--plugin-dir` folder, glob parsing of `denyRead` and `allowRead`, re-checks after a symlink swap, and Esc while wildcard read rules expand. They harden the route's sandbox, whose M1 arms are owed |
| 130 | 2.1.299 | adjacent | `loops-completion` | ScheduleWakeup did not fire during a background task in Agent SDK, IDE and Remote Control sessions; the self-paced `/loop` default runs in the terminal |
| 155 | 2.1.299 | adjacent | `usage-cost-monitoring`; `statusline` | `/usage`, the limit warning and the status line could show more than 100% used; the row's alternative (native `/usage` and the status line) reads correctly again |
| 160 | 2.1.299 | adjacent | `settings-permissions` | Deny and ask rules for an MCP server whose normalized name contains `__` did not apply; no server the repository registers has such a name (checked 2026-10-15) |
| 165, 192 | 2.1.299 | adjacent | `config-managers` | A third-party base URL's key was sent with Anthropic's flag and startup requests (no third-party base URL is configured on the host or the template), and `forceLoginMethod` from MDM or a managed file was hidden by server-managed settings (managed scope, so the user-settings question in the row's note stays open) |
| 174, 211 | 2.1.299 | adjacent | `mcp-shared-servers` | HTTP connections hung on a reply body that never ended, and OAuth sign-in skipped `headers` and `headersHelper`: fixes on the trial's transport and on its admission gate's authentication path |
| 197 | 2.1.299 | adjacent | `scheduled-tasks`; `loops-completion` | Scheduled tasks and loops fired again in the repeated hour when daylight saving time ends; the durable route is systemd |
| 204 | 2.1.299 | adjacent | `worktrees` | The isolation guard of worktree-isolated sessions accepted some awk programs: a fix in the native checks the route names |
| 217 | 2.1.299 | adjacent | `planning-persistence` | Plan mode ran a write that a PreToolUse hook allowed; native plan mode holds the plan again |
| 219 | 2.1.299 | adjacent | `agent-teams` | `SendMessage` could not find a subagent by name after a restart, and a name given before the last compaction still needs the agent ID |
| 235 | 2.1.299 | adjacent | `checkpoints-rewind` | An @-mentioned PDF's bytes are no longer kept in the transcript: less for the retention window to keep |
| 239, 249 | 2.1.299 | adjacent | `skills-library`; `commands` | The Skill tool suggests a skill's listed name for a wrong `anthropic-skills:` prefix, and skill and command names with hidden characters, `<` or `>` are no longer offered; the 37 skill names here are plain ASCII (checked 2026-10-15) |
| 240 | 2.1.299 | adjacent | `context-compaction`; `skills-library` | `/reload-skills` re-sends the full skill list, the way to get skills back after a compaction; the route's SessionStart(compact) re-injection is where open #1109 adds a hook for it |
| 244 | 2.1.299 | adjacent | `background-workflows` | Background agent notifications say when an agent waits on its own work, got a message too late, or hit a usage limit (alternative 2, background subagents) |
| 246 | 2.1.299 | adjacent | `hooks` | Plugin hooks fail closed when they cannot be handed an action or hand back the answer; no guard here is a plugin hook, and the row rejects plugin mods as guards |
| 251 | 2.1.299 | adjacent | `model-effort-routing` | WebFetch page reads pick their effort as web searches do; no route sets it |
| 265 | 2.1.299 | adjacent | `pr-review-pre-cue` | `/ultrareview` upload errors no longer suggest `git add .`, which could stage untracked files such as `.env`; the row's ultrareview route |
| 120, 123, 124, 125, 127, 135, 136, 137, 138, 142, 148, 150, 161, 162, 163, 164, 168, 169, 175, 176, 177, 180, 183, 188, 193, 195, 196, 199, 200, 205, 206, 207, 210, 218, 220, 221, 223 | 2.1.299 | no slot: pure bug fix | none | A teammate's task description, debug-log memory (two entries), rm prompts on `-c` scripts, `.mcp.json` checks, `/sandbox` saves, auto mode after a model switch, MCP servers named `constructor` (two entries), document blocks, streams behind a custom base URL, `enabledMcpjsonServers` strings, images (three entries), `plugin_loaded` telemetry, the 2.1.296 double run of an approved tool call on resume, scheduled-task minutes, MCP policy checks (two entries), `/reload-plugins`, bare-mode notices, `/config` notifications, stream-json queued prompts, `--bare` and `constructor`, `verbatimPrompts`, safe mode in woken background sessions, MCP double runs on reconnect, `/btw` cancellation, `--background` parsing (two entries), a command's embedded shell line, Ultracode in delivered turns, background subagent reports, silent cut-offs after a non-streaming fallback, file encodings, resumed finished turns. No row depends on the fixed behaviour |
| 96, 261 | 2.1.299 | no slot: out of scope | none | Areas no row covers: `CLAUDE_CODE_DISABLE_FILE_MENTIONS` (a new option no row selects) and a timeout for `/btw` in non-interactive sessions |
| 99, 100, 101, 103, 107, 110, 111, 115, 117, 118, 131, 145, 149, 151, 153, 154, 166, 167, 170, 182, 190, 213, 214, 215, 216, 227, 234, 238, 250, 252, 264 | 2.1.299 | no slot: out of scope | none | The mods API, `claude plugin test` and `claude plugin eval`, and the plugin-authoring skill |
| 102, 189, 209, 231, 232 | 2.1.299 | no slot: out of scope | none | Self-hosted runners |
| 108, 109, 146 | 2.1.299 | no slot: out of scope | none | The Claude apps gateway and Claude Desktop |
| 113, 116, 119, 141, 157, 159, 184, 185, 187, 222, 233, 247, 248, 255, 256, 258 | 2.1.299 | no slot: out of scope | none | Cloud, Cowork and remote sessions, and Anthropic-hosted connectors |
| 121, 132, 133, 152, 181, 194, 224, 225, 226 | 2.1.299 | no slot: out of scope | none | Remote Control |
| 140, 212, 243 | 2.1.299 | no slot: out of scope | none | Artifacts |
| 143 | 2.1.299 | no slot: out of scope | none | Claude in Chrome |
| 147, 173 | 2.1.299 | no slot: out of scope | none | Managed settings and organization policy; `settings-permissions` rejects managed settings on this host |
| 139 | 2.1.299 | no slot: out of scope | none | Plugins synced from claude.ai |
| 201, 228, 229, 230 | 2.1.299 | no slot: out of scope | none | macOS and Windows |
| 208 | 2.1.299 | no slot: out of scope | none | git's reftable ref storage, not used here |
| 105, 126, 128, 144, 156, 158, 172, 178, 179, 186, 191, 198, 237, 241, 242, 259, 260, 266 | 2.1.299 | no slot: out of scope | none | Display, input and message wording of the interactive terminal, including the resume line printed at exit and worktree-creation errors |
| 267-271 | 2.1.299 | no slot: out of scope | none | [VSCode] |
| 272-277 | 2.1.299 | no slot: out of scope | none | [Cloud sessions] |
| 278 | 2.1.299 | no slot: out of scope | none | [Remote Control] |
| 279-284 | 2.1.299 | no slot: out of scope | none | [Claude Tag] |
| 285 | 2.1.299 | no slot: out of scope | none | [Code Review] |
| 290 | 2.1.296 | touches | `context-compaction`; `subagent-definitions` (overlap #1142) | `autoCompactWindow` in subagent frontmatter and `--agents` definitions (#1053's L6). No definition of ours sets it (checked 2026-10-15) and no paired run supports an earlier window: evidence and a note on `context-compaction`; listed for #1142 |
| 291 | 2.1.296 | touches | `background-workflows`; `model-effort-routing` (overlap #1147) | `CLAUDE_CODE_WORKFLOW_SUBAGENT_MODEL` (#1053's L7), unset in the host's settings and the template: evidence and a note on `background-workflows`; #1147's route already names the variable for `model-effort-routing` |
| 343 | 2.1.296 | touches | `subagent-definitions` (overlap #1142) | `--debug` names unrecognized frontmatter fields of custom agent files (#1053's L59); listed for #1142 |
| 349 | 2.1.296 | touches | `mcp-config-tool-search` | The default limit on MCP tool descriptions and server instructions is 4,096 characters, was 2,048 (#1053's L65); the knob `CLAUDE_CODE_MAX_MCP_DESCRIPTION_LENGTH` (L1806) stays unset; evidence and a note |
| 297 | 2.1.296 | adjacent | `headless-sdk` | Headless sessions no longer start a folder's MCP server that was switched off for it (#1053's L13) |
| 299 | 2.1.296 | adjacent | `config-managers` | The managed-settings `forceLoginMethod: gateway` regression (#1053's L15): managed scope, so it does not settle the user-settings scope the row's note calls unconfirmed |
| 345 | 2.1.296 | adjacent | `hooks` | `--debug` logs command hooks with their command, plugin, outcome and duration (#1053's L61): a way to find a slow hook |
| 347 | 2.1.296 | adjacent | `usage-cost-monitoring` | `/cost` prices Sonnet 5.5 cache reads at $0.10 per million tokens, was $0.20 (#1053's L63): client-reported costs before and after 2.1.296 differ on that part; the row already calls the counters estimates |
| 295, 296, 302, 303, 304, 307, 308, 311, 318, 319, 320, 323, 331, 332, 333, 334, 346 | 2.1.296 | no slot: pure bug fix | none | #1053's bug fixes: managed-settings hooks, resumed subagents, altered hook output, secret redaction, an interrupt in a `UserPromptSubmit` hook, plugin SessionStart hooks, workflow nesting and CRLF, interrupted-turn resume, `BASH_ARGV0` permission checks, non-UTF-8 edits, OpenTelemetry `git_commit_id`, transcript garbage collection and `claude purge` |
| 292, 294 | 2.1.296 | no slot: out of scope | none | New options no row selects: `CLAUDE_CODE_OVERLOADED_RETRY_MAX_DELAY_MS` and the Read tool's `allow_large` |
| 321, 322, 350 | 2.1.296 | no slot: out of scope | none | The `←` key moving a session to the background: an interactive key; the background routes are `claude --bg` and the supervisor |
| 293, 312, 313, 314, 315, 316, 328, 329, 330 | 2.1.296 | no slot: out of scope | none | Plugin and marketplace machinery, mods and skills synced from claude.ai, relied on no further than the installed plugins |
| 289, 298, 300, 301, 341, 342 | 2.1.296 | no slot: out of scope | none | The Claude apps gateway, `--teleport` and token counts behind gateways |
| 309, 310, 317, 325, 326, 327, 351-367 | 2.1.296 | no slot: out of scope | none | Self-hosted runners, cloud sessions, Code Review, Claude Tag and the VS Code extension |
| 305, 306, 324, 335, 336, 337, 338, 339, 340, 344, 348 | 2.1.296 | no slot: out of scope | none | Terminal and display fixes, Windows and PowerShell fixes, auto mode's display and the bundled dataviz skill |

## Rows changed here

| Row | Page | Entries |
| --- | --- | --- |
| `context-compaction` | `token-efficiency.md` | L290, L97, L98 |
| `background-workflows` | `workers.md` | L291, L245, L65 |
| `mcp-config-tool-search` | `mcp-surfaces.md` | L349 (and the knob at L1806), L257 |
| `hooks` | `native-clients.md` | L262, L263, L69 |
| `settings-permissions` | `native-clients.md` | L253 |
| `checkpoints-rewind` | `native-clients.md` | L66 |

Each gains the entries as `evidence` items and a sentence or two at the end of its `notes`, the same text in `slots.json` and on its
layer page. No default, alternative, rejection or overturn condition changes; two routes gain the additions the command
center accepted (below).

## Route additions, accepted

No entry overturns a default. Two entries meet a row's overturn condition with a change the route did not describe. The route
text is the command center's to change: each was proposed here, and the command center's ruling of 2026-10-15T17:17Z accepted both,
with the two edits named below, after checking CHANGELOG@94506ff0 L65 and L97-L98. Both are applied to the rows:

1. **`context-compaction`, route addition** (2.1.299 L97, L98): name idle compaction among the automatic paths: in a terminal session
   a conversation of 200K or more tokens left idle for about 54 minutes is compacted before its one-hour cache expires, the native form
   of the Opus 5.5 long-context post's advice to compact before an idle gap. Keep `idleCompaction` and
   `CLAUDE_CODE_IDLE_COMPACT_MIN_TOKENS` unset (neither is set on the host or the template, checked 2026-10-15). The default stands.
   The ruling's edit: set `idleCompaction` false only in a session that must keep its exact context across an idle wait over about
   54 minutes (CC ruling 2026-10-14).
2. **`background-workflows`, route addition** (2.1.300 L65): a background session resumes a carried workflow through the Workflow
   tool's approval, not from the handoff file, so a carried run meets the same permission check as a launch. The default stands.
   The ruling's edit: whether a fenced `-p` run's launch-scoped `--allowedTools 'Workflow(<name>)'` also covers the carried run is an
   untested boundary, because the entry does not say; the route leaves it out and the notes label it.

The two other overturn conditions met, Workflow limits (2.1.299 L245) and MCP rule evaluation (2.1.299 L253), need no route change:
the re-checks are in the rows' notes.

## Overlaps with open pull requests

Rows that open pull requests change are not touched here. The entries that touch them, and the adjacent ones their authors may want,
are listed for those changes or a follow-up:

| Row | Open pull request | Touching entries, not applied | Adjacent entries |
| --- | --- | --- | --- |
| `subagent-definitions` | #1142 | L290, L343 (2.1.296), L254 (2.1.299); also #1053's re-measured drift note (2026-10-12), not carried | none |
| `model-effort-routing` | #1147 | L291 (2.1.296), which #1147's route already names | L104, L251 |
| `usage-cost-monitoring` | #1158 | L6 (2.1.300) | L10, L112, L155, L347 |
| `sandbox` | #1129, #1160 | L129, L134 (2.1.299) | L122, L202, L203, L236 |
| `headless-sdk` | #1157 | L171 (2.1.299) | L60, L297 |
| `agent-teams` | #1142 | none | L219 |
| `worktrees` | #1160 | none | L33, L204 |
| `scheduled-tasks` | #1158 | none | L197 |
| `loops-completion` | #1146 (merged after this change's base) | none | L130, L197 |
| `skills-library` | #1153 | none | L239, L240, L249 |
| `pr-review-pre-cue` | #1147 | none | L265 |
| `client-core` | #1128, #1129 | none | none |

`auto-memory` (#1149), `plugin-marketplaces` (#1147), `release-tracking` and `practice-references` (#1136) have no entry in either
column. Every page's stamp line changes here, including pages those pull requests edit; their hunks are elsewhere on the page. The
snapshot manifest's label and `manifests/evidence.json` change in all of them, so whichever lands second recomputes the label and
re-registers the files.

## Decision

1. **The pages and `slots.json` move to 2.1.300, checked 2026-10-15.** The `Client` stamp of every layer page, the `slots.md` index
   line and the Claude Code column header of the cross-client table change, and `client_version` and `checked_at` of `slots.json` with
   them. Mentions of 2.1.295 that are history stay: a measurement on 2.1.295, probes owed on it, a CHANGELOG cited at v2.1.295 and
   `onFailure: "block"` arriving in it.
2. **Six rows gain the entries that touch them** (above), with evidence and a note. The snapshot manifest's label
   (`evidence/artifacts/claude-native-practice-20261009/claude-native-slot-manifest.json`, `current_decision_source`) follows the new
   `slots.json`: its sha256 and the rows whose `evidence` now differs from the snapshot.
3. **Two route additions are applied** (above), as the command center accepted them.
4. **The overlaps are listed** (above), not applied. #1053's re-measured `subagent-definitions` drift note is left to #1142 or a
   follow-up, because #1142 changes that row.
5. **A test pins the version and the delta.** `tests/test_native_practice_currency.py`, ported from #1053, checks that `slots.json` and
   every page state the newer of the baseline's version and 2.1.300 with one checked date, that the table assigns every entry of the
   three sections exactly once with its version and one category, that the counts table matches it, and that each entry applied here is
   evidence on its row in `slots.json` and on its page.

## Alternatives

- **Bump the stamps only.** Rejected: the stamp says the rows were checked against the release, and 13 entries touch six free rows.
- **Change a default or a route on the strength of an entry.** Rejected: the route additions are the command center's, and
  `autoCompactWindow`, `CLAUDE_CODE_WORKFLOW_SUBAGENT_MODEL` and idle-compaction knobs are compaction and routing levers, each needing
  its own paired run before a default moves.
- **Edit the rows open pull requests change.** Rejected: it would collide with them; the overlaps are listed instead.
- **Keep #1053 and add a second change for 2.1.297-2.1.300.** Rejected by the command center's ruling of 2026-10-15: one currency
  change.

## What this does not cover

- The upstream-surface baseline's version (#1155) and the new-host install pin (#1128).
- Disposition rows in `catalogs/foundation/upstream-surface-dispositions.json` for `CLAUDE_CODE_IDLE_COMPACT_MIN_TOKENS`,
  `CLAUDE_CODE_DISABLE_FILE_MENTIONS`, `CLAUDE_CODE_STRICT_INLINE_SHELL_RM_PROMPT` and `CLAUDE_CODE_MAX_MCP_DESCRIPTION_LENGTH`, which
  it lacks (checked 2026-10-15): the surface watch's disposition pass, not this change.
- A re-read of each row's primary sources and of the docs pages (the pages' Primary sources lists stay as read on 2026-10-09); this
  delta rests on the CHANGELOG text and the repository and host checks named.
- The Codex column of the cross-client table (0.161.0 there).
- A re-run of the `hooks` row's fail-closed cases B, D, H and N on 2.1.300.
- Runs behind the pure-bug-fix and out-of-scope assignments: they rest on a reading of the entry text.

## Overturn conditions

- A paired same-task run showing an earlier subagent compaction window, one model for all workflow agents, or idle compaction off, at
  quality parity and lower cost: the `context-compaction` or `model-effort-routing` default changes by its own record.
- A later release that changes the behaviour a default above depends on: its own delta.

## Sources

- `anthropics/claude-code@94506ff0d3bd9185f1752da36e968775021fb48f` `CHANGELOG.md`
  (<https://github.com/anthropics/claude-code/blob/94506ff0d3bd9185f1752da36e968775021fb48f/CHANGELOG.md>, sha256
  `8c6fdbbd692bd9b2e108e9946948aa77200b6c8ffec4f807ea9c8cee92545139`): L3-L92 (2.1.300), L94-L285 (2.1.299), L287-L367 (2.1.296),
  L1806 (the description-cap knob), L371 (2.1.295 `onFailure: "block"`).
- `anthropics/claude-code@3deb873687379f0c199a69fdaccc65f0865f7a29` `CHANGELOG.md` (sha256
  `0383b383e05c30b7592c512ea3356104cbc3a799d028d36204033175ff256a51`), the file #1053 read.
- #1053 at `213a9b4d8`: `docs/decisions/2026-10-12-practice-currency-2296.md` and `tests/test_native_practice_currency.py`.
- The command center's ruling of 2026-10-15 (a coordination record, cited by name and date).
- Repository files: `catalogs/foundation/upstream-surface-baseline.json`, `catalogs/foundation/upstream-surface-dispositions.json`,
  `adoption/templates/claude.settings.template.json`, `adoption/hooks/claude/research-routing-guard.py`,
  `adoption/new-wsl/templates/claude.settings.additions.json`, `adoption/mcp/*.json`, `.claude/agents/*.md`,
  `adoption/agents/claude/*.md`, `.claude/skills/claude-native-practice/SKILL.md`, `adoption/pins-linux-x86_64.json`.
- Host checks on 2026-10-15, names and presence only: `claude --version` (2.1.300); the host's user settings (no idle-compaction,
  workflow-model, description-cap or tool-search key; 13 `mcp__` rules, each naming a tool); `rtk hook claude` on a sample Bash call
  (rtk 0.51.0); `git rev-parse --show-ref-format` (files).
