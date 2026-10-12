"""Native runtime profiles: live-port binding and generated tool fences.

The source of the endpoint is the repository's new-WSL client-config record;
the CC's 2026-10-12 measurement corroborates that record, without a network test.
"""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib
import unittest
import importlib.util
import argparse
from unittest import mock
import io
from contextlib import redirect_stdout

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/adoption"))
import runtime_profiles as profiles
import runtime_acceptance as acceptance


class GatewayPortBindingTests(unittest.TestCase):
    def test_omniroute_template_matches_new_wsl_gateway_record(self):
        source = ROOT / "adoption/new-wsl/client-config-map.json"
        records = json.loads(source.read_text())["entries"]
        records = [row for row in records if row.get("owner") == "OmniRoute"
                   and "gateway listens on 21128" in row.get("source", "")]
        self.assertEqual(len(records), 1, "the recorded live gateway must have one source")
        rendered = tomllib.loads((ROOT / "adoption/templates/codex.omniroute.config.toml").read_text())
        self.assertEqual(rendered["model_providers"]["omniroute"]["base_url"],
                         "http://127.0.0.1:21128/v1")


class RuntimeInvokeTrackerTests(unittest.TestCase):
    def test_pi_completed_skill_and_mcp_calls_reach_existing_tracker(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "pi.jsonl"
            records = [
                {"type": "session", "id": "fixture-pi-session"},
                {"type": "tool_execution_start", "toolCallId": "call-1", "toolName": "read",
                 "args": {"path": "/fixture/.agents/skills/codebase-design/SKILL.md"}},
                {"type": "tool_execution_end", "toolCallId": "call-1", "toolName": "read",
                 "isError": False},
                {"type": "tool_execution_start", "toolCallId": "call-2",
                 "toolName": "mcp__headroom__get_stats", "args": {}},
                {"type": "tool_execution_end", "toolCallId": "call-2",
                 "toolName": "mcp__headroom__get_stats", "isError": False},
            ]
            log.write_text("\n".join(json.dumps(row) for row in records) + "\n")
            result = subprocess.run(
                [sys.executable, "-B", str(ROOT / "tools/skill-usage/skill_usage.py"),
                 "--runtime-log", "pi", str(log), "--json"],
                cwd=ROOT, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            measured = json.loads(result.stdout)["runtimes"]["pi"]
            self.assertEqual(measured["sessions_measured"], 1)
            self.assertEqual(measured["successful_skill_uses"], {"codebase-design": 1})
            self.assertEqual(measured["successful_mcp_calls"], {"headroom": 1})
            self.assertNotIn("/fixture/", result.stdout)


class NativeProfileGenerationTests(unittest.TestCase):
    def test_valid_native_json_strings_with_unicode_line_separators_keep_usage(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "events.jsonl"
            event = {"type": "message_end", "message": {"role": "assistant",
                     "content": [{"type": "text", "text": "first\u2028second\u2029third"}],
                     "usage": {"input": 5, "output": 2, "totalTokens": 7, "cost": {"total": 0.01}}}}
            log.write_text(json.dumps(event, ensure_ascii=False) + "\n")
            measured = profiles.inference_facts(log, "pi")
            self.assertEqual(measured["completed_native_steps"], 1)
            self.assertEqual(measured["usage"]["total_tokens"], 7)
            self.assertEqual(measured["native_cost_usd"], 0.01)

    def test_pi_mcp_exit_zero_does_not_accept_absent_or_disabled_mandatory_server(self):
        for servers in [[], [{"name": "context-mode", "state": "disabled", "tools": []}]]:
            with self.subTest(servers=servers), tempfile.TemporaryDirectory() as directory:
                state = Path(directory)
                root = state / "pi-gpt"
                root.mkdir()
                (root / "profile.json").write_text(json.dumps({"pi_bin": "/fixture/pi",
                    "mcp_server_names": ["context-mode"]}))
                args = argparse.Namespace(state_root=state, workspace=state, out=state / "receipts",
                                          role_scope=None, tokenizer_python=Path(sys.executable))

                def native(command, **kwargs):
                    if "mcp" in command:
                        return 0, json.dumps({"servers": servers})
                    return 0, "{}"

                with mock.patch.object(acceptance, "native", side_effect=native), \
                        mock.patch.object(acceptance, "discovered", return_value=[]), \
                        mock.patch.object(acceptance, "skill_integrity", return_value={"managed_pass": True}), \
                        redirect_stdout(io.StringIO()):
                    self.assertFalse(acceptance.check(args, "pi-gpt"))
                receipt = json.loads((args.out / "pi-gpt.discovery.json").read_text())
                self.assertFalse(receipt["mcp"]["all_connected"])

    def test_interactive_claude_opencode_collector_uses_profile_xdg_after_loader(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            role = state / "opencode-claude/roles/builder"
            role.mkdir(parents=True)
            (role / "profile.json").write_text(json.dumps({
                "status": "trial", "model": "fixture", "effort": "xhigh",
                "opencode_bin": "/fixture/opencode", "roles": {"isolated-builder": {"tools": []}},
            }))
            expected = {"XDG_STATE_HOME": str(role / "state"), "XDG_DATA_HOME": str(role / "data"),
                        "OPENCODE_CONFIG_DIR": str(role / "config")}
            observed = []

            def run(command, **kwargs):
                if command[0] == "/fixture/opencode":
                    observed.append(kwargs["env"])
                    kwargs["stdout"].write("[]")
                return subprocess.CompletedProcess(command, 0)

            args = argparse.Namespace(profile="opencode-claude", state_root=state, repository=state,
                                      role="isolated-builder", print=False, prompt=None)
            with mock.patch.object(profiles, "fresh_worktree", return_value=state), \
                    mock.patch.object(profiles, "choose_slot", return_value="anthropic-api-4"), \
                    mock.patch.object(profiles, "profile_environment", return_value=expected), \
                    mock.patch.object(profiles.subprocess, "run", side_effect=run), redirect_stdout(io.StringIO()):
                self.assertEqual(profiles.launch(args), 0)
            self.assertEqual(len(observed), 1)
            for name, value in expected.items():
                self.assertEqual(observed[0].get(name), value, name)

    def test_vendor_skill_helper_does_not_broaden_imported_role_tool_fence(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            servers = {"context-mode": {"type": "stdio", "command": "/fixture/mcp"}}
            with mock.patch.object(profiles, "canonical_servers", return_value=servers), \
                    mock.patch.object(profiles.shutil, "which", return_value="/fixture/rtk"), \
                    mock.patch.object(profiles.subprocess, "check_output", side_effect=[
                        "rtk 0.51.0\n", "e001f773f80b22b7dc4c7a79521b30e35aaef026\n"]), \
                    mock.patch.object(profiles.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)):
                profiles.render("opencode-gpt", state=state, home=state, eco_root=state, templates=[],
                                pi_bin=state / "pi", opencode_bin=state / "opencode", rtk_source=state,
                                role_scope="auditor")
            config = json.loads((state / "opencode-gpt/roles/auditor/config/opencode/opencode.json").read_text())
            for name in profiles.ROLES:
                self.assertNotIn("skill", config["agent"][name]["permission"], name)

    def test_native_mcp_failed_or_absent_status_is_not_connected_despite_exit_zero(self):
        output = "│ ✓ serena connected\n│ ✗ socraticode failed\n"
        states = acceptance.opencode_statuses(output, ["serena", "socraticode", "context-mode"])
        self.assertEqual(states, {"serena": "connected", "socraticode": "failed", "context-mode": "unverified"})

    def test_mcp_conversion_preserves_transport_environment_and_arguments(self):
        servers = {
            "stdio-fixture": {"type": "stdio", "command": "/tool with spaces", "args": ["--one", "two words"],
                              "env": {"PUBLIC_OPTION": "value"}},
            "remote-fixture": {"type": "http", "url": "http://127.0.0.1:19999/mcp"},
        }
        converted = profiles.opencode_mcp(servers)
        self.assertEqual(converted["stdio-fixture"]["command"], ["/tool with spaces", "--one", "two words"])
        self.assertEqual(converted["stdio-fixture"]["environment"], {"PUBLIC_OPTION": "value"})
        self.assertEqual(converted["remote-fixture"]["type"], "remote")
        self.assertFalse(converted["remote-fixture"]["oauth"])

    def test_roles_cannot_gain_shell_write_or_mcp_wildcards(self):
        metadata, _ = profiles.role_source("evidence-reviewer")
        for runtime in ["pi", "opencode"]:
            tools, omitted = profiles.granted_tools(metadata, runtime)
            self.assertNotIn("bash", tools)
            self.assertNotIn("edit", tools)
            self.assertNotIn("write", tools)
            self.assertNotIn("mcp__*", tools)
            self.assertNotIn("*", tools)
            self.assertTrue(any("serena" in tool for tool in tools))
        metadata, _ = profiles.role_source("source-scout")
        tools, _ = profiles.granted_tools(metadata, "pi")
        self.assertEqual(tools, ["bash", "find", "grep", "read"])

    def test_native_tool_identity_preserves_vendor_hyphens_and_role_patterns(self):
        metadata = {"tools": "mcp__ai-memory__memory_query, mcp__serena__find_*"}
        tools, _ = profiles.granted_tools(metadata, "opencode")
        self.assertEqual(tools, ["ai-memory_memory_query", "serena_find_*"])
        tools, _ = profiles.granted_tools(metadata, "pi")
        self.assertEqual(tools, ["mcp__ai_memory__memory_query", "mcp__serena__find_*"])

    def test_profile_destinations_refuse_symlink_and_protected_roots(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "link").symlink_to(root / "target", target_is_directory=True)
            with self.assertRaises(profiles.ProfileError):
                profiles.owned_destination(root / "link/nested")
        with self.assertRaises(profiles.ProfileError):
            profiles.owned_destination(Path.home() / ".codex/never")

    def test_ns_run_accepts_named_launcher_profile(self):
        args = profiles.parser().parse_args(["run", "--state-root", "/fixture",
                                            "--repository", "/fixture", "ns-pi-gpt", "builder", "brief.md"])
        self.assertEqual(args.profile, "pi-gpt")

    def test_xdg_profile_path_reaches_selected_python_without_host_shim_config(self):
        with tempfile.TemporaryDirectory() as directory:
            env = profiles.profile_environment("opencode-gpt", Path(directory))
            expected = str(Path(sys.executable).resolve().parent)
            self.assertEqual(env["PATH"].split(os.pathsep)[0], expected)
            self.assertTrue(env["XDG_STATE_HOME"].startswith(directory))
            self.assertEqual(env["OTEL_EXPORTER_OTLP_ENDPOINT"], "http://127.0.0.1:21318")

    def test_existing_profile_is_preserved_and_token_layer_is_required(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            destination = state / "pi-gpt"
            destination.mkdir()
            (destination / "owner-file").write_text("keep")
            with self.assertRaises(profiles.ProfileError):
                profiles.render("pi-gpt", state=state, home=state, eco_root=state, templates=[],
                                pi_bin=state / "pi", opencode_bin=state / "opencode", rtk_source=state)
            self.assertEqual((destination / "owner-file").read_text(), "keep")
            with self.assertRaises(profiles.ProfileError):
                profiles.canonical_servers(state, state, [])

    def test_secret_is_environment_reference_not_stored_value(self):
        provider = profiles.opencode_provider("claude")
        self.assertEqual(provider["anthropic"]["options"]["apiKey"], "{env:ANTHROPIC_API_KEY}")
        self.assertNotIn("apiKey", json.dumps(profiles.pi_models("claude")))

    def test_windows_fragments_are_new_profiles_not_updates(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            args = argparse.Namespace(home=root, state_root=root / "state", repository=ROOT,
                                      fragment=root / "Fragments/native-stack/runtimes.json")
            profiles.install_launchers(args)
            fragment = json.loads(args.fragment.read_text())
            self.assertEqual(len(fragment["profiles"]), 4)
            self.assertTrue(all("updates" not in item for item in fragment["profiles"]))
            self.assertTrue(all("wsl.exe" in item["commandline"] for item in fragment["profiles"]))
            self.assertFalse((root / "settings.json").exists())


if __name__ == "__main__":
    unittest.main()
