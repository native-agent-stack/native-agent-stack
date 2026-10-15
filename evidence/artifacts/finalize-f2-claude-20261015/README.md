# FINALIZE-ALL F2, Claude side: invocation receipts (2026-10-15)

These are invocation receipts for the landscape winners a Claude Code session invokes, under condition 4 of `scripts/final_stack.py` (#1058 head 252babe4, :818-827): kind `invocation`, a tz-aware window, and calls > 0, bound to the winner's repository and run pin. The Codex side is #1135. Under the command center's 2026-10-14 ruling, invoke evidence is per winner across clients.

**Count of record:** [docs/decisions/2026-09-26-tool-invoke-rates.md](../../../docs/decisions/2026-09-26-tool-invoke-rates.md).
- Source: Claude Code's own OpenTelemetry tool events in the host's Loki. The Collector keeps the MCP server name, the skill name and a derived `shell_rtk` boolean; no command text is stored.
- `invoke_counts.py` sums 24-hour `count_over_time` chunks over each window. Its output is `counts.json` (read 2026-10-15T02:35:59Z; open windows end at 02:10:00Z).
- `validation.json` checks every receipt with #1058's own `complete_final_pin`, `normalize_repository` and `timestamp` against the run pin it binds to: all pass.
- Installation alone is never counted.

| Receipt | Run pin bound | Window (UTC) | Calls | Binds |
| --- | --- | --- | --- | --- |
| `receipts/invoke-claude-code-2.1.295.json` | 2.1.295 | 2026-10-08T20:12:18Z – 2026-10-10T05:04:41Z | 52006 tool calls (48207 model calls) | now (the run pin on main) |
| `receipts/invoke-claude-code-2.1.300.json` | 2.1.300; source 94506ff0 | 2026-10-14T20:16:22Z – 2026-10-15T02:10:00Z | 12132 (11755) | when #1128 lands |
| `receipts/invoke-serena-2.0.0.dev0.json` | 2.0.0.dev0 @ c6fbd1c5 | 2026-10-05T16:09:44Z – 2026-10-15T02:10:00Z | 148 | now |
| `receipts/invoke-qmd-2.8.3.json` | 2.8.3 | 2026-10-05T10:22:24Z – 2026-10-15T02:10:00Z | 135 | now |
| `receipts/invoke-headroom-0.40.0.json` | 0.40.0 | 2026-10-08T05:05:42Z – 2026-10-15T02:10:00Z | 7 | now |
| `receipts/invoke-rtk-0.51.0.json` | 0.51.0 | 2026-10-05T19:04:27Z – 2026-10-15T02:10:00Z | 8547 | now |
| `receipts/invoke-affaan-m-ecc-dd6ee538.json` | dd6ee538 | 2026-10-04T15:44:42Z – 2026-10-15T02:10:00Z | 204 activations of iterative-retrieval (search-first's 213 excluded) | now (ECC stays at dd6ee538; command center, 2026-10-15T02:38Z) |
| `receipts/invoke-ai-memory-2.6.3.json` | 2.6.3 | 2026-10-10T22:09:02Z – 2026-10-15T02:10:00Z | 2 | when the stack re-pin 2.4.1 → 2.6.3 lands |

Each receipt's `pin_binding` field says why the calls in its window ran that pin:
- **claude-code:** the client's own `service_version` label.
- **serena:** the uv receipt's git rev.
- **qmd:** the package version.
- **headroom and rtk:** the install link's birth time.
- **ECC:** iterative-retrieval's directory has the same blob set at the loaded 2b6e8397 and at dd6ee538. search-first is loaded at c70874fa, whose directory differs, so it is not counted. c70874fa is a failed candidate pin while its test failures are read.
- **ai-memory:** the service's own version line at each start.

`reasons/not-invoked-sandbox-runtime.json` records why sandbox-runtime has no Claude call: no Claude lane runs the native sandbox, and the slot is an owner-gated trial.

**Not here, with the reason:**
- **socraticode:** the Claude registration runs the 1.16.0 npm package (22 Claude calls since its install), but no retained record dates the registration's switch from 1.15.0. Its receipt is the Codex side's.
- **promptfoo:** its invoke evidence is its harness eval runs, not MCP calls (the command center's ruling). It follows with the re-pin to 0.124.0.
- **Claude-side calls of zero or one in the last 24 hours** (serena, headroom, socraticode, qmd, ai-memory): the command center ruled that such a zero is a wiring defect only where a slot row names Claude as the consumer. That follows the Codex-side record.
