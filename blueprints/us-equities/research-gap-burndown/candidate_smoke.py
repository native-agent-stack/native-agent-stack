#!/usr/bin/env python3
"""Run additional vendor-owned interfaces without provider or broker access.

Pins and the source corpus are in plan.json; each invocation has its own freeze,
receipt, exception and output bindings. Imported-only candidates are not credited.
"""
from __future__ import annotations

import argparse
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import traceback

from run import HERE, ROOT, digest, load_data, utc, write_new


def invoke(name, source, out, skill_source=None, model_cache=None):
    import numpy as np
    import pandas as pd

    plan, _, _, _, _, closes = load_data(source)
    # A common training-only prefix; never use the inspected reserved segment.
    history = closes.loc[plan["eligible_start"]:plan["development_end"]].iloc[:252]
    observed = closes.loc[plan["eligible_start"]:plan["development_end"]].iloc[252:257]
    if name == "arcticdb":
        from arcticdb import Arctic
        native = Arctic("lmdb://" + str(out / "lmdb"))
        library = native.create_library("frozen_research")
        library.write("training_closes", history)
        restored = library.read("training_closes").data
        pd.testing.assert_frame_equal(history, restored)
        return {"operation": "native local LMDB write/read exact roundtrip", "rows": len(restored),
                "library": "frozen_research", "no_cloud_or_broker": True}
    if name == "sktime":
        from sktime.forecasting.naive import NaiveForecaster
        native = NaiveForecaster(strategy="last")
        native.fit(pd.Series(history["SPY"].to_numpy(), index=pd.RangeIndex(len(history))))
        forecast = native.predict(fh=[1, 2, 3, 4, 5])
        if not np.all(forecast.to_numpy() == history["SPY"].iloc[-1]):
            raise AssertionError("native naive forecast differs from last close")
        return {"operation": "native fit/predict", "prediction": forecast.tolist(),
                "observed": observed["SPY"].tolist(), "case_scope": "training-only baseline"}
    if name == "tsfresh":
        from tsfresh import extract_features
        from tsfresh.feature_extraction import MinimalFCParameters
        data = pd.DataFrame({"id": np.repeat(np.arange(3), len(history)),
                             "time": list(range(len(history))) * 3,
                             "value": np.concatenate([history[a].to_numpy() for a in plan["assets"]])})
        native = extract_features(data, column_id="id", column_sort="time",
                                  default_fc_parameters=MinimalFCParameters(),
                                  n_jobs=0, disable_progressbar=True)
        if not np.isfinite(native.to_numpy()).all() or len(native) != 3:
            raise ValueError("native feature contract failed")
        return {"operation": "native extract_features", "columns": list(native.columns),
                "rows": len(native), "values": native.to_dict(orient="split")}
    if name == "river":
        from river import linear_model, metrics, preprocessing
        native = preprocessing.StandardScaler() | linear_model.LinearRegression()
        error = metrics.MAE()
        changes = history["SPY"].pct_change().dropna().to_numpy()
        for i in range(1, len(changes)):
            x, y = {"lagged_return": float(changes[i - 1])}, float(changes[i])
            prediction = native.predict_one(x)
            error.update(y, prediction)
            native.learn_one(x, y)
        if not np.isfinite(error.get()):
            raise ValueError("online learner output is nonfinite")
        return {"operation": "native predict-then-learn", "updates": len(changes) - 1,
                "mae": float(error.get()), "chronology": "only previous return predicts next, learn follows prediction"}
    if name == "haystack":
        from haystack import Document
        from haystack.document_stores.in_memory import InMemoryDocumentStore
        from haystack.components.retrievers.in_memory import InMemoryBM25Retriever
        native = InMemoryDocumentStore()
        docs = [Document(content="Synthetic research fixture: label exits after training cutoff; reject leakage."),
                Document(content="Synthetic research fixture: missing filing availability cannot establish point-in-time data.")]
        native.write_documents(docs)
        result = InMemoryBM25Retriever(document_store=native).run(query="label cutoff leakage", top_k=1)
        if not result["documents"] or "leakage" not in result["documents"][0].content:
            raise AssertionError("retrieval control failed")
        return {"operation": "native document write and BM25 retrieval", "documents": len(docs),
                "top_content": result["documents"][0].content, "synthetic": True,
                "scope": "retrieval only; no generation/provider or financial-NLP corpus"}
    if name == "ray":
        import ray
        from ray import serve
        # Ray's Unix sockets need a short path; the vendor accepts _temp_dir.
        with tempfile.TemporaryDirectory(prefix="r-ray-") as temp:
          ray.init(address="local", num_cpus=1, include_dashboard=False, log_to_driver=False,
                   object_store_memory=80 * 1024 * 1024, _temp_dir=temp)
          try:
            @serve.deployment(num_replicas=1, ray_actor_options={"num_cpus": 0.25})
            class ForecastControl:
                def __call__(self, last_close):
                    return [float(last_close)] * 5
            serve.start(http_options={"location": "NoServer"})
            handle = serve.run(ForecastControl.bind(), route_prefix=None)
            prediction = handle.remote(float(history["SPY"].iloc[-1])).result()
            if prediction != [float(history["SPY"].iloc[-1])] * 5:
                raise AssertionError("native served output differs from fixture")
            return {"operation": "native Ray Serve deployment and handle invocation, no HTTP", "prediction": prediction,
                    "synthetic_service": True, "production_serving_acceptance": False}
          finally:
            serve.shutdown()
            ray.shutdown()
    if name == "sentence-transformers":
        import torch
        from sentence_transformers import SentenceTransformer
        torch.set_num_threads(2)
        path = model_cache / "models--sentence-transformers--all-MiniLM-L6-v2" / "snapshots" / "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
        native = SentenceTransformer(str(path), device="cpu", local_files_only=True)
        texts = ["Synthetic fixture: future label exits cannot enter training.",
                 "Synthetic fixture: label information must precede the training cutoff.",
                 "Synthetic fixture: an unrelated pineapple recipe."]
        embeddings = native.encode(texts, normalize_embeddings=True)
        similarities = native.similarity(embeddings, embeddings).numpy()
        if embeddings.shape != (3, 384) or not np.isfinite(embeddings).all():
            raise AssertionError("native embedding output contract failed")
        if similarities[0, 1] <= similarities[0, 2]:
            raise AssertionError("synthetic related/unrelated embedding control failed")
        return {"operation": "native CPU encode/similarity", "shape": list(embeddings.shape),
                "similarities": similarities.tolist(), "synthetic": True,
                "financial_nlp_quality_established": False,
                "model_revision": "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"}
    if name == "timesfm":
        import torch
        from timesfm3 import TimesFM3Evaluator, ModelConfig
        torch.set_num_threads(2)
        path = model_cache / "models--google--timesfm-3.0-pytorch" / "snapshots" / "43046b85ec22d584a13f8098c2ed39c889e129c2"
        native = TimesFM3Evaluator(ModelConfig(checkpoint_path=str(path), per_core_batch_size=1, device="cpu"))
        outputs = list(native.predict_batch([history[a].to_numpy(dtype=np.float32) for a in plan["assets"]],
                      horizon=5, return_quantiles=True, use_symmetric_averaging=False))
        values = [r.forecast.tolist() for r in outputs]
        if len(outputs) != 3 or any(np.asarray(r.forecast).shape != (5,) for r in outputs) or not np.isfinite(values).all():
            raise AssertionError("native TimesFM forecast output contract failed")
        return {"operation": "native CPU predict_batch", "predictions": values,
                "observed": [observed[a].tolist() for a in plan["assets"]],
                "model_revision": "43046b85ec22d584a13f8098c2ed39c889e129c2",
                "scope": "one training prefix/asset, not a matched comparison or untouched OOS result"}
    if name == "qlib":
        # The package's native cross-sectional normalizer is a genuine executed
        # interface, not a claim of full Qlib model/dataset readiness.
        from qlib.data.dataset.processor import CSRankNorm
        index = pd.MultiIndex.from_product([history.index, plan["assets"]], names=["datetime", "instrument"])
        data = pd.DataFrame({("feature", "close"): history.to_numpy().reshape(-1)}, index=index)
        result = CSRankNorm(fields_group="feature")(data.copy())
        if result.shape != data.shape or not np.isfinite(result.to_numpy()).all():
            raise AssertionError("native Qlib processor contract failed")
        return {"operation": "native CSRankNorm processor", "rows": len(result),
                "columns": [list(c) for c in result.columns], "first_values": result.iloc[:3, 0].tolist(),
                "full_factor_model_pipeline": False}
    if name == "docling":
        from docling.document_converter import DocumentConverter
        from docling.datamodel.base_models import InputFormat
        page = out / "synthetic.html"
        page.write_text("<html><body><h1>Synthetic research fixture</h1><p>Label availability must precede selection.</p></body></html>")
        result = DocumentConverter(allowed_formats=[InputFormat.HTML]).convert(page)
        text = result.document.export_to_markdown()
        if "Label availability" not in text:
            raise AssertionError("native conversion lost the fixture")
        return {"operation": "native HTML conversion/export", "markdown": text,
                "synthetic": True, "historical_filing_corpus_acceptance": False}
    if name == "claude-trading-skills":
        expected = json.loads((HERE / "plan.json").read_text())["skill_source"]["commit"]
        actual = subprocess.check_output(["git", "-C", str(skill_source), "rev-parse", "HEAD"], text=True).strip()
        if expected != actual:
            raise ValueError("upstream skill source changed")
        script = skill_source / "skills/backtest-expert/scripts/evaluate_backtest.py"
        cases = [
            ("clean-metrics-control", ["--total-trades", "250", "--win-rate", "60", "--avg-win-pct", "2",
                                      "--avg-loss-pct", "1", "--max-drawdown-pct", "8", "--years-tested", "10",
                                      "--num-parameters", "3", "--slippage-tested"]),
            ("thin-overfit-no-slippage", ["--total-trades", "12", "--win-rate", "60", "--avg-win-pct", "2",
                                         "--avg-loss-pct", "1", "--max-drawdown-pct", "30", "--years-tested", "1",
                                         "--num-parameters", "9"]),
            ("invalid-summary-refusal", ["--total-trades", "-1", "--win-rate", "101", "--avg-win-pct", "2",
                                         "--avg-loss-pct", "1", "--max-drawdown-pct", "8", "--years-tested", "10",
                                         "--num-parameters", "3"])]
        rows = []
        for label, argv in cases:
            directory = out / label
            cmd = [sys.executable, str(script), *argv, "--output-dir", str(directory)]
            run = subprocess.run(cmd, capture_output=True, text=True)
            emitted = [json.loads(p.read_text()) for p in directory.glob("*.json")]
            rows.append({"fixture": label, "argv": argv, "exit_code": run.returncode,
                         "stdout": run.stdout.replace(str(Path.home()), "~"),
                         "stderr": run.stderr.replace(str(Path.home()), "~"), "results": emitted})
        if rows[0]["exit_code"] or rows[1]["exit_code"] or not rows[2]["exit_code"]:
            raise AssertionError("native skill control/refusal outcomes changed")
        if len(rows[0]["results"]) != 1 or len(rows[1]["results"]) != 1:
            raise AssertionError("native CLI did not emit its result document")
        clean, defect = rows[0]["results"][0], rows[1]["results"][0]
        flags = {f["id"] for f in defect["red_flags"]}
        if clean["red_flags"] or not {"small_sample", "no_slippage_test", "over_optimized", "short_test_period"}.issubset(flags):
            raise AssertionError("summary defect/clean controls did not discriminate")
        if clean["total_score"] <= defect["total_score"]:
            raise AssertionError("seeded summary defects did not reduce the native score")
        return {"operation": "vendor's supported quantitative backtest-expert CLI", "cases": rows,
                "upstream_source_sha256": digest(script),
                "found_defects": "small sample, short duration, overfitting and missing slippage are summary-level checks",
                "vendor_scores": {"clean": clean["total_score"], "defect": defect["total_score"]},
                "promotion_authority": False,
                "missed_defects": "CLI takes aggregate metrics, not label timestamps. Latent look-ahead can produce identical input metrics; this execution cannot verify causality or an LLM skill review."}
    raise ValueError("unsupported candidate " + name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate")
    parser.add_argument("--lean-source", type=Path, required=True)
    parser.add_argument("--skill-source", type=Path)
    parser.add_argument("--model-cache", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists() or args.out.resolve().is_relative_to(ROOT):
        raise ValueError("use a fresh private output path outside the worktree")
    args.out.mkdir(parents=True, mode=0o700)
    write_new(args.out / "freeze.json", {"at": utc(), "source_sha256": digest(Path(__file__)),
                                       "plan_sha256": digest(HERE / "plan.json"), "candidate": args.candidate})
    start, began = utc(), time.perf_counter()
    result, error = None, None
    try:
        result = invoke(args.candidate, args.lean_source, args.out, args.skill_source, args.model_cache)
    except Exception as e:
        error = {"type": type(e).__name__, "message": str(e).replace(str(Path.home()), "~"),
                 "traceback": traceback.format_exc().replace(str(Path.home()), "~")}
    packages = {"arcticdb": "arcticdb", "sktime": "sktime", "tsfresh": "tsfresh", "river": "river",
                "haystack": "haystack-ai", "ray": "ray", "qlib": "pyqlib", "docling": "docling-slim",
                "timesfm": "timesfm", "sentence-transformers": "sentence-transformers"}
    version = importlib.metadata.version(packages[args.candidate]) if args.candidate in packages else None
    receipt = {"schema_version": 1, "evidence_class": "native_proven", "candidate": args.candidate,
               "version": version, "start_utc": start, "end_utc": utc(), "elapsed_seconds": time.perf_counter() - began,
               "status": "fail" if error else "pass", "result": result, "failure": error,
               "freeze_sha256": digest(args.out / "freeze.json"), "scope": "Exact native API/CLI execution; no credentials, broker, cloud/provider or predictive superiority qualification."}
    write_new(args.out / "receipt.json", receipt)
    print(json.dumps({"candidate": args.candidate, "status": receipt["status"], "error": error["message"] if error else None}))
    return 1 if error else 0


if __name__ == "__main__":
    raise SystemExit(main())
