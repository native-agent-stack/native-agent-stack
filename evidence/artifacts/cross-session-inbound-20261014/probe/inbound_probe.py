#!/usr/bin/env python3
"""Cross-session inbound policy probe: inbound_probe.py OUTDIR BINARY MOCK [ARM ...]

Each arm starts a receiver and then a sender, both real client processes of BINARY in one scratch HOME and one scratch
XDG_RUNTIME_DIR (so they see each other and no real session sees them), each against its own loopback Messages-API
stand-in (MOCK; no model, no credential, no network beyond 127.0.0.1). The sender's stand-in makes it call SendMessage
to the receiver by name; the receiver's stand-in logs every request, so "delivered" means the receiver's model was sent
a request carrying the probe's marker. Nothing here touches the real ~/.claude or the real sockets.
"""
import json
import os
import re
import select
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

OUT, BINARY, MOCK = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
MESSAGE_ID = re.compile(r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}", re.I)  # SendMessage's msg_id, kept out of the receipt
BYPASS, DONTASK = ["--dangerously-skip-permissions"], ["--permission-mode", "dontAsk", "--allowedTools", "SendMessage"]
ACCEPT = '{"crossSessionInbound":"accept"}'
ARMS = {  # sender mode, receiver mode, receiver --settings, user-scope value in the scratch home, project-scope value in the receiver's cwd
    "A1-dontask-to-bypass-unset": (DONTASK, BYPASS, None, None, None),
    "A2-bypass-to-bypass-unset": (BYPASS, BYPASS, None, None, None),
    "A3-bypass-to-dontask-flag-accept": (BYPASS, DONTASK, ACCEPT, None, None),
    "A3c-bypass-to-dontask-unset": (BYPASS, DONTASK, None, None, None),
    "A4-dontask-to-bypass-user-accept": (DONTASK, BYPASS, None, "accept", None),
    "A5-dontask-to-bypass-project-accept": (DONTASK, BYPASS, None, None, "accept"),
    # the account-C trader's own shape (run_session.sh): -p with the prompt on stdin, --tools Bash,Read, dontAsk; it is
    # mid-run (a 25-second sleep) when the bypass sender's message arrives
    "A6-bypass-to-trader-flag-accept": (BYPASS, "trader", ACCEPT, None, None),
    "A6c-bypass-to-trader-unset": (BYPASS, "trader", None, None, None),
}
TRADER = ["--tools", "Bash,Read", "--permission-mode", "dontAsk", "--allowedTools", "Bash(sleep:*)"]


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def mock(base, label, commands):
    (base / f"{label}-commands.json").write_text(json.dumps(commands))
    port, log = free_port(), base / f"{label}-requests.jsonl"
    p = subprocess.Popen([sys.executable, "-I", MOCK, "--port", str(port), "--log", str(log), "--commands", str(base / f"{label}-commands.json")],
                         stdout=subprocess.PIPE, text=True)
    p.stdout.readline()
    return p, port, log


def env(home, runtime, port):
    return {"HOME": str(home), "PATH": "/usr/local/bin:/usr/bin:/bin", "LANG": "C.UTF-8", "TERM": "dumb", "XDG_RUNTIME_DIR": str(runtime),
            "ANTHROPIC_BASE_URL": f"http://127.0.0.1:{port}", "ANTHROPIC_API_KEY": "probe-dummy-not-a-key", "DISABLE_TELEMETRY": "1",
            "DISABLE_ERROR_REPORTING": "1", "DISABLE_AUTOUPDATER": "1", "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"}


def read_events(proc, seconds, stop_on_result=True):
    events, deadline = [], time.time() + seconds
    while time.time() < deadline:
        ready, _, _ = select.select([proc.stdout], [], [], 0.5)
        if not ready:
            if proc.poll() is not None:
                break
            continue
        line = proc.stdout.readline()
        if not line:
            break
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        events.append(ev)
        if stop_on_result and ev.get("type") == "result":
            break
    return events


def kinds(events):
    return [e.get("type") + (":" + str(e.get("subtype")) if e.get("subtype") else "") for e in events]


def logged_with(log, marker):
    n = 0
    for line in open(log) if os.path.exists(log) else []:
        r = json.loads(line)
        if marker in json.dumps(r.get("body") or {}):
            n += 1
    return n


def run_arm(name, spec, root):
    send_mode, recv_mode, recv_flag, user_value, project_value = spec
    base = root / name
    home, runtime, work = base / "h", Path(tempfile.mkdtemp(prefix="r", dir="/var/tmp")), base / "w"
    (home / ".claude").mkdir(parents=True)
    work.mkdir(parents=True)
    os.chmod(runtime, 0o700)
    if user_value:
        (home / ".claude" / "settings.json").write_text(json.dumps({"crossSessionInbound": user_value}))
    if project_value:
        (work / ".claude").mkdir()
        (work / ".claude" / "settings.json").write_text(json.dumps({"crossSessionInbound": project_value}))
    marker, receiver_name = f"PROBEMARK-{name}", f"probe-recv-{name[:3].lower()}"
    rmock, rport, rlog = mock(base, "receiver", [])
    smock, sport, slog = mock(base, "sender", [{"tool": "SendMessage", "to": receiver_name, "summary": "probe",
                                                "message": f"{marker}: reply with the word ok."}])
    rargs = [BINARY, "-p", "--input-format", "stream-json", "--output-format", "stream-json", "--verbose", "--model", "claude-haiku-5-5",
             "--name", receiver_name, *recv_mode] + (["--settings", recv_flag] if recv_flag else [])
    receiver = subprocess.Popen(rargs, cwd=work, env=env(home, runtime, rport), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True)
    row = {"arm": name, "sender_mode": "dontAsk" if send_mode is DONTASK else "bypassPermissions",
           "receiver_mode": "dontAsk" if recv_mode is DONTASK else "bypassPermissions",
           "receiver_settings_flag": recv_flag, "user_scope": user_value, "project_scope": project_value}
    try:
        receiver.stdin.write(json.dumps({"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": "start"}]}}) + "\n")
        receiver.stdin.flush()
        first = read_events(receiver, 60)
        row["receiver_first_turn"] = [k for k in kinds(first) if k.startswith("result")]
        sargs = [BINARY, "-p", "send the probe message", "--output-format", "stream-json", "--verbose", "--model", "claude-haiku-5-5",
                 "--name", f"probe-send-{name[:3].lower()}", *send_mode]
        sent = subprocess.run(sargs, cwd=work, env=env(home, runtime, sport), capture_output=True, text=True, timeout=120)
        results = []
        for line in sent.stdout.splitlines():
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            m = ev.get("message") if isinstance(ev.get("message"), dict) else {}
            for b in m.get("content") or []:
                if isinstance(b, dict) and b.get("type") == "tool_result":
                    c = b.get("content")
                    text = c if isinstance(c, str) else " ".join(x.get("text", "") for x in c if isinstance(x, dict))
                    results.append(MESSAGE_ID.sub("<msg-id>", text.replace(str(base), "<BASE>").replace(str(runtime), "<RUNTIME>"))[:400])
        row["sender_exit"], row["sender_tool_results"] = sent.returncode, results
        after = read_events(receiver, 25, stop_on_result=False)
        row["receiver_events_after_send"] = kinds(after)
        row["receiver_model_requests_with_marker"] = logged_with(rlog, marker)
        row["delivered"] = row["receiver_model_requests_with_marker"] > 0
    finally:
        try:
            receiver.stdin.close()
        except OSError:
            pass
        try:
            receiver.wait(timeout=20)
        except subprocess.TimeoutExpired:
            receiver.kill()
        row["receiver_stderr_tail"] = receiver.stderr.read()[-300:].replace(str(base), "<BASE>")
        rmock.terminate()
        smock.terminate()
        shutil.rmtree(runtime, ignore_errors=True)
    return row


def run_trader_arm(name, spec, root):
    send_mode, _, recv_flag, _, _ = spec
    base = root / name
    home, runtime, work = base / "h", Path(tempfile.mkdtemp(prefix="r", dir="/var/tmp")), base / "w"
    (home / ".claude").mkdir(parents=True)
    work.mkdir(parents=True)
    os.chmod(runtime, 0o700)
    marker, receiver_name = f"PROBEMARK-{name}", f"probe-recv-{name[:3].lower()}"
    rmock, rport, rlog = mock(base, "receiver", [{"command": "sleep 25", "description": "wait as the trader does"}])
    smock, sport, slog = mock(base, "sender", [{"tool": "SendMessage", "to": receiver_name, "summary": "probe",
                                                "message": f"{marker}: reply with the word ok."}])
    (base / "prompt.md").write_text("Run the session.\n")
    rargs = [BINARY, "-p", "--model", "claude-haiku-5-5", "--name", receiver_name, *TRADER, "--output-format", "stream-json", "--verbose"] + (
        ["--settings", recv_flag] if recv_flag else [])
    with open(base / "prompt.md") as prompt:
        receiver = subprocess.Popen(rargs, cwd=work, env=env(home, runtime, rport), stdin=prompt, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, text=True)
    row = {"arm": name, "sender_mode": "bypassPermissions", "receiver_mode": "dontAsk (trader shape: -p, prompt on stdin, --tools Bash,Read)",
           "receiver_settings_flag": recv_flag, "user_scope": None, "project_scope": None}
    try:
        time.sleep(8)
        sargs = [BINARY, "-p", "send the probe message", "--output-format", "stream-json", "--verbose", "--model", "claude-haiku-5-5",
                 "--name", f"probe-send-{name[:3].lower()}", *send_mode]
        sent = subprocess.run(sargs, cwd=work, env=env(home, runtime, sport), capture_output=True, text=True, timeout=120)
        row["sender_exit"] = sent.returncode
        row["sender_tool_results"] = []
        for line in sent.stdout.splitlines():
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            m = ev.get("message") if isinstance(ev.get("message"), dict) else {}
            for b in m.get("content") or []:
                if isinstance(b, dict) and b.get("type") == "tool_result":
                    c = b.get("content")
                    text = c if isinstance(c, str) else " ".join(x.get("text", "") for x in c if isinstance(x, dict))
                    row["sender_tool_results"].append(MESSAGE_ID.sub("<msg-id>", text)[:400])
        out, err = receiver.communicate(timeout=120)
        events = []
        for line in out.splitlines():
            try:
                events.append(json.loads(line))
            except ValueError:
                pass
        row["receiver_events_after_send"] = [k for k in kinds(events) if k.startswith(("system:peer", "result"))]
        row["receiver_exit"] = receiver.returncode
        row["receiver_model_requests_with_marker"] = logged_with(rlog, marker)
        row["delivered"] = row["receiver_model_requests_with_marker"] > 0
        row["receiver_stderr_tail"] = err[-300:].replace(str(base), "<BASE>")
    finally:
        if receiver.poll() is None:
            receiver.kill()
        rmock.terminate()
        smock.terminate()
        shutil.rmtree(runtime, ignore_errors=True)
    return row


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix="inbound-probe-", dir="/var/tmp"))
    arms = sys.argv[4:] or list(ARMS)
    version = subprocess.run([BINARY, "--version"], capture_output=True, text=True, stdin=subprocess.DEVNULL).stdout.split()[0]
    rows = []
    try:
        for name in arms:
            row = (run_trader_arm if ARMS[name][1] == "trader" else run_arm)(name, ARMS[name], root)
            rows.append(row)
            print(json.dumps({k: row[k] for k in ("arm", "delivered", "receiver_model_requests_with_marker", "sender_exit")}),
                  "| sender:", (row["sender_tool_results"] or ["-"])[0][:220].replace("\n", " "), "| recv events:", row["receiver_events_after_send"][:6], flush=True)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    (OUT / f"probe-{version}.json").write_text(json.dumps({"binary_version": version, "measured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                                             "arms": rows}, indent=1) + "\n")


if __name__ == "__main__":
    main()
