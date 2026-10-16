"""Validate sourced angle records and derive angle-convergence/2.

R0/R2/R3/R5 retain the input's sign rule. V2 raises coverage to four angles
and restricts A6 to comparative measurements. Weights affect score/coverage
and which angles are active, without introducing an acceptance threshold.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import re
from urllib.parse import urlsplit

from jsonschema import Draft202012Validator, FormatChecker
from rfc3986_validator import validate_rfc3986

DIRECTORY = "catalogs/landscape/angles"
SCHEMA = DIRECTORY + "/schema.json"
RULE_VERSION = "angle-convergence/2"
ANGLES = ("A1", "A2", "A3", "A4", "A5", "A6")
DEFAULT_WEIGHTS = dict(zip(ANGLES, (.20, .20, .15, .15, .20, .10)))
SIGNS = {"+": 1, "0": 0, "-": -1}
DISQUALIFIERS = (None, "missing_capability", "abandoned")
RESOLVED_PIN = re.compile(
    r"(?:[0-9a-f]{40}|v?\d+(?:\.\d+)+(?:[A-Za-z][0-9A-Za-z]*)?(?:[-.+~][0-9A-Za-z]+)*"
    r"(?:(?: @ |; source )[0-9a-f]{40})?)")
# Exact documented snapshots, including historical IDs. This is identity,
# not currency: there is no age cutoff or latest-generation requirement.
# Pinned provider files and snapshot/alias distinctions are retained in
# evidence/artifacts/angle-records-a1-20261015/provider-snapshot-sources.json.
# openai/openai-python@86cae50785fb7b7bf2a5d2383370b214b304acd2:
# src/openai/types/shared/chat_model.py:8-96 and all_models.py:14-28.
# anthropics/anthropic-sdk-python@bcd55fe1d3f0f1240765f8cef04295b67337f55a:
# src/anthropic/types/model.py:8-27; legacy dated IDs at e42451ab3f14443c0ed8076b17032a6d8986b6bf
# :11-20 and 472c51ebec9fca647df9f39e0da1ca77c221a62f:14-22, same path.
# GPT-5.4's exact dated ID is retained from its official snapshot table.
MODEL_SNAPSHOTS = frozenset((
    "claude-3-5-haiku-20241022", "claude-3-5-sonnet-20240620", "claude-3-5-sonnet-20241022",
    "claude-3-7-sonnet-20250219", "claude-3-haiku-20240307", "claude-3-opus-20240229",
    "claude-3-sonnet-20240229", "claude-4-opus-20250514", "claude-4-sonnet-20250514",
    "claude-fable-5", "claude-fable-5-1", "claude-haiku-4-5-20251001", "claude-haiku-5-5",
    "claude-mythos-5", "claude-mythos-5-1",
    "claude-opus-4-20250514", "claude-opus-4-5-20251101", "claude-opus-4-6",
    "claude-opus-4-7", "claude-opus-4-8", "claude-opus-5", "claude-opus-5-5",
    "claude-sonnet-4-20250514", "claude-sonnet-4-5-20250929", "claude-sonnet-4-6",
    "claude-sonnet-5", "claude-sonnet-5-5", "computer-use-preview-2025-03-11",
    "gpt-3.5-turbo-0125", "gpt-3.5-turbo-0301", "gpt-3.5-turbo-0613", "gpt-3.5-turbo-1106",
    "gpt-3.5-turbo-16k-0613", "gpt-4-0125-preview", "gpt-4-0314", "gpt-4-0613",
    "gpt-4-1106-preview", "gpt-4-32k-0314", "gpt-4-32k-0613", "gpt-4-turbo-2024-04-09",
    "gpt-4.1-2025-04-14", "gpt-4.1-mini-2025-04-14", "gpt-4.1-nano-2025-04-14",
    "gpt-4o-2024-05-13", "gpt-4o-2024-08-06", "gpt-4o-2024-11-20",
    "gpt-4o-audio-preview-2024-10-01", "gpt-4o-audio-preview-2024-12-17",
    "gpt-4o-audio-preview-2025-06-03", "gpt-4o-mini-2024-07-18",
    "gpt-4o-mini-audio-preview-2024-12-17", "gpt-4o-mini-search-preview-2025-03-11",
    "gpt-4o-search-preview-2025-03-11", "gpt-5-2025-08-07", "gpt-5-mini-2025-08-07",
    "gpt-5-nano-2025-08-07", "gpt-5-pro-2025-10-06", "gpt-5.1-2025-11-13",
    "gpt-5.2-2025-12-11", "gpt-5.2-pro-2025-12-11", "gpt-5.4-2026-03-05",
    "gpt-5.4-mini-2026-03-17", "gpt-5.4-nano-2026-03-17", "gpt-5.5-2026-04-23",
    "gpt-5.5-pro-2026-04-23", "gpt-5.6-luna", "gpt-5.6-sol", "gpt-5.6-terra",
    "gpt-6-astra", "gpt-6-luna", "gpt-6-sol", "gpt-6.1-sol", "gpt-audio-mini-2025-12-15",
    "o1-2024-12-17", "o1-mini-2024-09-12", "o1-preview-2024-09-12", "o1-pro-2025-03-19",
    "o3-2025-04-16", "o3-deep-research-2025-06-26", "o3-mini-2025-01-31",
    "o3-pro-2025-06-10", "o4-mini-2025-04-16", "o4-mini-deep-research-2025-06-26",
))
UTC_TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z")


class AngleRecordError(ValueError):
    """An angle record fails the schema or evidence contract."""


def timestamp(value: str) -> datetime:
    if not isinstance(value, str) or not UTC_TIMESTAMP.fullmatch(value):
        raise AngleRecordError("invalid UTC timestamp")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise AngleRecordError("invalid UTC timestamp") from None


def validate_https_url(value) -> None:
    try:
        if (not isinstance(value, str) or any(c.isspace() or ord(c) < 32 for c in value)
            or not validate_rfc3986(value, rule="URI")):
            raise ValueError
        parsed = urlsplit(value)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username is not None
            or parsed.password is not None or not parsed.netloc):
            raise ValueError
        parsed.port
    except (TypeError, ValueError):
        raise AngleRecordError("invalid HTTPS source URL") from None


def validate_reads(value, stated: datetime) -> None:
    """Explicit checks do not depend on optional FormatChecker registrations."""
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "read_at" and stated >= timestamp(child):
                if "score" in value and "sources" in value:
                    raise AngleRecordError("weights must be stated before scoring")
                raise AngleRecordError("weights must precede every read time")
            if key in ("url", "repository"):
                validate_https_url(child)
            validate_reads(child, stated)
    elif isinstance(value, list):
        for child in value:
            validate_reads(child, stated)


def effective_weights(record: dict) -> dict[str, Decimal]:
    weights = {angle: Decimal(str(record["weights"][angle])) for angle in ANGLES}
    if record["published_evaluations_available"] is False:
        weights["A6"] += weights["A5"]
        weights["A5"] = Decimal(0)
    return weights


def bound_a1_sources(candidate: dict, sources=None) -> list[dict]:
    """A capability citation belongs to the complete current candidate identity."""
    if not all(isinstance(candidate.get(field), str) and candidate[field].strip()
               for field in ("repository", "pin")):
        return []
    angles = candidate.get("angles")
    a1 = angles.get("A1") if isinstance(angles, dict) else None
    citations = a1.get("sources") if isinstance(a1, dict) else None
    if not isinstance(citations, list):
        return []
    for source in citations:
        if not isinstance(source, dict) or source.get("kind") != "receipt":
            continue
        if sources is None:
            return []
        try:
            receipt = sources.json(source.get("path"))
        except (OSError, ValueError, TypeError, KeyError):
            return []
        if (not isinstance(receipt, dict) or receipt.get("kind") != "capability"
            or not isinstance(candidate.get("id"), str) or not candidate["id"].strip()
            or receipt.get("candidate_id") != candidate["id"]
            or receipt.get("repository") != candidate.get("repository")
            or receipt.get("pin") != candidate.get("pin")):
            return []
    return [source for source in citations if isinstance(source, dict)
            and source.get("repository") == candidate.get("repository")
            and source.get("pin") == candidate.get("pin")
            and (candidate.get("pin") not in MODEL_SNAPSHOTS or source.get("pin_kind") == "model")]


def resolved_a1_pin(candidate: dict) -> bool:
    """Recognize a software pin or an explicitly typed documented snapshot."""
    pin = candidate.get("pin")
    angles = candidate.get("angles")
    a1 = angles.get("A1") if isinstance(angles, dict) else None
    citations = a1.get("sources") if isinstance(a1, dict) else None
    if not isinstance(pin, str):
        return False
    model = (isinstance(citations, list)
             and any(isinstance(source, dict) and source.get("repository") == candidate.get("repository")
                     and source.get("pin") == pin and source.get("pin_kind") == "model"
                     for source in citations))
    return pin in MODEL_SNAPSHOTS if model else bool(RESOLVED_PIN.fullmatch(pin))


def derive(record: dict, candidate: dict, *, sources=None) -> dict:
    """R0, R1(v2), R2, R3(v2), R5, in that order; no single-angle admission."""
    if candidate["disqualifier"] not in DISQUALIFIERS:
        raise AngleRecordError("unsupported disqualifier")
    weights = effective_weights(record)
    scores = {angle: cell["score"] for angle, cell in candidate["angles"].items()
              if cell["score"] != "U" and cell["sources"] and weights[angle] > 0}
    score = sum((weights[a] * SIGNS[s] for a, s in scores.items()), Decimal(0))
    coverage = sum((weights[a] for a in scores), Decimal(0))
    if candidate["disqualifier"] is not None:
        verdict = "REJECTED"
    elif (not candidate["a1_screened"] or not resolved_a1_pin(candidate) or not bound_a1_sources(candidate, sources)
          or "A1" not in scores or len(scores) < 4):
        verdict = "INSUFFICIENT"
    elif "+" in scores.values() and "-" in scores.values():
        verdict = "DISAGREE"
    elif (scores.get("A1") == "+" and scores.get("A2") != "-"
          and sum(scores.get(a) == "+" for a in ("A3", "A4", "A5")) >= 2
          and "-" not in scores.values()
          and any(scores.get(a) == "+" for a in ("A5", "A6"))):
        verdict = "CONVERGED"
    else:
        verdict = "INSUFFICIENT"
    return {"verdict": verdict,
            "provisional": verdict == "CONVERGED" and not candidate["a6_comparative"],
            "weighted_score": float(score), "coverage": float(coverage), "sourced_angles": len(scores)}


def validate_record(record: dict, schema: dict, *, label: str, sources=None) -> None:
    if isinstance(record, dict) and isinstance(record.get("candidates"), list):
        for candidate in record["candidates"]:
            if isinstance(candidate, dict) and candidate.get("a1_screened") is True:
                if not resolved_a1_pin(candidate):
                    angles = candidate.get("angles")
                    a1 = angles.get("A1") if isinstance(angles, dict) else None
                    citations = a1.get("sources") if isinstance(a1, dict) else None
                    old_model_binding = (isinstance(candidate.get("pin"), str)
                        and candidate["pin"] in MODEL_SNAPSHOTS and isinstance(citations, list)
                        and isinstance(candidate.get("repository"), str)
                        and bool(candidate["repository"].strip())
                        and any(isinstance(source, dict) and source.get("pin_kind") == "model"
                                and source.get("repository") == candidate["repository"]
                                and isinstance(source.get("pin"), str)
                                and source.get("pin") in MODEL_SNAPSHOTS
                                for source in citations))
                    if old_model_binding:
                        raise AngleRecordError(f"{label}: A1 evidence must bind its current repository and pin")
                    raise AngleRecordError(f"{label}: A1 screen requires a resolved pin identity")
        stated = timestamp(record.get("weights_stated_at"))
        validate_reads(record, stated)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    error = next(validator.iter_errors(record), None)
    if error is not None:
        # Rejected instance values may contain private bytes: diagnostics never echo them.
        raise AngleRecordError(f"{label}: schema failure ({error.validator})")
    if sum((Decimal(str(w)) for w in record["weights"].values()), Decimal(0)) != 1:
        raise AngleRecordError(f"{label}: weight sum must equal 1")
    stated = timestamp(record["weights_stated_at"])
    identities = set()
    for candidate in record["candidates"]:
        ident = candidate["id"]
        if ident in identities:
            raise AngleRecordError(f"{label}: duplicate candidate id")
        identities.add(ident)
        if candidate["a1_screened"] and candidate["angles"]["A1"]["score"] == "U":
            raise AngleRecordError(f"{label}: A1 screen requires a known pin and a sourced score")
        if candidate["a1_screened"] and not bound_a1_sources(candidate, sources):
            raise AngleRecordError(f"{label}: A1 evidence must name the current repository and pin")
        for angle, cell in candidate["angles"].items():
            if stated >= timestamp(cell["read_at"]):
                raise AngleRecordError(f"{label}: weights must be stated before scoring")
            if cell["score"] != "U" and not cell["sources"]:
                raise AngleRecordError(f"{label}: score without source")
            for source in cell["sources"]:
                if source["kind"] == "url" and timestamp(source["read_at"]) > timestamp(cell["read_at"]):
                    raise AngleRecordError(f"{label}: score precedes its URL source read")
                if sources is not None and source["kind"] == "receipt":
                    sources.read_bytes(source["path"])
                    if angle == "A6" and cell["score"] != "U":
                        validate_comparison(sources, source["path"], candidate, label)
        a6 = candidate["angles"]["A6"]
        if (candidate.get("entitlement") or {}).get("status") == "conflict" and candidate["disqualifier"] != "missing_capability":
            raise AngleRecordError(f"{label}: terms conflict is a missing_capability disqualifier")
        if a6["score"] != "U" and (not candidate["a6_comparative"] or not candidate["confounds"]
                                   or not any(s["kind"] == "receipt" for s in a6["sources"])):
            raise AngleRecordError(f"{label}: A6 requires a comparative receipt and stated confounds")
        if candidate["a6_comparative"] and a6["score"] == "U":
            raise AngleRecordError(f"{label}: comparative A6 flag has no measurement")
        if record["published_evaluations_available"] is False and candidate["angles"]["A5"]["score"] != "U":
            raise AngleRecordError(f"{label}: A5 transfer conflicts with a published evaluation")
        derived = derive(record, candidate, sources=sources)
        if (candidate["verdict"], candidate["provisional"]) != (derived["verdict"], derived["provisional"]):
            raise AngleRecordError(f"{label}: stated verdict does not re-derive under {RULE_VERSION}")
        if derived["verdict"] == "DISAGREE" and not (candidate["measure_next"] or "").strip():
            raise AngleRecordError(f"{label}: DISAGREE requires measure_next")
        if candidate["disqualifier"] and not any(candidate["angles"][a]["sources"] for a in ("A1", "A2")):
            raise AngleRecordError(f"{label}: hard disqualifier requires A1 or A2 source evidence")
        neutral = ("trial_permitted", "final_eligible", "basis")
        if any(k in candidate for k in neutral) and not all(k in candidate for k in neutral):
            raise AngleRecordError(f"{label}: neutral trial metadata requires all three fields")
        metadata_sources = list((candidate.get("entitlement") or {}).get("sources") or [])
        licence_source = (candidate.get("licence_note") or {}).get("source")
        if licence_source:
            metadata_sources.append(licence_source)
        for source in metadata_sources:
            if sources is not None and source["kind"] == "receipt":
                sources.read_bytes(source["path"])
    bound = [entry["candidate_id"] for entry in record["final_evidence"]]
    if len(bound) != len(set(bound)) or any(ident not in identities for ident in bound):
        raise AngleRecordError(f"{label}: FINAL evidence has a duplicate or unknown candidate")


def validate_comparison(sources, path: str, candidate: dict, label: str) -> None:
    """Retain upstream result artifacts for at least two arms; a smoke flag cannot satisfy A6."""
    receipt = sources.json(path)
    if (not isinstance(receipt, dict) or receipt.get("kind") != "comparative"
        or not isinstance(candidate.get("id"), str) or not candidate["id"].strip()
        or receipt.get("candidate_id") != candidate["id"]
        or receipt.get("evidence_class") != "native_proven" or receipt.get("completed") is not True
        or receipt.get("harness") not in ("Harbor", "promptfoo", "paired")
        or receipt.get("repository") != candidate["repository"] or receipt.get("pin") != candidate["pin"]
        or not isinstance(receipt.get("confounds"), list) or not receipt["confounds"]
        or any(not isinstance(c, str) or not c.strip() for c in receipt["confounds"])):
        raise AngleRecordError(f"{label}: A6 receipt is not a bound comparative upstream run")
    arms = receipt.get("arms")
    if (not isinstance(arms, list) or len(arms) < 2 or any(not isinstance(a, dict) for a in arms)
        or any(not isinstance(a.get("id"), str) or not a["id"].strip()
               or not isinstance(a.get("native_output"), str) or not a["native_output"].strip() for a in arms)
        or len({a["id"] for a in arms}) != len(arms)):
        raise AngleRecordError(f"{label}: A6 comparison requires distinct arms with native output receipts")
    for arm in arms:
        if not isinstance(arm["native_output"], str) or not sources.read_bytes(arm["native_output"]):
            raise AngleRecordError(f"{label}: A6 comparison native output is empty")


def load_records(sources) -> dict:
    directory = sources.path(DIRECTORY)
    if not directory.is_dir():
        return {}
    paths = sorted(p.name for p in directory.iterdir() if p.suffix == ".json" and p.name != "schema.json")
    if not paths:
        return {}
    schema = sources.json(SCHEMA)
    try:
        Draft202012Validator.check_schema(schema)
    except Exception as error:
        raise AngleRecordError("angle record schema is invalid") from error
    records = {}
    for name in paths:
        relative = DIRECTORY + "/" + name
        record = sources.json(relative)
        validate_record(record, schema, label=relative, sources=sources)
        key = (record["catalog"], record["layer_id"])
        if key in records or name != "-".join(key) + ".json":
            raise AngleRecordError("angle record key is duplicated or differs from its filename")
        for reference in record["resolution_inputs"]:
            sources.read_bytes(reference)
        records[key] = {"path": relative, "record": record}
    return records


def summary(entry: dict | None, *, sources=None) -> dict:
    if entry is None:
        return {"status": "missing", "gap": "No angle record; convergence is unverified."}
    record = entry["record"]
    return {"status": "recorded", "path": entry["path"], "rule_version": RULE_VERSION,
            "weights": record["weights"], "effective_weights": {a: float(w) for a, w in effective_weights(record).items()},
            "weights_stated_at": record["weights_stated_at"], "disclosure": record["disclosure"],
            "gaps": record["gaps"], "candidates": [{"id": c["id"], "repository": c["repository"],
                "pin": c["pin"], "disqualifier": c["disqualifier"],
                "adoption_status": c.get("adoption_status"),
                **{k: c[k] for k in ("trial_permitted", "final_eligible", "basis") if k in c},
                **derive(record, c, sources=sources)} for c in record["candidates"]]}
