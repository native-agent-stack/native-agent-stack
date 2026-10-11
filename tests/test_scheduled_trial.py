"""CI-run scheduler contracts and refusals; never execute Python or broker code."""
import os
from pathlib import Path
import re
import subprocess
import tempfile
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "blueprints/us-equities/adaptive-paper/scheduled_trial.sh"
INSTALLER = ROOT / "blueprints/us-equities/runtime-2604/install-trading-2604.sh"
PYPROJECT = ROOT / "blueprints/us-equities/runtime-2604/trading-2604-runtime/pyproject.toml"
REQUIREMENTS = ROOT / "blueprints/us-equities/adaptive-paper/requirements.txt"


class ScheduledTrialInterpreter(unittest.TestCase):
    def test_default_follows_the_supported_installer_project_environment(self):
        project = re.search(r'^readonly project="\$HOME/([a-zA-Z0-9_./-]+)"$', INSTALLER.read_text(), re.M)
        default = re.search(r'^PY="\$\{PY:-\$HOME/([a-zA-Z0-9_./-]+)\}"$', SCRIPT.read_text(), re.M)
        self.assertIsNotNone(project)
        self.assertIsNotNone(default)
        self.assertIn('UV_PROJECT_ENVIRONMENT="$project/.venv"', INSTALLER.read_text())
        self.assertEqual(Path(default.group(1)), Path(project.group(1)) / ".venv/bin/python")

    def test_runtime_pins_every_adaptive_requirement(self):
        def normalize(requirement):
            name, version = requirement.split("==")
            return re.sub(r"[-_.]+", "-", name.lower()) + "==" + version
        dependencies = {normalize(value) for value in tomllib.loads(PYPROJECT.read_text())["project"]["dependencies"]
                        if "==" in value}
        required = {normalize(line.strip()) for line in REQUIREMENTS.read_text().splitlines()
                    if line.strip() and not line.lstrip().startswith("#")}
        self.assertTrue(required <= dependencies, sorted(required - dependencies))

    def run_script(self, root, py, gate):
        capture = root / "argv.txt"
        bootstrap = root / "bootstrap.sh"
        bootstrap.write_text('TASK_CALL_COUNT=0\n'
            'timeout() { TASK_CALL_COUNT=$((TASK_CALL_COUNT + 1)); '
            'printf "%s\\n" CALL "$@" >> "$TASK_CAPTURE"; '
            'if [ "$TASK_CALL_COUNT" -lt 3 ]; then return 0; fi; return 53; }\n')
        env = {name: os.environ[name] for name in ("PATH", "HOME", "LANG") if name in os.environ}
        env.update(TRIAL="fixture", ENV_FILE=str(root / "unused.env"),
                   STATE_ROOT=str(root / "state"), OUT_DIR=str(root / "out"),
                   CONFIG=str(ROOT / "blueprints/us-equities/adaptive-paper/config-sip.json"),
                   BASH_ENV=str(bootstrap), TASK_CAPTURE=str(capture), PY=str(py), GATE_PY=str(gate))
        result = subprocess.run(["bash", str(SCRIPT)], env=env, cwd=ROOT,
                                capture_output=True, text=True)
        calls = [block.splitlines() for block in capture.read_text().split("CALL\n")[1:]] if capture.exists() else []
        self.assertFalse((root / "unused.env").exists())
        return result, calls

    def executable(self, root, name):
        path = root / name
        path.write_text("#!/bin/sh\nexit 97\n")
        path.chmod(0o700)
        return path

    def test_ingest_and_runner_use_py_while_gate_uses_gate_py(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            py, gate = self.executable(root, "approved-python"), self.executable(root, "approved-gate")
            result, calls = self.run_script(root, py, gate)
            self.assertEqual(result.returncode, 53, result.stderr)
            self.assertEqual(len(calls), 3)
            self.assertEqual([call[1] for call in calls], [str(py), str(gate), str(py)])
            self.assertEqual([call[0] for call in calls], ["120", "120", "900"])
            self.assertEqual([Path(call[2]).name for call in calls],
                             ["ingest_snapshot.py", "promotion_gate.py", "runner.py"])

    def test_missing_interpreter_is_refused_before_run_once_lock(self):
        for missing in ("PY", "GATE_PY"):
            with self.subTest(missing=missing), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                executable = self.executable(root, "available-python")
                unavailable = root / "missing-python"
                py, gate = (unavailable, executable) if missing == "PY" else (executable, unavailable)
                result, calls = self.run_script(root, py, gate)
                self.assertEqual(result.returncode, 2)
                self.assertIn(f"refused: interpreter not executable: {unavailable}", result.stderr)
                self.assertEqual(calls, [])
                self.assertFalse((root / "out" / ".run-once").exists())

    def test_non_executable_interpreter_is_refused_before_run_once_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            gate = self.executable(root, "available-gate")
            py = root / "not-executable"
            py.write_text("#!/bin/sh\nexit 97\n")
            py.chmod(0o600)
            result, calls = self.run_script(root, py, gate)
            self.assertEqual(result.returncode, 2)
            self.assertIn(f"refused: interpreter not executable: {py}", result.stderr)
            self.assertEqual(calls, [])
            self.assertFalse((root / "out" / ".run-once").exists())


if __name__ == "__main__":
    unittest.main()
