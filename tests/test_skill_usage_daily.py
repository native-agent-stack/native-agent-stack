"""Counts-only daily native reports and rendered timer, with no live clients."""
import contextlib
import errno
import getpass
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import shlex
import stat
import shutil
import subprocess
import sys
import tempfile
import threading
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


class NativeReportShapeTests(unittest.TestCase):
    """Review of #1043 at 68d4f4343 (P1): a host report whose `claude` value is [] raised AttributeError in project_reports, main did not catch it, and the traceback on stderr printed the account's name and
    home directory. json.loads gives an array as a list and an object as a dict (python/cpython@cbc944f4bc59 Doc/library/json.rst L385-L387), so a field of the wrong type is data, not a bug in the producer
    to be read from a traceback: a container of the wrong shape reads as absent, the half is unmeasured, and nothing is published as measured."""

    def mutated(self, half, change):
        host, codex, claude = claude_reports() if half == "claude" else codex_reports()
        change(host, codex, claude)
        return host, codex, claude

    CASES = (
        ("claude", "the host's claude state is an array", lambda h, c, l: h.update(claude=[]), {"host": False}),
        ("claude", "the host's claude state is a string", lambda h, c, l: h.update(claude="measured"), {"host": False}),
        ("claude", "the host's claude state is a number", lambda h, c, l: h.update(claude=5), {"host": False}),
        ("claude", "the host's claude state is null", lambda h, c, l: h.update(claude=None), {"host": False}),
        ("claude", "the host's codex state is an array", lambda h, c, l: h.update(codex=[]), {}),
        ("claude", "the codex use groups are an array", lambda h, c, l: h.update(codex_use_groups=[]), {}),
        ("claude", "a window of the codex use groups is an array", lambda h, c, l: h.update(codex_use_groups={"7": []}), {}),
        ("claude", "a skill's claude entry is an array", lambda h, c, l: h["skills"][0].update(claude=[]), {}),
        ("claude", "a skill's codex entry is an array", lambda h, c, l: h["skills"][0].update(codex=[]), {}),
        ("claude", "a skill's counts are an array", lambda h, c, l: h["skills"][0].update(codex={"counts": []}), {}),
        ("claude", "a skill's window is an array", lambda h, c, l: h["skills"][0].update(codex={"counts": {"7": []}}), {}),
        ("claude", "a skill's use counts are an array", lambda h, c, l: h["skills"][0].update(codex={"use_counts": []}), {}),
        ("claude", "the use policy is an array", lambda h, c, l: h.update(codex_use_policy=[]), {}),
        ("claude", "the claude groups are an array", lambda h, c, l: l.update(groups=[]), {}),
        ("claude", "the spawn groups are an array", lambda h, c, l: l.update(groups={"by_spawn_and_agent_type": []}), {}),
        ("claude", "a spawn's agents are an array", lambda h, c, l: l.update(groups={"by_spawn_and_agent_type": {"workflow": []}}), {}),
        ("claude", "the main lane is an array", lambda h, c, l: l.update(main=[]), {}),
        ("codex", "the host's codex state is an array", lambda h, c, l: h.update(codex=[]), {"codex": False}),
        ("codex", "the codex groups are an array", lambda h, c, l: c.update(groups=[]), {}),
        ("codex", "the workers_by_role groups are an array", lambda h, c, l: c["groups"].update(workers_by_role=[]), {}),
        ("codex", "the workers_by_kind groups are a string", lambda h, c, l: c["groups"].update(workers_by_kind="worker"), {}),
        ("codex", "the workers group is an array", lambda h, c, l: c["groups"].update(workers=[]), {}),
        ("codex", "the use groups of the roles are an array", lambda h, c, l: (c["groups"].update(workers_by_role={"worker": {"sessions": 1, "skill_md_reads": {"gh-fix-ci": 4}}}),
                                                                              h["codex_use_groups"]["7"].update(workers_by_role=["zz-fake"])), {}),
        ("codex", "the use groups of the kinds are an array", lambda h, c, l: (c["groups"].update(workers_by_kind={"edit": {"sessions": 1, "skill_md_reads": {"gh-fix-ci": 4}}}),
                                                                              h["codex_use_groups"]["7"].update(workers_by_kind=["zz-fake"])), {}),
        ("codex", "the use counts of a lane are an array", lambda h, c, l: h["codex_use_groups"]["7"].update(workers=["zz-fake"]), {}),
        ("codex", "a skill's counts are an array", lambda h, c, l: h["skills"][0]["codex"].update(counts=[]), {}),
        ("codex", "a skill's window is an array", lambda h, c, l: h["skills"][0]["codex"].update(counts={"7": ["zz-fake"]}), {}),
        ("codex", "a skill's use counts are an array", lambda h, c, l: h["skills"][0]["codex"].update(use_counts=["zz-fake"]), {}),
        ("codex", "a skill's codex entry is an array", lambda h, c, l: h["skills"][0].update(codex=["zz-fake"]), {}),
        ("codex", "the codex use groups are a string", lambda h, c, l: h.update(codex_use_groups="x"), {"codex": False}),
    )

    def test_a_native_report_of_the_wrong_shape_is_unmeasured_and_never_an_error(self):
        daily = daily_module()
        for half, label, change, expected in self.CASES:
            host, codex, claude = self.mutated(half, change)
            fresh = claude_reports() if half == "claude" else codex_reports()
            valid = daily.project_reports(*fresh, now=NOW, window=7, half=half)
            with self.subTest(case=label):
                report = daily.project_reports(host, codex, claude, now=NOW, window=7, half=half)
                self.assertNotIn("zz-fake", json.dumps(report), "a name that came out of a container of the wrong shape is not published")
                self.assertEqual(report["measured"], {**valid["measured"], **expected}, "only the flags the malformed field decides change, and never to measured")
                for key, flag in report["measured"].items():
                    self.assertFalse(flag and not valid["measured"][key], "nothing is published as measured that the valid report did not measure")

    def test_the_container_helper_reads_only_objects(self):
        daily = daily_module()
        self.assertEqual(daily.table({"a": 1}), {"a": 1})
        for value in ([], [{"a": 1}], "x", 5, None, True):
            self.assertEqual(daily.table(value), {})

    def copied_tool(self):
        """A copy of the tool under the home directory, as the live clone is: a traceback from it names the account and its home."""
        try:
            copy = Path(tempfile.mkdtemp(prefix=".skill-shape-", dir=Path.home()))
        except OSError:
            self.skipTest("the home directory is not writable")
        self.addCleanup(shutil.rmtree, copy, True)
        shutil.copytree(ROOT / "tools/skill-usage", copy / "tools/skill-usage", ignore=shutil.ignore_patterns("__pycache__"))
        (copy / "adoption/skills/claude-routing").mkdir(parents=True)
        shutil.copy(ROOT / "adoption/skills/claude-routing/trigger-baseline.json", copy / "adoption/skills/claude-routing/trigger-baseline.json")
        return copy

    def test_the_command_line_gives_a_fixed_diagnostic_and_no_traceback_for_a_malformed_native_report(self):
        copy = self.copied_tool()
        daily_path = copy / "tools/skill-usage/daily_skill_usage.py"
        host, _, lanes = claude_reports()
        lanes_file = copy / "lanes.json"
        lanes_file.write_text(json.dumps(lanes))
        account, home = getpass.getuser(), str(Path.home())
        destination = Path(tempfile.mkdtemp(prefix="skill-shape-out-"))      # a record may not be written inside the tool's own tree
        self.addCleanup(shutil.rmtree, destination, True)
        for label, change in (("claude is an array", lambda h: h.update(claude=[])), ("a skill's counts are an array", lambda h: h["skills"][0].update(codex={"counts": []})),
                              ("the codex use groups are an array", lambda h: h.update(codex_use_groups=[]))):
            bad_host = json.loads(json.dumps(host))
            change(bad_host)
            host_file = copy / "host.json"
            host_file.write_text(json.dumps(bad_host))
            out = destination / "record.json"
            out.unlink(missing_ok=True)
            with self.subTest(case=label):
                done = subprocess.run([sys.executable, "-B", str(daily_path), "--half", "claude", "--host-report", str(host_file), "--claude-lanes-report", str(lanes_file), "--now", NOW,
                                       "--out", str(out)], capture_output=True, text=True, timeout=60)
                self.assertNotIn("Traceback", done.stderr)
                self.assertNotIn(account, done.stderr)
                self.assertNotIn(home, done.stderr)
                self.assertNotIn(home, done.stdout)
                self.assertEqual(done.stderr, "", "a malformed field reads as absent: the half is unmeasured, and that is the exit status, not a diagnostic")
                self.assertEqual(done.returncode, 1 if label == "claude is an array" else 0, done.stdout)
                record = json.loads(out.read_text())
                self.assertIs(record["measured"]["host"], label != "claude is an array", "the host is measured only when its own state says so")

    def test_an_error_nobody_foresaw_is_a_fixed_diagnostic_without_its_text_or_a_traceback(self):
        daily = daily_module()
        out = Path(tempfile.mkdtemp(prefix="skill-fixed-")) / "never.json"
        self.addCleanup(shutil.rmtree, out.parent, True)
        for error in (AttributeError("SENTINEL-TEXT"), TypeError("SENTINEL-TEXT"), KeyError("SENTINEL-TEXT")):
            errors = io.StringIO()
            with self.subTest(error=type(error).__name__), mock.patch.object(daily, "require_reviewed_main"), mock.patch.object(daily, "collect_half", return_value=claude_reports()), \
                    mock.patch.object(daily, "project_reports", side_effect=error), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(errors):
                code = daily.main(["--half", "claude", "--claude-root", "/fixture/root", "--now", NOW, "--out", str(out)])
            self.assertEqual((code, errors.getvalue()), (2, "daily skill usage unavailable; inspect the native collector separately\n"))
            self.assertFalse(out.exists(), "nothing was published")


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


def projected(half):
    daily = daily_module()
    host, codex, claude = claude_reports() if half == "claude" else codex_reports()
    return daily.project_reports(host, codex, claude, now=NOW, window=7, half=half)


def run_half(half, directory, *extra):
    """daily.main for one half with the collection stubbed: (exit code, stderr text)."""
    daily = daily_module()
    reports = claude_reports() if half == "claude" else codex_reports()
    root = "--claude-root" if half == "claude" else "--codex-root"
    argv = ["--half", half, root, "/fixture/root", "--now", NOW, "--out", str(directory / f"{half}.json"), *extra]
    errors = io.StringIO()
    with mock.patch.object(daily, "require_reviewed_main"), mock.patch.object(daily, "collect_half", return_value=reports), \
            contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(errors):
        code = daily.main(argv)
    return code, errors.getvalue()


class OtherRecordTests(unittest.TestCase):
    """Astra's read of 6c4bbd0d (P1-2): the other half's record is a file another process wrote. One that parses as JSON and has the schema and the half but another shape used to end in an AttributeError in the merge:
    the refresh's handler did not catch it, the half exited 1 after writing its own record, and the traceback printed the account's home path. An invalid record is an absent half."""

    def malformed(self):
        base = projected("codex")
        return {
            "measured is a list": dict(base, measured=[]),
            "measured is missing": {key: value for key, value in base.items() if key != "measured"},
            "measured lacks the half's key": dict(base, measured={}),
            "measured holds a non-boolean": dict(base, measured={"codex": "yes"}),
            "host is a mapping": dict(base, host={"name": "gh-fix-ci"}),
            "lanes is a string": dict(base, lanes="none"),
            "generated_at is a number": dict(base, generated_at=5),
            "generated_at is not a timestamp": dict(base, generated_at="yesterday"),
            "window_days is a string": dict(base, window_days="7"),
            "window_days is a boolean": dict(base, window_days=True),
            "codex_bulk_scan_limit is a list": dict(base, codex_bulk_scan_limit=[1]),
        }

    def test_a_record_of_another_shape_is_an_absent_half(self):
        daily = daily_module()
        self.assertEqual(daily.half_record(projected("codex"), "codex"), projected("codex"), "a record the half itself writes is taken")
        for name, record in self.malformed().items():
            with self.subTest(record=name):
                self.assertIsNone(daily.half_record(record, "codex"))
                merged = daily.merge_halves(projected("claude"), record)
                self.assertEqual(merged["measured"], {"host": True, "codex": False, "claude": True})
                self.assertIsNone(merged["halves"]["codex"])
        for value in (None, [], "text", 5, [{"schema": "skill-invoke-rate-daily/1", "half": "codex"}]):
            self.assertIsNone(daily.half_record(value, "codex"))
        combined = daily.merge_halves(projected("claude"), projected("codex"))      # the combined record has all three keys: only its `half` tells it from a half's record
        self.assertEqual(combined["half"], "all")
        for half in daily.HALVES:
            self.assertIsNone(daily.half_record(combined, half), "a combined record is not a half's record")
        self.assertIsNone(daily.half_record(projected("claude"), "codex"))
        self.assertIsNone(daily.half_record(projected("codex"), "claude"))

    def test_a_row_value_of_another_type_is_unknown_in_the_combined_record(self):
        """The merge copies counts and the wiring name from the other half's rows; a value of another type (a boolean would read as zero uses) is unknown, not copied."""
        daily = daily_module()
        codex = projected("codex")
        codex["host"][0].update(codex_use=False, codex_skill_md_reads=-3, codex_name_mentions="4")
        codex["host"][1].update(codex_use=True)
        claude = projected("claude")
        claude["host"][0].update(wiring={"status": "wired"}, claude_uses_lifetime=2.5)
        merged = daily.merge_halves(claude, codex)
        rows = {row["name"]: row for row in merged["host"]}
        self.assertEqual((rows["gh-fix-ci"]["codex_use"], rows["gh-fix-ci"]["codex_skill_md_reads"], rows["gh-fix-ci"]["codex_name_mentions"]), (None, None, None))
        self.assertEqual((rows["gh-fix-ci"]["wiring"], rows["gh-fix-ci"]["claude_uses_lifetime"]), (None, None))
        self.assertIsNone(rows["typesafe-ai"]["codex_use"])
        self.assertEqual(merged["zero_use"]["codex"], [], "a boolean is not a count of zero")

    def test_a_malformed_other_record_leaves_the_halfs_exit_status_and_prints_no_traceback(self):
        for name, record in self.malformed().items():
            with self.subTest(record=name), tempfile.TemporaryDirectory() as temp:
                directory = Path(temp)
                other = directory / "codex.json"
                other.write_text(json.dumps(record))
                code, errors = run_half("claude", directory, "--combined-out", str(directory / "combined.json"), "--other-record", str(other))
                self.assertEqual((code, errors), (0, ""), "the half is measured: no failure, nothing on stderr (a traceback would name the home path)")
                self.assertEqual(json.loads((directory / "claude.json").read_text())["measured"], {"host": True, "claude": True}, "the half's own record is written first and stays")
                self.assertEqual(json.loads((directory / "combined.json").read_text())["measured"], {"host": True, "codex": False, "claude": True})

    def test_an_error_inside_the_refresh_is_a_fixed_message_whatever_it_is(self):
        daily = daily_module()
        for error in (AttributeError("sentinel text of an error"), RuntimeError("boom"), RecursionError()):
            with self.subTest(error=type(error).__name__), tempfile.TemporaryDirectory() as temp:
                with mock.patch.object(daily, "merge_halves", side_effect=error):
                    self.assertIs(daily.refresh_combined(Path(temp) / "combined.json", projected("claude"), None), False)
        errors = io.StringIO()
        with tempfile.TemporaryDirectory() as temp, mock.patch.object(daily, "require_reviewed_main"), mock.patch.object(daily, "collect_half", return_value=claude_reports()), \
                mock.patch.object(daily, "merge_halves", side_effect=AttributeError("sentinel text of an error")), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(errors):
            directory = Path(temp)
            code = daily.main(["--half", "claude", "--claude-root", "/fixture/root", "--now", NOW, "--out", str(directory / "claude.json"), "--combined-out", str(directory / "combined.json")])
        self.assertEqual(code, 0)
        self.assertEqual(errors.getvalue(), "daily skill usage: the combined record was not refreshed\n", "a fixed message: no traceback, no text of the error")


class RefreshLockTests(unittest.TestCase):
    """Astra's read of 6c4bbd0d (P3-5): both timers are Persistent=true, so after the host was off both units start at once and their refreshes can overlap. Each half publishes its own record, then reads the other's
    and publishes the combined one; without a lock the later publication can be built from an older read. The refresh now holds a lock from the read to the rename."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        self.combined, self.codex_record = self.directory / "combined.json", self.directory / "codex.json"
        self.lock = self.directory / "combined.json.lock"
        self.daily = daily_module()

    def hold_lock(self):
        """The other half's refresh: holds the lock until the test releases it. Returns (release event, thread)."""
        held, release = threading.Event(), threading.Event()

        def other_half_refresh():
            with self.daily.refresh_lock(self.lock):
                held.set()
                release.wait(20)
        holder = threading.Thread(target=other_half_refresh)
        holder.start()
        self.assertTrue(held.wait(10))
        return release, holder

    def test_a_refresh_waits_for_the_other_halfs_refresh_and_then_reads_the_record_that_half_published(self):
        release, holder = self.hold_lock()
        result = []
        waiter = threading.Thread(target=lambda: result.append(self.daily.refresh_combined(self.combined, projected("claude"), self.codex_record)))
        waiter.start()
        waiter.join(0.5)
        self.assertTrue(waiter.is_alive(), "while the other half's refresh holds the lock, this refresh has neither read nor published")
        self.assertFalse(self.combined.exists())
        self.codex_record.write_text(json.dumps(projected("codex")))   # the other half publishes its own record before its refresh ends
        release.set()
        holder.join(10)
        waiter.join(10)
        self.assertEqual(result, [True])
        data = json.loads(self.combined.read_text())
        self.assertEqual(data["measured"], {"host": True, "codex": True, "claude": True}, "built from the newest record of each half, not from the read taken before the wait")
        self.assertEqual(stat.S_IMODE(self.lock.stat().st_mode) & 0o077, 0, "the lock file is private to the account")

    def test_a_refresh_that_cannot_get_the_lock_gives_up_and_publishes_nothing(self):
        release, holder = self.hold_lock()
        try:
            self.assertFalse(self.daily.refresh_combined(self.combined, projected("claude"), self.codex_record, wait=0.2))
            self.assertFalse(self.combined.exists())
        finally:
            release.set()
            holder.join(10)
        self.assertTrue(self.daily.refresh_combined(self.combined, projected("claude"), self.codex_record, wait=0.2), "the lock is free again once its holder is done")

    def test_the_lock_is_dropped_when_its_holder_fails(self):
        with self.assertRaises(RuntimeError):
            with self.daily.refresh_lock(self.lock):
                raise RuntimeError("a failed refresh")
        with self.daily.refresh_lock(self.lock, wait=0.2):
            pass

    def test_the_record_directory_is_created_private_and_a_host_without_flock_still_refreshes(self):
        fresh = self.directory / "records" / "combined.json"
        self.assertTrue(self.daily.refresh_combined(fresh, projected("claude"), None))
        self.assertEqual(stat.S_IMODE(fresh.parent.stat().st_mode), 0o700)
        with mock.patch.object(self.daily, "fcntl", None):
            self.assertTrue(self.daily.refresh_combined(self.combined, projected("claude"), None), "no flock, no lock: the refresh is the one that ran before the lock")
        self.assertTrue(self.combined.exists())

    def test_no_lock_file_is_created_for_a_destination_inside_a_worktree(self):
        inside = ROOT / "combined-inside-the-worktree.json"
        self.assertFalse(self.daily.refresh_combined(inside, projected("claude"), None))
        self.assertFalse(inside.exists())
        self.assertFalse(inside.with_name(inside.name + ".lock").exists(), "the guard runs before the lock file is opened")

    def test_concurrent_refreshes_leave_one_complete_combined_record(self):
        """Both halves have published their own record and refresh at once, in either start order: the combined record is complete and parses."""
        claude, codex = projected("claude"), projected("codex")
        claude_record = self.directory / "claude.json"
        for first in ("claude", "codex"):
            self.combined.unlink(missing_ok=True)
            claude_record.unlink(missing_ok=True)
            self.codex_record.unlink(missing_ok=True)
            claude_record.write_text(json.dumps(claude))
            self.codex_record.write_text(json.dumps(codex))
            threads = [threading.Thread(target=self.daily.refresh_combined, args=(self.combined, claude, self.codex_record)),
                       threading.Thread(target=self.daily.refresh_combined, args=(self.combined, codex, claude_record))]
            for thread in (threads if first == "claude" else reversed(threads)):
                thread.start()
            for thread in threads:
                thread.join(20)
            with self.subTest(started_first=first):
                self.assertEqual(json.loads(self.combined.read_text())["measured"], {"host": True, "codex": True, "claude": True})


SANDBOX_KEYS = ("ProtectSystem", "ProtectHome", "ReadWritePaths", "PrivateTmp", "PrivateUsers")


def service_section(text):
    """The [Service] section of a rendered unit as {key: [values, in order]}, comment lines dropped."""
    found, inside = {}, False
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("[") and line.endswith("]"):
            inside = line == "[Service]"
        elif inside and line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            found.setdefault(key, []).append(value)
    return found


class ServiceSandboxTests(unittest.TestCase):
    """Astra's read of 6c4bbd0d (P1-1): UMask= restricts the mode of what a service creates, not where it can write, and neither service established a read-only file system or a write allow-list, so ordinary Python start-up
    wrote a __pycache__ into the live clone. systemd.exec(5) (systemd 259.5 installed; systemd/systemd@e846bbad man/systemd.exec.xml L1497 ProtectSystem=, L1526 ProtectHome=, L1809 ReadWritePaths=, L1919 PrivateTmp=):
    ProtectSystem=strict mounts the hierarchy read-only, ProtectHome=read-only does the same for the home directory, ReadWritePaths= allow-lists the one directory that is written."""

    def render(self, directory):
        daily = daily_module()
        daily.render_units(directory, Path("/fixture/live"), Path(sys.executable), Path("/fixture/bin/node"))
        return daily, {half: (directory / f"skill-invoke-rate-{half}.service") for half in daily.HALVES}

    def test_each_service_makes_the_file_system_read_only_except_its_record_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            daily, services = self.render(Path(temp))
            for half, service in services.items():
                section = service_section(service.read_text())
                with self.subTest(half=half):
                    self.assertEqual(section.get("ProtectSystem"), ["strict"])
                    self.assertEqual(section.get("ProtectHome"), ["read-only"])
                    self.assertEqual(section.get("PrivateTmp"), ["true"])
                    self.assertEqual(section.get("PrivateUsers"), ["true"], "asked for, so that a manager that cannot create the user namespace fails the unit (status 217/USER) instead of ignoring it")
                    self.assertIn("PYTHONDONTWRITEBYTECODE=1", section.get("Environment", []), "every interpreter the service starts, not only the parent")
                    writable = section.get("ReadWritePaths", [])
                    self.assertEqual(len(writable), 1, "one directory is written")
                    self.assertEqual(len(writable[0].split()), 1)
                    self.assertTrue(writable[0].startswith("%h/"), "a path under the account's home, resolved by the user manager")
                    self.assertFalse(writable[0].startswith(("-", "+")), "a missing directory fails the unit instead of running it unconfined")
                    records = {os.path.dirname(match) for match in re.findall(r"--(?:out|combined-out|other-record) (\S+)", section["ExecStart"][0])}
                    self.assertEqual(records, {writable[0]}, "every record the half writes or reads is in the one writable directory, so a path moved in ExecStart needs its allow-list moved too")
                    for protected in ("/fixture/live", "%h/.claude", "%h/.codex"):
                        self.assertFalse(writable[0] == protected or writable[0].startswith(protected + "/") or protected.startswith(writable[0] + "/"), f"{protected} is read-only")

    def test_each_service_asks_the_file_system_before_any_work_whether_it_is_confined(self):
        """Review of #1043 at 68d4f4343 (blocker 1, the CI job of the same head): systemd starts a unit without the file system namespace, and says nothing, when its manager cannot create one
        (systemd/systemd-stable@387a14a7b67b, v255.4, src/core/exec-invoke.c L3212-L3237), so the program checks."""
        with tempfile.TemporaryDirectory() as temp:
            daily, services = self.render(Path(temp))
            for half, service in services.items():
                tokens = shlex.split(service_section(service.read_text())["ExecStart"][0])
                flags = [tokens[i + 1] for i, token in enumerate(tokens) if token == "--refuse-writable"]
                with self.subTest(half=half):
                    self.assertEqual(flags, ["%h", "/fixture/live"], "the home directory (the client's state is under it) and the clone")
                    self.assertLess(tokens.index("--refuse-writable"), tokens.index("--half"), "the check is the first option, ahead of every one that starts work")

    @unittest.skipUnless(shutil.which("systemd-analyze"), "native systemd analyzer unavailable")
    def test_the_native_analyzer_reads_the_directives_as_protection(self):
        analyze = shutil.which("systemd-analyze")
        if "--offline" not in subprocess.run([analyze, "security", "--help"], capture_output=True, text=True, timeout=30).stdout:
            self.skipTest("this systemd-analyze has no `security --offline`")

        def rows(unit):
            done = subprocess.run([analyze, "security", "--offline=yes", "--user", "--json=short", str(unit)], capture_output=True, text=True, timeout=60)
            self.assertEqual(done.returncode, 0, done.stderr)
            return {row["json_field"]: row for row in json.loads(done.stdout) if row.get("json_field") in ("ProtectSystem", "ProtectHome", "PrivateTmp")}
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            daily, services = self.render(directory)
            for half, service in services.items():
                bare = directory / f"bare-{half}.service"
                bare.write_text("".join(line + "\n" for line in service.read_text().splitlines() if line.partition("=")[0] not in SANDBOX_KEYS and "PYTHONDONTWRITEBYTECODE" not in line))
                protected, unprotected = rows(service), rows(bare)
                with self.subTest(half=half):
                    self.assertTrue(protected["ProtectSystem"]["set"] and not unprotected["ProtectSystem"]["set"], protected["ProtectSystem"]["description"])
                    self.assertTrue(protected["PrivateTmp"]["set"] and not unprotected["PrivateTmp"]["set"])
                    self.assertNotEqual(protected["ProtectHome"]["description"], unprotected["ProtectHome"]["description"])
                    self.assertIn("read-only", protected["ProtectHome"]["description"])


PROBE = r"""
import errno, json, os, sys
from pathlib import Path
clone, other, records, unrelated = (Path(arg) for arg in sys.argv[1:5])


def attempt(target):
    try:
        target.write_text("x")
        target.unlink()
        return "written"
    except OSError as error:
        return errno.errorcode.get(error.errno, "?")


sys.path.insert(0, str(clone))
import helper_module
print(json.dumps({"clone": attempt(clone / "probe.txt"), "other": attempt(other / "probe.txt"), "unrelated": attempt(unrelated), "records": attempt(records / "probe.txt"),
                  "pycache": (clone / "__pycache__").exists(), "helper": helper_module.VALUE}))
"""

# What the program does first under a unit: ask the file system (daily_skill_usage.require_confined) about the clone, a sibling directory and the home directory. Exit 3 when it refuses.
CHECK = r"""
import sys
sys.path.insert(0, sys.argv[1])
import daily_skill_usage as daily
try:
    daily.require_confined(sys.argv[2:])
except daily.Unconfined:
    sys.exit(3)
"""

# A stand-in for `systemd-run --user --wait --collect --pipe -q -p KEY=VALUE ... COMMAND`: it accepts every property, applies WorkingDirectory= and Environment=, and applies none of the sandboxing ones, as a
# user manager does when it cannot create the mount namespace (systemd/systemd-stable@387a14a7b67b, v255.4: src/core/exec-invoke.c L3212-L3237, src/core/namespace.c L2488-L2497).
STUB_MANAGER = r"""
import os
import subprocess
import sys

arguments, environment, directory = sys.argv[1:], dict(os.environ), None
index = 0
while index < len(arguments):
    if arguments[index] in ("--user", "--wait", "--collect", "--pipe", "-q"):
        index += 1
    elif arguments[index] == "-p":
        key, _, value = arguments[index + 1].partition("=")
        if key == "WorkingDirectory":
            directory = value
        elif key == "Environment":
            name, _, setting = value.partition("=")
            environment[name] = setting
        index += 2
    else:
        break
sys.exit(subprocess.run(arguments[index:], cwd=directory, env=environment).returncode)
"""

UNCONFINED_MESSAGE = "daily skill usage refused: this process can write where its service unit forbids it, so the unit's file system directives are not in effect and it did not run\n"


class ManagerProbes:
    """What a service unit's directives do to a process, asked through `self.manager`: an argv prefix that behaves like `systemd-run --user --wait --collect --pipe -q` (the real one, or STUB_MANAGER)."""
    manager = None

    def units(self):
        daily = daily_module()
        with tempfile.TemporaryDirectory() as temp:
            daily.render_units(Path(temp), Path("/fixture/live"), Path(sys.executable), Path("/fixture/bin/node"))
            return {half: service_section((Path(temp) / f"skill-invoke-rate-{half}.service").read_text()) for half in daily.HALVES}

    def fixture(self):
        try:
            fixture = Path(tempfile.mkdtemp(prefix=".skill-sandbox-", dir=Path.home()))
        except OSError:
            self.skipTest("the home directory is not writable")
        self.addCleanup(shutil.rmtree, fixture, True)
        for name in ("clone", "other", "records"):
            (fixture / name).mkdir()
        (fixture / "clone" / "helper_module.py").write_text("VALUE = 7\n")
        shutil.copytree(ROOT / "tools/skill-usage", fixture / "tool", ignore=shutil.ignore_patterns("__pycache__"))   # the program, where a unit with a private /var/tmp can still read it
        return fixture

    def properties(self, section, records):
        home = str(Path.home())
        out = []
        for key in SANDBOX_KEYS:
            for value in section[key]:
                value = records if key == "ReadWritePaths" else value
                out += ["-p", f"{key}={value.replace('%h', home)}"]
        for value in section["Environment"]:
            if value.startswith("PYTHONDONTWRITEBYTECODE="):
                out += ["-p", f"Environment={value}"]
        return out

    def under_manager(self, extra, fixture, command):
        return subprocess.run([*self.manager, "-p", f"WorkingDirectory={fixture / 'clone'}", *extra, *command], capture_output=True, text=True, timeout=120)

    def probe(self, extra, fixture):
        clone, other, records = fixture / "clone", fixture / "other", fixture / "records"
        unrelated = Path.home() / f".skill-sandbox-probe-{os.getpid()}"
        self.addCleanup(lambda: unrelated.unlink(missing_ok=True))
        done = self.under_manager(extra, fixture, [sys.executable, "-c", PROBE, str(clone), str(other), str(records), str(unrelated)])
        self.assertEqual(done.returncode, 0, done.stderr)
        return json.loads(done.stdout)

    def check(self, extra, fixture):
        """The exit status of `require_confined` over the clone, the sibling directory and the home directory, run under the manager: 0 accepted, 3 refused."""
        done = self.under_manager(extra, fixture, [sys.executable, "-B", "-c", CHECK, str(fixture / "tool"), str(fixture / "clone"), str(fixture / "other"), str(Path.home())])
        self.assertIn(done.returncode, (0, 3), done.stderr)
        return done.returncode


class StubManagerTests(ManagerProbes, unittest.TestCase):
    """Review of #1043 at 68d4f4343 (blocker 1, and the failed shard of the same head on the GitHub-hosted runner: ubuntu-24.04 image 20261004.327.1, systemd 255.4-1ubuntu8.17, job 115064673607 of run
    38325995828): the rendered directives were accepted, the probe ran, and it wrote to the clone, the sibling directory and the home directory ({clone: written, other: written, unrelated: written, records:
    written, pycache: False, helper: 7}). The first version of the runtime test assumed the manager applies what it accepts. The stand-in manager reproduces that manager on every host, with or without systemd."""

    @classmethod
    def setUpClass(cls):
        cls._temp = tempfile.TemporaryDirectory(prefix="skill-stub-manager-")
        cls.addClassCleanup(cls._temp.cleanup)
        stub = Path(cls._temp.name) / "stub_manager.py"
        stub.write_text(STUB_MANAGER)
        cls.manager = [sys.executable, str(stub)]

    def test_a_manager_that_applies_none_of_the_directives_gives_the_probe_the_whole_home(self):
        fixture = self.fixture()
        control = self.probe(["-p", "Environment=PYTHONDONTWRITEBYTECODE="], fixture)
        self.assertEqual(control, {"clone": "written", "other": "written", "unrelated": "written", "records": "written", "pycache": True, "helper": 7})
        shutil.rmtree(fixture / "clone" / "__pycache__")
        for half, section in self.units().items():
            with self.subTest(half=half):
                confined = self.probe(self.properties(section, str(fixture / "records")), fixture)
                self.assertEqual(confined, {"clone": "written", "other": "written", "unrelated": "written", "records": "written", "pycache": False, "helper": 7},
                                 "the stand-in does what the runner's manager did: the environment is applied and the sandboxing is not")

    def test_the_program_refuses_to_run_under_a_manager_that_applies_none_of_the_directives(self):
        fixture = self.fixture()
        self.assertEqual(self.check(["-p", "Environment=PYTHONDONTWRITEBYTECODE="], fixture), 3, "without the directives the program is refused")
        for half, section in self.units().items():
            with self.subTest(half=half):
                self.assertEqual(self.check(self.properties(section, str(fixture / "records")), fixture), 3, "with the directives accepted and not applied it is refused too")
        self.assertEqual(sorted(path.name for folder in (fixture / "clone", fixture / "other", Path.home()) for path in folder.iterdir() if path.name.startswith(".skill-usage-confinement")), [],
                         "the probing leaves no file behind")

    def test_the_rendered_command_line_stops_before_any_work_when_the_manager_applied_nothing(self):
        """The service-level negative control: the unit's own command line, under a manager that ignores the sandbox, exits 2 with the fixed message and writes no record."""
        daily = daily_module()
        fixture = self.fixture()
        home = fixture / "home"
        home.mkdir()
        with tempfile.TemporaryDirectory() as temp:
            daily.render_units(Path(temp), ROOT, Path(sys.executable), Path("/fixture/bin/node"))
            for half in daily.HALVES:
                section = service_section((Path(temp) / f"skill-invoke-rate-{half}.service").read_text())
                command = [token.replace("%h", str(home)) for token in shlex.split(section["ExecStart"][0])]
                with self.subTest(half=half):
                    done = self.under_manager(["-p", "Environment=PYTHONDONTWRITEBYTECODE=1"], fixture, command)
                    self.assertEqual((done.returncode, done.stdout, done.stderr), (2, "", UNCONFINED_MESSAGE))
                    self.assertEqual(list(home.rglob("*")), [], "no record, no lock, no directory was written")


class NativeManagerTests(ManagerProbes, unittest.TestCase):
    """The rendered service's own directives, applied by the user manager of the host to a probe. A manager has three outcomes on a host: it applies the directives (`enforced`: writes to the clone and to the
    rest of the home are refused, the record directory is written, no bytecode is written), it accepts them and applies none (`unenforced`: the GitHub-hosted runner, and the program must refuse), or it will not
    start the unit with them (the suite skips: systemd itself failed closed)."""

    @classmethod
    def setUpClass(cls):
        systemd_run = shutil.which("systemd-run")
        if not systemd_run:
            raise unittest.SkipTest("systemd-run is unavailable")
        if sys.executable.startswith(("/tmp/", "/var/tmp/")):
            raise unittest.SkipTest("the interpreter lives where PrivateTmp= hides it")
        cls.manager = [systemd_run, "--user", "--wait", "--collect", "--pipe", "-q"]
        try:
            done = subprocess.run([*cls.manager, "-p", "ProtectSystem=strict", "-p", "ProtectHome=read-only", "-p", "PrivateTmp=true", "-p", "PrivateUsers=true", "/bin/true"],
                                  capture_output=True, text=True, timeout=60)
        except (OSError, subprocess.SubprocessError):
            raise unittest.SkipTest("the user manager cannot be reached") from None
        if done.returncode != 0:
            raise unittest.SkipTest("this user manager cannot be reached, or will not start a unit with the file system namespaces and the user namespace the services use (it fails closed)")
        try:
            fixture = Path(tempfile.mkdtemp(prefix=".skill-sandbox-", dir=Path.home()))
        except OSError:
            raise unittest.SkipTest("the home directory is not writable") from None
        try:
            (fixture / "clone").mkdir()
            for name in ("other", "records"):
                (fixture / name).mkdir()
            probe = subprocess.run([*cls.manager, "-p", f"WorkingDirectory={fixture / 'clone'}", "-p", "ProtectSystem=strict", "-p", "ProtectHome=read-only", "-p", "PrivateTmp=true",
                                    "-p", "PrivateUsers=true", "-p", f"ReadWritePaths={fixture / 'records'}", sys.executable, "-B", "-c",
                                    "import pathlib, sys\ntry:\n    pathlib.Path(sys.argv[1]).write_text('x')\nexcept OSError:\n    print('refused')\nelse:\n    print('written')", str(fixture / "clone" / "probe.txt")],
                                   capture_output=True, text=True, timeout=60)
        finally:
            shutil.rmtree(fixture, ignore_errors=True)
        cls.enforced = probe.stdout.strip() == "refused"
        print(f"manager class: {'enforced' if cls.enforced else 'unenforced'}", file=sys.stderr)

    def test_the_rendered_directives_refuse_writes_to_the_clone_and_the_home_and_allow_the_records(self):
        if not self.enforced:
            self.skipTest("this manager accepts the directives and applies none (the GitHub-hosted runner): the program refuses instead, see the next test")
        fixture = self.fixture()
        control = self.probe(["-p", "Environment=PYTHONDONTWRITEBYTECODE="], fixture)
        self.assertEqual(control, {"clone": "written", "other": "written", "unrelated": "written", "records": "written", "pycache": True, "helper": 7},
                         "without the directives the probe writes everywhere and the interpreter writes bytecode into the clone: the probe sees what the sandbox must stop")
        shutil.rmtree(fixture / "clone" / "__pycache__")
        for half, section in self.units().items():
            with self.subTest(half=half):
                confined = self.probe(self.properties(section, str(fixture / "records")), fixture)
                self.assertEqual(confined, {"clone": "EROFS", "other": "EROFS", "unrelated": "EROFS", "records": "written", "pycache": False, "helper": 7})

    def test_the_programs_check_agrees_with_what_the_manager_did(self):
        """Refused exactly when the probe could write: accepted under directives that were applied, refused under directives that were not, refused without them."""
        fixture = self.fixture()
        self.assertEqual(self.check(["-p", "Environment=PYTHONDONTWRITEBYTECODE="], fixture), 3, "without the directives the program is refused")
        for half, section in self.units().items():
            with self.subTest(half=half, enforced=self.enforced):
                properties = self.properties(section, str(fixture / "records"))
                wrote = self.probe(properties, fixture)["clone"] == "written"
                self.assertEqual(wrote, not self.enforced)
                self.assertEqual(self.check(properties, fixture), 3 if wrote else 0, "the check says what the file system does")


class RequireConfinedTests(unittest.TestCase):
    """daily_skill_usage.require_confined without a service manager: the file system is asked, and only a refused write passes."""

    def setUp(self):
        self.daily = daily_module()
        self._tmp = tempfile.TemporaryDirectory(prefix="skill-confined-")
        self.addCleanup(self._tmp.cleanup)
        self.directory = Path(self._tmp.name)

    @staticmethod
    def refusing(number):
        def opener(path, flags, mode=0o777):
            raise OSError(number, os.strerror(number))
        return opener

    def test_a_directory_where_a_file_can_be_created_refuses_the_run_and_the_probe_is_removed(self):
        with self.assertRaises(self.daily.Unconfined) as caught:
            self.daily.require_confined([self.directory])
        self.assertEqual(list(self.directory.iterdir()), [])
        self.assertEqual(str(caught.exception), UNCONFINED_MESSAGE[len("daily skill usage refused: "):-1])
        self.assertNotIn(str(self.directory), str(caught.exception))
        self.assertIsInstance(caught.exception, self.daily.Refused)

    def test_a_refused_write_is_what_confinement_looks_like(self):
        for number in (errno.EROFS, errno.EACCES, errno.EPERM):
            with self.subTest(errno=errno.errorcode[number]):
                self.assertIsNone(self.daily.require_confined([self.directory], opener=self.refusing(number)))
                self.assertEqual(list(self.directory.iterdir()), [], "nothing was created")

    @unittest.skipIf(os.geteuid() == 0, "root can create a file in a directory whose mode forbids it")
    def test_a_directory_whose_mode_forbids_the_write_passes(self):
        self.directory.chmod(0o500)
        self.addCleanup(self.directory.chmod, 0o700)
        self.assertIsNone(self.daily.require_confined([self.directory]))

    def test_an_error_that_says_nothing_about_confinement_refuses_the_run_without_naming_the_path(self):
        for number in (errno.ENOENT, errno.EIO, errno.ENOSPC, errno.EEXIST):
            with self.subTest(errno=errno.errorcode[number]):
                with self.assertRaises(ValueError) as caught:
                    self.daily.require_confined([self.directory], opener=self.refusing(number))
                self.assertNotIsInstance(caught.exception, self.daily.Refused)
                self.assertNotIn(str(self.directory), str(caught.exception))
        with self.assertRaises(ValueError):
            self.daily.require_confined([self.directory / "absent"])

    def test_a_file_that_already_has_the_probes_name_is_left_alone(self):
        for existing in ("regular", "link"):
            folder = self.directory / existing
            folder.mkdir()
            probe = folder / f".skill-usage-confinement-probe-{os.getpid()}"
            if existing == "regular":
                probe.write_text("not ours\n")
            else:
                (folder / "target").write_text("not ours\n")
                probe.symlink_to(folder / "target")
            with self.subTest(existing=existing):
                with self.assertRaises(ValueError) as caught:
                    self.daily.require_confined([folder])
                self.assertNotIsInstance(caught.exception, self.daily.Refused)
                self.assertTrue(probe.is_symlink() or probe.read_text() == "not ours\n")
                self.assertEqual((folder / "target").read_text() if existing == "link" else probe.read_text(), "not ours\n")

    def test_every_directory_is_asked_and_the_first_one_that_can_be_written_refuses(self):
        confined, open_dir = self.directory / "a", self.directory / "b"
        confined.mkdir()
        open_dir.mkdir()

        def opener(path, flags, mode=0o777):
            if str(path).startswith(str(confined)):
                raise OSError(errno.EROFS, "read-only")
            return os.open(path, flags, mode)
        with self.assertRaises(self.daily.Unconfined):
            self.daily.require_confined([confined, open_dir], opener=opener)
        self.assertEqual(list(open_dir.iterdir()), [])
        self.assertIsNone(self.daily.require_confined([confined], opener=opener))
        self.assertIsNone(self.daily.require_confined([]), "nothing to ask")


class ConfinementOptionTests(unittest.TestCase):
    """--refuse-writable: the check comes first, a refusal publishes nothing, and rendering the units (which writes by design) is not subject to it."""

    def setUp(self):
        self.daily = daily_module()
        self._tmp = tempfile.TemporaryDirectory(prefix="skill-confined-option-")
        self.addCleanup(self._tmp.cleanup)
        self.directory = Path(self._tmp.name)

    def run_main(self, *argv, **patches):
        errors, calls = io.StringIO(), []

        def work(*args, **kwargs):
            calls.append("work")
            raise AssertionError("work started")
        with mock.patch.object(self.daily, "require_reviewed_main", side_effect=work), mock.patch.object(self.daily, "collect_half", side_effect=work), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(errors):
            code = self.daily.main(list(argv))
        return code, errors.getvalue(), calls

    def test_an_unconfined_process_is_refused_before_any_work_and_publishes_nothing(self):
        out = self.directory / "claude.json"
        code, stderr, calls = self.run_main("--half", "claude", "--claude-root", "/fixture/root", "--now", NOW, "--out", str(out), "--refuse-writable", str(self.directory))
        self.assertEqual((code, stderr, calls), (2, UNCONFINED_MESSAGE, []))
        self.assertFalse(out.exists())
        self.assertEqual(sorted(path.name for path in self.directory.iterdir()), [], "the probe was removed")

    def test_a_confined_process_goes_on_to_the_work_and_each_directory_is_asked_first(self):
        order = []
        with mock.patch.object(self.daily, "require_confined", side_effect=lambda directories: order.append(("asked", [str(d) for d in directories]))), \
                mock.patch.object(self.daily, "require_reviewed_main", side_effect=lambda *a, **k: order.append(("reviewed", None))), \
                mock.patch.object(self.daily, "collect_half", return_value=claude_reports()), contextlib.redirect_stdout(io.StringIO()):
            code = self.daily.main(["--half", "claude", "--claude-root", "/fixture/root", "--now", NOW, "--out", str(self.directory / "claude.json"),
                                    "--refuse-writable", "/fixture/home", "--refuse-writable", "/fixture/clone"])
        self.assertEqual(code, 0)
        self.assertEqual(order, [("asked", ["/fixture/home", "/fixture/clone"]), ("reviewed", None)])

    def test_rendering_the_units_is_not_subject_to_the_check(self):
        destination = self.directory / "units"
        with mock.patch.object(self.daily, "require_reviewed_main"), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            code = self.daily.main(["--render-units", str(destination), "--repository", str(ROOT), "--refuse-writable", str(self.directory), "--node", sys.executable])
        self.assertEqual(code, 0)
        self.assertEqual(sorted(path.name for path in destination.iterdir()), sorted(self.daily.UNIT_FILES))


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
                    "GIT_AUTHOR_EMAIL": "fixture@users.noreply.github.com", "GIT_COMMITTER_EMAIL": "fixture@users.noreply.github.com"}
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
