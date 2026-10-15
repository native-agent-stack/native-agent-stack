"""Skill-listing context per source from Claude Code's own /skill-doctor table (headless, 0 turns, $0).

Run from the repository root:  python3 evidence/artifacts/claudeai-synced-plugins-20261015/listing_cost.py OUT.json
The `context` column is the approximate tokens each loaded skill's listing adds to the system prompt every turn
(/skill-doctor's own footer: "Each one adds to the system prompt every turn").
"""
import collections
import datetime as dt
import json
import re
import subprocess
import sys

ARGV = ["claude", "-p", "/skill-doctor", "--output-format", "json", "--permission-mode", "dontAsk",
        "--permission-prompts", "none", "--tools", "", "--strict-mcp-config", "--max-turns", "1", "--max-budget-usd", "0.05"]
NUM = r"(?:<\s*|~)?\d[\d,.]*[kKmM]?"
ROW = re.compile(rf"^\s*(\S+)\s+(.+?)\s+(-|{NUM})\s+(-|{NUM})\s+(\d+)×\s+(.+?)\s*$")
SYNCED = ("bigdata-com", "lseg", "daloopa", "cowork-plugin-management")


def tokens(cell: str) -> int:
    if cell == "-":
        return 0
    m = re.search(r"(\d[\d,.]*)([kKmM]?)", cell)
    scale = {"": 1, "k": 1_000, "m": 1_000_000}[m.group(2).lower()]
    return int(float(m.group(1).replace(",", "")) * scale)


done = subprocess.run(ARGV, capture_output=True, text=True, timeout=120, stdin=subprocess.DEVNULL)
result = json.loads(done.stdout)
by = collections.defaultdict(lambda: {"skills": 0, "used": 0, "listing_tokens": 0})
for line in result["result"].splitlines():
    m = ROW.match(line)
    if m:
        source = m.group(2).strip()
        by[source]["skills"] += 1
        by[source]["used"] += int(m.group(5)) > 0
        by[source]["listing_tokens"] += tokens(m.group(3))
report = {
    "kind": "measurement", "read_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "client": "claude-code (claude --version at the time)", "command": " ".join(a if a else "''" for a in ARGV),
    "num_turns": result.get("num_turns"), "total_cost_usd": result.get("total_cost_usd"),
    "by_source": dict(sorted(by.items(), key=lambda kv: -kv[1]["listing_tokens"])),
    "synced_total_tokens": sum(by[p]["listing_tokens"] for p in SYNCED),
    "all_total_tokens": sum(v["listing_tokens"] for v in by.values()),
    "note": "context is per turn, before prompt caching; uses are /skill-doctor's own counts",
}
version = subprocess.run(["claude", "--version"], capture_output=True, text=True, timeout=30).stdout.strip()
report["client"] = version
open(sys.argv[1], "w").write(json.dumps(report, indent=1) + "\n")
print(report["synced_total_tokens"], report["all_total_tokens"])
