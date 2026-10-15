"""Decision 6 statistics and ADDENDUM-01 A3, without model or network calls.

Point metrics use sklearn 1.9.1. Cluster resampling uses scipy 1.18.1's
stats.bootstrap and the sufficient statistics in sklearn's _classification.py
precision_recall_fscore_support / brier_score_loss. ECE follows P1 (15 bins),
but bins max(probabilities), never the API confidence field.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np
from scipy import stats
from sklearn.metrics import brier_score_loss, f1_score

from jev_trading_cases import LABELS, SEED, CaseSet, clusters, option_order
from p1_scoring import expected_calibration_error, mcnemar_exact, wilson_interval

MODELS = ("jev-1.14.0", "jev-1.13.0")
BASELINES = {"FPB-50": ("finbert", "nemotron", "clm-8b", "haiku"),
             "TFN": ("finbert", "nemotron", "clm-8b", "haiku"),
             "FOMC": ("nemotron", "clm-8b", "haiku")}


@dataclass(frozen=True)
class Prediction:
    label: str
    probabilities: dict[str, float]


def prediction(probabilities: dict, labels, choice: str | None = None) -> Prediction:
    labels = sorted(labels)
    if not isinstance(probabilities, dict) or set(probabilities) != set(labels):
        raise ValueError("probability labels mismatch")
    values = list(probabilities.values())
    if any(type(p) not in (int, float) or not math.isfinite(p) or not 0 <= p <= 1 for p in values):
        raise ValueError("invalid probability")
    if abs(sum(values) - 1.0) > 1e-6:
        raise ValueError("probabilities do not sum to one")
    best = max(labels, key=probabilities.__getitem__)
    if choice is not None and (choice not in labels or probabilities[choice] != probabilities[best]):
        raise ValueError("choice is not a maximum-probability label")
    return Prediction(choice if choice is not None else best, dict(probabilities))


def _metrics(truth, answers, labels) -> dict:
    if not len(truth):
        return {"macro_f1": None, "brier": None, "ece": None}
    labels = sorted(labels)
    proba = np.array([[a.probabilities[l] for l in labels] for a in answers])
    predicted = [a.label for a in answers]
    return {"macro_f1": float(f1_score(truth, predicted, labels=list(labels), average="macro", zero_division=0)),
            "brier": float(brier_score_loss(truth, proba, labels=list(labels), scale_by_half=False)),
            "ece": expected_calibration_error(proba.max(axis=1), np.array(labels)[proba.argmax(axis=1)] == np.asarray(truth))["ece"]}


def _wilson(successes: int, n: int):
    return list(wilson_interval(successes, n)) if n else None


def arm_metrics(pack: CaseSet, outputs: dict[int, Prediction | None], *, ordered_options=True) -> dict:
    labels = LABELS[pack.name]
    valid = [r for r in pack.scored if outputs.get(r.id) is not None]
    n = len(pack.scored)
    if not n:
        raise ValueError("empty scored population")
    failures = n - len(valid)
    representatives = [g[0] for g in clusters(pack.scored)]
    valid_reps = [i for i in representatives if outputs.get(i) is not None]
    uniform = prediction({label: 1 / len(labels) for label in labels}, labels)
    own = _metrics([r.label for r in valid], [outputs[r.id] for r in valid], labels)
    own["macro_f1"] = float(f1_score([r.label for r in pack.scored],
        [outputs[r.id].label if outputs.get(r.id) is not None else "__MISSING__" for r in pack.scored],
        labels=list(labels), average="macro", zero_division=0))
    sensitivity = _metrics([r.label for r in pack.scored],
                           [outputs.get(r.id) or uniform for r in pack.scored], labels)
    first = sum(outputs[r.id].label == option_order(pack.name, r.id)[0] for r in valid)
    first_reps = sum(outputs[i].label == option_order(pack.name, i)[0] for i in valid_reps)
    return {**own, "n": n, "valid": len(valid), "failures": failures,
            "incomplete": failures / n > 0.01, "calibration_rankable": failures / n <= 0.01,
            "population": {"macro_f1": "all rows; failed outputs are sentinel misses",
                           "brier_ece": "valid rows", "wilson": "lowest-id representative rows"},
            "coverage": {"row_rate": len(valid) / n, "representative_successes": len(valid_reps),
                         "representative_n": len(representatives),
                         "wilson_95": _wilson(len(valid_reps), len(representatives))},
            "first_position": {"row_rate": first / len(valid) if valid else None,
                               "wilson_95": _wilson(first_reps, len(valid_reps))} if ordered_options else {"status": "NOT_APPLICABLE"},
            "sensitivity": {"population": "all rows; failures replaced by uniform", **sensitivity}}


def _contributions(truth, answers, labels):
    """Additive row statistics; summing them preserves duplicate/conflicting rows."""
    labels = sorted(labels)
    n = len(truth)
    k = len(labels)
    y = np.array([labels.index(t) for t in truth])
    p = np.array([[a.probabilities[l] for l in labels] for a in answers])
    chosen = np.array([labels.index(a.label) for a in answers])
    target = np.eye(k)[y]
    predicted = np.eye(k)[chosen]
    bins = np.searchsorted(np.linspace(0, 1, 16)[1:], p.max(axis=1), side="left")
    indicator = np.eye(15)[bins]
    return np.column_stack((np.ones(n), target * predicted, target, predicted,
        ((target - p) ** 2).sum(axis=1), indicator,
        indicator * (p.argmax(axis=1) == y)[:, None], indicator * p.max(axis=1)[:, None]))


def _from_sums(sums):
    # sklearn's F1 = 2 TP / (true support + predicted support), zero denominator -> 0.
    denominator = sums[..., 4:7] + sums[..., 7:10]
    f1 = np.divide(2 * sums[..., 1:4], denominator, out=np.zeros_like(denominator), where=denominator != 0).mean(axis=-1)
    brier = sums[..., 10] / sums[..., 0]
    ece = np.abs(sums[..., 26:41] - sums[..., 41:56]).sum(axis=-1) / sums[..., 0]
    return np.stack((f1, brier, ece), axis=-1)


def paired_metrics(pack: CaseSet, first: dict, second: dict) -> dict:
    """Shared rows for point differences; bootstrap clusters; McNemar original reps."""
    labels = LABELS[pack.name]
    shared = [r for r in pack.scored if first.get(r.id) is not None and second.get(r.id) is not None]
    shared_ids = {r.id for r in shared}
    original_groups = clusters(pack.scored)
    representatives = [g[0] for g in original_groups if g[0] in shared_ids]
    result = {"status": "RAN", "shared_ids": sorted(shared_ids), "representative_ids": representatives,
              "population": "shared valid rows; intervals resample canonical-text clusters",
              "unit": {"point": "rows", "interval": "clusters", "mcnemar": "original representative rows"}}
    if not shared:
        return {**result, "status": "NO_SHARED", "macro_f1": None, "brier": None, "ece": None, "mcnemar": None}
    truth = [r.label for r in shared]
    a = _metrics(truth, [first[r.id] for r in shared], labels)
    b = _metrics(truth, [second[r.id] for r in shared], labels)
    index = {r.id: i for i, r in enumerate(shared)}
    groups = [[index[i] for i in g if i in shared_ids] for g in original_groups]
    groups = [g for g in groups if g]
    rows = np.stack([_contributions(truth, [arm[r.id] for r in shared], labels) for arm in (first, second)], axis=1)
    aggregate = np.stack([rows[g].sum(axis=0) for g in groups])
    def statistic(ids, axis=-1):
        total = aggregate[np.asarray(ids, dtype=int)].sum(axis=-3)
        values = _from_sums(total)
        difference = values[..., 0, :] - values[..., 1, :]
        return np.moveaxis(difference, -1, 0)
    interval = None
    if len(groups) >= 2:
        interval = stats.bootstrap((np.arange(len(groups)),), statistic, paired=True,
            vectorized=True, batch=16, method="percentile", n_resamples=10000,
            confidence_level=0.95, rng=np.random.default_rng(SEED)).confidence_interval
    for i, metric in enumerate(("macro_f1", "brier", "ece")):
        result[metric] = {"point": a[metric] - b[metric],
                          "low": float(interval.low[i]) if interval is not None else None,
                          "high": float(interval.high[i]) if interval is not None else None}
    by_id = {r.id: r for r in shared}
    result["mcnemar"] = mcnemar_exact([by_id[i].label for i in representatives],
        [first[i].label for i in representatives], [second[i].label for i in representatives])
    result["clusters"] = len(groups)
    return result


def beats(model: str, name: str, incomplete: bool, pairs: dict, canaries: dict) -> dict:
    """The sealed A3 conjunction; the model-parity pair is never an input."""
    if model not in MODELS or name not in BASELINES:
        raise ValueError("versioned model and static set required")
    if set(pairs) != set(BASELINES[name]):
        raise ValueError("every preregistered pair must be reported")
    not_run = [b for b in BASELINES[name] if pairs[b].get("status") == "NOT_RUN"]
    ran = [b for b in BASELINES[name] if b not in not_run]
    reasons = []
    if incomplete:
        reasons.append("model incomplete")
    if not ran:
        reasons.append("no baseline pair ran")
    def interval_ok(value, f1):
        if not isinstance(value, dict):
            return False
        low, high = value.get("low"), value.get("high")
        if any(type(x) not in (int, float) or not math.isfinite(x) for x in (low, high)) or low > high:
            return False
        return low > 0 if f1 else high <= 0
    for baseline in ran:
        pair = pairs[baseline]
        if pair.get("status") != "RAN" or not interval_ok(pair.get("macro_f1"), True) or not interval_ok(pair.get("brier"), False):
            reasons.append(f"pair did not satisfy both intervals: {baseline}")
    for canary in ("date_shift", "entity_mask"):
        status = canaries.get(canary, {}).get("status")
        if status not in {"PASS", "COUNTS_ONLY", "NOT_RUN", "NOT_APPLIED"}:
            reasons.append(f"canary failed or unreported: {canary}")
    passed = not reasons
    label = "does not beat the baselines"
    if passed:
        label = f"beats the baselines that ran ({len(ran)} of {len(pairs)})" if not_run else "beats the baselines"
    return {"model": model, "set": name, "beats": passed, "label": label,
            "ran_count": len(ran), "pair_count": len(pairs), "not_run": not_run,
            "not_run_count": len(not_run), "reasons": reasons, "lane_admission": False}


def harness_beats(sets: dict) -> dict:
    if set(sets) != set(LABELS):
        raise ValueError("all three static-set outcomes required")
    applicable = [name for name, outcome in sets.items() if outcome["ran_count"] > 0]
    return {"beats": bool(applicable) and all(sets[name]["beats"] for name in applicable),
            "sets_with_pairs": applicable, "sets_without_pairs": [n for n in sets if n not in applicable],
            "pooled": False, "lane_admission": False}
