"""Tests for scripts/evidence_manifest.py: the manifests/evidence.json
files[] sort normalizer/checker."""

from __future__ import annotations

import json
import hashlib
import errno
from contextlib import redirect_stdout
import io
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

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

    def git_bytes(self, *args, stdin=None):
        return subprocess.run(["git", *args], cwd=self.root, env=self.env, input=stdin,
                              capture_output=True, check=True, timeout=15).stdout

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

    def test_non_utf8_fragment_filename_cannot_erase_sibling_registration_history(self):
        (self.root / "docs").mkdir()
        (self.root / "docs/keep.md").write_text("keep the valid registration\n")
        register_file(self.root, "docs/keep.md")
        self.git("add", "--all")
        # Git 2.53.0 update-index --index-info/-z accepts raw path bytes. This
        # commits the actual offending tree without filesystem encoding limits.
        blob = self.git_bytes("hash-object", "-w", "--stdin", stdin=b"{}\n").strip()
        bad_name = em.RECORDS.encode("ascii") + b"/\xff.json"
        bad_entry = b"100644 blob " + blob + b"\t" + bad_name
        self.git_bytes("update-index", "-z", "--index-info", stdin=bad_entry + b"\0")
        self.git("commit", "--quiet", "-m", "valid registration beside non-UTF-8 fragment name")
        bad_head = self.git("rev-parse", "HEAD").stdout.strip()
        self.assertIn(bad_entry, self.git_bytes("ls-tree", "-r", "-z", bad_head,
                                              "--", em.RECORDS).split(b"\0"))
        with self.assertRaises(ValueError):
            em.load_at(self.root, bad_head)
        with self.assertRaisesRegex(InvalidPublication, "invalid current registration manifest"):
            validate_registration_rows(self.root, self.base, record_fragments=True)
        (self.root / em.record_path("docs/keep.md")).unlink()
        # add --all removes both missing fragments; the document stays tracked.
        self.commit("remove both fragments but retain the valid document")
        with self.assertRaisesRegex(InvalidPublication, "docs/keep.md: required registration row missing"):
            validate_registration_rows(self.root, self.base, before_ref=bad_head, record_fragments=True)
        register_file(self.root, "docs/keep.md")
        self.commit("restore the independently valid registration")
        validate_registration_rows(self.root, self.base, before_ref=bad_head, record_fragments=True)

    def test_current_git_listing_errors_name_escaped_entry_bytes_and_history_keeps_siblings(self):
        (self.root / "docs").mkdir()
        self.registration_branch("registered", "docs/keep.md", b"keep the valid registration\n")
        oid = b"0" * 40
        prefix = em.RECORDS.encode("ascii") + b"/"
        bad_entries = (
            b"100644 blob " + oid + b"\t" + prefix + b"\xff.json",
            b"100644 blob " + oid + b" " + prefix + b"missing-tab.json",
            b"100644 blob\t" + prefix + b"missing-object-id.json",
            b"120000 blob " + oid + b"\t" + prefix + b"symlink.json",
        )
        for bad_entry in bad_entries:
            with self.subTest(entry=bad_entry):
                def git(*args):
                    raw = self.git_bytes(*args)
                    return raw + bad_entry + b"\0" if args[0] == "ls-tree" else raw

                with self.assertRaises(ValueError) as raised:
                    em.load_at(self.root, "HEAD", git=git)
                self.assertIn(repr(bad_entry), str(raised.exception))
                historical = em.load_at(self.root, "HEAD", git=git, historical=True)
                self.assertEqual({row["path"] for row in historical["files"]},
                                 {"evidence/seed.txt", "docs/keep.md"})

    def test_unreadable_fanout_directory_cannot_produce_a_successful_partial_view(self):
        self.seed["files"] = []
        (self.root / em.EVIDENCE).write_text(json.dumps(self.seed))
        (self.root / "evidence/only.txt").write_text("the only authored record\n")
        register_file(self.root, "evidence/only.txt")
        self.assertEqual(len(em.load(self.root)["files"]), 1)
        directory = (self.root / em.record_path("evidence/only.txt")).parent
        mode = directory.stat().st_mode & 0o777
        directory.chmod(0)
        try:
            # Prove the real permission boundary; never turn a privileged run
            # that can still read the directory into a false passing probe.
            with self.assertRaises(PermissionError), os.scandir(directory):
                pass
            with self.subTest(entry_point="load"):
                with self.assertRaises((OSError, ValueError)) as raised:
                    em.load(self.root)
                self.assertIn(directory.relative_to(self.root).as_posix(), str(raised.exception))
            for option in ("--check", "--render"):
                with self.subTest(entry_point=option):
                    output = io.StringIO()
                    with redirect_stdout(output):
                        self.assertEqual(em.main(["--root", str(self.root), option]), 1)
                    self.assertIn(directory.relative_to(self.root).as_posix(), output.getvalue())
        finally:
            directory.chmod(mode)

    def test_enumerated_record_stat_failure_cannot_be_treated_as_absence(self):
        self.registration_branch("registered", "evidence/new.txt", b"registered\n")
        source = self.root / em.record_path("evidence/new.txt")
        native_stat = Path.stat

        def disappeared(path, *args, **kwargs):
            if path == source:
                raise FileNotFoundError(errno.ENOENT, "fixture disappearance", str(path))
            return native_stat(path, *args, **kwargs)

        with mock.patch.object(Path, "stat", disappeared):
            with self.assertRaises((OSError, ValueError)) as raised:
                em.load(self.root)
        self.assertIn(source.relative_to(self.root).as_posix(), str(raised.exception))

    def test_nonregular_record_is_refused_before_any_body_read(self):
        self.registration_branch("registered", "evidence/new.txt", b"registered\n")
        fifo = self.root / em.RECORDS / "not-a-regular-record.json"
        os.mkfifo(fifo)
        with self.assertRaises((OSError, ValueError)) as raised:
            em.record_sources(self.root)
        self.assertIn(fifo.relative_to(self.root).as_posix(), str(raised.exception))

    def test_unreadable_record_body_is_rejected_with_its_source_path(self):
        self.registration_branch("registered", "evidence/new.txt", b"registered\n")
        source = self.root / em.record_path("evidence/new.txt")
        mode = source.stat().st_mode & 0o777
        source.chmod(0)
        try:
            with self.assertRaises(PermissionError):
                source.read_bytes()
            with self.assertRaises((OSError, ValueError)) as raised:
                em.load(self.root)
            self.assertIn(source.relative_to(self.root).as_posix(), str(raised.exception))
        finally:
            source.chmod(mode)

    def test_historical_git_blob_read_errors_skip_only_the_named_record(self):
        (self.root / "docs").mkdir()
        for path in ("docs/keep.md", "docs/unreadable.md"):
            (self.root / path).write_text("registered document\n")
            register_file(self.root, path)
        self.commit("two independently registered documents")
        source = em.record_path("docs/unreadable.md")
        errors = (
            FileNotFoundError(errno.ENOENT, "fixture missing blob", source),
            PermissionError(errno.EACCES, "fixture unreadable blob", source),
            subprocess.CalledProcessError(128, ["git", "show", "HEAD:" + source]),
            subprocess.TimeoutExpired(["git", "show", "HEAD:" + source], 30),
        )
        for error in errors:
            with self.subTest(error=type(error).__name__):
                def git(*args):
                    if args == ("show", "HEAD:" + source):
                        raise error
                    return self.git_bytes(*args)

                with self.assertRaises((OSError, ValueError, subprocess.SubprocessError)) as raised:
                    em.load_at(self.root, "HEAD", git=git)
                self.assertIn(source, str(raised.exception))
                rows = em.load_at(self.root, "HEAD", git=git, historical=True)["files"]
                self.assertEqual({row["path"] for row in rows}, {"evidence/seed.txt", "docs/keep.md"})

    def test_seed_decode_errors_name_the_manifest_at_every_entry_point(self):
        (self.root / em.EVIDENCE).write_bytes(b"\xff")
        self.commit("undecodable seed")
        operations = {
            "load": lambda: em.load(self.root),
            "load_at": lambda: em.load_at(self.root, "HEAD"),
            "write_record": lambda: em.write_record(self.root, {
                "path": "evidence/new.txt", "sha256": "a" * 64, "bytes": 1}),
            "remove_record": lambda: em.remove_record(self.root, "evidence/seed.txt"),
        }
        for name, operation in operations.items():
            with self.subTest(entry_point=name):
                with self.assertRaises((OSError, ValueError)) as raised:
                    operation()
                self.assertIn(em.EVIDENCE, str(raised.exception))
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(em.main(["--root", str(self.root), "--check"]), 1)
        self.assertIn(em.EVIDENCE, output.getvalue())

    def test_failed_git_enumeration_cannot_clear_historical_registration_intent(self):
        (self.root / "docs").mkdir()
        registered = self.registration_branch("registered", "docs/keep.md", b"keep registration\n")
        (self.root / em.record_path("docs/keep.md")).unlink()
        self.commit("remove the registration but keep its document")
        native_run = subprocess.run
        observed = []

        def run(command, *args, **kwargs):
            if command[-6:] == ["ls-tree", "-r", "-z", registered, "--", em.RECORDS]:
                observed.append(command)
                raise subprocess.CalledProcessError(128, command)
            return native_run(command, *args, **kwargs)

        with mock.patch("scripts.validate.subprocess.run", side_effect=run):
            with self.assertRaisesRegex(InvalidPublication, em.RECORDS):
                validate_registration_rows(self.root, self.base, before_ref=registered, record_fragments=True)
        self.assertTrue(observed)

    def test_fragment_control_and_artifact_reads_fail_closed_with_the_source_name(self):
        head = self.registration_branch("registered", "evidence/new.txt", b"registered bytes\n")
        validate_registration_rows(self.root, self.base, record_fragments=True)
        native_run = subprocess.run
        targets = (
            (self.base, em.EVIDENCE, 2),
            (head, em.EVIDENCE, 2),
            (head, em.record_path("evidence/new.txt"), 1),
            (head, "evidence/new.txt", 1),
        )
        for revision, source, occurrence in targets:
            with self.subTest(revision=revision, source=source, occurrence=occurrence):
                observed = []

                def run(command, *args, **kwargs):
                    if command[-2:] == ["show", revision + ":" + source]:
                        observed.append(command)
                        if len(observed) == occurrence:
                            raise subprocess.CalledProcessError(128, command)
                    return native_run(command, *args, **kwargs)

                with mock.patch("scripts.validate.subprocess.run", side_effect=run):
                    with self.assertRaises(InvalidPublication) as raised:
                        validate_registration_rows(self.root, self.base, record_fragments=True)
                self.assertGreaterEqual(len(observed), occurrence)
                self.assertIn(source, str(raised.exception))


if __name__ == "__main__":
    unittest.main()
