# The plugins a profile template enables are held to a pin record: a tag where the template names one, a recorded exception where it cannot, and a test that fails without either, 2026-10-13

CPA-V-11 of the Claude-family practice audit (`claude-practice-audit-converged-20261012`, P2, stage 1 of the staging that the command center accepted). The practice page's slot for plugin marketplaces
(`.claude/skills/claude-native-practice/reference/instructions-skills.md`, `plugin-marketplaces`) names a catalog-owned marketplace with commit-pinned plugin entries as the default and says the host's current
state is "publisher marketplaces pinned by tag". The audit found the gap: nothing in the repository says, for a plugin a profile template enables, which commit was reviewed, and nothing fails when a template
enables a plugin that has none. This record adds that, without changing a plugin's identity.

## What the vendor supports (primary sources, fetched 2026-10-13)

- A plugin entry of a `marketplace.json` takes `ref` and `sha` for `github`, `url` and `git-subdir` sources; `sha` is "a full 40-character lowercase commit SHA" and is checked out when both are set
  (`code.claude.com/docs/en/plugins/marketplace-reference.md` L143-L145 and L157; `receipts/docs-excerpts.txt`).
- A marketplace source (`extraKnownMarketplaces`, `strictKnownMarketplaces`) takes `repo`, `ref`, `path` and `sparsePaths`, and no `sha` (same page, L351-L352). The practice page's route says the same:
  "marketplace sources take a `ref`, never a `sha`".
- The client supports the pin since the changelog's entry at `anthropics/claude-code@3deb873687379f0c199a69fdaccc65f0865f7a29` `CHANGELOG.md:7353` (and `:5103`, an install whose `ref` is gone but whose `sha` is
  pinned; `:3425`, the `archive` source with a SHA-256).
- The vendor's own marketplace uses it everywhere it points outside itself: `anthropics/claude-plugins-official@f359d43b406057f1a8cdbc4ea93b827642c162e6`, 315 entries, 262 external and all 262 with `sha`
  (53 are relative paths inside the marketplace; `receipts/official-marketplace-pins.txt`).

So the vendor's mechanism for a commit pin is a plugin entry in a marketplace file that the pinner owns. Stage 2 is that file.

## Measurement

On the first host, with the client at 2.1.296 (`receipts/`):

| Plugin | Template | What resolves | Result |
| --- | --- | --- | --- |
| `claude-hud@claude-hud` | `ref: v0.10.0` | `git ls-remote`: the annotated tag's peeled commit is `75683c6de1ac07f6bbef00d739001679dba0740c`, the installed `gitCommitSha` | a tag pin |
| `codex@openai-codex` | `ref: v1.0.6` | the lightweight tag is `db52e28f4d9ded852ab3942cea316258ae4ef346`, the installed `gitCommitSha` | a tag pin |
| `context-mode@context-mode` | no ref | the reviewed commit `6f0cc6841c687e754059f36714a11233fda1a02b` is on no tag: the newest tag of its version, `v1.0.169`, is a commit 133 commits older with different bundled files (`cli.bundle.mjs`, `server.bundle.mjs`, `stats.json`); the host's installed commit is 21 commits ahead of the reviewed one with `stats.json` the only changed file | an exception: held by content, not by commit |
| `cc-plugin-you-should-know@builtin` | the new-WSL additions | a built-in mod of the client, versioned with it | recorded as built in |

## Decision

1. **`adoption/plugins/pins.json` is the record.** One entry for each plugin that a profile template enables (`adoption/templates/claude.settings.template.json` and
   `adoption/new-wsl/templates/claude.settings.additions.json`): the marketplace source as the template writes it, the version, and the pin: `tag` (the template's ref resolves to the reviewed commit), `exception`
   (the template cannot name the reviewed commit; the reason and the content rule are written down) or `builtin`.
2. **`tests/test_plugin_pins.py` is the audit's fail-first test and its guards**: every enabled plugin of the templates has an entry and no entry is stale; each entry is one of the three forms with its reason; the
   record holds the template's own marketplace source key for key; a tag pin is the commit the captured tag resolution lists; an exception is backed by the captured compare; the revision check of
   `adoption/bootstrap.md` step 4a holds the same commits (the record is the one source, the guide's dict must agree); the documented rules the record rests on are in the captured pages.
3. **Nothing about a plugin's identity changes.** The template, the host's registry and every reference to `name@marketplace` stay as they are. Stage 2 moves the reviewed commits into a catalog-owned
   `marketplace.json` whose plugin entries carry `sha`.

## Alternatives

- **The catalog-owned marketplace now** (the slot's route): the plugin id is `name@marketplace`, so a new marketplace name changes the key of every enabled plugin on every host and every reference to it:
  44 tracked files outside `evidence/` name the three ids today (39 for `context-mode@context-mode`, 16 for `claude-hud@claude-hud`, 15 for `codex@openai-codex`), and 70 more files under `evidence/`, besides the
  hosts' registries, caches and hooks. That is a migration with its own measurement and its own rollback, not a scoped hardening; it is stage 2, built on this record.
- **Pin `context-mode` by naming the tag `v1.0.169`** in the template: changes the content (133 commits older, different bundled files) and re-registers the marketplace on every host; it holds a commit the
  catalog did not review.
- **Pin the marketplace source by `sha`:** not a field of a marketplace source (documented above), so the client would ignore or reject it.
- **Managed marketplace allowlists** (`strictKnownMarketplaces`): rejected by the slot for this host, and an allowlist matches sources, never commits.
- **Leave the guide's dict as the only record:** it is prose in a heredoc and nothing fails when a template enables a plugin it does not name.

## What is not covered

- The record is not enforced by the client: Claude Code installs what the marketplace source gives it, and `context-mode` follows the default branch's tip. The record states what was reviewed and the test keeps
  the repository's documents to it; the host check (`adoption/bootstrap.md` step 4a) compares the installed commit with it.
- The host's other marketplaces and plugins (`worktrunk`, `socraticode`, `claude-api`, `diagram-design`, `typesafe`, `equity-research`) are not enabled by a template and are not in the record; the
  skills manifest pins the two that it governs (`claude-api`, `typesafe`) by `ref`. A template that starts to enable one is stopped by the first test until it has an entry.
- Tags are mutable on the publisher's side; the record's commit is what was reviewed, and the tag resolution is a capture of 2026-10-13, not a guarantee. A pin that the client enforces is stage 2.
- The two guards that read `adoption/bootstrap.md` and the receipts are text readers of a guide's code block and of captured files; a reformatting of either fails the test loudly rather than passing.

## Review round 1 (the command center's read of `e9a75c5d`: no P1, one P2 in the diff, one P2 outside it, six P3; one commit with the leased registry-only rebase)

The read is the command center's record `pr1092-claude-read-e9a75c5d.md` (2026-10-13T22:35Z): a read-only evidence reviewer that checked client behaviour against the installed 2.1.296 binary by byte offset and
re-fetched every reproducible receipt (all matched); privacy clean. The ruling: one commit by this lane, in one push with the registry-only rebase onto main; P2-1, P3-2 and P3-3 are fixed here, and the rest
are follow-ups below.

| Finding | Fix | Test (fails before the fix) |
| --- | --- | --- |
| P2-1, `tests/test_plugin_pins.py:28-29`: a plugin counted as enabled only when its value was `true`; the client also enables a list: `function lM(e){return e===!0||Array.isArray(e)}` and `aet`, which builds the enabled set with it (2.1.296, bytes 215984845 and 215984892 of the binary, read here; the schema at 208959019 and 208925317), so a list-enabled plugin with no entry passed all seven tests and `adoption/plugins/README.md` was untrue for that format | `enabled_plugins` mirrors the client: `true` or a list (an empty list included); `false`, a string, a number, `null` and an object enable nothing; the README sentence says so | `test_a_plugin_is_enabled_as_the_client_reads_the_value_true_or_a_list`; the mutants "a template enables a plugin by a list", "... by an empty list" and the same in the additions template survive the pushed head's module and are killed by this one; five controls (false, a string, a number, null, an object) stay green in both |
| P3-2: a `builtin` pin was accepted for any marketplace | a `builtin` entry requires the `builtin` marketplace | the mutant "a built-in entry of another marketplace" (survives the pushed head's module, killed now) |
| P3-3: the tag-resolution parse took the first text that ends with the repository's name, and read to the next blank line although the capture lists its repositories one after another (so the rows of the repository listed next were read too); the sha check used `search`, which accepts a longer text that contains a commit | `tag_commit` reads the rows below the repository's own header line, up to the next header or a blank line; `is_sha` uses `fullmatch` | `test_the_tag_resolution_is_read_under_exactly_the_plugins_repository` and `test_a_sha_is_forty_lowercase_hex_characters_and_nothing_else`; the mutants "the pinned commit stands under a look-alike header" and "... under the repository listed next" survive the pushed head's module and are killed now; the old assertion accepts a 41-character value and the new one does not (in the receipt) |

The receipt is `evidence/artifacts/plugin-pins-20261013/receipts/mutants-round1-29.txt`: each mutant over a scratch copy of the files the tests read, run against the pushed head's module and this one: the six
of the round survive the old module and are killed by the new one; the five controls are green in both; the 17 mutants of the first head are still killed. A mutant of the plugin-side defects needs consistent changes in
several files for the old module to miss it (a 41-character commit changes the record, the capture and the guide together, and the guide's own pattern then catches it), so the predicate is shown directly.

### Follow-ups of the read (none changing code in this round)

- **P2-2, outside the diff and jointly with #1074's identical follow-up**: the registry reader in `adoption/bootstrap.md` (step 4a, the lines that read the plugin registry under `CLAUDE_CONFIG_DIR`) must honour
  `CLAUDE_CODE_PLUGIN_CACHE_DIR` and the cowork mode as the client resolves the plugin folder (bytes 219447724, 211876595 and 211876415 of the 2.1.296 binary). It is the same class as the plugin folder
  resolution in `scripts/skills_status.py`: one installer-side fix for both readers, after both pull requests land.
- P3-1: the record names step 4a as the host check without saying which checks it makes; qualify it at the next edit of that paragraph.
- P3-4: no test reads `receipts/observed-registry.json`; add one when the host check compares the installed commits with it.
- P3-5: the default branch's tip is captured and not compared with the reviewed commit; compare it at the next capture.
- P3-6: one claim is uncited ("no ref installs the default branch's tip"): cite the documentation lines (L156 and L380 of the marketplace reference) and the schema byte 208867701 at the next edit.

## Overturn conditions

- A client release that gives a marketplace source a `sha`: the template can then name the commit directly and the exception for `context-mode` ends.
- The `context-mode` publisher tags the reviewed content or the catalog re-reviews at a tagged commit: the exception becomes a tag pin.
- A pinned commit becoming unreachable (a force-pushed repository): the entry is re-reviewed, as the slot's `overturn_when` says.
