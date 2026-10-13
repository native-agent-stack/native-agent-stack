#!/usr/bin/env python3
"""summarize.py RUNDIR... [--out FILE]: reduce the arm results of readdeny_probe.py (one directory per repeat, one JSON file per arm) to status words and counts, the form of the receipts: no text of a tool result, no path.
`summarize(result)` is the reduction of one arm's result; the tests read it. ASCII only."""
import json
import re
import sys
from collections import Counter
from pathlib import Path

# the tool results of readdeny_probe.py, in order: 0 shell loop, 1 Python loop, 2 symlink, 3 copy, 4 listings, 5 decoys, 6 ordinary commands, 7 Read of a fixture, 8 Read of a decoy, then benign repeats
PROC_ERROR = re.compile(r"bwrap: Can't mkdir parents for /proc/\d+/environ")


def words(text):
    return dict(Counter(re.findall(r"\b(REAL|DENIED|OTHER)\b", text)))


def summarize(result):
    results = result["tool_results"]

    def text(index):
        return results[index]["text"] if index < len(results) else ""

    read_fixture = "READABLE" if "RB SYNTHETIC" in text(7) else ("REFUSED" if text(7).strip() else "EMPTY")
    return {
        "arm": result["arm"], "client_rc": result["claude_rc"], "tool_results": len(results),
        "shell": words(text(0)), "python": words(text(1)),
        "symlink": (re.search(r"(REAL|DENIED|OTHER)-via-symlink", text(2)) or [None, None])[1],
        "copy": (re.search(r"(NOT-COPIED|COPIED)", text(3)) or [None, None])[1],
        "listing_counts": dict(re.findall(r"listing ([^:]+): (\d+)", text(4))),
        "decoys_readable": sorted(re.findall(r"readable (\S+)", text(5))),
        "ordinary_commands_ok": all(re.search(rf"(^|\n){word}(\n|$)", text(6)) for word in ("ok", "42", "proc-ok")),
        "read_tool_fixture": read_fixture, "read_tool_decoy": "READABLE" if "ordinary file" in text(8) else "OTHER",
        "tool_errors": sum(1 for index, item in enumerate(results) if item["is_error"] and index != 7),
        "bwrap_proc_errors": sum(1 for item in results if PROC_ERROR.search(item["text"])),
    }


def main(argv):
    out = Path(argv[argv.index("--out") + 1]) if "--out" in argv else None
    directories = [Path(a) for i, a in enumerate(argv) if not a.startswith("--") and (i == 0 or argv[i - 1] != "--out")]
    rows = []
    for repeat, directory in enumerate(sorted(directories), 1):
        for path in sorted(directory.glob("*.json")):
            rows.append({"repeat": repeat, **summarize(json.loads(path.read_text(encoding="utf-8")))})
    text = json.dumps({"schema_version": 1, "kind": "sandbox_readdeny_arms", "arms": rows}, indent=1) + "\n"
    if out:
        out.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main(sys.argv[1:])
