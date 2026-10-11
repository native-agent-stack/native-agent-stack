# Public starred repositories: recorded dispositions and weekly intake

The public star inventory dated October 8 had 368 rows whose disposition was PENDING. The October 10 public acquisition returned 373 repositories, including five new identities. The earlier S2 source review and seed intake had not been written back to the catalog, and the ecosystem explorer overlaid an older 343-repository landscape capture even when the canonical public-star snapshot was newer.

This change refreshes the canonical snapshot through an explicit mode of the existing ecosystem builder. The resulting snapshot records 373 evidence-backed dispositions: 315 in scope, 58 out of scope, zero PENDING. Every in-scope row points to its canonical layer and one or more of 535 concrete rows in [the dated seed manifest](../../catalogs/convergence-practice/starred-seeds-20261010.json). Those rows feed research/adjudication; they are not adopted winners. The [convergence manifest](../../catalogs/convergence-practice/starred-convergence-20261010.json) is explicitly registered in the existing repository decision union.

The five additions are HKUDS/nanobot, astral-sh/ty, languagetool-org/languagetool, microsoft/playwright and microsoft/pyright. Their [pinned source review](../../catalogs/convergence-practice/starred-source-review-20261010.json) establishes runtime, type-checking/language-service, proofreading and browser/testing roles and feeds seven seed rows. Four lacked a prior S1 seed; this change creates the actual source-bearing seed rows that close that link. The other 368 decisions join recorded S2/S1 seed witnesses and current public metadata; they do not claim the same pinned README review. Eight descriptions/topics changed without changing their documented scope roles. The repository snapshot reports zero archived repositories; no superseded status is invented from a fork flag or age.

Each in-scope row carries verdict_refs and an explicit verdict_follow_up for tier-1/tier-2. The current committed wave registry contains no matching explicitly tier-labelled rows for these seeds, so the follow-up remains AWAITING-RECORDED-TIER-VERDICT. A future recorded tier must supply a matching repository/tier pointer; the validator rejects dangling or invented verdicts. NEEDS-EVIDENCE is the explicit weekly default for a new repository until a lane records its scope evidence. This change makes no new installation, comparative SOTA, benchmark or runtime acceptance claim.

## Supported sources and implementation choice

- [GitHub REST: repositories starred by a user](https://docs.github.com/en/rest/activity/starring#list-repositories-starred-by-a-user) specifies the public users/{username}/starred route and pagination up to 100 per page. Acquisition uses the endpoint already recorded in public-starred.json, filters nonpublic entries before persistence, and retains only the existing repository metadata allowlist plus explicit derived review fields. Account/user objects, credentials and raw failure output are not retained.
- [GitHub CLI v2.102.0](https://github.com/cli/cli/blob/v2.102.0/pkg/cmd/api/api.go), the installed CLI version, supplies the maintained fetch/pagination implementation. Its --paginate flag visits all response pages and --slurp returns an outer array of page arrays. The change extends the repository builder with that interface and adds no HTTP client or dependency.
- Native systemd 259.5-0ubuntu3.4 matches [systemd v259.5 at b3d8fc43](https://github.com/systemd/systemd/tree/b3d8fc43e9cb531d958c17ef2cd93b374bc14e8a). man/systemd.timer.xml defines OnCalendar, Persistent and the paired Unit; man/systemd.time.xml defines weekly. man/systemd.service.xml documents the ':' ExecStart prefix disabling environment-variable expansion, and man/systemd.syntax.xml documents quoted UTF-8/C escapes. Percent specifiers are escaped separately. [man/systemd.exec.xml](https://github.com/systemd/systemd/blob/b3d8fc43e9cb531d958c17ef2cd93b374bc14e8a/man/systemd.exec.xml) defines the service's `Environment=` and specifier expansion; [man/systemctl.xml](https://github.com/systemd/systemd/blob/b3d8fc43e9cb531d958c17ef2cd93b374bc14e8a/man/systemctl.xml) supplies the documented install/inverse lifecycle commands.
- Existing repository templates at main 0947b012, [stack-currency.service](../../adoption/templates/systemd/stack-currency.service) and [stack-currency.timer](../../adoption/templates/systemd/stack-currency.timer), establish the timer-triggered user oneshot convention. The stars service extends the sibling's explicit CLI PATH with `%h/.local/share/mise/shims`, the installed host's `gh` location. [The new renderer](../../tools/starred-maintenance/render_units.py) supplies the actual live clone path and external state/questions paths without committing rendered host paths.
- Installed [jdx/mise v2026.10.3 at 33a839a4](https://github.com/jdx/mise/tree/33a839a4d19acca617bc9ec0fe53f61266d60a9d) documents `mise activate --shims` as adding `$HOME/.local/share/mise/shims` to PATH in [src/cli/activate.rs:63-72](https://github.com/jdx/mise/blob/33a839a4d19acca617bc9ec0fe53f61266d60a9d/src/cli/activate.rs#L63-L72). Its [official shims guide:71-80](https://github.com/jdx/mise/blob/33a839a4d19acca617bc9ec0fe53f61266d60a9d/docs/dev-tools/shims.md#L71-L80) requires separately launched applications to receive their own environment setup. The installed `mise --version`, `mise activate --help` and `mise activate --shims bash` agree on the version and directory. This uses the measured Unix default; custom mise/XDG shim locations require an adjusted unit PATH.
- Installed Python 3.13.16 follows [CPython v3.13.16, Doc/library/subprocess.rst, Exceptions](https://github.com/python/cpython/blob/v3.13.16/Doc/library/subprocess.rst#exceptions): launching a missing executable raises an OS error. `_fetch` now translates `FileNotFoundError` into the explicit `GitHub CLI (gh) was not found on PATH` validation error. The builder's existing error handler reports it with exit 1; raw CLI failure output remains excluded.
- The existing [catalog decision union](../../scripts/catalog_decisions.py) provides safe JSON pointer and repository identity handling. The stars convergence validator reuses these helpers and registers its explicit source array through the supported --supplement interface.

Primary-source correction: scripts/build_ecosystem.py at main 0947b012 had no network acquisition mode. Its original default remains offline; --refresh-stars is an explicit extension. Current snapshot authority is decided by parsed UTC observation times, so the older landscape snapshot cannot erase newer canonical stars. No historic landscape capture or verdict wave is rewritten to achieve that correction.

PATH correction at c7a4603b: copying the sibling's PATH did not make the installed `gh` reachable. Native systemd verification parsed that PATH successfully, but `shutil.which("gh", path=parsed_path)` returned no executable and a real `gh --version` raised `FileNotFoundError`. The earlier fixture only proved lookup of its planted executable. The service now includes the documented mise shims directory, and the native regression uses the actual installed CLI.

## Maintenance and validation

Run the one-off reviewed refresh through the builder:

```sh
python3 scripts/build_ecosystem.py --refresh-stars \
  --starred-output catalogs/convergence-practice/public-starred.json
```

For upkeep, render the weekly units with the actual live clone and external state/questions paths as documented in [starred maintenance](../../tools/starred-maintenance/README.md). The README supplies post-landing installation/update and inverse steps that save the previous files and timer state, check installed digests before restoration, and restore the previous enablement. The scheduled mode writes an external snapshot and durable notification journal, then appends ## NEWSTARS followed by the unresolved new-star count to the lane's questions. It never commits, pushes or changes the live tracked catalog. A lane records the sources and dispositions in a small PR. Canonical reviewed fields take precedence over prior scratch fields, and a durable prepared journal replays a notification if an append failed before another refresh.

PENDING age follows first_observed_at, falling back to the retained observation date for legacy rows. Fetching a new snapshot cannot reset it. Both ecosystem building and FULL publication validation reject a PENDING row older than seven days. Malformed or future timestamps fail closed. This age rule does not misrepresent an explicit NEEDS-EVIDENCE source gap as a settled decision.

Fail-before evidence: two builder regressions initially failed assertions because an eight-day-old PENDING row and the same row under a fresh snapshot were accepted. A third initially failed because an older empty landscape capture removed a current canonical star. The fixed paths pass these cases. Public API fixture tests cover pagination/private-field exclusion, canonical review authority, first-observation preservation, and write-success/append-failure recovery. Convergence tests reject broken seed/layer joins, missing follow-up and fabricated verdict pointers. Native systemd verification checks staged units and special-path arguments without installing or starting them. At c7a4603b, the new renderer PATH assertion and updated native environment test both failed because the mise shims directory was absent; the missing-CLI regression raised `FileNotFoundError` in both canonical and external-state modes. All three pass after the correction. The native test parses systemd's expanded PATH, asserts the shims directory and runs real `gh --version` with only that PATH and the actual user home; it plants no executable and makes no API request. A separate renderer assertion runs even where systemd or gh is unavailable. The missing-CLI test uses a real empty search path and verifies that a fresh refresh leaves canonical snapshots and questions unchanged and creates no snapshot or notification journal.

Native acquisition returned 373 public allowlisted repositories and exactly the five additions above. Source review remains source_review; refresh and scratch unit verification are actual local execution. Live weekly timer execution remains untested until the post-landing CC installation cue. No host unit is installed or enabled by this PR.

The choice would be overturned by a maintained upstream snapshot/notification facility that natively supports the same public-only metadata, durable source-backed review links and external-state co-op intake with reproduced evidence. Until then, the supported GitHub CLI, systemd timer and existing repository builders provide the mechanisms, with small repository policy glue for the measured gaps.

## Retained provenance and review corrections, 2026-10-11

The pinned acquisition interface remains GitHub CLI v2.102.0. Its installed
pagination and error boundary, systemd v259.5 unit parsing, and mise v2026.10.3
shim directory are unchanged mechanisms. The maintenance README now documents
the actual installed-CLI verification; the former planted executable is marked
as historical evidence. No live timer or weekly network execution is claimed.

The notification fixes extend the existing repository journal at
`scripts/public_starred.py` in `6b91bb7166280a544280cd35f6961ccb4c571e97`.
They use CPython v3.13.16's documented
[SHA-256](https://github.com/python/cpython/blob/cbc944f4bc59639a444dd971c737788ba2283a91/Doc/library/hashlib.rst),
[sorted JSON encoding](https://github.com/python/cpython/blob/cbc944f4bc59639a444dd971c737788ba2283a91/Doc/library/json.rst),
[aware timestamp comparisons](https://github.com/python/cpython/blob/cbc944f4bc59639a444dd971c737788ba2283a91/Doc/library/datetime.rst)
and [atomic file replacement](https://github.com/python/cpython/blob/cbc944f4bc59639a444dd971c737788ba2283a91/Doc/library/os.rst).
The journal retains unresolved public observations even when a repository leaves
the latest live response. Canonical review clears work; a retained per-repository
generation and canonical review fields distinguish reopened work. Notifications
include repository identities, and retries deduplicate the same generation.
The previous snapshot also recovers new work if execution stops before the first
journal write. Each containing snapshot bounds its rows' first-observation times;
a later validation clock cannot legitimize a newer row timestamp.

All 528 historical seed joins now point into the committed, byte-identical
`sources/master-seeds-20261010.json` capture (SHA-256
`4a62af4ca834d6170e24d511f4982dc864d1b15502534733cd3fe9cf2cc633ad`).
Their evidence class is `metadata_seed_review`; the seven seed rows for the five
new repositories retain `source_review` with pinned upstream URLs. Validation
checks each historical string's hash, repository identity, layer/index locator
and master-capture hash. It rejects metadata-only references labelled as pinned
source reviews. This supplies reproducible historical discovery evidence without
claiming upstream source review for all 368 older repositories.

Every dynamically resolved evidence document receives the same public-field
scan as the initial manifests. Grand Catalog discovery witnesses use a narrow
public projection in `sources/grand-catalog-public-witnesses-20261011.json`,
retaining repository identity, pin, source commit/hash and original row pointer.
The broader catalog's workflow-assignment fields are excluded. A complete pair
of tier verdicts requires the awaiting follow-up to be removed from both the
manifest and snapshot.

The review packet retains the five new repositories' cited upstream files,
implementation sources, resolved release tags,
the original new-five metadata/pin record, the master seed, and the historical
baseline index/audit/templates in a separate `sources` directory with
`MANIFEST.sha256`. All twelve new-repository file hashes and Git blob identities
are verified against fetched bytes. The REST documentation is a current official
capture with the 2022-11-28 selector. The original raw public API response was
deliberately never retained; the allowlisted catalog and its native writer
reproduction are the acquisition evidence. Reacquired source bytes and tag
resolutions are distinct from the retained 2026-10-10 metadata observations.
Historical citations embedded in the master capture are discovery witnesses;
their transitive sources are not all retained or independently verified here.

## Consecutive publication-failure correction, 2026-10-11

At `3bbc426cab79ac57146c67022b3cce2a3e9665b7`, two successive journal-write
failures could overwrite the only recovery snapshot with an API response that
omitted unresolved work. The next successful run lost the identity and its
first-observed date. A separate adjacent regression also showed that retry
fetched another response before completing a failed snapshot publication.

The installed CPython 3.13.16 source,
[`Doc/library/os.rst:2754-2760` at `cbc944f4`](https://github.com/python/cpython/blob/cbc944f4bc59639a444dd971c737788ba2283a91/Doc/library/os.rst#L2754-L2760),
documents atomic replacement of one file. It supplies no transaction across
the snapshot and notification journal. The existing `_write_json` mechanism is
therefore reused to save one `newstars-prepared.json` record containing both
documents before publishing either. Recovery republishes the journal and saved
snapshot before notification or another acquisition. The record remains prepared
until the posted journal and notification complete, so all later failures can
retry with the same identities, generations and first-observation dates.

Two regression checks failed before this correction: consecutive journal failures
lost `example/new`, and consecutive snapshot failures fetched again before
recovery. Both pass with the correction. The original reviewer regression also
passes. Further checks cover final-marker failure, preparation failure preserving
previous state, legacy prepared journals, append failure, omitted responses,
canonical clearance and reopened review work. These are actual local executions
with synthetic API responses and injected filesystem failures; power-loss
durability and live weekly network delivery are not measured by these checks.

The alternative was to make the latest snapshot itself contain live metadata and
pending work. A separate prepared record preserves the existing snapshot and
journal interfaces and the live-response meaning of the snapshot. A maintained
upstream facility supporting the same public allowlist, canonical review queue
and reproduced recovery windows would overturn this repository glue.

The same correction addresses five adjacent review findings through the existing
repository interfaces at `3bbc426cab79ac57146c67022b3cce2a3e9665b7`:
`scripts/catalog_decisions.py:157-221,251-284` defines typed source registration
and derived review fields; `scripts/build_ecosystem.py:783-839,885-921,1264-1271`
defines tracked reads and input hashes; `scripts/starred_convergence.py:35-50,86-100`
resolves source pointers. Their exact pre-fix files are retained with the pinned
CPython capture in the correction packet's checksum manifest.

Convergence references now retain `source_review` for the five pinned new
repositories and `metadata_review` for the other 368. The native decision-index
writer registers the current public-star snapshot as its sanctioned `public_star`
source when that file exists. Current membership comes from that collection;
older coverage references remain available as historical evidence. Without a
canonical snapshot, legacy fixtures keep their existing membership behavior.
The registered current snapshot is mandatory where present, preventing a stale
index from silently falling back to historical flags. The derived union remains
901 repositories with 373 current stars and 528 beyond current stars.

The convergence validator accepts the builder's tracked reader for every local
document it resolves, binding dynamic master/projection inputs and verdict
registries to the reported input digest. A source object declaring a repository
must match its seed's normalized identity. This also caught four existing pointers
from the two awesome-react discovery seeds to React component rows; those
cross-repository pointers were removed. The committed historical master remains
byte-identical and both seeds retain their own snapshot and master references.
Finally, empty-queue notification identities include retained review generations,
so initial emptiness, later clearance and reopened clearance each notify once.

Six focused checks failed before these corrections and pass after them: rendered
metadata/source flags, current snapshot membership, tracked dynamic evidence and
digest changes, empty-queue transitions, and snapshot/non-snapshot identity joins.
The full committed current-star set is independently compared with the canonical
snapshot. These are offline repository integration and synthetic transition
checks; they do not qualify upstream runtime execution or live weekly delivery.
