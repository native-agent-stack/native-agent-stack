"""Regression for whole upstream files accidentally published as native stdout.

Policy source: the CC's named custody ruling on PR #1216, 2026-10-16.
The source identities below are the pinned URLs in C21-C24, not private hashes.
"""

import json
import hashlib
from pathlib import Path
import tempfile
import unittest

from capture_native import record
from mask_capture import publish


ROOT = Path(__file__).resolve().parent
UPSTREAM_STREAMS = (
    "21-fixture-collector", "22-fixture-prometheus-tests",
    "23-fixture-prometheus-rules", "24-fixture-loki",
    "39-fixture-collector-read", "41-fixture-rule-tests-read",
    "42-fixture-rules-read", "43-fixture-loki-read",
)


class UpstreamCustodyTests(unittest.TestCase):
    def test_whole_upstream_streams_have_pinned_envelopes_without_public_payloads(self):
        """Fails on the eight whole-file payloads at the reviewed 099f699c head."""
        for identity in UPSTREAM_STREAMS:
            with self.subTest(capture=identity):
                payload = ROOT / "captures" / (identity + ".stdout.txt")
                self.assertFalse(payload.exists(), "Whole upstream bytes require licensed private vendor custody")
                envelope = json.loads((ROOT / "captures" / (identity + ".json")).read_text())
                stream = envelope["streams"]["stdout"]
                self.assertNotIn("path", stream)
                self.assertEqual(stream["retention"], "licensed_private_vendor_custody")
                source = stream["upstream"]
                self.assertRegex(source["commit"], r"^[0-9a-f]{40}$")
                self.assertIn("/" + source["commit"] + "/", source["url"])
                self.assertEqual(stream["sha256"], source["sha256"])
                self.assertEqual(stream["bytes"], source["bytes"])

    def test_publisher_withholds_exact_upstream_bytes_and_refuses_a_source_mismatch(self):
        """Synthetic source control; does not run any candidate code."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = {"capture_ids": ["fixture"], "commit": "a" * 40,
                      "url": "https://example.invalid/" + "a" * 40 + "/fixture.txt",
                      "bytes": 7, "sha256": hashlib.sha256(b"sample\n").hexdigest()}
            record(root / "raw", "fixture", ["/usr/bin/printf", "sample\n"], root, {}, 10)
            out = root / "out"
            out.mkdir()
            (out / "fixture.stdout.txt").write_bytes(b"stale payload")
            publish(root / "raw", out, {}, {"sources": [source]})
            self.assertFalse((out / "fixture.stdout.txt").exists())
            envelope = json.loads((out / "fixture.json").read_text())
            self.assertEqual(envelope["streams"]["stdout"]["sha256"], source["sha256"])
            source["sha256"] = "0" * 64
            with self.assertRaisesRegex(ValueError, "differs from pinned public source"):
                publish(root / "raw", root / "invalid", {}, {"sources": [source]})


if __name__ == "__main__":
    unittest.main()
