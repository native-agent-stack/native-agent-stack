# Decision: layer resolution before future research sessions (2026-10-11)

**Status:** CC-approved W6 governance; adoption and FINAL enforcement remain
separate changes.

## Context

The owner's W6 resolution wave requires future sessions to consume the decisions
already reached, adjudicate surviving candidates, and carry unsettled evidence
to a dated comparison. Repeating a survey while its survivors remain undecided
does not resolve the layer.

This records the approved W6 plan's **Future sessions** clauses (lines 252–255)
and **Definition of FINAL per layer** (lines 212–219), read on 2026-10-11 from
`~/.claude/plans/expressive-scribbling-lerdorf.md`, SHA256
`22b9f43b62cfeb458c25be0b4ccaf27601e78c71316aecdcded696d66afa5ea7`.
The operative requirements are retained below so future sessions can read them
from the repository without access to that coordination file.

## Decision

Before any research dispatch or comparison:

1. Read the layer's catalog verdict in
   [foundation.json](../../catalogs/landscape/foundation.json) or
   [us-equities.json](../../catalogs/landscape/us-equities.json), its evidence,
   and the applicable wave in
   [layer-verdict-waves.json](../../catalogs/sota-convergence/layer-verdict-waves.json).
   For another catalog, use its layer verdict; an absent verdict remains an
   explicit gap.
2. Read the latest sweep's survivors for that layer from
   [saturation/ledger.json](../../catalogs/saturation/ledger.json): select the
   latest sweep covering the `(catalog, layer_id)`, then follow its `survived[]`,
   `manifest_ref` and retained `returns_ref`. A newer sweep of other layers does
   not replace this layer's last sweep. Read its `reopen[]` and unresolved or
   missing votes too; a missing return is not an adjudication
   ([ledger contract](../../catalogs/saturation/README.md)).
3. Record the verdict/wave and sweep references consumed, the unresolved
   survivors or changed evidence, and the bounded next action. **Dispatch only
   the delta**: adjudicate existing survivors, test a changed upstream mechanism
   at its pin, fill the named evidence gap, or execute the committed comparison.
   When a verdict or sweep is absent, record that absence and scope the initial
   work to the gap.

A **FINAL layer reopens only when a sweep detects a change**. Bind the reopening
to that sweep and its retained change evidence, then apply the same delta rule.
The existing [sweep recipe](../../recipes/saturation-sweep.md) and
[stopping rule](../landscape-continuation.md#a-bounded-stopping-rule) describe
change triggers and closure evidence. A routine review date schedules a check;
it does not by itself establish a changed result.

## Terminal states and evidence

**FINAL** requires all applicable W6 evidence:

1. A recorded verdict with its evidence class, verdict wave and `next_review`.
2. A winner with a run pin in `catalogs/landscape/final-stack.json` `runs[]`.
3. An E2E receipt through the upstream's own install and test path, at that pin.
4. Invoke evidence in the measured window (adoption-now), or a recorded reason
   it isn't invoked. A zero-call tool is a wiring defect to fix, or a role to
   retire; installation alone is not invoke evidence.

**Evidence cannot settle the layer:** commit to ONE preregistered comparison
with a date and a fixed decision rule. Record the comparison reference, frozen
scope, and the dated rule before the run, using the existing comparison harness.
This is the bounded next action for an unsettled layer, not proof of a FINAL
winner. “No-winner” without a scheduled comparison is not allowed; “still
undecided” cannot be a terminal state. Execute the comparison and record its
result before claiming resolution.

The W6 plan assigns machine enforcement of FINAL to a follow-up
`scripts/final_stack.py --check` after the manifest PR. At this base those files
are not present; this decision does not claim that generator has run or that
any layer is FINAL. The existing catalog statuses (`pending_lanes`, `recorded`,
`no_selection`) retain their meanings and are not aliases for FINAL.
K=3 saturation remains a separate sweep count, not a FINAL verdict or a claim
that this wave reached saturation.

## Alternatives and consequences

A new full survey on every launch discards retained adjudication work. Closing
a layer from a selected pin alone omits native lifecycle and invoke evidence.
Leaving a no-winner row without a dated comparison postpones the decision
indefinitely. The chosen protocol reuses the existing verdict, sweep and
comparison pipeline, and requires only a short always-loaded AGENTS.md pointer.

The doc-pinning test protects that pointer and its requirements in native
`unittest` discovery. It proves repository-text consistency, not research
behavior or runtime adoption. Review of this PR requires the co-op GPT read
at Sol high and the CC's independent Claude read after PR-OPENED.

Change this protocol through a new reviewed decision if sweep evidence shows
that its delta boundary loses a material candidate or its completion criteria
misclassify a layer; retain this record as superseded history.

## Sources and verification boundary

- Governance authority: the CC-approved W6 plan and its source hash above.
- Michael Nygard, [Documenting Architecture Decisions](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions),
  2011-11-15, **Decision**, **Status**, **Consequences**: a short retained decision
  with context and consequences, and supersession rather than erasure.
- [python/cpython v3.13.16, Lib/unittest/loader.py](https://github.com/python/cpython/blob/v3.13.16/Lib/unittest/loader.py),
  `TestLoader.discover`, and
  [Lib/unittest/case.py](https://github.com/python/cpython/blob/v3.13.16/Lib/unittest/case.py),
  `TestCase.assertIn` / `assertEqual`: the upstream test harness used here.
  Local Python reports 3.13.16; no new test runner is introduced.
- Native pipeline at base `8bffa2c41692ef483e91b68e3b15aeb331423d2c`:
  [validate.yml](../../.github/workflows/validate.yml)'s test-discovery step and
  [validate_shards.py](../../scripts/validate_shards.py) `discover` discover
  `test*.py`; a new `tests/test_resolution_protocol_docs.py` joins that path.

Source review establishes the protocol and harness references. Local integration
can establish the doc-pinning red/green result and full publication validation.
Neither is an executed winner comparison, E2E adoption receipt or invoke window.
