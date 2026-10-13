"""The public handbook publishes neutral policy and public-input digests only.

Correction #213: private source records may be named, never copied or digested
here. The public specification is the numeric contract. No private record is
read or hashed by this guard, and failure messages contain paths only.

Mechanism: CPython v3.13.16 Doc/library/hashlib.rst:39-49 documents SHA256 over
the supplied bytes; scripts/host_receipts.py:1012-1029 at df3a477c applies that
same public-bytes boundary. Retained public vendor captures are the explicit
source-review exception, identified by their public URL and capture row.
Calendar validation reuses CPython v3.13.16's date constructor; the installed
upstream reference is Lib/_pydatetime.py:535-546.
"""
from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path
import re
import tempfile
import unittest
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
DOCS = "docs/trading-handbook"
ARTIFACTS = "evidence/artifacts/trading-handbook-20261013"
INVENTORY = DOCS + "/sources/luld-bp-20261013.json"
PRIVATE_NAME = "account-c-calc-contracts-20261013.md"  # name-only provenance
SLOT = re.compile(r"\b(?:account|slot)[\s_-]+[a-z0-9]\b", re.IGNORECASE)
HEX = re.compile(r"(?<![a-z0-9])[0-9a-f]{7,64}(?![a-z0-9])", re.IGNORECASE)
DATED_REFERENCE = re.compile(
    r"(?<![\w-])[A-Za-z][A-Za-z0-9_.-]*[-_](?P<date>[0-9]{8})"
    r"(?=(?:\.[A-Za-z][A-Za-z0-9]*\b)|/)")
PUBLIC_HOSTS = {"www.luldplan.com", "cdn.luldplan.com", "docs.alpaca.markets", "raw.githubusercontent.com"}


def handbook_files(root: Path) -> list[Path]:
    return sorted(path for directory in (root / DOCS, root / ARTIFACTS)
                  if directory.is_dir() for path in directory.rglob("*") if path.is_file())


def dated_reference_spans(text: str) -> set[tuple[int, int]]:
    """Recognize calendar dates in dated file/directory references, not bare numbers."""
    spans = set()
    for match in DATED_REFERENCE.finditer(text):
        value = match.group("date")
        try:
            date(int(value[:4]), int(value[4:6]), int(value[6:]))
        except ValueError:
            continue
        spans.add(match.span("date"))
    return spans


def publication_findings(root: Path) -> tuple[list[str], list[str]]:
    """Inspect public files and their registrations; never dereference private inputs."""
    files = handbook_files(root)
    texts = {path.relative_to(root).as_posix(): path.read_text(encoding="utf-8") for path in files}
    inventory = json.loads((root / INVENTORY).read_text())
    public_digests = {hashlib.sha256(path.read_bytes()).hexdigest() for path in files
                      if path.name != PRIVATE_NAME}
    public_pins = set()
    for capture in inventory.get("public_captures", []):
        url = urlsplit(capture.get("url", ""))
        digest = capture.get("sha256", "")
        if (url.scheme == "https" and url.hostname in PUBLIC_HOSTS
                and capture.get("evidence_class") == "source_review"
                and re.fullmatch(r"[0-9a-f]{64}", digest)):
            public_digests.add(digest)
        if url.hostname == "raw.githubusercontent.com":
            public_pins.update(re.findall(r"(?<=/)[0-9a-f]{40}(?=/)", url.path))
    for key in ("public_contract", "upstream_engine"):
        pin = inventory.get(key, {}).get("commit", "")
        if re.fullmatch(r"[0-9a-f]{40}", pin):
            public_pins.add(pin)
    manifest = root / "manifests/evidence.json"
    if manifest.is_file():
        for row in json.loads(manifest.read_text()).get("files", []):
            relative = row.get("path", "")
            if relative.startswith((DOCS + "/", ARTIFACTS + "/")):
                texts["manifest registration for " + relative] = json.dumps(row)
    labels = [relative for relative, text in texts.items() if SLOT.search(text.replace(PRIVATE_NAME, ""))]
    allowed = public_digests | public_pins
    unresolved = []
    for relative, text in texts.items():
        # Calendar dates in dated references are not digest claims. Other 7+ hex tokens,
        # including shortened pins and MinerU locators, need a public binding.
        dates = dated_reference_spans(text)
        tokens = {match.group().lower() for match in HEX.finditer(text) if match.span() not in dates}
        if any(not any(digest.startswith(token) for digest in allowed) for token in tokens):
            unresolved.append(relative)
    return sorted(labels), sorted(unresolved)


class HandbookPublicationTests(unittest.TestCase):
    def test_public_handbook_excludes_account_slot_labels(self):
        labels, _ = publication_findings(ROOT)
        self.assertEqual(labels, [], "public handbook contains account/slot labels at these paths")

    def test_public_handbook_digests_and_prefixes_bind_public_inputs(self):
        _, unresolved = publication_findings(ROOT)
        self.assertEqual(unresolved, [], "handbook digests/prefixes lack public-input bindings at these paths")

    def fixture(self, root: Path, text: str):
        docs, artifacts = root / DOCS, root / ARTIFACTS
        (docs / "sources").mkdir(parents=True)
        artifacts.mkdir(parents=True)
        policy = b"Neutral trial policy; no measured account results.\n"
        digest = hashlib.sha256(policy).hexdigest()
        (artifacts / "neutral-policy.md").write_bytes(policy)
        capture = hashlib.sha256(b"Public vendor passage, synthetic fixture.\n").hexdigest()
        (root / INVENTORY).write_text(json.dumps({"public_captures": [{
            "url": "https://www.luldplan.com/", "sha256": capture,
            "evidence_class": "source_review"}]}))
        (docs / "page.md").write_text(text.format(public=digest, capture=capture))

    def test_neutral_policy_public_capture_and_name_only_reference_pass(self):
        with tempfile.TemporaryDirectory(dir="/var/tmp") as temporary:
            root = Path(temporary)
            self.fixture(root, "Policy {public}; public-page capture {capture}; provenance " + PRIVATE_NAME)
            self.assertEqual(publication_findings(root), ([], []))

    def test_registered_publication_applies_the_same_privacy_boundary(self):
        # Synthetic publication only; no private source or identity is read.
        with tempfile.TemporaryDirectory(dir="/var/tmp") as temporary:
            root = Path(temporary)
            self.fixture(root, "Neutral public policy.")
            relative = DOCS + "/account-" + chr(90).lower() + ".md"
            (root / DOCS / "page.md").rename(root / relative)
            raw = (root / relative).read_bytes()
            (root / "manifests").mkdir()
            (root / "manifests/evidence.json").write_text(json.dumps({"files": [{
                "path": relative, "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest()}]}))
            self.assertEqual(publication_findings(root),
                             (["manifest registration for " + relative], []))

    def test_slot_labels_and_private_digest_prefixes_are_refused(self):
        # Synthetic values only; no private source file is read or hashed.
        slot = "Account " + chr(90)
        for label in (slot, slot.lower().replace(" ", "_"), slot.replace(" ", "-")):
            with self.subTest(kind="slot-label"), tempfile.TemporaryDirectory(dir="/var/tmp") as temporary:
                root = Path(temporary)
                self.fixture(root, label)
                self.assertEqual(publication_findings(root)[0], [DOCS + "/page.md"])
        private = hashlib.sha256(b"Synthetic unpublished observation fixture.\n").hexdigest()
        for length in (7, 8, 12, 32, 40, 63, 64):
            with self.subTest(kind="private-digest", prefix_length=length), tempfile.TemporaryDirectory(dir="/var/tmp") as temporary:
                root = Path(temporary)
                self.fixture(root, "Unpublished input " + private[:length])
                self.assertEqual(publication_findings(root)[1], [DOCS + "/page.md"])

    def test_scoped_review_regression_refuses_unbound_numeric_prefix(self):
        # Deterministic synthetic data; no private file is read or hashed.
        candidates = (hashlib.sha256(("Synthetic unpublished input " + str(i)).encode()).hexdigest()
                      for i in range(1024))
        private = next(value for value in candidates
                       if value[:7].isdecimal() and not value[:8].isdecimal())
        for length in (7, 8):
            with self.subTest(prefix_length=length), tempfile.TemporaryDirectory(dir="/var/tmp") as temporary:
                root = Path(temporary)
                self.fixture(root, "Unpublished input " + private[:length])
                self.assertEqual(publication_findings(root)[1], [DOCS + "/page.md"])

    def test_calendar_reference_exception_is_context_bound(self):
        cases = [("policy-20261013.md", False), ("trading-handbook-20261013/policy.md", False),
                 ("Unpublished input 20261013", True), ("policy-20261340.md", True)]
        for text, refused in cases:
            with self.subTest(context=text), tempfile.TemporaryDirectory(dir="/var/tmp") as temporary:
                root = Path(temporary)
                self.fixture(root, text)
                self.assertEqual(publication_findings(root)[1], [DOCS + "/page.md"] if refused else [])


if __name__ == "__main__":
    unittest.main()
