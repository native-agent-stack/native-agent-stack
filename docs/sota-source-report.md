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
they do not vendor the verifier. PR #1003 has landed, and the workflow runs its
real CLI from the trusted PR base. Workflow selection and the explicit checkout
are separate: GitHub selects workflow files from the event's associated commit
([github/docs at be38ec5d, about-triggers:15](https://github.com/github/docs/blob/be38ec5d78e24172587e61b3c6ff40ace1865c71/data/reusables/actions/about-triggers.md#L15)).
For `pull_request`, that commit is the merge commit on `refs/pull/N/merge`
([event table:462](https://github.com/github/docs/blob/be38ec5d78e24172587e61b3c6ff40ace1865c71/content/actions/reference/workflows-and-actions/events-that-trigger-workflows.md#L462),
[commit identity:473](https://github.com/github/docs/blob/be38ec5d78e24172587e61b3c6ff40ace1865c71/content/actions/reference/workflows-and-actions/events-that-trigger-workflows.md#L473),
[merge ref/SHA:479-480](https://github.com/github/docs/blob/be38ec5d78e24172587e61b3c6ff40ace1865c71/content/actions/reference/workflows-and-actions/events-that-trigger-workflows.md#L479-L480)).
A same-repository PR can therefore run a workflow it adds before that workflow
lands; this job still explicitly checks out `pull_request.base.sha` for execution.

Hosted [run 38180620416](https://github.com/seathatflowsinourveins/native-agent-stack/actions/runs/38180620416),
[report job 114592212994](https://github.com/seathatflowsinourveins/native-agent-stack/actions/runs/38180620416/job/114592212994),
ran the real verifier at PR head `6f9e1c128ecc9dfb42580516c8fd8ac1889d6858`.
It reported four code citations, four `ok` and three `not-checked` results, with
`mode report, exit 0`. This is one observed hosted report; the local fake remains
a synthetic check of the invoked argument and exit/summary subset.
