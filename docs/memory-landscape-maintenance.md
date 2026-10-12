# Native memory selection and active maintenance

This September 21, 2026 review keeps **ai-memory as the shared Codex/Claude memory
of record**. It adds its supported background learning and bounded assistant
summary capture to the existing deployment. Repository discovery is not a local
quality benchmark: the alternatives below are current candidates with different
strengths, not installed winners. Code RAG, document search and transient context
remain separate layers.

The follow-up [native memory/RAG lifecycle guide](native-memory-rag-lifecycle.md)
records fresh cross-client retrieval, stored Claude outcome and consolidation,
current stable-release checks, and the active monitoring contract.

The [September 27 lifecycle follow-up](native-memory-rag-lifecycle.md#september-27-scheduled-follow-up)
supersedes the historical runtime settings below: the current host uses the
prefix-enabled ai-memory build with Nemotron embeddings and vLLM 0.30.0, native
Codex gpt-6-sol at medium effort, and an intentionally paused hourly learning
scheduler. These are observed configuration and previously qualified selections,
not a new quality benchmark. Do not apply the September 21 TOML as current defaults.

The adopted project's pinned `decisions/native-memory-learning-maintenance.md`
records this setup. The older consolidation decision is marked superseded while
its historical body is preserved; both writes were read back through native MCP.

## The selected running layers

| Purpose | Selected upstream | Actual scope |
| --- | --- | --- |
| Cross-client decisions, sessions and handoffs | ai-memory 2.3.2 | One adopted project, allowlisted lifecycle capture, scoped MCP retrieval and local MiniLM embeddings. |
| Session compilation and learning | ai-memory with native Codex provider | Session-end consolidation previously passed in both native clients; this wave exercises native learning, scheduler admission and assistant outcome capture. |
| Conceptual code retrieval | SocratiCode + Qdrant + vLLM/NVIDIA Nemotron 1B | Existing project index and model remain pinned; the [model qualification](hf-memory-model-qualification.md) explains compatibility. |
| Exact source navigation | Serena | Read actual symbols/source after retrieval; the native dashboard describes its active project/tools. |
| Markdown retrieval | QMD | Explicit project collections with BM25; no competing durable memory store. |
| Transient tool context | Context Mode | Bounded execution/search and session context; estimates remain separate from provider consumption. |
| Observation and recovery | Native status/learning reports, Grafana/Loki, upstream backup | Read real outcomes, preserve failures, and restore into an empty target when testing recovery. |

## Landscape decisions

The [source manifest](../evidence/artifacts/memory-landscape-20260921/sources.json)
pins the inspected repository heads and README hashes. The existing installed
ai-memory release remains pinned separately at
`353841d91618d20b110b208de284a74d0b960379`; newer source is not silently installed.

| Candidate | Useful upstream capability | Decision for this environment |
| --- | --- | --- |
| [ai-memory](https://github.com/akitaonrails/ai-memory) | Shared native lifecycle hooks, scoped wiki/MCP, consolidation, audited learning, recovery and read-only web browser. | **Retain and activate maintenance.** It already holds the adopted project's memory and has native client evidence. |
| [Basic Memory](https://github.com/basicmachines-co/basic-memory) | Local Markdown knowledge, MCP and native client integrations; human-editable knowledge workflow. | **Conditional alternative** when collaborative note editing is the principal need. No demonstrated reason to duplicate the current memory of record. |
| [Graphiti](https://github.com/getzep/graphiti) | Temporal entity/relationship graph, MCP and graph-database integration. | **Conditional application layer** for entity/time queries that ordinary project memory cannot answer. Its graph database browser is not a Codex/Claude activity dashboard. |
| [Mem0](https://github.com/mem0ai/mem0) | Application memory APIs and a self-hosted server/dashboard. | **Conditional application SDK**, with isolated identities and provider qualification. A second agent-memory database is not an automatic improvement. |
| [Hindsight](https://github.com/vectorize-io/hindsight) | Retain/recall/reflect, memory banks, coding-agent integrations and a local control plane. | **Priority comparison candidate** if richer inspection or reflective memory becomes a task requirement. Its published benchmark scores do not measure this project's retrieval quality. |
| [Claude-mem](https://github.com/thedotmack/claude-mem) | Plugin capture/compaction, retrieval and a worker viewer. | **Alternative capture system**, not an extra default beside ai-memory. A plugin installation is required; installing its npm library alone does not activate hooks. |
| [Letta / Letta Code](https://github.com/letta-ai/letta-code) | Stateful agents and a separate memory-aware coding runtime. | **Conditional worker architecture**. Replacing native Codex/Claude is outside this memory maintenance change. |
| [Supermemory](https://github.com/supermemoryai/supermemory) | Memory APIs, client plugins and local/self-hosted options. | **Conditional alternative** requiring provider, storage and workload qualification before migration. Published savings belong to its stated benchmark, not this session. |

No candidate was rejected merely for having another database. Adoption requires
an actual question or lifecycle need, a frozen representative corpus, original
source-grounded answers, scoped capture/deletion/recovery, and comparison of
quality, latency and complete provider use. Keep the current store authoritative
during an isolated trial; do not turn on overlapping automatic capture everywhere.

## Supported installation and configuration

Use the pinned upstream [installation guide](https://github.com/akitaonrails/ai-memory/blob/353841d91618d20b110b208de284a74d0b960379/docs/install.md)
and [learning implementation guide](https://github.com/akitaonrails/ai-memory/blob/353841d91618d20b110b208de284a74d0b960379/docs/auto-improvement-loop.md).
On a new host, complete the selected [adoption profile](../adoption/manifest.json),
native sign-in and project marker first. Do not copy this host's credential or
memory database as a substitute for setup.

The selected existing native service now has these explicit settings:

```toml
capture_assistant = true
consolidate_on_session_end = true

[auto_improve]
require_approval = false
min_observations = 8
min_session_duration_secs = 120
min_confidence = 0.75
max_input_tokens = 24000
max_proposals_per_run = 5
include_raw_fallback = false

[auto_improve.scheduler]
enabled = true
interval_secs = 3600
max_sessions_per_tick = 1
min_session_age_secs = 600

[maintenance]
enabled = true
forget_sweep_interval_secs = 0
lint_interval_secs = 86400
embedding_backfill_interval_secs = 3600
```

Within the shown maintenance/scheduler tables, the page-sweep interval (upstream
default 86,400 seconds) and embedding-backfill interval (default off) are the
selected deviations. Learning was disabled in this deployment and is now restored
to the upstream enabled default. Assistant capture and session-end consolidation
are explicit opt-ins.

Merge these fields into their existing tables; do not replace other model,
account, privacy or scope settings. The embedding backfill uses the already
configured local model. Scheduled page/observation forget sweeps are disabled;
the native curator and lint report surface candidates without deleting history.
The existing upstream empty-project cleanup still runs under `maintenance.enabled`
and can remove hollow project rows older than seven days. This is not a claim that
all deletion paths are disabled.

At the 2026-09-21 qualification the upstream installers were run with
`--capture-assistant` for native Claude, native Codex and the Desktop WSL hook
configuration, selecting each existing file explicitly (the arguments and exit
codes, all 0, are retained in
`evidence/artifacts/memory-landscape-20260921/native-commands.json:295-393`).
This is the record of that day, not the hook state now: correction #149 below
gives the state measured on 2026-10-11. The documented forms for Claude and
Codex:

```sh
ai-memory install-hooks --agent claude-code --capture-assistant --capture-mode allowlist --config-file CLAUDE_SETTINGS --server-url MEMORY_URL --apply
ai-memory install-hooks --agent codex --capture-assistant --capture-mode allowlist --config-file CODEX_HOOKS --server-url MEMORY_URL --apply
```

**Correction, 2026-10-10 (CC correction #144).** On the current host (ai-memory 2.6.0), `<data_dir>/capture-mode` was absent, so lifecycle capture ran in the default denylist mode and captured every directory, including scratch and test worktrees. The installer writes that file only under `--apply` (ai-memory v2.6.0 `install_hooks.rs:703-710`; `hook.rs:1340-1356` holds the mode-file reader and `hook.rs:720-726` reads it per event; at v2.6.3 = 385b81ea, which this host runs since 2026-10-10T22:09Z, the installer lines are identical and the reader moved unchanged to `hook.rs:1383-1399`). The repair follows this repository's documented enrollment design (`recipes/README.md`, "Worktrees and the capture marker"; the marker stays untracked, `.gitignore:73`): the main checkout carries `.ai-memory.toml` with workspace and project explicit; a worktree below it (such as Claude Code's default `.claude/worktrees/<name>`) or one that receives the marker through `.worktreeinclude` is enrolled too; scratch worktrees a script creates elsewhere carry none and are not captured; GPT read snapshots and blind or independent-review lanes must never carry or inherit it (the host-local GPT read kit strips any marker inside the read directory, then aborts if one remains or an ancestor carries one). Measured 2026-10-10: of 404 worktrees, 2 carry a marker (the main checkout and one 2026-10-06 record worktree) and none is nested under the main checkout. The trading repository has no marker, because its research memory goes to Hindsight's `trading-research` bank (`docs/decisions/2026-10-07-foundation-finalization.md:70,157`). Then `ai-memory install-hooks --agent claude-code --capture-mode allowlist --server-url MEMORY_URL --apply` with the existing data directory; Codex hooks read the same mode file and need no re-render. Verify each enrolled and excluded directory with the documented check (`recipes/README.md:419-421`):

```sh
printf '{"cwd":"%s"}' "$DIR" | ai-memory --data-dir "$AI_MEMORY_DATA_DIR" hook \
  --event pre-tool-use --agent codex --server-url "$MEMORY_URL" --check-capture
```

and expect `capture_mode` `allowlist`, with `marker_present` and `admits_capture` true only for enrolled directories; `ai-memory status` also reports `capture_mode`. Inverse: `install-hooks … --capture-mode denylist --apply` (or delete `<data_dir>/capture-mode`) and remove the markers that were added.

**Correction, 2026-10-11 (CC correction #149).** The `--capture-assistant` opt-in documented above (the two `install-hooks` commands and the "Assistant capture … explicit opt-ins" sentence) was not in force on this host on 2026-10-11: 0 of 9 Claude hook commands and 0 of 7 Codex hook commands carried it. The Codex count is one profile's seven: the retained qualification's `hook-trust.json` (under `evidence/artifacts/memory-landscape-20260921/`) lists seven hook commands from the `hooks.json` of each of two profiles, native (`$HOME/.codex/hooks.json`, `hook-trust.json:35-77`) and Desktop (`$DESKTOP_HOME_PARENT/.codex/hooks.json`, `hook-trust.json:279-321`), 14 in all. The 0 of 7 is the native profile's; the Desktop profile's seven were not measured, so this correction claims nothing about their flag or trust state, and its Codex statements are bounded to the native profile. These counts and the host history in this correction (the later hook applications, the Claude re-stage and the pending Codex trust) are CC host measurements, recorded as correction #149 in `coordination/lessons-20261005/cc-corrections-20261005.md` (host state, not in this repository) and not re-read by this change. The qualification's own installers carried the flag (`native-commands.json:295-393`, the commands above), so the flag was lost between then and 2026-10-11; the loss path is host history not reconstructed here. Two later applications, the #144 repair (a bare re-apply) and the 2.6.3 re-stage of 2026-10-10, ran without the flag, and ai-memory only preserves an opt-in already baked into the installed Stop command (`existing_capture_assistant_opt_in`, `crates/ai-memory-cli/src/commands/install_hooks.rs:689-701` and `:1104-1109`, identical at ai-memory v2.6.3 = 385b81ea, the release this host runs, and at v2.6.0 = 89bd8ded); a bare re-apply therefore does not add it. Claude was re-staged with `--capture-assistant` on 2026-10-11 and its Stop hook now carries the flag. Only the Stop hook carries it by design, so the other eight Claude commands correctly do not (the renderer bakes the flag only when `event == "stop"`, `crates/ai-memory-cli/src/commands/render_shared.rs:1425-1427`, so only the Stop command can carry it, and `install_hooks.rs:1142` scans the installed ai-memory commands for it; both ranges are identical at v2.6.3 = 385b81ea and v2.6.0 = 89bd8ded). Native Codex is pending a trust refresh: re-rendering a hook command changes its computed current hash, but the stored `trusted_hash` is unchanged, so the hook is marked modified and Codex skips it until the changed command is reviewed through the ordinary `/hooks` interface, which writes the reviewed current hash into `trusted_hash` (no trust-bypass flag, no trust-store edit; `docs/decisions/2026-10-04-codex-rtk-hook-qualified.md` Decision 1 states the mechanism from openai/codex rust-v0.159.3; at rust-v0.162.1 = 092d3acd, the installed `codex-cli`, `codex-rs/hooks/src/engine/discovery.rs:796-813` `hook_trust_status` marks a stored hash that differs from the current hash `Modified`, `:715-721` runs a hook only when it is Managed or Trusted unless `bypass_hook_trust` is set, and `codex-rs/tui/src/hooks_rpc.rs:58-92` `write_hook_trusts` writes the reviewed current hash), so native Codex assistant capture stays off until then. Host note: the GPT read kit (`tools/gpt_read_repo_exec_omni.sh`, `tools/strip_read_markers.py`) lives in the co-op's host state directory, not in this repository; its comment that "repositories commit the marker" contradicts `.gitignore:73` (`/.ai-memory.toml`, the marker is never committed), so the correct statement is that the marker is untracked, a per-host decision copied only by `.worktreeinclude`.

`CLAUDE_SETTINGS`, `CODEX_HOOKS` and `MEMORY_URL` are host-specific placeholders.
The upstream installer preserves unrelated hooks and writes a backup.
At the 2026-09-21 qualification this review recorded Claude's pre-existing
prompt-capture opt-out as off and both clients' assistant Stop excerpts as
opted in separately; correction #149 above gives the host state measured on
2026-10-11. Where the opt-in is in force, the excerpts are sanitized and
capped at 2,000 bytes, and a final message exceeding 64 KiB is dropped
entirely. They are not full transcripts. The service must enable this field as
well as the client hook. An existing Desktop task's hook reload is not proved
by editing its file.

Codex also requires native trust for a changed hook command.
At the 2026-09-21 qualification the first task ran without the modified Stop
hook. Only that reviewed hook was then trusted through the ordinary `/hooks`
interface in each native/Desktop profile; no trust-bypass flag or direct
trust-store edit was used. Native `hooks/list` subsequently reported zero
untrusted hooks in both profiles, and a new native task supplied the actual
captured outcome. For the current native Codex state see correction #149
above: assistant capture is off until Codex trust is refreshed; the Desktop
profile was not measured.

## Commands and observed results

| Upstream operation | Returned result and interpretation |
| --- | --- |
| `ai-memory doctor --workspace agent-lab --project agent-lab --json` | Claude and Codex both had captured sessions; `uncaptured: []`. This checks presence, not completeness of every local transcript. |
| `ai-memory status --json` | Baseline: 60 latest pages, 83 sessions, no missing latest-page embeddings and no unresolved embedding failures. Counts change with real work. |
| `ai-memory curator --workspace agent-lab --project agent-lab --dry-run --json` | Six conservative duplicate-title groups. Repeated titles do not prove duplicate bodies or justify deletion. |
| `ai-memory lint --workspace agent-lab --project agent-lab --no-llm` | Native rule-based audit written to `_lint/report.md`; this does not test semantic contradiction detection. |
| `ai-memory auto-improve --workspace agent-lab --project agent-lab --session-id SESSION_ID --json` | One real completed Codex session reviewed: no validated proposals; one rejected for insufficient durable evidence. Three observation bodies were truncated to the configured bound. |
| Native background scheduler | Two actual ticks at a temporary 60-second qualification cadence, independently matched to SQLite claims and `trigger: scheduler` run records. Both failed admission (one short session, one too few observations), made no model call and applied no edits. Restored hourly cadence afterward. |
| `ai-memory auto-improve-report --workspace agent-lab --project agent-lab --json` | Native read-only telemetry includes the manual review and scheduler admission records. A scheduler log saying `reviewed=1` does not imply a model call. |
| `cargo test --locked -p ai-memory-consolidate auto_improve_schedule::tests -- --nocapture` | Four unchanged tests passed at the installed source revision; 221 tests filtered out. These upstream tests use test providers and are not live-model evaluations. |
| `cargo test --locked -p ai-memory-hooks assistant_capture -- --nocapture` | Eighteen unchanged upstream tests passed; 290 filtered out. The initial reversed filter `capture_assistant` selected zero tests and is retained as inadequate verification. |

The [receipt](../evidence/receipts/memory-landscape-20260921.json) retains command
results, sanitization, source hashes, independent observations and client capture
acceptance. No native memory command above reports exact session or lifetime
tokens saved. Such values remain **unknown**, separate from provider usage.

## Operating boundaries that matter

- The upstream scheduler includes **every database project** and the limit is
  one session **per project** per tick. This deployment has one adopted scope.
  Qualify scope and usage before admitting another project.
- This store already had a persisted zero watermark from project creation.
  Enabling learning made existing ended sessions eligible. The generic
  first-start/no-backlog description must not be used to claim otherwise here.
- A resumed task can have newer observations after `ended_at`; the next genuine
  end event advances its observation generation. Do not synthesize lifecycle
  events or reset its database row. Learning claims are once per session, so
  long resumed tasks need deliberate later review when their new work warrants it.
- The upstream wiki is intentionally a read-only audit browser. Use the native
  MCP/CLI for scoped memory operations; do not present a marketing site or empty
  alternate dashboard as richer production memory.
- Source inspection, upstream tests, real admission, model review, successful
  learned writes and their long-term quality are distinct evidence. A rejected
  proposal is useful behavior; it is not proof that automatic learning improved
  future answers.
