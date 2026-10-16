# Combined review correction

Read date: 2026-10-16. Reviews are cited by name only:
`MICRO-full-a943dd3a.md`, `GPT-VERDICT-a943dd3ae.md`, and `review_output.json`.
This table reports the implemented correction, not a new independent approval.

| Finding | Disposition | Evidence or boundary |
| --- | --- | --- |
| Equivalent GitHub component identities were rejected | Fixed | Reuse pinned `host_receipts.normalize_repository`; the URL/case/suffix fixture failed through both CLI and imported validator before the fix, then passed. Exact proposal spelling still governs proposal coverage. |
| Component-only C2 proposals need package references | Fixed | A table may omit `routes`; package identity and exact proposal coverage remain mandatory. Fail-first component-only fixture now passes. |
| C2 inline rows could bypass the shared route registry | Fixed | Every route ID resolves through the registry, and its inline inventory ID must agree. The unregistered-route fixture failed first; mismatch controls also fail closed. |
| Duplicate, malformed and layer-count guards lacked tests | Covered | Existing code already rejected them. Six isolated guard-removal controls produced the expected assertion failures: duplicate binding 1, duplicate source 1, duplicate repository 1, GPT layer count 2, malformed binding 3, malformed source 3. No unexpected test errors; these are mutation controls, not baseline failures. |
| Routing prefixes needed a primary citation | Fixed | OmniRoute v3.8.51 registry files at the full public pin declare `codex`/`cx` and `muse-code`/`mc`; cited in the code and decision. Prefix comparison does not establish route availability. |
| Model inventory age findings stopped at publication output | Fixed | Publication and the daily collector share `model_currency_due`; `models_past_window` persists detail and the session notice with exit 0. Unreadable and structurally invalid inventory remains a coverage gap and preserves earlier due state. Existing proposal pre-step and other exit meanings are unchanged. Fail-first persistence/gap tests now pass. |
| Current guide still described age-based publication failure and the old background row | Fixed | The guide describes maintenance reporting and the held Haiku 5.5 proposal. Its regression failed before the correction. |
| Edited October 7 record retained private source hashes/prefix | Fixed | Two paragraphs cite the actual packet name only. Both linked evidence records replace private packet/proposal hashes with names and omit private command-output hashes. Two tests first produced three failures, then passed; output contains counts/locators only. Public model artifact identifiers remain. |
| Provider claims lacked independent primary captures in the review package | Supplied for review | `UPSTREAM-PINS-20261016.json` indexes dated vendor excerpts separately from findings. Four `UPSTREAM-SRC-*.md` files and a reproducible public base-validator copy were supplied through the co-op. The Full capture is limited to the pinned public native receipt. |
| Persisted `active_models: unknown` lacked an explanation | Follow-up | Reproduced the status and verified catalog/interpreter/source facts; the collector discarded its failure subtype. Service duration is compatible with, but does not prove, a timeout. The host owner must retain a sanitized failure category and duration. See `active-model-coverage-followup.json`. |
| Integration check assumed the working tree matched HEAD | Fixed | The existing custody helper now reads pinned blobs for modified checkout paths. The retained final-stack input matches the original public run pin. Its synthetic regression failed first, and the unchanged-file control preserves the optimization. No digest allowlist or evidence rewrite was added. |

The timer prerequisite is satisfied. This round changes no timer or runtime
configuration, invokes no model, and introduces no host install. It incorporates
main at `30542e70560147c19049016d19aa3f264515c92f` and re-registers retained
files from both sides. Full affected-suite and publication results are recorded
in `checks.json` after the final run.
