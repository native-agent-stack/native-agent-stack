"""Shared gap-closeout evidence, review-credit and historical-count contracts."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import importlib.metadata
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

try:
    from jsonschema import Draft202012Validator
except ImportError as error:
    raise unittest.SkipTest("jsonschema is not installed; gap-closeout validation controls require it") from error

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
        # Real receipts[] rows carry metadata; only files[] owns hashes/bytes.
        manifest = json.loads((self.root / "manifests/evidence.json").read_text())
        manifest["receipts"] = [{"id": "fixture-run", "kind": "native_run",
            "path": self.evidence_path, "component_ids": ["fixture-vendor"],
            "claim": "Synthetic loader fixture", "limitations": ["not native acceptance"]}]
        write_json(self.root, "manifests/evidence.json", manifest)
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
        # Isolate review credit from the separately pinned real-receipt regression.
        manifest = json.loads((self.root / "manifests/evidence.json").read_text())
        manifest["receipts"] = []
        write_json(self.root, "manifests/evidence.json", manifest)
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
                self.assertEqual(cm.gap_counts_by_layer(current)[("us-equities", "fixture")], 1)
                self.assertEqual(current["layers"][0]["gaps"][0]["category"], "executable_now")
                self.assertEqual(current["layers"][0]["gaps"][0]["closeout_status"], "proposed")

    def test_unreviewed_later_residual_preserves_prior_reviewed_counts(self):
        manifest = json.loads((self.root / "manifests/evidence.json").read_text())
        manifest["receipts"] = []
        write_json(self.root, "manifests/evidence.json", manifest)
        self.save()
        self.closeout["date"] = "2026-10-11"
        self.entry["status"] = "residual"
        self.entry["category"] = "needs_user_login"
        self.entry["reviews"] = []
        self.path = DIRECTORY + "/fixture-2026-10-11.json"
        self.save()
        current = self.current()
        self.assertEqual(cm.open_gap_counts_by_layer(current)[("us-equities", "fixture")], 0)
        self.assertEqual(cm.gap_counts_by_layer(current)[("us-equities", "fixture")], 0)
        self.assertEqual(current["layers"][0]["gaps"][0]["category"], "executable_now")
        self.assertEqual(current["layers"][0]["gaps"][0]["closeout_status"], "proposed")

    def test_reviewed_residual_and_blocked_keep_their_explicit_category(self):
        for status in ("residual", "blocked"):
            with self.subTest(status=status):
                self.entry["status"] = status
                self.entry["category"] = "needs_user_login"
                self.save()
                current = self.current()
                self.assertEqual(cm.open_gap_counts_by_layer(current)[("us-equities", "fixture")], 1)
                self.assertEqual(cm.gap_counts_by_layer(current)[("us-equities", "fixture")], 0)
                self.assertEqual(current["layers"][0]["gaps"][0]["closeout_status"], status)

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

    def test_receipt_metadata_uses_the_registered_file_hash(self):
        manifest = json.loads((self.root / "manifests/evidence.json").read_text())
        self.assertEqual(set(manifest["receipts"][0]),
                         {"id", "kind", "path", "component_ids", "claim", "limitations"})
        self.assertNotIn("sha256", manifest["receipts"][0])
        self.assertNotIn("bytes", manifest["receipts"][0])
        self.save()
        self.assertEqual(cm.gap_counts_by_layer(self.current())[("us-equities", "fixture")], 0)

    def test_conflicting_file_hash_registration_is_refused(self):
        manifest = json.loads((self.root / "manifests/evidence.json").read_text())
        record = next(r for r in manifest["files"] if r["path"] == self.evidence_path)
        manifest["files"].append({**record, "sha256": "0" * 64})
        write_json(self.root, "manifests/evidence.json", manifest)
        self.save()
        with self.assertRaisesRegex(InvalidDecisionIndex, "conflicting evidence registration"):
            self.current()

    def test_conflicting_receipt_hash_mirror_is_refused(self):
        manifest = json.loads((self.root / "manifests/evidence.json").read_text())
        record = next(r for r in manifest["files"] if r["path"] == self.evidence_path)
        for fields in ({"sha256": "0" * 64}, {"sha256": "0" * 64, "bytes": record["bytes"]}):
            with self.subTest(fields=sorted(fields)):
                candidate = deepcopy(manifest)
                candidate["receipts"][0].update(fields)
                write_json(self.root, "manifests/evidence.json", candidate)
                self.save()
                with self.assertRaisesRegex(InvalidDecisionIndex, "conflicting receipt mirror"):
                    self.current()
                self.assertEqual(cm.open_gap_counts_by_layer(self.historical)[("us-equities", "fixture")], 1)

    def test_conflicting_receipt_byte_mirror_is_refused(self):
        manifest = json.loads((self.root / "manifests/evidence.json").read_text())
        record = next(r for r in manifest["files"] if r["path"] == self.evidence_path)
        for fields in ({"bytes": record["bytes"] + 1},
                       {"bytes": record["bytes"] + 1, "sha256": record["sha256"]}):
            with self.subTest(fields=sorted(fields)):
                candidate = deepcopy(manifest)
                candidate["receipts"][0].update(fields)
                write_json(self.root, "manifests/evidence.json", candidate)
                self.save()
                with self.assertRaisesRegex(InvalidDecisionIndex, "conflicting receipt mirror"):
                    self.current()
                self.assertEqual(cm.open_gap_counts_by_layer(self.historical)[("us-equities", "fixture")], 1)

    def test_matching_receipt_mirrors_keep_file_registration_authoritative(self):
        manifest = json.loads((self.root / "manifests/evidence.json").read_text())
        record = next(r for r in manifest["files"] if r["path"] == self.evidence_path)
        for fields in (("sha256",), ("bytes",), ("sha256", "bytes")):
            with self.subTest(fields=fields):
                candidate = deepcopy(manifest)
                candidate["receipts"][0].update({field: record[field] for field in fields})
                write_json(self.root, "manifests/evidence.json", candidate)
                self.save()
                self.assertEqual(cm.open_gap_counts_by_layer(self.current())[("us-equities", "fixture")], 0)
                self.assertEqual(candidate["files"], manifest["files"])

    def test_importable_wrong_jsonschema_version_is_refused_before_loading_documents(self):
        self.save()
        before = deepcopy(self.historical)
        self.assertTrue(callable(Draft202012Validator))
        with patch("importlib.metadata.version", return_value="4.19.2"), \
                patch.object(cm, "load", wraps=cm.load) as load_document:
            with self.assertRaisesRegex(InvalidDecisionIndex,
                                        r"jsonschema==4\.26\.0.*4\.19\.2.*requirements-ci\.txt"):
                self.current()
            load_document.assert_not_called()
        self.assertEqual(self.historical, before)
        self.assertEqual(cm.open_gap_counts_by_layer(self.historical)[("us-equities", "fixture")], 1)

    def test_missing_jsonschema_distribution_is_actionable_before_loading_documents(self):
        self.save()
        with patch("importlib.metadata.version",
                   side_effect=importlib.metadata.PackageNotFoundError("jsonschema")), \
                patch.object(cm, "load", wraps=cm.load) as load_document:
            with self.assertRaisesRegex(InvalidDecisionIndex,
                                        r"jsonschema==4\.26\.0.*missing.*requirements-ci\.txt"):
                self.current()
            load_document.assert_not_called()
        self.assertEqual(cm.open_gap_counts_by_layer(self.historical)[("us-equities", "fixture")], 1)

    def test_unregistered_closeout_is_refused(self):
        self.save()
        manifest = json.loads((self.root / "manifests/evidence.json").read_text())
        manifest["files"] = [r for r in manifest["files"] if r["path"] != self.path]
        write_json(self.root, "manifests/evidence.json", manifest)
        with self.assertRaisesRegex(InvalidDecisionIndex, "unregistered closeout"):
            self.current()

    def test_nonopen_historical_gap_is_refused(self):
        self.historical["layers"][0]["gaps"][0]["status"] = "settled_by_receipt"
        self.closeout["source_crosswalk_sha256"] = write_json(
            self.root, cm.GAP_CROSSWALK_FILE, self.historical)
        self.save()
        with self.assertRaisesRegex(InvalidDecisionIndex, "not an open historical gap"):
            self.current()

    def test_filename_must_match_the_declared_layer_and_date(self):
        self.path = DIRECTORY + "/fixture-2026-10-11.json"
        self.save()
        with self.assertRaisesRegex(InvalidDecisionIndex, "filename"):
            self.current()

    def test_calendar_date_must_exist(self):
        self.closeout["date"] = "2026-02-30"
        self.path = DIRECTORY + "/fixture-2026-02-30.json"
        self.save()
        with self.assertRaisesRegex(InvalidDecisionIndex, "invalid gap closeout date"):
            self.current()

    def test_historical_layer_must_exist(self):
        self.closeout["layer_id"] = "absent-layer"
        self.path = DIRECTORY + "/absent-layer-2026-10-10.json"
        self.save()
        with self.assertRaisesRegex(InvalidDecisionIndex, "historical layer"):
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
        with patch("importlib.metadata.version", side_effect=AssertionError("no-record path queried metadata")):
            current = loader(self.root, historical) if loader else deepcopy(historical)
        self.assertEqual(current, historical)
        self.assertEqual(cm.gap_counts_by_layer(current), cm.gap_counts_by_layer(historical))
        self.assertEqual(cm.open_gap_counts_by_layer(current), cm.open_gap_counts_by_layer(historical))
        self.assertEqual((ROOT / cm.GAP_CROSSWALK_FILE).read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
