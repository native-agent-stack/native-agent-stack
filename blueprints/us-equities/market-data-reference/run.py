#!/usr/bin/env python3
"""Retain bounded supported-client runs for the October 10 market-data gap plan.

No credential is read or used. Vendor sources are public; SDK transport tests
use their existing synthetic adapters. Provider-news acquisition is a separate,
bounded native attempt and does not stand in for an entitled historical feed.
"""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys
import time
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[3]
OUTPUT = ROOT / "evidence/artifacts/market-data-reference-20261010"
PREVIOUS = "evidence/artifacts/gap-wave2-20260923/us-equities__market-data-reference"
HELPERS = "blueprints/gap-wave2-20260923/us-equities__market-data-reference"


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def mask(text):
    return text.replace(str(Path.home()), "~").replace(str(ROOT), "<worktree>")


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")


def artifact(path):
    return {"path": path.relative_to(ROOT).as_posix(), "sha256": digest(path.read_bytes())}


def command(label, args, timeout=45):
    started = datetime.now(timezone.utc).isoformat()
    before = time.monotonic()
    timed_out = False
    try:
        done = subprocess.run([str(a) for a in args], cwd=ROOT, capture_output=True, timeout=timeout)
        stdout, stderr, code = done.stdout, done.stderr, done.returncode
    except subprocess.TimeoutExpired as error:
        stdout, stderr, code, timed_out = error.stdout or b"", error.stderr or b"", 124, True
    paths = []
    for suffix, raw in [("stdout.txt", stdout), ("stderr.txt", stderr)]:
        path = OUTPUT / "raw" / f"{label}.{suffix}"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(mask(raw.decode("utf-8", errors="replace")), encoding="utf-8")
        paths.append(artifact(path))
    return {"label": label, "argv": [mask(str(a)) for a in args], "started_at_utc": started,
            "exit_code": code, "timed_out": timed_out,
            "duration_s": round(time.monotonic() - before, 4), "outputs": paths,
            "publication_transform": "host/worktree paths replaced with ~/ <worktree>; output hashes bind published bytes"}


def public_json(url):
    with urlopen(Request(url, headers={"User-Agent": "native-agent-stack-source-review"}), timeout=20) as response:
        raw = response.read(4_000_001)
        if len(raw) > 4_000_000:
            raise ValueError("public_source_too_large")
        return json.loads(raw), digest(raw)


def sources():
    observations = []
    for repo, branch in [("SEC-API-io/sec-api-python", "master"), ("Rossod4/quantlab", "main")]:
        api = f"https://api.github.com/repos/{repo}"
        metadata, metadata_sha = public_json(api)
        commit, commit_sha = public_json(api + "/commits/" + branch)
        releases, releases_sha = public_json(api + "/releases?per_page=5")
        pin = commit["sha"]
        readme, readme_sha = public_json(api + "/contents/README.md?ref=" + pin)
        raw_readme = base64.b64decode(readme["content"])
        carrier = OUTPUT / "sources" / (repo.split("/")[-1] + "-README.md.base64")
        carrier.parent.mkdir(parents=True, exist_ok=True)
        carrier.write_text(base64.b64encode(raw_readme).decode() + "\n", encoding="ascii")
        tree, tree_sha = public_json(api + "/git/trees/" + pin + "?recursive=1")
        license_files = [row["path"] for row in tree["tree"] if
                         row["path"].rsplit("/", 1)[-1].lower().split(".", 1)[0] in {"license", "copying", "notice"}]
        record = {"repository": "https://github.com/" + repo, "pin": pin,
                  "observed_at_utc": datetime.now(timezone.utc).isoformat(),
                  "default_branch": metadata["default_branch"], "archived": metadata["archived"],
                  "license": metadata["license"], "pushed_at": metadata["pushed_at"],
                  "releases": [{k: row[k] for k in ["tag_name", "published_at", "html_url"]} for row in releases],
                  "license_files": license_files, "tree_truncated": tree["truncated"],
                  "readme": {**artifact(carrier), "decoded_sha256": digest(raw_readme),
                             "source_url": "https://github.com/" + repo + "/blob/" + pin + "/README.md"},
                  "public_response_sha256": {"metadata": metadata_sha, "commit": commit_sha,
                                             "releases": releases_sha, "readme_json": readme_sha, "tree": tree_sha}}
        if tree["truncated"]:
            raise ValueError("candidate_tree_truncated")
        observations.append(record)
    latest, latest_sha = public_json("https://pypi.org/pypi/alpaca-py/json")
    result = {"candidate_sources": observations, "alpaca_pypi_latest": latest["info"]["version"],
              "alpaca_pypi_response_sha256": latest_sha,
              "source_scope": "public source/metadata only; no install or native data qualification of either alternative"}
    write_json(OUTPUT / "sources" / "public-observations.json", result)
    return result


def verify_previous():
    results = []
    names = {1: "1-ca-currency-field", 4: "4-alpaca-py-latest-seams", 5: "5-parameterized-comparator",
             7: "7-data-licensing-clauses", 8: "8-feast-pit-join", 12: "12-ca-currency-shared-capture",
             17: "17-sec-api-python-disposition", 18: "18-rossod4-quantlab-disposition"}
    for index, name in names.items():
        path = ROOT / PREVIOUS / (name + ".json")
        receipt = json.loads(path.read_text())
        checked = []
        for ref in receipt["raw_artifacts"]:
            source = ROOT / ref["path"]
            actual = digest(source.read_bytes())
            if actual != ref.get("published_sha256", ref["sha256"]):
                raise ValueError("retained_artifact_hash_mismatch")
            checked.append({"path": ref["path"], "sha256": actual})
        results.append({"index": index, "receipt": artifact(path), "verified_artifacts": checked,
                        "historical_outcome": receipt["outcome"],
                        "historical_observation": receipt["checked_at"],
                        "scope": "integrity of retained published bytes; original private market-data inputs are unavailable here"})
    write_json(OUTPUT / "retained-integrity.json", results)
    return results


def main():
    global OUTPUT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sdk-python", type=Path, required=True)
    parser.add_argument("--feast-python", type=Path, required=True)
    parser.add_argument("--run-name", default="final", help="new owned output subdirectory; never overwrite a run")
    parser.add_argument("--skip-news", action="store_true", help="keep prior native news refusals without repeating the provider call")
    args = parser.parse_args()
    if not args.run_name.isalnum():
        raise ValueError("run_name_must_be_alphanumeric")
    OUTPUT = OUTPUT / args.run_name
    if OUTPUT.exists():
        raise ValueError("existing_run_must_be_retained")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    verify_previous()
    public = sources()
    if public["alpaca_pypi_latest"] != "0.44.0":
        raise ValueError("new_alpaca_release_requires_a_new_compatibility_arm")
    input_paths = [
        "blueprints/us-equities/market-data-reference/run.py", "blueprints/us-equities/market-data-reference/native_news.py",
        "blueprints/us-equities/authenticated-data/compare_providers.py", "tests/test_market_data_gap_integration.py",
        HELPERS + "/compare_multi.py", HELPERS + "/feast_pit_fixture.py", HELPERS + "/seam_probe.py",
        "blueprints/us-equities/market-data-reference/retry_probe.py", "tests/test_alpaca_historical.py",
        "blueprints/us-equities/alpaca-historical/collect.py", "blueprints/us-equities/alpaca-historical/plan.json",
        "scripts/path_safety.py", "scripts/component_matrix.py", "scripts/catalog_decisions.py",
        "blueprints/us-equities/market-data-reference/vendor_binding.py",
        "catalogs/us-equities/market-data-reference-gap-review-20261010.json"]
    inputs = [artifact(ROOT / path) for path in input_paths]
    commands = [
        command("sdk-packages", ["uv", "pip", "freeze", "--python", args.sdk_python]),
        command("feast-packages", ["uv", "pip", "freeze", "--python", args.feast_python]),
        command("sdk-seams", [args.sdk_python, HELPERS + "/seam_probe.py"]),
        command("sdk-source-binding", [args.sdk_python, "blueprints/us-equities/market-data-reference/vendor_binding.py"]),
        command("sdk-tests", [args.sdk_python, "-m", "unittest", "tests.test_alpaca_historical", "-v"]),
        command("retry-mutation", [sys.executable, "blueprints/us-equities/market-data-reference/retry_probe.py",
                                   "--python", args.sdk_python], timeout=40),
        command("comparison-and-closeout-tests", [sys.executable, "-m", "unittest", "tests.test_market_data_gap_integration", "-v"]),
        command("feast-pit", [args.feast_python, HELPERS + "/feast_pit_fixture.py"], timeout=45),
    ]
    if not args.skip_news:
        commands.append(command("gdelt-news", [args.sdk_python, "blueprints/us-equities/market-data-reference/native_news.py"], timeout=35))
    unchanged = inputs == [artifact(ROOT / path) for path in input_paths]
    receipt = {"schema_version": 1, "observed_at_utc": datetime.now(timezone.utc).isoformat(),
               "kind": "artifact_measurement", "commands": commands, "inputs": inputs,
               "inputs_unchanged_during_run": unchanged, "news_call_skipped": args.skip_news,
               "source_scope": "public sources, synthetic SDK transports and local Feast fixture; GDELT is a separate native attempt"}
    write_json(OUTPUT / "run.json", receipt)
    print(json.dumps({"commands": [{"label": c["label"], "exit_code": c["exit_code"]} for c in commands],
                      "run_receipt": artifact(OUTPUT / "run.json")}, indent=2))
    required = [c for c in commands if c["label"] != "gdelt-news"]
    return 0 if unchanged and all(c["exit_code"] == 0 for c in required) else 1


if __name__ == "__main__":
    raise SystemExit(main())
