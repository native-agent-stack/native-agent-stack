"""tools/session-relaunch/session_relaunch.py: roster snapshots, the relaunch decision, the handoff and the tab calls.

The client and the tab opener are stand-in scripts: the stand-in `claude agents --json` prints a JSON file, and the stand-in
PowerShell records its arguments and, like a real tab, makes the launched session appear in that JSON file.
"""

import datetime as dt
import importlib.util
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
cat "$FAKE_AGENTS_JSON"
"""
FAKE_POWERSHELL = """#!/usr/bin/env python3
import json, os, sys
argv = sys.argv[1:]
with open(os.environ["FAKE_PS_LOG"], "a") as log:
    log.write(json.dumps(argv) + "\\n")
rc = int(os.environ.get("FAKE_PS_RC", "0"))
if rc == 0:
    names = json.loads(os.environ["FAKE_PS_NAMES"])
    launched = names[argv[argv.index("-Name") + 1]]
    path = os.environ["FAKE_AGENTS_JSON"]
    rows = json.load(open(path))
    rows.append({"name": launched, "kind": "interactive", "sessionId": "new", "cwd": "/w", "pid": "1", "status": "busy"})
    json.dump(rows, open(path, "w"))
    print("opened " + launched)
sys.exit(rc)
"""


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
            cc_wait_s=2, spacing_s=0, tab_attempts=2, tab_retry_pause_s=0)))
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


class Snapshot(Fixture):
    def test_writes_this_boots_roster_with_the_listed_fields(self):
        self.agents.write_text(json.dumps([dict(row("api-actions", "s1"), extra="dropped")]))
        path = R.cmd_snapshot(self.config, boot_id=THIS, sessions=R.list_sessions(self.config["claude"]), at=NOW)
        self.assertEqual(path.name, f"roster-{THIS}.json")
        doc = json.loads(path.read_text())
        self.assertEqual((doc["boot_id"], doc["written_at"]), (THIS, "2026-10-14T12:49:30Z"))
        self.assertEqual(doc["sessions"], [row("api-actions", "s1")])

    def test_a_failing_client_gives_an_empty_list(self):
        self.agents.write_text("not json")
        self.assertEqual(R.list_sessions(self.config["claude"]), [])

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

    def test_a_relaunched_boot_is_not_relaunched_again(self):
        self.crash_roster()
        R.marker(self.config, "relaunched", PREV).write_text("{}")
        self.assertIn("already relaunched", self.decide()["reason"])

    def test_a_roster_older_than_the_limit_at_the_boot_end_relaunches_nothing(self):
        self.roster(PREV, END - dt.timedelta(seconds=301), [row("trading-cc", "s")])
        self.assertIn("does not show who was alive", self.decide()["reason"])

    def test_the_relaunch_count_is_capped_in_the_window(self):
        self.crash_roster()
        for i in range(3):
            R.marker(self.config, "relaunched", f"{i:032x}").write_text(json.dumps({"started_at": R.iso(NOW)}))
        self.assertIn("relaunches already", self.decide()["reason"])
        R.marker(self.config, "relaunched", f"{0:032x}").write_text(json.dumps({"started_at": "2026-10-13T00:00:00Z"}))
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
    def run_relaunch(self, dry_run=False):
        return R.cmd_relaunch(self.config, boot_id=THIS, at=NOW, boots=BOOTS, dry_run=dry_run)

    def test_writes_a_sealed_handoff_and_opens_the_tabs_in_order(self):
        self.crash_roster()
        result = self.run_relaunch()
        handoff = Path(result["receipt"]["handoff"])
        self.assertEqual(handoff.parent, Path(self.config["handoff_dir"]))
        self.assertEqual(handoff.name, "AUTO-RESTART-20261014T124930Z.md")
        self.assertEqual(stat.S_IMODE(handoff.stat().st_mode), 0o444)
        calls = self.ps_calls()
        self.assertEqual([c[c.index("-Name") + 1] for c in calls], ["cc", "trading-cc", "coop"])
        for call in calls:
            self.assertEqual(call[call.index("-File") + 1], self.config["tab_opener"])
            self.assertEqual(call[call.index("-Handoff") + 1], str(handoff))
        receipt = json.loads(R.marker(self.config, "relaunched", PREV).read_text())
        self.assertEqual([t["rc"] for t in receipt["tabs"]], [0, 0, 0])
        self.assertTrue(receipt["tabs"][0]["cc_listed"])
        import hashlib
        self.assertEqual(receipt["handoff_sha256"], hashlib.sha256(handoff.read_bytes()).hexdigest())
        self.assertEqual(self.run_relaunch()["action"], "none")
        self.assertEqual(len(self.ps_calls()), 3)

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
        self.assertFalse(R.marker(self.config, "relaunched", PREV).exists())
        self.assertFalse(Path(self.config["handoff_dir"]).exists())

    def test_a_failing_tab_is_retried_recorded_and_the_rest_still_open(self):
        self.crash_roster()
        os.environ["FAKE_PS_RC"] = "1"
        result = self.run_relaunch()
        tabs = result["receipt"]["tabs"]
        self.assertEqual([t["rc"] for t in tabs], [1, 1, 1])
        self.assertEqual([len(t["attempts"]) for t in tabs], [2, 2, 2])
        self.assertNotIn("cc_listed", tabs[0])
        self.assertEqual(len(self.ps_calls()), 6)


class CommandLine(Fixture):
    def test_plan_restart_marks_this_boot(self):
        done = subprocess.run([sys.executable, "-I", str(TOOL), "plan-restart", "--config", str(self.tmp / "config.json")],
                              capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        doc = json.loads(Path(done.stdout.strip()).read_text())
        self.assertEqual(doc["boot_id"], R.current_boot_id())

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


if __name__ == "__main__":
    unittest.main()
