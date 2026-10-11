"""Scheduler interpreter selection at the shell boundary, without a Python/broker call."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "blueprints/us-equities/adaptive-paper/scheduled_trial.sh"


class ScheduledTrialInterpreter(unittest.TestCase):
    def selected_interpreter(self, override=None):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            capture = root / "argv.txt"
            bootstrap = root / "bootstrap.sh"
            # First timeout is the ingestion boundary. Return before invoking
            # Python, so no SDK, credential file, STOP or broker is accessed.
            bootstrap.write_text(
                'timeout() { printf "%s\\n" "$@" > "$TASK_CAPTURE"; return 53; }\n')
            env = {name: os.environ[name] for name in ("PATH", "HOME", "LANG") if name in os.environ}
            env.update(TRIAL="fixture", ENV_FILE=str(root / "unused.env"),
                       STATE_ROOT=str(root / "state"), OUT_DIR=str(root / "out"),
                       BASH_ENV=str(bootstrap), TASK_CAPTURE=str(capture))
            if override is not None:
                env["PY"] = override
            result = subprocess.run(["bash", str(SCRIPT)], env=env, cwd=ROOT,
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 53, result.stderr)
            args = capture.read_text().splitlines()
            self.assertEqual(args[0], "120")
            self.assertTrue(args[2].endswith("/data/ingest_snapshot.py"))
            self.assertFalse((root / "unused.env").exists())
            self.assertFalse((root / "out" / "gate-result.json").exists())
            return args[1]

    def test_default_uses_calendar_complete_paper_runtime(self):
        expected = Path.home() / "projects/us-equities-runtime/.venv/bin/python"
        self.assertEqual(self.selected_interpreter(), str(expected))

    def test_explicit_py_override_is_retained(self):
        self.assertEqual(self.selected_interpreter("/fixture/approved-python"), "/fixture/approved-python")


if __name__ == "__main__":
    unittest.main()
