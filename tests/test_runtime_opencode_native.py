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
try:
    result = subprocess.run(sys.argv[2:], stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=25)
except subprocess.TimeoutExpired as error:
    from types import SimpleNamespace
    result = SimpleNamespace(returncode=124, stderr=(error.stderr or b'').decode() if isinstance(error.stderr,bytes) else (error.stderr or ''))
text = json.dumps(request)
created = __import__('re').findall(r'created .*?directory=([^\s]+)', result.stderr)
summary = {'exit_code':result.returncode, 'request_captured':bool(request),
    'owned_instruction':'OWNED_AGENTS_MARKER' in text, 'primary_instruction':'PRIMARY_AGENTS_MARKER' in text,
    'working_directory_owned':('Working directory: '+sys.argv[1]) in text,
    'session_directory_owned':bool(created) and all(p==sys.argv[1] for p in created),
    'diagnostic':result.stderr[-1600:] if not request else ''}
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
        # Native verification of executable layouts uses only an already
        # installed public uv binary; never a real private file.
        uv_layout = os.environ.get("NS_RUNTIME_TEST_UV_LAYOUT")
        original_path = os.environ.get("PATH", "")
        self.addCleanup(os.environ.__setitem__, "PATH", original_path)
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
            if uv_layout == "local":
                outside = home / ".local/state/private-fixture.txt"
                outside.parent.mkdir(parents=True)
            owned.write_text("OWNED_FILE_MARKER\n"); outside.write_text("PRIMARY_FILE_MARKER\n")
            unrelated = scratch / "unrelated/outside.txt"
            unrelated.parent.mkdir(); unrelated.write_text("UNRELATED_FILE_MARKER\n")
            state = home / ".local/state/profiles"
            with mock.patch.object(module, "canonical_servers", return_value={"context-mode": {"command": "node"}}), \
                    mock.patch.object(module, "verify_runtime_binary", return_value="1.18.35", create=True), \
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
                    mock.patch.object(module, "opencode_sandbox_command", side_effect=lambda command, *args: command, create=True), \
                    mock.patch.object(module, "verify_runtime_binary", return_value="1.18.35", create=True), \
                    mock.patch.object(module, "fresh_worktree", return_value=workspace), \
                    mock.patch.object(module.subprocess, "run", side_effect=record), \
                    mock.patch.object(module.subprocess, "check_output", return_value="a" * 40), \
                    mock.patch.object(module, "utc", return_value="2026-10-12T00:00:00Z"), \
                    mock.patch.object(module, "cleanup_worktree", return_value={"status": "fixture_retained"}), \
                    redirect_stdout(io.StringIO()):
                module.launch(args)
            env = {key: value for key, value in launch["env"].items() if key.startswith(("XDG_", "OPENCODE_"))}
            env.update(HOME=str(home), PWD=launch["env"]["PWD"], PATH="/usr/bin:/bin",
                       TMPDIR=str(scratch), LANG="C.UTF-8", TERM="dumb")
            # The late-link probe is a native Node program. Its interpreter is an
            # explicit public dependency, never selected through host config.
            node = str(Path(shutil.which("node")).resolve())
            env["PATH"] = str(Path(node).parent) + ":/usr/bin:/bin"
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
            if uv_layout:
                uv_bin = home / (".local/bin" if uv_layout == "local" else "bin")
                uv_bin.mkdir(parents=True)
                shutil.copy2(Path(shutil.which("uv")).resolve(), uv_bin / "uv")
                os.environ["PATH"] = str(uv_bin) + os.pathsep + original_path
            with mock.patch.object(Path, "home", return_value=home):
                fenced = (module.opencode_sandbox_command([binary], root, workspace,
                    {"opencode_bin": binary}, "evidence-reviewer") if hasattr(module,"opencode_sandbox_command") else [binary])
            sandbox_prefix = fenced[:-1]
            capture = scratch / "capture.py"; capture.write_text(CAPTURE)
            command = launch["command"]
            command = command[command.index(binary):]
            summary = native([sys.executable, str(capture), str(workspace), *sandbox_prefix, binary,
                              "--print-logs", "--log-level", "INFO", *command[1:]])
            self.assertEqual(summary.returncode, 0, "hermetic fixture runner failed")
            result = json.loads(summary.stdout)
            self.assertTrue(result["request_captured"], "native request never reached namespace-local reject stub: "
                            + result.get("diagnostic", "").replace(str(Path.home()), "<home>"))
            # Subtests report both defects at the reviewed baseline.
            for field in ("session_directory_owned", "working_directory_owned", "owned_instruction"):
                with self.subTest(field=field):
                    self.assertTrue(result[field], "native session/prompt did not use its assigned worktree")
            self.assertFalse(result["primary_instruction"])
            # Project config is attacker-controlled input to deep merge. A
            # named permission survives a later wildcard deny unless project
            # loading is disabled. Exercise the real native tool, not only
            # rendered keys, while preserving absolute AGENTS.md loading.
            (workspace / "opencode.json").write_text(json.dumps({"agent": {
                "evidence-reviewer": {"permission": {"bash": "allow"}}}}))
            with self.subTest(target="project_config_tool_grant"):
                shell = native([*sandbox_prefix, binary, "debug", "agent", "evidence-reviewer",
                    "--tool", "bash", "--params", json.dumps({
                        "command": "printf FIXTURE_PROJECT_TOOL_ESCAPE",
                        "description": "synthetic neutral tool-fence probe"})])
                self.assertNotIn("FIXTURE_PROJECT_TOOL_ESCAPE", shell.stdout,
                                 "worktree project config enabled an ungranted shell tool")
                self.assertNotEqual(shell.returncode, 0, "native shell fence was not enforced")
            # Match the actual native run.ts directory rule, including a
            # baseline inherited PWD, rather than an assumed worktree base.
            native_directory = workspace if "--dir" in command else Path(env["PWD"])
            file_alias = workspace / "linked-primary.txt"
            directory_alias = workspace / "linked-primary-dir"
            vendor_alias = selected.parent / "linked-primary.txt"
            relative_alias = workspace / "relative-primary.txt"
            unselected_alias = workspace / "linked-unselected.txt"
            safe_alias = workspace / "linked-owned.txt"
            unrelated_alias = workspace / "linked-unrelated.txt"
            file_alias.symlink_to(outside)
            directory_alias.symlink_to(outside.parent, target_is_directory=True)
            vendor_alias.symlink_to(outside)
            relative_alias.symlink_to(os.path.relpath(outside, workspace))
            unselected_alias.symlink_to(unselected)
            safe_alias.symlink_to(owned)
            unrelated_alias.symlink_to(unrelated)
            for label, target, marker, permitted in (
                ("owned", owned, "OWNED_FILE_MARKER", True),
                ("primary", outside, "PRIMARY_FILE_MARKER", False),
                ("unrelated", unrelated, "UNRELATED_FILE_MARKER", False),
                ("selected_vendor", selected, "SELECTED_VENDOR_MARKER", True),
                ("unselected_vendor", unselected, "UNSELECTED_VENDOR_MARKER", False),
                ("file_alias", file_alias, "PRIMARY_FILE_MARKER", False),
                ("directory_alias", directory_alias / outside.name, "PRIMARY_FILE_MARKER", False),
                ("vendor_alias", vendor_alias, "PRIMARY_FILE_MARKER", False),
                ("relative_alias", relative_alias, "PRIMARY_FILE_MARKER", False),
                ("unselected_alias", unselected_alias, "UNSELECTED_VENDOR_MARKER", False),
                ("owned_alias", safe_alias, "OWNED_FILE_MARKER", True),
                ("unrelated_alias", unrelated_alias, "UNRELATED_FILE_MARKER", False),
            ):
                with self.subTest(target=label):
                    probe = native([*sandbox_prefix, binary, "debug", "agent", "evidence-reviewer", "--tool", "read",
                                    "--params", json.dumps({"filePath": str(target)})], cwd=native_directory)
                    self.assertEqual(marker in probe.stdout, permitted,
                        "native read containment differs from the role contract: "
                        + probe.stderr.replace(str(Path.home()), "<home>")[-1400:])
            # Create the alias from inside the already-running filesystem
            # namespace: the guarantee cannot depend on the preflight snapshot.
            script = "const fs=require('fs');fs.symlinkSync(process.argv[1],process.argv[2]);" \
                     "let disclosed=false;try{disclosed=fs.readFileSync(process.argv[2],'utf8').includes('PRIMARY_FILE_MARKER')}catch{}" \
                     "console.log(JSON.stringify({disclosed}));"
            live = native([*sandbox_prefix, node, "-e", script, str(outside), str(workspace / "late-alias")])
            self.assertEqual(live.returncode, 0, "live-link boundary probe did not execute: "
                             + live.stderr.replace(str(Path.home()), "<home>")[-1000:])
            self.assertFalse(json.loads(live.stdout)["disclosed"])
            late_vendor = native([*sandbox_prefix, node, "-e", script, str(unselected),
                                  str(workspace / "late-vendor-alias")])
            self.assertEqual(late_vendor.returncode, 0, "live vendor-link boundary probe did not execute")
            # The helper checks the primary marker; verify the unselected
            # vendor target is absent too using an independent content oracle.
            vendor_read = native([*sandbox_prefix, node, "-e",
                "const f=require('fs');try{console.log(f.readFileSync(process.argv[1],'utf8'))}catch{console.log('DENIED')}",
                str(workspace / "late-vendor-alias")])
            self.assertEqual(vendor_read.returncode, 0)
            self.assertEqual(vendor_read.stdout.strip(), "DENIED")


if __name__ == "__main__":
    unittest.main()
