"""Boundary tests for evidence projection; native execution has separate receipts."""

import importlib.util
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
BLUEPRINT = ROOT / "blueprints/us-equities/backtesting-gap-burndown-20261010"
BASE = ROOT / "evidence/artifacts/backtesting-gap-burndown-20261010/us-equities__backtesting-engine"


def load(name):
    spec = importlib.util.spec_from_file_location(name, BLUEPRINT / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FailureBoundaryTests(unittest.TestCase):
    def test_projection_keyerror_makes_mechanics_command_fail(self):
        module = load("native_mechanics")
        # The native runner completes; the defect is projection, not import or
        # signature compatibility. Reproduce the original missing-key failure.
        replay = SimpleNamespace(CASE={}, VENUE={},
            load_bound_manifests=lambda: ({}, {}), check_engine_binary=lambda _: None,
            CONVERT=SimpleNamespace(convert=lambda *a: {"rows": []}),
            known_short_sessions=lambda _: [], distribution_events=lambda _: [],
            run_once=lambda *a: {})
        spec = SimpleNamespace(name="fixture_replay", loader=SimpleNamespace(exec_module=lambda _: None))
        fake_modules = {
            "nautilus_trader.execution": SimpleNamespace(FixedFeeModel=lambda *a, **k: None),
            "nautilus_trader.model": SimpleNamespace(Currency=SimpleNamespace(from_str=lambda _: None),
                                                       Money=lambda *a: None)}
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(sys.modules, fake_modules), \
             mock.patch.object(module.importlib.util, "spec_from_file_location", return_value=spec), \
             mock.patch.object(module.importlib.util, "module_from_spec", return_value=replay), \
             mock.patch.object(sys, "argv", ["mechanics", "--data", tmp, "--output", tmp + "/run"]), \
             contextlib.redirect_stdout(io.StringIO()):
            try:
                code = module.main()
            except KeyError:
                code = 1
            self.assertNotEqual(code, 0, "projection KeyError must fail the command, never become a successful refusal")

    def test_missing_verdict_fails_even_when_wrapper_reports_expected_exit(self):
        module = load("execute_comparators")
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(module, "RAW", Path(tmp)), \
             mock.patch.object(module.subprocess, "run", return_value=SimpleNamespace(returncode=0)), \
             mock.patch.object(sys, "argv", ["comparators", "--data", tmp, "--fresh", tmp]), \
             contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertNotEqual(module.main(), 0, "missing verdict must fail independently of process exit")

    def test_wrong_refusal_check_set_fails(self):
        module = load("execute_comparators")
        with tempfile.TemporaryDirectory() as tmp:
            def run(command, **kwargs):
                path = Path(command[command.index("--verdict") + 1])
                path.write_text(json.dumps({"verdict": "FAIL", "checks": [
                    {"key": "unexpected_crash.crash#1", "id": "unexpected_crash", "field": "crash", "status": "FAIL"}]}))
                return SimpleNamespace(returncode=0)
            with mock.patch.object(module, "RAW", Path(tmp)), \
                 mock.patch.object(module.subprocess, "run", side_effect=run), \
                 mock.patch.object(sys, "argv", ["comparators", "--data", tmp, "--fresh", tmp]), \
                 contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertNotEqual(module.main(), 0, "only the declared check ids qualify as expected refusal")

    def test_all_retained_verdicts_satisfy_exact_designed_check_sets(self):
        module = load("execute_comparators")
        for name in module.EXPECTED_CHECKS:
            module.validate_verdict(name, BASE / "raw" / (name + ".verdict.json"))

    def test_successful_driver_checks_all_four_fresh_verdict_files(self):
        module = load("execute_comparators")
        with tempfile.TemporaryDirectory() as tmp:
            def run(command, **kwargs):
                path = Path(command[command.index("--verdict") + 1])
                name = path.name.removesuffix(".verdict.json")
                path.write_bytes((BASE / "raw" / path.name).read_bytes())
                self.assertEqual(kwargs["env"]["OMP_NUM_THREADS"], "1")
                return SimpleNamespace(returncode=0 if name == "accepted-v2-lean-data" else 1)
            with mock.patch.object(module, "RAW", Path(tmp)), \
                 mock.patch.object(module.subprocess, "run", side_effect=run) as process, \
                 mock.patch.object(sys, "argv", ["comparators", "--data", tmp, "--fresh", tmp]), \
                 contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(module.main(), 0)
                self.assertEqual(process.call_count, 4)

    def test_refusal_requires_native_denial_events(self):
        module = load("native_mechanics")
        result = {"fills": [], "native_account_event_rows": [], "native_end_cash_usd": "100000.00",
                  "fees_usd": "0", "distribution_module": {"emissions": []}, "order_events": [],
                  "cash_ledger": [], "engine_log_scan": {"error_lines": 0}}
        with self.assertRaisesRegex(ValueError, "native_denial"):
            module.project_result("four-cash-refusal", "4", "CASH", result)


class CloseoutRegressionTests(unittest.TestCase):
    def test_unreviewed_counts_stay_at_historical_eight_twelve(self):
        matrix = json.loads((ROOT / "catalogs/landscape/component-evidence-matrix.json").read_text())
        row = next(r for r in matrix["rows"] if r["layer_id"] == "backtesting-engine")
        self.assertEqual((row["open_executable_now_gaps"], row["open_gaps"]), (8, 12),
                         "unreviewed receipts must not subtract three gaps")

    def test_prior_settlements_are_reconfirmations(self):
        for index, filename in ((2, "2-nautilus-latest-stable-release.json"),
                                (6, "6-comparator-modes-and-review-count.json")):
            receipt = json.loads((BASE / f"{index}-gap.json").read_text())
            self.assertEqual(receipt["outcome"], "covered_elsewhere", "September 23 settlement is not new")
            self.assertTrue(any(r["path"].endswith(filename) for r in receipt["raw_outputs"]))

    def test_gap_four_reports_one_method_twelve_cases(self):
        summary = json.loads((BASE / "raw/lean-model-summary.json").read_text())
        self.assertIn("CanSubmitOrderWhenOutsideRegularTradingHours", summary["surface"])
        self.assertIn("12 TestCaseSource cases", summary["surface"])

    def test_legacy_environment_omission_is_explicit(self):
        for name in ("lean-alpaca-model-tests-with-icu", "lean-alpaca-model-tests-py312"):
            receipt = json.loads((BASE / "raw" / (name + ".json")).read_text())
            self.assertIn("environment_record", receipt, "historical environment omission must be disclosed")
            self.assertEqual(receipt["environment_record"]["status"], "unavailable")

    def test_fresh_lean_environment_is_observed_and_explicit(self):
        receipt = json.loads((BASE / "raw/lean-model-explicit-environment.json").read_text())
        self.assertEqual(receipt["observed_exit_code"], 0)
        self.assertEqual(receipt["counters"]["passed"], "12")
        environment = receipt["environment_record"]
        self.assertEqual(environment["status"], "observed")
        self.assertTrue(environment["cleared"])
        self.assertTrue({"PYTHONNET_PYDLL", "PYTHONHOME", "LD_LIBRARY_PATH", "DOTNET_PROCESSOR_COUNT",
                         "OMP_NUM_THREADS"}.issubset(environment["variables"]))

    def test_retained_expected_refusal_has_native_denials_and_no_fills(self):
        receipt = json.loads((BASE / "raw/native-mechanics-events.json").read_text())
        refusal = next(r for r in receipt["results"] if r["id"] == "four-cash-refusal")
        self.assertEqual(refusal["status"], "expected_refusal")
        self.assertEqual(refusal["fills"], [])
        denied = [e for e in refusal["order_events"] if e["event"] == "OrderDenied"]
        self.assertEqual(len(denied), 2)
        self.assertTrue(all(e["reason"].startswith("NOTIONAL_EXCEEDS_FREE_BALANCE:") for e in denied))

    def test_bespoke_registration_and_recording_helpers_are_removed(self):
        for name in ("record.py", "register_changed.py", "summarize.py"):
            self.assertFalse((BLUEPRINT / name).exists(), "use the shared closeout and explicit registration APIs")

    def test_deferred_gaps_do_not_borrow_unrelated_native_summaries(self):
        unrelated = {"native-replay-economic-summary.json", "native-mechanics-summary.json", "lean-model-summary.json",
                     "review-excerpt-integrity.json"}
        for index in (1, 8):
            receipt = json.loads((BASE / f"{index}-gap.json").read_text())
            self.assertFalse(unrelated & {Path(r["path"]).name for r in receipt["raw_outputs"]},
                             "deferred gaps must cite evidence for their own remaining boundary")

    def test_failed_build_capture_is_bounded_and_hash_bound(self):
        path = BASE / "raw/lean-alpaca-model-tests-with-icu.stdout.txt"
        self.assertLessEqual(path.stat().st_size, 65536, "retain failed-build tail and original digest")


class NativeSummaryTests(unittest.TestCase):
    def test_projection_uses_existing_runner_public_summary_keys(self):
        spec = importlib.util.spec_from_file_location("mechanics", ROOT /
            "blueprints/us-equities/backtesting-gap-burndown-20261010/native_mechanics.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        # Schema from spy-parity/run.py:663-698. The runner publishes an end
        # balance and event rows, never a native_account_totals summary field.
        observed = {"fills": [], "native_end_cash_usd": "100000.00", "native_account_event_rows": [],
                    "distribution_module": {"emissions": []}, "order_events": [],
                    "cash_ledger": [], "engine_log_scan": {"error_lines": 0}, "fees_usd": "0"}
        projected = module.project_result("cash-refusal", "4", "CASH", observed)
        self.assertEqual(projected["native_end_cash"], "100000.00")
        self.assertEqual(projected["native_account_events"], [])
        self.assertFalse(projected["qualifies_frozen_stress_case"])


if __name__ == "__main__":
    unittest.main()
