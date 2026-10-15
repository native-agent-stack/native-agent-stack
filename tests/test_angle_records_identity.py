"""Synthetic A1 identity controls; no candidate capability is qualified here."""

import copy
import json
from pathlib import Path
import unittest

from scripts import angle_records as ar
from tests.test_final_stack import COMMIT_A, COMMIT_B, _angle_fixture

SCHEMA = json.loads((Path(ar.__file__).resolve().parents[1] / ar.SCHEMA).read_text())


class A1IdentityTests(unittest.TestCase):
    def record(self):
        record = _angle_fixture()
        candidate = record["candidates"][0]
        candidate["angles"]["A1"]["sources"] = [{
            "kind": "repo", "repository": candidate["repository"],
            "pin": COMMIT_A, "path": "README.md", "line": 1,
        }]
        return record

    def test_pin_change_with_unchanged_a1_citations_is_refused(self):
        record = self.record()
        ar.validate_record(record, SCHEMA, label="synthetic")
        before = copy.deepcopy(record["candidates"][0]["angles"]["A1"]["sources"])
        record["candidates"][0]["pin"] = COMMIT_B
        self.assertEqual(record["candidates"][0]["angles"]["A1"]["sources"], before)
        with self.assertRaisesRegex(ar.AngleRecordError, "A1 evidence.*current repository and pin"):
            ar.validate_record(record, SCHEMA, label="synthetic")

    def test_repository_change_with_unchanged_a1_citations_is_refused(self):
        record = self.record()
        ar.validate_record(record, SCHEMA, label="synthetic")
        record["candidates"][0]["repository"] = "https://github.com/example/other"
        with self.assertRaisesRegex(ar.AngleRecordError, "A1 evidence.*current repository and pin"):
            ar.validate_record(record, SCHEMA, label="synthetic")

    def test_stale_identity_cannot_derive_converged(self):
        for field, value in (("pin", COMMIT_B), ("repository", "https://github.com/example/other")):
            with self.subTest(field=field):
                record = self.record()
                candidate = record["candidates"][0]
                candidate[field] = value
                self.assertEqual(ar.derive(record, candidate)["verdict"], "INSUFFICIENT")

    def test_resolved_model_identity_with_bound_url_evidence_is_accepted(self):
        for model in ("muse-wonder-full-1.0", "gpt-6.1-sol", "claude-opus-5-5"):
            with self.subTest(model=model):
                record = _angle_fixture()
                candidate = record["candidates"][0]
                candidate.update(repository="https://example.org/provider/models", pin=model)
                candidate["angles"]["A1"]["sources"][0].update(
                    repository=candidate["repository"], pin=model, pin_kind="model")
                ar.validate_record(record, SCHEMA, label="synthetic-model")
                self.assertEqual(ar.derive(record, candidate)["verdict"], "CONVERGED")

    def test_unresolved_or_untyped_model_identity_cannot_converge(self):
        for pin, kind in (("gpt-reserve", "model"), ("muse-code-subscription", "model"),
                          ("latest", "model"), ("HEAD", "model"), ("gpt-6.1-sol", None)):
            with self.subTest(pin=pin, kind=kind):
                record = _angle_fixture()
                candidate = record["candidates"][0]
                candidate["pin"] = pin
                source = candidate["angles"]["A1"]["sources"][0]
                source.update(repository=candidate["repository"], pin=pin)
                if kind:
                    source["pin_kind"] = kind
                with self.assertRaisesRegex(ar.AngleRecordError, "resolved pin identity"):
                    ar.validate_record(record, SCHEMA, label="synthetic")
                self.assertEqual(ar.derive(record, candidate)["verdict"], "INSUFFICIENT")

    def test_bound_commit_and_release_identity_remain_converged(self):
        for pin in (COMMIT_A, "v1.0.0", "1.0.0 @ " + COMMIT_A, "1.0.0; source " + COMMIT_A):
            with self.subTest(pin=pin):
                record = _angle_fixture()
                candidate = record["candidates"][0]
                candidate["pin"] = pin
                candidate["angles"]["A1"]["sources"][0].update(
                    repository=candidate["repository"], pin=pin)
                ar.validate_record(record, SCHEMA, label="synthetic")
                self.assertEqual(ar.derive(record, candidate)["verdict"], "CONVERGED")

    def test_generic_url_or_receipt_alone_does_not_bind_a1(self):
        for source in ({"kind": "url", "url": "https://example.org/capability",
                        "read_at": "2026-10-12T21:34:46Z"},
                       {"kind": "receipt", "path": "evidence/fixture.json"}):
            with self.subTest(kind=source["kind"]):
                record = self.record()
                record["candidates"][0]["angles"]["A1"]["sources"] = [source]
                with self.assertRaisesRegex(ar.AngleRecordError, "A1 evidence.*current repository and pin"):
                    ar.validate_record(record, SCHEMA, label="synthetic")

    def test_partial_source_identity_is_invalid(self):
        for missing in ("repository", "pin"):
            with self.subTest(missing=missing):
                record = _angle_fixture()
                source = record["candidates"][0]["angles"]["A1"]["sources"][0]
                source.update(repository=record["candidates"][0]["repository"], pin=COMMIT_A)
                del source[missing]
                with self.assertRaisesRegex(ar.AngleRecordError, "schema failure"):
                    ar.validate_record(record, SCHEMA, label="synthetic")

    def test_model_pin_change_keeps_the_old_screen_bound_to_the_old_model(self):
        record = _angle_fixture()
        candidate = record["candidates"][0]
        candidate["pin"] = "gpt-6.1-sol"
        candidate["angles"]["A1"]["sources"][0].update(
            repository=candidate["repository"], pin=candidate["pin"], pin_kind="model")
        ar.validate_record(record, SCHEMA, label="synthetic")
        candidate["pin"] = "gpt-6-astra"
        with self.assertRaisesRegex(ar.AngleRecordError, "resolved pin identity"):
            ar.validate_record(record, SCHEMA, label="synthetic")


if __name__ == "__main__":
    unittest.main()
