"""tools/startup-context/startup_context.py: the /context report parser, the $0 guard, per-variant receipts and the
summary of each component over the control. The client is a stand-in script; the report text is synthetic."""

import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "startup-context" / "startup_context.py"
spec = importlib.util.spec_from_file_location("startup_context", TOOL)
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)

HOME = "/home/example"


def report(total="12.4k", extra_server=None, extra_tokens="1.2k"):
    servers = "| mcp__fixture__lookup | fixture | 640 |\n| mcp__fixture__list | fixture | 1k |\n"
    if extra_server:
        servers += f"| mcp__{extra_server}__run | {extra_server} | {extra_tokens} |\n"
    return (f"## Context Usage\n\n**Model:** claude-fixture-1  \n**Tokens:** {total} / 1m (1%)\n\n"
            "### Estimated usage by category\n\n| Category | Tokens | Percentage |\n|----------|--------|------------|\n"
            "| System prompt | 2.5k | 0.2% |\n| MCP tools (deferred) | 9.1k | 0.9% |\n| Skills | ~300 | 0.0% |\n"
            "| Free space | 948.1k | 94.8% |\n\n### MCP Tools\n\n| Tool | Server | Tokens |\n|------|--------|--------|\n"
            f"{servers}\n### Memory Files\n\n| Type | Path | Tokens |\n|------|------|--------|\n"
            f"| User | {HOME}/.claude/CLAUDE.md | 966 |\n| Project | /srv/elsewhere/CLAUDE.md | 120 |\n\n"
            "### Skills\n\n| Skill | Source | Tokens |\n|-------|--------|--------|\n| fixture-skill | User | ~200 |\n")


FAKE_CLAUDE = """#!/usr/bin/env python3
import json, os, sys
if sys.argv[1:] == ["--version"]:
    print("9.9.9 (Claude Code)"); sys.exit(0)
argv = sys.argv[1:]
with open(os.environ["FAKE_LOG"], "a") as log:
    log.write(json.dumps(argv) + "\\n")
servers = []
if "--mcp-config" in argv:
    servers = sorted(json.load(open(argv[argv.index("--mcp-config") + 1]))["mcpServers"])
failed = set(os.environ.get("FAKE_FAILED", "").split(","))
init = {"type": "system", "subtype": "init", "plugins": [{"name": "fixture-plugin"}],
        "mcp_servers": [{"name": n, "status": "failed" if n in failed else "connected"} for n in servers]}
text = open(os.environ["FAKE_REPORT_DIR"] + "/" + ("extra" if "extra" in servers else "base")).read()
print(json.dumps(init))
print(json.dumps({"type": "result", "is_error": False, "num_turns": int(os.environ.get("FAKE_TURNS", "0")),
                  "total_cost_usd": float(os.environ.get("FAKE_COST", "0")), "result": text}))
"""


class Parse(unittest.TestCase):
    def test_the_report_tables_parse_with_the_client_rounding(self):
        parsed = S.parse(report(), HOME)
        self.assertEqual((parsed["model"], parsed["total_tokens"], parsed["window_tokens"]), ("claude-fixture-1", 12400, 1_000_000))
        self.assertEqual([(c["category"], c["tokens"]) for c in parsed["categories"]][:3],
                         [("System prompt", 2500), ("MCP tools (deferred)", 9100), ("Skills", 300)])
        self.assertEqual(parsed["mcp_tokens_by_server"], {"fixture": 1640})
        self.assertTrue(parsed["mcp_tools_deferred"])
        self.assertEqual(parsed["skills"], [{"name": "fixture-skill", "source": "User", "tokens": 200}])

    def test_a_receipt_shows_no_absolute_home_path(self):
        paths = [item["path"] for item in S.parse(report(), HOME)["memory_files"]]
        self.assertEqual(paths, ["~/.claude/CLAUDE.md", "<absolute path outside home>"])
        self.assertEqual(S.shown_flags(["--add-dir", f"{HOME}/repo", "--mcp-config", "/tmp/x/mcp-a.json"], HOME),
                         ["--add-dir", "~/repo", "--mcp-config", "mcp-a.json"])

    def test_the_dash_encoded_home_in_a_project_path_is_shortened_too(self):
        self.assertEqual(S.private_path(f"{HOME}/.claude/projects/-home-example-code-repo/memory/MEMORY.md", HOME),
                         "~/.claude/projects/-~-code-repo/memory/MEMORY.md")

    def test_token_cells(self):
        self.assertEqual([S.tokens(cell) for cell in ("689", "2.5k", "~200", "1m", "1,024", "n/a")],
                         [689, 2500, 200, 1_000_000, 1024, None])


class Measure(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.claude = self.tmp / "claude"
        self.claude.write_text(FAKE_CLAUDE)
        self.claude.chmod(0o755)
        (self.tmp / "reports").mkdir()
        (self.tmp / "reports" / "base").write_text(report())
        (self.tmp / "reports" / "extra").write_text(report(total="13.0k", extra_server="extra"))
        self.log = self.tmp / "log.jsonl"
        self.enterContext(mock.patch.dict(os.environ, {"FAKE_LOG": str(self.log), "FAKE_REPORT_DIR": str(self.tmp / "reports")}))
        template = self.tmp / "claude-user.json"
        template.write_text(json.dumps({"mcpServers": {"fixture": {"type": "http", "url": "http://127.0.0.1:1/mcp"},
                                                       "extra": {"type": "http", "url": "http://127.0.0.1:2/mcp"}}}))
        self.enterContext(mock.patch.object(S, "MCP_TEMPLATE", template))
        self.launch = {"schema": S.LAUNCH_SCHEMA, "role_id": "fixture-role", "cwd": str(self.tmp),
                       "variants": [{"id": "control", "mcp_servers": ["fixture"], "settings": {"enabledPlugins": {"p@m": False}}},
                                    {"id": "+extra", "component": "extra", "mcp_servers": ["fixture", "extra"],
                                     "settings": {"enabledPlugins": {"p@m": False}}}]}

    def test_each_variant_is_measured_and_the_component_is_reported_over_the_control(self):
        doc = S.measure(self.launch, self.tmp / "out", str(self.claude), HOME)
        self.assertEqual([(row["variant"], row["total_tokens"], row["over_control"]) for row in doc["rows"]],
                         [("control", 12400, None), ("+extra", 13000, 600)])
        calls = [json.loads(line) for line in self.log.read_text().splitlines()]
        self.assertEqual([call[:5] for call in calls], [["-p", "/context", "--output-format", "stream-json", "--verbose"]] * 2)
        self.assertIn("--strict-mcp-config", calls[0])
        receipt = json.loads((self.tmp / "out" / "fixture-role.+extra.json").read_text())
        self.assertEqual((receipt["client_version"], receipt["num_turns"], receipt["total_cost_usd"]), ("9.9.9", 0, 0))
        self.assertIn("mcp-extra-fixture.json", receipt["flags"])
        self.assertNotIn(HOME, json.dumps(receipt))
        self.assertEqual(receipt["mcp_servers"], [{"name": "extra", "status": "connected"}, {"name": "fixture", "status": "connected"}])
        self.assertEqual(receipt["plugins"], ["fixture-plugin"])

    def test_a_component_that_did_not_load_gets_no_delta(self):
        with mock.patch.dict(os.environ, {"FAKE_FAILED": "extra"}):
            doc = S.measure(self.launch, self.tmp / "out", str(self.claude), HOME)
        row = doc["rows"][1]
        self.assertEqual((row["component_loaded"], row["over_control"], row["servers_not_connected"]), (False, None, ["extra"]))

    def test_a_run_that_reached_a_model_is_refused_and_writes_nothing(self):
        for env in ({"FAKE_TURNS": "1"}, {"FAKE_COST": "0.01"}):
            with self.subTest(env=env), mock.patch.dict(os.environ, env):
                out = self.tmp / f"out-{next(iter(env))}"
                with self.assertRaises(SystemExit) as raised:
                    S.measure(self.launch, out, str(self.claude), HOME)
                self.assertIn("refused", str(raised.exception))
                self.assertEqual(list(out.glob("*.json")), [])

    def test_the_first_variant_must_be_the_control(self):
        launch = dict(self.launch, variants=self.launch["variants"][::-1])
        with self.assertRaises(SystemExit):
            S.measure(launch, self.tmp / "out", str(self.claude), HOME)

    def test_a_server_outside_the_template_is_refused(self):
        launch = dict(self.launch, variants=[{"id": "control", "mcp_servers": ["unknown"]}])
        with self.assertRaises(SystemExit):
            S.measure(launch, self.tmp / "out", str(self.claude), HOME)


if __name__ == "__main__":
    unittest.main()
