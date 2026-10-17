"""Synthetic fixtures test masking behavior; they are not execution evidence."""
import unittest

from mask_capture import mask


class LiteralMaskTests(unittest.TestCase):
    def test_preserves_nonmatching_bytes_including_binary_and_newlines(self):
        raw = b"\xffPASS\r\nwarning\n\x00last line"
        self.assertEqual(mask(raw, b"/private/scratch"), raw)

    def test_masks_every_literal_occurrence_without_line_filtering(self):
        raw = b"Cloning /private/scratch/work\nwarning at /private/scratch/tmp\n"
        self.assertEqual(mask(raw, b"/private/scratch"),
                         b"Cloning <SCRATCH_ARM>/work\nwarning at <SCRATCH_ARM>/tmp\n")

    def test_native_test_context_is_not_replaced_with_a_summary(self):
        raw = b"$ /private/scratch/bin/test\nWARN retained\nPASS suite\nTests: 48 passed\n"
        self.assertEqual(mask(raw, b"/private/scratch"),
                         b"$ <SCRATCH_ARM>/bin/test\nWARN retained\nPASS suite\nTests: 48 passed\n")

    def test_generated_status_cannot_reproduce_native_install_output(self):
        raw = b"added 3 packages in 10s\n"
        previous_standin = b'{"phase": "install", "exit_code": 0, "status": "completed"}\n'
        self.assertNotEqual(mask(raw, b"/private/scratch"), previous_standin)

    def test_idempotence(self):
        once = mask(b"/private/scratch/log\n", b"/private/scratch")
        self.assertEqual(mask(once, b"/private/scratch"), once)

    def test_rejects_nonabsolute_or_root_parameter(self):
        for value in (b"", b"/", b"relative", b"/private/\x00scratch", b"/<SCRATCH_ARM>"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                mask(b"unaltered native output", value)


if __name__ == "__main__":
    unittest.main()
