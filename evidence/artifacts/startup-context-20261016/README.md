# Start-up context of the command center's launch, by component (2026-10-16)

Measured on 2026-10-16 (05:36:56Z to 05:41:21Z) with `tools/startup-context/startup_context.py` and
`tools/startup-context/launches/CC.json`, client 2.1.301, model claude-opus-5-5, in the repository's working directory.
Every run was a $0 `/context` report (0 turns, $0). This is the third set, and it replaces two earlier ones:
- the first, measured at 03:07Z to 03:12Z, ran the Context Mode variant without its plugin's MCP server;
- the second, measured at 04:45Z to 04:49Z, ran that server under its bare name instead of the native
  `plugin:context-mode:context-mode`, so its tools did not carry the names Claude Code gives them.

The local reviews at 71b3fde3 and 3a1f8618 found these.

| Variant | Start-up tokens | Over the control | Loaded |
| --- | ---: | ---: | --- |
| control (serena; Context Mode off) | 25,100 | — | serena connected |
| + ai-memory | — | — | not connected (see below) |
| + qmd | 25,700 | +600 | connected |
| + socraticode | — | — | not connected (see below) |
| + headroom | 25,100 | +0 | connected; its tools are deferred |
| + Context Mode (plugin and its MCP server, native name) | 26,800 | +1,700 | plugin listed, `plugin:context-mode:context-mode` connected |

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
  outside the total. At start-up a server adds its server instructions. qmd's +600 is the report's "MCP server
  instructions" row (60 to 641 tokens); the second set read +500 for the same row, which is within the client's
  rounding to the nearest 100. headroom and Context Mode send none, so headroom adds +0.
- Context Mode's +1,700 is, by the report's rows:
  - Skills +900;
  - Messages +1,731 (369 to 2,100);
  - System tools −892 (1,400 to 508).

  Its MCP tool definitions (8,700 to 19,700, deferred) are outside the total and count per task.
- The control is 300 tokens above the first set's (24,800): System prompt +200 and Memory files +100, on the same
  client. Each delta is taken within one set.

## Not measured here

- The other roles, the per-task cost, and the other client families (Codex, Muse, the researchers): the role matrix and
  the wiring change take these.
- The new host: its launches are measured there once installed.
