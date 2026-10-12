# Code-navigation MCP servers leave the Claude user-scope profile and load on demand, 2026-10-12

Status: decided by the command center's ruling on the E1 comparison (RULED at 2026-10-12T09:47:08Z) and its addendum 01 on deviation D3 (2026-10-12T17:10:08Z); private records `ruling-e1-code-navigation-outcome-20261012.md` and
`.addendum-01.md` under `coordination/command-center/research-cc-role-20261008/`. This record carries the
evidence and the change to the templates. The stored client configuration of the host, the vendor-installed hooks and the vendor-installed agent files are changed by the command center after this lands, with an install
receipt, never by this change (host steps below).

## Context

The Claude Code user-scope profile (`adoption/mcp/claude-user.json`, plus the new WSL distribution's `claude-user.mcp.additions.json`) registered the code-navigation servers `serena`, `socraticode`,
`codebase-memory-mcp`, `jcodemunch` and (in the additions) `semble` at user scope, so every session of the host started with their server instructions (each tells the model to use it first for code navigation) and
their tool names loaded. The Claude-family practice audit counted eight always-on instruction blocks of 8,103 characters with four competing "use me first" claims (CPA-C-007, CPA-V-36).

E1 (code navigation under worktree-per-task) asked which change makes those tools get used, correctly, in a per-task worktree session, at no loss of correctness and no gain in cost. Its record is private; the
configs and tools that run it are public (`blueprints/native-skill-practice/e-series/`, [decision record](2026-10-12-e-series-promptfoo-configs.md)). Twelve frozen questions of one repository (definition, call sites,
raise lines, callers), `claude-opus-5-5` at medium effort, client 2.1.296, a session in the worktree at the base commit or in a stale copy of the shared checkout:

| Result | Value |
| --- | --- |
| A code-navigation tool used where no directive was in the context | 0 of 288 runs |
| Carrying `serena`, `semble`, `codebase-memory-mcp` and `jcodemunch` together (A0b against A5, the arm with no server; 12 questions x 3 repeats) | median cost +14.6 percent (0.0716 against 0.0625 USD), median wall time +9 s (21 against 12), correct runs 32 against 34 |
| The Bash-aware nudge, `alwaysLoad` and the vendor reminder hooks as levers (no directive in context) | no change in use |
| The preregistered adoption rule (section 6: correct not fewer, cost at most 1.1 times, use on at least 70 percent of the questions) | every arm fails the use test: "correct non-use or no gain" |

Deviation D3 (found 2026-10-12, [decision record of the e-series change](2026-10-12-e-series-promptfoo-configs.md)): the arms that carried a paragraph in `AGENTS.md` never delivered it under the flag the runner used, so
"a directive in the instruction file does not change use" is withdrawn. The command center approved a corrected re-run of arms A1 and A3 the same day (the paragraph delivered through the local instruction file under the
same fence, delivery checked per arm by a pre-flight row, 72 runs one at a time, addendum 2 of the comparison's record); its result is in the next section.

## The corrected re-run of A1 and A3

Run 2026-10-12 from 18:48Z to 19:50Z through the promptfoo configuration of #1046 (head `38f4151aa`; promptfoo 0.124.0, client 2.1.296, the same fence as E1); the pre-flight row passed 5 of 5 before the first run and after the last
(19:53:04Z), so the paragraph reached A1 and A3 and no other arm. A1's paragraph is Serena's (`directives/serena.md`; the session starts in the worktree at the base commit), A3's tells a session started in a stale copy to pass the worktree's path to the tools that take one, semble and
codebase-memory-mcp (`directives/path.md`); each is the only content of `CLAUDE.local.md` in the session's tree.

| Arm | Runs | Correct | Used a code-navigation tool (questions of 12; runs) | Median cost (USD) | Median seconds | Median turns |
| --- | --- | --- | --- | --- | --- | --- |
| A0a, the runner's reference (no paragraph) | 36 | 31 | 0; 0 | 0.0742 | 21.0 | 4.0 |
| A0a, matched: the same configuration (addendum 3) | 36 | 25 | 0; 0 | 0.0784 | 14.7 | 4.0 |
| A1, Serena's paragraph | 36 | 34 | 12; 35 | 0.0917 | 22.2 | 5.0 |
| A3, the path paragraph | 36 | 20 | 2; 7 | 0.0930 | 18.4 | 4.5 |

Read by the preregistered rule (section 6 of the comparison's preregistration): A1 meets (iii) (use on 12 of 12 questions). The runner's A0a ran on another route (the parity cell found promptfoo costing +3.5 and +8.2 percent
over the runner on two questions), so (i) and (ii) are read against an A0a run through the same configuration: 36 runs from 20:04Z to 20:25Z, pre-flight 5 of 5 before and after (end gate 20:28:18Z), fixed in addendum 3 of
the comparison's record before the first run. Against it A1 meets (i) (34 correct against 25) and fails (ii): median cost 0.0917 against 0.0784 USD, a ratio of 1.170 against the limit of 1.10 (1.24 against the runner's A0a).
A3 fails (i) and (iii). The outcome fixed in advance for this case: the paragraph makes the tools get used, correctly, at a cost the rule does not allow; no default changes and the carrying-cost reading of FIX-3 stands. So
a delivered paragraph does change use: the claim withdrawn by addendum 01 is replaced by "Serena's paragraph makes the tools get used on single-symbol lookups, at a cost that (ii) does not allow".

A lead, not a result (our own measurement is one angle, A6, under the command center's multi-angle ruling of 2026-10-12, tool clock 20:31Z, `ruling-multi-angle-convergence-20261012.md`): the matched A0a is 6 correct answers below the runner's A0a (25 against 31: the "explain" questions 0 of 9 against 4 of 9, one each on
definition and call sites), its median cost is 5.7 percent above the runner's and none of its runs used a code-navigation tool, so the route check of addendum 3 reports no difference. A1's extra correct answers are
concentrated on the "explain" questions (7 of 9 against 0 of 9). A1's median time is 22.2 s against 14.7 s. The cost per correct answer favours A1: 0.0962 USD against 0.1105 USD for the matched A0a (total cost 3.271 and
2.763 USD). The rule above does not read cost per correct answer, and 36 runs per arm over 12 questions do not support more than a lead. It seeds one new preregistered comparison, with cost per correct answer as the primary
metric, stratified by question type, and the directive delivered only when the tools are loaded on demand; that comparison is written before any run and goes through the command center. This change does not wait for it.

This change does not adopt a directive arm: FIX-3 is the ruling, the paragraph is the only memory content of the session in that comparison (more salient than in production), and the production-like arm is not measured.

## Decision

1. **`serena`, `socraticode` and `codebase-memory-mcp` leave `adoption/mcp/claude-user.json`; `semble` leaves the distribution's `claude-user.mcp.additions.json`.** The shared template registers `ai-memory`, `headroom`, `qmd` and
   `jcodemunch`. `jcodemunch` stays: [the 2026-10-04 record](2026-10-04-new-wsl-jcodemunch-user-scope.md) reserves removing it, or narrowing its scope in the default, to the user's instruction, and the command center
   has ruled that its E1 ruling does not carry that instruction. If the user gives it before the first read of this change starts, it joins this commit on the command center's record; otherwise it is a follow-up.
2. **The five entries move unchanged into a new on-demand file, `adoption/mcp/claude-code-navigation.json`.** A session that needs them (cross-file refactors, impact analysis, graph questions) loads them for that
   session only: `claude --mcp-config "$(python3 tools/adoption/install_claude_profile.py --print-mcp-config)"`. The new `--print-mcp-config [TEMPLATE]` option renders the file's `${HOME}` and `${ECO_ROOT}`
   placeholders for the host and prints the JSON `claude --mcp-config` takes; it runs no step, registers nothing and writes nothing. A project that wants one of them every time registers it with
   `claude mcp add --scope local`, as for jCodeMunch (`adoption/bootstrap.md` step 4a). The Claude allow rules for semble's two tools stay in `claude.settings.additions.json`: inert while the server is not loaded.
3. **The token-lane carrier blocks are unchanged.** They name `serena`, `socraticode` and `codebase-memory-mcp` tools; the existing coverage test requires every server a carrier names to be registered or a sourced
   exception, so `CARRIER_EXCEPTIONS` of `tests/test_install_claude_profile.py` now lists the three, each with the phrase in `adoption/bootstrap.md` and in this record that says why. The blocks already say "if exposed"
   (main session) and load their tools by one `ToolSearch` call, which finds nothing for a server that is not loaded; shrinking their text is a follow-up that needs the handbook and the hook tests with it.
4. **The Codex templates are untouched**: E1 measured Claude Code sessions only.
5. **The always-on instruction blocks shrink with the servers.** The ruling's "the always-on instruction blocks shrink to match" is the servers' own instruction text: the session header of 2026-10-12 lists eight server blocks
   (agentsview, ai-memory, codebase-memory-mcp, grafana, jcodemunch, qmd, semble, serena), and five remain once the host steps are done (SocratiCode contributes none). The hook-injected carrier blocks of decision 3 are a
   different text and stay.
6. **Scope limit, stated where the change is read.** E1 tested single-symbol lookups in worktree sessions of one repository (Python symbols, medium effort). Other task classes, such as cross-file refactors and impact
   analysis, were not measured and keep the on-demand path. The carrying cost was measured for the four servers together (the share of each is unknown) and `socraticode` was not in the comparison (its index belongs to
   the shared checkout); its removal rests on the ruling and on the same mechanism (a use-me-first instruction block and tool names loaded for every session).

## The agents whose tools sit in the on-demand set

Subagents inherit the MCP tools of the session that spawns them ("Subagents inherit the built-in tools and MCP tools available in the main conversation, narrowed by two filters", https://code.claude.com/docs/en/sub-agents,
"Available tools", read 2026-10-12), and a `tools` list with at least one entry that resolves still launches ("If no entry in the list resolves to a tool, the subagent usually fails to launch", the same page, the `tools` field).
So in a session started with the on-demand file every agent below has its tools as before; in any other session the tool ids do not exist and each agent works with the tools it has.

| Agent | Where it comes from | Code-navigation tools it names | Without the on-demand file |
| --- | --- | --- | --- |
| `evidence-reviewer` | `adoption/agents/claude/` | 7 Serena, 4 SocratiCode | reads with Grep/Read/Glob; its first paragraph ("Before Serena navigation, read initial_instructions...") is conditional on navigating with Serena |
| `isolated-builder` | `adoption/agents/claude/` | 6 Serena, 3 SocratiCode | the same |
| `security-reviewer` | `adoption/agents/claude/` | 7 Serena, 4 SocratiCode | the same |
| `stack-researcher` | `adoption/agents/claude/` | 4 Serena | the same |
| `codebase-memory`, `codebase-memory-auditor`, `codebase-memory-scout` | vendor-installed on the host (`~/.claude/agents`), not in any template | `mcp__codebase-memory-mcp__*` (besides Read, Grep, Glob) | Read, Grep and Glob only; the graph questions they exist for go unserved (host step 3) |
| `semble-search` | vendor-installed on the host | none: Bash and Read, running the `semble` command line | unaffected |

Measured on the installed client (2.1.296, `haiku`, one run per arm, an empty directory, `--setting-sources local --strict-mcp-config`, a probe agent passed with `--agents` whose tools are `Read` and one `codebase-memory-mcp` tool):
with `--mcp-config` set to the `codebase-memory-mcp` entry of the printed config the subagent called the tool and returned its output (project list); without the option it launched, reported the tool absent and listed `Read`
(private record `research/cc-native-practice-20261009/fix-3-20261012/agent-probe/`). One run per arm: the catalog agents themselves, Serena and SocratiCode were not run.

The vendor's way to give an agent its own server is the `mcpServers` frontmatter field: "Inline servers defined here are connected when the subagent starts ... and disconnected when it finishes", and "to keep an MCP
server out of the main conversation entirely and avoid its tool descriptions consuming context there, define it inline here rather than in `.mcp.json`" (https://code.claude.com/docs/en/sub-agents, "Scope MCP
servers to a subagent", read 2026-10-12; in the client since 2.1.117 for a main-thread agent, `anthropics/claude-code@3deb8736` `CHANGELOG.md` L5601, with the subagent and `--strict-mcp-config` rules at 2.1.153,
L4783-L4784, and the folder-trust rule for project agent files at 2.1.238, L3138). It is not used for the four catalog agents: the server connects at every spawn of the agent, and these reviewers and builders are spawned
often, so each spawn would pay the start-up that E1 measured per session. It fits the three `codebase-memory` agents, whose only purpose is graph questions; that is a host edit of vendor-installed files (host step 3).

## Host steps (the command center's act after landing, with an install receipt; none is run here)

1. `claude mcp remove <name> -s user` for `serena`, `socraticode`, `codebase-memory-mcp` and `semble`, all four registered on the first host (the value-free report `tools/adoption/mcp_template_drift.py` with this change
   applied, run 2026-10-12, lists each as an unacknowledged LIVE-ONLY row and nothing else open; check with `claude mcp list` afterwards). Keep the live command lines first if they are wanted again: `serena` runs as
   `serena` from `PATH` (12 arguments), `socraticode` through `npx` (3 arguments; SocratiCode 1.16.0 according to [the reconciliation record](2026-10-12-mcp-template-live-reconciliation.md#values-that-differ)), `semble` and
   `codebase-memory-mcp` by their plain commands. Until then the report's four open rows are the pending step, so no acknowledgement row is added. Do `socraticode` last: see step 6.
2. CPA-V-36: the codebase-memory hooks the vendor installed in the host's settings (four SessionStart entries, SubagentStart, PreToolUse) and Serena's opt-in activate hook are absent from every template and inject text
   about tools that are no longer loaded; remove them with the servers or keep them on purpose.
3. The three `codebase-memory*` agent files: give each an inline `codebase-memory-mcp` entry under `mcpServers` (the entry of the on-demand file, rendered), or leave them to sessions that load the on-demand file.
4. The new WSL distribution's render no longer carries the four Claude pieces (`client-config-map.json` loses their entries); a rebuilt host gets the user-scope set above and the on-demand file as a template only.
5. `jcodemunch` stays registered until the user's instruction.
6. `socraticode`: the on-demand entry names `${ECO_ROOT}/bin/node` and `${ECO_ROOT}/bin/socraticode`, and the second does not exist on the first host; the live registration runs SocratiCode through `npx` (3 arguments,
   1.16.0 according to the reconciliation record). Before step 1 removes that registration, either keep it until the version owner's entry replaces the on-demand one, or accept that `socraticode` does not start on
   demand on this host until then. The entry is the version owner's to bump; E1 did not measure `socraticode`.

## What the on-demand entries do not do yet

They are the shared template's entries, as the installer registered them. The new WSL distribution's overrides for the registered entries (Serena by `serena` from the settings `PATH`, SocratiCode's pinned entry point and the host's
Qdrant and embedding endpoints) are not applied to them, and `new_wsl_client_config.py` renders no on-demand file. On the first host `${ECO_ROOT}/bin/serena`, `bin/codebase-memory-mcp` and `semble` exist; `${ECO_ROOT}/bin/socraticode`
does not (the live registration runs SocratiCode through `npx`), so the on-demand `socraticode` entry needs the version owner's entry before its first use here. Both are follow-ups, outside this change: E1 did not measure
`socraticode`, and the version owner decides its entry.

## Records this changes

- [2026-10-12-mcp-template-live-reconciliation.md](2026-10-12-mcp-template-live-reconciliation.md), decision 1: the code graph server keeps the vendor's key `codebase-memory-mcp` in the Codex template and in the on-demand file; the
  Claude user-scope template no longer carries it. Its acknowledged row for Claude `socraticode` (DIFFERS) is removed in this change, since the server is no longer rendered; the Codex rows stay.
- [2026-10-02-new-wsl-client-configuration.md](2026-10-02-new-wsl-client-configuration.md): the counts (399 pieces, 359 wired), the agents' gaps table (the four agents above) and an addendum.
- The 2026-09-30 sentence in `adoption/mcp/claude-user.json`, that the file registers every server the carrier blocks name except context-mode, no longer holds for `serena`, `socraticode` and `codebase-memory-mcp`: the file's own comment
  says so, and `CARRIER_EXCEPTIONS` records why that is allowed.

## Alternatives

- **Leave the profile as it is.** The measured cost of carrying the servers buys no answer on this task class, and the instruction blocks compete.
- **Register them but disabled.** Claude Code can disable a registered server per project (`/mcp disable`), but that is state in the host's `~/.claude.json`, not something `claude mcp add` or a template sets.
- **`alwaysLoad`.** It loads every tool of a server upfront: the opposite direction, and E1's A4 arm showed no change in use.
- **Agent-scoped inline servers for the four catalog agents.** Above: a connection at every spawn.
- **One removal for all five including `jcodemunch`.** Reserved to the user (decision 1).
- **Rewrite the carrier blocks now.** They are checksum-pinned hook assets with a handbook source and their own tests; the blocks degrade to a no-op for a server that is not loaded.

## What this does not cover

Cross-file refactors, impact analysis and graph questions (kept on demand, unmeasured); other repositories and languages; Codex lanes; the directive lever beyond Serena's paragraph in an otherwise empty memory file; the share of each server in the
measured cost; `socraticode` as an arm; the carrier text; the production-like arm (a paragraph among the repository's other instructions).

## Overturn conditions

- A comparison on cross-file or impact tasks in which the servers' absence costs correctness: restore them for that task class (a profile, or the user-scope set).
- A larger repeat, or a production-like arm (the repository's own instructions around the paragraph), in which Serena's paragraph keeps (i) and (iii) and brings the median cost to at most 1.1 times the matched A0a's (1.170 at
  36 runs per arm): Serena with a directive then meets the three criteria for single-symbol lookups, and the always-on question reopens for that task class with the directive as the lever.
- The user's instruction on `jcodemunch` (2026-10-04 record), either way.

## Sources

- E1 comparison records (private, cc-native-practice): `E1-PREREGISTRATION.md`, addenda 1 and 2, `delivery-probe-20261012/RESULT.md`; the command center's ruling and addendum 01 of 2026-10-12.
- `docs/decisions/2026-10-12-e-series-promptfoo-configs.md` (the configs and D3), `docs/decisions/2026-10-04-new-wsl-jcodemunch-user-scope.md` (the overturn clause), `docs/decisions/2026-09-23-claude-user-profile.md`
  (the 2026-09-25 precedent: jCodeMunch registered per project because its instruction loaded into every session).
- `claude --help` of the installed client 2.1.296: `--mcp-config <configs...>  Load MCP servers from JSON files or strings (space-separated)`, which is what `--print-mcp-config` feeds; read 2026-10-12.
- https://code.claude.com/docs/en/sub-agents ("Scope MCP servers to a subagent", "Trust required for inline MCP servers"), read 2026-10-12; `anthropics/claude-code@3deb873687379f0c199a69fdaccc65f0865f7a29`
  `CHANGELOG.md` L5601, L4783-L4784, L3138.
