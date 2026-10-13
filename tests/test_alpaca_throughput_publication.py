"""Offline publication regressions for #1090 blocker 1 and the headline verifier.

Inputs are the approved public projection and synthetic receipts only. No private
receipt, credential, broker connection or external state is read.
"""
import contextlib
import copy
from datetime import datetime, timedelta
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "evidence/artifacts/trading-handbook-20261013/alpaca-throughput"
EVIDENCE = ARTIFACTS / "alpaca-throughput-evidence-20261013.json"


def load(name):
    spec = importlib.util.spec_from_file_location(name, ARTIFACTS / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    with patch.object(sys, "path", [str(ARTIFACTS), *sys.path]):
        spec.loader.exec_module(module)
    return module


class ThroughputPublicationTests(unittest.TestCase):
    def setUp(self):
        self.document = json.loads(EVIDENCE.read_text())
        self.generator = load("generate_alpaca_throughput_evidence")
        self.verifier = load("verify_alpaca_throughput_evidence")
        self.auditor = load("audit_publication_safety")

    def test_public_receipts_are_cited_by_name_only(self):
        rows = self.document["provenance"]["private_receipts"]
        self.assertTrue(rows)
        self.assertTrue(all(set(row) == {"name"} for row in rows),
                        "Private receipt citations must not publish sizes or digests")

    def test_export_removes_raw_receipt_metadata_and_rejects_other_digest_fields(self):
        private_fixture = b"synthetic private receipt; identity deliberately withheld"
        fingerprint = hashlib.sha256(private_fixture).hexdigest()
        candidate = copy.deepcopy(self.document)
        candidate["provenance"]["private_receipts"] = [
            {"name": "synthetic receipt", "bytes": len(private_fixture), "sha256": fingerprint}]
        exported = self.generator.public_document(candidate)
        self.assertEqual(exported["provenance"]["private_receipts"],
                         [{"name": "synthetic receipt"}])
        text = json.dumps(exported)
        self.assertTrue(all(fingerprint[:n] not in text for n in range(7, 65)),
                        "No seven-or-more-character private fingerprint may survive export")
        candidate["unexpected_digest"] = fingerprint
        with self.assertRaisesRegex(ValueError, "publication"):
            self.generator.public_document(candidate)
        candidate["unexpected_digest"] = "opaque:" + fingerprint[:7] + ":removed"
        with self.assertRaisesRegex(ValueError, "publication"):
            self.generator.public_document(candidate)
        del candidate["unexpected_digest"]
        candidate["facts"]["capacity_py_sha256"]["a1"] = fingerprint
        with self.assertRaisesRegex(ValueError, "publication"):
            self.generator.public_document(candidate)

    def test_publication_auditor_rejects_private_fingerprints(self):
        candidate = {"schema": "alpaca-throughput-evidence/1", "provenance": {
            "private_receipts": [{"name": "synthetic receipt",
                                  "sha256": hashlib.sha256(b"synthetic private bytes").hexdigest()}]}}
        with tempfile.TemporaryDirectory() as scratch:
            path = Path(scratch) / "projection.json"
            path.write_text(json.dumps(candidate))
            with contextlib.redirect_stdout(io.StringIO()):
                code = self.auditor.main([str(path)])
        self.assertEqual(code, 1, "Digest-only metadata must not bypass publication checks")

    def synthetic_inputs(self, scratch):
        """Reverse-map published numeric fields into synthetic, local test receipts."""
        cap = scratch / "capacity"
        headers = scratch / "headers"
        cap.mkdir()
        headers.mkdir()
        document = copy.deepcopy(self.document)
        # A synthetic fixture never republishes a historical private fingerprint.
        document["provenance"]["private_receipts"] = [
            {"name": row["name"]} for row in document["provenance"]["private_receipts"]]
        run = document["capacity_run"]
        start = datetime.fromisoformat(run["started_at_utc"])
        wall = float(document["derived_units"]["values"]["wall_seconds_start_to_end_of_run"])
        config = {"base_url": "https://paper-api.alpaca.markets",
                  "target_actions_ratio": run["limits"]["target_actions_ratio"]}
        a2 = {
            "started_at": start.isoformat(),
            "provenance": {"ended_at": (start + timedelta(seconds=wall)).isoformat(),
                           "source_sha256": {"order-throughput/capacity.py": "a" * 64}},
            "config": config,
            "rate": {"configured_cap_per_minute": 200, "observed_limit": 200,
                     "effective_limit": 200, "headroom": 0.9, "budget_per_minute": 180},
            "orders": {"rest_accepted": 496, "cancel_requests": 496, "submit_attempts": 496},
            "http_status_counts": run["counts"]["http_status_counts"],
            "http_429": {"total": 0},
            "websocket": {"completeness": 1.0},
            "cleanup": {"open_harness_orders_after": 0, "individual_cancels": 1},
            "reconciliation": {"filled_probes": []},
            "throughput": run["throughput"],
            "preflight": {"trading_limit_headers_seen": [1000]},
            "observed_rate_limit_headers": run["rate_limit_headers_seen_during_run"],
            "latency": {name: {("count" if key == "count" else key + "_ms"): value
                               for key, value in block.items()}
                        for name, block in run["latency_ms_from_receipt"].items()},
        }
        a1 = {"status": document["superseded_attempt"]["status"],
              "stage": document["superseded_attempt"]["stage"],
              "refusal_reason": document["superseded_attempt"]["refusal_reason"],
              "provenance": {"exit_code": 2,
                             "source_sha256": {"order-throughput/capacity.py": "b" * 64}},
              "http_status_counts": {}, "orders": {"submit_attempts": 0},
              "config": dict(config, base_url="https://paper-api.alpaca.markets/v2")}
        (cap / "capacity-200-pre-a2.json").write_text(json.dumps(a2))
        (cap / "capacity-200-pre-a1.json").write_text(json.dumps(a1))
        (cap / "a2.stderr").write_text("restarting synthetic stream\n")
        journal = [{"type": "start"}] + [
            {"client_order_id": f"fixture-{i}", "extended_hours": True,
             "limit_price": "1", "qty": "1", "seq": i, "type": "intent"}
            for i in range(496)] + [{"type": "end", "verified_zero_open": True}]
        (cap / "capacity-200-pre-a2.journal.jsonl").write_text(
            "".join(json.dumps(row) + "\n" for row in journal))
        observer = scratch / "observer.json"
        observer.write_text(json.dumps({"summary": document["independent_observer"]}))
        prefixes = {"lane_a": "lane-a", "lane_b": "lane-b", "account_c": "acct-c"}
        for name, rows in document["rate_limit_headers"]["accounts"].items():
            for version in ("v1", "v2"):
                directory = headers / f"readonly-limits{'2' if version == 'v2' else ''}-{prefixes[name]}-synthetic-20261013"
                directory.mkdir()
                receipt = {"label": prefixes[name],
                           "limit_and_remaining_in_request_order": [
                               [r["endpoint"], r["limit"], r["remaining"]] for r in rows],
                           "requests": [{"path": r["endpoint"], "headers": {
                               "x-ratelimit-limit": r["limit"],
                               "x-ratelimit-remaining": r["remaining"]}} for r in rows[:2]]}
                (directory / "receipt.json").write_text(json.dumps(receipt))
        return document, ["--capacity-dir", str(cap), "--header-receipts-dir", str(headers),
                          "--observer-receipt", str(observer)]

    def test_verifier_rejects_each_invented_headline(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            document, arguments = self.synthetic_inputs(root)
            path = root / "projection.json"
            for field, value in [(None, None),
                                 ("limit_reported_on_submit_and_cancel_responses_during_run", 999),
                                 ("p90_latency", 1), ("place_only_capacity", 999)]:
                with self.subTest(field=field or "valid control"):
                    candidate = copy.deepcopy(document)
                    if field:
                        candidate["headline"][field] = value
                    path.write_text(json.dumps(candidate))
                    self.verifier.RESULTS.clear()
                    with contextlib.redirect_stdout(io.StringIO()):
                        code = self.verifier.main(["--evidence", str(path), *arguments])
                    self.assertEqual(code, 1 if field else 0)


if __name__ == "__main__":
    unittest.main()
