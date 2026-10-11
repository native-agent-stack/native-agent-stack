"""Keep WS3 comparisons consistent with the canonical input-trigger protocol."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
RECORD = "docs/decisions/2026-10-11-research-convergence-practice.md"


class ResearchConvergencePracticeTests(unittest.TestCase):
    def test_record_rejects_scheduling_dates(self):
        # Exact regex from #1008 squash 569bbc59db2b5f7c8a932357726efb7acca90b91,
        # tests/test_resolution_protocol_docs.py:test_record_rejects_scheduling_dates.
        text = " ".join((ROOT / RECORD).read_text(encoding="utf-8").split())
        self.assertNotRegex(
            text,
            r"(?i)\b(?:run|due|target|scheduled|execution|start|end|comparison)\s+dates?\b"
            r"|\bdeadlines?\b|\bwith a date\b|\bmisses its date\b|\bdated comparison\b",
        )


if __name__ == "__main__":
    unittest.main()
