#!/usr/bin/env python3
"""Publish a byte-preserving masked derivative of an existing native capture.

Only the exact scratch-prefix byte string is replaced with b"<SCRATCH>".
No decoding, newline conversion, output generation or error substitution occurs.
Python's bytes.replace contract: https://docs.python.org/3/library/stdtypes.html#bytes.replace
"""

import argparse
from pathlib import Path


def mask_capture(raw: bytes, scratch_prefix: bytes) -> bytes:
    if not scratch_prefix.startswith(b"/") or scratch_prefix == b"/":
        raise ValueError("scratch prefix must be an absolute non-root path")
    return raw.replace(scratch_prefix, b"<SCRATCH>")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--scratch-prefix", required=True)
    args = parser.parse_args()
    if args.source.resolve() == args.output.resolve():
        parser.error("source and output must differ; preserve the raw capture")
    result = mask_capture(args.source.read_bytes(), args.scratch_prefix.encode("utf-8"))
    args.output.write_bytes(result)


if __name__ == "__main__":
    main()
