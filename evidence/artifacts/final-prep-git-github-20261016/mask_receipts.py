"""Deterministic masking of retained native captures; never invoke a component.

The input is the private recorder's JSON command array. Stream digests in that
input authenticate exact UTF-8 native bytes, including CR/LF. Only hashes of
published derivative bytes leave this function. Input capture paths and input
digests are not published. Commands and output use marked placeholders.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

RAW_CAPTURE_NAME = "git-github-native-command-capture-20261016"


def stream_digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def mask_capture(raw: list[dict]) -> dict:
    """Check original stream integrity, then apply the two declared literal rules."""
    if not isinstance(raw, list) or not raw:
        raise ValueError("Native command array is required")
    created = next(row for row in raw if row["id"] == "worktrunk-list-created")
    fixture = json.loads(created["stdout"])["items"][0]["head"]["sha"]
    if not isinstance(fixture, str) or not re.fullmatch(r"[0-9a-f]{40}", fixture):
        raise ValueError("Native fixture identity is invalid")
    scratch_root = str(Path(created["cwd"]).parent)
    if scratch_root == "/" or not scratch_root.startswith("/var/tmp/"):
        raise ValueError("Expected an isolated task scratch")

    def mask(text: str) -> str:
        return (text.replace(scratch_root, "<SCRATCH>")
                .replace(fixture, "<FIXTURE_COMMIT>")
                .replace(fixture[:7], "<FIXTURE_COMMIT>"))

    commands = []
    for row in raw:
        for stream in ("stdout", "stderr"):
            if stream_digest(row[stream]) != row[stream + "_sha256"]:
                raise ValueError("Native stream digest mismatch")
        command = {
            "id": row["id"],
            "command": mask(row["command"]),
            "cwd": mask(row["cwd"]),
            "started_at": row["started_at"],
            "completed_at": row["completed_at"],
            "exit_code": row["exit_code"],
            "expected_exit_code": row["expected_exit_code"],
            "stdout": mask(row["stdout"]),
            "stderr": mask(row["stderr"]),
        }
        for stream in ("stdout", "stderr"):
            command[stream + "_sha256"] = stream_digest(command[stream])
        command["hash_scope"] = "Exact PUBLISHED UTF-8 stream bytes after the declared literal masking rules."
        commands.append(command)
    return {
        "schema_version": 1,
        "record_type": "masked_derivative_of_native_capture",
        "raw_capture_name": RAW_CAPTURE_NAME,
        "raw_capture_custody": "Private; name only, no raw-capture digest or private locator is published.",
        "masking_script": "mask_receipts.py",
        "masking_test": "test_mask_receipts.py",
        "masking_rules": [
            "Replace the scratch root derived from the native worktrunk-list-created cwd with <SCRATCH> in command, cwd, stdout and stderr.",
            "Replace the full and seven-character disposable Git commit identity from the native worktrunk-list-created output with <FIXTURE_COMMIT> in those fields.",
            "Preserve native command ids, timestamps, exits and expected-exit metadata; recompute only hashes of PUBLISHED streams. Never copy an input digest as provenance metadata.",
        ],
        "fixture_scope": "Real native commands executed against disposable synthetic Git inputs and the vendor's source samples. Test data is not a production workload or a simulation of tool output.",
        "commands": commands,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = mask_capture(json.loads(args.raw.read_text(encoding="utf-8")))
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Masked derivative written; no private path or raw digest reported.")


if __name__ == "__main__":
    main()
