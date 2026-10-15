"""Guard a source-proven A1 recovery constraint; never execute the candidate.

ojuschugh1/sqz@ff33708e2a311e514e3d73a5bd04c021d4fd4527:README.md:603
states that some otherwise compressed outputs are not cached, so anything a
lossy stage drops cannot be expanded. The general compression route therefore
cannot pass the layer's recoverable-originals requirement at this frozen pin.
"""

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "evidence/artifacts/harness-screens-20261015"
SQZ_PIN = "ff33708e2a311e514e3d73a5bd04c021d4fd4527"


class SqzRecoveryScreenTests(unittest.TestCase):
    def test_uncached_lossy_output_cannot_pass_recovery(self):
        for family in ("anthropic", "openai", "research"):
            with self.subTest(family=family):
                rows = json.loads(
                    (ARTIFACTS / f"token-efficiency.{family}.json").read_text(encoding="utf-8")
                )
                matches = [
                    row for row in rows
                    if row["candidate"]["repository"]
                    == "https://github.com/ojuschugh1/sqz"
                ]
                self.assertEqual(len(matches), 1)
                row = matches[0]
                self.assertEqual(row["pin"]["commit"], SQZ_PIN)
                recovery = next(
                    item for item in row["requirements_result"]
                    if item["id"] == "recoverable-originals"
                )
                self.assertEqual(recovery["result"], "FAIL")
                self.assertEqual(row["screen_verdict"]["result"], "FAIL")
                self.assertEqual(
                    row["screen_verdict"]["disqualifier"], "missing_capability"
                )
                self.assertTrue(any(
                    source.get("commit") == SQZ_PIN
                    and source.get("path") == "README.md"
                    and source["lines"][0] <= 603 <= source["lines"][1]
                    for source in recovery["citations"]
                ))


class DejaResearchCaptureScreenTests(unittest.TestCase):
    def test_cli_recall_does_not_prove_research_capture(self):
        # The frozen README's harness matrix (lines 281-346) documents coding
        # harness ingestion, but no DeerFlow/GPT Researcher capture contract.
        rows = json.loads(
            (ARTIFACTS / "durable-memory.research.json").read_text(encoding="utf-8")
        )
        row = next(item for item in rows if item["candidate"]["repository"]
                   == "https://github.com/vshulcz/deja-vu")
        self.assertEqual(row["pin"]["commit"], "0fb72c044f9c75444d270275424de29dca62e536")
        capture = next(item for item in row["requirements_result"]
                       if item["id"] == "inspectable-capture")
        self.assertEqual(capture["result"], "UNKNOWN")
        self.assertEqual(row["screen_verdict"]["result"], "INCOMPLETE")
        self.assertIsNone(row["screen_verdict"]["disqualifier"])


if __name__ == "__main__":
    unittest.main()
