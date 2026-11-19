# ADR-0033: `v3.10.6` Pre-IPO `2026-11-19` Convergence — `P0-1..6` Unified Protective Shield, `10` Canonical Multi-Model Orca Lane Leads & Autonomous Overnight Goal Seal

- **Status:** Accepted
- **Date:** 2026-11-18
- **Layer:** Organization Umbrella, Pre-IPO Execution Firewall (`ADR-0035`), `10`-Lead Multi-Model Orca Runtime Fleet & Autonomous Overnight Goal (`L0–L13` × `P0–P5` × `T0–T8`)
- **Evidence Grade:** E4 (`sota-mover-ranker@4de58ade` `ADR-0035` `137/137 pytest` `35/35 ADRs`, `sota-multi-model-workflows` `ADR-0030` `10/10` Canonical Leads / `28/28 pytest` `30/30 ADRs`, `8` Live Nested Worktrees across `7/7` Domain Hubs on Stationary `Noesis`, Live Multi-Model Orca Run `run_5c51382bc888` with `4` Active Workers, `7` Standing Pre-Market Crons + `14` Orca Automations, `0` Leaks)
- **GitHub Evidence:** https://github.com/native-agent-stack/native-agent-stack, https://github.com/native-agent-stack/sota-multi-model-workflows, https://github.com/native-agent-stack/sota-harness-foundation, https://github.com/native-agent-stack/.github, https://github.com/stablyai/orca
- **Revisit Trigger:** `2026-11-20` Post-`NASDAQ:ANT` IPO debrief or `2026-12-06` `23/5` Consolidated SIP cutover

## Context and Problem Statement

Finalizes the entire dual-machine ecosystem ahead of the `2026-11-19` `NASDAQ:ANT` (`$83.00` IPO) debut and continuous `24/5` compounding:
1. **`P0-1..6` Live-Safety & Unified Shield Closure (`sota-mover-ranker@4de58ade`, `ADR-0035`):** Closes `T5`'s `#352` direct-call fail-closed finding (`validate_stage5_atomic_order(..., dedicated_live_guardian_healthy: bool = False)`), wires unified `evaluate_protective_entry_shield` (`ADR-0017`/`ADR-0019` opening-5m blackout, uncapped cooldown streak + elapsed seconds, probation throttle, directional long/short SAR OFI alignment) across `:8798` (`Stage5LosslessLiveLane`), `:8797` (`PaperP3AggressiveLabEngine`), and `VixAndMajorGrowthRegimeEngine`, ships `scripts/install-noesis-24x5-supervisor.ps1` (`2`-minute Scheduled Task keepalive respecting `SINGLE_BROKER_HOST_FIREWALL`), and hot-reloads `:8797` + `:8798` live.
2. **Complete `10`-Lead Multi-Model Orca Ecosystem Fleet (`sota-multi-model-workflows` `ADR-0030`):** Extends `CANONICAL_ORCA_LANE_LEADS` to `10` named leads (`T1`, `T2`, `T3`, read-only `T5`, `H1`, `H2`, `H3`, `D4`, read-only `D5`, `D7`), lands `3` additional nested worktrees (`d4-all-market-research-lead`, `d5-non-market-incentives-lead`, `d7-beyond-skillopt-lead`) on Stationary `Noesis` (`8` nested leads covering all `7/7` Domain Hubs), and launches live multi-model Orca Run `run_5c51382bc888` (`Codex gpt-6.2-sol`, `Claude claude-fable-5-2`, `Claude claude-sonnet-5-5`, `Codex gpt-6.2-astra`).
3. **Autonomous Pre-IPO Overnight Goal (`G_SOTA_IPO_20261119_FULL_ECOSYSTEM_CONVERGENCE`):** Persisted in `~/.agents/state/` & `~/.agents/wiki/` with `7` standing pre-market/open daemon crons (`08:00`..`09:35 ET`) plus `14` dual-machine Orca Automations (`7` Mac + `7` Noesis).

## Decision Outcome

- Bump `ECOSYSTEM_CONVERGENCE_LOCK.json` `schemaVersion` to `"3.10.6"` and record `v3106PreIpoP0ShieldClosureAndTenLeadMultiModelOrcaSeal`.

## Alternatives Considered

- **Entering tomorrow's `NASDAQ:ANT` IPO with `P0-1..6` open on `:8797`/`:8798`/`VIX` or Domains `04`/`05`/`07` unstaffed:** Rejected — Stage-5 Lossless Live requires fail-closed direct-call validation and uniform `ADR-0017`/`ADR-0019` shielding across every execution and signal path.

## Verification Witness

- `uv run python scripts/architecture_catalog.py --check` (`33/33` MADR 4.0 ADRs valid, `0` drift).
- `uv run python scripts/merge_gate.py && uv run pytest -q && ~/.local/bin/ruff check . && gitleaks git --no-banner` (`PASS`, `0` leaks).
