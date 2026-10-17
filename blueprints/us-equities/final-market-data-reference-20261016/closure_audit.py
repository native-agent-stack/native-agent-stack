"""Deterministic source audit of native freeze output versus the accepted lock."""

import argparse
import json
from pathlib import Path
import re
import tomllib


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze", required=True, type=Path)
    parser.add_argument("--runtime-lock", required=True, type=Path)
    args = parser.parse_args()
    normalize = lambda value: re.sub(r"[-_.]+", "-", value).lower()
    observed = {}
    for line, value in enumerate(args.freeze.read_text().splitlines(), 1):
        match = re.fullmatch(r"([A-Za-z0-9_.-]+)==([^\s]+)", value)
        if match:
            observed[normalize(match[1])] = (match[2], line)
    if not observed:
        raise ValueError("freeze contains no package-version rows; no closure can be claimed")
    lock_lines = args.runtime_lock.read_text().splitlines()
    locked = {normalize(p["name"]): p["version"]
              for p in tomllib.loads(args.runtime_lock.read_text())["package"]}
    rows = []
    for name, (version, line) in sorted(observed.items()):
        expected = locked.get(name)
        version_line = None
        if expected is not None:
            name_line = next(i for i, value in enumerate(lock_lines)
                             if value == f'name = "{name}"')
            version_line = next(i + 1 for i in range(name_line + 1, len(lock_lines))
                                if lock_lines[i].startswith("version = "))
        rows.append({"name": name, "observed": version, "locked": expected,
            "status": "not_in_runtime_lock" if expected is None else
                      "matches" if version == expected else "differs",
            "freeze_line": line, "runtime_lock_version_line": version_line})
    print(json.dumps({"schema": "resolved-closure-audit/1", "rows": rows,
        "scope": "Native freeze versus accepted runtime lock, not a claim of locked migration or suite acceptance."},
        indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
