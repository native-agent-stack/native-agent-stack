# Resolution protocol re-verification

Read order: repository `AGENTS.md`, `docs/decisions/2026-10-11-layer-resolution-protocol.md`, supplied `runtime-workers.context-eng.protocol-20261015T1957Z.md`, #1033, both Muse decisions, and #1174 Decisions 5–6. The old branch lacked the protocol decision; after confirming the tree was clean, `git fetch origin` and a new branch from `origin/main` supplied the requested exact base. No work was built on the old branch.

Branch: `codex/runtime-worker-context-engineering-20261015`. Verified base: `8053f14e7e0817d2502dff2bb284bfb7e1b0152f`.

The directing record `direction-cc-20261015T1946Z-north-star-new-wsl-takeover.md` was hash-verified as `4dfcb47245607bd3b3fb53bbdd49a561b1b157beccf02f9309623b23ffa2ad82`; its text is not reproduced. The co-op's task record bounds this delta to worker compaction, relaunch, handoffs, context maintenance and token saving. Command-center practice remains out of scope.

## Step 1: verdict, evidence and applicable wave

Both `foundation.json` and the wave were read. Wave `20260922` is the sole entry in `layer-verdict-waves.json`; `layer-verdicts-20260922.json` hashes to `2fef6da7468a8e97a319fdc6f75f73374cd34b412bf93de90fd0c2a7504159de`, matching the supplied record and wave index.

| Foundation layer | Verdict at base | Recorded winners (catalog pins, not current installed versions) | Open gaps |
| --- | --- | --- | --- |
| token-efficiency | recorded | rtk-ai/rtk `0.49.0`; headroomlabs-ai/headroom `0.37.0`; ccusage/ccusage `20.0.24` | 8 |
| durable-memory | recorded | akitaonrails/ai-memory `2.3.2` | 15 |
| instructions-skills | recorded | affaan-m/ECC `dd6ee538aee0f548d4a6b520118f875431fd749e`; typesafe-ai/skills and openai/skills `unpinned` | 12 |
| workers, adjacent only | recorded | anthropics/claude-code `2.1.278`; max-sixty/worktrunk `0.79.0` | 10 |

The evidence consumed includes each selected layer's `evidence_refs` and winner rationale, plus `docs/token-practice.md`, `docs/native-memory-rag-lifecycle.md`, `catalogs/landscape/native-practice.json` and #1033's vendor contracts, qualification and final-adjudication receipts. Their boundaries remain: artifact compression is not measured provider savings; native discovery is not quality parity; memory lifecycle success is not semantic recall superiority; profile smokes are not the preregistered worker comparison.

**Correction to the supplied protocol:** `catalogs/landscape/angles/foundation-workers.json` contains two candidates, OpenHands SDK + Agent Server and mini-swe-agent, with current verdicts **INSUFFICIENT**, not COMPARISON_ARM. Their previous verdicts are DISAGREE and CONVERGED respectively. This changes no candidate or layer record.

There is no dedicated runtime-worker context-policy layer among the catalog's layer ids. That absence remains a gap; the mapping is proposed in [policy-trial.md](policy-trial.md), not added to the catalog.

## Step 2: latest retained sweep and carry-forward

Latest ledger sweep covering all four layers is `landscape-sweep-20260929`, manifest `catalogs/sota-convergence/manifest-20260929.json`, returns `evidence/artifacts/landscape-sweep-20260929/returns.json`. Both retained file hashes match the ledger. The later `manifest-20261009.json` and ledger sweep concern other layers; they do not supersede this sweep. The supplied task record states no completed relevant sweep is awaiting a ledger append; the newer published manifest check found no relevant layer, with no claim about unexposed private work.

| Layer | Latest proposed / survived / refuted | Latest survivors | Reopen records |
| --- | --- | --- | --- |
| token-efficiency | 11 / 3 / 8 | ojuschugh1/sqz; paritok-official/paritok-4b-v1; lockedinlabs-ai/agent-console | retained_failure |
| durable-memory | 8 / 5 / 3 | vshulcz/deja-vu; vectorize-io/hindsight; rohitg00/agentmemory; mempalace/mempalace; tigerless-labs/agent-memory | pin_moved ×5 |
| instructions-skills | 8 / 1 / 7 | mattpocock/skills | pin_moved ×5 |
| workers | 8 / 1 / 7 | openai/codex | pin_moved ×3 |

`final-stack.json` marks all four layers **reopened**, with no terminal state. Cumulative unresolved counts are token-efficiency **5**, durable-memory **8**, instructions-skills **1**, workers **1**. Extra carried rows are atlassian-labs/mcp-compressor, klavis-ai/klavis, anthropics/claude-code, langchain-ai/langmem and vbcherepanov/total-agent-memory. Read the prior September 26 returns and the September 29 manifest's lane adjudications as well as child returns: these carry rows with missing refuter returns. A serialized `refuted_*` label whose adverse vote says only `missing` is not substantive refutation and does not clear them.

September 26's cisco-ai-defense/skill-scanner and anthropics/financial-services received substantive fit refutations in September 29's retained returns; they are not in the current unresolved set. They are not silently carried into this policy as context managers. Workers' openai/codex row is adjacent, outside the four requested worker harnesses and outside this candidate selection.

## Step 3: bounded action and status preservation

### Convergence correction, 2026-10-15 20:48Z

Verified `ROW-cc-20261015T2048Z-correction-practice-by-convergence.md`, sha256 `c75fd83da2664e94ff3064ff9d938ac36b9bde85a733803c3f0ebe4b6d98455c`. The 20:45Z context-lead definition is withdrawn. CC practice specifics are proposals to screen, never selection evidence by themselves. Task requirements identify the need; convergence selects its implementation. The lead-note design, size budgets, handoff fields and restart heuristics in this PR are explicitly **CANDIDATES** for trial and are not requirements established by the CC. Upstream native behavior is sourced independently in mechanisms.md; experiment-only controls are fixed in comparison.md. No assignment-matrix, halt-aware/session-leverage, lane-charter or horizon-enforcement design is adopted here. The comparison does not by itself qualify the proposed lead format or budgets.

This PR adjudicates only those candidates' **fit to worker context policy**, records native mechanisms, names gaps and preregisters one existing-harness contrast. It makes no catalog, ledger, research-state, default, hook, profile or fence change. No framework installation or comparison runs. #1033 merged as `703d588c5660d698a87b622efe0e3bd8c22f7e29`; its head was `6eba3d7c28421736425f9636c56935d767335b0b`. Pi/OpenCode remain TRIAL. The Muse fence and named-toolchain amendment retain their documented hold and review limits. Never invoke `muse_lane.sh` for this task.

#1174 is **OPEN**, head `8b28bbda7dca372baa8026ca0bc6dce21b5b5626`. Decision 5 records native Claude workers and TRIAL Pi/OpenCode/Muse. Decision 6 proposes superpowers worker pin `bb92a77741419a4ab5f06e711a283343f1ada0c3` (v7.0.0), Claude marketplace pin `5bf4e78011075bcfc0dc295f0724994cd123ee71` (v6.4.1), per-harness paired framework qualification, ECC's changed-head delta, named skills and the memory survivors. These are consumed as a pending plan. The context comparison here fixes framework exposure equally in both arms and does not run or replace Decision 6's framework comparisons.

## Hash-bound repository inputs at the base

| Input | SHA256 |
| --- | --- |
| catalogs/landscape/foundation.json | `55751afc9a6e3d2dd814d5ba35d811ea9424464ccc417234b8cb6d08864e48b8` |
| catalogs/saturation/ledger.json | `b6ca3220516a515bd6dec13f122f48acdd8ef738565f9c0145839d99dd0c21f2` |
| catalogs/sota-convergence/manifest-20260929.json | `af4e0314b28acafe2b5e8a0bce71d1ced2efe911a3c3757557b23bd71c63c9ee` |
| evidence/artifacts/landscape-sweep-20260929/returns.json | `2f93067652c0f1e8e4f3d726895d2017eafef018412e47e9bc9b48e7ef931a9c` |
| evidence/artifacts/landscape-sweep-20260926/returns.json | `ea7e8ed285639a247df91d0c64d9378e080bc820170e9fc773434488397f4600` |
| catalogs/landscape/final-stack.json | `e482c30346bbe97fc06a8909a43e86d8d69a93983a443747f92ad7d3d8b9d46d` |
| catalogs/landscape/angles/foundation-workers.json | `9bf004fd463a910b6325ba28965cd8a59374e2b4c5dc3339a532d996fdcd9e0c` |
| evidence/artifacts/native-practice-paired-runs-20261010/paired-runs.json | `86108379949cf688ae244436f81becac28d94861716ceefbbe794753ba439fa7` |

The protocol and all sources are `source_review`. Hash/version checks establish identity only. No measured worker context advantage follows from these checks.
