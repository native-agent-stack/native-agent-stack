# Receipts for CPA-V-07: a plugin's skill is listed under its own name (2026-10-13)

Value-free captures behind the measurements of [the decision record](../../../docs/decisions/2026-10-13-plugin-skill-identity.md), taken on the first host with Claude Code 2.1.296 (headless sessions, the host's settings untouched).
Nothing here holds an account name, a host name, a home path, a key or a transcript: skill names, counts, flags and file hashes only.

| File | What it shows |
| --- | --- |
| `receipts/listing-init-records.json` | the six init-record runs: the number of skills the client lists and which of `claude-api`, `claude-api:claude-api`, `typesafe-ai` and `typesafe:typesafe-ai` are among them under no overlay, `claude-api: off`, `typesafe-ai: off`, each qualified key off, and both bare names off (77, 76, 76, 77, 77, 75); the first five were captured earlier on 2026-10-13 with identical counts and names |
| `receipts/preload-probes.json` | ten probes: a project subagent that preloads the typesafe skill by its short or its qualified name, asked whether the skill's full text is in its context, with the default settings and with the personal copy hidden; all ten quoted the first heading of the body |
| `receipts/claude-api-currency.txt` | the client's bundled `claude-api` folder against the plugin's pinned folder by sha256 (94 and 96 files; 91 identical; three differ in early-access wording; the plugin's folder adds `LICENSE.txt` and `SKILL.md`), the difflib summaries of the three, and the `SKILL.md` comparison |
| `receipts/docs-skills-md-excerpt.txt` | lines 333, 909 and 928 of the skills documentation page (fetched 2026-10-13T10:29:20Z, with its size and sha256): plugin skills are not affected by `skillOverrides` |
| `receipts/host-overlay-simulation.json` | `scripts/skills_status.py` on the first host's real settings, then with the two proposed `skillOverrides` entries substituted in memory: `fail` (two rows, `duplicate_listing`) and `ok`; the host's file is untouched |
| `receipts/fail-before.txt` | the three test modules the change touches against the sources of the pull request's base (`3f1a921dd`): 22 of 142 tests fail or raise, among them the audit's two fail-first tests (a plugin row without `claude_skill_name`; the practice page without the plugin exception) |
| `receipts/mutants-v07-41.txt` | the 41 mutants of the change (the loader checks, the registry and settings readers, the twin check, the expected listing, the combined usage row): 41 of 41 killed |

The mutation driver, the listing capture scripts and the probe project (two subagents) are scripts and files of the author's private record; the method is in the record and in each receipt.

## Claims of the decision record without a receipt here

- **The listing cost of the duplicates (660 + 1,068 characters):** the `description_chars` of the two manifest rows, as the audit counted them (CPA-C-011); not a measurement of the client's listing text.
- **The client's answer `on` for any plugin skill** (the audit cites it from the 2.1.296 binary): not re-checked; the listing runs are the evidence.
- **The changelog line** (`anthropics/claude-code@3deb8736` `CHANGELOG.md` L5319) and the vendor's README lines (`typesafe-ai/skills@65a39f393687`): read from the local mirrors at those pins; no capture is kept.

The measurements are the author's, taken on one host; nothing here is a measurement by an independent party.
