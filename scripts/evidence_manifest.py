#!/usr/bin/env python3
"""Normalize the legacy registry; preview an explicit per-path record proposal.

Keeping files[] sorted by path makes independent additions in parallel PRs
land as conflict-friendly inserts instead of always colliding on the same
tail of the array. This never changes any entry's fields, and never
reorders the manifest's other top-level keys (schema_version, receipts,
files, convergence_records keep their existing order); only the files[]
list itself is reordered.

  python3 scripts/evidence_manifest.py --check   # exit 1 if files[] is out of order
  python3 scripts/evidence_manifest.py --write   # rewrite files[] in sorted order

The root registry remains legacy. Only a fixture/source explicitly marked
file_records=manifests/evidence-files opts into the reference representation.
--render emits its generated view without writing an aggregate or refreshing
expected hashes. Production reader migration is a separate reviewed change.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess

try:
    from .catalog_decisions import safe_file, unique_json
except ImportError:
    from catalog_decisions import safe_file, unique_json


EVIDENCE = "manifests/evidence.json"
RECORDS = "manifests/evidence-files"


def _object(raw: bytes | str) -> dict:
    value = json.loads(raw, object_pairs_hook=unique_json)
    if not isinstance(value, dict):
        raise ValueError("evidence registry input must be an object")
    return value


def uses_records(document: dict) -> bool:
    """An explicit format marker keeps historical/fixture registries readable."""
    marker = document.get("file_records")
    if "file_records" in document and marker != RECORDS:
        raise ValueError("unsupported evidence file_records source")
    return marker == RECORDS


def record_path(path: str) -> str:
    # Reuse the publication's canonical-path rules without reading artifact bytes.
    # The deterministic name makes competing edits to one record meet in Git.
    if (not isinstance(path, str) or not path or str(PurePosixPath(path)) != path
            or PurePosixPath(path).is_absolute()
            or any(part in {".", "..", ".git"} for part in PurePosixPath(path).parts)
            or any(ord(char) < 32 or char in "\\:?#" for char in path)
            or path == EVIDENCE or path.startswith(RECORDS + "/")):
        raise ValueError("invalid or recursive evidence record path")
    # Git 2.53.0 gitrepository-layout.adoc:55-61: fixed-depth digest fanout.
    # Hash the path identity, never the artifact or its expected integrity fields.
    identity = hashlib.sha256(path.encode("utf-8")).hexdigest()
    return f"{RECORDS}/{identity[:2]}/{identity[2:]}.json"


def record_sources(root: Path) -> list[str]:
    directory = safe_file(root, RECORDS)
    if not directory.exists():
        return []
    if not directory.is_dir():
        raise ValueError(f"{RECORDS}: evidence file_records source is not a directory")
    result = []
    for path in directory.rglob("*"):
        relative = path.relative_to(root).as_posix()
        safe_file(root, relative)  # includes directory symlinks, which rglob does not follow
        if path.is_file():
            if path.suffix != ".json":
                raise ValueError(f"{relative}: unexpected non-JSON evidence record")
            result.append(relative)
    return sorted(result)


def validate_record(row: dict) -> str:
    if not isinstance(row, dict):
        raise ValueError("evidence record must be an object")
    path = row.get("path")
    record_path(path)
    if (not isinstance(row.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", row["sha256"])
            or type(row.get("bytes")) is not int or row["bytes"] < 0):
        raise ValueError("invalid evidence record hash or byte count")
    return path


def assemble(seed: dict, sources, read, *, historical: bool = False) -> dict:
    """Project complete authored records; never hash or repair evidence here.

    Separate authored fragments follow Towncrier@f92fbf51 README.rst:18 and
    Changesets@a897bb8a packages/write/src/index.ts:27. The frozen files[] seed
    avoids rewriting twelve thousand records during migration.
    """
    try:
        if not uses_records(seed):
            return seed
        files = seed.get("files")
        if not isinstance(files, list):
            raise ValueError("evidence seed files must be an array")
    except ValueError as error:
        raise ValueError(f"{EVIDENCE}: {error}") from error
    records = {}
    ambiguous = set()
    for row in files:
        try:
            path = validate_record(row)
        except ValueError as error:
            if historical:
                continue
            raise ValueError(f"{EVIDENCE}: {error}") from error
        if path in records:
            if not historical:
                raise ValueError(f"{EVIDENCE}: duplicate evidence seed path")
            ambiguous.add(path)
        records[path] = row
    for path in ambiguous:
        records.pop(path)
    seen = set()
    for source in sorted(sources):
        try:
            document = _object(read(source))
            if document.get("schema_version") != 1 or type(document.get("schema_version")) is not int:
                raise ValueError("unsupported evidence record schema")
            if set(document) == {"schema_version", "remove"}:
                path = document["remove"]
                row = None
            else:
                row = document.get("record")
                if not isinstance(row, dict) or set(document) != {"schema_version", "record"}:
                    raise ValueError("evidence fragment must contain one complete record")
                path = validate_record(row)
            if record_path(path) != source or path in seen:
                raise ValueError("misnamed or duplicate evidence record")
        except (OSError, ValueError) as error:
            if historical:
                continue
            raise ValueError(f"{source}: {error}") from error
        seen.add(path)
        if row is None:
            records.pop(path, None)
        else:
            records[path] = row
    return {**seed, "files": [records[path] for path in sorted(records)]}


def load(root: Path, *, read=None) -> dict:
    """Read the generated legacy-shaped view, optionally through a bounded reader."""
    root = Path(root).resolve()
    if read is None:
        read = lambda path: safe_file(root, path).read_bytes()
    try:
        seed = _object(read(EVIDENCE))
    except (OSError, ValueError) as error:
        raise ValueError(f"{EVIDENCE}: {error}") from error
    return assemble(seed, record_sources(root) if uses_records(seed) else [], read)


def load_at(root: Path, revision: str, *, git=None, historical: bool = False) -> dict:
    """Read one Git tree; historical intent retains independently valid records.

    Default/current reads remain strict. Historical filtering follows the legacy
    validate_registration_rows row filter at bf665ec6, applied per source record.
    """
    if git is None:
        environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}

        def git(*args):
            return subprocess.run(["git", "--no-optional-locks", "-C", str(root), *args],
                                  env=environment, capture_output=True, check=True, timeout=30).stdout
    seed = _object(git("show", revision + ":" + EVIDENCE))
    sources = []
    if uses_records(seed):
        listing = git("ls-tree", "-r", "-z", revision, "--", RECORDS)
        if listing and not listing.endswith(b"\0"):
            raise ValueError("unterminated evidence record listing")
        for entry in listing.split(b"\0"):
            if not entry:
                continue
            metadata, path = entry.split(b"\t", 1)
            mode, kind, _oid = metadata.split()
            if mode not in (b"100644", b"100755") or kind != b"blob":
                if historical:
                    continue
                raise ValueError("evidence record must be a regular Git blob")
            sources.append(path.decode("utf-8"))
    return assemble(seed, sources, lambda path: git("show", revision + ":" + path), historical=historical)


def write_record(root: Path, record: dict) -> None:
    """Register exactly the supplied expected metadata in its own Git path."""
    if not uses_records(_object(safe_file(root, EVIDENCE).read_bytes())):
        raise ValueError("evidence file_records format is not enabled")
    target = safe_file(root, record_path(validate_record(record)))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({"schema_version": 1, "record": record}, indent=2) + "\n", encoding="utf-8")


def remove_record(root: Path, path: str) -> None:
    """An explicit tombstone preserves the seed and competes at the same Git path."""
    if not uses_records(_object(safe_file(root, EVIDENCE).read_bytes())):
        raise ValueError("evidence file_records format is not enabled")
    target = safe_file(root, record_path(path))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({"schema_version": 1, "remove": path}, indent=2) + "\n", encoding="utf-8")


def sorted_paths(files: list) -> list[str]:
    return [entry.get("path", "") if isinstance(entry, dict) else "" for entry in files]


def is_sorted(files: list) -> bool:
    paths = sorted_paths(files)
    return paths == sorted(paths) and len(set(paths)) == len(paths)


def normalize(evidence: dict) -> dict:
    """Return a copy of evidence with files[] sorted by path; every other
    top-level key and every entry's own fields are left exactly as they are."""
    files = evidence.get("files", [])
    ordered = sorted(files, key=lambda entry: entry.get("path", "") if isinstance(entry, dict) else "")
    return {**evidence, "files": ordered}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true", help="Rewrite files[] in sorted order")
    mode.add_argument("--check", action="store_true", help="Check files[] is already sorted (default)")
    mode.add_argument("--render", action="store_true", help="Print the generated registry; never update expected hashes")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    path = safe_file(root, EVIDENCE)
    try:
        evidence = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_json)
    except (OSError, UnicodeError, ValueError) as error:
        print(f"{EVIDENCE}: invalid JSON ({error})")
        return 1
    try:
        projected = load(root)
    except (OSError, UnicodeError, ValueError) as error:
        print(f"invalid evidence registry ({error})")
        return 1
    files = evidence.get("files")
    if not isinstance(files, list):
        print(f"{EVIDENCE}: files must be an array")
        return 1
    if args.render:
        print(json.dumps(projected, indent=2, ensure_ascii=True))
        return 0
    if args.write:
        path.write_text(json.dumps(normalize(evidence), indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
        print(json.dumps({"status": "written", "files": len(files)}, sort_keys=True))
        return 0
    if not is_sorted(files):
        print(f"{EVIDENCE}: files[] is not sorted by path (or has duplicate paths); "
              "run `python3 scripts/evidence_manifest.py --write` to sort it")
        return 1
    print(json.dumps({"status": "passed", "files": len(files)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
