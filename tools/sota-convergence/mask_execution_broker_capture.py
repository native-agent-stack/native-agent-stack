"""Deterministic byte masking for the execution-broker preparation captures.

Reference: CPython v3.13.16 Lib/re/__init__.py (escape, compile),
Modules/_sre/sre.c (Pattern.sub), Lib/pathlib/_abc.py (read_bytes/write_bytes),
Lib/json/__init__.py (loads).
Only declared literal private paths, unpublished build digests and private-source
cache keys are replaced. pip's SHA224 key is accepted in plain and sharded form
(pypa/pip@634a6ec src/pip/_internal/cache.py:27-30,50-85;
wheel_builder.py:49-50,88,196). These are explicit literals, not hash wildcards,
replaced longest-first in one pass. A digest entry masks a captured build-tool fingerprint;
it is never copied into a public map or recomputed as a public receipt value.
No output is summarized, filtered, decoded or assigned a new command result.
The private map is supplied separately to the co-op; publish only its marked
placeholder names and roles. This is not a general secret scanner.
"""
import argparse
import json
from pathlib import Path
import re


def replace_literals(raw, values):
    """Replace original byte matches once; inserted bytes are never rescanned.

    This byte-engine seam also accepts replacement bytes containing a key,
    allowing the one-pass property to be tested independently of path syntax.
    The CLI still uses mask_bytes' stricter path/placeholder validation.
    """
    pattern = re.compile(b'|'.join(re.escape(key) for key in sorted(values, key=lambda x: (-len(x), x))))
    return pattern.sub(lambda match: values[match.group(0)], raw)


def mask_bytes(raw, mapping):
    if not isinstance(mapping, dict) or not mapping:
        raise ValueError('nonempty path map required')
    for path, placeholder in mapping.items():
        if not isinstance(path, str):
            raise ValueError('literal mapping keys must be strings')
        is_path = path.startswith('/') and path != '/'
        is_digest = re.fullmatch(r'(?:[0-9a-f]{56}|[0-9a-f]{64})', path) is not None
        if (not (is_path or is_digest) or not isinstance(placeholder, str)
                or re.fullmatch(r'<[A-Z][A-Z0-9_]*>', placeholder) is None):
            raise ValueError('map requires absolute paths, SHA224 cache keys or SHA256 build digests and marked placeholders')
    values = {key.encode('utf-8'): value.encode('ascii') for key, value in mapping.items()}
    for key, value in mapping.items():
        if re.fullmatch(r'[0-9a-f]{56}', key):
            # pip Cache._get_cache_path_parts splits the declared SHA224 key
            # into two/two/two/remaining hex characters. Mask that exact spelling
            # too, so replacing a private source URL cannot leave its oracle.
            sharded = '/'.join((key[:2], key[2:4], key[4:6], key[6:]))
            values[sharded.encode('ascii')] = value.encode('ascii')
    return replace_literals(raw, values)


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
