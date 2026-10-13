"""Specific production-path controls for the first angle-record review round.

All receipts here are synthetic fixtures. Fresh-output controls distinguish
an evidence rejection from the unrelated source-drift rejection.
"""

import copy
import json
from pathlib import Path
import unittest
from unittest import mock

from scripts import angle_records as ar
from scripts import final_stack as fs
from tests import test_final_stack as helpers
from tests.test_final_stack import (
    COMMIT_A, COMMIT_B, FixtureTestCase,
    REPO_ROOT, _angle_fixture, _sweep, _write, _write_json,
)


class FinalFix1Tests(FixtureTestCase):
    prepare = helpers.AngleEnforcementTests.prepare

    def measured(self):
        root, path, record = self.prepare(final=True)
        c = record["candidates"][0]
        c.update(a6_comparative=True, provisional=False)
        paired = "evidence/artifacts/fixture/paired.json"
        c["angles"]["A6"].update(score="+", sources=[{"kind": "receipt", "path": paired}])
        arms = []
        for ident in ("a", "b"):
            native = f"evidence/artifacts/fixture/arm-{ident}.txt"
            _write(root / native, "Synthetic native-result stand-in.\n")
            arms.append({"id": ident, "native_output": native})
        _write_json(root / paired, {"kind": "comparative", "evidence_class": "native_proven",
            "completed": True, "harness": "paired", "repository": c["repository"], "pin": c["pin"],
            "confounds": ["Synthetic control; no real candidate measurement."], "arms": arms})
        _write_json(path, record)
        return root, path, record

    def fresh_reject(self, root, reason):
        try:
            document = fs.build_document(root)
        except fs.FinalStackError:
            pass
        else:
            _write(root / fs.OUTPUT, fs.serialize(document))
        code, output = self.run_main(root, "--check")
        self.assertEqual(code, 1, output)
        self.assertIn(reason, output)

    def edit_receipt(self, root, record, field, mutate):
        path = root / record["final_evidence"][0][field]
        value = json.loads(path.read_bytes())
        mutate(value)
        _write_json(path, value)

    def test_version_only_run_cannot_bridge_conflicting_commit_receipts(self):
        root, path, record = self.measured()
        stack = json.loads((root / fs.STACK).read_bytes())
        del stack["components"][0]["source_pin"]
        _write_json(root / fs.STACK, stack)
        source = root / "catalogs/landscape/foundation.json"
        doc = json.loads(source.read_bytes())
        selected = "1.0.0 @ " + COMMIT_A
        doc["layers"][0]["winners"][0]["pin"] = selected
        _write_json(source, doc)
        record["candidates"][0]["pin"] = selected
        record["final_evidence"][0]["run_pin"] = selected
        paired = root / "evidence/artifacts/fixture/paired.json"
        comparison = json.loads(paired.read_bytes())
        comparison["pin"] = selected
        _write_json(paired, comparison)
        for field in ("e2e_receipt", "invoke_receipt"):
            self.edit_receipt(root, record, field, lambda r: r.update(pin="1.0.0 @ " + COMMIT_B))
        self.edit_receipt(root, record, "e2e_receipt",
                          lambda r: r["upstream_sources"][0].update(pin="1.0.0 @ " + COMMIT_B))
        _write_json(path, record)
        self.fresh_reject(root, "complete FINAL pin identity")

    def test_malformed_citations_and_commands_are_rejected(self):
        mutations = [
            lambda r: r["upstream_sources"][0].update(path=True, line=True),
            lambda r: r["upstream_sources"][0].update(path="../outside", line=-1),
            lambda r: r["upstream_sources"][0].update(line=0),
            lambda r: r["upstream_sources"].append("not a citation"),
            lambda r: r["commands"][0].update(command=True),
            lambda r: r["commands"][0].update(command="   "),
            lambda r: r["commands"].append("not a command record"),
        ]
        for index, mutation in enumerate(mutations):
            with self.subTest(index=index):
                root, _, record = self.measured()
                self.edit_receipt(root, record, "e2e_receipt", mutation)
                self.fresh_reject(root, "condition 3 receipt has invalid commands or citations")

    def test_any_conflicting_final_marker_is_rejected(self):
        for marker in ("angle", "alias"):
            with self.subTest(marker=marker):
                root, path, record = self.measured()
                source = root / "catalogs/landscape/foundation.json"
                doc = json.loads(source.read_bytes())
                doc["layers"][0]["terminal_state"] = "TRIAL"
                if marker == "angle":
                    record["terminal_state"] = "FINAL"
                else:
                    doc["layers"][0]["verdict_status"] = "FINAL"
                _write_json(source, doc)
                _write_json(path, record)
                self.fresh_reject(root, "conflicting terminal-state claims")

    def test_final_requires_non_provisional_measured_convergence(self):
        root, path, record = self.prepare(final=True)
        c = record["candidates"][0]
        c.update(a6_comparative=False, provisional=True)
        c["angles"]["A6"].update(score="U", sources=[])
        _write_json(path, record)
        self.fresh_reject(root, "NON-provisional CONVERGED")

    def test_reopened_matrix_layer_cannot_be_final(self):
        root, _, _ = self.measured()
        ledger = json.loads((root / fs.LEDGER).read_bytes())
        later = _sweep("changed", "2026-09-23", [("foundation", "layer-a")])
        ledger["sweeps"].append(later)
        _write_json(root / fs.LEDGER, ledger)
        _write_json(root / later["manifest_ref"], {"checked_at": later["date"]})
        matrix = json.loads((root / fs.MATRIX).read_bytes())
        matrix["rows"][0]["convergence"].update(layer_state="recorded_reopened",
            reopened_by=[{"sweep_id": "changed", "date": "2026-09-23"}])
        _write_json(root / fs.MATRIX, matrix)
        self.fresh_reject(root, "reopened sweep delta must be adjudicated")

    def test_final_eligible_false_cannot_freeze_an_otherwise_measured_winner(self):
        root, path, record = self.measured()
        # Permit the newly specified neutral metadata in the synthetic schema,
        # so this control reaches production FINAL enforcement on the old head.
        schema_path = root / ar.SCHEMA
        schema = json.loads(schema_path.read_bytes())
        schema["$defs"]["candidate"]["properties"].update(
            trial_permitted={"type": "boolean"}, final_eligible={"type": "boolean"},
            basis={"const": "operator decision, recorded privately"})
        _write_json(schema_path, schema)
        record["candidates"][0].update(trial_permitted=True, final_eligible=False,
                                      basis="operator decision, recorded privately")
        _write_json(path, record)
        self.fresh_reject(root, "final_eligible is false")

    def test_unverified_entitlement_cannot_be_final(self):
        root, path, record = self.measured()
        record["candidates"][0]["entitlement"] = {"status": "pending",
            "sources": record["candidates"][0]["angles"]["A1"]["sources"],
            "note": "Synthetic unverified entitlement."}
        _write_json(path, record)
        self.fresh_reject(root, "entitlement remains unverified")

    def test_final_alias_obtains_the_recorded_review_date(self):
        root, _, _ = self.measured()
        source = root / "catalogs/landscape/foundation.json"
        doc = json.loads(source.read_bytes())
        doc["layers"][0]["verdict_status"] = "FINAL"
        _write_json(source, doc)
        document = fs.build_document(root)
        self.assertEqual(self.layer(document, "layer-a")["verdict"]["next_review"], "2026-10-22")
        _write(root / fs.OUTPUT, fs.serialize(document))
        code, output = self.run_main(root, "--check")
        self.assertEqual(code, 0, output)


class RecordFix1Tests(FixtureTestCase):
    prepare = helpers.AngleEnforcementTests.prepare

    def test_neutral_trial_fields_do_not_change_derivation_or_arm_list(self):
        record = _angle_fixture()
        candidate = record["candidates"][0]
        before = ar.derive(record, candidate)
        ids = [c["id"] for c in record["candidates"]]
        candidate.update(trial_permitted=True, final_eligible=False,
                         basis="operator decision, recorded privately")
        schema = json.loads((REPO_ROOT / ar.SCHEMA).read_text())
        ar.validate_record(record, schema, label="synthetic")
        self.assertEqual(ar.derive(record, candidate), before)
        self.assertEqual([c["id"] for c in record["candidates"]], ids)

    def test_screened_unknown_whitespace_and_malformed_pins_are_rejected(self):
        for pin in ("UNKNOWN", "   ", "deadbeef", "1.0 @ not-a-commit", "HEAD"):
            with self.subTest(pin=pin):
                root, path, record = self.prepare()
                record["candidates"][0]["pin"] = pin
                _write_json(path, record)
                try:
                    _write(root / fs.OUTPUT, fs.serialize(fs.build_document(root)))
                except fs.FinalStackError:
                    pass
                code, output = self.run_main(root, "--check")
                self.assertEqual(code, 1, output)
                self.assertIn("A1 screen requires a resolved pin identity", output)

    def test_invalid_time_has_clean_refusal_without_format_extras(self):
        root, path, record = self.prepare()
        bad_value = "invalid-time-valueZ"
        record["weights_stated_at"] = bad_value
        _write_json(path, record)
        with mock.patch.dict(ar.FormatChecker.checkers, {}, clear=True):
            try:
                _write(root / fs.OUTPUT, fs.serialize(fs.build_document(root)))
            except fs.FinalStackError:
                pass
            code, output = self.run_main(root, "--check")
        self.assertEqual(code, 1, output)
        self.assertIn("invalid UTC timestamp", output)
        self.assertNotIn(bad_value, output)
        self.assertNotIn("Traceback", output)

    def test_bad_https_url_has_clean_refusal_without_format_extras(self):
        root, path, record = self.prepare()
        record["candidates"][0]["angles"]["A1"]["sources"][0]["url"] = "https:///missing-host"
        _write_json(path, record)
        with mock.patch.dict(ar.FormatChecker.checkers, {}, clear=True):
            code, output = self.run_main(root, "--check")
        self.assertEqual(code, 1, output)
        self.assertIn("invalid HTTPS source URL", output)

    def test_weights_precede_source_compliance_and_entitlement_reads(self):
        for location in ("source", "licence", "entitlement"):
            with self.subTest(location=location):
                root, path, record = self.prepare()
                c = record["candidates"][0]
                old_time = "2026-10-12T21:32:22Z"
                source = {"kind": "url", "url": "https://example.org/fixture", "read_at": old_time}
                if location == "source":
                    c["angles"]["A1"]["sources"] = [source]
                elif location == "licence":
                    c["licence_note"] = {"spdx_id": "MIT", "source": source,
                                         "read_at": old_time, "note": "Synthetic compliance note."}
                else:
                    c["entitlement"] = {"status": "documented", "sources": [source],
                                        "note": "Synthetic source read."}
                _write_json(path, record)
                try:
                    _write(root / fs.OUTPUT, fs.serialize(fs.build_document(root)))
                except fs.FinalStackError:
                    pass
                code, output = self.run_main(root, "--check")
                self.assertEqual(code, 1, output)
                self.assertIn("weights must precede every read time", output)


class RetainedSourcesFix1Tests(unittest.TestCase):
    def test_every_committed_url_and_read_time_has_a_receipt_locator(self):
        captured = set()

        def walk(value):
            if isinstance(value, dict):
                if "url" in value and "read_at" in value:
                    yield value["url"], value["read_at"]
                for child in value.values():
                    yield from walk(child)
            elif isinstance(value, list):
                for child in value:
                    yield from walk(child)

        folder = REPO_ROOT / "evidence/artifacts/angle-records-20261012"
        for path in folder.glob("*source-reads.json"):
            captured.update(walk(json.loads(path.read_bytes())))
        for path in (REPO_ROOT / ar.DIRECTORY).glob("foundation-*.json"):
            for source in walk(json.loads(path.read_bytes())):
                self.assertIn(source, captured, "URL source/read time lacks its retained receipt locator")


if __name__ == "__main__":
    unittest.main()
