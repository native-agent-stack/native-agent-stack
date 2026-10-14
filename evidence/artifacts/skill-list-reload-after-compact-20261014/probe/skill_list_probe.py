#!/usr/bin/env python3
"""skill_list_probe.py RECEIPT.json TEMPLATE BINARY...: does Claude Code still send the skill list after a compaction,
and does the settings template's SessionStart hook on the `compact` source bring it back?

Wire-level and zero spend: each arm runs the named client binary in a scratch home against the loopback stand-in beside
this file (mock_messages_api.py), which records every request body. No model, no credential and no network beyond
127.0.0.1 are involved. The hook under test is read from TEMPLATE (adoption/templates/claude.settings.template.json), so
the receipt is about the entry the repository ships.

Arms per binary, each in one client process (a resume would re-seed the list) fed over --input-format stream-json:
  manual     two turns, /compact, two turns
  auto       four turns; the stand-in reports a context near the client's window on its first reply, so the client
             compacts by itself before the second turn's request
  auto-tool  as auto, with one tool call per conversation, so the compaction falls inside a turn
each once without the hook (control) and once with it (hook).

The receipt holds counts and booleans only: per request its number, its message count, whether the Skill tool was
offered and whether the skill list (and the scratch home's synthetic skill) was in the messages. The request logs hold
the client's own prompt text and are deleted with the scratch directory.
"""
import hashlib
import json
import os
import select
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
MARK_LIST = "skills are available for use with the Skill tool"
MARK_SKILL = "probe-alpha"
NEAR_WINDOW = "14990000"  # the client treats an unknown model behind a custom base URL as a 15,000,000-token window
ARMS = {
    "manual": {"turns": ["turn one: reply briefly", "turn two: reply briefly", "/compact", "turn three: reply briefly",
                         "turn four: reply briefly"], "commands": "[]", "high_first": "0"},
    "auto": {"turns": ["turn one: reply briefly", "turn two: reply briefly", "turn three: reply briefly",
                       "turn four: reply briefly"], "commands": "[]", "high_first": "1"},
    "auto-tool": {"turns": ["turn one: reply briefly", "turn two: reply briefly", "turn three: reply briefly",
                            "turn four: reply briefly"], "commands": '[{"command": "echo probe"}]', "high_first": "2"},
}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def texts(node):
    if isinstance(node, str):
        yield node
    elif isinstance(node, list):
        for x in node:
            yield from texts(x)
    elif isinstance(node, dict):
        for k in ("text", "content"):
            if k in node:
                yield from texts(node[k])


def compact_group(template):
    groups = [g for g in json.loads(Path(template).read_text(encoding="utf-8"))["hooks"]["SessionStart"]
              if g.get("matcher") == "compact"]
    if len(groups) != 1:
        raise SystemExit(f"expected one SessionStart group with matcher compact in {template}, found {len(groups)}")
    return groups[0]


def lines(path):
    return sum(1 for _ in open(path)) if os.path.exists(path) else 0


def run_arm(binary, version, arm, with_hook, group, root):
    spec = ARMS[arm]
    base = Path(root) / f"{version}-{arm}-{'hook' if with_hook else 'control'}"
    home, work = base / "home", base / "work"
    work.mkdir(parents=True)
    for name in ("probe-alpha", "probe-beta"):
        d = home / ".claude" / "skills" / name
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(f"---\nname: {name}\ndescription: Synthetic probe skill {name}; use when the user says {name}.\n---\n\nProbe body.\n")
    (home / ".claude" / "settings.json").write_text(json.dumps({"hooks": {"SessionStart": [group]}} if with_hook else {}))
    commands, log, port = base / "commands.json", base / "requests.jsonl", free_port()
    commands.write_text(spec["commands"])
    mock = subprocess.Popen([sys.executable, "-I", str(HERE / "mock_messages_api.py"), "--port", str(port), "--log", str(log),
                             "--commands", str(commands), "--high-usage-first", spec["high_first"], "--high-usage-tokens", NEAR_WINDOW],
                            stdout=subprocess.PIPE, text=True)
    mock.stdout.readline()
    env = {"HOME": str(home), "PATH": "/usr/local/bin:/usr/bin:/bin", "LANG": "C.UTF-8", "TERM": "dumb",
           "XDG_RUNTIME_DIR": os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"),
           "ANTHROPIC_BASE_URL": f"http://127.0.0.1:{port}", "ANTHROPIC_API_KEY": "probe-dummy-not-a-key",
           "DISABLE_TELEMETRY": "1", "DISABLE_ERROR_REPORTING": "1", "DISABLE_AUTOUPDATER": "1",
           "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"}
    client = subprocess.Popen([binary, "-p", "--input-format", "stream-json", "--output-format", "stream-json", "--verbose",
                               "--model", "claude-haiku-5-5"], cwd=work, env=env, stdin=subprocess.PIPE,
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    triggers, at_boundary, results = [], None, []
    try:
        for text in spec["turns"]:
            client.stdin.write(json.dumps({"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": text}]}}) + "\n")
            client.stdin.flush()
            deadline, done = time.time() + 120, False
            while time.time() < deadline and not done:
                ready, _, _ = select.select([client.stdout], [], [], 1.0)
                if not ready:
                    if client.poll() is not None:
                        break
                    continue
                line = client.stdout.readline()
                if not line:
                    break
                try:
                    ev = json.loads(line)
                except ValueError:
                    continue
                if ev.get("type") == "system" and ev.get("subtype") == "compact_boundary":
                    triggers.append((ev.get("compact_metadata") or ev.get("compactMetadata") or {}).get("trigger"))
                    if at_boundary is None:
                        at_boundary = lines(log)
                if ev.get("type") == "result":
                    results.append(ev.get("subtype"))
                    done = True
    finally:
        try:
            client.stdin.close()
        except OSError:
            pass
        try:
            client.wait(timeout=30)
        except subprocess.TimeoutExpired:
            client.kill()
        mock.terminate()
    requests = []
    for line in open(log) if os.path.exists(log) else []:
        r = json.loads(line)
        body = r.get("body") or {}
        if r.get("method") != "POST" or not str(r.get("path", "")).startswith("/v1/messages") or "count_tokens" in r["path"]:
            continue
        message_text = "\n".join(texts(body.get("messages")))
        requests.append({"n": r["n"], "messages": len(body.get("messages") or []),
                         "skill_tool_offered": "Skill" in [t.get("name") for t in body.get("tools") or [] if isinstance(t, dict)],
                         "skill_list_in_messages": MARK_LIST in message_text and MARK_SKILL in message_text,
                         "skill_list_in_system": MARK_LIST in "\n".join(texts(body.get("system")))})
    after = [q["skill_list_in_messages"] for q in requests if at_boundary is not None and q["n"] > at_boundary]
    return {"version": version, "arm": arm, "hook": with_hook, "client_exit": client.returncode, "turn_results": results,
            "compaction_triggers": triggers, "requests_logged_at_boundary": at_boundary, "requests": requests,
            "list_in_requests_before_boundary": [q["skill_list_in_messages"] for q in requests if at_boundary is not None and q["n"] <= at_boundary],
            "list_in_requests_after_boundary": after}


def main(argv):
    out, template, binaries = argv[0], argv[1], argv[2:]
    group = compact_group(template)
    root = tempfile.mkdtemp(prefix="skill-list-probe-", dir=os.environ.get("PROBE_SCRATCH", "/var/tmp"))
    rows = []
    try:
        for binary in binaries:
            version = subprocess.run([binary, "--version"], capture_output=True, text=True, stdin=subprocess.DEVNULL).stdout.split()[0]
            for arm in ARMS:
                for with_hook in (False, True):
                    row = run_arm(binary, version, arm, with_hook, group, root)
                    rows.append(row)
                    print(version, arm, "hook" if with_hook else "control", "triggers", row["compaction_triggers"],
                          "after", row["list_in_requests_after_boundary"], flush=True)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    receipt = {"probe": "skill_list_probe.py", "probe_sha256": sha256(__file__), "stand_in_sha256": sha256(HERE / "mock_messages_api.py"),
               "template": "adoption/templates/claude.settings.template.json", "template_sha256": sha256(template),
               "hook_group": group, "measured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "arms": rows}
    Path(out).write_text(json.dumps(receipt, indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
