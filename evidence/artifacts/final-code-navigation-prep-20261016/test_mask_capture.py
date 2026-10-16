"""Synthetic unit fixtures for the mask; these are not candidate E2E runs."""

import unittest

from mask_capture import mask_bytes


class CaptureMaskTests(unittest.TestCase):
    def test_preserves_nonprivate_bytes_and_native_line_endings(self):
        raw = b"\x00\xff cmd /fixture/private/project\r\nrc=1\n188/192\t\r\n"
        bindings = [{"value": "/fixture/private", "placeholder": "$REPO"}]
        expected = b"\x00\xff cmd $REPO/project\r\nrc=1\n188/192\t\r\n"
        self.assertEqual(mask_bytes(raw, bindings), expected)

    def test_specific_prefix_wins_over_private_parent(self):
        raw = b"/fixture/person/tools/uv /fixture/person/other"
        bindings = [
            {"value": "/fixture/person", "placeholder": "$USERHOME"},
            {"value": "/fixture/person/tools", "placeholder": "$UV_BIN"},
        ]
        self.assertEqual(mask_bytes(raw, bindings), b"$UV_BIN/uv $USERHOME/other")
        self.assertEqual(mask_bytes(raw, bindings[::-1]), b"$UV_BIN/uv $USERHOME/other")

    def test_does_not_trim_summarize_or_append_output(self):
        raw = b"  unchanged stderr\r\n161 passed\nno final newline"
        self.assertEqual(mask_bytes(raw, []), raw)

    def test_marked_placeholders_survive_a_second_pass(self):
        bindings = [{"value": "/fixture/private", "placeholder": "$SCRATCH"}]
        first = mask_bytes(b"$SCRATCH /fixture/private/file", bindings)
        self.assertEqual(mask_bytes(first, bindings), first)

    def test_invalid_bindings_cannot_remove_arbitrary_output(self):
        for value in ("", "/", "relative"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                mask_bytes(b"unchanged", [{"value": value, "placeholder": "$RAW"}])
        with self.assertRaises(ValueError):
            mask_bytes(b"unchanged", [{"value": "/fixture", "placeholder": "unmarked"}])

    def test_duplicate_prefix_is_rejected(self):
        bindings = [
            {"value": "/fixture", "placeholder": "$FIRST"},
            {"value": "/fixture", "placeholder": "$SECOND"},
        ]
        with self.assertRaises(ValueError):
            mask_bytes(b"/fixture/file", bindings)


if __name__ == "__main__":
    unittest.main()
