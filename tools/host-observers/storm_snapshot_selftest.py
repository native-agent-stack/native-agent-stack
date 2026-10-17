#!/usr/bin/env python3
"""Self-test for storm_snapshot.py: command shapes drop flags, values and anything secret-looking, copy only the program, a script or module name and a fixed vocabulary of subcommands (a
rewritten process title, option values, unknown first arguments, wrapped commands and the kernel-name fallback, each checked at the function and in the serialized lanes); lane attribution by claude ancestry with the unattributed remainder kept; the detector's
need and min-gap rules; the tool never opens a .key file or lists the sessions directory; a live --once snapshot of the real group parses and its shapes and lane names leak no long opaque
string. Real /proc is read only by the last three checks."""
import ast
import importlib.util
import json
import os
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


def count_group(path):
    """cgroup.procs entries under `path`, counted here and not by the tool."""
    n = 0
    for root, _dirs, files in os.walk(path):
        if "cgroup.procs" in files:
            try:
                n += len(Path(root, "cgroup.procs").read_text().split())
            except OSError:
                pass
    return n


def saw_group(seen, before, after, slack=25):
    """The snapshot counted the group: within one sample's churn of what the cgroup files held before and after.
    A machine with no such cgroup (a CI runner) holds nothing, so the snapshot must hold nothing too. The earlier
    `seen > 50` was true only on the workstation and failed on every runner.
    Mechanism relied on, at its pin: the tool enumerates the group with os.walk, which ignores a scandir error unless
    onerror is given and so yields nothing for a missing top (python/cpython@v3.13.16, tag commit cbc944f4bc59,
    Lib/os.py:321 for the documented default and Lib/os.py:368-373 for the try/except around scandir(top))."""
    lo, hi = min(before, after), max(before, after)
    if hi == 0:
        return seen == 0
    return max(1, lo - slack) <= seen <= hi + slack


S = ss.shape
check("pytest through python -m", S(["/home/example/.venv/bin/python3.13", "-m", "pytest", "tests/test_a.py", "-x", "-q"]) == "python3.13 -m pytest")
check("script run keeps the script base name only", S(["python3", "/home/example/code/uet/tools/run_mutation.py", "--token", "abc"]) == "python3 run_mutation.py")
check("-c drops the code", S(["python3", "-c", "import os; print(os.environ)"]) == "python3 -c")
check("a key-looking script name is redacted", S(["python3", "/x/sk-abcdef123456.py"]) == "python3 <redacted>", S(["python3", "/x/sk-abcdef123456.py"]))
check("a long opaque argument is redacted", S(["somecli", "A" * 40 + "B"]) == "somecli <redacted>")
check("a long opaque argument to node is not copied (only a script file would be)", S(["node", "A" * 40 + "B"]) == "node")
check("a token passed to a non-interpreter is not kept", "ghp_" not in S(["curl", "ghp_abcdefghijkl", "https://x"]) and S(["curl", "ghp_abcdefghijkl"]) == "curl <redacted>")
check("cargo test keeps the subcommand", S(["/usr/bin/cargo", "test", "--release"]) == "cargo test")
check("a path argument to a non-interpreter is dropped", S(["rm", "/tmp/a/b"]) == "rm")
check("uv run pytest keeps two words", S(["uv", "run", "pytest", "-q"]) == "uv run pytest")
check("wrapper: systemd-run idle scope", S(["systemd-run", "--user", "--scope", "-p", "CPUWeight=idle", "python3", "-m", "pytest"]) == "systemd-run python3 -m pytest")
check("wrapper: nice and env assignments", S(["nice", "-n", "10", "env", "A=1", "python3", "x.py"]) == "nice env python3 x.py")
check("empty command line", S([]) == "" and S(["", ""]) == "")
check("a version-named executable falls back to the process name", S(["/home/example/.local/share/claude/versions/2.1.296", "-p", "x"], "claude") == "claude" and S(["2.1.296"]) == "2.1.296")

# Sensitive text must not reach a shape. Text is copied from a command line in three places only: the program's base name, a script's or module's base name, and a word of a fixed
# vocabulary of subcommands. Every other argument, every option value and any rewritten process title becomes a fixed marker or is dropped. SENT is short and word-like, so no secret
# pattern would catch it: it stands for any value a user could put on a command line.
SENT = "zq7w9mk"
SHAPE_CASES = [
    ("a process title rewritten into one string is shaped by the kernel's name", [f"app --flag={SENT}"], "app", "app"),
    ("a rewritten title with a directory in it does not leak its last path segment", [f"app --root=/srv/{SENT}"], "app", "app"),
    ("a rewritten title with no usable kernel name gets a fixed marker", [f"app --flag={SENT}"], "", "<proc>"),
    ("a key-looking kernel name is not copied either", [f"app --flag={SENT}"], "token-svc", "<proc>"),
    ("a kernel name with a space is a plain name", ["Web Content --type=x"], "Web Content", "Web Content"),
    ("an unknown program's first argument is a fixed marker", ["somecli", SENT], "", "somecli <arg>"),
    ("an unknown program's option value is dropped", ["somecli", "--opt", SENT], "", "somecli"),
    ("a known program keeps its subcommand", ["git", "status", "-sb"], "", "git status"),
    ("a known program's unknown first word is a fixed marker", ["git", SENT], "", "git <arg>"),
    ("an option before the subcommand stops the extraction", ["git", "-C", f"/w/{SENT}", "status"], "", "git"),
    ("a URL argument is not copied", ["curl", f"https://user:{SENT}@host.example"], "", "curl <arg>"),
    ("a runner stops at an option whose arity it does not know", ["npm", "--opt-x", SENT, "run", "build"], "", "npm"),
    ("a tool runner keeps the tool and nothing after it", ["npx", "eslint", SENT], "", "npx eslint"),
    ("an interpreter's option value is not a script", ["python3", "-W", SENT, "run_x.py"], "", "python3 run_x.py"),
    ("inline code after a bundled flag is dropped (python)", ["python3", "-I", "-c", SENT], "", "python3 -c"),
    ("inline code after a bundled flag is dropped (shell)", ["bash", "-lc", SENT], "", "bash -c"),
    ("inline code is dropped (node)", ["node", "-e", SENT], "", "node -e"),
    ("a bare word that is no script is not copied", ["python3", SENT], "", "python3"),
    ("an option before the script ends node's extraction (its value cannot be told from a script)", ["node", "--max-old-space-size", SENT, "build.js"], "", "node"),
    ("a path-shaped option value of node is not taken for a script", ["node", "--redirect-warnings", f"/tmp/{SENT}.log", "app.js"], "", "node"),
    ("a path-shaped option value of node after the script is not read either", ["node", "app.js", "--redirect-warnings", f"/tmp/{SENT}.log"], "", "node app.js"),
    ("node's first argument as a script file", ["node", f"/w/{SENT}/build.js"], "", "node build.js"),
    ("node with inline code, long form with a value", ["node", f"--eval={SENT}"], "", "node -e"),
    ("a shell's option before the script ends the extraction", ["bash", "-x", f"/w/{SENT}.sh"], "", "bash"),
    ("a shell script as the first argument", ["bash", "/w/x/run.sh", SENT], "", "bash run.sh"),
    ("a long option of a shell with a value is not a script", ["bash", "--rcfile", f"/w/{SENT}.rc", "run.sh"], "", "bash"),
    ("perl with inline code", ["perl", "-ne", SENT], "", "perl -e"),
    ("perl with an option before the script", ["perl", "-w", f"/w/{SENT}.pl"], "", "perl"),
    ("python: -W attached to its value", ["python3", f"-W{SENT}", "run_x.py"], "", "python3 run_x.py"),
    ("python: -X attached to its value", ["python3", f"-X{SENT}", "run_x.py"], "", "python3 run_x.py"),
    ("python: -X with its value as the next word", ["python3", "-X", SENT, "run_x.py"], "", "python3 run_x.py"),
    ("python: a bundle ending in an option with a value", ["python3", "-uW", SENT, "run_x.py"], "", "python3 run_x.py"),
    ("python: -m attached to its module, and what follows is the module's own", ["python3", "-mpytest", f"/w/{SENT}/test_a.py"], "", "python3 -m pytest"),
    ("python: a bundle ending in -m", ["python3", "-Im", "pytest", f"/w/{SENT}/test_a.py"], "", "python3 -m pytest"),
    ("python: -c attached to its code", ["python3", f"-c{SENT}", "run_x.py"], "", "python3 -c"),
    ("python: a bundle with -c in the middle takes the rest as the code", ["python3", f"-Ic{SENT}", "run_x.py"], "", "python3 -c"),
    ("python: what follows -c is the code's own arguments", ["python3", "-c", "pass", f"/w/{SENT}/run_x.py"], "", "python3 -c"),
    ("python: the long option with an argument takes the next word", ["python3", "--check-hash-based-pycs", SENT, "run_x.py"], "", "python3 run_x.py"),
    ("python: the long option with = is unknown to CPython, nothing runs", ["python3", f"--check-hash-based-pycs={SENT}", "run_x.py"], "", "python3"),
    ("python: an unknown long option, nothing is read", ["python3", f"--{SENT}", "run_x.py"], "", "python3"),
    ("python: an unknown short option, nothing is read", ["python3", "-Z", "run_x.py"], "", "python3"),
    ("python: -- ends the options", ["python3", "-u", "--", "run_x.py"], "", "python3 run_x.py"),
    ("python: a lone dash is standard input", ["python3", "-", f"/w/{SENT}/run_x.py"], "", "python3"),
    ("python: -h prints and exits", ["python3", "-h", "run_x.py"], "", "python3"),
    ("python: a missing argument", ["python3", "-W"], "", "python3"),
    ("python: -m with a name that is no module name", ["python3", "-m", f"/w/{SENT}.py"], "", "python3 -m <arg>"),
    ("npm: an unknown subcommand", ["npm", SENT], "", "npm <arg>"),
    ("npm run: a script name that is not a well-known one", ["npm", "run", SENT], "", "npm run <arg>"),
    ("npm run: a well-known script name", ["npm", "run", "build", "--", SENT], "", "npm run build"),
    ("npm: an option before the subcommand", ["npm", f"--prefix=/w/{SENT}", "run", "build"], "", "npm"),
    ("npm run: an option after the subcommand", ["npm", "run", "--workspace", SENT, "build"], "", "npm run"),
    ("uv run: a target that is not a known tool", ["uv", "run", SENT], "", "uv run <arg>"),
    ("uv run: an option before the target", ["uv", "run", "--with", SENT, "pytest"], "", "uv run"),
    ("uv run: python with its own grammar", ["uv", "run", "python", "-m", "pytest", f"/w/{SENT}/test_a.py"], "", "uv run python -m pytest"),
    ("uv run: python with an option value", ["uv", "run", "python", "-W", SENT, "run_x.py"], "", "uv run python run_x.py"),
    ("uv run: a script file", ["uv", "run", f"/w/{SENT}/tool.py", SENT], "", "uv run tool.py"),
    ("uv: a subcommand without a target", ["uv", "sync", "--frozen", SENT], "", "uv sync"),
    ("npx: a tool that is not a known one", ["npx", SENT], "", "npx <arg>"),
    ("uvx: a tool that is not a known one", ["uvx", f"{SENT}@1.0"], "", "uvx <arg>"),
    ("bun: a subcommand of its own and what follows is dropped", ["bun", "run", SENT], "", "bun run"),
    ("bun: an unknown word", ["bun", SENT], "", "bun <arg>"),
    ("deno: no vocabulary, so a word is the marker", ["deno", "run", f"/w/{SENT}.ts"], "", "deno <arg>"),
    ("timeout: a duration that is not a number ends the extraction", ["timeout", SENT, "python3", "run_x.py"], "", "timeout"),
    ("timeout: a number, then the command", ["timeout", "5m", "python3", "run_x.py", SENT], "", "timeout python3 run_x.py"),
    ("chrt: a priority that is not a number ends the extraction", ["chrt", "-r", SENT, "python3"], "", "chrt"),
    ("chrt: a priority, then the command", ["chrt", "-r", "10", "git", "status"], "", "chrt git status"),
    ("taskset: a CPU list that is not a number ends the extraction", ["taskset", "-c", SENT, "git"], "", "taskset"),
    ("taskset: a CPU list, then the command", ["taskset", "-c", "0-3,8", "git", "log"], "", "taskset git log"),
    ("env: assignments are skipped without being read", ["env", f"A={SENT}", f"B=/w/{SENT}", "python3", "run_x.py"], "", "env python3 run_x.py"),
    ("a wrapper inside a wrapper", ["nice", "-n", "5", "timeout", "30", "git", "status"], "", "nice timeout git status"),
    ("a wrapper nested beyond the depth limit (four wrappers are read, the fifth is an ordinary program)", ["nice"] * 6 + [f"/w/{SENT}.sh"], "", "nice nice nice nice nice <arg>"),
    ("a wrapper's option value is not the command (sudo)", ["sudo", "-u", SENT, "git", "status"], "", "sudo git status"),
    ("a wrapper's option value is not the command (timeout)", ["timeout", "-s", SENT, "5", "python3", "x.py"], "", "timeout python3 x.py"),
    ("a wrapper's option value is not the command (env)", ["env", "-u", SENT, "python3", "x.py"], "", "env python3 x.py"),
    ("a wrapper's option value is not the command (systemd-run)", ["systemd-run", "--unit", SENT, "python3", "x.py"], "", "systemd-run python3 x.py"),
    ("a wrapper flag it does not know ends the extraction", ["nice", "--unknown-flag", SENT, "cmd"], "", "nice"),
    ("a title as the wrapped command is reduced too", ["env", f"app --flag={SENT}"], "", "env <proc>"),
]
for label, argv, comm, want in SHAPE_CASES:
    got = S(argv, comm)
    check(label, got == want and SENT not in got, (want, got))

# ---- the Python rules against the installed interpreter: command lines built from valid options are run for real, and what the reducer says ran is what ran. The options and their values come from a
# pool that includes the sentinel as a value (-W, -X) and as the arguments of the script, of the module and of the code, so the same lines also show that none of that text reaches the shape.
import random
import shutil
import subprocess

PROBE = 'import json, os, sys\nprint(json.dumps({"file": os.path.basename(sys.argv[0]), "args": sys.argv[1:]}))\n'
interp_name = S([sys.executable]).split(" ")[0]
if not re.match(r"^python[0-9.]*$", interp_name):
    check("the installed interpreter is named python*, so the differential run applies (otherwise skipped)", True)
else:
    rng = random.Random(20261014)
    flags = ["-B", "-s", "-S", "-u", "-E", "-b", "-O", "-OO", "-q", "-I", "-P", "-R", "-BsS", "-uq", "-Eb"]
    valued = [["-W", "ignore"], ["-W", SENT], [f"-W{SENT}"], ["-X", "dev"], ["-X", SENT], [f"-X{SENT}"], ["-uW", SENT], ["-BX", SENT], ["--check-hash-based-pycs", "never"], ["--check-hash-based-pycs", "default"]]
    with tempfile.TemporaryDirectory() as dtmp:
        target = Path(dtmp) / "probe_target.py"
        target.write_text(PROBE)
        bad = []
        ran = {"script": 0, "module": 0, "code": 0}
        for n in range(90):
            opts = []
            for _ in range(rng.randint(0, 3)):
                opts += rng.choice(valued) if rng.random() < 0.6 else [rng.choice(flags)]
            kind = rng.choice(["script", "script2", "module", "module2", "code", "code2"])
            if kind == "script":
                tail, want_kind = [str(target), "arg1", SENT, f"/w/{SENT}.log"], "script"
            elif kind == "script2":
                tail, want_kind = ["--", str(target), SENT], "script"
            elif kind == "module":
                tail, want_kind = ["-m", "this", SENT], "module"
            elif kind == "module2":
                tail, want_kind = ["-mthis", f"/w/{SENT}"], "module"
            elif kind == "code":
                tail, want_kind = ["-c", "import sys\nprint('CODE', sys.argv[1:])", SENT], "code"
            else:
                tail, want_kind = ["-cprint('CODE')", f"/w/{SENT}/x.py"], "code"
            argv = [sys.executable] + opts + tail
            r = subprocess.run(argv, capture_output=True, text=True, timeout=60, cwd=dtmp)
            if want_kind == "script":
                real = f"{interp_name} probe_target.py" if r.returncode == 0 and '"file": "probe_target.py"' in r.stdout else None
            elif want_kind == "module":
                real = f"{interp_name} -m this" if r.returncode == 0 and "Zen of Python" in r.stdout else None
            else:
                real = f"{interp_name} -c" if r.returncode == 0 and "CODE" in r.stdout else None
            ran[want_kind] += real is not None
            got = S(argv)
            if real is None or got != real or SENT in got:
                bad.append((argv[1:], r.returncode, got, real))
        check("90 valid command lines run for real: the reducer names exactly what the installed interpreter ran, every line ran, and the sentinel is in no shape",
              not bad and all(v > 0 for v in ran.values()), (ran, bad[:2]))

# ---- a seeded property over every family. Each line is built from benign program, subcommand, tool and script names; the sentinel, in 14 shapes (a word, a path, a script-named file, =, attached to an
# option, @, a URL, spaces, quotes, a trailing slash, ./, ~/, a version), is placed only where the grammar does not name it as the program, the module or the script: as option values, as the
# arguments after the target, as assignments, as the unknown subcommand or target of a runner, as the number a wrapper requires, and as garbage options. It must never reach the shape.
rng = random.Random(7)
FORMS = [SENT, f"/tmp/{SENT}.log", f"{SENT}.js", f"--opt={SENT}", f"-o{SENT}", f"@{SENT}", f"k={SENT}", f"https://h.example/{SENT}", f"{SENT} {SENT}", f"'{SENT}'", f"{SENT}/", f"./{SENT}", f"~/{SENT}", f"{SENT}@1.2"]
NOSCRIPT = [f for f in FORMS if not re.search(r"\.(py|pyw|sh|bash|zsh|js|mjs|cjs|ts|mts|cts|rb|pl|php|lua|jl)$", f, re.I)]
WRAPPER_NUMBERS = {"timeout": 1, "chrt": 1, "taskset": 1}       # the numbers these wrappers require before the command: a duration, a priority, a CPU list or mask
OPTION_TOKENS = ["-x", "--flag", "-v", "--quiet", "-n", "--prefix", "--with", "--workspace", "-C", "-p", "-u", "--unknown-flag", "-W", "-X", "-m", "-c", "-e", "--eval", "--rcfile", "--redirect-warnings", "--"]
BENIGN_INNER = [["git", "status"], ["python3", "run_x.py"], ["node", "build.js"], ["pytest", "-q"], ["cargo", "test"]]


def junk(k):
    return [rng.choice(FORMS) for _ in range(k)]


def option_run(allow_values=True):
    """Garbage in the option positions of the programs whose grammar is not read (npm): option tokens, each possibly followed by a value of any shape."""
    out = []
    for _ in range(rng.randint(0, 3)):
        o = rng.choice(OPTION_TOKENS) if rng.random() < 0.7 else "-" + rng.choice(FORMS)
        out.append(o)
        if allow_values and rng.random() < 0.6:
            out.append(rng.choice(FORMS))
    return out


def py_options():
    """Options of the python command line with a known arity, so that no sentinel lands in the script position: flags, -W and -X with the value as the next word or attached, the long option with
    its value as the next word, and an unknown option (after which nothing is read)."""
    out = []
    for _ in range(rng.randint(0, 3)):
        r = rng.random()
        if r < 0.35:
            out.append(rng.choice(["-B", "-u", "-E", "-s", "-q", "-I", "-OO"]))
        elif r < 0.65:
            out += [rng.choice(["-W", "-X"]), rng.choice(FORMS)]
        elif r < 0.8:
            out.append(rng.choice(["-W", "-X"]) + rng.choice(FORMS))
        elif r < 0.9:
            out += ["--check-hash-based-pycs", rng.choice(FORMS)]
        else:
            out.append(rng.choice(["--" + rng.choice(FORMS), "-" + rng.choice(FORMS)]))
    return out


def gen_line():
    fam = rng.choice(["python", "first_arg", "npm", "uv", "tool_runner", "generic", "wrapper"])
    if fam == "python":
        prog = rng.choice(["python3", "python3.13", "python"])
        target = rng.choice([["bench.py"], ["-m", "pytest"], ["-c", "pass"], ["-mpytest"], ["--", "bench.py"]])
        return [prog] + py_options() + target + junk(rng.randint(0, 3))
    if fam == "first_arg":
        prog = rng.choice(["node", "bash", "sh", "perl"])
        first = rng.choice([["build.js"], ["-e"], ["-lc"]] + [[o] for o in OPTION_TOKENS[:6]])
        return [prog] + first + junk(rng.randint(0, 4))
    if fam == "npm":
        sub = rng.choice([[], ["run"], ["exec"], ["install"], rng.choice(NOSCRIPT).split(" ")[:1]])
        tgt = [] if not sub or sub[0] not in ("run", "exec") else rng.choice([[rng.choice(NOSCRIPT)], ["build"], ["--workspace", rng.choice(FORMS)]])
        return ["npm"] + option_run(False)[:1] + sub + tgt + junk(rng.randint(0, 3))
    if fam == "uv":
        sub = rng.choice([["run"], ["sync"], ["pip"], [rng.choice(NOSCRIPT)]])
        tgt = [] if sub[0] != "run" else rng.choice([[rng.choice(NOSCRIPT)], ["pytest"], ["python", "-W", rng.choice(FORMS), "bench.py"], ["--with", rng.choice(FORMS), "pytest"]])
        return ["uv"] + sub + tgt + junk(rng.randint(0, 3))
    if fam == "tool_runner":
        return [rng.choice(["npx", "uvx", "bunx"])] + rng.choice([[rng.choice(NOSCRIPT)], ["eslint"], ["--yes", rng.choice(FORMS)]]) + junk(rng.randint(0, 3))
    if fam == "generic":
        prog = rng.choice(["git", "cargo", "docker", "systemctl", "somecli", "deno", "ruby", "bun", "restic", "gh"])
        return [prog] + junk(rng.randint(0, 5))
    name = rng.choice(sorted(ss.WRAPPERS))
    plain, valued_flags = ss.WRAPPER_FLAGS[name]
    opts = []
    for _ in range(rng.randint(0, 3)):
        if valued_flags and rng.random() < 0.5:
            f = rng.choice(sorted(valued_flags))
            opts += [f, rng.choice(FORMS)] if rng.random() < 0.7 else [f"{f}={rng.choice(FORMS)}" if f.startswith("--") else f + rng.choice(FORMS)]
        elif plain:
            opts.append(rng.choice(sorted(plain)))
    nums = ["5"] * WRAPPER_NUMBERS.get(name, 0) if rng.random() < 0.7 else junk(WRAPPER_NUMBERS.get(name, 0))
    assigns = [f"A={rng.choice(FORMS)}"] if name == "env" and rng.random() < 0.6 else []
    inner = rng.choice(BENIGN_INNER) + junk(rng.randint(0, 3))
    return [name] + opts + assigns + nums + inner


leaks = []
for n in range(3000):
    argv = gen_line()
    got = S(argv)
    if SENT in got:
        leaks.append((argv, got))
check("3000 seeded random command lines across every family (python, node/shell/perl, npm, uv, tool runners, other programs, 13 wrappers): the sentinel, in 14 shapes, is in no shape", not leaks, leaks[:2])

# the same cases at the snapshotter's output boundary: one lane each, serialized as the tool writes it
t2, sess2 = {}, {}
for i, (label, argv, comm, want) in enumerate(SHAPE_CASES):
    t2[1000 + 2 * i] = {"comm": "claude", "ppid": 1, "cores": 0.1}
    t2[1001 + 2 * i] = {"comm": comm, "ppid": 1000 + 2 * i, "cores": 1.0, "argv": argv, "cwd": "/w/x"}
    sess2[1000 + 2 * i] = {"name": f"lane-{i}", "cwd": "/w/x", "kind": "interactive"}
t2[5000] = {"comm": "claude", "ppid": 1, "cores": 0.1}
t2[5001] = {"comm": "my-secret-x", "ppid": 5000, "cores": 1.0}      # no command line was read: the kernel name stands in for the shape
t2[5002] = {"comm": "claude", "ppid": 1, "cores": 0.1}
t2[5003] = {"comm": "plain-name", "ppid": 5002, "cores": 1.0}
t2[5004] = {"comm": "claude", "ppid": 1, "cores": 0.1}
t2[5005] = {"comm": "jbd2/sdd-8", "ppid": 5004, "cores": 1.0}      # a kernel thread: its name has a slash and is the whole point of the IO attribution
sess2[5000], sess2[5002], sess2[5004] = {"name": "lane-secretish"}, {"name": "lane-plain"}, {"name": "lane-kernel"}
lanes2 = ss.aggregate(t2, sess2)
blob2 = json.dumps(lanes2)
by_lane = {x["lane"]: x["top"][0]["shape"] for x in lanes2 if x["top"]}
wants = {f"lane-{i}": w for i, (_l, _a, _c, w) in enumerate(SHAPE_CASES)}
check("the serialized snapshot holds no sentinel value", SENT not in blob2, [x for x in by_lane.values() if SENT in x][:3])
check("every lane's serialized shape is the one shape() gives for its command line", all(by_lane.get(k) == w for k, w in wants.items()), {k: by_lane.get(k) for k, w in wants.items() if by_lane.get(k) != w})
check("with no command line, a key-looking kernel name is replaced by a fixed marker and a plain one (a kernel thread's, with a slash, too) is kept", by_lane.get("lane-secretish") == "<proc>"
      and by_lane.get("lane-plain") == "plain-name" and by_lane.get("lane-kernel") == "jbd2/sdd-8" and "my-secret-x" not in blob2,
      (by_lane.get("lane-secretish"), by_lane.get("lane-plain"), by_lane.get("lane-kernel")))

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

# the group check itself, with numbers: a runner with no cgroup, the workstation, a tool that saw nothing, one that saw too much
check("group check: no cgroup and an empty snapshot agree (a CI runner)", saw_group(0, 0, 0))
check("group check: a snapshot of 3 processes of an empty group is wrong", not saw_group(3, 0, 0))
check("group check: an empty snapshot of a group that held 300 is wrong", not saw_group(0, 300, 310))
check("group check: 305 of a group that held 300 to 310 is right", saw_group(305, 300, 310))
check("group check: 900 of a group that held 300 to 310 is wrong", not saw_group(900, 300, 310))

# live --once snapshot of the real group: parses, has the keys, and its shapes and lane names hold no long opaque string
tmp = Path(tempfile.mkdtemp()) / "s.jsonl"
GROUP = os.environ.get("STORM_SELFTEST_GROUP", ss.GROUP_DEFAULT)  # point it at a missing path to rehearse a CI runner
group_before = count_group(GROUP)
r = subprocess.run([sys.executable, "-I", str(TOOL), str(tmp), "--once", "--sample", "1.0", "--group", GROUP], capture_output=True, text=True, timeout=60)
ok = r.returncode == 0 and tmp.exists()
rec = json.loads(tmp.read_text().splitlines()[-1]) if ok else {}
check("live --once exits 0 and writes one parseable line", ok and {"utc", "trigger_cores", "sample_s", "group_processes", "measured_cores", "lanes"} <= set(rec), (r.returncode, r.stderr[-200:]))
texts = [x["lane"] for x in rec.get("lanes", [])] + [s["shape"] for x in rec.get("lanes", []) for s in x["top"]]
long_tokens = [m for tx in texts for m in re.findall(r"[A-Za-z0-9+/_-]{28,}", tx)]
check("the live snapshot's shapes and lane names hold no long opaque string", not long_tokens, long_tokens[:3])
group_after = count_group(GROUP)
check("the live snapshot saw the group", saw_group(rec.get("group_processes", -1), group_before, group_after) and isinstance(rec.get("lanes"), list),
      (group_before, rec.get("group_processes"), group_after))

print("\n" + ("ALL PASS" if failed == 0 else f"{failed} FAILED"))
sys.exit(1 if failed else 0)
