# Decision: use only converged candidates, through a converged harness (2026-10-12)

**Status:** foundation rule text on the owner's directions. The six repository rule surfaces change together in this
PR; the user-level files follow only after it lands (below). **Supersession:** none. This extends the existing
"Decide by evidence" rule and replaces no record.

## The rule

Two sentences go at the end of the third core bullet, "Decide by evidence", after "Keep measured results, simulations
and untested boundaries distinct.", in this order:

> Use only converged candidates: a tool, runtime, model or skill is installed or run for trial only after the layer's own screen passes it, and becomes a default only after a measured win on quality at no higher cost; popularity, recency and vendor claims make a candidate a lead for that screen, never an admission.

> Use models only through a converged harness with its full layers (skills, MCP, hook equivalents, memory and token efficiency, telemetry, isolation and roles, invoke receipts); a bare API call is for measurement probes and smokes only, recorded as such.

| Sentence | UTF-8 bytes | Words | SHA256 |
| --- | ---: | ---: | --- |
| Converged candidates | 314 | 55 | `7d9e2a132969a4256bb42ca75bbe5b8bd1aa6949a36e53a9ed1e3ebdf2f33df7` |
| Converged harness | 252 | 39 | `f91075feb66ac3aa83d8fe8df3a2cde36b61df05c453306b735a75153c32429f` |

With one leading space each, every copy grows by 315 + 253 = 568 bytes.

**The first sentence's earlier wording.** Commit `7feb5fc1` carried "is installed, run or made a default only after the
layer's own convergence passes it on quality and SOTA standing (a screen pass or a measured win)" (310 bytes, SHA256
`added1b0c16f135f79366df655b87eae5b80d04fb998a073c7cd19096a73e17a`). The CC tightened it before landing, so it never
reached main: it let a screen pass alone make a default, and a screen pass is not quality evidence (next section).

## Basis: the converged-candidates sentence

- **The owner's direction, 2026-10-12, 19:57Z and 19:58Z** (paraphrased, not quoted): use only SOTA candidates that
  the current landscape's convergence has passed. It is a foundation rule: research-driven, and also about the
  candidate's quality and SOTA standing.
- **The CC record.** Addendum 01 to the CC's harness-stack ruling,
  `~/.local/state/native-agent-stack/coordination/command-center/research-cc-role-20261008/ruling-harness-stack-final-20261012.addendum-01.md`,
  SHA256 `bfb066684ef3e8565c5a241012ac0afb4c9619eb32b7859051ddf8ef3986203e`, written on that direction. It holds
  **CC correction #192**: two arms had been listed for a comparison without passing a convergence screen, one of them
  admitted from a usage list. The fix keeps only documented passers and incumbent trials as arms; the two enter the
  screen as leads and can be admitted only through a recorded supersession. Both are the CC's private records, outside
  this repository; this record restates only what it relies on.
- **The rules it extends.** The "Decide by evidence" bullet of `AGENTS.md` already says that agreement, recency,
  popularity and incumbency are not evidence. The "Research before acting" bullet already says to adopt the
  best-evidenced source. The new sentence applies both to admission: what may be installed or run for trial, and what
  may become a default. The layer's screen and its measured comparison are recorded where
  [the layer-resolution protocol](2026-10-11-layer-resolution-protocol.md) (Decision, steps 1-3) already reads: the
  layer's catalog verdict and wave, and the latest sweep's survivors in `catalogs/saturation/ledger.json`.
- **Why a screen pass admits a trial only.** The Stage A screen in the CC's runtime-profiles ruling, addendum 01,
  `~/.local/state/native-agent-stack/coordination/command-center/research-cc-role-20261008/ruling-runtime-profiles-and-invoke-gap-20261012.addendum-01.md`,
  SHA256 `390741f770843777e4863fcc8787a2559b03170822b2637fc3f50514fa329c8d`, section 2, is "a screen against
  documented requirements, from mirrors at the pin, each with file:line". A candidate passes when its own docs or source
  show six things: maintenance, both routes, headless use, native ecosystem inputs, model and effort controls, and
  isolation. It checks documented capability at a pin and runs nothing, so it says nothing about quality or cost.
  Section 3, Stage B, measures the passers in a preregistered comparison, and "a Stage A passer that has not been
  measured gets a profile marked 'trial', not 'final'". The sentence states that split: the screen admits a trial, a
  measured win on quality at no higher cost admits a default. "No higher cost" matches the roadmap ruling's stage 4
  rule (below): non-inferior to the better reference arm at no higher cost per passed task.

## Basis: the converged-harness sentence

- **The owner's direction, 2026-10-12, 20:15Z** (paraphrased, not quoted): models are used only through a SOTA harness
  with its full layers; a bare model without them is obsolete.
- **The CC record.** The CC's runtime-worker roadmap ruling,
  `~/.local/state/native-agent-stack/coordination/command-center/research-cc-role-20261008/ruling-runtime-roadmap-20261012.md`,
  SHA256 `a0104adef843e4039586a2b909de5275501eea1fb407bfa7f453c72c7df107ca`, written on that direction (tool clock
  20:16Z). Its "Rule" section states this rule for the foundation rules, in the same PR as the converged-candidates
  rule. Its stage 2, "Fully harnessed", names the layers a runtime's receipt shows wired: hook equivalents, the
  token-efficiency and memory layer, telemetry, effort on the wire and read-only roles. It is the CC's private record,
  outside this repository, restated only as relied on here.
- **What it extends.** The first sentence governs which harness is admitted; this one says a model runs only inside
  one, so the harness's layers apply to every model call. "Converged harness" is a harness the first sentence admits.

## What it changes

- **An install or a trial arm needs the layer's screen pass**, cited by that layer's verdict, wave or sweep record.
- **A default needs a measured win** on quality at no higher cost, from the layer's preregistered comparison. A screen
  pass alone never makes a default.
- **Popularity, recency, stars, usage lists and vendor claims** may put a candidate on the screen as a lead. They never
  admit it.
- **A candidate already in use without that record** enters the screen as a lead; a pass admits it only through a
  recorded supersession, as correction #192 did for its two arms.
- **A model call runs inside a converged harness** with its listed layers. A bare API call is allowed only as a
  measurement probe or a smoke, and its record says so.

No tool, hook, check or runtime behavior changes in this PR, and it reopens no settled record.

## Surfaces

The six always-loaded surfaces of `StandingRuleSurfacesTests.LAYERS` (`tests/test_install_claude_profile.py`) each hold
the core once; all six now end the bullet with the two sentences. Each changed line differs from main `7151664c9` only
by the appended 568 bytes. The first sentence landed in commit `7feb5fc1`, the second in fast-forward commit `fe358ffa`,
and the tightened first sentence in the fast-forward commit after it, each regenerated the same way.

| Surface | How it changes |
| --- | --- |
| `AGENTS.md` (:7) | Source, edited. |
| `examples/claude-native/CLAUDE.md` (:7) | Source of the Claude user block, edited. |
| `adoption/templates/codex.AGENTS.template.md` (:9) | Source of the Codex user block, edited. |
| `adoption/scaffold/AGENTS.md` (:8) | Scaffold source, edited. `tests/test_scaffold_repo.py` keeps its top-rule block byte-identical to the Codex template's. |
| `adoption/new-wsl/claude-user-instructions.md` (:7) | Generated by `python3 tools/adoption/new_wsl_client_config.py --write-blocks` at 20:03:42Z, 20:18:13Z and 20:25:26Z: "0 unit(s) ... left out" each time. |
| `adoption/new-wsl/codex-user-instructions.md` (:9) | Generated by the same command. |

Both carriers are byte-identical to their sources (`cmp` after the write).

**Unchanged on purpose:**
- `docs/harness-defaults.md` holds the long form of the rule, not a copy kept in step.
- The quotations of [the 2026-09-28 record](2026-09-28-top-rule-templates.md) quote the fourth bullet only.
- The frozen prompt-audit inputs under `evidence/artifacts/prompt-audit-20260927/` record what past runs saw.
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

| Loaded file | Main `7151664c9` | `7feb5fc1` (first sentence) | `fe358ffa` (both) | Final (tightened first) |
| --- | ---: | ---: | ---: | ---: |
| Claude user block | 2,681 | 2,992 | 3,245 | 3,249 |
| Codex user block | 3,102 | 3,413 | 3,666 | 3,670 |
| `AGENTS.md` | 3,565 | 3,876 | 4,129 | 4,133 |
| `CLAUDE.md` (Claude only) | 320 | 320 | 320 | 320 |
| **Claude total** | 6,566 | 7,188 | 7,694 | 7,702 |
| **Codex total** | 6,667 | 7,289 | 7,795 | 7,803 |
| Ceilings (Claude/Codex) | 6,895/7,001 | 7,548/7,654 | 8,079/8,185 | 8,088/8,194 |

- **New ceilings:** the final totals plus 5%, rounded up: 8,088 and 8,194 (`STARTUP_BUDGET_BYTES`). The final totals
  already fit the `fe358ffa` ceilings; the ceilings were still re-derived by the same formula, so the 5% headroom is
  measured from the landing text.
- **Required behavior:** both are foundation rules, so they are always-loaded text in both clients and on every layer.
- The Codex template's separate 8,192-byte check holds at 3,670 bytes.

**Alternatives considered:**
- **A pointer** to this record. Other projects lack this repository's paths, and a pointer keeps a foundation rule out
  of the startup context. Rejected.
- **A new bullet.** The sentences apply "Decide by evidence" to admission and use; a fifth bullet would split one rule.
  Rejected.
- **A hook or check instead of text.** No current tool admits a candidate or routes a model call by itself, so there is
  no single call to guard. The Overturn section names when enforcement moves there.

## Checks

These are checks on repository text, pins and registration. They do not measure behavior.

- **The new test fails first, for each sentence.**
  `StandingRuleSurfacesTests.test_every_layer_and_renderer_ends_the_evidence_bullet_with_the_converged_candidates_and_harness_sentences`
  asserts each sentence once, both together at the end of the bullet and before the next one, on the six layers and in
  the outputs of the two native block renderers and the scaffold renderer.
  - First sentence: against the unedited surfaces at 2026-10-12T20:03:20Z it failed with 9 failing subtests, rc 1.
  - Second sentence: extended with it, against the surfaces of `7feb5fc1` at 20:17:59Z, it failed with 9 failing
    subtests, rc 1.
  - Tightened first sentence: with the new wording, against the surfaces of `fe358ffa` at 20:25:11Z, it failed with
    9 failing subtests, rc 1.

  It passes after each edit and regeneration.
- **The discriminating controls.** With the surfaces edited and the previous `CORE`, `TOP_RULE_SHA256` and ceilings,
  `StandingRuleSurfacesTests`, `PortableTopRuleTests`, `test_codex_worker_lane.TemplateTests` and `test_scaffold_repo`
  ran 63 tests, rc 1, with 15 failures each of the first two times: in the four core-equality tests, the Codex pin and
  the two budget tests. At 20:03:50Z Claude 7,188 and Codex 7,289 bytes exceeded 6,895 and 7,001; at 20:18:14Z, 7,694
  and 7,795 exceeded 7,548 and 7,654. At 20:25:26Z, with the new wording already in `CORE`, only the old Codex pin
  failed (1 failure); the 4-byte growth fit the old ceilings. `test_scaffold_repo` passed each time, as the scaffold and
  template moved together.
- **The existing equality tests are updated, not loosened.** `CORE` now ends the bullet with both sentences.
- **The Codex top-rule pin.** `TOP_RULE_SHA256` was re-derived with the module's own `template_segments()`: 2,864 UTF-8
  bytes (2,296 plus 568), `5d034e3605f415b03fc2e797535372446b3902b6dd6b5cb9a14352467239ca73`.
- **The module runs.** `tests.test_install_claude_profile`, `tests.test_managed_block`,
  `tests.test_new_wsl_client_config`, `tests.test_validate`, `tests.test_codex_worker_lane` and
  `tests.test_scaffold_repo` in one idle-weight scope: `Ran 626 tests`, `OK (skipped=13)` on `7feb5fc1` (20:10:54Z to
  20:14:32Z) and on `fe358ffa` (20:20:34Z to 20:23:41Z). The run on the final text is in the PR description.

## Overturn

- A same-version A/B on an upstream harness (promptfoo for the gateway lanes, Harbor or Inspect for agent tasks) shows
  the added text raises startup cost without a measured gain in admission discipline. A shorter wording or a pointer then
  replaces it, through a new record that supersedes this one.
- Recorded incidents show a candidate admitted without its screen pass, a default set without a measured win, or a
  bare model call used for work, while this text is loaded. The enforcement then belongs in a hook, check or workflow.
- The owner rewords the rule, or a client release changes how `CLAUDE.md` or `AGENTS.md` load or are sized.

## Limits

- No behavior is measured. The checks show where the text is and that it is identical, not that agents follow it.
- The user-level pickup rests on the CC's host tooling, which this repository neither versions nor tests.

## Sources

- **Rule mechanics at main `7151664c9`:** [the 2026-09-28 top-rule record](2026-09-28-top-rule-templates.md), [the
  rule-text record](2026-09-30-rule-text-every-layer.md), [the philosophy-only record](2026-10-08-philosophy-only-rules.md),
  [the corrections record](2026-10-09-corrections-rule.md) and [the compounding record](2026-10-11-compounding-rule-text.md):
  one core on every layer, regeneration with `cmd_write_blocks` in `tools/adoption/new_wsl_client_config.py`, the pin
  re-derivation and the dated budget comparison.
- **Convergence record:** [the layer-resolution protocol](2026-10-11-layer-resolution-protocol.md).
- **CC records:** the harness-stack addendum with correction #192, the runtime-profiles addendum with the Stage A and
  Stage B definitions, and the runtime-roadmap ruling, at the SHA256s given above.
