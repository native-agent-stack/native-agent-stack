"""Fresh isolated install/smoke window; private capture.py outputs are authoritative.

Never launches a model, VM, service or host installer. Explicitly uses the
existing two run pins; upstream sources and smoke scope are in README.md.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys

from capture import record, save_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scratch", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--repo", type=Path, required=True)
    args = parser.parse_args()
    scratch, raw, repo = args.scratch.resolve(), args.raw_dir.resolve(), args.repo.resolve()
    scratch.mkdir(mode=0o700, parents=True, exist_ok=True)
    if list(scratch.iterdir()):
        raise ValueError("fresh scratch required")
    raw.mkdir(mode=0o700, parents=True)  # never append to a prior run window
    for name in ("config", "cache", "data", "tmp", "work", "npm-prefix", "wt-prefix"):
        (scratch / name).mkdir()
    env = {"PATH": os.environ["PATH"], "LANG": "C.UTF-8", "NO_COLOR": "1",
           "XDG_CONFIG_HOME": str(scratch / "config"), "XDG_CACHE_HOME": str(scratch / "cache"),
           "XDG_DATA_HOME": str(scratch / "data"), "TMPDIR": str(scratch / "tmp"),
           "WORKTRUNK_CONFIG_PATH": str(scratch / "config/wt.toml"),
           "WORKTRUNK_SYSTEM_CONFIG_PATH": str(scratch / "config/wt-system.toml"),
           "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1",
           "GIT_AUTHOR_NAME": "Isolation fixture", "GIT_COMMITTER_NAME": "Isolation fixture",
           "GIT_AUTHOR_EMAIL": "234074349+seathatflowsinourveins@users.noreply.github.com",
           "GIT_COMMITTER_EMAIL": "234074349+seathatflowsinourveins@users.noreply.github.com"}

    def invoke(name, argv, cwd=scratch, expected=(0,), timeout=180):
        result = record(raw, name, argv, cwd, env, timeout)
        print(json.dumps({"capture": name, "exit_code": result["exit_code"]}), flush=True)
        if result["timed_out"] or result["exit_code"] not in expected:
            raise RuntimeError("unexpected result; inspect private capture " + name)
        return result

    for name in ("wt", "srt", "node", "npm", "bwrap"):
        invoke("host-" + name + "-version", [name, "--version"])
    for name, url in (
        ("worktrunk-tag", "https://api.github.com/repos/max-sixty/worktrunk/commits/v0.80.0"),
        ("srt-tag", "https://api.github.com/repos/anthropics/sandbox-runtime/git/ref/tags/v0.0.79"),
        ("srt-package-metadata", "https://registry.npmjs.org/@anthropic-ai%2Fsandbox-runtime/0.0.79"),
    ):
        invoke(name, ["curl", "--fail", "--silent", "--show-error", "--location", url])
    installer = scratch / "worktrunk-installer.sh"
    invoke("worktrunk-download", ["curl", "--fail", "--silent", "--show-error", "--location",
           "https://github.com/max-sixty/worktrunk/releases/download/v0.80.0/worktrunk-installer.sh",
           "--output", str(installer)])
    invoke("worktrunk-install", ["env", "WORKTRUNK_UNMANAGED_INSTALL=" + str(scratch / "wt-prefix"),
                                "sh", str(installer)])
    wt = str(scratch / "wt-prefix/wt")
    invoke("worktrunk-version", [wt, "--version"])
    fixture = scratch / "work/repo"
    invoke("fixture-init", ["git", "init", "--quiet", "-b", "main", str(fixture)])
    invoke("fixture-commit", ["git", "commit", "--quiet", "--allow-empty", "-m", "Isolated fixture"], fixture)
    invoke("fixture-object", ["git", "rev-parse", "HEAD"], fixture)
    invoke("worktrunk-before", [wt, "list", "--format=json"], fixture)
    invoke("worktrunk-create", [wt, "switch", "--create", "isolated", "--base", "main", "--no-cd", "--no-hooks"], fixture)
    invoke("worktrunk-created", [wt, "list", "--format=json"], fixture)
    invoke("worktrunk-remove", [wt, "remove", "isolated", "--foreground", "--no-hooks"], fixture)
    invoke("worktrunk-after", [wt, "list", "--format=json"], fixture)
    invoke("fixture-status", ["git", "status", "--porcelain"], fixture)
    invoke("srt-install", ["npm", "--userconfig=" + str(scratch / "config/npm-user.conf"),
           "--globalconfig=" + str(scratch / "config/npm-global.conf"), "--cache=" + str(scratch / "cache/npm"),
           "install", "--global", "--prefix", str(scratch / "npm-prefix"), "--no-fund", "--no-audit",
           "@anthropic-ai/sandbox-runtime@0.0.79"], timeout=300)
    srt = str(scratch / "npm-prefix/bin/srt")
    invoke("srt-version", [srt, "--version"])
    policy = scratch / "policy.json"
    shutil.copyfile(Path(__file__).with_name("policy.json"), policy)
    invoke("policy-input", ["cat", str(policy)])
    prefix = [srt, "--settings", str(policy), "--"]
    invoke("srt-echo", [*prefix, "echo", "isolation-native-recapture"], scratch / "work")
    invoke("srt-allow-write", [*prefix, "sh", "-c", "printf allowed > allowed.txt"], scratch / "work")
    invoke("allowed-bytes", ["od", "-An", "-tx1", "allowed.txt"], scratch / "work")
    invoke("srt-deny-write", [*prefix, "sh", "-c", "printf forbidden > denied.txt"], scratch / "work", (1, 2))
    invoke("denied-file-absent", ["test", "!", "-e", "denied.txt"], scratch / "work")
    invoke("kvm-precondition", [sys.executable, "-c", 'import os; print(os.access("/dev/kvm", os.R_OK | os.W_OK))'])
    invoke("lane-packet-generation", [sys.executable, "tools/sota-convergence/lane_packets.py", "--root", str(repo),
           "--out", str(scratch / "packets"), "--catalog", "foundation", "--checked-at", "2026-10-16",
           "--manifest", "catalogs/sota-convergence/manifest-20260929.json", "--registered-receipts", "--manifest-newcomers"], repo)
    # Native generator file retained privately as an input, not labeled E2E.
    shutil.copyfile(scratch / "packets/packets/foundation__isolation.json", raw / "foundation__isolation.json")
    os.chmod(raw / "foundation__isolation.json", 0o600)
    fixture_object = (raw / "fixture-object/stdout.bin").read_bytes().decode("ascii").strip()
    if len(fixture_object) != 40 or any(c not in "0123456789abcdef" for c in fixture_object):
        raise ValueError("unexpected disposable fixture object")
    replacements = {str(scratch): "<SCRATCH>", str(repo): "<REPO>", str(Path.home()): "<USER_HOME>",
                    fixture_object: "<FIXTURE_OBJECT>", fixture_object[:7]: "<FIXTURE_SHORT_OBJECT>"}
    save_json(raw / "mask-rules.json", replacements)
    os.chmod(raw / "mask-rules.json", 0o600)
    print(json.dumps({"status": "captured", "raw_reference": raw.name}), flush=True)


if __name__ == "__main__":
    main()
