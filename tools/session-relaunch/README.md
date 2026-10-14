# Session relaunch after an unplanned WSL restart

`session_relaunch.py` brings the core Claude Code sessions back after the distro stops without a handoff, as on
2026-10-14 when WSL went down at 06:41:17Z and every session stayed down after the distro started again at 12:48:57Z.
It has two parts, both systemd `--user` units, the layer's recorded supervisor (`catalogs/landscape/foundation.json`,
`scheduling-supervision` winners: Dagu and the systemd user manager):

- `ns-session-roster.timer` runs `snapshot` every minute. It writes the live sessions that `claude agents --json`
  lists to `rosters/roster-<boot id>.json` in the state directory. That flag is the client's scripting interface
  ("Print active sessions (interactive and background) as a JSON array and exit (for scripting; does not require a
  TTY)", `claude agents --help` at 2.1.299). One call took 0.18-0.23 s here.
- `ns-session-relaunch.service` runs `relaunch` once at boot. It reads the newest roster from an earlier boot. If that
  boot did not end in a planned restart, it writes one handoff, `AUTO-RESTART-<UTC>.md` (mode 0444), in the
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

- no roster from an earlier boot exists;
- a `planned-<boot>.json` marker exists for the boot that ended;
- that boot was already relaunched (`relaunched-<boot>.json`);
- the roster was written more than `max_roster_age_s` (300 s) before that boot's last journal entry
  (`journalctl --list-boots -o json`);
- `max_relaunches` (3) relaunches already happened within `relaunch_window_s` (6 h), which caps a crash loop.

Otherwise it relaunches every `interactive` roster session whose name has a profile and is not running now.

## Install (the command center's act; nothing here is applied)

```bash
T=~/.local/share/native-agent-stack/session-relaunch; S=~/.local/state/native-agent-stack/session-relaunch
install -D -m 0644 tools/session-relaunch/session_relaunch.py "$T/session_relaunch.py"
install -D -m 0600 tools/session-relaunch/config.example.json "$S/config.json"   # then check every path in it
install -m 0644 tools/session-relaunch/units/ns-session-roster.service tools/session-relaunch/units/ns-session-roster.timer \
  tools/session-relaunch/units/ns-session-relaunch.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now ns-session-roster.timer
systemctl --user enable ns-session-relaunch.service    # runs at the next boot; never start it by hand
```

Check after two minutes: `ls "$S/rosters"` shows `roster-<this boot>.json`. Then
`/usr/bin/python3 -I "$T/session_relaunch.py" relaunch --dry-run --config "$S/config.json"` prints
`nothing to relaunch: no roster from an earlier boot`.

Inverse: `systemctl --user disable --now ns-session-roster.timer && systemctl --user disable ns-session-relaunch.service`,
then remove the three unit files, run `systemctl --user daemon-reload`, and remove `$T` and `$S`.

## A planned restart

Before a restart that has its own relaunch path (the command center's hands-free restart opens its own tabs), run
`session_relaunch.py plan-restart --config "$S/config.json"`. The next boot then relaunches nothing from this boot's
roster.

## Not covered

- **Starting the distro.** A linger unit runs only once the distro is running. After a WSL service restart, nothing
  starts the distro until something calls `wsl.exe` (2026-10-14: down 06:41:17Z-12:48:57Z). A Windows-side start task
  is the host lane's part.
- **A boot-time tab.** Measured inside a running boot only: a transient `systemd --user` unit ran `powershell.exe` in
  Windows session 1 and opened a tab that started a process back in the distro. No boot-time run has been measured.
  The relaunch retries each tab (`tab_attempts`) and records each attempt's rc in `relaunched-<boot>.json`.
- **Codex lanes and transient units.** These are re-armed by their owning sessions from the handoff, not by this tool.

## Tests

`python3 -m unittest tests.test_session_relaunch`, which uses stand-ins for the client and PowerShell.
