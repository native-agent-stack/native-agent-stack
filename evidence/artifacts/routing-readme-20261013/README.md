# Receipts for the routing README correction (CPA-V-12, 2026-10-13)

Value-free: counts, file names and test names only.

| File | What it shows |
| --- | --- |
| `receipts/fail-before.txt` | each method of `tests/test_routing_readme.py` on its own, in a process of its own, against the README of the exact merge base (the same file as on main when the change was written: it calls the AFTER measurement outstanding and the demand absent) and against this head: 5 of 5 fail on the merge base's README and pass here; and the extended baseline method as the first head had it (values only), which passes on the merge base's README, the escape of round 1 |
| `receipts/mutants-14.txt` | the 14 mutants of the README, the record's table and the baseline file it is read against: 14 of 14 killed |
| `receipts/mutants-round1-17.txt` | round 1: the 14 mutants again and three that hold the label of the quoted counts (the escape of the first head among them, which its test did not kill): 17 of 17 killed |

The primary source of every number the README now quotes is the decision record `docs/decisions/2026-10-10-daily-skill-invoke-rate.md` ("Primary effect size: same-checkout hermetic ablation") and
`adoption/skills/claude-routing/trigger-baseline.json`; the test reads both and fails when one changes without the other. The mutation driver is a script of the author's private record.
