"""Manual CLI/function runtime readers; native locks on scratch files only."""
import ast
import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / "blueprints/us-equities/adaptive-paper"


@unittest.skipUnless(shutil.which("flock"), "requires native flock")
class ManualRuntimeReadLock(unittest.TestCase):
    def helper(self):
        path = PAPER / "runtime_lock.py"
        self.assertTrue(path.is_file(), "manual entries need the managed runtime read-lock helper")
        spec = importlib.util.spec_from_file_location("scratch_runtime_lock", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def writer(self, lock):
        return subprocess.run(["flock", "--exclusive", "--nonblock", str(lock), "true"],
                              capture_output=True, text=True, timeout=5).returncode

    def test_native_reader_coordinates_with_shell_writer_and_releases_on_exception(self):
        helper = self.helper()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "projects/us-equities-runtime"
            (project / ".venv").mkdir(parents=True)
            lock = project.parent / ".us-equities-runtime.lock"
            with patch.object(helper.Path, "home", return_value=root), patch.object(sys, "prefix", str(project / ".venv")):
                with helper.runtime_read_lock():
                    self.assertEqual(self.writer(lock), 1)
                self.assertEqual(self.writer(lock), 0)
                @helper.runtime_read_locked
                def interrupted():
                    self.assertEqual(self.writer(lock), 1)
                    raise ValueError("scratch failure")
                with self.assertRaisesRegex(ValueError, "scratch failure"):
                    interrupted()
                self.assertEqual(self.writer(lock), 0)

    def test_manual_cli_refuses_before_any_runtime_package_import(self):
        # The exact CLI prefix runs with a refusal sentinel replacing the native
        # lock context. No SDK/import, parser, credential or runner body executes.
        for name, first_package in (("runner.py", "from corporate_actions"),
                                    ("mover_runner.py", "import safety")):
            with self.subTest(entry=name):
                source = (PAPER / name).read_text()
                prefix = source[:source.index(first_package)]
                sentinel = types.ModuleType("runtime_lock")
                class RuntimeLockError(RuntimeError):
                    pass
                class HeldWriter:
                    def __enter__(self):
                        raise RuntimeLockError("canonical_runtime_lock_unavailable")
                sentinel.RuntimeLockError = RuntimeLockError
                sentinel.runtime_read_lock = HeldWriter
                sentinel.runtime_read_locked = lambda function: function
                namespace = {"__name__": "__main__", "__file__": str(PAPER / name)}
                with patch.dict(sys.modules, {"runtime_lock": sentinel}):
                    with self.assertRaises(SystemExit) as stopped:
                        exec(compile(prefix, str(PAPER / name), "exec"), namespace)
                self.assertEqual(stopped.exception.code, 2)

    def test_imported_main_calls_retain_the_runtime_reader_for_their_lifetime(self):
        helper = self.helper()
        for name in ("runner.py", "mover_runner.py"):
            with self.subTest(entry=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                project = root / "projects/us-equities-runtime"
                (project / ".venv").mkdir(parents=True)
                function = next(node for node in ast.parse((PAPER / name).read_text()).body
                                if isinstance(node, ast.FunctionDef) and node.name == "main")
                # Preserve the production decorator and signature; a sentinel
                # stands at the entry boundary before any private/order state.
                function.body = [ast.Return(ast.Call(ast.Name("entry_probe", ast.Load()), [], []))]
                function.returns = None
                namespace = {"runtime_read_locked": helper.runtime_read_locked,
                             "entry_probe": lambda: self.assertEqual(self.writer(project.parent / ".us-equities-runtime.lock"), 1)}
                exec(compile(ast.fix_missing_locations(ast.Module([function], [])), name, "exec"), namespace)
                with patch.object(helper.Path, "home", return_value=root), patch.object(sys, "prefix", str(project / ".venv")):
                    namespace["main"]()
                self.assertEqual(self.writer(project.parent / ".us-equities-runtime.lock"), 0)
