"""Shared gap-closeout evidence, review-credit and historical-count contracts."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from scripts import component_matrix as cm
from scripts.catalog_decisions import InvalidDecisionIndex
from scripts.host_receipts import register_file


ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = "catalogs/landscape/gap-closeouts"
SCHEMA = DIRECTORY + "/schema.json"


def write_json(root, path, value):
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    return hashlib.sha256(target.read_bytes()).hexdigest()


class GapCloseoutTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.historical = {"layers": [{"catalog": "us-equities", "layer_id": "fixture",
            "gaps": [{"index": 0, "text": "No retained native fixture run.",
                      "status": "open", "category": "executable_now"}]}]}
        crosswalk_hash = write_json(self.root, cm.GAP_CROSSWALK_FILE, self.historical)
        write_json(self.root, "manifests/evidence.json", {"files": [], "receipts": []})
        # Before the feature exists, the required tests still reach the old public
        # matrix build: silently ignoring the closeout must fail each refusal case.
        if (ROOT / SCHEMA).is_file():
            (self.root / DIRECTORY).mkdir(parents=True)
            (self.root / SCHEMA).write_bytes((ROOT / SCHEMA).read_bytes())
        self.evidence_path = "evidence/artifacts/fixture/run.json"
        evidence_hash = write_json(self.root, self.evidence_path, {"exit_code": 0})
        register_file(self.root, self.evidence_path)
        self.reviews = []
        for family in ("gpt", "claude"):
            path = "evidence/artifacts/fixture/" + family + "-review.json"
            digest = write_json(self.root, path,
                                {"family": family, "head": "a" * 40, "verdict": "pass"})
            register_file(self.root, path)
            self.reviews.append({"path": path, "sha256": digest,
                                 "family": family, "head": "a" * 40})
        self.entry = {
            "index": 0, "status": "settled", "reason": "The retained native run passed.",
            "source_text_sha256": hashlib.sha256(
                self.historical["layers"][0]["gaps"][0]["text"].encode()).hexdigest(),
            "evidence": [{"path": self.evidence_path, "sha256": evidence_hash}],
            "vendor_paths": [{"repository": "https://github.com/example/vendor",
                              "pin": "v1.0.0", "path": "examples/native.py"}],
            "reviews": self.reviews,
        }
        self.closeout = {"schema_version": 1, "catalog": "us-equities", "layer_id": "fixture",
                         "date": "2026-10-10", "source_crosswalk_sha256": crosswalk_hash,
                         "gaps": [self.entry]}
        self.path = DIRECTORY + "/fixture-2026-10-10.json"

    def save(self):
        write_json(self.root, self.path, self.closeout)
        register_file(self.root, self.path)

    def current(self):
        # This fallback measures the pre-change behaviour without pinning a test
        # to a transient PR commit or raising merely because a helper is missing.
        loader = getattr(cm, "current_gap_document", None)
        return loader(self.root, self.historical) if loader else deepcopy(self.historical)

    def test_unregistered_evidence_is_refused(self):
        manifest = json.loads((self.root / "manifests/evidence.json").read_text())
        manifest["files"] = [r for r in manifest["files"] if r["path"] != self.evidence_path]
        write_json(self.root, "manifests/evidence.json", manifest)
        self.save()
        with self.assertRaisesRegex(InvalidDecisionIndex, "unregistered"):
            self.current()

    def test_missing_reason_is_refused(self):
        del self.entry["reason"]
        self.save()
        with self.assertRaisesRegex(InvalidDecisionIndex, "reason"):
            self.current()

    def test_unknown_status_is_refused(self):
        self.entry["status"] = "looks_done"
        self.save()
        with self.assertRaisesRegex(InvalidDecisionIndex, "status"):
            self.current()

    def test_two_passing_families_settle_without_mutating_history(self):
        before = deepcopy(self.historical)
        self.save()
        current = self.current()
        self.assertEqual(cm.gap_counts_by_layer(current)[("us-equities", "fixture")], 0)
        self.assertEqual(cm.open_gap_counts_by_layer(current)[("us-equities", "fixture")], 0)
        self.assertEqual(self.historical, before)

    def test_proposed_and_residual_and_blocked_stay_open(self):
        for status in ("proposed", "residual", "blocked"):
            with self.subTest(status=status):
                self.entry["status"] = status
                self.entry["reviews"] = []
                if status == "proposed":
                    self.entry.pop("category", None)
                else:
                    self.entry["category"] = "needs_user_login"
                self.save()
                current = self.current()
                self.assertEqual(cm.open_gap_counts_by_layer(current)[("us-equities", "fixture")], 1)
                self.assertEqual(cm.gap_counts_by_layer(current)[("us-equities", "fixture")],
                                 1 if status == "proposed" else 0)

    def test_settled_requires_both_families_at_the_same_head(self):
        for variant in ("one_family", "different_head", "changes_requested", "false_metadata"):
            with self.subTest(variant=variant):
                self.entry["reviews"] = deepcopy(self.reviews)
                if variant == "one_family":
                    self.entry["reviews"] = self.entry["reviews"][:1]
                else:
                    review = self.entry["reviews"][1]
                    report = {"family": "claude", "head": "a" * 40, "verdict": "pass"}
                    if variant == "different_head":
                        report["head"] = review["head"] = "b" * 40
                    elif variant == "changes_requested":
                        report["verdict"] = "changes_requested"
                    else:
                        report["family"] = "gpt"
                    review["sha256"] = write_json(self.root, review["path"], report)
                    register_file(self.root, review["path"])
                self.save()
                with self.assertRaises(InvalidDecisionIndex):
                    self.current()

    def test_changed_evidence_and_historical_bindings_are_refused(self):
        self.save()
        (self.root / self.evidence_path).write_text("changed", encoding="utf-8")
        with self.assertRaisesRegex(InvalidDecisionIndex, "evidence"):
            self.current()
        write_json(self.root, self.evidence_path, {"exit_code": 0})
        self.closeout["source_crosswalk_sha256"] = "0" * 64
        self.save()
        with self.assertRaisesRegex(InvalidDecisionIndex, "crosswalk"):
            self.current()
        self.closeout["source_crosswalk_sha256"] = hashlib.sha256(
            (self.root / cm.GAP_CROSSWALK_FILE).read_bytes()).hexdigest()
        self.entry["source_text_sha256"] = "0" * 64
        self.save()
        with self.assertRaisesRegex(InvalidDecisionIndex, "source text"):
            self.current()

    def test_receipt_can_be_registered_in_both_manifest_sections(self):
        manifest = json.loads((self.root / "manifests/evidence.json").read_text())
        record = next(r for r in manifest["files"] if r["path"] == self.evidence_path)
        manifest["receipts"] = [{**record, "kind": "native_proven"}]
        write_json(self.root, "manifests/evidence.json", manifest)
        self.save()
        self.assertEqual(cm.gap_counts_by_layer(self.current())[("us-equities", "fixture")], 0)
        manifest["receipts"][0]["sha256"] = "0" * 64
        write_json(self.root, "manifests/evidence.json", manifest)
        with self.assertRaisesRegex(InvalidDecisionIndex, "conflicting evidence registration"):
            self.current()

    def test_unknown_or_duplicate_gap_index_is_refused(self):
        for entries in ([{**self.entry, "index": 4}], [self.entry, self.entry]):
            self.closeout["gaps"] = entries
            self.save()
            with self.assertRaisesRegex(InvalidDecisionIndex, "gap index"):
                self.current()

    def test_schema_uses_upstream_integer_and_exact_digest_constraints(self):
        for key, value in (("index", True), ("source_text_sha256", "a" * 64 + "\n"),
                           ("reason", "   ")):
            with self.subTest(field=key):
                original = self.entry[key]
                self.entry[key] = value
                self.save()
                with self.assertRaises(InvalidDecisionIndex):
                    self.current()
                self.entry[key] = original

    def test_dated_later_residual_reopens_the_gap(self):
        self.save()
        self.closeout["date"] = "2026-10-11"
        self.entry["status"] = "residual"
        self.entry["category"] = "needs_hardware"
        self.entry["reason"] = "The qualified off-host run is still missing."
        self.path = DIRECTORY + "/fixture-2026-10-11.json"
        self.save()
        current = self.current()
        self.assertEqual(cm.open_gap_counts_by_layer(current)[("us-equities", "fixture")], 1)
        self.assertEqual(current["layers"][0]["gaps"][0]["category"], "needs_hardware")

    def test_public_matrix_build_consumes_shared_closeouts(self):
        self.save()
        from tests.test_component_matrix import _init_root, _layer
        _init_root(self.root, [_layer("fixture", catalog="us-equities")],
                   catalog_file="us-equities.json")
        # _init_root writes an empty registry, so explicitly restore each fixture binding.
        for path in [self.evidence_path, *(r["path"] for r in self.reviews), self.path]:
            register_file(self.root, path)
        document, violations = cm.build_document(self.root)
        self.assertFalse(violations)
        self.assertEqual(document["rows"][0]["open_executable_now_gaps"], 0)

    def test_no_closeouts_preserve_current_historical_counts_and_bytes(self):
        historical = json.loads((ROOT / cm.GAP_CROSSWALK_FILE).read_text())
        before = (ROOT / cm.GAP_CROSSWALK_FILE).read_bytes()
        loader = getattr(cm, "current_gap_document", None)
        # Use today's real historical data in a fixture with no dated records;
        # future layer closeouts must not make this baseline contract obsolete.
        current = loader(self.root, historical) if loader else deepcopy(historical)
        self.assertEqual(current, historical)
        self.assertEqual(cm.gap_counts_by_layer(current), cm.gap_counts_by_layer(historical))
        self.assertEqual(cm.open_gap_counts_by_layer(current), cm.open_gap_counts_by_layer(historical))
        self.assertEqual((ROOT / cm.GAP_CROSSWALK_FILE).read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
