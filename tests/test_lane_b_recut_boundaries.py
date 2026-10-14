"""SYN public re-cut/dry-run regression boundaries, never host unit mutations."""
import hashlib
import ast
import inspect
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
    for name in ("test_wiring.py", "test_go_issuer.py", "test_sequencing.py", "test_data_wiring.py"):
        (source / name).write_text("# SYN replay source\n")
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
        if "predecessor_sha256" in inspect.signature(recut.recut).parameters:
            return recut.recut(source, output, "SYN-fix-pin", predecessor_sha256=pin)
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

    def test_source_bytes_changed_after_the_checks_are_refused(self):
        # Adopt trading-cc's validated reproduction: the old source check
        # does not authenticate bytes read later by copytree.
        source, pin = sealed_fixture(self.root)
        real_copytree, fired = shutil.copytree, []
        def change_then_copy(src, dst, *args, **kwargs):
            if not fired and Path(src) == source.resolve():
                fired.append(1)
                (source / "frozen/native.txt").write_text("SYN bytes changed after the checks\n")
            return real_copytree(src, dst, *args, **kwargs)
        output = self.root / "SYN-window"
        with patch.object(recut.shutil, "copytree", side_effect=change_then_copy):
            with self.assertRaisesRegex(ValueError, "copied_bytes_not_in_sealed_inventory"):
                self.build(source, pin, output)
        self.assertTrue(fired)
        if output.exists():
            self.assertFalse((output / "RECUT-RECEIPT.json").exists())

    def test_uninventoried_replay_source_is_refused_before_a_new_seal(self):
        source, _ = sealed_fixture(self.root)
        inventory = source / "SHA256SUMS"
        inventory.write_text("\n".join(row for row in inventory.read_text().splitlines()
            if not row.endswith("  test_data_wiring.py")) + "\n")
        # The remaining inventory is valid, but this unbound replay was replaced.
        (source / "test_data_wiring.py").write_text("")
        pin = hashlib.sha256(inventory.read_bytes()).hexdigest()
        output = self.root / "SYN-missing-replay-binding"
        with self.assertRaisesRegex(ValueError, "predecessor_replay_source_not_in_manifest"):
            self.build(source, pin, output)
        self.assertFalse((output / "RECUT-RECEIPT.json").exists())

    def test_recutter_stdout_omits_the_private_predecessor_digest(self):
        source, pin = sealed_fixture(self.root)
        output = self.root / "SYN-new"
        result = subprocess.run([sys.executable, "-E", "-s", "-B", str(SOURCE / "recut.py"),
            "--source", str(source), "--output", str(output), "--source-commit", "SYN-fix-pin",
            "--predecessor-sha256", pin], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(pin, result.stdout)
        self.assertNotIn("predecessor_bundle_sha256", json.loads(result.stdout))
        private = json.loads((output / "RECUT-RECEIPT.json").read_text())
        self.assertEqual(private["predecessor_bundle_sha256"], pin)

    def test_runbook_names_systemd_259_and_the_33_case_review_baseline(self):
        text = (SOURCE / "README.md").read_text()
        self.assertIn("systemd 259", text)
        self.assertNotIn("Systemd v260", text)
        self.assertIn("33", text)
        self.assertNotIn("eleven now pass", text)

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

    def test_predecessor_digest_is_required_from_the_private_binding_input(self):
        source, pin = sealed_fixture(self.root)
        with patch.object(recut, "PREDECESSOR", pin, create=True):
            with self.assertRaisesRegex(ValueError, "predecessor_digest_required"):
                recut.recut(source, self.root / "SYN-no-authority", "SYN-fix-pin")

    def test_public_recutter_has_no_private_bundle_digest_constant(self):
        self.assertFalse(hasattr(recut, "PREDECESSOR"))

    def test_public_python_and_text_digest_literals_resolve_to_published_bytes(self):
        import re
        paths = list(SOURCE.glob("*.py")) + [ROOT / "tests/fixtures/seq2-launch.txt", ROOT / "tests/fixtures/seq2-issue-go.txt"]
        published = {hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
        for path in paths:
            for node in ast.walk(ast.parse(path.read_text())):
                if isinstance(node, ast.Constant) and isinstance(node.value, str) and re.fullmatch("[0-9a-f]{64}", node.value):
                    self.assertIn(node.value, published, path.name)

    def test_active_or_enabled_seq2_watchers_refuse_an_otherwise_ready_GO(self):
        source, _ = sealed_fixture(self.root)
        launch = types.ModuleType("launch")
        launch.__file__ = str(source / "launch.py")
        text = (source / "launch.py").read_text()
        if "predecessor_sha256" in inspect.signature(recut.rewrite_launch).parameters:
            text = recut.rewrite_launch(text, hashlib.sha256(b"SYN predecessor manifest").hexdigest(),
                                      hashlib.sha256(text.encode()).hexdigest())
        else:
            text = recut.rewrite_launch(text)
        exec(compile(text, launch.__file__, "exec"), launch.__dict__)
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
        if name in ("test_wiring", "test_sequencing"):
            method = ("test_nonflat_recovery_does_not_clear_stop_or_publish_completed" if name == "test_wiring"
                      else "test_failed_pre_recover_cannot_be_skipped_or_start_sip")
            text += "    def " + method + "(self):\n        # self.assertTrue(self.stop.exists())\n        pass\n"
        if name == "test_unit_contracts":
            # The keyless CLI fixture models the real sealed drill's 49-case
            # minimum (7 fixture cases plus 42 clearly synthetic cases).
            text += "".join("    def test_SYN_count_fixture_" + str(i) + "(self): self.assertTrue(True)\n"
                            for i in range(42))
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

    def command(self, receipt, *, env=None):
        # Deliberately no -B: the public runner must enforce its own isolation.
        return subprocess.run([sys.executable, "-E", "-s", str(SOURCE / "dry_run.py"),
            "--bundle", str(self.bundle), "--receipt", str(receipt)], capture_output=True, text=True, env=env)

    def test_empty_but_inventoried_replay_cannot_pass_with_fewer_cases(self):
        (self.bundle / "test_data_wiring.py").write_text("")
        self.add_replay_case("")  # Re-seal the SYN fixture, keeping the empty module inventoried.
        result = self.command(self.root / "receipt.json")
        self.assertEqual(result.returncode, 1, result.stderr)
        receipt = json.loads(result.stdout)
        self.assertEqual(receipt["cases"], 48)
        self.assertEqual(receipt["minimum_expected_cases"], 49)
        self.assertEqual(receipt["reason"], "replay_case_count_below_expected")
        self.assertEqual(receipt["status"], "failed")

    def test_keyless_scratch_manifest_check_with_TMPDIR_unset(self):
        self.add_replay_case("""
    def test_TMPDIR_unset_manifest_probe(self):
        import launch,subprocess
        from pathlib import Path
        result=subprocess.run(['/usr/bin/sha256sum','--strict','--quiet','-c','SHA256SUMS'],
                              cwd=Path(launch.__file__).parent,capture_output=True,text=True)
        self.assertEqual(result.returncode,0)
""")
        env = {k:v for k,v in os.environ.items() if k not in ("TMPDIR", "TMP", "TEMP")}
        result = self.command(self.root / "receipt.json", env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = json.loads(result.stdout)
        self.assertEqual(receipt["verification_processes_started"], 1)
        self.assertEqual(receipt["subprocess_tripwire_hits"], 0)

    def add_replay_case(self, text):
        target = self.bundle / "test_data_wiring.py"
        target.write_text(target.read_text() + text)
        sums = "\n".join(hashlib.sha256(p.read_bytes()).hexdigest() + "  " + p.name
            for p in sorted(self.bundle.iterdir()) if p.name != "SHA256SUMS") + "\n"
        (self.bundle / "SHA256SUMS").write_text(sums)

    def test_keyless_replay_reports_measured_tripwire_counts(self):
        result = self.command(self.root / "receipt.json")
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = json.loads(result.stdout)
        self.assertEqual(receipt["keyed_tripwire_hits"], 0)
        self.assertEqual(receipt["subprocess_tripwire_hits"], 0)
        self.assertEqual(receipt["broker_execution"], "NOT_RUN")

    def test_unstubbed_keyed_call_is_blocked_and_invalidates_even_a_passing_test(self):
        self.add_replay_case("""
    def test_unstubbed_keyed_probe(self):
        import launch
        with self.assertRaisesRegex(AssertionError,'dry_run_keyed_forbidden'):
            launch.keyed([],timeout=1)
""")
        result = self.command(self.root / "receipt.json")
        self.assertEqual(result.returncode, 1, result.stderr)
        receipt = json.loads(result.stdout)
        self.assertEqual(receipt["keyed_tripwire_hits"], 1)
        self.assertEqual(receipt["status"], "failed")
        self.assertEqual(receipt["errors"], 0)
        self.assertEqual(receipt["failures"], 0)

    def test_replay_cannot_spawn_an_external_process(self):
        self.add_replay_case("""
    def test_external_process_probe(self):
        import subprocess
        with self.assertRaisesRegex(AssertionError,'dry_run_subprocess_forbidden'):
            subprocess.run(['SYN-must-not-spawn'])
""")
        result = self.command(self.root / "receipt.json")
        self.assertEqual(result.returncode, 1, result.stderr)
        receipt = json.loads(result.stdout)
        self.assertEqual(receipt["subprocess_tripwire_hits"], 1)
        self.assertEqual(receipt["services_started"], 0)
        self.assertEqual(receipt["errors"], 0)
        self.assertEqual(receipt["failures"], 0)

    def test_replay_measures_only_keyless_scratch_manifest_processes(self):
        self.add_replay_case("""
    def test_manifest_process_probe(self):
        import launch,subprocess
        from pathlib import Path
        result=subprocess.run(['/usr/bin/sha256sum','--strict','--quiet','-c','SHA256SUMS'],
                              cwd=Path(launch.__file__).parent,capture_output=True,text=True)
        self.assertEqual(result.returncode,0)
""")
        result = self.command(self.root / "receipt.json")
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = json.loads(result.stdout)
        self.assertEqual(receipt["verification_processes_started"], 1)
        self.assertEqual(receipt["subprocess_tripwire_hits"], 0)
        self.assertEqual(receipt["services_started"], 0)

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

    def test_uninventoried_replay_module_cannot_reduce_the_checks_and_still_pass(self):
        sums = (self.bundle / "SHA256SUMS").read_text()
        (self.bundle / "SHA256SUMS").write_text("\n".join(line for line in sums.splitlines()
            if not line.endswith("  test_data_wiring.py")) + "\n")
        (self.bundle / "test_data_wiring.py").write_text("")
        result = self.command(self.root / "receipt.json")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("replay_sources_not_in_manifest", result.stderr)


if __name__ == "__main__":
    unittest.main()
