"""Regression at the published archive-claim seam; synthetic controls are labelled."""

import json
import hashlib
from pathlib import Path
import shutil
import tempfile
import unittest

from verify_bindings import ARCHIVES, verify_archives, verify_fixtures


ROOT = Path(__file__).resolve().parent


class ArchiveBindingTests(unittest.TestCase):
    def test_claimed_verification_matches_all_three_release_digests_after_downloads(self):
        """Fails at 5e5d94bb's actual C10 claim; passes only after a new capture."""
        document = json.loads((ROOT / "upstream-install-smoke.json").read_text())
        ids = {Path(row["actual_checksum"]["path"]).name.removesuffix(".stdout.txt") for row in document["artifacts"]}
        self.assertEqual(len(ids), 1)
        problems = verify_archives(ROOT / "captures", ids.pop())
        self.assertEqual(problems, [], "Native checksum must equal each published digest and start after every download finishes")

    def test_retained_partial_download_capture_is_rejected(self):
        problems = verify_archives(ROOT / "captures", "10-archive-checksums")
        self.assertTrue(any("otelcol-contrib" in problem and "differs" in problem for problem in problems))
        self.assertTrue(any("otelcol-contrib" in problem and "before" in problem for problem in problems))

    def test_each_archive_mismatch_is_rejected_even_with_valid_capture_hashes(self):
        """Synthetic mutations of each public checksum; none is a native run."""
        for _, _, filename in ARCHIVES:
            with self.subTest(filename=filename), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                shutil.copytree(ROOT / "captures", root / "captures")
                target = root / "captures/38-archive-checksums-sequential.stdout.txt"
                lines = target.read_text().splitlines(keepends=True)
                target.write_text("".join("0" * 64 + line[64:] if filename in line else line for line in lines))
                metadata_path = root / "captures/38-archive-checksums-sequential.json"
                metadata = json.loads(metadata_path.read_text())
                metadata["streams"]["stdout"]["sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()
                metadata_path.write_text(json.dumps(metadata))
                problems = verify_archives(root / "captures", "38-archive-checksums-sequential")
                self.assertIn(filename + ": actual checksum differs from published release digest", problems)

    def test_matching_digest_before_download_completion_is_rejected(self):
        """Synthetic ordering mutation independent of the digest comparison."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            shutil.copytree(ROOT / "captures", root / "captures")
            path = root / "captures/38-archive-checksums-sequential.json"
            metadata = json.loads(path.read_text())
            old = json.loads((root / "captures/10-archive-checksums.json").read_text())
            metadata["started_at"] = old["started_at"]
            path.write_text(json.dumps(metadata))
            problems = verify_archives(root / "captures", "38-archive-checksums-sequential")
            self.assertTrue(any("before" in problem for problem in problems))
            self.assertFalse(any("differs" in problem for problem in problems))

    def test_all_five_fixture_files_match_sources_and_bracketed_smokes(self):
        document = json.loads((ROOT / "fixture-bindings.json").read_text())
        self.assertEqual(len(document["bindings"]), 5)
        self.assertEqual(verify_fixtures(ROOT / "captures", document["bindings"]), [])


if __name__ == "__main__":
    unittest.main()
