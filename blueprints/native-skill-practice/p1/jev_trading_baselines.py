"""Decision 4 adapters to the pinned upstreams; no model is loaded on import.

Native factories are for the owning scored runner. BUILD uses test doubles only.
Nemotron's document encoder follows its c0c9fea9 README, Sentence Transformers
example. The native head follows sklearn 1.9.1 LogisticRegression defaults.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import io
import re

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression

from jev_trading_cases import LABELS, SEED, CaseSet, id_hash, sha256
from jev_trading_scoring import prediction

# The retained 2026-10-15 screen captures this Hub revision prefix only.
# Full revision resolution and real cached-weight loading remain offline gaps;
# do not substitute the superseded 4556d130 revision or a floating alias.
PINS = {"finbert": "0bc2ac10dda6",
        "nemotron": "c0c9fea93ea424587517f2c59e20db9f1d6bf615",
        "clm-8b": "e939398d4556fcd9400c76fa8c5a513202f42b0a",
        "haiku": "claude-haiku-5-5"}


def finbert_prediction(probabilities, name):
    if name not in ("FPB-50", "TFN"):
        raise ValueError("finBERT has no FOMC label map")
    positive, negative, neutral = map(float, probabilities)
    values = {"positive": positive, "negative": negative, "neutral": neutral} if name == "FPB-50" else {
        "bullish": positive, "bearish": negative, "neutral": neutral}
    return prediction(values, LABELS[name])


def finbert_native():
    """Official Transformers loader, pinned cached files only; no downloads."""
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    kwargs = {"revision": PINS["finbert"], "local_files_only": True}
    tokenizer = AutoTokenizer.from_pretrained("ProsusAI/finbert", **kwargs)
    model = AutoModelForSequenceClassification.from_pretrained("ProsusAI/finbert", **kwargs).eval()
    if {int(k): v for k, v in model.config.id2label.items()} != {0: "positive", 1: "negative", 2: "neutral"}:
        raise ValueError("finBERT config label pin mismatch")
    def predict(texts, name):
        with torch.inference_mode():
            logits = model(**tokenizer(texts, return_tensors="pt", padding=True, truncation=False)).logits
        return [finbert_prediction(p, name) for p in torch.softmax(logits, dim=-1).tolist()]
    return predict


def nemotron_native(device: str):
    import torch
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer("nvidia/Nemotron-3-Embed-1B-BF16", revision=PINS["nemotron"],
        local_files_only=True, device=device,
        model_kwargs={"dtype": torch.bfloat16, "attn_implementation": "sdpa"})
    model.max_seq_length = 32768
    return lambda texts: model.encode_document(texts, batch_size=8, convert_to_numpy=True)


def _embeddings(embed, texts):
    values = np.asarray(embed(texts), dtype=float)
    if values.shape != (len(texts), 2048) or not np.isfinite(values).all():
        raise ValueError("finite 2048-dimensional embeddings required")
    return values


@dataclass
class FittedHead:
    estimator: LogisticRegression
    embed: object
    artifact: bytes
    training_ids_sha256: str

    @property
    def sha256(self):
        return sha256(self.artifact)

    def predict(self, texts):
        values = self.estimator.predict_proba(_embeddings(self.embed, texts))
        return [prediction(dict(zip(self.estimator.classes_, map(float, p))), self.estimator.classes_) for p in values]


def fit_head(pack: CaseSet, embed) -> FittedHead:
    values = _embeddings(embed, [r.text for r in pack.training])
    if set(r.label for r in pack.training) != set(LABELS[pack.name]):
        raise ValueError("head training must contain all labels")
    model = LogisticRegression(max_iter=1000, random_state=SEED)
    model.fit(values, [r.label for r in pack.training])
    buffer = io.BytesIO()
    joblib.dump(model, buffer, compress=0)
    return FittedHead(model, embed, buffer.getvalue(), id_hash(r.id for r in pack.training))


def clm_status(gpu_window_sha256):
    if not isinstance(gpu_window_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", gpu_window_sha256):
        return {"status": "NOT_RUN", "reason": "no pinned GPU batch window", "pin": PINS["clm-8b"]}
    return {"status": "READY", "gpu_window_sha256": gpu_window_sha256, "pin": PINS["clm-8b"]}


class HaikuBudget:
    """Separate credential-runner workload; cap stops become missing outputs."""
    def __init__(self, config):
        required = {"model", "workload", "pricing_sha256", "credential_runner", "estimate_usd", "cap_usd",
                    "input_per_million", "output_per_million", "parameters", "run_order"}
        if not required <= config.keys() or config["model"] != PINS["haiku"] or config["credential_runner"] is not True:
            raise ValueError("Haiku preregistration incomplete")
        params = config["parameters"]
        if not config["workload"] or not config["run_order"] or not re.fullmatch(r"[0-9a-f]{64}", config["pricing_sha256"]):
            raise ValueError("Haiku workload, order and pricing capture required")
        if "temperature" not in params or params.get("max_tokens") != 200 or "inference_geo" in params:
            raise ValueError("Haiku frozen parameters mismatch")
        self.cap = Decimal(str(config["cap_usd"]))
        estimate = Decimal(str(config["estimate_usd"]))
        self.input_rate = Decimal(str(config["input_per_million"])) / 1000000
        self.output_rate = Decimal(str(config["output_per_million"])) / 1000000
        if not all(x.is_finite() and x > 0 for x in (self.cap, estimate, self.input_rate, self.output_rate)) or self.cap != 2 * estimate:
            raise ValueError("Haiku estimate/cap mismatch")
        if estimate != 8304 * (1000 * self.input_rate + 200 * self.output_rate):
            raise ValueError("Haiku estimate must be recomputed from frozen prices")
        self.spent = Decimal(0)
        self.reserved = Decimal(0)
        self.active_reservation = None
        self.uncertain_calls = 0
        self.stopped = False

    def reserve(self, input_token_upper_bound: int) -> bool:
        if type(input_token_upper_bound) is not int or input_token_upper_bound < 0:
            raise ValueError("input token upper bound required")
        cost = input_token_upper_bound * self.input_rate + 200 * self.output_rate
        if self.stopped or self.spent + self.reserved + cost > self.cap:
            self.stopped = True
            return False
        # Debit before dispatch. A timeout/invalid usage leaves this amount
        # outstanding until the owning ledger resolves the uncertain charge.
        self.reserved += cost
        self.active_reservation = cost
        return True

    def record(self, input_tokens: int, output_tokens: int):
        if any(type(x) is not int or x < 0 for x in (input_tokens, output_tokens)):
            raise ValueError("invalid usage")
        if self.active_reservation is None:
            raise ValueError("Haiku usage requires a pre-dispatch reservation")
        reserved = self.active_reservation
        actual = input_tokens * self.input_rate + output_tokens * self.output_rate
        self.spent += actual
        self.reserved -= reserved
        self.active_reservation = None
        if actual > reserved or self.spent + self.reserved > self.cap:
            self.stopped = True
            raise ValueError("Haiku cap exceeded or reserved token bound violated; stop and retain receipt")

    def unknown(self):
        if self.active_reservation is not None:
            self.uncertain_calls += 1
            self.active_reservation = None


def pending_rules_status():
    return {"status": "NOT_RUN", "reason": "8-K predicates, Item 6.06 tests, code hash and acquisition clock are not frozen"}
