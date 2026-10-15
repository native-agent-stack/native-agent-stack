# Source record: the sandbox's protected-path placeholders and the own-clone rule (2026-10-15)

This is the reviewable record behind the own-clone correction in `docs/decisions/2026-10-09-claude-code-native-practice.md`. It replaces citations to the lane's working files. Locators are pinned to the installed client binary. A binary offset holds only for that exact file, so its sha256 is given.

## Client binary

- Claude Code **2.1.300**, linux-x64, at `~/.local/share/claude/versions/2.1.300`.
- **sha256** `674deba0bba9aee479f4503c438b49303b6fdd304b9a471b14977aaec5215453`. This equals the linux-x64 checksum in the signed 2.1.300 release manifest. The GPG check is retained here: `release-signature-2.1.300.json`, re-run 2026-10-15T11:23:49Z against the manifest, signature and key kept in `release-2.1.300/`. The result was a good signature from key `31DDDE24DDFAB679F42D7BD2BAA929FF1A7ECACE`, and the manifest's linux-x64 checksum and size equal the installed file's.
- Offsets below are byte offsets into that file, re-read 2026-10-15T05:10Z.

| Offset | What it shows (bytes at the offset, abridged) |
| --- | --- |
| 110513208 (start of the `/.git/config.lock` entry; the list begins a few entries earlier) | The sandbox's write-protected path list: `/.git/hooks`, `/.git/config`, `/.git/config.lock`, `/.git/config.worktree`, `/.git/config.worktree.lock`, `/.git/commondir`, `/.git/worktrees`, `/.git/modules`, `/.git/info/exclude`, `/.git/glab-cli`, `/.gitmodules`, `/.github`, `/run/docker.sock` |
| 216332417 | `AM="/mnt/c/Program Files/ClaudeCode"`, the Windows managed-settings directory as WSL sees it |
| 216588603 | The `wslInheritsWindowsSettings` schema text: "When set to true in either admin-only Windows source — the HKLM SOFTWARE/Policies/ClaudeCode registry key or C:/Program Files/ClaudeCode/managed-settings.json — WSL reads managed settings from the full Windows policy chain …" |

## The mechanism, and what is inference

1. **Protected paths (binary, above).** Inside a sandboxed Bash, writes to these paths are denied.
2. **Placeholder files (inference from bubblewrap's documented binds).** To deny writes to a path that does not exist yet, the sandbox binds an empty read-only file over it, which leaves a 0-byte, mode-0444 file on the real filesystem. Two such files were observed on this host:
   - `~/code/native-agent-stack/.git/config.lock`, born 2026-10-14T23:59:29Z;
   - the Windows `managed-settings.json` and `managed-settings.d` (a file) under `C:\Program Files\ClaudeCode`.

   The bubblewrap command lines that made them were not captured, so the link from bind to file is an inference.
3. **Shared `.git` (git's own model).** A worktree's common dir is the main repository's `.git`. So a sandboxed session whose cwd is any worktree of the shared repository places `.git/config.lock` in the shared `.git`. While the file exists, every lane's `git config` writes fail, `git worktree add -b` among them ("could not lock config file", observed 2026-10-15T00:50Z). Hence the rule: **a sandboxed lane works in its own clone.**

## Measurements

**`probe.sh`** (this directory; the lane's copy) ran 2026-10-15T01:06:39Z–01:07:00Z. Each arm was one headless turn on claude-haiku-5-5 at low effort, from its own scratch cwd, with `--tools Bash --permission-mode dontAsk`.

| Arm | `--settings` | File written outside the cwd | PID 1 |
| --- | --- | --- | --- |
| on | `{"sandbox":{"enabled":true}}` | no (bwrap failed at the `/proc` environ bind under this host's read-deny settings) | none: the command never ran |
| off | `{"sandbox":{"enabled":false}}` | yes | `/sbin/init` |
| unset | none | yes | `/sbin/init` |

**Env-scrub probe** (2026-10-15T01:11:04Z, one headless turn with `CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1` and `--settings '{"sandbox":{"enabled":false}}'`):
- the write outside the cwd succeeded;
- `NSpid: 6`, `Seccomp: 2`, and PID 1 was `bwrap --new-session --die-with-parent …`;
- stderr: "Permission mode forced to default — CLAUDE_CODE_SUBPROCESS_ENV_SCRUB is set".

This is the scrub's own subprocess sandbox, independent of `sandbox.enabled`. Session ids are not recorded here.

## Upstream sources

- **anthropics/claude-code `CHANGELOG.md` at `94506ff0d3bd9185f1752da36e968775021fb48f`:**
  - 2.1.98: "Added subprocess sandboxing with PID namespace isolation on Linux when `CLAUDE_CODE_SUBPROCESS_ENV_SCRUB` is set";
  - 2.1.299: the fix for `bwrap: Can't mkdir /mnt/c/Program Files/ClaudeCode` on WSL2.
- **https://code.claude.com/docs/en/managed-settings** (managed-settings.md, sha256 `6bfb4f806ac254c5562baa28422c7c329ebc57353d95b9106e2a354390e5443c`, read 2026-10-15):
  - "An empty managed settings file counts as `{}`."
  - A `managed-settings.d` that exists but cannot be read makes every session exit at startup.
- **https://code.claude.com/docs/en/settings-reference:** `sandbox.enabled` defaults to `false`. The precedence is managed > `--settings` > local > project > user.
