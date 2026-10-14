# Receipts for the per-launcher cross-session inbound value (2026-10-14)

Captures behind [the decision record](../../../docs/decisions/2026-10-14-cross-session-inbound-per-launcher.md): arm
names, permission modes, booleans, counts and the client's own event kinds. The probes ran the installed Claude Code
2.1.299 in scratch homes and scratch runtime folders against loopback stand-ins for the Messages API (no model, no
credential, no network beyond 127.0.0.1). Nothing here holds an account name, a host name, a path or a key.

| File | What it shows |
| --- | --- |
| `receipts/probe-2.1.299.json` | arms A1-A6c of `probe/inbound_probe.py`: the sender's and the receiver's permission modes, where the receiver's value came from (`--settings`, user or project settings, none), whether the receiver's model was sent the marker, and the receiver's `peer_message_hold` events |
| `receipts/live-reload-2.1.299.json` | arms L1-L3 of `probe/live_reload_probe.py`: the scratch user settings rewritten while a trader-shaped worker runs, before or after the send, with the timeline in seconds |
| `receipts/fail-before.txt` | `tests/test_cross_session_inbound.py` against the additions template, the client-configuration map and the headless recipe as on main at 943d5ba27: 3 of 8 fail |
| `receipts/sources.json` | the two documentation pages the record cites (address, fetch time, sha256, cited lines) and the client binary's sha256 |
| `probe/mock_messages_api.py` | the stand-in, the same bytes as PR #1109's apart from its first docstring line |

To run them again: `python3 probe/inbound_probe.py OUT ~/.local/share/claude/versions/<version> probe/mock_messages_api.py
[ARM ...]` and `python3 probe/live_reload_probe.py OUT <binary> probe/mock_messages_api.py`. They take about five
minutes in all and spend nothing.

The measurements are the author's, taken on one host with one client version; nothing here is a measurement by an
independent party.

## Claims of the decision record without a receipt here

- **The order of the setting's sources and the mode classes** were read in the installed binary; no extract of the
  client's code is kept here.
- **That every interactive coordinator on this host runs in bypass mode** comes from the sessions' transcripts on
  2026-10-14, which stay outside the repository.
