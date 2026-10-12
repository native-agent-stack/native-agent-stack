"""Hermetic installed OpenCode53d1eabb directory/instruction/read contract.

No credential, provider or network leaves the namespace. A local fixture
endpoint captures one request and rejects it; no inference or W6 arm runs.
The runtime's real CLI/tools/permissions run; optional plugins and MCP services
are omitted from this focused fixture. All scratch is under /var/tmp.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from contextlib import redirect_stdout
import io

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/adoption"))
import runtime_profiles as profiles

CAPTURE = r'''
import json, subprocess, sys, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
request = {}
class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        request.update(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
        self.send_response(400); self.end_headers(); self.wfile.write(b'{"error":{"message":"fixture rejection"}}')
    def log_message(self, *args): pass
server = HTTPServer(('127.0.0.1', 21128), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
result = subprocess.run(sys.argv[2:], stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=25)
text = json.dumps(request)
created = __import__('re').findall(r'created .*?directory=([^\s]+)', result.stderr)
summary = {'exit_code':result.returncode, 'request_captured':bool(request),
    'owned_instruction':'OWNED_AGENTS_MARKER' in text, 'primary_instruction':'PRIMARY_AGENTS_MARKER' in text,
    'working_directory_owned':('Working directory: '+sys.argv[1]) in text,
    'session_directory_owned':bool(created) and all(p==sys.argv[1] for p in created)}
print(json.dumps(summary))
server.shutdown()
'''


class NativeOpenCodeContractTests(unittest.TestCase):
    def test_real_session_prompt_and_reads_use_fresh_worktree(self):
        binary = os.environ.get("NS_OPENCODE_TEST_BIN")
        bwrap = shutil.which("bwrap")
        if not binary or not bwrap:
            self.skipTest("explicit installed OpenCode binary and bubblewrap required")
        module = profiles
        baseline = os.environ.get("NS_RUNTIME_OPENCODE_BASELINE_SOURCE")
        if baseline:
            spec = importlib.util.spec_from_file_location("opencode_contract_baseline", baseline)
            module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
            module.ROOT = ROOT
        with tempfile.TemporaryDirectory(dir="/var/tmp") as temporary:
            scratch = Path(temporary)
            # Match host relative depths: primary below HOME/code, runtime
            # worktree below /var/tmp, profile below HOME/.local/state. Sibling
            # fixture dirs can accidentally give vendor files the same relative
            # pattern under both instances and conceal the selected-read defect.
            home = scratch / "h"
            primary, workspace = home / "code/primary", scratch / "vt/worktree"
            primary.mkdir(parents=True); workspace.parent.mkdir()
            subprocess.run(["git", "init", "-q", str(primary)], check=True)
            (primary / "AGENTS.md").write_text("PRIMARY_AGENTS_MARKER\n")
            subprocess.run(["git", "-C", str(primary), "add", "AGENTS.md"], check=True)
            subprocess.run(["git", "-C", str(primary), "-c", "user.name=Fixture",
                "-c", "user.email=fixture@users.noreply.github.com", "commit", "-qm", "fixture"], check=True)
            subprocess.run(["git", "-C", str(primary), "worktree", "add", "--detach", str(workspace)],
                           check=True, capture_output=True)
            (workspace / "AGENTS.md").write_text("OWNED_AGENTS_MARKER\n")
            owned, outside = workspace / "owned.txt", primary / "primary-only.txt"
            owned.write_text("OWNED_FILE_MARKER\n"); outside.write_text("PRIMARY_FILE_MARKER\n")
            state = home / ".local/state/profiles"
            with mock.patch.object(module, "canonical_servers", return_value={"context-mode": {"command": "node"}}), \
                    mock.patch.object(module.shutil, "which", return_value="/fixture/rtk"), \
                    mock.patch.object(module.subprocess, "check_output", side_effect=[
                        "rtk 0.51.0\n", "e001f773f80b22b7dc4c7a79521b30e35aaef026\n"]), \
                    mock.patch.object(module.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)):
                module.render("opencode-gpt", state=state, home=home, eco_root=scratch, templates=[],
                    pi_bin=Path("/fixture/pi"), opencode_bin=Path(binary), rtk_source=scratch, role_scope="reviewer")
            root = state / "opencode-gpt/roles/reviewer"
            config_path = root / "config/opencode/opencode.json"
            config = json.loads(config_path.read_text())
            config.update(plugin=[], mcp={})
            config["experimental"] = {"openTelemetry": False}
            config_path.write_text(json.dumps(config))
            for role in json.loads((root / "profile.json").read_text())["roles"].values():
                for preload in role["preloads"]:
                    path = Path(preload["path"]); path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text("# Fixture canonical preload\n")
            selected = module.opencode_role_skill_directories(root, "reviewer")[1] / "SKILL.md"
            selected.parent.mkdir(parents=True, exist_ok=True); selected.write_text("SELECTED_VENDOR_MARKER\n")
            unselected = selected.parent.parent / "test-driven-development/SKILL.md"
            unselected.parent.mkdir(); unselected.write_text("UNSELECTED_VENDOR_MARKER\n")
            config_dir = config_path.parent
            (config_dir / "node_modules").mkdir()
            (config_dir / "package.json").write_text('{"dependencies":{"@opencode-ai/plugin":"1.18.35"}}')
            (config_dir / "package-lock.json").write_text('{"packages":{"":{"dependencies":{"@opencode-ai/plugin":"1.18.35"}}}}')
            args = argparse.Namespace(profile="opencode-gpt", state_root=state, repository=primary,
                role="evidence-reviewer", print=True, prompt="Read owned.txt", timeout_seconds=25)
            launch = {}
            def record(command, **kwargs):
                launch.update(command=command, env=kwargs["env"], cwd=kwargs["cwd"])
                return subprocess.CompletedProcess(command, 0)
            with mock.patch.dict(os.environ, {"PWD": str(primary)}), \
                    mock.patch.object(module, "fresh_worktree", return_value=workspace), \
                    mock.patch.object(module.subprocess, "run", side_effect=record), \
                    mock.patch.object(module.subprocess, "check_output", return_value="a" * 40), \
                    mock.patch.object(module, "utc", return_value="2026-10-12T00:00:00Z"), \
                    mock.patch.object(module, "cleanup_worktree", return_value={"status": "fixture_retained"}), \
                    redirect_stdout(io.StringIO()):
                module.launch(args)
            env = {key: value for key, value in launch["env"].items() if key.startswith(("XDG_", "OPENCODE_"))}
            env.update(HOME=str(home), PWD=launch["env"]["PWD"], PATH="/usr/bin:/bin",
                       TMPDIR=str(root / "tmp"), LANG="C.UTF-8", TERM="dumb")
            # No inherited host environment/credential. Host tree is read-only;
            # private scratch and scratch-backed /tmp are the only writable dirs.
            def native(argv, cwd=workspace):
                command = [bwrap, "--ro-bind", "/", "/", "--bind", str(scratch), str(scratch),
                    "--bind", str(root / "tmp"), "/tmp", "--dev", "/dev", "--proc", "/proc",
                    "--unshare-net", "--unshare-pid", "--die-with-parent", "--chdir", str(cwd),
                    "/usr/bin/env", "PWD=" + env["PWD"], *argv]
                return subprocess.run(command, env=env, stdin=subprocess.DEVNULL,
                                      capture_output=True, text=True, timeout=35)
            version = native([binary, "--version"])
            self.assertEqual(version.stdout.strip(), "1.18.35", "test binary does not match installed source pin")
            capture = scratch / "capture.py"; capture.write_text(CAPTURE)
            command = launch["command"]
            command = command[command.index(binary):]
            summary = native([sys.executable, str(capture), str(workspace), binary,
                              "--print-logs", "--log-level", "INFO", *command[1:]])
            self.assertEqual(summary.returncode, 0, "hermetic fixture runner failed")
            result = json.loads(summary.stdout)
            self.assertTrue(result["request_captured"], "native request never reached namespace-local reject stub")
            # Subtests report both defects at the reviewed baseline.
            for field in ("session_directory_owned", "working_directory_owned", "owned_instruction"):
                with self.subTest(field=field):
                    self.assertTrue(result[field], "native session/prompt did not use its assigned worktree")
            self.assertFalse(result["primary_instruction"])
            # Match the actual native run.ts directory rule, including a
            # baseline inherited PWD, rather than an assumed worktree base.
            native_directory = workspace if "--dir" in command else Path(env["PWD"])
            for label, target, marker, permitted in (
                ("owned", owned, "OWNED_FILE_MARKER", True),
                ("primary", outside, "PRIMARY_FILE_MARKER", False),
                ("selected_vendor", selected, "SELECTED_VENDOR_MARKER", True),
                ("unselected_vendor", unselected, "UNSELECTED_VENDOR_MARKER", False),
            ):
                with self.subTest(target=label):
                    probe = native([binary, "debug", "agent", "evidence-reviewer", "--tool", "read",
                                    "--params", json.dumps({"filePath": str(target)})], cwd=native_directory)
                    self.assertEqual(marker in probe.stdout, permitted, "native read containment differs from the role contract")


if __name__ == "__main__":
    unittest.main()
