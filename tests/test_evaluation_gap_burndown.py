"""Receipt-backed gap accounting and replay of the retained evaluation comparison."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from scripts import component_matrix as cm
from scripts.catalog_decisions import InvalidDecisionIndex

ROOT = Path(__file__).resolve().parents[1]
WAVE = "evidence/artifacts/gap-wave2-20260923/us-equities__evaluation-experiments"


def write_json(root, relative, value):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) + "\n")
    return {"path": relative, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def fixture(root, outcome="settled"):
    text = "No retained native evaluation execution."
    digest = hashlib.sha256(text.encode()).hexdigest()
    raw = write_json(root, "evidence/artifacts/probe/output.json", {"passed": 8})
    receipt = write_json(root, "evidence/artifacts/probe/receipt.json", {
        "gap_index": 0, "gap_text_sha256": digest, "outcome": outcome,
        "evidence_class": "local_integration", "raw_outputs": [raw],
    })
    review = write_json(root, "evidence/artifacts/probe/review.json", {"verdict": outcome})
    verification = write_json(root, "evidence/artifacts/probe/verification.json", {"exit_code": 0})
    ledger = {
        "schema_version": 1, "catalog": "us-equities", "layer_id": "evaluation-experiments",
        "checked_at": "2026-10-10", "review": review, "verification": verification,
        "gaps": [{"index": 0, "gap_text_sha256": digest, "outcome": outcome,
                  "receipt": receipt, "reason": "Native run retained; bounded fixture only."}],
    }
    write_json(root, "catalogs/landscape/gap-burndown-probe.json", ledger)
    crosswalk = {"layers": [{"catalog": "us-equities", "layer_id": "evaluation-experiments",
        "gaps": [{"index": 0, "text": text, "status": "open", "category": "executable_now"},
                 {"index": 1, "text": "Independent domain test still owed.",
                  "status": "open", "category": "executable_now"}]}]}
    return crosswalk, ledger


class GapBurndownTests(unittest.TestCase):
    def test_verified_receipt_changes_the_matrix_count_without_rewriting_history(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            crosswalk, _ = fixture(root)
            effective, joins = cm.apply_gap_burndown(root, crosswalk)
            key = ("us-equities", "evaluation-experiments")
            self.assertEqual(cm.gap_counts_by_layer(effective)[key], 1)
            self.assertEqual(cm.open_gap_counts_by_layer(effective)[key], 1)
            self.assertEqual(crosswalk["layers"][0]["gaps"][0]["status"], "open")
            self.assertEqual(joins[key][0]["outcome"], "settled")

    def test_partial_receipt_keeps_the_entire_gap_open(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            crosswalk, _ = fixture(root, "advanced")
            effective, _ = cm.apply_gap_burndown(root, crosswalk)
            self.assertEqual(cm.gap_counts_by_layer(effective)[("us-equities", "evaluation-experiments")], 2)

    def test_absent_burndown_keeps_the_original_accounting(self):
        with tempfile.TemporaryDirectory() as directory:
            doc = {"layers": []}
            self.assertEqual(cm.apply_gap_burndown(Path(directory), doc), (doc, {}))

    def test_invalid_bindings_cannot_remove_an_open_gap(self):
        for damage in ("missing_receipt", "receipt_bytes", "raw_bytes", "gap_text", "false_settlement"):
            with self.subTest(damage=damage), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                crosswalk, ledger = fixture(root)
                receipt_path = root / ledger["gaps"][0]["receipt"]["path"]
                if damage == "missing_receipt":
                    receipt_path.unlink()
                elif damage == "receipt_bytes":
                    receipt_path.write_text("{}")
                elif damage == "raw_bytes":
                    (root / "evidence/artifacts/probe/output.json").write_text("{}")
                elif damage == "gap_text":
                    crosswalk["layers"][0]["gaps"][0]["text"] = "A different acceptance question."
                else:
                    receipt = json.loads(receipt_path.read_text())
                    receipt["outcome"] = "advanced"
                    ledger["gaps"][0]["receipt"] = write_json(root, str(receipt_path.relative_to(root)), receipt)
                    write_json(root, "catalogs/landscape/gap-burndown-probe.json", ledger)
                with self.assertRaises(InvalidDecisionIndex):
                    cm.apply_gap_burndown(root, crosswalk)


class RetainedComparisonTests(unittest.TestCase):
    def test_published_matrix_counts_all_and_only_complete_settlements(self):
        document, violations = cm.build_document(ROOT)
        self.assertFalse(violations)
        row = next(r for r in document["rows"] if r["catalog"] == "us-equities"
                   and r["layer_id"] == "evaluation-experiments")
        ledger = json.loads((ROOT / "catalogs/landscape/gap-burndown-20261010-evaluation-experiments.json").read_text())
        settled = {g["index"] for g in ledger["gaps"] if g["outcome"] == "settled"}
        original = json.loads((ROOT / cm.GAP_CROSSWALK_FILE).read_text())
        layer = next(l for l in original["layers"] if l["catalog"] == row["catalog"]
                     and l["layer_id"] == row["layer_id"])
        remaining = [g for g in layer["gaps"] if g["status"] == "open" and g["index"] not in settled]
        self.assertEqual(row["open_gaps"], len(remaining))
        self.assertEqual(row["open_executable_now_gaps"],
                         sum(g["category"] == "executable_now" for g in remaining))

    def test_published_error_log_and_resume_comparison_reproduce(self):
        raw = ROOT / WAVE / "raw/0"
        result = subprocess.run([
            "python3", str(ROOT / "blueprints/gap-wave2-20260923/us-equities__evaluation-experiments/compare_two_arm.py"),
            str(raw / "run"), str(ROOT),
        ], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), json.loads((raw / "comparison.json").read_text()))


if __name__ == "__main__":
    unittest.main()
