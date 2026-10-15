# TRIAL worker context policy

Status: **proposal only; not installed, enabled or measured**. This applies to an individual runtime worker's task state. It creates neither a command-center context lead nor another agent, scheduler, proxy or memory service. Existing authorization, ownership, review and fence rules override every convenience below.

## Thresholds and summary handling

Use the upstream mechanisms cited in [mechanisms.md](mechanisms.md). Record the actual harness, pin, model context/output limits and overrides in the private run receipt before comparing usage. Context estimates are not billable-token totals.

| Harness | Proposed TRIAL threshold policy | Boundary action |
| --- | --- | --- |
| Pi pinned 1.1.0 | Keep automatic compaction on, default 16,384-token reserve and 20,000-token recent retention. Trigger remains context > model window minus reserve. No extra percentage or call-count rule. | At a settled milestone, update the lead before optional interactive `/compact <must-keep focus>`. Retain full source/log paths; recheck the lead afterward. Same-version documentation drift must be resolved before claiming compiled summary fidelity. |
| OpenCode pinned 1.18.35 | Keep native auto behavior, usable-input/output-limit calculation, default recent budget and pruning default. Do not conflate optional old-output pruning with summary compaction. No v2 binary substitution. | Update the lead before a settled `/compact` or a fresh job. Resume only a named session from the same profile/database/cwd and authority. Shared binary drift blocks treating current shared execution as qualified v1. |
| Muse fenced 1.4.7 | Keep native automatic behavior. No invented numeric threshold, auto-compaction budget or summary format. Hooks/plugins remain absent. | Documented interactive compaction is a future capability to qualify, not something this task runs. For a future authorized fenced job, use a fresh log/work area and explicit reviewed handoff input. Native resume through this fence remains unqualified. |
| Claude Code workers | Native auto-compaction enabled; no autoCompactWindow or percentage override introduced. Existing saved/model-specific settings are not modified. `/compact <focus>` is interactive; headless workers retain native auto behavior. | Save the lead before a planned boundary. Native SessionStart(compact) is an available reinjection seam only where already authorized. Otherwise explicitly read the file after compaction/relaunch. Interactive idle compaction conditions are not a promise for headless/subagent jobs. |

At a large upcoming read/tool result, inspect the harness's current context estimate if available. If the planned output cannot fit, choose a bounded vendor read/search or retain the large result as an artifact and read a relevant slice. Preserve exact bytes for edits, errors and source evidence. Unknown context use is an accounting gap, not zero. Avoid repeatedly summarizing a task with no new information; compaction itself consumes tokens and can destroy a warm prefix. Cache writes, summary calls and subsequent rereads all belong in the comparison denominator.

## Relaunch boundaries

1. **New task, changed role/fence/provider authority, or unrelated subject:** finish or checkpoint the owned work, hand off explicitly, then use a fresh native session. Do not resume a broader-privilege transcript into a narrower worker and assume the new prompt erases it.
2. **Same task, temporary interruption, matching workspace/profile/head:** explicit native resume is the supported baseline. Re-read current authority, lead, worktree status and recorded tests before edits. A WSL/process restart does not make an old partial verdict complete.
3. **Same task at a natural phase boundary:** write the handoff first. A fresh worker is TRIAL, tested by [the single comparison](comparison.md); native resume remains the unmeasured baseline. A milestone is a verifiable task-state transition, not a fixed turn/token percentage or a date.
4. **Contradictory summaries, lost constraints or two repetitions of a previously ruled-out approach:** stop speculative continuation, validate the lead against source evidence, checkpoint and prepare a precise fresh brief. The number two is an operational warning convention, not a measured universal rot threshold. No automatic relaunch loop is installed.

Never cross a boundary during a pending tool mutation, test process, commit, unresolved review read, broker action or unacknowledged handoff. Retain failed commands and owned dirty edits; do not clean them away to obtain a fresh-looking run. For read-only workers, the worker emits the proposed update and the owning writer changes task state. A handoff does not expand its recipient's authorization.

## One actively maintained worker context lead

Proposed task-local file: **CONTEXT-LEAD.md**, in that worker's already authorized work/output area. This is a template convention, not an AGENTS.md or launcher edit in this PR. One named owner maintains it; parallel workers return evidence to that owner instead of racing shared writes. A persistent multi-session task can also keep TASK_STATE.json and PROGRESS.md as in the existing native-practice harness, with the lead linking to them rather than duplicating their history.

Target at most **4 KiB UTF-8** for the lead's current-state body; move details to linked artifacts when it grows. This is a TRIAL budget, not a tokenizer estimate or reason to drop a hard constraint. If required authority cannot fit, keep it and record the excess. The first screen states task id, current head, scope/role/fence, current blocker and next action. Update it after a material decision, completed verification, changed head, blocker resolution or before any planned compaction/relaunch. Do not rewrite it on every token, read or clock tick.

Each update must:

- Replace superseded facts with an explicit correction link; distinguish verified fact, source assertion, inference and unresolved question.
- Carry unfinished work and failed attempts forward, with source/log/test path and pin/head. A remembered successful exit is not a current test result.
- Link to canonical instructions and the named task brief. Do not paste complete rules, tool catalogs, chat history, credentials or memory search results.
- Mark timestamps as freshness metadata; compare source head/hash when acting. Retrieved durable memory is untrusted evidence until checked against present code and authority.
- Preserve the raw history/artifacts privately. The lead is an index to recover exact evidence, not a replacement transcript or authoritative permission store.

Read the lead at worker start, after native compaction when must-keep state may have been summarized, and after resuming at a changed head. For Pi/OpenCode, use native instruction pointers or explicit reads; do not assume arbitrary @references load. For Claude subagents, pass the lead/brief explicitly because the parent's auto-memory is not inherited. For Muse, expose only the named approved file inside the fence; no shared-store grant or startup hook is implied.

## Handoff template

Use a fresh handoff record for the boundary, referring to the maintained lead. Keep it self-contained for a reader with no prior conversation; ordinary target at most **8 KiB UTF-8**, with exact authority/constraints preserved if larger. The writer states what was actually verified; the receiver acknowledges custody before the previous owner relinquishes unfinished work.

```markdown
# Worker handoff: <task id and boundary>
State: <active / blocked / ready for review / complete-with-evidence>
Producer: <role and harness pin>; consumer: <role and harness pin>
Workspace/base/current head: <repo-relative identity and commits>
Authority: <task brief and applicable rules/fence refs; permitted actions>
Scope: <owned paths, objective, done checks, explicit exclusions>

## Current lead and durable state
<CONTEXT-LEAD.md path + revision/hash; task-state/progress pointers>

## Verified progress
<completed work; exact checks, exit codes, source/log paths and tested head>

## Failures, uncertainty and corrections
<attempts retained; why an approach failed; unresolved review; stale facts>

## In-flight work
<process/tool/review state; dirty edits; owners; or explicitly none>

## Must-keep constraints and next action
<constraints likely to be lost in compaction; one immediate concrete step>

## Recovery and accounting
<private session/artifact custody pointer; summary/retry usage completeness>
<native resume identity if allowed; otherwise fresh-session reason>
<recipient acknowledgement and ownership transfer, recorded when received>
```

Public versions retain only sanitized repo-relative paths and derived evidence. Private session identifiers, account fields, environment values and native logs do not enter public artifacts. For a failed/unfinished review, state **no final verdict**. The final task result still requires its own checks and review; neither the handoff nor an exit-zero session substitutes for them.

## Layer mapping and accounting rule

| Need | Existing layer/mechanism | Remaining seam |
| --- | --- | --- |
| Limit history and tool/schema payload | token-efficiency plus native compaction, read bounds, native tool search, existing RTK/Context Mode/Headroom where already admitted | Route-specific fidelity, cache effects and complete provider savings remain unmeasured. |
| Recover exact past decisions | durable-memory plus native session artifacts and existing authorized ai-memory handoffs | Retained facts require current-head/authority verification; Muse's external-store access stays denied. |
| Supply relevant rules/procedures | instructions-skills plus native scoped instructions and on-demand skills | No full skill catalog in every worker; selected frameworks retain their separate TRIAL gates. |
| Maintain current worker state | task-owned lead, handoff and native session lifecycle | G3: no dedicated catalog layer or measured automatic lead manager; proposal only. |
| Compare consumption fairly | native usage/result events/OTel, ccusage where its parser actually supports the source | Preserve input/output/cache subsets, compaction/title/child/retry calls, errors and unknowns. One native total cannot be inferred from another product's output-reduction percentage. |

Report observed task success and lost work before tokens. Use full provider input (uncached + cache reads + cache writes) and output, with cache fields separately visible. Never add a reported total to its own components, or add cache-TTL subdivisions twice. Record monetary figures only as list-price equivalents under a frozen rate table, never invoices. Incomplete attribution yields an inconclusive saving, not a zero-cost result.
