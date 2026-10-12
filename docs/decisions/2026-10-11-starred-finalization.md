# Final starred-repository classification

This is the WS1 classified list on main
`333ec47b94e49991271a7ce6b5ed591e24a444d6`, after #978 landed.
The existing convergence manifest remains the single repository list: 373 rows
retain their scope, seed and tier-follow-up links and now carry one of the 13
requested categories, public signals and a KEEP-MIRROR/KEEP/UNSTAR decision.
The existing validator checks these fields; the native decision-index writer
propagates the decision strings. No parallel Claude/Codex practice list is added.

The public-only GraphQL projection was acquired through installed GitHub CLI
2.102.0 between 2026-10-11T16:53:38Z and 16:55:56Z. All 373 repositories were
public and not archived. None had a last push older than its exact 18-calendar-
month cutoff. No evidenced same-category supersession was established. Therefore
this wave proposes **zero UNSTAR actions**, 328 KEEP rows and 45 KEEP-MIRROR
rows. Popularity and licence do not authorize removal or establish a winner.
Missing dependents data is recorded as null with its availability limit; null
does not mean zero. Release histories truncated after 100 entries remain marked
incomplete; absence in that window cannot establish no release.

| Category | Repositories |
| --- | ---: |
| research-skills | 112 |
| sentiment-nlp | 2 |
| north-star-runtime | 7 |
| engines | 10 |
| strategies | 17 |
| market-data | 7 |
| claude-practice | 42 |
| codex-practice | 9 |
| mcp-tools | 21 |
| memory-rag | 34 |
| observability | 13 |
| infra-ci | 66 |
| awesome-lists | 33 |

Categories describe each row's primary discovery role. Existing canonical layer
links remain available for other roles. KEEP-MIRROR preserves reproducible
primary references for recorded mirror roles and selected components; it does
not claim all 45 are mutually comparable winners or qualify new runtime adoption.
Thirty-seven already occurred in the original protected mirror inventory. Eight additional
selected components have their recorded source version resolved to a Git tag or
commit in the retained mirror-pin projection. The skills-ref package's 0.1.0
is a package version, not an upstream tag: its existing source_pin
69ef37e9424c0a7ea9dd2293b559e43ec8176379 is used instead.

The corrected protected projection contains all 373 listed repositories. It
scans 349 tracked sources: 319 at native-agent-stack
`86fa384421b1ca50134bd56d89cc72e0f7547816` and 30 at us-equities-trading
`56e174a20d115996ed2c791e14391c8ea820bb8b`. Both heads were obtained with
`git rev-parse`. The extraction includes URL and bare owner/repo citations in
Markdown decision records and their JSON attachments, workflow `uses:` pins,
and dependency manifests and lockfiles from both repositories. It retains the
first witness per repository per source, with its line, Git head and file hash.
The public mirror projection contains 220 entries, matching 55 listed repositories.
All 373 are conservatively protected because the retained decision attachment
`docs/decisions/memory-adoption-835/g5-grand-catalog-ae6cc228.json` cites the
whole list; 141 also have a mirror, Markdown decision, workflow or dependency
witness. This does not change the 45 KEEP-MIRROR/328 KEEP decisions.

`scripts/starred_protected.py` is the committed producer. It replays the named
Git trees and the embedded public repository/ref mirror projection without
depending on a later working tree or on mutable MIRRORS.json array positions:

```sh
python3 scripts/starred_protected.py --uet-root /path/to/us-equities-trading
```

Dependency package names use conservative normalized repository-basename
matching as well as direct GitHub citations; a name match can overprotect and
is explicitly labelled as a candidate, not an authoritative package mapping.
Different package/repository aliases and missing historical inputs remain
unresolved. The previous capture also missed direct bare-slug citations,
workflow pins and trading dependency pins; that was an extraction defect,
not a transitive-mapping limitation. The corrected capture includes all 32
repositories reproduced by the CC, including actions/checkout workflow pins
and pytest-dev/pytest at trading pyproject.toml:11. **No removal is authorized
in this wave.** Future removal must independently clear the complete protected
set; absence from a bounded capture cannot authorize it. Registered mirrors,
pinned dependencies in either repository and repositories cited by a decision
record are never eligible for UNSTAR.

UNSTAR eligibility in the existing validator requires archived=true, or a push
strictly older than 18 calendar months and a complete public release history
establishing no release in that window, or evidenced supersession by a named
KEEP/KEEP-MIRROR row in the same category. A protected row cannot be removed.
The signal values must equal their repository-bound public capture. Categories,
decisions, observation cutoffs and new mirror pins are checked as data. The
builder's tracked loader includes these dynamically resolved source documents
in the input digest.

## Primary sources and supported mechanisms

- GitHub CLI 2.102.0, `cli/cli@fc4b137cdef0a6bd28fd461b7cf9c84a5812a8cd`,
  `pkg/cmd/api/api.go`, supplies the existing `gh api graphql` interface. Native
  `scripts/build_ecosystem.py --refresh-stars` remains the inventory refresh
  path. No HTTP collector, orchestration runtime or dependency is introduced.
- The public GraphQL repository fields are archived status, pushedAt,
  stargazerCount, open issues, latestRelease and public release timestamps.
  `sources/starred-signals-20261011.json` records the projected values and the
  release-history completeness boundary; account objects and raw responses are
  not retained. `sources/starred-protected-20261011.json` records the protection
  witnesses and source-inventory revisions. `sources/starred-mirror-pins-20261011.json`
  binds the eight new mirror nominations to recorded selected source versions.
- The existing `scripts/starred_convergence.py`, `scripts/catalog_decisions.py`
  and `catalogs/landscape/candidate-quality-review.json` at #978 head
  f1dd19a423888a1f5da6221ae65120d610117753 supply the validation, explicit union
  and evidence-class mechanisms. Existing pins and acceptance limits stand.
- CPython v3.13.16 at cbc944f4bc59639a444dd971c737788ba2283a91,
  `Doc/library/datetime.rst` and `Doc/library/calendar.rst`, supplies aware UTC
  timestamp comparisons and calendar-month day bounds for the 18-month rule.
- The protected-capture correction uses Git's supported tree/blob interfaces,
  verified with installed Git 2.53.0 and the mirror at
  `git/git@67ad42147a7acc2af6074753ebd03d904476118f`,
  `Documentation/git-ls-tree.adoc:55-63` and `Documentation/revisions.adoc:217-223`.
  NUL-delimited tree paths and `<rev>:<path>` bind witnesses to immutable bytes.
  Package normalization follows the PyPA name-normalization specification
  (lowercase and collapse runs of `-`, `_`, `.`); no package resolver is added.
- The README first-install correction follows installed systemd
  259.5-0ubuntu3.4 and the pinned upstream implementation
  [`systemd/systemd@b3d8fc43`, `src/systemctl/systemctl-list-unit-files.c:289-290`](https://github.com/systemd/systemd/blob/b3d8fc43e9cb531d958c17ef2cd93b374bc14e8a/src/systemctl/systemctl-list-unit-files.c#L289-L290).
  An empty filtered result returns -ENOENT. The preflight now lists all unit
  files before the existing timer-state checks, preserving connection-failure
  refusal while allowing an absent first-install timer. The exact source was
  unavailable at that pin in the configured local mirror; its pinned public
  bytes were captured separately. No unit was installed or started.

## Measured verification and execution boundary

The actual README preflight regression fails before the fix with rc 1 when an
absent timer is filtered under set -eu. It passes afterward and also verifies
that an unreachable manager still stops the shell. Native unit syntax/PATH/argv
checks remain in the same module. Four new schema checks initially failed
because invalid categories, changed signal values, protected/recent removals
and licence-based removals were accepted; they pass after extending the existing
validator. Fixtures also cover the exact 18-month boundary and incomplete/recent
release evidence. These are local integration and synthetic policy checks;
they do not measure strategy returns or comparative runtime quality.

For B1, the planted actions/checkout UNSTAR regression was run against the
unchanged c8e7071f capture and validator first: rc 1, one failed assertion and
zero errors because removal was accepted. It passes with the corrected capture
(rc 0), refusing the same removal as protected. Producer fixtures cover bare
and URL citations, a workflow action subpath with a SHA pin, a Python package
pin and replay of a named tree despite a changed working file. No unstar call
or execution path is added.

The PR must land before execution. The CC alone performs the landed UNSTAR list
once, writes the timestamped owner/repository re-star receipt, and registers the
KEEP-MIRROR rows in MIRRORS.json the same day. This wave's empty UNSTAR list must
remain empty at execution. New star events reopen classification instead of
silently appending extra removals. Claude-practice and Codex-practice rows feed
their existing slot catalogs through the normal lane handoff.

REOPEN only on a new star, a new release or archive event of a KEEP-MIRROR
repository, or new primary evidence from WS2. A category without a qualified
comparative winner remains retained discovery; this list invents no winner to
fill it. The original raw public API response from #978 remains unretained.

## Carried validator corrections from #978

The CC assigned three terminal follow-ups to this PR. Each is fixed through the
existing validator and repository identity/pointer interfaces at main
`333ec47b94e49991271a7ce6b5ed591e24a444d6`,
[`scripts/starred_convergence.py:35-58,86-98,145-188`](https://github.com/seathatflowsinourveins/native-agent-stack/blob/333ec47b94e49991271a7ce6b5ed591e24a444d6/scripts/starred_convergence.py#L35-L58)
and `scripts/catalog_decisions.py:93-129`. This extends their recorded policy;
it does not replace the selected CLI, runtime or orchestration mechanism.

- Codex 4242466470: a source_review seed's qualifying pinned URL now declares
  the same normalized owner/repository as the seed. Both github.com/blob and
  raw.githubusercontent.com forms are tested, including accepted case variants.
- Codex 4242466473: a canonical snapshot whose kind is public_starred fails
  closed if convergence_manifest is missing. Legacy fixtures without that kind
  retain compatibility. The regression removes only the manifest field from
  an otherwise canonical-shaped snapshot.
- Codex 4242466476: disposition seed references must cover the entire declared
  seed array, using its canonical JSON pointers. A fully valid unreferenced
  seed fails instead of inflating seed_count. A second case checks separate
  rows for the same repository and accepts them when both are referenced.

Four focused tests produced five assertion failures and zero errors before
the corrections, then passed afterward. The earlier five policy/README checks
also retain their exact-parent fail-before evidence. No pre-existing committed
seed or URL needed alteration. The synthetic tests exercise malformed inputs;
the current committed 373 dispositions and 535 seeds pass the strengthened
validator without claiming upstream execution or runtime selection.

The native monitoring producer sees two additional conservative read locations
from the URL identity and seed-pointer expressions, including the `*#/seeds/*`
shape. The monitoring record is re-derived with its existing GitTree producer
to 334 entries; no enforcement category is added. Its current locator list and
shape values are checked against the final source. Old source_files_sha256
values remain explicitly labelled historical metadata rather than being claimed
as current-file bindings; their separate follow-up is not folded into this PR.
