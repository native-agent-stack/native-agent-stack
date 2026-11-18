# ADR-0019: `v3.9.3` Starred Visual/Diagram Craft Atlas (`ADR-0024`), `0.15x` Probation EB Throttle (`ADR-0012`), Dec-6 `23/5` Shadow Probe (`ADR-0016`) & Dual-TV Coexistence

- **Status:** Accepted
- **Date:** 2026-11-18
- **Layer:** Organization Umbrella, Visual/Diagram Architecture Craft (`L6`/`L8`/`L9`), Compounding Sizing & `23/5` Cutover Readiness (`L0–L13` × `P0–P5` × `T1–T8`)
- **Evidence Grade:** E4 (`sota-compounding-lab @ 57ff858b1e09` `56/56` `pytest`, `sota-dynamic-trail-c @ ec276a3493fa` `51/51` `pytest`, `agy-sota-harness @ 994e14441a05` `ADR-0024`, `sota-private-vault @ bcb1292682e8` `ADR-0015`)
- **GitHub Evidence:** https://github.com/native-agent-stack/native-agent-stack, https://github.com/native-agent-stack/.github, https://github.com/native-agent-stack/sota-compounding-lab, https://github.com/native-agent-stack/sota-dynamic-trail-c, https://github.com/native-agent-stack/agy-sota-harness, https://github.com/tt-a1i/archify, https://github.com/cathrynlavery/diagram-design, https://github.com/Graphify-Labs/graphify
- **Revisit Trigger:** 2026-12-06

## Context and Problem Statement

Following `ADR-0018` (`v3.9.2`), four coordinated finalization moves completed across all `3` workstation surfaces (`Mac M5 Max`, `Noesis Win32`, `* Noesis-Carbon` `ext4`):
1. **Starred Design, Diagramming, Knowledge-Graph & Illustration Craft Atlas (`agy-sota-harness @ 994e14441a05`, `ADR-0024`):** Manifests `24` curated repositories from the owner's `404` GitHub stars (`archify`, `diagram-design`, `likec4`, `graphify`, `Understand-Anything`, `ui-ux-pro-max-skill`, `taste-skill`, `impeccable`, `hallmark`, `openpencil`, `plannotator`, `perspective`, `lightweight-charts`) into canonical cross-peer skills (`17/17` mounted across AGY, Claude, and Codex).
2. **`PROBATION_NEGATIVE_EB_THROTTLE` (`sota-compounding-lab @ 57ff858b1e09`, `ADR-0012`, `56/56` `pytest` PASS):** Applies a `0.15x` Empirical-Bayes sizing throttle to persistent negative-expectancy probation strategies.
3. **Dec-6 `23/5` SIP Shadow Readiness & Live Dual Native TradingView Coexistence (`sota-dynamic-trail-c @ ec276a3493fa`, `ADR-0016`, `51/51` `pytest` PASS):** Adds `20:00–21:00 ET` pause probing ahead of `2026-12-06` and verifies simultaneous live tick streaming on both `Mac M5 Max` `TradingView.app` and `Noesis` 4K `TradingView.exe` with `0` disconnects.
4. **Orca `cc-lead` Dual-Mesh Activation:** Aligns `cc-lead`, `agy-lead`, `dsh-lead`, and `umbrella-lead` worktrees across `Mac` (`:6768`) and `Noesis` (`:6770`) with live `claude-fable-5-2` `xhigh` sessions.

## Decision Outcome

1. **Advance `ECOSYSTEM_CONVERGENCE_LOCK.json` to `schemaVersion = "3.9.3"` (`19` Umbrella ADRs):**
   - Record `v393StarredVisualCraftDualTvAndCompoundingSeal` binding all four finalization SHAs, `24` starred visual/diagram craft repositories, and `54/54` 3-surface checkout parity.

## Alternatives Considered

1. **Leave `ECOSYSTEM_CONVERGENCE_LOCK.json` at `v3.9.2` with unmanifested visual/diagram skills and drifted `sota-compounding-lab` / `sota-dynamic-trail-c` SHAs:** Rejected — umbrella lock must maintain zero drift across all `22` repositories.

## Verification Witness

- `uv run --frozen python scripts/merge_gate.py` (`architecture_catalog --check`, `umbrella --check`, `ruff`, `ty`, `pytest`) -> `PASS`.
- `gitleaks` -> `0` leaks.
