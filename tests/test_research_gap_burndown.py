"""Causal controls and common-input contracts for the native research runs."""
import copy
import datetime as dt
from decimal import Decimal
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import sys

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "blueprints/us-equities/research-gap-burndown/run.py"
spec = importlib.util.spec_from_file_location("research_gap_run", PATH)
RUN = importlib.util.module_from_spec(spec)
spec.loader.exec_module(RUN)
engine_spec = importlib.util.spec_from_file_location("research_gap_engine", PATH.parent / "engine_run.py")
ENGINE = importlib.util.module_from_spec(engine_spec)
previous_run = sys.modules.get("run")
sys.modules["run"] = RUN
try:
    engine_spec.loader.exec_module(ENGINE)
finally:
    if previous_run is None:
        del sys.modules["run"]
    else:
        sys.modules["run"] = previous_run


class MatchedForecastTests(unittest.TestCase):
    def setUp(self):
        self.names = json.loads((PATH.parent / "plan.json").read_text())["forecast"]["candidates"]
        self.inputs = [{"fold": fold, "asset": "SPY", "origin": "2019-01-01T00:00:00",
                        "target_dates": ["2019-01-10T00:00:00"], "gap": 6, "scale": 2.0}
                       for fold in range(1, 5)]
        self.rows = [dict(model=name, fold=fold, asset="SPY", observed=[102.0],
                          prediction=[101.0], mae=1.0, mase=0.5,
                          training_naive_scale=2.0, elapsed_seconds=0.0)
                     for name in self.names for fold in range(1, 5)]

    def compare(self, rows=None, model_inputs=None):
        rows = self.rows if rows is None else rows
        with tempfile.TemporaryDirectory() as folder:
            classical, models = Path(folder) / "classical.json", Path(folder) / "models.json"
            classical.write_text(json.dumps({"result": {
                "forecasts": [r for r in rows if r["model"] in self.names[:2] + ["last-close-naive"]],
                "forecast_inputs": self.inputs}}))
            models.write_text(json.dumps({"result": {
                "forecasts": [r for r in rows if r["model"] in ["chronos-bolt-small", "kronos-small"]],
                "model_input_dates": self.inputs if model_inputs is None else model_inputs}}))
            return RUN.match_forecasts(classical, models)

    def test_equal_native_targets_can_be_compared(self):
        self.assertEqual(set(self.compare()[0]), set(self.names))

    def test_entire_missing_arm_cannot_silently_change_the_plan(self):
        with self.assertRaisesRegex(ValueError, "prespecified"):
            self.compare([r for r in self.rows if r["model"] != "kronos-small"])

    def test_same_prices_on_different_dates_are_not_common_targets(self):
        inputs = copy.deepcopy(self.inputs)
        inputs[0]["target_dates"] = ["2020-01-10T00:00:00"]
        with self.assertRaisesRegex(ValueError, "input|chronology"):
            self.compare(model_inputs=inputs)

    def test_different_training_scale_is_refused(self):
        rows = copy.deepcopy(self.rows)
        rows[0]["training_naive_scale"] = 200.0
        with self.assertRaisesRegex(ValueError, "scale|metric"):
            self.compare(rows)

    def test_corrupted_exported_score_is_refused(self):
        rows = copy.deepcopy(self.rows)
        rows[0]["mae"] = 0.0
        with self.assertRaisesRegex(ValueError, "metric"):
            self.compare(rows)

    def test_duplicate_and_missing_cases_are_refused(self):
        for rows in [self.rows + [copy.deepcopy(self.rows[0])], self.rows[1:]]:
            with self.subTest(rows=len(rows)), self.assertRaises(ValueError):
                self.compare(rows)

    def test_changed_outcome_is_refused(self):
        rows = copy.deepcopy(self.rows)
        rows[0]["observed"] = [999.0]
        with self.assertRaisesRegex(ValueError, "target"):
            self.compare(rows)


class ChronologyTests(unittest.TestCase):
    def test_crossed_and_purged_training_intervals_discriminate(self):
        self.assertEqual(RUN.label_crossings([9], [10], 6), 1)
        self.assertEqual(RUN.label_crossings([3], [10], 6), 0)
        self.assertEqual(RUN.label_crossings([17], [10], 6), 0)

    def test_fold_labels_are_censored_at_that_fold_not_dataset_end(self):
        dates = [(dt.date(2018, 1, 1) + dt.timedelta(days=i)).isoformat() for i in range(150)]
        panel = {s: [dict(date=d, open=Decimal(100+i), close=Decimal(101+i))
                     for i, d in enumerate(dates)] for s in ["SPY", "QQQ", "IWM"]}
        # Both labels have outcomes in the full dataset; only the first fits
        # inside the declared fold. Future prices must not rescue the second.
        rows = RUN.fold_labels(panel, [120, 125], ["equalweight"], Decimal("0.002"), 126)
        self.assertEqual([r["status"] for r in rows], ["observed", "censored"])
        self.assertEqual(rows[0]["exit"], dates[126])
        self.assertNotIn("net_proxy", rows[1])
        panel["SPY"][131]["open"] = Decimal("999999")
        self.assertEqual(rows, RUN.fold_labels(panel, [120, 125], ["equalweight"], Decimal("0.002"), 126))

    def test_pandas_integer_price_columns_are_explicitly_converted(self):
        import pandas as pd
        frame = pd.DataFrame({"open": [100001, 100002], "high": [110001, 110002],
                              "low": [90001, 90002], "close": [105001, 105002], "volume": [10, 11]})
        result = RUN.convert_price_units(frame)
        self.assertEqual(result["volume"].tolist(), [10, 11])
        self.assertAlmostEqual(result["open"].iloc[0], 10.0001)
        self.assertTrue(all(result[f].dtype.kind == "f" for f in ["open", "high", "low", "close"]))


class EngineAccountingTests(unittest.TestCase):
    def setUp(self):
        self.rows = [
            dict(kind="intent", order_id=1, asset="SPY", quantity=10, utc_seconds=1),
            dict(kind="order", order_id=1, status="Filled", asset="SPY", quantity=10,
                 price=100, fee=1, utc_seconds=2),
            dict(kind="dividend", amount=5),
            dict(kind="intent", order_id=2, asset="SPY", quantity=-10, utc_seconds=3),
            dict(kind="order", order_id=2, status="Filled", asset="SPY", quantity=-10,
                 price=101, fee=1, utc_seconds=4),
            dict(kind="final", cash=100013, equity=100013, positions={"SPY": 0}, decisions=2)]

    def test_fills_fees_and_distributions_reconcile_to_flat_cash(self):
        self.assertEqual(ENGINE.reconcile(self.rows)["cash_residual_usd"], "0")

    def test_removed_dividend_or_fee_cannot_pass_cash_audit(self):
        for key in ["amount", "fee"]:
            rows = copy.deepcopy(self.rows)
            next(r for r in rows if key in r)[key] = 0
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "cash reconciliation"):
                ENGINE.reconcile(rows)

    def test_same_bar_fill_and_changed_quantity_are_refused(self):
        for key, value in [("utc_seconds", 1), ("quantity", 9)]:
            rows = copy.deepcopy(self.rows)
            rows[1][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                ENGINE.reconcile(rows)

    def test_duplicate_fill_and_unfilled_intent_are_refused(self):
        for extra in [self.rows[1], dict(kind="intent", order_id=3, asset="SPY", quantity=1, utc_seconds=5)]:
            with self.subTest(extra=extra["kind"]), self.assertRaises(ValueError):
                ENGINE.reconcile(self.rows + [extra])

    def test_nonfinite_cash_and_remaining_inventory_are_refused(self):
        for key, value in [("cash", "NaN"), ("positions", {"SPY": 1})]:
            rows = copy.deepcopy(self.rows)
            rows[-1][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                ENGINE.reconcile(rows)

    def test_native_exported_type_tag_symbol_quantity_and_time_are_bound(self):
        intent = dict(kind="intent", order_id=1, asset="SPY", quantity=10,
                      utc_seconds=1, decision="1970-01-01")
        order = dict(type=4, tag="frozen-target:1970-01-01", symbol={"value": "SPY"},
                     quantity=10, time="1970-01-01T00:00:01Z")
        ENGINE.bind_native_orders([intent], {"1": order})
        for key, value in [("type", 0), ("tag", "another-decision"), ("symbol", {"value": "QQQ"}),
                           ("quantity", 9), ("time", "1970-01-01T00:00:00Z")]:
            changed = copy.deepcopy(order)
            changed[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                ENGINE.bind_native_orders([intent], {"1": changed})


if __name__ == "__main__":
    unittest.main()
