"""Register a named pending layer without inventing a candidate or winner."""
import unittest

from tests import test_landscape as landscape_fixtures


class PendingRegistrationTests(unittest.TestCase):
    setUp = landscape_fixtures.LandscapeTests.setUp
    write = landscape_fixtures.LandscapeTests.write
    build = landscape_fixtures.LandscapeTests.build

    def test_unmarked_pending_row_cannot_drop_its_candidates(self):
        self.layer.update(candidates=[], winners=[], alternatives=[],
                          current_choice="No winner: waiting for the CC-approved layer sweep.",
                          open_gaps=["No covering sweep or verdict; scope registration only."])
        self.write("stack.json", {"components": []})
        self.freshness["components"] = []
        self.write("freshness.json", self.freshness)
        with self.assertRaisesRegex(ValueError, "layer needs candidates"):
            self.build()

    def test_marked_new_scope_passes_the_full_landscape_join_without_a_winner(self):
        self.layer.update(layer_id="new-scope", registration_only=True,
                          candidates=[], winners=[], alternatives=[],
                          current_choice="No winner: waiting for the scoped sweep.",
                          open_gaps=["No covering sweep or verdict; scope registration only."])
        self.write("foundation-manifest.json", {"layers": [{"id": "new-scope"}]})
        self.write("stack.json", {"components": []})
        self.freshness["components"] = []
        self.write("freshness.json", self.freshness)
        result = self.build()
        row = next(row for row in result["layers"] if row["catalog"] == "foundation")
        self.assertEqual(row["candidates"], [])
        self.assertEqual(row["winners"], [])
        self.assertEqual(row["verdict_status"], "pending_lanes")
        self.assertIs(row["registration_only"], True)

    def test_empty_recorded_row_and_pending_row_without_named_gap_are_refused(self):
        self.layer.update(registration_only=True, candidates=[], winners=[], alternatives=[], open_gaps=[])
        with self.assertRaisesRegex(ValueError, "registration_only requires an empty, unsealed pending scope"):
            self.build()

    def test_empty_registration_cannot_claim_terminal_state_or_a_lane_run(self):
        self.layer.update(registration_only=True, candidates=[], winners=[], alternatives=[], open_gaps=["Await covering sweep."])
        self.layer["terminal_state"] = "FINAL"
        with self.assertRaisesRegex(ValueError, "^admission under redesign$"):
            self.build()
        del self.layer["terminal_state"]
        self.layer["lanes"]["claude"]["run_id"] = "claimed-run"
        with self.assertRaisesRegex(ValueError, "registration_only requires an empty, unsealed pending scope"):
            self.build()
        self.layer.update(verdict_status="recorded", open_gaps=["No evidence"])
        with self.assertRaisesRegex(ValueError, "registration_only requires an empty, unsealed pending scope"):
            self.build()

    def test_marked_scope_in_a_published_sweep_is_not_unrun(self):
        self.layer.update(registration_only=True, candidates=[], winners=[], alternatives=[],
                          open_gaps=["Attempt to hide existing sweep membership."])
        self.write("catalogs/sota-convergence/manifest-20260921.json", {
            "foundation": [{"layer": "retrieval", "components": []}], "trading": []})
        with self.assertRaisesRegex(ValueError, "registration_only.*published sweep.*manifest-20260921"):
            self.build()

    def test_registered_sweep_ledger_membership_also_prevents_reregistration(self):
        self.layer.update(registration_only=True, candidates=[], winners=[], alternatives=[],
                          open_gaps=["Attempt to hide retained discovery history."])
        self.write("catalogs/saturation/ledger.json", {"sweeps": [{
            "sweep_id": "retained-discovery", "status": "completed",
            "layers": [{"catalog": "foundation", "layer_id": "retrieval"}]}]})
        with self.assertRaisesRegex(ValueError, "registration_only.*registered sweep.*retained-discovery"):
            self.build()

    def test_marker_does_not_skip_common_verdict_schema(self):
        self.layer.update(registration_only=True, candidates=[], winners=[], alternatives=[],
                          open_gaps=["Await covering sweep."])
        for field, value, reason in [("overturn_protocol", None, "overturn_protocol must be an object"),
                                     ("verdict_overturn_when", 42, "verdict_overturn_when must be text")]:
            with self.subTest(field=field):
                original = self.layer.get(field)
                self.layer[field] = value
                with self.assertRaisesRegex(ValueError, reason):
                    self.build()
                if original is None:
                    self.layer.pop(field, None)
                else:
                    self.layer[field] = original

    def test_unrun_marker_refuses_lane_run_binding_fields(self):
        self.layer.update(registration_only=True, candidates=[], winners=[], alternatives=[],
                          open_gaps=["Await covering sweep."])
        for field in ("run_manifest_sha256", "adjudication_sha256", "prose_exposed"):
            with self.subTest(field=field):
                self.layer["lanes"][field] = "a" * 64
                with self.assertRaisesRegex(ValueError, "registration_only.*run-binding fields"):
                    self.build()
                del self.layer["lanes"][field]
