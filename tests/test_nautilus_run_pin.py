"""Bind the unchanged rc5 lock entry to its exact upstream source identity."""
import copy
import json
from pathlib import Path
import unittest

from scripts import final_stack
from tests import test_final_stack as fixtures

ROOT = Path(__file__).resolve().parents[1]
SUPPLEMENT = "catalogs/landscape/lockfile-source-identities.json"
COMMIT = "1b0a49d2792a9432a3aca3fcb617ce7a630d905e"
REPOSITORY = "github.com/nautechsystems/nautilus_trader"


class NautilusRunPinTests(fixtures.FixtureTestCase):
    def prepare(self):
        root = self.root()
        fixtures._fixture(root, lock={"nautilus-trader": "2.0.0rc5"}, stack=[
            {"id": "nautilus-trader", "repository": "https://" + REPOSITORY,
             "version": "2.0.0rc5"}])
        lock = root / final_stack.LOCKFILE
        lock.write_text(lock.read_text() + '\nwheels = [{url = "https://example.org/rc5.whl", hash = "sha256:'
                        + "a" * 64 + '"}]\n')
        binding = {"source": final_stack.LOCKFILE + "#/package/1", "package": "nautilus-trader",
                   "version": "2.0.0rc5", "repository": REPOSITORY, "commit": COMMIT,
                   "artifact_sha256": ["sha256:" + "a" * 64],
                   "source_proof": "evidence/artifacts/pin-fixture/tag-resolution.json"}
        proof = root / binding["source_proof"]
        proof.parent.mkdir(parents=True, exist_ok=True)
        proof.write_text(json.dumps({
            "component": "nautilus-trader", "version": "2.0.0rc5", "repository": REPOSITORY,
            "command": ["git", "ls-remote", "https://" + REPOSITORY + ".git",
                        "refs/tags/v2.0.0rc5", "refs/tags/v2.0.0rc5^{}"],
            "exit_code": 0, "stderr": "",
            "stdout": "b" * 40 + "\trefs/tags/v2.0.0rc5\n" + COMMIT + "\trefs/tags/v2.0.0rc5^{}\n",
            "tag_object": "b" * 40, "peeled_commit": COMMIT}))
        return root, binding

    def write_binding(self, root, bindings):
        path = root / SUPPLEMENT
        path.write_text(json.dumps({"schema_version": 1, "lockfile": final_stack.LOCKFILE,
                                   "bindings": bindings}))

    def record(self, root):
        return next(row for row in final_stack.run_records(final_stack.Sources(root))
                    if row["id"] == "nautilus-trader")

    def test_commit_cited_receipt_binds_only_after_exact_lock_identity(self):
        root, binding = self.prepare()
        receipt_pin = "2.0.0rc5; source " + COMMIT
        before = final_stack.build_runs([self.record(root)])[0]
        self.assertFalse(final_stack.complete_final_pin(receipt_pin, before))
        self.write_binding(root, [binding])
        after = final_stack.build_runs([self.record(root)])[0]
        self.assertTrue(final_stack.complete_final_pin(receipt_pin, after))
        self.assertEqual(after["pin"], receipt_pin)
        self.assertEqual(after["source"], SUPPLEMENT + "#/bindings/0")

    def test_version_artifact_repository_package_or_commit_mismatch_is_unparsed(self):
        for field, wrong in [("version", "2.0.0rc6"), ("artifact_sha256", ["sha256:" + "b" * 64]),
                             ("repository", "github.com/example/imposter"), ("package", "other"),
                             ("commit", "v2.0.0rc5")]:
            with self.subTest(field=field):
                root, binding = self.prepare()
                binding[field] = wrong
                self.write_binding(root, [binding])
                self.assertEqual(self.record(root)["parsed"], {"pin_parse": "unparsed"})

    def test_duplicate_binding_is_refused(self):
        root, binding = self.prepare()
        self.write_binding(root, [binding, copy.deepcopy(binding)])
        with self.assertRaisesRegex(final_stack.FinalStackError, "duplicate source identity"):
            self.record(root)

    def test_missing_stack_repository_cannot_be_invented_by_a_fallback(self):
        root, binding = self.prepare()
        path = root / final_stack.STACK
        document = json.loads(path.read_text())
        document["components"] = []
        path.write_text(json.dumps(document))
        self.write_binding(root, [binding])
        record = self.record(root)
        self.assertIsNone(record["repository"])
        self.assertEqual(record["parsed"], {"pin_parse": "unparsed"})

    def test_published_bindings_carry_only_fields_the_reader_consumes(self):
        document = json.loads((ROOT / SUPPLEMENT).read_text())
        allowed = {"source", "package", "version", "artifact_sha256", "repository", "commit", "source_proof"}
        for binding in document["bindings"]:
            self.assertFalse(set(binding) - allowed)

    def test_well_formed_wrong_commit_cannot_bind_against_the_retained_tag(self):
        root, binding = self.prepare()
        binding["commit"] = "f" * 40
        self.write_binding(root, [binding])
        run = final_stack.build_runs([self.record(root)])[0]
        self.assertEqual(run.get("pin_parse"), "unparsed")
        self.assertFalse(final_stack.complete_final_pin("f" * 40, run))

    def test_missing_contradictory_or_foreign_source_proof_is_unparsed(self):
        for case in ("missing", "repository", "version", "stdout", "advertised_commit", "tag_object"):
            with self.subTest(case=case):
                root, binding = self.prepare()
                path = root / binding["source_proof"]
                proof = json.loads(path.read_text())
                if case == "missing":
                    path.unlink()
                elif case == "repository":
                    proof["command"][2] = "https://github.com/example/foreign.git"
                elif case == "version":
                    proof["version"] = "2.0.0rc6"
                elif case == "stdout":
                    proof["stdout"] = ""
                elif case == "advertised_commit":
                    proof["peeled_commit"] = "f" * 40
                else:
                    binding["commit"] = proof["tag_object"]
                if case != "missing":
                    path.write_text(json.dumps(proof))
                self.write_binding(root, [binding])
                self.assertEqual(self.record(root)["parsed"], {"pin_parse": "unparsed"})

    def test_published_rc5_run_binds_its_peeled_commit(self):
        document = json.loads((ROOT / final_stack.OUTPUT).read_text())
        run = next(row for row in document["runs"] if row["id"] == "nautilus-trader")
        self.assertEqual(run["pin"], "2.0.0rc5; source " + COMMIT)
        self.assertEqual(run["source"], SUPPLEMENT + "#/bindings/0")
        self.assertTrue(final_stack.complete_final_pin(COMMIT, run))
        self.assertFalse(final_stack.complete_final_pin("f" * 40, run))

    def test_real_lock_binding_replays_and_hashes_the_published_source_observation(self):
        sources = final_stack.Sources(ROOT)
        record = next(row for row in final_stack.run_records(sources) if row["id"] == "nautilus-trader")
        self.assertEqual(record["parsed"]["pin_parsed"]["commit"], COMMIT)
        self.assertIn("evidence/artifacts/nautilus-run-pin-20261016/tag-resolution.json", sources.hashes)


if __name__ == "__main__":
    unittest.main()
