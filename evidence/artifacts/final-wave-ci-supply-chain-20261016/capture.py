#!/usr/bin/env python3
"""Native byte recorder using Python subprocess.run (3.14 docs, read 2026-10-16).

No child output is decoded, merged, truncated, summarized, or fabricated.
Private capture directory contains exact argv/cwd/environment, stdout/stderr,
return code, timestamps and raw hashes. Never publish this private directory.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def record(raw_root, name, argv, cwd, environment):
    target = Path(raw_root) / name
    target.mkdir(mode=0o700, parents=True, exist_ok=False)
    start = now()
    with (target / "stdout.bin").open("xb") as stdout, (target / "stderr.bin").open("xb") as stderr:
        process = subprocess.run(argv, cwd=cwd, env=environment, stdin=subprocess.DEVNULL,
                                 stdout=stdout, stderr=stderr, check=False)
    data = {"schema_version": 1, "capture_name": name, "argv": argv, "cwd": str(cwd),
            "environment": environment, "started_at": start, "finished_at": now(),
            "exit_code": process.returncode, "streams": {}}
    for stream in ("stdout", "stderr"):
        raw = (target / (stream + ".bin")).read_bytes()
        data["streams"][stream] = {"file": stream + ".bin", "bytes": len(raw),
                                    "raw_sha256_private": hashlib.sha256(raw).hexdigest()}
    (target / "capture.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    for path in target.iterdir():
        path.chmod(0o600)
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-root", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--scratch", required=True)
    parser.add_argument("--cwd", required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    argv = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not argv or not args.name.replace("-", "").replace("_", "").isalnum():
        parser.error("a command and a simple capture name are required")
    s = str(Path(args.scratch).resolve())
    env = {
        "PATH": s + "/bin:/usr/bin:/bin", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8",
        "XDG_CONFIG_HOME": s + "/config", "XDG_CACHE_HOME": s + "/cache",
        "XDG_DATA_HOME": s + "/data", "TMPDIR": s + "/tmp",
        "UV_TOOL_DIR": s + "/tools", "UV_TOOL_BIN_DIR": s + "/bin",
        "UV_CACHE_DIR": s + "/cache/uv", "UV_PYTHON_INSTALL_DIR": s + "/python",
        "UV_NO_CONFIG": "1", "UV_NO_PROGRESS": "1", "UV_LINK_MODE": "copy",
        "UV_PYTHON_DOWNLOADS": "never", "UV_KEYRING_PROVIDER": "disabled",
        "CURL_HOME": s + "/curl", "WGETRC": "/dev/null",
        "DOWNLOAD_TAG_INSTALL_SCRIPT": "false", "SYFT_CHECK_FOR_APP_UPDATE": "false",
        "ZIZMOR_OFFLINE": "1", "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_NO_LAZY_FETCH": "1",
        "GIT_OPTIONAL_LOCKS": "0"
    }
    os.umask(0o077)
    result = record(args.raw_root, args.name, argv, args.cwd, env)
    print(json.dumps({"capture_name": args.name, "exit_code": result["exit_code"],
                      "stdout_bytes": result["streams"]["stdout"]["bytes"],
                      "stderr_bytes": result["streams"]["stderr"]["bytes"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
