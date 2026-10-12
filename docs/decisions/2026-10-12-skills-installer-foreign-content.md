# The skills installer does not delete content it did not write, 2026-10-12

Status: decided by the command center's ruling on #1024 (2026-10-12, 04:06Z and 04:41Z), built here as research-queue row 42 (F3), whose trigger "#1024 LANDED" fired at 06:55:24Z.

## Context

`tools/adoption/install_skills.py` runs the pinned Skills CLI (vercel-labs/skills@7407f3893ad4dceab546ac002c3ef806e4000c73) and never writes a skill folder itself. The CLI's add recreates the canonical folder from nothing (`src/installer.ts` L193-200 `cleanAndCreateDirectory`, L389-390 the write and the copy), so everything in the old folder is gone afterwards. Until #1024 the installer judged an existing folder by its `SKILL.md` alone; #1024 added the Claude Code link and the canonical-leaf link to what it protects and named this gap as not covered.

Measured with the real pinned CLI on 2026-10-12 (manifest row `gh-fix-ci`, a scratch home): after a clean install, an added `local-work.txt` in the unlocked canonical folder was deleted by the installer's run at main `83cec12ee` (`installed`, exit 0, the folder back to its 6 pinned files), and survived the run of this change (`local-modified`, exit 1, 7 files).

## Decision

1. **The folder must be what the CLI writes before an add runs over it.** Where an add is about to run over an existing canonical (or, for a Claude-Code-only copy, Claude) folder whose `SKILL.md` is the pinned one — an unlocked folder, or a folder locked at the pin whose Claude link is missing — the folder holds that `SKILL.md` alone, or its git tree SHA, with the runtime-artifact directories left out, equals the manifest's `tree_sha`. Otherwise it is `local-modified`: refused unless `--force`. The same rule covers a project's canonical folder.
2. **The comparison is the repository's own.** `scripts/skills_status.py` already hashes an installed folder the way git hashes a tree (`git_tree_sha`) and names the directories a skill's own tooling regenerates (`RUNTIME_ARTIFACT_DIRS`: `__pycache__`, `.venv`, `node_modules`, tool caches), and reports the comparison as `folder_tree`. The installer imports that predicate; it adds no second implementation and no network call.
3. **The canonical-leaf link rule stays literal.** The first version of the rule left open whether to refuse only a link that leads to the Claude entry. It does not narrow: a link the installer did not make is content it did not write, the CLI writes a real folder at that path, and none of the 32 entries of the host's canonical skills folder is a link. `scripts/skills_status.py` now enforces the same rule (`canonical_link`) and accepts the one layout a link on a parent folder makes, as `createSymlink` does (`src/installer.ts` L240-250), so the two required checks agree on both layouts that differed.
4. **Text items of the reads of #1024** (P3-2 the `--force` help, P3-3 the Codex-only scope of the link rule, P3-5 a missing space in a test) are fixed in the same change.

## Measurement behind decision 2

Research row 42 asked whether the installer can prove which files of a canonical folder it wrote. On this host all 28 managed rows (`tools/adoption/install_skills.py --check-only` ok) have a folder whose git tree SHA equals the manifest's `tree_sha`: 25 exactly, 3 (`gh-address-comments`, `supply-chain-risk-auditor`, `skill-creator`) once `__pycache__` is left out (`scripts/skills_status.py --json`, `folder_trees`). The pinned vendor listing minus the CLI's copy exclusions (`src/installer.ts` L458-466) predicts the same sets file for file (checked for blob SHA-1 as well, all 28 rows), so the manifest's `tree_sha` is enough and the GitHub trees API is not needed.

## Alternatives

- **Compare against the pinned tree listing fetched from GitHub** (the oracle the project path already uses): rejected; it puts the network into `--check-only` for a global entry, and the manifest already carries the answer.
- **Add a per-file listing to the manifest:** rejected; it duplicates `tree_sha` and could drift from it.
- **Write a marker file into the installed folder:** rejected; the installer never writes a skill folder.
- **Refuse every unlocked folder:** rejected; adopting an identical hand-installed folder is a documented case ((b) of the installer), and a lost lock should not cost a `--force`.
- **Narrow the canonical-link rule:** not taken (decision 3).

## What is not covered

- An upgrade over a lock of an older tree: the older version's files cannot be named offline, and the lock proves the CLI wrote some earlier version there. The add runs as before.
- A folder that is locked at the pin, linked and `ok`: no add runs, so nothing is deleted, and the folder is not judged here (`scripts/skills_status.py` reports drift).
- A pinned vendor folder that itself contains a file the CLI leaves out of a copy (`metadata.json`, `.git`, `__pypackages__`, `src/installer.ts` L458-466): its installed tree would differ from `tree_sha` and the folder would count as local content. No managed row has one today; the status check would report the same folder as `drift`.

## Overturn conditions

- A managed row whose installed folder legitimately differs from `tree_sha` (a vendor folder with CLI-excluded files): give that row an explicit expected tree, or exclude the names, in this change's predicate.
- A host layout that needs a canonical link (dotfiles-managed skills): rule on it with that host's evidence.
- The pinned CLI stops recreating the canonical folder from nothing in a later version: the protection is then stricter than the mechanism and is reviewed at the next pin.
