"""Synthetic utility fixtures only; not native component or publisher evidence."""

import contextlib
import hashlib
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from verify_release_asset import main


class ReleaseAssetCheckTests(unittest.TestCase):
    def check_case(self, published):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            asset = root / "fixture.bin"
            asset.write_bytes(b"synthetic utility fixture")
            metadata = root / "release.json"
            metadata.write_text(json.dumps({"assets": [{"name": "fixture.bin", "digest": "sha256:" + published}]}))
            output = io.StringIO()
            argv = ["verify_release_asset.py", "--release-json", str(metadata), "--asset", str(asset)]
            with patch("sys.argv", argv), contextlib.redirect_stdout(output):
                rc = main()
            return rc, output.getvalue()

    def test_matching_download_prints_both_values_and_succeeds(self):
        value = hashlib.sha256(b"synthetic utility fixture").hexdigest()
        rc, output = self.check_case(value)
        self.assertEqual(rc, 0)
        self.assertIn("published_sha256=" + value, output)
        self.assertIn("actual_sha256=" + value, output)
        self.assertIn("actual_equals_published=true", output)

    def test_mismatching_download_fails_closed(self):
        rc, output = self.check_case("0" * 64)
        self.assertEqual(rc, 1)
        self.assertIn("actual_equals_published=false", output)


if __name__ == "__main__":
    unittest.main()
