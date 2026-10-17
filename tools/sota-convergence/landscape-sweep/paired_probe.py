#!/usr/bin/env python3
"""Paired before/after probe of the opt-in Codex lane hardening (codex_job.py, build_args.py). STAGED, NOT RUN.

  paired_probe.py --lane DIR --pr-checkout DIR --scratch DIR [--pairs 3] [--prompt FILE --schema FILE]
                  [--build-flags="FLAGS"] [--hardening-flags="FLAGS"]            print the plan; nothing is copied or run
  paired_probe.py ... --run --gpt-capacity-confirmed                              copy, restage and run the six jobs

The probe waits for GPT capacity. It was written while the native account sat at its usage limit and the OmniRoute
gateway was down, so it has never been run and its first run is the first measurement. Without --run it only prints the
plan, so reading it costs nothing. --run needs --gpt-capacity-confirmed as well: confirm by hand that the lane's route
answers (a one-line `codex_call.sh` probe on a spare copy) before passing it.

What it does, never touching the lane itself (the lane stays on its own harness copy until the change lands):
  1. Copies the lane work directory without gpt6/, locks/, LIMIT markers and codex-home/sessions into <scratch>/before and
     <scratch>/after. BEFORE is the lane as it is; check that its staged codex_job.py is origin/main's before reading
     numbers (the lane's staged.json records harness.files.codex_job.py).
  2. Restages AFTER with the change's build_args.py (--pr-checkout) and `--force`, with the lane's own build flags
     (--build-flags="...", one shell-quoted string, e.g. --gpt6-provider omniroute --codex-host /path/to/host.json --gpt6-model cx/gpt-6.1-sol
     --slots 2) plus the hardening flags (--hardening-flags="...", the same form, e.g. --codex-hook rtk --codex-hook secret_guard
     --codex-disable-feature apps --web-search disabled --codex-otel-endpoint 127.0.0.1:23318 --rollout-usage
     --ai-memory-bearer-env). Pass a gateway host file by path: real hosts' files are gitignored and exist only in the
     main checkout.
  3. Runs B1 A1 B2 A2 B3 A3 back to back, a fresh job id each (a reused id with the same inputs returns "already done"),
     the same prompt and schema (default: the lane's own prompts/gpt6-probe.txt and schemas/probe.json), and prints every
     row of `codex_call.sh result` usage. No average is computed: three pairs do not support one.

What the default probe can and cannot show: the prompt asks for web search and runs few shell commands, so it shows
tool-definition changes (--disable apps) and prefix changes, not RTK's output compression and not the guard. For those
pass a shell-heavy --prompt (a finished read job's own prompt.txt with a fresh id, or a small "list and read ten files"
prompt) and say in the report that the jobs differ in work done even with the same prompt. Such a re-run is a probe, not a
review: do not use its verdict as an independent read.

Checks to run in the same session (not automated here; each needs Codex): `codex app-server` `hooks/list` on a scratch
copy of each Codex home with the identical -c flags must show trustStatus "trusted" for every registered entry
(including the session-flags guard key); one record tagged env=<lane>-<job id> must reach the loopback collector with no
content stored; zero mcp__codex_apps__* tools in an --disable apps job; the LIMIT markers must stay absent.
Standard library only; Python 3.9+.
"""

from __future__ import annotations

import argparse
import json
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

COPY_IGNORE = shutil.ignore_patterns("gpt6", "locks", "sessions", "LIMIT", "LIMIT-native")
ARMS = ("before", "after")
USAGE_KEYS = ("input_tokens", "cached_input_tokens", "cache_write_input_tokens", "output_tokens",
              "reasoning_output_tokens")


def plan(args: argparse.Namespace) -> list[tuple[str, list]]:
    """The ordered (label, command) steps; pure, so the plan can be printed without running anything."""
    lane, scratch = Path(args.lane).resolve(), Path(args.scratch).resolve()
    pr = Path(args.pr_checkout).resolve()
    staged = json.loads((lane / "staged.json").read_text(encoding="utf-8"))
    steps = [(f"copy the lane to {scratch / arm}", ["copytree", str(lane), str(scratch / arm)]) for arm in ARMS]
    steps.append(("restage the after arm with the change", [
        sys.executable, str(pr / "tools" / "sota-convergence" / "landscape-sweep" / "build_args.py"),
        "--work-dir", str(scratch / "after"), "--sweep-id", staged["sweep_id"], "--date", staged["date"], "--force",
        "--repo-root", str(pr), *shlex.split(args.build_flags), *shlex.split(args.hardening_flags)]))
    for pair in range(1, args.pairs + 1):
        for arm in ARMS:
            steps.append((f"{arm[0].upper()}{pair}: one job in the {arm} arm", ["job", arm, f"paired-{arm}-{pair}"]))
    return steps


def codex_call(work: Path, *rest: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(work / "codex_job.py"), "--work-dir", str(work), *rest],
                          capture_output=True, text=True, check=False)


def run_job(work: Path, job: str, prompt: Path, schema: Path) -> dict:
    started = codex_call(work, "start", job, str(prompt), str(schema))
    if started.returncode != 0:
        return {"job": job, "error": f"start exit {started.returncode}: {(started.stderr or started.stdout).strip()[-200:]}"}
    while True:
        waited = codex_call(work, "wait", job, "540")
        if waited.stdout.startswith("done"):
            break
    result = json.loads(codex_call(work, "result", job).stdout)
    row = {"job": job, "exit": result.get("exit"), "usage_status": result.get("usage_status"),
           "events": None, **{key: (result.get("usage") or {}).get(key) for key in USAGE_KEYS}}
    events = work / "gpt6" / job / "events.jsonl"
    if events.is_file():
        row["events"] = sum(1 for line in events.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip())
    if result.get("rollout_usage"):
        row["rollout_usage_status"] = result["rollout_usage"].get("status")
    return row


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0],
                                     formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    parser.add_argument("--lane", required=True, help="the lane work directory (read only: it is copied)")
    parser.add_argument("--pr-checkout", required=True, help="a checkout holding the change (its build_args.py restages)")
    parser.add_argument("--scratch", required=True, help="an empty directory outside the lane for the two arms")
    parser.add_argument("--pairs", type=int, default=3)
    parser.add_argument("--prompt", help="default <lane>/prompts/gpt6-probe.txt")
    parser.add_argument("--schema", help="default <lane>/schemas/probe.json")
    parser.add_argument("--build-flags", default="", help='the lane\'s build_args.py flags as one string, passed as --build-flags="..."')
    parser.add_argument("--hardening-flags", default="", help='the hardening flags as one string, passed as --hardening-flags="..."')
    parser.add_argument("--run", action="store_true", help="copy, restage and run; the default only prints the plan")
    parser.add_argument("--gpt-capacity-confirmed", action="store_true",
                        help="required with --run: the lane's route is known to have capacity")
    args = parser.parse_args(argv)
    lane, scratch = Path(args.lane).resolve(), Path(args.scratch).resolve()
    if not (lane / "staged.json").is_file():
        print("paired_probe.py: --lane holds no staged.json", file=sys.stderr)
        return 2
    if scratch == lane or lane in scratch.parents or scratch in lane.parents:
        print("paired_probe.py: --scratch must be outside the lane (and not hold it)", file=sys.stderr)
        return 2
    if args.pairs < 1:
        print("paired_probe.py: --pairs must be at least 1", file=sys.stderr)
        return 2
    steps = plan(args)
    if not args.run:
        print("PLAN ONLY (nothing copied, restaged or run); --run --gpt-capacity-confirmed starts the jobs")
        for label, command in steps:
            print(f"- {label}\n    {' '.join(shlex.quote(part) for part in command)}")
        return 0
    if not args.gpt_capacity_confirmed:
        print("paired_probe.py: --run needs --gpt-capacity-confirmed (the probe waits for GPT capacity)", file=sys.stderr)
        return 2
    if scratch.exists() and any(scratch.iterdir()):
        print("paired_probe.py: --scratch must be empty", file=sys.stderr)
        return 2
    prompt = Path(args.prompt) if args.prompt else lane / "prompts" / "gpt6-probe.txt"
    schema = Path(args.schema) if args.schema else lane / "schemas" / "probe.json"
    rows = []
    for label, command in steps:
        print(label, flush=True)
        if command[0] == "copytree":
            shutil.copytree(command[1], command[2], ignore=COPY_IGNORE, symlinks=True)
        elif command[0] == "job":
            rows.append({"arm": command[1], **run_job(scratch / command[1], command[2], prompt, schema)})
            print(json.dumps(rows[-1], sort_keys=True), flush=True)
        else:
            done = subprocess.run(command, capture_output=True, text=True, check=False)
            if done.returncode != 0:
                print(f"paired_probe.py: restaging failed: {(done.stderr or done.stdout).strip()[-300:]}", file=sys.stderr)
                return 2
    (scratch / "rows.jsonl").write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    print(f"rows written to {scratch / 'rows.jsonl'}; no average is computed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
