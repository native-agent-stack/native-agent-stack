#!/usr/bin/env python3
"""Universal Cross-OS SOTA Git Hook Runner (`ADR-0046`).

Enforces fail-closed One-Harness cleanliness across all 18 SOTA ecosystem repositories
regardless of which agent runtime (Antigravity, Claude Code, Codex, OpenCode, DSH, OMP,
Orca workers) or human executes `git commit` or `git push`.

Non-SOTA repositories outside the ecosystem (without `UPSTREAM.md` + `scripts/merge_gate.py`)
pass through untouched so global `core.hooksPath` never disrupts unrelated repos.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

SELF_SKIP_BASENAMES = frozenset(
    {
        "merge_gate.py",
        "run_sota_git_hook.py",
        "sync_tier0_harness_and_master_adrs.py",
        "sync_ecosystem_full_adrs.py",
        "one_harness_cleanliness_doctor.py",
    }
)

STAGED_LEAK_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("Broker Account ID", re.compile(r"\b(?:PA|DU)(?=[0-9A-Z]*[0-9])[0-9A-Z]{8,14}\b")),
    ("Alpaca Key Prefix", re.compile(r"\b(?:AK|PK)[0-9A-Z]{16,28}\b")),
    ("Private Key Header", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("macOS Home Path", re.compile(r"(?<![A-Za-z0-9_*])/" + r"Users/[A-Za-z0-9._-]+/")),
    ("Linux Home Path", re.compile(r"(?<![A-Za-z0-9_*])/home/[A-Za-z0-9._-]+/")),
    ("Windows Home Path", re.compile(r"[A-Za-z]:[/\\]Users[/\\][A-Za-z0-9._-]+[/\\]")),
)


def _run(cmd: list[str], *, cwd: Path, capture: bool = True) -> subprocess.CompletedProcess[str]:
    if sys.platform == "win32":
        return subprocess.run(
            cmd,
            cwd=cwd,
            text=True,
            capture_output=capture,
            check=False,
            creationflags=CREATE_NO_WINDOW,
        )
    return subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        capture_output=capture,
        check=False,
    )


def _repo_root() -> Path | None:
    proc = _run(["git", "rev-parse", "--show-toplevel"], cwd=Path.cwd())
    if proc.returncode != 0 or not proc.stdout.strip():
        return None
    return Path(proc.stdout.strip()).resolve()


def _is_sota_repo(root: Path) -> bool:
    return (root / "UPSTREAM.md").is_file() and (root / "scripts" / "merge_gate.py").is_file()


def _run_pre_commit(root: Path) -> int:
    if not _is_sota_repo(root):
        return 0

    errors: list[str] = []

    # 1. Enforce noreply author email on SOTA repos
    email_env = os.environ.get("GIT_AUTHOR_EMAIL", "").strip()
    if email_env:
        email = email_env
    else:
        ep = _run(["git", "config", "--get", "user.email"], cwd=root)
        email = ep.stdout.strip()
    if email and "@users.noreply.github.com" not in email.lower():
        errors.append(f"Author email must use @users.noreply.github.com on SOTA repos (got: {email})")

    # 2. Scan staged added lines for secrets / broker IDs / 3-OS home paths
    diff = _run(["git", "diff", "--cached", "--unified=0", "--no-color"], cwd=root)
    current_file = ""
    for line in diff.stdout.splitlines():
        if line.startswith("+++ b/"):
            current_file = line[6:].strip()
            continue
        if not line.startswith("+") or line.startswith("+++"):
            continue
        base = Path(current_file).name if current_file else ""
        if base in SELF_SKIP_BASENAMES or base.startswith("test_"):
            continue
        added = line[1:]
        for label, rx in STAGED_LEAK_PATTERNS:
            if rx.search(added):
                errors.append(f"{current_file}: staged addition triggered {label}")

    # 3. Run gitleaks on staged changes if installed
    gitleaks_bin = shutil.which("gitleaks")
    if gitleaks_bin:
        gl = _run([gitleaks_bin, "protect", "--staged", "--no-banner", "--redact"], cwd=root)
        if gl.returncode != 0:
            detail = (gl.stderr or gl.stdout or "").strip().splitlines()[:6]
            errors.append("gitleaks protect --staged failed: " + (" | ".join(detail) or "secret detected"))

    if errors:
        for err in errors:
            print(f"[SOTA-PRE-COMMIT FAIL] {err}", file=sys.stderr)
        return 1
    return 0


def _resolve_merge_gate_cmd(root: Path) -> list[str]:
    win_venv = root / ".venv" / "Scripts" / "python.exe"
    if win_venv.is_file():
        return [str(win_venv), "scripts/merge_gate.py"]
    posix_venv = root / ".venv" / "bin" / "python"
    if posix_venv.is_file():
        return [str(posix_venv), "scripts/merge_gate.py"]
    uv_bin = shutil.which("uv")
    if uv_bin and (root / "pyproject.toml").is_file():
        return [uv_bin, "run", "python", "scripts/merge_gate.py"]
    return [sys.executable, "scripts/merge_gate.py"]


def _run_pre_push(root: Path) -> int:
    if not _is_sota_repo(root):
        return 0
    cmd = _resolve_merge_gate_cmd(root)
    print(f"[SOTA-PRE-PUSH] Running Tier-0 merge_gate in {root.name}: {' '.join(cmd)}")
    proc = _run(cmd, cwd=root, capture=False)
    if proc.returncode != 0:
        print(
            f"[SOTA-PRE-PUSH FAIL] {root.name}/scripts/merge_gate.py exited {proc.returncode}; push blocked.",
            file=sys.stderr,
        )
        return proc.returncode
    return 0


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if not args or args[0] not in {"pre-commit", "pre-push"}:
        print("Usage: run_sota_git_hook.py <pre-commit|pre-push>", file=sys.stderr)
        return 2
    root = _repo_root()
    if root is None:
        return 0
    if args[0] == "pre-commit":
        return _run_pre_commit(root)
    return _run_pre_push(root)


if __name__ == "__main__":
    raise SystemExit(main())
