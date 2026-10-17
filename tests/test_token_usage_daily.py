"""Daily token projection: whitelisted lane numerators, closed-day history and rendered units, with no live client.

Fixtures are synthetic kernel reports shaped like child-usage.mjs --lanes-sweep (sweepLanes) and skill_usage.py
--lanes (scan_codex_lanes). Private-looking strings are assembled at run time, so this file holds none itself.
The module under test loads inside each test, so a run before it exists fails test by test.
"""
from contextlib import redirect_stderr
from datetime import datetime, timedelta, timezone
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/skill-usage"))
HOME_PATH = "/".join(("", "home", "x", "y"))
PRIVATE = "PRIVATE-" + "label"


def token():
    spec = importlib.util.spec_from_file_location("daily_token_usage_under_test", ROOT / "tools/skill-usage/daily_token_usage.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def message(model="claude-opus-5-5", *, inp=10, out=20, read=300, creation=40, five=30, hour=10):
    return {"ordinal": 1, "model": model, "effort": None, "speed": None,
            "usage": {"input_tokens": inp, "output_tokens": out, "cache_read_input_tokens": read, "cache_creation_input_tokens": creation},
            "cache_creation_5m": five, "cache_creation_1h": hour}


def actor(spawn, messages, complete=True, advisor=None):
    usage = {"complete": complete, "messages": messages, "totals": {}}
    if advisor is not None:
        usage["advisor_totals"] = advisor
    return {"ordinal": 1, "actor": "child", "spawn": spawn, "agent_type": PRIVATE, "session_ordinal": "session-01",
            "measurement": {"usage": usage, "cli_lanes": {"prompt": PRIVATE}}}


def sweep(*, main_mcp=None, workflow_mcp=None, actors=None, workflow_children=2):
    return {"kind": "claude_child_lane_usage", "main_sessions_in_window": 1, "limits": PRIVATE,
            "main": {"children": 1, "tool_calls": 10, "bash_calls": 4, "mcp_calls": main_mcp or {}, "rtk": {"hook_rewrites": 2, "model_typed": 1}},
            "groups": {"by_spawn": {"workflow": {"children": workflow_children, "tool_calls": 7, "bash_calls": 3, "mcp_calls": workflow_mcp or {},
                                                 "rtk": {"hook_rewrites": 1, "model_typed": 0}}}},
            "actors": actors if actors is not None else [actor("main", [message()]), actor("workflow", [message()]), actor("workflow", [message()])]}


def codex_actor(complete=True, cache_write=5, model="gpt-6.1-sol"):
    totals = {"input_tokens": 100, "cached_input_tokens": 60, "cache_write_input_tokens": cache_write, "output_tokens": 7,
              "reasoning_output_tokens": 3, "total_tokens": 110}
    return {"ordinal": 1, "kind": "exec", "role": PRIVATE, "user_config": "ignored",
            "measurement": {"provider_usage": {"complete": complete, "totals": totals, "attempts": [{"configured_model": model, "effort": "max"}]}}}


def codex(*, actors=None):
    def group(sessions, tools, mcp):
        return {"sessions": sessions, "tool_calls": tools, "mcp_calls": mcp, "shell_calls": tools, "rtk_prefixed_shell_calls": 1}
    return {"kind": "codex_lane_usage_report", "sessions_by_kind": {"exec": 2, "subagent": 1}, "limits": PRIVATE,
            "groups": {"workers": group(1, 3, {"ai-memory": 2}), "negative_controls": group(1, 2, {}), "unclassified": group(1, 1, {"bad/account": 4})},
            "actors": actors if actors is not None else [codex_actor(), codex_actor(), codex_actor(complete=False)]}


def write_json(path: Path, value) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))
    return path


class TokenCase(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="token-rate-test-")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.module = token()
        self.aliases, self.servers, _ = self.module.load_servers()

    def day(self, claude=None, codex_report=None, muse=None, date="2026-10-16"):
        return self.module.project_day(claude, codex_report, muse, servers=self.aliases, date=date)


class ProjectionTests(TokenCase):
    def test_only_listed_server_names_are_published(self):
        bad = {"ai-memory": 3, "plugin_context-mode_context-mode": 5, "bad/account": 1, PRIVATE: 2, HOME_PATH: 1}
        row = self.day(sweep(main_mcp=bad), codex())
        lane = row["lanes"]["claude:main"]
        self.assertEqual(lane["mcp"], {"ai-memory": 3, "context-mode": 5})
        self.assertEqual(lane["mcp_other"], 4)
        claude, codex_path = write_json(self.base / "c.json", sweep(main_mcp=bad)), write_json(self.base / "x.json", codex())
        out, history = self.base / "state/latest.json", self.base / "state/history.json"
        code = self.module.main(["--date", "2026-10-16", "--claude-lanes-report", str(claude), "--codex-lanes-report", str(codex_path),
                                 "--out", str(out), "--history", str(history), "--now", "2026-10-17T05:00:00Z"])
        self.assertEqual(code, 0)
        for path in (out, history):
            text = path.read_text()
            for value in ("bad/account", PRIVATE, HOME_PATH, "session-01", "@"):
                self.assertNotIn(value, text, (path.name, value))
        self.assertEqual(oct(out.stat().st_mode & 0o777), "0o600")

    def test_native_aliases_fold_into_their_tool_ids(self):
        lane = self.day(sweep(main_mcp={"codebase-memory": 2, "codebase-memory-mcp": 1, "grafana": 1, "unknown-server": 6}), codex())["lanes"]["claude:main"]
        self.assertEqual(lane["mcp"], {"codebase-memory-mcp": 3, "grafana-observation": 1})
        self.assertEqual(lane["mcp_other"], 6)
        self.assertNotIn("unknown-server", json.dumps(lane))

    def test_usage_sums_complete_actors_only_and_none_complete_is_null(self):
        actors = [actor("main", [message()]), actor("workflow", [message(inp=1000)]), actor("workflow", [message(inp=7)], complete=False)]
        lanes = self.day(sweep(actors=actors), codex())["lanes"]
        self.assertEqual((lanes["claude:workflow"]["actors"], lanes["claude:workflow"]["actors_complete"]), (2, 1))
        self.assertEqual(lanes["claude:workflow"]["usage"]["input"], 1000)
        lanes = self.day(sweep(actors=[actor("main", [message()], complete=False)], workflow_children=0), codex())["lanes"]
        self.assertEqual(set(lanes["claude:main"]["usage"].values()), {None})
        self.assertEqual(lanes["claude:main"]["actors_complete"], 0)

    def test_advisor_sub_inference_is_summed_apart_over_complete_actors_only(self):
        advisor = {"input_tokens": 500, "output_tokens": 20, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}
        actors = [actor("main", [message(inp=10)], advisor=advisor), actor("main", [message(inp=10)], complete=False, advisor={**advisor, "input_tokens": 999}),
                  actor("main", [message(inp=10)])]
        lane = self.day(sweep(actors=actors), codex())["lanes"]["claude:main"]
        self.assertEqual(lane["advisor"], {"input": 500, "output": 20})
        self.assertEqual(lane["usage"]["input"], 20)
        self.assertIsNone(self.day(sweep(), codex())["lanes"]["gpt:codex"]["advisor"])

    def test_cache_writes_by_ttl_add_up_to_cache_creation(self):
        messages = [message(creation=40, five=30, hour=10), message(creation=25, five=None, hour=None), message(creation=12, five=1, hour=2)]
        usage = self.day(sweep(actors=[actor("main", messages)]), codex())["lanes"]["claude:main"]["usage"]
        self.assertEqual((usage["cache_creation_5m"], usage["cache_creation_1h"], usage["cache_creation_ttl_unknown"]), (30, 10, 37))
        self.assertEqual(usage["cache_creation_5m"] + usage["cache_creation_1h"] + usage["cache_creation_ttl_unknown"], usage["cache_creation"])

    def test_codex_cache_writes_stay_null_when_an_actor_lacks_them(self):
        lane = self.day(sweep(), codex(actors=[codex_actor(cache_write=5), codex_actor(cache_write=None)]))["lanes"]["gpt:codex"]
        self.assertIsNone(lane["usage"])
        self.assertIsNone(lane["codex_usage"]["cache_write"])
        self.assertEqual((lane["codex_usage"]["input"], lane["codex_usage"]["cached_input"]), (200, 120))

    def test_codex_lane_sums_the_three_partitioning_groups(self):
        lane = self.day(sweep(), codex())["lanes"]["gpt:codex"]
        self.assertEqual((lane["actors"], lane["actors_complete"], lane["tool_calls"]), (3, 2, 6))
        self.assertEqual((lane["mcp"], lane["mcp_other"]), ({"ai-memory": 2}, 4))
        # Codex runs no RTK rewrite hook: its rtk-prefixed shell calls are typed, never rewrites.
        self.assertEqual(lane["rtk"], {"rewrites": None, "typed": 3, "shell_calls": 6})
        self.assertEqual(lane["spawn"]["codex_subagent_sessions"], 1)
        self.assertEqual(lane["models"], {"gpt-6.1-sol": 3})

    def test_muse_receipts_yield_counts_and_the_model_id_only(self):
        root = self.base / "muse-logs"
        receipt = {"schema": "muse-file-fence/1", "started_utc": "2026-10-16T09:00:00.123456+00:00", "exit_code": 0,
                   "terminal_counts": {"run.terminal.completed": 1}, "requested_model": "muse-wonder-full-1.0",
                   "toolchain_directories": [HOME_PATH + "/go"], "argv": [PRIVATE]}
        write_json(root / "run-alpha/receipt.json", receipt)
        write_json(root / "run-beta/receipt.json", {**receipt, "schema": "other/1"})
        write_json(root / "run-gamma/receipt.json", {**receipt, "started_utc": "2026-10-15T09:00:00+00:00"})
        write_json(root / "run-delta/receipt.json", {**receipt, "exit_code": 1})
        write_json(self.base / "elsewhere/receipt.json", receipt)
        (root / "run-link").mkdir()
        (root / "run-link/receipt.json").symlink_to(self.base / "elsewhere/receipt.json")
        runs = self.module.read_muse_receipts([root])
        lane = self.day(sweep(), codex(), runs)["lanes"]["muse:muse"]
        self.assertEqual(lane["runs"], {"total": 2, "completed": 1, "failed": 1})
        self.assertEqual(lane["models"], {"muse-wonder-full-1.0": 2})
        self.assertEqual(lane["unmeasured"], "no_usage_keys")
        self.assertIsNone(lane["usage"])
        text = json.dumps(lane)
        for value in (HOME_PATH, "run-alpha", PRIVATE):
            self.assertNotIn(value, text)
        self.assertEqual(self.day(sweep(), codex())["lanes"]["muse:muse"]["unmeasured"], "not_configured")

    def test_a_failed_collector_leaves_its_lanes_unknown_never_zero(self):
        row = self.day(None, codex())
        self.assertFalse(row["complete"])
        self.assertEqual(row["collectors"]["claude"], "collector_failed")
        lane = row["lanes"]["claude:main"]
        self.assertEqual(lane["unmeasured"], "collector_failed")
        self.assertIsNone(lane["tool_calls"])
        self.assertIsNone(lane["actors"])


class HistoryTests(TokenCase):
    def row(self, date, complete=True, tool_calls=1):
        row = self.day(sweep(), codex() if complete else None, date=date)
        row["lanes"]["claude:main"]["tool_calls"] = tool_calls
        return {**row, "measured_at": "2026-10-17T01:00:00Z"}

    def test_a_complete_row_is_never_replaced_and_an_incomplete_one_is_superseded(self):
        now = datetime(2026, 10, 17, 5, tzinfo=timezone.utc)
        history = self.module.merge_history(None, [self.row("2026-10-15"), self.row("2026-10-16", complete=False)], now=now)
        old_complete, old_incomplete = history["rows"]
        again = self.module.merge_history(history, [self.row("2026-10-15", tool_calls=99), self.row("2026-10-16", tool_calls=5)], now=now)
        self.assertEqual(len(again["rows"]), 2)
        self.assertEqual(again["rows"][0], old_complete)
        self.assertEqual(again["rows"][1]["supersedes_row_sha256"], old_incomplete["row_sha256"])
        self.assertEqual(again["rows"][1]["lanes"]["claude:main"]["tool_calls"], 5)
        tampered = json.loads(json.dumps(again))
        tampered["rows"][0]["lanes"]["claude:main"]["tool_calls"] = 7
        with self.assertRaises(ValueError):
            self.module.merge_history(tampered, [], now=now)

    def test_a_failed_re_collection_never_erases_a_measured_lane(self):
        now = datetime(2026, 10, 17, 5, tzinfo=timezone.utc)
        claude_only = self.row("2026-10-16", complete=False, tool_calls=12)
        history = self.module.merge_history(None, [claude_only], now=now)
        failed = {**self.day(None, None, date="2026-10-16"), "measured_at": "2026-10-17T02:00:00Z"}
        kept = self.module.merge_history(history, [failed], now=now)
        self.assertEqual(kept["rows"], history["rows"])
        self.assertEqual(kept["rows"][0]["lanes"]["claude:main"]["tool_calls"], 12)
        complete = self.row("2026-10-16", tool_calls=13)
        replaced = self.module.merge_history(kept, [complete], now=now)
        self.assertEqual((replaced["rows"][0]["complete"], replaced["rows"][0]["supersedes_row_sha256"]), (True, history["rows"][0]["row_sha256"]))

    def test_the_cap_drops_the_oldest_rows_and_rows_stay_sorted(self):
        now = datetime(2026, 10, 17, 5, tzinfo=timezone.utc)
        rows = [self.row(f"2026-10-{day:02d}") for day in (12, 10, 14, 11, 13)]
        history = self.module.merge_history(None, rows, now=now, cap=3)
        self.assertEqual([row["date"] for row in history["rows"]], ["2026-10-12", "2026-10-13", "2026-10-14"])

    def test_the_rollup_sums_numerators_over_the_window_and_discloses_gaps(self):
        now = datetime(2026, 10, 17, 5, tzinfo=timezone.utc)
        history = self.module.merge_history(None, [self.row("2026-10-09", tool_calls=1000), self.row("2026-10-12", tool_calls=3),
                                                   self.row("2026-10-16", complete=False, tool_calls=4)], now=now)
        rollup = self.module.rollup(history, days=7, until=now.date())
        self.assertEqual((rollup["since"], rollup["until"], rollup["days_present"], rollup["days_complete"]), ("2026-10-10", "2026-10-17", 2, 1))
        self.assertEqual(rollup["lanes"]["claude:main"]["tool_calls"], 7)
        self.assertEqual(rollup["lanes"]["claude:main"]["usage"]["cache_read"], 600)
        self.assertEqual(rollup["lanes"]["gpt:codex"]["tool_calls"], 6)
        self.assertEqual(rollup["lanes"]["gpt:codex"]["days_measured"], 1)
        self.assertEqual(rollup["lanes"]["muse:muse"]["unmeasured"], "not_configured")

    def test_partial_days_never_enter_the_history(self):
        now = datetime(2026, 10, 17, 5, tzinfo=timezone.utc)
        with self.assertRaises(ValueError):
            self.module.merge_history(None, [self.row("2026-10-17")], now=now)


class CollectionTests(TokenCase):
    def fake_run(self, commands, *, fail=False):
        def run(command, **kwargs):
            if command[:3] == ["git", "branch", "--show-current"]:
                return subprocess.CompletedProcess(command, 0, "main\n", "")
            commands.append(command)
            if fail:
                return subprocess.CompletedProcess(command, 1, "", "PRIVATE-collector-" + "stderr")
            report = codex() if "--lanes" in command else sweep()
            return subprocess.CompletedProcess(command, 0, json.dumps(report), "")
        return run

    def test_backfill_runs_one_sweep_and_one_lanes_per_missing_or_incomplete_date(self):
        now = datetime(2026, 10, 17, 5, tzinfo=timezone.utc)
        history_path, out = self.base / "state/history.json", self.base / "state/latest.json"
        complete = {**self.day(sweep(), codex(), date="2026-10-14"), "measured_at": "2026-10-15T01:00:00Z"}
        incomplete = {**self.day(sweep(), None, date="2026-10-15"), "measured_at": "2026-10-16T01:00:00Z"}
        seeded = self.module.merge_history(None, [complete, incomplete], now=now)
        write_json(history_path, seeded)
        commands = []
        with mock.patch("subprocess.run", side_effect=self.fake_run(commands)):
            code = self.module.main(["--codex-root", str(self.base / "codex"), "--claude-root", str(self.base / "claude"), "--now", "2026-10-17T05:00:00Z",
                                     "--out", str(out), "--history", str(history_path)])
        self.assertEqual(code, 0)
        windows = sorted({(command[command.index("--since") + 1], command[command.index("--until") + 1]) for command in commands})
        expected_days = ["2026-10-10", "2026-10-11", "2026-10-12", "2026-10-13", "2026-10-15", "2026-10-16"]
        self.assertEqual(windows, sorted([(f"{day}T00:00:00Z", (datetime.fromisoformat(day) + timedelta(days=1)).date().isoformat() + "T00:00:00Z") for day in expected_days]
                                         + [("2026-10-17T00:00:00Z", "2026-10-17T05:00:00Z")]))
        self.assertEqual(sum("--lanes-sweep" in command for command in commands), 7)
        self.assertEqual(sum("--lanes" in command for command in commands), 7)
        self.assertFalse(any("--run-skill-doctor" in command for command in commands))
        history = json.loads(history_path.read_text())
        self.assertEqual([row["date"] for row in history["rows"]], ["2026-10-10", "2026-10-11", "2026-10-12", "2026-10-13", "2026-10-14", "2026-10-15", "2026-10-16"])
        by_date = {row["date"]: row for row in history["rows"]}
        self.assertEqual(by_date["2026-10-14"], seeded["rows"][0])
        self.assertEqual(by_date["2026-10-15"]["supersedes_row_sha256"], seeded["rows"][1]["row_sha256"])
        latest = json.loads(out.read_text())
        self.assertEqual(latest["partial_today"]["until"], "2026-10-17T05:00:00Z")
        self.assertEqual((latest["rollup"]["days_present"], latest["rollup"]["days_complete"]), (7, 7))

    def test_destinations_inside_a_git_worktree_are_refused(self):
        claude, codex_path = write_json(self.base / "c.json", sweep()), write_json(self.base / "x.json", codex())
        inside = ROOT / "token-rate-refusal-probe.json"
        with redirect_stderr(io.StringIO()):
            code = self.module.main(["--date", "2026-10-16", "--claude-lanes-report", str(claude), "--codex-lanes-report", str(codex_path),
                                     "--out", str(inside), "--history", str(self.base / "history.json"), "--now", "2026-10-17T05:00:00Z"])
        self.assertEqual(code, 2)
        self.assertFalse(inside.exists())
        self.assertFalse((self.base / "history.json").exists())

    def test_live_collection_refuses_a_non_main_checkout_and_missing_roots(self):
        args = ["--now", "2026-10-17T05:00:00Z", "--out", str(self.base / "o.json"), "--history", str(self.base / "h.json")]
        def branch(command, **kwargs):
            return subprocess.CompletedProcess(command, 0, "feature-branch\n", "")
        with mock.patch("subprocess.run", side_effect=branch), redirect_stderr(io.StringIO()):
            self.assertEqual(self.module.main(["--codex-root", "/fixture/codex", "--claude-root", "/fixture/claude", *args]), 2)
            self.assertEqual(self.module.main(["--codex-root", "/fixture/codex", *args]), 2)
        self.assertFalse((self.base / "o.json").exists())

    def test_collector_errors_never_reach_output_and_hard_failures_print_one_fixed_line(self):
        commands, stderr = [], io.StringIO()
        out, history = self.base / "state/latest.json", self.base / "state/history.json"
        with mock.patch("subprocess.run", side_effect=self.fake_run(commands, fail=True)), redirect_stderr(stderr):
            code = self.module.main(["--codex-root", "/fixture/codex", "--claude-root", "/fixture/claude", "--now", "2026-10-17T05:00:00Z",
                                     "--out", str(out), "--history", str(history), "--backfill-days", "1"])
        self.assertEqual(code, 1)
        self.assertNotIn("PRIVATE", stderr.getvalue() + out.read_text() + history.read_text())
        self.assertEqual(json.loads(history.read_text())["rows"][0]["collectors"]["claude"], "collector_failed")
        history.write_text("{not json")
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            code = self.module.main(["--date", "2026-10-16", "--claude-lanes-report", str(write_json(self.base / "c.json", sweep())),
                                     "--out", str(out), "--history", str(history), "--now", "2026-10-17T05:00:00Z"])
        self.assertEqual(code, 2)
        self.assertEqual(stderr.getvalue(), self.module.FAILURE + "\n")
        self.assertEqual(history.read_text(), "{not json")


class UnitTests(TokenCase):
    def test_the_rendered_units_name_the_projection_paths(self):
        daily = importlib.import_module("daily_skill_usage")
        daily.render_units(self.base, Path("/fixture/live clone"), Path(sys.executable), Path("/fixture/bin/node"), names=self.module.UNITS)
        service, timer = (self.base / "token-rate.service").read_text(), (self.base / "token-rate.timer").read_text()
        self.assertIn('"/fixture/live clone/tools/skill-usage/daily_token_usage.py"', service)
        for text in ("--codex-root", "--claude-root", "token-rate-latest.json", "--history", "token-rate-history.json", "UMask=0077", "Type=oneshot"):
            self.assertIn(text, service)
        self.assertNotIn("--run-skill-doctor", service)
        self.assertIn("OnCalendar=hourly", timer)
        self.assertIn("Unit=token-rate.service", timer)

    @unittest.skipUnless(shutil.which("systemd-analyze") and shutil.which("node"), "native systemd verifier or node unavailable")
    def test_native_user_unit_verification_needs_no_session_or_install(self):
        daily = importlib.import_module("daily_skill_usage")
        runtime = self.base / "runtime"
        runtime.mkdir(mode=0o700)
        daily.render_units(self.base, ROOT, Path(sys.executable), Path(shutil.which("node")), names=self.module.UNITS)
        result = subprocess.run([shutil.which("systemd-analyze"), "--user", "--man=no", "verify", str(self.base / "token-rate.service"), str(self.base / "token-rate.timer")],
                                env={"HOME": str(self.base), "PATH": os.defpath, "XDG_RUNTIME_DIR": str(runtime)}, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.base / ".config/systemd/user").exists())


@unittest.skipUnless(shutil.which("node"), "node unavailable")
class RealKernelTests(TokenCase):
    """Guards kernel shape drift: the unchanged child-usage.mjs reads a synthetic transcript tree."""

    def row(self, ident, at, usage, cache=None):
        message = {"id": ident, "model": "claude-opus-5-5", "role": "assistant", "content": [{"type": "text", "text": "ok"}], "usage": usage}
        if cache is not None:
            message["usage"] = {**usage, "cache_creation": cache}
        return {"type": "assistant", "timestamp": at, "message": message}

    def test_the_projection_reads_the_real_sweep(self):
        project = self.base / "claude/projects/fixture-project"
        user = {"type": "user", "timestamp": "2026-10-16T10:00:00Z", "message": {"role": "user", "content": "hello"}}
        usage = {"input_tokens": 5, "output_tokens": 9, "cache_read_input_tokens": 100, "cache_creation_input_tokens": 30}
        main = [user, self.row("msg_main_1", "2026-10-16T10:00:01Z", usage, {"ephemeral_5m_input_tokens": 0, "ephemeral_1h_input_tokens": 30})]
        child = [user, self.row("msg_child_1", "2026-10-16T10:00:02Z", usage, {"ephemeral_5m_input_tokens": 30, "ephemeral_1h_input_tokens": 0})]
        project.mkdir(parents=True)
        (project / "session-a.jsonl").write_text("\n".join(json.dumps(row) for row in main) + "\n")
        (project / "session-a/subagents").mkdir(parents=True)
        (project / "session-a/subagents/agent-one.jsonl").write_text("\n".join(json.dumps(row) for row in child) + "\n")
        result = subprocess.run([shutil.which("node"), str(ROOT / "examples/claude-native/workflows/child-usage.mjs"), "--lanes-sweep", "--root", str(self.base / "claude/projects"),
                                 "--since", "2026-10-16T00:00:00Z", "--until", "2026-10-17T00:00:00Z"], capture_output=True, text=True, timeout=120, stdin=subprocess.DEVNULL)
        self.assertEqual(result.returncode, 0, result.stderr[-400:])
        # Files written now carry today's mtime, after the window start, so the kernel reads them.
        lanes = self.day(json.loads(result.stdout), codex())["lanes"]
        self.assertEqual((lanes["claude:main"]["actors"], lanes["claude:main"]["actors_complete"]), (1, 1))
        self.assertEqual(lanes["claude:main"]["usage"], {"input": 5, "output": 9, "cache_read": 100, "cache_creation": 30,
                                                         "cache_creation_5m": 0, "cache_creation_1h": 30, "cache_creation_ttl_unknown": 0})
        self.assertEqual((lanes["claude:agent_tool"]["actors"], lanes["claude:agent_tool"]["usage"]["cache_creation_5m"]), (1, 30))
        self.assertEqual(lanes["claude:main"]["models"], {"claude-opus-5-5": 1})
        self.assertEqual(lanes["claude:workflow"]["unmeasured"], "no_rows_in_window")


if __name__ == "__main__":
    unittest.main()
