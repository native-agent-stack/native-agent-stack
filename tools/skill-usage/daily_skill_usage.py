#!/usr/bin/env python3
"""Run the existing native reports and publish only skill names and counts.

The daily record has two halves, one per client, each its own unit with its own record and timeouts, so a slow Codex scan never leaves the Claude half
unmeasured and a timeout leaves only its own half unmeasured (docs/decisions/2026-10-12-skill-invoke-rate-timer.md):

  --half claude   the native /skill-doctor capture (Claude Code's lifetime uses per skill) and the child-usage.mjs --lanes-sweep Skill calls
  --half codex    the Codex rollout scan of the host report (windowed use counts) and the skill_usage.py --lanes report

Each half publishes `skill-invoke-rate-<half>-latest.json` (--out) and then refreshes the combined `skill-invoke-rate-latest.json` that the Fleet page reads
(--combined-out), merged from its own record and the other half's newest one (--other-record). The refresh reads the other record and publishes the combined one
under a lock, so two halves that finish together (a catch-up after the host was off starts both units at once) leave a combined record built from the newest
record of each. A report file given on the command line projects a combined record from files, without collecting.

The CC installs the rendered user timers after landing. Tests pass a stub runner;
lanes never invoke the real Claude client through this script.

Scheduled collection runs from a clone that is at a commit of origin/main: the
live clone is a detached worktree of origin/main (docs/decisions/2026-10-09-claude-review-worker.md),
so a branch name cannot be the test. A clone on a feature branch, or with
commits of its own, is refused, and so is rendering the units for one.

The service units confine the process (ProtectSystem=, ProtectHome=, ReadWritePaths=, PrivateTmp=, PrivateUsers=) and carry the marker TemporaryFileSystem=/srv:ro. A manager that cannot create the mount namespace
starts a unit without those directives and says nothing, unless the unit asks for something it cannot run without; the marker is that ask, so the manager stops the unit (status 226/NAMESPACE) instead
(systemd/systemd-stable@387a14a7b67b, v255.4: src/core/exec-invoke.c L2849-L2888 and L3212-L3237; docs/decisions/2026-10-12-skill-invoke-rate-timer.md, review round 5). The enforcement is the manager's: this program asks
the file system nothing, and run outside such a unit it is not confined. The marker hides /srv inside the unit, so rendering refuses a clone or an interpreter at or below /srv.
"""
import argparse
import contextlib
from datetime import timedelta
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time

import skill_usage

try:
    import fcntl
except ImportError:  # no flock where there is no systemd timer to race with
    fcntl = None

ROOT = Path(__file__).resolve().parents[2]
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,100}\Z")
KINDS = ("skill_invoke_rate_report", "codex_lane_usage_report", "claude_child_lane_usage")
SCHEMA = "skill-invoke-rate-daily/1"
HALVES = ("claude", "codex")
UNIT_FILES = tuple(f"skill-invoke-rate-{half}.{kind}" for half in HALVES for kind in ("service", "timer"))
HALF_KEYS = {"claude": ("host", "claude"), "codex": ("codex",), "all": ("host", "codex", "claude")}
CLAUDE_ROW_FIELDS = ("claude_uses_lifetime", "wiring")
CODEX_ROW_FIELDS = ("codex_use", "codex_skill_md_reads", "codex_name_mentions")
# Seconds a command of the daily run may take before it is abandoned (its report is then None and only the key it feeds is unmeasured). Measured 2026-10-12 as transient user units, one command at a time, on
# the host (64 CPUs, 1 minute load 12 to 19; docs/decisions/2026-10-12-skill-invoke-rate-timer.md): the /skill-doctor capture 19.9 s (1.5 GB peak; 58 to 62 s at three runnable threads per CPU); the Claude
# lanes sweep 2 min 18 s (1.8 GB peak; 198 MB of JSON on stdout, 513 MB to parse); the host report's Codex scan 1 min 10 s (2.8 GB peak, 3,234 rollout files); the Codex lanes scan 25 min 47 s (1.8 GB peak,
# 29 CPU minutes). The limits: the capture its own limit (skill_usage.DEFAULT_CLAUDE_TIMEOUT, 300 s) plus a minute, the two one-core commands 600 s each (4.3 and 8.5 times their wall; a CPU-bound command takes
# about three times as long at three runnable threads per CPU), and the Codex lanes scan twice its wall, the command center's rule of 2026-10-12 (a scan that is slower than that is the case for an incremental scan).
LOCK_WAIT = 60                # seconds one refresh waits for the other half's refresh: the lock is held for one read and one rename
CAPTURE_MARGIN = 60           # added to the capture's own limit (skill_usage.DEFAULT_CLAUDE_TIMEOUT, or --claude-timeout): start-up and the report
TIMEOUTS = {"claude_sweep": 600, "codex_host": 600, "codex_lanes": 3120}


def count(value):
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def counts(value):
    if not isinstance(value, dict):
        return []
    return [{"name": name, "count": count(number)} for name, number in sorted(value.items())
            if isinstance(name, str) and NAME.fullmatch(name) and count(number) is not None]


def table(value):
    """`value` when it is a JSON object, else an empty one. A native report is JSON that another process wrote: a field holds an array, a string or a number where the projection reads an object (`json.loads` gives
    an array as a list and an object as a dict, python/cpython@cbc944f4bc59 Doc/library/json.rst L385-L387), and calling `.get` on it raises. Every container the projection reads goes through here, so a field of
    the wrong shape reads as absent: the half is then unmeasured, and nothing is published as measured."""
    return value if isinstance(value, dict) else {}


def aggregate_usable(aggregate, field):
    """A lane aggregate the projection can read: an object that holds its counts (`field`) as an object. `counts` of anything else would read as no skills, a measured zero lane."""
    return isinstance(aggregate, dict) and isinstance(aggregate.get(field), dict)


def claude_lanes_usable(report):
    """Whether a Claude lanes report of the right kind has the containers the projection reads: `groups.by_spawn_and_agent_type` an object of objects of lane aggregates that hold `skill_calls` as an object,
    and `main`, when the report has one, such an aggregate. A report of the right kind whose containers are not these is unusable: it is read as not measured, never as a measured empty set of lanes."""
    groups = report.get("groups")
    spawns = groups.get("by_spawn_and_agent_type") if isinstance(groups, dict) else None
    if not isinstance(spawns, dict) or ("main" in report and not aggregate_usable(report["main"], "skill_calls")):
        return False
    return all(isinstance(agents, dict) and all(aggregate_usable(group, "skill_calls") for group in agents.values()) for agents in spawns.values())


def codex_lanes_usable(report):
    """The same for a Codex lanes report: `groups` an object whose `workers`, `negative_controls` and `unclassified`, when present, are lane aggregates that hold `skill_md_reads` as an object, and whose
    `workers_by_role` and `workers_by_kind`, when present, are objects of such aggregates."""
    groups = report.get("groups")
    if not isinstance(groups, dict):
        return False
    if any(name in groups and not aggregate_usable(groups[name], "skill_md_reads") for name in ("workers", "negative_controls", "unclassified")):
        return False
    return all(name not in groups or (isinstance(groups[name], dict) and all(aggregate_usable(group, "skill_md_reads") for group in groups[name].values()))
               for name in ("workers_by_role", "workers_by_kind"))


def unusable_reports(codex, claude):
    """Fixed one-line notes for the lanes reports of the right kind whose containers have the wrong shape (a note names no path and no value)."""
    notes = []
    if isinstance(codex, dict) and codex.get("kind") == KINDS[1] and not codex_lanes_usable(codex):
        notes.append("the Codex lanes report has a container of the wrong shape; its half is read as not measured")
    if isinstance(claude, dict) and claude.get("kind") == KINDS[2] and not claude_lanes_usable(claude):
        notes.append("the Claude lanes report has a container of the wrong shape; its half is read as not measured")
    return notes


def project_reports(host, codex, claude, *, now, window, half="all"):
    """Project native aggregates, preserving client/group and measurement meaning. `half` names the client halves the record is for (HALF_KEYS): `measured` holds only their keys, so a half is not
    unmeasured for want of the other half's report. Every container of a native report is read through `table`, so a report of the wrong shape cannot raise here."""
    host_t, codex_t, claude_t = table(host), table(codex), table(claude)
    codex_ok = codex_t.get("kind") == KINDS[1] and codex_lanes_usable(codex_t)
    claude_ok = claude_t.get("kind") == KINDS[2] and claude_lanes_usable(claude_t)
    use_groups = table(table(host_t.get("codex_use_groups")).get(str(window)))
    codex_state = table(host_t.get("codex"))
    codex_measured = (codex_ok and bool(use_groups)
                      and codex_state.get("measured") is True
                      and (count(codex_state.get("roots_count")) or 0) > 0
                      and (count(codex_state.get("files_scanned")) or 0) > 0)
    host_rows = None
    baseline = json.loads((ROOT / "adoption/skills/claude-routing/trigger-baseline.json").read_text())
    wiring = {row["name"]: row for row in baseline.get("skills", [])}
    if host_t.get("kind") == KINDS[0] and isinstance(host_t.get("skills"), list):
        host_rows = []
        for row in host_t["skills"]:
            if not isinstance(row, dict) or not isinstance(row.get("name"), str) or not NAME.fullmatch(row["name"]):
                continue
            c = table(row.get("claude"))
            x = table(row.get("codex"))
            days = table(table(x.get("counts")).get(str(window)))
            host_rows.append({"name": row["name"], "claude_uses_lifetime": count(c.get("uses")),
                              "wiring": wiring.get(row["name"], {}).get("status"),
                              "codex_use": count(table(x.get("use_counts")).get(str(window))) if codex_measured else None,
                              "codex_skill_md_reads": count(days.get("skill_md_reads")) if codex_measured else None,
                              "codex_name_mentions": count(days.get("name_mentions")) if codex_measured else None})
    lanes = []
    def lane(client, name, aggregate, field, use=None):
        if NAME.fullmatch(name) and isinstance(aggregate, dict):
            rows = counts(aggregate.get(field))
            if client == "codex":
                if not codex_measured or not isinstance(use, dict):
                    use = None      # unknown stays unknown (a count of None), never zero
                raw = {row["name"]: row["count"] for row in rows}
                rows = [{"name": skill, "count": count(use.get(skill, 0)) if isinstance(use, dict) else None,
                         "raw_reads": raw.get(skill, 0)} for skill in sorted(set(raw) | set(use or {}))
                        if isinstance(skill, str) and NAME.fullmatch(skill)]
            lanes.append({"client": client, "lane": name, "skills": rows,
                          "metric": "use" if client == "codex" else "skill_calls"})
    if codex_ok:
        groups = table(codex_t.get("groups"))
        for name in ("workers", "negative_controls", "unclassified"):
            if name in groups:
                lane("codex", name, groups[name], "skill_md_reads", use_groups.get(name))
        for name, group in table(groups.get("workers_by_role")).items():
            lane("codex", "role:" + name, group, "skill_md_reads", table(use_groups.get("workers_by_role")).get(name))
        for name, group in table(groups.get("workers_by_kind")).items():
            lane("codex", "kind:" + name, group, "skill_md_reads", table(use_groups.get("workers_by_kind")).get(name))
    if claude_ok:
        for spawn, agents in table(table(claude_t.get("groups")).get("by_spawn_and_agent_type")).items():
            for name, group in table(agents).items():
                lane("claude", spawn + ":" + name, group, "skill_calls")
        if isinstance(claude_t.get("main"), dict):
            lane("claude", "main", claude_t["main"], "skill_calls")
    measured = {"host": host_rows is not None and table(host_t.get("claude")).get("measured") is True,
                "codex": codex_measured,
                "claude": claude_ok}
    return {"schema": SCHEMA, "half": half, "generated_at": now, "window_days": window,
            "host": host_rows, "lanes": lanes if codex is not None or claude is not None else None,
            "zero_use": {"codex": [row["name"] for row in host_rows or [] if row["codex_use"] == 0],
                         "claude_host_lifetime": [row["name"] for row in host_rows or [] if row["claude_uses_lifetime"] == 0]},
            "codex_bulk_scan_limit": table(host_t.get("codex_use_policy")).get("max_distinct_skill_reads"),
            "measured": {key: measured[key] for key in HALF_KEYS[half]}}


class Refused(ValueError):
    """A refusal to run. The message is fixed text, safe to print: it names no path, no account and no exception text."""


class CloneRefused(Refused):
    """The clone is not at a commit of origin/main. The message is fixed text, safe to print."""


class LayoutRefused(Refused):
    """A path the units need is where their marker hides it. The message is fixed text, safe to print."""


# The directory that the units' TemporaryFileSystem=/srv:ro hides. The marker exists only to make the manager insist on the mount namespace (see the units); a clone or an interpreter below it would be invisible to the
# unit and fail after the namespace was made, every day.
MARKER_DIRECTORY = "/srv"


def hidden_by_marker(path):
    """Whether `path`, or the file it resolves to, is at or below MARKER_DIRECTORY (a path with `..` or a doubled slash is read as the file system reads it)."""
    for candidate in (os.path.normpath(path), os.path.realpath(path)):
        if [part for part in candidate.split("/") if part][:1] == [MARKER_DIRECTORY.strip("/")]:
            return True
    return False


def on_reviewed_main(root=ROOT):
    """Whether the clone's HEAD is origin/main or one of its ancestors: true for the live clone (a detached worktree of origin/main) and for a clone on branch main, false for a feature branch and for any
    commit of the clone's own. A clone without an origin/main cannot be judged and is refused."""
    try:
        done = subprocess.run(["git", "merge-base", "--is-ancestor", "HEAD", "origin/main"], cwd=root, capture_output=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as error:
        raise CloneRefused("git cannot compare the clone with origin/main") from error
    if done.returncode not in (0, 1):
        raise CloneRefused("the clone has no origin/main to compare with")
    return done.returncode == 0


def require_reviewed_main(root=ROOT):
    if not on_reviewed_main(root):
        raise CloneRefused("the clone is not at a commit of origin/main (a feature branch, or commits of its own); use the live clone, a detached worktree of origin/main")


def half_plan(half, roots, *, window, now, node="node", claude_timeout=None):
    """The native commands of one half, as (slot, kind, argv, timeout seconds); the slot is where the report goes in project_reports' (host, codex, claude).
    The Claude half asks the host report for the /skill-doctor capture only (no Codex root: its Codex part is then unmeasured, which that half does not count) and sweeps the Claude transcripts;
    the Codex half asks the host report for the Codex scan only (no Claude source) and runs the lanes report."""
    since, until = (now - timedelta(days=window)).isoformat(), now.isoformat()
    script = str(ROOT / "tools/skill-usage/skill_usage.py")
    if half == "claude":
        capture = claude_timeout if claude_timeout is not None else skill_usage.DEFAULT_CLAUDE_TIMEOUT
        timeout_args = [] if claude_timeout is None else ["--claude-timeout", str(claude_timeout)]
        return [("host", KINDS[0], [sys.executable, script, "--run-skill-doctor", *timeout_args, "--window", str(window), "--now", until, "--json"], capture + CAPTURE_MARGIN),
                ("claude", KINDS[2], [node, str(ROOT / "examples/claude-native/workflows/child-usage.mjs"), "--lanes-sweep",
                                      *[arg for root in roots for arg in ("--root", str(root))], "--since", since, "--until", until], TIMEOUTS["claude_sweep"])]
    if half == "codex":
        codex_args = [arg for root in roots for arg in ("--codex-root", str(root))]
        return [("host", KINDS[0], [sys.executable, script, *codex_args, "--window", str(window), "--now", until, "--json"], TIMEOUTS["codex_host"]),
                ("codex", KINDS[1], [sys.executable, script, "--lanes", *codex_args, "--since", since, "--until", until, "--now", until, "--json"], TIMEOUTS["codex_lanes"])]
    raise ValueError("unknown half")


def half_budget(half, claude_timeout=None):
    """Seconds the commands of a half may take in all: what the unit's TimeoutStartSec must exceed."""
    return sum(timeout for _, _, _, timeout in half_plan(half, [Path("x")], window=7, now=skill_usage.now_utc(), claude_timeout=claude_timeout))


def collect_half(half, roots, *, window, now, node="node", runner=subprocess.run, claude_timeout=None):
    """(host, codex, claude) native reports of one half; the other half's slots stay None, and a command that fails, times out or answers with another kind leaves its own slot None."""
    reports = {"host": None, "codex": None, "claude": None}
    for slot, kind, command, timeout in half_plan(half, roots, window=window, now=now, node=node, claude_timeout=claude_timeout):
        try:
            result = runner(command, cwd=ROOT, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout)
            report = json.loads(result.stdout) if result.returncode == 0 else None
            reports[slot] = report if isinstance(report, dict) and report.get("kind") == kind else None
        except (OSError, subprocess.TimeoutExpired, ValueError):
            pass  # Native errors and transcript text never become page content.
    return reports["host"], reports["codex"], reports["claude"]


def half_record(value, half):
    """`value` as the record of `half`, or None. A record is taken only when every field the merge reads has the type it is written with (a record that parses as JSON but has another shape is an absent half,
    not an error): `measured` a mapping of booleans for the half's keys, `host` and `lanes` null or a list, `generated_at` null or an ISO timestamp, `window_days` and `codex_bulk_scan_limit` null or a count."""
    if not (isinstance(value, dict) and value.get("schema") == SCHEMA and value.get("half") == half):
        return None
    measured = value.get("measured")
    if not isinstance(measured, dict) or not all(isinstance(measured.get(key), bool) for key in HALF_KEYS[half]):
        return None
    if any(value.get(key) is not None and not isinstance(value[key], list) for key in ("host", "lanes")):
        return None
    if any(value.get(key) is not None and count(value[key]) is None for key in ("window_days", "codex_bulk_scan_limit")):
        return None
    stamp = value.get("generated_at")
    if stamp is not None:
        try:
            skill_usage.parse_iso(stamp)
        except (AttributeError, TypeError, ValueError):
            return None
    return value


def row_field(row, field):
    """One field of a skill row of a half's record as the combined record carries it: a count, or for `wiring` a short name; anything else is unknown."""
    value = row.get(field)
    if field == "wiring":
        return value if isinstance(value, str) and NAME.fullmatch(value) else None
    return count(value)


def merge_halves(claude, codex):
    """The record the Fleet page reads (schema skill-invoke-rate-daily/1, no `half`) from the newest record of each half. A half that is absent, or is not a record of its half, contributes nothing and is not
    measured. The Claude half owns the Claude fields of a skill and its wiring, the Codex half the Codex ones; `generated_at` is the older of the two, so the page never shows a stale half as fresh."""
    claude, codex = half_record(claude, "claude"), half_record(codex, "codex")
    by_half = {"claude": {row["name"]: row for row in (claude or {}).get("host") or [] if isinstance(row, dict) and isinstance(row.get("name"), str) and NAME.fullmatch(row["name"])},
               "codex": {row["name"]: row for row in (codex or {}).get("host") or [] if isinstance(row, dict) and isinstance(row.get("name"), str) and NAME.fullmatch(row["name"])}}
    names = list(by_half["claude"]) + [name for name in by_half["codex"] if name not in by_half["claude"]]
    host = [{"name": name, **{field: row_field(by_half["claude"].get(name, {}), field) for field in CLAUDE_ROW_FIELDS},
             **{field: row_field(by_half["codex"].get(name, {}), field) for field in CODEX_ROW_FIELDS}} for name in names] if names else None
    # Codex lanes first, as the single record emitted them before the split: the Fleet page reads only the first 200 lanes (tools/local-pages/fleet_data.py `_skill_usage`) and the Claude half alone
    # holds more than that (564 on 2026-10-13), so lanes appended after the Claude ones would never be shown.
    lanes = [lane for source, client in ((codex, "codex"), (claude, "claude")) for lane in (source or {}).get("lanes") or []
             if isinstance(lane, dict) and lane.get("client") == client]
    stamps = [skill_usage.parse_iso(record["generated_at"]) for record in (claude, codex) if record and isinstance(record.get("generated_at"), str)]
    present = claude or codex
    measured = {"host": bool(claude and claude.get("measured", {}).get("host") is True), "codex": bool(codex and codex.get("measured", {}).get("codex") is True),
                "claude": bool(claude and claude.get("measured", {}).get("claude") is True)}
    return {"schema": SCHEMA, "half": "all", "generated_at": min(stamps).isoformat() if stamps else None, "window_days": present.get("window_days") if present else None,
            "host": host, "lanes": lanes if (claude and claude.get("lanes") is not None) or (codex and codex.get("lanes") is not None) else None,
            "zero_use": {"codex": [row["name"] for row in host or [] if row["codex_use"] == 0],
                         "claude_host_lifetime": [row["name"] for row in host or [] if row["claude_uses_lifetime"] == 0]},
            "codex_bulk_scan_limit": codex.get("codex_bulk_scan_limit") if codex else None,
            "halves": {"claude": claude.get("generated_at") if claude else None, "codex": codex.get("generated_at") if codex else None},
            "measured": measured}


@contextlib.contextmanager
def refresh_lock(path, wait=LOCK_WAIT):
    """An exclusive flock on `path` (created mode 0600) for one refresh: waits up to `wait` seconds for the other half's refresh, then raises TimeoutError. The lock belongs to the open file description, so two
    opens of the file in one process also exclude each other (util-linux sys-utils/flock.1.adoc L84), and it is dropped when the descriptor is closed or the process ends (L78), so a crashed refresh never
    holds it."""
    if fcntl is None:
        yield
        return
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT | os.O_CLOEXEC, 0o600)
    try:
        deadline = time.monotonic() + wait
        while True:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise TimeoutError("the other half's refresh holds the lock") from None
                time.sleep(0.05)
        yield
    finally:
        os.close(descriptor)


def refresh_combined(combined, own, other, wait=LOCK_WAIT):
    """Write the combined record from this half's record and the other half's newest one (a missing, unreadable or malformed file is an absent half). The read of the other record and the publication of the
    combined one happen under one lock: a half publishes its own record before it asks for the lock, so whichever refresh runs second reads what the first half published and writes the last combined record.
    Never raises, whatever the other record holds or the lock or the destination does: the half's own record is what the unit's exit status stands for, and the caller prints a fixed message on False."""
    try:
        destination = combined.absolute()
        require_outside_worktrees(destination)   # before the lock file is opened: it sits in the destination's directory
        destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with refresh_lock(destination.with_name(destination.name + ".lock"), wait):
            try:
                newest = json.loads(other.read_text()) if other else None
            except (OSError, ValueError):
                newest = None
            records = {own.get("half"): own}
            records.setdefault("claude" if own.get("half") == "codex" else "codex", newest)
            publish(destination, merge_halves(records.get("claude"), records.get("codex")))
        return True
    except Exception:  # noqa: BLE001 - a convenience refresh must not change the exit status or print a traceback (its text can hold the home path)
        return False


def require_outside_worktrees(path):
    if skill_usage.inside_git_work_tree(path.parent) or path.is_relative_to(ROOT):
        raise ValueError("report destination must be outside git worktrees")


def publish(path, report):
    require_outside_worktrees(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, temp = tempfile.mkstemp(prefix=".skill-usage-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w") as stream:
            json.dump(report, stream, indent=2, sort_keys=True)
            stream.write("\n")
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def render_units(destination, repository, python, node):
    destination.mkdir(parents=True, exist_ok=True)
    values = {"@REPOSITORY@": str(repository), "@PYTHON@": str(python), "@NODE@": str(node)}
    for value in values.values():
        if not Path(value).is_absolute() or any(char in value for char in ('\n', '\r', '"', '\\')):
            raise ValueError("unit values must be absolute paths without unit quoting characters")
        if hidden_by_marker(value):
            raise LayoutRefused("the clone, the interpreter and node must be outside /srv, which the units' TemporaryFileSystem=/srv:ro hides from them")
    for name in UNIT_FILES:
        text = (ROOT / "adoption/templates/systemd" / name).read_text()
        for key, value in values.items():
            text = text.replace(key, value.replace("%", "%%").replace("$", "$$"))
        (destination / name).write_text(text)


ARGUMENT_REFUSAL = "the command line has an argument this version does not take, or lacks one it needs; nothing was run"


class FixedErrorParser(argparse.ArgumentParser):
    """A command line this program cannot use ends in a fixed line and exit 2. argparse's own message echoes the values it could not use, and a unit's command line carries the account's paths: a service rendered by an
    earlier version still passes the removed --refuse-writable with the home directory and the clone, and replaying it printed both. `error` is the hook for another behavior (python/cpython@cbc944f4bc59:
    Lib/argparse.py L1925-L1932 joins the argv values it could not use into the message `unrecognized arguments: ...` and calls it; L2675-L2686 prints the message to stderr and exits 2, and says that an override "should
    either exit or raise an exception"; Doc/library/argparse.rst L2124-L2127)."""

    def error(self, message):
        self.exit(2, f"daily skill usage refused: {ARGUMENT_REFUSAL}\n")


def main(argv=None):
    parser = FixedErrorParser(description=__doc__)
    parser.add_argument("--half", choices=HALVES, help="the client half to collect (required unless report files are given): claude = /skill-doctor capture + Claude lanes sweep, codex = Codex rollout scan + lanes report")
    parser.add_argument("--codex-root", action="append", type=Path, default=[])
    parser.add_argument("--claude-root", action="append", type=Path, default=[])
    parser.add_argument("--window", type=int, default=7)
    parser.add_argument("--claude-timeout", type=int, metavar="SECONDS",
                        help=f"seconds the /skill-doctor capture may take (default: skill_usage.py's, {skill_usage.DEFAULT_CLAUDE_TIMEOUT})")
    parser.add_argument("--now")
    parser.add_argument("--node", default="node")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--combined-out", type=Path, help="after the half's record is written, refresh this combined record (what the Fleet page reads) from it and --other-record")
    parser.add_argument("--other-record", type=Path, help="the other half's record, merged into --combined-out when it exists")
    parser.add_argument("--host-report", type=Path)
    parser.add_argument("--codex-lanes-report", type=Path)
    parser.add_argument("--claude-lanes-report", type=Path)
    parser.add_argument("--render-units", type=Path)
    parser.add_argument("--repository", type=Path, default=ROOT)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    args = parser.parse_args(argv)
    try:
        if args.render_units:
            node = shutil.which(args.node)
            if not node:
                raise ValueError("node executable is unavailable")
            require_reviewed_main(args.repository)   # a unit rendered for a clone that the run refuses would fail every day
            render_units(args.render_units, args.repository, args.python, Path(node))
            return 0
        if not 1 <= args.window <= 366:
            raise ValueError("invalid window")
        if args.claude_timeout is not None and not 1 <= args.claude_timeout <= 3600:
            raise ValueError("invalid timeout")
        now = skill_usage.parse_iso(args.now) if args.now else skill_usage.now_utc()
        sources = (args.host_report, args.codex_lanes_report, args.claude_lanes_report)
        half = args.half or "all"
        if any(sources):
            reports = tuple(json.loads(path.read_text()) if path else None for path in sources)
        else:
            if not args.half:
                raise ValueError("a half is required")
            roots = args.claude_root if args.half == "claude" else args.codex_root
            if not roots:
                raise ValueError("the root of the half's client must be explicit")
            require_reviewed_main(ROOT)
            reports = collect_half(args.half, roots, window=args.window, now=now, node=args.node, claude_timeout=args.claude_timeout)
        for note in unusable_reports(reports[1], reports[2]):
            print(f"daily skill usage: {note}", file=sys.stderr)
        report = project_reports(*reports, now=now.isoformat(), window=args.window, half=half)
        if args.out:
            publish(args.out.absolute(), report)
        else:
            print(json.dumps(report, indent=2, sort_keys=True))
        if args.combined_out and args.half and not refresh_combined(args.combined_out, report, args.other_record):
            print("daily skill usage: the combined record was not refreshed", file=sys.stderr)
        return 0 if all(report["measured"].values()) else 1
    except Refused as error:
        print(f"daily skill usage refused: {error}", file=sys.stderr)
        return 2
    except (OSError, ValueError, TypeError, AttributeError, KeyError, subprocess.SubprocessError):   # never the exception's text or a traceback: both name the account's home
        print("daily skill usage unavailable; inspect the native collector separately", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
