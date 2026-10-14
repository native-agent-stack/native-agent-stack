"""Scope-locked FINAL lifecycle and retained-metadata controls.

Every execution receipt and sweep in these controls is synthetic. Fresh-output
refusals distinguish FINAL evidence checks from unrelated output drift.
"""

import json

from scripts import component_matrix as cm
from scripts import final_stack as fs
from tests import test_angle_records_fix1 as fix1
from tests import test_final_stack as helpers
from tests.test_final_stack import FixtureTestCase, REPO_ROOT, _sweep, _write, _write_json


class FinalIntegrityTests(FixtureTestCase):
    prepare = helpers.AngleEnforcementTests.prepare
    measured = fix1.FinalFix1Tests.measured
    fresh_reject = fix1.FinalFix1Tests.fresh_reject

    def matrix(self, root):
        _write(root / "adoption/host-receipt.schema.json",
               (REPO_ROOT / "adoption/host-receipt.schema.json").read_text())
        document, violations = cm.build_document(root)
        self.assertEqual(violations, [])
        _write_json(root / fs.MATRIX, document)

    def sweep(self, root, day, *, ident="later", survived=(), refuted=(), reopen=()):
        path = root / fs.LEDGER
        ledger = json.loads(path.read_bytes())
        record = _sweep(ident, day, [("foundation", "layer-a")])
        record["layers"][0].update(proposed=list(survived),
                                   survived=[{"repo": repo} for repo in survived],
                                   refuted=list(refuted), reopen=list(reopen))
        ledger["sweeps"].append(record)
        _write_json(path, ledger)
        _write_json(root / record["manifest_ref"], {"checked_at": day})
        self.matrix(root)

    def test_final_survives_a_later_covering_sweep_without_change_evidence(self):
        root, _, _ = self.measured()
        self.sweep(root, "2026-09-23")
        code, output = self.run_main(root, "--write")
        self.assertEqual(code, 0, output)
        layer = self.layer(json.loads((root / fs.OUTPUT).read_bytes()), "layer-a")
        self.assertEqual(layer["terminal_state"], "FINAL")
        self.assertNotEqual(layer["status"], "reopened")
        self.assertEqual(layer["verdict"]["reopened_by"], [])

    def test_unswept_layer_cannot_be_final(self):
        root, _, _ = self.measured()
        path = root / fs.LEDGER
        ledger = json.loads(path.read_bytes())
        ledger["sweeps"] = []
        _write_json(path, ledger)
        self.matrix(root)
        self.fresh_reject(root, "non-definitive status unswept cannot be FINAL")

    def test_covering_scope_hash_change_reopens_final(self):
        for field in ("requirement_sha256", "platform_profiles_sha256"):
            for scenario in ("changed", "changed_then_reverted", "prior_change_only", "unchanged"):
                with self.subTest(field=field, scenario=scenario):
                    root, _, _ = self.measured()
                    if scenario == "prior_change_only":
                        self.sweep(root, "2026-09-21", ident="older")
                    self.sweep(root, "2026-09-23")
                    if scenario == "changed_then_reverted":
                        self.sweep(root, "2026-09-24", ident="reverted")
                    path = root / fs.LEDGER
                    ledger = json.loads(path.read_bytes())
                    for sweep in ledger["sweeps"]:
                        sweep["layers"][0][field] = ("b" if
                            (scenario.startswith("changed") and sweep["date"] == "2026-09-23") or
                            (scenario == "prior_change_only" and sweep["date"] == "2026-09-21")
                            else "a") * 64
                    _write_json(path, ledger)
                    self.matrix(root)
                    if scenario.startswith("changed"):
                        self.fresh_reject(root, "reopened sweep delta must be adjudicated")
                    else:
                        code, output = self.run_main(root, "--write")
                        self.assertEqual(code, 0, output)
                        document = json.loads((root / fs.OUTPUT).read_bytes())
                        layer = self.layer(document, "layer-a")
                        self.assertEqual(layer["terminal_state"], "FINAL")
                        self.assertEqual(layer["verdict"]["reopened_by"], [])

    def test_retained_change_reopens_final_and_its_receipt_is_required(self):
        for retained in (True, False):
            with self.subTest(retained=retained):
                root, _, _ = self.measured()
                path = "evidence/artifacts/fixture/change.json"
                if retained:
                    _write_json(root / path, {"change": {"from": "1.0.0", "to": "1.1.0"}})
                self.sweep(root, "2026-09-23", reopen=[{"trigger": "pin_moved", "ref": path + "#/change"}])
                reason = ("reopened sweep delta must be adjudicated" if retained
                          else "FINAL reopening requires retained change evidence")
                self.fresh_reject(root, reason)

    def test_same_day_and_older_omitted_survivors_block_final(self):
        for day in ("2026-09-21", "2026-09-22"):
            with self.subTest(day=day):
                root, _, _ = self.measured()
                self.sweep(root, day, survived=["https://github.com/example/challenger"])
                self.fresh_reject(root, "cumulative unresolved survivors require retained dispositions")

    def test_missing_return_or_unretained_catalog_disposition_does_not_settle(self):
        for disposition in (False, True):
            with self.subTest(disposition=disposition):
                root, _, _ = self.measured()
                repo = "https://github.com/example/challenger"
                self.sweep(root, "2026-09-21", survived=[repo])
                if disposition:
                    path = root / "catalogs/landscape/foundation.json"
                    catalog = json.loads(path.read_bytes())
                    catalog["layers"][0]["alternatives"] = [{"name": "Challenger", "repository": repo,
                        "disposition": "out_of_scope", "why_not_default": "Reason without retained evidence.",
                        "evidence_refs": []}]
                    _write_json(path, catalog)
                    self.matrix(root)
                else:
                    path = root / fs.LEDGER
                    ledger = json.loads(path.read_bytes())
                    layer = ledger["sweeps"][-1]["layers"][0]
                    layer.update(survived=[], refuted=[])
                    _write_json(path, ledger)
                self.fresh_reject(root, "cumulative unresolved survivors require retained dispositions")

    def test_later_omission_and_missing_vote_do_not_settle_survivors(self):
        for missing in (False, True):
            with self.subTest(missing_vote=missing):
                root, _, _ = self.measured()
                repository = "https://github.com/example/challenger"
                self.sweep(root, "2026-09-21", ident="earlier", survived=[repository])
                refuted = []
                if missing:
                    vote = "evidence/artifacts/fixture/missing-vote.json"
                    _write_json(root / vote, {"refuted": True, "missing": True})
                    refuted = [{"repo": repository, "facts": {"vote": "refuted", "ref": vote}}]
                self.sweep(root, "2026-09-22", refuted=refuted)
                self.fresh_reject(root, "cumulative unresolved survivors require retained dispositions")

    def test_explicit_retained_catalog_disposition_or_substantive_refutation_settles_survivor(self):
        for settlement in ("catalog", "refutation"):
            with self.subTest(settlement=settlement):
                root, _, _ = self.measured()
                repository = "https://github.com/example/challenger"
                self.sweep(root, "2026-09-21", ident="earlier", survived=[repository])
                evidence = "evidence/artifacts/fixture/disposition.json"
                if settlement == "catalog":
                    _write_json(root / evidence, {"reason": "Outside this frozen role."})
                    path = root / "catalogs/landscape/foundation.json"
                    catalog = json.loads(path.read_bytes())
                    catalog["layers"][0]["alternatives"] = [{"name": "Challenger", "repository": repository,
                        "disposition": "out_of_scope", "why_not_default": "Outside this frozen role.",
                        "evidence_class": "source_review", "evidence_refs": [evidence]}]
                    _write_json(path, catalog)
                    self.matrix(root)
                else:
                    _write_json(root / evidence, {"refuted": True, "missing": False})
                    self.sweep(root, "2026-09-22", refuted=[{"repo": repository,
                        "facts": {"vote": "refuted", "ref": evidence}}])
                code, output = self.run_main(root, "--write")
                self.assertEqual(code, 0, output)
                document = json.loads((root / fs.OUTPUT).read_bytes())
                self.assertEqual(self.layer(document, "layer-a")["survivors"], [])
                self.assertIn(evidence, document["sources"])

    def metadata(self, record, field, path):
        candidate = record["candidates"][0]
        source = {"kind": "receipt", "path": path}
        if field == "entitlement":
            candidate[field] = {"status": "documented", "sources": [source], "note": "Synthetic entitlement."}
        else:
            candidate[field] = {"spdx_id": "MIT", "source": source,
                "read_at": candidate["angles"]["A1"]["read_at"], "note": "Synthetic compliance metadata."}

    def test_metadata_receipts_must_exist_before_final(self):
        for field in ("entitlement", "licence_note"):
            with self.subTest(field=field):
                root, path, record = self.measured()
                receipt = "evidence/artifacts/fixture/metadata.json"
                self.metadata(record, field, receipt)
                _write_json(path, record)
                self.fresh_reject(root, receipt + " is missing")

    def test_metadata_receipts_are_hashed_and_edits_invalidate_check(self):
        for field in ("entitlement", "licence_note"):
            with self.subTest(field=field):
                root, path, record = self.measured()
                receipt = "evidence/artifacts/fixture/metadata.json"
                _write_json(root / receipt, {"observed": "first"})
                self.metadata(record, field, receipt)
                _write_json(path, record)
                document = fs.build_document(root)
                self.assertIn(receipt, document["sources"])
                _write(root / fs.OUTPUT, fs.serialize(document))
                _write_json(root / receipt, {"observed": "second"})
                code, output = self.run_main(root, "--check")
                self.assertEqual(code, 1, output)
                self.assertIn("sources: " + receipt + " sha256 changed", output)
