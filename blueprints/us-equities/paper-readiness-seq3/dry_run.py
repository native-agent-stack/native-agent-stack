"""Replay the predecessor's complete SYN wiring against an uninstalled seq3.

Test source remains immutable. Only fixture latch paths and the now-two-hook
unit expectation adapt in memory. The real credential pointer is never called.
"""
import argparse
import contextlib
import hashlib
import importlib
import io
import json
from pathlib import Path
import subprocess
import sys
import types
import unittest


def run(bundle):
    bundle = Path(bundle).resolve()
    strict = subprocess.run(["sha256sum", "--check", "--strict", "--quiet", "SHA256SUMS"], cwd=bundle)
    if strict.returncode:
        raise ValueError("strict_manifest_refused")
    sys.path.insert(0, str(bundle))
    launch = importlib.import_module("launch")
    pointer_calls = []
    def fixture_pointer():
        pointer_calls.append("SYN-placeholder")
        return Path("/SYN/never-opened-paper.env")
    launch.credential_pointer = fixture_pointer
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
        "status": "passed" if result.wasSuccessful() else "failed", "cases": result.testsRun,
        "failures": len(result.failures), "errors": len(result.errors), "skips": len(result.skipped),
        "fixture_adaptations": adaptations, "credential_pointer": "real implementation replaced before tests",
        "placeholder_calls": len(pointer_calls), "services_started": 0, "broker_execution": "NOT_RUN"}
    if not result.wasSuccessful():
        # SYN traceback only; no credential pointer/broker call is reachable.
        print(log.getvalue(), file=sys.stderr)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    receipt = run(args.bundle)
    args.receipt.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))
    return 0 if receipt["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
