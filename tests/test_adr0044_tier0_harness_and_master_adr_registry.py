from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]


def _load_sync_mod() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "sync_tier0_harness_and_master_adrs",
        ROOT / "scripts" / "sync_tier0_harness_and_master_adrs.py",
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_MOD = _load_sync_mod()
TIER0_MARKER_END = _MOD.TIER0_MARKER_END
TIER0_MARKER_START = _MOD.TIER0_MARKER_START
build_public_master_adr_registry = _MOD.build_public_master_adr_registry
sync_tier0_harness_md_files = _MOD.sync_tier0_harness_md_files
upsert_tier0_block_in_text = _MOD.upsert_tier0_block_in_text


def test_upsert_tier0_block_preserves_omx_sections_and_is_idempotent() -> None:
    sample = (
        "# Runtime\n\n"
        "<!-- BEGIN SOTA-ECOSYSTEM-SYNC -->\n"
        "- Existing rule\n"
        "<!-- END SOTA-ECOSYSTEM-SYNC -->\n\n"
        "<!-- OMX:AGENTS:START -->\n"
        "Preserve me verbatim\n"
        "<!-- OMX:AGENTS:END -->\n"
    )
    once = upsert_tier0_block_in_text(sample)
    assert TIER0_MARKER_START in once
    assert TIER0_MARKER_END in once
    assert "ADR-0023" in once
    assert "allow_silent_fallback = False" in once
    assert "Preserve me verbatim" in once
    assert once.index(TIER0_MARKER_END) < once.index("<!-- END SOTA-ECOSYSTEM-SYNC -->")
    assert upsert_tier0_block_in_text(once) == once


def test_sync_tier0_harness_md_files_updates_all_seven_surfaces(tmp_path: Path) -> None:
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
        p.write_text(
            "<!-- BEGIN SOTA-ECOSYSTEM-SYNC -->\n<!-- END SOTA-ECOSYSTEM-SYNC -->\n", encoding="utf-8"
        )
    agy_plugin = tmp_path / ".gemini" / "config" / "plugins" / "agy-sota-core" / "rules" / "AGENTS.md"
    agy_plugin.parent.mkdir(parents=True, exist_ok=True)
    agy_plugin.write_text("# AGY Rules\n- Tier-0 Full-Resolution\n", encoding="utf-8")

    res = sync_tier0_harness_md_files(home_dir=tmp_path)
    assert len(res) == 7
    assert all(v == "updated" for v in res.values())
    for p in (*targets, agy_plugin):
        txt = p.read_text(encoding="utf-8")
        assert "ADR-0023" in txt

    # Second run must be strictly idempotent
    res2 = sync_tier0_harness_md_files(home_dir=tmp_path)
    assert all(v == "unchanged" for v in res2.values())


def test_build_public_master_adr_registry_scrubs_and_seals_sha256(tmp_path: Path) -> None:
    repo = tmp_path / "demo-repo"
    (repo / ".git").mkdir(parents=True)
    adr_dir = repo / "docs" / "adr"
    adr_dir.mkdir(parents=True)
    (adr_dir / "ADR-0001-demo.md").write_text(
        "# ADR-0001: Demo Title\n- **Status:** Accepted\n- **Date:** 2026-11-20\n"
        "- **Evidence Grade:** E4\n- **GitHub Evidence:** https://github.com/native-agent-stack/native-agent-stack\n",
        encoding="utf-8",
    )
    out = tmp_path / "out"
    res = build_public_master_adr_registry(workstation=tmp_path, out_dir=out)
    assert res["repos_indexed"] == 1
    assert res["total_adrs_indexed"] == 1
    data = json.loads((out / "ECOSYSTEM_FINALIZED_ADRS_MASTER_REGISTRY.json").read_text(encoding="utf-8"))
    assert data["manifest_sha256"] == res["manifest_sha256"]
    assert (out / "ECOSYSTEM_FINALIZED_ADRS_MASTER_REGISTRY.md").is_file()
