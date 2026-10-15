#!/usr/bin/python3 -I
"""Lane liveness v2.2 (for the command center's Monitor). Prints one line per meaningful change, never a status flip,
so the Monitor stays quiet on live lanes. v2.2 is v2.1 (2026-10-15) plus the LIMIT-BLOCKED report.

Sources: `claude agents --json --all`, the supported read of session state from outside Claude Code (agent-view.md:794,
client 2.1.300). Client version from /proc/<pid>/exe, since the JSON has no version field (agent-view.md:783-790).
Units: `systemctl --user list-units --all --no-legend` for the given patterns. Usage-limit stops: the tail of the
session's transcript, `<projects>/*/<sessionId>.jsonl` (sessions.md:256), read only for blocked background rows.

Reports:
  NEW / GONE      a session appears or disappears (key: name, kind, pid) or changes client
  NEEDS-INPUT     a non-null waitingFor that persisted 2 consecutive snapshots; CLEARED once when it clears
  UNIT            a matching unit appears, disappears or changes ACTIVE/SUB state
  LIMIT-BLOCKED   a background row still `blocked` --limit-grace seconds (600) after the reset that its last assistant
                  message, a usage-limit stop, names; once per (sessionId, reset), kept across restarts
  LIMIT-UNPARSED  the same stop, but no reset instant can be read from it; once per (sessionId, message)
  LIMIT-STATE     the once-only state file cannot be read or written; once per process
Usage: lane_liveness.py [--selftest] [--interval 60] [--unit-pattern 'cc-mcp-*' ...] [--limit-grace 600]
                        [--tail-bytes 1048576]
See tools/lane-liveness/README.md for each line, the state file and the sources.
"""
import argparse
import contextlib
import datetime as dt
import fcntl
import glob
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import time
import zoneinfo

UTC = dt.timezone.utc


def now_utc() -> dt.datetime:
    return dt.datetime.now(UTC)


def stamp_of(moment: dt.datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def utc() -> str:
    return stamp_of(now_utc())


def client_of(pid) -> str:
    try:
        exe = os.readlink(f"/proc/{int(pid)}/exe")
    except (OSError, TypeError, ValueError):
        return "-"
    if "/claude-retained/" in exe:
        return exe.split("/claude-retained/")[1].split("/")[0] + "(retained)"
    return os.path.basename(exe)


def agent_rows():
    """The `claude agents --json --all` rows; None when the client cannot be read (no change is reported then)."""
    try:
        done = subprocess.run(["claude", "agents", "--json", "--all"], capture_output=True, text=True, timeout=45)
        rows = json.loads(done.stdout)
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return None
    return rows if isinstance(rows, list) else None  # the client prints a JSON array (agent-view.md:779)


def sessions(rows):
    """{(name, kind, pid): (client, waitingFor)}; None when the client cannot be read (no change is reported then)."""
    if rows is None:
        return None
    out = {}
    for r in rows:
        if not isinstance(r, dict) or r.get("pid") is None:
            continue  # a finished background row with no process: not a live lane
        key = (str(r.get("name") or "-"), str(r.get("kind")), str(r.get("pid")))
        out[key] = (client_of(r.get("pid")), r.get("waitingFor") or None)
    return out


def units(patterns):
    try:
        done = subprocess.run(["systemctl", "--user", "list-units", "--all", "--no-legend", "--plain", *patterns],
                              capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    out = {}
    for line in done.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 4:
            out[parts[0]] = f"{parts[2]}/{parts[3]}"  # ACTIVE/SUB
    return out


def label(key):
    return f"{key[0]} kind={key[1]} pid={key[2]}"


# --- LIMIT-BLOCKED -------------------------------------------------------------------------------------------------
# A background session gets no automatic continue after a usage-limit reset (interactive-mode.md:756-758), so it
# stays `blocked` until someone replies. The stop is the client's own assistant message (measured 2026-10-15 at
# 2.1.300: `isApiErrorMessage: true`, model `<synthetic>`), in the forms errors.md lists (lines 44, 714-717, 822-831):
#   You've hit your session limit · resets 6:20am (America/New_York)
#   You've hit your weekly limit · resets Oct 20, 10am (America/New_York)
#   You've hit your monthly spend limit · raise it at <url> · your session limit resets 3:45pm (<zone>)
# The 2.1.300 formatter writes the time alone within 24 h, `Mon D[, YYYY], H[:MM]am` beyond, and the zone in
# parentheses; errors.md:715 also shows a weekday form (`resets Mon 12:00am`).

SESSION_ID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
STOP_PREFIX = "You've hit your "
SEPARATOR = " \N{MIDDLE DOT} "
RESET_SEGMENT = re.compile(r"(?:your .+ )?resets (?P<when>.+)")
MONTHS = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")
WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
WHEN = re.compile(
    r"(?:(?P<month>Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sept?|Oct|Nov|Dec) (?P<day>\d{1,2}),(?: (?P<year>\d{4}),)? "
    r"|(?P<weekday>Mon|Tue|Wed|Thu|Fri|Sat|Sun) )?"
    r"(?P<hour>\d{1,2})(?::(?P<minute>\d{2}))?[ \N{NARROW NO-BREAK SPACE}]?(?P<half>am|pm)"
    r" \((?P<zone>[A-Za-z][A-Za-z0-9_+-]*(?:/[A-Za-z0-9_+-]+)*)\)",
    re.IGNORECASE)
CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f\N{LINE SEPARATOR}\N{PARAGRAPH SEPARATOR}]")
STATE_SCHEMA = "lane-liveness-limits/1"
STATE_RETAIN = dt.timedelta(days=30)


def parse_time(value):
    """An aware UTC datetime from an ISO 8601 string with an offset or `Z`; None otherwise."""
    if not isinstance(value, str):
        return None
    try:
        moment = dt.datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)
    except ValueError:
        return None
    return moment.astimezone(UTC) if moment.tzinfo is not None else None


def reset_instant(when, stamp):
    """The first instant the reset text names at or after the stop's timestamp, in UTC; None when it cannot be read.

    The text states wall-clock minutes in an IANA zone, so the comparison uses the timestamp's minute. A wall time
    that occurs twice (the autumn change) yields its first occurrence at or after it; a wall time the zone skips
    yields the next day on which it occurs.
    """
    match = WHEN.fullmatch(when)
    if match is None or stamp is None:
        return None
    try:
        zone = zoneinfo.ZoneInfo(match["zone"])
    except (zoneinfo.ZoneInfoNotFoundError, ValueError):
        return None
    hour, minute = int(match["hour"]), int(match["minute"] or 0)
    if not 1 <= hour <= 12 or minute > 59:
        return None
    hour = hour % 12 + (12 if match["half"].lower() == "pm" else 0)
    floor = stamp.replace(second=0, microsecond=0)
    today = floor.astimezone(zone).date()
    if match["month"]:
        month = MONTHS.index(match["month"][:3].lower()) + 1
        days = []
        for year in [int(match["year"])] if match["year"] else [today.year, today.year + 1]:
            with contextlib.suppress(ValueError):
                days.append(dt.date(year, month, int(match["day"])))
    else:
        days = [today + dt.timedelta(days=n) for n in range(9)]
        if match["weekday"]:
            days = [day for day in days if day.weekday() == WEEKDAYS.index(match["weekday"][:3].lower())]
    for day in days:
        for fold in (0, 1):
            wall = dt.datetime(day.year, day.month, day.day, hour, minute, tzinfo=zone, fold=fold)
            instant = wall.astimezone(UTC)
            if instant.astimezone(zone).replace(tzinfo=None) != wall.replace(tzinfo=None):
                continue  # a wall time the zone skips
            if instant >= floor:
                return instant
    return None


def stop_text(record):
    """The text of a usage-limit stop the client wrote, else None (a model reply is never one)."""
    message = record.get("message")
    if not isinstance(message, dict):
        return None
    if record.get("isApiErrorMessage") is not True and message.get("model") != "<synthetic>":
        return None
    content = message.get("content")
    if isinstance(content, str):
        texts = [content]
    elif isinstance(content, list):
        texts = [part.get("text") for part in content if isinstance(part, dict) and part.get("type") == "text"]
    else:
        return None
    text = "".join(part for part in texts if isinstance(part, str))
    return text if text.startswith(STOP_PREFIX) else None


def reset_of(text, stamp):
    """The reset instant a stop names (`· resets <when>` or `· your <window> resets <when>`); None when it has none."""
    for segment in text.split(SEPARATOR)[1:]:
        match = RESET_SEGMENT.fullmatch(segment)
        if match:
            return reset_instant(match["when"], stamp)
    return None


def projects_dir():
    """Transcripts live under the config directory's `projects/` (sessions.md:256, env-vars.md:435)."""
    config = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")
    return os.path.join(config, "projects")


def state_path():
    """$XDG_STATE_HOME/native-agent-stack/lane-liveness/limits.json; ~/.local/state when it is unset or relative."""
    base = os.environ.get("XDG_STATE_HOME", "")
    if not os.path.isabs(base):
        base = os.path.join(os.path.expanduser("~"), ".local", "state")
    return os.path.join(base, "native-agent-stack", "lane-liveness", "limits.json")


def transcript(projects, session_id):
    """The newest `<projects>/*/<sessionId>.jsonl`; None for an id that is not a UUID or has no transcript."""
    if not isinstance(session_id, str) or not SESSION_ID.fullmatch(session_id):
        return None
    found = []
    for path in glob.glob(os.path.join(glob.escape(projects), "*", session_id + ".jsonl")):
        with contextlib.suppress(OSError):
            found.append((os.stat(path).st_mtime, path))
    return max(found)[1] if found else None


def last_assistant(path, tail_bytes):
    """The last main-thread assistant record in the file's last `tail_bytes` bytes, or None."""
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as handle:
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode):
            return None
        start = max(0, info.st_size - tail_bytes)
        handle.seek(start)
        data = handle.read(tail_bytes)
    lines = data.split(b"\n")
    if start > 0:
        lines = lines[1:]  # the first line in the window may be cut
    for raw in reversed(lines):
        if not raw.strip():
            continue
        try:
            record = json.loads(raw)
        except ValueError:
            continue
        if isinstance(record, dict) and record.get("type") == "assistant" and not record.get("isSidechain"):
            return record
    return None


def limit_key(row):
    """The row's label key, with control characters replaced so one row stays one line."""
    pid = row.get("pid")
    return tuple(CONTROL.sub("?", value) for value in
                 (str(row.get("name") or "-"), str(row.get("kind")), "-" if pid is None else str(pid)))


class Limits:
    """LIMIT-BLOCKED and LIMIT-UNPARSED decisions and the record that prints each one once."""

    def __init__(self, grace_s, tail_bytes, projects=None, path=None):
        self.grace = dt.timedelta(seconds=grace_s)
        self.tail_bytes = tail_bytes
        self.projects = projects or projects_dir()
        self.path = path or state_path()
        self.printed = {}  # key -> UTC time first printed; mirrors the state file
        self.noted = False

    def check(self, rows, moment):
        stamp = stamp_of(moment)
        for row in rows:
            if not isinstance(row, dict) or row.get("kind") != "background" or row.get("state") != "blocked":
                continue
            session = row.get("sessionId")
            path = transcript(self.projects, session)
            if path is None:
                continue
            try:
                record = last_assistant(path, self.tail_bytes)
            except OSError:
                continue
            text = stop_text(record) if record else None
            if text is None:
                continue
            at = parse_time(record.get("timestamp"))
            reset = reset_of(text, at)
            who = label(limit_key(row))
            if reset is None:
                message = record.get("uuid") or record.get("timestamp")
                self.once(f"unparsed {session} {message}", moment,
                          f"[lanes] {stamp} LIMIT-UNPARSED: {who} session={session} at={stamp_of(at) if at else '-'}")
            elif moment >= reset + self.grace:
                self.once(f"blocked {session} {stamp_of(reset)}", moment,
                          f"[lanes] {stamp} LIMIT-BLOCKED: {who} session={session} reset={stamp_of(reset)} "
                          f"blocked_for={int((moment - reset).total_seconds())}")

    def once(self, key, moment, line):
        """Print `line` unless the key was printed before; the line is flushed before the record is saved."""
        if key in self.printed:
            return
        directory = os.path.dirname(self.path)
        lock = None
        try:
            os.makedirs(directory, mode=0o700, exist_ok=True)
            os.chmod(directory, 0o700)
            lock = os.open(os.path.join(directory, "limits.lock"), os.O_RDWR | os.O_CREAT, 0o600)
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(lock)
            return  # another monitor is saving; the next snapshot decides
        except OSError as error:
            if lock is not None:
                os.close(lock)
            lock = None
            self.note(f"cannot lock {directory} ({type(error).__name__}); this process only")
        try:
            if lock is not None:
                self.printed.update(self.load())
                if key in self.printed:
                    return
            print(line, flush=True)
            self.printed[key] = stamp_of(moment)
            if lock is not None:
                self.save(moment)
        finally:
            if lock is not None:
                os.close(lock)

    def load(self):
        try:
            with open(self.path, encoding="utf-8") as handle:
                data = json.load(handle)
        except FileNotFoundError:
            return {}
        except (OSError, ValueError) as error:
            self.note(f"cannot read {self.path} ({type(error).__name__}); starting from this process's record")
            return {}
        printed = data.get("printed") if isinstance(data, dict) and data.get("schema") == STATE_SCHEMA else None
        if not isinstance(printed, dict):
            self.note(f"cannot read {self.path} (not {STATE_SCHEMA}); starting from this process's record")
            return {}
        return {key: value for key, value in printed.items() if isinstance(key, str) and isinstance(value, str)}

    def save(self, moment):
        keep = {}
        for key, value in self.printed.items():
            printed_at = parse_time(value)
            if printed_at is not None and printed_at >= moment - STATE_RETAIN:
                keep[key] = value  # older records are dropped: a reset 30 days back is not blocking anything
        directory = os.path.dirname(self.path)
        try:
            fd, temporary = tempfile.mkstemp(prefix=".limits.", suffix=".tmp", dir=directory)  # mode 0600
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    json.dump({"schema": STATE_SCHEMA, "printed": keep}, handle, indent=1, sort_keys=True)
                    handle.write("\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, self.path)
            except BaseException:
                with contextlib.suppress(OSError):
                    os.unlink(temporary)
                raise
            folder = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(folder)
            finally:
                os.close(folder)
        except OSError as error:
            self.note(f"cannot write {self.path} ({type(error).__name__}); this process only")

    def note(self, reason):
        if not self.noted:
            self.noted = True
            print(f"[lanes] {utc()} LIMIT-STATE: {reason}", flush=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true", help="print one snapshot and exit")
    ap.add_argument("--interval", type=int, default=60)
    ap.add_argument("--unit-pattern", action="append", default=None)
    ap.add_argument("--limit-grace", type=int, default=600,
                    help="seconds after a usage-limit reset before a still-blocked background row is reported")
    ap.add_argument("--tail-bytes", type=int, default=1 << 20, help="bytes read from the end of a transcript")
    args = ap.parse_args(argv)
    if args.limit_grace < 0 or args.tail_bytes < 1:
        ap.error("--limit-grace must be >= 0 and --tail-bytes >= 1")
    patterns = args.unit_pattern or ["cc-mcp-*", "cc-acctc-*"]
    cur = os.path.basename(os.path.realpath(os.path.expanduser("~/.local/bin/claude")))
    rows = agent_rows()
    snap, unit_state = sessions(rows), units(patterns)
    if args.selftest:
        print(f"[lanes] {utc()} selftest: current client {cur}")
        for key, (client, waiting) in sorted((snap or {}).items()):
            print(f"[lanes]   {label(key)} client={client} waiting={waiting or '-'}")
        for name, state in sorted((unit_state or {}).items()):
            print(f"[lanes]   unit {name} {state}")
        return 0 if snap is not None else 1
    limits = Limits(args.limit_grace, args.tail_bytes)
    snap, unit_state = snap or {}, unit_state or {}
    print(f"[lanes] {utc()} baseline: {len(snap)} sessions, {len(unit_state)} units; current client {cur}", flush=True)
    for key, (client, _) in sorted(snap.items()):
        if client not in (cur, "-"):
            print(f"[lanes] not on {cur}: {label(key)} client={client}", flush=True)
    if rows is not None:
        limits.check(rows, now_utc())
    pending = {}            # key -> waitingFor seen once
    reported = {}           # key -> waitingFor reported
    for key, (_, waiting) in snap.items():
        if waiting:
            pending[key] = waiting
    while True:
        time.sleep(args.interval)
        rows = agent_rows()
        now, now_units = sessions(rows), units(patterns)
        moment = now_utc()
        stamp = stamp_of(moment)
        if now is not None:
            for key in sorted(set(snap) - set(now)):
                print(f"[lanes] {stamp} GONE: {label(key)} client={snap[key][0]}", flush=True)
                pending.pop(key, None); reported.pop(key, None)
            for key in sorted(set(now) - set(snap)):
                print(f"[lanes] {stamp} NEW: {label(key)} client={now[key][0]}", flush=True)
            for key in sorted(set(now) & set(snap)):
                if now[key][0] != snap[key][0]:
                    print(f"[lanes] {stamp} CLIENT: {label(key)} {snap[key][0]} -> {now[key][0]}", flush=True)
            for key, (_, waiting) in now.items():
                if waiting:
                    if key in reported:
                        continue
                    if pending.get(key) == waiting:
                        print(f"[lanes] {stamp} NEEDS-INPUT: {label(key)} waiting={waiting}", flush=True)
                        reported[key] = waiting
                    else:
                        pending[key] = waiting
                else:
                    pending.pop(key, None)
                    if key in reported:
                        print(f"[lanes] {stamp} CLEARED: {label(key)}", flush=True)
                        reported.pop(key)
            snap = now
            limits.check(rows, moment)
        if now_units is not None:
            for name in sorted(set(unit_state) | set(now_units)):
                before, after = unit_state.get(name), now_units.get(name)
                if before != after:
                    print(f"[lanes] {stamp} UNIT: {name} {before or 'absent'} -> {after or 'absent'}", flush=True)
            unit_state = now_units


if __name__ == "__main__":
    sys.exit(main())
