# Unrun registration rules precede catalog registration

Status: rules-only prerequisite for a later model-routes registration PR. No
catalog, verdict row, wave, taxonomy entry or generated catalog changes here.
This supersedes the combined rules/registration publication shape in #1126;
its registration snapshot remains held at
`0f9e90b1a31f10c213857b36a6d4aa5d5ee4290a` until these rules land.

The CC's 2026-10-15 01:12Z split ruling follows the required gate at main base
`a339425ca56ec3fb87dff0fa8ad5dffc83354168`,
scripts/verdict_review_gate.py:1567-1576: a verdict change cannot land together
with its validating trust-base changes. CI deliberately runs base-trusted
validators against the head. Retained job evidence SHA256
`592a836829884baff2de24c34c39295baeb36017ab09837aca65a9482d528719`
reproduces this refusal at both combined heads. The gate is unchanged.

## Rules and independent regressions

The existing pending-lane schema can hold empty selection containers, but its
legacy consumers require selected candidates, complete taxonomy capability
coverage and membership in an existing wave/sweep. Those assumptions prevent
honest registration of a new unswept scope. Placeholder selections and an
invented frozen-wave membership would misstate evidence.

The rules support an explicit registration_only state: pending verdict, empty
candidates/winners/alternatives, unsealed empty lane identities, named gaps and
no terminal state. The shared predicate refuses a winner, sealed run or claimed
wave. Ordinary unmarked historical rows keep their existing wave fallback.

- landscape.py admits empty pending scope under its bounded container/gap rules.
- build_verdicts returns null for an explicit unrun registration and omits it
  from wave output. Frozen evidence is neither rewritten nor re-registered.
- validate_foundation keeps the existing 20 required layers and admits the
  supported additional scope only with its exact matching pending catalog row.
  It cannot borrow a capability decision or invent a selected component.
- component_matrix carries the explicit marker without changing selection.
- new_host_grand_list admits a missing sweep entry only for the marked empty
  pending matrix state with no adjudication, manifest layer or in-use/converged
  winner rows. The output retains an unswept gap in JSON and Markdown. Missing
  ordinary/selected sweep coverage still refuses.

All new consumer regressions construct independent temporary fixtures; none
requires a changed published catalog. Before applying the rules on this branch,
four tests reproduced the original exact failures: layer-needs-candidates,
20-required-layers, wrong 20260922 wave attribution and missing model-routes
sweep coverage. After applying the rules, positive and negative fixtures pass,
including frozen-wave byte preservation. Existing catalog checks continue to
pass on the unchanged 20-layer/32-row main data. No operational, provider,
account, runtime or adoption claim follows from these schema tests.

## Sources and next readiness input

Round-one local review at 5277796785096286d86c83d2b2dc0ad1ace3fddd
(review SHA256 5294a89d3b846032004862774d7456353968e90be30e8f2ce7c56c61bbaa5af1)
found four consumer gaps. Each correction has a behavioral fail-first regression:

- Native unittest module discovery collected an imported LandscapeTests class
  again, causing validate_shards.assignment to choose serial-native-fixture-fallback.
  Importing its module preserves one owner per native case and eight-way planning.
- An unmarked additional taxonomy layer borrowed an existing capability decision
  and passed without any matching catalog. Extra layers now require the explicit
  registration marker and its existing matching-scope checks.
- record_verdicts must not publish a sealed row while its ledger candidate
  container is still an empty registration. It refuses before publication until
  screened ledger candidates and explicit marker retirement are recorded.
  Packet candidates or one lane do not supply missing v1 selection roles.
  Missing or wholly rejected returns leave the registration row untouched.
- A pending registration with actual covering sweep membership was published as
  unswept. The grand-list joins layer membership from the selected sweep manifest,
  including empty component lists, and reports pending verdict lanes separately.
  Controls exercise both current and stale matrix coverage flags.

Pinned correction mechanisms at the reviewed head 52777967:
scripts/validate_shards.py:94-163 (native module ownership and shared-fixture fallback),
scripts/validate_foundation.py:88-113 (additional taxonomy and matching registration),
tools/sota-convergence/record_verdicts.py:720-741, :827-829, :1014-1043
(no-op when no lane is valid; mutation once returns are sealed), and
scripts/new_host_grand_list.py:91-163, :311-318, :381-383
(selected manifest coverage and registration reporting). The upstream discovery
mechanism is python/cpython v3.13.16 Lib/unittest/loader.py, loadTestsFromModule:
it collects every module-bound TestCase subclass, including imported classes.
These corrections introduce no catalog, verdict-row, wave or generated output edits.

## Round-two admission and publication boundary

CC FULL at 94f4c76497cb41b5d431b73101c64002d9918694, SHA256
20e91f29dd558bed0c8b7214c666b3d70d45dc3df5142b3b009222c3a82060e0,
and the overlapping local review SHA256
56dff7216525ea8ce66561119256c9b55c7bd2ad150d270ec21b93b3220ba4e8
showed that row shape cannot establish never-run identity. Admission now needs
repository context and refuses any catalog/layer key in a hash-verified registered
wave document, registered sweep ledger or published sweep manifest. All native
wave, taxonomy, landscape and final-stack callers supply that context; rootless
marked-row classification refuses. Required foundation layers cannot use the
marker to waive a capability decision.

Only that explicit admitted registration may bypass candidate/alternative and
quality challenger requirements. The previous unmarked empty-row acceptance is
removed. A two-wave fail-first fixture emptied the grandfathered row, erased its
lane identity and regenerated the newer wave successfully before the correction;
both --write and --check now refuse while every output stays byte-identical.
The unmarked empty-row and required-taxonomy capability-waiver controls also
failed behaviorally before correction. Independent sweep-manifest and ledger
membership controls exercise the same history boundary.

The first-run tests now start with genuinely valid empty registrations: native
admission and the full landscape join both pass before any returns arrive.
Both agreeing lane returns and Codex-only returns refuse before any ledger,
sealed return, registry or other root output changes, rather than removing the
marker and publishing an invalid candidate-less row. This takes the review's
explicit refusal-before-publication option; candidate promotion is a separate
screened catalog transition, not inferred by this rules PR. Missing/rejected
return controls assert the original row remains exactly unchanged. Specific
diagnostics replace broad exception/return-code-only negative controls.

Pinned mechanisms at 94f4c764: scripts/landscape.py:25-45, :1318-1349 and
:1606-1608; tools/sota-convergence/build_verdicts.py:164-174, :472-501;
scripts/validate_foundation.py:98-110, :237-239;
tools/sota-convergence/record_verdicts.py:813-830, :1016-1019; and
scripts/final_stack.py:524-528, :660. The existing confined JSON loader,
registered wave hashes and native recorder refusal path are reused. No gate,
catalog, frozen wave, sweep record or selection changes with these rules.

The Astra fix-one read at the same head, retained privately as
GPT-VERDICT-94f4c7649.md and cited here without a digest,
added two P2 blockers to this same final bounded round. Both reproduced before
correction: marked rows accepted malformed protocols, non-text overturn conditions
and lane run bindings; taxonomy accepted the right layer ID from the wrong catalog
and accepted an invalid registration date. The maintained common verdict-schema
checks now run for every registration admission and before the full validator's
wave exemption. Registrations admit only the empty lane fields, without run-manifest,
adjudication or prose-exposure bindings. Taxonomy matching requires the complete
foundation/layer identity, and shared admission validates its date and protocol.
The eight negative subcases failed before and pass after the correction.
Sources at the reviewed head: scripts/landscape.py:896-905, :1107 and
scripts/validate_foundation.py:105-109. No additional bounded fix commit is split off.

Native source at `a339425ca56ec3fb87dff0fa8ad5dffc83354168`:

- scripts/landscape.py:854-859 and :1264-1318: pending verdict containers and
  the candidate/selection integrity path.
- scripts/validate_foundation.py:35-42, :88-94 and :216: taxonomy/capability
  coverage, extended without changing the current taxonomy data.
- tools/sota-convergence/build_verdicts.py:164-170, :232-272 and :467-486:
  historical wave fallback, wave generation and frozen rows.
- scripts/component_matrix.py:580-618 and scripts/new_host_grand_list.py:91-151,
  :301-373: derived marker propagation and the newest-sweep coverage join.
- scripts/verdict_review_gate.py:1573: rules must land before verdict-row changes.
- python/cpython v3.13.16 Lib/unittest/case.py assertEqual/assertRaises:
  the existing regression harness, matching installed Python.

After this rules PR lands, rebuild the separate catalog registration on current
main with the CC's exact model-routes scope. The CC reads that registration PR
before the paced --slots 2 sweep. This is readiness by named inputs; no sweep
is dispatched by the rules change. Reopen the rules if retained validator/sweep
evidence shows an unrun state can bypass selection, wave or coverage integrity.
