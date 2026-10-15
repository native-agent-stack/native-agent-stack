# Register the pending model-routes scope

Status: registration only, pending CC read and a later documented two-family
landscape sweep. No candidate, winner, terminal state, sealed run, wave or model
invocation is recorded here.

This is the registration successor to closed #1126, whose held content at
`0f9e90b1a31f10c213857b36a6d4aa5d5ee4290a` supplies the pending-row shape.
Its mixed rules/data implementation is superseded by #1130, landed as
`f165498aa6340860ef52de3a720ca2981eced062`. This PR reuses those landed
validators without changing their trust base. Base:
`8053f14e7e0817d2502dff2bb284bfb7e1b0152f`.

## Resolution inputs and bounded action

Protocol steps 1–3 from the layer-resolution decision were checked at that base:

- `catalogs/landscape/foundation.json` has no model-routes verdict or pending
  registration; the foundation taxonomy has no matching scope entry.
- No registered document in `catalogs/sota-convergence/layer-verdict-waves.json`
  carries a foundation/model-routes row.
- `catalogs/saturation/ledger.json` has no sweep for foundation/model-routes.
- `catalogs/landscape/final-stack.json` carries an angle-only unswept entry,
  zero winners, no catalog verdict and no terminal state. The retained source
  `catalogs/landscape/angles/foundation-model-routes.json` contains 14 carried
  candidate records: 13 INSUFFICIENT and one REJECTED. Registration does not
  import them as selected catalog candidates or settle their outstanding gaps.

CC's 2026-10-15 19:52Z option (B), relayed by the co-op, calls for the pending
registration now. The 19:19Z scope brief is retained by filename as
`model-routes.handoff-20261015T192404Z.md`; no digest of its unpublished bytes is
published here. The CC dispatch follows the retained direction record
`direction-cc-20261015T1912Z-new-wsl-harness-first.md`; this citation also uses
its name without a digest. The action exposes the named gap to the existing documented
two-family sweep path. It is not a research dispatch or a changed route default.

## Scope and evidence boundary

CC's 19:19Z dispatch supplies this exact public requirement (co-op clarification
of the source boundary):

Scope: current model ids and routes for the Anthropic API (vendor docs and the claude-api skill), OpenAI through OmniRoute, and Meta's Muse through the muse-code provider (Wonder Full; the Muse fence rules hold).

The source lists and per-route field list in the handoff are co-op elaboration;
they do not extend the verbatim requirement. The instruction to adjudicate all
14 carried candidates belongs to the initial sweep's next action.

The requirement in the catalog and taxonomy is identical. It covers current
model identities and routes for the Anthropic API, OpenAI through OmniRoute,
and Meta Muse through the muse-code provider's Wonder Full route. The existing
Muse fence decisions remain binding. Vendor, client, provider and route identity,
read pin/date, effort/tier controls, limits, price or plan class and adoption
status belong in the later source-bound comparison; an unverified field remains
a named gap with its cheapest check. The 14 carried records require substantive
adjudication, rather than omission or automatic promotion.

The row, taxonomy, research state and quality coverage all state pending work.
The catalog has registration_only=true, pending_lanes, empty candidates/winners/
alternatives, empty unsealed lane identities and named gaps. It claims no wave,
sealed run or terminal state. The native-clients taxonomy sentence denying a
separate route layer is explicitly superseded without rewriting its historical
client observations. Derived matrix, final-stack and new-host views are rebuilt
through their owning generators.

Named inputs and gaps:

- No ledger-countable two-family sweep has run for this layer.
- At this dispatch two single-family initial sweeps are running or being
  retained separately: the GPT half (Codex lane mage, now open #1177) and the
  Claude half (co-op under CC's 19:52Z option (A)). A later separate PR must
  record them as PRIOR evidence for the documented two-family sweep. Neither
  is this registration's verdict, and neither is FINAL.
- Every keyed measurement waits for the CC's specific approval. This change
  runs no keyed call, installs no tool and changes no provider or account state.
- Later covering-sweep publication and promotion out of registration require
  their separately owned admission/lifecycle rules. This registration changes
  no fail-closed guard and supplies no implicit promotion authorization.

The CC reads this PR before the co-op's paced `landscape-sweep --slots 2`.
The sweep's named readiness inputs and retained evidence govern launch; a pool
capacity constraint does not convert incomplete single-family work into a
two-family verdict. No route becomes FINAL from scope registration, source
review, a harness smoke or an installation alone.

## Regression and validation

`tests/test_model_routes_registration.py` first ran against unchanged base data
and failed all three tests because the explicit catalog row did not exist
(0 != 1). After registration the full repository landscape join must admit it
only as unrun. Removing the marker, adding a winner, sealing a lane or claiming
a wave is refused by the actual landed validator, with specific diagnostics.
The negative cases edit only in-memory input projections; published rows and
frozen wave bytes stay unchanged by testing.

[Retained controls](../../evidence/artifacts/model-routes-registration-20261015/controls.json)
record the before/after command, counts and refusal cause. The three-test module
passes after registration; the four requested #1130 suites plus this module
pass 184 native tests with no failures, errors or skips. The foundation taxonomy
and landscape/matrix/grand-list joins validate 21 foundation taxonomy scopes and
33 catalog layers; the frozen wave remains at its unchanged 20+12 members.

Run #1130's registration, pending catalog, wave and recorder suites plus the
new regression, catalog checks and full publication validation. The
base-trusted verdict-review gate must pass with no trust-path changes. Those
results establish registration integrity, not model quality or runtime adoption.

## Sources and alternatives

- Native repository at the base above: `scripts/landscape.py`
  `is_unrun_registration`, `validate_verdict_row`, `build_landscape`;
  `scripts/validate_foundation.py` taxonomy matching;
  `tools/sota-convergence/build_verdicts.py` `row_run_id` and frozen-wave checks;
  `scripts/verdict_review_gate.py` base-trusted validation. #1130's decision is
  `docs/decisions/2026-10-15-unrun-registration-rules.md`.
- Existing generated publication mechanisms: `scripts/component_matrix.py`,
  `scripts/final_stack.py` and `scripts/new_host_grand_list.py` at that base.
- `docs/decisions/2026-10-11-layer-resolution-protocol.md`: absent verdict/sweep
  means a bounded gap, with cumulative survivor custody and no implicit FINAL.
- `docs/decisions/2026-10-14-muse-file-fence.md` and
  `docs/decisions/2026-10-15-muse-toolchain-directory-grants.md`: the existing
  native Muse containment and named toolchain grants, unchanged here.
- python/cpython `v3.13.16`, `Lib/unittest/case.py` assertions and
  `Lib/unittest/loader.py` module discovery: the repository's existing native
  regression harness. No replacement test runner or dependency is introduced.

Placeholder selected candidates would imply evidence that has not been retained.
Keeping the layer outside the taxonomy leaves the existing launch/coverage path
unable to address it. Reusing the landed pending-empty state exposes the gap
without inventing a winner or altering the rules that assess later evidence.

## Surface-inventory review correction

The local review at `eedd595e06833706d6d7b5b1b3f4855786ee19ce`, retained as
`pr1179-eedd595e/review_output.json`, found a missed publication consumer:
the new taxonomy scope had no foundation surface binding. The native
`scripts/build_ecosystem.py --check` refused its exact layer-coverage join.
The initial registration's six passing catalog checks did not cover this
separate ecosystem publication check.

Add one `model-routes` binding in `catalogs/foundation/surfaces.json` with
empty surface and runbook lists. This uses the supported unselected-scope
representation and establishes no operational route or launch surface. The
inventory's scope text distinguishes selected surfaces from that pending state;
existing surface definitions and layer bindings remain unchanged.

Primary mechanism at the reviewed commit: `scripts/build_ecosystem.py:293-346`,
`build_grand_catalogs`, requires exact taxonomy/surface layer identities while
allowing empty `surface_ids` and `runbook_paths`. The new regression invokes
the actual repository's `build_data` join. It failed before the binding with the
same `foundation surface layers must exactly match foundation layers` error,
then the four-test registration module and deterministic ecosystem publication
check passed after it. The retained controls distinguish these results from the
initial three-test and 184-test evidence above. No rule change is needed.

## Remaining publication consumers in the same review wave

The GPT full read at the same head, retained as `GPT-VERDICT-eedd595e0.md`,
identified five further consequences of the new scope. The moved-file locator
search ran before repinning, and the review's complete moved-line inventory was
read. Active disposition citations now identify the same sandbox instruction at
manifest line 265 and its companion range at 261–264. Dated or fixed-pin evidence
keeps its historical coordinates; no historical synthesis is rewritten.

The owning new-WSL handbook builder regenerated both outputs, changing only their
research-state input hash. The existing integration receipt's current output
bindings are refreshed, with the previous bindings retained as dated history.
Its profile, selection, generator and 37-layer edition remain unchanged. The
hand-written grand-catalog summary gains an explicitly pending model-routes row,
with no winner. Its test still checks every recorded winner and decision exactly,
using shared unrun admission only for the new pending representation.

The blind-convergence audit names its 2026-09-21, 32-layer synthesis scope and
excludes only a registration admitted by `is_unrun_registration(..., root=...)`.
Historical synthesis and reviewer bytes stay unchanged. New controls preserve
those bytes and refuse an exemption carrying a selected winner, sealed run or
published-sweep membership. The architecture-page checks retain exact layer
identity comparison, expect 21 foundation and 12 trading rows, and explicitly
assert model-routes is pending, has no winner or wave, and is not FINAL.

Before these corrections, eight citation checks had two added failures, the
summary failed 20-versus-21 coverage, all six blind-audit tests failed the old
collection count, both architecture count checks failed, and the new-WSL builder
and committed-output test reported stale bytes. Two new blind audit controls
also failed before the shared-admission correction. Targeted corrected checks
pass. The broader affected selection ran 496 tests with one failure, no errors
and no skips: the existing catalog-freshness publication control caught stale
evidence registrations for these local edits. After refreshing all 13 edited-file
bindings through `scripts.host_receipts.register_file`, that exact test passed
in 62.735 seconds. Thus 495 tests passed on the first run and its only failure
passed on the targeted rerun; the whole selection was not rerun. These results
are retained separately from the original registration checks.

After the CC released the fold, the final recheck reproduced all six mechanisms
on a clean export of the reviewed head: 24 tests, 16 assertion failures, one
surface-join error and no skips. The same targeted selection on the final tree
passed all 24 tests with no failures, errors or skips. The controls retain the
reviewed-head and final-tree boundaries separately.

Pinned native mechanisms at `eedd595e06833706d6d7b5b1b3f4855786ee19ce`:
`scripts/build_new_wsl_handbook.py:187,772,1340-1375` (input-byte binding and
owning publication path), `tests/test_handbook_summary.py:48-61` (exact summary
coverage), `blueprints/blind-catalog-convergence/audit_reports.py:26-65`
(dated synthesis decision/pointer custody), `scripts/landscape.py:67-95`
(shared registration admission), and
`tests/test_local_pages_architecture_layer_pages.py:187-193,323-334`
(page identity and count assertions). These are repository integration controls,
not a new tool/practice adoption claim. Any future promotion or measurement
remains a PROPOSAL pending its own required evidence and CC approval.
