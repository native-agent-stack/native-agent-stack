"""Synthetic controls for the published native-capture masking boundary."""
import importlib.util
import hashlib
import json
import sys
from pathlib import Path
import unittest

MODULE = Path(__file__).resolve().parents[1] / "evidence/artifacts/final-prep-semantic-rag-20261016/mask_capture.py"
SPEC = importlib.util.spec_from_file_location("semantic_rag_capture_mask", MODULE)
MASK = importlib.util.module_from_spec(SPEC)
_prior_bytecode = sys.dont_write_bytecode
try:
    sys.dont_write_bytecode = True
    SPEC.loader.exec_module(MASK)
finally:
    sys.dont_write_bytecode = _prior_bytecode


class CaptureMaskTests(unittest.TestCase):
    def test_preserves_non_private_bytes_and_native_failure(self):
        raw = b"\x1b[31mFAIL\x1b[0m\r\n2 failed; 3 passed\n\x00\xff"
        self.assertEqual(MASK.mask_capture(raw), raw)

    def test_masks_paths_without_dropping_failure_or_line(self):
        raw = b'error at "/home/example/private/file.py:12"\npath=/Users/example/file\n'
        expected = b'error at "<PRIVATE_HOME_PATH>"\npath=<PRIVATE_HOME_PATH>\n'
        masked = MASK.mask_capture(raw)
        self.assertEqual(masked, expected)
        self.assertEqual(masked.count(b"\n"), raw.count(b"\n"))

    def test_is_deterministic_and_idempotent(self):
        raw = b"/home/example/file\nresult: 107 files; 2517 tests\n"
        first = MASK.mask_capture(raw)
        self.assertEqual(first, MASK.mask_capture(raw))
        self.assertEqual(first, MASK.mask_capture(first))

    def test_preserves_public_paths_and_empty_stream(self):
        raw = b"/work/socraticode/tests/unit/example.test.ts\n/runtime/vllm/module.py\n"
        self.assertEqual(MASK.mask_capture(raw), raw)
        self.assertEqual(MASK.mask_capture(b""), b"")

    def test_masks_uuid_tokens_without_hiding_error_counts(self):
        uuid = b"22222222" + b"-2222-4222-8222-222222222222"
        raw = b'Bad Request pointId=' + uuid + b'; 2 failed\n'
        self.assertEqual(MASK.mask_capture(raw), b'Bad Request pointId=<UUID>; 2 failed\n')

    def test_masks_explicit_scratch_root_and_preserves_native_result(self):
        scratch = b"/var/tmp/synthetic-private-root"
        raw = b'{"status":"written","out_dir":"' + scratch + b'/packets","packet_count":20}\n'
        expected = b'{"status":"written","out_dir":"<PRIVATE_SCRATCH_ROOT>/packets","packet_count":20}\n'
        masked = MASK.mask_capture(raw, scratch_root=scratch)
        self.assertEqual(masked, expected)
        self.assertEqual(MASK.mask_capture(masked, scratch_root=scratch), expected)
        self.assertEqual(MASK.mask_capture(b"/work/packets\n", scratch_root=scratch), b"/work/packets\n")


class PublishedCaptureContractTests(unittest.TestCase):
    def test_complete_published_streams_match_recorded_hashes(self):
        root = Path(__file__).resolve().parents[1]
        record = json.loads((MODULE.parent / "native-checks.json").read_text())
        self.assertGreaterEqual(len(record["commands"]), 11)
        for command in record["commands"]:
            self.assertIsInstance(command["return_code"], int)
            self.assertTrue(command["command"])
            self.assertNotIn("output_excerpt", command)
            for stream in command["streams"].values():
                raw = (root / stream["path"]).read_bytes()
                self.assertEqual(len(raw), stream["bytes"])
                self.assertEqual(hashlib.sha256(raw).hexdigest(), stream["sha256"])
                self.assertFalse(stream["raw_digest_published"])

    def test_reported_counts_have_exact_native_line_witnesses(self):
        root = Path(__file__).resolve().parents[1]
        record = json.loads((MODULE.parent / "native-checks.json").read_text())
        for value in record["values"]:
            lines = (root / value["path"]).read_text().splitlines()
            self.assertEqual(lines[value["line"] - 1], value["text"])


if __name__ == "__main__":
    unittest.main()
