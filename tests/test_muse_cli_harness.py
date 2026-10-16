"""Model-free native harness route controls, Muse subscription TRIAL only."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import tomllib
import unittest
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("muse_cli_harness", ROOT / "tools/adoption/muse_cli_harness.py")
fence = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fence)


class MuseCliHarnessTests(unittest.TestCase):
    def test_codex_completed_file_changes_count_successful_and_failed_patches(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'events.jsonl'
            # Codex0.162.1 exec/src/exec_events.rs:116-118,175-188:
            # file_change is emitted as item.completed for both outcomes.
            records = [
                {'type': 'item.completed', 'item': {'id': 'patch-ok', 'type': 'file_change',
                 'status': 'completed', 'changes': [{'path': 'fixture.txt', 'kind': 'add'}]}},
                {'type': 'item.completed', 'item': {'id': 'patch-failed', 'type': 'file_change',
                 'status': 'failed', 'changes': []}},
                {'type': 'turn.completed', 'usage': {}},
            ]
            path.write_text('\n'.join(json.dumps(record) for record in records) + '\n')
            facts = fence.event_facts(path, 'codex')
            self.assertEqual(facts['tool_attempt_counts'], {'file_change': 2})
            self.assertEqual(facts['tool_completed_counts'], {'file_change': 1})
            self.assertEqual(facts['tool_failure_counts'], {'file_change': 1})
            self.assertEqual(facts['unresolved_tool_attempt_count'], 0)
            self.assertEqual(facts['completed_terminal_count'], 1)

    @unittest.skipUnless(os.name == 'posix', 'native identity launcher requires a POSIX shell')
    def test_overlapping_codex_launches_get_distinct_native_writer_identities(self):
        with tempfile.TemporaryDirectory(dir='/var/tmp') as temp:
            base = Path(temp)
            root = base/'codex-muse'
            root.mkdir()
            marker = base/'rendezvous'
            marker.mkdir()
            meta = {'runtime': 'codex', 'executable': sys.executable, 'status': 'trial',
                    'model': fence.MODEL, 'version': 'fixture', 'sha256': 'fixture',
                    'memory_runtime': {'executable': '/fixture/memory'}}
            (root/'profile.json').write_text(json.dumps(meta))
            script = ('import json,os,sys,time; from pathlib import Path; '
                      'p=Path(sys.argv[1]); (p/str(os.getpid())).touch(); '
                      'deadline=time.monotonic()+5\n'
                      'while len(list(p.iterdir())) < 2 and time.monotonic() < deadline: time.sleep(.01)\n'
                      'assert len(list(p.iterdir())) == 2, "both writers must overlap"\n'
                      'print(json.dumps({"type":"thread.started",'
                      '"writer_attributes":os.environ.get("OTEL_RESOURCE_ATTRIBUTES", ""),'
                      '"arguments":sys.argv[2:]}))')
            argument = "space and ' quote"
            argv = [sys.executable, '-I', '-c', script, str(marker), argument]
            args = argparse.Namespace(profile='codex-muse', state_root=base, role='isolated-builder',
                                      print=True, prompt='synthetic', repository=base,
                                      timeout_seconds=10, resume=None)
            profiles = SimpleNamespace(owned_destination=lambda path: path,
                                       fresh_worktree=lambda *a: base,
                                       private_write=lambda path, content: path.write_text(content))
            with patch.object(fence, 'adoption_module', return_value=profiles), \
                 patch.object(fence, 'executable_identity', return_value=meta), \
                 patch.object(fence, 'memory_identity', return_value=meta['memory_runtime']), \
                 patch.object(fence, 'role_metadata', return_value=({}, '')), \
                 patch.object(fence, 'command', return_value=argv):
                with ThreadPoolExecutor(max_workers=2) as executor:
                    results = list(executor.map(lambda _: fence.launch(args), range(2)))
            self.assertEqual(results, [0, 0])
            identities = []
            for path in (root/'runs').glob('*/events.jsonl'):
                event = json.loads(path.read_text())
                attributes = [entry.partition('=') for entry in event['writer_attributes'].split(',')]
                writers = [value for key, _, value in attributes if key == 'service.instance.id']
                self.assertEqual(len(writers), 1, 'each direct native launch needs one writer identity')
                self.assertTrue(writers[0])
                self.assertNotEqual(writers[0], 'unscoped')
                identities.extend(writers)
                self.assertEqual(event['arguments'], [argument])
                self.assertIn('service.name=ns-codex-muse', event['writer_attributes'])
            self.assertEqual(len(set(identities)), 2)

    @unittest.skipUnless(sys.platform == 'linux', 'native process-group control requires Linux')
    def test_timeout_stops_sigterm_ignoring_child_after_leader_exits(self):
        with tempfile.TemporaryDirectory(dir='/var/tmp') as temp:
            base = Path(temp)
            root = base/'claude-muse'
            root.mkdir()
            ready = base/'child-ready.json'
            child = ('import json,os,signal,time; from pathlib import Path; '
                     'signal.signal(signal.SIGTERM, signal.SIG_IGN); '
                     f'Path({str(ready)!r}).write_text(json.dumps({{"pid":os.getpid()}})); '
                     'time.sleep(60)')
            leader = ('import subprocess,sys,time; from pathlib import Path; '
                      f'subprocess.Popen([sys.executable,"-I","-c",{child!r}]); '
                      'time.sleep(60)')
            meta = {'runtime': 'claude', 'executable': sys.executable, 'status': 'trial',
                    'model': fence.MODEL, 'version': 'fixture', 'sha256': 'fixture',
                    'memory_runtime': {'executable': '/fixture/memory'}}
            (root/'profile.json').write_text(json.dumps(meta))
            args = argparse.Namespace(profile='claude-muse', state_root=base,
                                      role='isolated-builder', print=True, prompt='synthetic',
                                      repository=base, timeout_seconds=1, resume=None)
            profiles = SimpleNamespace(owned_destination=lambda path: path,
                                       fresh_worktree=lambda *a: base,
                                       private_write=lambda path, content: path.write_text(content))
            started = []
            native_popen = subprocess.Popen
            def spawn(*pos, **kw):
                process = native_popen(*pos, **kw)
                started.append(process)
                # Start the timeout only after the child has installed its
                # TERM disposition, independent of scheduler startup latency.
                deadline = time.monotonic() + 5
                while not ready.is_file() and time.monotonic() < deadline:
                    time.sleep(.01)
                self.assertTrue(ready.is_file(), 'fixture child startup failed')
                return process
            try:
                with patch.object(fence, 'adoption_module', return_value=profiles), \
                     patch.object(fence, 'executable_identity', return_value=meta), \
                     patch.object(fence, 'memory_identity', return_value=meta['memory_runtime']), \
                     patch.object(fence, 'role_metadata', return_value=({}, '')), \
                     patch.object(fence, 'command', return_value=[sys.executable, '-I', '-c', leader]), \
                     patch.object(fence.subprocess, 'Popen', side_effect=spawn):
                    self.assertEqual(fence.launch(args), 124)
                self.assertTrue(ready.is_file(), 'fixture child must be ready before timeout')
                pid = json.loads(ready.read_text())['pid']
                status = Path('/proc')/str(pid)/'stat'
                # SIGKILL delivery can briefly leave the target runnable until
                # the kernel schedules its exit; it cannot resume user code.
                for _ in range(100):
                    try:
                        state = status.read_text().rsplit(')', 1)[1].split()[0]
                    except FileNotFoundError:
                        state = None
                    if state in (None, 'Z'):
                        break
                    time.sleep(.01)
                self.assertIn(state, (None, 'Z'), 'timeout receipt must not leave a live group child')
                receipt = json.loads(next((root/'runs').glob('*/receipt.json')).read_text())
                self.assertTrue(receipt['timed_out'])
            finally:
                for process in started:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    process.wait()

    def test_codex_context_store_paths_reach_mcp_and_role_override(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            package = base / 'eco/tools/context-mode-1.0.169/lib/node_modules/context-mode'
            package.mkdir(parents=True)
            (package / 'package.json').write_text(json.dumps({'version': '1.0.169'}))
            args = argparse.Namespace(state_root=base/'state', home=base/'source-home',
                                      eco_root=base/'eco', codex_bin=base/'codex')
            identity = {'executable': str(args.codex_bin), 'version': '0.162.1', 'sha256': 'fixture'}
            with patch.object(fence, 'executable_identity', return_value=identity), \
                 patch.object(fence, 'memory_identity', return_value={'executable': '/fixture/ai-memory'}), \
                 patch.object(fence, 'selected_skills', return_value=[]), \
                 patch.object(fence, 'register_codex_plugin'):
                meta = fence.prepare(args, 'codex-muse')
            root = args.state_root/'codex-muse'
            config = tomllib.loads((root/'home/.codex/config.toml').read_text())
            native = config['mcp_servers']['context-mode']['env']
            expected = {'CONTEXT_MODE_DIR': str(root/'context-state/context-mode'),
                        'CONTEXT_MODE_DATA_DIR': str(root/'context-state')}
            for key, value in expected.items():
                self.assertEqual(config['shell_environment_policy']['set'][key], value)
                self.assertEqual(native.get(key), value, 'MCP must share the hooks context store')
            invocation = argparse.Namespace(role='isolated-builder', prompt='fixture', print=True)
            argv = fence.command(meta, root, base/'workspace', invocation)
            override = next(arg for arg in argv if arg.startswith('mcp_servers.context-mode='))
            transport = tomllib.loads('server=' + override.split('=', 1)[1])['server']
            self.assertEqual({key: transport['env'].get(key) for key in expected}, expected)

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
