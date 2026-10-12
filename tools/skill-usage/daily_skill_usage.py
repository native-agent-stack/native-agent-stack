#!/usr/bin/env python3
"""Run the existing native reports and publish only skill names and counts.

The daily record has two halves, one per client, each its own unit with its own record and timeouts, so a slow Codex scan never leaves the Claude half
unmeasured and a timeout leaves only its own half unmeasured (docs/decisions/2026-10-12-skill-invoke-rate-timer.md):

  --half claude   the native /skill-doctor capture (Claude Code's lifetime uses per skill) and the child-usage.mjs --lanes-sweep Skill calls
  --half codex    the Codex rollout scan of the host report (windowed use counts) and the skill_usage.py --lanes report

Each half publishes `skill-invoke-rate-<half>-latest.json` (--out) and then refreshes the combined `skill-invoke-rate-latest.json` that the Fleet page reads
(--combined-out), merged from its own record and the other half's newest one (--other-record). A report file given on the command line projects a
combined record from files, without collecting.

The CC installs the rendered user timers after landing. Tests pass a stub runner;
lanes never invoke the real Claude client through this script.

Scheduled collection runs from a clone that is at a commit of origin/main: the
live clone is a detached worktree of origin/main (docs/decisions/2026-10-09-claude-review-worker.md),
so a branch name cannot be the test. A clone on a feature branch, or with
commits of its own, is refused, and so is rendering the units for one.
"""
import argparse
from datetime import timedelta
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

import skill_usage

ROOT = Path(__file__).resolve().parents[2]
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,100}\Z")
KINDS = ("skill_invoke_rate_report", "codex_lane_usage_report", "claude_child_lane_usage")
SCHEMA = "skill-invoke-rate-daily/1"
HALVES = ("claude", "codex")
UNIT_FILES = tuple(f"skill-invoke-rate-{half}.{kind}" for half in HALVES for kind in ("service", "timer"))
HALF_KEYS = {"claude": ("host", "claude"), "codex": ("codex",), "all": ("host", "codex", "claude")}
CLAUDE_ROW_FIELDS = ("claude_uses_lifetime", "wiring")
CODEX_ROW_FIELDS = ("codex_use", "codex_skill_md_reads", "codex_name_mentions")
# Seconds a command of the daily run may take before it is abandoned (its report is then None and only the key it feeds is unmeasured). Measured 2026-10-12 as transient user units, one command at a time, on
# the host (64 CPUs, 1 minute load 12 to 19; docs/decisions/2026-10-12-skill-invoke-rate-timer.md): the /skill-doctor capture 19.9 s (1.5 GB peak; 58 to 62 s at three runnable threads per CPU); the Claude
# lanes sweep 2 min 18 s (1.8 GB peak; 198 MB of JSON on stdout, 513 MB to parse); the host report's Codex scan 1 min 10 s (2.8 GB peak, 3,234 rollout files); the Codex lanes scan 25 min 47 s (1.8 GB peak,
# 29 CPU minutes). The limits: the capture its own limit (skill_usage.DEFAULT_CLAUDE_TIMEOUT, 300 s) plus a minute, the two one-core commands 600 s each (4.3 and 8.5 times their wall; a CPU-bound command takes
# about three times as long at three runnable threads per CPU), and the Codex lanes scan twice its wall, the command center's rule of 2026-10-12 (a scan that is slower than that is the case for an incremental scan).
CAPTURE_MARGIN = 60           # added to the capture's own limit (skill_usage.DEFAULT_CLAUDE_TIMEOUT, or --claude-timeout): start-up and the report
TIMEOUTS = {"claude_sweep": 600, "codex_host": 600, "codex_lanes": 3120}


def count(value):
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def counts(value):
    if not isinstance(value, dict):
        return []
    return [{"name": name, "count": count(number)} for name, number in sorted(value.items())
            if isinstance(name, str) and NAME.fullmatch(name) and count(number) is not None]


def project_reports(host, codex, claude, *, now, window, half="all"):
    """Project native aggregates, preserving client/group and measurement meaning. `half` names the client halves the record is for (HALF_KEYS): `measured` holds only their keys, so a half is not
    unmeasured for want of the other half's report."""
    use_groups = host.get("codex_use_groups", {}).get(str(window), {}) if isinstance(host, dict) and isinstance(host.get("codex_use_groups"), dict) else {}
    codex_state = host.get("codex", {}) if isinstance(host, dict) else {}
    codex_measured = (isinstance(codex, dict) and codex.get("kind") == KINDS[1] and bool(use_groups)
                      and isinstance(codex_state, dict) and codex_state.get("measured") is True
                      and (count(codex_state.get("roots_count")) or 0) > 0
                      and (count(codex_state.get("files_scanned")) or 0) > 0)
    host_rows = None
    baseline = json.loads((ROOT / "adoption/skills/claude-routing/trigger-baseline.json").read_text())
    wiring = {row["name"]: row for row in baseline.get("skills", [])}
    if isinstance(host, dict) and host.get("kind") == KINDS[0] and isinstance(host.get("skills"), list):
        host_rows = []
        for row in host["skills"]:
            if not isinstance(row, dict) or not isinstance(row.get("name"), str) or not NAME.fullmatch(row["name"]):
                continue
            c = row.get("claude") if isinstance(row.get("claude"), dict) else {}
            x = row.get("codex") if isinstance(row.get("codex"), dict) else {}
            days = x.get("counts", {}).get(str(window), {})
            host_rows.append({"name": row["name"], "claude_uses_lifetime": count(c.get("uses")),
                              "wiring": wiring.get(row["name"], {}).get("status"),
                              "codex_use": count(x.get("use_counts", {}).get(str(window))) if codex_measured else None,
                              "codex_skill_md_reads": count(days.get("skill_md_reads")) if codex_measured else None,
                              "codex_name_mentions": count(days.get("name_mentions")) if codex_measured else None})
    lanes = []
    def lane(client, name, aggregate, field, use=None):
        if NAME.fullmatch(name) and isinstance(aggregate, dict):
            rows = counts(aggregate.get(field))
            if client == "codex":
                if not codex_measured:
                    use = None
                raw = {row["name"]: row["count"] for row in rows}
                rows = [{"name": skill, "count": count(use.get(skill, 0)) if isinstance(use, dict) else None,
                         "raw_reads": raw.get(skill, 0)} for skill in sorted(set(raw) | set(use or {}))
                        if isinstance(skill, str) and NAME.fullmatch(skill)]
            lanes.append({"client": client, "lane": name, "skills": rows,
                          "metric": "use" if client == "codex" else "skill_calls"})
    if isinstance(codex, dict) and codex.get("kind") == KINDS[1]:
        groups = codex.get("groups", {})
        for name in ("workers", "negative_controls", "unclassified"):
            if name in groups:
                lane("codex", name, groups[name], "skill_md_reads", use_groups.get(name))
        for name, group in groups.get("workers_by_role", {}).items():
            lane("codex", "role:" + name, group, "skill_md_reads", use_groups.get("workers_by_role", {}).get(name))
        for name, group in groups.get("workers_by_kind", {}).items():
            lane("codex", "kind:" + name, group, "skill_md_reads", use_groups.get("workers_by_kind", {}).get(name))
    if isinstance(claude, dict) and claude.get("kind") == KINDS[2]:
        for spawn, agents in claude.get("groups", {}).get("by_spawn_and_agent_type", {}).items():
            for name, group in agents.items():
                lane("claude", spawn + ":" + name, group, "skill_calls")
        if isinstance(claude.get("main"), dict):
            lane("claude", "main", claude["main"], "skill_calls")
    measured = {"host": host_rows is not None and host.get("claude", {}).get("measured") is True,
                "codex": codex_measured,
                "claude": isinstance(claude, dict) and claude.get("kind") == KINDS[2]}
    return {"schema": SCHEMA, "half": half, "generated_at": now, "window_days": window,
            "host": host_rows, "lanes": lanes if codex is not None or claude is not None else None,
            "zero_use": {"codex": [row["name"] for row in host_rows or [] if row["codex_use"] == 0],
                         "claude_host_lifetime": [row["name"] for row in host_rows or [] if row["claude_uses_lifetime"] == 0]},
            "codex_bulk_scan_limit": host.get("codex_use_policy", {}).get("max_distinct_skill_reads") if isinstance(host, dict) and isinstance(host.get("codex_use_policy"), dict) else None,
            "measured": {key: measured[key] for key in HALF_KEYS[half]}}


class CloneRefused(ValueError):
    """The clone is not at a commit of origin/main. The message is fixed text, safe to print."""


def on_reviewed_main(root=ROOT):
    """Whether the clone's HEAD is origin/main or one of its ancestors: true for the live clone (a detached worktree of origin/main) and for a clone on branch main, false for a feature branch and for any
    commit of the clone's own. A clone without an origin/main cannot be judged and is refused."""
    try:
        done = subprocess.run(["git", "merge-base", "--is-ancestor", "HEAD", "origin/main"], cwd=root, capture_output=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as error:
        raise CloneRefused("git cannot compare the clone with origin/main") from error
    if done.returncode not in (0, 1):
        raise CloneRefused("the clone has no origin/main to compare with")
    return done.returncode == 0


def require_reviewed_main(root=ROOT):
    if not on_reviewed_main(root):
        raise CloneRefused("the clone is not at a commit of origin/main (a feature branch, or commits of its own); use the live clone, a detached worktree of origin/main")


def half_plan(half, roots, *, window, now, node="node", claude_timeout=None):
    """The native commands of one half, as (slot, kind, argv, timeout seconds); the slot is where the report goes in project_reports' (host, codex, claude).
    The Claude half asks the host report for the /skill-doctor capture only (no Codex root: its Codex part is then unmeasured, which that half does not count) and sweeps the Claude transcripts;
    the Codex half asks the host report for the Codex scan only (no Claude source) and runs the lanes report."""
    since, until = (now - timedelta(days=window)).isoformat(), now.isoformat()
    script = str(ROOT / "tools/skill-usage/skill_usage.py")
    if half == "claude":
        capture = claude_timeout if claude_timeout is not None else skill_usage.DEFAULT_CLAUDE_TIMEOUT
        timeout_args = [] if claude_timeout is None else ["--claude-timeout", str(claude_timeout)]
        return [("host", KINDS[0], [sys.executable, script, "--run-skill-doctor", *timeout_args, "--window", str(window), "--now", until, "--json"], capture + CAPTURE_MARGIN),
                ("claude", KINDS[2], [node, str(ROOT / "examples/claude-native/workflows/child-usage.mjs"), "--lanes-sweep",
                                      *[arg for root in roots for arg in ("--root", str(root))], "--since", since, "--until", until], TIMEOUTS["claude_sweep"])]
    if half == "codex":
        codex_args = [arg for root in roots for arg in ("--codex-root", str(root))]
        return [("host", KINDS[0], [sys.executable, script, *codex_args, "--window", str(window), "--now", until, "--json"], TIMEOUTS["codex_host"]),
                ("codex", KINDS[1], [sys.executable, script, "--lanes", *codex_args, "--since", since, "--until", until, "--now", until, "--json"], TIMEOUTS["codex_lanes"])]
    raise ValueError("unknown half")


def half_budget(half, claude_timeout=None):
    """Seconds the commands of a half may take in all: what the unit's TimeoutStartSec must exceed."""
    return sum(timeout for _, _, _, timeout in half_plan(half, [Path("x")], window=7, now=skill_usage.now_utc(), claude_timeout=claude_timeout))


def collect_half(half, roots, *, window, now, node="node", runner=subprocess.run, claude_timeout=None):
    """(host, codex, claude) native reports of one half; the other half's slots stay None, and a command that fails, times out or answers with another kind leaves its own slot None."""
    reports = {"host": None, "codex": None, "claude": None}
    for slot, kind, command, timeout in half_plan(half, roots, window=window, now=now, node=node, claude_timeout=claude_timeout):
        try:
            result = runner(command, cwd=ROOT, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout)
            report = json.loads(result.stdout) if result.returncode == 0 else None
            reports[slot] = report if isinstance(report, dict) and report.get("kind") == kind else None
        except (OSError, subprocess.TimeoutExpired, ValueError):
            pass  # Native errors and transcript text never become page content.
    return reports["host"], reports["codex"], reports["claude"]


def half_record(value, half):
    return value if isinstance(value, dict) and value.get("schema") == SCHEMA and value.get("half") == half else None


def merge_halves(claude, codex):
    """The record the Fleet page reads (schema skill-invoke-rate-daily/1, no `half`) from the newest record of each half. A half that is absent, or is not a record of its half, contributes nothing and is not
    measured. The Claude half owns the Claude fields of a skill and its wiring, the Codex half the Codex ones; `generated_at` is the older of the two, so the page never shows a stale half as fresh."""
    claude, codex = half_record(claude, "claude"), half_record(codex, "codex")
    by_half = {"claude": {row["name"]: row for row in (claude or {}).get("host") or [] if isinstance(row, dict) and isinstance(row.get("name"), str) and NAME.fullmatch(row["name"])},
               "codex": {row["name"]: row for row in (codex or {}).get("host") or [] if isinstance(row, dict) and isinstance(row.get("name"), str) and NAME.fullmatch(row["name"])}}
    names = list(by_half["claude"]) + [name for name in by_half["codex"] if name not in by_half["claude"]]
    host = [{"name": name, **{field: by_half["claude"].get(name, {}).get(field) for field in CLAUDE_ROW_FIELDS},
             **{field: by_half["codex"].get(name, {}).get(field) for field in CODEX_ROW_FIELDS}} for name in names] if names else None
    lanes = [lane for source, client in ((claude, "claude"), (codex, "codex")) for lane in (source or {}).get("lanes") or []
             if isinstance(lane, dict) and lane.get("client") == client]
    stamps = [skill_usage.parse_iso(record["generated_at"]) for record in (claude, codex) if record and isinstance(record.get("generated_at"), str)]
    present = claude or codex
    measured = {"host": bool(claude and claude.get("measured", {}).get("host") is True), "codex": bool(codex and codex.get("measured", {}).get("codex") is True),
                "claude": bool(claude and claude.get("measured", {}).get("claude") is True)}
    return {"schema": SCHEMA, "half": "all", "generated_at": min(stamps).isoformat() if stamps else None, "window_days": present.get("window_days") if present else None,
            "host": host, "lanes": lanes if (claude and claude.get("lanes") is not None) or (codex and codex.get("lanes") is not None) else None,
            "zero_use": {"codex": [row["name"] for row in host or [] if row["codex_use"] == 0],
                         "claude_host_lifetime": [row["name"] for row in host or [] if row["claude_uses_lifetime"] == 0]},
            "codex_bulk_scan_limit": codex.get("codex_bulk_scan_limit") if codex else None,
            "halves": {"claude": claude.get("generated_at") if claude else None, "codex": codex.get("generated_at") if codex else None},
            "measured": measured}


def refresh_combined(combined, own, other):
    """Write the combined record from this half's record and the other half's newest one (a missing or unreadable file is an absent half). Never raises: the half's own record is what the unit's exit
    status stands for."""
    try:
        try:
            newest = json.loads(other.read_text()) if other else None
        except (OSError, ValueError):
            newest = None
        records = {own.get("half"): own}
        records.setdefault("claude" if own.get("half") == "codex" else "codex", newest)
        publish(combined.absolute(), merge_halves(records.get("claude"), records.get("codex")))
        return True
    except (OSError, ValueError, KeyError, TypeError):
        return False


def publish(path, report):
    if skill_usage.inside_git_work_tree(path.parent) or path.is_relative_to(ROOT):
        raise ValueError("report destination must be outside git worktrees")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, temp = tempfile.mkstemp(prefix=".skill-usage-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w") as stream:
            json.dump(report, stream, indent=2, sort_keys=True)
            stream.write("\n")
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def render_units(destination, repository, python, node):
    destination.mkdir(parents=True, exist_ok=True)
    values = {"@REPOSITORY@": str(repository), "@PYTHON@": str(python), "@NODE@": str(node)}
    for value in values.values():
        if not Path(value).is_absolute() or any(char in value for char in ('\n', '\r', '"', '\\')):
            raise ValueError("unit values must be absolute paths without unit quoting characters")
    for name in UNIT_FILES:
        text = (ROOT / "adoption/templates/systemd" / name).read_text()
        for key, value in values.items():
            text = text.replace(key, value.replace("%", "%%").replace("$", "$$"))
        (destination / name).write_text(text)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--half", choices=HALVES, help="the client half to collect (required unless report files are given): claude = /skill-doctor capture + Claude lanes sweep, codex = Codex rollout scan + lanes report")
    parser.add_argument("--codex-root", action="append", type=Path, default=[])
    parser.add_argument("--claude-root", action="append", type=Path, default=[])
    parser.add_argument("--window", type=int, default=7)
    parser.add_argument("--claude-timeout", type=int, metavar="SECONDS",
                        help=f"seconds the /skill-doctor capture may take (default: skill_usage.py's, {skill_usage.DEFAULT_CLAUDE_TIMEOUT})")
    parser.add_argument("--now")
    parser.add_argument("--node", default="node")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--combined-out", type=Path, help="after the half's record is written, refresh this combined record (what the Fleet page reads) from it and --other-record")
    parser.add_argument("--other-record", type=Path, help="the other half's record, merged into --combined-out when it exists")
    parser.add_argument("--host-report", type=Path)
    parser.add_argument("--codex-lanes-report", type=Path)
    parser.add_argument("--claude-lanes-report", type=Path)
    parser.add_argument("--render-units", type=Path)
    parser.add_argument("--repository", type=Path, default=ROOT)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    args = parser.parse_args(argv)
    try:
        if args.render_units:
            node = shutil.which(args.node)
            if not node:
                raise ValueError("node executable is unavailable")
            require_reviewed_main(args.repository)   # a unit rendered for a clone that the run refuses would fail every day
            render_units(args.render_units, args.repository, args.python, Path(node))
            return 0
        if not 1 <= args.window <= 366:
            raise ValueError("invalid window")
        if args.claude_timeout is not None and not 1 <= args.claude_timeout <= 3600:
            raise ValueError("invalid timeout")
        now = skill_usage.parse_iso(args.now) if args.now else skill_usage.now_utc()
        sources = (args.host_report, args.codex_lanes_report, args.claude_lanes_report)
        half = args.half or "all"
        if any(sources):
            reports = tuple(json.loads(path.read_text()) if path else None for path in sources)
        else:
            if not args.half:
                raise ValueError("a half is required")
            roots = args.claude_root if args.half == "claude" else args.codex_root
            if not roots:
                raise ValueError("the root of the half's client must be explicit")
            require_reviewed_main(ROOT)
            reports = collect_half(args.half, roots, window=args.window, now=now, node=args.node, claude_timeout=args.claude_timeout)
        report = project_reports(*reports, now=now.isoformat(), window=args.window, half=half)
        if args.out:
            publish(args.out.absolute(), report)
        else:
            print(json.dumps(report, indent=2, sort_keys=True))
        if args.combined_out and args.half and not refresh_combined(args.combined_out, report, args.other_record):
            print("daily skill usage: the combined record was not refreshed", file=sys.stderr)
        return 0 if all(report["measured"].values()) else 1
    except CloneRefused as error:
        print(f"daily skill usage refused: {error}", file=sys.stderr)
        return 2
    except (OSError, ValueError, subprocess.SubprocessError):
        print("daily skill usage unavailable; inspect the native collector separately", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
