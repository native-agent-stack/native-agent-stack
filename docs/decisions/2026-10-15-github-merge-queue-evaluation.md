# Evaluation: native merge queue and independent evidence registrations

Date: 2026-10-15. **Status: proposal with an opt-in registry reference
implementation; native trial pending.** The root registry format and the
default `register_file` behavior remain unchanged. Production reader/writer
migration and root activation require a separate PR after this design's two
independent review families decide it.

The registry conflict mechanism is the centrepiece: independent PRs currently
edit one tracked JSON array. A merge queue cannot repair a conflict that
prevents GitHub from constructing its temporary group. The proposed format
stores complete authored registrations in independent Git paths and generates
the familiar `files[]` view when explicitly requested. The separate readiness
trial is [PR #1164](https://github.com/native-agent-stack/native-agent-stack/pull/1164),
head `df71a6c231ed9cc87609041cc5f8c720d33355e1`, against the isolated
`mq-trial-20261015` branch at `e1b5288051292cfdb19e2ca64349e4da35ba0970`.

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
| [Same pin, native queue-entry schema](https://github.com/github/docs/blob/0226a2d78cf2be40ee3d769ec5661638461af0cc/src/graphql/data/fpt/schema.docs.graphql#L26227) and [enqueue input](https://github.com/github/docs/blob/0226a2d78cf2be40ee3d769ec5661638461af0cc/src/graphql/data/fpt/schema.docs.graphql#L14285) | Entry base/head/PR association and `expectedHeadOid`. |
| [Same pin, rejection reasons](https://github.com/github/docs/blob/0226a2d78cf2be40ee3d769ec5661638461af0cc/data/reusables/pull_requests/merge-queue-reject.md#L2) and [required checks](https://github.com/github/docs/blob/0226a2d78cf2be40ee3d769ec5661638461af0cc/content/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets.md#L173) | Conflicts/check failures remove entries; protection also governs direct ref changes. |
| [Same pin, code-scanning merge protection](https://github.com/github/docs/blob/0226a2d78cf2be40ee3d769ec5661638461af0cc/content/code-security/concepts/code-scanning/merge-protection.md#L35) | Lines 37–38 explicitly exempt merge queue groups from ruleset code-scanning protection; line 27 separates that protection from status checks. |
| [`github/rest-api-description@507b88ecbdccb4789ce77228fa2f2fde4bdeaf1f`, create-ruleset schema](https://github.com/github/rest-api-description/blob/507b88ecbdccb4789ce77228fa2f2fde4bdeaf1f/descriptions/api.github.com/api.github.com.json#L84445) | Exact branch, queue, required-check and code-scanning rule fields. |
| [`git/git@67ad42147a7acc2af6074753ebd03d904476118f` (2.53.0), merge-tree](https://github.com/git/git/blob/67ad42147a7acc2af6074753ebd03d904476118f/Documentation/git-merge-tree.adoc#L24) | Native merges without changing index/worktree; exit 0 for clean and 1 for conflict (line 214). |
| [Same Git pin, attributes](https://github.com/git/git/blob/67ad42147a7acc2af6074753ebd03d904476118f/Documentation/gitattributes.adoc#L1122) and [union implementation](https://github.com/git/git/blob/67ad42147a7acc2af6074753ebd03d904476118f/merge-ll.c#L149) | Union combines lines without JSON semantics; custom driver configuration is local Git configuration. |
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
migration. An update to `evidence/example.json` writes
`manifests/evidence-files/evidence/example.json.json`, containing schema version
1 and the complete `record`. An explicit `remove` tombstone at the same path
represents deletion. Two writers for the same evidence item therefore meet at
the same Git path instead of producing two competing identities.

`scripts/evidence_manifest.py` provides the strict assembly boundary:

- `load` reads the explicitly enabled seed and records; `load_at` assembles a
  named Git tree without borrowing files from the current checkout.
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
do not pass that option. The normal `Validator.load` remains a raw JSON reader;
no production reader silently changes format in this PR. The new helper is
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

The focused suite currently passes **43 tests** across
`tests.test_evidence_manifest` and `tests.test_registry_rows`. It also covers
current-versus-historical tree isolation and a tombstone that cannot hide a
still-tracked artifact. These are synthetic/local integration results, not
hosted queue outcomes. The native conflict fixture failed before the format
change; hashes are never recomputed by validation to make tampering pass.

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
fails closed. Hosted queue-entry base/head population remains a trial boundary;
the schema and fixtures alone do not prove it.

The frozen workflow diff is six files, 159 insertions and 17 deletions.
Actionlint 1.17.0 and zizmor 1.30.1 offline passed all six files; zizmor reported
14 existing suppressions. The rebased focused suite passed 165 tests with one
existing skip. An initial host run hit uutils `tee` 0.10.0's pipe panic; the
successful run selected installed GNU `tee` 9.7 via temporary PATH without
changing tests. These are local results. The trial head is natively mergeable
against its isolated base; its ordinary PR checks do not qualify group checks.

The command center created `mq-trial-20261015` from main and ruleset
**25165370** at **2026-10-15 13:56:32Z**. GET readbacks match the exact reviewed
proposal: only that ref, no bypass, SQUASH/ALLGREEN, build concurrency 1,
minimum/maximum group 1/1, wait 0, timeout 120 minutes, the seven existing
contexts and CodeQL. Main's rule has no merge queue and its last-update
timestamp remains 2026-10-04. No rule or branch-protection mutation is made by
this evaluation PR.

Before enqueue, preserve `lg_change_id`, head-bound LG-OK verdict files, both
independent reads, adjudication, shared-lane acknowledgement and the explicit
command-center cue. Enqueue with native `expectedHeadOid` equal to the reviewed
head. The queue cannot read private approval records or supply their authority.
#1148 is the ordinary-lander baseline; a PR cannot merge twice, so this is not
a paired causal speed benchmark. Missing cue/lock timestamps stay missing.
#1148's GET readback records merge time **2026-10-15 13:51:29Z**, reviewed head
`6028d29eb004b60cfbd729cfbd9ff3f5d75446fa`, and merge commit `e1b52880`.

The first merge or ejection ends the trial; its hard cap is **16:56:32Z**.
The command center deletes the ruleset, then the trial base branch; verify
both inverses by GET. Default-setup CodeQL is vendor-managed, with no workflow
file to patch. Retain actual analysis on the group SHA or observed absence on
this non-default branch. Never substitute a PR analysis or fabricated event.

**Documented protection exception:** GitHub's pinned code-scanning documentation
states that ruleset merge protection does not apply to merge queue groups.
The trial rule's presence therefore does not enforce group analysis or alert
thresholds, and absent CodeQL analysis is not assumed to cause an ejection.
The frozen trial PR's body records this correction. Main adoption requires an
explicit group-level status gate, independently qualified for complete analysis
coverage, the exact group SHA and the intended alert thresholds. A successful
analysis job alone is not proof that findings prevent a merge.

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
the isolated trial continues to measure the existing default setup.

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

The controlled docs probe is local commit
`692c9463740746138177665612693995596d075e` on the trial base. Native Git merge-tree
against trial head `df71a6c2` returns **1**, naming **only
`manifests/evidence.json`**. It adds an independent probe document and its
registration, without product or trading changes. This is a local prerequisite,
not an observed hosted removal.

While the genuine group builds, the command center may attempt **one leased
push** of that exact probe to the protected trial base. Required checks and
the queue may refuse it. Retain the refusal and rule names as the result;
there is no bypass, ruleset relaxation or retry. A second PR placed ahead in
the queue requires separate authorization. If the trial merges/ejects first,
do not manufacture another outcome. Distinguish admission conflict, base
update rejection, group invalidation and actual queue ejection.

The final native receipt must retain enqueue/group/base/ref identifiers,
required contexts and app IDs, job/run timing, actual CodeQL analysis or timed
absence, any removal reason, enqueue-to-outcome, merged tree/author if present,
and inverse readbacks. Until then, native queue success, population ejection
rate and stable speedup remain **unmeasured**. The current landing path remains
the default; multi-entry throughput and all-member metadata binding require a
separate evaluation.

All local heavy tests/scans in this evaluation run under
`systemd-run --user --scope -p CPUWeight=idle` through the specified 16:00 ET
resource window. That resource policy does not supply any missing trial input.
