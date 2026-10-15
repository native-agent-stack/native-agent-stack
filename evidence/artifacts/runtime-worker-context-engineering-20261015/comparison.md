# Preregistration: worker-context-boundary-20261015

Status: **one unrun paired comparison; TRIAL, pending named inputs**. This is a within-Claude-Code-*worker* contrast, not a test of command-center orchestration/context lead, framework selection or all four worker products. It does not establish policy parity for Pi, OpenCode or Muse.

The lead-note format, byte budgets and boundary strategy are **candidate designs**, not requirements settled by CC practice proposals. This protocol's fixed controls and scoring gates bind only this experiment if later authorized. Holding the state convention equal in both arms isolates history continuity; a positive result cannot separately establish that convention or the byte budgets as practice. The 2026-10-15 20:48Z convergence correction is recorded in protocol.md.

Question: on an unfinished task at a settled boundary, does a fresh worker with an explicit maintained handoff preserve quality and use less complete provider context than resuming the existing native conversation?

## Existing harness and custody

Use **cc-native-practice paired runs, planning_2b**, documented in `evidence/artifacts/native-practice-paired-runs-20261010/paired-runs.json` at base `8053f14e7e0817d2502dff2bb284bfb7e1b0152f`, sha256 `86108379949cf688ae244436f81becac28d94861716ceefbbe794753ba439fa7`. Its F5/F6 design already supports worker task state, forced context loss, hidden grading and retained failures. Do not create a new runner or substitute a toy fixture. No command is provided because the retained records do not contain the driver.

The co-op supplied the following private custody references and this lane re-verified their hashes. These are references to the **prior experiment**, not input hashes for a newly runnable one; no host paths or private run contents are published.

| Retained planning_2b record | SHA256 |
| --- | --- |
| preregistration.md | `fc2e48e57841632203f0a8eca5d32306f79a8c81e61fbfb96444198500b34c71` |
| RESULT.md | `293fe657916adb036514f2ee4ac2f1232baf0e6fe71d53ba521a956a76f88b3d` |
| lost-work-protocol.md | `297413ee073dd0f2037089f24d283d8086d71db77e7a2d9684730464a2c3e36c` |
| analysis.txt | `d75d7876e8a552c7d1e95f69e3fd7a4acfac663283a7d49f9827094127c920bc` |
| batch.log | `d426b326e0bd1a6787bbff0b3944200f93b6e5c0daba2a1f013846a8ab5dd4bf` |
| lost-work/COUNTS.md | `da9ca1977dc32a58b75f812654e7b0435d5307d77fb1ff01e27ac9b82ee3c3cb` |
| lost-work/lost_work.json | `e871e89e37ca1811f1416701cb826cbfd334571fee63437aa0f78dd7c9cb95d5` |

Prior planning_2b used a pinned 2.1.296 client, 30 turns per session, at most 8 sessions, F5/F6 × two trials × three state strategies. All 12 runs passed hidden tests with no counted lost work; task-list/loop alternatives did not win a majority. Those measurements support retaining repo state, not the new resume-versus-fresh decision. Its lost-work readers were not blind. Its 12-turn predecessor was infeasible and remains a failed design, not evidence for lower context limits.

## Frozen arms and controls

| Arm | At each sealed, settled boundary |
| --- | --- |
| A: native resume | Persist the common lead/handoff, terminate the worker process after the turn settles, then continue its exact native session with the same role/fence. Native automatic compaction remains on. |
| B: fresh boundary | Persist the **same common state format**, terminate after the turn settles, then launch a fresh native worker on the same owned task/worktree, receiving the handoff/lead and source pointers without previous conversation history. Native automatic compaction remains on. |

Only session-history continuity differs. Both arms update the lead and receive identical authority, tools, task brief, state-file budget, preflight checks and mandatory evidence. No extra memory/compression plugin, assistant, subagent, hook or framework in B. Both arms use the same admitted Claude worker route, exact model `claude-opus-5-5`, effort `xhigh`, pinned client **2.1.301** (or a reviewed superseding version requiring a new frozen protocol before data), model context/output limits, native defaults and privacy gates. Framework exposure is disabled in both through the existing paired-run fence. That is consistent with pending #1174 Decision 6, and does not uninstall anything on the host.

Reuse F5/F6 source fixtures and hidden oracles through the harness owner. Seal four repetitions per fixture, **8 pairs / 16 runs**, before results. For each fixture seal two task-relevant phase boundaries independently of either arm's output, plus the policy for reaching them and recording a boundary not reached. Same boundaries, tool permissions and budgets in a pair; no result-selected restart point. Alternate AB/BA by fixture-trial index (even AB, odd BA), fixed before dispatch. Both arms retain the planning_2b ceilings: 30 agentic turns per process, 8 processes per task, 3,000 seconds and $15 list-price-equivalent per process. The driver must account for native resume at caps; do not silently turn A into a fresh session. Every exceeded budget, interrupted process and failed attempt is scored and priced.

Use isolated owned clones and separate task-state/memory namespaces per run; no cross-pair learned memory or oracle access. Tool fixtures and initial dependency/cache state are identical within pairs. Retain actual cache usage rather than assuming fresh runs are cold or resumed runs always warm. Do not discard a pair because an arm failed, and do not rerun deterministic failures for a better result.

## Measures and fixed decision rule

Before execution, seal the hidden test manifest, expected failures/regressions and **10 must-keep facts per fixture** (scope, constraints, failed approaches and source/head freshness), with evaluator-only labels. The task brief may expose the relevant facts but not the grading keys. Require at least two actual settled re-entry boundaries in each scored run; if the workload cannot produce that, record the design as infeasible, without moving the boundaries after looking at answers.

Primary outcomes:

1. Existing hidden fail-to-pass and pass-to-pass checks, and the existing exact completion protocol. Completion claims without oracle success fail.
2. Constraint/freshness violations and lost-work events, using the retained lost-work definition (redo or undo of completed work without a justified new requirement/failing check). Score the 10 facts and ownership/scope correctness at each re-entry.
3. Complete provider input and output by run, including summary, internal auxiliary requests, failed/retried attempts, final verification and rereads. Keep uncached input, cache-read and cache-write fields separate; report wall time and frozen list-price-equivalent cost as secondary outcomes. Artifact token reductions are not provider savings.

Use exact tests and two independent readers for lost-work/fact checks; present shuffled run identifiers and suppress arm labels/launch metadata where possible. Handoff wording may reveal the strategy, so disclose residual unblinding. Resolve reader disagreement from source/test/log evidence before aggregating; unresolved disagreement prevents promotion. No judge may change the labels or briefs after seeing an arm.

**Adopt B as a worker-policy candidate only if all conditions hold:**

- B passes every hidden check A passes in each pair and has no additional hard-constraint, stale-head, scope or ownership violation.
- B has no more lost-work events and no lower must-keep-fact score in **every** pair.
- All 8 pairs have complete native usage attribution and two re-entry boundaries; missing usage, missing custody or infeasible boundaries make the result **INCONCLUSIVE**.
- B uses fewer complete provider input+output tokens in at least **6 of 8 pairs**, with at least **10% reduction in the median paired token ratio**, and median paired list-price-equivalent cost ratio **≤1.00**. Count failed attempts; no subset selection.

Otherwise keep A, reporting either a failed quality gate, no demonstrated saving or an inconclusive design as appropriate. This small fixed comparison cannot by itself promote a layer/product to FINAL; multi-angle convergence and other-harness qualification remain separate. No policy threshold is tuned from test results in this experiment.

## Named readiness inputs; no execution authorization here

Owned by **cc-native-practice, the existing harness owner**, with task input custody coordinated by the co-op:

- The retained planning_2b driver, version/hash and its supported native resume/fresh controls, including the corrected `orch_run.parse_statuses` parser. The co-op confirmed no driver script is retained alongside the prior records; it must be recovered or supplied by that owner, not reimplemented by this lane.
- F5/F6 source/base commits, sealed fixture manifest, original briefs, hidden tests and must-keep-fact oracle. No fixture SHA256SUMS is retained alongside those records. Freeze the exact missing inputs before dispatch.
- The two fixed boundaries per fixture and acknowledgement that this existing harness can honor them without a new runner. If it cannot, keep G5 unresolved and revise through review before data; do not improvise an execution command.
- Approved isolated worker configuration at the exact client/model/effort pin, complete/redacted usage capture and a frozen rate table; reviewed version/behavior parity for resume/compaction.
- The single current preregistration file's registered digest, task-packet digest/custody and an explicit later execution authorization. This research-only task authorizes **no keyed run**.

Work starts when these named inputs exist and execution is authorized, never on a date. No comparison was run, no driver was written and no fixture was invented by this PR.
