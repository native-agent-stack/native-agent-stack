#!/usr/bin/env python3
"""Hand-build the model-routes layer input for the co-op's Claude-family half (CC ruling 2026-10-15T19:52Z (A)).
usage: build_input.py <repo worktree at 8053f14e7> <work dir>   (no network, no model calls)"""
import hashlib, json, sys
from pathlib import Path

repo, work = Path(sys.argv[1]), Path(sys.argv[2])
sys.path.insert(0, str(repo / "scripts"))
import saturation_ledger as led  # the ledger's own canonical requirement hash

angles_rel = "catalogs/landscape/angles/foundation-model-routes.json"
angles = json.loads((repo / angles_rel).read_text(encoding="utf-8"))
final = json.loads((repo / "catalogs/landscape/final-stack.json").read_text(encoding="utf-8"))
row = next(r for r in final["layers"] if r.get("catalog") == "foundation" and r.get("layer_id") == "model-routes")
scope = json.loads((work / "scope.json").read_text(encoding="utf-8"))

requirement = (
    "The current model ids and routes for three route families: (a) the Anthropic API (vendor model pages and release "
    "notes, read and dated; the claude-api skill's model and pricing references); (b) OpenAI through OmniRoute (the "
    "Codex models page; OmniRoute's own model listing and release notes at its running pin); (c) Meta's Muse through "
    "the muse-code provider (Wonder Full; dev.meta.ai docs; the Muse fence decisions). For each route: model id; route "
    "(client + provider + endpoint class); the pin it was read at; effort and tier controls; limits; pricing or plan "
    "class; adoption status today (CURRENT, TRIAL, NOT_ADOPTED); each verified with a dated primary source or marked "
    "UNVERIFIED with the cheapest check. Selection serves the NativeHorizonNY harness (TRIAL labels only from this sweep).")
next_action = ("Initial sweep scoped to the gap (layer-resolution protocol step 3): adjudicate the 14 carried angle "
               "candidates and propose new routes only with primary sources.")
# The workers' copy also carried the private record's digest after its name. The published input names the record only
# (CC full read, 2026-10-15; RUN-RECORD.md deviation 7), so requirement_sha256 below is the published one.
decision_ref = ("command-center/research-cc-role-20261008/direction-cc-20261015T1912Z-new-wsl-harness-first.md, "
                "ruling 2 (Models: model-routes); CC ruling 2026-10-15T19:52Z (A) to the co-op")
req_row = {"next_action": next_action, "decision_ref": decision_ref}

def ident(c):
    return f"{c['repository']}#{c['id']}"

carried = []
for c in angles["candidates"]:
    carried.append({
        "id": c["id"], "route_identity": ident(c), "name": c["name"], "doc_url": c["repository"], "pin": c["pin"],
        "role": c.get("role"), "adoption_status": c.get("adoption_status"), "verdict": c.get("verdict"),
        "provisional": c.get("provisional"), "disqualifier": c.get("disqualifier"),
        "measure_next": c.get("measure_next"), "entitlement": c.get("entitlement"),
        "confounds": c.get("confounds"),
    })

layer_instructions = [
    "CANDIDATE IDENTITY FOR THIS LAYER: a candidate is a model ROUTE (client + provider + endpoint class + model id). Use "
    "repository = '<primary vendor doc URL>#<route-id>' with a lowercase kebab route-id (the carried set's route_identity "
    "values follow this form). A tool repository (client, gateway, SDK) keeps its canonical GitHub URL as the selection "
    "principles say. The 90-day default-branch maintenance rule applies to repositories; for a vendor-hosted model route, "
    "judge currency from the vendor's dated model page, release notes or changelog and record it in upstream_now "
    "(latest_release = model id or version, released_at = the vendor's date; null where unknowable).",
    "CARRIED SET: each of the 14 carried_candidates must be adjudicated. List every one in proposed[] under its "
    "route_identity with your label, demonstrated_gap, comparison_that_would_overturn, evidence and upstream_now. They do "
    "not count toward the cap of 6 proposals, which applies to NEW candidates only. The refuters vote on every carried "
    "candidate.",
    "REQUIREMENT FIELDS: state each route's adoption status today (CURRENT, TRIAL, NOT_ADOPTED), effort and tier "
    "controls, limits and pricing or plan class inside demonstrated_gap or evidence text, each with its dated source URL.",
    "FENCES: read-only research only. No keyed API call and no invocation of any Anthropic, OpenAI or Meta model. The "
    "Muse fence decisions hold: docs/decisions/2026-10-14-muse-file-fence.md and "
    "docs/decisions/2026-10-15-muse-toolchain-directory-grants.md in the repository worktree named in input_provenance.",
    "INDEPENDENCE: a GPT-family half of this sweep runs separately and stays sealed until both halves finish. Do not read "
    "pull requests of seathatflowsinourveins/native-agent-stack (also served as native-agent-stack/native-agent-stack) "
    "about model routes, nor any evidence/artifacts/model-routes-sweep-* directory. Your returns must be independent.",
]

doc = {
    "catalog": "foundation", "layer_id": "model-routes", "title": row.get("title"),
    "requirement": requirement,
    "research_status": row.get("status"), "next_action": next_action, "decision_ref": decision_ref,
    "requirement_sha256": led.requirement_sha256(req_row),
    "platform_profiles_sha256": scope["platform_profiles_sha256"],
    "winners": [], "alternatives": [],
    "upstream_checked_at": None, "components_vs_upstream": [],
    "open_gaps": [
        "Protocol steps 1-3 at 8053f14e7: no catalog verdict for model-routes in catalogs/landscape/foundation.json, no "
        "wave in catalogs/sota-convergence/layer-verdict-waves.json, no sweep for (foundation, model-routes) in "
        "catalogs/saturation/ledger.json; catalogs/landscape/final-stack.json status unswept, 0 winners, 0 survivors.",
        "The layer is not registered in foundation.json or research-state.json; a registration PR under #1130's "
        "pending-empty path is separate work.",
    ] + [str(g)[:300] for g in (angles.get("gaps") or [])[:5]],
    "open_gaps_followup": [], "verdict_checked_at": None,
    "verdict_note": "No sealed verdict exists for this layer; the carried candidates come from the angle record named in input_provenance.",
    "overturn_when": "", "previous_sweep": {},
    "known_repositories": sorted({c["route_identity"] for c in carried}),
    "seeded_candidates": [],
    "carried_candidates": carried,
    "layer_instructions": layer_instructions,
    "input_provenance": {
        "hand_built": True,
        "why": "model-routes is not a registered catalog layer at 8053f14e7, so build_inputs.py cannot write this input",
        "repository_worktree": str(repo), "commit": "8053f14e7",
        "angles_file": angles_rel,
        "angles_file_sha256": hashlib.sha256((repo / angles_rel).read_bytes()).hexdigest(),
        "final_stack_sha256": hashlib.sha256((repo / "catalogs/landscape/final-stack.json").read_bytes()).hexdigest(),
        "requirement_sha256_rule": "scripts/saturation_ledger.py requirement_sha256 over {next_action, decision_ref} above",
        "platform_profiles_sha256_source": "scripts/saturation_ledger.py --scope at 8053f14e7",
    },
}
out = work / "inputs" / "model-routes.json"
out.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
(work / "layers.json").write_text(json.dumps([{"catalog": "foundation", "layer_id": "model-routes", "title": row.get("title"),
                                               "input": str(out)}], indent=1) + "\n", encoding="utf-8")
print("wrote", out, hashlib.sha256(out.read_bytes()).hexdigest(), out.stat().st_size, "B; carried", len(carried))
