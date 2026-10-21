"""The retained public-fixture digest must resolve to published output bytes."""

import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCREEN = ROOT / "catalogs/us-equities/edgartools-562-screen-20261015.json"
OUTPUT = ROOT / "catalogs/us-equities/edgartools-562-fixture-output-20261015.json"


class EdgarToolsScreenCustodyTests(unittest.TestCase):
    def test_fixture_output_digest_resolves_to_published_bytes(self):
        screen = json.loads(SCREEN.read_text(encoding="utf-8"))
        output_record = screen["candidates"][0]["public_fixture_e2e"]
        self.assertEqual(output_record["output_file"], OUTPUT.relative_to(ROOT).as_posix())
        expected = output_record["output_sha256"]
        self.assertFalse(OUTPUT.is_symlink(), "the published output must be a regular file")
        self.assertTrue(OUTPUT.is_file(), "the E2E digest has no published output artifact")
        self.assertEqual(hashlib.sha256(OUTPUT.read_bytes()).hexdigest(), expected)


if __name__ == "__main__":
    unittest.main()
