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

## Deviation D4: the grader did not read an absolute path under a prepared tree

Found by the first full read of this change at `30639cdc1` (follow-up 8: "the path normalizer retains only the private runner's directory conventions") and measured on the stored results the same day. `e1_grade.norm`
dropped a leading run of directories ending in `/wt/` or `/primary/`, the names of the private runner's worktree and primary checkout. Under this route the prompt of the stale-start arms names `<root>/trees/base`
("answer about <root>/trees/base only"), so a session cites `/.../trees/base/<file>` with the right lines, which `norm` left absolute and the grader scored wrong; a session that starts in the worktree cites
relative paths (A1: 36 of 36 answers). `norm` now also drops, from an absolute path only, the leading directories up to `trees/<tree>/` of this harness's four trees or up to
`promptfoo-workspace-<id>/workspace/`, the per-call workspace (`src/providers/agentWorkspace.ts` L662-L668 at `promptfoo/promptfoo@30949931ee90`: `mkdtemp` of `promptfoo-workspace-` below the temporary directory,
and `workspace` inside it). The rules of the grader are the preregistered ones: a relative path is left alone, so is any other absolute path, and a location in the stale tree still differs from the base tree's.

The stored results of the corrected stage (`questions-...184816Z.json`: A1 and A3) and of the matched control (`questions-...200417Z.json`: A0a), graded with the old and the new `norm` (`e1_decide.load_runs`):

| Arm (36 runs each) | Runs | Answers citing an absolute tree path | Correct, as graded | Correct, re-graded | Explain (of 9) as graded / re-graded | Total cost USD | Cost per correct answer USD, as graded / re-graded |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A0a, matched control | 36 | 14 | 25 | 33 | 0 / 6 | 2.763 | 0.1105 / 0.0837 |
| A1 | 36 | 0 | 34 | 34 | 7 / 7 | 3.271 | 0.0962 / 0.0962 |
| A3 | 36 | 18 | 20 | 34 | 1 / 8 | 3.169 | 0.1584 / 0.0932 |

No answer of the 108 cited a workspace path or another absolute path. What the correction changes and what it leaves:

- **Unchanged:** A1 against the matched A0a: (i) holds (34 against 33, it was 34 against 25), (ii) fails (median cost 0.0917 against 0.0784 USD, 1.170 times, limit 1.10), (iii) holds (12 of 12 questions): the paragraph makes the
  tools get used, at a cost the rule does not allow, and no default changes. A3 fails (iii) (use on 2 of 12 questions), and now meets (i) as well (34 against 33; it was 20 against 25).
- **Changed:** the matched A0a is 33 correct, not 25, so it is 2 above the runner's A0a (31), not 6 below it: the route check of addendum 3 finds no difference in correctness, cost or tool use. A1's 7 of 9 on the
  explain questions is 7 of 9 against 6 of 9, one answer apart, not 7 against 0. The cost per correct answer of the matched A0a (0.0837 USD) is below A1's (0.0962 USD) in the whole stage; by type A1 is higher on
  `def`, `refs` and `callers` and lower on `explain` (0.1266 against 0.1432), at n = 9 per cell. Statements in other records that quote the old figures are corrected there (the comparison's private addendum 4, and the
  "A lead" paragraph of `2026-10-12-code-navigation-on-demand.md`).
- The private runner's 288 runs name their trees `wt` and `primary`, which `norm` always handled, and the arms that start in the worktree cite relative paths: neither is affected. The stage's runs were made before the
  gate below existed, so they carry no gate record; the re-grade describes them (`e1_decide.py --ungated` prints the same table without a verdict).
- Tests (fail before the change): `GraderTests.test_an_absolute_citation_under_a_prepared_tree_or_a_promptfoo_workspace_is_graded_as_the_relative_one` and
  `test_only_a_leading_run_of_directories_ending_in_a_known_name_is_dropped_and_the_stale_tree_stays_distinct`.

## Measurements through this change (2026-10-12; client 2.1.296, promptfoo 0.124.0, SDK 0.3.283, model `claude-opus-5-5` at medium effort, one eval step at a time)

| Check | Result |
| --- | --- |
| Pre-flight row, five arms | 5 of 5 pass: the four servers listed by A0a, A0b, A1 and A3, none by A5; the serena sentence quoted by A1 only, the path sentence by A3 only; 0.054 to 0.079 USD and 3.7 to 7.2 s per row; each session ran in `<root>/tmp/promptfoo-workspace-*/workspace`. An earlier run on the tree before the last edits (below) passed 5 of 5 as well |
| A0b on `p-def` and `p-callers`, three repeats each | 5 of 6 correct (the wrong answer names the nested helper `accept` instead of its enclosing function `boundary_self_check`, an error the runner's A3 and A4 arms and the first parity attempt made too and that the grader keeps wrong); no code-navigation tool in 6 of 6; median cost 0.0454 and 0.0804 USD against the runner's 0.0457 and 0.0748 (-0.7 and +7.5 percent); median turns 3 and 5, equal to the runner's. An earlier run of the same cell, before the last edits to three staged or run files that change nothing an arm does (a comment, the repository-root lookup, the credential-runner lookup), gave 6 of 6 correct, 0.0452 and 0.0765 USD (-1.1 and +2.3 percent) |
| Parity cell without `copy_working_dir` (runner's own worktrees) | +3.5 and +8.2 percent over the runner |
| Offline, no model: the config, the four skeletons, the generator, the assertions and the decision script against a stub provider | `tests/test_e_series.py`, 73 tests at the first head, 78 after review round 1 and 104 after round 2 (below) |

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

## Follow-ups

- The pre-flight still infers availability from the tool names the model lists; a provider that returns the client's init record or the servers' connection status would replace that inference (quality-evaluation, CPA-C-003, recorded in the research queue).
- The measurements this record cites (the delivery probe, the parity cell, the stage, the mutant runs) are private captures. Publishing sanitized captures with their hashes would let a reader verify the counts; the corrected re-grade above shows why that matters.

## Overturn conditions

- A promptfoo release whose structured MCP option carries `alwaysLoad`, or a parity cell with command hooks run through the provider: A4, A2n and A2v move into the config.
- A change to `copy_working_dir` (the semantics are those of `agentWorkspace.ts` at the pin): repeat the harness check.
- The corrected A1 and A3 re-run, or a production-like arm, showing a directive effect: the E1 conclusion about FIX-2 changes, and this record is superseded by the result.
- A cell in which the provider and the runner disagree on an arm without a directive or a hook.

## Review round 1 (the Codex review of 2026-10-12T18:49Z at `38f4151aa`: two P1, two P2)

Each finding was reproduced as a gap in a guard rail of the scripts, not in the measured path (the config, the tasks, the grader, the generator and the assertions). One commit fixes all four, with a test each that fails before it:

| Finding | Fix | Test (fails before the fix) |
| --- | --- | --- |
| P1 `e1_run.py`: a failed pre-flight row ended with exit 0, like a question row whose answer is wrong | `--preflight` returns promptfoo's own status (100 is "at least one test failed", `promptfoo/promptfoo@30949931ee90` `site/docs/usage/command-line.md` L171): a failed pre-flight row is a wiring defect, not a result. `--questions` still maps 100 to 0 | `test_a_failed_preflight_row_keeps_promptfoos_exit_status_and_a_failed_question_row_does_not` |
| P1 `e1_decide.py`: equal run counts were taken as comparable samples | the arms must hold the same (question, repeat) runs over their shared questions, for the adoption rule and for the carrying contrast (A0b against A5) | `test_equal_run_counts_over_different_question_repeat_pairs_are_refused`, `test_the_carrying_cost_needs_the_same_pairs_in_a0b_and_a5` |
| P2 `e1_run.py`: a copied or moved root was accepted | refused unless the root's real path equals the manifest's; another name for the same directory (a symbolic link) is accepted | `test_run_refuses_a_root_that_was_copied_or_moved_but_accepts_another_name_for_the_same_directory` |
| P2 `e1_prepare.py`: a relative `--claude`, `--semble-model` or `--promptfoo` was recorded as given | stored absolute, since the run starts promptfoo from `<root>/config` | `test_prepare_records_absolute_paths_for_tools_given_relative_to_the_working_directory` |

`--questions` did not yet require a passing pre-flight (round 2 closes that: below). The corrected A1 and A3 stage
(addendum 2 of the comparison's record) ran at the frozen digests of `38f4151aa`; this round changes `e1_run.py`, `e1_prepare.py` and `e1_decide.py` and not the config, the tasks, the grader, the generator or the assertions, so the
stage's evidence is unaffected. 12 of 12 mutants of the fixes are killed; the 78 tests pass, and 6 of them (the 5 new ones and the updated exit-status test) fail on the sources of `38f4151aa`.

## Review round 2 (the Codex delta review of 2026-10-12T20:17Z and the first full read at 22:13Z, both at `30639cdc1`: five blockers, six follow-ups)

The Codex delta review's two findings and the full read's five blockers were reproduced as gaps in the guard rails of the scripts. One commit fixes them, with tests that fail before it:

| Finding | Fix | Test (fails before the fix) |
| --- | --- | --- |
| P1 `e1_decide.py`: a response without `cost` was recorded as costing zero, so criterion (ii) could pass with no cost measurement (and `ADOPT` was printed). The provider makes `cost` undefined when usage accounting is unavailable and returns it with a success response (`promptfoo@30949931ee90` `src/providers/claude-agent-sdk.ts` L2445-L2447, L2487-L2498) | a response whose cost is missing, null, an empty string, a boolean, not finite or negative is a fault: listed, left out of the figures, exit 3, and the arms then hold different (question, repeat) pairs, so no verdict is printed. A cost of 0 that is present is a measurement | `test_a_response_without_a_usable_cost_is_a_fault_and_left_out_not_a_free_run`, `GatedDecideTests.test_a_missing_cost_never_gives_an_adoption` |
| P1 `e1_run.py`: a failing pre-flight returned 0 when the caller had set `PROMPTFOO_PASS_RATE_THRESHOLD` or `PROMPTFOO_FAILED_TEST_EXIT_CODE`, the two variables that decide promptfoo's exit status (`src/node/doEval.ts` L1271-L1286) | both are removed from the environment of the child (`C.EXIT_VARS`), and the pre-flight is decided from the result file (`e1_gate.preflight_outcome`: exactly one row per asked-for arm, each passed with no error, no row of another arm), not from the status | `test_the_exit_status_variables_of_the_caller_do_not_decide_the_preflight`, `PromptfooIntegrationTests.test_a_failing_preflight_stays_a_failure_under_the_exit_settings_of_the_caller` (the real promptfoo, three environments), `GateUnitTests` |
| P1 `e1_run.py`, `e1_decide.py`: the questions could be run after a failed pre-flight or with none, and a result was decided whatever it had run behind | `--preflight` writes `out/preflight-<time>.gate` (passed or not, the asked-for arms, the sha256 of the manifest and of the result file); `--questions` starts promptfoo only if the newest such record passed, belongs to this preparation, covers the asked-for arms and still matches its result file, and writes `out/questions-<time>.gate`; `e1_decide.py` refuses a result file without that record, one that changed, one of an earlier preparation, and a run that a later failed pre-flight voids (the preregistered protocol); `--ungated` describes without a verdict (`e1_gate.py`) | `PrepareTests.test_questions_do_not_start_without_a_passing_preflight_of_this_preparation_for_the_asked_arms` (absent, failed, a row missing, wrong arm, changed result, stale, later failure, with a passing control), `GatedDecideTests` |
| P2 `e1_run.py`: edited live directives were accepted (also the Codex thread 4251972782) | the live `CLAUDE.local.md` of the A1 and A3 trees must equal the staged directive (itself checked against the manifest) and the digest the manifest recorded | `test_run_refuses_a_directive_file_edited_after_prepare_or_a_manifest_that_does_not_record_it` (each tree on its own; live and manifest changed together; the manifest alone; the staged copy) |
| P1 `e1_prepare.py`: a directory holding a file named `manifest.json` was taken for an earlier root and its `config/` removed without `--rebuild` | a non-empty root must hold a manifest of this harness (`validate_manifest`: the marker, the schema 2 and the shape of every field a later step reads) or nothing in it is changed, with or without `--rebuild`; an owned root, partial or not, is replaced only with `--rebuild`; `e1_run.py` reads the same validation instead of failing on a missing key | `test_a_directory_with_a_file_named_manifest_json_is_not_a_root_of_this_harness`, `test_a_root_of_this_harness_is_replaced_only_with_rebuild_even_when_it_is_partial`, `test_each_field_a_later_step_reads_is_checked_in_an_otherwise_valid_manifest` |

The follow-ups, each fixed with a test unless said: a rebuild keeps `out/`, so a result file is bound to the preparation that produced it (the manifest digest in its record; every preparation has a new `generation`) and the same (arm, question, repeat) twice is a fault, exit 3
(`test_a_replayed_result_file_is_a_fault_with_its_exit_status`); `--repeats` is 1 to 3, the number the staged generator makes (`C.GENERATED_REPEATS`, compared with the config); the grader's path normalizer (deviation D4); the docstring of
`frozen_inputs.py` cites the rule in `AGENTS.md` instead of repeating a sentence of the owner; a relative `--credential-runner` is made absolute before promptfoo is started from `<root>/config`
(`test_a_relative_credential_runner_is_resolved_before_promptfoo_is_started_from_the_staged_config`). Not changed: the hostname lines that already stand in `manifests/evidence.json` (none is in this change).

104 tests pass; 49 of 49 mutants of the round-2 changes are killed (`review-fixes-round3-mutants.txt`, private); the new and rewritten tests fail on the sources of `30639cdc1` (29 failures and 14 errors of the 104, in 31 tests). The config, the tasks, the generator and the assertions are
unchanged. The grader is not: deviation D4 above, which changes what the stored stage's answers score and not a conclusion of the stage.

## Sources

- `promptfoo/promptfoo@30949931ee90` (0.124.0): `src/providers/agentWorkspace.ts` L89-L99 (modes), L637-L725 (a workspace per call: `git clone --shared` when the tree is clean, `fs.cp` otherwise); `site/docs/guides/evaluate-coding-agents.md`
  L288-L346 (isolated workspaces); `site/docs/providers/claude-agent-sdk.md` L22-L27 (the SDK package), L146-L206 (options), L485-L560 (skills); `src/providers/mcp/transform.ts` L205-L225;
  `src/providers/claude-agent-sdk.ts` L2503-L2509 (`toolCalls`, `numTurns`, `durationMs`); `site/docs/configuration/test-cases.md` L486-L530 (Python generators with config);
  `site/docs/configuration/expected-outputs/python.md` L60-L135 (assertion context); `src/types/index.ts` L380-L386 (`ResultFailureReason`: an assertion that rejects an answer is 1, a provider error 2);
  `site/docs/guides/test-agent-skills.md` (`skill-used`); `site/docs/usage/command-line.md` L171 (`eval` exits 100 when at least one test case fails); `src/node/doEval.ts` L1271-L1286 (the exit status is
  `PROMPTFOO_FAILED_TEST_EXIT_CODE`, default 100, when the pass rate is below `PROMPTFOO_PASS_RATE_THRESHOLD`, default 100); `src/providers/claude-agent-sdk.ts` L2445-L2447 and L2487-L2498 (`cost` is undefined
  when usage is unavailable, and a success response carries it); `src/providers/agentWorkspace.ts` L662-L668 (the per-call workspace is `<tmp>/promptfoo-workspace-<id>/workspace`).
- `promptfoo/promptfoo@34f74d34e140b5e17d23770dfb2340057b1936b8` (0.123.1, the pin the repository mirrors elsewhere): no `copy_working_dir` in `src` or `site`.
- `anthropics/claude-code@3deb873687379f0c199a69fdaccc65f0865f7a29`, `CHANGELOG.md` L1378, L2960, L5879, L6759, L7962 (`--setting-sources` restricts the settings sources a session loads); what a source loads is the
  probe above, run on the installed client.
- This repository: `tools/credentials/credential_run.py` (the key route), `scripts/validate.py` (private-content rules the folder passes).
