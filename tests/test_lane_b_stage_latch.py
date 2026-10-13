"""SYN replay of the actual seq2 launcher; keyed commands are tripwired."""
from contextlib import nullcontext
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "blueprints/us-equities/paper-readiness-seq3"
sys.path.insert(0, str(SOURCE))
BASE = (ROOT / "tests/fixtures/seq2-launch.txt").read_text()


def launcher(root):
    try:
        from recut import rewrite_launch
    except ImportError:
        text = BASE
    else:
        text = rewrite_launch(BASE)
    module = types.ModuleType("launch")
    module.__file__ = str(root / "launch.py")
    exec(compile(text, module.__file__, "exec"), module.__dict__)
    module.ROOT = root
    module.STATE = root / "state"
    module.HOST_STOP = root / "alpaca-paper/STOP"
    module.STOP = module.HOST_STOP if text == BASE else root / "alpaca-paper/lane-b/STOP"
    module.HOST_STOP.parent.mkdir(parents=True)
    module.verify_bundle = module.verify_runtime = lambda: None
    module.writer = nullcontext
    module.keyed = lambda *a, **k: (_ for _ in ()).throw(AssertionError("keyed_runtime_not_allowed"))
    module.credential_pointer = lambda: (_ for _ in ()).throw(AssertionError("credential_pointer_not_allowed"))
    for name in ("active", "ready/pre"):
        (module.STATE / name).mkdir(parents=True)
    (root / "configs").mkdir()
    (root / "configs/pre.json").write_text("{}")
    (root / "SHA256SUMS").write_text("SYN bundle\n")
    instance = module.STATE / "instances/syn-trial"
    instance.mkdir(parents=True)
    active = {"trial": "syn-trial", "stage": "pre", "instance": str(instance),
              "session_date": "2026-10-13", "config_sha256": module.sha(module.config("pre")),
              "bundle_sha256": module.sha(root / "SHA256SUMS"), "go_sha256": "a" * 64}
    module.save(module.STATE / "active/pre.json", active)
    def recover(stage, active):
        out = instance / "recover.json"
        module.save(out, {"status": "passed", "flat": True, "positions": [], "unresolved_orders": [],
                          "reconciliation": {"positions": 0, "open_orders": 0}})
        return 0, out
    module.native_recover = recover
    return module, instance


class StageLatch(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(dir="/var/tmp")
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        self.launch, self.instance = launcher(self.root)

    def test_stage_end_never_creates_a_host_stop(self):
        self.launch.stop_mark("pre")
        self.assertFalse(self.launch.HOST_STOP.exists())
        self.assertTrue((self.root / "alpaca-paper/lane-b/STOP").exists())
        self.launch.recover_stage("pre")
        self.assertFalse(self.launch.HOST_STOP.exists())
        self.assertFalse(self.launch.STOP.exists())

    def test_operator_host_stop_blocks_lane_b_and_is_untouched_by_recover(self):
        host = self.launch.HOST_STOP
        host.write_text("SYN operator abort\n")
        before = host.stat()
        with self.assertRaisesRegex(self.launch.Refused, "stop_present"):
            self.launch.skip_available("2026-10-13")
        self.launch.stop_mark("pre")
        self.launch.recover_stage("pre")
        self.assertEqual(host.read_text(), "SYN operator abort\n")
        self.assertEqual((host.stat().st_ino, host.stat().st_mtime_ns), (before.st_ino, before.st_mtime_ns))

    def test_retried_hook_retains_ownership_and_clears_its_lane_stop(self):
        self.launch.stop_mark("pre")
        first = (self.instance / "stop-hook.json").read_bytes()
        self.launch.stop_mark("pre")
        self.assertEqual((self.instance / "stop-hook.json").read_bytes(), first)
        self.launch.recover_stage("pre")
        self.assertFalse(self.launch.STOP.exists())

    def test_human_lane_stop_is_never_claimed_or_cleared(self):
        lane = self.root / "alpaca-paper/lane-b/STOP"
        lane.parent.mkdir(parents=True)
        lane.write_text("SYN human lane abort\n")
        self.launch.stop_mark("pre")
        self.launch.recover_stage("pre")
        self.assertEqual(lane.read_text(), "SYN human lane abort\n")

    def test_replaced_owned_latch_is_not_cleared(self):
        self.launch.stop_mark("pre")
        lane = self.launch.STOP
        replacement = lane.with_name("SYN-replacement")
        replacement.write_text("SYN human replacement\n")
        replacement.replace(lane)
        self.launch.recover_stage("pre")
        self.assertEqual(lane.read_text(), "SYN human replacement\n")

    def test_modified_owned_latch_is_not_cleared(self):
        self.launch.stop_mark("pre")
        self.launch.STOP.write_text("SYN human modification\n")
        self.launch.recover_stage("pre")
        self.assertTrue(self.launch.STOP.exists())

    def test_failed_recover_preserves_owned_lane_latch(self):
        self.launch.stop_mark("pre")
        def failed(stage, active):
            out = self.instance / "recover.json"
            self.launch.save(out, {"status": "failed", "flat": False, "reconciliation": {"positions": 1, "open_orders": 1}})
            return 3, out
        self.launch.native_recover = failed
        with self.assertRaisesRegex(self.launch.Refused, "recovery_not_flat"):
            self.launch.recover_stage("pre")
        self.assertTrue(self.launch.STOP.exists())

    def test_GO_admission_and_issuer_refuse_both_lane_and_host_latches(self):
        from recut import rewrite_issuer
        raw = (ROOT / "tests/fixtures/seq2-issue-go.txt").read_text()
        issuer = types.ModuleType("issue_go")
        with patch.dict(sys.modules, {"launch": self.launch}):
            exec(compile(rewrite_issuer(raw), "SYN-issue-go", "exec"), issuer.__dict__)
        self.launch.session_now = lambda: ("RTH", "2026-10-13")
        issuer.writer_units = lambda: []
        (self.launch.STATE / "active/pre.json").unlink()
        (self.root / "configs/sip.json").write_text("{}")
        self.launch.save(self.root / "GO-BINDING-REQUEST.json", {
            "bundle_sha256": self.launch.sha(self.root / "SHA256SUMS"), "issuer": "CC through co-op",
            "config_hashes": {"sip": self.launch.sha(self.root / "configs/sip.json")}})
        for stop in (self.launch.HOST_STOP, self.launch.STOP):
            with self.subTest(scope=stop.parent.name):
                stop.parent.mkdir(exist_ok=True)
                stop.touch()
                with self.assertRaisesRegex(self.launch.Refused, "STOP_present"):
                    issuer.build("sip", "syn-next")
                stop.unlink()

    def test_unit_rewrite_removes_host_touch_instead_of_retargeting_it(self):
        from recut import rewrite_unit
        old = "ExecStart=/SYN/old/launch.py run sip\nExecStopPost=/SYN/old/launch.py stop-mark sip\n" \
              "ExecStopPost=/usr/bin/bash -c 'if test -f /SYN/active; then /usr/bin/touch --no-dereference /SYN/alpaca-paper/STOP; fi'\n" \
              "ExecStopPost=/SYN/old/launch.py recover sip\n"
        new, count = rewrite_unit(old, Path("/SYN/old"), Path("/SYN/new"))
        self.assertEqual(count, 1)
        self.assertNotIn("touch", new)
        self.assertNotIn("alpaca-paper/STOP", new)
        self.assertIn("/SYN/new/launch.py stop-mark sip", new)

    def test_symlink_lane_stop_is_never_cleared_or_followed(self):
        target = self.root / "SYN-human-target"
        target.write_text("SYN preserved\n")
        self.launch.STOP.parent.mkdir(exist_ok=True)
        self.launch.STOP.symlink_to(target)
        self.launch.stop_mark("pre")
        self.launch.recover_stage("pre")
        self.assertTrue(self.launch.STOP.is_symlink())
        self.assertEqual(target.read_text(), "SYN preserved\n")


if __name__ == "__main__":
    unittest.main()
