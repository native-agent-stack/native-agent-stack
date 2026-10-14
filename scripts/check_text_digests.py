"""Check text commitments against published Git-index bytes (#161).

Adapts trading-cc's check_text_digests.py reference checker. Only indexed regular
files under ROOT can supply file preimages; ignored/untracked files and symlinks
cannot justify publication. Git's documented ls-files --stage and cat-file blob
interfaces provide that boundary. Explicit audited public Git commit references
and captured vendor asset identifiers may be supplied as JSON. Findings report locations and lengths, never values or
prefixes. No private probe or host-name inventory is read.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys


HEX = re.compile(r"(?<![0-9A-Za-z])[0-9a-f]{7,64}(?![0-9A-Za-z])", re.IGNORECASE)
COMMIT = re.compile(r"[0-9a-f]{40}")


def indexed_files(root: Path) -> dict[str, bytes]:
    records = subprocess.run(
        ["git", "-C", str(root), "ls-files", "--stage", "-z", "--", "."],
        check=True, capture_output=True,
    ).stdout.split(b"\0")
    known = {}
    for record in records:
        if not record:
            continue
        metadata, name = record.split(b"\t", 1)
        mode, oid, stage = metadata.split()
        if stage != b"0":
            raise ValueError("unmerged publication index")
        if mode not in (b"100644", b"100755"):
            continue
        data = subprocess.run(
            ["git", "-C", str(root), "cat-file", "blob", oid.decode("ascii")],
            check=True, capture_output=True,
        ).stdout
        known[name.decode("utf-8", "surrogateescape")] = data
    return known


def public_references(path: Path | None, indexed: dict[str, bytes]) -> set[str]:
    if path is None:
        return set()
    doc = json.loads(path.read_text())
    if doc.get("schema_version") != 1:
        raise ValueError("unsupported public-reference schema")
    allowed = set()
    for item in doc["references"]:
        value = item["value"]
        if item["public_preimage_class"] == "git_commit":
            if not COMMIT.fullmatch(value) or not re.fullmatch(
                r"https://github\.com/[^/]+/[^/]+/(?:commit|blob)/" + value + r"(?:/[^\s]*)?",
                item["source_url"],
            ):
                raise ValueError("public source URL does not bind its Git commit identifier")
        elif item["public_preimage_class"] == "ibkr_documentation_asset_identifier":
            if not re.fullmatch(r"[0-9a-f]{64}", value) or item["source_url"] != (
                "https://www.interactivebrokers.com/docs/_fern-img/" + value + ".webp"
            ):
                raise ValueError("public vendor asset reference lacks its indexed capture")
            captured = indexed[item["public_file"]]
            if hashlib.sha256(captured).hexdigest() != item["file_sha256"] or (
                "/docs/_fern-img/" + value + ".webp"
            ).encode() not in captured:
                raise ValueError("captured public documentation does not name the asset")
        else:
            raise ValueError("unsupported public preimage class")
        allowed.add(value)
    return allowed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--allow", type=Path)
    parser.add_argument("texts", type=Path, nargs="+")
    args = parser.parse_args(argv)
    try:
        indexed = indexed_files(args.root)
        known = {hashlib.sha256(data).hexdigest() for data in indexed.values()} | public_references(args.allow, indexed)
        findings = []
        checked = 0
        for path in args.texts:
            if path.is_symlink():
                raise ValueError("text publication input must not be a symlink")
            for line_number, line in enumerate(path.read_text().splitlines(), 1):
                for match in HEX.finditer(line):
                    value = match.group().lower()
                    if not re.search(r"[a-f]", value):
                        continue
                    checked += 1
                    if not any(full == value or (len(value) < len(full) and full.startswith(value)) for full in known):
                        findings.append((path.name, line_number, match.start() + 1, len(value)))
        print(f"files {len(args.texts)}, hex runs checked {checked}, public identities {len(known)}, findings {len(findings)}")
        for name, line, column, length in findings:
            print(f"FINDING {name}:{line}:{column}: unresolved {length}-hex run")
        return 1 if findings else 0
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError):
        print("text-digest guard error: publication inputs or references unavailable", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
