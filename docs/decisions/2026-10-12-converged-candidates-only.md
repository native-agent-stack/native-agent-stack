# Decision: use only converged candidates, through a converged harness (2026-10-12)

**Status:** foundation rule text on the owner's directions. The six repository rule surfaces change together in this
PR; the user-level files follow only after it lands (below). **Supersession:** no decision record is superseded. This
extends the existing "Decide by evidence" rule and amends one clause of it ("alone", below). The CC's own supersession
of its harness-stack ruling is recorded in its multi-angle ruling (Basis).

## The rule

The "Decide by evidence" bullet changes in two places.

**The not-evidence clause** gains one word:

> Agreement, recency, popularity and incumbency alone are not evidence.

It was "Agreement, recency, popularity and incumbency are not evidence." Under multi-angle convergence, community
consensus and net usage are angles of the evidence; none of them decides alone.

**Two sentences** go at the end of the bullet, after "Keep measured results, simulations and untested boundaries
distinct.", in this order:

> Use only converged candidates: a tool, runtime, model or skill is installed or run for trial only after the layer's screen passes it, and becomes a default only when the layer's multi-angle convergence agrees (capability at the pin, upstream engineering quality, community consensus, net usage, published evaluations and our own measured runs); where angles disagree, measure the disputed dimension first-hand, and no single angle admits a candidate on its own.

> Use models only through a converged harness with its full layers (skills, MCP, hook equivalents, memory and token efficiency, telemetry, isolation and roles, invoke receipts); a bare API call is for measurement probes and smokes only, recorded as such.

| Text | UTF-8 bytes | Words | SHA256 |
| --- | ---: | ---: | --- |
| Converged candidates | 461 | 70 | `e3b0471f80409a834e1a341db9a507fcfb2b5887df40bf746bae61a4b719fa17` |
| Converged harness | 252 | 39 | `f91075feb66ac3aa83d8fe8df3a2cde36b61df05c453306b735a75153c32429f` |

With one leading space for each sentence and " alone" in the clause, every copy grows by 462 + 253 + 6 = 721 bytes.

**Earlier wordings on this branch.** They never reached main; each was replaced by a fast-forward commit, not an amend.

| Commit | First sentence, as then worded | Why replaced |
| --- | --- | --- |
| `7feb5fc1` | "...is installed, run or made a default only after the layer's own convergence passes it on quality and SOTA standing (a screen pass or a measured win)..." | A screen pass alone could make a default, and a screen pass is not quality evidence (below). |
| `fe358ffa` | the same; the harness sentence added after it | - |
| `a7b113fc` | "...installed or run for trial only after the layer's own screen passes it, and becomes a default only after a measured win on quality at no higher cost..." | The owner's 20:29Z direction: our own measurement is one angle, not the decider. |

## Basis

**The converged-candidates sentence.**
- **The owner's direction, 2026-10-12, 19:57Z and 19:58Z** (paraphrased, not quoted): use only SOTA candidates that
  the current landscape's convergence has passed. It is a foundation rule: research-driven, and also about the
  candidate's quality and SOTA standing.
- **CC record:** addendum 01 to the CC's harness-stack ruling,
  `~/.local/state/native-agent-stack/coordination/command-center/research-cc-role-20261008/ruling-harness-stack-final-20261012.addendum-01.md`,
  SHA256 `bfb066684ef3e8565c5a241012ac0afb4c9619eb32b7859051ddf8ef3986203e`, written on that direction. It holds
  **CC correction #192**: two arms had been listed for a comparison without passing a screen, one of them admitted from
  a usage list. The fix keeps only documented passers and incumbent trials as arms; the two enter the screen as leads
  and can be admitted only through a recorded supersession.

**Multi-angle convergence, for defaults and the "alone" clause.**
- **The owner's direction, 2026-10-12, 20:29Z** (paraphrased, not quoted): research convergence is multi-angle. An
  end-to-end A/B cannot always hold the real factors equal, so it is one part of the evidence, not the decider. Merit is
  also judged from upstream repository quality, community consensus, net usage statistics and more advanced
  evaluations, on every repository and layer.
- **CC record:** the CC's multi-angle convergence ruling,
  `~/.local/state/native-agent-stack/coordination/command-center/research-cc-role-20261008/ruling-multi-angle-convergence-20261012.md`,
  SHA256 `83e78eacafa78c860a0d2052f5955a65f97e0b7d86ed3a358a73d975b3ae1d50` (tool clock 20:31Z).
  - **Six angles, A1 to A6:** capability at the pin, upstream engineering quality, community consensus, net usage,
    published evaluations, and our own measurement. The sentence's parenthesis lists them in that order.
  - **Convergence:** FINAL when the angles agree and none shows a disqualifying fact. Where angles disagree, the
    disputed dimension is measured first-hand. No single angle admits or rejects alone, except a hard disqualifier at
    A1 or A2 (a missing required capability, an abandoned repository or an incompatible licence), which rejects until
    it changes. Weights are stated per layer before scoring.
  - **Its supersession:** it supersedes the harness-stack ruling's "one measured comparison decides" and its treatment
    of usage rankings as no evidence. Its "Immediate application" item 2 names this PR's sentence and the "alone"
    clause.

**Why a screen pass admits a trial only.** The Stage A screen in the CC's runtime-profiles ruling, addendum 01,
`~/.local/state/native-agent-stack/coordination/command-center/research-cc-role-20261008/ruling-runtime-profiles-and-invoke-gap-20261012.addendum-01.md`,
SHA256 `390741f770843777e4863fcc8787a2559b03170822b2637fc3f50514fa329c8d`, section 2, is "a screen against documented
requirements, from mirrors at the pin, each with file:line". A candidate passes when its own docs or source show six
things: maintenance, both routes, headless use, native ecosystem inputs, model and effort controls, and isolation. It
checks documented capability at a pin and runs nothing, so it is angle A1 only: it can admit a trial, never a default.
Section 3 of the same addendum says so too: "A Stage A passer that has not been measured gets a profile marked
'trial', not 'final'".

**The converged-harness sentence.**
- **The owner's direction, 2026-10-12, 20:15Z** (paraphrased, not quoted): models are used only through a SOTA harness
  with its full layers; a bare model without them is obsolete.
- **CC record:** the CC's runtime-worker roadmap ruling,
  `~/.local/state/native-agent-stack/coordination/command-center/research-cc-role-20261008/ruling-runtime-roadmap-20261012.md`,
  SHA256 `a0104adef843e4039586a2b909de5275501eea1fb407bfa7f453c72c7df107ca` (tool clock 20:16Z). Its "Rule" section
  states this rule for the foundation rules, in the same PR. Its stage 2, "Fully harnessed", names the layers a
  runtime's receipt shows wired: hook equivalents, the token-efficiency and memory layer, telemetry, effort on the wire
  and read-only roles.

**The repository rules it extends.** The "Research before acting" bullet already says to adopt the best-evidenced
source, and "Decide by evidence" already says that agreement, recency, popularity and incumbency do not decide. The new
text applies both to admission (trial, then default) and to use (a model runs inside an admitted harness). The layer's
screen and angle scores are recorded where [the layer-resolution protocol](2026-10-11-layer-resolution-protocol.md)
(Decision, steps 1-3) already reads: the layer's catalog verdict and wave, and the latest sweep's survivors in
`catalogs/saturation/ledger.json`.

The CC records above are private and outside this repository; this record restates only what it relies on.

## What it changes

- **An install or a trial run needs the layer's screen pass**, cited by that layer's verdict, wave or sweep record.
- **A default needs multi-angle convergence**: the layer's angles agree, with per-layer weights stated before scoring.
  Where they disagree, the disputed dimension is measured first-hand and recorded.
- **No single angle admits a candidate**: not usage, stars, recency, a vendor's evaluation, nor one A/B of our own.
- **A candidate already in use without that record** enters the screen as a lead; a pass admits it only through a
  recorded supersession, as correction #192 did for its two arms.
- **A model call runs inside a converged harness** with its listed layers. A bare API call is allowed only as a
  measurement probe or a smoke, and its record says so.

No tool, hook, check or runtime behavior changes in this PR, and it reopens no settled record.

## How the rule applies: every layer, the freeze and the north star

Facts in this section were read at main `489b26328`. Every file cited here is byte-identical at this PR's base
`7151664c9` (`git diff --quiet` between the two commits), so the line numbers hold at either commit. This section
describes how the rule is used; it changes no surface, pin or check.

**1. Meaning.** Per the command center's multi-angle ruling of 2026-10-12, a candidate is converged when independent
angles agree:

| Angle | What it covers |
| --- | --- |
| A1 | Capability at the pin. |
| A2 | Upstream engineering quality: releases, CI, tests, maintainers, responsiveness, licence. |
| A3 | Community consensus: star and fork trajectory, credible adopters, independent reviews. |
| A4 | Net usage: OpenRouter app and model rankings, package downloads. |
| A5 | Published evaluations: Terminal-Bench, SWE-bench and its successors, Harbor registry results, Artificial Analysis for models. Vendor evaluations are marked as such. |
| A6 | Our own measured runs, with confounds stated. |

- **Weights** are stated per layer before scoring.
- **No single angle admits or rejects.** The exception is a hard disqualifier: a missing required capability, an
  abandoned project or an incompatible licence.
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

The freeze is evidence, not assertion. Each layer's angle table lands by pull request: weights, scores, and sources with
repo@pin and read times. Both model families read it, it is registered in `manifests/evidence.json`, and CI checks it.

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
  current or converged; no layer has either status today.

CI runs it on every validate run, shard 0 (`.github/workflows/validate.yml:152-158`):
- `python3 scripts/final_stack.py --check`, which gates;
- `--check --today "$(date -u +%F)"`, which reports to the step summary.

Run locally, `--check` printed `"status": "checked"` with the same counts. The protocol's line that these files "are
not present" at its base (`:115-117`) is stale at `489b26328`: both files exist, and CI runs the generator. That line
still correctly says that no layer is claimed FINAL.

**5. Revisit.** A frozen layer reopens only on new evidence or a landscape change (`:62-67`):
- a new release of a pinned winner;
- a new entrant passing the screen;
- a contradiction found in review;
- a changed angle, such as a usage shift or a new published evaluation.

The reopen is bound to the record that detected it, dispatches only the delta, and ends in a recorded supersession.

**6. PRs keep sourcing the finals.** The required SOTA sources section (`.github/pull_request_template.md:11-13`) names
the exact upstream repo@pin.
- In a layer with a FINAL winner, a PR cites that winner's pin from `final-stack.json` `runs[]` (`:9601`).
- Anything else is TRIAL only and says so.
- Replacing a winner needs a supersession record.

The `sota-sources` job (`.github/workflows/pr-metadata.yml:145-161`) enforces only that the section is present and not
empty. The pin rule here is a review rule, not yet a CI check.

**7. The north star.** The converged foundation is the means, and the trading north star is the object.
- Harnessed runtime workers run the same cycle on the trading layers: data, ranking (including the live top-100
  movers), exits, leverage and sizing, and engines.
- The workers are the Codex lanes, Claude Code, the research runtimes and two-family review.
- Paper results are A6 for the trading layers.

## Surfaces

The six always-loaded surfaces of `StandingRuleSurfacesTests.LAYERS` (`tests/test_install_claude_profile.py`) each hold
the core once; all six now carry the "alone" clause and end the bullet with the two sentences. Each changed line
differs from main `7151664c9` only by those 721 bytes.

| Surface | How it changes |
| --- | --- |
| `AGENTS.md` (:7) | Source, edited. |
| `examples/claude-native/CLAUDE.md` (:7) | Source of the Claude user block, edited. |
| `adoption/templates/codex.AGENTS.template.md` (:9) | Source of the Codex user block, edited. |
| `adoption/scaffold/AGENTS.md` (:8) | Scaffold source, edited. `tests/test_scaffold_repo.py` keeps its top-rule block byte-identical to the Codex template's. |
| `adoption/new-wsl/claude-user-instructions.md` (:7) | Generated by `python3 tools/adoption/new_wsl_client_config.py --write-blocks`, after each source edit; last at 20:33:01Z, "0 unit(s) ... left out". |
| `adoption/new-wsl/codex-user-instructions.md` (:9) | Generated by the same command. |

Both carriers are byte-identical to their sources (`cmp` after each write).

**Unchanged on purpose:**
- `docs/harness-defaults.md` holds the long form of the rule, not a copy kept in step, and has no not-evidence clause.
- The quotations of [the 2026-09-28 record](2026-09-28-top-rule-templates.md) quote the fourth bullet only.
- The frozen evidence under `evidence/artifacts/` (the 2026-09-27 prompt audit and the 2026-10-09 verification that
  quotes the old clause) records what past runs saw.
- Root `CLAUDE.md` imports `@AGENTS.md`; `blueprints/us-equities/AGENTS.md` carries no copy of the core; `REVIEW.md`
  carries review rules only. A review rule for this text is a follow-up.

## How the user-level files pick it up

The repository changes no user-level file. As for [the compounding record](2026-10-11-compounding-rule-text.md) ("How
the user-level files pick it up"), `tools/adoption/managed_block.py claude-md` and `codex-md` rewrite the managed blocks
from the two sources after main carries the change; on this host the CC's hourly re-sync runs them. Another host picks
it up when its installer or `managed_block.py` runs there.

## Startup byte budget: the dated comparison

[The context-budget record](2026-10-05-harness-context-budget.md) requires a dated comparison before a fixed ceiling
changes. The figures come from the test module's `startup_files()`, raw UTF-8 bytes including the markers.

| Loaded file | Main `7151664c9` | This change |
| --- | ---: | ---: |
| Claude user block | 2,681 | 3,402 |
| Codex user block | 3,102 | 3,823 |
| `AGENTS.md` | 3,565 | 4,286 |
| `CLAUDE.md` (Claude only) | 320 | 320 |
| **Claude total** | 6,566 | 8,008 |
| **Codex total** | 6,667 | 8,109 |

- **Old ceilings:** 6,895 and 7,001 bytes. **New ceilings:** the totals plus 5%, rounded up: 8,409 and 8,515
  (`STARTUP_BUDGET_BYTES`). The branch's intermediate ceilings were 7,548/7,654, 8,079/8,185 and 8,088/8,194.
- **Required behavior:** both are foundation rules, so they are always-loaded text in both clients and on every layer.
- The Codex template's separate 8,192-byte check holds at 3,823 bytes.

**Alternatives considered:**
- **A pointer** to this record. Other projects lack this repository's paths, and a pointer keeps a foundation rule out
  of the startup context. Rejected.
- **A new bullet.** The text applies "Decide by evidence" to admission and use; a fifth bullet would split one rule.
  Rejected.
- **The angle definitions in the always-loaded text.** The sentence names the six angles only; their sources, weights
  and the hard-disqualifier exception stay in the layer's evidence record and the CC ruling, to keep the startup cost
  bounded.
- **A hook or check instead of text.** No current tool admits a candidate or routes a model call by itself, so there is
  no single call to guard. The Overturn section names when enforcement moves there.

## Checks

These are checks on repository text, pins and registration. They do not measure behavior.

- **The new test fails first, at each step.**
  `StandingRuleSurfacesTests.test_every_layer_and_renderer_ends_the_evidence_bullet_with_the_converged_candidates_and_harness_sentences`
  asserts each sentence once, both together at the end of the bullet and before the next one, and the "alone" clause
  once in place with the old clause absent. It covers the six layers and the outputs of the two native block renderers
  and the scaffold renderer. Each new wording was put into the test before the surfaces, and the test then failed with
  9 failing subtests, rc 1:
  - against main's surfaces at 2026-10-12T20:03:20Z (first sentence);
  - against `7feb5fc1`'s at 20:17:59Z (the harness sentence);
  - against `fe358ffa`'s at 20:25:11Z (the trial and measured-win wording);
  - against `a7b113fc`'s at 20:32:30Z (the final wording). The "alone" assertions on their own counted 0 in-place
    matches and 1 old clause on each of the six layers.

  It passes after each edit and regeneration.
- **The discriminating controls.** With the surfaces edited and the previous `CORE`, `TOP_RULE_SHA256` and ceilings,
  `StandingRuleSurfacesTests`, `PortableTopRuleTests`, `test_codex_worker_lane.TemplateTests` and `test_scaffold_repo`
  ran 63 tests, rc 1:
  - at 20:03:50Z and 20:18:14Z, 15 failures each, in the four core-equality tests, the Codex pin and the two budget
    tests (7,188/7,289 over 6,895/7,001, then 7,694/7,795 over 7,548/7,654);
  - at 20:25:26Z and 20:33:01Z, with the new wording already in `CORE`, only the old Codex pin failed; the growth fit
    the previous ceilings, which were then re-derived anyway.

  `test_scaffold_repo` passed each time, as the scaffold and template moved together.
- **The existing equality tests are updated, not loosened.** `CORE` now carries the "alone" clause and both sentences,
  and `PortableTopRuleTests.PROCEDURE_PHRASES` checks the clause with "alone".
- **The Codex top-rule pin.** `TOP_RULE_SHA256` was re-derived with the module's own `template_segments()`: 3,017 UTF-8
  bytes (2,296 plus 721), `bc5f296f2a746c9ac51d9bf769542e7e7cae2f6e33ade4fbeb9b6cad94264769`.
- **The module runs.** `tests.test_install_claude_profile`, `tests.test_managed_block`,
  `tests.test_new_wsl_client_config`, `tests.test_validate`, `tests.test_codex_worker_lane` and
  `tests.test_scaffold_repo` in one idle-weight scope gave `Ran 626 tests`, `OK (skipped=13)` on `7feb5fc1`
  (20:10:54Z to 20:14:32Z), `fe358ffa` (20:20:34Z to 20:23:41Z) and `a7b113fc` (20:27:38Z to 20:30:41Z). The run on
  the final text is in the PR description.

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
- The user-level pickup rests on the CC's host tooling, which this repository neither versions nor tests.

## Sources

- **Rule mechanics at main `7151664c9`:** [the 2026-09-28 top-rule record](2026-09-28-top-rule-templates.md), [the
  rule-text record](2026-09-30-rule-text-every-layer.md), [the philosophy-only record](2026-10-08-philosophy-only-rules.md),
  [the corrections record](2026-10-09-corrections-rule.md) and [the compounding record](2026-10-11-compounding-rule-text.md):
  one core on every layer, regeneration with `cmd_write_blocks` in `tools/adoption/new_wsl_client_config.py`, the pin
  re-derivation and the dated budget comparison.
- **Convergence record:** [the layer-resolution protocol](2026-10-11-layer-resolution-protocol.md).
- **CC records**, at the SHA256s given above: the harness-stack addendum with correction #192, the multi-angle
  convergence ruling, the runtime-profiles addendum with the Stage A and Stage B definitions, and the runtime-roadmap
  ruling.
