#!/usr/bin/env python3
"""Invoke native research APIs on frozen bundled inputs, retaining honest receipts.

This is experiment orchestration, not a broker adapter or a forecasting engine.
Sources/API pins and prespecified comparison rules are in plan.json. Numerical
models, splitters, factor cleaning and uncertainty estimation remain upstream.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
import traceback
import warnings
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SEED = 260410


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def utc():
    return datetime.now(timezone.utc).isoformat()


def write_new(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def original():
    path = ROOT / "blueprints/us-equities/research-evaluation/evaluate.py"
    spec = importlib.util.spec_from_file_location("frozen_research_evaluation", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def convert_price_units(frame):
    """Use pandas' explicit conversion for LEAN's ten-thousandth-dollar OHLC."""
    fields = ["open", "high", "low", "close"]
    frame[fields] = frame[fields].astype(float) / 10000
    return frame


def fold_labels(panel, episodes, candidates, cost, last_test):
    """Evaluate through this fold's last session, retaining censored outcomes."""
    evaluator = original()
    bounded = {asset: rows[:last_test + 1] for asset, rows in panel.items()}
    labels = [evaluator.label(bounded, i, c, cost) for i in episodes for c in candidates]
    boundary = next(iter(panel.values()))[last_test]["date"]
    if any(r.get("exit", boundary) > boundary for r in labels):
        raise ValueError("evaluation label crosses its own fold boundary")
    return labels


def load_data(source):
    import numpy as np
    import pandas as pd

    plan = json.loads((ROOT / "blueprints/us-equities/research-evaluation/plan.json").read_text())
    for name, expected in plan["inputs"].items():
        if digest(source / name) != expected:
            raise ValueError("frozen input mismatch: " + name)
    # Reuse the existing reviewed loader's OHLC/calendar/map/split checks.
    panel, dates, _, counts = original().load_panel(source, plan)
    data = {}
    for asset in plan["assets"]:
        path = source / ("Data/equity/usa/daily/" + asset.lower() + ".zip")
        with zipfile.ZipFile(path) as archive:
            if len(archive.namelist()) != 1:
                raise ValueError("daily archive member count changed")
            with archive.open(archive.namelist()[0]) as stream:
                frame = pd.read_csv(stream, header=None,
                                    names=["date", "open", "high", "low", "close", "volume"])
        frame["date"] = pd.to_datetime(frame["date"], format="%Y%m%d %H:%M")
        frame = frame.set_index("date").loc[plan["data_start"]:plan["development_end"]]
        # pandas 3 disallows silently upcasting integer columns during .loc
        # assignment. Explicit dtype conversion preserves the integer source
        # unit contract before dividing; native DataFrame.astype owns conversion.
        frame = convert_price_units(frame)
        frame["amount"] = frame["volume"] * frame["close"]
        if not np.isfinite(frame.to_numpy(dtype=float)).all():
            raise ValueError("nonfinite bundled value")
        data[asset] = frame
    closes = pd.DataFrame({name: frame["close"] for name, frame in data.items()})
    if closes.isna().any().any():
        raise ValueError("asset sessions must stay grouped")
    return plan, panel, dates, counts, data, closes


def label_crossings(train, test, horizon=6):
    """Count train outcome intervals that intersect any test/outcome footprint."""
    tests = set(map(int, test))
    footprint = {i + offset for i in tests for offset in range(horizon + 1)}
    return sum(any(int(i) + offset in footprint for offset in range(1, horizon + 1))
               for i in train)


def forecast_record(model, fold, asset, observed, prediction, scale, elapsed):
    import numpy as np

    observed = np.asarray(observed, dtype=float)
    prediction = np.asarray(prediction, dtype=float)
    if observed.shape != prediction.shape or observed.ndim != 1 or not len(observed):
        raise ValueError("forecast and observations must have identical nonempty shape")
    if not np.isfinite(observed).all() or not np.isfinite(prediction).all():
        raise ValueError("forecast contains nonfinite values")
    if not np.isfinite(scale) or scale <= 0:
        raise ValueError("MASE training scale must be positive and finite")
    mae = float(np.mean(np.abs(prediction - observed)))
    return {"model": model, "fold": fold, "asset": asset, "observed": observed.tolist(),
            "prediction": prediction.tolist(), "mae": mae, "mase": mae / scale,
            "training_naive_scale": float(scale), "elapsed_seconds": elapsed}


def make_folds(closes, original_plan):
    from skfolio.model_selection import WalkForward

    eligible = closes.loc[original_plan["eligible_start"]:original_plan["development_end"]]
    splitter = WalkForward(train_size=252, test_size=63, purged_size=6, reduce_test=True)
    rows = []
    for number, (train, test) in enumerate(splitter.split(eligible), 1):
        if len(test) < 5:
            continue
        for asset in original_plan["assets"]:
            history = eligible[asset].iloc[train].to_numpy(dtype=float)
            gap = int(test[0] - train[-1] - 1)
            target = eligible[asset].iloc[test[:5]].to_numpy(dtype=float)
            rows.append({"fold": number, "asset": asset, "history": history,
                         "gap": gap, "target": target,
                         "origin": eligible.index[train[-1]].isoformat(),
                         "target_dates": [d.isoformat() for d in eligible.index[test[:5]]],
                         "scale": float(abs(history[1:] - history[:-1]).mean())})
    return rows


def chronology(source):
    import numpy as np
    import pandas as pd
    from skfolio.model_selection import CombinatorialPurgedCV, WalkForward

    plan, panel, dates, counts, _, closes = load_data(source)
    evaluator = original()
    eligible = [i for i, d in enumerate(dates) if plan["eligible_start"] <= d <= plan["development_end"]]
    frame = pd.DataFrame({"date": [dates[i] for i in eligible]})
    arms = []
    for purge in (0, 6):
        arm = {"purged_size": purge, "folds": [], "training_boundary_violations": 0,
               "fold_censored_evaluation_episodes": 0}
        splitter = WalkForward(train_size=252, test_size=63, purged_size=purge, reduce_test=True)
        for number, (tr, te) in enumerate(splitter.split(frame), 1):
            train, test = [eligible[int(i)] for i in tr], [eligible[int(i)] for i in te]
            episodes = [i for i in train if (i - eligible[0]) % 5 == 0]
            crossing = sum(i + 6 >= test[0] for i in episodes)
            arm["training_boundary_violations"] += crossing
            selection, refusal = None, None
            if crossing:
                # Retain the original selector's real refusal, rather than
                # merely counting crossings and skipping its invocation.
                labels = [evaluator.label(panel, i, c, Decimal(plan["round_trip_cost_fraction"]))
                          for i in episodes for c in plan["candidates"]]
                try:
                    evaluator.choose(labels, plan["selection_candidates"], dates[test[0]])
                except ValueError as error:
                    refusal = str(error)
                if refusal != "training label overlap with evaluation decision":
                    raise AssertionError("zero-purge selection must refuse crossed outcomes")
            else:
                truncated = {s: r[:test[0]] for s, r in panel.items()}
                labels = [evaluator.label(truncated, i, c, Decimal(plan["round_trip_cost_fraction"]))
                          for i in episodes for c in plan["candidates"]]
                selection = evaluator.choose(labels, plan["selection_candidates"], dates[test[0]])
            eval_episodes = [i for i in test if (i - eligible[0]) % 5 == 0]
            censored = sum(i + 6 > test[-1] for i in eval_episodes)
            evaluated = fold_labels(panel, eval_episodes, plan["candidates"],
                                    Decimal(plan["round_trip_cost_fraction"]), test[-1])
            if sum(r["status"] == "censored" for r in evaluated) != censored * len(plan["candidates"]):
                raise AssertionError("fold censoring count differs from actual evaluation")
            arm["fold_censored_evaluation_episodes"] += censored
            arm["folds"].append({"number": number, "train_last": dates[train[-1]],
                                 "test_first": dates[test[0]], "test_last": dates[test[-1]],
                                 "crossing_training_labels": crossing,
                                 "fold_censored_evaluation_episodes": censored,
                                 "selection": selection, "selection_refusal": refusal,
                                 "evaluation_summary": evaluator.summaries(evaluated, plan["candidates"])})
        arms.append(arm)
    if arms[0]["training_boundary_violations"] == 0 or arms[1]["training_boundary_violations"]:
        raise AssertionError("purge controls failed to discriminate label leakage")
    cv = []
    for purge, embargo in ((0, 0), (6, 0), (6, 6)):
        splitter = CombinatorialPurgedCV(n_folds=10, n_test_folds=2,
                                        purged_size=purge, embargo_size=embargo)
        count = dropped = 0
        for train, tests in splitter.split(frame):
            test = np.concatenate(tests)
            count += label_crossings(train, test)
            dropped += len(frame) - len(train) - len(test)
        cv.append({"purged_size": purge, "embargo_size": embargo,
                   "split_count": splitter.n_splits, "crossing_label_intervals": count,
                   "excluded_indices_across_splits": dropped})
    if cv[0]["crossing_label_intervals"] == 0 or cv[-1]["crossing_label_intervals"]:
        raise AssertionError("native purge/embargo interval checks failed")
    # A deliberate crossed interval must be refused by the same pure guard.
    if label_crossings([9], [10], 6) != 1:
        raise AssertionError("crossed-label negative control lost sensitivity")
    return {"kind": "native_chronology_control", "session_counts": counts,
            "historical_plan_already_purged_size": plan["splitter"]["purged_size"],
            "walk_forward_arms": arms, "cpcv_sensitivity": cv,
            "statistical_independence_established": False,
            "embargo_scope": "CPCV supports a future-side embargo; WalkForward has no embargo parameter and uses only prior training.",
            "reserved_reused": False, "forecast_cases": len(make_folds(closes, plan))}


def classical(source):
    import numpy as np
    import pandas as pd
    from alphalens.performance import factor_information_coefficient
    from alphalens.utils import get_clean_factor_and_forward_returns
    from arch import arch_model
    from statsforecast import StatsForecast
    from statsforecast.models import AutoARIMA
    from statsmodels.tsa.arima.model import ARIMA

    plan, _, _, _, data, closes = load_data(source)
    cases = make_folds(closes, plan)
    rows = []
    for case in cases:
        history, h = case["history"], case["gap"] + 5
        begin = time.perf_counter()
        native = ARIMA(history, order=(1, 1, 0)).fit()
        pred = native.forecast(h)[case["gap"]:]
        rows.append(forecast_record("statsmodels-ARIMA-1-1-0", case["fold"], case["asset"],
                                    case["target"], pred, case["scale"], time.perf_counter() - begin))
        begin = time.perf_counter()
        frame = pd.DataFrame({"unique_id": case["asset"], "ds": np.arange(len(history)), "y": history})
        native = StatsForecast(models=[AutoARIMA(season_length=1)], freq=1, n_jobs=1)
        pred = native.forecast(h=h, df=frame)["AutoARIMA"].to_numpy()[case["gap"]:]
        rows.append(forecast_record("statsforecast-AutoARIMA", case["fold"], case["asset"],
                                    case["target"], pred, case["scale"], time.perf_counter() - begin))
        rows.append(forecast_record("last-close-naive", case["fold"], case["asset"], case["target"],
                                    np.repeat(history[-1], 5), case["scale"], 0.0))
    # Factor IC is a native diagnostic on public raw-price data, not engine PnL.
    momentum = closes.pct_change(20).loc[plan["eligible_start"]:plan["development_end"]].stack()
    momentum.index.names = ["date", "asset"]
    cleaned = get_clean_factor_and_forward_returns(momentum, closes, quantiles=3, periods=(5,),
                                                   filter_zscore=None, max_loss=0.1)
    ic = factor_information_coefficient(cleaned)
    if not np.isfinite(ic.to_numpy()).all():
        raise ValueError("factor IC contains nonfinite output")
    volatility = []
    for asset in plan["assets"]:
        returns = 100 * closes[asset].pct_change().dropna().to_numpy()
        native = arch_model(returns, vol="Garch", p=1, q=1, mean="Constant", rescale=False)
        fit = native.fit(disp="off")
        variance = fit.forecast(horizon=5).variance.iloc[-1].to_numpy()
        if fit.convergence_flag or not np.isfinite(variance).all() or (variance <= 0).any():
            raise ValueError("native GARCH failed convergence or variance contract")
        volatility.append({"asset": asset, "convergence_flag": int(fit.convergence_flag),
                           "params": {k: float(v) for k, v in fit.params.items()},
                           "forecast_variance": variance.tolist(), "observations": len(returns)})
    return {"kind": "native_factor_econometric_forecast", "forecasts": rows,
            "factor": {"native_cleaned_rows": len(cleaned), "ic_dates": len(ic),
                       "mean_ic": float(ic["5D"].mean()), "std_ic": float(ic["5D"].std()),
                       "filter_zscore": None, "return_convention": "five-session raw-price, not dividend-inclusive"},
            "arch": volatility, "forecast_inputs": [{k: v for k, v in c.items()
                                                       if k not in {"history", "target"}} for c in cases]}


def models(source, model_cache, kronos_source):
    import numpy as np
    import pandas as pd
    import torch
    from chronos import ChronosBoltPipeline

    torch.set_num_threads(2)
    torch.manual_seed(SEED)
    np.random.seed(SEED)
    plan, _, _, _, data, closes = load_data(source)
    cases = make_folds(closes, plan)
    specs = json.loads((HERE / "plan.json").read_text())
    paths = {}
    for model in specs["model_pins"]:
        paths[model["model"]] = model_cache / ("models--" + model["model"].replace("/", "--")) / "snapshots" / model["sha"]
        if not all((paths[model["model"]] / f).is_file() for f in ("config.json", "model.safetensors")):
            raise FileNotFoundError("pinned public model missing: " + model["model"])
    pipeline = ChronosBoltPipeline.from_pretrained(str(paths["amazon/chronos-bolt-small"]),
                                                  device_map="cpu", torch_dtype=torch.float32,
                                                  local_files_only=True)
    rows = []
    for c in cases:
        begin = time.perf_counter()
        quantiles = pipeline.predict(torch.tensor(c["history"], dtype=torch.float32),
                                     prediction_length=c["gap"] + 5)
        values = quantiles[0, 4].numpy()[c["gap"]:]
        rows.append(forecast_record("chronos-bolt-small", c["fold"], c["asset"], c["target"],
                                    values, c["scale"], time.perf_counter() - begin))
    expected = specs["kronos_source"]["commit"]
    import subprocess
    actual = subprocess.check_output(["git", "-C", str(kronos_source), "rev-parse", "HEAD"], text=True).strip()
    if actual != expected:
        raise ValueError("Kronos source pin changed")
    sys.path.insert(0, str(kronos_source))
    from model import Kronos, KronosPredictor, KronosTokenizer

    tokenizer = KronosTokenizer.from_pretrained(str(paths["NeoQuasar/Kronos-Tokenizer-base"]), local_files_only=True)
    native = Kronos.from_pretrained(str(paths["NeoQuasar/Kronos-small"]), local_files_only=True)
    predictor = KronosPredictor(native, tokenizer, device="cpu", max_context=512)
    for c in cases:
        history_frame = data[c["asset"]].loc[:c["origin"]].iloc[-252:]
        begin = time.perf_counter()
        # The timestamp feature is public calendar information; no future prices
        # enter any model context. Forecast gap days too, then exclude them.
        all_index = closes.index
        origin_pos = all_index.get_loc(pd.Timestamp(c["origin"]))
        future = all_index[origin_pos + 1:origin_pos + 1 + c["gap"] + 5]
        prediction = predictor.predict(df=history_frame.reset_index(drop=True),
                                       x_timestamp=pd.Series(history_frame.index),
                                       y_timestamp=pd.Series(future), pred_len=len(future),
                                       T=1.0, top_p=0.9, sample_count=1, verbose=False)
        rows.append(forecast_record("kronos-small", c["fold"], c["asset"], c["target"],
                                    prediction["close"].to_numpy()[c["gap"]:], c["scale"],
                                    time.perf_counter() - begin))
    return {"kind": "native_pinned_model_forecast", "forecasts": rows,
            "model_input_dates": [{k: v for k, v in c.items() if k not in {"history", "target"}} for c in cases],
            "model_training_contamination": "unknown; historical data predates model releases, so this is not an untouched out-of-sample result"}


def match_forecasts(classical_result, model_result):
    """Refuse incomplete, differently timed or corrupted comparison exports."""
    import numpy as np

    classical = json.loads(classical_result.read_text())["result"]
    models = json.loads(model_result.read_text())["result"]
    raw = classical["forecasts"] + models["forecasts"]
    names = sorted(json.loads((HERE / "plan.json").read_text())["forecast"]["candidates"])
    if {r["model"] for r in raw} != set(names):
        raise ValueError("matched comparison requires every prespecified model")

    def inputs(rows):
        indexed = {(r["fold"], r["asset"]): r for r in rows}
        if len(indexed) != len(rows):
            raise ValueError("duplicate comparison input key")
        return indexed

    common = inputs(classical["forecast_inputs"])
    if not common or common != inputs(models["model_input_dates"]):
        raise ValueError("comparison input chronology, dates or scale differ")
    keyed = {name: {(r["fold"], r["asset"]): r for r in raw if r["model"] == name} for name in names}
    expected = set(common)
    if any(set(v) != expected or len(v) * len(names) != len(raw) for v in keyed.values()):
        raise ValueError("matched comparison requires all prespecified model/asset/fold rows")
    for key in expected:
        observed = keyed["last-close-naive"][key]["observed"]
        if any(v[key]["observed"] != observed for v in keyed.values()):
            raise ValueError("comparison targets differ")
        for name in names:
            row = keyed[name][key]
            if row["training_naive_scale"] != common[key]["scale"]:
                raise ValueError("comparison training scale differs")
            measured = forecast_record(name, *key, row["observed"], row["prediction"],
                                       row["training_naive_scale"], row["elapsed_seconds"])
            if any(not np.isclose(row[k], measured[k], rtol=1e-12, atol=1e-12) for k in ["mae", "mase"]):
                raise ValueError("exported metric differs from native forecast output")
    return names, keyed, expected


def compare(classical_result, model_result):
    import numpy as np
    from arch.bootstrap import StationaryBootstrap

    names, keyed, expected = match_forecasts(classical_result, model_result)
    summary = []
    for name in names:
        values = list(keyed[name].values())
        summary.append({"model": name, "cases": len(values), "mean_mae": float(np.mean([x["mae"] for x in values])),
                        "mean_mase": float(np.mean([x["mase"] for x in values])),
                        "elapsed_seconds": sum(x["elapsed_seconds"] for x in values)})
    paired = []
    folds = sorted({f for f, _ in expected})
    for i, left in enumerate(names):
        for right in names[i + 1:]:
            differences = np.array([np.mean([keyed[left][(fold, a)]["mae"] - keyed[right][(fold, a)]["mae"]
                                             for f, a in expected if f == fold]) for fold in folds])
            bootstrap = StationaryBootstrap(3, differences, seed=SEED)
            interval = bootstrap.conf_int(np.mean, reps=999, method="percentile", size=0.95)
            paired.append({"left": left, "right": right, "mean_mae_difference": float(differences.mean()),
                           "folds": len(folds), "fold_differences": differences.tolist(),
                           "percentile_95_interval": interval[:, 0].tolist(),
                           "multiplicity": "10 descriptive contrasts, no significance or winner-flip rule"})
    return {"kind": "matched_native_forecasts", "summary": summary, "paired_fold_intervals": paired,
            "cash_or_alpha_claim": False, "confirmatory": False,
            "scope": "Three fixed bundled ETFs, first five test closes per fold; model pretraining provenance unknown. Intervals are descriptive and depend on block size."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["chronology", "classical", "models", "compare"])
    parser.add_argument("--lean-source", type=Path)
    parser.add_argument("--model-cache", type=Path)
    parser.add_argument("--kronos-source", type=Path)
    parser.add_argument("--classical-result", type=Path)
    parser.add_argument("--model-result", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    if out.exists() or out.is_relative_to(ROOT):
        raise ValueError("use a fresh lane-owned output directory outside Git")
    os.umask(0o077)
    out.mkdir(parents=True)
    freeze = {"frozen_utc": utc(), "action": args.action, "source_sha256": digest(Path(__file__)),
              "plan_sha256": digest(HERE / "plan.json"), "requirements_sha256": digest(HERE / "requirements.lock"),
              "original_plan_sha256": digest(ROOT / "blueprints/us-equities/research-evaluation/plan.json")}
    write_new(out / "freeze.json", freeze)
    began, start = time.perf_counter(), utc()
    result, failure, status = None, None, "pass"
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        try:
            if args.action == "chronology":
                result = chronology(args.lean_source)
            elif args.action == "classical":
                result = classical(args.lean_source)
            elif args.action == "models":
                result = models(args.lean_source, args.model_cache, args.kronos_source)
            else:
                result = compare(args.classical_result, args.model_result)
        except Exception as error:
            status, failure = "fail", {"type": type(error).__name__, "message": str(error).replace(str(Path.home()), "~"),
                                       "traceback": traceback.format_exc().replace(str(Path.home()), "~")}
    versions = {}
    for package in ("skfolio", "alphalens-reloaded", "arch", "statsmodels", "statsforecast",
                    "chronos-forecasting", "torch", "pandas", "numpy"):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            pass
    receipt = {"schema_version": 1, "evidence_class": "native_proven", "status": status,
               "start_utc": start, "end_utc": utc(), "elapsed_seconds": time.perf_counter() - began,
               "freeze_sha256": digest(out / "freeze.json"), "freeze": freeze,
               "versions": versions, "python": sys.version.split()[0], "result": result, "failure": failure,
               "warnings": sorted(set(str(w.message).replace(str(Path.home()), "~") for w in captured)),
               "scope": "Native upstream API execution with local experiment orchestration; no broker calls, alpha, untouched holdout or account acceptance."}
    write_new(out / "receipt.json", receipt)
    print(json.dumps({"action": args.action, "status": status, "elapsed_seconds": receipt["elapsed_seconds"],
                      "failure": failure["message"] if failure else None}))
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
