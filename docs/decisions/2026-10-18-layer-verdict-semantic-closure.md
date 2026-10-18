# Layer-verdict lane: required revisions close findings

2026-10-18. This proposes a maintained NAS correction for source defects identified
by independent Claude/GPT desk review. It changes a reusable example and its
model-free tests; adoption and native pilot activation remain on HOLD pending
two-family review and the caller's native evidence gates. No native Workflow or
provider call was run for this correction.

## Pinned sources and contract

- NAS [`layer-verdict-lane.js` at `6f57256a6db754edb576519ed7803f202b5430a8`, lines 66–114](https://github.com/native-agent-stack/native-agent-stack/blob/6f57256a6db754edb576519ed7803f202b5430a8/examples/claude-native/workflows/layer-verdict-lane.js#L66-L114),
  SHA-256 `fd77b74945e9d2bd0b26b7822aabcde00e7e650c327da16d852fdbfd5984c0d6`.
  Line 105 restores an original major-bearing proposal after a required revision
  is null, unknown or refuted. Line 102 accepts an unrefuted revision even when
  its recheck still has major/blocking findings. Lines 92/99 do not catch errors;
  line 20 filters packet input and line 109 fans out all surviving packets.
- The maintained model-free seam is NAS [`test-envelope.mjs` at the same pin, lines 35–42](https://github.com/native-agent-stack/native-agent-stack/blob/6f57256a6db754edb576519ed7803f202b5430a8/examples/claude-native/workflows/test-envelope.mjs#L35-L42):
  execute the script body with injected agent/parallel/log stubs. The new focused
  Python suite uses that seam with no runtime or provider dependency.
- The caller contract `CLAUDE-GPT-PILOT-ADMISSION-01.md`, dated 2026-10-18,
  SHA-256 `7e090ba3b920138e58aa6ad4beba01ee3773884dd48fbf6d4f13dc820a109645`,
  requires explicit evidence-backed closure of every prior major/blocking finding,
  complete required returns and no unresolved final-round finding.
- `CLAUDE-INDEPENDENT-CRITIQUE-01.md`, dated 2026-10-18, SHA-256
  `928cdb53bfbbe05dc9ce1a2b9fb825d97a496c0961592813986a366298fee2d0`,
  findings 1, 2, 8, 9, 12, 14 and 15 supply the bounded correction/remaining-gate list.
  These caller documents are retained by the requesting project; their native
  identity claims are attributed, not independently measured here.

## Decision and behavior

Require exactly one valid raw packet, a nonblank source view and prompt before
dispatch. Reject malformed/extra packets and the ambiguous `docs` mode rather than
filtering or manufacturing packet identities. Keep the three inline Opus/max
bindings and the existing blind role unchanged. Exactly one chain runs; only its
two refuter lenses run concurrently.

A proposal can be final only after both valid lens votes return without refutation
or major/blocking findings. Once revision is required, the original proposal cannot
become final. A revised final requires two valid, unrefuted rechecks, no new
major/blocking finding, and one explicit `resolved` disposition with cited evidence
for every prior serious finding by its originating lens. Stable finding IDs include
round, lens and original array index. A refutation without a structured serious
finding creates an obligation for the refutation reason itself. Missing, duplicate,
unknown, foreign-lens, blank-evidence or unresolved dispositions do not close it.
Separate independent adjudication is not implemented by this script.

Required null, invalid, failed, refuted or unresolved revisions return unknown with
no final. Raw proposal/revision votes and findings remain; malformed values and
errors retain stage/label/round/lens and exception name/message. Outcomes are
recorded inside each lens thunk, so an orchestration failure cannot erase already
observed votes. Script-visible running and unstarted roles remain explicit if the
runtime stops the group. A source-visible stop cause never guesses a quota limit
from a missing value. Native retry histories still need the native journal.

Top-level `status: complete` means script-visible semantic closure, not accepted
catalog state, proven truth or native terminal/usage closure. Every other return is
`incomplete` with a stop cause; unsuccessful revisions retain raw refutation facts
while their overall judgment is unknown.

`vendored-lanes.json` preserves agent-lab origin as history and explicitly marks
the NAS correction. New workflow/source hashes are added to the existing
append-only provenance registry. This registers source custody, not a native run
or permission to record a FINAL verdict. The collector, shared helper and its
`admission under redesign` guard are unchanged.

## Findings addressed and gates retained

| Finding | Static correction / remaining native obligation |
| --- | --- |
| 1 — loaded code | Current artifact hashes and correction lineage are explicit; bind the actual loaded copy and loader precedence later. |
| 2 — reviewer role | Existing source role hash remains bound; effective discovery, inheritance and confinement still need native proof. |
| 8 — semantic closure | Remove all proposal fallback; require complete rechecks and explicit closure, preserving both rounds. |
| 9 — exceptions | Catch synchronous invocation failures and Promise rejections without discarding earlier judgments or error details. |
| 12 — completion | Return explicit status, stop cause and expected/returned roles; native headless waiting, attempt/journal/terminal closure remain unproved. |
| 14 — one packet | Reject raw cardinality/type errors before dispatch; actual packet bytes, prompt/tree bindings and readset closure remain caller checks. |
| 15 — global producers | One chain has two concurrent lenses; this does not constrain other runs, parent children, advisors or background calls. Global admission/usage gates remain. |

## Validation and alternatives

[`tests/test_layer_verdict_workflow.py`](../../tests/test_layer_verdict_workflow.py)
first failed on the pinned behavior, then passed after each correction. Separate
red/green slices cover unsuccessful revisions and prior-finding closure, raw
packet admission, error/status receipts, then orchestration failure and spoofed
label suffixes. Both positive proposal and explicitly closed revision cases pass.
The generic envelope and mutation suites continue to inspect inline model/effort
bindings. Retained command results are in
[`tests-first.json`](../../evidence/artifacts/layer-verdict-semantic-closure-20261018/tests-first.json)
and [`verification.json`](../../evidence/artifacts/layer-verdict-semantic-closure-20261018/verification.json).
All observations are `local_integration` with synthetic returns, not native proof.

A caller-only rejection rule could hold the old return without changing it; it
would leave misleading successful envelopes and evidence loss for other callers.
A null-only patch leaves unknown/refuted-revision fallback and remaining majors
unfixed. A local deployed fork would diverge without reviewed shared custody. The
maintained NAS correction is preferred for these shared semantics. Reopen this
decision if upstream changes the native orchestration contract or a retained
regression shows the envelope accepts an unclosed finding or loses a failure.
