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
At 20eac579 the verifier suites passed 75 tests, including actual CLI subprocess controls
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

## Follow-up micro at 20eac579

Recognized occurrences are emitted individually, including duplicates and citations
joined without whitespace. Only leftovers continuing the citation grammar invalidate
a match; ordinary punctuation and Markdown link suffixes preserve it. Invalid
candidates retain diagnostics. Repository/package pins have a distinct unchecked
reason, all rows use the same candidate_span key, and spans index the entry text.

The parser controls exercise both AT and URL forms after every ASCII punctuation
character and every Unicode punctuation character in the interpreter inventory,
except the reserved continuation markers (#, / and @), which have explicit negative
controls. At CPython 3.13.16 this is 848 characters per form (Unicode 15.1.0), plus
mixed-form comma/semicolon/dash/pipe/word joiners and the common `[label](URL): text`
layout. The complete current 14-method micro suite against 20eac579 is red:
10,120 assertion failures, zero errors, with 13 methods exposing regressions and
the grammar-continuation negative control passing. It covers 12 supported grammar
spellings (single/range/shorthand anchors, columns/plain query, host/ref case,
short/full refs and URL underscore wrapping) across all 848 punctuation characters.
The initial narrower 12-method run was 1,710 failures/zero errors. Additional ASCII
hyphen joiners exposed an atomic-URL/AT-neighbour boundary before its correction.

The integer conversion citation is
`python/cpython@f6650f9ad73359051f3e558c2431a109bc016664:Include/internal/pycore_long.h:L29`,
`#define _PY_LONG_DEFAULT_MAX_STR_DIGITS 4300`; captured header SHA256
`84c0c7bd7ba0c2fbbfb106561e32328e478d8350afe756af6a4862c95d921a06`.
Zero padding is normalized before the file-size bound, and SHA policy again precedes
range classification. Unfollowed 3xx and ordinary 403 responses are indeterminate.
The subsequent CC micro found that explicit contents `too_large` refusals need
precedence over generic 403 classification. The original 403 fixture is restored;
422 is only an extra synthetic classification control, not a documented contents
response. Successful transport-oversize controls remain distinct.

Successful JSON request caches retain only fields consumed by the commit/reference,
comparison, repository and PR-body callers; large commit messages and unused arrays
are released. Endpoint dispatch is relative to the repository identity, preventing
a repository named compare or pulls from selecting the wrong reducer. That adjacent
boundary failed twice before its correction. Owner/repository case aliases share
keys and one default tip; ref and path spelling retain their case. GitHub's captured
authentication documentation classifies insufficient permission and failed-login
responses as indeterminate and warns about repeated invalid-auth requests. After a
401 the client stops subsequent and previously cached requests, as after a rate limit;
the new 401-stop control failed once before that additional correction.

Budget measurement (synthetic, not a live quota claim): 70 abbreviated citations in
70 fresh repositories take eight requests each until the 256-request cap binds;
the replay yields 32 ok, 32 unavailable and six not-checked. The citation cap does
not bind first in this workload. Different cache reuse/ref spelling changes costs.

Committed-module provenance replaces reliance on intermediate receipt counts. We
re-executed the exact 20eac579 test modules against the exact a46fce0d verifier,
including actual CLI subprocesses in an isolated scratch tree, with the older compare
URL explicitly adapted to the recorded SHA/page-2 fixture route:

| Committed 20eac579 module | Tests | Failures | Errors |
| --- | --- | --- | --- |
| test_verify_sources | 48 | 6 | 0 |
| test_verify_sources_review | 15 | 35 | 1 |
| test_verify_sources_family_findings (local comparison-route adapter) | 12 | 28 | 8 |
| test_verify_sources_family_findings (unadapted) | 12 | 29 | 7 |

The CC's micro independently reports 38F/1E (unadapted), 35F/1E and 29F/7E.
Fresh isolated replay of the exact sources gives the family module **29F/7E
unadapted**, and **28F/8E with our explicit local comparison-route adapter**.
The existing module gives 38F/0E unadapted and 6F/0E adapted in that replay.
Thus the family row above is retained only with its precise adapter scope; the
CC's report that both scopes give 29F/7E is not reproduced by this adapter.
The complete replay uses 20eac579's test fixtures and exact a46fce0d production source.
It and the original receipts are retained. No aggregate count authenticates
an individual fix without an intended assertion or a separate CLI reproduction.
Router/missing-field errors are not
presented as an intended failing assertion for a fix; individual permanent controls
and actual CLI proofs establish those defects. The retained packet records scope.

Astra's complete micro has SHA256
`7185960587ed5ee270235c3488cdae16f3f24791455aa4db6b268cc9ccd9a245`.
Its case-alias/moving-tip P2 overlaps the Codex identity thread and is repaired by
normalizing repository components before path construction and cache lookup, while
preserving citation display and case in refs/file paths.

Wider identity controls cover each SHA/JSON/raw-media cache key, URL spellings and
redirect/rename aliases. Once repository metadata establishes its numeric id and
full_name, existing keys migrate to that id; later aliases reuse the first metadata
and tip snapshot. No undocumented id-based request route is used: numeric ids are
internal cache identities, and requests keep documented owner/name endpoints.
The case and moving-rename controls fail on 20eac579 with intended ancestry and
snapshot assertions. Exact replay of both the original 17e6789c learned-cache-key
fixture and the 82c86da6 fixture against 20eac579 reaches the intended **9 != 5**
request-count assertion, one failure and zero errors. The intervening statement
that the original failed through an unrouted metadata request was incorrect.
The separate case/URL-form preservation test (then test_verify_sources_micro.py:296)
instead fails at 20eac579 through an unrouted mixed-case commit request. It is a
post-fix preservation control, not claimed as an intended ancestry/cache fail-before.
Existing same-origin/foreign-origin redirect and hop controls still apply.
The public lychee metadata and .git-suffix recheck are retained: canonical200,
suffix metadata404 and suffix blob404. Thus .git is not stripped or conflated absent
API identity evidence; distinct repository names/ref/path case keep distinct keys.

The packet closes prior authentication gaps: #1006's source-citations-report.yml
is retained byte-exact at bd9d46f54b93fa8eb42a3caeb5e5dc651ce8ea6b, SHA256
`769cc256339d0ed7a1e065dea3348393488585a70b7a2223dc7524845fe965ed`;
fresh unauthenticated SHA-media responses bind CPython v3.12.3 and lychee-v0.24.2
to the two cited full commits. These are fresh mappings, not reconstructed originals.
The final combined verifier suites pass 92 tests without skips on both interpreters,
and the surrounding harness passes 123 without skips. Historical/intermediate
measurements above remain labelled by their exact scope and head.

## CC micro at 17e6789c: size precedence and visibility

The next forward repair restores the documented HTTP 403 size-refusal fixture and
checks unsuccessful contents `errors[].code == "too_large"` before generic transient
classification. The pinned OpenAPI is
github/rest-api-description@58b1e0c00b39b9e46c24dc4a0ba6a2669c90e9c1:descriptions/api.github.com/api.github.com.json:L55991-L56059:
contents lists 200, 404, 403, 302 and 304, not 422. A size refusal was not observed
live; these remain synthetic controls. Successful error-shaped raw JSON is still
file content. A size refusal that also identifies a rate limit preserves the run's
stop state; remaining rows cannot send requests or reuse cached results.

Commit-resolution, git-commit, contents and compare 404s now probe cached repository
metadata before they establish failure. A second 404 means `unavailable`, with
"repository not visible to this token". A successful visible-repository probe
preserves the established missing-resource status; malformed metadata, auth,
rate-limit and transport failures remain indeterminate. This also addresses Codex
thread 4241381563 at the same head. GitHub's primary troubleshooting page, "404 Not
Found for an existing resource", explicitly documents concealing private resources.
Its retained original page has SHA256
`2fd859cca1eaff6fce3d3c4f35ace570dc91acbb228a823beaa9ebbe6617f1c0`.
No inaccessible repository or credential was inspected to test that behavior.

Unsupported numeric continuations using U+2010 through U+2015, U+2212, comma or
tilde retain an explicit diagnostic, rather than checking only the first line.
An isolated dash or dash followed by prose remains punctuation; adjacent citations
joined by those characters still each receive a row. The cap and docstrings now
state that recognized occurrences, including repetitions, consume the budget.

Exact fail-before replay at 17e6789c gives four methods with **41 intended assertion
failures and zero errors**: explicit 403 size (one), initial hidden 404 (two),
unsupported ranges (36), and later hidden 404 (two). The corrected learned-alias
fixture at 20eac579 gives **9 != 5**, one intended assertion failure, zero errors.
Receipt-only changes correct misleading historical scope; no manufactured test of
Markdown wording is claimed as behavioral regression coverage.

One-step-wider checks enumerate HTTP 100 through 599 at every reachable REST step,
plus both contents envelope forms, explicit size/rate-limit stop, successful raw
JSON, transport/request-cap states, visible/invisible metadata and parser punctuation
and joiners. Codes outside the documented endpoint set are synthetic order controls.
Optional 405/409/410/451 semantics and repository-pin grammar remain deferred.

The production callers are `main -> verify_body -> citation_candidates/verify_citation`,
`verify_citation -> repository_visibility/too_large/transient`, and REST/PR retrieval
callers of `transient`. Graph coverage was checked; edited-file freshness changed,
so exact current source/AST and the executable controls verify these relationships.
#1006's pinned workflow still consumes CLI/Markdown without status-name mapping:
the visibility correction changes outcomes but requires no matching head change.

Current proof packet:
`~/.local/state/native-agent-stack/coordination/ns2604-coop/lanes/currency-work/pr1003-403-fix-20261011/attachments/`.
It retains all cited sources byte-exact under `prior-packet/`, new troubleshooting
capture, original CC micro, current threads, fail-before replay and precise baseline
table scopes, with a complete `MANIFEST.sha256`. Prior sealed packets are unchanged.

## Final adjudicated repair at 82c86da6: bounded report rows

Codex 4241763767 and the CC's final-round ruling identify repeated paragraph text
in unlimited diagnostics and recognized-occurrence rows. MAX_ROWS now permits
256 data rows plus one exact omitted-count row, covering diagnostics and
candidate-free entries as well as recognized occurrences. Omitted rows cannot
send requests and are indeterminate: report mode remains advisory, while enforce
returns 3 unless an established failure already requires 1. MAX_ENTRY_CHARS and
MAX_ROW_FIELD_CHARS retain at most 1,024 characters per display string with an
ellipsis/note. Spans describe the original input; display truncation never changes
verification or the 64 recognized-occurrence/256-request budgets.

The encoder mechanism is python/cpython v3.13.16 at
cbc944f4bc59639a444dd971c737788ba2283a91:Lib/json/encoder.py
(_iterencode_list and _iterencode_dict). It serializes each repeated row value;
the local report budgets prevent that amplification before serialization rather
than claiming a vendor-defined row limit. JSON records every limit and the exact
omitted count; Markdown exposes those limits and separates omissions from checked
citations. No grammar, HTTP classification, compare or cache mechanism is replaced.

Seven permanent row-budget methods replayed on exact 82c86da6 produce six intended
assertion failures and zero errors; the exact-boundary preservation method passes.
The actual CLI's 1,000-token malformed paragraph serializes 6,557,147 bytes before
the fix and violates the 30,000-byte test ceiling. The corrected fixed-budget
controls cover diagnostics, repetitions, candidate-free entries, display strings,
the existing citation budget and actual CLI limit metadata. They also establish
that omitted work remains indeterminate and sends no additional requests.

The first local harness invocation had a wrong keyword for run_main and produced
one test-harness error; it is excluded from defect evidence. The corrected replay
above uses the helper's supported environment argument and artificial empty tokens.
The receipt-only correction above follows exact original/current fixture replay;
no manufactured Markdown-wording test is claimed. Wider joiners, the compare clause
and optional occurrence-wording refinements remain PR-body Follow-ups under the
CC's final adjudication.
