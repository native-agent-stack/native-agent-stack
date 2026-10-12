"""token_tools_now.py runs each token tool's own report command and keeps its exit code and estimate."""

from __future__ import annotations

import html
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("local_pages_token_tools", ROOT / "tools/local-pages/token_tools_now.py")
tools = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tools)
SYNTHETIC_HOME = "/".join(["", "home", "synthetic-user", "ledger"])
SYNTHETIC_EMAIL = "owner" + "@" + "example.org"
RTK_SUMMARY = {"total_saved": 222382401, "avg_savings_pct": 16.98, "total_commands": 168688, "total_input": 1309306534, "total_output": 1086961158}
RTK_JSON = {"summary": dict(RTK_SUMMARY, total_time_ms=5, db_path=SYNTHETIC_HOME), "daily": [{"date": "2026-10-11"}]}
DOCTOR = "\x1b[32m[PASS]\x1b[0m Runtime\n[PASS] Hooks\n[SKIP] Bun\n[WARN] FTS5 cache at " + SYNTHETIC_HOME + "\n"
AGENT = "agent-savings --check-perf --hours 24 --format json"


def completed(code: int, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess([], code, stdout, stderr)


class Runner:
    """Answer each argv from a table keyed by the executable's name and its arguments; record every call."""

    def __init__(self, outcomes: dict):
        self.outcomes, self.calls = outcomes, []

    def __call__(self, argv, **options):
        self.calls.append((list(argv), options))
        name = Path(argv[0]).name
        key = name + " " + " ".join(argv[2:] if name == "node" else argv[1:])
        outcome = self.outcomes.get(key, FileNotFoundError(key))
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def context_cli(directory: str) -> Path:
    (Path(directory) / "package.json").write_text(json.dumps({"version": "1.0.169"}))
    return Path(directory) / "cli.bundle.mjs"


class TokenToolsTests(unittest.TestCase):
    def setUp(self):
        self.directory = self.enterContext(tempfile.TemporaryDirectory())

    def test_each_row_keeps_its_command_exit_code_version_and_own_estimate(self):
        runner = Runner({
            "rtk gain --format json": completed(0, json.dumps(RTK_JSON)), "rtk --version": completed(0, "rtk 0.51.0\n"),
            "headroom " + AGENT: completed(1, "", "Error: 0.0% savings below 90.0% target for agent-90\n"),
            "headroom --version": completed(0, "headroom, version 0.40.0\n"), "headroom output-savings": completed(0, "No output-savings data yet.\n"),
            "node doctor": completed(0, DOCTOR)})
        document = tools.collect("rtk", "headroom", "node", context_cli(self.directory), timeout=5, runner=runner)
        self.assertEqual(set(document), {"schema", "generated_utc", "tools"})
        self.assertEqual(document["schema"], "token-tools-now/1")
        rtk, agent, output, doctor = document["tools"]
        self.assertEqual((rtk["tool"], rtk["command"], rtk["rc"], rtk["version"]), ("RTK", "rtk gain --format json", 0, "rtk 0.51.0"))
        self.assertEqual(rtk["estimate"], RTK_SUMMARY)
        self.assertEqual((agent["command"], agent["rc"], agent["estimate"]), ("headroom " + AGENT, 1, None))
        self.assertEqual(agent["message"], "Error: 0.0% savings below 90.0% target for agent-90")
        self.assertIn("profile target", agent["note"])
        self.assertEqual(output["estimate"], {"report": "No output-savings data yet."})
        self.assertIn("counterfactual unless an A/B holdout is set", output["note"])
        self.assertEqual((doctor["version"], doctor["estimate"]), ("context-mode 1.0.169", {"checks": {"PASS": 2, "SKIP": 1, "WARN": 1}}))
        self.assertIn("ctx_stats", doctor["note"])
        for argv, options in runner.calls:
            with self.subTest(argv=argv):
                self.assertIs(options["stdin"], subprocess.DEVNULL)
                self.assertEqual({key: options["env"][key] for key in tools.QUIET}, tools.QUIET)
                self.assertEqual(options["timeout"], 30 if argv[-1] == "--version" else 5)

    def test_commands_that_cannot_run_are_recorded_rows_not_exceptions(self):
        runner = Runner({"rtk gain --format json": FileNotFoundError("rtk"), "headroom " + AGENT: subprocess.TimeoutExpired("headroom", 5),
                         "headroom output-savings": PermissionError("headroom")})
        document = tools.collect("rtk", "headroom", "node", None, timeout=5, runner=runner)
        rows = document["tools"]
        self.assertEqual([(row["rc"], row["error"]) for row in rows],
                         [(None, "command not found"), (None, "timed out after 5 s"), (None, "could not start (PermissionError)"), (None, "not run: no --context-mode-cli given")])
        self.assertEqual([row["estimate"] for row in rows], [None] * 4)
        self.assertEqual([row["version"] for row in rows], [None] * 4)
        self.assertFalse(any(argv[0] == "node" for argv, _ in runner.calls))

    def test_estimates_and_messages_are_sanitized_before_publication(self):
        runner = Runner({"rtk gain --format json": completed(0, "not json"), "headroom " + AGENT: completed(0, json.dumps({"log": SYNTHETIC_HOME, "contact": SYNTHETIC_EMAIL, "savings_pct": 91.2})),
                         "headroom output-savings": completed(2, "", "failed reading " + SYNTHETIC_HOME + " for " + SYNTHETIC_EMAIL.replace("@", "%40")),
                         "node doctor": completed(0, DOCTOR)})
        document = tools.collect("rtk", "headroom", "node", context_cli(self.directory), timeout=5, runner=runner)
        serialized = json.dumps(document)
        self.assertNotIn("synthetic-user", serialized)
        self.assertNotIn(SYNTHETIC_EMAIL, serialized)
        self.assertNotIn("owner%40", serialized)
        self.assertEqual(document["tools"][0]["estimate"], None)
        self.assertEqual(document["tools"][1]["estimate"], {"log": "${USER_HOME}/ledger", "contact": "[email omitted]", "savings_pct": 91.2})
        self.assertEqual(document["tools"][2]["message"], "failed reading ${USER_HOME}/ledger for [email omitted]")

    def test_dict_keys_are_sanitized_as_well_as_values(self):
        # The micro's (a)10 at 50977b00: estimates passed sanitize(), which projects values only, while the module
        # docstring promised the whole file; a path or address used as a JSON key reached the report verbatim.
        keyed = {SYNTHETIC_HOME + "/proxy.log": {"saved": 1}, SYNTHETIC_EMAIL: 2, "owner%40example.org": 3, "nested": {SYNTHETIC_HOME: [{SYNTHETIC_EMAIL: 4}]}}
        runner = Runner({"headroom " + AGENT: completed(0, json.dumps(keyed))})
        document = tools.collect("rtk", "headroom", "node", None, timeout=5, runner=runner)
        self.assertEqual(document["tools"][1]["estimate"], {"${USER_HOME}/ledger/proxy.log": {"saved": 1}, "[email omitted]": 2, "[email omitted] (2)": 3,
                                                            "nested": {"${USER_HOME}/ledger": [{"[email omitted]": 4}]}})
        serialized = json.dumps(document)
        self.assertNotIn("synthetic-user", serialized)
        self.assertNotIn(SYNTHETIC_EMAIL, serialized)
        self.assertNotIn("owner%40", serialized)

    def test_quoted_local_parts_are_masked_in_keys_and_values(self):
        # Astra's first read of a737ef98 (P1): the token report passes the same shared mask, so a quoted local part
        # must not reach token-tools-now.json as a key or a value. The parts are unique, so no address grammar is needed.
        quoted = '"zqlocal key"' + "@" + "zqdomain.example.org"
        keyed = {quoted: {"note": "%22zqlocalvalue%22%40zqdomain.example.org"}, "path": ['&quot;zqlocal list&quot;&#64;zqdomain.example.org']}
        runner = Runner({"headroom " + AGENT: completed(0, json.dumps(keyed))})
        serialized = json.dumps(tools.collect("rtk", "headroom", "node", None, timeout=5, runner=runner))
        for _ in range(2):
            serialized = html.unescape(unquote(serialized))
        self.assertNotIn("zqlocal", serialized)
        self.assertNotIn("zqdomain", serialized)
        self.assertIn("[email omitted]", serialized)

    def test_empty_quoted_and_punctuation_only_local_parts_are_masked_in_keys_and_values(self):
        # Astra's read of 51f85b5b, P1 1: the token report shares the mask, so these forms must not reach the file as a
        # key or a value, in plain, percent or entity form; residue the mask cannot classify is dropped whole.
        keyed = {'""' + "@" + "zqdomain.example.target": "!!!" + "@" + "zqdomain.example.target", "p": ["%22%22%40zqdomain.example.target", "&#33;&#33;&#33;&#64;zqdomain.example.target"],
                 "residue": '"zqsp" ' + "@" + "zqdomain.example.org"}
        runner = Runner({"headroom " + AGENT: completed(0, json.dumps(keyed))})
        serialized = json.dumps(tools.collect("rtk", "headroom", "node", None, timeout=5, runner=runner))
        for _ in range(2):
            serialized = html.unescape(unquote(serialized))
        self.assertNotIn("zqdomain", serialized)
        self.assertNotIn("zqsp", serialized)
        self.assertIn("[value omitted: an at sign beside a word remained after masking]", serialized)

    def test_destination_refuses_a_parent_or_ancestor_that_links_into_the_repository(self):
        # Codex token_tools_now.py:160 and the micro's (a)2 at 50977b00: abspath() follows no symlink, so
        # <tmp>/state linked to the checkout let --out land inside the repository.
        base = Path(self.directory)
        (base / "state").symlink_to(ROOT, target_is_directory=True)
        (base / "deep").symlink_to(ROOT / "tools", target_is_directory=True)
        outside = Path(self.enterContext(tempfile.TemporaryDirectory()))
        (base / "elsewhere").symlink_to(outside, target_is_directory=True)
        for inside in (base / "state/token-tools-now.json", base / "deep/local-pages/out/token-tools-now.json", base / "state"):
            with self.subTest(inside=inside), self.assertRaises(ValueError):
                tools.destination(inside)
        self.assertEqual(tools.destination(base / "elsewhere/token-tools-now.json"), base / "elsewhere/token-tools-now.json")
        with patch.object(tools, "collect") as collect, patch.object(tools, "publish") as publish, patch("sys.stderr"):
            self.assertEqual(tools.main(["--out", str(base / "state/token-tools-now.json")]), 2)
        collect.assert_not_called()
        publish.assert_not_called()

    def test_publish_refuses_the_repository_and_replaces_atomically(self):
        for inside in (ROOT / "token-tools-now.json", ROOT / "tools/local-pages/out/token-tools-now.json", ROOT):
            with self.subTest(inside=inside), self.assertRaises(ValueError):
                tools.publish(inside, {"schema": "token-tools-now/1"})
        self.assertFalse((ROOT / "token-tools-now.json").exists())
        target = Path(self.directory) / "pages/token-tools-now.json"
        tools.publish(target, {"schema": "token-tools-now/1", "tools": []})
        self.assertEqual(json.loads(target.read_text()), {"schema": "token-tools-now/1", "tools": []})
        with patch.object(tools.json, "dump", side_effect=ValueError("synthetic write failure")), self.assertRaises(ValueError):
            tools.publish(target, {"schema": "token-tools-now/1", "tools": [1]})
        self.assertEqual(json.loads(target.read_text()), {"schema": "token-tools-now/1", "tools": []})
        self.assertEqual(sorted(path.name for path in target.parent.iterdir()), ["token-tools-now.json"])

    def test_main_refuses_a_repository_destination_before_running_any_tool(self):
        with patch.object(tools, "collect") as collect, patch("sys.stderr"):
            self.assertEqual(tools.main(["--out", str(ROOT / "token-tools-now.json")]), 2)
        collect.assert_not_called()
        target = Path(self.directory) / "token-tools-now.json"
        with patch.object(tools, "collect", return_value={"schema": "token-tools-now/1", "tools": []}) as collect:
            self.assertEqual(tools.main(["--out", str(target), "--rtk", "rtk-fixture", "--timeout", "7"]), 0)
        self.assertEqual(collect.call_args.args[:3], ("rtk-fixture", "headroom", "node"))
        self.assertEqual(collect.call_args.kwargs, {"timeout": 7})
        self.assertEqual(json.loads(target.read_text())["schema"], "token-tools-now/1")


if __name__ == "__main__":
    unittest.main()
