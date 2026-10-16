"""tools/session-relaunch/session_relaunch.py: roster snapshots, the relaunch decision, the handoff and the tab calls.

The client and the tab opener are stand-in scripts: the stand-in `claude agents --json` prints a JSON file, and the stand-in
PowerShell records its arguments and, like a real tab, makes the launched session appear in that JSON file.
"""

import contextlib
import datetime as dt
import hashlib
import importlib.util
import io
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "session-relaunch" / "session_relaunch.py"
spec = importlib.util.spec_from_file_location("session_relaunch", TOOL)
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)

PREV, THIS = "a84c7d5283d54dee8de81e0c792dcaa0", "beb4ce836f4d48828ac60cfde6488630"
END = dt.datetime(2026, 10, 14, 6, 41, 17, tzinfo=dt.timezone.utc)
START = dt.datetime(2026, 10, 14, 12, 48, 57, tzinfo=dt.timezone.utc)
NOW = dt.datetime(2026, 10, 14, 12, 49, 30, tzinfo=dt.timezone.utc)
BOOTS = [{"index": -1, "boot_id": PREV, "first_entry": 1791640000000000, "last_entry": int(END.timestamp() * 1e6)},
         {"index": 0, "boot_id": THIS, "first_entry": int(START.timestamp() * 1e6), "last_entry": int(NOW.timestamp() * 1e6)}]

FAKE_CLAUDE = """#!/bin/sh
[ "$1 $2" = "agents --json" ] || exit 2
if [ -n "$FAKE_CLAUDE_FAILS" ] && [ "$(cat "$FAKE_CLAUDE_FAILS")" -gt 0 ]; then
  echo $(( $(cat "$FAKE_CLAUDE_FAILS") - 1 )) > "$FAKE_CLAUDE_FAILS"
  echo "client not ready" >&2
  exit 1
fi
cat "$FAKE_AGENTS_JSON"
"""
FAKE_POWERSHELL = """#!/usr/bin/env python3
import json, os, sys, time
argv = sys.argv[1:]
with open(os.environ["FAKE_PS_LOG"], "a") as log:
    log.write(json.dumps(argv) + "\\n")
rc = int(os.environ.get("FAKE_PS_RC", "0"))
launcher = argv[argv.index("-Name") + 1]
if launcher in os.environ.get("FAKE_PS_FAIL_NAMES", "").split(","):
    rc = 1
if os.environ.get("FAKE_PS_LAUNCH", "1" if rc == 0 else "0") == "1":
    names = json.loads(os.environ["FAKE_PS_NAMES"])
    launched = names[launcher]
    path = os.environ["FAKE_AGENTS_JSON"]
    rows = json.load(open(path))
    gone = json.loads(os.environ.get("FAKE_PS_KILL", "{}")).get(argv[argv.index("-Name") + 1])
    rows = [r for r in rows if r["name"] != gone]  # a session that registered earlier exits as this tab opens
    rows.append({"name": launched, "kind": "interactive", "sessionId": "new", "cwd": "/w", "pid": "1", "status": "busy"})
    json.dump(rows, open(path, "w"))
    print("opened " + launched, flush=True)
time.sleep(float(os.environ.get("FAKE_PS_SLEEP", "0")))
sys.exit(rc)
"""
NEXT = "c0ffee00c0ffee00c0ffee00c0ffee00"


class Interrupted(BaseException):
    """A stop of the relaunch process itself (the unit's timeout, a user-manager stop, a crash)."""


def row(name, sid, kind="interactive", cwd="/home/example/code/native-agent-stack"):
    return {"name": name, "kind": kind, "sessionId": sid, "cwd": cwd, "pid": "100", "startedAt": "1791980000000",
            "status": "busy"}


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(self.enterContext(tempfile.TemporaryDirectory()))
        bin_dir = self.tmp / "bin"
        bin_dir.mkdir()
        for name, body in (("claude", FAKE_CLAUDE), ("powershell", FAKE_POWERSHELL)):
            (bin_dir / name).write_text(body)
            (bin_dir / name).chmod(0o755)
        self.agents = self.tmp / "agents.json"
        self.agents.write_text("[]")
        self.ps_log = self.tmp / "ps.log"
        example = json.loads((ROOT / "tools" / "session-relaunch" / "config.example.json").read_text())
        self.config = R.load_config(self.write_config(dict(
            example, state_dir=str(self.tmp / "state"), claude=str(bin_dir / "claude"),
            powershell=str(bin_dir / "powershell"), handoff_dir=str(self.tmp / "cc"), projects_dir=str(self.tmp / "projects"),
            cc_wait_s=2, spacing_s=0, tab_attempts=2, tab_retry_pause_s=0, tab_timeout_s=30, settle_s=0.3, poll_s=0.05,
            client_wait_s=0)))
        names = {p["launcher_name"]: p["session_name"] for p in self.config["profiles"]}
        self.enterContext(mock.patch.dict(os.environ, {
            "FAKE_AGENTS_JSON": str(self.agents), "FAKE_PS_LOG": str(self.ps_log), "FAKE_PS_NAMES": json.dumps(names)}))
        transcript = self.tmp / "projects" / "-home-example-code-native-agent-stack" / "sid-cc.jsonl"
        transcript.parent.mkdir(parents=True)
        transcript.write_text("{}\n")

    def write_config(self, config):
        path = self.tmp / "config.json"
        path.write_text(json.dumps(config))
        return path

    def roster(self, boot, written, sessions):
        R.cmd_snapshot(self.config, boot_id=boot, sessions=sessions, at=written)

    def crash_roster(self, sessions=None):
        self.roster(PREV, END - dt.timedelta(seconds=40), sessions if sessions is not None else [
            row("trading-cc", "sid-trading", cwd="/home/example/code/us-equities-trading"), row("wsl-architecture-design", "sid-cc"),
            row("ns2604-coop", "sid-coop"), row("librarium-course-e2", "sid-lib", cwd="/home/example/code/librarium-course"),
            row("bg-job", "sid-bg", kind="background")])

    def ps_calls(self):
        return [json.loads(line) for line in self.ps_log.read_text().splitlines()] if self.ps_log.exists() else []

    def state(self, boot=PREV):
        path = R.marker(self.config, "relaunch", boot)
        return json.loads(path.read_text()) if path.exists() else None

    def main(self, *args, boot=None):
        """The command line in-process, as the units run it, on this host's boot or a pinned one."""
        with mock.patch.object(R, "current_boot_id", return_value=boot or R.current_boot_id()), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return R.main([*args, "--config", str(self.tmp / "config.json")])


class Snapshot(Fixture):
    def test_writes_this_boots_roster_with_the_listed_fields(self):
        self.agents.write_text(json.dumps([dict(row("api-actions", "s1"), extra="dropped")]))
        path = R.cmd_snapshot(self.config, boot_id=THIS, sessions=R.list_sessions(self.config["claude"]), at=NOW)
        self.assertEqual(path.name, f"roster-{THIS}.json")
        doc = json.loads(path.read_text())
        self.assertEqual((doc["boot_id"], doc["written_at"]), (THIS, "2026-10-14T12:49:30Z"))
        self.assertEqual(doc["sessions"], [row("api-actions", "s1")])

    def test_a_failing_client_gives_no_list_and_an_empty_one_stays_a_list(self):
        self.agents.write_text("not json")
        self.assertIsNone(R.list_sessions(self.config["claude"]))
        self.agents.write_text("[]")
        self.assertEqual(R.list_sessions(self.config["claude"]), [])

    def test_a_failing_client_keeps_the_last_good_roster_until_it_answers_again(self):
        path = R.roster_dir(self.config) / f"roster-{THIS}.json"
        self.agents.write_text(json.dumps([row("api-actions", "s1")]))
        self.assertEqual(self.main("snapshot", boot=THIS), 0)
        good = path.read_bytes()
        self.agents.write_text("not json")
        self.assertEqual(self.main("snapshot", boot=THIS), 1)
        self.assertEqual(path.read_bytes(), good)
        self.agents.write_text(json.dumps([row("api-actions", "s1"), row("trading-cc", "s2")]))
        self.assertEqual(self.main("snapshot", boot=THIS), 0)
        self.assertEqual([r["name"] for r in json.loads(path.read_text())["sessions"]], ["api-actions", "trading-cc"])

    def test_the_minute_snapshot_carries_the_unrelaunched_rows_while_a_relaunch_runs(self):
        self.crash_roster()
        # Stopped before its first call (a call stopped in flight stays unresolved: test_a_run_stopped_during_a_tab_call_...).
        with mock.patch.object(R, "listed", side_effect=Interrupted), self.assertRaises(Interrupted):
            R.cmd_relaunch(self.config, boot_id=THIS, at=NOW, boots=BOOTS, dry_run=False)
        self.agents.write_text(json.dumps([row("api-actions", "s-new")]))
        self.assertEqual(self.main("snapshot", boot=THIS), 0)
        names = [r["name"] for r in json.loads((R.roster_dir(self.config) / f"roster-{THIS}.json").read_text())["sessions"]]
        self.assertEqual(sorted(names), ["api-actions", "bg-job", "librarium-course-e2", "ns2604-coop", "trading-cc",
                                         "wsl-architecture-design"])
        R.cmd_relaunch(self.config, boot_id=THIS, at=NOW, boots=BOOTS, dry_run=False)
        self.assertEqual(self.state()["status"], "complete")
        self.assertEqual(self.main("snapshot", boot=THIS), 0)
        names = [r["name"] for r in json.loads((R.roster_dir(self.config) / f"roster-{THIS}.json").read_text())["sessions"]]
        self.assertEqual(names, ["api-actions", "wsl-architecture-design", "trading-cc", "ns2604-coop"])

    def test_keeps_the_newest_rosters_only(self):
        for i in range(R.ROSTER_KEEP + 3):
            path = R.cmd_snapshot(self.config, boot_id=f"{i:032x}", sessions=[], at=NOW)
            os.utime(path, (1_000_000 + i, 1_000_000 + i))
        names = {p.name for p in R.roster_dir(self.config).glob("roster-*.json")}
        self.assertEqual(len(names), R.ROSTER_KEEP)
        self.assertNotIn(f"roster-{0:032x}.json", names)


class Decision(Fixture):
    def decide(self, alive=()):
        return R.plan(self.config, boot_id=THIS, at=NOW, boots=BOOTS, alive_rows=[row(n, "x") for n in alive])

    def test_no_roster_from_an_earlier_boot_relaunches_nothing(self):
        self.assertEqual(self.decide()["action"], "none")
        self.roster(THIS, NOW, [row("trading-cc", "s")])
        self.assertIn("no roster", self.decide()["reason"])

    def test_the_newest_earlier_roster_decides(self):
        self.roster("1" * 32, END - dt.timedelta(days=2), [row("api-actions", "old")])
        self.crash_roster()
        self.assertEqual(self.decide()["prev_boot"], PREV)

    def test_a_planned_restart_relaunches_nothing(self):
        self.crash_roster()
        R.marker(self.config, "planned", PREV).write_text("{}")
        self.assertIn("planned restart", self.decide()["reason"])

    def test_a_completed_relaunch_is_not_run_again_and_an_unfinished_one_is(self):
        self.crash_roster()
        state = R.marker(self.config, "relaunch", PREV)
        state.write_text(json.dumps({"prev_boot": PREV, "status": "complete", "runs": []}))
        self.assertIn("already relaunched", self.decide()["reason"])
        for status in ("in_progress", "partial"):
            state.write_text(json.dumps({"prev_boot": PREV, "status": status, "runs": []}))
            self.assertEqual(self.decide()["action"], "relaunch", status)

    def test_a_roster_older_than_the_limit_at_the_boot_end_relaunches_nothing(self):
        self.roster(PREV, END - dt.timedelta(seconds=301), [row("trading-cc", "s")])
        self.assertIn("does not show who was alive", self.decide()["reason"])

    def test_without_the_ended_boot_in_the_journal_nothing_is_relaunched(self):
        self.crash_roster()
        for boots in ([], [BOOTS[1]]):
            decided = R.plan(self.config, boot_id=THIS, at=NOW, boots=boots, alive_rows=[])
            self.assertEqual(decided["action"], "none")
            self.assertIn("no journal entry", decided["reason"])

    def test_the_cap_counts_relaunch_runs_in_the_window(self):
        self.crash_roster()
        R.marker(self.config, "relaunch", "1" * 32).write_text(json.dumps(
            {"status": "partial", "runs": [{"started_at": R.iso(NOW)}, {"started_at": R.iso(NOW - dt.timedelta(hours=1))}]}))
        R.marker(self.config, "relaunch", "2" * 32).write_text(json.dumps(
            {"status": "complete", "runs": [{"started_at": R.iso(NOW - dt.timedelta(hours=2))}]}))
        self.assertIn("relaunches already", self.decide()["reason"])
        R.marker(self.config, "relaunch", "2" * 32).write_text(json.dumps(
            {"status": "complete", "runs": [{"started_at": "2026-10-13T00:00:00Z"}]}))
        self.assertEqual(self.decide()["action"], "relaunch")

    def test_the_command_center_goes_first_then_the_profile_order(self):
        self.crash_roster()
        decided = self.decide()
        self.assertEqual([r["name"] for r, _ in decided["launch"]], ["wsl-architecture-design", "trading-cc", "ns2604-coop"])
        self.assertEqual({r["name"] for r in decided["left"]}, {"librarium-course-e2", "bg-job"})

    def test_a_running_session_is_not_launched_twice(self):
        self.crash_roster()
        decided = self.decide(alive=("trading-cc",))
        self.assertEqual([r["name"] for r, _ in decided["launch"]], ["wsl-architecture-design", "ns2604-coop"])
        self.assertIn("trading-cc", {r["name"] for r in decided["left"]})

    def test_a_roster_without_profiled_sessions_relaunches_nothing(self):
        self.crash_roster([row("librarium-course-e2", "s")])
        self.assertIn("no session of the roster", self.decide()["reason"])

    def test_a_roster_whose_sessions_all_run_relaunches_nothing(self):
        self.crash_roster([row("trading-cc", "s"), row("ns2604-coop", "t")])
        self.assertIn("already running", self.decide(alive=("trading-cc", "ns2604-coop"))["reason"])

    def test_boot_ids_compare_with_or_without_dashes(self):
        self.assertEqual(R.norm_boot("ABCD-ef01\n"), "abcdef01")
        self.assertEqual(R.boot_window(BOOTS, PREV)[1], END)
        self.assertEqual(R.boot_window(BOOTS, "0" * 32), (None, None))


class Relaunch(Fixture):
    def run_relaunch(self, dry_run=False, boot=THIS, at=NOW, boots=BOOTS):
        return R.cmd_relaunch(self.config, boot_id=boot, at=at, boots=boots, dry_run=dry_run)

    def outcomes(self, boot=PREV):
        return {s["session_name"]: s["outcome"] for s in self.state(boot)["sessions"]}

    def handoffs(self):
        return sorted(Path(self.config["handoff_dir"]).glob("AUTO-RESTART-*.md"))

    def test_writes_a_sealed_handoff_and_opens_the_tabs_in_order(self):
        self.crash_roster()
        self.run_relaunch()
        state = self.state()
        handoff = Path(state["handoff"])
        self.assertEqual(handoff.parent, Path(self.config["handoff_dir"]))
        self.assertEqual(handoff.name, "AUTO-RESTART-20261014T124930Z.md")
        calls = self.ps_calls()
        self.assertEqual([c[c.index("-Name") + 1] for c in calls], ["cc", "trading-cc", "coop"])
        for call in calls:
            self.assertEqual(call[call.index("-File") + 1], self.config["tab_opener"])
            self.assertEqual(call[call.index("-Handoff") + 1], str(handoff))
        self.assertEqual(state["status"], "complete")
        self.assertEqual([s["session_name"] for s in state["sessions"]], ["wsl-architecture-design", "trading-cc", "ns2604-coop"])
        self.assertEqual(set(self.outcomes().values()), {"running"})
        self.assertEqual([[a["rc"] for a in s["attempts"]] for s in state["sessions"]], [[0], [0], [0]])
        self.assertEqual(state["handoff_sha256"], hashlib.sha256(handoff.read_bytes()).hexdigest())
        self.assertEqual(len(state["runs"]), 1)
        self.assertEqual(self.run_relaunch()["action"], "none")
        self.assertEqual(len(self.ps_calls()), 3)

    def test_a_run_stopped_before_its_first_tab_is_rerun_with_the_same_handoff(self):
        self.crash_roster()
        # Stopped at the live-list read before the first call: no call was recorded, so nothing is unresolved.
        with mock.patch.object(R, "listed", side_effect=Interrupted), self.assertRaises(Interrupted):
            self.run_relaunch()
        self.assertEqual(self.state()["status"], "in_progress")
        self.assertEqual(set(self.outcomes().values()), {"pending"})
        sealed = self.handoffs()
        self.assertEqual(len(sealed), 1)
        later = NOW + dt.timedelta(minutes=3)
        self.run_relaunch(at=later)
        self.assertEqual([c[c.index("-Name") + 1] for c in self.ps_calls()], ["cc", "trading-cc", "coop"])
        self.assertEqual(self.handoffs(), sealed)
        self.assertEqual({c[c.index("-Handoff") + 1] for c in self.ps_calls()}, {str(sealed[0])})
        self.assertEqual((self.state()["status"], len(self.state()["runs"])), ("complete", 2))

    def test_failed_tabs_are_retried_by_a_rerun_and_only_the_sessions_not_running(self):
        self.crash_roster()
        os.environ["FAKE_PS_RC"] = "1"
        self.run_relaunch()
        self.assertEqual((self.state()["status"], set(self.outcomes().values())), ("partial", {"failed"}))
        self.agents.write_text(json.dumps([row("trading-cc", "s-by-hand")]))
        os.environ["FAKE_PS_RC"] = "0"
        self.run_relaunch(at=NOW + dt.timedelta(minutes=5))
        self.assertEqual([c[c.index("-Name") + 1] for c in self.ps_calls()[6:]], ["cc", "coop"])
        self.assertEqual(self.state()["status"], "complete")
        self.assertEqual(set(self.outcomes().values()), {"running"})
        self.assertEqual(len(self.handoffs()), 1)

    def test_a_rerun_after_every_session_came_back_by_hand_completes_without_a_tab(self):
        self.crash_roster()
        os.environ["FAKE_PS_RC"] = "1"
        self.run_relaunch()
        self.assertEqual(self.state()["status"], "partial")
        self.agents.write_text(json.dumps([row(n, "by-hand") for n in ("wsl-architecture-design", "trading-cc", "ns2604-coop")]))
        self.run_relaunch(at=NOW + dt.timedelta(minutes=5))
        self.assertEqual(len(self.ps_calls()), 6)
        self.assertEqual((self.state()["status"], set(self.outcomes().values())), ("complete", {"running"}))

    def test_a_session_that_registers_and_then_exits_leaves_a_recoverable_partial_state(self):
        # Local review P2 at 7aad5a02 (:533; the final pass at c8d7fa9e :547-553): the command center registered, then
        # exited as the next tab opened. Its earlier running outcome stood, the run said complete, and plan() refused
        # every later rerun as already relaunched. Completion now rests on the final live list, and the session seen
        # running has its tab start resolved, so a rerun opens it again without a --reopen.
        self.crash_roster()
        os.environ["FAKE_PS_KILL"] = json.dumps({"trading-cc": "wsl-architecture-design"})
        self.run_relaunch()
        self.assertEqual(self.state()["status"], "partial")
        self.assertEqual(self.outcomes(), {"wsl-architecture-design": "absent", "trading-cc": "running",
                                           "ns2604-coop": "running"})
        del os.environ["FAKE_PS_KILL"]
        self.run_relaunch(at=NOW + dt.timedelta(minutes=5))
        self.assertEqual([c[c.index("-Name") + 1] for c in self.ps_calls()], ["cc", "trading-cc", "coop", "cc"])
        self.assertEqual((self.state()["status"], set(self.outcomes().values())), ("complete", {"running"}))

    def test_a_session_that_registers_and_exits_before_a_crash_stays_carried(self):
        # The command center's FULL read of #1141 at b2755a0e (P2): a row left the carry as soon as its session was seen
        # running, so when the command center registered and then exited while the next tab opened, and the boot stopped
        # before the final pass, every snapshot wrote this boot's roster without it, and the next boot dropped it. A row
        # now leaves the carry only when the final list shows its session running.
        self.crash_roster()
        launched, real_one = [], R.relaunch_one

        def one(*args, **kwargs):
            launched.append(real_one(*args, **kwargs))
            if len(launched) == 2:
                raise Interrupted()  # the boot stops right after the second tab
            return launched[-1]

        os.environ["FAKE_PS_KILL"] = json.dumps({"trading-cc": "wsl-architecture-design"})
        try:
            with mock.patch.object(R, "relaunch_one", side_effect=one), self.assertRaises(Interrupted):
                self.run_relaunch()
        finally:
            del os.environ["FAKE_PS_KILL"]
        self.assertEqual(self.main("snapshot", boot=THIS), 0)
        roster = json.loads((R.roster_dir(self.config) / f"roster-{THIS}.json").read_text())
        self.assertIn("wsl-architecture-design", {row["name"] for row in roster["sessions"]})

    def test_a_session_that_registers_and_then_exits_is_carried_again(self):
        # Rebase resolution of #1141 onto #1145 (main's completion rule meets #1141's carry retirement): a session seen
        # running and then missing from the final list is absent and still to be brought back, so a second crash in this
        # boot finds its row in this boot's roster. It guards the retire rule: a row leaves the carry only when the final
        # list shows its session running, and the test fails when an absent session's row is retired too (GPT fix2 of
        # #1141 at 07ea5674: the separate re-carry line it once guarded had become redundant and is removed).
        self.crash_roster()
        os.environ["FAKE_PS_KILL"] = json.dumps({"trading-cc": "wsl-architecture-design"})
        try:
            self.run_relaunch()
        finally:
            del os.environ["FAKE_PS_KILL"]
        self.assertEqual(self.outcomes()["wsl-architecture-design"], "absent")
        self.assertIn("wsl-architecture-design", [row["name"] for row in self.state()["carry"]])
        self.assertNotIn("trading-cc", [row["name"] for row in self.state()["carry"]])
        self.assertEqual(self.main("snapshot", boot=THIS), 0)
        roster = json.loads((R.roster_dir(self.config) / f"roster-{THIS}.json").read_text())
        self.assertIn("wsl-architecture-design", {row["name"] for row in roster["sessions"]})

    def test_an_unreadable_final_list_never_completes_a_run(self):
        # The same finding: completion rests on a final live list that was read. When that read fails, the run is
        # partial (exit 1, the alert), and a rerun reads the list again and completes without a tab.
        self.crash_roster()
        done, real_one, real_list = [], R.relaunch_one, R.list_sessions

        def one(*args, **kwargs):
            done.append(real_one(*args, **kwargs))
            return done[-1]

        with mock.patch.object(R, "relaunch_one", side_effect=one), \
                mock.patch.object(R, "list_sessions", side_effect=lambda claude: None if len(done) == 3 else real_list(claude)):
            self.run_relaunch()
        self.assertEqual(done, ["running"] * 3)
        self.assertEqual(self.state()["status"], "partial")
        self.run_relaunch(at=NOW + dt.timedelta(minutes=5))
        self.assertEqual(len(self.ps_calls()), 3)
        self.assertEqual((self.state()["status"], set(self.outcomes().values())), ("complete", {"running"}))

    def test_a_timer_snapshot_never_overwrites_the_seed_roster_of_a_starting_relaunch(self):
        # Local review P2 at 7aad5a02 (:496; the seed roster write at c8d7fa9e :512): a timer snapshot that read its
        # carry before the relaunch saved its state, and wrote after the seed, replaced the seed with the live list only.
        # The snapshot holds a pause between its carry read and its roster write; the relaunch starts inside that pause.
        self.crash_roster()
        paused, real_carry = threading.Event(), R.carried_rows

        def slow_carry(config, boot_id, live):
            rows = real_carry(config, boot_id, live)
            paused.set()
            time.sleep(1.0)
            return rows

        with mock.patch.object(R, "carried_rows", side_effect=slow_carry), \
                mock.patch.object(R, "current_boot_id", return_value=THIS):
            results = []
            timer = threading.Thread(target=lambda: results.append(
                R.main(["snapshot", "--config", str(self.tmp / "config.json")])))
            timer.start()
            self.assertTrue(paused.wait(10))
            self.run_relaunch()
            timer.join(10)
        self.assertEqual(results, [0])  # the snapshot ran to its end (a thread error would leave this empty)
        seeded = json.loads((R.roster_dir(self.config) / f"roster-{THIS}.json").read_text())
        self.assertLessEqual({"wsl-architecture-design", "trading-cc", "ns2604-coop"},
                             {row["name"] for row in seeded["sessions"]})

    def test_a_partial_relaunch_keeps_its_unfinished_rows_in_this_boots_roster(self):
        # Local review P2 at 7aad5a02 (:222; carried_rows at c8d7fa9e :221-223): only an in_progress state carried its
        # rows, so the first snapshot after a partial run kept the live sessions only, and a second crash lost the lanes
        # the relaunch had not brought back. A partial state of this boot carries them too.
        self.crash_roster()
        os.environ["FAKE_PS_RC"] = "1"
        self.run_relaunch()
        self.assertEqual(self.state()["status"], "partial")
        self.agents.write_text(json.dumps([row("trading-cc", "s-by-hand")]))
        self.assertEqual(self.main("snapshot", boot=THIS), 0)
        roster = json.loads((R.roster_dir(self.config) / f"roster-{THIS}.json").read_text())
        names = [r["name"] for r in roster["sessions"]]
        self.assertEqual(names.count("trading-cc"), 1)  # live, not carried a second time
        self.assertLessEqual({"wsl-architecture-design", "ns2604-coop", "trading-cc"}, set(names))

    def test_a_lane_brought_back_by_a_partial_run_leaves_the_carry(self):
        # Local review P2 at 474cf2b6 (:244-245): the carry was taken before any tab opened, so a lane the run brought
        # back stayed carried; once it exited on purpose, the next snapshot listed its old row again and a second crash
        # would relaunch it. A row leaves the carry when its session is seen running.
        self.crash_roster()
        with mock.patch.dict(os.environ, {"FAKE_PS_FAIL_NAMES": "trading-cc"}):
            self.run_relaunch()
        self.assertEqual(self.state()["status"], "partial")
        self.assertEqual((self.outcomes()["wsl-architecture-design"], self.outcomes()["ns2604-coop"]), ("running", "running"))
        self.agents.write_text("[]")  # the command center and the co-op exit on purpose later in this boot
        self.assertEqual(self.main("snapshot", boot=THIS), 0)
        roster = json.loads((R.roster_dir(self.config) / f"roster-{THIS}.json").read_text())
        names = {r["name"] for r in roster["sessions"]}
        self.assertIn("trading-cc", names)
        self.assertFalse(names & {"wsl-architecture-design", "ns2604-coop"}, names)

    def test_a_boot_stop_right_after_the_state_write_still_relaunches_from_the_seed(self):
        # GPT read of #1141 at 474cf2b6 (P2, the reviewer's retained crash case): with the state saved before the seed
        # roster, a boot stop between the two writes left the timer's empty roster of this boot as the newest, and the
        # next boot opened nothing. The seed roster is written first, both under roster_lock.
        self.crash_roster()
        at = NOW + dt.timedelta(seconds=120)  # past the timer's 90 s boot delay: it has written an empty roster
        self.roster(THIS, at, [])
        real = R.write_atomic

        def stop_after_the_state(path, text, *args, **kwargs):
            real(path, text, *args, **kwargs)
            if path == R.marker(self.config, "relaunch", PREV):
                raise Interrupted()

        with mock.patch.object(R, "write_atomic", side_effect=stop_after_the_state), self.assertRaises(Interrupted):
            self.run_relaunch(at=at)
        self.assertEqual(self.state()["status"], "in_progress")
        start = at + dt.timedelta(minutes=10)
        end = at + dt.timedelta(seconds=60)
        boots = [BOOTS[0], dict(BOOTS[1], last_entry=int(end.timestamp() * 1e6)),
                 {"index": 0, "boot_id": NEXT, "first_entry": int(start.timestamp() * 1e6),
                  "last_entry": int(start.timestamp() * 1e6)}]
        self.run_relaunch(boot=NEXT, at=start + dt.timedelta(seconds=30), boots=boots)
        self.assertEqual([c[c.index("-Name") + 1] for c in self.ps_calls()], ["cc", "trading-cc", "coop"])

    def test_a_crash_before_the_first_minute_snapshot_is_recovered_by_the_next_boot(self):
        self.crash_roster()
        self.run_relaunch()
        self.assertEqual(self.state()["status"], "complete")
        self.agents.write_text("[]")  # boot THIS ends 60 s after its relaunch, before the timer's first run at 90 s
        this_end = NOW + dt.timedelta(seconds=60)
        next_start = NOW + dt.timedelta(minutes=10)
        boots = [BOOTS[0], dict(BOOTS[1], last_entry=int(this_end.timestamp() * 1e6)),
                 {"index": 0, "boot_id": NEXT, "first_entry": int(next_start.timestamp() * 1e6),
                  "last_entry": int(next_start.timestamp() * 1e6)}]
        self.run_relaunch(boot=NEXT, at=next_start + dt.timedelta(seconds=30), boots=boots)
        self.assertEqual([c[c.index("-Name") + 1] for c in self.ps_calls()[3:]], ["cc", "trading-cc", "coop"])
        self.assertEqual(self.state(THIS)["status"], "complete")

    def test_an_unanswering_client_refuses_the_relaunch_and_opens_nothing_until_it_answers(self):
        self.crash_roster()
        self.agents.write_text("not json")
        decided = self.run_relaunch()
        self.assertEqual(decided["action"], "none")
        self.assertIn("no session list", decided["reason"])
        self.assertEqual(self.ps_calls(), [])
        self.assertIsNone(self.state())
        self.assertFalse(Path(self.config["handoff_dir"]).exists())
        self.assertFalse((R.roster_dir(self.config) / f"roster-{THIS}.json").exists())
        self.agents.write_text("[]")
        self.run_relaunch()
        self.assertEqual(len(self.ps_calls()), 3)

    def test_a_client_answering_within_the_wait_is_used(self):
        self.crash_roster()
        fails = self.tmp / "fails"
        fails.write_text("2")
        self.config.update(client_wait_s=10)
        with mock.patch.dict(os.environ, {"FAKE_CLAUDE_FAILS": str(fails)}):
            self.run_relaunch()
        self.assertEqual(fails.read_text().strip(), "0")
        self.assertEqual(self.state()["status"], "complete")

    def test_a_tab_that_launches_then_times_out_is_not_opened_again(self):
        self.crash_roster([row("trading-cc", "s")])
        self.config.update(tab_timeout_s=1)
        with mock.patch.dict(os.environ, {"FAKE_PS_LAUNCH": "1", "FAKE_PS_RC": "1", "FAKE_PS_SLEEP": "4"}):
            self.run_relaunch()
        self.assertEqual(len(self.ps_calls()), 1)
        session = self.state()["sessions"][0]
        self.assertEqual((session["outcome"], session["attempts"][0]["result"]), ("running", "timeout"))
        self.assertEqual(self.state()["status"], "complete")

    def test_a_tab_that_times_out_without_a_session_is_uncertain_and_not_retried(self):
        self.crash_roster([row("trading-cc", "s")])
        self.config.update(tab_timeout_s=1)
        with mock.patch.dict(os.environ, {"FAKE_PS_LAUNCH": "0", "FAKE_PS_RC": "1", "FAKE_PS_SLEEP": "4"}):
            self.run_relaunch()
        self.assertEqual(len(self.ps_calls()), 1)
        self.assertEqual((self.outcomes(), self.state()["status"]), ({"trading-cc": "uncertain"}, "partial"))

    def test_a_failed_tab_whose_session_is_listed_is_not_retried(self):
        self.crash_roster([row("trading-cc", "s")])
        with mock.patch.dict(os.environ, {"FAKE_PS_LAUNCH": "1", "FAKE_PS_RC": "1"}):
            self.run_relaunch()
        self.assertEqual(len(self.ps_calls()), 1)
        self.assertEqual(self.outcomes(), {"trading-cc": "running"})

    def test_a_tab_reported_opened_but_never_listed_is_unconfirmed(self):
        self.crash_roster([row("trading-cc", "s")])
        with mock.patch.dict(os.environ, {"FAKE_PS_LAUNCH": "0", "FAKE_PS_RC": "0"}):
            self.run_relaunch()
        self.assertEqual(len(self.ps_calls()), 1)
        self.assertEqual((self.outcomes(), self.state()["status"]), ({"trading-cc": "unconfirmed"}, "partial"))

    def test_a_rerun_does_not_reopen_a_tab_start_it_could_not_confirm(self):
        # The CC micro at 376f2bb9, F1 (P1): a rerun reset an unconfirmed or uncertain session to pending and opened a second
        # tab, while the first `claude -n` could still register. Such a call stays unresolved until the CC reopens it by name.
        for launch, rc, timeout, outcome in (("0", "0", 30, "unconfirmed"), ("0", "1", 1, "uncertain")):
            with self.subTest(outcome=outcome):
                self.setUp()
                self.crash_roster([row("trading-cc", "s")])
                self.config.update(tab_timeout_s=timeout)
                with mock.patch.dict(os.environ, {"FAKE_PS_LAUNCH": launch, "FAKE_PS_RC": rc, "FAKE_PS_SLEEP": "2" if timeout == 1 else "0"}):
                    self.run_relaunch()
                    self.assertEqual((self.outcomes(), len(self.ps_calls())), ({"trading-cc": outcome}, 1))
                    self.run_relaunch(at=NOW + dt.timedelta(minutes=5))
                self.assertEqual(len(self.ps_calls()), 1)
                self.assertEqual((self.outcomes(), self.state()["status"]), ({"trading-cc": outcome}, "partial"))
                with mock.patch.dict(os.environ, {"FAKE_PS_LAUNCH": "1", "FAKE_PS_RC": "0"}):
                    R.cmd_relaunch(self.config, boot_id=THIS, at=NOW + dt.timedelta(minutes=10), boots=BOOTS, dry_run=False,
                                   reopen={"trading-cc"})
                self.assertEqual(len(self.ps_calls()), 2)
                self.assertEqual((self.outcomes(), self.state()["status"]), ({"trading-cc": "running"}, "complete"))
                self.assertEqual(self.state()["runs"][-1]["reopened"], ["trading-cc"])

    def test_a_run_stopped_during_a_tab_call_leaves_it_unresolved(self):
        # F1, second path: TimeoutStartSec stops a run inside a call. The call is recorded before it is made, so the rerun
        # sees it in flight and does not open the session again.
        self.crash_roster([row("trading-cc", "s"), row("ns2604-coop", "t")])
        with mock.patch.object(R, "open_tab", side_effect=Interrupted), self.assertRaises(Interrupted):
            self.run_relaunch()
        self.assertEqual(self.state()["sessions"][0]["attempts"][-1]["result"], "in_flight")
        self.run_relaunch(at=NOW + dt.timedelta(minutes=5))
        self.assertEqual([c[c.index("-Name") + 1] for c in self.ps_calls()], ["coop"])
        self.assertEqual(self.outcomes(), {"trading-cc": "uncertain", "ns2604-coop": "running"})
        self.assertEqual(self.state()["status"], "partial")

    def test_a_run_stopped_in_its_settle_wait_is_not_reopened_by_a_rerun(self):
        # The CC DELTA micro at 307f686c, P1-a: the call's result was saved with the outcome still pending, so a run stopped
        # in wait_for left a lane that a rerun opened again. The provisional outcome is saved with the result.
        self.crash_roster([row("trading-cc", "s")])
        with mock.patch.dict(os.environ, {"FAKE_PS_LAUNCH": "0", "FAKE_PS_RC": "0"}):
            with mock.patch.object(R, "wait_for", side_effect=Interrupted), self.assertRaises(Interrupted):
                self.run_relaunch()
            self.assertEqual((self.outcomes(), self.state()["sessions"][0]["attempts"][-1]["result"]),
                             ({"trading-cc": "unconfirmed"}, "opened"))
            self.run_relaunch(at=NOW + dt.timedelta(minutes=5))
        self.assertEqual(len(self.ps_calls()), 1)
        self.assertEqual((self.outcomes(), self.state()["status"]), ({"trading-cc": "unconfirmed"}, "partial"))

    def test_a_held_run_lock_refuses_the_run_and_opens_nothing(self):
        # P1-b: a direct --reopen run could overlap the unit's run, and both rewrote the whole state. Every relaunch run takes
        # an exclusive lock in the state directory and exits 1 when another run holds it.
        import fcntl
        self.crash_roster([row("trading-cc", "s")])
        lock = R.state_dir(self.config) / "relaunch.lock"
        with open(lock, "a") as held:
            fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with mock.patch.object(R, "read_boots", return_value=BOOTS):
                self.assertEqual(self.main("relaunch", boot=THIS), 1)
                self.assertEqual(self.main("relaunch", "--reopen", "trading-cc", boot=THIS), 1)
        self.assertEqual((self.ps_calls(), self.state()), ([], None))
        with mock.patch.object(R, "read_boots", return_value=BOOTS):
            self.assertEqual(self.main("relaunch", boot=THIS), 0)  # released: the next run goes ahead
        self.assertEqual(len(self.ps_calls()), 1)

    def test_a_reopen_run_that_makes_no_call_leaves_the_lane_unresolved(self):
        # P3 of the same invariant: a --reopen run that ended skipped kept the earlier opened call as the last attempt, and the
        # next plain rerun opened the lane with no new explicit act. A reopen counts only once its call is made.
        self.crash_roster([row("trading-cc", "s")])
        with mock.patch.dict(os.environ, {"FAKE_PS_LAUNCH": "0", "FAKE_PS_RC": "0"}):
            self.run_relaunch()
            with mock.patch.object(R, "listed", return_value=None):
                R.cmd_relaunch(self.config, boot_id=THIS, at=NOW + dt.timedelta(minutes=5), boots=BOOTS, dry_run=False,
                               reopen={"trading-cc"})
            self.assertEqual(self.outcomes(), {"trading-cc": "unconfirmed"})
            self.run_relaunch(at=NOW + dt.timedelta(minutes=10))
        self.assertEqual(len(self.ps_calls()), 1)
        self.assertEqual(self.outcomes(), {"trading-cc": "unconfirmed"})

    def test_a_reopen_of_a_name_that_is_not_unresolved_or_not_planned_is_refused_with_a_record(self):
        self.crash_roster([row("trading-cc", "s"), row("ns2604-coop", "t")])
        with mock.patch.dict(os.environ, {"FAKE_PS_LAUNCH": "0", "FAKE_PS_RC": "0"}):
            self.run_relaunch()  # both unconfirmed
        self.agents.write_text(json.dumps([row("ns2604-coop", "by-hand")]))
        for name in ("ns2604-coop", "librarium-course-e2", "no-such-lane"):
            with self.subTest(name=name):
                decided = R.cmd_relaunch(self.config, boot_id=THIS, at=NOW + dt.timedelta(minutes=5), boots=BOOTS,
                                         dry_run=False, reopen={name})
                self.assertTrue(decided.get("refused"))
                self.assertIn(name, decided["reason"])
                self.assertEqual(self.state()["refusals"][-1]["reopen"], [name])
        self.assertEqual(len(self.ps_calls()), 2)

    def test_a_reopen_refused_by_a_complete_or_capped_relaunch_is_recorded(self):
        # The GPT read of #1116's follow-up at 7aad5a02 (its P2; the reviewer's two regression cases, reproduced here as the subtests case=complete and case=capped): a
        # --reopen refused because the relaunch is complete, or because the relaunch cap is reached, returned before the
        # only writer of the refusal record. It now records the refusal in the existing state, under the run lock, with no
        # run added and no tab call.
        for label in ("complete", "capped"):
            with self.subTest(case=label):
                self.setUp()
                self.crash_roster([row("trading-cc", "s")])
                self.config.update(max_relaunches=20)
                with mock.patch.dict(os.environ, {"FAKE_PS_LAUNCH": "1" if label == "complete" else "0"}):
                    self.run_relaunch()
                self.assertEqual(self.state()["status"], "complete" if label == "complete" else "partial")
                if label == "capped":
                    self.config.update(max_relaunches=1)
                runs = len(self.state()["runs"])
                decided = R.cmd_relaunch(
                    self.config, boot_id=THIS, at=NOW + dt.timedelta(minutes=5), boots=BOOTS, dry_run=False,
                    reopen={"trading-cc"})
                self.assertTrue(decided.get("refused"))
                self.assertEqual(len(self.ps_calls()), 1)
                state = self.state()
                self.assertEqual([entry["reopen"] for entry in state.get("refusals", [])], [["trading-cc"]])
                self.assertEqual(len(state["runs"]), runs)

    def test_a_dry_run_records_no_refusal(self):
        # The same read's P3: the refusal write ran before the dry-run return. A dry run records no refusal and leaves
        # the state file as it was (it may create the run lock: test_a_dry_run_creates_the_run_lock_and_nothing_else).
        self.crash_roster([row("trading-cc", "s"), row("ns2604-coop", "t")])
        with mock.patch.dict(os.environ, {"FAKE_PS_LAUNCH": "0", "FAKE_PS_RC": "0"}):
            self.run_relaunch()
        before = R.marker(self.config, "relaunch", PREV).read_bytes()
        decided = R.cmd_relaunch(self.config, boot_id=THIS, at=NOW + dt.timedelta(minutes=5), boots=BOOTS, dry_run=True,
                                 reopen={"no-such-lane"})
        self.assertTrue(decided.get("refused"))
        self.assertEqual(R.marker(self.config, "relaunch", PREV).read_bytes(), before)

    def test_an_unreadable_live_list_before_the_first_call_opens_nothing(self):
        # The CC micro at 376f2bb9, F2 (P1): a failed pre-open query on attempt 0 went on to open a tab.
        self.crash_roster([row("trading-cc", "s")])
        with mock.patch.object(R, "listed", return_value=None):
            self.run_relaunch()
        self.assertEqual(self.ps_calls(), [])
        self.assertEqual((self.outcomes(), self.state()["status"]), ({"trading-cc": "skipped"}, "partial"))
        self.assertEqual(self.state()["sessions"][0]["attempts"], [])
        self.run_relaunch(at=NOW + dt.timedelta(minutes=5))  # no call was made, so a rerun may open it
        self.assertEqual((len(self.ps_calls()), self.outcomes()), (1, {"trading-cc": "running"}))

    def test_two_roster_rows_of_one_name_get_one_turn(self):
        # The CC micro at 376f2bb9, F3: plan() kept every row, so two rows of one name got two turns.
        self.crash_roster([row("wsl-architecture-design", "sid-cc"), row("wsl-architecture-design", "sid-cc-2"),
                           row("trading-cc", "s")])
        decided = R.plan(self.config, boot_id=THIS, at=NOW, boots=BOOTS, alive_rows=[])
        self.assertEqual([r["sessionId"] for r, _ in decided["launch"]], ["sid-cc", "s"])
        self.assertEqual([r["sessionId"] for r in decided["left"]], ["sid-cc-2"])
        self.run_relaunch()
        self.assertEqual([c[c.index("-Name") + 1] for c in self.ps_calls()], ["cc", "trading-cc"])
        text = Path(self.state()["handoff"]).read_text()
        self.assertIn("wsl-architecture-design (interactive, a second row of a name relaunched above)", text)

    def test_the_handoff_names_the_stop_the_sessions_and_the_rest(self):
        self.crash_roster()
        text = self.run_relaunch(dry_run=True)["handoff_text"]
        self.assertIn(f"The previous boot ({PREV}) ended at 2026-10-14T06:41:17Z", text)
        self.assertIn("this boot's journal starts at 2026-10-14T12:48:57Z", text)
        self.assertIn("There is no outgoing command center", text)
        self.assertIn("`claude --resume sid-lib`", text)
        self.assertIn(str(self.tmp / "projects" / "-home-example-code-native-agent-stack" / "sid-cc.jsonl"), text)
        self.assertIn("| trading-cc | trading-cc | sid-trading | /home/example/code/us-equities-trading | not found |", text)
        self.assertIn(self.config["transcript_tail"], text)

    def test_a_dry_run_writes_and_opens_nothing(self):
        self.crash_roster()
        self.run_relaunch(dry_run=True)
        self.assertEqual(self.ps_calls(), [])
        self.assertIsNone(self.state())
        self.assertFalse((R.roster_dir(self.config) / f"roster-{THIS}.json").exists())
        self.assertFalse(Path(self.config["handoff_dir"]).exists())

    def test_a_failing_tab_is_retried_recorded_and_the_rest_still_open(self):
        self.crash_roster()
        os.environ["FAKE_PS_RC"] = "1"
        self.run_relaunch()
        sessions = self.state()["sessions"]
        self.assertEqual([[a["rc"] for a in s["attempts"]] for s in sessions], [[1, 1], [1, 1], [1, 1]])
        self.assertEqual({a["result"] for s in sessions for a in s["attempts"]}, {"failed"})
        self.assertEqual(len(self.ps_calls()), 6)

    def test_a_dry_run_creates_the_run_lock_and_nothing_else(self):
        # #1116 follow-up (d), item 1: the README said a dry run records nothing, but every run, dry or not, takes the run
        # lock, and run_lock() opens relaunch.lock with O_CREAT. Measured on a state directory that does not exist yet, and
        # on one that holds only the earlier boot's roster, where the dry run goes through the whole plan and the handoff.
        readme = " ".join((ROOT / "tools" / "session-relaunch" / "README.md").read_text().split())
        self.assertNotIn("A dry run records nothing", readme)
        self.assertIn("A dry run writes no relaunch state, roster, refusal or handoff, but like every run it takes the run "
                      "lock: it creates `relaunch.lock` in the state directory, creating the directory too when it is "
                      "missing, and sets the directory to mode 0700.", readme)

        def tree():
            return {p.relative_to(self.tmp).as_posix(): p.read_bytes() if p.is_file() else None for p in self.tmp.rglob("*")}

        before = tree()
        self.assertEqual(self.run_relaunch(dry_run=True)["reason"], "no roster from an earlier boot")
        after = tree()
        self.assertEqual(sorted(set(after) - set(before)), ["state", "state/relaunch.lock"])
        self.assertEqual({p: v for p, v in after.items() if p in before}, before)
        self.assertEqual(stat.S_IMODE(Path(self.config["state_dir"]).stat().st_mode), 0o700)
        self.setUp()
        self.crash_roster()
        state_dir = Path(self.config["state_dir"])
        state_dir.chmod(0o755)  # as `install -D` leaves it
        before = tree()
        self.assertIn("handoff_text", self.run_relaunch(dry_run=True))
        after = tree()
        self.assertEqual(sorted(set(after) - set(before)), ["state/relaunch.lock"])
        self.assertEqual({p: v for p, v in after.items() if p in before}, before)
        self.assertEqual(stat.S_IMODE(state_dir.stat().st_mode), 0o700)

    def test_only_the_refusals_the_readme_names_are_recorded(self):
        # #1116 follow-up (d), item 2 (the CC micro's P3-1): the README read as if every refused --reopen with a readable
        # state were recorded. plan()'s own refusals (no journal entry, an unreadable state), a missing or changed sealed
        # handoff, a held run lock and a client that gives no list record nothing, and a --reopen refused before any
        # relaunch state exists has nothing to record into; only the two kinds the README names are recorded.
        readme = " ".join((ROOT / "tools" / "session-relaunch" / "README.md").read_text().split())
        for sentence in (
                "Two kinds of refusal are also recorded, as a `refusals` entry in the ended boot's relaunch state file, "
                "under the run lock, with no run added: a name that is not an unresolved session this relaunch still has "
                "to bring back, and any `--reopen` while the relaunch has nothing to relaunch",
                "Either is recorded only when that state file already exists and can be read, and never in a dry run.",
                "No other refusal is recorded: another run holds the run lock, the client gives no session list, the "
                "journal has no entry for the ended boot, the relaunch state cannot be read, or the sealed handoff of an "
                "unfinished relaunch is missing or changed."):
            self.assertIn(sentence, readme)

        said = []

        def reopen(name, *extra, boots=BOOTS):
            err = io.StringIO()
            with mock.patch.object(R, "read_boots", return_value=boots), \
                    mock.patch.object(R, "current_boot_id", return_value=THIS), \
                    contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
                code = R.main(["relaunch", *extra, "--reopen", name, "--config", str(self.tmp / "config.json")])
            said.append(err.getvalue())
            return code

        def refused_for(text):
            # The CC's FULL read of bae41b92 (P3, :601): each case must show which refusal fired, not only exit 1.
            self.assertIn(text, said[-1])

        self.crash_roster([row("trading-cc", "s")])
        self.assertEqual(reopen("trading-cc"), 1)  # no relaunch state yet: nothing to record into
        refused_for("not an unresolved session")
        self.assertIsNone(self.state())
        with mock.patch.dict(os.environ, {"FAKE_PS_LAUNCH": "0", "FAKE_PS_RC": "0"}):
            self.run_relaunch()
        self.assertEqual((self.outcomes(), self.state()["status"]), ({"trading-cc": "unconfirmed"}, "partial"))
        path = R.marker(self.config, "relaunch", PREV)
        kept = path.read_bytes()
        self.assertEqual(reopen("trading-cc", boots=[BOOTS[1]]), 1)  # no journal entry for the ended boot
        refused_for("no journal entry for boot")
        self.assertEqual(reopen("no-such-lane", "--dry-run"), 1)  # a dry run
        refused_for("not an unresolved session")
        handoff = Path(self.state()["handoff"])
        sealed = handoff.read_bytes()
        handoff.chmod(0o600)
        handoff.write_bytes(sealed + b"changed\n")
        self.assertEqual(reopen("trading-cc"), 1)  # the sealed handoff changed
        refused_for("is missing or changed")
        handoff.write_bytes(sealed)
        import fcntl
        with open(R.state_dir(self.config) / "relaunch.lock", "a") as held:
            fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.assertEqual(reopen("trading-cc"), 1)  # another run holds the run lock
            refused_for("another relaunch run holds")
        self.agents.write_text("not json")
        self.assertEqual(reopen("trading-cc"), 1)  # the client gives no session list
        refused_for("gave no session list")
        self.agents.write_text("[]")
        self.assertEqual(path.read_bytes(), kept)
        self.assertNotIn("refusals", self.state())
        self.assertEqual(reopen("no-such-lane"), 1)  # recorded: not an unresolved session to bring back
        refused_for("not an unresolved session")
        state = self.state()
        state["status"] = "complete"
        path.write_text(json.dumps(state))
        self.assertEqual(reopen("trading-cc", "--dry-run"), 1)  # a dry run records neither kind
        refused_for("nothing to relaunch")
        self.assertEqual(reopen("trading-cc"), 1)  # recorded: nothing to relaunch, the relaunch is complete
        refused_for("nothing to relaunch")
        self.assertEqual([entry["reopen"] for entry in self.state()["refusals"]], [["no-such-lane"], ["trading-cc"]])
        path.write_text("{not json")
        self.assertEqual(reopen("trading-cc"), 1)  # the relaunch state cannot be read
        refused_for("is unreadable")
        self.assertEqual(path.read_text(), "{not json")
        self.assertEqual(len(self.ps_calls()), 1)


class Modes(Fixture):
    def mode(self, path):
        return stat.S_IMODE(path.stat().st_mode)

    def test_the_records_are_private_to_the_user(self):
        state_dir = Path(self.config["state_dir"])
        state_dir.mkdir(mode=0o755)
        state_dir.chmod(0o755)  # as `install -D` leaves it
        self.crash_roster()
        R.cmd_relaunch(self.config, boot_id=THIS, at=NOW, boots=BOOTS, dry_run=False)
        self.assertEqual(self.main("plan-restart", boot=THIS), 0)
        rosters = R.roster_dir(self.config)
        self.assertEqual({p.name: self.mode(p) for p in (state_dir, rosters, Path(self.config["handoff_dir"]))},
                         {"state": 0o700, "rosters": 0o700, "cc": 0o700})
        self.assertEqual({p.name: self.mode(p) for p in [*rosters.iterdir(), *state_dir.glob("*.json")]},
                         {f"roster-{PREV}.json": 0o600, f"roster-{THIS}.json": 0o600, f"relaunch-{PREV}.json": 0o600,
                          f"planned-{THIS}.json": 0o600})
        self.assertEqual(self.mode(Path(self.state()["handoff"])), 0o400)

    def test_an_existing_handoff_directory_keeps_its_mode(self):
        handoff_dir = Path(self.config["handoff_dir"])
        handoff_dir.mkdir(mode=0o755)
        handoff_dir.chmod(0o755)
        self.crash_roster()
        R.cmd_relaunch(self.config, boot_id=THIS, at=NOW, boots=BOOTS, dry_run=False)
        self.assertEqual(self.mode(handoff_dir), 0o755)


    def test_the_tool_and_its_tests_publish_no_full_digest(self):
        # The CC's FULL read of bae41b92 (P1): a test comment carried the full sha256 of a review file outside the
        # repository, which commits to unpublished bytes. Reads are cited by PR, commit and finding only.
        paths = [Path(__file__), *sorted((ROOT / "tools" / "session-relaunch").rglob("*")),
                 ROOT / "evidence" / "artifacts" / "session-relaunch-20261014" / "README.md"]
        for path in paths:
            if path.is_file():
                with self.subTest(path=str(path.relative_to(ROOT))):
                    self.assertIsNone(re.search(r"(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])", path.read_text(errors="replace")))

    def test_missing_parents_of_the_state_directory_are_created_private(self):
        # The CC's FULL read of bae41b92 (P3, R:69): Path.mkdir(parents=True) creates missing parents with the default
        # permissions, without taking mode into account (python/cpython v3.13.16, cbc944f4, Doc/library/pathlib.rst:1476-1478).
        # Each directory the tool creates is 0700, as the XDG Base Directory specification asks of a
        # directory it creates (version 0.8, "Referencing this specification").
        old = os.umask(0o022)
        try:
            leaf = self.tmp / "new-parent" / "nested" / "state"
            R.private_dir(leaf)
        finally:
            os.umask(old)
        for path in (self.tmp / "new-parent", self.tmp / "new-parent" / "nested", leaf):
            with self.subTest(path=path.name):
                self.assertEqual(self.mode(path), 0o700)
        self.assertEqual(self.mode(self.tmp), stat.S_IMODE(self.tmp.stat().st_mode))  # an existing parent is untouched


class CommandLine(Fixture):
    def test_plan_restart_marks_this_boot(self):
        done = subprocess.run([sys.executable, "-I", str(TOOL), "plan-restart", "--config", str(self.tmp / "config.json")],
                              capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        doc = json.loads(Path(done.stdout.strip()).read_text())
        self.assertEqual(doc["boot_id"], R.current_boot_id())

    def test_a_missing_journal_entry_or_an_unreadable_state_exits_nonzero(self):
        # The CC micro at 376f2bb9, F4: both skips exited 0, so the unit did not fail and nothing alerted.
        self.crash_roster()
        with mock.patch.object(R, "read_boots", return_value=[BOOTS[1]]):
            self.assertEqual(self.main("relaunch", boot=THIS), 1)
        R.marker(self.config, "relaunch", PREV).write_text("{not json")
        with mock.patch.object(R, "read_boots", return_value=BOOTS):
            self.assertEqual(self.main("relaunch", boot=THIS), 1)
        self.assertEqual(self.ps_calls(), [])

    def test_a_config_without_a_required_key_is_refused(self):
        path = self.write_config({"state_dir": str(self.tmp)})
        with self.assertRaises(SystemExit):
            R.load_config(path)


class PublicationSurfaces(unittest.TestCase):
    """The change's published files never attribute a quoted phrase to the owner: owner chat is paraphrased, never quoted
    (the fix round of the first read at 7a504750, its blocker 1). Checked by structure, so no private text is held here."""

    QUOTES = ('"', "\u201c", "\u201d")

    def surfaces(self):
        paths = [ROOT / "docs" / "decisions" / "2026-10-14-session-relaunch-after-wsl-restart.md"]
        for folder in (ROOT / "tools" / "session-relaunch", ROOT / "evidence" / "artifacts" / "session-relaunch-20261014"):
            paths += sorted(p for p in folder.rglob("*") if p.is_file() and "__pycache__" not in p.parts)
        return paths

    def strings(self, path):
        text = path.read_text(encoding="utf-8")
        if path.suffix != ".json":
            return [text]
        found = []
        def walk(value):
            if isinstance(value, str):
                found.append(value)
            elif isinstance(value, dict):
                for item in value.values():
                    walk(item)
            elif isinstance(value, list):
                for item in value:
                    walk(item)
        walk(json.loads(text))
        return found

    def test_no_sentence_attributes_a_quoted_phrase_to_the_owner(self):
        import re
        checked = 0
        for path in self.surfaces():
            for text in self.strings(path):
                for sentence in re.split(r"(?<=[.!?])\s+|\n\s*\n", " ".join(text.split(" "))):
                    flat = " ".join(sentence.split())
                    if "owner" in flat.casefold():
                        checked += 1
                        self.assertFalse(any(q in flat for q in self.QUOTES), f"{path.relative_to(ROOT)}: a quoted phrase in a sentence that names the owner")
        self.assertGreater(checked, 0)

    def test_the_readme_states_the_files_this_check_scans(self):
        # #1116 follow-up (d), item 6 (the GPT fix3 read's P3-5): a description of this check must keep its boundary, so the
        # README's Tests section states it, and the count it gives is the length of the list scanned here.
        import re
        readme = " ".join((ROOT / "tools" / "session-relaunch" / "README.md").read_text().split())
        stated = re.search(r"The publication check \(`PublicationSurfaces`\) scans (\d+) files: the decision record and "
                           r"every file under `tools/session-relaunch/` and `evidence/artifacts/session-relaunch-20261014/`; "
                           r"it does not scan the test module, `manifests/evidence\.json`, PR bodies or commit messages\.",
                           readme)
        self.assertIsNotNone(stated, "the README's Tests section states what PublicationSurfaces scans")
        scanned = self.surfaces()
        self.assertEqual(int(stated.group(1)), len(scanned))
        self.assertNotIn(ROOT / "tests" / "test_session_relaunch.py", scanned)
        self.assertNotIn(ROOT / "manifests" / "evidence.json", scanned)


class Units(unittest.TestCase):
    def test_the_units_run_the_installed_tool(self):
        units = ROOT / "tools" / "session-relaunch" / "units"
        roster = (units / "ns-session-roster.service").read_text()
        relaunch = (units / "ns-session-relaunch.service").read_text()
        timer = (units / "ns-session-roster.timer").read_text()
        tool = "%h/.local/share/native-agent-stack/session-relaunch/session_relaunch.py"
        self.assertIn(f"ExecStart=/usr/bin/python3 -I {tool} snapshot --config ", roster)
        self.assertIn(f"ExecStart=/usr/bin/python3 -I {tool} relaunch --config ", relaunch)
        self.assertIn("WantedBy=default.target", relaunch)
        self.assertIn("OnUnitActiveSec=60s", timer)
        # The roster must be younger than the decision's limit at a boot's end.
        self.assertLess(60 + 10, json.loads((ROOT / "tools" / "session-relaunch" / "config.example.json").read_text())[
            "max_roster_age_s"])

    def test_a_failed_relaunch_run_alerts(self):
        # The CC micro at 376f2bb9, F4: the only alert was a failed unit. OnFailure= runs the command center's stack-alert@
        # template, as adoption/templates/systemd/mineru.service does (systemd.unit(5), OnFailure=).
        relaunch = (ROOT / "tools" / "session-relaunch" / "units" / "ns-session-relaunch.service").read_text()
        unit_section = relaunch.split("[Unit]", 1)[1].split("[Service]", 1)[0]
        self.assertIn("OnFailure=stack-alert@%n.service", unit_section)

    def test_the_readme_runs_every_installed_command_through_python(self):
        readme = (ROOT / "tools" / "session-relaunch" / "README.md").read_text()
        self.assertIn('/usr/bin/python3 -I "$T/session_relaunch.py" plan-restart --config "$S/config.json"', readme)
        self.assertIn('/usr/bin/python3 -I "$T/session_relaunch.py" relaunch --reopen <name> --config "$S/config.json"', readme)
        self.assertNotIn("`session_relaunch.py plan-restart", readme)

    def test_the_evidence_readme_states_the_module_test_count(self):
        # The CC micro at 376f2bb9, F4: the evidence README said 22 tests after the module had grown to 38.
        loader = unittest.TestLoader()
        count = loader.loadTestsFromModule(sys.modules[__name__]).countTestCases()
        evidence = (ROOT / "evidence" / "artifacts" / "session-relaunch-20261014" / "README.md").read_text()
        self.assertIn(f"`python3 -m unittest tests.test_session_relaunch` ({count} tests;", evidence)

    def test_the_decision_records_a_reopen_refusal_only_where_a_state_exists(self):
        # #1116 follow-up (d), item 3 (the CC micro's P3-2): the decision said the 307f686c fix refuses with a record, with
        # no condition, while the README records such a refusal only where the ended boot's relaunch state exists.
        decision = " ".join((ROOT / "docs" / "decisions" / "2026-10-14-session-relaunch-after-wsl-restart.md").read_text()
                            .split())
        self.assertNotIn("refuses with a record", decision)
        self.assertIn("refuses a --reopen name that is not unresolved or not still to be relaunched, recording the refusal "
                      "only where the ended boot's relaunch state already exists;", decision)
        self.assertIn("records no refusal in a dry run;", decision)

    def test_the_readme_and_the_decision_cite_the_vendor_sources_of_the_three_mechanisms(self):
        # #1116 follow-up (d), item 5 (the GPT fix3 read's P3-2): the run lock, the call timeouts and the atomic replacement
        # had no pinned source. Each now cites flock(2) or the 3.14 docs of the unit's interpreter, /usr/bin/python3.
        sources = ("https://docs.python.org/3.14/library/fcntl.html#fcntl.flock",
                   "https://man7.org/linux/man-pages/man2/flock.2.html",
                   "https://docs.python.org/3.14/library/subprocess.html#subprocess.run",
                   "https://docs.python.org/3.14/library/os.html#os.replace")
        readme = " ".join((ROOT / "tools" / "session-relaunch" / "README.md").read_text().split())
        decision = " ".join((ROOT / "docs" / "decisions" / "2026-10-14-session-relaunch-after-wsl-restart.md").read_text()
                            .split())
        for name, text in (("README", readme), ("decision", decision)):
            for source in sources:
                self.assertIn(source, text, name)
        self.assertIn("If the timeout expires, the child process will be killed and waited for.", readme)
        self.assertIn("If successful, the renaming will be an atomic operation (this is a POSIX requirement).", readme)


if __name__ == "__main__":
    unittest.main()
