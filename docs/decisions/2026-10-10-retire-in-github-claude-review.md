# Retire Claude review inside GitHub; AI reviews run locally — 2026-10-10

## Decision

The owner decided on 2026-10-10 at about 17:15Z (relayed by the command center; paraphrased) that Claude review no
longer runs inside GitHub. AI reviews run on the local host, and GitHub enforces the gates. This change removes the
three workflows that ran `anthropics/claude-code-action`:

- `.github/workflows/claude-pr-review.yml` (scheduled and dispatched pull request review);
- `.github/workflows/claude-pr-toolkit-review.yml` (the pr-review-toolkit read before the command center's cue);
- `.github/workflows/harness-audit.yml` (the weekly harness-context audit).

Their tests go with them (`tests/test_claude_pr_review_workflow.py`, `tests/test_claude_pr_toolkit_review_workflow.py`,
`tests/test_claude_harness_audit_bounds.py`), as do their entries in the workflow-security coverage list and the
local-pages inventory. `tests/test_claude_federation_diagnostics.py` keeps its retained-snapshot and decision-claim
tests; its tests of the workflows' accounting shell go. `tests.test_workflow_hardening.InGitHubClaudeReviewRetiredTests`
replaces the API-key tests: the three files must stay absent, and no workflow may run the Claude action, name an
Anthropic key or deploy a job to the `claude-review` environment, read from each job's `environment` as a scalar or a
mapping's `name`, without a decision that reverses this one.

Before this change the command center disabled the three workflows (`disabled_manually`, 17:16Z) and deleted the
`claude-review` environment's `ANTHROPIC_API_KEY` secret (17:16:48Z).

## Cause (the command center's correction #141, measured)

- The API refused every request that carried the action's attribution: a 400 "credit balance is too low" on each of
  the five Console keys, while the same keys work from the Claude Code CLI and the Agent SDK. Request ids
  `req_011Cftv64ZSQrFDAWwCTe1b1` and `req_011Cftv6611xXRySUeyhBAhH`; reproduction scripts
  `ci_review_sdk_repro.sh` and `ci_review_oauth_repro.sh` in the command center's tool directory.
- The attribution: the pinned action sets `CLAUDE_CODE_ENTRYPOINT=claude-code-github-action` for the session
  (`anthropics/claude-code-action@2dca132ff0e0c4094ce6048b422c6915a071210b`, `base-action/src/parse-sdk-options.ts:284`,
  read for this record), and the client then reports that entrypoint in its billing header (the command center's
  measurement; not re-measured here).
- The record of the workflows: `claude-pr-review` had no successful run (4 failed, 68 skipped), the toolkit read
  never ran, and `harness-audit` failed its only run. Under federation, before 2026-10-10, the runs were refused as
  well (`docs/decisions/2026-10-10-claude-federation-diagnostics.md`).

## What remains

- **Local AI reads:** the local Claude review worker (`tools/claude-review-worker`, #953, open), the command
  center's and the co-op's GPT reads, and trading-cc's toolkit reads, all run on the host with the stored keys through
  the credential runner.
- **Codex's GitHub review**, which is not affected.
- **GitHub's gates:** the required checks (`validate`, `sota-sources`, `verdict-review-gate` in
  `pr-metadata.yml`, the supply-chain and security scans) and the landing scripts the command center is moving into
  the repository (`tools/landing`, #975).

**Follow-up (dated 2026-10-10, the command center's ruling at 20:19Z).** The `claude-native-practice` skill still
selects the retired route: its `github-action` row and the Actions part of `pr-review-pre-cue`
(`reference/git-github-automation.md`, `reference/slots.md`, `reference/slots.json`). Sessions load the pinned personal
copy of that skill, not this repository's folder, so editing the folder here would change nothing until the pin
moves. cc-native-practice retires those rows, points them to the local review route and re-pins the skill in its own
pull request right after this one lands.

## Revisit when

- Anthropic accepts Console API keys for requests that carry the action's attribution (a dispatch with a stored key
  returns a review with `total_cost_usd` above zero and a non-empty `modelUsage`);
- outside contributors open pull requests, so a review needs to run on GitHub's side rather than the owner's host;
- the repository moves to an organization, where GitHub's native merge queue becomes available: "Pull request merge
  queues are available in any public repository owned by an organization" (GitHub Docs, Managing a merge queue,
  read 2026-10-10).

## Inverse

1. Revert this change (the three workflows and their tests come back as they were at
   `9d4c00cd05d79b3fd5074df2e46bacab87ee67ff`, #968).
2. Re-set the `claude-review` environment secret from slot `anthropic-api-3` through `credential_run.py`, with the
   value on `gh secret set`'s standard input only (the procedure in `docs/secret-storage.md`).
3. Re-enable the three workflows (`gh workflow enable`) and keep their repository variables set.
4. Put the Claude action's two patterns back in `.github/actions-permissions.json` (`anthropics/claude-code-action@*`,
   and `oven-sh/setup-bun@*`, which its composite bootstrap uses) and in the live selected-actions setting.

## Actions allow-list

`.github/actions-permissions.json` drops `anthropics/claude-code-action@*` and `oven-sh/setup-bun@*`: no workflow uses
them now, and `test_every_allowed_pattern_is_used_by_a_workflow` keeps every remaining pattern in use. The command
center applies the live selected-actions change after this lands.

## Alternatives considered

- **Keep the workflows with an OAuth token** (`claude_code_oauth_token`): the command center's OAuth reproduction is
  among the measured refusals, and a subscription token in CI was already ruled out.
- **Keep them disabled in place:** dead workflows still carry tests, policy exemptions and documentation that describe
  a path that does not run; removing them keeps the repository's description true.

## What would overturn it

Any revisit trigger above, with a measured successful hosted run.

## SOTA sources

- anthropics/claude-code-action at `2dca132ff0e0c4094ce6048b422c6915a071210b` (v1.0.247),
  `base-action/src/parse-sdk-options.ts:283-284`: "Set the entrypoint for Claude Code to identify this as the GitHub
  Action" and `env.CLAUDE_CODE_ENTRYPOINT = "claude-code-github-action"`.
- GitHub Docs, Managing a merge queue,
  <https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue>
  (read 2026-10-10): availability for organization-owned public repositories.
- The command center's correction #141 (measured 2026-10-10; request ids above), relayed to the coordinator; its raw
  records stay in the command center's private state.
