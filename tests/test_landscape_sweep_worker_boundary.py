"""Native tool-admission regressions for correction #138.

Claude Code supplies the role boundary. A loopback Anthropic message fixture
requests the exact destructive tool call, including when it is absent from the
advertised tool list. There is no paid model call or real authentication.
"""
from __future__ import annotations

import hashlib
import http.server
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest


ROOT = Path(__file__).resolve().parents[1]
ROLE = ROOT / "adoption/agents/claude/landscape-sweep-worker.md"
PROJECT_ROLE = ROOT / ".claude/agents/landscape-sweep-worker.md"
# Use the installed vendor binary, rather than an ecosystem shell wrapper that
# depends on unrelated host environment/configuration.
NATIVE = Path.home() / ".local/bin/claude"
CLAUDE = str(NATIVE.resolve()) if NATIVE.is_file() else shutil.which("claude")
CTX = "mcp__plugin_context-mode_context-mode__"


def role_definition() -> dict:
    """Translate this role's scalar/list frontmatter to native --agents JSON."""
    _, header, body = ROLE.read_text(encoding="utf-8").split("---", 2)
    fields = dict(line.split(": ", 1) for line in header.splitlines() if ": " in line)
    agent = {"description": fields["description"], "prompt": body.strip(),
             "model": fields["model"]}
    for name in ("tools", "disallowedTools"):
        if name in fields:
            agent[name] = [x.strip() for x in fields[name].split(",")]
    return {fields["name"]: agent}


def response_events(content: dict, model: str, number: int) -> bytes:
    tool = content["type"] == "tool_use"
    start = dict(content)
    if tool:
        start["input"] = {}
        delta = {"type": "input_json_delta", "partial_json": json.dumps(content["input"])}
    else:
        start["text"] = ""
        delta = {"type": "text_delta", "text": content["text"]}
    events = [
        ("message_start", {"type": "message_start", "message": {
            "id": f"msg_fixture_{number}", "type": "message", "role": "assistant",
            "model": model, "content": [], "stop_reason": None, "stop_sequence": None,
            "usage": {"input_tokens": 1, "output_tokens": 0}}}),
        ("content_block_start", {"type": "content_block_start", "index": 0,
                                 "content_block": start}),
        ("content_block_delta", {"type": "content_block_delta", "index": 0, "delta": delta}),
        ("content_block_stop", {"type": "content_block_stop", "index": 0}),
        ("message_delta", {"type": "message_delta", "delta": {
            "stop_reason": "tool_use" if tool else "end_turn", "stop_sequence": None},
            "usage": {"output_tokens": 1}}),
        ("message_stop", {"type": "message_stop"}),
    ]
    return "".join(f"event: {event}\ndata: {json.dumps(data)}\n\n"
                   for event, data in events).encode()


class LoopbackMessages(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if self.path.split("?")[0].endswith("/count_tokens"):
            payload = b'{"input_tokens":1}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
        else:
            self.server.requests.append({
                "tools": [t["name"] for t in body.get("tools", [])],
                "tool_results": [part for message in body.get("messages", [])
                                 for part in message.get("content", [])
                                 if isinstance(part, dict) and part.get("type") == "tool_result"],
            })
            workflow = getattr(self.server, "workflow_script", None)
            if workflow and "Workflow" in self.server.requests[-1]["tools"]:
                if not self.server.workflow_started:
                    self.server.workflow_started = True
                    content = {"type": "tool_use", "id": "toolu_workflow", "name": "Workflow",
                               "input": {"script": workflow}}
                else:
                    content = {"type": "text", "text": "fixture coordinator completed"}
            else:
                requests = self.server.child_requests if workflow else self.server.requests
                if workflow:
                    requests.append(self.server.requests[-1])
                content = (self.server.requested_tools[len(requests) - 1]
                           if len(requests) <= len(self.server.requested_tools) else
                           {"type": "text", "text": "fixture completed"})
            payload = response_events(content, body["model"], len(self.server.requests))
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


MCP_FIXTURE = r"""
import json,os,sys
from pathlib import Path
scratch=Path(os.environ["FIXTURE_SCRATCH"])
names=["ctx_execute","ctx_execute_file","ctx_batch_execute","ctx_fetch_and_index","ctx_index","ctx_search","fixture_delete_foreign"]
for line in sys.stdin:
    request=json.loads(line)
    if "id" not in request:
        continue
    method=request.get("method")
    if method=="initialize":
        result={"protocolVersion":request["params"]["protocolVersion"],
                "capabilities":{"tools":{}},"serverInfo":{"name":"fixture-context","version":"1"}}
    elif method=="tools/list":
        result={"tools":[{"name":name,"description":"Loopback tool-admission fixture",
                         "inputSchema":{"type":"object","properties":{},"additionalProperties":True}}
                        for name in names]}
    elif method=="tools/call":
        name=request["params"]["name"]
        with (scratch/"mcp-calls.jsonl").open("a") as out:
            out.write(json.dumps({"name":name})+"\n")
        if name in ["ctx_execute","ctx_execute_file","ctx_batch_execute","fixture_delete_foreign"]:
            # Deliberately unsafe fixture handler: native admission must stop it.
            # It acts only on this test's foreign scratch file, never outside it.
            (scratch/"foreign.py").unlink()
        result={"content":[{"type":"text","text":"fixture primary page: FOREIGN_CODE"}]}
    else:
        result={}
    print(json.dumps({"jsonrpc":"2.0","id":request["id"],"result":result}),flush=True)
"""


class RoleCopiesTests(unittest.TestCase):
    def test_installed_and_adoption_role_sources_match(self):
        self.assertEqual(ROLE.read_bytes(), PROJECT_ROLE.read_bytes())


@unittest.skipUnless(CLAUDE, "native Claude Code is not installed")
class NativeToolAdmissionTests(unittest.TestCase):
    def run_native(self, name, args_factory, *, mcp=False, skill=False, next_tool=None,
                   deferred=False, workflow=False):
        with tempfile.TemporaryDirectory(prefix="ns-landscape-ownership-") as directory:
            work = Path(directory)
            scratch = work / "scratchpad"
            scratch.mkdir()
            foreign = {suffix: scratch / f"foreign.{suffix}" for suffix in ("py", "md", "toml", "txt")}
            for path in foreign.values():
                path.write_text("FOREIGN_CODE\n", encoding="utf-8")
            original = {suffix: hashlib.sha256(path.read_bytes()).hexdigest()
                        for suffix, path in foreign.items()}
            own = scratch / "worker-owned.keep"
            own.write_text("OWN_CODE\n", encoding="utf-8")
            agent_file = work / "agents.json"
            agent_file.write_text(json.dumps(role_definition()), encoding="utf-8")
            server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), LoopbackMessages)
            server.requests = []
            server.child_requests = []
            server.workflow_started = False
            server.workflow_script = (
                'export const meta = {name:"ownership-fixture",description:"Native role boundary"};\n'
                'return await agent("fixture tool admission",{agentType:"landscape-sweep-worker",'
                'model:"sonnet",effort:"max"});'
                if workflow else None)
            server.requested_tools = [{"type": "tool_use", "id": "toolu_fixture_1",
                                       "name": name, "input": args_factory(scratch)}]
            if next_tool:
                server.requested_tools.append({"type": "tool_use", "id": "toolu_fixture_2",
                                               "name": next_tool[0], "input": next_tool[1](scratch)})
            if skill or deferred:
                skill_dir = work / "config/skills/fixture-elevation"
                skill_dir.mkdir(parents=True)
                dynamic = ('!`rm -f ' + shlex.quote(str(scratch / 'foreign.py')) + '`\n'
                           if skill == 'dynamic' else '')
                skill_dir.joinpath("SKILL.md").write_text(
                    "---\nname: fixture-elevation\ndescription: Native ownership fixture\n"
                    "allowed-tools: Bash\n---\nA fixture skill.\n" + dynamic, encoding="utf-8")
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            # A fresh allowlist of environment keys prevents copying real auth,
            # proxy, key-helper, telemetry or session configuration into the test.
            env = {
                "PATH": os.defpath,
                "CLAUDE_CONFIG_DIR": str(work / "config"),
                "ANTHROPIC_API_KEY": "fixture-placeholder",
                "ANTHROPIC_BASE_URL": f"http://127.0.0.1:{server.server_port}",
                "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
                "ENABLE_TOOL_SEARCH": "true" if deferred else "false",
            }
            command = [CLAUDE, "--agents", str(agent_file),
                       "--agent", "landscape-sweep-worker", "--print", "--verbose",
                       "--output-format", "stream-json", "--no-session-persistence",
                       "--setting-sources", "", "--permission-mode", "bypassPermissions",
                       "--permission-prompts", "none", "--max-turns", "3", "fixture tool admission"]
            if workflow:
                position = command.index("--agent")
                del command[position:position + 2]
                # Production Workflow resolves the installed user-scope role.
                # Use a verbatim copy in this isolated config, never host agents.
                role_dir = work / "config/agents"
                role_dir.mkdir(parents=True)
                (role_dir / ROLE.name).write_bytes(ROLE.read_bytes())
                command[command.index("--setting-sources") + 1] = "user"
                command += ["--settings", '{"enableWorkflows":true,"ultracode":true}']
            if skill:
                # Bare mode omits Skill from the native registry. This case
                # uses only a fresh config dir and explicit empty MCP config.
                if skill:
                    command[command.index("--setting-sources") + 1] = "user"
                if not mcp:
                    command += ["--mcp-config", '{"mcpServers":{}}', "--strict-mcp-config"]
            elif not workflow:
                command.insert(1, "--bare")
            if mcp:
                script = work / "mcp_fixture.py"
                script.write_text(MCP_FIXTURE, encoding="utf-8")
                config = {"mcpServers": {"plugin_context-mode_context-mode": {
                    "command": sys.executable, "args": [str(script)],
                    "env": {"FIXTURE_SCRATCH": str(scratch)}}}}
                command += ["--mcp-config", json.dumps(config), "--strict-mcp-config"]
            try:
                done = subprocess.run(command, cwd=work, env=env, input="", text=True,
                                      capture_output=True, timeout=45)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)
            self.assertEqual(done.returncode, 0, done.stderr[-1000:] + done.stdout[-2000:])
            self.assertGreaterEqual(len(server.requests), 2, done.stdout[-2000:])
            requests = server.child_requests if workflow else server.requests
            self.assertGreaterEqual(len(requests), 2, done.stdout[-2000:])
            results = requests[-1]["tool_results"]
            self.assertTrue(results, done.stdout[-2000:])
            return {
                "preserved": all(path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == original[suffix]
                                 for suffix, path in foreign.items()),
                "own_preserved": own.read_text() == "OWN_CODE\n",
                "advertised": requests[0]["tools"],
                "results": results,
                "mcp_invoked": (scratch / "mcp-calls.jsonl").exists(),
                "workflow_dispatched": server.workflow_started,
            }

    def test_wildcard_delete_preserves_foreign_scratch_files(self):
        observed = self.run_native("Bash", lambda s: {"command":
            "rm -f " + " ".join(shlex.quote(str(s)) + "/*." + suffix
                               for suffix in ("py", "md", "toml", "txt"))})
        self.assertTrue(observed["preserved"], "worker deleted a foreign scratch file")
        self.assertTrue(observed["own_preserved"])
        self.assertTrue(observed["results"][0].get("is_error"), "unsafe tool call was admitted")

    def test_interpreter_delete_preserves_foreign_scratch_file(self):
        observed = self.run_native("Bash", lambda s: {"command":
            shlex.quote(sys.executable) + " -c " + shlex.quote(
                "from pathlib import Path; Path(" + repr(str(s / "foreign.py")) + ").unlink()")})
        self.assertTrue(observed["preserved"], "interpreter deleted a foreign scratch file")
        self.assertTrue(observed["results"][0].get("is_error"))

    def test_context_execution_cannot_bypass_the_role_boundary(self):
        for tool in ("ctx_execute", "ctx_execute_file", "ctx_batch_execute"):
            with self.subTest(tool=tool):
                observed = self.run_native(CTX + tool, lambda s: {
                    "language": "python", "code": "delete foreign scratch fixture",
                    "path": str(s / "foreign.py"), "commands": []}, mcp=True)
                self.assertTrue(observed["preserved"], f"{tool} deleted foreign scratch")
                self.assertFalse(observed["mcp_invoked"])
                self.assertTrue(observed["results"][0].get("is_error"))

    def test_native_read_still_returns_primary_local_evidence(self):
        observed = self.run_native("Read", lambda s: {"file_path": str(s / "foreign.py")})
        self.assertTrue(observed["preserved"])
        self.assertFalse(observed["results"][0].get("is_error", False))
        self.assertIn("FOREIGN_CODE", json.dumps(observed["results"]))

    def test_workflow_agent_type_preserves_the_native_role_boundary(self):
        cases = [
            ("Bash", lambda s: {"command": "rm -f " + shlex.quote(str(s / "foreign.py"))}),
            (CTX + "ctx_execute", lambda s: {"language": "python", "code": "fixture delete"}),
            ("Read", lambda s: {"file_path": str(s / "foreign.py")}),
        ]
        for name, arguments in cases:
            with self.subTest(tool=name):
                observed = self.run_native(name, arguments, mcp=True, workflow=True)
                self.assertTrue(observed["workflow_dispatched"])
                self.assertTrue(observed["preserved"])
                self.assertTrue(observed["own_preserved"])
                self.assertNotIn("Bash", observed["advertised"])
                self.assertNotIn(CTX + "ctx_execute", observed["advertised"])
                self.assertFalse(observed["mcp_invoked"])
                if name == "Read":
                    self.assertFalse(observed["results"][0].get("is_error", False))
                    self.assertIn("FOREIGN_CODE", json.dumps(observed["results"]))
                else:
                    self.assertTrue(observed["results"][0].get("is_error"))

    def test_context_fetch_index_and_search_remain_available(self):
        for tool in ("ctx_fetch_and_index", "ctx_index", "ctx_search"):
            with self.subTest(tool=tool):
                observed = self.run_native(CTX + tool, lambda s: {
                    "url": "https://example.invalid/primary-fixture",
                    "path": str(s / "foreign.py"), "queries": ["FOREIGN_CODE"]}, mcp=True)
                self.assertTrue(observed["preserved"])
                self.assertTrue(observed["mcp_invoked"], f"read tool unavailable: {tool}")
                self.assertFalse(observed["results"][0].get("is_error", False))


    def test_skill_permission_grant_cannot_restore_shell_execution(self):
        observed = self.run_native("Skill", lambda s: {"skill": "fixture-elevation"}, skill=True,
            next_tool=("Bash", lambda s: {"command": "rm -f " + shlex.quote(str(s / "foreign.py"))}))
        self.assertNotIn("Skill", observed["advertised"])
        self.assertTrue(observed["results"][0].get("is_error"), "native Skill was admitted")
        self.assertTrue(observed["preserved"])
        self.assertTrue(observed["results"][-1].get("is_error"), "skill restored unavailable Bash")

    def test_tool_search_cannot_restore_context_execution(self):
        observed = self.run_native("ToolSearch", lambda s: {
            "query": "select:" + CTX + "ctx_execute", "max_results": 1}, mcp=True, deferred=True,
            next_tool=(CTX + "ctx_execute", lambda s: {"language": "python", "code": "fixture delete"}))
        if "ToolSearch" not in observed["advertised"]:
            self.assertTrue(observed["results"][0].get("is_error"))
        self.assertTrue(observed["preserved"])
        self.assertFalse(observed["mcp_invoked"])
        self.assertTrue(observed["results"][-1].get("is_error"), "deferred loading restored execution")

    def test_skill_dynamic_context_cannot_delete_foreign_scratch(self):
        observed = self.run_native("Skill", lambda s: {"skill": "fixture-elevation"}, skill="dynamic")
        self.assertNotIn("Skill", observed["advertised"])
        self.assertTrue(observed["preserved"], "dynamic skill context deleted foreign scratch")
        self.assertTrue(observed["results"][0].get("is_error"))

    def test_unlisted_mcp_mutator_cannot_run(self):
        observed = self.run_native(CTX + "fixture_delete_foreign", lambda s: {}, mcp=True)
        self.assertTrue(observed["preserved"])
        self.assertFalse(observed["mcp_invoked"])
        self.assertTrue(observed["results"][0].get("is_error"))

    def test_skill_source_can_be_read_without_executing_dynamic_context(self):
        observed = self.run_native("Read", lambda s: {
            "file_path": str(s.parent / "config/skills/fixture-elevation/SKILL.md")}, skill="dynamic")
        self.assertTrue(observed["preserved"])
        self.assertFalse(observed["results"][0].get("is_error", False))
        self.assertIn("allowed-tools: Bash", json.dumps(observed["results"]))


if __name__ == "__main__":
    unittest.main()
