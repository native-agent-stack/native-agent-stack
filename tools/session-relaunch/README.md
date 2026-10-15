# Session relaunch after an unplanned WSL restart

`session_relaunch.py` brings the core Claude Code sessions back after the distro stops without a handoff, as on
2026-10-14 when WSL went down at 06:41:17Z and every session stayed down after the distro started again at 12:48:57Z.
It has two parts, both systemd `--user` units, the layer's recorded supervisor (`catalogs/landscape/foundation.json`,
`scheduling-supervision` winners: Dagu and the systemd user manager):

- `ns-session-roster.timer` runs `snapshot` every minute. It writes the live sessions that `claude agents --json`
  lists to `rosters/roster-<boot id>.json` in the state directory. That flag is the client's scripting interface
  ("Print active sessions (interactive and background) as a JSON array and exit (for scripting; does not require a
  TTY)", `claude agents --help` at 2.1.299). One call took 0.18-0.23 s here. When the client gives no list (an
  error, a timeout or output that is not a JSON array), the last good roster stays as it was and `snapshot` exits 1; an
  empty array is a valid, empty roster.
- `ns-session-relaunch.service` runs `relaunch` once at boot. It reads the newest roster from an earlier boot. If that
  boot did not end in a planned restart, it writes one handoff, `AUTO-RESTART-<UTC>.md` (mode 0400), in the
  command center's directory. Then it opens a fresh tab for each session that has a launcher profile, command center
  first, through the command center's own tab opener (`open-tab.ps1`, which starts `launch.sh`). A background session
  that has a profile is restarted with the client's `claude respawn <id>` instead (Background sessions, below).
  Sessions without a profile, and sessions already running, are listed in the handoff for the command center.

The tool makes no model call. Each relaunched interactive session is a new Claude session (new session id) that reads
the handoff, the same fresh-from-handoff practice as the command center's launcher (`launch.sh`); it does not resume
the old transcript. A respawned background session resumes its own saved conversation.

## Why not a native feature

Background sessions (agent view, `claude --bg`) do not restart by themselves after a shutdown. At 2.1.299, and again
at 2.1.301 (the same docs bytes, read 2026-10-15T20:05:17Z; `evidence/artifacts/session-relaunch-install-20261015/receipts/sources.json`):

- "Shutting down or restarting your machine stops running background sessions"; within 48 hours a session "shows as
  failed. Attach or reply to it and it restarts from its saved conversation" (agent-view docs, lines 884-886 of the
  copy read 2026-10-14T12:58:26Z, sha256 `c8e2b810…`).
- The docs' Limitations section says sessions "stop if the machine shuts down" (line 982).
- `claude daemon --help` says "Service install is disabled in this version — the daemon runs on demand and exits when
  the last client disconnects" (line 12, at 2.1.299 and at 2.1.301).
- The supervisor restarts a session that exits unexpectedly only while the supervisor itself runs (line 823), and it
  starts on demand (line 817). Nothing upstream brings sessions back after a boot.

Windows Terminal's `persistedWindowLayout` was rejected earlier because it starts a fresh process from each tab's saved
command line and reattaches nothing (`docs/decisions/2026-09-28-terminal-experience.md`, line 616).

The session files under `~/.claude/sessions/` cannot serve as the roster. None of the seven sessions alive at
06:41:17Z had a file there from the boot that ended. The one file for `0d2e4ed6` belongs to the process that resumed it
in the new boot. The files' `pidDomain` also holds the machine id, not the boot id. The
measurements are in `evidence/artifacts/session-relaunch-20261014/`.

## Decision rules (`plan()`)

`relaunch` does nothing, and says why, when any of these holds:

- the client gives no session list within `client_wait_s` (120 s): who is running is unknown, so nothing is written
  or opened and `relaunch` exits 1;
- no roster from an earlier boot exists;
- a `planned-<boot>.json` marker exists for the boot that ended;
- that boot's relaunch is complete (`relaunch-<boot>.json` with status `complete`);
- that boot's `relaunch-<boot>.json` cannot be read: a refusal, exit 1;
- the journal has no entry for that boot (`journalctl --list-boots -o json` failed or no longer lists it), so the
  roster's age at the boot's end cannot be checked: a refusal, exit 1;
- the roster was written more than `max_roster_age_s` (300 s) before that boot's last journal entry;
- `max_relaunches` (3) relaunch runs already started within `relaunch_window_s` (6 h), which caps a crash loop; a rerun
  of an unfinished relaunch counts as a run.

Otherwise it relaunches every `interactive` roster session whose name has a profile and is not running now, once per
name: a second roster row of the same name is left to the command center in the handoff. A `background` row whose name
has a profile is respawned instead (Background sessions). The handoff gives each row it leaves its reason: already
running, a second row of a name relaunched above, no launcher profile, or a kind the tool does not relaunch.

## Background sessions

The client's scripted restart of a background session is `claude respawn <id>`: "Restart a session, running or stopped
... A session that has a saved conversation resumes it" (agent-view docs, line 766, read 2026-10-15T20:05:17Z, sha256
`c8e2b810…`; `claude respawn --help` at 2.1.301). After the tabs, `relaunch` reads `claude agents --json --all` and
respawns a profiled background row only when that read still lists it, it has no process (a respawn restarts a working
session), and its saved transcript exists under the projects directory. Each call is recorded in flight in
`relaunch-<boot>.json` under `background`; a rerun respawns a row again only while it still has no process. A row with
no saved transcript, no short id or no listing is left to the command center with `claude attach <id>`.

Measured 2026-10-15 at 2.1.301 (`evidence/artifacts/session-relaunch-install-20261015/receipts/respawn-probe.json`):
a stopped row with a saved transcript came back on the same session id with its conversation, from a non-interactive
shell, and its process stayed up. A failed row with no saved transcript was respawned too, but its dispatch prompt was
sent again and its command ran again, although the 2.1.290 CHANGELOG says such a row starts with an empty conversation
(anthropics/claude-code@03b5892e `CHANGELOG.md` L794). That is one observation on an unusual row and an untested
boundary, which is why the transcript gate exists. A failed row with a saved transcript after a real shutdown is
untested until the first real boot.

## Relaunch state and reruns

`relaunch-<ended boot>.json` in the state directory records the relaunch of one ended boot: the sealed handoff and its
sha256, each run (`boot`, `started_at`, `ended_at`), and each session's tab calls and outcome:

| outcome | meaning |
|---|---|
| `pending` | not tried yet in this run |
| `running` | listed by `claude agents --json` |
| `failed` | every call failed definitely (a nonzero rc, or the opener could not start) |
| `skipped` | the live list could not be read before a call, so no call was made |
| `uncertain` | a call timed out after `tab_timeout_s` (120 s), or the run stopped inside a call, and the session was not listed |
| `unconfirmed` | the opener returned rc 0 but the session was not listed within the settle wait |
| `absent` | listed earlier in this run but missing from its final live list: it registered, then exited |

The status is `in_progress` from the run's start, then `complete` when the live list read at the run's end lists
every session, else `partial` (also when that last read fails). The
live list is read before every tab call, and a call is made only when that read lists the session as absent. Each
call is recorded in the state file (`in_flight`) before it is made. Its result is saved together with the provisional
outcome (`unconfirmed` after rc 0, `uncertain` after a timeout) before the settle wait, so a run stopped while it waits
leaves the session unresolved. A definite failure is retried up to `tab_attempts` calls; an opened or timed-out call is
never repeated, because a tab may already be open: the run waits for the session (`cc_wait_s` for the command center,
`settle_s`, 60 s, for the rest) and records the outcome.

A rerun of an `in_progress` or `partial` relaunch reuses its sealed handoff (refused when the file is missing or its
sha256 differs). It opens again only the sessions that are not running and whose earlier calls cannot have started a
tab (`pending`, `failed`, `skipped`, and `absent`, whose tab start registered before it exited). A session with a
call since its last reopen that opened, timed out or is still
`in_flight` is unresolved and stays as it is (`unconfirmed` or `uncertain`), because its first `claude -n` may still
register. The next boot reruns the relaunch by
itself when no roster of this boot exists; within this boot the command center reruns it with
`systemctl --user start ns-session-relaunch.service`. Only the command center reopens an unresolved session, once it
has checked that no tab of it is open:
`/usr/bin/python3 -I "$T/session_relaunch.py" relaunch --reopen <name> --config "$S/config.json"` (repeat `--reopen`
for more names; the run records them under `reopened`). A reopen is spent only by the call it makes
(`resolved_through` in the session's record), so a reopen run that skips the session or stops before its call leaves it
unresolved. A `--reopen` that cannot be carried out is refused, exit 1, and nothing is opened: a name that is not an
unresolved session this relaunch still has to bring back, or any `--reopen` while the relaunch is complete, capped by
`max_relaunches` or otherwise has nothing to relaunch. The refusal is recorded as a `refusals` entry in that boot's
relaunch state file, under the run lock, with no run added. With no readable relaunch state for the boot (none was
started, or the file cannot be read) there is nothing to add the entry to, and the refusal goes to stderr only. A dry
run records nothing.

Every relaunch run, the unit's or a direct one, holds an exclusive lock on `relaunch.lock` in the state directory
(`fcntl.flock`). A run that finds it held is refused with exit 1 and writes and opens nothing, so a direct `--reopen` run
never overlaps the unit's run.

At its start a run writes this boot's roster as the live sessions plus the ended boot's rows not running yet, and the
minute snapshot keeps carrying those rows while the run is `in_progress`. A second crash before the timer's first
snapshot (90 s after boot) therefore still leaves every session to the next boot.

The service's `TimeoutStartSec=900` bounds one run. A run stopped by it stays `in_progress` and is rerun as above; a
call it stopped is left `in_flight`, so the rerun records that session as `uncertain` and does not open it.

A refused, skipped or `partial` run exits 1, the unit fails, and `OnFailure=stack-alert@%n.service` runs the command
center's alert handler.

## Private files

The state directory and `rosters/` are mode 0700 (set on every write, so a directory made by `install -D` is narrowed
too). Rosters, the relaunch state and the planned-restart marker are 0600; the handoff is 0400. The handoff directory
is made 0700 only when the tool creates it; the command center's existing directory keeps its mode.

## Install (the command center's act, or the host install stage's; nothing here is applied)

`install.sh` is the forward install and `uninstall.sh` its automated inverse. Both port #1116's applied host install
v6 (2026-10-15, install_id `ba61c343` on NativeStack2604) and its manual inverse, with their gates unchanged:

```bash
tools/session-relaunch/install.sh --config <this host's config.json>   # default: config.example.json at HEAD
tools/session-relaunch/uninstall.sh                                    # from a checkout that holds the recorded commit
```

- **Sources:** the tool's committed bytes at HEAD of this checkout, read into a private staging directory; a tool
  directory that differs from HEAD stops the install. The host's config is passed with `--config`; its `state_dir` must
  be `~/.local/state/native-agent-stack/session-relaunch`, the path the units read.
- **Gates, before any write:** no target exists (a dangling symlink included); every directory written under is a real
  path; the alert handler loads (`systemctl --user show stack-alert@ns-session-relaunch.service.service
  --property=LoadState` reads `loaded`, so a new host installs its alert template first); the handoff and unit
  directories exist.
- **Install manifest:** sealed before the first write in `~/.local/state/native-agent-stack/session-relaunch-install/install-state/`,
  with a random install id, the source commit, the handoff directory, each directory it creates, each file with its mode
  and sha256, and the handoff files present then. The receipt beside it binds the manifest's full sha256.
- **Inverse:** `uninstall.sh` refuses unless the receipt and manifest are bound, no consumed receipt exists for the
  install, the file records equal the recorded commit's bytes (and the manifest's config record), the directory records
  are exact, and every path it may touch is a real path; a unit command touches only a unit file with the manifest's
  sha256. It records evidence first, stops at the first failed manager call, removes files only with their manifest
  sha256 and directories only when empty, and on a clean result consumes the receipt (`apply-receipt.txt.consumed-<id>`,
  0400). Anything left over reads "reconciliation pending", and the receipt stays live.

With `T=~/.local/share/native-agent-stack/session-relaunch` and `S=~/.local/state/native-agent-stack/session-relaunch`,
check after two minutes: `ls "$S/rosters"` shows `roster-<this boot>.json`. Then
`/usr/bin/python3 -I "$T/session_relaunch.py" relaunch --dry-run --config "$S/config.json"` prints
`nothing to relaunch: no roster from an earlier boot`.

Inverse: `tools/session-relaunch/uninstall.sh` (above). Runtime files the tool wrote (rosters, relaunch state, handoffs)
are not removed; the inverse copies the state directory into its evidence first.

## A planned restart

Before a restart that has its own relaunch path (the command center's hands-free restart opens its own tabs), run
`/usr/bin/python3 -I "$T/session_relaunch.py" plan-restart --config "$S/config.json"`. The next boot then relaunches nothing from this boot's
roster.

## Not covered

- **Starting the distro.** A linger unit runs only once the distro is running. After a WSL service restart, nothing
  starts the distro until something calls `wsl.exe` (2026-10-14: down 06:41:17Z-12:48:57Z). A Windows-side start task
  is the host lane's part.
- **A boot-time tab.** Measured inside a running boot only: a transient `systemd --user` unit ran `powershell.exe` in
  Windows session 1 and opened a tab that started a process back in the distro. No boot-time run has been measured.
  The relaunch retries a definite failure (`tab_attempts`) and records each call in `relaunch-<boot>.json`.
- **Codex lanes and transient units.** These are re-armed by their owning sessions from the handoff, not by this tool.

## Tests

`python3 -m unittest tests.test_session_relaunch`, which uses stand-ins for the client and PowerShell, and
`python3 -m unittest tests.test_session_relaunch_install`, which runs `install.sh` and `uninstall.sh` in scratch HOMEs
against a stateful `systemctl` stand-in with the fixtures of the v6 simulation.
