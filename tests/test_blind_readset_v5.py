"""Review regressions for cue masking, retained measurements and rewrite artifacts."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from tests.test_blind_readset_v3 import ROOT, blind, redaction, walk_strings


class ReviewPreservationTests(unittest.TestCase):
    def test_preserved_provenance_and_execution_stages_are_not_selection_statements(self):
        import export_isolation_check as isolation
        for heading, expected in (("Primary source basis", False), ("Primary source basis | Selected tool", True),
                                  ("Primary tool", True)):
            text = f"| Capability | {heading} |\n| --- | --- |\n| Cedar | Upstream code |\n"
            with self.subTest(heading=heading):
                self.assertEqual(list(isolation.prose_statements(text))[0][1], expected)
        self.assertFalse(isolation._states_selection("Unexercised daemon lifecycle stages.", []))
        self.assertTrue(isolation._states_selection("The lifecycle stage is partial_acceptance.", []))

    def view(self, relative):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        target = Path(temporary.name) / relative
        target.parent.mkdir(parents=True)
        shutil.copyfile(ROOT / relative, target)
        blind.strip_worktree(Path(temporary.name), b"k" * 32)
        return target.read_text()

    def test_ledger_selection_clauses_are_removed_without_losing_source_scope(self):
        hosting = self.view("docs/hosting-container-practice.md")
        self.assertNotIn("The selected [Nautilus", hosting)
        self.assertIn("DockerizedIBGateway", hosting)
        readiness = self.view("docs/foundation-rd-readiness.md")
        self.assertNotIn("LEAN remains the frozen historical comparator", readiness)
        self.assertIn("no post-result tolerance change", readiness)
        simulation = json.loads(self.view("catalogs/us-equities/simulation-data-review.json"))
        self.assertNotIn("selected path", simulation["scope"])
        self.assertIn("code/API/native acceptance only for EdgarTools", simulation["scope"])

    def test_measured_receipt_outcomes_survive_status_masking(self):
        cases = [
            ("omniroute-runtime-workers-20260930.json",
             ["passed one upstream coding fixture", "native resume and fresh recovery", "unknown/failed"]),
            ("mcporter-0142-qualification-20261003.json",
             ["stdio canary passed", "ELSPROBLEMS", "core 2.2.0", "server 2.3.0", "were not qualified"]),
            ("mcporter-0141-qualification-20260925.json", ["lifecycle stages"]),
        ]
        for name, measurements in cases:
            with self.subTest(receipt=name):
                values = list(walk_strings(json.loads(self.view("evidence/receipts/" + name))))
                for measurement in measurements:
                    self.assertTrue(any(measurement in value for value in values), measurement)

    def test_source_review_retains_native_provenance(self):
        text = self.view("blueprints/convergence-practice/service-reboot/source-review.md")
        for source in ("upstream QEMU", "official Ubuntu cloud image", "cloud-localds",
                       "OpenSSH", "systemd", "Dagu executable", "Primary source basis"):
            self.assertIn(source, text)
        self.assertNotIn("The selected runtime", text)
        self.assertNotIn("the accepted Dagu", text)

    def test_identical_bounded_workflow_is_preserved_in_both_receipts(self):
        paths = ["evidence/receipts/" + name + "-qualification-20261004.json"
                 for name in ("mcporter-0142", "claude-hud-0100")]
        for relative in paths:
            original = json.loads((ROOT / relative).read_text())["data"]["research"]["workflow"]
            view = json.loads(self.view(relative))
            with self.subTest(path=relative):
                self.assertEqual(view["data"]["research"]["workflow"], original)

    def test_redaction_leaves_no_new_odd_json_strings(self):
        names = ("markitdown-018-qualification-20260925.json",
                 "ai-memory-241-qualification-20260925.json",
                 "omniroute-runtime-workers-20260930.json")

        def odd(values):
            return sum(bool(value) and (not value.strip() or value != value.strip() or "  " in value)
                       for value in values)

        for name in names:
            relative = "evidence/receipts/" + name
            before = list(walk_strings(json.loads((ROOT / relative).read_text())))
            after = list(walk_strings(json.loads(self.view(relative))))
            with self.subTest(path=relative):
                self.assertLessEqual(odd(after), odd(before))

    def test_emptied_list_item_is_removed_but_measured_item_is_kept(self):
        relative = "probe.json"
        cue = "Cedar is the current choice."
        measured = "Native fixture passed with exit 0."
        node = [cue, measured]
        redaction.redact_document(node, relative, "", [], b"k" * 32,
                                  {redaction.digest(cue): "choice"}, {}, {})
        self.assertEqual(node, [measured])


if __name__ == "__main__":
    unittest.main()
