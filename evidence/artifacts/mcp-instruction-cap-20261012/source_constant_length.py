#!/usr/bin/env python3
r"""The length of a Rust string constant in a source file, counted the way the compiler reads it: source_constant_length.py FILE CONSTANT [--marker LINE]

Reads FILE (for example crates/ai-memory-mcp/src/server.rs of akitaonrails/ai-memory), finds `pub const CONSTANT: &str = "...";`, resolves the literal's escapes (`\n`, `\t`, `\"`, `\\`, `\'`) and a backslash at the end of a line
(which drops the newline and the next line's leading whitespace), and prints one JSON object: the length in characters (Unicode code points) and in UTF-16 code units, the number of characters outside the Basic Multilingual Plane,
the first 16 hex digits of the sha256 of the UTF-8 text, and with --marker the position of that line (the core length before it). The text itself is not printed. Other escapes (`\x`, `\u{...}`) stop the run with exit 2.
Exit 0 read, 2 the constant is not found or uses an escape this script does not resolve. ASCII only."""
import hashlib
import json
import re
import sys
from pathlib import Path

ESCAPES = {"n": "\n", "t": "\t", '"': '"', "\\": "\\", "'": "'"}


def constant_text(source: str, name: str) -> str:
    lines = source.split("\n")
    start = next((i for i, line in enumerate(lines) if re.match(rf"\s*pub const {re.escape(name)}\s*:\s*&str\s*=\s*\"", line)), None)
    if start is None:
        raise ValueError(f"constant {name} not found")
    first = lines[start].split('= "', 1)[1]
    body, closed = [first], first.rstrip().endswith('";') and not first.rstrip().endswith('\\";')
    for line in lines[start + 1:]:
        if closed:
            break
        body.append(line)
        closed = line.rstrip().endswith('";') and not line.rstrip().endswith('\\";')
    raw = "\n".join(body).rstrip()
    if not raw.endswith('";'):
        raise ValueError(f"constant {name} is not closed")
    raw = re.sub(r"\\\n\s*", "", raw[:-2])
    out, i = [], 0
    while i < len(raw):
        if raw[i] != "\\":
            out.append(raw[i])
            i += 1
            continue
        if raw[i + 1] not in ESCAPES:
            raise ValueError(f"escape \\{raw[i + 1]} is not resolved by this script")
        out.append(ESCAPES[raw[i + 1]])
        i += 2
    return "".join(out)


def main(argv):
    if len(argv) < 3:
        print(__doc__.split("\n")[0], file=sys.stderr)
        return 2
    marker = argv[argv.index("--marker") + 1] if "--marker" in argv else None
    try:
        text = constant_text(Path(argv[1]).read_text(encoding="utf-8"), argv[2])
    except (OSError, ValueError) as error:
        print(f"source_constant_length: {error}", file=sys.stderr)
        return 2
    out = {"constant": argv[2], "characters": len(text), "utf16_units": len(text.encode("utf-16-le")) // 2, "outside_bmp": sum(1 for c in text if ord(c) > 0xFFFF),
           "sha256_16": hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]}
    if marker:
        at = text.find(marker)
        out["marker"] = marker if at >= 0 else None
        if at >= 0:
            out["core"], out["detail"] = at, len(text) - at - len(marker)
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
