# Combined review correction

Read date: 2026-10-16. Reviews are cited by name only:
`MICRO-full-a943dd3a.md`, `GPT-VERDICT-a943dd3ae.md`, and `review_output.json`.
This table reports the implemented correction, not a new independent approval.

Round 3 also addresses `MICRO-delta-94b4ba55.md`,
`GPT-VERDICT-94b4ba551.md` and the newer `review_output.json`, named only.

The small follow-up to `MICRO-delta-1b62f8e7.md` and its matching local review
closes the notice-budget regression: three gaps compact before the budget is
exhausted, and no fitting command means omitting the inline command rather than
failing collection. Unreadable prior history no longer blocks writing current
known counts, retained origins appear in text, and the preservation wording is
aligned. Route-binding shape and PyPI mismatch guards now have explicit negative
controls. The three-gap, prior-history and rendering failures were reproduced
at `1b62f8e7d501846abb974622c89111f6f794ae9b` before the correction.

| Round-3 finding | Disposition | Evidence or boundary |
| --- | --- | --- |
| Gateway proposal could borrow a valid route ID | Fixed | Registry entries declare route kind and exact retained identities; the C2 repository must agree. The gateway relabel fixture returned success before the fix and now fails. |
| PyPI project comparison was case-sensitive | Fixed | Reuse the existing PEP 503 normalizer while preserving exact proposal spelling for coverage. Both case and punctuation fixtures failed before the fix. |
| Malformed/unknown C2 component lacked coverage | Covered | Five negative fixtures exercise the existing correct guard; no baseline defect is claimed. |
| Unknown inventory plus another due count erased earlier model findings | Fixed | The exact stale-receipt combination failed first. Earlier model count/findings are retained with their origin, alongside new known counts and the current gap. |
| SessionStart summary dropped gaps beside counts | Fixed | Both ordinary and truncated-count fixtures failed first. Summary space is reserved for the gap, using a shorter details pointer when necessary. |
| Haiku exception text, count total and preservation wording were stale | Fixed | Guide names the held Haiku 5.5 proposal; active-model guide lists eight counts; preservation wording describes retained findings rather than unchanged bytes. |
| Cleanup claim overstated the touched scope | Corrected claim only | Untouched `handbook-projection.json` and `fill-checks.json` retain historical residue under addendum-22. Those records were not edited. |
| Independent captures were missing from the review packet | Supplied and delivery confirmed | `pr1201-public-upstream` contains 14 public source/index files plus `SHA256SUMS`; the co-op confirmed next-packet attachment. Any privacy-scan exclusion must be named as an unmirrored-source gap. |
| Active-model host cause still lacks a retained category | Named GAP | `F5-G-ACTIVE-MODEL-FAILURE-CATEGORY` remains bounded and nonblocking; no host rerun or speculative timeout change. |

| Finding | Disposition | Evidence or boundary |
| --- | --- | --- |
| Equivalent GitHub component identities were rejected | Fixed | Reuse pinned `host_receipts.normalize_repository`; the URL/case/suffix fixture failed through both CLI and imported validator before the fix, then passed. Exact proposal spelling still governs proposal coverage. |
| Component-only C2 proposals need package references | Fixed | A table may omit `routes`; package identity and exact proposal coverage remain mandatory. Fail-first component-only fixture now passes. |
| C2 inline rows could bypass the shared route registry | Fixed | Every route ID resolves through the registry, and its inline inventory ID must agree. The unregistered-route fixture failed first; mismatch controls also fail closed. |
| Duplicate, malformed and layer-count guards lacked tests | Covered | Existing code already rejected them. Six isolated guard-removal controls produced the expected assertion failures: duplicate binding 1, duplicate source 1, duplicate repository 1, GPT layer count 2, malformed binding 3, malformed source 3. No unexpected test errors; these are mutation controls, not baseline failures. |
| Routing prefixes needed a primary citation | Fixed | OmniRoute v3.8.51 registry files at the full public pin declare `codex`/`cx` and `muse-code`/`mc`; cited in the code and decision. Prefix comparison does not establish route availability. |
| Model inventory age findings stopped at publication output | Fixed, with persistence and notice-budget corrections | Publication and the daily collector share `model_currency_due`; `models_past_window` persists detail and the session notice with exit 0. Recoverable prior model findings are explicitly retained alongside new known counts and the gap. Unreadable prior history is marked unavailable and does not block current counts; an incomplete run with no known counts retains the prior file. The malformed-inventory/stale-receipt and three-gap cases failed before their corrections. |
| Current guide still described age-based publication failure and the old background row | Fixed | The guide describes maintenance reporting and the held Haiku 5.5 proposal. Its regression failed before the correction. |
| Edited October 7 record retained private source hashes/prefix | Fixed within the touched records | Two paragraphs cite the actual packet name only. The touched `fill-source-review.json` and `j826-checks.json` replace private packet/proposal hashes with names; command-output hashes were removed from `j826-checks.json`. The untouched `handbook-projection.json:40,47` and `fill-checks.json:59` retain pre-existing residue as history under addendum-22. No claim is made that all linked records are clean. Two tests first produced three failures, then passed; output contains counts/locators only. |
| Provider claims lacked independent primary captures in the review package | Supplied for review | `UPSTREAM-PINS-20261016.json` indexes dated vendor excerpts separately from findings. Four `UPSTREAM-SRC-*.md` files and a reproducible public base-validator copy were supplied through the co-op. The Full capture is limited to the pinned public native receipt. |
| Persisted `active_models: unknown` lacked an explanation | Follow-up | Reproduced the status and verified catalog/interpreter/source facts; the collector discarded its failure subtype. Service duration is compatible with, but does not prove, a timeout. The host owner must retain a sanitized failure category and duration. See `active-model-coverage-followup.json`. |
| Integration check assumed the working tree matched HEAD | Fixed | The existing custody helper now reads pinned blobs for modified checkout paths. The retained final-stack input matches the original public run pin. Its synthetic regression failed first, and the unchanged-file control preserves the optimization. No digest allowlist or evidence rewrite was added. |

The timer prerequisite is satisfied. This round changes no timer or runtime
configuration, invokes no model, and introduces no host install. It incorporates
main at `30542e70560147c19049016d19aa3f264515c92f` and re-registers retained
files from both sides. Full affected-suite and publication results are recorded
in `checks.json` after the final run.
