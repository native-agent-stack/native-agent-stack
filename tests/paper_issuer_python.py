"""Select the issuer's real interpreter without restricting discovery's Python.

Uses CPython v3.12.3 Lib/unittest/case.py skipTest and the supported subprocess
CLI. No broker, runtime service or credential source is consulted.
"""
from functools import wraps
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SKIP_REASON = "issuer probe needs an explicit CPython 3.12 interpreter (set PAPER_ISSUER_TEST_PYTHON)"


def issuer_python():
    candidates = (os.environ.get("PAPER_ISSUER_TEST_PYTHON"), sys.executable,
                  shutil.which("python3.12"))
    for executable in dict.fromkeys(p for p in candidates if p):
        try:
            result = subprocess.run([executable, "-E", "-s", "-B", "-c",
                "import json,sys;print(json.dumps([sys.implementation.name,*sys.version_info[:2]]))"],
                capture_output=True, text=True, timeout=5)
            if result.returncode == 0 and json.loads(result.stdout) == ["cpython", 3, 12]:
                return executable
        except (OSError, ValueError, subprocess.TimeoutExpired):
            continue
    raise unittest.SkipTest(SKIP_REASON)


def on_issuer_python(method):
    """Run this complete issuer test on a probed 3.12, or state its skip."""
    @wraps(method)
    def run(self):
        executable = issuer_python()
        if sys.implementation.name == "cpython" and sys.version_info[:2] == (3, 12):
            return method(self)
        module = self.__class__.__module__.split(".")[-1]
        case = f"tests.{module}.{self.__class__.__qualname__}.{method.__name__}"
        result = subprocess.run([executable, "-E", "-s", "-B", "-m", "unittest", case],
            cwd=ROOT, capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0,
                         "explicit CPython 3.12 issuer test failed:\n" + result.stdout + result.stderr)
    return run
