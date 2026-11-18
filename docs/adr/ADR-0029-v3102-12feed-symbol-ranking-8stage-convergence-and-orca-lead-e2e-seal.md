# ADR-0029: `v3.10.2` `12`-Feed (`DF1..DF12`) Symbol Ranking Foundation, `8`-Stage SOTA Research Convergence (`413+6`), Zero-Kimi 8-Runtime Parity & Orca-Lead E2E Seal

- **Status:** Accepted
- **Date:** 2026-11-18
- **Layer:** Organization Umbrella, `12`-Feed Symbol Ranking DataFeeds (`DF1..DF12`), `8`-Stage SOTA Convergence & Multi-Runtime Orca Lead (`cc-lead`) E2E (`L0–L13` × `P0–P5` × `T0–T8`)
- **Evidence Grade:** E4 (`sota-multi-model-workflows` `ADR-0024` @ `de121fb6`, `sota-compounding-lab` `ADR-0016` @ `def30e1c`, `astrolabe` `ADR-0014` @ `d4f3fe9d`, `meridian` `0065` @ `389a8d8b`, `cc-sota-harness` `ADR-0037` @ `50e9967c`, `agy-sota-harness` `ADR-0031` @ `617f37ce`, `sota-private-vault` `ADR-0024` @ `3071f44a`, `0` Leaks)
- **GitHub Evidence:** https://github.com/native-agent-stack/native-agent-stack, https://github.com/native-agent-stack/sota-multi-model-workflows, https://github.com/native-agent-stack/cc-sota-harness, https://github.com/native-agent-stack/agy-sota-harness, https://github.com/native-agent-stack/sota-private-vault, https://github.com/microsoft/RD-Agent
- **Revisit Trigger:** 2026-12-06 (`23/5` SIP cutover) or next frontier model release

## Context and Problem Statement

While `ADR-0028` (`v3.10.0`) established the three frontier model powerhouses and Claude `~1:1` `claude-fable-5-2` mix, end-to-end research convergence required:
1. Finalizing the canonical `12`-Feed Bitemporal Symbol Ranking DataFeed contract (`DF1..DF12`, `sota-symbol-ranking-datafeeds.v3.10`) powering all `6` autonomous paper-trading routes across `sota-multi-model-workflows`, `sota-compounding-lab`, `astrolabe`, `meridian`, `tsl`, `trading-sota`, and `canon`.
2. Upgrading Research Convergence to an `8`-stage SOTA pipeline across `413` owner starred repositories plus `6` beyond-starred frontier anchors (`microsoft/RD-Agent`, `databento/databento-python`, `unit8co/darts`, `Nixtla/statsforecast`, `stanfordnlp/dspy`, `ADIA-Lab MinTRL`), retiring `kimi-*`/`Moonshot AI` + stale model aliases (`deepseek-v4-pro`) in favor of active frontier routing (`deepseek-flash`), and promoting `Workflow #19` (`orca-lead-e2e-research-convergence`) + `sota-cc-hub assign-orca-lead`.

## Decision Outcome

1. **Seal `ECOSYSTEM_CONVERGENCE_LOCK.json` with `v3102AdvancedResearchConvergence12FeedAndOrcaLeadE2ESeal` (`29` Umbrella ADRs):**
   - Preserve `schemaVersion = "3.10.0"`, `22` org repositories (`9` public unlimited Actions + `9` private 0-Actions-burn + `4` cold-archived), `12` Symbol Ranking DataFeeds -> `6` auto-trading routes, `19` canonical workflows (`10` AGY DAGs), `24` private vault ADRs (`3071f44a`), and `0` stale/`kimi` models across `54` 3-surface checkouts.

## Alternatives Considered

1. **Maintain separate `9`-feed datafeed contracts across research and harness repositories:** Rejected — creates PIT drift between ranking selection and downstream paper execution routes.

## Verification Witness

- `.venv/bin/python scripts/merge_gate.py` (`architecture_catalog --check`, `umbrella --check`, `ruff`, `ty`, `pytest`) -> `PASS`.
- `gitleaks` -> `0` leaks.
