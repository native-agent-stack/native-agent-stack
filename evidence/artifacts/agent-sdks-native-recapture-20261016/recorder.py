"""One recorded step of an F1 upstream_e2e recipe (CC FINALIZE-ALL, 2026-10-14). The arm runs every recipe command through
this wrapper, so a receipt's phases and exit codes come from the harness, never from the model's report.

  python3 f1_step.py <arm dir> <phase> [--cwd <dir under the arm dir>] -- <command> [args...]

Runs the command (argv, no shell; for a pipeline pass `bash -c '<text>'` explicitly), with its stdout and stderr in
<arm dir>/logs/<n>-<phase>.log, and appends one JSON line to <arm dir>/steps.jsonl: n, phase, command (the argv joined as
shell words), cwd relative to the arm dir, exit_code, started and ended (UTC), seconds, log path and log sha256. Prints only
`step <n> <phase> exit <code> log <path>`. Its own exit code is the command's. The phase must be a word of letters, digits,
dashes or underscores; the cwd must stay under the arm dir."""
import datetime as dt
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main(argv) -> int:
    if len(argv) < 4 or "--" not in argv:
        print("usage: f1_step.py <arm dir> <phase> [--cwd DIR] -- <command> [args...]", file=sys.stderr)
        return 2
    split = argv.index("--")
    head, command = argv[:split], argv[split + 1:]
    arm, phase = Path(head[0]).resolve(), head[1]
    cwd = arm / "work"
    if len(head) == 4 and head[2] == "--cwd":
        cwd = Path(head[3]).resolve()
    elif len(head) != 2:
        print("refused: unexpected arguments before --", file=sys.stderr)
        return 2
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", phase) or not command:
        print("refused: the phase must be a short word and a command is required", file=sys.stderr)
        return 2
    if not cwd.is_relative_to(arm):
        print("refused: --cwd must stay under the arm dir", file=sys.stderr)
        return 2
    (arm / "logs").mkdir(parents=True, exist_ok=True)
    cwd.mkdir(parents=True, exist_ok=True)
    steps = arm / "steps.jsonl"
    n = sum(1 for _ in steps.open()) + 1 if steps.exists() else 1
    log = arm / "logs" / f"{n:03d}-{phase}.log"
    started, t0 = now(), time.time()
    with open(log, "wb") as handle:
        try:
            code = subprocess.run(command, cwd=cwd, stdout=handle, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                  check=False).returncode
        except FileNotFoundError:
            handle.write(f"f1_step: command not found: {command[0]}\n".encode())
            code = 127
    row = {"n": n, "phase": phase, "command": shlex.join(command), "cwd": str(cwd.relative_to(arm)) or ".",
           "exit_code": code, "started": started, "ended": now(), "seconds": round(time.time() - t0, 1),
           "log": str(log.relative_to(arm)), "log_sha256": hashlib.sha256(log.read_bytes()).hexdigest()}
    with steps.open("a") as handle:
        handle.write(json.dumps(row) + "\n")
    print(f"step {n} {phase} exit {code} log {log}")
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
