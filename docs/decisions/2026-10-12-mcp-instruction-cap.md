# ai-memory's MCP instructions against the client's 4,096-character cap: no knob, 2026-10-12 (CPA-V-06)

Status: decided by measurement. The converged Claude practice audit (group CPA-V-06, accepted as the work queue by the command center's ruling of 2026-10-12T13:38:12Z) proposed adding
`CLAUDE_CODE_MAX_MCP_DESCRIPTION_LENGTH` to the settings template "at the smallest value that fits the block", on the premise that the block is 4,122 characters (marked "not re-checked" there). The block was
measured: it is 17,724 characters, the part that must reach the model is 1,987, and the knob would not be set at a small value. The audit's pull request is therefore not made; this record is its supersession.

## Context

- The audit's finding: ai-memory's instruction text is longer than the client's default cap, so its routing text for `memory_status` and every later tool never reaches the model (reproduced: the session header of the
  audit's analyst ends in a truncation marker after the `memory_status` line). The finding is right; the figure and the remedy are not.
- Claude Code 2.1.296 raised the default limit on MCP tool descriptions sent up front and on MCP server instructions from 2,048 to 4,096 characters (`anthropics/claude-code@3deb8736` `CHANGELOG.md` L65).
  `CLAUDE_CODE_MAX_MCP_DESCRIPTION_LENGTH` changes the cap "for every MCP server in the session" (L1522, 2.1.280). The 2026-09-29 record (`2026-09-29-max-default-effort.md`) left the knob as the user's decision for the same
  reason this record gives: raising it restores text at a token cost.
- The server is built for the cap. `akitaonrails/ai-memory@385b81ea` (tag v2.6.3, the running version) `crates/ai-memory-mcp/src/server.rs` L169-L171 says: "Claude Code keeps only the first 2,048 characters, so everything
  before the 'Detailed tool routing follows' marker must stay self-contained and within that cap", and the test `handshake_core_survives_common_instruction_truncation` (L8163-L8189) fails the build when the marker is
  past character 2,048 or the core omits a required sentence (session-aware and static clients, untrusted history, no routine notes, broadening, the SessionStart handoff). The mirror's manifest pin, `89bd8ded` (2.6.0), has
  the same design comment and a constant of 16,702 characters with the same 1,987-character core; the figures below are those of 2.6.3.

## Resolution protocol ([2026-10-11-layer-resolution-protocol.md](2026-10-11-layer-resolution-protocol.md))

This record touches the durable-memory layer only through its incumbent's configuration: the instruction text ai-memory serves and the client's cap on it. It adds no candidate, compares none and reopens nothing. Consumed before
writing it:

- **Verdict:** `catalogs/landscape/foundation.json`, layer `durable-memory`: decision `keep_but_compare`, `verdict_status` recorded, layer `checked_at` 2026-09-22; `winners[0]` is ai-memory pinned 2.3.2 there, and the host runs 2.6.3
  (the measurement below is of the running server).
- **Wave:** no wave of `catalogs/sota-convergence/layer-verdict-waves.json` names this layer, which is an explicit gap and not an input. The test below fails if one appears, so the record is revisited then.
- **Latest sweep covering the layer:** `landscape-sweep-20260929` (completed 2026-09-29; `catalogs/sota-convergence/manifest-20260929.json`, `evidence/artifacts/landscape-sweep-20260929/returns.json`; the `head_sha256` field of
  `catalogs/saturation/ledger.json` began `ec575b95c0558750` when read, and does at `489b26328`, this change's base, and at `738fdf700`; the file's own sha256 begins `b6ca3220516a515b`, a different thing). Its survivors for the layer are `vshulcz/deja-vu`, `vectorize-io/hindsight`, `rohitg00/agentmemory`, `mempalace/mempalace` and `tigerless-labs/agent-memory`; its `reopen[]` holds five `pin_moved`
  receipt-staleness triggers. All of them are carried forward as that sweep left them: this record adjudicates none.
- **Bounded delta:** fill the named evidence gap. The audit's figure for the incumbent's instruction block was marked "not re-checked"; the measurement replaces it. Nothing about which memory system is the layer's choice changes.

## Measurement (2026-10-12T23:47:58Z)

`python3 tools/adoption/mcp_instructions_length.py http://127.0.0.1:<ai-memory port>/mcp --cap 4096 --marker "--- Detailed tool routing follows. ---" --bullet "- \`" --json`: one `initialize` request, no tool listed or called, the text
neither printed nor stored. The first host's ai-memory is 2.6.3 (`ai-memory --version`). The handshake answered with protocol version 2025-06-18, the one the tool asked for; the source's default is 2024-11-05
(`server.rs` L6275 at v2.6.3), and neither touches the instruction text. "Characters" below are Unicode code points; UTF-16 code units, the unit of a JavaScript string length, are given beside them because which unit the
client's cap counts is not verified here.

| Quantity | Value |
| --- | --- |
| Instructions in the `initialize` result | 17,724 characters, 17,725 UTF-16 units (one character, U+1F4E5, is outside the Basic Multilingual Plane), 17,803 bytes, sha256 prefix `32d8deb7c1ef5020` |
| The constant in the v2.6.3 source (`source_constant_length.py`) | the same: 17,724 characters, 17,725 UTF-16 units, sha256 prefix `32d8deb7c1ef5020`; at the 2.6.0 pin `89bd8ded`: 16,702 characters (16,703 units), core 1,987 |
| Core, before the "Detailed tool routing follows" marker | 1,987 characters |
| Detail, after it | 15,699 characters, 23 tool-routing bullets (detail lines that start with "- `") |
| Client default cap (2.1.296) | 4,096 characters |
| The whole text over the cap | by 13,628 characters (13,629 UTF-16 units) |
| What a cut at 4,096 keeps | the whole core and the start of the detail: 3 of the 23 bullets start under the cap and the third is cut by it (the truncated block in this session's header ends inside the `memory_status` line) |
| The server's tool descriptions (`tools/list`, lengths only) | 23 tools, 20,381 characters in all, median 902, largest 1,905 (`memory_write_page`): none reaches the cap, so none is cut |

The figures are in `evidence/artifacts/mcp-instruction-cap-20261012/measurement.json`, which holds the verbatim output of each command (the tool, `tools_list_lengths.py`, which prints names and lengths only, and `source_constant_length.py`, which reads the constant out of the source); the audit's group is retained beside it as `audit-group-CPA-V-06.json`. The audit's 4,122 characters is not the live server's length; it matches neither the core nor the whole text.

## Decision

1. **`CLAUDE_CODE_MAX_MCP_DESCRIPTION_LENGTH` is not added** to the settings template. The part of the block the server marks as essential (1,987 characters) is inside the cap, as the server's own test requires; what the cap
   cuts is the detail part, one "when to use" bullet per tool (23), while each of the 23 tools also carries its own description (median 902 characters, none cut).
2. **The cost of the knob is stated.** Fitting the whole block needs the knob at 17,725 (UTF-16 units; 17,724 code points) or more: 4.3 times the default for ai-memory alone, 13,629 more units in every session (about 3,400
   tokens at four characters per token, an estimate), and the same raised cap for every other server's descriptions and instructions. No measurement shows that the missing detail costs correctness, and a token cost enters a default only with evidence
   of a benefit.
3. **The premise is recorded as measured**: the audit's figure of 4,122 characters is superseded by 17,724 (core 1,987) at ai-memory 2.6.3 (16,702 at the mirror's pin, 2.6.0).
4. **`tools/adoption/mcp_instructions_length.py`** measures any streamable-HTTP MCP server's instructions the same way, so the figure can be taken again at an ai-memory bump (`--cap 4096 --marker ...` exits 1 when the core
   outgrows the cap). A server that answers with an event stream may send requests and notifications before the response to the POST (MCP 2025-06-18, `transports.mdx` L104-L106), so the tool reads the stream event by event until
   the response with its request's id and skips the rest; a malformed URL, a transport failure and a reply without that response are exit 2 with a fixed message. `tools_list_lengths.py` reads the same way and sends the
   negotiated `MCP-Protocol-Version` and the session id on the requests after initialize (`transports.mdx` L240-L250). ai-memory itself answers with plain JSON, no stream and no session (measured, counts only).

## Alternatives

- **The knob at 17,725 or more.** Rejected above: a certain cost against an unmeasured benefit, applied to every server.
- **The knob at a value that keeps more bullets (for example 8,192).** An arbitrary cut inside the detail; the same cost class, with a worse stopping rule.
- **`ai-memory install-instructions` into an instruction file.** The upstream's route for the detail. The repository's instruction files carry philosophy only (`2026-10-08-philosophy-only-rules.md`), so it is not taken.
- **A shorter block from the server.** The server has one instruction constant and no shorter mode (`server.rs` L172 at v2.6.3); changing the vendor's text would fork what upstream ships, which AGENTS.md (Native engineering defaults) rules out: "Never rebuild or fork what an upstream already ships".

## What this does not cover

Whether the 23 routing bullets change what the model does with ai-memory (not measured; a paired run with and without the detail would measure it); other servers' instruction lengths (the tool takes any HTTP endpoint,
and the stdio servers of the profile are not reached by it); a future ai-memory whose core is longer than the cap (the tool's exit status is the check); the token figure (an estimate from characters).

## Overturn conditions

- A measurement of the core above 4,096 characters at an ai-memory bump, or above the cap in force then: set the knob or ask for a smaller core, as that measurement shows.
- A paired same-task comparison in which the detail (the knob raised) raises correctness or lowers cost enough to pay its tokens: set the knob at the measured length.
- A client that changes the cap or how it cuts the text (the CHANGELOG entries above).

## Sources

- `anthropics/claude-code@3deb873687379f0c199a69fdaccc65f0865f7a29` `CHANGELOG.md` L65 (2.1.296: default 2,048 to 4,096 characters) and L1522 (2.1.280: `CLAUDE_CODE_MAX_MCP_DESCRIPTION_LENGTH`).
- `akitaonrails/ai-memory@385b81ea95f7b73ede7146d0ae606c4caa7b43c1` (tag v2.6.3, the running version) `crates/ai-memory-mcp/src/server.rs` L169-L172 (the design comment and the constant), L6275 (the protocol-version default
  2024-11-05) and L6276 (`with_instructions`), and L8163-L8189 (the core test); its marker is at character 1,987, under the 2,048 the test pins. The mirror's manifest pin, `89bd8ded3c1ab8b769cf99417d038ed0364403c8` (2.6.0), has
  the same comment and a 16,702-character constant.
- `modelcontextprotocol/modelcontextprotocol@1f520964b295d58494d944f2aea8a5ab51c79f77` `docs/specification/2025-06-18/basic/transports.mdx` L84-L110 (a POST of a request is answered with one JSON object or an event stream, which may
  carry requests and notifications before the response and is closed after it), L240-L250 (`MCP-Protocol-Version` on every request after initialize, the negotiated version); `basic/lifecycle.mdx` L107 (the `initialized`
  notification); `server/tools.mdx` L57-L97 (`tools/list`, `nextCursor`); `schema/2025-06-18/schema.ts` L199-L213 (the optional `instructions` of the initialize result).
- The converged practice audit, group CPA-V-06, retained verbatim in `evidence/artifacts/mcp-instruction-cap-20261012/audit-group-CPA-V-06.json` (the full `converged.json` stays in the private research record, and no digest of it is
  published), and the command center's ruling of 2026-10-12T13:38:12Z that accepted the converged set as the work queue (a coordination record, cited by name and time).
- `docs/decisions/2026-09-29-max-default-effort.md` (the knob left as the user's decision), `docs/decisions/2026-10-08-philosophy-only-rules.md` (what the instruction files carry), `docs/decisions/2026-10-11-layer-resolution-protocol.md` (the inputs consumed above).
