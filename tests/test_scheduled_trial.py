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
ACCEPTANCE = ROOT / "blueprints/us-equities/runtime-2604/accept-trading-2604.sh"
SYNC = ROOT / "blueprints/us-equities/runtime-2604/sync-trading-2604.sh"
PYPROJECT = ROOT / "blueprints/us-equities/runtime-2604/trading-2604-runtime/pyproject.toml"
REQUIREMENTS = ROOT / "blueprints/us-equities/adaptive-paper/requirements.txt"


class ScheduledTrialInterpreter(unittest.TestCase):
    def test_default_follows_the_supported_installer_project_environment(self):
        project = re.search(r'\brealpath --canonicalize-missing -- "\$HOME/([a-zA-Z0-9_./-]+)"', INSTALLER.read_text())
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
                   TASK_RUNTIME=str(root / "runtime"), TASK_PROJECTS=str(root))
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
        text = SCRIPT.read_text().replace("$HOME/projects/us-equities-runtime", "$TASK_RUNTIME").replace("$HOME/projects", "$TASK_PROJECTS")
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



"""Scratch shell concurrency probes; no real installer, runtime or broker."""
import json
try:
    import fcntl
except ImportError:
    fcntl = None
import os
from pathlib import Path
import selectors
import shutil
import subprocess
import tempfile
import unittest


@unittest.skipUnless(shutil.which("flock") and fcntl is not None, "requires native flock")
class ScheduledTrialRuntimeLock(unittest.TestCase):
    def fixture(self):
        temporary = tempfile.TemporaryDirectory(prefix="runtime-lock-fixture-")
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        runtime = root / "projects/us-equities-runtime"
        (runtime / ".venv/bin").mkdir(parents=True)
        py = runtime / ".venv/bin/python"
        py.write_text("#!/bin/sh\nexit 97\n")
        py.chmod(0o700)
        gate = root / "gate-python"
        gate.write_text("#!/bin/sh\nexit 97\n")
        gate.chmod(0o700)
        (runtime / ".trading-2604-owner").write_text("native-stack-trading-2604-v1\n")
        (runtime / ".trading-2604-complete").write_text("native-stack-trading-2604-no-dvc-r4\n")
        bundle = ROOT / "blueprints/us-equities/runtime-2604/trading-2604-runtime"
        for name in ("pyproject.toml", "uv.lock"):
            shutil.copyfile(bundle / name, runtime / name)
        scheduler = root / "scheduled_trial.sh"
        text = SCRIPT.read_text().replace("$HOME/projects/us-equities-runtime", "$TASK_RUNTIME")
        text = text.replace("$HOME/projects", "$TASK_PROJECTS")
        text = text.replace('here="$(cd "$(dirname "$0")" && pwd)"',
                            'here="' + str(ROOT / "blueprints/us-equities/adaptive-paper") + '"')
        scheduler.write_text(text)
        # Execute only the real installer's ownership/lock/marker block and its
        # completion block. Replace ALL installation work with one scratch write.
        source = INSTALLER.read_text()
        begin = source.index("step=project-ownership\n")
        end = source.index("# All managed interpreter", begin)
        block = source[begin:end].replace("$HOME/projects", "$TASK_PROJECTS")
        block = block.replace('rm -f -- "$project/.trading-2604-complete"',
            'if [[ ${TASK_PAUSE_INSTALL:-0} == 1 ]]; then '
            'printf "ready\\n" > "$TASK_READY"; IFS= read -r token < "$TASK_RELEASE"; fi\n'
            'rm -f -- "$project/.trading-2604-complete"')
        completion = source[source.index("step=completion-marker\n"):source.index("result=PASS\n", source.index("step=completion-marker\n"))]
        installer = root / "scratch-installer.sh"
        assignment = next(line for line in source.splitlines()
                          if line.startswith(('readonly project=', 'project=$(realpath')))
        assignment = assignment.replace('$HOME/projects/us-equities-runtime', '$TASK_RUNTIME')
        installer.write_text('#!/usr/bin/env bash\nset -euo pipefail\n'
            'die() { echo "$1" >&2; exit "$2"; }\n' + assignment + '\n'
            'owner=native-stack-trading-2604-v1; '
            'completion=native-stack-trading-2604-no-dvc-r4; temporary=""\n'
            'die() { echo "$1" >&2; exit "$2"; }\n'
            'blocked() { echo "$1" >&2; exit "$2"; }\n' + block +
            'mkdir -p "$project/.venv"\n'
            'printf "scratch-sync\\n" > "$project/.venv/SYNCING"\n'
            'if [[ ${TASK_RUN_SYNC:-0} == 1 ]]; then '
            'safe=(); runtime_python="$project/.venv/bin/python"; '
            'uv() { printf "uv\\n" >> "$TASK_UV_CALLS"; }; '
            'source "$TASK_SYNC_SCRIPT"; sync_trading_2604; fi\n'
            'if [[ ${TASK_KEEP_INCOMPLETE:-0} != 1 ]]; then\n' + completion + 'fi\n')
        ready, release = root / "ready", root / "release"
        for path in (ready, release):
            os.mkfifo(path)
        ready_fd, release_fd = (os.open(path, os.O_RDWR | os.O_NONBLOCK) for path in (ready, release))
        self.addCleanup(os.close, ready_fd)
        self.addCleanup(os.close, release_fd)
        bootstrap = root / "stub.sh"
        bootstrap.write_text('TASK_CALL=0\n'
            'timeout() { TASK_CALL=$((TASK_CALL+1)); '
            'if [[ "$TASK_CALL" == "${TASK_PAUSE_STAGE:-1}" && ${TASK_PAUSE_TRIAL:-0} == 1 ]]; then '
            'printf "ready\\n" > "$TASK_READY"; IFS= read -r token < "$TASK_RELEASE"; fi; '
            'if [[ -f "$TASK_RUNTIME/.trading-2604-complete" ]]; then phase=COMPLETE; '
            'else phase=INCOMPLETE; fi; '
            'printf "%s %s\\n" "$TASK_CALL" "$phase" >> "$TASK_CALLS"; '
            'if [[ "$TASK_CALL" == 3 ]]; then return 53; fi; return 0; }\n')
        env = {key: os.environ[key] for key in ("PATH", "HOME", "LANG") if key in os.environ}
        env.update(TRIAL="fixture", ENV_FILE=str(root / "unused.env"), STATE_ROOT=str(root / "state"),
                   OUT_DIR=str(root / "out"), TASK_RUNTIME=str(runtime), TASK_PROJECTS=str(root / "projects"),
                   GATE_PY=str(gate), CONFIG=str(ROOT / "blueprints/us-equities/adaptive-paper/config-sip.json"),
                   BASH_ENV=str(bootstrap), TASK_CALLS=str(root / "calls"), TASK_READY=str(ready), TASK_RELEASE=str(release))
        if "SYNC" in globals():
            sync = root / "sync.sh"
            source = SYNC.read_text().replace("$HOME/projects/us-equities-runtime", "$TASK_RUNTIME")
            sync.write_text(source.replace("$HOME/projects", "$TASK_PROJECTS"))
            env.update(TASK_SYNC_SCRIPT=str(sync), TASK_UV_CALLS=str(root / "uv-calls"))
        return root, runtime, scheduler, installer, ready_fd, release_fd, env

    def spawn(self, script, env):
        process = subprocess.Popen(["bash", str(script)], env=env, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True)
        def stop():
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=5)
        self.addCleanup(stop)
        return process

    def wait_ready(self, descriptor):
        with selectors.DefaultSelector() as selector:
            selector.register(descriptor, selectors.EVENT_READ)
            self.assertTrue(selector.select(timeout=5), "scratch rendezvous not reached")
        self.assertIn(b"ready", os.read(descriptor, 4096))

    def test_installer_cannot_sync_after_trial_readiness_check_until_trial_exits(self):
        for stage in (1, 2, 3):
            with self.subTest(stage=stage):
                root, runtime, scheduler, installer, ready, release, env = self.fixture()
                env.update(TASK_PAUSE_TRIAL="1", TASK_PAUSE_STAGE=str(stage))
                trial = self.spawn(scheduler, env)
                self.wait_ready(ready)  # Real ownership/readiness code already ran.
                install_env = dict(env, TASK_KEEP_INCOMPLETE="1")
                install = subprocess.run(["bash", str(installer)], env=install_env, capture_output=True, text=True, timeout=5)
                os.write(release, b"continue\n")
                stdout, stderr = trial.communicate(timeout=5)
                self.assertEqual(trial.returncode, 53, stderr)
                self.assertFalse((root / "unused.env").exists())
                self.assertFalse((root / "state").exists())
                # Old scripts return install0 and the remaining trial phases INCOMPLETE.
                self.assertEqual(install.returncode, 69, install.stderr)
                self.assertFalse((runtime / ".venv/SYNCING").exists())
                self.assertEqual((root / "calls").read_text().splitlines(),
                                 ["1 COMPLETE", "2 COMPLETE", "3 COMPLETE"])
                # The lock releases only after the complete trial, including runner.
                after = subprocess.run(["bash", str(installer)], env=env, capture_output=True, text=True, timeout=5)
                self.assertEqual(after.returncode, 0, after.stderr)
                self.assertTrue((runtime / ".venv/SYNCING").exists())

    def test_trial_refuses_installer_lock_before_marker_removal_or_out_dir(self):
        root, runtime, scheduler, installer, ready, release, env = self.fixture()
        installing = self.spawn(installer, dict(env, TASK_PAUSE_INSTALL="1"))
        self.wait_ready(ready)  # Installer lock held, marker still valid.
        trial = subprocess.run(["bash", str(scheduler)], env=env, capture_output=True, text=True, timeout=5)
        os.write(release, b"continue\n")
        stdout, stderr = installing.communicate(timeout=5)
        self.assertEqual(installing.returncode, 0, stderr)
        self.assertEqual(trial.returncode, 2, trial.stderr)
        self.assertIn("runtime in use", trial.stderr)
        self.assertFalse((root / "out").exists())
        self.assertFalse((root / "calls").exists())

    def test_runtime_alias_in_either_interpreter_stage_coordinates_with_installer(self):
        for variable in ("PY", "GATE_PY"):
            with self.subTest(variable=variable):
                root, runtime, scheduler, installer, ready, release, env = self.fixture()
                alias = root / "runtime-python-alias"
                alias.symlink_to(runtime / ".venv/bin/python")
                if variable == "GATE_PY":
                    env["PY"] = env["GATE_PY"]  # Other interpreter is independent.
                env[variable] = str(alias)
                installing = self.spawn(installer, dict(env, TASK_PAUSE_INSTALL="1"))
                self.wait_ready(ready)
                trial = subprocess.run(["bash", str(scheduler)], env=env, capture_output=True, text=True, timeout=5)
                os.write(release, b"continue\n")
                stdout, stderr = installing.communicate(timeout=5)
                self.assertEqual(installing.returncode, 0, stderr)
                self.assertEqual(trial.returncode, 2, trial.stderr)
                self.assertFalse((root / "out").exists())

    def test_missing_flock_refuses_before_output_and_marker_mutation(self):
        root, runtime, scheduler, installer, ready, release, env = self.fixture()
        bootstrap = root / "no-flock.sh"
        bootstrap.write_text('flock() { return 127; }\n')
        env["BASH_ENV"] = str(bootstrap)
        trial = subprocess.run(["bash", str(scheduler)], env=env, capture_output=True, text=True, timeout=5)
        install = subprocess.run(["bash", str(installer)], env=env, capture_output=True, text=True, timeout=5)
        self.assertEqual(trial.returncode, 2)
        self.assertEqual(install.returncode, 69)
        self.assertFalse((root / "out").exists())
        self.assertTrue((runtime / ".trading-2604-complete").exists())
        self.assertFalse((runtime / ".venv/SYNCING").exists())

    def test_lock_symlink_refuses_without_changing_its_target(self):
        root, runtime, scheduler, installer, ready, release, env = self.fixture()
        target = root / "unchanged"
        target.write_text("retain\n")
        (root / "projects/.us-equities-runtime.lock").symlink_to(target)
        trial = subprocess.run(["bash", str(scheduler)], env=env, capture_output=True, text=True, timeout=5)
        install = subprocess.run(["bash", str(installer)], env=env, capture_output=True, text=True, timeout=5)
        self.assertEqual(trial.returncode, 2)
        self.assertEqual(install.returncode, 73)
        self.assertEqual(target.read_text(), "retain\n")
        self.assertFalse((root / "out").exists())
        self.assertFalse((runtime / ".venv/SYNCING").exists())

    def test_two_scheduled_trials_share_the_runtime_lock(self):
        root, runtime, scheduler, installer, ready, release, env = self.fixture()
        env["TASK_PAUSE_TRIAL"] = "1"
        first = self.spawn(scheduler, env)
        self.wait_ready(ready)
        second_env = dict(env, OUT_DIR=str(root / "out-2"), TASK_CALLS=str(root / "calls-2"))
        second = self.spawn(scheduler, second_env)
        self.wait_ready(ready)
        install = subprocess.run(["bash", str(installer)], env=env, capture_output=True, text=True, timeout=5)
        os.write(release, b"continue\ncontinue\n")
        for process in (first, second):
            stdout, stderr = process.communicate(timeout=5)
            self.assertEqual(process.returncode, 53, stderr)
        self.assertEqual(install.returncode, 69, install.stderr)

    def test_fresh_installer_lock_does_not_make_project_unowned(self):
        root, runtime, scheduler, installer, ready, release, env = self.fixture()
        shutil.rmtree(runtime)
        first = self.spawn(installer, dict(env, TASK_PAUSE_INSTALL="1"))
        self.wait_ready(ready)
        second = subprocess.run(["bash", str(installer)], env=env, capture_output=True, text=True, timeout=5)
        os.write(release, b"continue\n")
        stdout, stderr = first.communicate(timeout=5)
        self.assertEqual(first.returncode, 0, stderr)
        self.assertEqual(second.returncode, 69, second.stderr)
        self.assertTrue((runtime / ".trading-2604-owner").exists())
        self.assertTrue((runtime / ".trading-2604-complete").exists())

    def test_interrupted_install_leaves_incomplete_marker_and_releases_lock(self):
        root, runtime, scheduler, installer, ready, release, env = self.fixture()
        first = subprocess.run(["bash", str(installer)], env=dict(env, TASK_KEEP_INCOMPLETE="1"),
                               capture_output=True, text=True, timeout=5)
        self.assertEqual(first.returncode, 0, first.stderr)
        trial = subprocess.run(["bash", str(scheduler)], env=env, capture_output=True, text=True, timeout=5)
        self.assertEqual(trial.returncode, 2, trial.stderr)
        self.assertFalse((root / "out").exists())
        lock = root / "projects/.us-equities-runtime.lock"
        with lock.open("a") as descriptor:
            fcntl.flock(descriptor, fcntl.LOCK_SH | fcntl.LOCK_NB)
            retry = subprocess.run(["bash", str(installer)], env=env, capture_output=True, text=True, timeout=5)
            self.assertEqual(retry.returncode, 69, retry.stderr)
        restored = subprocess.run(["bash", str(installer)], env=env, capture_output=True, text=True, timeout=5)
        self.assertEqual(restored.returncode, 0, restored.stderr)
        self.assertTrue((runtime / ".trading-2604-complete").exists())

    def test_acceptance_reader_refuses_installer_before_reading_marker(self):
        root, runtime, scheduler, installer, ready, release, env = self.fixture()
        for name in (".python", ".upstream", ".install-home", ".docker-config", "vendor/adaptive-paper/.git"):
            (runtime / name).mkdir(parents=True, exist_ok=True)
        (runtime / ".upstream/nautilus-quickstart.py").write_text("scratch source\n")
        source = ACCEPTANCE.read_text()
        normalization = 'project=$(realpath --canonicalize-missing'
        begin = source.index(normalization) if normalization in source else source.index('[[ ! -L "$HOME/projects"')
        end = source.index('# Read only the context endpoint', begin)
        block = source[begin:end].replace("$HOME/projects", "$TASK_PROJECTS")
        accept = root / "scratch-accept.sh"
        accept.write_text('#!/usr/bin/env bash\nset -euo pipefail\n'
            'project="$TASK_RUNTIME"; python="$project/.venv/bin/python"; '
            'adapter="$project/vendor/adaptive-paper"\n'
            'project_hash=aa370e42e29dc2419e586358254ff2e821df48a693aa9a3ee16b65d30036ee0b\n'
            'lock_hash=2df713279918415554d7ba23972d3c9b8dc3a8762c52b36cfd31de53e92c22d7\n'
            'blocked() { echo "blocked runtime" >&2; exit 1; }\n' + block)
        installing = self.spawn(installer, dict(env, TASK_PAUSE_INSTALL="1"))
        self.wait_ready(ready)
        accepting = subprocess.run(["bash", str(accept)], env=env, capture_output=True, text=True, timeout=5)
        os.write(release, b"continue\n")
        stdout, stderr = installing.communicate(timeout=5)
        self.assertEqual(installing.returncode, 0, stderr)
        self.assertEqual(accepting.returncode, 1, accepting.stderr)
        after = subprocess.run(["bash", str(accept)], env=env, capture_output=True, text=True, timeout=5)
        self.assertEqual(after.returncode, 0, after.stderr)

    def test_standalone_sync_refuses_installer_and_reuses_its_own_installer_fd(self):
        root, runtime, scheduler, installer, ready, release, env = self.fixture()
        installing = self.spawn(installer, dict(env, TASK_PAUSE_INSTALL="1"))
        self.wait_ready(ready)
        sync = root / "scratch-sync.sh"
        sync.write_text('#!/usr/bin/env bash\nset -euo pipefail\n'
            'project="$TASK_RUNTIME"; runtime_python="$project/.venv/bin/python"; safe=()\n'
            'uv() { printf "uv\\n" >> "$TASK_UV_CALLS"; }\n'
            'source "$TASK_SYNC_SCRIPT"\nsync_trading_2604\n')
        syncing = subprocess.run(["bash", str(sync)], env=env, capture_output=True, text=True, timeout=5)
        os.write(release, b"continue\n")
        stdout, stderr = installing.communicate(timeout=5)
        self.assertEqual(installing.returncode, 0, stderr)
        self.assertEqual(syncing.returncode, 69, syncing.stderr)
        self.assertFalse((root / "uv-calls").exists())
        reuse = subprocess.run(["bash", str(installer)], env=dict(env, TASK_RUN_SYNC="1"),
                               capture_output=True, text=True, timeout=5)
        self.assertEqual(reuse.returncode, 0, reuse.stderr)
        self.assertEqual(len((root / "uv-calls").read_text().splitlines()), 3)
        # A standalone caller may outlive the sync function. Its descriptor
        # must release on return rather than blocking trials until shell exit.
        sync.write_text(sync.read_text() +
                        'printf "ready\\n" > "$TASK_READY"; IFS= read -r token < "$TASK_RELEASE"\n')
        idle_caller = self.spawn(sync, env)
        self.wait_ready(ready)
        after_return = subprocess.run(["bash", str(installer)], env=env, capture_output=True, text=True, timeout=5)
        os.write(release, b"continue\n")
        stdout, stderr = idle_caller.communicate(timeout=5)
        self.assertEqual(idle_caller.returncode, 0, stderr)
        self.assertEqual(after_return.returncode, 0, after_return.stderr)

    def test_signal_releases_trial_lock_after_child_exit(self):
        root, runtime, scheduler, installer, ready, release, env = self.fixture()
        trial = self.spawn(scheduler, dict(env, TASK_PAUSE_TRIAL="1"))
        self.wait_ready(ready)
        blocked = subprocess.run(["bash", str(installer)], env=env, capture_output=True, text=True, timeout=5)
        trial.terminate()
        trial.communicate(timeout=5)
        after = subprocess.run(["bash", str(installer)], env=env, capture_output=True, text=True, timeout=5)
        self.assertEqual(blocked.returncode, 69, blocked.stderr)
        self.assertEqual(after.returncode, 0, after.stderr)


if __name__ == "__main__":
    unittest.main()
