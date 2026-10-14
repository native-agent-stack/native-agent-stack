#!/usr/bin/env python3
"""Passive storm snapshotter (read-only; it writes only its own two files). Asked for by the command center on 2026-10-12: when a storm of 30 or more cores runs in the sessions cgroup
(/non-systemd) outside the idle-class scope, name the lane and the command shape.

  storm_snapshot.py OUT.jsonl [--group /sys/fs/cgroup/non-systemd] [--threshold-cores 30] [--need 2] [--poll 1.0] [--sample 2.0] [--min-gap 30] [--max-hours 24] [--max-lines 5000] [--once]

It reads the group's cpu.stat every --poll seconds. After --need polls in a row at or above --threshold-cores (and at least --min-gap seconds after the last snapshot) it samples every process of the
group twice, --sample seconds apart, and appends one JSON line to OUT.jsonl: the lanes (a lane is the `claude` session that is the ancestor of the process; its name and directory come from
~/.claude/sessions/<pid>.json, the only file of that directory it opens, never the .key files), each lane's cores and its top command shapes with a process count and up to two working directories.
OUT.log (next to it) gets a heartbeat every 10 minutes and any error. --once takes one snapshot now, whatever the load (for a dry run).

Privacy: raw command lines are never stored. A shape is the program's base name, plus `-m module`, the script's base name, or one plain subcommand word; flags, values, anything that looks like a key,
token or long opaque string, and the code after -c are dropped or replaced. Per-process views miss processes that live less than the sample window, so measured_cores is reported beside the group's cores.
"""
import json
import os
import re
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

GROUP_DEFAULT = "/sys/fs/cgroup/non-systemd"
SESS_DIR = Path.home() / ".claude" / "sessions"
HZ = os.sysconf("SC_CLK_TCK")
MIN_CORES = 0.25      # a process counts as heavy from this many cores over the sample window
TOP_N = 60            # most processes whose cwd and command line are read per snapshot
SECRET_RX = re.compile(r"(?i)(sk-[A-Za-z0-9]{6,}|gh[pousr]_[A-Za-z0-9]{6,}|eyJ[A-Za-z0-9_-]{8,}|[A-Za-z0-9+/_-]{28,}|key|token|secret|passw|bearer|auth|cookie|credential)")
WORD_RX = re.compile(r"^[A-Za-z0-9_.:@+,-]{1,48}$")
WRAPPERS = {"env", "nice", "timeout", "time", "setsid", "nohup", "xargs", "systemd-run", "sudo", "rtk", "stdbuf", "ionice", "chrt", "taskset"}
RUNNERS = {"uv", "uvx", "npx", "pnpm", "npm", "yarn", "bunx", "pipx"}
INTERPRETERS = re.compile(r"^(python[0-9.]*|node|nodejs|bash|sh|dash|zsh|deno|bun|ruby|perl|php)$")


def arg(name, default=None):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def _word(t):
    """One argument token as safe text, or None to drop it."""
    t = t.strip()
    if not t or t.startswith("-"):
        return None
    if "/" in t:
        t = t.rstrip("/").rsplit("/", 1)[-1]
    if not t:
        return None
    if SECRET_RX.search(t):
        return "<redacted>"
    return t[:40] if WORD_RX.match(t[:48]) else "<arg>"


def shape(argv, comm=""):
    """The command shape of a command line (see the module docstring); an empty string when there is nothing safe to say.
    A version-like executable name (the versioned claude binary is called 2.1.296) is replaced by the kernel's process name."""
    a = [x for x in argv if x]
    if not a:
        return ""
    b0 = a[0].rstrip("/").rsplit("/", 1)[-1][:40]
    if comm and re.fullmatch(r"[0-9][0-9.]*", b0):
        b0 = comm[:40]
    rest = a[1:]
    if b0 in WRAPPERS:
        # skip the wrapper's own flags, KEY=VALUE assignments and bare numbers (a duration or a priority), then describe the command it runs
        i = 0
        while i < len(rest) and (rest[i].startswith("-") or "=" in rest[i] or re.fullmatch(r"[0-9.]+[smhd]?", rest[i] or "")):
            i += 1
        inner = shape(rest[i:])
        return (b0 + " " + inner).strip()[:80]
    out = [b0]
    if INTERPRETERS.match(b0):
        if rest[:1] == ["-m"] and len(rest) > 1:
            out += ["-m", _word(rest[1]) or ""]
        elif rest[:1] == ["-c"]:
            out += ["-c"]
        else:
            first = next((x for x in rest if not x.startswith("-")), None)
            w = _word(first) if first else None
            if w:
                out.append(w)
    elif b0 in RUNNERS:
        words = [w for w in (_word(x) for x in rest if not x.startswith("-")) if w][:2]
        out += words
    else:
        w = _word(rest[0]) if rest and "/" not in rest[0] else None
        if w:
            out.append(w)
    return " ".join(x for x in out if x)[:80]


def read_stat(pid):
    try:
        s = open(f"/proc/{pid}/stat").read()
        r = s.rindex(")")
        f = s[r + 2:].split()
        return {"comm": s[s.index("(") + 1:r], "ppid": int(f[1]), "ticks": int(f[11]) + int(f[12]), "start": int(f[19])}
    except (OSError, ValueError, IndexError):
        return None


def group_pids(group):
    pids = set()
    for root, _dirs, files in os.walk(group):
        if "cgroup.procs" in files:
            try:
                pids |= {int(x) for x in open(os.path.join(root, "cgroup.procs")).read().split()}
            except (OSError, ValueError):
                pass
    return pids


def usage_usec(group):
    for ln in open(group + "/cpu.stat"):
        if ln.startswith("usage_usec"):
            return int(ln.split()[1])
    raise OSError("no usage_usec in cpu.stat")


def lane_of(pid, table):
    """The pid of the `claude` session that is this process's ancestor (or itself), or None."""
    seen = 0
    while pid in table and seen < 60:
        if table[pid]["comm"] == "claude":
            return pid
        nxt = table[pid]["ppid"]
        if nxt == pid:
            break
        pid, seen = nxt, seen + 1
    return None


def session_info(pid):
    """Name, directory and kind of a session from its own registry file; nothing else in that directory is opened."""
    try:
        d = json.loads((SESS_DIR / f"{int(pid)}.json").read_text())
        return {"name": str(d["name"])[:60] if d.get("name") else None, "cwd": d.get("cwd"), "kind": d.get("kind")}
    except (OSError, ValueError, KeyError, TypeError):
        return {}


def aggregate(table, sessions):
    """table: pid -> {comm, ppid, cores, [cwd], [argv]}; sessions: root pid -> {name, cwd, kind}. Returns the lanes, busiest first."""
    lanes = {}
    for p, e in table.items():
        if e["cores"] < MIN_CORES:
            continue
        key = lane_of(p, table) or 0
        L = lanes.setdefault(key, {"cores": 0.0, "n": 0, "shapes": {}})
        L["cores"] += e["cores"]
        L["n"] += 1
        S = L["shapes"].setdefault(shape(e.get("argv") or [], e["comm"]) or e["comm"], {"cores": 0.0, "n": 0, "cwds": []})
        S["cores"] += e["cores"]
        S["n"] += 1
        c = e.get("cwd")
        if c and c not in S["cwds"] and len(S["cwds"]) < 2:
            S["cwds"].append(c)
    out = []
    for key, L in sorted(lanes.items(), key=lambda kv: -kv[1]["cores"]):
        info = sessions.get(key, {}) if key else {}
        top = sorted(L["shapes"].items(), key=lambda kv: -kv[1]["cores"])[:5]
        out.append({"lane": info.get("name") or (f"claude pid {key}" if key else "unattributed (no claude ancestor in the group)"), "root_pid": key or None,
                    "root_cwd": info.get("cwd"), "kind": info.get("kind"), "cores": round(L["cores"], 2), "processes": L["n"],
                    "top": [{"shape": s, "cores": round(v["cores"], 2), "n": v["n"], "cwds": v["cwds"]} for s, v in top]})
    return out


class Detector:
    def __init__(self, threshold, need, min_gap):
        self.threshold, self.need, self.min_gap, self.run, self.last = threshold, need, min_gap, 0, None

    def feed(self, cores, now):
        self.run = self.run + 1 if cores >= self.threshold else 0
        if self.run >= self.need and (self.last is None or now - self.last >= self.min_gap):
            self.last = now
            return True
        return False


def snapshot(group, sample_s):
    a = {}
    t0 = time.monotonic()
    for p in group_pids(group):
        s = read_stat(p)
        if s:
            a[p] = s
    time.sleep(sample_s)
    dt = time.monotonic() - t0
    pids = group_pids(group)
    up = float(open("/proc/uptime").read().split()[0])
    table = {}
    for p in pids:
        b = read_stat(p)
        if not b:
            continue
        if p in a and a[p]["start"] == b["start"]:
            cores = (b["ticks"] - a[p]["ticks"]) / HZ / dt
        else:   # started inside the window: all its CPU time over its age (at most the window)
            age = max(up - b["start"] / HZ, 0.05)
            cores = b["ticks"] / HZ / min(age, dt)
        table[p] = {"comm": b["comm"], "ppid": b["ppid"], "cores": max(cores, 0.0)}
    heavy = sorted((p for p in table if table[p]["cores"] >= MIN_CORES), key=lambda p: -table[p]["cores"])[:TOP_N]
    for p in heavy:
        try:
            table[p]["cwd"] = os.readlink(f"/proc/{p}/cwd")
        except OSError:
            table[p]["cwd"] = None
        try:
            table[p]["argv"] = [x.decode("utf-8", "replace") for x in open(f"/proc/{p}/cmdline", "rb").read().split(b"\0")][:8]
        except OSError:
            table[p]["argv"] = []
    return table, dt, len(pids)       # heavy processes beyond TOP_N keep their cores and are grouped by comm (no command line was read)


def stamp():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main():
    if len(sys.argv) < 2 or sys.argv[1].startswith("--"):
        print(__doc__)
        return 2
    out = Path(sys.argv[1])
    log = out.with_suffix(".log")
    group = arg("--group", GROUP_DEFAULT)
    thr, need, poll, sample = float(arg("--threshold-cores", 30)), int(arg("--need", 2)), float(arg("--poll", 1.0)), float(arg("--sample", 2.0))
    min_gap, max_hours, max_lines, once = float(arg("--min-gap", 30)), float(arg("--max-hours", 24)), int(arg("--max-lines", 5000)), "--once" in sys.argv
    stop = {"now": False}
    signal.signal(signal.SIGTERM, lambda *_: stop.__setitem__("now", True))
    signal.signal(signal.SIGINT, lambda *_: stop.__setitem__("now", True))

    def note(s):
        with open(log, "a") as f:
            f.write(f"{stamp()} {s}\n")

    lines = 0

    def take(trigger):
        nonlocal lines
        table, dt, nprocs = snapshot(group, sample)
        roots = {lane_of(p, table) for p in table if table[p]["cores"] >= MIN_CORES} - {None}
        lanes = aggregate(table, {r: session_info(r) for r in roots})
        rec = {"utc": stamp(), "trigger_cores": round(trigger, 2), "sample_s": round(dt, 2), "group_processes": nprocs,
               "measured_cores": round(sum(e["cores"] for e in table.values() if e["cores"] >= MIN_CORES), 2), "lanes": lanes}
        if lines < max_lines:
            with open(out, "a") as f:
                f.write(json.dumps(rec) + "\n")
            lines += 1
        else:
            note(f"line cap {max_lines} reached; snapshot not written")
        return rec

    if once:
        rec = take(0.0)
        print(json.dumps(rec, indent=1))
        return 0
    note(f"start: group {group}, threshold {thr:g} cores for {need} polls of {poll:g} s, sample {sample:g} s, min gap {min_gap:g} s, cap {max_hours:g} h, out {out.name}")
    det = Detector(thr, need, min_gap)
    deadline = time.monotonic() + max_hours * 3600
    next_beat = time.monotonic() + 600
    prev_u, prev_t, last_cores, snaps = usage_usec(group), time.monotonic(), 0.0, 0
    while not stop["now"] and time.monotonic() < deadline:
        time.sleep(poll)
        try:
            u, t = usage_usec(group), time.monotonic()
            last_cores = (u - prev_u) / 1e6 / max(t - prev_t, 1e-6)
            prev_u, prev_t = u, t
            if det.feed(last_cores, t):
                rec = take(last_cores)
                snaps += 1
                note(f"snapshot {snaps}: group {last_cores:.1f} cores; top lane {rec['lanes'][0]['lane'] if rec['lanes'] else 'none'}")
                prev_u, prev_t = usage_usec(group), time.monotonic()
            if time.monotonic() >= next_beat:
                note(f"heartbeat: alive, group {last_cores:.1f} cores, {snaps} snapshots so far")
                next_beat += 600
        except Exception as ex:   # never die on a transient /proc race
            note(f"error: {type(ex).__name__}: {ex}")
            time.sleep(poll)
    note(f"stopped: {'signal' if stop['now'] else 'hour cap'}; {snaps} snapshots")
    return 0


if __name__ == "__main__":
    sys.exit(main())
