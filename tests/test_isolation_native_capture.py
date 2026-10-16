"""Synthetic controls for byte custody; these are not product E2E evidence."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

PATH = Path(__file__).resolve().parents[1] / "blueprints/convergence-practice/isolation-capture-20261016/capture.py"
spec = importlib.util.spec_from_file_location("isolation_capture", PATH)
capture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capture)


class NativeCaptureTests(unittest.TestCase):
    def test_native_bytes_and_nonzero_exit_survive_before_masking(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            command = [sys.executable, "-c", "import os; os.write(1,b'prefix\\xff\\r\\n'); os.write(2,b'failure\\x00'); raise SystemExit(7)"]
            meta = capture.record(root, "example", command, root, {})
            self.assertEqual(meta["exit_code"], 7)
            self.assertEqual(meta["argv"], command)
            self.assertEqual((root / "example/stdout.bin").read_bytes(), b"prefix\xff\r\n")
            self.assertEqual((root / "example/stderr.bin").read_bytes(), b"failure\x00")
            rendered = capture.render(root / "example", {"prefix": "<PREFIX>"})
            self.assertEqual(rendered["example.stdout.txt"], b"<PREFIX>\xff\r\n")
            public = json.loads(rendered["example.json"])
            self.assertNotIn(meta["streams"]["stdout"]["sha256"], rendered["example.json"].decode())
            self.assertEqual(public["streams"]["stdout"]["sha256"], capture.digest(b"<PREFIX>\xff\r\n"))

    def test_missing_or_modified_raw_capture_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            capture.record(root, "example", [sys.executable, "-c", "print('original')"], root, {})
            path = root / "example/stdout.bin"
            path.write_bytes(b"stand-in\n")
            with self.assertRaisesRegex(ValueError, "private capture bytes"):
                capture.render(root / "example", {})
            path.unlink()
            with self.assertRaises(FileNotFoundError):
                capture.render(root / "example", {})

    def test_literal_mask_preserves_public_hashes_and_overlapping_paths(self):
        public_pin = b"b49ca7eea9b03145791a5b94eccaf9c59412ed37"
        raw = b"/private/work/file /private/work " + public_pin + b"\r\n"
        masked = capture.mask_bytes(raw, {"/private/work": "<ROOT>", "/private/work/file": "<FILE>"})
        self.assertEqual(masked, b"<FILE> <ROOT> " + public_pin + b"\r\n")
        self.assertEqual(capture.mask_bytes(masked, {"/private/work": "<ROOT>"}), masked)
        with self.assertRaises(ValueError):
            capture.mask_bytes(raw, {"": "<ROOT>"})
        with self.assertRaises(ValueError):
            capture.mask_bytes(raw, {"private": "unmarked"})

    def test_reproduction_is_deterministic_and_rejects_different_derivative(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw = root / "raw"
            capture.record(raw, "example", [sys.executable, "-c", "print('owned-path')"], root, {})
            rules = root / "rules.json"
            rules.write_text(json.dumps({"owned-path": "<OWNED>"}))
            capture.publish(raw, rules, root / "first")
            capture.publish(raw, rules, root / "second")
            for file in (root / "first").iterdir():
                self.assertEqual(file.read_bytes(), (root / "second" / file.name).read_bytes())
            (root / "second/example.stdout.txt").write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "different derivative"):
                capture.publish(raw, rules, root / "second")

    def test_capture_name_cannot_overwrite_originals_or_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            argv = [sys.executable, "-c", "print('original')"]
            capture.record(root, "example", argv, root, {})
            with self.assertRaises(FileExistsError):
                capture.record(root, "example", argv, root, {})
            with self.assertRaises(ValueError):
                capture.record(root, "../escape", argv, root, {})


if __name__ == "__main__":
    unittest.main()
