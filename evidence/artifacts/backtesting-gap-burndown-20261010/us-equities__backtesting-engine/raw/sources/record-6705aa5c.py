"""Retain observed commands for the layer gap cluster, with scoped path export.

Receipt glue follows Python 3.12 subprocess/hashlib and the repository's existing
gap-wave receipt format. It does not interpret a result as gap closure.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time


ROOT = Path(__file__).resolve().parents[3]
ARTIFACTS = ROOT / "evidence/artifacts/backtesting-gap-burndown-20261010/us-equities__backtesting-engine/raw"


def exported(value):
    text = value.replace(str(Path.home()), "~")
    return re.sub(r"(?<![\w-])pytest-of-[\w.-]+", "pytest-of-<user>", text)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", required=True)
    parser.add_argument("--input", action="append", type=Path, default=[])
    parser.add_argument("--output-file", action="append", type=Path, default=[])
    parser.add_argument("--expected-exit", type=int, default=0)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    assert re.fullmatch(r"[a-z0-9-]+", args.id)
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    assert command
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    target = ARTIFACTS / (args.id + ".json")
    assert not target.exists(), "attempt names must be fresh"
    inputs = [{"path": exported(str(p.resolve())), "sha256": digest(p.read_bytes()), "bytes": p.stat().st_size}
              for p in args.input]
    before = datetime.now(timezone.utc).isoformat()
    start = time.monotonic()
    environment = {k: os.environ[k] for k in ("PATH", "HOME", "LANG", "LC_ALL") if k in os.environ}
    environment.update({"OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1", "DOTNET_CLI_TELEMETRY_OPTOUT": "1",
                        "DOTNET_SKIP_FIRST_TIME_EXPERIENCE": "1", "DOTNET_NOLOGO": "1", "DOTNET_PROCESSOR_COUNT": "1",
                        "DOTNET_CLI_HOME": str(ROOT / ".runtime/dotnet-home"), "NUGET_PACKAGES": str(ROOT / ".runtime/nuget")})
    if (ROOT / ".runtime/icu/usr/lib/x86_64-linux-gnu").is_dir():
        environment["LD_LIBRARY_PATH"] = str(ROOT / ".runtime/icu/usr/lib/x86_64-linux-gnu")
    base_python = (ROOT / ".venv/bin/python").resolve().parents[1]
    library = base_python / "lib/libpython3.12.so"
    if library.is_file() and Path(command[0]).name == "dotnet":
        environment["PYTHONNET_PYDLL"] = str(library)
        environment["PYTHONHOME"] = str(base_python)
    try:
        result = subprocess.run(command, cwd=ROOT, env=environment, capture_output=True, timeout=args.timeout)
        code, stdout, stderr = result.returncode, result.stdout, result.stderr
        launched = True
    except subprocess.TimeoutExpired as error:
        code, stdout, stderr, launched = 124, error.stdout or b"", error.stderr or b"", True
    except OSError as error:
        code, stdout, stderr, launched = 127, b"", type(error).__name__.encode(), False
    raw_outputs = []
    for label, data in (("stdout", stdout), ("stderr", stderr)):
        safe = exported(data.decode("utf8", errors="replace")).encode()
        path = ARTIFACTS / (args.id + "." + label + ".txt")
        with path.open("xb") as handle:
            handle.write(safe)
        raw_outputs.append({"path": str(path.relative_to(ROOT)), "raw_sha256": digest(data), "raw_bytes": len(data),
                            "sha256": digest(safe), "bytes": len(safe), "home_and_pytest_components_exported": True})
    outputs = []
    for path in args.output_file:
        if path.is_file():
            outputs.append({"path": exported(str(path.resolve())), "sha256": digest(path.read_bytes()),
                            "bytes": path.stat().st_size})
    receipt = {"schema_version": 1, "id": args.id, "command": [exported(v) for v in command],
               "started_utc": before, "finished_utc": datetime.now(timezone.utc).isoformat(),
               "duration_seconds": round(time.monotonic() - start, 3), "launched": launched,
               "observed_exit_code": code, "expected_exit_code": args.expected_exit,
               "expectation_met": code == args.expected_exit, "input_hashes": inputs,
               "captured_outputs": raw_outputs, "output_hashes": outputs,
               "input_bytes_unchanged": all(digest(p.read_bytes()) == row["sha256"] for p, row in zip(args.input, inputs)),
               "scope": "observed command result only; no automatic evidence-class or gap-status promotion"}
    with target.open("x") as handle:
        handle.write(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"receipt": str(target.relative_to(ROOT)), "exit_code": code,
                      "expectation_met": receipt["expectation_met"]}))
    return 0 if receipt["expectation_met"] and receipt["input_bytes_unchanged"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
