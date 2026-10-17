"""Counts-only daily native reports and rendered timer, with no live clients."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

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

    def test_daily_run_uses_the_three_existing_native_tools(self):
        daily = daily_module()
        commands = []
        def runner(command, **kwargs):
            commands.append(command)
            if "--run-skill-doctor" in command:
                result = {"kind": "skill_invoke_rate_report", "skills": []}
            elif "--lanes" in command:
                result = {"kind": "codex_lane_usage_report", "groups": {}}
            else:
                result = {"kind": "claude_child_lane_usage", "groups": {}}
            return subprocess.CompletedProcess(command, 0, json.dumps(result), "")
        daily.collect_reports([Path("/fixture/codex")], [Path("/fixture/claude")], window=7,
                              now=usage.parse_iso("2026-10-10T00:00:00Z"), runner=runner)
        self.assertEqual(3, len(commands))
        self.assertIn("--run-skill-doctor", commands[0])
        self.assertIn("--window", commands[0])
        self.assertIn("--lanes", commands[1])
        self.assertIn("--lanes-sweep", commands[2])
        self.assertIn("--since", commands[2])

    def test_timer_render_targets_the_selected_live_clone(self):
        daily = daily_module()
        with tempfile.TemporaryDirectory() as temp:
            dest = Path(temp)
            daily.render_units(dest, Path("/fixture/live clone"), Path(sys.executable), Path("/fixture/bin/node"))
            service = (dest / "skill-invoke-rate.service").read_text()
            timer = (dest / "skill-invoke-rate.timer").read_text()
            self.assertIn('"/fixture/live clone/tools/skill-usage/daily_skill_usage.py"', service)
            self.assertIn("--codex-root", service)
            self.assertIn("--claude-root", service)
            self.assertIn("OnCalendar=daily", timer)
            self.assertNotIn("@REPOSITORY@", service)

    def test_lane_commands_build_both_lane_reports_for_an_explicit_window(self):
        daily = daily_module()
        commands = daily.lane_commands([Path("/fixture/codex")], [Path("/fixture/claude")], since="2026-10-16T00:00:00Z",
                                       until="2026-10-17T00:00:00Z", now="2026-10-17T00:00:00Z", node="/fixture/bin/node")
        self.assertEqual(len(commands), 2)
        codex, claude = commands
        self.assertEqual(codex[codex.index("--lanes") + 1:], ["--codex-root", "/fixture/codex", "--since", "2026-10-16T00:00:00Z",
                                                               "--until", "2026-10-17T00:00:00Z", "--now", "2026-10-17T00:00:00Z", "--json"])
        self.assertEqual(claude[0], "/fixture/bin/node")
        self.assertEqual(claude[claude.index("--lanes-sweep") + 1:], ["--root", "/fixture/claude", "--since", "2026-10-16T00:00:00Z", "--until", "2026-10-17T00:00:00Z"])
        self.assertFalse(any("--run-skill-doctor" in command for command in commands))

    def test_render_units_renders_any_named_template(self):
        daily = daily_module()
        with tempfile.TemporaryDirectory() as temp:
            dest = Path(temp)
            daily.render_units(dest, Path("/fixture/live clone"), Path(sys.executable), Path("/fixture/bin/node"), names=("token-rate.service", "token-rate.timer"))
            self.assertEqual(sorted(path.name for path in dest.iterdir()), ["token-rate.service", "token-rate.timer"])
            self.assertIn('"/fixture/live clone/tools/skill-usage/daily_token_usage.py"', (dest / "token-rate.service").read_text())

    @unittest.skipUnless(shutil.which("systemd-analyze"), "native systemd verifier unavailable")
    def test_native_user_unit_verification_needs_no_session_or_install(self):
        daily = daily_module()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runtime = root / "runtime"
            runtime.mkdir(mode=0o700)
            daily.render_units(root, ROOT, Path(sys.executable), Path(shutil.which("node")))
            result = subprocess.run([shutil.which("systemd-analyze"), "--user", "--man=no", "verify",
                                     str(root / "skill-invoke-rate.service"), str(root / "skill-invoke-rate.timer")],
                                    env={"HOME": str(root), "PATH": os.defpath, "XDG_RUNTIME_DIR": str(runtime)},
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertFalse((root / ".config/systemd/user").exists())


if __name__ == "__main__":
    unittest.main()
