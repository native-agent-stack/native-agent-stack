"""Synthetic unit fixtures only; optional private-capture reproduction check.

None of the synthetic strings in these tests is an E2E or invoke receipt.
The optional custody check reads existing bytes and starts no component.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import unittest

from mask_receipts import mask_capture, stream_digest

PRIVATE_CAPTURE: Path | None = None
PUBLISHED_CAPTURE: Path | None = None
SUPPLEMENT_CAPTURE: Path | None = None
PRIVATE_SOURCES: Path | None = None


def unit_fixture() -> list[dict]:
    """Invented test data, explicitly separate from the real native capture."""
    fixture_sha = "1" * 40
    scratch = "/var/tmp/example-unit-fixture"
    output = json.dumps({"items": [{"head": {"sha": fixture_sha}}]})
    rows = []
    for name, stdout, stderr, rc in [
        ("worktrunk-list-created", output, "", 0),
        ("negative-probe", "", scratch + " " + fixture_sha[:7], 2),
        ("public-output", "Unicode: λ\r\nLiteral: `text` $word\n", "", 1),
    ]:
        rows.append({"id": name, "command": scratch + "/prefix/tool --example", "cwd": scratch + "/repo", "started_at": "2026-01-01T00:00:00Z", "completed_at": "2026-01-01T00:00:01Z", "exit_code": rc, "expected_exit_code": rc, "stdout": stdout, "stderr": stderr, "stdout_sha256": stream_digest(stdout), "stderr_sha256": stream_digest(stderr)})
    return rows


class MaskReceiptTests(unittest.TestCase):
    def test_committed_derivative_has_valid_published_stream_hashes(self) -> None:
        published = json.loads((Path(__file__).parent / "native-commands.json").read_text())
        self.assertEqual(published["record_type"], "masked_derivative_of_native_capture")
        self.assertTrue(published["commands"])
        for row in published["commands"]:
            for stream in ("stdout", "stderr"):
                self.assertEqual(row[stream + "_sha256"], stream_digest(row[stream]))

    def test_committed_derivative_withholds_generated_upstream_text(self) -> None:
        published = json.loads((Path(__file__).parent / "native-commands.json").read_text())
        rows = {row["id"]: row for row in published["commands"]}
        self.assertTrue(rows["gh-bash-completion"]["stdout"] == "<UPSTREAM_GENERATED_COMPLETION_WITHHELD>\n", "Generated completion must remain private")
        self.assertTrue(rows["gh-pr-review-help"]["stdout"] == "<UPSTREAM_HELP_TEXT_WITHHELD>\n", "Help text must remain private")

    def test_committed_source_record_retains_locators_without_source_quotations(self) -> None:
        sources = json.loads((Path(__file__).parent / "source-reads.json").read_text())
        for source in sources["reads"]:
            for excerpt in source.get("excerpts", []):
                self.assertEqual(excerpt["text"], "<UPSTREAM_SOURCE_TEXT_WITHHELD>")

    def test_deterministic_and_input_unchanged(self) -> None:
        raw = unit_fixture()
        prior = copy.deepcopy(raw)
        self.assertEqual(mask_capture(raw), mask_capture(raw))
        self.assertEqual(raw, prior)

    def test_private_paths_and_fixture_identity_are_marked(self) -> None:
        result = mask_capture(unit_fixture())
        text = json.dumps(result)
        self.assertNotIn("/var/tmp/example-unit-fixture", text)
        self.assertNotIn("1" * 7, text)
        self.assertIn("<SCRATCH>", text)
        self.assertIn("<FIXTURE_COMMIT>", text)
        self.assertEqual(result["record_type"], "masked_derivative_of_native_capture")

    def test_no_private_stream_digest_is_published(self) -> None:
        raw = unit_fixture()
        private_hash = raw[1]["stderr_sha256"]
        self.assertNotIn(private_hash, json.dumps(mask_capture(raw)))

    def test_published_hashes_cover_published_bytes(self) -> None:
        for row in mask_capture(unit_fixture())["commands"]:
            for stream in ("stdout", "stderr"):
                self.assertEqual(row[stream + "_sha256"], hashlib.sha256(row[stream].encode("utf-8")).hexdigest())

    def test_native_exit_codes_and_unmasked_crlf_are_preserved(self) -> None:
        raw = unit_fixture()
        rows = mask_capture(raw)["commands"]
        self.assertEqual([r["exit_code"] for r in rows], [0, 2, 1])
        self.assertEqual(rows[2]["stdout"], raw[2]["stdout"])
        self.assertIn("\r\n", rows[2]["stdout"])

    def test_tampered_native_capture_is_rejected(self) -> None:
        raw = unit_fixture()
        raw[2]["stdout"] += "tampered"
        with self.assertRaisesRegex(ValueError, "Native stream digest mismatch"):
            mask_capture(raw)

    def test_private_capture_reproduces_published_derivative(self) -> None:
        if PRIVATE_CAPTURE is None or PUBLISHED_CAPTURE is None:
            self.skipTest("Private native capture not supplied; synthetic unit checks alone do not establish custody reproduction")
        raw = json.loads(PRIVATE_CAPTURE.read_text(encoding="utf-8"))
        published = json.loads(PUBLISHED_CAPTURE.read_text(encoding="utf-8"))
        # Never include private instances or their digests in a failed assertion.
        supplement = json.loads(SUPPLEMENT_CAPTURE.read_text()) if SUPPLEMENT_CAPTURE else None
        self.assertTrue(mask_capture(raw, supplement) == published, "Published derivative does not reproduce under the declared rule")

    def test_private_source_locator_derivative_reproduces(self) -> None:
        if PRIVATE_SOURCES is None:
            self.skipTest("Private source projection not supplied")
        from mask_receipts import mask_source_reads
        published = json.loads((Path(__file__).parent / "source-reads.json").read_text())
        self.assertTrue(mask_source_reads(json.loads(PRIVATE_SOURCES.read_text())) == published, "Source locator derivative does not reproduce")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", type=Path)
    parser.add_argument("--published", type=Path)
    parser.add_argument("--supplement", type=Path)
    parser.add_argument("--source-raw", type=Path)
    args, remaining = parser.parse_known_args()
    PRIVATE_CAPTURE, PUBLISHED_CAPTURE = args.raw, args.published
    SUPPLEMENT_CAPTURE, PRIVATE_SOURCES = args.supplement, args.source_raw
    unittest.main(argv=["test_mask_receipts.py", *remaining])
