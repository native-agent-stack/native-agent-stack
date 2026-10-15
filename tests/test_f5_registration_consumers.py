"""Required publication consumers must preserve an explicitly unrun layer."""
import copy
import json
from pathlib import Path
import unittest

from scripts import final_stack, new_host_grand_list, validate_foundation
import build_verdicts
from tests import test_layer_verdicts as wave_fixtures


ROOT = Path(__file__).resolve().parents[1]


def registration():
    row = next(row for row in json.loads((ROOT / "catalogs/landscape/foundation.json").read_text())["layers"]
               if row["layer_id"] == "model-routes")
    return {**row, "registration_only": True}


class RegistrationConsumerTests(unittest.TestCase):
    def test_foundation_taxonomy_accepts_the_registered_scope_without_a_capability_claim(self):
        report = validate_foundation.validate_foundation(ROOT)
        self.assertEqual(report["layers"], 21)

    def test_unrun_registration_has_no_wave_or_frozen_wave_document(self):
        row = registration()
        self.assertIsNone(build_verdicts.row_run_id(row))
        verdict = final_stack.build_verdict(row, {}, {"20260922": {"path": "frozen.json", "sha256": "a" * 64}}, [])
        self.assertIsNone(verdict["wave"])
        self.assertIsNone(verdict["wave_doc"])

    def test_grand_list_accepts_only_the_explicit_empty_unswept_registration(self):
        relative, manifest = new_host_grand_list.component_matrix.newest_sweep_manifest(ROOT)
        matrix = json.loads((ROOT / "catalogs/landscape/component-evidence-matrix.json").read_text())
        row = next(row for row in matrix["rows"] if row["layer_id"] == "model-routes")
        row["registration_only"] = True
        new_host_grand_list.validate_selected_manifest(relative, manifest, matrix)

    def test_registration_marker_cannot_hide_a_winner_or_sealed_run(self):
        for change in [lambda row: row.update(winners=[{"component_id": "invented"}]),
                       lambda row: row["lanes"]["claude"].update(run_id="claimed-run")]:
            row = copy.deepcopy(registration())
            change(row)
            with self.assertRaises((ValueError, SystemExit)):
                build_verdicts.row_run_id(row)

    def test_scope_registration_does_not_rewrite_or_join_a_frozen_wave(self):
        fixture = wave_fixtures.LayerVerdictFixture()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.assertEqual(wave_fixtures.build_verdicts.main(["--write", "--root", str(fixture.root)]), 0)
        path = fixture.root / "catalogs/sota-convergence/layer-verdicts-20260922.json"
        before = path.read_bytes()
        catalog_path = fixture.root / "catalogs/landscape/foundation.json"
        document = json.loads(catalog_path.read_text())
        document["layers"].append(registration())
        fixture.write("catalogs/landscape/foundation.json", document)
        self.assertEqual(wave_fixtures.build_verdicts.main(["--check", "--root", str(fixture.root)]), 0)
        self.assertEqual(path.read_bytes(), before)
        generated = wave_fixtures.build_verdicts.build_document(fixture.root, "2026-09-22")
        self.assertNotIn("model-routes", {row["layer_id"] for row in generated["catalogs"]["foundation"]})

    def test_missing_sweep_layer_with_any_selection_or_without_registration_still_refuses(self):
        relative, manifest = new_host_grand_list.component_matrix.newest_sweep_manifest(ROOT)
        original = json.loads((ROOT / "catalogs/landscape/component-evidence-matrix.json").read_text())
        for field, value in [("registration_only", False), ("winners", [{"component_id": "invented"}]),
                             ("verdict_status", "recorded"), ("adjudication_ref", "claimed.json")]:
            with self.subTest(field=field):
                matrix = copy.deepcopy(original)
                row = next(row for row in matrix["rows"] if row["layer_id"] == "model-routes")
                row[field] = value
                with self.assertRaisesRegex(SystemExit, "missing report layers: model-routes"):
                    new_host_grand_list.validate_selected_manifest(relative, manifest, matrix)

    def test_unswept_layer_is_retained_as_an_explicit_gap_in_new_host_output(self):
        document = new_host_grand_list.build()
        row = next(row for row in document["layers"] if row["layer_id"] == "model-routes")
        self.assertEqual(row["sweep_status"], "unswept")
        self.assertEqual(row["winners"], [])
        self.assertIn(row["sweep_gap"], new_host_grand_list.render_md(document))


if __name__ == "__main__":
    unittest.main()
