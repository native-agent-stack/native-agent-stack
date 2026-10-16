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
equality, receipt identity, platform qualification and FINAL paths are unchanged.
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
and refusal paths in `landscape.py`. This change owns only lock-entry source
identity/proof, the repository fallback table, and `catalog_identity` with legacy
callers. The second lander regenerates final-stack and re-registers evidence
against then-current main. Neither lane edits the other's functions.

PIN-DATA follows landed rules on current main. Systemd requires a supported new
run/wave and its retained evidence; the frozen scheduling-supervision row is not
rewritten here. No source-pin data fills or version upgrades are published by
this rules PR. The generated document changes only by tracking the existing
Nautilus proof as an additional input.

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
- `nautechsystems/nautilus_trader` at the rc5 tag/peeled commit above, with its
  public native query retained by #1197. No new live-source observation is claimed.
- `python/cpython v3.13.16`, `Lib/unittest/case.py`, `Lib/unittest/loader.py`,
  `Lib/ast.py`: the existing assertion/discovery harness and pinned-source span
  verification. No concrete TestCase is imported into another collected module.

Trusting a claimed commit alone or reading the current remote HEAD would change
identity. Reopen only on retained changed-tag, artifact or source evidence; no
FINAL conclusion or operational default follows from this source check alone.
