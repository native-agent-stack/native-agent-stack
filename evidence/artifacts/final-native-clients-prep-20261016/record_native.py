#!/usr/bin/env python3
"""Record a native process without decoding or modifying its output streams.

CPython v3.13.16: Lib/subprocess.py (run and redirected binary files),
Lib/hashlib.py (file_digest), and Lib/pathlib/__init__.py (exclusive mkdir).
The private capture contains raw digests and exact argv; never publish it.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def utc_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def record(raw_dir, capture_id, cwd, argv):
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", capture_id):
        raise ValueError("invalid capture id")
    root = Path(raw_dir)
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    destination = root / capture_id
    destination.mkdir(mode=0o700)  # Existing observations cannot be overwritten.
    started = utc_now()
    paths = {stream: destination / (stream + ".bin") for stream in ("stdout", "stderr")}
    with paths["stdout"].open("xb") as stdout, paths["stderr"].open("xb") as stderr:
        os.chmod(paths["stdout"], 0o600)
        os.chmod(paths["stderr"], 0o600)
        result = subprocess.run(
            argv, cwd=cwd, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
            env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"}, check=False,
        )
    metadata = {
        "schema_version": 1, "kind": "private_native_capture", "id": capture_id,
        "argv": argv, "cwd": str(cwd), "started_at": started,
        "finished_at": utc_now(), "exit_code": result.returncode,
    }
    for stream, path in paths.items():
        with path.open("rb") as handle:
            digest = hashlib.file_digest(handle, "sha256").hexdigest()
        metadata[stream] = {"name": path.name, "bytes": path.stat().st_size, "sha256": digest}
    record_path = destination / "capture.json"
    with record_path.open("x", encoding="utf-8") as handle:
        json.dump(metadata, handle, indent=2)
        handle.write("\n")
    os.chmod(record_path, 0o600)
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", required=True, type=Path)
    parser.add_argument("--id", required=True)
    parser.add_argument("--cwd", required=True)
    parser.add_argument("argv", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.argv[1:] if args.argv[:1] == ["--"] else args.argv
    if not command:
        parser.error("a native command is required")
    metadata = record(args.raw_dir, args.id, args.cwd, command)
    print(args.id + ": captured; native exit " + str(metadata["exit_code"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
