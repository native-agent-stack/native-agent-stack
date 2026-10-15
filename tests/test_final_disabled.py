"""FINAL admission stays disabled while its evidence rules are redesigned.

The retained-return cases reproduce the parent-head admission defect using
synthetic fixtures. They do not repair or bypass the disabled admission gate.
"""

import json

from scripts import final_stack as fs
from tests.test_angle_records_fix3 import FinalIntegrityTests
from tests.test_final_stack import FixtureTestCase, _write_json


class FinalDisabledTests(FixtureTestCase):
    prepare = FinalIntegrityTests.prepare
    measured = FinalIntegrityTests.measured
    sweep = FinalIntegrityTests.sweep
    matrix = FinalIntegrityTests.matrix

    def assert_admission_disabled(self, root):
        for mode in ("--write", "--check"):
            with self.subTest(mode=mode):
                code, output = self.run_main(root, mode)
                self.assertEqual(code, 1, output)
                self.assertIn("admission under redesign", output)
                self.assertFalse((root / fs.OUTPUT).exists())

    def unretained_returns(self, votes):
        root, _, _ = self.measured()
        self.sweep(root, "2026-09-23", ident="unretained-after")
        path = root / fs.LEDGER
        ledger = json.loads(path.read_bytes())
        row = ledger["sweeps"][-1]["layers"][0]
        row.update(votes=votes, votes_note="Synthetic control: discovery returns were unavailable.")
        row.pop("discovery_ref", None)
        _write_json(path, ledger)
        self.matrix(root)
        self.assert_admission_disabled(root)

    def test_not_retained_post_anchor_returns_refuse_admission(self):
        self.unretained_returns("not_retained")

    def test_not_returned_post_anchor_returns_refuse_admission(self):
        self.unretained_returns("not_returned")

    def test_all_final_markers_refuse_even_with_complete_evidence(self):
        for marker in ("catalog_terminal", "catalog_alias", "angle", "conflicting_claims"):
            with self.subTest(marker=marker):
                root, path, record = self.measured()
                source = root / "catalogs/landscape/foundation.json"
                catalog = json.loads(source.read_bytes())
                row = catalog["layers"][0]
                row.pop("terminal_state", None)
                record.pop("terminal_state", None)
                if marker == "catalog_alias":
                    row["verdict_status"] = "FINAL"
                elif marker == "angle":
                    record["terminal_state"] = "FINAL"
                else:
                    row["terminal_state"] = "FINAL"
                    if marker == "conflicting_claims":
                        record["terminal_state"] = "NON_TERMINAL"
                _write_json(source, catalog)
                _write_json(path, record)
                self.matrix(root)
                self.assert_admission_disabled(root)

    def test_enforcement_refuses_final_for_every_catalog_without_admission_evidence(self):
        for catalog in ("foundation", "us-equities", "skills", "planned"):
            with self.subTest(catalog=catalog):
                layer = {"catalog": catalog, "layer_id": "fixture", "terminal_state": "FINAL",
                         "status": "current", "survivors": [], "winners": []}
                with self.assertRaisesRegex(fs.FinalStackError, "^admission under redesign$"):
                    fs.enforce_final(None, [layer], [], {})

    def test_disabled_admission_preserves_existing_output(self):
        root, _, _ = self.measured()
        previous = b"A retained preexisting artifact must not be overwritten.\n"
        path = root / fs.OUTPUT
        path.write_bytes(previous)
        for mode in ("--write", "--check"):
            code, output = self.run_main(root, mode)
            self.assertEqual(code, 1, output)
            self.assertIn("admission under redesign", output)
            self.assertEqual(path.read_bytes(), previous)

    def test_unrun_registration_final_claim_refuses_before_wave_resolution(self):
        from tests.test_registration_rules import registration

        root = self.root()
        row = registration()
        verdict = fs.build_verdict(row, {}, {}, [], root=root)
        self.assertIsNone(verdict["wave"])
        self.assertIsNone(verdict["wave_doc"])
        row["terminal_state"] = "FINAL"
        with self.assertRaisesRegex((fs.FinalStackError, ValueError),
                                    "^admission under redesign$") as caught:
            fs.build_verdict(row, {}, {}, [], root=root)
        self.assertIsInstance(caught.exception, fs.FinalStackError)


del FinalIntegrityTests
