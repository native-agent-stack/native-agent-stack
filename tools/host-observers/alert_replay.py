#!/usr/bin/env python3
"""Replay a Grafana-managed alert rule on the series Prometheus still holds, with Grafana's own pending and firing rules, and say when it would have fired.

  alert_replay.py --rule-file FILE --uid UID --start ISO --end ISO [--phases 0,15,30,45] [--prom URL] [--expect-fire ISO --tolerance 90 --expect-episodes N]
  alert_replay.py --expr PROMQL (--lt X | --gt X) --for SECONDS [--interval 60] --start ISO --end ISO ...

The rule is read from the provisioned rule file (JSON or YAML) so the replay cannot drift from what is deployed: query A's expression, the threshold on query B, the `for` and the group interval.
The query runs as a range query whose step is the group interval, once per phase (the second of the minute at which the group is evaluated is not known in advance, so a few phases show how far
the firing time can move). Each evaluation then goes through the state machine of grafana/grafana v13.2.3 pkg/services/ngalert/state/state.go:
  - a true condition on a Normal (or NoData) alert starts Pending when `for` > 0 (lines 433 to 446), else fires at once (447 to 458);
  - a Pending alert fires when evaluated_at - starts_at >= `for` (line 419);
  - a false condition ends Pending or Alerting at once when keep_firing_for is 0 (lines 386 to 399);
  - a missing sample is NoData: it is not true, and it restarts the pending clock.
Output per phase: the evaluations replayed, the firing episodes (fired, resolved), pending runs that never fired, and the NoData evaluations. With --expect-fire the exit status is 0 only when the first
firing of every phase is within --tolerance seconds of the expected instant (ISO, UTC) and the number of episodes equals --expect-episodes (default 1) in every phase; 1 otherwise; 2 for a usage error.
"""
import calendar
import datetime
import json
import sys
import urllib.parse
import urllib.request


def tsec(s):
    return calendar.timegm(datetime.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").timetuple())


def hms(t):
    return datetime.datetime.fromtimestamp(t, datetime.timezone.utc).strftime("%H:%M:%S")


def parse_duration(s):
    if isinstance(s, (int, float)):
        return float(s)
    total, num = 0.0, ""
    for ch in str(s):
        if ch.isdigit() or ch == ".":
            num += ch
        else:
            total += float(num or 0) * {"s": 1, "m": 60, "h": 3600}[ch]
            num = ""
    return total + (float(num) if num else 0.0)


def load_rule(path, uid):
    text = open(path).read()
    try:
        doc = json.loads(text)
    except ValueError:
        import yaml
        doc = yaml.safe_load(text)
    for g in doc["groups"]:
        for r in g["rules"]:
            if r["uid"] == uid:
                a = next(d for d in r["data"] if d["refId"] == "A")
                b = next(d for d in r["data"] if d["refId"] == r["condition"])
                ev = b["model"]["conditions"][0]["evaluator"]
                return {"expr": a["model"]["expr"], "op": ev["type"], "threshold": float(ev["params"][0]), "for": parse_duration(r.get("for", "0s")),
                        "interval": parse_duration(g["interval"]), "no_data": r.get("noDataState", "NoData")}
    raise KeyError(uid)


def simulate(points, op, threshold, for_s):
    """points: [(t, value or None)] at the evaluation instants. Returns (episodes, pending_runs, nodata).
    episodes: [[fired_at, resolved_at or None]]; pending_runs: [(started_at, ended_at)] that did not fire; nodata: count."""
    cond = {"lt": lambda v: v < threshold, "gt": lambda v: v > threshold}[op]
    state, starts = "normal", None
    episodes, pending_runs, nodata = [], [], 0
    last_t = None
    for t, v in points:
        last_t = t
        if v is None:
            nodata += 1
            if state == "firing":
                episodes[-1][1] = t
            elif state == "pending":
                pending_runs.append((starts, t))
            state, starts = "nodata", None
        elif cond(v):
            if state == "firing":
                continue
            if state == "pending":
                if t - starts >= for_s:
                    state = "firing"
                    episodes.append([t, None])
                continue
            if for_s > 0:
                state, starts = "pending", t
            else:
                state = "firing"
                episodes.append([t, None])
        else:
            if state == "firing":
                episodes[-1][1] = t
            elif state == "pending":
                pending_runs.append((starts, t))
            state, starts = "normal", None
    if state == "pending":
        pending_runs.append((starts, last_t))
    return episodes, pending_runs, nodata


def prom_range(base, expr, start, end, step):
    u = base + "/api/v1/query_range?" + urllib.parse.urlencode({"query": expr, "start": start, "end": end, "step": step})
    res = json.load(urllib.request.urlopen(u, timeout=60))["data"]["result"]
    return {json.dumps(r["metric"], sort_keys=True): {float(t): float(v) for t, v in r["values"]} for r in res}


def replay(base, expr, op, threshold, for_s, interval, start, end, phase):
    """Per series, the list of (t, value) on the grid start+phase+k*interval, with None where Prometheus has no sample."""
    t0 = start - (start % interval) + phase
    if t0 < start:
        t0 += interval
    grid = []
    t = t0
    while t <= end:
        grid.append(t)
        t += interval
    series = prom_range(base, expr, grid[0], grid[-1], interval)
    out = {}
    for key, vals in series.items():
        out[key] = [(g, vals.get(float(g))) for g in grid]
    return out, len(grid)


def main(argv):
    opt = lambda name, d=None: argv[argv.index(name) + 1] if name in argv else d
    if "--start" not in argv or "--end" not in argv or not (("--rule-file" in argv and "--uid" in argv) or ("--expr" in argv and "--for" in argv and ("--lt" in argv or "--gt" in argv))):
        print(__doc__)
        return 2
    if "--rule-file" in argv:
        rule = load_rule(opt("--rule-file"), opt("--uid"))
    else:
        rule = {"expr": opt("--expr"), "op": "lt" if "--lt" in argv else "gt", "threshold": float(opt("--lt") or opt("--gt")), "for": parse_duration(opt("--for")),
                "interval": parse_duration(opt("--interval", 60)), "no_data": "NoData"}
    start, end = tsec(opt("--start")), tsec(opt("--end"))
    base = opt("--prom", "http://127.0.0.1:21090")
    phases = [int(x) for x in opt("--phases", "0,15,30,45").split(",")]
    print(f"rule: {rule['expr']}  {rule['op']} {rule['threshold']:g}  for {rule['for']:g} s  every {rule['interval']:g} s; window {opt('--start')} to {opt('--end')}")
    first_fires, ep_counts = [], []
    for ph in phases:
        series, n = replay(base, rule["expr"], rule["op"], rule["threshold"], rule["for"], rule["interval"], start, end, ph)
        if not series:
            print(f"  phase :{ph:02d}: the query returned no series in the window")
            ep_counts.append(0)
            continue
        for key, pts in series.items():
            eps, pend, nod = simulate(pts, rule["op"], rule["threshold"], rule["for"])
            ep_counts.append(len(eps))
            first_fires += [e[0] for e in eps[:1]]
            desc = ", ".join(f"fired {hms(a)}" + (f" resolved {hms(b)}" if b else " still firing") for a, b in eps) or "never fired"
            print(f"  phase :{ph:02d}: {n} evaluations; {len(eps)} firing episode(s): {desc}; pending runs that did not fire: {len(pend)}; no-data evaluations: {nod}")
    if "--expect-fire" in argv:
        want = tsec(opt("--expect-fire"))
        tol = float(opt("--tolerance", 90))
        n_exp = int(opt("--expect-episodes", 1))
        good = bool(first_fires) and all(abs(f - want) <= tol for f in first_fires) and all(c == n_exp for c in ep_counts)
        print(f"{'PASS' if good else 'FAIL'}: first firing at {', '.join(hms(f) for f in sorted(set(first_fires))) or 'none'} against {hms(want)} (+/- {tol:g} s); episodes per phase {ep_counts} against {n_exp}")
        return 0 if good else 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
