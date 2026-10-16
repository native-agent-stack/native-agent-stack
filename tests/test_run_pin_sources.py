"""Native tag resolution and offline source fills, with no version upgrades."""
import copy
import ast
import json
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
        self.assertEqual((result["status"], result["exit_code"], result["stderr"]), ("gap", 128, "unavailable"))
        timeout = pins.resolve(self.run_record(), Mock(side_effect=subprocess.TimeoutExpired("git", 45, b"partial", b"timeout")))
        self.assertEqual((timeout["status"], timeout["stdout"], timeout["stderr"]), ("gap", "partial", "timeout"))
        self.assertIn("refs/tags/v1.2.3^{}", timeout["command"])

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
