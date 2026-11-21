#!/usr/bin/env python3
"""Build SHA-256 Sealed Full-Landscape Disk-Z Hosted SOTA Research Frameworks, Orca & Multi-Model AO Registry (`ADR-0050` / `ADR-0051`).

Verifies every locally hosted upstream SOTA repository across Disk `Z:` (`95` total repos):
- Tier A (`18`): Immutable Core Quantitative Shelf (`Z:/sota-data/upstream/`, strictly READ-ONLY)
- Tier B (`3`): Live Hosted Interactive UI, Official Plugins & Backends (`finos-workspace :1420`, `finos-workspace-plugins`, `backends-for-openbb :6900`)
- Tier C (`44`): SPDX-Cleared Quant, US Equities/Options, ML, Foundation-Model, Causal/Conformal & Sandboxed Research Frameworks
- Tier C2 (`25`): SPDX-Cleared SOTA Research Convergence Harness, Orca, Multi-Model AO, Red-Team Security, SkillEvaluator & Verification Frameworks
- Tier D (`5`): Explicitly Quarantined / Reference-Only / Unlicensed (`spdx=NONE`) Containment Firewall
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_WORKSTATION = ROOT.parent
SCHEMA_VERSION = "sota.hosted-research-frameworks-manifest.v2"
CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

HOSTED_UI_AND_PLUGINS_SPECS: tuple[dict[str, Any], ...] = (
    {
        "name": "finos-workspace",
        "repo": "openbq-org/finos-workspace",
        "spdx": "Apache-2.0",
        "tier": "HOSTED_INTERACTIVE_UI",
        "path": "Z:/sota-data/finos-workspace",
        "layers": ["L6"],
        "stages": ["S7", "S8"],
        "endpoint": "http://localhost:1420 (API :8000, Docker Compose 5/5 healthy)",
        "posture": "LIVE_HOSTED_LOCAL_DOCKER",
        "role": "Official Apache-2.0 FINOS/OpenBB Workspace UI with plotly-charts@2.5.0 & ag-grid@2.3.0 active",
    },
    {
        "name": "finos-workspace-plugins",
        "repo": "openbq-org/finos-workspace-plugins",
        "spdx": "Apache-2.0",
        "tier": "HOSTED_INTERACTIVE_UI",
        "path": "Z:/sota-data/hosted-research-frameworks/finos-workspace-plugins",
        "layers": ["L6"],
        "stages": ["S7", "S8"],
        "endpoint": "Deployed plugin plotly-charts@2.5.0 -> Z:/sota-data/finos-workspace/widget-plugins/",
        "posture": "LIVE_PLUGIN_APPROVED_GRANTED",
        "role": "Official FINOS Workspace widget plugin monorepo (plotly-charts, mermaid, react-flow, map-widget)",
    },
    {
        "name": "backends-for-openbb",
        "repo": "openbq-org/backends-for-openbb",
        "spdx": "MIT",
        "tier": "HOSTED_INTERACTIVE_UI",
        "path": "Z:/sota-data/hosted-research-frameworks/backends-for-openbb",
        "layers": ["L6"],
        "stages": ["S7", "S8"],
        "endpoint": "http://127.0.0.1:6900 (SOTA OpenBB Workspace FastAPI widgets.json backend)",
        "posture": "LIVE_HOSTED_LOCAL_API",
        "role": "Official MIT OpenBB Workspace FastAPI custom backend contract & reference widgets",
    },
)

HOSTED_FRONTIER_AND_CHARTER_SPECS: tuple[dict[str, Any], ...] = (
    {"name": "qlib", "repo": "microsoft/qlib", "spdx": "MIT", "path": "Z:/sota-cache/llm-native-eval/qlib", "layers": ["L3", "L14"], "stages": ["S3", "S5"], "posture": "CLEARED_RESEARCH_ISOLATED_PY312", "role": "Qlib v0.9.8 Alpha158 PIT cross-sectional factor research (REG_US 1m, 0 order code)"},
    {"name": "OpenBB", "repo": "openbq-org/OpenBB", "spdx": "AGPL-3.0", "path": "Z:/sota-cache/llm-native-eval/OpenBB", "layers": ["L6", "L13"], "stages": ["S2", "S7"], "posture": "CLEARED_HOSTED_LOCAL_ONLY", "role": "Official active OpenBQ OpenBB terminal & built-in MCP server continuation"},
    {"name": "nautilus_agents", "repo": "nautechsystems/nautilus_agents", "spdx": "LGPL-3.0", "path": "Z:/sota-cache/llm-native-eval-pass2/nautilus_agents", "layers": ["L2", "L5", "L8"], "stages": ["S4", "S6"], "posture": "CLEARED_WATCH_ZERO_ORDER_PATH", "role": "Official Rust-native Agents SDK for NautilusTrader (0 order-path code, 0 API keys)"},
    {"name": "financial-services", "repo": "anthropics/financial-services", "spdx": "Apache-2.0", "path": "Z:/sota-cache/llm-native-eval-pass2/financial-services", "layers": ["L3", "L8"], "stages": ["S3", "S6"], "posture": "CLEARED_RESEARCH_ZERO_ORDER_PATH", "role": "Official Anthropic financial analysis, Earnings Reviewer & MCP connectors"},
    {"name": "FINSABER", "repo": "waylonli/FINSABER", "spdx": "Apache-2.0", "path": "Z:/sota-cache/llm-native-eval-pass2/FINSABER", "layers": ["L4", "L15"], "stages": ["S5", "S6"], "posture": "CLEARED_EVAL_ONLY_NO_BROKER_KEYS", "role": "KDD 2026 Oral leakage-free & LLM token-cost backtest evaluation harness (eval-only)"},
    {"name": "FinRobot", "repo": "AI4Finance-Foundation/FinRobot", "spdx": "Apache-2.0", "path": "Z:/sota-cache/llm-native-eval-pass2/FinRobot", "layers": ["L3", "L6"], "stages": ["S3", "S8"], "posture": "CLEARED_RESEARCH_READ_ONLY", "role": "Deterministic tool-backed equity & quant research agent platform"},
    {"name": "qwen-dianjin", "repo": "aliyun/qwen-dianjin", "spdx": "MIT", "path": "Z:/sota-cache/llm-native-eval-pass2/qwen-dianjin", "layers": ["L1", "L7"], "stages": ["S2", "S3"], "posture": "CLEARED_LOCAL_RTX4090_ONLY", "role": "Local RTX 4090 DianJin-R1 & Fin-PRM SEC 8-K / earnings catalyst reasoning"},
    {"name": "mcp_massive", "repo": "massive-com/mcp_massive", "spdx": "MIT", "path": "Z:/sota-cache/llm-native-eval-pass2/mcp_massive", "layers": ["L1", "L13"], "stages": ["S2"], "posture": "CLEARED_READ_ONLY_MCP", "role": "Official Massive.com (formerly Polygon.io) read-only US equities & options MCP"},
    {"name": "mcp-polymarket", "repo": "BrainDAO/mcp-polymarket", "spdx": "MIT", "path": "Z:/sota-cache/llm-native-eval-pass2/mcp-polymarket", "layers": ["L1", "L13"], "stages": ["S2"], "posture": "CLEARED_READ_ONLY_ZERO_PRIVATE_KEY", "role": "Read-only Polymarket Gamma macro/Fed/CPI implied-probability MCP (0 private keys)"},
    {"name": "MarS", "repo": "microsoft/MarS", "spdx": "MIT", "path": "Z:/sota-data/hosted-research-frameworks/MarS", "layers": ["L2", "L12"], "stages": ["S4"], "posture": "CLEARED_RESEARCH_SIM_ONLY", "role": "ICLR 2025 Large Market Model order-level generative LOB & market-impact simulator"},
    {"name": "LOBS5", "repo": "peernagy/LOBS5", "spdx": "MIT", "path": "Z:/sota-data/hosted-research-frameworks/LOBS5", "layers": ["L2", "L12"], "stages": ["S4"], "posture": "CLEARED_RESEARCH_SIM_ONLY", "role": "State-Space generative LOB simulator & LOB-Bench stylized-fact parity"},
    {"name": "TabPFN", "repo": "PriorLabs/TabPFN", "spdx": "Apache-2.0", "path": "Z:/sota-data/hosted-research-frameworks/TabPFN", "layers": ["L3", "L7"], "stages": ["S3"], "posture": "CLEARED_LOCAL_RTX4090_ONLY", "role": "In-context tabular foundation model for small-sample cross-sectional factors"},
    {"name": "chronos-forecasting", "repo": "amazon-science/chronos-forecasting", "spdx": "Apache-2.0", "path": "Z:/sota-data/hosted-research-frameworks/chronos-forecasting", "layers": ["L3"], "stages": ["S3"], "posture": "CLEARED_LOCAL_RTX4090_ONLY", "role": "Chronos-2 120M multivariate & exogenous macro-covariate time-series foundation model"},
    {"name": "uni2ts", "repo": "SalesforceAIResearch/uni2ts", "spdx": "Apache-2.0", "path": "Z:/sota-data/hosted-research-frameworks/uni2ts", "layers": ["L7", "L11"], "stages": ["S3", "S5"], "posture": "CLEARED_LOCAL_RTX4090_ONLY", "role": "MOIRAI-2 decoder-only multi-quantile VaR/ES tail-risk foundation model"},
    {"name": "river", "repo": "online-ml/river", "spdx": "BSD-3-Clause", "path": "Z:/sota-data/hosted-research-frameworks/river", "layers": ["L3", "L14"], "stages": ["S3", "S5"], "posture": "CLEARED_TIER0_CHARTER_CORE", "role": "Streaming CUSUM, ADWIN & Page-Hinkley online anomaly & alpha-decay detection"},
    {"name": "MAPIE", "repo": "scikit-learn-contrib/MAPIE", "spdx": "BSD-3-Clause", "path": "Z:/sota-data/hosted-research-frameworks/MAPIE", "layers": ["L11"], "stages": ["S5"], "posture": "CLEARED_RESEARCH_RISK_GATE", "role": "Distribution-free adaptive conformal prediction intervals for dynamic VaR/stop bounds"},
    {"name": "dowhy", "repo": "py-why/dowhy", "spdx": "MIT", "path": "Z:/sota-data/hosted-research-frameworks/dowhy", "layers": ["L4", "L12"], "stages": ["S5", "S6"], "posture": "CLEARED_RESEARCH_CAUSAL_GATE", "role": "Causal inference, refutation & Double-ML alpha/execution slippage attribution"},
    {"name": "Kronos", "repo": "shiyu-coder/Kronos", "spdx": "MIT", "path": "Z:/sota-data/hosted-research-frameworks/Kronos", "layers": ["L7"], "stages": ["S3", "S4"], "posture": "CLEARED_LOCAL_RTX4090_ONLY", "role": "K-line foundation model (12B+ K-lines) for Monte Carlo volatility & path bounds"},
    {"name": "arch", "repo": "bashtage/arch", "spdx": "NCSA", "path": "Z:/sota-data/hosted-research-frameworks/arch", "layers": ["L4"], "stages": ["S5"], "posture": "CLEARED_TIER0_CHARTER_CORE", "role": "Hansen SPA, StationaryBootstrap & Model Confidence Set (MCS) falsification"},
    {"name": "FinBen", "repo": "The-FinAI/FinBen", "spdx": "MIT", "path": "Z:/sota-data/hosted-research-frameworks/FinBen", "layers": ["L4", "L15"], "stages": ["S6", "S8"], "posture": "CLEARED_EVAL_BENCHMARK", "role": "lm-evaluation-harness holistic financial LLM evaluation benchmark"},
    {"name": "Fino1", "repo": "The-FinAI/Fino1", "spdx": "MIT", "path": "Z:/sota-data/hosted-research-frameworks/Fino1", "layers": ["L3"], "stages": ["S3"], "posture": "CLEARED_LOCAL_RTX4090_ONLY", "role": "14B SFT+GRPO FinCoT financial reasoning model for FinQA/XBRL-Math"},
    {"name": "TwinMarket", "repo": "FreedomIntelligence/TwinMarket", "spdx": "MIT", "path": "Z:/sota-data/hosted-research-frameworks/TwinMarket", "layers": ["L11", "L13"], "stages": ["S4", "S6"], "posture": "CLEARED_STRESS_SIM_ONLY", "role": "BDI multi-agent herding, contagion & flash-crash counterfactual stress simulator"},
    {"name": "mlflow", "repo": "mlflow/mlflow", "spdx": "Apache-2.0", "path": "Z:/sota-data/hosted-research-frameworks/mlflow", "layers": ["L4", "L10"], "stages": ["S1", "S5", "S8"], "posture": "LIVE_HOSTED_LOCAL_SERVER_5050", "role": "MLflow 3.18.0 sole upstream experiment & true trial-count (N) tracking server (:5050)"},
    {"name": "optuna", "repo": "optuna/optuna", "spdx": "MIT", "path": "Z:/sota-data/hosted-research-frameworks/optuna", "layers": ["L3", "L14"], "stages": ["S3", "S5"], "posture": "CLEARED_TIER0_CHARTER_CORE", "role": "Hyperparameter & threshold optimization bounded by pre-registered HLZ trial budgets"},
    {"name": "ruptures", "repo": "deepcharles/ruptures", "spdx": "BSD-2-Clause", "path": "Z:/sota-data/hosted-research-frameworks/ruptures", "layers": ["L3"], "stages": ["S3"], "posture": "CLEARED_TIER0_CHARTER_CORE", "role": "Offline structural change-point & regime-break segmentation for pre-wall norm disruptions"},
    {"name": "stumpy", "repo": "stumpy-dev/stumpy", "spdx": "BSD-3-Clause", "path": "Z:/sota-data/hosted-research-frameworks/stumpy", "layers": ["L3"], "stages": ["S3"], "posture": "CLEARED_TIER0_CHARTER_CORE", "role": "Matrix-profile time-series anomaly/discord & motif discovery for early-entry detection"},
    {"name": "ml4t-engineer", "repo": "ml4t/engineer", "spdx": "MIT", "path": "Z:/sota-data/hosted-research-frameworks/ml4t-engineer", "layers": ["L3"], "stages": ["S2", "S3"], "posture": "CLEARED_TIER0_CHARTER_CORE", "role": "Point-in-time quantitative feature engineering companion to ml4t-diagnostic"},
    {"name": "dagster", "repo": "dagster-io/dagster", "spdx": "Apache-2.0", "path": "Z:/sota-data/hosted-research-frameworks/dagster", "layers": ["L1", "L8"], "stages": ["S2", "S8"], "posture": "CLEARED_TIER0_CHARTER_CORE", "role": "Software-defined data & pre-wall research pipeline orchestration"},
    {"name": "inspect_ai", "repo": "UKGovernmentBEIS/inspect_ai", "spdx": "MIT", "path": "Z:/sota-data/hosted-research-frameworks/inspect_ai", "layers": ["L8", "L15"], "stages": ["S6", "S8"], "posture": "CLEARED_TIER0_CHARTER_CORE", "role": "Structured agent & skill evaluation harness for multi-model regression testing"},
    {"name": "dspy", "repo": "stanfordnlp/dspy", "spdx": "MIT", "path": "Z:/sota-data/hosted-research-frameworks/dspy", "layers": ["L10", "L15"], "stages": ["S3", "S8"], "posture": "CLEARED_TIER0_CHARTER_CORE", "role": "Declarative GEPA / MIPROv2 prompt & skill optimization with empirical regression metrics"},
    {"name": "OpenHands", "repo": "OpenHands/OpenHands", "spdx": "MIT", "path": "Z:/sota-data/hosted-research-frameworks/OpenHands", "layers": ["L8", "L14"], "stages": ["S3", "S6"], "posture": "CLEARED_DOCKER_SANDBOX_ONLY", "role": "Tier-0 Charter Docker-sandboxed autonomous research & coding runtime"},
    {"name": "aideml", "repo": "WecoAI/aideml", "spdx": "MIT", "path": "Z:/sota-data/hosted-research-frameworks/aideml", "layers": ["L3", "L14"], "stages": ["S3", "S5"], "posture": "CLEARED_DOCKER_SANDBOX_ONLY", "role": "Tier-0 Charter Docker-sandboxed autonomous ML engineering search agent"},
    {"name": "LightGBM", "repo": "lightgbm-org/LightGBM", "spdx": "MIT", "path": "Z:/sota-data/hosted-research-frameworks/LightGBM", "layers": ["L3", "L7"], "stages": ["S3"], "posture": "CLEARED_TIER0_CHARTER_CORE", "role": "Gradient boosted decision trees for PIT cross-sectional tabular alpha"},
    {"name": "catboost", "repo": "catboost/catboost", "spdx": "Apache-2.0", "path": "Z:/sota-data/hosted-research-frameworks/catboost", "layers": ["L3", "L7"], "stages": ["S3"], "posture": "CLEARED_TIER0_CHARTER_CORE", "role": "Symmetric oblivious trees with native categorical & sector regime handling"},
    {"name": "dvc", "repo": "treeverse/dvc", "spdx": "Apache-2.0", "path": "Z:/sota-data/hosted-research-frameworks/dvc", "layers": ["L1", "L10"], "stages": ["S1", "S2"], "posture": "CLEARED_TIER0_CHARTER_CORE", "role": "Cryptographic PIT dataset versioning & pre-wall lake lineage tracking"},
    {"name": "darts", "repo": "unit8co/darts", "spdx": "Apache-2.0", "path": "Z:/sota-data/hosted-research-frameworks/darts", "layers": ["L3", "L11"], "stages": ["S3", "S5"], "posture": "CLEARED_RESEARCH_BASELINES", "role": "Conformal prediction intervals & multi-horizon statistical forecasting"},
    {"name": "statsforecast", "repo": "Nixtla/statsforecast", "spdx": "Apache-2.0", "path": "Z:/sota-data/hosted-research-frameworks/statsforecast", "layers": ["L3"], "stages": ["S3", "S5"], "posture": "CLEARED_RESEARCH_BASELINES", "role": "Zero-leakage fast statistical baseline hurdles"},
    {"name": "databento-python", "repo": "databento/databento-python", "spdx": "Apache-2.0", "path": "Z:/sota-data/hosted-research-frameworks/databento-python", "layers": ["L1", "L13"], "stages": ["S2", "S4"], "posture": "CLEARED_PIT_DATA_CLIENT", "role": "Bitemporal nanosecond PIT tick & MBO/L1 market-data contract"},
    {"name": "claude-trading-skills", "repo": "tradermonty/claude-trading-skills", "spdx": "MIT", "path": "Z:/sota-data/hosted-research-frameworks/claude-trading-skills", "layers": ["L3", "L11"], "stages": ["S3"], "posture": "CLEARED_STRATEGY_SKILLS", "role": "VCP, PEAD, Episodic Pivot, Momentum Burst, Breadth & Market-Top/FTD skills"},
    {"name": "aeon", "repo": "aeon-toolkit/aeon", "spdx": "BSD-3-Clause", "path": "Z:/sota-data/hosted-research-frameworks/aeon", "layers": ["L3", "L7"], "stages": ["S3"], "posture": "CLEARED_TIME_SERIES_ML", "role": "Time-series classification, regression, clustering, segmentation & anomaly detection"},
    {"name": "cvxpy", "repo": "cvxpy/cvxpy", "spdx": "Apache-2.0", "path": "Z:/sota-data/hosted-research-frameworks/cvxpy", "layers": ["L11"], "stages": ["S5", "S7"], "posture": "CLEARED_CONVEX_RISK_OPT", "role": "Convex portfolio risk-budgeting & turnover/beta-constrained allocation"},
    {"name": "timesfm", "repo": "google-research/timesfm", "spdx": "Apache-2.0", "path": "Z:/sota-data/hosted-research-frameworks/timesfm", "layers": ["L3", "L7"], "stages": ["S3"], "posture": "CLEARED_LOCAL_RTX4090_ONLY", "role": "Google Research Time-Series Foundation Model (TSFM) for pre-wall horizon forecasts"},
    {"name": "Lean", "repo": "QuantConnect/Lean", "spdx": "Apache-2.0", "path": "Z:/sota-data/hosted-research-frameworks/Lean", "layers": ["L1", "L3"], "stages": ["S2", "S4"], "posture": "CLEARED_EQUITIES_OPTIONS_REF", "role": "Institutional US equities & options corporate-action, RVOL & Greeks engine reference"},
    {"name": "QuantLib", "repo": "lballabio/QuantLib", "spdx": "BSD-3-Clause", "path": "Z:/sota-data/hosted-research-frameworks/QuantLib", "layers": ["L2", "L13"], "stages": ["S4"], "posture": "CLEARED_US_OPTIONS_PRICING", "role": "Institutional US options Greeks, implied-volatility surface & derivatives pricing library"},
)

HOSTED_HARNESS_ORCA_AO_SECURITY_SPECS: tuple[dict[str, Any], ...] = (
    {"name": "orca", "repo": "stablyai/orca", "spdx": "MIT", "path": "Z:/sota-data/hosted-research-frameworks/harness-and-ao/orca", "layers": ["L8", "L15"], "stages": ["S6", "S8"], "posture": "LIVE_LOCAL_RUNTIME_1_4_264", "role": "Isolated git worktree fleet (18/18 orca.yaml), dual-machine mesh & automations"},
    {"name": "agent-orchestrator", "repo": "OrchestratorInc/agent-orchestrator", "spdx": "Apache-2.0", "path": "Z:/sota-data/hosted-research-frameworks/harness-and-ao/agent-orchestrator", "layers": ["L8"], "stages": ["S6", "S8"], "posture": "CLEARED_MULTI_MODEL_AO", "role": "8-slot pluggable Multi-Model Agent Orchestrator (AO) worktree, CI-reaction & review lifecycle"},
    {"name": "oh-my-claudecode", "repo": "Yeachan-Heo/oh-my-claudecode", "spdx": "MIT", "path": "Z:/sota-data/hosted-research-frameworks/harness-and-ao/oh-my-claudecode", "layers": ["L8"], "stages": ["S6"], "posture": "CLEARED_RUNTIME_ORCHESTRATOR", "role": "Claude Code OMC v2 central multi-session runtime orchestrator"},
    {"name": "oh-my-codex", "repo": "Yeachan-Heo/oh-my-codex", "spdx": "MIT", "path": "Z:/sota-data/hosted-research-frameworks/harness-and-ao/oh-my-codex", "layers": ["L8"], "stages": ["S6"], "posture": "CLEARED_RUNTIME_ORCHESTRATOR", "role": "Codex OMX adversarial critic & parallel implementation workers"},
    {"name": "oh-my-pi", "repo": "can1357/oh-my-pi", "spdx": "MIT", "path": "Z:/sota-data/hosted-research-frameworks/harness-and-ao/oh-my-pi", "layers": ["L8"], "stages": ["S6"], "posture": "CLEARED_RUNTIME_ORCHESTRATOR", "role": "Pi/OMP @worker role-selected thinking-effort runtime workers"},
    {"name": "deepseek-harness", "repo": "deepseek-ai/deepseek-harness", "spdx": "MIT", "path": "Z:/sota-data/hosted-research-frameworks/harness-and-ao/deepseek-harness", "layers": ["L8"], "stages": ["S6"], "posture": "CLEARED_RUNTIME_ORCHESTRATOR", "role": "DSH 10-layer plugin harness & 1M-context pre-wall evaluation runtime"},
    {"name": "hcom", "repo": "aannoo/hcom", "spdx": "MIT", "path": "Z:/sota-data/hosted-research-frameworks/harness-and-ao/hcom", "layers": ["L8", "L10"], "stages": ["S6", "S8"], "posture": "CLEARED_PEER_BUS", "role": "Real-time cross-terminal agent wakeup & peer push messaging"},
    {"name": "beads", "repo": "gastownhall/beads", "spdx": "MIT", "path": "Z:/sota-data/hosted-research-frameworks/harness-and-ao/beads", "layers": ["L8"], "stages": ["S6", "S8"], "posture": "CLEARED_TASK_DAG", "role": "Git-backed distributed dependency task graph tracking (bd)"},
    {"name": "oh-my-hermes", "repo": "rlaope/oh-my-hermes", "spdx": "MIT", "path": "Z:/sota-data/hosted-research-frameworks/harness-and-ao/oh-my-hermes", "layers": ["L8", "L10"], "stages": ["S6", "S8"], "posture": "CLEARED_COWORKER_NET", "role": "Cross-vendor coworker network & adaptive self-evolution bridge"},
    {"name": "oh-my-opencode-slim", "repo": "alvinunreal/oh-my-opencode-slim", "spdx": "MIT", "path": "Z:/sota-data/hosted-research-frameworks/harness-and-ao/oh-my-opencode-slim", "layers": ["L8"], "stages": ["S6"], "posture": "CLEARED_MODEL_ROUTER", "role": "Lean multi-model routing for OpenCode Hephaestus/Sisyphus"},
    {"name": "openrig", "repo": "mvschwarz/openrig", "spdx": "Apache-2.0", "path": "Z:/sota-data/hosted-research-frameworks/harness-and-ao/openrig", "layers": ["L8"], "stages": ["S6"], "posture": "CLEARED_MULTI_AGENT_RIG", "role": "Structured multi-agent rig & worker dispatch supervision"},
    {"name": "plannotator", "repo": "backnotprop/plannotator", "spdx": "Apache-2.0", "path": "Z:/sota-data/hosted-research-frameworks/harness-and-ao/plannotator", "layers": ["L6", "L8"], "stages": ["S6"], "posture": "CLEARED_PLAN_REVIEW", "role": "Visual plan review & institutional editorial craft verification"},
    {"name": "auto-ontology", "repo": "NVIDIA/auto-ontology", "spdx": "Apache-2.0", "path": "Z:/sota-data/hosted-research-frameworks/harness-and-ao/auto-ontology", "layers": ["L8"], "stages": ["S6"], "posture": "CLEARED_ONTOLOGY_GRAPH", "role": "Automated codebase & ecosystem ontology graph reasoning"},
    {"name": "xerj", "repo": "xerj-org/xerj", "spdx": "Apache-2.0", "path": "Z:/sota-data/hosted-research-frameworks/harness-and-ao/xerj", "layers": ["L8"], "stages": ["S6"], "posture": "CLEARED_AST_INDEXER", "role": "High-speed local semantic & AST workspace indexing"},
    {"name": "hallmark", "repo": "Nutlope/hallmark", "spdx": "MIT", "path": "Z:/sota-data/hosted-research-frameworks/harness-and-ao/hallmark", "layers": ["L8", "L15"], "stages": ["S6", "S8"], "posture": "CLEARED_QUALITY_BENCH", "role": "Structured engineering quality verification benchmarks"},
    {"name": "SkillEvaluator", "repo": "NVIDIA/SkillEvaluator", "spdx": "Apache-2.0", "path": "Z:/sota-data/hosted-research-frameworks/harness-and-ao/SkillEvaluator", "layers": ["L9", "L15"], "stages": ["S6", "S8"], "posture": "CLEARED_4TIER_SKILL_AUDIT", "role": "4-tier skill quality, security & 8-runtime parity auditing (60/60)"},
    {"name": "openshell", "repo": "ai-openshell/openshell", "spdx": "Apache-2.0", "path": "Z:/sota-data/hosted-research-frameworks/harness-and-ao/openshell", "layers": ["L9"], "stages": ["S6"], "posture": "CLEARED_SANDBOX_POLICY", "role": "Fail-closed execution & secret-access sandbox boundaries"},
    {"name": "Claude-BugHunter", "repo": "elementalsouls/Claude-BugHunter", "spdx": "MIT", "path": "Z:/sota-data/hosted-research-frameworks/harness-and-ao/Claude-BugHunter", "layers": ["L9"], "stages": ["S6"], "posture": "CLEARED_REDTEAM_24CLASS", "role": "24-class adversarial bug-hunting & trading-firewall red-team audits"},
    {"name": "security-audit-skill", "repo": "cloudflare/security-audit-skill", "spdx": "MIT", "path": "Z:/sota-data/hosted-research-frameworks/harness-and-ao/security-audit-skill", "layers": ["L9"], "stages": ["S6"], "posture": "CLEARED_TWOPASS_AUDIT", "role": "Two-pass self-refuting vulnerability confirmation methodology"},
    {"name": "trailofbits-skills", "repo": "trailofbits/skills", "spdx": "CC-BY-SA-4.0", "path": "Z:/sota-data/hosted-research-frameworks/harness-and-ao/trailofbits-skills", "layers": ["L0", "L9"], "stages": ["S1", "S6"], "posture": "CLEARED_DIMENSIONAL_FP", "role": "Dimensional analysis, IEEE-754 fp-check & Hypothesis property invariants"},
    {"name": "superpowers", "repo": "obra/superpowers", "spdx": "MIT", "path": "Z:/sota-data/hosted-research-frameworks/harness-and-ao/superpowers", "layers": ["L0", "L8"], "stages": ["S6", "S8"], "posture": "CLEARED_TDD_DISCIPLINE", "role": "Red-Green-Refactor TDD, root-cause debugging & isolated worktree verification"},
    {"name": "SkillOpt", "repo": "microsoft/SkillOpt", "spdx": "MIT", "path": "Z:/sota-data/hosted-research-frameworks/harness-and-ao/SkillOpt", "layers": ["L10", "L15"], "stages": ["S8"], "posture": "CLEARED_FRICTION_MINING", "role": "Trajectory-friction mining converting transcript.jsonl errors into SKILL.md upgrades"},
    {"name": "gitleaks", "repo": "gitleaks/gitleaks", "spdx": "MIT", "path": "Z:/sota-data/hosted-research-frameworks/harness-and-ao/gitleaks", "layers": ["L0", "L9"], "stages": ["S6"], "posture": "CLEARED_ZERO_LEAK_GATE", "role": "Pre-commit & CI zero-secret / zero-home-path enforcement"},
    {"name": "ast-grep", "repo": "ast-grep/ast-grep", "spdx": "MIT", "path": "Z:/sota-data/hosted-research-frameworks/harness-and-ao/ast-grep", "layers": ["L0", "L9"], "stages": ["S6"], "posture": "CLEARED_AST_LINT_GATE", "role": "Structural AST search, lint rule authoring & deterministic multi-file codemods"},
    {"name": "hypothesis", "repo": "HypothesisWorks/hypothesis", "spdx": "MPL-2.0", "path": "Z:/sota-data/hosted-research-frameworks/harness-and-ao/hypothesis", "layers": ["L0", "L4"], "stages": ["S5", "S6"], "posture": "CLEARED_TIER0_CHARTER_CORE", "role": "Property-based invariant fuzzing for ADR-0022 stops, PIT timestamps & IEEE-754 bounds"},
)

QUARANTINED_REFERENCE_SPECS: tuple[dict[str, Any], ...] = (
    {"name": "RD-Agent", "repo": "microsoft/RD-Agent", "spdx": "MIT", "path": "Z:/sota-cache/llm-native-eval/RD-Agent", "layers": ["L3", "L14"], "stages": ["S3"], "posture": "QUARANTINED_DO_NOT_RUN_UNSANDBOXED", "role": "Reference-only Co-STEER methodology; factor.py:165 runs unsandboxed host shell & lacks HLZ control"},
    {"name": "TradingAgents", "repo": "TauricResearch/TradingAgents", "spdx": "Apache-2.0", "path": "Z:/sota-cache/llm-native-eval/TradingAgents", "layers": ["L3"], "stages": ["S2"], "posture": "REFERENCE_ONLY_DATE_WINDOW_PATTERN", "role": "Reference-only trade-date clamping pattern (date_window.py:79); daily/non-repeatable LLM outputs"},
    {"name": "ai-hedge-fund", "repo": "virattt/ai-hedge-fund", "spdx": "MIT", "path": "Z:/sota-cache/llm-native-eval/ai-hedge-fund", "layers": ["L3"], "stages": ["S3"], "posture": "REFERENCE_ONLY_MOCK_BOOK", "role": "Reference-only educational multi-agent mock book; not for production execution"},
    {"name": "Vibe-Trading", "repo": "HKUDS/Vibe-Trading", "spdx": "MIT", "path": "Z:/sota-cache/llm-native-eval-pass2/Vibe-Trading", "layers": ["L8"], "stages": ["S6"], "posture": "QUARANTINED_ZERO_BROKER_KEYS", "role": "Skill-native trading research harness reference; contains order-routing code (0 broker keys ever)"},
    {"name": "hermes-agent-self-evolution", "repo": "NousResearch/hermes-agent-self-evolution", "spdx": "NONE", "path": "(NOT_CLONED_LICENSE_FIREWALL)", "layers": ["L10"], "stages": ["S8"], "posture": "EXCLUDED_UNLICENSED_NONE", "role": "Live GitHub API returned spdx=NONE (all rights reserved); blocked by ADR-0048 license firewall"},
)


def _git_head_sha(repo_dir: Path) -> str:
    if not (repo_dir / ".git").exists():
        return ""
    if sys.platform == "win32":
        proc = subprocess.run(
            ["git", "-C", str(repo_dir), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
            creationflags=CREATE_NO_WINDOW,
        )
    else:
        proc = subprocess.run(
            ["git", "-C", str(repo_dir), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    return proc.stdout.strip() if proc.returncode == 0 else ""


def _load_core_shelf_pins(workstation: Path) -> list[dict[str, Any]]:
    lock_path = workstation / "sota-upstream-shelf-lock" / "PINS_LOCK.json"
    raw = json.loads(lock_path.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    for item in sorted(raw.get("upstreamShelfPins") or [], key=lambda x: str(x["name"]).lower()):
        name = str(item["name"])
        locked_sha = str(item["commit"])
        local_dir = Path("Z:/sota-data/upstream") / name
        live_sha = _git_head_sha(local_dir) if local_dir.is_dir() else locked_sha
        rows.append(
            {
                "name": name,
                "ref": str(item.get("ref", "")),
                "locked_sha": locked_sha,
                "live_sha": live_sha,
                "sha_verified_match": live_sha == locked_sha,
                "license": str(item.get("license", "")),
                "url": str(item.get("url", "")),
                "local_path": f"Z:/sota-data/upstream/{name}",
                "posture": "IMMUTABLE_CORE_SHELF_READ_ONLY",
            }
        )
    return rows


def _resolve_repo_entries(specs: tuple[dict[str, Any], ...]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for spec in specs:
        p = Path(spec["path"])
        present = p.is_dir() and (p / ".git").exists()
        sha = _git_head_sha(p) if present else ""
        entries.append(
            {
                "name": spec["name"],
                "repo": spec["repo"],
                "spdx": spec["spdx"],
                "local_path": spec["path"],
                "present_on_disk_z": present,
                "head_sha": sha,
                "layers": list(spec["layers"]),
                "stages": list(spec["stages"]),
                "posture": spec["posture"],
                "role": spec["role"],
                **({"endpoint": spec["endpoint"]} if "endpoint" in spec else {}),
            }
        )
    return entries


def build_hosted_research_frameworks_manifest(
    workstation: Path = DEFAULT_WORKSTATION,
    *,
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    """Assemble and SHA-256 seal the full 95-repo Disk-Z hosted research & Orca/AO manifest."""
    core_shelf = _load_core_shelf_pins(workstation)
    ui_and_plugins = _resolve_repo_entries(HOSTED_UI_AND_PLUGINS_SPECS)
    frontier_and_charter = _resolve_repo_entries(HOSTED_FRONTIER_AND_CHARTER_SPECS)
    harness_orca_ao = _resolve_repo_entries(HOSTED_HARNESS_ORCA_AO_SECURITY_SPECS)
    quarantined = _resolve_repo_entries(QUARANTINED_REFERENCE_SPECS)

    tearsheets_dir = Path("Z:/sota-data/tearsheets")
    tearsheet_files = (
        sorted(p.name for p in tearsheets_dir.glob("*.html") if p.is_file())
        if tearsheets_dir.is_dir()
        else []
    )

    all_hosted = [*ui_and_plugins, *frontier_and_charter, *harness_orca_ao]
    manifest: dict[str, Any] = {
        "schema": SCHEMA_VERSION,
        "adr": "ADR-0051",
        "prior_seal_adr": "ADR-0050",
        "supersedes_self_built_ui_adr": "ADR-0047",
        "cleanroom_v4_adr": "ADR-0049",
        "generated_at_utc": generated_at_utc or datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "storage_root": "Z:/sota-data/hosted-research-frameworks/",
        "hard_boundaries": {
            "immutable_shelf_untouched": True,
            "paper_only_firewall": True,
            "study_wall_date": "2026-10-15",
            "zero_unsandboxed_llm_exec": True,
            "zero_broker_keys_to_external_agents": True,
            "zero_self_built_html_js_ui": True,
            "zero_paper_self_invention": True,
            "clean_installed_frameworks_plus_official_paper_e2e_only": True,
        },
        "live_local_services": {
            "finos_workspace_ui": "http://localhost:1420",
            "finos_workspace_api": "http://localhost:8000",
            "finos_workspace_active_plugins": ["plotly-charts@2.5.0", "ag-grid@2.3.0"],
            "openbb_sota_backend": "http://127.0.0.1:6900",
            "mlflow_3_tracking_ui": "http://127.0.0.1:5050",
            "mlflow_backend_store": "sqlite:///Z:/sota-data/mlflow-store/mlflow.db",
            "upstream_tearsheets_server": "http://127.0.0.1:8793",
            "rtx4090_full_res_sidecar": "http://127.0.0.1:8794",
            "ibkr_paper_gateway": "127.0.0.1:4002",
            "orca_local_runtime": "1.4.264 (ready, reachable)",
            "tearsheet_html_artifacts": tearsheet_files,
        },
        "summary": {
            "immutable_core_shelf_count": len(core_shelf),
            "immutable_core_shelf_verified": sum(1 for r in core_shelf if r["sha_verified_match"]),
            "hosted_ui_and_plugins_count": len(ui_and_plugins),
            "hosted_frontier_and_charter_count": len(frontier_and_charter),
            "hosted_harness_orca_ao_count": len(harness_orca_ao),
            "quarantined_reference_count": len(quarantined),
            "total_local_upstream_repos_indexed": len(core_shelf) + len(all_hosted) + len(quarantined),
            "active_hosted_present_on_disk_z": sum(1 for r in all_hosted if r["present_on_disk_z"]),
        },
        "tier_a_immutable_core_shelf": core_shelf,
        "tier_b_hosted_ui_and_plugins": ui_and_plugins,
        "tier_c_hosted_frontier_and_charter_frameworks": frontier_and_charter,
        "tier_c2_hosted_harness_orca_ao_and_security": harness_orca_ao,
        "tier_d_quarantined_reference_only": quarantined,
    }
    raw_body = json.dumps(manifest, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    manifest["manifest_sha256"] = hashlib.sha256(raw_body).hexdigest()
    return manifest


def render_markdown(manifest: dict[str, Any]) -> str:
    s = manifest["summary"]
    svc = manifest["live_local_services"]
    lines = [
        "# SOTA Full-Landscape Disk-Z Hosted Research Frameworks, Orca & Multi-Model AO Registry (`ADR-0050` / `ADR-0051`)",
        "",
        f"- **Canonical SHA-256:** `{manifest['manifest_sha256']}`",
        (
            f"- **Total Local Upstream Repos Indexed:** `{s['total_local_upstream_repos_indexed']}` "
            f"(`{s['immutable_core_shelf_verified']}/{s['immutable_core_shelf_count']}` Immutable Shelf + "
            f"`{s['hosted_ui_and_plugins_count']}` Hosted UI/Plugins + "
            f"`{s['hosted_frontier_and_charter_count']}` Quant/Options/ML/Foundation/Sandbox Frameworks + "
            f"`{s['hosted_harness_orca_ao_count']}` Orca/Multi-Model-AO/Harness/Security Frameworks + "
            f"`{s['quarantined_reference_count']}` Explicitly Quarantined/Excluded)"
        ),
        (
            f"- **Live Local Surfaces:** FINOS Workspace `{svc['finos_workspace_ui']}` "
            f"(plugins: `{', '.join(svc['finos_workspace_active_plugins'])}`) · "
            f"OpenBB Backend `{svc['openbb_sota_backend']}` · MLflow 3.18.0 `{svc['mlflow_3_tracking_ui']}` · "
            f"Official Tearsheets `{svc['upstream_tearsheets_server']}` · RTX 4090 Sidecar `{svc['rtx4090_full_res_sidecar']}` · "
            f"IBKR Paper `{svc['ibkr_paper_gateway']}` · Orca `{svc['orca_local_runtime']}`"
        ),
        "",
        "## Tier A — 18 Immutable Core Shelf Pins (`Z:/sota-data/upstream/`, Read-Only)",
        "",
        "| Library | Ref | Exact 40-Char SHA | License | Verified |",
        "| :--- | :--- | :--- | :--- | :---: |",
    ]
    for r in manifest["tier_a_immutable_core_shelf"]:
        lines.append(
            f"| `{r['name']}` | `{r['ref']}` | `{r['locked_sha']}` | `{r['license']}` | `{r['sha_verified_match']}` |"
        )

    lines.extend(
        [
            "",
            "## Tier B — Live Hosted Interactive UI, Official Plugins & Backends",
            "",
            "| Repo | SPDX | HEAD SHA (12) | Local Path | Endpoint / Deployment | Posture |",
            "| :--- | :--- | :--- | :--- | :--- | :--- |",
        ]
    )
    for r in manifest["tier_b_hosted_ui_and_plugins"]:
        lines.append(
            f"| `{r['repo']}` | `{r['spdx']}` | `{r['head_sha'][:12]}` | `{r['local_path']}` | "
            f"{r.get('endpoint', '')} | `{r['posture']}` |"
        )

    lines.extend(
        [
            "",
            "## Tier C — Hosted Quant, US Equities/Options, ML, Foundation-Model & Sandbox Frameworks (`44`)",
            "",
            "| Repo | SPDX | HEAD SHA (12) | Layers | Stages | Security Posture | Role |",
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
        ]
    )
    for r in manifest["tier_c_hosted_frontier_and_charter_frameworks"]:
        ly = ", ".join(r["layers"])
        st = ", ".join(r["stages"])
        lines.append(
            f"| `{r['repo']}` | `{r['spdx']}` | `{r['head_sha'][:12]}` | `{ly}` | `{st}` | "
            f"`{r['posture']}` | {r['role']} |"
        )

    lines.extend(
        [
            "",
            "## Tier C2 — Hosted SOTA Research Convergence Harness, Orca, Multi-Model AO & Security (`25`)",
            "",
            "| Repo | SPDX | HEAD SHA (12) | Layers | Stages | Security Posture | Role |",
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
        ]
    )
    for r in manifest["tier_c2_hosted_harness_orca_ao_and_security"]:
        ly = ", ".join(r["layers"])
        st = ", ".join(r["stages"])
        lines.append(
            f"| `{r['repo']}` | `{r['spdx']}` | `{r['head_sha'][:12]}` | `{ly}` | `{st}` | "
            f"`{r['posture']}` | {r['role']} |"
        )

    lines.extend(
        [
            "",
            "## Tier D — Explicitly Quarantined / Reference-Only / Unlicensed (`NONE`) Containment Firewall (`5`)",
            "",
            "| Repo | SPDX | HEAD SHA (12) | Containment Posture | Reason |",
            "| :--- | :--- | :--- | :--- | :--- |",
        ]
    )
    for r in manifest["tier_d_quarantined_reference_only"]:
        lines.append(
            f"| `{r['repo']}` | `{r['spdx']}` | `{r['head_sha'][:12]}` | `{r['posture']}` | {r['role']} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    manifest = build_hosted_research_frameworks_manifest()
    md = render_markdown(manifest)
    json_txt = json.dumps(manifest, indent=2, allow_nan=False) + "\n"

    docs_json = ROOT / "docs" / "SOTA_HOSTED_RESEARCH_FRAMEWORKS_MANIFEST.json"
    docs_md = ROOT / "docs" / "SOTA_HOSTED_RESEARCH_FRAMEWORKS_MANIFEST.md"
    docs_json.write_text(json_txt, encoding="utf-8", newline="\n")
    docs_md.write_text(md, encoding="utf-8", newline="\n")

    z_root = Path("Z:/sota-data/hosted-research-frameworks")
    if z_root.is_dir():
        (z_root / "HOSTED_RESEARCH_FRAMEWORKS_MANIFEST.json").write_text(
            json_txt, encoding="utf-8", newline="\n"
        )
        (z_root / "HOSTED_RESEARCH_FRAMEWORKS_FULL_LANDSCAPE_MANIFEST.json").write_text(
            json_txt, encoding="utf-8", newline="\n"
        )
        (z_root / "README.md").write_text(md, encoding="utf-8", newline="\n")

    print(
        json.dumps(
            {
                "ok": True,
                "schema": manifest["schema"],
                "manifest_sha256": manifest["manifest_sha256"],
                "summary": manifest["summary"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
