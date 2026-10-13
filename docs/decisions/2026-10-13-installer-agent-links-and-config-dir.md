# The installer replaces a link at a shipped agent name with a copy and follows CLAUDE_CONFIG_DIR for the current user's own install, 2026-10-13

Status: decided 2026-10-13. Follow-up of [the agent drift check](2026-10-13-claude-agent-drift-check.md), whose "Not covered" section named the installer as not yet the recovery for every drift it counts.
Scope: the agents step of `tools/adoption/install_claude_profile.py` (`install_agents`). The other steps are unchanged (see "What is not covered").

## The gap

The drift check (`scripts/adoption_status.py`) counts a link at a shipped name and reads the Claude home from `CLAUDE_CONFIG_DIR` when it is set. The installer did neither:

| Case | Before | Effect |
| --- | --- | --- |
| a link at a shipped name whose target holds the shipped bytes | `dest.is_file()` follows the link, the bytes are equal: skipped | the drift check keeps counting the link, and the installer can never clear it |
| a link at a shipped name whose target holds other bytes | `shutil.copy2` opens the destination for writing through the link (`python/cpython@cbc944f4bc59` `Lib/shutil.py` L262, `open(dst, 'wb')`) | a file outside the folder is overwritten |
| a link to nothing | the same open creates the file where the link points | a file is created outside the folder |
| a folder at a shipped name | `copy2(src, dest)` copies *into* the folder | `agents/<name>.md/<name>.md`, a nested definition the client then loads |
| `CLAUDE_CONFIG_DIR` set | always `<home>/.claude/agents` | definitions installed where the client does not read them (below) |

## Measurement (Claude Code 2.1.296, zero model spend)

The installed client was started headless in a scratch home with a synthetic key and a loopback base URL nothing listens on, and killed at its system init record, which lists the definitions it loaded
(`evidence/artifacts/installer-agent-links-20261013/receipts/client-agents-probe.json`; names and counts only):

| Arm | Definitions placed | Listed by the client |
| --- | --- | --- |
| A, no `CLAUDE_CONFIG_DIR` | `<home>/.claude/agents/zz-home.md` | `zz-home` |
| B, `CLAUDE_CONFIG_DIR=<home>/cfg` | `<home>/cfg/agents/zz-cfg.md` and `<home>/.claude/agents/zz-home.md` | `zz-cfg` only: the home's own folder is not read |
| C, a link to a file outside the folder | `agents/zz-linked.md` -> `outside/zz-target.md` | `zz-target` (the front matter name; the link is followed) |
| D, a link to nothing | `agents/zz-dangling.md` -> a missing file | none (not loaded) |
| E, `CLAUDE_CONFIG_DIR=""` | `<home>/.claude/agents/zz-home.md`, `<cwd>/agents/zz-cwd.md` | `zz-cwd`: an empty value is read as the client's working directory |
| F, `CLAUDE_CONFIG_DIR=cfgrel` (relative) | `<cwd>/cfgrel/agents/zz-rel.md`, the other two as in E | `zz-rel`: resolved against the working directory |

The documentation says that the variable overrides "the configuration directory (default: `~/.claude`)" and that "all settings, session history, and plugins are stored under this path"
(`code.claude.com/docs/en/env-vars.md` L430), and that user definitions are `~/.claude/agents/`, scanned recursively (`sub-agents.md` L176-L178; `receipts/docs-excerpts.txt`). It does not say that the definitions
move with the variable; arm B is the evidence that they do.

## Decision

1. **A link at a shipped name is replaced by a regular copy, never written through.** The copy is written beside it (`.<name>.<pid>.tmp`) and renamed over it (`os.replace`: the rename replaces the directory entry,
   a link included, and is atomic on POSIX, `Doc/library/os.rst` L2754-L2760 at the same CPython commit), so there is no window in which a link has been removed and the file is not yet there, and the target of the link (a
   file, nothing, a folder) is not touched. The equality test no longer follows a link. A dry run says that it would replace the link.
2. **A folder at a shipped name is refused before anything is copied** (`InstallError`, "preserved"), so a run does not leave half of the definitions installed or nest one inside the folder. A link to a folder is a link
   (decision 1).
3. **The current user's own install follows `CLAUDE_CONFIG_DIR`.** Without `--home`, a set, absolute value names the folder (made absolute and NFC-normalized as the client reads it; the same reading as
   `scripts/skills_status.py` `claude_settings_path`); an empty value is read as unset, as the drift check reads it (the client reads it as its own working directory, which no installer run can match); a relative value is
   refused with a message that names the variable (the client resolves it against its working directory, which differs per session). With `--home`, the target is that home's own `.claude`, whatever the environment names: the
   new-WSL tool passes `--home` and strips the variable, and an environment that names another account's folder must not redirect an explicit install. A relative value does not stop a run that does not install agents.

## Alternatives

- **Refuse a link, as the workflows step does.** Rejected for the agents step: the shipped definitions are catalog-owned copies ("agent copies are always refreshed", the installer's docstring), the drift check counts a
  link as drift, and refusing would leave the installer unable to clear what the check reports. The replaced link's target is untouched, and re-linking is the user's one command; `--dry-run` names each link it would replace.
- **Remove the link, then copy** (the first wording of the follow-up). The same end state with a window between the two calls; the rename has none.
- **Follow `CLAUDE_CONFIG_DIR` also with `--home`.** Rejected (decision 3).
- **Read an empty or relative value as the client does** (the working directory). Rejected: the installer's working directory is not the client's, so the install would land in a folder chosen by where the command was run.
- **Ship the definitions as a plugin.** A different install path and a different priority (plugin definitions rank below user definitions, `sub-agents.md` L158-L168); not this change.

## What is not covered

- **The other steps.** The guard hooks are installed by absolute path and registered in the settings by absolute command, so their folder is part of the settings template's contract and does not move with the variable. The
  routing skill (`<home>/.claude/skills/...`) and the workflows (`<home>/.claude/workflows/`) are found by folder and may have the same gap; each needs its own measurement of where the client looks (the skills CLI 1.7.0 links under
  it, `dist/cli.mjs` L1398, as `scripts/skills_status.py` `claude_skills_dir` reads it). A follow-up.
- **An `agents` folder that is itself a link** (a dotfiles layout): the copies are written into what it points at, as before; the drift check reports such a folder as unknown.
- **Non-POSIX hosts.** `os.replace` over an existing entry is atomic on POSIX; this installer's targets are Linux and macOS.
- **A concurrent writer** that creates a link at a shipped name between the check and the rename is replaced like any link; nothing is written through it.

## Evidence

| Claim | Class | Receipt |
| --- | --- | --- |
| with `CLAUDE_CONFIG_DIR` set the client lists the definitions under its `agents/` and none under the home's own; an empty value is its working directory; a relative one is resolved against it; a link to a file is followed by its front matter name; a link to nothing is not loaded | native_proven (client 2.1.296, one host) | `receipts/client-agents-probe.json` |
| the documentation's statements the record cites | source_review | `receipts/docs-excerpts.txt` |
| a link (equal bytes, other bytes, to nothing, to a folder) is replaced and its target untouched; a folder is refused before any copy; the dry run names the link; no temporary file is left; the variable is followed for the current user, ignored with `--home`, empty is unset, relative is refused, a set value is normalized | local_integration | `tests/test_install_claude_profile.py` (`AgentsInstallTests`, `AgentsConfigDirTests`); `receipts/fail-before.txt` (9 tests fail or raise on the base) |
| the tests kill the mutants of the change | synthetic | `receipts/mutants-installer.txt` (15 of 15 killed; the first run killed 14) |

## Overturn conditions

- A client release that stops reading `<CLAUDE_CONFIG_DIR>/agents`, or that reads both folders: the destination changes (re-run the probe of the receipts).
- A catalog policy that allows a user-linked definition at a shipped name: the replacement of a link becomes a refusal, with the drift check's counting changed in the same step.
- A client release that reads an empty `CLAUDE_CONFIG_DIR` as unset: the installer's reading and the client's agree and the decision's reason for the empty value goes away.
