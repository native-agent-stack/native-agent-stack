"""Native tag resolution and offline source fills, with no version upgrades."""
import copy
import ast
import json
import os
from pathlib import Path
import re
import subprocess
import unittest
from unittest.mock import Mock, patch

from scripts import complete_run_pins as pins, final_stack
from tests import test_final_stack as fixtures

ROOT = Path(__file__).resolve().parents[1]
PUBLISHED_ROOT = ROOT


class PublishedSourceContractTests(unittest.TestCase):
    def test_record_pin_citation_matches_the_function_at_its_pinned_base(self):
        base = "8dfe8b588de22451364857b4be4683fb35f57a7d"
        source = subprocess.run(["git", "show", base + ":scripts/final_stack.py"], cwd=ROOT,
                                capture_output=True, text=True)
        if source.returncode:
            self.skipTest("pinned base absent from this checkout's history")
        function = next(node for node in ast.parse(source.stdout).body
                        if isinstance(node, ast.FunctionDef) and node.name == "record_pin")
        decision = (PUBLISHED_ROOT / "docs/decisions/2026-10-16-nautilus-rc5-run-source-pin.md").read_text()
        cited = re.search(r"scripts/final_stack.py:127-129,(\d+)-(\d+)", decision)
        self.assertIsNotNone(cited)
        self.assertEqual(tuple(map(int, cited.groups())), (function.lineno, function.end_lineno))


class TagResolutionTests(unittest.TestCase):
    A, B = "a" * 40, "b" * 40

    def run_record(self):
        return {"id": "widget", "repository": "github.com/example/widget", "pin": "1.2.3",
                "pin_parsed": {"version": "1.2.3", "commit": None}, "source": "pins.json#/tools/0"}

    def proof(self):
        run = self.run_record()
        return pins.resolve(run, Mock(return_value=Mock(returncode=0, stderr="", stdout=(
            self.A + "\trefs/tags/v1.2.3\n" + self.B + "\trefs/tags/v1.2.3^{}\n"))))

    def test_annotated_and_lightweight_tag_objects_stay_distinct(self):
        parsed = pins.parse_remote(self.A + " refs/tags/v1.2.3\n" + self.B + " refs/tags/v1.2.3^{}\n", ["v1.2.3"])
        self.assertEqual((parsed["tag_object"], parsed["peeled_commit"]), (self.A, self.B))
        light = pins.parse_remote(self.B + " refs/tags/1.2.3\n", ["1.2.3"])
        self.assertIsNone(light["tag_object"])
        self.assertEqual(light["peeled_commit"], self.B)

    def test_missing_ambiguous_malformed_conflicting_and_orphaned_refs_are_gaps(self):
        for stdout in ("", self.A + " refs/tags/v1.2.3\n" + self.B + " refs/tags/1.2.3\n",
                       "not-an-oid refs/tags/v1.2.3\n", self.A + " refs/heads/main\n",
                       self.A + " refs/tags/v1.2.3\n" + self.B + " refs/tags/v1.2.3\n",
                       self.B + " refs/tags/v1.2.3^{}\n"):
            with self.subTest(stdout=stdout):
                self.assertEqual(pins.parse_remote(stdout, ["v1.2.3", "1.2.3"])["status"], "gap")

    def test_offline_verification_reproduces_the_exact_query_and_peeled_commit(self):
        proof = self.proof()
        self.assertEqual(pins.verified_commit(proof, "widget", "1.2.3", "github.com/example/widget"), self.B)
        for change in ({"exit_code": 128}, {"version": "1.2.4"}, {"component": "imposter"},
                       {"peeled_commit": self.A}, {"tag_object": self.B}, {"stdout": ""},
                       {"command": ["git", "ls-remote", "https://github.com/example/widget/tree/main",
                                    "refs/tags/v1.2.3", "refs/tags/v1.2.3^{}"]}):
            with self.subTest(change=change):
                altered = {**proof, **change}
                self.assertIsNone(pins.verified_commit(altered, "widget", "1.2.3", "github.com/example/widget"))

    def test_lookup_failure_and_timeout_retain_command_and_outputs(self):
        result = pins.resolve(self.run_record(), Mock(return_value=Mock(returncode=128, stdout="", stderr="unavailable")))
        self.assertEqual((result["status"], result["exit_code"]), ("gap", 128))
        self.assertNotIn("unavailable", json.dumps(result))
        timeout = pins.resolve(self.run_record(), Mock(side_effect=subprocess.TimeoutExpired("git", 45, b"partial", b"timeout")))
        self.assertEqual((timeout["status"], timeout["stdout"]), ("gap", "partial"))
        self.assertNotIn('"stderr": "timeout"', json.dumps(timeout))
        self.assertIn("refs/tags/v1.2.3^{}", timeout["command"])

    def test_resolver_ignores_host_git_configuration_and_never_publishes_stderr(self):
        runner = Mock(return_value=Mock(returncode=128, stdout="", stderr="synthetic-private-error-marker"))
        with patch.dict(os.environ, {"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "url.private.insteadOf",
                                     "GIT_CONFIG_VALUE_0": "https://github.com/"}):
            result = pins.resolve(self.run_record(), runner)
        supplied = runner.call_args.kwargs.get("env", {})
        self.assertEqual(supplied.get("GIT_CONFIG_GLOBAL"), os.devnull)
        self.assertEqual(supplied.get("GIT_CONFIG_NOSYSTEM"), "1")
        self.assertNotIn("GIT_CONFIG_KEY_0", supplied)
        self.assertNotIn("synthetic-private-error-marker", json.dumps(result))

    def test_offline_proof_must_query_all_recognized_tag_spellings(self):
        proof = self.proof()
        proof["command"] = proof["command"][:5]
        self.assertIsNone(pins.verified_commit(proof, "widget", "1.2.3", "github.com/example/widget"))

    def test_target_inventory_contains_only_version_only_winner_runs(self):
        winner = self.run_record()
        document = {"layers": [{"winners": [{"run": "widget"}, {"run": "complete"}]}], "runs": [
            winner, {**winner, "id": "complete", "pin_parsed": {"version": "1.2.3", "commit": self.A}},
            {**winner, "id": "unused"}]}
        self.assertEqual(pins.targets(document), [winner])

    def test_table_retains_tag_objects_peeled_commits_and_explicit_gaps(self):
        resolved = self.proof()
        gap = {**self.run_record(), "component": "missing", "version": "1.2.3",
               "status": "gap", "reason": "tag_missing"}
        table = pins.render_table([resolved, gap])
        self.assertIn(self.A, table)
        self.assertIn(self.B, table)
        self.assertIn("| missing | 1.2.3 | tag_missing | gap | gap |", table)


class OfflineApplicationTests(fixtures.FixtureTestCase):
    def test_all_nonlock_commit_sources_need_proof_before_receipt_binding(self):
        for kind in ("adoption", "stack", "runtime"):
            with self.subTest(kind=kind):
                root = self.root()
                repository = "https://github.com/example/widget"
                commit = "b" * 40
                fixture = ({"pins_linux": [{"id": "widget", "url": repository,
                                             "version": "1.2.3", "commit": commit}]} if kind == "adoption"
                           else {"stack": [{"id": "widget", "repository": repository,
                                            "version": "1.2.3", "source_pin": commit}]} if kind == "stack"
                           else {"engine": {"repository": repository, "requested_version": "1.2.3",
                                             "source_commit": commit}})
                fixtures._fixture(root, **fixture)
                run = next(row for row in final_stack.build_runs(final_stack.run_records(final_stack.Sources(root)))
                           if row["repository"] == "github.com/example/widget")
                self.assertFalse(final_stack.complete_final_pin(commit, run))
                self.assertEqual(run["source_commit_claim"], commit)
                relative = "evidence/artifacts/source-fill-fixture/nonlock-proof.json"
                proof = pins.resolve({"id": "widget", "repository": "github.com/example/widget",
                                      "pin": "1.2.3", "pin_parsed": {"version": "1.2.3", "commit": None},
                                      "source": run["source"]},
                                     Mock(return_value=Mock(returncode=0, stdout=(
                                         "a" * 40 + " refs/tags/v1.2.3\n" + commit + " refs/tags/v1.2.3^{}\n"), stderr="")))
                proof_path = root / relative
                proof_path.parent.mkdir(parents=True, exist_ok=True)
                proof_path.write_text(json.dumps(proof))
                path = (final_stack.PIN_FILES[0][1] if kind == "adoption" else final_stack.STACK
                        if kind == "stack" else final_stack.RUNTIME_TARGET)
                document = json.loads((root / path).read_text())
                entry = document["tools"][0] if kind == "adoption" else document["components"][0] if kind == "stack" else document["engine"]
                entry["source_proof"] = relative
                (root / path).write_text(json.dumps(document))
                after = next(row for row in final_stack.build_runs(final_stack.run_records(final_stack.Sources(root)))
                             if row["repository"] == "github.com/example/widget")
                self.assertTrue(final_stack.complete_final_pin(commit, after))

    def test_invalid_report_destination_refuses_before_any_upstream_query(self):
        root = self.root()
        fixtures._fixture(root)
        (root / final_stack.OUTPUT).write_text(json.dumps({
            "layers": [{"winners": [{"run": "widget"}]}], "runs": [TagResolutionTests().run_record()]}))
        with patch.object(pins, "resolve") as lookup:
            with self.assertRaisesRegex(ValueError, "repository artifact JSON"):
                pins.main(["--root", str(root), "--resolve", "catalogs/landscape/not-a-report.json"])
        lookup.assert_not_called()

    def prepare(self):
        root = self.root()
        fixtures._fixture(root, stack=[{"id": "widget", "repository": "https://github.com/example/widget",
                                       "version": "1.2.3", "source_pin": None}])
        run = next(row for row in final_stack.build_runs(final_stack.run_records(final_stack.Sources(root)))
                   if row["id"] == "widget")
        proof = pins.resolve(run, Mock(return_value=Mock(returncode=0, stderr="", stdout=(
            "a" * 40 + " refs/tags/v1.2.3\n" + "b" * 40 + " refs/tags/v1.2.3^{}\n"))))
        relative = "evidence/artifacts/source-fill-fixture/resolution.json"
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({"rows": [proof]}))
        return root, relative, proof

    def test_offline_fill_preserves_the_version_and_records_replaced_metadata(self):
        root, relative, proof = self.prepare()
        result = pins.apply_report(root, relative)
        stack = json.loads((root / final_stack.STACK).read_text())
        self.assertEqual(stack["components"][0]["version"], "1.2.3")
        self.assertEqual(stack["components"][0]["source_pin"], proof["peeled_commit"])
        self.assertEqual(result["versions_changed"], [])
        self.assertIsNone(result["source_updates"][0]["previous"])
        self.assertEqual(stack["components"][0]["source_proof"], relative + "#/rows/0")
        run = next(row for row in final_stack.build_runs(final_stack.run_records(final_stack.Sources(root)))
                   if row["id"] == "widget")
        self.assertTrue(final_stack.complete_final_pin(proof["peeled_commit"], run))

    def test_bad_later_row_cannot_partially_write_an_earlier_fill(self):
        root, relative, proof = self.prepare()
        path = root / final_stack.STACK
        before = path.read_bytes()
        invalid = copy.deepcopy(proof)
        invalid["peeled_commit"] = "f" * 40
        (root / relative).write_text(json.dumps({"rows": [proof, invalid]}))
        with self.assertRaisesRegex(ValueError, "exact tag proof"):
            pins.apply_report(root, relative)
        self.assertEqual(path.read_bytes(), before)

    def test_adoption_fill_writes_a_consumed_source_proof_reference(self):
        root = self.root()
        fixtures._fixture(root, pins_linux=[{"id": "widget", "url": "https://github.com/example/widget",
                                           "version": "1.2.3"}])
        run = next(row for row in final_stack.build_runs(final_stack.run_records(final_stack.Sources(root)))
                   if row["id"] == "widget")
        proof = pins.resolve(run, Mock(return_value=Mock(returncode=0, stdout=(
            "a" * 40 + " refs/tags/v1.2.3\n" + "b" * 40 + " refs/tags/v1.2.3^{}\n"), stderr="")))
        relative = "evidence/artifacts/source-fill-fixture/adoption-report.json"
        report = root / relative
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps({"rows": [proof]}))
        pins.apply_report(root, relative)
        tools = json.loads((root / final_stack.PIN_FILES[0][1]).read_text())["tools"]
        self.assertEqual(tools[0]["source_proof"], relative + "#/rows/0")
        after = next(row for row in final_stack.build_runs(final_stack.run_records(final_stack.Sources(root)))
                     if row["id"] == "widget")
        self.assertTrue(final_stack.complete_final_pin("b" * 40, after))

    def test_an_implicit_version_upgrade_is_refused_without_writing(self):
        root, relative, proof = self.prepare()
        path = root / final_stack.STACK
        document = json.loads(path.read_text())
        document["components"][0]["version"] = "1.2.4"
        path.write_text(json.dumps(document))
        before = path.read_bytes()
        with self.assertRaisesRegex(ValueError, "run identity"):
            pins.apply_report(root, relative)
        self.assertEqual(path.read_bytes(), before)

    def test_apply_cannot_override_the_separately_owned_claude_code_exclusion(self):
        root, relative, proof = self.prepare()
        path = root / final_stack.STACK
        document = json.loads(path.read_text())
        document["components"][0]["id"] = "claude-code"
        path.write_text(json.dumps(document))
        before = path.read_bytes()
        proof["component"] = "claude-code"
        (root / relative).write_text(json.dumps({"rows": [proof]}))
        with self.assertRaisesRegex(ValueError, "separately owned"):
            pins.apply_report(root, relative)
        self.assertEqual(path.read_bytes(), before)

    def test_lock_fill_round_trip_is_artifact_bound_and_never_writes_uv_lock(self):
        root = self.root()
        fixtures._fixture(root, lock={"alpaca-py": "1.2.3"}, stack=[
            {"id": "alpaca-py", "repository": "https://github.com/alpacahq/alpaca-py", "version": "1.2.3"}])
        lock = root / final_stack.LOCKFILE
        lock.write_text(lock.read_text() + '\nwheels = [{hash = "sha256:' + "a" * 64 + '"}]\n')
        before = lock.read_bytes()
        run = next(row for row in final_stack.build_runs(final_stack.run_records(final_stack.Sources(root)))
                   if row["id"] == "alpaca-py")
        proof = pins.resolve(run, Mock(return_value=Mock(returncode=0, stderr="", stdout=(
            "b" * 40 + " refs/tags/v1.2.3\n" + "c" * 40 + " refs/tags/v1.2.3^{}\n"))))
        proof["artifact_sha256"] = ["sha256:" + "a" * 64]
        relative = "evidence/artifacts/source-fill-fixture/resolution.json"
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({"rows": [proof]}))
        pins.apply_report(root, relative)
        sources = final_stack.Sources(root)
        after = next(row for row in final_stack.build_runs(final_stack.run_records(sources))
                     if row["id"] == "alpaca-py")
        self.assertTrue(final_stack.complete_final_pin("c" * 40, after))
        self.assertIn(relative, sources.hashes)
        self.assertEqual(lock.read_bytes(), before)

    def test_lock_report_replay_refuses_without_changing_any_retained_identity(self):
        root = self.root()
        fixtures._fixture(root, lock={"alpaca-py": "1.2.3"}, stack=[
            {"id": "alpaca-py", "repository": "https://github.com/alpacahq/alpaca-py", "version": "1.2.3"}])
        lock = root / final_stack.LOCKFILE
        lock.write_text(lock.read_text() + '\nwheels = [{hash = "sha256:' + "a" * 64 + '"}]\n')
        run = next(row for row in final_stack.build_runs(final_stack.run_records(final_stack.Sources(root)))
                   if row["id"] == "alpaca-py")
        proof = pins.resolve(run, Mock(return_value=Mock(returncode=0, stderr="", stdout=(
            "b" * 40 + " refs/tags/v1.2.3\n" + "c" * 40 + " refs/tags/v1.2.3^{}\n"))))
        proof["artifact_sha256"] = ["sha256:" + "a" * 64]
        relative = "evidence/artifacts/source-fill-fixture/one-use.json"
        report = root / relative
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps({"rows": [proof]}))
        pins.apply_report(root, relative)
        generated = final_stack.build_document(root)
        bound = next(row for row in generated["runs"] if row["id"] == "alpaca-py")
        self.assertTrue(final_stack.complete_final_pin("c" * 40, bound))
        retained = {path: path.read_bytes() for path in root.rglob("*") if path.is_file()}
        with self.assertRaisesRegex(ValueError, "resolution no longer matches the run identity"):
            pins.apply_report(root, relative)
        self.assertEqual({path: path.read_bytes() for path in root.rglob("*") if path.is_file()}, retained)
        self.assertEqual(final_stack.build_document(root), generated)

    def test_lock_package_and_run_identifier_can_differ_with_same_repository(self):
        root = self.root()
        fixtures._fixture(root, lock={"mlflow": "1.2.3"}, stack=[
            {"id": "model-registry", "repository": "https://github.com/mlflow/mlflow", "version": "1.2.3"}])
        lock = root / final_stack.LOCKFILE
        lock.write_text(lock.read_text() + '\nwheels = [{hash = "sha256:' + "a" * 64 + '"}]\n')
        run = next(row for row in final_stack.build_runs(final_stack.run_records(final_stack.Sources(root)))
                   if row["id"] == "model-registry")
        proof = pins.resolve(run, Mock(return_value=Mock(returncode=0, stdout=(
            "b" * 40 + " refs/tags/v1.2.3\n" + "c" * 40 + " refs/tags/v1.2.3^{}\n"), stderr="")))
        proof["artifact_sha256"] = ["sha256:" + "a" * 64]
        relative = "evidence/artifacts/source-fill-fixture/renamed-run.json"
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"rows": [proof]}))
        pins.apply_report(root, relative)
        after = next(row for row in final_stack.build_runs(final_stack.run_records(final_stack.Sources(root)))
                     if row["id"] == "model-registry")
        self.assertTrue(final_stack.complete_final_pin("c" * 40, after))
        supplement = json.loads((root / final_stack.LOCKFILE_SOURCES).read_text())
        self.assertEqual(supplement["bindings"][0]["package"], "mlflow")

    def test_resolve_cannot_destroy_a_report_already_referenced_by_a_lock_binding(self):
        root = self.root()
        fixtures._fixture(root, lock={"alpaca-py": "1.2.3"}, stack=[
            {"id": "alpaca-py", "repository": "https://github.com/alpacahq/alpaca-py", "version": "1.2.3"}])
        lock = root / final_stack.LOCKFILE
        lock.write_text(lock.read_text() + '\nwheels = [{hash = "sha256:' + "a" * 64 + '"}]\n')
        run = next(row for row in final_stack.build_runs(final_stack.run_records(final_stack.Sources(root)))
                   if row["id"] == "alpaca-py")
        proof = pins.resolve(run, Mock(return_value=Mock(returncode=0, stderr="", stdout=(
            "b" * 40 + " refs/tags/v1.2.3\n" + "c" * 40 + " refs/tags/v1.2.3^{}\n"))))
        proof["artifact_sha256"] = ["sha256:" + "a" * 64]
        relative = "evidence/artifacts/source-fill-fixture/resolution.json"
        report = root / relative
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps({"rows": [proof]}))
        pins.apply_report(root, relative)
        generated = final_stack.build_document(root)
        (root / final_stack.OUTPUT).write_text(final_stack.serialize(generated))
        bound = next(row for row in generated["runs"] if row["id"] == "alpaca-py")
        self.assertTrue(final_stack.complete_final_pin("c" * 40, bound))
        table = report.with_suffix(".tags.md")
        table.write_text("retained table\n")
        before, table_before = report.read_bytes(), table.read_bytes()
        with patch.object(pins, "resolve") as lookup:
            with self.assertRaisesRegex(ValueError, "already exists|referenced"):
                pins.main(["--root", str(root), "--resolve", relative])
        lookup.assert_not_called()
        self.assertEqual(report.read_bytes(), before)
        self.assertEqual(table.read_bytes(), table_before)
        after = final_stack.build_document(root)
        self.assertEqual(after, generated)

    def test_resolve_refuses_an_existing_unbound_report_or_table_before_queries(self):
        for existing in ("report", "table"):
            with self.subTest(existing=existing):
                root = self.root()
                relative = "evidence/artifacts/source-fill-fixture/new-report.json"
                report = root / relative
                report.parent.mkdir(parents=True, exist_ok=True)
                target = report if existing == "report" else report.with_suffix(".tags.md")
                target.write_text("retained source bytes\n")
                before = target.read_bytes()
                with patch.object(pins, "resolve") as lookup:
                    with self.assertRaisesRegex(ValueError, "already exists"):
                        pins.main(["--root", str(root), "--resolve", relative])
                lookup.assert_not_called()
                self.assertEqual(target.read_bytes(), before)
