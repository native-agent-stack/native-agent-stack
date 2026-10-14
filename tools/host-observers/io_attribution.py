#!/usr/bin/env python3
"""Passive block-IO attribution sampler (read-only; it writes only its own output files). Built for the command center's question of 2026-10-14T03:21Z: who causes the IO pressure.

  io_attribution.py --totals [--dev sdd] [--top 8]      (cumulative IO per cgroup since boot, one walk)
  io_attribution.py [--seconds 60] [--interval 1] [--dev sdd] [--out PREFIX] [--top 12] [--group /non-systemd]
                    [--proc-root /proc] [--cg-root /sys/fs/cgroup] [--sessions-dir ~/.claude/sessions] [--devkey MAJ:MIN]

This kernel has no per-process IO accounting (CONFIG_TASK_IO_ACCOUNTING and CONFIG_TASK_DELAY_ACCT are off: no /proc/<pid>/io, no delay accounting), so `iotop`, `pidstat -d` and the
process exporter's IO series are blind. What can be read without privilege, and what this tool reads every --interval seconds:
  the device's /proc/diskstats row (reads, writes, sectors, milliseconds, flush requests and their milliseconds, discards), /proc/vmstat (swap, refaults, major faults), the system IO
  pressure, and every cgroup's io.stat (for the device) and io.pressure; plus every thread in uninterruptible sleep (state D) with its kernel wait symbol (wchan), its cgroup, its lane
  (the `claude` ancestor, named from its registry file; never the key files), working-directory area and sanitized command shape.
The report has five parts:
  1 the device: throughput, IOPS, average IO size, await, queue, busy share, flush requests a second and their latency, discards;
  2 the system pressure: IO some and full as a share of the wall time, swap, refaults, major faults;
  3 the cgroups by their own IO (a cgroup's io.stat includes its children, so each is shown minus its children) with the share of the device and the share of wall time its tasks spent
    stalled on IO; a cgroup under a parent without an io controller has no io.stat of its own and its IO is part of that parent's;
  4 the D-state threads by wait class (journal commit = fsync and metadata sync; metadata read; page or data read; dirty throttle; block queue; other) and by lane, command shape, area;
  5 the wait symbols, raw.
A D-state thread is a victim or the cause: a thread waiting in the journal commit is itself a synchronous writer, and one waiting for a buffer or page is a reader behind the queue.
"""
import importlib.util
import json
import os
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIELDS = ("rbytes", "wbytes", "rios", "wios", "dbytes", "dios")
VM_KEYS = ("pswpin", "pswpout", "workingset_refault_file", "workingset_refault_anon", "pgmajfault", "pgpgin", "pgpgout", "pgsteal_kswapd", "pgsteal_direct")
# wait symbol -> class (first match wins); the symbols are the kernel's own names
WAIT_CLASSES = (
    ("journal commit (fsync, metadata sync)", re.compile(r"jbd2|ext4_sync_file|ext4_fsync|do_fsync|start_this_handle|wait_transaction_locked|jbd2_log_wait|ext4_journal|sync_file_range")),
    ("dirty throttle", re.compile(r"balance_dirty_pages|wb_wait|writeback_inodes|wait_for_completion_io")),
    ("block queue", re.compile(r"blk_mq_get_tag|blk_mq_get_new|rq_qos_wait|blk_queue_enter|wbt_wait|blk_mq_freeze")),
    ("metadata read (buffer)", re.compile(r"__wait_on_buffer|wait_on_buffer|ext4_.*bh|ext4_find_entry|ext4_getblk|bh_submit_read")),
    ("page or data read", re.compile(r"folio_wait_bit|wait_on_page_bit|filemap_|io_schedule|do_swap_page|swap_|read_pages|ext4_mpage_readpages|rwsem_down_read|__lock_page")),
)


def _load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / (name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def arg(name, default=None):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def wait_class(wchan):
    for name, rx in WAIT_CLASSES:
        if rx.search(wchan):
            return name
    return "other"


def read_text(path):
    with open(path) as f:
        return f.read()


def parse_io_stat(text, devkey):
    """The io.stat counters of one device (devkey 'major:minor') or None when the file has no line for it."""
    for ln in text.splitlines():
        parts = ln.split()
        if parts and parts[0] == devkey:
            d = {}
            for kv in parts[1:]:
                k, _, v = kv.partition("=")
                if k in FIELDS and v.isdigit():
                    d[k] = int(v)
            return {k: d.get(k, 0) for k in FIELDS}
    return None


def parse_psi_total(text):
    """{'some': microseconds, 'full': microseconds} from a pressure file."""
    out = {}
    for ln in text.splitlines():
        p = ln.split()
        if p and p[0] in ("some", "full"):
            for kv in p[1:]:
                if kv.startswith("total="):
                    out[p[0]] = int(kv[6:])
    return out


def read_diskstats(proc_root, dev):
    """All fields after the device name, as ints (17 on kernels with flush accounting), or None."""
    for ln in read_text(f"{proc_root}/diskstats").splitlines():
        p = ln.split()
        if len(p) > 3 and p[2] == dev:
            return [int(x) for x in p[3:]]
    return None


def read_vmstat(proc_root):
    out = {}
    for ln in read_text(f"{proc_root}/vmstat").splitlines():
        k, _, v = ln.partition(" ")
        if k in VM_KEYS:
            out[k] = int(v)
    return out


def walk_cgroups(root, devkey):
    """{relative path: {'io': counters, 'psi': totals}} for every cgroup directory that has an io.stat file (its io controller is enabled)."""
    res = {}
    root = str(root).rstrip("/")
    for dirpath, _dirs, files in os.walk(root):
        if "io.stat" not in files:
            continue
        rel = dirpath[len(root):] or "/"
        try:
            io = parse_io_stat(read_text(dirpath + "/io.stat"), devkey)
        except OSError:
            continue
        psi = {}
        if "io.pressure" in files:
            try:
                psi = parse_psi_total(read_text(dirpath + "/io.pressure"))
            except OSError:
                pass
        res[rel] = {"io": io or dict.fromkeys(FIELDS, 0), "psi": psi}
    return res


def parent_of(rel):
    return "/" if rel.count("/") <= 1 else rel.rsplit("/", 1)[0]


def exclusive_delta(a, b):
    """Per cgroup the IO delta between two cgroup snapshots minus the deltas of its children that have an io.stat (a parent's counters include its children's), and the stall time
    delta (not exclusive). A cgroup created inside the window counts from zero; negative remainders are clamped to zero."""
    own, stall = {}, {}
    for rel, y in b.items():
        x = a.get(rel) or {"io": dict.fromkeys(FIELDS, 0), "psi": {}}
        own[rel] = {k: max(y["io"][k] - x["io"][k], 0) for k in FIELDS}
        stall[rel] = {k: max(y["psi"].get(k, 0) - x["psi"].get(k, 0), 0) for k in ("some", "full")}
    excl = {rel: dict(d) for rel, d in own.items()}
    for rel, d in own.items():
        if rel == "/":
            continue
        par = parent_of(rel)
        while par not in excl and par != "/":
            par = parent_of(par)
        if par in excl:
            for k in FIELDS:
                excl[par][k] = max(excl[par][k] - d[k], 0)
    return excl, stall


def snap_procs(proc_root):
    """{pid: {comm, state, ppid, nthr, start}} from /proc/<pid>/stat."""
    out = {}
    for name in os.listdir(proc_root):
        if not name.isdigit():
            continue
        pid = int(name)
        try:
            s = read_text(f"{proc_root}/{pid}/stat")
            r = s.rindex(")")
            f = s[r + 2:].split()
            out[pid] = {"comm": s[s.index("(") + 1:r], "state": f[0], "ppid": int(f[1]), "nthr": int(f[17]), "start": int(f[19])}
        except (OSError, ValueError, IndexError):
            continue
    return out


def proc_cgroup(proc_root, pid):
    try:
        for ln in read_text(f"{proc_root}/{pid}/cgroup").splitlines():
            if ln.startswith("0::"):
                return ln[3:] or "/"
    except OSError:
        pass
    return "?"


def dstate_scan(proc_root, procs):
    """[(pid, tid, comm, wchan)] for the threads in state D. Reads the stat of every thread of every multi-threaded process (about 0.4 s for 15,000 threads)."""
    rows = []
    for pid, e in procs.items():
        tids = [pid]
        if e["nthr"] > 1:
            try:
                tids = [int(t) for t in os.listdir(f"{proc_root}/{pid}/task")]
            except OSError:
                tids = [pid]
        for tid in tids:
            try:
                s = read_text(f"{proc_root}/{pid}/task/{tid}/stat")
                r = s.rindex(")")
                if s[r + 2] != "D":
                    continue
                comm = s[s.index("(") + 1:r]
            except (OSError, ValueError, IndexError):
                continue
            try:
                w = read_text(f"{proc_root}/{pid}/task/{tid}/wchan").strip() or "0"
            except OSError:
                w = "?"
            rows.append((pid, tid, comm, w))
    return rows


def read_detail(proc_root, pid):
    cwd, argv = None, []
    try:
        cwd = os.readlink(f"{proc_root}/{pid}/cwd")
    except OSError:
        pass
    try:
        with open(f"{proc_root}/{pid}/cmdline", "rb") as f:
            argv = [x.decode("utf-8", "replace") for x in f.read().split(b"\0")][:8]
    except OSError:
        pass
    return cwd, argv


class Sampler:
    def __init__(self, proc_root, cg_root, dev, sessions_dir, clock=time.monotonic, devkey=None):
        self.proc_root, self.cg_root, self.dev, self.sessions_dir, self.clock = proc_root, cg_root, dev, sessions_dir, clock
        self.ss, self.rq, self.sm = _load("storm_snapshot"), _load("storm_runq"), _load("storm_snapshot_summary")
        try:
            self.devkey = devkey or read_text(f"/sys/block/{dev}/dev").strip()
        except OSError:
            self.devkey = None
        self.snaps, self.table, self.detail, self.cgmap, self.sessions = [], {}, {}, {}, {}
        self.scans = []                      # one list per sample: (cgroup, lane, area, shape, comm, wchan, class)

    def who(self, pid, start, procs):
        """(cgroup, lane, area, shape) of a process, from caches and one read of its cgroup, directory and command line."""
        key = (pid, start)
        if key not in self.cgmap:
            cg = proc_cgroup(self.proc_root, pid)
            cwd, argv = read_detail(self.proc_root, pid)
            comm = procs.get(pid, {}).get("comm", "?")
            shape = (self.ss.shape(self.rq.clean_argv(argv, comm, self.ss), comm) if argv else comm) or comm
            root = self.ss.lane_of(pid, self.table)
            if root is not None and root not in self.sessions:
                self.sessions[root] = self.rq.session_info(self.sessions_dir, root)
            lane = (self.sessions.get(root, {}).get("name") or f"claude pid {root}") if root is not None else "no claude ancestor"
            self.cgmap[key] = (cg, lane, self.sm.area(cwd), shape)
        return self.cgmap[key]

    def take(self):
        procs = snap_procs(self.proc_root)
        snap = {"t": self.clock(), "wall": time.time(), "dev": read_diskstats(self.proc_root, self.dev), "vm": read_vmstat(self.proc_root),
                "psi": parse_psi_total(read_text(f"{self.proc_root}/pressure/io")), "cg": walk_cgroups(self.cg_root, self.devkey) if self.devkey else {}, "n_procs": len(procs)}
        for pid, e in procs.items():
            self.table[pid] = {"comm": e["comm"], "ppid": e["ppid"], "start": e["start"]}
        rows = []
        for pid, tid, comm, w in dstate_scan(self.proc_root, procs):
            if pid not in procs:
                continue
            cg, lane, ar, shape = self.who(pid, procs[pid]["start"], procs)
            rows.append((cg, lane, ar, shape, comm, w, wait_class(w)))
        self.scans.append(rows)
        self.snaps.append(snap)
        return snap


def pct(x, y):
    return f"{100 * x / y:5.1f}%" if y else "  n/a"


def mib(x):
    return x / 2**20


def clip(s, n):
    return s if len(s) <= n else s[:n - 1] + "~"


def report(sm, top, group):
    """The text report (a list of lines) from the finished sampler."""
    a, b = sm.snaps[0], sm.snaps[-1]
    dt = b["t"] - a["t"]
    out = []
    P = out.append
    P(f"window {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(a['wall']))} to {time.strftime('%H:%M:%SZ', time.gmtime(b['wall']))}: {len(sm.snaps)} samples over {dt:.1f} s; device {sm.dev} ({sm.devkey})")
    dev_bytes = None
    if a["dev"] and b["dev"]:
        d = [y - x for x, y in zip(a["dev"], b["dev"])]
        dev_bytes = (d[2] + d[6]) * 512
        P("")
        P(f"1 device {sm.dev}")
        P(f"  read   {d[0] / dt:7.0f} IOPS {d[2] * 512 / dt / 2**20:7.1f} MiB/s  avg {d[2] * 512 / max(d[0], 1) / 1024:6.1f} KiB  await {d[3] / max(d[0], 1):6.2f} ms  merged {d[1] / dt:.0f}/s")
        P(f"  write  {d[4] / dt:7.0f} IOPS {d[6] * 512 / dt / 2**20:7.1f} MiB/s  avg {d[6] * 512 / max(d[4], 1) / 1024:6.1f} KiB  await {d[7] / max(d[4], 1):6.2f} ms  merged {d[5] / dt:.0f}/s")
        if len(d) >= 17:
            P(f"  flush  {d[15] / dt:7.1f} requests/s  avg {d[16] / max(d[15], 1):6.2f} ms  (flush time {d[16] / (dt * 1000):.2f} s per second)   discard {d[11] / dt:6.1f}/s  avg {d[14] / max(d[11], 1):.2f} ms")
        P(f"  busy {100 * d[9] / (dt * 1000):.0f}% of wall, average queue {d[10] / (dt * 1000):.1f}")
    P("")
    P("2 pressure and memory side effects")
    ps = {k: b["psi"].get(k, 0) - a["psi"].get(k, 0) for k in ("some", "full")}
    P(f"  system IO pressure over the window: some {100 * ps['some'] / (dt * 1e6):.1f}% full {100 * ps['full'] / (dt * 1e6):.1f}% of wall time")
    vm = {k: b["vm"].get(k, 0) - a["vm"].get(k, 0) for k in VM_KEYS}
    P(f"  swap-in {vm['pswpin'] / dt:.0f} pages/s, swap-out {vm['pswpout'] / dt:.0f}/s; file refaults {vm['workingset_refault_file'] / dt:.0f}/s ({vm['workingset_refault_file'] * 4096 / dt / 2**20:.1f} MiB/s); "
      f"anon refaults {vm['workingset_refault_anon'] / dt:.0f}/s; major faults {vm['pgmajfault'] / dt:.0f}/s; kswapd reclaim {vm['pgsteal_kswapd'] * 4096 / dt / 2**20:.0f} MiB/s, direct {vm['pgsteal_direct'] * 4096 / dt / 2**20:.0f} MiB/s")
    excl, stall = exclusive_delta(a["cg"], b["cg"])
    P("")
    P(f"3 cgroups by their own IO on {sm.dev} (exclusive of children; a cgroup without an io controller is part of its parent)")
    P(f"  {'cgroup':<44} {'read MiB':>9} {'write MiB':>10} {'share':>6}  {'IOPS':>7}  {'stalled some/full':>18}")
    for rel, v in sorted(excl.items(), key=lambda kv: -(kv[1]["rbytes"] + kv[1]["wbytes"]))[:top]:
        tot = v["rbytes"] + v["wbytes"]
        P(f"  {clip(rel, 44):<44} {mib(v['rbytes']):>9.0f} {mib(v['wbytes']):>10.0f} {pct(tot, dev_bytes) if dev_bytes else '  n/a':>6}  {(v['rios'] + v['wios']) / dt:>7.0f}  "
          f"{100 * stall[rel]['some'] / (dt * 1e6):>7.1f}% /{100 * stall[rel]['full'] / (dt * 1e6):>6.1f}%")
    if dev_bytes:
        P(f"  all cgroups with an io.stat: {mib(sum(v['rbytes'] + v['wbytes'] for v in excl.values())):.0f} MiB of {mib(dev_bytes):.0f} MiB the device moved")
    n = max(len(sm.scans), 1)
    flat = [r for scan in sm.scans for r in scan]
    P("")
    P(f"4 threads in uninterruptible sleep (D): {len(sm.scans)} scans, per scan mean {len(flat) / n:.1f}, max {max((len(s) for s in sm.scans), default=0)}")
    cls = defaultdict(int)
    for r in flat:
        cls[r[6]] += 1
    P(f"  by wait class (threads per scan): " + "; ".join(f"{k} {v / n:.2f}" for k, v in sorted(cls.items(), key=lambda kv: -kv[1])))
    P(f"  {'cgroup or lane':<30} {'area':<26} {'command shape':<26} {'wait class':<28} {'threads/scan':>12}")
    agg = defaultdict(int)
    for cg, lane, ar, shape, comm, w, c in flat:
        who = lane if cg == (group if group.startswith("/") else "/" + group) else clip(cg.replace("/user.slice/user-1000.slice/user@1000.service/", "user:"), 30)
        agg[(who, ar, shape, c)] += 1
    for (who, ar, shape, c), k in sorted(agg.items(), key=lambda kv: -kv[1])[:top]:
        P(f"  {clip(who, 30):<30} {clip(ar, 26):<26} {clip(shape, 26):<26} {clip(c, 28):<28} {k / n:>12.2f}")
    P("")
    P("  by command shape alone (share of all D-state thread time, which is the share of the IO wait):")
    by_shape, by_who = defaultdict(int), defaultdict(int)
    for cg, lane, ar, shape, comm, w, c in flat:
        by_shape[shape] += 1
        by_who[lane if cg == (group if group.startswith("/") else "/" + group) else clip(cg.replace("/user.slice/user-1000.slice/user@1000.service/", "user:"), 30)] += 1
    total = max(len(flat), 1)
    for shape, k in sorted(by_shape.items(), key=lambda kv: -kv[1])[:top]:
        P(f"    {clip(shape, 34):<34} {100 * k / total:5.1f}%  ({k / n:.2f} threads/scan)")
    P("  by lane or user-level cgroup:")
    for who, k in sorted(by_who.items(), key=lambda kv: -kv[1])[:top]:
        P(f"    {clip(who, 34):<34} {100 * k / total:5.1f}%  ({k / n:.2f} threads/scan)")
    P("")
    P("5 wait symbols")
    sy = defaultdict(int)
    for r in flat:
        sy[(r[5], r[6])] += 1
    for (w, c), k in sorted(sy.items(), key=lambda kv: -kv[1])[:top]:
        P(f"  {clip(w, 40):<40} {clip(c, 30):<30} {k / n:>8.2f} threads/scan")
    return out


def totals_lines(cg, uptime_s, top):
    """Cumulative IO per cgroup since boot (exclusive of children) for one device, from one walk of the cgroup tree; rows are cgroups ranked by bytes, with the shares of the root's totals."""
    excl, _ = exclusive_delta({}, cg)
    root = cg.get("/", {"io": dict.fromkeys(FIELDS, 0)})["io"]
    out = [f"since boot ({uptime_s / 3600:.1f} h): the root cgroup's io.stat read {root['rbytes'] / 1e12:.2f} TB, wrote {root['wbytes'] / 1e12:.2f} TB",
           f"  {'cgroup (exclusive of children)':<44} {'read TB':>8} {'write TB':>9} {'write share':>11} {'writes/s avg':>12}"]
    for rel, v in sorted(excl.items(), key=lambda kv: -(kv[1]["rbytes"] + kv[1]["wbytes"]))[:top]:
        out.append(f"  {clip(rel, 44):<44} {v['rbytes'] / 1e12:>8.2f} {v['wbytes'] / 1e12:>9.2f} {pct(v['wbytes'], root['wbytes']):>11} {v['wios'] / max(uptime_s, 1):>12.0f}")
    return out


def main():
    if "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__)
        return 2
    if "--totals" in sys.argv:
        devkey = arg("--devkey") or read_text(f"/sys/block/{arg('--dev', 'sdd')}/dev").strip()
        up = float(read_text(f"{arg('--proc-root', '/proc')}/uptime").split()[0])
        print("\n".join(totals_lines(walk_cgroups(arg("--cg-root", "/sys/fs/cgroup"), devkey), up, int(arg("--top", 8)))))
        return 0
    seconds, interval = float(arg("--seconds", 60)), float(arg("--interval", 1))
    dev, top, group = arg("--dev", "sdd"), int(arg("--top", 12)), arg("--group", "/non-systemd")
    sm = Sampler(arg("--proc-root", "/proc"), arg("--cg-root", "/sys/fs/cgroup"), dev, arg("--sessions-dir", str(Path.home() / ".claude" / "sessions")), devkey=arg("--devkey"))
    if not sm.devkey:
        print(f"unknown device {dev}: no /sys/block/{dev}/dev")
        return 2
    n = max(int(seconds / interval), 1)
    t0 = time.monotonic()
    try:
        for i in range(n + 1):
            sm.take()
            if i < n:
                time.sleep(max(t0 + (i + 1) * interval - time.monotonic(), 0))
    except (OSError, ValueError) as ex:
        print("sampling failed:", type(ex).__name__, ex)
        return 2
    text = "\n".join(report(sm, top, group))
    print(text)
    out = arg("--out")
    if out:
        Path(out + ".txt").write_text(text + "\n")
        with open(out + ".jsonl", "w") as f:
            for s, scan in zip(sm.snaps, sm.scans):
                f.write(json.dumps({"wall": round(s["wall"], 3), "dev": s["dev"], "psi": s["psi"], "n_procs": s["n_procs"], "n_d": len(scan),
                                    "classes": {c: sum(1 for r in scan if r[6] == c) for c in sorted({r[6] for r in scan})}}) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
