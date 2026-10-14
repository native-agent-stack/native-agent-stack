#!/usr/bin/env python3
"""Run all integration modules with native unittest and isolated paper defaults.

CPython v3.12.3@f6650f9ad73359051f3e558c2431a109bc016664,
Lib/unittest/loader.py:229-340 and runner.py:193-258: public discovery/runner APIs.
CI supplies the locked runtime and mandatory network/filesystem isolation.
"""
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    # Discover before patching: engine modules bind DEFAULT_STOP on import.
    suite = unittest.TestLoader().discover(str(ROOT / "tests/integration"), pattern="*.py")
    from tests.adaptive_paper_hermetic import patch_default_stop, restore_default_stop
    token = patch_default_stop()
    try:
        result = unittest.TextTestRunner(verbosity=2, durations=20).run(suite)
    finally:
        restore_default_stop(token)
    # CPython v3.12.3 case.py:609-612 starts cases before checking skip;
    # result.py:59,147,172 counts skips separately and accepts them as successful.
    # Every integration case is mandatory: an empty or partially skipped suite fails.
    if result.skipped:
        print("integration refused: mandatory cases or fixtures were skipped", file=sys.stderr)
    return 0 if result.wasSuccessful() and result.testsRun > 0 and not result.skipped else 1


if __name__ == "__main__":
    raise SystemExit(main())
