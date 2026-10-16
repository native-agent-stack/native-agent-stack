"""Native receipt ownership and retained-history controls before activation."""

import json
from pathlib import Path
import tempfile
import unittest

from scripts import angle_records as ar
from scripts import final_stack as fs
from scripts import saturation_ledger as sl
from tests import test_angle_records_identity as identity_helpers
from tests import test_saturation_ledger as native_helpers

ROOT = Path(__file__).resolve().parents[1]


class ContractDocumentationTests(unittest.TestCase):
    """Keep the published policy attribution and receipt contract limits explicit."""

    def test_currency_separation_has_a_dated_clarification(self):
        for name in ("2026-10-15-a1-identity-binding.md",
                     "2026-10-16-preopening-receipt-ownership-v2-replay.md"):
            with self.subTest(decision=name):
                text = (ROOT / "docs/decisions" / name).read_text()
                paragraph = next(part for part in text.split("\n\n")
                                 if "currency separation" in part.casefold())
                self.assertIn("2026-10-16", paragraph)
                self.assertIn("clarification", paragraph.casefold())
                self.assertIn("background", paragraph.casefold())

    def test_receipt_definitions_are_described_as_test_only_producer_contracts(self):
        text = (ROOT / "docs/decisions/2026-10-16-preopening-receipt-ownership-v2-replay.md").read_text()
        contract = " ".join(text.split("## Snapshot recognition and currency")[0].split())
        self.assertIn("test-only producer contracts", contract)
        self.assertIn("Runtime enforcement", contract)
        self.assertIn("bound_a1_sources", contract)
        self.assertIn("validate_comparison", contract)


class ReceiptOwnershipTests(unittest.TestCase):
    record = identity_helpers.A1IdentityTests.record

    def capability_fixture(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        record = self.record()
        candidate = record["candidates"][0]
        path = "evidence/artifacts/fixture/capability.json"
        candidate["angles"]["A1"]["sources"] = [{"kind": "receipt", "path": path,
            "repository": candidate["repository"], "pin": candidate["pin"]}]
        receipt = {"kind": "capability", "candidate_id": candidate["id"],
                   "repository": candidate["repository"], "pin": candidate["pin"]}
        target = root / path
        target.parent.mkdir(parents=True)
        target.write_text(json.dumps(receipt) + "\n")
        return root, record, candidate, target, receipt

    def comparison_fixture(self):
        root, record, candidate, _, _ = self.capability_fixture()
        arms = []
        for ident in ("reference", "candidate"):
            path = f"evidence/artifacts/fixture/{ident}.txt"
            (root / path).write_text("Synthetic retained native output.\n")
            arms.append({"id": ident, "native_output": path})
        path = "evidence/artifacts/fixture/comparison.json"
        receipt = {"kind": "comparative", "candidate_id": candidate["id"],
                   "evidence_class": "native_proven", "completed": True,
                   "harness": "paired", "repository": candidate["repository"],
                   "pin": candidate["pin"], "confounds": ["Synthetic ownership control."],
                   "arms": arms}
        (root / path).write_text(json.dumps(receipt) + "\n")
        return root, candidate, path, receipt

    def test_a6_receipt_requires_its_own_candidate(self):
        for changed in ("missing", "sibling"):
            with self.subTest(changed=changed):
                root, candidate, path, receipt = self.comparison_fixture()
                ar.validate_comparison(fs.Sources(root), path, candidate, "synthetic-comparison")
                if changed == "missing":
                    receipt.pop("candidate_id")
                else:
                    receipt["candidate_id"] = "sibling-route"
                (root / path).write_text(json.dumps(receipt) + "\n")
                with self.assertRaisesRegex(ar.AngleRecordError, "bound comparative"):
                    ar.validate_comparison(fs.Sources(root), path, candidate, "synthetic-comparison")

    def test_a6_receipt_cannot_be_reused_by_a_sibling_candidate(self):
        root, candidate, path, _ = self.comparison_fixture()
        ar.validate_comparison(fs.Sources(root), path, candidate, "synthetic-comparison")
        candidate = dict(candidate, id="sibling-route")
        with self.assertRaisesRegex(ar.AngleRecordError, "bound comparative"):
            ar.validate_comparison(fs.Sources(root), path, candidate, "synthetic-comparison")

    def test_a1_receipt_requires_its_own_capability_kind_and_candidate(self):
        for changed in ("missing_kind", "wrong_kind", "missing_candidate", "wrong_candidate"):
            with self.subTest(changed=changed):
                root, record, candidate, target, receipt = self.capability_fixture()
                self.assertEqual(ar.derive(record, candidate, sources=fs.Sources(root))["verdict"], "CONVERGED")
                if changed == "missing_kind":
                    receipt.pop("kind")
                elif changed == "wrong_kind":
                    receipt["kind"] = "installation"
                elif changed == "missing_candidate":
                    receipt.pop("candidate_id")
                else:
                    receipt["candidate_id"] = "sibling-route"
                target.write_text(json.dumps(receipt) + "\n")
                self.assertEqual(ar.derive(record, candidate, sources=fs.Sources(root))["verdict"], "INSUFFICIENT")

    def test_a1_receipt_cannot_be_reused_by_a_sibling_candidate(self):
        root, record, candidate, _, _ = self.capability_fixture()
        self.assertEqual(ar.derive(record, candidate, sources=fs.Sources(root))["verdict"], "CONVERGED")
        candidate["id"] = "sibling-route"
        self.assertEqual(ar.derive(record, candidate, sources=fs.Sources(root))["verdict"], "INSUFFICIENT")

    def test_direct_derivation_requires_a_present_repository_identity(self):
        for absent in (None, "", "   "):
            with self.subTest(repository=absent):
                record = self.record()
                candidate = record["candidates"][0]
                self.assertEqual(ar.derive(record, candidate)["verdict"], "CONVERGED")
                candidate["repository"] = absent
                candidate["angles"]["A1"]["sources"][0]["repository"] = absent
                self.assertEqual(ar.derive(record, candidate)["verdict"], "INSUFFICIENT")

    def test_unbound_model_type_does_not_reclassify_bound_software(self):
        for changed in ("repository", "pin"):
            with self.subTest(changed=changed):
                record = self.record()
                candidate = record["candidates"][0]
                cell = candidate["angles"]["A1"]
                stray = {"kind": "url", "url": "https://example.org/provider/capability",
                         "read_at": cell["read_at"], "repository": candidate["repository"],
                         "pin": candidate["pin"], "pin_kind": "model"}
                stray[changed] = ("https://example.org/another/provider" if changed == "repository"
                                  else "gpt-6-astra")
                cell["sources"].append(stray)
                self.assertEqual(ar.derive(record, candidate)["verdict"], "CONVERGED")
                schema = json.loads((ROOT / ar.SCHEMA).read_text())
                ar.validate_record(record, schema, label="synthetic-mixed-citations")

    def test_receipt_content_schemas_require_their_own_identity_fields(self):
        schema = json.loads((ROOT / ar.SCHEMA).read_text())
        for kind in ("capability", "comparative"):
            with self.subTest(kind=kind):
                name = kind + "_receipt"
                self.assertIn(name, schema["$defs"])
                if kind == "capability":
                    _, _, _, _, receipt = self.capability_fixture()
                else:
                    _, _, _, receipt = self.comparison_fixture()
                contract = {"$schema": schema["$schema"], "$defs": schema["$defs"],
                            "$ref": "#/$defs/" + name}
                validator = ar.Draft202012Validator(contract, format_checker=ar.FormatChecker())
                self.assertEqual(list(validator.iter_errors(receipt)), [])
                for field in ("kind", "candidate_id", "repository", "pin"):
                    incomplete = dict(receipt)
                    incomplete.pop(field)
                    self.assertTrue(any(error.validator == "required"
                                        for error in validator.iter_errors(incomplete)), field)

    def test_uncorroborated_preview_is_not_a_resolved_model_snapshot(self):
        record = self.record()
        candidate = record["candidates"][0]
        candidate.update(repository="https://example.org/provider/models", pin="claude-mythos-preview")
        cell = candidate["angles"]["A1"]
        cell["sources"] = [{"kind": "url", "url": "https://example.org/provider/capability",
                            "read_at": cell["read_at"], "repository": candidate["repository"],
                            "pin": candidate["pin"], "pin_kind": "model"}]
        self.assertEqual(ar.derive(record, candidate)["verdict"], "INSUFFICIENT")
        schema = json.loads((ROOT / ar.SCHEMA).read_text())
        with self.assertRaisesRegex(ar.AngleRecordError, "resolved pin identity"):
            ar.validate_record(record, schema, label="synthetic-preview")


class ExpandedV2HistoryTests(unittest.TestCase):
    def test_native_v2_rediscovery_then_merit_refutation_resolves_history(self):
        for rediscover in (False, True):
            with self.subTest(rediscover=rediscover):
                native = native_helpers.V2PendingCliTests()
                native.setUp()
                try:
                    run = native.screen_run(copies=2, status="not_credible",
                        criterion="outside_requirement",
                        fact="The pinned primary source implements a different frozen requirement.")
                    if rediscover:
                        proposal = {"repository": native_helpers.SURV,
                                    "evidence": [native_helpers.SURV]}
                        run["first"][0]["claude_discover"]["proposed"] = [proposal]
                        run["first"][0]["merged"] = [proposal]
                    converted = native.convert_cli(run)
                    retained = native.retain_v2_result(converted)
                    ledger = sl.append(native.root, native.ledger(), json.loads(retained.read_bytes()))
                    native_helpers.write(native.root, fs.LEDGER, ledger)
                    self.assertEqual(sl.check_ledger(native.root, ledger), [])
                    layer = ledger["sweeps"][-1]["layers"][0]
                    self.assertEqual(sl.material_pending(layer), [])
                    member = next(row for row in layer["eligible_field"]
                                  if row["repository"] == native_helpers.SURV)
                    self.assertEqual(member["disposition"], "refuted")
                    if rediscover:
                        self.assertTrue(any("/raw/alpha/0/" in ref for ref in member["evidence_refs"]))
                    row = {"catalog": "foundation", "layer_id": "alpha",
                           "winners": [], "alternatives": []}
                    covering = fs.final_covering_sweeps(ledger, ("foundation", "alpha"))
                    self.assertEqual(fs.final_unresolved_survivors(fs.Sources(native.root), row, covering), [])
                finally:
                    native.tearDown()
