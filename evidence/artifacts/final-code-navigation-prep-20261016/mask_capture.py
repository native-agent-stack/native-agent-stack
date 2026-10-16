"""Publish literal path masks of native capture bytes; never summarize output.

The binding file stays private. Each item has an absolute ``value`` prefix
and a marked ``placeholder`` such as ``$SCRATCH``. Longer prefixes are
replaced first. All other bytes, including line endings, stay unchanged.
The published-byte hash contract follows scripts/host_receipts.py:1012.
"""

import argparse
import hashlib
import json
from pathlib import Path
import re


def mask_bytes(raw: bytes, bindings: list[dict[str, str]]) -> bytes:
    pairs = []
    seen = set()
    for item in bindings:
        value, placeholder = item["value"], item["placeholder"]
        if not value.startswith("/") or value == "/":
            raise ValueError("a non-root absolute prefix is required")
        if not re.fullmatch(r"\$[A-Z][A-Z0-9_]*", placeholder):
            raise ValueError("a marked placeholder is required")
        if value in seen:
            raise ValueError("duplicate private prefix")
        seen.add(value)
        pairs.append((value.encode("utf-8"), placeholder.encode("ascii")))
    for value, placeholder in sorted(pairs, key=lambda pair: -len(pair[0])):
        raw = raw.replace(value, placeholder)
    return raw


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--bindings", type=Path, required=True)
    parser.add_argument("--published", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.raw.resolve() == args.published.resolve():
        parser.error("capture and published destination must differ")
    bindings = json.loads(args.bindings.read_text(encoding="utf-8"))
    masked = mask_bytes(args.raw.read_bytes(), bindings)
    if args.check:
        if args.published.read_bytes() != masked:
            print("masked derivative mismatch")
            return 1
    else:
        args.published.parent.mkdir(parents=True, exist_ok=True)
        args.published.write_bytes(masked)
    print("published_sha256=" + hashlib.sha256(masked).hexdigest())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
