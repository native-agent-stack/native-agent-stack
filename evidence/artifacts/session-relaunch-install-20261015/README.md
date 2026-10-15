# Session relaunch: install, inverse and background respawn (2026-10-15)

The evidence behind `tools/session-relaunch/install.sh`, `uninstall.sh` and the background-session respawn, and
[the decision](../../../docs/decisions/2026-10-15-session-relaunch-install-and-inverse.md).

| File | What it shows | Class |
|---|---|---|
| `receipts/sources.json` | The agent-view doc lines at 2.1.301 (sha256 `c8e2b810…`, unchanged since 2026-10-14), `claude daemon --help` and `claude respawn --help` at 2.1.301, two CHANGELOG lines at anthropics/claude-code@03b5892e, and the v6 host install the scripts port | primary sources |
| `receipts/respawn-probe.json` | `claude respawn` on two scratch background rows: a stopped row with a saved transcript resumed on its own session; a failed row without one re-sent its dispatch prompt | measured, one run per case |
| `receipts/tests.json` | The two test modules on main's tree (they fail), and three mutants of `uninstall.sh`, one per v5 P1 class, each failing exactly its fixture | measured |

Not measured: real systemd behaviour, a boot, the tab opener on a second distro, and a failed background row with a
saved transcript after a real shutdown.

Re-run with `python3 -m unittest tests.test_session_relaunch tests.test_session_relaunch_install`.
