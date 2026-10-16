#!/usr/bin/env python3
"""Retain native bytes privately; publish with mask_capture.py, never this raw tree.

Mechanism: CPython 3.13 subprocess.run stdout/stderr file handles, timeout and
returncode; hashlib.sha256. Official documentation read 2026-10-16:
https://docs.python.org/3.13/library/subprocess.html#subprocess.run
https://docs.python.org/3.13/library/hashlib.html
This narrow wrapper differs from scripts/host_receipts.py:733-748 at
caa224140a2d04ba5f3d0ca320c487a75f9c9ea1 by retaining separate, undecoded bytes.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from datetime import datetime, timezone


def timestamp():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def record(raw_dir, capture_id, argv, cwd, environment, timeout):
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", capture_id) or not argv:
        raise ValueError("invalid capture identity or empty command")
    raw_dir = Path(raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    directory = raw_dir / capture_id
    directory.mkdir(mode=0o700)
    metadata = {
        "capture_id": capture_id,
        "argv": list(argv),
        "cwd": str(Path(cwd).resolve()),
        "environment": dict(environment),
        "started_at": timestamp(),
        "timeout_seconds": timeout,
        "exit_code": None,
        "timed_out": False,
    }
    with (directory / "stdout.bin").open("xb") as stdout, (directory / "stderr.bin").open("xb") as stderr:
        try:
            result = subprocess.run(
                argv, cwd=cwd, env=environment, stdin=subprocess.DEVNULL,
                stdout=stdout, stderr=stderr, timeout=timeout, check=False,
            )
            metadata["exit_code"] = result.returncode
        except subprocess.TimeoutExpired:
            metadata["timed_out"] = True
        except OSError as error:
            metadata["launch_error_type"] = type(error).__name__
    metadata["finished_at"] = timestamp()
    metadata["raw_streams"] = {}
    for stream in ("stdout", "stderr"):
        path = directory / (stream + ".bin")
        raw = path.read_bytes()
        metadata["raw_streams"][stream] = {
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
        }
        path.chmod(0o600)
    path = directory / "command.json"
    path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    path.chmod(0o600)
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", required=True)
    parser.add_argument("--id", required=True)
    parser.add_argument("--cwd", required=True)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--env", action="append", default=[])
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    argv = args.command[1:] if args.command[:1] == ["--"] else args.command
    environment = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "LANG": "C.UTF-8"}
    for item in args.env:
        key, separator, value = item.partition("=")
        if not separator or key not in {"ECOSYSTEM_OBSERVABILITY_DATA", "GIT_NO_LAZY_FETCH", "GIT_OPTIONAL_LOCKS"}:
            parser.error("unsupported explicit environment override")
        environment[key] = value
    metadata = record(args.raw_dir, args.id, argv, args.cwd, environment, args.timeout)
    print(json.dumps({"capture_id": metadata["capture_id"], "exit_code": metadata["exit_code"], "timed_out": metadata["timed_out"]}))
    return 0 if metadata["exit_code"] == 0 and not metadata["timed_out"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
