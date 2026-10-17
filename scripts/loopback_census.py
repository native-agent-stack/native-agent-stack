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

Exit codes. A systemd OnFailure= handler fires on 1 and 2, and stderr says which happened:
- 0: every listener binds loopback, or is the one exception;
- 1: a breach, where at least one listener breaks the rule;
- 2: a census error:
  - ss is missing, cannot start, exits non-zero or times out, or the saved listing cannot be read;
  - the listing names no listener, or a line does not parse;
  - or --state-dir cannot be written.
  A real host always has listeners (WSL's DNS tunnel at least), so an empty enumeration is an error, never a clean pass.

Output:
- stdout: one JSON line {"check", "at", "listeners", "violations"}, or {"check", "at", "error"} on exit 2.
  - An error report also carries "violations" when the other lines held a breach, so a parse error never hides one.
- stderr: first the breach count or the error, before any state is written. Then, with --state-dir, the breach record's
  path, or why the state was not kept, followed by the report itself.
- With --state-dir DIR:
  - A run with violations keeps them as DIR/breaches/<UTC stamp>.json, which no later run overwrites.
  - A run whose violations equal those in the record that last.json names reuses that record instead. So the record a
    run names always holds exactly that run's violations.
  - The JSON line then replaces DIR/last.json, with "record" naming the breach record when there is one.
- The unit's journal, which the alert points to, holds the stderr lines.

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
    """The census could not enumerate the listeners, so it must not report clean.

    violations holds the breaches found in the lines that did parse, so the error still reports them.
    """

    def __init__(self, message, violations=()):
        super().__init__(message)
        self.violations = list(violations)


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
    """Return (listeners, violations) for ss output lines, or raise CensusError.

    Every line is read before a line that does not parse raises, so the error carries the other lines' violations.
    """
    total, violations, unparsed = 0, [], []
    for line in lines:
        fields = line.split()
        if not fields:
            continue
        if len(fields) < 6 or fields[0] not in PROTOCOLS:
            unparsed.append(f"unparseable ss line {line.strip()[:80]!r}")
            continue
        proto, address = fields[0], fields[4]
        try:
            host, port = parse_address(address)
        except CensusError as error:
            unparsed.append(str(error))
            continue
        total += 1
        if (proto, host, port) in ALLOWED or is_loopback(host):
            continue
        match = PROCESS.search(line)
        process = f"{match.group(1)} pid={match.group(2)}" if match else "unknown"
        entry = {"proto": proto, "address": address, "process": process}
        if entry not in violations:
            violations.append(entry)
    if unparsed:
        more = f" and {len(unparsed) - 1} more" if len(unparsed) > 1 else ""
        raise CensusError(unparsed[0] + more, violations)
    if total == 0:
        raise CensusError("ss listed no listener")
    return total, violations


def run_ss(timeout):
    try:
        result = subprocess.run(SS_ARGV, capture_output=True, encoding="utf-8", errors="replace", timeout=timeout)
    except FileNotFoundError:
        raise CensusError("ss is not installed") from None
    except subprocess.TimeoutExpired:
        raise CensusError(f"ss did not finish within {timeout:g} s") from None
    except OSError as error:
        raise CensusError(f"ss could not start: {error.strerror}") from None
    if result.returncode:
        raise CensusError(f"ss exited {result.returncode}")
    return result.stdout


def read_listing(path, timeout):
    """Return the listing, from a run of SS_ARGV or the saved file at path. Raise CensusError when it cannot be read."""
    if path is None:
        return run_ss(timeout)
    try:
        with open(path, encoding="utf-8", errors="replace") as stream:
            return stream.read()
    except OSError as error:
        raise CensusError(f"cannot read {path}: {error.strerror}") from None


def reusable(breaches, previous, violations):
    """Return the record that the previous last.json names if it holds exactly these violations, else None."""
    named = previous.get("record") if isinstance(previous, dict) else None
    if not isinstance(named, str) or Path(named).name != named:
        return None
    try:
        kept = json.loads((breaches / named).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return breaches / named if isinstance(kept, dict) and kept.get("violations") == violations else None


def new_record(breaches, report):
    """Write report to a new breaches/<stamp>.json, suffixed -<n> when that name is taken, and return its path."""
    stamp = report["at"].replace("-", "").replace(":", "")
    record = breaches / f"{stamp}.json"
    serial = 1
    while record.exists():
        serial += 1
        record = breaches / f"{stamp}-{serial}.json"
    record.write_text(json.dumps(report) + "\n", encoding="utf-8")
    return record


def keep(state_dir, report):
    """Keep the run in state_dir. Return its breach record's path, or None for a run without violations.

    The record is written before last.json, so last.json never names a missing record.
    """
    state_dir.mkdir(parents=True, exist_ok=True)
    last = state_dir / "last.json"
    try:
        previous = json.loads(last.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        previous = {}
    record = None
    if report.get("violations"):
        breaches = state_dir / "breaches"
        breaches.mkdir(exist_ok=True)
        record = reusable(breaches, previous, report["violations"]) or new_record(breaches, report)
    temporary = state_dir / ".last.json.tmp"
    temporary.write_text(json.dumps(dict(report, record=record.name) if record else report) + "\n", encoding="utf-8")
    os.replace(temporary, last)
    return record


def finish(state_dir, report, code):
    """Keep the run when state_dir is set, name its breach record on stderr, and return code.

    A state that cannot be written returns ERROR. The report then goes to stderr, so its detail still reaches the journal.
    """
    if state_dir is None:
        return code
    try:
        record = keep(state_dir, report)
    except OSError as error:
        print(f"loopback census error: state not kept in {state_dir}: {error.strerror or error}; report "
              f"{json.dumps(report)}", file=sys.stderr)
        return ERROR
    if record:
        print(f"loopback census: breach record {record}", file=sys.stderr)
    return code


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--state-dir", type=Path, help="keep last.json and breaches/ here")
    parser.add_argument("--ss-output", help="read a saved `ss -H -ltunp` output instead of running ss")
    parser.add_argument("--ss-timeout", type=float, default=SS_TIMEOUT, help="seconds before a running ss counts as hung")
    args = parser.parse_args(argv)
    at = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        total, violations = census(read_listing(args.ss_output, args.ss_timeout).splitlines())
    except CensusError as error:
        report = {"check": "loopback-census", "at": at, "error": str(error)}
        if error.violations:
            report["violations"] = error.violations
        print(json.dumps(report))
        found = f"; {len(error.violations)} non-loopback listener(s) in the other lines" if error.violations else ""
        print(f"loopback census error: {error}{found}", file=sys.stderr)
        return finish(args.state_dir, report, ERROR)
    report = {"check": "loopback-census", "at": at, "listeners": total, "violations": violations}
    print(json.dumps(report))
    if violations:
        print(f"loopback census: {len(violations)} non-loopback listener(s)", file=sys.stderr)
    return finish(args.state_dir, report, BREACH if violations else 0)


if __name__ == "__main__":
    sys.exit(main())
