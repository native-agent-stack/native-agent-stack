"""Deterministic public derivative from retained native originals.

PyPI source JSON includes README byte copies: retain those in private horizon
vendor custody, and publish only the allowlisted release/wheel identity fields.
This projection is labelled source evidence, never an E2E output stand-in.
Exact native commands, observed exit codes and original metadata remain private.
"""

import argparse
import hashlib
import json
from pathlib import Path

from mask_capture import mask_bytes


WINNERS = {"alpaca-py": "0.44.0", "edgartools": "5.61.1", "exchange-calendars": "4.13.2"}
COMMITS = {"alpaca-py": "cc4cb3b7ba50ae250e621983c2779047fb16bb28",
    "edgartools": "7338aa335f6442c52dfa0695422cf1cd27e946e0",
    "exchange-calendars": "dbe38b1f6887434bbdd1a7d2df6ff8f1742a048a"}
SUFFIXES = {"alpaca": "alpaca-py", "edgar": "edgartools", "calendar": "exchange-calendars"}


def json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def release_projection(raw):
    source = json.loads(raw)
    info = source["info"]
    wheels = [item for item in source["urls"]
              if item["filename"].endswith("-py3-none-any.whl")]
    if len(wheels) != 1:
        raise ValueError("expected the one pure-Python release wheel")
    return json_bytes({
        "schema": "pypi-release-identity-projection/1",
        "projection": "Allowlisted factual identity fields; README/description/contacts omitted, full native source in horizon vendor custody.",
        "source_url": "https://pypi.org/pypi/" + info["name"] + "/" + info["version"] + "/json",
        "info": {"name": info["name"], "version": info["version"]},
        "urls": [{"filename": item["filename"], "url": item["url"],
                  "digests": {"sha256": item["digests"]["sha256"]},
                  "packagetype": item["packagetype"]} for item in wheels],
    })


def corrected_inputs(family, label, original):
    if family == "small-fold-v1":
        return original
    if label.startswith("pypi-"):
        package = SUFFIXES[label[5:]]
    elif label.startswith("calendar-") or label == "network-guard-calendar":
        package = "exchange-calendars"
    elif label.startswith("edgar-") or label == "upstream-offline-tests":
        package = "edgartools"
    elif label.startswith("alpaca-"):
        package = "alpaca-py"
    elif label.startswith("arctic-") or label == "create-arctic-venv":
        return {"arcticdb": "6.26.0", "source_commit": "e620d8572a1e62c9ec07df8cbc8f5c432cd84325"}
    elif "masking" in label or "recorder-tests" in label:
        return {"component": "capture_recorder_and_masker", "scope": "synthetic regression fixtures"}
    elif "closure-audit" in label:
        return {"component": "resolved_closure_source_audit", "runtime_lock": "uv.lock", "scope": "not component E2E"}
    elif label == "uv-pip-install-help":
        return {"component": "uv", "version": "0.12.22", "scope": "installed-client help"}
    elif label.startswith("pytest-override-help"):
        return {"component": "pytest", "scope": "installed-client override help"}
    elif label.startswith("network-guard"):
        return {"component": "audit_hook", "scope": "negative control, not a sandbox"}
    else:
        return {"winner_versions": WINNERS, "scope": "multi-package environment or identity audit"}
    return {package: WINNERS[package], "source_commit": COMMITS[package]}


def public_pair(raw_output, raw_receipt, rules, family, label):
    record = json.loads(raw_receipt)
    projected = family == "fold-v1" and label.startswith("pypi-")
    # The fail-first test deliberately prints synthetic private-root prefixes.
    # Its public fixture identity is known from test_mask_capture.py, so include
    # it in the declared publication map too; do not disguise it as a host root.
    if family == "small-fold-v1" and label == "masking-before":
        rules = [*rules, {"source": "/var/tmp/fixture-private-workspace-20261016",
                          "placeholder": "<synthetic-fixture-root>"}]
    output = release_projection(raw_output) if projected else mask_bytes(raw_output, rules)
    inputs = corrected_inputs(family, label, record.get("declared_inputs", {}))
    if inputs != record.get("declared_inputs"):
        record["declared_inputs"] = inputs
        record["metadata_correction"] = "Source-specific declaration corrected by publish_capture.py; original recorder metadata remains private and unchanged. Command/rc/times are unaltered."
    record["output_sha256"] = hashlib.sha256(output).hexdigest()
    record["publication_transform"] = "publish_capture.py:public_pair; retained originals and maps reproduce both derivatives"
    record["capture_class"] = "projected_native_source_capture" if projected else "masked_native_capture"
    if projected:
        record["projection_scope"] = "Allowlisted PyPI release/wheel fields only; original source capture moved to horizon vendor custody. Not E2E/invoke evidence."
        record["masking_scope"] = "Source output is an explicit field projection; metadata is byte-masked after documented correction. Full source retained in vendor custody."
        record["vendor_custody_name"] = "market-data-pypi-20261016/" + label + "/release.raw.json"
    return output, mask_bytes(json_bytes(record), rules)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-root", required=True, type=Path)
    parser.add_argument("--published-root", required=True, type=Path)
    parser.add_argument("--family", required=True)
    parser.add_argument("--label", required=True)
    args = parser.parse_args()
    capture = args.private_root / args.label
    output, receipt = public_pair((capture / "stdout.raw").read_bytes(),
        (capture / "receipt.raw.json").read_bytes(),
        json.loads((capture / "mask-map.json").read_bytes()), args.family, args.label)
    args.published_root.mkdir(parents=True, exist_ok=True)
    # Explicitly authorised re-publication from immutable originals; no command
    # is re-executed and no original file is overwritten.
    (args.published_root / (args.label + ".log")).write_bytes(output)
    (args.published_root / (args.label + ".json")).write_bytes(receipt)


if __name__ == "__main__":
    main()
