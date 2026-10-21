#!/usr/bin/env python3
"""Self-test for storm_snapshot_summary.py on synthetic snapshots: UTC parsing is DST-proof, working-directory areas, the window (from inclusive, to exclusive), unusable lines are counted and
skipped, the lanes' own directories are collected from the whole file and not from the window and the home directory never claims anything, the by-cwd hint (longest directory, directory boundary,
shared directory), a lane's rows add up to its cores, episodes split on the gap rule, the leader and the seen share, the under-seen mark, the by-lane order, an empty window and no arguments, and the
tool opens one file, lists no directory and imports only the standard library names it needs. No real /proc or snapshot file is read."""
import ast
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

os.environ["TZ"] = "EST5EDT,M3.2.0,M11.1.0"     # a New York clock with DST in October, so that a local-time slip in the tool shows up on any host
time.tzset()
TOOL = Path(__file__).resolve().parent / "storm_snapshot_summary.py"
spec = importlib.util.spec_from_file_location("storm_snapshot_summary", TOOL)
sm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sm)
failed = 0


def check(name, cond, extra=""):
    global failed
    print(("ok   " if cond else "FAIL ") + name + ((" :: " + str(extra)) if (extra and not cond) else ""))
    failed += 0 if cond else 1


def lane(name, cores, top, root=None):
    return {"lane": name, "root_pid": None, "root_cwd": root, "kind": None, "cores": cores, "processes": len(top),
            "top": [{"shape": s, "cores": c, "n": 1, "cwds": w} for s, c, w in top]}


def snap(utc, trig, meas, lanes):
    return {"utc": utc, "trigger_cores": trig, "sample_s": 2.03, "group_processes": 100, "measured_cores": meas, "lanes": lanes}


UNATTR = "unattributed (no claude ancestor in the group)"
GPT = "/home/example/.cache/ns2604-gpt-reads/x/tree"
LIB, NAS, TRD, API = ("/home/example/code/librarium-course", "/home/example/code/native-agent-stack", "/home/example/code/us-equities-trading",
                      "/home/example/code/native-agent-stack-api-actions")
S0 = snap("2026-10-12T21:35:47Z", 35.0, 22.5, [lane("librarium-course-e2", 20.0, [("python native_probe.py", 20.0, [LIB])], LIB),
                                              lane("librarium-sub", 0.5, [("claude", 0.5, [LIB + "/sub"])], LIB + "/sub"),
                                              lane("workspace-13", 1.0, [("claude", 1.0, ["/home/example"])], "/home/example"),
                                              lane("ns2604-coop", 0.5, [("claude", 0.5, [NAS])], NAS),
                                              lane("wsl-architecture-design", 0.5, [("claude", 0.5, [NAS])], NAS)])
S1 = snap("2026-10-13T09:00:00Z", 40.0, 30.0, [lane(UNATTR, 18.0, [("python3 -m pytest", 12.0, [GPT]), ("codebase-memory-mcp cli", 3.0, ["/var/tmp/cc-wt-harbor"])]),
                                              lane("ns2604-coop", 12.0, [("node", 12.0, [NAS])], NAS)])
S2 = snap("2026-10-13T09:02:00Z", 36.0, 33.0, [lane(UNATTR, 22.0, [("python3 -m pytest", 22.0, [GPT])]),
                                              lane("ns2604-coop", 11.0, [("node", 11.0, [NAS])], NAS)])
S3 = snap("2026-10-13T09:07:00Z", 31.0, 31.0, [lane("trading-cc", 31.0, [("python3 -m pytest", 31.0, [TRD])], TRD)])
S4 = snap("2026-10-13T09:20:00Z", 50.0, 16.5, [lane("api-actions", 10.0, [("cargo test", 10.0, [API])], API),
                                              lane(UNATTR, 6.5, [("python align.py", 4.0, [LIB + "/work"]), ("python3 -m pytest", 2.0, [NAS + "/tools"]),
                                                                 ("find", 0.5, ["/home/example/.cache/x"])])])
S5 = snap("2026-10-13T21:00:00Z", 33.0, 33.0, [lane("trading-cc", 33.0, [("python3 -m pytest", 33.0, [TRD])], TRD)])
BAD = ['{"utc": "2026-10-13T09:30:00Z", "trigger_cores": 3', "[1, 2]", json.dumps({"trigger_cores": 1, "measured_cores": 1, "lanes": []}),
       json.dumps({**S1, "lanes": "none"}), json.dumps({**S1, "utc": "2026-10-13 09:30:00"})]

# UTC strings: seconds of the day must come out as written, whatever the zone or DST (mktime minus timezone is an hour early in October)
check("parse_utc keeps the UTC time of day", sm.parse_utc("2026-10-12T20:00:00Z") % 86400 == 20 * 3600 and sm.parse_utc("2026-10-13T00:00:00Z") - sm.parse_utc("2026-10-12T00:00:00Z") == 86400)
try:
    sm.parse_utc("2026-10-13 09:30:00")
    check("parse_utc rejects a stamp without T and Z", False)
except ValueError:
    check("parse_utc rejects a stamp without T and Z", True)

A = sm.area
check("area: code/<repo>", A("/home/example/code/us-equities-trading/src/x") == "code/us-equities-trading", A("/home/example/code/us-equities-trading/src/x"))
check("area: .cache/<dir>", A(GPT) == ".cache/ns2604-gpt-reads", A(GPT))
check("area: .local keeps three parts", A("/home/example/.local/state/native-agent-stack/coordination") == ".local/state/native-agent-stack")
check("area: home directory itself and a plain child", A("/home/example") == "~" and A("/home/example/notes/a") == "notes")
check("area: /var/tmp child and /tmp child", A("/var/tmp/cc-wt-harbor/src") == "/var/tmp/cc-wt-harbor" and A("/tmp/x/y") == "/tmp/x" and A("/var/tmp") == "/var/tmp")
check("area: other roots keep two parts; empty and missing", A("/srv/data/x/y") == "/srv/data" and A(None) == "-" and A("") == "-" and A("/") == "/")
check("lane_name shortens the unattributed lane", sm.lane_name(UNATTR) == "unattributed" and sm.lane_name("trading-cc") == "trading-cc" and sm.lane_name(None) == "?")

with tempfile.TemporaryDirectory() as d:
    p = Path(d) / "s.jsonl"
    p.write_text("\n".join([json.dumps(S0), json.dumps(S1), BAD[0], json.dumps(S2), "", BAD[1], json.dumps(S3), BAD[2], json.dumps(S4), BAD[3], json.dumps(S5), BAD[4]]) + "\n")

    snaps, bad, homes = sm.load(p, None, None)
    check("load: six usable snapshots in time order, five unusable lines counted (a half-written line, a list, no utc, lanes not a list, a bad stamp)",
          [r["utc"] for r in snaps] == [S["utc"] for S in (S0, S1, S2, S3, S4, S5)] and bad == 5, (len(snaps), bad))
    check("load: the lanes' own directories, a shared one keeps both names, the home directory is left out",
          homes[LIB] == {"librarium-course-e2"} and homes[LIB + "/sub"] == {"librarium-sub"} and homes[NAS] == {"ns2604-coop", "wsl-architecture-design"} and "/home/example" not in homes, dict(homes))
    lo, hi = sm.parse_utc("2026-10-13T09:00:00Z"), sm.parse_utc("2026-10-13T09:20:00Z")
    w, _, hw = sm.load(p, lo, hi)
    check("load: --from is inclusive and --to is exclusive", [r["utc"] for r in w] == ["2026-10-13T09:00:00Z", "2026-10-13T09:02:00Z", "2026-10-13T09:07:00Z"], [r["utc"] for r in w])
    check("load: the window does not limit the lanes' directories (a lane seen only before the window still owns its directory)", hw[LIB] == {"librarium-course-e2"} and hw == homes, dict(hw))
    day, _, _ = sm.load(p, sm.parse_utc("2026-10-13T00:00:00Z"), sm.parse_utc("2026-10-13T20:00:00Z"))
    check("load: the day window drops last night and the evening", [r["utc"][11:16] for r in day] == ["09:00", "09:02", "09:07", "09:20"], [r["utc"] for r in day])

    O = lambda c: sm.owner_of(c, homes)     # noqa: E731
    check("owner_of: a directory under a lane's own directory, and the directory itself", O(LIB + "/work") == "librarium-course-e2" and O(LIB) == "librarium-course-e2", (O(LIB + "/work"), O(LIB)))
    check("owner_of: the longest directory wins", O(LIB + "/sub/x") == "librarium-sub", O(LIB + "/sub/x"))
    check("owner_of: a sibling that only shares the name prefix does not match", O(LIB + "-other") == "-" and O("/home/example/code/librarium") == "-")
    check("owner_of: a directory two lanes share says 'several'", O(NAS + "/tools") == "several", O(NAS + "/tools"))
    check("owner_of: the home directory does not claim what is under it; None and empty give '-'", O("/home/example/.cache/x") == "-" and O(None) == "-" and O("") == "-")

    rows = sm.entries(day[0], homes)
    un = [r for r in rows if r[0] == "unattributed"]
    check("entries: the unattributed lane's rows add up to its cores, with the unlisted remainder as '(other shapes)'",
          abs(sum(r[4] for r in un) - 18.0) < 1e-9 and ("unattributed", "(other shapes)", "-", "-", 3.0) in rows, rows)
    check("entries: shape, area and hint of the listed rows (an attributed lane's hint is '-')",
          ("unattributed", "python3 -m pytest", ".cache/ns2604-gpt-reads", "-", 12.0) in rows and ("ns2604-coop", "node", "code/native-agent-stack", "-", 12.0) in rows, rows)
    rows4 = sm.entries(day[3], homes)
    check("entries: unattributed rows carry the lane whose directory holds the working directory",
          ("unattributed", "python align.py", "code/librarium-course", "librarium-course-e2", 4.0) in rows4 and ("unattributed", "python3 -m pytest", "code/native-agent-stack", "several", 2.0) in rows4
          and ("unattributed", "find", ".cache/x", "-", 0.5) in rows4 and ("api-actions", "cargo test", "code/native-agent-stack-api-actions", "-", 10.0) in rows4, rows4)

    check("episodes: 300 s apart stays in one episode (gap rule is 'more than')", [len(e) for e in sm.episodes(day, 300)] == [3, 1], [len(e) for e in sm.episodes(day, 300)])
    check("episodes: gap 299 splits at the 300 s step; a single snapshot is one episode", [len(e) for e in sm.episodes(day, 299)] == [2, 1, 1] and [len(e) for e in sm.episodes(day[:1], 300)] == [1])
    check("episodes: nothing gives nothing", sm.episodes([], 300) == [])

    e1, e2 = (sm.episode_row(e, homes) for e in sm.episodes(day, 300))
    check("episode 1: leader by cores seen is the unattributed pytest in the GPT-read area, share 34 of 94",
          e1["lead"] == ("unattributed", "python3 -m pytest", ".cache/ns2604-gpt-reads", "-") and abs(e1["share"] - 34.0 / 94.0) < 1e-9 and e1["n"] == 3 and e1["peak"] == 40.0, e1)
    check("episode 1: seen share is measured over trigger (94 of 107)", abs(e1["seen"] - 94.0 / 107.0) < 1e-9, e1["seen"])
    check("episode 2: under-seen (16.5 of 50 trigger cores) and led by the api-actions lane", abs(e2["seen"] - 16.5 / 50.0) < 1e-9 and e2["lead"][0] == "api-actions", e2)

    def run(*a):
        return subprocess.run([sys.executable, "-I", str(TOOL), str(p), *a], capture_output=True, text=True, timeout=30)

    r = run("--from", "2026-10-13T00:00:00Z", "--to", "2026-10-13T20:00:00Z")
    out = r.stdout.splitlines()
    ep = [ln for ln in out if ln[:3].strip().isdigit()]
    check("cli: exit 0, four snapshots, two episodes, five unusable lines", r.returncode == 0 and "4 snapshots; 5 unusable lines skipped" in r.stdout and "2 episodes" in r.stdout, r.stdout[:400] + r.stderr[-300:])
    check("cli: episode 1 line shows 88% seen without the mark; episode 2 shows 33%*", len(ep) == 2 and "88% " in ep[0] and "*" not in ep[0] and "33%*" in ep[1], ep)
    check("cli: times print in UTC, not the host zone", len(ep) == 2 and "10-13 09:00:00..09:07:00" in ep[0] and "10-13 09:20:00..09:20:00" in ep[1], ep)
    check("cli: the episode lines carry lane, shape and area", len(ep) == 2 and "unattributed" in ep[0] and "python3 -m pytest" in ep[0] and ".cache/ns2604-gpt-reads" in ep[0]
          and "api-actions" in ep[1] and "cargo test" in ep[1], ep)
    check("cli: the table has a by-cwd column", any("by cwd" in ln and "leading lane" in ln for ln in out))
    i = out.index("by lane (cores seen, added over snapshots):")
    check("cli: by-lane order is unattributed (46.5 of 110.5, 42%), trading-cc, ns2604-coop, api-actions",
          [ln.split()[0] for ln in out[i + 1:i + 5]] == ["unattributed", "trading-cc", "ns2604-coop", "api-actions"] and "42%" in out[i + 1], out[i + 1:i + 5])
    j = out.index("unattributed cores seen, by the lane whose directory holds the working directory:")
    check("cli: the unattributed total by hint: none 40.5, librarium-course-e2 4.0, several 2.0",
          [ln.split()[0] for ln in out[j + 1:j + 4]] == ["-", "librarium-course-e2", "several"] and "40.5" in out[j + 1] and "4.0" in out[j + 2] and "2.0" in out[j + 3], out[j + 1:j + 4])
    check("cli: the lane, shape and area table names the hinted lane for the librarium-course script",
          any("python align.py" in ln and "librarium-course-e2" in ln and "code/librarium-course" in ln and "unattributed" in ln for ln in out[j + 4:]))
    check("cli: the footnotes are printed (under-seen, above 100%, by cwd)",
          any(ln.startswith("* ") and "lower bound" in ln for ln in out) and any(ln.startswith("seen can pass 100%") for ln in out) and any(ln.startswith("by cwd:") and "not ancestry" in ln for ln in out))
    check("cli: a capped table says how many episodes are not shown", "1 more episodes not shown" in run("--from", "2026-10-13T00:00:00Z", "--to", "2026-10-13T20:00:00Z", "--max-episodes", "1").stdout)
    r = run("--from", "2026-10-14T00:00:00Z")
    check("cli: an empty window says so plainly and exits 0", r.returncode == 0 and "0 snapshots" in r.stdout and "no snapshots in the window" in r.stdout, r.stdout)

r = subprocess.run([sys.executable, "-I", str(TOOL)], capture_output=True, text=True, timeout=30)
check("cli: no arguments prints the usage and exits 2", r.returncode == 2 and "SNAPSHOTS.jsonl" in r.stdout)

# the tool reads the one file it is given: one open() call, no directory listing, no subprocess, standard-library imports only
src = TOOL.read_text()
tree = ast.parse(src)
calls = [n.func.id if isinstance(n.func, ast.Name) else getattr(n.func, "attr", "") for n in ast.walk(tree) if isinstance(n, ast.Call)]
mods = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names} | {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
check("source: exactly one open() call", calls.count("open") == 1, calls.count("open"))
check("source: no listing, globbing, subprocess or key-file names", not any(w in src for w in ("listdir", "iterdir", "scandir", "glob", "subprocess", ".key", "readlink")))
check("source: imports are calendar, json, sys, time, collections", mods == {"calendar", "json", "sys", "time", "collections"}, mods)

print(f"{'all checks passed' if not failed else str(failed) + ' FAILED'}")
sys.exit(1 if failed else 0)
