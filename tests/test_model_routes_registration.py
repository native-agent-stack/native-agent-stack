"""The published model-routes row is an empty registration, never a verdict."""

import copy
import json
from pathlib import Path
import unittest

from scripts import landscape


ROOT = Path(__file__).resolve().parents[1]
CATALOG = "catalogs/landscape/foundation.json"


class ModelRoutesRegistrationTests(unittest.TestCase):
    def registered_row(self):
        document = json.loads((ROOT / CATALOG).read_text())
        rows = [row for row in document["layers"] if row["layer_id"] == "model-routes"]
        self.assertEqual(len(rows), 1, "one explicit model-routes registration must be published")
        return rows[0]

    def build_with(self, row):
        def read(path):
            document = json.loads((ROOT / path).read_text())
            if path == CATALOG:
                document["layers"] = [row if old["layer_id"] == "model-routes" else old
                                      for old in document["layers"]]
            return document

        return landscape.build_landscape(ROOT, read=read)

    def test_registered_model_routes_passes_the_full_join_only_as_unrun(self):
        row = self.registered_row()
        self.assertTrue(landscape.is_unrun_registration(row, root=ROOT))
        document = self.build_with(row)
        joined = next(item for item in document["layers"] if item["layer_id"] == "model-routes")
        self.assertIs(joined["registration_only"], True)
        self.assertEqual(joined["verdict_status"], "pending_lanes")
        self.assertEqual(row["requirement"],
                         "Scope: current model ids and routes for the Anthropic API (vendor docs and the claude-api "
                         "skill), OpenAI through OmniRoute, and Meta's Muse through the muse-code provider "
                         "(Wonder Full; the Muse fence rules hold).")
        for field in ("candidates", "winners", "alternatives"):
            self.assertEqual(joined[field], [])
        self.assertNotIn("terminal_state", joined)

    def test_removing_marker_cannot_admit_an_empty_verdict(self):
        row = self.registered_row()
        del row["registration_only"]
        with self.assertRaisesRegex(ValueError, "layer needs candidates"):
            self.build_with(row)

    def test_winner_sealed_run_and_wave_claim_are_refused(self):
        for mutation in (lambda row: row.update(winners=[{"component_id": "invented"}]),
                         lambda row: row["lanes"]["claude"].update(
                             run_id="foundation-model-routes-20261015", sealed_sha256="a" * 64),
                         lambda row: row["lanes"].update(
                             sealed_base="evidence/artifacts/layer-verdicts-20261015")):
            row = copy.deepcopy(self.registered_row())
            mutation(row)
            with self.assertRaisesRegex(ValueError, "registration_only requires an empty, unsealed pending scope"):
                self.build_with(row)


if __name__ == "__main__":
    unittest.main()
