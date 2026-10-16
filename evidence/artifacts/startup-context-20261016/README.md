# Start-up context of the command center's launch, by component (2026-10-16)

Measured on 2026-10-16 with `tools/startup-context/startup_context.py` and `tools/startup-context/launches/CC.json`, client
2.1.301, model claude-opus-5-5, in the repository's working directory. Every run was a $0 `/context` report (0 turns, $0).

| Variant | Start-up tokens | Over the control | Loaded |
| --- | ---: | ---: | --- |
| control (serena; context-mode off) | 24,800 | — | serena connected |
| + ai-memory | — | — | not connected (see below) |
| + qmd | 25,400 | +600 | connected |
| + socraticode | — | — | not connected (see below) |
| + headroom | 24,800 | +0 | connected; its tools are deferred |
| + context-mode (plugin) | 26,600 | +1,800 | plugin loaded |

`receipts/` holds one receipt per variant and `CC.summary.json`.

## Findings, recorded as found

- The template's ai-memory server (`adoption/mcp/claude-user.json`, an HTTP URL on a fixed loopback port) did not connect:
  nothing listened on that port on this host on 2026-10-16. This session's own ai-memory server reaches it another way.
- The template's socraticode server runs a binary under the ecosystem prefix that is not installed on this host, where
  socraticode arrives as a plugin instead.
- Both are drift between the template and this host, for the template's owner; nothing here repairs them.
- Every server's MCP tool definitions are deferred under tool search: they load on demand, count per task and stay outside
  the total. What a server adds at start-up is its server instructions: qmd's +600 is the report's "MCP server instructions"
  row (60 to 641 tokens); headroom sends none, so it adds +0.
- Context Mode's +1,800 is, by the report's rows, Skills +900 and Messages +1,731, less System tools −892.

## Not measured here

- The other roles, the per-task cost, and the other client families (Codex, Muse, the researchers): the role matrix and
  the wiring change take these.
- The new host: its launches are measured there once installed.
