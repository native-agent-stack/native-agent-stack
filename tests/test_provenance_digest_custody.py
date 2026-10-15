"""A digest in a receipt's `provenance` list binds a repository file, never unpublished bytes (correction #161; #1047 P1).

tests/test_published_digest_privacy.py finds a digest that hashes unmasked bytes once a mask is put back. It cannot reach a
`provenance` entry whose preimage is not published at all, such as a run log, a Claude stream or a home-state snapshot kept in a
private tree: no mask can be put back, yet the digest still lets anyone confirm a guessed path or name offline, and nothing in the
repository shows which bytes it covers. The GPT read of #1047 found ten of them in a new receipt (verdict P1).

findings() walks every JSON file under SCANNED. In each `provenance` list, at any depth, an entry that holds a 64-hex string value
must name a repository file under one of FILE_KEYS, resolved against the JSON file's directory and then the checkout root, that
stays inside the checkout, and the file's sha256 must be that value. LEGACY freezes the receipts that predate the check with the
number of such entries each still has: a count may fall, and must then be lowered here, but never rise, and a file that is not
listed fails on its first unresolved entry. Findings are reported as file and count, never as a digest.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCANNED = ("evidence", "blueprints", "manifests")
DIGEST = re.compile(r"[0-9a-f]{64}")
FILE_KEYS = ("path", "file", "log", "output_path", "raw_path", "capture")
HARBOR_RECEIPT = "evidence/receipts/harbor-smoke-20261012.json"
REGISTRATION_RECORD = "docs/decisions/2026-10-15-unrun-registration-rules.md"

LEGACY = {
    # file -> provenance digests that hash no published repository file, at the freeze (#1047)
    "evidence/receipts/artifact-reductions.json": 3,
    "evidence/receipts/codex-01592-qualification-20260930.json": 13,
    "evidence/receipts/component-history.json": 1,
    "evidence/receipts/desktop-cli-workflows.json": 5,
    "evidence/receipts/local-inference-c2-serving-switch-20260926.json": 2,
    "evidence/receipts/native-context-memory.json": 2,
    "evidence/receipts/native-memory.json": 1,
    "evidence/receipts/native-rag.json": 3,
    "evidence/receipts/runtime-tools.json": 3,
    "evidence/receipts/vllm-030-switch-20260925.json": 6,
    "evidence/receipts/vllm-030-switch-laptop-20260926.json": 2,
    "evidence/receipts/vllm-compatibility.json": 3,
}
LEGACY_ENTRIES = 44  # the sum at the freeze; lower it with each entry fixed, never raise it


def confined_file(base: Path, root: Path, reference: str) -> Path | None:
    """The regular file `reference` names under base, only if it stays inside root (no .., no absolute path, no symlink)."""
    if not reference or reference.startswith(("/", "\\")) or ".." in Path(reference.replace("\\", "/")).parts:
        return None
    candidate = base / reference
    try:
        inside = candidate.resolve().is_relative_to(root.resolve())
    except OSError:
        return None
    if not inside or candidate.is_symlink() or not candidate.is_file():
        return None
    return candidate


def resolves(entry: dict, directory: Path, root: Path, digest: str) -> bool:
    for key in FILE_KEYS:
        reference = entry.get(key)
        if not isinstance(reference, str) or reference.startswith(("http://", "https://")):
            continue
        for base in (directory, root):
            found = confined_file(base, root, reference)
            if found is not None and hashlib.sha256(found.read_bytes()).hexdigest() == digest:
                return True
    return False


def unresolved_in(node, directory: Path, root: Path) -> int:
    count = 0
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "provenance" and isinstance(value, list):
                for entry in value:
                    if isinstance(entry, dict):
                        for held in entry.values():
                            if isinstance(held, str) and DIGEST.fullmatch(held) and not resolves(entry, directory, root, held):
                                count += 1
            count += unresolved_in(value, directory, root)
    elif isinstance(node, list):
        for value in node:
            count += unresolved_in(value, directory, root)
    return count


def findings(root: Path, subdirs: tuple[str, ...] = SCANNED) -> dict[str, int]:
    """Repository-relative JSON file -> unresolved provenance digests, for files that have any."""
    found = {}
    for subdir in subdirs:
        for directory, _, names in os.walk(root / subdir):
            for name in sorted(names):
                if not name.endswith(".json"):
                    continue
                path = Path(directory) / name
                try:
                    document = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    continue
                count = unresolved_in(document, Path(directory), root)
                if count:
                    found[path.relative_to(root).as_posix()] = count
    return found


class ProvenanceDigestCustodyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.found = findings(ROOT)

    def test_no_provenance_digest_lacks_a_published_preimage(self):
        unlisted = {path: count for path, count in self.found.items() if count > LEGACY.get(path, 0)}
        self.assertEqual(
            unlisted, {},
            "provenance digests that hash no published repository file (file: count). Remove the digest and keep the "
            "original private, or publish a sanitized projection and hash those bytes, naming it under `path`.",
        )

    def test_the_frozen_list_only_shrinks(self):
        stale = {path: (frozen, self.found.get(path, 0)) for path, frozen in LEGACY.items() if self.found.get(path, 0) < frozen}
        self.assertEqual(stale, {}, "lower these LEGACY counts (file: (frozen, found)); the list only shrinks")
        self.assertEqual(sum(LEGACY.values()), LEGACY_ENTRIES)

    def test_the_harbor_receipt_digests_hash_the_files_it_publishes(self):
        receipt = json.loads((ROOT / HARBOR_RECEIPT).read_text(encoding="utf-8"))
        entries = receipt["provenance"]
        self.assertTrue(entries)
        for entry in entries:
            with self.subTest(name=entry.get("name")):
                self.assertRegex(entry["sha256"], DIGEST.pattern)
                self.assertTrue(resolves(entry, (ROOT / HARBOR_RECEIPT).parent, ROOT, entry["sha256"]))
        unpublished = json.dumps(receipt["unpublished_originals"])
        self.assertEqual(DIGEST.findall(unpublished), [], "the private originals carry no digest of any kind")

    def test_the_harbor_receipt_is_not_a_legacy_site(self):
        self.assertNotIn(HARBOR_RECEIPT, LEGACY)
        self.assertNotIn(HARBOR_RECEIPT, self.found)

    def test_registration_record_cites_private_gpt_review_without_a_digest(self):
        text = (ROOT / REGISTRATION_RECORD).read_text(encoding="utf-8")
        citation = re.search(r"The Astra fix-one read\b.*?(?=added two P2 blockers)", text, re.DOTALL)
        self.assertIsNotNone(citation, "identify the private GPT review citation for custody validation")
        self.assertEqual(len(DIGEST.findall(citation.group(0))), 0,
                         "the private GPT review is cited by name without any unpublished-byte digest")
        self.assertIn("GPT-VERDICT-94f4c7649.md", citation.group(0))


class SyntheticDetectorTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "evidence/receipts").mkdir(parents=True)

    def write(self, relative: str, content: bytes | str) -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content if isinstance(content, bytes) else content.encode())
        return path

    def receipt(self, provenance, key="provenance", nested=False):
        document = {"id": "fixture", key: provenance}
        if nested:
            document = {"id": "fixture", "data": {"inner": {key: provenance}}}
        self.write("evidence/receipts/fixture.json", json.dumps(document))
        return findings(self.root)

    def test_the_new_shape_a_digest_with_no_published_file_is_found(self):
        digest = hashlib.sha256(b"unsanitized run output").hexdigest()
        found = self.receipt([{"name": "run.log", "sha256": digest, "disclosure": "Retained privately; only the result is exported."}])
        self.assertEqual(found, {"evidence/receipts/fixture.json": 1})

    def test_a_digest_of_the_published_file_it_names_passes(self):
        data = b"sanitized projection\n"
        self.write("evidence/artifacts/fixture/projection.txt", data)
        found = self.receipt([{"name": "projection", "path": "evidence/artifacts/fixture/projection.txt",
                               "sha256": hashlib.sha256(data).hexdigest()}])
        self.assertEqual(found, {})

    def test_a_path_next_to_the_json_file_resolves_too(self):
        data = b"neighbour\n"
        self.write("evidence/receipts/neighbour.txt", data)
        found = self.receipt([{"path": "neighbour.txt", "sha256": hashlib.sha256(data).hexdigest()}])
        self.assertEqual(found, {})

    def test_a_named_file_with_different_bytes_is_found(self):
        self.write("evidence/artifacts/fixture/projection.txt", b"published bytes\n")
        found = self.receipt([{"path": "evidence/artifacts/fixture/projection.txt",
                               "sha256": hashlib.sha256(b"unsanitized original\n").hexdigest()}])
        self.assertEqual(found, {"evidence/receipts/fixture.json": 1})

    def test_a_path_that_leaves_the_checkout_never_resolves(self):
        data = b"outside\n"
        outside = Path(self.temporary.name).parent / "custody-fixture-outside.txt"
        outside.write_bytes(data)
        self.addCleanup(outside.unlink)
        digest = hashlib.sha256(data).hexdigest()
        for reference in ("../custody-fixture-outside.txt", str(outside), "evidence/../../custody-fixture-outside.txt"):
            with self.subTest(reference=reference):
                found = self.receipt([{"path": reference, "sha256": digest}])
                self.assertEqual(found, {"evidence/receipts/fixture.json": 1})

    def test_a_symlink_to_a_file_is_not_a_published_preimage(self):
        data = b"linked\n"
        target = self.write("evidence/artifacts/fixture/real.txt", data)
        link = self.root / "evidence/artifacts/fixture/link.txt"
        link.symlink_to(target)
        found = self.receipt([{"path": "evidence/artifacts/fixture/link.txt", "sha256": hashlib.sha256(data).hexdigest()}])
        self.assertEqual(found, {"evidence/receipts/fixture.json": 1})

    def test_provenance_is_found_at_any_depth_and_other_lists_are_ignored(self):
        digest = hashlib.sha256(b"x").hexdigest()
        self.assertEqual(self.receipt([{"sha256": digest}], nested=True), {"evidence/receipts/fixture.json": 1})
        self.assertEqual(self.receipt([{"sha256": digest}], key="inputs"), {})

    def test_an_entry_without_a_digest_and_the_unpublished_list_are_clean(self):
        found = self.receipt([{"name": "run.log", "disclosure": "Retained privately; no digest is published."}])
        self.assertEqual(found, {})

    def test_only_the_scanned_directories_are_walked(self):
        self.write("docs/fixture.json", json.dumps({"provenance": [{"sha256": hashlib.sha256(b"y").hexdigest()}]}))
        self.assertEqual(findings(self.root), {})


if __name__ == "__main__":
    unittest.main()
