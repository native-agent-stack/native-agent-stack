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
  Its native restore source immediately before the journal class (byte 228286338) declares
  `Vr=_({type:"restoring"})` and `Jr=_({type:"restored"})`; these two serialized control rows
  are accepted without granting any agent identity. A focused regression failed before this follow-up fix.
  The native transcript records advisor availability as an attachment with
  `{"type":"advisor_tool","available":true,"model":"...","toolChange":"add"}`.
  The pinned executable emits `toolChange:"add"` near zero-based byte224081124 and
  `available:false, toolChange:"remove"` near byte224080488; the fixture follows those native strings.
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

Touched and shared-adjudication regression modules passed: transcript audit 21, Claude collection 23, launch
commands 2, adjudication 116 (**162 tests**). The first FULL `python3 scripts/validate.py` failed solely because
the edited recipe's registered hash and byte count needed updating; the recipe entry is updated separately.
No judge or refuter was launched. The #992 landing hold remains in force.

## First-read corrections: registered keys and complete journal evidence

The first GPT read of `a2e3265087aa63711fca32cc7ae1a15fc42fb80b` found two P2 boundaries and an advisor-fixture
fidelity P3. The prior four-module command selection passed162 tests but omitted
`tests.test_verdict_lane_vendoring`. `python3 scripts/validate.py` verified file integrity and scope; it did not
establish the missing lane registry keys. The native vendoring module reproduces14 tests with five failures.

The corrected auditor requires a transcript for **every started identity in a present native journal**, even
when workflowProgress lists only the final attempt or this invocation audits a subset of items. Every missing
identity is named in the run issue and the collector's summary. A run issue voids its audited items; collection
does not emit a canonical accepted return. Restoring/restored control rows continue to grant no identities,
including when they carry agent-like fields. Legacy runs without a journal keep their bounded retry handling.
This conservative full-run rule avoids inferring an absent transcript's item or excusing lost earlier evidence.

The maintained native source remains Claude Code **2.1.296**, executable SHA-256 above: `Fo()` indexes started
rows next to the native v2 restore definitions near byte228286338; `Qr()` at byte228289997 validates the native
started identity. The journal proves the earlier attempt existed, and a lost file cannot establish its permitted
reads. The supported collector/auditor boundary is exercised by two synthetic regressions: an earlier attempt
reads `/outside/fixture`, then its transcript is deleted while its started identity remains. Before the fix,
the audit reports no run issue and collection writes a canonical return. Both regressions fail before the fix
and pass afterward. A second deleted earlier identity is also reported; restore controls remain excluded.

The advisor example and availability fixture now use native `toolChange:"add"`. The existing collection test
first failed on the old boolean field, then passed with the native string and corrected decision example.
A removal-only `available:false, toolChange:"remove"` control is accepted; removal after prior availability
does not erase the availability violation. These are fixture fidelity and local integration checks, not new
advisor/model execution.

The append-only registry preserves every earlier row from both the held PR and maintained main. Two complete
Claude keys are appended, one per supported workflow path, including the lane-prompt.md hash and corrected
auditor SHA-256 `c7d6232d7df922bcdc85e3c445b3bf88312f206842b39945489726d65355a5c1`. Current adjudication keys
are derived by executing `adjudicate.adjudication_provenance()` on the held PR source and an isolated merged
snapshot after #992 landed at main `9b3a39c43363f32ac61e74c674e4ba069593fe08`. Their adjudicate.py digests are
respectively `81645780e37d87756f10c5a023068105b9a4f32de8fcf3ca858ef60683caaad5` and
`9da98fd37870a56c25d1dc40a34636b540a6f1cfcca74e994c036eda2967797d`; both full keys are registered.
Main's four intervening historical adjudication registrations are retained byte-for-byte before these appends.
No history rewrite or landing rebase was performed. The actual landing must re-derive keys if its source moves.

Exact successful command, on both source snapshots:

```text
python3 -B -m unittest tests.test_transcript_audit tests.test_claude_lane tests.test_blind_lane_launch tests.test_adjudicate tests.test_verdict_lane_vendoring
```

The held PR with the correction passes179 tests; the merged snapshot with landed #992 passes193 tests, both
with zero skips. The explicit `python3 -B -m unittest tests.test_verdict_lane_vendoring` command separately
passes14/14 on both. The merged snapshot was built in a new detached worktree from9b3a39c4, merged with the
held PR without committing, then supplied the same correction source and the refreshed registry manifest
entry. It is a rehearsal; the PR's required ONE forward commit retains its exact a2e32650 parent/lease.
Receipts are retained under the private `pr993-review-fix-20261011` packet. No paid call, native journal change,
old collection rewrite, instruction/config change, blind key/export write or #995 change occurred.

## Micro correction: invalidate before the empty-directory exit

The GPT micro at `a4bd61b60a1c50d81f3c8c175957731d2af2cbb0` found a remaining collector ordering gap:
an empty transcript directory returned before the audit and left a prior accepted file and clean report intact.
The connector identified orphan `result`/`failed` journal rows that the start-only parser silently skipped.
Both are corrected together in one forward commit, with the old native evidence and all historical keys retained.

After provenance/result validation, the collector now always runs the audit and artifact invalidation, even for
an empty or missing transcript directory. It saves the failed audit, prints missing identities, and removes or
quarantines affected accepted returns before preserving exit2 for the no-transcript condition. Partial evidence
and zero-byte transcript files are audited; a clean resume after evidence restoration must pass a fresh audit.

The native journal parser now binds each `result` or `failed` identity/key to one **preceding** `started` row.
Missing, orphan, wrong-key, repeated or conflicting completion identities refuse, as do duplicate starts.
Native resume may reuse a key with a new agent identity; it is not a duplicate identity. Restore control rows
grant no identity. A started attempt without a completion remains subject to the completed-run record and
transcript audits rather than gaining acceptance from journal presence. The pinned Claude Code2.1.296
`Qr()` source at byte228289997 validates completion agent/key fields; the adjacent workflow source journals
the child start before its return. These unchanged primary bytes are retained in the private capture directory.

Four final public regressions transplanted onto exact prior `a4bd61b6` production run with19 failing subtests
and zero errors: single/multiple all-missing recollection, missing/partial/zero-byte directories, orphaned result
and failed collection, and the journal completion/start state matrix. Correction restores clean resume controls.
Every missing started identity is printed; invalid reports replace earlier clean reports. Removal-only advisor
and previous resume-boundary tests remain controls. Adjudication cache revalidation is checked one step wider:
after all transcripts disappear, cached judgments refuse by digest and the empty recollection exception cannot
make that judgment count. All collector/audit and adjudication collection/cache call sites were read directly.

Full current Claude keys under both workflow paths and the adjudication key were freshly derived with this
repository's own APIs, appended while preserving every historical list as an exact prefix, and hash/byte
registered in the evidence manifest. The exact generated fields and test receipts are retained privately.
This correction changes neither native journals/transcripts nor prompts, account/config state, paid work or #995.

## Capture-chain correction for the a191a1ca micro

The Astra micro at `a191a1ca1fe654258f4ba16dc6e7030517c90afd` verified the corrected
runtime but found that its review attachment carried the earlier capture seal and omitted the
current micro receipts. Retention on the lane host did not establish attachment to the reader.
This correction supplies the private attachments and makes their required bindings explicit.

The current `cited-captures-20261011/MANIFEST.sha256` is
`981aeb71fa758f6ab0f60fb7b540c3eb7abcca3e7b9cf47699d9c7c5dcb27740`, binding 449 files.
It supersedes original seal `d574beaca0c7692ed6f392adefb635e9748504dc1195ec65b809829f2c255653`.
Include `REDACTION-NOTES.md`: the unavailable original contents-API response hash
`9ea862224026dc640573c28f2a5e8aef2c8f6efc1637153ad390515a41dcdfe3` maps to the
redacted response `909c82810092811938b4771fbf60909cf917276ce798e4b940acbc3ee2389154`.
The authenticated workflow content and Git blob remain unchanged. The old seal identifies
historical bytes and must not be used to reconstruct or attach the removed access metadata.

The current `pr993-micro-fix-20261011/MANIFEST.sha256` is
`dc8305cc1d1b02557b1808fa7eca30883832c1ef4370b43c365d1637fa7eb5ac`, binding 63 files.
It supersedes original seal `f14b4567a3206cf31a7330e840219a2dd1a409a18530a229172a90d2c91c044c`
after its capture index and saved PR description were updated for the redaction. Attach this
packet under its declared name, including `final-regressions-prior-red.log`,
`final-audit-collector-green.log`, `final-six-modules.log`, `final-validate.log`,
`derive_provenance.py`, `provenance-derived.json`, the captured source/registry and
`call-sites.txt`. Also include the named historical `pr993-review-fix-20261011` receipts
for the earlier 179/193-test head/merged rehearsal, and the shared root `call-sites.txt`.
Historical sources and receipts retain their original revision identities.

The completed attachment is retained privately in `pr993-capture-chain-fix-20261011`.
Its `CITATION-CHECK.sha256` binds both current source seals, redaction notes, all cited
source/receipt files and each disclosed original-to-masked mapping. The supported check is
`sha256sum --strict --check CITATION-CHECK.sha256`, from its `attachments` directory;
missing files and incorrect seals must fail. This uses the installed uutils/coreutils
`0.10.0` command and its upstream
[sha256sum missing-file tests](https://github.com/uutils/coreutils/blob/0.10.0/tests/by-util/test_sha256sum.rs).
The previous reader attachment fails that same check; the completed attachment passes.
Omitted-note, omitted-current-receipt, stale-seal, missing-historical-receipt, altered-masked-data
and missing-pinned-binary controls are checked separately. Local checksum checks are attachment
verification, not a new native model run or an ACK from a subsequent independent reader.

Transport copies use the unchanged co-op `mask_packet.py` identified in the private correction
index. Preserve each source `MANIFEST.sha256` byte-for-byte and supply `MASKED.tsv` with source
and transport hashes plus the final transport manifest. Include the full pinned Claude executable
at its recorded 257068216 bytes and SHA-256 `24972e3bc859fab2b46ed4c1e51f7d6130f06d3bd550811a114640de3370d0de`;
its documented recovery from the transport helper's binary exclusion leaves upstream bytes intact.
Before either next micro, attach the complete correction archive and check its transport seal and
citation check from the extracted reader directory. A missing attachment or unexplained hash
difference continues to block ACK.
