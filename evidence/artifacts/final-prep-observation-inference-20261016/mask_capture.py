#!/usr/bin/env python3
"""Deterministic literal masking of private native captures, with no summaries.

Private mapping is {"<MARKED_PLACEHOLDER>": "literal private text", ...}.
Longest UTF-8 byte sequence wins; all nonmatching bytes remain unchanged.
No regex removal, line filtering, output synthesis or JSON API projection occurs.
CPython 3.13 bytes.replace/hashlib/json documentation, read 2026-10-16:
https://docs.python.org/3.13/library/stdtypes.html#bytes.replace
https://docs.python.org/3.13/library/hashlib.html
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re


def replacements(mapping):
    pairs = []
    seen = set()
    for marker, literal in mapping.items():
        if not re.fullmatch(r"<[A-Z][A-Z0-9_]*>", marker) or not isinstance(literal, str) or not literal:
            raise ValueError("invalid mask mapping")
        raw = literal.encode("utf-8")
        if raw in seen or b"<" in raw or b">" in raw:
            raise ValueError("ambiguous or recursive mask mapping")
        seen.add(raw)
        pairs.append((raw, marker.encode("ascii")))
    if any(literal in marker for literal, _ in pairs for _, marker in pairs):
        raise ValueError("a literal would modify a placeholder")
    return sorted(pairs, key=lambda pair: (-len(pair[0]), pair[0]))


def mask_bytes(raw, pairs):
    for literal, marker in pairs:
        raw = raw.replace(literal, marker)
    return raw


def mask_value(value, pairs):
    if isinstance(value, str):
        return mask_bytes(value.encode("utf-8"), pairs).decode("utf-8")
    if isinstance(value, list):
        return [mask_value(item, pairs) for item in value]
    if isinstance(value, dict):
        return {key: mask_value(item, pairs) for key, item in value.items()}
    return value


def publish(raw_dir, output_dir, mapping):
    pairs = replacements(mapping)
    raw_dir, output_dir = Path(raw_dir), Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for directory in sorted(path for path in raw_dir.iterdir() if path.is_dir()):
        private = json.loads((directory / "command.json").read_text(encoding="utf-8"))
        if directory.name != private["capture_id"] or not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", directory.name):
            raise ValueError("capture name mismatch")
        public = {key: value for key, value in private.items() if key != "raw_streams"}
        public = mask_value(public, pairs)
        public["capture_class"] = "deterministically_masked_native_capture"
        public["raw_capture_name"] = directory.name
        public["masking_rule"] = "mask_capture.py: literal UTF-8 replacements, longest first; unchanged nonmatching bytes"
        public["mask_placeholders"] = sorted(mapping)
        public["streams"] = {}
        for stream in ("stdout", "stderr"):
            raw = (directory / (stream + ".bin")).read_bytes()
            metadata = private["raw_streams"][stream]
            if len(raw) != metadata["bytes"] or hashlib.sha256(raw).hexdigest() != metadata["sha256"]:
                raise ValueError("private capture stream integrity mismatch")
            masked = mask_bytes(raw, pairs)
            name = directory.name + "." + stream + ".txt"
            (output_dir / name).write_bytes(masked)
            public["streams"][stream] = {
                "path": name, "bytes": len(masked), "sha256": hashlib.sha256(masked).hexdigest(),
                "hash_scope": "published masked bytes only",
            }
        (output_dir / (directory.name + ".json")).write_text(json.dumps(public, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        count += 1
    return count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--mapping", required=True)
    parser.add_argument("--init-mapping", action="store_true")
    parser.add_argument("--checkout")
    parser.add_argument("--scratch")
    args = parser.parse_args()
    if args.init_mapping:
        if not args.checkout or not args.scratch:
            parser.error("mapping initialization needs checkout and scratch")
        mapping = {
            "<CHECKOUT>": str(Path(args.checkout).resolve()),
            "<SCRATCH>": str(Path(args.scratch).resolve()),
            "<USER_HOME>": str(Path.home()),
            "<LOCAL_HOST>": os.uname().nodename,
        }
        replacements(mapping)
        path = Path(args.mapping)
        with path.open("x", encoding="utf-8") as output:
            json.dump(mapping, output, indent=2)
            output.write("\n")
        path.chmod(0o600)
        print("Private mapping created; no values or digests published.")
        return
    mapping = json.loads(Path(args.mapping).read_text(encoding="utf-8"))
    print(json.dumps({"published_native_captures": publish(args.raw_dir, args.out, mapping)}))


if __name__ == "__main__":
    main()
