#!/usr/bin/env python3
"""Project only named lane-owned experiment artifacts into a sanitized run bundle.

Does not traverse environment/account stores, launch experiments, judge gaps,
or update a verdict. The native receipt and exact output hashes remain distinct
from this projection's hash; incomplete runs cannot become passes.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from run import HERE, ROOT, digest, write_new


def sanitize(value, replacements):
    if isinstance(value, str):
        for old, new in replacements:
            value = value.replace(old, new)
        return value
    if isinstance(value, list):
        return [sanitize(x, replacements) for x in value]
    if isinstance(value, dict):
        return {sanitize(k, replacements): sanitize(v, replacements) for k, v in value.items()}
    return value


def project(base, runs):
    replacements = [(str(base), "$RESEARCH_STATE"), (str(ROOT), "$STACK_REPO"),
                    (str(Path.home() / "code/upstream"), "$UPSTREAM_ROOT"), (str(Path.home()), "~")]
    result = {}
    for name in runs:
        if Path(name).name != name:
            raise ValueError("name one owned run, never a traversal path")
        directory = base / "runs" / name
        if not directory.is_dir():
            raise ValueError("missing named native run")
        files = [directory / "freeze.json", directory / "receipt.json", directory / "targets.json"]
        files += sorted(directory.glob("*.command.private.json"))
        files += sorted(directory.glob("*.stdout.txt")) + sorted(directory.glob("*.stderr.txt"))
        files += sorted(directory.glob("*/audit.jsonl"))
        files += sorted(directory.glob("*/analysis.json"))
        files += sorted(directory.glob("*/data-monitor-report-*.json"))
        # Native outputs bind local callbacks to the engine's own orders/state.
        files += sorted(directory.glob("*/FrozenResearchTargets-order-events.json"))
        files += sorted(directory.glob("*/FrozenResearchTargets-summary.json"))
        files += sorted(directory.glob("*/FrozenResearchTargets.json"))
        item = {"files": {}}
        for path in files:
            if not path.is_file():
                continue
            if path.suffix == ".json":
                value = json.loads(path.read_text())
                if path.name == "FrozenResearchTargets.json":
                    value = {k: value[k] for k in ["orders", "statistics", "state", "algorithmConfiguration"]}
            elif path.suffix == ".jsonl":
                value = [json.loads(line) for line in path.read_text().splitlines()]
            else:
                value = path.read_text()
            item["files"][str(path.relative_to(directory))] = {
                "original_sha256": digest(path), "projection": sanitize(value, replacements)}
            if path.name == "FrozenResearchTargets.json":
                item["files"][str(path.relative_to(directory))]["projection_fields"] = list(value)
        receipt = directory / "receipt.json"
        item["status"] = json.loads(receipt.read_text())["status"] if receipt.is_file() else "incomplete"
        if not receipt.is_file():
            item["incomplete_reason"] = "Batch deadline interrupted this attempt; no native completion receipt exists."
        result[name] = item
    support = {}
    for name in ["lean-build.stdout.log", "lean-build.stderr.log"]:
        path = base / name
        if path.is_file():
            support[name] = {"original_sha256": digest(path),
                             "projection": sanitize(path.read_text(), replacements)}
    return {"schema_version": 1, "layer": "us-equities/research-factors-ml", "runs": result,
            "build_logs": support,
            "scope": "Sanitized projection of actual native executions and explicitly synthetic controls. No independent review, canonical gap settlement, predictive superiority or account acceptance is implied."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--runs", nargs="+", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    write_new(args.out, project(args.state.resolve(), args.runs))
    print(json.dumps({"runs": len(args.runs), "bundle_sha256": digest(args.out)}))


if __name__ == "__main__":
    main()
