"""Guard evidence boundaries using retained native data; start no component."""

from __future__ import annotations

import json
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent


def load(name: str) -> dict:
    return json.loads((HERE / name).read_text(encoding="utf-8"))


class EvidenceClaimTests(unittest.TestCase):
    def test_missing_host_capture_cannot_look_like_a_hashed_receipt(self) -> None:
        record = load("host-versions.json")
        self.assertEqual(record.get("record_type"), "named_gap")
        for row in record.get("components", record.get("probes", [])):
            self.assertEqual(row.get("status"), "GAP")
            self.assertIsNone(row.get("native_capture"))
            self.assertFalse(any(key.endswith("sha256") for key in row))
            self.assertNotIn("exit_code", row)

    def test_release_projection_cannot_certify_publisher_integrity(self) -> None:
        native = {row["id"]: row for row in load("native-commands.json")["commands"]}
        for row in load("source-reads.json")["reads"]:
            if row.get("asset") and row.get("native_api_receipt") is None:
                self.assertIsNot(row.get("checksum_matches"), True)
                self.assertEqual(row.get("publisher_integrity_status"), "GAP")
                self.assertTrue(row.get("publisher_integrity_prerequisite"))
            elif row.get("asset"):
                component = row["component"]
                result = native[component + "-actual-equals-published"]
                values = dict(line.split("=", 1) for line in result["stdout"].splitlines())
                self.assertEqual(result["exit_code"], 0)
                self.assertEqual(values["actual_sha256"], values["published_sha256"])
                self.assertEqual(values["actual_equals_published"], "true")
                self.assertLess(native[component + "-fresh-download"]["completed_at"], result["started_at"])

    def test_tag_binding_requires_a_native_resolution_receipt(self) -> None:
        native = {row["id"]: row for row in load("native-commands.json")["commands"]}
        for row in load("pin-reconciliation.json")["pins"]:
            if row.get("tag_resolution_receipt") is None:
                self.assertEqual(row.get("source_resolution_status"), "GAP")
                self.assertNotIn("resolved_commit", row)
                self.assertTrue(row.get("proposed_source_commit"))
            else:
                result = native[row["component"] + "-tag-resolution"]
                self.assertEqual(result["exit_code"], 0)
                self.assertIn(row["resolved_commit"], [line.split()[0] for line in result["stdout"].splitlines()])

    def test_index_counts_separate_nonzero_controls_from_zero_exits(self) -> None:
        native = {row["id"]: row for row in load("native-commands.json")["commands"]}
        expected_controls = {
            "worktrunk": {"worktrunk-dirty-refusal"},
            "gh": set(),
            "difftastic": {"difftastic-different-files", "difftastic-json-gate"},
        }
        for component, expected in expected_controls.items():
            index = load(component + ".e2e.json")
            zero = index["commands"]
            negative = index.get("negative_controls", [])
            self.assertEqual({row["id"] for row in negative}, expected)
            self.assertTrue(all(native[row["id"]]["exit_code"] == 0 for row in zero))
            self.assertTrue(all(native[row["id"]]["exit_code"] != 0 for row in negative))
            self.assertEqual(index["derived_counts"]["zero_exit_commands"], len(zero))
            self.assertEqual(index["derived_counts"].get("observed_nonzero_controls"), len(negative))
            for row in zero + negative:
                self.assertEqual(row["exit_code"], native[row["id"]]["exit_code"])

    def test_gh_help_completion_does_not_establish_pr_capability(self) -> None:
        candidate = next(row for row in load("angle-record.draft.json")["candidates"] if row["id"] == "gh")
        if not candidate.get("credentialed_pr_receipt"):
            self.assertFalse(candidate["a1_screened"])
            self.assertNotEqual(candidate["angles"]["A1"]["score"], "+")

    def test_engineering_score_requires_more_than_a_single_ci_source(self) -> None:
        for candidate in load("angle-record.draft.json")["candidates"][:3]:
            if not candidate.get("engineering_scorecard_receipt"):
                self.assertNotEqual(candidate["angles"]["A2"]["score"], "+")

    def test_formal_invoke_slot_cannot_point_to_a_raw_command_array(self) -> None:
        for evidence in load("angle-record.draft.json")["final_evidence"]:
            if evidence["invoke_receipt"]:
                receipt = json.loads((HERE.parents[2] / evidence["invoke_receipt"]).read_text())
                self.assertEqual(receipt.get("kind"), "invocation")
            else:
                self.assertTrue(evidence["not_invoked_reason"])

    def test_sem_published_call_count_cites_the_retained_text_not_css(self) -> None:
        sem = next(row for row in load("angle-record.draft.json")["candidates"] if row["id"] == "sem")
        citations = sem["angles"]["A5"]["sources"]
        self.assertTrue(any(row.get("path") == "catalogs/sota-convergence/manifest-20260926.json" and row.get("line") == 11337 for row in citations))


if __name__ == "__main__":
    unittest.main()
