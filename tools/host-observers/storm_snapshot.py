#!/usr/bin/env python3
"""Passive storm snapshotter (read-only; it writes only its own two files). Asked for by the command center on 2026-10-12: when a storm of 30 or more cores runs in the sessions cgroup
(/non-systemd) outside the idle-class scope, name the lane and the command shape.

  storm_snapshot.py OUT.jsonl [--group /sys/fs/cgroup/non-systemd] [--threshold-cores 30] [--need 2] [--poll 1.0] [--sample 2.0] [--min-gap 30] [--max-hours 24] [--max-lines 5000] [--once]

It reads the group's cpu.stat every --poll seconds. After --need polls in a row at or above --threshold-cores (and at least --min-gap seconds after the last snapshot) it samples every process of the
group twice, --sample seconds apart, and appends one JSON line to OUT.jsonl: the lanes (a lane is the `claude` session that is the ancestor of the process; its name and directory come from
~/.claude/sessions/<pid>.json, the only file of that directory it opens, never the .key files), each lane's cores and its top command shapes with a process count and up to two working directories.
OUT.log (next to it) gets a heartbeat every 10 minutes and any error. --once takes one snapshot now, whatever the load (for a dry run).

Privacy: raw command lines are never stored. A shape names what a process is, never what it was given. Text is copied from a command line in three places only: the program's base name (a process
that rewrote its title into one string is named by the kernel's process name instead, and nothing after it is read), the base name of a script or the module of `-m`, and one word of a fixed vocabulary
of subcommands (SUBCOMMANDS, and the words a runner such as npm or uv takes). Everything else is dropped or replaced by a fixed marker: flags and the values they take, any other argument (<arg>),
anything that looks like a key, token or long opaque string (<redacted>), the code after -c, and a process name that is not plain text (<proc>). The extraction stops at a flag whose arity it does not know,
because the next word may be its value. Per-process views miss processes that live less than the sample window, so measured_cores is reported beside the group's cores.
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
COMM_RX = re.compile(r"^[A-Za-z0-9_.:@+ ,/-]{1,40}$")       # a kernel process name: plain characters; spaces (Firefox's "Web Content") and slashes (kworker/u8:1, jbd2/sdd-8) are part of real names
ASSIGN_RX = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
NUMERIC_RX = re.compile(r"^(0x[0-9a-fA-F]+|[0-9][0-9.,-]*[smhd]?)$")       # a duration, a priority or a CPU mask
SCRIPT_RX = re.compile(r"\.(py|pyw|sh|bash|zsh|js|mjs|cjs|ts|mts|cts|rb|pl|php|lua|jl)$", re.I)
INTERPRETERS = re.compile(r"^(python[0-9.]*|node|nodejs|bash|sh|dash|zsh|deno|bun|ruby|perl|php)$")
# What each interpreter family treats as inline code, and the short options that take the next word as a value. Checked against the installed python3, node, bash and perl --help on
# 2026-10-14 (python3 -c, -m, -W, -X; node -e, -p, -r, -C; bash -c, -o, -O; perl -e, -E); ruby's -e and php's -r are from their documentation, neither is installed here.
CODE_LETTERS = {"python": "c", "sh": "c", "node": "ep", "ruby": "e", "perl": "eE", "php": "r"}
VALUED_SHORT = {"python": "WX", "node": "rC", "sh": "oO"}
# Wrappers: (flags that take no value, flags that take the next word as a value), read from the installed tools' --help on 2026-10-14 (coreutils env, nice and timeout; util-linux
# ionice and setsid; systemd-run; GNU time, xargs, stdbuf; sudo; chrt and taskset of util-linux). A flag a table does not list ends the extraction, because its next word may be its value.
WRAPPER_FLAGS = {
    "env": ({"-i", "--ignore-environment", "-0", "--null", "-v", "--debug"}, {"-u", "--unset", "-C", "--chdir", "-S", "--split-string", "-a", "--argv0"}),
    "nice": (set(), {"-n", "--adjustment"}),
    "timeout": ({"--foreground", "--preserve-status", "-v", "--verbose"}, {"-s", "--signal", "-k", "--kill-after"}),
    "time": ({"-p", "--portability", "-v", "--verbose", "-a", "--append", "-q", "--quiet"}, {"-f", "--format", "-o", "--output"}),
    "setsid": ({"-c", "--ctty", "-f", "--fork", "-w", "--wait"}, set()),
    "nohup": (set(), set()),
    "xargs": ({"-0", "--null", "-r", "--no-run-if-empty", "-t", "--verbose", "-p", "--interactive", "-x", "--exit", "-o", "--open-tty"},
              {"-n", "--max-args", "-P", "--max-procs", "-I", "-d", "--delimiter", "-s", "--max-chars", "-a", "--arg-file", "-E", "-L", "--max-lines"}),
    "systemd-run": ({"--user", "--scope", "-q", "--quiet", "--wait", "--collect", "--no-block", "--no-ask-password", "-t", "--pty", "-P", "--pipe", "-d", "--same-dir",
                     "-S", "--shell", "--remain-after-exit", "-G", "--ignore-failure", "--send-sighup", "--no-pager"},
                    {"-p", "--property", "-E", "--setenv", "-u", "--unit", "--slice", "--description", "-M", "--machine", "-H", "--host", "--uid", "--gid", "--nice", "--working-directory",
                     "--service-type", "--on-active", "--on-boot", "--on-calendar", "--on-startup", "--on-unit-active", "--on-unit-inactive"}),
    "sudo": ({"-n", "--non-interactive", "-S", "--stdin", "-i", "--login", "-s", "--shell", "-k", "-K", "-b", "-A"}, {"-u", "--user", "-g", "--group", "-D", "--chdir", "-p", "--prompt"}),
    "rtk": (set(), set()),
    "stdbuf": (set(), {"-i", "--input", "-o", "--output", "-e", "--error"}),
    "ionice": ({"-t", "--ignore"}, {"-c", "--class", "-n", "--classdata", "-p", "--pid", "-P", "--pgid", "-u", "--uid"}),
    "chrt": ({"-b", "--batch", "-f", "--fifo", "-i", "--idle", "-o", "--other", "-r", "--rr", "-R", "--reset-on-fork", "-m", "--max", "-v", "--verbose"}, {"-T", "--sched-runtime", "-P", "--sched-period", "-D", "--sched-deadline"}),
    "taskset": ({"-a", "--all-tasks", "-c", "--cpu-list"}, set()),
}
WRAPPERS = set(WRAPPER_FLAGS)
# Runners: the package-manager style ones keep a subcommand and, after one of RUNNER_TARGETS, the program or script it runs; the tool runners keep the tool only.
RUNNER_TARGETS = {"npm": {"run", "exec", "x", "run-script"}, "pnpm": {"run", "exec", "dlx", "x"}, "yarn": {"run", "exec", "dlx"}, "uv": {"run", "tool"}, "pipx": {"run"}}
TOOL_RUNNERS = {"npx", "uvx", "bunx"}
RUNNERS = TOOL_RUNNERS | set(RUNNER_TARGETS)
RUNNER_FLAGS = {"-q", "--quiet", "--silent", "-y", "--yes", "--no-color", "--verbose", "--offline", "--frozen", "--locked", "--no-progress"}       # known to take no value
# The subcommand words that are copied from a command line, program by program. Each word was found in the installed tool's own help on 2026-10-14 (git, gh, docker, systemctl, restic, pip,
# apt); git's list is a subset of command-list.txt of git/git@v2.53.0 (tag commit 67ad42147a7a, the installed version); cargo is not installed here: its words are the built-in commands of
# rust-lang/cargo@0.99.0 (tag commit 797e8a9bca27, src/bin/cargo/commands/mod.rs:3-44 and :95-133), plus clippy and fmt, which rustup installs as the external subcommands cargo-clippy and
# cargo-fmt. A word that is not listed is never copied: it is shown as the fixed marker <arg>.
SUBCOMMANDS = {
    "git": frozenset("status diff log show fetch pull push clone checkout switch restore commit add rebase merge worktree gc repack fsck grep blame stash reset cherry-pick bisect apply am remote branch "
                     "tag submodule ls-files ls-tree rev-parse rev-list cat-file pack-objects index-pack unpack-objects update-index write-tree read-tree merge-tree patch-id hash-object "
                     "for-each-ref maintenance prune count-objects config init clean mv rm describe shortlog notes archive bundle format-patch diff-tree diff-index".split()),
    "cargo": frozenset("build test check clippy run fmt bench doc install fetch update clean tree metadata publish package vendor add remove new init search".split()),
    "gh": frozenset("pr issue run api repo workflow release gist search status browse extension codespace cache variable label ruleset project".split()),
    "docker": frozenset("run build compose ps exec logs pull push images stop start rm rmi network volume system buildx container image inspect cp commit tag".split()),
    "systemctl": frozenset("start stop restart reload status is-active is-enabled is-failed show list-units list-timers list-unit-files daemon-reload enable disable mask unmask reset-failed cat edit kill".split()),
    "restic": frozenset("backup check forget prune snapshots ls stats diff restore mount init unlock rewrite copy find cat tag generate version repair recover migrate".split()),
    "pip": frozenset("install uninstall list freeze show wheel download check config cache index inspect".split()),
    "apt": frozenset("update upgrade install remove autoremove list search show full-upgrade".split()),
}
SUBCOMMANDS["pip3"], SUBCOMMANDS["apt-get"] = SUBCOMMANDS["pip"], SUBCOMMANDS["apt"]


def arg(name, default=None):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def safe_comm(c):
    """The kernel's process name as safe text: plain characters and no key-looking text, else the fixed marker <proc>."""
    c = (c or "")[:40]
    return c if COMM_RX.match(c) and not SECRET_RX.search(c) else "<proc>"


def _program(raw, comm=""):
    """(name, plain): the base name of the first command-line word when it is one plain word without key-looking text, else the kernel's process name and plain False.
    A process that rewrote its title into one string (chrome does) has spaces, flags or directories in its first word, and none of it is used, nor anything after it.
    A version-like executable name (the versioned claude binary is called 2.1.296) is replaced by the kernel's process name."""
    t = (raw or "").strip()
    if t and not re.search(r"[\s=]", t):
        b = t.rstrip("/").rsplit("/", 1)[-1]
        if comm and re.fullmatch(r"[0-9][0-9.]*", b):
            return safe_comm(comm), True
        if 0 < len(b) <= 40 and WORD_RX.match(b) and not SECRET_RX.search(b):
            return b, True
    return safe_comm(comm), False


def _word(t):
    """One argument token as safe text, or None to drop it. A path is reduced to its base name; a URL, an assignment or anything that is not one plain word is the marker <arg>,
    and anything key-looking is the marker <redacted>."""
    t = t.strip()
    if not t or t.startswith("-"):
        return None
    if "://" in t or "=" in t:
        return "<arg>"
    if "/" in t:
        t = t.rstrip("/").rsplit("/", 1)[-1]
    if not t:
        return None
    if SECRET_RX.search(t):
        return "<redacted>"
    return t[:40] if WORD_RX.match(t[:48]) else "<arg>"


def _interpreter(fam, rest):
    """The words after an interpreter: `-m MODULE`, the marker of inline code (the code itself is never kept), or the base name of the script. A bare word that is neither a script (a path or
    a script extension) nor key-looking is not copied, whether it is an option's value or an argument; a key-looking one shows as <redacted>."""
    codes, valued = CODE_LETTERS.get(fam, ""), VALUED_SHORT.get(fam, "")
    k = 0
    while k < len(rest):
        t = rest[k]
        k += 1
        if t.startswith("-") and len(t) > 1:
            if fam == "node" and t in ("--eval", "--print"):
                return ["-e" if t == "--eval" else "-p"]
            if re.fullmatch(r"-[A-Za-z]+", t):
                letters = t[1:]
                if fam == "python" and letters.endswith("m"):
                    return ["-m", _word(rest[k]) or ""] if k < len(rest) else ["-m"]
                hit = next((c for c in codes if c in letters), None)
                if hit:
                    return ["-" + hit]
                if letters[-1] in valued:
                    k += 1                                  # the next word is this option's value
            continue
        if "=" in t or "://" in t:
            continue
        if "/" in t or SCRIPT_RX.search(t):
            return [_word(t) or ""]
        if SECRET_RX.search(t):
            return ["<redacted>"]
    return []


def _runner(b0, rest):
    """The words after a runner (npm, uv, npx and the like): its subcommand and, after one that runs something, the program or script it runs; a tool runner keeps the tool only. The
    extraction stops at the first option it does not know to be valueless, because the next word may be that option's value."""
    words = []
    for t in rest:
        if t.startswith("-"):
            if t in RUNNER_FLAGS or "=" in t:
                continue
            break
        words.append(_word(t) or "")
        if b0 in TOOL_RUNNERS or len(words) == 2 or words[0] not in RUNNER_TARGETS.get(b0, ()):
            break
    return [w for w in words if w]


def _generic(b0, rest):
    """The one word that may follow any other program: a subcommand of the fixed vocabulary of that program. An unknown first word is the marker <arg>, a key-looking one <redacted>, an
    option, a path or an assignment is dropped (so is everything after the first word)."""
    t = rest[0] if rest else ""
    if not t or t.startswith("-"):
        return []
    if "://" in t:
        return ["<arg>"]
    if "/" in t or "=" in t:
        return []
    if t in SUBCOMMANDS.get(b0, ()):
        return [t]
    return ["<redacted>"] if SECRET_RX.search(t) else ["<arg>"]


def _wrapper(name, rest, depth):
    """`name` plus the command it runs. Skipped without being read: KEY=VALUE assignments, bare numbers (a duration, a priority, a CPU mask) and the wrapper's own flags with the values
    its table says they take. A flag the table does not list ends the extraction at the wrapper, because its next word may be its value."""
    plain, valued = WRAPPER_FLAGS[name]
    i = 0
    while i < len(rest):
        t = rest[i]
        if t == "--":
            i += 1
            break
        if t.startswith("-") and len(t) > 1:
            key = t.split("=", 1)[0]
            if key in plain or (key in valued and "=" in t) or re.fullmatch(r"-[0-9]+", t):
                i += 1
            elif key in valued:
                i += 2
            elif not key.startswith("--") and len(key) > 2 and key[:2] in valued:       # -n10: the value is attached
                i += 1
            else:
                return name
            continue
        if ASSIGN_RX.match(t) or NUMERIC_RX.match(t) or (name == "rtk" and t == "proxy"):
            i += 1
            continue
        break
    inner = _shape(rest[i:], "", depth + 1) if i < len(rest) else ""
    return (name + " " + inner).strip()[:80]


def _shape(argv, comm, depth):
    a = [x for x in argv if x]
    if not a:
        return ""
    b0, plain = _program(a[0], comm)
    if not plain:
        return b0                                           # a rewritten title is no command line: nothing after it is read
    rest = a[1:]
    if b0 in WRAPPERS and depth < 4:
        return _wrapper(b0, rest, depth)
    out = [b0]
    if INTERPRETERS.match(b0):
        fam = "python" if b0.startswith("python") else "node" if b0 in ("node", "nodejs", "bun", "deno") else "sh" if b0 in ("bash", "sh", "dash", "zsh") else b0
        out += _interpreter(fam, rest)
    elif b0 in RUNNERS:
        out += _runner(b0, rest)
    else:
        out += _generic(b0, rest)
    return " ".join(x for x in out if x)[:80]


def shape(argv, comm=""):
    """The command shape of a command line (see the module docstring); an empty string when there is no command line. Every path through it (a rewritten title, a wrapped command, the
    kernel's name standing in for a version-named executable) goes through the same reduction."""
    return _shape(argv, comm, 0)


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
        S = L["shapes"].setdefault(shape(e.get("argv") or [], e["comm"]) or safe_comm(e["comm"]), {"cores": 0.0, "n": 0, "cwds": []})
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
