# The research campaign on the new host: how it is launched, paced and sealed, 2026-10-16

Status: practice row written from this repository's own campaign tools, each cited at `native-agent-stack@8dfe8b588de22451364857b4be4683fb35f57a7d`
(abbreviated `@8dfe8b58` below); every step without such a source is labelled PROPOSAL. It installs nothing and changes no
default. The new host's install of these tools is the install stage's (#1174); a campaign runs there only after the checks
named under "On the new host".

## Trigger

At 21:15 ET on 2026-10-15 the owner asked that research convergence run as a campaign across several research runtimes and
model families, and that this campaign capability be part of the new host. The command center's addendum 11 to its 19:46Z
direction (2026-10-16, a coordination record cited by name and date) routed this row here, with the install to #1174.

## The campaign's parts

| Part | Mechanism | Source at @8dfe8b58 |
| --- | --- | --- |
| Landscape sweep, Claude half | the saved Workflow `landscape-sweep`: discovery, facts and fit refuters, completeness critic, one bounded follow-up round; Claude agents are `landscape-sweep-worker`, Opus, effort max | `tools/sota-convergence/landscape-sweep/sweep.js:1-11`, `:51`, `:184-196`; `.claude/agents/landscape-sweep-worker.md:3` |
| Landscape sweep, GPT half | the same Workflow runs `codex exec` jobs (GPT-6-Astra, effort max, live web search) through `codex_call.sh` | `sweep.js:105-139`; `codex_job.py:2`, `:15-17` |
| DeerFlow | `tools/research/dispatch --question '<public research question>'`, the embedded DeerFlow producer's cited answer | `tools/research/dispatch:2`, `:169-177`, `:211-212`; `docs/decisions/2026-10-08-coordinator-research-routing.md:115` |
| GPT Researcher | `tools/research/gpt_researcher.sh "<short current-month query>"`, keyless through the gateway | `tools/research/gpt_researcher.sh:2-5`, `:31` |
| Muse | TRIAL only, through the file fence: `python3 tools/muse_file_fence.py --role reader WORKTREE BRIEF LOGDIR` | `tools/muse_file_fence.py:2`; `docs/decisions/2026-10-14-muse-file-fence.md:149-155`; `catalogs/landscape/final-stack.json:6422` |
| Layer verdicts | the saved Workflow `layer-verdict-lane` over stripped packets (`lane_packets.py`), and its GPT half (`codex_lane.py`) | `examples/claude-native/workflows/layer-verdict-lane.js:1-4`, `:97-107`; `tools/sota-convergence/lane_packets.py:2-14` |
| Blind judges and adjudication | `blind-judge` on stripped comparison packets; `blind-adjudicator` on anonymous two-return inputs, through `adjudicate.py` | `.claude/agents/blind-judge.md:2-8`; `.claude/agents/blind-adjudicator.md:2-13`; `tools/sota-convergence/adjudicate.py:27-28` |

## Launch

1. **Scope before discovery:** the layer-resolution protocol's steps 1-3 (verdict, latest sweep, delta) decide which layers a
   campaign touches; only the delta is dispatched (`docs/decisions/2026-10-11-layer-resolution-protocol.md`).
2. **Stage, then run:** `build_args.py --work-dir W --sweep-id --date --due-report` stages the due layers in a work directory
   outside every repository, then the coordinator calls `Workflow({scriptPath: "<W>/sweep.embedded.js"})`; a resume is
   `Workflow({scriptPath, resumeFromRunId})` (`tools/sota-convergence/landscape-sweep/README.md:553-560`, `:604-612`).
3. **One-off questions** go through `tools/research/dispatch`, which needs an hcom identity (`hcom list self --json`,
   `dispatch:216-228`); a coordinator's own WebSearch is denied by the research-routing guard and redirected there
   (`adoption/hooks/claude/research-routing-guard.py:17-18`, `:57`, `:190-191`, `:207`).
4. **A person starts each sweep;** nothing calls a model on a schedule (`recipes/saturation-sweep.md:6-8`).

## Pace

- **Claude agents:** `CLAUDE_CODE_WORKFLOW_MAX_CONCURRENT_AGENTS` 8, spawn depth 1, 1,500 web searches per session
  (`.claude/settings.json:9-12`); raise the agent count toward 12-16 only after a run without rate-limit errors
  (`recipes/claude-native-ultracode.md:93-95`).
- **GPT jobs:** three semaphore slots per lock directory (`landscape-sweep/README.md:1001-1005`); the first 429 or usage
  limit writes `<W>/LIMIT`, later jobs exit 3, and the Workflow is stopped, never retried into the limit
  (`README.md:1011-1033`; `docs/decisions/2026-09-29-sweep-429-limit-marker.md:16-18`); capacity errors retry at most twice
  (`codex_job.py:86-95`).
- **Research runtimes:** a 1,500-second watchdog per call (`gpt_researcher.sh:23`, `:110`), one call in the foreground,
  with no retry or provider switch (`evidence/artifacts/new-wsl-install-plan-20261002/config/research-harnesses-skill.md:29-33`).
- **PROPOSAL, a cap on concurrent research calls:** no lock or slot bounds DeerFlow or GPT Researcher calls in the
  repository. A coordination measurement of 2026-10-11 saw no sources returned with six concurrent runs and normal results
  with two, paced; the cap stays a PROPOSAL until a repository record measures it.
- **Pool reserve:** the GPT pool's reserve rule lives in the co-op's screens plan (2026-10-15, a coordination record); it is
  not in the repository and stays a PROPOSAL here.

## Seal

- **A candidate survives** only when the facts refuter and both fit refuters (Claude and GPT) do not refute it; a missing
  vote counts as a refutation (`landscape-sweep/README.md:227-234`), and a failed part leaves a `retained_failure` reopen
  entry, never a clean layer (`:517-524`).
- **The critic** names at most eight layers where discovery most likely missed a candidate class, for one bounded
  follow-up round (`sweep.js:37-38`, `:211-230`; `templates.json:8`).
- **Returns are retained** under `evidence/artifacts/<lane>/` and registered with `scripts/host_receipts.register_file`, then
  `scripts/validate.py` (`landscape-sweep/README.md:644-650`).
- **The ledger row** is appended with `--append` and checked with `--check --base origin/main`
  (`recipes/saturation-sweep.md:110-147`); a layer is a saturation candidate after three consecutive clean sweeps at least
  seven days apart under unchanged hashes (`catalogs/saturation/README.md:118-126`). That count is not FINAL
  (`docs/decisions/2026-10-11-layer-resolution-protocol.md:120-121`).
- **Stopping:** a bounded candidate set resolved with no material gap left; reopen on a changed requirement or platform, a
  missing capability, a retained failure or a changed comparison (`docs/landscape-continuation.md:89-109`).
- **A verdict seals** only when both lenses voted and neither refuted (`layer-verdict-lane.js:97-107`); a winner needs
  unanimous, unrefuted judgments from both families in both orders, otherwise it is a split (`adjudicate.py:27-28`).
- **A layer evidence cannot settle** gets one preregistered comparison with a readiness trigger and a fixed rule
  (SCHEDULED, `layer-resolution-protocol.md:87-96`).
- **PROPOSAL, the blind judges in the sweep's own seal:** the sweep's seal path has no blind-judge step; blind judging is
  recorded for comparisons and verdict disagreements only. Whether a campaign's merge passes through a blind judge is a
  PROPOSAL for the quality-evaluation layer.

## On the new host

- The research arms dial the GPT gateway at 127.0.0.1:21128, which on the shared network is NativeStack2604's live gateway;
  no GPT arm, DeerFlow or GPT Researcher run starts there until the install plan's stage S has proved the new host's own
  gateway on its own port (`docs/decisions/2026-10-15-new-wsl-clean-install-plan.md:673-679`, `:750-758`, `:411-414`).
- The research harnesses' check runs in stage S, after sign-ins (`:265-269`).
- Muse stays a TRIAL through its fence there too (`:604`).
- PROPOSAL: the install plan names no landscape-sweep file or port for the new host; its stage H (harness landscape) is the
  place to add them, with the sweep's ports read from the host value file.

## Correction found

`recipes/saturation-sweep.md:67` says the facts refuter is Sonnet; the Workflow and its README run it on Opus
(`sweep.js:193-194`; `landscape-sweep/README.md:222`, `:239`). The code is the source; the recipe line is a Follow-up to
correct, with a check that ties it to `sweep.js`.

## Sources

- `native-agent-stack@8dfe8b588de22451364857b4be4683fb35f57a7d`, every path and line above.
- The command center's addendum 11 (2026-10-16) and its gap-routing record (2026-10-16T01:08Z); the co-op's screens plan
  (2026-10-15); a research-pacing measurement of 2026-10-11: coordination records, cited by name and date.
