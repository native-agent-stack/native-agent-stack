# Verify run-source proofs before the separate FINAL opening

Status: PIN-RULES, based on main
`caa224140a2d04ba5f3d0ca320c487a75f9c9ea1`, which lands #1197. This changes
source-identity rules, not winner pins, versions, verdicts or FINAL admission.

## Mechanism and retained evidence

#1197 binds the unchanged NautilusTrader rc5 lock identity to a commit. Its
reader checks a well-formed 40-hex value but does not reproduce the source
observation, so replacing the binding with a different well-formed commit can
bind a correspondingly wrong receipt. The existing public observation is
`evidence/artifacts/nautilus-run-pin-20261016/tag-resolution.json`: upstream
`nautechsystems/nautilus_trader`, tag `v2.0.0rc5`, tag object
`34de0d6f886a9fe8359f9d6590f43f53c86b1d32`, peeled commit
`1b0a49d2792a9432a3aca3fcb617ce7a630d905e`.

`run_records` now also requires a matching retained exact-version observation:
component, version, repository, successful native command, requested tag refs,
stdout, tag object and peeled commit must agree. The tag parser distinguishes
annotated tags from lightweight refs and refuses absent, conflicting, malformed,
or ambiguous output. The binding must name the peeled commit, not the annotated
tag object. Missing or contradictory proof leaves the lock entry unparsed.

Proof is read offline through the repository's existing `safe_file` and JSON
pointer helpers; no network call occurs while building or checking final-stack.
New lock bindings carry `source_proof`, a repository artifact JSON reference
with an optional JSON pointer. The existing #1197 binding uses its already
published observation as an explicit compatibility entry; no commit is embedded
in that lookup and no catalog data is rewritten. Every proof read goes through
`Sources`, so its bytes are included in the generated source hashes. A later
change to proof is visible to the separate current-snapshot checks.

This verifies consistency with retained public source evidence. It does not
create signed upstream provenance, establish artifact build equivalence, or
perform an installation, E2E qualification or broker operation.

## Separate native utilities and legacy index identity

`scripts/complete_run_pins.py` extracts the retained native Git resolver. It
queries the exact unchanged version, records the command, exit and output, and
emits a component/version/tag/tag-object/peeled-commit table. Unsupported sources
and missing or ambiguous tags remain gaps; Claude Code remains separately owned.
It never silently upgrades a version or selects a current HEAD.

The offline apply mode validates all rows before writing any fill. It uses
separate `tools[].commit` / `components[].source_pin` fields, or adds an exact
lock-entry supplement with the report's consumed `source_proof` pointer. The
complete artifact SHA256 set and source version must still match, existing
contradictory commits are refused, existing lock bindings are preserved, and
`uv.lock` is never written. Previous JSON source metadata is retained in the
application result. Invalid report destinations refuse before any upstream
query. Regeneration and evidence registration remain explicit owning-tool steps.

The distribution bridge accepts only an explicitly marked
`https://git.launchpad.net/ubuntu/+source/<package>` source and a canonical
GitHub upstream-project identity. `catalog_identity` maps that upstream only for
legacy index coverage; the actual candidate, winner and run repository stays
the package source. Unmarked and foreign sources remain refused. Winner pin
equality and platform qualification are unchanged by the bridge. The separate
CC-ruled source-claim refusal in `complete_final_pin` is documented below.
The fallback repository table remains limited to packages absent from the stack;
the already selected Nautilus repository is not duplicated there.

## Ownership and landing order

The layer-verdict lane owns this PIN-RULES work and the following PIN-DATA batch,
including the deferred systemd source identity. The named routing inputs are
`ROW-cc-20261016T0108Z-new-wsl-gap-routing.md` and
`T1-PROTOCOL-WALK-20261016.md`; the 02:59Z split is retained by name in
`layer-verdict.pin-ownership-20261016.md`.

PIN-RULES lands FIRST. The separate FINAL-opening PR rebases onto it once; FINAL
must not activate before the wrong-commit guard. Its owner keeps qualified
admission and current-snapshot checks in `final_stack.py`, plus FINAL admission
and refusal paths in `landscape.py`. This change owns run-source identity/proof,
the repository fallback table, and `catalog_identity` with legacy callers.
The CC's later ruling explicitly adds an early source-claim refusal to
`complete_final_pin`; its existing pin-matching logic stays intact. The opening
owner preserves that guard on its single rebase. The second lander regenerates
final-stack and re-registers evidence against then-current main.

PIN-DATA follows landed rules on current main. Systemd requires a supported new
run/wave and its retained evidence; the frozen scheduling-supervision row is not
rewritten here. No source-pin data fills or version upgrades are published by
this rules PR. The generated document tracks the full-spelling Nautilus proof
and marks 31 unproved source commits informational; the resulting drift and
summary changes follow that fail-closed source projection. The instructions-
skills ECC and backtesting-engine lean commit-only drift changes from same to
unknown. No input pin or frozen verdict bytes change.

## Regression and primary sources

At the unchanged base, three primary tests reproduced seven wrong-proof
assertion failures and one intended runtime URL refusal for the marked package.
The latter is a real catalog join failure, not an import or fixture error.
After the fixes, the native tag/utility/proof/distribution and legacy landscape
checks pass. Counts and commands are retained in
`evidence/artifacts/pin-source-rules-20261016/controls.json`.

The two #1197 P3 follow-ups are also retained: a dated systemd ownership update
in its repository decision, and three cleanup controls. Against the actual
pre-cleanup `1a7917ff95d9f1d2908c0bd0c3cbf213320fc6d1` bytes, those three tests
fail on unread binding fields, an invented missing-stack fallback, and the
incorrect pinned API span; the current controls pass. Reviews are cited by name
as `GPT-VERDICT-d6a7b88a8.md`, with no digest of review bytes.

Primary mechanisms reused:

- Native repository at the base above: `scripts/final_stack.py` `run_records`,
  `record_pin`, `Sources`; `scripts/catalog_decisions.py` `safe_file`, `pointer`
  and `identity`; `scripts/landscape.py` legacy index joins.
- `git/git v2.53.0`, `Documentation/git-ls-remote.adoc`, OUTPUT: exact tag refs
  and peeled annotated objects. The parser composes Git's supported output;
  no replacement Git implementation or dependency is introduced.
- `nautechsystems/nautilus_trader` at the rc5 tag/peeled commit above. A new
  retained native full-spelling query supersedes #1197's single-spelling query,
  confirming the same commit. Additional sanitized public tag/ref witnesses
  are source observations only, without runtime or adoption acceptance claims.
- `python/cpython v3.13.16`, `Lib/unittest/case.py`, `Lib/unittest/loader.py`,
  `Lib/ast.py`: the existing assertion/discovery harness and pinned-source span
  verification. No concrete TestCase is imported into another collected module.

Trusting a claimed commit alone or reading the current remote HEAD would change
identity. Reopen only on retained changed-tag, artifact or source evidence; no
FINAL conclusion or operational default follows from this source check alone.

## Producer, freshness and proof-custody review corrections

The local review `pr1209-f2ef44c5/review_output.json` identifies three P2s at
`f2ef44c5281946364de2436a76b89445258df2ae`. Its native index producer still
calls `identity` directly (`scripts/catalog_decisions.py:184-215`), so a marked
selected package accepted by the landscape cannot regenerate its required
index. The narrow fix shares `catalog_identity` from the index module and uses
it in both producer and legacy consumers, preserving the original source URL.
No FINAL admission, refusal, or qualification function changes.

The upstream-project bridge is coverage identity, not freshness identity.
`scripts/landscape.py:1523-1525` at that reviewed pin wrongly accepts the old
GitHub source or a different package path declaring the same upstream. The
freshness check now compares the actual normalized repositories. Existing
explicit GitHub transfer aliases remain supported only between GitHub sources;
a distribution source must match its actual package path. Matching-package,
stale-GitHub, different-package and existing transfer controls exercise this
boundary.

The native resolver's report and sibling tag table are now create-only.
`scripts/complete_run_pins.py:237-238` at the reviewed pin overwrites an applied
report when its completed lock run drops out of the target inventory, invalidating
the retained source-proof pointer. Existing output paths now refuse before any
query, and exclusive file creation also prevents a late overwrite. An end-to-end
fixture applies a real lock supplement, generates a commit-bound run, then
attempts re-resolution and verifies that the report, table and generated document
remain unchanged. Unreferenced existing reports and tables are protected too;
supersession requires a new path and separately reviewed reference migration.

The four primary controls first reproduced three assertion failures and one
intended runtime `InvalidDecisionIndex` from the real producer. After correction,
the selected-source producer, actual freshness and applied-proof controls pass
alongside their native consumers. The first broader run caught two inherited-test
expectations for explicit GitHub aliases; preserving that existing transfer path
resolved them while retaining strict package identity. Counts remain separated
in the controls record rather than relabelling that failing run as passing.

## CC all-source proof ruling and source citations

`MICRO-full-f2ef44c5.md` and the co-op's fail-closed ruling extend the same
proof requirement to adoption `tools[].commit`, stack `source_pin`, and runtime
`source_commit`. A claimed commit without matching retained proof now remains
`source_commit_claim` information, with `source_proof_status=not_verified` and
no `pin_parsed.commit`. That projection alone did not refuse a version-only
receipt: the CC reproduced that bypass and ruled the early completion guard
below. `record_pin` syntax parsing and FINAL activation/current-snapshot
functions stay unchanged. Offline fills now write the
consumed `source_proof` reference for both adoption and stack entries.

Each source-path fixture first reproduces unproved receipt completion, then
proves the same source/commit is refused without proof and accepted with proof.
The apply controls separately reproduce the missing reference for both JSON
source forms. Proof component/run ids may differ from lock package names only
when joined by the same repository's selected stack identity; a real lock-fill
round trip covers that distinction.

The same read reproduced two native policy-grant test failures: the new utility
was absent from the exact repository inventory. Its single sorted grant is now
recorded in `tools/local-pages/source_policy.json`. No wildcard or runtime
discovery grant is added. Primary mechanism at the reviewed pin:
`scripts/local_pages_policy_grants.py:40-62` and
`tests/test_local_pages_policy_grants.py:112-137`.

Source proof must query every recognized exact-version tag spelling, including
both `v<version>` and `<version>`; matching more than one spelling remains
ambiguous. The new public `nautilus-tag-proof.json` queries both and explicitly
supersedes the earlier single-spelling observation without changing its commit.
`tag-spelling-witnesses.json` retains the original public Git query/output
witnesses for the component-specific query alternatives (Codex `rust-v`,
PostgreSQL `REL_`, Poppler `poppler-`, and the npm package tag prefixes).
Those alternatives are queries, not assumptions about source identity. Only a
unique observed ref supplies a commit. The sanitized native Launchpad query in
`systemd-source-query.json` witnesses the exact package URL and public
`import/255.4-1ubuntu8.17` ref; it applies no systemd pin or runtime change.

The uv artifact fields follow `astral-sh/uv` commit
`635500036e1705961315e86447f0fab0a8ddb309` (0.12.17):
`crates/uv-lock/src/lock/serialize.rs:509-554` serializes `sdist` and wheel
hashes as each hash's string; `crates/uv-pypi-types/src/simple_json.rs:626-644`
`HashAlgorithm`, `HashDigest` and `Digest` define the algorithm and validated
lowercase hexadecimal representation. The lock's `sha256:` strings are artifact
identities, separate from Git source commits. No wheel-to-commit build claim is
inferred by comparing them.

Native `--resolve` now uses an isolated temporary cwd and an explicit Git
environment disabling global/system config, inherited config injection,
prompts and non-HTTPS protocols. Raw stderr is never published; records retain
only its presence and the exit/result classification. This follows
`git/git v2.53.0`, `Documentation/git.adoc:742-763,970-975` (configuration,
prompt and protocol environment controls). Synthetic hostile-config/stderr
controls fail before this correction and pass after it.

The two specifically ruled legacy fixture migrations preserve every original
assertion in `tests/test_final_stack.py`:
`test_only_the_engine_repository_version_and_commit_are_copied` and
`test_equal_version_only_lock_keeps_conflicting_lower_commit_sources_visible`.
They add retained native-output fixture proof after first asserting the
proof-less variant remains informational and cannot bind. No FINAL activation
test or refusal code changes; the opening takes these fixtures on its single
rebase. Stale generated-document expectations are resolved only by native
regeneration, not by weakening their assertions.

## Complete review-wave fold

The last read, `GPT-VERDICT-f2ef44c52.md`, repeats the Architecture grant
finding from `MICRO-full-f2ef44c5.md`. The native proposal command
`python3 scripts/local_pages_policy_grants.py --root . --pin
f2ef44c5281946364de2436a76b89445258df2ae` identifies the exact utility path;
the manually reviewed inventory grants that path only. All 25 native policy
grant tests pass as part of the 201-test post-fold selection.

The same read identifies missing native monitoring accounting. The unchanged
`push_gate.derive_ci_protected` reader derives 354 unclassified locations from
the current executable source, against 353 previously accounted locations.
The utility's additional path validation is classified as monitoring only.
`unclassified-gate-reads-20261016-pr1209-pin-rules-delta.json` appends that
observation and current line moves against the immutable baseline; the index
only appends an entry, and every historical baseline and delta retains its
bytes. No worker permission or policy changes. Before this append, the full
127-test native gate module reproduces exactly two failures in monitoring
accounting, with no errors or skips. Committed-head replay verifies the append.

The lock-report retry contract is explicitly one use: the report names the
original lock pointer, and a successful fill changes the generated source to
the supplement pointer. Reapplying the old plan refuses before writes. The
regression snapshots every fixture file after the first successful apply and
checks that replay preserves the binding, version, artifact hashes, proof and
generated result. This records existing refusal behavior rather than claiming
a new retry implementation. A later fill needs a separately retained report.

The final fold closes the local producer/freshness/report-custody P2s; the CC
Architecture P1 and source-proof P2; the CC proof-completeness, resolver privacy,
source citation and lock/run-identifier P3s; and the GPT Architecture/monitoring
P2s and retry/freshness P3s. The shared producer is now
`catalog_decisions.catalog_identity`, imported by landscape. The two expressly
authorized legacy fixture migrations above remain the only changed FINAL-stack
fixtures. Partial read files and unpublished review digests are not evidence.

## CC completion refusal and native source round trips

`MICRO-delta-37609bd9.md` confirms at `80ce8d8f` that dropping an unproved
commit while keeping its version accidentally lets a version-only receipt
complete. The CC's ruling requires `complete_final_pin` to refuse every receipt
while `source_commit_claim` is present or `source_proof_status` is `not_verified`.
The existing matching rules follow this new guard unchanged. The regression
first reproduced four failures (claim alone, status alone, both and the actual
generated run); all now refuse. This narrow source-custody guard is the explicit
exception to the earlier unchanged-helper ownership boundary. It grants no
FINAL activation or qualification; the opening owner preserves it on rebase.

Stack and runtime proof consumption now use the same normalized-repository
component-ID scope as adoption and lock bindings. Their positive controls first
failed twice, then passed; unrelated-repository IDs remain refused. The local
review `pr1209-80ce8d8f/review_output.json` adds three producer/application issues
to the same ruled fold:

- Commit-only pins keep their version null and exact original commit. The
  resolver now has a separate typed-object route, not a guessed release tag.
  In a new isolated bare SHA-1 repository, native Git fetches that exact refspec
  with depth one and no tags (required tree/blob objects may also be fetched),
  and `git cat-file commit <OID>` supplies its body. The retained
  proof records the commands, successful exit codes and base64 body (at most
  one MiB), never raw stderr. Offline verification requires the same repository
  and repository-scoped component ID and recomputes the typed Git object ID.
  Missing objects, failed fetches, malformed or mismatched bodies remain gaps.
  No real upstream fetch, source fill or runtime operation is claimed by the
  synthetic round-trip test. Native `git hash-object -t commit --stdin`
  independently reproduces the fixture OID; changed body/type/commit/repository,
  component or return codes cannot bind. This retains a verification route for
  ECC/lean-style historical commits without silently assigning a version.
- `record_verdicts.build_winners` and `build_verdicts.build_verdict_row` carry
  `source_identity_kind` and `upstream_repository` when present. The actual
  producer-to-landscape test first reproduced the missing distribution-marker
  refusal, then passed without hand-editing the generated winner. GitHub rows
  gain no fields. An initial test setup lookup named the wrong fixture class;
  it was corrected before the real producer failure and is not counted as
  regression evidence.
- Offline fills compare parsed version identity while separately requiring
  the original raw pin and source pointer to match the retained plan. Both
  `v1.2.3` and `1.2.3 @ <commit>` first raised real apply errors and now preserve
  their original version text; a changed raw pin still refuses before writes.
  An embedded differing commit also refuses adjudication-free replacement.

The Poppler spelling witness now names the actual queried GitLab repository;
its command/output stay unchanged. The five-row consistency check first failed
on that mismatch and now passes. It is a query witness, not proof for the
different GitHub mirror. Earlier stale generated-output and live-observation
prose above is corrected to describe the final projection and retained queries.

Primary source for commit-only verification: `git/git v2.53.0`,
`Documentation/pull-fetch-param.adoc:30-33` (fully spelled object refspec, included
by `git-fetch.adoc:49`), `Documentation/git-cat-file.adoc:57-63` (typed contents),
and `Documentation/user-manual.adoc:4090-4118` (typed object header and hash).
These pinned primary bytes were read for this correction; the installed native
Git reports 2.53.0. This is observation consistency, not signed provenance or
an artifact-to-source build-equivalence claim.
