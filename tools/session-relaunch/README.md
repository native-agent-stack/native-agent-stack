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
  first, through the command center's own tab opener (`open-tab.ps1`, which starts `launch.sh`). Sessions without a
  profile, and sessions already running, are listed in the handoff for the command center.

The tool makes no model call. Each relaunched session is a new Claude session (new session id) that reads the handoff,
the same fresh-from-handoff practice as the command center's launcher (`launch.sh`). It does not resume the old
transcript.

## Why not a native feature

Background sessions (agent view, `claude --bg`) do not restart by themselves after a shutdown. At 2.1.299:

- "Shutting down or restarting your machine stops running background sessions"; within 48 hours a session "shows as
  failed. Attach or reply to it and it restarts from its saved conversation" (agent-view docs, lines 884-886 of the
  copy read 2026-10-14T12:58:26Z, sha256 `c8e2b810…`).
- The docs' Limitations section says sessions "stop if the machine shuts down" (line 982).
- `claude daemon --help` says "Service install is disabled in this version — the daemon runs on demand and exits when
  the last client disconnects".

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
name: a second roster row of the same name is left to the command center in the handoff.

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

The status is `in_progress` from the run's start, then `complete` when every session is listed, else `partial`. The
live list is read before every tab call, and a call is made only when that read lists the session as absent. Each
call is recorded in the state file (`in_flight`) before it is made. Its result is saved together with the provisional
outcome (`unconfirmed` after rc 0, `uncertain` after a timeout) before the settle wait, so a run stopped while it waits
leaves the session unresolved. A definite failure is retried up to `tab_attempts` calls; an opened or timed-out call is
never repeated, because a tab may already be open: the run waits for the session (`cc_wait_s` for the command center,
`settle_s`, 60 s, for the rest) and records the outcome.

A rerun of an `in_progress` or `partial` relaunch reuses its sealed handoff (refused when the file is missing or its
sha256 differs). It opens again only the sessions that are not running and whose earlier calls cannot have started a
tab (`pending`, `failed`, `skipped`). A session with a call since its last reopen that opened, timed out or is still
`in_flight` is unresolved and stays as it is (`unconfirmed` or `uncertain`), because its first `claude -n` may still
register. The next boot reruns the relaunch by
itself when no roster of this boot exists; within this boot the command center reruns it with
`systemctl --user start ns-session-relaunch.service`. Only the command center reopens an unresolved session, once it
has checked that no tab of it is open:
`/usr/bin/python3 -I "$T/session_relaunch.py" relaunch --reopen <name> --config "$S/config.json"` (repeat `--reopen`
for more names; the run records them under `reopened`). A reopen is spent only by the call it makes
(`resolved_through` in the session's record), so a reopen run that skips the session or stops before its call leaves it
unresolved. A `--reopen` name that is not an unresolved session this relaunch still has to bring back is refused, exit 1,
with a `refusals` entry in the state file, and nothing is opened.

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

## Install (the command center's act; nothing here is applied)

```bash
T=~/.local/share/native-agent-stack/session-relaunch; S=~/.local/state/native-agent-stack/session-relaunch
install -D -m 0644 tools/session-relaunch/session_relaunch.py "$T/session_relaunch.py"
install -D -m 0600 tools/session-relaunch/config.example.json "$S/config.json"   # then check every path in it
install -m 0644 tools/session-relaunch/units/ns-session-roster.service tools/session-relaunch/units/ns-session-roster.timer \
  tools/session-relaunch/units/ns-session-relaunch.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user show stack-alert@ns-session-relaunch.service.service --property=LoadState   # the alert handler: loaded
systemctl --user enable --now ns-session-roster.timer
systemctl --user enable ns-session-relaunch.service    # runs at the next boot; start it by hand only for a rerun
```

Check after two minutes: `ls "$S/rosters"` shows `roster-<this boot>.json`. Then
`/usr/bin/python3 -I "$T/session_relaunch.py" relaunch --dry-run --config "$S/config.json"` prints
`nothing to relaunch: no roster from an earlier boot`.

Inverse: `systemctl --user disable --now ns-session-roster.timer && systemctl --user disable ns-session-relaunch.service`,
then remove the three unit files, run `systemctl --user daemon-reload`, and remove `$T` and `$S`.

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

`python3 -m unittest tests.test_session_relaunch`, which uses stand-ins for the client and PowerShell.
