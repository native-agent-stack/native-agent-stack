# Source citation reports

The Source citations workflow reads the current PR description through the
verifier's `--repo`, `--pr` and `--mode report` interface and writes a GitHub job
summary. Findings and report-command failures are advisory during W1b phase B.
The existing required `sota-sources` check still owns section presence.

This workflow needs PR #1003's verifier to land first. It checks out the PR's
main-base SHA, with persisted credentials disabled, and runs no PR-head code.
If that base predates the verifier, the summary names the missing dependency;
a later PR synchronization or reopen with a newer base runs the installed CLI.
No PR-branch revision is fetched or pinned as a verifier dependency.

Runs cover PR opens, synchronizations, reopens, description edits and transitions
from draft. The token has only contents-read and pull-requests-read permissions.
There is no cache, artifact upload, comment write, external secret or model call.
The verifier uses the runner's Python 3 and appends its own Markdown summary.

Sources: GitHub's [pull request events](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#pull_request),
[job summaries](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands#adding-a-job-summary),
[job permissions and advisory jobs](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax),
and [actions/checkout v7.0.1's inputs](https://github.com/actions/checkout/blob/3d3c42e5aac5ba805825da76410c181273ba90b1/action.yml).

The workflow's only action is GitHub-owned and pinned to that full release SHA.
The explicit W1b GitHub-owned-actions constraint creates one exact exception
to the repository's third-party harden-runner observer. The exception test
requires the sole checkout action, trusted base, disabled persisted credentials,
read-only token and advisory job; other jobs keep the existing observer rule.

Local workflow tests use a frozen fake of the verifier's exit/summary contract;
they never execute or vendor PR #1003's unmerged implementation. Hosted API
execution remains unrun until both PRs land and an eligible PR event occurs.
