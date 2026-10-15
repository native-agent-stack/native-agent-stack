# Validate shard timing refresh — 2026-10-15

The existing planner already assigns native discovery modules by descending
estimated duration to the least-loaded of eight shards. Its old serial-run
weights substantially understate today's two largest modules. This change
refreshes those inputs and prefers other shards over shard 0 when estimated
loads tie, leaving headroom for shard 0's fixed validation steps. Native
fixtures, the matrix, job names and the eight-report aggregate are unchanged.

## Sources and scope

- Assignment source at base
  [`f165498aa6340860ef52de3a720ca2981eced062`, scripts/validate_shards.py:135–160](https://github.com/native-agent-stack/native-agent-stack/blob/f165498aa6340860ef52de3a720ca2981eced062/scripts/validate_shards.py#L135-L160).
  `ModuleSuite` and `run_shard` retain native module suites; shared fixture
  origins trigger serial fallback. The workflow invokes `run --shards 8` and
  `aggregate --shards 8` in
  [validate.yml at the same pin](https://github.com/native-agent-stack/native-agent-stack/blob/f165498aa6340860ef52de3a720ca2981eced062/.github/workflows/validate.yml).
- [CPython v3.12.3, Lib/unittest/runner.py, `_printDurations`](https://github.com/python/cpython/blob/v3.12.3/Lib/unittest/runner.py#L191-L214),
  [case.py, `TestCase.run`](https://github.com/python/cpython/blob/v3.12.3/Lib/unittest/case.py),
  and [suite.py, `TestSuite.run`](https://github.com/python/cpython/blob/v3.12.3/Lib/unittest/suite.py)
  define native duration reporting and fixture execution. The hosted log
  reports Python 3.12.3. Native `--durations 50` gives the 50 slowest individual
  tests per shard, not every module's isolated runtime.
- GitHub Actions [workflow jobs REST API](https://docs.github.com/en/rest/actions/workflow-jobs),
  [workflow artifacts REST API](https://docs.github.com/en/rest/actions/artifacts),
  and [matrix documentation](https://docs.github.com/en/actions/using-jobs/using-a-matrix-for-your-jobs),
  accessed 2026-10-15. Installed client: `gh version 2.102.0` (2026-09-30).
- Trigger: the Blacksmith screen's measured imbalance, recorded in
  `SCREEN-blacksmith-20261015.md` and `MEASURED-nas-load.md`. These unpublished
  co-op working records are cited by name only, without digests, under
  [correction #161](../../../docs/decisions/2026-10-12-harbor-parallel-runtimes.md#custody-of-the-run-originals).
  The narrower baseline below is a fresh readback, not a reproduction of that
  report's larger window or its 30-minute median.

Layer-resolution delta: `catalogs/landscape/foundation.json` records
`ci-supply-chain`, with native GitHub Actions and the pinned automation tools;
its latest covering sweep is `landscape-sweep-20260929`, manifest
`catalogs/sota-convergence/manifest-20260929.json`, returns
`evidence/artifacts/landscape-sweep-20260929/returns.json`, recorded in
`catalogs/saturation/ledger.json`. The wave ledger references the original
recorded verdict in `catalogs/sota-convergence/layer-verdicts-20260922.json`.
Surviving poutine and the two
actionlint candidates, and the missing-vote firewall candidates, remain
outside this timing correction. No CI-runner layer or new vendor selection is
claimed. The bounded changed evidence is the measured stale assignment cost.

## Measurement and proxy

[timings.json](timings.json) commits three complete successful `main` push
runs, their heads, 24 job IDs, job/step/native-suite durations, log checksums,
and inventory artifact IDs/checksums. The sample is the latest successful
`main` push on each of October 13, 14 and 15 available before 05:50Z. Attempt 1
is used throughout. All 24 parsed primary-event counts equal the native test
counts; there were no unrecognized completion events.

The table records the exact `gh api` endpoint templates and extraction method.
For each primary verbose test event, its completion delta is a timestamp
proxy. When a native duration is present, the larger value retains class or
module fixture transitions and log-delivery overhead. Case IDs map through
that run's uploaded `report.json` inventory to discovery owners; this matters
for `tests.test_native_maintenance`, which owns three differently named source
modules. Sum by owner per run, then take the median of the available samples.
Missing observations are not zero. Of 410 observed owners, 392 have three
samples, 16 have two and two have one.

Each reconstructed suite is within 0.37 seconds of its native suite total.
That reconciles gross accounting; it does not make individual timestamp
proxies precise isolated measurements. New modules retain the existing
10-second fallback. Provisioning, queues, discovery and shard-0-only validators
are outside this expected-module-time model.

## MEASURED before

Seconds from REST job `completed_at - started_at`, excluding queue time:

| Shard | Run 38486609305 (10-13) | Run 38647310087 (10-14) | Run 38675090239 (10-15) | Median |
| --- | ---: | ---: | ---: | ---: |
| 0 | 550 | 625 | 596 | 596 |
| 1 | 335 | 422 | 434 | 422 |
| 2 | 1166 | 1087 | 1055 | 1087 |
| 3 | 449 | 465 | 442 | 449 |
| 4 | 1020 | 1557 | 1219 | 1219 |
| 5 | 368 | 416 | 421 | 416 |
| 6 | 364 | 425 | 400 | 400 |
| 7 | 469 | 478 | 469 | 469 |

The PR body records the separate **MEASURED after** table from the PR's own
completed CI run and its run/head identifiers. The predictions below are not
the after measurements.

## Expected assignment and regression

The frozen table evaluated with the original planner and production weights predicts
`[435.534, 356.046, 1033.212, 370.260, 1180.264, 340.245, 325.995, 391.078]`
seconds. Refreshed weights and the shard-0 tie-break predict
`[456.485, 917.878, 775.843, 456.485, 456.485, 456.485, 456.485, 456.485]`.

The unchanged workflow assigns 22 extra validation steps exclusively to
shard 0. The same three baseline jobs measure their total at 111, 112 and 99
seconds (median **111 seconds**), retained in `shard_zero_overhead` in the
timing table. Common provisioning and PR-only steps are excluded. Breaking
equal-load ties in favor of other shards prevents the largest module from
stacking on that work. Shard 0's expected module-plus-validator time becomes
567.485 seconds; the largest shard remains 917.878 seconds.

`tests.test_pre_push_gate` alone costs an estimated 917.878 seconds and
`tests.test_landscape_sweep_harness` 775.843 seconds. Native modules remain
indivisible. The refreshed assignment reaches that module lower bound for
the critical path, while its maximum/median ratio is 2.011. The remaining six
shards average 456.485 seconds; balancing that remainder cannot give a ratio
below 1.5 while the two largest modules remain indivisible.

The new test uses the independent committed observations to require:

- Maximum expected shard time at most the largest module plus **1 second**
  of numeric/proxy allowance, excluding runner setup.
- Every other expected shard time at most that largest module's time.
- Maximum/median expected time **below 2.1** across all eight shards.
- Including shard 0's measured fixed validation overhead, the maximum still
  fits the largest module plus one second.

Fail-first: against the original production weights, all three assertions
failed (maximum 1180.264 seconds, ratio 3.1005). With refreshed weights but the
original tie-break, the additional fixed-overhead assertion fails at 1028.878
seconds against 918.878 allowed. After the tie-break correction, all 14 shard
tests and 10 existing workflow/aggregate contract tests pass. The duplicate
receipt fixture now duplicates the populated shard instead of assuming it is
shard 0; it still requires rejection and zero counted tests, and checks the
exact unknown-shard list. The two hang-diagnostic fixtures likewise locate
their hanging test through native discovery/assignment instead of assuming
shard 0: both failed first with an empty shard (exit 0), then passed with the
original 3-second timeout, status 124, signal and traceback assertions intact.
Full reruns stay
the practice; partial shard reruns do not satisfy the eight-report aggregate.

## Follow-up boundary

Getting below roughly 15 minutes requires a separately reviewed fixture-aware
split of `test_pre_push_gate` (15.30 minutes) and
`test_landscape_sweep_harness` (12.93 minutes). This PR does not change their
tests or fixtures. Refresh the table when new CI evidence changes these
costs; a hosted result that does not improve the critical path should reopen
the timing estimates before expanding scope.
