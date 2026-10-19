"""Prove focused negative tests distinguish each independent sealing guard.

Only a temporary copy of the source is mutated; no native Workflow runs.
"""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests import test_layer_verdict_workflow as workflow_tests


class LayerVerdictMutationTests(unittest.TestCase):
    def assert_mutant_rejected(self, old, new, method):
        source = workflow_tests.WORKFLOW.read_text()
        self.assertEqual(source.count(old), 1, "mutation must match exactly one guard")
        with tempfile.TemporaryDirectory() as scratch:
            mutant = Path(scratch) / "layer-verdict-lane.js"
            mutant.write_text(source.replace(old, new))
            case = workflow_tests.LayerVerdictWorkflowTests(method)
            result = unittest.TestResult()
            with mock.patch.object(workflow_tests, "WORKFLOW", mutant):
                case.run(result)
        self.assertFalse(result.errors, result.errors)
        self.assertTrue(result.failures, f"{method} accepted the weakened guard")

    def test_remaining_findings_guard_is_decisive(self):
        self.assert_mutant_rejected(
            "!requiredFindings(revisionVotes).length && ", "",
            "test_remaining_major_or_blocking_findings_prevent_sealing_a_revision")

    def test_round_completion_guard_is_decisive(self):
        self.assert_mutant_rejected(
            "completeVotes(votes) && !stages.some((s) => s.round === round && s.status !== 'returned')",
            "completeVotes(votes)",
            "test_orchestration_faults_keep_completed_votes_and_never_complete")

    def test_clean_proposal_round_guard_is_decisive(self):
        self.assert_mutant_rejected(
            "completeVotes(votes) && !stages.some((s) => s.round === round && s.status !== 'returned')",
            "completeVotes(votes)",
            "test_clean_proposal_round_orchestration_faults_never_complete")


if __name__ == "__main__":
    unittest.main()
