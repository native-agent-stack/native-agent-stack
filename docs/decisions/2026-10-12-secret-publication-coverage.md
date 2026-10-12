# Public-ref secret-scan coverage

Base for qualification: `d8f7e2051b61bde6361a85b64f41413798015353`.
The reproduced predecessor is `9cfe3a964f416080cef914351ddff0502c8bd000` (#949).

## Decision

Use the pinned native Git/Gitleaks paths already selected by #949 to scan
every branch and tag push. The separate `secret-scan-history.yml` also runs
on schedule and manual dispatch; those backstops scan only the checked-out
commit's ancestry. This keeps PR/main validation in `validate.yml` and gives
new public refs an independent history gate without triggering its unrelated
eight-shard suite. Both workflows retain the pinned scanner installations,
redaction, exact generated-explorer exclusion, native timing and status rules.
The history-only backstop runs no working-tree scanner.

Normal pushes retain the available ancestor `before..after` scope. New refs
and verified forced rewrites use `merge-base(origin/main, tip)..tip`, traversing
every parent and emitting merge patches with `--diff-merges=first-parent`.
Unavailable main, unrelated histories, unverified rewrites and empty ranges
fail closed. An annotated tag's exact payload object may peel to the checked-out
commit only for a tag ref. Branch payloads still require the commit SHA itself.
No successful tip-only fallback is permitted.

Commit enumeration uses `git log -s --format=%H`. The explicit `-s` matters:
with merge-diff formatting, Git can emit patches without an explicit `-p`.
The regression uses a non-empty merge tree so patch lines cannot masquerade
as commit identifiers. Scanner traversal still emits the complete patches.

## Reviewed fingerprints reached through merges

The fourteen previously reviewed narrative fingerprints at side commit
`6568523f27e718a86251d041106c53e765a8325d` acquire exact bindings to their
reaching historical merge `9b7a67b98eea708af7b495037c01b3f8f327d558`. This
addresses the known fail-safe replay under the ancestry backstop. It adds
no rule or path-wide exemption.

The PR path can reach the same reviewed bytes under a new merge identity.
Before scanning, the existing event helper writes a temporary native ignore
file containing the reviewed entries plus exact merge-bound fingerprints.
A binding is translated only when native Git proves both source ancestry and
the identical regular-file blob at that path. This reads object metadata,
not file contents. Changed contents, paths, locations and ordinary commits
retain their detection. Missing source objects grant no new exemption.
No global fingerprint is generated. The two real-checkout acceptance scans
consume the same CI ignore path; the live repository ignore file is unchanged
by the temporary translation.

This small composition fills a demonstrated gap in native fingerprint identity:
Gitleaks checks exact commit-bound entries, and its baseline comparison also
requires the same commit. Neither automatically associates a reviewed side-commit
finding with a later merge. The supported fingerprint mechanism remains native;
no detector, scanner parser or secret-value matching is reimplemented.

The native synthetic PR fixture verifies the distinction: reviewed bytes
replayed by a merge scan clean, while a different value at the same file/rule/line
is detected. A global-binding negative control suppressed that later value,
so the global alternative was rejected. The actual historical merge has a
bounded one-commit zero-unsuppressed-findings regression.

## Sources

- [Gitleaks 8.30.1, sources/git.go:74](https://github.com/gitleaks/gitleaks/blob/83d9cd684c87d95d656c1458ef04895a7f1cbd8e/sources/git.go#L74)
  forwards explicit log options to native `git log -p -U0`.
- [Gitleaks AddFinding:711](https://github.com/gitleaks/gitleaks/blob/83d9cd684c87d95d656c1458ef04895a7f1cbd8e/detect/detect.go#L711)
  checks global and exact commit/file/rule/line fingerprints;
  [detect/baseline.go:12](https://github.com/gitleaks/gitleaks/blob/83d9cd684c87d95d656c1458ef04895a7f1cbd8e/detect/baseline.go#L12)
  includes commit identity in its comparison. The installed CLI is 8.30.1.
- [Git 2.53.0, git-log.adoc:130](https://github.com/git/git/blob/67ad42147a7acc2af6074753ebd03d904476118f/Documentation/git-log.adoc#L130)
  documents omitted merge diffs without an explicit format;
  `Documentation/diff-options.adoc` documents `--no-patch`/`-s`;
  `Documentation/git-ls-tree.adoc` describes blob identity and NUL records;
  `Documentation/git-merge-base.adoc` and `Documentation/revisions.adoc`
  define the merge-base, reachability difference and tag peeling used here.
- [GitHub push schema](https://github.com/github/docs/blob/be38ec5d78e24172587e61b3c6ff40ace1865c71/src/webhooks/data/fpt/push.json)
  defines ref and before/after payload fields;
  [branch/tag workflow semantics](https://github.com/github/docs/blob/be38ec5d78e24172587e61b3c6ff40ace1865c71/data/reusables/actions/workflows/run-on-specific-branches-or-tags1.md)
  explains why the old branch-only filter did not cover tag events.
- [Native dated advisory protocol at #1030](https://github.com/seathatflowsinourveins/native-agent-stack/blob/66584736c076873ca7e5898e3bd8111cca1a1447/blueprints/runtime-workers/openhands/evidence/advisory-gate-deltas.md)
  preserves immutable historical bytes while appending each reviewed observation.

## Qualification and limits

The first C1 assertions failed at landed #949: new branch/tag and forced-ref
scopes, non-empty merge enumeration, scanner-equipped regression enrollment,
missing backstop wiring and reviewed-merge replay. Native Gitleaks runs use
runtime-generated synthetic shapes in disposable repositories, including
removed targets over 3 MB. No literal key-shaped fixture is published.
The existing production Bash step and timing writer execute in the fixtures.
Scanner findings stay redacted; checks assert rule/location/count only.

The scanner-equipped job explicitly runs `CiSecretScanMergedHistoryTests`
and the new reviewed-merge tests. Native workflow tests pin install/history
command parity between the publication/backstop workflow and the PR job.
Real hosted scheduled/manual resource measurements remain a follow-up. The
previous +38% merge-patch stream observation is a volume measurement, not
a fresh RSS/time result. Local real-repository scans remain bounded to the
change range or the one explicitly reviewed historical merge; no full-history
local scan runs. Betterleaks 1.8.1 remains the report-only hosted pin; inert
workflow plumbing and the installed 1.9.0 never substitute for native 1.8.1
acceptance.

A later primary result supersedes this decision only through a reviewed,
cited record. A comparison can reconsider the scanner or coverage mechanism
if it reproduces an omitted publication path or yields equal detection with
lower measured cost on these frozen native fixtures.
