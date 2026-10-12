# ai-memory's MCP instructions against the client's cap (2026-10-12)

The record is [`docs/decisions/2026-10-12-mcp-instruction-cap.md`](../../../docs/decisions/2026-10-12-mcp-instruction-cap.md). `measurement.json` holds the counts it quotes.

- `python3 tools/adoption/mcp_instructions_length.py http://127.0.0.1:<port>/mcp --cap 4096 --marker "--- Detailed tool routing follows. ---" --json` sends one `initialize` request and prints the length of the server's
  `instructions` (never the text), the core and detail lengths around the marker, and whether the core is inside the cap (exit 1 when it is not).
- `python3 tools_list_lengths.py http://127.0.0.1:<port>/mcp` sends `initialize`, `notifications/initialized` and `tools/list` and prints the number of tools and the lengths of their descriptions (never the descriptions).

Neither call lists a memory page, calls a tool or sends a credential. The port is the one the host's ai-memory unit binds (`AI_MEMORY_URL`).
