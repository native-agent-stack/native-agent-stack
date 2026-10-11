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
| B2. Scorecard `npm install` of a verified tarball | 91 | Dismiss `won't fix` after landing; `npm ci` from committed locks is a separate follow-up PR |
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
`evidence/receipts/osv-frozen-macos-next-1638-20261007.json` and `tests/test_frozen_macos_variant_no_use.py`. The
2026-10-07 record (`docs/decisions/2026-10-07-frozen-evidence-osv-reporting.md:75-86`) asks for a command-center
ledger row naming each advisory's disposition within 24 hours of the report attempt, not for a dismissal; the
dismissal of 99-107 after landing is a separate ruling (the command center, 2026-10-11T02:12Z). The ledger row is the
command center's own record and this PR does not write it. The row to add: alerts 99-107 (the nine advisories above),
input hash `f1c707b8295e85bd396e49b990de92dc82bc0d58eca1e4e4bef31262d9898cd2`, disposition "retained inactive evidence,
no consumer; dismissed `won't fix` after #996 landed", review due per the report attempt. The frozen review issue links
`is:open` alerts, so a dismissal also removes them from that link; the ledger row is what then records them. A
dismissal hides nothing from the SARIF, which the workflow keeps publishing. Re-open the alerts if the lock gains a
consumer or its bytes change.

## B1. Alerts 108 and 109: `uses: $/.github/actions/setup-host-name-scanner`

`.github/workflows/validate.yml:251` and `.github/workflows/publish-catalog.yml:96` call the in-repo composite action
with GitHub's self-repository syntax.

- GitHub's changelog of 2026-07-30 (fetched 2026-10-11) defines it: "A `uses:` value that starts with `$/` resolves to
  your workflow's own repository at the exact commit that is running, with no checkout required." It works "everywhere
  the workspace-relative `./` syntax works", needs runner 2.336.0 or newer, and is "the recommended way to compose
  actions and reusable workflows within a repository". The `validate` run on `main` at `eb31d233` ran on runner 2.337.0
  and logged the step as `seathatflowsinourveins/native-agent-stack/.github/actions/setup-host-name-scanner@eb31d233...`,
  the running commit. So the reference is already bound to the workflow's own commit and cannot carry a separate hash.

- Scorecard v5.5.0 (`ossf/scorecard@c395761df6afe1a69e476bc60a013a94bcbc153f`,
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

`npm install "${npm_install_args[@]}" "$archive" >/dev/null` installs a tarball, not a registry spec.

- Scorecard v5.5.0 `checks/raw/shell_download_validate.go:464-490` (`isNpmUnpinnedDownload`) calls every
  `npm install` unpinned except `npm ci` (:466-468) and a `git+...#<commit>` URL, so no argument form of this command
  can satisfy it.
- The tarball itself is pinned: `install_npm` fetches `$archive` through `fetch "$url" "$sha256" "$archive"`
  (`bootstrap-linux.sh:737`), and `fetch` (`:357-367`) exits on a sha256 mismatch before the file is renamed into place.
  The platform dependency is also checked against its npm integrity hash (`:526-536`).
- The tarball's runtime dependencies are not pinned. `npm install <tarball>` resolves them from the registry by version
  range at install time. Reproduced here at 2026-10-11T02:42Z on the sha256-verified context-hub 0.1.4 tarball
  (`ca9fb94a...888f`, the pin in `adoption/pins-linux-x86_64.json`): the tarball holds no `npm-shrinkwrap.json`, and
  `npm install --global --ignore-scripts --no-audit --no-fund --dry-run <tarball>` reports "added 108 packages". The
  command center's read reports the same absence of a shrinkwrap for the other npm pins (13 runtime dependencies for qmd,
  10 mcporter, 8 context-mode, 28 repomix, 34 socraticode); those counts were not reproduced here. The repository already records this: `docs/decisions/2026-09-25-workstation-sota-refresh.md:376-378`
  ("The package ships no shrinkwrap, and undici 6.29.0 and @lumis-sh/wasm-eex 0.26.2 were published inside its ranges
  after the tag. The bootstrap's `install_npm` passes no `--before`") and `docs/decisions/2026-10-03-currency-wave-w1.md:448`
  ("The npm tarball hash is artifact evidence and does not pin the transitive dependency tree").

So the alert is right that the install is not fully pinned, and "false positive" is wrong for it. Disposition:
`won't fix` for this PR, naming the unpinned transitive dependency tree as the reason. The supported fix is `npm ci`
from a committed lockfile per package, which Scorecard accepts; it changes the bootstrap and its pins, so it is a separate
follow-up PR, planned by the command center, and the alert closes with it.

The guard executes the extracted bootstrap with the repository's existing offline download/npm stubs
(`tests/test_adoption_bootstrap.py:865`, `run_install_pin`) and compares npm's complete observed argv, invocation
count and the archive bytes at npm invocation time. It tests both ignore-scripts branches and paths containing spaces.
Literal argv checks previously accepted archive reassignment and an indexed array append; both now fail,
along with the original six mutations. Separately, the actual `fetch` function is exercised with valid and invalid
cached/downloaded bytes; replacing the downloaded-file verifier with `true` makes the checksum guard fail.

## C. Alerts 88, 89, 92, 97, 98: retained evidence scripts

Paths: `evidence/artifacts/new-wsl-local-models-20261002/scripts/a2/a2_run_bfcl.sh:33`,
`.../scripts/steps/M11p-precheck.sh:7`, `evidence/artifacts/new-wsl-install-plan-20261002/config/omniroute-canary-install.sh:82`,
and the two `.sh.txt` files under `evidence/artifacts/omniroute-post-terminal-drain-20261005/`.

- These are captured, hash-bound evidence. Editing them would break `manifests/evidence.json`, so they cannot be
  pinned.
- Scorecard v5.5.0 has no path exclusion. It always loads a `scorecard.yml` from the repository root
  (`pkg/scorecard/scorecard.go:179-190`), and the SARIF writer skips every annotated check
  (`pkg/scorecard/sarif.go:673-676`, reached from `scorecard-action` v2.4.4 `internal/scorecard/format.go:71`), so an
  annotation for `Pinned-Dependencies` would close these alerts. An annotation names a check and a reason
  (`config/annotations.go`), never a path, so it would also hide every future Pinned-Dependencies finding in live files.
  No annotation is added for that reason.

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
  The review gate is the required `verdict-review-gate` check. Disposition: `won't fix`; revisit
  with CodeReview below, when a second identity that can approve exists and `required_approving_review_count` can be raised.
- **CodeReview (20, score 0).** Scorecard counts a changeset as reviewed only when it has an `APPROVED` review, or a
  merge, by someone other than the author (`checks/raw/code_review.go:55-62`, `probes/codeApproved/impl.go:116-126`);
  it reads no check runs (0 of 30). The two-family reads happen off GitHub, in the co-op's review records, and the
  landing scripts check the record. The review-App decision (#947,
  `docs/decisions/2026-10-09-review-verdict-app-identity.md`) moves review verdicts to check runs posted by a dedicated
  GitHub App; that App reads pull requests and posts check runs, so it cannot approve, and it does not change this
  score. Disposition: `won't fix`. Revisit only if a second identity can submit `APPROVED` reviews or merge, which
  a repository with one authoring account does not have; alert 20 does not clear when the App goes live.
- **Fuzzing (18, score 0).** Scorecard v5.5.0 (`docs/checks.md`, "Fuzzing") looks for OSS-Fuzz membership, ClusterFuzzLite,
  or language fuzz functions (Go fuzzing and property-based libraries for Haskell, JavaScript/TypeScript, Erlang, C#/F#).
  It also detects Python through `import atheris` (`checks/raw/fuzzing.go:131-136`). The repository is mostly Python,
  shell and workflow files, with 16 Go, TypeScript, C# and Rust files outside `evidence/` (`git ls-files`); none is a
  fuzz target. Adding a fuzz harness only to raise a score is not a decision this record makes. Disposition: `won't fix`; revisit if a parser or a Go/TypeScript component
  becomes a fuzzing target of its own.
- **CIIBestPractices (22, score 0).** The check reads the OpenSSF Best Practices badge API by Git URL
  (`docs/checks.md`, "CII-Best-Practices"). Earning a badge needs the maintainer to enrol the project at
  bestpractices.dev and answer its criteria, which gold also asks of several developers; no enrolment exists. Disposition:
  `won't fix`; the owner may enrol later, which closes the alert on the next run.
- **Maintained (21, score 0).** Scorecard reports "created within the last 90 days"; the repository was created
  2026-09-19T05:26:55Z (`gh repo view --json createdAt`), so the 90 days end on 2026-12-18. This clears by age, not by
  action. Disposition: leave open and let GitHub close it.

## What this PR changes

This record and `tests/test_code_scanning_dispositions.py` only; no workflow, bootstrap script or artifact changes. The
regressions fail before their fixes for checksum-verifier bypass, archive reassignment/indexed array append,
and quoted or comment-suffixed missing self-action targets. The tests exercise the existing offline bootstrap
harness and reuse the repository's supported fail-closed workflow loader
(`tests/test_workflow_policy.py:403`, `load_workflow`) instead of introducing another YAML scanner.
They pin the facts the dismissals rest on and fail when:

1. the disposition table above does not list the 22 alerts exactly once each;
2. `install_npm` in `adoption/bootstrap-linux.sh` stops running exactly one `npm install` with the reviewed argv after
   the `fetch()` that checked `"$archive"` against a sha256 (the six original mutants plus archive reassignment and
   indexed array append, plus a fetch moved after installation, are caught), or `fetch()` promotes a checksum-mismatched download;
3. a decoded `$/` reference in `validate.yml` or `publish-catalog.yml` names an action directory that does not exist,
   including single-quoted, double-quoted and comment-suffixed scalars.

Third-party action pinning is already enforced by `tests/test_workflow_hardening.py` (every third-party action is
pinned by a full commit SHA); this PR adds no duplicate. The macOS lock's placement in the frozen group is enforced by
the `tests.test_osv_lockfile_coverage.FrozenScanTests` methods named under group A.

## After the PR lands

Dismiss through `PATCH /repos/{owner}/{repo}/code-scanning/alerts/{n}` (`state=dismissed`), each comment citing this
PR and the record section: 99-107 `won't fix` (A); 108, 109 `false positive` (B1); 91 `won't fix` (B2); 88, 89, 92, 97, 98
`won't fix` (C); 14, 18, 20, 22 `won't fix` (D). Alert 21 stays open. Nothing is dismissed before the PR lands, so the
reviewers read the reasons first.

## SOTA sources

- The existing repository harness at `fbec98e1cba60aa9851c8eca03d194743e3774bd`:
  `tests/test_adoption_bootstrap.py:865` executes the actual Bash functions with local stubs and captures npm argv;
  `tests/test_workflow_policy.py:403` decodes supported workflow YAML and rejects unsupported constructs.
  This correction reuses both implementations without changing the bootstrap or the shared loader.

- `ossf/scorecard@c395761df6afe1a69e476bc60a013a94bcbc153f` (the commit of tag v5.5.0; the tag object is
  `fac1a1678517b7185cd1fa24699a16423fd841d2`): `checks/raw/pinned_dependencies.go:800`,
  `checks/raw/shell_download_validate.go:464-490`, `config/annotations.go`, `pkg/scorecard/scorecard.go:179-190`,
  `pkg/scorecard/sarif.go:673-676`, `checks/raw/code_review.go:55-62`, `probes/codeApproved/impl.go:116-126`,
  `checks/raw/fuzzing.go:131-136`, `docs/checks.md`, `README.md` ("Showing Maintainers Annotations").
- `ossf/scorecard@5fc5c0007101ff4d51ba45da3792463b4a7ba7e7` (`main`, 2026-10-11): `pinned_dependencies.go:806`;
  `ossf/scorecard@bbcee3303b5a8a733d2ffe92fdf4364b2b7c0293` (#5191, 2026-09-28), the fix not yet in a release.
- `ossf/scorecard-action@55891bbd73f2425e97637d96e306fc9d491d0b21` (v2.4.4, 2026-07-23): `go.mod` requires Scorecard v5.5.0;
  `internal/scorecard/format.go:71` writes SARIF through `result.AsSARIF`, which applies the annotation filter.
- This repository's own records: `docs/decisions/2026-09-25-workstation-sota-refresh.md:376-378` (the install "ships no
  shrinkwrap" and ranges resolved after the tag) and `docs/decisions/2026-10-03-currency-wave-w1.md:448` ("does not pin the
  transitive dependency tree").
- GitHub, [self-repository action syntax](https://github.blog/changelog/2026-07-30-reference-same-repository-actions-with-self-repository-syntax/)
  (fetched 2026-10-11) and [finding and customizing actions](https://docs.github.com/actions/how-tos/write-workflows/choose-what-workflows-do/find-and-customize-actions),
  as cited in `docs/decisions/2026-10-09-host-name-scan.md`.
- GitHub REST, [compare two commits](https://docs.github.com/en/rest/commits/commits#compare-two-commits), used for the
  "in no release" check on `bbcee3303`.
- zizmor 1.30.1 `self-repository` audit, reproduced locally on a scratch copy.
- GitHub REST, [dismiss a code-scanning alert](https://docs.github.com/en/rest/code-scanning/code-scanning#update-a-code-scanning-alert).
