# Evaluation: native merge queue and independent evidence registrations

Date: 2026-10-15. **Status: proposal with an opt-in registry reference
implementation; native trial ended after an Actions event-policy rejection.**
Five genuine group runs failed before jobs started. Repository Actions policy
6423 excludes `merge_group`; the trial did not qualify queue adoption. The
root registry format and the
default `register_file` behavior remain unchanged. Production reader/writer
migration and root activation require a separate PR after this design's two
independent review families decide it.

The registry conflict mechanism is the centrepiece: independent PRs currently
edit one tracked JSON array. A merge queue cannot repair a conflict that
prevents GitHub from constructing its temporary group. The proposed format
stores complete authored registrations in independent Git paths and generates
the familiar `files[]` view when explicitly requested. The separate readiness
trial used [PR #1164](https://github.com/native-agent-stack/native-agent-stack/pull/1164),
head `df71a6c231ed9cc87609041cc5f8c720d33355e1`, against the isolated
`mq-trial-20261015` branch at `e1b5288051292cfdb19e2ca64349e4da35ba0970`.
The [sealed native trial record](../../evidence/artifacts/merge-queue-evaluation-20261015/native-trial.json)
retains admission, workflow failures, the protected-base push refusal, timed
CodeQL observations and the verified inverse, including residual-ref cleanup.

## Layer resolution and sources

This is a bounded delta to the existing native GitHub Actions path under the
[resolution protocol](2026-10-11-layer-resolution-protocol.md). The foundation
`ci-supply-chain` verdict remains `recorded` in
`catalogs/sota-convergence/layer-verdicts-20260922.json`; the latest covering
sweep is `landscape-sweep-20260929`, with its existing manifest, returns and
saturation ledger. No layer winner, FINAL status, runner service or model
default changes. The public Organization/free eligibility correction in #1148
reopened queue evaluation; eligibility alone does not establish readiness.

Primary sources, accessed 2026-10-15:

| Source at pin | Mechanism |
| --- | --- |
| [`github/docs@0226a2d78cf2be40ee3d769ec5661638461af0cc`, merge-queue management](https://github.com/github/docs/blob/0226a2d78cf2be40ee3d769ec5661638461af0cc/content/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue.md#L23) | Required group checks, settings, current-base construction; temporary branch creation precedes the webhook at lines 84–93. |
| [Same pin, Actions event reference](https://github.com/github/docs/blob/0226a2d78cf2be40ee3d769ec5661638461af0cc/content/actions/reference/workflows-and-actions/events-that-trigger-workflows.md#L374) | `merge_group: checks_requested` and the group SHA/ref. |
| [Same pin, trigger algorithm](https://github.com/github/docs/blob/0226a2d78cf2be40ee3d769ec5661638461af0cc/data/reusables/actions/about-triggers.md#L14) | Lines 14–18 explicitly select the workflow version at the event's associated SHA/ref. |
| [Same pin, Actions policies](https://github.com/github/docs/blob/0226a2d78cf2be40ee3d769ec5661638461af0cc/content/actions/concepts/about-actions-policies.md#L19) and [workflow execution controls](https://github.com/github/docs/blob/0226a2d78cf2be40ee3d769ec5661638461af0cc/content/actions/how-tos/administer/control-workflow-execution.md#L30) | Actions → Policies is separate from General permissions; event restrictions produce the exact observed denial, and policies layer across account levels. |
| [Same pin, native queue-entry schema](https://github.com/github/docs/blob/0226a2d78cf2be40ee3d769ec5661638461af0cc/src/graphql/data/fpt/schema.docs.graphql#L26227) and [enqueue input](https://github.com/github/docs/blob/0226a2d78cf2be40ee3d769ec5661638461af0cc/src/graphql/data/fpt/schema.docs.graphql#L14285) | Entry base/head/PR association and `expectedHeadOid`. |
| [Same pin, rejection reasons](https://github.com/github/docs/blob/0226a2d78cf2be40ee3d769ec5661638461af0cc/data/reusables/pull_requests/merge-queue-reject.md#L2) and [required checks](https://github.com/github/docs/blob/0226a2d78cf2be40ee3d769ec5661638461af0cc/content/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets.md#L173) | Conflicts/check failures remove entries; protection also governs direct ref changes. |
| [Same pin, code-scanning merge protection](https://github.com/github/docs/blob/0226a2d78cf2be40ee3d769ec5661638461af0cc/content/code-security/concepts/code-scanning/merge-protection.md#L35) | Lines 37–38 explicitly exempt merge queue groups from ruleset code-scanning protection; line 27 separates that protection from status checks. |
| [`github/rest-api-description@507b88ecbdccb4789ce77228fa2f2fde4bdeaf1f`, create-ruleset schema](https://github.com/github/rest-api-description/blob/507b88ecbdccb4789ce77228fa2f2fde4bdeaf1f/descriptions/api.github.com/api.github.com.json#L84445) | Exact branch, queue, required-check and code-scanning rule fields. |
| [`git/git@67ad42147a7acc2af6074753ebd03d904476118f` (2.53.0), merge-tree](https://github.com/git/git/blob/67ad42147a7acc2af6074753ebd03d904476118f/Documentation/git-merge-tree.adoc#L24) | Native merges without changing index/worktree; exit 0 for clean and 1 for conflict (line 214). |
| [Same Git pin, attributes](https://github.com/git/git/blob/67ad42147a7acc2af6074753ebd03d904476118f/Documentation/gitattributes.adoc#L1122) and [union implementation](https://github.com/git/git/blob/67ad42147a7acc2af6074753ebd03d904476118f/merge-ll.c#L149) | Union combines lines without JSON semantics; custom driver configuration is local Git configuration. |
| [Same Git pin, object layout](https://github.com/git/git/blob/67ad42147a7acc2af6074753ebd03d904476118f/Documentation/gitrepository-layout.adoc#L55) | Lines 55–61 store digest-named files below a two-hex-character directory. The proposal adopts that fixed-depth layout for path identities. |
| [Same Git pin, raw tree listing](https://github.com/git/git/blob/67ad42147a7acc2af6074753ebd03d904476118f/Documentation/git-ls-tree.adoc#L55) and [index input](https://github.com/git/git/blob/67ad42147a7acc2af6074753ebd03d904476118f/Documentation/git-update-index.adoc#L283) | `ls-tree -z` emits verbatim filenames with NUL termination (lines 130–133). `update-index --index-info -z` accepts native entry bytes, allowing a real committed invalid-UTF-8 filename in the regression. |
| [`python/cpython@cbc944f4bc59639a444dd971c737788ba2283a91`, hashlib](https://github.com/python/cpython/blob/cbc944f4bc59639a444dd971c737788ba2283a91/Doc/library/hashlib.rst#L40) | Lines 40–46 and 217–221 specify SHA-256 over bytes and hexadecimal output; record names use the UTF-8 artifact path. |
| [Same CPython pin, bytes decoding](https://github.com/python/cpython/blob/cbc944f4bc59639a444dd971c737788ba2283a91/Objects/bytesobject.c#L2439) | Lines 2439–2458 define strict UTF-8 decoding and `UnicodeDecodeError`. The reader retains strict decoding while isolating each historical entry's failure. |
| [`native-agent-stack@bf665ec698f9121b4c8e075804c259c57fd4f7b8`, legacy registration filter](https://github.com/native-agent-stack/native-agent-stack/blob/bf665ec698f9121b4c8e075804c259c57fd4f7b8/scripts/validate.py#L747) and [loader diagnostics](https://github.com/native-agent-stack/native-agent-stack/blob/bf665ec698f9121b4c8e075804c259c57fd4f7b8/scripts/validate.py#L415) | Independently valid historical rows retain registration intent; malformed current input fails. The loader identifies the file that failed. These are the reference behaviors extended to fragments. |
| [Same repository pin, explicit legacy-root contract](https://github.com/native-agent-stack/native-agent-stack/blob/bf665ec698f9121b4c8e075804c259c57fd4f7b8/scripts/evidence_manifest.py#L14) and [publication enumeration](https://github.com/native-agent-stack/native-agent-stack/blob/bf665ec698f9121b4c8e075804c259c57fd4f7b8/scripts/validate.py#L449) | The prototype does not activate the root. The production validator now rejects the marker and record-tree paths using its existing complete publication boundary. |
| [`twisted/towncrier@f92fbf5180f70e797af62932a4346573023d4001`, README](https://github.com/twisted/towncrier/blob/f92fbf5180f70e797af62932a4346573023d4001/README.rst#L18) and [builder](https://github.com/twisted/towncrier/blob/f92fbf5180f70e797af62932a4346573023d4001/src/towncrier/_builder.py#L148) | Separate authored fragments avoid shared-file conflicts; discover, read and check identity before assembly. |
| [`changesets/changesets@a897bb8ac115fa65343a8bfe53654040c1542a80`, writer](https://github.com/changesets/changesets/blob/a897bb8ac115fa65343a8bfe53654040c1542a80/packages/write/src/index.ts#L27) and [reader](https://github.com/changesets/changesets/blob/a897bb8ac115fa65343a8bfe53654040c1542a80/packages/read/src/index.ts#L29) | Unique fragment files avoid Git conflicts and are parsed into a generated view. |
| [`actions/dependency-review-action@a1d282b36b6f3519aa1f3fc636f609c47dddb294`, action.yml](https://github.com/actions/dependency-review-action/blob/a1d282b36b6f3519aa1f3fc636f609c47dddb294/action.yml#L25) | Explicit base/head refs outside PR events. |

Towncrier and Changesets provide the cited fragment pattern, not an
evidence-integrity package to install. Neither supplies this repository's
hash, byte-count, publication-review or sealed-review contract. No package,
server-side merge driver or new service is installed by this proposal.

## Registry proposal and fail-first evidence

Only a source explicitly declaring
`"file_records": "manifests/evidence-files"` opts into the reference format.
The existing `files[]` becomes a frozen seed; this avoids a 12,000-file
migration. For an update to `evidence/example.json`, SHA-256 of the UTF-8 path
selects `manifests/evidence-files/<first-two-hex>/<remaining-62-hex>.json`,
containing schema version 1 and the complete `record`, including its artifact
path. Every record has the same directory depth and bounded filename length;
artifact names cannot become record-directory prefixes. This supersedes the
unactivated path-plus-`.json` proposal after the collision regression below.
An explicit `remove` tombstone at the same path
represents deletion. Two writers for the same evidence item therefore meet at
the same Git path instead of producing two competing identities.

`scripts/evidence_manifest.py` provides the strict assembly boundary:

- `load` reads the explicitly enabled seed and records; `load_at` assembles a
  named Git tree without borrowing files from the current checkout. Its explicit
  historical mode retains independently valid registrations when a sibling is
  malformed; default/current reads remain strict.
- `write_record` and `remove_record` update one deterministic record path.
  Registration retains `publication_review` and unknown authored fields while
  deliberately updating only the artifact's expected hash and byte count.
- `--render` emits the generated legacy-shaped view to stdout. Neither loading
  nor rendering hashes artifact bodies or silently refreshes expected values.
- Invalid paths, recursive registry registration, duplicate JSON keys,
  misnamed/duplicate records, symlinks and malformed integrity fields fail.
  Unknown top-level metadata and authored record fields survive assembly.

`host_receipts.register_file` keeps its legacy writer unless the source has the
explicit marker. The reference historical validator additionally requires
`validate_registration_rows(..., record_fragments=True)`. Production callers
do not pass that option. The normal `Validator.load` remains a raw JSON reader.
Production validation rejects any root `file_records` key, including null,
and any publication under `manifests/evidence-files/`, whether hash-listed or
unregistered. The existing Git/archive publication enumerator supplies that
boundary. Root activation therefore requires a separate reviewed change.
The new helper is
added to the verdict gate's derived trust-code list because it is reachable
from existing modules, without changing the sealed-data reading contract.

| Local probe | Observed before | Observed after |
| --- | --- | --- |
| Two independent artifacts registered through the real `register_file` entry point, then native `git merge-tree` | Exit 1; only `manifests/evidence.json` conflicts | Exit 0; seed unchanged; both exact records and authored metadata retained |
| Same artifact updated differently on two branches | A shared record requires resolution | Native exit 1 at its deterministic record path; no union or silent winner |
| Explicit fragment-aware historical registration | Registered new artifact rejected as a missing row by the legacy reader | Matching recorded bytes pass; changed artifact bytes fail SHA-256 verification |
| An enabled frozen seed edited to restore shared-array registration | The deliberate bad fixture passed | Explicit validator rejects the frozen-seed edit |
| Malformed fragment with bad hash/boolean byte count | Normalizer checked only the seed and returned 0 | Checker returns 1 |
| Legacy writer without marker | Existing shared-array format | Byte-exact legacy output retained; no record directory created |

The initial focused suite passed **43 tests** across
`tests.test_evidence_manifest` and `tests.test_registry_rows`. It also covers
current-versus-historical tree isolation and a tombstone that cannot hide a
still-tracked artifact. These are synthetic/local integration results, not
hosted queue outcomes. The native conflict fixture failed before the format
change; hashes are never recomputed by validation to make tampering pass.

The review fold on `bf665ec698f9121b4c8e075804c259c57fd4f7b8` adds four fail-first
regressions. With only those tests added, the pinned implementation produced
**8 failing assertions/subtests in 4 tests** (exit 1, 0.398 seconds):

| Correction | RED at the reviewed head | GREEN behavior |
| --- | --- | --- |
| Historical registration continuity | A valid `docs/keep.md` registration beside a malformed sibling disappeared from history; deleting both fragments was accepted | The missing valid registration is rejected; restoring it passes while the malformed sibling creates no registration obligation; current malformed input still fails |
| Record naming | `evidence/a` and `evidence/a.json/b` collided as a record file and directory | Both register and load through native Git; a 255-byte artifact filename also works; the shared seed is unchanged |
| Fragment diagnostics | Invalid JSON and invalid record metadata named the seed manifest | Both errors identify the actual fragment source |
| Legacy root boundary | The root marker, null marker and registered/unregistered record-tree files were accepted | Production validation rejects all four cases; ordinary legacy fixtures pass |

All four regressions pass after the fold (0.525 seconds). The broader
manifest, registry, host-receipt, validator and verdict suite passes **492
tests**, no skips, in **40.941 seconds**. Native advisory derivation remains
**359 sites**, with identical script and shape counts; historical monitoring
snapshots remain unchanged. The commands, source pins and observations are
retained in `registry-reference-probes.json`. The path digest selects only a
record filename; it does not replace or recompute recorded artifact hashes.

A subsequent native probe at `9badf2e609d910ebb50c860b4dbbc1ac1c1348c4`
exposed a remaining failure before record assembly: one filename containing
invalid UTF-8 bytes aborted the entire historical listing. The listing reader
now handles tab separation, metadata splitting, regular-blob validation and
UTF-8 decoding inside each entry's boundary. Historical reads skip only that
entry; current reads refuse it and include the complete escaped byte entry in
the error. Strict decoding is retained without replacement or ignored bytes.

Two fail-first tests cover this correction. One uses native Git index plumbing
to commit a valid `docs/keep.md` registration beside an invalid-UTF-8 fragment
filename, then deletes both fragments while keeping the document. The missing
registration must be refused, and restoring it passes. The second checks
escaped current-mode diagnostics and sibling preservation for invalid UTF-8,
a missing tab, incomplete metadata and a nonregular blob. At `9badf2e6` these
produce **5 failing assertions/subtests in 2 tests** (exit 1, 0.547 seconds).
After correction both pass (0.797 seconds). The additional receipt is recorded
under `listing_fold` in `registry-reference-probes.json`. The broader suite
passes **494 tests** without skips in **79.958 seconds**. Native advisory
comparison remains at 359 sites with identical locations and shapes.

The next I/O sweep uses `c0437a49687a3d50bb28312cba893ce5cd045f9b` as
its unchanged RED implementation. A real mode-000 digest fanout directory
exposed a successful partial registry: `Path.rglob` silently omitted the
unreadable directory. The fix uses explicit `os.scandir` and `lstat`, rejecting
scan/stat failures and nonregular entries before any body read. A genuinely
absent record root remains a valid empty record set. An unavailable complete
enumeration aborts both current and historical reads; it cannot be treated as
an empty historical registry. Read/decode failures identify their source,
while a failed individual historical record is skipped without losing valid
siblings. Git stderr and command details are not included in I/O diagnostics.

This behavior follows the release-tag source for CPython **v3.13.16**:
[`Lib/pathlib/_local.py:611–620`](https://github.com/python/cpython/blob/v3.13.16/Lib/pathlib/_local.py#L611)
delegates `rglob` to `glob`, and
[`Lib/glob.py:452–467`](https://github.com/python/cpython/blob/v3.13.16/Lib/glob.py#L452)
and [`:509–523`](https://github.com/python/cpython/blob/v3.13.16/Lib/glob.py#L509)
suppress scanning and entry `is_dir` errors. `Path.walk` also delegates to
`os.walk` at
[`Lib/pathlib/_local.py:622–628`](https://github.com/python/cpython/blob/v3.13.16/Lib/pathlib/_local.py#L622);
a walker replacement must explicitly preserve the error path. The annotated
release tag resolves to `cbc944f4bc59639a444dd971c737788ba2283a91`;
these sources were accessed **2026-10-15**.

The bounded site inventory and dispositions are:

| Site class at `c0437a49` | Disposition and regression |
| --- | --- |
| `evidence_manifest.py` record-root predicates and recursive scan/stat, lines 72, 74, 77, 80 | Explicit enumeration and stat errors reject partial views. The mode-000 fixture first proves a real `PermissionError`, then exercises `load`, `--check` and `--render`; an enumerated entry's stat failure and a FIFO are separate cases. Modes are restored in `finally`; no permission skip or mock. |
| Local seed/record reads, including lines 161, 208, 217, 253 | Named-source read/decode boundaries cover loading, registration, removal and CLI paths. Seed decode diagnostics are tested through all entry points. Unreadable record-body rejection was already correct and remains a positive control. |
| Native Git seed, listing and record reads in `load_at`, including strict entry decode at line 197 | Global enumeration failure aborts; each known historical record's I/O/process/timeout failure skips only that record. The existing malformed-entry decode boundary and current strictness remain. |
| Fragment-aware `validate_registration_rows` seed, record and artifact reads | Scoped named-source helpers preserve current rejection and the frozen-seed guard. Base-seed I/O failure can no longer disable that guard; base/head seed, fragment and artifact failures name the source. The `record_fragments=False` path retains its behavior. |
| Global Git revision/history control decodes in `validate.py`, lines 745, 808, 813 | Existing controls already reject unavailable/invalid global Git inputs through the outer error boundary; retained without a speculative fix. |

With only the eight new regression tests added to `c0437a49`, RED produced
**13 failures and 2 errors in 8 tests** (exit 1, 0.743 seconds). The same
eight tests pass after correction (exit 0, 0.631 seconds); the broader suite
passes **502 tests**, no skips, in **39.681 seconds**. Exact commands, test
names, source hashes and dispositions are retained under `io_fold` in
`registry-reference-probes.json`. No existing test is weakened.

The native monitoring observation is appended as
[`unclassified-gate-reads-20261015-pr1166-io.json`](../../blueprints/runtime-workers/openhands/evidence/unclassified-gate-reads-20261015-pr1166-io.json)
with a new dated delta. Its provenance is `GitTree(c0437a49)` plus the three
explicitly hashed candidate source/test files, not `c0437a49` alone. Native
derivation changes **359 to 354 sites**: minus three in `evidence_manifest.py`
and two in `validate.py`, with the exact location/shape differences retained.
Centralizing reads changes the static scanner inventory; this is not a claim
of fewer runtime reads. The complete new snapshot supports an empty relative
delta; all historical snapshots, deltas and exact assertions remain intact,
with no worker permission change.

**Follow-ups for the first burn-down PR:** inspect unrelated `validate.py`
publication traversal, optional existence checks, regular-file/symlink
predicates and ordinary scanner reads/decodes. The retained locations at
`c0437a49` are 331, 335, 337, 404, 410, 420, 434, 442, 453, 483, 495, 498,
499, 538, 555, 557, 604, 691 and 694. These sites are deliberately outside
this correction; their presence in the inventory is not a finding of a bug.
The existing fail-closed Git controls above remain controls. The I/O sweep
does not authorize production registry activation or a wider validator change.

The first evaluation CI run, **38755360119**, failed two OpenHands advisory
baseline checks in `validate-shard-3` (job **116492228275**). Both failures were
reproduced locally before correction. Native `GitTree`/`derive_ci_protected`
comparison of base `e1b5288051292cfdb19e2ca64349e4da35ba0970` and implementation
`0f3464b8bc30108fc53bb692da56c9f30b53fc0a` measures **353 to 359** conservative
static sites: four registry-directory enumeration sites and two explicit
historical-manifest observations; eleven existing sites only moved lines.
The fresh dated snapshot and appended delta follow
[`advisory-gate-deltas.md`](../../blueprints/runtime-workers/openhands/evidence/advisory-gate-deltas.md)
at the base pin. The snapshot records each added site's actual purpose, without
calling registry reads user-status observations. Historical snapshots and
deltas stay byte-identical; the exact script, shape, total and history tests
are unchanged. This is monitoring accounting, with no worker permission change.

The installed Git 2.53.0 research probe found that `merge=union` returned exit
0 with malformed JSON for independent additions and duplicate digest keys for
competing updates. No current primary source was found promising GitHub queue
support for repository-defined custom merge drivers. This proposal relies on
neither union semantics nor such a support assumption. Regenerating a tracked
aggregate after `checks_requested` cannot solve its earlier admission conflict.

## Complete migration inventory before any activation

The [machine-readable inventory](../../evidence/artifacts/merge-queue-evaluation-20261015/registry-migration-inventory.json)
retains **503 matching files and 1,568 matching lines** from all tracked text at
`39b3fcaf5bcb96c8a672fb6198972dffd3d9937a`, plus eight inspected indirect
consumer paths. It includes retained snapshots, tests, instructions and
substring false positives instead of silently dropping them. A textual hit is
not automatically a runtime reader. The inventory also records the runtime
source delta through PR base `e1b52880`: four already inventoried consumers
changed, with updated reference locations, and no new direct reference consumer
was found by the same scan. The following migration responsibilities
are separate from the reference implementation:

| Surface | Paths and required migration |
| --- | --- |
| Ordinary integrity readers | `scripts/validate.py`, `host_receipts.py`, `validate_convergence.py`, `component_matrix.py`, `saturation_ledger.py`, `tools/sota-convergence/lane_packets.py`: explicitly consume the complete projection; preserve exact expected hashes and malformed-input failures. |
| Shared loaders and derived status | `scripts/catalog_decisions.py:load`, `landscape.py`, `platform_status.py`, `build_ecosystem.py`, `validate_foundation.py`: trace the existing delegated contract; receipts-only consumers may remain on seed metadata only with an explicit scope regression. |
| Historical Git-tree readers | `scripts/validate.py:validate_registration_rows`, `verdict_review_gate.py:Side.json/BaseTrust`, `local_pages_policy_grants.py:proposal`: enumerate the records in the same commit being judged, retain old-format history, all prior force-pushed heads, sealed-base binding and frozen-seed enforcement. The reference option is not production activation. |
| Bounded architecture reads | `tools/local-pages/architecture_evidence.py`, `architecture_builder.py`, `source_policy.py` (`Policy`, `ArchitectureReads`, `OverviewReads`), `overview_data.py`, `evidence_sources.py`, `build_pages.py`, plus `source_policy.json`, `overview_sources.json` and `architecture_mapping.json`: authorize the narrow metadata inputs, include every fragment in source provenance and cache signatures, and preserve byte limits, protected paths and explicit grants. Runtime discovery must not grant arbitrary body reads. |
| North-star source join | `tools/north-star/sources.json` and `build_readiness.py:Receipts/get/document`: the configured registry is joined to `files[]` hashes, so fragments must enter the confined read/provenance model before its source changes. |
| Receipt-only raw captures | `observability/grand-dashboard/progress.py` counts `receipts[]`; `tools/token-report/token_manifest.py` captures raw registry bytes and consumes `receipts[]`. Preserve their bounds and exact-capture claims; explicitly test whether the unchanged seed metadata is sufficient instead of pretending it is the assembled file registry. |
| Writers and rollback | `host_receipts.py`, `freshness_propose.py`, `hardware_profile.py`, `component_matrix.py`, `new_host_grand_list.py`, `final_stack.py`, `tools/sota-convergence/merge_fragments.py`: migrate explicit registration, deletion, failure rollback and generated-report registration. `freshness_propose.register_receipt` still owns shared `receipts[]`; that metadata is not reconstructed from file discovery. |
| Staging and path filters | `.github/workflows/catalog-freshness.yml`, `adoption-bootstrap.yml`, `validate.yml`, `adoption/manifest.json`: stage all authored records, include them in change discovery and preserve registration-history scope. Existing workflow gates must continue to test clean clones. |
| Identity and change exclusions | `tools/landing/nas_land.sh`, `scripts/active_model_currency.py`, `release_due.py`, `tools/sota-convergence/record_verdicts.py`: review each registry-only exclusion and prove review carry, re-pin drift and generated-index semantics before changing it. No blanket new exclusion is added here. |
| Tests, instructions and external clients | Every fixture/document occurrence is listed in the inventory. Retain legacy fixtures and immutable evidence; add format-specific cases and update operational instructions such as `docs/lanes.md` and `docs/contributing-evidence.md`. External raw-JSON clients must deliberately adopt a generated projection; arbitrary clients outside this repository are not discoverable by a repository scan. |

The root **does not contain the marker or any record directory** after this
change. The migration PR must close all these responsibilities and run the
affected consumers before enabling it. Raw JSON readers would otherwise see
only the frozen seed, which is why this evaluation does not activate the mode.
Concurrent changes to one artifact or shared authored top-level metadata can
still conflict; this proposal removes conflicts from independent file records.

## Native queue readiness and isolated trial

The [baseline](../../evidence/artifacts/merge-queue-evaluation-20261015/baseline.json)
records main ruleset **23739774**, seven required Actions contexts bound to app
**15368**, and the separate CodeQL code-scanning rule. At the source pin none
of the five owning workflows accepted `merge_group`. PR #1164 adds the event
to validate/secret-scan, token-report, dependency-review, security-scan and
pr-metadata, retaining the eight-shard aggregate and all context names.

That trial explicitly binds scanner and verdict ranges to the group base/head,
passes dependency-review refs, keeps SARIF write jobs off group events, and
checks the live SOTA body through a unique native queue association. Its
reusable SOTA job stays byte-identical. Missing, stale or ambiguous metadata
fails closed in the fixtures. The native queue entry populated the expected
group base/head. Its Actions-token access and live SOTA script remain
unqualified because the workflow never started a job.

The frozen workflow diff is six files, 159 insertions and 17 deletions.
Actionlint 1.17.0 and zizmor 1.30.1 offline passed all six files; zizmor reported
14 existing suppressions. The rebased focused suite passed 165 tests with one
existing skip. An initial host run hit uutils `tee` 0.10.0's pipe panic; the
successful run selected installed GNU `tee` 9.7 via temporary PATH without
changing tests. These are local results. The trial head was natively mergeable
against its isolated base and all required PR checks passed before enqueue;
those ordinary PR checks do not qualify group checks.

The command center created `mq-trial-20261015` from main and ruleset
**25165370** at **2026-10-15 13:56:32Z**. GET readbacks match the exact reviewed
proposal: only that ref, no bypass, SQUASH/ALLGREEN, build concurrency 1,
minimum/maximum group 1/1, wait 0, timeout 120 minutes, the seven existing
contexts and CodeQL. Main's rule has no merge queue and its last-update
timestamp remains 2026-10-04. No rule or branch-protection mutation is made by
this evaluation PR.

Admission preserved `lg_change_id` across the readiness rebase, both independent
reads and adjudication, head-bound verdict files reported as passing the native
gate, and the explicit command-center cue. Fresh GETs verified all seven latest
required checks successful on Actions app 15368, the frozen head, empty queue
and approved rule before native enqueue with `expectedHeadOid`. The queue
cannot read private approval records or supply their authority.
#1148 is the ordinary-lander baseline; a PR cannot merge twice, so this is not
a paired causal speed benchmark. Missing cue/lock timestamps stay missing.
#1148's GET readback records merge time **2026-10-15 13:51:29Z**, reviewed head
`6028d29eb004b60cfbd729cfbd9ff3f5d75446fa`, and merge commit `e1b52880`.

The planned window ended at first merge/ejection or **16:56:32Z**. After the
startup-policy failure, the command center explicitly ended it early and
deleted the rule at **15:30:54Z**, then the base at **15:30:55Z**. A retained
group ref was subsequently deleted at **15:37:37Z**. Independent final GETs
confirm all three absent, an empty `gh-readonly-queue` namespace, and unchanged
main-rule bytes. PR #1164 is closed and unmerged. This administrative end is
distinct from a natural queue ejection.

Default-setup CodeQL is vendor-managed. Successful API reads for the exact
group ref returned no analyses at 15:18:09Z, 15:22:09Z, 15:33:53Z and 15:40:47Z.
These are timed observations during and after this policy-blocked trial;
they do not prove permanent absence or qualify default setup after correction.

**Documented protection exception:** GitHub's pinned code-scanning documentation
states that ruleset merge protection does not apply to merge queue groups.
The trial rule's presence therefore does not enforce group analysis or alert
thresholds, and absent CodeQL analysis is not assumed to cause an ejection.
The frozen trial PR's body records this correction. Main adoption requires an
explicit group-level status gate, independently qualified for complete analysis
coverage, the exact group SHA and the intended alert thresholds. A successful
analysis job alone is not proof that findings prevent a merge.

## Separate Actions-policy security prerequisite

The native group was `b630c5168445503fdf5bfdf44d9a7f18b31c6d2b`, at
`refs/heads/gh-readonly-queue/mq-trial-20261015/pr-1164-e1b5288051292cfdb19e2ca64349e4da35ba0970`.
All five owning workflow runs reached `startup_failure`, with zero jobs,
artifacts and check runs. Four public run pages expose the exact annotation:
`Event 'merge_group' is not allowed to trigger Actions workflows.` The metadata
run also failed at startup but exposed no annotation in the public page read.

The supported GETs `/repos/native-agent-stack/native-agent-stack/actions/policies?has_parents=true`
and `/actions/policies/6423` establish the cause. Active Repository policy
**6423, Allowed workflow events**, applies to `~ALL` workflow paths and permits
only `push`, `pull_request`, `schedule` and `workflow_dispatch`. It was last
updated on October 4. General Actions permissions being enabled did not prove
event permission; the initial preflight missed this separate policy surface.
The governing policy documentation was already present at the original source
pin. This was not a new vendor restriction introduced during the trial.

The REST mechanism is documented at
[`github/rest-api-description@a7fb3ea21794469181243b7611b6e7cb99e0cef9`, policy listing](https://github.com/github/rest-api-description/blob/a7fb3ea21794469181243b7611b6e7cb99e0cef9/descriptions/api.github.com/api.github.com.json#L51546),
[individual retrieval](https://github.com/github/rest-api-description/blob/a7fb3ea21794469181243b7611b6e7cb99e0cef9/descriptions/api.github.com/api.github.com.json#L51737)
and [`restrict_action_events.allowed_events`](https://github.com/github/rest-api-description/blob/a7fb3ea21794469181243b7611b6e7cb99e0cef9/descriptions/api.github.com/api.github.com.json#L140065).
Organization-policy retrieval remains **UNCHECKED after HTTP 403**. No scope,
reauthentication or policy change was attempted. The directly observed
repository rule is sufficient to explain this rejection.

A new trial requires **its own reviewed security change** permitting
`merge_group` only for the five gate workflows: `validate.yml`,
`token-report.yml`, `dependency-review.yml`, `security-scan.yml` and
`pr-metadata.yml`. Preserve the existing event restrictions on other workflow
paths. Because policies layer, merely adding a more permissive policy cannot
override the current `~ALL` restriction; review the required scoping adjustment
explicitly, along with effective parent policies and actor rules. Qualify both
allowed group execution and rejection of unapproved events/paths. Nothing in
this evaluation changes policy 6423.

Workflow selection is the **group head**, according to the pinned source chain:
the trigger algorithm selects the workflow version at the associated event
SHA/ref; the `merge_group` table supplies the group SHA/ref; queue management
creates that combined branch before dispatch. The target branch filter does
not select the base's workflow version. No extra default-branch requirement
is stated for this event. Our zero-job failure does not establish a runtime
checkout, but it has a directly observed policy cause; it is not evidence that
the readiness delta had to land on main/base first.

## Required group code-scanning design before main adoption

Use the supported **advanced CodeQL setup**, with `pull_request` and
`merge_group` triggers and a separately required **CodeQL group policy** status
check bound to the intended Actions provider. GitHub explicitly instructs
advanced setups to add the group trigger in
[`workflow-configuration-options.md:62`](https://github.com/github/docs/blob/0226a2d78cf2be40ee3d769ec5661638461af0cc/content/code-security/reference/code-scanning/workflow-configuration-options.md#L62).
Default setup's [published trigger list](https://github.com/github/docs/blob/0226a2d78cf2be40ee3d769ec5661638461af0cc/content/code-security/concepts/code-scanning/setup-types.md#L18)
does not establish group coverage, and [default setup blocks separately
uploaded CodeQL SARIF](https://github.com/github/docs/blob/0226a2d78cf2be40ee3d769ec5661638461af0cc/content/code-security/reference/code-scanning/sarif-files/troubleshoot-sarif-uploads/default-setup-enabled.md#L25).
A reviewed switch to advanced setup is a prerequisite for that future design;
the isolated trial measured only the existing default setup's timed absence.

The policy is a proposed repository gate composed from supported APIs, not a
severity-threshold feature of the CodeQL action. Its concrete contract is:

1. Run the reviewed language/category matrix on the actual event commit. For a
   group, verify checkout HEAD equals `GITHUB_SHA=S` and retain its exact
   `GITHUB_REF=R`. Keep stable categories and every current invocation's
   `sarif-id`. `github/codeql-action` **v4.39.0** at
   `6f2ac81f5cd81fe351a197ba0b00d91d03cd2aee` supports explicit ref, sha, category
   and the SARIF ID output in
   [`analyze/action.yml`](https://github.com/github/codeql-action/blob/6f2ac81f5cd81fe351a197ba0b00d91d03cd2aee/analyze/action.yml#L56).
2. Independently require every upload to reach `processing_status=complete`
   with no processing errors. Missing IDs, API failure, failed/partial
   processing or a bounded deadline expiry fail the status check. The action's
   own `wait-for-processing` warns and continues after an API error or timeout
   ([`upload-lib.ts:882–886,916–923`](https://github.com/github/codeql-action/blob/6f2ac81f5cd81fe351a197ba0b00d91d03cd2aee/src/upload-lib.ts#L882));
   its successful exit is insufficient.
3. Follow the completed upload's `analyses_url`, or list analyses filtered by
   that current `sarif_id`, with full pagination. Require exact `commit_sha=S`,
   `ref=R`, reviewed CodeQL tool identity, every expected category/analysis key,
   and empty analysis error. Missing or skipped configurations and unreviewed
   completeness warnings fail. A nonzero `rules_count` is a sanity check, not
   proof of complete extraction. Do not use the newest repository analysis as
   a substitute for this run's uploads.
4. Fetch every page of CodeQL alerts for `ref=R&state=open`. Reject native
   `rule.severity=error` or `rule.security_severity_level` of `high` or
   `critical`. Bind current instances to `S` and the validated categories/
   analysis keys; use the instances endpoint to disambiguate multiple
   configurations. Stale, missing or ambiguous identity fails instead of
   dropping an alert. No custom fingerprint-diff algorithm is needed.
5. Publish success only after all preceding conditions pass. Run the status
   gate for the relevant PR event too, with its correct merge commit/ref, so
   the required context is neither absent nor merely skipped at admission.
   Preserve the existing PR code-scanning rule, other required contexts and
   independent review/cue process. Execute reviewed policy code, retain the
   expected coverage declaration, and qualify the required-check binding.

The REST contracts are pinned at
`github/rest-api-description@a7fb3ea21794469181243b7611b6e7cb99e0cef9`,
`descriptions/api.github.com/api.github.com.json`:
[alerts/ref semantics (60919)](https://github.com/github/rest-api-description/blob/a7fb3ea21794469181243b7611b6e7cb99e0cef9/descriptions/api.github.com/api.github.com.json#L60919),
[instances (61428)](https://github.com/github/rest-api-description/blob/a7fb3ea21794469181243b7611b6e7cb99e0cef9/descriptions/api.github.com/api.github.com.json#L61428),
[analysis upload filter (61500)](https://github.com/github/rest-api-description/blob/a7fb3ea21794469181243b7611b6e7cb99e0cef9/descriptions/api.github.com/api.github.com.json#L61500),
[native severity fields (156389)](https://github.com/github/rest-api-description/blob/a7fb3ea21794469181243b7611b6e7cb99e0cef9/descriptions/api.github.com/api.github.com.json#L156389),
[analysis identity (156699)](https://github.com/github/rest-api-description/blob/a7fb3ea21794469181243b7611b6e7cb99e0cef9/descriptions/api.github.com/api.github.com.json#L156699),
and [SARIF completion/errors (157337)](https://github.com/github/rest-api-description/blob/a7fb3ea21794469181243b7611b6e7cb99e0cef9/descriptions/api.github.com/api.github.com.json#L157337).
These source reads establish supported interfaces, not hosted qualification.

This whole-group open-alert policy is deliberately stricter than PR-diff-scoped
protection: existing blocking findings can stop a merge. Adoption must review
the existing-alert baseline and dismissal policy. Upload requires
`security-events: write`; the separate policy reader needs
[`security-events: read`](https://github.com/github/docs/blob/0226a2d78cf2be40ee3d769ec5661638461af0cc/data/reusables/actions/github-token-scope-descriptions.md#L31),
with only the other permissions needed by its trusted execution.

Before main activation, native trials must show a clean group passing and a
blocking alert causing the required status to fail and the queue to eject.
Also exercise wrong SHA/ref, stale category, missing language, pending/failed
processing, API timeout, pagination, dismissal and group regeneration. No
advanced-setup switch, new status check, workflow or rule change is implemented
by this evaluation or added to the frozen trial head.

## Conflict measurements and outcome record

Three deliberately selected baseline heads (#1145, #1091, #1141) produced
native merge-tree conflicts including the registry and other paths. The
baseline retains their exact run inputs. Selection is biased and repository
mergeability is asynchronous; these are neither a registry-only attribution
nor a queue ejection rate. Known and `UNKNOWN` states remain distinct.

The controlled docs probe is commit
`692c9463740746138177665612693995596d075e` on the trial base. Native Git merge-tree
against trial head `df71a6c2` returns **1**, naming **only
`manifests/evidence.json`**. It adds an independent probe document and its
registration, without product or trading changes. Native repository rule-suite
**4544322016** independently records the command center's single attempted
push at **15:20:58Z** (CLI refusal reported at **15:20:59Z**). It failed with
GH013: `Changes must be made through the merge queue` and
`7 of 7 required status checks are expected.` The base stayed at `e1b52880`.
This is a measured protected-base refusal, not an induced hosted conflict or
conflict-driven ejection. There was no bypass, retry or second queue entry.

| Native group workflow | Run ID | Result | Jobs / check runs |
| --- | --- | --- | --- |
| Validate published evidence | [38758783592](https://github.com/native-agent-stack/native-agent-stack/actions/runs/38758783592) | startup_failure | 0 / 0 |
| Validate portable token report | [38758785123](https://github.com/native-agent-stack/native-agent-stack/actions/runs/38758785123) | startup_failure | 0 / 0 |
| Dependency review | [38758788988](https://github.com/native-agent-stack/native-agent-stack/actions/runs/38758788988) | startup_failure | 0 / 0 |
| PR metadata gates | [38758787069](https://github.com/native-agent-stack/native-agent-stack/actions/runs/38758787069) | startup_failure | 0 / 0 |
| Dependency and workflow security scan | [38758791317](https://github.com/native-agent-stack/native-agent-stack/actions/runs/38758791317) | startup_failure | 0 / 0 |

All five check suites identify GitHub Actions app **15368**. The seven required
contexts are **unreported on the group SHA**; no group test, scanner or metadata
gate executed. Their successful PR checks and local fixtures do not qualify
group execution. The receipt preserves observed event fields as an API
projection, with raw webhook capture explicitly absent.

Native enqueue time was **15:15:36Z**. REST records administrative PR closure
at **15:30:55Z**, a **919-second enqueue-to-close interval**. The GraphQL
timeline contains the queue-add event and a closure event (15:30:56Z), with no
merge or queue-removal reason observed. No enqueue-to-natural-ejection or
enqueue-to-merge duration is claimed. The orphan group ref observed after the
initial inverse is retained in the record alongside its later cleanup, rather
than omitted from the outcome.

The sealed native record is complete. Successful queue qualification,
population ejection rate and stable speedup remain **unmeasured**. The current
landing path remains the default. The next trial first needs the scoped
Actions-policy security change; main adoption also needs the explicit
group-level CodeQL enforcement design and its native positive/negative tests.
Multi-entry throughput and all-member metadata binding remain separate work.

All local heavy tests/scans in this evaluation run under
`systemd-run --user --scope -p CPUWeight=idle` through the specified 16:00 ET
resource window. That resource policy does not supply any missing trial input.
