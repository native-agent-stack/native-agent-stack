# Decision: relaunch the core sessions after an unplanned WSL restart (2026-10-14)

**Status:** proposed by cc-native-practice. Installing the units is the command center's act; nothing is applied.

## Context

WSL stopped at 06:41:17Z on 2026-10-14 and the distro started again at 12:48:57Z (`journalctl --list-boots`). Every
Claude session died at the stop, along with every transient `systemd-run` unit. The linger units came back with the
distro, but no session did. The command center's old session was resumed at 12:49:03Z, and it relaunched the other
five by hand at 12:53:44-12:54:12Z (its launcher's launch.log). At 08:50 ET on 2026-10-14 the owner told the command
center that the sessions had not come back by themselves; this decision is the response.

The failure has two parts:

1. Nothing started the distro after the stop. This is the host lane's part: the cause of the stop, and a Windows-side
   start task.
2. Once the distro was up, nothing relaunched the sessions. This decision covers that part.

## Decision

Adopt `tools/session-relaunch/` on the layer's recorded supervisor, the systemd user manager (`scheduling-supervision`
winners in `catalogs/landscape/foundation.json`, line 3376):

- A timer writes the live sessions to a per-boot roster every minute, through the client's scripting interface,
  `claude agents --json`.
- A boot oneshot reads the newest roster from an earlier boot. If that boot did not end in a planned restart, it writes
  one sealed handoff and opens a fresh tab per profiled session, command center first, through the command center's
  existing `open-tab.ps1` and `launch.sh`.

The decision rules, the install, the inverse and the planned-restart marker are in
[the tool's README](../../tools/session-relaunch/README.md).

## Alternatives

| Option | Why not at 2.1.299 | Overturned when |
|---|---|---|
| Native background sessions (agent view, `claude --bg`) | After a shutdown a session "shows as failed. Attach or reply to it and it restarts from its saved conversation", and sessions "stop if the machine shuts down" (agent-view docs, lines 886 and 982, sha256 `c8e2b810…`). `claude daemon --help`: "Service install is disabled in this version". Moving the lanes to background sessions would also change how they are watched and isolated, which needs its own paired measurement | A release restarts background sessions after a host restart by itself, or a paired run shows the lanes as background sessions at parity |
| Windows Terminal `persistedWindowLayout` | It starts a fresh process from each tab's saved command line and reattaches nothing (`docs/decisions/2026-09-28-terminal-experience.md`, line 616). It acts only when Windows Terminal itself starts again | Unchanged |
| `~/.claude/sessions/<pid>.json` as the roster | None of the seven sessions alive at the stop kept a file from that boot, and `pidDomain` holds the machine id (`evidence/artifacts/session-relaunch-20261014/receipts/probes.json`) | A documented client interface lists the sessions of an ended boot |
| Resume each old session (`claude --resume <id>`) | A resume re-reads the whole old context into a cold cache. The command center's relaunch practice is fresh-from-handoff (`launch.sh`) | A paired measurement shows resume ahead at an acceptable cost |
| tmux with resurrect or continuum | Rejected earlier for Windows Terminal (`docs/decisions/2026-09-28-terminal-experience.md`); tmux dies with the distro too | Unchanged |

## Evidence

All of it is in `evidence/artifacts/session-relaunch-20261014/`.

- **Measured inside a running boot:**
  - a `systemd --user` unit ran `powershell.exe` with rc 0 in Windows session 1, without `WSL_INTEROP` in its
    environment;
  - a tab opened from such a unit ran a process back in the distro about 1 s later;
  - `claude agents --json` took 0.18-0.23 s.
- **Simulation:** the 06:40:30Z roster, rebuilt from the command center's handoff and decided against the real
  journal. It relaunches six sessions, the command center first, and leaves `librarium-course-e2` to the command
  center.
- **Primary sources for the mechanisms** (vendor behaviour; what the tool does with each is local policy, in the
  README's Mechanisms section): the run lock, `fcntl.flock`
  (https://docs.python.org/3.14/library/fcntl.html#fcntl.flock) and flock(2)
  (https://man7.org/linux/man-pages/man2/flock.2.html, Linux man-pages 6.19); the call timeouts,
  `subprocess.run(timeout=...)` (https://docs.python.org/3.14/library/subprocess.html#subprocess.run); the atomic
  replacement, `os.replace` (https://docs.python.org/3.14/library/os.html#os.replace). The Python docs are the 3.14
  docs, for the unit's interpreter (`/usr/bin/python3` 3.14.4), read on 2026-10-15; the cited sentences match CPython's
  `Doc/library/` at tag `v3.14.4`.
- **Tests:** 58 unit tests with stand-ins for the client and PowerShell; one checks that no published sentence of this change attributes a quoted phrase to the owner. The fix round of the first read (four P2s) added the relaunch state file with per-session outcomes and reruns, the refusals when the client gives no list or the journal no longer lists the ended boot, the settle wait instead of a retry after a timed-out tab call, and private file modes; each has a test that fails on the first version. The blocker commit on 376f2bb9 (the CC adjudication of 2026-10-14, two paths to a second live session of one lane) makes a call only when the live list reads the session as absent, records each call in flight before making it, leaves an unconfirmed, uncertain or in-flight session to an explicit --reopen by the command center, gives each name one turn, turns the journal-missing and unreadable-state skips into refusals with exit 1, and adds OnFailure= to the relaunch unit; each has a test that fails on 376f2bb9. The item-2 commit on 307f686c (the CC adjudication addendum of 2026-10-15) saves the provisional unconfirmed or uncertain outcome with each call result before the settle wait, holds an exclusive lock on relaunch.lock in the state directory for every run (a second run is refused with exit 1), spends a reopen only on a call it makes, and refuses a --reopen name that is not unresolved or not still to be relaunched, recording the refusal only where the ended boot's relaunch state already exists; each has a test that fails on 307f686c. The fix on 7aad5a02 (the CC ruling of 2026-10-15T01:50Z on the GPT read) records a --reopen refused because the relaunch is complete or capped in the existing state, under the run lock with no run added, and records no refusal in a dry run; each has a test that fails on 7aad5a02. The follow-up to the local review's completion finding (2026-10-15) bases completion on the run's final live list: a session seen running earlier and missing from that list is absent, with its tab start resolved, so a rerun opens it again, and an unreadable final list leaves the run partial; The follow-up on 0f4ee075 (the remaining P3s of the CC micro and of the GPT read) corrects the README on which refusals are recorded and on the relaunch.lock that a dry run creates, aligns this record with it, cites the vendor sources of the run lock, the call timeouts and the atomic replacement here and in the README, and states the files the publication check scans; each has a test that fails on its base (c8d7fa9e for the completion follow-up, 0f4ee075 for the README follow-up).

It also does not pay the scheduled-tasks slot's owed "`claude -p` run started by a systemd timer across a WSL
restart": no model call runs here, and no boot was measured.

## Not established

- **A boot-time run:** interop readiness when the user manager reaches `default.target`. The tool retries a definite tab
  failure, records every call and leaves an unfinished relaunch to a rerun. The first real restart after the install is
  the measurement.
- **The distro start after a WSL service restart:** the host lane's part.
