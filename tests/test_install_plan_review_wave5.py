"""PR1180 review_output.json regressions; staged fixtures and fake commands only."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from tests.test_install_plan_no_start_ports import ROOT, PLAN, host_allocation, module


class PortlessInstallFlowTests(unittest.TestCase):
    def renderer(self, root, action, slot, host, stage=None):
        command = [sys.executable, str(PLAN / "config/observability_config.py"), action,
                   "--config-root", str(root / "config"), "--source-root", str(PLAN / "config"),
                   "--plan-file", str(PLAN / "install-plan.json"), "--slot", slot,
                   "--host-file", str(host)]
        if stage is not None:
            command += ["--output-root", str(stage)]
        return subprocess.run(command, env={"PATH": "/usr/bin:/bin", "HOME": str(root)},
                              text=True, capture_output=True)

    def test_portless_provisioning_allows_rerun_and_later_listener_install(self):
        checker = module(PLAN / "check_plan.py", "wave5_portless_checker")
        funcs = checker.functions((PLAN / "install.sh").read_text())
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            host = root / "host.json"
            host.write_text(json.dumps(host_allocation()))
            stage = root / "first"
            result = self.renderer(root, "stage", "container-engine", host, stage)
            self.assertEqual(result.returncode, 0, result.stderr)
            # The actual copy seam provisions only the inert Docker config template.
            copy = 'copy_config() {\n' + funcs["copy_config"] + '\n}\ncopy_config docker.service'
            result = subprocess.run(["bash", "-euo", "pipefail", "-c", copy],
                env={"PATH": "/usr/bin:/bin", "HOME": tmp, "plan_dir": str(PLAN),
                     "config_source_root": str(stage), "config_root": str(root / "config")},
                text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = self.renderer(root, "commit-ports", "container-engine", stage / ".service-ports.json")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((root / "config/.service-ports.json").exists(),
                             "portless installation must not claim unselected listener allocations")
            result = self.renderer(root, "stage", "container-engine", host, root / "rerun")
            self.assertEqual(result.returncode, 0, result.stderr)
            host.write_text(json.dumps(host_allocation({"NS_PORT_MEMORY": "39374"})))
            result = self.renderer(root, "stage", "memory-owner", host, root / "memory")
            self.assertEqual(result.returncode, 0, result.stderr)
            result = self.renderer(root, "commit-ports", "memory-owner", root / "memory/.service-ports.json")
            self.assertEqual(result.returncode, 0, result.stderr)
            active = json.loads((root / "config/.service-ports.json").read_text())
            self.assertEqual(active["NS_PORT_MEMORY"], "39374")
            self.assertEqual((root / "config/docker.service").read_bytes(),
                             (PLAN / "config/docker.service").read_bytes())


    def test_known_portless_copies_include_renamed_worker_and_research_assets(self):
        from tests.test_install_plan_no_start_ports import ROOT
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            host = root / "host.json"
            host.write_text(json.dumps(host_allocation()))
            staged = root / "portless-stage"
            result = self.renderer(root, "stage", "agent-runtime-worker", host, staged)
            self.assertEqual(result.returncode, 0, result.stderr)
            config = root / "config"
            (config / "openhands").mkdir(parents=True)
            for target, source in (
                ("openhands/worker.py", staged / "openhands-worker.py"),
                ("openhands/job-template.json", staged / "openhands-job.json"),
                ("openhands/srt-template.json", staged / "openhands-srt.json"),
                ("gpt-researcher.sh", ROOT / "tools/research/gpt_researcher.sh"),
                ("gpt-researcher.config.json", ROOT / "tools/research/gpt-researcher.config.json"),
            ):
                (config / target).write_bytes(source.read_bytes())
            result = self.renderer(root, "stage", "memory-owner", host, root / "stage")
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_unknown_or_modified_configuration_still_requires_allocation_custody(self):
        for case in ("modified", "line-endings", "symlink", "root-symlink", "listener", "unknown"):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                config = root / "config"
                config.mkdir()
                docker = config / "docker.service"
                docker.write_bytes((PLAN / "config/docker.service").read_bytes())
                if case == "modified":
                    docker.write_text(docker.read_text() + "# operator change\n")
                elif case == "line-endings":
                    docker.write_bytes(docker.read_bytes().replace(b"\n", b"\r\n"))
                elif case == "symlink":
                    docker.unlink()
                    docker.symlink_to(PLAN / "config/docker.service")
                elif case == "root-symlink":
                    target = root / "linked-config"
                    config.rename(target)
                    config.symlink_to(target, target_is_directory=True)
                elif case == "listener":
                    (config / "omniroute.service").write_text("[Service]\nEnvironment=PORT=21128\n")
                else:
                    (config / "unknown.conf").write_text("operator bytes\n")
                host = root / "host.json"
                host.write_text(json.dumps(host_allocation()))
                result = self.renderer(root, "stage", "memory-owner", host, root / "stage")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("needs_owner", result.stderr)
                self.assertFalse((config / ".service-ports.json").exists())

    def test_declared_portless_runtime_state_does_not_establish_listener_ownership(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / "config/promptfoo-state"
            state.mkdir(parents=True)
            # Native state is opaque; staging must not decode or inspect its contents.
            (state / "fixture.sqlite").write_bytes(b"\x00\xfffixture-state")
            host = root / "host.json"
            host.write_text(json.dumps(host_allocation()))
            result = self.renderer(root, "stage", "memory-owner", host, root / "stage")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((root / "config/.service-ports.json").exists())
            (state / "link").symlink_to(state / "fixture.sqlite")
            result = self.renderer(root, "stage", "memory-owner", host, root / "symlink-stage")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("needs_owner", result.stderr)


class FailedFirstInstallTests(unittest.TestCase):
    def run_partial(self, root, finish=False):
        checker = module(PLAN / "check_plan.py", "wave5_first_attempt")
        funcs = checker.functions((PLAN / "install.sh").read_text())
        names = ("stage_plan_sources", "copy_config", "commit_allocation")
        script = '\n'.join(name + '() {\n' + funcs[name] + '\n}' for name in names)
        script += '\nstage_plan_sources\ncopy_config dagu.service\n'
        script += 'failed=0; needs_execution=true; commit_allocation' if finish else 'exit 37'
        return subprocess.run(["bash", "-euo", "pipefail", "-c", script],
            env={"PATH": "/usr/bin:/bin", "HOME": str(root), "plan_dir": str(PLAN),
                 "config_root": str(root / "config"), "host_file": str(root / "host.json"),
                 "only": "dagu", "NS2604_NO_START": "1"}, text=True, capture_output=True)

    def test_failed_first_install_retries_with_the_same_host_allocation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            values = host_allocation({"NS_PORT_DAGU": "31080"})
            (root / "host.json").write_text(json.dumps(values))
            failed = self.run_partial(root)
            self.assertEqual(failed.returncode, 37, failed.stderr)
            config = root / "config"
            self.assertTrue((config / "dagu.service").is_file())
            self.assertFalse((config / ".service-ports.json").exists())
            retry = self.run_partial(root, finish=True)
            self.assertEqual(retry.returncode, 0, retry.stderr)
            self.assertEqual(json.loads((config / ".service-ports.json").read_text()), values)
            self.assertFalse((config / ".service-ports.pending.json").exists())

    def test_failed_first_install_does_not_retarget_partial_assets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            host = root / "host.json"
            host.write_text(json.dumps(host_allocation({"NS_PORT_DAGU": "31080"})))
            self.assertEqual(self.run_partial(root).returncode, 37)
            unit = root / "config/dagu.service"
            before = unit.read_bytes()
            host.write_text(json.dumps(host_allocation({"NS_PORT_DAGU": "41080"})))
            retry = self.run_partial(root, finish=True)
            self.assertNotEqual(retry.returncode, 0)
            self.assertIn("needs_owner", retry.stderr)
            self.assertEqual(unit.read_bytes(), before)
            self.assertFalse((root / "config/.service-ports.json").exists())

    def test_changed_pending_intent_cannot_be_published(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            host = root / "host.json"
            host.write_text(json.dumps(host_allocation({"NS_PORT_DAGU": "31080"})))
            self.assertEqual(self.run_partial(root).returncode, 37)
            command = [sys.executable, str(PLAN / "config/observability_config.py")]
            common = ["--config-root", str(root / "config"), "--slot", "dagu",
                      "--plan-file", str(PLAN / "install-plan.json")]
            env = {"PATH": "/usr/bin:/bin", "HOME": str(root)}
            stage = subprocess.run(command + ["stage", *common, "--host-file", str(host),
                "--source-root", str(PLAN / "config"), "--output-root", str(root / "stage")],
                env=env, text=True, capture_output=True)
            self.assertEqual(stage.returncode, 0, stage.stderr)
            pending = root / "config/.service-ports.pending.json"
            changed = json.dumps(host_allocation({"NS_PORT_DAGU": "41080"}))
            pending.write_text(changed)
            commit = subprocess.run(command + ["commit-ports", *common,
                "--host-file", str(root / "stage/.service-ports.json")],
                env=env, text=True, capture_output=True)
            self.assertNotEqual(commit.returncode, 0)
            self.assertIn("needs_owner", commit.stderr)
            self.assertEqual(pending.read_text(), changed)
            self.assertFalse((root / "config/.service-ports.json").exists())

    def test_portless_install_staging_records_no_first_install_intent(self):
        checker = module(PLAN / "check_plan.py", "wave5_portless_intent")
        body = checker.functions((PLAN / "install.sh").read_text())["stage_plan_sources"]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "host.json").write_text(json.dumps(host_allocation()))
            result = subprocess.run(["bash", "-euo", "pipefail", "-c",
                                     'stage_plan_sources() {\n' + body + '\n}\nstage_plan_sources'],
                env={"PATH": "/usr/bin:/bin", "HOME": tmp, "plan_dir": str(PLAN),
                     "config_root": str(root / "config"), "host_file": str(root / "host.json"),
                     "only": "container-engine", "NS2604_NO_START": "1"}, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((root / "config/.service-ports.pending.json").exists())
            self.assertFalse((root / "config/.service-ports.json").exists())


class DocumentationFlowTests(unittest.TestCase):
    def test_frozen_document_checks_work_without_pr_only_git_objects(self):
        from tests import test_install_plan_review_wave3 as wave3
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("2026-10-01-new-wsl-distro-recipe.md", "2026-10-02-new-wsl-client-configuration.md",
                         "2026-10-16-new-wsl-host-allocation-addendum.md"):
                path = Path("docs/decisions") / name
                (root / path).parent.mkdir(parents=True, exist_ok=True)
                (root / path).write_bytes((ROOT / path).read_bytes())
            # An exported source tree has no PR object database, like a squash checkout
            # whose obsolete PR commits have been pruned. Run the real public test.
            case = wave3.ReviewWave4DocumentationTests("test_addendum_supersedes_both_decisions_without_rewriting_them")
            result = unittest.TestResult()
            with mock.patch.object(wave3, "ROOT", root):
                case.run(result)
            self.assertEqual(len(result.errors), 0, result.errors)
            self.assertEqual(len(result.failures), 0, result.failures)
            self.assertFalse(result.skipped)
            target = root / "docs/decisions/2026-10-01-new-wsl-distro-recipe.md"
            rewritten = bytearray(target.read_bytes())
            rewritten[0] ^= 1
            target.write_bytes(rewritten)
            changed = unittest.TestResult()
            with mock.patch.object(wave3, "ROOT", root):
                case.run(changed)
            self.assertEqual(len(changed.failures), 1)
            self.assertFalse(changed.skipped)

    def test_after_sign_in_instructions_require_activation_and_listener_ownership_first(self):
        recipe = (ROOT / "adoption/platforms/linux-wsl2-new-distro.md").read_text()
        paragraph = recipe.split("After the `--apply` line,", 1)[1].split("\n\n", 1)[0]
        checklist = (ROOT / "adoption/templates/wsl/first-boot-checklist.md").read_text()
        f9 = next(line for line in checklist.splitlines() if line.startswith("- [ ] **F9**"))
        for name, text in (("recipe", paragraph), ("checklist", f9)):
            with self.subTest(name=name):
                before_acceptance = text.split("--stage after_sign_in", 1)[0]
                self.assertIn("activation", before_acceptance)
                self.assertIn("listener-ownership", before_acceptance)


class MineruInstallFlowTests(unittest.TestCase):
    def test_no_start_models_satisfy_post_install_verification_without_daemon(self):
        checker = module(PLAN / "check_plan.py", "wave5_mineru_checker")
        install = checker.functions((PLAN / "install.sh").read_text())
        setup = next(c for c in checker.run_commands("mineru", install, set())
                     if "models download" in c)
        accept = checker.functions((PLAN / "accept.sh").read_text())
        post_install = next(program for stage, _, _, program in checker.checks_of(accept["mineru"])
                            if stage == "post_install")
        verification = next(line for line in post_install.splitlines()
                            if line.startswith("mineru-kit models verify"))
        # Model commands use the standalone kit at c221cc41, models.py:86-116,171-205.
        # The fake download persists data across the setup/acceptance process boundary.
        fakes = '''mineru() { printf 'DAEMON %s\\n' "$*"; return 99; }
mineru-kit() {
  printf 'KIT %s\\n' "$*"
  case "$*" in
    'models download --tier standard') touch "$HOME/models-ready" ;;
    'models verify --tier standard') test -f "$HOME/models-ready" ;;
    *) return 98 ;;
  esac
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            env = {"PATH": "/usr/bin:/bin", "HOME": tmp, "NS2604_NO_START": "1"}
            installed = subprocess.run(["bash", "-euo", "pipefail", "-c", fakes + setup],
                                       env=env, text=True, capture_output=True)
            self.assertEqual(installed.returncode, 0, installed.stderr)
            accepted = subprocess.run(["bash", "-euo", "pipefail", "-c", fakes + verification],
                                      env=env, text=True, capture_output=True)
            self.assertEqual(accepted.returncode, 0, "post_install model verification failed: " + accepted.stdout)
            self.assertIn("KIT models download --tier standard", installed.stdout)
            self.assertIn("KIT models verify --tier standard", installed.stdout)
            self.assertNotIn("DAEMON", installed.stdout + accepted.stdout)

    def test_no_start_failed_model_download_stops_before_verification_or_daemon_configuration(self):
        checker = module(PLAN / "check_plan.py", "wave5_mineru_failure")
        funcs = checker.functions((PLAN / "install.sh").read_text())
        setup = next(c for c in checker.run_commands("mineru", funcs, set()) if "models download" in c)
        fakes = '''mineru() { printf 'DAEMON %s\\n' "$*"; return 99; }
mineru-kit() { printf 'KIT %s\\n' "$*"; return 37; }
'''
        # Normal mode disables doclib telemetry first (CC correction192741).
        # This no-start contract still prohibits every daemon call.
        for mode in ("1",):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                result = subprocess.run(["bash", "-euo", "pipefail", "-c", fakes + setup],
                    env={"PATH": "/usr/bin:/bin", "HOME": tmp, "NS2604_NO_START": mode},
                    text=True, capture_output=True)
                self.assertEqual(result.returncode, 37, result.stderr)
                self.assertNotIn("verify", result.stdout)
                self.assertNotIn("DAEMON", result.stdout)


class DaguInstallFlowTests(unittest.TestCase):
    def prepare(self, root):
        renderer = module(PLAN / "config/observability_config.py", "wave5_dagu_ports")
        config = root / "config"
        config.mkdir()
        for name in ("dagu.service", "dagu-coordinator.conf"):
            (config / name).write_text(renderer.render_ports((PLAN / "config" / name).read_text(),
                                                            renderer.service_ports()))
        units = root / ".config/systemd/user"
        units.mkdir(parents=True)
        # Verbatim user-scope output of dagu v2.18.2 scripts/installer.sh:1666-1698;
        # user defaults are at657-675 and native env filenames at1635-1637.
        native = f'''[Unit]
Description=Dagu Workflow Engine
After=network.target
Wants=network-online.target

[Service]
Type=simple
ExecStart={root}/.local/bin/dagu start-all
WorkingDirectory={root}/.dagu
EnvironmentFile={root}/.config/dagu/dagu.env
EnvironmentFile=-{root}/.config/dagu/bootstrap.env
Restart=always
RestartSec=10

[Install]
WantedBy=default.target
'''
        (root / "native-unit.fixture").write_text(native)
        return units / "dagu.service"

    def run_dagu_commands(self, root, no_start="0"):
        checker = module(PLAN / "check_plan.py", "wave5_dagu_checker")
        funcs = checker.functions((PLAN / "install.sh").read_text())
        # Exercise the complete command sequence; config copies above are staged fixtures.
        # Neither the downloaded script nor a native installer/service command can run.
        fakes = '''systemctl() { printf 'FAKE_SYSTEMCTL %s\\n' "$*"; }
curl() { :; }
bash() {
  printf 'FAKE_INSTALLER %s\\n' "$*"
  if [[ "$dagu_service_mode" == yes ]]; then
    cp -- "$HOME/native-unit.fixture" "$HOME/.config/systemd/user/dagu.service"
  fi
}
'''
        script = fakes + '\n'.join(checker.run_commands("dagu", funcs, set()))
        return subprocess.run(["/bin/bash", "-euo", "pipefail", "-c", script],
            env={"PATH": "/usr/bin:/bin", "HOME": str(root), "plan_dir": str(root),
                 "config_root": str(root / "config"), "NS2604_NO_START": no_start,
                 "dagu_service_mode": "no" if no_start == "1" else "yes"},
            text=True, capture_output=True)

    def test_normal_install_can_rerun_over_its_native_generated_unit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            unit = self.prepare(root)
            initial = self.run_dagu_commands(root)
            self.assertEqual(initial.returncode, 0, initial.stderr)
            self.assertEqual(unit.read_bytes(), (root / "native-unit.fixture").read_bytes())
            rerun = self.run_dagu_commands(root)
            self.assertEqual(rerun.returncode, 0, rerun.stderr)
            self.assertIn("FAKE_INSTALLER", rerun.stdout)
            self.assertEqual(unit.read_bytes(), (root / "native-unit.fixture").read_bytes())

    def test_native_unit_recognition_preserves_unknown_files_and_no_start_boundary(self):
        for case in ("modified-unit", "symlink-unit", "unknown-drop-in", "symlink-drop-in", "no-start"):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                unit = self.prepare(root)
                unit.write_bytes((root / "native-unit.fixture").read_bytes())
                if case == "modified-unit":
                    unit.write_text(unit.read_text().replace("start-all", "server"))
                elif case == "symlink-unit":
                    unit.unlink()
                    unit.symlink_to(root / "native-unit.fixture")
                elif case.endswith("drop-in"):
                    drops = unit.parent / "dagu.service.d"
                    drops.mkdir()
                    if case == "symlink-drop-in":
                        (drops / "20-ns2604-coordinator.conf").symlink_to(root / "config/dagu-coordinator.conf")
                    else:
                        (drops / "90-operator.conf").write_text("[Service]\nEnvironment=DAGU_PORT=31080\n")
                before = unit.read_bytes()
                result = self.run_dagu_commands(root, "1" if case == "no-start" else "0")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("needs_owner", result.stderr)
                self.assertNotIn("FAKE_SYSTEMCTL", result.stdout)
                self.assertNotIn("FAKE_INSTALLER", result.stdout)
                self.assertEqual(unit.read_bytes(), before)
if __name__ == "__main__":
    unittest.main()
