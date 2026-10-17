#!/usr/bin/env python3
"""Publish the daily token-rate projection: per-lane counts, token numerators and model ids only.

Inputs are the native collectors this repository already runs, unchanged: Claude Code's
examples/claude-native/workflows/child-usage.mjs --lanes-sweep (sweepLanes, child-usage.mjs:3224) and Codex's
tools/skill-usage/skill_usage.py --lanes (scan_codex_lanes, skill_usage.py:2201), built and run through
daily_skill_usage.lane_commands and run_reports, plus Muse file-fence receipts (schema muse-file-fence/1,
tools/muse_file_fence.py:539-546) read from explicit roots only. Outputs, both outside every git worktree:
token-rate-daily/1 (the closed-day rollup and today so far) and token-rate-history/1 (one row per closed UTC
day; a complete row is never rewritten). Every value is rebuilt from named fields: counts, token numerators,
listed MCP server ids and model ids that match MODEL. Transcript text, prompts, tool inputs and outputs,
paths, session ids and agent-type names never reach either file. The CC installs the rendered user timer
after landing; tests pass a stub runner or replayed reports and never run a live client.
"""
from __future__ import annotations

import argparse
from datetime import date as Date, datetime, timedelta, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

import daily_skill_usage
import skill_usage

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "token-rate-daily/1"
HISTORY_SCHEMA = "token-rate-history/1"
LANES = ("claude:main", "claude:agent_tool", "claude:workflow", "gpt:codex", "muse:muse")
CLAUDE_LANES = {"claude:main": "main", "claude:agent_tool": "agent_tool", "claude:workflow": "workflow"}
REASONS = ("collector_failed", "not_configured", "no_usage_keys", "no_rows_in_window")
KINDS = ("codex_lane_usage_report", "claude_child_lane_usage")
NUMERATORS = ("actors", "actors_complete", "tool_calls", "mcp", "mcp_other", "rtk", "spawn", "models", "usage",
              "advisor", "codex_usage", "runs")
CLAUDE_USAGE = ("input", "output", "cache_read", "cache_creation", "cache_creation_5m", "cache_creation_1h",
                "cache_creation_ttl_unknown")
# Codex native counters (openai/codex rust-v0.157.1 protocol.rs:2234-2310, as skill_usage.CODEX_COUNTERS cites them).
CODEX_USAGE = {"input": "input_tokens", "cached_input": "cached_input_tokens", "cache_write": "cache_write_input_tokens",
               "output": "output_tokens", "reasoning_output": "reasoning_output_tokens"}
CLAUDE_COUNTERS = {"input": "input_tokens", "output": "output_tokens", "cache_read": "cache_read_input_tokens",
                   "cache_creation": "cache_creation_input_tokens"}
MODEL = re.compile(r"(claude|gpt|muse)-[a-z0-9][a-z0-9.\-]{0,60}")
MUSE_SCHEMA = "muse-file-fence/1"
MUSE_COMPLETED = "run.terminal.completed"
MUSE_RECEIPT_BYTES = 1024 * 1024
ROLE_TOOL_SETS = ROOT / "docs/role-tool-sets.json"
KERNEL = ROOT / "examples/claude-native/workflows/child-usage.mjs"
UNITS = ("token-rate.service", "token-rate.timer")
CAP = 400
ROLLUP_DAYS = 7
MAX_MODELS = 32
FAILURE = "daily token usage unavailable; inspect the native collector separately"
_GITHUB = re.compile(r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
count, NAME = daily_skill_usage.count, daily_skill_usage.NAME


def canonical(value) -> bytes:
    """The canonical JSON every digest here covers."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def digest(value) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def stamp(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def midnight(moment: datetime) -> datetime:
    return moment.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)


def day_window(day: str) -> tuple[datetime, datetime]:
    start = datetime.combine(Date.fromisoformat(day), datetime.min.time(), timezone.utc)
    return start, start + timedelta(days=1)


# ---------------------------------------------------------------- servers
def load_servers(path: Path = ROLE_TOOL_SETS) -> tuple[dict, list, str]:
    """The MCP server names this projection may publish: docs/role-tool-sets.json tools[] ids with a GitHub repository,
    plus the native names its server_aliases fold into them. Returns (native name -> tool id, servers, file sha256)."""
    raw = Path(path).read_bytes()
    document = json.loads(raw)
    servers, aliases = [], {}
    for tool in document.get("tools") or []:
        if (isinstance(tool, dict) and isinstance(tool.get("tool_id"), str) and NAME.fullmatch(tool["tool_id"])
                and isinstance(tool.get("repository"), str) and _GITHUB.fullmatch(tool["repository"])):
            servers.append({"name": tool["tool_id"], "repository": tool["repository"]})
            aliases[tool["tool_id"]] = tool["tool_id"]
    for tool_id, entry in (document.get("server_aliases") or {}).items():
        if tool_id not in aliases or not isinstance(entry, dict):
            continue
        names = [entry.get(key) for key in ("observed_native_server_name", "trial_native_name", "portable_native_name")]
        observed = entry.get("observed_native_server_names")
        names += list(observed.values()) if isinstance(observed, dict) else []
        for name in names:
            if isinstance(name, str) and NAME.fullmatch(name):
                aliases.setdefault(name, tool_id)
    return aliases, sorted(servers, key=lambda row: row["name"]), hashlib.sha256(raw).hexdigest()


def fold(calls, aliases: dict) -> tuple[dict | None, int | None]:
    """Server call counts under their listed tool ids; every other server name is counted in other, never kept."""
    if not isinstance(calls, dict):
        return None, None
    named, other = {}, 0
    for name, number in calls.items():
        number = count(number)
        if number is None:
            continue
        tool = aliases.get(name) if isinstance(name, str) else None
        if tool is None:
            other += number
        else:
            named[tool] = named.get(tool, 0) + number
    return dict(sorted(named.items())), other


def _models(names) -> dict:
    """Counts per model id, keeping only ids that fully match MODEL; at most MAX_MODELS, most frequent first."""
    counted: dict = {}
    for name in names:
        if isinstance(name, str) and MODEL.fullmatch(name):
            counted[name] = counted.get(name, 0) + 1
    kept = sorted(counted.items(), key=lambda item: (-item[1], item[0]))[:MAX_MODELS]
    return dict(sorted(kept))


def _sum(values) -> int | None:
    values = list(values)
    return None if any(value is None for value in values) else sum(values)


def unmeasured(reason: str) -> dict:
    """A lane whose collector did not run: every numerator unknown, with its reason code."""
    if reason not in REASONS:
        raise ValueError("unknown reason code")
    return {**dict.fromkeys(NUMERATORS), "spawn": {"children": None, "codex_subagent_sessions": None}, "models": {},
            "unmeasured": reason}


# ---------------------------------------------------------------- lanes
def _claude_complete(actor) -> bool:
    """An actor counts toward usage only when the kernel marks its usage complete and every counter is a count."""
    usage = ((actor.get("measurement") or {}).get("usage") or {}) if isinstance(actor, dict) else {}
    messages = usage.get("messages")
    return (usage.get("complete") is True and isinstance(messages, list)
            and all(isinstance(message, dict) and all(count((message.get("usage") or {}).get(key)) is not None for key in CLAUDE_COUNTERS.values())
                    for message in messages))


def _claude_usage(actors: list) -> tuple[dict, dict, int]:
    """Usage summed over complete actors (transcriptUsage, child-usage.mjs:2507-2565); null fields when none is complete.

    A message's cache writes count by TTL only when its 5m and 1h split (splitOf/rowSplit, :2496-2503) is known and adds
    up to its cache_creation_input_tokens; otherwise all of them count as TTL unknown, so 5m + 1h + unknown = cache_creation
    (the primary docs state cache_creation_input_tokens is the sum of the cache_creation values). Advisor sub-inference,
    which the kernel keeps apart in advisor_totals, is summed apart too: it is never added to the token columns.
    """
    complete = [actor for actor in actors if _claude_complete(actor)]
    if not complete:
        return dict.fromkeys(CLAUDE_USAGE), dict.fromkeys(("input", "output")), 0
    totals = dict.fromkeys(CLAUDE_USAGE, 0)
    advisor = {"input": 0, "output": 0}
    for actor in complete:
        advised = actor["measurement"]["usage"].get("advisor_totals") if isinstance(actor["measurement"]["usage"].get("advisor_totals"), dict) else {}
        for field, key in (("input", "input_tokens"), ("output", "output_tokens")):
            advisor[field] = None if advisor[field] is None or count(advised.get(key, 0)) is None else advisor[field] + count(advised.get(key, 0))
        for message in actor["measurement"]["usage"]["messages"]:
            usage = message["usage"]
            for field, key in CLAUDE_COUNTERS.items():
                totals[field] += usage[key]
            creation, five, hour = usage["cache_creation_input_tokens"], count(message.get("cache_creation_5m")), count(message.get("cache_creation_1h"))
            if five is not None and hour is not None and five + hour == creation:
                totals["cache_creation_5m"] += five
                totals["cache_creation_1h"] += hour
            else:
                totals["cache_creation_ttl_unknown"] += creation
    return totals, advisor, len(complete)


def claude_lanes(sweep, aliases: dict) -> tuple[dict, bool]:
    """The three Claude spawn lanes from one claude_child_lane_usage sweep (child-usage.mjs:3279-3296)."""
    if not isinstance(sweep, dict) or sweep.get("kind") != KINDS[1]:
        return {lane: unmeasured("collector_failed") for lane in CLAUDE_LANES}, False
    groups = (sweep.get("groups") or {}).get("by_spawn") or {}
    actors = [actor for actor in sweep.get("actors") or [] if isinstance(actor, dict)]
    lanes = {}
    for lane, spawn in CLAUDE_LANES.items():
        aggregate = sweep.get("main") if spawn == "main" else groups.get(spawn)
        members = [actor for actor in actors if actor.get("spawn") == spawn]
        if not isinstance(aggregate, dict):
            aggregate = {"children": 0, "tool_calls": 0, "bash_calls": 0, "mcp_calls": {}, "rtk": {"hook_rewrites": 0, "model_typed": 0}}
        mcp, other = fold(aggregate.get("mcp_calls"), aliases)
        rtk = aggregate.get("rtk") if isinstance(aggregate.get("rtk"), dict) else {}
        usage, advisor, complete = _claude_usage(members)
        total = count(sweep.get("main_sessions_in_window")) if spawn == "main" else count(aggregate.get("children"))
        lanes[lane] = {"actors": total, "actors_complete": complete, "tool_calls": count(aggregate.get("tool_calls")),
                       "mcp": mcp, "mcp_other": other,
                       "rtk": {"rewrites": count(rtk.get("hook_rewrites")), "typed": count(rtk.get("model_typed")),
                               "shell_calls": count(aggregate.get("bash_calls"))},
                       "spawn": {"children": None if spawn == "main" else count(aggregate.get("children")), "codex_subagent_sessions": None},
                       "models": _models(message.get("model") for actor in members
                                         for message in ((actor.get("measurement") or {}).get("usage") or {}).get("messages") or []
                                         if isinstance(message, dict)),
                       "usage": usage, "advisor": advisor, "codex_usage": None, "runs": None,
                       "unmeasured": "no_rows_in_window" if total == 0 else None}
    return lanes, True


def _codex_complete(actor) -> bool:
    usage = ((actor.get("measurement") or {}).get("provider_usage") or {}) if isinstance(actor, dict) else {}
    totals = usage.get("totals") if isinstance(usage.get("totals"), dict) else {}
    return usage.get("complete") is True and all(count(totals.get(key)) is not None for name, key in CODEX_USAGE.items() if name != "cache_write")


def codex_lane(report, aliases: dict) -> tuple[dict, bool]:
    """gpt:codex: the workers, negative_controls and unclassified groups, which partition the sessions by user_config
    (skill_usage.py:2272-2280); codex_call.sh jobs run with --ignore-user-config and land in negative_controls."""
    if not isinstance(report, dict) or report.get("kind") != KINDS[0]:
        return unmeasured("collector_failed"), False
    groups = report.get("groups") or {}
    parts = [groups[name] for name in ("workers", "negative_controls", "unclassified") if isinstance(groups.get(name), dict)]
    calls: dict = {}
    for part in parts:
        for server, number in (part.get("mcp_calls") or {}).items():
            if count(number) is not None:
                calls[server] = calls.get(server, 0) + number
    mcp, other = fold(calls, aliases)
    actors = [actor for actor in report.get("actors") or [] if isinstance(actor, dict)]
    complete = [actor for actor in actors if _codex_complete(actor)]
    codex_usage = dict.fromkeys(CODEX_USAGE)
    if complete:
        for name, key in CODEX_USAGE.items():
            codex_usage[name] = _sum(count(actor["measurement"]["provider_usage"]["totals"].get(key)) for actor in complete)
    total = _sum(count(part.get("sessions")) for part in parts) if parts else 0
    subagents = (report.get("sessions_by_kind") or {}).get("subagent", 0)
    # Codex rollouts carry no per-message model id; each attempt's configured_model (the turn's turn_context, read by the
    # existing scanner, skill_usage.py:1512-1516) is counted once per turn.
    turns = (attempt.get("configured_model") for actor in actors
             for attempt in ((actor.get("measurement") or {}).get("provider_usage") or {}).get("attempts") or [] if isinstance(attempt, dict))
    return {"actors": total, "actors_complete": len(complete), "tool_calls": _sum(count(part.get("tool_calls")) for part in parts),
            "mcp": mcp, "mcp_other": other,
            # Codex runs no RTK rewrite hook (its hook is held, skill_usage.py:1744); a shell call whose first word is rtk
            # (skill_usage.py:2009-2010) was typed with the prefix, so it counts as typed, never as a rewrite.
            "rtk": {"rewrites": None, "typed": _sum(count(part.get("rtk_prefixed_shell_calls")) for part in parts),
                    "shell_calls": _sum(count(part.get("shell_calls")) for part in parts)},
            "spawn": {"children": None, "codex_subagent_sessions": count(subagents)},
            "models": _models(turns), "usage": None, "advisor": None, "codex_usage": codex_usage, "runs": None,
            "unmeasured": "no_rows_in_window" if total == 0 else None}, True


def _policy():
    """tools/local-pages/source_policy.py, for its bounded no-symlink regular-file reads (_read_regular, :115-120)."""
    spec = importlib.util.spec_from_file_location("token_rate_source_policy", ROOT / "tools/local-pages/source_policy.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_muse_receipts(roots) -> list[dict]:
    """The fields a Muse run is counted by, from each <root>/<run>/receipt.json one level deep: a regular file of at most
    1 MiB, read without following a symlink. Run directory names, toolchain_directories and every other receipt field are
    never kept. A receipt of another schema, a symlink, an oversized file or one that does not parse is skipped."""
    policy = _policy()
    runs = []
    for root in roots:
        root = Path(root).absolute()
        with policy._directory(root) as directory:
            names = sorted(entry.name for entry in os.scandir(directory) if entry.is_dir(follow_symlinks=False))
        for name in names:
            try:
                document = json.loads(policy._read_regular(root / name / "receipt.json", MUSE_RECEIPT_BYTES))
            except (OSError, ValueError):
                continue  # absent, symlinked, nonregular, oversized or unparsable: skipped, never followed
            if not isinstance(document, dict) or document.get("schema") != MUSE_SCHEMA:
                continue
            try:
                started = skill_usage.parse_iso(document.get("started_utc"))
            except (ValueError, TypeError, AttributeError):
                continue
            terminals = document.get("terminal_counts") if isinstance(document.get("terminal_counts"), dict) else {}
            runs.append({"started": started, "completed": (count(terminals.get(MUSE_COMPLETED)) or 0) >= 1 and document.get("exit_code") == 0,
                         "model": document.get("requested_model") if isinstance(document.get("requested_model"), str) else None})
    return runs


def muse_lane(runs, since: datetime, until: datetime) -> tuple[dict, str]:
    """muse:muse from receipt runs that started in [since, until): runs and requested models; Muse receipts hold no usage keys."""
    if runs is None:
        return unmeasured("not_configured"), "not_configured"
    if runs == "collector_failed":
        return unmeasured("collector_failed"), "collector_failed"
    inside = [run for run in runs if since <= run["started"] < until]
    completed = sum(1 for run in inside if run["completed"])
    return {**dict.fromkeys(NUMERATORS), "actors": len(inside), "spawn": {"children": None, "codex_subagent_sessions": None},
            "models": _models(run["model"] for run in inside),
            "runs": {"total": len(inside), "completed": completed, "failed": len(inside) - completed},
            "unmeasured": "no_usage_keys"}, "measured"


def project_lanes(claude, codex, muse, *, servers: dict, since: datetime, until: datetime) -> tuple[dict, dict]:
    """Every lane's numerators for one window, and how each collector fared."""
    claude_part, claude_ok = claude_lanes(claude, servers)
    codex_part, codex_ok = codex_lane(codex, servers)
    muse_part, muse_state = muse_lane(muse, since, until)
    lanes = {**claude_part, "gpt:codex": codex_part, "muse:muse": muse_part}
    collectors = {"claude": "measured" if claude_ok else "collector_failed", "codex": "measured" if codex_ok else "collector_failed",
                  "muse": muse_state}
    return {lane: lanes[lane] for lane in LANES}, collectors


def project_day(claude, codex, muse, *, servers: dict, date: str) -> dict:
    """One history row for the closed UTC day `date` (YYYY-MM-DD). A row is complete when the Claude and Codex collectors
    both measured; incomplete actors are disclosed by their counts and never make a row incomplete."""
    since, until = day_window(date)
    lanes, collectors = project_lanes(claude, codex, muse, servers=servers, since=since, until=until)
    return {"date": date, "since": stamp(since), "until": stamp(until),
            "complete": collectors["claude"] == "measured" and collectors["codex"] == "measured",
            "collectors": collectors, "lanes": lanes}


# ---------------------------------------------------------------- history
def check_history(history) -> dict | None:
    """The previous token-rate-history/1 document with every row's digest verified; None when there is none yet."""
    if history is None:
        return None
    rows = history.get("rows") if isinstance(history, dict) else None
    if not isinstance(history, dict) or history.get("schema") != HISTORY_SCHEMA or not isinstance(rows, list):
        raise ValueError("token-rate history is not a token-rate-history/1 document")
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("date"), str) or row["date"] in seen:
            raise ValueError("token-rate history row is malformed or repeats a date")
        if row.get("row_sha256") != digest({key: value for key, value in row.items() if key != "row_sha256"}):
            raise ValueError("token-rate history row digest does not verify")
        seen.add(row["date"])
    return history


def _measured(row: dict) -> set:
    return {client for client, state in (row.get("collectors") or {}).items() if state == "measured"}


def merge_history(history, rows, *, now: datetime, cap: int = CAP) -> dict:
    """The next history: closed days only, one row per date, a complete row never replaced, an incomplete one superseded
    by a later measurement that is complete or measured at least the collectors the old row measured (so a failed
    re-collection never erases a measured lane), recording the old row's digest; sorted by date, the oldest rows dropped
    past the cap."""
    history = check_history(history)
    closed = midnight(now)
    by_date = {row["date"]: row for row in (history or {}).get("rows") or []}
    for row in rows:
        _, until = day_window(row["date"])
        if until > closed or row.get("until") != stamp(until):
            raise ValueError("token-rate history holds closed UTC days only")
        previous = by_date.get(row["date"])
        if previous is not None and (previous.get("complete") is True
                                     or not (row.get("complete") is True or _measured(previous) <= _measured(row))):
            continue
        candidate = {key: value for key, value in row.items() if key not in ("row_sha256", "supersedes_row_sha256")}
        candidate["supersedes_row_sha256"] = previous["row_sha256"] if previous else None
        candidate["row_sha256"] = digest(candidate)
        by_date[row["date"]] = candidate
    ordered = [by_date[day] for day in sorted(by_date)]
    return {"schema": HISTORY_SCHEMA, "cap": cap, "rows": ordered[-cap:] if cap > 0 else []}


def _add(values):
    values = [value for value in values if value is not None]
    if not values:
        return None
    if all(isinstance(value, dict) for value in values):
        return {key: _add([value.get(key) for value in values]) for key in sorted({key for value in values for key in value})}
    if all(isinstance(value, int) and not isinstance(value, bool) for value in values):
        return sum(values)
    return None


def add_lanes(items: list) -> dict:
    """Field-wise sums of one lane's numerators over rows: numbers add, null is skipped and a field no row measured stays
    null. Shares are never stored or averaged; readers divide the summed numerators."""
    items = [item for item in items if isinstance(item, dict)]
    result = {key: _add([item.get(key) for item in items]) for key in NUMERATORS}
    result["models"] = _models_sum(item.get("models") for item in items)
    result["spawn"] = result["spawn"] or {"children": None, "codex_subagent_sessions": None}
    reasons = {item.get("unmeasured") for item in items}
    result["unmeasured"] = next(iter(reasons)) if len(reasons) == 1 else None if items else "no_rows_in_window"
    result["days_measured"] = sum(1 for item in items if item.get("unmeasured") not in ("collector_failed", "not_configured"))
    return result


def _models_sum(models) -> dict:
    summed: dict = {}
    for item in models:
        for name, number in (item or {}).items():
            if isinstance(name, str) and MODEL.fullmatch(name) and count(number) is not None:
                summed[name] = summed.get(name, 0) + number
    return dict(sorted(sorted(summed.items(), key=lambda item: (-item[1], item[0]))[:MAX_MODELS]))


def rollup(history: dict, *, days: int = ROLLUP_DAYS, until: Date) -> dict:
    """The lane numerators summed over the history rows whose date falls in [until - days, until)."""
    since = until - timedelta(days=days)
    rows = [row for row in history["rows"] if since <= Date.fromisoformat(row["date"]) < until]
    return {"days": days, "since": since.isoformat(), "until": until.isoformat(), "days_present": len(rows),
            "days_complete": sum(1 for row in rows if row.get("complete") is True),
            "lanes": {lane: add_lanes([row["lanes"].get(lane) for row in rows]) for lane in LANES}}


def _coverage(lanes: dict) -> dict:
    claude = [lanes[lane] for lane in CLAUDE_LANES]
    actors = _sum(lane.get("actors") for lane in claude)
    complete = _sum(lane.get("actors_complete") for lane in claude)
    codex = lanes["gpt:codex"]
    return {"claude_actors": actors, "claude_actors_incomplete": None if actors is None or complete is None else actors - complete,
            "codex_sessions": codex.get("actors"),
            "codex_usage_incomplete": None if codex.get("actors") is None or codex.get("actors_complete") is None
            else codex["actors"] - codex["actors_complete"],
            "muse_receipts": (lanes["muse:muse"].get("runs") or {}).get("total")}


def latest(history: dict, partial: dict | None, *, now: datetime, measured: dict, servers: list, source: dict) -> dict:
    """The token-rate-daily/1 document: the closed-day rollup, today so far and the history's extent."""
    summary = rollup(history, until=midnight(now).date())
    rows = history["rows"]
    return {"schema": SCHEMA, "generated_at": stamp(now), "rollup": summary, "partial_today": partial,
            "measured": measured, "coverage": _coverage(summary["lanes"]), "servers": servers, "source": source,
            "history": {"rows": len(rows), "first_date": rows[0]["date"] if rows else None, "last_date": rows[-1]["date"] if rows else None}}


# ---------------------------------------------------------------- collection
def _read_json(path: Path | None):
    return json.loads(Path(path).read_text()) if path else None


def collect_window(codex_roots, claude_roots, *, since: datetime, until: datetime, node: str, runner=None) -> tuple:
    """One Codex --lanes and one Claude --lanes-sweep run for [since, until); never --run-skill-doctor."""
    commands = daily_skill_usage.lane_commands(codex_roots, claude_roots, since=stamp(since), until=stamp(until), now=stamp(until), node=node)
    codex, claude = daily_skill_usage.run_reports(commands, KINDS, runner or subprocess.run)
    return claude, codex


def _muse(roots):
    if not roots:
        return None
    try:
        return read_muse_receipts(roots)
    except OSError:
        return "collector_failed"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex-root", action="append", type=Path, default=[])
    parser.add_argument("--claude-root", action="append", type=Path, default=[])
    parser.add_argument("--muse-logs-root", action="append", type=Path, default=[])
    parser.add_argument("--node", default="node")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--history", type=Path)
    parser.add_argument("--now")
    parser.add_argument("--backfill-days", type=int, default=7)
    parser.add_argument("--date", help="replay one closed UTC day from pre-captured reports")
    parser.add_argument("--claude-lanes-report", type=Path)
    parser.add_argument("--codex-lanes-report", type=Path)
    parser.add_argument("--muse-receipts-dir", action="append", type=Path, default=[])
    parser.add_argument("--render-units", type=Path)
    parser.add_argument("--repository", type=Path, default=ROOT)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    args = parser.parse_args(argv)
    try:
        if args.render_units:
            node = shutil.which(args.node)
            if not node:
                raise ValueError("node executable is unavailable")
            daily_skill_usage.render_units(args.render_units, args.repository, args.python, Path(node), names=UNITS)
            return 0
        if not args.out or not args.history or not 0 <= args.backfill_days <= 31:
            raise ValueError("--out, --history and a backfill of at most 31 days are required")
        now = skill_usage.parse_iso(args.now) if args.now else skill_usage.now_utc()
        aliases, servers, role_sha = load_servers()
        source = {"role_tool_sets_sha256": role_sha, "kernel_sha256": hashlib.sha256(KERNEL.read_bytes()).hexdigest(),
                  "lanes_report_kind": KINDS[0], "sweep_kind": KINDS[1]}
        history_path, out_path = args.history.absolute(), args.out.absolute()
        # Both destinations pass publish's refusal (daily_skill_usage.py:145-147) before anything runs or is written,
        # so a hard failure writes neither file.
        if history_path == out_path or any(skill_usage.inside_git_work_tree(path.parent) or path.is_relative_to(daily_skill_usage.ROOT)
                                           for path in (history_path, out_path)):
            raise ValueError("projection destinations must be two files outside every git worktree")
        history = check_history(_read_json(history_path) if history_path.exists() else None)
        rows, partial, states = [], None, []
        if args.date or args.claude_lanes_report or args.codex_lanes_report or args.muse_receipts_dir:
            if not args.date:
                raise ValueError("a replay names its --date")
            day = Date.fromisoformat(args.date).isoformat()
            row = project_day(_read_json(args.claude_lanes_report), _read_json(args.codex_lanes_report),
                              _muse(args.muse_receipts_dir), servers=aliases, date=day)
            rows.append({**row, "measured_at": stamp(now)})
            states.append(row["collectors"])
        else:
            daily_skill_usage.require_live_clone(args.codex_root, args.claude_root)
            known = {row["date"]: row for row in (history or {}).get("rows") or []}
            today = midnight(now).date()
            for offset in range(args.backfill_days, 0, -1):
                day = (today - timedelta(days=offset)).isoformat()
                if (known.get(day) or {}).get("complete") is True:
                    continue
                since, until = day_window(day)
                claude, codex = collect_window(args.codex_root, args.claude_root, since=since, until=until, node=args.node)
                row = project_day(claude, codex, _muse(args.muse_logs_root), servers=aliases, date=day)
                rows.append({**row, "measured_at": stamp(now)})
                states.append(row["collectors"])
            since = midnight(now)
            if now > since:
                claude, codex = collect_window(args.codex_root, args.claude_root, since=since, until=now, node=args.node)
                lanes, collectors = project_lanes(claude, codex, _muse(args.muse_logs_root), servers=aliases, since=since, until=now)
                states.append(collectors)
                if collectors["claude"] == "measured" or collectors["codex"] == "measured":
                    partial = {"since": stamp(since), "until": stamp(now), "lanes": lanes}
        merged = merge_history(history, rows, now=now)
        last = states[-1] if states else {}
        measured = {client: last.get(client) == "measured" for client in ("claude", "codex", "muse")}
        document = latest(merged, partial, now=now, measured=measured, servers=servers, source=source)
        daily_skill_usage.publish(history_path, merged)
        daily_skill_usage.publish(out_path, document)
        return 0 if any(state.get(client) == "measured" for state in states for client in ("claude", "codex", "muse")) else 1
    except (OSError, ValueError, subprocess.SubprocessError):
        print(FAILURE, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
