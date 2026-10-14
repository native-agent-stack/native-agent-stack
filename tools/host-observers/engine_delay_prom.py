#!/usr/bin/env python3
"""Engine delay sidecar: turns the live delay log (engine_delay_logger.py's CSV) into the node exporter's textfile format, so the god-view can show and alert on the accepted E4 budget.
Read-only: it reads the tail of the newest delay CSV and writes one output file by rename.

  engine_delay_prom.py --dir EVIDENCE_DIR --out FILE.prom [--window 300] [--tail-bytes 2097152]

The newest `engine-delay-*.csv` in --dir (summaries excluded) is read from its last --tail-bytes. For each stage unit with samples in the last --window seconds (300 s of 0.2 s samples is
1,500, above the 1,000-sample minimum of engine_delay_budget_v2.py) it writes, with the label unit="<stage>":
  engine_delay_p99_seconds, engine_delay_p999_seconds, engine_delay_max_seconds   worst-thread run-queue delay per sample over the window
  engine_delay_share                                                              delay / (run + delay) over the window, a fraction
  engine_delay_samples, engine_delay_samples_ge_10ms
  engine_unit_active                                                              1 when the unit's newest sample is at most 10 s old
and, whatever the units do:
  engine_delay_logger_age_seconds                                                 seconds since the newest row of any kind (the logger writes a heartbeat a minute)
  engine_delay_vm_busy_cores, engine_delay_group_cores                            the newest row's whole-VM and sessions-group busy cores
No per-unit series are written for a unit with no sample in the window, so a stopped stage raises no alert. Percentiles use the budget tool's linear interpolation.
"""
import calendar
import glob
import os
import re
import sys
import time

COLS = "ts_utc,unit,cg_weight,nthreads,d_run_us,d_delay_us,d_slices,max_thr_delay_us,max_thr_tid,n_thr_delay_gt10ms,psi_some_us,psi_full_us,dt_ms,vm_busy_cores,nsd_cores,note".split(",")
IDX = {c: i for i, c in enumerate(COLS)}
GE_MS = 10.0


def arg(name, default=None):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def pc(v, p):
    if not v:
        return float("nan")
    s = sorted(v)
    k = (len(s) - 1) * p / 100
    i = int(k)
    j = min(i + 1, len(s) - 1)
    return s[i] + (s[j] - s[i]) * (k - i)


def parse_ts(s):
    """2026-10-14T08:00:08.750Z to seconds since the epoch (UTC; timegm, not mktime)."""
    base = calendar.timegm(time.strptime(s[:19], "%Y-%m-%dT%H:%M:%S"))
    frac = float("0" + s[19:-1]) if len(s) > 20 and s.endswith("Z") else 0.0
    return base + frac


def stage(unit):
    u = unit[len("paper-ready-"):] if unit.startswith("paper-ready-") else unit
    return re.split(r"[-.]", u, 1)[0]


def newest_csv(d):
    files = [f for f in glob.glob(os.path.join(d, "engine-delay-2*.csv")) if "summary" not in os.path.basename(f)]
    return max(files, key=os.path.getmtime) if files else None


def read_rows(path, tail_bytes):
    """The parsed rows of the file's tail: [(t, unit, d_run_us, d_delay_us, max_delay_us, busy, group)]; a cut first line, a partial last line and unreadable rows are skipped."""
    size = os.path.getsize(path)
    with open(path, "rb") as f:
        if size > tail_bytes:
            f.seek(size - tail_bytes)
            f.readline()
        data = f.read().decode("utf-8", "replace")
    rows = []
    for ln in data.splitlines():
        p = ln.split(",")
        if len(p) != len(COLS):
            continue
        try:
            rows.append((parse_ts(p[IDX["ts_utc"]]), p[IDX["unit"]], int(p[IDX["d_run_us"]]), int(p[IDX["d_delay_us"]]), int(p[IDX["max_thr_delay_us"]]),
                         float(p[IDX["vm_busy_cores"]]), float(p[IDX["nsd_cores"]])))
        except (ValueError, IndexError):
            continue
    return rows


def compute(rows, now, window):
    """({stage: metrics}, newest row time or None, newest row's (busy, group) or None)."""
    newest = max(rows, key=lambda r: r[0]) if rows else None
    per = {}
    for t, unit, run_us, dly_us, mx_us, _b, _g in rows:
        if unit == "-" or t < now - window or t > now + 5:
            continue
        per.setdefault(stage(unit), []).append((t, run_us, dly_us, mx_us))
    out = {}
    for st, rs in per.items():
        mx = [r[3] / 1e6 for r in rs]
        run, dly = sum(r[1] for r in rs), sum(r[2] for r in rs)
        out[st] = {"p99": pc(mx, 99), "p999": pc(mx, 99.9), "max": max(mx), "share": dly / max(run + dly, 1), "n": len(rs),
                   "ge": sum(1 for x in mx if x * 1000 >= GE_MS), "active": 1 if now - max(r[0] for r in rs) <= 10 else 0}
    return out, (newest[0] if newest else None), ((newest[5], newest[6]) if newest else None)


def render(stages, newest_t, load, now):
    lines = []
    for st in sorted(stages):
        m = stages[st]
        lines += [f'engine_delay_p99_seconds{{unit="{st}"}} {m["p99"]:.6f}', f'engine_delay_p999_seconds{{unit="{st}"}} {m["p999"]:.6f}', f'engine_delay_max_seconds{{unit="{st}"}} {m["max"]:.6f}',
                  f'engine_delay_share{{unit="{st}"}} {m["share"]:.6f}', f'engine_delay_samples{{unit="{st}"}} {m["n"]}', f'engine_delay_samples_ge_10ms{{unit="{st}"}} {m["ge"]}',
                  f'engine_unit_active{{unit="{st}"}} {m["active"]}']
    if newest_t is not None:
        lines.append(f"engine_delay_logger_age_seconds {max(now - newest_t, 0):.1f}")
    if load is not None:
        lines += [f"engine_delay_vm_busy_cores {load[0]:.2f}", f"engine_delay_group_cores {load[1]:.2f}"]
    return "\n".join(lines) + "\n"


def write_atomic(path, text):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        f.write(text)
    os.replace(tmp, path)


def main():
    d, out = arg("--dir"), arg("--out")
    if not d or not out:
        print(__doc__)
        return 2
    window, tail = float(arg("--window", 300)), int(arg("--tail-bytes", 2097152))
    path = newest_csv(d)
    if path is None:
        write_atomic(out, "engine_delay_logger_age_seconds 999999\n")
        print("no engine-delay CSV in", d, file=sys.stderr)
        return 1
    now = time.time()
    try:
        rows = read_rows(path, tail)
    except OSError as ex:
        print("unreadable:", type(ex).__name__, ex, file=sys.stderr)
        return 1
    stages, newest_t, load = compute(rows, now, window)
    write_atomic(out, render(stages, newest_t, load, now))
    return 0


if __name__ == "__main__":
    sys.exit(main())
