#!/usr/bin/env python3
"""Self-test for net_probe.py against a fake DNS server and a fake TCP listener on loopback, and a pass of planted faults.

  net_probe_selftest.py [--tools DIR] [--mutate]
"""
import argparse
import importlib.util
import os
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULTS = []


def ok(label, cond, detail=""):
    RESULTS.append((label, bool(cond), str(detail)[:400]))


def load(tools):
    spec = importlib.util.spec_from_file_location("np_ut", Path(tools) / "net_probe.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class FakeDns:
    """A UDP server that answers per mode: ok, nxdomain, wrongid, noanswer, silent."""

    def __init__(self, mode):
        self.mode = mode
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", 0))
        self.port = self.sock.getsockname()[1]
        self.sock.settimeout(0.2)
        self.stop = False
        self.seen = []
        threading.Thread(target=self.run, daemon=True).start()

    def run(self):
        while not self.stop:
            try:
                data, addr = self.sock.recvfrom(2048)
            except socket.timeout:
                continue
            except OSError:
                return
            self.seen.append(data)
            qid = struct.unpack(">H", data[:2])[0]
            if self.mode == "silent":
                continue
            if self.mode == "wrongid":
                qid ^= 0x5555
            flags = 0x8183 if self.mode == "nxdomain" else 0x8180
            an = 0 if self.mode in ("nxdomain", "noanswer") else 1
            resp = struct.pack(">HHHHHH", qid, flags, 1, an, 0, 0) + data[12:]
            if an:
                resp += b"\xc0\x0c" + struct.pack(">HHIH", 1, 1, 60, 4) + bytes([93, 184, 216, 34])
            self.sock.sendto(resp, addr)

    def close(self):
        self.stop = True
        self.sock.close()


def free_port():
    """A port number nothing listens on: bound once, then closed with no thread holding it."""
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def listener():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    s.listen(8)
    def accept_loop():
        try:
            for _ in range(64):
                s.accept()[0].close()
        except OSError:
            pass

    threading.Thread(target=accept_loop, daemon=True).start()
    return s, s.getsockname()[1]


def checks(tools):
    m = load(tools)
    for mode, want in (("ok", True), ("nxdomain", False), ("wrongid", False), ("noanswer", False)):
        d = FakeDns(mode)
        got, t = m.dns_check("127.0.0.1", 1.0, d.port)
        ok(f"dns_check against a server that answers '{mode}': {'ok' if want else 'not ok'}", got is want and ((t is not None) == want), (got, t))
        if mode == "ok":
            q = d.seen[0] if d.seen else b""
            ok("the query asks for example.com, type A, class IN, with the recursion bit", q[12:25] == b"\x07example\x03com\x00" and q[25:29] == b"\x00\x01\x00\x01" and struct.unpack(">H", q[2:4])[0] == 0x0100, q[:30])
        d.close()
    d = FakeDns("silent")
    t0 = time.time()
    got, t = m.dns_check("127.0.0.1", 0.5, d.port)
    ok("a silent server times out after the timeout, not later", got is False and t is None and 0.4 < time.time() - t0 < 1.5, (got, time.time() - t0))
    d.close()
    s, port = listener()
    got, t = m.tcp_check("127.0.0.1", port, 1.0)
    ok("tcp_check connects to a listener", got is True and t is not None and t < 1.0, (got, t))
    s.close()
    got, t = m.tcp_check("127.0.0.1", free_port(), 1.0)
    ok("tcp_check to a closed port is not ok", got is False and t is None, (got, t))
    ok("system_dns_check passes a resolvable name and reports a time", m.system_dns_check("x", 1.0, lambda *a, **k: [1])[0] is True)
    def boom(*a, **k):
        raise socket.gaierror(-3, "Temporary failure in name resolution")
    ok("system_dns_check reports a resolver error as not ok", m.system_dns_check("x", 1.0, boom) == (False, None))
    def slow(*a, **k):
        time.sleep(3)
        return [1]
    t0 = time.time()
    got = m.system_dns_check("x", 0.5, slow)
    ok("a resolver that hangs is abandoned at the timeout", got == (False, None) and time.time() - t0 < 1.5, (got, time.time() - t0))

    good, bad = FakeDns("ok"), FakeDns("silent")
    s, port = listener()
    dns, tcp, sysd = m.probe(["127.0.0.1"], "x", 1.0, good.port, port, lambda *a, **k: [1])
    text = m.render(dns, tcp, sysd, "x", 1791958236.4, 0.123)
    ok("a healthy probe renders every ok metric as 1 with its seconds, public_ok 1, the timestamp and the run time",
       'net_probe_dns_ok{resolver="127.0.0.1"} 1' in text and 'net_probe_tcp_ok{target="127.0.0.1:%d"} 1' % port in text and 'net_probe_system_dns_ok{name="x"} 1' in text and "\nnet_probe_public_ok 1\n" in text
       and "net_probe_last_run_timestamp_seconds 1791958236" in text and "net_probe_run_seconds 0.123" in text and "net_probe_dns_seconds{" in text and text.endswith("\n"), text)
    s.close()
    closed = free_port()
    dns, tcp, sysd = m.probe(["127.0.0.1"], "x", 0.5, bad.port, closed, lambda *a, **k: [1])
    text = m.render(dns, tcp, sysd, "x", 1.0, 0.1)
    port = closed
    ok("with the DNS server silent and the TCP port closed all public checks are 0, public_ok is 0, and failed checks have no seconds line", 'net_probe_dns_ok{resolver="127.0.0.1"} 0' in text and 'net_probe_tcp_ok{target="127.0.0.1:%d"} 0' % port in text
       and "\nnet_probe_public_ok 0\n" in text and "net_probe_dns_seconds{" not in text and "net_probe_tcp_seconds{" not in text and 'net_probe_system_dns_ok{name="x"} 1' in text, text)
    s, port = listener()
    dns, tcp, sysd = m.probe(["127.0.0.1"], "x", 0.5, bad.port, port, lambda *a, **k: [1])
    text = m.render(dns, tcp, sysd, "x", 1.0, 0.1)
    ok("one working check is enough for public_ok 1 (DNS silent, TCP up)", "\nnet_probe_public_ok 1\n" in text and 'net_probe_dns_ok{resolver="127.0.0.1"} 0' in text, text)
    s.close()
    good.close()
    bad.close()

    d = Path(tempfile.mkdtemp(prefix="np-selftest-"))
    try:
        dsrv = FakeDns("ok")
        s, port = listener()
        out = d / "p.prom"
        r = subprocess.run([sys.executable, "-I", str(Path(tools) / "net_probe.py"), str(out), "--resolvers", "127.0.0.1", "--name", "localhost", "--timeout", "1", "--dns-port", str(dsrv.port), "--tcp-port", str(port)],
                           capture_output=True, text=True, timeout=30)
        body = out.read_text() if out.exists() else ""
        ok("CLI: exit 0, the file has the metrics, no temp file is left", r.returncode == 0 and "\nnet_probe_public_ok 1\n" in body and sorted(os.listdir(d)) == ["p.prom"], (r.returncode, r.stderr, os.listdir(d)))
        dsrv.close()
        s.close()
        t0 = time.time()
        r = subprocess.run([sys.executable, "-I", str(Path(tools) / "net_probe.py"), str(out), "--resolvers", "127.0.0.1", "--name", "nonexistent.invalid", "--timeout", "1", "--dns-port", str(free_port()), "--tcp-port", str(free_port())],
                           capture_output=True, text=True, timeout=30)
        body = out.read_text()
        ok("CLI with everything down (including the system resolver, for a name that does not exist): still exit 0, the file says public_ok 0 and system_dns_ok 0, within about the timeout", r.returncode == 0 and "\nnet_probe_public_ok 0\n" in body and 'net_probe_system_dns_ok{name="nonexistent.invalid"} 0' in body and time.time() - t0 < 6, (r.returncode, time.time() - t0, body[-200:]))
        r = subprocess.run([sys.executable, "-I", str(Path(tools) / "net_probe.py"), str(d / "no" / "such" / "p.prom"), "--resolvers", "127.0.0.1", "--timeout", "0.5", "--dns-port", "9", "--tcp-port", "9"], capture_output=True, text=True, timeout=30)
        ok("an unwritable output path gives exit 1", r.returncode == 1 and "cannot write" in r.stderr, (r.returncode, r.stderr))
        r = subprocess.run([sys.executable, "-I", str(Path(tools) / "net_probe.py")], capture_output=True, text=True, timeout=30)
        ok("no arguments: usage and exit 2", r.returncode == 2 and "net_probe.py OUT.prom" in r.stdout)
    finally:
        shutil.rmtree(d, ignore_errors=True)


MUTANTS = [("a response with the wrong id is accepted", "return rid == qid and bool(flags & 0x8000)", "return bool(flags & 0x8000)"),
           ("an NXDOMAIN response counts as ok", "(flags & 0x000F) == 0 and an >= 1", "an >= 0"),
           ("a response with no answer counts as ok", "(flags & 0x000F) == 0 and an >= 1", "(flags & 0x000F) == 0"),
           ("a query is not marked as recursion desired", "struct.pack(\">HHHHHH\", qid, 0x0100, 1, 0, 0, 0)", "struct.pack(\">HHHHHH\", qid, 0x0000, 1, 0, 0, 0)"),
           ("the system resolver is not waited for only the timeout", "th.join(timeout)", "th.join()"),
           ("public_ok needs all checks, not one", "public = int(any(ok for ok, _ in list(dns.values()) + list(tcp.values())))", "public = int(all(ok for ok, _ in list(dns.values()) + list(tcp.values())))"),
           ("failed checks report a time", "if ok]", "]"),
           ("a failed probe exits non-zero", "        write_atomic(argv[1], render(dns, tcp, sysd, name, time.time(), time.time() - t0))\n", "        write_atomic(argv[1], render(dns, tcp, sysd, name, time.time(), time.time() - t0))\n        return 0 if sysd[0] else 1\n")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tools", default=str(HERE))
    ap.add_argument("--mutate", action="store_true")
    a = ap.parse_args()
    if a.mutate:
        caught = 0
        for name, old, new in MUTANTS:
            with tempfile.TemporaryDirectory(prefix="np-mut-") as d:
                shutil.copy(HERE / "net_probe.py", d)
                p = Path(d) / "net_probe.py"
                s = p.read_text()
                if s.count(old) < 1:
                    print(f"BROKEN  {name} (text not found)")
                    continue
                p.write_text(s.replace(old, new, 1) if s.count(old) > 1 else s.replace(old, new))
                r = subprocess.run([sys.executable, "-I", str(Path(__file__).resolve()), "--tools", d], capture_output=True, text=True, timeout=300)
                hit = r.returncode != 0
                caught += hit
                print(("caught  " if hit else "MISSED  ") + name)
        print(f"{caught} of {len(MUTANTS)} planted faults caught")
        return 0 if caught == len(MUTANTS) else 1
    checks(a.tools)
    bad = [r for r in RESULTS if not r[1]]
    for label, good, detail in RESULTS:
        print(("ok   " if good else "FAIL ") + label + ((" :: " + detail) if (detail and not good) else ""))
    print(f"{len(RESULTS) - len(bad)} of {len(RESULTS)} checks passed" + (f", {len(bad)} FAILED" if bad else ""))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
