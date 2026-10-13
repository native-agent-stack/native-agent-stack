# Receipts for the Claude agent drift check (CPA-V-10, 2026-10-13)

Value-free captures behind [the decision record](../../../docs/decisions/2026-10-13-claude-agent-drift-check.md): counts, flags and test names only. Nothing here holds an account name, a host name, a home path, a key or the text
of an agent definition.

| File | What it shows |
| --- | --- |
| `receipts/host-run.json` | `scripts/adoption_status.py --profile token-efficiency --client-wiring --json` on the first host with the round-2 commit: `client_wiring.claude.stack_agents_drift` 0 and `complete` true (the 11 shipped definitions equal, the four vendor-installed ones listed, no subfolder) |
| `receipts/fail-before.txt` | the new `tests/test_adoption_status.py` against `scripts/adoption_status.py` at `c63c83a82` with two constants added (so the tests fail on behavior, not on a missing name): `FAILED (failures=15, errors=1)` of 153 tests, among them the stale-agent fixture that reported `complete: true` |
| `receipts/mutants-20.txt` | the 20 mutants of the check (the key, the vendor list, the byte comparison, links and folders, absent and unreadable folders, the source folder, the completeness rule, the limitation text): 20 of 20 killed |
| `receipts/fail-before-review.txt` | the tests of the review fix against the sources of `e70d2de0a`, the head that was read: FAILED (failures=24, errors=3) of 170 tests, in 16 tests (the replacement of a shipped file or of the agents folder by a link is read through: 0 and complete) |
| `receipts/mutants-review.txt` | the 49 mutants of the review fix (the descriptor reads, the depth and entry bounds, nested definitions, links and other kinds, the vendor front matter rule, the platform fallback, the Codex caller, the limitation text): 49 of 49 killed |
| `receipts/fail-before-round2.txt` | the tests of the round-2 commit against the sources of `e22358e46`, the head that was read: FAILED (failures=42, errors=62) of 178 tests, in 9 tests (7 fail on behavior: every vendor spelling of the reviewer gives a count and complete wiring; 2 raise because the name reader does not exist there) |
| `receipts/mutants-round2.txt` | the 92 mutants of the final source (the earlier groups on the final tests, and the name reader: the block extraction, the key lines, the values, the quoted scalars, the vendor branch): 92 of 92 killed |
| `receipts/identity-oracle.txt` | the differential measurement of the name reader against the installed 2.1.296 client's own front matter parser: the byte intervals of the copied functions, the Bun versions, 8,582 generated texts and 26 real definitions per family, 0 misses |

The mutation drivers and the oracle are scripts of the author's private record (this commit adds no code under `evidence/`); the mutants are listed by label, one change each.
