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
import stat
import subprocess
import sys
import tempfile
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
if os.environ.get("FAKE_PS_LAUNCH", "1" if rc == 0 else "0") == "1":
    names = json.loads(os.environ["FAKE_PS_NAMES"])
    launched = names[argv[argv.index("-Name") + 1]]
    path = os.environ["FAKE_AGENTS_JSON"]
    rows = json.load(open(path))
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


if __name__ == "__main__":
    unittest.main()
