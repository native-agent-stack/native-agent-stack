"""Deterministic byte masking for the execution-broker preparation captures.

Reference: CPython v3.13.16 Lib/re/__init__.py (escape, compile, Pattern.sub),
Lib/pathlib.py (read_bytes/write_bytes), Lib/json/__init__.py (loads).
Only declared literal private paths are replaced, longest-first, in one pass.
No output is summarized, filtered, decoded or assigned a new command result.
The private map is supplied separately to the co-op; publish only its marked
placeholder names and roles. This is not a general secret scanner.
"""
import argparse
import json
from pathlib import Path
import re


def mask_bytes(raw, mapping):
    if not isinstance(mapping, dict) or not mapping:
        raise ValueError('nonempty path map required')
    for path, placeholder in mapping.items():
        if (not isinstance(path, str) or not path.startswith('/') or path == '/'
                or not isinstance(placeholder, str)
                or re.fullmatch(r'<[A-Z][A-Z0-9_]*>', placeholder) is None):
            raise ValueError('map requires literal absolute paths and marked placeholders')
    values = {key.encode('utf-8'): value.encode('ascii') for key, value in mapping.items()}
    pattern = re.compile(b'|'.join(re.escape(key) for key in sorted(values, key=lambda x: (-len(x), x))))
    return pattern.sub(lambda match: values[match.group(0)], raw)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mapping', type=Path, required=True)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = mask_bytes(args.input.read_bytes(), json.loads(args.mapping.read_text()))
    with args.output.open('xb') as stream:
        stream.write(result)


if __name__ == '__main__':
    main()
