"""The retained federation documentation snapshots and the decision claim that cites them.

The three in-GitHub Claude workflows whose failed exchanges this module once executed were retired on 2026-10-10
(docs/decisions/2026-10-10-retire-in-github-claude-review.md); the snapshots stay as the evidence behind that record.
"""

import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_INDEX = ROOT / "evidence/artifacts/claude-federation-docs-20261010/snapshots.json"


class DocumentationSnapshotTests(unittest.TestCase):
    def test_pull_request_subject_remains_a_derivation_from_prefix_and_event_suffix(self):
        # Retained GitHub OIDC revision 35d79cb1:332-336 and 352-359, retrieved 2026-10-10.
        source = ROOT / "evidence/artifacts/claude-federation-docs-20261010/docs.github.com_actions_reference_security_oidc.txt"
        raw = source.read_bytes()
        digest = "35d79cb17e94732a467c63e59c3a01d18029b47f4b5f9cbf15d92037164b03cd"
        self.assertEqual(hashlib.sha256(raw).hexdigest(), digest)
        lines = raw.decode().splitlines()
        self.assertIn("Syntax: repo:ORG-NAME/REPO-NAME:pull_request", lines[334])
        self.assertIn("Syntax: repo:OWNER@OWNER-ID/REPO@REPO-ID:ref:refs/heads/BRANCH", lines[354])
        decision = (ROOT / "docs/decisions/2026-10-08-claude-actions-pr-review.md").read_text()
        claim = decision.split('- **A `pull_request` trigger**', 1)[1].split('- **`workflow_run`', 1)[0]
        for surface, text, qualifiers in (
            ("decision", claim, ("derived immutable form", "sub_claim_prefix", "Filtering for pull_request events",
                                 "derivation, not an example", "immutable-subject section", "sha256:" + digest)),
        ):
            with self.subTest(surface=surface):
                normalized = " ".join(text.replace("\n# ", " ").split())
                self.assertIn("repo:OWNER@OWNER-ID/REPO@REPO-ID:pull_request", normalized)
                for qualifier in qualifiers:
                    self.assertIn(qualifier, normalized)

    def test_the_federation_concepts_snapshot_is_retained(self):
        # Retained Claude WIF concepts revision d929e368:42, retrieved 2026-10-10.
        source = ROOT / "evidence/artifacts/claude-federation-docs-20261010/platform.claude.com_workload-identity-federation.md"
        raw = source.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),
                         "d929e36810bcfdcc7a9bf5de39df8b08fbfde60a6d4c138b097f0940feb13bb7")
        self.assertIn("all configured matchers must pass for the JWT to be accepted", raw.decode().splitlines()[41])

    def test_cited_vendor_revisions_match_retained_bytes_and_registry(self):
        self.assertTrue(SNAPSHOT_INDEX.is_file(), "no retained vendor-document revision index")
        index = json.loads(SNAPSHOT_INDEX.read_text())
        manifest = json.loads((ROOT / "manifests/evidence.json").read_text())
        registered = {row["path"]: row for row in manifest["files"]}
        decision = (ROOT / "docs/decisions/2026-10-10-claude-federation-diagnostics.md").read_text()
        self.assertEqual(len(index["snapshots"]), 3)
        for row in index["snapshots"]:
            with self.subTest(snapshot=row["id"]):
                raw = (ROOT / row["path"]).read_bytes()
                digest = hashlib.sha256(raw).hexdigest()
                self.assertEqual(digest, row["sha256"])
                self.assertEqual(len(raw), row["bytes"])
                self.assertEqual(row["revision"], "sha256:" + digest)
                self.assertEqual(row["retrieved_on"], "2026-10-10")
                self.assertEqual(registered[row["path"]]["sha256"], digest)
                self.assertEqual(registered[row["path"]]["bytes"], len(raw))
                self.assertIn(row["revision"], decision)
                self.assertIn(str(row["bytes"]), decision)
                self.assertIn(Path(row["path"]).name, decision)
                lines = raw.decode().splitlines()
                for locator in row["locators"]:
                    self.assertIn(locator["contains"], lines[locator["line"] - 1])


if __name__ == "__main__":
    unittest.main()
