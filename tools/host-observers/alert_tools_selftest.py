#!/usr/bin/env python3
"""Self-test for alert_replay.py, grafana_rule_add.py and alert_watch.py, with a fake Prometheus and a fake Grafana on loopback and a pass of planted faults.

  alert_tools_selftest.py [--tools DIR] [--only GROUP[,GROUP]] [--mutate]

The real Prometheus, Grafana and rule files are never read or changed. --mutate copies the three tools, plants each fault in the copy, runs the groups that must notice it, and requires a failure.
"""
import argparse
import copy
import http.server
import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS = HERE
RESULTS = []
CURRENT = {"group": ""}
GROUPS = {}
CLEAN = []


def group(fn):
    GROUPS[fn.__name__.replace("_", "-")] = fn
    return fn


def ok(label, cond, detail=""):
    RESULTS.append((CURRENT["group"], label, bool(cond), str(detail)[:400]))


def mod(name):
    spec = importlib.util.spec_from_file_location(name + "_ut", TOOLS / (name + ".py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def run_tool(name, *args, timeout=60):
    return subprocess.run([sys.executable, "-I", str(TOOLS / (name + ".py")), *args], capture_output=True, text=True, timeout=timeout)


def tmpdir():
    d = tempfile.mkdtemp(prefix="alert-selftest-")
    CLEAN.append(d)
    return d


def rule(uid="r1", expr="m", thr=5, op="lt", for_="2m", **over):
    r = {"uid": uid, "title": uid, "condition": "B",
         "data": [{"refId": "A", "relativeTimeRange": {"from": 600, "to": 0}, "datasourceUid": "ds", "model": {"refId": "A", "expr": expr, "instant": True}},
                  {"refId": "B", "relativeTimeRange": {"from": 0, "to": 0}, "datasourceUid": "__expr__",
                   "model": {"refId": "B", "type": "threshold", "expression": "A", "conditions": [{"evaluator": {"type": op, "params": [thr]}}]}}],
         "noDataState": "NoData", "execErrState": "Error", "for": for_, "isPaused": False, "dashboardUid": "dash", "panelId": 1, "labels": {"severity": "CRIT"}, "annotations": {"summary": uid}}
    r.update(over)
    return r


def prov(*rules, interval="1m"):
    return {"apiVersion": 1, "groups": [{"orgId": 1, "name": "g", "folder": "F", "interval": interval, "rules": list(rules)}]}


def write_prov(d, doc, name="rules.yaml", mode=0o644):
    p = Path(d) / name
    p.write_text(json.dumps(doc, indent=2) + "\n")
    p.chmod(mode)
    return p


# ------------------------------------------------------------------------------------------- fake servers
class Fake:
    """A loopback HTTP server whose answer comes from a callback taking (path, query dict) and returning a JSON-able object."""

    def __init__(self, fn):
        outer = self

        class H(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                u = urllib.parse.urlparse(self.path)
                body = json.dumps(fn(u.path, dict(urllib.parse.parse_qsl(u.query)))).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *a):
                pass

        self.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.srv.server_address[1]}"
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def stop(self):
        self.srv.shutdown()
        self.srv.server_close()


def fake_prom(value_fn, gap=lambda t: False):
    def fn(path, q):
        s, e, step = int(float(q["start"])), int(float(q["end"])), int(float(q["step"]))
        vals = [[t, str(value_fn(t))] for t in range(s, e + 1, step) if not gap(t)]
        return {"status": "success", "data": {"resultType": "matrix", "result": [{"metric": {"device": "eth0"}, "values": vals}]}}
    return fn


T0 = 1791954000   # an arbitrary minute boundary
LOW_FROM, LOW_TO = T0 + 570, T0 + 1275    # 9:30 to 21:15 after T0, like the real outage


# ------------------------------------------------------------------------------------------- alert_replay
@group
def replay_sim():
    m = mod("alert_replay")
    ok("durations parse (2m, 0s, 1h30m, a bare number)", m.parse_duration("2m") == 120 and m.parse_duration("0s") == 0 and m.parse_duration("1h30m") == 5400 and m.parse_duration(60) == 60)
    sim = m.simulate
    pts = lambda vals, step=60: [(i * step, v) for i, v in enumerate(vals)]
    eps, pend, nod = sim(pts([100, 100, 1, 1, 1, 1, 100, 100]), "lt", 5, 120)
    ok("fires on the third true evaluation (elapsed 120 s is enough) and resolves at the first false one", eps == [[240, 360]] and pend == [] and nod == 0, (eps, pend))
    eps, pend, _ = sim(pts([100, 1, 1, 100]), "lt", 5, 120)
    ok("two true evaluations only (elapsed 60 s) never fire; one pending run is reported", eps == [] and pend == [(60, 180)], (eps, pend))
    eps, _, _ = sim(pts([100, 5, 5, 5, 5]), "lt", 5, 120)
    ok("a value equal to the threshold is not below it", eps == [])
    eps, _, _ = sim(pts([100, 4.99, 4.99, 4.99]), "lt", 5, 120)
    ok("just below the threshold fires", eps == [[180, None]], eps)
    eps, pend, nod = sim(pts([1, 1, None, 1, 1, 1]), "lt", 5, 120)
    ok("a missing sample restarts the pending clock: it fires at the sixth evaluation, not the third", eps == [[300, None]] and nod == 1 and pend == [(0, 120)], (eps, pend, nod))
    eps, _, _ = sim(pts([100, 1, 1]), "lt", 5, 0)
    ok("for 0 fires at the first true evaluation", eps == [[60, None]], eps)
    eps, _, _ = sim(pts([1, 9, 9, 9, 9]), "gt", 5, 120)
    ok("the gt operator works, and an alert still firing at the end has no resolve time", eps == [[180, None]], eps)
    eps, _, _ = sim(pts([9, 9, 9, 1, 9, 9, 9]), "gt", 5, 120)
    ok("gt: fired at the third true evaluation, resolved at the first false one, then a second episode begins and fires after another 120 s", eps == [[120, 180], [360, None]], eps)
    eps, _, nod = sim(pts([1, 1, 1, None, 100]), "lt", 5, 120)
    ok("a gap while firing resolves the episode at the gap", eps == [[120, 180]] and nod == 1, (eps, nod))


@group
def replay_rule_file():
    m = mod("alert_replay")
    d = tmpdir()
    p = write_prov(d, prov(rule("a", expr="x / 1024", thr=5, for_="2m"), rule("b", expr="y", thr=70, op="gt", for_="0s")))
    r = m.load_rule(str(p), "a")
    ok("load_rule reads the expression, operator, threshold, for and the group interval", r["expr"] == "x / 1024" and r["op"] == "lt" and r["threshold"] == 5.0 and r["for"] == 120.0 and r["interval"] == 60.0, r)
    r = m.load_rule(str(p), "b")
    ok("a second rule gets its own values", r["op"] == "gt" and r["threshold"] == 70.0 and r["for"] == 0.0, r)
    try:
        m.load_rule(str(p), "nope")
        ok("an unknown uid raises KeyError", False)
    except KeyError:
        ok("an unknown uid raises KeyError", True)


def replay_cli(url, rule_path, *extra):
    return run_tool("alert_replay", "--rule-file", str(rule_path), "--uid", "r1", "--start", "2026-10-14T04:00:00Z", "--end", "2026-10-14T06:00:00Z", "--prom", url, *extra, timeout=120)


@group
def replay_cli_fake_prometheus():
    from datetime import datetime, timezone
    t_start = int(datetime(2026, 10, 14, 4, 0, tzinfo=timezone.utc).timestamp())
    low_from, low_to = t_start + 70 * 60 + 30, t_start + 81 * 60 + 15      # 05:10:30 to 05:21:15
    fake = Fake(fake_prom(lambda t: 0.0 if low_from <= t < low_to else 120.0))
    d = tmpdir()
    p = write_prov(d, prov(rule("r1", expr="m", thr=5, for_="2m")))
    r = replay_cli(fake.url, p, "--phases", "0,15,30,45", "--expect-fire", "2026-10-14T05:12:45Z", "--tolerance", "60")
    out = r.stdout
    ok("the replay prints the rule line and one line per phase with a single firing episode", out.count("1 firing episode(s)") == 4 and "lt 5" in out and "for 120 s" in out, out[:600])
    ok("phase :30 fires at 05:12:30 (true from 05:10:30, third true evaluation) and resolves at 05:21:30", "phase :30" in out and "fired 05:12:30 resolved 05:21:30" in out, out)
    ok("phase :00 fires at 05:13:00 and resolves at 05:22:00", "fired 05:13:00 resolved 05:22:00" in out, out)
    ok("--expect-fire within the tolerance passes with exit 0", r.returncode == 0 and "PASS" in out, (r.returncode, out[-300:]))
    r = replay_cli(fake.url, p, "--phases", "30", "--expect-fire", "2026-10-14T05:00:00Z", "--tolerance", "60")
    ok("an expected time far from the firing time fails with exit 1", r.returncode == 1 and "FAIL" in r.stdout, (r.returncode, r.stdout[-200:]))
    r = replay_cli(fake.url, p, "--phases", "30", "--expect-fire", "2026-10-14T05:12:30Z", "--tolerance", "60", "--expect-episodes", "2")
    ok("a different expected episode count fails with exit 1", r.returncode == 1 and "FAIL" in r.stdout, (r.returncode, r.stdout[-200:]))
    fake.stop()
    # a second drop that is too short to fire gives a pending run, not an episode
    short = (t_start + 30 * 60 + 0, t_start + 31 * 60 + 40)
    fake = Fake(fake_prom(lambda t: 0.0 if (low_from <= t < low_to or short[0] <= t < short[1]) else 120.0))
    r = replay_cli(fake.url, p, "--phases", "30", "--expect-fire", "2026-10-14T05:12:30Z", "--tolerance", "60")
    ok("a 100 s dip earlier in the window shows as a pending run that did not fire, and the episode count stays 1", "1 firing episode(s)" in r.stdout and "pending runs that did not fire: 1" in r.stdout and r.returncode == 0, r.stdout[-400:])
    fake.stop()
    # missing samples
    fake = Fake(fake_prom(lambda t: 0.0 if low_from <= t < low_to else 120.0, gap=lambda t: t_start + 71 * 60 <= t < t_start + 72 * 60 + 5))
    r = replay_cli(fake.url, p, "--phases", "30")
    ok("a gap while pending is one no-data evaluation and restarts the clock: the episode fires at 05:14:30 instead of 05:12:30", "no-data evaluations: 1" in r.stdout and "fired 05:14:30 resolved 05:21:30" in r.stdout, r.stdout[-400:])
    fake.stop()
    r = run_tool("alert_replay")
    ok("no arguments: usage and exit 2", r.returncode == 2 and "alert_replay.py --rule-file" in r.stdout, (r.returncode, r.stdout[:80]))


# ------------------------------------------------------------------------------------------- grafana_rule_add
@group
def rule_add():
    d = tmpdir()
    p = write_prov(d, prov(rule("a"), rule("b")), mode=0o640)
    spec = Path(d) / "spec.json"
    spec.write_text(json.dumps(rule("c", expr="z")) + "\n")
    original = p.read_text()
    r = run_tool("grafana_rule_add", "check", str(p))
    ok("check passes on a good file and says it reads back identically", r.returncode == 0 and "no problems" in r.stdout and "identically: True" in r.stdout, r.stdout)
    r = run_tool("grafana_rule_add", "add", str(p), str(spec))
    doc = json.loads(p.read_text())
    baks = sorted(Path(d).glob("rules.yaml.bak-*"))
    ok("add appends the rule: 2 -> 3, in order, and prints the backup name", r.returncode == 0 and [x["uid"] for x in doc["groups"][0]["rules"]] == ["a", "b", "c"] and "2 -> 3" in r.stdout, r.stdout)
    ok("the backup holds the old content byte for byte and is mode 0600", len(baks) == 1 and baks[0].read_text() == original and stat.S_IMODE(baks[0].stat().st_mode) == 0o600, [str(b) for b in baks])
    ok("the file keeps its mode (0640) and no temp file is left behind", stat.S_IMODE(p.stat().st_mode) == 0o640 and not list(Path(d).glob("*.tmp-*")), oct(stat.S_IMODE(p.stat().st_mode)))
    r = run_tool("grafana_rule_add", "add", str(p), str(spec))
    ok("adding the same uid again is refused (exit 1) and the file is unchanged", r.returncode == 1 and "already exists" in r.stdout and json.loads(p.read_text()) == doc, r.stdout)
    r = run_tool("grafana_rule_add", "remove", str(p), "c")
    ok("remove is the inverse: the file reads back byte-identical to the original, even when it follows the add within the same second (a second backup, not a crash)", r.returncode == 0 and p.read_text() == original and len(list(Path(d).glob("rules.yaml.bak-*"))) == 2, (r.stdout, r.stderr[-200:]))
    r = run_tool("grafana_rule_add", "remove", str(p), "nope")
    ok("removing an unknown uid is refused (exit 1)", r.returncode == 1 and "found 0 times" in r.stdout, r.stdout)
    bad = rule("e")
    del bad["panelId"]
    spec.write_text(json.dumps(bad))
    r = run_tool("grafana_rule_add", "add", str(p), str(spec))
    ok("a rule missing a key the others have is refused", r.returncode == 1 and "missing ['panelId']" in r.stdout and p.read_text() == original, r.stdout)
    spec.write_text(json.dumps(rule("e", condition="Z")))
    r = run_tool("grafana_rule_add", "add", str(p), str(spec))
    ok("a condition that names no query is refused", r.returncode == 1 and "condition 'Z'" in r.stdout, r.stdout)
    spec.write_text(json.dumps(rule("e", **{"for": "banana"})))
    r = run_tool("grafana_rule_add", "add", str(p), str(spec))
    ok("a for that does not parse is refused", r.returncode == 1 and "does not parse" in r.stdout, r.stdout)
    spec.write_text(json.dumps(rule("e")))
    r = run_tool("grafana_rule_add", "add", str(p), str(spec), "--group", "nope")
    ok("an unknown group is refused and nothing is written", r.returncode == 1 and "no group nope" in r.stdout and p.read_text() == original, r.stdout)
    bdir = Path(d) / "elsewhere"
    bdir.mkdir()
    r = run_tool("grafana_rule_add", "add", str(p), str(spec), "--backup-dir", str(bdir))
    inside = [x.name for x in Path(d).glob("rules.yaml.bak-*")]
    outside = list(bdir.glob("rules.yaml.bak-*"))
    ok("--backup-dir puts the new backup in that directory and none beside the file", r.returncode == 0 and len(outside) == 1 and len(inside) == 2 and outside[0].read_text() == original, (r.stdout, inside, outside))
    r = run_tool("grafana_rule_add")
    ok("no arguments: usage and exit 2", r.returncode == 2 and "check  FILE" in r.stdout)


@group
def rule_check():
    d = tmpdir()
    p = write_prov(d, prov(rule("a"), rule("a")))
    r = run_tool("grafana_rule_add", "check", str(p))
    ok("check flags a duplicate uid (exit 1)", r.returncode == 1 and "duplicate uid a" in r.stdout, r.stdout)
    odd = rule("b")
    odd["extra"] = 1
    p = write_prov(d, prov(rule("a"), odd), name="odd.yaml")
    r = run_tool("grafana_rule_add", "check", str(p))
    ok("check flags rules with different key sets", r.returncode == 1 and "same key set" in r.stdout, r.stdout)
    p = write_prov(d, prov(rule("a"), interval="soon"), name="iv.yaml")
    r = run_tool("grafana_rule_add", "check", str(p))
    ok("check flags a group interval that does not parse", r.returncode == 1 and "interval 'soon'" in r.stdout, r.stdout)
    p2 = Path(d) / "loose.yaml"
    p2.write_text(json.dumps(prov(rule("a")), indent=4))
    r = run_tool("grafana_rule_add", "check", str(p2))
    ok("a file written with another indent still passes but says it does not read back identically", r.returncode == 0 and "identically: False" in r.stdout, r.stdout)


# ------------------------------------------------------------------------------------------- alert_watch
def api(*rules):
    return {"status": "success", "data": {"groups": [{"name": "g", "rules": list(rules)}]}}


def prule(uid, state="inactive", health="ok", notify=None, summary=None, active=None):
    labels = {"severity": "CRIT"}
    if notify:
        labels["notify"] = notify
    return {"uid": uid, "name": uid, "state": state, "health": health, "labels": labels, "annotations": {"summary": summary or f"{uid} summary"},
            "alerts": [{"activeAt": active, "state": "Alerting"}] if active else []}


@group
def watch_events():
    m = mod("alert_watch")
    flat = m.flatten(api(prule("a", notify="cc"), prule("b"), prule("c", state="firing", active="2026-10-14T05:11:40Z")))
    ok("flatten keys rules by uid and reads state, health, labels and the active-since time", set(flat) == {"a", "b", "c"} and flat["c"]["active_at"] == "2026-10-14T05:11:40Z" and flat["a"]["labels"]["notify"] == "cc", flat)
    ok("select by label picks only rules with that value", set(m.select(flat, label="notify=cc")) == {"a"} and set(m.select(flat, label="notify=zz")) == set())
    ok("select by uid picks the named rules, and a label miss does not pick a rule that merely has the key", set(m.select(flat, uids=["b", "c"])) == {"b", "c"})
    flat2 = m.flatten(api(prule("a", notify="x")))
    ok("a rule with the label key but another value is not selected", set(m.select(flat2, label="notify=cc")) == set())
    ev = m.events
    P = lambda s, h="ok", **k: m.flatten(api(prule("a", state=s, health=h, **k)))
    ok("inactive to firing: one FIRING line with the since time and the summary", ev(P("inactive"), P("firing", active="2026-10-14T05:11:40Z"), {"a"}) == ["ALERT FIRING uid=a since=2026-10-14T05:11:40Z summary='a summary'"], ev(P("inactive"), P("firing", active="2026-10-14T05:11:40Z"), {"a"}))
    ok("firing to inactive: one RESOLVED line", ev(P("firing"), P("inactive"), {"a"}) == ["ALERT RESOLVED uid=a was=firing summary='a summary'"])
    ok("pending lines are off by default and the matching resolve is silent too", ev(P("inactive"), P("pending"), {"a"}) == [] and ev(P("pending"), P("inactive"), {"a"}) == [])
    ok("with --pending both the PENDING and the resolve lines print", ev(P("inactive"), P("pending"), {"a"}, True) == ["ALERT PENDING uid=a summary='a summary'"] and len(ev(P("pending"), P("inactive"), {"a"}, True)) == 1)
    ok("pending to firing prints FIRING", ev(P("pending"), P("firing", active="t"), {"a"})[0].startswith("ALERT FIRING"))
    ok("no change: no lines", ev(P("firing"), P("firing"), {"a"}) == [] and ev(P("inactive"), P("inactive"), {"a"}) == [])
    ok("health ok to nodata prints NODATA, nodata to ok prints HEALTH-OK, error prints ERROR", ev(P("inactive"), P("inactive", "nodata"), {"a"})[0].startswith("ALERT NODATA") and ev(P("inactive", "nodata"), P("inactive"), {"a"})[0].startswith("ALERT HEALTH-OK")
       and ev(P("inactive"), P("inactive", "error"), {"a"})[0].startswith("ALERT ERROR"))
    ok("a rule that leaves the list prints RULE-MISSING; one that returns prints RULE-BACK", ev(P("inactive"), m.flatten(api()), {"a"}) == ["ALERT RULE-MISSING uid=a"] and ev(m.flatten(api()), P("firing"), {"a"})[0].startswith("ALERT RULE-BACK uid=a state=firing"))
    ok("a rule that is not watched produces nothing", ev(P("inactive"), P("firing"), set()) == [])


def start_watch(url, *args):
    p = subprocess.Popen([sys.executable, "-I", str(TOOLS / "alert_watch.py"), "--grafana", url, *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
    lines = []

    def pump():
        for ln in p.stdout:
            lines.append(ln.rstrip("\n"))

    threading.Thread(target=pump, daemon=True).start()
    return p, lines


def wait_lines(lines, n, timeout=20):
    t0 = time.time()
    while time.time() - t0 < timeout and len(lines) < n:
        time.sleep(0.05)
    return len(lines) >= n


@group
def watch_live():
    state = {"rules": [prule("a", notify="cc"), prule("b")]}
    fake = Fake(lambda path, q: api(*state["rules"]))
    r = run_tool("alert_watch", "--grafana", fake.url, "--label", "notify=cc", "--once")
    ok("--once prints the armed line for the selected rule and exits 0", r.returncode == 0 and "WATCH armed 1 rule(s) by notify=cc: a state=inactive health=ok" in r.stdout, (r.returncode, r.stdout, r.stderr[-200:]))
    p, lines = start_watch(fake.url, "--label", "notify=cc", "--interval", "0.2")
    wait_lines(lines, 1)
    state["rules"] = [prule("a", state="firing", notify="cc", active="2026-10-14T05:11:40Z"), prule("b")]
    wait_lines(lines, 2)
    state["rules"] = [prule("a", state="inactive", notify="cc"), prule("b", state="firing")]
    wait_lines(lines, 3)
    time.sleep(0.8)
    p.terminate()
    p.wait(timeout=10)
    text = "\n".join(lines)
    ok("the watcher printed armed, FIRING and RESOLVED for the selected rule, in that order, and nothing for the other rule", len(lines) == 3 and "WATCH armed" in lines[0] and "ALERT FIRING uid=a since=2026-10-14T05:11:40Z" in lines[1] and "ALERT RESOLVED uid=a" in lines[2] and "uid=b" not in "\n".join(lines[1:]), text)
    ok("every line starts with a UTC time", all(len(ln) > 20 and ln[4] == "-" and ln[10] == "T" and ln[19] == "Z" for ln in lines), text)
    fake.stop()
    state = {"rules": [prule("a", notify="cc")]}
    fake = Fake(lambda path, q: api(*state["rules"]))
    p, lines = start_watch(fake.url, "--uid", "a", "--interval", "0.2", "--blind-after", "0.6")
    wait_lines(lines, 1)
    fake.stop()
    ok("with Grafana gone the watcher says BLIND once after the blind-after time", wait_lines(lines, 2, 15) and "WATCH BLIND" in lines[1], lines)
    time.sleep(1.0)
    ok("it does not repeat the BLIND line while Grafana stays gone", sum("WATCH BLIND" in ln for ln in lines) == 1, lines)
    p.terminate()
    p.wait(timeout=10)
    r = run_tool("alert_watch")
    ok("no selection: usage and exit 2", r.returncode == 2 and "alert_watch.py" in r.stdout)
    r = run_tool("alert_watch", "--grafana", "http://127.0.0.1:9", "--uid", "a", "--once")
    ok("--once with nothing listening exits 1 with a BLIND line", r.returncode == 1 and "WATCH BLIND" in r.stdout, (r.returncode, r.stdout))


MUTANTS = [
    ("pending fires only after more than the for time", "alert_replay.py", "if t - starts >= for_s:", "if t - starts > for_s:", ["replay-sim"]),
    ("the lt comparison includes the threshold", "alert_replay.py", '"lt": lambda v: v < threshold', '"lt": lambda v: v <= threshold', ["replay-sim"]),
    ("the gt comparison is reversed", "alert_replay.py", '"gt": lambda v: v > threshold', '"gt": lambda v: v < threshold', ["replay-sim"]),
    ("a missing sample does not restart the clock", "alert_replay.py", "            nodata += 1\n            if state == \"firing\":", "            nodata += 1\n            continue\n            if state == \"firing\":", ["replay-sim"]),
    ("a false evaluation never records the resolve time", "alert_replay.py", "        else:\n            if state == \"firing\":\n                episodes[-1][1] = t", "        else:\n            if state == \"firing\":\n                pass", ["replay-sim"]),
    ("for 0 waits one evaluation", "alert_replay.py", "            if for_s > 0:\n                state, starts = \"pending\", t", "            if for_s >= 0:\n                state, starts = \"pending\", t", ["replay-sim"]),
    ("the evaluation phase is ignored", "alert_replay.py", "t0 = start - (start % interval) + phase", "t0 = start - (start % interval)", ["replay-cli-fake-prometheus"]),
    ("the rule's for is read as zero", "alert_replay.py", '"for": parse_duration(r.get("for", "0s"))', '"for": parse_duration("0s")', ["replay-rule-file"]),
    ("the expected-fire check ignores the time", "alert_replay.py", "good = bool(first_fires) and all(abs(f - want) <= tol for f in first_fires) and", "good = bool(first_fires) and", ["replay-cli-fake-prometheus"]),
    ("--backup-dir is ignored", "grafana_rule_add.py", "bak = os.path.join(backup_dir or os.path.dirname(path) or \".\", os.path.basename(path))", "bak = os.path.join(os.path.dirname(path) or \".\", os.path.basename(path))", ["rule-add"]),
    ("a duplicate uid is accepted", "grafana_rule_add.py", "        if any(r[\"uid\"] == spec.get(\"uid\") for g in new[\"groups\"] for r in g[\"rules\"]):", "        if False and any(r[\"uid\"] == spec.get(\"uid\") for g in new[\"groups\"] for r in g[\"rules\"]):", ["rule-add"]),
    ("the backup is world-readable", "grafana_rule_add.py", "fd = os.open(bak, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)", "fd = os.open(bak, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)", ["rule-add"]),
    ("the file mode is not kept", "grafana_rule_add.py", "mode = os.stat(path).st_mode & 0o777", "mode = 0o600", ["rule-add"]),
    ("removing an unknown uid succeeds", "grafana_rule_add.py", "if removed != 1:", "if removed < 0:", ["rule-add"]),
    ("a condition that names no query is accepted", "grafana_rule_add.py", "if r.get(\"condition\") not in refids:", "if False:", ["rule-add"]),
    ("an unknown group appends to the first group", "grafana_rule_add.py", "if name is None or g[\"name\"] == name:", "if True:", ["rule-add"]),
    ("duplicate uids are not flagged", "grafana_rule_add.py", "            if uid in seen:", "            if False:", ["rule-check"]),
    ("a bad group interval is not flagged", "grafana_rule_add.py", "        if not DUR.match(str(g.get(\"interval\", \"\"))):", "        if False:", ["rule-check"]),
    ("the FIRING line is never printed", "alert_watch.py", "            if c[\"state\"] == \"firing\":", "            if c[\"state\"] == \"firing_\":", ["watch-events"]),
    ("pending lines print without the flag", "alert_watch.py", "elif c[\"state\"] == \"pending\" and include_pending:", "elif c[\"state\"] == \"pending\":", ["watch-events"]),
    ("a pending flap prints RESOLVED without the flag", "alert_watch.py", "(p[\"state\"] == \"firing\" or (p[\"state\"] == \"pending\" and include_pending))", "(p[\"state\"] in (\"firing\", \"pending\"))", ["watch-events"]),
    ("the label match checks only the key", "alert_watch.py", "r[\"labels\"].get(k) == v", "k in r[\"labels\"]", ["watch-events"]),
    ("the healthy-again line is dropped", "alert_watch.py", "            if c[\"health\"] == \"ok\":\n                out.append(f\"ALERT HEALTH-OK uid={uid} (was {p['health']})\")", "            if c[\"health\"] == \"ok\":\n                pass", ["watch-events"]),
    ("the blind report never happens", "alert_watch.py", "if not blind and time.monotonic() - down_since >= blind_after:", "if False:", ["watch-live"]),
    ("the blind line repeats on every poll", "alert_watch.py", "                blind = True\n", "                blind = False\n", ["watch-live"]),
]


def run_mutant(m):
    name, fname, old, new, groups = m
    with tempfile.TemporaryDirectory(prefix="alert-mut-") as d:
        for f in ("alert_replay.py", "grafana_rule_add.py", "alert_watch.py"):
            shutil.copy(HERE / f, d)
        p = Path(d) / fname
        s = p.read_text()
        if s.count(old) != 1:
            return name, None, f"text found {s.count(old)} times"
        p.write_text(s.replace(old, new))
        r = subprocess.run([sys.executable, "-I", str(Path(__file__).resolve()), "--tools", d, "--only", ",".join(groups)], capture_output=True, text=True, timeout=600)
        return name, r.returncode != 0, (r.stdout.strip().splitlines() or [""])[-1]


def mutate():
    union = sorted({g for m in MUTANTS for g in m[4]})
    r = subprocess.run([sys.executable, "-I", str(Path(__file__).resolve()), "--only", ",".join(union)], capture_output=True, text=True, timeout=900)
    print(f"control: the unmodified files pass the {len(union)} groups the matrix uses: {'yes' if r.returncode == 0 else 'NO'}")
    if r.returncode != 0:
        print("\n".join(x for x in r.stdout.splitlines() if x.startswith("FAIL")))
        return 1
    with ThreadPoolExecutor(max_workers=3) as ex:
        results = list(ex.map(run_mutant, MUTANTS))
    caught = 0
    for name, c, info in results:
        print(("caught  " if c else "MISSED  " if c is False else "BROKEN  ") + name + ("" if c else f"  [{info}]"))
        caught += 1 if c else 0
    print(f"{caught} of {len(MUTANTS)} planted faults caught")
    return 0 if caught == len(MUTANTS) else 1


def main():
    global TOOLS
    ap = argparse.ArgumentParser()
    ap.add_argument("--tools")
    ap.add_argument("--only")
    ap.add_argument("--mutate", action="store_true")
    a = ap.parse_args()
    if a.tools:
        TOOLS = Path(a.tools).resolve()
    if a.mutate:
        return mutate()
    names = a.only.split(",") if a.only else list(GROUPS)
    unknown = [n for n in names if n not in GROUPS]
    if unknown:
        print("unknown group:", unknown, "known:", sorted(GROUPS))
        return 2
    try:
        for n in names:
            CURRENT["group"] = n
            try:
                GROUPS[n]()
            except Exception as ex:
                ok(f"group {n} crashed", False, f"{type(ex).__name__}: {ex}")
    finally:
        for p in CLEAN:
            shutil.rmtree(p, ignore_errors=True)
    bad = [r for r in RESULTS if not r[2]]
    for g, label, good, detail in RESULTS:
        print(("ok   " if good else "FAIL ") + f"[{g}] {label}" + ((" :: " + detail) if (detail and not good) else ""))
    print(f"{len(RESULTS) - len(bad)} of {len(RESULTS)} checks passed in {len(names)} groups" + (f", {len(bad)} FAILED" if bad else ""))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
