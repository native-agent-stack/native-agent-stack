#!/usr/bin/env python3
"""No-model native discovery acceptance; publish only allowlisted derived facts.

Native commands: Pi get_commands RPC/mcp list/auth check (04566631),
OpenCode debug skill/mcp list (53d1eabb). Native stdout stays in an anonymous
temporary file, which also avoids OpenCode's piped stdout truncation. No native
config/auth/session root is copied or hashed. Only managed SKILL.md bytes are
hashed, as the canonical manifest's integrity check requires.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import re

from runtime_profiles import ROOT, PROFILES, ROLE_SCOPES, private_write, profile_environment, utc, choose_slot


def native(command, *, env, cwd, input=None, seconds=180):
    with tempfile.TemporaryFile(mode="w+") as output, tempfile.TemporaryFile(mode="w+") as errors:
        try:
            result = subprocess.run(command, env=env, cwd=cwd, input=input, text=True,
                                    stdout=output, stderr=errors, timeout=seconds)
            code = result.returncode
        except subprocess.TimeoutExpired:
            code = 124
        except OSError:
            code = 127
        output.seek(0)
        return code, output.read()


def managed_rows():
    manifest = json.loads((ROOT / "adoption/skills/manifest.json").read_text())
    return {s["name"]: s for s in manifest["skills"] if s.get("status") != "held"
            and not s.get("native_plugin") and s.get("agents") != ["claude-code"]}


def discovered(runtime, text):
    if runtime == "opencode":
        return [{"name": s["name"], "description": s.get("description", ""), "path": s.get("location"),
                 "builtin": s.get("location") == "<built-in>"} for s in json.loads(text)]
    for line in text.split("\n"):
        if not line.strip():
            continue
        event = json.loads(line)
        if event.get("command") == "get_commands" and event.get("success"):
            return [{"name": s["name"].removeprefix("skill:"), "description": s.get("description", ""),
                     "path": s.get("sourceInfo", {}).get("path"), "builtin": False}
                    for s in event.get("data", {}).get("commands", []) if s.get("source") == "skill"]
    raise ValueError("native discovery unavailable")


def opencode_statuses(text, names):
    """Read pinned native CLI statuses; an exit0 alone does not mean connected.

    OpenCode53 cli/cmd/mcp.ts:138-162 prints exact names and state text, and
    does not fail the process for an individual connection failure.
    """
    plain = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", text)
    states = {}
    for name in names:
        match = re.search(r"(?:✓|○|⚠|✗)\s+" + re.escape(name)
                          + r"\s+(connected|disabled|not initialized|needs authentication|needs client registration|failed)\b", plain)
        states[name] = match.group(1) if match else "unverified"
    return states


def skill_integrity(rows, tokenizer_python=sys.executable):
    expected = managed_rows()
    found = {s["name"]: s for s in rows}
    checks = {}
    for name, spec in expected.items():
        row = found.get(name)
        if not row or not isinstance(row.get("path"), str):
            checks[name] = "missing"
            continue
        path = Path(row["path"])
        # Accept only canonical public skill bytes, never arbitrary native
        # output paths that could identify an authentication file.
        canonical = Path.home() / ".agents/skills" / name / "SKILL.md"
        if path.resolve() != canonical.resolve() or not canonical.is_file():
            checks[name] = "noncanonical_location"
            continue
        actual = hashlib.sha256(canonical.read_bytes()).hexdigest()
        checks[name] = "ok" if actual == spec["skill_md_sha256"] else "sha_mismatch"
    listing = "\n".join(s["name"] + ": " + s.get("description", "") for s in rows)
    try:
        result = subprocess.run([str(tokenizer_python), "-c",
            "import sys,json,tiktoken; print(json.dumps({'tokens':len(tiktoken.get_encoding('o200k_base').encode(sys.stdin.read())),'version':tiktoken.__version__}))"],
            input=listing, capture_output=True, text=True, timeout=60)
        tokenized = json.loads(result.stdout) if result.returncode == 0 else {}
        count = tokenized.get("tokens")
    except (OSError, ValueError, subprocess.SubprocessError):
        count, tokenized = None, {}
    return {"required_managed_count": len(expected), "managed_checks": checks,
            "managed_pass": all(value == "ok" for value in checks.values()),
            "native_discovered_count": len(rows),
            "extras": sorted(s["name"] for s in rows if s["name"] not in expected),
            "builtin_names": sorted(s["name"] for s in rows if s["builtin"]),
            "listing_description_chars": len(listing), "listing_description_tokens_o200k": count,
            "tokenizer_version": tokenized.get("version"),
            "listing_token_basis": "o200k_base on name:description lines; proxy, not native Claude tokenizer or system-prompt billing"}


def check(args, profile):
    runtime = profile.split("-")[0]
    root = args.state_root / profile
    if args.role_scope:
        root = root / "roles" / args.role_scope
    # Our non-secret descriptor is explicit input, not native config/auth.
    descriptor = json.loads((root / "profile.json").read_text())
    aux = Path(descriptor["auxiliary_root"]) if descriptor.get("auxiliary_root") else None
    env = {**os.environ, **profile_environment(profile, args.state_root, args.role_scope, aux)}
    if descriptor.get("skills_bin"):
        env["PATH"] = str(Path(descriptor["skills_bin"]).parent) + os.pathsep + env["PATH"]
    binary = descriptor[runtime + "_bin"]
    started = utc()
    route = profile.split("-")[1]
    slot = choose_slot() if route == "claude" else None
    auth = {"native_check": "not provided by OpenCode 1.18.35", "loader_health_ready": bool(slot),
            "credential_loader_id": slot, "inference_required": True}
    if runtime == "pi":
        auth_command = [binary, "auth", "check", "--provider", "anthropic" if slot else "omniroute", "--json", "--no-refresh"]
        if slot:
            auth_command = [sys.executable, str(ROOT / "tools/credentials/credential_run.py"), slot,
                            "--only", "ANTHROPIC_API_KEY", "--", "env",
                            *[key + "=" + value for key, value in profile_environment(profile, args.state_root, args.role_scope, aux).items()],
                            *auth_command]
        auth_code, auth_output = native(auth_command, env=os.environ if slot else env, cwd=args.workspace)
        auth = {"native_check": "pi auth check --json --no-refresh", "exit_code": auth_code,
                "credential_loader_id": slot, "ready": auth_code == 0, "inference_required": True}
    if runtime == "pi":
        command = [binary, "--mode", "rpc", "--no-mcp"]
        data = json.dumps({"id": "native-skill-discovery", "type": "get_commands"}) + "\n"
    else:
        command, data = [binary, "debug", "skill"], None
    code, output = native(command, env=env, cwd=args.workspace, input=data)
    try:
        skill_facts = skill_integrity(discovered(runtime, output), args.tokenizer_python)
    except (ValueError, OSError, KeyError, TypeError):
        skill_facts = {"managed_pass": False, "status": "native_discovery_unreadable"}
    mcp_command = [binary, "mcp", "list"] + (["--json"] if runtime == "pi" else [])
    mcp_code, mcp_output = native(mcp_command, env=env, cwd=args.workspace)
    mcp_facts = {"exit_code": mcp_code, "all_connected": mcp_code == 0,
                 "expected_names": descriptor["mcp_server_names"]}
    if runtime == "pi":
        mcp_facts["all_connected"] = False
        try:
            servers = json.loads(mcp_output).get("servers", [])
            if isinstance(servers, dict):
                servers = [{"name": name, **entry} for name, entry in servers.items()]
            mcp_facts["servers"] = [{"name": s["name"], "state": s.get("state"),
                                       "tool_count": len(s.get("tools", []))} for s in servers
                                      if s.get("name") in descriptor["mcp_server_names"]]
            found = mcp_facts["servers"]
            expected = descriptor["mcp_server_names"]
            mcp_facts["all_connected"] = (mcp_code == 0 and bool(expected)
                and len(found) == len(expected) and {s["name"] for s in found} == set(expected)
                and all(s["state"] == "connected" for s in found))
        except (ValueError, KeyError, TypeError):
            mcp_facts["readback"] = "unreadable"
    else:
        # This CLI offers human statuses, not a JSON tool-count contract.
        # Do not invent counts or publish arbitrary native error strings.
        mcp_facts["tool_counts"] = "UNVERIFIED: native CLI list has no JSON tool-count interface"
        statuses = opencode_statuses(mcp_output, descriptor["mcp_server_names"])
        mcp_facts["servers"] = [{"name": name, "state": state} for name, state in statuses.items()]
        mcp_facts["all_connected"] = all(s == "connected" for s in statuses.values())
    probes = {}
    for name in ("rtk", "wt", "qmd", "promptfoo", "mcporter", "srt", "orx", "agent-browser", "tvly", "gitleaks"):
        probe_code, _ = native([name, "--version"], env=env, cwd=args.workspace, seconds=30)
        probes[name] = {"exit_code": probe_code, "scope": "native version probe, not functional acceptance"}
    receipt = {"schema_version": 1, "status": "trial", "profile": "ns-" + profile,
               "role_scope": args.role_scope, "started_utc": started, "tool_read_utc": utc(),
               "discovery_command": [runtime, *command[1:]], "discovery_exit_code": code,
               "skills": skill_facts, "mcp_command": [runtime, *mcp_command[1:]], "mcp": mcp_facts,
               "model_calls": 0, "native_state_published": False,
               "native_cli_invocations": probes,
               "tier1": {"consumed_by_path": bool(descriptor.get("tier1_input")),
                         "slot_count": len(descriptor.get("tier1_slots", [])),
                         "managed_required_count": len(managed_rows())},
               "tier2": descriptor.get("tier2"),
               "pending_layers": {"socraticode": "pending E1: fresh worktree has no index; incremental indexing/path-per-call unmeasured"},
               "auth": auth}
    private_write(args.out / (profile + ".discovery.json"), json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"profile": profile, "discovery_exit_code": code,
                      "managed_skills_pass": skill_facts["managed_pass"], "mcp_exit_code": mcp_code}))
    return code == 0 and skill_facts["managed_pass"] and mcp_code == 0 and mcp_facts["all_connected"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--role-scope", choices=ROLE_SCOPES)
    parser.add_argument("--tokenizer-python", type=Path, default=Path(sys.executable),
                        help="existing interpreter with tiktoken; never installs a tokenizer")
    parser.add_argument("--profile", choices=PROFILES, action="append")
    args = parser.parse_args()
    results = [check(args, profile) for profile in args.profile or PROFILES]
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
