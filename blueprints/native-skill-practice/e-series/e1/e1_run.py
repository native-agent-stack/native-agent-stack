#!/usr/bin/env python3
"""Run E1 through promptfoo from a prepared root.

e1_run.py --root DIR (--preflight | --questions) [--arms A0b,A1] [--ids p-def,p-refs] [--repeats N] [--slot SLOT [--credential-runner PATH]] [--dry-run]

Checks the root against its manifest (staged files, settings.json, tree heads and contents), then starts `promptfoo eval` in <root>/config with one run at a time, no cache, no sharing, no database write, the
telemetry and update checks off, the state and temporary directories inside the root, and an environment without the variables that change a client session's model, effort or credential route. The key is not
read here: --slot starts promptfoo under tools/credentials/credential_run.py for that inventory entry; without it the caller's environment must already hold the key. Results go to <root>/out/<stage>-<time>.json
(e1_decide.py reads them). --preflight runs the one `preflight` row per arm (servers connected, directive delivered); --questions runs the frozen questions. --dry-run prints the command and the names of the
variables it sets or removes, and runs nothing. Exit 0 when promptfoo finished (it exits 100 when a test failed, which is a result, not a fault), 2 a refusal, else promptfoo's status.
"""
import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import e1_common as C  # noqa: E402
from e1_prepare import MANIFEST, Refusal, run, sha256_file  # noqa: E402

PROMPTFOO_FAILED_TESTS = 100


def verify_root(root):
    """The manifest of the prepare, and a refusal when anything it recorded has changed."""
    path = root / MANIFEST
    if not path.is_file():
        raise Refusal("the root holds no manifest.json: run e1_prepare.py first")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if os.path.realpath(root) != os.path.realpath(manifest["root"]):
        raise Refusal(f"this root is {root} but the manifest recorded {manifest['root']}: the sandbox fence and the sibling paths are bound to the recorded path; prepare again with --rebuild")
    for name, digest in manifest["staged"].items():
        if not (root / "config" / name).is_file() or sha256_file(root / "config" / name) != digest:
            raise Refusal(f"staged file {name} no longer matches the manifest: prepare again with --rebuild")
    if sha256_file(root / "settings.json") != manifest["settings_sha256"]:
        raise Refusal("settings.json no longer matches the manifest: prepare again with --rebuild")
    for name, (commit, directive) in C.TREES.items():
        tree = root / "trees" / name
        if run(["git", "-C", str(tree), "rev-parse", "HEAD"]).strip() != manifest["trees"][name]:
            raise Refusal(f"tree {name} is not at the commit the manifest recorded")
        untracked = sorted(line for line in run(["git", "-C", str(tree), "status", "--porcelain", "--untracked-files=all"]).splitlines())
        if untracked != (["?? CLAUDE.local.md"] if directive else []):
            raise Refusal(f"tree {name} has changes or files beyond what prepare put there: {untracked[:3]}")
    return manifest


def build_env(root, manifest, environ):
    env = {k: v for k, v in environ.items() if k not in C.BEHAVIOUR_VARS}
    env.update({"E1_ROOT": str(root), "E1_CLAUDE": manifest["claude"]["path"], "E1_SEMBLE_MODEL": manifest["semble_model"], "TMPDIR": str(root / "tmp"),
                "CLAUDE_CODE_TMPDIR": str(root / "claude-tmp"), "PROMPTFOO_CONFIG_DIR": str(root / "promptfoo-state"), "PROMPTFOO_DISABLE_TELEMETRY": "1",
                "PROMPTFOO_DISABLE_UPDATE": "1", "PROMPTFOO_DISABLE_SHARING": "1", **C.CHILD_ENV})
    return env


def test_pattern(ids, repeats):
    names = "|".join(re.escape(i) for i in ids) if ids else "[^ ]+"
    return f"^(?:{names}) r[1-{repeats}]$"


def build_command(root, manifest, args, stamp):
    arms = args.arms.split(",") if args.arms else list(C.ARMS)
    unknown = [a for a in arms if a not in C.ARMS]
    if unknown:
        raise Refusal("unknown arm: " + ", ".join(unknown))
    stage = "preflight" if args.preflight else "questions"
    out = root / "out" / f"{stage}-{stamp}.json"
    cmd = [manifest["promptfoo"]["path"], "eval", "-c", str(root / "config" / "promptfooconfig.yaml"), "--no-cache", "--no-share", "--no-write", "--no-table", "--no-progress-bar",
           "--max-concurrency", "1", "-o", str(out), "--filter-providers", "^(" + "|".join(arms) + ")$", "--filter-metadata", "kind=" + ("preflight" if args.preflight else "question")]
    if args.questions:
        ids = args.ids.split(",") if args.ids else []
        known = {q["id"] for q in json.loads((C.HERE / "tasks.json").read_text(encoding="utf-8"))["questions"]}
        if set(ids) - known:
            raise Refusal("unknown question id: " + ", ".join(sorted(set(ids) - known)))
        if not 1 <= args.repeats <= 9:
            raise Refusal("--repeats must be 1 to 9")
        cmd += ["--filter-pattern", test_pattern(ids, args.repeats)]
    if args.slot:
        runner = args.credential_runner or (C.REPO_ROOT / "tools" / "credentials" / "credential_run.py" if C.REPO_ROOT else None)
        if runner is None or not Path(runner).is_file():
            raise Refusal("tools/credentials/credential_run.py was not found; pass --credential-runner")
        cmd = [sys.executable, "-I", str(runner), args.slot, "--", *cmd]
    return cmd, out


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run E1 through promptfoo from a prepared root.")
    parser.add_argument("--root", required=True, type=Path)
    stage = parser.add_mutually_exclusive_group(required=True)
    stage.add_argument("--preflight", action="store_true")
    stage.add_argument("--questions", action="store_true")
    parser.add_argument("--arms")
    parser.add_argument("--ids")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--slot")
    parser.add_argument("--credential-runner", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        root = Path(os.path.abspath(args.root))
        manifest = verify_root(root)
        cmd, out = build_command(root, manifest, args, datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
        env = build_env(root, manifest, os.environ)
        if args.dry_run:
            print(json.dumps({"command": cmd, "sets": sorted(k for k in env if os.environ.get(k) != env[k]), "removes": sorted(k for k in C.BEHAVIOUR_VARS if k in os.environ), "out": str(out)}, indent=1))
            return 0
        status = subprocess.run(cmd, cwd=root / "config", env=env, stdin=subprocess.DEVNULL).returncode
        print(f"promptfoo exited {status}; results: {out}", file=sys.stderr)
        if args.preflight:
            return status           # exit 100 is "at least one test failed" (promptfoo@30949931ee90 site/docs/usage/command-line.md L171): for a pre-flight row that is a wiring defect, not a result
        return 0 if status in (0, PROMPTFOO_FAILED_TESTS) else status
    except Refusal as refusal:
        print(f"refused: {refusal}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
