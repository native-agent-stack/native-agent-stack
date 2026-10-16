"""Regression controls for the published packet; no candidate code executes."""

import copy
import json
from pathlib import Path
import unittest

from project_packet import REPOSITORIES, project


ROOT = Path(__file__).parent


class LanePacketTests(unittest.TestCase):
    def setUp(self):
        self.raw = json.loads((ROOT / "generator-token-efficiency.json").read_text())

    def test_published_candidate_rows_preserve_every_producer_field(self):
        actual = json.loads((ROOT / "lane-packet.json").read_text())
        expected = project(self.raw)
        self.assertEqual(actual["candidates"], expected["candidates"])

    def test_full_receipt_lists_and_pin_names_survive_projection(self):
        rows = project(self.raw)["candidates"]
        counts = {row["name"]: len(row.get("registered_receipts", [])) for row in rows}
        self.assertEqual({name: counts[name] for name in ("ccusage", "Headroom", "RTK")},
                         {"ccusage": 11, "Headroom": 22, "RTK": 27})
        for row in rows:
            self.assertIn("pin", row)
            self.assertNotIn("packet_pin", row)

    def test_missing_duplicate_and_wrong_layer_inputs_fail(self):
        missing = copy.deepcopy(self.raw)
        chosen = next(row for row in missing["candidates"] if row["repository"] in REPOSITORIES)
        missing["candidates"].remove(chosen)
        duplicate = copy.deepcopy(self.raw)
        duplicate["candidates"].append(chosen)
        wrong = copy.deepcopy(self.raw)
        wrong["layer_id"] = "other"
        for packet in (missing, duplicate, wrong):
            with self.subTest(kind=packet["layer_id"], count=len(packet["candidates"])):
                with self.assertRaises(ValueError):
                    project(packet)


if __name__ == "__main__":
    unittest.main()
