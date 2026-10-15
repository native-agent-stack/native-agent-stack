"""Install-plan regressions: extracted shell commands and disposable config fixtures only.

Never execute install.sh, accept.sh, installers, or the host's systemctl.
The baseline is native-agent-stack@8053f14e7; upstream mechanisms are cited in
the plan's NO_START_PORTS.md record.
"""
import importlib.util
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "evidence/artifacts/new-wsl-install-plan-20261002"


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


class NoStartTests(unittest.TestCase):
    def test_mineru_transient_start_is_deferred_in_no_start_mode(self):
        checker = module(PLAN / "check_plan.py", "mineru_start_check")
        funcs = checker.functions((PLAN / "install.sh").read_text())
        command = next(c for c in checker.run_commands("mineru", funcs, set()) if "mineru server start" in c)
        script = ('mineru() { printf "CALL %s\\n" "$*"; }; '
                  'mineru-kit() { printf "KIT %s\\n" "$*"; }; jq() { return 1; };\n' + command)
        for mode in ("0", "1"):
            result = subprocess.run(["bash", "-euo", "pipefail", "-c", script], text=True, capture_output=True,
                                    env={"PATH": "/usr/bin:/bin", "NS2604_NO_START": mode})
            self.assertEqual(result.returncode, 0, result.stderr)
            if mode == "0":
                self.assertIn("CALL server start", result.stdout)
                self.assertIn("CALL server stop", result.stdout)
            else:
                self.assertNotIn("CALL", result.stdout)
                self.assertNotIn("KIT", result.stdout)

    def test_docker_no_start_masks_package_activation_and_skips_setup(self):
        checker = module(PLAN / "check_plan.py", "docker_check")
        funcs = checker.functions((PLAN / "install.sh").read_text())
        setup = next(c for c in checker.run_commands("container-engine", funcs, set())
                     if "dockerd-rootless-setuptool.sh install" in c)
        script = ('sudo() { printf "CALL %s\\n" "$*"; }; apt_release_version() { printf "fixture"; };\n'
                  'dockerd-rootless-setuptool.sh() { printf "UNSAFE_SETUP\\n"; };\n'
                  'docker_engine_packages() {\n' + funcs["docker_engine_packages"] + '\n}\n'
                  'docker_engine_packages\n' + setup)
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(["bash", "-euo", "pipefail", "-c", script], text=True, capture_output=True,
                                    env={"PATH": "/usr/bin:/bin", "HOME": tmp, "NS2604_NO_START": "1"})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("UNSAFE_SETUP", result.stdout)
        self.assertLess(result.stdout.index("systemctl mask docker.service docker.socket containerd.service"),
                        result.stdout.index("apt-get install"))

    def test_activation_helper_only_enables_in_normal_mode(self):
        checker = module(PLAN / "check_plan.py", "activation_check")
        body = checker.functions((PLAN / "install.sh").read_text())["activate_user_unit"]
        for mode in ("0", "1"):
            script = 'systemctl() { printf "%s\\n" "$*"; }\nactivate_user_unit() {\n' + body + '\n}\nactivate_user_unit fixture.service'
            result = subprocess.run(["bash", "-euo", "pipefail", "-c", script],
                                    env={"PATH": "/usr/bin:/bin", "NS2604_NO_START": mode}, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "" if mode == "1" else "--user enable --now fixture.service\n")

    def test_dagu_installer_receives_no_service_mode(self):
        checker = module(PLAN / "check_plan.py", "dagu_check")
        funcs = checker.functions((PLAN / "install.sh").read_text())
        command = next(c for c in checker.run_commands("dagu", funcs, set()) if "installer.sh" in c)
        script = 'curl() { :; }; bash() { printf "%s\\n" "$*"; };\n' + command
        result = subprocess.run(["bash", "-euo", "pipefail", "-c", script],
                                env={"PATH": "/usr/bin:/bin", "dagu_service_mode": "no"}, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--service no --service-scope user", result.stdout)

    def test_foreground_units_are_registered_without_activation(self):
        checker = module(PLAN / "check_plan.py", "unit_check")
        body = checker.functions((PLAN / "install.sh").read_text())["register_service_row"]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / "config"
            config.mkdir()
            (config / "ns2604-prometheus.service").write_text("[Service]\nExecStart=/bin/true\n")
            grafana = root / ".local/bin/grafana"
            grafana.parent.mkdir(parents=True)
            grafana.write_text("fixture binary path only")
            script = 'systemctl() { printf "CALL %s\\n" "$*"; }\nregister_service_row() {\n' + body + '\n}\n'
            script += '\n'.join('register_service_row ' + slot for slot in (
                "otel-collector-contrib", "prometheus", "loki", "grafana", "alerting"))
            result = subprocess.run(["bash", "-euo", "pipefail", "-c", script], text=True, capture_output=True,
                                    env={"PATH": "/usr/bin:/bin", "HOME": tmp, "config_root": str(config),
                                         "plan_dir": str(PLAN), "config_source_root": str(PLAN / "config"),
                                         "tool_root": str(root / "tools"), "NS2604_NO_START": "1"})
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(len(list((root / ".config/systemd/user").glob("*.service"))), 5)
            self.assertEqual(result.stdout.count("--user daemon-reload"), 5)
            self.assertNotRegex(result.stdout, r"\b(enable|start|restart|preset)\b")
            self.assertFalse(list((root / ".config/systemd/user").glob("*.wants")))

    def test_checker_rejects_start_bypass_in_every_service_row(self):
        checker = module(PLAN / "check_plan.py", "every_row_check")
        text = (PLAN / "install.sh").read_text()
        funcs = checker.functions(text)
        rows = json.loads((PLAN / "install-plan.json").read_text())["owners"]
        for row in rows:
            if row.get("service"):
                with self.subTest(slot=row["slot"]):
                    changed = dict(funcs)
                    changed[row["slot"]] += '\nrun_command "systemctl --user start unsafe.service"'
                    errors = []
                    checker.no_start_contract(rows, changed, text, lambda tag, msg: errors.append(msg))
                    self.assertTrue(any(row["slot"] + ": direct service activation" in e for e in errors), errors)

    def test_memory_unit_is_installed_and_reloaded_without_enable_or_start(self):
        checker = module(PLAN / "check_plan.py", "plan_check")
        funcs = checker.functions((PLAN / "install.sh").read_text())
        commands = checker.run_commands("memory-owner", funcs, set())
        command = next(c for c in commands if "systemd/user" in c)
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            unit = home / ".local/opt/ai-memory-2.5.2/packaging/systemd/ai-memory-user.service"
            unit.parent.mkdir(parents=True)
            unit.write_text("[Service]\nExecStart=/usr/bin/ai-memory serve\n[Install]\nWantedBy=default.target\n")
            helper = ("activate_user_unit() {\n" + funcs["activate_user_unit"] + "\n}\n"
                      if "activate_user_unit" in funcs else "")
            script = "set -euo pipefail\n" + helper + "\n" + (
                'systemctl() { printf "CALL %s\\n" "$*"; }\n'
                'export -f systemctl\n'
            ) + command
            result = subprocess.run(["bash", "-c", script], text=True, capture_output=True,
                                    env={"PATH": "/usr/bin:/bin", "HOME": tmp, "NS2604_NO_START": "1"})
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((home / ".config/systemd/user/ai-memory.service").is_file())
            self.assertIn("--user daemon-reload", result.stdout)
            self.assertNotRegex(result.stdout, r"\b(enable|start|restart|preset)\b")

    def test_no_start_is_an_install_option(self):
        self.assertTrue(re.search(r"--no-start\)", (PLAN / "install.sh").read_text()), "missing --no-start option")


class RtkFreshHostTests(unittest.TestCase):
    def test_hook_checks_ignore_the_upstream_missing_hook_warning(self):
        checker = module(PLAN / "check_plan.py", "rtk_plan_check")
        install = checker.functions((PLAN / "install.sh").read_text())
        acceptance = checker.functions((PLAN / "accept.sh").read_text())
        programs = [command for command in checker.run_commands("command-output", install, set())
                    if 'hook check "$command"' in command]
        programs += [command for _, _, _, command in checker.checks_of(acceptance["command-output"])
                     if 'hook check "$command"' in command]
        self.assertEqual(len(programs), 2)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake = root / "bin/rtk"
            fake.parent.mkdir()
            fake.write_text('#!/bin/bash\n'
                            'if [[ "${RTK_SUPPRESS_HOOK_WARNING:-0}" != 1 ]]; then '
                            'printf "No hook installed\\n" >&2; fi\n'
                            'if [[ "$3" == "git status" ]]; then printf "rtk git status\\n"; '
                            'else printf "No rewrite for: %s\\n" "$3"; exit 1; fi\n')
            fake.chmod(0o755)
            for index, program in enumerate(programs):
                with self.subTest(carrier=("install", "accept")[index]):
                    # Only the hook-check fragment: never initialize/trust hooks or run a client.
                    end = program.index('[[ "$decision" == "rtk git status" ]]') + len('[[ "$decision" == "rtk git status" ]]')
                    start = program.index('for command in ')
                    fragment = 'e="$ECO_ROOT"; ' + program[start:end]
                    result = subprocess.run(["bash", "-euo", "pipefail", "-c", fragment],
                                            env={"PATH": "/usr/bin:/bin", "ECO_ROOT": tmp},
                                            capture_output=True, text=True)
                    self.assertEqual(result.returncode, 0, "missing-hook stderr contaminated the decision")


class HostPortTests(unittest.TestCase):
    def test_shell_dispatchers_use_host_ports_and_staged_config_sources(self):
        checker = module(PLAN / "check_plan.py", "dispatch_ports")
        install = checker.functions((PLAN / "install.sh").read_text())
        acceptance = checker.functions((PLAN / "accept.sh").read_text())
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "config").mkdir()
            (root / "source").mkdir()
            (root / "source/probe.txt").write_text("http://127.0.0.1:31128")
            (root / "config/.service-ports.json").write_text(json.dumps({"NS_PORT_GATEWAY": "31128"}))
            env = {"PATH": "/usr/bin:/bin", "plan_dir": str(PLAN), "config_root": str(root / "config"),
                   "config_source_root": str(root / "source")}
            program = 'test "$(cat "$plan_dir/config/probe.txt")" = "http://127.0.0.1:21128"'
            script = 'run_command() {\n' + install["run_command"] + '\n}\nrun_command ' + shlex.quote(program)
            installed = subprocess.run(["bash", "-euo", "pipefail", "-c", script], env=env, text=True, capture_output=True)
            self.assertEqual(installed.returncode, 0, installed.stderr)
            script = ('stage=post_install; failed=0; port_args=(); prepare_path() { :; };\ncheck() {\n'
                      + acceptance["check"] + '\n}\ncheck fixture smoke ' + shlex.quote(program) + '\nexit "$failed"')
            accepted = subprocess.run(["bash", "-euo", "pipefail", "-c", script], env=env, text=True, capture_output=True)
            self.assertEqual(accepted.returncode, 0, accepted.stderr)
            self.assertEqual(accepted.stdout, "fixture | post_install | 0\n")

    def test_staging_and_later_commands_share_the_persisted_allocation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            host = root / "host.json"
            host.write_text(json.dumps({"NS_PORT_GATEWAY": "31128", "AI_MEMORY_URL": "127.0.0.1:39374"}))
            script = str(PLAN / "config/observability_config.py")
            common = [sys.executable, script]
            result = subprocess.run(common + ["stage", "--config-root", str(root / "config"),
                "--source-root", str(PLAN / "config"), "--output-root", str(root / "staged"),
                "--host-file", str(host), "--persist-ports"], text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("serve --port 31128", (root / "staged/omniroute-serve.sh").read_text())
            self.assertIn("Environment=PORT=31128", (root / "staged/omniroute.service").read_text())
            saved = (root / "config/.service-ports.json").read_bytes()
            command = subprocess.run(common + ["command", "--config-root", str(root / "config")],
                                     input="http://127.0.0.1:21128 http://127.0.0.1:29374", text=True, capture_output=True)
            self.assertEqual(command.returncode, 0, command.stderr)
            self.assertEqual(command.stdout, "http://127.0.0.1:31128 http://127.0.0.1:39374")
            acceptance = subprocess.run(common + ["stage", "--config-root", str(root / "config"),
                "--source-root", str(PLAN / "config"), "--output-root", str(root / "accept-source")],
                text=True, capture_output=True)
            self.assertEqual(acceptance.returncode, 0, acceptance.stderr)
            self.assertEqual((root / "config/.service-ports.json").read_bytes(), saved)
            self.assertEqual((root / "staged/gpt-gateway-topology.json").read_bytes(),
                             (root / "accept-source/gpt-gateway-topology.json").read_bytes())

    def test_dashboard_generator_emits_plan_port_markers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "config").mkdir()
            result = subprocess.run([sys.executable, str(ROOT / "observability/ns2604_dashboards.py"),
                                     "--plan-dir", str(root)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue("@PORT_AGENTSVIEW@" in (root / "config/grafana-command-center.json").read_text(),
                            "dashboard output lacks the host port marker")

    def test_custom_gateway_preserves_composition_wrapper_and_moves_its_unit(self):
        renderer = module(PLAN / "config/observability_config.py", "gateway_ports")
        ports = renderer.service_ports({"NS_PORT_GATEWAY": "31128"})
        wrapper = renderer.render_asset("omniroute-serve.sh", (PLAN / "config/omniroute-serve.sh").read_text(), ports)
        self.assertIn("serve --port 31128", wrapper)
        expected = hashlib.sha256(wrapper.encode()).hexdigest()
        command = renderer.render_command(
            "672063a12174d46f7065ae7bb9adf1ed268c958cd264f64a25d0af3f74ae45bc wrapper", ports)
        self.assertEqual(command, expected + " wrapper")
        unit = renderer.render_asset("omniroute.service", (PLAN / "config/omniroute.service").read_text(), ports)
        self.assertIn("Environment=PORT=31128\n", unit)
        self.assertNotIn("Environment=PORT=21128\n", unit)

    def test_checker_rejects_literal_service_ports(self):
        checker = module(PLAN / "check_plan.py", "literal_check")
        rows = json.loads((PLAN / "install-plan.json").read_text())["owners"]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "config").mkdir()
            (root / "config/observability_config.py").write_text((PLAN / "config/observability_config.py").read_text())
            for literal in ("21318", "32123"):
                (root / "config/rogue.yaml").write_text("endpoint: 127.0.0.1:" + literal + "\n")
                errors = []
                checker.host_port_contract(root, rows, None, lambda tag, msg: errors.append(msg))
                self.assertTrue(any("literal service port" in e for e in errors), errors)

    def test_command_render_swaps_ports_without_cascading(self):
        renderer = module(PLAN / "config/observability_config.py", "command_ports")
        ports = renderer.service_ports({"NS_PORT_GATEWAY": "21080", "NS_PORT_DAGU": "21128"})
        self.assertEqual(renderer.render_command("http://127.0.0.1:21128 http://127.0.0.1:21080 @PORT_DAGU@", ports),
                         "http://127.0.0.1:21080 http://127.0.0.1:21128 21128")

    def test_default_host_renders_the_baseline_config_bytes(self):
        renderer = module(PLAN / "config/observability_config.py", "plan_ports")
        host = json.loads((ROOT / "adoption/templates/wsl/host.new-distro.json.template").read_text())
        ports = renderer.service_ports(host)
        fixture = json.loads((ROOT / "tests/fixtures/install_plan_default_ports.json").read_text())
        for entry in fixture["files"]:
            name, expected = entry["path"], entry["sha256"]
            with self.subTest(config=name):
                rendered = renderer.render_ports((PLAN / "config" / name).read_text(), ports)
                self.assertEqual(hashlib.sha256(rendered.encode()).hexdigest(), expected)

    def test_host_ports_reach_collector_bindings_and_cross_service_targets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            host = root / "host.json"
            host.write_text(json.dumps({"NS_PORT_OTEL_HTTP": "31318", "NS_PORT_OTEL_GRPC": "31317",
                                        "NS_PORT_GATEWAY": "31128", "NS_PORT_LOKI_HTTP": "31300"}))
            out = root / "render"
            out.mkdir()
            result = subprocess.run([sys.executable, str(PLAN / "config/observability_config.py"), "otel",
                                     "--config-root", str(out), "--source-root", str(PLAN / "config"),
                                     "--host-file", str(host)], text=True, capture_output=True,
                                    env={"PATH": "/usr/bin:/bin", "HOME": tmp})
            self.assertEqual(result.returncode, 0, result.stderr)
            text = (out / "otel.yaml").read_text()
            for endpoint in ("127.0.0.1:31318", "127.0.0.1:31317", "127.0.0.1:31128/api/health",
                             "127.0.0.1:31300/otlp"):
                self.assertIn(endpoint, text)
            self.assertNotRegex(text, r"127\.0\.0\.1:(21318|21317|21128|21300)\b")

    def test_two_rows_cannot_claim_the_same_port(self):
        renderer = module(PLAN / "config/observability_config.py", "plan_ports")
        self.assertTrue(hasattr(renderer, "service_ports"), "plan has no host-port validation")
        with self.assertRaisesRegex(ValueError, "claimed"):
            renderer.service_ports({"NS_PORT_GATEWAY": "31080", "NS_PORT_DAGU": "31080"})


class CitationAuditTests(unittest.TestCase):
    def test_live_locators_and_dated_history_remain_distinct(self):
        audit = json.loads((PLAN / "no-start-citation-audit.json").read_text())
        for row in audit["locators"]:
            line = (PLAN / row["script"]).read_text().splitlines()[row["current_line"] - 1]
            self.assertEqual(hashlib.sha256(line.encode()).hexdigest(), row["anchor_sha256"])
        history = audit["dated_history"]
        self.assertEqual(hashlib.sha256((ROOT / history["path"]).read_bytes()).hexdigest(), history["sha256"])


if __name__ == "__main__":
    unittest.main()
