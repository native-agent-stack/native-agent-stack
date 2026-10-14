"""The trading-runtime job: the modules behind trading-runtime skip guards run on the locked runtime, and a skip fails.

CI's validate shards install only .github/requirements-ci.txt, so every test guarded on the pinned trading runtime skipped
there and no required check ever ran it (the co-op's skip-guard inventory of 2026-10-14, from validate run 38504827195).
scripts/trading_runtime_suite.py runs those modules in validate.yml's trading-runtime job; these tests pin its skip policy,
its version preflight, the module list and the workflow wiring that makes the required `validate` check depend on it.

Sources: Python 3.12 unittest, "Skipping tests and expected failures" and TestResult.skipped
(https://docs.python.org/3.12/library/unittest.html); GitHub Actions, jobs.<job_id>.needs with always() and the needs
context's result values (docs.github.com, workflow-syntax and contexts reference).
"""

import importlib.metadata
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

from tests.test_workflow_hardening import block_if, jobs, step_block

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts/trading_runtime_suite.py"
MANIFEST = json.loads((ROOT / "scripts/trading_runtime_suite.json").read_text(encoding="utf-8"))
WORKFLOW = (ROOT / ".github/workflows/validate.yml").read_text(encoding="utf-8")
SPEC = importlib.util.spec_from_file_location("trading_runtime_suite", RUNNER)
suite = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(suite)

# A test module carrying one of these guards depends on the trading runtime; it must be in the manifest.
GUARD = re.compile(r"""find_spec\(\s*["'](?:nautilus_trader|alpaca)["']\s*\)"""
                   r"""|version\(\s*["']nautilus_trader["']\s*\)"""
                   r"""|^[ \t]+(?:import (?:alpaca|nautilus_trader)\b|from (?:alpaca|nautilus_trader)[ .])""", re.M)


def row(prefix, reason, count):
    return {"id_prefix": prefix, "reason_contains": reason, "count": count, "owner": "fixture", "why": "fixture"}


class SkipPolicy(unittest.TestCase):
    def test_a_skip_matching_no_named_exclusion_is_unexpected(self):
        unexpected, drift = suite.classify([["tests.test_a.T.test_x", "requires the pinned alpaca-py package"]], [])
        self.assertEqual(unexpected, [["tests.test_a.T.test_x", "requires the pinned alpaca-py package"]])
        self.assertEqual(drift, [])

    def test_a_named_exclusion_with_its_exact_count_passes(self):
        skips = [["tests.test_a.T.test_x", "needs v1"], ["tests.test_a.T.test_y", "needs v1"]]
        self.assertEqual(suite.classify(skips, [row("tests.test_a.", "needs v1", 2)]), ([], []))

    def test_a_named_exclusion_whose_count_moved_is_drift(self):
        for skips in ([["tests.test_a.T.test_x", "needs v1"]], []):
            with self.subTest(matched=len(skips)):
                unexpected, drift = suite.classify(skips, [row("tests.test_a.", "needs v1", 2)])
                self.assertEqual(unexpected, [])
                self.assertEqual([entry["matched"] for entry in drift], [len(skips)])

    def test_a_skip_must_match_the_prefix_and_the_reason_of_exactly_one_exclusion(self):
        exclusions = [row("tests.test_a.", "needs", 1), row("tests.test_a.T.", "v1", 1)]
        unexpected, _ = suite.classify([["tests.test_a.T.test_x", "needs v1"]], exclusions)
        self.assertEqual(len(unexpected), 1, "a skip that two exclusions match is ambiguous")
        unexpected, _ = suite.classify([["tests.test_b.T.test_x", "needs v1"]], [row("tests.test_a.", "needs v1", 0)])
        self.assertEqual(len(unexpected), 1, "the reason alone does not excuse another module's skip")


class VersionPreflight(unittest.TestCase):
    def preflight(self, lock_text, installed, required=("alpaca-py",)):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "x.lock").write_text(lock_text, encoding="utf-8")

            def version(name):
                if name not in installed:
                    raise importlib.metadata.PackageNotFoundError(name)
                return installed[name]
            return suite.preflight({"lock": "x.lock", "required_distributions": list(required)}, Path(directory),
                                   version=version)

    def test_each_required_distribution_must_be_installed_at_the_pinned_version(self):
        lock = "alpaca-py==0.44.0 \\\n    --hash=sha256:" + "0" * 64 + "\n"
        self.assertEqual(self.preflight(lock, {"alpaca-py": "0.44.0"})[1], [])
        self.assertEqual(self.preflight(lock, {"alpaca-py": "0.43.0"})[1],
                         ["alpaca-py: installed 0.43.0, the lock pins 0.44.0"])
        self.assertEqual(self.preflight(lock, {})[1], ["alpaca-py: installed None, the lock pins 0.44.0"])
        self.assertEqual(self.preflight("requests==2.34.2\n", {"alpaca-py": "0.44.0"})[1],
                         ["alpaca-py: not pinned in x.lock"])

    def test_names_compare_as_pep_503_normalizes_them(self):
        self.assertEqual(self.preflight("Nautilus_Trader==2.0.0rc5\n", {"nautilus-trader": "2.0.0rc5"},
                                        ("nautilus-trader",))[1], [])


class Manifest(unittest.TestCase):
    def test_every_test_module_with_a_trading_runtime_guard_is_listed(self):
        guarded = sorted(path.stem for path in (ROOT / "tests").glob("test_*.py")
                         if path.name != Path(__file__).name and GUARD.search(path.read_text(encoding="utf-8")))
        self.assertTrue(guarded)
        self.assertEqual([name for name in guarded if name not in MANIFEST["modules"]], [],
                         "add the module to scripts/trading_runtime_suite.json so the trading-runtime job runs it")

    def test_every_listed_module_exists_once(self):
        self.assertEqual(len(MANIFEST["modules"]), len(set(MANIFEST["modules"])))
        for module in MANIFEST["modules"]:
            self.assertTrue((ROOT / "tests" / f"{module}.py").is_file(), module)

    def test_the_lock_pins_each_required_distribution_with_hashes(self):
        lock = ROOT / MANIFEST["lock"]
        pins = suite.lock_pins(lock)
        for name in MANIFEST["required_distributions"]:
            self.assertIn(suite.canonical(name), pins, name)
        self.assertIn("--hash=sha256:", lock.read_text(encoding="utf-8"))

    def test_each_exclusion_names_a_listed_module_an_owner_and_a_reason(self):
        for entry in MANIFEST["exclusions"]:
            module = entry["id_prefix"].split(".")[1]
            self.assertIn(module, MANIFEST["modules"])
            self.assertTrue(entry["reason_contains"] and entry["owner"] and entry["why"])
            self.assertIsInstance(entry["count"], int)


class RunnerEndToEnd(unittest.TestCase):
    """The runner on a fixture tree: one test that skips the way a runtime guard skips without its runtime."""

    def run_runner(self, exclusions, required=(), pin=None, baseline=None):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "tests").mkdir()
            (root / "tests/__init__.py").write_text("", encoding="utf-8")
            (root / "tests/test_fixture_guard.py").write_text(
                "import unittest\n\n\nclass Guarded(unittest.TestCase):\n"
                "    @unittest.skipUnless(False, 'requires the fixture runtime')\n"
                "    def test_guarded(self):\n        pass\n\n"
                "    def test_plain(self):\n        pass\n", encoding="utf-8")
            (root / "x.lock").write_text(pin or "", encoding="utf-8")
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({"lock": "x.lock", "required_distributions": list(required),
                                            "modules": ["test_fixture_guard"], "exclusions": exclusions}),
                                encoding="utf-8")
            command = [sys.executable, str(RUNNER), "run", "--manifest", str(manifest), "--report", str(root / "r.json")]
            if baseline is not None:
                (root / "b.json").write_text(json.dumps(baseline), encoding="utf-8")
                command += ["--baseline", str(root / "b.json")]
            proc = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=60)
            report = json.loads((root / "r.json").read_text(encoding="utf-8"))
        return proc, report

    def test_a_guard_skip_fails_the_job_unless_it_is_a_named_exclusion(self):
        proc, report = self.run_runner([])
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("unexpected skip: test_fixture_guard.Guarded.test_guarded: requires the fixture runtime",
                      proc.stdout.replace("tests.", ""))
        self.assertFalse(report["success"])
        proc, report = self.run_runner([row("tests.test_fixture_guard.", "fixture runtime", 1)])
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(report["counts"], {"ran": 2, "failures": 0, "errors": 0, "skipped": 1})
        proc, _ = self.run_runner([row("tests.test_fixture_guard.", "fixture runtime", 2)])
        self.assertEqual(proc.returncode, 1, "a named exclusion whose count moved fails")
        self.assertIn("named exclusion drift", proc.stdout)

    def test_a_missing_runtime_fails_before_any_test_runs(self):
        # VersionPreflight covers a different installed version; here the distribution is absent, as when the job's
        # install step is removed.
        name = "trading-runtime-suite-absent-fixture"
        proc, report = self.run_runner([], required=(name,), pin=f"{name}==1.0\n")
        self.assertEqual(proc.returncode, 1)
        self.assertNotIn("counts", report, "no test runs on the wrong runtime")
        self.assertEqual(report["preflight_errors"], [f"{name}: installed None, the lock pins 1.0"])

    def test_the_baseline_counts_the_tests_only_the_runtime_lets_run(self):
        baseline = {"ran": 2, "skipped": ["tests.test_fixture_guard.Guarded.test_guarded",
                                          "tests.test_fixture_guard.Guarded.test_plain"]}
        proc, report = self.run_runner([row("tests.test_fixture_guard.", "fixture runtime", 1)], baseline=baseline)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual((report["baseline_skipped"], report["guarded_tests_run"]), (2, 1))
        proc, report = self.run_runner([row("tests.test_fixture_guard.", "fixture runtime", 1)],
                                       baseline=dict(baseline, ran=3))
        self.assertEqual(proc.returncode, 1, "a baseline of another test set is refused")


class Workflow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.jobs = jobs(WORKFLOW)
        cls.job = cls.jobs["trading-runtime"]
        cls.final = cls.jobs["validate-result"]

    def test_the_job_installs_the_lock_with_hashes_into_its_own_venv(self):
        step = step_block(self.job, "Provision the pinned trading runtime")
        self.assertIn("pip sync", step)
        self.assertIn("--require-hashes", step)
        self.assertIn(MANIFEST["lock"], step)
        self.assertIsNone(block_if(step))

    def test_the_baseline_runs_on_the_shards_interpreter_and_the_suite_on_the_runtime(self):
        install = step_block(self.job, "Install checksum-locked CI analyzer")
        self.assertIn("-r .github/requirements-ci.txt", install)
        self.assertIn("python3 scripts/trading_runtime_suite.py baseline", step_block(self.job, "baseline"))
        step = step_block(self.job, "Run the trading-runtime modules")
        self.assertIn('"$TRADING_RUNTIME_PYTHON" scripts/trading_runtime_suite.py run', step)
        self.assertIn("--baseline", step)
        self.assertIn("set -o pipefail", step)
        limit = int(re.search(r"(?m)^    timeout-minutes: (\d+)$", self.job).group(1))
        self.assertIn(f"timeout --signal=ABRT --kill-after=60s {limit - 5}m", step)
        self.assertIsNone(block_if(step))
        self.assertNotIn("continue-on-error", self.job)

    def test_its_artifact_stays_out_of_the_shard_reports(self):
        self.assertRegex(self.job, r"name: validate-trading-runtime-\$\{\{ github\.run_id \}\}")
        self.assertNotIn("validate-shard-", self.job)

    def test_the_required_validate_check_needs_the_job_and_its_success(self):
        self.assertRegex(self.final, r"(?m)^    name: validate$")
        self.assertRegex(self.final, r"(?m)^    needs: \[validate, trading-runtime\]$")
        self.assertEqual(block_if(self.final), "always()")
        step = step_block(self.final, "Require the trading-runtime job's success")
        self.assertIn("TRADING_RUNTIME_RESULT: ${{ needs.trading-runtime.result }}", step)
        self.assertIn('test "$TRADING_RUNTIME_RESULT" = success', step)
        self.assertEqual(block_if(step), "always()")


if __name__ == "__main__":
    unittest.main()
