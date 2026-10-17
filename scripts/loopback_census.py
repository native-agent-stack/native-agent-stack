#!/usr/bin/env python3
"""Loopback-only listener census: alert on any TCP or UDP listener that does not bind loopback.

Rule (docs/decisions/2026-10-17-loopback-listener-census.md):
- Dashboards and local services run without a password through each upstream's own no-auth mode.
- Every listener therefore binds loopback only: 127.0.0.0/8, ::1, or ::ffff:127.0.0.0/104.
- A periodic census alerts on any other listener.
- WSL here runs in mirrored networking, where a wildcard or interface bind reaches the LAN.

It runs SS_ARGV, `ss -H -l -t -u -n -p` (iproute2 ss(8)), with a timeout:
- -l listening sockets, -t TCP, -u UDP;
- -n numeric addresses, -p the owning process, -H no header line.

Exit codes. A systemd OnFailure= handler fires on 1 and 2, and the stderr line says which happened:
- 0: every listener binds loopback, or is the one exception;
- 1: a breach, where at least one listener breaks the rule;
- 2: a census error. ss is missing, exits non-zero or times out; its output lists no listener; or a line does not parse.
  A real host always has listeners (WSL's DNS tunnel at least), so an empty enumeration is an error, never a clean pass.

Output:
- stdout: one JSON line {"check", "at", "listeners", "violations"}, or {"check", "at", "error"} on exit 2.
- With --state-dir DIR, two more outputs:
  - The same line replaces DIR/last.json.
  - A set of violations that differs from the previous run's is also kept as DIR/breaches/<UTC stamp>.json, which no
    later run overwrites.
- One stderr line names the breach record, or states the error. The unit's journal, which the alert points to, then
  says where to look.

The one allowed exception is WSL's DNS tunnel at 10.255.255.254:53, the nameserver that resolv.conf names on a mirrored
WSL host. It is allowed for UDP and TCP, by address and port, not by process.

Process names come from ss's users field when ss can see them (the user's own processes). Listeners of other users, or
of other WSL distributions, show as "unknown". argv is never read.

Usage: loopback_census.py [--state-dir DIR] [--ss-output FILE] [--ss-timeout SECONDS]
--ss-output reads a saved `ss -H -ltunp` output instead of running ss; the tests use it.
"""
import argparse
import datetime as dt
import ipaddress
import json
import os
import re
import subprocess
import sys
from pathlib import Path

SS_ARGV = ("ss", "-H", "-l", "-t", "-u", "-n", "-p")
SS_TIMEOUT = 30.0
ALLOWED = {("udp", "10.255.255.254", "53"), ("tcp", "10.255.255.254", "53")}
PROTOCOLS = {"tcp", "udp"}
PROCESS = re.compile(r'\(\("([^"]+)",pid=(\d+)')
# ss -n prints host:port and [v6host]:port. A %scope may follow the host inside or after the brackets, and * is the
# wildcard.
ADDRESS = re.compile(r"^\[?(?P<host>[^\]%]+)(?:%[^\]]*)?\]?(?:%[^:]*)?:(?P<port>[^:\]]+)$")
BREACH, ERROR = 1, 2


class CensusError(Exception):
    """The census could not enumerate the listeners, so it must not report clean."""


def parse_address(address):
    """Return (host, port) of an ss local address, or raise CensusError."""
    match = ADDRESS.match(address)
    if not match:
        raise CensusError(f"unparseable local address {address!r}")
    return match.group("host"), match.group("port")


def is_loopback(host):
    """True for 127.0.0.0/8, ::1 and ::ffff:127.0.0.0/104; False for the wildcard and every other address."""
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    mapped = getattr(ip, "ipv4_mapped", None)
    if mapped is not None:
        return mapped.is_loopback
    return ip.is_loopback


def census(lines):
    """Return (listeners, violations) for ss output lines, or raise CensusError."""
    total, violations = 0, []
    for line in lines:
        fields = line.split()
        if not fields:
            continue
        if len(fields) < 6 or fields[0] not in PROTOCOLS:
            raise CensusError(f"unparseable ss line {line.strip()[:80]!r}")
        proto, address = fields[0], fields[4]
        host, port = parse_address(address)
        total += 1
        if (proto, host, port) in ALLOWED or is_loopback(host):
            continue
        match = PROCESS.search(line)
        process = f"{match.group(1)} pid={match.group(2)}" if match else "unknown"
        entry = {"proto": proto, "address": address, "process": process}
        if entry not in violations:
            violations.append(entry)
    if total == 0:
        raise CensusError("ss listed no listener")
    return total, violations


def run_ss(timeout):
    try:
        result = subprocess.run(SS_ARGV, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        raise CensusError("ss is not installed") from None
    except subprocess.TimeoutExpired:
        raise CensusError(f"ss did not finish within {timeout:g} s") from None
    if result.returncode:
        raise CensusError(f"ss exited {result.returncode}")
    return result.stdout


def keep(state_dir, report):
    """Replace last.json, and keep a new set of violations as breaches/<stamp>.json. Return the breach record's path."""
    state_dir.mkdir(parents=True, exist_ok=True)
    last = state_dir / "last.json"
    try:
        previous = json.loads(last.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        previous = {}
    temporary = state_dir / ".last.json.tmp"
    temporary.write_text(json.dumps(report) + "\n", encoding="utf-8")
    os.replace(temporary, last)
    if not report.get("violations"):
        return None
    breaches = state_dir / "breaches"
    breaches.mkdir(exist_ok=True)
    existing = sorted(breaches.glob("*.json"))
    if existing and previous.get("violations") == report["violations"]:
        return existing[-1]
    stamp = report["at"].replace("-", "").replace(":", "")
    record = breaches / f"{stamp}.json"
    serial = 1
    while record.exists():
        serial += 1
        record = breaches / f"{stamp}-{serial}.json"
    record.write_text(json.dumps(report) + "\n", encoding="utf-8")
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--state-dir", type=Path, help="keep last.json and breaches/ here")
    parser.add_argument("--ss-output", help="read a saved `ss -H -ltunp` output instead of running ss")
    parser.add_argument("--ss-timeout", type=float, default=SS_TIMEOUT, help="seconds before a running ss counts as hung")
    args = parser.parse_args(argv)
    at = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        if args.ss_output:
            with open(args.ss_output, encoding="utf-8") as stream:
                text = stream.read()
        else:
            text = run_ss(args.ss_timeout)
        total, violations = census(text.splitlines())
    except CensusError as error:
        report = {"check": "loopback-census", "at": at, "error": str(error)}
        print(json.dumps(report))
        if args.state_dir:
            keep(args.state_dir, report)
        print(f"loopback census error: {error}", file=sys.stderr)
        return ERROR
    report = {"check": "loopback-census", "at": at, "listeners": total, "violations": violations}
    print(json.dumps(report))
    record = keep(args.state_dir, report) if args.state_dir else None
    if violations:
        where = f"; record {record}" if record else ""
        print(f"loopback census: {len(violations)} non-loopback listener(s){where}", file=sys.stderr)
        return BREACH
    return 0


if __name__ == "__main__":
    sys.exit(main())
