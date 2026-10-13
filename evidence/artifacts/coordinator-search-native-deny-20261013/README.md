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
| `receipts/fail-before-round1.txt` | round 1 of the review (the read of `74afed4eb`): the new tests against the sources of the head that was read and against this head, and the probe's pre-fix read of a silent child (a loop that blocks past its own deadline) |
| `receipts/mutants-round1.txt` | the 15 mutants of round 1 (the two registrations without `exec`, the recovery preflight's home, the probe reader's deadline, signals and record selection): 15 of 15 killed; the first run killed 13, and the two survivors and the tests that now kill them are named in the file |

The probe drivers (the init-record capture and the two-arm model call) are scripts of the author's private record; the method is in the record and in each receipt. The measurements are the author's, taken on
one host with one client version; nothing here is a measurement by an independent party.

The two-arm model call measured the first form of the registration, `[ -f "$f" ] && exec python3 "$f"; true`. For a missing file the two forms run the same commands (the check is false and the closing `true` ends the
command), so the measured arms stand; the cases the first form got wrong (an existing file that cannot be read, a runner that exits 2) are shell-level and are tested in
`tests/test_coordinator_search_native_deny.py`, not measured natively.

## Claims of the decision record without a receipt here

- **The marked coordinators' launcher files** are private to their owners; the overlay is the reviewed diff the command center applies.
- **A resume of a marked coordinator through a route that omits `--settings`** was not run; the record says the denial is per launch.
