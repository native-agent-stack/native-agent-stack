# E-series: promptfoo configs for the invoke-gap experiments

The five paired experiments that the invoke-gap cause table gates its fixes on, as versioned promptfoo configs: E1 code navigation under worktree-per-task, E2 records retrieval, E3 Headroom parity, E4
autonomous skills, E5 unresolved triggers. **E1 is runnable for five arms; E2 to E5 are skeletons that refuse to start until their inputs are frozen.** Nothing in this folder has been scored. E1's earlier
measurements came from a private runner; what carries over, what is withdrawn and how this config differs from it are in the
[decision record](../../../docs/decisions/2026-10-12-e-series-promptfoo-configs.md).

| Experiment | Question | Status | Arms | Rule fixed before the first scored run |
| --- | --- | --- | --- | --- |
| [E1](e1/promptfooconfig.yaml) | which change makes code-navigation MCP tools get used, correctly, in a per-task worktree | runnable | A0a status quo (stale session directory, worktree via `--add-dir`), A0b session in the worktree, A1 plus the serena paragraph, A3 stale start plus the path-per-call paragraph, A5 no code-navigation server | adopt an arm only if its correct answers are not fewer than A0a's, its median cost is at most 1.1 times A0a's, and it used a code-navigation tool on at least 70 percent of the questions; A5 is a reference |
| [E2](e2/promptfooconfig.yaml) | records retrieval from rulings, lane records and memory notes | skeleton | `grep-status-quo`, `qmd-directive`, `aimemory-directive` | as E1 |
| [E3](e3/promptfooconfig.yaml) | does the Headroom proxy keep correctness and cut input tokens | skeleton | `direct`, `headroom-proxy` | equal correctness and at least 15 percent fewer input tokens |
| [E4](e4/promptfooconfig.yaml) | do autonomous lanes invoke skills when one sentence answers the approval step | skeleton | `baseline`, `fix7-sentence` | skill invoked in at least 6 of 8 tasks and no loss of correctness |
| [E5](e5/promptfooconfig.yaml) | do the two unresolved skills trigger on natural requests | skeleton | `natural` | descriptive |

The E1 arms with a hook (A2n the Bash-aware nudge, A2v the vendor reminder hooks) or `alwaysLoad` (A4) stay in the private runner: promptfoo's structured MCP option carries `type`, `command`, `args` and
`env` only (`src/providers/mcp/transform.ts` L205-L225 at `promptfoo/promptfoo@30949931ee90`), and command hooks were not run through the provider.

## Requirements

- promptfoo 0.124.0 or newer: `copy_working_dir` gives each eval step its own copy of `working_dir` (`src/providers/agentWorkspace.ts` L89-L99, L637-L725; `site/docs/guides/evaluate-coding-agents.md` L288-L346 at the
  same pin). The release the repository mirrors and pins elsewhere (0.123.1) does not have it, so these configs name 0.124.0 as their minimum.
- `@anthropic-ai/claude-agent-sdk` 0.3.283 (the version promptfoo 0.124.0 pins) resolvable from the config's directory: the provider imports it from there (`site/docs/providers/claude-agent-sdk.md` L22-L27).
  `e1_prepare.py` stages a copy of the config directory and installs or links the SDK beside it.
- The versioned Claude Code client 2.1.296 (`--claude`), not a wrapper on PATH; the four servers (`serena`, `semble`, `codebase-memory-mcp`, `jcodemunch-mcp`) on PATH; the local semble model directory; git; a
  sandbox the client can start (`failIfUnavailable` is on).
- A key for the API, supplied by the caller's environment or, for this repository, by `tools/credentials/credential_run.py <inventory id>` (`--slot`). No config here holds or names a key value.

## Run E1

```sh
E=blueprints/native-skill-practice/e-series/e1
python3 $E/e1_prepare.py --root <root outside $HOME and the repository> --claude <client 2.1.296> --semble-model <dir> [--sdk-from <SDK 0.3.283 dir>]
python3 $E/e1_run.py --root <root> --preflight --slot <inventory id>                    # one row per arm: servers connected, directive delivered
python3 $E/e1_run.py --root <root> --questions --arms A0a,A1 --slot <inventory id>      # the 12 frozen questions x 3 repeats per arm; --ids and --repeats (1 to 3) narrow it
python3 $E/e1_decide.py <root>/out/questions-*.json --baseline A0a                      # the rule above over the result files
```

A question run starts only behind a passing pre-flight: `--preflight` records its outcome in `<root>/out/preflight-<time>.gate` (read from the result file, not from promptfoo's exit status, which two environment
variables can set to 0 and which the runner therefore removes from the child's environment), and `--questions` refuses unless the newest record passed, belongs to this preparation of the root and covers the asked-for
arms. `e1_decide.py` decides only a result file that `e1_run.py` produced behind such a record (`<result>.gate` beside it); a file without one is refused, and `--ungated` prints the table without a verdict. A failed
pre-flight after a run voids it, so the preregistered gates before the first and after the last run are `--preflight` before and after, and `--require-after-gate` makes the decision ask for the second.

`e1_prepare.py` replaces only a root of this harness (a non-empty directory must hold a `manifest.json` of schema 2 that names the harness, and replacing it takes `--rebuild`; any other directory is refused and left as
it was). It builds four trees under `<root>/trees` (the base commit, the base commit with the serena paragraph in `CLAUDE.local.md`, the stale commit, the stale commit with the path paragraph), the sandbox and
permission fence as `settings.json`, the staged config, and `manifest.json`; `e1_run.py` refuses to start when anything the manifest recorded has changed, removes the variables that change a session's model,
effort or credential route, and runs one eval step at a time with no cache, no sharing and no database write. Run the pre-flight first and again after any change to the host.

The base commit `2bdb5731` and the stale commit `a30c2188` are in `tasks.json` with the 12 questions and their gold answers, computed from the base commit by script (git archive and Python's `ast`); the file is
byte-identical to the one the preregistration froze (sha256 starting `9d2727ad3ba5cb9f`). `e1_grade.py` grades an answer by the preregistered rules; `python3 e1_grade.py` runs its self-test.

## What the pre-flight row settles (and what reads it)

The client's init record (tools offered, servers connected) is not part of the provider's response, and an MCP server that fails to start looks, to every metric, like a model that chose not to use it. The pre-flight
row asks each arm to list the code-navigation tools it has and to quote the first sentence of the "Code navigation" paragraph, with no tool but ToolSearch allowed: the four servers' tools must be listed (A5: none)
and the paragraph quoted only by the arm that carries it. Under `--setting-sources local`, which the runner and these configs use, neither the project's `CLAUDE.md` (and the `AGENTS.md` it imports) nor the
user-level one is loaded, so a paragraph appended to `AGENTS.md` never reaches the model; `CLAUDE.local.md` does. That was deviation D3 of the private E1 stage, found by a probe that asked a session with no tool to quote the paragraph (the decision record has the table).

## Differences from the private runner (each one is a limit of the results)

- The paragraph travels in `CLAUDE.local.md`, not in `AGENTS.md` (above). It is then the only memory content of the session, more salient than in production, where it would sit among the repository's other
  instructions: a null result is a strong null, a positive one would still need a production-like arm.
- The session directory is a per-call copy that promptfoo makes (`copy_working_dir: copy`: `fs.cp` of the prepared tree, `agentWorkspace.ts` L715), so its path cannot be named in a prompt: the stale-start prompt
  says "the current one". A shared directory for all repeats made cost 13 to 21 percent lower than the runner's in the first parity attempt, because the directory is part of the cached prompt prefix.
- The MCP servers' indexes and caches live under `<root>/cache` and persist across calls; the runner started each run with empty ones.
- Evaluation order is promptfoo's: the rows in the generator's order (repeat-major), and within a row the arms in the order the config lists them, one at a time. The runner shuffled the arms inside each
  question with a seeded shuffle; here an arm's position in the row is fixed, so a position effect (API load, time between calls) is not randomised across arms.
- The raw stream and the init record are not available; tool names, turns, cost and duration come from `response.metadata` (`src/providers/claude-agent-sdk.ts` L2503-L2509).

## E2 to E5

Each skeleton defines its arms and the shared fence and takes its test rows from [`frozen_inputs.py`](frozen_inputs.py). That generator raises while loading the config, so promptfoo stops before any provider
call, unless `frozen/<experiment>.json` (or `$E_SERIES_FROZEN/<experiment>.json`) says `status: frozen`, names every input the design needs with the sha256 of a file that still matches, and holds the rows:

| Experiment | Inputs that must exist and be hashed before the first run |
| --- | --- |
| E2 | `questions` (12, with gold path and line), `qmd_collection` (the new collection of the private records, embedded), `directives` |
| E3 | `tasks` (E1's `tasks.json`), `proxy` (the Headroom proxy and its version) |
| E4 | `tasks` (8 synthetic pull requests), `sentence`, `skills` |
| E5 | `trigger_cases`, `variants` (6 natural-language variants per skill), `skills` |

The frozen receipt is the experiment's preregistration: rows, rule and digests are fixed in it before the first scored run, and a change to an input after that is a new receipt. E4 and E5 use promptfoo's
own `skill-used` and `not-skill-used` assertions (`site/docs/providers/claude-agent-sdk.md` L485-L560).

## Tests

`python3 -m unittest tests.test_e_series` checks the config values against `e1_common.py`, the grader (including the preregistered deviation D1), the test generator, the assertions, the decision rule on built
result files, the prepare and run scripts on a scratch repository, and the fail-closed generator. The promptfoo-dependent checks (`promptfoo validate config`, an offline eval with a stub provider) run when
promptfoo 0.124.0 or newer is installed and skip otherwise.
