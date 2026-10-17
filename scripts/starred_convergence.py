"""Check recorded starred-repository intake joins without promoting discovery to acceptance."""

from __future__ import annotations

from collections import Counter
from calendar import monthrange
from datetime import datetime, timezone
import hashlib
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
CATEGORIES = {"research-skills", "sentiment-nlp", "north-star-runtime", "engines", "strategies",
              "market-data", "claude-practice", "codex-practice", "mcp-tools", "memory-rag",
              "observability", "infra-ci", "awesome-lists"}


def _public_fields(value):
    if isinstance(value, dict):
        require(not PRIVATE_FIELDS.intersection(str(key).lower() for key in value),
                "starred convergence contains account or private fields")
        for child in value.values():
            _public_fields(child)
    elif isinstance(value, list):
        for child in value:
            _public_fields(child)


def _resolve(root, ref, documents, read=None):
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
        documents[path] = read(path) if read is not None else load(root, path)
        _public_fields(documents[path])
    return pointer(documents[path], fragment)


def _validate_finalization(root, manifest, read):
    """Enforce WS1's recorded classification and removal conditions in the existing validator."""
    config = manifest.get("finalization")
    if config is None:
        return
    require(isinstance(config, dict) and config.get("schema_version") == 1,
            "unsupported starred finalization schema")
    documents = {}
    protected = _resolve(root, config["protected_source"] + "#/repositories", documents, read)
    require(isinstance(protected, dict), "finalized protected set must be recorded")
    rows = {identity(row["repository"]): row for row in manifest["repositories"]}
    for name, row in rows.items():
        require(row.get("category") in CATEGORIES, "unsupported finalized category")
        require(row.get("decision") in {"KEEP-MIRROR", "KEEP", "UNSTAR"}
                and isinstance(row.get("decision_reason"), str) and bool(row["decision_reason"].strip()),
                "finalized decision requires a supported action and reason")
        signals = row.get("signals")
        require(isinstance(signals, dict), "finalized signals are required")
        require(signals.get("source_ref", "").partition("#")[0] == config["signals_source"],
                "finalized signals must use the declared public capture")
        captured = _resolve(root, signals["source_ref"], documents, read)
        require(isinstance(captured, dict) and identity(captured.get("repository")) == name,
                "finalized signal reference repository disagrees")
        fields = ("archived", "pushed_at", "latest_release", "stars", "open_issues", "dependents",
                  "observed_at", "cutoff_18_months", "release_in_18_month_window", "release_history_complete")
        require(all(field in signals and signals[field] == captured.get(field) for field in fields),
                "finalized signals disagree with public capture")
        require(type(signals["archived"]) is bool and type(signals["release_history_complete"]) is bool
                and all(type(signals[field]) is int and signals[field] >= 0 for field in ("stars", "open_issues"))
                and (signals["dependents"] is None or type(signals["dependents"]) is int and signals["dependents"] >= 0)
                and (signals["release_in_18_month_window"] is None
                     or type(signals["release_in_18_month_window"]) is bool), "malformed finalized signals")
        observed = datetime.fromisoformat(signals["observed_at"].replace("Z", "+00:00"))
        require(observed.tzinfo is not None and observed.utcoffset() == timezone.utc.utcoffset(None),
                "finalized observation must be UTC")
        year, month = divmod(observed.year * 12 + observed.month - 1 - 18, 12)
        cutoff = observed.replace(year=year, month=month + 1,
                                  day=min(observed.day, monthrange(year, month + 1)[1]))
        require(datetime.fromisoformat(signals["cutoff_18_months"].replace("Z", "+00:00")) == cutoff,
                "finalized 18-month cutoff disagrees with observation")
        require(type(row.get("protected")) is bool and row["protected"] == (name in protected),
                "finalized protected flag disagrees with recorded protected set")
        for ref in row.get("finalization_evidence_refs", []):
            _resolve(root, ref, documents, read)
        if row["decision"] == "KEEP-MIRROR":
            pin = row.get("mirror_pin_source_ref")
            if pin is not None:
                source = _resolve(root, pin, documents, read)
                require(isinstance(source, dict) and identity(source.get("repository")) == name
                        and source.get("resolved") is True and source.get("ref") == row.get("mirror_ref")
                        and source.get("commit") == row.get("mirror_commit"),
                        "finalized mirror pin disagrees with source")
            else:
                require(any(ref.get("kind") == "upstream_mirror" and ref.get("ref") == row.get("mirror_ref")
                            for ref in protected.get(name, [])), "finalized mirror pin needs recorded source")
        if row["decision"] != "UNSTAR":
            continue
        require(name not in protected, "cannot UNSTAR a protected repository")
        basis = row.get("unstar_basis")
        require(basis in {"archived", "inactive_18_months", "superseded"}, "unsupported UNSTAR basis; licence is never a basis")
        if basis == "archived":
            require(signals["archived"], "UNSTAR archive basis requires archived evidence")
        elif basis == "inactive_18_months":
            pushed = datetime.fromisoformat(signals["pushed_at"].replace("Z", "+00:00"))
            require(pushed < cutoff and signals["release_in_18_month_window"] is False
                    and signals["release_history_complete"], "UNSTAR requires complete 18-month inactivity evidence")
        else:
            target = rows.get(identity(row.get("superseded_by")))
            require(target is not None and target is not row and target["category"] == row["category"]
                    and target["decision"] in {"KEEP", "KEEP-MIRROR"},
                    "supersession requires a named KEEP row in the same category")
            evidence = row.get("supersession_evidence_refs")
            require(isinstance(evidence, list) and bool(evidence), "supersession requires recorded evidence")
            for ref in evidence:
                _resolve(root, ref, documents, read)


def validate_convergence(root: Path, snapshot: dict, *, read=None) -> dict:
    """Validate a completed intake manifest, retaining compatibility with older snapshots."""
    if "convergence_manifest" not in snapshot:
        require(snapshot.get("kind") != "public_starred",
                "canonical public-star snapshot requires convergence_manifest")
        return {"status": "legacy", "count": len(snapshot.get("repositories", []))}
    manifest_path = snapshot["convergence_manifest"]
    load_document = read if read is not None else lambda path: load(root, path)
    manifest = load_document(manifest_path)
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
    layer_doc = load_document("catalogs/foundation/manifest.json")
    layers = {row["id"] for row in layer_doc["layers"]} | _us_equities_layers(root, load_document)
    skills = "catalogs/landscape/skills-lifecycle.json"
    if safe_file(root, skills).exists():
        layers.update(row["layer_id"] for row in load_document(skills)["tasks"])
    seeds_path = manifest.get("seed_manifest")
    seed_doc = load_document(seeds_path)
    require(seed_doc.get("schema_version") == 1 and isinstance(seed_doc.get("seeds"), list),
            "unsupported starred seed schema")
    documents = {manifest_path: manifest, seeds_path: seed_doc}
    for document in (manifest, snapshot, seed_doc):
        _public_fields(document)
    capture_hashes = {}
    for seed in seed_doc["seeds"]:
        identity(seed.get("repository"))
        require(seed.get("layer") in layers, "seed has unsupported canonical layer")
        require(isinstance(seed.get("reason"), str) and bool(seed["reason"].strip()),
                "seed requires a recorded reason")
        refs = seed.get("source_refs")
        require(isinstance(refs, list) and bool(refs), "seed requires source references")
        for ref in refs:
            resolved = _resolve(root, ref, documents, read)
            if isinstance(resolved, dict) and "repository" in resolved:
                require(identity(resolved["repository"]) == identity(seed["repository"]),
                        "seed reference repository disagrees with source evidence")
        if seed.get("evidence_class") == "source_review":
            require(any("://" in ref for ref in refs),
                    "source_review requires pinned upstream source bytes")
            for ref in refs:
                if "://" in ref:
                    repository = "/".join(urlsplit(ref).path.strip("/").split("/")[:2])
                    require(identity(repository) == identity(seed["repository"]),
                            "source URL repository disagrees with source_review seed")
        witness = seed.get("recorded_seed")
        if witness is not None:
            require(isinstance(witness, dict), "recorded seed witness must be an object")
            require(seed.get("evidence_class") == "metadata_seed_review",
                    "historical seed witness is metadata_seed_review, not pinned source_review")
            ref = witness.get("source_ref")
            require(ref in refs, "recorded seed requires a resolvable source reference")
            source = _resolve(root, ref, documents, read)
            require(isinstance(source, str) and hashlib.sha256(source.encode()).hexdigest()
                    == witness.get("source_seed_sha256"), "recorded seed source hash disagrees")
            capture = ref.partition("#")[0]
            if capture not in capture_hashes:
                capture_hashes[capture] = hashlib.sha256(safe_file(root, capture).read_bytes()).hexdigest()
            require(capture_hashes[capture] == witness.get("master_sha256"),
                    "recorded master seed capture hash disagrees")
            require(identity(source.split(";", 1)[0].split("@", 1)[0]) == identity(seed["repository"])
                    and ref.partition("#")[2] == "/" + str(witness.get("layer")).replace("~", "~0").replace("/", "~1")
                    + "/" + str(witness.get("index")), "recorded seed source identity or locator disagrees")
        try:
            checked_at = datetime.fromisoformat(seed["checked_at"].replace("Z", "+00:00"))
        except (KeyError, TypeError, ValueError, AttributeError):
            require(False, "seed checked_at must be a UTC timestamp")
        require(checked_at.tzinfo is not None and checked_at.utcoffset() == timezone.utc.utcoffset(None),
                "seed checked_at must be a UTC timestamp")
    seen, counts = set(), Counter({scope.lower().replace("-", "_"): 0 for scope in SCOPES})
    referenced_seeds = set()
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
            seed = _resolve(root, ref, documents, read)
            referenced_seeds.add(ref)
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
            _resolve(root, ref, documents, read)
        verdict_refs = row.get("verdict_refs")
        require(isinstance(verdict_refs, list), "verdict_refs must be an array")
        require(star.get("evidence_refs") == evidence and star.get("verdict_refs") == verdict_refs
                and star.get("verdict_follow_up") == row.get("verdict_follow_up"),
                "snapshot evidence or verdict claims disagree with convergence manifest")
        tiers = set()
        for ref in verdict_refs:
            verdict = _resolve(root, ref, documents, read)
            require(isinstance(verdict, dict) and identity(verdict.get("repository", verdict.get("repo"))) == name
                    and verdict.get("tier") in TIERS, "verdict reference requires the same repository and explicit tier")
            tiers.add(verdict["tier"])
        if scope == "IN-SCOPE" and TIERS - tiers:
            follow_up = row.get("verdict_follow_up")
            require(isinstance(follow_up, dict) and follow_up.get("status") == "AWAITING-RECORDED-TIER-VERDICT"
                    and set(follow_up.get("required_tiers", [])) == TIERS - tiers
                    and follow_up.get("layer_keys") == keys and follow_up.get("registry") == REGISTRY,
                    "in-scope disposition needs honest recorded-tier follow-up")
            load_document(REGISTRY)
        elif scope == "IN-SCOPE":
            require(row.get("verdict_follow_up") is None,
                    "complete tier verdicts must not retain an awaiting follow-up")
        counts[scope.lower().replace("-", "_")] += 1
    require(seen == set(by_repo), "convergence manifest must cover every starred repository")
    require(referenced_seeds == {f"{seeds_path}#/seeds/{index}" for index in range(len(seed_doc["seeds"]))},
            "every seed row must be referenced by a disposition")
    _validate_finalization(root, manifest, read)
    return {"status": "valid", "count": len(rows), "pending": 0, "seed_count": len(seed_doc["seeds"]), **counts}


def _us_equities_layers(root, load_document):
    """The us-equities layer ids (catalogs/landscape/us-equities.json#/layers), read like the skills catalog: only
    when the catalog exists. Its domain_rows are the historical research layers, not canonical layer ids."""
    us_equities = "catalogs/landscape/us-equities.json"
    if not safe_file(root, us_equities).exists():
        return set()
    return {row["layer_id"] for row in load_document(us_equities)["layers"]}
