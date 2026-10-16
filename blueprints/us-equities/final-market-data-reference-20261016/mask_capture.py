"""Mask literal private strings in a retained native byte stream.

Preparation only: this does not record commands, return codes, or native output.
The native recorder must retain those privately before calling this helper.

Reference: CPython 3.12 re.escape/re.sub with a bytes pattern and callable
replacement: https://docs.python.org/3.12/library/re.html#re.sub
JSON escaping: https://docs.python.org/3.12/library/json.html#json.dumps
Repository source check found secret/proxy redactors, not this byte-preserving
capture transform. No generic redactor or new dependency is introduced.
"""

import argparse
import json
from pathlib import Path
import re


def mask_bytes(raw: bytes, rules: list[dict[str, str]]) -> bytes:
    """Replace UTF-8/JSON-escaped private literals once; preserve other bytes.

    Rules stay private. Each rule has an exact UTF-8 source and a marked public
    placeholder, for example {"source": "private path", "placeholder": "<scratch>"}.
    JSON forms are the literal's encoded contents from json.dumps with either
    ensure_ascii setting. This masks metadata serialized before substitution,
    including non-ASCII characters, quotes and backslashes. It does not parse,
    normalize or reserialize the captured byte stream.
    This is a declared literal mapping, not a secret detector or privacy proof.
    """
    replacements = {}
    sources = set()
    for rule in rules:
        if set(rule) != {"source", "placeholder"}:
            raise ValueError("each rule needs source and placeholder only")
        source, placeholder = rule["source"], rule["placeholder"]
        if not isinstance(source, str) or not source:
            raise ValueError("source must be a nonempty string")
        if not isinstance(placeholder, str) or not re.fullmatch(
            r"<[a-z][a-z0-9_-]*>", placeholder
        ):
            raise ValueError("placeholder must be an explicit marked token")
        if source in sources:
            raise ValueError("duplicate source")
        sources.add(source)
        aliases = {
            source.encode("utf-8"),
            json.dumps(source, ensure_ascii=True)[1:-1].encode("utf-8"),
            json.dumps(source, ensure_ascii=False)[1:-1].encode("utf-8"),
        }
        replacement = placeholder.encode("ascii")
        for key in aliases:
            if key in replacements and replacements[key] != replacement:
                raise ValueError("conflicting encoded source aliases")
            replacements[key] = replacement
    if not replacements:
        return raw
    keys = sorted(replacements, key=lambda key: (-len(key), key))
    pattern = re.compile(b"|".join(re.escape(key) for key in keys))
    return pattern.sub(lambda match: replacements[match.group(0)], raw)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", required=True, type=Path)
    parser.add_argument("--mapping", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    if args.out.resolve() in {args.raw.resolve(), args.mapping.resolve()}:
        parser.error("output must be separate from private inputs")
    rules = json.loads(args.mapping.read_text(encoding="utf-8"))
    if not isinstance(rules, list):
        parser.error("mapping must be a JSON list")
    masked = mask_bytes(args.raw.read_bytes(), rules)
    # Exclusive creation prevents overwriting either an earlier publication or
    # a raw file reached through an existing output symlink.
    with args.out.open("xb") as output:
        output.write(masked)


if __name__ == "__main__":
    main()
