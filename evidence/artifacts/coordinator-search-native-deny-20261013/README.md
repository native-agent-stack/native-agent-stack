# Receipts for CPA-V-03: a marked coordinator's WebSearch is denied natively at launch (2026-10-13)

Value-free captures behind the measurements of [the decision record](../../../docs/decisions/2026-10-13-coordinator-search-native-deny.md), taken on the first host with Claude Code 2.1.296
(headless sessions in an empty directory, the host's settings untouched; the one model call per arm is `claude-haiku-5-5`). Nothing here holds an account name, a host name, a home path, a key,
a search query's result or a transcript: tool names, counts, flags and error classes only.

| File | What it shows |
| --- | --- |
| `receipts/tool-lists.json` | six init-record runs: whether `WebSearch` and `WebFetch` are among the tools the client lists under no settings, `--disallowedTools WebSearch`, the overlay, the overlay under `bypassPermissions`, a hook entry with a missing runner alone, and the overlay with that runner (the host runs in `bypassPermissions` by default, so every arm is a bypass arm) |
| `receipts/behavior-probe.json` | one model call per arm, asked to call WebSearch once: the control, a runner that exits 1, a runner whose file is missing (exit 2), and the overlay with each; and two UserPromptSubmit runs, a missing runner and the existence-checked registration |
| `receipts/docs-excerpts.txt` | the lines of the permissions, settings-reference, CLI-reference and hooks pages (fetched 2026-10-13, with size and sha256) and the changelog line that the decision cites |
| `receipts/fail-before.txt` | the new test module against the sources of `ba6afd8d7` (main when the change was written; every file this change touches is the same on `77cc7ef42` and on `24a209016`, the base of the pull request, so the result holds there) and against this head |
| `receipts/mutants-v03.txt` | the 15 mutants of the change (the hint, the overlay, the registrations, the applier's retirement): 15 of 15 killed; the first run killed 14, and the survivor (a template that still runs the replaced command) is killed by the host's own timeout that its test now asserts |

The probe drivers (the init-record capture and the two-arm model call) are scripts of the author's private record; the method is in the record and in each receipt. The measurements are the author's, taken on
one host with one client version; nothing here is a measurement by an independent party.

## Claims of the decision record without a receipt here

- **The marked coordinators' launcher files** are private to their owners; the overlay is the reviewed diff the command center applies.
- **A resume of a marked coordinator through a route that omits `--settings`** was not run; the record says the denial is per launch.
