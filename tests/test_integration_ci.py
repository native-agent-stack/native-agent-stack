"""Exercise the integration entry point against hermetic native unittest fixtures."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from tests.test_workflow_hardening import jobs, run_block, step_block


ROOT = Path(__file__).resolve().parents[1]


class IntegrationEntryPoint(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="integration-ci-")
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        (self.root / "scripts").mkdir()
        (self.root / "tests/integration").mkdir(parents=True)
        (self.root / "tests/__init__.py").write_text("")
        for name in ("scripts/run_integration_tests.py", "tests/adaptive_paper_hermetic.py"):
            shutil.copyfile(ROOT / name, self.root / name)

    def run_entry(self):
        return subprocess.run([sys.executable, "-B", "scripts/run_integration_tests.py"],
                              cwd=self.root, capture_output=True, text=True, timeout=20)

    def test_nonprefixed_integration_assertion_failure_reaches_exit_status(self):
        module = self.root / "tests/integration/preset_output.py"
        module.write_text("import unittest\nclass Output(unittest.TestCase):\n"
                          " def test_output(self): self.assertEqual('observed', 'expected')\n")
        failed = self.run_entry()
        self.assertEqual(failed.returncode, 1, failed.stdout + failed.stderr)
        self.assertIn("FAIL: test_output", failed.stderr)
        self.assertIn("Ran 1 test", failed.stderr)
        module.write_text("import unittest\nclass Output(unittest.TestCase):\n"
                          " def test_output(self): self.assertEqual('expected', 'expected')\n")
        passed = self.run_entry()
        self.assertEqual(passed.returncode, 0, passed.stdout + passed.stderr)
        self.assertIn("Ran 1 test", passed.stderr)

    def test_empty_directory_cannot_pass(self):
        result = self.run_entry()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("Ran 0 tests", result.stderr)

    def test_import_error_cannot_pass(self):
        (self.root / "tests/integration/broken_import.py").write_text("raise ImportError('fixture missing runtime')\n")
        result = self.run_entry()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("fixture missing runtime", result.stderr)

    def test_imported_paper_default_is_isolated_before_tests_run(self):
        sentinel = self.root / "SYN-canonical-STOP"
        sentinel.write_text("fixture preserved\n")
        (self.root / "safety.py").write_text(f"from pathlib import Path\nDEFAULT_STOP = Path({str(sentinel)!r})\n")
        (self.root / "tests/integration/paper_default.py").write_text(
            "import unittest, safety\nclass PaperDefault(unittest.TestCase):\n"
            " def test_default(self): self.assertFalse(safety.DEFAULT_STOP.exists())\n")
        result = self.run_entry()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(sentinel.read_text(), "fixture preserved\n")


class IntegrationWorkflow(unittest.TestCase):
    def test_job_runs_the_entrypoint_inside_mandatory_isolation(self):
        workflow = jobs((ROOT / ".github/workflows/validate.yml").read_text())
        job = workflow["integration"]
        script = run_block(step_block(job, "Run every integration module without network or host state"))
        for required in ("--unshare-all", "--unshare-net", "--clearenv", "--cap-drop ALL",
                         '--ro-bind "$GITHUB_WORKSPACE" /workspace', "--perms 1777 --tmpfs /var/tmp",
                         "--setenv HOME /var/tmp", "/venv/bin/python scripts/run_integration_tests.py",
                         "set -euo pipefail", "/usr/bin/time"):
            self.assertIn(required, script)
        self.assertNotIn("||", script)
        self.assertNotIn("continue-on-error", job)
        install = run_block(step_block(job, "Install the locked native integration runtime"))
        self.assertIn("--require-hashes", install)
        self.assertIn("adaptive-paper/requirements-linux-x86_64-py312.lock", install)
        # Required-check expansion is a CC decision; preserve the existing aggregate dependency.
        self.assertIn("needs: validate\n", workflow["validate-result"])


if __name__ == "__main__":
    unittest.main()
