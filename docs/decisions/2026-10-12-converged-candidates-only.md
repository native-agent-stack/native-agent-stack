# Decision: use only converged candidates, through a converged harness (2026-10-12)

**Status:** foundation rule text on the owner's directions. The six repository rule surfaces change together in this
PR; the user-level files follow only after it lands (below). **Supersession:** no decision record is superseded. This
extends the existing "Decide by evidence" rule and amends one clause of it ("alone", below), and the same word in the
long form of the rule in `docs/harness-defaults.md`. The CC's own supersessions of its rulings are recorded in its
rulings (Basis).

## The rule

The "Decide by evidence" bullet changes in two places.

**The not-evidence clause** gains one word:

> Agreement, recency, popularity and incumbency alone are not evidence.

It was "Agreement, recency, popularity and incumbency are not evidence." Under multi-angle convergence, community
consensus and net usage are angles of the evidence; none of them decides alone.

**Two sentences** go at the end of the bullet, after "Keep measured results, simulations and untested boundaries
distinct.", in this order:

> Use only converged candidates: a tool, runtime, model or skill is installed or run for trial only after the layer's screen (its requirements checked at a pin) passes it, and becomes a default only when the layer's multi-angle convergence agrees (capability at the pin, upstream engineering quality, community consensus, net usage, published evaluations and our own measured runs); where angles disagree, measure the disputed dimension first-hand, and no single angle makes a candidate a default.

> Use models only through a converged harness with its full layers (skills, MCP, hook equivalents, memory and token efficiency, telemetry, isolation and roles, invoke receipts); a bare API call is for measurement probes and smokes only, recorded as such.

| Text | UTF-8 bytes | Words | SHA256 |
| --- | ---: | ---: | --- |
| Converged candidates | 495 | 75 | `3cc237d3559648b6600db3bb40674899770e4d7df51a2ba2db8bddd02ca20540` |
| Converged harness | 252 | 39 | `f91075feb66ac3aa83d8fe8df3a2cde36b61df05c453306b735a75153c32429f` |

Each hash is over the quoted sentence's own bytes, without the Markdown `> ` or a newline. With one leading space for
each sentence and " alone" in the clause, every copy grows by 496 + 253 + 6 = 755 bytes.

**The screen and the default.** "The layer's screen" is angle A1: the layer's requirements, checked against the
candidate's own documentation and source at a pin. It runs nothing, so it admits a trial only. A default needs the
other angles too, and no one angle, a screen pass included, makes a candidate a default.

**Earlier wordings on this branch.** They never reached main; each was replaced by a fast-forward commit, not an amend.
The branch was rebased onto main `703d588c` before review round 1, changing only `manifests/evidence.json`; the commit
ids below are the rebased ones.

| Commit | First sentence, as then worded | Why replaced |
| --- | --- | --- |
| `e18efdcc` | "...is installed, run or made a default only after the layer's own convergence passes it on quality and SOTA standing (a screen pass or a measured win)..." | A screen pass alone could make a default, and a screen pass is not quality evidence (above). |
| `d945f4ce` | the same; the harness sentence added after it | - |
| `e4d8f694` | "...installed or run for trial only after the layer's own screen passes it, and becomes a default only after a measured win on quality at no higher cost..." | The owner's 20:29Z direction: our own measurement is one angle, not the decider. |
| `37577653` | "...after the layer's screen passes it, and becomes a default only when the layer's multi-angle convergence agrees (...) ...and no single angle admits a candidate on its own." | Review round 1: "admits" contradicted the trial a screen pass allows, and "the layer's screen" was undefined. |

## Basis

The command center's (CC) rulings cited here are private coordination records outside this repository. They are cited
by name only; this record restates what it relies on, in paraphrase.

**The converged-candidates sentence.**
- **The owner's direction, 2026-10-12, 19:57Z and 19:58Z** (paraphrased, not quoted): use only SOTA candidates that
  the current landscape's convergence has passed. It is a foundation rule: research-driven, and also about the
  candidate's quality and SOTA standing.
- **CC record:** addendum 01 to the CC's harness-stack ruling, written on that direction. It holds **CC correction
  #192**: two arms had been listed for a comparison without passing a screen, one of them admitted from a usage list.
  The fix keeps only documented passers and incumbent trials as arms; the two enter the screen as leads and can be
  admitted only through a recorded supersession.

**Multi-angle convergence, for defaults and the "alone" clause.**
- **The owner's direction, 2026-10-12, 20:29Z** (paraphrased, not quoted): research convergence is multi-angle. An
  end-to-end A/B cannot always hold the real factors equal, so it is one part of the evidence, not the decider. Merit is
  also judged from upstream repository quality, community consensus, net usage statistics and more advanced
  evaluations, on every repository and layer.
- **CC record:** the CC's multi-angle convergence ruling of 2026-10-12.
  - **Six angles, A1 to A6:** capability at the pin, upstream engineering quality, community consensus, net usage,
    published evaluations, and our own measurement. The sentence's parenthesis lists them in that order.
  - **Convergence:** FINAL when the angles agree and none shows a disqualifying fact. Where angles disagree, the
    disputed dimension is measured first-hand. No single angle admits or rejects alone, except a hard disqualifier
    (below), which rejects until it changes. Weights are stated per layer before scoring.
  - **Its supersession:** it supersedes the harness-stack ruling's "one measured comparison decides" and its treatment
    of usage rankings as no evidence. Its "Immediate application" item 2 names this PR's sentence and the "alone"
    clause.
- **Licence is never a disqualifier.** The standing owner rule is that licence is never an exclusion ground. The CC's
  ruling "licence is never a disqualifier" (ruling-licence-not-a-disqualifier-20261012, correction #197) applies it
  and supersedes the licence clause that the multi-angle ruling had listed as a disqualifier. So:
  - **The hard disqualifiers are exactly two:** a missing required capability, and an abandoned project. An
    entitlement or terms conflict counts as a missing required capability, for example a subscription used outside
    the client it is limited to, or data the plan does not entitle. Spending and availability limits stay valid
    grounds as well.
  - **Licence is a compliance note** on each candidate: its SPDX id, the source it was read from and the read time.
    It never changes a verdict.

**Why a screen pass admits a trial only.** The Stage A screen in addendum 01 of the CC's runtime-profiles ruling,
section 2, is "a screen against documented requirements, from mirrors at the pin, each with file:line". A candidate
passes when its own docs or source show six things: maintenance, both routes, headless use, native ecosystem inputs,
model and effort controls, and isolation. It checks documented capability at a pin and runs nothing, so it is angle A1
only: it can admit a trial, never a default. Section 3 of the same addendum says so too: "A Stage A passer that has
not been measured gets a profile marked 'trial', not 'final'".

**The converged-harness sentence.**
- **The owner's direction, 2026-10-12, 20:15Z** (paraphrased, not quoted): models are used only through a SOTA harness
  with its full layers; a bare model without them is obsolete.
- **CC record:** the CC's runtime-worker roadmap ruling of 2026-10-12. Its "Rule" section states this rule for the
  foundation rules, in the same PR. Its stage 2, "Fully harnessed", names the layers a runtime's receipt shows wired:
  hook equivalents, the token-efficiency and memory layer, telemetry, effort on the wire and read-only roles.

**The repository rules it extends.** The "Research before acting" bullet already says to adopt the best-evidenced
source, and "Decide by evidence" already says that agreement, recency, popularity and incumbency do not decide. The new
text applies both to admission (trial, then default) and to use (a model runs inside an admitted harness).

The protocol does not yet hold screens or angle scores. [The layer-resolution protocol](2026-10-11-layer-resolution-protocol.md)
(Decision, steps 1-3) reads each layer's catalog verdict and wave, and the latest sweep's survivors in
`catalogs/saturation/ledger.json`. It never uses the words "screen", "angle" or "trial", and no committed record holds a
per-layer screen pass or angle score today. Those land with the freeze wave (section 4 below).

## What it changes

- **An install or a trial run needs the layer's screen pass**, cited by that layer's verdict, wave or sweep record.
- **A default needs multi-angle convergence**: the layer's angles agree, with per-layer weights stated before scoring.
  Where they disagree, the disputed dimension is measured first-hand and recorded.
- **No single angle makes a candidate a default**: not a screen pass, usage, stars, recency, a vendor's evaluation, nor
  one A/B of our own.
- **A candidate already in use without that record** enters the screen as a lead; a pass admits it only through a
  recorded supersession, as correction #192 did for its two arms.
- **A model call runs inside a converged harness** with its listed layers. A bare API call is allowed only as a
  measurement probe or a smoke, and its record says so.

No tool, hook, check or runtime behavior changes in this PR, and it reopens no settled record.

## How the rule applies: every layer, the freeze and the north star

Facts in this section were read at main `489b26328`. Every file cited here is byte-identical at this PR's original base
`7151664c9` and at its rebased base `703d588c` (`git diff --quiet` between the commits), so the line numbers hold at all
three. This section describes how the rule is used; it changes no surface, pin or check. Statements of what later waves
will do are plans, not measured results.

**1. Meaning.** Per the CC's multi-angle ruling of 2026-10-12, as amended by its licence ruling, a candidate is
converged when independent angles agree:

| Angle | What it covers |
| --- | --- |
| A1 | Capability at the pin: the layer's screen. |
| A2 | Upstream engineering quality: releases, CI, tests, maintainers, responsiveness. |
| A3 | Community consensus: star and fork trajectory, credible adopters, independent reviews. |
| A4 | Net usage: OpenRouter app and model rankings, package downloads. |
| A5 | Published evaluations: Terminal-Bench, SWE-bench and its successors, Harbor registry results, Artificial Analysis for models. Vendor evaluations are marked as such. |
| A6 | Our own measured runs, with confounds stated. |

- **Weights** are stated per layer before scoring.
- **No single angle admits or rejects.** The exception is a hard disqualifier: a missing required capability (an
  entitlement or terms conflict counts as one), or an abandoned project.
- **Licence is a compliance note,** never a ground: its SPDX id, source and read time are recorded for each candidate.
- **Where angles disagree,** the disputed dimension is measured first-hand.

**2. Scope.** The rule covers every layer of both repositories:
- native clients, runtimes and harnesses, worker SDKs, orchestration and research runtimes;
- review, landing and CI, memory, token efficiency, evaluation, observability and skills;
- the trading layers. `catalogs/landscape/us-equities.json:7` lists 12 of them, from `market-data-reference` to
  `security-supply-chain`.

`catalogs/landscape/final-stack.json` carries 34 layer rows: 20 foundation and 14 us-equities. Models run only through
converged harnesses (the second sentence).

**3. Waves.** Each layer runs this cycle, and each wave dispatches only the delta
(`docs/decisions/2026-10-11-layer-resolution-protocol.md:55-60`):
1. Discovery: the landscape sweep, the stars manifest, usage rankings and releases.
2. The screen (A1).
3. Angle scoring (A2 to A5).
4. Refutation by blind and other-family reviewers.
5. First-hand measurement where the angles disagree (A6).
6. A terminal state under the protocol (`:69-113`): FINAL, SCHEDULED or RETIRED.

**4. The freeze.** `catalogs/landscape/final-stack.json` is the architecture freeze record. A layer is frozen only when
two things hold:
- the protocol's four FINAL conditions (`docs/decisions/2026-10-11-layer-resolution-protocol.md:78-85`): a recorded
  verdict, a run pin in `runs[]`, an E2E receipt at that pin, and invoke evidence;
- its angle record converges.

The freeze is evidence, not assertion. Each layer's angle table is to land by pull request: weights, scores, and
sources with repo@pin and read times. Both model families read it, and it is registered in `manifests/evidence.json`.
CI checks angle records only once the freeze-wave PR lands. Until then CI checks only each registered file's digest,
and `scripts/final_stack.py` reads no angle record (below).

The file's current numbers:
- `checked_at` is `2026-10-11` (`:2`), and it has 34 layers (`:4831`).
- Status counts: converged 0, current 0, reopened 30, no-winner 2, unswept 2 (`:10707-10713`).
- This "converged" status is the component-matrix status the file defines (`:139`), not the protocol's FINAL.
- No layer carries angle weights: neither "weight" nor "angle" appears in the file.

The next wave is filling that record layer by layer.

What `scripts/final_stack.py` does today:
- **Its job** (its docstring, `:1-21`): it joins the recorded verdicts, sweeps and run pins into that file. It never
  selects a winner.
- **`--check`** exits 1 when the committed file differs from the rebuild, when a source hash changed, or when the
  document is inconsistent.
- **Report-only flags.** Winners without a run pin, pin drift and past-`next_review` verdicts are flags only, exiting
  0 in v1.
- **What it does not check.** It does not test the FINAL conditions 3 and 4 (E2E receipts and invoke evidence), and it
  reads no angle record.
- **What counts as definitive.** `is_definitive` (`:856`) treats a winner as definitive in a layer whose status is
  current or converged and whose `next_review` has not passed; no layer has either status today.

CI runs it on every validate run, shard 0 (`.github/workflows/validate.yml:152-158`):
- `python3 scripts/final_stack.py --check`, which gates;
- `--check --today "$(date -u +%F)"`, which reports to the step summary.

Run locally, `--check` printed `"status": "checked"` with the same counts. The protocol's line that these files "are
not present" at its base (`:115-117`) is stale at `489b26328`: both files exist, and CI runs the generator. That line
still correctly says that no layer is claimed FINAL.

**5. Revisit.** The protocol's reopen rule stands as written: "A **FINAL layer reopens only when a sweep detects a
change**. Bind the reopening to that sweep and its retained change evidence, then apply the same delta rule"
(`docs/decisions/2026-10-11-layer-resolution-protocol.md:62-63`). This record adds no trigger to it.
- **The angle sources become inputs the sweep reads.** These are a pinned winner's new release, a new entrant passing
  the screen, a usage shift and a new published evaluation. The sweep recipe's reopen list today
  (`recipes/saturation-sweep.md:156-162`) names a changed requirement, a new platform, a retained failure, a credible
  missing capability and a comparison that changes a result. Adding the angle sources to that list is a named
  follow-up to the sweep recipe, through its own PR. Until then a change in an angle reopens a layer only when a sweep
  records it under one of the existing triggers.
- **A contradiction found in review** goes through [the corrections rule](2026-10-09-corrections-rule.md): resolve it from the
  pinned upstream primary source, record the correction with its citation and add a regression test that fails before
  the fix.
- **Nothing is silently superseded.** A replaced winner, verdict or record is replaced through a recorded supersession.

**6. PRs keep sourcing the finals.** The required SOTA sources section (`.github/pull_request_template.md:11-13`) names
the exact upstream repo@pin.
- In a layer with a FINAL winner, a PR cites that winner's pin from `final-stack.json` `runs[]` (`:9601`).
- Anything else is TRIAL only and says so.
- Replacing a winner needs a supersession record.

The `sota-sources` job (`.github/workflows/pr-metadata.yml:145-161`) enforces only that the section is present and not
empty. The pin rule here is a review rule, not yet a CI check.

**7. The north star.** The converged foundation is the means, and the trading north star is the object. This is the
intended operation, not a measured one.
- Harnessed runtime workers run the same cycle on the trading layers: data, ranking (including the live top-100
  movers), exits, leverage and sizing, and engines.
- The workers are the Codex lanes, Claude Code, the research runtimes and two-family review.
- Paper results are A6 for the trading layers.

## Surfaces

The six always-loaded surfaces of `StandingRuleSurfacesTests.LAYERS` (`tests/test_install_claude_profile.py`) each hold
the core once; all six now carry the "alone" clause and end the bullet with the two sentences. Each changed line
differs from main only by those 755 bytes.

| Surface | How it changes |
| --- | --- |
| `AGENTS.md` (:7) | Source, edited. |
| `examples/claude-native/CLAUDE.md` (:7) | Source of the Claude user block, edited. |
| `adoption/templates/codex.AGENTS.template.md` (:9) | Source of the Codex user block, edited. |
| `adoption/scaffold/AGENTS.md` (:8) | Scaffold source, edited. `tests/test_scaffold_repo.py` keeps its top-rule block byte-identical to the Codex template's. |
| `adoption/new-wsl/claude-user-instructions.md` (:7) | Generated by `python3 tools/adoption/new_wsl_client_config.py --write-blocks`, after each source edit; last at 22:27:42Z, "0 unit(s) ... left out". |
| `adoption/new-wsl/codex-user-instructions.md` (:9) | Generated by the same command. |

Both carriers are byte-identical to their sources (`cmp` after each write).

**The long form.** `docs/harness-defaults.md:9` holds the long form of the rule, not a copy kept in step. Its clause
read "Agreement, recency, stars and extra tooling are not evidence", which contradicted angle A3 (star and fork
trajectory). It now reads "Agreement, recency, stars and extra tooling alone are not evidence", and
`StandingRuleSurfacesTests.test_the_long_form_rule_says_alone_in_its_not_evidence_clause` pins it. The test fails on
the file before this fix: 0 matches of the new clause and 1 of the old.

**Unchanged on purpose:**
- The quotations of [the 2026-09-28 record](2026-09-28-top-rule-templates.md) quote the fourth bullet only.
- The frozen evidence under `evidence/artifacts/` (the 2026-09-27 prompt audit and the 2026-10-09 verification that
  quote the old clauses) records what past runs saw.
- Root `CLAUDE.md` imports `@AGENTS.md`; `blueprints/us-equities/AGENTS.md` carries no copy of the core; `REVIEW.md`
  carries review rules only. A review rule for this text is a follow-up.

## How the user-level files pick it up

The repository changes no user-level file. As for [the compounding record](2026-10-11-compounding-rule-text.md) ("How
the user-level files pick it up"), `tools/adoption/managed_block.py claude-md` and `codex-md` rewrite the managed blocks
from the two sources after main carries the change. On this host, the CC reports that its hourly re-sync runs them; that
is an unverified host report, and this repository neither versions nor tests that tooling. Another host picks it up
when its installer or `managed_block.py` runs there.

## Startup byte budget: the dated comparison

[The context-budget record](2026-10-05-harness-context-budget.md) (`:164-171`) requires a dated decision with old and
new rendered bytes, the required behavior, alternatives, primary sources and the overturn comparison before a fixed
ceiling changes. The figures come from the test module's `startup_files()`, raw UTF-8 bytes including the markers.
These loaded files are identical at `7151664c9` and `703d588c`.

| Loaded file | Main | This change |
| --- | ---: | ---: |
| Claude user block | 2,681 | 3,436 |
| Codex user block | 3,102 | 3,857 |
| `AGENTS.md` | 3,565 | 4,320 |
| `CLAUDE.md` (Claude only) | 320 | 320 |
| **Claude total** | 6,566 | 8,076 |
| **Codex total** | 6,667 | 8,177 |

- **Old ceilings:** 6,895 and 7,001 bytes. **New ceilings:** the totals plus 5%, rounded up: 8,480 and 8,586
  (`STARTUP_BUDGET_BYTES`). The branch's intermediate ceilings were 7,548/7,654, 8,079/8,185, 8,088/8,194 and
  8,409/8,515.
- **Required behavior:** both are foundation rules, so they are always-loaded text in both clients and on every layer.
- **Primary sources.**
  - **Codex.** The client's own limit on project instructions is far above these sizes. The default
    `project_doc_max_bytes` is 32 KiB: `pub const DEFAULT_PROJECT_DOC_MAX_BYTES: usize = 32 * 1024;` at
    `openai/codex` `codex-rs/config/src/config_toml.rs:75`. It is applied when the setting is unset at
    `codex-rs/core/src/config/mod.rs:256` and `:4380`. All three lines were read in the upstream mirror registered at
    `rust-v0.162.1` (the installed `codex-cli 0.162.1`; mirror checkout `092d3acd6bec3e3a14bdc7e7a2810ab628ab759d`).
    The same line 75 is present at `rust-v0.161.0`, commit `979011409de0a60b52f179721948e65531d26144`.
  - **The Codex template's** separate 8,192-byte check holds at 3,857 bytes.
  - **Claude Code.** No client byte limit is claimed for Claude Code; its ceiling here is this repository's own
    budget.

**Alternatives considered:**
- **A pointer** to this record. Other projects lack this repository's paths, and a pointer keeps a foundation rule out
  of the startup context. Rejected.
- **A new bullet.** The text applies "Decide by evidence" to admission and use; a fifth bullet would split one rule.
  Rejected.
- **The angle definitions in the always-loaded text.** The sentence names the six angles and defines the screen only.
  The angles' sources and weights, the hard disqualifiers and the licence compliance note stay in the layer's evidence
  record and the CC rulings, to keep the startup cost bounded.
- **A hook or check instead of text.** No current tool admits a candidate or routes a model call by itself, so there is
  no single call to guard. The Overturn section names when enforcement moves there.

## Checks

These are checks on repository text, pins and registration. They do not measure behavior. The fail-first runs below
were observed in this session's tool output; their raw logs are not retained in the repository.

- **The new test fails first, at each step.**
  `StandingRuleSurfacesTests.test_every_layer_and_renderer_ends_the_evidence_bullet_with_the_converged_candidates_and_harness_sentences`
  asserts each sentence once, both together at the end of the bullet and before the next one, and the "alone" clause
  once in place with the old clause absent. It covers the six layers and the outputs of the two native block renderers
  and the scaffold renderer. Each new wording was put into the test before the surfaces, and the test then failed with
  9 failing subtests, rc 1:
  - against main's surfaces at 2026-10-12T20:03:20Z (first sentence);
  - against `e18efdcc`'s at 20:17:59Z (the harness sentence);
  - against `d945f4ce`'s at 20:25:11Z (the trial and measured-win wording);
  - against `e4d8f694`'s at 20:32:30Z (the multi-angle wording). The "alone" assertions on their own counted 0
    in-place matches and 1 old clause on each of the six layers;
  - against `14ea7e1b`'s at 22:27:23Z (review round 1: the screen defined, "makes a candidate a default").

  It passes after each edit and regeneration. The commit ids are the rebased ones. The first four runs were made
  before the registry-only rebase, on trees that differ from the rebased ones only in `manifests/evidence.json` and in
  main's one-line port change to `tests/test_codex_worker_lane.py`.
- **The discriminating controls.** With the surfaces edited and the previous `CORE`, `TOP_RULE_SHA256` and ceilings,
  `StandingRuleSurfacesTests`, `PortableTopRuleTests`, `test_codex_worker_lane.TemplateTests` and `test_scaffold_repo`
  ran 63 tests, rc 1:
  - at 20:03:50Z and 20:18:14Z, 15 failures each, in the four core-equality tests, the Codex pin and the two budget
    tests (7,188/7,289 over 6,895/7,001, then 7,694/7,795 over 7,548/7,654);
  - at 20:25:26Z, 20:33:01Z and 22:27:43Z, with the new wording already in `CORE`, only the old Codex pin failed; the
    growth fit the previous ceilings, which were then re-derived anyway.

  `test_scaffold_repo` passed each time, as the scaffold and template moved together.
- **The existing equality tests are updated, not loosened.** `CORE` now carries the "alone" clause and both sentences,
  and `PortableTopRuleTests.PROCEDURE_PHRASES` checks the clause with "alone".
- **The Codex top-rule pin.** `TOP_RULE_SHA256` was re-derived with the module's own `template_segments()`: 3,051 UTF-8
  bytes (2,296 plus 755), `210e97c2e5e7c333114052d93e5eb689572cdadafa82436db5691c8c35af42e8`.
- **The module runs.** `tests.test_install_claude_profile`, `tests.test_managed_block`,
  `tests.test_new_wsl_client_config`, `tests.test_validate`, `tests.test_codex_worker_lane` and
  `tests.test_scaffold_repo` in one idle-weight scope gave `Ran 626 tests`, `OK (skipped=13)` at each earlier step. The
  run on the final text is in the PR description.

## Overturn

- A same-version A/B on an upstream harness (promptfoo for the gateway lanes, Harbor or Inspect for agent tasks),
  read with the other angles, shows the added text raises startup cost without a gain in admission discipline. A
  shorter wording or a pointer then replaces it, through a new record that supersedes this one.
- Recorded incidents show a candidate run without its screen pass, a default set on one angle, or a bare model call
  used for work, while this text is loaded. The enforcement then belongs in a hook, check or workflow.
- The owner rewords the rule, or a client release changes how `CLAUDE.md` or `AGENTS.md` load or are sized.

## Limits

- No behavior is measured. The checks show where the text is and that it is identical, not that agents follow it.
- The angle scores and per-layer weights are not yet recorded for any layer; the multi-angle ruling assigns that work.
- The CC rulings are private and cannot be authenticated from this repository; the paraphrases above are the CC's
  account of them.
- The user-level pickup rests on the CC's host tooling, which this repository neither versions nor tests.

## Sources

- **Rule mechanics at main `7151664c9`:** [the 2026-09-28 top-rule record](2026-09-28-top-rule-templates.md), [the
  rule-text record](2026-09-30-rule-text-every-layer.md), [the philosophy-only record](2026-10-08-philosophy-only-rules.md),
  [the corrections record](2026-10-09-corrections-rule.md) and [the compounding record](2026-10-11-compounding-rule-text.md):
  one core on every layer, regeneration with `cmd_write_blocks` in `tools/adoption/new_wsl_client_config.py`, the pin
  re-derivation and the dated budget comparison.
- **Convergence record:** [the layer-resolution protocol](2026-10-11-layer-resolution-protocol.md) and
  `recipes/saturation-sweep.md`.
- **Client limit:** `openai/codex` at `rust-v0.162.1`, `codex-rs/config/src/config_toml.rs:75` (above).
- **CC rulings, by name:** the harness-stack ruling's addendum 01 (correction #192), the multi-angle convergence
  ruling, ruling-licence-not-a-disqualifier-20261012 (correction #197), the runtime-profiles ruling's addendum 01
  (Stage A and Stage B), and the runtime-roadmap ruling.
