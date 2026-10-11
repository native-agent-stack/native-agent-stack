"""Boundary tests for evidence projection; native execution has separate receipts."""

import importlib.util
import contextlib
import io
import json
import hashlib
from pathlib import Path
import sys
import tempfile
import os
import re
import subprocess
from types import SimpleNamespace
import unittest
import copy
import xml.etree.ElementTree as ET
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
BLUEPRINT = ROOT / "blueprints/us-equities/backtesting-gap-burndown-20261010"
BASE = ROOT / "evidence/artifacts/backtesting-gap-burndown-20261010/us-equities__backtesting-engine"


def load(name):
    spec = importlib.util.spec_from_file_location(name, BLUEPRINT / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def evidence_nodes():
    def walk(value, pointer=""):
        if isinstance(value, dict):
            yield pointer, value
            for key, item in value.items():
                yield from walk(item, pointer + "/" + key)
        elif isinstance(value, list):
            for index, item in enumerate(value):
                yield from walk(item, pointer + "/" + str(index))
    for path in BASE.rglob("*.json"):
        for pointer, node in walk(json.loads(path.read_text())):
            yield path, pointer, node


class PublishedOutputDigestTests(unittest.TestCase):
    def test_embedded_outputs_bind_only_published_bytes(self):
        checked = 0
        for path, pointer, node in evidence_nodes():
            if isinstance(node.get("text"), str) and "sha256" in node:
                with self.subTest(file=path.name, pointer=pointer + "/sha256"):
                    self.assertEqual(node["sha256"], hashlib.sha256(
                        node["text"].encode("utf8", "surrogateescape")).hexdigest())
                    checked += 1
            if "output_sha256" not in node:
                continue
            with self.subTest(file=path.name, pointer=pointer):
                output = node.get("output", node.get("output_excerpt"))
                self.assertIsInstance(output, str, "a public output digest requires retained published text")
                self.assertEqual(node["output_sha256"], hashlib.sha256(
                    output.encode("utf8", "surrogateescape")).hexdigest())
                checked += 1
        self.assertGreater(checked, 0)

    def test_no_presanitization_output_commitments_are_published(self):
        forbidden = {"raw_sha256", "raw_log_sha256", "original_receipt_sha256",
                     "supersedes_draft_receipt_sha256", "original_export_sha256"}
        for path, pointer, node in evidence_nodes():
            with self.subTest(file=path.name, pointer=pointer):
                self.assertFalse(forbidden & node.keys(), "original commitments belong only in private evidence")

    def test_output_files_bind_published_repository_bytes(self):
        checked = 0
        for path, pointer, node in evidence_nodes():
            if "path" not in node or "sha256" not in node or not any(
                    "/" + group + "/" in pointer for group in ("captured_outputs", "output_hashes", "outputs", "captures")):
                continue
            with self.subTest(file=path.name, pointer=pointer):
                self.assertFalse(Path(node["path"]).is_absolute() or node["path"].startswith("~"),
                                 "published output must have retained repository bytes")
                output = ROOT / node["path"]
                self.assertTrue(output.is_file())
                self.assertEqual(node["sha256"], hashlib.sha256(output.read_bytes()).hexdigest())
                checked += 1
        self.assertGreater(checked, 0)

    def test_home_candidate_cannot_confirm_a_public_output_digest(self):
        # Keep the candidate internal; failures emit only a Boolean and locator.
        candidate = str(Path.home()).encode()
        digests = {digest for _, _, node in evidence_nodes() for value in node.values()
                   if isinstance(value, str) for digest in re.findall(r"(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])", value)}
        checked = 0
        for path, pointer, node in evidence_nodes():
            data = None
            if isinstance(node.get("output"), str):
                data = node["output"].encode("utf8", "surrogateescape")
            elif isinstance(node.get("text"), str):
                data = node["text"].encode("utf8", "surrogateescape")
            elif isinstance(node.get("path"), str) and "sha256" in node and any(
                    "/" + group + "/" in pointer for group in ("captured_outputs", "output_hashes", "outputs", "captures")):
                output = ROOT / node["path"]
                if output.is_file():
                    data = output.read_bytes()
            if data is None or b"~" not in data:
                continue
            inverse = hashlib.sha256(data.replace(b"~", candidate)).hexdigest()
            with self.subTest(file=path.name, pointer=pointer):
                self.assertFalse(inverse in digests, "masked-home inverse matched a public digest")
            checked += 1
        self.assertGreater(checked, 0, "inverse probe must exercise published masked text")


class FinalRoundRegressionTests(unittest.TestCase):
    def test_published_trx_machine_fields_are_structurally_masked(self):
        paths = list((BASE / "raw/published").glob("*.trx"))
        self.assertEqual(len(paths), 4)
        checked = 0
        for path in paths:
            for element in ET.parse(path).iter():
                tag = element.tag.rsplit("}", 1)[-1]
                for attribute, value in element.attrib.items():
                    if attribute == "computerName" or (tag, attribute) in {
                            ("TestRun", "name"), ("Deployment", "runDeploymentRoot")}:
                        # Never include the original value in a failing diagnostic.
                        self.assertTrue(value == "[MACHINE]", "unmasked TRX machine field")
                        checked += 1
        self.assertEqual(checked, 45)

    def test_original_paths_and_published_copy_bindings_are_preserved(self):
        entries = json.loads((BASE / "raw/final-path-provenance.json").read_text())["entries"]
        self.assertEqual(sum(e["kind"] == "dedup" for e in entries), 26)
        self.assertEqual(sum(e["kind"] == "private" for e in entries), 18)
        for entry in entries:
            document = json.loads((BASE / "raw" / entry["receipt"]).read_text())
            node = document
            for part in entry["pointer"].strip("/").split("/"):
                node = node[int(part)] if isinstance(node, list) else node[part]
            with self.subTest(receipt=entry["receipt"], pointer=entry["pointer"]):
                self.assertEqual(node["path"], entry["original_path"])
                if entry["kind"] == "private":
                    self.assertNotIn("sha256", node, "original private bytes must not have a public commitment")
                    published = node["published_copy"]
                    self.assertEqual(published["path"], entry["published_path"])
                    self.assertEqual(published["sha256"], hashlib.sha256(
                        (ROOT / published["path"]).read_bytes()).hexdigest())

    def test_dll_commitment_is_kept_out_of_public_inputs(self):
        receipt = json.loads((BASE / "raw/lean-model-explicit-environment.json").read_text())
        self.assertFalse(any(item["path"].endswith("QuantConnect.Tests.dll")
                             for item in receipt["input_hashes"]), "private DLL commitment is published")
        private = [item for item in receipt.get("private_outputs", [])
                   if item["path"].endswith("QuantConnect.Tests.dll")]
        self.assertEqual(len(private), 1)
        self.assertNotIn("sha256", private[0], "private digest must stay in local evidence")

    def test_truncated_rows_cannot_borrow_an_execution_summary(self):
        module = load("execute_comparators")
        for name in ("accepted-v2-bars", "accepted-v2-no-attribution", "fresh-native-v2"):
            verdict = json.loads((BASE / "raw" / (name + ".verdict.json")).read_text())
            verdict["checks"] = [row for row in verdict["checks"] if row["status"] != "PASS"]
            path = SimpleNamespace(read_text=lambda: json.dumps(verdict))
            with self.subTest(mode=name), self.assertRaisesRegex(ValueError, "execution"):
                module.validate_verdict(name, path)

    def test_case_specific_quantity_prices_and_cash_are_checked(self):
        module = load("native_mechanics")
        for name, target, account, quantity, fee, cash in (
                ("one-fixed-fee", "1", "CASH", 304, "1", "90732.08"),
                ("two-margin-zero", "2", "MARGIN", 608, "0", "81468.16"),
                ("two-margin-fixed-fee", "2", "MARGIN", 608, "1", "81466.16")):
            valid = {"fills": [{"side": "BUY", "quantity": quantity, "price": "323.5800", "fee": fee},
                               {"side": "SELL", "quantity": -quantity, "price": "291.6900", "fee": fee}],
                     "native_end_cash_usd": cash, "native_account_event_rows": [],
                     "distribution_module": {"emissions": []}, "order_events": [],
                     "cash_ledger": [{"cash": cash}], "engine_log_scan": {"error_lines": 0},
                     "fees_usd": str(int(fee) * 2)}
            self.assertEqual(module.project_result(name, target, account, valid)["status"], "completed")
            for fault in ("quantity", "cash", "price", "target", "account"):
                wrong = copy.deepcopy(valid)
                if fault == "quantity":
                    wrong["fills"][0]["quantity"], wrong["fills"][1]["quantity"] = 1, -1
                elif fault == "cash":
                    wrong["native_end_cash_usd"] = wrong["cash_ledger"][-1]["cash"] = "99999"
                elif fault == "price":
                    wrong["fills"][0]["price"] = "300"
                with self.subTest(case=name, fault=fault), self.assertRaises(ValueError):
                    module.project_result(name, "4" if fault == "target" else target,
                                          "MARGIN" if fault == "account" and account == "CASH" else
                                          "CASH" if fault == "account" else account, wrong)


class FailureBoundaryTests(unittest.TestCase):
    def test_default_inside_checkout_is_refused_before_launch(self):
        module = load("execute_comparators")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "checkout"
            root.mkdir()
            with mock.patch.object(module, "ROOT", root), mock.patch.dict(os.environ, {"TMPDIR": str(root)}), \
                 mock.patch.object(module.tempfile, "tempdir", None), \
                 mock.patch.object(module.subprocess, "run") as process, \
                 mock.patch.object(sys, "argv", ["comparators", "--data", tmp, "--fresh", tmp]), \
                 contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(module.main(), 1)
                process.assert_not_called()
            self.assertEqual(list(root.iterdir()), [], "refusal must precede creation inside the checkout")

    def test_relative_inputs_are_resolved_in_callers_directory(self):
        module = load("execute_comparators")
        with tempfile.TemporaryDirectory() as tmp:
            caller = Path(tmp)
            calls = []
            def run(command, **kwargs):
                calls.append(command)
                p = Path(command[command.index("--verdict") + 1])
                p.write_bytes((BASE / "raw" / p.name).read_bytes())
                return SimpleNamespace(returncode=0 if p.name.startswith("accepted-v2-lean-data") else 1)
            previous = Path.cwd()
            try:
                os.chdir(caller)
                with mock.patch.object(module.subprocess, "run", side_effect=run), \
                     mock.patch.object(sys, "argv", ["comparators", "--data", "data", "--fresh", "fresh", "--output", "output"]), \
                     contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(module.main(), 0)
            finally:
                os.chdir(previous)
            self.assertEqual(Path(calls[0][calls[0].index("--lean-data") + 1]), caller / "data")
            self.assertEqual(Path(calls[2][calls[2].index("--bars") + 1]), caller / "fresh/converted-rows.private.json")
            self.assertEqual(Path(calls[3][calls[3].index("--receipt") + 1]), caller / "fresh/receipt.json")

    def test_each_refusal_requires_its_full_execution_counts(self):
        module = load("execute_comparators")
        for name in ("accepted-v2-bars", "accepted-v2-no-attribution"):
            original = json.loads((BASE / "raw" / (name + ".verdict.json")).read_text())
            with tempfile.TemporaryDirectory() as tmp:
                for counts in (None, {"pass": 0, "fail": 0, "skipped": 0}):
                    verdict = dict(original)
                    if counts is None:
                        verdict.pop("execution_checks")
                    else:
                        verdict["execution_checks"] = counts
                    p = Path(tmp) / "verdict.json"
                    p.write_text(json.dumps(verdict))
                    with self.assertRaises((KeyError, ValueError)):
                        module.validate_verdict(name, p)

    def test_every_completed_case_requires_fills_and_charged_fees(self):
        module = load("native_mechanics")
        observed = {"fills": [], "native_end_cash_usd": "100000.00", "native_account_event_rows": [],
                    "distribution_module": {"emissions": []}, "order_events": [],
                    "cash_ledger": [], "engine_log_scan": {"error_lines": 0}, "fees_usd": "0"}
        for name, target, account in (("one-fixed-fee", "1", "CASH"), ("two-margin-zero", "2", "MARGIN"),
                                      ("two-margin-fixed-fee", "2", "MARGIN")):
            with self.assertRaisesRegex(ValueError, "native_fills"):
                module.project_result(name, target, account, observed)
        observed["fills"] = [{"side": "BUY", "quantity": 1, "fee": "0"}, {"side": "SELL", "quantity": -1, "fee": "0"}]
        with self.assertRaisesRegex(ValueError, "native_fees"):
            module.project_result("one-fixed-fee", "1", "CASH", observed)
    def test_clean_checkout_driver_invokes_all_modes_without_mutating_captures(self):
        module = load("execute_comparators")
        before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in (BASE / "raw").glob("*.verdict.json")}
        outputs = []
        def run(command, **kwargs):
            path = Path(command[command.index("--verdict") + 1])
            self.assertFalse(path.is_relative_to(BASE), "fresh outputs must not target retained evidence")
            path.write_bytes((BASE / "raw" / path.name).read_bytes())
            outputs.append(path)
            return SimpleNamespace(returncode=0 if path.name.startswith("accepted-v2-lean-data") else 1)
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.object(module.subprocess, "run", side_effect=run) as process, \
             mock.patch.object(sys, "argv", ["comparators", "--data", tmp, "--fresh", tmp]), \
             contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            # Do not redirect RAW: this reproduces an ordinary clean checkout.
            self.assertEqual(module.main(), 0, "tracked verdicts must not prevent fresh comparator execution")
            self.assertEqual(process.call_count, 4)
        self.assertEqual(before, {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in before})
        for path in outputs:
            path.unlink()
        if outputs:
            outputs[0].parent.rmdir()

    def test_projection_keyerror_makes_mechanics_command_fail(self):
        module = load("native_mechanics")
        # The native runner completes; the defect is projection, not import or
        # signature compatibility. Reproduce the original missing-key failure.
        replay = SimpleNamespace(CASE={}, VENUE={},
            load_bound_manifests=lambda: ({}, {}), check_engine_binary=lambda _: None,
            CONVERT=SimpleNamespace(convert=lambda *a: {"rows": []}),
            known_short_sessions=lambda _: [], distribution_events=lambda _: [],
            run_once=lambda *a: {})
        spec = SimpleNamespace(name="fixture_replay", loader=SimpleNamespace(exec_module=lambda _: None))
        fake_modules = {
            "nautilus_trader.execution": SimpleNamespace(FixedFeeModel=lambda *a, **k: None),
            "nautilus_trader.model": SimpleNamespace(Currency=SimpleNamespace(from_str=lambda _: None),
                                                       Money=lambda *a: None)}
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(sys.modules, fake_modules), \
             mock.patch.object(module.importlib.util, "spec_from_file_location", return_value=spec), \
             mock.patch.object(module.importlib.util, "module_from_spec", return_value=replay), \
             mock.patch.object(sys, "argv", ["mechanics", "--data", tmp, "--output", tmp + "/run"]), \
             contextlib.redirect_stdout(io.StringIO()):
            try:
                code = module.main()
            except KeyError:
                code = 1
            self.assertNotEqual(code, 0, "projection KeyError must fail the command, never become a successful refusal")

    def test_missing_verdict_fails_even_when_wrapper_reports_expected_exit(self):
        module = load("execute_comparators")
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.object(module.subprocess, "run", return_value=SimpleNamespace(returncode=0)), \
             mock.patch.object(sys, "argv", ["comparators", "--data", tmp, "--fresh", tmp, "--output", tmp + "/output"]), \
             contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertNotEqual(module.main(), 0, "missing verdict must fail independently of process exit")

    def test_wrong_refusal_check_set_fails(self):
        module = load("execute_comparators")
        with tempfile.TemporaryDirectory() as tmp:
            def run(command, **kwargs):
                path = Path(command[command.index("--verdict") + 1])
                path.write_text(json.dumps({"verdict": "FAIL", "checks": [
                    {"key": "unexpected_crash.crash#1", "id": "unexpected_crash", "field": "crash", "status": "FAIL"}]}))
                return SimpleNamespace(returncode=0)
            with mock.patch.object(module.subprocess, "run", side_effect=run), \
                 mock.patch.object(sys, "argv", ["comparators", "--data", tmp, "--fresh", tmp, "--output", tmp + "/output"]), \
                 contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertNotEqual(module.main(), 0, "only the declared check ids qualify as expected refusal")

    def test_all_retained_verdicts_satisfy_exact_designed_check_sets(self):
        module = load("execute_comparators")
        for name in module.EXPECTED_CHECKS:
            module.validate_verdict(name, BASE / "raw" / (name + ".verdict.json"))

    def test_successful_driver_checks_all_four_fresh_verdict_files(self):
        module = load("execute_comparators")
        with tempfile.TemporaryDirectory() as tmp:
            def run(command, **kwargs):
                path = Path(command[command.index("--verdict") + 1])
                name = path.name.removesuffix(".verdict.json")
                path.write_bytes((BASE / "raw" / path.name).read_bytes())
                self.assertEqual(kwargs["env"]["OMP_NUM_THREADS"], "1")
                return SimpleNamespace(returncode=0 if name == "accepted-v2-lean-data" else 1)
            with mock.patch.object(module.subprocess, "run", side_effect=run) as process, \
                 mock.patch.object(sys, "argv", ["comparators", "--data", tmp, "--fresh", tmp, "--output", tmp + "/output"]), \
                 contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(module.main(), 0)
                self.assertEqual(process.call_count, 4)

    def test_existing_or_checkout_output_is_refused_before_any_comparator(self):
        module = load("execute_comparators")
        with tempfile.TemporaryDirectory() as tmp:
            for output in (tmp, str(BASE / "raw"), str(ROOT / "fresh-output")):
                with mock.patch.object(module.subprocess, "run") as process, \
                     mock.patch.object(sys, "argv", ["comparators", "--data", tmp, "--fresh", tmp, "--output", output]), \
                     contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(module.main(), 1)
                    process.assert_not_called()

    def test_each_comparator_failure_stops_without_overwriting_retained_outputs(self):
        module = load("execute_comparators")
        for stop in range(4):
            with tempfile.TemporaryDirectory() as tmp:
                calls = []
                def run(command, **kwargs):
                    path = Path(command[command.index("--verdict") + 1])
                    calls.append(path)
                    path.write_bytes((BASE / "raw" / path.name).read_bytes())
                    expected = 0 if path.name.startswith("accepted-v2-lean-data") else 1
                    return SimpleNamespace(returncode=expected + 2 if len(calls) == stop + 1 else expected)
                with mock.patch.object(module.subprocess, "run", side_effect=run), \
                     mock.patch.object(sys, "argv", ["comparators", "--data", tmp, "--fresh", tmp, "--output", tmp + "/output"]), \
                     contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(module.main(), 1)
                    self.assertEqual(len(calls), stop + 1)

    def test_refusal_requires_native_denial_events(self):
        module = load("native_mechanics")
        result = {"fills": [], "native_account_event_rows": [], "native_end_cash_usd": "100000.00",
                  "fees_usd": "0", "distribution_module": {"emissions": []}, "order_events": [],
                  "cash_ledger": [], "engine_log_scan": {"error_lines": 0}}
        with self.assertRaisesRegex(ValueError, "native_denial"):
            module.project_result("four-cash-refusal", "4", "CASH", result)

    def test_other_mechanics_cases_refuse_denials_and_engine_errors(self):
        module = load("native_mechanics")
        result = {"order_events": [{"event": "OrderDenied", "reason": "unexpected"}],
                  "engine_log_scan": {"error_lines": 0}}
        with self.assertRaisesRegex(ValueError, "unexpected_native_denial"):
            module.project_result("one-fixed-fee", "1", "CASH", result)
        result["order_events"] = []
        result["engine_log_scan"]["error_lines"] = 1
        with self.assertRaisesRegex(ValueError, "native_engine_errors"):
            module.project_result("two-margin-zero", "2", "MARGIN", result)


class CloseoutRegressionTests(unittest.TestCase):
    def test_path_semantics_cite_pinned_cpython(self):
        readme = (BLUEPRINT / "README.md").read_text()
        self.assertIn("https://github.com/python/cpython", readme)
        self.assertIn("8e8a4baf652f6e1cee7acde9d78c4b6154539748", readme)

    def test_recorder_sources_have_retained_bytes_and_blob_identity(self):
        for p in (BASE / "raw").glob("*.json"):
            receipt = json.loads(p.read_text())
            source = receipt.get("environment_record", {}).get("recorder_source")
            if source is None:
                continue
            self.assertIn("blob_sha1", source, "a transient PR commit alone is not durable source provenance")
            data = (ROOT / source["retained_path"]).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(), source["sha256"])
            self.assertEqual(hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest(), source["blob_sha1"])

    def test_unrecoverable_input_receipts_are_historical_drafts(self):
        for name in ("green-matrix-wave-join", "green-matrix-wave-join-2", "red-matrix-wave-join", "native-fee-margin-mechanics"):
            receipt = json.loads((BASE / "raw" / (name + ".json")).read_text())
            self.assertEqual(receipt.get("provenance_status"), "historical_draft")

    def test_cited_red_test_bytes_are_retained(self):
        receipt = json.loads((BASE / "raw/codex-p2-red.json").read_text())
        self.assertIn("test_source_path", receipt, "a draft test hash must have retained bytes")
        self.assertEqual(hashlib.sha256((ROOT / receipt["test_source_path"]).read_bytes()).hexdigest(),
                         receipt["test_source_sha256"])

    def test_cross_checkout_preserves_captured_bytes_with_autocrlf(self):
        attributes = (BASE / ".gitattributes").read_bytes()
        capture = (BASE / "raw/native-fee-margin-mechanics-2.stdout.txt").read_bytes()
        def checked_out(rule):
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True)
                (root / ".gitattributes").write_bytes(rule)
                (root / "capture.txt").write_bytes(capture)
                subprocess.run(["git", "-C", str(root), "-c", "core.attributesFile=/dev/null", "-c", "core.autocrlf=true", "add", "--", ".gitattributes", "capture.txt"], check=True, capture_output=True)
                (root / "capture.txt").unlink()
                subprocess.run(["git", "-C", str(root), "-c", "core.attributesFile=/dev/null", "-c", "core.autocrlf=true", "checkout-index", "--", "capture.txt"], check=True, capture_output=True)
                return (root / "capture.txt").read_bytes()
        self.assertNotEqual(hashlib.sha256(checked_out(b"")).hexdigest(), hashlib.sha256(capture).hexdigest(),
                            "control must demonstrate pre-fix checkout drift")
        self.assertEqual(hashlib.sha256(checked_out(attributes)).hexdigest(), hashlib.sha256(capture).hexdigest())
    def test_mechanics_citations_bind_native_execution_of_current_harness(self):
        current = hashlib.sha256((BLUEPRINT / "native_mechanics.py").read_bytes()).hexdigest()
        for index in (0, 9):
            gap = json.loads((BASE / f"{index}-gap.json").read_text())
            receipts = []
            for ref in gap["raw_outputs"]:
                if "native-fee-margin-mechanics" in Path(ref["path"]).name and ref["path"].endswith(".json"):
                    receipts.append(json.loads((ROOT / ref["path"]).read_text()))
            self.assertTrue(any(r.get("observed_exit_code") == 0 and any(
                p["path"].endswith("/native_mechanics.py") and p["sha256"] == current
                for p in r.get("input_hashes", [])) for r in receipts),
                "gap citations need native execution of the current harness, not only an old-run projection")

    def test_unreviewed_counts_stay_at_historical_eight_twelve(self):
        matrix = json.loads((ROOT / "catalogs/landscape/component-evidence-matrix.json").read_text())
        row = next(r for r in matrix["rows"] if r["layer_id"] == "backtesting-engine")
        self.assertEqual((row["open_executable_now_gaps"], row["open_gaps"]), (8, 12),
                         "unreviewed receipts must not subtract three gaps")

    def test_prior_settlements_are_reconfirmations(self):
        for index, filename in ((2, "2-nautilus-latest-stable-release.json"),
                                (6, "6-comparator-modes-and-review-count.json")):
            receipt = json.loads((BASE / f"{index}-gap.json").read_text())
            self.assertEqual(receipt["outcome"], "covered_elsewhere", "September 23 settlement is not new")
            self.assertTrue(any(r["path"].endswith(filename) for r in receipt["raw_outputs"]))

    def test_gap_four_reports_one_method_twelve_cases(self):
        summary = json.loads((BASE / "raw/lean-model-summary.json").read_text())
        self.assertIn("CanSubmitOrderWhenOutsideRegularTradingHours", summary["surface"])
        self.assertIn("12 TestCaseSource cases", summary["surface"])

    def test_legacy_environment_omission_is_explicit(self):
        for name in ("lean-alpaca-model-tests-with-icu", "lean-alpaca-model-tests-py312"):
            receipt = json.loads((BASE / "raw" / (name + ".json")).read_text())
            self.assertIn("environment_record", receipt, "historical environment omission must be disclosed")
            self.assertEqual(receipt["environment_record"]["status"], "unavailable")

    def test_fresh_lean_environment_is_observed_and_explicit(self):
        receipt = json.loads((BASE / "raw/lean-model-explicit-environment.json").read_text())
        self.assertEqual(receipt["observed_exit_code"], 0)
        self.assertEqual(receipt["counters"]["passed"], "12")
        environment = receipt["environment_record"]
        self.assertEqual(environment["status"], "observed")
        self.assertTrue(environment["cleared"])
        self.assertTrue({"PYTHONNET_PYDLL", "PYTHONHOME", "LD_LIBRARY_PATH", "DOTNET_PROCESSOR_COUNT",
                         "OMP_NUM_THREADS"}.issubset(environment["variables"]))

    def test_retained_expected_refusal_has_native_denials_and_no_fills(self):
        receipt = json.loads((BASE / "raw/native-mechanics-events.json").read_text())
        refusal = next(r for r in receipt["results"] if r["id"] == "four-cash-refusal")
        self.assertEqual(refusal["status"], "expected_refusal")
        self.assertEqual(refusal["fills"], [])
        denied = [e for e in refusal["order_events"] if e["event"] == "OrderDenied"]
        self.assertEqual(len(denied), 2)
        self.assertTrue(all(e["reason"].startswith("NOTIONAL_EXCEEDS_FREE_BALANCE:") for e in denied))

    def test_bespoke_registration_and_recording_helpers_are_removed(self):
        for name in ("record.py", "register_changed.py", "summarize.py"):
            self.assertFalse((BLUEPRINT / name).exists(), "use the shared closeout and explicit registration APIs")

    def test_deferred_gaps_do_not_borrow_unrelated_native_summaries(self):
        unrelated = {"native-replay-economic-summary.json", "native-mechanics-summary.json", "lean-model-summary.json",
                     "review-excerpt-integrity.json"}
        for index in (1, 8):
            receipt = json.loads((BASE / f"{index}-gap.json").read_text())
            self.assertFalse(unrelated & {Path(r["path"]).name for r in receipt["raw_outputs"]},
                             "deferred gaps must cite evidence for their own remaining boundary")

    def test_failed_build_capture_is_bounded_and_hash_bound(self):
        path = BASE / "raw/lean-alpaca-model-tests-with-icu.stdout.txt"
        self.assertLessEqual(path.stat().st_size, 65536, "retain failed-build tail and original digest")


class NativeSummaryTests(unittest.TestCase):
    def test_projection_uses_existing_runner_public_summary_keys(self):
        spec = importlib.util.spec_from_file_location("mechanics", ROOT /
            "blueprints/us-equities/backtesting-gap-burndown-20261010/native_mechanics.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        # Schema from spy-parity/run.py:663-698. The runner publishes an end
        # balance and event rows, never a native_account_totals summary field.
        observed = {"fills": [{"side": "BUY", "quantity": 304, "price": "323.5800", "fee": "1"},
                               {"side": "SELL", "quantity": -304, "price": "291.6900", "fee": "1"}],
                    "native_end_cash_usd": "90732.08", "native_account_event_rows": [],
                    "distribution_module": {"emissions": []}, "order_events": [],
                    "cash_ledger": [{"cash": "90732.08"}], "engine_log_scan": {"error_lines": 0}, "fees_usd": "2"}
        projected = module.project_result("one-fixed-fee", "1", "CASH", observed)
        self.assertEqual(projected["native_end_cash"], "90732.08")
        self.assertEqual(projected["native_account_events"], [])
        self.assertFalse(projected["qualifies_frozen_stress_case"])


if __name__ == "__main__":
    unittest.main()
