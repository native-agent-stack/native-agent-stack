"""Model-free native harness route controls, Muse subscription TRIAL only."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import tomllib
import unittest
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("muse_cli_harness", ROOT / "tools/adoption/muse_cli_harness.py")
fence = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fence)


class MuseCliHarnessTests(unittest.TestCase):
    def test_claude_retains_canonical_hooks_and_exact_subscription_model(self):
        baseline = {"hooks": {"PreToolUse": [{"hooks": [{"command": "guard"}]}]},
                    "permissions": {"deny": ["Read(.env)"]},
                    "env": {"CLAUDE_CODE_SUBAGENT_MODEL": "opus"},
                    "enabledPlugins": {"context-mode@context-mode": True}}
        data = fence.claude_settings(baseline)
        self.assertEqual(data["hooks"], baseline["hooks"])
        self.assertEqual(data["permissions"], baseline["permissions"])
        self.assertEqual(data["model"], fence.MODEL)
        self.assertEqual(data["effortLevel"], "max")
        self.assertEqual(data["env"]["CLAUDE_CODE_SUBAGENT_MODEL"], fence.MODEL)
        self.assertEqual(data["env"]["ANTHROPIC_DEFAULT_HAIKU_MODEL"], fence.MODEL)
        self.assertEqual(baseline["env"]["CLAUDE_CODE_SUBAGENT_MODEL"], "opus")

    def test_codex_retains_layers_and_selects_responses_subscription_route(self):
        baseline = {"features": {"hooks": True, "shell_snapshot": False},
                    "hooks": {"state": {"retained": {"trusted_hash": "sha256:fixture"}}},
                    "skills": {"max_context_tokens": 6000},
                    "mcp_servers": {"ai-memory": {"url": "http://127.0.0.1:29374/mcp"}},
                    "agents": {"default_subagent_model": "gpt-6-astra"}}
        data = fence.codex_settings(baseline)
        self.assertEqual(data["model"], fence.MODEL)
        self.assertEqual(data["model_reasoning_effort"], "max")
        self.assertEqual(data["agents"]["default_subagent_model"], fence.MODEL)
        self.assertEqual(data["hooks"], baseline["hooks"])
        self.assertEqual(data["skills"], baseline["skills"])
        self.assertEqual(data["mcp_servers"], baseline["mcp_servers"])
        provider = data["model_providers"]["omniroute-muse"]
        self.assertEqual(provider["wire_api"], "responses")
        self.assertEqual(provider["base_url"], "http://127.0.0.1:21128/v1")
        self.assertFalse(provider["requires_openai_auth"])
        self.assertFalse(data["features"]["daemon_auto_start"])
        self.assertFalse(data["features"]["shell_snapshot"])

    def test_codex_qualification_does_not_automatically_retry_provider_failures(self):
        provider = fence.codex_settings({})["model_providers"]["omniroute-muse"]
        self.assertEqual(provider.get("request_max_retries"), 0)
        self.assertEqual(provider.get("stream_max_retries"), 0)

    def test_child_environment_does_not_inherit_account_or_provider_secrets(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "do-not-copy", "OPENAI_API_KEY": "do-not-copy",
                                    "CLAUDE_CODE_OAUTH_TOKEN": "do-not-copy", "LD_PRELOAD": "do-not-copy"}):
            env = fence.child_environment(Path("/var/tmp/owned"), "claude-muse", Path("/var/tmp/work"))
        self.assertEqual(env["HOME"], "/var/tmp/owned/home")
        self.assertEqual(env["ANTHROPIC_AUTH_TOKEN"], "local")
        self.assertEqual(env["CLAUDE_CONFIG_DIR"], str(Path('/var/tmp/owned') / 'home' / '.claude'))
        self.assertEqual(env["CONTEXT_MODE_PROJECT_DIR"], "/var/tmp/work")
        for key in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN", "LD_PRELOAD"):
            self.assertNotIn(key, env)

    def test_native_commands_keep_layers_and_readonly_role(self):
        root = Path("/var/tmp/owned")
        args = argparse.Namespace(prompt="Inspect README", print=True, role="evidence-reviewer")
        meta = {"runtime": "claude", "executable": "/pin/claude", "context_mode": "/pin/context-mode"}
        command = fence.command(meta, root, Path("/var/tmp/work"), args)
        self.assertIn("--plugin-dir", command)
        self.assertIn("--strict-mcp-config", command)
        self.assertNotIn("--bare", command)
        self.assertNotIn("--dangerously-skip-permissions", command)
        self.assertEqual(command[command.index("--effort") + 1], "max")
        tools = command[command.index("--tools") + 1].split(",")
        self.assertNotIn("Bash", tools)
        self.assertNotIn("Edit", tools)
        meta["runtime"] = "codex"
        meta["executable"] = "/pin/codex"
        meta["mcp_server_configs"] = {}
        command = fence.command(meta, root, Path("/var/tmp/work"), args)
        self.assertIn("--json", command)
        self.assertEqual(command[command.index("--sandbox") + 1], "read-only")
        self.assertNotIn("--dangerously-bypass-approvals-and-sandbox", command)

    def test_unreported_model_remains_unverified(self):
        with tempfile.TemporaryDirectory() as temp:
            log = Path(temp) / "events.jsonl"
            log.write_text(json.dumps({"type": "thread.started", "thread_id": "fixture"}) + "\n")
            facts = fence.event_facts(log, "codex")
            self.assertEqual(facts["runtime_reported_models"], [])
            self.assertEqual(facts["model_identity_evidence"], "not-reported")
            self.assertEqual(facts["event_count"], 1)

    def test_gateway_reported_model_is_not_upstream_attestation(self):
        with tempfile.TemporaryDirectory() as temp:
            log = Path(temp) / "events.jsonl"
            log.write_text(json.dumps({"type": "assistant", "message": {"model": fence.MODEL}}) + "\n")
            facts = fence.event_facts(log, "claude")
            self.assertEqual(facts["runtime_reported_models"], [fence.MODEL])
            self.assertEqual(facts["model_identity_evidence"], "runtime-or-gateway-reported; upstream-unverified")

    def test_unknown_role_refuses_before_invocation(self):
        args = argparse.Namespace(prompt="task", print=True, role="unknown")
        with self.assertRaisesRegex(fence.HarnessError, "role"):
            fence.command({"runtime": "claude", "executable": "/pin/claude", "context_mode": "/pin/cm"},
                          Path("/var/tmp/owned"), Path("/var/tmp/work"), args)

    def test_codex_role_uses_exact_mcp_tools_and_disables_ungranted_servers(self):
        args = argparse.Namespace(prompt="Inspect README", print=True, role="evidence-reviewer")
        meta = {"runtime": "codex", "executable": "/pin/codex", "context_mode": "/pin/cm",
                "mcp_servers": ["ai-memory", "context-mode", "ungranted"],
                "mcp_server_configs": {"ai-memory": {"url": "http://127.0.0.1:29374/mcp"},
                                       "context-mode": {"command": "/pin/node", "args": ["/pin/cm/start.mjs"]},
                                       "ungranted": {"command": "/pin/ungranted"}}}
        command = fence.command(meta, Path("/var/tmp/owned"), Path("/var/tmp/work"), args)
        setting = next(part for part in command if part.startswith('mcp_servers.ai-memory='))
        native = tomllib.loads("server=" + setting.split("=", 1)[1])["server"]
        self.assertEqual(native["url"], "http://127.0.0.1:29374/mcp")
        self.assertTrue(native["enabled"])
        self.assertIn("memory_query", native["enabled_tools"])
        self.assertNotIn("memory_store", native["enabled_tools"])
        setting = next(part for part in command if part.startswith('mcp_servers.ungranted='))
        native = tomllib.loads("server=" + setting.split("=", 1)[1])["server"]
        self.assertEqual(native["command"], "/pin/ungranted")
        self.assertFalse(native["enabled"])
        self.assertIn('web_search="disabled"', command)

    def test_native_preparation_renders_parseable_canonical_layers_in_owned_home(self):
        for runtime in ("claude", "codex"):
            with self.subTest(runtime=runtime), tempfile.TemporaryDirectory() as temp:
                base = Path(temp)
                package = base / "eco/tools/context-mode-1.0.169/lib/node_modules/context-mode"
                package.mkdir(parents=True)
                (package / "package.json").write_text(json.dumps({"version": "1.0.169"}))
                args = argparse.Namespace(state_root=base / "state", home=base / "host-home",
                                          eco_root=base / "eco", claude_bin=base / "claude",
                                          codex_bin=base / "codex")
                identity = {"executable": str(base / runtime), "version": fence.VERSIONS[runtime],
                            "sha256": "fixture"}
                with patch.object(fence, "executable_identity", return_value=identity), \
                     patch.object(fence, "memory_identity", return_value={"executable": "/fixture/ai-memory", "version": "2.6.6", "sha256": "fixture"}, create=True), \
                     patch.object(fence, "selected_skills", return_value=[]), \
                     patch.object(fence, "register_codex_plugin") as register:
                    result = fence.prepare(args, runtime + "-muse")
                self.assertEqual(result["status"], "trial")
                root = args.state_root / (runtime + "-muse")
                if runtime == "codex":
                    data = tomllib.loads((root / "home/.codex/config.toml").read_text())
                    self.assertEqual(data["model"], fence.MODEL)
                    self.assertTrue(data["features"]["hooks"])
                    self.assertIn("context-mode", data["mcp_servers"])
                    register.assert_called_once()
                else:
                    data = json.loads((root / "home/.claude/settings.json").read_text())
                    self.assertIn("PreToolUse", data["hooks"])
                    self.assertTrue((root / "home/.claude/agents/isolated-builder.md").is_file())
                    self.assertIn("context-mode", json.loads((root / "mcp.json").read_text())["mcpServers"])
                    role = (root / "home/.claude/agents/isolated-builder.md").read_text()
                    self.assertIn("mcp__context-mode__ctx_execute", role)
                    self.assertNotIn("mcp__plugin_context-mode_context-mode__ctx_execute", role)
                    register.assert_not_called()

    def test_claude_grants_bind_exact_tools_to_explicit_context_mode_server(self):
        args = argparse.Namespace(prompt="bounded task", print=True, role="isolated-builder")
        meta = {"runtime": "claude", "executable": "/pin/claude", "context_mode": "/pin/cm"}
        command = fence.command(meta, Path("/var/tmp/owned"), Path("/var/tmp/work"), args)
        grants = command[command.index("--allowedTools") + 1].split(",")
        self.assertIn("mcp__context-mode__ctx_execute", grants)
        self.assertNotIn("mcp__plugin_context-mode_context-mode__ctx_execute", grants)
        self.assertNotIn("mcp__context-mode__ctx_purge", grants)
        self.assertNotIn("Skill", grants)

    def test_native_tool_counts_require_successful_results(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "events.jsonl"
            records = [
                {"type": "assistant", "message": {"content": [
                    {"type": "tool_use", "id": "read-1", "name": "Read", "input": {}},
                    {"type": "tool_use", "id": "ctx-1", "name": "mcp__context-mode__ctx_execute", "input": {}},
                    {"type": "tool_use", "id": "pending-1", "name": "Bash", "input": {}}]}},
                {"type": "user", "message": {"content": [
                    {"type": "tool_result", "tool_use_id": "read-1", "is_error": False},
                    {"type": "tool_result", "tool_use_id": "ctx-1", "is_error": True}]}},
                {"type": "result", "subtype": "error_during_execution", "is_error": True},
            ]
            path.write_text("\n".join(json.dumps(record) for record in records) + "\n")
            result = fence.event_facts(path, "claude")
            self.assertEqual(result["tool_attempt_counts"], {"Read": 1, "mcp__context-mode__ctx_execute": 1, "Bash": 1})
            self.assertEqual(result["tool_completed_counts"], {"Read": 1})
            self.assertEqual(result["tool_failure_counts"], {"mcp__context-mode__ctx_execute": 1})
            self.assertEqual(result["unresolved_tool_attempt_count"], 1)
            self.assertEqual(result["completed_terminal_count"], 0)
            self.assertEqual(result["error_terminal_count"], 1)

    def test_codex_started_completed_items_count_once_and_preserve_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "events.jsonl"
            records = [
                {"type": "item.started", "item": {"id": "check-1", "type": "command_execution", "status": "in_progress"}},
                {"type": "item.completed", "item": {"id": "check-1", "type": "command_execution", "status": "completed", "exit_code": 0}},
                {"type": "item.completed", "item": {"id": "ctx-1", "type": "mcp_tool_call", "tool": "ctx_execute", "status": "completed", "result": {"is_error": True}}},
                {"type": "turn.failed", "error": {"message": "synthetic failure"}},
            ]
            path.write_text("\n".join(json.dumps(record) for record in records) + "\n")
            result = fence.event_facts(path, "codex")
            self.assertEqual(result["tool_attempt_counts"], {"command_execution": 1, "ctx_execute": 1})
            self.assertEqual(result["tool_completed_counts"], {"command_execution": 1})
            self.assertEqual(result["tool_failure_counts"], {"ctx_execute": 1})
            self.assertEqual(result["unresolved_tool_attempt_count"], 0)
            self.assertEqual(result["error_terminal_count"], 1)

    def test_memory_hook_uses_explicit_committed_host_path_not_ecosystem_derived_path(self):
        with patch.object(Path, "home", return_value=Path("/fixture/host")):
            bundle = fence.layer_bundle(Path("/fixture/profile/home"), Path("/fixture/eco"), ROOT)
        data = json.loads(bundle["settings.json"])
        commands = [hook["command"] for group in data["hooks"].values()
                    for entry in group for hook in entry["hooks"] if "ai-memory" in hook.get("command", "")]
        self.assertTrue(commands)
        self.assertTrue(all(command.startswith("/fixture/host/.local/bin/ai-memory ") for command in commands))
        expected_data = str(Path('/fixture/profile') / 'home' / '.local/share/ai-memory')
        self.assertTrue(all('--data-dir ' + expected_data in command for command in commands))

    def test_failed_native_spawn_retains_sanitized_receipt(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root = base / "claude-muse"
            root.mkdir()
            meta = {"runtime": "claude", "executable": "/fixture/claude", "status": "trial",
                    "model": fence.MODEL, "version": "2.1.301", "sha256": "fixture",
                    "memory_runtime": {"executable": "/fixture/memory", "version": "2.6.6", "sha256": "fixture"}}
            (root / "profile.json").write_text(json.dumps(meta))
            args = argparse.Namespace(profile="claude-muse", state_root=base, role="isolated-builder",
                                      print=True, prompt="synthetic task", repository=base,
                                      timeout_seconds=1, resume=None)
            profiles = SimpleNamespace(owned_destination=lambda path: path,
                                       fresh_worktree=lambda *a: base)
            with patch.object(fence, "adoption_module", return_value=profiles), \
                 patch.object(fence, "executable_identity", return_value=meta), \
                 patch.object(fence, "memory_identity", return_value=meta["memory_runtime"]), \
                 patch.object(fence, "role_metadata", return_value=({}, "")), \
                 patch.object(fence, "command", return_value=["fixture"]), \
                 patch.object(fence, "private_write", side_effect=lambda p,t: p.write_text(t)), \
                 patch.object(fence.subprocess, "Popen", side_effect=FileNotFoundError("do-not-copy-detail")):
                self.assertEqual(fence.launch(args), 127)
            receipt_path = next((root / "runs").glob("*/receipt.json"))
            receipt = json.loads(receipt_path.read_text())
            self.assertEqual(receipt["launch_error"], "FileNotFoundError")
            self.assertEqual(receipt["event_count"], 0)
            self.assertNotIn("do-not-copy-detail", receipt_path.read_text())


if __name__ == "__main__":
    unittest.main()
