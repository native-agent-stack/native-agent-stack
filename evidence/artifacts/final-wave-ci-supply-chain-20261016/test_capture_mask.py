"""Synthetic custody tests; these are NOT candidate E2E or invoke evidence."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent
def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / (name + ".py"))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result

C = module("capture")
M = module("mask")


class CaptureMaskTests(unittest.TestCase):
    def test_native_binary_streams_and_failure_status_are_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            code = "import os; os.write(1, b'out\\r\\n\\xff'); os.write(2, b'err\\x00'); raise SystemExit(7)"
            result = C.record(temp, "probe", [sys.executable, "-c", code], temp, {"PATH": "/usr/bin:/bin"})
            p = Path(temp) / "probe"
            self.assertEqual(result["exit_code"], 7)
            self.assertEqual((p / "stdout.bin").read_bytes(), b"out\r\n\xff")
            self.assertEqual((p / "stderr.bin").read_bytes(), b"err\x00")
            self.assertEqual(result["streams"]["stdout"]["raw_sha256_private"],
                             hashlib.sha256(b"out\r\n\xff").hexdigest())

    def test_empty_stream_stays_empty(self):
        self.assertEqual(M.mask_bytes(b"", [(b"/private", b"<PRIVATE>")]), b"")

    def test_longest_prefix_preserves_nonprivate_bytes(self):
        pairs = [(b"/private", b"<PRIVATE>"), (b"/private/run", b"<SCRATCH>")]
        self.assertEqual(M.mask_bytes(b"/private/run/a\r\n/private/b\xff", pairs),
                         b"<SCRATCH>/a\r\n<PRIVATE>/b\xff")

    def test_private_digest_is_masked_and_public_commit_retained(self):
        commit = b"a" * 40
        self.assertEqual(M.mask_bytes(commit + b" " + b"b" * 64, [], [commit]),
                         commit + b" <MASKED_DIGEST>")

    def test_masking_is_idempotent(self):
        first = M.mask_bytes(b"/private/a " + b"c" * 64, [(b"/private", b"<PRIVATE>")])
        self.assertEqual(first, M.mask_bytes(first, [(b"/private", b"<PRIVATE>")]))

    def test_sbom_digest_prefixes_are_masked(self):
        self.assertEqual(M.mask_bytes(b"id=" + b"d" * 16 + b" 1.30.1", []),
                         b"id=<MASKED_DIGEST> 1.30.1")

    def test_uuid_shaped_public_asset_names_follow_publication_policy(self):
        token = b"12345678" + b"-1234-5678-9012-" + b"123456789012"
        self.assertEqual(M.mask_bytes(b"asset/" + token + b".png", []),
                         b"asset/<MASKED_UUID>.png")

    def test_derivative_reproduces_and_has_only_published_hashes(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp)
            C.record(p / "raw", "probe", [sys.executable, "-c", "print('/private/a')"], temp, {})
            pairs = [(b"/private", b"<PRIVATE>"), (temp.encode(), b"<SCRATCH>")]
            M.publish(p / "raw", p / "a", pairs)
            M.publish(p / "raw", p / "b", pairs)
            for f in (p / "a").rglob("*"):
                if f.is_file():
                    self.assertEqual(f.read_bytes(), (p / "b" / f.relative_to(p / "a")).read_bytes())
            data = json.loads((p / "a/probe/receipt.json").read_text())
            self.assertNotIn("raw_sha256_private", json.dumps(data))
            stdout = (p / "a/probe/stdout.txt").read_bytes()
            self.assertEqual(data["streams"]["stdout"]["published_sha256"], hashlib.sha256(stdout).hexdigest())

    def test_tampered_raw_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp)
            C.record(p / "raw", "probe", [sys.executable, "-c", "print('real')"], temp, {})
            (p / "raw/probe/stdout.bin").write_bytes(b"replacement")
            with self.assertRaisesRegex(ValueError, "integrity mismatch"):
                M.publish(p / "raw", p / "out", [])

    def test_existing_capture_and_output_are_never_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp)
            C.record(p, "probe", [sys.executable, "-c", "pass"], temp, {})
            with self.assertRaises(FileExistsError):
                C.record(p, "probe", [sys.executable, "-c", "pass"], temp, {})


if __name__ == "__main__":
    unittest.main()
