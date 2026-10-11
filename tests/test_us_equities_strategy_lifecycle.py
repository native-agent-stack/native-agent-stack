"""Native regression seams for T22 order lifecycle, durable safety and clocks."""

from __future__ import annotations

import importlib
import importlib.util
import ast
import tempfile
import time
import unittest
from contextlib import nullcontext
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

NATIVE = importlib.util.find_spec("nautilus_trader") is not None
if NATIVE:
    simulation = importlib.import_module("blueprints.us-equities.strategies.simulation")
    contracts = importlib.import_module("blueprints.us-equities.strategies.contracts")
    families = importlib.import_module("blueprints.us-equities.strategies.families")
    safety = importlib.import_module("blueprints.us-equities.adaptive-paper.safety")


def run_strategy(
    *,
    ledger,
    faults,
    instrument=None,
    bids=None,
    overrides=None,
    advance_to_ns=None,
    start_ns=None,
    halt_after_ns=None,
    reopen_at_ns=None,
    strategy_type=None,
    quote_offsets_ns=None,
    status_events=(),
    post_cutoff_fill_sink=None,
    notice_sink=None,
    snapshot_steps=(),
    initial_snapshot_age_ns=600_000_000_000,
    liquidity_consumption=False,
    quote_sizes=None,
    fill_model=None,
):
    """Drive the real class through native data/clock/callback boundaries."""
    from nautilus_trader.model import (
        CustomData,
        InstrumentStatus,
        MarketStatusAction,
        QuoteTick,
        Quantity,
    )

    engine, instrument = simulation.fixture_engine(
        instrument, liquidity_consumption=liquidity_consumption, fill_model=fill_model
    )
    start_ns = simulation.BASE_NS if start_ns is None else start_ns
    fields = {
        "entry_timeout_ns": 2_000_000_000,
        "exit_timeout_ns": 2_000_000_000,
        "exit_deadline_ns": start_ns + 8_000_000_000,
    }
    fields.update(overrides or {})
    spec = replace(
        contracts.StrategySpec(simulation.INSTRUMENT_ID, simulation.COHORT_SHA256),
        **fields,
    )
    dependencies = dict(
        ledger=ledger,
        fault_sink=faults.append,
        post_cutoff_fill_sink=post_cutoff_fill_sink,
    )
    if notice_sink is not None:
        dependencies["notice_sink"] = notice_sink
    strategy = (strategy_type or families.GapPremarketStrategy)(spec, **dependencies)
    snapshot = replace(
        simulation.fixture_snapshot(),
        evidence_class=spec.evidence_class,
        ts_event=start_ns - initial_snapshot_age_ns,
        ts_init=start_ns - initial_snapshot_age_ns,
        valid_until_ns=start_ns + 3600_000_000_000,
    )
    quotes = simulation.fixture_quotes(
        instrument, start_ns=start_ns, **({"bids": bids} if bids is not None else {})
    )
    if quote_offsets_ns is not None:
        if len(quote_offsets_ns) != len(quotes):
            raise ValueError("one_timestamp_per_quote_required")
        quotes = [
            QuoteTick(
                quote.instrument_id,
                quote.bid_price,
                quote.ask_price,
                quote.bid_size,
                quote.ask_size,
                start_ns + offset,
                start_ns + offset,
            )
            for quote, offset in zip(quotes, quote_offsets_ns, strict=True)
        ]
    if quote_sizes is not None:
        quotes = [
            QuoteTick(
                q.instrument_id,
                q.bid_price,
                q.ask_price,
                Quantity.from_int(size),
                Quantity.from_int(size),
                q.ts_event,
                q.ts_init,
            )
            for q, size in zip(quotes, quote_sizes, strict=True)
        ]
    data = [
        CustomData(families.snapshot_data_type(simulation.INSTRUMENT_ID), snapshot),
        *quotes,
    ]
    data.extend(
        InstrumentStatus(
            instrument.id,
            getattr(MarketStatusAction, action),
            start_ns + event_ns,
            start_ns + init_ns,
            **flags,
        )
        for event_ns, init_ns, action, flags in status_events
    )
    if advance_to_ns is not None:
        data.append(
            CustomData(
                families.snapshot_data_type(simulation.INSTRUMENT_ID),
                replace(snapshot, ts_event=advance_to_ns, ts_init=advance_to_ns),
            )
        )
    if halt_after_ns is not None:
        data.append(
            CustomData(
                families.snapshot_data_type(simulation.INSTRUMENT_ID),
                replace(
                    snapshot, ts_event=halt_after_ns, ts_init=halt_after_ns, halted=True
                ),
            )
        )
    if reopen_at_ns is not None:
        data.append(
            CustomData(
                families.snapshot_data_type(simulation.INSTRUMENT_ID),
                replace(snapshot, ts_event=reopen_at_ns, ts_init=reopen_at_ns),
            )
        )
    for deliver_ns, halted in snapshot_steps:
        data.append(
            CustomData(
                families.snapshot_data_type(simulation.INSTRUMENT_ID),
                replace(
                    snapshot,
                    ts_event=start_ns + deliver_ns,
                    ts_init=start_ns + deliver_ns,
                    halted=halted,
                ),
            )
        )
    try:
        engine.add_strategy(strategy)
        engine.add_data(data, sort=True)
        engine.run()
        return strategy
    finally:
        engine.dispose()


class PortableRecoveryTests(unittest.TestCase):
    """Execute production command/recovery methods without importing Nautilus.

    Fake clock and wire sinks make these logic checks, not engine acceptance.
    The persistence cases use the actual SQLite Ledger with close/reopen.
    """

    @classmethod
    def setUpClass(cls):
        from decimal import Decimal

        cls.D = Decimal
        if importlib.util.find_spec("exchange_calendars") is None:
            from types import ModuleType

            calendar = ModuleType("exchange_calendars")

            def refuse_calendar(*args, **kwargs):
                raise AssertionError("notice tests must not query a calendar")

            calendar.get_calendar = refuse_calendar
            # These tests exercise metadata only. Retain the actual Ledger;
            # block its unrelated calendar port when that dependency is absent.
            with patch.dict("sys.modules", {"exchange_calendars": calendar}):
                cls.safety = importlib.import_module(
                    "blueprints.us-equities.adaptive-paper.safety"
                )
        else:
            cls.safety = importlib.import_module(
                "blueprints.us-equities.adaptive-paper.safety"
            )
        cls.notices = importlib.import_module(
            "blueprints.us-equities.strategies.halt_notice"
        )
        cls.contracts = importlib.import_module(
            "blueprints.us-equities.strategies.contracts"
        )
        source = (
            Path(__file__).resolve().parents[1]
            / "blueprints/us-equities/strategies/families.py"
        )
        tree = ast.parse(source.read_text())
        strategy = next(
            n
            for n in tree.body
            if isinstance(n, ast.ClassDef) and n.name == "FamilyStrategy"
        )
        selected = {
            "_drive",
            "_halt_reason",
            "_submit",
            "_notify_halt_hold",
            "_clear_halt_hold",
            "_retire_halt_notice_alert",
            "_record",
            "_freeze",
            "_on_watchdog",
            "_restore_ledger",
            "reconcile_held_notice_resolved",
        }
        methods = [
            n
            for n in strategy.body
            if isinstance(n, ast.FunctionDef) and n.name in selected
        ]
        namespace = {"D": Decimal, "decimal": cls.contracts.decimal}
        exec(
            compile(
                ast.fix_missing_locations(ast.Module(body=methods, type_ignores=[])),
                str(source),
                "exec",
            ),
            namespace,
        )
        cls.Methods = type(
            "ExactRecoveryMethods", (), {name: namespace[name] for name in selected}
        )

    def fixture(
        self,
        *,
        ledger=None,
        halted=None,
        expiry=0,
        role="entry",
        quantity="0",
        now=3_000_000_000,
    ):
        class Clock:
            def __init__(self, now):
                self.now, self.alerts = now, {}

            def timestamp_ns(self):
                return self.now

            def timer_names(self):
                return list(self.alerts)

            def cancel_timer(self, name):
                self.alerts.pop(name, None)

            def set_time_alert_ns(self, name, when, callback):
                self.alerts[name] = (when, callback)

            def advance(self, target):
                while self.alerts and min(t[0] for t in self.alerts.values()) <= target:
                    name = min(self.alerts, key=lambda key: self.alerts[key][0])
                    self.now, callback = self.alerts.pop(name)
                    callback(None)
                self.now = target

        s = self.Methods()
        s.clock = Clock(now)
        s.spec = SimpleNamespace(
            instrument_id="SPY.ALPACA",
            entry_timeout_ns=2_000_000_000,
            exit_timeout_ns=2_000_000_000,
            entry_deadline_ns=None,
            exit_deadline_ns=None,
        )
        s.instrument_id = SimpleNamespace(symbol="SPY")
        s.client_id_prefix = "t22-unit-"
        s.instrument_status_halted = False
        s.snapshot_halted, s.snapshot_halt_valid_until_ns = halted, expiry
        s.quantity = self.D(quantity)
        s.pending = SimpleNamespace(client_order_id=s.client_id_prefix + "0000001")
        s.pending_role, s.pending_since_ns = role, 0
        s.pending_policy_deadline_ns = None
        s.cancel_requested, s.cancel_requested_ns = False, 0
        s.faulted, s.enabled = False, True
        s.flags, s.trace, s.callback_faults = set(), [], []
        s.last_halt_notice_ns = s.last_halt_notice_reason = None
        s.active_halt_notice = s.restored_halt_notice = None
        s.cancels, s.submits, s.notified = [], [], []
        s.sequence, s.entry_attempted = 0, False
        s.cancel_order, s.submit_order = s.cancels.append, s.submits.append
        s.fault_sink = s.notified.append
        s.notice_sink = s.notified.append
        s.ledger = (
            ledger
            if ledger is not None
            else SimpleNamespace(
                freeze=lambda reason: None,
                intents=lambda: (),
                unresolved=lambda: (),
                positions=dict,
                halted_reason=lambda: None,
            )
        )
        s.cache = SimpleNamespace(
            orders_open=lambda **kw: [], positions_open=lambda **kw: []
        )
        return s

    def test_unknown_state_cancels_only_entries_and_refuses_exit_replacement_commands(
        self,
    ):
        for state in (None, False):
            for boundary in ("entry", "exit", "cancel_entry", "cancel_exit", "replace"):
                with self.subTest(state=state, boundary=boundary):
                    s = self.fixture(
                        halted=state,
                        expiry=2_000_000_000,
                        role="entry" if boundary.endswith("entry") else "exit",
                        quantity="0" if boundary.endswith("entry") else "7",
                    )
                    original = s.pending
                    if boundary.startswith("cancel"):
                        s._drive()
                    elif boundary == "replace":
                        s.pending = None  # Prior order already terminal.
                        s._submit("SELL", self.D(7), self.D(10), "exit", "time_exit")
                    else:
                        s._drive()
                    expected_cancel = boundary in ("entry", "cancel_entry")
                    self.assertEqual(
                        s.cancels, [original.client_order_id] if expected_cancel else []
                    )
                    self.assertEqual(s.submits, [])
                    self.assertEqual(s.sequence, 0)
                    if boundary != "replace":
                        self.assertIs(s.pending, original)
                    self.assertEqual(s.cancel_requested, expected_cancel)

    def test_observed_halt_still_dispatches_entry_cancel(self):
        s = self.fixture(halted=True)
        s._drive()
        self.assertEqual(s.cancels, ["t22-unit-0000001"])
        self.assertTrue(s.cancel_requested)

    def recovered(self, path, now):
        ledger = self.safety.Ledger(path)
        original = self.fixture(ledger=ledger, halted=True, role="exit", quantity="7")
        original._drive()
        with ledger._transaction():
            ledger.db.execute("INSERT INTO positions VALUES ('SPY','7','70')")
        ledger.close()
        reopened = self.safety.Ledger(path)
        restarted = self.fixture(ledger=reopened, now=now)
        restarted.pending = None
        self.notices.restore(restarted, arm=True)
        self.assertFalse(restarted._restore_ledger())
        return restarted, reopened

    def test_real_ledger_reopen_preserves_original_boundary_and_order_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            s, ledger = self.recovered(
                Path(directory) / "ledger.sqlite3", 100_000_000_000
            )
            try:
                self.assertEqual(s.last_halt_notice_ns, 3_000_000_000)
                s.clock.advance(603_000_000_000 - 1)
                self.assertNotIn("held_halted", s.notified)
                s.clock.advance(603_000_000_000)
                notices = [row for row in s.trace if row["event"] == "halt_hold_notice"]
                self.assertEqual([row["now_ns"] for row in notices], [603_000_000_000])
                self.assertEqual(notices[0]["client_order_id"], "t22-unit-0000001")
                self.assertTrue(s.faulted)
                self.assertEqual(s.cancels + s.submits, [])
            finally:
                ledger.close()

    def test_overdue_notices_coalesce_once_then_use_actual_delivery_time(self):
        with tempfile.TemporaryDirectory() as directory:
            s, ledger = self.recovered(
                Path(directory) / "ledger.sqlite3", 2000_000_000_000
            )
            try:
                s.clock.advance(2600_000_000_000 - 1)
                notices = [row for row in s.trace if row["event"] == "halt_hold_notice"]
                self.assertEqual([row["now_ns"] for row in notices], [2000_000_000_000])
                s.clock.advance(2600_000_000_000)
                self.assertEqual(
                    [
                        row["now_ns"]
                        for row in s.trace
                        if row["event"] == "halt_hold_notice"
                    ],
                    [2000_000_000_000, 2600_000_000_000],
                )
            finally:
                ledger.close()

    def test_reconciliation_cannot_clear_an_unresolved_held_position(self):
        with tempfile.TemporaryDirectory() as directory:
            s, ledger = self.recovered(
                Path(directory) / "ledger.sqlite3", 100_000_000_000
            )
            try:
                with self.assertRaisesRegex(ValueError, "held_exposure_not_resolved"):
                    s.reconcile_held_notice_resolved()
                self.assertIsNotNone(
                    self.notices.load(ledger, s.spec.instrument_id, s.client_id_prefix)
                )
                with ledger._transaction():
                    ledger.db.execute(
                        "UPDATE positions SET qty='0',cost_basis='0' WHERE symbol='SPY'"
                    )
                s.reconcile_held_notice_resolved()
                self.assertIsNone(
                    self.notices.load(ledger, s.spec.instrument_id, s.client_id_prefix)
                )
                self.assertEqual(s.clock.alerts, {})
                self.assertTrue(s.faulted)  # Resolution does not resume trading.
            finally:
                ledger.close()

    def test_real_metadata_is_scoped_to_one_strategy_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = self.safety.Ledger(Path(directory) / "ledger.sqlite3")
            try:
                s = self.fixture(ledger=ledger, halted=True, role="exit", quantity="7")
                s._drive()
                self.assertIsNone(
                    self.notices.load(ledger, s.spec.instrument_id, "t22-another-")
                )
            finally:
                ledger.close()

    def test_notice_persistence_runtime_error_keeps_cancel_delivery_and_next_alert(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = self.safety.Ledger(Path(directory) / "ledger.sqlite3")
            try:
                s = self.fixture(ledger=ledger, halted=True, quantity="3")
                original = s.pending
                with patch.object(ledger, "_set", side_effect=RuntimeError("synthetic write failure")):
                    s._drive()
                self.assertEqual(s.cancels, [original.client_order_id])
                self.assertIs(s.pending, original)
                self.assertTrue(s.cancel_requested)
                self.assertEqual(s.submits, [])
                self.assertEqual(s.notified, ["held_halted"])
                self.assertIn("held_notice_persistence_failed", s.flags)
                rows = [row for row in s.trace if row["event"] == "halt_hold_notice"]
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["persist_error"], "RuntimeError")
                self.assertEqual(rows[0]["client_order_id"], original.client_order_id)
                self.assertEqual(s.clock.alerts["t22-halt-hold"][0], 603_000_000_000)
                self.assertIsNone(self.notices.load(ledger, s.spec.instrument_id, s.client_id_prefix))
                self.assertEqual(s.callback_faults, [])
            finally:
                ledger.close()

    def test_routine_notice_keeps_an_existing_freeze_without_repeating_the_stop(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = self.safety.Ledger(Path(directory) / "ledger.sqlite3")
            try:
                s = self.fixture(ledger=ledger, halted=True, role="exit", quantity="7")
                s.pending = None
                stops, notices = [], []
                s.fault_sink, s.notice_sink = stops.append, notices.append
                s._freeze("held_quote_stale")
                self.assertEqual(ledger.halted_reason(), "held_quote_stale")
                s._notify_halt_hold(s.clock.timestamp_ns(), "held_halted")
                self.assertEqual(stops, ["held_quote_stale"])
                self.assertEqual(notices, ["held_halted"])
                self.assertEqual(ledger.halted_reason(), "held_quote_stale")
                self.assertEqual(
                    [row["reason"] for row in s.trace if row["event"] == "safety_freeze"],
                    ["held_quote_stale"],
                )
                self.assertTrue(s.faulted)
                self.assertEqual(s.submits + s.cancels, [])
                self.assertEqual(s.clock.alerts["t22-halt-hold"][0], 603_000_000_000)
                self.assertEqual(
                    self.notices.load(ledger, s.spec.instrument_id, s.client_id_prefix)["reason"],
                    "held_halted",
                )
            finally:
                ledger.close()

    def test_recreated_actor_retains_notice_without_adopting_exposure_or_sending_orders(self):
        with tempfile.TemporaryDirectory() as directory:
            s, ledger = self.recovered(Path(directory) / "ledger.sqlite3", 100_000_000_000)
            try:
                # Preserve the real startup freeze. Each recovery/clear fence
                # alone is redundant; the property catches only their pair.
                with ledger._transaction():
                    ledger.db.execute("UPDATE positions SET qty='0',cost_basis='0' WHERE symbol='SPY'")
                s.snapshot_halted, s.snapshot_halt_valid_until_ns = False, 200_000_000_000
                original = self.notices.load(ledger, s.spec.instrument_id, s.client_id_prefix)
                self.assertTrue(s.faulted)
                self.assertFalse(s.enabled)
                s._drive()
                self.assertEqual(self.notices.load(ledger, s.spec.instrument_id, s.client_id_prefix), original)
                self.assertEqual(s.quantity, 0)
                self.assertIsNone(s.pending)
                self.assertEqual(s.cancels + s.submits, [])
                self.assertTrue(s.faulted)
                self.assertFalse(s.enabled)
            finally:
                ledger.close()

    def test_each_reconciliation_refusal_signal_retains_the_durable_notice(self):
        # Each case has exactly one refusal signal; another guard cannot hide
        # deletion of the signal under test. Ledger position has its own real
        # close/reopen regression above.
        for signal in ("quantity", "pending", "ledger_unresolved", "cache_order", "cache_position"):
            with self.subTest(signal=signal), tempfile.TemporaryDirectory() as directory:
                ledger = self.safety.Ledger(Path(directory) / "ledger.sqlite3")
                try:
                    s = self.fixture(ledger=ledger, halted=True, role="exit", quantity="7")
                    s._drive()
                    s.quantity, s.pending = self.D(0), None
                    original = self.notices.load(ledger, s.spec.instrument_id, s.client_id_prefix)
                    s.faulted = True
                    due = s.clock.alerts["t22-halt-hold"][0]
                    if signal == "quantity":
                        s.quantity = self.D(7)
                    elif signal == "pending":
                        s.pending = SimpleNamespace(client_order_id=original["client_order_id"])
                    elif signal == "ledger_unresolved":
                        with ledger._transaction():
                            ledger.db.execute(
                                "INSERT INTO intents(client_id,symbol,side,qty,limit_price,status,updated_at) VALUES (?,?,?,?,?,?,?)",
                                (original["client_order_id"], "SPY", "SELL", "7", "10", "reserved", 0),
                            )
                        self.assertEqual(len(ledger.unresolved()), 1)
                    elif signal == "cache_order":
                        s.cache.orders_open = lambda **kw: [SimpleNamespace()]
                    else:
                        s.cache.positions_open = lambda **kw: [SimpleNamespace()]
                    with self.assertRaisesRegex(ValueError, "held_exposure_not_resolved"):
                        s.reconcile_held_notice_resolved()
                    self.assertEqual(self.notices.load(ledger, s.spec.instrument_id, s.client_id_prefix), original)
                    self.assertEqual(s.clock.alerts["t22-halt-hold"][0], due)
                    self.assertEqual(s.active_halt_notice, original)
                    self.assertTrue(s.faulted)
                    self.assertEqual(s.submits + s.cancels, [])
                finally:
                    ledger.close()


@unittest.skipUnless(NATIVE, "requires the exact locked Nautilus rc5 runtime")
class LifecycleTests(unittest.TestCase):
    def test_development_restart_does_not_consume_notice_without_callable_port(self):
        notices = importlib.import_module("blueprints.us-equities.strategies.halt_notice")
        base = simulation.BASE_NS
        development = {
            "evidence_class": "development",
            "qualified_data": ("released_development", "horizon_qualified"),
            "exit_policy": "regular-close-v1",
            "exit_evidence_sha256": "f" * 64,
        }

        class ObserveStartup(families.GapPremarketStrategy):
            def on_start(self):
                super().on_start()
                self.startup_notice_armed = "t22-halt-hold" in self.clock.timer_names()

        for binding in ("omitted", "noncallable", "callable"):
            for offset in (100_000_000_000, 2000_000_000_000):
                with self.subTest(binding=binding, offset=offset), tempfile.TemporaryDirectory() as directory:
                    path = Path(directory) / "restart.sqlite3"
                    ledger = safety.Ledger(path)
                    try:
                        original = run_strategy(
                            ledger=ledger, faults=[], bids=("10", "10", "9", "8", "8"),
                            halt_after_ns=base + 3_000_000_000,
                            notice_sink=lambda reason: None,
                            post_cutoff_fill_sink=lambda *args: None,
                            overrides=dict(development, exit_deadline_ns=base + 2_000_000_000),
                        )
                        before = notices.load(ledger, original.spec.instrument_id, original.client_id_prefix)
                        self.assertIsNotNone(before)
                        self.assertEqual(before["last_notice_ns"], base + 3_000_000_000)
                        ledger.close()
                        ledger = safety.Ledger(path)
                        faults, deliveries = [], []
                        dependencies = {} if binding == "omitted" else {
                            "notice_sink": 7 if binding == "noncallable" else deliveries.append
                        }
                        restarted = run_strategy(
                            ledger=ledger, faults=faults, bids=("8",) * 3,
                            start_ns=base + offset, initial_snapshot_age_ns=0,
                            quote_offsets_ns=(0, 604_000_000_000, 1204_000_000_000),
                            post_cutoff_fill_sink=lambda *args: None,
                            strategy_type=ObserveStartup, overrides=development, **dependencies,
                        )
                        after = notices.load(ledger, original.spec.instrument_id, original.client_id_prefix)
                        rows = [r for r in restarted.trace if r["event"] == "halt_hold_notice"]
                        self.assertEqual(restarted.client_id_prefix, original.client_id_prefix)
                        self.assertFalse(any(r["event"] in ("submit", "cancel_requested") for r in restarted.trace))
                        self.assertTrue(restarted.faulted)
                        self.assertFalse(restarted.enabled)
                        self.assertEqual(restarted.quantity, 0)
                        if binding == "callable":
                            due = base + (603_000_000_000 if offset == 100_000_000_000 else offset)
                            expected = [due + i * 600_000_000_000 for i in range(2 if offset == 100_000_000_000 else 3)]
                            self.assertTrue(restarted.startup_notice_armed)
                            self.assertNotIn("startup_notice_sink_required", faults)
                            self.assertEqual([r["now_ns"] for r in rows], expected)
                            self.assertEqual(deliveries, [before["reason"]] * len(expected))
                            self.assertEqual(after["last_notice_ns"], expected[-1])
                            self.assertEqual(after["next_due_ns"], expected[-1] + 600_000_000_000)
                        else:
                            self.assertEqual(after, before)  # Preserve the complete recovery record.
                            self.assertFalse(restarted.startup_notice_armed)
                            self.assertEqual(rows, [])
                            self.assertEqual(deliveries, [])
                            self.assertEqual(faults, ["startup_notice_sink_required"])
                            self.assertFalse(restarted.callback_faults)
                            # A correctly wired later restart can consume the
                            # preserved record; refusal cannot discard custody.
                            ledger.close()
                            ledger = safety.Ledger(path)
                            recovered_deliveries = []
                            run_strategy(
                                ledger=ledger, faults=[], bids=("8",),
                                start_ns=base + offset + 1300_000_000_000,
                                initial_snapshot_age_ns=0,
                                notice_sink=recovered_deliveries.append,
                                post_cutoff_fill_sink=lambda *args: None,
                                overrides=development,
                            )
                            self.assertEqual(recovered_deliveries, [before["reason"]])
                            recovered = notices.load(ledger, original.spec.instrument_id, original.client_id_prefix)
                            self.assertEqual(recovered["last_notice_ns"], base + offset + 1300_000_000_000)
                    finally:
                        ledger.close()

    def test_corrected_notice_port_restart_notifies_overdue_record_immediately(self):
        notices = importlib.import_module("blueprints.us-equities.strategies.halt_notice")
        base = simulation.BASE_NS
        development = {
            "evidence_class": "development",
            "qualified_data": ("released_development", "horizon_qualified"),
            "exit_policy": "regular-close-v1",
            "exit_evidence_sha256": "f" * 64,
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "corrected-port.sqlite3"
            ledger = safety.Ledger(path)
            try:
                original = run_strategy(
                    ledger=ledger, faults=[], bids=("10", "10", "9", "8", "8"),
                    halt_after_ns=base + 3_000_000_000,
                    notice_sink=lambda reason: None, post_cutoff_fill_sink=lambda *args: None,
                    overrides=dict(development, exit_deadline_ns=base + 2_000_000_000),
                )
                before = notices.load(ledger, original.spec.instrument_id, original.client_id_prefix)
                ledger.close()
                ledger = safety.Ledger(path)
                faults = []
                refused = run_strategy(
                    ledger=ledger, faults=faults, bids=("8",),
                    start_ns=base + 2000_000_000_000, initial_snapshot_age_ns=0,
                    post_cutoff_fill_sink=lambda *args: None, overrides=development,
                )
                self.assertEqual(faults, ["startup_notice_sink_required"])
                self.assertFalse(any(r["event"] == "halt_hold_notice" for r in refused.trace))
                self.assertEqual(notices.load(ledger, original.spec.instrument_id, original.client_id_prefix), before)
                ledger.close()
                ledger = safety.Ledger(path)
                delivered = []
                corrected = run_strategy(
                    ledger=ledger, faults=[], bids=("8",),
                    start_ns=base + 2060_000_000_000, initial_snapshot_age_ns=0,
                    notice_sink=delivered.append, post_cutoff_fill_sink=lambda *args: None,
                    overrides=development,
                )
                self.assertEqual(delivered, ["held_halted"])
                self.assertEqual(
                    [r["now_ns"] for r in corrected.trace if r["event"] == "halt_hold_notice"],
                    [base + 2060_000_000_000],
                )
                self.assertFalse(any(r["event"] in ("submit", "cancel_requested") for r in corrected.trace))
            finally:
                ledger.close()

    def test_equal_accepted_snapshot_replay_clears_late_halt_before_native_entry(self):
        observed = []

        class Replay(families.GapPremarketStrategy):
            def on_quote(self, quote):
                if not observed and self.snapshot is not None:
                    accepted = self.snapshot
                    self.on_data(replace(
                        accepted, halted=True,
                        ts_event=accepted.ts_event - 1_000_000_000,
                        ts_init=accepted.ts_init - 1_000_000_000,
                    ))
                    held = self._halt_reason(self.clock.timestamp_ns())
                    self.on_data(accepted)
                    observed.append((held, self._halt_reason(self.clock.timestamp_ns()),
                                     self.snapshot is accepted, self.snapshot_halted,
                                     self.snapshot_halt_timestamps))
                return super().on_quote(quote)

        strategy = run_strategy(ledger=None, faults=[], strategy_type=Replay)
        self.assertEqual(len(observed), 1)
        held, resumed, same_snapshot, latch, stamps = observed[0]
        self.assertEqual(held, "held_halted")
        self.assertIsNone(resumed)
        self.assertTrue(same_snapshot)
        self.assertIs(latch, False)
        self.assertEqual(stamps, (strategy.snapshot.ts_event, strategy.snapshot.ts_init))
        self.assertTrue(any(row["event"] == "submit" and row["side"] == "BUY"
                            for row in strategy.trace))
        self.assertFalse(strategy.callback_faults)

    def test_snapshot_replay_keeps_conflict_future_and_native_halt_vetoes(self):
        from nautilus_trader.model import InstrumentStatus, MarketStatusAction

        for boundary in (
            "conflicting", "future", "older", "native_halt",
            "accepted_true_replay", "accepted_none_replay", "newer_event_halt",
        ):
            with self.subTest(boundary=boundary):
                observed = []

                class RefuseReplay(families.GapPremarketStrategy):
                    def on_data(self, data, boundary=boundary):
                        value = getattr(data, "data", data)
                        if (
                            boundary == "newer_event_halt"
                            and self.snapshot is None
                            and isinstance(value, contracts.FactorSnapshot)
                        ):
                            # Leave room for a newer event with an older init;
                            # every fixture still respects ts_event <= ts_init.
                            value = replace(value, ts_event=value.ts_init - 10_000_000_000)
                        return super().on_data(value)

                    def on_quote(self, quote, boundary=boundary, observed=observed):
                        if not observed and self.snapshot is not None:
                            accepted = self.snapshot
                            if boundary in ("accepted_true_replay", "accepted_none_replay"):
                                self.on_data(replace(
                                    accepted,
                                    halted=True if boundary == "accepted_true_replay" else None,
                                    ts_event=accepted.ts_event + 1_000_000_000,
                                    ts_init=accepted.ts_init + 1_000_000_000,
                                ))
                                accepted = self.snapshot
                            else:
                                self.on_data(replace(
                                    accepted, halted=True,
                                    ts_event=accepted.ts_event + 1_000_000_000
                                    if boundary == "newer_event_halt"
                                    else accepted.ts_event - 1_000_000_000,
                                    ts_init=accepted.ts_init - 1_000_000_000,
                                ))
                            replay = accepted
                            if boundary == "conflicting":
                                replay = replace(accepted, valid_until_ns=accepted.valid_until_ns + 1)
                            elif boundary == "future":
                                replay = replace(accepted, ts_init=quote.ts_event + 1)
                            elif boundary == "older":
                                replay = replace(
                                    accepted, ts_event=accepted.ts_event - 2_000_000_000,
                                    ts_init=accepted.ts_init - 2_000_000_000,
                                )
                            elif boundary == "native_halt":
                                self.on_instrument_status(InstrumentStatus(
                                    self.instrument_id, MarketStatusAction.HALT,
                                    quote.ts_event, quote.ts_event,
                                ))
                            self.on_data(replay)
                            observed.append((self._halt_reason(self.clock.timestamp_ns()),
                                             self.faulted, self.snapshot is accepted,
                                             self.snapshot_halted, self.instrument_status_halted))
                        return super().on_quote(quote)

                strategy = run_strategy(ledger=None, faults=[], strategy_type=RefuseReplay)
                self.assertEqual(len(observed), 1)
                reason, frozen, retained, latch, native_halt = observed[0]
                self.assertEqual(reason, "held_halt_state_unknown"
                                 if boundary == "accepted_none_replay" else "held_halted")
                self.assertTrue(retained)
                self.assertEqual(frozen, boundary == "conflicting")
                self.assertIs(latch, None if boundary == "accepted_none_replay"
                              else boundary != "native_halt")
                self.assertEqual(native_halt, boundary == "native_halt")
                self.assertFalse(any(row["event"] == "submit" for row in strategy.trace))
                self.assertFalse(strategy.callback_faults)

    def test_development_startup_requires_callable_notice_sink(self):
        # Synthetic native data carries development labels only to exercise
        # startup admission; this does not qualify a development dataset.
        for binding in ("omitted", "noncallable", "callable"):
            with self.subTest(binding=binding), tempfile.TemporaryDirectory() as directory:
                ledger = safety.Ledger(Path(directory) / "notice-startup.sqlite3")
                faults, notices = [], []
                try:
                    dependencies = {} if binding == "omitted" else {
                        "notice_sink": 7 if binding == "noncallable" else notices.append
                    }
                    strategy = run_strategy(
                        ledger=ledger, faults=faults,
                        post_cutoff_fill_sink=lambda strategy, event, cutoff: None,
                        overrides={
                            "evidence_class": "development",
                            "qualified_data": ("released_development", "horizon_qualified"),
                            "exit_policy": "regular-close-v1",
                            "exit_evidence_sha256": "f" * 64,
                        },
                        **dependencies,
                    )
                    submitted = [row for row in strategy.trace if row["event"] == "submit"]
                    if binding == "callable":
                        self.assertTrue(any(row["side"] == "BUY" for row in submitted))
                        self.assertNotIn("startup_notice_sink_required", faults)
                    else:
                        self.assertTrue(strategy.faulted)
                        self.assertFalse(strategy.enabled)
                        self.assertEqual(faults, ["startup_notice_sink_required"])
                        self.assertIn("startup_notice_sink_required", strategy.flags)
                        self.assertEqual(ledger.halted_reason(), "startup_notice_sink_required")
                        self.assertEqual(strategy.sequence, 0)
                        self.assertIsNone(strategy.pending)
                        self.assertEqual(submitted, [])
                        self.assertEqual(notices, [])
                    self.assertFalse(strategy.callback_faults)
                finally:
                    ledger.close()

    def test_expiry_first_observes_unknown_state_and_persists_notice_before_return(self):
        start = simulation.BASE_NS
        notices, faults, observed = [], [], []
        notice_state = importlib.import_module(
            "blueprints.us-equities.strategies.halt_notice"
        )

        class Expire(families.GapPremarketStrategy):
            def on_data(self, data):
                value = getattr(data, "data", data)
                if isinstance(value, contracts.FactorSnapshot):
                    value = replace(value, valid_until_ns=start + 2_400_000_000)
                return super().on_data(value)

            def on_quote(self, quote):
                if (
                    not observed
                    and quote.ts_event >= start + 2_500_000_000
                    and self.pending_role == "exit"
                ):
                    # Inject the terminal callback before the next drive first
                    # observes expired producer state. No earlier hold notice
                    # can mask loss of the expiry callback's independent port.
                    original_id = str(self.pending.client_order_id)
                    self.on_order_expired(
                        SimpleNamespace(client_order_id=self.pending.client_order_id)
                    )
                    observed.append(
                        (
                            list(notices),
                            notice_state.load(
                                self.ledger, self.spec.instrument_id, self.client_id_prefix
                            ),
                            original_id,
                            self.clock.timestamp_ns(),
                            self.faulted,
                            self.pending,
                            self.quantity,
                            set(self.flags),
                        )
                    )
                    return  # Inspect the callback before any subsequent drive.
                return super().on_quote(quote)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.sqlite3"
            ledger = safety.Ledger(path)
            try:
                strategy = run_strategy(
                    ledger=ledger,
                    faults=faults,
                    notice_sink=notices.append,
                    strategy_type=Expire,
                    bids=("10", "10", "9", "8", "8"),
                    quote_offsets_ns=(
                        0, 1_000_000_000, 2_000_000_000, 2_200_000_000, 2_500_000_000
                    ),
                    overrides={"exit_deadline_ns": start + 2_000_000_000},
                )
            finally:
                ledger.close()
            self.assertEqual(len(observed), 1)
            delivered, state, original_id, now, frozen, pending, quantity, flags = observed[0]
            self.assertEqual(delivered, ["held_halt_state_unknown"])
            self.assertIsNotNone(state)
            self.assertEqual(
                state,
                {
                    "schema_version": 1,
                    "instrument_id": strategy.spec.instrument_id,
                    "client_id_prefix": strategy.client_id_prefix,
                    "client_order_id": original_id,
                    "reason": "held_halt_state_unknown",
                    "last_notice_ns": now,
                    "next_due_ns": now + 600_000_000_000,
                    "active": True,
                },
            )
            reopened = safety.Ledger(path)
            try:
                self.assertEqual(
                    notice_state.load(
                        reopened, strategy.spec.instrument_id, strategy.client_id_prefix
                    ),
                    state,
                )
            finally:
                reopened.close()
        self.assertTrue(frozen)
        self.assertIsNone(pending)
        self.assertGreater(quantity, 0)
        self.assertIn("held_halt_state_unknown", flags)
        self.assertIn("halted_day_expiry_requires_handoff", flags)
        self.assertIn("halted_day_expiry_requires_handoff", faults)
        self.assertFalse(strategy.callback_faults)

    def test_partial_native_fill_is_cancelled_before_a_raising_notice(self):
        from nautilus_trader.execution import DefaultFillModel

        start = simulation.BASE_NS
        observed = []

        def down(reason):
            raise RuntimeError("notice sink unavailable")

        class PartialEntry(families.GapPremarketStrategy):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.fault_sink = down
                self.notice_sink = down

            def cancel_order(self, client_order_id):
                observed.append(
                    (self.clock.timestamp_ns(), self.quantity, self.pending_remaining)
                )
                return super().cancel_order(client_order_id)

        strategy = run_strategy(
            ledger=None,
            faults=[],
            strategy_type=PartialEntry,
            bids=("10", "10", "11", "11"),
            quote_offsets_ns=(0, 200_000_000, 400_000_000, 800_000_000),
            quote_sizes=(3, 3, 3, 3),
            liquidity_consumption=True,
            fill_model=DefaultFillModel(
                prob_fill_on_limit=1.0, prob_slippage=0.0, random_seed=22
            ),
            status_events=((300_000_000, 300_000_000, "HALT", {}),),
            overrides={
                "entry_timeout_ns": 60_000_000_000,
                "exit_deadline_ns": start + 600_000_000_000,
            },
        )
        self.assertEqual(
            observed,
            [(start + 300_000_000, contracts.decimal("3"), contracts.decimal("4"))],
        )
        self.assertEqual(
            [
                r["quantity"]
                for r in strategy.trace
                if r["event"] == "fill" and r["side"] == "BUY"
            ],
            ["3"],
        )
        self.assertEqual(
            [
                r
                for r in strategy.callback_faults
                if r["callback"] == "halt_hold_notice"
            ],
            [
                {
                    "callback": "halt_hold_notice",
                    "reason": "held_halted",
                    "stop_error": "RuntimeError",
                }
            ],
        )
        self.assertFalse(
            [
                r
                for r in strategy.callback_faults
                if r["callback"]
                in ("on_data", "on_instrument_status", "on_order_filled")
            ]
        )
        events = [r["event"] for r in strategy.trace]
        self.assertLess(
            events.index("cancel_requested"), events.index("halt_hold_notice")
        )

    def test_separate_notice_channel_does_not_stop_native_actor_or_resumption(self):
        start = simulation.BASE_NS
        for bound in (False, True):

            class StopOnFault(families.GapPremarketStrategy):
                stop_calls = []
                notice_times = []

                def on_start(self, bound=bound):
                    def stop(reason):
                        self.stop_calls.append(self.clock.timestamp_ns())
                        self.stop()

                    self.fault_sink = stop
                    self.notice_sink = (
                        (
                            lambda reason: self.notice_times.append(
                                self.clock.timestamp_ns()
                            )
                        )
                        if bound
                        else None
                    )
                    return super().on_start()

            with self.subTest(notice_bound=bound):
                strategy = run_strategy(
                    ledger=None,
                    faults=[],
                    strategy_type=StopOnFault,
                    bids=("10", "10", "9", "8", "8", "8", "8", "8"),
                    quote_offsets_ns=(
                        0,
                        1_000_000_000,
                        2_000_000_000,
                        2_200_000_000,
                        602_500_000_000,
                        1202_500_000_000,
                        1205_200_000_000,
                        1205_400_000_000,
                    ),
                    halt_after_ns=start + 2_300_000_000,
                    reopen_at_ns=start + 1205_000_000_000,
                    overrides={"exit_deadline_ns": start + 2_000_000_000},
                )
                self.assertEqual(strategy.stop_calls, [])
                self.assertEqual(
                    strategy.notice_times,
                    [
                        start + ns
                        for ns in (2_300_000_000, 602_300_000_000, 1202_300_000_000)
                    ]
                    if bound
                    else [],
                )
                cancels = [
                    r for r in strategy.trace if r["event"] == "cancel_requested"
                ]
                self.assertEqual(cancels[0]["now_ns"], start + 1205_000_000_000)
                self.assertFalse(strategy.callback_faults)

    def test_frozen_hold_reason_survives_resumption(self):
        start = simulation.BASE_NS
        faults = []
        strategy = run_strategy(
            ledger=None,
            faults=faults,
            bids=("10",) * 12,
            halt_after_ns=start + 3_000_000_000,
            reopen_at_ns=start + 5_000_000_000,
        )
        self.assertTrue(strategy.faulted)
        self.assertGreater(strategy.quantity, 0)
        self.assertIn("held_halted", strategy.flags)
        self.assertEqual(faults, ["held_halted"])

    def _halt_state_series(
        self, steps, quote_offsets_ns=(0, 1_000_000_000, 2_000_000_000, 3_000_000_000)
    ):
        """What the instance would do about orders after each scripted snapshot and each quote.

        ``steps`` are ``(deliver_ms, halted, event_ms, init_ms, valid_until_ms)`` offsets from the fixture
        start. The engine delivers each snapshot at ``deliver_ms``; the strategy then rewrites its halt flag
        and stamps, as a producer whose clock differs from the host's would. ``valid_until_ms`` None keeps the
        fixture's. No order is ever sent, so only the halt state machine is observed."""
        start = simulation.BASE_NS
        ms = 1_000_000
        script = {
            start + deliver * ms: (halted, start + event * ms, start + init * ms, valid)
            for deliver, halted, event, init, valid in steps
        }
        series = []

        class Scripted(families.GapPremarketStrategy):
            def entry_condition(self, snapshot):
                return False

            def on_data(self, data):
                value = getattr(data, "data", data)
                if (
                    not isinstance(value, contracts.FactorSnapshot)
                    or value.ts_init not in script
                ):
                    return super().on_data(value)
                halted, event, init, valid = script[value.ts_init]
                before = len(self.trace)
                super().on_data(
                    replace(
                        value,
                        halted=halted,
                        ts_event=event,
                        ts_init=init,
                        valid_until_ns=value.valid_until_ns
                        if valid is None
                        else start + valid * ms,
                    )
                )
                now = self.clock.timestamp_ns()
                refused = tuple(
                    row["reason"]
                    for row in self.trace[before:]
                    if row["event"] == "snapshot_refused"
                )
                series.append(
                    ("data", (now - start) // ms, self._halt_reason(now), refused)
                )

            def on_quote(self, quote):
                super().on_quote(quote)
                now = self.clock.timestamp_ns()
                series.append(
                    ("quote", (now - start) // ms, self._halt_reason(now), ())
                )

        strategy = run_strategy(
            ledger=None,
            faults=[],
            strategy_type=Scripted,
            bids=("10",) * len(quote_offsets_ns),
            quote_offsets_ns=quote_offsets_ns,
            snapshot_steps=tuple(
                (deliver * ms, halted) for deliver, halted, _, _, _ in steps
            ),
        )
        self.assertFalse(strategy.callback_faults)
        return series

    def test_snapshot_halt_fence_keeps_event_and_init_stamps_apart(self):
        held, free = "held_halted", None
        rows = {
            # A halt whose event stamp leads: a resumption with an older event stamp is refused even though its init stamp is newer.
            "event stamp": (
                (
                    (300, True, 700, 700, None),
                    (800, False, 500, 800, None),
                    (900, False, 800, 900, None),
                ),
                [
                    ("quote", 0, free, ()),
                    ("data", 300, held, ("future_availability",)),
                    ("data", 800, held, ("out_of_order",)),
                    ("data", 900, free, ()),
                    ("quote", 1000, free, ()),
                    ("quote", 2000, free, ()),
                    ("quote", 3000, free, ()),
                ],
            ),
            # A halt whose init stamp leads while its event stamp does not: an older init stamp is refused, a newer one resumes.
            "init stamp": (
                (
                    (300, True, 100, 700, None),
                    (500, False, 200, 500, None),
                    (800, False, 200, 800, None),
                ),
                [
                    ("quote", 0, free, ()),
                    ("data", 300, held, ("future_availability",)),
                    ("data", 500, held, ("out_of_order",)),
                    ("data", 800, free, ()),
                    ("quote", 1000, free, ()),
                    ("quote", 2000, free, ()),
                    ("quote", 3000, free, ()),
                ],
            ),
            # A late, older halt cannot lower the fence that a newer halt set.
            "stale halt": (
                (
                    (300, True, 700, 700, None),
                    (400, True, 50, 50, None),
                    (500, False, 500, 500, None),
                    (800, False, 800, 800, None),
                ),
                [
                    ("quote", 0, free, ()),
                    ("data", 300, held, ("future_availability",)),
                    ("data", 400, held, ()),
                    ("data", 500, held, ("out_of_order",)),
                    ("data", 800, free, ()),
                    ("quote", 1000, free, ()),
                    ("quote", 2000, free, ()),
                    ("quote", 3000, free, ()),
                ],
            ),
        }
        for label, (steps, expected) in rows.items():
            with self.subTest(label):
                self.assertEqual(self._halt_state_series(steps), expected)

    def test_known_snapshot_fence_orders_the_event_stamp_of_each_resumption(self):
        free = None
        steps = (
            (300, False, 250, 300, None),  # accepted: the fence becomes (250, 300)
            (
                400,
                False,
                200,
                400,
                None,
            ),  # an older observation with a newer init stamp is refused
            (
                500,
                False,
                280,
                500,
                None,
            ),  # newer in both dimensions: accepted, fence (280, 500)
            (
                600,
                False,
                300,
                450,
                None,
            ),  # init older than the fence: refused (the stored snapshot's own ordering says the same)
        )
        self.assertEqual(
            self._halt_state_series(steps),
            [
                ("quote", 0, free, ()),
                ("data", 300, free, ()),
                ("data", 400, free, ("out_of_order",)),
                ("data", 500, free, ()),
                ("data", 600, free, ("out_of_order",)),
                ("quote", 1000, free, ()),
                ("quote", 2000, free, ()),
                ("quote", 3000, free, ()),
            ],
        )

    def test_available_snapshot_resumption_accepts_equal_fence_stamps(self):
        # A leading halt latches raw stamps but cannot install future factors.
        # Its later available resumption can equal either fence dimension
        # without conflicting with an already installed snapshot revision.
        for event_ms, init_ms in ((600, 700), (600, 750), (650, 700)):
            with self.subTest(event_ms=event_ms, init_ms=init_ms):
                self.assertEqual(
                    self._halt_state_series(
                        (
                            (300, True, 600, 700, None),
                            (800, False, event_ms, init_ms, None),
                        )
                    ),
                    [
                        ("quote", 0, None, ()),
                        ("data", 300, "held_halted", ("future_availability",)),
                        ("data", 800, None, ()),
                        ("quote", 1000, None, ()),
                        ("quote", 2000, None, ()),
                        ("quote", 3000, None, ()),
                    ],
                )

    def test_reason_change_inside_a_hold_notifies_again(self):
        start = simulation.BASE_NS
        notices = []

        class ObserveHold(families.GapPremarketStrategy):
            def on_data(self, data):
                value = getattr(data, "data", data)
                if isinstance(value, contracts.FactorSnapshot):
                    value = replace(value, valid_until_ns=start + 2_500_000_000)
                return super().on_data(value)

            def _record(self, event, **fields):
                super()._record(event, **fields)
                if event == "halt_hold_notice":
                    notices.append(
                        (self.clock.timestamp_ns() - start, fields["reason"])
                    )

        faults = []
        run_strategy(
            ledger=None,
            faults=faults,
            notice_sink=faults.append,
            strategy_type=ObserveHold,
            bids=("10", "10", "9", "8", "8", "8"),
            quote_offsets_ns=(
                0,
                1_000_000_000,
                2_000_000_000,
                2_200_000_000,
                602_500_000_000,
                1202_500_000_000,
            ),
            status_events=(
                (2_300_000_000, 2_300_000_000, "HALT", {}),
                (3_000_000_000, 3_000_000_000, "TRADING", {}),
            ),
            overrides={"exit_deadline_ns": start + 2_000_000_000},
        )
        # A native halt holds the exit; the producer state lapses; the native resumption leaves the hold in place for a different reason,
        # which is worth saying even though the first notice is not ten minutes old. The alerts follow each notice.
        self.assertEqual(
            notices,
            [
                (2_300_000_000, "held_halted"),
                (3_000_000_000, "held_halt_state_unknown"),
                (603_000_000_000, "held_halt_state_unknown"),
            ],
        )
        self.assertEqual(
            faults,
            ["held_halted", "held_halt_state_unknown", "held_halt_state_unknown"],
        )

    def test_halted_is_an_explicit_boolean_or_unknown(self):
        snapshot = simulation.fixture_snapshot()
        for bad in ("false", "yes", 0, 1, "", [], {}):
            with self.subTest(halted=bad), self.assertRaises(ValueError):
                replace(snapshot, halted=bad)
        for good in (True, False, None):
            self.assertIs(replace(snapshot, halted=good).halted, good)

    def test_halt_state_validity_is_the_latest_snapshots(self):
        # A newer snapshot that is valid for less time than its predecessor shortens the state's validity.
        series = self._halt_state_series(((300, False, 300, 300, 900),))
        self.assertEqual(
            series,
            [
                ("quote", 0, None, ()),
                ("data", 300, None, ()),
                ("quote", 1000, "held_halt_state_unknown", ()),
                ("quote", 2000, "held_halt_state_unknown", ()),
                ("quote", 3000, "held_halt_state_unknown", ()),
            ],
        )

    def test_second_halt_after_a_resumption_notifies_again_and_the_flag_clears(self):
        start = simulation.BASE_NS
        notices, flags_at = [], []

        class ObserveHold(families.GapPremarketStrategy):
            def _record(self, event, **fields):
                super()._record(event, **fields)
                if event == "halt_hold_notice":
                    notices.append(self.clock.timestamp_ns() - start)

            def on_quote(self, quote):
                super().on_quote(quote)
                flags_at.append(
                    (self.clock.timestamp_ns() - start, "held_halted" in self.flags)
                )

        faults = []
        strategy = run_strategy(
            ledger=None,
            faults=faults,
            notice_sink=faults.append,
            strategy_type=ObserveHold,
            bids=("10", "10", "9", "8", "8", "8", "8"),
            quote_offsets_ns=(
                0,
                1_000_000_000,
                2_000_000_000,
                2_200_000_000,
                3_500_000_000,
                602_500_000_000,
                1202_500_000_000,
            ),
            snapshot_steps=(
                (2_300_000_000, True),
                (3_000_000_000, False),
                (4_000_000_000, True),
            ),
            overrides={"exit_deadline_ns": start + 2_000_000_000},
        )
        # The first halt notifies at once; the resumption ends that hold; the second halt, well inside ten minutes of the first, notifies at once
        # again and its own ten-minute alert follows. Only the second hold's alert is live.
        self.assertEqual(
            [ns for ns in notices], [2_300_000_000, 4_000_000_000, 604_000_000_000]
        )
        self.assertEqual(faults, ["held_halted"] * 3)
        self.assertEqual(
            flags_at,
            [
                (0, False),
                (1_000_000_000, False),
                (2_000_000_000, False),
                (2_200_000_000, False),
                (3_500_000_000, False),
                (602_500_000_000, True),
                (1202_500_000_000, True),
            ],
        )
        self.assertEqual(strategy.sequence, 2)
        self.assertEqual(strategy.pending_role, "exit")
        self.assertFalse(
            [row for row in strategy.trace if row["event"] == "cancel_requested"]
        )
        self.assertFalse(strategy.faulted)
        self.assertFalse(strategy.callback_faults)

    def test_exit_lost_inside_a_throttled_halt_hold_freezes_once_for_handoff(self):
        start = simulation.BASE_NS
        lost = []

        class LoseExit(families.GapPremarketStrategy):
            def _drive(self):
                if (
                    not lost
                    and self.clock.timestamp_ns() >= start + 5_000_000_000
                    and self.pending_role == "exit"
                ):
                    # The venue cancels the held exit during the halt, inside the ten minutes since the notice.
                    lost.append(self.clock.timestamp_ns() - start)
                    self.on_order_canceled(
                        SimpleNamespace(client_order_id=self.pending.client_order_id)
                    )
                return super()._drive()

        faults = []
        strategy = run_strategy(
            ledger=None,
            faults=faults,
            notice_sink=faults.append,
            strategy_type=LoseExit,
            bids=("10", "10", "9", "8", "8", "8", "8", "8"),
            quote_offsets_ns=(
                0,
                1_000_000_000,
                2_000_000_000,
                2_200_000_000,
                5_000_000_000,
                6_000_000_000,
                7_000_000_000,
                8_000_000_000,
            ),
            halt_after_ns=start + 2_300_000_000,
            overrides={"exit_deadline_ns": start + 2_000_000_000},
        )
        self.assertEqual(len(lost), 1)
        freezes = [row for row in strategy.trace if row["event"] == "safety_freeze"]
        self.assertEqual(
            [(row["now_ns"] - start, row["reason"]) for row in freezes],
            [(5_000_000_000, "held_halted")],
        )
        self.assertTrue(strategy.faulted)
        self.assertGreater(strategy.quantity, 0)
        self.assertEqual(faults, ["held_halted", "held_halted"])
        self.assertFalse(strategy.callback_faults)

    def test_unknown_halt_state_cancels_a_resting_entry_and_never_a_held_exit(self):
        # Pins the current reading of F-1: an entry is cancelled once its halt state lapses (nothing may fill into a state the instance cannot
        # see), a held exit is not (test_expired_halt_state_keeps_working_exit_and_notifies). Flip both assertions if the ruling is the reverse.
        start = simulation.BASE_NS
        calls = []

        class Expiring(families.GapPremarketStrategy):
            def on_data(self, data):
                value = getattr(data, "data", data)
                if isinstance(value, contracts.FactorSnapshot):
                    value = replace(value, valid_until_ns=start + 500_000_000)
                return super().on_data(value)

        with patch.object(
            families.FamilyStrategy,
            "cancel_order",
            new=lambda self, client_id: calls.append(
                (self.clock.timestamp_ns() - start, str(client_id))
            ),
        ):
            strategy = run_strategy(
                ledger=None,
                faults=[],
                strategy_type=Expiring,
                bids=("10",) * 4,
                quote_offsets_ns=(0, 600_000_000, 1_200_000_000, 1_800_000_000),
                overrides={"entry_timeout_ns": 10_000_000_000},
            )
        self.assertEqual([ns for ns, _ in calls], [600_000_000])
        self.assertEqual(calls[0][1], strategy.client_id_prefix + "0000001")
        self.assertEqual(
            [
                (row["now_ns"] - start, row["role"])
                for row in strategy.trace
                if row["event"] == "cancel_requested"
            ],
            [(600_000_000, "entry")],
        )
        self.assertFalse(strategy.callback_faults)

    def test_submit_fence_refuses_every_order_role_while_a_halt_is_known(self):
        start = simulation.BASE_NS
        for carrier in ("native status", "snapshot"):
            for side in (families.OrderSide.BUY, families.OrderSide.SELL):

                class DirectSubmit(families.GapPremarketStrategy):
                    attempted = False

                    def _drive(self):
                        # Isolate the final submit fence from the drive-level refusal.
                        return

                    def on_quote(self, quote, carrier=carrier, side=side):
                        if (
                            self.attempted
                            or self.clock.timestamp_ns() < start + 1_000_000_000
                        ):
                            return
                        self.attempted = True
                        if carrier == "snapshot":
                            self.snapshot_halted = True
                        else:
                            self.instrument_status_halted = True
                        self._submit(
                            side,
                            contracts.decimal("1"),
                            contracts.decimal("10"),
                            "entry" if side == families.OrderSide.BUY else "exit",
                            "time_exit",
                        )

                with self.subTest(carrier=carrier, side=str(side)):
                    strategy = run_strategy(
                        ledger=None,
                        faults=[],
                        strategy_type=DirectSubmit,
                        bids=("10",) * 4,
                    )
                    self.assertEqual(strategy.sequence, 0)
                    self.assertFalse(
                        [row for row in strategy.trace if row["event"] == "submit"]
                    )
                    self.assertEqual(
                        [
                            (row["reason"], row["role"])
                            for row in strategy.trace
                            if row["event"] == "order_refused"
                        ],
                        [
                            (
                                "held_halted",
                                "entry" if side == families.OrderSide.BUY else "exit",
                            )
                        ],
                    )
                    self.assertFalse(strategy.faulted)
                    self.assertFalse(strategy.callback_faults)

    def test_expiry_freezes_a_held_exit_only_for_its_own_order_inside_a_halt(self):
        start = simulation.BASE_NS
        for scenario in ("own order, no halt", "another order, halted"):
            injected = []

            class Expire(families.GapPremarketStrategy):
                def _drive(self, scenario=scenario, injected=injected):
                    if (
                        not injected
                        and self.clock.timestamp_ns() >= start + 2_500_000_000
                        and self.pending_role == "exit"
                    ):
                        injected.append(self.pending.client_order_id)
                        other = "t22-not-the-pending-order-0000001"
                        owned = self.pending.client_order_id
                        self.on_order_expired(
                            SimpleNamespace(
                                client_order_id=owned
                                if scenario == "own order, no halt"
                                else other
                            )
                        )
                    return super()._drive()

            with self.subTest(scenario):
                faults = []
                strategy = run_strategy(
                    ledger=None,
                    faults=faults,
                    notice_sink=faults.append,
                    strategy_type=Expire,
                    bids=("10", "10", "9", "8", "8", "8", "8"),
                    quote_offsets_ns=(
                        0,
                        1_000_000_000,
                        2_000_000_000,
                        2_200_000_000,
                        3_000_000_000,
                        4_000_000_000,
                        5_000_000_000,
                    ),
                    halt_after_ns=None
                    if scenario == "own order, no halt"
                    else start + 2_300_000_000,
                    overrides={"exit_deadline_ns": start + 2_000_000_000},
                )
                self.assertEqual(len(injected), 1)
                self.assertFalse(strategy.faulted)
                self.assertNotIn("halted_day_expiry_requires_handoff", strategy.flags)
                self.assertNotIn("halted_day_expiry_requires_handoff", faults)
                self.assertFalse(strategy.callback_faults)

    def test_unknown_state_blocks_replacement_after_native_cancel_confirmation(self):
        start = simulation.BASE_NS
        for state in ("missing", "expired"):

            class CancelBeforeUnknown(families.GapPremarketStrategy):
                requested_id = None
                terminal_ids = []
                wire_commands = []

                def on_data(self, data, state=state):
                    value = getattr(data, "data", data)
                    if isinstance(value, contracts.FactorSnapshot):
                        if state == "expired":
                            value = replace(value, valid_until_ns=start + 2_300_000_000)
                        elif value.ts_event >= start:
                            value = replace(value, halted=None)
                    return super().on_data(value)

                def on_quote(self, quote):
                    super().on_quote(quote)
                    if self.clock.timestamp_ns() == start + 2_200_000_000:
                        self.requested_id = str(self.pending.client_order_id)
                        self.cancel_order(self.pending.client_order_id)

                def cancel_order(self, client_order_id):
                    self.wire_commands.append((self.clock.timestamp_ns(), "cancel"))
                    return super().cancel_order(client_order_id)

                def submit_order(self, order):
                    self.wire_commands.append((self.clock.timestamp_ns(), "submit"))
                    return super().submit_order(order)

                def on_order_canceled(self, event):
                    self.terminal_ids.append(str(event.client_order_id))
                    return super().on_order_canceled(event)

            with self.subTest(state=state):
                strategy = run_strategy(
                    ledger=None,
                    faults=[],
                    strategy_type=CancelBeforeUnknown,
                    bids=("10", "10", "9", "8", "8", "8"),
                    quote_offsets_ns=(
                        0,
                        1_000_000_000,
                        2_000_000_000,
                        2_200_000_000,
                        2_400_000_000,
                        3_000_000_000,
                    ),
                    advance_to_ns=start + 2_300_000_000 if state == "missing" else None,
                    overrides={
                        "exit_deadline_ns": start + 2_000_000_000,
                        "exit_timeout_ns": 10_000_000_000,
                    },
                )
                self.assertEqual(strategy.terminal_ids, [strategy.requested_id])
                self.assertEqual(strategy.sequence, 2)
                self.assertIsNone(strategy.pending)
                self.assertGreater(strategy.quantity, 0)
                self.assertFalse(
                    [
                        row
                        for row in strategy.wire_commands
                        if row[0] >= start + 2_300_000_000
                    ]
                )
                self.assertIn("held_halt_state_unknown", strategy.flags)
                self.assertFalse(strategy.callback_faults)

    def test_missing_and_expired_state_cancel_pending_native_entry(self):
        start = simulation.BASE_NS
        for state in ("missing", "expired"):

            class UnknownProducer(families.GapPremarketStrategy):
                wire_cancels = []

                def cancel_order(self, client_order_id):
                    self.wire_cancels.append(str(client_order_id))
                    return super().cancel_order(client_order_id)

                def on_data(self, data, state=state):
                    value = getattr(data, "data", data)
                    if isinstance(value, contracts.FactorSnapshot):
                        if state == "expired":
                            value = replace(value, valid_until_ns=start + 2_000_000_000)
                        elif value.ts_event >= start:
                            value = replace(value, halted=None)
                    return super().on_data(value)

            with self.subTest(state=state):
                strategy = run_strategy(
                    ledger=None,
                    faults=[],
                    strategy_type=UnknownProducer,
                    bids=("10", "11", "11", "11", "11", "11"),
                    advance_to_ns=start + 300_000_000 if state == "missing" else None,
                    overrides={
                        "entry_timeout_ns": 10_000_000_000,
                        "exit_deadline_ns": start + 20_000_000_000,
                    },
                )
                cancels = [
                    row for row in strategy.trace if row["event"] == "cancel_requested"
                ]
                self.assertEqual(
                    [row["now_ns"] for row in cancels],
                    [start + (300_000_000 if state == "missing" else 3_000_000_000)],
                )
                self.assertEqual(
                    strategy.wire_cancels, [strategy.client_id_prefix + "0000001"]
                )
                self.assertIsNone(strategy.pending)
                self.assertEqual(strategy.quantity, 0)
                self.assertFalse(strategy.faulted)
                self.assertFalse(strategy.callback_faults)

    def test_real_ledger_restart_rearms_original_notice_deadline_and_coalesces_overdue(
        self,
    ):
        start = simulation.BASE_NS
        for restart_offset in (100_000_000_000, 2000_000_000_000):
            with (
                self.subTest(restart_offset=restart_offset),
                tempfile.TemporaryDirectory() as directory,
            ):
                path = Path(directory) / "ledger.sqlite3"
                ledger = safety.Ledger(path)
                first = run_strategy(
                    ledger=ledger,
                    faults=[],
                    bids=("10", "10", "9", "8", "8"),
                    halt_after_ns=start + 3_000_000_000,
                    overrides={"exit_deadline_ns": start + 2_000_000_000},
                )
                original_id = str(first.pending.client_order_id)
                self.assertGreater(first.quantity, 0)
                # Seed the journal's position view from the native synthetic
                # fill. This is a persistence fixture, not a broker writer.
                with ledger._transaction():
                    ledger.db.execute(
                        "INSERT INTO positions VALUES (?,?,?)",
                        (
                            str(first.instrument_id.symbol),
                            str(first.quantity),
                            str(first.quantity * first.entry_price),
                        ),
                    )
                ledger.close()
                reopened = safety.Ledger(path)
                try:
                    due = (
                        start + 603_000_000_000
                        if restart_offset < 603_000_000_000
                        else start + restart_offset
                    )
                    next_due = due + 600_000_000_000
                    restart_faults = []
                    restarted = run_strategy(
                        ledger=reopened,
                        faults=restart_faults,
                        bids=("8",) * 3,
                        start_ns=start + restart_offset,
                        initial_snapshot_age_ns=0,
                        quote_offsets_ns=(
                            0,
                            due - start - restart_offset + 100_000_000,
                            next_due - start - restart_offset + 100_000_000,
                        ),
                        overrides={"exit_deadline_ns": start + 2_000_000_000},
                    )
                    notices = [
                        row
                        for row in restarted.trace
                        if row["event"] == "halt_hold_notice"
                    ]
                    self.assertEqual(
                        [row["now_ns"] for row in notices], [due, next_due]
                    )
                    self.assertTrue(
                        all(row["client_order_id"] == original_id for row in notices)
                    )
                    self.assertTrue(restarted.faulted)
                    startup_faults = [
                        "startup_held_notice_requires_reconciliation",
                        "startup_position_requires_reconciliation",
                    ]
                    if restart_offset >= 603_000_000_000:
                        # An overdue first delivery freezes the new actor
                        # before startup reconciliation, then sets the durable
                        # ledger halt. Later routine notices cannot repeat it.
                        startup_faults = [
                            "held_halted",
                            "startup_held_notice_requires_reconciliation",
                            "startup_ledger_halted_requires_reconciliation",
                            "startup_position_requires_reconciliation",
                        ]
                    self.assertEqual(restart_faults, startup_faults)
                    self.assertEqual(restarted.quantity, 0)  # No implicit adoption.
                    self.assertFalse(
                        [
                            row
                            for row in restarted.trace
                            if row["event"] in ("submit", "cancel_requested")
                        ]
                    )
                    self.assertFalse(restarted.callback_faults)
                finally:
                    reopened.close()

    def test_omitted_halt_field_remains_unknown_at_startup_and_while_held(self):
        start = simulation.BASE_NS
        for delivery in ("startup", "held"):

            class OmittedHalt(families.GapPremarketStrategy):
                def on_data(self, data, delivery=delivery):
                    value = getattr(data, "data", data)
                    if isinstance(value, contracts.FactorSnapshot) and (
                        delivery == "startup" or value.ts_event >= start
                    ):
                        payload = value.as_dict()
                        payload.pop("halted")
                        value = contracts.FactorSnapshot.from_json(payload)
                    return super().on_data(value)

            faults = []
            with self.subTest(delivery=delivery):
                strategy = run_strategy(
                    ledger=None,
                    faults=faults,
                    strategy_type=OmittedHalt,
                    bids=("10",) * 6,
                    advance_to_ns=start + 1_500_000_000 if delivery == "held" else None,
                    overrides={"exit_deadline_ns": start + 2_000_000_000},
                )
                self.assertEqual(
                    [row["side"] for row in strategy.trace if row["event"] == "submit"],
                    ["BUY"] if delivery == "held" else [],
                )
                if delivery == "held":
                    self.assertIn("held_halt_state_unknown", strategy.flags)
                    self.assertIn("held_halt_state_unknown", faults)
                    self.assertGreater(strategy.quantity, 0)
                self.assertFalse(strategy.callback_faults)

    def test_clock_leading_halted_snapshot_cancels_at_delivery(self):
        start = simulation.BASE_NS
        for lead in (1_000_000, 400_000_000):
            with self.subTest(lead_ns=lead), tempfile.TemporaryDirectory() as directory:
                observed = []

                class LeadingSnapshot(families.GapPremarketStrategy):
                    def on_data(self, data, lead=lead, observed=observed):
                        value = getattr(data, "data", data)
                        if isinstance(value, contracts.FactorSnapshot) and value.halted:
                            value = replace(value, ts_init=value.ts_init + lead)
                        result = super().on_data(value)
                        if isinstance(value, contracts.FactorSnapshot) and value.halted:
                            observed.append(
                                (
                                    self.clock.timestamp_ns(),
                                    self.snapshot.ts_init,
                                    self.snapshot_halted,
                                )
                            )
                        return result

                strategy = run_strategy(
                    ledger=safety.Ledger(Path(directory) / "ledger.json"),
                    faults=[],
                    strategy_type=LeadingSnapshot,
                    bids=("10", "10.04", "10.04", "10.04", *("9.99",) * 12),
                    quote_offsets_ns=(
                        0,
                        200_000_000,
                        400_000_000,
                        500_000_000,
                        *(600_000_000 + i * 100_000_000 for i in range(12)),
                    ),
                    halt_after_ns=start + 300_000_000,
                    reopen_at_ns=start + 500_000_000,
                    overrides={"entry_timeout_ns": 10_000_000_000},
                )
                cancels = [
                    row for row in strategy.trace if row["event"] == "cancel_requested"
                ]
                self.assertEqual(
                    [row["now_ns"] for row in cancels], [start + 300_000_000]
                )
                self.assertEqual(strategy.quantity, 0)
                self.assertIsNone(strategy.pending)
                self.assertFalse(strategy.callback_faults)
                self.assertEqual(
                    observed, [(start + 300_000_000, start - 600_000_000_000, True)]
                )

    def test_expired_halt_state_blocks_exit_and_notifies(self):
        start = simulation.BASE_NS

        class ExpiringState(families.GapPremarketStrategy):
            def on_data(self, data):
                value = getattr(data, "data", data)
                if isinstance(value, contracts.FactorSnapshot):
                    value = replace(value, valid_until_ns=start + 1_500_000_000)
                return super().on_data(value)

        faults = []
        with tempfile.TemporaryDirectory() as directory:
            strategy = run_strategy(
                ledger=safety.Ledger(Path(directory) / "ledger.json"),
                faults=faults,
                strategy_type=ExpiringState,
                bids=("10",) * 6,
                overrides={"exit_deadline_ns": start + 2_000_000_000},
            )
        submits = [row for row in strategy.trace if row["event"] == "submit"]
        self.assertEqual([row["side"] for row in submits], ["BUY"])
        self.assertGreater(strategy.quantity, 0)
        self.assertIn("held_halt_state_unknown", strategy.flags)
        self.assertIn("held_halt_state_unknown", faults)
        self.assertFalse(strategy.callback_faults)

    def test_raw_native_halt_stamps_fence_older_available_resumption(self):
        from nautilus_trader.model import InstrumentStatus, MarketStatusAction

        start = simulation.BASE_NS
        for stamp in ("event", "init"):
            for resume in (False, True):

                class LeadingStatus(families.GapPremarketStrategy):
                    def entry_condition(self, snapshot):
                        return self.clock.timestamp_ns() >= start + 600_000_000

                    def on_instrument_status(self, status, stamp=stamp):
                        if status.action == MarketStatusAction.HALT:
                            status = InstrumentStatus(
                                status.instrument_id,
                                status.action,
                                start + 700_000_000
                                if stamp == "event"
                                else status.ts_event,
                                start + 700_000_000
                                if stamp == "init"
                                else status.ts_init,
                            )
                        return super().on_instrument_status(status)

                statuses = [
                    (300_000_000, 300_000_000, "HALT", {}),
                    (500_000_000, 500_000_000, "TRADING", {}),
                ]
                if resume:
                    statuses.append((800_000_000, 800_000_000, "TRADING", {}))
                with self.subTest(stamp=stamp, resume=resume):
                    strategy = run_strategy(
                        ledger=None,
                        faults=[],
                        strategy_type=LeadingStatus,
                        bids=("10",) * 6,
                        quote_offsets_ns=(
                            0,
                            200_000_000,
                            600_000_000,
                            800_000_000,
                            1_000_000_000,
                            1_200_000_000,
                        ),
                        status_events=statuses,
                    )
                    buys = [
                        row
                        for row in strategy.trace
                        if row["event"] == "submit" and row["side"] == "BUY"
                    ]
                    self.assertEqual(len(buys), int(resume))
                    if resume:
                        self.assertGreaterEqual(buys[0]["now_ns"], start + 800_000_000)
                    self.assertIn(
                        "out_of_order",
                        [
                            row["reason"]
                            for row in strategy.trace
                            if row["event"] == "instrument_status_refused"
                        ],
                    )
                    self.assertFalse(strategy.callback_faults)

    def test_raw_snapshot_halt_stamps_fence_older_available_resumption(self):
        start = simulation.BASE_NS

        class LeadingSnapshot(families.GapPremarketStrategy):
            def entry_condition(self, snapshot):
                return self.clock.timestamp_ns() >= start + 600_000_000

            def on_data(self, data):
                value = getattr(data, "data", data)
                if isinstance(value, contracts.FactorSnapshot) and value.halted:
                    value = replace(
                        value, ts_event=start + 700_000_000, ts_init=start + 700_000_000
                    )
                return super().on_data(value)

        for resume in (False, True):
            with self.subTest(resume=resume):
                strategy = run_strategy(
                    ledger=None,
                    faults=[],
                    strategy_type=LeadingSnapshot,
                    bids=("10",) * 6,
                    quote_offsets_ns=(
                        0,
                        200_000_000,
                        600_000_000,
                        800_000_000,
                        1_000_000_000,
                        1_200_000_000,
                    ),
                    halt_after_ns=start + 300_000_000,
                    reopen_at_ns=start + 500_000_000,
                    advance_to_ns=start + 800_000_000 if resume else None,
                    overrides={"preset": "aggressive-v1"},
                )
                buys = [
                    row
                    for row in strategy.trace
                    if row["event"] == "submit" and row["side"] == "BUY"
                ]
                self.assertEqual(len(buys), int(resume))
                if resume:
                    self.assertGreaterEqual(buys[0]["now_ns"], start + 800_000_000)
                self.assertFalse(strategy.callback_faults)

    def test_submit_fence_blocks_every_order_role_with_expired_halt_state(self):
        start = simulation.BASE_NS
        for state, side in (
            (state, side)
            for state in ("missing", "expired")
            for side in (families.OrderSide.BUY, families.OrderSide.SELL)
        ):

            class DirectSubmit(families.GapPremarketStrategy):
                attempted = False

                def on_data(self, data, state=state):
                    value = getattr(data, "data", data)
                    if isinstance(value, contracts.FactorSnapshot):
                        if state == "missing":
                            return
                        value = replace(value, valid_until_ns=start + 1_500_000_000)
                    return super().on_data(value)

                def _drive(self):
                    # Isolate the final submit fence from watchdog/drive
                    # refusal, while retaining native order dispatch.
                    if self.clock.timestamp_ns() < start + 1_500_000_000:
                        return super()._drive()

                def on_quote(self, quote, side=side):
                    if self.clock.timestamp_ns() < start + 2_000_000_000:
                        return super().on_quote(quote)
                    if not self.attempted:
                        self.attempted = True
                        self._submit(
                            side,
                            contracts.decimal("1"),
                            contracts.decimal("10"),
                            "entry" if side == families.OrderSide.BUY else "exit",
                            "time_exit",
                        )

            with self.subTest(state=state, side=str(side)):
                strategy = run_strategy(
                    ledger=None,
                    faults=[],
                    strategy_type=DirectSubmit,
                    bids=("10",) * 6,
                    status_events=((1_500_000_000, 1_500_000_000, "TRADING", {}),),
                    overrides={"exit_deadline_ns": start + 7_000_000_000},
                )
                self.assertEqual(strategy.sequence, int(state == "expired"))
                self.assertEqual(
                    len([row for row in strategy.trace if row["event"] == "submit"]),
                    int(state == "expired"),
                )
                self.assertFalse(strategy.callback_faults)

    def test_working_exit_is_flagged_and_notified_every_ten_minutes(self):
        start = simulation.BASE_NS
        notices = []

        class ObserveHold(families.GapPremarketStrategy):
            def _record(self, event, **fields):
                super()._record(event, **fields)
                if event == "halt_hold_notice":
                    notices.append(
                        (
                            self.clock.timestamp_ns(),
                            self.pending.client_order_id,
                            self.quantity,
                            frozenset(self.flags),
                        )
                    )

        faults = []
        strategy = run_strategy(
            ledger=None,
            faults=faults,
            notice_sink=faults.append,
            strategy_type=ObserveHold,
            bids=("10", "10", "9", "8", "8", "8"),
            quote_offsets_ns=(
                0,
                1_000_000_000,
                2_000_000_000,
                2_200_000_000,
                602_500_000_000,
                1202_500_000_000,
            ),
            halt_after_ns=start + 2_300_000_000,
            overrides={"exit_deadline_ns": start + 2_000_000_000},
        )
        self.assertEqual(
            [row[0] for row in notices],
            [start + ns for ns in (2_300_000_000, 602_300_000_000, 1202_300_000_000)],
        )
        self.assertEqual(faults, ["held_halted"] * 3)
        self.assertTrue(
            all(row[1] == strategy.pending.client_order_id for row in notices)
        )
        self.assertTrue(all(row[2] > 0 and "held_halted" in row[3] for row in notices))
        self.assertEqual(strategy.sequence, 2)
        self.assertEqual(strategy.pending_role, "exit")
        self.assertFalse(
            [row for row in strategy.trace if row["event"] == "cancel_requested"]
        )
        self.assertFalse(strategy.faulted)
        self.assertFalse(strategy.callback_faults)

    def test_expired_halt_state_keeps_working_exit_and_notifies(self):
        start = simulation.BASE_NS
        observed = []

        class ExpiringState(families.GapPremarketStrategy):
            def on_data(self, data):
                value = getattr(data, "data", data)
                if isinstance(value, contracts.FactorSnapshot):
                    value = replace(value, valid_until_ns=start + 2_500_000_000)
                return super().on_data(value)

            def _record(self, event, **fields):
                super()._record(event, **fields)
                if event == "halt_hold_notice":
                    observed.append(
                        (self.clock.timestamp_ns(), self.pending.client_order_id)
                    )

        faults = []
        strategy = run_strategy(
            ledger=None,
            faults=faults,
            notice_sink=faults.append,
            strategy_type=ExpiringState,
            bids=("10", "10", "9", "8", "8", "8"),
            quote_offsets_ns=(
                0,
                1_000_000_000,
                2_000_000_000,
                3_000_000_000,
                603_000_000_000,
                1203_000_000_000,
            ),
            overrides={"exit_deadline_ns": start + 2_000_000_000},
        )
        self.assertEqual(
            [row[0] for row in observed],
            [start + seconds * 1_000_000_000 for seconds in (3, 603, 1203)],
        )
        self.assertEqual(faults, ["held_halt_state_unknown"] * 3)
        self.assertEqual(strategy.sequence, 2)
        self.assertEqual(strategy.pending_role, "exit")
        self.assertTrue(
            all(row[1] == strategy.pending.client_order_id for row in observed)
        )
        self.assertFalse(
            [row for row in strategy.trace if row["event"] == "cancel_requested"]
        )
        self.assertFalse(strategy.faulted)
        self.assertFalse(strategy.callback_faults)

    def test_halt_expiry_notification_freezes_before_another_drive(self):
        start = simulation.BASE_NS
        at_expiry = []

        class ExpiryCallback(families.GapPremarketStrategy):
            expired = False

            def _drive(self):
                if (
                    not self.expired
                    and self.clock.timestamp_ns() >= start + 5_000_000_000
                    and self.pending_role == "exit"
                ):
                    self.expired = True
                    # Inject the terminal callback, as the retained policy
                    # probe does. Venue-driven DAY expiry remains T15 work.
                    self.on_order_expired(
                        SimpleNamespace(client_order_id=self.pending.client_order_id)
                    )
                    at_expiry.append(
                        (self.faulted, self.quantity, frozenset(self.flags))
                    )
                return super()._drive()

        faults = []
        strategy = run_strategy(
            ledger=None,
            faults=faults,
            strategy_type=ExpiryCallback,
            bids=("10", "10", "9", "8", "8", "8", "8"),
            halt_after_ns=start + 3_000_000_000,
            overrides={"exit_deadline_ns": start + 2_000_000_000},
        )
        self.assertEqual(len(at_expiry), 1)
        self.assertTrue(at_expiry[0][0])
        self.assertGreater(at_expiry[0][1], 0)
        self.assertIn("held_halted", at_expiry[0][2])
        self.assertIn("halted_day_expiry_requires_handoff", at_expiry[0][2])
        self.assertIn("halted_day_expiry_requires_handoff", faults)
        self.assertEqual(strategy.sequence, 2)
        self.assertIsNone(strategy.pending)
        self.assertFalse(strategy.callback_faults)

    def test_unprocessed_halt_cancel_uses_entry_deadline_in_all_three_fill_windows(
        self,
    ):
        start = simulation.BASE_NS
        for window, timeout, reopen, fill, flagged, frozen in (
            (
                "before_deadline",
                2_000_000_000,
                1_500_000_000,
                1_550_000_000,
                False,
                False,
            ),
            (
                "deadline_before_freeze",
                2_000_000_000,
                2_200_000_000,
                2_250_000_000,
                True,
                False,
            ),
            ("after_freeze", 2_000_000_000, 2_400_000_000, 2_500_000_000, True, True),
        ):
            applied = []

            def sink(strategy, event, cutoff, applied=applied):
                applied.append(
                    (event.ts_event, cutoff, strategy.quantity, strategy.faulted)
                )

            with (
                self.subTest(window=window),
                patch.object(
                    families.FamilyStrategy,
                    "cancel_order",
                    new=lambda self, client_id: None,
                ),
            ):
                strategy = run_strategy(
                    ledger=None,
                    faults=[],
                    post_cutoff_fill_sink=sink,
                    bids=("10", "11", "11", "10", "10", "10"),
                    quote_offsets_ns=(
                        0,
                        200_000_000,
                        400_000_000,
                        fill,
                        fill + 200_000_000,
                        fill + 400_000_000,
                    ),
                    status_events=(
                        (300_000_000, 300_000_000, "HALT", {}),
                        (reopen, reopen, "TRADING", {}),
                    ),
                    overrides={
                        "entry_timeout_ns": timeout,
                        "exit_deadline_ns": start + 20_000_000_000,
                    },
                )
                self.assertEqual("post_cutoff_fill" in strategy.flags, flagged)
                self.assertEqual(strategy.faulted, frozen)
                self.assertEqual(
                    applied,
                    [(start + fill, start + timeout, contracts.decimal("7"), frozen)]
                    if flagged
                    else [],
                )
                sells = [
                    row
                    for row in strategy.trace
                    if row["event"] == "submit" and row["side"] == "SELL"
                ]
                self.assertEqual(bool(sells), flagged and not frozen)
                if sells:
                    self.assertEqual(sells[0]["reason"], "time_exit")
                    self.assertEqual(sells[0]["now_ns"], start + fill)
                freezes = [
                    row for row in strategy.trace if row["event"] == "safety_freeze"
                ]
                self.assertEqual(
                    [row["now_ns"] for row in freezes],
                    [start + 2_400_000_000] if frozen else [],
                )
                self.assertEqual(strategy.quantity == 0, flagged and not frozen)
                self.assertFalse(strategy.callback_faults)

    def test_clock_ahead_and_stale_native_halts_cancel_at_delivery(self):
        from nautilus_trader.model import InstrumentStatus, MarketStatusAction

        start = simulation.BASE_NS
        for lead, init_lead in (
            (-200_000_000, 0),
            (0, 0),
            (1_000_000, 0),
            (400_000_000, 0),
            (0, 400_000_000),
        ):

            class InitClockLeadStrategy(families.GapPremarketStrategy):
                def on_instrument_status(self, status):
                    if init_lead and status.action == MarketStatusAction.HALT:
                        # Native simulation schedules delivery by ts_init.
                        # Shift only the delivered event's init metadata at
                        # this callback seam to isolate host-clock lead.
                        status = InstrumentStatus(
                            status.instrument_id,
                            status.action,
                            status.ts_event,
                            status.ts_init + init_lead,
                        )
                    super().on_instrument_status(status)

            with self.subTest(event_lead_ns=lead, init_lead_ns=init_lead):
                strategy = run_strategy(
                    ledger=None,
                    faults=[],
                    strategy_type=InitClockLeadStrategy,
                    bids=("10", "11", "11", "10", "10", "10"),
                    quote_offsets_ns=(
                        0,
                        200_000_000,
                        400_000_000,
                        600_000_000,
                        800_000_000,
                        1_200_000_000,
                    ),
                    status_events=(
                        (200_000_000, 200_000_000, "TRADING", {}),
                        (300_000_000 + lead, 300_000_000, "HALT", {}),
                    ),
                    overrides={"entry_timeout_ns": 10_000_000_000},
                )
                cancels = [
                    row for row in strategy.trace if row["event"] == "cancel_requested"
                ]
                self.assertEqual(len(cancels), 1)
                self.assertEqual(cancels[0]["now_ns"], start + 300_000_000)
                self.assertEqual(cancels[0]["role"], "entry")
                self.assertTrue(
                    any(
                        row["event"] == "terminal"
                        and row["now_ns"] == start + 400_000_000
                        for row in strategy.trace
                    )
                )
                self.assertFalse(any(row["event"] == "fill" for row in strategy.trace))
                self.assertIsNone(strategy.pending)
                self.assertEqual(strategy.quantity, 0)
                self.assertEqual(strategy.sequence, 1)
                ahead = lead > 0 or init_lead > 0
                self.assertEqual("status_clock_ahead" in strategy.flags, ahead)
                leads = [
                    row
                    for row in strategy.trace
                    if row["event"] == "status_clock_ahead"
                ]
                self.assertEqual(len(leads), int(ahead))
                if ahead:
                    self.assertEqual(leads[0]["event_lead_ns"], max(0, lead))
                    self.assertEqual(leads[0]["init_lead_ns"], init_lead)

    def test_clock_ahead_halt_requires_available_ordered_resumption(self):
        class SignalAfterStatusStrategy(families.GapPremarketStrategy):
            def entry_condition(self, snapshot):
                return (
                    self.clock.timestamp_ns() >= simulation.BASE_NS + 600_000_000
                    and super().entry_condition(snapshot)
                )

        for halt_event, resumed in (
            (700_000_000, False),
            (700_000_000, True),
            (100_000_000, False),
            (100_000_000, True),
        ):
            statuses = [
                (200_000_000, 200_000_000, "TRADING", {}),
                (halt_event, 300_000_000, "HALT", {}),
                (900_000_000, 500_000_000, "TRADING", {}),
                (150_000_000, 600_000_000, "TRADING", {}),
            ]
            if resumed:
                statuses.append((800_000_000, 800_000_000, "TRADING", {}))
            with self.subTest(halt_event_ns=halt_event, resumed=resumed):
                strategy = run_strategy(
                    ledger=None,
                    faults=[],
                    strategy_type=SignalAfterStatusStrategy,
                    bids=("10",) * 6,
                    quote_offsets_ns=(
                        0,
                        200_000_000,
                        600_000_000,
                        1_000_000_000,
                        1_400_000_000,
                        1_800_000_000,
                    ),
                    status_events=statuses,
                    overrides={"preset": "aggressive-v1"},
                )
                buys = [
                    row
                    for row in strategy.trace
                    if row["event"] == "submit" and row["side"] == "BUY"
                ]
                self.assertEqual(len(buys), int(resumed))
                if resumed:
                    self.assertEqual(
                        buys[0]["now_ns"], simulation.BASE_NS + 800_000_000
                    )
                else:
                    self.assertEqual(strategy.quantity, 0)
                    self.assertEqual(strategy.sequence, 0)
                refusals = [
                    row["reason"]
                    for row in strategy.trace
                    if row["event"] == "instrument_status_refused"
                ]
                self.assertEqual(refusals, ["future_availability", "out_of_order"])

    def test_unsupported_session_names_block_entry_and_durably_hold_exit(self):
        for name in ("CLOSED", "OVERNIGHT"):

            def session_at(now):
                return SimpleNamespace(kind=SimpleNamespace(name=name))

            with (
                self.subTest(kind=name, scenario="entry"),
                patch.object(
                    families.FamilyStrategy, "_session", side_effect=session_at
                ),
            ):
                strategy = run_strategy(
                    ledger=None,
                    faults=[],
                    bids=("10",) * 6,
                    overrides={"preset": "aggressive-v1"},
                )
                self.assertFalse(
                    any(row["event"] == "submit" for row in strategy.trace)
                )
                self.assertEqual(strategy.sequence, 0)
                self.assertEqual(strategy.quantity, 0)

            def cross_session(now):
                if now >= simulation.BASE_NS + 3_000_000_000:
                    return session_at(now)
                return families._sessions.session_at(
                    datetime.fromtimestamp(now / 1e9, timezone.utc)
                )

            with (
                self.subTest(kind=name, scenario="held"),
                tempfile.TemporaryDirectory() as directory,
                patch.object(
                    families.FamilyStrategy, "_session", side_effect=cross_session
                ),
            ):
                ledger = safety.Ledger(Path(directory) / "unsupported-session.sqlite")
                faults = []
                try:
                    strategy = run_strategy(
                        ledger=ledger,
                        faults=faults,
                        bids=("10",) * 12,
                        overrides={
                            "preset": "aggressive-v1",
                            "exit_policy": "overnight-v1",
                            "exit_deadline_ns": simulation.BASE_NS + 8_000_000_000,
                        },
                    )
                    self.assertGreater(strategy.quantity, 0)
                    self.assertEqual(
                        ledger.halted_reason(), "closed_session_requires_handoff"
                    )
                    self.assertIn("closed_session_requires_handoff", faults)
                    self.assertFalse(
                        any(
                            row["event"] == "submit" and row["side"] == "SELL"
                            for row in strategy.trace
                        )
                    )
                finally:
                    ledger.close()

    def test_native_status_halt_cancels_pending_entry_before_reopen(self):
        start = simulation.BASE_NS
        native_cancel = families.FamilyStrategy.cancel_order
        observed = []

        def observe_cancel(strategy, client_id):
            observed.append((str(client_id), str(strategy.pending.client_order_id)))
            native_cancel(strategy, client_id)

        for action in (
            "HALT",
            "PAUSE",
            "SUSPEND",
            "QUOTING",
            "NOT_AVAILABLE_FOR_TRADING",
        ):
            observed.clear()
            with (
                self.subTest(action=action),
                patch.object(
                    families.FamilyStrategy, "cancel_order", new=observe_cancel
                ),
            ):
                strategy = run_strategy(
                    ledger=None,
                    faults=[],
                    bids=("10", "11", "11", "10", "10", "10"),
                    quote_offsets_ns=(
                        0,
                        200_000_000,
                        400_000_000,
                        600_000_000,
                        800_000_000,
                        1_200_000_000,
                    ),
                    status_events=(
                        (300_000_000, 300_000_000, action, {}),
                        (500_000_000, 500_000_000, "TRADING", {}),
                    ),
                    overrides={"entry_timeout_ns": 10_000_000_000},
                )
                buys = [
                    row
                    for row in strategy.trace
                    if row["event"] == "submit" and row["side"] == "BUY"
                ]
                self.assertEqual(len(buys), 1)
                original_id = buys[0]["client_order_id"]
                self.assertEqual(observed, [(original_id, original_id)])
                cancels = [
                    row for row in strategy.trace if row["event"] == "cancel_requested"
                ]
                self.assertEqual(len(cancels), 1)
                self.assertEqual(cancels[0]["now_ns"], start + 300_000_000)
                self.assertEqual(cancels[0]["role"], "entry")
                self.assertTrue(
                    any(
                        row["event"] == "terminal"
                        and row["now_ns"] == start + 400_000_000
                        for row in strategy.trace
                    )
                )
                self.assertFalse(any(row["event"] == "fill" for row in strategy.trace))
                self.assertIsNone(strategy.pending)
                self.assertEqual(strategy.quantity, 0)
                self.assertEqual(strategy.sequence, 1)

    def test_nonhalted_snapshot_does_not_clear_native_status_halt(self):
        class SignalAfterStatusStrategy(families.GapPremarketStrategy):
            def entry_condition(self, snapshot):
                return (
                    self.clock.timestamp_ns() >= simulation.BASE_NS + 600_000_000
                    and super().entry_condition(snapshot)
                )

        for resumed in (False, True):
            statuses = [(300_000_000, 300_000_000, "HALT", {})]
            if resumed:
                statuses.append((800_000_000, 800_000_000, "TRADING", {}))
            with self.subTest(resumed=resumed):
                strategy = run_strategy(
                    ledger=None,
                    faults=[],
                    strategy_type=SignalAfterStatusStrategy,
                    bids=("10",) * 6,
                    quote_offsets_ns=(
                        0,
                        200_000_000,
                        600_000_000,
                        1_000_000_000,
                        1_400_000_000,
                        1_800_000_000,
                    ),
                    reopen_at_ns=simulation.BASE_NS + 500_000_000,
                    status_events=statuses,
                    overrides={"preset": "aggressive-v1"},
                )
                buys = [
                    row
                    for row in strategy.trace
                    if row["event"] == "submit" and row["side"] == "BUY"
                ]
                self.assertEqual(len(buys), int(resumed))
                if resumed:
                    self.assertEqual(
                        buys[0]["now_ns"], simulation.BASE_NS + 800_000_000
                    )
                else:
                    self.assertEqual(strategy.quantity, 0)
                    self.assertEqual(strategy.sequence, 0)

    def test_native_resumption_does_not_clear_snapshot_halt(self):
        class SignalAfterStatusStrategy(families.GapPremarketStrategy):
            def entry_condition(self, snapshot):
                return (
                    self.clock.timestamp_ns() >= simulation.BASE_NS + 600_000_000
                    and super().entry_condition(snapshot)
                )

        for snapshot_resumed in (False, True):
            with self.subTest(snapshot_resumed=snapshot_resumed):
                strategy = run_strategy(
                    ledger=None,
                    faults=[],
                    strategy_type=SignalAfterStatusStrategy,
                    bids=("10",) * 6,
                    quote_offsets_ns=(
                        0,
                        200_000_000,
                        600_000_000,
                        1_000_000_000,
                        1_400_000_000,
                        1_800_000_000,
                    ),
                    halt_after_ns=simulation.BASE_NS + 300_000_000,
                    reopen_at_ns=simulation.BASE_NS + 800_000_000
                    if snapshot_resumed
                    else None,
                    status_events=(
                        (400_000_000, 400_000_000, "HALT", {"is_trading": False}),
                        (500_000_000, 500_000_000, "TRADING", {"is_trading": True}),
                    ),
                    overrides={"preset": "aggressive-v1"},
                )
                buys = [
                    row
                    for row in strategy.trace
                    if row["event"] == "submit" and row["side"] == "BUY"
                ]
                self.assertEqual(len(buys), int(snapshot_resumed))

    def test_explicit_nontrading_status_cancels_entry_without_halt_action(self):
        for action in ("NONE", "TRADING"):
            with self.subTest(action=action):
                strategy = run_strategy(
                    ledger=None,
                    faults=[],
                    bids=("10", "11", "11", "10", "10", "10"),
                    quote_offsets_ns=(
                        0,
                        200_000_000,
                        400_000_000,
                        600_000_000,
                        800_000_000,
                        1_200_000_000,
                    ),
                    status_events=(
                        (300_000_000, 300_000_000, action, {"is_trading": False}),
                        (500_000_000, 500_000_000, "TRADING", {"is_trading": True}),
                    ),
                    overrides={"entry_timeout_ns": 10_000_000_000},
                )
                cancels = [
                    row for row in strategy.trace if row["event"] == "cancel_requested"
                ]
                self.assertEqual(len(cancels), 1)
                self.assertEqual(cancels[0]["now_ns"], simulation.BASE_NS + 300_000_000)
                self.assertFalse(any(row["event"] == "fill" for row in strategy.trace))
                self.assertIsNone(strategy.pending)
                self.assertEqual(strategy.quantity, 0)
                self.assertEqual(strategy.sequence, 1)

    def test_native_resumption_requires_current_available_trading_status(self):
        class SignalAfterStatusStrategy(families.GapPremarketStrategy):
            def entry_condition(self, snapshot):
                return (
                    self.clock.timestamp_ns() >= simulation.BASE_NS + 600_000_000
                    and super().entry_condition(snapshot)
                )

        for event_ns, action, flags, refusal in (
            (200_000_000, "TRADING", {}, "out_of_order"),
            (900_000_000, "TRADING", {}, "future_availability"),
            (500_000_000, "NONE", {"is_trading": True}, None),
        ):
            for resumed in (False, True):
                statuses = [
                    (300_000_000, 300_000_000, "HALT", {}),
                    (event_ns, 500_000_000, action, flags),
                ]
                if resumed:
                    statuses.append((800_000_000, 800_000_000, "TRADING", {}))
                with self.subTest(event_ns=event_ns, action=action, resumed=resumed):
                    strategy = run_strategy(
                        ledger=None,
                        faults=[],
                        strategy_type=SignalAfterStatusStrategy,
                        bids=("10",) * 6,
                        quote_offsets_ns=(
                            0,
                            200_000_000,
                            600_000_000,
                            1_000_000_000,
                            1_400_000_000,
                            1_800_000_000,
                        ),
                        status_events=statuses,
                        overrides={"preset": "aggressive-v1"},
                    )
                    buys = [
                        row
                        for row in strategy.trace
                        if row["event"] == "submit" and row["side"] == "BUY"
                    ]
                    self.assertEqual(len(buys), int(resumed))
                    if resumed:
                        self.assertEqual(
                            buys[0]["now_ns"], simulation.BASE_NS + 800_000_000
                        )
                    else:
                        self.assertEqual(strategy.quantity, 0)
                        self.assertEqual(strategy.sequence, 0)
                    refusals = [
                        row["reason"]
                        for row in strategy.trace
                        if row["event"] == "instrument_status_refused"
                    ]
                    self.assertEqual(refusals, [refusal] if refusal is not None else [])

    def test_exit_deadline_refuses_new_entry_at_and_after_boundary(self):
        cutoff = simulation.BASE_NS + 2_000_000_000
        for offset in (-500_000_000, 0, 500_000_000):
            with self.subTest(offset_ns=offset):
                strategy = run_strategy(
                    ledger=None,
                    faults=[],
                    start_ns=cutoff + offset,
                    bids=("10", "11", "11", "11", "11"),
                    quote_offsets_ns=(
                        0,
                        200_000_000,
                        400_000_000,
                        600_000_000,
                        800_000_000,
                    ),
                    overrides={
                        "entry_deadline_ns": None,
                        "exit_policy": None,
                        "entry_timeout_ns": 10_000_000_000,
                        "exit_deadline_ns": cutoff,
                    },
                )
                buys = [
                    row
                    for row in strategy.trace
                    if row["event"] == "submit" and row["side"] == "BUY"
                ]
                self.assertEqual(len(buys), int(offset < 0))
                self.assertEqual(strategy.sequence, int(offset < 0))

    def test_development_startup_requires_durable_ledger_before_entry(self):
        # Synthetic data carries the development contract solely to exercise
        # native startup; these labels do not qualify any historical dataset.
        overrides = {
            "evidence_class": "development",
            "qualified_data": ("released_development", "horizon_qualified"),
            "exit_policy": "regular-close-v1",
            "exit_evidence_sha256": "f" * 64,
        }
        faults = []
        missing = run_strategy(
            ledger=None,
            faults=faults,
            overrides=overrides,
            post_cutoff_fill_sink=lambda strategy, event, cutoff: None,
        )
        self.assertTrue(missing.faulted)
        self.assertFalse(missing.enabled)
        self.assertEqual(faults, ["startup_durable_ledger_required"])
        self.assertIn("startup_durable_ledger_required", missing.flags)
        self.assertFalse(any(row["event"] == "submit" for row in missing.trace))
        self.assertEqual(missing.sequence, 0)

        with tempfile.TemporaryDirectory() as tmp:
            ledger = safety.Ledger(Path(tmp) / "development-startup.sqlite")
            try:
                with_ledger_faults = []
                supplied = run_strategy(
                    ledger=ledger,
                    faults=with_ledger_faults,
                    overrides=overrides,
                    post_cutoff_fill_sink=lambda strategy, event, cutoff: None,
                    notice_sink=lambda reason: None,
                )
                self.assertNotIn("startup_durable_ledger_required", supplied.flags)
                self.assertNotIn("startup_durable_ledger_required", with_ledger_faults)
                self.assertTrue(
                    any(
                        row["event"] == "submit" and row["side"] == "BUY"
                        for row in supplied.trace
                    )
                )
            finally:
                ledger.close()

    def test_development_startup_requires_post_cutoff_risk_sink(self):
        # Admission control only: synthetic factors carry development labels.
        # The separate post-cutoff test exercises actual same-callback accounting.
        with tempfile.TemporaryDirectory() as directory:
            ledger = safety.Ledger(Path(directory) / "risk-sink-startup.sqlite")
            try:
                faults = []
                strategy = run_strategy(
                    ledger=ledger,
                    faults=faults,
                    overrides={
                        "evidence_class": "development",
                        "qualified_data": ("released_development", "horizon_qualified"),
                        "exit_policy": "regular-close-v1",
                        "exit_evidence_sha256": "f" * 64,
                    },
                )
                self.assertTrue(strategy.faulted)
                self.assertFalse(strategy.enabled)
                self.assertEqual(faults, ["startup_post_cutoff_risk_sink_required"])
                self.assertFalse(
                    any(row["event"] == "submit" for row in strategy.trace)
                )
                self.assertEqual(strategy.sequence, 0)
            finally:
                ledger.close()

    def test_native_entry_denial_freezes_and_notifies_session(self):
        faults = []
        strategy = run_strategy(
            ledger=None,
            faults=faults,
            bids=("1000",) * 5,
            overrides={
                "position_cap_usd": "1000000",
                "cash_cap_usd": "1000000",
                "loss_cap_usd": "1000000",
                "max_quantity": 100,
            },
        )
        # The real cash venue has 10000 USD; this order exceeds its balance.
        self.assertTrue(
            any(row["event"] == "terminal" and row["refused"] for row in strategy.trace)
        )
        self.assertIn("native_order_refused_requires_handoff", strategy.flags)
        self.assertEqual(faults, ["native_order_refused_requires_handoff"])
        self.assertTrue(strategy.faulted)
        self.assertFalse(strategy.enabled)
        self.assertIsNone(strategy.pending)
        self.assertEqual(strategy.quantity, 0)
        self.assertEqual(strategy.sequence, 1)

    def test_late_native_alert_arm_immediately_cancels_expired_entry(self):
        class DelayedArmStrategy(families.GapPremarketStrategy):
            def _arm_pending_entry_alert(self):
                def finish_arm(event):
                    super(DelayedArmStrategy, self)._arm_pending_entry_alert()

                self.clock.set_time_alert_ns(
                    "test-delayed-entry-arm",
                    self.pending_since_ns + 400_000_000,
                    callback=finish_arm,
                )

        start = simulation.BASE_NS
        strategy = run_strategy(
            ledger=None,
            faults=[],
            strategy_type=DelayedArmStrategy,
            bids=("10", "11", "11", "11", "11"),
            quote_offsets_ns=(0, 200_000_000, 600_000_000, 800_000_000, 1_200_000_000),
            overrides={
                "entry_timeout_ns": 10_000_000_000,
                "exit_deadline_ns": start + 300_000_000,
            },
        )
        cancels = [row for row in strategy.trace if row["event"] == "cancel_requested"]
        self.assertEqual(len(cancels), 1)
        self.assertEqual(cancels[0]["now_ns"], start + 400_000_000)
        self.assertEqual(cancels[0]["role"], "entry")
        self.assertTrue(any(row["event"] == "terminal" for row in strategy.trace))
        self.assertFalse(any(row["event"] == "fill" for row in strategy.trace))
        self.assertIsNone(strategy.pending)
        self.assertEqual(strategy.sequence, 1)

    def test_delayed_native_fill_keeps_original_session_calendar_deadline(self):
        from nautilus_trader.model import OrderSide

        class NextSessionDeliveryStrategy(families.GapPremarketStrategy):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.delayed_fill = None
                self.first_fill_ns = None
                self.callback_ns = None

            def on_data(self, data):
                value = getattr(data, "data", data)
                if isinstance(value, contracts.FactorSnapshot):
                    # This fixture isolates the execution-time calendar
                    # anchor; keep its named synthetic halt state valid.
                    value = replace(
                        value, valid_until_ns=simulation.BASE_NS + 90000_000_000_000
                    )
                return super().on_data(value)

            def on_order_filled(self, event):
                if event.order_side == OrderSide.BUY and self.first_fill_ns is None:
                    self.first_fill_ns = event.ts_event
                    self.delayed_fill = event
                else:
                    super().on_order_filled(event)

            def _drive(self):
                # Withhold consumer processing solely to isolate the calendar
                # anchor; this does not qualify day-long live delivery latency.
                if self.delayed_fill is None:
                    super()._drive()

            def on_quote(self, quote):
                if (
                    self.delayed_fill is not None
                    and quote.ts_event >= simulation.BASE_NS + 86400_000_000_000
                ):
                    self.callback_ns = self.clock.timestamp_ns()
                    super().on_order_filled(self.delayed_fill)
                    self.delayed_fill = None
                super().on_quote(quote)

        strategy = run_strategy(
            ledger=None,
            faults=[],
            strategy_type=NextSessionDeliveryStrategy,
            bids=("10",) * 5,
            quote_offsets_ns=(
                0,
                1_000_000_000,
                86402_000_000_000,
                86403_000_000_000,
                86404_000_000_000,
            ),
            overrides={"exit_policy": "regular-close-v1", "exit_deadline_ns": None},
        )
        expected = int(
            datetime.fromisoformat("2026-10-08T19:58:00+00:00").timestamp() * 1e9
        )
        self.assertIsNotNone(strategy.first_fill_ns)
        self.assertGreater(strategy.callback_ns, expected)
        self.assertEqual(strategy.entered_ns, strategy.first_fill_ns)
        self.assertEqual(strategy.close_deadline_ns, expected)
        self.assertNotIn("post_cutoff_fill", strategy.flags)
        self.assertTrue(
            any(
                row["event"] == "submit" and row["reason"] == "time_exit"
                for row in strategy.trace
            )
        )
        self.assertEqual(strategy.quantity, 0)

    def test_fractional_policy_boundary_dispatches_cancel_before_crossing_quote(self):
        # Proves dispatch at the boundary. A fill matched before the cancel is
        # processed remains owned, accounted and exited; exclusion is not claimed.
        native_cancel = families.FamilyStrategy.cancel_order
        observed = []

        def observe_cancel(strategy, client_id):
            observed.append((str(client_id), str(strategy.pending.client_order_id)))
            native_cancel(strategy, client_id)

        for policy, boundary in (
            ("regular-close-v1", "2026-10-08T19:58:00+00:00"),
            ("after-hours-v1", "2026-10-08T23:58:00+00:00"),
        ):
            cutoff = int(datetime.fromisoformat(boundary).timestamp() * 1e9)
            start = cutoff - 500_000_000
            observed.clear()
            with (
                self.subTest(policy=policy),
                patch.object(
                    families.FamilyStrategy, "cancel_order", new=observe_cancel
                ),
            ):
                strategy = run_strategy(
                    ledger=None,
                    faults=[],
                    start_ns=start,
                    bids=("10", "11", "11", "10", "10", "10"),
                    quote_offsets_ns=(
                        0,
                        200_000_000,
                        400_000_000,
                        600_000_000,
                        800_000_000,
                        1_200_000_000,
                    ),
                    overrides={
                        "preset": "aggressive-v1",
                        "exit_policy": policy,
                        "entry_timeout_ns": 10_000_000_000,
                        "exit_deadline_ns": start + 30_000_000_000,
                    },
                )
                cancels = [
                    r for r in strategy.trace if r["event"] == "cancel_requested"
                ]
                buys = [
                    r
                    for r in strategy.trace
                    if r["event"] == "submit" and r["side"] == "BUY"
                ]
                self.assertEqual(len(cancels), 1)
                self.assertEqual(cancels[0]["now_ns"], cutoff)
                self.assertEqual(cancels[0]["role"], "entry")
                self.assertEqual(len(buys), 1)
                self.assertEqual(buys[0]["now_ns"], start)
                self.assertEqual(
                    observed, [(buys[0]["client_order_id"], buys[0]["client_order_id"])]
                )
                # Native cancel latency allows this crossing fill. Dispatch at
                # the boundary must retain fill ownership and the time exit.
                fills = [r for r in strategy.trace if r["event"] == "fill"]
                self.assertEqual([r["side"] for r in fills], ["BUY", "SELL"])
                self.assertEqual(fills[0]["now_ns"], cutoff + 100_000_000)
                self.assertIn("post_cutoff_fill", strategy.flags)
                exceptions = [
                    row for row in strategy.trace if row["event"] == "post_cutoff_fill"
                ]
                self.assertEqual(len(exceptions), 1)
                self.assertEqual(exceptions[0]["ts_event"], cutoff + 100_000_000)
                self.assertEqual(exceptions[0]["cutoff_ns"], cutoff)
                self.assertEqual(exceptions[0]["now_ns"], fills[0]["now_ns"])
                self.assertEqual(strategy.quantity, 0)
                self.assertIsNone(strategy.pending)
                self.assertEqual(strategy.sequence, 2)
                self.assertNotIn("t22-pending-entry", strategy.clock.timer_names())

    def test_subsecond_halt_cancels_on_acceptance_before_reopen_and_fill(self):
        start = simulation.BASE_NS
        native_terminal = families.FamilyStrategy.on_order_canceled
        retired = []

        def observe_terminal(strategy, event):
            native_terminal(strategy, event)
            retired.append((str(event.client_order_id), strategy.clock.timer_names()))

        with patch.object(
            families.FamilyStrategy, "on_order_canceled", new=observe_terminal
        ):
            strategy = run_strategy(
                ledger=None,
                faults=[],
                bids=("10", "11", "11", "10", "10", "10"),
                quote_offsets_ns=(
                    0,
                    200_000_000,
                    400_000_000,
                    600_000_000,
                    800_000_000,
                    1_200_000_000,
                ),
                halt_after_ns=start + 300_000_000,
                reopen_at_ns=start + 500_000_000,
                overrides={
                    "entry_timeout_ns": 10_000_000_000,
                    "exit_deadline_ns": start + 30_000_000_000,
                },
            )
        cancels = [r for r in strategy.trace if r["event"] == "cancel_requested"]
        terminals = [r for r in strategy.trace if r["event"] == "terminal"]
        self.assertEqual(len(cancels), 1)
        self.assertEqual(cancels[0]["now_ns"], start + 300_000_000)
        self.assertEqual(cancels[0]["role"], "entry")
        self.assertEqual(len(terminals), 1)
        self.assertEqual(terminals[0]["now_ns"], start + 400_000_000)
        self.assertFalse(any(r["event"] == "fill" for r in strategy.trace))
        self.assertEqual(strategy.quantity, 0)
        self.assertIsNone(strategy.pending)
        self.assertEqual(strategy.sequence, 1)
        self.assertNotIn("t22-pending-entry", strategy.clock.timer_names())
        self.assertEqual(len(retired), 1)
        self.assertEqual(retired[0][0], strategy.client_id_prefix + "0000001")
        self.assertNotIn("t22-pending-entry", retired[0][1])

    def test_post_cutoff_fill_updates_risk_state_in_native_callback(self):
        from nautilus_trader.model import OrderSide, Price

        cutoff = int(
            datetime.fromisoformat("2026-10-08T19:58:00+00:00").timestamp() * 1e9
        )
        start = cutoff - 500_000_000
        risk_state = {
            "gross_exposure_usd": contracts.decimal("0"),
            "daily_loss_usd": contracts.decimal("0"),
        }
        applied = []
        returned = []

        def apply_post_fill_account(strategy, event, cutoff_ns):
            # Declared one-instrument synthetic account producer. Its native
            # portfolio is updated by rc5 before this strategy fill callback.
            # The coming T14 consumer contract is risk.caps.post_cutoff_fill;
            # no implementation/binding is supplied here. Its actual writer
            # must supply all holdings, uncertain orders and frozen day anchors.
            mark = Price.from_str("10.0000")
            exposure = strategy.portfolio.net_exposure(strategy.instrument_id, mark)
            unrealized = strategy.portfolio.unrealized_pnl(strategy.instrument_id, mark)
            risk_state.update(
                gross_exposure_usd=exposure.as_decimal(),
                daily_loss_usd=max(contracts.decimal("0"), -unrealized.as_decimal()),
            )
            applied.append(
                (
                    str(event.client_order_id),
                    event.ts_event,
                    cutoff_ns,
                    strategy.clock.timestamp_ns(),
                    strategy.quantity,
                )
            )

        class ObservedRiskStrategy(families.GapPremarketStrategy):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.post_cutoff_fill_sink = apply_post_fill_account

            def on_order_filled(self, event):
                super().on_order_filled(event)
                if event.order_side == OrderSide.BUY:
                    returned.append(dict(risk_state))
                    # Native duplicate delivery must not apply the exception twice.
                    super().on_order_filled(event)

        strategy = run_strategy(
            ledger=None,
            faults=[],
            strategy_type=ObservedRiskStrategy,
            start_ns=start,
            bids=("10", "11", "11", "10", "10", "10"),
            quote_offsets_ns=(
                0,
                200_000_000,
                400_000_000,
                600_000_000,
                800_000_000,
                1_200_000_000,
            ),
            overrides={
                "preset": "aggressive-v1",
                "exit_policy": "regular-close-v1",
                "entry_timeout_ns": 10_000_000_000,
                "exit_deadline_ns": start + 30_000_000_000,
            },
        )
        self.assertEqual(
            returned,
            [
                {
                    "gross_exposure_usd": contracts.decimal("160"),
                    "daily_loss_usd": contracts.decimal("0.16"),
                }
            ],
        )
        self.assertEqual(
            applied,
            [
                (
                    strategy.client_id_prefix + "0000001",
                    cutoff + 100_000_000,
                    cutoff,
                    cutoff + 100_000_000,
                    contracts.decimal("16"),
                )
            ],
        )
        self.assertIn("post_cutoff_fill", strategy.flags)
        applied_events = [
            row for row in strategy.trace if row["event"] == "post_cutoff_risk_applied"
        ]
        self.assertEqual(len(applied_events), 1)
        self.assertEqual(applied_events[0]["now_ns"], cutoff + 100_000_000)
        self.assertEqual(strategy.quantity, 0)
        self.assertIsNone(strategy.pending)
        self.assertEqual(strategy.sequence, 2)
        self.assertEqual(strategy.callback_faults, [])

    def test_explicit_deadline_and_timeout_races_use_armed_cutoff(self):
        start = simulation.BASE_NS
        cutoff = start + 500_000_000
        for source in ("entry_deadline", "exit_deadline", "entry_timeout"):
            applied = []

            def observe_risk(strategy, event, cutoff_ns):
                applied.append(
                    (
                        event.ts_event,
                        cutoff_ns,
                        strategy.clock.timestamp_ns(),
                        str(event.client_order_id),
                        strategy.quantity,
                    )
                )

            with self.subTest(source=source):
                strategy = run_strategy(
                    ledger=None,
                    faults=[],
                    post_cutoff_fill_sink=observe_risk,
                    bids=("10", "11", "11", "10", "10", "10", "10"),
                    quote_offsets_ns=(
                        0,
                        200_000_000,
                        400_000_000,
                        600_000_000,
                        800_000_000,
                        1_000_000_000,
                        1_200_000_000,
                    ),
                    overrides={
                        "preset": "aggressive-v1",
                        "exit_policy": None,
                        "entry_deadline_ns": cutoff
                        if source == "entry_deadline"
                        else None,
                        "exit_deadline_ns": cutoff
                        if source == "exit_deadline"
                        else start + 900_000_000,
                        "entry_timeout_ns": 500_000_000
                        if source == "entry_timeout"
                        else 10_000_000_000,
                    },
                )
                self.assertIn("post_cutoff_fill", strategy.flags)
                self.assertEqual(
                    applied,
                    [
                        (
                            start + 600_000_000,
                            cutoff,
                            start + 600_000_000,
                            strategy.client_id_prefix + "0000001",
                            contracts.decimal("16"),
                        )
                    ],
                )
                cancels = [
                    row for row in strategy.trace if row["event"] == "cancel_requested"
                ]
                self.assertEqual(cancels[0]["now_ns"], cutoff)
                sells = [
                    row
                    for row in strategy.trace
                    if row["event"] == "submit" and row["side"] == "SELL"
                ]
                self.assertEqual(sells[0]["now_ns"], start + 600_000_000)
                self.assertEqual(sells[0]["reason"], "time_exit")
                self.assertEqual(strategy.quantity, 0)
                self.assertIsNone(strategy.pending)
                self.assertIsNone(strategy.pending_entry_deadline_ns)
                self.assertEqual(strategy.sequence, 2)
                self.assertEqual(strategy.callback_faults, [])

    def test_post_cutoff_classification_includes_exact_boundary_and_pins_missing_sink(
        self,
    ):
        from nautilus_trader.model import OrderSide

        start = simulation.BASE_NS
        cutoff = start + 500_000_000
        for fill_offset in (499_999_999, 500_000_000):
            with self.subTest(fill_offset_ns=fill_offset):
                callback_state = []

                class ObservedBoundaryStrategy(families.GapPremarketStrategy):
                    def on_order_filled(self, event):
                        super().on_order_filled(event)
                        if event.order_side == OrderSide.BUY:
                            callback_state.append((event.ts_event, set(self.flags)))

                strategy = run_strategy(
                    ledger=None,
                    faults=[],
                    strategy_type=ObservedBoundaryStrategy,
                    bids=("10", "11", "10", "10", "10", "10"),
                    quote_offsets_ns=(
                        0,
                        200_000_000,
                        fill_offset,
                        700_000_000,
                        900_000_000,
                        1_200_000_000,
                    ),
                    overrides={
                        "preset": "aggressive-v1",
                        "exit_policy": None,
                        "entry_deadline_ns": cutoff,
                        "entry_timeout_ns": 10_000_000_000,
                        "exit_deadline_ns": start + 800_000_000,
                    },
                )
                self.assertEqual(len(callback_state), 1)
                ts_event, flags = callback_state[0]
                self.assertEqual(ts_event, start + fill_offset)
                at_cutoff = fill_offset == 500_000_000
                self.assertEqual("post_cutoff_fill" in flags, at_cutoff)
                self.assertEqual(
                    "post_cutoff_risk_sink_unqualified" in flags, at_cutoff
                )
                self.assertEqual(strategy.quantity, 0)
                self.assertIsNone(strategy.pending)
                self.assertFalse(
                    any(
                        row["event"] == "post_cutoff_risk_applied"
                        for row in strategy.trace
                    )
                )

    def test_post_cutoff_risk_sink_cannot_defer_accounting(self):
        async def deferred_update():
            return None

        deferred = deferred_update()

        class DeferredRiskStrategy(families.GapPremarketStrategy):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.post_cutoff_fill_sink = lambda strategy, event, cutoff: deferred

        cutoff = int(
            datetime.fromisoformat("2026-10-08T19:58:00+00:00").timestamp() * 1e9
        )
        faults = []
        try:
            strategy = run_strategy(
                ledger=None,
                faults=faults,
                strategy_type=DeferredRiskStrategy,
                start_ns=cutoff - 500_000_000,
                bids=("10", "11", "11", "10", "10", "10"),
                quote_offsets_ns=(
                    0,
                    200_000_000,
                    400_000_000,
                    600_000_000,
                    800_000_000,
                    1_200_000_000,
                ),
                overrides={
                    "preset": "aggressive-v1",
                    "exit_policy": "regular-close-v1",
                    "entry_timeout_ns": 10_000_000_000,
                    "exit_deadline_ns": cutoff + 30_000_000_000,
                },
            )
            self.assertTrue(strategy.faulted)
            self.assertFalse(strategy.enabled)
            self.assertIn("post_cutoff_fill", strategy.flags)
            self.assertEqual(strategy.quantity, contracts.decimal("16"))
            self.assertIsNotNone(strategy.pending)
            self.assertEqual(
                str(strategy.pending.client_order_id),
                strategy.client_id_prefix + "0000001",
            )
            self.assertEqual(strategy.sequence, 1)
            self.assertTrue(faults)
            self.assertFalse(
                any(
                    row["event"] == "post_cutoff_risk_applied" for row in strategy.trace
                )
            )
        finally:
            deferred.close()

    def test_native_alert_selects_earliest_pending_entry_limit(self):
        start = simulation.BASE_NS
        for timeout, entry, exit_, earliest in (
            (300_000_000, 350_000_000, 450_000_000, 300_000_000),
            (450_000_000, 300_000_000, 350_000_000, 300_000_000),
            (350_000_000, 450_000_000, 300_000_000, 300_000_000),
        ):
            with self.subTest(timeout=timeout, entry=entry, exit=exit_):
                strategy = run_strategy(
                    ledger=None,
                    faults=[],
                    bids=("10", "11", "11", "10", "10", "10"),
                    quote_offsets_ns=(
                        0,
                        200_000_000,
                        400_000_000,
                        600_000_000,
                        800_000_000,
                        1_200_000_000,
                    ),
                    overrides={
                        "entry_timeout_ns": timeout,
                        "entry_deadline_ns": start + entry,
                        "exit_deadline_ns": start + exit_,
                    },
                )
                cancels = [
                    r for r in strategy.trace if r["event"] == "cancel_requested"
                ]
                self.assertEqual(len(cancels), 1)
                self.assertEqual(cancels[0]["now_ns"], start + earliest)
                self.assertEqual(cancels[0]["role"], "entry")
                self.assertTrue(any(r["event"] == "terminal" for r in strategy.trace))
                self.assertFalse(any(r["event"] == "fill" for r in strategy.trace))
                self.assertEqual(strategy.quantity, 0)
                self.assertEqual(strategy.sequence, 1)

    def test_entry_deadline_cancels_before_timeout_and_preserves_terminal_identity(
        self,
    ):
        start = simulation.BASE_NS
        native_cancel = families.FamilyStrategy.cancel_order
        observed = []

        def observe_cancel(strategy, client_id):
            observed.append((str(client_id), str(strategy.pending.client_order_id)))
            native_cancel(strategy, client_id)

        with patch.object(families.FamilyStrategy, "cancel_order", new=observe_cancel):
            strategy = run_strategy(
                ledger=None,
                faults=[],
                bids=("10", "11", "11", "10", "10", "10"),
                overrides={
                    "entry_deadline_ns": start + 1_000_000_000,
                    "entry_timeout_ns": 10_000_000_000,
                    "exit_deadline_ns": start + 30_000_000_000,
                },
            )
        cancels = [r for r in strategy.trace if r["event"] == "cancel_requested"]
        self.assertEqual(len(cancels), 1)
        self.assertEqual(cancels[0]["now_ns"], start + 1_000_000_000)
        self.assertEqual(cancels[0]["role"], "entry")
        self.assertEqual(observed, [(strategy.client_id_prefix + "0000001",) * 2])
        self.assertTrue(any(r["event"] == "terminal" for r in strategy.trace))
        self.assertFalse(any(r["event"] == "fill" for r in strategy.trace))
        self.assertIsNone(strategy.pending)
        self.assertEqual(strategy.quantity, 0)
        self.assertEqual(strategy.sequence, 1)

    def test_entry_deadline_admits_only_before_boundary(self):
        cutoff = simulation.BASE_NS + 2_000_000_000
        for offset in (-500_000_000, 0, 500_000_000):
            with self.subTest(offset_ns=offset):
                strategy = run_strategy(
                    ledger=None,
                    faults=[],
                    start_ns=cutoff + offset,
                    bids=("10", "11", "11", "11", "11"),
                    quote_offsets_ns=(
                        0,
                        200_000_000,
                        400_000_000,
                        600_000_000,
                        800_000_000,
                    ),
                    overrides={
                        "entry_deadline_ns": cutoff,
                        "entry_timeout_ns": 10_000_000_000,
                        "exit_deadline_ns": cutoff + 30_000_000_000,
                    },
                )
                buys = [
                    r
                    for r in strategy.trace
                    if r["event"] == "submit" and r["side"] == "BUY"
                ]
                self.assertEqual(len(buys), int(offset < 0))
                self.assertFalse(any(r["event"] == "fill" for r in strategy.trace))
                self.assertEqual(strategy.quantity, 0)

    def test_exit_deadline_cancels_pending_entry_before_ordinary_timeout(self):
        start = simulation.BASE_NS
        strategy = run_strategy(
            ledger=None,
            faults=[],
            bids=("10", "11", "11", "10", "10", "10"),
            overrides={
                "entry_timeout_ns": 10_000_000_000,
                "exit_deadline_ns": start + 1_000_000_000,
            },
        )
        cancels = [r for r in strategy.trace if r["event"] == "cancel_requested"]
        self.assertEqual(len(cancels), 1)
        self.assertEqual(cancels[0]["now_ns"], start + 1_000_000_000)
        self.assertEqual(cancels[0]["role"], "entry")
        self.assertFalse(any(r["event"] == "fill" for r in strategy.trace))
        self.assertTrue(any(r["event"] == "terminal" for r in strategy.trace))
        self.assertEqual(strategy.quantity, 0)
        self.assertEqual(strategy.sequence, 1)

    def test_exit_deadline_cancels_pending_exit_before_ordinary_timeout(self):
        start = simulation.BASE_NS
        strategy = run_strategy(
            ledger=None,
            faults=[],
            bids=("10", "10", "9", "8", "8", "9", "9"),
            overrides={
                "entry_timeout_ns": 10_000_000_000,
                "exit_timeout_ns": 10_000_000_000,
                "exit_deadline_ns": start + 3_000_000_000,
            },
        )
        cancels = [r for r in strategy.trace if r["event"] == "cancel_requested"]
        self.assertEqual(len(cancels), 1)
        self.assertEqual(cancels[0]["now_ns"], start + 3_000_000_000)
        self.assertEqual(cancels[0]["role"], "exit")
        sells = [
            r for r in strategy.trace if r["event"] == "submit" and r["side"] == "SELL"
        ]
        self.assertEqual([r["reason"] for r in sells], ["stop_loss", "time_exit"])
        self.assertEqual(strategy.quantity, 0)
        self.assertEqual(strategy.sequence, 3)

    def test_policy_boundary_refuses_new_entries_at_and_after_cutoff(self):
        for policy, boundary in (
            ("regular-close-v1", "2026-10-08T19:58:00+00:00"),
            ("after-hours-v1", "2026-10-08T23:58:00+00:00"),
        ):
            cutoff = int(datetime.fromisoformat(boundary).timestamp() * 1e9)
            for offset in (-2, 0, 60):
                start = cutoff + offset * 1_000_000_000
                with self.subTest(policy=policy, offset=offset):
                    strategy = run_strategy(
                        ledger=None,
                        faults=[],
                        start_ns=start,
                        bids=("10",) * 5,
                        overrides={
                            "preset": "aggressive-v1",
                            "exit_policy": policy,
                            "exit_deadline_ns": start + 30_000_000_000,
                        },
                    )
                    buys = [
                        r
                        for r in strategy.trace
                        if r["event"] == "submit" and r["side"] == "BUY"
                    ]
                    self.assertEqual(len(buys), int(offset < 0))

    def test_resting_entry_is_cancelled_at_selected_policy_boundary(self):
        for policy, boundary in (
            ("regular-close-v1", "2026-10-08T19:58:00+00:00"),
            ("after-hours-v1", "2026-10-08T23:58:00+00:00"),
        ):
            cutoff = int(datetime.fromisoformat(boundary).timestamp() * 1e9)
            start = cutoff - 1_000_000_000
            with self.subTest(policy=policy):
                strategy = run_strategy(
                    ledger=None,
                    faults=[],
                    start_ns=start,
                    bids=("10", "11", "11", "10", "10", "10"),
                    overrides={
                        "preset": "aggressive-v1",
                        "exit_policy": policy,
                        "entry_timeout_ns": 10_000_000_000,
                        "exit_deadline_ns": start + 30_000_000_000,
                    },
                )
                cancels = [
                    r for r in strategy.trace if r["event"] == "cancel_requested"
                ]
                self.assertEqual(len(cancels), 1)
                self.assertEqual(cancels[0]["now_ns"], cutoff)
                self.assertEqual(cancels[0]["role"], "entry")
                self.assertTrue(any(r["event"] == "terminal" for r in strategy.trace))
                self.assertFalse(any(r["event"] == "fill" for r in strategy.trace))
                self.assertEqual(strategy.quantity, 0)
                self.assertEqual(strategy.sequence, 1)

    def test_halt_cancels_entry_and_keeps_identity_until_native_terminal(self):
        native_cancel = families.FamilyStrategy.cancel_order
        observed = []

        def observe_cancel(strategy, client_id):
            native_cancel(strategy, client_id)
            observed.append(
                (
                    str(client_id),
                    str(strategy.pending.client_order_id),
                    strategy.cancel_requested,
                    strategy.clock.timestamp_ns(),
                )
            )

        with patch.object(families.FamilyStrategy, "cancel_order", new=observe_cancel):
            strategy = run_strategy(
                ledger=None,
                faults=[],
                bids=("10", "11", "11", "10", "10", "10"),
                halt_after_ns=simulation.BASE_NS + 1_000_000_000,
                reopen_at_ns=simulation.BASE_NS + 3_000_000_000,
                overrides={"entry_timeout_ns": 10_000_000_000},
            )
        self.assertEqual(len(observed), 1)
        client_id, pending_id, cancel_requested, cancelled_at = observed[0]
        self.assertEqual(client_id, pending_id)
        self.assertTrue(cancel_requested)
        self.assertEqual(cancelled_at, simulation.BASE_NS + 1_000_000_000)
        self.assertTrue(any(r["event"] == "terminal" for r in strategy.trace))
        self.assertFalse(any(r["event"] == "fill" for r in strategy.trace))
        self.assertIsNone(strategy.pending)
        self.assertEqual(strategy.sequence, 1)

    def test_halt_cancel_without_ack_retains_original_entry_identity(self):
        requested = []

        def drop_cancel_ack(strategy, client_id):
            requested.append((str(client_id), strategy.clock.timestamp_ns()))

        with patch.object(families.FamilyStrategy, "cancel_order", new=drop_cancel_ack):
            faults = []
            strategy = run_strategy(
                ledger=None,
                faults=faults,
                bids=("10",) + ("11",) * 7,
                halt_after_ns=simulation.BASE_NS + 1_000_000_000,
            )
        self.assertEqual(
            requested,
            [
                (
                    strategy.client_id_prefix + "0000001",
                    simulation.BASE_NS + 1_000_000_000,
                )
            ],
        )
        self.assertEqual(str(strategy.pending.client_order_id), requested[0][0])
        self.assertEqual(strategy.sequence, 1)
        self.assertEqual(faults, ["cancel_ack_timeout_requires_reconciliation"])
        self.assertTrue(strategy.faulted)

    def test_halt_does_not_apply_entry_cancellation_to_pending_exit(self):
        faults = []
        strategy = run_strategy(
            ledger=None,
            faults=faults,
            bids=("10", "10", "9", "8", "8", "8", "10", "10"),
            halt_after_ns=simulation.BASE_NS + 3_000_000_000,
            reopen_at_ns=simulation.BASE_NS + 6_000_000_000,
            overrides={"exit_deadline_ns": simulation.BASE_NS + 2_000_000_000},
        )
        sells = [
            r for r in strategy.trace if r["event"] == "submit" and r["side"] == "SELL"
        ]
        self.assertEqual(len(sells), 1)
        self.assertEqual(sells[0]["now_ns"], simulation.BASE_NS + 2_000_000_000)
        self.assertFalse(any(r["event"] == "cancel_requested" for r in strategy.trace))
        self.assertEqual(strategy.quantity, 0)
        self.assertEqual(strategy.sequence, 2)
        self.assertEqual(faults, [])

    def test_delayed_first_buy_callback_uses_native_fill_event_time(self):
        from nautilus_trader.model import OrderSide

        class DelayedFillStrategy(families.GapPremarketStrategy):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.delayed_fill = None
                self.first_fill_ns = None
                self.callback_ns = None

            def on_order_filled(self, event):
                if event.order_side == OrderSide.BUY and self.first_fill_ns is None:
                    self.first_fill_ns = event.ts_event
                    self.delayed_fill = event
                else:
                    super().on_order_filled(event)

            def on_quote(self, quote):
                if (
                    self.delayed_fill is not None
                    and quote.ts_event >= self.first_fill_ns + 2_000_000_000
                ):
                    self.callback_ns = self.clock.timestamp_ns()
                    super().on_order_filled(self.delayed_fill)
                    self.delayed_fill = None
                super().on_quote(quote)

        strategy = run_strategy(
            ledger=None,
            faults=[],
            bids=("10",) * 12,
            strategy_type=DelayedFillStrategy,
            overrides={"entry_timeout_ns": 10_000_000_000},
        )
        self.assertIsNotNone(strategy.first_fill_ns)
        self.assertGreater(strategy.callback_ns, strategy.first_fill_ns)
        self.assertEqual(strategy.entered_ns, strategy.first_fill_ns)
        self.assertEqual(
            strategy.close_deadline_ns,
            strategy._holding_deadline(strategy.first_fill_ns),
        )
        self.assertEqual(strategy.quantity, 0)
        self.assertFalse(strategy.faulted)

    def test_session_is_notified_even_when_durable_freeze_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = safety.Ledger(Path(directory) / "ledger.sqlite3")
            faults = []
            try:
                ledger.start_trial(simulation.BASE_NS / 1e9)
                with patch.object(
                    ledger,
                    "freeze",
                    side_effect=RuntimeError("synthetic_journal_failure"),
                ):
                    strategy = run_strategy(
                        ledger=ledger,
                        faults=faults,
                        overrides={"execution_profile": "native-target-v1"},
                    )
                self.assertEqual(faults, ["T15_native_order_capability_unqualified"])
                self.assertTrue(strategy.faulted)
                self.assertEqual(
                    strategy.callback_faults[0]["freeze_error"], "RuntimeError"
                )
                self.assertEqual(
                    ledger.halted_reason(), None
                )  # no false durability claim
                self.assertFalse(any(r["event"] == "submit" for r in strategy.trace))
            finally:
                ledger.close()

    def test_live_node_fixtures_do_not_depend_on_weekend_wall_clock(self):
        legacy = importlib.import_module("tests.test_us_equities_strategies")
        # Saturday noon UTC. Only the fixture module's old wall-time access is
        # replaced; the native engine and asyncio scheduler remain real.
        weekend_ns = 1791633600_000_000_000
        fixed_wall = SimpleNamespace(
            time=lambda: weekend_ns / 1e9,
            time_ns=lambda: weekend_ns,
            monotonic=time.monotonic,
        )
        for name in (
            "test_ambiguous_LiveNode_submit_journals_id_then_restart_sends_nothing",
            "test_same_family_classes_use_real_LiveNode_and_owned_partial_fills",
        ):
            with self.subTest(fixture=name), patch.object(legacy, "time", fixed_wall):
                case = legacy.NativeStrategyTests(name)
                getattr(case, name)()

    def test_unacknowledged_cancel_times_out_without_new_id(self):
        requested = []

        def drop_cancel_ack(strategy, client_id):
            requested.append((str(client_id), strategy.clock.timestamp_ns()))

        with tempfile.TemporaryDirectory() as directory:
            ledger = safety.Ledger(Path(directory) / "ledger.sqlite3")
            faults = []
            try:
                ledger.start_trial(simulation.BASE_NS / 1e9)
                with patch.object(
                    families.FamilyStrategy, "cancel_order", new=drop_cancel_ack
                ):
                    strategy = run_strategy(
                        ledger=ledger, faults=faults, bids=("10",) + ("11",) * 11
                    )
                self.assertEqual(
                    ledger.halted_reason(), "cancel_ack_timeout_requires_reconciliation"
                )
                self.assertEqual(faults, ["cancel_ack_timeout_requires_reconciliation"])
                self.assertEqual(len(requested), 1)
                self.assertEqual(strategy.sequence, 1)
                freezes = [r for r in strategy.trace if r["event"] == "safety_freeze"]
                self.assertEqual(freezes[0]["now_ns"], requested[0][1] + 2_000_000_000)
            finally:
                ledger.close()

    def test_terminal_entry_is_consumed_without_other_startup_refusal(self):
        spec = contracts.StrategySpec(
            simulation.INSTRUMENT_ID, simulation.COHORT_SHA256
        )
        seed = families.GapPremarketStrategy(spec)
        client_id = seed.client_id_prefix + "0000001"
        now = simulation.BASE_NS / 1e9
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.sqlite3"
            ledger = safety.Ledger(path)
            try:
                ledger.start_trial(now)
                ledger.reserve_intent(
                    client_id,
                    "TST",
                    "buy",
                    "1",
                    "10.03",
                    quote=safety.Quote("TST", "10", "10.01", now),
                    now=now,
                    market_open=True,
                    session_close=now + 3600,
                    stop_file=Path(directory) / "unused-stop-fixture",
                )
                ledger.mark_not_sent(client_id, "synthetic_pre_wire_refusal")
            finally:
                ledger.close()
            ledger = safety.Ledger(path)
            faults = []
            try:
                self.assertEqual(ledger.halted_reason(), None)
                self.assertEqual(ledger.unresolved(), [])
                self.assertEqual(ledger.positions(), {})
                strategy = run_strategy(ledger=ledger, faults=faults, bids=("10",) * 12)
                self.assertEqual(strategy.sequence, 1)  # far below exhaustion
                self.assertFalse(strategy.faulted)
                self.assertEqual(faults, [])
                self.assertIn("prior_entry_attempt_restored", strategy.flags)
                self.assertFalse(any(r["event"] == "submit" for r in strategy.trace))
                # Only the explicitly new trial identity changes. Its positive
                # entry proves no other silent refusal made the first pass.
                control = run_strategy(
                    ledger=ledger,
                    faults=[],
                    bids=("10",) * 12,
                    overrides={"instance_id": "new_trial"},
                )
                self.assertTrue(
                    any(
                        r["event"] == "submit" and r["side"] == "BUY"
                        for r in control.trace
                    )
                )
            finally:
                ledger.close()

    def test_native_cancel_rejection_escalates_without_replacement(self):
        from nautilus_trader.core import UUID4
        from nautilus_trader.model import OrderCancelRejected, TraderId

        observed = []

        def reject_cancel(strategy, client_id):
            event = OrderCancelRejected(
                trader_id=TraderId("TRADER-001"),
                strategy_id=strategy.strategy_id,
                instrument_id=strategy.instrument_id,
                client_order_id=client_id,
                reason="synthetic_cancel_refusal",
                event_id=UUID4(),
                ts_event=strategy.clock.timestamp_ns(),
                ts_init=strategy.clock.timestamp_ns(),
                reconciliation=False,
            )
            handler = getattr(strategy, "on_order_cancel_rejected", None)
            if handler is not None:
                handler(event)
            observed.append((str(client_id), strategy.pending is not None))

        with tempfile.TemporaryDirectory() as directory:
            ledger = safety.Ledger(Path(directory) / "ledger.sqlite3")
            faults = []
            try:
                ledger.start_trial(simulation.BASE_NS / 1e9)
                with patch.object(
                    families.FamilyStrategy, "cancel_order", new=reject_cancel
                ):
                    strategy = run_strategy(
                        ledger=ledger, faults=faults, bids=("10",) + ("11",) * 11
                    )
                self.assertEqual(
                    ledger.halted_reason(),
                    "native_cancel_rejected_requires_reconciliation",
                )
                self.assertEqual(
                    faults, ["native_cancel_rejected_requires_reconciliation"]
                )
                self.assertEqual(
                    observed, [(strategy.client_id_prefix + "0000001", True)]
                )
                self.assertEqual(strategy.sequence, 1)
            finally:
                ledger.close()

    def test_restart_never_enters_when_durable_halt_exists_without_exposure(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.sqlite3"
            ledger = safety.Ledger(path)
            ledger.start_trial(simulation.BASE_NS / 1e9)
            ledger.freeze("prior_safety_halt")
            ledger.close()
            reopened = safety.Ledger(path)
            faults = []
            try:
                self.assertEqual(reopened.unresolved(), [])
                self.assertEqual(reopened.positions(), {})
                strategy = run_strategy(
                    ledger=reopened, faults=faults, bids=("10",) * 12
                )
                self.assertFalse(any(r["event"] == "submit" for r in strategy.trace))
                self.assertIn("startup_ledger_halted_requires_reconciliation", faults)
                self.assertEqual(reopened.halted_reason(), "prior_safety_halt")
            finally:
                reopened.close()

    def test_held_hazards_persist_and_escalate_without_new_exit(self):
        from datetime import datetime, timezone

        closed = int(
            datetime(2026, 10, 8, 23, 59, 58, tzinfo=timezone.utc).timestamp() * 1e9
        )
        cases = (
            (
                "held_quote_stale",
                {
                    "bids": ("10", "10"),
                    "advance_to_ns": simulation.BASE_NS + 12_000_000_000,
                },
            ),
            (
                "held_halted",
                {
                    "bids": ("10",) * 12,
                    "halt_after_ns": simulation.BASE_NS + 3_000_000_000,
                },
            ),
            (
                "closed_session_requires_handoff",
                {
                    "bids": ("10",) * 12,
                    "start_ns": closed,
                    "overrides": {
                        "preset": "aggressive-v1",
                        "exit_policy": "overnight-v1",
                    },
                },
            ),
            (
                "exit_budget_exhausted_requires_handoff",
                {
                    "bids": (
                        "10",
                        "10",
                        "10",
                        "10",
                        "9",
                        "8",
                        "7",
                        "6",
                        "5",
                        "4",
                        "3",
                        "2",
                    ),
                    "overrides": {
                        "max_exit_orders": 1,
                        "exit_deadline_ns": simulation.BASE_NS + 3_000_000_000,
                    },
                },
            ),
        )
        for reason, kwargs in cases:
            with (
                self.subTest(reason=reason),
                tempfile.TemporaryDirectory() as directory,
            ):
                path = Path(directory) / "ledger.sqlite3"
                ledger = safety.Ledger(path)
                faults = []
                try:
                    ledger.start_trial(simulation.BASE_NS / 1e9)
                    if reason == "closed_session_requires_handoff":
                        legacy = importlib.import_module(
                            "tests.test_us_equities_strategies"
                        )
                        context = legacy.synthetic_overnight_session_context()
                    else:
                        context = nullcontext()
                    with context:
                        strategy = run_strategy(ledger=ledger, faults=faults, **kwargs)
                    self.assertGreater(strategy.quantity, 0)
                    self.assertEqual(ledger.halted_reason(), reason)
                    self.assertIn(reason, faults)
                    sells = [
                        r
                        for r in strategy.trace
                        if r["event"] == "submit" and r["side"] == "SELL"
                    ]
                    self.assertEqual(
                        len(sells),
                        1 if reason == "exit_budget_exhausted_requires_handoff" else 0,
                    )
                finally:
                    ledger.close()
                reopened = safety.Ledger(path)
                try:
                    self.assertEqual(reopened.halted_reason(), reason)
                finally:
                    reopened.close()

    def test_missing_instrument_startup_escalates_and_survives_ledger_reopen(self):
        faults = []
        factory = simulation.fixture_engine

        def missing_instrument(_=None):
            engine, instrument = factory()
            # The actor declares a different valid identifier. Do not register
            # it, so the actual native startup cache lookup is the refusal seam.
            return engine, instrument

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.sqlite3"
            ledger = safety.Ledger(path)
            try:
                ledger.start_trial(simulation.BASE_NS / 1e9)
                from nautilus_trader.model import CustomData

                engine, _ = missing_instrument()
                spec = contracts.StrategySpec(
                    "MISSING.ALPACA", simulation.COHORT_SHA256
                )
                strategy = families.GapPremarketStrategy(
                    spec, ledger=ledger, fault_sink=faults.append
                )
                try:
                    engine.add_strategy(strategy)
                    engine.add_data(
                        [
                            CustomData(
                                families.snapshot_data_type(simulation.INSTRUMENT_ID),
                                simulation.fixture_snapshot(),
                            )
                        ]
                    )
                    try:
                        engine.run()
                    except (ValueError, RuntimeError):
                        # rc5 may propagate startup errors; neither logging nor
                        # raising by itself supplies the durable/session signal.
                        pass
                    self.assertEqual(faults, ["startup_instrument_not_registered"])
                    self.assertEqual(
                        ledger.halted_reason(), "startup_instrument_not_registered"
                    )
                finally:
                    engine.dispose()
            finally:
                ledger.close()
            reopened = safety.Ledger(path)
            try:
                self.assertEqual(
                    reopened.halted_reason(), "startup_instrument_not_registered"
                )
            finally:
                reopened.close()

    def test_non_equity_freeze_is_durable_and_escalates_to_session(self):
        from nautilus_trader.model import (
            Currency,
            CurrencyPair,
            InstrumentId,
            Price,
            Quantity,
            Symbol,
        )

        non_equity = CurrencyPair(
            instrument_id=InstrumentId.from_str(simulation.INSTRUMENT_ID),
            raw_symbol=Symbol("TST"),
            base_currency=Currency.from_str("EUR"),
            quote_currency=Currency.from_str("USD"),
            price_precision=4,
            size_precision=0,
            price_increment=Price.from_str("0.0001"),
            size_increment=Quantity.from_int(1),
            lot_size=Quantity.from_int(1),
            ts_event=0,
            ts_init=0,
        )
        faults = []
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.sqlite3"
            ledger = safety.Ledger(path)
            try:
                ledger.start_trial(simulation.BASE_NS / 1e9)
                strategy = run_strategy(
                    ledger=ledger, faults=faults, instrument=non_equity
                )
                self.assertTrue(strategy.faulted)
                self.assertEqual(ledger.halted_reason(), "equity_instrument_required")
                self.assertEqual(faults, ["equity_instrument_required"])
                self.assertFalse(any(r["event"] == "submit" for r in strategy.trace))
            finally:
                ledger.close()
            reopened = safety.Ledger(path)
            try:
                self.assertEqual(reopened.halted_reason(), "equity_instrument_required")
            finally:
                reopened.close()

    def test_forced_exit_rests_until_timeout_and_fills_once(self):
        result = simulation.run_case(
            "gap_premarket",
            bids=("10",) * 12,
            spec_overrides={
                "exit_deadline_ns": simulation.BASE_NS + 5_000_000_000,
                "exit_timeout_ns": 4_000_000_000,
            },
        )
        sells = [
            r for r in result["trace"] if r["event"] == "submit" and r["side"] == "SELL"
        ]
        self.assertEqual(len(sells), 1, result)
        early_cancels = [
            r
            for r in result["trace"]
            if r["event"] == "cancel_requested"
            and r["role"] == "exit"
            and r["now_ns"] < sells[0]["now_ns"] + 4_000_000_000
        ]
        self.assertEqual(early_cancels, [], result)
        self.assertEqual(result["owned_quantity"], "0", result)
        self.assertEqual(result["callback_faults"], [])


if __name__ == "__main__":
    unittest.main()
