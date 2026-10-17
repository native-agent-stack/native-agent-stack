"""Disabled FINAL lifecycle scenarios and independent retained-metadata controls.

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
        try:
            document, violations = cm.build_document(root)
        except ValueError as error:
            # FINAL now refuses at the matrix seam before final-stack reads it.
            self.assertEqual(str(error), "admission under redesign")
            return
        self.assertEqual(violations, [])
        _write_json(root / fs.MATRIX, document)

    def sweep(self, root, day, *, ident="later", survived=(), refuted=(), reopen=()):
        path = root / fs.LEDGER
        ledger = json.loads(path.read_bytes())
        record = _sweep(ident, day, [("foundation", "layer-a")])
        record["manifest_ref"] = f"catalogs/sota-convergence/manifest-{day.replace('-', '')}-{ident}.json"
        record["layers"][0].update(requirement_sha256="a" * 64, platform_profiles_sha256="a" * 64)
        record["layers"][0].update(proposed=list(survived),
                                   survived=[{"repo": repo} for repo in survived],
                                   refuted=list(refuted), reopen=list(reopen))
        ledger["sweeps"].append(record)
        _write_json(path, ledger)
        _write_json(root / record["manifest_ref"], {"checked_at": day})
        self.matrix(root)

    def test_final_disabled_with_unchanged_later_covering_sweep(self):
        root, _, _ = self.measured()
        self.sweep(root, "2026-09-23")
        self.assert_final_disabled(root)

    def test_unswept_layer_cannot_be_final(self):
        root, _, _ = self.measured()
        path = root / fs.LEDGER
        ledger = json.loads(path.read_bytes())
        ledger["sweeps"] = []
        _write_json(path, ledger)
        self.matrix(root)
        self.assert_final_disabled(root)

    def test_final_disabled_with_changed_or_unchanged_covering_scope(self):
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
                    if scenario == "prior_change_only":
                        ledger["sweeps"].sort(key=lambda sweep: sweep["date"])
                    for sweep in ledger["sweeps"]:
                        sweep["layers"][0][field] = ("b" if
                            (scenario.startswith("changed") and sweep["date"] == "2026-09-23") or
                            (scenario == "prior_change_only" and sweep["date"] == "2026-09-21")
                            else "a") * 64
                    _write_json(path, ledger)
                    self.matrix(root)
                    self.assert_final_disabled(root)

    def test_post_verdict_scope_hashes_without_baseline_refuse_final(self):
        for field in ("requirement_sha256", "platform_profiles_sha256"):
            for baseline in ("absent", "missing_hash"):
                for later_hash in ("a", "b"):
                    with self.subTest(field=field, baseline=baseline, later_hash=later_hash):
                        root, _, _ = self.measured()
                        self.sweep(root, "2026-09-23", ident="first-after")
                        self.sweep(root, "2026-09-24", ident="changed-after")
                        path = root / fs.LEDGER
                        ledger = json.loads(path.read_bytes())
                        if baseline == "absent":
                            ledger["sweeps"] = [sweep for sweep in ledger["sweeps"]
                                                if sweep["date"] > "2026-09-22"]
                        for sweep in ledger["sweeps"]:
                            row = sweep["layers"][0]
                            row.update(requirement_sha256="a" * 64, platform_profiles_sha256="a" * 64)
                            if sweep["date"] == "2026-09-22":
                                row.pop(field)
                            elif sweep["date"] == "2026-09-24":
                                row[field] = later_hash * 64
                        _write_json(path, ledger)
                        self.matrix(root)
                        self.assert_final_disabled(root)

    def test_final_disabled_with_unchanged_scope_and_retained_baseline(self):
        root, _, _ = self.measured()
        self.sweep(root, "2026-09-23", ident="first-after")
        self.sweep(root, "2026-09-24", ident="unchanged-after")
        path = root / fs.LEDGER
        ledger = json.loads(path.read_bytes())
        for sweep in ledger["sweeps"]:
            sweep["layers"][0].update(requirement_sha256="a" * 64, platform_profiles_sha256="a" * 64)
        _write_json(path, ledger)
        self.matrix(root)
        self.assert_final_disabled(root)

    def test_same_day_scope_change_after_consumed_sweep_refuses_final(self):
        for field in ("requirement_sha256", "platform_profiles_sha256"):
            for ident in ("same-day-after", "a-after"):
                with self.subTest(field=field, ident=ident):
                    root, _, _ = self.measured()
                    self.sweep(root, "2026-09-22", ident=ident)
                    path = root / fs.LEDGER
                    ledger = json.loads(path.read_bytes())
                    for sweep in ledger["sweeps"]:
                        sweep["layers"][0].update(requirement_sha256="a" * 64,
                                                   platform_profiles_sha256="a" * 64)
                    ledger["sweeps"][-1]["layers"][0][field] = "b" * 64
                    _write_json(path, ledger)
                    self.matrix(root)
                    self.assert_final_disabled(root)

    def test_final_disabled_with_same_day_reopen(self):
        for retained in (True, False):
            with self.subTest(retained=retained):
                root, _, _ = self.measured()
                path = "evidence/artifacts/fixture/same-day-change.json"
                if retained:
                    _write_json(root / path, {"change": {"from": "1.0.0", "to": "1.1.0"}})
                self.sweep(root, "2026-09-22", ident="same-day-after",
                           reopen=[{"trigger": "pin_moved", "ref": path + "#/change"}])
                self.assert_final_disabled(root)

    def test_final_disabled_with_same_day_consumed_sweep(self):
        root, _, _ = self.measured()
        self.sweep(root, "2026-09-22", ident="same-day-consumed")
        path = root / fs.LEDGER
        ledger = json.loads(path.read_bytes())
        for i, sweep in enumerate(ledger["sweeps"]):
            sweep["layers"][0].update(requirement_sha256=("a" if i == 0 else "b") * 64,
                                       platform_profiles_sha256=("a" if i == 0 else "b") * 64)
        _write_json(path, ledger)
        registry = root / fs.WAVE_REGISTRY
        waves = json.loads(registry.read_bytes())
        waves["waves"][0]["manifest"] = ledger["sweeps"][-1]["manifest_ref"]
        _write_json(registry, waves)
        self.matrix(root)
        self.assert_final_disabled(root)

    def test_final_disabled_with_missing_or_ambiguous_consumed_sweep(self):
        for missing in ("manifest", "match", "covering_layer", "ambiguous"):
            with self.subTest(missing=missing):
                root, _, _ = self.measured()
                registry = root / fs.WAVE_REGISTRY
                waves = json.loads(registry.read_bytes())
                path = root / fs.LEDGER
                ledger = json.loads(path.read_bytes())
                if missing == "manifest":
                    waves["waves"][0].pop("manifest")
                elif missing == "match":
                    waves["waves"][0]["manifest"] = "catalogs/sota-convergence/unconsumed.json"
                elif missing == "covering_layer":
                    ledger["sweeps"][0]["layers"][0]["layer_id"] = "another-layer"
                    self.sweep(root, "2026-09-23")
                    ledger["sweeps"].append(json.loads(path.read_bytes())["sweeps"][-1])
                else:
                    ledger["sweeps"].append({**ledger["sweeps"][0], "sweep_id": "same-manifest"})
                _write_json(path, ledger)
                _write_json(registry, waves)
                self.matrix(root)
                self.assert_final_disabled(root)

    def test_final_disabled_with_retained_or_missing_change_receipt(self):
        for retained in (True, False):
            with self.subTest(retained=retained):
                root, _, _ = self.measured()
                path = "evidence/artifacts/fixture/change.json"
                if retained:
                    _write_json(root / path, {"change": {"from": "1.0.0", "to": "1.1.0"}})
                self.sweep(root, "2026-09-23", reopen=[{"trigger": "pin_moved", "ref": path + "#/change"}])
                self.assert_final_disabled(root)

    def test_same_day_and_older_omitted_survivors_block_final(self):
        for day in ("2026-09-21", "2026-09-22"):
            with self.subTest(day=day):
                root, _, _ = self.measured()
                self.sweep(root, day, survived=["https://github.com/example/challenger"])
                self.assert_final_disabled(root)

    def test_final_disabled_with_missing_return_or_unretained_disposition(self):
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
                self.assert_final_disabled(root)

    def test_final_disabled_with_later_omission_or_missing_vote(self):
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
                self.assert_final_disabled(root)

    def test_final_disabled_with_retained_disposition_or_substantive_refutation(self):
        for settlement in ("catalog", "refutation"):
            with self.subTest(settlement=settlement):
                root, _, _ = self.measured()
                repository = "https://github.com/example/challenger"
                self.sweep(root, "2026-09-21", ident="earlier", survived=[repository])
                evidence = "evidence/artifacts/fixture/disposition.json"
                if settlement == "catalog":
                    _write_json(root / evidence, {"reason": "Outside this frozen role.", "sweep_id": "earlier"})
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
                self.assert_final_disabled(root)

    def metadata(self, record, field, path):
        candidate = record["candidates"][0]
        source = {"kind": "receipt", "path": path}
        if field == "entitlement":
            candidate[field] = {"status": "documented", "sources": [source], "note": "Synthetic entitlement."}
        else:
            candidate[field] = {"spdx_id": "MIT", "source": source,
                "read_at": candidate["angles"]["A1"]["read_at"], "note": "Synthetic compliance metadata."}

    def test_missing_metadata_refuses_ordinary_records_after_final_policy(self):
        for field in ("entitlement", "licence_note"):
            with self.subTest(field=field):
                root, path, record = self.measured()
                receipt = "evidence/artifacts/fixture/metadata.json"
                self.metadata(record, field, receipt)
                _write_json(path, record)
                self.assert_final_disabled(root)
                catalog_path = root / "catalogs/landscape/foundation.json"
                catalog = json.loads(catalog_path.read_bytes())
                catalog["layers"][0].pop("terminal_state", None)
                _write_json(catalog_path, catalog)
                self.fresh_reject(root, receipt + " is missing")

    def test_metadata_receipts_are_hashed_and_edits_invalidate_check(self):
        for field in ("entitlement", "licence_note"):
            with self.subTest(field=field):
                root, path, record = self.measured()
                receipt = "evidence/artifacts/fixture/metadata.json"
                _write_json(root / receipt, {"observed": "first"})
                self.metadata(record, field, receipt)
                _write_json(path, record)
                # Source hashing remains active for ordinary, non-FINAL records.
                catalog_path = root / "catalogs/landscape/foundation.json"
                catalog = json.loads(catalog_path.read_bytes())
                catalog["layers"][0].pop("terminal_state", None)
                _write_json(catalog_path, catalog)
                document = fs.build_document(root)
                self.assertIn(receipt, document["sources"])
                _write(root / fs.OUTPUT, fs.serialize(document))
                _write_json(root / receipt, {"observed": "second"})
                code, output = self.run_main(root, "--check")
                self.assertEqual(code, 1, output)
                self.assertIn("sources: " + receipt + " sha256 changed", output)
