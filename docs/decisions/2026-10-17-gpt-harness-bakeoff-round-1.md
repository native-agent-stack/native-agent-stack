# Decision: GPT-lane harness bake-off, round 1 — a measurement record and a proposal, no routing change (2026-10-17)

Status: measurement recorded; the outcome is a **proposal** for the command center. No runtime default, lane runner, profile or
catalog changes in this record. Scope: eight agent harnesses driven through one gateway lane with one model and one effort.

## What this changes

- Adds the round-1 scores and ranking as evidence, in
  [`evidence/artifacts/gpt-harness-bakeoff-20261017/`](../../evidence/artifacts/gpt-harness-bakeoff-20261017/)
  (`SCORES.json`, `RANKING.md`), registered in `manifests/evidence.json`.
- Adds a numeric T2 usage extract (`T2-USAGE.json`), an offline publication checker (`recompute.py`) and the proposed frozen
  round-2 scope (`ROUND2-PREREGISTRATION.json`) beside the scores. The extract is recomputed from retained usage events and final
  replies; it contains no raw transcripts. The checker derives aggregates from runs and rejects incomplete records.
- Adds this record and `tests/test_gpt_harness_bakeoff_round_1.py`, which bind the tables to those run records.
- `codex exec` (through the Codex runner `tools/sota-convergence/landscape-sweep/codex_call.sh`) stays the
  default and the fallback of the GPT lane.

## Layer resolution consumed

The [resolution protocol](2026-10-11-layer-resolution-protocol.md) supplies the resolution inputs and the delta boundary for
`agent-sdks` (Agent SDKs and runtime workers):

- Catalog verdict: `catalogs/landscape/foundation.json:4577` (current choice: Codex SDK/CLI for supported start/run/resume; the
  OpenHands SDK among the source-reviewed, unselected alternatives) and `:4661` (`verdict_status` `recorded`).
- Latest sweep covering the layer: `landscape-sweep-20260929`, `catalogs/saturation/ledger.json:7694` (sweep) and `:10396` (the
  `agent-sdks` row, with its `survived[]`, `refuted[]` and `reopen[]`; the reopen triggers are `pin_moved` receipt-staleness
  entries for the Codex receipts).
- That row's `refuted[]` includes `earendil-works/pi` and `openhands/software-agent-sdk`, each with a `fit` vote of `refuted`.
  Its unresolved `survived[]` entries are `github/copilot-sdk` and `agentproto/ts`. The retained manifest and
  `evidence/artifacts/landscape-sweep-20260929/returns.json#/votes/agent-sdks` supply the adjudications; round 1 does not settle
  either survivor. Earlier covering sweeps in the ledger have no additional unresolved survivors.
- Wave gap: `catalogs/sota-convergence/layer-verdict-waves.json` has no entry for this layer; specifically,
  `layer-verdict-waves.json` has no `agent-sdks` entry. An absent wave is not an approval.
- This round was **not a preregistered comparison**. It adjudicates no survivor, settles no unresolved vote and changes no verdict
  or wave; it is a first-hand measurement of one disputed dimension (speed, token use and reply fidelity per harness on one model),
  taken because the runtime matrix screened several harnesses as `pass` for the same gateway lane. Round 2 below is the delta, and
  remains a proposal pending its named inputs. Proposing pi requires the protocol's reopen on this new evidence
  (protocol Decision, lines 55–60): retain a changed-evidence sweep that revisits its refuted fit, bind the reopening to it, and
  dispatch only that delta. The old Codex `pin_moved` entries do not reopen pi. The cumulative survivors must receive an explicit
  disposition before any terminal layer claim; omitting them from this bounded harness comparison does not refute them.

## SOTA sources

- Repository policy for what a default needs: `AGENTS.md:7` ("Use models only through a converged harness with its full layers
  (skills, MCP, hook equivalents, memory and token efficiency, telemetry, isolation and roles, invoke receipts)"; a bare API call
  is for measurement probes and smokes only).
- Harness pins, as screened in the runtime matrix (CC-local `pages/runtimes.json`, generated 2026-10-17T20:17:46Z; each commit was
  resolved on GitHub for this record):

  | Harness | Pin | Commit |
  | --- | --- | --- |
  | Codex CLI (`codex exec`, baseline) | `openai/codex` `rust-v0.163.0` | `83086188ae0614bd882818ff1aa23f3194962012` |
  | pi | `earendil-works/pi` `v1.3.0` | `71023aec1546d6d677a65669c5665c0927ce0dd0` |
  | opencode | `anomalyco/opencode` `v1.19.3` | `e3c4eb242585dcd77be1a867391b7c25fd47ce52` |
  | kilo | `Kilo-Org/kilocode` `v7.8.12` | `8001cdc387522ff36fc0b775e3bd11e098f5b03f` |
  | oh-my-pi | `can1357/oh-my-pi` `v18.12.0` | `df4f996e66a200ab7e0496114d43bdf85f32194d` |
  | goose | `aaif-goose/goose` `v1.55.0` | `2bcb8583a18a0623eb78c9ed845d597ed99fae48` |
  | OpenHands SDK | `OpenHands/software-agent-sdk` `v1.55.1` | `5fa4dea24c52fe3ac53fa4e3e67a1376b72189e2` |
  | deerflow | `bytedance/deer-flow` `v2.1.0` | `345f08be00c8a9495079b732a39b46aa9af1584e` |

- Token accounting in the baseline: `openai/codex@83086188ae0614bd882818ff1aa23f3194962012:codex-rs/protocol/src/protocol.rs:2363-2382`
  (`TokenUsage` keeps `input_tokens` and `cached_input_tokens` as separate fields) and `:2552-2554` (`non_cached_input` is
  `input_tokens - cached_input`, so `input_tokens` includes the cached part).
- pi's model configuration: `earendil-works/pi@71023aec1546d6d677a65669c5665c0927ce0dd0:packages/coding-agent/src/core/model-config.ts:38,54`
  (`thinkingLevelMap` in the model schemas) and `packages/coding-agent/docs/models.md:104-109` (the thinking-level keys `off` to
  `max` in a sampling-configuration example; this does not establish an effort-clamping mechanism). The configuration effect
  in caveat 4 is host-observed only. The flags the pi run used are parsed at
  `packages/coding-agent/src/cli/args.ts:189` (`--no-extensions`), `:191` (`--no-mcp`), `:210` (`--no-skills`) and `:216`
  (`--no-context-files`). pi's own statement of its safety model: `packages/coding-agent/docs/security.md:3` (it runs with the
  permissions of its user and does not ask for approval before every tool call) and `:99` (no built-in sandbox).
- The repository's Codex runner: `tools/sota-convergence/landscape-sweep/codex_job.py:14-18` (the exact `codex exec` argv:
  `codex exec --ignore-user-config --skip-git-repo-check -s read-only -m gpt-6-astra -c model_reasoning_effort="max" -c web_search="live" --output-schema <job>/schema.json -o <job>/last.json --json "<prompt>"`,
  with null stdin) and `:193` (`DEFAULT_MODEL = "gpt-6-astra"`). This is the documented native-provider command; gateway mode
  uses its staged profile as described immediately below it. `codex_argv()` at `:1091` forces `read-only` in both modes.
  At the Codex pin above, `codex-rs/protocol/src/protocol.rs:1357` gives ReadOnly no writable roots; isolation alone cannot make
  that wrapper an edit baseline.
- The repository's profile code for harness runs: `tools/adoption/runtime_profiles.py:77-98` (`verify_runtime_binary` admits only pi
  1.1.0 and opencode 1.18.35).
- Publication computation and tests use the installed Python 3.13.16 standard library, following
  [`python/cpython@v3.13.16:Lib/statistics.py`](https://github.com/python/cpython/blob/v3.13.16/Lib/statistics.py) (`median`),
  `Lib/json` and `Lib/unittest`. No model driver or test dependency is introduced. The offline selectors in `recompute.py` use
  completed `message_end` / `step_finish` events, Codex `turn.completed`, goose metadata, OpenHands `USAGE`, and DeerFlow's final
  `values` snapshot, so repeated histories and streaming deltas are not counted twice.

## What ran

- Model `cx/gpt-6.1-sol` at effort max through the loopback gateway lane, for every harness
  (`evidence/artifacts/gpt-harness-bakeoff-20261017/RANKING.md:3`). The Codex runner's default model is `gpt-6-astra`
  (`codex_job.py:193`), so this round measured a different model from the runner's default; the baseline is the same binary and a
  different model, not the runner's own configuration.
- Two known-answer tasks on a clone of the repository at `bfd139c347c73cf94eed2bf36eb7767dff082063`, two repetitions each, scored
  by script (`SCORES.json:2-5`):
  - **T1, code reading.** `tools/local-pages/atlas_map.json` cites `tools/sota-convergence/landscape-sweep/codex_job.py` with the
    anchor "Quota gate". Report the cited line and the line the anchor is on. Known answer: cited 76 at
    `bfd139c3:tools/local-pages/atlas_map.json:141`, actual 77 at `bfd139c3:tools/sota-convergence/landscape-sweep/codex_job.py:77`.
    Reply `{"cited": int, "actual": int}`; correct when the reply is 76 and 77.
  - **T2, edit and test.** Fix the stale citation so `tests.test_local_pages_atlas_data` passes, run that module with
    `python3 -m unittest`, and reply `{"changed_line": int, "tests_ok": bool}`. Correct reply: `changed_line` 77 and `tests_ok` true.
    Correct state: the file's line 141 holds 77 and the unittest exits 0.
- A loopback census (72 listeners, 0 violations) was read after the runs (`SCORES.json:6-11`).

## Measured

Source: `SCORES.json` `per_run`; the checker recomputes counts and medians and rejects stale aggregates before the test checks the
table. Wall medians retain the scores' two-decimal rounding before display; token display rounds halves up. Medians over two
runs; "reply" is the strict reply score, "state" is the recorded file-and-unittest check of the clone. Retained logs re-establish
usage and replies where available; absent raw events or timing receipts are explicitly bounded in caveats 1 and 6.

| Harness | T1 correct | T1 wall s | T1 tokens in+out | T2 reply correct | T2 state ok | T2 wall s | T2 tokens in+out |
| --- | --- | --- | --- | --- | --- | --- | --- |
| codex-exec (baseline) | 2/2 | 59.0 | 31,485 | 2/2 | 2/2 | 93.0 | 271,893 |
| pi | 2/2 | 4.4 | 2,168 | 2/2 | 2/2 | 46.0 | 17,856 |
| opencode | 2/2 | 65.9 | 5,075 | 1/2 | 2/2 | 100.1 | 26,053 |
| kilo | 2/2 | 94.8 | 6,250 | 0/2 | 2/2 | 57.8 | 15,624 |
| oh-my-pi | 2/2 | 8.6 | 9,977 | 0/2 | 2/2 | 59.0 | 33,128 |
| goose | 1/2 | 10.0 | 5,028 | 2/2 | 2/2 | 55.4 | 82,868 |
| openhands | 2/2 | 31.1 | 13,124 | 1/2 | 2/2 | 61.0 | 128,453 |
| deerflow | 2/2 | 11.0 | 26,590 | 0/2 | 2/2 | 50.9 | 104,266 |

- **All 16 edit-and-test clones were correct**: the file and the unittest were right in 2 of 2 runs for every harness
  (`SCORES.json` `t2_file_and_tests_ok`, 2 for each of the eight harnesses, e.g. `:46,102,158,214,270,326,382,438`).
- **Some replies were wrong while the state was right.** Eight of the 16 T2 replies reported `changed_line` 141 where the scorer
  wanted 77 (opencode rep 2, kilo both, oh-my-pi both, OpenHands rep 2, deerflow both; the other eight T2 replies, from the baseline,
  pi, goose and rep 1 of opencode and OpenHands, reported 77). Strict scoring counts the 141 replies as incorrect even where the file
  and unittest passed (`SCORES.json` `notes[0]`; the final replies extracted from every T2 log are in `T2-USAGE.json`).
- **Every T1 run answered correctly except one goose run, which did not complete**: goose T1 rep 1 exited 1 with a Responses
  stream-decode error and reported no usage (`SCORES.json:303`, `:464`).
- pi had the shortest median wall time in both classes (T1 4.4 s against 59.0 s for the baseline; T2 46.0 s against 93.0 s) and
  no incorrect reply in four runs. Its T1 reported in-plus-out column was the lowest. After cache normalization, T2 deerflow,
  goose and kilo are below pi; the medians and accounting groups are in caveat 3. These token figures are not prices.

## Caveats

Each limits what the table supports.

1. **Sample.** n = 2 per task per harness, two tasks, one model at one effort. No confidence interval is meaningful, and a
   harness's effect is confounded with its prompt, its tool schema and cache state. The baseline's T1 reps are recorded as 103 s
   and 15 s in `SCORES.json`; cold-then-warm cache is an untested explanation. T1 baseline event logs are not retained, and no
   controlled cache experiment is retained. These two times are historical score inputs, not an independently recovered timing.
2. **The T2 reply score is partly a wording effect.** The prompt does not define `changed_line`; 141 is the line of the edited
   file and 77 is the new value. The eight wrong T2 replies left a correct file (`RANKING.md:32`). Read the T2 reply column as an
   instruction-following measure on an ambiguous schema, not as editing quality.
3. **Token accounting differs across runtimes, and the reported columns are not like-for-like.** codex-exec, deerflow, goose and
   OpenHands include cached input; pi, OpenCode, Kilo and oh-my-pi report uncached input. Codex's source supports its class
   (`protocol.rs:2552-2554`); the other classes are observed in these pinned runs' usage events, not a guarantee for all providers.
   The public `T2-USAGE.json` extract retains each run's input, output, cached input, final reply and relative source name.
   Subtract cached input only for the inclusive group, add each runtime's reported output, then take the median over both runs:

   | Harness | T2 uncached input + reported output median |
   | --- | --- |
   | codex-exec | 37,141.0 |
   | pi | 17,855.5 |
   | opencode | 26,052.5 |
   | kilo | 15,624.0 |
   | oh-my-pi | 33,128.0 |
   | goose | 14,131.5 |
   | openhands | 26,116.5 |
   | deerflow | 9,801.5 |

   pi's apparent token advantage is overstated against codex-exec, deerflow, goose and OpenHands. It is not overstated on this
   basis against OpenCode, Kilo or oh-my-pi. DeerFlow, goose and Kilo are below pi on cache-normalized T2 tokens. This harmonizes
   cached input only; output/reasoning counters and prices have not been made uniform. goose's T1 median also includes the
   unmeasured failed run as zero; it is indicative only. `SCORES.json` and `RANKING.md` have declared corrections below.
4. **pi's model configuration was adjusted.** The CC's `diag-max.out` records `thinkingLevel` `high` when max was requested;
   `diag-max2.out` records `max` after setting `reasoning: true` plus a `thinkingLevelMap` in the agent-directory `models.json`.
   This effect is host-observed only: neither the schema nor the sampling example establishes the clamp mechanism, and no
   controlled mechanism reproduction is claimed. All scored pi session events record `thinkingLevel` `max`. `RANKING.md` also
   records an excluded initial hang and a rerun with null stdin; its cause and duration were not independently recovered.
5. **pi ran without its layers.** The pi runs used `--no-extensions --no-mcp --no-skills --no-context-files` (`RANKING.md:44`; the
   flags at `args.ts:189,191,210,216`). pi's documentation says it does not ask for approval before every tool call and has no
   built-in sandbox (`security.md:3,99`); an external OS boundary can restrict it. The round-1 record reports no such isolation.
   Its measured speed therefore does not establish performance with MCP, skills, instruction files or isolation enabled.
6. **The baseline ran differently.** codex-exec T2 ran `codex exec` directly rather than through `codex_call.sh`, a recorded
   departure (`RANKING.md:51`). For T2 only, the baseline received a typed `--output-schema` and a prompt with no repository path
   (`codex-exec/_in/t2.prompt`, with the clone as its working directory). Its T1 prompts (`_in/t1-1.prompt`, `_in/t1-2.prompt`)
   name clone paths; T1 baseline event logs are not retained. Other harnesses received the schema and clone path in prompt text.
   The T2 launch script and sandbox mode are not retained, so the wrapper's read-only mode cannot be attributed to that direct
   run. The model label is `gpt-6.1-sol`, not the runner's default `gpt-6-astra`; the Codex events do not independently record
   model or effort. Independent timing receipts are absent for Codex T2, pi and oh-my-pi; their times remain score-record inputs.
   The retained Codex T2 stderr contains ai-memory MCP `AuthRequired`; the scored jobs still completed.
7. **Effort is verified for pi only.** For opencode the run passed `--variant max`; for goose it set the thinking-effort
   environment variable to max; oh-my-pi's `run.py` passes `--thinking max`. Those logs do not confirm applied effort. No launch
   scripts are retained for Codex, Kilo, DeerFlow or OpenHands; their applied effort is unverified. pi and oh-my-pi events name
   `cx/gpt-6.1-sol`; the other harnesses' model labels rest on the original ranking rather than event confirmation.
8. **goose has a stream-decode failure** (T1 rep 1, `SCORES.json:303`), which `RANKING.md:43` treats as disqualifying for now. One failure in
   two runs is a signal to investigate, not a rate.
9. **Wall times** are single-machine, under a memory gate and varying load (`RANKING.md:52`).

## Untested boundaries

Not measured, and therefore not claimed: multi-file edits, long runs, tool-heavy tasks, failure recovery, concurrency, sandbox
behaviour, MCP and skill use under load, telemetry, role isolation and invoke receipts (`RANKING.md:53`). The harnesses were run
outside the repository's runtime profiles: `runtime_profiles.py:77-98` admits only pi 1.1.0 and opencode 1.18.35, so none of the eight
ran at an admitted pin through its isolation and MCP layers.

## Proposal (not adopted)

For the command center to dispose; nothing here is applied.

- **pi is a measured fast-path candidate for bounded read-and-edit jobs.** It was correct and fastest on both task classes. It may
  not become a default on this evidence: `AGENTS.md:7` requires a converged harness with its full layers, and this round ran pi with
  MCP, skills and context files off and with no recorded external OS isolation (caveats 4 and 5). A candidate path first requires
  the evidence-bound reopen of its refuted fit, then a layer screen at its pin (MCP, skills, hooks, telemetry, isolation, receipts).
- **`codex exec` stays the default and the fallback** for sandbox-governed read-only jobs, typed output schemas and anything that
  needs its MCP and skill layers.
- The other harnesses that tied on T1 correctness (opencode, kilo, oh-my-pi, deerflow, OpenHands) stay untested alternates.
  oh-my-pi, deerflow and OpenHands were also faster than the baseline on T1; opencode and kilo were slower. goose waits on its
  stream-decode failure. None receives a new fit adjudication here.

## Round 2 (the delta)

**Comparison id:** `gpt-harness-bakeoff-round-2`. The proposed preregistration and frozen scope are retained in
`evidence/artifacts/gpt-harness-bakeoff-20261017/ROUND2-PREREGISTRATION.json`; preregistration hash (SHA256 of the exact file bytes):
`5655b151c54803c856029ff610797677a80b5d8e5bd4e6cef2870889cde6a2c4`.
The frozen scope is all eight round-1 harnesses at their recorded commits, `cx/gpt-6.1-sol`, max effort, three repetitions of each
of the five task classes below and the fixed decision rule. This is a proposal, not SCHEDULED: profile adoption, the reopen and
the fully hash-bound task/launch input manifest are still missing. No comparison or layer closure is claimed. Before running,
retain that reviewed input manifest under the comparison id and scope hash with exact fixtures, prompts, schemas, scorers,
ordering and resource limits; any change to the frozen scope requires a reviewed superseding registration before a run.

**Readiness trigger (named inputs, no date):** the comparison starts only after all registration inputs exist. They include the
evidence-bound reopen and survivor dispositions above; a profile-adoption decision for each missing harness; reviewed pin
admission and native qualification; rendered isolation, MCP, skills, hooks and telemetry; and a write-capable baseline plus a
successful edit-and-test smoke for every arm through its exact recorded launch path. Each smoke must retain its argv, allowed
writable roots, correct edit, passing unittest and invoke receipt. A failed or missing smoke blocks the comparison, rather than
becoming a scored failure of an arm denied write access.

`tools/adoption/runtime_profiles.py` currently admits only pi 1.1.0 and opencode 1.18.35. Re-pin and requalify those profiles at the
frozen commits. Kilo, oh-my-pi, goose, OpenHands and DeerFlow have no entries: adopt and implement their proposed profiles before
launching them. Every arm's intended write-mode path is retained in the registration and named here:

| Arm | Write-mode harness path required before readiness |
| --- | --- |
| codex-exec | `tools/sota-convergence/landscape-sweep/codex_call.sh` → `codex_job.py`: reviewed `workspace-write` mode in an isolated task clone; absent today |
| pi | `tools/adoption/runtime_profiles.py launch pi-gpt --role isolated-builder` in the isolated task clone, after requalification |
| opencode | `tools/adoption/runtime_profiles.py launch opencode-gpt --role isolated-builder` in the isolated task clone, after requalification |
| kilo | `tools/adoption/runtime_profiles.py launch kilo-gpt --role isolated-builder`: proposed entry, adoption required |
| oh-my-pi | `tools/adoption/runtime_profiles.py launch oh-my-pi-gpt --role isolated-builder`: proposed entry, adoption required |
| goose | `tools/adoption/runtime_profiles.py launch goose-gpt --role isolated-builder`: proposed entry, adoption required |
| openhands | `tools/adoption/runtime_profiles.py launch openhands-gpt --role isolated-builder`: proposed entry, adoption required |
| deerflow | `tools/adoption/runtime_profiles.py launch deerflow-gpt --role isolated-builder`: proposed entry, adoption required |

The current `codex_call.sh` wrapper forces read-only mode even for an isolated-builder role. Round 2 requires a reviewed
write-capable mode in that wrapper and its edit-and-test smoke before it can start. Round 1's successful direct T2 edits do not
qualify that wrapper. The named profile paths are requirements to qualify, not claims that the missing entries already work.

**Design:**

- Every harness runs through its repository runtime profile, with its isolation and MCP layers, at the re-pinned version.
- Tasks: a multi-file edit, a long tool-heavy task and a concurrency task (several jobs at once on one gateway), plus the two
  round-1 tasks with an unambiguous reply schema (the edited file line and the new value as separate fields), enforced by the
  harness's structured-output mode where it has one and checked from the clone's state either way.
- n of at least 3 per task per harness (the frozen scope fixes n = 3), the same prompt text and reply schema for every harness,
  and the baseline run through the reviewed write-capable `codex_call.sh` mode on the same model.
- Uniform token accounting: record uncached input, cached input and output separately per run from each runtime's own usage
  events, and rank on uncached input plus output with cached input reported beside it.
- Effort verified per runtime from that runtime's event log or the gateway's request record, and a run whose applied effort
  cannot be shown is reported as unverified.
- The measurement uses an existing harness named in the resolution protocol (promptfoo, token-e2e or paired runs), or is adopted by
  its own reviewed decision first; retain its exact pin and command in the input manifest before readiness. Round 1's per-harness
  driver scripts stayed CC-local and are not an adopted comparison harness.

**Fixed decision rule:** a harness is proposed for any default role only when, on every task, its state-correct and reply-correct
counts are at least the baseline's, its median wall time or its median uncached tokens is lower with the other not worse, and it
shows MCP, skills, hook equivalents, telemetry, isolation and invoke receipts under its profile. A harness that misses any term is
recorded with the missed term and does not change a default.

## Alternatives considered

- Route pi into the GPT lane now: rejected. Its fit is refuted in the latest covering sweep and its fast runs omitted the layers
  required of a default. Record the measurement as changed evidence; require a sweep-bound reopen and qualified comparison.
- Rank on the original token totals alone: rejected. Cache accounting differs; the cache-normalized T2 comparison even places
  DeerFlow and goose below pi. Output/reasoning and monetary cost remain unharmonized.
- Run round 2 through the current read-only Codex wrapper: rejected. A read-only baseline cannot complete the edit tasks.
  Qualify a write-capable launch and a successful smoke for every arm first.
- Start a new broad survey or silently drop the existing survivors: rejected by the resolution protocol. Address the bounded
  changed evidence and explicitly dispose of the cumulative survivor set before a terminal claim.

## Inverse

No runner or runtime default was changed. Withdraw the proposal through a reviewed supersession of this record and its proposed
registration, retaining the measurement and correction history. Reverting this publication must also restore or remove its
evidence rows using the repository tools; it is not a runtime rollback.

## Overturn condition

A retained-log mismatch overturns the affected measurement claim and requires a cited correction with a failing regression.
The proposed pi fast path is overturned if the evidence-bound fit reopen fails or the qualified round-2 comparison misses any
term of its fixed rule. A default change requires that comparison and full-layer convergence evidence; this record authorizes no
default adoption. New evidence changing a frozen comparison input requires a reviewed superseding registration before execution.

## Public copies and privacy

The originals of `SCORES.json` and `RANKING.md` stay on the host. The public copies preserve their measured run values and tables.
The following are the declared substitutions relative to those originals; each stays on its original line:

- `SCORES.json:7`, the `census.file` value, a home-directory path to the host's loopback-census state file, is replaced with the
  placeholder `<private census state file>` (the repository's host scan failed on the original line).
- `RANKING.md:3`, the leading `Source:` locator, a scratch path on the host, is replaced with the bare name `SCORES.json`.
- `SCORES.json:465`, `notes[2]`, and `RANKING.md:38`, the token-accounting bullet, now identify both accounting groups explicitly.
  The original statement that all non-Codex inputs were uncached was false. The correction follows the usage events at the pins
  above, retained numerically in `T2-USAGE.json`, and the Codex `non_cached_input` mechanism at `protocol.rs:2552-2554`.
- `RANKING.md:36` labels the pi configuration effect host-observed and the excluded hang as originally recorded, without claiming
  an independently established cause. `:42` confines the T1 comparison to reported columns; `:45` makes the fast path a proposal
  pending the fit reopen and layer screen. `:49` marks the cold-cache attribution unconfirmed because T1 baseline logs are absent.

Raw per-harness logs, run scripts and clones stay on the host and are cited here by relative names only. Following the
public-copy practice of [the currency sweep record](2026-10-17-currency-sweep-repin.md), their locators are not published.

## Verification

`recompute.py` derives counts and medians from `per_run` only after requiring exactly two uniquely numbered runs for every task
and harness, and rejects stale stored aggregates. With an explicit raw-root input, it checks the published T2 usage extract and
all retained usage/reply events and timing receipts; unavailable raw inputs remain historical score values. It does not rerun
any model or the clone tests. The tests cover missing, empty and duplicate runs, changed measurements with stale aggregates,
both measured tables, cache-normalized medians, reply values and the per-harness split, time figures in prose, the resolution
gaps, proposal boundaries, prerequisites, registration hash and publication privacy. They do not pin every sentence or treat
host-observed causes as source-proven mechanisms. The required test-only overlay against the reviewed head has not run in this
build: the specified scratch location is read-only in the sandbox. Passing workspace tests do not establish that fail-first result.
The repository's own checks (`scripts/validate.py`, `scripts/evidence_manifest.py --check`,
`tests.test_local_pages_policy_grants`) and their results are in the pull request.
