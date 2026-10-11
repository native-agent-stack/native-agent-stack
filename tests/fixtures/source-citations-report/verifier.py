"""Frozen fake of verify-sources/1 CLI/summary boundaries; no citation checker."""
import argparse
import json
import os
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--repo", required=True)
parser.add_argument("--pr", required=True, type=int)
parser.add_argument("--mode", required=True, choices=["report"])
parser.add_argument("--report", required=True, type=Path)
args = parser.parse_args()
report = {"schema": "verify-sources/1", "mode": args.mode,
          "source": {"repo": args.repo, "pr": args.pr},
          "counts": {"line-range-out-of-bounds": 1}}
args.report.write_text(json.dumps(report), encoding="utf-8")
if os.environ.get("FIXTURE_SUMMARY", "yes") == "yes":
    with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a", encoding="utf-8") as output:
        output.write("## Verified sources\n\nFixture finding: line-range-out-of-bounds.\n")
raise SystemExit(int(os.environ.get("FIXTURE_EXIT", "0")))
