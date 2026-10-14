#!/usr/bin/env python3
"""readdeny_probe.py OUTDIR [--arm NAME ...]: the native sandbox's read denial of the credential paths (CPA route B), measured on the installed Claude Code in a scratch HOME with synthetic credential files and a
loopback stand-in for the Messages API (tools/sandbox-probe/mock_messages_api.py): no model, no credential and no network beyond 127.0.0.1 are involved. Every probe prints status words only; the scratch HOME is
deleted after each arm. The arms read the shipped overlay, adoption/templates/claude.sandbox-readdeny.settings.template.json. ASCII only."""
import hashlib
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
repo = HERE.parents[1]
outdir = Path(sys.argv[1]).resolve()
wanted = [sys.argv[i + 1] for i, a in enumerate(sys.argv) if a == "--arm"]
CLAUDE = Path.home() / ".local/share/claude/versions" / os.environ.get("NAS_PROBE_CLIENT_VERSION", "2.1.296")

# synthetic credential files at the paths the profile template's Read rules and the credential inventory name (relative to the scratch HOME)
FIXTURES = [".ssh/id_ed25519", ".aws/credentials", ".netrc", ".npmrc", ".docker/config.json", ".config/gh/hosts.yml", ".config/native-agent-stack/alpaca-paper.env",
            ".config/ecosystem-observability/ecosystem-grafana.env", ".config/nativestack/generation.key", ".claude/.credentials.json", ".codex/auth.json", ".cache/huggingface/token",
            ".local/state/native-agent-stack/runtime-workers/openhands/secrets/run1-armA.server.env", ".config/omniroute/data.json"]
DECOYS = [".config/gh/config.yml", "notes.txt"]
template_permissions = json.loads((repo / "adoption/templates/claude.settings.template.json").read_text(encoding="utf-8"))["permissions"]
overlay = json.loads((repo / "adoption/templates/claude.sandbox-readdeny.settings.template.json").read_text(encoding="utf-8"))
BASE_SANDBOX = {"enabled": True, "failIfUnavailable": True, "allowUnsandboxedCommands": False}


def arm_settings(arm):
    """(settings of the scratch user file, settings passed with --settings or None)"""
    bypass = {"defaultMode": "bypassPermissions"}
    if arm == "control-no-sandbox":
        return {"permissions": template_permissions}, None
    if arm == "sandbox-open":
        return {"permissions": bypass, "sandbox": BASE_SANDBOX}, None
    if arm == "sandbox-template":
        return {"permissions": template_permissions, "sandbox": BASE_SANDBOX}, None
    if arm == "overlay-denyread-only":
        return {"permissions": bypass}, {"sandbox": overlay["sandbox"]}
    if arm == "overlay-user-scope-loaded":
        return {"permissions": template_permissions}, overlay
    if arm == "overlay-setting-sources":
        # the deployment: --setting-sources project,local leaves the user scope out, so the overlay carries the mode too
        return {"permissions": template_permissions}, {**overlay, "permissions": {**overlay["permissions"], "defaultMode": "bypassPermissions"}}
    raise SystemExit(f"unknown arm {arm}")


ARMS = ["control-no-sandbox", "sandbox-open", "sandbox-template", "overlay-denyread-only", "overlay-user-scope-loaded", "overlay-setting-sources"]
REPEATS = int(os.environ.get("NAS_PROBE_REPEATS", "0"))


def commands():
    names = [f"F{i}" for i in range(len(FIXTURES))]
    shell_loop = ('for n in ' + " ".join(names) + '; do eval f=\\$RB_P_$n; eval h=\\$RB_H_$n; if out=$(sha256sum "$f" 2>/dev/null); then [ "${out%% *}" = "$h" ] && echo "REAL $n" || echo "OTHER $n"; '
                  'else echo "DENIED $n"; fi; done; echo rc=$?')
    python_loop = ('python3 -c \'import hashlib, os\nfor n in (' + ", ".join(f'"{n}"' for n in names) + '):\n    try:\n        d = hashlib.sha256(open(os.environ["RB_P_" + n], "rb").read()).hexdigest()\n'
                   '        print(("REAL " if d == os.environ["RB_H_" + n] else "OTHER ") + n)\n    except OSError as e:\n        print("DENIED " + n, type(e).__name__)\'; echo rc=$?')
    return [
        {"command": shell_loop, "description": "read each synthetic credential, status only"},
        {"command": python_loop, "description": "Python open() of each synthetic credential, status only"},
        {"command": 'ln -sf "$RB_P_F0" ./rb-link; if out=$(sha256sum ./rb-link 2>/dev/null); then [ "${out%% *}" = "$RB_H_F0" ] && echo REAL-via-symlink || echo OTHER-via-symlink; else echo DENIED-via-symlink; fi; rm -f ./rb-link; echo rc=$?',
         "description": "read through a symlink in the working directory"},
        {"command": 'cp "$RB_P_F0" ./rb-copy 2>/dev/null; if [ -f ./rb-copy ]; then echo COPIED; else echo NOT-COPIED; fi; rm -f ./rb-copy; echo rc=$?', "description": "copy into the working directory"},
        {"command": 'for d in .ssh .aws .config/native-agent-stack .config/gh; do n=$(ls -A "$HOME/$d" 2>/dev/null | wc -l); echo "listing $d: $n"; done; echo rc=$?', "description": "entries listed in the protected directories"},
        {"command": 'echo "decoys:"; for f in .config/gh/config.yml notes.txt; do if [ -r "$HOME/$f" ]; then echo "readable $f"; else echo "unreadable $f"; fi; done; echo rc=$?', "description": "ordinary files stay readable"},
        {"command": 'echo ok; (git status --short | wc -l); python3 -c "print(40+2)"; ls /proc/self/status > /dev/null && echo proc-ok; if cat /proc/self/environ > /dev/null 2>&1; then echo environ-readable; else echo environ-blocked; fi; echo rc=$?',
         "description": "ordinary commands and the process environment file"},
        {"tool": "Read", "file_path": "$HOME_PLACEHOLDER/" + FIXTURES[0]},
        {"tool": "Read", "file_path": "$HOME_PLACEHOLDER/" + DECOYS[1]},
    ] + [{"command": f"echo repeat-{k}; true", "description": f"benign repeat {k}"} for k in range(REPEATS)]


def run_arm(arm):
    root = Path(tempfile.mkdtemp(prefix=f"sandbox-probe-{arm}-"))
    home, work = root / "home", root / "work"
    for sub in (".claude", "work"):
        (root / ("home/" + sub if sub == ".claude" else sub)).mkdir(parents=True, exist_ok=True)
    env_extra, hashes = {}, {}
    for i, rel in enumerate(FIXTURES):
        path = home / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("RB SYNTHETIC, NOT A CREDENTIAL\n" + secrets.token_hex(32) + "\n")
        os.chmod(path, 0o600)
        env_extra[f"RB_P_F{i}"] = str(path)
        env_extra[f"RB_H_F{i}"] = hashlib.sha256(path.read_bytes()).hexdigest()
    for rel in DECOYS:
        path = home / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("ordinary file\n")
    subprocess.run(["git", "-C", str(work), "init", "-q"], check=True)
    (work / "README.md").write_text("rb\n")
    subprocess.run(["git", "-C", str(work), "add", "README.md"], check=True)
    subprocess.run(["git", "-C", str(work), "-c", "user.email=rb@example.invalid", "-c", "user.name=rb", "commit", "-qm", "init"], check=True)
    user_settings, cli_settings = arm_settings(arm)
    (home / ".claude/settings.json").write_text(json.dumps(user_settings, indent=1))
    cli_args = []
    if cli_settings is not None:
        overlay = root / "overlay.json"
        overlay.write_text(json.dumps(cli_settings, indent=1))
        cli_args = ["--settings", str(overlay)]
    if arm == "overlay-setting-sources":
        cli_args += ["--setting-sources", "project,local"]
    plan = [dict(c, **({"file_path": c["file_path"].replace("$HOME_PLACEHOLDER", str(home))} if c.get("tool") == "Read" else {})) for c in commands()]
    (root / "commands.json").write_text(json.dumps(plan))
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    log = root / "requests.jsonl"
    mock = subprocess.Popen([sys.executable, "-I", str(HERE / "mock_messages_api.py"), "--port", str(port), "--log", str(log), "--commands", str(root / "commands.json")],
                            stdout=open(root / "mock.out", "w"), stderr=subprocess.STDOUT)
    for _ in range(60):
        if "listening" in (root / "mock.out").read_text():
            break
        time.sleep(0.1)
    environment = {"HOME": str(home), "PATH": "/usr/local/bin:/usr/bin:/bin", "LANG": "C.UTF-8", "TERM": "dumb", "XDG_RUNTIME_DIR": os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"),
                   "ANTHROPIC_BASE_URL": f"http://127.0.0.1:{port}", "ANTHROPIC_API_KEY": "rb-dummy-not-a-key", "DISABLE_TELEMETRY": "1", "DISABLE_ERROR_REPORTING": "1", "DISABLE_AUTOUPDATER": "1",
                   "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1", **env_extra}
    started = time.strftime("%FT%TZ", time.gmtime())
    done = subprocess.run([str(CLAUDE), "-p", "Run the credentials probe.", "--output-format", "stream-json", "--verbose", "--max-turns", "40", *cli_args], cwd=work, env=environment,
                          stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=300)
    mock.terminate()
    mock.wait(timeout=10)
    # the tool results, in order, from the requests the client sent back
    results = []
    last = {}
    for line in log.read_text().splitlines():
        body = json.loads(line).get("body") or {}
        messages = body.get("messages") or []
        if messages:
            last = messages[-1]
    # the last request holds every tool result of the conversation in order
    outputs = []
    for message in (json.loads(l).get("body") or {} for l in log.read_text().splitlines()):
        pass
    final_messages = []
    for l in log.read_text().splitlines():
        b = json.loads(l).get("body") or {}
        if isinstance(b.get("messages"), list):
            final_messages = b["messages"]
    for message in final_messages:
        if message.get("role") == "user" and isinstance(message.get("content"), list):
            for block in message["content"]:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    content = block.get("content")
                    text = content if isinstance(content, str) else "".join(c.get("text", "") for c in content if isinstance(c, dict))
                    outputs.append({"is_error": bool(block.get("is_error")), "text": text.replace(str(home), "<HOME>").replace(str(work), "<WORK>")[:700]})
    stderr = done.stderr.replace(str(home), "<HOME>").replace(str(work), "<WORK>")[-600:]
    shutil.rmtree(root, ignore_errors=True)
    return {"arm": arm, "claude_rc": done.returncode, "started_utc": started, "tool_results": outputs, "stderr_tail": stderr, "scratch_deleted": not root.exists()}


outdir.mkdir(parents=True, exist_ok=True)
for arm in (wanted or ARMS):
    result = run_arm(arm)
    (outdir / f"{arm}.json").write_text(json.dumps(result, indent=1) + "\n")
    print(arm, "rc", result["claude_rc"], "results", len(result["tool_results"]), flush=True)
