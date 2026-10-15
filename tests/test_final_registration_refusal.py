"""Uniform disabled-admission refusal before native registration consumers.

The fixtures are #1130's registration and native reader/recorder fixtures.
Ordinary registration results and non-FINAL validation remain controls.
"""

import copy
import json
import unittest

from scripts import component_matrix, final_stack, landscape
from tests import test_landscape as landscape_fixtures
from tests import test_layer_verdicts as wave_fixtures
from tests import test_record_verdicts as recorder_fixtures
from tests.test_registration_rules import registration


class RegistrationFinalRefusalReview(wave_fixtures.LayerVerdictFixture):
    """The reader's two original fail-first regressions."""

    def assert_wave_refusal(self, marker):
        source = "catalogs/landscape/foundation.json"
        catalog = json.loads((self.root / source).read_bytes())
        row = registration()
        catalog["layers"].append(row)
        self.write(source, catalog)
        document = wave_fixtures.build_verdicts.build_document(self.root, "2026-09-22")
        self.assertNotIn(row["layer_id"], [r["layer_id"] for r in document["catalogs"]["foundation"]])
        row[marker] = "FINAL"
        self.write(source, catalog)
        with self.assertRaisesRegex((final_stack.FinalStackError, ValueError), "^admission under redesign$"):
            wave_fixtures.build_verdicts.build_document(self.root, "2026-09-22")

    def test_terminal_claim_refuses_before_unrun_filter(self):
        self.assert_wave_refusal("terminal_state")

    def test_alias_claim_refuses_before_unrun_filter(self):
        self.assert_wave_refusal("verdict_status")


class RegistrationFinalRefusalTests(wave_fixtures.LayerVerdictFixture):
    def row_fixture(self):
        path = "catalogs/landscape/foundation.json"
        catalog = json.loads((self.root / path).read_bytes())
        row = registration()
        catalog["layers"].append(row)
        self.write(path, catalog)
        return path, catalog, row

    def assert_redesign_refusal(self, call):
        with self.assertRaisesRegex((ValueError, SystemExit), "^admission under redesign$"):
            call()

    def test_wave_filter_and_run_discovery_refuse_each_final_marker(self):
        path, catalog, row = self.row_fixture()
        wave = wave_fixtures.build_verdicts
        document = wave.build_document(self.root, "2026-09-22")
        self.assertNotIn(row["layer_id"], [r["layer_id"] for r in document["catalogs"]["foundation"]])
        self.assertIsNone(wave.row_run_id(row, root=self.root))
        self.assertEqual(wave.main(["--write", "--root", str(self.root)]), 0)
        frozen = self.root / "catalogs/sota-convergence/layer-verdicts-20260922.json"
        previous = frozen.read_bytes()
        for marker in ("terminal_state", "verdict_status"):
            with self.subTest(marker=marker):
                changed = copy.deepcopy(row)
                changed[marker] = "FINAL"
                catalog["layers"][-1] = changed
                self.write(path, catalog)
                self.assert_redesign_refusal(lambda: wave.build_document(self.root, "2026-09-22"))
                self.assert_redesign_refusal(lambda: wave.row_run_id(changed, root=self.root))
                self.assert_redesign_refusal(lambda: wave.main(["--check", "--root", str(self.root)]))
                self.assertEqual(frozen.read_bytes(), previous)

    def test_classifier_and_verdict_validation_refuse_before_registration_rules(self):
        row = registration()
        self.assertTrue(landscape.is_unrun_registration(row, root=self.root))

        def validate(value):
            return landscape.validate_verdict_row(
                value, ("foundation", "model-routes"), root=self.root,
                identities=set(), aliases={}, evidence=None, recipe_map={}, sota_pins={}, status_context=None)

        self.assertIsNone(validate(row))
        for marker in ("terminal_state", "verdict_status"):
            with self.subTest(marker=marker):
                changed = copy.deepcopy(row)
                changed[marker] = "FINAL"
                self.assert_redesign_refusal(lambda: landscape.is_unrun_registration(changed, root=self.root))
                self.assert_redesign_refusal(lambda: validate(changed))

    def test_matrix_refuses_final_before_projection_and_preserves_pending_control(self):
        row = registration()

        def build(value):
            return component_matrix.build_row(self.root, "foundation", value, {}, {}, {}, {},
                                              status_context=object())

        projected, violations = build(row)
        self.assertEqual(violations, [])
        self.assertEqual(projected["verdict_status"], "pending_lanes")
        self.assertIs(projected["registration_only"], True)
        for marker in ("terminal_state", "verdict_status"):
            with self.subTest(marker=marker):
                changed = copy.deepcopy(row)
                changed[marker] = "FINAL"
                self.assert_redesign_refusal(lambda: build(changed))

    def test_recorder_no_lane_replay_refuses_final_without_mutating_the_row(self):
        row = registration()

        def replay(value):
            return recorder_fixtures.record_verdicts.process_row(
                value, self.root, "foundation", "model-routes", self.root / "empty-work", "2026-09-22",
                None, set(), {}, {}, [])

        before = copy.deepcopy(row)
        self.assertEqual(replay(row), [])
        self.assertEqual(row, before)
        for marker in ("terminal_state", "verdict_status"):
            with self.subTest(marker=marker):
                changed = copy.deepcopy(row)
                changed[marker] = "FINAL"
                expected = copy.deepcopy(changed)
                self.assert_redesign_refusal(lambda: replay(changed))
                self.assertEqual(changed, expected)

    def test_full_landscape_refuses_final_and_preserves_pending_registration(self):
        fixture = landscape_fixtures.LandscapeTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.layer.clear()
        fixture.layer.update(registration())
        fixture.write("foundation-manifest.json", {"layers": [{"id": "model-routes"}]})
        fixture.write("stack.json", {"components": []})
        fixture.freshness["components"] = []
        fixture.write("freshness.json", fixture.freshness)
        document = fixture.build()
        layer = next(row for row in document["layers"] if row["catalog"] == "foundation")
        self.assertEqual(layer["verdict_status"], "pending_lanes")
        self.assertIs(layer["registration_only"], True)
        for marker in ("terminal_state", "verdict_status"):
            with self.subTest(marker=marker):
                previous = copy.deepcopy(fixture.layer)
                fixture.layer[marker] = "FINAL"
                self.assert_redesign_refusal(fixture.build)
                fixture.layer.clear()
                fixture.layer.update(previous)

    def test_non_final_registration_errors_keep_the_native_diagnostics(self):
        for mutation, message in (
                ({"terminal_state": "RETIRED"}, "registration_only requires an empty, unsealed pending scope"),
                ({"verdict_status": "recorded"}, "registration_only requires an empty, unsealed pending scope"),
                ({"winners": [{"component_id": "invented"}]},
                 "registration_only requires an empty, unsealed pending scope")):
            with self.subTest(mutation=mutation):
                row = registration()
                row.update(mutation)
                with self.assertRaisesRegex(ValueError, message):
                    landscape.is_unrun_registration(row, root=self.root)


if __name__ == "__main__":
    unittest.main()
