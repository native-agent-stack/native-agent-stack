# SOTA Full-Landscape Disk-Z Hosted Research Frameworks, Orca & Multi-Model AO Registry (`ADR-0050` / `ADR-0051`)

- **Canonical SHA-256:** `f9164837df0bd1ee326efc7d7959b4d261637d2f1e4a5a7cbbf3b0aae7cbdc70`
- **Total Local Upstream Repos Indexed:** `95` (`18/18` Immutable Shelf + `3` Hosted UI/Plugins + `44` Quant/Options/ML/Foundation/Sandbox Frameworks + `25` Orca/Multi-Model-AO/Harness/Security Frameworks + `5` Explicitly Quarantined/Excluded)
- **Live Local Surfaces:** FINOS Workspace `http://localhost:1420` (plugins: `plotly-charts@2.5.0, ag-grid@2.3.0`) · OpenBB Backend `http://127.0.0.1:6900` · MLflow 3.18.0 `http://127.0.0.1:5050` · Official Tearsheets `http://127.0.0.1:8793` · RTX 4090 Sidecar `http://127.0.0.1:8794` · IBKR Paper `127.0.0.1:4002` · Orca `1.4.264 (ready, reachable)`

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
| `openbq-org/finos-workspace` | `Apache-2.0` | `a0047d50d97c` | `Z:/sota-data/finos-workspace` | http://localhost:1420 (API :8000, Docker Compose 5/5 healthy) | `LIVE_HOSTED_LOCAL_DOCKER` |
| `openbq-org/finos-workspace-plugins` | `Apache-2.0` | `d9b57e901411` | `Z:/sota-data/hosted-research-frameworks/finos-workspace-plugins` | Deployed plugin plotly-charts@2.5.0 -> Z:/sota-data/finos-workspace/widget-plugins/ | `LIVE_PLUGIN_APPROVED_GRANTED` |
| `openbq-org/backends-for-openbb` | `MIT` | `a6293707576e` | `Z:/sota-data/hosted-research-frameworks/backends-for-openbb` | http://127.0.0.1:6900 (SOTA OpenBB Workspace FastAPI widgets.json backend) | `LIVE_HOSTED_LOCAL_API` |

## Tier C — Hosted Quant, US Equities/Options, ML, Foundation-Model & Sandbox Frameworks (`44`)

| Repo | SPDX | HEAD SHA (12) | Layers | Stages | Security Posture | Role |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `microsoft/qlib` | `MIT` | `543552324638` | `L3, L14` | `S3, S5` | `CLEARED_RESEARCH_ISOLATED_PY312` | Qlib v0.9.8 Alpha158 PIT cross-sectional factor research (REG_US 1m, 0 order code) |
| `openbq-org/OpenBB` | `AGPL-3.0` | `bbf1ab2020c2` | `L6, L13` | `S2, S7` | `CLEARED_HOSTED_LOCAL_ONLY` | Official active OpenBQ OpenBB terminal & built-in MCP server continuation |
| `nautechsystems/nautilus_agents` | `LGPL-3.0` | `380ae38f3533` | `L2, L5, L8` | `S4, S6` | `CLEARED_WATCH_ZERO_ORDER_PATH` | Official Rust-native Agents SDK for NautilusTrader (0 order-path code, 0 API keys) |
| `anthropics/financial-services` | `Apache-2.0` | `3e32c2287dcb` | `L3, L8` | `S3, S6` | `CLEARED_RESEARCH_ZERO_ORDER_PATH` | Official Anthropic financial analysis, Earnings Reviewer & MCP connectors |
| `waylonli/FINSABER` | `Apache-2.0` | `e72c26206d08` | `L4, L15` | `S5, S6` | `CLEARED_EVAL_ONLY_NO_BROKER_KEYS` | KDD 2026 Oral leakage-free & LLM token-cost backtest evaluation harness (eval-only) |
| `AI4Finance-Foundation/FinRobot` | `Apache-2.0` | `63e1884a42ea` | `L3, L6` | `S3, S8` | `CLEARED_RESEARCH_READ_ONLY` | Deterministic tool-backed equity & quant research agent platform |
| `aliyun/qwen-dianjin` | `MIT` | `a626b083c1c3` | `L1, L7` | `S2, S3` | `CLEARED_LOCAL_RTX4090_ONLY` | Local RTX 4090 DianJin-R1 & Fin-PRM SEC 8-K / earnings catalyst reasoning |
| `massive-com/mcp_massive` | `MIT` | `1e161a8c50b6` | `L1, L13` | `S2` | `CLEARED_READ_ONLY_MCP` | Official Massive.com (formerly Polygon.io) read-only US equities & options MCP |
| `BrainDAO/mcp-polymarket` | `MIT` | `5360bef548af` | `L1, L13` | `S2` | `CLEARED_READ_ONLY_ZERO_PRIVATE_KEY` | Read-only Polymarket Gamma macro/Fed/CPI implied-probability MCP (0 private keys) |
| `microsoft/MarS` | `MIT` | `f04dd87a4d56` | `L2, L12` | `S4` | `CLEARED_RESEARCH_SIM_ONLY` | ICLR 2025 Large Market Model order-level generative LOB & market-impact simulator |
| `peernagy/LOBS5` | `MIT` | `aa36029e9d34` | `L2, L12` | `S4` | `CLEARED_RESEARCH_SIM_ONLY` | State-Space generative LOB simulator & LOB-Bench stylized-fact parity |
| `PriorLabs/TabPFN` | `Apache-2.0` | `e1a3550654df` | `L3, L7` | `S3` | `CLEARED_LOCAL_RTX4090_ONLY` | In-context tabular foundation model for small-sample cross-sectional factors |
| `amazon-science/chronos-forecasting` | `Apache-2.0` | `1224fafa91e1` | `L3` | `S3` | `CLEARED_LOCAL_RTX4090_ONLY` | Chronos-2 120M multivariate & exogenous macro-covariate time-series foundation model |
| `SalesforceAIResearch/uni2ts` | `Apache-2.0` | `cfd46d4510ed` | `L7, L11` | `S3, S5` | `CLEARED_LOCAL_RTX4090_ONLY` | MOIRAI-2 decoder-only multi-quantile VaR/ES tail-risk foundation model |
| `online-ml/river` | `BSD-3-Clause` | `5ea245400645` | `L3, L14` | `S3, S5` | `CLEARED_TIER0_CHARTER_CORE` | Streaming CUSUM, ADWIN & Page-Hinkley online anomaly & alpha-decay detection |
| `scikit-learn-contrib/MAPIE` | `BSD-3-Clause` | `e4c4f5f7daea` | `L11` | `S5` | `CLEARED_RESEARCH_RISK_GATE` | Distribution-free adaptive conformal prediction intervals for dynamic VaR/stop bounds |
| `py-why/dowhy` | `MIT` | `45de9a90623b` | `L4, L12` | `S5, S6` | `CLEARED_RESEARCH_CAUSAL_GATE` | Causal inference, refutation & Double-ML alpha/execution slippage attribution |
| `shiyu-coder/Kronos` | `MIT` | `67b630e67f6a` | `L7` | `S3, S4` | `CLEARED_LOCAL_RTX4090_ONLY` | K-line foundation model (12B+ K-lines) for Monte Carlo volatility & path bounds |
| `bashtage/arch` | `NCSA` | `d3e858fc1c99` | `L4` | `S5` | `CLEARED_TIER0_CHARTER_CORE` | Hansen SPA, StationaryBootstrap & Model Confidence Set (MCS) falsification |
| `The-FinAI/FinBen` | `MIT` | `74ea6b8f8fcd` | `L4, L15` | `S6, S8` | `CLEARED_EVAL_BENCHMARK` | lm-evaluation-harness holistic financial LLM evaluation benchmark |
| `The-FinAI/Fino1` | `MIT` | `f2b9e9931778` | `L3` | `S3` | `CLEARED_LOCAL_RTX4090_ONLY` | 14B SFT+GRPO FinCoT financial reasoning model for FinQA/XBRL-Math |
| `FreedomIntelligence/TwinMarket` | `MIT` | `de5f2446fcba` | `L11, L13` | `S4, S6` | `CLEARED_STRESS_SIM_ONLY` | BDI multi-agent herding, contagion & flash-crash counterfactual stress simulator |
| `mlflow/mlflow` | `Apache-2.0` | `1ca7129977ab` | `L4, L10` | `S1, S5, S8` | `LIVE_HOSTED_LOCAL_SERVER_5050` | MLflow 3.18.0 sole upstream experiment & true trial-count (N) tracking server (:5050) |
| `optuna/optuna` | `MIT` | `0abf066c1e5d` | `L3, L14` | `S3, S5` | `CLEARED_TIER0_CHARTER_CORE` | Hyperparameter & threshold optimization bounded by pre-registered HLZ trial budgets |
| `deepcharles/ruptures` | `BSD-2-Clause` | `ee1c8ff8a548` | `L3` | `S3` | `CLEARED_TIER0_CHARTER_CORE` | Offline structural change-point & regime-break segmentation for pre-wall norm disruptions |
| `stumpy-dev/stumpy` | `BSD-3-Clause` | `a42ca40e544b` | `L3` | `S3` | `CLEARED_TIER0_CHARTER_CORE` | Matrix-profile time-series anomaly/discord & motif discovery for early-entry detection |
| `ml4t/engineer` | `MIT` | `c63159245c0c` | `L3` | `S2, S3` | `CLEARED_TIER0_CHARTER_CORE` | Point-in-time quantitative feature engineering companion to ml4t-diagnostic |
| `dagster-io/dagster` | `Apache-2.0` | `939bd1ea940e` | `L1, L8` | `S2, S8` | `CLEARED_TIER0_CHARTER_CORE` | Software-defined data & pre-wall research pipeline orchestration |
| `UKGovernmentBEIS/inspect_ai` | `MIT` | `cf72dbc041f9` | `L8, L15` | `S6, S8` | `CLEARED_TIER0_CHARTER_CORE` | Structured agent & skill evaluation harness for multi-model regression testing |
| `stanfordnlp/dspy` | `MIT` | `7fbc8ff1665e` | `L10, L15` | `S3, S8` | `CLEARED_TIER0_CHARTER_CORE` | Declarative GEPA / MIPROv2 prompt & skill optimization with empirical regression metrics |
| `OpenHands/OpenHands` | `MIT` | `0f4cb6af9591` | `L8, L14` | `S3, S6` | `CLEARED_DOCKER_SANDBOX_ONLY` | Tier-0 Charter Docker-sandboxed autonomous research & coding runtime |
| `WecoAI/aideml` | `MIT` | `ad73d227af48` | `L3, L14` | `S3, S5` | `CLEARED_DOCKER_SANDBOX_ONLY` | Tier-0 Charter Docker-sandboxed autonomous ML engineering search agent |
| `lightgbm-org/LightGBM` | `MIT` | `7810ecea3f23` | `L3, L7` | `S3` | `CLEARED_TIER0_CHARTER_CORE` | Gradient boosted decision trees for PIT cross-sectional tabular alpha |
| `catboost/catboost` | `Apache-2.0` | `b7f986a16ac2` | `L3, L7` | `S3` | `CLEARED_TIER0_CHARTER_CORE` | Symmetric oblivious trees with native categorical & sector regime handling |
| `treeverse/dvc` | `Apache-2.0` | `b59add99ee66` | `L1, L10` | `S1, S2` | `CLEARED_TIER0_CHARTER_CORE` | Cryptographic PIT dataset versioning & pre-wall lake lineage tracking |
| `unit8co/darts` | `Apache-2.0` | `b91773760a22` | `L3, L11` | `S3, S5` | `CLEARED_RESEARCH_BASELINES` | Conformal prediction intervals & multi-horizon statistical forecasting |
| `Nixtla/statsforecast` | `Apache-2.0` | `98ce313b089b` | `L3` | `S3, S5` | `CLEARED_RESEARCH_BASELINES` | Zero-leakage fast statistical baseline hurdles |
| `databento/databento-python` | `Apache-2.0` | `f6529f1062e0` | `L1, L13` | `S2, S4` | `CLEARED_PIT_DATA_CLIENT` | Bitemporal nanosecond PIT tick & MBO/L1 market-data contract |
| `tradermonty/claude-trading-skills` | `MIT` | `901985468f4d` | `L3, L11` | `S3` | `CLEARED_STRATEGY_SKILLS` | VCP, PEAD, Episodic Pivot, Momentum Burst, Breadth & Market-Top/FTD skills |
| `aeon-toolkit/aeon` | `BSD-3-Clause` | `1510ad271b91` | `L3, L7` | `S3` | `CLEARED_TIME_SERIES_ML` | Time-series classification, regression, clustering, segmentation & anomaly detection |
| `cvxpy/cvxpy` | `Apache-2.0` | `d889ec46a03a` | `L11` | `S5, S7` | `CLEARED_CONVEX_RISK_OPT` | Convex portfolio risk-budgeting & turnover/beta-constrained allocation |
| `google-research/timesfm` | `Apache-2.0` | `918df02c9d36` | `L3, L7` | `S3` | `CLEARED_LOCAL_RTX4090_ONLY` | Google Research Time-Series Foundation Model (TSFM) for pre-wall horizon forecasts |
| `QuantConnect/Lean` | `Apache-2.0` | `32a302a9a0fd` | `L1, L3` | `S2, S4` | `CLEARED_EQUITIES_OPTIONS_REF` | Institutional US equities & options corporate-action, RVOL & Greeks engine reference |
| `lballabio/QuantLib` | `BSD-3-Clause` | `26a44f1fc884` | `L2, L13` | `S4` | `CLEARED_US_OPTIONS_PRICING` | Institutional US options Greeks, implied-volatility surface & derivatives pricing library |

## Tier C2 — Hosted SOTA Research Convergence Harness, Orca, Multi-Model AO & Security (`25`)

| Repo | SPDX | HEAD SHA (12) | Layers | Stages | Security Posture | Role |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `stablyai/orca` | `MIT` | `9e9ceede7543` | `L8, L15` | `S6, S8` | `LIVE_LOCAL_RUNTIME_1_4_264` | Isolated git worktree fleet (18/18 orca.yaml), dual-machine mesh & automations |
| `OrchestratorInc/agent-orchestrator` | `Apache-2.0` | `080a1a2a5830` | `L8` | `S6, S8` | `CLEARED_MULTI_MODEL_AO` | 8-slot pluggable Multi-Model Agent Orchestrator (AO) worktree, CI-reaction & review lifecycle |
| `Yeachan-Heo/oh-my-claudecode` | `MIT` | `dec7e4188c0e` | `L8` | `S6` | `CLEARED_RUNTIME_ORCHESTRATOR` | Claude Code OMC v2 central multi-session runtime orchestrator |
| `Yeachan-Heo/oh-my-codex` | `MIT` | `0323a79e5b0b` | `L8` | `S6` | `CLEARED_RUNTIME_ORCHESTRATOR` | Codex OMX adversarial critic & parallel implementation workers |
| `can1357/oh-my-pi` | `MIT` | `517aaf00c435` | `L8` | `S6` | `CLEARED_RUNTIME_ORCHESTRATOR` | Pi/OMP @worker role-selected thinking-effort runtime workers |
| `deepseek-ai/deepseek-harness` | `MIT` | `2e39e70496aa` | `L8` | `S6` | `CLEARED_RUNTIME_ORCHESTRATOR` | DSH 10-layer plugin harness & 1M-context pre-wall evaluation runtime |
| `aannoo/hcom` | `MIT` | `de33e31a0cdb` | `L8, L10` | `S6, S8` | `CLEARED_PEER_BUS` | Real-time cross-terminal agent wakeup & peer push messaging |
| `gastownhall/beads` | `MIT` | `786241099046` | `L8` | `S6, S8` | `CLEARED_TASK_DAG` | Git-backed distributed dependency task graph tracking (bd) |
| `rlaope/oh-my-hermes` | `MIT` | `78e2c3b62e75` | `L8, L10` | `S6, S8` | `CLEARED_COWORKER_NET` | Cross-vendor coworker network & adaptive self-evolution bridge |
| `alvinunreal/oh-my-opencode-slim` | `MIT` | `d667451c304b` | `L8` | `S6` | `CLEARED_MODEL_ROUTER` | Lean multi-model routing for OpenCode Hephaestus/Sisyphus |
| `mvschwarz/openrig` | `Apache-2.0` | `5295b61a7c23` | `L8` | `S6` | `CLEARED_MULTI_AGENT_RIG` | Structured multi-agent rig & worker dispatch supervision |
| `backnotprop/plannotator` | `Apache-2.0` | `5cf5177267aa` | `L6, L8` | `S6` | `CLEARED_PLAN_REVIEW` | Visual plan review & institutional editorial craft verification |
| `NVIDIA/auto-ontology` | `Apache-2.0` | `f3c310c7a279` | `L8` | `S6` | `CLEARED_ONTOLOGY_GRAPH` | Automated codebase & ecosystem ontology graph reasoning |
| `xerj-org/xerj` | `Apache-2.0` | `d9dd2cbb9155` | `L8` | `S6` | `CLEARED_AST_INDEXER` | High-speed local semantic & AST workspace indexing |
| `Nutlope/hallmark` | `MIT` | `04977e15f3df` | `L8, L15` | `S6, S8` | `CLEARED_QUALITY_BENCH` | Structured engineering quality verification benchmarks |
| `NVIDIA/SkillEvaluator` | `Apache-2.0` | `4327960b90d1` | `L9, L15` | `S6, S8` | `CLEARED_4TIER_SKILL_AUDIT` | 4-tier skill quality, security & 8-runtime parity auditing (60/60) |
| `ai-openshell/openshell` | `Apache-2.0` | `438e07b23124` | `L9` | `S6` | `CLEARED_SANDBOX_POLICY` | Fail-closed execution & secret-access sandbox boundaries |
| `elementalsouls/Claude-BugHunter` | `MIT` | `8258d2972680` | `L9` | `S6` | `CLEARED_REDTEAM_24CLASS` | 24-class adversarial bug-hunting & trading-firewall red-team audits |
| `cloudflare/security-audit-skill` | `MIT` | `c1c8a8c14710` | `L9` | `S6` | `CLEARED_TWOPASS_AUDIT` | Two-pass self-refuting vulnerability confirmation methodology |
| `trailofbits/skills` | `CC-BY-SA-4.0` | `149d7b21f406` | `L0, L9` | `S1, S6` | `CLEARED_DIMENSIONAL_FP` | Dimensional analysis, IEEE-754 fp-check & Hypothesis property invariants |
| `obra/superpowers` | `MIT` | `22f0b463e7a5` | `L0, L8` | `S6, S8` | `CLEARED_TDD_DISCIPLINE` | Red-Green-Refactor TDD, root-cause debugging & isolated worktree verification |
| `microsoft/SkillOpt` | `MIT` | `4fa83964c71a` | `L10, L15` | `S8` | `CLEARED_FRICTION_MINING` | Trajectory-friction mining converting transcript.jsonl errors into SKILL.md upgrades |
| `gitleaks/gitleaks` | `MIT` | `5f6ec56cfa6f` | `L0, L9` | `S6` | `CLEARED_ZERO_LEAK_GATE` | Pre-commit & CI zero-secret / zero-home-path enforcement |
| `ast-grep/ast-grep` | `MIT` | `8a92260ad4b6` | `L0, L9` | `S6` | `CLEARED_AST_LINT_GATE` | Structural AST search, lint rule authoring & deterministic multi-file codemods |
| `HypothesisWorks/hypothesis` | `MPL-2.0` | `9a15ddde5824` | `L0, L4` | `S5, S6` | `CLEARED_TIER0_CHARTER_CORE` | Property-based invariant fuzzing for ADR-0022 stops, PIT timestamps & IEEE-754 bounds |

## Tier D — Explicitly Quarantined / Reference-Only / Unlicensed (`NONE`) Containment Firewall (`5`)

| Repo | SPDX | HEAD SHA (12) | Containment Posture | Reason |
| :--- | :--- | :--- | :--- | :--- |
| `microsoft/RD-Agent` | `MIT` | `484776c211e4` | `QUARANTINED_DO_NOT_RUN_UNSANDBOXED` | Reference-only Co-STEER methodology; factor.py:165 runs unsandboxed host shell & lacks HLZ control |
| `TauricResearch/TradingAgents` | `Apache-2.0` | `c4544913a14e` | `REFERENCE_ONLY_DATE_WINDOW_PATTERN` | Reference-only trade-date clamping pattern (date_window.py:79); daily/non-repeatable LLM outputs |
| `virattt/ai-hedge-fund` | `MIT` | `5c553b522204` | `REFERENCE_ONLY_MOCK_BOOK` | Reference-only educational multi-agent mock book; not for production execution |
| `HKUDS/Vibe-Trading` | `MIT` | `25c89a0aa21d` | `QUARANTINED_ZERO_BROKER_KEYS` | Skill-native trading research harness reference; contains order-routing code (0 broker keys ever) |
| `NousResearch/hermes-agent-self-evolution` | `NONE` | `` | `EXCLUDED_UNLICENSED_NONE` | Live GitHub API returned spdx=NONE (all rights reserved); blocked by ADR-0048 license firewall |
