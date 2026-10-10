"""Check recorded starred-repository intake joins without promoting discovery to acceptance."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import re
from urllib.parse import urlsplit

try:
    from .catalog_decisions import identity, load, pointer, require, safe_file
except ImportError:
    from catalog_decisions import identity, load, pointer, require, safe_file

SCOPES = {"IN-SCOPE", "OUT-OF-SCOPE", "NEEDS-EVIDENCE", "ARCHIVED", "SUPERSEDED"}
TIERS = {"tier-1", "tier-2"}
REGISTRY = "catalogs/sota-convergence/layer-verdict-waves.json"
PRIVATE_FIELDS = {"owner", "user", "login", "email", "avatar_url", "private", "password",
                  "token", "access_token", "api_key", "authorization", "credential"}


def _public_fields(value):
    if isinstance(value, dict):
        require(not PRIVATE_FIELDS.intersection(str(key).lower() for key in value),
                "starred convergence contains account or private fields")
        for child in value.values():
            _public_fields(child)
    elif isinstance(value, list):
        for child in value:
            _public_fields(child)


def _resolve(root, ref, documents):
    require(isinstance(ref, str) and bool(ref), "source reference must be text")
    if "://" in ref:
        url = urlsplit(ref)
        paths = {"github.com": r"/[^/]+/[^/]+/blob/[0-9a-f]{40}/.+",
                 "raw.githubusercontent.com": r"/[^/]+/[^/]+/[0-9a-f]{40}/.+"}
        require(url.scheme == "https" and url.netloc in paths and not url.query
                and bool(re.fullmatch(paths[url.netloc], url.path)),
                "source URL must identify pinned public GitHub bytes")
        return None
    path, separator, fragment = ref.partition("#")
    require(bool(separator) and path.endswith(".json"), "source reference needs a JSON pointer")
    if path not in documents:
        documents[path] = load(root, path)
    return pointer(documents[path], fragment)


def validate_convergence(root: Path, snapshot: dict) -> dict:
    """Validate a completed intake manifest, retaining compatibility with older snapshots."""
    if "convergence_manifest" not in snapshot:
        return {"status": "legacy", "count": len(snapshot.get("repositories", []))}
    manifest_path = snapshot["convergence_manifest"]
    manifest = load(root, manifest_path)
    require(manifest.get("schema_version") == 1, "unsupported starred convergence schema")
    rows, stars = manifest.get("repositories"), snapshot.get("repositories")
    require(isinstance(rows, list) and isinstance(stars, list), "starred repositories must be arrays")
    require(manifest.get("count") == snapshot.get("count") == len(rows) == len(stars),
            "starred convergence count differs from snapshot")
    by_repo = {}
    for star in stars:
        name = identity(star.get("repository"))
        require(name not in by_repo, "duplicate snapshot repository identity")
        by_repo[name] = star
    layer_doc = load(root, "catalogs/foundation/manifest.json")
    layers = {row["id"] for row in layer_doc["layers"]}
    skills = "catalogs/landscape/skills-lifecycle.json"
    if safe_file(root, skills).exists():
        layers.update(row["layer_id"] for row in load(root, skills)["tasks"])
    seeds_path = manifest.get("seed_manifest")
    seed_doc = load(root, seeds_path)
    require(seed_doc.get("schema_version") == 1 and isinstance(seed_doc.get("seeds"), list),
            "unsupported starred seed schema")
    documents = {manifest_path: manifest, seeds_path: seed_doc}
    for document in (manifest, snapshot, seed_doc):
        _public_fields(document)
    for seed in seed_doc["seeds"]:
        identity(seed.get("repository"))
        require(seed.get("layer") in layers, "seed has unsupported canonical layer")
        require(isinstance(seed.get("reason"), str) and bool(seed["reason"].strip()),
                "seed requires a recorded reason")
        refs = seed.get("source_refs")
        require(isinstance(refs, list) and bool(refs), "seed requires source references")
        for ref in refs:
            _resolve(root, ref, documents)
        try:
            checked_at = datetime.fromisoformat(seed["checked_at"].replace("Z", "+00:00"))
        except (KeyError, TypeError, ValueError, AttributeError):
            require(False, "seed checked_at must be a UTC timestamp")
        require(checked_at.tzinfo is not None and checked_at.utcoffset() == timezone.utc.utcoffset(None),
                "seed checked_at must be a UTC timestamp")
    seen, counts = set(), Counter({scope.lower().replace("-", "_"): 0 for scope in SCOPES})
    for row in rows:
        name, scope = identity(row.get("repository")), row.get("scope")
        require(name not in seen, "duplicate convergence repository identity")
        seen.add(name)
        require(name in by_repo, "convergence repository is absent from snapshot")
        require(scope in SCOPES, "completed convergence scope cannot be PENDING or unknown")
        require(isinstance(row.get("reason"), str) and bool(row["reason"].strip()),
                "convergence disposition requires a recorded reason")
        keys, refs = row.get("layer_keys"), row.get("seed_refs")
        require(isinstance(keys, list) and all(isinstance(key, str) for key in keys)
                and len(keys) == len(set(keys)) and set(keys) <= layers,
                "disposition has unsupported or duplicate canonical layers")
        require(isinstance(refs, list), "disposition seed_refs must be an array")
        star = by_repo[name]
        status = str(star.get("disposition_status", "")).upper().replace("_", "-")
        if status == "IN-SCOPE-SOURCE-REVIEW":
            status = "IN-SCOPE"
        require(status == scope
                and star.get("reason") == row["reason"] and star.get("layer_keys") == keys
                and star.get("seed_refs") == refs and star.get("convergence_manifest") == manifest_path
                and star.get("decision_manifest") == manifest_path,
                "snapshot disposition disagrees with convergence manifest")
        require(isinstance(star.get("disposition"), str) and bool(star["disposition"].strip())
                and not star["disposition"].strip().upper().startswith("PENDING"),
                "snapshot disposition must be completed")
        covered = set()
        for ref in refs:
            require(isinstance(ref, str) and ref.partition("#")[0] == seeds_path,
                    "seed reference must use the declared seed manifest")
            seed = _resolve(root, ref, documents)
            require(isinstance(seed, dict) and identity(seed.get("repository")) == name,
                    "seed reference repository disagrees with disposition")
            require(seed.get("layer") in keys, "seed reference layer disagrees with disposition")
            covered.add(seed["layer"])
        if scope == "IN-SCOPE":
            require(bool(keys) and covered == set(keys), "in-scope disposition needs a seed for every layer")
        elif scope in {"OUT-OF-SCOPE", "NEEDS-EVIDENCE"}:
            require(not keys and not refs, "unscoped disposition must not claim layer or seed coverage")
        evidence = row.get("evidence_refs")
        require(isinstance(evidence, list) and bool(evidence), "disposition requires recorded evidence")
        for ref in evidence:
            _resolve(root, ref, documents)
        verdict_refs = row.get("verdict_refs")
        require(isinstance(verdict_refs, list), "verdict_refs must be an array")
        require(star.get("evidence_refs") == evidence and star.get("verdict_refs") == verdict_refs
                and star.get("verdict_follow_up") == row.get("verdict_follow_up"),
                "snapshot evidence or verdict claims disagree with convergence manifest")
        tiers = set()
        for ref in verdict_refs:
            verdict = _resolve(root, ref, documents)
            require(isinstance(verdict, dict) and identity(verdict.get("repository", verdict.get("repo"))) == name
                    and verdict.get("tier") in TIERS, "verdict reference requires the same repository and explicit tier")
            tiers.add(verdict["tier"])
        if scope == "IN-SCOPE" and TIERS - tiers:
            follow_up = row.get("verdict_follow_up")
            require(isinstance(follow_up, dict) and follow_up.get("status") == "AWAITING-RECORDED-TIER-VERDICT"
                    and set(follow_up.get("required_tiers", [])) == TIERS - tiers
                    and follow_up.get("layer_keys") == keys and follow_up.get("registry") == REGISTRY,
                    "in-scope disposition needs honest recorded-tier follow-up")
            load(root, REGISTRY)
        counts[scope.lower().replace("-", "_")] += 1
    require(seen == set(by_repo), "convergence manifest must cover every starred repository")
    return {"status": "valid", "count": len(rows), "pending": 0, "seed_count": len(seed_doc["seeds"]), **counts}
