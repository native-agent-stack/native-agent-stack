"""Pre-merge F1-F4 guard pins: CI protocol fixtures plus a production native emitter."""
import ast
import asyncio
from datetime import datetime, timezone
from decimal import Decimal
import importlib
import io
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

SOURCE = Path(__file__).resolve().parents[1] / "blueprints/us-equities/adaptive-paper"
sys.path.insert(0, str(SOURCE))
try:
    from . import test_adaptive_paper_overnight_arming as arming_tests
    from .test_adaptive_paper_overnight_guard_mutations import delete_in_definition
except ImportError:
    import test_adaptive_paper_overnight_arming as arming_tests
    from test_adaptive_paper_overnight_guard_mutations import delete_in_definition


def method_source(filename, qualified):
    node = ast.parse((SOURCE / filename).read_text())
    for part in qualified.split("."):
        node = next(n for n in node.body if getattr(n, "name", None) == part)
    return node


class OvernightGuardPins(unittest.TestCase):
    def pre_controller(self):
        from runner import _controller_session
        c, clock, _, _, _ = arming_tests.OvernightArming._controller(self, held=True,
            now=datetime(2026, 3, 11, 7, 49, tzinfo=timezone.utc).timestamp())
        clock[0] = datetime(2026, 3, 11, 8, 0, 1, tzinfo=timezone.utc).timestamp()
        c.close, c.market_open = _controller_session(clock[0], clock[0],
            {"extended_hours": True, "overnight_enabled": True, "flatten_minutes_before_pre": 10})
        c.quote({"symbol": "SPY", "bid": "10", "ask": "10.01", "ts_ns": int(clock[0] * 1e9)})
        c.trading_status({"symbol": "SPY", "source": "alpaca_assets", "ts_ns": int(clock[0] * 1e9),
                         "overnight_tradable": False, "overnight_halted": False,
                         "tradable": True, "asset_status": "active"})
        return c, clock

    def order(self, **changes):
        return {"client_order_id": "pin-exit", "symbol": "SPY", "side": "sell", "qty": "1",
                "limit_price": "10", "type": "limit", "time_in_force": "day",
                "extended_hours": True, "reduce_only": True, **changes}

    def rejection(self):
        node = method_source("native_adapter.py", "NativeOrderRejected")
        scope = {}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])), "<native-rejection>", "exec"), scope)
        return patch.dict(sys.modules, {"native_adapter": SimpleNamespace(NativeOrderRejected=scope["NativeOrderRejected"])})

    def assert_refusal(self, fn, reason):
        try:
            fn()
        except Exception as error:
            self.assertEqual(str(error), reason)
        else:
            self.fail("guard admitted an unauthorized entry/exit")

    def test_production_mover_emitter_sets_reduce_only_on_overnight_exits(self):
        node = method_source("mover_strategy.py", "MoverStrategy._execute")
        scope = {"ClientOrderId": str, "InstrumentId": SimpleNamespace(from_str=str),
                 "OrderSide": SimpleNamespace(BUY="buy", SELL="sell"),
                 "Quantity": SimpleNamespace(from_int=int), "Price": SimpleNamespace(from_str=str),
                 "TimeInForce": SimpleNamespace(DAY="day"), "price_text": str}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])), "<production-mover-emitter>", "exec"), scope)
        for enabled, side, expected in ((True, "sell", True), (True, "buy", False), (False, "sell", False)):
            with self.subTest(enabled=enabled, side=side):
                factory = Mock(side_effect=lambda *args, **kwargs: SimpleNamespace(
                    is_reduce_only=kwargs.get("reduce_only", False), side=args[1]))
                owner = SimpleNamespace(faulted=False, overnight_enabled=enabled,
                    order_factory=SimpleNamespace(limit=factory), submitted=0, submit_order=Mock(),
                    book=SimpleNamespace(plan=SimpleNamespace(exit_rule="X2")))
                record = SimpleNamespace(symbol="SPY", side=side, qty=1, limit_price=Decimal("10"),
                                         client_id="pin-order", reason="owned_residual_exit")
                scope["_execute"](owner, [SimpleNamespace(kind="submit", record=record)])
                self.assertIs(owner.submit_order.call_args.args[0].is_reduce_only, expected)
                self.assertEqual(owner.submitted, 1)

    def test_adaptive_exit_factories_set_reduce_only(self):
        # Execute each production call's optional-keyword expression, which is
        # independent of the native ABI and still distinguishes entry/legacy paths.
        for qualified in ("AdaptiveStrategy._rebalance", "AdaptiveStrategy._submit_replacement_exit"):
            node = method_source("native_strategy.py", qualified)
            calls = [n for n in ast.walk(node) if isinstance(n, ast.Call)
                     and isinstance(n.func, ast.Attribute) and n.func.attr == "limit"]
            self.assertEqual(len(calls), 1)
            for enabled in (True, False):
                scope = {"self": SimpleNamespace(transport=SimpleNamespace(overnight_enabled=enabled)), "side": "sell"}
                options = {}
                for kw in calls[0].keywords:
                    if kw.arg is None:
                        options.update(eval(compile(ast.Expression(kw.value), "<production-adaptive-keywords>", "eval"), scope))
                self.assertEqual(options.get("reduce_only", False), enabled)

    def test_recovery_preflight_permits_pre_rth_post_but_entries_do_not(self):
        import runner
        for hour in (8, 14, 21):
            with self.subTest(hour=hour):
                now = datetime(2026, 3, 11, hour, 0, 1, tzinfo=timezone.utc).timestamp()
                observation = {"account": {"status": "ACTIVE", "currency": "USD", "trading_blocked": False,
                    "account_blocked": False, "trade_suspended_by_user": False, "cash": "10000", "equity": "30000"},
                    "clock": {"timestamp_ns": int(now * 1e9), "received_at_ns": int(now * 1e9),
                              "next_close_ns": int((now + 3600) * 1e9), "is_open": hour == 14},
                    "positions": [{"symbol": "SPY", "qty": "1"}], "orders": [],
                    "assets": [{"symbol": "SPY", "status": "active", "tradable": True}],
                    "quotes": [{"symbol": "SPY", "ts_ns": int(now * 1e9)}]}
                config = {"symbols": ["SPY"], "benchmarks": ["SPY"], "capital_usd": "10000",
                          "duration_seconds": 300, "cleanup_seconds": 120, "quote_max_age_seconds": 3}
                policy = {"extended_hours": True, "overnight_enabled": True, "flatten_minutes_before_pre": 10}
                try:
                    close = runner.validate_preflight(observation, config, require_open=True,
                        allow_existing=True, session_policy=policy)
                except Exception as error:
                    self.fail("held-position preflight refused: " + str(error))
                self.assertGreater(close, now)
                self.assert_refusal(lambda: runner.validate_preflight(observation, config, require_open=True,
                    session_policy=policy), "regular_session_window_unavailable")

    def test_controller_reserve_requires_reduce_only_before_downstream_guards(self):
        c, _ = self.pre_controller()
        # Isolate this layer: the admission layer has its own tests below.
        with self.rejection(), patch.object(c, "_check_overnight_admission", return_value=None):
            for side in ("buy", "sell"):
                self.assert_refusal(lambda: c.before_submit(self.order(side=side, reduce_only=False)),
                                    "overnight_exit_requires_reduce_only")
        self.assertEqual(len(c.ledger.intents()), 1)

    def test_wire_requires_reduce_only_before_admission_and_journal(self):
        c, _ = self.pre_controller()
        with patch.object(c, "_check_overnight_admission", return_value=None):
            for side in ("buy", "sell"):
                self.assert_refusal(lambda: c._overnight_before_wire(self.order(side=side, reduce_only=False)),
                                    "overnight_exit_requires_reduce_only")
        self.assertIsNone(c.ledger.overnight_submission_basis("pin-exit"))

    def test_admission_requires_active_session_sell_and_owned_position(self):
        c, clock = self.pre_controller()
        self.assert_refusal(lambda: c._check_overnight_admission("SPY", clock[0], "buy"),
                            "overnight_session_unavailable")
        c.quote({"symbol": "QQQ", "bid": "10", "ask": "10.01", "ts_ns": int(clock[0] * 1e9)})
        c.trading_status({**c.overnight_states["SPY"], "symbol": "QQQ"})
        self.assert_refusal(lambda: c._check_overnight_admission("QQQ", clock[0], "sell"),
                            "overnight_session_unavailable")

    def test_admission_refuses_closed_calendar_before_downstream_status(self):
        c, clock = self.pre_controller()
        clock[0] = datetime(2026, 3, 14, 14, tzinfo=timezone.utc).timestamp()
        c.quote({"symbol": "SPY", "bid": "10", "ask": "10.01", "ts_ns": int(clock[0] * 1e9)})
        c.trading_status({**c.overnight_states["SPY"], "ts_ns": int(clock[0] * 1e9)})
        with patch.object(c, "_check_overnight_status", return_value=None):
            self.assert_refusal(lambda: c._check_overnight_admission("SPY", clock[0], "sell"),
                                "overnight_session_unavailable")

    def test_normalize_rejects_reduce_only_buy_false_flag_and_unqualified_port(self):
        import transport
        for change, enabled in (({"side": "buy"}, True), ({"reduce_only": False}, True), ({}, False)):
            self.assert_refusal(lambda: transport.normalize_intent(self.order(**change), ("SPY",),
                allow_extended_hours=True, overnight_allowed=enabled), "invalid reduce-only exit")
        good = transport.normalize_intent(self.order(), ("SPY",), allow_extended_hours=True, overnight_allowed=True)
        self.assertIs(good["reduce_only"], True)

    def test_exit_requires_active_asset(self):
        c, clock = self.pre_controller()
        c.overnight_states["SPY"]["asset_status"] = "inactive"
        self.assert_refusal(lambda: c._check_overnight_admission("SPY", clock[0], "sell"), "exit_asset_not_tradable")

    def test_exit_requires_tradable_asset(self):
        c, clock = self.pre_controller()
        c.overnight_states["SPY"]["tradable"] = False
        self.assert_refusal(lambda: c._check_overnight_admission("SPY", clock[0], "sell"), "exit_asset_not_tradable")

    def test_exit_refuses_standing_halt(self):
        c, clock = self.pre_controller()
        c.halted_symbols.add("SPY")
        self.assert_refusal(lambda: c._check_overnight_admission("SPY", clock[0], "sell"), "exit_asset_halted")

    def test_exit_requires_owned_entry_window(self):
        c, _ = self.pre_controller()
        c.ledger.db.execute("DELETE FROM meta WHERE key LIKE 'overnight_window:%'")
        with self.rejection():
            self.assert_refusal(lambda: c.before_submit(self.order()), "overnight_exit_without_owned_window")
        self.assertFalse(any(e["type"] == "intent" for e in c.events))


# One deletion at a time, plus the transport-layer pair/triple deletions.
MUTANTS = (
    ("M2-reserve", "runner", "Controller.before_submit", 'order.get("reduce_only") is not True', "False",
     "test_controller_reserve_requires_reduce_only_before_downstream_guards"),
    ("M3-wire", "runner", "Controller._overnight_before_wire", 'order.get("side") != "sell" or order.get("reduce_only") is not True', "False",
     "test_wire_requires_reduce_only_before_admission_and_journal"),
    ("M4-admission", "runner", "Controller._check_overnight_admission", 'kind not in (SessionKind.PRE, SessionKind.RTH, SessionKind.POST)\n              or side != "sell" or symbol not in self.ledger.positions()', "False",
     "test_admission_requires_active_session_sell_and_owned_position"),
    ("M6-emitter", "mover_strategy", "MoverStrategy._execute", '**({"reduce_only": True} if record.side == "sell" and self.overnight_enabled else {}),', "",
     "test_production_mover_emitter_sets_reduce_only_on_overnight_exits"),
    ("M8-active", "runner", "Controller._check_overnight_status", 'status.get("asset_status") != "active"', "False", "test_exit_requires_active_asset"),
    ("M8-tradable", "runner", "Controller._check_overnight_status", 'status.get("tradable") is not True', "False", "test_exit_requires_tradable_asset"),
    ("M9-halt", "runner", "Controller._check_overnight_status", 'if self.is_halted(symbol):', "if False:", "test_exit_refuses_standing_halt"),
    ("M10-window", "runner", "Controller.before_submit", 'if not held_entries:\n                        raise SafetyError("overnight_exit_without_owned_window")\n                    window = windows[held_entries[-1].client_id]', 'window = {"flatten_at": self.clock()-60, "boundary_at": self.clock()-1, "day_expiry": self.clock()+3600}', "test_exit_requires_owned_entry_window"),
    ("M11-normalize", "transport", "normalize_intent", 'overnight_allowed is not True or order["reduce_only"] is not True or result["side"] != "sell"', "False",
     "test_normalize_rejects_reduce_only_buy_false_flag_and_unqualified_port"),
    ("M15-preflight", "runner", "validate_preflight", '(allow_existing and info.kind in (SessionKind.PRE, SessionKind.RTH, SessionKind.POST))', "False",
     "test_recovery_preflight_permits_pre_rth_post_but_entries_do_not"),
    ("F1-adaptive-direct", "native_strategy", "AdaptiveStrategy._rebalance", '**({"reduce_only": True} if side == "sell" and\n                   getattr(self.transport, "overnight_enabled", False) is True else {}),', "",
     "test_adaptive_exit_factories_set_reduce_only"),
    ("F1-adaptive-replacement", "native_strategy", "AdaptiveStrategy._submit_replacement_exit", '**({"reduce_only": True} if getattr(self.transport, "overnight_enabled", False) is True else {}),', "",
     "test_adaptive_exit_factories_set_reduce_only"),
    ("F3-admission-side", "runner", "Controller._check_overnight_admission", 'side != "sell"', "False",
     "test_admission_requires_active_session_sell_and_owned_position"),
    ("F3-admission-owned", "runner", "Controller._check_overnight_admission", 'symbol not in self.ledger.positions()', "False",
     "test_admission_requires_active_session_sell_and_owned_position"),
    ("F3-admission-calendar", "runner", "Controller._check_overnight_admission", 'kind not in (SessionKind.PRE, SessionKind.RTH, SessionKind.POST)', "False",
     "test_admission_refuses_closed_calendar_before_downstream_status"),
)


class GuardPinMutations(unittest.TestCase):
    def test_followup_guard_deletions_fail_ci_assertions(self):
        modules = {n: importlib.import_module(n) for n in ("runner", "transport")}
        originals = {n: dict(m.__dict__) for n,m in modules.items()}
        sources = {n: (SOURCE / (n + ".py")).read_text() for n in ("runner", "transport", "mover_strategy", "native_strategy")}
        tests = list(MUTANTS)
        plans = [[m] for m in tests]
        plans += [[tests[0], tests[1]], [tests[0], tests[2]], [tests[1], tests[2]], tests[:3]]
        killed = 0
        for plan in plans:
            name = "+".join(m[0] for m in plan)
            with self.subTest(mutant=name):
                changed = dict(sources)
                for _, module, definition, old, new, _ in plan:
                    changed[module] = delete_in_definition(changed[module], definition, old, new)
                real_read = Path.read_text
                def read(path, *args, **kwargs):
                    if path.parent == SOURCE and path.name.removesuffix(".py") in changed:
                        return changed[path.name.removesuffix(".py")]
                    return real_read(path, *args, **kwargs)
                try:
                    for module in {m[1] for m in plan} & modules.keys():
                        exec(compile(changed[module], "<guard-mutant:" + name + ">", "exec"), modules[module].__dict__)
                    with patch.object(Path, "read_text", read):
                        suite = unittest.defaultTestLoader.loadTestsFromNames(
                            ["OvernightGuardPins." + m[-1] for m in plan], sys.modules[__name__])
                        output = io.StringIO()
                        result = unittest.TextTestRunner(stream=output).run(suite)
                    self.assertGreater(len(result.failures), 0, name + output.getvalue())
                    killed += 1
                    print("followup_mutant", name, "assertion_failures", len(result.failures), "errors", len(result.errors))
                finally:
                    for module, values in originals.items():
                        modules[module].__dict__.clear()
                        modules[module].__dict__.update(values)
        self.assertEqual(killed, len(plans))
        print("followup_mutants_killed", killed, "survived", 0)


try:
    import nautilus_trader
    import alpaca
    NATIVE = True
except ImportError:
    NATIVE = False


@unittest.skipUnless(NATIVE, "requires pinned combined native runtime")
class NativeMoverEmitterPin(unittest.TestCase):
    def test_production_mover_strategy_reduces_held_position_in_pre(self):
        import tempfile
        import time
        from nautilus_trader.common import Clock
        from mover_strategy import MoverStrategy
        from native_adapter import AlpacaExecutionClient, build_node
        import runner
        from runner import Controller, _controller_session
        from safety import Ledger, RiskLimits
        from simulation import SimulatedPort
        now = [datetime(2026, 3, 11, 7, 49, tzinfo=timezone.utc).timestamp()]
        policy = {"extended_hours": True, "overnight_enabled": True, "flatten_minutes_before_pre": 10}
        real_submit = AlpacaExecutionClient._submit_order
        async def dispatch(client, command):
            old = client.clock
            client.clock = Clock.new_test()
            client.clock.set_time(int(now[0] * 1e9))
            try:
                await real_submit(client, command)
            finally:
                client.clock = old
        with tempfile.TemporaryDirectory(dir="/var/tmp") as root:
            ledger = Ledger(Path(root) / "ledger.db", RiskLimits(trial_seconds=3600, cleanup_seconds=600,
                                                               min_entry_close_seconds=600))
            self.addCleanup(ledger.close)
            ledger.start_trial(now[0])
            controller = Controller(ledger, now[0] + 3600, market_open=True, clock=lambda: now[0])
            port = SimulatedPort(controller, ("SPY",))
            port.feed, port.quote_source_mode = "boats", "boats_rest"
            port.overnight_enabled, port.extended_hours_allowed = True, True
            port.flatten_minutes_before_pre, port.quote_timeout = 10, 3
            controller.port = controller.bind(port)
            def carrier():
                controller.trading_status({"symbol": "SPY", "source": "alpaca_assets", "ts_ns": int(now[0] * 1e9),
                    "overnight_tradable": True, "overnight_halted": False, "tradable": True, "asset_status": "active"})
            carrier()
            class ScriptedBook:
                # Only deterministic decisions are fixtures. The production
                # MoverStrategy factory, callbacks and native dispatch run intact.
                plan = SimpleNamespace(symbol_names=lambda: ("SPY",), exit_rule="X2")
                def __init__(self):
                    self.legs = {"SPY": SimpleNamespace(state="queued")}
                    self.sent, self.fills = 0, 0
                def evaluate(self, at, **kwargs):
                    if controller.current_quote("SPY").timestamp != now[0]:
                        return []
                    if self.sent == 0 or (self.sent == 1 and self.fills == 1):
                        side = "buy" if self.sent == 0 else "sell"
                        self.sent += 1
                        record = SimpleNamespace(symbol="SPY", side=side, qty=1,
                            limit_price=Decimal("100.02") if side == "buy" else Decimal("100"),
                            client_id="production-" + side, reason="owned_residual_exit")
                        return [SimpleNamespace(kind="submit", record=record)]
                    return []
                def on_accepted(self, *args):
                    pass
                def on_terminal(self, *args, **kwargs):
                    pass
                def on_fill(self, *args):
                    self.fills += 1
                    if self.fills == 1:
                        now[0] = datetime(2026, 3, 11, 8, 0, 1, tzinfo=timezone.utc).timestamp()
                        controller.close, controller.market_open = _controller_session(now[0], now[0], policy)
                        carrier()
                    else:
                        self.legs["SPY"].state = "closed"
            book = ScriptedBook()
            strategy = MoverStrategy(book, ledger, clock=lambda: now[0], overnight_enabled=True)
            strategy.enabled = True
            session = build_node(port, [{"symbol": "SPY"}], [strategy], session_policy=policy)
            async def exercise():
                task = asyncio.create_task(session.run_async())
                try:
                    deadline = time.monotonic() + 5
                    while book.fills < 2 and not task.done() and time.monotonic() < deadline:
                        await asyncio.sleep(.01)
                    self.assertEqual(session.errors, [])
                    self.assertEqual(book.fills, 2)
                    self.assertEqual(ledger.positions(), {})
                    sells = [o for o in port.orders.values() if o["side"] == "sell"]
                    self.assertEqual(len(sells), 1)
                    self.assertIs(sells[0]["reduce_only"], True)
                    self.assertIs(sells[0]["extended_hours"], True)
                    self.assertEqual(sells[0]["type"], "limit")
                    self.assertEqual(sells[0]["time_in_force"], "day")
                finally:
                    if session.handle.is_running:
                        session.handle.stop()
                    await asyncio.wait_for(task, 5)
            with patch.object(runner.time, "time", side_effect=lambda: now[0]), \
                 patch.object(runner.time, "time_ns", side_effect=lambda: int(now[0] * 1e9)), \
                 patch.object(AlpacaExecutionClient, "_submit_order", dispatch):
                asyncio.run(exercise())

    def test_native_emitter_keyword_deletion_is_killed(self):
        import mover_strategy
        source = (SOURCE / "mover_strategy.py").read_text()
        mutated = delete_in_definition(source, "MoverStrategy._execute",
            '**({"reduce_only": True} if record.side == "sell" and self.overnight_enabled else {}),', "")
        node = next(n for n in ast.parse(mutated).body if isinstance(n, ast.ClassDef) and n.name == "MoverStrategy")
        method = next(n for n in node.body if getattr(n, "name", None) == "_execute")
        scope = dict(mover_strategy.__dict__)
        exec(compile(ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[])), "<native-M6>", "exec"), scope)
        with patch.object(mover_strategy.MoverStrategy, "_execute", scope["_execute"]):
            output = io.StringIO()
            suite = unittest.defaultTestLoader.loadTestsFromName(
                "NativeMoverEmitterPin.test_production_mover_strategy_reduces_held_position_in_pre", sys.modules[__name__])
            result = unittest.TextTestRunner(stream=output).run(suite)
        self.assertGreater(len(result.failures), 0, output.getvalue())
        self.assertEqual(result.errors, [], output.getvalue())
