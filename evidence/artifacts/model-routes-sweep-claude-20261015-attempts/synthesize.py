#!/usr/bin/env python3
"""Combine the three Claude-only stage run records into the sweep.js return shape convert.py reads.
usage: synthesize.py <work dir>"""
import json, sys
from pathlib import Path
W = Path(sys.argv[1])

def find(obj, key):
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for v in obj.values():
            h = find(v, key)
            if h is not None:
                return h
    elif isinstance(obj, list):
        for v in obj:
            h = find(v, key)
            if h is not None:
                return h
    return None

r1 = json.loads((W / "run-wf_424f30f4-0af.json").read_text(encoding="utf-8"))
r2 = json.loads((W / "run-wf_27e93022-5c0.json").read_text(encoding="utf-8"))
r3 = json.loads((W / "run-wf_d251d8c8-3b7.json").read_text(encoding="utf-8"))
kept = json.loads((W / "stage2-merged.json").read_text(encoding="utf-8"))["kept"]
first = {"layer_id": "model-routes", "catalog": "foundation", "round": "first", "followup_reason": None,
         "claude_discover": find(r1, "claude_discover"), "gpt6_discover": None, "merged": kept, "dropped": [],
         "facts": find(r2, "facts"), "fit_claude": find(r2, "fit_claude"), "fit_gpt6": None}
critic = find(r3, "critic")
# The critic flagged model-routes for a follow-up round; the round was NOT run because it would pass the $40 cap
# (CC ruling 19:52Z (A)). sweep.js keeps a round that returned nothing as {lost: true}; convert.py then records the
# layer's retained failure, which is the honest state. The reason travels in the convert.py --limit note.
flag = (critic or {}).get("followup_layers") or []
followups = [{"layer_id": f["layer_id"], "catalog": "foundation", "round": "followup",
              "followup_reason": {"reason": f.get("reason"), "search_directions": f.get("search_directions"),
                                  "already": [p.get("repository") for p in kept]},
              "lost": True} for f in flag if f.get("layer_id") == "model-routes"]
out = {"sweep": "model-routes-claude-20261015", "first": [first], "critic": critic, "followups": followups,
       "lost_first": [], "lost_followups": [f["layer_id"] for f in followups]}
(W / "synthesized-return.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
scope = json.loads((W / "scope.json").read_text(encoding="utf-8"))
inp = json.loads((W / "inputs" / "model-routes.json").read_text(encoding="utf-8"))
scope.setdefault("requirement_sha256", {})["foundation/model-routes"] = inp["requirement_sha256"]
(W / "scope-model-routes.json").write_text(json.dumps(scope, indent=1) + "\n", encoding="utf-8")
print("ok", len(kept), "proposals; critic followups:", len((out["critic"] or {}).get("followup_layers") or []))
