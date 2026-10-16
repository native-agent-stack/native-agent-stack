"""Synthetic controls for the native recorder/masker public command boundaries."""
import json
import hashlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "evidence/artifacts/final-native-clients-prep-20261016"
RECORDER = ARTIFACT / "record_native.py"
MASKER = ARTIFACT / "mask_native.py"


class NativeCaptureCustodyTests(unittest.TestCase):
    def fixture(self, scratch):
        raw = scratch / "raw"
        result = subprocess.run([
            sys.executable, str(RECORDER), "--raw-dir", str(raw), "--id", "fixture",
            "--cwd", str(scratch), "--", sys.executable, "-c",
            "import os; os.write(1, b'/fixture/private/value'); os.write(2,b'')",
        ], capture_output=True)
        self.assertEqual(result.returncode, 0)
        mapping = scratch / "map.json"
        mapping.write_text(json.dumps([{"literal": "/fixture/private", "placeholder": "<PRIVATE>"}]))
        return raw, mapping

    def publish(self, raw, mapping, output):
        return subprocess.run([sys.executable, str(MASKER), "--raw-dir", str(raw),
                               "--map-file", str(mapping), "--out", str(output)],
                              capture_output=True)

    def test_recorder_retains_unmodified_bytes_and_nonzero_exit(self):
        with tempfile.TemporaryDirectory() as directory:
            scratch = Path(directory)
            command = [sys.executable, "-c", "import os,sys; os.write(1,b'\\xff\\x1b[31mraw\\r\\n'); os.write(2,b'failure-without-newline'); sys.exit(7)"]
            result = subprocess.run(
                [sys.executable, str(RECORDER), "--raw-dir", str(scratch / "raw"),
                 "--id", "binary-control", "--cwd", directory, "--", *command],
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
            capture = scratch / "raw/binary-control"
            self.assertEqual((capture / "stdout.bin").read_bytes(), b"\xff\x1b[31mraw\r\n")
            self.assertEqual((capture / "stderr.bin").read_bytes(), b"failure-without-newline")
            metadata = json.loads((capture / "capture.json").read_text())
            self.assertEqual(metadata["exit_code"], 7)
            self.assertEqual(metadata["argv"], command)
            self.assertEqual(metadata["cwd"], directory)

    def test_masked_derivative_preserves_all_bytes_except_named_literals(self):
        with tempfile.TemporaryDirectory() as directory:
            scratch = Path(directory)
            raw = scratch / "raw/example"
            raw.mkdir(parents=True)
            stdout = b"\xff\x1b[31m/fixture/private/long/x\r\n/fixture/private/y"
            stderr = b"failure-without-newline"
            metadata = {"schema_version": 1, "kind": "private_native_capture", "id": "example",
                        "argv": ["/fixture/private/tool", "--help"], "cwd": "/fixture/private/long",
                        "started_at": "2026-01-01T00:00:00Z", "finished_at": "2026-01-01T00:00:01Z",
                        "exit_code": 7}
            for stream, data in (("stdout", stdout), ("stderr", stderr)):
                (raw / (stream + ".bin")).write_bytes(data)
                metadata[stream] = {"name": stream + ".bin", "bytes": len(data),
                                    "sha256": hashlib.sha256(data).hexdigest()}
            (raw / "capture.json").write_text(json.dumps(metadata))
            mapping = scratch / "map.json"
            mapping.write_text(json.dumps([
                {"literal": "/fixture/private", "placeholder": "<PRIVATE>"},
                {"literal": "/fixture/private/long", "placeholder": "<LONG>"},
            ]))
            result = subprocess.run([sys.executable, str(MASKER), "--raw-dir", str(raw.parent),
                                     "--map-file", str(mapping), "--out", str(scratch / "published")],
                                    capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
            published = scratch / "published"
            self.assertEqual((published / "example.stdout.txt").read_bytes(),
                             b"\xff\x1b[31m<LONG>/x\r\n<PRIVATE>/y")
            self.assertEqual((published / "example.stderr.txt").read_bytes(), stderr)
            index_text = (published / "index.json").read_text()
            index = json.loads(index_text)
            self.assertEqual(index["captures"][0]["exit_code"], 7)
            self.assertEqual(index["captures"][0]["argv"], ["<PRIVATE>/tool", "--help"])
            self.assertEqual(index["captures"][0]["cwd"], "<LONG>")
            self.assertNotIn(metadata["stdout"]["sha256"], index_text)
            self.assertNotIn("/fixture/private", index_text)

    def test_reproduction_is_byte_identical_and_leaves_raw_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            scratch = Path(directory)
            raw, mapping = self.fixture(scratch)
            before = {p.name: p.read_bytes() for p in (raw / "fixture").iterdir()}
            for name in ("first", "second"):
                result = self.publish(raw, mapping, scratch / name)
                self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
            first = {p.name: p.read_bytes() for p in (scratch / "first").iterdir()}
            second = {p.name: p.read_bytes() for p in (scratch / "second").iterdir()}
            self.assertEqual(first, second)
            self.assertEqual(before, {p.name: p.read_bytes() for p in (raw / "fixture").iterdir()})

    def test_tampered_raw_capture_is_refused_before_publication(self):
        with tempfile.TemporaryDirectory() as directory:
            scratch = Path(directory)
            raw, mapping = self.fixture(scratch)
            (raw / "fixture/stdout.bin").write_bytes(b"substituted output")
            result = self.publish(raw, mapping, scratch / "published")
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((scratch / "published").exists())

    def test_missing_raw_stream_is_refused_without_a_standin(self):
        with tempfile.TemporaryDirectory() as directory:
            scratch = Path(directory)
            raw, mapping = self.fixture(scratch)
            (raw / "fixture/stdout.bin").unlink()
            result = self.publish(raw, mapping, scratch / "published")
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((scratch / "published").exists())

    def test_duplicate_capture_id_cannot_overwrite_an_observation(self):
        with tempfile.TemporaryDirectory() as directory:
            scratch = Path(directory)
            raw, _ = self.fixture(scratch)
            before = (raw / "fixture/capture.json").read_bytes()
            result = subprocess.run([
                sys.executable, str(RECORDER), "--raw-dir", str(raw), "--id", "fixture",
                "--cwd", str(scratch), "--", sys.executable, "-c", "print('replacement')",
            ], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual((raw / "fixture/capture.json").read_bytes(), before)
            self.assertEqual((raw / "fixture/stdout.bin").read_bytes(), b"/fixture/private/value")


if __name__ == "__main__":
    unittest.main()
