"""Synthetic unit controls for the masker, never candidate E2E evidence."""

import hashlib
import unittest

from mask_capture import mask_bytes, masked_record


class MaskCaptureTests(unittest.TestCase):
    def test_preserves_failure_counts_line_endings_and_trailing_bytes(self):
        raw = b"\x1b[31mERROR /private/scratch/test\x1b[0m\r\n15 passed; 2 failed\n \t\n"
        expected = b"ERROR <scratch>/test\r\n15 passed; 2 failed\n \t\n"
        self.assertEqual(mask_bytes(raw, b"/private/scratch"), expected)

    def test_unmatched_bytes_and_empty_output_are_preserved(self):
        raw = b"\x00\xff exact stdout\r\n\n"
        self.assertEqual(mask_bytes(raw, b"/private/scratch"), raw)
        self.assertEqual(mask_bytes(b"", b"/private/scratch"), b"")

    def test_idempotent_without_summarization(self):
        raw = b"\n".join(b"row " + str(i).encode() for i in range(500))
        masked = mask_bytes(raw, b"/private/scratch")
        self.assertEqual(masked, raw)
        self.assertEqual(mask_bytes(masked, b"/private/scratch"), raw)

    def test_hash_binds_only_published_bytes_and_missing_custody_stays_gap(self):
        raw = b"/private/scratch ERROR"
        masked = mask_bytes(raw, b"/private/scratch")
        record = masked_record("native.log", "outputs/native.log", masked)
        self.assertEqual(record["published_sha256"], hashlib.sha256(masked).hexdigest())
        self.assertNotIn(hashlib.sha256(raw).hexdigest(), str(record))
        self.assertNotIn("/private/scratch", str(record))
        self.assertNotIn("exit_code", record)
        self.assertIn("plain output file alone does not establish", record["command_rc_custody"])

    def test_native_recorder_command_and_failure_survive_private_path_masking(self):
        raw = b'Script started on 2026-10-16 00:00:00+00:00 [COMMAND="/private/host/bin/tool /private/scratch/x" <not executed on terminal>]\r\nERROR\r\nScript done on 2026-10-16 00:00:01+00:00 [COMMAND_EXIT_CODE="7"]\n'
        masked = mask_bytes(raw, b"/private/scratch", ((b"/private/host", b"<host-home>"),))
        self.assertIn(b'COMMAND="<host-home>/bin/tool <scratch>/x"', masked)
        self.assertIn(b'COMMAND_EXIT_CODE="7"', masked)
        self.assertIn(b"ERROR\r\n", masked)
        record = masked_record("native.typescript", "captures/native.typescript", masked)
        self.assertEqual(record["return_code"], 7)
        self.assertEqual(record["command_display"], "<host-home>/bin/tool <scratch>/x")
        self.assertEqual(record["return_code_line"], 3)

    def test_missing_native_footer_is_not_filled_in(self):
        raw = b'Script started on 2026-10-16 [COMMAND="true"]\nall good\n'
        record = masked_record("incomplete.typescript", "captures/incomplete.typescript", raw)
        self.assertNotIn("return_code", record)

    def test_rejects_ambiguous_masks_and_private_capture_paths(self):
        for prefix in (b"", b"/"):
            with self.assertRaises(ValueError):
                mask_bytes(b"input", prefix)
        with self.assertRaises(ValueError):
            masked_record("/private/native.log", "outputs/native.log", b"output")


if __name__ == "__main__":
    unittest.main()
