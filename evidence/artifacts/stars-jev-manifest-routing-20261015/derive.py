"""Offline identity joins and proposal projection for this dated evidence record.

Uses the existing public_starred builder's output, canonical catalogs and pinned
public README captures. It fetches nothing, installs nothing and changes no
catalog. Routing rules below are proposals for the existing layer pipeline,
not a replacement screen, adoption decision or star-classification builder.
Run from any directory: python3 <this file> [--check].
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BASE = "8053f14e7e0817d2502dff2bb284bfb7e1b0152f"
PREFIX = HERE.relative_to(ROOT).as_posix()
INPUTS: dict[str, dict] = {}
JSON_CACHE: dict[str, object] = {}


def norm(value):
    value = value.lower().removeprefix("https://").removeprefix("http://")
    return value.removeprefix("github.com/").rstrip("/").removesuffix(".git")


def read(path):
    path = ROOT / path
    raw = path.read_bytes()
    INPUTS[path.relative_to(ROOT).as_posix()] = {
        "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)
    }
    return raw.decode("utf-8")


def load(path):
    if path not in JSON_CACHE:
        JSON_CACHE[path] = json.loads(read(path))
    return JSON_CACHE[path]


def local(name):
    return load(f"{PREFIX}/{name}")


def pointer(ref):
    path, _, ptr = ref.partition("#")
    obj = load(path)
    for part in ptr.strip("/").split("/") if ptr.strip("/") else []:
        part = part.replace("~1", "/").replace("~0", "~")
        obj = obj[int(part)] if isinstance(obj, list) else obj[part]
    return obj


def refs_in(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if key in ("ref", "source_review", "adjudication_ref") and isinstance(child, str):
                yield child
            else:
                yield from refs_in(child)
    elif isinstance(value, list):
        for child in value:
            yield from refs_in(child)


def has_missing(value):
    if isinstance(value, dict):
        return value.get("missing") is True or any(has_missing(v) for v in value.values())
    return isinstance(value, list) and any(has_missing(v) for v in value)


def derive():
    for path in ["AGENTS.md", "docs/decisions/2026-10-11-layer-resolution-protocol.md",
                 "blueprints/us-equities/AGENTS.md",
                 "docs/decisions/2026-10-11-starred-finalization.md",
                 "tools/starred-maintenance/README.md", "scripts/public_starred.py",
                 "scripts/build_ecosystem.py", "catalogs/saturation/README.md",
                 "docs/decisions/2026-10-15-jev-trading-harness-build.md",
                 "docs/decisions/2026-10-15-jev-scored-contract-corrections.md",
                 "docs/decisions/2026-10-05-typesafe-sdk-transport.md"]:
        read(path)
    canonical_path = "catalogs/convergence-practice/public-starred.json"
    canonical = load(canonical_path)
    snapshot = local("public-starred.refreshed.json")
    finalization = load("catalogs/convergence-practice/starred-convergence-20261010.json")
    audit_path = "catalogs/us-equities/star-audit.json"
    audit = load(audit_path)
    historical = local("historical-undecided.json")
    upstream = local("upstream-sources.json")
    skill_manifest = load("adoption/skills/manifest.json")
    typesafe_skill_index, typesafe_skill = next(
        (i, s) for i, s in enumerate(skill_manifest["skills"]) if s["source"] == "typesafe-ai/skills")
    c = {norm(row["repository"]): (i, row) for i, row in enumerate(canonical["repositories"])}
    live = {norm(row["repository"]): (i, row) for i, row in enumerate(snapshot["repositories"])}
    a = {norm(row["repository"]): (i, row) for i, row in enumerate(audit["entries"])}
    assert len(c) == canonical["count"] == 373
    assert len(live) == snapshot["count"]
    assert len(finalization["repositories"]) == 373
    assert finalization["counts"]["out_of_scope"] == 58
    assert historical["source_sha256"]["star-audit.json"] == INPUTS[audit_path]["sha256"]
    renamed = {new: old for old, new in historical["renames"].items()}
    legacy_missing = sorted(set(live) - set(a) - set(renamed))
    prior = set(historical["undecided_identities"])
    diff = {
        "base_commit": BASE, "canonical_count": len(c), "live_count": len(live),
        "observed_at": snapshot["retrieved_at"],
        "new": sorted(set(live) - set(c)), "unstarred": sorted(set(c) - set(live)),
        "canonical_unresolved": sorted(k for k, (_, r) in c.items()
                                       if r.get("disposition_status") not in
                                       ("IN-SCOPE-SOURCE-REVIEW", "OUT-OF-SCOPE")),
        "legacy_audit_undecided": legacy_missing,
        "historical_undecided_count": len(prior),
        "historical_undecided_already_classified": sorted(prior & set(c)),
        "historical_undecided_still_without_canonical_classification": sorted(prior - set(c)),
        "historic_rename_aliases": historical["renames"],
        "unstarred_semantics": "Absent from this public response; not a request to change stars or delete records.",
    }
    assert len(prior) == 33
    assert prior == set(legacy_missing), "Live undecided set changed; revisit the historical reconciliation"

    layers = {}
    catalog_candidates = {}
    for catalog in ("foundation", "us-equities"):
        path = f"catalogs/landscape/{catalog}.json"
        for i, layer in enumerate(load(path)["layers"]):
            key = f"{catalog}:{layer['layer_id']}"
            layers[key] = {"catalog_ref": f"{path}#/layers/{i}", "row": layer}
            for j, candidate in enumerate(layer.get("candidates", [])):
                repository = candidate.get("repository", "")
                if repository.startswith("https://github.com/"):
                    catalog_candidates.setdefault(norm(repository), []).append({
                        "layer": key, "ref": f"{path}#/layers/{i}/candidates/{j}",
                        "disposition": candidate.get("disposition"),
                        "evidence_kind": candidate.get("evidence_kind"),
                    })
    final_stack = load("catalogs/landscape/final-stack.json")
    runs = {r["id"]: (i, r) for i, r in enumerate(final_stack["runs"])}
    final_layers = {f"{l['catalog']}:{l['layer_id']}": l for l in final_stack["layers"]}
    final_layer_indices = {f"{l['catalog']}:{l['layer_id']}": i for i, l in enumerate(final_stack["layers"])}
    waves = load("catalogs/sota-convergence/layer-verdict-waves.json")
    for wave in waves["waves"]:
        load(wave["path"])
        assert INPUTS[wave["path"]]["sha256"] == wave["sha256"]
    ledger = load("catalogs/saturation/ledger.json")
    contexts = {}
    for key, record in layers.items():
        layer = record["row"]
        covering = []
        history = {}
        missing = []
        for si, sweep in enumerate(ledger["sweeps"]):
            for li, entry in enumerate(sweep["layers"]):
                if f"{entry['catalog']}:{entry['layer_id']}" != key:
                    continue
                ref = f"catalogs/saturation/ledger.json#/sweeps/{si}/layers/{li}"
                # Read immutable retained manifests/returns rather than trusting summary rows.
                for path, expected in [(sweep["manifest_ref"], sweep["manifest_sha256"]),
                                       (sweep.get("returns_ref"), sweep.get("returns_sha256"))]:
                    if path:
                        load(path)
                        assert INPUTS[path]["sha256"] == expected
                if sweep["status"] == "completed":
                    covering.append({"sweep_id": sweep["sweep_id"], "date": sweep["date"],
                                     "ref": ref, "manifest_ref": sweep["manifest_ref"],
                                     "returns_ref": sweep.get("returns_ref"),
                                     "votes": entry["votes"], "survived": entry["survived"],
                                     "reopen": entry["reopen"]})
                if entry["votes"] != "retained":
                    missing.append({"sweep_id": sweep["sweep_id"], "ref": ref,
                                    "reason": entry.get("votes_note", entry["votes"])})
                for outcome in ("survived", "refuted"):
                    for candidate in entry[outcome]:
                        repo = norm(candidate["repo"])
                        witnessed_missing = False
                        for source_ref in refs_in(candidate):
                            if not source_ref.startswith(("catalogs/", "evidence/")):
                                continue
                            try:
                                material = pointer(source_ref)
                                witnessed_missing |= has_missing(material)
                            except (FileNotFoundError, KeyError, IndexError):
                                witnessed_missing = True
                                missing.append({"ref": source_ref, "reason": "Missing vote/source material"})
                        # An absent vote is not a substantive refutation and cannot clear a survivor.
                        if outcome == "refuted" and witnessed_missing:
                            missing.append({"repository": repo, "ref": ref,
                                            "reason": "Refutation by absent vote; prior survivor carried"})
                            continue
                        history[repo] = {"outcome": outcome, "ref": ref,
                                         "sweep_id": sweep["sweep_id"], "date": sweep["date"]}
        final = final_layers.get(key, {})
        verdict = final.get("verdict", {})
        for source_ref in refs_in(verdict):
            if source_ref.startswith(("catalogs/", "evidence/")):
                pointer(source_ref)
        # Also preserve the broad catalog's evidence references, without invoking their mechanisms.
        for source_ref in layer.get("evidence_refs", []):
            path = source_ref.split("#", 1)[0]
            if path.startswith(("catalogs/", "docs/", "evidence/", "blueprints/")) and (ROOT / path).is_file():
                read(path)
        contexts[key] = {
            "catalog_ref": record["catalog_ref"], "requirement": layer["requirement"],
            "decision": layer["decision"], "verdict_status": layer.get("verdict_status"),
            "verdict_wave": verdict.get("wave_doc"), "adjudication_ref": verdict.get("adjudication_ref"),
            "terminal_state": final.get("terminal_state"),
            "winners": [{**{k: w.get(k) for k in ("component_id", "repository", "evidence_class")},
                         "verdict_pin_ref": f"catalogs/landscape/final-stack.json#/layers/{final_layer_indices[key]}/winners/{wi}/verdict_pin",
                         "run_ref": f"catalogs/landscape/final-stack.json#/runs/{runs[w['run']][0]}" if w.get("run") in runs else None,
                         "run_pin_ref": f"catalogs/landscape/final-stack.json#/runs/{runs[w['run']][0]}/pin_parsed" if w.get("run") in runs and runs[w["run"]][1].get("pin_parsed") else None}
                        for wi, w in enumerate(final.get("winners", []))],
            "latest_completed_sweep": covering[-1] if covering else None,
            "covering_sweeps": [{k: s[k] for k in ("sweep_id", "date", "ref", "manifest_ref", "returns_ref")}
                                for s in covering],
            "cumulative_unresolved_survivors": [dict(repository=k, **v) for k, v in sorted(history.items())
                                                if v["outcome"] == "survived"],
            "latest_candidate_adjudications": [dict(repository=k, **v) for k, v in sorted(history.items())],
            "unretained_or_missing_vote_limits": missing,
            "pending_append_boundary": "No newer completed-but-unappended sweep was supplied in task inputs or referenced by these committed ledger/catalog records; a newly retained one supersedes this proposal before a sweep dispatch.",
        }

    source_map = {norm(s["repository"]): s for s in upstream["sources"]}
    for source in source_map.values():
        read(f"{PREFIX}/{source['capture']}")
    awesome = source_map["logicrw/awesome-jev-projects"]
    text = read(f"{PREFIX}/{awesome['capture']}")
    entries = {}
    section = "Directory"
    for i, line in enumerate(text.splitlines(), 1):
        if line.startswith("## "):
            section = line[3:]
        match = re.match(r"^- \[\*\*(.*?)\*\*\]\(https://github.com/([\w.-]+/[\w.-]+)\)(.*)", line)
        if match:
            name = norm(match[2])
            assert name not in entries, "Duplicate project entry in pinned Jev index"
            entries[name] = {"repository": name, "section": section, "line": i,
                             "role_claim": match[3].strip(" —"),
                             "source": f"https://github.com/{awesome['repository']}/blob/{awesome['commit']}/README.md#L{i}"}
    assert len(entries) == 864, "Pinned index entry count drifted"
    index_names = set(entries)
    entries["logicrw/awesome-jev-projects"] = {
        "repository": "logicrw/awesome-jev-projects", "section": "Directory", "line": 5,
        "role_claim": "Discovery directory; not a runtime or proof of quality",
        "source": f"https://github.com/{awesome['repository']}/blob/{awesome['commit']}/README.md#L5"}
    for index, row in enumerate(upstream["typesafe_public_organization"]["repositories"]):
        name = norm(row["repository"])
        if name not in entries:
            entries[name] = {"repository": name, "section": "TypeSafe organization",
                             "role_claim": row["role"],
                             "source": f"{PREFIX}/upstream-sources.json#/typesafe_public_organization/repositories/{index}"}
        entries[name]["observed_head"] = row["commit"]

    section_route = {
        "Directory": "foundation:instructions-skills",
        "Browser & OS Action": "foundation:quality-evaluation",
        "CLI & Pipelines": "foundation:instructions-skills",
        "Classification": "foundation:quality-evaluation",
        "Code Navigation": "foundation:code-navigation",
        "Context GC": "foundation:token-efficiency",
        "Creative Tools": "foundation:hosting-services",
        "Data & Search": "foundation:semantic-rag",
        "Decision Tools": "foundation:agent-sdks",
        "Domain Tools": "us-equities:research-factors-ml",
        "Evaluation & Observability": "foundation:quality-evaluation",
        "High-Frequency / Games": "foundation:quality-evaluation",
        "MCP & Integrations": "foundation:mcp-surfaces",
        "Model Routing": "foundation:native-clients",
        "SDK & Decision Frameworks": "foundation:agent-sdks",
        "SDK Integrations": "foundation:agent-sdks",
        "Security & Guardrails": "foundation:ci-supply-chain",
        "Voice & Conversation": "foundation:hosting-services",
    }
    new_route = {
        "mvschwarz/openrig": ("foundation:workers", "Persistent teams and ownership; compare only to the existing worker requirement after a pin screen."),
        "ranxianglei/billion-context": ("foundation:token-efficiency", "Context compression; token and fidelity claims require the existing paired harness, not marketing acceptance."),
        "tester-army/e2e": ("foundation:quality-evaluation", "Browser/mobile test harness; screen against the retained Playwright path before a trial."),
        "morluto/rea": ("foundation:code-navigation", "Reverse-engineering MCP; screen the binary-analysis gap and tool boundaries before use."),
        "flutter/flutter": ("foundation:hosting-services", "OUT-OF-SCOPE: mobile/application UI toolkit; no Flutter workload or mobile host requirement is named in this stack delta."),
        "chrislgarry/apollo-11": ("foundation:code-navigation", "OUT-OF-SCOPE: historical spacecraft source archive; no agent-stack or US-equity runtime requirement."),
        "storytold/artcraft": ("foundation:hosting-services", "OUT-OF-SCOPE: interactive artist/video creation application; no corresponding north-star workload."),
    }
    org_route = {
        "typesafe-ai/typesafe-ai.github.io": "foundation:instructions-skills",
        "typesafe-ai/vllm": "foundation:observation-inference",
        "typesafe-ai/llada": "foundation:observation-inference",
        "typesafe-ai/daggerverse": "foundation:ci-supply-chain",
        "typesafe-ai/pulumi-clickhouse": "foundation:hosting-services",
        "typesafe-ai/system-one-adapter-python": "foundation:agent-sdks",
        "typesafe-ai/skills": "foundation:instructions-skills",
        "typesafe-ai/typesafe-sdk-python": "foundation:agent-sdks",
        "typesafe-ai/typesafe-sdk-js": "foundation:agent-sdks",
        "typesafe-ai/n8n-nodes-typesafe-ai": "us-equities:data-quality-orchestration",
        "typesafe-ai/workflowevals": "foundation:quality-evaluation",
        "typesafe-ai/typesafe-public-examples": "foundation:instructions-skills",
    }
    # The index's mixed Domain Tools bucket is not a US-equities requirement.
    # Route general coding/data roles individually; exclude unrelated vertical apps.
    domain_routes = {
        "0xshikhar/jev-fuse": "foundation:agent-sdks",
        "0xzee/jev-stock-decision-maker": "us-equities:research-factors-ml",
        "austinaway/working-memory-jev": "foundation:durable-memory",
        "bl888m/jev-bot": "us-equities:research-factors-ml",
        "cairn-ink/cairn-jev-lab": "foundation:durable-memory",
        "charlie-wang-03/jev-testbench": "foundation:quality-evaluation",
        "choxos/jev-reviewer": "foundation:document-retrieval",
        "clduab11/jev-test": "foundation:quality-evaluation",
        "cmaintz/jev-triage": "foundation:git-github-automation",
        "codegirl-007/jevlint": "foundation:quality-evaluation",
        "dagfinndybvig/jev_ontology": "foundation:semantic-rag",
        "darwintechlab/claude-jev": "foundation:mcp-surfaces",
        "darwintechlab/openjev": "foundation:instructions-skills",
        "eliot5566/jev-paper-radar": "foundation:web-research",
        "emiroberti77/jev-py-integration": "foundation:agent-sdks",
        "ethanalgox/jev-trading": "us-equities:research-factors-ml",
        "fox-islam/jevlint": "foundation:quality-evaluation",
        "gabazureus/jevextract": "foundation:document-retrieval",
        "grandamenium/jev-anything": "foundation:instructions-skills",
        "hemanth/tc39-atlas": "foundation:code-navigation",
        "ice-hazymoon/jevlint": "foundation:quality-evaluation",
        "itisnomatter/kojev": "foundation:agent-sdks",
        "j341nono/jev-prompt-optimization": "foundation:quality-evaluation",
        "joshhu/jevtest": "foundation:quality-evaluation",
        "kenhuangus/jev-usecases": "foundation:agent-sdks",
        "kunyanli230/jev-clean": "us-equities:data-quality-orchestration",
        "kyaulabs/kairos": "us-equities:research-factors-ml",
        "kyotofin/tax-doc-classifier": "foundation:document-retrieval",
        "louisultra/jev-deep-dive": "foundation:instructions-skills",
        "lzq-0529/jev-span": "foundation:document-retrieval",
        "mattn/sqlite3-jev": "foundation:agent-sdks",
        "mingleiw/jev-oncall": "foundation:observation-inference",
        "parth1811/jevflow": "foundation:workers",
        "patrick-sch03/jev-issue-radar": "foundation:git-github-automation",
        "poiuyjie/jev_project_context": "foundation:durable-memory",
        "rileycarney/jevtools": "foundation:agent-sdks",
        "romiluz13/jevmory": "foundation:durable-memory",
        "saimahmedqazi/typesafe-jev-playground": "foundation:quality-evaluation",
        "smithclay/dbt_jev": "us-equities:data-quality-orchestration",
        "sunil-sadasivan/jevernetes": "foundation:observation-inference",
        "timmikeladze/jevlang": "foundation:agent-sdks",
        "tomerglick57/jevstiller": "foundation:observation-inference",
        "typesafeai/typesafe-playground": "foundation:quality-evaluation",
        "viniciusfinger/jev-intent-classification": "foundation:quality-evaluation",
        "vinilana/jev-eval-agent": "foundation:quality-evaluation",
        "yangyu666/dsh-jev-prune": "foundation:token-efficiency",
    }
    excluded_context = {
        "anthropics/financial-services": "us-equities:research-factors-ml",
        "deepentropy/tvscreener": "us-equities:market-data-reference",
        "ghostfolio/ghostfolio": "us-equities:portfolio-risk",
        "margelo/react-native-graph": "foundation:hosting-services",
        "marketcalls/openalgo": "us-equities:execution-broker",
        "mathieu2301/tradingview-api": "us-equities:market-data-reference",
        "nofxaios/nofx": "us-equities:agents-models-workers",
        "shner-elmo/tradingview-screener": "us-equities:market-data-reference",
        "stocksharp/stocksharp": "us-equities:backtesting-engine",
        "jarrodwatts/jev-trader": "us-equities:agents-models-workers",
        "virattt/ai-hedge-fund": "us-equities:agents-models-workers",
    }
    routing = []
    universe = set(diff["new"]) | prior | set(entries)
    for repo in sorted(universe):
        ent = entries.get(repo)
        row = {"repository": repo, "intake": [], "citations": []}
        if repo in diff["new"]:
            row["intake"].append("new_vs_373")
        if repo in prior:
            row["intake"].append("legacy_undecided_20261012")
        if ent:
            row["intake"].append("jev_index" if repo in index_names else "jev_anchor_or_typesafe_org")
            row["citations"].append(ent["source"])
        if repo in c:
            i, prior_row = c[repo]
            row["citations"].append(f"{canonical_path}#/repositories/{i}")
            row["disposition"] = "OUT-OF-SCOPE" if prior_row["disposition_status"] == "OUT-OF-SCOPE" else "already adjudicated"
            row["reason"] = "Preserve recorded discovery-scope/seed disposition: " + prior_row["reason"]
            row["adjudication_kind"] = "scope_and_seed_only; not a qualified runtime verdict"
            row["layers"] = [next(k for k in layers if k.endswith(":" + lid)) for lid in prior_row["layer_keys"]]
            row["canonical_layer_keys"] = prior_row["layer_keys"]
            if not row["layers"]:
                row["layers"] = [excluded_context.get(repo, section_route.get(ent["section"], "foundation:instructions-skills") if ent else "foundation:instructions-skills")]
                row["context_only_routing"] = "Nearest layer for requirement/exclusion review; canonical empty layer_keys and exclusion unchanged"
        elif repo in catalog_candidates:
            records = catalog_candidates[repo]
            row["disposition"] = "already adjudicated"
            row["reason"] = "Preserve the catalog candidate's recorded disposition for its existing role; Jev integration remains unmeasured."
            row["layers"] = sorted({r["layer"] for r in records})
            row["candidate_dispositions"] = records
            row["citations"].extend(r["ref"] for r in records)
        else:
            if repo in new_route:
                key, reason = new_route[repo]
                s = source_map[repo]
                row["citations"].append(f"https://github.com/{s['repository']}/blob/{s['commit']}/README.md#L{s['role_line']}")
            elif repo in org_route:
                key = org_route[repo]
                reason = "Provisional role routing from public organization projection; target implementation screen has not run."
            elif ent["section"] == "Domain Tools":
                key = domain_routes.get(repo, "foundation:hosting-services")
                reason = ("Provisional routing from the specific pinned entry's coding/data/research role, not its mixed Domain Tools category; independently verify target pin and required fit before any trial."
                          if repo in domain_routes else
                          "OUT-OF-SCOPE for this task: the retained mixed-domain entry establishes no named coding-stack or US-equity research workload to pursue. Preserve its application/reference identity; this is a bounded scope exclusion, not a failed capability screen or a claim that transferable capability is absent.")
            else:
                key = section_route[ent["section"]]
                reason = f"Provisional next-sweep discovery seed from pinned index section {ent['section']}; independently screen candidate implementation and pin before trial."
            row["layers"] = [key]
            row["disposition"] = "OUT-OF-SCOPE" if reason.startswith("OUT-OF-SCOPE") else "seed for next sweep"
            row["reason"] = reason
            if ent and ent["section"] in ("Creative Tools", "Voice & Conversation", "High-Frequency / Games"):
                row["disposition"] = "OUT-OF-SCOPE"
                row["reason"] = f"OUT-OF-SCOPE: {ent['section']} application/game demonstrations are not a named coding-stack or US-equity research workload. Retain as discovery reference; no install."
            if repo in ("typesafe-ai/vllm", "typesafe-ai/daggerverse", "typesafe-ai/pulumi-clickhouse"):
                row["disposition"] = "OUT-OF-SCOPE"
                row["reason"] = "OUT-OF-SCOPE: organization-owned fork/infrastructure is not proof of Jev relevance; use the already selected upstream mechanism instead of adopting this fork by association."
        # Explicitly carry the adopted official transport at its existing pin.
        if repo == "typesafe-ai/typesafe-sdk-python":
            row.update(disposition="already adjudicated", layers=["foundation:agent-sdks"],
                       reason="Retain the adopted typesafe-sdk0.7.2 transport; observed HEAD is discovery only, not an upgrade or model selection.",
                       adopted_pin="f078f1e208a0d885154dc758344ae4fce77ac168")
            row["citations"].append("docs/decisions/2026-10-05-typesafe-sdk-transport.md:10")
        if repo == "typesafe-ai/skills":
            row["adopted_pin"] = typesafe_skill["ref"]
            row["citations"].append(f"adoption/skills/manifest.json#/skills/{typesafe_skill_index}")
        if ent and ent["section"] == "Domain Tools":
            row["citations"].extend(["blueprints/us-equities/AGENTS.md",
                                     "docs/decisions/2026-10-15-jev-trading-harness-build.md",
                                     "docs/decisions/2026-10-15-jev-scored-contract-corrections.md"])
            row["trading_boundary"] = "Research-question discovery only; no numeric risk, order, broker or model-to-feature admission. Existing frozen comparison only; broader use needs its own dated admission."
        row["layer_context_refs"] = [f"{PREFIX}/layer-contexts.json#/layers/{k}" for k in row["layers"]]
        assert row["citations"]
        routing.append(row)

    manifest = []
    for row in routing:
        selected = []
        for key in row["layers"]:
            selected += [(key, w) for w in contexts[key]["winners"] if w.get("repository") and norm(w["repository"]) == row["repository"]]
        # FINAL must be a terminal FINAL row, not selected, installed, or a source-review seed.
        final = [(k, w) for k, w in selected if contexts[k]["terminal_state"] == "FINAL"]
        label = "FINAL" if final else "TRIAL" if selected or row.get("adopted_pin") else "GAP"
        if row["disposition"] == "OUT-OF-SCOPE":
            label = "GAP"
        parsed = pointer(selected[0][1]["run_pin_ref"]) if selected and selected[0][1].get("run_pin_ref") else None
        inherited_pin = (f"{parsed['version']}; source {parsed['commit']}" if parsed and parsed.get("commit")
                         else pointer(selected[0][1]["verdict_pin_ref"]) if selected else None)
        manifest.append({
            "repository": row["repository"], "label": label, "layers": row["layers"],
            "disposition": row["disposition"], "install": False, "invoke": False,
            "role": "Retained selected role only" if selected or row.get("adopted_pin") else "Discovery proposal only",
            "pin": row.get("adopted_pin") or inherited_pin,
            "observed_source_pin": source_map.get(row["repository"], {}).get("commit") or entries.get(row["repository"], {}).get("observed_head"),
            "gap": "Layer is not FINAL; named selected role still subject to full-layer completion" if label == "TRIAL" else
                   "Excluded from this workload; installs nothing" if row["disposition"] == "OUT-OF-SCOPE" else
                   "No candidate pin screen, independent implementation review, native E2E or invoke evidence for this proposed Jev/new role",
            "routing_ref": f"{PREFIX}/routing.json#/repositories/{len(manifest)}",
            "citations": row["citations"],
        })
    summary = {"routing_rows": len(routing), "jev_project_entries": len(index_names),
               "jev_directory_plus_org_identities": len(entries),
               "dispositions": dict(sorted(Counter(r["disposition"] for r in routing).items())),
               "manifest_labels": dict(sorted(Counter(r["label"] for r in manifest).items())),
               "new_stars": len(diff["new"]), "unstarred": len(diff["unstarred"]),
               "legacy_undecided": len(prior), "legacy_now_classified": len(prior & set(c)),
               "final_layers_at_base": sum(l.get("terminal_state") == "FINAL" for l in final_stack["layers"])}
    assert not any(r["install"] or r["invoke"] for r in manifest)
    assert summary["final_layers_at_base"] == 0
    assert summary["manifest_labels"].get("FINAL", 0) == 0
    builder_receipt = {"kind": "native_builder_public_refresh", "base_commit": BASE,
        "command": f"python3 scripts/build_ecosystem.py --refresh-stars --starred-output {PREFIX}/public-starred.refreshed.json",
        "exit_code": 0, "count": snapshot["count"], "new_count": len(diff["new"]),
        "observed_at": snapshot["retrieved_at"], "endpoint": snapshot["endpoint"],
        "snapshot_sha256": INPUTS[f"{PREFIX}/public-starred.refreshed.json"]["sha256"],
        "builder_sha256": INPUTS["scripts/public_starred.py"]["sha256"],
        "raw_api_retained": False, "allowed_fields": snapshot["fields_allowlisted"]}
    protocol = {"base_commit": BASE, "kind": "reverified_resolution_protocol",
        "coordination_protocol_sha256": "d35af84758a6eb78a468ae775766543c1bbd63e61b7886e0baff0505b8db95ff",
        "authority": {"record": "command-center/research-cc-role-20261008/direction-cc-20261015T1946Z-north-star-new-wsl-takeover.md",
                      "sha256": "4dfcb47245607bd3b3fb53bbdd49a561b1b157beccf02f9309623b23ffa2ad82", "ruling": 4,
                      "verification": "Exact local bytes hash checked; authority prose and unpublished data not copied"},
        "step_1": {"canonical_count": len(c), "canonical_retrieved_at": canonical["retrieved_at"],
                   "finalization_count": len(finalization["repositories"]), "out_of_scope": 58,
                   "legacy_audit_count": len(a), "legacy_audit_checked_at": audit["checked_at"],
                   "wave_registry": waves, "final_layers_at_base": summary["final_layers_at_base"]},
        "step_2": {"completed_sweeps": [s["sweep_id"] for s in ledger["sweeps"] if s["status"] == "completed"],
                   "layer_contexts": f"{PREFIX}/layer-contexts.json", "omission_clears_survivor": False,
                   "missing_return_is_adjudication": False, "pending_unappended_sweep": "None supplied; revisit on retained newer evidence"},
        "step_3": {"delta": "New/legacy-undecided star identities plus all pinned Jev directory project identities and the public TypeSafe organization projection; no re-adjudication of prior scope, no installs or runtime selection", "summary": summary},
        "preserved_old_worktree": {"tracked_diff": "none", "untracked": "blobs/ contains two DocVortex middle JSON artifacts; not a tracked #1016 change; original producer provenance unverified",
            "sha256": ["40cdf0eb029358d92eb709519f2be40f5d4a86e764699da932838e1778116638", "9e3719797163c22d28bb02e81df694a6c7c6f895956dea835f0185ca2ef60648"],
            "action": "untouched in old worktree; fresh branch/worktree from origin/main"},
        "inputs": dict(sorted(INPUTS.items()))}
    gaps = {"base_commit": BASE, "named_gaps": [
        {"id": "NO-FINAL-ROWS", "scope": "NativeHorizonNY defaults", "reason": "All35 final-stack terminal_state values are null at this base; selected or classified rows cannot be promoted to FINAL", "next_action": "Complete existing layer pipeline and require explicit FINAL before default proposal"},
        {"id": "DISCOVERY-SCREEN", "scope": "Unscreened new/Jev identities", "reason": "A pinned index/metadata claim is not a target source pin or requirements screen", "next_action": "Owning layer's next sweep screens only the named new role; no trial install before passing"},
        {"id": "CUMULATIVE-SURVIVORS", "scope": "All routed layers", "reason": "Later omission and absent votes cannot remove unresolved candidates; detailed refs retained per layer", "next_action": "Resolve/compare existing carried survivors before broad discovery; use newer retained completed sweeps if supplied"},
        {"id": "JEV-SCORED-AND-ADMISSION", "scope": "Trading Jev classification and feature use", "reason": "Two10-15 decisions prove synthetic/local plumbing and corrections, not scored model selection, order or feature admission", "next_action": "Owning trading-cc frozen comparison after its named inputs/reviews; separate dated availability/threshold admission"},
        {"id": "TYPESAFE-ORG-ASSOCIATION", "scope": "Organization-owned forks/infrastructure", "reason": "Public membership does not establish a Jev workload or supersede selected upstreams", "next_action": "Retain explicit excluded/reference rows; independently justify any new role"},
        {"id": "HISTORIC-UNDECIDED-MEANING", "scope": "33 legacy-audit gaps", "reason": "26 already have later canonical scope/seed dispositions and7 do not; no350-row resurvey inferred", "next_action": "Carry26 existing decisions unchanged and screen only7 new proposals"},
        {"id": "RD-AGENT-NARRATIVE-DRIFT", "scope": "Research-factors survivor narrative", "reason": "The10-15 Jev build narrative carries RD-Agent from09-23, but the retained09-26 fit return substantively refutes it in both families; this is not a missing vote", "next_action": "Use the exact latest-candidate adjudication and retained fit vote in layer-contexts; do not silently rewrite the earlier narrative or re-adjudicate RD-Agent"},
    ]}
    outputs = {"builder-receipt.json": builder_receipt, "star-diff.json": diff,
               "jev-inventory.json": {"index_repository": awesome["repository"], "index_pin": awesome["commit"],
                                      "project_count": len(index_names), "identity_count": len(entries),
                                      "limits": upstream["limits"], "repositories": [entries[k] for k in sorted(entries)]},
               "layer-contexts.json": {"base_commit_ref": f"{PREFIX}/protocol.json#/base_commit", "layers": contexts},
               "routing.json": {"base_commit": BASE, "summary": summary, "repositories": routing},
               "manifest-proposal.json": {"target": "NativeHorizonNY", "base_commit": BASE,
                                          "proposal_only": True, "summary": summary,
                                          "rows": manifest}, "named-gaps.json": gaps, "protocol.json": protocol}
    def cell(value):
        return str(value).replace("|", "\\|").replace("\n", " ")
    table = ["# Proposed layer routing", "",
             "Source review only. Citations bind discovery/scope, not implementation quality or an installation screen. "
             "The JSON rows retain all citations, reasons and context-only exclusions; layer-contexts.json records the exact verdicts and cumulative sweep evidence.", "",
             "| Repository | Catalog layer(s) | Proposed disposition | Source citation |",
             "| --- | --- | --- | --- |"]
    for row in routing:
        cite = row["citations"][0]
        target = cite if cite.startswith("https://") else "../../../" + cite
        table.append(f"| {cell(row['repository'])} | {cell(', '.join(row['layers']))} | {row['disposition']} | [source]({target}) |")
    outputs["routing.md"] = "\n".join(table) + "\n"
    return outputs, summary


def main():
    outputs, summary = derive()
    checking = sys.argv[1:] == ["--check"]
    assert not sys.argv[1:] or checking
    for name, value in outputs.items():
        expected = value if isinstance(value, str) else json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
        path = HERE / name
        if checking:
            assert path.read_text() == expected, f"Derived artifact drift: {name}"
        else:
            path.write_text(expected)
    print(json.dumps({"mode": "check" if checking else "write", "summary": summary}, sort_keys=True))


if __name__ == "__main__":
    main()
