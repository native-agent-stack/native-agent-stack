# Receipts for the skill-list reload after a compaction (2026-10-14)

Captures behind [the decision record](../../../docs/decisions/2026-10-14-skill-list-reload-after-compaction.md): counts
and booleans only. The probe ran the installed Claude Code 2.1.296 and 2.1.299 in scratch homes against a loopback
stand-in for the Messages API (no model, no credential, no network beyond 127.0.0.1); nothing here holds an account
name, a host name, a path, a key or any of the client's prompt text.

| File | What it shows |
| --- | --- |
| `receipts/arms.json` | the 12 arms of `probe/skill_list_probe.py`: three kinds of compaction (`/compact`; automatic before a turn's request; automatic inside a turn that calls a tool), each without and with the settings template's hook, on both client versions. Per request: its number, its message count, whether the Skill tool was offered and whether the skill list was in the messages; per arm the compaction's trigger as the client reported it and the request count at the boundary |
| `receipts/fail-before.txt` | `tests/test_skill_list_reload_hook.py` run against the settings template as it is on main at 59899aaf: 7 of 14 fail |
| `receipts/mutants-16.txt` | 16 mutants of the template entry and of the receipt: 16 of 16 killed |
| `receipts/sources.json` | the two published sources the record cites: address, fetch time, size, sha256 and the cited line numbers |
| `probe/skill_list_probe.py` | the probe. It reads the hook from the settings template, so the receipt is about the entry the repository ships, and it deletes its scratch directory, request logs included |
| `probe/mock_messages_api.py` | the stand-in, copied from pull request #1100 at its head 6f16028f with one addition: it can report a large context on its first replies, which makes the client compact by itself |

To run it again: `python3 probe/skill_list_probe.py OUT.json adoption/templates/claude.settings.template.json
~/.local/share/claude/versions/<version>...` from the repository root. It needs the client binaries and `jq`, takes about
two minutes per version and spends nothing.

The mutation driver is a script of the author's private record. The measurements are the author's, taken on one host
with two client versions; nothing here is a measurement by an independent party.

## Claims of the decision record without a receipt here

- **The share of tool calls made without the list** (90%) and the Skill call counts come from the command center's
  diagnosis of 2026-10-14, which reads session transcripts and stays outside the repository.
- **The places where the client clears its set of sent names** were read in the two installed binaries; no extract of
  the client's code is kept here.
- **An idle compaction** was not exercised. macOS and Windows clients were not run.
