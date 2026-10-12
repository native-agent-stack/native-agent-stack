#!/usr/bin/env python3
"""Reproduce the starred protected set from named Git trees and a public mirror projection.

Git's ls-tree/show interfaces supply immutable tracked bytes. Slug matching is
bounded by the canonical starred list; dependency-name matches deliberately
overprotect rather than infer that a package with a different name is absent.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

try:
    from .catalog_decisions import identity, load, safe_file
except ImportError:
    from catalog_decisions import identity, load, safe_file

MANIFEST = "catalogs/convergence-practice/starred-convergence-20261010.json"
CAPTURE = "catalogs/convergence-practice/sources/starred-protected-20261011.json"
SCOPE = (
    "Conservative union over the recorded starred list: registered mirror entries, "
    "URL and bare owner/repo citations in both repositories' Markdown decision records "
    "and their JSON attachments, "
    "workflow uses pins, and direct GitHub or conservative repository-basename "
    "matches in both repositories' dependency manifests and lockfiles. "
    "Different package/repository names and historical inputs outside these named "
    "trees remain unresolved; this is not proof of absence of protection. "
    "No removal is proposed or authorized by this capture."
)
RULE = (
    "Never unstar registered mirrors, pinned dependencies in either repository, "
    "or repositories cited by decision records. The reproducible capture includes "
    "bare slugs, URL citations, workflow pins and dependency manifests/locks at "
    "named heads. Package/repository aliases and missing historical inputs remain "
    "bounded; an unprotected flag is not permission to remove. No removals proposed."
)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def package_name(name):
    """PEP 503 normalization, also conservative for npm basename candidates."""
    return re.sub(r"[-_.]+", "-", name).lower()


def source_kind(path):
    parts = Path(path).parts
    name = Path(path).name
    if "decisions" in parts and path.endswith((".md", ".json")):
        return "decision_record"
    if path.startswith(".github/workflows/") and path.endswith((".yml", ".yaml")):
        return "workflow_pin"
    if (name in {"pyproject.toml", "uv.lock", "poetry.lock", "Pipfile", "Pipfile.lock",
                 "package.json", "package-lock.json", "pnpm-lock.yaml", "yarn.lock",
                 "Cargo.toml", "Cargo.lock", "go.mod", "go.sum"}
            or name.startswith("requirements") and name.endswith((".txt", ".in", ".lock"))
            or path in {"manifests/stack.json", "catalogs/us-equities/runtime-target.json"}):
        return "dependency_or_runtime_manifest"
    return None


def witnesses(text, kind, names):
    """Yield only normalized known slugs, or conservative dependency-name candidates."""
    slugs = re.compile(r"(?<![A-Za-z0-9_.-])(" + "|".join(re.escape(name) for name in sorted(names))
                       + r")(?![A-Za-z0-9_-]|\.[A-Za-z0-9])", re.IGNORECASE)
    actions = re.compile(r"\buses:\s*['\"]?([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)(?:/[^\s@]+)?@[^\s'\"#]+")
    packages = {}
    for name in sorted(names):
        packages.setdefault(package_name(name.split("/")[1]), []).append(name)
    for line, value in enumerate(text.splitlines(), 1):
        matched = {}
        pattern = actions if kind == "workflow_pin" else slugs
        for match in pattern.finditer(value):
            name = match[1].lower().removesuffix(".git")
            if name in names:
                matched[name] = "uses_pin" if kind == "workflow_pin" else "repository_citation"
        if kind == "dependency_or_runtime_manifest":
            for token in re.findall(r"[A-Za-z0-9]+(?:[-_.][A-Za-z0-9]+)*", value):
                for name in packages.get(package_name(token), []):
                    matched.setdefault(name, "conservative_package_basename")
        for name, match in sorted(matched.items()):
            yield name, {"kind": kind, "line": line, "match": match}


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout


def capture(names, trees, mirror_inventory, mirrors_sha256):
    repositories = {}
    for index, entry in enumerate(mirror_inventory):
        name = identity(entry["repository"])
        if name in names:
            repositories.setdefault(name, []).append({
                "kind": "upstream_mirror", "source": f"mirror_inventory/{index}",
                "ref": entry["ref"], "inventory_sha256": mirrors_sha256})
    inventories = []
    for label, repo, head in trees:
        resolved = git(repo, "rev-parse", "--verify", head + "^{commit}").decode().strip()
        if resolved != head or not re.fullmatch(r"[0-9a-f]{40}", head):
            raise ValueError("capture requires a full immutable commit ID")
        paths = git(repo, "ls-tree", "-r", "--name-only", "-z", head).decode().split("\0")
        sources = []
        for path in sorted(filter(None, paths)):
            kind = source_kind(path)
            if kind is None:
                continue
            data = git(repo, "show", f"{head}:{path}")
            sha = digest(data)
            sources.append({"path": path, "sha256": sha})
            seen = set()
            for name, witness in witnesses(data.decode("utf-8"), kind, names):
                if name in seen:
                    continue
                seen.add(name)
                repositories.setdefault(name, []).append({**witness,
                    "source": f"{label}:{path}", "head": head, "sha256": sha})
        inventories.append({"repository": label, "head": head,
                            "source_count": len(sources), "sources": sources})
    return {"schema_version": 1, "producer": "scripts/starred_protected.py",
            "scope": SCOPE, "inventories": inventories,
            "mirrors_sha256": mirrors_sha256, "mirror_inventory": mirror_inventory,
            "repositories": dict(sorted(repositories.items()))}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--uet-root", type=Path, required=True)
    parser.add_argument("--nas-head")
    parser.add_argument("--uet-head")
    parser.add_argument("--mirrors", type=Path,
                        help="Public MIRRORS.json; omitted when replaying the embedded projection")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    manifest = load(root, MANIFEST)
    previous = load(root, CAPTURE)
    heads = {row["repository"]: row["head"] for row in previous["inventories"]}
    if args.mirrors:
        data = args.mirrors.read_bytes()
        mirrors_sha256 = digest(data)
        # Project only public repository identities and pins; no host paths or prose.
        mirror_inventory = sorted(({
            "repository": identity(entry["repo"]), "ref": entry["ref"]}
            for entry in json.loads(data)["mirrors"]),
            key=lambda entry: (entry["repository"], entry["ref"]))
    else:
        mirror_inventory = previous["mirror_inventory"]
        mirrors_sha256 = previous["mirrors_sha256"]
    names = {identity(row["repository"]) for row in manifest["repositories"]}
    result = capture(names, [
        ("native-agent-stack", root, args.nas_head or heads["native-agent-stack"]),
        ("us-equities-trading", args.uet_root, args.uet_head or heads["us-equities-trading"])],
        mirror_inventory, mirrors_sha256)
    if args.write:
        safe_file(root, CAPTURE).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        manifest["finalization"]["protected_rule"] = RULE
        for row in manifest["repositories"]:
            refs = result["repositories"].get(identity(row["repository"]), [])
            row.update(protected=bool(refs), protection_refs=refs)
            if refs and row["decision"] == "KEEP":
                row["decision_reason"] = (
                    "Retain the protected repository recorded by a mirror, decision citation, "
                    "workflow pin or dependency/runtime manifest; no removal is authorized.")
        safe_file(root, MANIFEST).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    elif result != previous:
        raise ValueError("protected capture differs from its named inputs; regenerate with --write")
    print(json.dumps({"status": "written" if args.write else "passed",
                      "protected": len(result["repositories"]),
                      "heads": {row["repository"]: row["head"] for row in result["inventories"]}}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
