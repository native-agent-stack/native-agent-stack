"""Custody tests for the published deterministic native-output masking rule."""

import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "evidence/artifacts/final-durable-memory-20261016/mask_capture.py"
)
SPEC = importlib.util.spec_from_file_location("final_memory_mask", SCRIPT)
MASK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MASK)


class NativeCaptureMaskTests(unittest.TestCase):
    def test_preserves_binary_newlines_ansi_and_error_bytes(self):
        raw = b"\xff\x00\x1b[31merror\x1b[0m\r\n/var/tmp/private-run/store\nexit=2"
        expected = b"\xff\x00\x1b[31merror\x1b[0m\r\n<SCRATCH>/store\nexit=2"
        self.assertEqual(MASK.mask_capture(raw, b"/var/tmp/private-run"), expected)

    def test_empty_and_unrelated_native_output_stays_exact(self):
        for raw in [b"", b"189 passed, 0 failed\n", b"no trailing newline", b"\r\n"]:
            with self.subTest(raw=raw):
                self.assertEqual(MASK.mask_capture(raw, b"/var/tmp/private-run"), raw)

    def test_rejects_unsafe_prefix(self):
        for prefix in [b"", b"/", b"relative"]:
            with self.subTest(prefix=prefix), self.assertRaises(ValueError):
                MASK.mask_capture(b"native output", prefix)

    def test_cli_preserves_source_and_reproduces_derivative(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "raw.bin"
            target = Path(temp) / "published.bin"
            raw = b"/var/tmp/private-run/a\r\n/var/tmp/private-run/b\xff"
            source.write_bytes(raw)
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--source", str(source), "--output", str(target),
                 "--scratch-prefix", "/var/tmp/private-run"],
                capture_output=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, b"")
            self.assertEqual(source.read_bytes(), raw)
            self.assertEqual(target.read_bytes(), b"<SCRATCH>/a\r\n<SCRATCH>/b\xff")


if __name__ == "__main__":
    unittest.main()
