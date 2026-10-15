# Session relaunch after an unplanned WSL restart: probes and sources (2026-10-14)

WSL stopped at 06:41:17Z on 2026-10-14 and the distro came back at 12:48:57Z. At 08:50 ET that day the owner told the
command center that the sessions had not come back by themselves. This folder holds the measurements behind `tools/session-relaunch/` and
[the decision](../../../docs/decisions/2026-10-14-session-relaunch-after-wsl-restart.md).

| File | What it shows | Class |
|---|---|---|
| `receipts/probes.json` | Interop from a `systemd --user` unit (rc 0, Windows session 1). A tab opened from such a unit that ran back in the distro. The cost of `claude agents --json` (0.18-0.23 s). That `~/.claude/sessions/` kept no file for any session alive at the stop | measured inside a running boot |
| `receipts/sources.json` | Agent-view doc lines (sha256 `c8e2b810…`), `claude daemon --help` and `claude agents --help` at 2.1.299, a CHANGELOG line, the earlier terminal decision, the layer verdict | primary sources |
| `probe/tab_probe.ps1`, `probe/tab_probe.sh` | The tab probe's two scripts | measured |
| `probe/retro_dry_run.py`, `receipts/retro-handoff.md` | The 06:40:30Z roster, rebuilt from the CC's handoff, decided against the real journal boots. The handoff the six sessions would have received at 12:49:30Z | simulation |

Not measured: a relaunch at a real boot, which waits for the next restart; the distro start after a WSL service
restart, which is the host lane's part.

Re-run the tests with `python3 -m unittest tests.test_session_relaunch` (53 tests; the client and PowerShell are
stand-ins). Re-run the retro dry run with
`python3 -I evidence/artifacts/session-relaunch-20261014/probe/retro_dry_run.py tools/session-relaunch/session_relaunch.py tools/session-relaunch/config.example.json /tmp/retro.md <rows.json>`
on a host whose journal still lists the boot `a84c7d5283d54dee8de81e0c792dcaa0`. `<rows.json>` holds the seven
`[name, old session id, cwd]` rows. Those ids are local session identifiers, so the file stays in the state directory and
the published handoff shows 8-hex prefixes only.
