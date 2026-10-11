"""SYN ordinary adaptive sell-age regressions; native engine with fake order I/O."""

from dataclasses import replace
from decimal import Decimal
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "blueprints/us-equities/adaptive-paper"
sys.path.insert(0, str(SOURCE))
import runner
from strategies import AdaptivePolicy

NATIVE = importlib.util.find_spec("nautilus_trader") is not None
ABSENT = object()
MEASURED_AGE = float(json.loads((ROOT / "tests/fixtures/adaptive_paper_exit_quote_age/aggregate-selection.json")
                              .read_text())["stale_minute_median_cases"][-1]["age_seconds_p50"])


def load_policy(exit_age=ABSENT):
    data = json.loads((SOURCE / "config.json").read_text())
    if exit_age is not ABSENT:
        data["exit_quote_max_age_seconds"] = exit_age
    original = Path.read_text
    fixture = Path("synthetic-sell-age-config.json")
    with patch.object(Path, "read_text", lambda path, *a, **kw:
                      json.dumps(data) if path == fixture else original(path, *a, **kw)):
        _, limits, config = runner.load_config(fixture)
    return limits, config


class AdaptiveSellAgePolicyRegressionTests(unittest.TestCase):
    def test_loaded_policy_prices_ordinary_exits_with_the_validated_sell_bound(self):
        for session in ("RTH", "PRE", "POST"):
            for ceiling, age in ((30, MEASURED_AGE), (30, 30), (10, 10)):
                with self.subTest(session=session, ceiling=ceiling, age=age):
                    limits, config = load_policy(ceiling)
                    self.assertEqual(limits.effective_exit_quote_max_age_seconds, ceiling)
                    self.assertEqual(config.quote_age_seconds, 3)
                    policy = AdaptivePolicy(config)
                    symbol = config.symbols[0]
                    policy.sync_positions({symbol: {"qty": "1", "avg_entry_price": "100"}}, 900)
                    policy.observe(symbol, 99.5, 99.51, 1000-age)
                    policy.exit_session = session
                    decision = policy.decide(1000, allow_entries=False)
                    self.assertEqual(decision.exits.get(symbol), "stop_loss")
                    self.assertTrue(policy.last_exit_decisions[symbol].submit)

    def test_absent_null_and_explicit_bounds_preserve_entry_feature_isolation(self):
        for setting in (ABSENT, None, 30):
            with self.subTest(setting="absent" if setting is ABSENT else setting):
                _, config = load_policy(setting)
                # Public decisions use a warmed causal trend, with fresh controls.
                config = replace(config, warmup_samples=32, warmup_seconds=30)
                fresh, stale = AdaptivePolicy(config), AdaptivePolicy(config)
                for i in range(40):
                    for symbol in config.symbols:
                        price = 100 + (.015 if symbol in config.benchmarks else .04) * i
                        fresh.observe(symbol, price-.005, price+.005, 1000+i)
                        stale.observe(symbol, price-.005, price+.005, 1000+i)
                self.assertTrue(fresh.decide(1039).targets)
                result = stale.decide(1039+MEASURED_AGE)
                self.assertEqual(result.targets, {})
                self.assertEqual(result.signals, ())
                self.assertEqual(result.regime, "unavailable")


@unittest.skipUnless(NATIVE, "requires installed native engine; broker operations are fakes")
class AdaptiveSellAgeNativeRegressionTests(unittest.TestCase):
    def strategy(self, session, exit_age=30):
        from .test_adaptive_paper_extended_exits import NativeExtendedExitCallerTests
        strategy, helper, now, events = NativeExtendedExitCallerTests().strategy(session=session)
        limits, config = load_policy(exit_age)
        strategy.policy = AdaptivePolicy(replace(config, exit_replace_enabled=True))
        strategy.ledger.limits = limits
        return strategy, helper, now, events

    def test_forced_native_sells_use_the_bound_in_rth_pre_and_post(self):
        for session in (None, "RTH", "PRE", "POST"):
            for ceiling, age, expected in ((30, 2, 1), (30, MEASURED_AGE, 1),
                    (30, 30, 1), (30, 30.001, 0), (10, 10, 1), (10, 10.001, 0),
                    (30, -.25, 1), (30, -.251, 0)):
                with self.subTest(session=session, ceiling=ceiling, age=age):
                    strategy, _, now, _ = self.strategy(session, ceiling)
                    if session is None:
                        strategy._exit_session_at = None
                    strategy.policy.observe("AAPL", 100, 100.02, now[0]-age)
                    strategy.rebalance(now=now[0], force_exit=True)
                    self.assertEqual(len(strategy.submitted), expected)
                    if not expected:
                        self.assertEqual(strategy._exit_pending_attention, {"AAPL": "quote_stale"})

    def test_ordinary_native_stop_sells_use_the_bound_in_rth_pre_and_post(self):
        for session in ("RTH", "PRE", "POST"):
            for age, expected in ((2, 1), (MEASURED_AGE, 1), (30, 1), (30.001, 0)):
                with self.subTest(session=session, age=age):
                    strategy, _, now, _ = self.strategy(session)
                    strategy.policy.observe("AAPL", 99.5, 99.51, now[0]-age)
                    strategy.rebalance(now=now[0])
                    self.assertEqual(len(strategy.submitted), expected)
                    if expected:
                        self.assertEqual(next(iter(strategy.pending.values()))["reason"], "stop_loss")

    def test_cancel_ack_reprices_from_the_ack_clock_with_the_sell_bound(self):
        for session in (None, "RTH", "PRE", "POST"):
            for ceiling, age, expected in ((30, MEASURED_AGE, 1), (30, 30, 1),
                                         (30, 30.001, 0), (10, 10, 1), (10, 10.001, 0)):
                with self.subTest(session=session, ceiling=ceiling, age=age):
                    strategy, helper, now, _ = self.strategy(session, ceiling)
                    if session is None:
                        strategy._exit_session_at = None
                    strategy.policy.observe("AAPL", 100, 100.02, now[0])
                    client_id = helper.seed_resting_sell(strategy)
                    self.assertEqual(strategy.replace_exit("AAPL", now[0], Decimal("2"),
                                                           "trailing_stop"), "cancel_requested")
                    self.assertEqual(strategy.submitted, [])
                    # The request was fresh. Its quote ages during cancellation.
                    now[0] += age
                    strategy.on_order_canceled(SimpleNamespace(client_order_id=client_id))
                    self.assertEqual(len(strategy.submitted), expected)
                    self.assertNotIn("AAPL", strategy._exit_replace_busy)
                    if not expected:
                        self.assertEqual(strategy._exit_pending_attention, {"AAPL": "quote_stale"})

    def test_absent_and_null_keep_the_legacy_native_sell_bound(self):
        for session in (None, "RTH", "PRE", "POST"):
            for setting in (ABSENT, None):
                for age, expected in ((2, 1), (3, 1), (3.001, 0), (MEASURED_AGE, 0)):
                    with self.subTest(session=session, null=setting is None, age=age):
                        strategy, _, now, _ = self.strategy(session, setting)
                        if session is None:
                            strategy._exit_session_at = None
                        strategy.policy.observe("AAPL", 100, 100.02, now[0]-age)
                        strategy.rebalance(now=now[0], force_exit=True)
                        self.assertEqual(len(strategy.submitted), expected)

    def test_sell_override_keeps_native_buy_guards_and_held_admission_marks_on_entry_age(self):
        from .test_adaptive_paper_exits import RebalanceBusySymbolReplaceExitTests
        from strategies_v1 import Decision
        helper = RebalanceBusySymbolReplaceExitTests()
        for age, expected in ((2, 1), (3, 1), (3.001, 0), (MEASURED_AGE, 0)):
            with self.subTest(age=age):
                strategy, policy = helper.strategy_and_policy()
                _, config = load_policy(30)
                policy.config = config
                policy._decisions = [Decision(1000, "trend", {"AAPL": 1}, (), {}, .01, "SYN")]
                strategy.positions = lambda: {}
                strategy.ledger.unresolved = lambda: []
                strategy.ledger.halted_reason = lambda: None
                policy.latest["AAPL"] = SimpleNamespace(bid=100, ask=100.02, timestamp=1000-age)
                strategy.started, strategy.enabled = True, True
                strategy.rebalance(now=1000)
                self.assertEqual(len(strategy.submitted), expected)
                strategy.positions = lambda: {"AAPL": {"qty": "1"}}
                self.assertEqual(strategy._operational_status(1000).state_fresh, bool(expected))
