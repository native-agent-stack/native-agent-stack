#!/usr/bin/env python3
"""Deterministically mask a native output; never manufacture command/rc metadata.

Reference primitives: Python 3.14 bytes.replace and re.sub (bytes patterns),
https://docs.python.org/3/library/stdtypes.html#bytes.replace and
https://docs.python.org/3/library/re.html#re.sub . Custody follows the repository's
tests/test_provenance_digest_custody.py and the named FINAL-wave masking addendum.

Only explicitly supplied path prefixes and ANSI SGR sequences are replaced.
All other bytes, including line endings, trailing whitespace, errors and counts,
are retained. The private raw file is named only in the public manifest. No raw
digest, source path, command, exit code, measurement or timestamp is invented.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re


ANSI_SGR = re.compile(rb"\x1b\[[0-9;]*m")


def mask_bytes(
    raw: bytes,
    scratch_prefix: bytes,
    private_prefixes: tuple[tuple[bytes, bytes], ...] = (),
) -> bytes:
    if not scratch_prefix or scratch_prefix == b"/":
        raise ValueError("An explicit non-root scratch prefix is required")
    masked = ANSI_SGR.sub(b"", raw).replace(scratch_prefix, b"<scratch>")
    for prefix, placeholder in sorted(private_prefixes, key=lambda pair: len(pair[0]), reverse=True):
        if not prefix or prefix == b"/" or not re.fullmatch(rb"<[a-z-]+>", placeholder):
            raise ValueError("Private prefixes need a non-root path and a marked placeholder")
        masked = masked.replace(prefix, placeholder)
    return masked


def masked_record(capture_name: str, output_name: str, masked: bytes) -> dict:
    if Path(capture_name).name != capture_name or capture_name in {"", ".", ".."}:
        raise ValueError("Raw capture must be identified by a basename only")
    record = {
        "kind": "masked_native_output",
        "raw_capture_name": capture_name,
        "published_output": output_name,
        "published_bytes": len(masked),
        "published_sha256": hashlib.sha256(masked).hexdigest(),
        "masking_rule": "mask_capture.py:ANSI_SGR removal and explicit path-prefix replacements only",
        "command_rc_custody": "Read the native transcript's COMMAND and COMMAND_EXIT_CODE; a plain output file alone does not establish them",
        "co_op_private_reproduction": "PENDING",
    }
    lines = masked.splitlines()
    command = re.search(rb'\[COMMAND="(.*)"(?: .*)?\]$', lines[0]) if lines else None
    tail = next(((index + 1, line) for index, line in reversed(list(enumerate(lines))) if line), None)
    returned = re.search(rb'^Script done on .* \[COMMAND_EXIT_CODE="([0-9]+)"\]$', tail[1]) if tail else None
    if lines and lines[0].startswith(b"Script started on ") and command and returned:
        record["command_rc_custody"] = "native util-linux script transcript header/footer"
        record["command_display"] = command.group(1).decode("utf-8")
        record["return_code"] = int(returned.group(1))
        record["command_line"] = 1
        record["return_code_line"] = tail[0]
    return record


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--scratch-prefix", required=True)
    parser.add_argument("--capture-name", required=True)
    parser.add_argument("--published-name", required=True)
    parser.add_argument("--private-prefix", action="append", default=[], metavar="PATH=<placeholder>")
    args = parser.parse_args()
    if args.raw.resolve() == args.output.resolve():
        parser.error("Raw input must never be overwritten")
    private_prefixes = []
    for entry in args.private_prefix:
        prefix, separator, placeholder = entry.rpartition("=")
        if not separator:
            parser.error("--private-prefix requires PATH=<placeholder>")
        private_prefixes.append((prefix.encode(), placeholder.encode()))
    masked = mask_bytes(args.raw.read_bytes(), args.scratch_prefix.encode(), tuple(private_prefixes))
    record = masked_record(args.capture_name, args.published_name, masked)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(masked)
    print(json.dumps(record, sort_keys=True))


if __name__ == "__main__":
    main()
