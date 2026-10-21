# Decision: a standing maintenance consolidation cycle with self-reflection (2026-10-17)

**Status:** proposed for the command center's (CC) review. It follows the owner's direction of 2026-10-17 (paraphrased,
not quoted): run a maintenance consolidation cycle with automatic self-reflection as the lasting way of working, with
every finding backed by exact upstream source evidence.

It changes no existing CI check, unit, catalog row, model setting or host file. Its one addition to the suite is a test
that pins this record's required structure (`tests/test_consolidation_cycle_record.py`). The detector count, unit
templates, inputs ledger and citation resolver it names are follow-up changes, each with a test that fails before it.

**Base:** `origin/main` at `059bd1a660fadb31deec016628f11ef7b8d2be83`. Every `path:line` of this repository below is at
that commit.

Upstream lines are at the commits in their links:

- most were read in local mirrors of those repositories;
- the Letta Code lines come from raw files whose git blob hashes equal upstream's at the linked commit.

**Supersession:** none. This record applies `AGENTS.md:8`, the
[layer-resolution protocol](2026-10-11-layer-resolution-protocol.md) and the
[zero-tolerance record](2026-10-17-zero-tolerance-currency.md). It changes none of them.

## Why

- **What the repository rules already require.**
  - `AGENTS.md:8` requires that every result lands "as a reviewed, cited record (a pull request, decision, manifest or receipt) that the next session starts from".
  - Under the same line, "Work starts when its named inputs exist, never on a date".
  - Also under `AGENTS.md:8`, a claim or fix that proves wrong is resolved "from the upstream primary source at the pinned version", recorded "with its citation", and covered by "a regression test that fails before the fix".
  - `AGENTS.md:19-23` makes that last part a review rule.
- **What happened on 2026-10-17.** A run of quiet failures was caught late and fixed by hand. Each failure stands for a class that recurs:
  - A line citation broke when its file shifted (#1249). #1251's head `b4812bac` re-points nine more atlas citations, and one of them is the same quota-gate citation, now at `:79`.
  - A catalog row kept a background model that its client had stopped defaulting to (#1250). The change is in the client's [`CHANGELOG.md:642`](https://github.com/anthropics/claude-code/blob/c017428c8c27e604840435048d5bce6a9a22c040/CHANGELOG.md#L642).
  - Lane generators enabled a web-search route that the gateway does not serve (#1251). The route is recorded absent at [2026-10-06](2026-10-06-codex-omniroute-opt-in-search.md) `:52-54,121`.
  - A service's port differed from its record, `2026-10-08-qmd-shared-mcp.md:4,130`. Ports are explicit, private host allocations (`2026-10-16-new-wsl-host-allocation-addendum.md:12,20`).
  - A merge check logged an exit status read after a command substitution in the same string, so it always read 0. The same pattern sits in a tracked history script, `blueprints/memory-lifecycle-v2/history/upstream-final-round-driver-20260926.sh:8,11,13`. Its log's `exit=0` lines (`….log:5,7,9,11,13`) therefore carry `date`'s status.
  - A token-saving ratio was withdrawn: a token trimmed once is also skipped on every later re-send. A paired same-task run then measured the effect.
  - A first-run watcher alerted on every old pull request because it had no baseline.
  - Workflow agents stopped at a usage limit.
  - Codex `ultra` was taken for deeper than `max`.
  - Gateway compression for Codex traffic was reviewed and kept off. The research found no engine at the running release that is both lossless and cache-neutral for that traffic; the first cycle re-reads that finding at the pin.
  - The repository move left functional references on the old path.
  - Codex instruction loading turned out to have no `@` include.
  - A memory gate counted reclaimable page cache as used.
- **What exists already, and what does not.**
  - Upstreams already ship most pieces of such a cycle (see "Mechanisms reused").
  - This stack does not run them as one loop.
  - Claude Code 2.1.302 ships no consolidation of its own auto memory. That negative finding is scoped to a search of its changelog and memory documentation for "dream" and "consolidat".

## Decision

### 1. Inputs and triggers

- **Inputs, never dates.** A cycle fires only when an input exists (`AGENTS.md:8`; protocol `:92-94`). A schedule runs only zero-token detection. No date, weekday, session start or usage meter starts a cycle, and no required check compares dates (zero-tolerance `:23-25`).
- **Fire inputs.** Any one of these fires a cycle:
  - **F1.** A correction: a recorded claim, fix, count or citation proved wrong.
  - **F2.** A recurrence: a new input whose root cause matches a lesson already recorded. The lesson is escalated into a mechanism (a hook, test or check).
  - **F3.** Auto-memory load pressure: the `MEMORY.md` index at 90% of the documented load limit or more. Claude Code loads "The first 200 lines of `MEMORY.md`, or the first 25KB, whichever comes first", and "Content beyond that threshold is not loaded at session start" ([memory docs](https://code.claude.com/docs/en/memory), read 2026-10-17).
  - **F4.** A nonzero currency count with no owner lane. The cycle assigns an owner and records the detection gap; dispatch stays with the zero-tolerance record's lanes (`:134-140`).
  - **F5.** A new release of an upstream the cycle reuses.
- **Accumulated inputs.** These are hygiene findings:
  - **A1.** Memory-store lint findings.
  - **A2.** Retention-sweep dry-run candidates.
  - **A3.** Stale knowledge pages.
  - **A4.** Instruction-file audit proposals.
  - **A5.** Memories whose citations no longer resolve.
  - **A6.** Duplicate memory topics.

  They add weights and fire a cycle when the sum reaches K. The initial K is 10, an **untested boundary**. K is tuned from
  the false-fire and miss rates under section 5, and each change to it is recorded as an input. The shape is
  Generative Agents' importance-sum trigger, whose threshold of 150 is tuned for that paper's sandbox.
- **Detection.**
  - The daily stack-currency run stays as it is (`adoption/templates/systemd/stack-currency.timer:14-16`).
  - A new six-hourly oneshot runs the same detector, `scripts/currency_due.py`, with the same arguments as the daily run. It gains one count, `consolidation_inputs`, read offline from two sources: an append-only inputs ledger in the CC's private state, and the auto-memory index size.
  - The index path comes from a setting in that state directory, not from a flag. A flag on one unit only would make the two runs write different counts to the same due-file. Any new `ExecStart` flag would also have to appear in the notice's command (`adoption/templates/systemd/stack-currency.service:28-30`).
  - This is the pattern the surface-watch count already uses (`scripts/currency_due.py:29-40,116-125`).
  - A missing ledger is a coverage gap, never "nothing due" (`:52-60`).
  - The new run makes no network call and reads no credential. It runs at idle priority, as `adoption/templates/systemd/stack-currency.service:58-59` does.
  - Timer settings follow [`systemd.timer` `OnCalendar=`](https://github.com/systemd/systemd/blob/b3d8fc43e9cb531d958c17ef2cd93b374bc14e8a/man/systemd.timer.xml#L190-L200) and [`Persistent=`](https://github.com/systemd/systemd/blob/b3d8fc43e9cb531d958c17ef2cd93b374bc14e8a/man/systemd.timer.xml#L384-L391), at systemd v259.5, the host's version.
- **Never at session start.** The session notice prints the due line only, and dispatch happens in a lane (zero-tolerance `:104-105`).
- **Paper window.** Heavy steps skip the paper window that `adoption/templates/systemd/upstream-surface-watch.service:26-29` encodes. This is the protected window of `AGENTS.md:8`.
- **Single flight.**
  - One cycle runs at a time. This is the single global lock of [Codex memories Phase 2](https://github.com/openai/codex/blob/83086188ae0614bd882818ff1aa23f3194962012/codex-rs/memories/README.md#L79-L92).
  - Inputs that arrive mid-cycle queue for the next one.
  - The accumulation counter resets only on a successful cycle. That is Letta Code's step count "since last successful reflection" ([`memory-reminder.ts:236-245`](https://github.com/letta-ai/letta-code/blob/5cc742b452e39ba0b00eb643b48fa8c8c5ac60b3/src/cli/helpers/memory-reminder.ts#L236-L245)).

### 2. Steps

The CC owns the cycle. Routing follows the owner's 2026-10-17 tiering: GPT reads evidence, Sonnet builds, Haiku does
mechanical work and Opus adjudicates. It stays within the [2026-10-12 routing record](2026-10-12-model-effort-routing.md):

- Gate work stays on Opus (`:39-44`).
- Haiku is a per-launch choice for mechanical work (`:31-35`). No Haiku 5.5 trial is recorded, so each Haiku output is checked by a script, and a failed check re-runs the step on Sonnet.

| Step | What it does | Reuses | Owner | Route |
|---|---|---|---|---|
| S0 Detect | Counts inputs; writes or removes the due-file | `scripts/currency_due.py`; systemd timers | Timer | None (zero tokens) |
| S1 Intake | Collects store health with dry runs only; dedupes each input against open PRs, branches, runs and memories; names each input's owner | ai-memory [`memory_briefing`](https://github.com/akitaonrails/ai-memory/blob/11ca7c5b3b65e7fc216c7eae5a9aac67d38c11ea/crates/ai-memory-mcp/src/server.rs#L6211-L6233) (no LLM call), [`memory_lint`](https://github.com/akitaonrails/ai-memory/blob/11ca7c5b3b65e7fc216c7eae5a9aac67d38c11ea/crates/ai-memory-mcp/src/server.rs#L3695-L3699) with its [rule layer](https://github.com/akitaonrails/ai-memory/blob/11ca7c5b3b65e7fc216c7eae5a9aac67d38c11ea/crates/ai-memory-consolidate/src/lint.rs#L1-L14), [`memory_forget_sweep`](https://github.com/akitaonrails/ai-memory/blob/11ca7c5b3b65e7fc216c7eae5a9aac67d38c11ea/crates/ai-memory-mcp/src/server.rs#L3622-L3647) with `dry_run`; Hindsight knowledge-page staleness; Claude Code `/doctor prompt-audit` ([`CHANGELOG.md:1562`](https://github.com/anthropics/claude-code/blob/c017428c8c27e604840435048d5bce6a9a22c040/CHANGELOG.md#L1562), propose-only); Hindsight `reflect` as a cross-check for unlogged corrections | CC | Haiku, script-checked |
| S2 Evidence | Reads each input's primary source at the installed pin and returns `repo@commit:path:line` with the anchor text and the evidence class. Disagreeing sources are stated, not settled by choice | Local upstream mirrors | GPT lane at effort max; Muse when GPT is at its limit (the exhaustion is reported, never rationed) | GPT |
| S3 Reflect | Writes one lesson per failure and assigns one disposition per input: (a) correction record, (b) code fix with a fail-first test, (c) memory update, (d) practice page, (e) owner assignment, (f) owner-only act, (g) no change | Reflexion's failure-triggered verbal self-reflection; Generative Agents' questions, evidence and cited insights; Letta Code's filters ([`reflection-v2.md:88`](https://github.com/letta-ai/letta-code/blob/5cc742b452e39ba0b00eb643b48fa8c8c5ac60b3/src/agent/subagents/builtin/reflection-v2.md#L88), "If nothing survives filtering, make no changes") | CC | Opus max |
| S4 Memory | Verifies each touched memory against code or upstream; fixes contradictions at the source ([`:102`](https://github.com/letta-ai/letta-code/blob/5cc742b452e39ba0b00eb643b48fa8c8c5ac60b3/src/agent/subagents/builtin/reflection-v2.md#L102)); merges duplicates; archives stale entries rather than deleting them ([`:104`](https://github.com/letta-ai/letta-code/blob/5cc742b452e39ba0b00eb643b48fa8c8c5ac60b3/src/agent/subagents/builtin/reflection-v2.md#L104)); keeps the index inside the load limit; hashes the memory directory before and after and lists every archived or merged file by name | Letta Code's pattern; ai-memory's feedback and sweep tools, used as shipped; Hindsight's own [refresh](https://github.com/vectorize-io/hindsight/blob/39c65ffe2f140d0c84cee58566cad8900c5b9908/hindsight-api-slim/hindsight_api/engine/consolidation/consolidator.py#L2207-L2215), never reimplemented | CC | GPT for claims, Sonnet for edits, Haiku for mechanics, Opus to approve each merge and archive |
| S5 Build | Builds the cycle's records PR and the unowned code fixes. Each code fix carries a regression test that fails on the previous head with only the test files overlaid | `.github/pull_request_template.md`; `scripts/validate.py` | Builder in its own clone | Sonnet; Opus for gate-relevant code (`2026-10-12` `:26,37`) |
| S6 Review | Two model families read each head. The higher severity governs, and a P1 from either family blocks. One fold commit per head | The repository's review practice | CC | Claude and GPT (or Muse); Opus adjudicates disputes |
| S7 Land and record | Lands after both families pass; writes the cycle receipt; closes ledger rows with new rows | `tools/landing/` | CC | Haiku, script-checked |
| S8 Self-measure | Computes section 5's metrics; proposes changes to K and the weights as inputs; turns each recurrence into a mechanism | Earlier receipts | CC | Opus |

### 3. Outputs

- **One reviewed records PR per cycle.**
  - Each is labelled `lane:foundation` and has a `### SOTA sources` section and an evidence-class table (`.github/pull_request_template.md:17-20`).
  - It holds a dated cycle record, new files that amend hash-bound records, practice-page updates and small unowned fixes.
  - An item that already has an owner PR stays in that PR; the cycle PR links it.
  - Trading items go to the trading lane (`AGENTS.md:15`).
- **Memory updates.**
  - Each memory is verified against code or upstream.
  - Stale entries are archived and duplicates merged. Nothing is deleted without a by-name list and the CC's approval.
  - The index stays inside the load limit, so no entry stops loading unnoticed.
- **A cycle receipt.**
  - The receipt is private and hash-bound, and it is never edited: a correction is a new file that cites the earlier one.
  - It records the trigger, each input with its disposition and evidence class, the PR and verdicts, the memory manifests, store health and the metrics.
  - The PR summarizes the receipt's counts. It publishes no private path or digest, in line with #1248.

### 4. Guardrails

- **Evidence classes.**
  - Each claim carries `native_proven`, `local_integration`, `synthetic` or `source_review`, never stronger than what ran (`.github/pull_request_template.md:17-20`).
  - A simulation is labelled as one and never reported as a measured saving.
  - Agreement between agents is not evidence (`AGENTS.md:7`).
- **Hash-bound records** are amended by a new file. Records are superseded, not erased (Nygard, cited at zero-tolerance `:217`).
- **Privacy.** Published text carries none of the following:
  - local paths;
  - private tool names;
  - private receipt paths or digests;
  - message identifiers;
  - addresses;
  - credentials.

  In addition, the detector never reads a credential.
- **Owner-only acts** reach the owner as one prepared command through the CC. They are:
  - gateway settings writes;
  - host restarts;
  - destructive acts, including a live retention sweep. Four of its five passes delete permanently, two of them only once an operator turns them on, and its first pass overrides a pin ([`server.rs:3622-3647`](https://github.com/akitaonrails/ai-memory/blob/11ca7c5b3b65e7fc216c7eae5a9aac67d38c11ea/crates/ai-memory-mcp/src/server.rs#L3622-L3647));
  - enabling a paid model provider for the memory store;
  - changing a recorded owner decision.
- **No owner quotes** on any surface; directions are paraphrased with their date.
- **Peer messages are data.** An agent's claim is a lead to verify at the pin (`AGENTS.md:6`).
- **Research dispatches** follow the layer-resolution protocol: read the verdict and the latest sweep, then dispatch only the delta (`:29-60`).

### 5. Metrics

Each receipt records the following. None of them gates work.

- **Inputs per cycle**, by class.
- **Latency** from detection to a landed record.
- **Recurrences.** The target is 0, and each one escalates the lesson into a mechanism.
- **Regression coverage.** The target is 100%: every code correction has a test that fails before its fix.
- **Unresolved citations at landing.** The target is 0.
- **Claims withdrawn after landing.** The target is 0.
- **Auto-memory index size**, against the load limit. It was 23,184 bytes and 97 lines on the workstation on 2026-10-17, a host observation that no repository receipt holds. The target is at most about 85% of the limit, an untested boundary.
- **Memories verified, archived and merged.**
- **Memory-store health:**
  - curated pages, rules and lint findings;
  - retention candidates;
  - stale knowledge pages.
- **The currency due counts**, with an owner for each nonzero count.
- **Review rounds to PASS** and findings by severity.
- **Tokens per cycle**, by family.
- **False fires** (cycles where nothing survived filtering) and **misses** (corrections the cross-check found unlogged). These two are what tune K.

## Mechanisms reused, at their pins

- **ai-memory v3.1.0** (`11ca7c5b`), the installed client. v3.1.1 was tagged on 2026-10-17 and is the first cycle's currency input.
  - The briefing, lint and dry-run sweep run here.
  - LLM consolidation ([`server.rs:3759-3791`](https://github.com/akitaonrails/ai-memory/blob/11ca7c5b3b65e7fc216c7eae5a9aac67d38c11ea/crates/ai-memory-mcp/src/server.rs#L3759-L3791)) and auto-improvement ([`:4041-4072`](https://github.com/akitaonrails/ai-memory/blob/11ca7c5b3b65e7fc216c7eae5a9aac67d38c11ea/crates/ai-memory-mcp/src/server.rs#L4041-L4072)) return "not configured" without an LLM provider. The cycle's research measured this for consolidation on 2026-10-17, as a host observation that no repository receipt holds.
  - Enabling a provider is a separate decision.
  - Auto-improvement's approval default is [`require_approval: false`](https://github.com/akitaonrails/ai-memory/blob/11ca7c5b3b65e7fc216c7eae5a9aac67d38c11ea/crates/ai-memory-cli/src/config.rs#L1702), so a host that enables it must set `require_approval = true` to keep manual review (the key name is in [`server.rs:4050`](https://github.com/akitaonrails/ai-memory/blob/11ca7c5b3b65e7fc216c7eae5a9aac67d38c11ea/crates/ai-memory-mcp/src/server.rs#L4050)).
- **Hindsight v1.0.0** (`39c65ffe`), the running server.
  - Consolidation runs automatically after retain ([`observations.mdx:41-48`](https://github.com/vectorize-io/hindsight/blob/39c65ffe2f140d0c84cee58566cad8900c5b9908/hindsight-docs/docs/developer/observations.mdx#L41-L48)).
  - A mental-model dry-run refresh persists nothing ([`api/mental-models.mdx:440-446`](https://github.com/vectorize-io/hindsight/blob/39c65ffe2f140d0c84cee58566cad8900c5b9908/hindsight-docs/docs/developer/api/mental-models.mdx#L440-L446)).
  - The refresh tick is 300 s ([`config.py:2021`](https://github.com/vectorize-io/hindsight/blob/39c65ffe2f140d0c84cee58566cad8900c5b9908/hindsight-api-slim/hindsight_api/config.py#L2021)).
  - Observation history is kept before each update: the function inserts "one pre-update snapshot" ([`consolidator.py:2803-2810`](https://github.com/vectorize-io/hindsight/blob/39c65ffe2f140d0c84cee58566cad8900c5b9908/hindsight-api-slim/hindsight_api/engine/consolidation/consolidator.py#L2803-L2810)).
  - A second-family inventory read the server code at the coding-agents plugin tag instead. Its server lines are re-read at `39c65ffe` before use.
- **Claude Code 2.1.302** (`c017428c`).
  - `/doctor prompt-audit` was added in 2.1.283 ([`CHANGELOG.md:1562`](https://github.com/anthropics/claude-code/blob/c017428c8c27e604840435048d5bce6a9a22c040/CHANGELOG.md#L1562)).
  - Dynamic workflows are documented to pause at a usage limit and continue at reset ([`:2472`](https://github.com/anthropics/claude-code/blob/c017428c8c27e604840435048d5bce6a9a22c040/CHANGELOG.md#L2472), 2.1.271). Runs interrupted on 2026-10-17 instead stayed stopped until resumed by hand. That is a host observation, and no repository receipt holds it. The sources disagree, so the first cycle measures this first-hand.
- **Codex rust-v0.163.0** (`83086188`).
  - Memories Phase 2 runs its agent only when the workspace diff is non-empty ([`README.md:139-152`](https://github.com/openai/codex/blob/83086188ae0614bd882818ff1aa23f3194962012/codex-rs/memories/README.md#L139-L152)); the cycle adopts that as its own "act only on inputs" rule. The feature is off on this host.
  - Instruction loading reads `AGENTS.md` bytes as text. A search of those two loader files for "include", "import" and `@` found no include syntax ([`agents_md.rs:150-171`](https://github.com/openai/codex/blob/83086188ae0614bd882818ff1aa23f3194962012/codex-rs/core/src/agents_md.rs#L150-L171); [`instructions/mod.rs:41-79`](https://github.com/openai/codex/blob/83086188ae0614bd882818ff1aa23f3194962012/codex-rs/codex-home/src/instructions/mod.rs#L41-L79)).
  - `ultra` resolves to the catalog's multi-agent effort ([`reasoning_effort.rs:10-40`](https://github.com/openai/codex/blob/83086188ae0614bd882818ff1aa23f3194962012/codex-rs/protocol/src/openai_models/reasoning_effort.rs#L10-L40)). That effort is `xhigh` for gpt-6-astra and gpt-6.1-sol ([`models.json:22`](https://github.com/openai/codex/blob/83086188ae0614bd882818ff1aa23f3194962012/codex-rs/models-manager/models.json#L22), [`:195`](https://github.com/openai/codex/blob/83086188ae0614bd882818ff1aa23f3194962012/codex-rs/models-manager/models.json#L195)), and `ultra` also turns on proactive delegation ([`multi_agents.rs:92-107`](https://github.com/openai/codex/blob/83086188ae0614bd882818ff1aa23f3194962012/codex-rs/core/src/session/multi_agents.rs#L92-L107)).
  - So `max` is the deepest single-agent effort. The coordinator template's `ultra` (`adoption/templates/codex.config.template.toml:1-8`) is a recorded user choice and stays.
- **Letta Code v0.34.16** (`5cc742b4`, the latest release).
  - The reflection subagent runs with Bash and Edit only ([`reflection-v2.md:1-8`](https://github.com/letta-ai/letta-code/blob/5cc742b452e39ba0b00eb643b48fa8c8c5ac60b3/src/agent/subagents/builtin/reflection-v2.md#L1-L8)).
  - Its default trigger is the compaction event, with a 25-step alternative ([`memory-reminder.ts:15,51-56`](https://github.com/letta-ai/letta-code/blob/5cc742b452e39ba0b00eb643b48fa8c8c5ac60b3/src/cli/helpers/memory-reminder.ts#L15-L56)).
  - Letta Code is used as a pattern only and is not installed.
- **Gateway.** OmniRoute v3.8.51 (`c1e30b76`)'s "lite" compression cuts earlier chat-format tool messages to a default of 2,000 characters ([`lite.ts:24`](https://github.com/diegosouzapw/OmniRoute/blob/c1e30b7676975feb298b49eff6ff58923c04b89e/open-sse/services/compression/lite.ts#L24), [`:148-175`](https://github.com/diegosouzapw/OmniRoute/blob/c1e30b7676975feb298b49eff6ff58923c04b89e/open-sse/services/compression/lite.ts#L148-L175)).
  - Compression stays off for Codex traffic, as the [2026-09-27 record](2026-09-27-omniroute-account-pool.md)'s `codex/*` exclusion (`:252`) keeps it.
  - How each engine treats Codex's Responses-format requests is re-read at the pin in the first cycle.
- **Shell status.**
  - In bash 5.3.9, the installed shell, `false; echo "A $(true) rc=$?"` prints `rc=0`. This is a first-hand run.
  - ShellCheck v0.11.0's `$?` checks cover a condition or `echo`/`printf` ([`Analytics.hs:5084-5086`](https://github.com/koalaman/shellcheck/blob/aac0823e6b58f8a499e856e93738082691cbf212/src/ShellCheck/Analytics.hs#L5084-L5086)), not this pattern. That is from reading the source; ShellCheck is not installed here.

## Limits and untested boundaries

- K = 10 and the 85% index target are untested. Section 5's false-fire and miss rates tune them.
- Hindsight's consolidation quality and its stale-page counts are not yet measured here.
- `/doctor prompt-audit` has not yet been run on this repository.
- The page-cache rule behind the memory gate rests on the kernel's [cgroup v2 documentation](https://docs.kernel.org/admin-guide/cgroup-v2.html), read 2026-10-17. Above `memory.high`, processes "are throttled and put under heavy reclaim pressure". The page showed kernel 7.3.0-rc7, while the host runs 6.18 (WSL2), so verifying the rule at the running kernel's source is a first-cycle action.
- **The repository move.**
  - GitHub's [transfer documentation](https://docs.github.com/en/repositories/creating-and-managing-repositories/transferring-a-repository) (read 2026-10-17) says links and `git clone`, `fetch` and `push` redirect.
  - It also says that creating a repository or fork at the previous location deletes those redirects permanently.
  - It says nothing about the API or search. That search does not follow the redirect is a first-hand observation without a receipt.
- This is governance text (`source_review`). No unit, catalog, setting or model changed, and no run measured the cycle.

## Alternatives

- **A calendar cycle**, such as a weekly consolidation. Ruled out by `AGENTS.md:8` and protocol `:92-94`.
- **Turning on the memory store's LLM consolidation, auto-improvement or dream pass now.** These need a paid provider, which is a separate decision with a cost estimate and a cap.
- **Turning on Codex memories as well.** That would add a third store. It is a decision for the Codex lanes, not this record.
- **Installing Letta Code for its reflection subagent.** That is a new harness for one pattern. The pattern is reused instead.
- **A second detector, or timer-driven memory edits.** There stays one detector, and memory changes only through reviewed steps.
- **Fixing each incident without a cycle.** That is the status quo that caught the 2026-10-17 failures late.

## Overturn

- The owner rewords the direction.
- **Measured false fires or misses** show that the fire rule wastes runs or misses inputs. The answer is a recorded change to K or to the classes.
- **A maintained upstream ships one cross-store consolidation loop** that covers these steps. It then supersedes this design through a recorded supersession.

## Sources

- **Repository** at the base:
  - `AGENTS.md:6-8,15,19-23`;
  - `scripts/currency_due.py:29-40,52-60,116-125`;
  - `adoption/templates/systemd/stack-currency.timer:14-16`, `stack-currency.service:28-30,58-59`, `upstream-surface-watch.service:26-29`;
  - `adoption/templates/codex.config.template.toml:1-8`;
  - `.github/pull_request_template.md:17-20`;
  - `blueprints/memory-lifecycle-v2/history/upstream-final-round-driver-20260926.sh:8,11,13` and `….log:5,7,9,11,13`;
  - the records [2026-10-11 protocol](2026-10-11-layer-resolution-protocol.md) `:29-60,92-94`; [2026-10-12 routing](2026-10-12-model-effort-routing.md) `:26,31-35,37,39-44`; [2026-10-17 zero tolerance](2026-10-17-zero-tolerance-currency.md) `:23-25,104-105,134-140,217`; [2026-10-06 search](2026-10-06-codex-omniroute-opt-in-search.md) `:52-54,121`; [2026-10-08 qmd](2026-10-08-qmd-shared-mcp.md) `:4,130`; [2026-10-16 allocation](2026-10-16-new-wsl-host-allocation-addendum.md) `:12,20`; [2026-09-27 account pool](2026-09-27-omniroute-account-pool.md) `:252`.
- **Upstream** at the linked commits:
  - `akitaonrails/ai-memory` v3.1.0;
  - `vectorize-io/hindsight` v1.0.0;
  - `anthropics/claude-code` v2.1.302;
  - `openai/codex` rust-v0.163.0;
  - `letta-ai/letta-code` v0.34.16;
  - `diegosouzapw/OmniRoute` v3.8.51;
  - `systemd/systemd` v259.5;
  - `koalaman/shellcheck` v0.11.0.
- **Documentation** read 2026-10-17:
  - [Claude Code memory](https://code.claude.com/docs/en/memory);
  - [GitHub repository transfer](https://docs.github.com/en/repositories/creating-and-managing-repositories/transferring-a-repository);
  - [Linux cgroup v2](https://docs.kernel.org/admin-guide/cgroup-v2.html).
- **Papers:**
  - Shinn et al., [Reflexion](https://arxiv.org/abs/2303.11366), §3: an Evaluator's failure signal drives a verbal self-reflection, kept in a memory bounded by Ω, "usually set to 1-3".
  - Park et al., [Generative Agents](https://arxiv.org/abs/2304.03442), §4.2: reflection fires when the importance sum of recent events "exceeds a threshold (150" in that implementation.
- Michael Nygard, [Documenting Architecture Decisions](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions), 2011-11-15: supersession rather than erasure.
