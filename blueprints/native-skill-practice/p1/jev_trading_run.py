"""Offline SYN runner and credential-runner integration for the frozen Jev study.

The executable exposes build and SYN only. An owning runner may call run() with
TypeSafeHTTP and a complete scored attestation after two-family review. BUILD
never constructs that transport. HTTP shape: retained docs.typesafe.ai/api.md,
2026-10-11 capture sha256 6b760275f89341fe15cff80c28aacae94d7d0c0c99afcd987ec0bca680b5713a.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
import json
import math
import os
from pathlib import Path
import re
import time

import numpy as np
from scipy import stats

from jev_trading_cases import (LABELS, SEED, SOURCE_PINS, ID_PINS, Case, assemble, build_frozen_sets,
                               id_hash, json_bytes, option_order, require_dependencies, sha256, verify_content, verify_lists)
from jev_trading_canaries import freeze_dates, shift_dates
from jev_trading_baselines import PINS, HaikuBudget, clm_status, pending_rules_status
from jev_trading_custody import ADDENDUM_REFERENCE, SDK_VERSION, require_credential_run, verify_attestation
from jev_trading_budget import JevBudget
from jev_trading_scoring import MODELS, BASELINES, arm_metrics, paired_metrics, beats, harness_beats, prediction

SDK_TRANSPORT_SOURCE = Path(__file__).resolve().parents[3] / "tools/sota-convergence/gap_crosswalk.py"
PROMPTS = {"FPB-50": "Classify the financial sentiment expressed by this sentence.",
           "TFN": "Classify the market sentiment expressed by this financial news text.",
           "FOMC": "Classify the monetary policy stance expressed by this Federal Reserve text."}
PRICE_PER_TOKEN = Decimal("0.042") / 1000000


def wire_bytes(value) -> bytes:
    # Dict insertion order is the preregistered Choice option order. Do not sort.
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def jev_request(name: str, row: Case, model: str) -> dict:
    if model not in MODELS:
        raise ValueError("versioned Jev model required")
    return {"state": row.text, "model": model, "questions": {"label": {"type": "choice",
        "instructions": PROMPTS[name], "criteria": {label: None for label in option_order(name, row.id)}}}}


def parse_response(response, model, name):
    if not isinstance(response, dict):
        return None, "MALFORMED"
    if response.get("model") != model:
        return None, "MODEL_MISMATCH"
    try:
        answer = response["answers"]["label"]
        if answer["type"] != "choice":
            return None, "REFUSED"
        result = prediction(answer["probabilities"], LABELS[name], answer["choice"])
        if type(response["usage"]["input_tokens"]) is not int or response["usage"]["input_tokens"] < 0:
            return None, "MALFORMED"
        return result, "VALID"
    except (KeyError, ValueError, TypeError):
        return None, "MALFORMED"


class FakeTransport:
    """Deterministic fixture responses; no credentials, sockets or SDK clients."""
    is_fake = True

    def __init__(self):
        self.calls = []

    def evaluate(self, request):
        self.calls.append(request)
        labels = list(request["questions"]["label"]["criteria"])
        chosen = labels[int(sha256(wire_bytes(request))[:8], 16) % len(labels)]
        probabilities = {label: 0.8 if label == chosen else 0.1 for label in labels}
        return {"model": request["model"], "answers": {"label": {"type": "choice", "choice": chosen,
                "probabilities": probabilities, "confidence": 0.7}},
                "usage": {"input_tokens": 40 + len(request["state"].split()), "output_tokens": 12}}


def _native_sdk_call(request):
    """Reuse the adopted native SDK transport and its 429/529 policy unchanged."""
    require_credential_run()
    import importlib.util
    spec = importlib.util.spec_from_file_location("jev_pinned_sdk_transport", SDK_TRANSPORT_SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.call(request, os.environ["TYPESAFE_API_KEY"])


class TypeSafeSDK:
    """Pinned typesafe-sdk 0.7.2 through the existing public SDK transport seam."""
    is_fake = False
    max_attempts = 5

    def prepare(self):
        from importlib.metadata import version, PackageNotFoundError
        try:
            installed = version("typesafe-sdk")
        except PackageNotFoundError:
            raise ValueError("typesafe-sdk==0.7.2 is required before a scored start") from None
        if installed != SDK_VERSION:
            raise ValueError("typesafe-sdk pin mismatch")

    def evaluate(self, request):
        if request.get("model") not in MODELS:
            raise ValueError("versioned Jev model required")
        require_credential_run()
        response, _request_id, _exchange_seconds, retries = _native_sdk_call(request)
        if type(retries) is not int or not 0 <= retries < self.max_attempts:
            raise ValueError("invalid native SDK retry metadata")
        return {**response, "_sdk_retry_count": retries}


def latency_sample(pack, *, synthetic=False):
    ids = sorted(r.id for r in pack.scored)
    size = min(300, len(ids)) if synthetic else 300
    if len(ids) < size:
        raise ValueError("latency sample requires 300 rows")
    positions = np.random.default_rng(SEED).choice(len(ids), size=size, replace=False)
    return [ids[int(i)] for i in positions]


def latency_report(milliseconds):
    if not milliseconds:
        return {"status": "NOT_RUN", "n": 0}
    values = np.asarray(milliseconds, dtype=float)
    if not np.isfinite(values).all() or (values < 0).any():
        raise ValueError("invalid call latency")
    result = {"status": "RAN", "n": len(values), "unit": "calls", "milliseconds": {}}
    for label, q in (("p50", 0.50), ("p95", 0.95), ("p99", 0.99)):
        def statistic(sample, axis=-1):
            return np.take(np.sort(sample, axis=axis), math.ceil(sample.shape[axis] * q) - 1, axis=axis)
        interval = stats.bootstrap((values,), statistic, paired=True, vectorized=True, batch=32,
            method="percentile", n_resamples=10000, confidence_level=0.95,
            rng=np.random.default_rng(SEED)).confidence_interval if len(values) >= 2 else None
        result["milliseconds"][label] = {"point": float(statistic(values)),
            "low": float(interval.low) if interval is not None else None,
            "high": float(interval.high) if interval is not None else None}
    return result


def synthetic_sets():
    """Nine invented rows per set; these never claim the frozen public hashes."""
    return {name: assemble(name,
        [Case(i, f"Synthetic training bulletin {i}.", label) for i, label in enumerate(labels * 3)],
        [Case(i, f"Synthetic scored bulletin {i}." + (" Jan. 5 2008" if i == 0 and name != "FOMC" else ""), label)
         for i, label in enumerate(labels * 3)]) for name, labels in LABELS.items()}


def _digest(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _code_hashes():
    root = Path(__file__).parent
    names = ["jev_trading_cases.py", "jev_trading_canaries.py", "jev_trading_scoring.py",
             "jev_trading_baselines.py", "jev_trading_budget.py", "jev_trading_custody.py", "jev_trading_run.py", "p1_scoring.py", "requirements-scoring.lock"]
    return {**{name: sha256((root / name).read_bytes()) for name in names},
            "tools/sota-convergence/gap_crosswalk.py": sha256(SDK_TRANSPORT_SOURCE.read_bytes())}


def preregistration(packs, evidence_class, transport, baseline_meta, attestation=None):
    dependencies = require_dependencies()
    if set(packs) != set(LABELS) or evidence_class not in {"SYN", "SCORED"}:
        raise ValueError("three static sets and explicit evidence class required")
    if (evidence_class == "SYN") != (getattr(transport, "is_fake", None) is True):
        raise ValueError("SYN requires a fake transport; SCORED forbids it")
    public_attestation = None
    if evidence_class == "SCORED":
        for name, pack in packs.items():
            verify_lists(pack, ID_PINS[name])
            verify_content(pack)
        public_attestation = verify_attestation(attestation)
    metadata = {}
    for name in packs:
        metadata[name] = {}
        for arm in BASELINES[name]:
            row = baseline_meta.get(name, {}).get(arm, {"status": "NOT_RUN", "reason": "adapter not supplied"})
            if row["status"] == "RAN":
                if row.get("pin") != PINS[arm]:
                    raise ValueError("baseline pin mismatch")
                if evidence_class == "SCORED" and arm == "nemotron" and not _digest(row.get("head_sha256")):
                    raise ValueError("fitted head hash required before scoring")
                if arm == "haiku":
                    HaikuBudget(row.get("gate", {}))
                if arm == "clm-8b" and clm_status(row.get("gpu_window_sha256"))["status"] != "READY":
                    raise ValueError("CLM requires its GPU batch window")
            elif row["status"] != "NOT_RUN" or not row.get("reason"):
                raise ValueError("explicit baseline status/reason required")
            metadata[name][arm] = row
    return {"schema_version": 1, "kind": "preregistration", "evidence_class": evidence_class,
        "models": list(MODELS), "dependencies": dependencies, "seed": SEED, "code_sha256": _code_hashes(),
        "addendum_record": ADDENDUM_REFERENCE, "attestation": public_attestation,
        "case_sets": {name: pack.manifest() for name, pack in packs.items()},
        "date_shift": {name: freeze_dates(pack, frozen=evidence_class == "SCORED") for name, pack in packs.items()},
        "prompt_sha256": {name: sha256(text.encode()) for name, text in PROMPTS.items()},
        "request_shape": "TypeSafe SDK Choice; state/model/questions; SDK-native headers, no danger-zone overrides",
        "latency_sample_ids": {name: latency_sample(pack, synthetic=evidence_class == "SYN") for name, pack in packs.items()},
        "option_order": "ascending SHA256(20261011:<set>:<id>:<label>)",
        "bootstrap": {"paired": True, "method": "percentile", "n_resamples": 10000, "confidence_level": 0.95, "seed": SEED},
        "audits": {"k": 10, "n": 281, "seed": SEED, "status": "NOT_RUN", "auditor": None,
                   "reason": "no separately frozen auditor, candidate rule, parameters or prompt"},
        "entity_mask": {"status": "NOT_RUN", "specification_sha256": None, "code_sha256": None,
                        "reason": "masker specification and code not frozen"},
        "baselines": metadata, "pending_sets": {"SEC-8K": pending_rules_status(),
            "openFDA": {"status": "NOT_RUN", "reason": "no acquisition receipt and reconstructed availability clock"}},
        "run_order": ["FPB-50", "TFN", "FOMC"], "condition_order": ["raw", "date_shift", "latency"],
        "cost_bounds_usd": {"per_model": "0.386568", "both_models": "0.773136", "input_tokens_per_call_assumption": 1000}}


def _write_new(path, value):
    data = json_bytes(value) + b"\n"
    with path.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    return sha256(data)


def validate_receipt(receipt):
    required = {"schema_version", "kind", "evidence_class", "status", "command", "exit_code", "input_sha256", "output_sha256"}
    if not required <= receipt.keys() or receipt["schema_version"] != 1 or receipt["kind"] != "run":
        raise ValueError("invalid receipt schema")
    if receipt["evidence_class"] not in {"SYN", "SCORED"} or receipt["status"] not in {"COMPLETE", "COMPLETE_WITH_FAILURES", "FAILED", "PARTIAL"}:
        raise ValueError("invalid receipt state")
    if type(receipt["exit_code"]) is not int or not isinstance(receipt["command"], list) or not receipt["command"]:
        raise ValueError("invalid receipt command/exit code")
    for key in ("input_sha256", "output_sha256"):
        if not isinstance(receipt[key], dict) or not all(_digest(v) for v in receipt[key].values()):
            raise ValueError("invalid receipt hashes")


def _masked_response(response, name):
    """Retain typed response fields; arbitrary error/refusal text is not a log."""
    if not isinstance(response, dict):
        return {"malformed": True}
    answer = response.get("answers", {}).get("label", {}) if isinstance(response.get("answers"), dict) else {}
    if not isinstance(answer, dict):
        answer = {}
    proba = answer.get("probabilities", {})
    proba = proba if isinstance(proba, dict) else {}
    usage = response.get("usage", {})
    usage = usage if isinstance(usage, dict) else {}
    model = response.get("model")
    return {"model": model if isinstance(model, str) and re.fullmatch(r"jev-\d+\.\d+\.\d+", model) else "OTHER_OR_MISSING",
        "answers": {"label": {"type": "choice" if answer.get("type") == "choice" else "OTHER_OR_MISSING",
            "choice": answer.get("choice") if answer.get("choice") in LABELS[name] else "OTHER_OR_MISSING",
            "probabilities": {label: proba[label] if type(proba.get(label)) in (int, float) and math.isfinite(proba[label]) else None
                              for label in LABELS[name]}}},
        "usage": {key: usage.get(key) if type(usage.get(key)) is int and usage[key] >= 0 else None
                  for key in ("input_tokens", "output_tokens")}}


def _date_report(pack, raw, shifted, subset):
    if not subset:
        return {"status": "NOT_RUN", "reason": "frozen expression selects no rows", "n": 0}
    by_id = {r.id: r for r in pack.scored}
    shared = [i for i in subset if raw.get(i) is not None and shifted.get(i) is not None]
    return {"status": "COUNTS_ONLY", "n": len(subset), "valid_pairs": len(shared),
        "label_flips": sum(raw[i].label != shifted[i].label for i in shared),
        "correct_before": sum(raw[i].label == by_id[i].label for i in shared),
        "correct_after": sum(shifted[i].label == by_id[i].label for i in shared),
        "audit": "NO_VERDICT: static subsets have fewer than 281 items", "interval": None, "pass_fail": None}


def run(packs, output_dir: Path, transport, *, evidence_class, command, baseline_adapters=None,
        baseline_meta=None, attestation=None):
    """One new directory per attempt. Failures never overwrite prior receipts.

    An adapter maps (set_name, Case) to a Prediction; training/freeze precede run.
    Haiku's owning-workload adapter additionally supplies token_bound(name,row)
    and returns {probabilities, choice, input_tokens, output_tokens}. The runner
    checks/reserves its cap and retains normalized outputs. No Haiku key is read.
    """
    if evidence_class == "SCORED":
        # This refusal precedes directory/receipt creation and is never turned
        # into per-row failures. An owning runner receives a non-zero exit.
        require_credential_run()
        transport.prepare()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    output_hashes = {}
    input_hashes = _code_hashes()
    attempted = 0
    failures = Counter()
    status, exit_code, error_class = "FAILED", 1, None
    baseline_adapters = baseline_adapters or {}
    baseline_meta = baseline_meta or {}
    jev_budget = None
    # Available to the final receipt even when preregistration fails. Configure
    # only after validating the frozen workload, before any dispatch.
    haiku_budget = None
    try:
        for name, entries in baseline_meta.items():
            for arm, metadata in entries.items():
                if metadata.get("status") == "RAN" and (arm not in baseline_adapters or
                        (arm == "haiku" and not callable(getattr(baseline_adapters[arm], "token_bound", None)))):
                    raise ValueError("baseline adapter missing before first call")
        registration = preregistration(packs, evidence_class, transport, baseline_meta, attestation)
        planned = sum(len(pack.scored) + len(registration["date_shift"][name]["ids"]) +
                      len(registration["latency_sample_ids"][name]) for name, pack in packs.items())
        jev_budget = JevBudget({model: planned for model in MODELS},
                               max_attempts=1 if evidence_class == "SYN" else transport.max_attempts)
        registration["jev_budget"] = {"planned_calls_per_model": planned, "max_attempts": jev_budget.max_attempts,
            "planning_input_tokens_per_call": 1000, "reserved_input_tokens_per_attempt": 65536,
            "unknown_charge_policy": "retain the per-attempt reserve until the owning ledger resolves it",
            "stop_policy": "sticky cap stop; returned usage above the planning bound stops that model"}
        output_hashes["preregistration.json"] = _write_new(output_dir / "preregistration.json", registration)
        input_hashes["preregistration.json"] = output_hashes["preregistration.json"]
        all_raw = {model: {} for model in MODELS}
        report = {"evidence_class": evidence_class, "models": {m: {} for m in MODELS}, "model_parity": {},
                  "pending_sets": registration["pending_sets"], "baseline_metrics": {}}
        haiku_configs = [metadata["gate"] for rows in registration["baselines"].values()
                        for arm, metadata in rows.items() if arm == "haiku" and metadata["status"] == "RAN"]
        if haiku_configs and any(config != haiku_configs[0] for config in haiku_configs):
            raise ValueError("Haiku workload and cap must be shared across sets")
        haiku_order = [name + "/" + condition for name in registration["run_order"]
            if registration["baselines"][name]["haiku"]["status"] == "RAN"
            for condition in (["raw", "date_shift"] if registration["date_shift"][name]["ids"] else ["raw"])]
        if haiku_configs and haiku_configs[0]["run_order"] != haiku_order:
            raise ValueError("Haiku declared order does not match the frozen run order")
        haiku_budget = HaikuBudget(haiku_configs[0]) if haiku_configs else None
        with (output_dir / "calls.jsonl").open("xb") as log:
            for name in registration["run_order"]:
                pack = packs[name]
                rows = {r.id: r for r in pack.scored}
                subset = registration["date_shift"][name]["ids"]
                for model in MODELS:
                    raw, shifted, latency, tokens = {}, {}, [], []
                    unresolved_retries = 0
                    schedule = [("raw", r.id) for r in pack.scored]
                    schedule += [("date_shift", i) for i in subset]
                    schedule += [("latency", i) for i in registration["latency_sample_ids"][name]]
                    for condition, item_id in schedule:
                        if sha256((output_dir / "preregistration.json").read_bytes()) != input_hashes["preregistration.json"]:
                            raise ValueError("preregistration changed after freeze")
                        original = rows[item_id]
                        row = Case(item_id, shift_dates(original.text)["text"], original.label) if condition == "date_shift" else original
                        request = jev_request(name, row, model)
                        response = None
                        elapsed = None
                        dispatched = jev_budget.reserve(model)
                        if not dispatched:
                            parsed, outcome = None, "CAP_STOP"
                        else:
                            attempted += 1
                            started = time.perf_counter()
                            try:
                                response = transport.evaluate(request)
                                parsed, outcome = parse_response(response, model, name)
                            except Exception as exc:
                                parsed, outcome = None, "TRANSPORT_ERROR_" + type(exc).__name__
                            elapsed = (time.perf_counter() - started) * 1000
                            if evidence_class == "SYN":
                                elapsed = 1 + int(sha256(wire_bytes(request))[:4], 16) % 100 / 100
                        masked = _masked_response(response, name)
                        count = masked.get("usage", {}).get("input_tokens")
                        if dispatched:
                            retries = response.get("_sdk_retry_count", 0) if isinstance(response, dict) else None
                            if type(retries) is int and 0 < retries < jev_budget.max_attempts:
                                unresolved_retries += retries
                            budget_outcome = jev_budget.record(model, count, retries)
                            if budget_outcome != "VALID":
                                parsed = None
                                if budget_outcome == "TOKEN_BOUND_STOP" or outcome == "VALID":
                                    outcome = budget_outcome
                            tokens.append(count if budget_outcome != "UNKNOWN_USAGE" and jev_budget.bounded[model] else None)
                        if parsed is None:
                            failures[f"{name}/{model}/{condition}/{outcome}"] += 1
                        if condition == "raw":
                            raw[item_id] = parsed
                        elif condition == "date_shift":
                            shifted[item_id] = parsed
                        elif dispatched:
                            latency.append(elapsed)
                        record = {"set": name, "model": model, "condition": condition, "id": item_id,
                            "request": request, "request_wire": wire_bytes(request).decode(),
                            "request_sha256": sha256(wire_bytes(request)),
                            "response": masked, "response_sha256": sha256(json_bytes(masked)),
                            "outcome": outcome, "latency_ms": elapsed}
                        log.write(json_bytes(record) + b"\n")
                        log.flush()
                    all_raw[model][name] = raw
                    report["models"][model][name] = {"metrics": arm_metrics(pack, raw),
                        "canaries": {"date_shift": _date_report(pack, raw, shifted, subset),
                            "entity_mask": {"status": "NOT_APPLIED" if name == "FOMC" else "NOT_RUN",
                                            "reason": "no issuer to hide" if name == "FOMC" else "masker and auditor not frozen"}},
                        "latency": latency_report(latency),
                        "cost": {"known_input_tokens": sum(t for t in tokens if t is not None),
                            "usage_complete": all(t is not None for t in tokens) and not unresolved_retries,
                            "unresolved_retry_attempts": unresolved_retries,
                            "usd": str(sum(t for t in tokens if t is not None) * PRICE_PER_TOKEN) if all(t is not None for t in tokens) and not unresolved_retries else None,
                            "known_usd": str(sum(t for t in tokens if t is not None) * PRICE_PER_TOKEN),
                            "synthetic": evidence_class == "SYN"}}
                report["baseline_metrics"][name] = {}
                baseline_outputs = {}
                for baseline, metadata in registration["baselines"][name].items():
                    if metadata["status"] == "NOT_RUN":
                        report["baseline_metrics"][name][baseline] = metadata
                        continue
                    adapter = baseline_adapters[baseline]
                    def invoke_baseline(row, condition):
                        nonlocal attempted
                        if sha256((output_dir / "preregistration.json").read_bytes()) != input_hashes["preregistration.json"]:
                            raise ValueError("preregistration changed after freeze")
                        outcome, value, usage = "VALID", None, None
                        try:
                            if baseline == "haiku" and not haiku_budget.reserve(adapter.token_bound(name, row)):
                                outcome = "CAP_STOP"
                            else:
                                attempted += 1
                                answer = adapter(name, row)
                                if baseline == "haiku":
                                    usage = _masked_response({"usage": answer}, name)["usage"]
                                    haiku_budget.record(answer["input_tokens"], answer["output_tokens"])
                                    value = prediction(answer["probabilities"], LABELS[name], answer["choice"])
                                else:
                                    value = prediction(answer.probabilities, LABELS[name], answer.label)
                        except Exception as exc:
                            if baseline == "haiku":
                                haiku_budget.unknown()
                            outcome = "BASELINE_ERROR_" + type(exc).__name__
                        if value is None:
                            failures[f"{name}/{baseline}/{condition}/{outcome}"] += 1
                        answer_record = {"choice": value.label, "probabilities": value.probabilities} if value else None
                        log.write(json_bytes({"set": name, "model": baseline, "condition": condition, "id": row.id,
                            "text_sha256": sha256(row.text.encode()), "response": answer_record,
                            "response_sha256": sha256(json_bytes(answer_record)), "outcome": outcome, "usage": usage}) + b"\n")
                        log.flush()
                        return value
                    baseline_outputs[baseline] = {r.id: invoke_baseline(r, "raw") for r in pack.scored}
                    shifted_base = {i: invoke_baseline(Case(i, shift_dates(rows[i].text)["text"], rows[i].label), "date_shift") for i in subset}
                    report["baseline_metrics"][name][baseline] = {"status": "RAN", "pin": PINS[baseline],
                        "contaminated": baseline == "finbert" and name == "FPB-50",
                        "metrics": arm_metrics(pack, baseline_outputs[baseline], ordered_options=baseline in ("clm-8b", "haiku")),
                        "canaries": {"date_shift": _date_report(pack, baseline_outputs[baseline], shifted_base, subset),
                                     "entity_mask": {"status": "NOT_APPLIED" if name == "FOMC" else "NOT_RUN"}}}
                for model in MODELS:
                    result = report["models"][model][name]
                    result["pairs"] = {b: paired_metrics(pack, all_raw[model][name], baseline_outputs[b])
                        if b in baseline_outputs else registration["baselines"][name][b] for b in BASELINES[name]}
                    for baseline, pair in result["pairs"].items():
                        if pair["status"] != "NOT_RUN":
                            pair["calibration_rankable"] = (not result["metrics"]["incomplete"] and
                                not report["baseline_metrics"][name][baseline]["metrics"]["incomplete"])
                        if baseline == "haiku":
                            pair["probability_comparison"] = "self-reported vs returned probabilities"
                    result["beats"] = beats(model, name, result["metrics"]["incomplete"], result["pairs"], result["canaries"])
                report["model_parity"][name] = {**paired_metrics(pack, all_raw[MODELS[0]][name], all_raw[MODELS[1]][name]),
                                               "reported_only": True, "first": MODELS[0], "second": MODELS[1]}
        report["harness_beats"] = {m: harness_beats({n: report["models"][m][n]["beats"] for n in packs}) for m in MODELS}
        report["failure_counts"] = dict(failures)
        report["jev_spend"] = jev_budget.snapshot()
        report["haiku_spend"] = haiku_budget.snapshot() if haiku_budget else {"status": "NOT_RUN"}
        output_hashes["report.json"] = _write_new(output_dir / "report.json", report)
        status, exit_code = ("COMPLETE_WITH_FAILURES" if failures else "COMPLETE"), 0
    except BaseException as exc:
        status = "PARTIAL" if attempted else "FAILED"
        error_class = type(exc).__name__
    finally:
        for path in output_dir.iterdir():
            if path.is_file():
                output_hashes[path.name] = sha256(path.read_bytes())
        receipt = {"schema_version": 1, "kind": "run", "evidence_class": evidence_class,
            "status": status, "exit_code": exit_code, "command": list(command),
            "input_sha256": input_hashes, "output_sha256": output_hashes,
            "attempted_calls": attempted, "failure_counts": dict(failures), "error_class": error_class,
            "jev_spend": jev_budget.snapshot() if jev_budget else None,
            "haiku_spend": haiku_budget.snapshot() if haiku_budget else {"status": "NOT_RUN"},
            "created_at": datetime.now(timezone.utc).isoformat(), "network_transport": "FAKE" if evidence_class == "SYN" else "TypeSafe SDK 0.7.2"}
        validate_receipt(receipt)
        _write_new(output_dir / "receipt.json", receipt)
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("build", "syn"))
    parser.add_argument("--sources", type=Path, help="JSON map of role to {path, sha256}; no acquisition")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.action == "build":
        if args.sources is None:
            parser.error("build requires --sources")
        packs = build_frozen_sets(json.loads(args.sources.read_text()))
        result = {name: {**pack.manifest(), "date_shift": freeze_dates(pack, frozen=True)} for name, pack in packs.items()}
        _write_new(args.out, result)
        print("Frozen lists verified; wrote " + str(args.out))
        return 0
    packs = synthetic_sets()
    def fake_baseline(name, row):
        labels = LABELS[name]
        chosen = labels[row.id % 3]
        return prediction({label: 0.7 if label == chosen else 0.15 for label in labels}, labels)
    adapters = {"finbert": fake_baseline, "nemotron": fake_baseline}
    meta = {name: {b: {"status": "RAN", "pin": PINS[b], "synthetic": True} for b in adapters if b in BASELINES[name]} for name in packs}
    receipt = run(packs, args.out, FakeTransport(), evidence_class="SYN", command=["jev_trading_run.py", "syn", "--out", str(args.out)],
                  baseline_adapters=adapters, baseline_meta=meta)
    print(json.dumps({"receipt": str(args.out / "receipt.json"), "status": receipt["status"], "exit_code": receipt["exit_code"]}))
    return receipt["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
