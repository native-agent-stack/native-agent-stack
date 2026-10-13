# Decision: pinned awesome-list membership as bounded A3 evidence

This change supplies a deterministic source artifact for community evidence.
It changes no catalog winner, score, runtime, installation or FINAL state.
The counter invokes no model. Coordinator provider usage is unknown.

At base `c63c83a822f2687c3e7aed2d3b3ede0413119c9b`, the layer-resolution
protocol was read before implementation. The foundation's native-clients,
code-navigation, quality-evaluation and agent-SDK decisions retain their
existing choices; durable-memory and observation-inference retain their
comparisons. The Q4 membership-counter evidence layer has no existing layer
verdict or sweep entry. The delta is this named A3 source gap; existing
survivors, comparisons and component adoption remain untouched.

The A3 source layout follows the source kinds in
`catalogs/landscape/angles/schema.json` and the community-proxy boundary in
`catalogs/landscape/angles/README.md` at PR #1058's reviewed source head
`df5f32f790b7672f6e72e62cfb75939e00aee0ef`. The artifact is an A3 **input**,
not a complete `angle-convergence/2` layer record or a convergence verdict.
Its `sources[]` uses committed receipt references; document sources retain
repository, full pin, path and line. No weights or signs are assigned.

## Selection and count contract

The bounded upstream check lasted 194 seconds. None of the inspected tools
provided the full cross-list counter contract. The closest maintained source,
awesome-stars, supplies canonical list-membership hydration. Its crawler and
asset tools report members per list and corpus unions, rather than the
requested per-repository distinct-list count. The counter adds that missing
glue and uses the native GitHub API through `gh`.

`selection.json` retains the six named-list resolutions and twelve source
search receipts: six exact-name searches and six category-extension searches.
Named lists select the highest-star nonarchived exact repository name pushed
within 90 days. Extensions select the top two starred GitHub search results
with the recorded category keywords, at least 1,000 stars and the same push
window. Their `awesome-list` topic restriction identifies curated lists;
searching name, description and README admits broad lists. Overlapping
selection reasons add no list votes. Exact `awesome-codex` resolves to a
small repository; suffix variants are not silently substituted.

Every list uses `Accept: application/vnd.github.raw` at a recorded full ref.
The one extractor removes HTML comments and fenced code blocks, then takes
GitHub repository URLs, including reference definitions, inline code and
image sources. It records the nearest ATX/setext section. For a URL written
on an entry heading, the section is the nearest preceding higher-level
parent; the complete entry line is retained as `entry_heading`. A heading
without a higher-level parent maps to the preamble. Reference definitions
are categorized at their definition location.

Heading-to-category regexes are the one recorded classification judgment.
They were stated before source collection and remain unchanged through the
heading corrections. Parent-section refinement and its chronology are
disclosed separately. Unmatched sections remain uncategorized.

The threshold is three distinct lists per canonical repository across the
selected corpus. Categories require a mapped supporting row; the artifact
reports the number of category-supporting lists separately from total
membership. It retains all supporting list URLs, full commits, file paths,
sections, entry headings and row locations. Duplicate occurrences, files
and aliases cannot add votes within one canonical list.

Canonicalization uses awesome-stars' alias-based 40-repository GraphQL
hydration through `gh api graphql`. Renames resolve to the API's returned
`nameWithOwner`, numeric repository ID and URL. Before the full collection,
the renamed `jeremylongshore/claude-code-plugins-plus-skills` resolved to
`jeremylongshore/tons-of-skills-marketplace`; independent REST returned the
same name and ID. `openai/codex` also agreed. Missing/nonpublic repositories
remain explicit unresolvable records. No credential value is read or
implemented in the counter; the supported installed client owns API access.

Published link values retain only `https://github.com/<owner>/<repo>`.
Unnecessary asset suffixes, query parameters and non-repository HTML locations
are omitted. Source pin/file/line and original source/render hashes preserve
provenance. A sanitization guard verified unchanged repository sets across
all three retained source snapshots; count results stayed unchanged. Combined
URL minimization and native JSON serialization put top-level array records on individual lines, reducing
those three snapshots from 17,965,804 to 9,921,378 bytes. This is an exact
artifact-size comparison, not a provider-token or efficiency claim.

## Cross-check and corrections

Native rendered HTML is a set cross-check, not a second count. Per-list
Jaccard and both differences use normalized requested owner/repo values
before canonicalization. Media types, full refs, source hashes and read
times are retained. Every supported small-file render is remeasured; the
oversized MCP README has no HTML comparison, and is counted through raw.

The first POST `/markdown` attempt returned HTTP 403. Headers and request
size were not captured and remain unknown. That endpoint was not retried.
The supported Contents HTML GET route worked, but the MCP README exceeded
its documented 1 MB source-file bound. A uniform raw route superseded HTML
as the counting input; no local Markdown parser was adopted.

The original HTML adapter excluded links inside heading elements. This
made e2b's overlap 94/109, or 0.862385. Native HTML at the same pin carries
all fifteen missing URLs inside headings. A regression control failed
before the fix. Collecting those `<a href>` values and excluding permalink
anchors restored 109/109. The raw parent-section refinement has its own
fail-before control. `OVERLAP.md` retains every list's before/after overlap.

## Anti-pattern log

| Mistake | Primary evidence and correction | Regression |
| --- | --- | --- |
| Assuming heading elements contain only category text | e2b's pinned rendered Aider entry contains its repository anchor inside h2; include it in the HTML set and omit permalink anchors | Heading-anchor fixture failed before correction and passes afterward |
| Treating a heading entry's project name as category evidence | Use the preceding higher-level parent section and retain the entry line separately | Raw heading-entry fixture failed before correction and passes afterward |
| Applying the three-list threshold to matching-category rows rather than repository membership | The contract counts distinct lists per canonical repository; retain category-support counts separately | Mixed-section three-list fixture failed before correction and passes afterward |
| Using a reserved GitHub surface as a synthetic owner and ignoring preamble offsets | Correct the fixture owner and section offsets; preserve the initial eleven-test failure | Corrected fixtures pass; initial failure remains in attempts.json |
| Retaining ancillary rendered asset locations in a repository-membership receipt | Repository identities plus source pin/file/line suffice; discard non-repository locations and URL suffixes before publication | Two URL-minimization controls failed before correction; identity-set guard and native publication validation verify the sanitized artifacts |

## Publication references

Opaque Git pins and receipt digests live in `identifiers.json`, which contains
only identifier IDs and hexadecimal values, with no repository names.
Named JSON receipts use identifier references instead of full hashes.
`a3.json` refers to lists and documents by ID; `sources.json` maps those IDs
to repository/path metadata and the corresponding identifier references.
The script resolves these tables for offline reproduction. Reference encoding
round-trips every original receipt without changing any count or overlap.

Two publication-shape controls failed before the structural split and pass
afterward: named/count JSON files contain no forty-hex substring, and the
identifier registry contains no repository namespace. Additional controls
check lossless encoding, document-to-list ownership and preservation of
unclassified opaque strings. Only typed public pin/digest metadata approves
relocation; an unknown opaque value remains detectable rather than being
silently moved. The existing native scanner and ignore files are unchanged.
The staged native scan then reports zero findings.

## Reproduction and validation

The committed `corpus.json` contains all returned canonical identities and
the source rows needed for offline reproduction; no network is used by
`build` or `check`.

```sh
python3 scripts/awesome_convergence.py check --directory evidence/artifacts/q4-awesome-convergence-20261013
python3 -m unittest tests.test_awesome_convergence -v
python3 scripts/validate.py
```

For a new public source read, use a new directory so historical attempts
remain intact:

```sh
python3 scripts/awesome_convergence.py select --directory evidence/artifacts/awesome-new-read
python3 scripts/awesome_convergence.py collect-raw --directory evidence/artifacts/awesome-new-read
# Stop and report any measured overlap below 0.95 before continuing.
python3 scripts/awesome_convergence.py canonicalize --directory evidence/artifacts/awesome-new-read
# Supply the reviewed heading mapping, then build the artifact.
python3 scripts/awesome_convergence.py build --directory evidence/artifacts/awesome-new-read
python3 scripts/awesome_convergence.py publish --directory evidence/artifacts/awesome-new-read
python3 scripts/awesome_convergence.py check --directory evidence/artifacts/awesome-new-read
```

Tests are locally authored synthetic fixtures executed with upstream
CPython's unittest harness. Source reads are source_review; offline
reproduction and the independent set tally are local integration checks.
The unchanged upstream counter test suite is not claimed: no fitting
counter was adopted. Actual commands/results and retained failures belong
in `attempts.json` and `checks.json`; structural consistency is not native
runtime, model, GPU or whole-ecosystem acceptance.

## Completeness critic and reopening

The corpus is finite, and extension queries favor broad high-star lists.
The exact-name rule can select a small list; topic tags can omit otherwise
relevant lists. Non-Markdown category sites, directory links and translated
READMEs are outside the retrieval contract. Literal URL extraction can
retain punctuation-bearing invalid targets. Generic headings and unmarked
entry categories reduce category recall, and broad framework/benchmark
sections can contain auxiliary repositories. No individual target's
capability is verified by a heading assignment.

Future sweeps should examine omitted curated-list/tag classes and changes
to pinned list contents. A maintained counter satisfying the full contract
would supersede this glue through its own installation/test path. A change
to the list-selection or mapping judgment requires a new recorded source
read/rule version rather than tuning the frozen corpus to yield more hits.
These counts supply weak A3 evidence and alone cannot select a default.

## SOTA sources

- [cli/cli@fc4b137cdef0a6bd28fd461b7cf9c84a5812a8cd](https://github.com/cli/cli/blob/fc4b137cdef0a6bd28fd461b7cf9c84a5812a8cd/pkg/cmd/api/api.go#L373), installed gh 2.102.0: native API request and GraphQL query interface.
- [subev/awesome-stars@2a86cfbbc9a8eb8de49135c1ddbee4a9e3064bdf](https://github.com/subev/awesome-stars/blob/2a86cfbbc9a8eb8de49135c1ddbee4a9e3064bdf/app/lib/graphql.server.ts#L97), `buildRepoQuery`, requested-name mapping, NOT_FOUND handling and 40-item batches; [crawl.ts:440](https://github.com/subev/awesome-stars/blob/2a86cfbbc9a8eb8de49135c1ddbee4a9e3064bdf/scripts/crawl.ts#L440), canonical membership per list.
- [GitHub REST repository contents](https://docs.github.com/en/rest/repos/contents#get-repository-content), raw/HTML media types, pinned `ref` and source-size bounds; read 2026-10-13T02:41:51Z.
- [e2b-dev/awesome-ai-agents@9596ab1e69fbbb6c95291141c8dab5c181083216](https://github.com/e2b-dev/awesome-ai-agents/blob/9596ab1e69fbbb6c95291141c8dab5c181083216/README.md), heading-entry source and native rendered diagnosis, read 2026-10-13T03:01:30Z.
- [python/cpython v3.13.16 HTMLParser](https://github.com/python/cpython/blob/v3.13.16/Lib/html/parser.py), native HTML extraction interface; [unittest](https://github.com/python/cpython/blob/v3.13.16/Lib/unittest/main.py), the installed harness for the synthetic controls.
- [A3 source layout at #1058](https://github.com/native-agent-stack/native-agent-stack/blob/df5f32f790b7672f6e72e62cfb75939e00aee0ef/catalogs/landscape/angles/README.md), source kinds and community-proxy boundary. That source pin is separate from this PR's base.
