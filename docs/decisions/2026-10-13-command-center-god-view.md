# Command center god view: one Grafana board over the platforms' own data

The command center's god view is one provisioned Grafana dashboard, **Command center**
(`uid cc-god-view`, `http://127.0.0.1:21301/d/cc-god-view`), in NativeStack2604's Ecosystem
folder. It tracks every lane and worker from data the platforms already emit: Codex and Claude
OTLP through the OTel Collector into Loki and Prometheus, hcom status records, the runtime
workers that export OTLP, and OmniRoute routing spans. Session-level detail stays in agentsview
(`http://127.0.0.1:21808`, `/sessions/<agent>/<session id>`), which the board links. Nothing here
is a self-built page or a hand-rolled exporter; every gap below names the vendor's documented
option or says that none is documented.

## SOTA sources

| Source and pin | Contract used |
| --- | --- |
| [grafana/grafana v13.2.3](https://github.com/grafana/grafana/tree/6193dc03311b631b9727b560d24369e683dc396e), `6193dc03`; live build `90ffed05` (`/api/health`) | File provisioning (provider `updateIntervalSeconds: 30`); instant queries as table frames named `Value #<refId>`; `merge` keys on fields shared by every frame and merges rows whose other fields do not conflict (`packages/grafana-data/src/transformations/transformers/merge.ts:25-95,189-205`); `joinByField` drops frames without the key (`joinDataFrames.ts:183-194`); `organize` orders before it renames (`organize.ts:36-46`, `rename.ts:43-68`) |
| [grafana/loki v3.7.8](https://github.com/grafana/loki/tree/09e6ce2f), `09e6ce2f` (live `/loki/api/v1/status/buildinfo`) | `__timestamp__` and `unixEpoch` in `label_format` templates (`pkg/logql/log/fmt.go:21,117,122`); `on`, `unless`, `or` vector operators (`pkg/logql/syntax/lex.go:41-49`); structured metadata (`ecosystem_lane`, `model`, `tool_family`) |
| [prometheus/prometheus v3.15.0](https://github.com/prometheus/prometheus/tree/5241a27fe3c6983549fccc32f6e65917408c63cd), `5241a27f` (live buildinfo) | `increase`, `label_replace`, `or` with zero rows for the wiring-gap tables |
| [open-telemetry/opentelemetry-collector-contrib v0.162.0](https://github.com/open-telemetry/opentelemetry-collector-contrib/tree/v0.162.0) (`otelcol-contrib --version`) | Collector resource label `ecosystem_lane`, Loki export, spanmetrics connector for OmniRoute and runtime spans |
| agentsview v0.44.0, commit `413a87f7bfbd67b2815b1119ac51abc1efbeeaba` (installed `agentsview version`) | Session archive and UI; `/api/v1/agents` and `/api/v1/sessions` counts; `pg`, `clickhouse` and `duckdb` push as the only documented data feeds (`agentsview --help`) |
| [aannoo/hcom v0.7.28](https://github.com/aannoo/hcom/tree/b2a7c192003e7fd67ed93265289e4ac36276f965), mirror `b2a7c192` (installed `hcom 0.7.28`) | `list --json` fields, `name` vs `base_name` (`src/commands/list.rs:353,370`), status values (`src/commands/status.rs:192-197`), listening gate contexts (`src/instance_lifecycle.rs:588-600`), `term --json` fields (`src/commands/help.rs:803`) |
| [openai/codex rust-v0.162.1](https://github.com/openai/codex/tree/092d3acd6bec3e3a14bdc7e7a2810ab628ab759d), mirror `092d3acd` (installed `codex-cli 0.162.1`) | `codex.skill.injected` (`codex-rs/core/src/skills.rs:66-72`), `codex.turn.e2e_duration_ms` (`codex-rs/otel/src/metrics/names.rs:35`) |

## What the board shows

34 panels: a header, six rows and 27 panels in them. 13 panels are reused from
`ecosystem-native` (ids 31, 32, 33, 37, 40, 41, 42, 43) and `cc-lanes` (hcom status, per-lane
tool-result rate, native API errors, both gateway routing panels) with their queries byte for
byte; `tests/test_ns2604_dashboards.py` compares them with the rendered source boards. The new
panels add the lane key to the same events and counters.

| Row | Panels | New queries |
| --- | --- | --- |
| Lane roster | 3 | Roster (kind, lane, role, hcom tag, model, last event, sessions, 20-minute events, hcom status, state); STUCK lanes |
| Progress | 4 | Started turns and tool calls per lane; runtime-worker tool spans |
| Invoke rates | 7 | Skills, MCP and subagents per lane with zero rows; Codex skill injections; MCP per lane and server |
| Errors | 7 | Claude tool failure share by lane; gateway 4xx/5xx by provider and their share |
| Gateway | 3 | Requests by family (GPT, Muse, Claude), provider and model |
| Coverage | 3 | OTLP log records and span calls per service; the dated coverage table below |

Keys and flags:

- **Kind** comes from `service.name`; **lane** is `ecosystem_lane`, `unattributed` when a Codex
  process or Claude session has none, and `service.name` for runtime workers, which set none.
- **State** joins hcom with telemetry on the hcom instance name (`base_name`), which is what a
  lane exports as `ecosystem.lane`: STALE is hcom status `active*` with no Codex or Claude event for
  the lane in 20 minutes; ACTIVE has events; LISTENING is idle waiting for messages.
- **Role** stays blank: no recorded role source exists in telemetry or hcom. The hcom launch tag is
  shown beside it; the free-text hcom description is never exported.
- **Wiring gap**: a lane with tool results and zero MCP, skill or subagent calls in the hour shows
  `0 · wiring gap`; it proves non-use only once exposure and a full window are qualified.
- **STUCK** (command center request, 2026-10-13): in every hcom snapshot of the last 10 minutes,
  at least 15 of the 30-second snapshots, `unread_count > 0` and the PTY prompt holds text
  (`hcom term` `prompt_empty=false`, or the listening gate context `tui:prompt-has-text`). The
  bridge exports only `prompt_has_text` as 0/1; `input_text` and screen lines never leave hcom.

## Coverage

Observed 2026-10-13 between 01:40Z and 02:30Z: Loki `service_name` values over 7 days,
Prometheus `job` values over 24 hours, and agentsview session counts including one-shot,
automated and child sessions (`/api/v1/sessions`; top-level counts from `/api/v1/agents`:
claude 2257, codex 2050, runtimes unchanged).

| Runtime (installed) | OTLP on this host | agentsview | Vendor telemetry option |
| --- | --- | --- | --- |
| Codex 0.162.1 | yes: `codex_exec`, `codex_cli_rs`, `codex-app-server`, `codex_sdk_ts` | 3299 | `[otel]` exporter in `config.toml`: `openai/codex@092d3acd:codex-rs/otel/README.md:115-121` |
| Claude Code | yes: `claude-code` | 6482 | [monitoring usage](https://code.claude.com/docs/en/monitoring-usage) |
| pi 1.1.0 | yes: `pi`, through the pi-otel extension | 1 | No built-in exporter; adapters: `earendil-works/pi@04566631:packages/telemetry/README.md:11,13`; the host's `@b1tank/pi-otel@0.5.0` (`notes/runtime-profiles-20261012/README.md:143-144`) |
| OpenCode 2.0.27 | yes: `opencode`, `ns-opencode-claude`, `ns-opencode-gpt`, `ns-opencode-muse` | 6 | OTLP endpoint and `OTEL_RESOURCE_ATTRIBUTES`: `anomalyco/opencode@a3496182:packages/util/src/observability/otlp.ts:30,64-97` (mirror HEAD, newer than the install) |
| goose 1.54.0 | yes: `goose` | 1 | `OTEL_EXPORTER_OTLP_ENDPOINT`: `aaif-goose/goose@4617040c:documentation/docs/guides/environment-variables.md:406-421` |
| Qwen Code 0.25.1 | yes: `qwen-code` | 1 | `telemetry.otlpEndpoint`: `QwenLM/qwen-code@aaf97b86:docs/developers/development/telemetry.md:72-73` |
| oh-my-pi 18.10.2 | yes: `oh-my-pi` | 1 | `OTEL_EXPORTER_OTLP_ENDPOINT`: `can1357/oh-my-pi@5d0aaffa:docs/environment-variables.md:634-647` |
| Hermes 0.21.7 | **no** (agentsview only) | 1 | Gateway-daemon health only (`monitoring.export.otlp`); run trajectories are a separate NeMo Relay plane: `NousResearch/hermes-agent@3569e846:website/docs/developer-guide/gateway-monitoring.md:8-18`. No per-run OTLP is documented. |
| Cline 3.0.70 | **no** (agentsview only) | 3 | `CLINE_OTEL_TELEMETRY_ENABLED`, `CLINE_OTEL_EXPORTER_OTLP_ENDPOINT`: `cline/cline@8eba11b2:docs/enterprise-solutions/monitoring/opentelemetry_override.mdx:30-41`; CLI build env `apps/cli/bun.mts:102-106` |
| Kilo | **no** (agentsview only) | 2 | Not checked: not installed, no mirror |
| Muse Code 1.4.6 | **no**: neither; only the gateway provider `muse-code` | 0 | Not documented: the installed `muse --help` lists no telemetry or OTLP option, only local traces (`muse trace inspect`); Harbor 0.24.0's adapter installs it from `https://dev.meta.ai/install.sh` without a version pin (`harbor/agents/installed/muse_code.py:83,136-149`) |
| OmniRoute 3.8.51 | yes: routing spans (`omniroute`) | n/a | Built-in GenAI OTLP trace sink (`cc-lanes` source: OmniRoute `c1e30b76` `open-sse/services/routing/otel.ts:193-216`) |

agentsview has no Prometheus or OTLP output: `/metrics` on 21808 serves the web UI
(`text/html`). Its documented feeds are `pg push`/`pg service`, `clickhouse push`/`service` and
`duckdb push`; Grafana 13.2.3 bundles `grafana-postgresql-datasource`
(`data/plugins-bundled/` in the release archive). No PostgreSQL runs on this host, so the
board links to the agentsview UI instead.

## Correction: the hcom status bridge failed every snapshot

The research-progress unit's second `ExecStart` runs `hcom_status.py --name gore` every 30
seconds. With no live `gore` instance, `hcom list --json --name gore` exits 1 ("Instance 'gore'
not found"): the unit journal at 2026-10-13T02:16:25Z shows the `CalledProcessError`, and
`query_loki_stats` found 0 `agent-stack-lanes` streams over 30 days. An explicit `--name` takes
hcom's error-propagating path; an omitted name falls back to an optional lookup
(`aannoo/hcom@b2a7c192:src/bootstrap.rs:25-30`, `src/identity.rs:58`,
`src/commands/list.rs:213-234`), and listing needs no identity (`systemd-run --user` listed 19
agents). The bridge now passes `--name` only when given, and the plan unit template no longer
passes it. `tests/test_hcom_status.py` runs the bridge against a stand-in hcom that rejects
`--name` and checks the template; both fail before the fix. This corrects the bridge command
recorded in `docs/decisions/2026-10-06-native-lane-invocation-observability.md:55`.

The join also changed: hcom `name` is the tagged display name (`angle-records-benu`) and
`base_name` the instance name (`benu`) that `hcom term` and `ecosystem.lane` use
(`list.rs:353,370`); the bridge exports `base_name` and keys prompt state on it.

## Apply and rollback

Before merge, only `ecosystem-grafana-dashboards/command-center.json` was published to the live
config root: `observability_config.py grafana` rendered into a staging root, its bytes matched
`config/grafana-command-center.json`, and the file and its digest in `.g4-source-digests.json`
were written the way `publish()` writes them. Grafana's file provider loaded it within 30 seconds;
no restart and no other dashboard changed (`cc-lanes` stays at its live revision). The hcom
stream was seeded for the read-back by running the corrected bridge at the unit's 30-second
cadence in three bounded runs between 02:35Z and 03:09Z.

Read-back at 03:07Z: `/api/dashboards/uid/cc-god-view` serves the provisioned file (Ecosystem
folder, 34 panels) with the same SHA-256 as `config/grafana-command-center.json`. Every target
of the 26 query panels ran against Loki and Prometheus without an error; all returned series
except "Codex goal blocked and usage-limited events by lane", which had no events in its
15-minute window and shows Grafana's No data. The browser view showed one merged roster row per
lane with State ACTIVE or LISTENING for hcom lanes, and `0 · wiring gap` rows (for example Codex
skill injections on every Codex lane in that hour). Both hcom reads work without an identity under
the user manager (`systemd-run --user`: `hcom list` 19 agents, `hcom term` 18 PTY objects).

Untested boundary: no lane met the STUCK rule during the read-back, so the rule's positive branch
(`== 1` and at least 15 snapshots) parsed and ran but never produced a row. The bridge side of it,
`prompt_has_text` from `hcom term` and the `tui:prompt-has-text` context, is covered by synthetic
tests only.

After merge the CC applies from the main checkout: `bash install.sh --only grafana`, which
re-renders and installs the research-progress unit without `--name`; then
`python3 config/observability_config.py grafana-check --config-root <config root> --installed-units`.
Until then the installed unit still exits 1 on every hcom snapshot, so the hcom-based columns,
State and STUCK go empty once the seeded window ends. Rollback: as for the other Ecosystem
dashboards in the plan README, remove `command-center.json`, set `disableDeletion: false` on
`nativestack2604-ecosystem` for one Grafana restart, verify `/api/dashboards/uid/cc-god-view`
returns 404, then restore `disableDeletion: true`.

## Follow-ups

1. **Claude lane attribution.** Claude sessions show as `unattributed` because none sets
   `ecosystem.lane`. Proposal: launch each named Claude session with
   `OTEL_RESOURCE_ATTRIBUTES=ecosystem.lane=<name>` (appending to any inherited value), as Codex
   lanes do. Launchers are unchanged in this record.
2. **Runtime-worker lanes.** The `ns-run` profiles can export the same attribute, so runtime rows
   key on a lane instead of `service.name`.
3. **hcom unit re-render** after merge (above); the CC owns the installed unit.
4. **Cline** has a documented OTLP override (`CLINE_OTEL_*`); adding it to a Cline profile is a
   candidate for that profile's owner.
5. **Hermes and Muse Code** have no documented per-run OTLP; they stay agentsview-only and
   gateway-only respectively until the vendors document an option.
6. **agentsview to Grafana** through `pg push` and the bundled PostgreSQL datasource is a candidate
   to screen, not adopted: it adds a database service and a datasource.
7. **Role** needs a recorded source (for example a launch-time attribute) before the column can
   fill; none exists today.
