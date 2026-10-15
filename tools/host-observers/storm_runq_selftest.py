#!/usr/bin/env python3
"""Self-test for storm_runq.py on a fake /proc tree and a fake sessions directory (the real /proc is read only by the last two checks, which also run the tool on the live machine for one
second): the trigger (running for N polls, PSI over a window, both, the minimum gap, the history needed), the scan attribution (a process in state R, one whose ticks advanced, one born
between scans, one gone, a reused pid, an idle one that weighs nothing, the claude ancestor naming the lane from its own registry file, the shape sanitizer), the record fields the two
summary tools read, the series CSV, the log, and that the tool opens no .key file and lists only the process directory."""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOL = HERE / "storm_runq.py"
spec = importlib.util.spec_from_file_location("storm_runq", TOOL)
rq = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rq)
ss = rq._load_snapshotter()
failed = 0


def check(name, cond, extra=""):
    global failed
    print(("ok   " if cond else "FAIL ") + name + ((" :: " + str(extra)) if (extra and not cond) else ""))
    failed += 0 if cond else 1


class Fake:
    """A fake /proc: stat, pressure/cpu and one directory per pid with stat, cmdline and a cwd symlink."""

    def __init__(self, root):
        self.root = Path(root)
        (self.root / "pressure").mkdir(parents=True, exist_ok=True)
        self.procs = {}
        self.running, self.psi, self.forks = 5, 0, 1000
        self.write_global()

    def write_global(self):
        (self.root / "stat").write_text(f"cpu  100 0 50 800 20 0 5 0 0 0\ncpu0 1 1 1 1 1 1 1 1 1 1\nintr 1 2 3\nprocesses {self.forks}\nprocs_running {self.running}\nprocs_blocked 2\n")
        (self.root / "pressure" / "cpu").write_text(f"some avg10=0.00 avg60=0.00 avg300=0.00 total={self.psi}\nfull avg10=0.00 avg60=0.00 avg300=0.00 total=0\n")

    def proc(self, pid, comm, state, ppid, ticks, start, cmdline=None, cwd=None):
        d = self.root / str(pid)
        d.mkdir(exist_ok=True)
        # fields after the comm: state ppid pgrp session tty tpgid flags minflt cminflt majflt cmajflt utime stime cutime cstime prio nice num_threads itrealvalue starttime
        (d / "stat").write_text(f"{pid} ({comm}) {state} {ppid} 0 0 0 0 0 0 0 0 0 {ticks} 0 0 0 20 0 1 0 {start} 0 0\n")
        if cmdline is not None:
            (d / "cmdline").write_bytes(b"\0".join(c.encode() for c in cmdline) + b"\0")
        if cwd is not None:
            link = d / "cwd"
            if link.is_symlink():
                link.unlink()
            link.symlink_to(cwd)
        self.procs[pid] = d

    def kill(self, pid):
        d = self.procs.pop(pid)
        for p in d.iterdir():
            p.unlink()
        d.rmdir()


def sessions(tmp):
    sd = Path(tmp) / "sessions"
    sd.mkdir()
    (sd / "100.json").write_text(json.dumps({"name": "lane-a", "cwd": "/w/a", "kind": "interactive", "sessionId": "x"}))
    (sd / "100.deadbeef.key").write_text("SECRET-DO-NOT-READ")
    return sd


# ---- trigger
T = rq.Trigger(40, 2, 25.0, 0.5, 10.0)
r = [T.feed(0.0 + 0.1 * i, 10, 0)[0] for i in range(6)]
check("quiet polls never trigger", r == [None] * 6, r)
check("one poll at 40 is not enough, the second in a row triggers 'running'", T.feed(1.0, 41, 0)[0] is None and T.feed(1.1, 41, 0)[0] == "running")
check("the minimum gap holds the next trigger back (9.9 s) and releases it at 10 s", T.feed(1.2, 60, 0)[0] is None and T.feed(10.9, 60, 0)[0] is None and T.feed(11.1, 60, 0)[0] == "running")
T = rq.Trigger(40, 2, 25.0, 0.5, 10.0)
out = [T.feed(0.1 * i, 5, 150_000 * (i // 5)) for i in range(0, 16)]   # +150 ms of stall per 0.5 s = 30 percent, in steps
why = [o[0] for o in out]
check("PSI: 30 percent of a 0.5 s window triggers 'psi' once enough history exists and not before", why[:5] == [None] * 5 and "psi" in why[5:], why)
T = rq.Trigger(40, 2, 25.0, 0.5, 10.0)
o = [T.feed(0.1 * i, 5, 10_000 * i) for i in range(12)]     # 10 ms of stall per 100 ms: 10 percent of every window
check("PSI: 10 percent never triggers; the percentage is reported", all(x[0] is None for x in o) and 8 < o[-1][1] < 12, o[-1])
T = rq.Trigger(40, 1, 25.0, 0.5, 10.0)
o = [T.feed(0.1 * i, 50, 200_000 * i) for i in range(12)]
check("both conditions give 'running+psi'", any(x[0] == "running+psi" for x in o) or o[0][0] == "running", [x[0] for x in o])

# ---- attribution on a fake tree
with tempfile.TemporaryDirectory() as tmp:
    sd = sessions(tmp)
    fk = Fake(Path(tmp) / "proc")
    fk.proc(1, "systemd", "S", 0, 10, 1)
    fk.proc(100, "claude", "S", 1, 500, 10, ["/home/example/versions/2.1.296", "--resume", "abc"], "/w/a")
    fk.proc(101, "bash", "S", 100, 20, 11, ["bash"], "/w/a/repo")
    fk.proc(102, "python3", "R", 101, 1000, 12, ["python3", "-m", "pytest", "tests/test_a.py", "--token", "zzzzzzzzzzzz-sentinel"], "/w/a/repo")
    fk.proc(200, "git", "R", 101, 50, 13, ["git", "status"], "/w/a/repo")
    fk.proc(400, "idle-daemon", "S", 1, 70, 14, ["idle-daemon"], "/srv")
    # a process that rewrote its title into one string (chrome): flags, a profile directory and a key-looking value must not reach the record
    (Path(tmp) / "proc").mkdir(exist_ok=True)
    fk.proc(600, "chrome", "R", 100, 900, 16, None, "/tmp/p")
    (fk.root / "600" / "cmdline").write_bytes(b"/opt/google/chrome/puppeteer_dev_chrome_profile-25P6Eo --change-stack-guard-on=sk-abcdefghij123456\0")
    fk.proc(500, "oldproc", "S", 1, 5, 15, ["oldproc"], "/srv")
    fk.proc(700, "worker", "S", 100, 100, 17, ["worker", "--once"], "/w/a/jobs")      # asleep at every scan, but its CPU ticks move between scans 1 and 2
    step = {"n": 0}
    clock_t = {"t": 0.0}

    def clock():
        return clock_t["t"]

    def sleep(dt):
        """Between scans: advance the clock by dt and change the tree."""
        step["n"] += 1
        clock_t["t"] += dt
        if step["n"] == 1:      # before scan 2: git dies, a shell is born and runs, pid 500 is reused, the pytest process keeps running (10 ticks in 0.05 s = 2 cores)
            fk.proc(102, "python3", "R", 101, 1010, 12, ["python3", "-m", "pytest", "tests/test_a.py", "--token", "zzzzzzzzzzzz-sentinel"], "/w/a/repo")
            fk.kill(200)
            fk.proc(700, "worker", "S", 100, 105, 17, ["worker", "--once"], "/w/a/jobs")
            fk.proc(300, "sh", "R", 1, 3, 90, ["sh", "-c", "echo secret-code-here"], "/tmp/work")
            fk.proc(500, "newproc", "S", 1, 1, 99, ["newproc"], "/srv")
        elif step["n"] == 2:    # before scan 3: pytest runs on, the shell is still runnable
            fk.proc(102, "python3", "R", 101, 1020, 12, ["python3", "-m", "pytest", "tests/test_a.py", "--token", "zzzzzzzzzzzz-sentinel"], "/w/a/repo")
            fk.proc(300, "sh", "R", 1, 4, 90, ["sh", "-c", "echo secret-code-here"], "/tmp/work")

    rec = rq.take_snapshot(str(fk.root), str(sd), ss, scans=3, gap=0.05, sleep=sleep, clock=clock)
    lanes = {L["lane"]: L for L in rec["lanes"]}
    check("three scans, 50 ms apart on the injected clock", rec["scans"] == 3 and rec["scan_ms"] == [50, 50] and abs(rec["sample_s"] - 0.1) < 1e-9, rec)
    check("leader_R counts the processes in state R per scan (102, 200 and 600; 102, 300 and 600; 102, 300 and 600)", rec["leader_R"] == [3, 3, 3], rec["leader_R"])
    check("born is the shell and the reused pid; gone is git and the old pid 500", rec["born"] == 2 and rec["gone"] == 2, (rec["born"], rec["gone"]))
    check("the claude ancestor names the lane from its own registry file", "lane-a" in lanes and lanes["lane-a"]["root_cwd"] == "/w/a" and lanes["lane-a"]["kind"] == "interactive", list(lanes))
    pt = next(s for s in lanes["lane-a"]["top"] if s["shape"] == "python3 -m pytest")
    check("the pytest process weighs its CPU cores (20 ticks over 0.1 s = 2.0 at HZ 100), above its 1.0 share of scans", abs(pt["cores"] - 20 / rq.HZ / 0.1) < 0.01 and pt["cwds"] == ["/w/a/repo"], pt)
    gt = next(s for s in lanes["lane-a"]["top"] if s["shape"] == "git status")
    check("git, seen running in scan 1 and gone in scan 2, weighs 2 of 3 scans", abs(gt["cores"] - 2 / 3) < 0.01, gt)
    wk = next((s for s in lanes["lane-a"]["top"] if s["shape"] == "worker"), None)
    check("a process asleep at every scan whose ticks advanced between two scans is counted (5 ticks over 0.1 s = 0.5 cores)", wk is not None and abs(wk["cores"] - 0.5) < 0.01, lanes["lane-a"]["top"])
    un = lanes.get("unattributed (no claude ancestor in the group)")
    sh = next((s for s in un["top"] if s["shape"] == "sh -c"), None) if un else None
    check("the shell born between scans has no claude ancestor, is shaped 'sh -c' (the code dropped) and weighs 2 of 3", sh is not None and abs(sh["cores"] - 2 / 3) < 0.01, un)
    names = [s["shape"] for L in rec["lanes"] for s in L["top"]]
    check("the reused pid counts as a new process that ran (born) and the old one as gone: both weigh a scan", "oldproc" in names and "newproc" in names, names)
    check("the idle process weighs nothing and is not listed", "idle-daemon" not in names, names)
    check("a process that rewrote its title into one string is shaped by the kernel's name only (no profile directory, no flag, no key)", "chrome" in names
          and not any("puppeteer" in n or "stack-guard" in n for n in names), names)
    blob = json.dumps(rec)
    check("no token, no command-line text, no .key content in the record", "zzzzzzzzzzzz" not in blob and "puppeteer_dev" not in blob and "secret-code" not in blob and "SECRET-DO-NOT-READ" not in blob and "tests/test_a" not in blob, blob[:300])
    check("measured_cores adds the weights of the listed processes", abs(rec["measured_cores"] - sum(L["cores"] for L in rec["lanes"])) < 0.05, (rec["measured_cores"], [L["cores"] for L in rec["lanes"]]))

    # ---- the CLI on the fake tree: series, jsonl, log
    fk.running, fk.psi = 60, 0
    fk.write_global()
    outp = Path(tmp) / "o" / "runq.jsonl"
    outp.parent.mkdir()
    r = subprocess.run([sys.executable, "-I", str(TOOL), str(outp), "--proc-root", str(fk.root), "--sessions-dir", str(sd), "--group", str(Path(tmp) / "nogroup"), "--max-hours", "0.0006",
                        "--poll", "0.1", "--running", "40", "--polls", "2", "--min-gap", "30"], capture_output=True, text=True, timeout=60)
    series = Path(str(outp.with_suffix("")) + "-series.csv")
    lines = outp.read_text().splitlines() if outp.exists() else []
    check("the CLI ran for its cap and exited 0", r.returncode == 0, r.stdout[-300:] + r.stderr[-300:])
    check("one snapshot in the cap (the minimum gap of 30 s), with the fields the summary tools read", len(lines) == 1 and all(k in json.loads(lines[0]) for k in
          ("utc", "trigger_cores", "measured_cores", "lanes", "kind", "trigger", "procs_running", "leader_R", "weights")) and json.loads(lines[0])["trigger_cores"] == 60, lines[:1])
    rows = series.read_text().splitlines() if series.exists() else []
    check("the series CSV has the header and about one row per 0.1 s", len(rows) >= 15 and rows[0] == rq.SERIES_HEADER and rows[1].split(",")[1] == "60", rows[:3] + [str(len(rows))])
    check("the series row carries blocked, the forks counter, the cpu jiffies (busy 155, idle 820 with iowait) and the PSI total; the missing group gives -1", rows[1].split(",")[2:] == ["2", "1000", "155", "820", "0", "-1"], rows[1])
    lg = outp.with_suffix(".log").read_text()
    check("the log has the start line, a snapshot line and the stop line", "start:" in lg and "snapshot 1: running" in lg and "stopped: hour cap" in lg, lg)

    # ---- the existing summary tools read the record unchanged
    sm = subprocess.run([sys.executable, "-I", str(HERE / "storm_snapshot_summary.py"), str(outp)], capture_output=True, text=True, timeout=30)
    check("storm_snapshot_summary.py reads the record unchanged and names the lane", sm.returncode == 0 and "lane-a" in sm.stdout and "1 snapshots" in sm.stdout, sm.stdout[:500])

    # ---- --once prints a record and writes the file once
    o2 = Path(tmp) / "once.jsonl"
    r = subprocess.run([sys.executable, "-I", str(TOOL), str(o2), "--proc-root", str(fk.root), "--sessions-dir", str(sd), "--once"], capture_output=True, text=True, timeout=30)
    d = json.loads(r.stdout) if r.returncode == 0 else {}
    check("--once: a dry run prints one record with trigger 'once'", r.returncode == 0 and d.get("trigger") == "once" and d.get("kind") == "runq", r.stdout[:200] + r.stderr[-200:])

    r = subprocess.run([sys.executable, "-I", str(TOOL)], capture_output=True, text=True, timeout=30)
    check("no arguments: usage, exit 2", r.returncode == 2 and "OUT.jsonl" in r.stdout)

# ---- sensitive text at this tool's output boundary: the classes of storm_snapshot_selftest.py through take_snapshot on a fake tree, serialized as the tool writes them
SENT = "zq7w9mk"          # short and word-like, so no secret pattern would catch it: it stands for any value a user could put on a command line
with tempfile.TemporaryDirectory() as tmp:
    sd = sessions(tmp)
    fk = Fake(Path(tmp) / "proc")
    fk.proc(1, "systemd", "S", 0, 10, 1)
    cases = [("app", [f"app --root=/srv/{SENT}"], "app"), ("somecli", ["somecli", SENT], "somecli <arg>"), ("git", ["git", "status"], "git status"),
             ("npm", ["npm", "--opt-x", SENT, "run", "build"], "npm"), ("python3", ["python3", "-W", SENT, "run_x.py"], "python3 run_x.py"), ("bash", ["bash", "-lc", SENT], "bash -c"),
             ("sudo", ["sudo", "-u", SENT, "git", "status"], "sudo git status"), ("my-secret-x", None, "<proc>"),
             ("node", ["node", "--redirect-warnings", f"/tmp/{SENT}.log", "app.js"], "node"), ("python3", ["python3", "-mpytest", f"/w/{SENT}/test_a.py"], "python3 -m pytest"),
             ("npm", ["npm", "run", SENT], "npm run <arg>"), ("timeout", ["timeout", SENT, "git", "status"], "timeout"), ("uv", ["uv", "run", "--with", SENT, "pytest"], "uv run")]
    for i, (comm, cmdline, _want) in enumerate(cases):
        fk.proc(300 + 10 * i, "claude", "S", 1, 5, 30 + i, ["claude"], "/w/a")
        fk.proc(301 + 10 * i, comm, "R", 300 + 10 * i, 100, 130 + i, cmdline, "/w/a/x")
    tick = {"t": 0.0}

    def clock2():
        tick["t"] += 0.05
        return tick["t"]

    rec = rq.take_snapshot(str(fk.root), str(sd), ss, scans=3, gap=0.05, sleep=lambda dt: None, clock=clock2)
    shapes = sorted(s["shape"] for L in rec["lanes"] for s in L["top"])
    check("the serialized record holds no sentinel value", SENT not in json.dumps(rec), [s for s in shapes if SENT in s])
    check("the recognized identities stay and the rest is a fixed marker or dropped", shapes == sorted(w for _c, _a, w in cases), shapes)

# ---- a machine with only three processes: the scan sees them, and the live check's predicate (counted here, not by the tool) accepts it
def count_procs(root="/proc"):
    return sum(1 for n in os.listdir(root) if n.isdigit())


def saw_processes(seen, before, after, slack=25):
    """The scan counted the machine's processes: within one scan's churn of what /proc held before and after, counted by this test and not by the tool.
    The earlier `group_processes > 50` was true only on a machine with a large process population and failed on a small container or runner."""
    lo, hi = min(before, after), max(before, after)
    return max(1, lo - slack) <= seen <= hi + slack


with tempfile.TemporaryDirectory() as tmp:
    sd = sessions(tmp)
    fk = Fake(Path(tmp) / "proc")
    fk.proc(1, "systemd", "S", 0, 10, 1)
    fk.proc(100, "bash", "R", 1, 500, 10, ["bash"], "/w/a")
    fk.proc(101, "python3", "R", 100, 100, 11, ["python3", "x.py"], "/w/a")
    rec = rq.take_snapshot(str(fk.root), str(sd), ss, scans=3, gap=0.05, sleep=lambda dt: None, clock=clock2)
    check("a three-process machine: the scan saw all three and the live predicate accepts it", rec["scans"] == 3 and rec["group_processes"] == 3 and saw_processes(rec["group_processes"], count_procs(fk.root), count_procs(fk.root)), rec)
    check("the predicate rejects a scan that saw nothing of a large machine, and one that saw far more than exists", not saw_processes(0, 300, 310) and not saw_processes(900, 300, 310) and saw_processes(305, 300, 310))

# ---- the real machine for one second (read-only): one poll loop with a trigger set low, so the real scan runs once
with tempfile.TemporaryDirectory() as tmp:
    outp = Path(tmp) / "live.jsonl"
    procs_before = count_procs()
    r = subprocess.run([sys.executable, "-I", str(TOOL), str(outp), "--max-hours", "0.0006", "--running", "1", "--polls", "1", "--min-gap", "60"], capture_output=True, text=True, timeout=90)
    procs_after = count_procs()
    lines = outp.read_text().splitlines() if outp.exists() else []
    d = json.loads(lines[0]) if lines else {}
    check("live: the real /proc, one snapshot on a trigger set low, exit 0, and the scan saw the machine's processes", r.returncode == 0 and len(lines) == 1 and d.get("scans") == 3
          and saw_processes(d.get("group_processes", -1), procs_before, procs_after), r.stderr[-300:] + str(d)[:200] + str((procs_before, procs_after)))
    texts = [L["lane"] for L in d.get("lanes", [])] + [s["shape"] for L in d.get("lanes", []) for s in L["top"]]
    opaque = [x for x in texts if __import__("re").search(r"[A-Za-z0-9+/_-]{28,}", x)]
    check("live: no long opaque string in a lane name or a command shape, and no key-looking text in the record", not opaque and "sk-" not in json.dumps(d), opaque[:3])
    check("live: the real runnable count is a positive integer and leader_R has three entries", isinstance(d.get("procs_running"), int) and d["procs_running"] >= 1 and len(d.get("leader_R", [])) == 3, d.get("leader_R"))
    series = Path(str(outp.with_suffix("")) + "-series.csv")
    check("live: the series file has rows from the real /proc/stat", series.exists() and len(series.read_text().splitlines()) >= 5, series.exists())

# ---- source: no key files, one directory listing (the process directory), only its own outputs opened for writing
src = TOOL.read_text()
check("source: no .key string, and os.listdir appears exactly once", ".key" not in src and src.count("os.listdir") == 1, src.count("os.listdir"))
idx = src.index("os.listdir")
check("source: os.listdir is inside scan_leaders", src.rfind("def ", 0, idx) == src.index("def scan_leaders"), src[src.rfind("def ", 0, idx):src.rfind("def ", 0, idx) + 40])
check("source: opened for writing or appending only: the log, the JSONL and the series", len([ln for ln in src.splitlines() if 'open(' in ln and ('"a"' in ln or '"w"' in ln)]) == 3, [ln for ln in src.splitlines() if 'open(' in ln and ('"a"' in ln or '"w"' in ln)])
print(f"{'all checks passed' if not failed else str(failed) + ' FAILED'}")
sys.exit(1 if failed else 0)
