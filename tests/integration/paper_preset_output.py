"""Native SYN output seam, no broker or credential loader."""
import asyncio
import json
import stat
from decimal import Decimal
from dataclasses import replace
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ENGINE = Path(__file__).resolve().parents[2] / "blueprints/us-equities/adaptive-paper"
sys.path.insert(0, str(ENGINE))
import runner
from runner import Controller, load_config, run_native
from safety import Ledger, Quote, RiskLimits, SafetyError
from strategies import PolicyConfig
from simulation import SimulatedPort
from tests.adaptive_paper_hermetic import patch_default_stop, restore_default_stop, real_tmp_root

_STOP_TOKEN = None


def setUpModule():
    global _STOP_TOKEN
    _STOP_TOKEN = patch_default_stop()


def tearDownModule():
    restore_default_stop(_STOP_TOKEN)


class PresetOutputNative(unittest.TestCase):
    def test_native_admission_uses_registered_ceiling_above_old_share_and_dollar_caps(self):
        with tempfile.TemporaryDirectory(dir="/var/tmp") as root:
            root = real_tmp_root(root)
            config = json.loads((ENGINE / "config-sip.json").read_text())
            config.update(capital_usd="200000", max_gross_exposure_usd="100000",
                max_order_notional_usd="20000", max_order_quantity=1000000000,
                max_order_qty_mode="notional", risk_ceilings={"capital_usd": "1000000",
                    "max_order_notional_usd": "20000", "max_order_quantity": 1000000000})
            path = root / "config.json"
            path.write_text(json.dumps(config))
            _, limits, policy = load_config(path)
            self.assertEqual(policy.max_shares_ceiling, 1000000000)
            ledger = Ledger(root / "journal.db", limits)
            now = time.time()
            try:
                ledger.start_trial(now)
                controller = Controller(ledger, now+3600, market_open=True, clock=lambda: now,
                                        stop_file=root / "unused-SYN-stop")
                controller.port = type("Port", (), {"ready": True})()
                controller.quote({"symbol": "SPY", "bid": "99.99", "ask": "100", "ts_ns": int(now * 1e9)})
                controller.before_submit({"client_order_id": "SYN-acct-sized", "symbol": "SPY", "side": "buy",
                    "qty": "200", "limit_price": "100", "strategy": "SYN-v1"})
                self.assertEqual(ledger.intents()[0].qty, Decimal("200"))
                self.assertEqual(controller.private_order_sizing[-1]["code_binding_ceilings"],
                                 ["order_notional_ceiling"])
            finally:
                ledger.close()

    def test_unbound_preset_and_invalid_pass_equity_refuse_before_native_start(self):
        for kwargs, reason in (({"preset_set_version": "unknown"}, "unknown_preset_set"),
                ({"preset_set_version": "acct-sized-v1"}, "acct_sized_pass_context_required"),
                ({"broker_equity_usd": "0"}, "positive_broker_equity_required"),
                ({"broker_equity_usd": "NaN"}, "positive_broker_equity_required")):
            with self.subTest(kwargs=kwargs), self.assertRaisesRegex(ValueError, reason):
                asyncio.run(run_native(None, None, [], "SYN", {}, "0", **kwargs))

    def test_one_way_loss_cannot_be_relabelled_as_a_control_pass(self):
        # Known activation blocker: even with unchanged capital, lifetime
        # loss above CONTROL's cap prevents returning from a larger arm.
        # The reviewed rebasing mechanism must solve this without a reset.
        with tempfile.TemporaryDirectory(dir="/var/tmp") as root:
            now = time.time()
            larger = RiskLimits(max_gross_loss_usd=Decimal("100"), max_drawdown_usd=Decimal("100"))
            control = replace(larger, max_gross_loss_usd=Decimal("25"), max_drawdown_usd=Decimal("25"))
            ledger = Ledger(Path(root) / "journal.db", larger, exploratory=True)
            try:
                ledger.begin_next_trial(now, "larger", config_sha256="a" * 64, limits=larger)
                quote = Quote("SPY", "99.99", "100", now)
                ledger.reserve_intent("SYN-buy", "SPY", "buy", "1", "100", quote=quote,
                    now=now, market_open=True, session_close=now+3600, stop_file=Path(root)/"STOP")
                ledger.record_order("SYN-buy", "SYN-buy", "filled", "1", "100")
                quote = Quote("SPY", "60", "60.01", now)
                ledger.reserve_intent("SYN-sell", "SPY", "sell", "1", "60", quote=quote,
                    now=now, market_open=True, session_close=now+3600, stop_file=Path(root)/"STOP")
                ledger.record_order("SYN-sell", "SYN-sell", "filled", "1", "60")
                before = ledger.accounting()
                self.assertEqual(before.gross_loss_usd, Decimal("40"))
                with self.assertRaisesRegex(SafetyError, "next_trial_risk_budget_exhausted"):
                    ledger.begin_next_trial(now+1, "control", config_sha256="b" * 64, limits=control)
                self.assertEqual(ledger.accounting(), before)
                self.assertEqual(ledger.exploratory_config_history(), ["a" * 64])
            finally:
                ledger.close()

    def test_unlabelled_native_run_is_not_control_and_public_output_is_ratios_only(self):
        config, _, _ = load_config(ENGINE / "config.json")
        config.update(capital_usd="50000", duration_seconds=2, cleanup_seconds=2, order_timeout_seconds=1)
        with tempfile.TemporaryDirectory(dir="/var/tmp") as scratch:
            ledger = Ledger(Path(scratch) / "journal.db", RiskLimits(capital_usd=Decimal("50000"),
                trial_seconds=2, cleanup_seconds=2))
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
                self.assertIsNone(result["preset_set_version"])
                summary = result["exposure"]
                self.assertEqual(summary["account_equity_usd"], "100000")
                self.assertEqual(summary["equity_basis"], "trial_preflight")
                self.assertEqual(summary["sampling"], "native owner-loop ticks; filled and pending separate")
                self.assertGreater(result["native_fill_events"], 0)
                self.assertGreater(Decimal(summary["peak_filled_gross_usd"]), 0)
                self.assertEqual(Decimal(summary["peak_deployed_to_account_equity"]),
                                 Decimal(summary["peak_filled_gross_usd"]) / Decimal("100000"))
                output = Path(scratch) / "public/paper-output.json"
                runner.publish_paper_output(Path(scratch) / "journal.db", output, result, "SYN-trial")
                public = json.loads(output.read_text())
                self.assertEqual(set(public["exposure"]), {"equity_basis", "sampling",
                    "peak_deployed_to_account_equity", "peak_pending_to_account_equity"})
                self.assertNotIn("accounting", public)
                self.assertNotIn("execution_stats", public)
                self.assertNotIn("account_equity_usd", public["exposure"])
                self.assertNotIn("peak_filled_gross_usd", public["exposure"])
                self.assertNotIn("100000", output.read_text())
                sidecars = list(Path(scratch).glob("paper-output-*.private.json"))
                self.assertEqual(len(sidecars), 1)
                self.assertEqual(stat.S_IMODE(sidecars[0].stat().st_mode), 0o600)
                private = json.loads(sidecars[0].read_text())
                self.assertEqual(private["exposure"]["account_equity_usd"], "100000")
                intents = [e for e in private["events"] if e["type"] == "intent"]
                self.assertTrue(intents)
                for event in intents:
                    self.assertIsNone(event["preset_set_version"])
                    self.assertIn("configured_order_quantity", event["sizing"]["binding_ceilings"])
                    self.assertNotIn("submitted_notional_usd", event["sizing"])
                self.assertTrue(private["private_order_sizing"])
                self.assertEqual(private["private_order_sizing"][0]["definition"],
                                 "next whole share at submitted limit price")
            finally:
                ledger.close()

    def test_public_projection_does_not_reconstruct_equity_from_other_dollars(self):
        private = {"status": "passed", "flat": True, "preset_set_version": "acct-sized-v1",
            "pass_id": "pass-2", "accounting": {"gross_exposure_usd": "5000"},
            "preflight": {"account": {"equity": "100000"}},
            "execution_stats": {"fills": [{"qty": "50", "price": "100"}]},
            "events": [{"type": "intent", "sizing": {"submitted_notional_usd": "5000",
                        "binding_ceilings": ["configured_order_quantity"]}}],
            "exposure": {"account_equity_usd": "100000", "peak_filled_gross_usd": "5000",
                "peak_deployed_to_account_equity": "0.05", "peak_pending_to_account_equity": "0"},
            "leverage": {"peak_gross_exposure_usd": "5000", "broker_cash_at_start": "100000",
                "peak_achieved_leverage": "0.05", "peak_effective_leverage": "0.1"}}
        public = runner.public_paper_output(private)
        self.assertEqual(public["exposure"]["peak_deployed_to_account_equity"], "0.05")
        # Trial-capital ratios can recover gross dollars using the public
        # CONTROL config, then recover account equity from the new ratio.
        self.assertNotIn("peak_achieved_leverage", public["leverage"])
        self.assertNotIn("peak_effective_leverage", public["leverage"])
        raw = json.dumps(public)
        for forbidden in ("5000", "100000", "submitted_notional", "qty", "price", "accounting", "preflight"):
            self.assertNotIn(forbidden, raw)
        self.assertEqual(public["order_ceiling_events"][0]["binding_ceilings"], ["configured_order_quantity"])

    def test_private_publication_refuses_journal_inside_repository_before_writing(self):
        with tempfile.TemporaryDirectory(dir="/var/tmp") as root:
            output = Path(root) / "public.json"
            with self.assertRaisesRegex(ValueError, "private_journal_outside_repository_required"):
                runner.publish_paper_output(ENGINE / "SYN-never-written.db", output,
                                            {"status": "passed"}, "SYN-test")
            self.assertFalse(output.exists())

    def test_publication_keeps_evidence_private_if_sidecar_write_fails(self):
        with tempfile.TemporaryDirectory(dir="/var/tmp") as root:
            output = Path(root) / "public.json"
            output.write_text("previous-public-receipt")
            with patch.object(runner, "save", side_effect=OSError("SYN disk refusal")) as writer:
                with self.assertRaises(OSError):
                    runner.publish_paper_output(Path(root) / "journal.db", output,
                                                {"status": "passed"}, "SYN-test")
            self.assertEqual(writer.call_count, 1)
            self.assertEqual(output.read_text(), "previous-public-receipt")

    def test_module_stop_is_hermetic_and_restored(self):
        import safety
        before = runner.DEFAULT_STOP
        with tempfile.TemporaryDirectory(dir="/var/tmp") as root:
            operator = real_tmp_root(root) / "STOP"
            operator.write_text("SYN operator stop must be preserved")
            with patch.object(runner, "DEFAULT_STOP", operator), patch.object(safety, "DEFAULT_STOP", operator):
                token = patch_default_stop()
                try:
                    self.assertFalse(runner.DEFAULT_STOP.exists())
                    self.assertNotEqual(runner.DEFAULT_STOP, operator)
                finally:
                    restore_default_stop(token)
                self.assertEqual(runner.DEFAULT_STOP, operator)
                self.assertEqual(operator.read_text(), "SYN operator stop must be preserved")
        self.assertEqual(runner.DEFAULT_STOP, before)

    def test_intent_receipt_names_code_quantity_and_notional_ceilings(self):
        with tempfile.TemporaryDirectory(dir="/var/tmp") as scratch:
            limits = RiskLimits(capital_usd=Decimal("1000000"), max_gross_exposure_usd=Decimal("1000000"),
                                max_order_notional_usd=Decimal("10000"), max_order_qty=Decimal("100"))
            ledger = Ledger(Path(scratch) / "journal.db", limits)
            now = time.time()
            try:
                ledger.start_trial(now)
                controller = Controller(ledger, now + 3600, market_open=True, clock=lambda: now,
                                        stop_file=Path(scratch) / "unused-SYN-stop")
                controller.port = type("Port", (), {"ready": True})()
                controller.quote({"symbol": "SPY", "bid": "99.99", "ask": "100", "ts_ns": int(now * 1e9)})
                controller.before_submit({"client_order_id": "sizing-SYN", "symbol": "SPY", "side": "buy",
                                          "qty": "100", "limit_price": "100", "strategy": "SYN-v1"})
                sizing = controller.private_order_sizing[-1]
                self.assertEqual(sizing["code_binding_ceilings"], ["order_quantity_ceiling", "order_notional_ceiling"])
                self.assertTrue(sizing["capital_at_code_ceiling"])
                self.assertEqual(sizing["submitted_notional_usd"], "10000")
            finally:
                ledger.close()


if __name__ == "__main__":
    unittest.main()
