"""Generate synthetic test data with native resolve and mocked exact tag output.

This producer performs no Git/network command and captures no real candidate.
Run with the reviewed PIN-RULES complete_run_pins module on the import path.
The retained JSON is fixture data, not authenticated external evidence.
"""

import json
from pathlib import Path
import subprocess
from unittest.mock import Mock

from scripts import complete_run_pins
from tests.test_final_stack import COMMIT_A


def generate():
    """Use the supported native full-tag query to produce a synthetic fixture."""
    run = {"id": "widget", "repository": "github.com/example/widget",
           "source": "manifests/stack.json#/components/0", "pin": "1.0.0",
           "pin_parsed": {"version": "1.0.0", "commit": None}}
    output = subprocess.CompletedProcess([], 0,
        stdout=COMMIT_A + "\trefs/tags/v1.0.0\n", stderr="")
    return {**complete_run_pins.resolve(run, Mock(return_value=output)),
            "evidence_class": "synthetic",
            "fixture_note": "Synthetic test fixture; exact tag output is mocked, no network observation."}


if __name__ == "__main__":
    target = Path(__file__).with_name("widget-source-proof.json")
    target.write_text(json.dumps(generate(), indent=2) + "\n")
    print("Generated synthetic widget fixture through native complete_run_pins.resolve")
