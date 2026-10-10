#!/usr/bin/env python3
"""Run the single retry-guard mutation with an explicit, importable test package.

The retained shell runner's temporary tests directory has no __init__.py. In
the new prefix an installed tests package shadows it, giving an import error.
This probe refuses setup/error kills and requires the native retry assertion.
"""
import argparse
import hashlib
from pathlib import Path
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[3]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, required=True)
    args = parser.parse_args()
    source = ROOT / "blueprints/us-equities/alpaca-historical/collect.py"
    before = source.read_text()
    guard = "            client._retry = 0\n"
    if before.count(guard) != 1:
        raise ValueError("retry_guard_must_be_unique")
    after = before.replace(guard, "")
    with tempfile.TemporaryDirectory(prefix="market-retry-probe-") as tmp:
        root = Path(tmp)
        (root / "tests").mkdir()
        (root / "tests/__init__.py").write_text("")
        (root / "tests/test_alpaca_historical.py").write_bytes((ROOT / "tests/test_alpaca_historical.py").read_bytes())
        (root / "scripts").mkdir()
        (root / "scripts/path_safety.py").write_bytes((ROOT / "scripts/path_safety.py").read_bytes())
        directory = root / "blueprints/us-equities/alpaca-historical"
        directory.mkdir(parents=True)
        (directory / "collect.py").write_text(after)
        (directory / "plan.json").write_bytes((source.parent / "plan.json").read_bytes())
        done = subprocess.run([str(args.python), "-m", "unittest",
                               "tests.test_alpaca_historical.AlpacaHistoricalTests.test_native_get_retains_exact_bytes_and_disables_redirect_retry"],
                              cwd=root, capture_output=True, text=True, timeout=35)
        output = done.stdout + done.stderr
        print(output.replace(str(Path.home()), "~").replace(str(root), "<mutation-worktree>"))
        print("mutant_exit=" + str(done.returncode))
        print("source_sha256=" + hashlib.sha256(before.encode()).hexdigest())
        print("mutant_sha256=" + hashlib.sha256(after.encode()).hexdigest())
        caught = (done.returncode == 1 and "native retry or redirect added an HTTP attempt" in output
                  and "FAILED (failures=1)" in output and "ERROR:" not in output
                  and "errors=" not in output and "Ran 1 test" in output)
        print("assertion_kill_without_setup_errors=" + str(caught).lower())
        return 0 if caught else 1


if __name__ == "__main__":
    raise SystemExit(main())
