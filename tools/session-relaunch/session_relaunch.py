#!/usr/bin/env python3
"""Relaunch the core Claude Code sessions after an unplanned WSL restart.

Three subcommands, the first two run by systemd --user units (see units/ beside this file and README.md):

  snapshot      Every minute: write the live sessions that `claude agents --json` lists (the client's documented scripting
                interface, "Print active sessions (interactive and background) as a JSON array") to
                rosters/roster-<boot id>.json under the state directory.
  relaunch      Once at boot: read the newest roster written in an earlier boot. When that boot ended without a planned-
                restart marker and the roster was fresh at its end, write one handoff file and open a fresh Windows Terminal
                tab per session that has a launcher profile, the command center first, through the command center's own
                tab opener and launcher. Sessions without a profile are listed in the handoff for the command center.
  plan-restart  Mark this boot's end as planned, so the restart's own relaunch path (the command center's) is the only one.

Native background sessions do not cover this: after a shutdown they restart only when attached or replied to, and the
supervisor's service install is disabled at 2.1.299 (README.md, Sources). The tool starts no model call of its own.
"""

from __future__ import annotations

import argparse
import datetime as dt
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


def write_atomic(path: Path, text: str, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(text)
    os.chmod(tmp, mode)
    os.replace(tmp, path)


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
    config.setdefault("projects_dir", str(Path.home() / ".claude" / "projects"))
    return config


def list_sessions(claude: str) -> list[dict]:
    """The live sessions as `claude agents --json` prints them; an error is an empty list plus a stderr line."""
    try:
        done = subprocess.run([claude, "agents", "--json"], capture_output=True, text=True, timeout=60)
        rows = json.loads(done.stdout) if done.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired, ValueError):
        rows = None
    if not isinstance(rows, list):
        print("session_relaunch: claude agents --json gave no session list", file=sys.stderr)
        return []
    keep = ("name", "kind", "sessionId", "cwd", "pid", "startedAt", "status")
    return [{k: row.get(k) for k in keep} for row in rows if isinstance(row, dict)]


def roster_dir(config: dict) -> Path:
    return Path(config["state_dir"]) / "rosters"


def cmd_snapshot(config: dict, *, boot_id: str, sessions: list[dict], at: dt.datetime) -> Path:
    target = roster_dir(config) / f"roster-{boot_id}.json"
    write_atomic(target, json.dumps({"boot_id": boot_id, "written_at": iso(at), "sessions": sessions}, indent=1) + "\n")
    rosters = sorted(roster_dir(config).glob("roster-*.json"), key=lambda p: p.stat().st_mtime)
    for old in rosters[:-ROSTER_KEEP]:
        old.unlink()
    return target


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


def recent_relaunches(config: dict, at: dt.datetime) -> int:
    count = 0
    for path in Path(config["state_dir"]).glob("relaunched-*.json"):
        try:
            started = parse_iso(json.loads(path.read_text(encoding="utf-8"))["started_at"])
        except (OSError, ValueError, KeyError, TypeError):
            continue
        if (at - started).total_seconds() <= config["relaunch_window_s"]:
            count += 1
    return count


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
        lines.append("- Not relaunched (no launcher profile, or already running); your call:")
        for row in left:
            why = "already running" if row.get("name") in alive else "no launcher profile"
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
    """One tab through the command center's tab opener (it starts the launcher in a new Windows Terminal tab); an
    interop failure early in a boot is retried."""
    attempts, pause_s = config["tab_attempts"], config["tab_retry_pause_s"]
    argv = [config["powershell"], "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File",
            config["tab_opener"], "-Name", profile["launcher_name"], "-Title", profile.get("title") or profile["session_name"],
            "-Handoff", str(handoff)]
    result = {"session_name": profile["session_name"], "launcher_name": profile["launcher_name"], "attempts": []}
    for attempt in range(attempts):
        try:
            done = subprocess.run(argv, capture_output=True, text=True, timeout=120)
            rc, out = done.returncode, (done.stdout.strip().splitlines() or [""])[-1][:200]
        except (OSError, subprocess.TimeoutExpired) as exc:
            rc, out = None, type(exc).__name__
        result["attempts"].append({"at": iso(now_utc()), "rc": rc, "last_line": out})
        if rc == 0:
            break
        if attempt + 1 < attempts:
            time.sleep(pause_s)
    result["rc"] = result["attempts"][-1]["rc"]
    return result


def wait_for(config: dict, name: str, deadline_s: float, poll_s: float = 5.0) -> bool:
    end = time.monotonic() + deadline_s
    while True:
        if any(row.get("name") == name for row in list_sessions(config["claude"])):
            return True
        if time.monotonic() >= end:
            return False
        time.sleep(poll_s)


def plan(config: dict, *, boot_id: str, at: dt.datetime, boots: list[dict], alive_rows: list[dict]) -> dict:
    """What a relaunch would do now; pure apart from reading the state directory."""
    prev = previous_roster(config, boot_id)
    if prev is None:
        return {"action": "none", "reason": "no roster from an earlier boot"}
    prev_boot = norm_boot(str(prev["boot_id"]))
    if marker(config, "planned", prev_boot).exists():
        return {"action": "none", "reason": f"the end of boot {prev_boot} was a planned restart", "prev_boot": prev_boot}
    if marker(config, "relaunched", prev_boot).exists():
        return {"action": "none", "reason": f"boot {prev_boot} was already relaunched", "prev_boot": prev_boot}
    _, prev_end = boot_window(boots, prev_boot)
    this_start, _ = boot_window(boots, boot_id)
    written = parse_iso(prev["written_at"])
    if prev_end is not None and (prev_end - written).total_seconds() > config["max_roster_age_s"]:
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
    launch, left = [], []
    for row in prev.get("sessions") or []:
        name = row.get("name")
        if name in profiles and name not in alive and row.get("kind") == "interactive":
            launch.append((row, profiles[name]))
        else:
            left.append(row)
    launch.sort(key=lambda pair: (pair[0].get("name") != cc, order[pair[0].get("name")]))
    if not launch:
        return {"action": "none", "prev_boot": prev_boot, "reason": "no session of the roster needs a relaunch (no launcher profile, or already running)"}
    return {"action": "relaunch", "prev_boot": prev_boot, "prev": prev, "prev_end": prev_end, "this_start": this_start,
            "launch": launch, "left": left, "alive": alive}


def cmd_relaunch(config: dict, *, boot_id: str, at: dt.datetime, boots: list[dict], dry_run: bool) -> dict:
    decided = plan(config, boot_id=boot_id, at=at, boots=boots, alive_rows=list_sessions(config["claude"]))
    if decided["action"] != "relaunch":
        print(f"session_relaunch: nothing to relaunch: {decided['reason']}")
        return decided
    text = handoff_text(config, at=at, prev=decided["prev"], prev_end=decided["prev_end"],
                        this_start=decided["this_start"], launch=decided["launch"], left=decided["left"],
                        alive=decided["alive"])
    names = [row.get("name") for row, _ in decided["launch"]]
    if dry_run:
        print(f"DRY: would write a handoff of {len(text.encode())} bytes and open tabs in this order: {', '.join(names)}")
        return {**decided, "handoff_text": text}
    handoff = Path(config["handoff_dir"]) / f"AUTO-RESTART-{at.strftime('%Y%m%dT%H%M%SZ')}.md"
    write_atomic(handoff, text, mode=0o444)
    digest = hashlib.sha256(text.encode()).hexdigest()
    receipt = {"prev_boot": decided["prev_boot"], "boot": boot_id, "started_at": iso(at), "handoff": str(handoff),
               "handoff_sha256": digest, "tabs": []}
    receipt_path = marker(config, "relaunched", decided["prev_boot"])
    write_atomic(receipt_path, json.dumps(receipt, indent=1) + "\n")
    cc = config["cc_session_name"]
    for index, (row, profile) in enumerate(decided["launch"]):
        if index:
            time.sleep(config["spacing_s"])
        tab = open_tab(config, profile, handoff)
        if row.get("name") == cc and tab["rc"] == 0:
            tab["cc_listed"] = wait_for(config, cc, config["cc_wait_s"])
        receipt["tabs"].append(tab)
        write_atomic(receipt_path, json.dumps(receipt, indent=1) + "\n")
    print(f"session_relaunch: handoff {handoff} (sha256 {digest}); tabs: "
          + ", ".join(f"{t['session_name']} rc={t['rc']}" for t in receipt["tabs"]))
    return {**decided, "receipt": receipt}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("command", choices=("snapshot", "relaunch", "plan-restart"))
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true", help="relaunch: print the plan and the handoff size, open nothing")
    args = parser.parse_args(argv)
    config = load_config(args.config)
    boot_id, at = current_boot_id(), now_utc()
    if args.command == "snapshot":
        print(cmd_snapshot(config, boot_id=boot_id, sessions=list_sessions(config["claude"]), at=at))
    elif args.command == "plan-restart":
        target = marker(config, "planned", boot_id)
        write_atomic(target, json.dumps({"boot_id": boot_id, "written_at": iso(at)}) + "\n")
        print(target)
    else:
        cmd_relaunch(config, boot_id=boot_id, at=at, boots=read_boots(), dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
