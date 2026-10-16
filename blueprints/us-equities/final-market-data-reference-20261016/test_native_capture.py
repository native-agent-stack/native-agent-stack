"""Recorder custody tests with explicitly synthetic child-process bytes."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class NativeCaptureTests(unittest.TestCase):
    def test_failed_child_retains_raw_and_exact_command_before_masking(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            private = root / "private"
            public = root / "public"
            private_cwd = root / 'caf\u00e9"back\\slash'
            private_cwd.mkdir()
            command = [sys.executable, "-I", "-c",
                "import sys;sys.stdout.buffer.write(b'\\xff original \\r\\n');sys.exit(7)"]
            spec = {"label": "failed-child", "argv": command,
                "cwd": str(private_cwd), "environment": {},
                "masking_rules": [
                    {"source": "original", "placeholder": "<private>"},
                    {"source": str(private_cwd), "placeholder": "<scratch>"}],
                "claim_scope": "SYNTHETIC recorder regression fixture only"}
            specfile = root / "spec.json"
            specfile.write_text(json.dumps(spec))
            result = subprocess.run([sys.executable, str(Path(__file__).with_name("native_capture.py")),
                "--spec", str(specfile), "--private-root", str(private),
                "--published-root", str(public)], capture_output=True)
            self.assertEqual(result.returncode, 7)
            capture = private / "failed-child"
            self.assertEqual((capture / "stdout.raw").read_bytes(), b"\xff original \r\n")
            self.assertEqual((public / "failed-child.log").read_bytes(), b"\xff <private> \r\n")
            metadata = json.loads((capture / "receipt.raw.json").read_bytes())
            self.assertEqual(metadata["command"], command)
            self.assertEqual(metadata["exit_code"], 7)
            self.assertEqual(metadata["cwd"], str(private_cwd))
            published_metadata = json.loads((public / "failed-child.json").read_bytes())
            self.assertEqual(published_metadata["cwd"], "<scratch>")
            self.assertEqual(json.loads((capture / "integrity.private.json").read_bytes())["raw_bytes"], 13)
            self.assertNotIn(b"raw_sha256", (public / "failed-child.json").read_bytes())

    def test_existing_publication_is_not_overwritten_or_command_run(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            public = root / "public"
            public.mkdir()
            (public / "existing.log").write_bytes(b"existing")
            marker = root / "must-not-exist"
            spec = {"label": "existing", "argv": [sys.executable, "-c",
                "from pathlib import Path;Path(" + repr(str(marker)) + ").touch()"],
                "cwd": str(root), "environment": {}, "masking_rules": [],
                "claim_scope": "SYNTHETIC recorder regression fixture only"}
            specfile = root / "spec.json"
            specfile.write_text(json.dumps(spec))
            result = subprocess.run([sys.executable, str(Path(__file__).with_name("native_capture.py")),
                "--spec", str(specfile), "--private-root", str(root / "private"),
                "--published-root", str(public)], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(marker.exists())
            self.assertEqual((public / "existing.log").read_bytes(), b"existing")


if __name__ == "__main__":
    unittest.main()
