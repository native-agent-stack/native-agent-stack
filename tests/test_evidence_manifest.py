"""Tests for scripts/evidence_manifest.py: the manifests/evidence.json
files[] sort normalizer/checker."""

from __future__ import annotations

import json
import hashlib
from contextlib import redirect_stdout
import io
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from scripts import evidence_manifest as em
from scripts.host_receipts import register_file
from scripts.validate import InvalidPublication, validate as validate_publication, validate_registration_rows


class EvidenceManifestSortTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "manifests").mkdir(parents=True)
        self.evidence = {
            "schema_version": 1,
            "receipts": [{"id": "sample"}],
            "files": [
                {"path": "z-later.json", "sha256": "a" * 64, "bytes": 1},
                {"path": "a-earlier.json", "sha256": "b" * 64, "bytes": 2},
                {"path": "m-middle.json", "sha256": "c" * 64, "bytes": 3},
            ],
            "convergence_records": [],
        }
        self.write()

    def write(self):
        (self.root / "manifests" / "evidence.json").write_text(
            json.dumps(self.evidence, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    def load(self):
        return json.loads((self.root / "manifests" / "evidence.json").read_text(encoding="utf-8"))

    def test_check_fails_on_unsorted_manifest(self):
        self.assertEqual(em.main(["--root", str(self.root), "--check"]), 1)

    def test_write_sorts_by_path_and_preserves_entry_fields_and_other_keys(self):
        exit_code = em.main(["--root", str(self.root), "--write"])
        self.assertEqual(exit_code, 0)
        data = self.load()
        self.assertEqual([entry["path"] for entry in data["files"]],
                          ["a-earlier.json", "m-middle.json", "z-later.json"])
        by_path = {entry["path"]: entry for entry in data["files"]}
        self.assertEqual(by_path["z-later.json"], {"path": "z-later.json", "sha256": "a" * 64, "bytes": 1})
        self.assertEqual(list(data.keys()), ["schema_version", "receipts", "files", "convergence_records"])

    def test_check_passes_after_write(self):
        self.assertEqual(em.main(["--root", str(self.root), "--write"]), 0)
        self.assertEqual(em.main(["--root", str(self.root), "--check"]), 0)

    def test_check_rejects_duplicate_paths_even_if_adjacent(self):
        self.evidence["files"] = [
            {"path": "a.json", "sha256": "a" * 64, "bytes": 1},
            {"path": "a.json", "sha256": "b" * 64, "bytes": 2},
        ]
        self.write()
        self.assertEqual(em.main(["--root", str(self.root), "--check"]), 1)

    def test_write_is_idempotent(self):
        em.main(["--root", str(self.root), "--write"])
        first = (self.root / "manifests" / "evidence.json").read_text(encoding="utf-8")
        em.main(["--root", str(self.root), "--write"])
        second = (self.root / "manifests" / "evidence.json").read_text(encoding="utf-8")
        self.assertEqual(first, second)


class EvidenceRegistrationMergeTests(unittest.TestCase):
    """Exercise real registrations and Git's native merge, with no merge driver.

    git/git@67ad42147a7acc2af6074753ebd03d904476118f (2.53.0),
    Documentation/git-merge-tree.adoc:24,214: real merges, exit 0/1.
    """

    def setUp(self):
        scratch = tempfile.TemporaryDirectory(prefix="evidence-registration-merge-")
        self.addCleanup(scratch.cleanup)
        self.root = Path(scratch.name).resolve()
        self.env = {"PATH": os.environ.get("PATH", os.defpath),
                    "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
                    "GIT_AUTHOR_NAME": "registration-fixture", "GIT_COMMITTER_NAME": "registration-fixture",
                    "GIT_AUTHOR_EMAIL": "fixture@example.invalid", "GIT_COMMITTER_EMAIL": "fixture@example.invalid"}
        self.git("init", "--quiet", "--initial-branch=main")
        (self.root / "manifests").mkdir()
        (self.root / "evidence").mkdir()
        raw = b"unchanged seed\n"
        (self.root / "evidence/seed.txt").write_bytes(raw)
        self.seed = {"schema_version": 1, "receipts": [], "convergence_records": [],
                     "file_records": "manifests/evidence-files", "authored_top_level": {"retain": True},
                     "files": [{"path": "evidence/seed.txt", "sha256": hashlib.sha256(raw).hexdigest(),
                                "bytes": len(raw), "publication_review": {"status": "fixture"},
                                "authored_extension": "retain this exact field"}]}
        (self.root / "manifests/evidence.json").write_text(json.dumps(self.seed, indent=2) + "\n")
        self.base = self.commit("base")

    def git(self, *args, check=True):
        result = subprocess.run(["git", *args], cwd=self.root, env=self.env,
                                capture_output=True, text=True, timeout=15)
        if check:
            self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def commit(self, message):
        self.git("add", "--all")
        self.git("commit", "--quiet", "-m", message)
        return self.git("rev-parse", "HEAD").stdout.strip()

    def registration_branch(self, branch, path, raw):
        self.git("checkout", "--quiet", "-b", branch, self.base)
        (self.root / path).write_bytes(raw)
        register_file(self.root, path)
        return self.commit(branch)

    def test_independent_registrations_merge_without_touching_the_shared_seed(self):
        left = self.registration_branch("left", "evidence/a.txt", b"left evidence\n")
        right = self.registration_branch("right", "evidence/b.txt", b"right evidence\n")
        merged = self.git("merge-tree", "--write-tree", left, right, check=False)
        self.assertEqual(merged.returncode, 0, "independent registrations must merge natively: " + merged.stdout)
        tree = merged.stdout.splitlines()[0]
        self.git("read-tree", "--reset", "-u", tree)
        self.assertEqual(json.loads((self.root / "manifests/evidence.json").read_text()), self.seed)
        document = em.load(self.root)
        self.assertEqual(document["authored_top_level"], {"retain": True})
        by_path = {row["path"]: row for row in document["files"]}
        self.assertEqual(set(by_path), {"evidence/a.txt", "evidence/b.txt", "evidence/seed.txt"})
        self.assertEqual(by_path["evidence/seed.txt"], self.seed["files"][0])
        for path, raw in (("evidence/a.txt", b"left evidence\n"), ("evidence/b.txt", b"right evidence\n")):
            self.assertEqual(by_path[path], {"path": path, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)})
        self.assertEqual(document, em.load(self.root), "assembly must be deterministic")

    def test_same_evidence_updates_remain_a_native_conflict_and_keep_authored_metadata(self):
        left = self.registration_branch("left", "evidence/seed.txt", b"left replacement\n")
        row = em.load(self.root)["files"][0]
        self.assertEqual(row["publication_review"], self.seed["files"][0]["publication_review"])
        self.assertEqual(row["authored_extension"], self.seed["files"][0]["authored_extension"])
        right = self.registration_branch("right", "evidence/seed.txt", b"right replacement\n")
        merged = self.git("merge-tree", "--write-tree", left, right, check=False)
        self.assertEqual(merged.returncode, 1, "competing authored records must not be silently combined")
        self.assertIn(em.record_path("evidence/seed.txt"), merged.stdout)

    def test_git_registration_validation_uses_the_recorded_hash_and_rejects_tampering(self):
        self.registration_branch("registered", "evidence/new.txt", b"reviewed bytes\n")
        validate_registration_rows(self.root, self.base, record_fragments=True)
        (self.root / "evidence/new.txt").write_bytes(b"unregistered replacement\n")
        self.commit("tampered artifact")
        with self.assertRaisesRegex(InvalidPublication, "SHA-256 mismatch at Git head"):
            validate_registration_rows(self.root, self.base, record_fragments=True)

    def test_an_enabled_seed_cannot_be_rewritten_to_restore_shared_file_registration(self):
        (self.root / "evidence/new.txt").write_bytes(b"new\n")
        self.seed["files"].insert(0, {"path": "evidence/new.txt", "sha256": hashlib.sha256(b"new\n").hexdigest(), "bytes": 4})
        (self.root / "manifests/evidence.json").write_text(json.dumps(self.seed, indent=2) + "\n")
        self.commit("shared-array registration")
        with self.assertRaisesRegex(InvalidPublication, "frozen.*seed"):
            validate_registration_rows(self.root, self.base, record_fragments=True)

    def test_checker_rejects_a_malformed_record_instead_of_checking_only_the_seed(self):
        self.registration_branch("registered", "evidence/new.txt", b"reviewed bytes\n")
        path = self.root / em.record_path("evidence/new.txt")
        path.write_text('{"schema_version": 1, "record": {"path": "evidence/new.txt", "sha256": "bad", "bytes": true}}')
        self.assertEqual(em.main(["--root", str(self.root), "--check"]), 1)

    def test_legacy_registration_still_writes_the_shared_manifest_without_opt_in(self):
        self.seed.pop("file_records")
        (self.root / "manifests/evidence.json").write_text(json.dumps(self.seed, indent=2) + "\n")
        (self.root / "evidence/new.txt").write_bytes(b"legacy\n")
        register_file(self.root, "evidence/new.txt")
        expected = {**self.seed, "files": [
            {"path": "evidence/new.txt", "sha256": hashlib.sha256(b"legacy\n").hexdigest(), "bytes": 7},
            *self.seed["files"]]}
        self.assertEqual((self.root / "manifests/evidence.json").read_text(), json.dumps(expected, indent=2) + "\n")
        self.assertFalse((self.root / "manifests/evidence-files").exists())

    def test_tombstone_cannot_hide_a_still_tracked_artifact(self):
        em.remove_record(self.root, "evidence/seed.txt")
        self.commit("remove registration only")
        with self.assertRaisesRegex(InvalidPublication, "required registration row missing"):
            validate_registration_rows(self.root, self.base, record_fragments=True)
        (self.root / "evidence/seed.txt").unlink()
        self.commit("remove artifact too")
        validate_registration_rows(self.root, self.base, record_fragments=True)
        self.assertEqual(em.load(self.root)["files"], [])

    def test_misnamed_duplicate_and_symlink_records_fail_closed(self):
        self.registration_branch("registered", "evidence/new.txt", b"reviewed bytes\n")
        source = self.root / em.record_path("evidence/new.txt")
        duplicate = source.with_name("duplicate.json")
        duplicate.write_bytes(source.read_bytes())
        with self.assertRaises(ValueError):
            em.load(self.root)
        duplicate.unlink()
        duplicate.symlink_to(source.name)
        with self.assertRaises(ValueError):
            em.load(self.root)
        duplicate.unlink()
        source.write_text('{"schema_version": 1, "schema_version": 1, "record": {}}')
        with self.assertRaises(ValueError):
            em.load(self.root)

    def test_git_tree_reader_does_not_borrow_records_from_the_current_checkout(self):
        self.registration_branch("registered", "evidence/new.txt", b"reviewed bytes\n")
        self.assertEqual(em.load_at(self.root, self.base)["files"], self.seed["files"])
        self.assertEqual(em.load_at(self.root, "HEAD"), em.load(self.root))

    def test_record_paths_cannot_escape_or_register_the_registry_itself(self):
        for path in ("../outside", "/outside", "evidence/../outside", "evidence\\outside",
                     ".git/config", "manifests/evidence.json", "manifests/evidence-files/nested.json"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                em.write_record(self.root, {"path": path, "sha256": "a" * 64, "bytes": 1})

    def test_render_preserves_expected_hashes_and_never_rewrites_source_records(self):
        self.registration_branch("registered", "evidence/new.txt", b"reviewed bytes\n")
        sources = [self.root / em.EVIDENCE, self.root / em.record_path("evidence/new.txt")]
        before = {path: path.read_bytes() for path in sources}
        (self.root / "evidence/new.txt").write_bytes(b"tampered after registration\n")
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(em.main(["--root", str(self.root), "--render"]), 0)
        rows = {row["path"]: row for row in json.loads(output.getvalue())["files"]}
        self.assertEqual(rows["evidence/new.txt"]["sha256"], hashlib.sha256(b"reviewed bytes\n").hexdigest())
        self.assertEqual(before, {path: path.read_bytes() for path in sources})

    def test_git_tree_rejects_symlink_even_when_its_target_text_is_valid_record_json(self):
        self.registration_branch("registered", "evidence/new.txt", b"reviewed bytes\n")
        source = self.root / em.record_path("evidence/new.txt")
        document = json.loads(source.read_text())
        source.unlink()
        source.symlink_to(json.dumps(document, separators=(",", ":")))
        self.commit("symlink record")
        with self.assertRaisesRegex(ValueError, "regular Git blob"):
            em.load_at(self.root, "HEAD")

    def test_prior_fragment_history_keeps_registration_intent_for_non_evidence_files(self):
        (self.root / "docs").mkdir()
        self.registration_branch("registered", "docs/new.md", b"registered doc\n")
        (self.root / em.record_path("docs/new.md")).unlink()
        self.commit("lost registration after first push")
        with self.assertRaisesRegex(InvalidPublication, "docs/new.md: required registration row missing"):
            validate_registration_rows(self.root, self.base, record_fragments=True)

    def test_malformed_sibling_cannot_erase_valid_historical_registration(self):
        (self.root / "docs").mkdir()
        (self.root / "docs/keep.md").write_text("keep this registration\n")
        (self.root / "docs/bad.md").write_text("invalid metadata creates no intent\n")
        register_file(self.root, "docs/keep.md")
        valid_source = self.root / em.record_path("docs/keep.md")
        bad_source = self.root / em.record_path("docs/bad.md")
        bad_source.parent.mkdir(parents=True, exist_ok=True)
        bad_source.write_text(json.dumps({"schema_version": 1, "record": {
            "path": "docs/bad.md", "sha256": "malformed", "bytes": 1}}))
        bad_head = self.commit("valid registration beside a malformed sibling")
        with self.assertRaisesRegex(InvalidPublication, "invalid current registration manifest"):
            validate_registration_rows(self.root, self.base, record_fragments=True)
        valid_source.unlink()
        bad_source.unlink()
        self.commit("remove both fragments but retain both documents")
        with self.assertRaisesRegex(InvalidPublication, "docs/keep.md: required registration row missing"):
            validate_registration_rows(self.root, self.base, before_ref=bad_head, record_fragments=True)
        register_file(self.root, "docs/keep.md")
        self.commit("restore only the independently valid registration")
        validate_registration_rows(self.root, self.base, before_ref=bad_head, record_fragments=True)

    def test_valid_artifact_paths_cannot_collide_as_record_file_and_directory(self):
        paths = ("evidence/a", "evidence/a.json/b", "evidence/" + "x" * 255)
        for path in paths:
            artifact = self.root / path
            artifact.parent.mkdir(parents=True, exist_ok=True)
            artifact.write_bytes(path.encode("utf-8"))
            try:
                register_file(self.root, path)
            except OSError as error:
                self.fail(f"independent valid artifact {path!r} could not be registered: {error}")
        self.commit("register independently valid artifact names")
        rows = {row["path"]: row for row in em.load_at(self.root, "HEAD")["files"]}
        self.assertEqual(set(rows), {*paths, "evidence/seed.txt"})
        for path in paths:
            self.assertEqual(rows[path]["sha256"], hashlib.sha256(path.encode("utf-8")).hexdigest())
        self.assertEqual(json.loads((self.root / em.EVIDENCE).read_text()), self.seed)

    def test_bad_fragment_diagnostic_identifies_its_own_source_file(self):
        self.registration_branch("registered", "evidence/new.txt", b"reviewed bytes\n")
        source = self.root / em.record_path("evidence/new.txt")
        for raw in ('{', '{"schema_version": 1, "record": {"path": "evidence/new.txt", "sha256": "bad", "bytes": 1}}'):
            with self.subTest(raw=raw):
                source.write_text(raw)
                output = io.StringIO()
                with redirect_stdout(output):
                    self.assertEqual(em.main(["--root", str(self.root), "--check"]), 1)
                self.assertIn(source.relative_to(self.root).as_posix(), output.getvalue())
                self.assertNotIn(em.EVIDENCE + ": invalid JSON", output.getvalue())

    def test_production_validator_keeps_the_root_registry_legacy(self):
        from tests.test_validate import PublicationValidationTests

        for case in ("marker", "null-marker", "unregistered-tree", "registered-tree"):
            with self.subTest(case=case):
                fixture = PublicationValidationTests()
                self.addCleanup(fixture.doCleanups)
                fixture.setUp()
                validate_publication(fixture.root)
                if case in {"marker", "null-marker"}:
                    fixture.evidence["file_records"] = em.RECORDS if case == "marker" else None
                    fixture.save()
                    diagnostic = "file_records.*legacy"
                else:
                    source = em.RECORDS + "/00/probe.json"
                    fixture.write(source, "{}\n")
                    if case == "registered-tree":
                        register_file(fixture.root, source)
                    diagnostic = "manifests/evidence-files/.*legacy"
                with self.assertRaisesRegex(InvalidPublication, diagnostic):
                    validate_publication(fixture.root)


if __name__ == "__main__":
    unittest.main()
