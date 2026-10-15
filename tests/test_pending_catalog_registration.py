"""Register a named pending layer without inventing a candidate or winner."""
import unittest

from tests import test_landscape as landscape_fixtures


class PendingRegistrationTests(unittest.TestCase):
    setUp = landscape_fixtures.LandscapeTests.setUp
    write = landscape_fixtures.LandscapeTests.write
    build = landscape_fixtures.LandscapeTests.build

    def test_named_pending_row_accepts_empty_candidates_without_promoting_a_winner(self):
        self.layer.update(candidates=[], winners=[], alternatives=[],
                          current_choice="No winner: waiting for the CC-approved layer sweep.",
                          open_gaps=["No covering sweep or verdict; scope registration only."])
        self.write("stack.json", {"components": []})
        self.freshness["components"] = []
        self.write("freshness.json", self.freshness)
        result = self.build()
        row = next(row for row in result["layers"] if row["catalog"] == "foundation")
        self.assertEqual(row["candidates"], [])
        self.assertEqual(row["winners"], [])
        self.assertEqual(row["verdict_status"], "pending_lanes")

    def test_empty_recorded_row_and_pending_row_without_named_gap_are_refused(self):
        self.layer.update(candidates=[], winners=[], alternatives=[], open_gaps=[])
        with self.assertRaises(ValueError):
            self.build()

    def test_empty_registration_cannot_claim_terminal_state_or_a_lane_run(self):
        self.layer.update(candidates=[], winners=[], alternatives=[], open_gaps=["Await covering sweep."])
        self.layer["terminal_state"] = "FINAL"
        with self.assertRaises(ValueError):
            self.build()
        del self.layer["terminal_state"]
        self.layer["lanes"]["claude"]["run_id"] = "claimed-run"
        with self.assertRaises(ValueError):
            self.build()
        self.layer.update(verdict_status="recorded", open_gaps=["No evidence"])
        with self.assertRaises(ValueError):
            self.build()
