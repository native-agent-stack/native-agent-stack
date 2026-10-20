"""Option-A accounting is operator-only and uses actual sets, never layer names."""
import json
import unittest

from tests.test_blind_readset_v3 import ROOT
import export_isolation_check as isolation
import lane_packets as lane


class EligibilityAccountingTests(unittest.TestCase):
    def test_real_exact_pools_and_pilot_are_distinguished(self):
        keys = {}
        packets = lane.build_all_packets(
            ROOT, catalogs=["foundation", "us-equities"], seed=lane.DEFAULT_SEED,
            checked_at=lane.DEFAULT_CHECKED_AT,
            manifest="catalogs/sota-convergence/manifest-20260923.json",
            trading_candidates="ledger", withhold=True, registered_receipts=True, sealed_keys=keys)
        winners = isolation.ledger_winners(ROOT)
        for layer, size, exact in (("mcp-surfaces", 2, True), ("secrets-credentials", 1, True),
                                   ("document-retrieval", 6, False)):
            name = "foundation__" + layer + ".json"
            packet = json.loads(packets[name])
            restored = [dict(candidate, **keys[name]["candidates"].get(candidate["key"], {}))
                        for candidate in packet["candidates"]]
            result = isolation.eligibility_accounting(restored, winners["foundation::" + layer])
            with self.subTest(layer=layer):
                self.assertEqual(result["eligible_count"], size)
                self.assertEqual(result["eligibility_determined"], exact)
                self.assertEqual(result["blind_evidence_excluded"], exact)
                self.assertEqual(result["near_rule"], exact)
                self.assertNotIn("blind_evidence", packets[name])

    def test_equal_counts_do_not_replace_set_equality(self):
        candidates = [{"key": "eligible", "component_id": "a", "adopted": True},
                      {"key": "ineligible", "component_id": "b", "adopted": False}]
        result = isolation.eligibility_accounting(candidates, [("", "b", "b")])
        self.assertFalse(result["eligibility_determined"])
        self.assertTrue(result["near_rule"])

    def test_unmatched_and_empty_winners_cannot_create_exact_success(self):
        candidates = [{"key": "eligible", "component_id": "a", "adopted": True}]
        for winners in ([], [("", "missing", "missing")], [("", "a", "a"), ("", "missing", "missing")]):
            with self.subTest(winners=winners):
                self.assertFalse(isolation.eligibility_accounting(candidates, winners)["eligibility_determined"])


if __name__ == "__main__":
    unittest.main()
