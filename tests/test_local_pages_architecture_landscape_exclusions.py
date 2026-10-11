"""Every landscape JSON is canonical, granted or explicitly excluded.

Regression for the Architecture refresh that #878 stopped: it added
catalogs/landscape/grand-catalog-20261008.json (28389911 bytes) and its slot
index, which the committed policy neither granted nor excluded. Both landscape
globs (architecture_sources.build and architecture_builder.refresh_if_changed)
then refused every refresh with SourcePolicyError, which the local-pages
refresh receipt records under .architecture.reason.
"""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tests.local_pages_architecture_policy_fixture import G5, policy_fixture

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "tools/local-pages"
POLICY_PATH = HERE / "source_policy.json"
EXCLUDED = "catalogs/landscape/excluded-fixture.json"


def load(name):
    spec = importlib.util.spec_from_file_location("landscape_exclusion_" + name, HERE / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


POLICY, SOURCES, EVIDENCE, BUILDER = (load(name) for name in ("source_policy", "architecture_sources", "architecture_evidence", "architecture_builder"))


class CommittedLandscapeSetTests(unittest.TestCase):
    def test_every_committed_landscape_json_is_canonical_granted_or_excluded(self):
        tracked = subprocess.run(["git", "ls-files", "-z", "--", ":(glob)catalogs/landscape/*.json"], cwd=ROOT,
                                 check=True, capture_output=True).stdout.decode().split("\0")
        manifest = json.loads((ROOT / "catalogs/landscape/manifest.json").read_text())
        policy = json.loads(POLICY_PATH.read_text())
        canonical = set(manifest["catalogs"].values()) | {"catalogs/landscape/manifest.json"}
        granted = {row["path"] for row in policy["architecture"]["architecture_supplement"] if row["root"] == "repo"}
        excluded = {row["path"] for row in policy.get("architecture_supplement_exclusions", [])}
        unclassified = sorted(path for path in tracked if path and path not in canonical | granted | excluded)
        self.assertEqual(unclassified, [], "Grant or explicitly exclude each landscape JSON file; "
                                           "an unclassified file stops every Architecture refresh.")

    def test_committed_catalog_set_builds_through_the_committed_policy(self):
        with tempfile.TemporaryDirectory() as state:
            reads = POLICY.ArchitectureReads(ROOT, Path(state), policy_path=POLICY_PATH)
            opened, original = [], reads.read

            def read(role, path, *args, **kwargs):
                opened.append(Path(path).absolute())
                return original(role, path, *args, **kwargs)

            with patch.object(reads, "read", side_effect=read):
                try:
                    model = SOURCES.build(ROOT, Path(state), reads=reads)
                except POLICY.SourcePolicyError as error:
                    self.fail(f"committed landscape catalog set refused: SourcePolicyError: {error}")
        policy = json.loads(POLICY_PATH.read_text())
        expected = {row["path"]: row["reason"] for row in policy["architecture_supplement_exclusions"]}
        self.assertEqual({row["path"]: row["reason"] for row in model["excluded_supplements"]}, expected)
        for relative in expected:
            self.assertNotIn(ROOT / relative, opened)
        catalogs = json.loads((ROOT / "catalogs/landscape/manifest.json").read_text())["catalogs"].values()
        self.assertEqual(model["layer_count"], sum(len(json.loads((ROOT / relative).read_text())["layers"]) for relative in catalogs))
        self.assertIn(ROOT / "catalogs/landscape/component-evidence-matrix.json", opened)

    def test_committed_exclusions_name_files_above_the_read_bound_or_without_projected_records(self):
        policy = json.loads(POLICY_PATH.read_text())
        rows = {row["path"]: row for row in policy["architecture_supplement_exclusions"]}
        self.assertEqual(set(rows), {"catalogs/landscape/grand-catalog-counts.json",
                                     "catalogs/landscape/grand-catalog-20261008.json",
                                     "catalogs/landscape/grand-catalog-index-20261008.json"})
        self.assertGreater((ROOT / "catalogs/landscape/grand-catalog-20261008.json").stat().st_size, SOURCES._DOC_LIMIT)
        index = json.loads((ROOT / "catalogs/landscape/grand-catalog-index-20261008.json").read_text())
        self.assertFalse({"layers", "rows", "candidates", "components"} & set(index))
        counts = json.loads((ROOT / "catalogs/landscape/grand-catalog-counts.json").read_text())
        self.assertFalse({"layers", "rows", "candidates", "components"} & set(counts))
        provenance = {row["path"]: row for row in policy["architecture_derivation_sources"]}
        for relative in rows:
            self.assertRegex(provenance[relative]["pin"], r"\A[0-9a-f]{40}\Z")
            self.assertRegex(provenance[relative]["sha256"], r"\A[0-9a-f]{64}\Z")


class ExclusionFixture(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.root, self.state = self.base / "repo", self.base / "state"
        self.state.mkdir(parents=True)
        self.write("catalogs/landscape/manifest.json", {"catalogs": {"foundation": "catalogs/landscape/foundation.json"}})
        self.write("catalogs/landscape/foundation.json", {"layers": [{"layer_id": "native-clients", "title": "Native clients", "winners": []}]})
        self.write("catalogs/landscape/supplement.json", {"rows": []})
        excluded = self.root / EXCLUDED
        excluded.write_bytes(b"\xff not JSON and never readable")
        excluded.chmod(0)
        self.addCleanup(excluded.chmod, 0o600)
        self.document = json.loads(policy_fixture(self.base / "base-policy.json").read_text())
        self.document["architecture_supplement_exclusions"] = [{"root": "repo", "path": EXCLUDED, "reason": "fixture exclusion"}]
        self.policy_path = self.base / "independent-policy.json"
        self.save()

    def write(self, relative, document):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(document), encoding="utf-8")

    def save(self):
        self.policy_path.write_text(json.dumps(self.document))

    def reads(self):
        return POLICY.ArchitectureReads(self.root, self.state, policy_path=self.policy_path, user_root=self.base / "user")


class ExclusionMechanismTests(ExclusionFixture):
    def test_excluded_file_is_skipped_before_any_byte_access_and_reported(self):
        if os.geteuid() == 0:
            self.skipTest("an unreadable fixture needs a non-root user")
        with patch.object(SOURCES, "SOURCE_POLICY_PATH", self.policy_path), patch.object(EVIDENCE, "SOURCE_POLICY_PATH", self.policy_path):
            model = SOURCES.build(self.root, self.state)
        self.assertEqual(model["excluded_supplements"], [{"path": EXCLUDED, "reason": "fixture exclusion"}])
        self.assertNotIn(EXCLUDED, [source.get("path") for source in model["sources"]])
        self.assertIn("catalogs/landscape/supplement.json", [source.get("path") for source in model["sources"]])

    def test_unlisted_landscape_file_still_fails_closed(self):
        self.write("catalogs/landscape/unreviewed.json", {"rows": []})
        with patch.object(SOURCES, "SOURCE_POLICY_PATH", self.policy_path), patch.object(EVIDENCE, "SOURCE_POLICY_PATH", self.policy_path):
            # Each loader binds its own SourcePolicyError class; ValueError is their shared base.
            with self.assertRaisesRegex(ValueError, "architecture_supplement"):
                SOURCES.build(self.root, self.state)

    def test_exclusions_must_be_exact_reasoned_landscape_files_never_granted(self):
        bad = (
            {"root": "repo", "path": EXCLUDED},
            {"root": "repo", "path": EXCLUDED, "reason": " "},
            {"root": "repo", "path": EXCLUDED, "reason": "x", "sha256": "0" * 64},
            {"root": "state", "path": EXCLUDED, "reason": "x"},
            {"root": "repo", "path": "catalogs/foundation/manifest.json", "reason": "x"},
            {"root": "repo", "path": "catalogs/landscape/nested/file.json", "reason": "x"},
            {"root": "repo", "path": "catalogs/landscape/notes.md", "reason": "x"},
            {"root": "repo", "path": "catalogs/landscape/../landscape/x.json", "reason": "x"},
            {"root": "repo", "path": "catalogs/landscape/credentials.json", "reason": "x"},
            {"root": "repo", "path": "catalogs/landscape/supplement.json", "reason": "granted too"},
        )
        for row in bad:
            with self.subTest(row=row):
                self.document["architecture_supplement_exclusions"] = [row]
                self.save()
                with self.assertRaises(POLICY.SourcePolicyError):
                    self.reads()
        self.document["architecture_supplement_exclusions"] = [{"root": "repo", "path": EXCLUDED, "reason": "x"}] * 2
        self.save()
        with self.assertRaises(POLICY.SourcePolicyError):
            self.reads()
        self.document["architecture_supplement_exclusions"] = {"path": EXCLUDED}
        self.save()
        with self.assertRaises(POLICY.SourcePolicyError):
            self.reads()

    def test_refresh_signature_skips_exclusions_and_still_refuses_unlisted_files(self):
        if os.geteuid() == 0:
            self.skipTest("an unreadable fixture needs a non-root user")
        for relative in ("catalogs/north-star/readiness.json", "adoption/skills/manifest.json", "manifests/stack.json",
                         "manifests/evidence.json", "adoption/manifest.json"):
            self.write(relative, {})
        current = self.state / "coordination/command-center/pages/cc-now.json"
        current.parent.mkdir(parents=True)
        current.write_text("{}")
        output, receipt = self.base / "served", self.base / "nonserved/receipt.json"
        original = BUILDER.load
        modules = {"build_pages": SimpleNamespace(no_symlinks=lambda path: path.absolute(), prune_architecture_details=lambda *unused: None),
                   "architecture_evidence": SimpleNamespace(invocation_source=lambda unused, reads=None: {"sha256": "a" * 64}),
                   "source_policy": original("source_policy"), "architecture_inventory": original("architecture_inventory"),
                   "architecture_sources": SimpleNamespace(_FINAL_ASSET=G5)}
        calls = []

        def generate(*unused):
            calls.append(1)
            output.mkdir(exist_ok=True)
            (output / "architecture.html").write_text("page")
            receipt.parent.mkdir(parents=True, exist_ok=True)
            receipt.write_text(json.dumps({"generated_utc": "2026-01-01T00:00:00Z"}))
            return {"generated_utc": "2026-01-01T00:00:00Z"}

        with patch.object(modules["architecture_inventory"], "USER_ROOT", self.base / "user"), \
                patch.object(BUILDER, "SOURCE_POLICY_PATH", self.policy_path), \
                patch.object(BUILDER, "load", side_effect=lambda name: modules[name]), \
                patch.object(BUILDER, "build", side_effect=generate):
            BUILDER.refresh_if_changed(self.root, self.state, output, receipt)
            self.assertEqual(len(calls), 1)
            self.write("catalogs/landscape/unreviewed.json", {"rows": []})
            with self.assertRaisesRegex(modules["source_policy"].SourcePolicyError, "architecture_supplement"):
                BUILDER.refresh_if_changed(self.root, self.state, output, receipt)


if __name__ == "__main__":
    unittest.main()
