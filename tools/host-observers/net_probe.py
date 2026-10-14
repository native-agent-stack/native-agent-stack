#!/usr/bin/env python3
"""Active network probe for the VM: is the Internet reachable, and does the resolver path the lanes use answer? Writes node-exporter textfile metrics; exits 0 whenever it wrote them (a failed
network check is data, not a failure of the probe).

  net_probe.py OUT.prom [--resolvers 1.1.1.1,9.9.9.9] [--name api.anthropic.com] [--timeout 2] [--dns-port 53] [--tcp-port 443]

Per public resolver: a DNS query for the A record of example.com sent straight to it over UDP, and a TCP connect to its port 443. Once: the system resolver (getaddrinfo, which goes through the
VM's DNS tunnel to Windows, the path the lanes use) for --name. All checks run in parallel, so a dead network costs about --timeout + 1 seconds.
Metrics: net_probe_dns_ok / net_probe_dns_seconds{resolver}, net_probe_tcp_ok / net_probe_tcp_seconds{target}, net_probe_system_dns_ok / _seconds{name}, net_probe_public_ok (1 when at least one of
the public checks succeeded), net_probe_last_run_timestamp_seconds, net_probe_run_seconds. A failed check has no *_seconds line.
The file is replaced by rename, so the exporter never reads a half-written one. Exit status 1 only when the file cannot be written; 2 for a usage error.
"""
import os
import random
import socket
import struct
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor


def build_query(qid, name="example.com"):
    q = struct.pack(">HHHHHH", qid, 0x0100, 1, 0, 0, 0)
    for label in name.split("."):
        q += bytes([len(label)]) + label.encode()
    return q + b"\x00" + struct.pack(">HH", 1, 1)


def check_answer(qid, data):
    """True when data is a successful response to query qid with at least one answer."""
    if len(data) < 12:
        return False
    rid, flags, _qd, an, _ns, _ar = struct.unpack(">HHHHHH", data[:12])
    return rid == qid and bool(flags & 0x8000) and (flags & 0x000F) == 0 and an >= 1


def dns_check(resolver, timeout, port=53):
    qid = random.randint(1, 0xFFFF)
    t0 = time.monotonic()
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(timeout)
    try:
        s.sendto(build_query(qid), (resolver, port))
        data, _ = s.recvfrom(2048)
        good = check_answer(qid, data)
        return good, (time.monotonic() - t0 if good else None)
    except OSError:
        return False, None
    finally:
        s.close()


def tcp_check(host, port, timeout):
    t0 = time.monotonic()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, time.monotonic() - t0
    except OSError:
        return False, None


def system_dns_check(name, timeout, getaddrinfo=socket.getaddrinfo):
    """getaddrinfo has no timeout of its own, so it runs in a thread and is abandoned after the timeout."""
    box = {}

    def go():
        try:
            getaddrinfo(name, 443, type=socket.SOCK_STREAM)
            box["ok"] = True
        except OSError:
            box["ok"] = False

    t0 = time.monotonic()
    th = threading.Thread(target=go, daemon=True)
    th.start()
    th.join(timeout)
    if box.get("ok"):
        return True, time.monotonic() - t0
    return False, None


def probe(resolvers, name, timeout, dns_port=53, tcp_port=443, getaddrinfo=socket.getaddrinfo):
    with ThreadPoolExecutor(max_workers=2 * len(resolvers) + 1) as ex:
        dns = {r: ex.submit(dns_check, r, timeout, dns_port) for r in resolvers}
        tcp = {r: ex.submit(tcp_check, r, tcp_port, timeout) for r in resolvers}
        sysd = ex.submit(system_dns_check, name, timeout + 1, getaddrinfo)
        return ({r: f.result() for r, f in dns.items()}, {f"{r}:{tcp_port}": f.result() for r, f in tcp.items()}, sysd.result())


def render(dns, tcp, sysd, name, now, run_seconds):
    L = ["# HELP net_probe_dns_ok 1 when the resolver answered a direct UDP query for example.com.", "# TYPE net_probe_dns_ok gauge"]
    for r, (ok, _) in dns.items():
        L.append(f'net_probe_dns_ok{{resolver="{r}"}} {int(ok)}')
    L += ["# TYPE net_probe_dns_seconds gauge"] + [f'net_probe_dns_seconds{{resolver="{r}"}} {t:.4f}' for r, (ok, t) in dns.items() if ok]
    L += ["# HELP net_probe_tcp_ok 1 when a TCP connect to the public resolver's port 443 succeeded.", "# TYPE net_probe_tcp_ok gauge"]
    for r, (ok, _) in tcp.items():
        L.append(f'net_probe_tcp_ok{{target="{r}"}} {int(ok)}')
    L += ["# TYPE net_probe_tcp_seconds gauge"] + [f'net_probe_tcp_seconds{{target="{r}"}} {t:.4f}' for r, (ok, t) in tcp.items() if ok]
    L += ["# HELP net_probe_system_dns_ok 1 when the system resolver (the path the lanes use) resolved the name.", "# TYPE net_probe_system_dns_ok gauge", f'net_probe_system_dns_ok{{name="{name}"}} {int(sysd[0])}']
    if sysd[0]:
        L += ["# TYPE net_probe_system_dns_seconds gauge", f'net_probe_system_dns_seconds{{name="{name}"}} {sysd[1]:.4f}']
    public = int(any(ok for ok, _ in list(dns.values()) + list(tcp.values())))
    L += ["# HELP net_probe_public_ok 1 when at least one direct check of a public resolver succeeded.", "# TYPE net_probe_public_ok gauge", f"net_probe_public_ok {public}",
          "# TYPE net_probe_last_run_timestamp_seconds gauge", f"net_probe_last_run_timestamp_seconds {int(now)}", "# TYPE net_probe_run_seconds gauge", f"net_probe_run_seconds {run_seconds:.3f}"]
    return "\n".join(L) + "\n"


def write_atomic(path, text):
    tmp = f"{path}.tmp-{os.getpid()}"
    with open(tmp, "w") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def main(argv):
    if len(argv) < 2 or argv[1].startswith("--"):
        print(__doc__)
        return 2
    opt = lambda name, d=None: argv[argv.index(name) + 1] if name in argv else d
    resolvers = [r for r in opt("--resolvers", "1.1.1.1,9.9.9.9").split(",") if r]
    name, timeout = opt("--name", "api.anthropic.com"), float(opt("--timeout", 2))
    t0 = time.time()
    dns, tcp, sysd = probe(resolvers, name, timeout, int(opt("--dns-port", 53)), int(opt("--tcp-port", 443)))
    try:
        write_atomic(argv[1], render(dns, tcp, sysd, name, time.time(), time.time() - t0))
    except OSError as ex:
        print(f"cannot write {argv[1]}: {ex}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
