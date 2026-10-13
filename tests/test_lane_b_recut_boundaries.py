"""SYN public re-cut/dry-run regression boundaries, never host unit mutations."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "blueprints/us-equities/paper-readiness-seq3"
sys.path.insert(0, str(SOURCE))
import recut


def sealed_fixture(root, *, embedded=None):
    source = root / "SYN-source"
    source.mkdir()
    embedded = embedded or source
    for dest, src in (("launch.py", "seq2-launch.txt"), ("issue_go.py", "seq2-issue-go.txt")):
        (source / dest).write_bytes((ROOT / "tests/fixtures" / src).read_bytes())
    (source / "GO-BINDING-REQUEST.json").write_text("{}")
    (source / "prepare_units.py").write_text("# OLD touch HOST STOP template, never execute\n")
    (source / "GO-PROCEDURE.md").write_text("OLD seq2 touch HOST STOP\n")
    (source / "DEPLOYMENT.md").write_text("OLD seq2\n")
    (source / "test_unit_contracts.py").write_text("self.assertEqual(len(hooks),3)\nself.assertIn('touch --no-dereference',hooks[1])\nself.assertTrue(hooks[2].endswith('recover'))\n")
    (source / "frozen").mkdir()
    (source / "frozen/native.txt").write_text("SYN frozen bytes\n")
    (source / "configs").mkdir()
    (source / "configs/sip.json").write_text("{}\n")
    units = source / "units"
    units.mkdir()
    for stage in ("record", "scan", "pre", "pre-skip", "sip", "lev1", "lev2", "lev4", "edge2", "edge8", "iex"):
        for ext in ("path", "service"):
            body = "# SYN\nWorkingDirectory=" + str(embedded) + "\nExecStart=" + str(embedded) + "/launch.py\n"
            if ext == "service" and stage not in ("record", "scan", "pre-skip"):
                body += "ExecStopPost=/usr/bin/bash -c '/usr/bin/touch /SYN/alpaca-paper/STOP'\n"
            (units / ("paper-ready-" + stage + "-8c95a50d-seq2." + ext)).write_text(body)
    inventory = "\n".join(hashlib.sha256(p.read_bytes()).hexdigest() + "  " + p.relative_to(source).as_posix()
        for p in sorted(source.rglob("*")) if p.is_file() and p.name != "GO-BINDING-REQUEST.json") + "\n"
    (source / "SHA256SUMS").write_text(inventory)
    return source, hashlib.sha256(inventory.encode()).hexdigest()


class RecutBoundaries(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(dir="/var/tmp")
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)

    def build(self, source, pin, output):
        with patch.object(recut, "PREDECESSOR", pin):
            return recut.recut(source, output, "SYN-fix-pin")

    def test_copied_source_relocates_the_root_actually_embedded_in_units(self):
        embedded = self.root / "ORIGINAL-sealed-bundle"
        source, pin = sealed_fixture(self.root, embedded=embedded)
        output = self.root / "SYN-relocated"
        self.build(source, pin, output)
        for unit in (output / "units").iterdir():
            text = unit.read_text()
            self.assertIn("WorkingDirectory=" + str(output), text)
            self.assertIn("ExecStart=" + str(output) + "/launch.py", text)
            self.assertNotIn(str(embedded), text)

    def test_symlink_ancestor_cannot_place_output_inside_the_source(self):
        source, pin = sealed_fixture(self.root)
        alias = self.root / "SYN-alias"
        alias.symlink_to(source, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "new_bundle_destination_required"):
            self.build(source, pin, alias / "inside")
        self.assertFalse((source / "inside").exists())

    def test_dotdot_cannot_place_output_inside_the_source(self):
        source, pin = sealed_fixture(self.root)
        outside = self.root / "outside"; outside.mkdir()
        destination = outside / ".." / source.name / "inside"
        with self.assertRaisesRegex(ValueError, "new_bundle_destination_required"):
            self.build(source, pin, destination)
        self.assertFalse((source / "inside").exists())

    def test_read_only_packet_root_is_writable_only_during_new_generation(self):
        source, pin = sealed_fixture(self.root)
        source.chmod(0o500)
        output = self.root / "SYN-new"
        self.build(source, pin, output)
        self.assertTrue((output / "lane_latch.py").is_file())
        self.assertEqual(source.stat().st_mode & 0o777, 0o500)
        self.assertEqual(output.stat().st_mode & 0o777, 0o500)

    def test_old_builder_and_operational_docs_are_neutralized(self):
        source, pin = sealed_fixture(self.root)
        output = self.root / "SYN-new"
        self.build(source, pin, output)
        self.assertFalse((output / "prepare_units.py").exists())
        text = (output / "GO-PROCEDURE.md").read_text()
        self.assertIn("disable --now", text)
        self.assertIn("zero active", text)
        self.assertNotIn("OLD seq2 touch", text)
        self.assertNotIn("len(hooks),3", (output / "test_unit_contracts.py").read_text())

    def test_unchanged_bytes_are_a_computed_comparison(self):
        source, pin = sealed_fixture(self.root)
        output = self.root / "SYN-new"
        result = self.build(source, pin, output)
        self.assertEqual(result["unchanged_comparison"]["frozen_files"], 1)
        self.assertEqual(result["unchanged_comparison"]["config_files"], 1)
        self.assertTrue(result["unchanged_comparison"]["equal"])

    def test_changeover_instructions_retire_all_eleven_watchers_before_install(self):
        text = (SOURCE / "README.md").read_text()
        self.assertIn("disable --now", text)
        self.assertIn("zero active", text)
        self.assertIn("CC", text)
        self.assertIn("11", text)

    def test_active_or_enabled_seq2_watchers_refuse_an_otherwise_ready_GO(self):
        source, _ = sealed_fixture(self.root)
        launch = types.ModuleType("launch")
        launch.__file__ = str(source / "launch.py")
        exec(compile(recut.rewrite_launch((source / "launch.py").read_text()), launch.__file__, "exec"), launch.__dict__)
        launch.ROOT = source; launch.STATE = self.root / "SYN-state"; launch.STATE.mkdir()
        launch.HOST_STOP = self.root / "alpaca-paper/STOP"
        launch.STOP = launch.HOST_STOP.parent / "lane-b/STOP"
        launch.verify_bundle = launch.verify_runtime = lambda: None
        launch.session_now = lambda: ("RTH", "2026-10-13")
        launch.record_window_drained = lambda date: {}
        (source / "GO-BINDING-REQUEST.json").write_text(json.dumps({
            "bundle_sha256": launch.sha(source / "SHA256SUMS"), "issuer": "CC through co-op",
            "config_hashes": {"sip": launch.sha(source / "configs/sip.json")}}))
        issuer = types.ModuleType("issue_go")
        with patch.dict(sys.modules, {"launch": launch}):
            exec(compile(recut.rewrite_issuer((source / "issue_go.py").read_text()), "SYN-issuer", "exec"), issuer.__dict__)
        issuer.writer_units = lambda: []
        issuer.verify_previous = lambda stage,date: (None, None)
        stages = ("record", "scan", "pre", "pre-skip", "sip", "lev1", "lev2", "lev4", "edge2", "edge8", "iex")
        rows = "\n\n".join("Id=paper-ready-" + s + "-8c95a50d-seq2.path\nLoadState=loaded\nActiveState=active\nUnitFileState=enabled" for s in stages)
        with patch("subprocess.run", return_value=types.SimpleNamespace(returncode=0, stdout=rows)):
            with self.assertRaisesRegex(launch.Refused, "seq2_watchers_not_retired"):
                issuer.build("sip", "syn-ready")


def dry_fixture(root):
    bundle = root / "SYN-bundle"; bundle.mkdir()
    (bundle / "launch.py").write_text("def credential_pointer(): raise AssertionError('real_pointer')\n")
    for name in ("test_wiring", "test_go_issuer", "test_sequencing", "test_unit_contracts", "test_data_wiring"):
        text = "import unittest\nclass SYN(unittest.TestCase):\n    def test_only_SYN(self): self.assertTrue(True)\n"
        if name in ("test_wiring", "test_go_issuer"):
            text += "# self.stop=self.root/'STOP'\n# ('STOP',self.stop)\n"
        if name == "test_wiring":
            text += "    def finish_fixture(self):\n        self.stop.touch()  # Actual native unit's touch, scratch latch only.\n        pass\n"
        (bundle / (name + ".py")).write_text(text)
    sums = "\n".join(hashlib.sha256(p.read_bytes()).hexdigest() + "  " + p.name for p in sorted(bundle.iterdir())) + "\n"
    (bundle / "SHA256SUMS").write_text(sums)
    return bundle


class DryRunBoundaries(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(dir="/var/tmp")
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        self.bundle = dry_fixture(self.root)

    def command(self, receipt):
        # Deliberately no -B: the public runner must enforce its own isolation.
        return subprocess.run([sys.executable, "-E", "-s", str(SOURCE / "dry_run.py"),
            "--bundle", str(self.bundle), "--receipt", str(receipt)], capture_output=True, text=True)

    def test_dry_run_never_adds_bytecode_to_the_bundle(self):
        result = self.command(self.root / "receipt.json")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(list(self.bundle.rglob("__pycache__")), [])

    def test_receipt_inside_bundle_is_refused_before_import(self):
        result = self.command(self.bundle / "receipt.json")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("receipt_inside_bundle", result.stderr)
        self.assertFalse((self.bundle / "receipt.json").exists())

    def test_preexisting_bytecode_cannot_be_read_as_a_runtime_input(self):
        cache = self.bundle / "__pycache__";cache.mkdir()
        (cache / "launch.pyc").write_bytes(b"SYN untrusted cache")
        result = self.command(self.root / "receipt.json")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("bytecode_in_bundle", result.stderr)

    def test_foreign_cached_launcher_cannot_stand_in_for_sealed_bytes(self):
        import dry_run
        foreign = types.ModuleType("launch")
        foreign.__file__ = str(self.root / "OTHER-bundle/launch.py")
        with patch.dict(sys.modules, {"launch": foreign}):
            with self.assertRaisesRegex(ValueError, "foreign_bundle_module"):
                dry_run.run(self.bundle)


if __name__ == "__main__":
    unittest.main()
