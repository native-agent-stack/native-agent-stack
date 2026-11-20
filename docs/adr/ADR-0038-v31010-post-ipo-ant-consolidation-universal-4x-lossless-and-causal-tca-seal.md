# ADR-0038: `v3.10.10` Post-IPO `NASDAQ:ANT` Consolidation, Universal Zero-Gap 4x Live Lossless Foundation (`:8798` + `:8796`) & Unified Causal Markout TCA Seal

- **Status:** Accepted
- **Date:** 2026-11-19
- **Layer:** Organization Umbrella (`L1`), Post-IPO `NASDAQ:ANT` Day-2+ & 30-Day Seasoning Lifecycle, Universal Zero-Gap 4x Live Lossless Foundation (`:8798` + `:8796`), Perspective Paper Cockpit & Causal Markout TCA Queue-Parity Convergence (`T3` × `T4` × `T5` × `L7`)
- **Evidence Grade:** E4 (`sota-mover-ranker@630a4e6b` `ADR-0059`+`ADR-0060` `395/395` pytest `60/60` ADRs, `sota-dynamic-trail-c@e4cccdf6` `ADR-0028` `28/28` ADRs, `sota-compounding-lab@9bc50788` `ADR-0025` `25/25` ADRs, `sota-multi-model-workflows@e7c2ea1b` `ADR-0035` `35/35` ADRs, `H107` pre-wall reproduction PASS `512/512` dates, `103` HLZ trials `t*(104)=4.2063`, `242+` lessons, `38/38` umbrella ADRs, `gitleaks 0`)
- **GitHub Evidence:** https://github.com/native-agent-stack/native-agent-stack, https://github.com/native-agent-stack/sota-mover-ranker, https://github.com/native-agent-stack/sota-dynamic-trail-c, https://github.com/native-agent-stack/sota-compounding-lab, https://github.com/native-agent-stack/sota-multi-model-workflows
- **Revisit Trigger:** `2026-12-06` `23/5` Consolidated SIP cutover or `2026-12-20` `NASDAQ:ANT` 30-day new-issue seasoning graduation

## Context and Problem Statement

On **2026-11-19**, Anthropic, PBC (`NASDAQ:ANT`) completed its Day-1 Nasdaq IPO (`$83.00` offer, `$111.50` Nasdaq Opening Cross at `11:48 ET`, `$97.17` Day-1 RTH close). Simultaneously, four cross-repository milestones landed across the execution, simulation, and multi-model orchestration tiers:

1. **Post-IPO Day-2+ Transition & Universal Zero-Gap 4x Live Lossless Foundation (`sota-mover-ranker` `ADR-0060`):** Replaced permanent Day-1 IPO hardcodes with a date-aware ET IPO lifecycle (`PRE_IPO -> IPO_DAY1 -> POST_IPO_30D_SEASONING [2026-11-19..2026-12-19] -> SEASONED_LARGE_CAP [2026-12-20+]`; `SPCX` graduated seasoned large-cap since `2026-07-13`), unified `:8798` + `:8796` zero-gap failsafe with confirmed-fill co-mingled ownership debit, cross-process exit reservation + shared idempotent `client_order_id`, dimensionless 4x leverage stop scaling (`<= 2.00%` `ADR-0022`) + monotonic 3-tier MFE Chandelier (`65/75/82/86%`) 24/5, `15:50–16:00 ET` `> 2.0x` Overnight Reg-T Margin Guard + projected gross leverage cap, whole-market SOTA opportunity ranking with persistent `900s` stopout cooldowns, P2 re-weighting & collars, IBKR P4 `:4002` BOATS attribution, and complete Codex `#430/#431/#432/#435/#454/#466/#467/#470/#471` + Astra P0/P1 audit closure.
2. **Perspective Paper Cockpit & Causal Markout TCA Stack (`sota-mover-ranker` `ADR-0059`, `sota-dynamic-trail-c` `ADR-0028`, `sota-compounding-lab` `ADR-0025`):** Shipped unified fill + markout TCA streaming (`/api/tca`, `/api/unified-blotter-feed`), Perspective paper cockpit UI, and live-paper TCA vs. Nautilus/hftbacktest queue-parity reconciliation + Empirical-Bayes decay gating.
3. **Cross-Vendor Structural Wall Audit & Never-Raise Hardening (`sota-multi-model-workflows` `ADR-0035`):** Closed Opus 5.5 audit findings (strict loopback + paper-port allowlist, `:8796` live-port refusal, Rule-612 tick verification, extreme-Decimal/int never-raise bounds, explicit BOATS/DF5 flags, and Post-IPO `D5` lane charter update).
4. **Umbrella Lock Parity:** `ECOSYSTEM_CONVERGENCE_LOCK.json` and `README.md` still cited `v3.10.9`, `37` umbrella ADRs, `57` ranker ADRs, `102` HLZ trials, and pre-IPO lane descriptions.

## Decision Outcome

1. **Bump Canonical Umbrella Schema to `v3.10.10` (`ADR-0038`):** Add `v31010PostIpoConsolidationUniversal4xLosslessAndCausalTcaSeal` to `ECOSYSTEM_CONVERGENCE_LOCK.json`, pinning the exact post-IPO & causal-TCA SHAs (`sota-mover-ranker@630a4e6ba0bf13ccd6e9cb6833abc843dda78a40`, `sota-dynamic-trail-c@e4cccdf60596232f568822148278e439bd503574`, `sota-compounding-lab@9bc50788b582fab72dba37a02af1b503efbe65c3`, `sota-multi-model-workflows@e7c2ea1b3520908d7d384bd4fe3b4a93c00c6f0c`) while preserving all Two-Tier PUBLIC/PRIVATE/ARCHIVED boundaries (`9/9/4`), `singleActiveBrokerHostOnly = true`, `ADR-0022 <= 2.00%`, and `actions_enabled=false` on all `9` PRIVATE repos.
2. **Align Umbrella README & Regression Tests:** Update `README.md` to exact `v3.10.10` ADR counts (`38` umbrella, `60` ranker, `28` dynamic-trail-c, `25` compounding-lab, `35` multi-model-workflows, `43` harness-foundation, `34` agy-sota-harness, `42` cc-sota-harness), `103` HLZ trials (`t*(104) = 4.2063`), `242+` lessons, and assert `v3.10.10` invariants in `tests/test_umbrella_convergence.py`.

## Alternatives Considered

- **Leaving Umbrella at `v3.10.9` Until Dec-6 `23/5` SIP Cutover:** Rejected because `NASDAQ:ANT` already completed Day-1 IPO and four core execution/TCA/workflow repos advanced with major ADRs (`ADR-0025`, `ADR-0028`, `ADR-0035`, `ADR-0059`, `ADR-0060`) that must be locked before sealing `.github/ECOSYSTEM_ORG_MANIFEST.json`.

## Verification Witness

- `uv run python scripts/architecture_catalog.py --check` (`38/38` MADR 4.0 ADRs), `uv run python scripts/merge_gate.py` (`umbrella --check`, `ruff check`, `ruff format --check`, `ty check`, `pytest -q`), and `gitleaks protect --staged --no-banner` (`0` leaks).
