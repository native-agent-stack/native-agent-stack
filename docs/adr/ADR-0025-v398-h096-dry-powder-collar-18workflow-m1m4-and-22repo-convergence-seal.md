# ADR-0025: `v3.9.8` `Trial #96` (`H096` Dry-Powder Collar Joint-Necessity Law), `18`-Workflow `M1–M4` Multi-Model Memory Hub & 22-Repo Convergence Seal

- **Status:** Accepted
- **Date:** 2026-11-18
- **Layer:** Organization Umbrella, Pre-Wall Microstructure (`H096`), `18`-Workflow `M1–M4` Multi-Model Memory Sync & Pine/Wave-2 Execution Parity (`L0–L13` × `P0–P5` × `T0–T8`)
- **Evidence Grade:** E4 (`Trial #96` `H096` `spec_sha256=588d27755bad`, `Lesson fdf1adc7ebf05bdf`, `18/18` Active-Repo Disjoint ADR Wave, `merge_gate.py` & `gitleaks` `0` Leaks)
- **GitHub Evidence:** https://github.com/native-agent-stack/native-agent-stack, https://github.com/native-agent-stack/.github, https://github.com/native-agent-stack/sota-private-vault, https://github.com/native-agent-stack/sota-multi-model-workflows, https://github.com/native-agent-stack/sota-mover-ranker, https://github.com/native-agent-stack/sota-dynamic-trail-c, https://github.com/native-agent-stack/astrolabe, https://github.com/native-agent-stack/meridian
- **Revisit Trigger:** 2026-12-06 (`23/5` SIP cutover) or next `ALPHA_STRATEGY_MINOR` promotion (`t >= 4.1905`, `DSR >= 0.95`)

## Context and Problem Statement

Completing the full `18/18` active-repository `v3.9.8` SOTA convergence wave across `Mac M5 Max`, `Stationary Noesis` (`100.110.115.22`), and `* Noesis-Carbon` (`Ubuntu 26.04.1` `ext4`):
1. **`Trial #96` (`H096`, `spec_sha256 = 588d27755bad`, `Lesson fdf1adc7ebf05bdf`, `N = 96 -> t*(97) = 4.1905`):** Closed the 5-trial causal microstructure chain (`H090 -> H091 -> H094 -> H095 -> H096`), proving joint necessity (`+29.564` bps `1x` lift): bare `OFI > 0` (`n = 124`) failed (`-12.729` bps `1x`), whereas strict `OFI >= 0.25 & (ISO_F >= 0.15 | BJZZ >= 0.12)` + `15s` pure dry-powder bid-survival (`0` resting orders in `(0, 15s]`) + `<= 10.0` bps collar (`n = 52` / `47` dates) achieved **`+16.835` bps `1x` / `+11.366` bps `2x`** (`3/3` years positive, `11/15` disjoint CPCV `> 0`) under Two-Track `PROTECTIVE_FILTER_OR_GOVERNANCE`.
2. **`M1–M4` `18`-Workflow Multi-Model Memory Hub & Pine/Wave-2 Execution Parity:** Enacted Workflow `#18` (`multi_model_omc_memory_assign_workflow.py`), `sota_bus_assign_worker` (8th AGY MCP tool), `567`-doc `qmd` ADR/wiki index, `OMC_RUNTIME_V2=1` stop-callback ingestion, `sota-workstation v2.3.0 --sync-memory` 3-surface E2EE delta sync, and `:8787`/`:8799` Pine v6 Indicator<->Strategy + Wave-2 Auto Re-Entry E2E parity.

## Decision Outcome

1. **Advance `ECOSYSTEM_CONVERGENCE_LOCK.json` to `schemaVersion = "3.9.8"` (`25` Umbrella ADRs):**
   - Record `v398H096DryPowderCollarAnd18WorkflowM1M4Seal` (`hlzTrialsCompleted = 96`, `nextHlzTHurdle = 4.1905`, `canonicalWorkflowsTotal = 18`, `threeSurfaceSyncedCheckouts = 54`) aligned 1:1 with `DEFAULT_ECOSYSTEM_SEMVER = "3.9.8"`.

## Alternatives Considered

1. **Leave `ECOSYSTEM_CONVERGENCE_LOCK.json` at `v3.9.7` / `17` workflows:** Rejected — `DEFAULT_ECOSYSTEM_SEMVER = "3.9.8"` and `18` canonical workflows require exact lock parity across the umbrella and `.github` org manifest.

## Verification Witness

- `.venv/bin/python scripts/merge_gate.py` (`architecture_catalog --check`, `umbrella --check`, `ruff`, `ty`, `pytest`) -> `PASS`.
- `gitleaks` -> `0` leaks.
