#!/usr/bin/env python3
"""Render the skill invoke-rate refresh user units into an explicit review directory.

Pattern reference: tools/starred-maintenance/render_units.py on the #978 branch
(codex/ns2604-starred-convergence-20261010 at 2b5c9abe0d7b0f4cf56d8502f887261a0c8cc851):
absolute external paths, systemd argument quoting and a ':' ExecStart prefix.
The units run three existing producers and write the exact files that
tools/local-pages/source_policy.json grants the command-center page.
"""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parent / "systemd"
HOURLY, DAILY = "native-agent-skill-usage", "native-agent-skill-usage-codex-lanes"
UNITS = (f"{HOURLY}.service", f"{HOURLY}.timer", f"{DAILY}.service", f"{DAILY}.timer")
OUTPUTS = {"host": "skill-usage-host-latest.json", "codex": "skill-usage-codex-lanes-latest.json",
           "claude": "skill-usage-claude-lanes-latest.json"}
WINDOW = '/usr/bin/date -u -d "7 days ago" +%Y-%m-%dT%H:%M:%SZ'
NOW = "/usr/bin/date -u +%Y-%m-%dT%H:%M:%SZ"
# Each script writes "$2.tmp" (and "$2.full" before a projection) beside its
# destination, renames the finished report into place and removes the rest.
CLEANUP = '; status=$?; /usr/bin/rm -f "$2.full" "$2.tmp"; exit $status'
SCRIPTS = {
    "host": '/usr/bin/python3 -B "$0" --run-skill-doctor --claude-timeout 120 --codex-root "$1" --window 7 --out "$2.tmp"'
            ' && /usr/bin/mv -f "$2.tmp" "$2"' + CLEANUP,
    "codex": f'since=$({WINDOW}) && until=$({NOW})'
             ' && /usr/bin/python3 -B "$0" --lanes --codex-root "$1" --since "$since" --until "$until" --out "$2.full"'
             ' && /usr/bin/jq -c "del(.actors)" "$2.full" > "$2.tmp" && /usr/bin/mv -f "$2.tmp" "$2"' + CLEANUP,
    "claude": f'since=$({WINDOW}) && until=$({NOW})'
              ' && node "$0" --lanes-sweep --root "$1" --since "$since" --until "$until" > "$2.full"'
              ' && /usr/bin/jq -c -f "$3" "$2.full" > "$2.tmp" && /usr/bin/mv -f "$2.tmp" "$2"' + CLEANUP,
}
CALENDAR = re.compile(r"[A-Za-z0-9*/:,. -]{1,64}")


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

    systemd.syntax(7): double quotes and C escapes are accepted.
    systemd.unit(5): a literal percent sign is written as '%%'.
    """
    if any(unicodedata.category(char) in {"Cc", "Cs"} for char in value):
        raise ValueError("systemd arguments cannot contain control characters")
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%")
    return f'"{escaped}"'


def exec_start(script: str, arguments: list[str]) -> str:
    return ":/bin/sh -c " + " ".join(map(quote_argument, [script, *arguments]))


def render_units(repo: str | Path, skills_dir: str | Path, codex_root: str | Path, claude_root: str | Path,
                 on_calendar: str = "hourly", on_calendar_codex: str = "*-*-* 01:30:00") -> dict[str, str]:
    """Return unit text for the supplied clone and external locations."""
    repo = _absolute_path(repo, "--repo").resolve(strict=True)
    producers = {"skill_usage": repo / "tools/skill-usage/skill_usage.py",
                 "child_usage": repo / "examples/claude-native/workflows/child-usage.mjs",
                 "projection": repo / "tools/skill-usage/systemd/claude-lanes.jq"}
    for path in producers.values():
        if not path.is_file() or not _inside(path.resolve(), repo):
            raise ValueError(f"--repo must contain {path.relative_to(repo)} within the repository")
    skills = _external_path(skills_dir, "--skills-dir", repo)
    if skills.exists() and not skills.is_dir():
        raise ValueError("--skills-dir must name a directory")
    codex = _absolute_path(codex_root, "--codex-root").resolve()
    claude = _absolute_path(claude_root, "--claude-root").resolve()
    for value, label in ((on_calendar, "--on-calendar"), (on_calendar_codex, "--on-calendar-codex")):
        if not isinstance(value, str) or not CALENDAR.fullmatch(value):
            raise ValueError(f"{label} must be a plain systemd calendar expression")
    outputs = {name: str(skills / filename) for name, filename in OUTPUTS.items()}
    lines = {
        "@EXEC_HOST@": exec_start(SCRIPTS["host"], [str(producers["skill_usage"]), str(codex), outputs["host"]]),
        "@EXEC_CLAUDE_LANES@": exec_start(SCRIPTS["claude"], [str(producers["child_usage"]), str(claude), outputs["claude"],
                                                              str(producers["projection"])]),
        "@EXEC_CODEX_LANES@": exec_start(SCRIPTS["codex"], [str(producers["skill_usage"]), str(codex), outputs["codex"]]),
        "@ON_CALENDAR@": on_calendar, "@ON_CALENDAR_CODEX@": on_calendar_codex,
    }
    units = {}
    for name in UNITS:
        text = (TEMPLATES / f"{name}.in").read_text(encoding="utf-8")
        for placeholder, line in lines.items():
            text = text.replace(placeholder, line)
        units[name] = text
    return units


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, help="Absolute path of the live clone")
    parser.add_argument("--skills-dir", required=True, help="The state root's coordination/command-center/skills directory")
    parser.add_argument("--codex-root", required=True, help="Codex rollout root, such as an absolute ~/.codex/sessions")
    parser.add_argument("--claude-root", required=True, help="Claude transcript root, such as an absolute ~/.claude/projects")
    parser.add_argument("--on-calendar", default="hourly", help="Host and Claude-lanes timer (default: hourly)")
    parser.add_argument("--on-calendar-codex", default="*-*-* 01:30:00", help="Codex-lanes timer (default: daily at 01:30)")
    parser.add_argument("--output-dir", required=True, help="External review directory for rendered units")
    args = parser.parse_args(argv)
    try:
        units = render_units(args.repo, args.skills_dir, args.codex_root, args.claude_root, args.on_calendar, args.on_calendar_codex)
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
    print("Rendered " + ", ".join(UNITS) + " for review")
    return 0


if __name__ == "__main__":
    sys.exit(main())
