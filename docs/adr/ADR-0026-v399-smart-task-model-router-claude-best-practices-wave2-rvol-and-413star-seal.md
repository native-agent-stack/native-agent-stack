# ADR-0026: `v3.9.9` Smart Task-to-Model Suitability Router, Claude Code Best Practices, Wave-2/`RVOL_tod` Parity & `413`-Star 22-Repo Seal

- **Status:** Accepted
- **Date:** 2026-11-18
- **Layer:** Organization Umbrella, Smart Multi-Model Routing, Quant Execution & 3-Surface Parity (`L0–L13` × `P0–P5` × `T0–T8`)
- **Evidence Grade:** E4 (`26` ADRs, `8`-Class Smart Router `ADR-0022`/`ADR-0034`, `8/8` Runtimes × `49` MCP Tools, `413` Audited Stars & `54/54` Synced Checkouts)
- **GitHub Evidence:** https://github.com/native-agent-stack/native-agent-stack, https://github.com/native-agent-stack/.github, https://github.com/native-agent-stack/sota-multi-model-workflows, https://github.com/native-agent-stack/cc-sota-harness, https://github.com/native-agent-stack/sota-mover-ranker, https://github.com/parallel-web/parallel-search-evals
- **Revisit Trigger:** Ecosystem `v4.0.0` promotion or `2026-12-06` `23/5` Consolidated SIP cutover

## Context and Problem Statement

Across `v3.9.9`, all `18` active repositories converged on: (1) compiled `OMC 5.8.6 dist/` stop-callbacks, `2,325`-vector `qmd` hybrid search, and `CreateProcessW`-safe `24h` chunked memory sync; (2) deterministic `8`-class Smart Task-to-Model Suitability Routing (`sota-cc-hub smart-route` / `--worker auto`) + Claude Code `v2.1.327` Best-Practice Charter v2 (`ADR-0022` / `ADR-0034`); (3) own-history abnormal `RVOL_tod` size-bias purge, `900s` Wave-2 cooldown, and IBKR `:4002` DU atomic pattern-break SAR (`ADR-0064` / `ADR-0015` / `sota-mover-ranker @ 25b18cf12eef`); and (4) full `413`-star (`33`-anchor) owner research & evaluation convergence (`parallel-web/parallel-search-evals`, `NVIDIA/SkillEvaluator`, `elementalsouls/Claude-BugHunter`).

## Decision Outcome

1. **Advance `ECOSYSTEM_CONVERGENCE_LOCK.json` to `schemaVersion = "3.9.9"` (`26` Umbrella ADRs):**
   - Record `v399SmartTaskModelRouter413StarAnd22RepoSeal` locking `smartTaskSuitabilityProfiles = 8`, `runtimesIndependentlyHarnessed = 8`, `verifiedMcpToolsPerSurface = 49`, `ownerTotalStarsAudited = 413`, `curatedStarAnchors = 33`, and exact sibling `origin/main` SHAs.

## Alternatives Considered

- **Leave Umbrella lock at `v3.9.8`:** Rejected — `22/22` zero-drift SHA parity across all `3` surfaces is mandatory.

## Verification Witness

- `uv run --frozen --all-groups --all-extras python scripts/merge_gate.py` -> `PASS`.
- `gitleaks` -> `0` leaks.
