# Day-five currency dispatch and catalog-freshness failure correction

Base: `929bc3c3f3b6d1f890279ff14d3f500e2d4db592`. Sources/logs read
2026-10-15 UTC. This change reuses the existing daily catalog workflow,
model-currency age policy, native unittest shards and GitHub issue APIs.
It makes no model call, adds no provider secret and never resets review dates.

## Measured scheduled failures

Read each run with `gh run view <id> --repo native-agent-stack/native-agent-stack --log-failed`
and inspected its exact failed step/head through the native run API:

| Run | Head | Actual failure |
| --- | --- | --- |
| [38118948272](https://github.com/native-agent-stack/native-agent-stack/actions/runs/38118948272) | `8bffa2c41692ef483e91b68e3b15aeb331423d2c` | Serial suite:12772tests/2226.144seconds,25failures,1316skips. Native scanner missing from test environment; affected pre-push/synthetic scanner checks. |
| [38216023021](https://github.com/native-agent-stack/native-agent-stack/actions/runs/38216023021) | `2c4fdf86f929197a85505358e294be164c58a7eb` | Serial suite:13827tests/2544.697seconds,25failures,1420skips; same missing scanner prerequisite. |
| [38358887691](https://github.com/native-agent-stack/native-agent-stack/actions/runs/38358887691) | `dbe7a8da1bb497570471e2b9d0dcfe56bbdc56e9` | Serial suite:14231tests/2146.728seconds,527failures,1440skips.492assertions explicitly report native publication scanner unavailable, with additional expected-diagnosis mismatches. |
| [38559440278](https://github.com/native-agent-stack/native-agent-stack/actions/runs/38559440278) | `8c11dac090f71d340abd54abf8c67ffae13fa2d5` | Serial suite exceeded its55minute guard, process exit124/fatal timeout. No complete unittest summary exists; no test-count or success inferred. |

The first missing-scanner defect is already repaired on the base, and its guard
is retained. The fourth run is a distinct throughput/budget failure: one serial
suite no longer fits. Increasing the timeout would defer the same failure;
discarding tests would lose coverage. Reuse the validated eight-way native
whole-module partition from `validate.yml` instead.

## Full test coverage, separate from source fetch

`freshness` fetches metadata once and retains its report. New `freshness-tests`
cells copy the existing validation prerequisite commands: full-history checkout,
locked dependencies, promotion venv, Bun, shell-parser/YAML pins and native
scanner. Every cell invokes the existing `scripts/validate_shards.py run`, with
fail-fast disabled, unchanged55minute per-cell hang guard and verbose logs.
An always-run native aggregate requires all eight complete, successful reports
and exact discovery coverage. The existing evidence proposal now waits for both
the freshness report and this aggregate. A partial or failed suite is not green.

The new workflow regression failed before the change because the native matrix
and aggregate jobs were absent, then passed after the change. Existing scanner,
history, diagnostics and prerequisite guards now inspect `freshness-tests`.
Shell-parser/YAML recorded omissions are removed only because those prerequisites
are now provisioned; synthetic stale-gap/fake-provision controls remain exercised.
Local discovery measured411modules/14887cases, zero loader errors and zero shared
fixture origins, so no serial fixture fallback was needed on this interpreter.
This is discovery/contract evidence, not a complete hosted eight-shard pass.

## Age-triggered durable review requests

An independent main-only `model-currency` job runs on the existing daily cron
(`17 6 * * 1` and `17 6 * * 0,2-6`) and manual dispatch. It has **no needs edge**
on the network report or suite: their failure cannot suppress due delivery.
Only this job gains `issues: write`; it otherwise has `contents: read` for the
checkout, default workflow permissions remain empty, and it uses only the native
`GITHUB_TOKEN`. No model/provider credentials are added.

`scripts/model_currency_tracking.py` calls the existing
`collect_model_currency(..., offline=True)` calculation and consumes only
`refresh_due` rows, including the existing pre-release-age transition behavior.
For a row without a landscape check, delivery now begins two days before its
effective release reaches day43 (the first invalid date), rather than waiting
until validation already fails. Effective package release dates are retained
for package-bound rows; no release/check date or validator rule is changed.
The threshold remains max_landscape_age_days minus refresh_lead_days (7 minus2,
day5). Schema/source/future-date errors fail delivery; no inventory bytes change.
The gate is row/check-age driven, not a hardcoded October deadline. Initial
triggers are October19 for Fable/Astra and October20 for the nine October15
checks, before first invalid dates October22/23.

No-check rows at the rebased main inventory are `claude-opus-5-5`,
`claude-sonnet-5-5`, `gpt-6-1-sol`, `mineru-onnx-bundle`,
`headroom-bge-onnx`, `headroom-minilm-onnx`,
`headroom-technique-router-onnx`, `headroom-siglip-onnx`,
`markitdown-magika-standard-v3-3` and `codebase-memory-static-nomic`.
The actual MinerU ONNX row's September10 release means review is due October21,
before its October23 failure date. The regression uses that committed row and
checks October20 (not due),21/22 (due, not expired),23 (due, expired).

At reviewed `fd849227`, the new test fails on October21/22 (request absent)
and October23 (no first-invalid date); at the fold all four dates pass.
Runtime parser/YAML skip controls now plant a synthetic recorded gap in the
child test module and run the real tripwire; empty committed gap sets no longer
make those branches vacuous. The workflow's interpreter comment follows its
actual setup-python3.13 selection.

One bot-owned issue per stable row is maintained with labels
`model-currency-review` and `lane:foundation`, title `CURRENCY-DUE: <row>` and
first-line marker `<!-- native-agent-stack:model-currency-review row=<row> -->`.
Native `gh api --paginate --slurp` completes the entire listing before writes.
Only `github-actions[bot]` issues with exact markers participate; outsider
issues, PRs and prose cannot hijack dispatch. Replays are idempotent. A manually
closed but still-due request reopens; duplicate trusted open issues consolidate.
Requests close only when current main no longer requests that row's review.
Failed/unknown source acquisition never becomes a refreshed landscape date.
`--dry-run` lists/plans only and never creates labels or changes issues.

## Co-op handoff and real refresh

The co-op poller watches bot-owned `model-currency-review` issues. Before emitting
`CURRENCY-DUE`, it validates the marker against known inventory IDs, recomputes
the row's due state on current main and deduplicates the row/check-date cycle.
It dispatches a fixed task through the existing currency lane's converged
harness; issue prose is input data, never executable instructions. The lane
reads primary model cards/release notes and alternatives, retains sources and
opens the normal PR, with two-family reads before landing. Claude paired work
runs through api-actions' full headless Claude Code harness. This job itself
cannot certify quality, apply pins, merge PRs or perform model calls.

GitHub issue creation is durable request delivery, not completion. A schedule
can be delayed/dropped and the co-op must actually perform and land the review.
Monitor this job and due issues before expiry; manual `workflow_dispatch` with
`currency_dry_run` supports recovery. No host service/unit is installed here,
and no scheduled hosted run or poller deployment is claimed by local tests.

## Primary upstream sources at pins

- [github/docs c174b7fc, events-that-trigger-workflows.md, schedule](https://github.com/github/docs/blob/c174b7fcadbafa3a060e684cd943f50d2cc52ef7/content/actions/reference/workflows-and-actions/events-that-trigger-workflows.md#schedule):
  default branch/UTC cron, off-hour-minute scheduling, delay/drop behavior and
  public60day inactivity disabling. Existing cron is reused, not a new scheduler.
- [github/docs c174b7fc, workflow-syntax.md, permissions and job permissions](https://github.com/github/docs/blob/c174b7fcadbafa3a060e684cd943f50d2cc52ef7/content/actions/reference/workflows-and-actions/workflow-syntax.md#permissions):
  least job-level grants, concurrency and matrix behavior.
- [github/rest-api-description 0d220194, api.github.com OpenAPI](https://github.com/github/rest-api-description/blob/0d220194b394fa0f5fe444fb8aa2537b99f7f3f0/descriptions/api.github.com/api.github.com.json):
  `paths./repos/{owner}/{repo}/issues.get` (`issues/list-for-repo`), `.post`
  (`issues/create`), and `paths./repos/{owner}/{repo}/issues/{issue_number}.patch`
  (`issues/update`), including title/body/state/labels fields. Corresponding
  [list](https://docs.github.com/rest/issues/issues#list-repository-issues),
  [create](https://docs.github.com/rest/issues/issues#create-an-issue), and
  [update](https://docs.github.com/rest/issues/issues#update-an-issue) references.
- cli/cli v2.102.0 at `fc4b137cdef0a6bd28fd461b7cf9c84a5812a8cd`,
  [api.go](https://github.com/cli/cli/blob/fc4b137cdef0a6bd28fd461b7cf9c84a5812a8cd/pkg/cmd/api/api.go):
  supported `--paginate`, `--slurp` and `--input -`; payloads are structured JSON,
  never interpolated shell commands. Hosted CLI version belongs to the runner.
- Reused local implementations at base929bc3c3: `freshness_propose.py` age gate,
  `validate_shards.py` native partition/aggregate and `saturation-tracking.yml`
  least-privilege issue delivery, with existing full action SHA pins retained.

Tests use synthetic UTC fixtures only inside the test API; production CLI offers
no date override. Local real-inventory dry-run on October15 reported zero due
rows and zero issue writes. No schedule, external issue or provider action was
triggered during development. CI must establish the hosted result after review.
