"""Boundary tests for evidence projection; native execution has separate receipts."""

import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


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
