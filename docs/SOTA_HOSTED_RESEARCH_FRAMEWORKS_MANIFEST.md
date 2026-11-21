# SOTA Disk-Z Hosted Advanced Research Frameworks Registry (`ADR-0050`)

- **Canonical SHA-256:** `557d42cd3736e666545995c8cdce10acf39bef50a19320d8efbfeec69cd1fd37`
- **Total Local Upstream Repos Indexed:** `55` (`18/18` Immutable Shelf + `3` Hosted UI/Plugins + `30` SPDX-Cleared Frontier/Charter Research Frameworks + `4` Explicitly Quarantined Reference-Only)
- **Live Local Surfaces:** FINOS Workspace `http://localhost:1420` (plugins: `plotly-charts@2.5.0, ag-grid@2.3.0`) · OpenBB Backend `http://127.0.0.1:6900` · Official Tearsheets `http://127.0.0.1:8793` · RTX 4090 Full-Res Sidecar `http://127.0.0.1:8794` · IBKR Paper `127.0.0.1:4002`

## Tier A — 18 Immutable Core Shelf Pins (`Z:/sota-data/upstream/`, Read-Only)

| Library | Ref | Exact 40-Char SHA | License | Verified |
| :--- | :--- | :--- | :--- | :---: |
| `alpaca-mcp-server` | `v2.4.1` | `63cc4278d87b31f3ed4efcfaa55624095c6d7be8` | `MIT` | `True` |
| `alpaca-py` | `v0.45.0` | `c42add7c0a7026e2ead3ed64e76f4def2b99fda4` | `Apache-2.0` | `True` |
| `duckdb` | `v2.0.0` | `d54cbbe3df17e8e5ce68312f483b4155836112aa` | `MIT` | `True` |
| `edgartools` | `v6.2.0` | `574c2bd15f6c629bceef03b6550ea8ac8abf3473` | `MIT` | `True` |
| `exchange_calendars` | `4.13.2` | `dbe38b1f6887434bbdd1a7d2df6ff8f1742a048a` | `Apache-2.0` | `True` |
| `hftbacktest` | `main` | `5f3ec40b2afb764e0fea112f941ed85523ef4e88` | `MIT` | `True` |
| `ib_async` | `v2.1.0` | `ab629f34c1823ea4c1542f32f07377208a86bdfd` | `BSD-3-Clause` | `True` |
| `lightweight-charts` | `master` | `c29c51e1e5bc61981da5832c97797cb8283d120f` | `Apache-2.0` | `True` |
| `ml4t-diagnostic` | `v0.2.0` | `19e76072e64a18c9ba56130e4a7bcc0bc871f57e` | `MIT` | `True` |
| `nautilus-alpaca` | `main` | `59685d56631b981018a189b5ced1a7000a50bfbd` | `Apache-2.0` | `True` |
| `nautilus_trader` | `v2.0.0rc9` | `da6b57aefdd62b44f675e434ffcfefca7f4025dd` | `LGPL-3.0-or-later` | `True` |
| `pandera` | `v0.35.0` | `02b375ab43f39f8c5c5108695c1791fa04f99a26` | `MIT` | `True` |
| `perspective` | `v5.9.2` | `0264ec13cd28ef4a2a136c8ef021c3c112bc8990` | `Apache-2.0` | `True` |
| `polars` | `py-2.1.0` | `7f902bd3ffd27ff82d14278a09a295ff2f7aed92` | `MIT` | `True` |
| `quantstats` | `main` | `d1a214fb906e76f974f45cdccf923b601c67a756` | `Apache-2.0` | `True` |
| `skfolio` | `v1.12.7` | `90e3fb907fab39d244d899f3caf4e9676889309c` | `BSD-3-Clause` | `True` |
| `statsmodels` | `v0.15.0` | `278ff9950636cdd4939b4055e339a8e681d79cab` | `BSD-3-Clause` | `True` |
| `vectorbt` | `v1.2.0` | `a52a984b631624bb9daf41cb19f532fe559cf0ef` | `Apache-2.0` | `True` |

## Tier B — Live Hosted Interactive UI, Official Plugins & Backends

| Repo | SPDX | HEAD SHA (12) | Local Path | Endpoint / Deployment | Posture |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `openbq-org/finos-workspace` | `Apache-2.0` | `a0047d50d97c` | `Z:/sota-data/finos-workspace` | http://localhost:1420 (API :8000, Docker Compose 5-container stack) | `LIVE_HOSTED_LOCAL_DOCKER` |
| `openbq-org/finos-workspace-plugins` | `Apache-2.0` | `d9b57e901411` | `Z:/sota-data/hosted-research-frameworks/finos-workspace-plugins` | Deployed plugin plotly-charts@2.5.0 -> Z:/sota-data/finos-workspace/widget-plugins/ | `LIVE_PLUGIN_APPROVED_GRANTED` |
| `openbq-org/backends-for-openbb` | `MIT` | `a6293707576e` | `Z:/sota-data/hosted-research-frameworks/backends-for-openbb` | http://127.0.0.1:6900 (SOTA OpenBB Workspace FastAPI widgets.json backend) | `LIVE_HOSTED_LOCAL_API` |

## Tier C — Hosted Advanced Research & Tier-0 Charter Frameworks (`L0`–`L15` / `S1`–`S8`)

| Repo | SPDX | HEAD SHA (12) | Layers | Stages | Local Path | Security Posture | Role |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `microsoft/qlib` | `MIT` | `543552324638` | `L3, L14` | `S3, S5` | `Z:/sota-cache/llm-native-eval/qlib` | `CLEARED_RESEARCH_ISOLATED_PY312` | Qlib v0.9.8 Alpha158 PIT cross-sectional factor research (REG_US 1m, 0 order code) |
| `openbq-org/OpenBB` | `AGPL-3.0` | `bbf1ab2020c2` | `L6, L13` | `S2, S7` | `Z:/sota-cache/llm-native-eval/OpenBB` | `CLEARED_HOSTED_LOCAL_ONLY` | Official active OpenBQ OpenBB terminal & built-in MCP server continuation |
| `nautechsystems/nautilus_agents` | `LGPL-3.0` | `380ae38f3533` | `L2, L5, L8` | `S4, S6` | `Z:/sota-cache/llm-native-eval-pass2/nautilus_agents` | `CLEARED_WATCH_ZERO_ORDER_PATH` | Official Rust-native Agents SDK for NautilusTrader (0 order-path code, 0 API keys) |
| `anthropics/financial-services` | `Apache-2.0` | `3e32c2287dcb` | `L3, L8` | `S3, S6` | `Z:/sota-cache/llm-native-eval-pass2/financial-services` | `CLEARED_RESEARCH_ZERO_ORDER_PATH` | Official Anthropic financial analysis, Earnings Reviewer & MCP connectors |
| `waylonli/FINSABER` | `Apache-2.0` | `e72c26206d08` | `L4, L15` | `S5, S6` | `Z:/sota-cache/llm-native-eval-pass2/FINSABER` | `CLEARED_EVAL_ONLY_NO_BROKER_KEYS` | KDD 2026 Oral leakage-free & LLM token-cost backtest evaluation harness (eval-only) |
| `AI4Finance-Foundation/FinRobot` | `Apache-2.0` | `63e1884a42ea` | `L3, L6` | `S3, S8` | `Z:/sota-cache/llm-native-eval-pass2/FinRobot` | `CLEARED_RESEARCH_READ_ONLY` | Deterministic tool-backed equity & quant research agent platform |
| `aliyun/qwen-dianjin` | `MIT` | `a626b083c1c3` | `L1, L7` | `S2, S3` | `Z:/sota-cache/llm-native-eval-pass2/qwen-dianjin` | `CLEARED_LOCAL_RTX4090_ONLY` | Local RTX 4090 DianJin-R1 & Fin-PRM SEC 8-K / earnings catalyst reasoning |
| `massive-com/mcp_massive` | `MIT` | `1e161a8c50b6` | `L1, L13` | `S2` | `Z:/sota-cache/llm-native-eval-pass2/mcp_massive` | `CLEARED_READ_ONLY_MCP` | Official Massive.com (formerly Polygon.io) read-only US equities & options MCP |
| `BrainDAO/mcp-polymarket` | `MIT` | `5360bef548af` | `L1, L13` | `S2` | `Z:/sota-cache/llm-native-eval-pass2/mcp-polymarket` | `CLEARED_READ_ONLY_ZERO_PRIVATE_KEY` | Read-only Polymarket Gamma macro/Fed/CPI implied-probability MCP (0 private keys) |
| `microsoft/MarS` | `MIT` | `f04dd87a4d56` | `L2, L12` | `S4` | `Z:/sota-data/hosted-research-frameworks/MarS` | `CLEARED_RESEARCH_SIM_ONLY` | ICLR 2025 Large Market Model order-level generative LOB & market-impact simulator |
| `peernagy/LOBS5` | `MIT` | `aa36029e9d34` | `L2, L12` | `S4` | `Z:/sota-data/hosted-research-frameworks/LOBS5` | `CLEARED_RESEARCH_SIM_ONLY` | State-Space generative LOB simulator & LOB-Bench stylized-fact parity |
| `PriorLabs/TabPFN` | `Apache-2.0` | `e1a3550654df` | `L3, L7` | `S3` | `Z:/sota-data/hosted-research-frameworks/TabPFN` | `CLEARED_LOCAL_RTX4090_ONLY` | In-context tabular foundation model for small-sample cross-sectional factors |
| `amazon-science/chronos-forecasting` | `Apache-2.0` | `1224fafa91e1` | `L3` | `S3` | `Z:/sota-data/hosted-research-frameworks/chronos-forecasting` | `CLEARED_LOCAL_RTX4090_ONLY` | Chronos-2 120M multivariate & exogenous macro-covariate time-series foundation model |
| `SalesforceAIResearch/uni2ts` | `Apache-2.0` | `cfd46d4510ed` | `L7, L11` | `S3, S5` | `Z:/sota-data/hosted-research-frameworks/uni2ts` | `CLEARED_LOCAL_RTX4090_ONLY` | MOIRAI-2 decoder-only multi-quantile VaR/ES tail-risk foundation model |
| `online-ml/river` | `BSD-3-Clause` | `5ea245400645` | `L3, L14` | `S3, S5` | `Z:/sota-data/hosted-research-frameworks/river` | `CLEARED_TIER0_CHARTER_CORE` | Streaming CUSUM, ADWIN & Page-Hinkley online anomaly & alpha-decay detection |
| `scikit-learn-contrib/MAPIE` | `BSD-3-Clause` | `e4c4f5f7daea` | `L11` | `S5` | `Z:/sota-data/hosted-research-frameworks/MAPIE` | `CLEARED_RESEARCH_RISK_GATE` | Distribution-free adaptive conformal prediction intervals for dynamic VaR/stop bounds |
| `py-why/dowhy` | `MIT` | `45de9a90623b` | `L4, L12` | `S5, S6` | `Z:/sota-data/hosted-research-frameworks/dowhy` | `CLEARED_RESEARCH_CAUSAL_GATE` | Causal inference, refutation & Double-ML alpha/execution slippage attribution |
| `shiyu-coder/Kronos` | `MIT` | `67b630e67f6a` | `L7` | `S3, S4` | `Z:/sota-data/hosted-research-frameworks/Kronos` | `CLEARED_LOCAL_RTX4090_ONLY` | K-line foundation model (12B+ K-lines) for Monte Carlo volatility & path bounds |
| `bashtage/arch` | `NCSA` | `d3e858fc1c99` | `L4` | `S5` | `Z:/sota-data/hosted-research-frameworks/arch` | `CLEARED_TIER0_CHARTER_CORE` | Hansen SPA, StationaryBootstrap & Model Confidence Set (MCS) falsification |
| `The-FinAI/FinBen` | `MIT` | `74ea6b8f8fcd` | `L4, L15` | `S6, S8` | `Z:/sota-data/hosted-research-frameworks/FinBen` | `CLEARED_EVAL_BENCHMARK` | lm-evaluation-harness holistic financial LLM evaluation benchmark |
| `The-FinAI/Fino1` | `MIT` | `f2b9e9931778` | `L3` | `S3` | `Z:/sota-data/hosted-research-frameworks/Fino1` | `CLEARED_LOCAL_RTX4090_ONLY` | 14B SFT+GRPO FinCoT financial reasoning model for FinQA/XBRL-Math |
| `FreedomIntelligence/TwinMarket` | `MIT` | `de5f2446fcba` | `L11, L13` | `S4, S6` | `Z:/sota-data/hosted-research-frameworks/TwinMarket` | `CLEARED_STRESS_SIM_ONLY` | BDI multi-agent herding, contagion & flash-crash counterfactual stress simulator |
| `mlflow/mlflow` | `Apache-2.0` | `1ca7129977ab` | `L4, L10` | `S1, S5, S8` | `Z:/sota-data/hosted-research-frameworks/mlflow` | `CLEARED_TIER0_CHARTER_CORE` | MLflow 3 sole upstream experiment & true trial-count (N) tracking ledger |
| `optuna/optuna` | `MIT` | `0abf066c1e5d` | `L3, L14` | `S3, S5` | `Z:/sota-data/hosted-research-frameworks/optuna` | `CLEARED_TIER0_CHARTER_CORE` | Hyperparameter & threshold optimization bounded by pre-registered HLZ trial budgets |
| `deepcharles/ruptures` | `BSD-2-Clause` | `ee1c8ff8a548` | `L3` | `S3` | `Z:/sota-data/hosted-research-frameworks/ruptures` | `CLEARED_TIER0_CHARTER_CORE` | Offline structural change-point & regime-break segmentation for pre-wall norm disruptions |
| `stumpy-dev/stumpy` | `BSD-3-Clause` | `a42ca40e544b` | `L3` | `S3` | `Z:/sota-data/hosted-research-frameworks/stumpy` | `CLEARED_TIER0_CHARTER_CORE` | Matrix-profile time-series anomaly/discord & motif discovery for early-entry detection |
| `ml4t/engineer` | `MIT` | `c63159245c0c` | `L3` | `S2, S3` | `Z:/sota-data/hosted-research-frameworks/ml4t-engineer` | `CLEARED_TIER0_CHARTER_CORE` | Point-in-time quantitative feature engineering companion to ml4t-diagnostic |
| `dagster-io/dagster` | `Apache-2.0` | `939bd1ea940e` | `L1, L8` | `S2, S8` | `Z:/sota-data/hosted-research-frameworks/dagster` | `CLEARED_TIER0_CHARTER_CORE` | Software-defined data & pre-wall research pipeline orchestration |
| `UKGovernmentBEIS/inspect_ai` | `MIT` | `cf72dbc041f9` | `L8, L15` | `S6, S8` | `Z:/sota-data/hosted-research-frameworks/inspect_ai` | `CLEARED_TIER0_CHARTER_CORE` | Structured agent & skill evaluation harness for multi-model regression testing |
| `stanfordnlp/dspy` | `MIT` | `7fbc8ff1665e` | `L10, L15` | `S3, S8` | `Z:/sota-data/hosted-research-frameworks/dspy` | `CLEARED_TIER0_CHARTER_CORE` | Declarative GEPA / MIPROv2 prompt & skill optimization with empirical regression metrics |

## Tier D — Explicitly Quarantined / Reference-Only Repos (Containment Firewall)

| Repo | SPDX | HEAD SHA (12) | Containment Posture | Reason |
| :--- | :--- | :--- | :--- | :--- |
| `microsoft/RD-Agent` | `MIT` | `484776c211e4` | `QUARANTINED_DO_NOT_RUN_UNSANDBOXED` | Reference-only Co-STEER methodology; factor.py:165 runs unsandboxed host shell & lacks HLZ control |
| `TauricResearch/TradingAgents` | `Apache-2.0` | `c4544913a14e` | `REFERENCE_ONLY_DATE_WINDOW_PATTERN` | Reference-only trade-date clamping pattern (date_window.py:79); daily/non-repeatable LLM outputs |
| `virattt/ai-hedge-fund` | `MIT` | `5c553b522204` | `REFERENCE_ONLY_MOCK_BOOK` | Reference-only educational multi-agent mock book; not for production execution |
| `HKUDS/Vibe-Trading` | `MIT` | `25c89a0aa21d` | `QUARANTINED_ZERO_BROKER_KEYS` | Skill-native trading research harness reference; contains order-routing code (0 broker keys ever) |
