"""Authenticated replay input and verified-byte build seams; SYN output only."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from tests.test_lane_b_recut_boundaries import ROOT, SOURCE, sealed_fixture
import recut

GIT_COMMIT = "000ae0e39e20b947f1bd700e0257f781c069898d"
GIT_DIRECTORY = "blueprints/us-equities/paper-open-e2e/seq2-replay/"


class ReplayInventory(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir="/var/tmp")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.source, _ = sealed_fixture(self.root)
        self.blobs = {name: subprocess.check_output(
            ["git", "-C", str(ROOT), "show", GIT_COMMIT + ":" + GIT_DIRECTORY + name])
            for name in recut.REPLAY_SOURCES}
        for name, raw in self.blobs.items():
            (self.source / name).write_bytes(raw)
        inventory = self.source / "SHA256SUMS"
        inventory.write_text("\n".join(line for line in inventory.read_text().splitlines()
            if line.split("  ", 1)[1] not in recut.REPLAY_SOURCES) + "\n")
        self.origin_bytes = inventory.read_bytes()
        self.origin = hashlib.sha256(self.origin_bytes).hexdigest()
        self.record = self.root / "SYN-replay-inventory.md"
        self.record_text = (
            "# SYN authenticated replay record\n"
            "- **Source commit:** native-agent-stack main " + GIT_COMMIT + "\n"
            "- **Directory:** " + GIT_DIRECTORY + "\n"
            "| File | Bytes | sha256 |\n| --- | ---: | --- |\n" +
            "".join("| " + name + " | " + str(len(raw)) + " | " + hashlib.sha256(raw).hexdigest() + " |\n"
                    for name, raw in self.blobs.items()))
        self.record.write_text(self.record_text)
        self.output = self.root / "SYN-seq3"

    def run_cli(self, *, expected=None):
        return subprocess.run([sys.executable, "-E", "-s", "-B", str(SOURCE / "recut.py"),
            "--source", str(self.source), "--output", str(self.output),
            "--source-commit", "SYN-reviewed-builder", "--predecessor-sha256", self.origin,
            "--replay-inventory", str(self.record), "--replay-inventory-sha256",
            expected or hashlib.sha256(self.record.read_bytes()).hexdigest()],
            capture_output=True, text=True)

    def test_git_bound_record_seals_missing_replay_rows_without_resealing_seq2(self):
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.source / "SHA256SUMS").read_bytes(), self.origin_bytes)
        manifest = (self.output / "SHA256SUMS").read_text()
        self.assertTrue(all("  " + name + "\n" in manifest for name in recut.REPLAY_SOURCES))
        request = json.loads((self.output / "GO-BINDING-REQUEST.json").read_text())
        provenance = request["replay_inventory"]
        self.assertEqual(provenance["record"], self.record.name)
        self.assertEqual(provenance["commit"], GIT_COMMIT)
        self.assertEqual(provenance["record_sha256"], hashlib.sha256(self.record.read_bytes()).hexdigest())
        for name, raw in self.blobs.items():
            self.assertEqual(provenance["files"][name]["sha256"], hashlib.sha256(raw).hexdigest())
            self.assertEqual((self.output / name).read_bytes(), raw)
            self.assertIn(hashlib.sha256(raw).hexdigest() + "  " + name + "\n", manifest)
        strict = subprocess.run(["sha256sum", "--check", "--strict", "--quiet", "SHA256SUMS"],
                                cwd=self.output, capture_output=True, text=True)
        self.assertEqual(strict.returncode, 0, strict.stderr)

    def test_genuine_original_seal_handoff_survives_replay_packaging(self):
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        launch = types.ModuleType("SYN_launch")
        launch.__file__ = str(self.output / "launch.py")
        exec(compile((self.output / "launch.py").read_text(), launch.__file__, "exec"), launch.__dict__)
        launch.ROOT = self.output
        launch.STATE = self.root / "SYN-state"
        self.assertEqual(launch.PREDECESSOR_BUNDLE, self.origin)
        new_seal = launch.sha(self.output / "SHA256SUMS")
        self.assertNotEqual(new_seal, self.origin)
        request = json.loads((self.output / "GO-BINDING-REQUEST.json").read_text())
        self.assertEqual(request["predecessor_receipt_origin_sha256"], self.origin)
        trial = "syn-old-sip"
        native = launch.STATE / "instances" / trial / "recover.json"
        launch.save(native, {"status": "passed", "flat": True, "positions": [], "unresolved_orders": [],
                             "reconciliation": {"positions": 0, "open_orders": 0}})
        handoff = launch.STATE / "completed/2026-10-14/sip.json"
        launch.save(handoff, {"stage": "sip", "session_date": "2026-10-14", "trial": trial,
            "config_sha256": launch.sha(launch.config("sip")), "recover_rc": 0,
            "native_recover_sha256": launch.sha(native), "flat": True, "positions": 0, "open_orders": 0,
            "bundle_sha256": self.origin, "boot_id": launch.boot_id(), "recover_finished_monotonic": 1})
        before = handoff.read_bytes()
        with patch.object(launch.time, "monotonic", return_value=100):
            self.assertEqual(launch.verify_handoff("sip", "2026-10-14")[0], handoff)
        self.assertEqual(handoff.read_bytes(), before)

    def test_wrong_authority_record_hash_refuses_before_copy(self):
        result = self.run_cli(expected="0" * 64)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("replay_inventory_hash_mismatch", result.stderr)
        self.assertFalse(self.output.exists())

    def test_git_rows_cannot_relabel_hash_size_commit_or_missing_file(self):
        name = "test_data_wiring.py"
        raw = self.blobs[name]
        row = "| " + name + " | " + str(len(raw)) + " | " + hashlib.sha256(raw).hexdigest() + " |\n"
        variants = [
            (self.record_text.replace(row, row.replace(str(len(raw)), str(len(raw) + 1))),
             "replay_inventory_git_mismatch"),
            (self.record_text.replace(row, row.replace(hashlib.sha256(raw).hexdigest(), "0" * 64)),
             "replay_inventory_git_mismatch"),
            (self.record_text.replace(GIT_COMMIT, "0" * 40), "replay_inventory_commit_not_landed"),
            (self.record_text.replace(row, ""), "replay_inventory_schema"),
            (self.record_text + row, "replay_inventory_schema"),
        ]
        for text, reason in variants:
            with self.subTest(reason=reason):
                self.record.write_text(text)  # Expected hash matches this SYN record; git must still refuse.
                result = self.run_cli()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(reason, result.stderr)
                self.assertFalse(self.output.exists())

    def test_copied_replay_must_equal_the_authenticated_git_blob(self):
        (self.source / "test_data_wiring.py").write_bytes(b"# SYN unbound replacement\n")
        result = self.run_cli()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("copied_bytes_not_in_sealed_inventory", result.stderr)
        self.assertFalse((self.output / "RECUT-RECEIPT.json").exists())

    def test_record_and_expected_hash_are_a_required_pair(self):
        args = [sys.executable, "-E", "-s", "-B", str(SOURCE / "recut.py"),
            "--source", str(self.source), "--output", str(self.output),
            "--source-commit", "SYN-reviewed-builder", "--predecessor-sha256", self.origin]
        for extra in (["--replay-inventory", str(self.record)],
                      ["--replay-inventory-sha256", hashlib.sha256(self.record.read_bytes()).hexdigest()]):
            with self.subTest(extra=extra[0]):
                result = subprocess.run(args + extra, capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("replay_inventory_pair_required", result.stderr)
                self.assertFalse(self.output.exists())


class VerifiedBuildBytes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir="/var/tmp")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.source, self.pin = sealed_fixture(self.root)
        self.output = self.root / "SYN-seq3"

    def test_unit_relocation_uses_the_verified_snapshot(self):
        target = self.output / "units/paper-ready-sip-8c95a50d-seq2.service"
        original = Path.read_bytes
        fired = []
        def mutate_after_read(path):
            raw = original(path)
            if path == target and not fired:
                fired.append(True)
                path.write_bytes(raw + b"# SYN unverified unit bytes\n")
            return raw
        with patch.object(Path, "read_bytes", mutate_after_read):
            recut.recut(self.source, self.output, "SYN-reviewed-builder", predecessor_sha256=self.pin)
        self.assertTrue(fired)
        unit = self.output / "units/paper-ready-sip-8c95a50d-seq3.service"
        self.assertNotIn("SYN unverified unit bytes", unit.read_text())

    def test_digest_does_not_certify_a_post_verification_mutation(self):
        name = "SYN-runtime-input.txt"
        (self.source / name).write_bytes(b"SYN authenticated bytes\n")
        sums = self.source / "SHA256SUMS"
        sums.write_text(sums.read_text() + hashlib.sha256((self.source/name).read_bytes()).hexdigest() + "  " + name + "\n")
        self.pin = hashlib.sha256(sums.read_bytes()).hexdigest()
        target = self.output / name
        original = Path.read_bytes
        fired = []
        def mutate_after_read(path):
            raw = original(path)
            if path == target and not fired:
                fired.append(True)
                path.write_bytes(b"SYN unverified bytes\n")
            return raw
        with patch.object(Path, "read_bytes", mutate_after_read):
            with self.assertRaisesRegex(ValueError, "generated_bundle_manifest_refused"):
                recut.recut(self.source, self.output, "SYN-reviewed-builder", predecessor_sha256=self.pin)
        self.assertTrue(fired)
        self.assertFalse((self.output / "RECUT-RECEIPT.json").exists())

    def test_final_check_uses_captured_inventory_bytes(self):
        native_run = recut.subprocess.run
        checked = []
        def inspect_expected(command, *args, **kwargs):
            if kwargs.get("cwd") == self.output and command[0] == "sha256sum":
                self.assertEqual(command[-1], "-")
                self.assertEqual(kwargs.get("input"), (self.output / "SHA256SUMS").read_bytes())
                checked.append(True)
            return native_run(command, *args, **kwargs)
        with patch.object(recut.subprocess, "run", inspect_expected):
            recut.recut(self.source, self.output, "SYN-reviewed-builder", predecessor_sha256=self.pin)
        self.assertEqual(checked, [True])

    def test_success_requires_emitted_inventory_identity(self):
        native_run = recut.subprocess.run
        checked = []
        def finish_check(command, *args, **kwargs):
            result = native_run(command, *args, **kwargs)
            if kwargs.get("cwd") == self.output and command[0] == "sha256sum":
                self.assertEqual(result.returncode, 0)
                checked.append(True)
                inventory = self.output / "SHA256SUMS"
                inventory.chmod(0o600)
                inventory.write_bytes(b"# SYN inventory identity boundary\n")
            return result
        with patch.object(recut.subprocess, "run", finish_check):
            with self.assertRaisesRegex(ValueError, "generated_bundle_manifest_refused"):
                recut.recut(self.source, self.output, "SYN-reviewed-builder", predecessor_sha256=self.pin)
        self.assertEqual(checked, [True])
        self.assertFalse((self.output / "RECUT-RECEIPT.json").exists())


if __name__ == "__main__":
    unittest.main()
