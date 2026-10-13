"""Portable helper evidence may not commit to withheld private output bytes."""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PublishedEvidence(unittest.TestCase):
    def test_guard_record_contains_no_private_output_commitments(self):
        path = ROOT / "evidence/artifacts/paper-deployment-pr1042-guards-20261012.json"
        record = json.loads(path.read_bytes())
        def inspect(value):
            if isinstance(value, dict):
                for key, item in value.items():
                    # The record intentionally publishes counts/commands,
                    # not commitments to logs/censuses absent from the repo.
                    if key.endswith("sha256"):
                        self.fail("unpublished_output_commitment:" + key)
                    inspect(item)
            elif isinstance(value, list):
                for item in value: inspect(item)
        inspect(record)


if __name__ == "__main__":
    unittest.main()
