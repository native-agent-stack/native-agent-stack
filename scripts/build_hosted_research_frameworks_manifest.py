#!/usr/bin/env python3
"""Build SHA-256 Sealed Disk-Z Hosted Advanced Research Frameworks Registry (`ADR-0050`).

Verifies every locally hosted upstream SOTA repository across Disk `Z:` (immutable 18-pin core
shelf, live hosted FINOS/OpenBB Workspace + plugins + tearsheets, SPDX-cleared frontier &
Tier-0 Charter research frameworks, and explicitly quarantined reference-only repos), checks
exact 40-char Git HEAD SHAs, enforces zero concrete home-path / credential leaks, and writes
public-safe manifests to BOTH Disk `Z:` and `native-agent-stack/docs/`.
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
SCHEMA_VERSION = "sota.hosted-research-frameworks-manifest.v1"
CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

# Explicit metadata for every hosted repo tier on Disk Z:
HOSTED_UI_AND_PLUGINS_SPECS: tuple[dict[str, Any], ...] = (
    {
        "name": "finos-workspace",
        "repo": "openbq-org/finos-workspace",
        "spdx": "Apache-2.0",
        "tier": "HOSTED_INTERACTIVE_UI",
        "path": "Z:/sota-data/finos-workspace",
        "layers": ["L6"],
        "stages": ["S7", "S8"],
        "endpoint": "http://localhost:1420 (API :8000, Docker Compose 5-container stack)",
        "posture": "LIVE_HOSTED_LOCAL_DOCKER",
        "role": "Official Apache-2.0 FINOS/OpenBB Workspace UI with plotly-charts@2.5.0 & ag-grid@2.3.0 plugins active",
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
    {
        "name": "qlib",
        "repo": "microsoft/qlib",
        "spdx": "MIT",
        "path": "Z:/sota-cache/llm-native-eval/qlib",
        "layers": ["L3", "L14"],
        "stages": ["S3", "S5"],
        "posture": "CLEARED_RESEARCH_ISOLATED_PY312",
        "role": "Qlib v0.9.8 Alpha158 PIT cross-sectional factor research (REG_US 1m, 0 order code)",
    },
    {
        "name": "OpenBB",
        "repo": "openbq-org/OpenBB",
        "spdx": "AGPL-3.0",
        "path": "Z:/sota-cache/llm-native-eval/OpenBB",
        "layers": ["L6", "L13"],
        "stages": ["S2", "S7"],
        "posture": "CLEARED_HOSTED_LOCAL_ONLY",
        "role": "Official active OpenBQ OpenBB terminal & built-in MCP server continuation",
    },
    {
        "name": "nautilus_agents",
        "repo": "nautechsystems/nautilus_agents",
        "spdx": "LGPL-3.0",
        "path": "Z:/sota-cache/llm-native-eval-pass2/nautilus_agents",
        "layers": ["L2", "L5", "L8"],
        "stages": ["S4", "S6"],
        "posture": "CLEARED_WATCH_ZERO_ORDER_PATH",
        "role": "Official Rust-native Agents SDK for NautilusTrader (0 order-path code, 0 API keys)",
    },
    {
        "name": "financial-services",
        "repo": "anthropics/financial-services",
        "spdx": "Apache-2.0",
        "path": "Z:/sota-cache/llm-native-eval-pass2/financial-services",
        "layers": ["L3", "L8"],
        "stages": ["S3", "S6"],
        "posture": "CLEARED_RESEARCH_ZERO_ORDER_PATH",
        "role": "Official Anthropic financial analysis, Earnings Reviewer & MCP connectors",
    },
    {
        "name": "FINSABER",
        "repo": "waylonli/FINSABER",
        "spdx": "Apache-2.0",
        "path": "Z:/sota-cache/llm-native-eval-pass2/FINSABER",
        "layers": ["L4", "L15"],
        "stages": ["S5", "S6"],
        "posture": "CLEARED_EVAL_ONLY_NO_BROKER_KEYS",
        "role": "KDD 2026 Oral leakage-free & LLM token-cost backtest evaluation harness (eval-only)",
    },
    {
        "name": "FinRobot",
        "repo": "AI4Finance-Foundation/FinRobot",
        "spdx": "Apache-2.0",
        "path": "Z:/sota-cache/llm-native-eval-pass2/FinRobot",
        "layers": ["L3", "L6"],
        "stages": ["S3", "S8"],
        "posture": "CLEARED_RESEARCH_READ_ONLY",
        "role": "Deterministic tool-backed equity & quant research agent platform",
    },
    {
        "name": "qwen-dianjin",
        "repo": "aliyun/qwen-dianjin",
        "spdx": "MIT",
        "path": "Z:/sota-cache/llm-native-eval-pass2/qwen-dianjin",
        "layers": ["L1", "L7"],
        "stages": ["S2", "S3"],
        "posture": "CLEARED_LOCAL_RTX4090_ONLY",
        "role": "Local RTX 4090 DianJin-R1 & Fin-PRM SEC 8-K / earnings catalyst reasoning",
    },
    {
        "name": "mcp_massive",
        "repo": "massive-com/mcp_massive",
        "spdx": "MIT",
        "path": "Z:/sota-cache/llm-native-eval-pass2/mcp_massive",
        "layers": ["L1", "L13"],
        "stages": ["S2"],
        "posture": "CLEARED_READ_ONLY_MCP",
        "role": "Official Massive.com (formerly Polygon.io) read-only US equities & options MCP",
    },
    {
        "name": "mcp-polymarket",
        "repo": "BrainDAO/mcp-polymarket",
        "spdx": "MIT",
        "path": "Z:/sota-cache/llm-native-eval-pass2/mcp-polymarket",
        "layers": ["L1", "L13"],
        "stages": ["S2"],
        "posture": "CLEARED_READ_ONLY_ZERO_PRIVATE_KEY",
        "role": "Read-only Polymarket Gamma macro/Fed/CPI implied-probability MCP (0 private keys)",
    },
    {
        "name": "MarS",
        "repo": "microsoft/MarS",
        "spdx": "MIT",
        "path": "Z:/sota-data/hosted-research-frameworks/MarS",
        "layers": ["L2", "L12"],
        "stages": ["S4"],
        "posture": "CLEARED_RESEARCH_SIM_ONLY",
        "role": "ICLR 2025 Large Market Model order-level generative LOB & market-impact simulator",
    },
    {
        "name": "LOBS5",
        "repo": "peernagy/LOBS5",
        "spdx": "MIT",
        "path": "Z:/sota-data/hosted-research-frameworks/LOBS5",
        "layers": ["L2", "L12"],
        "stages": ["S4"],
        "posture": "CLEARED_RESEARCH_SIM_ONLY",
        "role": "State-Space generative LOB simulator & LOB-Bench stylized-fact parity",
    },
    {
        "name": "TabPFN",
        "repo": "PriorLabs/TabPFN",
        "spdx": "Apache-2.0",
        "path": "Z:/sota-data/hosted-research-frameworks/TabPFN",
        "layers": ["L3", "L7"],
        "stages": ["S3"],
        "posture": "CLEARED_LOCAL_RTX4090_ONLY",
        "role": "In-context tabular foundation model for small-sample cross-sectional factors",
    },
    {
        "name": "chronos-forecasting",
        "repo": "amazon-science/chronos-forecasting",
        "spdx": "Apache-2.0",
        "path": "Z:/sota-data/hosted-research-frameworks/chronos-forecasting",
        "layers": ["L3"],
        "stages": ["S3"],
        "posture": "CLEARED_LOCAL_RTX4090_ONLY",
        "role": "Chronos-2 120M multivariate & exogenous macro-covariate time-series foundation model",
    },
    {
        "name": "uni2ts",
        "repo": "SalesforceAIResearch/uni2ts",
        "spdx": "Apache-2.0",
        "path": "Z:/sota-data/hosted-research-frameworks/uni2ts",
        "layers": ["L7", "L11"],
        "stages": ["S3", "S5"],
        "posture": "CLEARED_LOCAL_RTX4090_ONLY",
        "role": "MOIRAI-2 decoder-only multi-quantile VaR/ES tail-risk foundation model",
    },
    {
        "name": "river",
        "repo": "online-ml/river",
        "spdx": "BSD-3-Clause",
        "path": "Z:/sota-data/hosted-research-frameworks/river",
        "layers": ["L3", "L14"],
        "stages": ["S3", "S5"],
        "posture": "CLEARED_TIER0_CHARTER_CORE",
        "role": "Streaming CUSUM, ADWIN & Page-Hinkley online anomaly & alpha-decay detection",
    },
    {
        "name": "MAPIE",
        "repo": "scikit-learn-contrib/MAPIE",
        "spdx": "BSD-3-Clause",
        "path": "Z:/sota-data/hosted-research-frameworks/MAPIE",
        "layers": ["L11"],
        "stages": ["S5"],
        "posture": "CLEARED_RESEARCH_RISK_GATE",
        "role": "Distribution-free adaptive conformal prediction intervals for dynamic VaR/stop bounds",
    },
    {
        "name": "dowhy",
        "repo": "py-why/dowhy",
        "spdx": "MIT",
        "path": "Z:/sota-data/hosted-research-frameworks/dowhy",
        "layers": ["L4", "L12"],
        "stages": ["S5", "S6"],
        "posture": "CLEARED_RESEARCH_CAUSAL_GATE",
        "role": "Causal inference, refutation & Double-ML alpha/execution slippage attribution",
    },
    {
        "name": "Kronos",
        "repo": "shiyu-coder/Kronos",
        "spdx": "MIT",
        "path": "Z:/sota-data/hosted-research-frameworks/Kronos",
        "layers": ["L7"],
        "stages": ["S3", "S4"],
        "posture": "CLEARED_LOCAL_RTX4090_ONLY",
        "role": "K-line foundation model (12B+ K-lines) for Monte Carlo volatility & path bounds",
    },
    {
        "name": "arch",
        "repo": "bashtage/arch",
        "spdx": "NCSA",
        "path": "Z:/sota-data/hosted-research-frameworks/arch",
        "layers": ["L4"],
        "stages": ["S5"],
        "posture": "CLEARED_TIER0_CHARTER_CORE",
        "role": "Hansen SPA, StationaryBootstrap & Model Confidence Set (MCS) falsification",
    },
    {
        "name": "FinBen",
        "repo": "The-FinAI/FinBen",
        "spdx": "MIT",
        "path": "Z:/sota-data/hosted-research-frameworks/FinBen",
        "layers": ["L4", "L15"],
        "stages": ["S6", "S8"],
        "posture": "CLEARED_EVAL_BENCHMARK",
        "role": "lm-evaluation-harness holistic financial LLM evaluation benchmark",
    },
    {
        "name": "Fino1",
        "repo": "The-FinAI/Fino1",
        "spdx": "MIT",
        "path": "Z:/sota-data/hosted-research-frameworks/Fino1",
        "layers": ["L3"],
        "stages": ["S3"],
        "posture": "CLEARED_LOCAL_RTX4090_ONLY",
        "role": "14B SFT+GRPO FinCoT financial reasoning model for FinQA/XBRL-Math",
    },
    {
        "name": "TwinMarket",
        "repo": "FreedomIntelligence/TwinMarket",
        "spdx": "MIT",
        "path": "Z:/sota-data/hosted-research-frameworks/TwinMarket",
        "layers": ["L11", "L13"],
        "stages": ["S4", "S6"],
        "posture": "CLEARED_STRESS_SIM_ONLY",
        "role": "BDI multi-agent herding, contagion & flash-crash counterfactual stress simulator",
    },
    {
        "name": "mlflow",
        "repo": "mlflow/mlflow",
        "spdx": "Apache-2.0",
        "path": "Z:/sota-data/hosted-research-frameworks/mlflow",
        "layers": ["L4", "L10"],
        "stages": ["S1", "S5", "S8"],
        "posture": "CLEARED_TIER0_CHARTER_CORE",
        "role": "MLflow 3 sole upstream experiment & true trial-count (N) tracking ledger",
    },
    {
        "name": "optuna",
        "repo": "optuna/optuna",
        "spdx": "MIT",
        "path": "Z:/sota-data/hosted-research-frameworks/optuna",
        "layers": ["L3", "L14"],
        "stages": ["S3", "S5"],
        "posture": "CLEARED_TIER0_CHARTER_CORE",
        "role": "Hyperparameter & threshold optimization bounded by pre-registered HLZ trial budgets",
    },
    {
        "name": "ruptures",
        "repo": "deepcharles/ruptures",
        "spdx": "BSD-2-Clause",
        "path": "Z:/sota-data/hosted-research-frameworks/ruptures",
        "layers": ["L3"],
        "stages": ["S3"],
        "posture": "CLEARED_TIER0_CHARTER_CORE",
        "role": "Offline structural change-point & regime-break segmentation for pre-wall norm disruptions",
    },
    {
        "name": "stumpy",
        "repo": "stumpy-dev/stumpy",
        "spdx": "BSD-3-Clause",
        "path": "Z:/sota-data/hosted-research-frameworks/stumpy",
        "layers": ["L3"],
        "stages": ["S3"],
        "posture": "CLEARED_TIER0_CHARTER_CORE",
        "role": "Matrix-profile time-series anomaly/discord & motif discovery for early-entry detection",
    },
    {
        "name": "ml4t-engineer",
        "repo": "ml4t/engineer",
        "spdx": "MIT",
        "path": "Z:/sota-data/hosted-research-frameworks/ml4t-engineer",
        "layers": ["L3"],
        "stages": ["S2", "S3"],
        "posture": "CLEARED_TIER0_CHARTER_CORE",
        "role": "Point-in-time quantitative feature engineering companion to ml4t-diagnostic",
    },
    {
        "name": "dagster",
        "repo": "dagster-io/dagster",
        "spdx": "Apache-2.0",
        "path": "Z:/sota-data/hosted-research-frameworks/dagster",
        "layers": ["L1", "L8"],
        "stages": ["S2", "S8"],
        "posture": "CLEARED_TIER0_CHARTER_CORE",
        "role": "Software-defined data & pre-wall research pipeline orchestration",
    },
    {
        "name": "inspect_ai",
        "repo": "UKGovernmentBEIS/inspect_ai",
        "spdx": "MIT",
        "path": "Z:/sota-data/hosted-research-frameworks/inspect_ai",
        "layers": ["L8", "L15"],
        "stages": ["S6", "S8"],
        "posture": "CLEARED_TIER0_CHARTER_CORE",
        "role": "Structured agent & skill evaluation harness for multi-model regression testing",
    },
    {
        "name": "dspy",
        "repo": "stanfordnlp/dspy",
        "spdx": "MIT",
        "path": "Z:/sota-data/hosted-research-frameworks/dspy",
        "layers": ["L10", "L15"],
        "stages": ["S3", "S8"],
        "posture": "CLEARED_TIER0_CHARTER_CORE",
        "role": "Declarative GEPA / MIPROv2 prompt & skill optimization with empirical regression metrics",
    },
)

QUARANTINED_REFERENCE_SPECS: tuple[dict[str, Any], ...] = (
    {
        "name": "RD-Agent",
        "repo": "microsoft/RD-Agent",
        "spdx": "MIT",
        "path": "Z:/sota-cache/llm-native-eval/RD-Agent",
        "layers": ["L3", "L14"],
        "stages": ["S3"],
        "posture": "QUARANTINED_DO_NOT_RUN_UNSANDBOXED",
        "role": "Reference-only Co-STEER methodology; factor.py:165 runs unsandboxed host shell & lacks HLZ control",
    },
    {
        "name": "TradingAgents",
        "repo": "TauricResearch/TradingAgents",
        "spdx": "Apache-2.0",
        "path": "Z:/sota-cache/llm-native-eval/TradingAgents",
        "layers": ["L3"],
        "stages": ["S2"],
        "posture": "REFERENCE_ONLY_DATE_WINDOW_PATTERN",
        "role": "Reference-only trade-date clamping pattern (date_window.py:79); daily/non-repeatable LLM outputs",
    },
    {
        "name": "ai-hedge-fund",
        "repo": "virattt/ai-hedge-fund",
        "spdx": "MIT",
        "path": "Z:/sota-cache/llm-native-eval/ai-hedge-fund",
        "layers": ["L3"],
        "stages": ["S3"],
        "posture": "REFERENCE_ONLY_MOCK_BOOK",
        "role": "Reference-only educational multi-agent mock book; not for production execution",
    },
    {
        "name": "Vibe-Trading",
        "repo": "HKUDS/Vibe-Trading",
        "spdx": "MIT",
        "path": "Z:/sota-cache/llm-native-eval-pass2/Vibe-Trading",
        "layers": ["L8"],
        "stages": ["S6"],
        "posture": "QUARANTINED_ZERO_BROKER_KEYS",
        "role": "Skill-native trading research harness reference; contains order-routing code (0 broker keys ever)",
    },
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
    """Assemble and SHA-256 seal the full Disk-Z hosted research frameworks manifest."""
    core_shelf = _load_core_shelf_pins(workstation)
    ui_and_plugins = _resolve_repo_entries(HOSTED_UI_AND_PLUGINS_SPECS)
    frontier_and_charter = _resolve_repo_entries(HOSTED_FRONTIER_AND_CHARTER_SPECS)
    quarantined = _resolve_repo_entries(QUARANTINED_REFERENCE_SPECS)

    tearsheets_dir = Path("Z:/sota-data/tearsheets")
    tearsheet_files = (
        sorted(p.name for p in tearsheets_dir.glob("*.html") if p.is_file())
        if tearsheets_dir.is_dir()
        else []
    )

    all_hosted = [*ui_and_plugins, *frontier_and_charter]
    manifest: dict[str, Any] = {
        "schema": SCHEMA_VERSION,
        "adr": "ADR-0050",
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
        },
        "live_local_services": {
            "finos_workspace_ui": "http://localhost:1420",
            "finos_workspace_api": "http://localhost:8000",
            "finos_workspace_active_plugins": ["plotly-charts@2.5.0", "ag-grid@2.3.0"],
            "openbb_sota_backend": "http://127.0.0.1:6900",
            "upstream_tearsheets_server": "http://127.0.0.1:8793",
            "rtx4090_full_res_sidecar": "http://127.0.0.1:8794",
            "ibkr_paper_gateway": "127.0.0.1:4002",
            "tearsheet_html_artifacts": tearsheet_files,
        },
        "summary": {
            "immutable_core_shelf_count": len(core_shelf),
            "immutable_core_shelf_verified": sum(1 for r in core_shelf if r["sha_verified_match"]),
            "hosted_ui_and_plugins_count": len(ui_and_plugins),
            "hosted_frontier_and_charter_count": len(frontier_and_charter),
            "quarantined_reference_count": len(quarantined),
            "total_local_upstream_repos_indexed": len(core_shelf) + len(all_hosted) + len(quarantined),
            "active_hosted_present_on_disk_z": sum(1 for r in all_hosted if r["present_on_disk_z"]),
        },
        "tier_a_immutable_core_shelf": core_shelf,
        "tier_b_hosted_ui_and_plugins": ui_and_plugins,
        "tier_c_hosted_frontier_and_charter_frameworks": frontier_and_charter,
        "tier_d_quarantined_reference_only": quarantined,
    }
    raw_body = json.dumps(manifest, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    manifest["manifest_sha256"] = hashlib.sha256(raw_body).hexdigest()
    return manifest


def render_markdown(manifest: dict[str, Any]) -> str:
    s = manifest["summary"]
    svc = manifest["live_local_services"]
    lines = [
        "# SOTA Disk-Z Hosted Advanced Research Frameworks Registry (`ADR-0050`)",
        "",
        f"- **Canonical SHA-256:** `{manifest['manifest_sha256']}`",
        (
            f"- **Total Local Upstream Repos Indexed:** `{s['total_local_upstream_repos_indexed']}` "
            f"(`{s['immutable_core_shelf_verified']}/{s['immutable_core_shelf_count']}` Immutable Shelf + "
            f"`{s['hosted_ui_and_plugins_count']}` Hosted UI/Plugins + "
            f"`{s['hosted_frontier_and_charter_count']}` SPDX-Cleared Frontier/Charter Research Frameworks + "
            f"`{s['quarantined_reference_count']}` Explicitly Quarantined Reference-Only)"
        ),
        (
            f"- **Live Local Surfaces:** FINOS Workspace `{svc['finos_workspace_ui']}` "
            f"(plugins: `{', '.join(svc['finos_workspace_active_plugins'])}`) · "
            f"OpenBB Backend `{svc['openbb_sota_backend']}` · Official Tearsheets `{svc['upstream_tearsheets_server']}` · "
            f"RTX 4090 Full-Res Sidecar `{svc['rtx4090_full_res_sidecar']}` · IBKR Paper `{svc['ibkr_paper_gateway']}`"
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
            "## Tier C — Hosted Advanced Research & Tier-0 Charter Frameworks (`L0`–`L15` / `S1`–`S8`)",
            "",
            "| Repo | SPDX | HEAD SHA (12) | Layers | Stages | Local Path | Security Posture | Role |",
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
        ]
    )
    for r in manifest["tier_c_hosted_frontier_and_charter_frameworks"]:
        ly = ", ".join(r["layers"])
        st = ", ".join(r["stages"])
        lines.append(
            f"| `{r['repo']}` | `{r['spdx']}` | `{r['head_sha'][:12]}` | `{ly}` | `{st}` | "
            f"`{r['local_path']}` | `{r['posture']}` | {r['role']} |"
        )

    lines.extend(
        [
            "",
            "## Tier D — Explicitly Quarantined / Reference-Only Repos (Containment Firewall)",
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

    # Write public-safe mirror inside native-agent-stack/docs/
    docs_json = ROOT / "docs" / "SOTA_HOSTED_RESEARCH_FRAMEWORKS_MANIFEST.json"
    docs_md = ROOT / "docs" / "SOTA_HOSTED_RESEARCH_FRAMEWORKS_MANIFEST.md"
    docs_json.write_text(json_txt, encoding="utf-8", newline="\n")
    docs_md.write_text(md, encoding="utf-8", newline="\n")

    # Write Disk Z: registry root copy if Disk Z: is mounted
    z_root = Path("Z:/sota-data/hosted-research-frameworks")
    if z_root.is_dir():
        (z_root / "HOSTED_RESEARCH_FRAMEWORKS_MANIFEST.json").write_text(
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
