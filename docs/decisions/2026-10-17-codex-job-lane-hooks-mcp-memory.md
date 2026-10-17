# Decision: the codex_job.py roles, and their hook, MCP and memory choices; opt-in per-job hook trust, `--disable apps`, loopback OTEL, rollout usage and the gateway ai-memory bearer (2026-10-17)

Status: accepted by the command center's ruling of 2026-10-17T08:07Z on the lane conformance report of the same day
(enhancements 1 to 5 of its GPT-Codex section) and the requests that report folded in. Scope: the Codex runner
`tools/sota-convergence/landscape-sweep/codex_job.py` and its stager `build_args.py`, for the native provider and the
OmniRoute gateway lane. Nothing here runs by default: every behaviour is a staged key, and a lane that stages none
produces the argv, environment, `inputs.json` and `result` bytes it produced before.

## SOTA sources

- openai/codex `rust-v0.163.0` at `83086188ae0614bd882818ff1aa23f3194962012` (paths are `codex-rs/`-relative): hook discovery and trust
  `hooks/src/engine/discovery.rs` (:129-152 layer folders, :421 the session-flags source path, :559-568 handler
  normalization, :715-736 and :796-813 trust states, :742-794 the identity and its hash), `config/src/fingerprint.rs:54-66`,
  `hooks/src/lib.rs:112-123` (the state key), `hooks/src/config_rules.rs:8-29` (trust is read only from the user and
  session-flags layers), `config/src/hook_config.rs:19-61` (`[hooks]` and `[hooks.state]` shapes), `hooks/src/engine/matcher.rs`
  (an alphanumeric matcher is an exact tool-name match), `hooks/src/events/pre_tool_use.rs:213-291` (what blocks), `core/src/tools/handlers/unified_exec/write_stdin.rs:144-149`
  (no pre-tool payload) and `core/src/tools/handlers/mcp.rs:109-111,449-459` (MCP tools hook under `mcp__` names), the `-c`
  parser `utils/cli/src/config_override.rs:49-101` and `config/src/overrides.rs:18-22`, `features/src/lib.rs:1346-1350`
  (hooks on by default) and `:1523-1528` (apps), `cli/src/main.rs:951-997` (`--disable` is validated),
  `config/src/types.rs:596-654` (`otel`), `protocol/src/protocol.rs:2363-2404` (`TokenUsage`, `TokenUsageInfo`),
  `rollout/src/policy.rs:41-48` (what a rollout keeps), `utils/home-dir/src/lib.rs:13-62` (`CODEX_HOME`).
- rtk 1.0.1: `rtk init -g --codex` (writes `RTK.md`, appends the `@RTK.md` pointer to the home's `AGENTS.md`, registers
  `rtk hook codex` as one PreToolUse group; `--hook-only`, `--auto-patch` and `--no-patch` are refused with `--codex`, as
  recorded for 0.51.0 in [2026-10-04-codex-rtk-hook-qualified.md](2026-10-04-codex-rtk-hook-qualified.md)).
- ai-memory 3.1.0: `install-mcp --client codex --apply` writes the token as a literal `Authorization` header in the lane's
  `config.toml`; the host's own entry uses `bearer_token_env_var` instead. The Codex config reference documents both fields
  (https://developers.openai.com/codex/config-reference).
- The Codex hooks documentation (https://developers.openai.com/codex/hooks) for the event payloads and the rule that
  hook guardrails are not a complete enforcement boundary.
- The observability collector's own id pattern, `observability/collector/collector.yaml:303`.

## The roles and their choices

`codex_job.py` runs three kinds of job. Each row is what a lane of that role stages; the unlisted settings keep their
defaults.

| Role | Provider and home | MCP | Memory | Hooks | Web and apps |
| --- | --- | --- | --- | --- | --- |
| Sweep worker (landscape-sweep GPT-6 discovery and fit) | the OmniRoute gateway lane home (`-p stack-worker`) | the rendered token servers, `serena` required, the profile's read-only ai-memory tools | ai-memory reads on, through `--ai-memory-bearer-env` | `rtk` and `secret_guard` | search live, apps untouched |
| Non-blind worker on the native login (G8-style) | native, `--ignore-user-config` | none: the user config is dropped, so no MCP server loads | none | `rtk` and `secret_guard` | search per the job, apps untouched |
| Independent PR reader | native, or a gateway work directory staged **without** `--ai-memory-bearer-env` | none on native | **off**: the entry carries no credential, so ai-memory answers `invalid_token` (the report's measured failure) and returns nothing it captured | `rtk` and `secret_guard` | `--web-search disabled --codex-disable-feature apps` |

Why memory stays off for independent reads: ai-memory could return the Claude and Muse reads that earlier sessions captured,
so a reader that queries it is no longer independent. This supersedes, for `codex_job.py` readers only,
`adoption/agents/codex/workers/evidence-reviewer.toml:25` (which lists ai-memory `memory_query` among that interactive role's
lanes) and any reading of the PR-review recipe in `recipes/claude-codex-cooperation-lanes.md` that has a reader query
memory. Those two files keep their text and their own surfaces; this record scopes the reader rule to the runner. Making the
exclusion structural, by rendering a reviewer lane home with no ai-memory server, needs a stager option this change does not
add; until then the rule is the staging recipe in the table.

## Hooks: per-job trust, carried on the command line

- A staged `codex.hooks` (`--codex-hook rtk`, `--codex-hook secret_guard`) adds **one** `-c hooks.state={...}` inline table
  that holds every trust entry. A second `-c hooks.state` replaces the first, and the dotted quoted-key spelling is split on
  every `.` and lands under a key that matches nothing, which leaves the hook untrusted with no error. The table is parsed as
  a TOML value into the session-flags layer. `--ignore-user-config` stays on the native lane, so the host's trust of its
  other hooks never applies, and `--dangerously-bypass-hook-trust` is never passed.
- The trusted hash is computed by the runner at launch with `hook_trust_hash`, a port of upstream's identity and hash
  (sorted compact JSON of `{event_name, matcher?, hooks:[normalized handler]}`, a 600 s default timeout, `async` false).
  The regression vectors are the RTK hook's hash (`rtk hook codex`, matcher `Bash`) and upstream's own published fingerprint vector;
  a read-only mapping pass recomputed all 11 hashes Codex had stored for one live host's `hooks.json` and matched all 11 (a
  host measurement, not reproducible from the repository).
- **RTK** (`rtk`): the key is `<home>/hooks.json:pre_tool_use:<group>:<handler>`. The runner finds the single handler whose
  command is `rtk hook codex` by command, never by position, because the key embeds the group index. `<home>` is the realpath
  of `CODEX_HOME` when set, else `$HOME/.codex`; for the gateway lane it is the realpath of `<work-dir>/codex-home`, where
  `build_args.py --codex-hook rtk` runs upstream's own `rtk init -g --codex` with `CODEX_HOME` at the lane home. The lane's
  `config.toml` stays trust-free (`tests/test_landscape_sweep_harness.py` keeps asserting it): trust travels per job. A missing or
  duplicate handler ends the job before codex starts (exit 2, failure kind `hook_trust`), because an untrusted hook is skipped
  without an error. `RTK_TELEMETRY_DISABLED=1` is set in the runner's environment for codex (hook processes inherit it) and as
  `shell_environment_policy.set` for the model's shells.
- **Secret-path guard** (`secret_guard`): `scripts/hooks/secret_path_guard.py` is registered for the **`Bash` tool only**, as
  `-c hooks.PreToolUse=[...]` with a 10 s timeout, from a byte-for-byte copy that `build_args.py` stages beside `codex_job.py`
  and records in `staged.json` `harness.files`; the runner refuses a missing copy or a copy that differs from that hash. Its
  trust entry is keyed by the session-flags source, `/<session-flags>/config.toml:pre_tool_use:0:0`, in the same `hooks.state`
  table. The guard's code and patterns are not changed, so `adoption/hooks/claude/SHA256SUMS` is unchanged. `apply_patch` is
  **not** registered: the guard returns 0 for every `tool_name` but `Bash` (`scripts/hooks/secret_path_guard.py`, `main()`), and
  covering patches is the command center's separate guard change. A characterization test pins that today a patch payload
  passes, so it flips when that change lands.
- **What the Bash-only guard never sees: `write_stdin` and MCP tools.** The guard checks a command once, at the `PreToolUse` of
  the `exec_command` that starts it. `write_stdin` is transport for an existing unified-exec session and runs no `PreToolUse`
  when it sends input or polls (Codex hooks documentation, tool-path table and the note under it, evidence-pack copy
  `hooks.md:450-465`; `core/src/tools/handlers/unified_exec/write_stdin.rs:144-149` returns no pre-tool payload), so text typed
  into a shell session the guard already allowed (a `bash` or REPL started earlier) is never checked: a secret path read that
  way passes. MCP tools do run `PreToolUse`, but under their own names (`mcp__<server>__<tool>`,
  `core/src/tools/handlers/mcp.rs:109-111,449-459`), and the `Bash` matcher is an exact tool-name match
  (`hooks/src/engine/matcher.rs:12-34`), so the guard never sees their arguments: on the gateway lane the `serena` and
  `ai-memory` calls are outside it. That matches the Bash-only ruling and widens nothing, but `apply_patch` is therefore not
  the only uncovered path; `write_stdin` input and every MCP tool call are uncovered too, and the guard's own header
  ("not a security boundary") holds for the lane as a whole. Closing either needs a separate change (a matcher for the MCP
  names, and a guard that follows a session's input), which this record does not make.
- **Codex fails open where Claude fails closed.** Claude's hook settings carry `onFailure: "block"`
  ([2026-10-08-guard-hook-fails-closed.md](2026-10-08-guard-hook-fails-closed.md)); Codex's command handler has no such field
  (`config/src/hook_config.rs:163-185`). In Codex only exit 2 **with** non-empty stderr blocks; exit 2 with empty stderr is a failed
  hook that does not block, and a crash, a timeout, a kill or any other exit code is a failed hook after which the tool call
  continues (`hooks/src/events/pre_tool_use.rs:213-291`). The guard converts its own errors, oversize commands and work-budget
  exhaustion to exit 2 with a reason, but it exits 1 on unreadable JSON, and `python3` or the shell failing is outside it.
  The registered command therefore refuses with exit 2 and a reason when the staged copy or the interpreter is missing, the
  runner refuses the job before launch in the same cases, and the guard stays what its own header says: a text heuristic that
  stops accidental exposure, not a security boundary. A host that needs a guaranteed block needs a Codex-side mechanism that
  does not fail open, which upstream does not offer for command hooks at this pin.
- RTK and the guard run side by side (several matching command hooks start concurrently), and the guard sees the original
  command; RTK rewrites through `updatedInput`.

### Supersession

For the lanes that stage `secret_guard`, this record supersedes
`docs/decisions/2026-10-02-new-wsl-client-configuration.md:248-279` (decision 13(a): the guard "runs for Codex nowhere", and a
Codex-side guard "would be a new decision") and `docs/secret-storage.md:362-364` ("Codex, OmniRoute lanes and units do not
automatically run this hook"). Both files stay as written, by record; for every other Codex surface they remain true. Decision
13(b) of the 2026-10-02 record (a trust entry can be rendered for a hook whose definition is the same on every host) is what
this change uses, per job instead of per host.

## The gateway lane's ai-memory MCP

The lane's ai-memory entry authenticates the host's way: `bearer_token_env_var = "AI_MEMORY_AUTH_TOKEN"` (default; the name is
an option), written by `build_args.py --ai-memory-bearer-env` after the rendered MCP tables are extracted and read back with
`tomllib`. `ai-memory install-mcp --apply` was considered and not adopted: it writes the token as a literal header into the
lane's `config.toml` (a secret at rest, a `.bak` copy that may keep an older secret, a stale `lane_home.config_sha256`, and a restage
that drops the header). The variable approach writes no token anywhere. The runner refuses a start while the variable is unset or blank
(exit 6, failure kind `no_key`, as for a missing gateway key), the lane's `shell_environment_policy.filters` excludes it from the
model's shells exactly as it excludes `OMNIROUTE_API_KEY`, and `inputs.json` binds only the variable's name. The default
staging is unchanged, and `tests/test_codex_worker_lane.py` still holds the lane's tables equal to the omniroute profile; a new case
there pins the opt-in form. Whether the lane's ai-memory server accepts this bearer is not measured here (the report saw
`invalid_token` with no credential).

## `--disable apps`, OTEL and rollout usage

- `codex.disable: ["apps"]` adds `--disable apps` (Codex validates the name; documented as `-c features.apps=false`), bound in
  `inputs.json`. It is **not** coupled to `web_search`, so a lane that already stages `disabled` keeps its bytes; reviewers stage both.
  Not shown complete: remote plugin MCP servers, `search_service.web_run` surviving `web_search = "disabled"`, and the
  transport-only fallback; the acceptance is a probe with zero `mcp__codex_apps__*` tools.
- `codex.otel` adds `otel.exporter` and `otel.metrics_exporter` (OTLP/HTTP, `protocol = "binary"`, which has no default),
  `otel.tool_result.max_bytes = 0` and `otel.environment = <lane>-<job id>` for the loopback collector only (a non-loopback
  endpoint is refused before state changes). The lane prefix is approved; the tag must match the collector's
  `^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$` (a tag outside it is deleted, never rewritten), so a job whose tag would pass 128
  characters is refused before state changes. The client sends `user.email`, `user.account_id` and tool arguments; the collector
  strips them. `span_attributes` and `log_user_prompt` are not set (traces stay off; the prompt default is false).
- `codex.rollout_usage` writes, per attempt, `codex_home` (the effective Codex home) and `rollout_usage.json`, and `result` and
  every `attempts[]` entry carry `rollout_usage {status, thread_id, rollout, usage, reason}`: the last `token_count` event's
  `total_token_usage` of the rollout found by **thread id** under `<home>/sessions/*/*/*/rollout-*-<thread id>.jsonl` (the date
  folders use local time). `usage` and `usage_status` are untouched, `total_tokens` is dropped (`convert.py` sums every counter
  it sees, so the field is never added to `gpt6_usage`), a job that died before `thread.started` stays `unavailable`, and a
  compressed or missing rollout records a reason and never changes the exit. The rollout format is internal and a killed run can lose
  pending items, so the figure is labelled rollout-derived. It is not bound in `inputs.json`: it reads a finished attempt and
  changes nothing codex runs.

## Evidence status

Measured by the tests in `tests/test_codex_job_lane_hardening.py` (a fake `codex`, a stub `rtk`, no real `codex`, `rtk` or
`ai-memory`): the argv, environment and `inputs.json` of every option; each `-c` value parsed as TOML as Codex parses it; the trust
hash against the RTK vector and upstream's published fingerprint vector; the registered guard command run as `<shell> -c` with
payload JSON on stdin (a `cat` of a fake Codex auth file exits 2, `credential_run.py <fake id> -- true` exits 0, a missing copy
exits 2 with a reason); the rollout lookup by thread id; and that no option changes a byte when absent.

Read from the pinned source only, not yet measured with Codex 0.163.0, and therefore the acceptance gate before any lane relies
on them (a scratch `CODEX_HOME` copy and `codex app-server` `hooks/list` with the identical `-c` flags, each registered entry
showing `trustStatus: trusted`):

- the session-flags trust key `/<session-flags>/config.toml:pre_tool_use:0:0` and discovery of an inline `hooks.PreToolUse`;
- that a changed group index, command or timeout turns trust into `Modified` or `Untrusted` with no error;
- that `-c shell_environment_policy.set` reaches the model's shell and that `RTK_TELEMETRY_DISABLED` reaches the hook process;
- OTEL delivery from the lane (a record tagged `env=<tag>` arriving with no content stored) and the metrics exporter replacing
  the Statsig default;
- `--strict-config` as an in-argv tripwire (it would validate every existing `-c` and the lane's own config, which is unmeasured).

The paired before/after probe (`tools/sota-convergence/landscape-sweep/paired_probe.py`) is **staged and has not been run**: it
waits for GPT capacity (the gateway was down and the native account at its usage limit when this was written). Its first run is
the first measurement of any token or cache effect; no saving is claimed here.

## Consequences and rollback

`sweep.js` copies a fixed list of `result` keys (`attempts[]` entries pass whole), so a final failed attempt's top-level `rollout_usage`
is read with `codex_call.sh result` until a separate change adds it to the sweep record and `convert.py`. The rollout also holds `token_usage_record` items
(`protocol/src/protocol.rs:2386-2395`, per-response usage with thread totals); they are not adopted, because the measured on-disk
shape of the installed client is the `token_count` event.

A restage rewrites `staged.json`, `config.toml` and `AGENTS.md`, so every option must be repeated and `rtk init -g --codex`
re-run (the stager does that for `--codex-hook rtk`); the restage keeps an existing `hooks.json`. Dropping an option restores the earlier
bytes; a finished job whose inputs lack a newly staged field is rerun, and one staged with a field is not reused by an unstaged
lane. The runner's frozen copy in each work directory changes only on a `--force` restage.
