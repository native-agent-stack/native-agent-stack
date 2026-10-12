"""Policy controls for v2 convergence, using synthetic sourced angle cells."""

import copy
import json
from pathlib import Path
import unittest

from scripts import angle_records as ar
from tests.test_final_stack import _angle_fixture

SCHEMA = json.loads((Path(__file__).resolve().parents[1] / ar.SCHEMA).read_text())


class DerivationTests(unittest.TestCase):
    def setUp(self):
        self.record = _angle_fixture()
        self.candidate = self.record["candidates"][0]

    def set_score(self, angle, score):
        self.candidate["angles"][angle]["score"] = score
        if score == "U":
            self.candidate["angles"][angle]["sources"] = []

    def test_v1_smoke_convergence_becomes_insufficient_without_an_outcome(self):
        self.set_score("A5", "U")
        result = ar.derive(self.record, self.candidate)
        self.assertEqual((result["verdict"], result["sourced_angles"], result["coverage"]),
                         ("INSUFFICIENT", 4, .70))

    def test_three_sourced_angles_cannot_converge_in_v2(self):
        self.set_score("A2", "U")
        self.set_score("A4", "U")
        self.assertEqual(ar.derive(self.record, self.candidate)["verdict"], "INSUFFICIENT")

    def test_convergence_without_comparative_a6_is_provisional(self):
        result = ar.derive(self.record, self.candidate)
        self.assertEqual((result["verdict"], result["provisional"], result["weighted_score"]),
                         ("CONVERGED", True, .90))

    def test_comparative_a6_clears_only_the_provisional_flag(self):
        self.candidate["a6_comparative"] = True
        self.set_score("A6", "+")
        self.candidate["angles"]["A6"]["sources"] = [{"kind": "receipt", "path": "evidence/comparison.json"}]
        result = ar.derive(self.record, self.candidate)
        self.assertEqual((result["verdict"], result["provisional"]), ("CONVERGED", False))

    def test_a_terms_conflict_is_a_missing_capability_disqualifier(self):
        self.candidate["disqualifier"] = "missing_capability"
        self.assertEqual(ar.derive(self.record, self.candidate)["verdict"], "REJECTED")

    def test_opposing_sourced_angles_require_first_hand_measurement(self):
        self.set_score("A3", "-")
        self.assertEqual(ar.derive(self.record, self.candidate)["verdict"], "DISAGREE")

    def test_unscreened_documented_model_route_remains_insufficient(self):
        self.candidate["a1_screened"] = False
        self.assertEqual(ar.derive(self.record, self.candidate)["verdict"], "INSUFFICIENT")

    def test_all_unpublished_transfer_preserves_weight_sum(self):
        self.record["published_evaluations_available"] = False
        self.set_score("A5", "U")
        weights = ar.effective_weights(self.record)
        self.assertEqual((float(weights["A5"]), float(weights["A6"]), float(sum(weights.values()))), (0, .30, 1))
        self.assertEqual(self.record["weights"], ar.DEFAULT_WEIGHTS)

    def test_zero_weight_angles_do_not_satisfy_coverage(self):
        self.record["weights"].update(A2=0, A3=0, A1=.55)
        self.assertEqual(ar.derive(self.record, self.candidate)["sourced_angles"], 3)

    def test_unknown_publication_availability_does_not_assert_absence(self):
        self.record["published_evaluations_available"] = None
        self.assertEqual({a: float(w) for a, w in ar.effective_weights(self.record).items()}, ar.DEFAULT_WEIGHTS)

    def test_licence_note_cannot_change_any_derived_result_or_arm_list(self):
        original = ar.derive(self.record, self.candidate)
        identities = [c["id"] for c in self.record["candidates"]]
        for spdx in ("MIT", "AGPL-3.0-only", None):
            with self.subTest(spdx=spdx):
                self.candidate["licence_note"] = {
                    "spdx_id": spdx, "source": {"kind": "url", "url": "https://example.org/fixture",
                                                 "read_at": "2026-10-12T21:34:46Z"},
                    "read_at": "2026-10-12T21:34:46Z", "note": "Synthetic compliance note only."}
                ar.validate_record(self.record, SCHEMA, label="synthetic")
                self.assertEqual(ar.derive(self.record, self.candidate), original)
                self.assertEqual([c["id"] for c in self.record["candidates"]], identities)


class ValidationTests(unittest.TestCase):
    def reject(self, mutate, needle):
        record = copy.deepcopy(_angle_fixture())
        mutate(record)
        with self.assertRaisesRegex(ar.AngleRecordError, needle):
            ar.validate_record(record, SCHEMA, label="synthetic")

    def test_smoke_cannot_be_labelled_a6(self):
        def mutate(r):
            r["candidates"][0]["angles"]["A6"].update(score="+", sources=[
                {"kind": "receipt", "path": "evidence/smoke.json"}])
        self.reject(mutate, "A6 requires")

    def test_comparison_needs_a_receipt_and_confounds(self):
        def mutate(r):
            c = r["candidates"][0]
            c["a6_comparative"] = True
            c["confounds"] = []
            c["angles"]["A6"].update(score="+", sources=c["angles"]["A1"]["sources"])
        self.reject(mutate, "A6 requires")

    def test_weights_must_strictly_precede_scores(self):
        self.reject(lambda r: r.update(weights_stated_at=r["candidates"][0]["angles"]["A1"]["read_at"]),
                    "before scoring")

    def test_source_time_cannot_follow_assessment_time(self):
        self.reject(lambda r: r["candidates"][0]["angles"]["A1"]["sources"][0].update(
            read_at="2026-10-12T21:34:47Z"), "source read")

    def test_duplicate_candidate_ids_fail(self):
        self.reject(lambda r: r["candidates"].append(copy.deepcopy(r["candidates"][0])), "duplicate candidate")

    def test_disagreement_must_name_measure_next(self):
        def mutate(r):
            c = r["candidates"][0]
            c["angles"]["A3"]["score"] = "-"
            c.update(verdict="DISAGREE", provisional=False)
        self.reject(mutate, "measure_next")

    def test_transfer_cannot_hide_a_published_evaluation(self):
        self.reject(lambda r: r.update(published_evaluations_available=False), "A5 transfer")

    def test_provisional_flag_must_rederive(self):
        self.reject(lambda r: r["candidates"][0].update(provisional=False), "re-derive")

    def test_licence_is_not_an_accepted_disqualifier(self):
        self.reject(lambda r: r["candidates"][0].update(
            disqualifier="licence", verdict="REJECTED", provisional=False), "schema failure")

    def test_private_or_escaping_paths_fail_schema_validation(self):
        for path in ("/absolute/receipt.json", "../receipt.json", "evidence/../../receipt.json"):
            with self.subTest(path=path):
                self.reject(lambda r: r["candidates"][0]["angles"]["A1"].update(sources=[
                    {"kind": "receipt", "path": path}]), "schema failure")


if __name__ == "__main__":
    unittest.main()
