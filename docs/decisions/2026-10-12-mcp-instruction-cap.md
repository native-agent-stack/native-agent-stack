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
- The server is built for the cap. `akitaonrails/ai-memory@89bd8ded` `crates/ai-memory-mcp/src/server.rs` L169-L171 says: "Claude Code keeps only the first 2,048 characters, so everything before the 'Detailed tool routing
  follows' marker must stay self-contained and within that cap", and the test `handshake_core_survives_common_instruction_truncation` (L8087-L8112) fails the build when the marker is past character 2,048 or the core
  omits a required sentence (session-aware and static clients, untrusted history, no routine notes, broadening, the SessionStart handoff).

## Measurement (2026-10-12T20:21:29Z)

`python3 tools/adoption/mcp_instructions_length.py http://127.0.0.1:<ai-memory port>/mcp --cap 4096 --marker "--- Detailed tool routing follows. ---" --json`: one `initialize` request, no tool listed or called, the text
neither printed nor stored. The first host's ai-memory is 2.6.3 (`ai-memory --version`; its protocol version 2025-06-18).

| Quantity | Value |
| --- | --- |
| Instructions in the `initialize` result | 17,724 characters (17,803 bytes), sha256 prefix `32d8deb7c1ef5020` |
| Core, before the "Detailed tool routing follows" marker | 1,987 characters |
| Detail, after it | 15,699 characters, 23 tool-routing bullets |
| Client default cap (2.1.296) | 4,096 characters |
| The whole text over the cap | by 13,628 characters |
| What a cut at 4,096 keeps | the whole core and the first bullets: `memory_query`, `memory_recent` and `memory_status` cut inside its line |
| The server's tool descriptions (`tools/list`, lengths only) | 23 tools, 20,381 characters in all, median 902, largest 1,905 (`memory_write_page`): none reaches the cap, so none is cut |

The figures are in `evidence/artifacts/mcp-instruction-cap-20261012/measurement.json`; the `tools/list` figures come from `tools_list_lengths.py` beside it, which prints names and lengths only. The audit's 4,122 characters is not the live server's length; it matches neither the core nor the whole text.

## Decision

1. **`CLAUDE_CODE_MAX_MCP_DESCRIPTION_LENGTH` is not added** to the settings template. The part of the block the server marks as essential (1,987 characters) is inside the cap, as the server's own test requires; what the cap
   cuts is the detail part, one "when to use" bullet per tool (23), while each of the 23 tools also carries its own description (median 902 characters, none cut).
2. **The cost of the knob is stated.** Fitting the whole block needs the knob at 17,724 or more: 4.3 times the default for ai-memory alone, 13,628 more characters in every session (about 3,400 tokens at four characters per
   token, an estimate), and the same raised cap for every other server's descriptions and instructions. No measurement shows that the missing detail costs correctness, and a token cost enters a default only with evidence
   of a benefit.
3. **The premise is recorded as measured**: the audit's figure of 4,122 characters is superseded by 17,724 (core 1,987) at ai-memory 2.6.3.
4. **`tools/adoption/mcp_instructions_length.py`** measures any streamable-HTTP MCP server's instructions the same way, so the figure can be taken again at an ai-memory bump (`--cap 4096 --marker ...` exits 1 when the core
   outgrows the cap).

## Alternatives

- **The knob at 17,724 or more.** Rejected above: a certain cost against an unmeasured benefit, applied to every server.
- **The knob at a value that keeps more bullets (for example 8,192).** An arbitrary cut inside the detail; the same cost class, with a worse stopping rule.
- **`ai-memory install-instructions` into an instruction file.** The upstream's route for the detail. The repository's instruction files carry philosophy only (`2026-10-08-philosophy-only-rules.md`), so it is not taken.
- **A shorter block from the server.** The server has one instruction constant and no shorter mode (`server.rs` L172 at the pinned revision); changing the vendor's text is not ours (no upstream issue is filed; the owner's
  rule is to fix by documented usage).

## What this does not cover

Whether the 23 routing bullets change what the model does with ai-memory (not measured; a paired run with and without the detail would measure it); other servers' instruction lengths (the tool takes any HTTP endpoint,
and the stdio servers of the profile are not reached by it); a future ai-memory whose core is longer than the cap (the tool's exit status is the check); the token figure (an estimate from characters).

## Overturn conditions

- A measurement of the core above 4,096 characters at an ai-memory bump, or above the cap in force then: set the knob or ask for a smaller core, as that measurement shows.
- A paired same-task comparison in which the detail (the knob raised) raises correctness or lowers cost enough to pay its tokens: set the knob at the measured length.
- A client that changes the cap or how it cuts the text (the CHANGELOG entries above).

## Sources

- `anthropics/claude-code@3deb873687379f0c199a69fdaccc65f0865f7a29` `CHANGELOG.md` L65 (2.1.296: default 2,048 to 4,096 characters) and L1522 (2.1.280: `CLAUDE_CODE_MAX_MCP_DESCRIPTION_LENGTH`).
- `akitaonrails/ai-memory@89bd8ded3c1ab8b769cf99417d038ed0364403c8` `crates/ai-memory-mcp/src/server.rs` L169-L172 (the design comment and the constant) and L8087-L8112 (the core test). The mirror is at the 2.6.0 line and the
  host runs 2.6.3; the measurement above is of the running 2.6.3, whose marker is at character 1,987, under the 2,048 the test pins.
- The converged practice audit, group CPA-V-06 (`research/claude-practice-audit-converged-20261012/converged.json`, sha256 prefix `18a731a5`), and the command center's ruling of 2026-10-12T13:38:12Z.
- `docs/decisions/2026-09-29-max-default-effort.md` (the knob left as the user's decision), `docs/decisions/2026-10-08-philosophy-only-rules.md` (what the instruction files carry).
