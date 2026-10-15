"""Skill-listing context per source from Claude Code's own /skill-doctor table (headless, 0 turns, $0).

Run from the repository root:  python3 evidence/artifacts/claudeai-synced-plugins-20261015/listing_cost.py OUT.json
The `context` column is the approximate tokens each loaded skill's listing adds to the system prompt every turn
(/skill-doctor's own footer: "Each one adds to the system prompt every turn").

The probe and its checks are tools/skill-usage/skill_usage.py's (GPT read of #1138 at 9f63fc31, P2 1-3):
skill_doctor_argv() drops only --strict-mcp-config on a host with a managed MCP config, and parse_claude_output() reads
a result object or a verbose event array, refusing an error result and a nonzero-cost or nonzero-turn run. A run that
fails, is refused or prints no table writes nothing, so earlier evidence stays.
"""
import collections
import datetime as dt
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
NUM = r"(?:<\s*|~)?\d[\d,.]*[kKmM]?"
ROW = re.compile(rf"^\s*(\S+)\s+(.+?)\s+(-|{NUM})\s+(-|{NUM})\s+(\d+)×\s+(.+?)\s*$")
SYNCED = ("bigdata-com", "lseg", "daloopa", "cowork-plugin-management")


def skill_usage():
    spec = importlib.util.spec_from_file_location("skill_usage", ROOT / "tools/skill-usage/skill_usage.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def tokens(cell: str) -> int:
    if cell == "-":
        return 0
    m = re.search(r"(\d[\d,.]*)([kKmM]?)", cell)
    scale = {"": 1, "k": 1_000, "m": 1_000_000}[m.group(2).lower()]
    return int(float(m.group(1).replace(",", "")) * scale)


def measure(stdout: str, su) -> tuple[dict | None, str | None]:
    """(by-source totals and the result event, None) for an accepted table, else (None, the refusal)."""
    parsed = su.parse_claude_output(stdout)
    if parsed.get("error"):
        return None, parsed["error"]
    if parsed.get("format") != "json":
        return None, "the output is not the JSON result of a headless run"
    if not parsed["rows"]:
        return None, "no /skill-doctor table in the result: not measured"
    events = json.loads(stdout)
    result = su.find_result_event(events if isinstance(events, list) else [events])
    by = collections.defaultdict(lambda: {"skills": 0, "used": 0, "listing_tokens": 0})
    for line in result["result"].splitlines():
        m = ROW.match(line)
        if m:
            source = m.group(2).strip()
            by[source]["skills"] += 1
            by[source]["used"] += int(m.group(5)) > 0
            by[source]["listing_tokens"] += tokens(m.group(3))
    if not by:
        return None, "the table rows carry no source column: not measured"
    return {"by": by, "result": result}, None


def main(argv=None, *, runner=subprocess.run, managed_paths=None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("usage: listing_cost.py OUT.json", file=sys.stderr)
        return 2
    su = skill_usage()
    command = su.skill_doctor_argv(managed_paths)
    try:
        done = runner(command, capture_output=True, text=True, timeout=120, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired) as error:
        print(f"listing_cost: not measured: {type(error).__name__}; nothing written", file=sys.stderr)
        return 2
    if done.returncode != 0:
        print(f"listing_cost: not measured: claude -p /skill-doctor exited {done.returncode}; nothing written",
              file=sys.stderr)
        return 2
    measured, refusal = measure(done.stdout, su)
    if measured is None:
        print(f"listing_cost: not measured: {refusal}; nothing written", file=sys.stderr)
        return 2
    by, result = measured["by"], measured["result"]
    version = runner(["claude", "--version"], capture_output=True, text=True, timeout=30,
                     stdin=subprocess.DEVNULL).stdout.strip()
    report = {
        "kind": "measurement", "read_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "client": version, "command": " ".join(a if a else "''" for a in command),
        "num_turns": result.get("num_turns"), "total_cost_usd": result.get("total_cost_usd"),
        "by_source": dict(sorted(by.items(), key=lambda kv: -kv[1]["listing_tokens"])),
        "synced_total_tokens": sum(by[p]["listing_tokens"] for p in SYNCED if p in by),
        "all_total_tokens": sum(v["listing_tokens"] for v in by.values()),
        "note": "context is per turn, before prompt caching; uses are /skill-doctor's own counts",
    }
    Path(args[0]).write_text(json.dumps(report, indent=1) + "\n")
    print(report["synced_total_tokens"], report["all_total_tokens"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
