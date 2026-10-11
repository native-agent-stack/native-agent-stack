"""CI-run scheduler contracts and refusals; never execute Python or broker code."""
import os
import shutil
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

    def run_script(self, root, py, gate, script=None):
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
                   BASH_ENV=str(bootstrap), TASK_CAPTURE=str(capture), GATE_PY=str(gate),
                   TASK_RUNTIME=str(root / "runtime"))
        if py is not None:
            env["PY"] = str(py)
        result = subprocess.run(["bash", str(script or SCRIPT)], env=env, cwd=ROOT,
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
                self.assertFalse((root / "out").exists())
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
            self.assertFalse((root / "out").exists())
            self.assertFalse((root / "out" / ".run-once").exists())

    def runtime_fixture(self, root):
        runtime = root / "runtime"
        (runtime / ".venv/bin").mkdir(parents=True)
        self.executable(runtime / ".venv/bin", "python")
        (runtime / ".trading-2604-owner").write_text("native-stack-trading-2604-v1\n")
        (runtime / ".trading-2604-complete").write_text("native-stack-trading-2604-no-dvc-r4\n")
        bundle = ROOT / "blueprints/us-equities/runtime-2604/trading-2604-runtime"
        for name in ("pyproject.toml", "uv.lock"):
            shutil.copyfile(bundle / name, runtime / name)
        # Virtualize only the managed prefix in a scratch script. HOME stays
        # inherited; the original script's validation and ordering are intact.
        script = root / "scheduled_trial.sh"
        text = SCRIPT.read_text().replace("$HOME/projects/us-equities-runtime", "$TASK_RUNTIME")
        text = text.replace('here="$(cd "$(dirname "$0")" && pwd)"',
                            'here="' + str(SCRIPT.parent) + '"')
        script.write_text(text)
        return runtime, script

    def test_default_runtime_requires_complete_owned_matching_metadata_before_output(self):
        cases = ("missing_runtime", "missing_completion", "stale_completion", "missing_owner",
                 "wrong_owner", "missing_manifest", "wrong_manifest", "missing_lock", "wrong_lock",
                 "completion_symlink", "owner_symlink", "manifest_symlink", "lock_symlink")
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                runtime, script = self.runtime_fixture(root)
                if case == "missing_runtime":
                    shutil.rmtree(runtime)
                elif case.startswith("missing_"):
                    name = {"completion": ".trading-2604-complete", "owner": ".trading-2604-owner",
                            "manifest": "pyproject.toml", "lock": "uv.lock"}[case[8:]]
                    (runtime / name).unlink()
                elif case in ("stale_completion", "wrong_owner", "wrong_manifest", "wrong_lock"):
                    name = {"stale_completion": ".trading-2604-complete", "wrong_owner": ".trading-2604-owner",
                            "wrong_manifest": "pyproject.toml", "wrong_lock": "uv.lock"}[case]
                    (runtime / name).write_text("partial-install\n")
                else:
                    name = {"completion": ".trading-2604-complete", "owner": ".trading-2604-owner",
                            "manifest": "pyproject.toml", "lock": "uv.lock"}[case.split("_")[0]]
                    target = runtime / name
                    target.rename(runtime / "original")
                    target.symlink_to(runtime / "original")
                gate = self.executable(root, "gate")
                result, calls = self.run_script(root, None, gate, script)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("refused:", result.stderr)
                self.assertEqual(calls, [])
                self.assertFalse((root / "out").exists())

    def test_complete_default_accepts_python_symlink_but_marker_cannot_replace_executable(self):
        for kind in ("file", "symlink", "missing", "directory", "broken_symlink", "directory_symlink"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                runtime, script = self.runtime_fixture(root)
                python = runtime / ".venv/bin/python"
                if kind != "file":
                    python.unlink()
                if kind == "symlink":
                    python.symlink_to(self.executable(root, "managed-python"))
                elif kind == "directory":
                    python.mkdir()
                elif kind == "broken_symlink":
                    python.symlink_to(root / "absent")
                elif kind == "directory_symlink":
                    python.symlink_to(runtime)
                gate = self.executable(root, "gate")
                result, calls = self.run_script(root, None, gate, script)
                valid = kind in ("file", "symlink")
                self.assertEqual(result.returncode, 53 if valid else 2, result.stderr)
                self.assertEqual(len(calls), 3 if valid else 0)
                self.assertEqual((root / "out").exists(), valid)

    def test_override_files_and_symlinks_are_valid_but_directories_are_refused(self):
        for variable in ("PY", "GATE_PY"):
            for kind in ("file_symlink", "directory", "directory_symlink", "broken_symlink"):
                with self.subTest(variable=variable, kind=kind), tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    valid = self.executable(root, "valid")
                    supplied = root / "override"
                    if kind == "file_symlink":
                        supplied.symlink_to(valid)
                    elif kind == "directory":
                        supplied.mkdir()
                    elif kind == "directory_symlink":
                        supplied.symlink_to(root)
                    else:
                        supplied.symlink_to(root / "absent")
                    py, gate = (supplied, valid) if variable == "PY" else (valid, supplied)
                    result, calls = self.run_script(root, py, gate)
                    accepted = kind == "file_symlink"
                    self.assertEqual(result.returncode, 53 if accepted else 2, result.stderr)
                    self.assertEqual(len(calls), 3 if accepted else 0)
                    self.assertEqual((root / "out").exists(), accepted)


if __name__ == "__main__":
    unittest.main()
