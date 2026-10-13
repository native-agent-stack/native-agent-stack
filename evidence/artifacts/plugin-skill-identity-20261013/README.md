# Receipts for CPA-V-07: a plugin's skill is listed under its own name (2026-10-13)

Value-free captures behind the measurements of [the decision record](../../../docs/decisions/2026-10-13-plugin-skill-identity.md), taken on the first host with Claude Code 2.1.296 (headless sessions, the host's settings untouched).
Nothing here holds an account name, a host name, a home path, a key or a transcript: skill names, counts, flags and file hashes only.

| File | What it shows |
| --- | --- |
| `receipts/listing-init-records.json` | the six init-record runs: the number of skills the client lists and which of `claude-api`, `claude-api:claude-api`, `typesafe-ai` and `typesafe:typesafe-ai` are among them under no overlay, `claude-api: off`, `typesafe-ai: off`, each qualified key off, and both bare names off (77, 76, 76, 77, 77, 75); the first five were captured earlier on 2026-10-13 with identical counts and names |
| `receipts/preload-probes.json` | ten probes: a project subagent that preloads the typesafe skill by its short or its qualified name, asked whether the skill's full text is in its context, with the default settings and with the personal copy hidden; all ten quoted the first heading of the body |
| `receipts/claude-api-currency.txt` | the client's bundled `claude-api` folder against the plugin's pinned folder by sha256 (94 and 96 files; 91 identical; three differ in early-access wording; the plugin's folder adds `LICENSE.txt` and `SKILL.md`), the difflib summaries of the three, and the `SKILL.md` comparison (the digest of the expanded prompt is not published: its first line names the folder the client unpacked the skill into on the host) |
| `receipts/docs-skills-md-excerpt.txt` | lines 333, 909 and 928 of the skills documentation page (fetched 2026-10-13T10:29:20Z, with its size and sha256): plugin skills are not affected by `skillOverrides` |
| `receipts/host-overlay-simulation.json` | `scripts/skills_status.py` on the first host's real settings, then with the two proposed `skillOverrides` entries substituted in memory: `fail` (two rows, `duplicate_listing`) and `ok`; the host's file is untouched |
| `receipts/fail-before.txt` | the three test modules the change touches against the sources of the pull request's base (`3f1a921dd`): 22 of 142 tests fail or raise, among them the audit's two fail-first tests (a plugin row without `claude_skill_name`; the practice page without the plugin exception) |
| `receipts/mutants-v07-41.txt` | the 41 mutants of the change (the loader checks, the registry and settings readers, the twin check, the expected listing, the combined usage row): 41 of 41 killed |
| `receipts/docs-env-vars-excerpt.txt` | the rows of the environment-variables page (fetched 2026-10-13T13:38:26Z, with its size and sha256) that give `CLAUDE_CODE_DISABLE_BUNDLED_SKILLS` as the equivalent of `disableBundledSkills` and `CLAUDE_CONFIG_DIR` as the folder of settings and plugins, and the changelog line of 2.1.169 |
| `receipts/global-disable-init-records.json` | 30 init-record runs of 2.1.296 with the plugin enabled: the number of skills listed and whether the bundled `claude-api` and the plugin's are among them under the setting and the variable in every spelling tried, with the settings `env` entry and their precedence |
| `receipts/fail-before-round1.txt` | round 1 against the sources of `2dae97511`: 14 tests fail or raise (the global switch, the replacement plugin, the registry folder, the copied row, the last use, the digest of the private prompt) and pass on this head |
| `receipts/fail-before-at-main-993cc890b.txt` | the fail-first tests of the first commit replayed at the exact base of its head (main `993cc890b`): 22 of 142 fail or raise, the count `receipts/fail-before.txt` gave against the pre-rebase base |
| `receipts/mutants-round1-30.txt` | the 30 mutants of round 1 (the global switch, the plugin validation, the registry folder, the copied skill, the ordering of the last use, the private digest): 30 of 30 killed |
| (the advisory delta) | `blueprints/runtime-workers/openhands/evidence/unclassified-gate-reads-20261013-pr1074-delta.json` and its index entry: round 1 removes two reads of `scripts/skills_status.py` (346 reads), derived with the native `GitTree` and `derive_ci_protected` at the committed head |

The mutation driver, the listing capture scripts and the probe project (two subagents) are scripts and files of the author's private record; the method is in the record and in each receipt.

## Claims of the decision record without a receipt here

- **The listing cost of the duplicates (660 + 1,068 characters):** the `description_chars` of the two manifest rows, as the audit counted them (CPA-C-011); not a measurement of the client's listing text.
- **The client's answer `on` for any plugin skill** (the audit cites it from the 2.1.296 binary): not re-checked; the listing runs are the evidence.
- **The changelog line** (`anthropics/claude-code@3deb8736` `CHANGELOG.md` L5319) and the vendor's README lines (`typesafe-ai/skills@65a39f393687`): read from the local mirrors at those pins; no capture is kept.

The measurements are the author's, taken on one host; nothing here is a measurement by an independent party.
