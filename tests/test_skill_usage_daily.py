"""Counts-only daily native reports and rendered timer, with no live clients."""
import contextlib
import getpass
import importlib.util
import io
from datetime import datetime
import json
import os
from pathlib import Path
import re
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
            with mock.patch.object(daily, "hidden_by_private_tmp", return_value=False):   # systemd's parser is what is verified; a checkout in a temporary directory is refused by the layout rule, which has its own tests
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


def deep_report():
    """The input of Astra's read of c56121e4 (P1): one valid JSON value, 10,000 arrays nested around a 0, and a newline (20,002 bytes). `json.loads` raises RecursionError for it, which is neither a ValueError nor an
    OSError: the C scanner enters the recursion guard for every object and array it opens and propagates its error, and the Python decoder translates only StopIteration (python/cpython@cbc944f4bc59639a444dd971c737788ba2283a91,
    Modules/_json.c L1031-L1046, Lib/json/decoder.py L360-L363)."""
    return "[" * 10000 + "0" + "]" * 10000 + "\n"


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
        ("claude", "the claude groups are an array", lambda h, c, l: l.update(groups=[]), {"claude": False}),
        ("claude", "the spawn groups are an array", lambda h, c, l: l.update(groups={"by_spawn_and_agent_type": []}), {"claude": False}),
        ("claude", "a spawn's agents are an array", lambda h, c, l: l.update(groups={"by_spawn_and_agent_type": {"workflow": []}}), {"claude": False}),
        ("claude", "the main lane is an array", lambda h, c, l: l.update(main=[]), {"claude": False}),
        ("codex", "the host's codex state is an array", lambda h, c, l: h.update(codex=[]), {"codex": False}),
        ("codex", "the codex groups are an array", lambda h, c, l: c.update(groups=[]), {"codex": False}),
        ("codex", "the workers_by_role groups are an array", lambda h, c, l: c["groups"].update(workers_by_role=[]), {"codex": False}),
        ("codex", "the workers_by_kind groups are a string", lambda h, c, l: c["groups"].update(workers_by_kind="worker"), {"codex": False}),
        ("codex", "the workers group is an array", lambda h, c, l: c["groups"].update(workers=[]), {"codex": False}),
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

    LANE_CASES = (
        ("claude", "groups and main are arrays", lambda l: l.update(groups=[], main=[])),
        ("claude", "groups is an array", lambda l: l.update(groups=[])),
        ("claude", "the spawn groups are an array", lambda l: l["groups"].update(by_spawn_and_agent_type=[])),
        ("claude", "a spawn's agents are an array", lambda l: l["groups"].update(by_spawn_and_agent_type={"workflow": []})),
        ("claude", "an agent's counts are an array", lambda l: l["groups"]["by_spawn_and_agent_type"]["workflow"]["security-reviewer"].update(skill_calls=[])),
        ("claude", "main has no counts", lambda l: l.update(main={})),
        ("codex", "groups is an array", lambda l: l.update(groups=[])),
        ("codex", "the workers group has no counts", lambda l: l["groups"]["workers"].pop("skill_md_reads")),
        ("codex", "workers_by_role is an array", lambda l: l["groups"].update(workers_by_role=[])),
    )

    def test_a_lanes_report_with_a_container_of_the_wrong_shape_is_never_published_as_measured(self):
        """Review of #1043 at 9caafa601 (P2): the lanes report of the right kind was a measured success whatever its containers, so `groups: []` published `measured.claude: true` with no lane."""
        daily = daily_module()
        for half, label, change in self.LANE_CASES:
            host, codex, claude = claude_reports() if half == "claude" else codex_reports()
            report = claude if half == "claude" else codex
            change(report)
            key = "claude" if half == "claude" else "codex"
            with self.subTest(half=half, case=label):
                projected = daily.project_reports(host, codex, claude, now=NOW, window=7, half=half)
                self.assertIs(projected["measured"][key], False)
                self.assertEqual([row for row in projected["lanes"] if row["client"] == key], [], "no lane of a report that cannot be read is published")
                notes = daily.unusable_reports(codex, claude)
                self.assertEqual(len(notes), 1)
                self.assertNotIn("/", notes[0])
        for half in ("claude", "codex"):          # a valid empty object is not a malformed one
            host, codex, claude = claude_reports() if half == "claude" else codex_reports()
            report = claude if half == "claude" else codex
            report["groups"] = {"by_spawn_and_agent_type": {}} if half == "claude" else {}
            if half == "claude":
                report["main"] = {"skill_calls": {}}
            with self.subTest(half=half, case="valid and empty"):
                self.assertIs(daily.project_reports(host, codex, claude, now=NOW, window=7, half=half)["measured"][half], True)
                self.assertEqual(daily.unusable_reports(codex, claude), [])

    def test_the_command_line_publishes_a_malformed_lanes_report_as_not_measured_with_a_fixed_reason(self):
        copy = self.copied_tool()
        daily_path = copy / "tools/skill-usage/daily_skill_usage.py"
        account, home = getpass.getuser(), str(Path.home())
        destination = Path(tempfile.mkdtemp(prefix="skill-lane-out-"))
        self.addCleanup(shutil.rmtree, destination, True)
        for half, label, change in self.LANE_CASES:
            host, codex, claude = claude_reports() if half == "claude" else codex_reports()
            report = claude if half == "claude" else codex
            change(report)
            (copy / "host.json").write_text(json.dumps(host))
            (copy / "lanes.json").write_text(json.dumps(report))
            own, combined = destination / "own.json", destination / "combined.json"
            for stale in (own, combined):
                stale.unlink(missing_ok=True)
            flag = "--claude-lanes-report" if half == "claude" else "--codex-lanes-report"
            with self.subTest(half=half, case=label):
                done = subprocess.run([sys.executable, "-B", str(daily_path), "--half", half, "--host-report", str(copy / "host.json"), flag, str(copy / "lanes.json"), "--now", NOW,
                                       "--out", str(own), "--combined-out", str(combined)], capture_output=True, text=True, timeout=60)
                self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
                self.assertNotIn("Traceback", done.stderr)
                self.assertNotIn(account, done.stderr)
                self.assertNotIn(home, done.stderr)
                self.assertEqual(done.stderr.strip().splitlines(), [f"daily skill usage: the {half.capitalize()} lanes report has a container of the wrong shape; its half is read as not measured"])
                self.assertIs(json.loads(own.read_text())["measured"][half], False)
                self.assertIs(json.loads(combined.read_text())["measured"][half], False, "no falsely measured combined publication")

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

    def test_a_report_file_nested_beyond_the_decoders_limit_is_a_fixed_diagnostic_and_names_nothing(self):
        """Astra's read of c56121e4 (P1): the handler of `main` listed ValueError and OSError, and the decoder's RecursionError is neither, so `--host-report` of a 20,002-byte file ended in a traceback with six
        occurrences of the account's name. The same fixed line as any other report the program cannot read, whichever of the three report options carries the file; a valid empty report and an ordinary malformed
        one are the controls."""
        deep = deep_report()
        with self.assertRaises(RecursionError):
            json.loads(deep)   # the fixture is deeper than this interpreter's limit; an interpreter that decodes it needs a deeper one
        copy = self.copied_tool()
        daily_path = copy / "tools/skill-usage/daily_skill_usage.py"
        account, home = getpass.getuser(), str(Path.home())
        files = Path(tempfile.mkdtemp(prefix="skill-deep-"))
        self.addCleanup(shutil.rmtree, files, True)
        fixed = "daily skill usage unavailable; inspect the native collector separately\n"
        for name, text, expected in (("nested beyond the limit", deep, (2, "", fixed)), ("malformed text", "[\n", (2, "", fixed)), ("a valid empty report", "{}\n", (1, None, ""))):
            report = files / "report.json"
            report.write_text(text)
            for option in ("--host-report", "--codex-lanes-report", "--claude-lanes-report"):
                with self.subTest(report=name, option=option):
                    done = subprocess.run([sys.executable, "-B", str(daily_path), option, str(report), "--now", NOW], capture_output=True, text=True, timeout=60)
                    self.assertEqual((done.returncode, done.stderr), (expected[0], expected[2]), done.stdout[:200])
                    if expected[1] is not None:
                        self.assertEqual(done.stdout, expected[1], "nothing is published or printed for a report that cannot be read")
                    for stream in (done.stdout, done.stderr):
                        self.assertNotIn("Traceback", stream)
                        self.assertNotIn(account, stream)
                        self.assertNotIn(home, stream)
                        self.assertNotIn(str(files), stream, "the path of the supplied file is not echoed")

    FIXED_UNAVAILABLE = "daily skill usage unavailable; inspect the native collector separately\n"
    FIXED_ARGUMENT = "daily skill usage refused: the command line has an argument this version does not take, or lacks one it needs; nothing was run\n"

    def hostile_inputs(self):
        """The inputs of the daily command line that another process or a person chooses, one entry per surface: (label, extra arguments, report text or None, report option, expected exit status or None for any,
        expected stderr or None for 'only lines of the program's own'). The two --now values are the reviewers' (Astra's read of 0383243e, P1); the deeply nested arrays are the read of c56121e4."""
        fixed, argument = self.FIXED_UNAVAILABLE, self.FIXED_ARGUMENT
        deep, deep_objects, big_int = "[" * 10000 + "0" + "]" * 10000 + "\n", '{"a":' * 5000 + "0" + "}" * 5000, "1" + "0" * 5000
        now = ["--now", NOW]
        cases = [(f"--now {value!r}", ["--now", value], "{}", "--host-report", code, expected_stderr) for value, code, expected_stderr in (
            ("0001-01-01T00:00:00+01:00", 2, fixed), ("9999-12-31T23:59:59-01:00", 2, fixed), ("2026-13-45T99:99:99", 2, fixed), ("tomorrow", 2, fixed), ("2026-10-12T10:00:00+25:00", 2, fixed),
            ("2026-10-12", None, None), ("", None, None))]
        cases += [(f"--window {value}", ["--window", value, *now], "{}", "--host-report", 2, expected) for value, expected in
                  (("0", fixed), ("-1", fixed), ("367", fixed), ("99999999999999999999999999", fixed), ("x", argument))]
        cases += [(f"--claude-timeout {value}", ["--claude-timeout", value, "--half", "claude", "--claude-root", "/fixture/root", *now], "{}", "--host-report", 2, fixed) for value in ("0", "-5", "3601", "99999999999999999999")]
        for label, report in (("deeply nested arrays", deep), ("deeply nested objects", deep_objects), ("a big integer", '{"skills":[{"name":"gh-fix-ci","claude":{"uses":' + big_int + "}}]}"),
                              ("infinity", '{"window_days": 1e999}'), ("NaN", '{"window_days": NaN}'), ("a long string", '{"kind":"' + "x" * 200_000 + '"}'), ("not JSON", "[\n"), ("empty", ""),
                              ("a lone surrogate", '{"kind":"\\ud800"}')):
            for option in ("--host-report", "--codex-lanes-report", "--claude-lanes-report"):
                unreadable = label in ("deeply nested arrays", "a big integer", "not JSON", "empty")
                cases.append((f"{option}: {label}", list(now), report, option, 2 if unreadable else None, fixed if unreadable else None))
        return cases

    def test_no_input_of_the_command_line_ends_in_a_traceback_or_names_the_account(self):
        """The class, not the instance (the command center's route decision on #1043, 2026-10-13): three reads of this boundary found three exception classes that the handler's enumeration did not list
        (ValueError, then RecursionError, then OverflowError). Every option and the three report options are driven with hostile values, from a copy of the program under the home directory, where a traceback names
        the account: a refusal is the fixed line and exit 2, and nothing ends in a traceback."""
        copy = self.copied_tool()
        program = copy / "tools/skill-usage/daily_skill_usage.py"
        account, home = getpass.getuser(), str(Path.home())
        files = Path(tempfile.mkdtemp(prefix="skill-hostile-"))
        self.addCleanup(shutil.rmtree, files, True)
        report = files / "report.json"
        cases = self.hostile_inputs()
        self.assertEqual(len(cases), 43, "every surface of the list is driven")
        for label, extra, text, option, code, expected_stderr in cases:
            argv = [sys.executable, "-B", str(program), *extra]
            if text is not None:
                report.write_text(text, encoding="utf-8", errors="surrogatepass")
                argv += [option, str(report)]
            with self.subTest(case=label):
                done = subprocess.run(argv, capture_output=True, text=True, timeout=120)
                self.assertNotIn("Traceback", done.stderr)
                for stream in (done.stdout, done.stderr):
                    self.assertNotIn(account, stream)
                    self.assertNotIn(home, stream)
                    self.assertNotIn(str(files), stream)
                if code is not None:
                    self.assertEqual(done.returncode, code, done.stderr[:200])
                if expected_stderr is not None:
                    self.assertEqual(done.stderr, expected_stderr)
                for line in done.stderr.splitlines():
                    self.assertTrue(line.startswith("daily skill usage"), "only the program's own lines: " + line[:60])

    def test_a_timestamp_whose_conversion_to_utc_overflows_is_a_fixed_diagnostic_and_a_value_error(self):
        """Astra's read of 0383243e (P1): datetime.astimezone subtracts the offset and raises OverflowError for 0001-01-01T00:00:00+01:00 and 9999-12-31T23:59:59-01:00 (python/cpython@cbc944f4bc59639a444dd971c737788ba2283a91
        Modules/_datetimemodule.c L6510-L6515 and L805-L808; Lib/_pydatetime.py L2034 and L2230). parse_iso reports it as the ValueError of any unusable timestamp, with no value in its text."""
        for value in ("0001-01-01T00:00:00+01:00", "9999-12-31T23:59:59-01:00", "0001-01-01T00:00:00+23:59", "9999-12-31T23:59:59.999999-23:59"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError) as caught:
                    usage.parse_iso(value)
                self.assertNotIsInstance(caught.exception, OverflowError)
                self.assertNotIn(value[:10], str(caught.exception), "the text of the error holds no part of the argument")
        for value in ("2026-10-12T10:00:00Z", "2026-10-12T10:00:00+00:00", "0001-01-01T00:00:00+00:00", "9999-12-31T23:59:59-00:00", "0001-01-01T00:00:00", "9999-12-31T23:59:59"):
            with self.subTest(still_valid=value):
                self.assertIsNotNone(usage.parse_iso(value))
        daily = daily_module()
        errors = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(errors):
            code = daily.main(["--host-report", "/dev/null", "--now", "0001-01-01T00:00:00+01:00"])
        self.assertEqual((code, errors.getvalue()), (2, self.FIXED_UNAVAILABLE))

    def test_a_stored_half_whose_time_is_out_of_range_is_an_invalid_record(self):
        daily = daily_module()
        for stamp in ("0001-01-01T00:00:00+01:00", "9999-12-31T23:59:59-01:00"):
            record = projected("codex")
            record["generated_at"] = stamp
            with self.subTest(stamp=stamp):
                self.assertIsNone(daily.half_record(record, "codex"))
                merged = daily.merge_halves(projected("claude"), record)
                self.assertEqual(merged["measured"], {"host": True, "codex": False, "claude": True})
                self.assertIsNone(merged["halves"]["codex"])

    def test_an_exception_nobody_listed_is_the_fixed_diagnostic_at_both_boundaries(self):
        """The handlers were enumerations. Any Exception a collaborator raises, of any class, is the fixed line without its text and a traceback (main) or an unmeasured slot (collect_half)."""
        daily = daily_module()

        class Unforeseen(Exception):
            pass
        out = Path(tempfile.mkdtemp(prefix="skill-unforeseen-")) / "never.json"
        self.addCleanup(shutil.rmtree, out.parent, True)
        for error in (Unforeseen("SENTINEL-TEXT"), RuntimeError("SENTINEL-TEXT"), OverflowError("SENTINEL-TEXT"), ZeroDivisionError("SENTINEL-TEXT"), UnicodeEncodeError("ascii", "x", 0, 1, "SENTINEL-TEXT"),
                      MemoryError("SENTINEL-TEXT"), RecursionError("SENTINEL-TEXT")):
            errors = io.StringIO()
            with self.subTest(error=type(error).__name__), mock.patch.object(daily, "require_reviewed_main"), mock.patch.object(daily, "collect_half", return_value=claude_reports()), \
                    mock.patch.object(daily, "project_reports", side_effect=error), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(errors):
                code = daily.main(["--half", "claude", "--claude-root", "/fixture/root", "--now", NOW, "--out", str(out)])
            self.assertEqual((code, errors.getvalue()), (2, self.FIXED_UNAVAILABLE))
            self.assertFalse(out.exists())
        now = usage.parse_iso("2026-10-12T10:00:00Z")
        host, _, lanes = claude_reports()
        for error in (Unforeseen("SENTINEL-TEXT"), RuntimeError("SENTINEL-TEXT"), OverflowError("SENTINEL-TEXT"), KeyError("SENTINEL-TEXT")):
            calls = []

            def runner(command, **kwargs):
                calls.append(command)
                if len(calls) == 1:
                    raise error
                return subprocess.CompletedProcess(command, 0, json.dumps(lanes), "")
            with self.subTest(collect_half_error=type(error).__name__):
                reports = daily.collect_half("claude", [Path("/fixture/claude")], window=7, now=now, runner=runner)
                self.assertEqual(len(calls), 2, "the second command still runs")
                self.assertIsNone(reports[0], "the slot of the command that raised is unmeasured")
                self.assertIsInstance(reports[2], dict, "the other command's report is kept")

    def test_a_stored_other_record_nested_beyond_the_decoders_limit_is_an_absent_half_not_a_failed_refresh(self):
        """The follow-up that round 7 recorded, closed with the class: a stored record that cannot be read, of whatever kind, is an absent half and the combined record is published, as for text that is not JSON."""
        daily = daily_module()
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            stored = directory / "codex.json"
            for label, content in (("nested arrays", "[" * 10000 + "0" + "]" * 10000), ("nested objects", '{"a":' * 5000 + "0" + "}" * 5000), ("text that is not JSON", "[\n")):
                stored.write_text(content)
                combined = directory / "combined.json"
                combined.unlink(missing_ok=True)
                with self.subTest(record=label):
                    self.assertTrue(daily.refresh_combined(combined, projected("claude"), stored))
                    self.assertEqual(json.loads(combined.read_text())["measured"], {"host": True, "codex": False, "claude": True})

    def test_a_native_output_nested_beyond_the_decoders_limit_leaves_only_its_own_slot_unmeasured(self):
        """The same defect at the other place a report is decoded: `collect_half` read each native command's output with `json.loads` and caught ValueError, so the deep output of one command raised out of the
        collection and the half had no record at all. It is an unusable report: that slot is None (unmeasured) and the other command's report is kept. A valid empty object and ordinary malformed text are the controls."""
        daily = daily_module()
        now = usage.parse_iso("2026-10-12T10:00:00Z")
        host, _, lanes = claude_reports()
        codex_host, codex_lanes, _ = codex_reports()
        deep = deep_report()
        with self.assertRaises(RecursionError):
            json.loads(deep)
        for half, roots in (("claude", [Path("/fixture/claude")]), ("codex", [Path("/fixture/codex")])):
            plan = daily.half_plan(half, roots, window=7, now=now)
            slots = [slot for slot, _, _, _ in plan]
            self.assertEqual(len(slots), 2)
            for name, text in (("nested beyond the limit", deep), ("malformed text", "[\n"), ("a valid empty object", "{}\n")):
                calls = []

                def runner(command, **kwargs):
                    key = next((flag for flag in ("--run-skill-doctor", "--lanes-sweep", "--lanes") if flag in command), None)
                    payload = {"--run-skill-doctor": host, "--lanes-sweep": lanes, "--lanes": codex_lanes}.get(key, codex_host)
                    calls.append(command)
                    return subprocess.CompletedProcess(command, 0, text if len(calls) == 1 else json.dumps(payload), "")
                with self.subTest(half=half, first_command_answers=name):
                    reports = dict(zip(("host", "codex", "claude"), daily.collect_half(half, roots, window=7, now=now, runner=runner)))
                    self.assertEqual(len(calls), 2, "the second command still runs")
                    self.assertIsNone(reports[slots[0]], "an output that cannot be used leaves its slot unmeasured")
                    self.assertIsInstance(reports[slots[1]], dict, "the other command's report is kept")


RECORD_KEYS = {"schema", "half", "generated_at", "window_days", "host", "lanes", "zero_use", "codex_bulk_scan_limit", "halves", "measured", "name", "claude_uses_lifetime", "wiring", "codex_use", "codex_skill_md_reads",
               "codex_name_mentions", "client", "lane", "metric", "skills", "count", "raw_reads", "claude", "codex", "claude_host_lifetime"}
RECORD_WORDS = {"skill-invoke-rate-daily/1", "claude", "codex", "all", "use", "skill_calls"}
PRIVATE = "PRIVATE-MARKER"
HOSTILE = (("an object", {"prompt": f"/fixture/{PRIVATE}/prompt", "path": f"/fixture/{PRIVATE}/path"}), ("a list", [f"/fixture/{PRIVATE}/item"]), ("a path", f"/fixture/{PRIVATE}/value"),
           ("a negative number", -1), ("a float", 1.5), ("a boolean", True), ("a huge number", 10 ** 30), ("a short word", "wired"), ("null", None),
           ("a time that does not exist", "9999-99-99T99:99:99Z"), ("a time with another separator", "2026-10-12 10:00:00"), ("a time with a slash", "2026-10-12/10:00:00"),
           ("a name with a space", f"{PRIVATE} text"), ("a long word", "w" * 400))


def leaf_paths(value, path=()):
    """Every scalar of a JSON structure, as the path of keys and indexes that leads to it, and every object as a path too (for a key to be added to)."""
    if isinstance(value, dict):
        yield path, "object"
        for key, item in value.items():
            yield from leaf_paths(item, path + (key,))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from leaf_paths(item, path + (index,))
    else:
        yield path, "leaf"


def with_value(structure, path, value, *, key=None):
    """A copy of `structure` with the scalar at `path` replaced by `value`, or, with `key`, with that key added (to the object at `path`) holding `value`."""
    copy = json.loads(json.dumps(structure))
    cursor = copy
    for step in path[:-1] if key is None else path:
        cursor = cursor[step]
    if key is None:
        cursor[path[-1]] = value
    else:
        cursor[key] = value
    return copy


def assert_counts_only(case, value, where="record"):
    """The independent statement of the contract: only keys of the schema, and leaves that are null, a boolean, a non-negative integer, a name of the allowed pattern, a timestamp or one of the fixed words."""
    if isinstance(value, dict):
        for key, item in value.items():
            case.assertIn(key, RECORD_KEYS, f"{where}: a key outside the schema")
            assert_counts_only(case, item, f"{where}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            assert_counts_only(case, item, f"{where}[{index}]")
    elif value is None or isinstance(value, bool):
        pass
    elif isinstance(value, int):
        case.assertGreaterEqual(value, 0, where)
    else:
        case.assertIsInstance(value, str, where)
        if value in RECORD_WORDS or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,100}", value):
            return
        case.assertRegex(value, r"\d{4}-\d{2}-\d{2}T[0-9:.]+(?:Z|[+-]\d{2}:\d{2})", f"{where}: a string that is no name, word or time")
        datetime.fromisoformat(value.replace("Z", "+00:00"))   # raises for a time that does not exist


def assert_times(case, record):
    """The time-typed fields hold a time that exists, in the program's own spelling: a string that merely has the shape of a name is not accepted there."""
    stamps = [record.get("generated_at"), *(record.get("halves") or {}).values()] if isinstance(record, dict) else []
    for stamp in stamps:
        if stamp is not None:
            case.assertRegex(stamp, r"^\d{4}-\d{2}-\d{2}T[0-9:.]+(?:Z|[+-]\d{2}:\d{2})$")
            datetime.fromisoformat(stamp.replace("Z", "+00:00"))


class ClosedRecordTests(unittest.TestCase):
    """The command center's design decision on #1043 (2026-10-13), after Astra's read of c23b9ce48 found a scalar of the native report copied into the record without its check (the second field of that kind
    after a lane's own fields): the record is written through one closed-schema check (render_record), so that no field depends on its producer having validated it."""

    def test_every_scalar_the_projection_reads_is_checked_whatever_it_holds(self):
        daily = daily_module()
        checked = 0
        for half, reports in (("claude", claude_reports()), ("codex", codex_reports())):
            for index, native in enumerate(reports):
                if native is None:
                    continue
                for path, kind in list(leaf_paths(native)):
                    variants = [("replaced by " + label, with_value(native, path, value)) for label, value in HOSTILE] if kind == "leaf" else []
                    variants += [(f"gains a key holding {label}", with_value(native, path, value, key=f"/fixture/{PRIVATE}/key")) for label, value in HOSTILE[:3]] if kind == "object" else []
                    for label, changed in variants:
                        arguments = list(reports)
                        arguments[index] = changed
                        report = daily.project_reports(*arguments, now=NOW, window=7, half=half)
                        written = daily.render_record(report)
                        checked += 1
                        with self.subTest(half=half, native=index, path="/".join(map(str, path)), case=label):
                            self.assertNotIn(PRIVATE, written)
                            assert_counts_only(self, json.loads(written))
                            assert_times(self, json.loads(written))
        self.assertGreater(checked, 300, "the corpus covers every scalar of the fixtures")

    def test_every_scalar_of_a_stored_half_is_checked_in_the_merge(self):
        daily = daily_module()
        halves = {"claude": projected("claude"), "codex": projected("codex")}
        checked = 0
        for name, record in halves.items():
            for path, kind in list(leaf_paths(record)):
                variants = [("replaced by " + label, with_value(record, path, value)) for label, value in HOSTILE] if kind == "leaf" else \
                           [(f"gains a key holding {label}", with_value(record, path, value, key=f"/fixture/{PRIVATE}/key")) for label, value in HOSTILE[:3]]
                for label, changed in variants:
                    arguments = {"claude": halves["claude"], "codex": halves["codex"]}
                    arguments[name] = changed
                    written = daily.render_record(daily.merge_halves(arguments["claude"], arguments["codex"]))
                    checked += 1
                    with self.subTest(half=name, path="/".join(map(str, path)), case=label):
                        self.assertNotIn(PRIVATE, written)
                        assert_counts_only(self, json.loads(written))
                        assert_times(self, json.loads(written))
        self.assertGreater(checked, 150)

    def test_the_schema_holds_without_the_producers_checks(self):
        """The layer itself: a record whose every scalar is replaced, one at a time, by a hostile value is written through the check without anyone having validated it (the producers' own checks are not in
        the path), for the record of each half and for the combined record."""
        daily = daily_module()
        records = {"claude half": projected("claude"), "codex half": projected("codex"), "combined": daily.merge_halves(projected("claude"), projected("codex"))}
        checked = 0
        for name, record in records.items():
            self.assertEqual(json.loads(daily.render_record(record)), json.loads(json.dumps(record)), "a record the program builds itself is not changed by the check")
            for path, kind in list(leaf_paths(record)):
                variants = [("replaced by " + label, with_value(record, path, value)) for label, value in HOSTILE] if kind == "leaf" else \
                           [(f"gains a key holding {label}", with_value(record, path, value, key=f"/fixture/{PRIVATE}/key")) for label, value in HOSTILE[:3]]
                for label, changed in variants:
                    written = daily.render_record(changed)
                    checked += 1
                    with self.subTest(record=name, path="/".join(map(str, path)), case=label):
                        self.assertNotIn(PRIVATE, written)
                        assert_counts_only(self, json.loads(written))
                        assert_times(self, json.loads(written))
        self.assertGreater(checked, 400)

    def test_both_outputs_are_the_checked_rendering_of_whatever_the_projection_returns(self):
        """The check stands at the place that writes, not in the projection: a report that the projection returns with a field of its own is written without it, to stdout and to the file."""
        daily = daily_module()
        hostile = projected("codex")
        hostile["codex_bulk_scan_limit"] = {"prompt": f"/fixture/{PRIVATE}/prompt"}
        hostile["extra_field"] = f"/fixture/{PRIVATE}/extra"
        hostile["host"][0]["name"] = f"/fixture/{PRIVATE}/name"
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            (directory / "host.json").write_text("{}")
            for label, extra, file_output in (("standard output", [], False), ("the file", ["--out", str(directory / "record.json")], True)):
                out = io.StringIO()
                with self.subTest(output=label), mock.patch.object(daily, "project_reports", return_value=hostile), contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
                    daily.main(["--half", "codex", "--host-report", str(directory / "host.json"), "--now", NOW, *extra])
                    written = (directory / "record.json").read_text() if file_output else out.getvalue()
                    self.assertNotIn(PRIVATE, written)
                    self.assertEqual(written, daily.render_record(hostile))
                    self.assertNotIn("extra_field", json.loads(written))

    def test_the_policy_scalar_of_the_native_report_is_a_count_through_both_outputs(self):
        """Astra's read of c23b9ce48 (P1): `codex_use_policy.max_distinct_skill_reads` was copied into the record whatever it held; the record then carried an object with a prompt and a path, to stdout and to the file."""
        daily = daily_module()
        host, lanes, _ = codex_reports()
        for label, value in HOSTILE + (("a valid count", 25),):
            changed = json.loads(json.dumps(host))
            changed["codex_use_policy"] = {"max_distinct_skill_reads": value}
            projected_limit = daily.project_reports(changed, lanes, None, now=NOW, window=7, half="codex")["codex_bulk_scan_limit"]
            self.assertEqual(projected_limit, 25 if label == "a valid count" else None, "the projection validates the scalar itself, before the output check")
            with self.subTest(policy=label), tempfile.TemporaryDirectory() as temp:
                directory = Path(temp)
                (directory / "host.json").write_text(json.dumps(changed))
                (directory / "lanes.json").write_text(json.dumps(lanes))
                out = io.StringIO()
                with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
                    daily.main(["--half", "codex", "--host-report", str(directory / "host.json"), "--codex-lanes-report", str(directory / "lanes.json"), "--now", NOW])
                self.assertNotIn(PRIVATE, out.getvalue())
                expected = 25 if label == "a valid count" else None
                self.assertEqual(json.loads(out.getvalue())["codex_bulk_scan_limit"], expected)
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    daily.main(["--half", "codex", "--host-report", str(directory / "host.json"), "--codex-lanes-report", str(directory / "lanes.json"), "--now", NOW,
                                "--out", str(directory / "record.json")])
                written = (directory / "record.json").read_text()
                self.assertNotIn(PRIVATE, written)
                self.assertEqual(json.loads(written)["codex_bulk_scan_limit"], expected)

    def test_the_file_and_the_standard_output_are_one_rendering_and_the_check_precedes_any_write(self):
        daily = daily_module()
        report = projected("claude")
        report["codex_bulk_scan_limit"] = {"prompt": f"/fixture/{PRIVATE}/prompt"}
        report["extra_field"] = f"/fixture/{PRIVATE}/extra"
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "record.json"
            daily.publish(target, report)
            written = target.read_text()
        self.assertEqual(written, daily.render_record(report))
        self.assertNotIn(PRIVATE, written)
        self.assertNotIn("extra_field", json.loads(written), "a key outside the schema is dropped")
        self.assertIsNone(json.loads(written)["codex_bulk_scan_limit"])
        self.assertEqual(daily.render_record(projected("claude")), json.dumps(projected("claude"), indent=2, sort_keys=True) + "\n", "a record the program writes itself is unchanged by the check")

    def test_a_measured_flag_that_is_not_true_is_false_and_a_count_beyond_reason_is_unknown(self):
        daily = daily_module()
        report = projected("codex")
        report["measured"] = {"codex": "yes"}
        report["window_days"] = 10 ** 30
        written = json.loads(daily.render_record(report))
        self.assertEqual(written["measured"], {"codex": False})
        self.assertIsNone(written["window_days"])


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

    def test_the_codex_lanes_come_first_so_the_fleet_readers_cut_of_the_lane_list_keeps_them(self):
        """Review of #1043 at da4895b5 (the local codex review, P2): the combined record listed the Claude lanes first and the Fleet reader keeps only the first 200 (`_skill_usage`: `lanes[:200]`). The Claude half
        alone held 564 lanes in the end-to-end run of 2026-10-13, so every Codex lane was cut although `measured.codex` was true. The single record that the split replaced emitted the Codex lanes first."""
        daily = daily_module()
        claude, codex = self.projected("claude"), self.projected("codex")
        claude["lanes"] = [*claude["lanes"], *({"client": "claude", "lane": f"workflow:agent-{number}", "metric": "skill_calls", "skills": []} for number in range(564))]
        combined = daily.merge_halves(claude, codex)
        self.assertGreater(len(combined["lanes"]), 200)
        self.assertEqual([lane["client"] for lane in combined["lanes"][:len(codex["lanes"])]], ["codex"] * len(codex["lanes"]), "the Codex lanes lead")
        page = fleet_data._skill_usage(json.loads(json.dumps(combined)))
        self.assertEqual(len(page["lanes"]), 200)
        self.assertEqual({lane["lane"] for lane in page["lanes"] if lane["client"] == "codex"}, {lane["lane"] for lane in codex["lanes"]}, "every Codex lane survives the reader's cut")

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

    def test_a_stored_half_cannot_carry_extra_fields_into_the_combined_record(self):
        """The local codex re-review of 0383243e (P2): a stored half is a file another process wrote, and its lanes were copied whole, so a `prompt` or a `path` in a lane or a skill, and counts that are not
        counts, reached the published combined record, which is names and counts only. Lanes and skills are rebuilt from the fields the projection writes."""
        daily = daily_module()
        codex, claude = projected("codex"), projected("claude")
        for record, client in ((codex, "codex"), (claude, "claude")):
            lane = record["lanes"][0]
            lane.update(prompt="MARKER-PROMPT", path="/fixture/transcript.jsonl", extra={"text": "MARKER-NESTED"})
            lane["skills"][0].update(prompt="MARKER-SKILL-PROMPT", path="/fixture/skill", count="many")
            lane["skills"] += [{"name": "x y", "count": 1, "text": "MARKER-NOT-A-NAME"}, "not an object"]
            record["lanes"] += [{"client": client, "lane": "MARKER lane name!", "skills": []}, {"client": client, "lane": "no-skills", "skills": "MARKER-TEXT"}, {"client": "other", "lane": "foreign", "skills": []}]
        merged = daily.merge_halves(claude, codex)
        published = json.dumps(merged)
        for marker in ("MARKER", "/fixture/transcript.jsonl", "/fixture/skill", "no-skills", "foreign"):
            self.assertNotIn(marker, published)
        self.assertTrue(merged["lanes"])
        for lane in merged["lanes"]:
            self.assertEqual(sorted(lane), ["client", "lane", "metric", "skills"])
            self.assertEqual(lane["metric"], "use" if lane["client"] == "codex" else "skill_calls")
            for skill in lane["skills"]:
                self.assertLessEqual(set(skill), {"name", "count", "raw_reads"})
                self.assertTrue(skill["count"] is None or (isinstance(skill["count"], int) and not isinstance(skill["count"], bool) and skill["count"] >= 0))
        self.assertIsNone([lane for lane in merged["lanes"] if lane["client"] == "codex"][0]["skills"][0]["count"], "a count that is not a count is unknown")
        self.assertEqual(daily.merge_halves(projected("claude"), projected("codex"))["lanes"], projected("codex")["lanes"] + projected("claude")["lanes"], "a record the halves write themselves crosses unchanged")

    def test_a_stored_half_with_extra_fields_publishes_a_counts_only_combined_file(self):
        daily = daily_module()
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            stored = projected("codex")
            stored["lanes"][0].update(prompt="MARKER-PROMPT")
            (directory / "codex.json").write_text(json.dumps(stored))
            self.assertTrue(daily.refresh_combined(directory / "combined.json", projected("claude"), directory / "codex.json"))
            published = (directory / "combined.json").read_text()
            self.assertNotIn("MARKER-PROMPT", published)
            self.assertEqual(json.loads(published)["measured"], {"host": True, "codex": True, "claude": True})

    def test_halves_of_different_windows_are_never_merged_under_one_window(self):
        """The local codex re-review of 0383243e (P2): the combined record has one `window_days`, which the Fleet page uses to label every windowed count, and it took the Claude half's, so a Codex run of
        `--window 30` beside a stored Claude half of 7 days published 30-day counts as seven-day counts. The later record stands and the other half is absent, unmeasured."""
        daily = daily_module()
        for label, claude_window, codex_window, claude_at, codex_at, expected in (
                ("a later Codex half of 30 beside a Claude half of 7", 7, 30, "2026-10-12T10:00:00+00:00", "2026-10-12T10:05:00+00:00", (30, {"host": False, "codex": True, "claude": False})),
                ("a later Claude half of 7 beside a Codex half of 30", 7, 30, "2026-10-12T10:05:00+00:00", "2026-10-12T10:00:00+00:00", (7, {"host": True, "codex": False, "claude": True})),
                ("the same window", 30, 30, "2026-10-12T10:05:00+00:00", "2026-10-12T10:00:00+00:00", (30, {"host": True, "codex": True, "claude": True})),
                ("no window on the Claude half", None, 7, "2026-10-12T10:00:00+00:00", "2026-10-12T10:05:00+00:00", (7, {"host": False, "codex": True, "claude": False})),
                ("the same time", 7, 30, "2026-10-12T10:00:00+00:00", "2026-10-12T10:00:00+00:00", (7, {"host": True, "codex": False, "claude": True}))):
            claude, codex = projected("claude"), projected("codex")
            claude.update(window_days=claude_window, generated_at=claude_at)
            codex.update(window_days=codex_window, generated_at=codex_at)
            with self.subTest(case=label):
                merged = daily.merge_halves(claude, codex)
                self.assertEqual((merged["window_days"], merged["measured"]), expected)
                dropped = "codex" if expected[1]["codex"] is False else "claude" if expected[1]["claude"] is False else None
                if dropped:
                    self.assertIsNone(merged["halves"][dropped])
                    self.assertFalse([lane for lane in merged["lanes"] or [] if lane["client"] == dropped], "nothing of the dropped half crosses")

    def test_a_refresh_does_not_merge_a_stored_half_of_another_window(self):
        daily = daily_module()
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            stored = projected("claude")
            stored.update(window_days=7, generated_at="2026-10-12T09:00:00+00:00")
            (directory / "claude.json").write_text(json.dumps(stored))
            own = projected("codex")
            own.update(window_days=30, generated_at="2026-10-12T10:00:00+00:00")
            self.assertTrue(daily.refresh_combined(directory / "combined.json", own, directory / "claude.json"))
            published = json.loads((directory / "combined.json").read_text())
            self.assertEqual((published["window_days"], published["measured"]), (30, {"host": False, "codex": True, "claude": False}), "the half just written stands; the stored one is another window")

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


SANDBOX_KEYS = ("ProtectSystem", "ProtectHome", "ReadWritePaths", "PrivateTmp", "PrivateUsers", "TemporaryFileSystem")
MARKER = "/srv:ro"
ARGUMENT_REFUSAL_LINE = "daily skill usage refused: the command line has an argument this version does not take, or lacks one it needs; nothing was run\n"
LAYOUT_MESSAGE = "the clone, the interpreter and node must be outside /srv, which the units' TemporaryFileSystem=/srv:ro hides from them"
TMP_LAYOUT_MESSAGE = "the clone, the interpreter and node must be outside /tmp and /var/tmp, which the units' PrivateTmp=true replaces with directories of their own"


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
    ProtectSystem=strict mounts the hierarchy read-only, ProtectHome=read-only does the same for the home directory, ReadWritePaths= allow-lists the one directory that is written. Round 5 (route B, the command center's
    ruling of 2026-10-13): the units also carry the marker TemporaryFileSystem=/srv:ro, which makes a manager that cannot make the mount namespace stop the unit instead of starting it without the directives."""

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

    def test_each_service_carries_the_marker_that_makes_the_manager_insist_and_asks_nothing_of_the_program(self):
        """Route B (ruling-pr1043-route-b-20261013): the enforcement is the manager's. TemporaryFileSystem= is a member of insist_on_sandboxing() (systemd/systemd-stable@387a14a7b67b, v255.4, src/core/exec-invoke.c
        L2849-L2888), so a manager that cannot make the mount namespace stops the unit (226/NAMESPACE, exec_invoke L4655-L4664) instead of starting it without the directives (L3212-L3237). The program no longer
        probes the file system: no option of it is in the command line."""
        with tempfile.TemporaryDirectory() as temp:
            daily, services = self.render(Path(temp))
            for half, service in services.items():
                text = service.read_text()
                section = service_section(text)
                with self.subTest(half=half):
                    self.assertEqual(section.get("TemporaryFileSystem"), [MARKER], "one mount point, read-only: it hides /srv, which nothing in the unit reads, and exists only to make the manager insist")
                    self.assertNotIn("--refuse-writable", section["ExecStart"][0], "the inside probe was removed in round 5")
                    self.assertEqual(section.get("PrivateUsers"), ["true"])
                    comment = "\n".join(line for line in text.splitlines() if line.startswith("#"))
                    for needle in ("insist_on_sandboxing", "226/NAMESPACE", "217/USER", "no boundary", "gracefully turned off", "exec_invoke"):
                        self.assertIn(needle, comment, "the comment says what the marker is for and what the guarantee is not")

    def test_the_marker_is_a_directive_the_manager_insists_on(self):
        """The members of insist_on_sandboxing() that the units could carry (exec-invoke.c L2849-L2888 at v255.4; the development head e846bbad L3527-L3566 has the same membership for these). The marker must be one of them,
        and the other sandbox directives of the units must not be, since those are the ones that are 'gracefully turned off'."""
        insisting = {"TemporaryFileSystem", "RootDirectory", "RootImage", "MountImages", "DynamicUser", "ExtensionImages", "ExtensionDirectories", "BindPaths", "BindReadOnlyPaths", "LogNamespace"}
        quiet = {"ProtectSystem", "ProtectHome", "ReadWritePaths", "PrivateTmp"}
        self.assertIn("TemporaryFileSystem", insisting)
        self.assertFalse(insisting & quiet)
        with tempfile.TemporaryDirectory() as temp:
            daily, services = self.render(Path(temp))
            for half, service in services.items():
                with self.subTest(half=half):
                    carried = {key for key in service_section(service.read_text()) if key in insisting}
                    self.assertEqual(carried, {"TemporaryFileSystem"}, "exactly the marker, no bind or root directive that would change the unit's view")

    def test_rendering_refuses_a_path_that_the_marker_hides(self):
        daily = daily_module()
        with tempfile.TemporaryDirectory() as temp:
            link = Path(temp) / "node-link"
            link.symlink_to("/srv/tools/node")
            cases = (("the clone", dict(repository="/srv/clone")), ("the clone below a doubled slash", dict(repository="//srv/clone")), ("the clone through dot-dot", dict(repository="/fixture/../srv/clone")),
                     ("the interpreter", dict(python="/srv/bin/python3")), ("node through a link", dict(node=str(link))), ("the directory itself", dict(repository="/srv")))
            for label, override in cases:
                values = dict(repository="/fixture/live", python=sys.executable, node="/fixture/bin/node") | override
                with self.subTest(case=label):
                    with self.assertRaises(daily.LayoutRefused) as caught:
                        daily.render_units(Path(temp) / "units", Path(values["repository"]), Path(values["python"]), Path(values["node"]))
                    self.assertEqual(str(caught.exception), LAYOUT_MESSAGE, "the message is fixed text and names no path")
                    self.assertIsInstance(caught.exception, daily.Refused)
            for fine in ("/serve/clone", "/srvx/clone", "/fixture/dir/srv/clone", "/fixture/srv"):
                with self.subTest(allowed=fine):
                    daily.render_units(Path(temp) / "ok", Path(fine), Path(sys.executable), Path("/fixture/bin/node"))

    def test_rendering_refuses_a_path_that_private_tmp_hides(self):
        """The local codex re-review of 0383243e (P2): the check excluded only /srv, but both services enable PrivateTmp=true, which gives them a /tmp and a /var/tmp of their own (systemd/systemd@b3d8fc43e9cb
        man/systemd.exec.xml L1865-L1870), so a clone, an interpreter or a node under those directories rendered and the units failed on every run."""
        daily = daily_module()
        with tempfile.TemporaryDirectory() as temp:
            cases = (("the clone in /tmp", dict(repository="/tmp/clone")), ("the clone in /var/tmp", dict(repository="/var/tmp/clone")), ("the clone below a doubled slash", dict(repository="//tmp/clone")),
                     ("the clone through dot-dot", dict(repository="/fixture/../var/tmp/clone")), ("the interpreter", dict(python="/tmp/venv/bin/python3")), ("node", dict(node="/var/tmp/tools/node")),
                     ("the directory itself", dict(repository="/tmp")))
            for label, override in cases:
                values = dict(repository="/fixture/live", python=sys.executable, node="/fixture/bin/node") | override
                with self.subTest(case=label):
                    with self.assertRaises(daily.LayoutRefused) as caught:
                        daily.render_units(Path(temp) / "units", Path(values["repository"]), Path(values["python"]), Path(values["node"]))
                    self.assertEqual(str(caught.exception), TMP_LAYOUT_MESSAGE, "the message is fixed text and names no path")
            for fine in ("/tmpx/clone", "/var/tmpfile/x", "/var/lib/tmp/x", "/fixture/tmp/clone", "/fixture/var/tmp"):
                with self.subTest(allowed=fine):
                    daily.render_units(Path(temp) / "ok", Path(fine), Path(sys.executable), Path("/fixture/bin/node"))

    def test_a_path_that_resolves_into_a_hidden_directory_is_hidden_whatever_its_own_name(self):
        """A link is judged by where it leads, for both directories the units hide (the resolution is made up here, so that the test does not depend on where the checkout lives)."""
        daily = daily_module()
        with mock.patch.object(daily.os.path, "realpath", return_value="/var/tmp/tools/node"):
            self.assertTrue(daily.hidden_by_private_tmp("/fixture/node-link"))
            self.assertFalse(daily.hidden_by_marker("/fixture/node-link"))
        with mock.patch.object(daily.os.path, "realpath", return_value="/srv/tools/node"):
            self.assertTrue(daily.hidden_by_marker("/fixture/node-link"))
            self.assertFalse(daily.hidden_by_private_tmp("/fixture/node-link"))
        self.assertFalse(daily.hidden_by_private_tmp("/fixture/bin/node"))

    def test_the_command_line_refuses_to_render_for_a_path_that_private_tmp_hides(self):
        daily = daily_module()
        with tempfile.TemporaryDirectory() as temp, mock.patch.object(daily, "require_reviewed_main"), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as errors:
            code = daily.main(["--render-units", str(Path(temp) / "units"), "--repository", "/var/tmp/clone", "--node", sys.executable])
        self.assertEqual(code, 2)
        self.assertEqual(errors.getvalue(), f"daily skill usage refused: {TMP_LAYOUT_MESSAGE}\n")

    def test_the_command_line_refuses_to_render_for_a_path_that_the_marker_hides(self):
        daily = daily_module()
        with tempfile.TemporaryDirectory() as temp, mock.patch.object(daily, "require_reviewed_main"), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as errors:
            code = daily.main(["--render-units", str(Path(temp) / "units"), "--repository", "/srv/clone", "--node", sys.executable])
        self.assertEqual(code, 2)
        self.assertEqual(errors.getvalue(), f"daily skill usage refused: {LAYOUT_MESSAGE}\n")

    def test_the_program_has_no_confinement_probe_option(self):
        """Route B removed the inside probe (require_confined, --refuse-writable): five rounds of fixes each found another way to satisfy it without the sandbox (the corpus of the design record)."""
        daily = daily_module()
        for name in ("require_confined", "Unconfined", "Unverified", "READ_ONLY_REFUSAL", "ACCESS_REFUSALS"):
            self.assertFalse(hasattr(daily, name), name)
        with contextlib.redirect_stderr(io.StringIO()) as errors, self.assertRaises(SystemExit) as caught:
            daily.main(["--refuse-writable", "/fixture/home"])
        self.assertEqual(caught.exception.code, 2)
        self.assertEqual(errors.getvalue(), ARGUMENT_REFUSAL_LINE, "a fixed line: argparse's own message would echo the value it could not use")

    def test_replaying_the_retired_probe_option_refuses_without_the_account_or_a_path(self):
        """Astra's read of #1043 at da4895b5 (fix4, P1): a unit rendered by an earlier version still passes `--refuse-writable <home> --refuse-writable <clone>`, and argparse printed `unrecognized arguments:` with both
        values, the account's home path among them. Every way the old command line can be framed, and the other command lines the program cannot use, now end in the fixed line."""
        daily = daily_module()
        home, clone = str(Path.home()), str(Path.home() / "code" / "live-clone")
        account = Path.home().name
        framings = (["--refuse-writable", home, "--refuse-writable", clone, "--half", "claude"], [f"--refuse-writable={home}", "--half", "claude"], [f"--refuse-writable={clone}"],
                    ["--half", "claude", "--refuse-writable", home], ["--half", "not-a-half"], ["--window", home], ["--no-such-option", home], [home])
        for argv in framings:
            with self.subTest(argv=[("<path>" if home in item or clone in item else item) for item in argv]):
                output, errors = io.StringIO(), io.StringIO()
                with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors), self.assertRaises(SystemExit) as caught:
                    daily.main(argv)
                self.assertEqual(caught.exception.code, 2)
                self.assertEqual((output.getvalue(), errors.getvalue()), ("", ARGUMENT_REFUSAL_LINE))
                self.assertNotIn(account, errors.getvalue())
                self.assertNotIn(home, errors.getvalue())

    def test_the_native_analyzer_reads_the_directives_as_protection(self):
        analyze = shutil.which("systemd-analyze")
        if not analyze:
            unavailable("native systemd analyzer unavailable")
        if "--offline" not in subprocess.run([analyze, "security", "--help"], capture_output=True, text=True, timeout=30).stdout:
            unavailable("this systemd-analyze has no `security --offline`")

        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            runtime = directory / "runtime"
            runtime.mkdir(mode=0o700)
            # `--user` builds a user manager, and its runtime directory is $XDG_RUNTIME_DIR and nothing else: sd_path_lookup(SD_PATH_USER_RUNTIME) returns -ENXIO when the variable is not set to an absolute path
            # (systemd/systemd@b3d8fc43e9cb531d958c17ef2cd93b374bc14e8a, tag v259.5, the installed 259.5: src/libsystemd/sd-path/sd-path.c L20-L39 and L244-L245; src/core/manager.c L708-L742,
            # called from manager_new at L960; src/analyze/analyze-security.c L2708-L2710; man/sd_path_lookup.xml L186-L194). A caller without the variable (a non-login shell, a container) therefore
            # stopped at "Failed to lookup RuntimeDirectory path: No such device or address". The call gets its own HOME and runtime directory, as the native verification test above does.
            environment = {"HOME": str(directory), "PATH": os.defpath, "XDG_RUNTIME_DIR": str(runtime)}

            def rows(unit):
                done = subprocess.run([analyze, "security", "--offline=yes", "--user", "--json=short", str(unit)], capture_output=True, text=True, timeout=60, env=environment)
                self.assertEqual(done.returncode, 0, done.stderr)
                return {row["json_field"]: row for row in json.loads(done.stdout) if row.get("json_field") in ("ProtectSystem", "ProtectHome", "PrivateTmp")}
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


# What a unit's directives do to a process, observed through the manager that starts it (route B, ruling-pr1043-route-b-20261013). The payload prints a first line the moment it starts (so a unit that was refused is
# known by its silence), then tries to create a file at each target. The control is the same payload started by the same manager with no directive at all: it is in the manager's own mount namespace, which is the
# reference a sandboxed unit's namespace is compared with (never the namespace of the process that started the test: a manager may live in a namespace of its own, as the first host's does), and every write of it must succeed.
PROBE_CHILD = r"""
import errno, json, os, sys
print(json.dumps({"started": True, "ns": os.readlink("/proc/self/ns/mnt")}), flush=True)


def attempt(path):
    try:
        with open(path, "w"):
            pass
        os.unlink(path)
        return "written"
    except OSError as error:
        return errno.errorcode.get(error.errno, "errno-%d" % error.errno)


print(json.dumps({"writes": {name: attempt(path) for name, path in json.loads(sys.argv[1]).items()}}), flush=True)
"""

# The statuses with which a manager refuses a unit before its payload runs, because the namespaces its directives ask for cannot be made: EXIT_NAMESPACE (man/systemd.exec.xml L4356-L4358, systemd-stable@387a14a7b67b
# v255.4; exec_invoke L4655-L4664) for the mount namespace, and EXIT_USER (L4316-L4317; exec_invoke L4595-L4609) for the user namespace that PrivateUsers=true asks for. Any other status is not a refusal of the directives.
REFUSAL_STATUSES = {226: "NAMESPACE", 217: "USER"}
PROTECTED_TARGETS = ("clone", "other", "unrelated", "runtime")
WRITABLE_TARGETS = ("records",)


def observe(done):
    """One run through the manager as plain data: the exit status (None when the run never completed), whether the payload printed its first line, its mount namespace, its write attempts, whether the run printed
    nothing at all, and the status the manager itself reported (its own words, `226/NAMESPACE`). A key that is absent is a missing fact (None): nothing is guessed. The payload prints exactly a start line and then a
    write map; output of any other shape (a line that is not JSON, a second start, a second write map, a frame of another kind) is not that payload's, and every fact that depended on it is missing (Astra's read of #1043
    at da4895b5, P3: a later start replaced an earlier one, so a contradictory framing classified as enforced)."""
    if done is None or done.returncode is None:
        return {"rc": None, "started": False, "silent": True, "ns": None, "writes": None, "manager": None}
    starts, maps, strays = [], [], 0
    for line in done.stdout.splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except ValueError:
            strays += 1
            continue
        if isinstance(item, dict) and item.get("started") is True and isinstance(item.get("ns"), str):
            starts.append(item["ns"])
        elif isinstance(item, dict) and isinstance(item.get("writes"), dict):
            maps.append({str(key): str(value) for key, value in item["writes"].items()})
        else:
            strays += 1
    framed = len(starts) <= 1 and len(maps) <= 1 and strays == 0 and not (maps and not starts)
    started, ns, writes = (bool(starts), starts[0] if starts else None, maps[0] if maps else None) if framed else (False, None, None)
    reported = re.search(r"status=(\d+)(?:/([A-Z_]+))?", done.stderr or "")   # systemd 255 prints `code=exited/status=226`, 259 `code=exited, status=226/NAMESPACE`
    return {"rc": done.returncode, "started": started, "silent": not done.stdout.strip(), "ns": ns, "writes": writes,
            "manager": None if not reported else f"{reported.group(1)}/{reported.group(2)}" if reported.group(2) else reported.group(1)}


def classify(control, run):
    """What the manager did with the directives, from two observations taken through the same manager: `control` (no directive) and `run` (the unit's directives). Returns (class, reason):

    "enforced"      the unit ran (status 0) in a mount namespace other than the control's (the manager's own), every protected write was refused by a read-only file system (EROFS) where the control's succeeded,
                    and the record directory was written;
    "fails_closed"  the manager refused the unit with 226/NAMESPACE or 217/USER (REFUSAL_STATUSES) and the payload never printed anything;
    "fail"          anything else, with the reason: it ran in the control's namespace (unconfined), there is no usable reference namespace, an observation is missing or malformed or timed out, a refusal was not EROFS,
                    a status is not one of the two, or the payload started although the manager reported a refusal. There is no skip and no tolerated middle class."""
    status = run.get("rc")
    if status is None:
        return "fail", "the run did not complete"
    if status in REFUSAL_STATUSES:
        if run.get("started") or not run.get("silent"):
            return "fail", "the payload started although the manager reported a refusal"
        if run.get("manager") not in (None, str(status), f"{status}/{REFUSAL_STATUSES[status]}"):
            return "fail", "the manager's own words do not match the status"
        return "fails_closed", f"{status}/{REFUSAL_STATUSES[status]}"
    if status != 0:
        return "fail", f"status {status} is not a refusal of the namespaces"
    if control.get("rc") != 0 or not control.get("ns") or not isinstance(control.get("writes"), dict):
        return "fail", "the control gave no reference namespace"
    expected = set(control["writes"])
    if not {"clone", "other", "unrelated", "records"} <= expected or any(value != "written" for value in control["writes"].values()):
        return "fail", "the control could not write where the unit must be refused"
    if not run.get("started") or not run.get("ns") or not isinstance(run.get("writes"), dict) or set(run["writes"]) != expected:
        return "fail", "the observation of the run is incomplete"
    if run["ns"] == control["ns"]:
        return "fail", "the unit ran in the manager's own mount namespace: unconfined"
    for name in sorted(expected):
        wanted = "written" if name in WRITABLE_TARGETS else "EROFS"
        if run["writes"][name] != wanted:
            return "fail", f"the write to {name} gave {run['writes'][name]}, not {wanted}"
    return "enforced", ""


def unavailable(reason):
    """A native test that cannot run: a skip on a developer's machine, a failure under GitHub Actions, so that a green run there means something was asserted (the pattern of
    tests/test_token_full_save_evidence.py metadata_lines, which reads GITHUB_ACTIONS on every call so a control can patch the environment). The hosted runner has a user manager (receipts)."""
    if os.environ.get("GITHUB_ACTIONS") == "true":
        raise AssertionError(f"{reason}; the GitHub-hosted runner has a user manager, so a native test that cannot run there is a defect")
    raise unittest.SkipTest(reason)


# A stand-in for `systemd-run --user --wait --collect --pipe -p KEY=VALUE ... COMMAND`. It exercises the classifier and the observation, nothing about systemd: its modes are what a manager can do with the
# directives, selected by STUB_MODE. "apply-none" accepts every property and applies none (the hosted runner's manager without the marker); "refuse" exits with STUB_STATUS before the payload runs; "refuse-after-start"
# runs the payload and then exits with STUB_STATUS (a contradiction: a refusal that came too late); "insist" refuses (STUB_STATUS) only a unit that carries TemporaryFileSystem= and applies none otherwise (the hosted
# runner's manager with and without the marker); "refuse-user-namespace" refuses (STUB_STATUS, 217/USER) only a unit that carries PrivateUsers= and applies none otherwise (a host whose user manager cannot
# create the user namespace).
STUB_MANAGER = r"""
import os
import subprocess
import sys

arguments, environment, directory, marked, private = sys.argv[1:], dict(os.environ), None, False, False
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
        elif key == "TemporaryFileSystem":
            marked = True
        elif key == "PrivateUsers":
            private = True
        index += 2
    else:
        break
mode = os.environ.get("STUB_MODE", "apply-none")
if mode == "insist":
    mode = "refuse" if marked else "apply-none"
elif mode == "refuse-user-namespace":
    mode = "refuse" if private else "apply-none"
status = int(os.environ.get("STUB_STATUS", "0"))
if mode == "refuse":
    sys.stderr.write("Finished with result: exit-code\nMain processes terminated with: code=exited, status=%d/%s\n" % (status, os.environ.get("STUB_NAME", "NAMESPACE")))
    sys.exit(status)
done = subprocess.run(arguments[index:], cwd=directory, env=environment).returncode
if mode == "refuse-after-start":
    sys.stderr.write("Finished with result: exit-code\nMain processes terminated with: code=exited, status=%d/NAMESPACE\n" % status)
    sys.exit(status)
sys.exit(done)
"""


class ManagerProbes:
    """What a service unit's directives do to a process, asked through `self.manager`: an argv prefix that behaves like `systemd-run --user --wait --collect --pipe` (the real one, or STUB_MANAGER)."""
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
            unavailable("the home directory is not writable")
        self.addCleanup(shutil.rmtree, fixture, True)
        for name in ("clone", "other", "records"):
            (fixture / name).mkdir()
        return fixture

    def targets(self, fixture):
        """Where the payload tries to create a file: the clone and a sibling directory (below the home, read-only under the directives), a file in the home itself, the pre-existing runtime tmpfs below /run (a submount
        of a protected tree that exists before the unit starts), and the record directory (the one that must stay writable)."""
        found = {"clone": fixture / "clone" / "probe.txt", "other": fixture / "other" / "probe.txt", "records": fixture / "records" / "probe.txt", "unrelated": Path.home() / f".skill-sandbox-probe-{os.getpid()}"}
        if os.environ.get("XDG_RUNTIME_DIR"):
            found["runtime"] = Path(os.environ["XDG_RUNTIME_DIR"]) / f"skill-sandbox-probe-{os.getpid()}"
        return found

    def properties(self, section, records):
        """The sandbox properties of a rendered unit as KEY=VALUE strings, with the record directory moved to the fixture: the marker is in them."""
        home = str(Path.home())
        out = []
        for key in SANDBOX_KEYS:
            for value in section[key]:
                value = records if key == "ReadWritePaths" else value
                out.append(f"{key}={value.replace('%h', home)}")
        for value in section["Environment"]:
            if value.startswith("PYTHONDONTWRITEBYTECODE="):
                out.append(f"Environment={value}")
        return out

    def marker_comparison(self, fixture, control, results, env=None):
        """The reason for the marker, shown by taking it away: where the manager refuses the marked units with the mount-namespace status (every half 226/NAMESPACE), the same unit without the marker is classified
        and returned. None where the comparison does not apply: the manager enforces the directives (a capable manager enforces both), or it refuses for another reason. Review of #1043 at da4895b5 (the local
        codex review, P2): on a host where PrivateUsers=true is refused with 217/USER the marked units fail closed, and the comparison was made for that result too; removing only the marker leaves PrivateUsers=true,
        so the unmarked unit also failed closed with 217 and the assertion that it ran unconfined failed although the services behave as specified."""
        if set(results.values()) != {("fails_closed", "226/NAMESPACE")}:
            return None
        without = [item for item in self.properties(self.units()["claude"], str(fixture / "records")) if not item.startswith("TemporaryFileSystem=")]
        return classify(control, self.run_probe(without, fixture, env=env))

    def run_probe(self, properties, fixture, env=None):
        """The observation (observe) of the payload started through the manager with the KEY=VALUE `properties`."""
        targets = {name: str(path) for name, path in self.targets(fixture).items()}
        for path in targets.values():
            self.addCleanup(lambda path=path: Path(path).unlink(missing_ok=True))
        flags = [item for prop in properties for item in ("-p", prop)]
        argv = [*self.manager, "-p", f"WorkingDirectory={fixture / 'clone'}", *flags, sys.executable, "-B", "-c", PROBE_CHILD, json.dumps(targets)]
        try:
            done = subprocess.run(argv, capture_output=True, text=True, timeout=120, env={**os.environ, **(env or {})})
        except (OSError, subprocess.SubprocessError):
            done = None
        return observe(done)


class ClassifierTests(unittest.TestCase):
    """classify() on observations written out by hand: the decision logic of the native test, which no host class can exercise all of. Review of the design record of #1043 (Astra P2, Muse P2-3, the command
    center's Claude read P1-1): a child whose namespace differs from the test process's is not necessarily in a namespace the manager made for the unit, and a skip or a tolerated 'ran and unenforced' class lets
    a manager that stopped insisting pass."""

    WRITTEN = {"clone": "written", "other": "written", "unrelated": "written", "runtime": "written", "records": "written"}
    CONTROL = {"rc": 0, "started": True, "silent": False, "ns": "mnt:[100]", "writes": WRITTEN, "manager": "0/SUCCESS"}
    ENFORCED = {"rc": 0, "started": True, "silent": False, "ns": "mnt:[200]", "manager": "0/SUCCESS",
                "writes": {"clone": "EROFS", "other": "EROFS", "unrelated": "EROFS", "runtime": "EROFS", "records": "written"}}
    REFUSED = {"rc": 226, "started": False, "silent": True, "ns": None, "writes": None, "manager": "226/NAMESPACE"}

    def run_with(self, **changes):
        return {**self.ENFORCED, **changes}

    def test_a_unit_in_a_namespace_the_manager_made_with_every_protected_write_refused_is_enforced(self):
        self.assertEqual(classify(self.CONTROL, self.ENFORCED), ("enforced", ""))

    def test_a_unit_that_ran_in_the_managers_own_namespace_is_a_failure_whatever_else_it_shows(self):
        """The hosted runner's manager without the marker: status 0, every write succeeded (receipts/marker-probe-hosted-runner.json, set 'the shipped directives before round 5 (no marker)')."""
        unconfined = self.run_with(ns=self.CONTROL["ns"], writes=self.WRITTEN)
        self.assertEqual(classify(self.CONTROL, unconfined), ("fail", "the unit ran in the manager's own mount namespace: unconfined"))
        refused_but_inherited = self.run_with(ns=self.CONTROL["ns"])
        self.assertEqual(classify(self.CONTROL, refused_but_inherited)[0], "fail", "refusals do not make a namespace: the Astra counterexample, a child that inherited the manager's namespace")

    def test_the_namespace_of_the_process_that_started_the_test_is_not_an_input(self):
        """Astra P2: on the first host the manager's namespace differs from the starter's, so 'differs from the starter' holds for a child that merely inherited the manager's. The reference is the control's."""
        starter = "mnt:[1]"
        child_equal_to_the_manager = self.run_with(ns="mnt:[100]")
        self.assertNotEqual(child_equal_to_the_manager["ns"], starter)
        self.assertEqual(classify(self.CONTROL, child_equal_to_the_manager)[0], "fail")

    def test_an_unknown_reference_cannot_pass_the_successful_branch(self):
        for label, control in (("no namespace", {**self.CONTROL, "ns": None}), ("an empty namespace", {**self.CONTROL, "ns": ""}), ("the control did not complete", {**self.CONTROL, "rc": None}),
                               ("the control failed", {**self.CONTROL, "rc": 1}), ("no writes", {**self.CONTROL, "writes": None}), ("not an object", {**self.CONTROL, "writes": []})):
            with self.subTest(control=label):
                self.assertEqual(classify(control, self.ENFORCED), ("fail", "the control gave no reference namespace"))

    def test_the_control_must_be_able_to_write_where_the_unit_is_refused(self):
        """A control that was itself refused somewhere shows nothing about what the directives refuse."""
        for target in ("clone", "other", "unrelated", "runtime", "records"):
            with self.subTest(refused_in_the_control=target):
                control = {**self.CONTROL, "writes": {**self.WRITTEN, target: "EROFS"}}
                self.assertEqual(classify(control, self.ENFORCED), ("fail", "the control could not write where the unit must be refused"))

    def test_a_control_that_lacks_a_target_shows_nothing_about_that_target(self):
        for target in ("clone", "other", "unrelated", "records"):
            with self.subTest(missing_in_the_control=target):
                control = {**self.CONTROL, "writes": {key: value for key, value in self.WRITTEN.items() if key != target}}
                self.assertEqual(classify(control, self.ENFORCED), ("fail", "the control could not write where the unit must be refused"))

    def test_every_protected_write_must_be_refused_by_a_read_only_file_system_and_the_records_written(self):
        for target in PROTECTED_TARGETS:
            for answer in ("written", "EACCES", "EPERM", "ENOENT", "EIO"):
                with self.subTest(target=target, answer=answer):
                    writes = {**self.ENFORCED["writes"], target: answer}
                    outcome, reason = classify(self.CONTROL, self.run_with(writes=writes))
                    self.assertEqual(outcome, "fail")
                    self.assertIn(target, reason)
        for answer in ("EROFS", "EACCES", "ENOENT"):
            with self.subTest(records=answer):
                outcome, reason = classify(self.CONTROL, self.run_with(writes={**self.ENFORCED["writes"], "records": answer}))
                self.assertEqual((outcome, "records" in reason), ("fail", True))

    def test_a_missing_malformed_or_incomplete_observation_of_a_run_that_started_is_a_failure(self):
        for label, changes in (("never started", dict(started=False)), ("no namespace", dict(ns=None)), ("no writes", dict(writes=None)), ("writes of the wrong type", dict(writes=[])),
                               ("a target missing", dict(writes={key: value for key, value in self.ENFORCED["writes"].items() if key != "runtime"})),
                               ("a target more", dict(writes={**self.ENFORCED["writes"], "extra": "EROFS"}))):
            with self.subTest(run=label):
                self.assertEqual(classify(self.CONTROL, self.run_with(**changes))[0], "fail")

    def test_a_run_that_did_not_complete_is_a_failure_never_a_skip(self):
        self.assertEqual(classify(self.CONTROL, {**self.ENFORCED, "rc": None}), ("fail", "the run did not complete"))
        self.assertEqual(classify(self.CONTROL, observe(None)), ("fail", "the run did not complete"))

    def test_the_two_refusals_of_the_namespaces_are_fails_closed_when_the_payload_never_ran(self):
        for status, name in ((226, "NAMESPACE"), (217, "USER")):
            with self.subTest(status=status):
                self.assertEqual(classify(self.CONTROL, {**self.REFUSED, "rc": status, "manager": f"{status}/{name}"}), ("fails_closed", f"{status}/{name}"))
                self.assertEqual(classify(self.CONTROL, {**self.REFUSED, "rc": status, "manager": None})[0], "fails_closed", "the manager's words are optional, the status is not")
        broken_control = {**self.CONTROL, "rc": 1, "ns": None, "writes": None}
        self.assertEqual(classify(broken_control, self.REFUSED)[0], "fails_closed", "a refusal needs no reference namespace")

    def test_a_refusal_with_any_sign_that_the_payload_ran_is_a_failure(self):
        for label, changes in (("it printed its first line", dict(started=True, ns="mnt:[200]")), ("it printed something", dict(silent=False)),
                               ("it wrote", dict(writes={"records": "written"}, started=True, silent=False))):
            with self.subTest(run=label):
                self.assertEqual(classify(self.CONTROL, {**self.REFUSED, **changes}), ("fail", "the payload started although the manager reported a refusal"))

    def test_the_managers_own_words_must_match_the_status(self):
        self.assertEqual(classify(self.CONTROL, {**self.REFUSED, "manager": "226/USER"}), ("fail", "the manager's own words do not match the status"))
        self.assertEqual(classify(self.CONTROL, {**self.REFUSED, "rc": 217, "manager": "217/NAMESPACE"})[0], "fail")
        self.assertEqual(classify(self.CONTROL, {**self.REFUSED, "manager": "217"})[0], "fail", "the number alone must match too")
        self.assertEqual(classify(self.CONTROL, {**self.REFUSED, "manager": "226"})[0], "fails_closed", "systemd 255 prints the number without its name")

    def test_every_other_status_is_a_failure(self):
        """The statuses the unit set could end in besides the two refusals (man/systemd.exec.xml): the working directory (200), exec (203), capabilities (218), network (225), the cgroup (219), a plain 1, a signal."""
        for status in (1, 2, 200, 203, 205, 218, 219, 225, 227, 255, 143):
            with self.subTest(status=status):
                outcome, reason = classify(self.CONTROL, {**self.REFUSED, "rc": status, "manager": f"{status}/X"})
                self.assertEqual((outcome, reason), ("fail", f"status {status} is not a refusal of the namespaces"))

    def test_the_classifier_never_skips_and_has_exactly_three_classes(self):
        seen = set()
        for run in (self.ENFORCED, self.REFUSED, {**self.REFUSED, "rc": 1}, {"rc": None}, {}):
            outcome, _ = classify(self.CONTROL, run)
            seen.add(outcome)
        self.assertEqual(seen, {"enforced", "fails_closed", "fail"})


class ObserveTests(unittest.TestCase):
    def done(self, stdout, returncode=0, stderr=""):
        return subprocess.CompletedProcess(["manager"], returncode, stdout, stderr)

    def test_the_two_lines_of_the_payload_and_the_managers_words_are_read(self):
        stdout = json.dumps({"started": True, "ns": "mnt:[7]"}) + "\n" + json.dumps({"writes": {"clone": "EROFS", "records": "written"}}) + "\n"
        seen = observe(self.done(stdout, stderr="Finished with result: success\nMain processes terminated with: code=exited, status=0/SUCCESS\n"))
        self.assertEqual(seen, {"rc": 0, "started": True, "silent": False, "ns": "mnt:[7]", "writes": {"clone": "EROFS", "records": "written"}, "manager": "0/SUCCESS"})

    def test_a_silent_refusal_has_nothing_but_the_status(self):
        seen = observe(self.done("", 226, "Finished with result: exit-code\nMain processes terminated with: code=exited, status=226/NAMESPACE\n"))
        self.assertEqual(seen, {"rc": 226, "started": False, "silent": True, "ns": None, "writes": None, "manager": "226/NAMESPACE"})

    def test_the_managers_words_are_read_in_the_forms_of_both_host_classes(self):
        """systemd 259 (the first host) prints `code=exited, status=226/NAMESPACE`; systemd 255 (the hosted runner) prints `code=exited/status=226` (receipts/marker-probe-hosted-runner.json)."""
        for words, expected in (("Main processes terminated with: code=exited, status=226/NAMESPACE", "226/NAMESPACE"), ("Main processes terminated with: code=exited/status=226", "226"),
                                ("Main processes terminated with: code=exited/status=0", "0"), ("Main processes terminated with: code=exited, status=0/SUCCESS", "0/SUCCESS"), ("nothing about a status", None)):
            with self.subTest(words=words):
                self.assertEqual(observe(self.done("", 1, words + "\n"))["manager"], expected)

    def test_output_that_is_not_the_payloads_two_lines_is_a_missing_observation(self):
        """Astra's read of #1043 at da4895b5 (fix4, P3): a malformed line, a start in the manager's namespace, a second start in another namespace and a valid write map made `enforced` (the later start replaced the
        earlier one). The reader takes the payload's output only as its start line and its write map, once each."""
        start = lambda ns: json.dumps({"started": True, "ns": ns})
        writes = json.dumps({"writes": {"clone": "EROFS", "other": "EROFS", "unrelated": "EROFS", "runtime": "EROFS", "records": "written"}})
        control = {"rc": 0, "started": True, "silent": False, "ns": "mnt:[100]", "writes": ClassifierTests.WRITTEN, "manager": "0/SUCCESS"}
        missing = {"started": False, "ns": None, "writes": None, "silent": False}
        cases = (("the reviewer's framing", ["garbage", start("mnt:[100]"), start("mnt:[200]"), writes]), ("a second start", [start("mnt:[200]"), start("mnt:[300]"), writes]),
                 ("a second write map", [start("mnt:[200]"), writes, writes]), ("a line that is not JSON between the two", [start("mnt:[200]"), "garbage", writes]),
                 ("a frame of another kind", [start("mnt:[200]"), json.dumps({"other": 1}), writes]), ("a write map without a start", [writes]), ("a list", [start("mnt:[200]"), "[1]", writes]))
        for label, lines in cases:
            with self.subTest(framing=label):
                seen = observe(self.done("\n".join(lines) + "\n"))
                self.assertEqual({key: seen[key] for key in missing}, missing)
                self.assertEqual(classify(control, seen), ("fail", "the observation of the run is incomplete"))
        clean = observe(self.done(start("mnt:[200]") + "\n" + writes + "\n"))
        self.assertEqual(classify(control, clean), ("enforced", ""), "the payload's own two lines, with a blank line around them, are still read")
        self.assertEqual(observe(self.done("\n" + start("mnt:[200]") + "\n\n" + writes + "\n\n"))["ns"], "mnt:[200]")
        self.assertEqual(observe(self.done(start("mnt:[200]") + "\n"))["writes"], None, "a start without a write map: the writes are missing, the start is not")

    def test_what_is_not_json_or_not_the_right_shape_is_a_missing_fact(self):
        for label, stdout in (("garbage", "garbage\n"), ("a list", "[1, 2]\n"), ("started as a string", json.dumps({"started": "yes", "ns": "x"}) + "\n"),
                              ("a namespace of the wrong type", json.dumps({"started": True, "ns": 5}) + "\n"), ("writes as a list", json.dumps({"writes": ["x"]}) + "\n")):
            with self.subTest(output=label):
                seen = observe(self.done(stdout))
                self.assertFalse(seen["started"] and seen["ns"] is not None and isinstance(seen["writes"], dict))
                self.assertFalse(seen["silent"])

    def test_a_run_that_did_not_complete_is_observed_as_no_status(self):
        self.assertEqual(observe(None)["rc"], None)
        self.assertEqual(observe(self.done("", None))["rc"], None)
        printed = json.dumps({"started": True, "ns": "mnt:[7]"}) + "\n"
        self.assertEqual(observe(self.done(printed, None)), {"rc": None, "started": False, "silent": True, "ns": None, "writes": None, "manager": None}, "nothing that an unfinished run printed is trusted")

    def test_a_start_without_a_namespace_is_not_a_start(self):
        seen = observe(self.done(json.dumps({"started": True}) + "\n"))
        self.assertEqual((seen["started"], seen["ns"], seen["silent"]), (False, None, False))


class StubManagerTests(ManagerProbes, unittest.TestCase):
    """The classifier driven through a stand-in manager, with real processes, so that the whole path (the properties handed over, the payload, the observation, the class) runs on every host with or without systemd.
    The stand-in exercises the decision logic only: it says nothing about what any real manager does (the hosted runner's is in the retained receipts and the native tests)."""

    @classmethod
    def setUpClass(cls):
        cls._temp = tempfile.TemporaryDirectory(prefix="skill-stub-manager-")
        cls.addClassCleanup(cls._temp.cleanup)
        stub = Path(cls._temp.name) / "stub_manager.py"
        stub.write_text(STUB_MANAGER)
        cls.manager = [sys.executable, str(stub)]

    def test_a_manager_that_accepts_the_directives_and_applies_none_is_a_failure_even_with_the_marker(self):
        """Review of #1043 at 68d4f4343 (blocker 1, the failed shard on the GitHub-hosted runner: ubuntu-24.04 image 20261004.327.1, systemd 255.4-1ubuntu8.17, job 115064673607 of run 38325995828): the manager accepted the
        directives, started the probe, and every write succeeded. Before round 5 that was a skip or a 'ran and unenforced' class; now it is the failure that a manager which stopped insisting must be."""
        fixture = self.fixture()
        control = self.run_probe([], fixture)
        self.assertEqual((control["rc"], set(control["writes"].values())), (0, {"written"}))
        for half, section in self.units().items():
            with self.subTest(half=half):
                run = self.run_probe(self.properties(section, str(fixture / "records")), fixture)
                self.assertEqual(run["ns"], control["ns"])
                self.assertEqual(classify(control, run), ("fail", "the unit ran in the manager's own mount namespace: unconfined"))

    def test_a_manager_that_refuses_the_unit_before_the_payload_is_fails_closed(self):
        fixture = self.fixture()
        control = self.run_probe([], fixture)
        for status, name in ((226, "NAMESPACE"), (217, "USER")):
            with self.subTest(status=status):
                run = self.run_probe(self.properties(self.units()["claude"], str(fixture / "records")), fixture, env={"STUB_MODE": "refuse", "STUB_STATUS": str(status), "STUB_NAME": name})
                self.assertEqual((run["rc"], run["started"], run["silent"], run["manager"]), (status, False, True, f"{status}/{name}"))
                self.assertEqual(classify(control, run), ("fails_closed", f"{status}/{name}"))

    def test_a_refusal_that_came_after_the_payload_ran_is_a_failure(self):
        fixture = self.fixture()
        control = self.run_probe([], fixture)
        run = self.run_probe(self.properties(self.units()["codex"], str(fixture / "records")), fixture, env={"STUB_MODE": "refuse-after-start", "STUB_STATUS": "226"})
        self.assertEqual((run["rc"], run["started"]), (226, True))
        self.assertEqual(classify(control, run), ("fail", "the payload started although the manager reported a refusal"))

    def test_any_other_status_is_a_failure_through_the_whole_path(self):
        fixture = self.fixture()
        control = self.run_probe([], fixture)
        for status in (1, 203, 218):
            with self.subTest(status=status):
                run = self.run_probe(self.properties(self.units()["claude"], str(fixture / "records")), fixture, env={"STUB_MODE": "refuse", "STUB_STATUS": str(status), "STUB_NAME": "OTHER"})
                self.assertEqual(classify(control, run)[0], "fail")

    def test_the_marker_comparison_is_made_only_where_the_manager_refuses_for_the_mount_namespace(self):
        """Review of #1043 at da4895b5 (the local codex review, P2): see marker_comparison. The stand-in manager stands for the three managers a host can have: one that insists on the marker, one that refuses every
        unit for the user namespace, and one that applies nothing."""
        fixture = self.fixture()
        control = self.run_probe([], fixture)

        def marked(env):
            return {half: classify(control, self.run_probe(self.properties(section, str(fixture / "records")), fixture, env=env)) for half, section in self.units().items()}

        insist = {"STUB_MODE": "insist", "STUB_STATUS": "226", "STUB_NAME": "NAMESPACE"}
        results = marked(insist)
        self.assertEqual(set(results.values()), {("fails_closed", "226/NAMESPACE")})
        self.assertEqual(self.marker_comparison(fixture, control, results, env=insist), ("fail", "the unit ran in the manager's own mount namespace: unconfined"), "the marker is what stops the unit")

        user = {"STUB_MODE": "refuse-user-namespace", "STUB_STATUS": "217", "STUB_NAME": "USER"}
        results = marked(user)
        self.assertEqual(set(results.values()), {("fails_closed", "217/USER")})
        self.assertIsNone(self.marker_comparison(fixture, control, results, env=user), "PrivateUsers=true stops the unit with or without the marker: nothing to compare")

        results = marked({"STUB_MODE": "apply-none"})
        self.assertEqual(set(results.values()), {("fail", "the unit ran in the manager's own mount namespace: unconfined")})
        self.assertIsNone(self.marker_comparison(fixture, control, results), "a manager that applies nothing fails the primary test; the comparison does not apply")

        every_unit = {"STUB_MODE": "refuse", "STUB_STATUS": "226", "STUB_NAME": "NAMESPACE"}
        results = marked(every_unit)
        outcome, _ = self.marker_comparison(fixture, control, results, env=every_unit)
        self.assertEqual(outcome, "fails_closed", "a manager that refuses the unit without the marker too is not shown to be stopped by it: the native test fails there")

    def test_the_properties_handed_to_the_manager_carry_the_marker(self):
        """Muse P2-3(c): SANDBOX_KEYS lacked the marker, so a test built on it measured the unit without it and believed it measured the shipped unit."""
        fixture = self.fixture()
        for half, section in self.units().items():
            with self.subTest(half=half):
                properties = self.properties(section, str(fixture / "records"))
                self.assertIn(f"TemporaryFileSystem={MARKER}", properties)
                self.assertIn("PrivateUsers=true", properties)
                self.assertEqual([item for item in properties if item.startswith("ReadWritePaths=")], [f"ReadWritePaths={fixture / 'records'}"])


class UnavailableTests(unittest.TestCase):
    """A native test that cannot run must not be a green one under GitHub Actions (the command center's ruling, point 4; the pattern of tests/test_token_full_save_evidence.py)."""

    def outcome(self, reason):
        try:
            unavailable(reason)
        except unittest.SkipTest as skipped:
            return "skip", str(skipped)
        except AssertionError as failed:
            return "fail", str(failed)
        return "returned", ""

    def test_it_skips_on_a_developers_machine_and_fails_under_github_actions(self):
        for ci, expected in (("unset", "skip"), ("true", "fail"), ("false", "skip")):
            with self.subTest(GITHUB_ACTIONS=ci), mock.patch.dict(os.environ):
                os.environ.pop("GITHUB_ACTIONS", None)
                if ci != "unset":
                    os.environ["GITHUB_ACTIONS"] = ci
                kind, message = self.outcome("no user manager can be reached")
                self.assertEqual(kind, expected)
                self.assertIn("no user manager can be reached", message)


class NativeManagerTests(ManagerProbes, unittest.TestCase):
    """The rendered service's own directives, applied by the user manager of the host to a payload (route B). A manager has two acceptable outcomes: it makes the mount namespace and the unit runs in it (`enforced`:
    a namespace other than the manager's own, every protected write refused as a read-only file system, the record directory written), or it refuses the unit (`fails_closed`: 226/NAMESPACE or 217/USER, nothing
    printed). Everything else fails, a manager that accepts the directives and applies none included. The test skips only where there is no user manager at all, and under GitHub Actions even that fails."""

    @classmethod
    def setUpClass(cls):
        systemd_run = shutil.which("systemd-run")
        if not systemd_run:
            unavailable("systemd-run is unavailable")
        if sys.executable.startswith(("/tmp/", "/var/tmp/")):
            unavailable("the interpreter lives where PrivateTmp= hides it")
        cls.manager = [systemd_run, "--user", "--wait", "--collect", "--pipe"]
        try:
            done = subprocess.run([*cls.manager, "-q", "/bin/true"], capture_output=True, text=True, timeout=60)
        except (OSError, subprocess.SubprocessError):
            unavailable("the user manager cannot be reached")
        if done.returncode != 0:
            unavailable("the user manager cannot be reached, or will not start a plain unit")

    def classes(self):
        fixture = self.fixture()
        control = self.run_probe([], fixture)
        results = {half: classify(control, self.run_probe(self.properties(section, str(fixture / "records")), fixture)) for half, section in self.units().items()}
        return fixture, control, results

    def test_the_rendered_directives_are_enforced_by_the_manager_or_the_manager_refuses_the_unit(self):
        fixture, control, results = self.classes()
        self.assertEqual(control["rc"], 0, "the control (no directive) must run, or the manager cannot be asked")
        for half, (outcome, reason) in results.items():
            with self.subTest(half=half):
                self.assertNotEqual(outcome, "fail", reason)
        self.assertEqual(len({outcome for outcome, _ in results.values()}), 1, "both halves carry the same directives and meet the same manager")
        print(f"manager class: {next(iter(results.values()))[0]}", file=sys.stderr)

    def test_a_marker_on_a_mount_point_that_does_not_exist_fails_closed(self):
        """The marker's failure mode on a host without /srv (Muse P2-1, Astra P3-1): mount_tmpfs creates the mount point and ignores that result, then mounts (src/core/namespace.c L1284-L1289 at v255.4), so for an
        unprivileged unit a missing top-level directory ends in the refusal and never in a unit that runs without the directives. Measured: receipts/marker-probe-*.json, set 'a marker on a missing mount point'."""
        fixture = self.fixture()
        control = self.run_probe([], fixture)
        absent = f"/skill-marker-absent-{os.getpid()}"
        self.assertFalse(os.path.lexists(absent))
        section = self.units()["claude"]
        properties = [item for item in self.properties(section, str(fixture / "records")) if not item.startswith("TemporaryFileSystem=")] + [f"TemporaryFileSystem={absent}:ro"]
        outcome, reason = classify(control, self.run_probe(properties, fixture))
        self.assertEqual(outcome, "fails_closed", reason)

    def test_where_the_manager_cannot_make_the_namespace_only_the_marker_stops_the_unit(self):
        """The reason for the marker: on the hosted runner the same directives without it ran unconfined (receipts/marker-probe-hosted-runner.json, set 'the shipped directives before round 5 (no marker)'). The comparison is made only on a manager that refuses the unit with the marker, and
        says so on stderr otherwise; a capable manager enforces both and the primary test above is the assertion."""
        fixture, control, results = self.classes()
        compared = self.marker_comparison(fixture, control, results)
        if compared is None:
            print(f"namespace-denied branch exercised: no (the marked units gave {sorted(set(results.values()))}: a manager that makes the namespace, or that refuses for another reason)", file=sys.stderr)
            return
        outcome, reason = compared
        self.assertEqual(outcome, "fail", "without the marker the manager that refuses it must have started the unit unconfined, or the marker is not what stops it")
        self.assertEqual(reason, "the unit ran in the manager's own mount namespace: unconfined")
        print("namespace-denied branch exercised: yes", file=sys.stderr)


RECEIPTS = ROOT / "evidence/artifacts/skill-invoke-rate-timer-20261012/receipts"


class RetainedReceiptTests(unittest.TestCase):
    """The probes that were run on both host classes before round 5 (the first host, systemd 259.5; the GitHub-hosted runner, systemd 255.4) hold the observations classify() reads. The expected class of each set
    is written here, by hand, from the manager's own words in the receipt: the classifier must read the retained observations the way the record states them."""

    EXPECTED = {
        "marker-probe-first-host.json": {"the shipped directives before round 5 (no marker)": "enforced", "the Claude unit's directives": "enforced",
                                         "the Codex unit's directives": "enforced", "a marker on a missing mount point": "fails_closed"},
        "marker-probe-hosted-runner.json": {"the shipped directives before round 5 (no marker)": "fail", "the Claude unit's directives": "fails_closed",
                                            "the Codex unit's directives": "fails_closed", "a marker on a missing mount point": "fails_closed"},
    }

    def test_the_classifier_reads_every_retained_observation_as_the_record_states_it(self):
        for name, expected in self.EXPECTED.items():
            report = json.loads((RECEIPTS / name).read_text(encoding="utf-8"))
            with self.subTest(receipt=name):
                self.assertEqual({item["set"] for item in report["sets"]}, set(expected))
                for item in report["sets"]:
                    with self.subTest(receipt=name, set=item["set"]):
                        outcome, reason = classify(report["control"], item["observation"])
                        self.assertEqual(outcome, expected[item["set"]], reason)
                        self.assertEqual([outcome, reason], item["class"], "the class recorded when the probe ran")

    def test_the_hosted_runners_unit_without_the_marker_is_the_failure_that_the_marker_removes(self):
        report = json.loads((RECEIPTS / "marker-probe-hosted-runner.json").read_text(encoding="utf-8"))
        before = next(item for item in report["sets"] if item["set"].startswith("the shipped directives before round 5"))
        self.assertEqual(before["observation"]["rc"], 0)
        self.assertEqual(before["observation"]["ns"], report["control"]["ns"], "the unit ran in the manager's own namespace")
        self.assertEqual(set(before["observation"]["writes"].values()), {"written"})
        for item in report["sets"]:
            if item["set"] in ("the Claude unit's directives", "the Codex unit's directives"):
                # the manager's own words on systemd 255 are `code=exited/status=226`, without the name that 259 prints (`status=226/NAMESPACE`)
                self.assertEqual((item["observation"]["rc"], item["observation"]["manager"], item["observation"]["started"]), (226, "226", False))

    def test_the_receipts_name_the_two_host_classes(self):
        classes = {name: json.loads((RECEIPTS / name).read_text(encoding="utf-8"))["environment"] for name in self.EXPECTED}
        first, runner = classes["marker-probe-first-host.json"], classes["marker-probe-hosted-runner.json"]
        self.assertRegex(first["systemd"], r"systemd 259")
        self.assertRegex(runner["systemd"], r"systemd 255")
        self.assertEqual(runner["image"]["ImageOS"], "ubuntu24")
        self.assertEqual(first["unshare_user_mount_rc"], 0)
        self.assertNotEqual(runner["unshare_user_mount_rc"], 0)


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
    one clone the unit renders for: the daily run exited 2 every day. The question is whether HEAD is a commit of origin/main, and it is answered by the exit status of `git merge-base --is-ancestor`: 0 for an
    ancestor, 1 for a commit that is not, another non-zero status for an error (git/git@67ad42147a7acc2af6074753ebd03d904476118f, tag v2.53.0, the installed Git: Documentation/git-merge-base.adoc L55-L58;
    builtin/merge-base.c L108-L124 and L44-L56, where a name that does not resolve dies; usage.c L82-L87, where die exits 128)."""

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

    def test_the_statuses_the_clone_test_reads_are_the_ones_git_documents(self):
        """Measured on the installed Git, which is the version of the pin (2.53.0): an ancestor exits 0, a commit that is not exits 1, and a name that does not resolve exits 128, which is neither; the helper reads
        the first two as answers and the third as a clone that cannot be judged."""
        daily = daily_module()

        def status():
            return subprocess.run(["git", "merge-base", "--is-ancestor", "HEAD", "origin/main"], cwd=self.clone, env=self.env, capture_output=True).returncode
        self.assertEqual(status(), 0)
        self.assertTrue(daily.on_reviewed_main(self.clone))
        self.commit_in_clone()
        self.assertEqual(status(), 1)
        self.assertFalse(daily.on_reviewed_main(self.clone))
        self.git("remote", "remove", "origin", cwd=self.clone)
        self.assertEqual(status(), 128)
        with self.assertRaises(daily.CloneRefused):
            daily.on_reviewed_main(self.clone)

    def test_the_clone_test_cites_the_pinned_git_source_where_it_relies_on_it(self):
        """The local review of c56121e4 (P2): the helper, these tests and the decision record cited only the deployment decision, and a correction needs the upstream source at the pinned version. Each of the three
        carries the pin and the locations of the documented contract and of the code that implements it."""
        daily = daily_module()
        record = (ROOT / "docs/decisions/2026-10-12-skill-invoke-rate-timer.md").read_text(encoding="utf-8")
        needles = ("git/git@67ad42147a7acc2af6074753ebd03d904476118f", "Documentation/git-merge-base.adoc L55-L58", "builtin/merge-base.c L108-L124", "L44-L56", "usage.c L82-L87")
        for place, text in (("the helper", daily.on_reviewed_main.__doc__), ("these tests", type(self).__doc__), ("the decision record", record)):
            for needle in needles:
                with self.subTest(place=place, needle=needle):
                    self.assertIn(needle, text)

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
        # the fixture clone is in a temporary directory, which the layout rule refuses (PrivateTmp=true hides it from the service): this test is about which clones are accepted, the rule has its own
        with mock.patch.object(daily, "hidden_by_private_tmp", return_value=False):
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
