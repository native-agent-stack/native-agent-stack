"""Native SYN output seam, no broker or credential loader."""
import asyncio
from decimal import Decimal
from pathlib import Path
import sys
import tempfile
import time
import unittest

ENGINE = Path(__file__).resolve().parents[2] / "blueprints/us-equities/adaptive-paper"
sys.path.insert(0, str(ENGINE))
from runner import Controller, load_config, run_native
from safety import Ledger, RiskLimits
from strategies import PolicyConfig
from simulation import SimulatedPort


class PresetOutputNative(unittest.TestCase):
    def test_nonleveraged_native_output_records_deployed_and_broker_equity(self):
        config, _, _ = load_config(ENGINE / "config.json")
        config.update(duration_seconds=2, cleanup_seconds=2, order_timeout_seconds=1)
        with tempfile.TemporaryDirectory(dir="/var/tmp") as scratch:
            ledger = Ledger(Path(scratch) / "journal.db", RiskLimits(trial_seconds=2, cleanup_seconds=2))
            try:
                ledger.start_trial(time.time())
                controller = Controller(ledger, time.time() + 3600, market_open=True,
                                        stop_file=Path(scratch) / "unused-SYN-stop")
                policy = PolicyConfig(symbols=("SPY", "QQQ", "IWM", "DIA", "AAPL", "MSFT"), max_positions=6,
                    warmup_samples=4, warmup_seconds=.06, sample_seconds=.02, rebalance_seconds=.02,
                    min_hold_seconds=.05, max_hold_seconds=.4, cooldown_seconds=.05)
                def price(symbol, tick):
                    slope = Decimal(".03") if symbol in policy.benchmarks else Decimal(".10")
                    return Decimal("100") + min(tick, 70) * slope
                controller.port = SimulatedPort(controller, policy.symbols, price=price)
                result = asyncio.run(run_native(controller, policy, [{"symbol": s} for s in policy.symbols],
                    "preset-summary-SYN", config, "100000", broker_equity_usd="100000"))
                self.assertNotIn("leverage", result)
                self.assertEqual(result["preset_set_version"], "control-v1")
                summary = result["exposure"]
                self.assertEqual(summary["account_equity_usd"], "100000")
                self.assertEqual(summary["equity_basis"], "trial_preflight")
                self.assertEqual(summary["sampling"], "native owner-loop ticks; filled and pending separate")
                self.assertGreater(result["native_fill_events"], 0)
                self.assertGreater(Decimal(summary["peak_filled_gross_usd"]), 0)
                self.assertEqual(Decimal(summary["peak_deployed_to_account_equity"]),
                                 Decimal(summary["peak_filled_gross_usd"]) / Decimal("100000"))
            finally:
                ledger.close()


if __name__ == "__main__":
    unittest.main()
