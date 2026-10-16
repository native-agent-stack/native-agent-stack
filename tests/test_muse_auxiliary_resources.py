"""Model-free controls for the reviewed public dependency inventory."""

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


MODULE = Path(__file__).resolve().parents[1] / "tools/adoption/muse_auxiliary_resources.py"
spec = importlib.util.spec_from_file_location("muse_auxiliary_resources_tested", MODULE)
resources = importlib.util.module_from_spec(spec)
if MODULE.exists():
    spec.loader.exec_module(resources)


class MuseAuxiliaryResourcesTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.home = self.base / "home"
        self.eco = self.home / ".local/share/codex-ecosystem"
        self.profile = self.home / ".local/state/trial/role"
        self.profile.mkdir(parents=True)
        self.node_root = self.home / ".local/share/mise/installs/node/24.21.0"
        self.python_root = self.home / ".local/share/mise/installs/python/3.13.16"
        self.executable(self.node_root / "bin/node")
        self.executable(self.python_root / "bin/python3.13")
        (self.python_root / "lib/python3.13").mkdir(parents=True)
        self.node_package(self.node_root / "lib/node_modules/npm", "npm", "11.19.0", "bin/npx-cli.js")
        self.npx_physical = self.node_root / "lib/node_modules/npm/bin/npx-cli.js"
        self.executables = {}
        self.alias("node", self.eco / "bin/node", self.node_root / "bin/node")
        self.alias("npx", self.node_root / "bin/npx", self.npx_physical)
        self.executable(self.eco / "tools/rtk-0.51.0/rtk")
        self.alias("rtk", self.eco / "bin/rtk", self.eco / "tools/rtk-0.51.0/rtk")
        self.venv("serena", self.home / ".local/share/uv/tools/serena-agent", "serena-agent", "2.0.0.dev0")
        self.venv("semble", self.home / ".local/share/uv/tools/semble", "semble", "0.6.2")
        self.venv("jcodemunch-mcp", self.eco / "python-tools/jcodemunch-mcp", "jcodemunch-mcp", "1.108.333")
        self.socraticode = self.eco / "tools/socraticode-1.15.0/lib/node_modules/socraticode"
        self.node_package(self.socraticode, "socraticode", "1.15.0", "dist/index.js")
        self.promptfoo = self.eco / "tools/promptfoo-0.124.0/lib/node_modules/promptfoo"
        self.node_package(self.promptfoo, "promptfoo", "0.124.0", "dist/src/entrypoint.js")
        self.alias("promptfoo", self.eco / "bin/promptfoo", self.promptfoo / "dist/src/entrypoint.js")
        self.commands = {
            "serena": ["serena", "start-mcp-server", "--transport", "stdio"],
            "semble": ["semble"],
            "jcodemunch": [str(self.executables["jcodemunch-mcp"])],
            "chrome-devtools": ["npx", "-y", "chrome-devtools-mcp@1.10.1", "--isolated"],
            "promptfoo": [str(self.executables["promptfoo"]), "mcp", "--transport", "stdio"],
            "socraticode": [str(self.executables["node"]), str(self.socraticode / "dist/index.js")],
        }

    def executable(self, path, content="#!/usr/bin/env node\n"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        path.chmod(0o755)

    def alias(self, name, path, target):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.symlink_to(target)
        self.executables[name] = path

    def node_package(self, path, name, version, entrypoint):
        (path / "node_modules").mkdir(parents=True)
        (path / "package.json").write_text(json.dumps({"name": name, "version": version}))
        self.executable(path / entrypoint)

    def venv(self, command, path, package, version):
        site = path / "lib/python3.13/site-packages"
        metadata = site / (package.replace("-", "_") + "-" + version + ".dist-info")
        metadata.mkdir(parents=True)
        (metadata / "METADATA").write_text(f"Name: {package}\nVersion: {version}\n")
        if command == "serena":
            (metadata / "direct_url.json").write_text(json.dumps({
                "url": "https://github.com/oraios/serena",
                "vcs_info": {"commit_id": "c6fbd1c5932df2494ffa0020af5a9fbe80b82143"},
            }))
        (path / "pyvenv.cfg").write_text(
            f"home = {self.python_root / 'bin'}\nversion_info = 3.13.16\ninclude-system-site-packages = false\n"
        )
        (path / "bin").mkdir()
        (path / "bin/python").symlink_to(self.python_root / "bin/python3.13")
        self.executable(path / "bin" / command, f"#!{path / 'bin/python'}\n")
        alias = self.home / ".local/bin/semble" if command == "semble" else self.eco / "bin" / command
        self.alias(command, alias, path / "bin" / command)

    def qualify(self, **overrides):
        return resources.qualify_auxiliary_resources(**{
            "home": self.home, "eco_root": self.eco, "profile_root": self.profile,
            "executables": self.executables, "local_commands": self.commands, **overrides,
        })

    def test_inventory_contains_rtk_alias_target_and_named_resources(self):
        result = self.qualify()
        admitted = set(result["qualified_auxiliary_read_paths"])
        self.assertIn(str(self.executables["rtk"]), admitted)
        self.assertIn(str(self.executables["rtk"].resolve()), admitted)
        self.assertIn(str(self.socraticode), admitted)
        self.assertIn(str(self.promptfoo), admitted)
        for forbidden in [self.home, self.eco, self.home / ".local", self.home / ".local/share/uv/tools"]:
            self.assertNotIn(str(forbidden), admitted)
        self.assertEqual(result["local_server_commands"]["serena"][1:], self.commands["serena"][1:])

    def test_javascript_entrypoints_execute_physical_module_path(self):
        result = self.qualify()["local_server_commands"]
        node = str(self.executables["node"].resolve())
        self.assertEqual(result["chrome-devtools"], [node, str(self.npx_physical), *self.commands["chrome-devtools"][1:]])
        self.assertEqual(result["promptfoo"], [node, str(self.executables["promptfoo"].resolve()), *self.commands["promptfoo"][1:]])
        self.assertEqual(result["socraticode"], [node, str(self.socraticode / "dist/index.js")])

    def test_missing_dependency_refuses_before_launch(self):
        (self.promptfoo / "node_modules").rmdir()
        with self.assertRaisesRegex(resources.AuxiliaryResourceError, "promptfoo.*dependencies"):
            self.qualify()

    def test_wrong_installed_package_pin_refused(self):
        (self.socraticode / "package.json").write_text(json.dumps({"name": "socraticode", "version": "1.16.0"}))
        with self.assertRaisesRegex(resources.AuxiliaryResourceError, "socraticode.*pin"):
            self.qualify()

    def test_unknown_selected_entrypoint_refused(self):
        wrong = self.home / "other-project/serena"
        self.executable(wrong)
        with self.assertRaisesRegex(resources.AuxiliaryResourceError, "serena.*entrypoint"):
            self.qualify(executables={**self.executables, "serena": wrong})

    def test_venv_shebang_outside_named_interpreter_refused(self):
        self.executables["serena"].resolve().write_text("#!/usr/bin/python3\n")
        with self.assertRaisesRegex(resources.AuxiliaryResourceError, "serena.*interpreter"):
            self.qualify()

    def test_unknown_canonical_command_refused(self):
        with self.assertRaisesRegex(resources.AuxiliaryResourceError, "serena.*canonical command"):
            self.qualify(local_commands={**self.commands, "serena": ["other-agent", "start-mcp-server"]})

    def test_private_state_environment_does_not_point_at_host_state(self):
        environment = self.qualify()["environment"]
        for key in ["SERENA_HOME", "npm_config_cache", "SEMBLE_CACHE_LOCATION"]:
            self.assertTrue(Path(environment[key]).is_relative_to(self.profile))
        self.assertEqual(environment["PYTHONDONTWRITEBYTECODE"], "1")


if __name__ == "__main__":
    unittest.main()
