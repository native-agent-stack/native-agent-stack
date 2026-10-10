"""Market-data gap regressions: local fixtures, no provider or credential access."""
import contextlib
import copy
import importlib.util
import io
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts import component_matrix as cm
from scripts.catalog_decisions import InvalidDecisionIndex


ROOT = Path(__file__).resolve().parents[1]
ENTRY = ROOT / "blueprints/us-equities/authenticated-data/compare_providers.py"


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ProviderComparisonTests(unittest.TestCase):
    def setUp(self):
        self.entry = load(ENTRY, "provider_comparison_entry")
        self.m = self.entry.load_comparator()

    def test_cli_scores_multiple_symbols_and_selects_the_requested_sessions(self):
        with tempfile.TemporaryDirectory() as tmp:
            reference = Path(tmp) / "reference.csv"
            provider = Path(tmp) / "provider.csv"
            reference.write_text("symbol,session_date,close\n"
                                 "AAPL,2020-08-03,100.000000000000000001\n"
                                 "AAPL,2020-08-04,101\nIBM,2020-08-03,200\n"
                                 "IBM,2020-08-04,201\nIBM,2020-07-31,999\n"
                                 "ZZZ,2020-08-03,999\n", encoding="utf-8")
            provider.write_text(reference.read_text().replace("IBM,2020-08-04,201", "IBM,2020-08-04,201.01"))
            args = [str(ENTRY), "--reference", f"normalized-csv:{reference}",
                    "--provider", f"normalized-csv:{provider}", "--symbols", "AAPL,IBM",
                    "--start", "2020-08-03", "--end", "2020-08-04", "--expect-sessions", "2"]
            out = io.StringIO()
            with patch.object(sys, "argv", args), contextlib.redirect_stdout(out):
                self.entry.main()
            result = json.loads(out.getvalue())
            self.assertEqual(set(result["results"]), {"AAPL", "IBM"})
            self.assertEqual(result["results"]["AAPL"]["bars"]["status"], "equal")
            ibm = result["results"]["IBM"]["bars"]
            self.assertEqual((ibm["compared"], ibm["different"]), (2, 1))
            self.assertEqual(ibm["maximum_absolute_close_difference"], "0.01")
            self.assertFalse(result["results"]["IBM"]["strategy_or_return_computed"])

    def test_absent_or_failed_reference_never_reports_equal(self):
        provider = self.m.Source("normalized-csv", "fixture")
        for state, reason in [("complete", "no_reference_sessions"), ("unavailable", "reference_refused")]:
            reference = self.m.Source("normalized-csv", "fixture", bars_status=state, reason="refused")
            actual = self.m.compare(reference, provider, ["IBM"])["IBM"]["bars"]
            self.assertEqual((actual["status"], actual["reason"], actual["compared"]), ("unavailable", reason, 0))

    def test_unknown_dividend_currency_cannot_establish_cash_units(self):
        event = {"kind": "dividend", "date": "2020-08-07", "distribution": "0.82"}
        action = {"type": "cash_dividend", "ex_date": "2020-08-07", "symbol": "AAPL",
                  "qualification": "qualified", "rate": "0.82"}
        for currency in [None, "", "USD", "EUR"]:
            row = copy.deepcopy(action)
            row["currency"] = currency
            actual = self.m.compare_actions("AAPL", [event], {"status": "complete", "rows": [row]})
            self.assertEqual(actual["numeric_values_equal"], 1)
            self.assertEqual(actual["status"], "equal" if currency == "USD" else "reconciliation_incomplete")
            self.assertEqual(actual["equal"], int(currency == "USD"))

    def test_bounded_aapl_result_keeps_the_original_comparison_contract(self):
        days = json.loads((ROOT / "blueprints/us-equities/alpaca-historical/plan.json").read_text())["expected_session_dates"]
        lean = {"symbol": "AAPL", "observations": [{"date": d, "mapped_symbol": "AAPL", "raw_close": "100.00"} for d in days],
                "events": [{"kind": "dividend", "date": "2020-08-07", "distribution": "0.82"}]}
        stages = {"bars": {"status": "complete", "rows": [{"symbol": "AAPL", "session_date": d, "c": "100.00"} for d in days]},
                  "actions": {"status": "complete", "rows": [{"symbol": "AAPL", "type": "cash_dividend",
                              "ex_date": "2020-08-07", "qualification": "qualified", "rate": "0.82", "currency": None}]}}
        original = self.m.original.compare(lean, stages)
        reference = self.m.Source("lean-probe", "fixture")
        reference.bars = {"AAPL": {r["date"]: r["raw_close"] for r in lean["observations"]}}
        reference.events = {"AAPL": lean["events"]}
        provider = self.m.Source("alpaca-run", "fixture")
        provider.bars = {"AAPL": {r["session_date"]: r["c"] for r in stages["bars"]["rows"]}}
        provider.actions = stages["actions"]
        self.assertEqual(self.m.compare(reference, provider, ["AAPL"], 25)["AAPL"], original)


class MarketDataSourceDispositionsTests(unittest.TestCase):
    def test_both_unindexed_alternatives_have_explicit_pinned_dispositions(self):
        review = json.loads((ROOT / "catalogs/us-equities/market-data-reference-gap-review-20261010.json").read_text())
        entries = {e["repository"]: e for e in review["entries"]}
        sec = entries["https://github.com/SEC-API-io/sec-api-python"]
        quantlab = entries["https://github.com/Rossod4/quantlab"]
        self.assertEqual(sec["disposition"], "keep_but_compare")
        self.assertIn("891443361734c8f09de96750c679e82bd251936d", sec["version_or_commit"])
        self.assertEqual(quantlab["disposition"], "not_adopted")
        self.assertIn("883d893b5f41bec6c1ffa67c88420f5068376e09", quantlab["version_or_commit"])
        self.assertEqual(review["currency_policy"]["decision"], "preserve_unknown")
        self.assertEqual(review["rights_boundary"]["decision"], "account_and_source_rights_unestablished")
        union = json.loads((ROOT / "catalogs/us-equities/decision-index.json").read_text())
        recorded = {r["repository"].lower(): r for r in union["records"]}
        for source in [sec, quantlab]:
            refs = recorded[source["repository"].lower()]["references"]
            matches = [r for r in refs if r["path"] == "catalogs/us-equities/market-data-reference-gap-review-20261010.json"]
            self.assertEqual(len(matches), 1)
            self.assertEqual(matches[0]["disposition"], source["disposition"])


class LaterGapEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.doc = {"source_revision": "a" * 40, "layers": [{"catalog": "us-equities",
                    "layer_id": "market-data-reference", "gaps": [{"index": 5, "text": "missing comparator",
                    "status": "open", "category": "executable_now"}]}]}
        self.write(cm.GAP_CROSSWALK_FILE, self.doc)
        self.artifact = "evidence/artifacts/test/run.txt"
        self.write(self.artifact, "measured fixture result\n")
        self.receipt = {"catalog": "us-equities", "layer_id": "market-data-reference", "gap_index": 5,
                        "source_revision": self.doc["source_revision"],
                        "gap_text_sha256": hashlib.sha256(b"missing comparator").hexdigest(),
                        "outcome": "settled", "residuals": [], "evidence_class": "local_integration",
                        "artifacts": [{"path": self.artifact, "sha256": self.sha(self.artifact)}]}

    def write(self, relative, value):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value if isinstance(value, str) else json.dumps(value), encoding="utf-8")

    def sha(self, relative):
        return hashlib.sha256((self.root / relative).read_bytes()).hexdigest()

    def publish(self, duplicate=False):
        receipt_path = "evidence/artifacts/test/gap-5.json"
        self.write(receipt_path, self.receipt)
        refs = [{"path": receipt_path, "sha256": self.sha(receipt_path)}]
        self.write(cm.GAP_CLOSEOUT_DIR + "/test.json", {"schema_version": 1,
                   "source_revision": self.doc["source_revision"],
                   "crosswalk_sha256": self.sha(cm.GAP_CROSSWALK_FILE),
                   "receipts": refs * (2 if duplicate else 1)})

    def test_settled_receipt_updates_counts_without_mutating_the_frozen_source(self):
        self.publish()
        effective, listed = cm.apply_gap_closeouts(self.root, self.doc)
        self.assertEqual(cm.gap_counts_by_layer(effective)[("us-equities", "market-data-reference")], 0)
        self.assertEqual(self.doc["layers"][0]["gaps"][0]["status"], "open")
        self.assertEqual(listed[("us-equities", "market-data-reference")][0]["outcome"], "settled")

    def test_advanced_and_deferred_receipts_keep_residual_gaps_open(self):
        for outcome in ["advanced", "deferred", "not_settled"]:
            with self.subTest(outcome=outcome):
                self.receipt.update(outcome=outcome, residuals=["needs an authorized source"])
                self.publish()
                effective, listed = cm.apply_gap_closeouts(self.root, self.doc)
                self.assertEqual(cm.gap_counts_by_layer(effective)[("us-equities", "market-data-reference")], 1)
                self.assertEqual(listed[("us-equities", "market-data-reference")][0]["residuals"], self.receipt["residuals"])

    def test_changed_artifact_or_receipt_cannot_remove_a_gap(self):
        self.publish()
        self.write(self.artifact, "changed after the receipt\n")
        with self.assertRaisesRegex(InvalidDecisionIndex, "artifact hash"):
            cm.apply_gap_closeouts(self.root, self.doc)
        self.receipt["artifacts"][0]["sha256"] = self.sha(self.artifact)
        self.publish()
        self.write("evidence/artifacts/test/gap-5.json", {**self.receipt, "outcome": "deferred"})
        with self.assertRaisesRegex(InvalidDecisionIndex, "receipt hash"):
            cm.apply_gap_closeouts(self.root, self.doc)

    def test_wrong_text_duplicate_gap_and_unexplained_partial_are_refused(self):
        self.receipt["gap_text_sha256"] = "0" * 64
        self.publish()
        with self.assertRaisesRegex(InvalidDecisionIndex, "text binding"):
            cm.apply_gap_closeouts(self.root, self.doc)
        self.receipt["gap_text_sha256"] = hashlib.sha256(b"missing comparator").hexdigest()
        self.publish(duplicate=True)
        with self.assertRaisesRegex(InvalidDecisionIndex, "duplicate gap"):
            cm.apply_gap_closeouts(self.root, self.doc)
        self.receipt.update(outcome="advanced", residuals=[])
        self.publish()
        with self.assertRaisesRegex(InvalidDecisionIndex, "residuals"):
            cm.apply_gap_closeouts(self.root, self.doc)


if __name__ == "__main__":
    unittest.main()
