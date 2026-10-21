#!/usr/bin/env python3
"""Fault pass for the command-shape reducer: plant each fault in a copy of storm_snapshot.py, run storm_snapshot_selftest.py on the copy and require a failure. The unchanged copy is run first (the
control) and must pass; a run that does not reach the self-test's summary line is BROKEN and never counts as a caught fault.

  storm_snapshot_mutants.py [--tools DIR]       (DIR holds storm_snapshot.py and storm_snapshot_selftest.py; default: this file's directory)

Each fault removes one rule of the reducer's grammar (see the docstring and the tables of storm_snapshot.py): CPython's own option scan, the first-argument rule of the other interpreters, the
subcommand and target vocabularies of the runners and of other programs, the wrapper tables, or the plain-text tests on names. Reference for the control-first rule: trailofbits/skills (mirrored at
HEAD 0f44fe01dcb0) plugins/mutation-testing/skills/mutation-testing/workflows/configuration.md:134-141.
"""
import re
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(sys.argv[sys.argv.index("--tools") + 1] if "--tools" in sys.argv else Path(__file__).resolve().parent)
TOOL, SELFTEST = "storm_snapshot.py", "storm_snapshot_selftest.py"
MUTANTS = [
    ("python: an attached value of -m, -c, -W or -X is not recognized (the next word is taken instead)", "                if j < len(letters):\n                    value, j = letters[j:], len(letters)\n                elif i < n:",
     "                if False:\n                    value, j = letters[j:], len(letters)\n                elif i < n:"),
    ("python: -c does not end the scan (a later word is taken for the script)", '                if c == "c":\n                    return ("code", None)\n', '                if c == "c":\n                    continue\n'),
    ("python: an unknown short option does not end the scan", "                continue\n            return None\n    if i < n and rest[i] != \"-\":", "                continue\n            continue\n    if i < n and rest[i] != \"-\":"),
    ("python: the long option with an argument does not consume it", "            if t in PY_LONG_ARG:\n                i += 2\n                continue", "            if t in PY_LONG_ARG:\n                i += 1\n                continue"),
    ("python: an unknown long option does not end the scan", "                continue\n            return None\n        i += 1\n        letters, j = t[1:], 0", "                continue\n            i += 1\n            continue\n        i += 1\n        letters, j = t[1:], 0"),
    ("python: a lone dash is taken for a script", 'if not t.startswith("-") or t == "-":', 'if not t.startswith("-"):'),
    ("python: a module name is not validated", 'value if (len(value) <= 40 and MODULE_RX.match(value) and not SECRET_RX.search(value)) else "<arg>"', "value"),
    ("node, a shell, perl: the first non-option word is taken, not only the first argument", "    t = rest[0]\n    for rx, marker in FIRST_ARG_INLINE.get(fam, ()):", "    t = next((x for x in rest if not x.startswith(\"-\")), rest[0])\n    for rx, marker in FIRST_ARG_INLINE.get(fam, ()):"),
    ("a script is any word, not only a path or a file with a script extension", '    if t.startswith("-") or not ("/" in t or SCRIPT_RX.search(t)):\n        return []', '    if t.startswith("-"):\n        return []'),
    ("a runner copies an unknown subcommand", '    if sub not in RUNNER_SUBS[b0]:\n        return ["<arg>"]', "    if sub not in RUNNER_SUBS[b0]:\n        return [sub]"),
    ("a runner copies an unknown target", '        return _script(t)\n    return ["<arg>"]', "        return _script(t)\n    return [t]"),
    ("another program's unknown first word is copied", '    return ["<redacted>"] if SECRET_RX.search(t) else ["<arg>"]\n\n\ndef _wrapper', "    return [t]\n\n\ndef _wrapper"),
    ("a wrapper's required number is not required", "    for _ in range(WRAPPER_POSITIONALS.get(name, 0)):", "    for _ in range(0):"),
    ("a wrapper flag that is not in its table does not end the extraction", "            else:\n                return name\n            continue", "            else:\n                i += 1\n            continue"),
    ("a wrapper's assignments are not skipped", '        if ASSIGN_RX.match(t) or (name == "rtk" and t == "proxy"):', '        if (name == "rtk" and t == "proxy"):'),
    ("the kernel name is copied without the plain-text test", '    return c if COMM_RX.match(c) and not SECRET_RX.search(c) else "<proc>"', "    return c"),
    ("a key-looking word is copied", '    if SECRET_RX.search(t):\n        return "<redacted>"\n    return t[:40] if WORD_RX.match(t[:48]) else "<arg>"', '    return t[:40] if WORD_RX.match(t[:48]) else "<arg>"'),
]


def run_suite(d):
    try:
        r = subprocess.run([sys.executable, "-B", "-I", str(Path(d) / SELFTEST)], capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired:
        return -1, ""
    return r.returncode, r.stdout


def classify(rc, out):
    summary = re.search(r"^(ALL PASS|\d+ FAILED)$", out, re.M)
    if not summary:
        return "broken"
    return "pass" if rc == 0 and summary.group(1) == "ALL PASS" else "caught" if rc != 0 and summary.group(1).endswith("FAILED") else "broken"


def one(m):
    name, old, new = m
    with tempfile.TemporaryDirectory(prefix="ss-mut-") as d:
        for f in (TOOL, SELFTEST):
            shutil.copy(HERE / f, d)
        p = Path(d) / TOOL
        s = p.read_text()
        if s.count(old) != 1:
            return name, "broken", f"text found {s.count(old)} times"
        p.write_text(s.replace(old, new))
        return name, classify(*run_suite(d)), ""


def main():
    with tempfile.TemporaryDirectory(prefix="ss-mut-") as d:
        for f in (TOOL, SELFTEST):
            shutil.copy(HERE / f, d)
        control = classify(*run_suite(d))
    print(f"control: the unmodified self-test {'passes' if control == 'pass' else 'does NOT pass (' + control + ')'}")
    if control != "pass":
        print("no score is issued")
        return 1
    with ThreadPoolExecutor(max_workers=3) as ex:
        results = list(ex.map(one, MUTANTS))
    caught = 0
    for name, v, info in results:
        print({"caught": "caught  ", "pass": "MISSED  ", "broken": "BROKEN  "}[v] + name + (f" ({info})" if info else ""))
        caught += v == "caught"
    print(f"{caught} of {len(MUTANTS)} planted faults caught")
    return 0 if caught == len(MUTANTS) else 1


if __name__ == "__main__":
    sys.exit(main())
