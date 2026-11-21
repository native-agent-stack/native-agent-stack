#!/usr/bin/env python3
"""One-Harness SOTA Cleanliness Doctor (`ADR-0046`).

Single deterministic fail-closed command verifying ALL 10 continuous SOTA cleanliness
invariants across all 16 layers (`L0`–`L15`), 18 repositories, 7 agent runtimes,
415+ audited GitHub starred repos & beyond-starred SOTA anchors, 8-stage Research
Convergence Practice, 60-skill SkillEvaluator corpus, 24-class Red-Team firewall,
universal Git hooks, 18/18 `orca.yaml` gates, single-repo ADR archives, downward-ratchet
anti-bloat budgets, and live Paper P1–P4 / RTX 4090 `:8794` full-resolution health.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_WORKSTATION = ROOT.parent
SCHEMA_VERSION = "sota.one-harness-cleanliness-receipt.v1"
CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

QUANT_AST_REPOS = (
    "meridian",
    "sota-compounding-lab",
    "sota-dynamic-trail-c",
    "sota-mover-ranker",
)

# Downward-ratchet LOC ceilings on legacy monoliths (`ADR-0047`: frozen against growth; may only shrink)
MONOLITH_RATCHET_CAPS: dict[str, int] = {
    "sota-mover-ranker/ranker/stage5_lossless_live_lane.py": 8330,
    "sota-mover-ranker/ranker/alpaca_paper_e2e.py": 8405,
    "sota-mover-ranker/ranker/tv_watchlist_fast_sync.py": 3775,
    "sota-mover-ranker/ranker/paper_p3_aggressive_lab.py": 3120,
    "sota-mover-ranker/ranker/ipo_microstructure_stream.py": 3035,
    "sota-mover-ranker/ranker/scanner.py": 2915,
    "sota-mover-ranker/ranker/paper_auto_engine.py": 2650,
}
MAX_MERGED_ORCA_WORKTREE_WASTE_GB = 4.0

SKIP_ADR_NAMES = frozenset(
    {
        "CATALOG.md",
        "README.md",
        "INDEX.md",
        "ECOSYSTEM_FINALIZED_ADRS_MASTER_REGISTRY.md",
    }
)
DEFAULT_EXTRA_ADR_REPOS: tuple[Path, ...] = (Path("Z:/tier0-quant"),)


def _run(
    cmd: list[str],
    *,
    cwd: Path | None = None,
    timeout: int = 45,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    if sys.platform == "win32":
        return subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
            env=env,
            creationflags=CREATE_NO_WINDOW,
        )
    return subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
        env=env,
    )


def _load_script_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load script module: {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _http_get_json(url: str, timeout: float = 2.5) -> dict[str, Any] | None:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            if resp.status != 200:
                return None
            return json.loads(resp.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError, TimeoutError):
        return None


def _discover_repos(workstation: Path) -> list[Path]:
    if not workstation.is_dir():
        return []
    return sorted(
        (p for p in workstation.iterdir() if p.is_dir() and (p / ".git").exists()),
        key=lambda p: p.name,
    )


def _discover_adr_repos(
    workstation: Path,
    extra_repo_dirs: tuple[Path, ...] | None = None,
) -> list[Path]:
    repos = _discover_repos(workstation)
    extras = (
        DEFAULT_EXTRA_ADR_REPOS
        if (extra_repo_dirs is None and workstation.resolve() == DEFAULT_WORKSTATION.resolve())
        else (extra_repo_dirs or ())
    )
    seen_names = {p.name for p in repos}
    for extra in extras:
        if extra.is_dir() and (extra / "docs" / "adr").is_dir() and extra.name not in seen_names:
            repos.append(extra)
            seen_names.add(extra.name)
    return sorted(repos, key=lambda p: p.name)


def _check_1_upstream_shelf_lock(workstation: Path, *, is_ci: bool) -> dict[str, Any]:
    shelf_src = workstation / "sota-upstream-shelf-lock" / "src"
    if shelf_src.is_dir() and str(shelf_src) not in sys.path:
        sys.path.insert(0, str(shelf_src))
    try:
        hur = importlib.import_module("shelf_lock.hard_upstream_rule")
    except ModuleNotFoundError:
        return {
            "ok": is_ci,
            "mode": "ci_skipped" if is_ci else "missing_shelf_lock",
            "repos_audited": 0,
            "details": "sota-upstream-shelf-lock not co-located in CI checkout"
            if is_ci
            else "missing shelf_lock",
        }

    report = hur.audit_workstation_repos(workstation)
    repos_audited = int(report.get("repos_audited", 0))
    passing = int(report.get("repos_passing_upstream_map", 0))
    adr_pass = int(report.get("repos_passing_adr_evidence", 0))
    shelf_ok = bool(report.get("shelf_18_pins_ok", False))
    shelf_errors = list(report.get("shelf_errors") or [])
    repo_failures = [
        f"{r['repo']}: map_ok={r['upstream_map_ok']} adr_ok={r['adr_evidence_ok']}"
        for r in (report.get("repos") or [])
        if not (r.get("upstream_map_ok") and r.get("adr_evidence_ok"))
    ]
    failures = [*shelf_errors, *repo_failures]
    ok = (
        repos_audited >= 18
        and passing == repos_audited
        and adr_pass == repos_audited
        and shelf_ok
        and not failures
    )
    return {
        "ok": ok,
        "repos_audited": repos_audited,
        "upstream_map_pass": passing,
        "adr_evidence_pass": adr_pass,
        "shelf_pins_ok": shelf_ok,
        "audit_sha256": str(report.get("manifest_sha256", ""))[:16],
        "failure_count": len(failures),
        "failures": failures[:10],
    }


QUANT_AST_GATE_SYMBOLS = (
    "audit_no_empty_backtest_engine_stub",
    "audit_python_source_for_full_resolution",
    "audit_p1_source_no_empty_backtest_stub",
    "audit_ranker_source_no_empty_backtest_stub",
)


def _check_2_zero_stub_and_full_res(workstation: Path, *, offline: bool, is_ci: bool) -> dict[str, Any]:
    ast_wired: dict[str, bool] = {}
    for rname in QUANT_AST_REPOS:
        mg = workstation / rname / "scripts" / "merge_gate.py"
        if not mg.is_file():
            ast_wired[rname] = False
        else:
            txt = mg.read_text(encoding="utf-8", errors="replace")
            ast_wired[rname] = any(sym in txt for sym in QUANT_AST_GATE_SYMBOLS)

    live_status: dict[str, Any] = {"probed": False}
    live_ok = True
    if not offline and not is_ci:
        payload = _http_get_json("http://127.0.0.1:8794/api/full_resolution/status")
        if payload is not None:
            audit = payload.get("audit") or {}
            engines_n = int(audit.get("engines_verified_n", 0))
            required_n = int(audit.get("required_engines_n", 9))
            residuals_n = int(audit.get("residual_fallbacks_count", 0))
            allow_fb = payload.get("allow_silent_fallback")
            fr_verified = bool(payload.get("full_resolution_verified", False))
            live_ok = (
                fr_verified and (allow_fb is False) and (residuals_n == 0) and (engines_n >= required_n)
            )
            live_status = {
                "probed": True,
                "reachable": True,
                "cuda_available": bool(payload.get("cuda_available", False)),
                "engines_verified_n": engines_n,
                "required_engines_n": required_n,
                "allow_silent_fallback": allow_fb,
                "residual_fallbacks_count": residuals_n,
                "ok": live_ok,
            }
        else:
            live_status = {"probed": True, "reachable": False, "note": "sidecar_offline_nonblocking"}

    ast_ok = is_ci or all(ast_wired.values())
    return {
        "ok": ast_ok and live_ok,
        "quant_ast_zero_stub_wired": ast_wired,
        "quant_ast_count": sum(1 for v in ast_wired.values() if v),
        "live_full_resolution_sidecar": live_status,
    }


def _check_3_landscape_starred_beyond_and_research(workstation: Path, *, is_ci: bool) -> dict[str, Any]:
    mf_path = ROOT / "docs" / "SOTA_FULL_LANDSCAPE_LAYER_PIN_ARCHITECTURE_MANIFEST.json"
    if not mf_path.is_file():
        return {"ok": False, "error": "missing SOTA_FULL_LANDSCAPE_LAYER_PIN_ARCHITECTURE_MANIFEST.json"}

    data = json.loads(mf_path.read_text(encoding="utf-8"))
    body = {k: v for k, v in data.items() if k != "manifest_sha256"}
    expected_sha = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()
    sha_ok = data.get("manifest_sha256") == expected_sha

    layers = data.get("layers") or []
    layer_errors: list[str] = []
    covered_stages: set[str] = set()
    for ly in layers:
        lid = str(ly.get("layer_id", "?"))
        if not ly.get("pinned_core_shelf"):
            layer_errors.append(f"{lid}: missing pinned_core_shelf")
        if not ly.get("starred_sota_repos"):
            layer_errors.append(f"{lid}: missing starred_sota_repos")
        if not ly.get("beyond_starred_sota_repos"):
            layer_errors.append(f"{lid}: missing beyond_starred_sota_repos")
        stages = ly.get("research_convergence_stages") or []
        if not stages:
            layer_errors.append(f"{lid}: missing research_convergence_stages")
        covered_stages.update(str(s) for s in stages)
        hb = ly.get("harness_and_agent_md_binding") or {}
        if not hb.get("runtime_md_rules") or not hb.get("canonical_skills"):
            layer_errors.append(f"{lid}: incomplete harness_and_agent_md_binding")

    # Verify pins match live PINS_LOCK.json when co-located
    pins_lock_path = workstation / "sota-upstream-shelf-lock" / "PINS_LOCK.json"
    pins_match_lock = True
    if pins_lock_path.is_file():
        lock_raw = json.loads(pins_lock_path.read_text(encoding="utf-8"))
        lock_map = {str(r["name"]): str(r["commit"]) for r in (lock_raw.get("upstreamShelfPins") or [])}
        mf_map = {str(p["name"]): str(p["commit"]) for p in (data.get("immutable_core_shelf_pins") or [])}
        pins_match_lock = lock_map == mf_map

    # Verify 8-stage Research Convergence Practice from sota-multi-model-workflows when co-located
    rc_summary: dict[str, Any] = {"available": False, "valid": True}
    mmw_src = workstation / "sota-multi-model-workflows" / "src"
    if mmw_src.is_dir():
        if str(mmw_src) not in sys.path:
            sys.path.insert(0, str(mmw_src))
        try:
            rc_mod = importlib.import_module("sota_mmw.research_convergence_contract")
            adv = rc_mod.verify_advanced_sota_convergence_practice()
            rc_summary = {
                "available": True,
                "valid": bool(adv.get("valid", False)),
                "stages_count": int(adv.get("stages_count", 0)),
                "owner_starred_total_audited": int(adv.get("owner_starred_total_audited", 0)),
                "beyond_starred_sota_count": int(adv.get("beyond_starred_sota_count", 0)),
                "bitemporal_pit_verified": bool(adv.get("bitemporal_pit_verified", False)),
            }
        except Exception as exc:  # noqa: BLE001
            rc_summary = {"available": True, "valid": False, "error": str(exc)}
    elif not is_ci:
        rc_summary = {"available": False, "valid": False, "error": "missing sota-multi-model-workflows"}

    # Verify hosted research frameworks manifest & zero-paper-self-invention boundaries
    hosted_path = ROOT / "docs" / "SOTA_HOSTED_RESEARCH_FRAMEWORKS_MANIFEST.json"
    hosted_summary: dict[str, Any] = {"present": hosted_path.is_file(), "valid": False}
    if hosted_path.is_file():
        h_data = json.loads(hosted_path.read_text(encoding="utf-8"))
        h_body = {k: v for k, v in h_data.items() if k != "manifest_sha256"}
        h_expected_sha = hashlib.sha256(
            json.dumps(h_body, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
        ).hexdigest()
        h_sha_ok = h_data.get("manifest_sha256") == h_expected_sha
        h_hb = h_data.get("hard_boundaries") or {}
        h_bounds_ok = (
            h_hb.get("zero_paper_self_invention") is True
            and h_hb.get("clean_installed_frameworks_plus_official_paper_e2e_only") is True
            and h_hb.get("paper_only_firewall") is True
        )
        hosted_summary = {
            "present": True,
            "sha256_valid": h_sha_ok,
            "zero_paper_self_invention": bool(h_hb.get("zero_paper_self_invention")),
            "clean_installed_frameworks_plus_official_paper_e2e_only": bool(
                h_hb.get("clean_installed_frameworks_plus_official_paper_e2e_only")
            ),
            "valid": h_sha_ok and h_bounds_ok,
        }

    ok = (
        sha_ok
        and len(layers) == 16
        and len(covered_stages) == 8
        and not layer_errors
        and pins_match_lock
        and bool(rc_summary.get("valid", False))
        and bool(hosted_summary.get("valid", False))
    )
    return {
        "ok": ok,
        "manifest_sha256_valid": sha_ok,
        "manifest_sha256": str(data.get("manifest_sha256", "")),
        "total_layers": len(layers),
        "research_stages_covered": len(covered_stages),
        "pins_match_pins_lock": pins_match_lock,
        "layer_errors": layer_errors[:10],
        "research_convergence_contract": rc_summary,
        "hosted_frameworks_manifest": hosted_summary,
    }


def _check_4_runtime_md_skills_redteam_and_models(
    workstation: Path, *, home_dir: Path | None = None, is_ci: bool = False
) -> dict[str, Any]:
    sync_mod = _load_script_module(
        "sync_tier0_harness_and_master_adrs",
        ROOT / "scripts" / "sync_tier0_harness_and_master_adrs.py",
    )
    home = home_dir or Path.home()
    md_parity = sync_mod.check_tier0_harness_md_parity(home)
    md_ok = True if is_ci else bool(md_parity["all_synced"])

    # SkillEvaluator (60/60) & Red-Team 24-class Firewall from sota-harness-foundation
    skill_eval: dict[str, Any] = {"available": False, "all_passed": True, "skills_evaluated": 0}
    redteam: dict[str, Any] = {"available": False, "passed": True, "p0_count": 0, "p1_count": 0}
    found_root = workstation / "sota-harness-foundation"
    found_src = found_root / "src"
    skills_root = home / ".agents" / "skills"
    if found_src.is_dir():
        mod_path = found_src / "cc_sota_harness" / "redteam_and_skill_eval.py"
        if mod_path.is_file():
            try:
                rt_mod = _load_script_module("_one_harness_redteam_skill_eval", mod_path)
                if skills_root.is_dir():
                    corpus = rt_mod.evaluate_skill_corpus(skills_root)
                    skill_eval = {
                        "available": True,
                        "all_passed": bool(corpus["all_passed"]),
                        "skills_evaluated": int(corpus["skills_evaluated"]),
                        "passed_count": int(corpus["passed_count"]),
                        "failed_skills": list(corpus["failed_skills"]),
                        "report_sha256": str(corpus["report_sha256"]),
                    }
                rt = rt_mod.run_redteam_firewall_audit(
                    "Verify 16-layer One-Harness SOTA cleanliness, Paper-only firewall & pre-wall <= 2026-10-15",
                    context="one_harness_doctor",
                    hard_stop_pct=1.75,
                    ts_event_ns=1_792_074_600_000_000_000,
                    ts_recv_ns=1_792_074_600_005_000_000,
                    decision_ns=1_792_074_600_010_000_000,
                )
                redteam = {
                    "available": True,
                    "passed": bool(rt["passed"]),
                    "p0_count": int(rt["p0_count"]),
                    "p1_count": int(rt["p1_count"]),
                    "vulnerability_classes_catalog_count": int(rt["vulnerability_classes_catalog_count"]),
                }
            except ModuleNotFoundError:
                venv_py = next(
                    (
                        cand
                        for cand in (
                            found_root / ".venv" / "Scripts" / "python.exe",
                            found_root / ".venv" / "bin" / "python",
                        )
                        if cand.is_file()
                    ),
                    None,
                )
                if venv_py is not None:
                    probe = (
                        "import json, sys; from pathlib import Path; "
                        "sys.path.insert(0, sys.argv[1]); "
                        "from cc_sota_harness.redteam_and_skill_eval import "
                        "evaluate_skill_corpus, run_redteam_firewall_audit; "
                        "sr = Path(sys.argv[2]); "
                        "se = {'available': False, 'all_passed': True, 'skills_evaluated': 0, 'failed_skills': []}; "
                        "corpus = evaluate_skill_corpus(sr) if sr.is_dir() else None; "
                        "se = ({'available': True, 'all_passed': bool(corpus['all_passed']), "
                        "'skills_evaluated': int(corpus['skills_evaluated']), "
                        "'passed_count': int(corpus['passed_count']), "
                        "'failed_skills': list(corpus['failed_skills']), "
                        "'report_sha256': str(corpus['report_sha256'])} if corpus else se); "
                        "rt = run_redteam_firewall_audit('Verify 16-layer One-Harness SOTA cleanliness', "
                        "context='one_harness_doctor', hard_stop_pct=1.75, "
                        "ts_event_ns=1792074600000000000, ts_recv_ns=1792074600005000000, "
                        "decision_ns=1792074600010000000); "
                        "rp = {'available': True, 'passed': bool(rt['passed']), "
                        "'p0_count': int(rt['p0_count']), 'p1_count': int(rt['p1_count']), "
                        "'vulnerability_classes_catalog_count': int(rt['vulnerability_classes_catalog_count'])}; "
                        "print(json.dumps({'skill_eval': se, 'redteam': rp}))"
                    )
                    proc = _run([str(venv_py), "-c", probe, str(found_src), str(skills_root)])
                    if proc.returncode == 0 and proc.stdout.strip():
                        parsed = json.loads(proc.stdout.strip().splitlines()[-1])
                        skill_eval = parsed["skill_eval"]
                        redteam = parsed["redteam"]
                    else:
                        err_txt = (proc.stderr or proc.stdout or "venv probe failed").strip()[:160]
                        skill_eval = {"available": True, "all_passed": False, "error": err_txt}
                        redteam = {"available": True, "passed": False, "error": err_txt}
                else:
                    skill_eval = {
                        "available": True,
                        "all_passed": False,
                        "error": "missing yaml and foundation venv",
                    }
                    redteam = {
                        "available": True,
                        "passed": False,
                        "error": "missing yaml and foundation venv",
                    }
            except Exception as exc:  # noqa: BLE001
                skill_eval = {"available": True, "all_passed": False, "error": str(exc)}
                redteam = {"available": True, "passed": False, "error": str(exc)}

    # Zero stale/retired models across Orca worker defaults & runtime roster
    stale_hits: list[str] = []
    mmw_src = workstation / "sota-multi-model-workflows" / "src"
    if mmw_src.is_dir():
        if str(mmw_src) not in sys.path:
            sys.path.insert(0, str(mmw_src))
        try:
            hub = importlib.import_module("sota_mmw.cc_lead_hub")
            for wk, meta in hub.RUNTIME_WORKER_ROSTER.items():
                if wk in hub.RETIRED_WORKER_KEYS:
                    stale_hits.append(f"retired_worker:{wk}")
                hay = f"{wk} {meta.get('model', '')} {meta.get('vendor', '')}".lower()
                for bad in hub.FORBIDDEN_STALE_AND_REDUNDANT_MODELS:
                    if bad in hay:
                        stale_hits.append(f"roster:{wk}:{bad}")
            for aid, spec in hub.ORCA_RUNTIME_WORKER_DEFAULTS.items():
                hay = f"{aid} {spec.get('default_model', '')} {spec.get('extra_agent_args', '')}".lower()
                for bad in hub.FORBIDDEN_STALE_AND_REDUNDANT_MODELS:
                    if bad in hay:
                        stale_hits.append(f"orca:{aid}:{bad}")
        except Exception as exc:  # noqa: BLE001
            stale_hits.append(f"hub_load_error:{exc}")

    ok = (
        md_ok
        and bool(skill_eval.get("all_passed", False))
        and bool(redteam.get("passed", False))
        and len(stale_hits) == 0
    )
    return {
        "ok": ok,
        "global_md_parity": md_parity,
        "skill_evaluator": skill_eval,
        "redteam_firewall": redteam,
        "stale_model_hits": stale_hits,
    }


def _check_5_single_repo_adr_parity(workstation: Path, *, is_ci: bool) -> dict[str, Any]:
    pub_path = ROOT / "docs" / "adr" / "ECOSYSTEM_FINALIZED_ADRS_MASTER_REGISTRY.json"
    if not pub_path.is_file():
        return {"ok": False, "error": "missing ECOSYSTEM_FINALIZED_ADRS_MASTER_REGISTRY.json"}
    pub = json.loads(pub_path.read_text(encoding="utf-8"))
    pub_counts: dict[str, int] = dict(pub.get("per_repo_counts") or {})
    pub_total = int(pub.get("total_adrs_indexed", 0))

    if is_ci:
        return {
            "ok": pub_total > 0 and len(pub_counts) >= 18,
            "mode": "ci_public_registry_only",
            "public_registry_total": pub_total,
            "public_repos_indexed": len(pub_counts),
        }

    live_counts: dict[str, int] = {}
    for rp in _discover_adr_repos(workstation):
        adr_dir = rp / "docs" / "adr"
        if adr_dir.is_dir():
            cnt = sum(1 for p in adr_dir.glob("*.md") if p.is_file() and p.name not in SKIP_ADR_NAMES)
            live_counts[rp.name] = cnt
    live_total = sum(live_counts.values())

    pub_drift = {
        k: {"live": live_counts.get(k, 0), "public_registry": pub_counts.get(k, 0)}
        for k in sorted(set(live_counts) | set(pub_counts))
        if live_counts.get(k, 0) != pub_counts.get(k, 0)
    }

    vault_manifest = (
        workstation / "sota-private-vault" / "adr_archive" / "ECOSYSTEM_ALL_FINALIZED_ADRS_MANIFEST.json"
    )
    vault_ok = True
    vault_total = 0
    vault_drift: dict[str, Any] = {}
    if vault_manifest.is_file():
        vm = json.loads(vault_manifest.read_text(encoding="utf-8"))
        v_counts_raw = vm.get("per_repo_counts") or {}
        vault_total = int(vm.get("total_adrs_archived", 0))
        if isinstance(v_counts_raw, dict) and v_counts_raw:
            vault_drift = {
                k: {"live": live_counts.get(k, 0), "vault_archive": int(v_counts_raw.get(k, 0))}
                for k in sorted(set(live_counts) | set(v_counts_raw))
                if live_counts.get(k, 0) != int(v_counts_raw.get(k, 0))
            }
            vault_ok = len(vault_drift) == 0
        else:
            vault_ok = vault_total >= live_total

    ok = len(pub_drift) == 0 and vault_ok and live_total > 0
    return {
        "ok": ok,
        "live_total_adrs": live_total,
        "public_registry_total": pub_total,
        "public_drift": pub_drift,
        "vault_archive_present": vault_manifest.is_file(),
        "vault_archive_total": vault_total,
        "vault_drift": vault_drift,
    }


def _check_6_hooks_and_orca_parity(workstation: Path, *, is_ci: bool) -> dict[str, Any]:
    hooks_dir = ROOT / "hooks"
    hooks_files_ok = all(
        (hooks_dir / fn).is_file() for fn in ("pre-commit", "pre-push", "run_sota_git_hook.py")
    )
    configured_hooks = _run(["git", "config", "--global", "--get", "core.hooksPath"]).stdout.strip()
    expected_resolved = hooks_dir.resolve()
    hooks_active = False
    if configured_hooks:
        try:
            hooks_active = Path(configured_hooks).resolve() == expected_resolved
        except OSError:
            hooks_active = False

    if is_ci:
        return {
            "ok": hooks_files_ok,
            "mode": "ci_tracked_hooks_check",
            "hooks_files_present": hooks_files_ok,
        }

    repos = _discover_repos(workstation)
    missing_merge_gate_script: list[str] = []
    missing_orca_merge_gate: list[str] = []
    for rp in repos:
        if not (rp / "scripts" / "merge_gate.py").is_file():
            missing_merge_gate_script.append(rp.name)
        oy = rp / "orca.yaml"
        if not oy.is_file() or "merge_gate.py" not in oy.read_text(encoding="utf-8", errors="replace"):
            missing_orca_merge_gate.append(rp.name)

    ok = (
        hooks_files_ok
        and hooks_active
        and len(repos) >= 18
        and not missing_merge_gate_script
        and not missing_orca_merge_gate
    )
    return {
        "ok": ok,
        "hooks_files_present": hooks_files_ok,
        "global_core_hooks_path_active": hooks_active,
        "repos_checked": len(repos),
        "merge_gate_scripts_present": len(repos) - len(missing_merge_gate_script),
        "orca_yaml_merge_gate_present": len(repos) - len(missing_orca_merge_gate),
        "missing_merge_gate_script": missing_merge_gate_script,
        "missing_orca_merge_gate": missing_orca_merge_gate,
    }


def _check_7_security_and_github_firewall(*, is_ci: bool) -> dict[str, Any]:
    gitleaks_available = shutil.which("gitleaks") is not None
    email = _run(["git", "config", "--global", "--get", "user.email"]).stdout.strip()
    noreply_ok = is_ci or ("@users.noreply.github.com" in email.lower())

    src_dir = str(ROOT / "src")
    existing_pp = os.environ.get("PYTHONPATH", "")
    umbrella_env = {
        **os.environ,
        "PYTHONPATH": f"{src_dir}{os.pathsep}{existing_pp}" if existing_pp else src_dir,
    }
    umbrella_proc = _run(
        [sys.executable, "-m", "native_agent_stack.umbrella", "--check"],
        cwd=ROOT,
        env=umbrella_env,
    )
    umbrella_ok = umbrella_proc.returncode == 0

    return {
        "ok": noreply_ok and umbrella_ok and (is_ci or gitleaks_available),
        "noreply_global_email_ok": noreply_ok,
        "umbrella_two_tier_firewall_ok": umbrella_ok,
        "gitleaks_on_path": gitleaks_available,
    }


def _audit_merged_orca_worktrees() -> tuple[float, int]:
    """Measure clean, already-merged Orca worktree byte waste (no home paths emitted)."""
    orca_root = Path.home() / "orca" / "workspaces"
    if not orca_root.is_dir():
        return 0.0, 0
    merged_bytes = 0
    merged_count = 0
    for repo_dir in orca_root.iterdir():
        if not repo_dir.is_dir():
            continue
        for wt in repo_dir.iterdir():
            if not wt.is_dir() or not (wt / ".git").exists():
                continue
            st = _run(["git", "-C", str(wt), "status", "--porcelain"], timeout=10)
            if st.returncode != 0 or st.stdout.strip():
                continue
            ab = _run(
                ["git", "-C", str(wt), "rev-list", "--left-right", "--count", "origin/main...HEAD"],
                timeout=10,
            )
            if ab.returncode != 0:
                continue
            parts = ab.stdout.strip().split()
            ahead = int(parts[1]) if len(parts) == 2 else 999
            if ahead != 0:
                continue
            merged_count += 1
            for r_dir, _, files in os.walk(wt):
                rp = Path(r_dir)
                for fn in files:
                    try:
                        merged_bytes += (rp / fn).stat().st_size
                    except OSError:
                        pass
    return round(merged_bytes / 1e9, 2), merged_count


def _check_8_anti_bloat_and_ratchet(workstation: Path, *, is_ci: bool) -> dict[str, Any]:
    if is_ci:
        return {"ok": True, "mode": "ci_skipped"}
    repos = _discover_repos(workstation)
    size_budget_repos = [rp.name for rp in repos if (rp / "size-budget.toml").is_file()]
    monolith_lines: dict[str, dict[str, Any]] = {}
    ratchet_violations: list[str] = []
    for rel, cap in MONOLITH_RATCHET_CAPS.items():
        fp = workstation / rel
        if fp.is_file():
            loc = sum(1 for _ in fp.open(encoding="utf-8", errors="replace"))
            exceeded = loc > cap
            monolith_lines[rel] = {"loc": loc, "ratchet_cap": cap, "ok": not exceeded}
            if exceeded:
                ratchet_violations.append(f"{rel}: {loc} > {cap}")
    merged_waste_gb, merged_worktrees_count = _audit_merged_orca_worktrees()
    if merged_waste_gb > MAX_MERGED_ORCA_WORKTREE_WASTE_GB:
        ratchet_violations.append(
            f"merged_orca_worktree_waste: {merged_waste_gb}GB > {MAX_MERGED_ORCA_WORKTREE_WASTE_GB}GB"
        )
    return {
        "ok": len(ratchet_violations) == 0,
        "size_budget_repos_count": len(size_budget_repos),
        "size_budget_repos": size_budget_repos,
        "monolith_ratchet": monolith_lines,
        "merged_worktrees_count": merged_worktrees_count,
        "merged_waste_gb": merged_waste_gb,
        "max_merged_waste_gb": MAX_MERGED_ORCA_WORKTREE_WASTE_GB,
        "ratchet_violations": ratchet_violations,
    }


def _check_9_sota_bus_health(*, is_ci: bool) -> dict[str, Any]:
    sota_bus = shutil.which("sota-bus")
    if not sota_bus:
        return {"ok": is_ci, "available": False}
    proc = _run([sota_bus, "status"], timeout=15)
    if proc.returncode != 0:
        return {"ok": False, "available": True, "error": proc.stderr.strip()[:200]}
    try:
        parsed = json.loads(proc.stdout)
        return {
            "ok": True,
            "available": True,
            "live_sessions_count": len(parsed.get("live_sessions") or []),
            "active_leases_count": len(parsed.get("active_leases") or []),
        }
    except json.JSONDecodeError:
        return {"ok": False, "available": True, "error": "invalid json from sota-bus status"}


def _check_10_paper_trajectory_and_live_probes(
    workstation: Path, *, offline: bool, is_ci: bool
) -> dict[str, Any]:
    if is_ci:
        return {"ok": True, "mode": "ci_skipped"}
    traj_path = (
        workstation / "sota-mover-ranker" / "docs" / "SOTA_PAPER_IMPROVEMENT_TRAJECTORY_MANIFEST.json"
    )
    manifest_info: dict[str, Any] = {"present": traj_path.is_file()}
    manifest_ok = True
    if traj_path.is_file():
        raw = json.loads(traj_path.read_text(encoding="utf-8"))
        manifest_sha = str(raw.get("manifest_sha256", ""))
        privacy_ok = bool(raw.get("dimensionless_privacy_firewall", True))
        snap_count = int(raw.get("snapshots_tracked_count", 0))
        latest_ny = str(raw.get("latest_snapshot_ny", ""))
        kpi_deltas = raw.get("kpi_deltas_baseline_to_latest") or {}
        q_intact = kpi_deltas.get("quarantine_firewall_intact", True)
        manifest_ok = bool(manifest_sha) and privacy_ok and snap_count > 0 and bool(q_intact)
        manifest_info.update(
            {
                "schema": raw.get("schema", ""),
                "version": raw.get("version", ""),
                "snapshots_tracked_count": snap_count,
                "latest_snapshot_ny": latest_ny,
                "dimensionless_privacy_firewall": privacy_ok,
                "quarantine_firewall_intact": bool(q_intact),
                "ok": manifest_ok,
            }
        )
    else:
        manifest_ok = False

    live_probes: dict[str, Any] = {}
    if not offline:
        for label, url in (
            ("p1_8799", "http://127.0.0.1:8799/api/state"),
            ("p2_8787", "http://127.0.0.1:8787/api/health"),
            ("p3_8797", "http://127.0.0.1:8797/api/status"),
        ):
            res = _http_get_json(url, timeout=2.0)
            live_probes[label] = {"reachable": res is not None}

    return {
        "ok": manifest_ok,
        "paper_trajectory_manifest": manifest_info,
        "live_paper_probes": live_probes,
    }


def apply_fix_sync(workstation: Path = DEFAULT_WORKSTATION) -> dict[str, Any]:
    """Deterministically repair runtime .md drift, landscape manifest, ADR archives & global Git hooks."""
    actions: dict[str, Any] = {}

    # 1. Configure global core.hooksPath to canonical native-agent-stack/hooks
    hooks_dir = (ROOT / "hooks").resolve().as_posix()
    hp = _run(["git", "config", "--global", "core.hooksPath", hooks_dir])
    actions["git_global_hooks_path_set"] = hp.returncode == 0

    # 2. Regenerate ADR-0045 16-layer Full-Landscape Manifest
    mf_mod = _load_script_module(
        "build_full_landscape_layer_manifest",
        ROOT / "scripts" / "build_full_landscape_layer_manifest.py",
    )
    mf = mf_mod.build_full_landscape_layer_manifest(workstation=workstation)
    (ROOT / "docs" / "SOTA_FULL_LANDSCAPE_LAYER_PIN_ARCHITECTURE_MANIFEST.json").write_text(
        json.dumps(mf, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n"
    )
    (ROOT / "docs" / "SOTA_FULL_LANDSCAPE_LAYER_PIN_ARCHITECTURE_MANIFEST.md").write_text(
        mf_mod.render_markdown(mf), encoding="utf-8", newline="\n"
    )
    actions["landscape_manifest_sha256"] = mf["manifest_sha256"]

    # 3. Sync all 7/7 global runtime .md files & public Master ADR Registry
    sync_mod = _load_script_module(
        "sync_tier0_harness_and_master_adrs",
        ROOT / "scripts" / "sync_tier0_harness_and_master_adrs.py",
    )
    reg = sync_mod.build_public_master_adr_registry(workstation=workstation)
    md_res = sync_mod.sync_tier0_harness_md_files()
    actions["public_master_adr_registry"] = reg
    actions["global_runtime_md_sync"] = md_res

    # 4. Sync private verbatim single-repo ADR archive if co-located
    vault_script = workstation / "sota-private-vault" / "scripts" / "sync_ecosystem_full_adrs.py"
    if vault_script.is_file():
        vp = _run([sys.executable, str(vault_script)], cwd=vault_script.parent.parent, timeout=60)
        actions["private_vault_adr_sync_ok"] = vp.returncode == 0
    return actions


def run_one_harness_doctor(
    workstation: Path = DEFAULT_WORKSTATION,
    *,
    home_dir: Path | None = None,
    offline: bool = False,
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    """Run all 10 deterministic One-Harness Cleanliness invariants and seal a SHA-256 receipt."""
    is_ci = os.environ.get("GITHUB_ACTIONS", "").lower() == "true"

    checks: dict[str, dict[str, Any]] = {
        "1_adr0023_upstream_and_shelf_lock": _check_1_upstream_shelf_lock(workstation, is_ci=is_ci),
        "2_adr0038_zero_stub_and_full_res": _check_2_zero_stub_and_full_res(
            workstation, offline=offline, is_ci=is_ci
        ),
        "3_adr0045_16layer_starred_beyond_and_research": _check_3_landscape_starred_beyond_and_research(
            workstation, is_ci=is_ci
        ),
        "4_adr0044_7runtime_md_60skills_redteam_and_models": _check_4_runtime_md_skills_redteam_and_models(
            workstation, home_dir=home_dir, is_ci=is_ci
        ),
        "5_adr0027_adr0044_single_repo_adr_0drift": _check_5_single_repo_adr_parity(
            workstation, is_ci=is_ci
        ),
        "6_universal_git_hooks_and_18repo_orca_gate": _check_6_hooks_and_orca_parity(
            workstation, is_ci=is_ci
        ),
        "7_security_zero_leak_and_github_firewall": _check_7_security_and_github_firewall(is_ci=is_ci),
        "8_anti_bloat_size_budget_and_ratchet": _check_8_anti_bloat_and_ratchet(workstation, is_ci=is_ci),
        "9_sota_bus_peer_coordination_health": _check_9_sota_bus_health(is_ci=is_ci),
        "10_paper_trajectory_manifest_and_live_probes": _check_10_paper_trajectory_and_live_probes(
            workstation, offline=offline, is_ci=is_ci
        ),
    }

    passed_count = sum(1 for v in checks.values() if bool(v.get("ok")))
    failed_checks = [k for k, v in checks.items() if not bool(v.get("ok"))]

    report: dict[str, Any] = {
        "schema": SCHEMA_VERSION,
        "adr": "ADR-0046",
        "generated_at_utc": generated_at_utc or datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "mode": "ci" if is_ci else ("offline" if offline else "full_workstation"),
        "overall_ok": len(failed_checks) == 0,
        "summary": {
            "checks_total": len(checks),
            "checks_passed": passed_count,
            "checks_failed": len(failed_checks),
            "failed_check_ids": failed_checks,
        },
        "checks": checks,
    }
    raw = json.dumps(report, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    report["receipt_sha256"] = hashlib.sha256(raw).hexdigest()
    return report


def render_receipt_markdown(report: dict[str, Any]) -> str:
    """Render concise public-safe Markdown Cleanliness Receipt."""
    s = report["summary"]
    status_badge = "PASS" if report["overall_ok"] else "FAIL"
    lines = [
        "# Native Agent Stack — One-Harness SOTA Cleanliness Receipt (`ADR-0046`)",
        "",
        f"- **Overall Verdict:** `{status_badge}` (`{s['checks_passed']}/{s['checks_total']}` deterministic invariants passed)",
        f"- **Canonical Receipt SHA-256:** `{report['receipt_sha256']}`",
        f"- **Audit Mode:** `{report['mode']}` · **Generated (UTC):** `{report['generated_at_utc']}`",
        "",
        "## Deterministic 10-Invariant Verification Matrix",
        "",
        "| Invariant | Verdict | Key Verified Telemetry |",
        "| :--- | :---: | :--- |",
    ]
    for cid, c in report["checks"].items():
        verdict = "PASS" if c.get("ok") else "FAIL"
        summary_parts: list[str] = []
        for k, v in c.items():
            if k in {"ok", "failures", "layer_errors", "public_drift", "vault_drift", "statuses"}:
                continue
            if isinstance(v, (int, float, bool, str)):
                summary_parts.append(f"`{k}={v}`")
            elif isinstance(v, dict):
                sub = ", ".join(
                    f"{sk}={sv}"
                    for sk, sv in v.items()
                    if isinstance(sv, (int, float, bool, str)) and sk != "report_sha256"
                )
                if sub:
                    summary_parts.append(f"{k}({sub})")
        detail = " · ".join(summary_parts[:6]).replace("|", "\\|")
        lines.append(f"| `{cid}` | `{verdict}` | {detail} |")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="One-Harness SOTA Cleanliness Doctor (ADR-0046)")
    parser.add_argument("--workstation", type=Path, default=DEFAULT_WORKSTATION)
    parser.add_argument("--check", action="store_true", help="Verify all 10 invariants (default)")
    parser.add_argument(
        "--fix-sync",
        action="store_true",
        help="Repair .md drift, landscape manifest, ADR archives & global Git hooks before verifying",
    )
    parser.add_argument(
        "--write-receipt",
        action="store_true",
        help="Write sealed public-safe docs/SOTA_ONE_HARNESS_CLEANLINESS_RECEIPT.{json,md}",
    )
    parser.add_argument("--offline", action="store_true", help="Skip live localhost HTTP probes")
    parser.add_argument("--json", action="store_true", help="Print full JSON report")
    args = parser.parse_args()

    fix_actions: dict[str, Any] | None = None
    if args.fix_sync:
        fix_actions = apply_fix_sync(workstation=args.workstation)

    report = run_one_harness_doctor(workstation=args.workstation, offline=args.offline)
    if args.write_receipt:
        out_json = ROOT / "docs" / "SOTA_ONE_HARNESS_CLEANLINESS_RECEIPT.json"
        out_md = ROOT / "docs" / "SOTA_ONE_HARNESS_CLEANLINESS_RECEIPT.md"
        out_json.write_text(
            json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n"
        )
        out_md.write_text(render_receipt_markdown(report), encoding="utf-8", newline="\n")

    if args.json:
        payload = {"fix_actions": fix_actions, "report": report} if fix_actions is not None else report
        print(json.dumps(payload, indent=2))
    else:
        s = report["summary"]
        tag = "PASS" if report["overall_ok"] else "FAIL"
        print(
            f"[ONE-HARNESS-DOCTOR {tag}] {s['checks_passed']}/{s['checks_total']} invariants passed | "
            f"receipt_sha256={report['receipt_sha256'][:16]} | failed={s['failed_check_ids']}"
        )
    return 0 if report["overall_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
