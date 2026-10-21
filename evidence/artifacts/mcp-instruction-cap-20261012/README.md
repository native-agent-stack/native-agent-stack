# ai-memory's MCP instructions against the client's cap (2026-10-12)

The record is [`docs/decisions/2026-10-12-mcp-instruction-cap.md`](../../../docs/decisions/2026-10-12-mcp-instruction-cap.md). `measurement.json` holds the verbatim output of the commands below, with their provenance; the
record's figures are read from it.

- `python3 tools/adoption/mcp_instructions_length.py http://127.0.0.1:<port>/mcp --cap 4096 --marker "--- Detailed tool routing follows. ---" --bullet "- \`" --json` sends one `initialize` request and prints the length of the
  server's `instructions` (never the text) in characters, UTF-16 units and bytes, the core and detail lengths around the marker, the detail-line counts and whether the core is inside the cap (exit 1 when it is not).
- `python3 tools_list_lengths.py http://127.0.0.1:<port>/mcp --json` sends `initialize`, `notifications/initialized` and `tools/list` (following `nextCursor`), with the negotiated `MCP-Protocol-Version` and the session id on
  the requests after initialize, and prints the number of tools and the lengths of their descriptions (never the descriptions). Both HTTP scripts read an event stream until the response with the request's id (a server may send
  notifications first), and both end with exit 2 and a fixed message when the URL or the reply is unusable.
- `python3 source_constant_length.py <ai-memory checkout>/crates/ai-memory-mcp/src/server.rs MEMORY_INSTRUCTIONS --marker "--- Detailed tool routing follows. ---"` reads the constant out of the source the way the compiler does
  and prints the same counts and hash prefix: at the v2.6.3 tag (`385b81ea`) it equals what the running server sends.
- `audit-group-CPA-V-06.json` is the audit's group, copied verbatim from the full file, which stays private (no digest of it is published).

None of them lists a memory page, calls a tool or sends a credential. The port is the one the host's ai-memory unit binds (`AI_MEMORY_URL`).

`receipts/` holds the value-free captures behind the record's claims about the tools: `mutants-tool-round1-16.txt` and `mutants-round2-38.txt` (every mutant killed by `tests/test_mcp_instruction_cap.py`),
`fail-before-round2.txt` (the round-2 tests against the sources before the round) and `ai-memory-reply-shape.txt` (the running server answers with plain JSON, status 202 for the notification, no session: counts and
header names only). They show what was run; they are the author's runs, not a measurement by another party. The first run of the 11 mutants of the first build and the audit's own text are not kept.
