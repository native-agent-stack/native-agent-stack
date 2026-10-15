# Harness practice rows for the new host: layer resolution before any row, 2026-10-15

Status: scoping record (steps 1 to 3 of the layer-resolution protocol). It writes no practice row and changes no default. Rows follow
in this change only from converged, cited inputs, once the inputs named under "Readiness" exist.

## Trigger

On 2026-10-15 at 15:46 ET the owner directed that the new host's harness carry a more advanced fleet view (every lane, unit, worker
and order path), agent-orchestration practice, token saving with a maintained context lead in each long session, and context
engineering against context rot for runtime-worker sessions (compaction policy, fresh relaunch at boundaries, handoffs), with the
practice skill on 2.1.301. At 15:59 ET and 16:04 ET they widened it to the full harness landscape, enabled per role. At 16:47 ET the
owner corrected the command center: practice content comes from research convergence, not from command-center design. The command
center's correction record of 2026-10-15 (20:48Z) withdrew its own definition of the context lead and routed the context-engineering
practice to this protocol. These are dated paraphrases; the coordination records are cited by name and date.

## Requirements recorded since (inputs, not decisions)

At 17:54 ET on 2026-10-15 the owner asked for a new-host command center whose fleet view and orchestration use the SOTA
platforms' own views through their MCP servers and native CLIs. The command center recorded this as dated requirements
(addendum 10 to its 19:12Z direction, a coordination record cited by name and date) and routed two of them here:

- **R2:** the fleet view and orchestration use each platform's own views (GitHub, agentsview, Grafana and the other
  converged platforms) through their shipped MCP servers and CLIs, with nothing rebuilt by the command center
  (AGENTS.md: never rebuild what an upstream ships).
- **R3:** CLI first; MCP where the platform ships a server; each pinned, with an install receipt and an inverse.

They bind the fleet-view and orchestration rows here and the framework rows of the framework change. The platform MCP and
CLI candidates are screened by the co-op; a row names only a converged winner, and anything else stays a PROPOSAL.

## Step 1: layer verdicts read

At `origin/main` 8053f14e7 (`catalogs/landscape/foundation.json`, every row `recorded`, wave 20260922 in
`catalogs/sota-convergence/layer-verdict-waves.json`):

| Layer | foundation.json | Decision | Winners | Open gaps | final-stack.json |
| --- | --- | --- | --- | --- | --- |
| native-clients | `/layers/0` | retain | anthropics/claude-code, openai/codex | 14 | `/layers/11` reopened |
| instructions-skills | `/layers/1` | adjust | affaan-m/ECC, typesafe-ai/skills, openai/skills | 12 | `/layers/7` reopened |
| workers | `/layers/2` | keep_but_compare | anthropics/claude-code, max-sixty/worktrunk | 10 | `/layers/20` reopened |
| durable-memory | `/layers/7` | keep_but_compare | akitaonrails/ai-memory | 15 | `/layers/4` reopened |
| token-efficiency | `/layers/9` | keep_but_compare | rtk-ai/rtk, headroomlabs-ai/headroom, ccusage/ccusage | 8 | `/layers/18` reopened |
| scheduling-supervision | `/layers/12` | keep_but_compare | dagucloud/dagu, systemd/systemd | 14 | `/layers/15` reopened |
| observation-inference | `/layers/15` | keep_but_compare | opentelemetry-collector-contrib, prometheus, loki | 11 | `/layers/12` reopened |

Every final-stack row above has terminal state null, verdict wave 20260922 and `next_review` 2026-10-22; `/summary/final_layers` is 0.
No layer here is FINAL, so none needs a change-detecting sweep to reopen.

## Step 2: latest sweep read

The latest ledger row for all seven layers is `catalogs/saturation/ledger.json` `/sweeps/4`, `landscape-sweep-20260929`
(manifest `catalogs/sota-convergence/manifest-20260929.json`, returns `evidence/artifacts/landscape-sweep-20260929/returns.json`):

| Layer | Row | Survived | Reopen entries |
| --- | --- | --- | --- |
| native-clients | `/sweeps/4/layers/0` | none | 5 |
| instructions-skills | `/sweeps/4/layers/1` | mattpocock/skills | 5 |
| workers | `/sweeps/4/layers/2` | openai/codex | 3 |
| durable-memory | `/sweeps/4/layers/7` | vshulcz/deja-vu, vectorize-io/hindsight, rohitg00/agentmemory, mempalace/mempalace, tigerless-labs/agent-memory | 5 |
| token-efficiency | `/sweeps/4/layers/9` | ojuschugh1/sqz, paritok-official/paritok-4b-v1, lockedinlabs-ai/agent-console | 1 |
| scheduling-supervision | `/sweeps/4/layers/12` | dagucloud/dagu, restatedev/restate, conductor-oss/conductor, microsoft/pg_durable | 3 |
| observation-inference | `/sweeps/4/layers/15` | none | 4 |

A completed sweep awaits its ledger append: `evidence/artifacts/w6-layer-verdict-20261011/resolution-delta.json`
(`ledger_append_pending`) names `landscape-sweep-20260926-gpt6-fit-revote-20261003`, retained at
`evidence/artifacts/landscape-sweep-20260926-gpt6-fit-revote-20261003/tabulation.json`, scoped to completing the frozen 09-26 fit
proposals. Its survivors carry forward with the ledger's until a retained adjudication settles them. This record does not reconstruct
earlier sweeps' survivors; the screens below do, per layer.

## Step 3: the delta, and what each row waits for

No new survey is dispatched from here. The delta is:

1. **Context engineering for long and runtime-worker sessions** (token-efficiency, durable-memory, instructions-skills): the
   co-op's runtime-worker context-engineering research (#1181, a TRIAL policy proposal, under its reads) and its screens of those
   layers' full candidate sets (screens plan of 2026-10-15, wave 2), plus the vendor sources below. Rows for a context lead,
   context headroom, compaction, relaunch at boundaries, handoffs and role-based enablement are written only where these converge,
   and are measured first-hand where they disagree.
2. **Fleet view** (observation-inference): the latest sweep left no survivor and its returns retain failures for the layer (the
   reopen entries above), an open gap. The vendor's documented session-state interface is a primary input to the row, not its
   decision; the row also waits on the observation-inference screen.
3. **Agent orchestration and frameworks** (workers, instructions-skills, the practice skill's `orchestration-frameworks` slot): the
   co-op's framework screens (wave 1). This goes to the framework-rows change, so one change edits that slot.

## Primary sources captured for the rows

Retained on the host (2026-10-15) with their sha256; a row cites the page, line and the first 16 hex digits of the capture, as the
practice pages already do, and the change that writes a row retains the bytes it cites:

- Claude Code documentation for client 2.1.301, fetched 2026-10-15 between 20:05:17Z and 20:05:21Z from `https://code.claude.com/docs/en/<page>.md`:
  agent-view (`c8e2b81092b94b4b`), statusline (`bbe651578fa8edf2`), context-window (`78bf25a505d7563d`), costs (`4f4bca5c46ea26db`),
  best-practices (`3f2d4f1a6eeba4cb`), hooks (`f5957ad68ec47ada`), sub-agents (`a0c1d6fb66b6f3d8`), settings-reference
  (`8ba90434d2801f9e`), cross-session-messaging (`7b359027749ff27d`), agents (`67874a4189558b75`), workflows (`a324b4814d760d6c`),
  monitoring-usage (`72374067fb003eb1`), and 14 more pages (sessions, analytics, agent-teams, worktrees, large-codebases,
  prompt-caching, memory, how-claude-code-works, checkpointing, headless, goal, scheduled-tasks, env-vars, commands).
- `anthropics/claude-code@03b5892ee77de289bcd5dfa39f541525ade74aff` `CHANGELOG.md` (the 2.1.301 currency record's source).
- Anthropic, "Effective context engineering for AI agents" (2025-09-29,
  <https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents>), fetched 2026-10-15T20:48:33Z, sha256
  `3995d033c8c30b9818cce02c01fdc3cac1eeb48380cf6908fed49c47d27499e2`: context rot, compaction, structured note-taking and
  sub-agent architectures as the long-horizon techniques.

Still to capture, by the research lanes or the row change: the Codex, Pi, OpenCode and Muse documentation at their pins.

## Readiness

Each row starts when its inputs exist: #1181 landed or its policy record retained at a read-accepted head; the screen rows of its
layer in a pull request; and, where those disagree with the vendor sources, the first-hand measurement named in the row's record.
No row starts on a date.

## Sources

- `docs/decisions/2026-10-11-layer-resolution-protocol.md` (steps 1 to 3).
- `catalogs/landscape/foundation.json`, `catalogs/landscape/final-stack.json`, `catalogs/sota-convergence/layer-verdict-waves.json`,
  `catalogs/saturation/ledger.json`, `evidence/artifacts/w6-layer-verdict-20261011/resolution-delta.json`, at `origin/main` 8053f14e7.
- The command center's direction of 2026-10-15 (19:46Z), its addenda of 15:59 ET and 16:04 ET, and its correction record of
  2026-10-15 (20:48Z): coordination records, cited by name and date.
- The co-op's screens plan of 2026-10-15 (20:07Z) and dispatch register: coordination records, cited by name and date.
