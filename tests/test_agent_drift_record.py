"""The mutation counts that the decision record and the receipts README of the Claude agent drift check quote are the counts the receipts hold.

Review of #1062 (the command center's Claude read): the record said "46 of 46 killed" for a receipt that held 49. Every line of the record and of the README that names a mutation receipt must carry that receipt's own
count, and a receipt must end in a summary with no survivor.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence/artifacts/agent-drift-check-20261013"
DOCUMENTS = (ROOT / "docs/decisions/2026-10-13-claude-agent-drift-check.md", EVIDENCE / "README.md")
SUMMARY = re.compile(r"^(\d+) mutants, (\d+) killed, survivors: none$", re.MULTILINE)


class MutationCountTests(unittest.TestCase):
    def receipts(self):
        found = sorted((EVIDENCE / "receipts").glob("mutants-*.txt"))
        self.assertTrue(found, "the evidence folder holds no mutation receipt")
        return found

    def test_every_mutation_receipt_ends_in_a_summary_with_every_mutant_killed(self):
        for receipt in self.receipts():
            with self.subTest(receipt=receipt.name):
                summaries = SUMMARY.findall(receipt.read_text(encoding="utf-8"))
                self.assertEqual(len(summaries), 1)
                total, killed = map(int, summaries[0])
                self.assertEqual(total, killed)
                self.assertGreater(total, 0)

    def test_every_line_that_names_a_mutation_receipt_quotes_its_count(self):
        for receipt in self.receipts():
            total = SUMMARY.search(receipt.read_text(encoding="utf-8")).group(1)
            for document in DOCUMENTS:
                lines = [line for line in document.read_text(encoding="utf-8").splitlines() if f"receipts/{receipt.name}" in line]
                with self.subTest(receipt=receipt.name, document=document.name):
                    self.assertTrue(lines, "the document does not name the receipt")
                    for line in lines:
                        self.assertIn(f"{total} of {total} killed", line)


if __name__ == "__main__":
    unittest.main()
