#!/usr/bin/env python3
"""Build a source-bound local Architecture page, preserving the input records.

Uses the installed zstd stream reader through architecture_sources, the native
landscape layer contract, and the existing local-pages document/publish API.
No install, gate adjudication, network fetch or credential/config read.
"""
from __future__ import annotations

import argparse
import copy
from datetime import date, datetime, timedelta, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RETAINED_REFRESH = Path("research/fullspeed-20261008/g5-stars-gap/local-pages/refresh-receipt.json")
SOURCE_POLICY_PATH = HERE / "source_policy.json"
# Manifest views read only these records, each under a role source_policy.json
# already grants for that exact path. An absent record leaves its view unreported.
MANIFEST_SOURCES = (
    ("matrix", "catalogs/landscape/component-evidence-matrix.json", "architecture_static"),
    ("plan", "evidence/artifacts/new-wsl-install-plan-20261002/install-plan.json", "architecture_receipt"),
    ("handbook", "docs/new-wsl-handbook.json", "architecture_receipt"),
    ("ruleset", ".github/main-ruleset.json", "architecture_receipt"),
    ("gates", "catalogs/us-equities/gates-20260922.json", "architecture_receipt"),
    ("runtime", "catalogs/us-equities/runtime-target.json", "architecture_receipt"),
)
MANIFEST_STYLE = HERE / "assets/architecture-manifest.css"
MODULES = ("architecture_sources", "architecture_inventory", "architecture_evidence", "architecture_view",
           "architecture_manifest", "architecture_diagrams", "evidence_sources", "build_pages", "sanitization", "source_policy")


def load(name: str) -> Any:
    spec = importlib.util.spec_from_file_location("local_architecture_" + name, HERE / (name + ".py"))
    if spec is None or spec.loader is None:
        raise ValueError("local architecture module unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def architecture_reads(root: Path, state_root: Path):
    return load("source_policy").ArchitectureReads(root, state_root, policy_path=SOURCE_POLICY_PATH)


def _normalize_invocation_roles(components: list[dict], role_map: dict, attribution: dict | None = None) -> None:
    """Project copied rows once, keeping original instances for future passes."""
    projected = {}
    for component in components:
        invoke = component.get("invoke")
        if not isinstance(invoke, dict):
            continue
        if id(invoke) in projected:
            component["invoke"] = projected[id(invoke)]
            continue
        normalized = copy.deepcopy(invoke)
        if attribution is not None:
            normalized["role_attribution"] = copy.deepcopy(attribution)
        rows, groups = [], {}
        for row in invoke.get("roles", []):
            if row.get("client") != "Codex":
                rows.append(copy.deepcopy(row))
                continue
            observations = row.get("instance_observations") or [row]
            for observation in observations:
                original = copy.deepcopy(observation)
                instance = original.get("source_instance", original.get("role"))
                original["source_instance"] = instance
                owner = role_map.get(instance) or "unattributed instances"
                key = (owner, original.get("server"), original.get("window_hours"))
                if key not in groups:
                    group = copy.deepcopy(original)
                    group.update(
                        role=owner,
                        attribution=("retained launch-window projection" if attribution else "launch-window registry") if role_map.get(instance) else "unattributed",
                        source_instances=[], instance_observations=[],
                        aggregation_scope="sum of published instance counts; distinct cross-instance conversations unverified",
                    )
                    group.pop("source_instance", None)
                    if not role_map.get(instance) and attribution is not None:
                        group["attribution_reason"] = attribution["reason"] or "instance absent or unassigned in retained role projection"
                    groups[key] = group
                    rows.append(group)
                group = groups[key]
                group["instance_observations"].append(original)
                if instance not in group["source_instances"]:
                    group["source_instances"].append(instance)
        for group in groups.values():
            for field in ("calls", "conversations"):
                values = [row.get(field) for row in group["instance_observations"]]
                group[field] = sum(values) if all(isinstance(value, int) and not isinstance(value, bool) and value >= 0 for value in values) else None
        normalized["roles"] = rows
        projected[id(invoke)] = normalized
        projected[id(normalized)] = normalized
        component["invoke"] = normalized


def _retained_projection(state_root: Path, pages: Any, reads) -> dict:
    """Capture the native composer's sanitized refresh JSON once, without links."""
    path = state_root / RETAINED_REFRESH
    try:
        raw, captured = reads.read("architecture_projection", path, max_bytes=pages.MAX_BYTES)
    except OSError as error:
        raise ValueError("retained native readiness projection is unavailable") from error
    document = pages.strict_json(raw)
    if not isinstance(document, dict) or document.get("schema_version") != 1 or isinstance(document.get("schema_version"), bool) or document.get("kind") != "local_page_refresh":
        raise ValueError("retained native readiness projection has an unsupported schema")

    def utc(value):
        if not isinstance(value, str) or not 20 <= len(value) <= 40 or "T" not in value or not value.endswith(("Z", "+00:00")):
            return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo is not None and parsed.utcoffset().total_seconds() == 0 else None
        except ValueError:
            return None

    generated = document.get("generated_utc")
    manifest_sha = document.get("native_readiness_manifest_sha256")
    roles = document.get("adoption_role_attribution")
    window = roles.get("window") if isinstance(roles, dict) else None
    instances = roles.get("instances") if isinstance(roles, dict) else None
    role_map = instances.get("role_map") if isinstance(instances, dict) else None
    if utc(generated) is None or not isinstance(manifest_sha, str) or not re.fullmatch(r"[a-fA-F0-9]{64}", manifest_sha):
        raise ValueError("retained native readiness projection has invalid identity or generated UTC metadata")
    if not isinstance(window, dict) or utc(window.get("start_utc")) is None or utc(window.get("end_utc")) is None or utc(window["start_utc"]) >= utc(window["end_utc"]) or not isinstance(role_map, dict) or len(role_map) > 1024:
        raise ValueError("retained native readiness projection has invalid dated role attribution")
    safe_label = re.compile(r"[A-Za-z0-9][A-Za-z0-9 ._:/()+-]{0,119}\Z")
    for instance, role in role_map.items():
        if not isinstance(instance, str) or not safe_label.fullmatch(instance) or role is not None and (not isinstance(role, str) or not safe_label.fullmatch(role)):
            raise ValueError("retained native readiness projection has invalid role labels")
    source = {key: captured[key] for key in ("path", "sha256", "bytes")}
    source.update(generated_utc=generated, status="recorded sanitized refresh projection", scope="retained native identity and dated role attribution; referenced inputs unread")
    return {"source": source, "manifest_sha256": manifest_sha, "generated_utc": generated, "window": {key: window[key] for key in ("start_utc", "end_utc")}, "role_map": dict(role_map)}


def build(root: Path, state_root: Path, output_dir: Path, receipt: Path,
          first_layer: str | None = None, asset: Path | None = None) -> dict:
    pages = load("build_pages")
    output_dir, receipt = pages.no_symlinks(output_dir), pages.no_symlinks(receipt)
    if receipt.is_relative_to(output_dir):
        raise ValueError("architecture receipt must remain outside serving root")
    reads = architecture_reads(root, state_root)
    policy_module = load("source_policy")
    retained = _retained_projection(state_root, pages, reads)
    model = load("architecture_sources").build(root, state_root, asset, reads=reads)
    inventory = load("architecture_inventory").build(root, state_root, reads=reads)
    evidence = load("architecture_evidence")
    model["host_receipts"] = evidence.host_receipts_index(state_root, reads=reads)
    model["sources"] = list(model.get("sources") or []) + model["host_receipts"].get("sources", []) + [retained["source"]]
    manifest = load("architecture_manifest").build(root, model, reads, MANIFEST_SOURCES, pages=pages.PAGES, refresh_utc=retained["generated_utc"])
    model["manifest"] = manifest
    custody = {(source.get("path"), source.get("sha256")) for source in model["sources"] if isinstance(source, dict)}
    model["sources"] += [source for source in manifest["sources"] if (source["path"], source["sha256"]) not in custody]
    if hasattr(evidence, "attach_inventory"):
        inventory["items"] = evidence.attach_inventory(inventory.get("items", []), model.get("evidence_index", {}), root=root, state_root=state_root, reads=reads)
    observation = model.get("adoption_observation") or {}
    window_matches = False
    try:
        generated_observation = datetime.fromisoformat(observation["generated_utc"].replace("Z", "+00:00"))
        hours = observation.get("window_hours")
        start = datetime.fromisoformat(retained["window"]["start_utc"].replace("Z", "+00:00"))
        end = datetime.fromisoformat(retained["window"]["end_utc"].replace("Z", "+00:00"))
        window_matches = isinstance(hours, int) and not isinstance(hours, bool) and hours > 0 and generated_observation == end and generated_observation - timedelta(hours=hours) == start
    except (KeyError, ValueError, TypeError, AttributeError):
        pass
    attribution = {"status": "retained window matches published observation" if window_matches else "unattributed", "reason": None if window_matches else "retained role projection window differs from the published observation window", "window": retained["window"], "source": {**retained["source"], "locator": "/adoption_role_attribution/instances/role_map"}}
    components = inventory.get("items", []) + [component for layer in model["layers"] for category in ("winners", "candidates", "alternatives", "rejected", "source_quality", "g5_candidates") for component in layer.get(category, []) if isinstance(component, dict)]
    _normalize_invocation_roles(components, retained["role_map"] if window_matches else {}, attribution)
    detail_outputs = {}
    body, counts = load("architecture_view").render(model, inventory, first_layer, detail_outputs=detail_outputs)
    if first_layer is None and counts["rendered_layer_count"] != model["layer_count"]:
        raise ValueError("architecture section count differs from canonical landscape")
    if counts["rendered_layer_count"] == 0:
        raise ValueError("selected architecture layer does not exist")
    generated = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    manifest_sha = retained["manifest_sha256"]
    scope = "Builder reads dated landscape choices, current CC stage records and published invoke observations."
    style_raw = policy_module._read_regular(MANIFEST_STYLE, 1024 * 1024)
    style = "\n  <style>\n" + style_raw.decode("utf-8") + "  </style>"
    html = pages.document("architecture", "Architecture by layer", "The whole stack first, then each layer's selected tools, alternatives, inventories and evidence.", scope, body, generated, manifest_sha, [], head=style)
    builder_path = Path(__file__).resolve()
    outputs = {"architecture.html": html}
    for name, raw in detail_outputs.items():
        detail_body = '<p><a href="architecture.html">All Architecture layers</a></p><div id="architecture-detail-content">' + raw.decode("utf-8") + '</div>'
        detail = pages.document("architecture", "Architecture component detail", "Expand a table to read its component evidence.", scope, detail_body, generated, manifest_sha, [])
        outputs[name] = detail.replace(b"<head>", b'<head>\n  <base href="../../">', 1).replace(b'href="#architecture-custody"', b'href="architecture.html#architecture-custody"')
    if len(html) >= 1_500_000:
        raise ValueError("initial Architecture HTML must be under 1500000 bytes")
    components = [item for item in inventory.get("items", []) if item.get("kind") == "component"]
    e2e_components = sum(1 for item in components if (item.get("e2e") or {}).get("sha256") and (item.get("e2e") or {}).get("path") and "e2e" in str((item.get("e2e") or {}).get("kind", "")).lower())
    for name in ("site.css", "site.js"):
        outputs["assets/" + name] = policy_module._read_regular(HERE / "assets" / name, 8 * 1024 * 1024)
    result = {"schema": "local-architecture/1", "generated_utc": generated,
              "builder": {"path": str(builder_path), "sha256": hashlib.sha256(policy_module._read_regular(builder_path, 8 * 1024 * 1024)).hexdigest()},
              **counts, "first_layer": first_layer,
                "page_bytes": len(html), "detail_file_count": len(detail_outputs),
                "local_host_receipts": model["host_receipts"],
                "e2e_components": {"with_evidence": e2e_components, "total": len(components), "successful_qualifying": sum(1 for item in components if (item.get("e2e") or {}).get("verified"))},
              "design": model.get("design"), "g5": model.get("g5"),
              "manifest": {**manifest["receipt"], "design": load("architecture_diagrams").DESIGN,
                           "style": {"path": str(MANIFEST_STYLE), "sha256": hashlib.sha256(style_raw).hexdigest()}},
              "invocation_source": {key: (model.get("adoption_observation") or {}).get(key) for key in ("path", "sha256", "generated_utc", "window_hours")},
              "role_attribution_sources": [attribution["source"]], "role_attribution": attribution,
                "modules": [{"path": str(HERE / (name + ".py")), "sha256": hashlib.sha256(policy_module._read_regular(HERE / (name + ".py"), 8 * 1024 * 1024)).hexdigest()} for name in MODULES if (HERE / (name + ".py")).exists()],
              "sources": model.get("sources"), "excluded_supplements": model.get("excluded_supplements", []),
              "inventory_sources": inventory.get("sources"),
              "source_policy": dict(reads.policy.receipt),
              "inventory_coverage": inventory.get("coverage"),
              "unapproved_inventory_counts": inventory.get("unapproved_counts", {"total": 0, "by_kind_root": []}),
              "native_readiness_manifest_sha256": manifest_sha,
              "native_readiness_source": retained["source"],
              "outputs": {name: {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)} for name, raw in outputs.items()},
                "limits": ["Published source records and metadata observations do not confer gate acceptance or fresh-session evidence.", "Catalog component/repository joins and the committed inventory mapping associate layers; remaining unmapped items carry their reason.", "Initial HTML defers closed component tables to generated layer pages, loaded only on expansion."]}
    pages.publish(output_dir, receipt, outputs, result, architecture_details=True)
    return result


FINAL_STACK_SCRIPT = ROOT / "scripts/final_stack.py"


def _final_stack_flags(document: dict, today) -> dict:
    """The report-only flags of `scripts/final_stack.py --check`, from the script's own flags() on the read document."""
    scripts = str(FINAL_STACK_SCRIPT.parent)
    added = scripts not in sys.path
    if added:
        sys.path.insert(0, scripts)
    try:
        spec = importlib.util.spec_from_file_location("local_architecture_final_stack", FINAL_STACK_SCRIPT)
        if spec is None or spec.loader is None:
            raise ImportError("final_stack.py unavailable")
        module = importlib.util.module_from_spec(spec)
        # final_stack.py declares a dataclass, which resolves its module through sys.modules.
        sys.modules[spec.name] = module
        try:
            spec.loader.exec_module(module)
            return module.flags(document, today)
        finally:
            sys.modules.pop(spec.name, None)
    finally:
        if added:
            sys.path.remove(scripts)


def _commit(root: Path) -> str | None:
    """The checked-out commit the cited repository paths belong to, or None outside a Git checkout."""
    try:
        result = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    value = result.stdout.strip()
    return value if result.returncode == 0 and re.fullmatch(r"[0-9a-f]{40}", value) else None


def build_layer_pages(root: Path, output_dir: Path, receipt: Path, *, state_root: Path | None = None,
                      today: date | None = None, commit: str | None = None, generated: str | None = None) -> dict:
    """Render the Foundation and North-star pages and their manifests from committed repository records only."""
    pages = load("build_pages")
    output_dir, receipt = pages.no_symlinks(output_dir), pages.no_symlinks(receipt)
    if receipt.is_relative_to(output_dir):
        raise ValueError("layer-page receipt must remain outside serving root")
    reads = architecture_reads(root, state_root if state_root is not None else root / ".layer-pages-no-state")
    manifest_module, view = load("architecture_manifest"), load("architecture_view")
    policy_module, sanitizer = load("source_policy"), load("sanitization")
    documents, captured = {}, {}
    for name, relative, role in (("final_stack", manifest_module.FINAL_STACK, "architecture_final_stack"), ("matrix", manifest_module.MATRIX, "architecture_static"),
                                 ("foundation", manifest_module.CATALOGS["foundation"], "architecture_catalog"), ("us-equities", manifest_module.CATALOGS["us-equities"], "architecture_catalog")):
        raw, record = reads.read(role, root / relative, max_bytes=16 * 1024 * 1024)
        document = pages.strict_json(raw)
        if not isinstance(document, dict):
            raise ValueError(relative + " must be a JSON object")
        documents[name] = document
        captured[name] = {"path": relative, "sha256": record["sha256"], "bytes": record["bytes"], "role": role}
    generated = generated or datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    today = today or datetime.fromisoformat(generated.replace("Z", "+00:00")).date()
    commit = commit or _commit(root)
    flags = _final_stack_flags(documents["final_stack"], today)
    style_raw = policy_module._read_regular(MANIFEST_STYLE, 1024 * 1024)
    style = "\n  <style>\n" + style_raw.decode("utf-8") + "  </style>"
    outputs, summaries = {}, {}
    final_sha = captured["final_stack"]["sha256"]
    for key, config in manifest_module.LAYER_PAGES.items():
        catalog = config["catalog"]
        sources = [captured["final_stack"], captured[catalog], captured["matrix"]]
        manifest = manifest_module.layer_manifest(root, key, documents["final_stack"], documents[catalog], documents["matrix"],
                                                  commit=commit, sources=sources, flags=flags)
        manifest = sanitizer.sanitize(manifest)
        manifest["page_file"] = {"html": config["page"] + ".html", "manifest": config["manifest"]}
        manifest["generated_utc"] = generated
        body, counts = view.render_layer_page(manifest)
        expected = len([row for row in documents[catalog].get("layers", []) if isinstance(row, dict)])
        if counts["rendered_layer_count"] != expected:
            raise ValueError(f"{key} page renders {counts['rendered_layer_count']} layers; the catalog has {expected}")
        scope = f"committed records at {commit or 'an unrecorded commit'}; final-stack.json checked_at {documents['final_stack'].get('checked_at')}"
        lede = ("The 20 foundation layers, what runs on the workstation, and what each layer still needs before it is finalized." if catalog == "foundation"
                else "The 12 trading layers, how the trading data flows, and what each layer still needs before it is finalized.")
        html = pages.document(config["page"], config["title"], lede, scope, body, generated, final_sha, [], head=style,
                              digest_label="final-stack.json SHA-256")
        manifest_raw = (json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
        outputs[config["page"] + ".html"] = html
        outputs[config["manifest"]] = manifest_raw
        summaries[key] = {**counts, "page": config["page"] + ".html", "manifest": config["manifest"], "states": manifest["summary"]["states"],
                          "conditions_met": manifest["summary"]["conditions_met"], "manifest_sha256": hashlib.sha256(manifest_raw).hexdigest()}
    for name in ("site.css", "site.js"):
        outputs["assets/" + name] = policy_module._read_regular(HERE / "assets" / name, 8 * 1024 * 1024)
    builder_path = Path(__file__).resolve()
    result = {"schema": "local-architecture-layer-pages/1", "generated_utc": generated, "commit": commit,
              "builder": {"path": str(builder_path), "sha256": hashlib.sha256(policy_module._read_regular(builder_path, 8 * 1024 * 1024)).hexdigest()},
              "manifest_schema": manifest_module.LAYER_SCHEMA, "pages": summaries, "sources": list(captured.values()),
              "flags_today": flags.get("today"), "design": load("architecture_diagrams").DESIGN,
              "style": {"path": str(MANIFEST_STYLE), "sha256": hashlib.sha256(style_raw).hexdigest()},
              "source_policy": dict(reads.policy.receipt),
              "outputs": {name: {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)} for name, raw in outputs.items()},
              "limits": ["Pages project committed records; they establish no new E2E, invoke or verdict.",
                         "The data-layer decisions are cited by record name; their text is not in this repository."]}
    pages.publish(output_dir, receipt, outputs, result)
    return result


def refresh_if_changed(root: Path, state_root: Path, output_dir: Path, receipt: Path) -> dict:
    """Authorize source metadata before deciding whether a refresh is reusable."""
    pages = load("build_pages")
    policy = load("source_policy")
    reads = architecture_reads(root, state_root)
    evidence = load("architecture_evidence")
    observation = evidence.invocation_source(state_root, reads=reads)
    signature = {"adoption_sha256": observation.get("sha256"), "source_policy_sha256": reads.policy.receipt["sha256"], "files": []}
    signature["inventory_sources"] = load("architecture_inventory").input_signature(root, state_root, reads=reads)
    manifest = root / "catalogs/landscape/manifest.json"
    manifest_raw, _ = reads.read("architecture_manifest", manifest, max_bytes=16 * 1024 * 1024)
    declaration = json.loads(manifest_raw)
    canonical = set(declaration.get("catalogs", {}).values()) if isinstance(declaration.get("catalogs"), dict) else set()
    selections = []
    for path in sorted((root / "catalogs/landscape").glob("*.json")):
        relative = path.relative_to(root).as_posix()
        if policy.protected_path(relative):
            raise policy.SourcePolicyError("protected supplementary catalog excluded before cache access")
        if reads.excluded_supplement(path) is not None:
            continue  # reviewed policy exclusion; never opened, so never an input
        role = "architecture_manifest" if path == manifest else "architecture_catalog" if relative in canonical else "architecture_supplement"
        selections.append((path, role))
    selections += [
        (state_root / "coordination/command-center/pages/cc-now.json", "architecture_projection"),
        (root / "adoption/skills/manifest.json", "architecture_skill_manifest"),
        (root / "manifests/stack.json", "architecture_registry"),
        (root / "adoption/manifest.json", "architecture_registry"),
        (root / "manifests/evidence.json", "architecture_registry"),
        (root / "catalogs/north-star/readiness.json", "architecture_readiness"),
    ]
    selections += [(path, "architecture_projection") for path in (
        state_root / "coordination/command-center/pages/automation-projection.json",
        state_root / "coordination/command-center/pages/host-receipts-index.json",
        state_root / RETAINED_REFRESH,
    ) if path.exists()]
    selected = {path for path, _ in selections}
    selections += [(root / relative, role) for _, relative, role in MANIFEST_SOURCES
                   if root / relative not in selected and (root / relative).is_file()]
    for path, role in selections:
        _, captured = reads.read(role, path, max_bytes=16 * 1024 * 1024)
        signature["files"].append([str(path), captured["bytes"], captured["sha256"]])
    archive = state_root / load("architecture_sources")._FINAL_ASSET
    if archive.exists():
        with reads.open("architecture_g5_asset", archive, max_bytes=512 * 1024 * 1024) as handle:
            stat = os.fstat(handle.fileno())
            signature["files"].append([str(archive), stat.st_size, stat.st_mtime_ns])
    helper_paths = [HERE / (name + ".py") for name in ("architecture_builder",) + MODULES]
    helper_paths += [HERE / "assets/site.css", HERE / "assets/site.js", MANIFEST_STYLE]
    for path in helper_paths:
        if path.exists():
            raw = policy._read_regular(path, 8 * 1024 * 1024)
            signature["files"].append([str(path), len(raw), hashlib.sha256(raw).hexdigest()])
    cache_path = pages.no_symlinks(receipt.with_name("architecture-cache.json"))
    if cache_path.is_relative_to(output_dir):
        raise ValueError("architecture cache must remain outside the served root")
    if cache_path.exists() and receipt.exists() and (output_dir / "architecture.html").exists():
        previous = json.loads(policy._read_regular(cache_path, 8 * 1024 * 1024))
        if previous.get("signature") == signature:
            result = json.loads(policy._read_regular(receipt, 8 * 1024 * 1024))
            pages.prune_architecture_details(output_dir, result.get("outputs") or {})
            return result
    result = build(root, state_root, output_dir, receipt)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = pages.no_symlinks(cache_path.with_suffix(".tmp"))
    temporary.write_text(json.dumps({"signature": signature, "generated_utc": result["generated_utc"]}, sort_keys=True) + "\n")
    temporary.replace(cache_path)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--state-root", type=Path, default=Path.home() / ".local/state/native-agent-stack")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--first-layer")
    parser.add_argument("--g5-asset", type=Path)
    args = parser.parse_args(argv)
    output = args.output_dir or args.state_root / "coordination/command-center/local-pages"
    receipt = args.receipt or args.state_root / "research/fullspeed-20261008/g5-stars-gap/local-pages/architecture/architecture-receipt.json"
    try:
        result = build(args.root, args.state_root, output, receipt, args.first_layer, args.g5_asset)
    except (OSError, ValueError, KeyError, TypeError, ImportError) as error:
        parser.exit(1, f"architecture: build failed ({type(error).__name__}): {error}\n")
    print(json.dumps({"output": str(output / "architecture.html"), "receipt": str(receipt),
                      "builder_sha256": result["builder"]["sha256"],
                      "rendered_layer_count": result["rendered_layer_count"],
                      "canonical_layer_count": result["canonical_layer_count"],
                      "unmapped_inventory_items": result["unmapped_inventory_items"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
