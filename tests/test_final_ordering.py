"""Ledger-index disposition and retained native V2 settlement controls."""

import ast
import json
import unittest

from scripts import final_stack as fs
from tests.test_angle_records_fix3 import FinalIntegrityTests
from tests.test_final_admission import FinalAdmissionTests
from tests.test_final_stack import FixtureTestCase, REPO_ROOT, _write_json
from tests.test_record_verdicts import record_verdicts


class FinalLedgerIndexStructureTests(unittest.TestCase):
    def test_final_admission_ordering_never_compares_date_or_day(self):
        tree = ast.parse((REPO_ROOT / "scripts/final_stack.py").read_text())
        failures = []
        for function in tree.body:
            if not isinstance(function, ast.FunctionDef):
                continue
            if function.name.startswith("final_") or function.name == "enforce_final":
                scopes = [function]
            elif function.name == "build_document":
                scopes = [node for node in ast.walk(function) if isinstance(node, ast.If)
                          and isinstance(node.test, ast.Compare)
                          and isinstance(node.test.left, ast.Name)
                          and node.test.left.id == "resolved_terminal"
                          and any(isinstance(value, ast.Constant) and value.value == "FINAL"
                                  for value in node.test.comparators)]
            else:
                continue
            for compare in (node for scope in scopes for node in ast.walk(scope)
                            if isinstance(node, ast.Compare)):
                names = []
                for node in ast.walk(compare):
                    if isinstance(node, ast.Name):
                        names.append(node.id)
                    elif isinstance(node, ast.Attribute):
                        names.append(node.attr)
                    elif isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant):
                        names.append(str(node.slice.value))
                if any(set(name.split("_")) & {"date", "day"} for name in names):
                    failures.append((function.name, compare.lineno))
        self.assertEqual(failures, [], "FINAL event admission must use the shared ledger index")


class FinalLedgerIndexTests(FixtureTestCase):
    prepare = FinalIntegrityTests.prepare
    measured = FinalIntegrityTests.measured
    matrix = FinalIntegrityTests.matrix
    sweep = FinalIntegrityTests.sweep
    native_cutoff_fixture = FinalAdmissionTests.native_cutoff_fixture

    def disposition_fixture(self, kind, binding):
        root, _, _ = self.measured()
        repository = ("https://github.com/example/widget" if kind == "winner"
                      else "https://github.com/example/challenger")
        self.sweep(root, "2026-09-22", ident="a-survivor", survived=[repository])
        self.sweep(root, "2026-09-22", ident="z-later")
        evidence = "evidence/artifacts/fixture/index-disposition.json"
        target = {"reason": "Retained synthetic catalog disposition."}
        if binding != "missing":
            target["sweep_id"] = {"unknown": "not-a-sweep", "before": "fixture",
                                  "same": "a-survivor", "later": "z-later"}.get(binding)
        _write_json(root / evidence, target)
        references = [fs.LEDGER + "#/sweeps/1"] if binding == "pointer" else [evidence]
        path = root / "catalogs/landscape/foundation.json"
        catalog = json.loads(path.read_bytes())
        if kind == "winner":
            catalog["layers"][0]["winners"][0]["evidence_refs"] = references
        else:
            catalog["layers"][0]["alternatives"] = [{"name": "Challenger", "repository": repository,
                "disposition": "out_of_scope", "why_not_default": "Outside the named frozen role.",
                "evidence_class": "source_review", "evidence_refs": references}]
        _write_json(path, catalog)
        self.matrix(root)
        return root

    def test_same_day_dispositions_require_a_named_same_or_later_sweep(self):
        for kind in ("winner", "alternative"):
            for binding in ("missing", "unknown", "before", "same", "later", "pointer"):
                with self.subTest(kind=kind, binding=binding):
                    root = self.disposition_fixture(kind, binding)
                    code, output = self.run_main(root, "--write")
                    self.assertEqual(code, 0 if binding in ("same", "later", "pointer") else 1, output)
                    if code == 0:
                        layer = self.layer(json.loads((root / fs.OUTPUT).read_bytes()), "layer-a")
                        self.assertEqual(layer["terminal_state"], "FINAL")
                        self.assertEqual(layer["survivors"], [])

    def test_recorder_drops_hand_added_sweep_field_and_admission_ignores_it(self):
        root = self.disposition_fixture("alternative", "missing")
        path = root / "catalogs/landscape/foundation.json"
        catalog = json.loads(path.read_bytes())
        alternative = catalog["layers"][0]["alternatives"][0]
        alternative["sweep_id"] = "a-survivor"
        identities = {record_verdicts.safe_identity(alternative["repository"])}
        recorded, gaps = record_verdicts.build_alternatives(
            {"claude": {"alternatives": [alternative]}}, identities, {})
        self.assertEqual(gaps, [])
        self.assertNotIn("sweep_id", recorded[0])
        for alternatives in ([alternative], recorded):
            catalog["layers"][0]["alternatives"] = alternatives
            _write_json(path, catalog)
            self.matrix(root)
            code, output = self.run_main(root, "--write")
            self.assertEqual(code, 1, output)

    def test_native_v2_refuting_vote_settles_and_unknown_vote_does_not(self):
        for mutation in (None, "unknown_vote", "missing_reference", "wrong_identity", "wrong_evidence_key",
                         "wrong_repository", "wrong_outcome"):
            with self.subTest(mutation=mutation):
                root = self.native_cutoff_fixture("requirement_sha256", "completed", refutation=True)
                path = root / fs.LEDGER
                ledger = json.loads(path.read_bytes())
                if mutation:
                    entry = ledger["sweeps"][-1]["layers"][0]["refuted"][0]
                    if mutation == "unknown_vote":
                        entry["fit"]["vote"] = "unrecognized"
                    elif mutation == "missing_reference":
                        entry["fit"]["ref"] = "evidence/artifacts/fixture/missing-vote.json"
                    elif mutation == "wrong_identity":
                        entry["candidate_key"] = "foundation/alpha/wrong/identity"
                    elif mutation == "wrong_evidence_key":
                        entry["evidence_key"] = "foundation/alpha/wrong/evidence"
                    elif mutation == "wrong_repository":
                        entry["repo"] = "https://github.com/example/wrong-refutation-target"
                    else:
                        entry["material"] = True
                    _write_json(path, ledger)
                    self.matrix(root)
                code, output = self.run_main(root, "--write")
                self.assertEqual(code, 0 if mutation is None else 1, output)


del FinalIntegrityTests, FinalAdmissionTests
