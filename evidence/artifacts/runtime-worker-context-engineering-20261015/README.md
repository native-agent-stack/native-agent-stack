# Runtime-worker context engineering, 2026-10-15

Status: **CANDIDATE designs for a future TRIAL; research only**. Base `8053f14e7e0817d2502dff2bb284bfb7e1b0152f`.

The candidate policy keeps the harness's native compaction and session store, adds a small worker-owned current-state file and a verifiable handoff, and proposes fresh sessions at selected boundaries. Whether a fresh session beats native resume *within the same unfinished task* remains an unrun paired comparison. No new percentage threshold, memory product, framework default or autonomous context manager is adopted here. A context lead is an unresolved practice need; the file format below is one candidate, not its required definition.

The convergence correction of 2026-10-15 20:48Z withdraws the CC's 20:45Z context-lead definition and treats CC-designed practice specifics as candidates. This proposal predates that definition and does not rely on it. The implementation particulars here—including note fields, 4/8 KiB budgets and relaunch heuristics—are lane-designed candidates, supported by analogous upstream mechanisms but without matched evidence of improvement. They become practice only through upstream evidence at a pin and measured runs agreeing, under the resolution protocol. Other CC proposals about assignment matrices, halt/session mechanics, charters and horizon enforcement are not adopted by this research.

| Record | Purpose |
| --- | --- |
| [Protocol](protocol.md) | Re-verifies resolution steps 1–3, cumulative survivors, input hashes and two corrections to the supplied record. |
| [Vendor mechanisms](mechanisms.md) | Per-harness compaction, summaries, restart, memory, context-lead building blocks and accounting; pinned source or dated vendor URL for each. |
| [Survivor fit](survivors.md) | Bounded fit adjudication for the carried token, memory and skills candidates; no layer-wide reopening or catalog change. |
| [TRIAL policy and handoff](policy-trial.md) | Native thresholds, safe relaunch boundaries, one maintained context lead and the handoff template. |
| [One preregistration](comparison.md) | A within-Claude-worker boundary comparison on the existing paired-runs harness; named missing inputs and fixed rule. **Not run.** |

The work covered Pi and OpenCode trial profiles from #1033, native Muse only through its existing fence, and Claude Code workers. It excludes command-center orchestration, its context lead, trading execution and model-route selection. PR #1174 Decisions 5–6 were read at head `8b28bbda7dca372baa8026ca0bc6dce21b5b5626`; they remain an open proposal, not landed authority to install anything.

Evidence classes: vendor mechanisms and policy-fit judgments are `source_review`; empty-home Pi/OpenCode version queries and the Claude version query establish only installed version strings. No compaction, inference, model benchmark, memory query, install or Muse invocation was performed. Existing receipts are cited as dated measurements, not rerun results. No token/cost saving or quality parity is claimed.

Named gaps:

1. **G1: native source parity.** OpenCode's shared binary reports `2.0.27`, unlike #1033's qualified `1.18.35`. Pi `1.1.0` has compaction documentation drift at the same version. Requalify changed mechanisms before use; this PR does not migrate or repair profiles.
2. **G2: Muse pin coverage and fence compatibility.** Current public docs do not establish numeric compaction thresholds, summary schema or token-event completeness at installed `1.4.7-R6101.1`. Hooks/plugins stay masked, and native resume cannot be assumed to work through the fence's fresh-log contract.
3. **G3: context-lead semantics.** None of the reviewed harness contracts supplies a continuously verified, shared cross-harness context lead. The proposed file is human/worker-maintained state, not a new service or hook.
4. **G4: complete accounting.** Cross-harness parity for compaction, retries, title generation, child runs and cache accounting is unmeasured. Muse's public event schema and Agent Console's inaccessible retained pin remain unresolved.
5. **G5: paired-run custody.** The existing planning_2b records are retained, but its driver and fixture manifest are not. The harness owner must supply/seal them and support the specified resume/fresh contrast before execution. No synthetic substitute or invented command is offered.
6. **G6: quality evidence.** Retrieval/compression claims from survivors do not establish same-task handoff quality or provider savings in these worker profiles. The single comparison tests the native boundary policy only, not every memory/compression product or framework.

Replace this proposal when the named comparison shows a different worker policy at quality parity and lower complete consumption, or vendor changes invalidate a cited mechanism. Existing convergence and fence gates still apply.
