#!/usr/bin/env python3
"""Run E1 through promptfoo from a prepared root.

e1_run.py --root DIR (--preflight | --questions) [--arms A0b,A1] [--ids p-def,p-refs] [--repeats N] [--slot SLOT [--credential-runner PATH]] [--dry-run]

Checks the root against its manifest (the manifest's own shape, staged files, settings.json, tree heads and contents, the directive files), then starts `promptfoo eval` in <root>/config with one run at a time,
no cache, no sharing, no database write, the telemetry and update checks off, the state and temporary directories inside the root, and an environment without the variables that change a client session's model,
effort or credential route or promptfoo's exit status. The key is not read here: --slot starts promptfoo under tools/credentials/credential_run.py for that inventory entry; without it the caller's environment
must already hold the key. Results go to <root>/out/<stage>-<time>.json (e1_decide.py reads them).
--preflight runs the one `preflight` row per arm (servers connected, directive delivered). It passes only if promptfoo exited 0 and the result file shows every asked-for arm's row passed (e1_gate.py); the outcome
is recorded in <root>/out/preflight-<time>.gate either way. --questions runs the frozen questions (--repeats can be 1 to 3: the staged generator makes three) and starts promptfoo only if the newest pre-flight
record passed, belongs to this preparation of the root and covers the asked-for arms; it writes <result>.gate beside the result. --dry-run prints the command and the names of the variables it sets or removes,
and runs nothing. Exit 0 when promptfoo finished (it exits 100 when a test failed, which for the questions is a result, not a fault, and for the pre-flight a failed gate), 2 a refusal, else promptfoo's status.
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
import e1_gate as gate  # noqa: E402
from e1_prepare import MANIFEST, Refusal, run, sha256_file, validate_manifest  # noqa: E402

PROMPTFOO_FAILED_TESTS = 100


def verify_root(root):
    """The manifest of the prepare, and a refusal when anything it recorded has changed."""
    path = root / MANIFEST
    if not path.is_file():
        raise Refusal("the root holds no manifest.json: run e1_prepare.py first")
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        raise Refusal("manifest.json is not JSON: prepare again with --rebuild") from None
    problems = validate_manifest(manifest)
    if problems:
        raise Refusal(f"manifest.json is not a manifest of this harness ({problems[0]}): prepare again with --rebuild")
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
        if directive:   # git reports only the name of an untracked file, so the content is compared: with the digest the manifest recorded and with the staged directive (itself checked against the manifest above)
            live = sha256_file(tree / "CLAUDE.local.md")
            if live != manifest["directives"].get(name) or live != sha256_file(root / "config" / "directives" / f"{directive}.md"):
                raise Refusal(f"the directive file of tree {name} is not the {directive} paragraph that was prepared into this root: prepare again with --rebuild")
    return manifest


def build_env(root, manifest, environ):
    env = {k: v for k, v in environ.items() if k not in C.BEHAVIOUR_VARS and k not in C.EXIT_VARS}
    env.update({"E1_ROOT": str(root), "E1_CLAUDE": manifest["claude"]["path"], "E1_SEMBLE_MODEL": manifest["semble_model"], "TMPDIR": str(root / "tmp"),
                "CLAUDE_CODE_TMPDIR": str(root / "claude-tmp"), "PROMPTFOO_CONFIG_DIR": str(root / "promptfoo-state"), "PROMPTFOO_DISABLE_TELEMETRY": "1",
                "PROMPTFOO_DISABLE_UPDATE": "1", "PROMPTFOO_DISABLE_SHARING": "1", **C.CHILD_ENV})
    return env


def test_pattern(ids, repeats):
    names = "|".join(re.escape(i) for i in ids) if ids else "[^ ]+"
    return f"^(?:{names}) r[1-{repeats}]$"


def selected_arms(args):
    arms = args.arms.split(",") if args.arms else list(C.ARMS)
    unknown = [a for a in arms if a not in C.ARMS]
    if unknown:
        raise Refusal("unknown arm: " + ", ".join(unknown))
    return arms


def build_command(root, manifest, args, stamp):
    arms = selected_arms(args)
    stage = "preflight" if args.preflight else "questions"
    out = root / "out" / f"{stage}-{stamp}.json"
    cmd = [manifest["promptfoo"]["path"], "eval", "-c", str(root / "config" / "promptfooconfig.yaml"), "--no-cache", "--no-share", "--no-write", "--no-table", "--no-progress-bar",
           "--max-concurrency", "1", "-o", str(out), "--filter-providers", "^(" + "|".join(arms) + ")$", "--filter-metadata", "kind=" + ("preflight" if args.preflight else "question")]
    if args.questions:
        ids = args.ids.split(",") if args.ids else []
        known = {q["id"] for q in json.loads((root / "config" / "tasks.json").read_text(encoding="utf-8"))["questions"]}
        if set(ids) - known:
            raise Refusal("unknown question id: " + ", ".join(sorted(set(ids) - known)))
        if not 1 <= args.repeats <= C.GENERATED_REPEATS:
            raise Refusal(f"--repeats must be 1 to {C.GENERATED_REPEATS}: the staged generator makes {C.GENERATED_REPEATS} repeats of every question")
        cmd += ["--filter-pattern", test_pattern(ids, args.repeats)]
    if args.slot:
        runner = Path(os.path.abspath(args.credential_runner)) if args.credential_runner else (C.REPO_ROOT / "tools" / "credentials" / "credential_run.py" if C.REPO_ROOT else None)
        if runner is None or not Path(runner).is_file():
            raise Refusal("tools/credentials/credential_run.py was not found; pass --credential-runner")
        cmd = [sys.executable, "-I", str(runner), args.slot, "--", *cmd]   # absolute: promptfoo is started from <root>/config
    return cmd, out


def finish_preflight(root, out, arms, status, stamp):
    """Record the pre-flight's outcome and return the exit status: 0 only if promptfoo exited 0 and every asked-for row passed; promptfoo's own nonzero status otherwise; 100 when promptfoo said 0 and the
    result says the pre-flight failed."""
    path, passed, reasons = gate.record_preflight(root / "out", stamp, root / MANIFEST, arms, out, status)
    if passed:
        print(f"pre-flight passed for {','.join(arms)}; gate record: {path}", file=sys.stderr)
        return 0
    for reason in reasons:
        print(f"pre-flight failed: {reason}", file=sys.stderr)
    return status if status != 0 else PROMPTFOO_FAILED_TESTS


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run E1 through promptfoo from a prepared root.")
    parser.add_argument("--root", required=True, type=Path)
    stage = parser.add_mutually_exclusive_group(required=True)
    stage.add_argument("--preflight", action="store_true")
    stage.add_argument("--questions", action="store_true")
    parser.add_argument("--arms")
    parser.add_argument("--ids")
    parser.add_argument("--repeats", type=int, default=C.GENERATED_REPEATS)
    parser.add_argument("--slot")
    parser.add_argument("--credential-runner", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        root = Path(os.path.abspath(args.root))
        manifest = verify_root(root)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        cmd, out = build_command(root, manifest, args, stamp)
        arms = selected_arms(args)
        env = build_env(root, manifest, os.environ)
        preflight_record, gate_state = None, None
        if args.questions:
            try:
                preflight_record = gate.require_preflight(root, arms)
                gate_state = f"passed: {preflight_record.name}"
            except gate.GateError as error:
                if not args.dry_run:
                    raise Refusal(str(error)) from None
                gate_state = f"refused: {error}"
        if args.dry_run:
            plan = {"command": cmd, "sets": sorted(k for k in env if os.environ.get(k) != env[k]), "removes": sorted(k for k in C.BEHAVIOUR_VARS + C.EXIT_VARS if k in os.environ), "out": str(out)}
            if gate_state:
                plan["gate"] = gate_state
            print(json.dumps(plan, indent=1))
            return 0
        status = subprocess.run(cmd, cwd=root / "config", env=env, stdin=subprocess.DEVNULL).returncode
        print(f"promptfoo exited {status}; results: {out}", file=sys.stderr)
        if args.preflight:
            return finish_preflight(root, out, arms, status, stamp)   # exit 100 is "at least one test failed" (promptfoo@30949931ee90 site/docs/usage/command-line.md L171): for a pre-flight row that is a wiring defect, not a result
        if out.is_file():
            gate.write_questions_record(out, preflight_record, root / MANIFEST, arms, args.ids.split(",") if args.ids else [], args.repeats, status)
        return 0 if status in (0, PROMPTFOO_FAILED_TESTS) else status
    except Refusal as refusal:
        print(f"refused: {refusal}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
