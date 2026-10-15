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
- record_verdicts accepted and sealed the first valid lane returns but retained
  registration_only, leaving a recorded row rejected by the next consumer.
  The recorder removes that marker when valid lane processing mutates the row;
  missing or wholly rejected returns still leave the row untouched. New-wave
  controls cover both agreeing lanes and a sole Codex lane with no recorded winner.
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
