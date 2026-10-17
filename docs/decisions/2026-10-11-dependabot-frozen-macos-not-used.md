# Dependabot alerts 18–23: inactive frozen macOS dependency evidence

Status: proposed disposition; alert state remains open until this record lands
and the command center's read passes. Owner: github-ci-finalize.
Reviewed source: native-agent-stack@77185991ec9627e59473df5b4d7a11ca87b0461d,
a fresh main checkout after PR996 landed. Observation date: 2026-10-11 UTC.

## Alerts and proposed disposition

The authenticated, read-only Dependabot API observation returns six open
alerts: one high, four medium and one low. All name npm package next in
`evidence/artifacts/macos-application-20260924/variant/package.json`,
which records next 16.3.5. The proposed dismissal reason is `not_used`,
individually for the six alert numbers below.

| Alert | Severity | Advisory | API first patched version |
| --- | --- | --- | --- |
| 18 | high | GHSA-cjq9-62q9-8jv4 | 16.3.8 |
| 19 | medium | GHSA-mcj8-r9mp-w47p | 16.3.8 |
| 20 | medium | GHSA-f87g-xv8r-7p7x | 16.3.8 |
| 21 | low | GHSA-39w2-rjm5-chcv | 16.3.8 |
| 22 | medium | GHSA-4jqv-mc3x-m676 | 16.3.8 |
| 23 | medium | GHSA-3w37-wq28-93x7 | 16.3.8 |

The package remains vulnerable at its recorded version. This is an inactive
artifact disposition, not a version fix, a false-positive classification or
permission to install it. No blanket dismissal covers future alerts or a
different input path.

## Input identity and current consumption review

The variant contains exactly two tracked files, both bound by
`manifests/evidence.json` at the reviewed main commit:

| File under the variant | Bytes | SHA256 |
| --- | ---: | --- |
| package.json | 792 | 02becfe07513621c35367d1cd703d2ba2fb5965eb6b719790e040a0a70295ddc |
| pnpm-lock.yaml | 32972 | f1c707b8295e85bd396e49b990de92dc82bc0d58eca1e4e4bef31262d9898cd2 |

At that exact commit, the following native Git searches were retained with
commands, exit codes, counts and output hashes. Counts are matching lines,
not installer counts.

| Search at the reviewed source | Matching lines | Result after inspection |
| --- | ---: | --- |
| git grep -n -I -F full variant path | 131 | Historical captures, records, inventory, scans and tests |
| git grep -n -I -F macos-application-20260924 | 192 | Parent-name coverage includes assembled parent/variant references |
| Full path in scripts, tests, tools, adoption and .github | 12 | Ten configuration/scan references and two test references |
| Full path in scripts, tests, tools and adoption | 2 | Both in tests/test_osv_lockfile_coverage.py; no installer |
| npm ci/install in .github/workflows | 3 | One comment and two command-shape assertions in validate.yml |
| Installation/traversal candidate search in those maintained scopes | 84 | No consumer of the frozen variant found |
| git ls-tree -r --name-only for the variant | 2 | package.json and pnpm-lock.yaml only |

The 12 maintained references are exhaustively located in:
`.github/dependabot.yml` (2), the retired
`.github/osv-scanner-frozen-macos.toml` (3),
`.github/osv-scanner-lockfiles.json` (3),
`.github/workflows/frozen-evidence-risk.yml` (1),
`.github/workflows/security-scan.yml` (1), and
`tests/test_osv_lockfile_coverage.py` (2).
They select or verify dependency metadata; they do not install dependencies.

The two workflow npm invocations are indirect through reviewed command pins:
`examples/claude-native/workflows/shell-parser.pin.json` installs the pinned
web-tree-sitter/tree-sitter-bash packages, and
`tools/sota-convergence/landscape-sweep/skills-yaml.pin.json` installs yaml.
Both use a new runner-temporary prefix. Neither uses this variant manifest
or lock. The Linux/macOS adoption bootstraps install explicit reviewed
tarball inputs from their pin records, not a traversal of evidence manifests.

The maintained application Makefile's pnpm install runs from
`blueprints/convergence-practice/application-delivery`, with its own manifest
and lock. That manifest currently records next 16.3.8, the API's first patched
version for all six listed advisories. It does not import the frozen variant.

Historical qualification did install and run a scratch copy containing the
variant bytes. `experiment-macos-20260924.json` and the application's README
explicitly record that separate scratch execution and its rollback. This
record does not claim that the bytes have never been executed. The reviewed
current checkout has no maintained workflow, script or test that installs,
builds or serves from the frozen artifact path.

## Existing tripwire and limits

The existing `tests/test_frozen_macos_variant_no_use.py` suite passes its
ten tests. Its tracked-source scan sees 12,477 entries and finds 82
parent-name reference lines in 28 scanned files, all matching the existing
reviewed line pins. It watches the whole artifact directory, checks the two
frozen dependency files and refuses new direct references in its stated scope.
The separate frozen inventory/digest/eligibility tests also remain required.

This reuses an established guard; the PR adds no scanner, tests, exceptions,
workflow changes or new pins. The guard is a bounded direct-reference
tripwire, not a universal reachability proof. Its documented limits include
glob/inventory traversal, names assembled from fragments, outside-repository
inputs and some record/configuration classes. Current candidate-install
searches and source review supplement it at the named commit. A manually
copied artifact or a future consuming route requires a new review.

The existing 2026-10-07 frozen-evidence reporting decision remains in force:
frozen advisories are reported unsuppressed by the separate report workflow;
ordinary required scans keep their live inputs and policy. Dependabot's
version-update ignore entry does not dismiss these alerts. The current
inactive-policy review bound is 2026-12-24; recheck this disposition at that
bound, on a guard failure, changed bytes or before any consumer is introduced.

## Approval and API action after landing

This PR changes this record only and dismisses no alert. After it is merged
and the command center's read passes, re-read each alert and confirm its
number, open state, advisory identity, package and exact manifest path.
Reconfirm no consuming route was introduced. Then update each of 18–23
individually through GitHub's supported endpoint with:

- state: dismissed
- dismissed_reason: not_used
- dismissed_comment: a short reference to this record and its landed PR,
  identifying inactive frozen dependency evidence.

GitHub's API limits the comment to 280 characters. Retain each observed
response and read back the six states. If any input or use differs, stop
that dismissal and follow the pinned-dependency upgrade practice instead.
Reopen the affected alerts and enter required vulnerability coverage before
any install, build, serve or replay of these bytes.

## Evidence and sources

The hashed attachment packet named in the PR body retains the exact-base Git
search outputs, alert API projection, source blobs, GitHub documentation,
input hash bindings and actual validation logs. Source review, historical
receipts and current execution are kept distinct.

- [GitHub: viewing and updating Dependabot alerts, dismissal section](https://docs.github.com/en/code-security/how-tos/manage-security-alerts/manage-dependabot-alerts/view-dependabot-alerts#dismissing-dependabot-alerts).
  Pinned github/docs@be38ec5d78e24172587e61b3c6ff40ace1865c71,
  content/code-security/how-tos/manage-security-alerts/manage-dependabot-alerts/view-dependabot-alerts.md:115-128:
  assessed open alerts can be dismissed with a reason/comment and reopened.
- [GitHub REST: update a Dependabot alert](https://docs.github.com/en/rest/dependabot/alerts?apiVersion=2022-11-28#update-a-dependabot-alert).
  Pinned github/rest-api-description@58b1e0c00b39b9e46c24dc4a0ba6a2669c90e9c1,
  descriptions/api.github.com/api.github.com.json,
  /repos/{owner}/{repo}/dependabot/alerts/{alert_number} PATCH:
  state, dismissed_reason (including not_used) and dismissed_comment.
- Repository@77185991ec9627e59473df5b4d7a11ca87b0461d:
  manifests/evidence.json (two exact file bindings),
  tests/test_frozen_macos_variant_no_use.py (scope/limits and existing guard),
  tests/test_osv_lockfile_coverage.py:92-105,603-624 (frozen identity/eligibility),
  docs/decisions/2026-10-07-frozen-evidence-osv-reporting.md (current policy),
  application-delivery/README.md:178-191 and experiment-macos-20260924.json
  (historical scratch execution).
