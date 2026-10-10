#!/usr/bin/env python3
"""Render a weekly public-stars user timer into an explicit staging directory."""

from __future__ import annotations

import argparse
import sys
import unicodedata
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parent / "systemd"
SERVICE = "native-agent-newstars.service"
TIMER = "native-agent-newstars.timer"


def _absolute_path(value: str | Path, label: str) -> Path:
    text = str(value)
    if any(unicodedata.category(char) in {"Cc", "Cs"} for char in text):
        raise ValueError(f"{label} contains unsupported control characters")
    path = Path(text)
    if not path.is_absolute():
        raise ValueError(f"{label} must be an absolute path; expand ~ in the shell")
    return path


def _inside(path: Path, parent: Path) -> bool:
    return path == parent or parent in path.parents


def _external_path(value: str | Path, label: str, repo: Path) -> Path:
    path = _absolute_path(value, label)
    resolved = path.resolve()
    if _inside(path, repo) or _inside(resolved, repo):
        raise ValueError(f"{label} must stay outside the repository, including symlinks")
    return resolved


def quote_argument(value: str) -> str:
    """Quote one systemd argument; ExecStart's ':' keeps dollar signs literal.

    systemd.syntax(7), v259.5: double quotes and C escapes are accepted.
    systemd.unit(5): a literal percent sign is written as '%%'.
    """
    if any(unicodedata.category(char) in {"Cc", "Cs"} for char in value):
        raise ValueError("systemd arguments cannot contain control characters")
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%")
    return f'"{escaped}"'


def render_units(
    repo: str | Path, state_dir: str | Path, questions_file: str | Path
) -> dict[str, str]:
    """Return unit text for the supplied clone and external runtime locations."""
    repo = _absolute_path(repo, "--repo").resolve(strict=True)
    if not repo.is_dir():
        raise ValueError("--repo must name a repository directory")
    builder = repo / "scripts" / "build_ecosystem.py"
    if not builder.is_file() or not _inside(builder.resolve(), repo):
        raise ValueError("--repo must contain scripts/build_ecosystem.py within the repository")
    state = _external_path(state_dir, "--state-dir", repo)
    questions = _external_path(questions_file, "--questions-file", repo)
    if _inside(questions, state):
        raise ValueError("--questions-file must stay outside the state directory, including symlinks")
    if state.exists() and not state.is_dir():
        raise ValueError("--state-dir must name a directory")
    if questions.exists() and not questions.is_file():
        raise ValueError("--questions-file must name a file")

    arguments = [
        "-B", str(builder), "--root", str(repo), "--refresh-stars",
        "--starred-state-dir", str(state), "--newstars-questions", str(questions),
    ]
    # ':' suppresses environment-variable expansion; no shell interprets argv.
    exec_start = ":/usr/bin/python3 " + " ".join(map(quote_argument, arguments))
    service = (TEMPLATES / f"{SERVICE}.in").read_text(encoding="utf-8")
    timer = (TEMPLATES / f"{TIMER}.in").read_text(encoding="utf-8")
    return {SERVICE: service.replace("@EXEC_START@", exec_start), TIMER: timer}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, help="Absolute path of the live clone")
    parser.add_argument("--state-dir", required=True, help="External snapshot and receipt directory")
    parser.add_argument("--questions-file", required=True, help="External co-op lane questions file")
    parser.add_argument("--output-dir", required=True, help="External review directory for rendered units")
    args = parser.parse_args(argv)
    try:
        units = render_units(args.repo, args.state_dir, args.questions_file)
        repo = Path(args.repo).resolve(strict=True)
        output = _external_path(args.output_dir, "--output-dir", repo)
        if output.exists() and not output.is_dir():
            raise ValueError("--output-dir must name a directory")
        if any((output / name).is_symlink() for name in units):
            raise ValueError("rendered unit destinations cannot be symlinks")
        output.mkdir(parents=True, exist_ok=True, mode=0o700)
        for name, text in units.items():
            (output / name).write_text(text, encoding="utf-8")
    except (OSError, ValueError) as error:
        parser.exit(1, f"Cannot render units: {error}\n")
    print("Rendered native-agent-newstars.service and native-agent-newstars.timer for review")
    return 0


if __name__ == "__main__":
    sys.exit(main())
