"""Summarize observed gap work and publish single-gap evidence receipts.

Uses the existing gap_wave_ledger vocabulary. Never rewrites the historical
crosswalk, preregistration, reviewed-first-run record or execution oracle.
"""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / "evidence/artifacts/backtesting-gap-burndown-20261010/us-equities__backtesting-engine"
RAW = BASE / "raw"
NT_PIN = "1b0a49d2792a9432a3aca3fcb617ce7a630d905e"
LEAN_PIN = "985ef30ad3ac774218c5ac516b4cb0aa2655730f"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def capture(value, name):
    path = RAW / name
    data = json.dumps(value, indent=2, default=str) + "\n"
    assert str(Path.home()) not in data
    path.write_text(data)
    return path


def observed(name):
    receipt = json.loads((RAW / (name + ".json")).read_text())
    assert receipt["expectation_met"] and receipt["input_bytes_unchanged"]
    return receipt


def main():
    sys.path.insert(0, str(ROOT))
    from scripts import host_receipts

    sources = {}
    for repository, pin, files in [
        ("nautechsystems/nautilus_trader", NT_PIN,
         ["crates/backtest/src/exchange.rs", "crates/execution/src/matching_engine/mod.rs",
          "python/nautilus_trader/execution/__init__.pyi", "python/nautilus_trader/backtest/__init__.pyi"]),
        ("QuantConnect/Lean", LEAN_PIN,
         ["Tests/Common/Brokerages/AlpacaBrokerageModelTests.cs", "Tests/AssemblyInitialize.cs",
          "Common/Python/PythonInitializer.cs"]),
    ]:
        mirror = Path.home() / "code/upstream" / repository
        subprocess.run(["git", "-C", str(mirror), "cat-file", "-e", pin + "^{commit}"], check=True, capture_output=True)
        for file in files:
            data = subprocess.check_output(["git", "-C", str(mirror), "show", pin + ":" + file])
            sources[repository + "@" + pin + ":" + file] = hashlib.sha256(data).hexdigest()
    source_receipt = capture({"source_hashes": sources, "observed_utc": datetime.now(timezone.utc).isoformat(),
                              "engine_extension_sha256": "a53dd5a24fe77f4c66169af84ee9c7e292018010922e3dce9a8b6c9f7f3b7021",
                              "dotnet_sdk": {"version": "10.0.401", "sha512":
                                  "51c8b999af9e8dd9998c9edc5944e19a90788862068acd38694e098889054ce8c23d4f0c5cccfa16bf187d044562359e5ee69a9f8ad0bbe913ba90311fbce25b",
                                  "source": "https://builds.dotnet.microsoft.com/dotnet/release-metadata/10.0/releases.json"},
                              "scope": "source/runtime provenance, no qualification or broker acceptance"}, "source-pins.json")
    native = Path.home() / ".cache/native-agent-stack/backtesting-gaps-20261010/replay-diagnostic-2/native/receipt.json"
    replay = json.loads(native.read_text())
    assert replay["native_end_cash_usd"] == "90734.08" and replay["two_run_records_equal"]
    assert replay["dividend_cash_usd"] == "428.64" and not replay["unsupported_mappings"]
    mechanics = json.loads((Path.home() / ".cache/native-agent-stack/backtesting-gaps-20261010/mechanics-2/native/results.json").read_text())
    assert [x["native_end_cash"] for x in mechanics["results"]] == ["90732.08", "81468.16", "81466.16", "100000.00"]
    # Fresh records contain native generated UUIDs: publish only safe economic
    # projections, with the unchanged primary record's byte hash retained.
    replay_summary = capture({"primary_sha256": sha(native), "native_end_cash": replay["native_end_cash_usd"],
                               "dividend_cash": replay["dividend_cash_usd"], "bars": 725, "equal_runs": True,
                               "fills": [{k: v for k, v in f.items() if k in ("side", "quantity", "price", "fee", "utc_seconds")}
                                         for f in replay["fills"]],
                               "new_gate_qualification": False,
                               "review_boundary": "fresh comparator fails reviewed-first-run condition; 106 native checks pass"},
                              "native-replay-economic-summary.json")
    mechanics_summary = capture({"scope": mechanics["scope"], "qualifies_frozen_stress_case": False,
                                  "results": [{k: x[k] for k in ["id", "status", "target", "account_type", "native_end_cash", "native_fees"]}
                                              for x in mechanics["results"]], "slippage_fraction_mapped": False,
                                  "adaptive_state_implemented": False, "calibrated_liquidity": False},
                                 "native-mechanics-summary.json")
    ns = {"t": "http://microsoft.com/schemas/VisualStudio/TeamTest/2010"}
    trx = ROOT / ".runtime/lean-985ef30/TestResults/alpaca-model-py312.trx"
    counters = ET.parse(trx).find(".//t:Counters", ns).attrib
    assert counters["passed"] == "12" and counters["failed"] == "0" and counters["executed"] == "12"
    lean_summary = capture({"primary_trx_sha256": sha(trx), "counters": counters,
                            "surface": "unchanged pinned upstream AlpacaBrokerageModelTests",
                            "paper_adapter_initialized": False, "broker_requests": 0}, "lean-model-summary.json")
    accepted = json.loads((RAW / "accepted-v2-lean-data.verdict.json").read_text())
    assert accepted["verdict"] == "PASS" and accepted["complete"] and accepted["execution_checks"] == {
        "pass": 106, "fail": 0, "skipped": 0}
    releases = json.loads((RAW / "latest-nonprerelease.stdout.txt").read_text())
    assert releases[0]["tagName"] == "v1.231.0" and not any(x["isPrerelease"] for x in releases)
    review = ROOT / "evidence/artifacts/gap-wave2-20260923/us-equities__backtesting-engine/raw/6-agent-lab-parity-final-review-excerpt.md"
    reference = capture({"retained_review_path": str(review.relative_to(ROOT)), "sha256": sha(review),
                          "claim": "the historical review excerpt is retained, not a new review count"}, "review-excerpt-integrity.json")
    crosswalk = json.loads((ROOT / "catalogs/landscape/gap-crosswalk-92bb279.json").read_text())
    layer = next(x for x in crosswalk["layers"] if x["layer_id"] == "backtesting-engine")
    dispositions = {
        0: ("advanced", "local_integration", "Accepted one_zero comparator and fresh native execution reproduce; frozen stress/margin/adaptive mappings remain blocked.",
            ["accepted-v2-lean-data", "fresh-native-v2", "native-fee-margin-mechanics-2"]),
        1: ("deferred", "source_review", "No retained authorized Alpaca action-window directory or quote payload on this host; no lane credential/acquisition authority. Upstream examples directory has no unchanged equity example. The requested acquisition/unchanged-example gate is not closed.", []),
        2: ("settled", "native_proven", "Official latest non-prerelease list and tag response retained; rc5 selection remains unchanged.",
            ["latest-nonprerelease", "stable-release-tag"]),
        4: ("advanced", "native_proven", "All 12 unchanged LEAN AlpacaBrokerageModelTests pass via dotnet 10.0.401/explicit Python 3.12 after retained prerequisite failures. No keyed paper adapter initialization or vendor dataset claim.",
            ["lean-alpaca-model-tests-py312"]),
        6: ("settled", "local_integration", "All comparator modes executed: accepted v2 lean-data PASS; bars/no-attribution refuse incomplete evidence. Historical review excerpt retained and hash-verified.",
            ["accepted-v2-lean-data", "accepted-v2-bars", "accepted-v2-no-attribution", "local-parity-boundaries"]),
        7: ("settled", "local_integration", "Retained accepted v2 one_zero comparator PASS with 106 native execution checks; fresh diagnostic reproduces native end cash 90734.08, distributions 428.64 and equal runs. Ending-cash delta to frozen LEAN is zero instead of -655.12; the fresh run does not reset the review gate.",
            ["accepted-v2-lean-data", "native-spy-replay-2", "fresh-native-v2"]),
        8: ("deferred", "source_review", "No retained authorized AAPL quotes/action-window acquisition on this host. Existing native receipt demonstrates missing split/distribution treatment; synthetic quote fills cannot replace the historical-data gate.", []),
        9: ("advanced", "local_integration", "Native FixedFeeModel, MARGIN and over-capacity CASH refusal complete on retained SPY. Frozen fractional slippage/adaptive parity and calibrated depth remain unqualified, so this composite is not settled.",
            ["native-fee-margin-mechanics-2"]),
    }
    all_outputs = [source_receipt, replay_summary, mechanics_summary, lean_summary, reference]
    for index, (outcome, evidence_class, result, names) in dispositions.items():
        gap = next(x for x in layer["gaps"] if x["index"] == index)
        outputs = all_outputs + [RAW / (name + ".json") for name in names]
        for name in names:
            command = observed(name)
            outputs.extend(ROOT / x["path"] for x in command["captured_outputs"])
            verdict = RAW / (name + ".verdict.json")
            if verdict.exists():
                outputs.append(verdict)
        doc = {"id": f"backtesting-gap-burndown-20261010/backtesting-engine/{index}",
               "source_revision": crosswalk["source_revision"], "gap_refs": [index], "gap_index": index,
               "gap_text_sha256": hashlib.sha256(gap["text"].encode()).hexdigest(),
               "outcome": outcome, "settles_gap": True if outcome == "settled" else
                   "partially" if outcome == "advanced" else "deferred",
               "review_status": "pending independent PR review",
               "evidence_class": evidence_class, "result": result,
               "raw_outputs": [{"path": str(p.relative_to(ROOT)), "sha256": sha(p)} for p in sorted(set(outputs))],
               "checked_at": "2026-10-10", "model_calls": [], "broker_requests": 0,
               "limitations": ["Historical source-revision gap accounting; no automatic strategy, paper, platform or live promotion.",
                               "New gate-owner review/first-run acceptance is not fabricated."]}
        (BASE / f"{index}-gap.json").write_text(json.dumps(doc, indent=2) + "\n")
    for path in sorted(BASE.rglob("*")):
        if path.is_file():
            host_receipts.register_file(ROOT, str(path.relative_to(ROOT)))
    print(json.dumps({"settled": [2, 6, 7], "advanced": [0, 4, 9], "deferred": [1, 8],
                      "no_broker_requests": True, "matrix_effect_expected": "8->5 executable-now; 12->9 open"}))


if __name__ == "__main__":
    main()
