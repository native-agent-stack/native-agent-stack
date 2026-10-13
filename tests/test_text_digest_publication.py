"""Text publication gate: only public preimages may justify a digest."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "scripts/check_text_digests.py"


class TextDigestPublicationTests(unittest.TestCase):
    def test_unpublished_probe_cannot_justify_a_text_digest(self):
        with tempfile.TemporaryDirectory(dir="/var/tmp") as folder:
            root = Path(folder)
            subprocess.run(["git", "init", "--quiet", str(root)], check=True)
            private = root / "unpublished-probe.py"
            private.write_bytes(b"fixture-only unpublished probe\n")
            digest = hashlib.sha256(private.read_bytes()).hexdigest()
            text = root / "ADDENDUM.txt"
            for value in (digest[:7], digest, digest.upper()):
                with self.subTest(length=len(value)):
                    text.write_text(f"Unpublished probe digest: {value}\n")
                    subprocess.run(["git", "add", "ADDENDUM.txt"], cwd=root, check=True)
                    result = subprocess.run(
                        [sys.executable, str(CHECKER), str(root), str(text)],
                        capture_output=True, text=True,
                    )
                    self.assertEqual(result.returncode, 1, "untracked probe is not a published preimage")
                    self.assertNotIn(digest[:7], result.stdout + result.stderr)

    def test_published_preimage_allows_full_digest_and_prefix(self):
        with tempfile.TemporaryDirectory(dir="/var/tmp") as folder:
            root = Path(folder)
            subprocess.run(["git", "init", "--quiet", str(root)], check=True)
            public = root / "source.txt"
            public.write_bytes(b"public fixture source\n")
            digest = hashlib.sha256(public.read_bytes()).hexdigest()
            text = root / "ADDENDUM.txt"
            text.write_text(f"Published source: {digest} ({digest[:7]})\n")
            subprocess.run(["git", "add", "source.txt", "ADDENDUM.txt"], cwd=root, check=True)
            result = subprocess.run(
                [sys.executable, str(CHECKER), str(root), str(text)], capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0)

    def test_symlink_cannot_publish_a_private_preimage(self):
        with tempfile.TemporaryDirectory(dir="/var/tmp") as folder:
            root = Path(folder)
            subprocess.run(["git", "init", "--quiet", str(root)], check=True)
            private = root / "private.txt"
            private.write_bytes(b"fixture-only private source\n")
            (root / "public-link.txt").symlink_to(private.name)
            text = root / "ADDENDUM.txt"
            text.write_text(hashlib.sha256(private.read_bytes()).hexdigest() + "\n")
            subprocess.run(["git", "add", "public-link.txt", "ADDENDUM.txt"], cwd=root, check=True)
            result = subprocess.run(
                [sys.executable, str(CHECKER), str(root), str(text)], capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 1)

    def test_published_ibkr_text_has_public_preimages(self):
        root = ROOT / "evidence/artifacts/ibkr-pacing-20261013"
        files = sorted(path for path in root.iterdir() if path.suffix in (".md", ".txt"))
        result = subprocess.run(
            [sys.executable, str(CHECKER), str(root), "--allow", str(root / "text-digest-public-references.json"),
             *map(str, files), str(ROOT / "docs/trading-handbook/ibkr-pacing.md"),
             str(ROOT / "docs/trading-handbook/paper-marker.md")],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_vendor_reference_cannot_launder_an_unpublished_commitment(self):
        with tempfile.TemporaryDirectory(dir="/var/tmp") as folder:
            root = Path(folder)
            subprocess.run(["git", "init", "--quiet", str(root)], check=True)
            document = root / "vendor.md"
            document.write_text("![Public fixture](/docs/_fern-img/" + "ab" * 32 + ".webp)\n")
            unpublished = hashlib.sha256(b"fixture-only unpublished source").hexdigest()
            text = root / "ADDENDUM.txt"
            text.write_text(unpublished + "\n")
            references = root / "references.json"
            references.write_text(json.dumps({"schema_version": 1, "references": [{
                "value": unpublished,
                "public_preimage_class": "ibkr_documentation_asset_identifier",
                "source_url": "https://www.interactivebrokers.com/docs/_fern-img/" + unpublished + ".webp",
                "public_file": "vendor.md",
                "file_sha256": hashlib.sha256(document.read_bytes()).hexdigest(),
            }]}))
            subprocess.run(["git", "add", "vendor.md", "ADDENDUM.txt", "references.json"], cwd=root, check=True)
            result = subprocess.run(
                [sys.executable, str(CHECKER), str(root), "--allow", str(references), str(text)],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 2, "a public source must actually name the declared asset")
            self.assertNotIn(unpublished[:7], result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
