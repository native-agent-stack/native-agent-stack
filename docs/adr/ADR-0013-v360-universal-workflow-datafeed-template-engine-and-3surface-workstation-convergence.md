# ADR-0013: `v3.6.0` Universal `14/14` + `5/5` Workflow Research-Convergence, 6 DataFeed APIs, 4 Strategy Templates, 8 Engine Sources & 3-Surface Workstation Parity

- **Status:** Accepted
- **Date:** 2026-11-18
- **Evidence Grade:** E4

## Context and Problem Statement

Following `ADR-0012` (`v3.5.1` cross-tier runner convexity and `15/15` `cc-lead` hub convergence), the organization needed every workflow script (`14/14` canonical workflows in `sota-multi-model-workflows` + `5/5` native `Antigravity` workflows in `agy-sota-harness`, plus the org reusable GitHub Actions gate) to enforce deterministic Turn-0 verification of all **Trading Lane DataFeed APIs**, **4 canonical SOTA Strategy Templates + closed-bar Pine v6**, **8 Trading Engine Source repositories**, and **3-surface Dual-Workstation path parity** (`Apple M5 Max` `~/Documents/*`, `Noesis Win32` `C:/sota-workstation/*`, and `Noesis-Carbon WSL2` `~/sota-workstation/*`).

## Decision Outcome

1. **Universal Turn-0 `verify_workflow_research_convergence` Across All `14/14` + `5/5` Workflows (`v3.6.0`):**
   - Lock `sota-multi-model-workflows @ 9f7c9aa6d3` (`ADR-0013`, `13` ADRs) and `agy-sota-harness @ 53d5808bd4` (`ADR-0019`, `19` ADRs) so every workflow computes a deterministic `64`-hex `golang/mod` `dirhash`-style `envelope_input_sha256` (`sota-workflow-research-convergence.v3.6`) and runs `verify_research_convergence_claim` (`18` `40`-hex upstream pins, `study_max_date <= 2026-10-15`, `0 < hard_stop_pct <= 2.00%`, `PHILOSOPHY_ONLY` sibling-repo authority).
2. **6 Trading Lane DataFeed APIs, 4 Strategy Templates & 8 Trading Engine Sources:**
   - Bind `CANONICAL_TRADING_LANE_DATAFEED_APIS` (`:8787/api/{research_feeds,first_hand_incentives,strategy_templates,research_convergence}`, `:8799/api/{status,tv-webhook}`, and `127.0.0.1:4002` `astrolabe` IBKR Paper `L1` with `300/min` exit reserve; live ports `4001`/`7496` hard-refused).
   - Bind `CANONICAL_STRATEGY_TEMPLATES_MATRIX` (`PRE_TRAVEL_EARLY_IGNITION`, `FIRST_HAND_SEC_EPISODIC_PIVOT`, `MEGA_CAP_NEAR_LOSSLESS_ORB`, `CLIMAX_VWAP_MEAN_REVERSION` + non-repainting closed-bar `sota_pine_v6_nonrepainting.template.pine` + `tsl`/`trading-sota` `strategies/_template/manifest.json`) under `ADVERSE_STOP_FIRST` and `100x` CTA/UTP round-lot `hftbacktest::RiskAdverseQueueModel` parity.
   - Bind `CANONICAL_TRADING_ENGINE_SOURCES` across all `8` trading engine & research repositories (`meridian`, `canon`, `tsl`, `trading-sota @ e838c5bb82` `ADR-0012`, `sota-mover-ranker`, `astrolabe`, `sota-compounding-lab`, `sota-dynamic-trail-c`).
3. **3-Surface Dual-Workstation Synchronization (`sota-workstation v2.1.0` + `cc-sota-harness` `ADR-0025` + `sota-harness-foundation` `ADR-0027`):**
   - Standardize `resolve_ecosystem_repo_dir` / `resolve_workstation_repo_dir` and `sota-workstation v2.1.0` (`sync --repo all`) to synchronize repositories and all `15` workflow files lease-safely across Mac M5 Max, `Noesis` Windows (`C:/sota-workstation/*`), and `Noesis-Carbon` WSL2 (`~/sota-workstation/*`).

## Alternatives Considered

1. **Enforce DataFeed/Template/Engine validation only in `research_convergence_landing_workflow.py`:** Rejected — leaves the other `13` orchestration pipelines without Turn-0 SHA/template/engine verification.
2. **Sync only Windows `C:/sota-workstation/*` on `Noesis` without fast-forwarding `Noesis-Carbon` WSL2:** Rejected — causes version skew when running `Antigravity` (`1.5.10`) or Linux Python suites inside `Noesis-Carbon`.

## Verification Witness

- `sota-multi-model-workflows @ 9f7c9aa6d3` (`14/14` unittest PASS), `agy-sota-harness @ 53d5808bd4` (`13/13` probes, `21/21` pytest PASS), `cc-sota-harness @ 9e566deb38` (`25` ADRs PASS), `sota-harness-foundation @ 6c053bb205` (`27` ADRs PASS), `trading-sota @ e838c5bb82` (`12` ADRs PASS).
- `scripts/merge_gate.py`: `13/13 MADR 4.0 ADRs, 0 drift, umbrella v3.6.0 PASS`.
