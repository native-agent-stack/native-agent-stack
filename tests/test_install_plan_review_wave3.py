"""PR1180 review_output.json regressions: renderers and extracted helpers only."""
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

    def test_unrelated_selected_row_keeps_unselected_gateway_allocation(self):
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
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads((root / "config/.service-ports.json").read_text()), previous)

    def test_selected_memory_config_keeps_references_to_the_installed_gateway(self):
        _, funcs = self.functions()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "config").mkdir()
            (root / "config/.service-ports.json").write_text(json.dumps(host_allocation({"NS_PORT_GATEWAY": "31128"})))
            (root / "B.json").write_text(json.dumps(host_allocation({"NS_PORT_MEMORY": "39374", "NS_PORT_GATEWAY": "41128"})))
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

    def test_default_selection_preserves_measurement_only_ports_and_detects_merged_collisions(self):
        renderer = module(PLAN / "config/observability_config.py", "wave3_selection")
        plan = json.loads((PLAN / "install-plan.json").read_text())
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".service-ports.json").write_text(json.dumps(host_allocation({"NS_PORT_GATEWAY": "31128"})))
            candidate = renderer.service_ports({"NS_PORT_GRAFANA_HTTP": "31301"})
            self.assertEqual(renderer.installation_ports(candidate, root, plan)["GRAFANA_HTTP"], 21301)
            candidate = renderer.service_ports({"NS_PORT_MEMORY": "31128", "NS_PORT_GATEWAY": "41128"})
            with self.assertRaisesRegex(ValueError, "claimed"):
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

    def test_prometheus_render_provisions_its_unit_working_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = self.render("prometheus", root)
            self.assertEqual(result.returncode, 0, result.stderr)
            unit = (root / "config/ns2604-prometheus.service").read_text()
            directory = Path(re.search(r"(?m)^WorkingDirectory=(.+)$", unit)[1])
            self.assertEqual(directory, root / "data/prometheus")
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


if __name__ == "__main__":
    unittest.main()
