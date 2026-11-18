# ADR-0018: `v3.9.2` Dual-Desktop Zero-WS Coexistence (`ADR-0018` & `ADR-0015`), Workflow `ADR-0017`/`ADR-0023` & 54-Checkout 3-Surface Seal

- **Status:** Accepted
- **Date:** 2026-11-18
- **Layer:** Organization Umbrella, Dual-Desktop TradingView Coexistence & 3-Surface Zero-Drift Governance (`L0–L13` × `P0–P5` × `T1–T8`)
- **Evidence Grade:** E4 (`sota-mover-ranker @ 31907e95999d` `89/89` `pytest` + `ty` `0`, `sota-dynamic-trail-c @ 7fb92138931e` `ADR-0015`, `sota-multi-model-workflows @ a6c71a4a4d0f`, `agy-sota-harness @ 6c4073d9f36a`, `93` Trials & `69` Lessons)
- **GitHub Evidence:** https://github.com/native-agent-stack/native-agent-stack, https://github.com/native-agent-stack/.github, https://github.com/native-agent-stack/sota-mover-ranker, https://github.com/native-agent-stack/sota-dynamic-trail-c, https://github.com/native-agent-stack/sota-multi-model-workflows, https://github.com/native-agent-stack/agy-sota-harness
- **Revisit Trigger:** 2027-01-02

## Context and Problem Statement

Following `ADR-0017` (`v3.9.1`), final cross-machine reconciliation across `Mac M5 Max`, `Noesis Win32`, and `* Noesis-Carbon` `ext4` landed four coordinated closures:
1. **`sota-mover-ranker @ 31907e95999d` (`ADR-0018`, `18` ADRs, `89/89` `pytest` PASS, `ty@0.0.104` `0` errors):** Replica Cloud MCP/watchlist single-writer guard, Win32 computer-use & `24/5` `BOATS` chart routing, `--read-only-radar`, and `list-windows` static type narrowing on top of `ADR-0017` RTH protective-shield E2E wiring.
2. **`sota-dynamic-trail-c @ 7fb92138931e` (`ADR-0015`, `15` ADRs):** Reserves `2/2` Alpaca WebSocket slots for Dual TradingView Desktops and enforces `msvcrt` Win32 + `fcntl.flock` POSIX singleton daemon locks.
3. **`sota-multi-model-workflows @ a6c71a4a4d0f` (`ADR-0017`) & `agy-sota-harness @ 6c4073d9f36a` (`ADR-0023`):** Unified `v3.9.x` `16`-workflow registry, `14`-layer `sota-doctor`, and `54/54` (`18 × 3`) 3-surface checkout parity.

## Decision Outcome

1. **Advance `ECOSYSTEM_CONVERGENCE_LOCK.json` to `schemaVersion = "3.9.2"` (`18` Umbrella ADRs):**
   - Record `v392DualDesktopCoexistenceAnd22RepoZeroDriftSeal` binding `sotaMoverRankerAdr0018Sha`, `sotaDynamicTrailCAdr0015Sha`, `sotaMultiModelWorkflowsAdr0017Sha`, `agySotaHarnessAdr0023Sha`, `hlzTrialsCompleted = 93` (`t*(94) = 4.1834`), `lessonsCount = 69`, and `threeSurfaceSyncedCheckouts = 54`.

## Alternatives Considered

1. **Leave `ECOSYSTEM_CONVERGENCE_LOCK.json` at `v3.9.1` prior to `ADR-0018` / `ADR-0015` / `ADR-0017` / `ADR-0023` convergence:** Rejected — umbrella lock must reflect the complete 3-surface converged state.

## Verification Witness

- `python scripts/merge_gate.py` -> `PASS` (`18/18` ADRs, `umbrella --check`, `ruff`, `ty`, `pytest`).
- `gitleaks` -> `0` leaks.
