#!/usr/bin/env python3
"""fsync canary for the god-view: one short fsync_probe run on a directory, written in the node exporter's textfile format. Read-only apart from its own scratch files (removed) and the
output file (written by rename, so the exporter never reads a half-written file).

  fsync_canary.py DIR OUT.prom [--seconds 3] [--rate 10] [--size 4096] [--label NAME]

Run it from a timer at most once a minute: every probe adds synchronous writes to the saturated flush path (the default 3 s at 10 a second is 30 appends and 30 atomic replaces, about 90
sync calls). Metrics (seconds): fsync_probe_latency_seconds{target,pattern,quantile} for p50, p99 and max of the run, fsync_probe_samples, fsync_probe_late_slots,
fsync_probe_last_run_timestamp_seconds and fsync_probe_run_seconds. With 30 samples p99 is close to the maximum; judge the tail over a window in Prometheus
(max_over_time of the max series), not from one run. On a failure it writes fsync_probe_last_failure_timestamp_seconds and leaves the previous latency lines out, so staleness is visible.
"""
import importlib.util
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent


def arg(name, default=None):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def load_probe():
    spec = importlib.util.spec_from_file_location("fsync_probe", HERE / "fsync_probe.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def render(res, label, now, seconds):
    """The textfile lines for one probe result {pattern: summary}."""
    lines = []
    for mode, r in res.items():
        for q in ("p50", "p99", "max"):
            lines.append(f'fsync_probe_latency_seconds{{target="{label}",pattern="{mode}",quantile="{q}"}} {r[q] / 1000:.6f}')
        lines.append(f'fsync_probe_samples{{target="{label}",pattern="{mode}"}} {r["n"]}')
        lines.append(f'fsync_probe_late_slots{{target="{label}",pattern="{mode}"}} {r["late"]}')
    lines.append(f'fsync_probe_last_run_timestamp_seconds{{target="{label}"}} {now:.0f}')
    lines.append(f'fsync_probe_run_seconds{{target="{label}"}} {seconds:g}')
    return "\n".join(lines) + "\n"


def write_atomic(path, text):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        f.write(text)
    os.replace(tmp, path)


def main():
    if len(sys.argv) < 3 or sys.argv[1].startswith("--") or sys.argv[2].startswith("--"):
        print(__doc__)
        return 2
    d, out = sys.argv[1], sys.argv[2]
    seconds, rate, size, label = float(arg("--seconds", 3)), float(arg("--rate", 10)), int(arg("--size", 4096)), arg("--label", d)
    try:
        res = load_probe().run(d, seconds, rate, size)
    except OSError as ex:
        write_atomic(out, f'fsync_probe_last_failure_timestamp_seconds{{target="{label}"}} {time.time():.0f}\n')
        print("probe failed:", type(ex).__name__, ex, file=sys.stderr)
        return 1
    write_atomic(out, render(res, label, time.time(), seconds))
    return 0


if __name__ == "__main__":
    sys.exit(main())
