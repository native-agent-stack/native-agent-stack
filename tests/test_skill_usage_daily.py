"""Counts-only daily native reports and rendered timer, with no live clients."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import stat
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/skill-usage"))
import skill_usage as usage


def daily_module():
    spec = importlib.util.spec_from_file_location("daily_skill_usage", ROOT / "tools/skill-usage/daily_skill_usage.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PluginUsageTests(unittest.TestCase):
    def test_native_plugin_namespace_is_joined_to_its_trial_name(self):
        manifest = usage.load_manifest(ROOT / "tests/fixtures/skill_usage/manifest.json")
        skill = dict(manifest["skills"][0], name="claude-api", claude_skill_name="claude-api:claude-api", codex_enabled=False)
        manifest["skills"] = [skill]
        report = usage.build_report(manifest, claude={"rows": {"claude-api:claude-api": {
            "uses": 3, "context_tokens": 10, "last_used": "today"}}},
            codex_scan=usage.scan_codex_roots([], ["claude-api"], now=usage.parse_iso("2026-10-11T00:00:00Z"),
                                              windows=[7, 30]),
            lock_installed_at={"claude-api": "2026-10-10T00:00:00Z"},
            now=usage.parse_iso("2026-10-11T00:00:00Z"), windows=[7])
        self.assertEqual(3, report["skills"][0]["claude"]["uses"])
        self.assertEqual(1, report["skills"][0]["age_days"])


class TwinListingUsageTests(unittest.TestCase):
    """CPA-V-07: a skill that a plugin and another copy both deliver is listed under two names in the /skill-doctor table, and a use of either is a use of the skill."""

    ROWS = {"typesafe:typesafe-ai": {"source": "plugin", "context_tokens": 100, "tokens_7d": None, "uses": 2, "last_used": "1 day"},
            "typesafe-ai": {"source": "userSettings", "context_tokens": 90, "tokens_7d": None, "uses": 3, "last_used": "3 days"}}

    def skill(self, **extra):
        return {"name": "typesafe-ai", "claude_plugin": "typesafe@typesafe-ai", "claude_skill_name": "typesafe:typesafe-ai", **extra}

    def test_both_listings_are_one_row_with_the_uses_added(self):
        row = usage.claude_row(self.skill(), self.ROWS)
        self.assertEqual((row["uses"], row["context_tokens"], row["last_used"]), (5, 190, "1 day"))

    def test_one_listing_is_that_row_and_none_is_none(self):
        self.assertEqual(usage.claude_row(self.skill(), {"typesafe-ai": self.ROWS["typesafe-ai"]}), self.ROWS["typesafe-ai"])
        self.assertEqual(usage.claude_row(self.skill(), {"typesafe:typesafe-ai": self.ROWS["typesafe:typesafe-ai"]}), self.ROWS["typesafe:typesafe-ai"])
        self.assertIsNone(usage.claude_row(self.skill(), {}))

    def test_the_last_use_is_that_of_the_listing_that_was_used(self):
        rows = {name: dict(row, uses=0, last_used="never") for name, row in self.ROWS.items()}
        rows["typesafe-ai"]["uses"], rows["typesafe-ai"]["last_used"] = 4, "today"
        self.assertEqual(usage.claude_row(self.skill(), rows)["last_used"], "today")
        self.assertEqual(usage.claude_row(self.skill(), {name: dict(row, uses=0, last_used="never") for name, row in self.ROWS.items()})["last_used"], "never")

    def test_the_combined_last_use_is_the_most_recent_of_the_listings_that_were_used_whichever_is_listed_first(self):
        """Astra's read of 2dae9751 (P2): the combined row took the first used listing's date, the plugin's, so a plugin used 7 days ago and a personal copy used an hour ago reported 7 days ago. The cells say how long
        ago (Claude Code 2.1.296 prints never, today and N day(s); older tables N days ago and N hours ago), so they are put in order; the most recent wins whichever listing carries it, for both kinds of twin."""
        twins = (("a personal twin", self.skill(), "typesafe:typesafe-ai", "typesafe-ai"),
                 ("a bundled twin", {"name": "claude-api", "native_plugin": "claude-api@market", "claude_skill_name": "claude-api:claude-api", "bundled_twin": "claude-api"}, "claude-api:claude-api", "claude-api"))
        cases = ((("7 days ago", "1 hour ago"), "1 hour ago"), (("1 hour ago", "7 days ago"), "1 hour ago"), (("3 days", "1 day"), "1 day"), (("1 day", "3 days"), "1 day"), (("today", "2 days"), "today"),
                 (("2 days", "today"), "today"), (("30 minutes ago", "2 hours ago"), "30 minutes ago"), (("1 week ago", "6 days ago"), "6 days ago"), (("2 days", "2 days"), "2 days"))
        for label, skill, plugin_name, other_name in twins:
            for (plugin_cell, other_cell), expected in cases:
                with self.subTest(twin=label, plugin=plugin_cell, other=other_cell):
                    rows = {plugin_name: {"source": "plugin", "context_tokens": 10, "tokens_7d": None, "uses": 2, "last_used": plugin_cell},
                            other_name: {"source": "userSettings", "context_tokens": 10, "tokens_7d": None, "uses": 3, "last_used": other_cell}}
                    self.assertEqual(usage.claude_row(skill, rows)["last_used"], expected)

    def test_a_listing_that_was_not_used_does_not_count_and_one_that_cannot_be_put_in_order_makes_the_date_unknown(self):
        rows = {name: dict(row) for name, row in self.ROWS.items()}
        rows["typesafe:typesafe-ai"].update(uses=0, last_used="never")
        self.assertEqual(usage.claude_row(self.skill(), rows)["last_used"], "3 days", "the listing never used is no use")
        rows["typesafe:typesafe-ai"].update(uses=2, last_used="Oct 12")
        self.assertIsNone(usage.claude_row(self.skill(), rows)["last_used"], "an absolute date cannot be compared with a relative one: unknown, not the plugin's date")
        rows["typesafe:typesafe-ai"].update(last_used="2 months ago")
        self.assertIsNone(usage.claude_row(self.skill(), rows)["last_used"], "a month has no fixed length")
        rows["typesafe:typesafe-ai"].update(uses=0, last_used="never")
        rows["typesafe-ai"].update(uses=3, last_used="Oct 12")
        self.assertEqual(usage.claude_row(self.skill(), rows)["last_used"], "Oct 12", "one used listing: its own cell, whether or not it can be put in order")
        rows["typesafe-ai"].update(uses=0, last_used="never")
        self.assertEqual(usage.claude_row(self.skill(), rows)["last_used"], "never")
        self.assertEqual([usage.last_used_age_seconds(cell) for cell in ("today", "1 day", "2 days ago", "3 hours", "1 week", "never", "Oct 12", "", None)], [0, 86400, 172800, 10800, 604800, None, None, None, None])

    def test_a_row_without_a_twin_ignores_a_same_name_row(self):
        skill = {"name": "typesafe-ai"}
        self.assertEqual(usage.claude_row(skill, self.ROWS), self.ROWS["typesafe-ai"])

    def test_a_listing_named_twice_is_one_listing(self):
        skill = {"name": "x", "claude_skill_name": "x", "bundled_twin": "x", "native_plugin": "x@m"}
        rows = {"x": {"source": "plugin", "context_tokens": 7, "tokens_7d": None, "uses": 2, "last_used": "1 day"}}
        self.assertEqual(usage.claude_row(skill, rows), rows["x"])

    def test_an_unknown_context_stays_unknown_and_a_window_the_rows_hold_is_dropped(self):
        rows = {name: dict(row, context_tokens=None, tokens_7d=5) for name, row in self.ROWS.items()}
        combined = usage.claude_row(self.skill(), rows)
        self.assertIsNone(combined["context_tokens"])
        self.assertIsNone(combined["tokens_7d"])
        self.assertEqual(combined["uses"], 5)

    def test_the_bundled_twin_of_a_native_plugin_row_is_added_too(self):
        skill = {"name": "claude-api", "native_plugin": "claude-api@market", "claude_skill_name": "claude-api:claude-api", "bundled_twin": "claude-api"}
        rows = {"claude-api:claude-api": {"source": "plugin", "context_tokens": 50, "tokens_7d": None, "uses": 1, "last_used": "1 day"},
                "claude-api": {"source": "bundled", "context_tokens": 40, "tokens_7d": None, "uses": 6, "last_used": "5 days"}}
        self.assertEqual(usage.claude_row(skill, rows)["uses"], 7)

    def test_the_report_counts_the_uses_of_both_listings(self):
        manifest = usage.load_manifest(ROOT / "tests/fixtures/skill_usage/manifest.json")
        manifest["skills"] = [dict(manifest["skills"][0], **self.skill(), codex_enabled=False)]
        report = usage.build_report(manifest, claude={"rows": self.ROWS}, codex_scan=usage.scan_codex_roots([], ["typesafe-ai"], now=usage.parse_iso("2026-10-11T00:00:00Z"), windows=[7]),
                                    lock_installed_at={"typesafe-ai": "2026-10-10T00:00:00Z"}, now=usage.parse_iso("2026-10-11T00:00:00Z"), windows=[7])
        self.assertEqual(report["skills"][0]["claude"]["uses"], 5)


class CodexUseTests(unittest.TestCase):
    def test_duplicate_rollout_parts_share_one_session_skill_use(self):
        now = usage.parse_iso("2026-10-10T00:00:00Z")
        rows = [{"type": "session_meta", "payload": {"id": "synthetic-session"}},
                {"timestamp": "2026-10-09T23:00:00Z", "type": "response_item", "payload": {
                    "type": "function_call", "name": "exec_command", "arguments": json.dumps({"cmd": "/fixture/gh-fix-ci/SKILL.md"})}}]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for index in range(2):
                (root / f"rollout-part-{index}.jsonl").write_text("\n".join(map(json.dumps, rows)))
            scan = usage.scan_codex_roots([root], ["gh-fix-ci"], now=now, windows=[7])
            self.assertEqual(2, scan["counts"]["gh-fix-ci"][7]["skill_md_reads"])
            self.assertEqual(1, scan["uses"]["gh-fix-ci"][7])

    def test_bulk_scan_inflates_raw_reads_but_not_once_per_session_use(self):
        names = ["gh-fix-ci", "typesafe-ai", *["document-" + str(i) for i in range(50)]]
        now = usage.parse_iso("2026-10-10T00:00:00Z")
        def record(payload):
            return {"timestamp": "2026-10-09T23:00:00Z", "type": "response_item", "payload": payload}
        def call(text):
            return record({"type": "function_call", "name": "exec_command", "arguments": json.dumps({"cmd": text})})
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            bulk = " ".join("/fixture/" + name + "/SKILL.md" for name in names)
            (root / "rollout-bulk.jsonl").write_text("\n".join(json.dumps(r) for r in [call(bulk), call(bulk)]))
            scan = usage.scan_codex_roots([root], names, now=now, windows=[7])
            self.assertEqual(2, scan["counts"]["gh-fix-ci"][7]["skill_md_reads"])
            self.assertEqual(0, scan["uses"]["gh-fix-ci"][7])
            normal = [call("/fixture/gh-fix-ci/SKILL.md")] * 3 + [record({"type": "message", "role": "user",
                      "content": [{"type": "input_text", "text": "$gh-fix-ci and $typesafe-ai"}]})]
            (root / "rollout-normal.jsonl").write_text("\n".join(json.dumps(r) for r in normal))
            scan = usage.scan_codex_roots([root], names, now=now, windows=[7])
            self.assertEqual(5, scan["counts"]["gh-fix-ci"][7]["skill_md_reads"])
            self.assertEqual(1, scan["uses"]["gh-fix-ci"][7])
            self.assertEqual(1, scan["uses"]["typesafe-ai"][7])


class DailyProjectionTests(unittest.TestCase):
    def test_absent_codex_root_is_unknown_in_projection(self):
        daily = daily_module()
        host = {"kind": "skill_invoke_rate_report", "codex": {
                    "measured": True, "roots_count": 1, "files_scanned": 0},
                "skills": [{"name": "gh-fix-ci", "codex": {"use_counts": {"7": 0},
                           "counts": {"7": {"skill_md_reads": 0, "name_mentions": 0}}}}],
                "codex_use_groups": {"7": {"workers": {"gh-fix-ci": 0}}}}
        codex = {"kind": "codex_lane_usage_report", "roots_count": 1, "files_scanned": 0,
                 "groups": {"workers": {"sessions": 0, "skill_md_reads": {"gh-fix-ci": 0}}}}
        report = daily.project_reports(host, codex, None, now="2026-10-11T00:00:00Z", window=7)
        self.assertFalse(report["measured"]["codex"])
        self.assertIsNone(report["host"][0]["codex_use"])
        self.assertIsNone(report["lanes"][0]["skills"][0]["count"])
        self.assertEqual([], report["zero_use"]["codex"])
        host["codex"]["files_scanned"] = 1
        report = daily.project_reports(host, codex, None, now="2026-10-11T00:00:00Z", window=7)
        self.assertTrue(report["measured"]["codex"])
        self.assertEqual(0, report["host"][0]["codex_use"])
        self.assertEqual(["gh-fix-ci"], report["zero_use"]["codex"])

    def test_groups_keep_names_and_counts_and_unknown_is_not_zero(self):
        daily = daily_module()
        host = {"kind": "skill_invoke_rate_report", "codex": {"measured": True, "roots_count": 1, "files_scanned": 1},
                "skills": [{"name": "gh-fix-ci", "claude": {"uses": 0},
                "codex": {"counts": {"7": {"skill_md_reads": 4, "name_mentions": 1}}, "use_counts": {"7": 1}}, "prompt": "PRIVATE"}],
                "codex_use_groups": {"7": {"workers": {"gh-fix-ci": 1}, "workers_by_role": {"worker": {"gh-fix-ci": 1}}}}}
        codex = {"kind": "codex_lane_usage_report", "groups": {"workers": {"sessions": 2,
                 "skill_md_reads": {"gh-fix-ci": 4, "bad/account": 99}}, "workers_by_role": {
                 "worker": {"sessions": 2, "skill_md_reads": {"gh-fix-ci": 4}}}}}
        claude = {"kind": "claude_child_lane_usage", "groups": {"by_spawn_and_agent_type": {
                  "workflow": {"security-reviewer": {"children": 1, "skill_calls": {"security-audit": 2}}}}},
                  "main": {"skill_calls": {}}, "actors": [{"prompt": "PRIVATE", "path": "/private/credential"}]}
        report = daily.project_reports(host, codex, claude, now="2026-10-10T00:00:00Z", window=7)
        self.assertEqual(1, report["lanes"][0]["skills"][0]["count"])
        self.assertEqual(4, report["lanes"][0]["skills"][0]["raw_reads"])
        self.assertTrue(any(row["lane"] == "workflow:security-reviewer" and row["skills"][0]["count"] == 2
                            for row in report["lanes"]))
        self.assertNotIn("PRIVATE", json.dumps(report))
        self.assertNotIn("bad/account", json.dumps(report))
        self.assertNotIn("credential", json.dumps(report))
        unknown = daily.project_reports(None, None, None, now="2026-10-10T00:00:00Z", window=7)
        self.assertIsNone(unknown["host"])
        self.assertIsNone(unknown["lanes"])

    def test_each_half_runs_only_its_own_clients_native_commands(self):
        daily = daily_module()
        for half, roots, expected in (("claude", [Path("/fixture/claude")], ("--run-skill-doctor", "--lanes-sweep")), ("codex", [Path("/fixture/codex")], ("--codex-root", "--lanes"))):
            commands = []

            def runner(command, **kwargs):
                commands.append((command, kwargs))
                return subprocess.CompletedProcess(command, 1, "", "")
            daily.collect_half(half, roots, window=7, now=usage.parse_iso("2026-10-10T00:00:00Z"), runner=runner)
            with self.subTest(half=half):
                self.assertEqual(2, len(commands))
                joined = [" ".join(command) for command, _ in commands]
                self.assertIn(expected[0], joined[0])
                self.assertIn(expected[1], joined[1])
                self.assertIn("--window", commands[0][0])
                self.assertIn("--since", commands[1][0])
                flag = "--root" if half == "claude" else "--codex-root"
                self.assertEqual([command[command.index(flag) + 1] for command, _ in commands[(1 if half == "claude" else 0):] if flag in command], [str(roots[0])] * (1 if half == "claude" else 2),
                                 "the client's own root reaches the commands that read it")
                other = ("--codex-root", "--lanes ") if half == "claude" else ("--run-skill-doctor", "--lanes-sweep", "--claude-timeout")
                for text in joined:
                    for word in other:
                        self.assertNotIn(word, text, f"the {half} half must not run the other client's command")
        with self.assertRaises(ValueError):
            daily.collect_half("both", [], window=7, now=usage.parse_iso("2026-10-10T00:00:00Z"))

    def test_timer_render_targets_the_selected_live_clone(self):
        daily = daily_module()
        with tempfile.TemporaryDirectory() as temp:
            dest = Path(temp)
            daily.render_units(dest, Path("/fixture/live clone"), Path(sys.executable), Path("/fixture/bin/node"))
            self.assertEqual(sorted(path.name for path in dest.iterdir()), sorted(daily.UNIT_FILES))
            for half, other, root in (("claude", "codex", "--claude-root"), ("codex", "claude", "--codex-root")):
                service = (dest / f"skill-invoke-rate-{half}.service").read_text()
                timer = (dest / f"skill-invoke-rate-{half}.timer").read_text()
                self.assertIn('"/fixture/live clone/tools/skill-usage/daily_skill_usage.py"', service)
                self.assertIn(f"--half {half} ", service)
                self.assertIn(root, service)
                self.assertNotIn(f"--{other}-root", service, "a half is given only the root of its own client")
                self.assertIn(f"Unit=skill-invoke-rate-{half}.service", timer)
                self.assertNotIn("@REPOSITORY@", service)

    @unittest.skipUnless(shutil.which("systemd-analyze"), "native systemd verifier unavailable")
    def test_native_user_unit_verification_needs_no_session_or_install(self):
        daily = daily_module()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runtime = root / "runtime"
            runtime.mkdir(mode=0o700)
            daily.render_units(root, ROOT, Path(sys.executable), Path(shutil.which("node")))
            result = subprocess.run([shutil.which("systemd-analyze"), "--user", "--man=no", "verify", *[str(root / name) for name in daily.UNIT_FILES]],
                                    env={"HOME": str(root), "PATH": os.defpath, "XDG_RUNTIME_DIR": str(runtime)},
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertFalse((root / ".config/systemd/user").exists())


FLEET = importlib.util.spec_from_file_location("local_pages_fleet_data", ROOT / "tools/local-pages/fleet_data.py")
fleet_data = importlib.util.module_from_spec(FLEET)
FLEET.loader.exec_module(fleet_data)
NOW = "2026-10-12T10:00:00+00:00"


def claude_reports():
    host = {"kind": "skill_invoke_rate_report", "claude": {"measured": True}, "codex": {"measured": False, "roots_count": 0, "files_scanned": 0},
            "skills": [{"name": "gh-fix-ci", "claude": {"uses": 2}, "codex": {}}, {"name": "typesafe-ai", "claude": {"uses": 0}, "codex": {}}], "codex_use_groups": {}}
    lanes = {"kind": "claude_child_lane_usage", "groups": {"by_spawn_and_agent_type": {"workflow": {"security-reviewer": {"children": 1, "skill_calls": {"gh-fix-ci": 2}}}}}, "main": {"skill_calls": {}}}
    return host, None, lanes


def codex_reports():
    host = {"kind": "skill_invoke_rate_report", "claude": {"measured": False}, "codex": {"measured": True, "roots_count": 1, "files_scanned": 3},
            "skills": [{"name": "gh-fix-ci", "claude": {}, "codex": {"counts": {"7": {"skill_md_reads": 4, "name_mentions": 1}}, "use_counts": {"7": 1}}},
                       {"name": "typesafe-ai", "claude": {}, "codex": {"counts": {"7": {"skill_md_reads": 0, "name_mentions": 0}}, "use_counts": {"7": 0}}}],
            "codex_use_groups": {"7": {"workers": {"gh-fix-ci": 1, "typesafe-ai": 0}}}}
    lanes = {"kind": "codex_lane_usage_report", "groups": {"workers": {"sessions": 2, "skill_md_reads": {"gh-fix-ci": 4, "typesafe-ai": 0}}}}
    return host, lanes, None


class HalvesTests(unittest.TestCase):
    """CPA-C-002 (Claude-family practice audit, 2026-10-12): the daily record is two units, one per client, each with its own record and limits, so a slow Codex scan (25 min 47 s measured) never leaves the
    Claude half (about 2.5 minutes) unmeasured and a timeout marks only its own half."""

    def projected(self, half):
        daily = daily_module()
        host, codex, claude = claude_reports() if half == "claude" else codex_reports()
        return daily.project_reports(host, codex, claude, now=NOW, window=7, half=half)

    def test_a_half_is_measured_by_its_own_keys_only(self):
        self.assertEqual(self.projected("claude")["measured"], {"host": True, "claude": True})
        self.assertEqual(self.projected("codex")["measured"], {"codex": True})
        daily = daily_module()
        self.assertEqual(sorted(daily.project_reports(None, None, None, now=NOW, window=7)["measured"]), ["claude", "codex", "host"], "a combined projection keeps all three keys")
        self.assertEqual(self.projected("claude")["half"], "claude")
        unmeasured = daily.project_reports(None, None, None, now=NOW, window=7, half="codex")
        self.assertEqual(unmeasured["measured"], {"codex": False})

    def test_a_slow_codex_half_leaves_the_claude_half_measured_and_a_timeout_marks_only_its_own_half(self):
        daily = daily_module()
        now = usage.parse_iso("2026-10-12T10:00:00Z")
        host, _, lanes = claude_reports()
        codex_host, codex_lanes, _ = codex_reports()

        def runner_for(slow):
            def runner(command, **kwargs):
                if slow in " ".join(command):
                    raise subprocess.TimeoutExpired(command, kwargs["timeout"])
                key = next((flag for flag in ("--run-skill-doctor", "--lanes-sweep", "--lanes") if flag in command), None)
                payload = {"--run-skill-doctor": host, "--lanes-sweep": lanes, "--lanes": codex_lanes}.get(key, codex_host)
                return subprocess.CompletedProcess(command, 0, json.dumps(payload), "")
            return runner
        reports = daily.collect_half("codex", [Path("/fixture/codex")], window=7, now=now, runner=runner_for("--lanes"))
        record = daily.project_reports(*reports, now=now.isoformat(), window=7, half="codex")
        self.assertEqual(record["measured"], {"codex": False}, "the lanes scan timed out: the Codex half is unmeasured")
        reports = daily.collect_half("claude", [Path("/fixture/claude")], window=7, now=now, runner=runner_for("--lanes "))
        record = daily.project_reports(*reports, now=now.isoformat(), window=7, half="claude")
        self.assertEqual(record["measured"], {"host": True, "claude": True}, "the Claude half does not run the Codex scan, so it is measured however long that takes")
        reports = daily.collect_half("claude", [Path("/fixture/claude")], window=7, now=now, runner=runner_for("--run-skill-doctor"))
        record = daily.project_reports(*reports, now=now.isoformat(), window=7, half="claude")
        self.assertEqual(record["measured"], {"host": False, "claude": True}, "a capture timeout leaves the sweep measured")

    def test_every_command_has_its_own_limit_and_the_codex_scan_gets_twice_its_measured_wall(self):
        daily = daily_module()
        now = usage.parse_iso("2026-10-12T10:00:00Z")
        seen = {}

        def runner(command, **kwargs):
            seen[" ".join(command)] = kwargs["timeout"]
            return subprocess.CompletedProcess(command, 1, "", "")
        for half, roots in (("claude", [Path("/fixture/claude")]), ("codex", [Path("/fixture/codex")])):
            daily.collect_half(half, roots, window=7, now=now, runner=runner)
        limits = {("lanes-sweep" if "--lanes-sweep" in key else "lanes" if "--lanes " in key else "capture" if "--run-skill-doctor" in key else "codex-host"): value for key, value in seen.items()}
        self.assertEqual(sorted(limits), ["capture", "codex-host", "lanes", "lanes-sweep"])
        self.assertEqual(limits["capture"], usage.DEFAULT_CLAUDE_TIMEOUT + daily.CAPTURE_MARGIN)
        self.assertEqual(limits["lanes-sweep"], daily.TIMEOUTS["claude_sweep"])
        self.assertEqual(limits["codex-host"], daily.TIMEOUTS["codex_host"])
        self.assertEqual(limits["lanes"], daily.TIMEOUTS["codex_lanes"])
        self.assertGreaterEqual(daily.TIMEOUTS["codex_lanes"], 2 * (25 * 60 + 47), "twice the 25 min 47 s measured for the Codex lanes scan on 2026-10-12")
        self.assertGreaterEqual(daily.TIMEOUTS["claude_sweep"], 4 * 138, "four times the 2 min 18 s measured for the Claude lanes sweep")
        self.assertGreaterEqual(daily.TIMEOUTS["codex_host"], 2 * 71, "twice the wall measured for the host report's Codex scan")

    def test_the_combined_record_is_what_the_fleet_page_reads_from_the_newest_record_of_each_half(self):
        daily = daily_module()
        claude, codex = self.projected("claude"), self.projected("codex")
        codex["generated_at"] = "2026-10-12T09:00:00+00:00"
        combined = daily.merge_halves(claude, codex)
        self.assertEqual(combined["schema"], "skill-invoke-rate-daily/1")
        self.assertEqual(combined["measured"], {"host": True, "codex": True, "claude": True})
        self.assertEqual(combined["generated_at"], "2026-10-12T09:00:00+00:00", "the page never shows a stale half as fresh: the older of the two")
        rows = {row["name"]: row for row in combined["host"]}
        self.assertEqual((rows["gh-fix-ci"]["claude_uses_lifetime"], rows["gh-fix-ci"]["codex_use"], rows["gh-fix-ci"]["codex_skill_md_reads"]), (2, 1, 4))
        self.assertEqual(combined["zero_use"], {"codex": ["typesafe-ai"], "claude_host_lifetime": ["typesafe-ai"]})
        self.assertEqual({(lane["client"], lane["lane"]) for lane in combined["lanes"]}, {("claude", "workflow:security-reviewer"), ("claude", "main"), ("codex", "workers")})
        page = fleet_data._skill_usage(json.loads(json.dumps(combined)))
        self.assertEqual(page["measured"], {"host": True, "codex": True, "claude": True})
        self.assertEqual([row["name"] for row in page["host"]], ["gh-fix-ci", "typesafe-ai"])
        self.assertEqual(len(page["lanes"]), 3)

    def test_a_missing_or_foreign_half_contributes_nothing_and_is_not_measured(self):
        daily = daily_module()
        only_claude = daily.merge_halves(self.projected("claude"), None)
        self.assertEqual(only_claude["measured"], {"host": True, "codex": False, "claude": True})
        self.assertIsNone(only_claude["halves"]["codex"])
        self.assertTrue(all(row["codex_use"] is None for row in only_claude["host"]))
        wrong = daily.merge_halves(self.projected("codex"), self.projected("claude"))
        self.assertEqual(wrong["measured"], {"host": False, "codex": False, "claude": False}, "a record is taken only as the half it says it is")
        self.assertIsNone(wrong["host"])
        nothing = daily.merge_halves(None, None)
        self.assertEqual((nothing["measured"], nothing["host"], nothing["lanes"], nothing["generated_at"]), ({"host": False, "codex": False, "claude": False}, None, None, None))
        self.assertIsNotNone(fleet_data._skill_usage(json.loads(json.dumps(nothing))))
        other_schema = dict(self.projected("claude"), schema="skill-invoke-rate-daily/2")
        self.assertEqual(daily.merge_halves(other_schema, None)["measured"], {"host": False, "codex": False, "claude": False}, "a record of another schema is not read")
        injected = self.projected("codex")
        injected["lanes"] = [*injected["lanes"], {"client": "claude", "lane": "main", "skills": []}]
        self.assertEqual([(lane["client"], lane["lane"]) for lane in daily.merge_halves(None, injected)["lanes"]], [("codex", "workers")], "a half contributes only the lanes of its own client")

    def test_report_files_project_a_combined_record_and_leave_the_combined_file_alone(self):
        daily = daily_module()
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            host = directory / "host.json"
            host.write_text(json.dumps(claude_reports()[0]))
            combined = directory / "combined.json"
            with contextlib.redirect_stdout(io.StringIO()):
                code = daily.main(["--host-report", str(host), "--now", NOW, "--combined-out", str(combined), "--out", str(directory / "all.json")])
            self.assertEqual(code, 1, "the Codex and Claude lanes keys are unmeasured")
            self.assertFalse(combined.exists(), "only a collecting half refreshes the combined record")
            self.assertEqual(json.loads((directory / "all.json").read_text())["half"], "all")

    def run_half(self, half, directory, *extra):
        daily = daily_module()
        reports = claude_reports() if half == "claude" else codex_reports()
        root = "--claude-root" if half == "claude" else "--codex-root"
        argv = ["--half", half, root, "/fixture/root", "--now", NOW, "--out", str(directory / f"{half}.json"), *extra]
        errors = io.StringIO()
        with mock.patch.object(daily, "require_reviewed_main"), mock.patch.object(daily, "collect_half", return_value=reports), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(errors):
            code = daily.main(argv)
        return code, errors.getvalue()

    def test_a_half_publishes_its_record_then_refreshes_the_combined_one_from_the_other_halfs_newest(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            combined, other = directory / "combined.json", directory / "codex.json"
            code, _ = self.run_half("codex", directory)
            self.assertEqual(code, 0)
            code, errors = self.run_half("claude", directory, "--combined-out", str(combined), "--other-record", str(other))
            self.assertEqual((code, errors), (0, ""))
            data = json.loads(combined.read_text())
            self.assertEqual(data["measured"], {"host": True, "codex": True, "claude": True})
            self.assertEqual(sorted(data["halves"]), ["claude", "codex"])
            self.assertEqual(json.loads((directory / "claude.json").read_text())["half"], "claude")
            self.assertEqual(stat.S_IMODE(combined.stat().st_mode) & 0o077, 0, "a record is private to the account")

    def test_a_combined_record_that_cannot_be_refreshed_never_changes_the_halfs_exit_status(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            (directory / "garbage.json").write_text("{not json")
            code, errors = self.run_half("claude", directory, "--combined-out", str(directory / "combined.json"), "--other-record", str(directory / "garbage.json"))
            self.assertEqual((code, errors), (0, ""))
            self.assertEqual(json.loads((directory / "combined.json").read_text())["measured"], {"host": True, "codex": False, "claude": True}, "an unreadable record is an absent half")
            inside = ROOT / "combined-inside-the-worktree.json"
            code, errors = self.run_half("claude", directory, "--combined-out", str(inside))
            self.assertEqual(code, 0, "the half is measured; the combined record is a convenience")
            self.assertIn("combined record was not refreshed", errors)
            self.assertFalse(inside.exists())

    def test_a_half_needs_the_root_of_its_own_client_and_a_live_run_needs_a_half(self):
        daily = daily_module()
        with mock.patch.object(daily, "require_reviewed_main"), mock.patch.object(daily, "collect_half", return_value=(None, None, None)) as collect, \
                contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(daily.main(["--half", "claude", "--claude-root", "/fixture/claude"]), 1, "unmeasured: exit 1, not 2")
            self.assertEqual(collect.call_args.args[:2], ("claude", [Path("/fixture/claude")]))
            self.assertEqual(daily.main(["--half", "codex", "--codex-root", "/fixture/codex"]), 1)
            self.assertEqual(collect.call_args.args[:2], ("codex", [Path("/fixture/codex")]))
            collect.reset_mock()
            self.assertEqual(daily.main(["--half", "claude", "--codex-root", "/fixture/codex"]), 2, "the Claude half is given the Claude root")
            self.assertEqual(daily.main(["--half", "codex", "--claude-root", "/fixture/claude"]), 2)
            self.assertEqual(daily.main(["--codex-root", "/fixture/codex", "--claude-root", "/fixture/claude"]), 2, "a live run names its half")
            collect.assert_not_called()

    def test_each_units_start_timeout_exceeds_the_sum_of_its_halfs_command_limits(self):
        daily = daily_module()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            daily.render_units(root, Path("/fixture/live"), Path(sys.executable), Path("/fixture/bin/node"))
            for half in daily.HALVES:
                service = (root / f"skill-invoke-rate-{half}.service").read_text()
                line = next(line for line in service.splitlines() if line.startswith("TimeoutStartSec="))
                number, unit = re.fullmatch(r"TimeoutStartSec=(\d+)(min|s)", line).groups()
                seconds = int(number) * (60 if unit == "min" else 1)
                with self.subTest(half=half):
                    self.assertGreater(seconds, daily.half_budget(half), "a unit that is stopped before its commands may finish marks the half unmeasured for nothing")
                    self.assertLessEqual(seconds, daily.half_budget(half) + 120, "a minute or two of margin, not so long that a hung scan holds the unit all day")

    def test_the_two_units_are_staggered_at_a_quiet_hour_and_write_distinct_records(self):
        daily = daily_module()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            daily.render_units(root, Path("/fixture/live"), Path(sys.executable), Path("/fixture/bin/node"))
            texts = {half: (root / f"skill-invoke-rate-{half}.service").read_text() for half in daily.HALVES}
            timers = {half: (root / f"skill-invoke-rate-{half}.timer").read_text() for half in daily.HALVES}
            outs = {half: re.search(r"--out (\S+)", texts[half]).group(1) for half in daily.HALVES}
            self.assertEqual(len(set(outs.values())), 2)
            combined = {re.search(r"--combined-out (\S+)", text).group(1) for text in texts.values()}
            self.assertEqual(len(combined), 1)
            self.assertTrue(next(iter(combined)).endswith("/skill-invoke-rate-latest.json"), "the file the Fleet page reads")
            self.assertIn("skill-invoke-rate-latest.json", (ROOT / "tools/local-pages/fleet_data.py").read_text())
            for half, other in (("claude", "codex"), ("codex", "claude")):
                self.assertEqual(re.search(r"--other-record (\S+)", texts[half]).group(1), outs[other])
            calendars = {half: re.search(r"OnCalendar=(.*)", timers[half]).group(1) for half in daily.HALVES}
            self.assertEqual(len(set(calendars.values())), 2, "staggered: the Claude half is over long before the Codex half starts")
            for calendar in calendars.values():
                self.assertTrue(calendar.endswith(" UTC"), "the hour is stated in UTC, not in the host's zone")
                self.assertRegex(calendar, r"\b(0[89]|1[0-2]):\d\d:00 UTC$", "inside the quietest span of the host's load by hour (08:00 to 13:00 UTC)")
            if shutil.which("systemd-analyze"):
                for calendar in calendars.values():
                    done = subprocess.run([shutil.which("systemd-analyze"), "calendar", calendar], capture_output=True, text=True, timeout=30)
                    self.assertEqual(done.returncode, 0, done.stderr)


class CaptureTimeoutTests(unittest.TestCase):
    """CPA-C-002 of the Claude-family practice audit (2026-10-12): the daily record was not running because the /skill-doctor capture hit its 30 s default (it takes about 19 s on a quiet host and about 60 s at three
    runnable threads per CPU, docs/decisions/2026-10-12-skill-invoke-rate-timer.md) and the daily run had no way to give it more."""

    def test_a_capture_may_take_300_seconds_by_default_and_the_flag_still_sets_it(self):
        self.assertEqual(usage.DEFAULT_CLAUDE_TIMEOUT, 300)
        parser = usage.build_parser()
        self.assertEqual(parser.get_default("claude_timeout"), 300)
        self.assertEqual(parser.parse_args(["--run-skill-doctor", "--claude-timeout", "45"]).claude_timeout, 45)
        seen = []
        usage.run_skill_doctor(runner=lambda argv, **kwargs: seen.append(kwargs["timeout"]) or subprocess.CompletedProcess(argv, 1, "", ""))
        self.assertEqual(seen, [300])

    def test_the_daily_run_hands_a_given_timeout_to_the_capture_and_only_to_it(self):
        daily = daily_module()
        for given, expected in ((None, []), (120, ["--claude-timeout", "120"])):
            commands = []

            def runner(command, **kwargs):
                commands.append(command)
                return subprocess.CompletedProcess(command, 1, "", "")
            daily.collect_half("claude", [Path("/fixture/claude")], window=7, now=usage.parse_iso("2026-10-10T00:00:00Z"), runner=runner, claude_timeout=given)
            with self.subTest(claude_timeout=given):
                capture = commands[0]
                after = capture[capture.index("--run-skill-doctor") + 1:]
                self.assertEqual(after[:len(expected)], expected)
                self.assertEqual(sum(command.count("--claude-timeout") for command in commands), len(expected) // 2)

    def test_the_command_line_option_reaches_the_collector_and_a_silly_value_is_refused(self):
        daily = daily_module()
        report = {"measured": {"host": True, "claude": True}}
        with mock.patch.object(daily, "require_reviewed_main"), mock.patch.object(daily, "project_reports", return_value=report), \
                mock.patch.object(daily, "collect_half", return_value=(None, None, None)) as collect, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(daily.main(["--half", "claude", "--claude-root", "/fixture/claude", "--claude-timeout", "120"]), 0)
            self.assertEqual(collect.call_args.kwargs["claude_timeout"], 120)
            self.assertEqual(daily.main(["--half", "claude", "--claude-root", "/fixture/claude"]), 0)
            self.assertIsNone(collect.call_args.kwargs["claude_timeout"])
        with mock.patch.object(daily, "require_reviewed_main"), mock.patch.object(daily, "collect_half") as collect, contextlib.redirect_stderr(io.StringIO()):
            for silly in ("0", "-5", "3601"):
                self.assertEqual(daily.main(["--half", "claude", "--claude-root", "/fixture/claude", "--claude-timeout", silly]), 2, silly)
            collect.assert_not_called()

    def test_a_capture_that_runs_to_its_limit_still_ends_inside_the_commands_limit(self):
        daily = daily_module()
        for given in (None, 120, 3600):
            plan = daily.half_plan("claude", [Path("/fixture/claude")], window=7, now=usage.parse_iso("2026-10-10T00:00:00Z"), claude_timeout=given)
            capture = plan[0]
            with self.subTest(claude_timeout=given):
                self.assertEqual(capture[3], (given or usage.DEFAULT_CLAUDE_TIMEOUT) + daily.CAPTURE_MARGIN)


class ReviewedMainCloneTests(unittest.TestCase):
    """The live clone is a detached worktree of origin/main (docs/decisions/2026-10-09-claude-review-worker.md), so `git branch --show-current` is empty there and the old check (`branch == main`) refused the
    one clone the unit renders for: the daily run exited 2 every day. The question is whether HEAD is a commit of origin/main."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.env = {"PATH": os.environ["PATH"], "HOME": str(self.root), "GIT_CONFIG_NOSYSTEM": "1", "GIT_AUTHOR_NAME": "t", "GIT_COMMITTER_NAME": "t",
                    "GIT_AUTHOR_EMAIL": "t@example.invalid", "GIT_COMMITTER_EMAIL": "t@example.invalid"}
        self.git("init", "-q", "--bare", "-b", "main", str(self.root / "origin.git"), cwd=self.root)
        work = self.root / "work"
        self.git("init", "-q", "-b", "main", str(work), cwd=self.root)
        for name in ("a", "b"):
            (work / name).write_text(name)
            self.git("add", name, cwd=work)
            self.git("commit", "-q", "-m", name, cwd=work)
        self.git("remote", "add", "origin", str(self.root / "origin.git"), cwd=work)
        self.git("push", "-q", "origin", "main", cwd=work)
        self.clone = self.root / "clone"
        self.git("clone", "-q", str(self.root / "origin.git"), str(self.clone), cwd=self.root)
        self.addCleanup(self.tmp.cleanup)

    def git(self, *args, cwd):
        return subprocess.run(["git", *args], cwd=cwd, env=self.env, check=True, capture_output=True, text=True).stdout.strip()

    def commit_in_clone(self):
        (self.clone / "local").write_text("work of this clone")
        self.git("add", "local", cwd=self.clone)
        self.git("commit", "-q", "-m", "local", cwd=self.clone)

    def test_a_clone_on_main_and_a_detached_worktree_of_origin_main_are_accepted(self):
        daily = daily_module()
        self.assertTrue(daily.on_reviewed_main(self.clone))
        self.git("switch", "-q", "--detach", "origin/main", cwd=self.clone)
        self.assertEqual(self.git("branch", "--show-current", cwd=self.clone), "", "the live clone has no branch name")
        self.assertTrue(daily.on_reviewed_main(self.clone))
        self.git("switch", "-q", "--detach", "origin/main~1", cwd=self.clone)
        self.assertTrue(daily.on_reviewed_main(self.clone), "an older commit of origin/main is still reviewed code")

    def test_a_feature_branch_and_a_commit_of_the_clones_own_are_refused(self):
        daily = daily_module()
        self.git("switch", "-q", "-c", "feature", cwd=self.clone)
        self.commit_in_clone()
        self.assertFalse(daily.on_reviewed_main(self.clone))
        self.git("switch", "-q", "main", cwd=self.clone)
        self.commit_in_clone()
        self.assertFalse(daily.on_reviewed_main(self.clone), "branch main with a commit of its own")
        self.git("switch", "-q", "--detach", "feature", cwd=self.clone)
        self.assertFalse(daily.on_reviewed_main(self.clone))

    def test_a_clone_without_origin_main_cannot_be_judged(self):
        daily = daily_module()
        self.git("remote", "remove", "origin", cwd=self.clone)
        with self.assertRaises(daily.CloneRefused):
            daily.on_reviewed_main(self.clone)

    def test_the_daily_run_collects_from_the_live_clone_and_refuses_a_feature_branch(self):
        daily = daily_module()
        report = {"measured": {"host": True, "claude": True}}
        argv = ["--half", "claude", "--claude-root", "/fixture/claude"]
        self.git("switch", "-q", "--detach", "origin/main", cwd=self.clone)
        with mock.patch.object(daily, "ROOT", self.clone), mock.patch.object(daily, "project_reports", return_value=report), \
                mock.patch.object(daily, "collect_half", return_value=(None, None, None)) as collect, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(daily.main(argv), 0)
            collect.assert_called_once()
        self.git("switch", "-q", "-c", "feature", cwd=self.clone)
        self.commit_in_clone()
        errors = io.StringIO()
        with mock.patch.object(daily, "ROOT", self.clone), mock.patch.object(daily, "collect_half") as collect, contextlib.redirect_stderr(errors):
            self.assertEqual(daily.main(argv), 2)
            collect.assert_not_called()
        self.assertIn("not at a commit of origin/main", errors.getvalue())

    def test_the_units_are_rendered_only_for_a_clone_the_run_accepts(self):
        daily = daily_module()
        python = sys.executable
        destination = self.root / "units"
        argv = ["--render-units", str(destination), "--repository", str(self.clone), "--python", python, "--node", python]
        self.git("switch", "-q", "--detach", "origin/main", cwd=self.clone)
        self.assertEqual(daily.main(argv), 0)
        for name in daily.UNIT_FILES:
            self.assertIn(str(self.clone) if name.endswith(".service") else "OnCalendar", (destination / name).read_text())
        shutil.rmtree(destination)
        self.git("switch", "-q", "-c", "feature", cwd=self.clone)
        self.commit_in_clone()
        with contextlib.redirect_stderr(io.StringIO()) as errors:
            self.assertEqual(daily.main(argv), 2)
        self.assertFalse(destination.exists(), "nothing is rendered for a clone that the run would refuse every day")
        self.assertIn("not at a commit of origin/main", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
