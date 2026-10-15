#!/usr/bin/env python3
"""Watch Claude Code's auto-memory indexes and its background memory consolidation (auto-dream).

One run reads, and writes only inside its own state directory:

  limits      The MEMORY.md load caps, read from the installed client binary (default: the realpath of
              ~/.local/bin/claude). Step A finds the loader's user-visible truncation warning ("Only part of it was
              loaded", with "lines (limit: ${X})" and "(limit: ${F(Y)}) ... index entries are too long" in the 1,200 bytes
              before it) and takes the two identifiers X and Y. Step B takes the values from the declaration beside the
              file name literal, `="MEMORY.md",X=<int>,Y=<int>`. The caps count only when both steps bind exactly one
              pair; otherwise they are "unknown". No number is assumed.
  indexes     Every ~/.claude/projects/*/memory/MEMORY.md, and MEMORY.md in the user settings' autoMemoryDirectory, measured
              as the client measures them: the text trimmed as JavaScript's String.prototype.trim does, lines = newlines
              + 1, size = UTF-16 code units (the string's length). UTF-8 bytes are reported too. Status: ok; warn at 80% of
              either cap (where the client's own write-time reminder starts); alert at 90%.
  auto-dream  autoDreamEnabled from ~/.claude/settings.json (that key only); the server flag's `enabled` and `available`
              fields from ~/.claude.json (cachedGrowthBookFeatures.tengu_onyx_plover, nothing else); and each memory
              directory's .consolidate-lock mtime, which the client keeps as the time of the last consolidation. A lock
              newer than the recorded one is a new consolidation: the guard keeps the directory's last snapshot as
              before.tar, tars the directory as it is now as after.tar, and writes a names-and-counts diff.

Output: one JSON report on stdout and in <state dir>/report.json, and one summary line on stderr. Exit 1 when an index is
at alert or a new consolidation was seen (the unit fails and OnFailure= runs the command center's stack-alert); exit 0
otherwise, also when the caps or the flag are unknown (reported, never an alert); exit 2 when the guard's own state cannot be
read or written. Sources and measurements: README.md beside this file and evidence/artifacts/memory-maintenance-20261015/.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import fcntl
import hashlib
import io
import json
import mmap
import os
import re
import stat
import sys
import tarfile
import tempfile
import time
from pathlib import Path

REPORT_SCHEMA = "memory-index-guard-report/1"
STATE_SCHEMA = "memory-index-guard-state/1"
INDEX_NAME = "MEMORY.md"
LOCK_NAME = ".consolidate-lock"
FLAG_NAME = "tengu_onyx_plover"
WARN_FRACTION = 0.8  # the client's write-time reminder starts here: `var FPo=0.8` (2.1.300, byte 225621868)
ALERT_FRACTION = 0.9  # this guard's alert threshold
SNAPSHOT_MAX_BYTES = 64 * 1024 * 1024  # a memory directory larger than this is not tarred; the report says so

# String.prototype.trim() removes the WhiteSpace and LineTerminator code points (ECMA-262, TrimString). These are the 25 it
# removed from a one-character string in Bun 1.4.2 and in Node v24.21.0
# (evidence/artifacts/memory-maintenance-20261015/js-trim-set.json). Python's str.strip() differs: it also removes
# U+001C-U+001F and U+0085, and keeps U+FEFF. So the set is spelled out by code point.
JS_TRIM = "".join(map(chr, (0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x20, 0xA0, 0x1680, *range(0x2000, 0x200B), 0x2028, 0x2029,
                            0x202F, 0x205F, 0x3000, 0xFEFF)))

IDENT = rb"[A-Za-z_$][A-Za-z0-9_$]*"
ANCHOR = b"Only part of it was loaded"
LINE_TEMPLATE = re.compile(rb" lines \(limit: \$\{(" + IDENT + rb")\}\)")
SIZE_TEMPLATE = re.compile(rb"\(limit: \$\{" + IDENT + rb"\((" + IDENT + rb")\)\}\)[^`]{0,40}index entries are too long")
DECLARATION_PREFIX = b'="MEMORY.md",'
DECLARATION = re.compile(rb'="MEMORY\.md",(' + IDENT + rb")=(\d+),(" + IDENT + rb")=(\d+)[,;]")
WINDOW_BEFORE, WINDOW_AFTER = 1200, 400


class GuardFault(Exception):
    """The guard's own state cannot be read or written: exit 2."""


def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def iso(moment: dt.datetime) -> str:
    return moment.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def iso_ns(ns: int) -> str:
    return iso(dt.datetime.fromtimestamp(ns // 10**9, dt.timezone.utc))


def stamp_ns(ns: int) -> str:
    """20261003T040000000Z: the lock mtime to the millisecond, as a directory name."""
    return dt.datetime.fromtimestamp(ns // 10**9, dt.timezone.utc).strftime("%Y%m%dT%H%M%S") + f"{(ns // 10**6) % 1000:03d}Z"


def display(path: Path | str | None, home: Path) -> str | None:
    """A path with the home directory shown as ~, so reports and alerts do not carry the account's home path."""
    if path is None:
        return None
    text, home_text = str(path), str(home)
    if text == home_text:
        return "~"
    return "~" + text[len(home_text):] if text.startswith(home_text + os.sep) else text


def pct(fraction: float) -> float:
    return round(fraction * 100, 2)


def plural(count: int, word: str, many: str | None = None) -> str:
    return f"{count} {word if count == 1 else (many or word + 's')}"


# --------------------------------------------------------------------------- the caps, read from the client binary


def default_binary(home: Path) -> Path | None:
    """The realpath of ~/.local/bin/claude (the native installer's launcher link), or None when it does not resolve."""
    try:
        target = (home / ".local" / "bin" / "claude").resolve(strict=True)
    except (OSError, RuntimeError):
        return None
    return target if target.is_file() else None


def find_all(buf, needle: bytes):
    start = buf.find(needle)
    while start != -1:
        yield start
        start = buf.find(needle, start + 1)


def read_limits(binary: Path | None, home: Path | None = None) -> dict:
    """Step A binds the identifiers through the user-visible warning; step B binds their values beside "MEMORY.md"."""
    home = home or Path.home()
    result = {"status": "unknown", "line_cap": None, "size_cap": None, "identifiers": None,
              "binary": display(binary, home), "version": binary.name if binary else None, "sha256": None}
    if binary is None:
        return {**result, "reason": "no client binary (~/.local/bin/claude does not resolve)"}
    try:
        with binary.open("rb") as handle:
            if os.fstat(handle.fileno()).st_size == 0:
                return {**result, "reason": "the binary is an empty file"}
            with mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ) as buf:
                result["sha256"] = hashlib.sha256(buf).hexdigest()
                pairs = set()
                for offset in find_all(buf, ANCHOR):
                    window = buf[max(0, offset - WINDOW_BEFORE):offset + WINDOW_AFTER]
                    line, size = LINE_TEMPLATE.search(window), SIZE_TEMPLATE.search(window)
                    if line and size:
                        pairs.add((line.group(1).decode("ascii"), size.group(1).decode("ascii")))
                values = set()
                if len(pairs) == 1:
                    ((line_id, size_id),) = pairs
                    for offset in find_all(buf, DECLARATION_PREFIX):
                        match = DECLARATION.match(buf[offset:offset + 256])
                        if match and (match.group(1).decode("ascii"), match.group(3).decode("ascii")) == (line_id, size_id):
                            values.add((int(match.group(2)), int(match.group(4))))
    except OSError as error:
        return {**result, "reason": f"cannot read the binary ({error.strerror or type(error).__name__})"}
    if len(pairs) != 1:
        return {**result, "reason": f"the loader's warning template does not bind one identifier pair (found {len(pairs)})"}
    identifiers = [line_id, size_id]
    if len(values) != 1:
        return {**result, "identifiers": identifiers,
                "reason": f"no single declaration binds {line_id} and {size_id} beside \"MEMORY.md\" (found {len(values)})"}
    ((line_cap, size_cap),) = values
    if line_cap <= 0 or size_cap <= 0:
        return {**result, "identifiers": identifiers, "reason": "a bound cap is not a positive number, so nothing binds"}
    return {**result, "status": "ok", "line_cap": line_cap, "size_cap": size_cap, "identifiers": identifiers}


# --------------------------------------------------------------------------- the indexes


def measure_index(path: Path) -> dict:
    """Lines and size of MEMORY.md as the 2.1.300 loader measures them (trimmed text: newlines + 1, string length)."""
    raw = path.read_bytes()
    text = raw.decode("utf-8", errors="replace")
    trimmed = text.strip(JS_TRIM)
    body = text[1:] if text.startswith(chr(0xFEFF)) else text
    return {"lines": trimmed.count("\n") + 1, "code_units": len(trimmed.encode("utf-16-le")) // 2, "utf8_bytes": len(raw),
            # The client strips YAML frontmatter and block-level HTML comments before it measures; this guard does not,
            # so with either present its numbers are an upper bound.
            "stripped_parts_present": body.startswith(("---\n", "---\r\n")) or "<!--" in text}


def rate(measure: dict, limits: dict) -> dict:
    if limits["status"] != "ok":
        return {**measure, "lines_pct": None, "size_pct": None, "utf8_bytes_pct": None, "status": "unknown"}
    lines, size = measure["lines"] / limits["line_cap"], measure["code_units"] / limits["size_cap"]
    worst = max(lines, size)
    status = "alert" if worst >= ALERT_FRACTION else "warn" if worst >= WARN_FRACTION else "ok"
    return {**measure, "lines_pct": pct(lines), "size_pct": pct(size),
            "utf8_bytes_pct": pct(measure["utf8_bytes"] / limits["size_cap"]), "status": status}


# --------------------------------------------------------------------------- settings and the server flag, one key each


def read_settings(path: Path) -> tuple[object, Path | None]:
    """autoDreamEnabled and autoMemoryDirectory from user settings; nothing else of the file leaves this function."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return "absent", None
    except (OSError, UnicodeError, ValueError):
        return "unreadable", None
    if not isinstance(data, dict):
        return "unreadable", None
    if "autoDreamEnabled" not in data:
        dream = "absent"
    else:
        dream = data["autoDreamEnabled"] if isinstance(data["autoDreamEnabled"], bool) else "non-boolean"
    directory = data.get("autoMemoryDirectory")
    # The documented forms are an absolute path or one that starts with ~/ (memory.md, Storage location).
    if isinstance(directory, str) and (directory.startswith("~/") or os.path.isabs(directory)):
        return dream, Path(os.path.expanduser(directory))
    return dream, None


def flag_field(flag: dict, key: str):
    if key not in flag:
        return "absent"
    return flag[key] if isinstance(flag[key], bool) else "non-boolean"


def read_flag(path: Path, home: Path) -> dict:
    """`enabled` and `available` of cachedGrowthBookFeatures.tengu_onyx_plover; no other key of the file is kept."""
    unknown = {"status": "unknown", "enabled": None, "available": None}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {**unknown, "reason": f"{display(path, home)} does not exist"}
    except (OSError, UnicodeError, ValueError):
        return {**unknown, "reason": f"{display(path, home)} is not readable JSON"}
    features = data.get("cachedGrowthBookFeatures") if isinstance(data, dict) else None
    flag = features.get(FLAG_NAME) if isinstance(features, dict) else None
    if not isinstance(flag, dict):
        return {**unknown, "reason": "the flag is not in the client's feature cache"}
    return {"status": "read", "enabled": flag_field(flag, "enabled"), "available": flag_field(flag, "available")}


def gate(flag: dict, dream) -> tuple[bool | None, bool | None]:
    """The 2.1.300 gate as read from the binary: the setting counts only when the flag has enabled or available true;
    then the setting, when set, overrides the flag's enabled default. (None, None) when the flag is unknown."""
    if flag["status"] != "read":
        return None, None
    if not (flag["enabled"] is True or flag["available"] is True):
        return False, False
    return True, dream if isinstance(dream, bool) else flag["enabled"] is True


# --------------------------------------------------------------------------- memory directories, locks and snapshots


def memory_dirs(claude_dir: Path, extra: Path | None) -> list[tuple[str, Path]]:
    found, seen = [], set()
    try:
        projects = sorted((claude_dir / "projects").iterdir())
    except OSError:
        projects = []
    for project in projects:
        memory = project / "memory"
        if memory.is_dir():
            found.append((project.name, memory))
            seen.add(os.path.realpath(memory))
    if extra is not None and extra.is_dir() and os.path.realpath(extra) not in seen:
        found.append(("autoMemoryDirectory", extra))
    return found


def read_lock(memory: Path) -> dict | None:
    path = memory / LOCK_NAME
    try:
        mtime_ns = path.stat().st_mtime_ns
    except OSError:
        return None
    pid = None
    with contextlib.suppress(OSError):
        first = path.read_text(encoding="utf-8", errors="replace").strip().split("\n", 1)[0].strip()
        pid = int(first) if first.isdigit() and int(first) > 0 else None
    return {"mtime_ns": mtime_ns, "pid": pid}


def pid_running(pid: int | None) -> bool:
    return pid is not None and os.path.exists(f"/proc/{pid}")


def line_count(raw: bytes) -> int:
    return raw.count(b"\n") + (1 if raw and not raw.endswith(b"\n") else 0)


def read_memory(memory: Path) -> tuple[dict[str, tuple[bytes, int]] | None, str | None]:
    """The regular files under a memory directory (symlinks are not followed; the lock is the client's, not memory)."""
    entries = []
    for directory, folders, names in os.walk(memory):
        folders.sort()
        for name in sorted(names):
            path = Path(directory) / name
            relative = path.relative_to(memory).as_posix()
            if relative == LOCK_NAME:
                continue
            info = path.lstat()
            if stat.S_ISREG(info.st_mode):
                entries.append((relative, path, info.st_size, int(info.st_mtime)))
    total = sum(size for _, _, size, _ in entries)
    if total > SNAPSHOT_MAX_BYTES:
        return None, f"over {SNAPSHOT_MAX_BYTES} bytes"
    return {relative: (path.read_bytes(), mtime) for relative, path, _, mtime in entries}, None


def manifest_of(files: dict[str, tuple[bytes, int]]) -> dict[str, dict]:
    return {name: {"lines": line_count(raw), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
            for name, (raw, _) in sorted(files.items())}


def fingerprint(manifest: dict[str, dict]) -> str:
    return hashlib.sha256(json.dumps([[name, row["sha256"]] for name, row in sorted(manifest.items())]).encode()).hexdigest()


def tar_of(files: dict[str, tuple[bytes, int]]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.PAX_FORMAT) as archive:
        for name, (raw, mtime) in sorted(files.items()):
            info = tarfile.TarInfo(name)
            info.size, info.mtime, info.mode = len(raw), mtime, 0o600
            archive.addfile(info, io.BytesIO(raw))
    return buffer.getvalue()


def diff(before: dict[str, dict], after: dict[str, dict]) -> dict:
    """Names and counts only: the content stays in the private tars."""
    return {"added": [{"name": name, "lines": after[name]["lines"], "bytes": after[name]["bytes"]}
                      for name in sorted(set(after) - set(before))],
            "removed": [{"name": name, "lines": before[name]["lines"], "bytes": before[name]["bytes"]}
                        for name in sorted(set(before) - set(after))],
            "changed": [{"name": name, "lines_before": before[name]["lines"], "lines_after": after[name]["lines"],
                         "bytes_before": before[name]["bytes"], "bytes_after": after[name]["bytes"]}
                        for name in sorted(set(before) & set(after)) if before[name]["sha256"] != after[name]["sha256"]],
            "unchanged": sum(1 for name in set(before) & set(after) if before[name]["sha256"] == after[name]["sha256"])}


# --------------------------------------------------------------------------- the state directory


def private_dir(path: Path) -> Path:
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(path, 0o700)  # also narrows a directory that something else made
    return path


def write_atomic(path: Path, data: bytes, mode: int) -> None:
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)  # a 0400 file is replaced, never opened for writing
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(temporary)
        raise


def load_state(state_dir: Path) -> dict:
    path = state_dir / "state.json"
    if not path.exists():
        return {"schema": STATE_SCHEMA, "locks": {}, "snapshots": {}, "dreams": [], "first_dream_seen": None}
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as error:
        raise GuardFault(f"cannot read state.json in the state directory ({type(error).__name__})") from None
    if not (isinstance(state, dict) and state.get("schema") == STATE_SCHEMA
            and all(isinstance(state.get(key), dict) for key in ("locks", "snapshots")) and isinstance(state.get("dreams"), list)):
        raise GuardFault("state.json in the state directory does not have the guard's state schema")
    return state


def keep_before(snapshot: Path, target: Path) -> None:
    """The pre-consolidation snapshot outlives the next rolling snapshot: a hard link to its file (0400), else a copy."""
    with contextlib.suppress(FileNotFoundError):
        target.unlink()
    try:
        os.link(snapshot, target)
    except OSError:
        write_atomic(target, snapshot.read_bytes(), 0o400)


def record_consolidation(state_dir: Path, state: dict, key: str, memory: Path, lock: dict, now: dt.datetime, home: Path) -> dict:
    record = private_dir(state_dir / "dreams" / key / stamp_ns(lock["mtime_ns"]))
    prior = state["snapshots"].get(key)
    if prior and (state_dir / prior["file"]).is_file():
        keep_before(state_dir / prior["file"], record / "before.tar")
    entry = {"dir": key, "lock_mtime_utc": iso_ns(lock["mtime_ns"]),
             "lock_age_s": max(0, (time.time_ns() - lock["mtime_ns"]) // 10**9),
             "holder_pid_running": pid_running(lock["pid"]), "detected_at": iso(now),
             "baseline_taken_at": prior["taken_at"] if prior else None, "record": display(record, home)}
    try:
        files, skipped = read_memory(memory)
    except OSError as error:
        files, skipped = None, f"unreadable ({error.strerror or type(error).__name__})"
    if files is None:
        entry.update({"after": None, "after_skipped": skipped})
    else:
        write_atomic(record / "after.tar", tar_of(files), 0o400)
        entry.update(diff(prior["files"] if prior else {}, manifest_of(files)))
    write_atomic(record / "diff.json", (json.dumps(entry, indent=1, ensure_ascii=True) + "\n").encode(), 0o400)
    state["dreams"].append({"dir": key, "lock_mtime_utc": entry["lock_mtime_utc"], "detected_at": entry["detected_at"],
                            "record": record.relative_to(state_dir).as_posix()})
    if state.get("first_dream_seen") is None:
        state["first_dream_seen"] = {"dir": key, "lock_mtime_utc": entry["lock_mtime_utc"], "detected_at": entry["detected_at"]}
    return entry


def rolling_snapshot(state_dir: Path, state: dict, key: str, memory: Path, now: dt.datetime) -> str:
    """Tar the directory when it changed since the last snapshot: 'written', 'unchanged', 'empty' or a skip reason."""
    try:
        files, skipped = read_memory(memory)
    except OSError as error:
        return f"unreadable ({error.strerror or type(error).__name__})"
    if files is None:
        return skipped
    if not files:
        return "empty"
    manifest = manifest_of(files)
    print_ = fingerprint(manifest)
    prior = state["snapshots"].get(key)
    if prior and prior.get("fingerprint") == print_ and (state_dir / prior["file"]).is_file():
        return "unchanged"
    target = private_dir(state_dir / "snapshots") / f"{key}.tar"
    write_atomic(target, tar_of(files), 0o400)
    state["snapshots"][key] = {"file": target.relative_to(state_dir).as_posix(), "taken_at": iso(now), "fingerprint": print_,
                               "files": manifest}
    return "written"


# --------------------------------------------------------------------------- one run


def run(binary: Path | None, state_dir: Path, claude_dir: Path, claude_json: Path, home: Path) -> tuple[dict, int]:
    now = now_utc()
    state = load_state(state_dir)
    limits = read_limits(binary, home)
    dream, auto_dir = read_settings(claude_dir / "settings.json")
    flag = read_flag(claude_json, home)
    gate_open, effective = gate(flag, dream)
    dirs = memory_dirs(claude_dir, auto_dir)

    indexes = []
    for key, memory in dirs:
        index = memory / INDEX_NAME
        if index.is_file():
            try:
                indexes.append({"project": key, **rate(measure_index(index), limits)})
            except OSError as error:
                indexes.append({"project": key, "status": "unreadable", "reason": error.strerror or type(error).__name__})

    locks, new, moved_back, written, skipped, unchanged = [], [], [], [], [], 0
    for key, memory in dirs:
        lock = read_lock(memory)
        current = lock["mtime_ns"] if lock else 0
        recorded = int(state["locks"].get(key, 0))
        if lock:
            locks.append({"dir": key, "lock_mtime_utc": iso_ns(current), "lock_age_s": max(0, (time.time_ns() - current) // 10**9),
                          "holder_pid_running": pid_running(lock["pid"])})
        try:
            if current > recorded:
                new.append(record_consolidation(state_dir, state, key, memory, lock, now, home))
            else:
                if current < recorded:
                    moved_back.append({"dir": key, "lock_mtime_utc": iso_ns(current) if current else None,
                                       "recorded_utc": iso_ns(recorded)})
                outcome = rolling_snapshot(state_dir, state, key, memory, now)
                if outcome == "written":
                    written.append(key)
                elif outcome == "unchanged":
                    unchanged += 1
                elif outcome != "empty":
                    skipped.append({"dir": key, "reason": outcome})
        except OSError as error:
            raise GuardFault(f"cannot write the state directory ({error.strerror or type(error).__name__})") from None
        state["locks"][key] = current

    state["last_run_at"] = iso(now)
    try:
        write_atomic(state_dir / "state.json", (json.dumps(state, indent=1, ensure_ascii=True) + "\n").encode(), 0o600)
    except OSError as error:
        raise GuardFault(f"cannot write state.json ({error.strerror or type(error).__name__})") from None

    exit_code = 1 if new or any(row["status"] == "alert" for row in indexes) else 0
    report = {
        "schema": REPORT_SCHEMA, "generated_at": iso(now), "exit_code": exit_code, "limits": limits,
        "thresholds": {"warn": WARN_FRACTION, "alert": ALERT_FRACTION}, "indexes": indexes,
        "auto_dream": {"autoDreamEnabled": dream, "auto_memory_directory": display(auto_dir, home), "flag": flag,
                       "gate_open": gate_open, "effective": effective, "memory_dirs": len(dirs), "locks": locks,
                       "first_dream_seen": state.get("first_dream_seen")},
        "new_consolidations": new, "locks_moved_back": moved_back,
        "snapshots": {"written": written, "unchanged": unchanged, "skipped": skipped},
        "state_dir": display(state_dir, home),
    }
    return report, exit_code


def summary(report: dict) -> str:
    limits, dream, indexes = report["limits"], report["auto_dream"], report["indexes"]
    counts = {status: sum(1 for row in indexes if row["status"] == status) for status in ("alert", "warn", "ok", "unknown")}
    statuses = f"{counts['alert']} alert, {counts['warn']} warn, {counts['ok']} ok"
    if counts["unknown"] or len(indexes) != counts["alert"] + counts["warn"] + counts["ok"]:
        statuses += f", {len(indexes) - counts['alert'] - counts['warn'] - counts['ok']} unknown or unreadable"
    if limits["status"] == "ok":
        caps = f"limits {limits['line_cap']} lines / {limits['size_cap']} code units ({limits['version']})"
    else:
        caps = f"limits unknown ({limits['reason']})"
    flag = dream["flag"]
    if flag["status"] != "read":
        auto = f"auto-dream flag unknown ({flag['reason']})"
    else:
        state = "on" if dream["effective"] else ("off" if dream["gate_open"] else "inert")
        shown = {key: json.dumps(value) if isinstance(value, bool) else str(value)
                 for key, value in (("enabled", flag["enabled"]), ("available", flag["available"]),
                                    ("setting", dream["autoDreamEnabled"]))}
        auto = (f"auto-dream {state} (flag enabled={shown['enabled']} available={shown['available']}, "
                f"autoDreamEnabled={shown['setting']})")
    return (f"memory-index-guard: exit {report['exit_code']}; {plural(len(indexes), 'index', 'indexes')}: {statuses}; {caps}; "
            f"{auto}; {plural(len(report['new_consolidations']), 'new consolidation')}; "
            f"{plural(len(dream['locks']), 'lock')} in {plural(dream['memory_dirs'], 'memory dir')}")


def main(argv: list[str] | None = None) -> int:
    home = Path.home()
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--binary", type=Path, help="client binary to read the caps from (default: the realpath of ~/.local/bin/claude)")
    parser.add_argument("--state-dir", type=Path, default=home / ".local" / "state" / "native-agent-stack" / "memory-index-guard")
    parser.add_argument("--claude-dir", type=Path, default=home / ".claude", help="the client's config directory (default: ~/.claude)")
    parser.add_argument("--claude-json", type=Path, default=home / ".claude.json", help="the client's state file (default: ~/.claude.json)")
    args = parser.parse_args(argv)
    binary = args.binary.resolve() if args.binary is not None else default_binary(home)
    shown = display(args.state_dir, home)
    try:
        private_dir(args.state_dir)
        lock_fd = os.open(args.state_dir / "guard.lock", os.O_RDWR | os.O_CREAT, 0o600)
    except OSError as error:
        print(f"memory-index-guard: exit 2; cannot use the state directory {shown} ({error.strerror})", file=sys.stderr)
        return 2
    try:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print(f"memory-index-guard: another run holds {shown}/guard.lock; nothing done", file=sys.stderr)
            return 0
        try:
            report, exit_code = run(binary, args.state_dir, args.claude_dir, args.claude_json, home)
            text = json.dumps(report, indent=1, ensure_ascii=True) + "\n"
            write_atomic(args.state_dir / "report.json", text.encode(), 0o600)
        except GuardFault as fault:
            print(f"memory-index-guard: exit 2; {fault}", file=sys.stderr)
            return 2
        except OSError as error:
            print(f"memory-index-guard: exit 2; cannot write report.json ({error.strerror or type(error).__name__})", file=sys.stderr)
            return 2
        sys.stdout.write(text)
        print(summary(report), file=sys.stderr)
        return exit_code
    finally:
        os.close(lock_fd)


if __name__ == "__main__":
    raise SystemExit(main())
