#!/usr/bin/env python3
"""Does a RUNNING dontAsk -p session pick up a change to crossSessionInbound in its user settings file?
live_reload_probe.py OUTDIR BINARY MOCK

Same harness as inbound_probe.py (scratch HOME and XDG_RUNTIME_DIR, loopback stand-ins, zero spend). The receiver has the
account-C trader's shape (-p, prompt on stdin, --tools Bash,Read, dontAsk) and sleeps 45 seconds mid-run; the sender
runs in bypass mode. The scratch user settings file is rewritten while the receiver runs.
  L1  accept at start, removed before the send            -> held if the change is picked up live
  L2  nothing at start, accept written before the send    -> delivered if the change is picked up live
  L3  nothing at start, the send, then accept written     -> a held message released if the change is picked up live
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

OUT, BINARY, MOCK_PATH = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
sys.argv = [sys.argv[0], str(OUT), BINARY, MOCK_PATH]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import inbound_probe as ip  # noqa: E402  (mock, env, kinds and logged_with; its main() is not run)

ARMS = {"L1-accept-removed-before-send": ("accept", "remove", "before"),
        "L2-accept-added-before-send": (None, "add", "before"),
        "L3-accept-added-after-send": (None, "add", "after")}


def write_user(home, value):
    path = home / ".claude" / "settings.json"
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps({"crossSessionInbound": value} if value else {}))
    os.replace(tmp, path)


def run(name, spec, root):
    start_value, change, when = spec
    base = root / name
    home, runtime, work = base / "h", Path(tempfile.mkdtemp(prefix="r", dir="/var/tmp")), base / "w"
    (home / ".claude").mkdir(parents=True)
    work.mkdir(parents=True)
    os.chmod(runtime, 0o700)
    write_user(home, start_value)
    marker, receiver_name = f"PROBEMARK-{name}", f"probe-recv-{name[:2].lower()}"
    rmock, rport, rlog = ip.mock(base, "receiver", [{"command": "sleep 45", "description": "wait as the trader does"}])
    smock, sport, _ = ip.mock(base, "sender", [{"tool": "SendMessage", "to": receiver_name, "summary": "probe",
                                                "message": f"{marker}: reply with the word ok."}])
    (base / "prompt.md").write_text("Run the session.\n")
    rargs = [BINARY, "-p", "--model", "claude-haiku-5-5", "--name", receiver_name, *ip.TRADER, "--output-format", "stream-json", "--verbose"]
    with open(base / "prompt.md") as prompt:
        receiver = subprocess.Popen(rargs, cwd=work, env=ip.env(home, runtime, rport), stdin=prompt, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, text=True)
    timeline = []
    try:
        time.sleep(6)

        def flip():
            write_user(home, "accept" if change == "add" else None)
            timeline.append(("user settings rewritten", "accept" if change == "add" else "(no value)", round(time.time() - t0, 1)))

        t0 = time.time()
        if when == "before":
            flip()
            time.sleep(6)
        sargs = [BINARY, "-p", "send the probe message", "--output-format", "stream-json", "--verbose", "--model", "claude-haiku-5-5",
                 "--name", f"probe-send-{name[:2].lower()}", *ip.BYPASS]
        sent = subprocess.run(sargs, cwd=work, env=ip.env(home, runtime, sport), capture_output=True, text=True, timeout=120)
        timeline.append(("message sent", sent.returncode, round(time.time() - t0, 1)))
        if when == "after":
            time.sleep(4)
            flip()
        out, err = receiver.communicate(timeout=150)
        events = []
        for line in out.splitlines():
            try:
                events.append(json.loads(line))
            except ValueError:
                pass
        requests = ip.logged_with(rlog, marker)
        row = {"arm": name, "start_value": start_value, "change": change, "change_relative_to_send": when, "timeline": timeline,
               "receiver_events": [k for k in ip.kinds(events) if k.startswith(("system:peer", "result"))],
               "receiver_exit": receiver.returncode, "receiver_model_requests_with_marker": requests, "delivered": requests > 0}
    finally:
        if receiver.poll() is None:
            receiver.kill()
        rmock.terminate()
        smock.terminate()
        shutil.rmtree(runtime, ignore_errors=True)
    return row


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix="inbound-reload-", dir="/var/tmp"))
    version = subprocess.run([BINARY, "--version"], capture_output=True, text=True, stdin=subprocess.DEVNULL).stdout.split()[0]
    rows = []
    try:
        for name, spec in ARMS.items():
            row = run(name, spec, root)
            rows.append(row)
            print(json.dumps(row), flush=True)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    (OUT / f"live-reload-{version}.json").write_text(json.dumps({"binary_version": version, "measured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                                                  "arms": rows}, indent=1) + "\n")


if __name__ == "__main__":
    main()
