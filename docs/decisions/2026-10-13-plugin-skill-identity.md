# A plugin's skill is listed under its own name whatever `skillOverrides` says: one copy of each per client, 2026-10-13

CPA-V-07 of the Claude-family practice audit (`claude-practice-audit-converged-20261012`, P2, measured): `typesafe-ai` and `claude-api` are each delivered to Claude Code by two routes, so each is listed twice with one description, and the
practice page said that `skillOverrides` governs skills. This record states what the client does (measured and read from its documentation), which copy of each pair stays, how the manifest and the status check say it, and the one step
that is the command center's: the host's own `skillOverrides`. The change writes no host configuration.

## Context

- `typesafe-ai` is this repository's skills.sh copy (the canonical folder under `~/.agents/skills`, linked into `~/.claude/skills` as a personal skill) and also the vendor's Claude Code plugin, `typesafe@typesafe-ai`, which the vendor's
  README gives as its Claude Code route (`claude plugin marketplace add typesafe-ai/skills`, `claude plugin install typesafe@typesafe-ai`; `typesafe-ai/skills@65a39f393687` README, "Claude Code plugin" and "Other agents via skills.sh").
- `claude-api` is a native plugin row of the manifest (`claude-api@anthropic-agent-skills`, pinned to `anthropics/skills@dbd4588f9e1033efb41dad4bef2f7947c8993d44`, trial since 2026-10-10) and also a skill that the client bundles.
- The audit counted the cost of the duplicates at 660 + 1,068 characters of skill listing in every session (the `description_chars` of the two manifest rows), and found the practice page's skills-library row saying the skills are governed
  by `skillOverrides` with no exception.

## Measurement

Claude Code 2.1.296. `skillOverrides` is the documented way to hide a skill ("`off` hides from model and `/`", `anthropics/claude-code@3deb8736` `CHANGELOG.md` L5319), and the documentation excludes plugin skills from it
(`code.claude.com/docs/en/skills.md` L909: "Plugin skills are not affected by `skillOverrides`. Manage those through `/plugin` instead."; L928 and L333, `receipts/docs-skills-md-excerpt.txt`, fetched 2026-10-13T10:29:20Z, sha256
`35fd2c11...`). The client lists a plugin's skill as `<plugin>:<skill>`. Measured with headless sessions started in an empty directory with `--settings <overlay>`, the init record's skill list read and the session killed before any model
call (the host's settings are untouched; `receipts/listing-init-records.json`; the first five runs were captured earlier on 2026-10-13 and the rerun gave the same counts and names):

| `skillOverrides` overlay | Skills listed | `claude-api` | `claude-api:claude-api` | `typesafe-ai` | `typesafe:typesafe-ai` |
| --- | --- | --- | --- | --- | --- |
| none | 77 | listed | listed | listed | listed |
| `claude-api: off` | 76 | hidden | listed | listed | listed |
| `typesafe-ai: off` | 76 | listed | listed | hidden | listed |
| `claude-api:claude-api: off` | 77 | listed | listed | listed | listed |
| `typesafe:typesafe-ai: off` | 77 | listed | listed | listed | listed |
| both bare names off | 75 | hidden | listed | hidden | listed |

So an entry hides the copy it names (the client's bundled one, the personal one) and nothing else; a qualified key changes nothing. The only copy that can be hidden by `skillOverrides` is the one that is not the plugin's.

Whether hiding the personal copy breaks an agent that preloads the skill: ten probes with a project subagent whose frontmatter lists the skill (`skills: typesafe-ai` or `skills: typesafe:typesafe-ai`), asked whether the skill's full text is in its
context and to quote its first body heading, on `claude-haiku-5-5`: all ten quoted it, among them the three short-name and the three qualified-name probes with the personal copy hidden (`receipts/preload-probes.json`).

## The `claude-api` currency comparison

The choice between hiding the bundled copy and disabling the plugin (the audit's two options) depends on whether the plugin's copy at the manifest's pin is behind the one the client bundles. It is not (`receipts/claude-api-currency.txt`): of the 94 files in
the folder that the client unpacks for the bundled skill, 91 are byte for byte the plugin's; the three that differ (`shared/evals/build-eval.md`, `shared/evals/eval-hillclimb.md`, `shared/model-migration.md`) differ in wording about the early-access
install, which the bundled variants carry and the plugin's omit; `SKILL.md` (inlined in the bundled prompt) differs by the client's header line against the plugin's frontmatter, two "(EAP install)" phrases and one closing line about language
detection; the plugin's folder also holds `LICENSE.txt`. The plugin's copy lacks nothing of substance that the bundled one has. The plugin is the copy the manifest pins and checks (tree and `SKILL.md` hash, a trial under the 30-day rule), while the
bundled copy moves with the client release, so the plugin stays and the bundled copy is the one hidden. Not established: that the bundled copy never moves ahead of the pin; the comparison is repeated at each re-pin and when a client release
changes the skill (overturn conditions).

## Decision

1. **Each row names its twin.** `adoption/skills/manifest.json`: `typesafe-ai` carries `claude_plugin: typesafe@typesafe-ai` and `claude_skill_name: typesafe:typesafe-ai` (its personal copy remains the Codex route and the Claude route on a host without the plugin);
   `claude-api` keeps `native_plugin` and `claude_skill_name: claude-api:claude-api` and gains `bundled_twin: claude-api`, the bare name the client lists its own copy under. `load_manifest` checks the fields: a plugin id is `<plugin>@<marketplace>`,
   `claude_plugin` and `native_plugin` exclude each other, `bundled_twin` belongs on a `native_plugin` row, and `claude_skill_name` must be `<plugin>:<skill>`.
2. **`scripts/skills_status.py` reports a duplicate.** Where the plugin is present (the native registry `installed_plugins.json` holds a user-scope install, and `settings.json` has `enabledPlugins` true for it) the other copy must be hidden: the row
   gets a `claude_twin` entry, `ok` when the twin is hidden and `duplicate_listing` when not; for the personal copy the listing expected on such a host is `off` instead of the manifest's `on`. The twin is hidden by `skillOverrides` `off` under its
   name (a wrong type hides nothing) and, for the client's bundled twin, by disabling bundled skills as a whole: `disableBundledSkills` true in the user settings or `CLAUDE_CODE_DISABLE_BUNDLED_SKILLS` (review round 1 below; it hides no personal
   copy). The plugin that stays must be the pinned one: an installed and enabled plugin at another commit, outside the plugin cache, with another `SKILL.md` or none is `plugin_invalid`, whether or not the other copy is hidden, because the client
   lists it all the same. The registry is read from the folder the settings are read from (the client's configuration folder), and a Claude-only copied row gets the same twin check as a linked one. On a host without the plugin nothing
   changes: the personal copy keeps the manifest listing, one copy. Only ids and states are read, never an install path or a credential, and a `settings.json` that cannot be read lists no plugin, so the personal row's own listing check
   reports the unreadable file.
3. **The usage tracker counts both listings.** `skill_usage.py` `claude_row` adds the uses and the context of the two names a skill is listed under (`claude_skill_name` and the personal or bundled name) and takes the last use of the listings that were used, the most recent: the cells of the table are put in
   order (`never`, `today`, `N days` and, in older tables, `N hours ago`), and a cell that cannot be ordered (an absolute date, a month) makes the combined date unknown, never the plugin's older one;
   the zero a hidden twin would otherwise leave next to the plugin's count is not read as no use.
4. **The practice page states the exception.** The skills-library row of `.claude/skills/claude-native-practice/reference/instructions-skills.md` and its `slots.json` say that `skillOverrides` changes nothing about a plugin skill's listing, what was measured,
   and where the manifest and the status check carry it. A test holds the page's needles (the audit's fail-first).
5. **The profile template stays as it is.** `adoption/templates/claude.settings.template.json` keeps `typesafe-ai: on` and no `claude-api` entry: a fresh host installs one copy, and which copy a host has is the host's. A test holds it.
6. **Host step, the command center's act** (this change writes no host configuration): in the first host's `~/.claude/settings.json`, `skillOverrides`:

   ```
   -    "typesafe-ai": "on",
   +    "typesafe-ai": "off",
   +    "claude-api": "off",
   ```

   Simulated against the first host's real settings with those two keys substituted in memory (`receipts/host-overlay-simulation.json`): `skills_status.py` reports `fail` today (the two rows, `duplicate_listing`) and `ok` after. Until the step is
   made, the status of that host is `fail` for exactly these two rows, which is the check working. Re-applying the profile template (`tools/adoption/apply_claude_settings.py` deep-merges and the template wins on shared keys) sets
   `typesafe-ai` back to `on`: the status reports the duplicate again and the step is repeated until the decision moves into the template (follow-up).

## Review round 1 (Astra's read of `2dae9751`: two P1 and a P2; the local codex review: three P2; one commit for the six, after the command center's read)

| Finding | Fix | Test (fails before the fix) |
| --- | --- | --- |
| P1 (Astra), `receipts/claude-api-currency.txt:45`: the receipt published the digest of the prompt that the client expands for its bundled skill, whose first line names the folder the client unpacked the skill into on this host; no published file hashes to it and its preimage holds a path of the host, so it was a confirmation oracle for a private preimage (the #161 class) | the digest and every prefix of it are removed from the receipt; the plugin file's digest (the manifest's `skill_md_sha256`, an upstream blob at the pin) stays; the receipt says why the other is not published. No history rewrite | `tests/test_plugin_skill_identity_receipts.py`: every digest in the evidence folder, its README and this record resolves to a registered file, a manifest pin or a public page quoted with its URL and fetch time; the text receipts are in its reach (the scanner of `test_published_digest_privacy` reads JSON). The mutant that writes the digest back is killed |
| P1 (Astra), `scripts/skills_status.py:495-499`: a host that disables bundled skills as a whole has one copy of `claude-api` and was reported as a duplicate | the bundled twin is hidden by `disableBundledSkills` true or `CLAUDE_CODE_DISABLE_BUNDLED_SKILLS`; measured on 2.1.296 (`receipts/global-disable-init-records.json`, 30 runs): 77 skills listed, 61 with either, the bundled `claude-api` gone and the plugin's kept; only the boolean true counts in the setting (the string, the number 1 and null disable nothing); the variable counts as 1, true, TRUE, yes, on and a padded ` 1` (not 0, 2, false, off, no, y, t, enabled or empty); the settings `env` entry (a string, number or boolean) overrides the process environment in both directions; each disables alone. Documented: `code.claude.com/docs/en/env-vars` (the variable's row, `receipts/docs-env-vars-excerpt.txt`), `skills.md` L29 and L333, `anthropics/claude-code@3deb873687379f0c199a69fdaccc65f0865f7a29` `CHANGELOG.md` L4500 (2.1.169). A personal twin is not a bundled skill and stays a duplicate | `test_a_bundled_twin_is_hidden_by_disabling_bundled_skills_as_a_whole`, `..._by_the_environment_equivalent_of_that_setting`, `test_the_env_entry_of_settings_overrides_the_environment_and_may_be_a_number_or_a_boolean`, `test_disabling_bundled_skills_hides_no_personal_copy_and_an_unreadable_settings_file_disables_nothing` |
| P2 (Astra), `tools/skill-usage/skill_usage.py:2542-2544`: the combined row took the first used listing's date, the plugin's, so a plugin used 7 days ago and a personal copy used an hour ago reported 7 days ago | the used listings' cells are put in order and the most recent is taken; a cell that cannot be ordered makes the date unknown (`last_used_age_seconds`); the cell spellings are the client's (`never`, `today`, `N days`; its table formatter is in the 2.1.296 binary, `daysSinceUse` null, 0 or a count) and the older table's | `TwinListingUsageTests.test_the_combined_last_use_is_the_most_recent_of_the_listings_that_were_used_whichever_is_listed_first` (both twin kinds, both orders, nine spellings) and `test_a_listing_that_was_not_used_does_not_count_and_one_that_cannot_be_put_in_order_makes_the_date_unknown` |
| P2 (local review), `scripts/skills_status.py:471-474`: a registry row with `scope: user` was enough, even at another commit or with its cached skill gone, so a hidden personal copy passed behind a plugin that was not the pinned one | `plugin_status` (the native plugin checker's own read) validates the plugin before the twin is accepted: pin, folder, bytes; the twin entry is `plugin_invalid` with the state (`pin_mismatch`, `invalid_install_path`, `hash_mismatch`, `cache_unreadable`) | `test_a_replacement_plugin_that_is_not_the_pinned_one_is_not_accepted_for_a_hidden_copy` (four breakages, hidden and not) and `test_a_native_plugin_row_that_is_not_as_pinned_reports_its_twin_as_invalid_too` |
| P2 (local review), `scripts/skills_status.py:710-711`: the registry was read from the skills CLI's link folder, which trims `CLAUDE_CONFIG_DIR` and falls back to `~/.claude` for a blank value, while the settings are read as the client reads them; a padded or blank value sent the two to different folders and an enabled plugin looked absent | the registry is read from the folder of the settings file (`claude_config_dir`: the client's configuration folder, which `CLAUDE_CONFIG_DIR` moves with "all settings, session history, and plugins"); the native plugin status reads it too | `test_the_plugin_registry_is_read_from_the_folder_of_the_settings_that_enable_the_plugin` and `test_the_native_plugin_status_reads_the_registry_of_the_folder_the_client_uses` |
| P2 (local review), `scripts/skills_status.py:759-760`: a Claude-only copied row (`copy`, `agents: ["claude-code"]`) with `claude_plugin` took the copied-skill branch, which never computed the twin | the branch computes the twin and the adjusted listing like the linked one | `test_a_claude_only_copied_skill_gets_the_twin_policy_too` |

The cases were reproduced on `2dae97511` and pass on this head (`receipts/fail-before-round1.txt`: 14 tests fail or raise there); the original fail-first tests replayed at the exact base `993cc890b` give the same 22 of 142 (`receipts/fail-before-at-main-993cc890b.txt`, Astra's P3 6, which also relabels `receipts/fail-before.txt`); 30 mutants of the round's changes are killed (`receipts/mutants-round1-30.txt`).

Dispositions of the rest of the read, none changing code in this round: item 4 (P2, adjacent): a disabled native plugin plus an already hidden bundled twin passes, because the native-plugin checker has no enablement requirement and never had one; a future correction distinguishes an installed plugin from an active route (follow-up). Item 5 (P3): project and local scope installs and the profile replay (`apply_claude_settings.py` restores `typesafe-ai: on`) stay the recorded boundaries (above, "What is not covered", decision 6). Item 7 (P3, inherited): the anchor `catalogs/sota-convergence/manifest-20260926.json:6521` was already stale at the base. Item 8 (P3, inherited): five hostname occurrences in the full changed files, none added here.

## Alternatives

- **Disable the plugins, keep the personal copy and the bundled one:** `/plugin` is the documented way to turn a plugin skill off, but the typesafe plugin is the vendor's Claude Code route and the `claude-api` plugin is the pinned trial row; disabling them
  retires the pinned route and leaves the bundled copy, which the manifest does not pin.
- **Hide the plugin's copy with `skillOverrides`:** not possible (measured above).
- **Set `typesafe-ai: off` and enable the plugin in the template:** a fresh host would then have no typesafe skill in Claude Code until the plugin is installed, which the profile installer does not do; the dynamic expectation keeps one copy on every host.
- **Leave the duplicates:** 1,728 characters of listing in every session for no gain, and the practice page wrong.

## What is not covered

- Plugin installs at project or managed scope are not counted as present: the registry check counts a user-scope install, the scope the installer and the vendor's README use.
- The preload probes cover the typesafe skill and one model; the claim is that hiding the personal copy leaves the preload by either name intact, not a statement about every agent.
- The client's answer `on` for any plugin skill (the audit cites it from the 2.1.296 binary) was not re-checked; the listing runs above are the evidence.
- The usage counts of the two listings are added; a skill used through both in one window is counted for both uses.
- Follow-up (Astra's read, P2, adjacent): the checker of a native plugin row does not require the plugin to be enabled, so a disabled plugin with the bundled twin already hidden reports `ok` although neither route lists the skill; the twin check treats a disabled plugin as not present. Trigger: the next change to `native_plugin_status`: report an installed plugin separately from an active route.
- Follow-up (Astra's read, P3): `catalogs/sota-convergence/manifest-20260926.json` anchors a mutation-testing deferral at `adoption/skills/manifest.json#L788-L791`, which already described another row at the base. Trigger: the next edit of that catalog.

## Overturn conditions

- A client release or documentation change that makes `skillOverrides` govern plugin skills (`skills.md` L909 and L928 change): the exception text, `bundled_twin` and the twin check are then re-derived.
- The bundled `claude-api` copy moves ahead of the pinned plugin copy in substance (repeat `receipts/claude-api-currency.txt` at each re-pin and client release): re-pin the plugin or flip which copy is hidden.
- A third skill delivered by two routes: add its row fields (the loader and the check are general).
