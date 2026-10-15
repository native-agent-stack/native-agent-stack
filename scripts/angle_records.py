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


def derive(record: dict, candidate: dict) -> dict:
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
    elif not candidate["a1_screened"] or "A1" not in scores or len(scores) < 4:
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
                pin = candidate.get("pin")
                if not isinstance(pin, str) or not RESOLVED_PIN.fullmatch(pin):
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
        derived = derive(record, candidate)
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


def summary(entry: dict | None) -> dict:
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
                **derive(record, c)} for c in record["candidates"]]}
