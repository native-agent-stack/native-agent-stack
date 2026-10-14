#!/usr/bin/env python3
"""fsync latency probe: what a process that appends to a journal or replaces a state file with fsync experiences on a given directory's filesystem. Read-only apart from its own scratch
files, which are removed. It doubles as the proposed god-view canary (--prom writes node_exporter textfile lines).

  fsync_probe.py DIR [--seconds 20] [--rate 20] [--size 4096] [--prom OUT.prom] [--label NAME]

Two patterns run on a fixed schedule (--rate starts a second, open loop, so a slow call does not hide the next one; slots missed while a call was still running are counted as late):
  append   write --size bytes to an O_APPEND file and os.fdatasync it (a journal or audit-line writer);
  replace  write a temp file, os.fsync it, os.rename it over the target and os.fsync the directory (the atomic state-file pattern the engine and the test suites use).
Output: per pattern the count, the achieved rate, p50, p90, p99, p99.9 and max latency in milliseconds, and the late slots.
"""
import math
import os
import sys
import tempfile
import time


def arg(name, default=None):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def pct(v, p):
    if not v:
        return float("nan")
    s = sorted(v)
    k = (len(s) - 1) * p / 100
    i = int(k)
    j = min(i + 1, len(s) - 1)
    return s[i] + (s[j] - s[i]) * (k - i)


def summarize(lat_s, late, seconds):
    ms = [x * 1000 for x in lat_s]
    return {"n": len(ms), "rate": len(ms) / seconds if seconds else 0.0, "p50": pct(ms, 50), "p90": pct(ms, 90), "p99": pct(ms, 99), "p999": pct(ms, 99.9), "max": max(ms) if ms else float("nan"), "late": late}


def run(dirpath, seconds, rate, size, clock=time.perf_counter, sleep=time.sleep):
    payload = b"x" * size
    out = {}
    for mode in ("append", "replace"):
        base = tempfile.mkdtemp(prefix="fsync-probe-", dir=dirpath)
        lat, late = [], 0
        try:
            if mode == "append":
                fd = os.open(os.path.join(base, "journal"), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            else:
                dfd = os.open(base, os.O_RDONLY)
            t0 = clock()
            slot, interval = 0, 1.0 / rate
            n_slots = math.ceil(seconds * rate - 1e-9)      # the slots the schedule holds: those that start inside the run
            while slot < n_slots:
                due = t0 + slot * interval
                now = clock()
                if now < due:
                    sleep(due - now)
                elif now - due > interval:          # the call before ran past this slot: count the slots that have passed, never more than the schedule still held, and move on to the next one that has not
                    skipped = min(int((now - due) / interval), n_slots - slot)
                    late += skipped
                    slot += skipped
                    continue
                a = clock()
                if mode == "append":
                    os.write(fd, payload)
                    os.fdatasync(fd)
                else:
                    tmp = os.path.join(base, "state.tmp")
                    tfd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
                    os.write(tfd, payload)
                    os.fsync(tfd)
                    os.close(tfd)
                    os.rename(tmp, os.path.join(base, "state"))
                    os.fsync(dfd)
                lat.append(clock() - a)
                slot += 1
        finally:
            try:
                (os.close(fd) if mode == "append" else os.close(dfd))
            except (OSError, UnboundLocalError):
                pass
            for f in os.listdir(base):
                try:
                    os.unlink(os.path.join(base, f))
                except OSError:
                    pass
            os.rmdir(base)
        out[mode] = summarize(lat, late, seconds)
    return out


def main():
    if len(sys.argv) < 2 or sys.argv[1].startswith("--"):
        print(__doc__)
        return 2
    d = sys.argv[1]
    seconds, rate, size = float(arg("--seconds", 20)), float(arg("--rate", 20)), int(arg("--size", 4096))
    label = arg("--label", d)
    try:
        res = run(d, seconds, rate, size)
    except OSError as ex:
        print("probe failed:", type(ex).__name__, ex)
        return 2
    fs = os.statvfs(d)
    print(f"fsync probe on {label} ({seconds:g} s, {rate:g} per second, {size} bytes)")
    print(f"  {'pattern':<8} {'n':>5} {'rate':>6} {'p50':>8} {'p90':>8} {'p99':>8} {'p99.9':>8} {'max':>8}  late  (milliseconds)")
    for mode, r in res.items():
        print(f"  {mode:<8} {r['n']:>5} {r['rate']:>6.1f} {r['p50']:>8.2f} {r['p90']:>8.2f} {r['p99']:>8.2f} {r['p999']:>8.2f} {r['max']:>8.2f}  {r['late']:>4}")
    prom = arg("--prom")
    if prom:
        lines = []
        for mode, r in res.items():
            for q in ("p50", "p99", "max"):
                lines.append(f'fsync_probe_latency_seconds{{target="{label}",pattern="{mode}",quantile="{q}"}} {r[q] / 1000:.6f}')
            lines.append(f'fsync_probe_late_slots{{target="{label}",pattern="{mode}"}} {r["late"]}')
        tmp = prom + ".tmp"
        with open(tmp, "w") as f:
            f.write("\n".join(lines) + "\n")
        os.replace(tmp, prom)
    return 0


if __name__ == "__main__":
    sys.exit(main())
