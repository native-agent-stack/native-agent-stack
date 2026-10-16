#!/usr/bin/env python3
"""Join the three stage runs' usage records into the one record convert.py --usage reads (CC full read, 2026-10-15).
convert.py takes a single --usage path (tools/sota-convergence/landscape-sweep/convert.py:762) and reads only
child_usage.children and child_usage.superseded_attempts from it (resolved_models, usage_children, effort_deviations,
superseded_retained, web_search_capped). Every child is copied as recorded; no counter is changed.
usage: join_usage.py <attempts dir> <out json>   (no network, no model calls)"""
import json, sys
from pathlib import Path

here, out = Path(sys.argv[1]), Path(sys.argv[2])
runs = ["wf_424f30f4-0af", "wf_27e93022-5c0", "wf_d251d8c8-3b7"]  # stage 1 discover, stage 2 refute, stage 3 critic
children, superseded = [], []
for run in runs:
    usage = json.loads((here / f"child-usage-{run}.json").read_text(encoding="utf-8"))["child_usage"]
    if usage.get("status") != "complete" or not str(usage.get("transcript_dir", "")).endswith("/" + run):
        sys.exit(f"child-usage-{run}.json: status is not complete, or the record names another run")
    children += usage["children"]
    superseded += usage.get("superseded_attempts") or []
labels = [child["label"] for child in children]
if len(set(labels)) != len(labels):
    sys.exit("a child label repeats across the runs, and convert.py keys children by label")
doc = {"schema_version": 1, "kind": "joined_child_usage", "joined_from": [f"child-usage-{run}.json" for run in runs],
       "child_usage": {"status": "complete", "children": children, "superseded_attempts": superseded}}
out.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print("wrote", out.name, "children", len(children), "labels", labels, "superseded", len(superseded))
