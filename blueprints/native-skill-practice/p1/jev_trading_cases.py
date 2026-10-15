"""Frozen public sets; uet 2026-10-11 decisions 3/7 and JV10–13/JV47.

No acquisition: callers supply retained paths and SHA256 pins. Dataset text is
never written by this module. FPB parsing follows takala/financial_phrasebank
8d3fe0c36d5feec6b3cc5e455b0fcb4820fb9964, financial_phrasebank.py:119–148.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
import hashlib
from importlib.metadata import version
import io
import json
from pathlib import Path

SEED = 20261011
LABELS = {"FPB-50": ("negative", "neutral", "positive"),
          "TFN": ("bearish", "bullish", "neutral"),
          "FOMC": ("dovish", "hawkish", "neutral")}
DEPENDENCIES = {"numpy": "2.5.3", "scipy": "1.18.1", "scikit-learn": "1.9.1"}
SOURCE_PINS = {
    "fpb": "bb1b4df6de05d50b146f87a9d4d024b69f947066445f2384f014c3564c1612c8",
    "tfn_train": "71aa99d0d37feced03c999ec23b5b25302c92f39d69b6acb0a37aa076c5420e8",
    "tfn_scored": "31ea8274c98b52212daa68f2fb962811bf1913c1efe51b99765c8e2311806de6",
    "fomc_train": "3c9ec066b7bbdedc60d553b48e74ae6ca36715b5de2f9000a82e76e909bd76b7",
    "fomc_scored": "c4b6a660a3cd67f940f59b1b77fc4d2f1b99e56c94eaf54b9298a37647ecfbac",
}
ID_PINS = {
    "FPB-50": {
        "scored": "8190e1b51b698362ac21134a74b4e5e3f835e009ca5a29729aa17f8c3e35b008",
        "training": "6c465f233055ff08f4b24fc2a2e27c25873a9e930d2a57c789ce8ace88b7290a",
        "final_training": "3b1ab6c118ecd6714cd48766289d35bfb34eb1b33d1f642190a1673e6b2e9ff2"},
    "TFN": {
        "scored": "19ca04442b94550b226cd9afc0d07cf1f878ba0b2e7df0d3c2c9273dba0b0f67",
        "training": "54ee1a5b3d81542b0b7876fa2eb5e8e3927829ad300138d2d5ce32e2f6ee6059",
        "final_training": "823bd5d20b6e3ff05cf83cbbd131d71852dcd1405f97012acd1d61a7f563f0ab"},
    "FOMC": {
        "scored": "c88b19824ffc35cafb1e87765c88eed214f4eaf775d0e7f35bb58409d227cdb6",
        "training": "dd3e718c4662bb3b5c11705528159995e65ab6c1ef3ffdd57447ecce0df39400",
        "final_training": "6f3e0699af75db9a981cd1a86c780b882663e5c7e7803c12a3a0ef28889928bc"},
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_bytes(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def id_hash(ids) -> str:
    return sha256(json_bytes(sorted(ids)))


def require_dependencies() -> dict:
    installed = {name: version(name) for name in DEPENDENCIES}
    if installed != DEPENDENCIES:
        raise ValueError("dependency pin mismatch; use requirements-scoring.lock")
    return installed


def canonical(text: str) -> str:
    return " ".join(text.split())


def read_pinned(path: Path, pin: str) -> bytes:
    data = Path(path).read_bytes()
    if sha256(data) != pin:
        raise ValueError("source pin mismatch")
    return data


@dataclass(frozen=True)
class Case:
    id: int
    text: str
    label: str


def clusters(rows: tuple[Case, ...] | list[Case]) -> list[list[int]]:
    groups = {}
    for row in sorted(rows, key=lambda r: r.id):
        groups.setdefault(canonical(row.text), []).append(row.id)
    return list(groups.values())


@dataclass(frozen=True)
class CaseSet:
    name: str
    original_training: tuple[Case, ...]
    training: tuple[Case, ...]
    scored: tuple[Case, ...]

    def manifest(self) -> dict:
        final_ids = {r.id for r in self.training}
        ids = {"training": [r.id for r in self.original_training],
               "final_training": sorted(final_ids), "scored": [r.id for r in self.scored],
               "excluded_training": [r.id for r in self.original_training if r.id not in final_ids]}
        groups = clusters(self.scored)
        labels = {r.id: r.label for r in self.scored}
        return {"set": self.name, "ids": ids,
                "id_sha256": {k: id_hash(v) for k, v in ids.items()},
                "content_sha256": {part: sha256(json_bytes([
                    {"id": r.id, "text": r.text, "label": r.label} for r in rows]))
                    for part, rows in (("training", self.original_training),
                                       ("final_training", self.training), ("scored", self.scored))},
                "counts": {k: len(v) for k, v in ids.items()},
                "label_counts": {part: {label: sum(r.label == label for r in rows)
                                       for label in LABELS[self.name]}
                                 for part, rows in (("training", self.original_training),
                                                    ("final_training", self.training), ("scored", self.scored))},
                "clusters": {"count": len(groups), "duplicate_texts": sum(len(g) > 1 for g in groups),
                             "duplicate_rows": sum(len(g) for g in groups if len(g) > 1),
                             "conflicting_labels": sum(len({labels[i] for i in g}) > 1 for g in groups),
                             "representatives": [g[0] for g in groups]}}


def assemble(name: str, training: list[Case], scored: list[Case]) -> CaseSet:
    labels = LABELS[name]
    for rows in (training, scored):
        if len({r.id for r in rows}) != len(rows) or any(
                type(r.id) is not int or r.id < 0 or r.label not in labels or not canonical(r.text)
                for r in rows):
            raise ValueError("invalid case rows")
    scored_text = {canonical(r.text) for r in scored}
    final = [r for r in training if canonical(r.text) not in scored_text]
    order = lambda rows: tuple(sorted(rows, key=lambda r: r.id))
    return CaseSet(name, order(training), order(final), order(scored))


def verify_lists(pack: CaseSet, pins: dict[str, str]) -> None:
    actual = pack.manifest()["id_sha256"]
    if set(pins) != {"training", "final_training", "scored"} or any(actual[k] != v for k, v in pins.items()):
        raise ValueError("id-list pin mismatch")


def option_order(name: str, item_id: int) -> list[str]:
    return sorted(LABELS[name], key=lambda label: sha256(f"{SEED}:{name}:{item_id}:{label}".encode()))


def build_frozen_sets(sources: dict) -> dict[str, CaseSet]:
    """sources maps each SOURCE_PINS role to {path, sha256}; all must match."""
    require_dependencies()
    if set(sources) != set(SOURCE_PINS) or any(sources[k]["sha256"] != v for k, v in SOURCE_PINS.items()):
        raise ValueError("frozen source pins required")
    raw = {k: read_pinned(Path(sources[k]["path"]), pin) for k, pin in SOURCE_PINS.items()}
    fpb = [Case(i, text, label) for i, line in enumerate(raw["fpb"].decode("iso-8859-1").splitlines())
           for text, label in [line.strip().rsplit("@", 1)]]
    from sklearn.model_selection import train_test_split
    train_ids, scored_ids = train_test_split(list(range(len(fpb))), test_size=0.3,
                                             stratify=[r.label for r in fpb], random_state=SEED)
    result = {"FPB-50": assemble("FPB-50", [fpb[i] for i in train_ids], [fpb[i] for i in scored_ids])}
    for name, prefix, column in (("TFN", "tfn", "text"), ("FOMC", "fomc", "sentence")):
        parts = []
        for part in ("train", "scored"):
            rows = csv.DictReader(io.StringIO(raw[f"{prefix}_{part}"].decode("utf-8")))
            parts.append([Case(i, row[column], LABELS[name][int(row["label"])]) for i, row in enumerate(rows)])
        result[name] = assemble(name, *parts)
    for name, pack in result.items():
        verify_lists(pack, ID_PINS[name])
    return result
