# The `claude-native-practice` skill as a first-party manifest row — 2026-10-10

Pin this repository's own `claude-native-practice` skill in the central skills manifest as a first-party row, listed on Claude
Code (`on`) and enabled in Codex, and raise the manifest's own ceiling on the on-listed description sum from 10,500 to 11,000
characters. The command center ruled this on 2026-10-10 as option (a) of the four it was offered: raise the ceiling, retire a
trial skill, list the skill name-only, or keep it project-scoped. The 2026-09-30 listing record keeps every model-invocable skill
`on` with its description, and a move back to `name-only` needs the owner to revise that directive
([the record](2026-09-30-skills-llm-native-listing.md)), so a name-only row was not available without that revision; the ceiling
raise was chosen over retiring a trial skill and over keeping the skill project-scoped, and this record states what it costs.

## Source and row

The skill is `.claude/skills/claude-native-practice` in this repository, added by #923 and extended by #958 (landed as
`7a6bfbcf0`). The row pins this repository at that commit: tree `3a485d2a4bbe63dc1ae54e23101c472d21450b8c`, `SKILL.md` sha256
`a52a24bc7691fa18b3e4c532c6cbd15b79968d82a54acb4202c9fcced2ad8bcb` (2,224 bytes), description 349 characters by the manifest's method. No skill
body is copied. Installation uses the existing pinned Vercel Skills CLI tree-URL route (`skills add https://github.com/seathatflowsinourveins/native-agent-stack/tree/7a6bfbcf0a4f7201c64e5410c2ccbed1b224b511/.claude/skills/claude-native-practice --skill
claude-native-practice -g -y`). The row carries `first_party: true`: a skill of this repository has no skills.sh page, so its
`audits.url` says it is reviewed in the pull request that changes it, and `tests.test_skills_manifest` holds a first-party row to
that form and to this repository as its source while every other row keeps the skills.sh requirement.

## Listing check

The unchanged repository counter, [`scripts/skills_status.py`](../../scripts/skills_status.py), with
[`adoption/skills/manifest.json`](../../adoption/skills/manifest.json); the method is the manifest's
`description_chars_method`.

| Declared listing | Before | After | Change |
| --- | ---: | ---: | ---: |
| Claude on-listed descriptions | 10,374 | 10,723 | +349 |
| Manifest ceiling on that sum | 10,500 | 11,000 | +500 |
| Characters left under the ceiling | 126 | 277 |  |
| Codex enabled and catalog descriptions | 10,055 | 10,404 | +349 |
| Codex catalog skill count | 27 | 28 | +1 |

The row costs about 90 tokens in every session whose listing includes it (349 characters at the counter's one token per four
characters is 87): every Claude Code session that lists the skill and every Codex session whose catalog shows it. The
counter's Codex estimate for the 28-skill catalog is 3,171 tokens against the configured 6,000, so the
Codex setting still fits. These are declared listing and counter results; they are separate from a client's observed listing,
which the trial's `/skill-doctor` and `tools/skill-usage` measurements record.

## What else follows

- [`blueprints/runtime-workers/skills/manifest.json`](../../blueprints/runtime-workers/skills/manifest.json) excludes the skill
  from the runtime-worker selection through its existing `adoption_ref` contract, with a reason and an overturn condition, and its
  README counts the central skills reused (25 of 29).
- [`catalogs/landscape/skills-lifecycle.json`](../../catalogs/landscape/skills-lifecycle.json) gains this repository as a source at
  the row's pin and lists the skill once, under `agent-docs`; the task field `installed` follows the central manifest, and the
  addition performs no client installation.
- The Claude settings template adds `"claude-native-practice": "on"` so its declarative overrides equal the manifest; the Codex
  template's comment counts 28 catalog-visible skills.
- `catalogs/foundation/upstream-surface-dispositions.json` follows the manifest line it cites to its new place.

After the pull request lands, the designated host shell outside Claude installs the skill by
[`adoption/skills/lifecycle.md`](../../adoption/skills/lifecycle.md) and the pinned Vercel Skills CLI route; a skill pin does not
install itself.

## Changed test contracts for landing

Three main test methods change, as the [landing contract](../command-center.md#landing) requires them declared:

1. `tests.test_new_wsl_client_config.AgentGapTests.test_the_gaps_are_the_servers_and_skills_the_agents_name_beyond_the_wired_ones_and_the_plans_skills`:
   the plan's selected skill count changes from 27 to 28.
2. `tests.test_skills_status.SkillsStatusTests.test_real_manifest_codex_catalog_fits_the_configured_token_budget`: the real
   Codex catalog count changes from 27 to 28 and still must match the manifest description total and fit
   the unchanged 6,000-token setting.
3. `tests.test_skills_manifest.SkillEntryTests.test_audit_url_is_on_skills_sh`: a first-party row is held to the repository source
   and the not-applicable audit form instead of a skills.sh page.

## Inverse and revisit

The reversible inverse is to revert this commit: the row, its budget sums and ceiling, the template entries, the worker exclusion
and the landscape entries. A host uninstall follows the lifecycle's retirement procedure and its retained receipt; a metadata
revert alone does not remove an installed copy.

Revisit the 11,000 ceiling when the verdicts of the 2026-10-10 wave's thirteen skills-slot candidates land: return it to 10,500 if
the on-listed sum then fits, which needs at least 223 characters of listed descriptions retired, and otherwise
record the margin that remains. The same review keeps or removes this row from the skill's measured use, as the 2026-09-30
record's measured-invocation rule says.

## Re-pin (2026-10-11)

The row follows the skill to the commit that holds the results of the retirement of the Claude routes in GitHub (#1001), the cross-client source table (#986) and the paired-run results (#1005): `c59655c7c` (a commit of main). Only the
measured pin fields change, from the commit's own bytes: the ref and the tree URL, tree `f08d0d241b774112bbc1e1f43558e7604e4916b6` (was `3a485d2a4bbe63dc1ae54e23101c472d21450b8c`), `SKILL.md` sha256
`005288455c9d6a0bd70772847e2bb2411554d90eeabc0aa135af5d12fe99b353` (2,290 bytes, was 2,224). The description is unchanged at 349 characters, so the listing check above and its sums are unchanged, and the row's other fields
(first-party flag, listing, Codex enablement, audit text, gap text) equal the measured ones. `catalogs/landscape/skills-lifecycle.json` follows the pin of this repository. The skill is not installed by this change: the designated host shell
installs it by `adoption/skills/lifecycle.md` after the pull request lands, from the new pin (an installed copy at the old pin is stale until then).

## Reference repair and source ordering (2026-10-18)

Owner direction of 2026-10-18, paraphrased: qualify the current runtime foundation through pinned native installation, independent review and retained end-to-end evidence before accepting it. PR #1257 corrects source claims and keeps this first-party lifecycle source and the selected manifest ref equal.

The source pin is a verified predecessor of the manifest and install-receipt update, fetched through the supported installer. It may therefore be reachable through this pull request rather than main when the receipt is recorded. The lander squash-merges: that predecessor is not claimed to become an ancestor of main. The exact commit, skill tree and installed files must match before an install receipt passes. This ordering lets the receipt describe an actual installation without making a manifest refer to its own future commit. A later adoption may re-pin both records to the landed main commit; the current pin remains an explicit source identity, not an assertion of main-branch ancestry.
