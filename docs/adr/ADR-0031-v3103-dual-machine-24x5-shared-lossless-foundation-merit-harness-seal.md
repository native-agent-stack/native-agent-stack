# ADR-0031: `v3.10.3` Dual-Machine Active `24/5` Shared Lossless Foundation, 7-Lane Merit-Promotion Harness & SOTA GitHub Maintenance Seal

- **Status:** Accepted
- **Date:** 2026-11-18
- **Layer:** Organization Umbrella, Shared Active `24/5` Foundation, Multi-Paper Merit Promotion & Dual-Machine Orca Governance (`L0–L13` × `P0–P5` × `T0–T8`)
- **Evidence Grade:** E4 (`sota-harness-foundation` `ADR-0040 @ 43b51358`, `sota-multi-model-workflows` `ADR-0027 / WF20 @ 163d86e7`, `sota-mover-ranker` `ADR-0030`+`ADR-0031 @ a628552b`, `11` Dual-Machine Orca Automations, `14/14 sota-doctor PASS`, `0` Leaks)
- **GitHub Evidence:** https://github.com/native-agent-stack/native-agent-stack, https://github.com/native-agent-stack/sota-harness-foundation, https://github.com/native-agent-stack/sota-multi-model-workflows, https://github.com/native-agent-stack/.github, https://github.com/alpacahq/alpaca-mcp-server, https://github.com/stablyai/orca
- **Revisit Trigger:** `2026-12-06` `23/5` Consolidated SIP cutover or `v4.0.0` promotion

## Context and Problem Statement

Seals the `v3.10.3` dual-machine Master Lead Goal (`G_SOTA_DUAL_MACHINE_MERIT_TO_LOSSLESS_LIVE_24X5`) across `Mac M5 Max`, `Noesis Win32` (`64c/128GB/RTX4090`), and `Noesis-Carbon WSL2`:
1. **Upstream-First Shared Active `24/5` Lossless Foundation:** Paper accounts and Stage-5 Live run on the exact same `24/5` Lossless Foundation (`sota-harness-foundation` `ADR-0040`, built strictly upon our `18` pinned SOTA libraries — zero custom reinvention).
2. **Never-Gated Merit Sources -> Proven-Only Automated Live:** `2` Sim/Backtest lanes (`S1`, `S2`) and `4` Paper accounts (`3` distinct active `4x` Alpaca Paper `:8799/:8787/:8797` + `1` IBKR Paper `:4002`) remain strictly `NEVER_GATED`; Stage-5 Live (`:8798`) runs automated proven strategies starting with the Shared Lossless Foundation.
3. **Always-On `24/5` Maintenance & Org GitHub Automation:** `11` Dual-Machine Orca Automations (`7` Mac + `4` Noesis), `4`-port `sota-deadman-check`, and SHA-pinned reusable org GitHub Actions maintenance workflows.

## Decision Outcome

- Bump `ECOSYSTEM_CONVERGENCE_LOCK.json` `schemaVersion` to `"3.10.3"` and record `v3103Shared24x5LosslessFoundationAndMeritHarnessSeal` locking `sota-harness-foundation@43b51358af05`, `sota-multi-model-workflows@163d86e7d801`, `sota-mover-ranker@a628552bed37`, `20` canonical workflows, `7` execution merit lanes (`2` Sim + `3` Alpaca Paper + `1` IBKR Paper + `1` Stage-5 Lossless Live), and `11` dual-machine Orca automations.

## Alternatives Considered

- **Leaving umbrella lock at `v3.10.2` without recording the shared `24/5` foundation and `WF20` merit ladder:** Rejected because umbrella SHA drift breaks cross-surface `sota-org-doctor` verification.

## Verification Witness

- `uv run python scripts/architecture_catalog.py --check` (`31` MADR 4.0 ADRs valid, `0` drift).
- `uv run pytest -q && ~/.local/bin/ruff check . && gitleaks git --no-banner` (`PASS`, `0` leaks).
