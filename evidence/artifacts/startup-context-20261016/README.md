# Start-up context of the command center's launch, by component (2026-10-16)

Measured on 2026-10-16 (04:45:07Z to 04:49:24Z) with `tools/startup-context/startup_context.py` and
`tools/startup-context/launches/CC.json`, client 2.1.301, model claude-opus-5-5, in the repository's working directory.
Every run was a $0 `/context` report (0 turns, $0). These receipts replace the first set, measured at 03:07Z to 03:12Z
before the fold for the co-op's local review at 71b3fde3. That review found the first set's Context Mode variant
measured without its plugin's MCP server.

| Variant | Start-up tokens | Over the control | Loaded |
| --- | ---: | ---: | --- |
| control (serena; Context Mode off) | 25,100 | — | serena connected |
| + ai-memory | — | — | not connected (see below) |
| + qmd | 25,600 | +500 | connected |
| + socraticode | — | — | not connected (see below) |
| + headroom | 25,100 | +0 | connected; its tools are deferred |
| + Context Mode (plugin and its MCP server) | 26,800 | +1,700 | plugin listed, server connected |

`receipts/` holds one receipt per variant and `CC.summary.json`. A delta is given only when the component loaded and
every server and plugin the variant shares with the control is in the same state in both runs (`baseline_differs`
empty in every row here).

## Findings, recorded as found

- The template's ai-memory server (`adoption/mcp/claude-user.json`, an HTTP URL on a fixed loopback port) did not
  connect: nothing listened on that port on this host on 2026-10-16. This session's own ai-memory server reaches it
  another way.
- The template's socraticode server runs a binary under the ecosystem prefix that is not installed on this host, where
  socraticode arrives as a plugin instead (listed in every run).
- Both are drift between the template and this host, for the template's owner; nothing here repairs them.
- Every server's MCP tool definitions are deferred under tool search: they load on demand, count per task and stay
  outside the total. At start-up a server adds its server instructions. qmd's +500 is the report's "MCP server
  instructions" row (60 to 641 tokens). headroom and Context Mode send none, so headroom adds +0.
- Context Mode's +1,700 is, by the report's rows:
  - Skills +900;
  - Messages +1,731 (369 to 2,100);
  - System tools −892 (1,400 to 508).

  Its MCP tool definitions (8,700 to 19,600, deferred) are outside the total and count per task.
- The control is 300 tokens above the first set's (24,800): System prompt +200 and Memory files +100, on the same
  client. Each delta is taken within one set.

## Not measured here

- The other roles, the per-task cost, and the other client families (Codex, Muse, the researchers): the role matrix and
  the wiring change take these.
- The new host: its launches are measured there once installed.
