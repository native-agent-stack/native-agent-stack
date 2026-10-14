"""CI-visible overnight guards; no SDK, credentials or broker required."""
import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

SOURCE = Path(__file__).resolve().parents[1] / "blueprints/us-equities/adaptive-paper"
sys.path.insert(0, str(SOURCE))


class OvernightArming(unittest.TestCase):
    def test_exit_rest_feed_follows_the_session_only_for_the_explicit_instance(self):
        from overnight import overnight_quote_feed
        for hour, minute, second, expected in ((1, 0, 0, "boats"), (8, 0, 1, "sip"),
                                                (14, 0, 0, "sip"), (21, 0, 0, "sip")):
            now = datetime(2026, 3, 11, hour, minute, second, tzinfo=timezone.utc).timestamp()
            with self.subTest(expected=expected, hour=hour):
                self.assertEqual(overnight_quote_feed("boats", now, enabled=True), expected)
                self.assertEqual(overnight_quote_feed("boats", now), "boats")
                self.assertEqual(overnight_quote_feed("iex", now, enabled=True), "iex")

    def test_pre_entry_remains_refused(self):
        from overnight import overnight_dispatch_refusal
        now = datetime(2026, 3, 11, 8, 0, 1, tzinfo=timezone.utc).timestamp()
        port = SimpleNamespace(overnight_enabled=True, feed="boats", quote_source_mode="boats_rest",
                               overnight_check=lambda *args: None)
        self.assertEqual(overnight_dispatch_refusal(port, "SPY", now,
                         {"overnight_enabled": True}, "buy"), "entry_dispatch_session_unavailable")

    def test_held_overnight_position_exits_at_pre_as_extended_hours_limit(self):
        """Exercise committed native dispatch and owner/ledger/wire guards at 04:00:01 ET."""
        import ast
        import transport
        from sessions import SessionKind, session_at, order_extended_hours_flag
        from runner import _controller_session
        from safety import SafetyError
        controller, clock, _, _, _ = self._controller(held=True,
            now=datetime(2026, 3, 11, 7, 49, tzinfo=timezone.utc).timestamp())
        now = clock[0] = datetime(2026, 3, 11, 8, 0, 1, tzinfo=timezone.utc).timestamp()
        controller.close, controller.market_open = _controller_session(now, now,
            {"extended_hours": True, "overnight_enabled": True, "flatten_minutes_before_pre": 10})
        controller.quote({"symbol": "SPY", "bid": "10", "ask": "10.01", "ts_ns": int(now * 1e9)})
        controller.trading_status({"symbol": "SPY", "source": "alpaca_assets", "ts_ns": int(now * 1e9),
            "overnight_tradable": False, "overnight_halted": False, "tradable": True, "asset_status": "active"})
        tree = ast.parse((SOURCE / "native_adapter.py").read_text())
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "AlpacaExecutionClient")
        method = next(n for n in cls.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "_submit_order")
        rejection = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "NativeOrderRejected")
        scope = {"datetime": datetime, "timezone": timezone, "SessionKind": SessionKind,
                 "session_at": session_at, "order_extended_hours_flag": order_extended_hours_flag,
                 "OrderType": SimpleNamespace(LIMIT="limit"), "TimeInForce": SimpleNamespace(DAY="day", GTC="gtc"),
                 "OrderSide": SimpleNamespace(SELL="sell")}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[method, rejection], type_ignores=[])),
                     str(SOURCE / "native_adapter.py"), "exec"), scope)
        submitted = []
        wire = SimpleNamespace(overnight_enabled=True, overnight_before_wire=controller.port.overnight_before_wire,
                               _on_owner=lambda fn, *args, **kwargs: fn(*args),
                               _quote_values={"SPY": {"ts_ns": int(now * 1e9)}},
                               order_quote_max_age_ns=3000000000, exit_quote_max_age_ns=3000000000,
                               _stopping=False, _started=True, ready=True)
        async def submit(payload):
            order = transport.normalize_intent(payload, ("SPY",), allow_extended_hours=True, overnight_allowed=True)
            # Execute the actual rejection class without importing the SDK in CI.
            with patch.dict(sys.modules, {"native_adapter": SimpleNamespace(NativeOrderRejected=scope["NativeOrderRejected"])}):
                controller.before_submit(order)
            wire._intents = {order["client_order_id"]: order}
            transport.AlpacaPaperTransport._wire_guard(wire, {**order, "type": "limit"})
            submitted.append(payload)
            return payload
        controller.port.submit = submit
        order = SimpleNamespace(order_type="limit", time_in_force="day", instrument_id=SimpleNamespace(symbol="SPY"),
                                side="sell", client_order_id="pre-exit", quantity=1, price="10.00",
                                strategy_id="fixture", tags=[], is_reduce_only=True)
        session = SimpleNamespace(errors=[], instruments={"SPY": object()}, port=controller.port,
                                  session_policy={"extended_hours": True, "overnight_enabled": True}, fail=Mock())
        client = SimpleNamespace(session=session, clock=SimpleNamespace(timestamp_ns=lambda: int(now * 1e9)),
                                 orders={}, generate_order_denied=Mock(), generate_order_submitted=Mock(),
                                 observe=Mock(), generate_order_rejected=Mock())
        with patch.object(transport.time, "time_ns", return_value=int(now * 1e9)):
            asyncio.run(scope["_submit_order"](client, SimpleNamespace(order=order)))
        self.assertEqual(len(submitted), 1, (session.fail.call_args_list, client.generate_order_denied.call_args_list,
                                           client.generate_order_rejected.call_args_list))
        self.assertEqual(submitted[0]["type"], "limit")
        self.assertIs(submitted[0]["extended_hours"], True)
        self.assertIs(submitted[0]["reduce_only"], True)
        client.generate_order_denied.assert_not_called()
        session.fail.assert_not_called()
        self.assertEqual(controller.ledger.positions()["SPY"].qty, Decimal(1))
        # Concurrent exits cannot oversell the position the port actually holds.
        with patch.dict(sys.modules, {"native_adapter": SimpleNamespace(NativeOrderRejected=scope["NativeOrderRejected"])}), \
             self.assertRaisesRegex(RuntimeError, "sell_exceeds"):
            controller.before_submit({**submitted[0], "client_order_id": "oversell"})

    def test_committed_native_dispatch_method_is_ci_visible(self):
        """Execute the committed method's AST with protocol fixtures, no native import."""
        import ast
        from sessions import SessionKind, session_at, order_extended_hours_flag
        tree = ast.parse((SOURCE / "native_adapter.py").read_text())
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "AlpacaExecutionClient")
        method = next(n for n in cls.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "_submit_order")
        scope = {"datetime": datetime, "timezone": timezone, "SessionKind": SessionKind,
                 "session_at": session_at, "order_extended_hours_flag": order_extended_hours_flag,
                 "OrderType": SimpleNamespace(LIMIT="limit"), "TimeInForce": SimpleNamespace(DAY="day", GTC="gtc"),
                 "OrderSide": SimpleNamespace(SELL="sell")}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[])),
                     str(SOURCE / "native_adapter.py"), "exec"), scope)
        now = datetime(2026, 3, 11, 1, tzinfo=timezone.utc).timestamp()
        order = SimpleNamespace(order_type="limit", time_in_force="day", instrument_id=SimpleNamespace(symbol="SPY"),
                                side="buy", client_order_id="synthetic-order", quantity=1, price="10.01",
                                strategy_id="fixture", tags=[])
        submitted = []
        async def submit(payload):
            submitted.append(payload)
            return payload
        port = SimpleNamespace(overnight_enabled=True, feed="boats", quote_source_mode="boats_rest",
                               overnight_check=lambda *args: None, submit=submit)
        for missing in (None, "quote_source_mode", "overnight_enabled", "overnight_check", "carrier", "quote"):
            with self.subTest(missing=missing):
                submitted.clear()
                port.overnight_enabled, port.quote_source_mode = True, "boats_rest"
                port.overnight_check = lambda *args: None
                if missing in ("quote_source_mode", "overnight_enabled", "overnight_check"):
                    setattr(port, missing, None)
                elif missing in ("carrier", "quote"):
                    def refused(*args):
                        raise RuntimeError("missing_fixture_precondition")
                    port.overnight_check = refused
                errors = []
                session = SimpleNamespace(errors=errors, instruments={"SPY": object()}, port=port,
                                          session_policy={"extended_hours": True, "overnight_enabled": True},
                                          fail=errors.append)
                denied = Mock()
                client = SimpleNamespace(session=session, clock=SimpleNamespace(timestamp_ns=lambda: int(now * 1e9)),
                                         orders={}, generate_order_denied=denied, generate_order_submitted=Mock(),
                                         observe=Mock(), generate_order_rejected=Mock())
                asyncio.run(scope["_submit_order"](client, SimpleNamespace(order=order)))
                if missing is None:
                    self.assertEqual(len(submitted), 1)
                    self.assertIs(submitted[0]["extended_hours"], True)
                    denied.assert_not_called()
                else:
                    self.assertEqual(submitted, [])
                    denied.assert_called_once_with(order, "entry_dispatch_session_unavailable")
                    self.assertEqual(client.orders, {})
                    self.assertEqual(session.errors, [])

    def test_stale_entry_carrier_denies_without_stopping_node_or_touching_other_position(self):
        import ast
        from sessions import SessionKind, session_at, order_extended_hours_flag
        tree = ast.parse((SOURCE / "native_adapter.py").read_text())
        execution = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "AlpacaExecutionClient")
        method = next(n for n in execution.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "_submit_order")
        session_cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "NativeSession")
        fail = next(n for n in session_cls.body if isinstance(n, ast.FunctionDef) and n.name == "fail")
        scope = {"datetime": datetime, "timezone": timezone, "SessionKind": SessionKind,
                 "session_at": session_at, "order_extended_hours_flag": order_extended_hours_flag,
                 "OrderType": SimpleNamespace(LIMIT="limit"), "TimeInForce": SimpleNamespace(DAY="day", GTC="gtc"),
                 "OrderSide": SimpleNamespace(SELL="sell")}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[method, fail], type_ignores=[])),
                     str(SOURCE / "native_adapter.py"), "exec"), scope)
        controller, clock, _, _, _ = self._controller()
        controller.overnight_states["SPY"]["ts_ns"] -= 4000000000
        other = {"QQQ": {"qty": Decimal(2), "average_cost": Decimal(100)}}
        before = {s: dict(p) for s, p in other.items()}
        handle = SimpleNamespace(is_running=True)
        def stop():
            handle.is_running = False
        handle.stop = Mock(side_effect=stop)
        session = SimpleNamespace(errors=[], instruments={"SPY": object()}, handle=handle,
                                  port=controller.port,
                                  session_policy={"extended_hours": True, "overnight_enabled": True})
        from types import MethodType
        session.fail = MethodType(scope["fail"], session)
        order = SimpleNamespace(order_type="limit", time_in_force="day", instrument_id=SimpleNamespace(symbol="SPY"),
                                side="buy", client_order_id="new-entry", quantity=1, price="10.01",
                                strategy_id="fixture", tags=[])
        client = SimpleNamespace(session=session, clock=SimpleNamespace(timestamp_ns=lambda: int(clock[0] * 1e9)),
                                 orders={}, generate_order_denied=Mock(), generate_order_submitted=Mock(),
                                 observe=Mock(), generate_order_rejected=Mock())
        asyncio.run(scope["_submit_order"](client, SimpleNamespace(order=order)))
        client.generate_order_denied.assert_called_once_with(order, "entry_dispatch_session_unavailable")
        self.assertEqual(session.errors, [])
        self.assertTrue(handle.is_running)
        handle.stop.assert_not_called()
        self.assertEqual(other, before)
        self.assertEqual(client.orders, {})
        order.side = "sell"
        client.generate_order_denied.reset_mock()
        asyncio.run(scope["_submit_order"](client, SimpleNamespace(order=order)))
        client.generate_order_denied.assert_called_once_with(order, "exit_dispatch_session_unavailable")
        self.assertEqual(session.errors, ["exit_dispatch_session_unavailable:new-entry"])
        self.assertFalse(handle.is_running)
        handle.stop.assert_called_once()

    def test_mover_carrier_cannot_use_thirty_second_transport_timeout(self):
        controller, clock, _, _, _ = self._controller()
        controller.port.quote_timeout = 30
        controller.overnight_states["SPY"]["ts_ns"] -= 4000000000
        with self.assertRaisesRegex(RuntimeError, "overnight_status_stale"):
            controller._check_overnight_admission("SPY", clock[0], "buy")

    def test_final_transport_guard_refusal_does_not_journal_wire_submit(self):
        import transport
        controller, clock, _, _, _ = self._controller()
        now = clock[0]
        wire = SimpleNamespace(overnight_enabled=True, overnight_before_wire=controller.port.overnight_before_wire,
                               _on_owner=lambda fn, *args, **kwargs: fn(*args),
                               _quote_values={"SPY": {"ts_ns": int(now * 1e9)}},
                               order_quote_max_age_ns=3000000000, exit_quote_max_age_ns=3000000000,
                               _stopping=False, _started=True, ready=False)
        order = {"symbol": "SPY", "side": "buy", "type": "limit", "time_in_force": "day",
                 "extended_hours": True, "client_order_id": "entry"}
        with patch.object(transport.time, "time_ns", return_value=int(now * 1e9)), \
             self.assertRaises(transport.SubmissionNotSent):
            transport.AlpacaPaperTransport._wire_guard(wire, order)
        self.assertIsNone(controller.ledger.overnight_submission_basis("entry"))
        self.assertFalse(any(e["type"] == "overnight_wire_submit" for e in controller.events))

    def test_transport_rest_construction_never_constructs_stock_stream(self):
        from enum import Enum
        import transport
        class Feed(str, Enum):
            BOATS = "boats"
        class Orders:
            def __init__(self, *args, **kwargs):
                pass
        class Quotes:
            def __init__(self, *args, **kwargs):
                raise AssertionError("unsupported BOATS StockDataStream constructed")
        clients = []
        def sdk(*args, **kwargs):
            client = SimpleNamespace(_session=SimpleNamespace(before_send=None, close=Mock()))
            clients.append(client)
            return client
        with patch.dict(sys.modules, {"alpaca.data.enums": SimpleNamespace(DataFeed=Feed)}), \
             patch.object(transport, "_sdk_client", side_effect=sdk), \
             patch.object(transport, "_stream_classes", return_value=(Orders, Quotes)), \
             patch.object(transport, "_protocol_factory", return_value=None):
            port = transport.AlpacaPaperTransport("fixture", "fixture", ("SPY", "QQQ"),
                before_request=lambda *_: None, before_submit=lambda *_: None,
                sink_observation=lambda *_: None, sink_status=lambda *_: None,
                feed="boats", quote_source_mode="boats_rest", overnight_enabled=True, extended_hours_allowed=True)
            self.assertIsNone(port._quotes_stream)
            self.assertEqual(len(clients), 5)
            self.assertEqual(set(port._boats_source.symbols), {"SPY", "QQQ"})

    def test_explicit_rest_opt_in_preserves_stream_refusal(self):
        from feeds import require_qualified_quote_source, require_qualified_stream
        require_qualified_quote_source("boats", "boats_rest")
        with self.assertRaisesRegex(ValueError, "boats_stream_unqualified_sdk"):
            require_qualified_stream("boats")
        for feed, mode in (("overnight", "boats_rest"), ("sip", "boats_rest"), ("boats", "stream")):
            with self.subTest(feed=feed, mode=mode), self.assertRaises(ValueError):
                require_qualified_quote_source(feed, mode)

    def test_calendar_cutoff_and_no_pre_carry(self):
        from overnight import overnight_bounds
        now = datetime(2026, 3, 11, 1, tzinfo=timezone.utc).timestamp()
        bounds = overnight_bounds(now)
        self.assertEqual(bounds["flatten_at"], datetime(2026, 3, 11, 7, 50, tzinfo=timezone.utc).timestamp())
        self.assertEqual(bounds["boundary_at"], datetime(2026, 3, 11, 8, tzinfo=timezone.utc).timestamp())
        self.assertEqual(bounds["day_expiry"], datetime(2026, 3, 12, 0, tzinfo=timezone.utc).timestamp())
        for reserve in (0, -1, 61, True, 10.0):
            with self.subTest(reserve=reserve), self.assertRaisesRegex(ValueError, "unqualified_overnight_configuration"):
                overnight_bounds(now, reserve)
        for stamp in ("2026-03-14T01:00:00+00:00", "2026-07-03T01:00:00+00:00", "2026-03-11T08:00:00+00:00"):
            with self.subTest(stamp=stamp), self.assertRaisesRegex(ValueError, "overnight_session_unavailable"):
                overnight_bounds(datetime.fromisoformat(stamp).timestamp())

    def test_dispatch_missing_each_precondition_keeps_tripwire(self):
        from overnight import overnight_dispatch_refusal
        now = datetime(2026, 3, 11, 1, tzinfo=timezone.utc).timestamp()
        policy = {"extended_hours": True, "overnight_enabled": True}
        port = SimpleNamespace(overnight_enabled=True, feed="boats", quote_source_mode="boats_rest",
                               overnight_check=lambda symbol, at, side: None)
        self.assertIsNone(overnight_dispatch_refusal(port, "SPY", now, policy, "buy"))
        for key, bad in (("overnight_enabled", False), ("feed", "overnight"),
                         ("quote_source_mode", "stream"), ("overnight_check", None)):
            old = getattr(port, key)
            setattr(port, key, bad)
            self.assertEqual(overnight_dispatch_refusal(port, "SPY", now, policy, "buy"),
                             "entry_dispatch_session_unavailable")
            setattr(port, key, old)
        for reason in ("no_current_quote", "overnight_status_unknown", "overnight_status_stale"):
            def refuse(*_, reason=reason):
                raise ValueError(reason)
            port.overnight_check = refuse
            self.assertEqual(overnight_dispatch_refusal(port, "SPY", now, policy, "buy"),
                             "entry_dispatch_session_unavailable")

    def test_rest_sweep_concurrent_bounded_and_429_preserves_state(self):
        from overnight import BoatsQuoteSource
        active, peak, calls = 0, 0, []
        async def read(symbol):
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(.01)
            active -= 1
            calls.append(symbol)
            return {"symbol": symbol}
        class RateLimited(Exception):
            status_code = 429
        async def exercise():
            source = BoatsQuoteSource(("SPY", "QQQ", "IWM"), read, read, concurrency=2)
            first = await source.sweep(100)
            self.assertEqual(len(first), 3)
            self.assertEqual(peak, 2)
            async def throttled(_):
                calls.append("throttled_quote")
                raise RateLimited()
            source.quote_read = throttled
            self.assertEqual(await source.sweep(101), [])
            self.assertEqual(len(source.last), 3)
            self.assertTrue(all(at > 101 for at in source.retry_at.values()))
            count = len(calls)
            self.assertEqual(await source.sweep(101.1), [])
            self.assertEqual(len(calls), count)
        asyncio.run(exercise())

    def test_poll_bound_and_asset_refresh_never_restamp_cached_carrier(self):
        from overnight import BoatsQuoteSource
        async def noop(_):
            return {}
        for symbols, concurrency in (((), 5), (tuple("ABCDEF"), 5), (("SPY",), 0),
                                     (("SPY",), 6), (("SPY",), True)):
            with self.subTest(symbols=symbols, concurrency=concurrency), self.assertRaisesRegex(ValueError, "overnight_symbol_bound"):
                BoatsQuoteSource(symbols, noop, noop, concurrency=concurrency)
        clock, reads = [100], []
        async def asset(symbol):
            reads.append(symbol)
            return {"ts_ns": clock[0] * 1000000000}
        async def exercise():
            source = BoatsQuoteSource(("SPY",), noop, asset, asset_timeout=3)
            a = await source.sweep(clock[0])
            clock[0] = 102
            b = await source.sweep(clock[0])
            self.assertEqual(a[0]["asset"]["ts_ns"], b[0]["asset"]["ts_ns"])
            self.assertEqual(len(reads), 1)
            clock[0] = 103
            c = await source.sweep(clock[0])
            self.assertEqual(c[0]["asset"]["ts_ns"], 103000000000)
            self.assertEqual(len(reads), 2)
            await source.close()
        asyncio.run(exercise())

    def test_no_pre_carry_forces_handoff_without_an_unresolved_order(self):
        controller, clock, _, bounds, _ = self._controller(held=True)
        clock[0] = bounds["boundary_at"]
        self.assertTrue(asyncio.run(controller.overnight_tick(clock[0])))
        self.assertTrue(controller.stop)
        self.assertEqual(controller.ledger.accounting().halted_reason, "overnight_boundary_handoff")

    def test_missing_status_preserves_exit_repricing_until_fresh(self):
        controller, clock, _, _, _ = self._controller(held=True)
        self.assertTrue(controller.overnight_reprice_allowed("SPY", clock[0]))
        controller.overnight_states.clear()
        self.assertFalse(controller.overnight_reprice_allowed("SPY", clock[0]))

    def test_overnight_carrier_cannot_halt_a_legacy_rth_port(self):
        controller, _, _, _, _ = self._controller()
        controller.overnight_states["SPY"]["overnight_halted"] = True
        self.assertTrue(controller.is_halted("SPY"))
        controller.port.overnight_enabled = False
        self.assertFalse(controller.is_halted("SPY"))
        controller.halted_symbols.add("SPY")
        self.assertTrue(controller.is_halted("SPY"))

    def test_wire_guard_repeats_carrier_check_immediately_before_post(self):
        import transport
        controller, clock, _, _, _ = self._controller()
        now = clock[0]
        wire = SimpleNamespace(overnight_enabled=True, overnight_before_wire=controller.port.overnight_before_wire,
                               _on_owner=lambda fn, *args, **kwargs: fn(*args),
                               _quote_values={"SPY": {"ts_ns": int(now * 1e9)}},
                               order_quote_max_age_ns=3000000000, exit_quote_max_age_ns=3000000000,
                               _stopping=False, _started=True, ready=True)
        order = {"symbol": "SPY", "side": "buy", "type": "limit", "time_in_force": "day",
                 "extended_hours": True, "client_order_id": "entry"}
        with patch.object(transport.time, "time", return_value=now), \
             patch.object(transport.time, "time_ns", return_value=int(now * 1e9)):
            status = dict(controller.overnight_states["SPY"])
            controller.overnight_states.clear()
            with self.assertRaisesRegex(transport.SubmissionNotSent, "overnight admission changed before submission"):
                transport.AlpacaPaperTransport._wire_guard(wire, order)
            self.assertIsNone(controller.ledger.overnight_submission_basis("entry"))
            controller.overnight_states["SPY"] = status
            transport.AlpacaPaperTransport._wire_guard(wire, order)
            self.assertEqual(controller.ledger.overnight_submission_basis("entry")["midpoint"], "10.005")

    def test_wire_callback_returns_to_owner_and_basis_survives_reopen(self):
        import threading
        from types import MethodType
        import transport
        from safety import Ledger
        controller, clock, _, _, root = self._controller()
        now, owners = clock[0], []
        wire = SimpleNamespace(overnight_enabled=True, _quote_values={"SPY": {"ts_ns": int(now * 1e9)}},
                               order_quote_max_age_ns=3000000000, exit_quote_max_age_ns=3000000000,
                               _stopping=False, _started=True, ready=True)
        def before_wire(order):
            owners.append(threading.get_ident())
            controller.port.overnight_before_wire(order)
        wire.overnight_before_wire = before_wire
        wire._on_owner = MethodType(transport.AlpacaPaperTransport._on_owner, wire)
        wire._invoke = MethodType(transport.AlpacaPaperTransport._invoke, wire)
        order = {"symbol": "SPY", "side": "buy", "type": "limit", "time_in_force": "day",
                 "extended_hours": True, "client_order_id": "entry"}
        async def exercise():
            wire._loop = asyncio.get_running_loop()
            owner = threading.get_ident()
            with patch.object(transport.time, "time_ns", return_value=int(now * 1e9)):
                await asyncio.to_thread(transport.AlpacaPaperTransport._wire_guard, wire, order)
            self.assertEqual(owners, [owner])
        asyncio.run(exercise())
        limits = controller.ledger.limits
        controller.ledger.close()
        reopened = Ledger(Path(root) / "ledger.sqlite3", limits)
        self.addCleanup(reopened.close)
        self.assertEqual(reopened.overnight_submission_basis("entry"), {"midpoint": "10.005", "sent_at": now})

    def test_sdk_request_keeps_gtc_from_the_explicit_envelope(self):
        import transport
        fields = {"symbol": "SPY", "side": "sell", "type": "limit", "time_in_force": "gtc",
                  "extended_hours": True, "qty": "1", "limit_price": "10", "client_order_id": "fixture-gtc"}
        envelope = transport.order_envelope(fields, extended_hours_allowed=True, overnight_allowed=True)
        factory = Mock(side_effect=lambda **values: SimpleNamespace(fields=values))
        with patch.dict(sys.modules, {"alpaca.trading.requests": SimpleNamespace(LimitOrderRequest=factory)}):
            request = transport.limit_order_request(envelope)
        self.assertEqual(request.fields["time_in_force"], "gtc")
        self.assertIs(request.fields["extended_hours"], True)

    def test_execution_receipt_midpoint_latency_and_replay_are_durable(self):
        controller, clock, _, _, _ = self._controller()
        now = clock[0]
        controller.port.overnight_before_wire({"client_order_id": "entry", "symbol": "SPY", "side": "buy"})
        clock[0] += .2
        row = {"client_order_id": "entry", "id": "synthetic-entry", "status": "filled", "filled_qty": "1",
               "filled_avg_price": "10.01", "updated_at_ns": int(clock[0] * 1e9), "symbol": "SPY", "side": "buy",
               "event": "fill", "execution_id": "synthetic-execution", "event_qty": "1", "event_price": "10.01",
               "execution_time_ns": int(clock[0] * 1e9)}
        controller.observe(row)
        controller.observe(row)
        receipts = [e for e in controller.events if e["type"] == "overnight_execution_receipt"]
        self.assertEqual(len(receipts), 1)
        self.assertEqual(receipts[0]["midpoint_at_submit"], "10.005")
        self.assertAlmostEqual(receipts[0]["latency_seconds"], .2, places=5)
        self.assertGreater(Decimal(receipts[0]["slippage_bps"]), 0)
        self.assertFalse(controller.ledger.record_overnight_execution_receipt("entry", receipts[0]))

    def test_mover_trail_samples_initial_and_raised_fill_high_only_on_change(self):
        from mover import MoverBook, OrderRecord
        record = OrderRecord("entry", "SPY", "buy", Decimal(3), Decimal(10), "fixture", 100, Decimal(10))
        leg = SimpleNamespace(first_fill_at=None, running_high=None)
        events = []
        book = SimpleNamespace(orders={"entry": record}, legs={"SPY": leg}, events=events.append,
                               on_terminal=Mock())
        MoverBook.on_fill(book, "entry", 100, "1", "10")
        MoverBook.on_fill(book, "entry", 101, "1", "11")
        MoverBook.on_fill(book, "entry", 102, ".5", "10")
        self.assertEqual([(e["high_bid"], e["at"]) for e in events], [("10", 100), ("11", 101)])
        self.assertTrue(all(e["basis"] == "entry_fill" for e in events))
        self.assertEqual(leg.running_high, Decimal(11))

    def test_qualified_overnight_exits_are_marketable_and_unqualified_still_hold(self):
        from exits import DEFAULT_PLAN, ExitContext
        from strategies import PolicyConfig
        c = PolicyConfig(symbols=("SPY",), benchmarks=("SPY",), max_positions=1)
        ctx = ExitContext(now=100, entered_at=0, pnl_bps=0, trail_bps=-1000,
                          quote_fresh=True, risk_off=False, force_exit=False,
                          force_exit_reason="force_exit", session="OVERNIGHT", bid="0.9349", ask="0.95",
                          overnight_qualified=True)
        decision = DEFAULT_PLAN.evaluate(ctx, c)
        self.assertTrue(decision.submit)
        self.assertEqual(decision.price_rule, "limit")
        self.assertLessEqual(Decimal(decision.limit_price), Decimal(ctx.bid))
        from dataclasses import replace
        for other, reason in ((replace(ctx, overnight_qualified=False), "overnight_unqualified"),
                              (replace(ctx, quote_fresh=False), "quote_stale")):
            decision = DEFAULT_PLAN.evaluate(other, c)
            self.assertFalse(decision.submit)
            self.assertTrue(decision.flag_position)
            self.assertEqual(decision.reason, reason)

    def _controller(self, *, held=False, now=None):
        from runner import Controller
        from safety import Ledger, RiskLimits, Quote
        from overnight import overnight_bounds
        now = datetime(2026, 3, 11, 1, tzinfo=timezone.utc).timestamp() if now is None else now
        root = tempfile.TemporaryDirectory(dir="/var/tmp")
        self.addCleanup(root.cleanup)
        limits = RiskLimits(trial_seconds=3600, cleanup_seconds=600, min_entry_close_seconds=600)
        ledger = Ledger(Path(root.name) / "ledger.sqlite3", limits)
        self.addCleanup(ledger.close)
        ledger.start_trial(now)
        clock = [now]
        bounds = overnight_bounds(now)
        controller = Controller(ledger, bounds["boundary_at"], market_open=True, clock=lambda: clock[0])
        cancels = []
        async def cancel(cid):
            cancels.append(cid)
        async def submit(order):
            return order
        port = SimpleNamespace(ready=True, overnight_enabled=True, feed="boats", quote_source_mode="boats_rest",
                               extended_hours_allowed=True, flatten_minutes_before_pre=10, quote_timeout=3,
                               cancel=cancel, submit=submit)
        controller.port = controller.bind(port)
        controller.quote({"symbol": "SPY", "bid": "10", "ask": "10.01", "ts_ns": int(now * 1e9)})
        controller.trading_status({"symbol": "SPY", "source": "alpaca_assets", "ts_ns": int(now * 1e9),
                                   "overnight_tradable": True, "overnight_halted": False})
        ledger.reserve_intent("entry", "SPY", "buy", "1", "10.01", quote=Quote("SPY", "10", "10.01", now),
                              now=now, market_open=True, session_close=bounds["boundary_at"],
                              stop_file=Path(root.name) / "synthetic-stop")
        ledger.record_overnight_window("entry", bounds)
        ledger.record_order("entry", "synthetic-entry", "filled" if held else "accepted",
                            "1" if held else "0", "10.01" if held else None, timestamp=now)
        return controller, clock, cancels, bounds, root.name

    def test_status_quote_freshness_and_replay_before_wire(self):
        controller, clock, _, _, _ = self._controller()
        now = clock[0]
        controller.port.overnight_check("SPY", now, "buy")
        status = dict(controller.overnight_states["SPY"])
        for change, reason in (({"overnight_tradable": None}, "overnight_status_unknown"),
                               ({"ts_ns": int((now - 4) * 1e9)}, "overnight_status_stale"),
                               ({"ts_ns": int((now + 1) * 1e9)}, "overnight_status_stale"),
                               ({"overnight_halted": True}, "overnight_halted")):
            controller.overnight_states["SPY"] = {**status, **change}
            with self.subTest(change=change), self.assertRaisesRegex(RuntimeError, reason):
                asyncio.run(controller.before_request("submit", client_id="entry"))
        controller.overnight_states["SPY"] = status
        clock[0] += 4
        with self.assertRaisesRegex(RuntimeError, "overnight_status_stale"):
            asyncio.run(controller.before_request("submit", client_id="entry"))
        clock[0] = now
        newer = {**status, "ts_ns": int((now + .1) * 1e9), "overnight_halted": True}
        controller.trading_status(newer)
        controller.trading_status(status)
        self.assertTrue(controller.is_halted("SPY"))
        self.assertEqual(controller.overnight_states["SPY"], newer)

    def test_third_d6_cutoff_halted_and_unknown_entries_cancel_without_reprice(self):
        import json
        fixture = json.loads((SOURCE.parents[2] / "tests/fixtures/adaptive_paper_overnight_cutoff.json").read_text())
        self.assertEqual(fixture["paper_acceptance"], "NOT_RUN")
        for mode in (case["status"] for case in fixture["cases"]):
            with self.subTest(mode=mode):
                controller, clock, cancels, bounds, _ = self._controller()
                if mode == "halted":
                    controller.overnight_states["SPY"]["overnight_halted"] = True
                    self.assertFalse(asyncio.run(controller.overnight_tick(clock[0])))
                    self.assertEqual(cancels, ["entry"])
                else:
                    controller.overnight_states.clear()
                clock[0] = bounds["flatten_at"]
                self.assertTrue(asyncio.run(controller.overnight_tick(clock[0])))
                self.assertEqual(cancels, ["entry"])
                self.assertEqual(controller.ledger.positions(), {})
                self.assertEqual(controller.ledger.intents()[0].filled_qty, 0)

    def test_persisted_carry_deadline_reopens_and_cancels_accepted_entry(self):
        from runner import Controller
        from safety import Ledger
        controller, clock, cancels, bounds, root = self._controller()
        limits = controller.ledger.limits
        controller.ledger.close()
        reopened = Ledger(Path(root) / "ledger.sqlite3", limits)
        self.addCleanup(reopened.close)
        self.assertEqual(reopened.overnight_windows(), {"entry": bounds})
        self.assertEqual(reopened.db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0], "4")
        self.assertEqual(reopened.intents()[0].status, "accepted")
        self.assertEqual(reopened.positions(), {})
        fresh = Controller(reopened, bounds["boundary_at"], market_open=True, clock=lambda: bounds["flatten_at"])
        fresh.port = controller.port
        self.assertTrue(asyncio.run(fresh.overnight_tick(bounds["flatten_at"])))
        self.assertEqual(cancels, ["entry"])

    def test_halted_exit_rests_and_day_expiry_flags_freezes_and_notifies(self):
        from safety import Quote
        controller, clock, cancels, bounds, _ = self._controller(held=True)
        now = clock[0]
        controller.ledger.reserve_intent("exit", "SPY", "sell", "1", "10", quote=Quote("SPY", "10", "10.01", now),
                                        now=now, market_open=True, session_close=bounds["boundary_at"])
        controller.ledger.record_overnight_window("exit", bounds)
        controller.ledger.record_order("exit", "synthetic-exit", "accepted", "0", None, timestamp=now)
        controller.overnight_states["SPY"]["overnight_halted"] = True
        clock[0] = bounds["flatten_at"]
        asyncio.run(controller.overnight_tick(clock[0]))
        self.assertEqual(cancels, [])
        self.assertEqual(controller.ledger.intents()[1].status, "accepted")
        clock[0] = bounds["day_expiry"]
        asyncio.run(controller.overnight_tick(clock[0]))
        self.assertEqual(cancels, [])
        self.assertTrue(controller.stop)
        self.assertEqual(controller.ledger.accounting().halted_reason, "overnight_day_expiry")
        self.assertTrue(any(e["type"] == "overnight_handoff" for e in controller.events))
        self.assertTrue(any(e["type"] == "exit_attention" for e in controller.events))


if __name__ == "__main__":
    unittest.main()
