"""Managed runtime identity across native shell/Python readers and writers."""
import ast
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

try:
    import fcntl
except ImportError:
    fcntl = None

ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / "blueprints/us-equities/adaptive-paper"
RUNTIME = ROOT / "blueprints/us-equities/runtime-2604"


@unittest.skipUnless(fcntl is not None and shutil.which("flock") and shutil.which("realpath"),
                     "requires native runtime lock tools")
class RuntimeDirectoryIdentity(unittest.TestCase):
    def aliases(self, root):
        target = root / "physical/runtime"
        target.mkdir(parents=True)
        link = root / "runtime-link"
        link.symlink_to(target)
        return target, (str(target) + "/", str(target) + "/.", str(link))

    def test_shell_entry_directories_normalize_before_selecting_lock(self):
        for entry in ("installer", "scheduler", "acceptance", "sync"):
            with self.subTest(entry=entry), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                target, aliases = self.aliases(root)
                sources = {
                    "installer": (RUNTIME / "install-trading-2604.sh").read_text(),
                    "scheduler": (PAPER / "scheduled_trial.sh").read_text(),
                    "acceptance": (RUNTIME / "accept-trading-2604.sh").read_text(),
                    "sync": (RUNTIME / "sync-trading-2604.sh").read_text(),
                }
                source = sources[entry]
                self.assertIn("realpath --canonicalize-missing", source,
                              "every entry must resolve the directory before lock selection")
                if entry == "installer":
                    assignment = next(line for line in source.splitlines() if line.startswith("project=$(realpath"))
                    assignment = assignment.replace("$HOME/projects/us-equities-runtime", "$TASK_ALIAS")
                    selected = next(line for line in source.splitlines() if line.startswith("runtime_lock="))
                elif entry == "scheduler":
                    assignment = next(line for line in source.splitlines() if line.startswith("runtime=$(realpath"))
                    assignment = 'runtime="$TASK_ALIAS"\n' + assignment.split(" || {", 1)[0]
                    selected = next(line.strip() for line in source.splitlines() if line.strip().startswith("runtime_lock="))
                elif entry == "acceptance":
                    assignment = next(line for line in source.splitlines() if line.startswith("project=$(realpath"))
                    assignment = 'project="$TASK_ALIAS"\n' + assignment
                    selected = next(line for line in source.splitlines() if line.startswith("runtime_lock="))
                else:
                    assignment = next(line.strip() for line in source.splitlines() if line.strip().startswith("sync_directory=$(realpath"))
                    assignment = 'project="$TASK_ALIAS"\n' + assignment
                    selected = next(line.strip() for line in source.splitlines() if line.strip().startswith("runtime_lock="))
                body = 'set -euo pipefail\ndie() { exit "$2"; }; blocked() { exit 73; }\n' + assignment + '\n' + selected + '\n'
                body += 'exec {fd}>>"$runtime_lock"\nflock -s -n "$fd"\n'
                lock = target.parent / ".us-equities-runtime.lock"
                with lock.open("a") as writer:
                    fcntl.flock(writer, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    for alias in aliases:
                        with self.subTest(alias=alias):
                            env = {key: os.environ[key] for key in ("PATH", "HOME") if key in os.environ}
                            env["TASK_ALIAS"] = alias
                            outcome = subprocess.run(["bash", "-c", body], env=env,
                                                     capture_output=True, text=True, timeout=5)
                            self.assertEqual(outcome.returncode, 1, outcome.stderr)

    def test_manual_reader_selects_canonical_directory_before_choosing_parent_lock(self):
        path = PAPER / "runtime_lock.py"
        source = path.read_text()
        function = next(node for node in ast.parse(source).body
                        if isinstance(node, ast.FunctionDef) and node.name == "runtime_read_lock")
        assignment = next(node for node in function.body if isinstance(node, ast.Assign)
                          and any(isinstance(target, ast.Name) and target.id == "project" for target in node.targets))
        self.assertIsInstance(assignment.value, ast.Call)
        self.assertIsInstance(assignment.value.func, ast.Attribute)
        self.assertEqual(assignment.value.func.attr, "resolve",
                         "manual readers resolve before selecting the lock's parent")
        spec = importlib.util.spec_from_file_location("runtime_directory_fixture", path)
        helper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(helper)
        for entry in ("runner.py", "mover_runner.py"):
            self.assertIn("runtime_read_lock()", (PAPER / entry).read_text())
            self.assertIn("@runtime_read_locked", (PAPER / entry).read_text())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target, aliases = self.aliases(root)
            (target / ".venv").mkdir()
            home = root / "home"
            (home / "projects").mkdir(parents=True)
            (home / "projects/us-equities-runtime").symlink_to(target)
            lock = target.parent / ".us-equities-runtime.lock"
            with lock.open("a") as writer:
                fcntl.flock(writer, fcntl.LOCK_EX | fcntl.LOCK_NB)
                for alias in aliases:
                    with self.subTest(alias=alias), patch.object(helper.Path, "home", return_value=home), \
                         patch.object(sys, "prefix", alias + "/.venv"):
                        with self.assertRaises(helper.RuntimeLockError):
                            with helper.runtime_read_lock():
                                self.fail("writer held; manual runtime reader must refuse")

    def test_standalone_sync_aliases_refuse_with_zero_uv_calls(self):
        from tests.test_scheduled_trial import ScheduledTrialRuntimeLock
        for alias in ("trailing_slash", "dot", "directory_symlink"):
            with self.subTest(alias=alias):
                fixture = ScheduledTrialRuntimeLock("test_signal_releases_trial_lock_after_child_exit")
                try:
                    root, runtime, scheduler, installer, ready, release, env = fixture.fixture()
                    if alias == "directory_symlink":
                        link = root / "project-alias"
                        link.symlink_to(runtime)
                        value = str(link)
                    else:
                        value = str(runtime) + ("/" if alias == "trailing_slash" else "/.")
                    installing = fixture.spawn(installer, dict(env, TASK_PAUSE_INSTALL="1"))
                    fixture.wait_ready(ready)
                    caller = root / "caller.sh"
                    caller.write_text('set -euo pipefail\n'
                        'project="$TASK_ALIAS"; runtime_python="$TASK_RUNTIME/.venv/bin/python"; safe=()\n'
                        'uv() { printf "uv\\n" >> "$TASK_UV_CALLS"; }\n'
                        'source "$TASK_SYNC_SCRIPT"\nsync_trading_2604\n')
                    invoked = subprocess.run(["bash", str(caller)], env=dict(env, TASK_ALIAS=value),
                                             capture_output=True, text=True, timeout=5)
                    os.write(release, b"continue\n")
                    stdout, stderr = installing.communicate(timeout=5)
                    self.assertEqual(installing.returncode, 0, stderr)
                    self.assertEqual(invoked.returncode, 69, invoked.stderr)
                    self.assertFalse((root / "uv-calls").exists())
                    self.assertFalse((root / "unused.env").exists())
                finally:
                    fixture.doCleanups()

    def test_standalone_failed_sync_invalidates_and_success_restores_only_valid_completion(self):
        from tests.test_scheduled_trial import ScheduledTrialRuntimeLock
        for prior in ("valid", "missing", "invalid"):
            for failure in (0, 42):
                with self.subTest(prior=prior, failure=failure):
                    fixture = ScheduledTrialRuntimeLock("test_signal_releases_trial_lock_after_child_exit")
                    try:
                        root, runtime, scheduler, installer, ready, release, env = fixture.fixture()
                        marker = runtime / ".trading-2604-complete"
                        if prior == "missing":
                            marker.unlink()
                        elif prior == "invalid":
                            marker.write_text("stale\n")
                        caller = root / "sync-failure-caller.sh"
                        caller.write_text('set -euo pipefail\n'
                            'project="$TASK_RUNTIME"; runtime_python="$project/.venv/bin/python"; safe=()\n'
                            'uv() { [[ ! -f "$project/.trading-2604-complete" ]] || return 91; '
                            'if [[ "$2" == sync ]]; then printf "scratch\\n" > "$project/.venv/PARTIAL"; return "$TASK_FAILURE"; fi; return 0; }\n'
                            'source "$TASK_SYNC_SCRIPT"\nsync_trading_2604\n')
                        result = subprocess.run(["bash", str(caller)], env=dict(env, TASK_FAILURE=str(failure)),
                                                capture_output=True, text=True, timeout=5)
                        self.assertEqual(result.returncode, failure, result.stderr)
                        expected_complete = prior == "valid" and failure == 0
                        self.assertEqual(marker.exists(), expected_complete)
                        trial = subprocess.run(["bash", str(scheduler)], env=env,
                                               capture_output=True, text=True, timeout=5)
                        self.assertEqual(trial.returncode, 53 if expected_complete else 2, trial.stderr)
                        self.assertEqual((root / "out").exists(), expected_complete)
                        self.assertFalse((root / "unused.env").exists())
                    finally:
                        fixture.doCleanups()
