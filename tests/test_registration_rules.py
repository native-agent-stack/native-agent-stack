"""Unrun-scope rules verified without editing any published catalog or wave."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from scripts import component_matrix, final_stack, new_host_grand_list as grand
from tests import test_foundation_catalog as foundation_fixtures
from tests import test_layer_verdicts as wave_fixtures
import build_verdicts


def registration():
    return {
        "catalog": "foundation", "layer_id": "model-routes", "title": "Model routes",
        "requirement": "Synthetic pending route scope", "current_choice": "No winner: awaiting the covering sweep.",
        "decision": "keep_but_compare", "rationale": "Synthetic registration; no measurement or adoption.",
        "registration_only": True, "verdict_status": "pending_lanes", "checked_at": "2026-09-20",
        "candidates": [], "winners": [], "alternatives": [], "evidence_refs": ["guide.md"],
        "limitations": ["No provider or account acceptance."], "overturn_when": "A scoped comparison runs.",
        "overturn_protocol": {"fixture_paths": [], "metric": "", "arms": []},
        "lanes": {"claude": {"run_id": "", "sealed_sha256": ""},
                  "codex": {"run_id": "", "sealed_sha256": ""}, "agreement": "pending"},
        "open_gaps": ["No covering sweep, verdict or frozen comparison."],
    }


def matrix_row():
    return {"catalog": "foundation", "layer_id": "model-routes", "title": "Model routes",
            "registration_only": True, "verdict_status": "pending_lanes", "independent_review": "pending_lanes",
            "winners": [], "alternatives": [], "adjudication_ref": None,
            "convergence": {"layer_state": "pending_lanes", "manifest_layer_found": False,
                            "winner_rows": [], "recorded_winner_rows": 0, "in_use": 0, "converged": 0}}


class RegistrationRuleTests(unittest.TestCase):
    def test_matrix_preserves_registration_marker_without_any_winner(self):
        with tempfile.TemporaryDirectory() as temporary:
            row, violations = component_matrix.build_row(
                Path(temporary), "foundation", registration(), {}, {}, {}, {}, status_context=object())
        self.assertIs(row.get("registration_only"), True)
        self.assertEqual(row["winners"], [])
        self.assertEqual(violations, [])

    def foundation_fixture(self):
        fixture = foundation_fixtures.FoundationCatalogTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.manifest["layers"].append({
            "id": "model-routes", "title": "Model routes", "purpose": registration()["requirement"],
            "selection": "Pending only", "activation": "After review and landing", "lifecycle_scope": "None",
            "next_gap": "Run covering sweep", "registration_only": True})
        fixture.write("catalogs/landscape/foundation.json", {"layers": [registration()]})
        return fixture

    def test_foundation_accepts_existing_taxonomy_and_one_pending_scope_without_capability_claim(self):
        fixture = self.foundation_fixture()
        result, report = fixture.run_check()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(report["counts"]["layers"], 21)
        self.assertEqual(report["counts"]["decisions"], 1)

    def test_foundation_refuses_scope_mismatch_and_borrowed_capability(self):
        for mutation in [lambda f: f.manifest["layers"][-1].update(purpose="Different scope"),
                         lambda f: f.decision.update(layer_ids=[*f.decision["layer_ids"], "model-routes"])]:
            fixture = self.foundation_fixture()
            mutation(fixture)
            result, _ = fixture.run_check()
            self.assertEqual(result.returncode, 1, result.stdout)

    def test_unrun_registration_has_no_wave_or_wave_document(self):
        row = registration()
        self.assertIsNone(build_verdicts.row_run_id(row))
        verdict = final_stack.build_verdict(row, {}, {"20260922": {"path": "frozen.json", "sha256": "a" * 64}}, [])
        self.assertIsNone(verdict["wave"])
        self.assertIsNone(verdict["wave_doc"])

    def test_marker_cannot_hide_a_winner_or_sealed_run(self):
        for mutation in [lambda row: row.update(winners=[{"component_id": "invented"}]),
                         lambda row: row["lanes"]["claude"].update(run_id="claimed-run")]:
            row = registration()
            mutation(row)
            with self.assertRaises((ValueError, SystemExit)):
                build_verdicts.row_run_id(row)

    def test_registration_never_changes_frozen_wave_bytes_or_membership(self):
        fixture = wave_fixtures.LayerVerdictFixture()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.assertEqual(wave_fixtures.build_verdicts.main(["--write", "--root", str(fixture.root)]), 0)
        path = fixture.root / "catalogs/sota-convergence/layer-verdicts-20260922.json"
        before = path.read_bytes()
        document = json.loads((fixture.root / "catalogs/landscape/foundation.json").read_text())
        document["layers"].append(registration())
        fixture.write("catalogs/landscape/foundation.json", document)
        self.assertEqual(wave_fixtures.build_verdicts.main(["--check", "--root", str(fixture.root)]), 0)
        self.assertEqual(path.read_bytes(), before)

    def test_grand_list_accepts_only_marked_empty_unswept_scope(self):
        manifest = {"checked_at": "2026-09-20", "foundation": [], "trading": []}
        grand.validate_selected_manifest("fixture.json", manifest, {"rows": [matrix_row()]})
        for field, value in [("registration_only", False), ("winners", [{"component_id": "invented"}]),
                             ("verdict_status", "recorded"), ("adjudication_ref", "claimed.json")]:
            with self.subTest(field=field):
                row = matrix_row()
                row[field] = value
                with self.assertRaisesRegex(SystemExit, "missing report layers: model-routes"):
                    grand.validate_selected_manifest("fixture.json", manifest, {"rows": [row]})

    def test_grand_list_retains_the_unswept_scope_and_its_gap(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            files = {"catalogs/landscape/component-evidence-matrix.json": {"rows": [matrix_row()], "summary": {}},
                     "catalogs/sota-convergence/manifest-20260920.json": {
                         "checked_at": "2026-09-20", "foundation": [], "trading": []},
                     "adoption/manifest.json": {"profiles": [], "recipe_map": {}},
                     "adoption/hardware-profiles.json": {"hosts": []},
                     **{path: {"tools": []} for path in grand.PIN_FILES.values()},
                     **{path: {"layers": [registration()] if name == "foundation" else []}
                        for name, path in grand.LEDGERS.items()}}
            for path, value in files.items():
                (root / path).parent.mkdir(parents=True, exist_ok=True)
                (root / path).write_text(json.dumps(value))
            with mock.patch.object(grand, "ROOT", root):
                document = grand.build()
            row = document["layers"][0]
            self.assertEqual(row["winners"], [])
            self.assertEqual(row["sweep_status"], "unswept")
            self.assertIn(row["sweep_gap"], grand.render_md(document))


if __name__ == "__main__":
    unittest.main()
