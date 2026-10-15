#!/usr/bin/env python3
"""Read the MEMORY.md index limits out of an installed Claude Code binary without hard-coding
minified identifiers.

Step A (anchored on user-visible text): find the loader's truncation warning template, which
contains the literal phrases "lines (limit: ${X})" and "(limit: ${F(Y)}) ... index entries are
too long" within ~1.2 KB before "Only part of it was loaded". X and Y are the minified
identifiers of the line cap and the size cap in this build.

Step B (binds the identifiers to values): the module that defines the caps declares them right
after the filename literal: `<id>="MEMORY.md",X=<int>,Y=<int>`. Accept the values only when B's
identifiers are exactly A's identifiers. Minified names are module-local and collide across
chunks (2.1.299: `qN=8` in one chunk, `qN=200` in the memory chunk), so a global `X=<int>`
search is reported for transparency but never decides.

Exit 0 and print JSON when A and B bind; exit 2 (fail closed, no guessed numbers) otherwise.
Usage: extract_memory_index_limits.py <path-to-claude-binary>
"""
import hashlib
import json
import mmap
import re
import sys

IDENT = rb"[A-Za-z_$][A-Za-z0-9_$]*"
LINE_TMPL = re.compile(rb" lines \(limit: \$\{(" + IDENT + rb")\}\)")
SIZE_TMPL = re.compile(rb"\(limit: \$\{" + IDENT + rb"\((" + IDENT + rb")\)\}\)[^`]{0,40}index entries are too long")
ANCHOR = b"Only part of it was loaded"
DECL_B = re.compile(rb'=\"MEMORY\.md\",(' + IDENT + rb")=(\d+),(" + IDENT + rb")=(\d+)[,;]")


def global_values(buf, ident):
    pat = re.compile(rb"(?<![A-Za-z0-9_$.])" + re.escape(ident) + rb"=(\d+)(?=[,;)}\s])")
    return sorted({int(m.group(1)) for m in pat.finditer(buf)})


def main(path):
    with open(path, "rb") as fh:
        if fh.seek(0, 2) == 0:
            print(json.dumps({"binary": path, "status": "unresolved", "reason": "empty file"}))
            return 2
        buf = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
        result = {"binary": path, "sha256": hashlib.sha256(buf).hexdigest(), "step_a": [], "step_b": []}
        for m in re.finditer(re.escape(ANCHOR), buf):
            win = buf[max(0, m.start() - 1200): m.start() + 400]
            lm, sm = LINE_TMPL.search(win), SIZE_TMPL.search(win)
            if lm and sm:
                result["step_a"].append({
                    "anchor_offset": m.start(),
                    "line_cap_ident": lm.group(1).decode(),
                    "size_cap_ident": sm.group(1).decode(),
                    "global_line_values": global_values(buf, lm.group(1)),
                    "global_size_values": global_values(buf, sm.group(1)),
                })
        for m in DECL_B.finditer(buf):
            result["step_b"].append({
                "offset": m.start(),
                "first": [m.group(1).decode(), int(m.group(2))],
                "second": [m.group(3).decode(), int(m.group(4))],
            })
    ids = {(a["line_cap_ident"], a["size_cap_ident"]) for a in result["step_a"]}
    bound = set()
    if len(ids) == 1:
        (line_id, size_id), = ids
        for b in result["step_b"]:
            if b["first"][0] == line_id and b["second"][0] == size_id:
                bound.add((b["first"][1], b["second"][1]))
    ok = len(bound) == 1
    if ok:
        (result["line_cap"], result["size_cap"]), = bound
    result["status"] = "ok" if ok else "unresolved"
    print(json.dumps(result, indent=1))
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
