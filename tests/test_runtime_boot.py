"""Hermetic native Context Mode boot; no provider call, network or host HOME.

Vendor1.0.169 /6f0cc684 start.mjs config/self-heal paths and native MCP initialize.
CI without this installed vendor package skips native integration; portable
profile generation/isolation tests remain in test_runtime_profiles.py.
"""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/adoption"))
import runtime_profiles as profiles


class HermeticRuntimeBootTests(unittest.TestCase):
    def test_context_mode_boot_creates_zero_entries_outside_profile(self):
        package = Path(os.environ.get("NS_CONTEXT_MODE_TEST_PACKAGE", ""))
        if not (package / "start.mjs").is_file():
            self.skipTest("explicit installed context-mode test package not supplied")
        if json.loads((package / "package.json").read_text())["version"] != "1.0.169":
            self.fail("test package does not match the cited pin")
        node, bwrap = shutil.which("node"), shutil.which("bwrap")
        if not node or not bwrap:
            self.skipTest("hermetic native runtime prerequisites unavailable")
        node = str(Path(node).resolve())
        # --ignore-scripts suppresses dependency builds as well as the unsafe
        # context-mode postinstall. Native initialize alone is insufficient:
        # the stores are lazy. Require a usable dependency binding too.
        sqlite = package.parent / "better-sqlite3"
        binding = subprocess.run([node, "-e",
            "const D=require(process.argv[1]);const d=new D(':memory:');"
            "console.log(d.prepare('select 1 as ready').get().ready);d.close();", str(sqlite)],
            env={"PATH": str(Path(node).parent), "TMPDIR": "/var/tmp"},
            capture_output=True, text=True, timeout=10)
        self.assertEqual(binding.returncode, 0, "native SQLite dependency is not ready")
        self.assertEqual(binding.stdout.strip(), "1")
        module = profiles
        baseline = os.environ.get("NS_RUNTIME_BOOT_BASELINE_SOURCE")
        if baseline:
            spec = importlib.util.spec_from_file_location("runtime_boot_baseline", baseline)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            module.ROOT = ROOT
        for profile in profiles.PROFILES:
            with self.subTest(profile=profile), tempfile.TemporaryDirectory(dir="/var/tmp") as temporary:
                scratch = Path(temporary)
                home = scratch / "home"
                home.mkdir()
                (home / ".claude").mkdir()
                sentinel = home / ".claude/settings.json"
                sentinel.write_text('{"hooks":{}}\n')
                state = scratch / "profiles"
                root = state / profile
                root.mkdir(parents=True)
                (root / "tmp").mkdir()
                (root / "config/opencode").mkdir(parents=True)
                (root / "config/opencode/opencode.json").write_text('{"plugin":[]}\n')
                env = {"HOME": str(home), "PATH": str(Path(node).parent) + ":/usr/bin:/bin",
                       "TMPDIR": str(root / "tmp"), "CONTEXT_MODE_PROJECT_DIR": str(root),
                       "CLAUDE_PROJECT_DIR": str(root), "NODE_NO_WARNINGS": "1"}
                scoped = module.profile_environment(profile, state)
                env.update({key: value for key, value in scoped.items() if key.startswith("CONTEXT_MODE_") or key == "CLAUDE_CONFIG_DIR"})
                if hasattr(module, "context_mode_environment"):
                    env.update(module.context_mode_environment(profile, state))
                    Path(env["HOME"]).mkdir(parents=True)
                def outside_snapshot():
                    return {str(p.relative_to(scratch)): p.read_bytes() if p.is_file() else None
                            for p in scratch.rglob("*") if not p.is_relative_to(root)}
                before = outside_snapshot()
                # No inherited credentials/config. No network. Only fixture
                # HOME/profile can be written; actual host config is unmounted.
                command = [bwrap, "--unshare-all", "--die-with-parent", "--new-session",
                           "--ro-bind", "/usr", "/usr", "--ro-bind", "/lib", "/lib",
                           "--ro-bind", "/lib64", "/lib64", "--dev", "/dev", "--proc", "/proc",
                           "--ro-bind", str(Path(node).parent), str(Path(node).parent),
                           "--ro-bind", str(package.resolve()), str(package.resolve()),
                           "--bind", str(scratch), str(scratch),
                           "--chdir", str(root / "config/opencode" if profile.startswith("opencode") else root),
                           node, str(package.resolve() / "start.mjs")]
                initialize = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                    "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                               "clientInfo": {"name": "hermetic-profile-fixture", "version": "1"}}}) + "\n"
                result = subprocess.run(command, input=initialize, env=env, text=True,
                                        capture_output=True, timeout=25)
                self.assertEqual(result.returncode, 0, "native hermetic bootstrap failed")
                responses = [json.loads(line) for line in result.stdout.split("\n") if line.startswith('{')]
                self.assertTrue(any(item.get("id") == 1 and "result" in item for item in responses),
                                "native MCP initialize did not complete")
                after = outside_snapshot()
                self.assertEqual(after, before, "native boot wrote outside its private profile")


if __name__ == "__main__":
    unittest.main()
