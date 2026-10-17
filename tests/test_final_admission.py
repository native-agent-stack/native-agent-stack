"""Disabled FINAL controls through native ledger conversion and the public CLI."""

import copy
import hashlib
import importlib.util
import json
import sys

from scripts import final_stack as fs
from scripts import saturation_ledger as sl
from tests.test_angle_records_fix3 import FinalIntegrityTests
from tests.test_final_stack import FixtureTestCase, REPO_ROOT, _write_json
from tests import test_saturation_ledger as ledger_helpers


class FinalAdmissionTests(FixtureTestCase):
    prepare = FinalIntegrityTests.prepare
    measured = FinalIntegrityTests.measured
    matrix = FinalIntegrityTests.matrix
    sweep = FinalIntegrityTests.sweep

    def write_result(self, root):
        try:
            code, output = self.run_main(root, "--write")
            if code == 1:
                self.assertIn(fs.FINAL_ADMISSION_REFUSAL, output)
            return code, output
        except SystemExit as error:
            self.assertIsInstance(error.code, str)
            self.assertIn("component_matrix: catalogs/saturation/ledger.json", error.code)
            return 1, error.code

    def test_every_post_anchor_status_outside_completed_refuses(self):
        for status in ("stopped", "partial", "cutoff", "unknown", None, "", "COMPLETED"):
            with self.subTest(status=status):
                root, _, _ = self.measured()
                self.sweep(root, "2026-09-22", ident="status-after")
                path = root / fs.LEDGER
                ledger = json.loads(path.read_bytes())
                ledger["sweeps"][-1]["status"] = status
                if status is None:
                    ledger["sweeps"][-1].pop("status")
                _write_json(path, ledger)
                if status == "stopped":
                    self.matrix(root)
                code, output = self.write_result(root)
                self.assertEqual(code, 1, output)
                self.assertFalse((root / fs.OUTPUT).exists())

    def test_missing_required_scope_or_reopen_cannot_admit(self):
        mutations = ("baseline_requirement", "baseline_platform", "later_requirement", "later_platform",
                     "both_missing_requirement", "malformed_scope", "reopen_missing", "reopen_null",
                     "layers_missing", "layers_null", "layers_empty", "layer_identity_missing", "duplicate_layer")
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                root, _, _ = self.measured()
                self.sweep(root, "2026-09-22", ident="incomplete-after")
                path = root / fs.LEDGER
                ledger = json.loads(path.read_bytes())
                baseline, later = [sweep["layers"][0] for sweep in ledger["sweeps"]]
                for row in (baseline, later):
                    row.update(requirement_sha256="a" * 64, platform_profiles_sha256="a" * 64)
                target = baseline if mutation.startswith("baseline") else later
                if "requirement" in mutation:
                    target.pop("requirement_sha256")
                    if mutation.startswith("both_missing"):
                        baseline.pop("requirement_sha256")
                elif "platform" in mutation:
                    target.pop("platform_profiles_sha256")
                elif mutation == "malformed_scope":
                    for row in (baseline, later):
                        row["requirement_sha256"] = "not-a-retained-hash"
                elif mutation == "reopen_missing":
                    later.pop("reopen")
                elif mutation == "reopen_null":
                    later["reopen"] = None
                elif mutation == "layers_missing":
                    ledger["sweeps"][-1].pop("layers")
                elif mutation == "layers_null":
                    ledger["sweeps"][-1]["layers"] = None
                elif mutation == "layers_empty":
                    ledger["sweeps"][-1]["layers"] = []
                elif mutation == "layer_identity_missing":
                    later.pop("layer_id")
                else:
                    ledger["sweeps"][-1]["layers"].append(dict(later))
                _write_json(path, ledger)
                if mutation not in ("layers_missing", "layers_null", "layer_identity_missing"):
                    self.matrix(root)
                code, output = self.write_result(root)
                self.assertEqual(code, 1, output)
                self.assertFalse((root / fs.OUTPUT).exists())

    def test_material_pending_without_scope_change_refuses(self):
        root, _, _ = self.measured()
        self.sweep(root, "2026-09-22", ident="pending-after")
        path = root / fs.LEDGER
        ledger = json.loads(path.read_bytes())
        row = ledger["sweeps"][-1]["layers"][0]
        row.update(contract_version=2, eligible_field=[], pending=[{
            "candidate_key": "foundation/layer-a/example/pending",
            "repository": "https://github.com/example/pending", "material": True}])
        _write_json(path, ledger)
        self.matrix(root)
        code, output = self.run_main(root, "--write")
        self.assertEqual(code, 1, output)
        self.assertIn(fs.FINAL_ADMISSION_REFUSAL, output)

    def test_retained_failure_refuses_with_unchanged_scope(self):
        root, _, _ = self.measured()
        reference = "evidence/artifacts/fixture/failure.json"
        _write_json(root / reference, {"failure": "Retained synthetic failure."})
        self.sweep(root, "2026-09-22", ident="failure-after",
                   reopen=[{"trigger": "retained_failure", "ref": reference}])
        code, output = self.run_main(root, "--write")
        self.assertEqual(code, 1, output)
        self.assertIn("admission under redesign", output)

    def test_completed_unchanged_post_anchor_sweep_refuses_while_disabled(self):
        root, _, _ = self.measured()
        self.sweep(root, "2026-09-22", ident="completed-after")
        self.assert_final_disabled(root)

    def test_material_pending_before_anchor_requires_retained_disposition(self):
        root, _, _ = self.measured()
        self.sweep(root, "2026-09-21", ident="prior-pending")
        path = root / fs.LEDGER
        ledger = json.loads(path.read_bytes())
        ledger["sweeps"][-1]["layers"][0].update(contract_version=2, eligible_field=[], pending=[{
            "candidate_key": "foundation/layer-a/example/pending",
            "repository": "https://github.com/example/pending", "material": True}])
        ledger["sweeps"].sort(key=lambda sweep: sweep["date"])
        _write_json(path, ledger)
        self.matrix(root)
        code, output = self.run_main(root, "--write")
        self.assertEqual(code, 1, output)
        self.assertIn("admission under redesign", output)

    def native_cutoff_fixture(self, field, status, *, refutation=False):
        native = ledger_helpers.V2PendingCliTests()
        native.setUp()
        self.addCleanup(native.tearDown)
        directory = REPO_ROOT / "tools/sota-convergence/landscape-sweep"
        if str(directory) not in sys.path:
            sys.path.insert(0, str(directory))
        spec = importlib.util.spec_from_file_location("final_admission_converter", directory / "convert.py")
        converter = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(converter)
        frozen = copy.deepcopy(native.field_input)
        empty = copy.deepcopy(frozen)
        empty["eligible_field"] = []
        empty["field_sha256"] = sl.v2_field_sha256(empty)
        _write_json(native.work / "inputs/alpha.json", empty)
        run = {"contract_version": 2, "sweep": ledger_helpers.LANE,
               "first": [{"catalog": "foundation", "layer_id": "alpha"}]}
        clean = converter.convert(run, sl.scope_hashes(native.root), ledger_helpers.LANE, {}, work=native.work)
        path = native.retain_v2_result(clean, "fx-clean", "2026-09-22", "completed")
        ledger = sl.append(native.root, native.ledger(), json.loads(path.read_bytes()))
        if not refutation:
            frozen[field] = "d" * 64
        frozen["field_sha256"] = sl.v2_field_sha256(frozen)
        _write_json(native.work / "inputs/alpha.json", frozen)
        scope = sl.scope_hashes(native.root)
        if field == "requirement_sha256":
            scope[field]["foundation/alpha"] = frozen[field]
        else:
            scope[field] = frozen[field]
        if refutation:
            run = native.screen_run(copies=2, status="not_credible", criterion="outside_requirement",
                                    fact="The primary source implements a different frozen requirement.")
        else:
            run["first"][0]["lost"] = True
        cutoff = converter.convert(run, scope, ledger_helpers.LANE, {}, work=native.work)
        path = native.retain_v2_result(cutoff, "fx-cutoff", "2026-09-23", status)
        ledger = sl.append(native.root, ledger, json.loads(path.read_bytes()))
        self.assertEqual(sl.check_ledger(native.root, ledger), [])
        self.assertEqual(len(sl.material_pending(ledger["sweeps"][-1]["layers"][0])), 0 if refutation else 2)

        root, _, _ = self.measured()
        for path in list(root.rglob("*.json")):
            path.write_text(path.read_text().replace("layer-a", "alpha"))
            if "layer-a" in path.name:
                path.rename(path.with_name(path.name.replace("layer-a", "alpha")))
        for relative in ("evidence/artifacts/fx", "catalogs/sota-convergence"):
            for path in (native.root / relative).rglob("*"):
                if path.is_file():
                    target = root / path.relative_to(native.root)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(path.read_bytes())
        registry_path = root / "manifests/evidence.json"
        registry = json.loads(registry_path.read_bytes())
        rows = {row["path"]: row for row in registry.get("files", [])}
        for row in json.loads((native.root / "manifests/evidence.json").read_bytes()).get("files", []):
            if (root / row["path"]).is_file():
                rows[row["path"]] = row
        for relative, row in rows.items():
            raw = (root / relative).read_bytes()
            row.update(sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))
        registry["files"] = list(rows.values())
        _write_json(registry_path, registry)
        self.assertEqual(sl.check_ledger(root, ledger), [])
        waves_path = root / fs.WAVE_REGISTRY
        waves = json.loads(waves_path.read_bytes())
        for wave in waves["waves"]:
            wave["manifest"] = ledger["sweeps"][0]["manifest_ref"]
            wave["sha256"] = hashlib.sha256((root / wave["path"]).read_bytes()).hexdigest()
        _write_json(waves_path, waves)
        _write_json(root / fs.LEDGER, ledger)
        self.matrix(root)
        return root

    def test_native_valid_stopped_v2_cutoff_refuses_final(self):
        for field in ("requirement_sha256", "platform_profiles_sha256"):
            for status in ("completed", "stopped"):
                with self.subTest(field=field, status=status):
                    root = self.native_cutoff_fixture(field, status)
                    self.assert_final_disabled(root)
                    self.assertFalse((root / fs.OUTPUT).exists())


del FinalIntegrityTests
