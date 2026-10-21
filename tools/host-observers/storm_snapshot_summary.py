#!/usr/bin/env python3
"""Summarise the storm snapshotter's output (storm_snapshot.py) for the command center's follow-up of 2026-10-12: which lane and command shape ran the 30-plus-core storms in the sessions cgroup.
Read-only; it opens only the file named on the command line.

  storm_snapshot_summary.py SNAPSHOTS.jsonl [--from 2026-10-13T08:00:00Z] [--to 2026-10-13T20:00:00Z] [--gap 300] [--max-episodes 60]

Snapshots in the window (--from inclusive, --to exclusive, UTC) that are at most --gap seconds apart form one episode. Per episode: its snapshots, the peak group cores at the trigger, the share of
the trigger cores that the per-process sample saw (a storm of short-lived processes is under-seen; marked *), and the leading lane, command shape and working-directory area by cores seen. A lane is
the `claude` session that is the process's ancestor. "unattributed" processes have none left (test runs of the GPT-read kit, promptfoo runs, scripts whose launcher exited); for them the `by cwd`
column names the one lane whose own directory holds the process's working directory ("several" when lanes share that directory, "-" when none does): a hint from the directory, not ancestry.
Then totals by lane, the unattributed total by that hint, and by lane, shape and area. Weights are cores seen in the 2 s samples added over snapshots, not CPU hours.
"""
import calendar
import json
import sys
import time
from collections import defaultdict

TS_FMT = "%Y-%m-%dT%H:%M:%SZ"
UNDER_SEEN = 0.5     # an episode whose samples saw less than this share of its trigger cores is marked *
MIN_DEPTH = 3        # a lane's own directory needs this many path parts to count as a hint (the home directory would otherwise claim everything under it)


def arg(name, default=None):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def parse_utc(s):
    return calendar.timegm(time.strptime(s, TS_FMT))    # mktime minus timezone is an hour early under DST


def fmt_t(t, day=True):
    return time.strftime("%m-%d %H:%M:%S" if day else "%H:%M:%S", time.gmtime(t))


def clip(s, n):
    return s if len(s) <= n else s[:n - 1] + "~"


def pct(a, b):
    return f"{a / b:.0%}" if b else "n/a"


def area(cwd):
    """A short owner hint from a working directory: one or two parts under the home directory (three under .local), one part under /var/tmp or /tmp, else the first two parts."""
    if not isinstance(cwd, str) or not cwd:
        return "-"
    p = [x for x in cwd.split("/") if x]
    if not p:
        return "/"
    if p[0] == "home" and len(p) >= 2:
        p = p[2:]
        return "/".join(p[:{"code": 2, ".cache": 2, ".local": 3}.get(p[0], 1)]) if p else "~"
    if p[0] == "tmp" or p[:2] == ["var", "tmp"]:
        return "/" + "/".join(p[:2 if p[0] == "tmp" else 3])
    return "/" + "/".join(p[:2])


def lane_name(raw):
    raw = raw if isinstance(raw, str) and raw else "?"
    return "unattributed" if raw.startswith("unattributed") else raw


def owner_of(cwd, homes):
    """The lane that most likely ran a process without a claude ancestor, from its working directory: the lane whose own directory is the longest one holding it; 'several' when more than one lane
    has that directory, '-' when none holds it. `homes` maps a lane's own directory to the set of lane names that sit in it."""
    if not isinstance(cwd, str) or not cwd:
        return "-"
    best = max((h for h in homes if cwd == h or cwd.startswith(h.rstrip("/") + "/")), key=len, default=None)
    if best is None:
        return "-"
    return next(iter(homes[best])) if len(homes[best]) == 1 else "several"


def load(path, lo, hi):
    """The snapshots inside the window sorted by time; how many lines were not a usable snapshot (one still being written, or damaged); and the lanes' own directories seen anywhere in the file
    (directory -> lane names). The window does not limit the directories: a lane that is quiet in the window still owns its directory."""
    snaps, bad, homes = [], 0, defaultdict(set)
    with open(path, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                r = json.loads(line)
                r["_t"] = parse_utc(r["utc"])
                float(r["trigger_cores"])
                float(r["measured_cores"])
                if not isinstance(r["lanes"], list):
                    raise TypeError("lanes")
            except (ValueError, KeyError, TypeError):
                bad += 1
                continue
            for ln in r["lanes"]:
                root = ln.get("root_cwd") if isinstance(ln, dict) else None
                if isinstance(root, str) and len([x for x in root.split("/") if x]) >= MIN_DEPTH and lane_name(ln.get("lane")) != "unattributed":
                    homes[root].add(lane_name(ln.get("lane")))
            if (lo is None or r["_t"] >= lo) and (hi is None or r["_t"] < hi):
                snaps.append(r)
    snaps.sort(key=lambda r: r["_t"])
    return snaps, bad, homes


def entries(r, homes):
    """The (lane, shape, area, by_cwd, cores) rows of one snapshot; by_cwd is the owner_of hint for an unattributed row and '-' for the others. A lane's cores beyond its listed shapes come back as
    an '(other shapes)' row, so a lane's rows add up to its cores."""
    out = []
    for ln in r["lanes"]:
        if not isinstance(ln, dict):
            continue
        name, listed = lane_name(ln.get("lane")), 0.0
        for t in ln.get("top") or []:
            c, cw = float(t.get("cores", 0)), t.get("cwds") or []
            out.append((name, str(t.get("shape") or "?"), area(cw[0]) if cw else "-", owner_of(cw[0], homes) if name == "unattributed" and cw else "-", c))
            listed += c
        rest = float(ln.get("cores", 0)) - listed
        if rest > 0.05:
            out.append((name, "(other shapes)", "-", "-", rest))
    return out


def episodes(snaps, gap):
    eps, cur = [], []
    for r in snaps:
        if cur and r["_t"] - cur[-1]["_t"] > gap:
            eps.append(cur)
            cur = []
        cur.append(r)
    return eps + ([cur] if cur else [])


def episode_row(e, homes):
    trig = sum(float(r["trigger_cores"]) for r in e)
    meas = sum(float(r["measured_cores"]) for r in e)
    w = defaultdict(float)
    for r in e:
        for lane, shape, ar, hint, c in entries(r, homes):
            w[(lane, shape, ar, hint)] += c
    lead, lw = max(w.items(), key=lambda kv: kv[1]) if w else (("none", "-", "-", "-"), 0.0)
    return {"start": e[0]["_t"], "end": e[-1]["_t"], "n": len(e), "peak": max(float(r["trigger_cores"]) for r in e),
            "seen": meas / trig if trig else None, "lead": lead, "share": lw / meas if meas else None}


def totals(snaps, homes):
    by_lane, by_key, present, by_hint = defaultdict(float), defaultdict(float), defaultdict(int), defaultdict(float)
    for r in snaps:
        keys = set()
        for ln in r["lanes"]:
            if isinstance(ln, dict):
                by_lane[lane_name(ln.get("lane"))] += float(ln.get("cores", 0))
        for lane, shape, ar, hint, c in entries(r, homes):
            by_key[(lane, shape, ar, hint)] += c
            keys.add((lane, shape, ar, hint))
            if lane == "unattributed":
                by_hint[hint] += c
        for k in keys:
            present[k] += 1
    return by_lane, by_key, present, by_hint


def main():
    if len(sys.argv) < 2 or sys.argv[1].startswith("--"):
        print(__doc__)
        return 2
    f_arg, t_arg = arg("--from"), arg("--to")
    lo, hi = (parse_utc(f_arg) if f_arg else None), (parse_utc(t_arg) if t_arg else None)
    gap, cap = float(arg("--gap", 300)), int(arg("--max-episodes", 60))
    snaps, bad, homes = load(sys.argv[1], lo, hi)
    print(f"snapshots: {sys.argv[1]}")
    print(f"window (UTC): {f_arg or 'start of file'} to {t_arg or 'end of file'}; {len(snaps)} snapshots; {bad} unusable lines skipped")
    if not snaps:
        print("no snapshots in the window (the snapshotter's .log says whether it was running)")
        return 0
    trig = sum(float(r["trigger_cores"]) for r in snaps)
    meas = sum(float(r["measured_cores"]) for r in snaps)
    rows = [episode_row(e, homes) for e in episodes(snaps, gap)]
    print(f"first {fmt_t(snaps[0]['_t'])}Z, last {fmt_t(snaps[-1]['_t'])}Z; {len(rows)} episodes (snapshots at most {gap:g} s apart)")
    print(f"seen {pct(meas, trig)} of the trigger cores ({meas:.0f} measured of {trig:.0f}, added over snapshots): the per-process sample misses processes shorter than its 2 s window")
    print()
    print(f"{'#':>3} {'start..end (UTC)':<24} {'n':>3} {'peak':>5} {'seen':>5}  {'leading lane':<20} {'by cwd':<20} {'command shape':<28} {'working-directory area':<30} {'share':>5}")
    for i, x in enumerate(rows[:cap], 1):
        lane, shape, ar, hint = x["lead"]
        seen = "n/a" if x["seen"] is None else f"{x['seen']:.0%}" + ("*" if x["seen"] < UNDER_SEEN else "")
        share = "n/a" if x["share"] is None else f"{x['share']:.0%}"
        print(f"{i:>3} {fmt_t(x['start'])}..{fmt_t(x['end'], False)} {x['n']:>3} {x['peak']:>5.1f} {seen:>5}  {clip(lane, 20):<20} {clip(hint, 20):<20} {clip(shape, 28):<28} {clip(ar, 30):<30} {share:>5}")
    if len(rows) > cap:
        print(f"... {len(rows) - cap} more episodes not shown (--max-episodes)")
    print("* the samples saw under half of the trigger cores: most of that storm ran in processes shorter than the sample, so its lane is a lower bound, not a finding")
    print("seen can pass 100%: the trigger is the cpu.stat rate over the second before the snapshot, the sample covers the next 2 s")
    print("by cwd: for a process with no claude ancestor, the lane whose own directory holds its working directory ('several': lanes share it; '-': none does); a hint from the directory, not ancestry")
    by_lane, by_key, present, by_hint = totals(snaps, homes)
    print()
    print("by lane (cores seen, added over snapshots):")
    for lane, w in sorted(by_lane.items(), key=lambda kv: -kv[1])[:8]:
        print(f"  {clip(lane, 30):<30} {w:8.1f} {pct(w, meas):>5}")
    if by_hint:
        print()
        print("unattributed cores seen, by the lane whose directory holds the working directory:")
        for hint, w in sorted(by_hint.items(), key=lambda kv: -kv[1])[:8]:
            print(f"  {clip(hint, 30):<30} {w:8.1f} {pct(w, meas):>5}")
    print()
    print("by lane, command shape and area (top 12):")
    for k, w in sorted(by_key.items(), key=lambda kv: -kv[1])[:12]:
        print(f"  {clip(k[0], 20):<20} {clip(k[3], 20):<20} {clip(k[1], 28):<28} {clip(k[2], 30):<30} {w:8.1f} {pct(w, meas):>5}  in {present[k]} of {len(snaps)} snapshots")
    return 0


if __name__ == "__main__":
    sys.exit(main())
