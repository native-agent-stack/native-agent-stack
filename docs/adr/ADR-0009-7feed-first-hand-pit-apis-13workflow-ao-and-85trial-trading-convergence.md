# ADR-0009: Unified 7-Feed First-Hand PIT APIs, 13-Workflow AO Automation & 85-Trial Trading Convergence

- **Status:** Accepted
- **Date:** 2026-11-18
- **Evidence Grade:** E4

## Context and Problem Statement

Building on `ADR-0008` (`Canon 0169..0176` snapshot/queue/RVOL contracts, `sota-upstream-shelf-lock` `ADR-0004`, and dual-workstation `sota-workstation coop`), the live autonomous Paper execution daemons (`sota-mover-ranker` `:8787`, `sota-dynamic-trail-c` `:8799`, `astrolabe` `:4002`), the `13`-workflow multi-model orchestration suite (`sota-multi-model-workflows` `v3.3.0`, `agy-sota-harness` `ADR-0016`), and the `85`-trial HLZ hypothesis ledger (`sota-private-vault` `ADR-0008`) required unified umbrella convergence so live ranking, catalyst detection, and strategy landing operate strictly on first-hand point-in-time (`PIT`) evidence.

## Decision Outcome

1. **7-Feed `sota-research-feeds.v2` First-Hand Early-Reaction DataFeed APIs (`:8787` + `16`-Tool MCP Surface):**
   - Converge `sota-mover-ranker` (`@ 24b5886cb7`, `ADR-0007..0010`), `trading-sota` (`@ a75a5f72da`, `ADR-0011`), `sota-compounding-lab` (`@ d791f8adb4`, `ADR-0006`), and `astrolabe` (`@ 6016e0798b`, `ADR-0004`) onto the canonical 7-feed `sota-research-feeds.v2` schema (`GET /api/research_feeds`, `GET /api/first_hand_incentives`, and MCP tools `sota_get_research_feeds`, `sota_get_first_hand_incentives`, `sota_get_converged_strategy_templates`).
   - Enforce direct SEC EDGAR `getcurrent` Atom polling (`<= 0.067 req/s`, `acceptanceDateTime` PIT stamps), `15m` exponential catalyst freshness half-life decay (penalizing stale media rehashes), `424B*`/`S-3` dilution blocking below `USD 2B` float, `FINRA CNMSshvol` `T-1` lag discipline, `3.0s` `OVERNIGHT_BOATS` novel-mover promotion, `<50ms` `EXEC_WAKE_EVENT` auto-trader wakeup, `MAX_SPREAD_BPS = 35.0`, and Rule 612 `25..75 bps` `IBKR :4002` `StopLimitOrder` collars.
2. **13-Workflow `v3.3.0` Multi-Model `AO` & End-to-End Research-Convergence Landing (`sota-multi-model-workflows` `@ 8a29338c70` + `agy-sota-harness` `@ ceb78426be`):**
   - Standardize Turn-0 `_sota_kit.py` `v3.3.0` peer-bus + 7-feed PIT injection across all `13` canonical workflows, adding Workflow `#12` (`ao_multi_model_convergence_workflow.py`, `8`-slot `ComposioHQ/agent-orchestrator` cross-vendor lifecycle with frozen-assertion protection and telemetry-derived `meshState` failover) and Workflow `#13` (`research_convergence_landing_workflow.py`, 4-phase `ADR-0004` 64-hex `seed_input_sha256` + `18` 40-hex upstream pin + 7-feed PIT validator).
3. **85-Trial Empirical HLZ Ledger & `v0.8.0` Protective Execution Proofs (`t*(86) = 4.1631`):**
   - Record pre-registered `Trial #84` (`sota-dynamic-trail-c` `v0.8.0` `@ 5567ab57ab`, `ADR-0006`: `+19.73 bps/trade` OOS lift, `-84.4%` `CVaR_95` reduction vs static `200 bps` stops, and `PostWallCohortLedger` accruing toward `N >= 250` fills) and `Trial #85` (`H085` `sota-upstream-shelf-lock` `v2.0.0` `@ 075e66b542`: `14,750` nanosecond SIP files `<= 2026-10-15`, `86.41%` passive `10:30` bid queue fills `1,393 / 1,612` across `577` dates, flipping net `1x` to `+7.908 bps` and `2x` to `+2.374 bps` for a `+13.55 bps` passive-vs-taker swing while honestly logging `FAILED` at `t = 0.8151 < 4.1604`).

## Alternatives Considered

1. **Rely on secondary news headlines without `acceptanceDateTime` half-life decay:** Rejected — introduces multi-minute to multi-hour rehash lag and misses first-hand `8-K` Item `1.01`/`2.02`/`7.01`/`8.01` ignition windows.
2. **Promote strategies without `verify_research_convergence_claim` Turn-0 validation:** Rejected — allows drift between `18` pinned `~/Documents/upstream/` SHAs, `<= 2026-10-15` pre-wall boundaries, and `ADR-0022 <= 2.00%` stop geometry.

## Verification Witness

- `research_convergence_landing_workflow.py` (`H08_FIRST_HAND_CATALYST_IGNITION`, `seed_input_sha256=aa47f11693c0177840681809404737166ab5adaacf2c20e8f9aeeb3bcd620fd9`): `convergence_claim_valid=True`, `feed_count=7`, `upstream_pin_count=18`, `sota_doctor=11/11 PASS`.
- `scripts/merge_gate.py` (`architecture_catalog.py --check`, `native_agent_stack.umbrella --check`, `ruff`, `ty`, `pytest`): `9/9 MADR 4.0 ADRs, 0 drift, PASS`.
