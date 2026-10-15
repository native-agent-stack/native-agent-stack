"""Evidence qualification controls, independent of the disabled admission switch."""

import json
import hashlib
from pathlib import Path
import tempfile
import unittest

from scripts import angle_records as ar
from scripts import final_stack as fs
from tests.test_final_admission import FinalAdmissionTests
from tests.test_final_stack import COMMIT_A, FixtureTestCase, _angle_fixture, _layer, _sweep, _winner
from tests.test_saturation_ledger import sl_rechain
from tests import test_saturation_ledger as ledger_helpers
from scripts import saturation_ledger as sl
from tests import test_layer_verdicts as wave_helpers
from tests import test_local_pages_architecture_manifest as view_helpers
from tests import test_record_verdicts as recorder_helpers

ROOT = Path(__file__).resolve().parents[1]


class AngleCitationFileTests(unittest.TestCase):
    def validate_path(self, path):
        record = _angle_fixture()
        candidate = record["candidates"][0]
        candidate["angles"]["A1"]["sources"] = [{
            "kind": "repo", "repository": candidate["repository"],
            "pin": COMMIT_A, "path": path, "line": 1,
        }]
        schema = json.loads((ROOT / ar.SCHEMA).read_text())
        ar.validate_record(record, schema, label="synthetic")

    def test_repository_citation_refuses_directory_aliases_without_final(self):
        for path in (".", "src/", "src/.", "././", "README.md\n"):
            with self.subTest(path=path):
                with self.assertRaisesRegex(ar.AngleRecordError, "schema failure"):
                    self.validate_path(path)

    def test_repository_citation_retains_safe_relative_files(self):
        for path in ("README.md", "./README.md", "src/./module.py", ".github/workflows/test.yml"):
            with self.subTest(path=path):
                self.validate_path(path)


class RetainedReturnPolicyTests(unittest.TestCase):
    def test_empty_v1_sweep_without_retained_discovery_is_not_unchanged(self):
        for votes in (None, "not_retained", "not_returned"):
            with self.subTest(votes=votes), tempfile.TemporaryDirectory() as folder:
                row = {"catalog": "foundation", "layer_id": "alpha", "requirement_sha256": "a" * 64,
                       "platform_profiles_sha256": "b" * 64, "reopen": [], "proposed": [],
                       "refuted": [], "survived": []}
                baseline = {"record": {"status": "completed", "layers": [dict(row)]}}
                later = {"sweep_id": "after", "date": "2026-09-22",
                         "record": {"status": "completed", "layers": [{**row, "votes": votes}]}}
                result = fs.final_reopened_by(fs.Sources(Path(folder)), ("foundation", "alpha"),
                                             [later], baseline)
                self.assertEqual(result, [{"sweep_id": "after", "date": "2026-09-22"}])


class NativeHistoryQualificationTests(FixtureTestCase):
    prepare = FinalAdmissionTests.prepare
    measured = FinalAdmissionTests.measured
    matrix = FinalAdmissionTests.matrix
    native_fixture = FinalAdmissionTests.native_cutoff_fixture

    def qualification(self, root):
        source = fs.Sources(root)
        ledger = source.json(fs.LEDGER)
        row = source.json("catalogs/landscape/foundation.json")["layers"][0]
        return fs.qualify_final_history(source, ("foundation", "alpha"),
                                        ledger["sweeps"][0]["manifest_ref"], row)

    def qualification_packet(self, root):
        # Build the ordinary projection through native builders. Only the
        # qualification packet carries a prospective FINAL marker; the real
        # repository claim is restored and still refuses production admission.
        paths = [root / "catalogs/landscape/foundation.json",
                 root / ar.DIRECTORY / "foundation-alpha.json"]
        original = {path: path.read_bytes() for path in paths}
        try:
            for path in paths:
                document = json.loads(original[path])
                document.pop("terminal_state", None)
                for row in document.get("layers", []):
                    row.pop("terminal_state", None)
                path.write_text(json.dumps(document) + "\n")
            self.matrix(root)
            document = fs.build_document(root)
        finally:
            for path, raw in original.items():
                path.write_bytes(raw)
        self.layer(document, "alpha")["terminal_state"] = "FINAL"
        source = fs.Sources(root)
        return source, document, ar.load_records(source)

    def test_full_native_evidence_qualifies_without_enabling_admission(self):
        root = self.native_fixture("requirement_sha256", "completed", refutation=True)
        source, document, angles = self.qualification_packet(root)
        result = fs.qualify_final_requirements(source, document["layers"], document["runs"], angles)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["status"], "qualified")
        self.assertIs(result[0]["admission_enabled"], False)
        self.assert_final_disabled(root)

    def test_qualification_packet_cannot_replace_the_current_recorded_winner(self):
        root = self.native_fixture("requirement_sha256", "completed", refutation=True)
        _, document, angles = self.qualification_packet(root)
        path = root / "catalogs/landscape/foundation.json"
        catalog = json.loads(path.read_bytes())
        catalog["layers"][0]["winners"][0]["pin"] = "b" * 40
        path.write_text(json.dumps(catalog) + "\n")
        with self.assertRaisesRegex(fs.FinalStackError, "current recorded winners"):
            fs.qualify_final_requirements(fs.Sources(root), document["layers"], document["runs"], angles)

    def test_qualification_requires_fresh_run_and_angle_inputs(self):
        for changed in ("run", "angle"):
            with self.subTest(changed=changed):
                root = self.native_fixture("requirement_sha256", "completed", refutation=True)
                _, document, angles = self.qualification_packet(root)
                if changed == "run":
                    path = root / fs.STACK
                    data = json.loads(path.read_bytes())
                    next(c for c in data["components"] if c["id"] == "widget")["source_pin"] = "b" * 40
                else:
                    path = root / angles[("foundation", "alpha")]["path"]
                    data = json.loads(path.read_bytes())
                    candidate = data["candidates"][0]
                    candidate.update(a6_comparative=False, provisional=True)
                    candidate["angles"]["A6"].update(score="U", sources=[])
                path.write_text(json.dumps(data) + "\n")
                with self.assertRaisesRegex(fs.FinalStackError, "current (run pins|angle evidence)"):
                    fs.qualify_final_requirements(fs.Sources(root), document["layers"], document["runs"], angles)

    def test_malformed_uri_in_an_additional_e2e_citation_is_refused(self):
        root = self.native_fixture("requirement_sha256", "completed", refutation=True)
        source, document, angles = self.qualification_packet(root)
        record = angles[("foundation", "alpha")]["record"]
        path = root / record["final_evidence"][0]["e2e_receipt"]
        receipt = json.loads(path.read_bytes())
        receipt["upstream_sources"].append({"kind": "repo", "repository": "https://%ZZ",
                                            "pin": COMMIT_A, "path": "README.md", "line": 1})
        path.write_text(json.dumps(receipt) + "\n")
        with self.assertRaisesRegex(fs.FinalStackError, "condition 3.*URI"):
            fs.qualify_final_requirements(fs.Sources(root), document["layers"], document["runs"], angles)

    def test_invocation_window_uses_explicit_utc_z_policy_and_order(self):
        root = self.native_fixture("requirement_sha256", "completed", refutation=True)
        source, document, angles = self.qualification_packet(root)
        fs.qualify_final_requirements(source, document["layers"], document["runs"], angles)
        path = root / angles[("foundation", "alpha")]["record"]["final_evidence"][0]["invoke_receipt"]
        receipt = json.loads(path.read_bytes())
        for start, end in (("2026-10-12T20:00:00+00:00", "2026-10-12T21:00:00+00:00"),
                           ("2026-10-12T21:00:00+01:00", "2026-10-12T22:00:00+01:00"),
                           ("2026-10-12T21:00:00Z", "2026-10-12T21:00:00Z")):
            with self.subTest(start=start):
                receipt.update(window_start=start, window_end=end)
                path.write_text(json.dumps(receipt) + "\n")
                with self.assertRaisesRegex(fs.FinalStackError, "condition 4.*measured window"):
                    fs.qualify_final_requirements(fs.Sources(root), document["layers"], document["runs"], angles)

    def test_complete_native_v2_history_qualifies_evidence_but_never_admits_final(self):
        root = self.native_fixture("requirement_sha256", "completed", refutation=True)
        result = self.qualification(root)
        self.assertEqual(result["status"], "qualified")
        self.assertIs(result["admission_enabled"], False)
        self.assertEqual(len(result["checked_sweeps"]), 2)
        self.assert_final_disabled(root)

    def test_missing_native_v2_projection_is_refused_before_replay(self):
        for field in ("eligible_field", "pending", "proposed", "manifest_ref"):
            with self.subTest(field=field):
                root = self.native_fixture("requirement_sha256", "completed", refutation=True)
                ledger = json.loads((root / fs.LEDGER).read_bytes())
                target = ledger["sweeps"][-1] if field == "manifest_ref" else ledger["sweeps"][-1]["layers"][0]
                target.pop(field)
                # Retained evidence remains intact; recompute the chain so this
                # control reaches semantic integrity, rather than a stale hash.
                (root / fs.LEDGER).write_text(json.dumps(sl_rechain(ledger)) + "\n")
                with self.assertRaisesRegex(fs.FinalStackError, "native ledger integrity"):
                    self.qualification(root)

    def test_retained_raw_failure_cannot_be_hidden_by_valid_looking_projection(self):
        root = self.native_fixture("requirement_sha256", "completed", refutation=True)
        self.assertEqual(self.qualification(root)["status"], "qualified")
        ledger = json.loads((root / fs.LEDGER).read_bytes())
        later = ledger["sweeps"][-1]
        retained_path = root / later["returns_ref"]
        retained = json.loads(retained_path.read_bytes())
        retained["raw"]["alpha"][-1]["lost"] = True
        retained_path.write_text(json.dumps(retained) + "\n")
        later["returns_sha256"] = hashlib.sha256(retained_path.read_bytes()).hexdigest()
        (root / fs.LEDGER).write_text(json.dumps(sl_rechain(ledger)) + "\n")
        ledger_helpers.register(root)
        errors = sl.check_ledger(root, sl_rechain(ledger))
        self.assertTrue(errors)
        self.assertFalse(any("sha256" in error for error in errors), errors)
        with self.assertRaisesRegex(fs.FinalStackError, "native ledger integrity"):
            self.qualification(root)
        self.assert_final_disabled(root)

    def test_native_v1_history_requires_retained_same_index_survivor_disposition(self):
        native = ledger_helpers.FixtureCase()
        native.setUp()
        self.addCleanup(native.tearDown)
        ledger = native.appended(ledger_helpers.result())
        (native.root / fs.LEDGER).write_text(json.dumps(ledger) + "\n")
        row = {"catalog": "foundation", "layer_id": "alpha", "winners": [], "alternatives": []}
        consumed = ledger["sweeps"][0]["manifest_ref"]
        with self.assertRaisesRegex(fs.FinalStackError, "unresolved survivors"):
            fs.qualify_final_history(fs.Sources(native.root), ("foundation", "alpha"), consumed, row)
        row["winners"] = [{"repository": ledger_helpers.SURV,
                           "evidence_refs": [fs.LEDGER + "#/sweeps/0"]}]
        result = fs.qualify_final_history(fs.Sources(native.root), ("foundation", "alpha"), consumed, row)
        self.assertEqual(result["status"], "qualified")
        self.assertIs(result["admission_enabled"], False)

    def test_native_stopped_or_changed_history_never_qualifies(self):
        for field in ("requirement_sha256", "platform_profiles_sha256"):
            for status in ("completed", "stopped"):
                with self.subTest(field=field, status=status):
                    root = self.native_fixture(field, status)
                    with self.assertRaisesRegex(fs.FinalStackError, "incomplete, changed or pending"):
                        self.qualification(root)

    def test_missing_consumed_anchor_refuses_even_with_complete_history(self):
        root = self.native_fixture("requirement_sha256", "completed", refutation=True)
        source = fs.Sources(root)
        row = source.json("catalogs/landscape/foundation.json")["layers"][0]
        with self.assertRaisesRegex(fs.FinalStackError, "one retained consumed"):
            fs.qualify_final_history(source, ("foundation", "alpha"), "missing-manifest.json", row)


class RetainedSnapshotConsumerTests(FixtureTestCase):
    def test_non_final_terminal_conflict_remains_a_conflict(self):
        with self.assertRaisesRegex(fs.FinalStackError, "conflicting terminal-state claims"):
            fs.terminal_state({"terminal_state": "SCHEDULED"}, {"terminal_state": "RETIRED"})

    def test_retained_final_snapshot_never_counts_as_current_qualification(self):
        document = self.build(foundation=[_layer("layer-a", winners=[_winner("widget")])],
                              sweeps=[_sweep("anchor", "2026-09-22", [("foundation", "layer-a")])])
        self.assertTrue(fs.is_definitive(document, "widget", "2026-09-22"))
        self.layer(document, "layer-a")["terminal_state"] = "FINAL"
        result = fs.is_definitive(document, "widget", "2026-09-22")
        self.assertFalse(result)
        self.assertEqual(result.reason, fs.FINAL_ADMISSION_REFUSAL)
        with self.assertRaisesRegex(fs.FinalStackError, "^admission under redesign$"):
            fs.flags(document, None)

    def test_wave_projection_does_not_turn_a_final_alias_into_current_adoption(self):
        row = {"layer_id": "alpha", "verdict_status": "recorded", "winners": []}
        self.assertEqual(wave_helpers.build_verdicts.build_verdict_row(row, [])["verdict_status"], "recorded")
        row["verdict_status"] = "FINAL"
        with self.assertRaisesRegex(ValueError, "^admission under redesign$"):
            wave_helpers.build_verdicts.build_verdict_row(row, [])

    def test_matrix_projection_leaves_final_unreported(self):
        self.assertEqual(view_helpers.MANIFEST.layer_status("recorded"), "adopted")
        self.assertEqual(view_helpers.MANIFEST.layer_status("FINAL"), "unreported")

    def test_layer_builder_refuses_a_plain_restored_final_row(self):
        document = {"layers": [{"catalog": "foundation", "layer_id": "alpha", "terminal_state": "FINAL"}]}
        with self.assertRaisesRegex(ValueError, "successful current admission check"):
            view_helpers.MANIFEST.layer_manifest(self.root(), "foundation", document, {}, {},
                                                 commit=None, sources=[], flags=None)

    def test_layer_builder_refuses_current_final_claim_even_with_an_ordinary_snapshot(self):
        for source in ("catalog", "matrix"):
            with self.subTest(source=source):
                row = {"layer_id": "alpha", "catalog": "foundation", "verdict_status": "FINAL"}
                catalog = {"layers": [row]} if source == "catalog" else {}
                matrix = {"rows": [row]} if source == "matrix" else {}
                with self.assertRaisesRegex(ValueError, "successful current admission check"):
                    view_helpers.MANIFEST.layer_manifest(self.root(), "foundation", {"layers": []}, catalog, matrix,
                                                         commit=None, sources=[], flags=None)


class AppendFinalRefusalTests(recorder_helpers.NewWaveFixture):
    def test_append_refuses_an_unnamed_final_row_before_any_write_and_recovers(self):
        catalog = self.both_lanes("wave-same-layer")
        self.assertEqual(self.run_wave()[0], 0)
        work_temp = tempfile.TemporaryDirectory()
        self.addCleanup(work_temp.cleanup)
        self.work_dir = Path(work_temp.name).resolve()
        self.packets = recorder_helpers.PacketWriter(self.work_dir)
        self.both_lanes("wave-append-layer")
        relative = recorder_helpers.record_verdicts.LEDGER_FILES[catalog]
        path = self.root / relative
        original = path.read_bytes()
        document = json.loads(original)
        next(row for row in document["layers"] if row["layer_id"] == "wave-same-layer")["terminal_state"] = "FINAL"
        path.write_text(json.dumps(document) + "\n")
        before = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        for _ in range(2):
            with self.assertRaisesRegex(ValueError, "^admission under redesign$"):
                self.run_wave(extra=["--append-rows", "foundation/wave-append-layer"])
            self.assertEqual({p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}, before)
        path.write_bytes(original)
        code, output = self.run_wave(extra=["--append-rows", "foundation/wave-append-layer"])
        self.assertEqual(code, 0, output)


del FinalAdmissionTests


if __name__ == "__main__":
    unittest.main()
