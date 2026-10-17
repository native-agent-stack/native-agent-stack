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
only_in, _, name = os.environ.get("FAKE_FAILED_IN", "").partition(":")
if only_in and only_in in servers:
    failed.add(name)
enabled = []
if "--settings" in argv:
    enabled = [k.split("@")[0] for k, v in json.loads(argv[argv.index("--settings") + 1]).get("enabledPlugins", {}).items() if v]
init = {"type": "system", "subtype": "init", "plugins": [{"name": n} for n in ["fixture-plugin", *enabled]],
        "mcp_servers": [{"name": n, "status": "failed" if n in failed else "connected"} for n in servers]}
text = open(os.environ["FAKE_REPORT_DIR"] + "/" + ("extra" if any(n.split(":")[-1] == "extra" for n in servers) else "base")).read()
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

    def test_inline_settings_are_shown_without_environment_values_or_absolute_paths(self):
        # The co-op's local review of #1203 at 71b3fde3 (P1, :173-177): an inline --settings value was copied into the
        # receipt unchanged, so an environment value and a home path survived. Synthetic values only.
        secret = "synthetic-" + "v" * 24
        settings = {"env": {"FIXTURE_API_KEY": secret, "FIXTURE_DIR": HOME + "/data"},
                    "enabledPlugins": {"p@m": True}, "statusLine": {"command": HOME + "/bin/status"},
                    "apiKeyHelper": "/srv/elsewhere/helper"}
        launch = dict(self.launch, variants=[dict(self.launch["variants"][0], settings=settings)])
        S.measure(launch, self.tmp / "out", str(self.claude), HOME)
        text = (self.tmp / "out" / "fixture-role.control.json").read_text()
        self.assertNotIn(secret, text)
        self.assertNotIn(HOME, text)
        self.assertNotIn("/srv/elsewhere", text)
        shown = json.loads(json.loads(text)["flags"][json.loads(text)["flags"].index("--settings") + 1])
        # The co-op's local review at 3a1f8618 (P1, :234-240): the equals form and a repeated flag went unsanitized.
        other = "synthetic-" + "w" * 24
        launch = dict(self.launch, variants=[dict(self.launch["variants"][0], flags=[
            "--settings=" + json.dumps({"env": {"FIXTURE_TOKEN": secret}}), "--settings", json.dumps({"env": {"B": other}}),
            "--add-dir=" + HOME + "/elsewhere"])])
        S.measure(launch, self.tmp / "out2", str(self.claude), HOME)
        text2 = (self.tmp / "out2" / "fixture-role.control.json").read_text()
        for value in (secret, other, HOME):
            self.assertNotIn(value, text2)
        self.assertEqual(S.split_flags(["--settings={}", "-v", "--model", "m", "x=y"]),
                         ["--settings", "{}", "-v", "--model", "m", "x=y"])
        self.assertEqual(shown["env"], {"FIXTURE_API_KEY": "<redacted>", "FIXTURE_DIR": "<redacted>"})
        self.assertEqual(shown["enabledPlugins"], {"p@m": True})
        self.assertEqual(shown["statusLine"], {"command": "~/bin/status"})
        self.assertEqual(shown["apiKeyHelper"], "<redacted>")

    def test_a_delta_needs_the_shared_servers_connected_in_both_runs(self):
        # The co-op's local review of #1203 at 71b3fde3 (P2, :226-231): a shared server that failed in one run moved its
        # tokens into the component's delta.
        with mock.patch.dict(os.environ, {"FAKE_FAILED_IN": "extra:fixture"}):
            doc = S.measure(self.launch, self.tmp / "out", str(self.claude), HOME)
        row = doc["rows"][1]
        self.assertEqual((row["component_loaded"], row["over_control"]), (True, None))
        self.assertEqual(row["baseline_differs"], ["fixture"])
        # A plugin listed in both runs is shared, even when the component has its name.
        same = {"mcp_servers": [], "plugins": ["x", "y"]}
        self.assertEqual(S.baseline_differs({"component": "x"}, same, same), [])
        self.assertEqual(S.baseline_differs({"component": "x"}, {"mcp_servers": [], "plugins": ["x"]}, same), ["plugin y"])

    def test_a_plugin_mcp_server_is_measured_with_its_plugin(self):
        # The co-op's local review of #1203 at 71b3fde3 (P2, launches/CC.json:95-100): --strict-mcp-config suppressed the
        # plugin's own MCP server, so the plugin variant measured its hooks and skills only and still reported a delta.
        home = self.tmp / "home"
        root = home / ".claude" / "plugins" / "cache" / "m" / "p" / "1.0.0"
        (root / ".claude-plugin").mkdir(parents=True)
        (root / ".claude-plugin" / "plugin.json").write_text(json.dumps(
            {"name": "p", "mcpServers": {"extra": {"command": "node", "args": ["${CLAUDE_PLUGIN_ROOT}/start.mjs"]}}}))
        (home / ".claude" / "plugins" / "installed_plugins.json").write_text(json.dumps(
            {"version": 2, "plugins": {"p@m": [{"scope": "user", "installPath": str(root), "version": "1.0.0"}]}}))
        launch = dict(self.launch, variants=[self.launch["variants"][0],
                                             {"id": "+p", "component": "extra", "plugin": "p@m", "mcp_servers": ["fixture"],
                                              "settings": {"enabledPlugins": {"p@m": True}}}])
        with mock.patch.object(S.Path, "home", return_value=home):
            doc = S.measure(launch, self.tmp / "out", str(self.claude), str(home))
        config = [json.loads(line) for line in self.log.read_text().splitlines()][1]
        # The co-op's local review at 3a1f8618 (P2, :174-177): the plugin's server keeps its native name.
        self.assertIn("mcp-fixture-plugin_p_extra.json", [Path(flag).name for flag in config])
        receipt = json.loads((self.tmp / "out" / "fixture-role.+p.json").read_text())
        self.assertIn({"name": "plugin:p:extra", "status": "connected"}, receipt["mcp_servers"])
        row = doc["rows"][1]
        self.assertEqual((row["component_loaded"], row["over_control"]), (True, 600))
        with mock.patch.object(S.Path, "home", return_value=home), mock.patch.dict(os.environ, {"FAKE_FAILED": "plugin:p:extra"}):
            row = S.measure(launch, self.tmp / "out2", str(self.claude), str(home))["rows"][1]
        self.assertEqual((row["component_loaded"], row["over_control"]), (False, None))

    def test_plugin_servers_load_in_the_documented_order(self):
        # plugins-reference.md:301-317: .mcp.json first, then each declared shape in order; a later name replaces an
        # earlier one; a bundle is refused here.
        home = self.tmp / "home2"
        root = home / "plugin"
        (root / ".claude-plugin").mkdir(parents=True)
        (root / ".mcp.json").write_text(json.dumps({"mcpServers": {"a": {"command": "one"}, "b": {"command": "one"}}}))
        (root / "more.json").write_text(json.dumps({"mcpServers": {"b": {"command": "two"}}}))
        (root / ".claude-plugin" / "plugin.json").write_text(json.dumps(
            {"name": "q", "mcpServers": ["./more.json", {"c": {"command": "${CLAUDE_PLUGIN_ROOT}/c"}}]}))
        (home / ".claude" / "plugins").mkdir(parents=True)
        (home / ".claude" / "plugins" / "installed_plugins.json").write_text(json.dumps(
            {"version": 2, "plugins": {"q@m": [{"installPath": str(root)}]}}))
        with mock.patch.object(S.Path, "home", return_value=home):
            self.assertEqual(S.plugin_servers("q@m"), {"plugin:q:a": {"command": "one"}, "plugin:q:b": {"command": "two"},
                                                       "plugin:q:c": {"command": str(root) + "/c"}})
            (root / ".claude-plugin" / "plugin.json").write_text(json.dumps({"name": "q", "mcpServers": "./x.mcpb"}))
            with self.assertRaises(SystemExit):
                S.plugin_servers("q@m")

    def test_every_server_of_the_plugin_is_its_own_not_a_baseline_change(self):
        # The co-op's local review at 3a1f8618 (P2, :288-291): with a plugin of several servers, the ones other than the
        # component's counted as baseline changes, so no delta was ever given.
        variant = {"component": "a", "plugin": "q@m"}
        control = {"mcp_servers": [{"name": "fixture", "status": "connected"}], "plugins": ["x"]}
        receipt = {"mcp_servers": [{"name": "fixture", "status": "connected"}, {"name": "plugin:q:a", "status": "connected"},
                                   {"name": "plugin:q:b", "status": "connected"}, {"name": "plugin:q:c", "status": "connected"}],
                   "plugins": ["x", "q"]}
        self.assertEqual(S.baseline_differs(variant, receipt, control), [])
        self.assertTrue(S.loaded_component(variant, receipt))
        receipt["mcp_servers"][3]["status"] = "failed"
        self.assertFalse(S.loaded_component(variant, receipt))

    def test_plugin_metadata_comes_from_the_active_config_directory(self):
        # The co-op's local review at 3a1f8618 (P2, :144-145): the registry was read from ~/.claude even when
        # CLAUDE_CONFIG_DIR points the client elsewhere.
        active = self.tmp / "profile"
        root = self.tmp / "profile-plugin"
        (root / ".claude-plugin").mkdir(parents=True)
        (root / ".claude-plugin" / "plugin.json").write_text(json.dumps({"name": "r", "mcpServers": {"s": {"command": "x"}}}))
        (active / "plugins").mkdir(parents=True)
        (active / "plugins" / "installed_plugins.json").write_text(json.dumps(
            {"version": 2, "plugins": {"r@m": [{"installPath": str(root)}]}}))
        empty_home = self.tmp / "empty-home"
        empty_home.mkdir()
        with mock.patch.object(S.Path, "home", return_value=empty_home), \
                mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(active)}):
            self.assertEqual(S.plugin_servers("r@m"), {"plugin:r:s": {"command": "x"}})

    def test_the_committed_context_mode_variant_loads_its_plugin_server(self):
        launch = json.loads((ROOT / "tools" / "startup-context" / "launches" / "CC.json").read_text())
        variant = next(v for v in launch["variants"] if v["id"] == "+context-mode")
        self.assertEqual(variant["plugin"], "context-mode@context-mode")

    def test_a_server_outside_the_template_is_refused(self):
        launch = dict(self.launch, variants=[{"id": "control", "mcp_servers": ["unknown"]}])
        with self.assertRaises(SystemExit):
            S.measure(launch, self.tmp / "out", str(self.claude), HOME)


if __name__ == "__main__":
    unittest.main()
