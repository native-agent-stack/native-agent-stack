#!/usr/bin/env python3
"""Runnable-set storm observer (passive and read-only; it writes only its own CSV, JSONL and log). Built on the command center's go of 2026-10-13T20:56:58Z for the proposal in
NEXT-STEPS-20261013.md section 3: the CPU-rate trigger of storm_snapshot.py reached 11 of Tuesday's 29 bursts; what hurts the engine is time spent runnable and waiting.

  storm_runq.py OUT.jsonl [--series SERIES.csv] [--running 40] [--polls 2] [--psi-pct 25] [--psi-window 0.5] [--poll 0.1] [--scans 3] [--scan-gap 0.05] [--min-gap 10]
                          [--max-hours 24] [--max-lines 4000] [--max-mb 100] [--once] [--proc-root /proc] [--sessions-dir ~/.claude/sessions] [--group /sys/fs/cgroup/non-systemd]

Every --poll seconds (10 Hz) it reads /proc/stat (procs_running: the threads running or ready to run, the whole VM; processes: the fork counter; the cpu line), /proc/pressure/cpu (the `some`
stall total) and the sessions group's cpu.stat, and appends one row to the series CSV (the calibration record: any trigger can be replayed offline against the delay log). A trigger is
procs_running at or above --running for --polls polls in a row, or the PSI some stall at or above --psi-pct percent of the last --psi-window seconds; at most one a --min-gap seconds.
On a trigger it scans every process (leader threads only) --scans times, --scan-gap seconds apart, and attributes what it saw:
  a process is running or runnable in a scan when its leader thread is in state R, when its CPU ticks advanced since the previous scan, or when it appeared (born) or vanished (gone)
  between scans; its weight is the larger of its CPU cores over the scan windows and its share of the scans in which that held. Processes shorter than the gap can still be missed, and
  a multi-threaded process whose leader sleeps counts only through its ticks; `leader_R` against `procs_running` in each record says how much of the runnable set the scan saw.
Attribution is as storm_snapshot.py does it: the `claude` ancestor names the lane (its own name and directory from ~/.claude/sessions/<pid>.json, never the key files), else the
sanitized command shape and working directory; raw command lines are never stored. The JSON keeps the fields storm_snapshot_summary.py and storm_attribution.py read
(utc, trigger_cores = procs_running at the trigger, measured_cores, lanes with cores = the weight above), so both tools work on it unchanged.
--once takes one snapshot now (a dry run) and prints it.
"""
import importlib.util
import json
import os
import re
import signal
import sys
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
HZ = os.sysconf("SC_CLK_TCK")
TOP_N = 80          # most processes whose cwd and command line are read per snapshot
SERIES_HEADER = "ts_utc,running,blocked,forks_total,busy_jiffies,idle_jiffies,psi_some_us,nsd_usec"


def _load_snapshotter():
    spec = importlib.util.spec_from_file_location("storm_snapshot", HERE / "storm_snapshot.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def arg(name, default=None):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def stamp(t=None):
    d = datetime.fromtimestamp(t, timezone.utc) if t is not None else datetime.now(timezone.utc)
    return d.strftime("%Y-%m-%dT%H:%M:%SZ")


def stamp_ms(t):
    return datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + f"{int(t * 1000) % 1000:03d}Z"


def read_proc_stat(root):
    """procs_running, procs_blocked, the fork counter and the cpu line's busy and idle jiffies (idle includes iowait)."""
    d = {"running": 0, "blocked": 0, "forks": 0, "busy": 0, "idle": 0}
    with open(f"{root}/stat") as f:
        for ln in f:
            if ln.startswith("cpu "):
                v = [int(x) for x in ln.split()[1:9]]
                v += [0] * (8 - len(v))
                d["idle"] = v[3] + v[4]
                d["busy"] = v[0] + v[1] + v[2] + v[5] + v[6] + v[7]
            elif ln.startswith("procs_running"):
                d["running"] = int(ln.split()[1])
            elif ln.startswith("procs_blocked"):
                d["blocked"] = int(ln.split()[1])
            elif ln.startswith("processes "):
                d["forks"] = int(ln.split()[1])
    return d


def read_psi_some(root):
    """The `some` stall total in microseconds of the system-wide cpu pressure file."""
    with open(f"{root}/pressure/cpu") as f:
        for ln in f:
            if ln.startswith("some"):
                return int(ln.rsplit("total=", 1)[1])
    raise OSError("no some line in pressure/cpu")


def read_usage_usec(group):
    with open(group + "/cpu.stat") as f:
        for ln in f:
            if ln.startswith("usage_usec"):
                return int(ln.split()[1])
    raise OSError("no usage_usec in cpu.stat")


def read_leader(root, pid):
    try:
        with open(f"{root}/{pid}/stat") as f:
            s = f.read()
        r = s.rindex(")")
        f2 = s[r + 2:].split()
        return {"comm": s[s.index("(") + 1:r], "state": f2[0], "ppid": int(f2[1]), "ticks": int(f2[11]) + int(f2[12]), "start": int(f2[19])}
    except (OSError, ValueError, IndexError):
        return None


def scan_leaders(root):
    out = {}
    for name in os.listdir(root):
        if name.isdigit():
            e = read_leader(root, name)
            if e:
                out[int(name)] = e
    return out


def read_detail(root, pid):
    """The working directory and command line of a process, or empty values when it is gone."""
    cwd, argv = None, []
    try:
        cwd = os.readlink(f"{root}/{pid}/cwd")
    except OSError:
        pass
    try:
        with open(f"{root}/{pid}/cmdline", "rb") as f:
            argv = [x.decode("utf-8", "replace") for x in f.read().split(b"\0")][:8]
    except OSError:
        pass
    return cwd, argv


def session_info(sess_dir, pid):
    """Name, directory and kind of a session from its own registry file; nothing else in that directory is opened or listed."""
    try:
        with open(Path(sess_dir) / f"{int(pid)}.json") as f:
            d = json.load(f)
        return {"name": str(d["name"])[:60] if d.get("name") else None, "cwd": d.get("cwd"), "kind": d.get("kind")}
    except (OSError, ValueError, KeyError, TypeError):
        return {}


class Trigger:
    """procs_running at or above `running` for `polls` polls in a row, or the PSI some stall at or above `psi_pct` percent of the last `window` seconds; one trigger a `min_gap` seconds."""

    def __init__(self, running, polls, psi_pct, window, min_gap):
        self.running, self.polls, self.psi_pct, self.window, self.min_gap = running, polls, psi_pct, window, min_gap
        self.run, self.last, self.hist = 0, None, deque()

    def feed(self, t, running, psi_total_us):
        """(reason or None, psi percent over the window). The PSI figure needs most of a window of history."""
        self.run = self.run + 1 if running >= self.running else 0
        self.hist.append((t, psi_total_us))
        while len(self.hist) > 1 and self.hist[1][0] <= t - self.window:
            self.hist.popleft()
        t0, p0 = self.hist[0]
        span = t - t0
        pct = 100.0 * (psi_total_us - p0) / (span * 1e6) if span >= 0.8 * self.window else 0.0
        why = []
        if self.run >= self.polls:
            why.append("running")
        if pct >= self.psi_pct:
            why.append("psi")
        if why and (self.last is None or t - self.last >= self.min_gap):
            self.last = t
            return "+".join(why), pct
        return None, pct


def take_snapshot(root, sess_dir, ss, scans=3, gap=0.05, sleep=time.sleep, clock=time.monotonic):
    """Scan the leader threads of every process `scans` times, `gap` seconds apart, and attribute the running or runnable ones. Returns the record without the trigger fields."""
    tabs, times, leader_r, active_n = [], [], [], []
    detail, key_of = {}, {}                 # detail: (pid, start) -> (cwd, argv); key_of: pid -> latest (pid, start)
    obs = {}                                 # (pid, start) -> {"seen": scans observed running, "first": (t, ticks), "last": (t, ticks), "comm", "ppid"}
    born = gone = 0
    for i in range(scans):
        if i:
            sleep(gap)
        t = clock()
        tab = scan_leaders(root)
        times.append(t)
        tabs.append(tab)
        prev = tabs[i - 1] if i else {}
        n_active = 0
        for pid, e in tab.items():
            k = (pid, e["start"])
            o = obs.get(k)
            was = prev.get(pid)
            same = was is not None and was["start"] == e["start"]
            is_born = i > 0 and not same
            advanced = same and e["ticks"] > was["ticks"]
            active = e["state"] == "R" or advanced or is_born
            if o is None:
                o = obs[k] = {"seen": 0, "first": (t, e["ticks"]), "last": (t, e["ticks"]), "comm": e["comm"], "ppid": e["ppid"]}
            o["last"] = (t, e["ticks"])
            if is_born:
                born += 1
            if active:
                o["seen"] += 1
                n_active += 1
                if k not in detail:
                    detail[k] = read_detail(root, pid)
        if i:
            for pid, was in prev.items():
                cur = tab.get(pid)
                if cur is None or cur["start"] != was["start"]:
                    k = (pid, was["start"])
                    obs[k]["seen"] += 1             # no detail is read for a process that is gone: its pid may already belong to another one (comm only unless it was read earlier)
                    gone += 1
                    n_active += 1
        leader_r.append(sum(1 for e in tab.values() if e["state"] == "R"))
        active_n.append(n_active)
    span = max(times[-1] - times[0], 1e-6)
    # a table for the ancestry walk and the aggregate: the latest info of every process seen in any scan
    table = {}
    heavy = []
    # a pid reused between scans appears twice (the old process and the new one): the live one (the larger start time) keeps the pid as its key, an older one gets a negative key
    for (pid, start), o in sorted(obs.items(), key=lambda kv: -kv[0][1]):
        t_a, k_a = o["first"]
        t_b, k_b = o["last"]
        cores = (k_b - k_a) / HZ / (t_b - t_a) if t_b > t_a else 0.0
        weight = max(o["seen"] / scans, cores) if o["seen"] else 0.0
        tkey = pid if pid not in table else -(len(table) + 1)
        table[tkey] = {"comm": o["comm"], "ppid": o["ppid"], "cores": weight}
        if weight > 0:
            heavy.append((weight, tkey, pid, start))
    for _w, tkey, pid, start in sorted(heavy, reverse=True)[:TOP_N]:
        cwd, argv = detail.get((pid, start), (None, []))
        table[tkey]["cwd"], table[tkey]["argv"] = cwd, argv
    roots = {ss.lane_of(p, table) for p, e in table.items() if e["cores"] >= ss.MIN_CORES} - {None}
    lanes = ss.aggregate(table, {r: session_info(sess_dir, r) for r in roots})
    return {"sample_s": round(span, 3), "scans": scans, "scan_ms": [round((times[i + 1] - times[i]) * 1000) for i in range(scans - 1)], "leader_R": leader_r, "active": active_n,
            "born": born, "gone": gone, "group_processes": len(table), "measured_cores": round(sum(e["cores"] for e in table.values() if e["cores"] >= ss.MIN_CORES), 2),
            "lanes": lanes}


WEIGHTS_NOTE = ("per process, the larger of its CPU cores over the scan windows and its share of the scans in which it was running, runnable, born or gone; "
                "lanes[].cores and shapes[].cores are these weights")


def main():
    if len(sys.argv) < 2 or sys.argv[1].startswith("--"):
        print(__doc__)
        return 2
    ss = _load_snapshotter()
    out = Path(sys.argv[1])
    series = Path(arg("--series", str(out.with_suffix("")) + "-series.csv"))
    log = out.with_suffix(".log")
    root, sess_dir = arg("--proc-root", "/proc"), arg("--sessions-dir", str(Path.home() / ".claude" / "sessions"))
    group = arg("--group", "/sys/fs/cgroup/non-systemd")
    running, polls, psi_pct, window = int(arg("--running", 40)), int(arg("--polls", 2)), float(arg("--psi-pct", 25)), float(arg("--psi-window", 0.5))
    poll, scans, scan_gap, min_gap = float(arg("--poll", 0.1)), int(arg("--scans", 3)), float(arg("--scan-gap", 0.05)), float(arg("--min-gap", 10))
    max_hours, max_lines, max_mb = float(arg("--max-hours", 24)), int(arg("--max-lines", 4000)), float(arg("--max-mb", 100))
    stop = {"now": False}
    signal.signal(signal.SIGTERM, lambda *_: stop.__setitem__("now", True))
    signal.signal(signal.SIGINT, lambda *_: stop.__setitem__("now", True))

    def note(s):
        with open(log, "a") as f:
            f.write(f"{stamp()} {s}\n")

    lines = {"n": 0}

    def snapshot(why, running_now, pct, busy):
        rec = take_snapshot(root, sess_dir, ss, scans, scan_gap)
        rec = {"utc": stamp(), "kind": "runq", "trigger": why, "trigger_cores": running_now, "procs_running": running_now, "psi_some_pct": round(pct, 1), "busy_cores": round(busy, 1),
               **rec, "weights": WEIGHTS_NOTE}
        if lines["n"] < max_lines:
            with open(out, "a") as f:
                f.write(json.dumps(rec) + "\n")
            lines["n"] += 1
        else:
            note(f"line cap {max_lines} reached; snapshot not written")
        return rec

    if "--once" in sys.argv:
        s = read_proc_stat(root)
        print(json.dumps(snapshot("once", s["running"], 0.0, 0.0), indent=1))
        return 0

    note(f"start: proc {root}, poll {poll:g} s, trigger procs_running >= {running} for {polls} polls or PSI some >= {psi_pct:g}% of {window:g} s, {scans} scans {scan_gap:g} s apart, "
         f"min gap {min_gap:g} s, cap {max_hours:g} h, series {series.name}, out {out.name}")
    trig = Trigger(running, polls, psi_pct, window, min_gap)
    series_new = not series.exists()
    sf = open(series, "a", buffering=1 << 16)
    if series_new:
        sf.write(SERIES_HEADER + "\n")
    deadline = time.monotonic() + max_hours * 3600
    next_beat, last_flush = time.monotonic() + 600, time.monotonic()
    prev = None
    snaps = polls_n = 0
    series_bytes = series.stat().st_size if series.exists() else 0
    next_t = time.monotonic()
    while not stop["now"] and time.monotonic() < deadline:
        next_t += poll
        delay = next_t - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        else:
            next_t = time.monotonic()           # fell behind (a long scan): do not burst to catch up
        try:
            wall, mono = time.time(), time.monotonic()
            st = read_proc_stat(root)
            psi = read_psi_some(root)
            try:
                nsd = read_usage_usec(group)
            except OSError:
                nsd = -1
            polls_n += 1
            if series_bytes < max_mb * 1e6:
                row = f"{stamp_ms(wall)},{st['running']},{st['blocked']},{st['forks']},{st['busy']},{st['idle']},{psi},{nsd}\n"
                sf.write(row)
                series_bytes += len(row)
            busy = 0.0
            if prev is not None and mono > prev[0]:
                busy = (st["busy"] - prev[1]) / HZ / (mono - prev[0])
            prev = (mono, st["busy"])
            why, pct = trig.feed(mono, st["running"], psi)
            if why:
                rec = snapshot(why, st["running"], pct, busy)
                snaps += 1
                top = rec["lanes"][0]["lane"] if rec["lanes"] else "none"
                note(f"snapshot {snaps}: {why}, procs_running {st['running']}, psi {pct:.0f}%, leader_R {rec['leader_R']}, top lane {top}")
            if mono - last_flush > 10:
                sf.flush()
                last_flush = mono
            if mono >= next_beat:
                note(f"heartbeat: alive, procs_running {st['running']}, {snaps} snapshots, {polls_n} polls, series {series_bytes / 1e6:.1f} MB")
                next_beat += 600
        except Exception as ex:                  # never die on a transient /proc race
            note(f"error: {type(ex).__name__}: {ex}")
            time.sleep(poll)
    sf.close()
    note(f"stopped: {'signal' if stop['now'] else 'hour cap'}; {snaps} snapshots, {polls_n} polls")
    return 0


if __name__ == "__main__":
    sys.exit(main())
