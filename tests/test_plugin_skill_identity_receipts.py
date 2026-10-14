"""Every sha256 that the plugin-skill-identity evidence, its README and its decision record publish resolves to published bytes.

Review of #1074 at 2dae9751 (Astra's read, P1): the claude-api currency receipt gave the digest of the prompt that the client expands for its bundled skill, whose first line names the folder the client unpacked the
skill into on the author's host. No published file hashes to it, and its preimage holds a path of that host, so the digest was a confirmation oracle for a private preimage. The text receipts are outside the
scanner of tests/test_published_digest_privacy.py (it reads JSON), so this module reads them: a digest is accepted when it is the sha256 of a file the evidence registry publishes, a digest the pinned skills manifest
publishes (the bytes of an upstream file at its pin), or the digest of a public documentation page that the receipt named by the table below quotes with its URL and fetch time.
"""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence/artifacts/plugin-skill-identity-20261013"
DOCUMENTS = (ROOT / "docs/decisions/2026-10-13-plugin-skill-identity.md", EVIDENCE / "README.md")
DIGEST = re.compile(r"\b[0-9a-f]{64}\b")

# A public documentation page, hashed as fetched: its bytes are at the URL, not in this repository. Each is accepted only in the receipt that quotes it with the URL and the time of the fetch.
PUBLIC_PAGES = {
    "35fd2c11f870fbe1497a53796de31b2a6b760645e724bda58894525356d4602a": ("receipts/docs-skills-md-excerpt.txt", "code.claude.com/docs/en/skills.md", "2026-10-13T10:29:20Z"),
    "83dcafe4cb6a4f1ec9aa29163cf76a70c4e68878cd77a28c1242ffec57b444e3": ("receipts/docs-env-vars-excerpt.txt", "code.claude.com/docs/en/env-vars.md", "2026-10-13T13:38:26Z"),
}


def published_digests():
    registry = json.loads((ROOT / "manifests/evidence.json").read_text(encoding="utf-8"))
    registered = {row["sha256"] for row in registry["files"] if isinstance(row.get("sha256"), str)}
    pinned = set(DIGEST.findall((ROOT / "adoption/skills/manifest.json").read_text(encoding="utf-8")))
    return registered | pinned | set(PUBLIC_PAGES)


def unresolved(text, accepted):
    """The digests in ``text`` that resolve to nothing published."""
    return sorted({digest for digest in DIGEST.findall(text) if digest not in accepted})


def published_texts():
    files = [path for path in sorted(EVIDENCE.rglob("*")) if path.is_file()] + list(DOCUMENTS)
    return [(path, path.read_text(encoding="utf-8")) for path in files]


class ReceiptDigestTests(unittest.TestCase):
    def test_every_digest_the_evidence_the_readme_and_the_record_publish_resolves_to_published_bytes(self):
        accepted = published_digests()
        texts = published_texts()
        self.assertGreater(len(texts), 8, "the evidence folder, its README and the record were found")
        for path, text in texts:
            with self.subTest(file=str(path.relative_to(ROOT))):
                self.assertEqual(unresolved(text, accepted), [], "a digest of nothing published is a confirmation oracle for a private preimage: remove it, or publish the exact bytes it hashes")

    def test_a_digest_of_a_private_original_is_found_wherever_it_is_written(self):
        accepted = published_digests()
        private = "04" + "a" * 62   # a stand-in: any 64-hex string that nothing published hashes to
        for label, text in (("a receipt line", f"SKILL.md: the bundled one is inlined in the prompt (sha256 {private}, 611 lines)"), ("a table cell", f"| prompt | `{private}` |"), ("a bare line", f"{private}\n")):
            with self.subTest(case=label):
                self.assertEqual(unresolved(text, accepted), [private])
        self.assertEqual(unresolved("sha256 " + "0" * 63, accepted), [], "a shorter hex run is not a digest")

    def test_a_public_page_digest_is_accepted_only_where_its_receipt_quotes_the_url_and_the_fetch_time(self):
        for digest, (receipt, url, fetched) in PUBLIC_PAGES.items():
            with self.subTest(page=url):
                text = (EVIDENCE / receipt).read_text(encoding="utf-8")
                self.assertIn(digest, text)
                self.assertIn(url, text)
                self.assertIn(fetched, text)
                others = [path for path, other in published_texts() if digest in other and path != EVIDENCE / receipt]
                self.assertEqual(others, [], "the digest of a page stands only beside its URL and its fetch time")


if __name__ == "__main__":
    unittest.main()
