"""Mask private home-path, scratch-root and UUID tokens in native bytes.

Mechanism: Python 3.13 re.sub on bytes, documented at
https://docs.python.org/3.13/library/re.html#re.sub (read 2026-10-16).
The capture and its original digest stay private. Hash the output file only.
UUID gate: native-agent-stack/native-agent-stack@caa224140a2d04ba5f3d0ca320c487a75f9c9ea1
scripts/validate.py:40. The UUID preservation test failed before this rule.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import re

HOME_PATH = re.compile(rb"/(?:home|Users)/[^\s\"'<>]+")
UUID = re.compile(rb"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")


def mask_capture(raw: bytes, *, scratch_root: bytes | None = None) -> bytes:
    """Preserve every byte except named tokens; no decoding or filtering."""
    if scratch_root:
        raw = raw.replace(scratch_root, b"<PRIVATE_SCRATCH_ROOT>")
    return UUID.sub(b"<UUID>", HOME_PATH.sub(b"<PRIVATE_HOME_PATH>", raw))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--scratch-root", help="Private exact root supplied locally; never embedded in the rule.")
    args = parser.parse_args()
    scratch_root = args.scratch_root.encode() if args.scratch_root else None
    args.output.write_bytes(mask_capture(args.input.read_bytes(), scratch_root=scratch_root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
