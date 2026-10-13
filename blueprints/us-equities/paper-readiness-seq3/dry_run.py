"""Replay the predecessor's complete SYN wiring against an uninstalled seq3.

Test source remains immutable. Only fixture latch paths and the now-two-hook
unit expectation adapt in memory. The real credential pointer is never called.
"""
import sys
sys.dont_write_bytecode = True
import argparse
import contextlib
import hashlib
import importlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import types
import unittest
from unittest.mock import patch


def run(bundle):
    sys.dont_write_bytecode = True
    bundle = Path(bundle).resolve()
    if any(p.name == "__pycache__" or p.suffix in (".pyc", ".pyo") for p in bundle.rglob("*")):
        raise ValueError("bytecode_in_bundle")
    strict = subprocess.run(["sha256sum", "--check", "--strict", "--quiet", "SHA256SUMS"], cwd=bundle)
    if strict.returncode:
        raise ValueError("strict_manifest_refused")
    inventoried = {line.split("  ", 1)[1] for line in (bundle / "SHA256SUMS").read_text().splitlines()}
    required = {name + ".py" for name in ("test_wiring", "test_go_issuer", "test_sequencing", "test_unit_contracts", "test_data_wiring")}
    if not required <= inventoried:
        raise ValueError("replay_sources_not_in_manifest")
    for name in ("launch", "lane_latch", "seq2_retirement", "issue_go", "launch_data", "data_worker"):
        existing = sys.modules.get(name)
        if existing is not None and (not getattr(existing, "__file__", None)
                or Path(existing.__file__).resolve() != bundle / (name + ".py")):
            raise ValueError("foreign_bundle_module")
    sys.path.insert(0, str(bundle))
    launch = importlib.import_module("launch")
    # Operational retirement is checked live by the issuer; this replay uses
    # SYN unit state and makes no user-manager mutation or production claim.
    launch.assert_seq2_watchers_retired = lambda: []
    pointer_calls = []
    def fixture_pointer():
        pointer_calls.append("SYN-placeholder")
        return Path("/SYN/never-opened-paper.env")
    launch.credential_pointer = fixture_pointer
    attempts = {"keyed": 0, "subprocess": 0, "verification_processes_started": 0}
    real_run, real_popen = subprocess.run, subprocess.Popen
    def manifest_check(command, kwargs):
        # Retain the launcher's real bundle-tamper check in SYN roots.
        # This sole process exception is keyless and cannot run a broker,
        # credential loader or systemd command. Its inventory must stay
        # inside its scratch cwd; absolute/escaping/symlink inputs refuse.
        if command != ['/usr/bin/sha256sum', '--strict', '--quiet', '-c', 'SHA256SUMS']:
            return False
        if kwargs.get('shell') or any(k in kwargs for k in ('executable', 'preexec_fn', 'env')):
            return False
        root = Path(kwargs.get('cwd', '/')).resolve()
        if not root.is_relative_to(Path(tempfile.gettempdir()).resolve()):
            return False
        manifest = root / 'SHA256SUMS'
        if manifest.is_symlink() or not manifest.is_file():
            return False
        for row in manifest.read_text().splitlines():
            if '  ' not in row:
                return False
            name = Path(row.split('  ', 1)[1])
            target = root / name
            if name.is_absolute() or '..' in name.parts or target.is_symlink() or not target.resolve().is_relative_to(root):
                return False
        return True
    def blocked_keyed(*args, **kwargs):
        attempts["keyed"] += 1
        raise AssertionError("dry_run_keyed_forbidden")
    def blocked_process(command, *args, **kwargs):
        if manifest_check(command, kwargs):
            return real_run(command, *args, **kwargs)
        attempts["subprocess"] += 1
        raise AssertionError("dry_run_subprocess_forbidden")
    def blocked_popen(command, *args, **kwargs):
        if manifest_check(command, kwargs):
            process = real_popen(command, *args, **kwargs)
            attempts['verification_processes_started'] += 1
            return process
        attempts['subprocess'] += 1
        raise AssertionError('dry_run_subprocess_forbidden')
    # Bound replay source can still contain a missed stub. Never let that
    # omission reach the credential runner or an external process. Install
    # before executing replay-module imports, and restore on every exit.
    with patch.object(launch, "keyed", blocked_keyed, create=True), \
         patch.object(subprocess, "run", blocked_process), \
         patch.object(subprocess, "Popen", blocked_popen):
        return replay(bundle, launch, pointer_calls, attempts)


def replay(bundle, launch, pointer_calls, attempts):
    modules = []
    adaptations = []
    for name in ("test_wiring", "test_go_issuer", "test_sequencing", "test_unit_contracts", "test_data_wiring"):
        path = bundle / (name + ".py")
        text = path.read_text()
        if name in ("test_wiring", "test_go_issuer"):
            old = "self.stop=self.root/'STOP'"
            if text.count(old) != 1 or text.count("('STOP',self.stop)") != 1:
                raise ValueError("unexpected_SYN_latch_fixture_shape")
            text = text.replace(old, "self.stop=self.root/'lane-b/STOP';self.stop.parent.mkdir()")
            text = text.replace("('STOP',self.stop)", "('STOP',self.stop),('HOST_STOP',self.root/'STOP')")
            if name == "test_wiring":
                # finish() explicitly simulated the deleted shell touch hook.
                old_touch = "        self.stop.touch()  # Actual native unit's touch, scratch latch only.\n"
                if text.count(old_touch) != 1:
                    raise ValueError("unexpected_SYN_stop_touch_fixture_shape")
                text = text.replace(old_touch, "")
            adaptations.append(name + ": SYN host/lane roots")
        if name == "test_unit_contracts":
            text = text.replace("-seq2", "-seq3")
            text = text.replace("self.assertEqual(len(hooks),3)", "self.assertEqual(len(hooks),2)")
            text = text.replace("self.assertIn('touch --no-dereference',hooks[1])",
                                "self.assertNotIn('touch','\\n'.join(hooks))")
            text = text.replace("hooks[2].endswith", "hooks[1].endswith")
            adaptations.append(name + ": seq3 names and two hooks/no touch")
        if name in ("test_wiring", "test_sequencing"):
            method = ("test_nonflat_recovery_does_not_clear_stop_or_publish_completed"
                      if name == "test_wiring" else "test_failed_pre_recover_cannot_be_skipped_or_start_sip")
            start = text.index("    def " + method)
            end = text.find("\n    def ", start + 1)
            end = len(text) if end < 0 else end
            body = text[start:end]
            if body.count("self.assertTrue(self.stop.exists())") != 1:
                raise ValueError("private_marker_replay_assertion_shape")
            body = body.replace("self.assertTrue(self.stop.exists())",
                                "self.assertTrue((self.state/'instances/fixture-pre/.stage-hook-latch').exists())")
            text = text[:start] + body + text[end:]
            adaptations.append(name + ": failed recovery retains private marker; human actions unchanged")
        module = types.ModuleType(name)
        module.__file__ = str(path)
        sys.modules[name] = module
        exec(compile(text, str(path), "exec"), module.__dict__)
        modules.append(module)
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromModule(m) for m in modules)
    log = io.StringIO()
    with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
        result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
    receipt = {"schema_version": 1, "paper_lane": "B", "evidence_class": "synthetic",
        "deployment_version": "readiness-sequencing-v3-lane-latch",
        "bundle_sha256": hashlib.sha256((bundle / "SHA256SUMS").read_bytes()).hexdigest(),
        "status": "passed" if result.wasSuccessful() and not (attempts['keyed'] or attempts['subprocess']) else "failed", "cases": result.testsRun,
        "failures": len(result.failures), "errors": len(result.errors), "skips": len(result.skipped),
        "fixture_adaptations": adaptations, "credential_pointer": "real implementation replaced before tests",
        "seq2_retirement": "SYN fixture only; live retirement proof required before installation",
        "placeholder_calls": len(pointer_calls), "keyed_tripwire_hits": attempts["keyed"],
        "subprocess_tripwire_hits": attempts["subprocess"],
        "verification_processes_started": attempts['verification_processes_started'],
        "execution_boundary": "keyed and subprocess run/Popen guarded before replay imports; only scratch-contained sha256sum checks may execute; any tripwire hit fails the drill",
        "services_started": 0, "broker_execution": "NOT_RUN"}
    if receipt["status"] != "passed":
        # SYN traceback only; no credential pointer/broker call is reachable.
        print(log.getvalue(), file=sys.stderr)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    if args.receipt.resolve().is_relative_to(args.bundle.resolve()):
        raise ValueError("receipt_inside_bundle")
    receipt = run(args.bundle)
    args.receipt.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))
    return 0 if receipt["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
