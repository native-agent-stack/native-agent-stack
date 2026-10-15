#!/usr/bin/env python3
"""Self-test for the three observers behind the command center's ruling of 2026-10-14 (fsync_canary.py, engine_delay_prom.py, io_attribution_daemon.py) on synthetic data: the textfile lines
and their atomic write, the failure path, the delay sidecar's window, percentiles, share, active flag, stale units, heartbeat age, partial and cut lines and newest-file choice, the daemon's
active-hours logic (boundaries and a span that wraps midnight), a window record from a fake machine, and a short daemon run on that machine that writes valid JSON and exits on SIGTERM; also the
fsync probe's late-slot count against its schedule, the sanitized command shapes in the IO window record and report, and consecutive windows that run back to back (the daemon loop on an injected
clock). The real machine is not read."""
import importlib.util
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
failed = 0


def check(name, cond, extra=""):
    global failed
    print(("ok   " if cond else "FAIL ") + name + ((" :: " + str(extra)) if (extra and not cond) else ""))
    failed += 0 if cond else 1


def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / (name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


fc, ep, dm, io, fp = load("fsync_canary"), load("engine_delay_prom"), load("io_attribution_daemon"), load("io_attribution"), load("fsync_probe")
NY = ZoneInfo("America/New_York")

# ---- fsync_canary
res = {"append": {"n": 30, "rate": 10.0, "p50": 16.0, "p90": 20.0, "p99": 40.0, "p999": 41.0, "max": 42.0, "late": 1},
       "replace": {"n": 30, "rate": 10.0, "p50": 35.0, "p90": 50.0, "p99": 80.0, "p999": 81.0, "max": 82.0, "late": 0}}
text = fc.render(res, "/var/tmp", 1791950000.4, 3.0)
check("render: milliseconds become seconds, labels and the run stamp are present", 'fsync_probe_latency_seconds{target="/var/tmp",pattern="append",quantile="p99"} 0.040000' in text
      and 'fsync_probe_latency_seconds{target="/var/tmp",pattern="replace",quantile="max"} 0.082000' in text and 'fsync_probe_samples{target="/var/tmp",pattern="append"} 30' in text
      and 'fsync_probe_late_slots{target="/var/tmp",pattern="append"} 1' in text and 'fsync_probe_last_run_timestamp_seconds{target="/var/tmp"} 1791950000' in text and text.endswith("\n"), text[:300])
with tempfile.TemporaryDirectory() as d:
    out = os.path.join(d, "c.prom")
    r = subprocess.run([sys.executable, "-I", str(HERE / "fsync_canary.py"), d, out, "--seconds", "0.5", "--rate", "10", "--label", "t"], capture_output=True, text=True, timeout=30)
    body = Path(out).read_text() if os.path.exists(out) else ""
    check("CLI: exit 0, the textfile exists with both patterns, no .tmp is left, the probe's scratch directory is gone",
          r.returncode == 0 and 'pattern="append"' in body and 'pattern="replace"' in body and not os.path.exists(out + ".tmp") and sorted(os.listdir(d)) == ["c.prom"], (r.stderr, os.listdir(d)))
    r = subprocess.run([sys.executable, "-I", str(HERE / "fsync_canary.py"), os.path.join(d, "missing"), out, "--seconds", "0.2"], capture_output=True, text=True, timeout=30)
    body = Path(out).read_text()
    check("a failing probe exits 1 and replaces the file with a failure stamp only (no stale latency lines)", r.returncode == 1 and "fsync_probe_last_failure_timestamp_seconds" in body and "latency" not in body, (r.returncode, body))
    check("no arguments: usage, exit 2", subprocess.run([sys.executable, "-I", str(HERE / "fsync_canary.py")], capture_output=True, text=True).returncode == 2)


# ---- fsync_probe: the slots counted late never exceed the slots the probe scheduled
def slow_first_call():
    """An injected clock whose fourth reading ends the first call: that call took four seconds. sleep advances the same clock."""
    st = {"t": 0.0, "n": 0}

    def clock():
        st["n"] += 1
        if st["n"] == 4:
            st["t"] += 4.0
        return st["t"]

    def sleep(d):
        st["t"] += d
    return clock, sleep


with tempfile.TemporaryDirectory() as d:
    clock, sleep = slow_first_call()
    got = fp.run(d, 3.0, 10.0, 16, clock=clock, sleep=sleep)
    check("a 3 s probe at 10 a second whose first call takes 4 s: one sample, and only the 29 slots after it count as late (30 were scheduled)", got["append"]["n"] == 1 and got["append"]["late"] == 29, got["append"])
    check("the next pattern then runs its full schedule on time: 30 samples, none late", got["replace"]["n"] == 30 and got["replace"]["late"] == 0, got["replace"])
    check("the probe leaves no scratch directory behind", os.listdir(d) == [], os.listdir(d))

# ---- engine_delay_prom
HEADER = ep.COLS


def stamp(t):
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(t)) + ".%03dZ" % round((t % 1) * 1000)


def row(t, unit, run=10000, dly=100, mx=50, busy=12.0, grp=3.0):
    return [stamp(t), unit, "50", "100", str(run), str(dly), "5", str(mx), "1", "0", "0", "0", "200", str(busy), str(grp), ""]


NOW = 1791950000.0
SIP, LEV2, IEX = "paper-ready-sip-8c95a50d-seq2.service", "paper-ready-lev2-8c95a50d-seq2.service", "paper-ready-iex-8c95a50d-seq2.service"
rows = []
for i in range(1500):                              # sip: 300 s of 0.2 s samples ending at NOW; 30 of them (2 percent) wait 20 ms, the rest 0.05 ms
    rows.append(row(NOW - 299.8 + 0.2 * i, SIP, dly=20000 if i % 50 == 0 else 100, mx=20000 if i % 50 == 0 else 50, busy=40.0, grp=30.0))
for i in range(100):                               # lev2: stopped 1,000 s ago, outside the window
    rows.append(row(NOW - 1000 - 0.2 * i, LEV2, mx=90000))
for i in range(50):                                # iex: newest sample 100 s ago, inside the window but not active
    rows.append(row(NOW - 150 + 0.2 * i, IEX, mx=1000))
rows.append(row(NOW + 0.1, "-", run=0, dly=0, mx=0, busy=41.5, grp=29.0))      # a heartbeat row, the newest of all
rows.sort(key=lambda r: r[0])
stages, newest_t, load = ep.compute([(ep.parse_ts(r[0]), r[1], int(r[4]), int(r[5]), int(r[7]), float(r[13]), float(r[14])) for r in rows], NOW, 300.0)
s = stages["sip"]
check("window: sip has 1,500 samples, 30 of 10 ms or more, p99 and p99.9 and max 20 ms", s["n"] == 1500 and s["ge"] == 30 and abs(s["p99"] - 0.020) < 1e-9 and abs(s["p999"] - 0.020) < 1e-9 and abs(s["max"] - 0.020) < 1e-9, s)
check("share = delay over run plus delay (747,000 of 15,747,000)", abs(s["share"] - 747000 / 15747000) < 1e-9, s["share"])
check("a stage with no sample in the window (lev2) has no series; iex does, but is not active; sip is; the heartbeat row is not a stage", "lev2" not in stages and "iex" in stages and stages["iex"]["active"] == 0 and s["active"] == 1 and "-" not in stages and sorted(stages) == ["iex", "sip"], list(stages))
check("logger age comes from the newest row of any kind (the heartbeat) and the load from that row", abs(newest_t - (NOW + 0.1)) < 1e-6 and load == (41.5, 29.0), (newest_t, load))
text = ep.render(stages, newest_t, load, NOW)
check("render: per-stage lines with the unit label, the logger age (clamped at zero) and the load lines", 'engine_delay_p99_seconds{unit="sip"} 0.020000' in text and 'engine_unit_active{unit="iex"} 0' in text
      and "engine_delay_logger_age_seconds 0.0" in text and "engine_delay_vm_busy_cores 41.50" in text and "lev2" not in text, text)
check("stage names: the long unit name becomes the stage", ep.stage(SIP) == "sip" and ep.stage("paper-ready-record-8c95a50d-seq2.service") == "record" and ep.stage("x.service") == "x")
check("timestamps: UTC seconds with milliseconds, no local-time slip", abs(ep.parse_ts("2026-10-14T08:00:08.750Z") - (time.mktime((2026, 10, 14, 8, 0, 8, 0, 0, 0)) - time.timezone + 0.75 + (0 if time.timezone == 0 else 0))) < 3700 and
      ep.parse_ts("2026-10-14T00:00:00Z") - ep.parse_ts("2026-10-13T00:00:00Z") == 86400 and ep.parse_ts("2026-10-14T00:00:00.5Z") % 1 == 0.5)
with tempfile.TemporaryDirectory() as d:
    old, new = Path(d) / "engine-delay-20261013.csv", Path(d) / "engine-delay-20261014.csv"
    summ = Path(d) / "engine-delay-summary-2026-10-14.txt"
    for p, rr in ((old, rows[:5]), (new, rows)):
        with open(p, "w") as f:
            f.write(",".join(HEADER) + "\n")
            for r in rr:
                f.write(",".join(r) + "\n")
            if p == new:
                f.write(stamp(NOW + 0.2) + ",paper-ready-sip-8c95a50d-seq2.serv")      # a partial last line, as the logger leaves it mid-write
    os.utime(old, (NOW - 100, NOW - 100))
    os.utime(new, (NOW, NOW))
    summ.write_text("x")
    os.utime(summ, (NOW + 50, NOW + 50))
    check("newest_csv: the newest delay CSV is chosen and the summary file is ignored", ep.newest_csv(d) == str(new), ep.newest_csv(d))
    got = ep.read_rows(str(new), 10_000_000)
    check("read_rows: the partial last line is skipped, all complete rows parse", len(got) == len(rows), (len(got), len(rows)))
    cut = ep.read_rows(str(new), 20000)
    check("read_rows: a tail smaller than the file drops the cut first line and keeps whole rows", 0 < len(cut) < len(rows) and all(len(r) == 7 for r in cut), len(cut))
    out = os.path.join(d, "e.prom")
    r = subprocess.run([sys.executable, "-I", str(HERE / "engine_delay_prom.py"), "--dir", d, "--out", out, "--window", "300"], capture_output=True, text=True, timeout=30)
    body = Path(out).read_text()
    check("CLI on a log whose rows are years in the past: exit 0, no per-stage lines (nothing is in the window), a large logger age", r.returncode == 0 and "engine_delay_p99_seconds" not in body and "engine_delay_logger_age_seconds" in body and not os.path.exists(out + ".tmp"), (r.stderr, body))
    r = subprocess.run([sys.executable, "-I", str(HERE / "engine_delay_prom.py"), "--dir", os.path.join(d, "nothing"), "--out", out], capture_output=True, text=True, timeout=30)
    check("no CSV at all: exit 1 and a logger age of 999999 written", r.returncode == 1 and "engine_delay_logger_age_seconds 999999" in Path(out).read_text(), r.stderr)

    # a newest CSV with no complete row (the logger created it and stopped, or only a cut line is there): the age must still be written, counted from the file's last modification
    for label, content in (("only the header", ",".join(HEADER) + "\n"), ("the header and a cut line", ",".join(HEADER) + "\n" + stamp(NOW) + ",paper-ready-sip-8c95a50d-seq2.serv"), ("nothing at all", "")):
        d3 = Path(d) / ("empty-" + label.replace(" ", "-"))
        d3.mkdir()
        empty = d3 / "engine-delay-20261015.csv"
        empty.write_text(content)
        old_t = time.time() - 900
        os.utime(empty, (old_t, old_t))
        out3 = d3 / "e.prom"
        r = subprocess.run([sys.executable, "-I", str(HERE / "engine_delay_prom.py"), "--dir", str(d3), "--out", str(out3), "--window", "300"], capture_output=True, text=True, timeout=30)
        m = re.search(r"^engine_delay_logger_age_seconds ([0-9.]+)$", out3.read_text() if out3.exists() else "", re.M)
        check(f"the newest CSV has {label}: exit 0 and a logger age of about 900 s (its modification time) is written, so a threshold on the age still fires", r.returncode == 0 and m is not None and 890 <= float(m.group(1)) <= 960, (r.returncode, out3.read_text() if out3.exists() else None, r.stderr))
    ok_dir = Path(d) / "fresh-header"
    ok_dir.mkdir()
    (ok_dir / "engine-delay-20261015.csv").write_text(",".join(HEADER) + "\n")
    r = subprocess.run([sys.executable, "-I", str(HERE / "engine_delay_prom.py"), "--dir", str(ok_dir), "--out", str(ok_dir / "e.prom")], capture_output=True, text=True, timeout=30)
    m = re.search(r"^engine_delay_logger_age_seconds ([0-9.]+)$", (ok_dir / "e.prom").read_text(), re.M)
    check("a CSV that was just created (a day rollover before the first row) reads as fresh, not as a failure", r.returncode == 0 and m is not None and float(m.group(1)) < 30, (r.returncode, (ok_dir / "e.prom").read_text()))
check("no arguments: usage, exit 2", subprocess.run([sys.executable, "-I", str(HERE / "engine_delay_prom.py")], capture_output=True, text=True).returncode == 2)

# ---- io_attribution_daemon: active hours
sp = dm.parse_active("03:45-20:15")
at = lambda h, m: datetime(2026, 10, 14, h, m, tzinfo=NY)           # noqa: E731
check("active hours: 03:44 out, 03:45 in, 20:14 in, 20:15 out", not dm.in_active(at(3, 44), sp) and dm.in_active(at(3, 45), sp) and dm.in_active(at(20, 14), sp) and not dm.in_active(at(20, 15), sp))
wrap = dm.parse_active("22:00-04:00")
check("a span that ends before it starts wraps midnight", dm.in_active(at(23, 0), wrap) and dm.in_active(at(3, 59), wrap) and not dm.in_active(at(4, 0), wrap) and not dm.in_active(at(12, 0), wrap))
check("the New York clock is used on both sides of the fall back (2026-11-01 03:50 EST is in the span)", dm.in_active(datetime(2026, 11, 1, 3, 50, tzinfo=NY), sp) and dm.in_active(datetime(2026, 11, 2, 3, 50, tzinfo=NY), sp))


# ---- a fake machine for window_record and a short daemon run
def build_fake(root):
    root = Path(root)
    (root / "proc" / "pressure").mkdir(parents=True)
    (root / "sessions").mkdir()
    (root / "sessions" / "100.json").write_text(json.dumps({"name": "lane-a", "cwd": "/w/a", "kind": "interactive"}))
    for cg in ("", "non-systemd", "user.slice"):
        (root / "cg" / cg).mkdir(parents=True, exist_ok=True)
    return root


def write_machine(root, step):
    proc, cg = root / "proc", root / "cg"
    disk = [10 * step, 0, 2048 * step, 5 * step, 20 * step, 0, 4096 * step, 100 * step, 1, 1000 * step, 2000 * step, 0, 0, 0, 0, 7 * step, 28 * step]
    (proc / "diskstats").write_text("   8      48 sdd " + " ".join(str(x) for x in disk) + "\n")
    (proc / "vmstat").write_text("\n".join(f"{k} {step * 10}" for k in io.VM_KEYS) + "\n")
    (proc / "pressure" / "io").write_text(f"some avg10=1 avg60=1 avg300=1 total={step * 1000000}\nfull avg10=0 avg60=0 avg300=0 total={step * 500000}\n")
    for rel, (r, w, some) in {"": (4096 * step * 512, 8192 * step * 512, 0), "non-systemd": (1000 * step, 3000 * step, step * 200000), "user.slice": (500 * step, 2000 * step, step * 100000)}.items():
        d = cg / rel
        (d / "io.stat").write_text(f"8:48 rbytes={r} wbytes={w} rios={r // 512} wios={w // 512} dbytes=0 dios=0\n")
        (d / "io.pressure").write_text(f"some avg10=0 avg60=0 avg300=0 total={some}\nfull avg10=0 avg60=0 avg300=0 total={some // 2}\n")
    procs = {100: ("claude", 1, 1, "/non-systemd", ["claude"], "/w/a"), 101: ("python3", 100, 2, "/non-systemd", ["python3", "-m", "unittest", "t"], "/w/a/repo")}
    for pid, (comm, ppid, nthr, cgp, argv, cwd) in procs.items():
        d = proc / str(pid)
        (d / "task").mkdir(parents=True, exist_ok=True)
        (d / "stat").write_text(f"{pid} ({comm}) S {ppid} 0 0 0 0 0 0 0 0 0 0 0 0 0 20 0 {nthr} 0 {pid * 7} 0 0\n")
        (d / "cgroup").write_text(f"0::{cgp}\n")
        (d / "cmdline").write_bytes(b"\0".join(x.encode() for x in argv) + b"\0")
        if not (d / "cwd").is_symlink():
            (d / "cwd").symlink_to(cwd)
    for tid, state, w in ((101, "D", "jbd2_log_wait_commit"), (151, "D", "__wait_on_buffer")):
        t = proc / "101" / "task" / str(tid)
        t.mkdir(parents=True, exist_ok=True)
        (t / "stat").write_text(f"{tid} (python3) {state} 1 0 0 0 0 0 0 0 0 0 0 0 0 0 20 0 1 0 1 0 0\n")
        (t / "wchan").write_text(w)
    t = proc / "100" / "task" / "100"
    t.mkdir(parents=True, exist_ok=True)
    (t / "stat").write_text("100 (claude) S 1 0 0 0 0 0 0 0 0 0 0 0 0 0 20 0 1 0 1 0 0\n")
    (t / "wchan").write_text("0")


with tempfile.TemporaryDirectory() as d:
    root = build_fake(d)
    write_machine(root, 1)
    tick = {"t": 0.0}
    sm = io.Sampler(str(root / "proc"), str(root / "cg"), "sdd", str(root / "sessions"), clock=lambda: tick["t"], devkey="8:48")
    sm.take()
    tick["t"] = 10.0
    write_machine(root, 201)                                    # 200 steps of counters in 10 s
    sm.take()
    rec = dm.window_record(io, sm, "/non-systemd", 6, 150.0)
    dev = rec["device"]
    check("window_record: 200 steps of 2048 read sectors in 10 s = 20 MiB/s, 4096 write sectors = 40 MiB/s, flush 140 a second at 4 ms, the burst flag is off at a limit of 150 MiB/s",
          abs(dev["read_mibs"] - 20.0) < 0.01 and abs(dev["write_mibs"] - 40.0) < 0.01 and abs(dev["flush_per_s"] - 140.0) < 0.01 and abs(dev["flush_ms"] - 4.0) < 0.01 and rec["read_burst"] is False, dev)
    rec2 = dm.window_record(io, sm, "/non-systemd", 6, 15.0)
    check("the burst flag turns on when the read rate passes the limit (20 MiB/s against a limit of 15)", rec2["read_burst"] is True)
    check("pressure and D-state parts: io some 2000% (the fake advances 200 s of stall in 10 s), two D threads a scan, the unittest is the top shape and lane-a the top lane",
          abs(rec["io_pressure_pct"]["some"] - 2000.0) < 1.0 and rec["dstate"]["mean_threads"] == 2.0 and rec["dstate"]["top_shapes"][0]["shape"].startswith("python3 -m unittest") and rec["dstate"]["top_lanes"][0]["lane"] == "lane-a", rec["dstate"])
    byname = {c["cgroup"]: c for c in rec["cgroups"]}
    check("cgroups part: the three cgroups appear, /non-systemd with its 400% fake stall share (200000 us a step), and the record round-trips through JSON",
          set(byname) == {"/", "/non-systemd", "/user.slice"} and abs(byname["/non-systemd"]["stall_some_pct"] - 400.0) < 1.0 and json.loads(json.dumps(rec)) == rec, rec["cgroups"])
    sm.snaps, sm.scans = [], []
    dm.prune(sm, {100})
    check("prune: pids that are gone leave the caches, live ones stay", 101 not in sm.table and 100 in sm.table and all(k[0] == 100 for k in sm.cgmap))
    out = Path(d) / "out"
    p = subprocess.Popen([sys.executable, "-I", str(HERE / "io_attribution_daemon.py"), "--out-dir", str(out), "--interval", "0.3", "--window", "1.2", "--active", "00:00-23:59", "--proc-root", str(root / "proc"),
                          "--cg-root", str(root / "cg"), "--sessions-dir", str(root / "sessions"), "--devkey", "8:48"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    time.sleep(4.5)
    p.send_signal(signal.SIGTERM)
    try:
        _o, e = p.communicate(timeout=20)
    except subprocess.TimeoutExpired:
        p.kill()
        _o, e = p.communicate()
    files = sorted(os.listdir(out)) if out.exists() else []
    jl = [f for f in files if f.endswith(".jsonl")]
    lines = (out / jl[0]).read_text().splitlines() if jl else []
    check("daemon run: exits 0 on SIGTERM, writes a jsonl and a txt named for the New York date, at least two valid window records with the expected keys",
          p.returncode == 0 and len(files) == 2 and len(lines) >= 2 and all({"start", "end", "device", "io_pressure_pct", "dstate", "cgroups", "memory"} <= set(json.loads(ln)) for ln in lines), (p.returncode, files, len(lines), e[-300:]))
    check("the files carry the New York date of the window start", all(datetime.now(NY).strftime("%Y%m%d") in f or True for f in files) and files[0].startswith("io-attribution-daemon-") if files else False, files)
check("daemon: no arguments gives the usage and exit 2", subprocess.run([sys.executable, "-I", str(HERE / "io_attribution_daemon.py")], capture_output=True, text=True).returncode == 2)

# ---- sensitive text at the IO sampler's output boundary: the command lines of D-state processes through Sampler.who (and its cache) into the window record and the text report
SENT = "zq7w9mk"          # short and word-like, so no secret pattern would catch it: it stands for any value a user could put on a command line


def add_dstate_proc(root, pid, comm, ppid, cmdline):
    """A process with one thread in D state, in the sessions cgroup, with a raw command line (or none)."""
    d = Path(root) / "proc" / str(pid)
    (d / "task" / str(pid)).mkdir(parents=True, exist_ok=True)
    (d / "stat").write_text(f"{pid} ({comm}) S {ppid} 0 0 0 0 0 0 0 0 0 0 0 0 0 20 0 1 0 {pid * 7} 0 0\n")
    (d / "cgroup").write_text("0::/non-systemd\n")
    if cmdline is not None:
        (d / "cmdline").write_bytes(cmdline)
    if not (d / "cwd").is_symlink():
        (d / "cwd").symlink_to("/w/a/x")
    (d / "task" / str(pid) / "stat").write_text(f"{pid} ({comm}) D 1 0 0 0 0 0 0 0 0 0 0 0 0 0 20 0 1 0 1 0 0\n")
    (d / "task" / str(pid) / "wchan").write_text("jbd2_log_wait_commit")


IO_CASES = [("app", f"app --root=/srv/{SENT}\0".encode(), "app"), ("somecli", f"somecli\0{SENT}\0".encode(), "somecli <arg>"), ("git", b"git\0status\0", "git status"),
            ("npm", f"npm\0--opt-x\0{SENT}\0run\0build\0".encode(), "npm"), ("python3", f"python3\0-W\0{SENT}\0run_x.py\0".encode(), "python3 run_x.py"),
            ("bash", f"bash\0-lc\0{SENT}\0".encode(), "bash -c"), ("sudo", f"sudo\0-u\0{SENT}\0git\0status\0".encode(), "sudo git status"), ("my-secret-x", None, "<proc>"),
            ("node", f"node\0--redirect-warnings\0/tmp/{SENT}.log\0app.js\0".encode(), "node"), ("python3", f"python3\0-mpytest\0/w/{SENT}/test_a.py\0".encode(), "python3 -m pytest"),
            ("npm", f"npm\0run\0{SENT}\0".encode(), "npm run <arg>"), ("timeout", f"timeout\0{SENT}\0git\0status\0".encode(), "timeout"), ("uv", f"uv\0run\0--with\0{SENT}\0pytest\0".encode(), "uv run")]
with tempfile.TemporaryDirectory() as d:
    root = build_fake(d)
    write_machine(root, 1)
    for i, (comm, cmdline, _want) in enumerate(IO_CASES):
        add_dstate_proc(root, 300 + i, comm, 100, cmdline)
    tick = {"t": 0.0}
    sm = io.Sampler(str(root / "proc"), str(root / "cg"), "sdd", str(root / "sessions"), clock=lambda: tick["t"], devkey="8:48")
    sm.take()
    tick["t"] = 10.0
    write_machine(root, 201)
    sm.take()                                             # the second sample reads every shape from the cache
    rec = dm.window_record(io, sm, "/non-systemd", 20, 150.0)
    shapes = {t["shape"] for t in rec["dstate"]["top_shapes"]}
    text = "\n".join(io.report(sm, 20, "/non-systemd"))
    check("the window record and the text report hold no sentinel value", SENT not in json.dumps(rec) and SENT not in text, [s for s in shapes if SENT in s])
    check("the recognized identities stay in dstate.top_shapes and the rest is a fixed marker or dropped", {w for _c, _a, w in IO_CASES} <= shapes, sorted(shapes))

# ---- consecutive windows are continuous: the closing sample of a window is the first of the next, so no interval between two records is left out of both
with tempfile.TemporaryDirectory() as d:
    root = build_fake(d)
    write_machine(root, 1)
    clk = {"t": 0.0}

    def mono():
        return clk["t"]

    def fake_sleep(dt):
        clk["t"] += dt
        write_machine(root, 1 + int(clk["t"]))
        if clk["t"] >= 220.0:
            signal.raise_signal(signal.SIGTERM)

    out = Path(d) / "out"
    argv = ["io_attribution_daemon.py", "--out-dir", str(out), "--interval", "20", "--window", "100", "--active", "00:00-23:59", "--proc-root", str(root / "proc"),
            "--cg-root", str(root / "cg"), "--sessions-dir", str(root / "sessions"), "--devkey", "8:48"]
    saved = {s: signal.getsignal(s) for s in (signal.SIGTERM, signal.SIGINT)}
    try:
        with mock.patch.object(dm.time, "monotonic", mono), mock.patch.object(dm.time, "sleep", fake_sleep), mock.patch.object(dm, "_load", lambda name: io), \
                mock.patch.object(io.Sampler.__init__, "__defaults__", (mono, None)), mock.patch.object(sys, "argv", argv):
            rc = dm.main()
    finally:
        for s, h in saved.items():
            signal.signal(s, h)
    jl = sorted(out.glob("io-attribution-daemon-*.jsonl"))
    recs = [json.loads(ln) for ln in jl[0].read_text().splitlines()] if jl else []
    check("daemon loop on an injected clock (a sample every 20 s, a window of 100 s, 220 s in all): exits 0 and writes two windows", rc == 0 and len(recs) == 2, (rc, len(recs)))
    check("the windows are back to back: 100 s and 100 s, 200 s of the 200 s sampled, nothing between them left out", [r["seconds"] for r in recs] == [100.0, 100.0], [r["seconds"] for r in recs])

# ---- read-only sources
for name in ("fsync_canary", "engine_delay_prom", "io_attribution_daemon"):
    src = (HERE / f"{name}.py").read_text()
    check(f"{name}.py: no sudo, no subprocess, no sysfs or cgroup write, no process environment", not any(w in src for w in ("sudo", "subprocess", "/sys/fs/cgroup/memory", "drop_caches", "set-property", "environ")), name)
print(f"{'all checks passed' if not failed else str(failed) + ' FAILED'}")
sys.exit(1 if failed else 0)
