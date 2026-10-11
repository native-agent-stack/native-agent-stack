#!/usr/bin/env python3
"""Run each installed token tool's own report command and publish token-tools-now.json.

The CC's hourly_usage_refresh.sh calls this beside its existing token-window
record; the command-center page reads the result under its exact
source_policy.json grant. Each row keeps the tool's command, exit code, run
time, version and its own estimate; nothing is summed across tools. Commands
and flags were read from each tool's --help at the installed version on
2026-10-11:

- RTK 0.51.0 `rtk gain --format json` (--format text|json|csv); the summary
  object is the tool's lifetime estimate on this host.
- Headroom 0.40.0 `headroom agent-savings --check-perf --hours 24 --format json`
  checks proxy logs against the profile target and exits 1 below it, and
  `headroom output-savings`, whose help says output savings are counterfactual
  unless an A/B holdout is set (HEADROOM_OUTPUT_HOLDOUT>0).
- context-mode 1.0.169 `node <plugin>/cli.bundle.mjs doctor`. Its savings are
  the MCP tool ctx_stats; `statusline` prints a fixed headline when it has no
  session (bin/statusline.mjs:236-242), so it is not used.

Text and JSON pass the shared page sanitizer before they are written, so the
file carries no home path, session id or email address.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "token-tools-now/1"
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
CHECK = re.compile(r"\b(PASS|FAIL|WARN|SKIP)\b")
# Headroom's own guards for read-only reports: no update check, offline, no telemetry.
QUIET = {"HEADROOM_UPDATE_CHECK": "off", "HEADROOM_OFFLINE": "1", "DO_NOT_TRACK": "1"}


def _sanitizer():
    spec = importlib.util.spec_from_file_location("token_tools_sanitization", Path(__file__).with_name("sanitization.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SANITIZE = _sanitizer()


def utc(stamp: float | None = None) -> str:
    return datetime.fromtimestamp(time.time() if stamp is None else stamp, timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def clean(value: str, limit: int = 1200) -> str:
    """Strip terminal escapes, keep the last useful lines and sanitize; never more than limit characters."""
    lines = [line.strip() for line in ANSI.sub("", value).splitlines() if line.strip()]
    return SANITIZE.text("\n".join(lines))[-limit:]


def run(argv: list[str], *, timeout: int, runner=subprocess.run) -> dict:
    started = time.time()
    try:
        result = runner(argv, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout,
                        env=dict(os.environ, **QUIET), check=False)
    except FileNotFoundError:
        error = "command not found"
    except subprocess.TimeoutExpired:
        error = f"timed out after {timeout} s"
    except OSError as failure:
        error = "could not start (" + type(failure).__name__ + ")"
    else:
        return {"rc": result.returncode, "started_utc": utc(started), "seconds": round(time.time() - started, 2), "stdout": result.stdout, "stderr": result.stderr}
    return {"rc": None, "started_utc": utc(started), "seconds": round(time.time() - started, 2), "error": error, "stdout": "", "stderr": ""}


def version(argv: list[str], *, runner=subprocess.run) -> str | None:
    outcome = run(argv, timeout=30, runner=runner)
    lines = clean(outcome["stdout"] or outcome["stderr"], 80).splitlines() if outcome["rc"] == 0 else []
    return lines[0] if lines else None


def row(tool: str, command: list[str], label: str, outcome: dict, tool_version: str | None, estimate: dict | None, *, note: str | None = None) -> dict:
    message = clean(outcome.get("stderr") or "", 400) if outcome.get("rc") not in (0, None) else None
    return {"tool": tool, "command": " ".join(command), "label": label, "version": tool_version, "rc": outcome.get("rc"),
            "started_utc": outcome.get("started_utc"), "seconds": outcome.get("seconds"), "error": outcome.get("error"),
            "estimate": SANITIZE.sanitize(estimate) if estimate is not None else None, "message": message, "note": note}


def rtk(executable: str, *, timeout: int, runner=subprocess.run) -> dict:
    command = [executable, "gain", "--format", "json"]
    outcome = run(command, timeout=timeout, runner=runner)
    estimate = None
    if outcome["rc"] == 0:
        try:
            summary = json.loads(outcome["stdout"]).get("summary")
        except (ValueError, AttributeError):
            summary = None
        if isinstance(summary, dict):
            estimate = {key: summary[key] for key in ("total_saved", "avg_savings_pct", "total_commands", "total_input", "total_output") if key in summary}
    return row("RTK", ["rtk", "gain", "--format", "json"], "lifetime on this host, the tool's own estimate", outcome, version([executable, "--version"], runner=runner), estimate)


def headroom_agent(executable: str, *, timeout: int, runner=subprocess.run) -> dict:
    command = [executable, "agent-savings", "--check-perf", "--hours", "24", "--format", "json"]
    outcome = run(command, timeout=timeout, runner=runner)
    estimate = None
    if outcome["rc"] == 0 and outcome["stdout"].strip():
        try:
            parsed = json.loads(outcome["stdout"])
            estimate = parsed if isinstance(parsed, dict) else None
        except ValueError:
            estimate = None
    return row("Headroom", ["headroom", "agent-savings", "--check-perf", "--hours", "24", "--format", "json"], "proxy logs of the last 24 h against the profile target", outcome,
               version([executable, "--version"], runner=runner), estimate, note="exits 1 when savings fall below the profile target")


def headroom_output(executable: str, *, timeout: int, runner=subprocess.run) -> dict:
    command = [executable, "output-savings"]
    outcome = run(command, timeout=timeout, runner=runner)
    summary = clean(outcome["stdout"], 600) if outcome["rc"] == 0 else None
    return row("Headroom", ["headroom", "output-savings"], "output-token reduction from the shaper", outcome, version([executable, "--version"], runner=runner),
               {"report": summary} if summary else None, note="counterfactual unless an A/B holdout is set (HEADROOM_OUTPUT_HOLDOUT>0)")


def context_mode(node: str, cli: Path | None, *, timeout: int, runner=subprocess.run) -> dict:
    if cli is None:
        return row("context-mode", ["context-mode", "doctor"], "runtime, hooks and storage checks", {"rc": None, "error": "not run: no --context-mode-cli given"}, None, None,
                   note="savings are the MCP tool ctx_stats; there is no CLI report")
    outcome = run([node, str(cli), "doctor"], timeout=timeout, runner=runner)
    checks: dict[str, int] = {}
    for line in ANSI.sub("", outcome["stdout"]).splitlines():
        match = CHECK.search(line)
        if match:
            checks[match.group(1)] = checks.get(match.group(1), 0) + 1
    try:
        tool_version = json.loads((cli.parent / "package.json").read_text()).get("version")
    except (OSError, ValueError, AttributeError):
        tool_version = None
    return row("context-mode", ["context-mode", "doctor"], "runtime, hooks and storage checks", outcome, f"context-mode {tool_version}" if tool_version else None,
               {"checks": checks} if outcome["rc"] == 0 else None, note="savings are the MCP tool ctx_stats; there is no CLI report")


def collect(rtk_bin: str, headroom_bin: str, node: str, context_cli: Path | None, *, timeout: int = 120, runner=subprocess.run) -> dict:
    tools = [rtk(rtk_bin, timeout=timeout, runner=runner), headroom_agent(headroom_bin, timeout=timeout, runner=runner),
             headroom_output(headroom_bin, timeout=timeout, runner=runner), context_mode(node, context_cli, timeout=timeout, runner=runner)]
    return {"schema": SCHEMA, "generated_utc": utc(), "tools": tools}


def destination(path: Path) -> Path:
    """The report is local state: refuse a destination inside the repository."""
    path = Path(os.path.abspath(path))
    if path == ROOT or ROOT in path.parents:
        raise ValueError("--out must stay outside the repository")
    return path


def publish(path: Path, document: dict) -> None:
    path = destination(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".token-tools-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(document, stream, indent=2, sort_keys=True, ensure_ascii=False)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", required=True, type=Path, help="token-tools-now.json destination, outside the repository")
    parser.add_argument("--rtk", default="rtk")
    parser.add_argument("--headroom", default="headroom")
    parser.add_argument("--node", default="node")
    parser.add_argument("--context-mode-cli", type=Path, help="the context-mode plugin's cli.bundle.mjs")
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args(argv)
    try:
        destination(args.out)
        publish(args.out, collect(args.rtk, args.headroom, args.node, args.context_mode_cli, timeout=args.timeout))
    except (OSError, ValueError) as error:
        print(f"token_tools_now: {type(error).__name__}: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
