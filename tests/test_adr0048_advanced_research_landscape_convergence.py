from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]


def _load_manifest_mod() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "build_full_landscape_layer_manifest",
        ROOT / "scripts" / "build_full_landscape_layer_manifest.py",
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_adr0048_v3_manifest_binds_live_verified_llm_quant_frontier_and_blocks_quarantined() -> None:
    mod = _load_manifest_mod()
    manifest = mod.build_full_landscape_layer_manifest(generated_at_utc="2026-11-21T02:00:00Z")

    assert manifest["schema"] == "sota.full-landscape-resolute-layer-pin-manifest.v3"
    assert manifest["advanced_research_landscape_adr"] == "ADR-0048"
    assert manifest["hosted_platform_adr"] == "ADR-0047"

    all_mapped = {
        r["repo"]
        for ly in manifest["layers"]
        for r in (*ly["starred_sota_repos"], *ly["beyond_starred_sota_repos"])
    }

    expected_active_licensed = (
        "nautechsystems/nautilus_agents",
        "anthropics/financial-services",
        "waylonli/FINSABER",
        "microsoft/MarS",
        "peernagy/LOBS5",
        "AI4Finance-Foundation/FinRobot",
        "HKUDS/Vibe-Trading",
        "aliyun/qwen-dianjin",
        "The-FinAI/Fino1",
        "The-FinAI/FinBen",
        "PriorLabs/TabPFN",
        "amazon-science/chronos-forecasting",
        "SalesforceAIResearch/uni2ts",
        "online-ml/river",
        "scikit-learn-contrib/MAPIE",
        "py-why/dowhy",
        "massive-com/mcp_massive",
        "BrainDAO/mcp-polymarket",
        "FreedomIntelligence/TwinMarket",
        "shiyu-coder/Kronos",
        "openbq-org/finos-workspace",
    )
    for slug in expected_active_licensed:
        assert slug in all_mapped, f"Expected verified frontier anchor missing from v3 manifest: {slug}"

    # Quarantined unlicensed / archived / GPL-3.0 repos must NOT appear as active layer pins
    forbidden_quarantined = (
        "QuantaAlpha/QuantaAlpha",
        "SUFE-AIFLM-Lab/Fin-R1",
        "FinStep-AI/Alpha-R1",
        "horizon-llm/AlphaQuanter",
        "hansbuehler/deephedging",
        "OpenBB-finance/agents-for-openbb",
        "Polymarket/agents",
        "jpmorganchase/abides-jpmc-public",
        "hummingbot/mcp",
    )
    for bad in forbidden_quarantined:
        assert bad not in all_mapped, f"Quarantined repo leaked into v3 manifest: {bad}"
