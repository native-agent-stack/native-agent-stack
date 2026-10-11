# Daily native skill use and Claude parent routing

Pin the installed official Claude API skill in the existing 30-day trial,
schedule the repository's three native collectors on the live main clone,
and show only skill names and counts by native lane group on the Fleet page.
Seven on-listed skills have zero baseline Claude uses and positive Codex
skill-file reads. Native BEFORE measurements establish that six are wired;
only security-audit needs a proposed invocation cue. No skill is pruned here.

## SOTA sources

- `anthropics/skills` at `dbd4588f9e1033efb41dad4bef2f7947c8993d44`:
  [marketplace entry](https://github.com/anthropics/skills/blob/dbd4588f9e1033efb41dad4bef2f7947c8993d44/.claude-plugin/marketplace.json#L46)
  defines `claude-api@anthropic-agent-skills` and `skills/claude-api`;
  [SKILL.md](https://github.com/anthropics/skills/blob/dbd4588f9e1033efb41dad4bef2f7947c8993d44/skills/claude-api/SKILL.md#L3)
  supplies the unchanged description, and `LICENSE.txt` supplies Apache-2.0.
  Its 105146 bytes hash to
  `40537cca17c4aa86e4ce83ced39efcbfb1204905e3cf4c4ff98f2eab011e4b7f`;
  public upstream and the installed native cache agree. The manifest records
  the upstream directory tree SHA, description's 1068 Unicode code points,
  plugin identity and native skill name `claude-api:claude-api`.
- Installed Claude Code 2.1.296 and
  `anthropics/claude-code@2301018b1f61073c501a8e7a4813ef48c239163b`:
  [release history](https://github.com/anthropics/claude-code/blob/2301018b1f61073c501a8e7a4813ef48c239163b/CHANGELOG.md),
  [skill discovery](https://code.claude.com/docs/en/skills#where-skills-live),
  [description/invocation control](https://code.claude.com/docs/en/skills#frontmatter-reference),
  [visibility settings](https://code.claude.com/docs/en/skills#override-skill-visibility-from-settings)
  and [native evals](https://code.claude.com/docs/en/plugin-evals), read 2026-10-10.
  Native `installed_plugins.json` uses `installedAt`, `gitCommitSha` and
  `installPath`. Registry/pin and SKILL.md checks attest plugin provenance;
  they do not claim its enabled state. The doctor capture measures listing/use.
- Existing collector reference implementation at main
  `e1c88ff3d7edc71052d6fb4eed8422438b06efaf`: `tools/skill-usage/skill_usage.py`
  and `examples/claude-native/workflows/child-usage.mjs`. Reuse their parsers,
  native cost/turn checks, timestamp windows, group aggregation and privacy
  boundary. The daily adapter introduces no competing event collector.
- `systemd/systemd` v259.5 at
  `b3d8fc43e9cb531d958c17ef2cd93b374bc14e8a`:
  [timer semantics](https://github.com/systemd/systemd/blob/b3d8fc43e9cb531d958c17ef2cd93b374bc14e8a/man/systemd.timer.xml)
  and [user verification](https://github.com/systemd/systemd/blob/b3d8fc43e9cb531d958c17ef2cd93b374bc14e8a/src/analyze/analyze-verify.c).
  Adopt the repository's `@REPOSITORY@` live-clone rendering convention,
  daily calendar, persistent catch-up and randomized start. Unit verification
  uses a fixture runtime directory, without starting or installing units.

## What the measurements mean

The host collector requests `--run-skill-doctor --codex-root <explicit-root>
--window 7 --json`. Claude doctor `uses` is lifetime; its seven-day token
column does not convert it into a seven-day invocation count. The existing
collector also includes the trial's 30-day window. Native plugin installation
age comes from `installedAt`, not a guessed date or the Vercel skill lock.

The Codex group collector requests `--lanes --since <seven-days-ago>
--until <now> --json` over the same explicit root. Its skill-file reads are
a usage proxy, labeled as reads. The Claude collector requests
`child-usage.mjs --lanes-sweep --root <explicit-root> --since <seven-days-ago>
--until <now>` and counts native `Skill` calls by spawn path and agent type.
Group views overlap and are not summed. Missing or failed sources remain
UNKNOWN. The latest private projection stores names, counts, timestamps and
measurement flags; prompts, paths, session IDs and account fields are dropped.

## Raw reads and de-inflated use

Retain raw SKILL.md path-read and `$name` mention counts. The new `use_counts`
counts at most once per native session and skill from the union of its own
windowed read/mention signals. Inherited copied records add no use. Sessions
reading more than **N = 26 distinct SKILL.md names** in that window are omitted
from use, including their mentions. Native session metadata identities join
duplicate rollout parts in memory; identities are never published.

Measured the shipped collector first-hand at `2026-10-10T15:24:25Z`, seven-day
window, 2799 rollout files, zero parse errors. Its distinct-read distribution
is: 0:885, 1:910, 2:447, 3:181, 4:107, 5:58, 6:39, 7:30, 8:26, 9:30,
10:9, 11:9, 12:20, 13:17, 14:11, 15:3, 16:6, 17:5, 18:2, 22:1,
36:1, 37:1, 41:1. The zero bin includes scanned sessions without a windowed
read. N=26 lies in the observed gap between 22 and 36 and excludes the three
broadest sessions while retaining the next observed tier. It is a transparent
bulk-scan heuristic, not proof of research intent or native skill activation.
Future distributions and known legitimate broad sessions can overturn it.

An initial exploratory histogram used the last metadata header and joined
inherited headers; it is superseded by the shipped scanner's first-header
rule from the pinned main reference implementation. The calibrated report
uses the actual implementation and its regression-tested session join.

| Skill | Raw reads (7d) | Use (7d) |
| --- | ---: | ---: |
| security-audit | 109 | 69 |
| gh-fix-ci | 101 | 71 |
| gh-address-comments | 87 | 53 |
| frontend-design | 60 | 20 |
| typesafe-ai | 17 | 11 |
| security-best-practices | 8 | 4 |
| security-threat-model | 6 | 3 |

Every listed skill had zero explicit `$name` mentions in this sample. The
synthetic bulk-scan regression demonstrates two raw reads per skill and zero
use; repeated ordinary reads plus mentions count as one use. It failed before
the new metric existed. The page's primary Codex count and zero-use list use
use; raw reads remain beside it. Trial zero-use flags also use this metric.

The baseline files remain outside the repository. Their supplied SHA-256s are
`f9bb0dfc164223fd5bcccaccd0895871f843de3166c4e5de495f71bb1675ad95`
for the host report and
`3963beb88ba0c03fd5a9a493c8870637b8b8ce33178374c4ab2ae1cbe18a391c`
for the Codex group report. Their seven target rows are present/on-listed,
with Claude uses zero and last_used never. This is measured usage/discovery,
not a causal model-trigger test.

## Wiring and untested boundary

Native `skillOverrides` controls visibility, has no description replacement,
and does not govern plugin skills. Preserve the selected vendor files.
The authored `native-skill-routing` skill adds only a security-audit invocation
description and directs the parent to call that target before Bash or repository
search. Existing read-only security-reviewer already preloads
security-best-practices and has no Skill tool; preload guidance is not an
invocation event. No worker tool grant is widened.

The project `.claude/skills/native-skill-routing/SKILL.md` is the single
authored source. Native project skill discovery can therefore reproduce
AFTER routing from a worktree of this PR, before any user-profile application.
The twenty-four `trigger-cases-v4.json` requests give cc-native-practice seven
initial positives, seven near-miss negatives, three additional security-audit
phrasings, one actual repository-relative source-path request and six indirect
requests for its native BEFORE/AFTER harness. Its comparability base stays
`60004bb1dd581e00e3303c54d93435bb72f76952`; the PR's assigned base is separate.

The CC-owned BEFORE receipt at 2026-10-10T15:44:29Z measured 21 runs on
Claude Code 2.1.296. gh-fix-ci, gh-address-comments, frontend-design,
typesafe-ai, security-best-practices and security-threat-model each invoked
3/3; security-audit invoked 1/3. The public baseline holds only those skill
names/counts and dispositions. The private summary's SHA-256 is
`36b7e6b39df077def1d5ce2408fc079d6d313f3d01a4fc8d7bb184f01f0662dc`.
It is a real native trigger observation for explicit task prompts, not a
general success-rate estimate. Zero baseline use on the six means zero
observed calls and a reason to check wiring; it does not establish absence
of demand. Their descriptions and routes are unchanged.

The original [Cloudflare description](https://github.com/cloudflare/security-audit-skill/blob/c1c8a8c1471069fb0e188eeaff69b8e8db6564a8/skills/security-audit/SKILL.md#L3)
is pinned at `c1c8a8c1471069fb0e188eeaff69b8e8db6564a8`.
Compared the unchanged Cloudflare description's broad security-question and
full-workflow branches with the explicit request language of the two OpenAI
security skills. The smallest supported change without mutating pinned vendor
bytes is an authored description that names vulnerability/injection review and
directs an immediate `security-audit` Skill call before code exploration.
Native visibility settings cannot override vendor description text. This
project skill is an authored invocation cue, not a replacement of the vendor
skill. The same-checkout hermetic ablation below supplies its primary measured
effect size; future observations can reject or refine it.

Earlier non-hermetic observations motivated the wording change but are not
used as the primary matched comparison. Loading after exploration differs from
loading before it; the ablation reports both invocation and turn one.
The explicit trigger/exclusion phrasing follows the sibling descriptions at
`openai/skills@49f948faa9258a0c61caceaf225e179651397431`:
[security-best-practices](https://github.com/openai/skills/blob/49f948faa9258a0c61caceaf225e179651397431/skills/.curated/security-best-practices/SKILL.md#L3)
and [security-threat-model](https://github.com/openai/skills/blob/49f948faa9258a0c61caceaf225e179651397431/skills/.curated/security-threat-model/SKILL.md#L3).
Anthropic's
[skill-creator description guidance](https://github.com/anthropics/skills/blob/dbd4588f9e1033efb41dad4bef2f7947c8993d44/skills/skill-creator/SKILL.md#L67)
at `anthropics/skills@dbd4588f9e1033efb41dad4bef2f7947c8993d44:skills/skill-creator/SKILL.md:67`
identifies the description as the primary trigger and requires specific use
contexts; line 52 asks which phrases/contexts should trigger. The local mirror
HEAD and live upstream HEAD were both verified at that same pin. Only the
authored security-audit cue changes; the actual vendor file remains pinned.

Fixture tests verify native plugin namespace/age, unchanged plugin hashes,
profile discovery and preservation, native collector command lines, private
count projection, Fleet rendering and unit rendering. Namespace, profile and
page regressions failed before the fixes. They establish wiring contracts,
not semantic selection. Native CC-owned AFTER observations are recorded below;
the expanded case file remains unchanged for reruns. Optional post-install
personal profile read-back remains explicitly unmeasured here.

## Primary effect size: same-checkout hermetic ablation

The primary effect size comes from the CC-owned one-switch ablation: 128
sessions, 64 per arm, on one checkout and one HEAD, with only the inline
skillOverrides.native-skill-routing setting changing between on and off.
Claude Code 2.1.296/claude-opus-5-5 used the same explicit-task synthetic
v4 prompts and three turns per session. The cue was listed in 64/64 on
sessions and 0/64 off sessions; all eight retained receipt/summary hashes
were independently checked against their files. The 128 receipts are
hermetic with no memory markers or other-case prompt leaks.

Primary state-root citation, rehashed for this method correction:

- ~/.local/state/native-agent-stack/research/cc-native-practice-20261009/trigger-cases-20261010/ABLATION-TABLE.md:
  2724 bytes, SHA-256
  770555cb65e58c0143991faf6220bf3c29e78cec671e2e274e48effd5304e179.

| Same-HEAD observation | Cue hidden | Cue with exclusion listed |
| --- | ---: | ---: |
| security-audit, five phrasings, turn one | 13/20 | 20/20 |
| security-audit, five phrasings, invoked within three turns | 17/20 | 20/20 |
| security-best-practices indirect, turn one | 8/12 | 12/12 |
| security-best-practices indirect, invoked | 12/12 | 12/12 |
| security-audit capture of the indirect sibling request | 0/12 | 0/12 |
| Explicit sibling request, invoked and turn one | 4/4 | 4/4 |
| Near-miss negatives, any skill invoked | 0/28 | 0/28 |

The primary security-audit turn-one effect is 13/20 to 20/20, a 35 percentage
point observed increase, Fisher two-sided p=0.008. Invocation within three
turns rises from 17/20 to 20/20, Fisher two-sided p=0.23. The indirect sibling's
turn-one result is 8/12 to 12/12, Fisher two-sided p=0.09; it is a small-sample
observation rather than a precise estimate. The cue with the exclusion and its measured
conclusion stand: all twenty audit positives invoke in turn one, the sibling
is not captured on these indirect requests, and no near-miss fires.

The CC's 2026-10-10 21:22Z method ruling identifies HEAD-subject priming in
the git-status context. Its reported stale-tree control fired 7/8 under a
retirement-related subject versus 2/11 under its own subjects. These control
counts explain the method correction; they are not the cue's effect estimate.
The earlier three-arm study has different HEAD subjects, so its effect size
is overstated and it is retained only as supporting evidence below. Hermetic
memory isolation alone does not control this source of priming.

Future A/B measurements must be hermetic and share one HEAD, toggling
skillOverrides on the same checkout. If a tree-switch control requires an
empty commit, use the same subject in both arms; never let differing commit
subjects enter the git-status context. Record HEAD/subject equivalence with
the invocation receipts.

## Supporting three-arm comparison: HEAD-subject confound

The supporting comparison is the CC-owned native run completed 2026-10-10
17:59–18:13Z: 64 sessions per arm, 192 total, Claude Code 2.1.296 and
claude-opus-5-5, three turns per session. The three arms are no cue at
60004bb1dd581e00e3303c54d93435bb72f76952, the original cue at
47fdceea7fc4444c0faae90c6cd7d2c8435dcb67, and the cue with the exclusion at
ef43fdc1f64e444922676b0b1788dcabaf2dd30e. The native runner's process-tree
memory-hook isolation left host files/settings, plugins, skills and other
hooks unchanged.

Supporting state-root citations, independently rehashed before publication:

- ~/.local/state/native-agent-stack/research/cc-native-practice-20261009/trigger-cases-20261010/HERMETIC-TABLE.md:
  3541 bytes, SHA-256
  af2337937bc4157460064bc986c3c77cfa985ae0ce3201d972d26912efd13115.
- ~/.local/state/native-agent-stack/research/cc-native-practice-20261009/trigger-cases-20261010/AFTER-RESULT-e2cb8810.md,
  section "Final: the hermetic three-arm run (17:59-18:13Z, the CC's method default)":
  25027 bytes, SHA-256
  e2cb8810b47df696ca0015269550d78da099bf34e6eed0ff3e671171a3d671f4.

All twelve receipt/summary file hashes listed in HERMETIC-TABLE.md were checked
against their bytes. Independent inspection of the six receipt arrays verifies
192/192 hermetic sessions, zero memory markers, zero other-case prompt leaks,
and identical 11006-character SessionStart output. No transcript or hook
content is copied here.

| Hermetic observation | No cue | Original cue | Cue with exclusion |
| --- | ---: | ---: | ---: |
| security-audit, five phrasings, invoked | 13/20 | 20/20 | 20/20 |
| security-audit, five phrasings, turn one | 10/20 | 20/20 | 20/20 |
| security-best-practices indirect, invoked | 9/12 | 10/12 | 12/12 |
| security-best-practices indirect, turn one | 3/12 | 5/12 | 12/12 |
| security-audit on the indirect sibling request | 0/12 | 2/12 | 0/12 |
| Explicit sibling request, invoked and turn one | 4/4 | 4/4 | 4/4 |
| Near-miss negatives, any skill invoked | 0/28 | 0/28 | 0/28 |

These counts remain supporting observations. The arms differ by HEAD subject,
so the three-arm gain and its statistical comparisons do not supply the primary
effect size. The same-checkout ablation above controls that context and is the
comparison used for the 13/20 to 20/20 turn-one estimate.

The Final section also pools every measurement set of the indirect sibling
request: original-cue capture is 5/25 versus no-cue 0/25, Fisher p=0.050, and
exclusion capture is 0/22 versus original-cue p=0.052. The sibling is invoked
in turn one in 22/22 exclusion runs. This pool includes the earlier
non-hermetic sets; it is separate from the hermetic 2/12 versus 0/12 capture
comparison above. The original cue captured about one in five of those pooled
requests and no capture was observed in the exclusion runs. The pool is
descriptive support across measurement sets with context confounds, not a
same-HEAD estimate of the exclusion's isolated effect. These finite counts do
not establish a zero population risk or a precise organic capture rate. The
initial 3/3 and settling 0/10 interpretations are superseded by the primary
ablation and the explicitly qualified supporting results.

The cue and exclusion remain supported on the stated evidence. The exclusion
sentence names secure-defaults/best-practices
guidance for a design or endpoint and preserves audit, penetration-test and
exploitability triggers. No further executable change is needed. Naming
security-best-practices in the always-listed description is a possible
explanation for the sibling's first-turn improvement, not a tested mechanism.

These are explicit-task synthetic prompts that mirror descriptions, an upper
bound on organic triggering. They measure the model's first move and target
choice within three turns, not real-work invocation frequency or security
review quality. The six other skills' positive rows were not rerun
hermetically; their earlier non-hermetic aggregate cannot support a matched
three-arm claim. All seven near-miss negative rows were included. Daily
organic-use measurement remains a separate source.

The earlier v4 memory exposure was unequal: BEFORE 66/72 and AFTER 39/72.
The previous equal-exposure assertion was wrong, and the earlier v4 arms are
not cited as comparable evidence. Intermediate non-hermetic tables, the
settling result and their changing interpretations remain in the native
research record for audit history. The same-checkout ablation supplies this
decision's primary effect size; the three-arm table is supporting only.

## 2026-10-11 policy and integration correction

The previous on-listed ceiling was 11000 characters. This decision explicitly
raises both `trial.on_description_char_cap` and `budget.claude_on_cap` to
12000; describing that value as already existing was incorrect.
The repository's `scripts.skills_status.budget_report` derives
11791 Unicode description characters with the installed official
claude-api row, 1068 more than the 10723
characters for the other selected rows. The old ceiling cannot contain that
measured sum. The new ceiling retains the directive to list model-invocable
skills while accounting for the separately tracked native plugin. It is a
repository policy ceiling, not a measured client context budget; the Claude
listing fraction remains the existing 0.05. The trial now links to this dated
decision. A future increase requires another dated rationale and recalculation
with `budget_report`, not an unexplained edit to the ceiling.

The bundled claude-api duplicate reason remains applicable. The pinned
[Claude Code changelog](https://github.com/anthropics/claude-code/blob/2301018b1f61073c501a8e7a4813ef48c239163b/CHANGELOG.md)
adds `/claude-api` in 2.1.69 and updates it for Managed Agents in 2.1.290.
Registering the already-installed marketplace plugin supplies identity, age
and invocation measurement for the trial; it does not prove an advantage over
that bundled skill. A future capability decision needs a matched same-HEAD
comparison with the bundled baseline. The manifest retains that duplicate
rationale instead of treating registration as evidence that the duplicate
ceased to exist.

A lifetime count of zero is zero observed calls and a reason to check wiring.
The fleet view now says “zero calls; check wiring” for that count regardless of
a prior wiring-receipt label. Missing counts remain unknown and positive
counts retain their receipt status. Neither zero use nor a synthetic wiring
receipt with an unreported hermetic condition establishes absence of demand.
The revised display regression failed before the renderer change.

The central claude-api selection now serves the skills-implement sweep task
exactly once, with a native-client comparison requirement. It is explicitly
excluded from the frozen runtime-worker deployment through an
`adoption_ref`, a dated reason and an overturn condition. Existing worker
grants and source pins are preserved.

All shifted registrations were derived, not guessed. The architecture pin
locators use `tests.test_architecture_pin_source.expected_ranges`; the surface
watch locator uses its `DispositionCitationTests.has_token` identity check.
The pinned `scripts.local_pages_policy_grants.proposal` at
`90fab198098ef103b95c409c287f03ce5bd22f52` derives 93 exact
repository grants and one addition:
`.claude/skills/native-skill-routing/SKILL.md`. The policy grants only that
reviewed path, retaining exact set equality.

The native push-gate derivation at that same source commit adds
10 unclassified
`scripts/skills_status.py` reads and
1 read shape.
The dated accounting delta
`blueprints/runtime-workers/openhands/evidence/unclassified-gate-reads-20261011-skill-use-delta.json`
records the actual locations, script and shape changes, source commit and
original receipt hash. The original receipt remains intact. The guard still
compares every script count, every read-shape multiplicity and the total
(332), as well as its existing protection bounds.
This is monitoring accounting; it grants no new read or execution authority.

The architecture locator changes also invalidate the source digest embedded
in the generated WSL handbook. Its existing stale-output regression failed
after those changes. The supported
`python3 scripts/build_new_wsl_handbook.py --write` command regenerates both
outputs; its native `digest` function supplies their updated receipt hashes.
The supported generator and native replay are version-bound in the correction
source table below, using unchanged main source bindings rather than a
PR-branch pin. Those source bindings are distinct from the final landing base.
This refresh changes source-digest metadata, not handbook recommendations.

The focused local replay at 90fab198 reproduced nine failures across eight
test methods with no import errors. The same methods pass on the repaired
tree, together with all 13 fleet-view tests (21 methods in the combined
replay). The two architecture rows below are independent failing subtests
of the same method. These are local repository regression checks, not new
native model measurements.

| Regression method or subtest | 90fab198 | Repaired tree |
| --- | --- | --- |
| RuntimeWorkerManifestTests.test_contract_rejects_a_future_main_skill_in_neither_set | fail | pass |
| RuntimeWorkerManifestTests.test_contract_survives_main_reordering_its_skills | fail | pass |
| RuntimeWorkerManifestTests.test_every_adoption_skill_is_reused_or_explicitly_excluded | fail | pass |
| CatalogTests.test_every_pinned_skill_serves_exactly_one_task | fail | pass |
| RepositoryWorkflowTests.test_advisory_baseline_and_explicit_categories_stay_bounded_on_this_repository | fail | pass |
| PolicyGrantDerivation.test_committed_repository_grants_match_current_git_inventory_paths | fail | pass |
| DispositionCitationTests.test_every_cited_line_names_the_key, PostToolUseFailure | fail | pass |
| ArchitecturePinSourceTests.test_all_line_citations_identify_the_winners_pin_fields, openai/skills | fail | pass |
| ArchitecturePinSourceTests.test_all_line_citations_identify_the_winners_pin_fields, typesafe-ai/skills | fail | pass |

## Correction source bindings and maintained regressions

These bindings use the exact final source locations, derived from Python's
syntax tree and the native callable's source metadata. Files unchanged by
this PR are compared byte-for-byte with main
`878f2891aaa9027b10b7af3e4321ef5e882eedd0` and cited at that main commit.
Files added or changed by this PR are cited by repository path and line in
this PR, without a PR-branch SHA. Historical input-commit IDs in measurement
records identify their measured inputs, not durable code-source citations.

| Corrected mechanism | Primary source and supported entry point | Reproduced before and after result |
| --- | --- | --- |
| Description-budget accounting and dated ceiling | [`scripts/skills_status.py:543`](../../scripts/skills_status.py#L543) (this PR; no branch-SHA pin); `budget_report(manifest, skills_root="<skills-root>")` | The native sum is 11791 characters. The ceiling-decision regression fails with 90fab198's missing pointer and passes with the current dated rationale. The increase from main's 11000 ceiling is explicit policy, not an existing client limit. |
| Zero-call reading | [`tools/local-pages/fleet_view.py:243`](../../tools/local-pages/fleet_view.py#L243) (this PR; no branch-SHA pin); `_skill_usage` through the maintained fleet-view suite | The revised zero-call checks fail four assertions on the prior renderer and pass after; zero calls ask to check wiring for every receipt label. |
| Exhaustive runtime-worker adoption | [`tests/test_runtime_worker_skills.py:32`](https://github.com/seathatflowsinourveins/native-agent-stack/blob/878f2891aaa9027b10b7af3e4321ef5e882eedd0/tests/test_runtime_worker_skills.py#L32) (main `878f2891`); `adoption_contract_problems` and its three repository contracts | Three original failures report claude-api neither reused nor excluded; all three pass with the explicit adoption_ref exclusion and overturn condition. |
| Exhaustive lifecycle task map | [`tests/test_landscape_sweep_skills.py:133`](https://github.com/seathatflowsinourveins/native-agent-stack/blob/878f2891aaa9027b10b7af3e4321ef5e882eedd0/tests/test_landscape_sweep_skills.py#L133) (main `878f2891`); `CatalogTests.test_every_pinned_skill_serves_exactly_one_task` | The original missing claude-api task fails; the corrected map passes with exactly one implementation task. |
| Identity-bound architecture locators | [`tests/test_architecture_pin_source.py:49`](https://github.com/seathatflowsinourveins/native-agent-stack/blob/878f2891aaa9027b10b7af3e4321ef5e882eedd0/tests/test_architecture_pin_source.py#L49) (main `878f2891`); `expected_ranges` | Both original OpenAI/TypeSafe locator subtests fail before and pass after native identity-based derivation. |
| Identity-bound surface-watch locator | [`tests/test_upstream_surface_watch.py:2034`](https://github.com/seathatflowsinourveins/native-agent-stack/blob/878f2891aaa9027b10b7af3e4321ef5e882eedd0/tests/test_upstream_surface_watch.py#L2034) (main `878f2891`); `DispositionCitationTests.has_token` and its repository citation contract | The original PostToolUseFailure locator fails before and passes after native token-based derivation. |
| Exact reviewed inventory proposal | [`scripts/local_pages_policy_grants.py:109`](https://github.com/seathatflowsinourveins/native-agent-stack/blob/878f2891aaa9027b10b7af3e4321ef5e882eedd0/scripts/local_pages_policy_grants.py#L109) (main `878f2891`); `proposal` / the test's `inventory_paths` selector | The integrated expected and actual sets each contain 97 paths, derived on the current carry inventory input below, with no missing or extra path. |
| Push-gate accounting | [`blueprints/runtime-workers/openhands/resolver/push_gate.py:665`](https://github.com/seathatflowsinourveins/native-agent-stack/blob/878f2891aaa9027b10b7af3e4321ef5e882eedd0/blueprints/runtime-workers/openhands/resolver/push_gate.py#L665) (main `878f2891`); `derive_ci_protected` through `RepositoryWorkflowTests.derived()` | The original unclassified-read guard fails before; the regenerated delta preserves exact script, shape, total and protection comparisons against the new main baseline. |
| Handbook output provenance | [`scripts/build_new_wsl_handbook.py:1340`](https://github.com/seathatflowsinourveins/native-agent-stack/blob/878f2891aaa9027b10b7af3e4321ef5e882eedd0/scripts/build_new_wsl_handbook.py#L1340) (main `878f2891`); supported `--write`, `render` and `digest` APIs | The stale-output/receipt guard fails before regeneration and passes after native regeneration. |

The maintained public, count-only checks in
`tests/test_skill_correction_claims.py` load the published record and
manifest, without opening private transcripts or receipts. A native unittest
replay supplies exact public record/manifest snapshots from 90fab198 to those
same checks: each fails independently, with three failures and no errors or
skips. Each passes against the corrected files.

| Maintained claim check | Previous public inputs (90fab198) | Corrected public inputs |
| --- | --- | --- |
| `test_same_head_ablation_is_the_primary_comparison` | fail: no explicit same-HEAD primary comparison | pass: ablation identity/hash and two equal-size count-only arms |
| `test_ceiling_decision_resolves_to_its_dated_rationale` | fail: missing decision pointer | pass: confined dated pointer resolves to rationale naming the current ceiling and native listed sum |
| `test_registered_claude_api_keeps_a_supported_bundled_baseline` | fail: no explicit bundled baseline | pass: separate registration retains the bundled baseline, immutable official changelog reference and supported releases |

## 2026-10-11 landing integration

Historical #1013 integration base (retained as the reviewed source binding):
The final CC-cued main base is `ccff8765bf91aa02c0c4addad25d680d32abac89`.
The current carry base is `c735e8b2e7d096475ceed380ce956b9191af508c`. Its inventory was re-derived
at carry input `900a40a6b806228cfbe0ebafc16408b5bff69c82`
through the same native selector the maintained test calls. The count
below describes that current carry, separately from the historical
base and advisory delta source binding.
The test's own `inventory_paths` derivation returns 97 expected paths,
exactly equal to 97 actual reviewed repository grants, with no missing or
extra path. Main's three retired workflow grants remain retired; this PR's
routing skill is the reviewed addition. The maintained grant test uses #1013's
policy-derived `expected_count` rather than a branch-edited literal.
No grant count is copied from an earlier landing target.
The `878f2891` source bindings above remain valid
for the unchanged code; they do not identify the final landing base.

Main's regenerated push-gate baseline already separates test modules.
The merged guard preserves that baseline and the PR's exact script/shape
accounting, without the obsolete eight-location subtraction. A fresh native
derivation on the completed rebased input generates the current delta. The
measured parent/source input is
`cda8f6de85941787be7d331ac068ba28343978ac`:
342 unclassified reads, ten added skills_status reads and one added shape,
with no removals. It binds the current baseline hash
`5ea8e4db0ab15115e5b1eec6c1939450514dc227e0f9308d865f661507c6c93d`.
At the historical reviewed integration, the original final rebase
integration commit had that rebased input commit as its parent. Both full SHAs above were read from Git on the rebased input,
using `git merge-base HEAD origin/main` and `git rev-parse HEAD`, before
creating the final rebase integration commit. The delta's `source_commit` independently
identifies the measured input. Current main's native 332-read baseline is
retained unchanged. The delta is re-derived through the native mechanism;
exact script counts, shape multiplicities and total comparisons remain.

Each native location-difference identifier is classified in the delta's
`read_classifications`: ten `scripts/skills_status.py` observations belong
to skill/configuration status inspection, and three installer identifiers
are source-line moves with unchanged read multiplicity. The native bucket
remains `unclassified` and monitoring-only; these labels grant no worker
execution or read authority. The maintained native gate test checks complete
location coverage, the ten-read script counter, the allowed classifications
and `permission_change: false`, in addition to its existing exact script,
shape and total comparisons. The refreshed delta binds the current main
baseline rather than silently replacing its 332-read snapshot. This uses
the unchanged `GitTree` / `derive_ci_protected` route used by #982.

Historical observations: the earlier proposal on input `90fab198` held 93
paths and recorded 332 reads. The earlier landing at `878f2891` held 94
expected and actual paths, with `9fbac9b0` as its measured parent/source
input. These observations describe earlier targets, not this integration.
The later `8bffa2c4` landing and its `1e4f4654` source input are historical
too; the final main base and measured parent above supersede them.
The later `1e6a49ff` landing, its `561361c4` measured input and its
91-grant inventory are historical after main's #1004/#979 landings.
The later bcf55c45/9794477a input with 92 grants and 340 reads is historical
after the merge. The merged `82bb95d1`/`84131271` inventory with 94 grants
is historical after main's #1013 landing. The current 97-grant/342-read values above are measured,
not copied from an earlier landing or inferred from moving remote main.

The maintained `test_landing_record_matches_native_grants_and_measured_source`
in `tests/test_skill_correction_claims.py` derives the current reviewed sets
through the native selector cited above and checks the landing provenance
against the delta's measured input. It fails on the reviewed `52cbf6ac`
record with `94 != 91` and passes after this correction. The original three
claim regressions retain their separate historical replay results above.

### Final adjudication corrections and fail-first checks

The daily adapter now requires the native host report's Codex measurement
flag, a configured root and at least one scanned rollout before projecting
Codex invocation counts. The upstream native metadata is exposed by
[`tools/skill-usage/skill_usage.py:702`](../../tools/skill-usage/skill_usage.py#L702).
This follows the unavailable-root boundary in the existing Claude collector,
[`child-usage.mjs:3537`](https://github.com/seathatflowsinourveins/native-agent-stack/blob/1e6a49ffe8652918479e59bcb3751c0eb418e6d3/examples/claude-native/workflows/child-usage.mjs#L3537)
at that retained source-binding base. With no scanned rollout, the daily report emits
unmeasured/UNKNOWN Codex counts and no zero-use candidates. A scanned
rollout with zero uses remains a measured zero. This changes the daily
projection; the legacy host report's root semantics remain a follow-up.

The native-plugin policy remains registration of an already-installed
plugin, as recorded above at the bundled-baseline paragraph and in the
pinned upstream marketplace entry. The installer does not install it.
The default installer selection excludes native-plugin rows in every mode,
including `--check-only`. The plan's `installed_skills` selector excludes
them too and reports 28 managed skills. An explicit `--only` naming a native
plugin is refused; its provenance/status remains with the native status
checker. Native installation remains a separate CC-owned step. This replaces
the earlier nonfatal `not-installed` default behavior, whose acceptance and
plan layers were incomplete.

The native status check receives `os.environ`, so a fixture plugin under
`CLAUDE_CONFIG_DIR` is resolved identically by the installer and status
checker. The retained reference is
[`scripts/skills_status.py:250`](../../scripts/skills_status.py#L250), the
existing config-directory resolver, and the official
[environment-variable documentation, CLAUDE_CONFIG_DIR](https://code.claude.com/docs/en/env-vars#variables).
The official page states that this variable overrides the configuration
directory and stores settings, session history and plugins under that path.
This live documentation is unmirrored; the unmodified Markdown capture read
2026-10-11 is retained with SHA-256
`8097c27c0a5dd4b3428a61a9d3a79eb33b57c8eb30a3e5422d471d64c98f515f` in the last-correction
attachment directory. The former CHANGELOG.md:1138 citation described a
VSCode setting and did not support plugin registry resolution; it is removed.
No client settings or credentials are read by the fixture regressions.

Each correction has a fail-first maintained check: the landing regression
fails the old `94 != 91` record and, after rebasing, its old measured-source
claim; the absent-root projection fails with `True is not false`; fresh
normal/dry plugin runs fail with `0 != 1`; the custom config-directory
check also fails with `0 != 1`. The latter three methods produce four
failures before the code changes, with no errors. They pass after, retaining
positive controls for measured zero, explicit absence refusal and default
registry lookup. These are fixture checks, not fresh model measurements.

The last C2 correction adds two fail-first contracts: fresh-home default
`--check-only` excludes native-plugin rows, and the plan's installed set
omits the native plugin and counts 28 managed skills. Both fail on the
reviewed `d38ab63b` code (acceptance `0 != 1`, and `claude-api` unexpectedly
in the installed set) and pass after correction. All three default modes
exclude native rows; explicit native `--only` is refused in all three.
The rebase also makes the landing contract fail `91 != 92` before the
record is refreshed through its native selector. These supersede the
earlier C2 default-report policy without re-running the model experiment.

The handbook and receipt are regenerated through the supported native
APIs above. Native `register_file` and `evidence_manifest --write`
start from the cued main's registry, preserve its existing paths and
non-files fields, and register this PR's current files. Generated values
are produced by their native tools. Zero observed calls require a wiring
check and do not establish absence of demand.

Listing cost remains 267 Unicode characters for the original cue and 362 for
the excluded cue, an increase of 95. This project-scoped description is listed
in each session and sits outside the selected vendor manifest's description
budget. Vendor bytes, the positive dispatch body, worker grants and immutable
v4 cases remain unchanged.

The CC installs/enables the timer and applies any optional personal profile
after landing. This lane performed no model run, credential/account read or
host apply. The CC owns both families' range-diff micros and landing.
