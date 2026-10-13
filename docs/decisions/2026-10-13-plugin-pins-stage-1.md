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

## Overturn conditions

- A client release that gives a marketplace source a `sha`: the template can then name the commit directly and the exception for `context-mode` ends.
- The `context-mode` publisher tags the reviewed content or the catalog re-reviews at a tagged commit: the exception becomes a tag pin.
- A pinned commit becoming unreachable (a force-pushed repository): the entry is re-reviewed, as the slot's `overturn_when` says.
