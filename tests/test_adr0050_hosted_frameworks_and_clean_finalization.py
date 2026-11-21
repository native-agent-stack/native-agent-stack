from __future__ import annotations

import hashlib
import importlib.util
import json
import re
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, rel: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_HOSTED = _load(
    "build_hosted_research_frameworks_manifest",
    "scripts/build_hosted_research_frameworks_manifest.py",
)
_SYNC = _load(
    "sync_tier0_harness_and_master_adrs",
    "scripts/sync_tier0_harness_and_master_adrs.py",
)


def test_adr0050_hosted_research_frameworks_manifest_is_sealed_and_zero_leak() -> None:
    mf_path = ROOT / "docs" / "SOTA_HOSTED_RESEARCH_FRAMEWORKS_MANIFEST.json"
    md_path = ROOT / "docs" / "SOTA_HOSTED_RESEARCH_FRAMEWORKS_MANIFEST.md"
    assert mf_path.is_file()
    assert md_path.is_file()

    data = json.loads(mf_path.read_text(encoding="utf-8"))
    body = {k: v for k, v in data.items() if k != "manifest_sha256"}
    expected_sha = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()
    assert data["manifest_sha256"] == expected_sha
    assert data["adr"] == "ADR-0051"
    assert data["prior_seal_adr"] == "ADR-0050"
    assert data["summary"]["immutable_core_shelf_count"] == 18
    assert data["summary"]["hosted_ui_and_plugins_count"] == 3
    assert data["summary"]["hosted_frontier_and_charter_count"] == 44
    assert data["summary"]["hosted_harness_orca_ao_count"] == 25
    assert data["summary"]["quarantined_reference_count"] == 5
    assert data["summary"]["total_local_upstream_repos_indexed"] == 95
    assert data["live_local_services"]["mlflow_3_tracking_ui"] == "http://127.0.0.1:5050"
    assert "1.4." in data["live_local_services"]["orca_local_runtime"]

    # Verify mandatory safety boundaries
    hb = data["hard_boundaries"]
    assert hb["immutable_shelf_untouched"] is True
    assert hb["paper_only_firewall"] is True
    assert hb["study_wall_date"] == "2026-10-15"
    assert hb["zero_unsandboxed_llm_exec"] is True
    assert hb["zero_broker_keys_to_external_agents"] is True
    assert hb["zero_self_built_html_js_ui"] is True
    assert hb["zero_paper_self_invention"] is True
    assert hb["clean_installed_frameworks_plus_official_paper_e2e_only"] is True

    # Verify Orca & Multi-Model AO are actively hosted in Tier C2
    tier_c2_repos = {r["repo"] for r in data["tier_c2_hosted_harness_orca_ao_and_security"]}
    for required_ao in (
        "stablyai/orca",
        "OrchestratorInc/agent-orchestrator",
        "Yeachan-Heo/oh-my-claudecode",
        "Yeachan-Heo/oh-my-codex",
        "can1357/oh-my-pi",
        "deepseek-ai/deepseek-harness",
        "NVIDIA/SkillEvaluator",
        "ai-openshell/openshell",
    ):
        assert required_ao in tier_c2_repos

    # Verify quarantined/unlicensed repos are strictly in Tier D, never Tier C or C2
    tier_c_repos = {r["repo"] for r in data["tier_c_hosted_frontier_and_charter_frameworks"]}
    tier_d_repos = {r["repo"] for r in data["tier_d_quarantined_reference_only"]}
    for q in (
        "microsoft/RD-Agent",
        "TauricResearch/TradingAgents",
        "virattt/ai-hedge-fund",
        "HKUDS/Vibe-Trading",
        "NousResearch/hermes-agent-self-evolution",
    ):
        assert q in tier_d_repos
        assert q not in tier_c_repos
        assert q not in tier_c2_repos

    combined = json.dumps(data) + md_path.read_text(encoding="utf-8")
    leak_rx = re.compile(
        r"(C:\\U"
        + r"sers|/"
        + r"Users/|/"
        + r"home/|PA[0-9A-Z]{8,}|DU[0-9]{7,}|AK[0-9A-Z]{16,}|PK[0-9A-Z]{16,})"
    )
    assert not leak_rx.search(combined)


def test_adr0050_canonical_single_rule_charter_parity_without_bloat(tmp_path: Path) -> None:
    charter_path = ROOT / "docs" / "cleanroom" / "TIER0_CANONICAL_CHARTER.md"
    assert charter_path.is_file()
    charter_txt = charter_path.read_text(encoding="utf-8")
    assert _SYNC.is_canonical_tier0_charter(charter_txt)

    targets = [
        tmp_path / ".gemini" / "GEMINI.md",
        tmp_path / ".claude" / "CLAUDE.md",
        tmp_path / ".codex" / "AGENTS.md",
        tmp_path / ".config" / "opencode" / "AGENTS.md",
        tmp_path / ".dsh" / "AGENTS.md",
        tmp_path / ".omp" / "agent" / "AGENTS.md",
    ]
    for p in targets:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(charter_txt, encoding="utf-8")

    # Even with obsolete agy plugin file absent, canonical charter parity must pass 7/7
    parity = _SYNC.check_tier0_harness_md_parity(tmp_path)
    assert parity["all_synced"] is True
    assert parity["synced_count"] == 7
    assert parity["canonical_charter_mode"] is True
    assert parity["drifted"] == []

    # Sync must preserve the concise canonical charter verbatim (never re-inject legacy block)
    res = _SYNC.sync_tier0_harness_md_files(tmp_path)
    assert res["gemini_global"] == "unchanged"
    assert res["agy_plugin_rules"] == "superseded_by_canonical_charter"
    assert targets[0].read_text(encoding="utf-8") == charter_txt


def test_canonical_charter_sync_upgrades_older_charter_idempotently(tmp_path: Path) -> None:
    charter_path = ROOT / "docs" / "cleanroom" / "TIER0_CANONICAL_CHARTER.md"
    charter_txt = charter_path.read_text(encoding="utf-8")
    older_charter = (
        "# Tier-0 Engineering & Quantitative Charter (Canonical Single Rule)\n\n"
        "## 1. Upstream-Only Mandate (Zero Self-Built Frameworks)\n"
        "- Old charter missing zero paper self-invention clause.\n"
    )
    targets = [
        tmp_path / ".gemini" / "GEMINI.md",
        tmp_path / ".claude" / "CLAUDE.md",
        tmp_path / ".codex" / "AGENTS.md",
        tmp_path / ".config" / "opencode" / "AGENTS.md",
        tmp_path / ".dsh" / "AGENTS.md",
        tmp_path / ".omp" / "agent" / "AGENTS.md",
    ]
    for p in targets:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(older_charter, encoding="utf-8")

    res1 = _SYNC.sync_tier0_harness_md_files(tmp_path)
    assert all(
        res1[k] == "updated"
        for k in (
            "gemini_global",
            "claude_global",
            "codex_global",
            "opencode_global",
            "dsh_global",
            "omp_global",
        )
    )
    parity = _SYNC.check_tier0_harness_md_parity(tmp_path)
    assert parity["all_synced"] is True
    assert parity["canonical_charter_mode"] is True
    for p in targets:
        assert p.read_text(encoding="utf-8") == charter_txt

    res2 = _SYNC.sync_tier0_harness_md_files(tmp_path)
    assert all(
        res2[k] == "unchanged"
        for k in (
            "gemini_global",
            "claude_global",
            "codex_global",
            "opencode_global",
            "dsh_global",
            "omp_global",
        )
    )
