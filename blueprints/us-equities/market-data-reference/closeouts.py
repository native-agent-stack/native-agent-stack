#!/usr/bin/env python3
"""Publish this layer's explicitly scoped closeouts from the retained accepted run.

Follows the existing gap-wave receipt vocabulary and component-matrix join.
It records neither an independent review nor a provider/host qualification.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from scripts import host_receipts


BASE = "evidence/artifacts/market-data-reference-20261010"
SOURCE = "catalogs/landscape/gap-crosswalk-92bb279.json"
REVIEW = "catalogs/us-equities/market-data-reference-gap-review-20261010.json"
OUTCOMES = {
    1: ("advanced", "source_review", "The optional missing/empty currency contract is recorded and the refusal regression passes.",
        ["Explicit action-specific currency is still absent; numerical agreement does not reconcile cash units."]),
    4: ("settled", "local_integration", "Latest released Alpaca 0.44.0 is installed in a fresh prefix; 23 real SDK tests pass with zero skips and the retry mutation is caught by its assertion with zero setup errors.", []),
    5: ("settled", "local_integration", "The retained provider-neutral implementation is promoted through the supported entry point; fresh tests cover multiple symbols, date ranges, precision and unavailable references. The hash-verified September native-data run records the exact AAPL reproduction and nonzero IBM/SPY scores.", []),
    7: ("advanced", "source_review", "Public Alpaca/SEC/LEAN clauses and the prior source captures are retained and their hashes verified.",
        ["The acquiring account's applicable agreements, storage/derived-data rights and LEAN third-party sample-data rights are unestablished; the owner/account lane must supply them."]),
    8: ("advanced", "local_integration", "Feast 0.66.0's local file-store fixture matches the independent event-time oracle, reports stale-row loss and catches duplicate/unrequested rows. Native GDELT news returns a retained RateLimitError refusal.",
        ["News is unavailable in the native attempt; macro vintages, a real stream and a server store remain unqualified. The Feast source is synthetic and does not reconstruct original historical availability."]),
    12: ("advanced", "source_review", "The duplicate cash-unit gap has its own receipt bound to the same optional-currency evidence and passing refusal test.",
         ["Explicit action-specific currency is still absent; this duplicate does not provide an independent currency observation."]),
    17: ("settled", "source_review", "Pinned SEC-API Python release/readme/license observations have a conditional disposition registered in the canonical catalog identity union.", []),
    18: ("settled", "source_review", "The current quantlab README/tree and absent software license have an explicit not-adopted disposition registered in the canonical catalog identity union.", []),
}


def raw(path):
    return (ROOT / path).read_bytes()


def sha(path):
    return hashlib.sha256(raw(path)).hexdigest()


def artifact(path):
    return {"path": path, "sha256": sha(path)}


def write(path, data):
    destination = ROOT / path
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")


def main():
    crosswalk = json.loads(raw(SOURCE))
    run_path = BASE + "/published/run.json"
    run = json.loads(raw(run_path))
    if not run["inputs_unchanged_during_run"] or any(c["exit_code"] != 0 for c in run["commands"]):
        raise ValueError("accepted_run_must_have_one_unchanged_input_generation_and_no_failed_required_command")
    for entry in run["inputs"]:
        if sha(entry["path"]) != entry["sha256"]:
            raise ValueError("accepted_input_changed")
    commands = {c["label"]: c for c in run["commands"]}
    retry = (ROOT / commands["retry-mutation"]["outputs"][0]["path"]).read_text()
    if "assertion_kill_without_setup_errors=true" not in retry:
        raise ValueError("retry_proof_must_be_an_assertion_kill")
    gaps = {g["index"]: g for layer in crosswalk["layers"] if layer["layer_id"] == "market-data-reference" for g in layer["gaps"]}
    previous = json.loads(raw(BASE + "/published/retained-integrity.json"))
    previous_by_gap = {r["index"]: r for r in previous}
    observed = datetime.now(timezone.utc).isoformat()
    references = []
    for index, (outcome, evidence_class, claim, residuals) in OUTCOMES.items():
        paths = [run_path, BASE + "/published/retained-integrity.json", REVIEW,
                 previous_by_gap[index]["receipt"]["path"]]
        paths.extend(a["path"] for a in previous_by_gap[index]["verified_artifacts"])
        paths.extend(a["path"] for c in run["commands"] for a in c["outputs"])
        if index in {17, 18}:
            paths += [BASE + "/published/sources/public-observations.json",
                      "catalogs/us-equities/decision-index.json", "catalogs/us-equities/manifest.json"]
        if index == 8:
            paths += [BASE + "/raw/gdelt-news.stdout.txt", BASE + "/run.json"]
        limitations = [
            "SDK transports and comparison controls are synthetic; Feast is a native local tool over synthetic data.",
            "The September private market-data inputs are unavailable here. Their retained aggregate results are dated observations, not a fresh data acquisition or a replay on this host.",
            "No provider ranking, entitlement, host qualification, strategy number, order or historical as-known universe is established.",
        ]
        receipt = {"schema_version": 1, "id": f"market-data-reference-20261010-gap-{index}",
                   "catalog": "us-equities", "layer_id": "market-data-reference", "gap_index": index,
                   "source_revision": crosswalk["source_revision"], "base_commit": "0947b01289dcaa9157aa38392a94cf00f592b86d",
                   "gap_text_sha256": hashlib.sha256(gaps[index]["text"].encode()).hexdigest(),
                   "observed_at_utc": observed, "outcome": outcome, "evidence_class": evidence_class,
                   "claim": claim, "residuals": residuals, "limitations": limitations,
                   "artifacts": [artifact(p) for p in sorted(set(paths))]}
        path = BASE + f"/receipts/gap-{index:02d}.json"
        write(path, receipt)
        references.append(artifact(path))
    write("catalogs/landscape/gap-closeouts/market-data-reference-20261010.json", {
        "schema_version": 1, "source_revision": crosswalk["source_revision"],
        "crosswalk_sha256": sha(SOURCE), "owner": "catalyst-watch",
        "scope": "Eight assigned market-data-reference gaps; only four settled receipts reduce counts. Partial residuals stay open.",
        "receipts": references})
    receipt = {"schema_version": 1, "id": "market-data-reference-gap-burndown-20261010", "kind": "artifact_measurement",
               "component_ids": ["alpaca-py"],
               "claim": "Four of eight assigned executable-now gaps close through current SDK compatibility, the promoted measured comparator and two indexed source dispositions. Four residual gaps remain open. The matrix joins hash-bound later receipts without changing the historical crosswalk.",
               "limitations": [
                   "Dividend currency, account/source data rights and missing news/macro/stream/server evidence remain unresolved.",
                   "Local fixture execution is separate from native provider data; a GDELT rate-limit refusal is retained without qualifying news.",
                   "Historical native-data comparison output is reused by hash; absent private input paths prevent a current replay. No strategy or order authority follows.",
                   "The first mutation helpers produced setup errors, which are not counted as kills. The accepted correction requires the native retry assertion with zero errors.",
               ], "commands": run["commands"], "inputs": run["inputs"],
               "gap_receipts": references, "accepted_run": artifact(run_path)}
    receipt_path = "evidence/receipts/market-data-reference-gap-burndown-20261010.json"
    write(receipt_path, receipt)
    manifest_path = ROOT / "manifests/evidence.json"
    manifest = json.loads(manifest_path.read_text())
    summary = {k: receipt[k] for k in ["id", "kind", "component_ids", "claim", "limitations"]}
    summary["path"] = receipt_path
    manifest["receipts"] = [r for r in manifest["receipts"] if r["id"] != receipt["id"]] + [summary]
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=True) + "\n")
    for path in sorted((ROOT / BASE).rglob("*")):
        if path.is_file():
            host_receipts.register_file(ROOT, path.relative_to(ROOT).as_posix())
    for path in [receipt_path, "catalogs/landscape/gap-closeouts/market-data-reference-20261010.json", REVIEW,
                 "catalogs/us-equities/decision-index.json", "catalogs/us-equities/manifest.json",
                 "scripts/component_matrix.py", "tests/test_market_data_gap_integration.py",
                 "blueprints/us-equities/authenticated-data/README.md", "blueprints/us-equities/authenticated-data/compare_providers.py",
                 "blueprints/us-equities/market-data-reference/README.md", "blueprints/us-equities/market-data-reference/run.py",
                 "blueprints/us-equities/market-data-reference/closeouts.py", "blueprints/us-equities/market-data-reference/retry_probe.py",
                 "blueprints/us-equities/market-data-reference/vendor_binding.py",
                 "blueprints/us-equities/market-data-reference/native_news.py"]:
        host_receipts.register_file(ROOT, path)
    print(json.dumps({"settled": [i for i, value in OUTCOMES.items() if value[0] == "settled"],
                      "partial": [i for i, value in OUTCOMES.items() if value[0] == "advanced"]}))


if __name__ == "__main__":
    main()
