#!/usr/bin/env python3
"""Publish deterministic masked derivatives of retained native captures.

Only explicit UTF-8 literals are replaced, simultaneously, longest first.
All other bytes (including ANSI, invalid UTF-8, CR/LF and absent final newline)
are preserved. The private mapping and raw digests are never published.
Uses CPython v3.13.16 Lib/re/__init__.py (bytes pattern/sub), Lib/hashlib.py
(sha256), and Lib/json/__init__.py (deterministic explicit metadata encoding).
"""
import argparse
import hashlib
import json
import re
from pathlib import Path


def masking_rule(rows):
    replacements = {}
    placeholders = set()
    for row in rows:
        literal, token = row["literal"], row["placeholder"]
        if not isinstance(literal, str) or not literal or not re.fullmatch(r"<[A-Z][A-Z0-9_]*>", token):
            raise ValueError("invalid explicit masking rule")
        if literal.encode() in replacements or token in placeholders:
            raise ValueError("duplicate masking source or placeholder")
        replacements[literal.encode()] = token.encode()
        placeholders.add(token)
    if any(token.encode() in literal for token in placeholders for literal in replacements):
        raise ValueError("masking placeholders may not occur in source literals")
    pattern = re.compile(b"|".join(re.escape(key) for key in sorted(replacements, key=lambda x: (-len(x), x)))) if replacements else None

    def mask(data):
        return pattern.sub(lambda match: replacements[match[0]], data) if pattern else data

    return mask, sorted(placeholders)


def publish(raw_dir, mapping, destination):
    mask, tokens = masking_rule(json.loads(Path(mapping).read_text()))
    root = Path(raw_dir)
    files = {}
    captures = []
    for directory in sorted(root.iterdir()):
        if not directory.is_dir() or directory.is_symlink() or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", directory.name):
            raise ValueError("raw directory contains an unsupported entry")
        record_path = directory / "capture.json"
        if record_path.is_symlink():
            raise ValueError("capture metadata must not be a symlink")
        source = json.loads(record_path.read_text())
        if source["id"] != directory.name or source["kind"] != "private_native_capture" or source["schema_version"] != 1:
            raise ValueError("capture identity mismatch")
        if type(source["exit_code"]) is not int:
            raise ValueError("native exit code is missing")
        text = lambda value: mask(value.encode()).decode()
        capture = {
            "id": source["id"], "classification": "masked_native_capture",
            "private_capture_name": directory.name,
            "argv": [text(value) for value in source["argv"]], "cwd": text(source["cwd"]),
            "started_at": source["started_at"], "finished_at": source["finished_at"],
            "exit_code": source["exit_code"],
        }
        for stream in ("stdout", "stderr"):
            row = source[stream]
            if row["name"] != stream + ".bin":
                raise ValueError("unexpected raw stream name")
            path = directory / row["name"]
            if path.is_symlink():
                raise ValueError("raw stream must not be a symlink")
            raw = path.read_bytes()
            if len(raw) != row["bytes"] or hashlib.sha256(raw).hexdigest() != row["sha256"]:
                raise ValueError("private capture byte count or digest mismatch")
            derivative = mask(raw)
            name = directory.name + "." + stream + ".txt"
            files[name] = derivative
            capture[stream] = {"path": name, "bytes": len(derivative),
                               "sha256": hashlib.sha256(derivative).hexdigest()}
        captures.append(capture)
    if not captures:
        raise ValueError("no retained native captures")
    index = {
        "schema_version": 1, "classification": "masked_native_capture_index",
        "masking_rule": "Explicit literal byte replacement only, simultaneous longest match; all other bytes unchanged.",
        "command_placeholders": tokens,
        "custody": "Raw captures and exact argv remain private and are cited by capture name only. Digests below bind published derivative bytes only.",
        "captures": captures,
    }
    target = Path(destination)
    target.mkdir(parents=True)  # Never overwrite an already published derivative.
    for name, data in files.items():
        (target / name).write_bytes(data)
    (target / "index.json").write_text(json.dumps(index, indent=2) + "\n")
    return len(captures)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", required=True, type=Path)
    parser.add_argument("--map-file", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    count = publish(args.raw_dir, args.map_file, args.out)
    print("Published masked derivatives for " + str(count) + " native captures.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
