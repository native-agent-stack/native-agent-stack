"""Deterministic normalization of a timestamped T22 factor-source export.

No acquisition, fitting, model call or parameter choice. Source exports carry
the computed factors; native FactorSnapshot validates decimal/clock contracts.
Source identity is SHA256 of exact retained bytes, never a home/account path.
"""
import hashlib
import importlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
contracts = importlib.import_module("blueprints.us-equities.strategies.contracts")
PRODUCER_ID = "t22-source-normalizer-v1"


def produce(source_bytes):
    """Return exact packet/receipt bytes for the immutable source export."""
    data = json.loads(source_bytes)
    if not isinstance(data, dict) or "source_sha256" in data:
        raise ValueError("t22_source_export_shape_invalid")
    data["source_sha256"] = hashlib.sha256(source_bytes).hexdigest()
    snapshot = contracts.FactorSnapshot.from_json(data)
    packet = snapshot.to_json().encode()
    receipt = {"schema_version": 1, "producer": PRODUCER_ID,
               "code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               "source_sha256": snapshot.source_sha256,
               "packet_sha256": hashlib.sha256(packet).hexdigest()}
    return packet, json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode()
