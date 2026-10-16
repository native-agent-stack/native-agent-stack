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
                   "artifact_sha256": ["sha256:" + "a" * 64]}
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

    def test_published_rc5_run_binds_its_peeled_commit(self):
        document = json.loads((ROOT / final_stack.OUTPUT).read_text())
        run = next(row for row in document["runs"] if row["id"] == "nautilus-trader")
        self.assertEqual(run["pin"], "2.0.0rc5; source " + COMMIT)
        self.assertEqual(run["source"], SUPPLEMENT + "#/bindings/0")
        self.assertTrue(final_stack.complete_final_pin(COMMIT, run))
        self.assertFalse(final_stack.complete_final_pin("f" * 40, run))


if __name__ == "__main__":
    unittest.main()
