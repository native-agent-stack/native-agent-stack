"""Exploratory T22 dispatch: fixtures never contact a broker."""
import importlib
import importlib.util
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import asyncio
from decimal import Decimal
import time
import sys

SOURCE = Path(__file__).resolve().parents[1] / "blueprints/us-equities/adaptive-paper"
sys.path.insert(0, str(SOURCE))


class ExploratoryContract(unittest.TestCase):
    def test_forward_exploratory_factors_are_distinct_from_development(self):
        contracts = importlib.import_module("blueprints.us-equities.strategies.contracts")
        values = dict(instrument_id="SPY.ALPACA", cohort_sha256="a" * 64,
                      source_sha256="b" * 64, ts_event=1_900_000_000_000_000_000,
                      ts_init=1_900_000_000_000_000_000,
                      valid_until_ns=1_900_000_001_000_000_000,
                      values=(("momentum_20", "0.03"),), halted=False)
        snapshot = contracts.FactorSnapshot(**values, evidence_class="exploratory")
        self.assertEqual(snapshot.evidence_class, "exploratory")
        with self.assertRaisesRegex(ValueError, "development_cutoff_exceeded"):
            contracts.FactorSnapshot(**values, evidence_class="development")
        spec = contracts.StrategySpec(instrument_id="SPY.ALPACA",
                                      cohort_sha256="a" * 64,
                                      evidence_class="exploratory")
        self.assertEqual(spec.evidence_class, "exploratory")
        with self.assertRaisesRegex(ValueError, "measured_exit_policy"):
            contracts.StrategySpec(instrument_id="SPY.ALPACA",
                                   cohort_sha256="a" * 64, evidence_class="development")

    def test_runner_loads_hash_bound_exploratory_family_and_refuses_wrong_inputs(self):
        import sys
        source = Path(__file__).resolve().parents[1] / "blueprints/us-equities/adaptive-paper"
        sys.path.insert(0, str(source))
        runner = importlib.import_module("runner")
        with tempfile.TemporaryDirectory(dir="/var/tmp") as root:
            root = Path(root)
            snapshot = dict(instrument_id="SPY.ALPACA", cohort_sha256="a" * 64,
                            source_sha256="b" * 64, ts_event=1, ts_init=1,
                            valid_until_ns=2, values={"atr_price": "1", "entry_trigger": "100",
                            "momentum_20": "0.03", "range_breakout": "1.02",
                            "tight_range_state": "0.02"}, evidence_class="exploratory", halted=False)
            raw = json.dumps(snapshot).encode()
            (root / "factors.json").write_bytes(raw)
            config = json.loads((source / "config.json").read_text())
            config.update(paper_lane="B", evidence_class="exploratory", symbols=["SPY"], benchmarks=["SPY"],
                          max_held_symbols=1)
            config["t22"] = dict(family="momentum_breakout", preset="conservative-v1",
                                 instance_id="trial_one", cohort_sha256="a" * 64,
                                 factors_file="factors.json", factors_sha256=hashlib.sha256(raw).hexdigest())
            path = root / "config.json"
            path.write_text(json.dumps(config))
            loaded, _, _ = runner.load_config(path)
            self.assertEqual(loaded["_t22"].snapshot.instrument_id, "SPY.ALPACA")
            for updates in ({"paper_lane": "A"}, {"evidence_class": "synthetic"},
                            {"t22": config["t22"] | {"factors_file": str(root / "factors.json")}},
                            {"exit_quote_max_age_seconds": 11},
                            {"exploratory_exit_preset": {"name": "baseline"}},
                            {"sessions": {"extended_hours": False, "overnight_holds": True,
                                          "overnight_gross_multiple": "1.0"}}):
                with self.subTest(updates=updates):
                    path.write_text(json.dumps(config | updates))
                    with self.assertRaises(ValueError):
                        runner.load_config(path)
            path.write_text(json.dumps(config))
            (root / "factors.json").write_bytes(raw + b" ")
            with self.assertRaisesRegex(ValueError, "t22_factor_hash_mismatch"):
                runner.load_config(path)


@unittest.skipUnless(importlib.util.find_spec("nautilus_trader"), "requires pinned native runtime")
class NativeDispatch(unittest.TestCase):
    def test_stale_or_future_packet_never_starts_native_dispatch(self):
        import sys
        from types import SimpleNamespace
        from unittest.mock import patch
        source = Path(__file__).resolve().parents[1] / "blueprints/us-equities/adaptive-paper"
        sys.path.insert(0, str(source))
        runner = importlib.import_module("runner")
        dispatch = importlib.import_module("t22_dispatch")
        contracts = importlib.import_module("blueprints.us-equities.strategies.contracts")
        now = time.time_ns()
        for stamp, until in ((now - 10_000_000_000, now - 1),
                             (now + 10_000_000_000, now + 20_000_000_000)):
            snapshot = contracts.FactorSnapshot("SPY.ALPACA", "a" * 64, "b" * 64,
                        stamp, stamp, until, (), evidence_class="exploratory", halted=False)
            config = {"_t22": dispatch.T22Dispatch("momentum_breakout", "conservative-v1",
                        "trial_one", "c" * 64, snapshot)}
            with patch("native_adapter.build_node") as node:
                with self.assertRaisesRegex(ValueError, "t22_factors_unavailable_or_stale"):
                    asyncio.run(runner.run_native(SimpleNamespace(), None, [], "fixture", config, "100000"))
                node.assert_not_called()

    def test_family_dispatch_places_owned_stock_limits_and_exits_flat(self):
        self.exercise_dispatch()

    def test_ranked_mover_family_uses_same_guarded_dispatch(self):
        self.exercise_dispatch(family="gap_premarket", preset="aggressive-v1")

    def test_stop_latch_suppresses_entry_without_clearing_it(self):
        self.exercise_dispatch(stopped=True)

    def test_explicit_halt_suppresses_entry(self):
        self.exercise_dispatch(halted=True)

    def test_stream_integrity_gap_suppresses_entry(self):
        self.exercise_dispatch(gap=True)

    def test_durable_startup_freeze_remains_needs_attention_when_flat(self):
        self.exercise_dispatch(frozen=True)

    def exercise_dispatch(self, *, stopped=False, halted=False, gap=False, frozen=False,
                          family="momentum_breakout", preset="conservative-v1"):
        from tests.adaptive_paper_hermetic import patch_default_stop, restore_default_stop
        from tests.test_us_equities_strategies import synthetic_rth_context
        source = Path(__file__).resolve().parents[1] / "blueprints/us-equities/adaptive-paper"
        import sys
        sys.path.insert(0, str(source))
        runner = importlib.import_module("runner")
        safety = importlib.import_module("safety")
        dispatch = importlib.import_module("t22_dispatch")
        contracts = importlib.import_module("blueprints.us-equities.strategies.contracts")
        simulation = importlib.import_module("simulation")
        token = patch_default_stop()
        self.addCleanup(restore_default_stop, token)
        if stopped:
            safety.DEFAULT_STOP.write_text("fixture stop\n")
        with tempfile.TemporaryDirectory(dir="/var/tmp") as root:
            limits = safety.RiskLimits(max_order_qty=Decimal(1))
            ledger = safety.Ledger(Path(root) / "ledger.db", limits)
            self.addCleanup(ledger.close)
            ledger.start_trial(time.time())
            if frozen:
                ledger.freeze("fixture_integrity_fault")
            controller = runner.Controller(ledger, time.time() + 3600, market_open=True)
            port = simulation.SimulatedPort(controller, ("SPY",))
            if gap:
                port.health["reasons"] = ["stream_integrity_gap"]
            controller.port = port
            stamp = time.time_ns()
            snapshot = contracts.FactorSnapshot("SPY.ALPACA", "a" * 64, "b" * 64,
                stamp - 301_000_000_000, stamp - 301_000_000_000, stamp + 600_000_000_000,
                tuple(sorted({"momentum_20": "0.03", "range_breakout": "1.02",
                              "tight_range_state": "0.02", "atr_price": "0.2",
                              "overnight_gap": "0.05", "premarket_return": "0.02",
                              "premarket_activity": "2",
                              "entry_trigger": "100"}.items())), evidence_class="exploratory", halted=halted)
            config = json.loads((source / "config.json").read_text())
            config.update(duration_seconds=2, cleanup_seconds=3, symbols=["SPY"],
                          benchmarks=["SPY"], max_held_symbols=1)
            config["_t22"] = dispatch.T22Dispatch(family, preset, "trial_one", "c" * 64, snapshot)
            with synthetic_rth_context():
                result = asyncio.run(asyncio.wait_for(runner.run_native(controller, None,
                    [{"symbol": "SPY"}], "t22-fixture", config, "100000"), 8))
            self.assertEqual(result["paper_lane"], "B")
            self.assertEqual(result["evidence_class"], "exploratory")
            self.assertEqual(result["t22"]["family"], family)
            self.assertEqual(result["adapter_errors"], [], result)
            self.assertEqual(result["callback_faults"], [], result)
            self.assertTrue(result["flat"], result)
            self.assertEqual([i.side for i in ledger.intents()], [] if stopped or halted or gap or frozen else ["buy", "sell"], result)
            self.assertEqual(result["native_fill_events"], 0 if stopped or halted or gap or frozen else 2, result)
            if not stopped and not halted and not gap and not frozen:
                self.assertTrue(all("family=" + family in order["tags"] for order in port.orders.values()), result)
            self.assertTrue(result["reconciliation"]["positions_match"])
            self.assertTrue(result["reconciliation"]["cash_match"])
            if stopped:
                self.assertTrue(safety.DEFAULT_STOP.exists())
            if frozen:
                self.assertEqual(result["status"], "needs_attention", result)

    def test_status_adapter_delivers_explicit_halt_and_resume_without_fabricating_state(self):
        from types import SimpleNamespace
        adapter = importlib.import_module("native_adapter")
        from nautilus_trader.model import MarketStatusAction
        session = adapter.NativeSession(SimpleNamespace(), [{"symbol": "SPY"}])
        observed = []
        session.data = SimpleNamespace(clock=SimpleNamespace(timestamp_ns=lambda: 100),
                                       _handle_data=observed.append)
        session.status_subscriptions.add("SPY")
        session.on_status({"symbol": "SPY", "ts_ns": 90, "halted": None})
        self.assertEqual(observed, [])
        session.on_status({"symbol": "SPY", "ts_ns": 91, "halted": True})
        session.on_status({"symbol": "SPY", "ts_ns": 92, "halted": False})
        self.assertEqual([s.action for s in observed], [MarketStatusAction.HALT, MarketStatusAction.TRADING])
        self.assertEqual([s.ts_event for s in observed], [91, 92])
        self.assertEqual(session.errors, [])
        # Negative status is observed immediately; an earlier/future resume
        # cannot erase it from the subscription startup cache.
        session.on_status({"symbol": "SPY", "ts_ns": 110, "halted": True})
        session.on_status({"symbol": "SPY", "ts_ns": 95, "halted": False})
        session.on_status({"symbol": "SPY", "ts_ns": 120, "halted": False})
        self.assertEqual(session.statuses["SPY"].action, MarketStatusAction.HALT)
        self.assertEqual(len(observed), 3)
