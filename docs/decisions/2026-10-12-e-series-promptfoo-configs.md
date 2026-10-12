# E-series experiments as promptfoo configs, and the E1 directive-delivery finding, 2026-10-12

Status: decided by the command center's queue of 2026-10-12 (the Claude-family practice audit's CPA-C-003 rule: adopt promptfoo when a parity cell agrees). The corrected A1 and A3 re-run that this change makes
possible was approved the same day and follows this change. Nothing here scores an arm: the configs and tools are in `blueprints/native-skill-practice/e-series/`, which also holds the run instructions.

## Context

The invoke-gap cause table (a private research record) gates its fixes on five paired experiments, E1 to E5. E1 ran on a private runner: 288 runs, 20.73 USD, a code-navigation MCP tool used in 0 of them.
CPA-C-003 asked whether promptfoo's `anthropic:claude-agent-sdk` provider reproduces that runner, so that the experiments become reviewable, versioned configs instead of one author's scripts. The parity cell
(arm A0b on `p-def` and `p-callers`, three trials per side, same client, model, effort, fence and settings file) agreed: provider cost +3.5 and +8.2 percent over the runner's medians, turns equal, no
code-navigation call in 12 of 12 runs, 12 of 12 answers correct. It also named what the provider cannot carry: `alwaysLoad`, command hooks and the client's init record.

## Decision

1. **E1 becomes a promptfoo config for five arms**: A0a (stale session directory, worktree via `--add-dir`), A0b (session in the worktree), A1 (A0b plus the serena paragraph), A3 (A0a plus the path-per-call
   paragraph), A5 (no server). The 12 frozen questions, their gold answers, the grader (the preregistered rules plus deviation D1) and the decision rule are in the folder; the frozen `tasks.json` is byte-identical to
   the preregistered one (sha256 starting `9d2727ad3ba5cb9f`).
2. **Each eval step gets its own copy of the tree** (`copy_working_dir: copy`). A single shared working directory made cost 13 to 21 percent lower than the runner's in the first parity attempt, because the
   directory is part of the cached prompt prefix.
3. **A pre-flight row per arm** replaces the init record the provider does not return: with no tool but ToolSearch allowed, the session lists the code-navigation tools it has and quotes the first sentence of the
   "Code navigation" paragraph. The four servers must be listed (A5: none) and the paragraph quoted only by the arm that carries it.
4. **A1 and A3 deliver their paragraph in `CLAUDE.local.md`**, not in `AGENTS.md` (deviation D3, below).
5. **E2 to E5 are skeletons that fail closed.** Their arms and fence are versioned; their test rows come from `frozen_inputs.py`, which raises while promptfoo loads the config unless a frozen receipt names every
   input the design needs with a matching sha256. E4 and E5 use promptfoo's own `skill-used` assertion.
6. **Arms that stay in the private runner**: A2n and A2v (command hooks), A4 (`alwaysLoad` is dropped by the structured MCP option, `src/providers/mcp/transform.ts` L205-L225 at `promptfoo/promptfoo@30949931ee90`).

## Deviation D3: the E1 directive arms never delivered their directive

E1's arms A1, A2n, A3, A4 and A2v appended a "Code navigation" paragraph to `AGENTS.md`, which the checked-in `CLAUDE.md` imports, and started the client with `--setting-sources local`. Probe (client 2.1.296,
`-p --tools ""` so that no tool can be called, the runner's fence flags, model `claude-haiku-5-5` at low effort, one run per row, 0.00004 to 0.0007 USD each; prompt: quote the first sentence of the section titled
"Code navigation" from the instructions given at the start of the session, or answer NONE):

| Setting sources | Where the paragraph is | Answer |
| --- | --- | --- |
| `local` (E1 as run) | appended to `AGENTS.md` | NONE |
| `local` (control) | nowhere | NONE |
| `project,local` | appended to `AGENTS.md` | the sentence, verbatim |
| `user,project,local` | appended to `AGENTS.md` | the sentence, verbatim |
| `local` | `CLAUDE.local.md` in the tree root | the sentence, verbatim |
| `local` | `--append-system-prompt` | the sentence, verbatim |

A second prompt, for the heading "Native engineering defaults" that the base commit's `AGENTS.md` and the user-level `CLAUDE.md` both carry, gave NONE under `local` and the sentence under `project,local`: the
flag loads neither file (the preregistration's section 2 said the user's `CLAUDE.md` loads). The provider's own page says the same of its option: `setting_sources` is "where SDK looks for settings, CLAUDE.md, and
slash commands" (`site/docs/providers/claude-agent-sdk.md` L176).

| E1 result | Status after D3 |
| --- | --- |
| No code-navigation tool used in 0 of 288 runs where no directive was in the context | stands |
| Carrying the four servers (A0b against A5): median cost +14.6 percent, median wall time +9 s, correct runs 32 against 34 | stands |
| The Bash-aware nudge (A2n), `alwaysLoad` (A4) and the vendor reminder hooks (A2v) did not change use | stand, as levers without a directive |
| A1 and A3 equal A0b and A0a (their runs are replicates of those arms) | follows from D3 |
| "A directive in `AGENTS.md` does not change use" | withdrawn: the lever was never delivered, so FIX-2 of the cause table has not been tested |

`CLAUDE.local.md` is the delivery route that needs no change to the fence. Its limit: the paragraph is then the only memory content of the session, more salient than in production, where it sits among the
repository's other instructions, so a null result is a strong null and a positive one would still need a production-like arm (the `project` source, which loads the repository's own settings and hooks).

## Measurements through this change (2026-10-12; client 2.1.296, promptfoo 0.124.0, SDK 0.3.283, model `claude-opus-5-5` at medium effort, one eval step at a time)

| Check | Result |
| --- | --- |
| Pre-flight row, five arms | 5 of 5 pass: the four servers listed by A0a, A0b, A1 and A3, none by A5; the serena sentence quoted by A1 only, the path sentence by A3 only; 0.054 to 0.079 USD and 3.7 to 7.2 s per row; each session ran in `<root>/tmp/promptfoo-workspace-*/workspace`. An earlier run on the tree before the last edits (below) passed 5 of 5 as well |
| A0b on `p-def` and `p-callers`, three repeats each | 5 of 6 correct (the wrong answer names the nested helper `accept` instead of its enclosing function `boundary_self_check`, an error the runner's A3 and A4 arms and the first parity attempt made too and that the grader keeps wrong); no code-navigation tool in 6 of 6; median cost 0.0454 and 0.0804 USD against the runner's 0.0457 and 0.0748 (-0.7 and +7.5 percent); median turns 3 and 5, equal to the runner's. An earlier run of the same cell, before the last edits to three staged or run files that change nothing an arm does (a comment, the repository-root lookup, the credential-runner lookup), gave 6 of 6 correct, 0.0452 and 0.0765 USD (-1.1 and +2.3 percent) |
| Parity cell without `copy_working_dir` (runner's own worktrees) | +3.5 and +8.2 percent over the runner |
| Offline, no model: the config, the four skeletons, the generator, the assertions and the decision script against a stub provider | `tests/test_e_series.py`, 73 tests |

The harness check is descriptive: two rounds of three repeats on two questions of one arm (11 of 12 correct, no code-navigation call in 12 of 12), medians. It shows that this route reproduces the runner for the arm without a directive or a hook; it does not measure A1 or A3. The pre-flight and the cell above are the run of the committed bytes: the root was prepared from the committed tree, without `--repo` or `--credential-runner`, and its manifest digests equal the committed files.

## What is not covered

- Arms with a hook or `alwaysLoad` (above); the client's init record and the raw stream, so the pre-flight row is the only check that servers connected and a directive arrived.
- The runner's seeded shuffle of the arms inside each question: promptfoo runs the arms in the config's order for each row, so an arm's position is fixed.
- The MCP servers' indexes persist across calls under `<root>/cache`; the runner started each run with empty ones. The stale-start prompt says "the current one" for the session directory, which promptfoo creates per call.
- 12 questions of one repository and Python symbols only; E1 is single-symbol lookups that one Grep answers, so a null can be correct non-use.
- E2 to E5 are designs, not experiments: no input is frozen, the frozen-receipt format has not been used, and their server definitions and skill discovery routes are to be settled at their freeze.
- A production-like directive arm (project source) and the effect of a directive among the repository's other instructions.

## Alternatives

- **Keep the private runner for all of E1 to E5.** Its measurements stay valid for the arms listed above, but its scripts are one author's, unreviewed and unversioned, and D3 went unseen in them for the whole stage.
- **Deliver the directive through `AGENTS.md` with `project` in the setting sources.** That is the production route, and it loads the repository's own `.claude/` settings and hooks, which changes the fence for every
  arm; it is a separate arm, not a repair of A1.
- **`--append-system-prompt`.** It delivered in the probe, but it moves the paragraph out of the memory-file position the fix under test would occupy.
- **promptfoo's `trajectory:*` assertions for use of a tool.** They need tracing; `response.metadata.toolCalls` is returned without it, so `e1_decide.py` reads the tool names from there.
- **One config per arm.** Five copies of the fence to keep in step; one config with a shared fence and a test that pins it is smaller and checkable.

## Overturn conditions

- A promptfoo release whose structured MCP option carries `alwaysLoad`, or a parity cell with command hooks run through the provider: A4, A2n and A2v move into the config.
- A change to `copy_working_dir` (the semantics are those of `agentWorkspace.ts` at the pin): repeat the harness check.
- The corrected A1 and A3 re-run, or a production-like arm, showing a directive effect: the E1 conclusion about FIX-2 changes, and this record is superseded by the result.
- A cell in which the provider and the runner disagree on an arm without a directive or a hook.

## Sources

- `promptfoo/promptfoo@30949931ee90` (0.124.0): `src/providers/agentWorkspace.ts` L89-L99 (modes), L637-L725 (a workspace per call: `git clone --shared` when the tree is clean, `fs.cp` otherwise); `site/docs/guides/evaluate-coding-agents.md`
  L288-L346 (isolated workspaces); `site/docs/providers/claude-agent-sdk.md` L22-L27 (the SDK package), L146-L206 (options), L485-L560 (skills); `src/providers/mcp/transform.ts` L205-L225;
  `src/providers/claude-agent-sdk.ts` L2503-L2509 (`toolCalls`, `numTurns`, `durationMs`); `site/docs/configuration/test-cases.md` L486-L530 (Python generators with config);
  `site/docs/configuration/expected-outputs/python.md` L60-L135 (assertion context); `src/types/index.ts` L380-L386 (`ResultFailureReason`: an assertion that rejects an answer is 1, a provider error 2);
  `site/docs/guides/test-agent-skills.md` (`skill-used`).
- `promptfoo/promptfoo@34f74d34e140b5e17d23770dfb2340057b1936b8` (0.123.1, the pin the repository mirrors elsewhere): no `copy_working_dir` in `src` or `site`.
- `anthropics/claude-code@3deb873687379f0c199a69fdaccc65f0865f7a29`, `CHANGELOG.md` L1378, L2960, L5879, L6759, L7962 (`--setting-sources` restricts the settings sources a session loads); what a source loads is the
  probe above, run on the installed client.
- This repository: `tools/credentials/credential_run.py` (the key route), `scripts/validate.py` (private-content rules the folder passes).
