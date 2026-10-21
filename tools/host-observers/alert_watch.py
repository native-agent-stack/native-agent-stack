#!/usr/bin/env python3
"""Print one line to stdout each time a watched Grafana alert rule changes state, so a Monitor task or `journalctl --user -u UNIT -f -o cat` can wake a Claude session on it.

  alert_watch.py [--grafana http://127.0.0.1:21301] (--label notify=cc | --uid UID[,UID]) [--interval 15] [--blind-after 60] [--pending] [--once]

It reads Grafana's Prometheus-compatible rule state, /api/prometheus/grafana/api/v1/rules, which the local Grafana serves to a viewer without a sign-in; it changes nothing and holds no credential.
Lines (UTC time first, one event per line, nothing else is printed while nothing changes):
  WATCH armed          the rules selected and their state at the start, once;
  ALERT FIRING         a watched rule went to firing (with its active-since time and summary);
  ALERT RESOLVED       it left firing for inactive (or, with --pending, left pending);
  ALERT PENDING        only with --pending: the condition turned true and the `for` clock started;
  ALERT NODATA, ALERT ERROR, ALERT HEALTH-OK   the last evaluation returned no data, failed, or is healthy again;
  ALERT RULE-MISSING, ALERT RULE-BACK          a selected rule left or re-entered the rule list (a provisioning reload);
  WATCH BLIND, WATCH OK   Grafana did not answer for --blind-after seconds, and answers again.
--once prints the armed lines and exits (a quick check). Exit status 2 for a usage error.
"""
import datetime
import json
import sys
import time
import urllib.error
import urllib.request


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def flatten(api):
    """Rules from the API document, keyed by uid: name, state, health, labels, annotations, active-since."""
    out = {}
    for g in api.get("data", {}).get("groups", []):
        for r in g.get("rules", []):
            active = [a.get("activeAt") for a in r.get("alerts", []) if a.get("activeAt")]
            out[r["uid"]] = {"name": r.get("name", ""), "state": r.get("state", "inactive"), "health": r.get("health", "ok"), "labels": r.get("labels", {}) or {},
                             "annotations": r.get("annotations", {}) or {}, "active_at": min(active) if active else ""}
    return out


def select(rules, label=None, uids=()):
    """Subset of rules that carry the label (key=value) or are named in uids."""
    k, _, v = (label or "").partition("=")
    return {u: r for u, r in rules.items() if u in set(uids) or (label and r["labels"].get(k) == v)}


def events(prev, cur, selected_uids, include_pending=False):
    """Event lines (without the time) for the change from prev to cur. prev and cur are the flattened rules; selected_uids is the set being watched."""
    out = []
    for uid in sorted(selected_uids):
        p, c = prev.get(uid), cur.get(uid)
        if p is not None and c is None:
            out.append(f"ALERT RULE-MISSING uid={uid}")
            continue
        if c is None:
            continue
        if p is None:
            out.append(f"ALERT RULE-BACK uid={uid} state={c['state']} health={c['health']}")
            continue
        if c["state"] != p["state"]:
            summ = c["annotations"].get("summary", c["name"])
            if c["state"] == "firing":
                out.append(f"ALERT FIRING uid={uid} since={c['active_at'] or '?'} summary={summ!r}")
            elif c["state"] == "inactive" and (p["state"] == "firing" or (p["state"] == "pending" and include_pending)):
                out.append(f"ALERT RESOLVED uid={uid} was={p['state']} summary={summ!r}")
            elif c["state"] == "pending" and include_pending:
                out.append(f"ALERT PENDING uid={uid} summary={summ!r}")
        if c["health"] != p["health"]:
            if c["health"] == "ok":
                out.append(f"ALERT HEALTH-OK uid={uid} (was {p['health']})")
            else:
                out.append(f"ALERT {c['health'].upper()} uid={uid} summary={c['annotations'].get('summary', c['name'])!r}")
    return out


def fetch(base):
    with urllib.request.urlopen(base + "/api/prometheus/grafana/api/v1/rules", timeout=15) as r:
        return json.loads(r.read())


def say(msg):
    print(f"{now_iso()} {msg}", flush=True)


def main(argv):
    opt = lambda name, d=None: argv[argv.index(name) + 1] if name in argv else d
    label, uids = opt("--label"), [u for u in (opt("--uid") or "").split(",") if u]
    if not label and not uids:
        print(__doc__)
        return 2
    base, interval, blind_after = opt("--grafana", "http://127.0.0.1:21301"), float(opt("--interval", 15)), float(opt("--blind-after", 60))
    pending = "--pending" in argv
    prev, watched, down_since, blind = None, set(), None, False
    while True:
        try:
            cur = flatten(fetch(base))
            if blind:
                say("WATCH OK Grafana answers again")
                blind = False
            down_since = None
            if prev is None:
                sel = select(cur, label, uids)
                watched = set(sel) | set(uids)
                say(f"WATCH armed {len(sel)} rule(s) by {label or 'uid'}: " + "; ".join(f"{u} state={r['state']} health={r['health']}" for u, r in sorted(sel.items())))
                if "--once" in argv:
                    return 0
            else:
                # rules that gain the label later are picked up; rules never leave the watched set by themselves
                watched |= set(select(cur, label, uids))
                for line in events(prev, cur, watched, pending):
                    say(line)
            prev = cur
        except (urllib.error.URLError, OSError, ValueError, KeyError) as ex:
            down_since = down_since or time.monotonic()
            if not blind and time.monotonic() - down_since >= blind_after:
                say(f"WATCH BLIND Grafana did not answer for {blind_after:g} s ({type(ex).__name__})")
                blind = True
            if "--once" in argv:
                say(f"WATCH BLIND Grafana did not answer ({type(ex).__name__})")
                return 1
        time.sleep(interval)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
