# model-routes initial sweep: Claude-family half (2026-10-15)

**Status: single-family (Claude) initial sweep, sealed. Not a ledger sweep.** The layer stays reopened until this
half and the GPT-family half (PR #1177, head `6ecd0e74`) are merged as `MERGE-PLAN.md` describes. The merged result
supports TRIAL labels on NativeHorizonNY only, never FINAL. No catalog, `catalogs/sota-convergence/` or
`catalogs/saturation/ledger.json` file is edited.

## Authority

- The CC's ruling of 2026-10-15T19:52Z, option (A): run the Claude roles now from the co-op, as
  `landscape-sweep-worker` agents (Claude Opus 5.5, effort max). Use the frozen `templates.json` and schemas at
  `8053f14e7` and the recipe labels. Hash the hand-built layer input, run the stages one at a time with usage measured
  between them, and cap spend at $40. Stay blind to the GPT half until both seal.
- The owner direction is recorded in the CC's record `direction-cc-20261015T1912Z-new-wsl-harness-first.md`
  (`research-cc-role-20261008/`, kept privately and cited by name only), ruling 2: the Models row names
  model-routes. Its addenda 01-09 refine the harness scope.

## Protocol steps 1-3 (docs/decisions/2026-10-11-layer-resolution-protocol.md), at 8053f14e7

- There is no catalog verdict for model-routes in `catalogs/landscape/foundation.json` (0 occurrences), no row in
  `research-state.json` (0 occurrences), no wave in `catalogs/sota-convergence/layer-verdict-waves.json`, and no sweep
  of `(foundation, model-routes)` in `catalogs/saturation/ledger.json`.
- `catalogs/landscape/final-stack.json` lists the layer as `unswept`, with 0 winners and 0 survivors. Its source is
  `catalogs/landscape/angles/foundation-model-routes.json` (14 carried candidates: 13 INSUFFICIENT, 1 REJECTED).
- The bounded next action is therefore an initial sweep scoped to the gap. Registration of the layer is separate work
  (PR #1179, under #1130's pending-empty path).

## How it ran

The harness's own `build_args.py` staged the run (`--layers model-routes --no-stars`, date 2026-10-15) into a work
directory outside every repository. That fixes the templates and schemas and gives
`prompts_sha256 = f8263a7b7cce54784278ac909ecb1ab5e83376411891b3e4880fd134df516a7d`, which recomputes from tracked
files with the harness's own code (`prompts_sha256_rule` in `hashes.json`). The GPT-6 lane was not run.
Three Workflow runs executed the Claude stages. Each stage script is sweep.js's own prompt code for that role,
reproduced verbatim with the staged args embedded. The generators are in
`../model-routes-sweep-claude-20261015-attempts/`.

| Stage | Workflow run | Label | Measured model, effort | Requests | WebSearch (capped) |
|---|---|---|---|---|---|
| 1 discover | `wf_424f30f4-0af` | `discover:model-routes` | claude-opus-5-5, max | 69 | 10 (0) |
| 2 refute | `wf_27e93022-5c0` | `refute-facts:model-routes` | claude-opus-5-5, max | 69 | 0 (0) |
| 2 refute | `wf_27e93022-5c0` | `refute-fit:model-routes` | claude-opus-5-5, max | 42 | 0 (0) |
| 3 critic | `wf_d251d8c8-3b7` | `critic` | claude-opus-5-5, max | 50 | 1 (0) |

Usage comes from the three `child-usage-*.json` records (`usage_record.py` over each run's transcripts; status
complete, every child at effort max). The cost estimate below uses list prices from the claude-api skill at its manifest pin
`anthropics/skills@dbd4588f9e1033efb41dad4bef2f7947c8993d44`: $4 input, $20 output and $0.20 cache read per MTok for
Claude Opus 5.5 (`skills/claude-api/shared/models.md:79`; cache reads 0.05x input, `shared/prompt-caching.md:144`).
The same line gives the cache-write rate per TTL: 1.25x input for the 5-minute TTL and 2x for the 1-hour TTL. The
usage records count cache writes without their TTL (`cache_creation_input_tokens` only), so the estimate ASSUMES that
every write used the 1-hour TTL, at $8 per MTok. That is an upper bound: the assumption is the TTL, not the rate. At
the 5-minute TTL ($5 per MTok) the total would be about $21.48. Discover ~$8.34, facts ~$6.58,
fit ~$4.87 and critic ~$5.08 come to about $24.86. Advisor calls inside workers are not counted. This is an estimate,
not a bill.

Hashes (`../model-routes-sweep-claude-20261015-attempts/hashes.json`) bind published bytes only:

- `prompts_sha256` (above), which recomputes from tracked files;
- the published layer input: `63aed082dc3fccd336c75e0ba74252f371a60607d92553248761d09163ea019b`;
- returns: `498651465682013d9e8c668b0f1aa0c9d936f51c3c7fed6612d80fb71292f5e6`.

The originals behind the run stay private: the unmasked layer input, the three stage scripts as run (they embed the
work-directory path), the merged proposal list (before convert.py's path redaction), the three run records, the
synthesized return and the scope copies. `hashes.json` names each under `unpublished_originals`, with no digest of any
kind (correction #161, `tests/test_provenance_digest_custody.py`).

## Deviations from sweep.js, each deliberate

1. **Hand-built layer input.** model-routes is not a registered catalog layer, so `build_inputs.py` cannot write
   it. `layer-input.json` has the V1 shape. Its `requirement_sha256` uses the ledger's own rule
   (`scripts/saturation_ledger.py:524` `requirement_sha256` over `next_action` and `decision_ref`, at 8053f14e7), and `platform_profiles_sha256` comes
   from `saturation_ledger.py --scope`. The workers read the unmasked layer input, which is kept privately in the
   co-op work directory, with no digest published. The published copy masks the host worktree path; deviation 7
   covers its `decision_ref`.
2. **Carried-set rule.** `layer_instructions` asks discovery to adjudicate all 14 carried candidates outside the cap
   of 6 new proposals, so that the refuters vote on all 14 and the merge has three votes per carried candidate.
3. **No MAX_PROPOSALS cut.** All 19 proposals went to both refuters; sweep.js cuts to 8
   (`tools/sota-convergence/landscape-sweep/sweep.js:37` at 8053f14e7, `const MAX_PROPOSALS = 8`).
4. **Stages as separate runs.** This enforces the $40 cap between stages.
5. **Single family.** The GPT-6 discovery and fit lanes were not run. The critic summary marks this as
   `gpt6_discover_status: not_run_single_family_claude_half`.
6. **Follow-up round not run.** The critic flagged model-routes. A follow-up round (discover, facts and fit, about
   $20) would have passed the $40 cap, so it is recorded as a lost round. `convert.py` therefore records a
   `retained_failure`.
7. **Published `decision_ref` names the record only.** The workers' copy of the input carried the CC direction
   record's digest in `decision_ref`. The published input names the record only (CC full read, 2026-10-15), so
   `requirement_sha256` is recomputed over the published `next_action` and `decision_ref` with the same rule
   (`scripts/saturation_ledger.py:524`). The requirement's meaning is unchanged: the same next action, the same record
   and the same ruling. The scope copy of the second conversion carries the recomputed value.
8. **One joined usage record.** `convert.py --usage` reads one usage record (`convert.py:762`), and each of the three
   stage runs has its own. `join_usage.py` copies the children of all three, unchanged, into `usage-joined.json`,
   which the second conversion reads.

## Result (returns.json; convert.py at 8053f14e7 over the synthesized return, with --usage)

`git diff 8053f14e7 a93ba0b8c` is empty for `tools/sota-convergence/landscape-sweep/`, `scripts/saturation_ledger.py`
and `scripts/host_receipts.py`, so the same tools hold at this branch's base.

`returns.json` is the second conversion (CC full read, 2026-10-15). It used the first conversion's synthesized return,
work directory and `--limit` note, the scope copy with the published `requirement_sha256`, and
`--usage usage-joined.json`. Against the first conversion it changes only the discovery's `requirement_sha256` and the
model and effort of the 38 Claude votes, which now name the measured `claude-opus-5-5` at effort `max` instead of the
alias `opus` with effort null. No `effort_deviation` or `web_search_capped` failure is retained: every child ran at
effort max, and no WebSearch call was capped. The counts below are unchanged.

- 19 proposals: all 14 carried candidates labelled, plus 5 new:
  - `claude-code-claude-fable-5-1`;
  - `diegosouzapw/OmniRoute`;
  - `anthropic-api-claude-opus-5-5`;
  - `muse-code-spark-subscription`;
  - `codex-omniroute-gpt-6-1-sol`.
- Labels: 7 targeted_candidate, 11 keep_but_compare, 1 not_adopted.
- The facts refuter refuted 0 of 19.
- The Claude fit refuter refuted 8 of 19:
  - `muse-code-wonder-api`, `codex-wonder-api`, `opencode-wonder-api`, `claude-code-wonder-api`;
  - `harness-spark-api`;
  - `claude-code-claude-sonnet-5-5`;
  - `openai-pool-foreign-harness`;
  - `muse-code-spark-subscription`.
- This half has 0 survivors, as a single family must: the GPT-6 fit vote is missing, so every proposal is refuted
  under the two-family rule. The other 11 are refuted only by absence. No returned vote refutes them, so they are not
  adjudicated on merit, and they carry into the merge.
- Retained failures: the GPT-6 discovery family missing; the GPT-6 fit votes missing; the follow-up round lost
  (cap). The layer's reopen entry is `retained_failure`.
- The facts refuter corrected discovery: the Muse Code changelog lists 1.4.8 and 1.4.9 above the 1.4.7 fence pin. The
  fence was re-qualified at 1.4.9 the same day; its receipt is the co-op record
  `lanes/sdk-harness-ready.muse-requal-149-receipt-20261015T2125Z.md`, kept privately and cited by name only.

## The critic's missed classes (seeds for the merge round or the registered two-family sweep)

1. **Family (a): Claude Agent SDK and Managed Agents on the Console API credits.**
   `platform.claude.com/docs/en/about-claude/api-credits-for-subscribers` (read 2026-10-15) says the credits cover the
   Claude API, Managed Agents and the Agent SDK, but not Claude Code.
2. **Family (b): per-user ChatGPT sign-in in a non-Codex harness (OpenCode).** Source: `opencode.ai/docs/providers`.
   An entitlement statement from OpenAI itself is still needed.
3. **Family (b): a gateway comparator to OmniRoute, `router-for-me/CLIProxyAPI`.** It should be judged against
   `developers.openai.com/codex/enterprise/gateway-compatibility`.
4. **Family (c): the Muse programmatic client surface.** The `muse serve` session protocol and SDK arrived in 1.4.8,
   and `muse exec` in 1.4.9. Whether the subscription covers connected apps is open.

## Independence disclosure

The co-op coordinator built `layer-input.json` from repository files at `8053f14e7` and the CC's scope only. It saw
one line of the GPT half before that point: the GPT lane's `R PR-OPENED #1177` notice at 19:55Z, summarizing "14
carried + Fable 5.1, no formal survivors". Nothing from that notice or from #1177's content entered the Claude inputs
or prompts. The discovery worker found `claude-code-claude-fable-5-1` independently, from `code.claude.com` model
configuration documentation. The layer instructions told workers not to read PRs or `model-routes-sweep-*` artifacts
from the other half.

## Corrections after the CC's full read (2026-10-15)

The CC's full read of the PR's first head (verdict `MICRO-full-afcc08cb.md`, kept privately) found digests of
unpublished bytes in this record. They are removed: `hashes.json` names the private originals without any digest, the
CC direction record and the Muse receipt are cited by name only, `requirement_sha256` is recomputed over the published
fields (deviation 7), and `returns.json` is reconverted with `--usage` (deviation 8). The cost section now states the
TTL as the assumption, and `MERGE-PLAN.md` labels the vendor-document capture a PROPOSAL.
`tests/test_provenance_digest_custody.py` (`ModelRoutesClaudeHalfCustodyTests`) checks every digest in this record's
two directories. The PR branch was rebuilt as a single commit under the CC's ruling (2026-10-15), and GitHub may keep
the earlier commit in the PR timeline. That earlier head, `afcc08cbc` (tree `f64abddb4f9b84821c94d077761d3108c68d5da6`),
is the fail-first state: run against its tree, the four custody tests fail (10 digests with no published preimage, 3
digest-bearing citations of the direction record, 6 shortened digests, no private-originals list), and they pass on the
rebuilt commit.
