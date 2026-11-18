# ADR-0001: Upstream-First Single-Owner Ecosystem Umbrella

- **Status:** Accepted
- **Date:** 2026-11-18
- **Evidence Grade:** E3

## Context and Problem Statement
Across multi-model agent sessions (`Antigravity`, `Claude Code`, `Codex`, `DSH`, `Orca`), overlapping utilities and stale snapshots cause split-brain drift unless each harness and trading layer maps to exactly one authoritative repository.

## Decision Outcome
`ECOSYSTEM_CONVERGENCE_LOCK.json` enforces a strict bijection (`layerSingleOwnerMap`) across `L0-L7` harness layers and `Stage1-Stage5` quantitative compounding stages, verified fail-closed by `native_agent_stack.umbrella`.
