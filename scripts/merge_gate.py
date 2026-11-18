#!/usr/bin/env python3
"""Deterministic Merge Gate for native-agent-stack v3.0.0."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    steps: list[list[str]] = [
        [sys.executable, "scripts/architecture_catalog.py", "--check"],
        [sys.executable, "-m", "native_agent_stack.umbrella", "--check"],
        [sys.executable, "-m", "ruff", "check", "."],
        [sys.executable, "-m", "ruff", "format", "--check", "."],
        [sys.executable, "-m", "ty", "check", "src", "scripts", "tests"],
        [sys.executable, "-m", "pytest", "-q"],
    ]
    for cmd in steps:
        proc = subprocess.run(cmd, cwd=ROOT, check=False)
        if proc.returncode != 0:
            return proc.returncode
    print("[MERGE-GATE PASS] All v3.0.0 umbrella invariants verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
