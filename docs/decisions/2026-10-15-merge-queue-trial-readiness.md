# Isolated native merge-queue trial readiness

Date: 2026-10-15. Status: trial preparation, not adoption. Layer: repository CI
admission and required-check transport; the existing GitHub Actions and native
module-shard choices remain in place. This is a narrow new-evidence delta under
the [layer-resolution protocol](2026-10-11-layer-resolution-protocol.md).

## Scope and admission

The trial carries only the workflow readiness delta, its direct range-selection
code and regression tests, and this documentation/registration. The evidence
registry conflict fix and its native conflict experiment belong to the separate
merge-queue evaluation. No product or trading behavior changes here.

The command center creates `mq-trial-20261015` from main and a temporary ruleset
targeting only `refs/heads/mq-trial-20261015`. The reviewed proposal uses SQUASH,
ALLGREEN, build concurrency one, minimum/maximum group size one, zero wait and a
120-minute check timeout. Its seven required Actions checks and CodeQL rule
mirror main's requirements. The trial branch and ruleset are prerequisites, not
resources this change creates. Main's protection and rulesets remain unchanged.

Before enqueue, preserve the ordinary lander's `lg_change_id`, LG-OK verdict
files, independent reads, adjudication and explicit cue. Enqueue with native
GraphQL `enqueuePullRequest` and `expectedHeadOid` equal to that reviewed head;
a changed head requires renewed admission. This patch neither replaces nor
automates those approvals. PR #1148 is the ordinary-lander baseline.

The window starts at ruleset creation and ends at the first merge or ejection,
with a three-hour hard cap. The command center deletes the ruleset, then the
trial base branch. Record and verify both inverses by GET. There is no native
ruleset TTL in the pinned create-ruleset schema.

## Required checks on the group SHA

GitHub creates a temporary combined branch before emitting
`merge_group: checks_requested`. A successful PR-head check does not supply a
missing check on that group. All five owning workflows therefore accept the
event without path filters; their existing check names and app identity stay
the same. The validate matrix remains eight shards with its existing aggregate.

| Required context | Group handling |
| --- | --- |
| `validate` | Validate the group checkout; evidence/release comparisons use the explicit group base SHA. Keep all eight reports and the aggregate. |
| `secret-scan` | Verify `head_sha` equals checked-out HEAD and `base_sha` is a distinct commit ancestor. Scan the complete base-to-group range, including merge patches and side ancestry. |
| `token-report` | Run the unchanged test command on the group checkout. |
| `dependency-review` | Pass explicit base/head SHAs to the pinned action; isolate concurrency from PR events and do not cancel group runs. |
| `osv-scanner` | Run the unchanged required scanner with a read token. Exclude groups from the separate SARIF write jobs. |
| `verdict-review-gate` | Compare the complete group against its payload base, verify checkout/base ancestry and allowed branch, and execute the base commit's gate. Never infer a group base from HEAD's immediate parent. |
| `sota-sources` | Resolve the sole native queue entry, bind its base/head commits to the group, then fetch and judge the current PR body. Keep the reusable workflow byte-identical. |

SOTA requires exactly one queue entry, a complete response with no next page,
matching group base/head, an open PR on that base branch and a current PR head
matching the queue response. Missing, stale, ambiguous or unavailable metadata
fails closed. It does not infer a PR number from a temporary branch name.
`MergeQueueEntry.baseCommit/headCommit` are the pinned schema's association
fields; their hosted population is a trial observation still to collect. A
larger queue needs a separately reviewed all-member association and tests.

The verdict gate admits only main and this exact temporary trial branch. Its
existing PR merge-parent checks, retarget protection and base-code trust remain
in place for both. The trial allowlist is temporary and must be removed when
the evaluation is closed. Unknown events fail instead of using a dispatch
fallback. Existing workflow-edit trust limitations are unchanged.

Default-setup CodeQL is vendor-managed and has no checked-in workflow to amend.
The evaluation must retain its actual group-SHA analysis or observed absence on
this non-default branch. A green static check, PR analysis or locally fabricated
event is not evidence of CodeQL's native merge-group behavior.

## Local evidence and open measurements

All commands below ran with `systemd-run --user --scope -p CPUWeight=idle` on
2026-10-15. They are local integration/synthetic results, not hosted queue runs.

| Probe | Before | After |
| --- | --- | --- |
| Native Git secret-scan range fixture | Exit 1: valid group rejected as unsupported | 27 range tests pass, including stale/empty/unrelated group rejection |
| Executed verdict workflow shell fixture | Failed: compared only HEAD's parent instead of the group base | 20 verdict workflow tests pass, including full range, trusted base gate and invalid bindings |
| Executed github-script SOTA fixture | Failed: requested unrelated fallback PR number instead of queued PR | 10 behavior/identity tests pass, including current body, stale/ambiguous queue failure and exact reusable mirror |
| Seven required trigger/range/permission contracts | Nine failing assertions across three tests | All three tests pass; dependency severity and token restrictions retained |
| `actionlint` 1.17.0 on all six changed workflows | Baseline passed | Exit 0 |
| `zizmor --offline --no-config --no-ignores --persona regular --strict-collection` 1.30.1 on the same files | Baseline passed, 14 suppressed | Exit 0, no reported findings, 14 suppressed |

The broader focused command, `python3 -m unittest
tests.test_ci_secret_scan_range tests.test_sota_sources_gate
tests.test_workflow_hardening -q`, passed 165 tests with one existing skip in
21.234 seconds. Its first run failed three fixture subcases because the host's
uutils `tee` 0.10.0 panicked while copying captured test output. The successful
run selected the already installed GNU `tee` 9.7 via a temporary PATH entry,
matching the GNU tool family on the Ubuntu CI runner; no test or repository
command was weakened. `python3 scripts/validate.py` is also required before
freezing the trial head. No hosted success or performance claim is made here.
Collect the rule ID and creation/readback, unchanged-main readback,
reviewed/enqueued head, group ref/SHA/base, seven check contexts/app IDs/runs,
actual CodeQL analysis, admission-versus-ejection reason, enqueue-to-outcome
duration, final tree/author if merged, and inverse readbacks. Keep native
measurements distinct from the fixture results above.

## Sources

Accessed 2026-10-15; upstream behavior is pinned for review.

- [`github/docs@0226a2d78cf2be40ee3d769ec5661638461af0cc`, merge-queue management](https://github.com/github/docs/blob/0226a2d78cf2be40ee3d769ec5661638461af0cc/content/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue.md#L23): required group checks, temporary branch construction and queue settings; [event reference](https://github.com/github/docs/blob/0226a2d78cf2be40ee3d769ec5661638461af0cc/content/actions/reference/workflows-and-actions/events-that-trigger-workflows.md#L374): `checks_requested`, group SHA/ref.
- [The same pin's GraphQL schema, `MergeQueueEntry`](https://github.com/github/docs/blob/0226a2d78cf2be40ee3d769ec5661638461af0cc/src/graphql/data/fpt/schema.docs.graphql#L26227), [`Repository.mergeQueue(branch:)`](https://github.com/github/docs/blob/0226a2d78cf2be40ee3d769ec5661638461af0cc/src/graphql/data/fpt/schema.docs.graphql#L55547), and [`EnqueuePullRequestInput.expectedHeadOid`](https://github.com/github/docs/blob/0226a2d78cf2be40ee3d769ec5661638461af0cc/src/graphql/data/fpt/schema.docs.graphql#L14285).
- [`actions/dependency-review-action@a1d282b36b6f3519aa1f3fc636f609c47dddb294`, `action.yml:25`](https://github.com/actions/dependency-review-action/blob/a1d282b36b6f3519aa1f3fc636f609c47dddb294/action.yml#L25): explicit base/head inputs outside PR events. No action pin changes.
- [`actions/github-script@3a2844b7e9c422d3c10d287c895573f7108da1b3`, `src/async-function.ts`](https://github.com/actions/github-script/blob/3a2844b7e9c422d3c10d287c895573f7108da1b3/src/async-function.ts): execution interface used by the existing behavioral fixture.
- [`github/rest-api-description@507b88ecbdccb4789ce77228fa2f2fde4bdeaf1f`, create-ruleset schema](https://github.com/github/rest-api-description/blob/507b88ecbdccb4789ce77228fa2f2fde4bdeaf1f/descriptions/api.github.com/api.github.com.json#L84445): branch scope, merge queue, required checks and code-scanning parameters. The exact proposal passed schema validation with zero errors; it remains a command-center act.
- [`git/git@67ad42147a7acc2af6074753ebd03d904476118f` (2.53.0), `Documentation/git-log.adoc`](https://github.com/git/git/blob/67ad42147a7acc2af6074753ebd03d904476118f/Documentation/git-log.adoc): revision ranges and merge diff formatting. Existing scanner ancestry coverage is retained.
