from __future__ import annotations

import hashlib
import importlib.util
import json
import re
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]


def _load_mod() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "build_full_landscape_layer_manifest",
        ROOT / "scripts" / "build_full_landscape_layer_manifest.py",
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_MOD = _load_mod()


def test_full_landscape_manifest_covers_all_16_layers_and_18_exact_pins() -> None:
    manifest = _MOD.build_full_landscape_layer_manifest(generated_at_utc="2026-11-21T00:00:00Z")
    assert manifest["summary"]["total_layers"] == 16
    assert manifest["summary"]["active_operational_layers"] == 11
    assert manifest["summary"]["institutional_expansion_layers"] == 5
    assert manifest["summary"]["immutable_core_pins_verified"] == 18

    inv = manifest["hard_invariants"]
    assert inv["tier0_sota_source_only"] is True
    assert inv["allow_silent_fallback"] is False
    assert inv["paper_only_firewall"] is True
    assert inv["study_wall_date"] == "2026-10-15"
    assert inv["adr0022_max_stop_pct"] == 2.0
    assert set(inv["forbidden_live_ports"]) == {4001, 7496, 8796, 8798}

    seen_ids: set[str] = set()
    covered_stages: set[str] = set()
    for ly in manifest["layers"]:
        assert ly["layer_id"] not in seen_ids
        seen_ids.add(ly["layer_id"])
        assert ly["status"] in {"ACTIVE_FULL_RES_VERIFIED", "ACTIVE_PAPER_LIVE", "EXPANSION_ROADMAP"}
        assert len(ly["owning_local_repos"]) >= 1
        assert len(ly["pinned_core_shelf"]) >= 1
        assert len(ly["starred_sota_repos"]) >= 1
        assert len(ly["beyond_starred_sota_repos"]) >= 1
        assert len(ly["sota_ecosystem_repos"]) >= 2
        assert len(ly["research_convergence_stages"]) >= 1
        covered_stages.update(ly["research_convergence_stages"])
        hb = ly["harness_and_agent_md_binding"]
        assert hb["runtime_md_rules"].strip()
        assert len(hb["canonical_skills"]) >= 1
        assert hb["enforcement_gate"].strip()
        assert ly["full_resolution_invariant"].strip()
        assert ly["verification_gate"].strip()
        for pin in ly["pinned_core_shelf"]:
            assert re.fullmatch(r"[0-9a-f]{40}", pin["commit"]), f"Non-40-char SHA on {pin}"
    assert len(covered_stages) == 8
    sb = manifest["starred_and_beyond_convergence"]
    assert sb["owner_starred_total_audited"] == 415
    assert sb["research_convergence_stages_covered"] == 8

    body = {k: v for k, v in manifest.items() if k != "manifest_sha256"}
    expected_sha = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()
    assert manifest["manifest_sha256"] == expected_sha

    md = _MOD.render_markdown(manifest)
    for needle in (
        "L0_IMMUTABLE_SOTA_SHELF_AND_PROVENANCE",
        "L2_FULL_RESOLUTION_BACKTEST_AND_QUEUE_SIM_ENGINE",
        "L3_STRATEGY_LIBRARIES_AND_PREWALL_RESEARCH_CONVERGENCE",
        "L5_AUTONOMOUS_24X5_PAPER_TRADING_ENGINE",
        "L6_INSTITUTIONAL_TRADING_ENGINE_UI_AND_COCKPIT",
        "L8_ORCA_ECOSYSTEM_AND_MULTI_RUNTIME_HARNESS",
        "L11_BEYOND_CROSS_ACCOUNT_PORTFOLIO_RISK_AND_REGIME_META_ALLOCATOR",
        "L15_BEYOND_SEMANTIC_WATCHDOG_CHAOS_FAILOVER_AND_FORENSIC_ROI",
    ):
        assert needle in md
    assert not re.search(
        r"(C:\\Users|/Users/|/home/|PA[0-9A-Z]{8,}|DU[0-9]{7,})", json.dumps(manifest) + md
    )


def test_sealed_manifest_on_disk_matches_sha256() -> None:
    mf_path = ROOT / "docs" / "SOTA_FULL_LANDSCAPE_LAYER_PIN_ARCHITECTURE_MANIFEST.json"
    assert mf_path.is_file()
    data = json.loads(mf_path.read_text(encoding="utf-8"))
    body = {k: v for k, v in data.items() if k != "manifest_sha256"}
    expected_sha = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()
    assert data["manifest_sha256"] == expected_sha
