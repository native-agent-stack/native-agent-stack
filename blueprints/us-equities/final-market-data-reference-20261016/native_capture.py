"""Retain native subprocess bytes privately and emit reproducible masked copies.

Extends this preparation's original recorder by retaining bytes BEFORE masking.
CPython 3.12 subprocess.run: https://docs.python.org/3.12/library/subprocess.html#subprocess.run
No command output is interpreted as a pass or replaced with a summary.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess

from mask_capture import mask_bytes


def json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def exclusive(path, value):
    with path.open("xb") as output:
        output.write(value)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", required=True, type=Path)
    parser.add_argument("--private-root", required=True, type=Path)
    parser.add_argument("--published-root", required=True, type=Path)
    args = parser.parse_args()
    spec = json.loads(args.spec.read_text())
    label = spec["label"]
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", label):
        parser.error("invalid label")
    if not isinstance(spec["argv"], list) or not all(
        isinstance(arg, str) for arg in spec["argv"]
    ):
        parser.error("argv must be a list of strings")
    rules = spec["masking_rules"]
    # Validate the mapping before running anything.
    mask_bytes(b"", rules)
    private = args.private_root / label
    private.mkdir(mode=0o700, parents=True, exist_ok=False)
    args.published_root.mkdir(parents=True, exist_ok=True)
    published_log = args.published_root / (label + ".log")
    published_receipt = args.published_root / (label + ".json")
    if published_log.exists() or published_receipt.exists():
        parser.error("published outputs already exist; choose a new capture label")
    exclusive(private / "spec.json", json_bytes(spec))
    started = datetime.now(timezone.utc).isoformat()
    # Stream straight into a private file. No text decoding, universal-newline
    # translation, truncation or in-memory-only original capture.
    with (private / "stdout.raw").open("xb") as raw_output:
        result = subprocess.run(
            spec["argv"], cwd=spec["cwd"], env=spec["environment"],
            stdout=raw_output, stderr=subprocess.STDOUT, check=False,
        )
    finished = datetime.now(timezone.utc).isoformat()
    raw = (private / "stdout.raw").read_bytes()
    masked = mask_bytes(raw, rules)
    exclusive(private / "mask-map.json", json_bytes(rules))
    exclusive(private / "integrity.private.json", json_bytes({
        "raw_sha256": hashlib.sha256(raw).hexdigest(),
        "raw_bytes": len(raw), "exit_code": result.returncode,
    }))
    exclusive(published_log, masked)
    record = {
        "schema": "masked-native-command/1",
        "capture_class": "masked_native_capture",
        "command": spec["argv"], "cwd": spec["cwd"],
        "declared_inputs": spec.get("declared_inputs", {}),
        "started_utc": started, "finished_utc": finished,
        "exit_code": result.returncode,
        "stream": "stdout_and_stderr_merged_as_bytes",
        "private_capture_name": label,
        "private_original_name": "stdout.raw",
        "private_receipt_original_name": "receipt.raw.json",
        "private_mapping_name": "mask-map.json",
        "output": label + ".log",
        "output_sha256": hashlib.sha256(masked).hexdigest(),
        "masking_rule": "mask_capture.py:mask_bytes",
        "masking_scope": "Declared literal substitution only; all other bytes retained",
        "claim_scope": spec["claim_scope"],
    }
    receipt_raw = json_bytes(record)
    exclusive(private / "receipt.raw.json", receipt_raw)
    exclusive(published_receipt, mask_bytes(receipt_raw, rules))
    # This terminal line is recorder control output, not command evidence.
    print(json.dumps({"capture": label, "exit_code": result.returncode}))
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
