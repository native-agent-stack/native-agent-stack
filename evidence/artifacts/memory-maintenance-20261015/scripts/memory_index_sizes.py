#!/usr/bin/env python3
"""List ~/.claude/projects/*/memory/MEMORY.md: path, size and line counts only (never content).

Columns:
  utf8_bytes      raw file size on disk
  raw_lines       newline count (wc -l semantics)
  trim_lines      lines of the whitespace-trimmed text, counted the way the 2.1.300
                  loader does (count of "\n" in trimmed text + 1)
  trim_units      UTF-16 code units of the trimmed text (JavaScript String.length,
                  which the 2.1.300 loader compares against its 25000 cap)
Flags mark >= 90% (and >= 80%, the client's own "near" threshold) of 200 lines / 25000.
"""
import glob
import os
import sys

LINE_CAP, SIZE_CAP = 200, 25000
home = os.path.expanduser("~")
rows = []
for path in sorted(glob.glob(os.path.join(home, ".claude/projects/*/memory/MEMORY.md"))):
    raw = open(path, "rb").read()
    text = raw.decode("utf-8", errors="replace")
    # JS String.prototype.trim() strips the same Unicode whitespace class Python's str.strip covers
    # for practical index content (spaces, tabs, newlines, NBSP, BOM is not stripped by Python: handle it).
    trimmed = text.strip().lstrip(chr(0xFEFF)).strip()
    trim_lines = trimmed.count("\n") + 1 if trimmed else 0
    trim_units = len(trimmed.encode("utf-16-le")) // 2
    flags = []
    for name, val, cap in (
        ("lines", trim_lines, LINE_CAP),
        ("units", trim_units, SIZE_CAP),
        ("bytes", len(raw), SIZE_CAP),
    ):
        frac = val / cap
        if frac > 1:
            flags.append(f"OVER-{name}")
        elif frac >= 0.9:
            flags.append(f">=90%-{name}")
        elif frac >= 0.8:
            flags.append(f">=80%-{name}")
    rows.append((path.replace(home, "~"), len(raw), raw.count(b"\n"), trim_lines, trim_units, ",".join(flags) or "-"))

w = sys.stdout.write
w("path\tutf8_bytes\traw_lines\ttrim_lines\ttrim_units\tflags\n")
for r in rows:
    w("\t".join(str(x) for x in r) + "\n")
w(f"# files={len(rows)}\n")
