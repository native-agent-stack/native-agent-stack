#!/usr/bin/env python3
"""Resolve exact release tags and fill separate run-source fields, without upgrades.

Git v2.53.0 Documentation/git-ls-remote.adoc OUTPUT defines annotated tag
objects and peeled ^{} refs. This module reuses the retained F1 resolver;
offline proof validation never calls Git, installs a package or selects a winner.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import tomllib

try:
    from . import host_receipts
    from .catalog_decisions import pointer, safe_file
except ImportError:
    import host_receipts
    from catalog_decisions import pointer, safe_file

ROOT = Path(__file__).resolve().parents[1]
OID = re.compile(r"[0-9a-f]{40}")
EXCLUSIONS = {"claude-code": "Owned by the separate version-changing Claude Code slot work."}


def targets(document: dict) -> list[dict]:
    winners = {winner.get("run") for layer in document["layers"] for winner in layer["winners"]}
    return [run for run in document["runs"] if run["id"] in winners
            and run.get("pin_parsed", {}).get("version")
            and not run["pin_parsed"].get("commit")]


def tag_names(component: str, version: str) -> list[str]:
    """Known exact spellings are queries, never inferred commits or upgrades."""
    extra = {
        "codex": [f"rust-v{version}"],
        "postgresql": ["REL_" + version.replace(".", "_")],
        "poppler": [f"poppler-{version}"],
        "systemd": [f"import/{version}"],
        "ccusage": [f"ccusage@{version}", f"@ccusage/ccusage@{version}"],
        "mcp-inspector": [f"@modelcontextprotocol/inspector@{version}"],
    }
    return extra.get(component, []) + [f"v{version}", version]


def parse_remote(stdout: str, tags: list[str]) -> dict:
    """Retained F1 parser: refuse absent, contradictory or ambiguous refs."""
    allowed = {"refs/tags/" + tag + suffix for tag in tags for suffix in ("", "^{}")}
    refs = {}
    for line in stdout.splitlines():
        fields = line.split()
        if len(fields) != 2 or not OID.fullmatch(fields[0]) or fields[1] not in allowed:
            return {"status": "gap", "reason": "malformed_or_unexpected_ref"}
        oid, ref = fields
        if ref in refs and refs[ref] != oid:
            return {"status": "gap", "reason": "contradictory_ref"}
        refs[ref] = oid
    matches = [tag for tag in tags if "refs/tags/" + tag in refs]
    if any(ref.endswith("^{}") and ref[:-3] not in refs for ref in refs):
        return {"status": "gap", "reason": "peeled_ref_without_tag"}
    if len(matches) != 1:
        return {"status": "gap", "reason": "tag_missing" if not matches else "ambiguous_tags"}
    tag = matches[0]
    ref = "refs/tags/" + tag
    annotated = ref + "^{}" in refs
    return {"status": "resolved", "tag": tag, "tag_ref": ref,
            "tag_object": refs[ref] if annotated else None, "ref_object": refs[ref],
            "tag_kind": "annotated" if annotated else "lightweight",
            "peeled_commit": refs.get(ref + "^{}", refs[ref])}


def verified_commit(proof, component: str, version: str, repository: str) -> str | None:
    """Reproduce a retained exact-version Git observation; never trust its OID alone."""
    if (not all(isinstance(value, str) and value for value in (component, version, repository))
            or not isinstance(proof, dict) or proof.get("component") != component
            or proof.get("version") != version or type(proof.get("exit_code")) is not int or proof["exit_code"] != 0
            or proof.get("status", "resolved") != "resolved"
            or host_receipts.normalize_repository(proof.get("repository")) != repository):
        return None
    command = proof.get("command")
    if (not isinstance(command, list) or not 5 <= len(command) <= 35
            or not all(isinstance(arg, str) for arg in command) or command[:2] != ["git", "ls-remote"]
            or command[2].lower() not in {"https://" + repository, "https://" + repository + ".git"}):
        return None
    allowed_tags = tag_names(component, version)
    tags = [ref[len("refs/tags/"):] for ref in command[3::2] if ref.startswith("refs/tags/")]
    expected = ["refs/tags/" + tag + suffix for tag in tags for suffix in ("", "^{}")]
    if (not tags or len(set(tags)) != len(tags) or any(tag not in allowed_tags for tag in tags)
            or command[3:] != expected):
        return None
    stdout = proof.get("stdout")
    if not isinstance(stdout, str) or len(stdout) > 65536:
        return None
    parsed = parse_remote(stdout, tags)
    if parsed["status"] != "resolved" or proof.get("peeled_commit") != parsed["peeled_commit"]:
        return None
    if "tag_object" not in proof or proof["tag_object"] != parsed["tag_object"]:
        return None
    if any(proof[key] != parsed[key] for key in ("tag", "tag_ref", "ref_object", "tag_kind") if key in proof):
        return None
    return parsed["peeled_commit"]


def resolve(run: dict, runner=subprocess.run) -> dict:
    row = {"component": run["id"], "version": run["pin_parsed"]["version"],
           "repository": run["repository"], "source": run["source"], "original_pin": run["pin"]}
    if run["id"] in EXCLUSIONS:
        return {**row, "status": "excluded", "reason": EXCLUSIONS[run["id"]]}
    repository = run["repository"] or ""
    if not re.fullmatch(r"github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+|git\.launchpad\.net/ubuntu/\+source/[a-z0-9+.-]+", repository):
        return {**row, "status": "gap", "reason": "repository_missing_or_unsupported"}
    names = tag_names(row["component"], row["version"])
    command = ["git", "ls-remote", "https://" + repository + (".git" if repository.startswith("github.com/") else "")]
    command.extend("refs/tags/" + tag + suffix for tag in names for suffix in ("", "^{}"))
    try:
        result = runner(command, capture_output=True, text=True, timeout=45, check=False)
    except subprocess.TimeoutExpired as error:
        def decoded(value):
            return value.decode(errors="replace") if isinstance(value, bytes) else value or ""
        return {**row, "command": command, "status": "gap", "reason": "lookup_timeout",
                "exit_code": None, "stdout": decoded(error.stdout), "stderr": decoded(error.stderr)}
    observed = {**row, "command": command, "exit_code": result.returncode,
                "stdout": result.stdout, "stderr": result.stderr}
    if result.returncode:
        return {**observed, "status": "gap", "reason": "lookup_failed"}
    return {**observed, **parse_remote(result.stdout, names)}


def render_table(rows: list[dict]) -> str:
    lines = ["| component | version | tag | tag object | peeled commit |",
             "| --- | --- | --- | --- | --- |"]
    for row in rows:
        lines.append("| " + " | ".join(str(value) for value in (
            row["component"], row["version"], row.get("tag", row.get("reason", "gap")),
            row.get("tag_object") or ("lightweight" if row.get("status") == "resolved" else "gap"),
            row.get("peeled_commit", "gap"))) + " |")
    return "\n".join(lines) + "\n"


def apply_report(root: Path, relative: str) -> dict:
    """Plan all fills before writing; preserve versions, artifacts and existing bindings."""
    try:
        from . import final_stack
    except ImportError:
        import final_stack
    if not isinstance(relative, str) or not relative.startswith("evidence/artifacts/") or not relative.endswith(".json"):
        raise ValueError("resolution report must be a repository artifact JSON")
    report_path = safe_file(root, relative)
    report = json.loads(report_path.read_text())
    if not isinstance(report, dict) or not isinstance(report.get("rows"), list):
        raise ValueError("resolution report must contain rows")
    sources = final_stack.Sources(root)
    current = {run["id"]: run for run in final_stack.build_runs(final_stack.run_records(sources))}
    documents, updates = {}, []
    supplement_path = safe_file(root, final_stack.LOCKFILE_SOURCES)
    supplement = (json.loads(supplement_path.read_text()) if supplement_path.exists() else
                  {"schema_version": 1, "lockfile": final_stack.LOCKFILE, "bindings": []})
    bindings = {entry["source"]: entry for entry in supplement["bindings"]}
    for index, row in enumerate(report["rows"]):
        if row.get("status") != "resolved":
            continue
        if row.get("component") in EXCLUSIONS:
            raise ValueError("component is separately owned; source fill refused")
        run = current.get(row["component"])
        commit = verified_commit(row, row["component"], row["version"], row["repository"])
        if (not run or not commit or run["repository"] != row["repository"] or run["source"] != row["source"]
                or run.get("pin_parsed", {}).get("version") != row["version"]):
            raise ValueError("resolution no longer matches the run identity or exact tag proof")
        path, _, selector = row["source"].partition("#")
        if path not in {final_stack.LOCKFILE, final_stack.STACK, *(p for _, p in final_stack.PIN_FILES)}:
            raise ValueError("source path is not an allowlisted run-pin input")
        if path not in documents:
            raw = safe_file(root, path).read_text()
            documents[path] = tomllib.loads(raw) if path == final_stack.LOCKFILE else json.loads(raw)
        entry = pointer(documents[path], selector)
        if entry.get("version") != row["version"]:
            raise ValueError("source version changed; refuse an implicit upgrade")
        if path == final_stack.LOCKFILE:
            artifacts = sorted({a["hash"] for a in [entry.get("sdist", {}), *entry.get("wheels", [])] if a.get("hash")})
            if (not artifacts or artifacts != row.get("artifact_sha256")
                    or any(not re.fullmatch(r"sha256:[0-9a-f]{64}", value) for value in artifacts)):
                raise ValueError("lock artifact identity changed or is incomplete")
            old = bindings.get(row["source"])
            if old and old.get("commit") != commit:
                raise ValueError("an existing source commit disagrees; adjudication required")
            bindings[row["source"]] = {"source": row["source"], "package": entry["name"], "version": row["version"],
                                       "artifact_sha256": artifacts, "repository": row["repository"], "commit": commit,
                                       "source_proof": relative + "#/rows/" + str(index)}
        else:
            field = "source_pin" if path == final_stack.STACK else "commit"
            previous = entry.get(field)
            if isinstance(previous, str) and OID.fullmatch(previous) and previous != commit:
                raise ValueError("an existing source commit disagrees; adjudication required")
            entry[field] = commit
            updates.append({"source": row["source"], "field": field, "previous": previous, "commit": commit})
    for path, document in documents.items():
        if path != final_stack.LOCKFILE:
            safe_file(root, path).write_text(json.dumps(document, indent=2) + "\n")
    if list(bindings.values()) != supplement["bindings"]:
        supplement["bindings"] = list(bindings.values())
        supplement_path.write_text(json.dumps(supplement, indent=2) + "\n")
    return {"source_updates": updates, "lockfile_bindings": len(bindings), "versions_changed": []}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=ROOT)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--resolve", metavar="REPORT", help="Retain exact Git observations in an artifact JSON.")
    mode.add_argument("--apply", metavar="REPORT", help="Offline fills only; regenerate/register separately.")
    args = parser.parse_args(argv)
    if args.apply:
        print(json.dumps(apply_report(args.root, args.apply), indent=2))
        return 0
    if not args.resolve.startswith("evidence/artifacts/") or not args.resolve.endswith(".json"):
        raise ValueError("resolution report must be a repository artifact JSON")
    output = safe_file(args.root, args.resolve)
    table = safe_file(args.root, str(Path(args.resolve).with_suffix(".tags.md")))
    try:
        from . import final_stack
    except ImportError:
        import final_stack
    inventory = json.loads(safe_file(args.root, final_stack.OUTPUT).read_text())
    rows = []
    for run in targets(inventory):
        row = resolve(run)
        path, _, selector = run["source"].partition("#")
        if path == final_stack.LOCKFILE:
            entry = pointer(tomllib.loads(safe_file(args.root, path).read_text()), selector)
            row["artifact_sha256"] = sorted({a["hash"] for a in [entry.get("sdist", {}), *entry.get("wheels", [])] if a.get("hash")})
        rows.append(row)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"schema_version": 1, "kind": "run_pin_tag_resolution",
                                 "recorded_at": datetime.now(timezone.utc).isoformat(), "rows": rows}, indent=2) + "\n")
    table.write_text(render_table(rows))
    print(json.dumps({"resolved": sum(row["status"] == "resolved" for row in rows),
                      "gaps": sum(row["status"] == "gap" for row in rows)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
