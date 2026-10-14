"""Aggregate-derived synthetic sell-age controls; no broker, raw pages or credentials."""

from dataclasses import replace
import json
from pathlib import Path
import tempfile
import types
import sys
import unittest
from unittest.mock import Mock, patch

try:
    from . import test_adaptive_paper_mover as fixtures
except ImportError:
    import test_adaptive_paper_mover as fixtures

import safety
import transport

ROOT = Path(__file__).resolve().parents[1]
AGGREGATES = json.loads((ROOT / "tests/fixtures/adaptive_paper_exit_quote_age/aggregate-selection.json").read_text())
AGES = [float(row["age_seconds_p50"]) for row in AGGREGATES["stale_minute_median_cases"]]


def sell_limits(base=None, seconds=30):
    base = base or safety.RiskLimits()
    if "exit_quote_max_age_seconds" in base.__dataclass_fields__:
        return replace(base, exit_quote_max_age_seconds=seconds)
    # For fail-before only, attach the proposed setting to the old frozen object.
    # Main's real quote checks still use 3 s and fail on quote age, not TypeError.
    object.__setattr__(base, "exit_quote_max_age_seconds", seconds)
    return base


class SellQuoteAgeRegressionTests(unittest.TestCase):
    def ledger(self, directory, limits):
        ledger = safety.Ledger(Path(directory) / "ledger.sqlite3", limits)
        self.addCleanup(ledger.close)
        ledger.start_trial(1000)
        quote = safety.Quote("SPY", "100", "100.01", 1000)
        ledger.reserve_intent("buy", "SPY", "buy", "1", "100.02", quote=quote,
                              now=1000, market_open=True, session_close=5000,
                              stop_file=Path(directory) / "STOP")
        ledger.record_order("buy", "synthetic-buy", "filled", "1", "100", timestamp=1000)
        return ledger

    def test_measured_stale_minutes_allow_owned_sell_reservation(self):
        for age in AGES:
            with self.subTest(age=age), tempfile.TemporaryDirectory() as directory:
                ledger = self.ledger(directory, sell_limits())
                quote = safety.Quote("SPY", "100", "100.01", 1025 - age)
                try:
                    result = ledger.reserve_intent("sell", "SPY", "sell", "1", "99.99", quote=quote,
                        now=1025, market_open=True, session_close=5000)
                    outcome = result.status
                except safety.SafetyError as error:
                    outcome = str(error)
                self.assertEqual(outcome, "reserved")

    def test_measured_stale_minutes_allow_pending_sell_revalidation(self):
        for age in AGES:
            with self.subTest(age=age), tempfile.TemporaryDirectory() as directory:
                ledger = self.ledger(directory, sell_limits())
                ledger.reserve_intent("sell", "SPY", "sell", "1", "99.99",
                    quote=safety.Quote("SPY", "100", "100.01", 1000), now=1000,
                    market_open=True, session_close=5000)
                try:
                    ledger.validate_pending("sell", quote=safety.Quote("SPY", "100", "100.01", 1025-age),
                                            now=1025, market_open=True, session_close=5000)
                    outcome = "admitted"
                except safety.SafetyError as error:
                    outcome = str(error)
                self.assertEqual(outcome, "admitted")

    def test_measured_stale_minutes_allow_mover_exit_pricing(self):
        for age in AGES:
            with self.subTest(age=age):
                h = fixtures.BookHarness(self, symbols=fixtures.scan_dict()["symbols"][:1])
                h.book.limits = sell_limits(h.limits)
                now = h.t0 + 1
                h.quote("ABCD", "3.21", "3.22", now)
                buy = fixtures.submits(h.evaluate(now), "buy")[0]
                h.fill(buy, buy.qty, "3.22", now)
                at = now + 3600
                h.quote("ABCD", "3.20", "3.21", at-age)
                sells = fixtures.submits(h.evaluate(at), "sell")
                self.assertEqual(len(sells), 1)
                self.assertLessEqual(sells[0].limit_price, fixtures.D("3.20"))

    def wire_port(self, age_ns):
        port = object.__new__(transport.AlpacaPaperTransport)
        port._stopping, port._started = False, True
        import threading
        port._reasons, port._state_lock = set(), threading.RLock()
        port._quote_values = {"SPY": {"ts_ns": 1_000_000_000_000-age_ns}}
        port.order_quote_max_age_ns = 3_000_000_000
        port.exit_quote_max_age_ns = 30_000_000_000
        return port

    def test_measured_stale_minutes_allow_final_sell_wire_guard(self):
        for age in AGES:
            with self.subTest(age=age), patch.object(transport.time, "time_ns", return_value=1_000_000_000_000):
                port = self.wire_port(int(age*1_000_000_000))
                try:
                    port._wire_guard({"symbol": "SPY", "side": "sell"})
                    outcome = "admitted"
                except transport.SubmissionNotSent:
                    outcome = "refused"
                self.assertEqual(outcome, "admitted")

    def test_config_propagates_sell_age_and_refuses_above_measured_ceiling(self):
        data = fixtures.config_data()
        data["exit_quote_max_age_seconds"] = 30
        _, limits, _ = fixtures.load(data)
        self.assertEqual(getattr(limits, "exit_quote_max_age_seconds", None), 30)
        data["exit_quote_max_age_seconds"] = 31
        with self.assertRaises((safety.SafetyError, ValueError)):
            fixtures.load(data)


class SellQuoteAgeControls(unittest.TestCase):
    def test_transport_constructor_defaults_to_entry_age_and_caps_explicit_exit_age(self):
        try:
            from .test_adaptive_paper_transport import FakeStream
        except ImportError:
            from test_adaptive_paper_transport import FakeStream
        enums = types.ModuleType("alpaca.data.enums")
        enums.DataFeed = lambda value: value
        stubs = {"alpaca": types.ModuleType("alpaca"), "alpaca.data": types.ModuleType("alpaca.data"),
                 "alpaca.data.enums": enums}
        with patch.dict(sys.modules, stubs), patch.object(transport, "_sdk_client", return_value=Mock()), \
             patch.object(transport, "_protocol_factory", return_value=None), \
             patch.object(transport, "_stream_classes", return_value=(FakeStream, FakeStream)):
            def build(**kwargs):
                return transport.AlpacaPaperTransport("fixture-key", "fixture-secret", ["SPY"],
                    before_request=lambda *a, **k: None, before_submit=lambda _: None,
                    sink_observation=lambda _: None, order_quote_max_age_seconds=2, **kwargs)
            self.assertEqual(build().exit_quote_max_age_ns, 2_000_000_000)
            self.assertEqual(build(exit_quote_max_age_seconds=30).exit_quote_max_age_ns, 30_000_000_000)
            for value in [31, 0, -1, True, False, "30", 30.0]:
                with self.subTest(value=value), self.assertRaises(transport.TransportError):
                    build(exit_quote_max_age_seconds=value)

    def test_entries_and_mark_to_market_keep_the_three_second_bound(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = safety.Ledger(Path(directory)/"ledger.sqlite3", sell_limits())
            self.addCleanup(ledger.close)
            ledger.start_trial(1000)
            stale = safety.Quote("SPY", "100", "100.01", 996)
            with self.assertRaisesRegex(safety.SafetyError, "quote_not_fresh"):
                ledger.reserve_intent("buy", "SPY", "buy", "1", "100.02", quote=stale,
                    now=1000, market_open=True, session_close=5000, stop_file=Path(directory)/"STOP")
            with self.assertRaisesRegex(safety.SafetyError, "quote_not_fresh"):
                ledger.mark_to_market([stale], 1000)

    def test_sell_age_future_tolerance_ownership_and_ceiling_are_bounded(self):
        helper = SellQuoteAgeRegressionTests()
        for age, allowed in [(30, True), (30.001, False), (-.25, True), (-.251, False)]:
            with self.subTest(age=age), tempfile.TemporaryDirectory() as directory:
                ledger = helper.ledger(directory, sell_limits())
                try:
                    quote = safety.Quote("SPY", "100", "100.01", 1025-age)
                    call = lambda: ledger.reserve_intent("sell", "SPY", "sell", "1", "99.99", quote=quote,
                        now=1025, market_open=True, session_close=5000)
                    if allowed:
                        self.assertEqual(call().status, "reserved")
                    else:
                        with self.assertRaisesRegex(safety.SafetyError, "quote_not_fresh"):
                            call()
                finally:
                    helper.doCleanups()
        with self.assertRaisesRegex(safety.SafetyError, "integer_limit_out_of_bounds"):
            safety.RiskLimits(quote_max_age_seconds=4)
        for value in [0, -1, 31, True, False, "30", 30.0]:
            with self.subTest(value=value), self.assertRaises((safety.SafetyError, ValueError)):
                safety.RiskLimits(exit_quote_max_age_seconds=value)

    def test_default_legacy_frozen_limits_and_restart_still_match(self):
        ordinary = safety.RiskLimits()
        # New absent setting is omitted exactly like the existing leverage field.
        self.assertNotIn("exit_quote_max_age_seconds", json.loads(ordinary.frozen_json()))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"ledger.sqlite3"
            ledger = safety.Ledger(path, ordinary)
            ledger.close()
            ledger = safety.Ledger(path, safety.RiskLimits())
            ledger.close()
            candidate = object.__new__(safety.Ledger)
            try:
                with self.assertRaisesRegex(safety.SafetyError, "persisted_risk_limits_differ"):
                    candidate.__init__(path, sell_limits())
            finally:
                if hasattr(candidate, "db"):
                    candidate.close()

    def test_unknown_quotes_oversells_and_halted_mover_exits_are_not_admitted(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = safety.Ledger(Path(directory)/"ledger.sqlite3", sell_limits())
            self.addCleanup(ledger.close)
            ledger.start_trial(1000)
            with self.assertRaisesRegex(safety.SafetyError, "sell_exceeds_owned"):
                ledger.reserve_intent("sell", "SPY", "sell", "1", "99.99",
                    quote=safety.Quote("SPY", "100", "100.01", 980), now=1000,
                    market_open=True, session_close=5000)
            with self.assertRaisesRegex(safety.SafetyError, "quote_required"):
                ledger.reserve_intent("sell", "SPY", "sell", "1", "99.99", quote=None,
                    now=1000, market_open=True, session_close=5000)
        h = fixtures.BookHarness(self, symbols=fixtures.scan_dict()["symbols"][:1])
        h.book.limits = sell_limits(h.limits)
        now = h.t0+1
        h.quote("ABCD", "3.21", "3.22", now)
        buy = fixtures.submits(h.evaluate(now), "buy")[0]
        h.fill(buy, buy.qty, "3.22", now)
        at = now+3600
        h.quote("ABCD", "3.20", "3.21", at-20, halted=True)
        self.assertEqual(fixtures.submits(h.evaluate(at), "sell"), [])
        self.assertEqual(h.book.legs["ABCD"].exits, [])

    def test_wire_bound_is_side_specific_inclusive_and_rechecked_after_delay(self):
        helper = SellQuoteAgeRegressionTests()
        with patch.object(transport.time, "time_ns", return_value=1_000_000_000_000), \
             patch.object(transport.AlpacaPaperTransport, "ready", new=property(lambda _: True)):
            for side, age, allowed in [("sell", 30_000_000_000, True), ("sell", 30_000_000_001, False),
                    ("buy", 3_000_000_000, True), ("buy", 3_000_000_001, False),
                    ("sell", -250_000_000, True), ("sell", -250_000_001, False)]:
                with self.subTest(side=side, age=age):
                    port = helper.wire_port(age)
                    call = lambda: port._wire_guard({"symbol":"SPY", "side":side})
                    if allowed:
                        call()
                    else:
                        with self.assertRaises(transport.SubmissionNotSent):
                            call()
            port = helper.wire_port(20_000_000_000)
            port._wire_guard({"symbol":"SPY", "side":"sell"})
            port._quote_values["SPY"]["ts_ns"] -= 11_000_000_000
            with self.assertRaises(transport.SubmissionNotSent):
                port._wire_guard({"symbol":"SPY", "side":"sell"})
