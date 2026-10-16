"""Custody regressions; these synthetic strings are not runtime evidence."""

import importlib.util
from pathlib import Path
import unittest


SOURCE = Path(__file__).with_name("mask_capture.py")
spec = importlib.util.spec_from_file_location("mask_capture", SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class MaskCaptureTests(unittest.TestCase):
    def test_preserves_failure_command_and_output(self):
        raw = (
            b'Script started [COMMAND="/scratch/native/tool /checkout/test.pdf"]\r\n'
            b'\x1b[31mFAILED: 2 tests; 55 passed\x1b[0m\r\n'
            b'Script done [COMMAND_EXIT_CODE="1"]\r\n'
        )
        expected = (
            b'Script started [COMMAND="<SCRATCH>/native/tool <REPO>/test.pdf"]\n'
            b'FAILED: 2 tests; 55 passed\n'
            b'Script done [COMMAND_EXIT_CODE="1"]\n'
        )
        self.assertEqual(module.mask(raw, "/scratch", "/checkout"), expected)

    def test_does_not_strip_public_digest_or_success(self):
        raw = b"sha256:" + b"a" * 64 + b'\nCOMMAND_EXIT_CODE="0"\n'
        self.assertEqual(module.mask(raw, "/scratch", "/checkout"), raw)

    def test_strips_native_progress_control_without_losing_text(self):
        raw = b"\x1b]9;4;3\x07Indexing: 6/6\x1b]9;4;0\x07\r\n"
        self.assertEqual(module.mask(raw, "/scratch", "/checkout"), b"Indexing: 6/6\n")

    def test_idempotent_and_rejects_invalid_utf8(self):
        first = module.mask(b"/scratch/file\rprogress\r\n", "/scratch", "/checkout")
        self.assertEqual(module.mask(first, "/scratch", "/checkout"), first)
        with self.assertRaises(UnicodeDecodeError):
            module.mask(b"\xff", "/scratch", "/checkout")

    def test_container_identifier_is_context_specific(self):
        raw = b"Script started\n" + b"a" * 64 + b"\nScript done\n"
        self.assertEqual(module.mask(raw, "/scratch", "/checkout"), raw)
        masked = module.mask(raw, "/scratch", "/checkout", container_create=True)
        self.assertEqual(masked, b"Script started\n<CONTAINER_ID>\nScript done\n")


if __name__ == "__main__":
    unittest.main()
