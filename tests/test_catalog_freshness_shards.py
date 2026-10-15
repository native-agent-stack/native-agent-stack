"""The scheduled report retains all tests without a redundant serial timeout."""
from pathlib import Path
import unittest

from tests.test_workflow_policy import load_workflow

ROOT = Path(__file__).resolve().parents[1]


class CatalogFreshnessShardRegression(unittest.TestCase):
    def test_daily_suite_uses_all_native_shards_with_required_prerequisites(self):
        document = load_workflow((ROOT / ".github/workflows/catalog-freshness.yml").read_text())
        jobs = document["jobs"]
        self.assertIn("freshness-tests", jobs,
                      "run38559440278 exhausted the serial55minute budget; use existing native shards")
        job = jobs["freshness-tests"]
        self.assertEqual(list(map(int, job["strategy"]["matrix"]["shard"])), list(range(8)))
        self.assertEqual(str(job["strategy"]["fail-fast"]).lower(), "false")
        suite = next(s for s in job["steps"] if s.get("name") == "Test validation failure modes")
        self.assertIn("scripts/validate_shards.py run -v", suite["run"])
        self.assertIn('--shard "$VALIDATE_SHARD" --shards 8', suite["run"])
        self.assertNotIn("--module", suite["run"])
        scanner = next(s for s in job["steps"] if s.get("uses") == "$/.github/actions/setup-host-name-scanner")
        self.assertLess(job["steps"].index(scanner), job["steps"].index(suite))
        self.assertNotIn("if", scanner)
        self.assertNotIn("continue-on-error", scanner)
        validation = load_workflow((ROOT / ".github/workflows/validate.yml").read_text())["jobs"]["validate"]
        for name in ("Provision the promotion gate's isolated venv",
                     "Provision the Bun that Claude Code 2.1.296 embeds, for the agent front matter tests",
                     "Provision the pinned tree-sitter-bash parser for the token-measurement lane tests",
                     "Provision the pinned yaml package for the skills-modality SKILL.md reader tests"):
            with self.subTest(prerequisite=name):
                selected = next(s for s in job["steps"] if s.get("name") == name)
                upstream = next(s for s in validation["steps"] if s.get("name") == name)
                self.assertEqual(selected["run"], upstream["run"])
                self.assertLess(job["steps"].index(selected), job["steps"].index(suite))

    def test_proposal_waits_for_complete_native_aggregate(self):
        jobs = load_workflow((ROOT / ".github/workflows/catalog-freshness.yml").read_text())["jobs"]
        self.assertIn("freshness-test-results", jobs)
        result = jobs["freshness-test-results"]
        self.assertEqual(result["needs"], "freshness-tests")
        self.assertEqual(result["if"], "always()")
        command = next(s["run"] for s in result["steps"] if "scripts/validate_shards.py aggregate" in s.get("run", ""))
        self.assertIn("--shards 8", command)
        self.assertEqual(set(jobs["propose"]["needs"]), {"freshness", "freshness-test-results"})
        self.assertFalse(any("python3 -m unittest --durations" in s.get("run", "")
                             for s in jobs["freshness"]["steps"]))


if __name__ == "__main__":
    unittest.main()
