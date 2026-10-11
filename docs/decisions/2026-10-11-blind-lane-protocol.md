# Audit every blind Claude attempt and exclude unauditable context

The October 10 tier-1 collection exposed two independent gaps. Claude Code added its server-side advisor even
though the role listed only Read, Glob and Grep, and workflow resume rebuilt progress without every original
attempt. The old audit quarantined eight finals for advisor use and reported only three names from twenty
unaccounted attempts on those eight items. The CC accepted that historical collection under its executed-action
review; this change governs subsequent runs and does not rebuild or replace that acceptance or its receipts.

## Primary sources and choice

- Installed `claude --version`: **2.1.296**. The native executable at
  `~/.local/share/claude/versions/2.1.296` has SHA-256
  `24972e3bc859fab2b46ed4c1e51f7d6130f06d3bd550811a114640de3370d0de`.
  Its embedded JavaScript at byte 214409014 (zero-based) contains `Rkt()`:
  `if(a.CLAUDE_CODE_DISABLE_ADVISOR_TOOL||Mj())return!1`.
  Both reviewer and adjudicator launches therefore set `CLAUDE_CODE_DISABLE_ADVISOR_TOOL=1`.
  Role tool lists alone do not control this tool.
- The same executable's CLI declaration at byte 225734757, confirmed with its `--help`, says
  `--strict-mcp-config` will "Only use MCP servers from --mcp-config, ignoring all other MCP configurations".
  Both documented launches supply that flag and supply no `--mcp-config`. They keep the existing hook disable
  and background-wait controls. The concrete adjudication command is the CC's next launch recipe.
- [anthropics/claude-code v2.1.296 release](https://github.com/anthropics/claude-code/releases/tag/v2.1.296),
  published 2026-10-09T19:28:59Z, was read through the GitHub release API. Its notes include headless MCP startup
  corrections and an increased default MCP instruction limit. Those notes corroborate the relevant surface;
  the installed executable and CLI help establish the controls used here.
- Claude Code 2.1.296's embedded journal parser at byte 228289997 records `started`, `result` and `failed` rows
  with `key` and `agentId`; the actual tier-1 journal additionally records `label` on each `started` row.
  The native transcript records advisor availability as an attachment with
  `{"type":"advisor_tool","available":true,"model":"...","toolChange":true}`.
  The audit now refuses that availability even without a call, and still refuses every advisor call.
- The native saved workflow is
  [seathatflowsinourveins/agent-lab at e070125dae03b4e44484ccb78d2d65057ad38f40](https://github.com/seathatflowsinourveins/agent-lab/tree/e070125dae03b4e44484ccb78d2d65057ad38f40),
  `.claude/workflows/layer-verdict-lane.js` (packet identity echo, upstream #47), workflow SHA-256
  `fd77b74945e9d2bd0b26b7822aabcde00e7e650c327da16d852fdbfd5984c0d6`.
  This change consumes its native journal and keeps the shipped workflow and roles unchanged.

With a journal present, an earlier transcript must have its own started identity and match the label of a listed
agent serving that same item. A final progress entry must bind the journal's agent and label. Every attempt's
paths and tools are still audited. Unknown, malformed or conflicting journal rows fail closed. Pre-journal
records keep their existing bounded retry accounting. The transcript digest now also binds journal bytes.
The report names all unaccounted transcripts, including when another run-level problem is already present.

The alternative of allowing advisor was superseded by the CC because its encrypted replies cannot be audited.
Counting spare retry ordinals alone also fails to identify native resume attempts. Revisit the choice if a future
installed client changes these interfaces or exposes an auditable supported advisor mechanism; first reproduce
that version's behavior and update the regression fixtures from its primary source.

## Regressions: observed failure before each fix

All commands use `python3 -m unittest discover -s tests -p <module>`, with `-k <case> -v` for focused runs.
The seams are the existing public `transcript_audit.audit`, `claude_lane.main` collection command and documented
recipe launch commands, as authorized by the CC's protocol cue.

| Module / case | Before fix, exit 1 | After fix, exit 0 |
| --- | --- | --- |
| `test_claude_lane.py`, `available_advisor` | Canonical return incorrectly existed (`True is not false`) despite availability and no call | Canonical return absent; audit names advisor availability |
| `test_transcript_audit.py`, `resumed_attempts` | `agent-old.jsonl` unaccounted despite exact native started rows | Both attempts attributed and audited; outside Read and absent journal identity still flag |
| `test_transcript_audit.py`, `every_unaccounted` | Fourth name `agent-unaccounted-03.jsonl` absent from diagnostic | Every one of twenty names appears |
| `test_claude_lane.py`, `prints_every` | No unaccounted name printed by the collector | All twenty names are present in its JSON stdout |
| `test_blind_lane_launch.py` | Missing concrete adjudication launch; reviewer lacks both advisor env and strict MCP flag | Both complete launch commands carry the controls, with no explicit MCP config |

The launch test initially needed an anchored parser to avoid treating a commented child-usage example as a
launch. That fixture-parser error was corrected; no production requirement was relaxed. The outside Read,
nonempty advisor call and unknown-tool negative controls remain enforced. Fixtures are synthetic evidence;
these tests do not start clients or dispatch models.

## Actual retained run: read-only replay of the new audit

On 2026-10-11, the new auditor processed the original native run's 73 transcripts and journal without writing
to native state. Result: `run_issue=None`; all twenty earlier attempts on the eight final items are accounted.
There are twenty-two earlier identities over the whole run, including two on the item without a final. The
eight historical finals still flag under the new advisor policy (65 availability attachments and 65 calls in
the audited final-item scope). Their previous CC acceptance remains a separate historical ruling.
This is a local integration over retained native evidence, not a newly executed blind model run.

Touched and shared-adjudication regression modules passed: transcript audit 20, Claude collection 23, launch
commands 2, adjudication 116 (**161 tests**). The first FULL `python3 scripts/validate.py` failed solely because
the edited recipe's registered hash and byte count needed updating; the recipe entry is updated separately.
No judge or refuter was launched. The #992 landing hold remains in force.
