#!/usr/bin/env python3
"""Deterministic Merge Gate for native-agent-stack (zero-leak, MADR 4.0, ADR-0023, ruff, ty, pytest)."""

from __future__ import annotations

import importlib
import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
SECRET_OR_PATH_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("Broker Account ID", re.compile(r"\b(?:PA|DU)(?=[0-9A-Z]*[0-9])[0-9A-Z]{8,14}\b")),
    ("Alpaca Key Prefix", re.compile(r"\b(?:AK|PK)[0-9A-Z]{16,28}\b")),
    ("Private Key Header", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("macOS Home Path", re.compile(r"(?<![A-Za-z0-9_*])/" + r"Users/[A-Za-z0-9._-]+/")),
    ("Linux Home Path", re.compile(r"(?<![A-Za-z0-9_*])/home/[A-Za-z0-9._-]+/")),
    ("Windows Home Path", re.compile(r"[A-Za-z]:[/\\]Users[/\\][A-Za-z0-9._-]+[/\\]")),
)


def _verify_zero_leaks() -> list[str]:
    errors: list[str] = []
    if sys.platform == "win32":
        tracked = subprocess.run(
            ["git", "-C", str(ROOT), "ls-files"],
            capture_output=True,
            text=True,
            check=True,
            creationflags=CREATE_NO_WINDOW,
        )
    else:
        tracked = subprocess.run(
            ["git", "-C", str(ROOT), "ls-files"], capture_output=True, text=True, check=True
        )
    for rel in (ln.strip() for ln in tracked.stdout.splitlines() if ln.strip()):
        if rel in ("scripts/merge_gate.py", "scripts/sync_tier0_harness_and_master_adrs.py"):
            continue
        fp = ROOT / rel
        if not fp.is_file():
            continue
        try:
            txt = fp.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for label, rx in SECRET_OR_PATH_PATTERNS:
            if rx.search(txt):
                errors.append(f"{rel}: triggered {label}")
    return errors


def _verify_adr0023_hard_upstream_rule() -> list[str]:
    errors: list[str] = []
    if not (ROOT / "UPSTREAM.md").is_file():
        errors.append("ADR-0023: missing UPSTREAM.md")
    umap = ROOT / "upstream-map.toml"
    if not umap.is_file():
        errors.append("ADR-0023: missing upstream-map.toml")
    else:
        try:
            parsed = tomllib.loads(umap.read_text(encoding="utf-8"))
            if not isinstance(parsed.get("areas"), dict) or not parsed["areas"]:
                errors.append("ADR-0023: upstream-map.toml [areas] must be non-empty")
            if not isinstance(parsed.get("shelf_pins"), dict) or len(parsed["shelf_pins"]) < 18:
                errors.append("ADR-0023: upstream-map.toml [shelf_pins] must contain all 18 core pins")
        except (OSError, tomllib.TOMLDecodeError) as exc:
            errors.append(f"ADR-0023: upstream-map.toml parse error: {exc}")

    for cand in (
        ROOT.parent / "sota-upstream-shelf-lock" / "src",
        Path("C:/sota-workstation/sota-upstream-shelf-lock/src"),
    ):
        if cand.is_dir() and str(cand) not in sys.path:
            sys.path.insert(0, str(cand))
            break
    try:
        hur = importlib.import_module("shelf_lock.hard_upstream_rule")
    except ModuleNotFoundError:
        if os.environ.get("GITHUB_ACTIONS", "").lower() == "true":
            return errors
        errors.append("ADR-0023: missing local sota-upstream-shelf-lock (required outside hosted CI)")
        return errors

    errors.extend(hur.verify_upstream_map(ROOT))
    errors.extend(hur.verify_adrs_have_evidence(ROOT))
    errors.extend(hur.verify_sealed_manifests(ROOT))
    errors.extend(hur.verify_shelf_pins_on_disk())
    return errors


def main() -> int:
    leak_errors = _verify_zero_leaks()
    adr0023_errors = _verify_adr0023_hard_upstream_rule()
    all_static = [*leak_errors, *adr0023_errors]
    if all_static:
        for err in all_static:
            print(f"[MERGE-GATE FAIL] {err}", file=sys.stderr)
        return 1
    steps: list[list[str]] = [
        [sys.executable, "scripts/architecture_catalog.py", "--check"],
        [sys.executable, "-m", "native_agent_stack.umbrella", "--check"],
        [sys.executable, "-m", "ruff", "check", "."],
        [sys.executable, "-m", "ruff", "format", "--check", "."],
        [sys.executable, "-m", "ty", "check", "src", "scripts", "tests"],
        [sys.executable, "-m", "pytest", "-q"],
    ]
    for cmd in steps:
        if sys.platform == "win32":
            proc = subprocess.run(cmd, cwd=ROOT, check=False, creationflags=CREATE_NO_WINDOW)
        else:
            proc = subprocess.run(cmd, cwd=ROOT, check=False)
        if proc.returncode != 0:
            return proc.returncode
    print(
        "[MERGE-GATE PASS] All umbrella invariants, ADR-0023 upstream provenance & zero-leak gates verified."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
