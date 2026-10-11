# Disposition of the 22 open code-scanning alerts

Date: 2026-10-11. Status: proposed; the dismissals below run only after this record lands on `main`.

Read at 2026-10-11T02:05Z with the repository's `gh` token: 22 open alerts on `seathatflowsinourveins/native-agent-stack`,
all on the default branch. This record gives each one a disposition and the source that supports it. No workflow,
bootstrap script or evidence artifact changes in this PR. The one guard test added is
`tests/test_code_scanning_dispositions.py`.

| Group | Alerts | Disposition |
| --- | --- | --- |
| A. OSV, frozen macOS lock | 99-107 | Dismiss `won't fix` after landing |
| B1. Scorecard `$/` action reference | 108, 109 | Dismiss `false positive` after landing |
| B2. Scorecard `npm install` of a verified tarball | 91 | Dismiss `false positive` after landing |
| C. Scorecard on retained evidence scripts | 88, 89, 92, 97, 98 | Dismiss `won't fix` after landing |
| D. Scorecard repository-level checks | 14, 18, 20, 21, 22 | Recorded here; 14, 18, 20 and 22 dismissed `won't fix` after landing, 21 left open (clears 2026-12-18) |

## Why scoping the OSV input does not apply (group A)

The nine alerts sit in `evidence/artifacts/macos-application-20260924/variant/pnpm-lock.yaml`: CVE-2026-93749, 94483,
94484, 94485, 94486, 94543, 94544, GHSA-vcvr-r3jv-pc5j (critical) and GHSA-wq5f-xc86-pv6w.

- The required scan already excludes this lock. `.github/osv-scanner-lockfiles.json` assigns it to the frozen group
  (`.github/osv-scanner-frozen-report.toml`), and `security-scan.yml` scans only the ordinary group.
- The alerts are uploaded by a different workflow on purpose. `frozen-evidence-risk.yml`
  (`frozen-osv-sarif-upload`, category `osv-scanner-frozen-macos`) reports that lock's findings with an empty config.
  `docs/decisions/2026-10-07-frozen-evidence-osv-reporting.md` accepted this: findings stay visible, with no
  exceptions, so a future consumer of the lock cannot hide behind a suppression. Dropping `evidence/artifacts/**` from
  that scan would overturn that record, which only the command center may do, and it would remove the visibility the
  record chose.
- A rescan will not close these alerts. The weekly and push runs of `frozen-evidence-risk.yml` upload the same
  findings again, so the alerts stay open until someone dismisses them.
- The existing tests already fail if the lock moves into the ordinary group:
  `tests.test_osv_lockfile_coverage.FrozenScanTests.test_the_split_is_exhaustive_and_disjoint`,
  `test_only_the_frozen_locks_name_a_config` and `test_the_ordinary_config_has_no_exception_for_a_frozen_advisory`,
  plus `tests/test_frozen_macos_variant_no_use.py` for any consumer. This PR adds no duplicate.

Disposition: dismiss each alert `won't fix`. The reason: retained, hash-bound evidence that no workflow installs,
builds or serves; the maintained application lock pins next 16.3.8 and sits in the ordinary scan. Evidence:
`evidence/receipts/osv-frozen-macos-next-1638-20261007.json` and `tests/test_frozen_macos_variant_no_use.py`. A
dismissal is the durable disposition the 2026-10-07 record asks for; it hides nothing from the SARIF, which the
workflow keeps publishing. Re-open the alerts if the lock gains a consumer or its bytes change.

## B1. Alerts 108 and 109: `uses: $/.github/actions/setup-host-name-scanner`

`.github/workflows/validate.yml:251` and `.github/workflows/publish-catalog.yml:96` call the in-repo composite action
with GitHub's self-repository syntax.

- GitHub's changelog of 2026-07-30 (fetched 2026-10-11) defines it: "A `uses:` value that starts with `$/` resolves to
  your workflow's own repository at the exact commit that is running, with no checkout required." It works "everywhere
  the workspace-relative `./` syntax works", needs runner 2.336.0 or newer, and is "the recommended way to compose
  actions and reusable workflows within a repository". The `validate` run on `main` at `eb31d233` ran on runner 2.337.0
  and logged the step as `seathatflowsinourveins/native-agent-stack/.github/actions/setup-host-name-scanner@eb31d233...`,
  the running commit. So the reference is already bound to the workflow's own commit and cannot carry a separate hash.

- Scorecard v5.5.0 (`ossf/scorecard@fac1a1678517b7185cd1fa24699a16423fd841d2`,
  `checks/raw/pinned_dependencies.go:800`) treats only a `./` prefix as same-repository and reports every other `uses`
  as a third-party action.
- Scorecard `main` (`5fc5c0007101ff4d51ba45da3792463b4a7ba7e7`) recognises `$/` (`pinned_dependencies.go:806`, change
  `bbcee3303b5a8a733d2ffe92fdf4364b2b7c0293`, #5191, 2026-09-28). It is in no release: the GitHub compare API
  (`compare/bbcee3303...v5.5.0` and `...v5.4.0`) returns `behind` for both, so neither tag contains it; v5.5.0
  (2026-04-23) is the latest release and tag, and `main` is 54 commits ahead of it. The `$/` string is absent from
  `checks/raw/pinned_dependencies.go` at v5.5.0 and present on `main`. `scorecard-action` v2.4.4 (2026-07-23, the latest
  release) requires `github.com/ossf/scorecard/v5 v5.5.0` in its `go.mod`. Nothing with the fix exists to adopt yet.
- Rewriting to `./` is not a fix. zizmor 1.30.1, which `validate.yml:86` runs with `--persona regular`, reports
  `self-repository` on `./.github/actions/...`; this was reproduced on a scratch copy of `validate.yml`. See
  `docs/decisions/2026-10-04-ci-least-privilege.md` ("self-repository ... asks for `$/` instead of `./`").

Disposition: `false positive`, dismissed after landing. Re-check on the first `scorecard-action` release that bundles
Scorecard with `bbcee3303`; the alerts then close on their own. The guard test keeps every other `uses` pinned.

## B2. Alert 91: `adoption/bootstrap-linux.sh:772`

`npm install "${npm_install_args[@]}" "$archive"` installs a tarball, not a registry spec.

- Scorecard v5.5.0 `checks/raw/shell_download_validate.go:464-490` (`isNpmUnpinnedDownload`) calls every
  `npm install` unpinned except `npm ci` and a `git+...#<commit>` URL, so no argument form can satisfy it.
- `install_npm` fetches `$archive` through `fetch "$url" "$sha256" "$archive"` (`bootstrap-linux.sh:737`), and `fetch`
  (`:357-367`) exits on a sha256 mismatch before the file is renamed into place. The platform dependency is also checked
  against its npm integrity hash (`:526-536`).

Disposition: `false positive`, dismissed after landing. The guard test fails if that argument stops being the
verified archive (for example `name@version`).

## C. Alerts 88, 89, 92, 97, 98: retained evidence scripts

Paths: `evidence/artifacts/new-wsl-local-models-20261002/scripts/a2/a2_run_bfcl.sh:33`,
`.../scripts/steps/M11p-precheck.sh:7`, `evidence/artifacts/new-wsl-install-plan-20261002/config/omniroute-canary-install.sh:82`,
and the two `.sh.txt` files under `evidence/artifacts/omniroute-post-terminal-drain-20261005/`.

- These are captured, hash-bound evidence. Editing them would break `manifests/evidence.json`, so they cannot be
  pinned.
- Scorecard v5.5.0 has no path exclusion. Its maintainer annotations (`config/annotations.go`, a `scorecard.yml` in the
  repository root) are shown only with `--show-annotations`; they do not change SARIF results or code-scanning alerts.
  A `scorecard.yml` would not close these alerts, so none is added.

Disposition: `won't fix`, dismissed after landing: retained evidence, executed on the recorded host only, not run by any
workflow in this repository.

## D. Repository-level checks

These five alerts have no file. Each is a read-only measurement of the repository, and the repository records its
choice here. Quoted warnings are Scorecard's text at 2026-10-11.

- **BranchProtection (14, score 3).** Scorecard warns that `main` does not require approvers, does not require
  code-owner review, has "last push approval" disabled and has "up-to-date branches" disabled. Each is the value in
  `.github/main-ruleset.json` (`required_approving_review_count: 0`, `require_code_owner_review: false`,
  `require_last_push_approval: false`, `strict_required_status_checks_policy: false`). The ruleset instead requires
  squash-only linear history, resolved review threads, and the seven status checks it lists. One GitHub account
  authors and merges every change, so a required human approval would block landing without adding a second reviewer.
  The review gate is the required `verdict-review-gate` check. Disposition: `won't fix`, until the review-App identity
  below ships and the approval count can be raised.
- **CodeReview (20, score 0).** Scorecard counts GitHub approvals on merged changesets (0 of 30). The two-family reads
  happen off GitHub, in the co-op's review records, and the landing scripts check the record. The native fix is #947,
  `docs/decisions/2026-10-09-review-verdict-app-identity.md`: review verdicts move to check runs posted by a dedicated
  GitHub App, so the verdict carries a reviewer identity that Scorecard and the ruleset can see. Disposition:
  `won't fix` for now, with this record as the decision; revisit when the App is registered and live.
- **Fuzzing (18, score 0).** Scorecard v5.5.0 (`docs/checks.md`, "Fuzzing") looks for OSS-Fuzz membership, ClusterFuzzLite,
  or language fuzz functions (Go fuzzing and property-based libraries for Haskell, JavaScript/TypeScript, Erlang, C#/F#).
  This repository is Python, shell and workflow files and uses none of those. Adding a fuzz harness only to raise a score
  is not a decision this record makes. Disposition: `won't fix`; revisit if a parser or a Go/TypeScript component
  becomes a fuzzing target of its own.
- **CIIBestPractices (22, score 0).** The check reads the OpenSSF Best Practices badge API by Git URL
  (`docs/checks.md`, "CII-Best-Practices"). Earning a badge needs the maintainer to enrol the project at
  bestpractices.dev and answer its criteria, which gold also asks of several developers; no enrolment exists. Disposition:
  `won't fix`; the owner may enrol later, which closes the alert on the next run.
- **Maintained (21, score 0).** Scorecard reports "created within the last 90 days"; the repository was created
  2026-09-19T05:26:55Z (`gh repo view --json createdAt`), so the 90 days end on 2026-12-18. This clears by age, not by
  action. Disposition: leave open and let GitHub close it.

## What this PR changes

This record and `tests/test_code_scanning_dispositions.py` only; no workflow, bootstrap script or artifact changes, so
there is no fix whose failure before the change could be shown. The test pins the facts the dismissals rest on, and
fails when:

1. the disposition table above does not list the 22 alerts exactly once each;
2. `install_npm` in `adoption/bootstrap-linux.sh` stops installing only the archive that `fetch()` checked against a
   sha256 (a mutant installing `name@version` is caught), or `fetch()` stops exiting on a mismatch;
3. a `$/` reference in `validate.yml` or `publish-catalog.yml` names an action directory that does not exist.

Third-party action pinning is already enforced by `tests/test_workflow_hardening.py` (every third-party action is
pinned by a full commit SHA); this PR adds no duplicate. The macOS lock's placement in the frozen group is enforced by
the `tests.test_osv_lockfile_coverage.FrozenScanTests` methods named under group A.

## After the PR lands

Dismiss through `PATCH /repos/{owner}/{repo}/code-scanning/alerts/{n}` (`state=dismissed`), each comment citing this
PR and the record section: 99-107 `won't fix` (A); 108, 109 and 91 `false positive` (B1, B2); 88, 89, 92, 97, 98
`won't fix` (C); 14, 18, 20, 22 `won't fix` (D). Alert 21 stays open. Nothing is dismissed before the PR lands, so the
reviewers read the reasons first.

## SOTA sources

- `ossf/scorecard@fac1a1678517b7185cd1fa24699a16423fd841d2` (v5.5.0): `checks/raw/pinned_dependencies.go:800`,
  `checks/raw/shell_download_validate.go:464-490`, `config/annotations.go`, `README.md` ("Showing Maintainers
  Annotations").
- `ossf/scorecard@5fc5c0007101ff4d51ba45da3792463b4a7ba7e7` (`main`, 2026-10-11): `pinned_dependencies.go:806`;
  `ossf/scorecard@bbcee3303` (#5191, 2026-09-28), the fix not yet in a release.
- `ossf/scorecard-action` v2.4.4 (2026-07-23), whose `go.mod` requires Scorecard v5.5.0.
- GitHub, [self-repository action syntax](https://github.blog/changelog/2026-07-30-reference-same-repository-actions-with-self-repository-syntax/)
  (fetched 2026-10-11) and [finding and customizing actions](https://docs.github.com/actions/how-tos/write-workflows/choose-what-workflows-do/find-and-customize-actions),
  as cited in `docs/decisions/2026-10-09-host-name-scan.md`.
- GitHub REST, [compare two commits](https://docs.github.com/en/rest/commits/commits#compare-two-commits), used for the
  "in no release" check on `bbcee3303`.
- zizmor 1.30.1 `self-repository` audit, reproduced locally on a scratch copy.
- GitHub REST, [dismiss a code-scanning alert](https://docs.github.com/en/rest/code-scanning/code-scanning#update-a-code-scanning-alert).
