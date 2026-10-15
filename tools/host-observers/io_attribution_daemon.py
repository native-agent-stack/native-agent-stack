#!/usr/bin/env python3
"""Long-running IO attribution sampler for the trading day (read-only; it writes only its own two files per day). It runs tools/io_attribution.py's Sampler every --interval seconds inside
the active hours (default 03:45 to 20:15 New York time, the series window plus margin), and every --window seconds appends one JSON line and one text report for that window.

  io_attribution_daemon.py --out-dir DIR [--interval 20] [--window 300] [--active 03:45-20:15] [--dev sdd] [--top 6] [--group /non-systemd] [--max-days 0]

Files: DIR/io-attribution-daemon-YYYYMMDD.jsonl (one record per window) and .txt (the full report of each window), the date being the New York date of the window's start. Outside the active
hours it sleeps (a check every 30 s). Cost: one sample reads the stat of every process and thread (about 0.5 s of CPU), so the default 20 s interval is about 2.5% of a core; run it idle-class.
A window record has: device throughput, IOPS, await, flush requests and time, discards, busy share and queue; system IO pressure; refaults and swap; the cgroups by their own bytes with their
stall share; the D-state mean per scan and by wait class; the top command shapes and lanes by share of the D-state time; and `read_burst` when the window's device read rate exceeds
--burst-mib (default 150 MiB/s), the shape of the 2026-10-13 18:28Z surge that filled the cache. SIGTERM ends it after the current window's record is written.
"""
import importlib.util
import json
import os
import signal
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
NY = ZoneInfo("America/New_York")


def arg(name, default=None):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def _load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / (name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def parse_active(s):
    a, b = s.split("-")
    h1, m1 = (int(x) for x in a.split(":"))
    h2, m2 = (int(x) for x in b.split(":"))
    return h1 * 60 + m1, h2 * 60 + m2


def in_active(now_local, span):
    """True when the local time of day is inside [start, end); a span that ends before it starts wraps midnight."""
    m = now_local.hour * 60 + now_local.minute
    lo, hi = span
    return lo <= m < hi if lo < hi else (m >= lo or m < hi)


def window_record(io, sm, group, top, burst_mib):
    """One JSON-able record from the sampler's snapshots (at least two) and scans."""
    a, b = sm.snaps[0], sm.snaps[-1]
    dt = max(b["t"] - a["t"], 1e-6)
    rec = {"start": datetime.fromtimestamp(a["wall"], tz=ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%SZ"), "end": datetime.fromtimestamp(b["wall"], tz=ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "seconds": round(dt, 1), "samples": len(sm.snaps)}
    if a["dev"] and b["dev"]:
        d = [y - x for x, y in zip(a["dev"], b["dev"])]
        rec["device"] = {"read_mibs": round(d[2] * 512 / dt / 2**20, 2), "write_mibs": round(d[6] * 512 / dt / 2**20, 2), "read_iops": round(d[0] / dt), "write_iops": round(d[4] / dt),
                         "read_await_ms": round(d[3] / max(d[0], 1), 2), "write_await_ms": round(d[7] / max(d[4], 1), 2), "busy_pct": round(100 * d[9] / (dt * 1000), 1),
                         "avg_queue": round(d[10] / (dt * 1000), 1)}
        if len(d) >= 17:
            rec["device"].update({"flush_per_s": round(d[15] / dt, 1), "flush_ms": round(d[16] / max(d[15], 1), 2), "flush_time_s_per_s": round(d[16] / (dt * 1000), 3), "discard_per_s": round(d[11] / dt, 1)})
        rec["read_burst"] = rec["device"]["read_mibs"] >= burst_mib
    ps = {k: b["psi"].get(k, 0) - a["psi"].get(k, 0) for k in ("some", "full")}
    rec["io_pressure_pct"] = {"some": round(100 * ps["some"] / (dt * 1e6), 1), "full": round(100 * ps["full"] / (dt * 1e6), 1)}
    vm = {k: b["vm"].get(k, 0) - a["vm"].get(k, 0) for k in io.VM_KEYS}
    rec["memory"] = {"refault_file_mibs": round(vm["workingset_refault_file"] * 4096 / dt / 2**20, 2), "swapin_pages_s": round(vm["pswpin"] / dt, 1), "swapout_pages_s": round(vm["pswpout"] / dt, 1),
                     "kswapd_mibs": round(vm["pgsteal_kswapd"] * 4096 / dt / 2**20, 1), "direct_mibs": round(vm["pgsteal_direct"] * 4096 / dt / 2**20, 1)}
    excl, stall = io.exclusive_delta(a["cg"], b["cg"])
    rec["cgroups"] = [{"cgroup": rel, "read_mib": round(v["rbytes"] / 2**20), "write_mib": round(v["wbytes"] / 2**20), "stall_some_pct": round(100 * stall[rel]["some"] / (dt * 1e6), 1)}
                      for rel, v in sorted(excl.items(), key=lambda kv: -(kv[1]["rbytes"] + kv[1]["wbytes"]))[:top] if v["rbytes"] + v["wbytes"] > 0]
    n = max(len(sm.scans), 1)
    flat = [r for scan in sm.scans for r in scan]
    gkey = group if group.startswith("/") else "/" + group
    cls, shape, who = defaultdict(int), defaultdict(int), defaultdict(int)
    for cg, lane, _ar, sh, _comm, _w, c in flat:
        cls[c] += 1
        shape[sh] += 1
        who[lane if cg == gkey else io.clip(cg.replace("/user.slice/user-1000.slice/user@1000.service/", "user:"), 40)] += 1
    total = max(len(flat), 1)
    rec["dstate"] = {"mean_threads": round(len(flat) / n, 2), "by_class": {k: round(v / n, 2) for k, v in sorted(cls.items(), key=lambda kv: -kv[1])},
                     "top_shapes": [{"shape": k, "share_pct": round(100 * v / total, 1)} for k, v in sorted(shape.items(), key=lambda kv: -kv[1])[:top]],
                     "top_lanes": [{"lane": k, "share_pct": round(100 * v / total, 1)} for k, v in sorted(who.items(), key=lambda kv: -kv[1])[:top]]}
    return rec


def prune(sm, alive):
    """Forget cached facts of processes that no longer exist, so a day of pid churn does not grow the caches."""
    for pid in [p for p in sm.table if p not in alive]:
        del sm.table[pid]
    for key in [k for k in sm.cgmap if k[0] not in alive]:
        del sm.cgmap[key]


def rotate(sm):
    """Close a window while the sampling goes on: the closing snapshot is kept as the first one of the next window, so the interval between two records is counted in the second and not left out of
    both; the scans start empty, so the closing sample's D-state threads stay with the window they closed. The counters it differences are cumulative (/proc/diskstats, cgroup io.stat, the pressure
    totals: Linux Documentation/admin-guide/iostats.rst and accounting/psi.rst, which are UNMIRRORED here); first-hand measurement: host_observers_selftest.py runs the loop on an injected clock, where
    two windows must cover the 200 s sampled (100 s and 100 s; the loop without this rotation gave 100 s and 80 s)."""
    sm.snaps, sm.scans = sm.snaps[-1:], []


def append(path, text):
    with open(path, "a") as f:
        f.write(text)


def main():
    out_dir = arg("--out-dir")
    if not out_dir or "--help" in sys.argv:
        print(__doc__)
        return 2
    interval, window, top = float(arg("--interval", 20)), float(arg("--window", 300)), int(arg("--top", 6))
    span, dev, group, burst = parse_active(arg("--active", "03:45-20:15")), arg("--dev", "sdd"), arg("--group", "/non-systemd"), float(arg("--burst-mib", 150))
    proc_root, cg_root = arg("--proc-root", "/proc"), arg("--cg-root", "/sys/fs/cgroup")
    sess_dir = arg("--sessions-dir", str(Path.home() / ".claude" / "sessions"))
    max_days = int(arg("--max-days", 0))
    io = _load("io_attribution")
    sm = io.Sampler(proc_root, cg_root, dev, sess_dir, devkey=arg("--devkey"))
    if not sm.devkey:
        print(f"unknown device {dev}", file=sys.stderr)
        return 2
    os.makedirs(out_dir, exist_ok=True)
    stop = {"now": False}
    signal.signal(signal.SIGTERM, lambda *_: stop.__setitem__("now", True))
    signal.signal(signal.SIGINT, lambda *_: stop.__setitem__("now", True))
    started = datetime.now(NY)
    t_next = time.monotonic()
    t_window = None
    while not stop["now"]:
        now = datetime.now(NY)
        if max_days and now - started > timedelta(days=max_days):
            break
        if not in_active(now, span):
            if sm.snaps:                                   # the active hours ended: close the open window
                if len(sm.snaps) >= 2:
                    emit(io, sm, group, top, burst, out_dir)
                sm.snaps, sm.scans, t_window = [], [], None
            time.sleep(30)
            t_next = time.monotonic()
            continue
        try:
            sm.take()
        except (OSError, ValueError):                       # a /proc race: skip this sample
            pass
        if t_window is None:
            t_window = time.monotonic()
        if time.monotonic() - t_window >= window and len(sm.snaps) >= 2:
            emit(io, sm, group, top, burst, out_dir)
            prune(sm, set(io.snap_procs(proc_root)))
            rotate(sm)
            t_window = sm.snaps[0]["t"]
        t_next += interval
        time.sleep(max(t_next - time.monotonic(), 0))
        if t_next < time.monotonic() - interval:             # fell behind (a long pause): do not burst to catch up
            t_next = time.monotonic()
    if len(sm.snaps) >= 2:
        emit(io, sm, group, top, burst, out_dir)
    return 0


def emit(io, sm, group, top, burst, out_dir):
    rec = window_record(io, sm, group, top, burst)
    day = datetime.fromtimestamp(sm.snaps[0]["wall"], NY).strftime("%Y%m%d")
    append(os.path.join(out_dir, f"io-attribution-daemon-{day}.jsonl"), json.dumps(rec) + "\n")
    append(os.path.join(out_dir, f"io-attribution-daemon-{day}.txt"), "\n".join(io.report(sm, top, group)) + "\n\n")


if __name__ == "__main__":
    sys.exit(main())
