#!/usr/bin/env python3
"""Prepare the root directory an E1 promptfoo run needs.

e1_prepare.py --root DIR --claude PATH --semble-model DIR [--repo DIR] [--promptfoo PATH] [--sdk-from DIR] [--rebuild] [--dry-run]

Builds under DIR: trees/ (four detached shared clones: the base commit, the base commit with the serena paragraph in CLAUDE.local.md, the stale commit, the stale commit with the path paragraph),
settings.json (the runner's sandbox and permission fence), config/ (a copy of this directory's staged files with the SDK package beside them, the directory promptfoo runs from), the empty tmp/, claude-tmp/,
cache/, out/ and promptfoo-state/ directories, and manifest.json (commits, tree heads, tool versions, the sha256 of every staged file and of settings.json). e1_run.py refuses to start when a staged file
no longer matches the manifest. --claude is the versioned client binary (2.1.296), not the wrapper on PATH. --sdk-from links an existing @anthropic-ai/claude-agent-sdk 0.3.283 (the copy promptfoo
bundles); without it the script runs `npm install` for that version, the route promptfoo's provider page documents.
The root must be outside the repository and outside $HOME (the fence denies reading $HOME), and must be new, empty, or an earlier root of this script: a directory is one only if its manifest.json is a
manifest of this harness (validate_manifest), and replacing it takes --rebuild, which replaces its trees and config and keeps out/ (each result file there is bound to the preparation that produced it by
e1_gate.py, so a rebuild does not let an older generation's files be decided with a newer one's). Any other non-empty directory is refused, with or without --rebuild, and left as it was. Nothing here calls
a model or reads a key. Exit 0 prepared, 2 a refusal with the reason on stderr.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import e1_common as C  # noqa: E402

MANIFEST = "manifest.json"
WORK_DIRS = ("tmp", "claude-tmp", "cache", "out", "promptfoo-state")


class Refusal(Exception):
    pass


def run(cmd, cwd=None):
    try:
        return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError) as error:
        detail = (getattr(error, "stderr", "") or "").strip().splitlines()[-1:] or [str(error)]
        raise Refusal(f"{' '.join(str(c) for c in cmd[:3])} failed: {detail[0][:200]}") from None


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def version_tuple(text):
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", text)
    return tuple(int(x) for x in match.groups()) if match else None


def is_inside(path, parent):
    try:
        Path(path).resolve().relative_to(Path(parent).resolve())
        return True
    except ValueError:
        return False


def validate_manifest(manifest):
    """The reasons `manifest` is not the manifest of a root this harness prepared (an empty list when it is): the marker and the schema, and the shape of every field a later step reads."""
    if not isinstance(manifest, dict):
        return ["it is not a JSON object"]
    sha, commit = re.compile(r"[0-9a-f]{64}"), re.compile(r"[0-9a-f]{40}")
    problems = []

    def keyed(name, keys, pattern=None, optional=False):
        value = manifest.get(name)
        if not isinstance(value, dict) or set(value) != set(keys):
            problems.append(f"it records no {name} for exactly {sorted(keys)}" if not optional else f"its {name} do not match")
        elif pattern and not all(isinstance(v, str) and pattern.fullmatch(v) for v in value.values()):
            problems.append(f"a {name} entry is not a digest")
    if manifest.get("harness") != C.HARNESS:
        problems.append("it does not name this harness")
    if manifest.get("schema") != C.MANIFEST_SCHEMA:
        problems.append(f"its schema is not {C.MANIFEST_SCHEMA}")
    if not isinstance(manifest.get("root"), str) or not isinstance(manifest.get("generation"), str):
        problems.append("it records no root or generation")
    keyed("commits", ("base", "stale"), commit)
    keyed("trees", tuple(C.TREES), commit)
    keyed("staged", tuple(C.STAGED_FILES), sha)
    keyed("directives", tuple(name for name, (_, directive) in C.TREES.items() if directive), sha)
    if not isinstance(manifest.get("settings_sha256"), str) or not sha.fullmatch(manifest["settings_sha256"]):
        problems.append("it records no digest of settings.json")
    for name in ("claude", "promptfoo"):
        value = manifest.get(name)
        if not isinstance(value, dict) or not isinstance(value.get("path"), str) or not isinstance(value.get("version"), str):
            problems.append(f"it records no {name} path and version")
    if not isinstance(manifest.get("semble_model"), str) or not isinstance(manifest.get("servers"), dict):
        problems.append("it records no semble model or servers")
    return problems


def owner_problems(root):
    """Why `root` (a non-empty directory) is not a root of this harness, or an empty list when its manifest.json is a manifest of this harness."""
    try:
        manifest = json.loads((root / MANIFEST).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ["it holds no readable manifest.json"]
    return validate_manifest(manifest)


def check_root(root, repo, home, rebuild=False):
    if not root.is_absolute() or Path(os.path.realpath(root)) != root:
        raise Refusal("the root must be an absolute path with no symbolic link in it")
    if is_inside(root, repo):
        raise Refusal("the root is inside the repository")
    if is_inside(root, home):
        raise Refusal("the root is inside $HOME, which the fence denies reading")
    if not root.exists():
        return
    if not root.is_dir():
        raise Refusal("the root exists and is not a directory")
    if not any(root.iterdir()):
        return
    problems = owner_problems(root)
    if problems:   # a file named manifest.json does not make a directory ours: nothing in a directory that is not a root of this harness is changed, with or without --rebuild
        raise Refusal(f"the root exists, is not empty and is not a root of this harness ({problems[0]}); nothing was changed")
    if not rebuild:
        raise Refusal("the root already holds a prepared E1 root; pass --rebuild to replace its trees, config and manifest")


def settings_for(root, home):
    """The runner's fence: Bash in the sandbox with no network and $HOME and every other entry of the directory the root lives in unreadable, no edit tool, the server tools and ToolSearch allowed."""
    siblings = sorted(str(c) for c in root.parent.iterdir() if c != root)
    deny_read = sorted({str(home), *siblings})
    return {
        "permissions": {"allow": ["Bash", *[f"mcp__{s}" for s in C.SERVERS], "ToolSearch"],
                        "deny": ["Read(/" + str(home) + "/**)", "Edit(/" + str(home) + "/**)", *["Read(/" + s + "/**)" for s in siblings], "Read(//tmp/**)", "Read(//root/**)"]},
        "sandbox": {"enabled": True, "failIfUnavailable": True, "allowUnsandboxedCommands": False, "autoAllowBashIfSandboxed": True,
                    "filesystem": {"denyRead": deny_read, "allowRead": []}, "network": {"allowedDomains": [], "strictAllowlist": True}},
    }


def build_tree(repo, dest, commit, directive):
    run(["git", "clone", "-q", "--shared", "--no-checkout", str(repo), str(dest)])
    run(["git", "-C", str(dest), "checkout", "-q", "--detach", commit])
    if directive:
        (dest / "CLAUDE.local.md").write_text((C.HERE / "directives" / f"{directive}.md").read_text(encoding="utf-8"), encoding="utf-8")
    return run(["git", "-C", str(dest), "rev-parse", "HEAD"]).strip()


def stage_config(root, sdk_from):
    config = root / "config"
    shutil.rmtree(config, ignore_errors=True)
    for name in C.STAGED_FILES:
        (config / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(C.HERE / name, config / name)
    if sdk_from:
        link = config / "node_modules" / "@anthropic-ai" / "claude-agent-sdk"
        link.parent.mkdir(parents=True)
        link.symlink_to(Path(sdk_from).resolve())
        return "link"
    run(["npm", "install", "--no-save", "--no-package-lock", "--no-audit", "--no-fund", "--prefix", str(config), f"@anthropic-ai/claude-agent-sdk@{C.SDK_VERSION}"])
    return "npm"


def checks(args, repo, tasks):
    """Every refusal that needs no write; returns what the manifest records about the tools."""
    claude = Path(os.path.abspath(args.claude))      # absolute: e1_run.py starts promptfoo from <root>/config
    if not claude.is_file() or not os.access(claude, os.X_OK):
        raise Refusal("--claude is not an executable file")
    reported = run([str(claude), "--version"]).strip()
    if version_tuple(reported) != version_tuple(C.CLIENT_VERSION):
        raise Refusal(f"--claude reports {reported!r}, the preregistered client is {C.CLIENT_VERSION}")
    semble = Path(os.path.abspath(args.semble_model))
    if not semble.is_dir():
        raise Refusal("--semble-model is not a directory")
    promptfoo = args.promptfoo or shutil.which("promptfoo")
    if not promptfoo:
        raise Refusal("promptfoo is not on PATH; pass --promptfoo")
    promptfoo = os.path.abspath(promptfoo)
    pf_text = run([promptfoo, "--version"])
    pf_version = next((line.strip() for line in pf_text.splitlines() if re.fullmatch(r"\d+\.\d+\.\d+", line.strip())), None)
    if pf_version is None or version_tuple(pf_version) < version_tuple(C.PROMPTFOO_MINIMUM):
        raise Refusal(f"promptfoo {pf_version or 'of unknown version'} is older than {C.PROMPTFOO_MINIMUM}, which has copy_working_dir")
    if args.sdk_from:
        try:
            package = json.loads((Path(args.sdk_from) / "package.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise Refusal("--sdk-from holds no readable package.json") from None
        if package.get("version") != C.SDK_VERSION:
            raise Refusal(f"--sdk-from holds {package.get('name')} {package.get('version')}, not {C.SDK_VERSION}")
    elif not shutil.which("npm"):
        raise Refusal("npm is not on PATH; install the SDK with --sdk-from DIR instead")
    servers = {}
    for name, command in C.SERVER_COMMANDS.items():
        found = shutil.which(command)
        if not found:
            raise Refusal(f"the {name} server executable `{command}` is not on PATH")
        servers[name] = found
    for key in ("base", "stale"):
        if subprocess.run(["git", "-C", str(repo), "cat-file", "-e", tasks[key] + "^{commit}"], capture_output=True).returncode != 0:
            raise Refusal(f"the {key} commit {tasks[key][:12]} is not in {repo}")
    return {"claude": {"path": str(claude), "version": reported}, "promptfoo": {"path": promptfoo, "version": pf_version}, "semble_model": str(semble), "servers": servers}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Prepare the root directory an E1 promptfoo run needs.")
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--claude", required=True)
    parser.add_argument("--semble-model", required=True)
    parser.add_argument("--repo", type=Path, default=C.REPO_ROOT)
    parser.add_argument("--promptfoo")
    parser.add_argument("--sdk-from", type=Path)
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    home = Path.home()
    try:
        if args.repo is None:
            raise Refusal("--repo is required: this copy of the scripts is not inside the repository")
        root, repo = Path(os.path.abspath(args.root)), args.repo.resolve()
        tasks = json.loads((C.HERE / "tasks.json").read_text(encoding="utf-8"))
        check_root(root, repo, home, args.rebuild)
        tools = checks(args, repo, tasks)
        if args.dry_run:
            print(json.dumps({"dry_run": True, "root": str(root), "trees": sorted(C.TREES), "tools": {k: tools[k] for k in ("claude", "promptfoo")}}, indent=1))
            return 0
        root.mkdir(parents=True, exist_ok=True)
        for name in ("trees", "config"):
            shutil.rmtree(root / name, ignore_errors=True)
        (root / "trees").mkdir()
        heads = {name: build_tree(repo, root / "trees" / name, tasks[commit], directive) for name, (commit, directive) in C.TREES.items()}
        for name in WORK_DIRS:
            (root / name).mkdir(mode=0o700, exist_ok=True)
        (root / "settings.json").write_text(json.dumps(settings_for(root, home), indent=1) + "\n", encoding="utf-8")
        route = stage_config(root, args.sdk_from)
        directives = {name: sha256_file(root / "trees" / name / "CLAUDE.local.md") for name, (_, directive) in C.TREES.items() if directive}
        manifest = {"harness": C.HARNESS, "schema": C.MANIFEST_SCHEMA, "generation": uuid.uuid4().hex, "created_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "root": str(root),
                    "commits": {"base": tasks["base"], "stale": tasks["stale"]}, "trees": heads,
                    **tools, "directives": directives, "sdk": {"version": C.SDK_VERSION, "route": route}, "staged": {name: sha256_file(root / "config" / name) for name in C.STAGED_FILES},
                    "settings_sha256": sha256_file(root / "settings.json")}
        (root / MANIFEST).write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
        print(json.dumps({"root": str(root), "trees": heads, "sdk": route, "manifest": str(root / MANIFEST)}, indent=1))
        return 0
    except Refusal as refusal:
        print(f"refused: {refusal}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
