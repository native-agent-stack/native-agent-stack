# Tier-0 Engineering & Quantitative Charter (Canonical Single Rule)

## 1. Upstream-Only Mandate (Zero Self-Built Frameworks & Zero Paper Self-Invention)
- **Install, integrate, or build upon verified SOTA upstream open-source repos only.** Never self-build backtest loops, broker polling daemons, experiment trackers, agent buses, memory stores, MCP wrappers, or manifest registries.
- **Zero Paper Self-Invention (Clean-Installed Frameworks, Platforms & Official Paper Repos Only):** Never self-invent or hand-code strategies, models, indicators, simulators, or research algorithms from scratch "based on papers." ONLY cleanly install verified SOTA upstream frameworks, hosted platforms, and official/verified paper reference repositories, configure them with related installed paper packages, and test end-to-end (E2E) on pre-wall historical data (`<= 2026-10-15`).
- **Pinned stack (exact versions in `pyproject.toml` / `uv.lock` & `~/Documents/upstream/PINS.md`):**
  - **Data & PIT:** `Polars`, `DuckDB`, `NautilusTrader ParquetDataCatalog`, `Pandera`, `exchange_calendars`, `edgartools`, `DVC`.
  - **Features, Anomaly & Reversal:** `ml4t-engineer`, `river`, `ruptures`, `stumpy`, `LightGBM`, `CatBoost` (plus isolated Python 3.12 `Qlib v0.9.8` worker).
  - **Sim == Paper == Live Engine:** `NautilusTrader v2` (`BacktestEngine` / `sandbox` / `LiveNode` with native `interactive_brokers` adapter) + Rust `hftbacktest` (`RiskAdverseQueueModel`).
  - **Falsification & Risk:** `skfolio` (`CombinatorialPurgedCV`), `ml4t-diagnostic` (`DSR`/`PBO`), `arch` (Hansen `SPA` / `StationaryBootstrap`), `statsmodels` (HAC SE), `QuantStats`.
  - **Research Harness & Compounding:** `MLflow 3` (sole experiment & trial-count ledger), `Optuna`, `Dagster`, Docker-sandboxed `OpenHands` / `aideml` (never run LLM-generated code unsandboxed on host), `Inspect AI`, `DSPy`/`GEPA`, `Orca` worktrees.
  - **Verification & UI:** `uv`, `ruff`, `ty`, `ast-grep`, `pytest`, `Hypothesis`, `gitleaks`, `pre-commit`, `FINOS Perspective`, `TradingView Lightweight Charts`.
- **Hard Code Ceiling:** Custom production code MUST remain `<= 5,000` LOC (thin strategy, PIT glue, fail-closed risk only). Delete before adding. Write an ADR only for an irreversible architectural decision.

## 2. Epistemic Discipline
- **Evidence over recollection:** Verify every API, schema, version, and flag against `~/Documents/upstream/` (`PINS.md`) or live execution before citing or coding. Label anything unverified `UNVERIFIED`.
- **No silent fallbacks:** If a test, engine, GPU check, sandbox, or data load fails, stop and report the exact failure. Never substitute synthetic data, stubs, or hand-rolled loops.
- **Empirical done:** Every engineering task concludes with exact commands executed and verbatim pass/fail counts (`ruff`, `ty`, `pytest`, `gitleaks`).

## 3. Quantitative Parity, PIT & Falsification Standard
- **Single-Engine Parity (Sim == Paper == Live):** Every strategy subclasses `nautilus_trader.trading.Strategy` and runs identically across `BacktestEngine`, `sandbox`, and `LiveNode`. Zero custom broker polling loops or separate research simulators.
- **Strict Causal PIT Wall (`<= 2026-10-15`):** Discovery reads ONLY pre-wall `~/Documents/market-data/` (zero post-wall reads). 1-min bars are visible at `t_ns + 60s`; FINRA short volume is strictly `T-1`; SEC filings join on `accepted_ns <= as_of_ns`; splits/halves respect `XNYS` (`exchange_calendars`).
- **Prove Before Plumbing:** Every strategy—and every reversal/inverse-flip leg independently—must be logged in `MLflow` and clear `1x` & `2x` real NBBO spread + impact costs, `hftbacktest` L1 queue markout (if passive), `skfolio` CPCV, `ml4t-diagnostic` DSR/PBO (at true total trial count `N`), `arch` Hansen SPA, and `statsmodels` HAC t-stat before Paper deployment.

## 4. Hard Safety, Privacy & Topology Boundaries
- **Protected Boundaries (100% hard-refused without explicit owner authorization):** Never modify `~/Documents/upstream/`, `sextant`, Drive `D:`, or live real-money broker endpoints (Alpaca Live, IBKR `:4001`/`:7496`, `:8798`/`:8796`).
- **Fail-Closed Risk Invariants (exact `Decimal` + `NautilusTrader RiskEngine`, Hypothesis-tested):** Atomic Reg-NMS Rule-612 stop-loss `<= 2.00%`, session-latched `-1.50%` daily drawdown breaker, `>= 10%` broker API protective-exit rate reserve.
- **Single Active Broker Host (`singleActiveBrokerHostOnly = true`):** Stationary `Noesis` (`100.110.115.22`) runs Docker research sandboxes and Paper `LiveNode` (`:4002`). Portable Mac runs zero broker ports while Noesis is active.
- **Zero Secret or PII Leaks:** Never print, log, or commit `.env`, API keys, tokens, account IDs, raw dollar balances, or hardcoded home paths.
