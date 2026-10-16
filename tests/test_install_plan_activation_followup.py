"""Post-staging regressions using extracted shell seams and fixture commands.

Never execute full install/accept scripts, native installers or host services.
"""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from tests.test_install_plan_no_start_ports import PLAN, host_allocation, module


class DeferredDockerSetupTests(unittest.TestCase):
    def run_container_row(self, root, *, no_start, setup_exit=0):
        checker = module(PLAN / "check_plan.py", "activation_docker_checker")
        functions = checker.functions((PLAN / "install.sh").read_text())
        definitions = "\n".join(name + "() {\n" + functions[name] + "\n}"
                                for name in ("container-engine", "activate_user_unit"))
        script = definitions + r'''
run_command() { eval "$1"; }
docker_repository() { :; }
docker_engine_packages() { :; }
copy_config() { install -m 0600 "$fixture_source/$1" "$config_root/$1"; }
systemctl() { printf 'systemctl %s\n' "$*" >> "$HOME/calls"; }
sudo() { "$@"; }
dockerd-rootless-setuptool.sh() {
  printf 'native-setup %s\n' "$*" >> "$HOME/calls"
  [[ "$fixture_setup_exit" == 0 ]] || return "$fixture_setup_exit"
  mkdir -p "$HOME/.config/systemd/user"
  if [[ ! -f "$HOME/.config/systemd/user/docker.service" ]]; then
    printf 'fixture native Docker unit\n' > "$HOME/.config/systemd/user/docker.service"
  fi
  # Moby8af9fe3a install creates/selects the rootless CLI context even with a unit.
  printf 'rootless\n' > "$HOME/selected-context"
  printf 'unix://%s/docker.sock\n' "$XDG_RUNTIME_DIR" > "$HOME/context-endpoint"
}
docker() {
  [[ "$*" == 'context show' ]] || return 91
  if [[ -f "$HOME/selected-context" ]]; then cat "$HOME/selected-context"; else printf 'default\n'; fi
}
container-engine
docker context show
'''
        (root / "config").mkdir(exist_ok=True)
        (root / "run").mkdir(exist_ok=True)
        return subprocess.run(["bash", "-euo", "pipefail", "-c", script], text=True, capture_output=True,
            env={"PATH": "/usr/bin:/bin", "HOME": str(root), "XDG_RUNTIME_DIR": str(root / "run"),
                 "NS2604_NO_START": "1" if no_start else "0", "config_root": str(root / "config"),
                 "fixture_source": str(PLAN / "config"), "fixture_setup_exit": str(setup_exit)})

    def test_normal_install_completes_rootless_context_after_no_start(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            staged = self.run_container_row(root, no_start=True)
            self.assertEqual(staged.returncode, 0, staged.stderr)
            self.assertEqual(staged.stdout.strip(), "default")
            unit = root / ".config/systemd/user/docker.service"
            staged_unit = unit.read_bytes()
            self.assertNotRegex((root / "calls").read_text(), r"native-setup|\b(enable|start)\b")
            activated = self.run_container_row(root, no_start=False)
            self.assertEqual(activated.returncode, 0, activated.stderr)
            self.assertEqual(activated.stdout.strip(), "rootless")
            self.assertEqual((root / "context-endpoint").read_text().strip(), f"unix://{root}/run/docker.sock")
            self.assertEqual(unit.read_bytes(), staged_unit)

    def test_fresh_and_repeated_normal_installs_use_native_setup(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = self.run_container_row(root, no_start=False)
            self.assertEqual(first.returncode, 0, first.stderr)
            unit = root / ".config/systemd/user/docker.service"
            original = unit.read_bytes()
            second = self.run_container_row(root, no_start=False)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(second.stdout.strip(), "rootless")
            self.assertEqual(unit.read_bytes(), original)
            self.assertEqual((root / "calls").read_text().count("native-setup install\n"), 2)

    def test_repeated_no_start_only_registers_the_unit(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for _ in range(2):
                result = self.run_container_row(root, no_start=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.strip(), "default")
            calls = (root / "calls").read_text()
            self.assertNotRegex(calls, r"native-setup|\b(enable|start)\b")
            self.assertEqual(calls.count("systemctl --user daemon-reload\n"), 2)

    def test_failed_deferred_setup_stops_before_activation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            staged = self.run_container_row(root, no_start=True)
            self.assertEqual(staged.returncode, 0, staged.stderr)
            result = self.run_container_row(root, no_start=False, setup_exit=37)
            self.assertEqual(result.returncode, 37)
            self.assertFalse((root / "selected-context").exists())
            self.assertNotIn("systemctl --user enable", (root / "calls").read_text())


class DockerSetupContractTests(unittest.TestCase):
    def test_checker_rejects_unguarded_or_incomplete_native_setup(self):
        checker = module(PLAN / "check_plan.py", "activation_contract_checker")
        source = (PLAN / "install.sh").read_text()
        rows = json.loads((PLAN / "install-plan.json").read_text())["owners"]
        guard = 'if [[ "$NS2604_NO_START" != 1 ]]; then dockerd-rootless-setuptool.sh install; fi'

        def issues(text):
            failures = []
            checker.no_start_contract(rows, checker.functions(text), text,
                                      lambda category, message: failures.append(message))
            return failures

        self.assertEqual(issues(source), [])
        for replacement in (
            "dockerd-rootless-setuptool.sh install",
            guard + "; dockerd-rootless-setuptool.sh install",
            'if [[ "$NS2604_NO_START" != 1 && ! -f "$HOME/.config/systemd/user/docker.service" ]]; then dockerd-rootless-setuptool.sh install; fi',
        ):
            with self.subTest(replacement=replacement):
                changed = source.replace(guard, replacement, 1)
                self.assertNotEqual(changed, source)
                self.assertTrue(any("rootless setup" in message for message in issues(changed)))


class InheritedAcceptanceHostTests(unittest.TestCase):
    def run_selector(self, root, *, inherited=None, arguments=()):
        source = (PLAN / "accept.sh").read_text()
        selector = source.split("only=''\n", 1)[1].split('case "$stage" in', 1)[0]
        script = "only=''\n" + selector + '''
python3 "$plan_dir/config/observability_config.py" gateway --config-root "$config_root" > "$HOME/before-directory-change"
cd "$tool_root/gpt-researcher"
python3 "$plan_dir/config/observability_config.py" gateway --config-root "$config_root"
'''
        config = root / "config"
        config.mkdir(exist_ok=True)
        tools = root / "tools"
        (tools / "gpt-researcher").mkdir(parents=True, exist_ok=True)
        environment = {"PATH": "/usr/bin:/bin", "HOME": str(root), "plan_dir": str(PLAN),
                       "config_root": str(config), "tool_root": str(tools)}
        if inherited is not None:
            environment["NS2604_HOST_FILE"] = inherited
        return subprocess.run(["bash", "-euo", "pipefail", "-c", script, "acceptance-fixture", *arguments],
                              cwd=root, env=environment, text=True, capture_output=True)

    def test_inherited_relative_host_survives_research_directory_change(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            host = root / "host values/selected.json"
            host.parent.mkdir()
            host.write_text(json.dumps(host_allocation({"NS_PORT_GATEWAY": "41128"})))
            result = self.run_selector(root, inherited="host values/selected.json")
            self.assertEqual((root / "before-directory-change").read_text().strip(), "http://127.0.0.1:41128/v1")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "http://127.0.0.1:41128/v1")

    def test_explicit_host_overrides_the_inherited_selector(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            host = root / "explicit host.json"
            host.write_text(json.dumps(host_allocation({"NS_PORT_GATEWAY": "51128"})))
            result = self.run_selector(root, inherited="missing/inherited.json",
                                       arguments=("--host-file", host.name))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "http://127.0.0.1:51128/v1")

    def test_absolute_inherited_and_saved_selectors_survive_directory_change(self):
        for saved in (False, True):
            with self.subTest(saved=saved), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                host = root / "config/.service-ports.json" if saved else root / "host.json"
                host.parent.mkdir(exist_ok=True)
                host.write_text(json.dumps(host_allocation({"NS_PORT_GATEWAY": "41128"})))
                result = self.run_selector(root, inherited=None if saved else str(host))
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.strip(), "http://127.0.0.1:41128/v1")

    def test_invalid_parent_path_fails_before_any_check_runs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result = self.run_selector(root, inherited="missing/host.json")
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((root / "before-directory-change").exists())

    def test_no_selector_keeps_the_default_endpoint(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = self.run_selector(Path(temporary))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "http://127.0.0.1:21128/v1")


if __name__ == "__main__":
    unittest.main()
