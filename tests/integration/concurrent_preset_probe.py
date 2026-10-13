"""Focused native SYN probe regressions; no real STOP, broker or GO access."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
ENGINE = ROOT / "blueprints/us-equities/adaptive-paper"
sys.path.insert(0, str(ENGINE))
PATH = ROOT / "blueprints/us-equities/concurrent-paper-presets/probe.py"
SPEC = importlib.util.spec_from_file_location("concurrent_preset_probe", PATH)
PROBE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROBE)

import runner
import safety
import native_strategy


class ConcurrentProbeIsolation(unittest.TestCase):
    def test_synthetic_canonical_stop_is_isolated_and_restored(self):
        with tempfile.TemporaryDirectory(dir="/var/tmp") as scratch:
            sentinel = Path(scratch) / "SYN-canonical-STOP"
            sentinel.write_text("SYN preserved sentinel\n")
            before = sentinel.stat()
            with patch.object(runner, "DEFAULT_STOP", sentinel), \
                 patch.object(safety, "DEFAULT_STOP", sentinel), \
                 patch.object(native_strategy, "DEFAULT_STOP", sentinel):
                result = PROBE.coupling_probe()
                self.assertEqual(result["submit_refusals_by_preset"],
                                 ["submission_rate_deferred", "submission_rate_deferred"])
                self.assertEqual(runner.DEFAULT_STOP, sentinel)
                self.assertEqual(safety.DEFAULT_STOP, sentinel)
                self.assertEqual(native_strategy.DEFAULT_STOP, sentinel)
            self.assertEqual(sentinel.read_text(), "SYN preserved sentinel\n")
            self.assertEqual((sentinel.stat().st_ino, sentinel.stat().st_mtime_ns),
                             (before.st_ino, before.st_mtime_ns))

    def test_unrelated_refusal_cannot_pass_the_aggregate_gross_probe(self):
        original = safety.Ledger.reserve_intent
        def reserve(ledger, client_id, *args, **kwargs):
            if client_id == "second-buy":
                raise safety.SafetyError("outstanding_order_cap_reached")
            return original(ledger, client_id, *args, **kwargs)
        with patch.object(safety.Ledger, "reserve_intent", reserve):
            with self.assertRaisesRegex(AssertionError, "unexpected_aggregate_gross_refusal"):
                PROBE.ledger_probe()


if __name__ == "__main__":
    unittest.main()
