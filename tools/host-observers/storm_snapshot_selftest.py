#!/usr/bin/env python3
"""Self-test for storm_snapshot.py: command shapes drop flags, values and anything secret-looking; lane attribution by claude ancestry with the unattributed remainder kept; the detector's
need and min-gap rules; the tool never opens a .key file or lists the sessions directory; a live --once snapshot of the real group parses and its shapes and lane names leak no long opaque
string. Real /proc is read only by the last three checks."""
import ast
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

TOOL = Path(__file__).resolve().parent / "storm_snapshot.py"
spec = importlib.util.spec_from_file_location("storm_snapshot", TOOL)
ss = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ss)
failed = 0


def check(name, cond, extra=""):
    global failed
    print(("ok   " if cond else "FAIL ") + name + ((" :: " + str(extra)) if (extra and not cond) else ""))
    failed += 0 if cond else 1


S = ss.shape
check("pytest through python -m", S(["/home/example/.venv/bin/python3.13", "-m", "pytest", "tests/test_a.py", "-x", "-q"]) == "python3.13 -m pytest")
check("script run keeps the script base name only", S(["python3", "/home/example/code/uet/tools/run_mutation.py", "--token", "abc"]) == "python3 run_mutation.py")
check("-c drops the code", S(["python3", "-c", "import os; print(os.environ)"]) == "python3 -c")
check("a key-looking script name is redacted", S(["python3", "/x/sk-abcdef123456.py"]) == "python3 <redacted>", S(["python3", "/x/sk-abcdef123456.py"]))
check("a long opaque argument is redacted", S(["node", "A" * 40 + "B"]) == "node <redacted>")
check("a token passed to a non-interpreter is not kept", "ghp_" not in S(["curl", "ghp_abcdefghijkl", "https://x"]) and S(["curl", "ghp_abcdefghijkl"]) == "curl <redacted>")
check("cargo test keeps the subcommand", S(["/usr/bin/cargo", "test", "--release"]) == "cargo test")
check("a path argument to a non-interpreter is dropped", S(["rm", "/tmp/a/b"]) == "rm")
check("uv run pytest keeps two words", S(["uv", "run", "pytest", "-q"]) == "uv run pytest")
check("wrapper: systemd-run idle scope", S(["systemd-run", "--user", "--scope", "-p", "CPUWeight=idle", "python3", "-m", "pytest"]) == "systemd-run python3 -m pytest")
check("wrapper: nice and env assignments", S(["nice", "-n", "10", "env", "A=1", "python3", "x.py"]) == "nice env python3 x.py")
check("empty command line", S([]) == "" and S(["", ""]) == "")
check("a version-named executable falls back to the process name", S(["/home/example/.local/share/claude/versions/2.1.296", "-p", "x"], "claude") == "claude" and S(["2.1.296"]) == "2.1.296")

# aggregation: session A (claude 100) runs 47 pytest shards under a bash; session B (claude 200) one node; an orphan with no claude ancestor
t = {1: {"comm": "systemd", "ppid": 0, "cores": 0.0},
     100: {"comm": "claude", "ppid": 1, "cores": 0.1}, 101: {"comm": "bash", "ppid": 100, "cores": 0.0},
     200: {"comm": "claude", "ppid": 1, "cores": 0.4, "argv": ["claude"]}, 203: {"comm": "node", "ppid": 200, "cores": 3.0, "argv": ["node", "build.js"], "cwd": "/w/b"},
     300: {"comm": "python3", "ppid": 1, "cores": 2.0, "argv": ["python3", "-m", "http.server"], "cwd": "/w/o"}}
for i in range(47):
    t[1000 + i] = {"comm": "python3", "ppid": 101, "cores": 0.9, "argv": ["python3", "-m", "pytest", f"tests/t{i}.py"], "cwd": "/w/a"}
sess = {100: {"name": "lane-a", "cwd": "/w/a", "kind": "interactive"}, 200: {"name": "lane-b", "cwd": "/w/b", "kind": "interactive"}}
lanes = ss.aggregate(t, sess)
check("lanes ordered by cores", [x["lane"] for x in lanes] == ["lane-a", "lane-b", "unattributed (no claude ancestor in the group)"], [x["lane"] for x in lanes])
a = lanes[0]
check("lane a: 47 shards, 42.3 cores, one shape", a["processes"] == 47 and a["cores"] == 42.3 and a["top"] == [{"shape": "python3 -m pytest", "cores": 42.3, "n": 47, "cwds": ["/w/a"]}], a)
check("lane b counts its claude root and its node", lanes[1]["processes"] == 2 and {s["shape"] for s in lanes[1]["top"]} == {"node build.js", "claude"}, lanes[1])
check("the orphan is kept as unattributed", lanes[2]["root_pid"] is None and lanes[2]["cores"] == 2.0 and lanes[2]["top"][0]["shape"] == "python3 -m http.server", lanes[2])
check("processes below 0.25 cores are not counted", sum(x["processes"] for x in lanes) == 47 + 2 + 1, sum(x["processes"] for x in lanes))
check("a ppid cycle does not hang", ss.lane_of(2, {2: {"comm": "bash", "ppid": 3, "cores": 0}, 3: {"comm": "bash", "ppid": 2, "cores": 0}}) is None)

# detector: two polls in a row at or above 30; during a long storm one snapshot per min-gap
d = ss.Detector(30.0, 2, 30.0)
seq = [(10, 0), (35, 1), (36, 2), (37, 3), (5, 4), (40, 40), (41, 41), (42, 80)]
fired = [t_ for c, t_ in seq if d.feed(c, t_)]
check("detector: fires on the second consecutive poll, waits the gap, fires again in a continuing storm", fired == [2, 41, 80], fired)
check("one poll above the threshold is not a storm", not any(ss.Detector(30.0, 2, 30.0).feed(c, i) for i, c in enumerate([10, 50, 10, 50, 10])))

# the tool opens only <pid>.json in the sessions directory: no .key literal in code, no directory listing
tree = ast.parse(TOOL.read_text())
doc = ast.get_docstring(tree)
consts = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value != tree.body[0].value.value]
calls = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)} | {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
check("no code string mentions .key", not any(".key" in c for c in consts), [c for c in consts if ".key" in c])
check("the sessions directory is never listed or globbed", not ({"iterdir", "glob", "rglob", "listdir", "scandir"} & calls), sorted({"iterdir", "glob", "rglob", "listdir", "scandir"} & calls))

# live --once snapshot of the real group: parses, has the keys, and its shapes and lane names hold no long opaque string
tmp = Path(tempfile.mkdtemp()) / "s.jsonl"
r = subprocess.run([sys.executable, "-I", str(TOOL), str(tmp), "--once", "--sample", "1.0"], capture_output=True, text=True, timeout=60)
ok = r.returncode == 0 and tmp.exists()
rec = json.loads(tmp.read_text().splitlines()[-1]) if ok else {}
check("live --once exits 0 and writes one parseable line", ok and {"utc", "trigger_cores", "sample_s", "group_processes", "measured_cores", "lanes"} <= set(rec), (r.returncode, r.stderr[-200:]))
texts = [x["lane"] for x in rec.get("lanes", [])] + [s["shape"] for x in rec.get("lanes", []) for s in x["top"]]
long_tokens = [m for tx in texts for m in re.findall(r"[A-Za-z0-9+/_-]{28,}", tx)]
check("the live snapshot's shapes and lane names hold no long opaque string", not long_tokens, long_tokens[:3])
check("the live snapshot saw the group", rec.get("group_processes", 0) > 50 and isinstance(rec.get("lanes"), list), rec.get("group_processes"))

print("\n" + ("ALL PASS" if failed == 0 else f"{failed} FAILED"))
sys.exit(1 if failed else 0)
