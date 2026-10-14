#!/usr/bin/env python3
"""Run the test modules behind trading-runtime skip guards on the pinned runtime, where a skip is a failure.

The validate shards install only .github/requirements-ci.txt, so every test guarded on the pinned trading runtime
(alpaca-py, nautilus_trader, requests and the rest of the lock named in trading_runtime_suite.json) skips there. This
runner is for the job that installs that lock. It checks the installed versions against the lock, runs the listed
modules, and fails on any skip that is not a named exclusion with its exact count, and on any named exclusion whose
count no longer matches. Local runs without the runtime keep their skips: only this runner treats a skip as a failure.
`baseline`, run by the CI interpreter without the runtime, records which of these tests skip there, so `run --baseline`
can count the tests that only the runtime lets run.

Sources: Python 3.12 unittest, "Skipping tests and expected failures", TestLoader.loadTestsFromName and
TestResult.skipped (https://docs.python.org/3.12/library/unittest.html); importlib.metadata.version.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
from pathlib import Path
import re
import sys
import time
import unittest


SCHEMA_VERSION = 1
MANIFEST = Path(__file__).with_name("trading_runtime_suite.json")
PIN = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==([^\s\\;]+)")


def canonical(name):
    """A distribution name as PEP 503 normalizes it."""
    return re.sub(r"[-_.]+", "-", name).lower()


def lock_pins(path):
    """{normalized name: version} for each `name==version` line of a pip-compile style lock."""
    pins = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        match = PIN.match(line)
        if match:
            pins[canonical(match.group(1))] = match.group(2)
    return pins


def preflight(manifest, root, version=importlib.metadata.version):
    """(installed versions, problems): every required distribution must be installed at the version the lock pins."""
    pins = lock_pins(root / manifest["lock"])
    versions, problems = {}, []
    for name in manifest["required_distributions"]:
        pinned = pins.get(canonical(name))
        try:
            installed = version(name)
        except importlib.metadata.PackageNotFoundError:
            installed = None
        versions[name] = installed
        if pinned is None:
            problems.append(f"{name}: not pinned in {manifest['lock']}")
        elif installed != pinned:
            problems.append(f"{name}: installed {installed}, the lock pins {pinned}")
    return versions, problems


def classify(skips, exclusions):
    """(skips that match no single named exclusion, exclusions whose matched count is not their recorded count)."""
    matched = [0] * len(exclusions)
    unexpected = []
    for test_id, reason in skips:
        hits = [index for index, row in enumerate(exclusions)
                if test_id.startswith(row["id_prefix"]) and row["reason_contains"] in reason]
        if len(hits) == 1:
            matched[hits[0]] += 1
        else:
            unexpected.append([test_id, reason])
    drift = [dict(row, matched=count) for row, count in zip(exclusions, matched) if count != row["count"]]
    return unexpected, drift


def execute(modules, root, verbosity, durations):
    """Run tests.<module> for each module with the native runner; a module that does not import is an error case."""
    sys.path.insert(0, str(root))
    loader = unittest.TestLoader()
    suite = unittest.TestSuite(loader.loadTestsFromName("tests." + module) for module in modules)
    return unittest.TextTestRunner(verbosity=verbosity, durations=durations).run(suite)


def baseline(args):
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    result = execute(manifest["modules"], Path.cwd().resolve(), args.verbosity, args.durations)
    skipped = sorted(test.id() for test, _ in result.skipped)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps({"schema_version": SCHEMA_VERSION, "python_version": list(sys.version_info[:3]),
                                       "ran": result.testsRun, "skipped": skipped}, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"baseline": True, "ran": result.testsRun, "skipped": len(skipped)}))
    return 0


def run(args):
    began = time.monotonic()
    root = Path.cwd().resolve()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    report = {"schema_version": SCHEMA_VERSION, "python_version": list(sys.version_info[:3]),
              "lock": manifest["lock"], "modules": manifest["modules"], "success": False, "errors": []}
    versions, problems = preflight(manifest, root)
    report.update(installed_versions=versions, preflight_errors=problems)
    if problems:
        report["errors"].append("the installed runtime does not match the lock: " + "; ".join(problems))
    else:
        result = execute(manifest["modules"], root, args.verbosity, args.durations)
        skips = sorted([test.id(), reason] for test, reason in result.skipped)
        unexpected, drift = classify(skips, manifest["exclusions"])
        report.update(counts={"ran": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
                              "skipped": len(result.skipped)},
                      unexpected_skips=unexpected, exclusion_drift=drift,
                      failed=sorted(test.id() for test, _ in result.failures + result.errors))
        if unexpected:
            report["errors"].append(f"{len(unexpected)} skipped tests match no named exclusion")
        if drift:
            report["errors"].append(f"{len(drift)} named exclusions no longer match their recorded count")
        if args.baseline is not None:
            plain = json.loads(args.baseline.read_text(encoding="utf-8"))
            if plain["ran"] != result.testsRun:
                report["errors"].append(f"the baseline ran {plain['ran']} tests, this run {result.testsRun}")
            here = {test_id for test_id, _ in skips}
            report["guarded_tests_run"] = len(set(plain["skipped"]) - here)
            report["baseline_skipped"] = len(plain["skipped"])
        report["success"] = result.wasSuccessful() and not report["errors"]
    report["elapsed_seconds"] = round(time.monotonic() - began, 3)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"success": report["success"], "counts": report.get("counts"), "modules": len(manifest["modules"]),
                      "skipped_by_the_baseline": report.get("baseline_skipped"),
                      "guarded_tests_run": report.get("guarded_tests_run"),
                      "named_exclusions": {row["id_prefix"]: row["count"] for row in manifest["exclusions"]},
                      "errors": report["errors"]}, sort_keys=True))
    for test_id, reason in report.get("unexpected_skips", []):
        print(f"unexpected skip: {test_id}: {reason}")
    for row in report.get("exclusion_drift", []):
        print(f"named exclusion drift: {row['id_prefix']} '{row['reason_contains']}' matched {row['matched']},"
              f" recorded {row['count']}")
    return 0 if report["success"] else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("run", "baseline"):
        command = sub.add_parser(name)
        command.add_argument("--manifest", type=Path, default=MANIFEST)
        command.add_argument("--report", type=Path, required=True)
        command.add_argument("--durations", type=int, default=50)
        command.add_argument("-v", "--verbose", dest="verbosity", action="store_const", const=2, default=1)
        if name == "run":
            command.add_argument("--baseline", type=Path,
                                 help="the baseline report of the same modules, run without the runtime")
    args = parser.parse_args(argv)
    return run(args) if args.command == "run" else baseline(args)


if __name__ == "__main__":
    sys.exit(main())
