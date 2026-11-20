#!/usr/bin/env python3
"""Deterministic Merge Gate for native-agent-stack v3.6.0."""

from __future__ import annotations

import re
import subprocess
import sys
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
        if rel == "scripts/merge_gate.py":
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


def main() -> int:
    leak_errors = _verify_zero_leaks()
    if leak_errors:
        for err in leak_errors:
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
    print("[MERGE-GATE PASS] All umbrella invariants & zero-leak gates verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
