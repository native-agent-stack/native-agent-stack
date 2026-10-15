"""Install-plan regressions: extracted shell commands and disposable config fixtures only.

Never execute install.sh, accept.sh, installers, or the host's systemctl.
The baseline is native-agent-stack@8053f14e7; upstream mechanisms are cited in
the plan's NO_START_PORTS.md record.
"""
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

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


class ReviewWave1Tests(unittest.TestCase):
    def test_dagu_preserves_native_bootstrap_unless_no_start_is_selected(self):
        source = (PLAN / "install.sh").read_text()
        parser = "only=''" + source.split("only=''", 1)[1].split("\ndone\n", 1)[0] + "\ndone\n"
        for args, expected in (([], "yes"), (["--no-start"], "no")):
            result = subprocess.run(["bash", "-euo", "pipefail", "-c", parser + 'printf "%s" "$dagu_service_mode"',
                                     "fixture", *args], env={"PATH": "/usr/bin:/bin"}, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, expected)
        checker = module(PLAN / "check_plan.py", "wave_dagu_bootstrap")
        commands = checker.run_commands("dagu", checker.functions(source), set())
        self.assertLess(next(i for i, command in enumerate(commands) if "20-ns2604-coordinator.conf" in command),
                        next(i for i, command in enumerate(commands) if "scripts/installer.sh" in command))

    def test_checker_lists_the_transitive_docker_lifecycle(self):
        checker = module(PLAN / "check_plan.py", "wave_inventory")
        source = (PLAN / "install.sh").read_text()
        inventory = checker.transitive_service_inventory(checker.functions(source), source)
        self.assertEqual({entry["selected_row"] for entry in inventory},
                         {"docker-compose", "harbor-containerized-agent-e2e-runner"})
        for entry in inventory:
            self.assertEqual(entry["dependency"], "container-engine")
            self.assertEqual({step["kind"] for step in entry["steps"]},
                             {"package_install", "rootless_setup", "unit_registration", "activation"})

    def test_no_start_covers_both_docker_dependency_selections(self):
        checker = module(PLAN / "check_plan.py", "wave_dependency_check")
        reference = os.environ.get("NS_TEST_INSTALL_REF")
        source = (subprocess.check_output(["git", "show", reference + ":" + str((PLAN / "install.sh").relative_to(ROOT))],
                                         cwd=ROOT, text=True) if reference else (PLAN / "install.sh").read_text())
        functions = checker.functions(source)
        dependency_selection = next(line for line in source.splitlines()
                                    if line.startswith("for slot in ") and "needs_docker=true" in line)
        dependency_dispatch = re.search(
            r"^if \$needs_docker \|\| selected container-engine; then\n  run_slot container-engine\n.*?(?=^if \$needs_docker \|\| selected docker-compose;)",
            source, re.M | re.S)[0]
        cases = ((row, present) for row in ("docker-compose", "harbor-containerized-agent-e2e-runner")
                 for present in (False, True))
        for selected_row, existing in cases:
            with self.subTest(row=selected_row, existing=existing), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                unit = root / ".config/systemd/user/docker.service"
                if existing:
                    unit.parent.mkdir(parents=True)
                    unit.write_text("fixture pre-existing unit\n")
                names = ("selected", "copy_config", "run_command", "activate_user_unit", "register_service_row",
                         "container-engine", "docker_engine_packages", "run_slot")
                definitions = "\n".join(name + "() {\n" + functions[name] + "\n}" for name in names if name in functions)
                script = definitions + '\n' + (
                    'systemctl() { printf "CALL %s\\n" "$*"; };\n'
                    'sudo() { printf "ROOT %s\\n" "$*"; '
                    'if [[ "$*" == "systemctl mask docker.service docker.socket containerd.service" ]]; then '
                    ': > "$HOME/.package-units-masked"; '
                    'elif [[ "$1" == apt-get && ! -f "$HOME/.package-units-masked" ]]; then printf "PACKAGE_START\\n"; fi; };\n'
                    'docker_repository() { :; }; apt_release_version() { printf fixture; };\n'
                    'dockerd-rootless-setuptool.sh() { printf "SETUP\\n"; mkdir -p "$HOME/.config/systemd/user"; '
                    'printf "fixture setup unit\\n" > "$HOME/.config/systemd/user/docker.service"; };\n'
                    'export -f systemctl sudo docker_repository docker_engine_packages apt_release_version dockerd-rootless-setuptool.sh\n'
                    'if declare -F activate_user_unit >/dev/null; then export -f activate_user_unit; fi\n'
                    'needs_docker=false; failed=0; last_rc=0\n'
                ) + 'only=' + shlex.quote(selected_row) + '\n' + dependency_selection + '\n' + dependency_dispatch
                result = subprocess.run(["bash", "-euo", "pipefail", "-c", script], text=True, capture_output=True,
                    env={"PATH": "/usr/bin:/bin", "HOME": tmp, "XDG_RUNTIME_DIR": str(root / "run"),
                         "NS2604_NO_START": "1", "plan_dir": str(PLAN), "config_root": str(root / "config"),
                         "config_source_root": str(PLAN / "config"), "tool_root": str(root / "tools")})
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("container-engine | install | 0", result.stdout)
                self.assertIn("ROOT apt-get install", result.stdout)
                self.assertNotRegex(result.stdout, r"\b(enable|start|restart|SETUP|PACKAGE_START)\b")
                self.assertIn("CALL --user daemon-reload", result.stdout)
                self.assertTrue(unit.is_file())

    def test_native_research_command_carries_the_host_file_explicitly(self):
        checker = module(PLAN / "check_plan.py", "wave_native_research")
        body = checker.functions((PLAN / "accept.sh").read_text())["research-harnesses"]
        program = next(p for stage, _, _, p in checker.checks_of(body) if stage == "after_sign_in")
        assignment = next(line for line in program.splitlines() if "printf -v gpt_command " in line)
        with tempfile.TemporaryDirectory() as tmp:
            host = str(Path(tmp) / "host values.json")
            result = subprocess.run(["bash", "-euo", "pipefail", "-c", assignment + '\nprintf "%s" "$gpt_command"'],
                text=True, capture_output=True, env={"PATH": "/usr/bin:/bin", "client_state": tmp,
                    "repo_root": str(ROOT), "NS2604_HOST_FILE": host, "gpt_marker": "fixture-complete"})
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("NS2604_HOST_FILE=" + host, shlex.split(result.stdout))

    def test_plan_rejects_a_foreign_listener_in_a_supplied_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            host, snapshot = root / "host.json", root / "ss.txt"
            snapshot.write_text("LISTEN 0 128 127.0.0.1:21128 0.0.0.0:*\n")
            for moved in (False, True):
                host.write_text(json.dumps({"NS_PORT_GATEWAY": "31128"} if moved else {}))
                result = subprocess.run([sys.executable, str(PLAN / "check_plan.py"), "--host-file", str(host),
                                         "--ss-output", str(snapshot)], text=True, capture_output=True)
                self.assertEqual(result.returncode, 0 if moved else 1, result.stderr)
                if not moved:
                    self.assertIn("21128 foreign", result.stdout)

    def test_cited_acceptance_programs_use_host_ports(self):
        renderer = module(PLAN / "config/observability_config.py", "wave_accept_ports")
        checker = module(PLAN / "check_plan.py", "wave_accept_check")
        functions = checker.functions((PLAN / "accept.sh").read_text())
        ports = renderer.service_ports({"NS_PORT_MEMORY": "39374", "NS_PORT_ALERTMANAGER": "31093",
                                        "NS_PORT_PROMETHEUS": "31090", "NS_PORT_GATEWAY": "31128"})
        for slot, stage, expected in (("memory-owner", "service_health", "39374"),
                                      ("alerting", "service_health", "31093"),
                                      ("alerting", "after_sign_in", "31090"),
                                      ("gpt-gateway", "service_health", "31128"),
                                      ("research-harnesses", "post_install", "31128")):
            with self.subTest(slot=slot, stage=stage):
                program = next(p for s, _, _, p in checker.checks_of(functions[slot]) if s == stage)
                rendered = renderer.render_command(program, ports)
                self.assertIn("127.0.0.1:" + expected, rendered)
                self.assertNotRegex(rendered, r"127\.0\.0\.1:(29374|21093|21090|21128)\b")

    def test_all_gateway_listeners_move_and_require_visible_owners(self):
        renderer = module(PLAN / "config/observability_config.py", "wave_ws_ports")
        ports = renderer.service_ports({"NS_PORT_GATEWAY": "41128", "NS_PORT_GATEWAY_WS": "41129",
                                        "NS_PORT_GATEWAY_EMBED_WS": "41131"})
        unit = renderer.render_ports((PLAN / "config/omniroute.service").read_text(), ports)
        self.assertIn("Environment=PORT=41128\n", unit)
        self.assertIn("Environment=LIVE_WS_PORT=41129\n", unit)
        self.assertIn("Environment=EMBED_WS_PROXY_PORT=41131\n", unit)
        plan = json.loads((PLAN / "install-plan.json").read_text())
        expected = renderer.planned_listeners(plan, ports, "gpt-gateway")
        self.assertEqual(set(expected), {41128, 41129, 41131})
        owned = lambda port: f'LISTEN 0 128 127.0.0.1:{port} 0.0.0.0:* users:(("fixture",pid=42,fd=3))\n'
        self.assertEqual(renderer.listener_ownership(plan, ports, "".join(owned(p) for p in expected), "gpt-gateway"), [])
        errors = renderer.listener_ownership(plan, ports, owned(41128) + "LISTEN 0 128 127.0.0.1:41129 0.0.0.0:*\n", "gpt-gateway")
        self.assertTrue(any("41129 foreign" in error for error in errors))
        self.assertTrue(any("41131 absent" in error for error in errors))
        with self.assertRaisesRegex(ValueError, "claimed"):
            renderer.service_ports({"NS_PORT_GATEWAY_WS": "41129", "NS_PORT_DAGU": "41129"})

    def test_default_stage_s_enumerates_fifteen_planned_listeners(self):
        renderer = module(PLAN / "config/observability_config.py", "wave_all_ports")
        plan = json.loads((PLAN / "install-plan.json").read_text())
        self.assertEqual(len(renderer.planned_listeners(plan, renderer.service_ports())), 15)

    def test_foreign_listener_stops_the_acceptance_program(self):
        checker = module(PLAN / "check_plan.py", "wave_gate_check")
        body = checker.functions((PLAN / "accept.sh").read_text())["check"]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "bin").mkdir()
            (root / "config").mkdir()
            sudo = root / "bin/sudo"
            sudo.write_text('#!/bin/sh\n[ "$*" = "ss -ltnpH" ] || exit 99\nprintf "%s\\n" "LISTEN 0 128 127.0.0.1:29374 0.0.0.0:*"\n')
            sudo.chmod(0o755)
            script = ('stage=service_health; failed=0; port_args=(); prepare_path() { :; };\ncheck() {\n'
                      + body + '\n}\ncheck memory-owner health ' + shlex.quote('touch "$config_root/probe-ran"')
                      + '\nexit "$failed"')
            result = subprocess.run(["bash", "-euo", "pipefail", "-c", script], text=True, capture_output=True,
                env={"PATH": str(root / "bin") + ":/usr/bin:/bin", "plan_dir": str(PLAN),
                     "config_root": str(root / "config"), "config_source_root": str(root / "config")})
            self.assertEqual(result.returncode, 1)
            self.assertIn("foreign", result.stderr)
            self.assertFalse((root / "config/probe-ran").exists())

    def test_runtime_profiles_reads_the_host_gateway(self):
        with tempfile.TemporaryDirectory() as tmp:
            host = Path(tmp) / "host.json"
            host.write_text(json.dumps({"NS_PORT_GATEWAY": "41128"}))
            with mock.patch.dict(os.environ, {"NS2604_HOST_FILE": str(host)}):
                profiles = module(ROOT / "tools/adoption/runtime_profiles.py", "wave_runtime_profiles")
            self.assertEqual(profiles.GATEWAY, "http://127.0.0.1:41128/v1")

    def test_research_helper_uses_the_host_gateway_before_scrubbing(self):
        from tests import test_research_entry
        fixture = test_research_entry.ResearchEntry()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.provide_timer()
        host = fixture.temp / "host.json"
        host.write_text(json.dumps({"NS_PORT_GATEWAY": "41128"}))
        fixture.env["NS2604_HOST_FILE"] = str(host)
        result = fixture.run_script("fixture research query")
        self.assertEqual(result.returncode, 0, result.stderr)
        run = fixture.run_dir(result)
        self.assertEqual(json.loads((run / "config.json").read_text())["LLM_KWARGS"]["base_url"],
                         "http://127.0.0.1:41128/v1")
        self.assertEqual(json.loads((run / "cli-call.json").read_text())["env"]["OPENAI_BASE_URL"],
                         "http://127.0.0.1:41128/v1")

    def ownership(self, text):
        renderer = module(PLAN / "config/observability_config.py", "listener_ports")
        self.assertTrue(hasattr(renderer, "listener_ownership"), "stage-S ownership gate is absent")
        plan = json.loads((PLAN / "install-plan.json").read_text())
        ports = renderer.service_ports({"NS_PORT_MEMORY": "39374"})
        return renderer.listener_ownership(plan, ports, text, slot="memory-owner")

    def test_owned_listener_has_visible_process(self):
        self.assertEqual(self.ownership('LISTEN 0 128 127.0.0.1:39374 0.0.0.0:* users:(("ai-memory",pid=42,fd=3))\n'), [])

    def test_foreign_listener_is_rejected(self):
        self.assertTrue(any("foreign" in error for error in self.ownership('LISTEN 0 128 127.0.0.1:39374 0.0.0.0:*\n')))

    def test_absent_listener_is_rejected(self):
        self.assertTrue(any("absent" in error for error in self.ownership('LISTEN 0 128 127.0.0.1:49374 0.0.0.0:* users:(("other",pid=42,fd=3))\n')))


if __name__ == "__main__":
    unittest.main()
