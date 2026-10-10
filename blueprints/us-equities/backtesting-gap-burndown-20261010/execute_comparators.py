"""Exercise the existing comparator against retained accepted and fresh evidence.

The fresh replay is diagnostic: it cannot reset the reviewed-first-run gate.
Every subprocess's observed exit and file identity is recorded by record.py.
"""

import argparse
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[3]
PARITY = ROOT / "blueprints/us-equities/engine-nautilus/spy-parity"
RAW = ROOT / "evidence/artifacts/backtesting-gap-burndown-20261010/us-equities__backtesting-engine/raw"
RECORD = Path(__file__).with_name("record.py")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--fresh", required=True, type=Path)
    args = parser.parse_args()
    for name, receipt, expected, flags in [
        ("accepted-v2-lean-data", PARITY / "receipt-v2.json", 0, ["--lean-data", str(args.data)]),
        ("accepted-v2-no-attribution", PARITY / "receipt-v2.json", 1, []),
        ("accepted-v2-bars", PARITY / "receipt-v2.json", 1,
         ["--bars", str(args.fresh / "converted-rows.private.json")]),
        ("fresh-native-v2", args.fresh / "receipt.json", 1, ["--lean-data", str(args.data)]),
    ]:
        verdict = RAW / (name + ".verdict.json")
        command = [sys.executable, str(RECORD), "--id", name, "--expected-exit", str(expected),
                   "--input", str(receipt), "--input", str(PARITY / "compare.py"),
                   "--output-file", str(verdict), "--", sys.executable, str(PARITY / "compare.py"),
                   "--receipt", str(receipt), "--verdict", str(verdict), *flags]
        result = subprocess.run(command, cwd=ROOT)
        if result.returncode:
            return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
