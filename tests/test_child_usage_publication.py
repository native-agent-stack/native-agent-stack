"""Publication regressions for retained child-usage receipts and validated pair provenance."""
import json
import re
from pathlib import Path
import unittest

from tests import test_landscape_postrun as postrun


ROOT = postrun.HARNESS.parents[2]


class ChildUsagePublicationTests(unittest.TestCase):
    def test_published_child_usage_receipts_do_not_authenticate_private_raw_output(self):
        receipts = sorted((ROOT / "evidence/artifacts").rglob("child-usage*.json"))
        flagged = []
        for path in receipts:
            value = json.loads(path.read_text(encoding="utf-8"))
            measurement = value.get("measurement", {}) if isinstance(value, dict) else {}
            digest = measurement.get("raw_output_sha256") if isinstance(measurement, dict) else None
            if isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest):
                flagged.append(path.relative_to(ROOT).as_posix())
        self.assertTrue(receipts)
        self.assertEqual(flagged, [], "published receipts retain private-original authentication")

    def test_supersession_receipt_omits_unvalidated_pair_extra_fields(self):
        fixture = postrun.CompletedSupersessionTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        address = "pair-fixture-" + fixture.work.name + "@" + "example.org"
        proof = fixture.proof
        proof["supersessionPairs"][0]["extra_note"] = address
        fixture.write("proof.json", proof)
        done = fixture.run_usage(explicit=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        receipt = (fixture.work / "usage.json").read_text()
        self.assertFalse(address in receipt, "unvalidated synthetic address reaches publication")
        provenance = json.loads(receipt)["measurement"]["post_processing"]["explicit_supersession"]
        fields = {"label", "superseded_agent_id", "superseded_by_agent_id"}
        self.assertTrue(all(set(pair) == fields for pair in provenance["pairs"]))
        self.assertEqual(provenance["proof"]["supersessionPairs"], provenance["pairs"])
