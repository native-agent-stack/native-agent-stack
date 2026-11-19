# ADR-0032: `v3.10.5` Full-Ecosystem 7-Domain Orca Lane Hubs, Stationary `Noesis` Primary `24/5` Host & Dedicated `:8796` Live Guardian Seal

- **Status:** Accepted
- **Date:** 2026-11-18
- **Layer:** Organization Umbrella, Dual-Machine Stationary Workstation Sovereignty, 7-Domain Orca Orchestration & Stage-5 Lossless Live Isolation (`L0–L13` × `P0–P5` × `T0–T8`)
- **Evidence Grade:** E4 (`sota-harness-foundation@0629fd82` `ADR-0041`, `sota-multi-model-workflows@938decb2` `ADR-0029` + `CANONICAL_ORCA_LANE_LEADS`, `sota-dynamic-trail-c@2e3d96b5` `ADR-0026`, `sota-mover-ranker@2010a9e1` `ADR-0034`, `18` Live Orca Folder Hubs (`9` Noesis + `9` Mac), `14` Live Dual-Machine Orca Automations (`7` + `7`), `0` Leaks)
- **GitHub Evidence:** https://github.com/native-agent-stack/native-agent-stack, https://github.com/native-agent-stack/sota-harness-foundation, https://github.com/native-agent-stack/sota-multi-model-workflows, https://github.com/native-agent-stack/agy-sota-harness, https://github.com/native-agent-stack/sota-compounding-lab, https://github.com/native-agent-stack/.github, https://github.com/stablyai/orca
- **Revisit Trigger:** `2026-12-06` `23/5` Consolidated SIP cutover or `v4.0.0` promotion

## Context and Problem Statement

Completes the full-ecosystem dual-machine convergence (`v3.10.4` -> `v3.10.5`) across Stationary Workstation `Noesis` (`100.110.115.22`, Win32 64c/128GB/RTX4090 + `Noesis-Carbon` WSL2) and Portable `Mac M5 Max` (`100.93.211.101`):
1. **Stationary Workstation Sovereign Host (`sota-harness-foundation` `ADR-0041`, `sota-dynamic-trail-c` `ADR-0026`, `sota-mover-ranker` `ADR-0033`):** Promotes `stationary_noesis_win32` to the canonical always-on `24/5` primary host for the Main Framework Foundation (`H1`–`H3`) and Trading Engine (`P1:8799`, `P2:8787`, `P3:8797`, `P4:4002`, `L5:8798`, `:8796` Live EXT Guardian, `S1`/`S2` Sim, 4K TradingView), while `portable_mac_m5_max` serves as the portable interactive command cockpit and explicit hot failover (`singleActiveBrokerHostOnly = true` enforced symmetrically).
2. **All 7 Full-Ecosystem Domain Orca Lane Hubs + Named Lane Leads (`sota-multi-model-workflows` `ADR-0029` + `938decb2`):** Manifests all 7 ecosystem domains directly into Orca on BOTH machines (`18` live folder hubs total: `2` macro + `7` domain per host) covering `01-sim-backtest`, `02-paper-4acct-farm`, `03-stage5-lossless-live` (strictly read-only `T5` Lane Lead with zero broker credentials/order write path), `04-research-all-market`, `05-non-market-incentives`, `06-framework-and-harness`, and `07-beyond-convergence-skillopt`, backed by `14` active scheduled Orca Automations (`7` Mac + `7` Noesis).
3. **Dedicated `:8796` Extended-Hours Live Guardian Isolation (`sota-mover-ranker` `ADR-0034`):** Closes the extended-hours live protection gap by requiring a dedicated `:8796` Live Guardian reporting `account_mode == "LIVE"` before allowing non-RTH Stage-5 Live entries (never mistaking Paper `:8799` for a Live guardian), while preserving RTH native server-side atomic OCO `bracket`/`oto` (`<= 2.00%` `ADR-0022`).

## Decision Outcome

- Bump `ECOSYSTEM_CONVERGENCE_LOCK.json` `schemaVersion` to `"3.10.5"`, record `primarySovereignHost: "stationary_noesis_win32"` in `dualWorkstationMesh`, and seal `v3105FullEcosystemSevenDomainOrcaLanesAndStationaryNoesisSeal` with all 7 Noesis + 7 Mac Orca folder UUIDs, `14` dual-machine Orca automations, dedicated `:8796` Live EXT Guardian invariant, and exact 40-char SHAs across all updated repositories.

## Alternatives Considered

- **Consolidating all domains into only two macro Orca hubs (`trading-lanes`, `harness-lanes`) without per-domain folder hubs or dedicated `:8796` Live Guardian separation:** Rejected because cross-domain context conflates never-gated Sim/Paper/Research/Non-Market-Incentive loops with proven-only Stage-5 Live isolation, and Paper `:8799` cannot guard a Live account during extended hours.

## Verification Witness

- `uv run python scripts/architecture_catalog.py --check` (`32/32` MADR 4.0 ADRs, 40-char SHA CI & zero-leak privacy PASS).
- `uv run pytest -q && ~/.local/bin/ruff check . && gitleaks git --no-banner` (`PASS`, `0` leaks).
