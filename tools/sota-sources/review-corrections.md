# W1b phase A review corrections

Reviewed base: `a46fce0da2ee009419a1fc291139bc82d054fb06` (#1003).
The Claude first read was recorded by the CC at 2026-10-11T06:08:16Z, SHA256
`45697e23d0a7e9828adc3fa03334cb3ec4c0426fc16051ab123508151f733a25`.

Phase A measures code citations in report mode. An API limitation cannot establish
that a citation is wrong. Compare failures other than 404, malformed or oversize
JSON, and missing comparison fields therefore produce `unavailable`. An unresolved
abbreviated SHA produces `sha-unresolved`, separately from `commit-not-found` for
a full SHA. Both indeterminate statuses exit 3 in enforce mode and 0 in report mode.

The checker resolves the default branch tip once, records its full SHA, and compares
against it on page 2 to avoid the changed-file patches returned only on page 1.
`behind` and `diverged` are counted as `not-on-default-branch:behind` and
`not-on-default-branch:diverged`. They do not establish that a commit is in no history.
By the CC's P2-4 ruling, release-tag comparison heads and a grammar that names the tag
are deferred to phase B. Extended SWHID verification is also explicitly deferred;
phase A keeps those entries `not-checked` rather than implying it verified them.

The default run budget is 64 checked citations and 256 HTTP requests including PR
retrieval and redirects, below a GITHUB_TOKEN's documented 1,000 requests per hour
per repository. Excess citations retain rows marked `not-checked` with a cap reason.
The first primary/secondary rate-limit response stops further requests. Exhausted
request budgets yield `unavailable`. These are local operating budgets, not GitHub
limits. Raw file contents are discarded after computing line count and blob SHA;
directory JSON is reduced to metadata. A renamed API repository keeps authentication
only on HTTPS redirects within api.github.com; other origins never receive it.

## SOTA sources

- GitHub REST API version `2026-03-10`, [Compare two commits](https://docs.github.com/en/rest/commits/commits?apiVersion=2026-03-10#compare-two-commits),
  especially "Working with large comparisons": changed files appear only on page 1;
  status and merge base are comparison metadata.
- GitHub [REST rate limits](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api),
  "Primary rate limit for GITHUB_TOKEN" and "Exceeding the rate limit": continuing
  requests while rate limited may ban an integration. This checker stops rather than retries.
- CPython `v3.12.3`, commit `f6650f9ad73359051f3e558c2431a109bc016664`,
  [Lib/urllib/request.py](https://github.com/python/cpython/blob/f6650f9ad73359051f3e558c2431a109bc016664/Lib/urllib/request.py#L675-L679):
  redirects copy ordinary headers, excluding unredirected headers. Its supported
  HTTPRedirectHandler and request processor seams provide auth scoping and per-hop counting.
- The same CPython pin, [Lib/http/client.py](https://github.com/python/cpython/blob/f6650f9ad73359051f3e558c2431a109bc016664/Lib/http/client.py):
  `putheader` rejects invalid header values with ValueError containing the value.
  The checker strips surrounding whitespace and records a constant safe reason for that error.
- Maintained upstream landscape and exclusions remain the W1b source review's choice:
  `lycheeverse/lychee` at `2bba271688c1abb1503097a064e6c3bc1d1b6a9b`,
  `lychee-lib/src/quirks/mod.rs:23-24` removes GitHub line fragments; it cannot verify
  line ranges. Packages, document liveness and upstream health remain later phases.

## Reproduced evidence and boundaries

The existing unittest harness is the supported local verifier harness. No test uses
the network or a real credential. Before changing the verifier, this command at the
reviewed base, with the new regression module and correction fixture, exited 1:

```text
env -u GITHUB_TOKEN -u GITHUB_STEP_SUMMARY python3 -E -s -B -m unittest tests.test_verify_sources_review -v
Ran 13 tests; FAILED (failures=30, errors=1)
```

The assertion failures include compare 422/incomplete/oversize -> wrong failure,
unresolved 12-hex -> commit-not-found, 5 requests rather than a 2-citation cap,
5 rather than a 2-request cap, 4 requests rather than stopping at the first rate limit,
retained raw contents, undifferentiated ancestry counts, unpinned default tip,
parser mismatches and one counted request rather than two redirect hops. The one
error is the reproduced invalid-header ValueError, not a missing test dependency.
After adding whitespace and redirect-budget coverage, the same tests against the
reviewed verifier and its original request paths produced 15 tests, 32 assertion
failures and that same one error. All 63 verifier/regression tests pass on the local
initial candidate. The final combined repair and its wider controls are recorded below.

Unauthenticated public GitHub requests at 2026-10-11T06:14:37Z reproduced the Linux
root commit's 12-hex 422 and 13-hex successful resolution. The compare endpoint
returned 200 on both pages during our recheck. Its intermittent 422 is reconstructed
from the reviewer's measured observation and labelled `source_review` in
`tests/fixtures/verify_sources/review-corrections.json`; it is not claimed as a raw
capture from this run. Malformed/oversize responses and rate limits are synthetic.
No hosted workflow run or release-tag verification is claimed.

The original PR's "22 of 22" mutation receipt was produced by a scratch `mutate.py`
outside the repository; that mutation list is **not in the repository**. It describes
the original head and is not a reproduced measurement of this correction. The CC's
independent first read reports 15 killed mutations of 16, with the surviving mutation
equivalent. Current evidence is the failing-first regressions above.

#1006 invokes this verifier's report CLI and consumes its Markdown summary; it does
not map or enumerate status names. These status corrections require no matching
PR-B head change. Its own pending review remains separate.

## Combined family findings and adjacent states

Astra FIRST at the same reviewed head has SHA256
`64f840a8405c9647baea83db3b384a9c27fbf4a382c867f65e840d751ea52fb3`.
The four Codex threads cover excessive line numbers, retained raw cache bodies,
matching hex-named mutable refs and HTTP 408. The combined repair additionally:

- Keeps candidate spans and one diagnostic for every unrecognized citation-shaped
  token, even beside a valid citation; SWHID candidates remain explicitly unchecked.
- Bounds numeric tokens before `int`, reports invalid ranges without requests and
  emits JSON/Markdown with report exit 0. It never changes Python's conversion limit.
- Interprets `too_large` only on unsuccessful API error responses. A successful raw
  JSON file containing that spelling is measured as file bytes, not an error envelope.
- Looks up exact heads/tags for abbreviated refs, including original/canonical case,
  before resolution. A matching mutable name is unpinned; indeterminate lookup is
  unavailable. Full SHA resolution and unresolved prefix remain distinct.
- Treats HTTP 408 as unavailable at every request step, following RFC 9110 section
  15.5.9. Invalid authorization values are rejected before fetch/socket construction.
- Reuses one cached default-tip snapshot across citations even if the branch moves.

New-family tests failed on the initial prepared candidate before these fixes:
8 methods, 14 assertions and two reproduced numeric-conversion errors. Against the
exact original verifier with its original endpoints, all eight methods are red:
20 assertions and three errors (two numeric conversions, one absent snapshot field).
Original actual CLI controls reproduce exit 1/zero stdout for a 5,000-digit range
and invalid synthetic authorization, with sentinel exposure only in the latter.
The final verifier suites pass 75 tests, including actual CLI subprocess controls
and a socket guard; no real credential or network is used in these tests.

Call sites checked in the current source: `main` and `pull_request_body` consume
GitHub/get and verify_body; verify_body consumes candidate parsing/verify_citation;
verify_citation consumes ref classification, REST/get, transient/too_large and
compact contents; get consumes urllib_fetch, redirect/counter and content reduction.
The cached/default-tip, compare outcomes, named-ref lookup failures, full-SHA 422,
cache-hit/miss/rate-stop, budget-on-redirect, raw JSON/file/directory/symlink and
report/enforce transitions have offline controls. #1006's CLI/Markdown consumer was
read for compatibility. Graph coverage changed after editing, so current source/AST
and exact call-site reads were used; the old graph is not claimed as complete.

## Retained primary-source packet

The FIX-PUSHED packet names a local attachment directory and its MANIFEST.sha256.
It retains unmodified GitHub REST compare, refs, contents, git-commits, API-version,
breaking-change and rate-limit pages; RFC 9110; pinned CPython, Linux, lychee,
ECMAScript and GitHub OpenAPI blobs; pinned repository grammar mirrors; both original
family verdicts, Codex threads and synthetic/native proof receipts. Installed
CPython 3.13.16 http/client.py matches Astra's hash
`d12e0060428b8389389db2244f9e1bd7fccae1450d43f74bce91b782498c300a`.
The packet's SOURCE-INDEX.json maps filenames to URLs/pins and evidence classes.

The original trimmed fixture is a replay input, not an authenticated original HTTP
capture. Fresh unauthenticated prefix-resolution/ref-absence bodies are retained
separately with their capture statuses. The earlier intermittent 422 reconstruction
remains source_review; no claim of reproducing that live limitation is made. The
original scratch mutation list is not republished as evidence of the final repair.
