#!/usr/bin/env python3
"""Relaunch the core Claude Code sessions after an unplanned WSL restart.

Three subcommands, the first two run by systemd --user units (see units/ beside this file and README.md):

  snapshot      Every minute: write the live sessions that `claude agents --json` lists (the client's documented scripting
                interface, "Print active sessions (interactive and background) as a JSON array") to
                rosters/roster-<boot id>.json under the state directory. When the client gives no list, the last good
                roster stays as it is and the command exits 1.
  relaunch      Once at boot: read the newest roster written in an earlier boot. When that boot ended without a planned-
                restart marker and the roster was fresh at its end, write one handoff file and open a fresh Windows Terminal
                tab per session that has a launcher profile, the command center first, through the command center's own
                tab opener and launcher. Sessions without a profile are listed in the handoff for the command center. The
                state file relaunch-<boot>.json records each run and each session's outcome; a rerun of an unfinished
                relaunch reuses its handoff and opens only the sessions that are not running.
  plan-restart  Mark this boot's end as planned, so the restart's own relaunch path (the command center's) is the only one.

Native background sessions do not cover this: after a shutdown they restart only when attached or replied to, and the
supervisor's service install is disabled at 2.1.299 (README.md, Sources). The tool starts no model call of its own.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import fcntl
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROSTER_KEEP = 20


def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def iso(t: dt.datetime) -> str:
    return t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(text: str) -> dt.datetime:
    return dt.datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)


def norm_boot(boot_id: str) -> str:
    return boot_id.strip().replace("-", "").lower()


def current_boot_id() -> str:
    return norm_boot(Path("/proc/sys/kernel/random/boot_id").read_text())


def write_atomic(path: Path, text: str, mode: int = 0o600) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(text)
    os.chmod(tmp, mode)
    os.replace(tmp, path)


def private_dir(path: Path) -> Path:
    """A directory this tool owns (the state directory and its rosters): created when missing and kept 0700. Missing
    parents are created 0700 one by one: Path.mkdir(parents=True) gives them the default permissions without taking mode
    into account (python/cpython v3.13.16, cbc944f4, Doc/library/pathlib.rst:1476-1478), and the XDG Base Directory
    specification (0.8) asks for 0700 on a directory it creates. An existing parent keeps its mode."""
    missing, probe = [], path
    while not probe.exists():
        missing.append(probe)
        probe = probe.parent
    for directory in reversed(missing):
        directory.mkdir(mode=0o700, exist_ok=True)
        os.chmod(directory, 0o700)
    os.chmod(path, 0o700)
    return path


def state_dir(config: dict) -> Path:
    return private_dir(Path(config["state_dir"]))


def handoff_dir(config: dict) -> Path:
    """The command center's directory: made 0700 only when this tool creates it; an existing one keeps its mode."""
    path = Path(config["handoff_dir"])
    if not path.is_dir():
        path.mkdir(parents=True, exist_ok=True)
        os.chmod(path, 0o700)
    return path


def load_config(path: Path) -> dict:
    config = json.loads(path.read_text(encoding="utf-8"))
    for key in ("state_dir", "claude", "powershell", "tab_opener", "handoff_dir", "transcript_tail", "cc_session_name"):
        if not config.get(key):
            raise SystemExit(f"config {path}: missing {key}")
    for key in ("state_dir", "claude", "powershell", "handoff_dir", "transcript_tail", "projects_dir"):
        if isinstance(config.get(key), str):
            config[key] = os.path.expanduser(config[key])
    config.setdefault("profiles", [])
    config.setdefault("max_roster_age_s", 300)
    config.setdefault("max_relaunches", 3)
    config.setdefault("relaunch_window_s", 21600)
    config.setdefault("cc_wait_s", 120)
    config.setdefault("spacing_s", 5)
    config.setdefault("tab_attempts", 3)
    config.setdefault("tab_retry_pause_s", 10)
    config.setdefault("tab_timeout_s", 120)
    config.setdefault("settle_s", 60)
    config.setdefault("client_wait_s", 120)
    config.setdefault("poll_s", 5)
    config.setdefault("projects_dir", str(Path.home() / ".claude" / "projects"))
    return config


def list_sessions(claude: str) -> list[dict] | None:
    """The live sessions as `claude agents --json` prints them; None (plus a stderr line) when the client gave no list,
    which is not the same as an empty list."""
    try:
        done = subprocess.run([claude, "agents", "--json"], capture_output=True, text=True, timeout=60)
        rows = json.loads(done.stdout) if done.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired, ValueError):
        rows = None
    if not isinstance(rows, list):
        print("session_relaunch: claude agents --json gave no session list", file=sys.stderr)
        return None
    keep = ("name", "kind", "sessionId", "cwd", "pid", "startedAt", "status")
    return [{k: row.get(k) for k in keep} for row in rows if isinstance(row, dict)]


def wait_client(config: dict) -> list[dict] | None:
    """The live sessions, asking again for up to client_wait_s while the client gives no list."""
    end = time.monotonic() + config["client_wait_s"]
    while True:
        rows = list_sessions(config["claude"])
        if rows is not None or time.monotonic() >= end:
            return rows
        time.sleep(config["poll_s"])


def roster_dir(config: dict) -> Path:
    return Path(config["state_dir"]) / "rosters"


def cmd_snapshot(config: dict, *, boot_id: str, sessions: list[dict], at: dt.datetime) -> Path:
    state_dir(config)
    target = private_dir(roster_dir(config)) / f"roster-{boot_id}.json"
    write_atomic(target, json.dumps({"boot_id": boot_id, "written_at": iso(at), "sessions": sessions}, indent=1) + "\n")
    rosters = sorted(roster_dir(config).glob("roster-*.json"), key=lambda p: p.stat().st_mtime)
    for old in rosters[:-ROSTER_KEEP]:
        old.unlink()
    return target


@contextlib.contextmanager
def roster_lock(config: dict):
    """An exclusive lock on roster.lock in the state directory, held by the timer's snapshot from its carry read to its
    roster write and by a relaunch while it writes the seed roster and saves its state, so a snapshot never writes a
    carry read before that state over the seed. Both holders are short; the relaunch's own run lock (relaunch.lock) is a
    different lock, held for the whole run. fcntl.flock performs flock(2) on the descriptor (python/cpython v3.13.16,
    cbc944f4, Doc/library/fcntl.rst:176-183), and the lock is released when all its descriptors are closed (Linux
    man-pages tag man-pages-6.9.1, man/man2/flock.2:69-72), so os.close in the finally clause releases it."""
    fd = os.open(state_dir(config) / "roster.lock", os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)


def snapshot_live(config: dict, *, boot_id: str, sessions: list[dict], at: dt.datetime) -> Path:
    """The timer's snapshot: the live sessions plus the rows a relaunch of this boot still carries, under roster_lock."""
    with roster_lock(config):
        return cmd_snapshot(config, boot_id=boot_id, sessions=sessions + carried_rows(config, boot_id, sessions), at=at)


def previous_roster(config: dict, boot_id: str) -> dict | None:
    """The newest roster written in another boot than this one (by its own written_at)."""
    best = None
    for path in roster_dir(config).glob("roster-*.json"):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
            written = parse_iso(doc["written_at"])
        except (OSError, ValueError, KeyError, TypeError):
            continue
        if norm_boot(str(doc.get("boot_id", ""))) == boot_id:
            continue
        if best is None or written > best[0]:
            best = (written, doc)
    return best[1] if best else None


def boot_window(boots: list[dict], boot_id: str) -> tuple[dt.datetime | None, dt.datetime | None]:
    """(first entry, last entry) of one boot from `journalctl --list-boots -o json`."""
    for boot in boots:
        if norm_boot(str(boot.get("boot_id", ""))) == boot_id:
            to_t = lambda us: dt.datetime.fromtimestamp(us / 1e6, dt.timezone.utc) if isinstance(us, int) else None
            return to_t(boot.get("first_entry")), to_t(boot.get("last_entry"))
    return None, None


def read_boots() -> list[dict]:
    try:
        done = subprocess.run(["journalctl", "--list-boots", "-o", "json", "--no-pager"], capture_output=True, text=True,
                              timeout=60)
        rows = json.loads(done.stdout)
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return []
    return rows if isinstance(rows, list) else []


def marker(config: dict, kind: str, boot_id: str) -> Path:
    return Path(config["state_dir"]) / f"{kind}-{boot_id}.json"


def relaunch_states(config: dict) -> list[dict]:
    """Every readable relaunch-<boot>.json: one per ended boot, with its runs and each session's outcome."""
    states = []
    for path in Path(config["state_dir"]).glob("relaunch-*.json"):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(doc, dict):
            states.append(doc)
    return states


def recent_relaunches(config: dict, at: dt.datetime) -> int:
    """Relaunch runs started within relaunch_window_s, a rerun of an unfinished relaunch included."""
    count = 0
    for doc in relaunch_states(config):
        for run in doc.get("runs") or []:
            try:
                started = parse_iso(run["started_at"])
            except (ValueError, KeyError, TypeError):
                continue
            if (at - started).total_seconds() <= config["relaunch_window_s"]:
                count += 1
    return count


def carried_rows(config: dict, boot_id: str, live: list[dict]) -> list[dict]:
    """The earlier boot's rows that a relaunch in this boot has not brought back yet (not listed live), while it runs
    or after it ended partial, so a second crash still finds them in this boot's roster and the next boot relaunches
    them."""
    names = {row.get("name") for row in live}
    carried = []
    for doc in relaunch_states(config):
        if doc.get("status") in ("in_progress", "partial") and doc.get("boot") == boot_id:
            carried += [row for row in doc.get("carry") or [] if row.get("name") not in names]
    return carried


def transcript_path(config: dict, session_id: str) -> str:
    hits = sorted(Path(config["projects_dir"]).glob(f"*/{session_id}.jsonl")) if session_id else []
    return str(hits[0]) if hits else "not found"


def handoff_text(config: dict, *, at: dt.datetime, prev: dict, prev_end: dt.datetime | None,
                 this_start: dt.datetime | None, launch: list[tuple[dict, dict]], left: list[dict], alive: set[str]) -> str:
    cc = config["cc_session_name"]
    end = iso(prev_end) if prev_end else "unknown (no journal entry for that boot)"
    start = iso(this_start) if this_start else "unknown"
    lines = [
        f"# Automatic relaunch after an unplanned WSL restart (written {iso(at)} by session_relaunch.py; no session wrote it)",
        "",
        f"## For the command center ({cc})",
        "- There is no outgoing command center: the earlier one died in the restart. Do not wait for one or send it READY;",
        "  take over directly from your own last handoff and tracker.",
        "- The sessions in the table below start after you and send you READY by name.",
    ]
    if left:
        launched = {row.get("name") for row, _ in launch}
        lines.append("- Not relaunched (no launcher profile, or already running); your call:")
        for row in left:
            why = ("already running" if row.get("name") in alive else
                   "a second row of a name relaunched above" if row.get("name") in launched else "no launcher profile")
            lines.append(f"  - {row.get('name')} ({row.get('kind')}, {why}): cwd {row.get('cwd')}; "
                         f"resume with `claude --resume {row.get('sessionId')}`")
    lines += [
        "",
        "## What happened (read by the tool)",
        f"- The previous boot ({prev['boot_id']}) ended at {end}; this boot's journal starts at {start}.",
        f"- The last roster of that boot was written at {prev['written_at']} and lists {len(prev.get('sessions') or [])} "
        f"sessions. {len(launch)} are relaunched now, fresh, each with this file as its handoff.",
        "- No session wrote a handoff for this stop. Every Claude session and every transient systemd-run unit of that boot",
        "  died with it; persistent linger units start again by themselves.",
        "",
        "## How each relaunched session recovers its state",
        "1. Find your old session in the table below and its transcript.",
        "2. Read your last handoff: your old transcript's first prompt names it.",
        f"3. Read the work since that handoff: `python3 -I {config['transcript_tail']} <old transcript> --turns 120 --chars 600`.",
        "4. Read the command center's tracker and its rulings since your last handoff.",
        "5. Re-arm what died: units, watchers, Monitors, Codex lanes, readers. Re-run a reader or builder killed mid-run from",
        "   its packet; never trust a partial verdict file.",
        f"6. Send the command center ({cc}) one line: READY, this file's sha256, what you do first. Then work.",
        "",
        "This file authorizes nothing new: every lane keeps its own rules (trading work reads blueprints/us-equities/AGENTS.md).",
        "",
        "## Sessions relaunched",
        "| name | launcher | old session id | cwd | old transcript |",
        "|---|---|---|---|---|",
    ]
    for row, profile in launch:
        lines.append(f"| {row.get('name')} | {profile['launcher_name']} | {row.get('sessionId')} | {row.get('cwd')} | "
                     f"{transcript_path(config, row.get('sessionId') or '')} |")
    return "\n".join(lines) + "\n"


def open_tab(config: dict, profile: dict, handoff: Path) -> dict:
    """One call of the command center's tab opener (it starts the launcher in a new Windows Terminal tab). Its result is
    opened (rc 0), failed (a nonzero rc, or the opener could not start) or timeout (no answer within tab_timeout_s: a tab
    may or may not have opened)."""
    argv = [config["powershell"], "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File",
            config["tab_opener"], "-Name", profile["launcher_name"], "-Title", profile.get("title") or profile["session_name"],
            "-Handoff", str(handoff)]
    try:
        done = subprocess.run(argv, capture_output=True, text=True, timeout=config["tab_timeout_s"])
        rc, out = done.returncode, (done.stdout.strip().splitlines() or [""])[-1][:200]
        result = "opened" if rc == 0 else "failed"
    except subprocess.TimeoutExpired:
        rc, out, result = None, "TimeoutExpired", "timeout"
    except OSError as exc:
        rc, out, result = None, type(exc).__name__, "failed"
    return {"at": iso(now_utc()), "rc": rc, "result": result, "last_line": out}


def listed(config: dict, name: str) -> bool | None:
    """Whether the session is listed live; None when the client gave no list."""
    rows = list_sessions(config["claude"])
    return None if rows is None else any(row.get("name") == name for row in rows)


def wait_for(config: dict, name: str, deadline_s: float) -> bool:
    end = time.monotonic() + deadline_s
    while True:
        if listed(config, name):
            return True
        if time.monotonic() >= end:
            return False
        time.sleep(config["poll_s"])


TAB_STARTS = ("opened", "timeout", "in_flight")  # call results after which a tab may be open


def unresolved(entry: dict) -> bool:
    """A tab start of this session may have been issued and the session was never seen listed: a call since the last
    reopen (`resolved_through`) opened, timed out or is recorded in flight. Only an explicit `--reopen <name>` opens the
    session again, and a reopen counts only once its own call is recorded. A session seen listed and later found
    absent has its calls resolved too (`resolved_through` moves past them), since its tab start did register."""
    if entry.get("outcome") == "running":
        return False
    calls = (entry.get("attempts") or [])[entry.get("resolved_through", 0):]
    return any(call.get("result") in TAB_STARTS for call in calls)


def unresolved_outcome(entry: dict) -> str:
    """unconfirmed when the last possible tab start was an opened call, else uncertain (timed out or in flight)."""
    starts = [call for call in entry.get("attempts") or [] if call.get("result") in TAB_STARTS]
    return "unconfirmed" if starts and starts[-1]["result"] == "opened" else "uncertain"


def run_lock(config: dict) -> int | None:
    """An exclusive lock on relaunch.lock in the state directory, held for the whole run (the unit's or a direct one);
    None when another run holds it."""
    fd = os.open(state_dir(config) / "relaunch.lock", os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        os.close(fd)
        return None
    return fd


def relaunch_one(config: dict, profile: dict, handoff: Path, entry: dict, save, reopening: bool = False) -> str:
    """Open one session's tab and return its outcome. The live list is read before every call, and a call is opened
    only when that read lists the session as absent: an unreadable list skips the session (skipped, nothing opened).
    Each call is recorded in flight before it is made, and its result is saved with the provisional outcome
    (unconfirmed after rc 0, uncertain after a timeout) before the settle wait. An opened or timed-out call is never
    repeated: the session is waited for (cc_wait_s for the command center, settle_s for the rest) and is running or
    keeps the provisional outcome. Only a definite failure is retried, up to tab_attempts calls. A reopen is spent by
    the first call it makes (`resolved_through`), so a reopen that makes no call leaves the session unresolved."""
    name = profile["session_name"]
    settle_s = config["cc_wait_s"] if name == config["cc_session_name"] else config["settle_s"]
    for attempt in range(config["tab_attempts"]):
        if attempt:
            time.sleep(config["tab_retry_pause_s"])
        live = listed(config, name)
        if live:
            return "running"
        if live is None:
            return "skipped"
        if reopening:
            entry["resolved_through"], reopening = len(entry["attempts"]), False
        entry["attempts"].append({"at": iso(now_utc()), "result": "in_flight"})
        save()
        result = open_tab(config, profile, handoff)
        entry["attempts"][-1] = result
        if result["result"] != "failed":
            entry["outcome"] = "unconfirmed" if result["result"] == "opened" else "uncertain"
        save()
        if result["result"] != "failed":
            if wait_for(config, name, settle_s):
                return "running"
            return "unconfirmed" if result["result"] == "opened" else "uncertain"
    return "failed"


def plan(config: dict, *, boot_id: str, at: dt.datetime, boots: list[dict], alive_rows: list[dict]) -> dict:
    """What a relaunch would do now; pure apart from reading the state directory."""
    prev = previous_roster(config, boot_id)
    if prev is None:
        return {"action": "none", "reason": "no roster from an earlier boot"}
    prev_boot = norm_boot(str(prev["boot_id"]))
    if marker(config, "planned", prev_boot).exists():
        return {"action": "none", "reason": f"the end of boot {prev_boot} was a planned restart", "prev_boot": prev_boot}
    state_path = marker(config, "relaunch", prev_boot)
    try:
        state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else None
        status = None if state is None else state["status"]
    except (OSError, ValueError, KeyError, TypeError):
        status = "unreadable"
    if status == "complete":
        return {"action": "none", "reason": f"boot {prev_boot} was already relaunched", "prev_boot": prev_boot}
    if status not in (None, "in_progress", "partial"):
        return refuse(f"the relaunch state {state_path} is unreadable", prev_boot=prev_boot)
    _, prev_end = boot_window(boots, prev_boot)
    this_start, _ = boot_window(boots, boot_id)
    if prev_end is None:
        return refuse(f"no journal entry for boot {prev_boot} ({len(boots)} boots listed), so the roster's age at that "
                      "boot's end is unknown", prev_boot=prev_boot)
    written = parse_iso(prev["written_at"])
    if (prev_end - written).total_seconds() > config["max_roster_age_s"]:
        return {"action": "none", "prev_boot": prev_boot,
                "reason": f"the roster was written {int((prev_end - written).total_seconds())} s before boot {prev_boot} "
                          f"ended (limit {config['max_roster_age_s']} s), so it does not show who was alive at the end"}
    if recent_relaunches(config, at) >= config["max_relaunches"]:
        return {"action": "none", "prev_boot": prev_boot,
                "reason": f"{config['max_relaunches']} relaunches already in the last {config['relaunch_window_s']} s"}
    profiles = {p["session_name"]: p for p in config["profiles"]}
    alive = {row.get("name") for row in alive_rows}
    cc = config["cc_session_name"]
    order = {p["session_name"]: i for i, p in enumerate(config["profiles"])}
    launch, left, taken = [], [], set()
    for row in prev.get("sessions") or []:
        name = row.get("name")
        if name in profiles and name not in alive and name not in taken and row.get("kind") == "interactive":
            launch.append((row, profiles[name]))
            taken.add(name)  # one turn per name: a second row of the name is left to the command center
        else:
            left.append(row)
    launch.sort(key=lambda pair: (pair[0].get("name") != cc, order[pair[0].get("name")]))
    if not launch and state is None:
        return {"action": "none", "prev_boot": prev_boot, "reason": "no session of the roster needs a relaunch (no launcher profile, or already running)"}
    return {"action": "relaunch", "prev_boot": prev_boot, "prev": prev, "prev_end": prev_end, "this_start": this_start,
            "launch": launch, "left": left, "alive": alive, "state": state}


def refuse(reason: str, **fields) -> dict:
    print(f"session_relaunch: refused: {reason}", file=sys.stderr)
    return {**fields, "action": "none", "reason": reason, "refused": True}


def cmd_relaunch(config: dict, *, boot_id: str, at: dt.datetime, boots: list[dict], dry_run: bool,
                 reopen: set[str] | frozenset[str] = frozenset()) -> dict:
    """One relaunch run under the exclusive run lock: a second run (the unit's or a direct one) is refused, exit 1."""
    lock = run_lock(config)
    if lock is None:
        return refuse(f"another relaunch run holds {state_dir(config) / 'relaunch.lock'}; nothing was written or opened")
    try:
        return locked_relaunch(config, boot_id=boot_id, at=at, boots=boots, dry_run=dry_run, reopen=frozenset(reopen))
    finally:
        os.close(lock)


def record_refusal(config: dict, prev_boot: str, names: list[str], reason: str) -> bool:
    """Append a refused --reopen to the relaunch state of ``prev_boot`` (the caller holds the run lock), keeping its runs,
    sessions and earlier refusals. A boot with no readable relaunch state keeps no record (nothing to add it to); the
    refusal then goes to stderr only. True when a record was written."""
    path = marker(config, "relaunch", prev_boot)
    try:
        state = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    except (OSError, ValueError):
        return False
    if not isinstance(state, dict):
        return False
    state.setdefault("refusals", []).append({"at": iso(now_utc()), "reopen": list(names), "reason": reason})
    write_atomic(path, json.dumps(state, indent=1) + "\n")
    return True


def locked_relaunch(config: dict, *, boot_id: str, at: dt.datetime, boots: list[dict], dry_run: bool,
                    reopen: frozenset[str]) -> dict:
    alive_rows = wait_client(config)
    if alive_rows is None:
        return refuse(f"claude agents --json gave no session list within {config['client_wait_s']} s, so who is running "
                      "is unknown; nothing was written or opened")
    decided = plan(config, boot_id=boot_id, at=at, boots=boots, alive_rows=alive_rows)
    if decided["action"] != "relaunch":
        if reopen and not decided.get("refused"):
            reason = f"--reopen {', '.join(sorted(reopen))}: nothing to relaunch ({decided['reason']})"
            if not dry_run and decided.get("prev_boot"):
                record_refusal(config, decided["prev_boot"], sorted(reopen), reason)
            return refuse(reason, prev_boot=decided.get("prev_boot"))
        print(f"session_relaunch: nothing to relaunch: {decided['reason']}")
        return decided
    state, names = decided["state"], [row.get("name") for row, _ in decided["launch"]]
    known = {entry["session_name"]: entry for entry in (state or {}).get("sessions") or []}
    bad = sorted(name for name in reopen if name not in names or not unresolved(known.get(name, {})))
    if bad:
        reason = (f"--reopen {', '.join(bad)}: not an unresolved session that this relaunch still has to bring back; "
                  "nothing was opened")
        if not dry_run:
            record_refusal(config, decided["prev_boot"], bad, reason)
        return refuse(reason, prev_boot=decided["prev_boot"])
    if state is None:
        text = handoff_text(config, at=at, prev=decided["prev"], prev_end=decided["prev_end"],
                            this_start=decided["this_start"], launch=decided["launch"], left=decided["left"],
                            alive=decided["alive"])
    else:
        try:
            text = Path(state.get("handoff") or "").read_bytes().decode()
        except (OSError, UnicodeDecodeError):
            text = None
        if text is None or hashlib.sha256(text.encode()).hexdigest() != state.get("handoff_sha256"):
            return refuse(f"the sealed handoff {state.get('handoff')} of the unfinished relaunch is missing or changed",
                          prev_boot=decided["prev_boot"])
    if dry_run:
        print(f"DRY: would {'write' if state is None else 'reuse'} a handoff of {len(text.encode())} bytes and open tabs "
              f"in this order: {', '.join(names) or 'none'}")
        return {**decided, "handoff_text": text}
    prev_boot, alive = decided["prev_boot"], decided["alive"]
    if state is None:
        handoff = handoff_dir(config) / f"AUTO-RESTART-{at.strftime('%Y%m%dT%H%M%SZ')}.md"
        write_atomic(handoff, text, mode=0o400)
        state = {"prev_boot": prev_boot, "handoff": str(handoff), "handoff_sha256": hashlib.sha256(text.encode()).hexdigest(),
                 "runs": [], "sessions": []}
    carry = [row for row in decided["prev"].get("sessions") or [] if row.get("name") not in alive]
    earlier = {entry["session_name"]: entry for entry in state.get("sessions") or []}
    sessions, profiles, reopened = [], {}, []
    for row, profile in decided["launch"]:
        entry = earlier.pop(row.get("name"), None) or {"session_name": row.get("name"),
                                                        "launcher_name": profile["launcher_name"], "attempts": []}
        profiles[entry["session_name"]] = profile
        if not unresolved(entry):
            entry["outcome"] = "pending"
        elif entry["session_name"] in reopen:
            entry["outcome"] = "pending"
            reopened.append(entry["session_name"])
        else:
            entry["outcome"] = unresolved_outcome(entry)  # a tab start may be open; only the CC reopens it
        sessions.append(entry)
    for name, entry in earlier.items():
        if name in alive:
            entry["outcome"] = "running"
        sessions.append(entry)
    state.update(status="in_progress", boot=boot_id, carry=carry, sessions=sessions)
    state["runs"].append({"boot": boot_id, "started_at": iso(at), **({"reopened": reopened} if reopened else {})})
    state_path = marker(config, "relaunch", prev_boot)
    save = lambda: write_atomic(state_path, json.dumps(state, indent=1) + "\n")

    def retire(names: set[str]) -> None:
        """A row whose session the run saw running leaves the carry, so it is not carried again after it exits."""
        state["carry"] = [row for row in state["carry"] if row.get("name") not in names]
    # This boot's roster first (the live sessions and the earlier boot's rows not running yet), then the state, both
    # under roster_lock: a boot stop between the two writes still leaves the seed as this boot's newest roster (an
    # earlier timer snapshot of this boot can be empty), the timer carries the rows from the saved state afterwards,
    # and no snapshot interleaves with the two writes.
    with roster_lock(config):
        cmd_snapshot(config, boot_id=boot_id, sessions=alive_rows + carry, at=at)
        save()
    handoff = Path(state["handoff"])
    for index, entry in enumerate(e for e in sessions if e["outcome"] == "pending"):
        if index:
            time.sleep(config["spacing_s"])
        entry["outcome"] = relaunch_one(config, profiles[entry["session_name"]], handoff, entry, save,
                                        reopening=entry["session_name"] in reopened)
        if entry["outcome"] != "running" and unresolved(entry):
            entry["outcome"] = unresolved_outcome(entry)  # e.g. a reopen that was skipped before its call
        retire({entry["session_name"]} if entry["outcome"] == "running" else set())
        save()
    # Completion rests on this final read: a session seen running earlier in the run (it registered) and missing now
    # has exited, so it is absent, and its tab start is resolved (seen listed), so a rerun opens it again without a
    # --reopen. An unreadable final list leaves the run partial; a rerun reads it again.
    final = list_sessions(config["claude"])
    if final is not None:
        live = {row.get("name") for row in final}
        for entry in sessions:
            if entry["session_name"] in live:
                entry["outcome"] = "running"
            elif entry["outcome"] == "running":
                entry["outcome"] = "absent"
                entry["resolved_through"] = len(entry.get("attempts") or [])
        retire({entry["session_name"] for entry in sessions if entry["outcome"] == "running"})
        # A session that registered and then exited is still to be brought back, so its row is carried again.
        absent = {entry["session_name"] for entry in sessions if entry["outcome"] == "absent"}
        state["carry"] += [row for row in carry if row.get("name") in absent and row not in state["carry"]]
    complete = final is not None and all(entry["outcome"] == "running" for entry in sessions)
    state["status"] = "complete" if complete else "partial"
    state["runs"][-1]["ended_at"] = iso(now_utc())
    save()
    print(f"session_relaunch: handoff {handoff} (sha256 {state['handoff_sha256']}); {state['status']}: "
          + ", ".join(f"{entry['session_name']} {entry['outcome']}" for entry in sessions))
    return {**decided, "state": state}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("command", choices=("snapshot", "relaunch", "plan-restart"))
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true", help="relaunch: print the plan and the handoff size, open nothing")
    parser.add_argument("--reopen", action="append", default=[], metavar="NAME",
                        help="relaunch: open this session again although an earlier call may have started its tab "
                             "(unconfirmed, uncertain or in flight); the command center's explicit act, once it has "
                             "checked that no tab of the session is open")
    args = parser.parse_args(argv)
    config = load_config(args.config)
    boot_id, at = current_boot_id(), now_utc()
    if args.command == "snapshot":
        sessions = list_sessions(config["claude"])
        if sessions is None:
            print("session_relaunch: the last good roster stays as it is", file=sys.stderr)
            return 1
        print(snapshot_live(config, boot_id=boot_id, sessions=sessions, at=at))
    elif args.command == "plan-restart":
        target = marker(config, "planned", boot_id)
        state_dir(config)
        write_atomic(target, json.dumps({"boot_id": boot_id, "written_at": iso(at)}) + "\n")
        print(target)
    else:
        result = cmd_relaunch(config, boot_id=boot_id, at=at, boots=read_boots(), dry_run=args.dry_run,
                              reopen=frozenset(args.reopen))
        if result.get("refused") or (not args.dry_run and (result.get("state") or {}).get("status") == "partial"):
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
