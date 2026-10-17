# Decision: GPT-lane harness bake-off, round 1 — a measurement record and a proposal, no routing change (2026-10-17)

Status: measurement recorded; the outcome is a **proposal** for the command center. No runtime default, lane runner, profile or
catalog changes in this record. Scope: eight agent harnesses driven through one gateway lane with one model and one effort.

## What this changes

- Adds the round-1 scores and ranking as evidence, in
  [`evidence/artifacts/gpt-harness-bakeoff-20261017/`](../../evidence/artifacts/gpt-harness-bakeoff-20261017/)
  (`SCORES.json`, `RANKING.md`), registered in `manifests/evidence.json`.
- Adds this record and `tests/test_gpt_harness_bakeoff_round_1.py`, which pins the table below to `SCORES.json`.
- Changes nothing else. `codex exec` (through the Codex runner `tools/sota-convergence/landscape-sweep/codex_call.sh`) stays the
  default and the fallback of the GPT lane.

## Layer resolution consumed

The [resolution protocol](2026-10-11-layer-resolution-protocol.md) was followed for the layer this touches, `agent-sdks`
(Agent SDKs and runtime workers):

- Catalog verdict: `catalogs/landscape/foundation.json:4577` (current choice: Codex SDK/CLI for supported start/run/resume; the
  OpenHands SDK among the source-reviewed, unselected alternatives) and `:4661` (`verdict_status` `recorded`).
- Latest sweep covering the layer: `landscape-sweep-20260929`, `catalogs/saturation/ledger.json:7694` (sweep) and `:10396` (the
  `agent-sdks` row, with its `survived[]`, `refuted[]` and `reopen[]`; the reopen triggers are `pin_moved` receipt-staleness
  entries for the Codex receipts).
- This round was **not a preregistered comparison**. It adjudicates no survivor, settles no unresolved vote and changes no verdict
  or wave; it is a first-hand measurement of one disputed dimension (speed, token use and reply fidelity per harness on one model),
  taken because the runtime matrix screened several harnesses as `pass` for the same gateway lane. Round 2 below is the delta, and
  carries the readiness trigger and decision rule the protocol requires of a comparison.

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
  `max`; `thinkingLevelMap` holds provider values; `reasoning` marks a model that thinks). The flags the pi run used are parsed at
  `packages/coding-agent/src/cli/args.ts:189` (`--no-extensions`), `:191` (`--no-mcp`), `:210` (`--no-skills`) and `:216`
  (`--no-context-files`). pi's own statement of its safety model: `packages/coding-agent/docs/security.md:3` (it runs with the
  permissions of its user and does not ask for approval before every tool call) and `:99` (no built-in sandbox).
- The repository's Codex runner: `tools/sota-convergence/landscape-sweep/codex_job.py:14-18` (the exact `codex exec` argv:
  `--ignore-user-config -s read-only -m gpt-6-astra -c model_reasoning_effort="max" --output-schema`) and `:193`
  (`DEFAULT_MODEL = "gpt-6-astra"`).
- The repository's profile code for harness runs: `tools/adoption/runtime_profiles.py:77-98` (`verify_runtime_binary` admits only pi
  1.1.0 and opencode 1.18.35).

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

Source: `SCORES.json`; the table is derived from it and the test pins it. Medians over two runs; "reply" is the strict reply
score, "state" is the file-and-unittest check of the clone.

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
  wanted 77 (opencode 1 of 2, kilo 2, oh-my-pi 2, OpenHands 1, deerflow 2; the other eight T2 replies, from the baseline, pi, goose
  and one each of opencode and OpenHands, reported 77). Strict scoring counts the 141 replies as incorrect even where the file and
  unittest passed (`SCORES.json:463`; each run's final reply was read from its log for this record).
- **Every T1 run answered correctly except one goose run, which did not complete**: goose T1 rep 1 exited 1 with a Responses
  stream-decode error and reported no usage (`SCORES.json:303`, `:464`).
- pi had the shortest median wall time in both classes (T1 4.4 s against 59.0 s for the baseline; T2 46.0 s against 93.0 s) and
  no incorrect reply in four runs; its T1 in-plus-out tokens were the lowest, while in T2 kilo's were lower (15,624 against pi's
  17,856; `RANKING.md:9-30`, subject to caveat 3).

## Caveats

Each limits what the table supports.

1. **Sample.** n = 2 per task per harness, two tasks, one model at one effort. No confidence interval is meaningful, and a
   harness's effect is confounded with its prompt, its tool schema and cache state (the baseline's T1 reps took 103 s and 15 s, a
   cold-then-warm cache; `RANKING.md:49`).
2. **The T2 reply score is partly a wording effect.** The prompt does not define `changed_line`; 141 is the line of the edited
   file and 77 is the new value. The eight wrong T2 replies left a correct file (`RANKING.md:32`). Read the T2 reply column as an
   instruction-following measure on an ambiguous schema, not as editing quality.
3. **Token accounting differs across runtimes, and the figures are not like-for-like.** The baseline's `tokens_in` includes cached
   input (`SCORES.json:465`; upstream at `protocol.rs:2552-2554` above). That note says the others report uncached input
   separately; the logs show this holds for pi only (pi T2 rep 2 held 69,504 cached tokens outside its total, `SCORES.json:466`).
   OpenHands' own usage line for T2 rep 1 reads `in` 102,034 with `cached` 81,536, and goose's T2 rep 1 reports `input_tokens`
   67,956 with `cache_read_input_tokens` 56,704, so both of their in-figures also include cached input (`openhands/T2-1/out.log` and
   `goose/T2-1/out.json` in the CC-local run directory). Which of opencode, kilo, oh-my-pi and deerflow include cached input was
   not established. pi's token advantage is therefore overstated, and the token columns are indicative only. goose's T1 median
   (5,028) also includes the unmeasured rep 1 as zero, so it is about half of the one measured run (`SCORES.json:464`).
4. **pi's model configuration was adjusted.** pi needed `reasoning: true` plus a `thinkingLevelMap` in its agent-directory
   `models.json`, otherwise max effort was clamped (`RANKING.md:36`; the keys are in pi's schema at the `model-config.ts` lines
   above). With that, pi's session events record `thinkingLevel` `max`. pi's first attempt hung for 900 s on an inherited stdin
   and was rerun with stdin from the null device; the hung attempt is not counted (`RANKING.md:36`).
5. **pi ran without its layers.** The pi runs used `--no-extensions --no-mcp --no-skills --no-context-files` (`RANKING.md:44`; the
   flags at `args.ts:189,191,210,216`), and pi has no OS sandbox or approval gate (`security.md:3,99`; the runtime matrix lists the
   same). Its speed was measured without MCP, skills, instruction files or isolation.
6. **The baseline ran differently.** codex-exec T2 ran `codex exec` directly rather than through `codex_call.sh`, a recorded
   departure (`RANKING.md:51`). The baseline also received a typed `--output-schema` and a prompt that names no repository path
   (it ran in its clone's directory), where the other harnesses got the schema in the prompt text and the clone's path in the
   prompt; the model was `gpt-6.1-sol`, not the runner's default `gpt-6-astra`. The benign ai-memory MCP `AuthRequired` stderr it
   printed had no effect on the jobs (`RANKING.md:37`).
7. **Effort is verified for pi only.** For opencode the run passed `--variant max`; for goose it set the thinking-effort
   environment variable to max; for OpenHands no run script was kept with the logs. None of the three logs confirms the effort the
   provider received, so "effort max" is the setting passed, not a verified application, for opencode, goose and OpenHands, and
   this record did not check the other harnesses' event logs.
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
  MCP, skills and context files off and with no OS sandbox (caveats 4 and 5). A candidate path would first pass a layer screen at its
  pin (MCP, skills, hooks, telemetry, isolation, receipts).
- **`codex exec` stays the default and the fallback** for sandbox-governed read-only jobs, typed output schemas and anything that
  needs its MCP and skill layers.
- The other harnesses that tied on T1 correctness (oh-my-pi, deerflow, OpenHands) stay untested alternates; goose waits on its
  stream-decode failure.

## Round 2 (the delta)

**Readiness trigger (named inputs, no date):** the comparison starts when `tools/adoption/runtime_profiles.py` admits each harness
at the pin to be measured (today it admits pi 1.1.0 and opencode 1.18.35 only; the matrix screened pi 1.3.0 and opencode 1.19.3), and
renders that harness's isolation and MCP layers.

**Design:**

- Every harness runs through its repository runtime profile, with its isolation and MCP layers, at the re-pinned version.
- Tasks: a multi-file edit, a long tool-heavy task and a concurrency task (several jobs at once on one gateway), plus the two
  round-1 tasks with an unambiguous reply schema (the edited file line and the new value as separate fields), enforced by the
  harness's structured-output mode where it has one and checked from the clone's state either way.
- n of at least 3 per task per harness, the same prompt text and reply schema for every harness, and the baseline run through
  `codex_call.sh` on the same model.
- Uniform token accounting: record uncached input, cached input and output separately per run from each runtime's own usage
  events, and rank on uncached input plus output with cached input reported beside it.
- Effort verified per runtime from that runtime's event log or the gateway's request record, and a run whose applied effort
  cannot be shown is reported as unverified.
- The measurement uses an existing harness named in the resolution protocol (promptfoo, token-e2e or paired runs), or is adopted by
  its own reviewed decision first; round 1's per-harness driver scripts stayed CC-local and are not a harness.

**Fixed decision rule:** a harness is proposed for any default role only when, on every task, its state-correct and reply-correct
counts are at least the baseline's, its median wall time or its median uncached tokens is lower with the other not worse, and it
shows MCP, skills, hook equivalents, telemetry, isolation and invoke receipts under its profile. A harness that misses any term is
recorded with the missed term and does not change a default.

## Public copies and privacy

The originals of `SCORES.json` and `RANKING.md` stay on the host. The public copies keep every byte except two substitutions,
both on one line each and neither changing a number or the line count:

- `SCORES.json:7`, the `census.file` value, a home-directory path to the host's loopback-census state file, is replaced with the
  placeholder `<private census state file>` (the repository's host scan failed on the original line).
- `RANKING.md:3`, the leading `Source:` locator, a scratch path on the host, is replaced with the bare name `SCORES.json`.

Raw per-harness logs, run scripts and clones stay on the host and are cited here by relative names only. Following the
public-copy practice of [the currency sweep record](2026-10-17-currency-sweep-repin.md), their locators are not published.

## Verification

`tests/test_gpt_harness_bakeoff_round_1.py` fails on the base: it needs the two evidence files, this record, and the match between
the table above and `SCORES.json` (its derived medians, correct counts, the 16 of 16 state check, the wrong-reply count and the
absence of private-locator shapes in the three published files). The repository's own checks (`scripts/validate.py`,
`scripts/evidence_manifest.py --check`, `tests.test_local_pages_policy_grants`) and their results are in the pull request.
