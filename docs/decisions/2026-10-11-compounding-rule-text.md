# Decision: work compounds through reviewed, cited repository records (2026-10-11)

**Status:** rule text whose first sentence the owner approved and whose optional second sentence the command center
(CC) included under the owner's delegation (Trigger). The six repository surfaces change together in this PR; the
user-level files follow only after it lands (below).

## Trigger

On 2026-10-11, section 1 of the CC's 19:10Z ruling proposed text for the "The ecosystem compounds" bullet: a main
sentence and an "Optional second clause". At 19:12Z the CC sent both to the owner and asked for an OK or an edit.

- **The first sentence.** The owner approved the section 1 proposal at 22:01Z. The owner's answer is recorded in
  paraphrase and is not quoted here.
- **The second sentence.** It was presented as the optional clause, and the owner's answer did not single it out. The
  CC included it under the owner's delegation in that answer, because it restates the owner's own no-dates direction
  (the 17:31Z ruling below).
- **The owner was told at 23:44Z,** with the option to drop the clause before this PR lands. If the owner drops it, a
  recorded supersession removes it from every surface.
- The ruling is retained in
  `~/.local/state/native-agent-stack/coordination/command-center/research-cc-role-20261008/ruling-north-star-handbook-compounding-20261011.md`,
  SHA256 `9dfd309773abd0b24d0923e06426fd46212f92709fdb121fdc33121694ba138d`. Its last line still says that section 1
  waits for the owner's OK. Its addendum-01 beside it,
  `ruling-north-star-handbook-compounding-20261011.addendum-01.md` (23:56:42Z), SHA256
  `8dd06f2bdf349b4e584cb8943e7ba735e5e08cce33c66226e6db37f0504eda6c`, supersedes that line and records the facts
  above. It gives each sentence's UTF-8 SHA256: `a38a40e4622831a25641d3eaa1e0b80b3b73e756e3917262569f959f061461c5`
  for the first and `1be84fa09477e62c66379765971fb4d9f4811bff793b6b9ced0154954355b4bf` for the second.
- The second sentence comes from the CC's 17:31Z readiness ruling, which
  [the layer-resolution record](2026-10-11-layer-resolution-protocol.md) already cites (SHA256 `dd05310efdb5...`).

## The text

The two sentences go into the fourth core bullet, after "Proceed where the evidence converges, and apply or propose the
related improvements the work surfaces, at a moment that keeps the current focus and any protected window intact." and
before "Each choice adopts the current best converged practice":

> Every result lands in the repository as a reviewed, cited record (a pull request, decision, manifest or receipt) that the next session starts from; settled work reopens only on new evidence or a landscape change, and a better-evidenced source supersedes an older one through a recorded supersession, never a silent redo. Work starts when its named inputs exist, never on a date.

**What it changes.** The core now says how results compound:
- the next session starts from a reviewed, cited repository record;
- settled work reopens only on new evidence or a landscape change;
- a replacement is recorded as a supersession;
- readiness, not a calendar, starts work.

The sentence after it already says that a better-evidenced practice replaces an older one; the new text says how that
replacement is recorded. No tool, hook, check or runtime behavior changes, and this change reopens no settled record.

**What the second sentence leaves in force.** The trading lane's Claude read of us-equities-trading #87 proposed this
clarification (F1); the rule text on the surfaces does not change.

The second sentence forbids a date as the trigger that starts work; it leaves in force every time bound the contract states as a fact or protocol window, such as a live promotion record's `not_before`, market hours and a release receipt's date boundary.

## Evidence

**The corrections.** The CC's corrections log holds entries #161 to #172, all recorded on 2026-10-11 between 11:24:29Z
and 22:05:54Z. The log is the CC's own record outside this repository. It is append-only and still growing, so it is
cited here by entry number and recorded time rather than by a digest. Each correction was found after the fact and cost
at least one more pass:

- **State outside a reviewed record (5).**
  - #162 (16:06Z): a PR was ranked as the next paper session's path without tracing that path, which does not import
    the changed code. No timer or configuration for that session was registered either.
  - #166 (19:14:18Z, addendum 19:22:37Z): the row shape of an unversioned shared state file changed without its
    readers being checked. Two page services failed until they were fixed.
  - #167 (19:39:25Z): two PRs landed on review-verdict files that their runs were still rewriting. The landing evidence
    is the drafts' digests, not the finished records.
  - #169 (20:27:59Z): the user-level instruction file was said to stay in sync with landed rule text, but nothing reran
    the sync, so landed text would not have reached it.
  - #170 (21:53:52Z): citations were to be pinned at a PR-branch commit. A squash merge leaves that commit outside
    main's history, where the citation verifier's ancestry check fails it.
- **Work settled one way, then reopened or patched again (4).**
  - #161 (11:24:29Z): a privacy finding (published digests over unmasked bytes) was recorded as a convention until a
    second model family's read measured it. The fix re-derives every digest over the published bytes.
  - #163 (16:13Z): a fix-now ruling was made without reading the PR's earlier review records. Those records already
    showed the same sentence splitter drawing findings in five consecutive rounds.
  - #165 (17:16Z): one false claim was split into a fix now and a follow-up, which would have left the same claim
    false in the docs for a later round.
  - #172 (22:05:54Z): a guard-bypass class that had been ruled a follow-up for #1014 was re-ruled a P1 to fix in
    #1014, after a later read reproduced more forms of it. The log superseded #172 at 22:18:17Z: under the owner's
    threat model of 22:17Z, guard bypasses are follow-ups, not P1s, kept in the research queue (row 23). #1014 landed
    as `ccff8765`, and its only guard change lets `POINTER_VARIABLE` take a one-letter suffix; no deny-by-default
    pointer rule landed. Both changes of ruling are recorded.
- **A claim without its measurement (3).** The new text does not address these directly; they are listed so the twelve
  are complete.
  - #164 (16:58Z): an incomplete split rule for a names list, which can return a false zero.
  - #168 (19:50:37Z): a tool wrote a per-PR description that it had not computed.
  - #171 (21:56:26Z): a "no review posted" claim came from a query that could not see issue comments.

**The PR triage.** The CC's open-PR triage of 2026-10-11 (snapshot 19:35Z) measured the same costs across 97 open PRs,
86 here and 11 in us-equities-trading. It is retained in
`~/.local/state/native-agent-stack/coordination/command-center/research-cc-role-20261008/pr-triage-20261011.md`,
SHA256 `40ef7f137a4d0aaaa140a3a9a6057c3aadb0741ad3d02e3756f6115a54a67ee9`.
- 61 of the 86 open PRs here conflicted with main. Every one of them conflicted in the derived `manifests/evidence.json`,
  and 20 conflicted nowhere else. The median open PR here was 80 commits behind main.
- 39 PRs waited on one unmet input: a verdict wave, and main had recorded none since 2026-09-22.
- 7 finished PRs sat outside the landing wave. 61 PRs here and 5 in us-equities-trading had no CC record in the
  record directories the triage read.
- 15 PRs had three or more recorded Claude review rounds.
- 3 fold receivers (#878, #927, #958) merged without their 4 donors (#804, #915, #870, #829). The triage's line 64
  says 4 receivers; its addendum-01 beside it, `pr-triage-20261011.addendum-01.md`, SHA256
  `68a6060adb49b6c888c1d5a0c321b60b85b0a00457032bc042197e20db571b7a`, corrects the count from the triage's own rows.

These are records and counts, not a measured effect of the rule text on behavior (see Limits).

## Surfaces

The six always-loaded surfaces of `StandingRuleSurfacesTests.LAYERS` (`tests/test_install_claude_profile.py`) each
hold the core once, and all six now carry the new text in the same place.

| Surface | How it changes |
| --- | --- |
| `AGENTS.md` (:8) | Source, edited. |
| `examples/claude-native/CLAUDE.md` (:8) | Source of the Claude user block, edited. |
| `adoption/templates/codex.AGENTS.template.md` (:10) | Source of the Codex user block, edited. |
| `adoption/scaffold/AGENTS.md` (:9) | Scaffold source, edited. `tests/test_scaffold_repo.py` keeps its top-rule block byte-identical to the Codex template's. |
| `adoption/new-wsl/claude-user-instructions.md` (:8) | Generated by `python3 tools/adoption/new_wsl_client_config.py --write-blocks`: rc 0 at 22:20:40Z, no unit left out. |
| `adoption/new-wsl/codex-user-instructions.md` (:10) | Generated by the same command. |

Each changed line differs from main `569bbc59` only by the inserted text: 379 UTF-8 bytes with its leading space. Both
carriers stay byte-identical to their sources, as `cmp` showed after the write.

**Unchanged on purpose:**
- Root `CLAUDE.md` imports `@AGENTS.md`, so it loads the new text without a change. With a `CLAUDE.md` present, Claude
  Code reads `AGENTS.md` through that import only, and it skips an `AGENTS.md` that is already loaded under the
  together setting ([Claude Code memory](https://code.claude.com/docs/en/memory), "When Claude Code reads AGENTS.md"
  and "Choose which instruction files load", read 2026-10-11).
- `blueprints/us-equities/AGENTS.md` carries no copy of the core, only the corrections paragraph that #944 added.
  Trading sessions here load the root file as well.
- `REVIEW.md` carries review rules only. A review rule for this text is a follow-up and is not part of this change.

## How the user-level files pick it up

The repository changes no user-level file. After this PR lands, two mechanisms carry the text there:

- **The tool.** `tools/adoption/managed_block.py claude-md` rewrites the block between the managed markers of
  `~/.claude/CLAUDE.md` from `examples/claude-native/CLAUDE.md`. `codex-md` does the same for the canonical block of the
  Codex `AGENTS.md`, from the Codex template. Each backs the file up first and writes nothing when the block is already
  current (the module docstring). In `tests/test_managed_block.py`:
  - `test_a_changed_example_replaces_the_block_in_place_and_backs_up_first` and
    `test_replace_keeps_outside_text_mode_backup_and_rerun_is_idempotent` cover the rewrite;
  - `test_an_older_hand_copy_is_refused_with_nothing_written` covers a file without markers that holds an older copy.
- **The trigger on this host.** It is the CC's, outside this repository, and was added as correction #169's fix:
  - `cc-usage-refresh.timer` (hourly) runs `hourly_usage_refresh.sh`, whose line 20 runs `cc-tools/rules_resync.sh`;
  - that script runs both subcommands from the local-pages sources checkout, which `native-agent-pages-refresh`
    switches to `origin/main` every 10 minutes;
  - `rules_drift_watch.sh`, running at 22:29:37Z, reports drift or a failed re-sync.
- **The state before this change.** `rules-resync.json` at 2026-10-11T22:09:15Z records rc 0, source head `569bbc59`
  and "already current, nothing written" for both files. Each file held one managed begin marker at 22:26:44Z.

So the user-level files carry the new text only after main does: at the first hourly re-sync after the pages refresh
has switched the checkout to the landing commit. Another host picks it up when its installer or `managed_block.py`
runs there.

## Startup byte budget: the dated comparison

[The context-budget record](2026-10-05-harness-context-budget.md) (lines 164-171) requires a dated comparison before a
fixed ceiling changes. The figures below come from the test module's `startup_files()`, which counts the raw UTF-8
bytes of each client's loaded files, including the markers.

| Loaded file | Main `569bbc59` | This change |
| --- | ---: | ---: |
| Claude user block (the carrier with its managed markers) | 2,302 | 2,681 |
| Codex user block (the carrier, which holds its own markers) | 2,723 | 3,102 |
| `AGENTS.md` | 3,186 | 3,565 |
| `CLAUDE.md` (Claude only) | 320 | 320 |
| **Claude total** | 5,808 | 6,566 |
| **Codex total** | 5,909 | 6,667 |

- **Old ceilings.** 5,933 and 6,039 bytes: the 2026-10-09 totals of 5,650 and 5,751 plus 5%. The base above already
  includes #1008's 158-byte root bullet, which fit the old headroom.
- **New ceilings.** The new totals plus 5%, rounded up: 6,895 and 7,001 bytes (`STARTUP_BUDGET_BYTES`).
- **Required behavior.** Both sentences are always-loaded text (ruling section 1), in both clients and on every layer.
- **The Codex template's separate 8,192-byte check** still holds at 3,102 bytes. Codex's `project_doc_max_bytes`
  default of 32 KiB ([Codex AGENTS.md guide](https://developers.openai.com/codex/guides/agents-md), read 2026-10-11)
  is far above the 3,565-byte root file.

**Alternatives considered:**
- **A task pointer**, one line naming this record. It would cost far fewer bytes, but other projects lack this
  repository's paths (the user blocks and the scaffold leave it), and a pointer keeps the rule out of the startup
  context. Rejected.
- **The main sentence alone**, without the optional clause. It saves 58 bytes per copy, but the clause restates the
  owner's own no-dates direction, and the CC included it under the owner's delegation; the owner, told at 23:44Z, may
  still drop it (Trigger). Rejected unless the owner drops it.
- **The user-level blocks only, not root `AGENTS.md`.** It saves 379 bytes per client but breaks the one-core-on-every-
  layer rule of [the philosophy-only record](2026-10-08-philosophy-only-rules.md), which `StandingRuleSurfacesTests`
  enforces. Rejected.

## Checks

These are checks on repository text, pins and registration. They do not measure behavior.

- **The new test fails first.** `StandingRuleSurfacesTests.test_every_layer_and_renderer_carries_the_compounding_sentences_in_place`
  asserts that the text appears once, between the two sentences named above, on each of the six layers and in the
  outputs of the two native block renderers and the scaffold renderer. Against the unedited surfaces at
  2026-10-11T22:20:18Z it failed with 9 failing subtests (six layers, three renderers), rc 1. It passes after the edit
  and the regeneration.
- **The existing equality tests are updated, not loosened.** `CORE` now holds the text in its place, so four tests keep
  pinning byte equality: `test_the_portable_block_is_exactly_the_core_and_the_evidence_backed_line`,
  `test_every_layer_carries_the_same_core_and_no_dropped_rule`, `test_native_instruction_renderers_keep_the_amended_common_core`
  and `test_the_repository_file_keeps_its_core_and_the_trading_prerequisite`. With the surfaces edited and the old
  `CORE`, the class reported 11 failures in those four tests at 22:20:48Z.
- **The Codex top-rule pin.** `TOP_RULE_SHA256` in `tests/test_codex_worker_lane.py` was re-derived with that module's
  own `template_segments()`: 2,296 UTF-8 bytes (1,917 plus 379),
  `7dc76265052d6610fdc91c4f72db22bbbe5f4fd002cd8fcaa35bffc5fa2bde8f`. The old pin failed against the edited template
  at 22:20:58Z.
- **The budget.** `test_rendered_startup_files_fit_each_clients_fixed_byte_budget` failed against the old ceilings at
  22:20:58Z (Claude 6,566 over 5,933; Codex 6,667 over 6,039) and passes with the new ones.
  `test_growth_in_any_loaded_file_crosses_the_fixed_budget` fills the available headroom in each loaded file in turn, verifies that equality with the ceiling passes, then appends a two-byte UTF-8 character and verifies rejection.
- **The module runs**, from 22:21:36Z to 22:24:52Z, all rc 0:

  | Module | Tests | Skipped |
  | --- | ---: | ---: |
  | `test_install_claude_profile` | 123 | 1 |
  | `test_codex_worker_lane` | 123 | 12 |
  | `test_scaffold_repo` | 19 | 0 |
  | `test_new_wsl_client_config` | 230 | 0 |
  | `test_managed_block` | 43 | 0 |
  | `test_codex_roles` | 38 | 0 |

## Overturn

- A same-version A/B on an upstream harness (promptfoo for the gateway lanes, Harbor or Inspect for agent tasks) shows
  that the added text raises startup cost without a measured gain in rule-following. A pointer or a shorter wording
  then replaces it, through a new record that supersedes this one.
- A client release changes how `CLAUDE.md` or `AGENTS.md` load or are sized.
- The owner rewords the rule.
- Recorded incidents show sessions still redoing settled work, or starting on a date, with this text loaded. The
  enforcement then belongs in a hook, check or workflow, not in more text.

## Limits

- No behavior is measured. The checks show where the text is and that it is identical, not that agents follow it.
- The user-level pickup rests on the CC's host tooling, which this repository neither versions nor tests.
- The corrections log, the ruling, the triage and their addenda are the CC's private records. This record restates
  what it relies on.

## Sources

- **Rule mechanics at main `569bbc59`:**
  - [the rule-text record](2026-09-30-rule-text-every-layer.md): one wording on every surface (lines 57-59), the
    scaffold copy (line 78), and the 2026-10-07 addendum (lines 295-312);
  - [the corrections record](2026-10-09-corrections-rule.md): the same insertion, regeneration (line 19) and pin
    re-derivation (line 44);
  - `tools/adoption/managed_block.py` and `tests/test_managed_block.py`;
  - `cmd_write_blocks` in `tools/adoption/new_wsl_client_config.py`.
- **Client loading:**
  - [Claude Code memory](https://code.claude.com/docs/en/memory), read 2026-10-11: `~/.claude/CLAUDE.md` holds
    personal preferences for all projects, plus the AGENTS.md sections cited above;
  - the [Codex AGENTS.md guide](https://developers.openai.com/codex/guides/agents-md), read 2026-10-11:
    `project_doc_max_bytes`, 32 KiB by default.
- **Supersession rather than erasure:**
  - Michael Nygard, [Documenting Architecture Decisions](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions),
    2011-11-15, read 2026-10-11: a reversed decision is kept and marked superseded, with a reference to its replacement;
  - [MADR 4.0.0 `template/adr-template.md`, line 3](https://github.com/adr/madr/blob/2475fe1973f66a12aaf58a91d8fa7b42c0f5ea3d/template/adr-template.md#L3):
    its status field includes "superseded by ADR-0123".
- **CC records,** private and outside this repository: the ruling, the triage and their addenda-01 at the SHA256s
  above, corrections #161 to #172 with #172's supersession, and the readiness ruling that the layer-resolution record
  cites.
