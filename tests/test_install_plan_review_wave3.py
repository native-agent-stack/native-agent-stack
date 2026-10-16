"""PR1180 review_output.json regressions: renderers and extracted helpers only."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

from tests.test_install_plan_no_start_ports import ROOT, PLAN, host_allocation, module


class ReviewWave3Tests(unittest.TestCase):
    def functions(self):
        checker = module(PLAN / "check_plan.py", "wave3_checker")
        return checker, checker.functions((PLAN / "install.sh").read_text())

    def render(self, action, root, renderer=None, source=None):
        return subprocess.run([sys.executable, str(renderer or PLAN / "config/observability_config.py"), action,
            "--config-root", str(root / "config"), "--source-root", str(source or PLAN / "config"),
            "--tools-root", str(root / "tools"), "--plan-file", str(PLAN / "install-plan.json"),
            "--repo-root", str(ROOT)],
            env={"PATH": "/usr/bin:/bin", "HOME": str(root), "NS2604_OBSERVABILITY_DATA": str(root / "data")},
            text=True, capture_output=True)

    def test_grafana_rerun_accepts_its_rendered_ledger_owned_configuration(self):
        _, funcs = self.functions()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            initial = self.render("grafana", root)
            self.assertEqual(initial.returncode, 0, initial.stderr)
            before = (root / "config/grafana.ini").read_text()
            self.assertNotIn("@CONFIG_ROOT@", before)
            body = 'copy_config() {\n' + funcs["copy_config"] + '\n}\ncopy_config grafana.ini'
            result = subprocess.run(["bash", "-euo", "pipefail", "-c", body],
                env={"PATH": "/usr/bin:/bin", "HOME": tmp, "plan_dir": str(PLAN),
                     "config_source_root": str(PLAN / "config"), "config_root": str(root / "config")},
                text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            rerun = self.render("grafana", root)
            self.assertEqual(rerun.returncode, 0, rerun.stderr)
            self.assertEqual((root / "config/grafana.ini").read_text(), before)

    def test_grafana_upgrade_accepts_the_base_branch_writers_ledger(self):
        _, funcs = self.functions()
        renderer = module(PLAN / "config/observability_config.py", "wave3_base_templates")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "baseline-source"
            source.mkdir()
            base = "8053f14e7:evidence/artifacts/new-wsl-install-plan-20261002/config/"
            for name in ["observability_config.py", *(name for name, _ in renderer.GRAFANA_FILES)]:
                raw = subprocess.check_output(["git", "show", base + name], cwd=ROOT)
                (source / name).write_bytes(raw)
            initial = self.render("grafana", root, source / "observability_config.py", source)
            self.assertEqual(initial.returncode, 0, initial.stderr)
            original = (root / "config/grafana.ini").read_text()
            body = 'copy_config() {\n' + funcs["copy_config"] + '\n}\ncopy_config grafana.ini'
            copy = subprocess.run(["bash", "-euo", "pipefail", "-c", body],
                env={"PATH": "/usr/bin:/bin", "HOME": tmp, "plan_dir": str(PLAN),
                     "config_source_root": str(PLAN / "config"), "config_root": str(root / "config")},
                text=True, capture_output=True)
            self.assertEqual(copy.returncode, 0, copy.stderr)
            upgrade = self.render("grafana", root)
            self.assertEqual(upgrade.returncode, 0, upgrade.stderr)
            self.assertEqual((root / "config/grafana.ini").read_text(), original)

    def test_unrelated_selected_row_refuses_a_conflicting_gateway_request(self):
        _, funcs = self.functions()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "config").mkdir()
            previous = host_allocation({"NS_PORT_GATEWAY": "31128"})
            (root / "config/.service-ports.json").write_text(json.dumps(previous))
            (root / "B.json").write_text(json.dumps(host_allocation({"NS_PORT_GATEWAY": "41128"})))
            names = ("stage_plan_sources", "commit_allocation")
            body = '\n'.join(name + '() {\n' + funcs[name] + '\n}' for name in names)
            body += '\nstage_plan_sources\nfailed=0; needs_execution=true; commit_allocation\n'
            result = subprocess.run(["bash", "-euo", "pipefail", "-c", body],
                env={"PATH": "/usr/bin:/bin", "HOME": tmp, "plan_dir": str(PLAN),
                     "only": "structured-data", "host_file": str(root / "B.json"),
                     "config_root": str(root / "config")}, text=True, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("unselected", result.stderr)
            self.assertEqual(json.loads((root / "config/.service-ports.json").read_text()), previous)

    def test_selected_memory_config_keeps_references_to_the_installed_gateway(self):
        _, funcs = self.functions()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "config").mkdir()
            (root / "config/.service-ports.json").write_text(json.dumps(host_allocation({"NS_PORT_GATEWAY": "31128"})))
            (root / "B.json").write_text(json.dumps(host_allocation({"NS_PORT_MEMORY": "39374", "NS_PORT_GATEWAY": "31128"})))
            names = ("stage_plan_sources", "commit_allocation", "run_command")
            body = '\n'.join(name + '() {\n' + funcs[name] + '\n}' for name in names)
            body += ('\nstage_plan_sources\n'
                     'run_command \'printf "%s\\n" http://127.0.0.1:21128/v1\'\n'
                     'failed=0; needs_execution=true; commit_allocation\n')
            result = subprocess.run(["bash", "-euo", "pipefail", "-c", body],
                env={"PATH": "/usr/bin:/bin", "HOME": tmp, "plan_dir": str(PLAN),
                     "only": "memory-owner", "host_file": str(root / "B.json"),
                     "config_root": str(root / "config")}, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "http://127.0.0.1:31128/v1")
            active = json.loads((root / "config/.service-ports.json").read_text())
            self.assertEqual(active["NS_PORT_MEMORY"], "39374")
            self.assertEqual(active["NS_PORT_GATEWAY"], "31128")

    def test_default_selection_refuses_changes_to_unselected_owners(self):
        renderer = module(PLAN / "config/observability_config.py", "wave3_selection")
        plan = json.loads((PLAN / "install-plan.json").read_text())
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".service-ports.json").write_text(json.dumps(host_allocation({"NS_PORT_GATEWAY": "31128"})))
            candidate = renderer.service_ports({"NS_PORT_GRAFANA_HTTP": "31301"})
            with self.assertRaisesRegex(ValueError, "unselected"):
                renderer.installation_ports(candidate, root, plan)
            candidate = renderer.service_ports({"NS_PORT_MEMORY": "31128", "NS_PORT_GATEWAY": "41128"})
            with self.assertRaisesRegex(ValueError, "unselected"):
                renderer.installation_ports(candidate, root, plan, "memory-owner")

    def test_grafana_rerun_still_refuses_an_operator_modified_render(self):
        _, funcs = self.functions()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(self.render("grafana", root).returncode, 0)
            target = root / "config/grafana.ini"
            changed = target.read_text().replace("http_port = 21301", "http_port = 31301")
            self.assertNotEqual(target.read_text(), changed)
            target.write_text(changed)
            body = 'copy_config() {\n' + funcs["copy_config"] + '\n}\ncopy_config grafana.ini'
            subprocess.run(["bash", "-euo", "pipefail", "-c", body], check=True,
                env={"PATH": "/usr/bin:/bin", "HOME": tmp, "plan_dir": str(PLAN),
                     "config_source_root": str(PLAN / "config"), "config_root": str(root / "config")})
            result = self.render("grafana", root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("needs_owner", result.stderr)
            self.assertEqual(target.read_text(), changed)

    def test_dagu_no_start_refuses_an_existing_unit_with_another_port(self):
        checker, funcs = self.functions()
        command = next(c for c in checker.run_commands("dagu", funcs, set())
                       if 'if [[ "$NS2604_NO_START" == 1' in c)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            units = root / ".config/systemd/user"
            units.mkdir(parents=True)
            old = "[Service]\nEnvironment=DAGU_PORT=21080\n"
            (units / "dagu.service").write_text(old)
            (root / "config").mkdir()
            (root / "config/dagu.service").write_text("[Service]\nEnvironment=DAGU_PORT=31080\n")
            result = subprocess.run(["bash", "-euo", "pipefail", "-c",
                                     'systemctl() { printf "FAKE %s\\n" "$*"; };\n' + command],
                env={"PATH": "/usr/bin:/bin", "HOME": tmp, "config_root": str(root / "config"),
                     "NS2604_NO_START": "1"}, text=True, capture_output=True)
            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertIn("needs_owner", result.stderr)
            self.assertEqual((units / "dagu.service").read_text(), old)
            self.assertNotIn("enable", result.stdout)
            self.assertNotIn("start", result.stdout)

    def test_prometheus_registration_provisions_its_unit_working_directory(self):
        _, funcs = self.functions()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = self.render("prometheus", root)
            self.assertEqual(result.returncode, 0, result.stderr)
            unit = (root / "config/ns2604-prometheus.service").read_text()
            directory = Path(re.search(r"(?m)^WorkingDirectory=(.+)$", unit)[1])
            self.assertEqual(directory, root / "data/prometheus")
            self.assertFalse(directory.exists(), "standalone unit rendering must not provision runtime state")
            script = ('systemctl() { printf "FAKE %s\\n" "$*"; };\nregister_service_row() {\n'
                      + funcs["register_service_row"] + '\n}\nregister_service_row prometheus')
            registered = subprocess.run(["bash", "-euo", "pipefail", "-c", script],
                env={"PATH": "/usr/bin:/bin", "HOME": tmp, "config_root": str(root / "config"),
                     "NS2604_OBSERVABILITY_DATA": str(root / "data"), "NS2604_NO_START": "1"},
                text=True, capture_output=True)
            self.assertEqual(registered.returncode, 0, registered.stderr)
            self.assertEqual(registered.stdout.strip(), "FAKE --user daemon-reload")
            self.assertTrue(directory.is_dir(), unit)

    def test_dagu_no_start_retains_matching_units_but_refuses_unknown_environment_dropins(self):
        checker, funcs = self.functions()
        command = next(c for c in checker.run_commands("dagu", funcs, set())
                       if 'if [[ "$NS2604_NO_START" == 1' in c)
        for extra in (False, True):
            with self.subTest(extra=extra), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                units = root / ".config/systemd/user"
                (units / "dagu.service.d").mkdir(parents=True)
                (root / "config").mkdir()
                content = "[Service]\nEnvironment=DAGU_PORT=31080\n"
                for target in (units / "dagu.service", root / "config/dagu.service"):
                    target.write_text(content)
                if extra:
                    (units / "dagu.service.d/90-operator.conf").write_text("[Service]\nEnvironment=DAGU_PORT=21080\n")
                result = subprocess.run(["bash", "-euo", "pipefail", "-c",
                                         'systemctl() { printf "FAKE %s\\n" "$*"; };\n' + command],
                    env={"PATH": "/usr/bin:/bin", "HOME": tmp, "config_root": str(root / "config"),
                         "NS2604_NO_START": "1"}, text=True, capture_output=True)
                if extra:
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("needs_owner", result.stderr)
                else:
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stdout.strip(), "FAKE --user daemon-reload")
                self.assertEqual((units / "dagu.service").read_text(), content)


class ReviewWave4DocumentationTests(unittest.TestCase):
    def test_live_recipe_and_handbook_use_the_explicit_host_for_no_start(self):
        for name in ("adoption/platforms/linux-wsl2-new-distro.md", "docs/new-wsl-handbook.md"):
            with self.subTest(path=name):
                text = (ROOT / name).read_text()
                self.assertTrue("install.sh --no-start --host-file 'adoption/hosts/<host>.json'" in text, name)
                self.assertTrue("accept.sh --host-file 'adoption/hosts/<host>.json'" in text, name)

    def test_checklist_requires_complete_allocations_and_host_identity(self):
        text = (ROOT / "adoption/templates/wsl/first-boot-checklist.md").read_text()
        f8 = next(line for line in text.splitlines() if line.startswith("- [ ] **F8**"))
        self.assertIn("NS_PORT_*", f8)
        self.assertIn("WSL_DISTRO_NAME", f8)
        self.assertNotIn("four ports", f8)
        self.assertNotIn("nine keys", f8)

    def test_addendum_supersedes_both_decisions_without_rewriting_them(self):
        addendum = ROOT / "docs/decisions/2026-10-16-new-wsl-host-allocation-addendum.md"
        self.assertTrue(addendum.is_file())
        text = addendum.read_text()
        # Frozen public bytes at main8053f14e7, also retained in the scope receipt.
        # A squash checkout/export need not retain any PR-only commit objects.
        frozen = {
            "2026-10-01-new-wsl-distro-recipe.md": "8df3f18af352be4f1dd1a2a2dc5a4d718804582b8a6281e6d461dddd73e2647c",
            "2026-10-02-new-wsl-client-configuration.md": "be8a467cd2070d715a820213ab47fd35c49d727fdb7dabd1f4f01b1cbec7c5ef",
        }
        for name, digest in frozen.items():
            self.assertIn(name, text)
            path = "docs/decisions/" + name
            self.assertEqual(hashlib.sha256((ROOT / path).read_bytes()).hexdigest(), digest)
        self.assertIn("WSL_DISTRO_NAME", text)
        self.assertIn("Supersedes", text)


class ReviewWave4RuntimeTests(unittest.TestCase):
    def test_publication_refuses_a_snapshot_changed_after_staging(self):
        renderer = module(PLAN / "config/observability_config.py", "wave4_concurrent_allocation")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config, staged = root / "config", root / "staged"
            config.mkdir()
            active = config / ".service-ports.json"
            active.write_text(json.dumps(host_allocation({"NS_PORT_GATEWAY": "31128"})))
            host = root / "B.json"
            host.write_text(json.dumps(host_allocation({"NS_PORT_MEMORY": "39374", "NS_PORT_GATEWAY": "31128"})))
            command = [sys.executable, str(PLAN / "config/observability_config.py")]
            env = {"PATH": "/usr/bin:/bin", "HOME": tmp}
            stage = subprocess.run(command + ["stage", "--config-root", str(config), "--output-root", str(staged),
                "--source-root", str(PLAN / "config"), "--host-file", str(host), "--plan-file", str(PLAN / "install-plan.json"),
                "--slot", "memory-owner"], env=env, text=True, capture_output=True)
            self.assertEqual(stage.returncode, 0, stage.stderr)
            later = json.dumps(host_allocation({"NS_PORT_GATEWAY": "51128"}))
            active.write_text(later)
            commit = subprocess.run(command + ["commit-ports", "--config-root", str(config),
                "--host-file", str(staged / ".service-ports.json"), "--plan-file", str(PLAN / "install-plan.json"),
                "--slot", "memory-owner"], env=env, text=True, capture_output=True)
            self.assertNotEqual(commit.returncode, 0)
            self.assertIn("changed", commit.stderr)
            self.assertEqual(active.read_text(), later)

    def test_dagu_preflight_preserves_all_assets_before_any_reload(self):
        checker = module(PLAN / "check_plan.py", "wave4_dagu_sequence")
        funcs = checker.functions((PLAN / "install.sh").read_text())
        commands = checker.run_commands("dagu", funcs, set())
        selected = [c for c in commands if "installer.sh" not in c]
        script = 'systemctl() { printf "RELOAD %s\\n" "$*"; };\n' + '\n'.join(selected)
        for filename in ("20-ns2604-coordinator.conf", "90-operator.conf"):
            with self.subTest(filename=filename), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                config = root / "config"
                config.mkdir()
                unit = "[Service]\nEnvironment=DAGU_PORT=21080\n"
                coordinator = "[Service]\nEnvironment=DAGU_COORDINATOR_PORT=50055\n"
                for name, text in (("dagu.service", unit), ("dagu-coordinator.conf", coordinator)):
                    (config / name).write_text(text)
                units = root / ".config/systemd/user"
                (units / "dagu.service.d").mkdir(parents=True)
                (units / "dagu.service").write_text(unit)
                target = units / "dagu.service.d" / filename
                original = "[Service]\nEnvironment=DAGU_PORT=31080\n"
                target.write_text(original)
                result = subprocess.run(["bash", "-euo", "pipefail", "-c", script],
                    env={"PATH": "/usr/bin:/bin", "HOME": tmp, "config_root": str(config), "plan_dir": tmp,
                         "NS2604_NO_START": "1"}, text=True, capture_output=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("needs_owner", result.stderr)
                self.assertEqual(target.read_text(), original)
                self.assertNotIn("RELOAD", result.stdout)
                if filename != "20-ns2604-coordinator.conf":
                    self.assertFalse((units / "dagu.service.d/20-ns2604-coordinator.conf").exists())

    def test_promptfoo_default_export_matches_unchanged_base_source(self):
        renderer = module(PLAN / "config/observability_config.py", "wave4_promptfoo_default")
        topology = {"gateway": {"endpoint": "http://127.0.0.1:21128/v1"},
                    "pool_fallback": {"model": "fixture/gpt", "model_reasoning_effort": "max"},
                    "promptfoo": {"claude_model": "fixture/claude"}}
        original = subprocess.check_output(["git", "show", "8053f14e7:evidence/artifacts/new-wsl-install-plan-20261002/config/promptfoo-gateway.cjs"], cwd=ROOT, text=True)
        current = renderer.render_ports((PLAN / "config/promptfoo-gateway.cjs").read_text(), renderer.service_ports())
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "gpt-gateway-topology.json").write_text(json.dumps(topology))
            outputs = []
            for name, text in (("before.cjs", original), ("after.cjs", current)):
                (root / name).write_text(text)
                result = subprocess.run(["node", "-e", "process.stdout.write(JSON.stringify(require(process.argv[1])));", str(root / name)], text=True, capture_output=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                outputs.append(result.stdout)
            self.assertEqual(*outputs)

    def test_first_snapshot_refuses_unknown_unselected_installed_allocations(self):
        renderer = module(PLAN / "config/observability_config.py", "wave4_first_snapshot")
        plan = json.loads((PLAN / "install-plan.json").read_text())
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "omniroute.service").write_text("[Service]\nEnvironment=PORT=21128\n")
            candidate = renderer.service_ports({"NS_PORT_GATEWAY": "41128"})
            with self.assertRaisesRegex(ValueError, "needs_owner"):
                renderer.installation_ports(candidate, root, plan, "code-graph")

    def test_dagu_coordinator_refuses_operator_bytes_before_any_write(self):
        checker = module(PLAN / "check_plan.py", "wave4_dagu_custody")
        funcs = checker.functions((PLAN / "install.sh").read_text())
        command = next(c for c in checker.run_commands("dagu", funcs, set()) if '20-ns2604-coordinator.conf' in c and 'if [[ "$NS2604_NO_START"' not in c)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "config").mkdir()
            (root / "config/dagu-coordinator.conf").write_text("[Service]\nEnvironment=DAGU_COORDINATOR_PORT=50055\n")
            target = root / ".config/systemd/user/dagu.service.d/20-ns2604-coordinator.conf"
            target.parent.mkdir(parents=True)
            original = "[Service]\nEnvironment=DAGU_COORDINATOR_PORT=35055\n"
            target.write_text(original)
            result = subprocess.run(["bash", "-euo", "pipefail", "-c", 'systemctl() { :; };\n' + command],
                env={"PATH": "/usr/bin:/bin", "HOME": tmp, "config_root": str(root / "config"), "plan_dir": tmp, "NS2604_NO_START": "1"},
                text=True, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("needs_owner", result.stderr)
            self.assertEqual(target.read_text(), original)

    def test_promptfoo_accepts_the_effective_default_http_port(self):
        import shutil
        node = shutil.which("node")
        if node is None:
            self.skipTest("node is required for the native URL parser fixture")
        renderer = module(PLAN / "config/observability_config.py", "wave4_promptfoo_ports")
        ports = renderer.service_ports({"NS_PORT_GATEWAY": "80"})
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("promptfoo-gateway.cjs", "gpt-gateway-topology.json"):
                (root / name).write_text(renderer.render_ports((PLAN / "config" / name).read_text(), ports))
            topology = json.loads((root / "gpt-gateway-topology.json").read_text())
            topology["promptfoo"] = {"claude_model": "fixture/claude-route"}
            (root / "gpt-gateway-topology.json").write_text(json.dumps(topology))
            result = subprocess.run([node, "-e", "require(process.argv[1]);", str(root / "promptfoo-gateway.cjs")], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            checker = module(PLAN / "check_plan.py", "wave4_promptfoo_acceptance")
            body = checker.functions((PLAN / "accept.sh").read_text())["promptfoo"]
            program = next(p for stage, _, _, p in checker.checks_of(body) if stage == "after_sign_in")
            js = program.split("<<'JS'\n", 1)[1].split("\nJS", 1)[0]
            result = subprocess.run([node, "-", str(root / "gpt-gateway-topology.json")],
                input=renderer.render_command(js, ports), text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
