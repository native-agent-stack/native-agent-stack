"""Run the existing comparator and verify each designed refusal's exact checks.

The fresh replay is diagnostic: it cannot reset the reviewed-first-run gate.
Reference: spy-parity/compare.py at native-agent-stack 8bffa2c41692ef483e91b68e3b15aeb331423d2c.
This execution driver grants no gap credit. Use scripts/host_receipts.py for
command recording and the shared gap-closeouts loader for dispositions.
"""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[3]
PARITY = ROOT / "blueprints/us-equities/engine-nautilus/spy-parity"
RAW = ROOT / "evidence/artifacts/backtesting-gap-burndown-20261010/us-equities__backtesting-engine/raw"
EXPECTED_CHECKS = {
    "accepted-v2-lean-data": set(),
    "accepted-v2-no-attribution": {("precondition_hashes", "inputs_at_comparison", "SKIPPED"),
        ("entry_oco", "trigger_and_gap_evidence", "SKIPPED"),
        ("exit_oco", "trigger_and_gap_evidence", "SKIPPED"),
        ("attribution_evidence", "converted_bars", "SKIPPED")},
    "accepted-v2-bars": {("precondition_hashes", "inputs_at_comparison", "SKIPPED")},
    "fresh-native-v2": {("precondition_review", "no_prior_replay_ran_the_reviewed_harness", "FAIL")},
}


def validate_verdict(name, path):
    """Missing, truncated or unexpected evidence cannot be an expected refusal."""
    verdict = json.loads(path.read_text())
    checks = verdict["checks"]
    keys = [check["key"] for check in checks]
    if not checks or len(keys) != len(set(keys)):
        raise ValueError("missing_or_duplicate_comparator_checks")
    if any(check["status"] not in {"PASS", "FAIL", "SKIPPED"} for check in checks):
        raise ValueError("unknown_comparator_check_status")
    failures = {(check["id"], check["field"], check["status"]) for check in checks if check["status"] != "PASS"}
    if failures != EXPECTED_CHECKS[name]:
        raise ValueError("unexpected_comparator_check_set:" + name)
    if name == "accepted-v2-lean-data":
        if (verdict["verdict"] != "PASS" or not verdict["complete"] or
                verdict["execution_checks"] != {"pass": 106, "fail": 0, "skipped": 0}):
            raise ValueError("accepted_comparator_incomplete")
    elif verdict["verdict"] != "FAIL":
        raise ValueError("designed_refusal_must_fail")
    if name == "fresh-native-v2" and verdict["execution_checks"] != {"pass": 106, "fail": 0, "skipped": 0}:
        raise ValueError("fresh_comparator_execution_incomplete")
    return verdict


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--fresh", required=True, type=Path)
    args = parser.parse_args()
    # Deliberate allowlist: never inspect arbitrary environment values.
    environment = {k: os.environ[k] for k in ("PATH", "LANG", "LC_ALL") if k in os.environ}
    environment.update({"OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1"})
    print(json.dumps({"execution_environment": {k: v.replace(str(Path.home()), "~")
                                               for k, v in environment.items()}}), flush=True)
    for name, receipt, expected, flags in [
        ("accepted-v2-lean-data", PARITY / "receipt-v2.json", 0, ["--lean-data", str(args.data)]),
        ("accepted-v2-no-attribution", PARITY / "receipt-v2.json", 1, []),
        ("accepted-v2-bars", PARITY / "receipt-v2.json", 1,
         ["--bars", str(args.fresh / "converted-rows.private.json")]),
        ("fresh-native-v2", args.fresh / "receipt.json", 1, ["--lean-data", str(args.data)]),
    ]:
        verdict = RAW / (name + ".verdict.json")
        if verdict.exists():
            print("refusing stale verdict:" + name, file=sys.stderr)
            return 1
        command = [sys.executable, str(PARITY / "compare.py"),
                   "--receipt", str(receipt), "--verdict", str(verdict), *flags]
        result = subprocess.run(command, cwd=ROOT, env=environment)
        if result.returncode != expected:
            return 1
        try:
            validate_verdict(name, verdict)
        except (OSError, ValueError, KeyError, TypeError) as error:
            print("invalid comparator evidence:" + name + ":" + type(error).__name__, file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
