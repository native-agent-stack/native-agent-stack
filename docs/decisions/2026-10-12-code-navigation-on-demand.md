# Code-navigation MCP servers leave the Claude user-scope profile and load on demand, 2026-10-12

Status: decided by the command center's ruling on the E1 comparison (RULED at 2026-10-12T09:47:08Z) and its addendum 01 on deviation D3 (2026-10-12T17:10:08Z); private records `ruling-e1-code-navigation-outcome-20261012.md` and
`.addendum-01.md` under `coordination/command-center/research-cc-role-20261008/`. This record carries the
evidence and the change to the templates. The stored client configuration of the host, the vendor-installed hooks and the vendor-installed agent files are changed by the command center after this lands, with an install
receipt, never by this change (the host handoff below).

## Context

The Claude Code user-scope profile (`adoption/mcp/claude-user.json`, plus the new WSL distribution's `claude-user.mcp.additions.json`) registered the code-navigation servers `serena`, `socraticode`,
`codebase-memory-mcp`, `jcodemunch` and (in the additions) `semble` at user scope, so every session of the host started with their tool names loaded and, for `serena`, `codebase-memory-mcp` and `semble`, with a server instruction block that tells the model to use that server first for code
navigation (SocratiCode sends no instruction block: its server is constructed with a name, a version and `capabilities` and no `instructions`, `giancarloerra/SocratiCode@2218f25153d0f3f4a76ee240a5643dbc873e80be`
`src/index.ts` L21-L31, the mirror's checkout at v1.14.0, and the same in the installed 1.15.0, `dist/index.js` L18-L28, which adds a `logging` capability; neither file mentions `instructions`). The Claude-family practice audit counted eight always-on instruction blocks of 8,103 characters with four competing "use me first" claims (CPA-C-007, CPA-V-36).

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
| A0a, matched: the same configuration (addendum 3) | 36 | 33 (25 as first graded) | 0; 0 | 0.0784 | 14.7 | 4.0 |
| A1, Serena's paragraph | 36 | 34 | 12; 35 | 0.0917 | 22.2 | 5.0 |
| A3, the path paragraph | 36 | 34 (20 as first graded) | 2; 7 | 0.0930 | 18.4 | 4.5 |

The correct counts are those of the grader after deviation D4 of [the e-series change](2026-10-12-e-series-promptfoo-configs.md): the first grading scored an answer wrong when it cited `<root>/trees/base/<file>` with the right lines (the
stale-start arms' prompt names that tree), because `norm` dropped only the private runner's `/wt/` and `/primary/` directories; the stored results were graded again with the root-aware `norm`, unchanged otherwise.

Read by the preregistered rule (section 6 of the comparison's preregistration): A1 meets (iii) (use on 12 of 12 questions). The runner's A0a ran on another route (the parity cell found promptfoo costing +3.5 and +8.2 percent
over the runner on two questions), so (i) and (ii) are read against an A0a run through the same configuration: 36 runs from 20:04Z to 20:25Z, pre-flight 5 of 5 before and after (end gate 20:28:18Z), fixed in addendum 3 of
the comparison's record before the first run. Against it A1 meets (i) (34 correct against 33; 34 against 25 as first graded) and fails (ii): median cost 0.0917 against 0.0784 USD, a ratio of 1.170 against the limit of 1.10 (1.24 against the runner's A0a).
A3 fails (iii) (use on 2 of 12 questions) and meets (i) (34 against 33). The outcome fixed in advance for this case: the paragraph makes the tools get used, correctly, at a cost the rule does not allow; no default changes and the carrying-cost reading of FIX-3 stands. So
a delivered paragraph does change use: the claim withdrawn by addendum 01 is replaced by "Serena's paragraph makes the tools get used on single-symbol lookups, at a cost that (ii) does not allow".

**Correction (deviation D4, found by the first full read of the e-series change, 2026-10-12).** An earlier version of this record read a lead into the first grading: the matched A0a 6 correct answers below the runner's
(25 against 31), the "explain" questions 0 of 9 for it against 7 of 9 for A1, and a lower cost per correct answer for A1 (0.0962 against 0.1105 USD). The three came from the path defect above. Graded again (`e1_decide.load_runs`
with the root-aware `norm`, the stored results unchanged), the matched A0a has 33 correct (explain 6 of 9), 2 above the runner's 31, so the route check of addendum 3 (a median cost more than 10 percent apart, or a code-navigation call in any run, is a route difference) finds none: the matched A0a's median cost is 0.0784 USD against the runner's
0.0742, 5.7 percent above, and no run used a tool, and its correct count, which is printed beside the check and is not part of it, is 33 against 31; A1 has
34 (explain 7 of 9, one answer apart); the cost per correct answer is 0.0837 USD for the matched A0a against 0.0962 USD for A1, and by question type A1 is higher on `def`, `refs` and `callers` and lower on `explain` (0.1266
against 0.1432), at n = 9 per cell. No lead remains, and the preregistered comparison the first reading seeded was withdrawn before any run (the command center's ruling to stop E1b, a coordination message sent after my report of the re-grade at 2026-10-12T22:42:49Z and recorded in the private addendum 4 of the E1 preregistration). Our own measurement
is one angle, A6, under the command center's multi-angle ruling of 2026-10-12 (tool clock 20:31Z, `ruling-multi-angle-convergence-20261012.md`): for this layer it reads "no measured benefit". The rule outcomes above stand.

This change does not adopt a directive arm: FIX-3 is the ruling, the paragraph is the only memory content of the session in that comparison (more salient than in production), and the production-like arm is not measured.

## Decision

1. **`serena`, `socraticode` and `codebase-memory-mcp` leave `adoption/mcp/claude-user.json`; `semble` leaves the distribution's `claude-user.mcp.additions.json`.** The shared template registers `ai-memory`, `headroom`, `qmd` and
   `jcodemunch`. `jcodemunch` stays: [the 2026-10-04 record](2026-10-04-new-wsl-jcodemunch-user-scope.md) reserves removing it, or narrowing its scope in the default, to the user's instruction, and the command center
   has ruled that its E1 ruling does not carry that instruction. If the user gives it before the first read of this change starts, it joins this commit on the command center's record; otherwise it is a follow-up.
2. **The four entries move into a new on-demand file, `adoption/mcp/claude-code-navigation.json`, with the values they had.** A session that needs them (cross-file refactors, impact analysis, graph questions) loads them for that
   session only: `claude --mcp-config "$(python3 tools/adoption/install_claude_profile.py --print-mcp-config)"`. The new `--print-mcp-config [TEMPLATE]` option renders the file's `${HOME}` and `${ECO_ROOT}`
   placeholders for the host and prints the JSON `claude --mcp-config` takes; it runs no step, registers nothing and writes nothing. Its error names the file it renders; before this change it always named `claude-user.json`
   (`tools/adoption/install_claude_profile.py` at `489b26328` L390, `MCP_TEMPLATE.name`). `--server NAME` (repeatable) prints only the named entries, because a server loaded by
   `--mcp-config` replaces a registered server of the same name for that session (measured below). A project that wants one of them every time registers it with
   `claude mcp add --scope local`, as for jCodeMunch (`adoption/bootstrap.md` step 4a). The Claude allow rules for semble's two tools stay in `claude.settings.additions.json`: inert while the server is not loaded.
   On a new WSL distribution host the file is rendered, not printed from the template: `new_wsl_client_config.py --render` writes `mcp-servers.on-demand.json` with the overrides the map gives each entry, as it renders the registered servers
   (Serena's command from the settings `PATH`, SocratiCode's pinned entry point under `tools/socraticode-1.15.0/` and the host's Qdrant and embedding endpoints), and `--print-mcp-config` prints that file. The template's own values
   (`${ECO_ROOT}/bin/socraticode`, the shared endpoints) are what every other host gets.
3. **The token-lane carrier blocks are unchanged.** They name `serena`, `socraticode` and `codebase-memory-mcp` tools; the existing coverage test requires every server a carrier names to be registered or a sourced
   exception, so `CARRIER_EXCEPTIONS` of `tests/test_install_claude_profile.py` now lists the three, each with the phrase in `adoption/bootstrap.md` and in this record that says why. The blocks already say "if exposed"
   (main session) and load their tools by one `ToolSearch` call, which finds nothing for a server that is not loaded; shrinking their text is a follow-up that needs the handbook and the hook tests with it.
4. **The Codex templates are untouched**: E1 measured Claude Code sessions only.
5. **The always-on instruction blocks shrink with the servers.** The ruling's "the always-on instruction blocks shrink to match" is the servers' own instruction text: the session header of 2026-10-12 lists eight server blocks
   (agentsview, ai-memory, codebase-memory-mcp, grafana, jcodemunch, qmd, semble, serena), and five remain once the host handoff is done (SocratiCode contributes none). The hook-injected carrier blocks of decision 3 are a
   different text and stay.
6. **Scope limit, stated where the change is read.** E1 tested single-symbol lookups in worktree sessions of one repository (Python symbols, medium effort). Other task classes, such as cross-file refactors and impact
   analysis, were not measured and keep the on-demand path. The carrying cost was measured for the four servers together (the share of each is unknown) and `socraticode` was not in the comparison (its index belongs to
   the shared checkout); its removal rests on the ruling and on the tool names and descriptions it loads into every session. It has no instruction block, so it was never one of the competing "use me first" claims.

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
| `codebase-memory`, `codebase-memory-auditor`, `codebase-memory-scout` | vendor-installed on the host (`~/.claude/agents`), not in any template | `mcp__codebase-memory-mcp__*` (besides Read, Grep, Glob) | Read, Grep and Glob only; the graph questions they exist for go unserved (handoff step 6) |
| `semble-search` | vendor-installed on the host | none: Bash and Read, running the `semble` command line | unaffected |

Measured on the installed client (2.1.296, `haiku`, one run per arm, an empty directory, `--setting-sources local --strict-mcp-config`, a probe agent passed with `--agents` whose tools are `Read` and one `codebase-memory-mcp` tool):
with `--mcp-config` set to the `codebase-memory-mcp` entry of the printed config the subagent called the tool and returned its output (project list); without the option it launched, reported the tool absent and listed `Read`
(private record `research/cc-native-practice-20261009/fix-3-20261012/agent-probe/`). One run per arm: the catalog agents themselves, Serena and SocratiCode were not run.

**A server loaded by `--mcp-config` replaces a registered server of the same name for that session.** `CHANGELOG.md` L7929 (2.0.30) says "Fixed `--mcp-config` flag to correctly override file-based MCP configurations"; measured on the
installed client (2.1.296, one run each, `haiku`, one turn, `--setting-sources user`, an empty directory, the init event's `mcp_servers`): without the option the host's registered `socraticode` is listed as pending (its connection had not
finished at the event; `claude mcp list` shows the registration connected), and with `--mcp-config` holding only the on-demand `socraticode` entry, whose `${ECO_ROOT}/bin/socraticode` is absent on this host, it is listed as failed.
Loading the shared template's SocratiCode entry therefore broke the working registration for that session; the rendered file carries the pinned entry point and the host's endpoints instead (`OnDemandRenderTests` starts the emitted
command in the distribution's layout, which has no `bin/socraticode`, with endpoints other than the shared ones, and shows the template's entry failing with MODULE_NOT_FOUND). `--server` stays for a host that wants a subset.

The vendor's way to give an agent its own server is the `mcpServers` frontmatter field: "Inline servers defined here are connected when the subagent starts ... and disconnected when it finishes", and "to keep an MCP
server out of the main conversation entirely and avoid its tool descriptions consuming context there, define it inline here rather than in `.mcp.json`" (https://code.claude.com/docs/en/sub-agents, "Scope MCP
servers to a subagent", read 2026-10-12; in the client since 2.1.117 for a main-thread agent, `anthropics/claude-code@3deb8736` `CHANGELOG.md` L5601, with the subagent and `--strict-mcp-config` rules at 2.1.153,
L4783-L4784, and the folder-trust rule for project agent files at 2.1.238, L3138). It is not used for the four catalog agents: the server connects at every spawn of the agent, and these reviewers and builders are spawned
often, so each spawn would pay the start-up that E1 measured per session. It fits the three `codebase-memory` agents, whose only purpose is graph questions; that is a host edit of vendor-installed files (handoff step 6).

## Host handoff (the command center's act after landing, with an install receipt; none is run here)

One order, with the recovery in it. The replacement is rendered and accepted while the live registrations still work, and they are removed only after it passes. Rerunning the profile installer is not a step: it visits only the
servers present in its input and never prunes a registration, so it cannot complete the removal (`install_claude_profile.py`, the `--only mcp` loop).

1. **Capture** each live registration as JSON into a private file (owner-readable, outside every repository; see Rollback): `serena` runs as `serena` from `PATH` (12 arguments), `socraticode` through `npx` (3 arguments;
   SocratiCode 1.16.0 according to [the reconciliation record](2026-10-12-mcp-template-live-reconciliation.md#values-that-differ)), `semble` and `codebase-memory-mcp` by their plain commands. The value-free report
   `tools/adoption/mcp_template_drift.py` with this change applied (run 2026-10-12) lists each as an unacknowledged LIVE-ONLY row and nothing else open; no acknowledgement row is added, so those four rows are the pending step.
2. **Render** the host's files with the command that rendered its registrations: `python3 tools/adoption/new_wsl_client_config.py --render --host <host> --out <dir>`. `<dir>/mcp-servers.on-demand.json` holds the four with the
   host's values. SocratiCode's entry is the distribution's pin (1.15.0, `tools/socraticode-1.15.0/lib/node_modules/socraticode/dist/index.js`, present on the first host), not the live registration's 1.16.0: bumping the pin
   is the version owner's change to the map, not this one.
3. **Accept** while the live registrations stand: start a session with `claude --strict-mcp-config --mcp-config "$(python3 tools/adoption/install_claude_profile.py --print-mcp-config <dir>/mcp-servers.on-demand.json)"`
   (`--strict-mcp-config`, so that no registration masks a failure) and see the four connected in `/mcp`, or call one tool of each. If any does not connect, stop: nothing has been changed.
4. **Remove** the live registrations: `claude mcp remove <name> -s user` for `serena`, `socraticode`, `codebase-memory-mcp` and `semble`; check with `claude mcp list` and with the drift report (no LIVE-ONLY row for them).
5. CPA-V-36: the codebase-memory hooks the vendor installed in the host's settings (four SessionStart entries, SubagentStart, PreToolUse) and Serena's opt-in activate hook are absent from every template and inject text
   about tools that are no longer loaded; remove them with the servers or keep them on purpose.
6. The three `codebase-memory*` agent files: give each an inline `codebase-memory-mcp` entry under `mcpServers` (the entry of the rendered on-demand file), or leave them to sessions that load the on-demand file.
7. `jcodemunch` stays registered until the user's instruction.
8. **Receipt**: record the outcome as the install receipt (value-free: the commands, their exit codes, the four servers connected in step 3, the drift report after step 4).
9. **Recovery**: before step 4 nothing has changed. After it, a registration is restored from its captured file (Rollback) and the drift report shows its row again.

## Rollback

- **Template path A, `git revert`:** revert the merge commit of this change and run `python3 tools/adoption/install_claude_profile.py --only mcp`, which registers the three servers the user-scope template held again
  (`serena`, `socraticode`, `codebase-memory-mcp`; a server already registered is reported as matching or left unchanged). It does not register `semble`: the shared template never held it, only the new WSL distribution's
  additions file did (`adoption/new-wsl/templates/claude-user.mcp.additions.json` at `489b26328`), which only `new_wsl_client_config.py` reads. On a distribution host the reverted tree gives `semble` back with the rest of
  the host's files: `python3 tools/adoption/new_wsl_client_config.py --render --host NAME --out DIR`, then `python3 tools/adoption/install_claude_profile.py --only mcp --mcp-template DIR/mcp-servers.json` (or
  `new_wsl_client_config.py --apply --host NAME`, whose `claude-mcp` step does the same). On any other host `semble` was not registered before this change, so there is nothing to restore.
- **Template path B, without reverting:** `python3 tools/adoption/install_claude_profile.py --only mcp --mcp-template adoption/mcp/claude-code-navigation.json` registers all four on-demand entries at user scope with the
  template's values; on a distribution host `--mcp-template DIR/mcp-servers.on-demand.json` (the file `--render` writes) registers the four with the host's values.
- Both paths restore portable or rendered values, not this host's live ones (`serena` run from `PATH`, SocratiCode through `npx`). `RollbackRoutesTests` and `RollbackOnADistributionHostTests` plan each route with `--dry-run`
  and compare the servers it would register with the sets above.
- **Live values:** before the removal (handoff step 1), capture each server's registration as JSON into a private file that is not in any repository and is readable by the owner only (it can hold environment values):
  `jq '.mcpServers["serena"]' ~/.claude.json`, once per name. Restore one with `claude mcp add-json --scope user serena "$(cat <that file>)"` (`add-json` is in `CHANGELOG.md` L8759 and answers
  `claude mcp add-json --help` on 2.1.296). `claude mcp get <name>` prints the same values as text, which `add-json` does not take.

## What the on-demand file does and does not carry

On a new WSL distribution host it carries the map's overrides (step 2 of the handoff); on any other host it carries the shared template's values: for `serena`, `socraticode` and `codebase-memory-mcp` the values they had in
the user-scope template, and for `semble`, which the shared template never held (only the distribution registered it), the values the distribution's additions file gave it, so on another host the file offers a server that was
not registered there before. `${ECO_ROOT}/bin/serena`, `bin/codebase-memory-mcp` and the `semble` command exist on the first host, and `${ECO_ROOT}/bin/socraticode` does not on a host the install plan built, which is why the file
is rendered there. SocratiCode's version (the plan pins 1.15.0; the live registration runs 1.16.0 through `npx`) is the version owner's to bump; E1 did not measure `socraticode`.

Boundaries of the procedure above, so that none is read as more than it is:

- The printer's refusal is its exit status (1) and a message on standard error. A shell command substitution does not stop the outer command: `claude --mcp-config "$(...)"` runs with an empty argument when the printer refuses,
  so a script assigns the JSON and tests it first (`bootstrap.md`, step 4a).
- `new_wsl_client_config.py --apply` stages every rendered file in a temporary directory and installs and verifies the user-scope file only (`step_claude_mcp`, `step_verify`): it does not persist or accept the on-demand file,
  so the separate render and the four-server acceptance of the handoff stay necessary.
- The drift report (`mcp_template_drift.py`) and the runtime-profile reader (`runtime_profiles.py`) read user-scope registrations only; a server loaded for one session appears in neither.
- Re-running the profile installer registers what its template lists and never removes a registration, so it cannot complete the removal of the handoff.

## What this record cites that the repository does not hold

The configs, the tools and the tests are public (#1046 and this change). These captures are private and a reader of the repository cannot verify them: the E1 comparison's records and result digests (the 288 runs, the corrected
stage and the matched control, the delivery probe, the re-grade), the agent probe (`fix-3-20261012/agent-probe/`) and the override probe of 2.1.296, the drift report this change quotes, and the fail-before and mutant runs of
this change. The documentation pages cited from `code.claude.com` were read on 2026-10-12 and are not captured. Trigger: publish sanitized captures with their hashes before this record is used as independent verification of
those measurements.

## Records this changes

- [2026-10-12-mcp-template-live-reconciliation.md](2026-10-12-mcp-template-live-reconciliation.md), decision 1: the code graph server keeps the vendor's key `codebase-memory-mcp` in the Codex template and in the on-demand file; the
  Claude user-scope template no longer carries it. Its acknowledged row for Claude `socraticode` (DIFFERS) is removed in this change, since the server is no longer rendered; the Codex rows stay.
- [2026-10-02-new-wsl-client-configuration.md](2026-10-02-new-wsl-client-configuration.md): an addendum (the four pieces are a group of their own, `claude/mcp-on-demand`, rendered to `mcp-servers.on-demand.json`; the counts are the ones before this change,
  403 pieces and 363 wired) and the agents' gaps table (the four agents above).
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

- A comparison on cross-file or impact tasks in which the servers' absence costs correctness reopens the question for that task class (a profile, or the user-scope set). Under the multi-angle ruling a comparison is one angle
  (A6), so the question is decided across the angles, not by that comparison alone.
- A larger repeat, or a production-like arm (the repository's own instructions around the paragraph), in which Serena's paragraph keeps (i) and (iii) and brings the median cost to at most 1.1 times the matched A0a's (1.170 at
  36 runs per arm) reopens the always-on question for single-symbol lookups, with the directive as the lever; it is again one angle (A6), decided across the angles.
- The user's instruction on `jcodemunch` (2026-10-04 record), either way.

## Sources

- E1 comparison records (private, cc-native-practice): `E1-PREREGISTRATION.md`, addenda 1 and 2, `delivery-probe-20261012/RESULT.md`; the command center's ruling and addendum 01 of 2026-10-12.
- `docs/decisions/2026-10-12-e-series-promptfoo-configs.md` (the configs and D3), `docs/decisions/2026-10-04-new-wsl-jcodemunch-user-scope.md` (the overturn clause), `docs/decisions/2026-09-23-claude-user-profile.md`
  (the 2026-09-25 precedent: jCodeMunch registered per project because its instruction loaded into every session).
- The command center's multi-angle ruling, `ruling-multi-angle-convergence-20261012.md` (tool clock 20:31Z): our own measurement is angle A6, one of six, and admits or rejects nothing alone. The private override probe of this record
  (init events of two sessions, 2026-10-12) is in the cc-native-practice record `fix-3-20261012/`.
- `claude --help` of the installed client 2.1.296: `--mcp-config <configs...>  Load MCP servers from JSON files or strings (space-separated)`, which is what `--print-mcp-config` feeds; read 2026-10-12.
- https://code.claude.com/docs/en/sub-agents ("Scope MCP servers to a subagent", "Trust required for inline MCP servers"), read 2026-10-12; `anthropics/claude-code@3deb873687379f0c199a69fdaccc65f0865f7a29`
  `CHANGELOG.md` L5601, L4783-L4784, L3138, L7929 (2.0.30: `--mcp-config` overrides file-based MCP configurations, the measured same-name replacement) and L8759 (`claude mcp add-json`, the live-values recovery).
- The command center's ruling to stop E1b after the re-grade (a coordination message after my report of 2026-10-12T22:42:49Z), recorded in the private addendum 4 of the E1 preregistration; the e-series record's deviation D4
  (`docs/decisions/2026-10-12-e-series-promptfoo-configs.md`) is the public source of the corrected counts.
