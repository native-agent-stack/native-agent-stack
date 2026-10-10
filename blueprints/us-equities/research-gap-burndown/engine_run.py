#!/usr/bin/env python3
"""Replay frozen selected targets with native LEAN accounting in the existing sandbox."""
from __future__ import annotations

import argparse
from datetime import datetime
from decimal import Decimal
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
import traceback

from run import HERE, ROOT, digest, load_data, original, utc, write_new


def target_schedule(source, chronology):
    plan, panel, dates, _, _, _ = load_data(source)
    receipt = json.loads(chronology.read_text())
    if receipt["status"] != "pass":
        raise ValueError("chronology must pass before an engine replay")
    arm = next(a for a in receipt["result"]["walk_forward_arms"] if a["purged_size"] == 6)
    if arm["training_boundary_violations"]:
        raise ValueError("crossed labels cannot select engine targets")
    eligible_first = next(i for i, day in enumerate(dates) if day >= plan["eligible_start"])
    targets = {}
    evaluator = original()
    for fold in arm["folds"]:
        candidate = fold["selection"]["chosen"]
        first, last = dates.index(fold["test_first"]), dates.index(fold["test_last"])
        episodes = [i for i in range(first, last + 1) if (i - eligible_first) % 5 == 0 and i + 6 <= last]
        for i in episodes:
            targets[dates[i]] = {s: str(w) for s, w in evaluator.weights(panel, i, candidate).items()}
            # A coinciding next decision replaces this exit with its net target;
            # no pretend independent episode round-trip/cost equality follows.
            targets[dates[i + 5]] = {}
    return targets


def reconcile(rows, initial="100000"):
    intents = {r["order_id"]: r for r in rows if r["kind"] == "intent"}
    fills = [r for r in rows if r["kind"] == "order" and r["status"] == "Filled"]
    finals = [r for r in rows if r["kind"] == "final"]
    if len(finals) != 1 or not fills:
        raise ValueError("missing native final state or fills")
    if len(intents) != sum(r["kind"] == "intent" for r in rows) or len({r["order_id"] for r in fills}) != len(fills):
        raise ValueError("duplicate intent or native terminal fill")
    if set(intents) != {r["order_id"] for r in fills}:
        raise ValueError("intent lacks a terminal native fill")
    if any(r["kind"] == "order" and r["status"] in ["Invalid", "Canceled"] for r in rows):
        raise ValueError("unexpected native rejection or cancellation")
    positions, notional, fees = {}, Decimal(0), Decimal(0)
    for row in fills:
        intent = intents.get(row["order_id"])
        if not intent or row["asset"] != intent["asset"] or Decimal(str(row["quantity"])) != Decimal(str(intent["quantity"])):
            raise ValueError("native fill is not bound to its frozen intent")
        if Decimal(str(row["utc_seconds"])) <= Decimal(str(intent["utc_seconds"])):
            raise ValueError("native fill must follow its decision")
        quantity, price, fee = (Decimal(str(row[k])) for k in ["quantity", "price", "fee"])
        if not all(v.is_finite() for v in [quantity, price, fee]) or price <= 0 or fee < 0:
            raise ValueError("invalid native fill/fee")
        notional += quantity * price
        fees += fee
        positions[row["asset"]] = positions.get(row["asset"], Decimal(0)) + quantity
    dividends = sum((Decimal(str(r["amount"])) for r in rows if r["kind"] == "dividend"), Decimal(0))
    final = finals[0]
    cash = Decimal(str(final["cash"]))
    expected = Decimal(initial) - notional - fees + dividends
    if not expected.is_finite() or not cash.is_finite() or abs(cash - expected) > Decimal("0.01"):
        raise ValueError("native dividend/fill/fee cash reconciliation failed")
    if any(Decimal(str(q)) for q in final["positions"].values()) or any(positions.values()):
        raise ValueError("native terminal positions must be flat")
    if abs(Decimal(str(final["equity"])) - cash) > Decimal("0.01"):
        raise ValueError("flat native equity and cash differ")
    return {"fill_count": len(fills), "decisions": final["decisions"], "cash_usd": str(cash),
            "signed_fill_notional_usd": str(notional), "fees_usd": str(fees),
            "native_dividends_usd": str(dividends), "expected_cash_usd": str(expected),
            "cash_residual_usd": str(cash - expected), "flat": True,
            "return_convention": "raw fills plus separately credited native distributions minus native fees"}


def native_helpers():
    directory = HERE.parent / "execution-realism"
    sys.path.insert(0, str(directory))
    spec = importlib.util.spec_from_file_location("research_native_lean", directory / "run.py")
    native = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(native)
    sys.path.pop(0)
    return native


def bind_native_orders(rows, native_orders):
    """Bind callbacks to LEAN's exported order type, tag, symbol and sizing."""
    intents = [r for r in rows if r["kind"] == "intent"]
    if {str(r["order_id"]) for r in intents} != set(native_orders):
        raise ValueError("native exported order set differs from frozen intents")
    for row in intents:
        order = native_orders[str(row["order_id"])]
        # LEAN OrderType.MarketOnOpen is 4 in the pinned serialization enum.
        if order["type"] != 4 or order["tag"] != "frozen-target:" + row["decision"]:
            raise ValueError("native order type or target attribution differs")
        if order["symbol"]["value"] != row["asset"] or Decimal(str(order["quantity"])) != Decimal(str(row["quantity"])):
            raise ValueError("native exported order symbol or quantity differs")
        seconds = Decimal(str(datetime.fromisoformat(order["time"].replace("Z", "+00:00")).timestamp()))
        if seconds != Decimal(str(row["utc_seconds"])):
            raise ValueError("native order creation time differs from frozen intent")


def execute(source, dotnet, chronology, out):
    native = native_helpers()
    plan = json.loads((HERE / "engine-plan.json").read_text())
    head = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    if head != plan["source_commit"]:
        raise ValueError("engine source pin differs")
    targets = target_schedule(source, chronology)
    write_new(out / "targets.json", targets)
    # All mounted inputs originate in this isolated public-source clone, never
    # an account store, peer lane, or protected paper evidence directory.
    inputs = {str(p.relative_to(source)): digest(p) for base in [source / "Data", source / "Launcher/bin/Debug"]
              for p in sorted(base.rglob("*")) if p.is_file()}
    write_new(out / "inputs.json", inputs)
    (out / "home").mkdir()
    (out / "build").mkdir()
    shutil.copyfile(HERE / "FrozenResearchTargets.cs", out / "build/FrozenResearchTargets.cs")
    prefix = native.sandbox(source, dotnet, out)
    prefix += ["--setenv", "LD_LIBRARY_PATH", "/dotnet/icu/usr/lib/x86_64-linux-gnu",
               "--setenv", "DOTNET_ICU_VERSION_OVERRIDE", "78"]
    compilers = list(dotnet.parent.glob("sdk/*/Roslyn/bincore/csc.dll"))
    packs = list(dotnet.parent.glob("packs/Microsoft.NETCore.App.Ref/*/ref/net10.0"))
    if len(compilers) != 1 or len(packs) != 1:
        raise ValueError("select the isolated .NET10 compiler and reference pack")
    refs = ["/dotnet/" + str(p.relative_to(dotnet.parent)) for p in sorted(packs[0].glob("*.dll"))]
    refs += ["/engine/" + n for n in ["QuantConnect.Algorithm.dll", "QuantConnect.Common.dll", "QuantConnect.Indicators.dll", "Python.Runtime.dll", "NodaTime.dll"]]
    rsp = ["/nologo", "/target:library", "/deterministic+", "/out:/run/build/FrozenResearchTargets.dll"]
    rsp += ['/reference:"' + p + '"' for p in refs] + ["/run/build/FrozenResearchTargets.cs"]
    (out / "build/compiler.rsp").write_text("\n".join(rsp) + "\n")
    native.execute(prefix, ["/dotnet/dotnet", "/dotnet/" + str(compilers[0].relative_to(dotnet.parent)), "@/run/build/compiler.rsp"], out, "compile", 60)
    results = []
    for case in plan["cases"]:
        name = case["id"]
        directory = out / name
        directory.mkdir()
        config = {
            "environment": "backtesting", "live-mode": False,
            "algorithm-type-name": "FrozenResearchTargets", "algorithm-language": "CSharp",
            "algorithm-location": "/run/build/FrozenResearchTargets.dll", "composer-dll-directory": "/engine",
            "data-folder": "/data", "results-destination-folder": "/run/" + name,
            "object-store-root": "/run/" + name + "/storage", "close-automatically": True,
            "daily-precise-end-time": True,
            "parameters": {"fee-usd": case["fee_usd"], "slippage": case["slippage"],
                           "targets": "/run/targets.json", "ledger": "/run/" + name + "/audit.jsonl"},
            "log-handler": "QuantConnect.Logging.CompositeLogHandler", "messaging-handler": "QuantConnect.Messaging.Messaging",
            "job-queue-handler": "QuantConnect.Queues.JobQueue", "api-handler": "QuantConnect.Api.Api",
            "map-file-provider": "QuantConnect.Data.Auxiliary.LocalDiskMapFileProvider",
            "factor-file-provider": "QuantConnect.Data.Auxiliary.LocalDiskFactorFileProvider",
            "data-provider": "QuantConnect.Lean.Engine.DataFeeds.DefaultDataProvider", "data-channel-provider": "DataChannelProvider",
            "object-store": "QuantConnect.Lean.Engine.Storage.LocalObjectStore", "data-aggregator": "QuantConnect.Lean.Engine.DataFeeds.AggregationManager",
            "setup-handler": "QuantConnect.Lean.Engine.Setup.BacktestingSetupHandler",
            "result-handler": "QuantConnect.Lean.Engine.Results.BacktestingResultHandler", "data-feed-handler": "QuantConnect.Lean.Engine.DataFeeds.FileSystemDataFeed",
            "real-time-handler": "QuantConnect.Lean.Engine.RealTime.BacktestingRealTimeHandler",
            "history-provider": ["QuantConnect.Lean.Engine.HistoricalData.SubscriptionDataReaderHistoryProvider"],
            "transaction-handler": "QuantConnect.Lean.Engine.TransactionHandlers.BacktestingTransactionHandler"}
        write_new(directory / "config.json", config)
        native.execute(prefix, ["/dotnet/dotnet", "/engine/QuantConnect.Lean.Launcher.dll", "--config", "/run/" + name + "/config.json"], out, name, 120)
        status = json.loads((directory / "FrozenResearchTargets.json").read_text())
        if status.get("state", {}).get("Status") != "Completed" or status.get("state", {}).get("RuntimeError"):
            raise ValueError("native engine did not complete cleanly")
        failed = list(directory.glob("failed-data-requests-*.txt"))
        reports = list(directory.glob("data-monitor-report-*.json"))
        if len(failed) != 1 or failed[0].stat().st_size or len(reports) != 1:
            raise ValueError("native data request logs missing or failed")
        monitor = json.loads(reports[0].read_text())
        if monitor["failed-data-requests-count"] or monitor["failed-universe-data-requests-count"] or monitor["succeeded-data-requests-count"] <= 0:
            raise ValueError("native monitor records failed or absent input requests")
        rows = [json.loads(line, parse_float=Decimal) for line in (directory / "audit.jsonl").read_text().splitlines()]
        bind_native_orders(rows, status["orders"])
        result = reconcile(rows)
        result.update(case=case, audit_sha256=digest(directory / "audit.jsonl"),
                      native_result_sha256=digest(directory / "FrozenResearchTargets.json"),
                      failed_data_request_bytes=0, data_monitor=monitor,
                      data_monitor_sha256=digest(reports[0]))
        write_new(directory / "analysis.json", result)
        results.append(result)
    unchanged = all(digest(source / p) == sha for p, sha in inputs.items())
    if not unchanged:
        raise ValueError("mounted engine input changed")
    return {"cases": results, "mounted_inputs": len(inputs), "inputs_unchanged": unchanged,
            "targets": len(targets), "targets_sha256": digest(out / "targets.json"),
            "inputs_sha256": digest(out / "inputs.json"), "engine_source_commit": head,
            "scope": "Offline raw-price/distribution portfolio integration with illustrative costs; no financing, capacity, PIT-universe, broker or alpha acceptance."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lean-source", type=Path, required=True)
    parser.add_argument("--dotnet", type=Path, required=True)
    parser.add_argument("--chronology", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    if out.exists() or out.is_relative_to(ROOT):
        raise ValueError("use a fresh output directory outside the worktree")
    out.mkdir(parents=True, mode=0o700)
    write_new(out / "freeze.json", {"at": utc(), "engine_plan_sha256": digest(HERE / "engine-plan.json"),
        "source_sha256": digest(Path(__file__)), "algorithm_sha256": digest(HERE / "FrozenResearchTargets.cs"),
        "chronology_sha256": digest(args.chronology)})
    start, begin, result, failure = utc(), time.perf_counter(), None, None
    try:
        result = execute(args.lean_source.resolve(), args.dotnet.resolve(), args.chronology, out)
    except Exception as error:
        failure = {"type": type(error).__name__, "message": str(error).replace(str(Path.home()), "~"),
                   "traceback": traceback.format_exc().replace(str(Path.home()), "~")}
    write_new(out / "receipt.json", {"schema_version": 1, "status": "fail" if failure else "pass",
        "evidence_class": "local_integration", "start_utc": start, "end_utc": utc(),
        "elapsed_seconds": time.perf_counter() - begin, "freeze_sha256": digest(out / "freeze.json"),
        "result": result, "failure": failure})
    print(json.dumps({"status": "fail" if failure else "pass", "failure": failure["message"] if failure else None}))
    return 1 if failure else 0


if __name__ == "__main__":
    raise SystemExit(main())
