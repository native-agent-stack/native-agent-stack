# Session relaunch: an in-repo forward install, its automated inverse, and background sessions by `claude respawn`, 2026-10-15

Status: decided by the command center's rulings of 2026-10-15 (cited by name and date) on primary sources read at
client 2.1.301; nothing is installed by this change. It extends
[2026-10-14-session-relaunch-after-wsl-restart.md](2026-10-14-session-relaunch-after-wsl-restart.md) (#1116, #1140).

## Trigger

#1116's tool was installed on NativeStack2604 by hand on 2026-10-15 (host install v6, install_id `ba61c343`): a forward
install script, an ownership manifest and a manual inverse that the command center runs. Its v5 inverse had three P1s
(a forged or reused manifest pair, a symlinked install-state parent or tool directory, and a handoff inventory inside a
process substitution that escaped `pipefail`); v6 closed them in the manual block. The command center then ruled
(2026-10-15, about 20:52Z): 2604 keeps v6 and its manual inverse; for NativeHorizonNY, first check whether upstream now
relaunches sessions after a boot; if not, the tool ships in the new host's install stage with its forward install and an
automated inverse, background rows go through the vendor's own resume path, and the example config gains the `ns51`
launcher's profile. The install stage of #1174 pins the landed commit.

## Upstream at 2.1.301: no relaunch after a boot

Read 2026-10-15 (`evidence/artifacts/session-relaunch-install-20261015/receipts/sources.json`):

- `claude daemon --help` line 12 (2.1.301): service install is disabled; the daemon runs on demand and exits when the last
  client disconnects.
- The agent-view docs (read 2026-10-15T20:05:17Z, sha256 `c8e2b81092b94b4b…`, the same bytes as on 2026-10-14): the
  supervisor starts on demand (line 817) and restarts a session that exits unexpectedly only while it runs (line 823); a
  shutdown stops background sessions, which then show failed and restart only when attached or replied to (lines
  884-886); interactive sessions have no relaunch at all.
- `claude respawn <id>` restarts a session, running or stopped, and a session with a saved conversation resumes it
  (line 766; `claude respawn --help` at 2.1.301).

So the in-repo tool stays (AGENTS.md: never rebuild what upstream ships; upstream does not ship this), and background rows
use upstream's own scripted restart.

## Decision

1. **`tools/session-relaunch/install.sh`** ports v6's `apply.sh` with its gates unchanged (no existing target, a dangling
   symlink included; real paths only; the `stack-alert@` handler loads; the handoff and unit directories exist; an
   install manifest sealed before the first write, bound by a receipt that holds its full sha256 and a random install id).
   Three changes: the sources are the tool's committed bytes at HEAD of the checkout (a tool directory that differs from
   HEAD refuses); the host's config comes in with `--config` and must name the state directory the units read; the
   install state lives in its own root, `~/.local/state/native-agent-stack/session-relaunch-install/`.
2. **`tools/session-relaunch/uninstall.sh`** ports v6's manual-inverse block with its gates unchanged. One change: the
   expected file records are the recorded source commit's bytes in the checkout (the manifest's `source_commit`, bound by
   the receipt) instead of hardcoded digests, and the config's record is the manifest's own. A source commit missing
   from the checkout refuses.
3. **Background rows** with a launcher profile are respawned with `claude respawn <id>`, only when
   `claude agents --json --all` still lists the row with no process and its saved transcript exists; otherwise the
   handoff leaves them to the command center with `claude attach <id>`. Rosters keep the background row's short id and
   state for this. This closes the follow-up recorded at `session_relaunch.py:420` (39b3fcaf5): only interactive rows
   were relaunched.
4. **The handoff's reason text** names the actual reason a row is left (already running, a second row of a name relaunched
   above, no launcher profile, or a kind the tool does not relaunch). This closes the follow-up at `:249-250`, which
   labelled a profiled background row "no launcher profile".
5. **`config.example.json`** gains the `ns51` profile (`native-agent-stack-51`), the launcher row the command center's
   `launch.sh` already has.

## Measured: `claude respawn` at 2.1.301

`evidence/artifacts/session-relaunch-install-20261015/receipts/respawn-probe.json` (2026-10-15, this lane's scratch
rows, Haiku 5.5): a done row whose process was stopped, with a saved transcript, came back from a non-interactive shell
on the same session id with its conversation, nothing re-sent, and its process stayed up. A failed row with no saved
transcript came back too, but its dispatch prompt was sent again and its command ran again. The CHANGELOG says the
opposite since 2.1.290 (anthropics/claude-code@03b5892ee77de289bcd5dfa39f541525ade74aff `CHANGELOG.md` L794): such a
row starts with an empty conversation. That is one observation on a row with an unusual history, so it is recorded as an
**untested boundary**, not a regression, and the transcript gate in item 3 keeps the tool away from it.

## Tests

- `tests/test_session_relaunch_install.py` runs `install.sh` and `uninstall.sh` in scratch HOMEs against the v6
  simulation's stateful `systemctl` stand-in, with its fixtures A, F-B4, F-B3, F-B1a, F-B1b, F-B1c, F-D, E and C, the R
  retirement, and three new ones: G (an unknown source commit), W (a changed tool directory) and K (a host config). Each
  refusal is asserted by its STOP reason.
- `tests/test_session_relaunch.py` gains the background cases (respawned once; left without a transcript; never with a
  process; a failed respawn leaves the run partial and a rerun retries), the reason text and the `ns51` profile.
- Fail-first and mutants (`receipts/tests.json`): on main's tree the two modules fail; a mutant of `uninstall.sh` for each
  v5 P1 class (no parent real-path check, no consumed-receipt check, no handoff-directory check) fails exactly its
  fixture (F-B3, F-B1b, F-B4).

## What this does not cover

- Real systemd behaviour, the boot, the E: path and alert delivery: the stand-in proves control flow, gating, binding and
  filesystem effects only (as v2 to v6 recorded).
- The tab opener on a second distro: `open-tab.ps1` and `launch.sh` are 2604's; NativeHorizonNY's config names its own.
- The `stack-alert@` template on NativeHorizonNY: the install refuses until it loads, so the install stage orders it first.
- A failed background row with a saved transcript after a real shutdown, which waits for the first real boot.
- The third follow-up (a planned restart without `plan-restart` is labelled unplanned) belongs to the command center's
  restart checklist; the README's "A planned restart" section states the command.
- NativeStack2604's v6 install: it stays as installed, with its manual inverse.

## Sources

- `claude daemon --help`, `claude respawn --help`, `claude agents --help` at 2.1.301 (the host's installed client).
- `https://code.claude.com/docs/en/agent-view.md`, read 2026-10-15T20:05:17Z, sha256
  `c8e2b81092b94b4b3ded2c86b40b8329e73b8f39b36acb3288bd56385bc83266`: lines 766, 817, 823, 884-886.
- anthropics/claude-code@03b5892ee77de289bcd5dfa39f541525ade74aff `CHANGELOG.md` (sha256
  `0551b63e968529c0ddbff2010b89014f84f97c8117fd233c176f6392061f3979`): L794 (2.1.290), L4147 (2.1.211).
- The systemd user manager, the scheduling-supervision layer's recorded winner (`catalogs/landscape/foundation.json`
  `/layers/12`, pinned there at 255.4-1ubuntu8.17; this host runs 259.5-0ubuntu3.4, `systemctl --version` on
  2026-10-15): `systemctl --user enable`, `disable --now`, `reset-failed` and `show -p LoadState/ActiveState`
  (systemctl(1)); `OnFailure=` (systemd.unit(5)).
- #1116's host install v6 (`apply.sh`, `MANUAL-INVERSE.md`) and its simulation `run_sim_v6.sh`: coordination records of
  2026-10-15, cited by name and date.
- The command center's rulings of 2026-10-15 on the #1116 inverse (about 20:52Z and 21:13Z): coordination records, cited
  by name and date.
