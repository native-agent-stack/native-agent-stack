# Decision: layer resolution before future research sessions (2026-10-11)

**Status:** CC-approved W6 governance; adoption and FINAL enforcement remain
separate changes.

## Context

The CC-approved W6 plan supplies the pre-dispatch protocol and comparison
mechanics below. Repeating a survey while its survivors remain undecided does
not resolve the layer.

Authority is the retained W6 snapshot, section **W6. The final resolution wave**,
including **Definition of FINAL per layer**, **Terminal states** and
**Future sessions**, SHA256
`fb4a95b19a00335c5831bce913cbf177f90d5bd2c17819013b6021d2dc585e5c`.
It is captured unmodified as `coordination/plan-current-unmodified.md` in
`~/.local/state/native-agent-stack/coordination/ns2604-coop/lanes/landscape-live-foundation.w6-sources-20261011/`,
whose `MANIFEST.sha256` binds the source bytes. This replaces the initial
unretained full-plan citation. The terminal definitions incorporate the CC's
2026-10-11 06:12Z ruling, which resolves condition 5 separately from FINAL's
conditions 1–4. Operative requirements are retained here so future sessions
need no access to the coordination file.

The CC's 2026-10-11 17:31Z readiness ruling supersedes date-based comparison
routing below; preregistered data windows retain their original boundaries.

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
   not replace this layer's last sweep. For a completed sweep awaiting its ledger
   append, read its retained manifest and returns and record that the ledger
   append is pending; use that newer completed sweep rather than an older ledger
   row. If those retained sources are unavailable, record an unresolved
   latest-sweep gap and bound recovery to retaining and registering them.
   An older ledger row cannot be treated as the latest sweep. Reconstruct each
   candidate's latest adjudication from all prior sweeps covering the layer,
   including retained completed sweeps awaiting append. Carry forward every
   unresolved survivor until a later retained substantive adjudication or
   catalog verdict explicitly settles it; later omission and missing return
   do not clear it. Read its `reopen[]` and unresolved or missing votes too;
   a missing return is not an adjudication
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
change triggers and closure evidence. A routine review date records review
metadata; it does not delay ready work or by itself establish a changed result.

## Terminal states and evidence

**Terminal states:** FINAL, SCHEDULED, RETIRED.

Before choosing a terminal state, record the disposition of the cumulative
unresolved survivor set: adjudicate it, include it in the frozen comparison, or
record the reason its role is retired. A later sweep's omission cannot provide
that disposition.

A layer is FINAL only when all of the following hold for each of its winners:

1. A recorded verdict with its evidence class, verdict wave and `next_review`.
2. Each winner has a run pin in `catalogs/landscape/final-stack.json` `runs[]`.
3. An E2E receipt through the upstream's own install and test path, at that pin.
4. Invoke evidence in the measured window (adoption-now), or a recorded reason
   it isn't invoked. A zero-call tool is a wiring defect to fix, or a role to
   retire; installation alone is not invoke evidence.

**SCHEDULED:** no winner because evidence cannot settle the layer; commit to
ONE preregistered comparison with a readiness trigger and a fixed decision rule. Retain its
comparison id, preregistration hash, readiness trigger and fixed decision rule, plus the
frozen scope, before the run. SCHEDULED is terminal for the wave: its decision
procedure is fixed, so the layer waits for its named inputs rather than being relaunched.
A readiness trigger names the inputs whose existence starts the run, with no date.
The comparison starts as soon as those inputs exist.
A comparison whose inputs exist and has not run is a defect.
This is not a reason to re-research.
The term SCHEDULED stays for compatibility and means a comparison pending its named inputs.
It becomes FINAL or RETIRED when the comparison runs and its rule applies.
Preregistered protocol windows, including the holdout boundary and the model seal
before forward scoring, are data-range rules, not schedules.
Use the existing W5 harnesses: promptfoo, token-e2e, cc-native-practice paired runs
and landscape-sweep comparisons; introduce another only through its adoption
decision.

**RETIRED:** the role is retired with a recorded reason (condition 4); retirement
does not claim a qualified winner or an E2E adoption.

**Non-terminal:** everything else, including pending lanes, reopened, unswept,
`no_selection` or no-winner without a scheduled comparison, and still undecided.
`no_selection` must name its comparison in `open_gaps`, including the comparison
id, preregistration hash, readiness trigger and fixed decision rule above, to qualify as
SCHEDULED. No-winner without a scheduled comparison is not allowed;
still undecided cannot be a terminal state. A catalog status alone is not a
terminal state.

The W6 plan assigns machine enforcement of FINAL to a follow-up
`scripts/final_stack.py --check` after W4 PR 2. At this base those files
are not present; this decision does not claim that generator has run or that
any layer is FINAL. The existing catalog statuses (`pending_lanes`, `recorded`,
`no_selection`) retain their meanings and are not aliases for FINAL.
K=3 saturation remains a separate sweep count, not a FINAL verdict or a claim
that this wave reached saturation.

## Alternatives and consequences

A new full survey on every launch discards retained adjudication work. Closing
a layer from a selected pin alone omits native lifecycle and invoke evidence.
Leaving a no-winner row without a comparison's named inputs postpones the decision
indefinitely. The chosen protocol reuses the existing verdict, sweep and
comparison pipeline, and requires only a short always-loaded AGENTS.md pointer.

The doc test pins the normalized Terminal states and evidence section exactly,
while allowing whitespace reflow. Separate checks cover the AGENTS.md pointer,
scheduling-date vocabulary and selected Decision phrases. Widening coverage of
the Decision phrase checks has not been measured. These are repository-text
checks, not research behavior or runtime adoption.

Change this protocol through a new reviewed decision if sweep evidence shows
that its delta boundary loses a material candidate or its completion criteria
misclassify a layer; retain this record as superseded history.

## Sources and verification boundary

- Governance authority: the CC-approved W6 plan snapshot and hash above, and the
  CC's 2026-10-11 06:12Z terminal-state ruling retained in
  `~/.local/state/native-agent-stack/coordination/command-center/research-cc-role-20261008/pr1008-claude-read-95b27707.md`,
  SHA256 `42e3e24ec9ee2e06288b6f6cba407b741e585ca93cef5e738f3f93535258c8de`.
- Readiness amendment: the CC's 2026-10-11 17:31Z ruling retained in
  `~/.local/state/native-agent-stack/coordination/command-center/research-cc-role-20261008/ruling-no-schedules-proceed-when-ready-20261011.md`,
  SHA256 `dd05310efdb514b2886bb55a292176352f51f7d161345d8335e33d6285d191f2`.
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
