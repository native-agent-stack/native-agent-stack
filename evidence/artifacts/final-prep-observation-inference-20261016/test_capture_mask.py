"""Synthetic custody controls; these are not component E2E measurements."""

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

from capture_native import record
from mask_capture import mask_bytes, publish, replacements


class CaptureMaskTests(unittest.TestCase):
    def test_preserves_nonmatching_binary_bytes_and_line_endings(self):
        raw = b"\x00\xff first\r\nprivate/path\nlast\x80"
        masked = mask_bytes(raw, replacements({"<OWNED_PATH>": "private/path"}))
        self.assertEqual(masked, b"\x00\xff first\r\n<OWNED_PATH>\nlast\x80")

    def test_longest_match_prevents_parent_hiding_specific_root(self):
        pairs = replacements({"<PARENT>": "/private", "<CHECKOUT>": "/private/project"})
        self.assertEqual(mask_bytes(b"/private/project/file /private/else", pairs), b"<CHECKOUT>/file <PARENT>/else")

    def test_no_match_is_byte_identical(self):
        self.assertEqual(mask_bytes(b"native SUCCESS\n", replacements({"<ROOT>": "/private"})), b"native SUCCESS\n")

    def test_rejects_ambiguous_empty_and_recursive_mapping(self):
        for mapping in [{"bad": "value"}, {"<A>": ""}, {"<A>": "same", "<B>": "same"}, {"<A>": "<B>"}, {"<PATH>": "PATH"}]:
            with self.subTest(mapping=mapping), self.assertRaises(ValueError):
                replacements(mapping)

    def test_real_subprocess_nonzero_is_not_replaced_by_success(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result = record(root / "raw", "fixture", [sys.executable, "-c", "import sys;sys.stdout.buffer.write(b'ok\\r\\n');sys.stderr.buffer.write(b'bad\\xff');sys.exit(7)"], root, {"PATH": "/usr/bin:/bin"}, 10)
            self.assertEqual(result["exit_code"], 7)
            self.assertEqual((root / "raw/fixture/stdout.bin").read_bytes(), b"ok\r\n")
            self.assertEqual((root / "raw/fixture/stderr.bin").read_bytes(), b"bad\xff")
            with self.assertRaises(FileExistsError):
                record(root / "raw", "fixture", [sys.executable, "-V"], root, {}, 10)

    def test_public_derivative_reproduces_and_omits_private_hashes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            record(root / "raw", "fixture", [sys.executable, "-c", "print('private/path')"], root, {"PATH": "/usr/bin:/bin"}, 10)
            mapping = {"<VALUE>": "private/path", "<SCRATCH>": str(root)}
            self.assertEqual(publish(root / "raw", root / "one", mapping), 1)
            self.assertEqual(publish(root / "raw", root / "two", mapping), 1)
            for path in (root / "one").iterdir():
                self.assertEqual(path.read_bytes(), (root / "two" / path.name).read_bytes())
            metadata = json.loads((root / "one/fixture.json").read_text())
            self.assertNotIn("raw_streams", metadata)
            stream = (root / "one/fixture.stdout.txt").read_bytes()
            self.assertEqual(stream, b"<VALUE>\n")
            self.assertEqual(metadata["streams"]["stdout"]["sha256"], hashlib.sha256(stream).hexdigest())
            self.assertEqual(metadata["raw_capture_name"], "fixture")

    def test_refuses_tampered_raw_stream(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            record(root / "raw", "fixture", [sys.executable, "-c", "print('native')"], root, {}, 10)
            (root / "raw/fixture/stdout.bin").write_bytes(b"substituted")
            with self.assertRaises(ValueError):
                publish(root / "raw", root / "out", {})


if __name__ == "__main__":
    unittest.main()
