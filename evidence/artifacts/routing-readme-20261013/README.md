# Receipts for the routing README correction (CPA-V-12, 2026-10-13)

Value-free: counts, file names and test names only.

| File | What it shows |
| --- | --- |
| `receipts/fail-before.txt` | `tests/test_routing_readme.py` against the README on main when the change was written (it calls the AFTER measurement outstanding and the demand absent) and against this head |
| `receipts/mutants-14.txt` | the 14 mutants of the README, the record's table and the baseline file it is read against: 14 of 14 killed |

The primary source of every number the README now quotes is the decision record `docs/decisions/2026-10-10-daily-skill-invoke-rate.md` ("Primary effect size: same-checkout hermetic ablation") and
`adoption/skills/claude-routing/trigger-baseline.json`; the test reads both and fails when one changes without the other. The mutation driver is a script of the author's private record.
