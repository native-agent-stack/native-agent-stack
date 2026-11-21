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


_DOCTOR = _load("one_harness_cleanliness_doctor", "scripts/one_harness_cleanliness_doctor.py")
_HOOK = _load("run_sota_git_hook", "hooks/run_sota_git_hook.py")
_SYNC = _load("sync_tier0_harness_and_master_adrs", "scripts/sync_tier0_harness_and_master_adrs.py")


def test_universal_git_hook_files_and_leak_detectors() -> None:
    for fn in ("pre-commit", "pre-push", "run_sota_git_hook.py"):
        assert (ROOT / "hooks" / fn).is_file()

    assert _HOOK._is_sota_repo(ROOT) is True
    sample_leaks = [
        "acct = " + "PA" + "3K9M2N8Q1X",
        "key = " + "PK" + "1234567890" + "ABCDEFGH",
        "path = /" + "Users" + "/alice/secret.txt",
        "path = /" + "home" + "/bob/secret.txt",
        "path = C:" + "\\U" + "sers\\carol\\secret.txt",
    ]
    for sample in sample_leaks:
        assert any(rx.search(sample) for _, rx in _HOOK.STAGED_LEAK_PATTERNS), sample

    clean = "path = ~/sota-workstation/native-agent-stack/scripts/merge_gate.py"
    assert not any(rx.search(clean) for _, rx in _HOOK.STAGED_LEAK_PATTERNS)


def test_sync_tier0_check_parity_on_temp_home(tmp_path: Path) -> None:
    targets = [
        tmp_path / ".gemini" / "GEMINI.md",
        tmp_path / ".claude" / "CLAUDE.md",
        tmp_path / ".codex" / "AGENTS.md",
        tmp_path / ".config" / "opencode" / "AGENTS.md",
        tmp_path / ".dsh" / "AGENTS.md",
        tmp_path / ".omp" / "agent" / "AGENTS.md",
        tmp_path / ".gemini" / "config" / "plugins" / "agy-sota-core" / "rules" / "AGENTS.md",
    ]
    for p in targets:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("# header\n<!-- END SOTA-ECOSYSTEM-SYNC -->\n", encoding="utf-8")

    before = _SYNC.check_tier0_harness_md_parity(tmp_path)
    assert before["all_synced"] is False
    assert len(before["drifted"]) == 7

    _SYNC.sync_tier0_harness_md_files(tmp_path)
    after = _SYNC.check_tier0_harness_md_parity(tmp_path)
    assert after["all_synced"] is True
    assert after["synced_count"] == 7
    assert after["drifted"] == []
    for p in targets:
        assert "ADR-0047" in p.read_text(encoding="utf-8")


def test_adr0047_monolith_ratchet_freeze_and_worktree_waste_cap() -> None:
    assert len(_DOCTOR.MONOLITH_RATCHET_CAPS) >= 7
    assert _DOCTOR.MAX_MERGED_ORCA_WORKTREE_WASTE_GB <= 4.0
    for req_rel in (
        "sota-mover-ranker/ranker/stage5_lossless_live_lane.py",
        "sota-mover-ranker/ranker/alpaca_paper_e2e.py",
        "sota-mover-ranker/ranker/scanner.py",
        "sota-mover-ranker/ranker/paper_auto_engine.py",
    ):
        assert req_rel in _DOCTOR.MONOLITH_RATCHET_CAPS


def test_one_harness_doctor_receipt_on_disk_is_sealed_and_zero_leak() -> None:
    rcpt_path = ROOT / "docs" / "SOTA_ONE_HARNESS_CLEANLINESS_RECEIPT.json"
    md_path = ROOT / "docs" / "SOTA_ONE_HARNESS_CLEANLINESS_RECEIPT.md"
    assert rcpt_path.is_file()
    assert md_path.is_file()

    data = json.loads(rcpt_path.read_text(encoding="utf-8"))
    body = {k: v for k, v in data.items() if k != "receipt_sha256"}
    expected_sha = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()
    assert data["receipt_sha256"] == expected_sha
    assert data["overall_ok"] is True
    assert data["summary"]["checks_total"] == 10
    assert data["summary"]["checks_passed"] == 10

    combined = json.dumps(data) + md_path.read_text(encoding="utf-8")
    leak_rx = re.compile(
        r"(C:\\U"
        + r"sers|/"
        + r"Users/|/"
        + r"home/|PA[0-9A-Z]{8,}|DU[0-9]{7,}|AK[0-9A-Z]{16,}|PK[0-9A-Z]{16,})"
    )
    assert not leak_rx.search(combined)


def test_extra_disk_z_adr_repo_parity_and_isolation(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    demo = ws / "demo-repo"
    (demo / ".git").mkdir(parents=True)
    (demo / "docs" / "adr").mkdir(parents=True)
    (demo / "docs" / "adr" / "ADR-0001-demo.md").write_text(
        "# ADR-0001: Demo\n- **Status:** Accepted\n- **Date:** 2026-11-21\n",
        encoding="utf-8",
    )
    disk_z_repo = tmp_path / "disk_z" / "tier0-quant"
    (disk_z_repo / "docs" / "adr").mkdir(parents=True)
    (disk_z_repo / "docs" / "adr" / "ADR-0001-converged.md").write_text(
        "# ADR-0001: Tier-0 Quant Converged\n- **Status:** Accepted\n- **Date:** 2026-11-21\n",
        encoding="utf-8",
    )

    isolated = _DOCTOR._discover_adr_repos(ws)
    assert [p.name for p in isolated] == ["demo-repo"]

    combined = _DOCTOR._discover_adr_repos(ws, extra_repo_dirs=(disk_z_repo,))
    assert [p.name for p in combined] == ["demo-repo", "tier0-quant"]

    out = tmp_path / "out"
    res = _SYNC.build_public_master_adr_registry(
        workstation=ws, out_dir=out, extra_repo_dirs=(disk_z_repo,)
    )
    assert res["repos_indexed"] == 2
    assert res["total_adrs_indexed"] == 2
    reg = json.loads((out / "ECOSYSTEM_FINALIZED_ADRS_MASTER_REGISTRY.json").read_text(encoding="utf-8"))
    by_repo = {rec["repo"]: rec for rec in reg["records"]}
    assert by_repo["tier0-quant"]["tier"] == "PRIVATE"
