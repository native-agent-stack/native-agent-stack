"""Real rc5 queue/adapter cancellation handoff; synthetic broker, no network."""
import asyncio
import contextlib
from dataclasses import replace
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[2] / "blueprints/us-equities/adaptive-paper"
sys.path.insert(0, str(SOURCE))
import native_adapter
import native_strategy
import runner
from nautilus_trader.model import ClientOrderId, InstrumentId, OrderSide, Price, Quantity, TimeInForce
from safety import Ledger, RiskLimits
from simulation import SimulatedPort, invoke
from tests.adaptive_paper_hermetic import patch_default_stop, restore_default_stop


class NativeCancelDispatch(unittest.TestCase):
    def test_integrity_loss_waits_for_real_native_cancel_confirmation_before_stop(self):
        # nautechsystems/nautilus_trader v2.0.0rc5 @
        # 1b0a49d2792a9432a3aca3fcb617ce7a630d905e:
        # crates/trading/src/python/strategy.rs:2001 queues native cancellation;
        # crates/execution/src/engine/mod.rs:185-196 defers execution commands;
        # crates/live/src/python/runtime.rs:177-211,834-867 queues/serializes
        # Python client operations. node/mod.rs:1786-1801,2360-2373 drains only
        # during a bounded stop grace; runtime.rs:685-697 discards queued work
        # on disconnect. Match the vendor disconnect test at
        # python/tests/unit/live/test_client_runtime.py:193-228, but use a real
        # LiveNode, native Strategy.cancel_order and this repo's real adapter.
        # Hold its submit dispatcher for .6 s after loss (> .1+.2 stop grace).
        # No synchronous replacement for cancel_order and no fresh recovery.
        result = self.exercise()
        self.assertEqual(result["cancel_calls"], 1, result)
        self.assertTrue(result["confirmed_before_stop"], result)
        self.assertEqual(result["active_at_stop"], 0, result)
        self.assertEqual(result["unresolved"], 0, result)
        self.assertEqual(result["adapter_errors"], [], result)
        self.assertEqual(result["cancellations"], {"status": "confirmed", "requested_count": 1,
            "confirmed_count": 1, "unconfirmed_count": 0, "timeout_seconds": 2}, result)
        self.assertLess(result["events"].index("confirmed"), result["events"].index("session_stop"), result)

    def test_integrity_loss_cancel_ack_without_terminal_confirmation_stays_unresolved(self):
        result = self.exercise(confirm=False, timeout=1)
        self.assertEqual(result["cancel_calls"], 1, result)
        self.assertFalse(result["confirmed_before_stop"], result)
        self.assertEqual(result["active_at_stop"], 1, result)
        self.assertEqual(result["unresolved"], 1, result)
        self.assertIn("integrity_loss_cancellation_unconfirmed", result["adapter_errors"], result)
        self.assertEqual(result["cancellations"], {"status": "deadline_expired", "requested_count": 1,
            "confirmed_count": 0, "unconfirmed_count": 1, "timeout_seconds": 1}, result)
        self.assertEqual(result["status"], "needs_attention", result)
        self.assertLess(result["elapsed"], 3, result)

    def test_mid_tick_loss_waits_for_native_cancel_without_another_rebalance(self):
        result = self.exercise(loss_during_mark=True)
        self.assertEqual(result["cancel_calls"], 1, result)
        self.assertTrue(result["confirmed_before_stop"], result)
        self.assertNotIn("rebalance_after_loss", result["events"], result)
        self.assertEqual(result["unresolved"], 0, result)
        self.assertEqual(result["adapter_errors"], [], result)
        self.assertEqual(result["cancellations"], {"status": "confirmed", "requested_count": 1,
            "confirmed_count": 1, "unconfirmed_count": 0, "timeout_seconds": 2}, result)
        self.assertLess(result["events"].index("loss_during_mark"),
                        result["events"].index("dispatcher_released"), result)
        self.assertLess(result["events"].index("confirmed"),
                        result["events"].index("session_stop"), result)

    def exercise(self, *, confirm=True, timeout=2, loss_during_mark=False):
        events = []
        original_stop = native_adapter.NativeSession.stop
        original_mark = Ledger.mark_to_market

        class RestingEntry(native_strategy.AdaptiveStrategy):
            def rebalance(self, now, *, force_exit=False):
                if loss_during_mark and "loss" in events:
                    events.append("rebalance_after_loss")
                if not self.enabled or getattr(self, "placed", False):
                    return
                self.placed = True
                cid = "synthetic-resting-entry"
                self.pending[cid] = {"symbol": "SPY", "side": "buy", "created": now}
                order = self.order_factory.limit(InstrumentId.from_str("SPY.ALPACA"),
                    OrderSide.BUY, Quantity.from_int(1), Price.from_str("100.01"),
                    time_in_force=TimeInForce.DAY, client_order_id=ClientOrderId(cid))
                self.submit_order(order)

        class Port(SimulatedPort):
            def __init__(self, controller):
                super().__init__(controller, ("SPY",))
                self.cancel_calls = 0
                self.confirmed = False
                self.active_at_stop = None
                self.confirmed_before_stop = False

            async def submit(self, payload):
                self.controller.before_submit(payload)
                await self.controller.before_request("submit", client_id=payload["client_order_id"])
                row = dict(payload, id="synthetic-broker-order", status="new", filled_qty="0",
                           filled_avg_price=None, updated_at_ns=time.time_ns())
                self.orders[payload["client_order_id"]] = row
                await invoke(self.sink_observation, dict(row))
                await invoke(self.on_order, dict(row))
                if loss_during_mark:
                    self.defer_loss_until_mark = True
                    while self.defer_loss_until_mark:
                        await asyncio.sleep(.01)
                else:
                    self.health["reasons"] = ["queue_overflow"]
                    self.ready = False
                    events.append("loss")
                await asyncio.sleep(.6)
                events.append("dispatcher_released")
                return dict(row)

            async def cancel(self, cid):
                self.cancel_calls += 1
                events.append("cancel_dispatched")
                await self.controller.before_request("cancel", client_id=cid)
                row = dict(self.orders[cid], status="pending_cancel", updated_at_ns=time.time_ns())
                if confirm:
                    await asyncio.sleep(.05)
                    row.update(status="canceled", updated_at_ns=time.time_ns())
                    self.confirmed = True
                    events.append("confirmed")
                self.orders[cid] = row
                await invoke(self.sink_observation, dict(row))
                await invoke(self.on_order, dict(row))
                return dict(row)

            async def stop(self):
                self.stopped += 1
                self.ready = False
                if self.task:
                    self.task.cancel()
                    await asyncio.gather(self.task, return_exceptions=True)

        def mark(ledger, *args, **kwargs):
            result = original_mark(ledger, *args, **kwargs)
            # run_native marks between its first health check and the check
            # after snapshot/refresh work. Keep the native dispatcher blocked.
            if loss_during_mark and getattr(port, "defer_loss_until_mark", False):
                port.defer_loss_until_mark = False
                port.health["reasons"] = ["queue_overflow"]
                port.ready = False
                events.extend(("loss", "loss_during_mark"))
            return result

        def stop(session):
            events.append("session_stop")
            session.port.confirmed_before_stop = session.port.confirmed
            session.port.active_at_stop = sum(row["status"] not in native_adapter.TERMINAL
                                             for row in session.port.orders.values())
            original_stop(session)

        config, _, policy = runner.load_config(SOURCE / "config.json")
        policy = replace(policy, symbols=("SPY",), benchmarks=("SPY",), max_positions=1)
        config.update(duration_seconds=3, cleanup_seconds=2, order_timeout_seconds=timeout)
        token = patch_default_stop()
        try:
            with tempfile.TemporaryDirectory(dir="/var/tmp") as scratch:
                with contextlib.closing(Ledger(Path(scratch) / "journal.db",
                                              RiskLimits(trial_seconds=3, cleanup_seconds=2))) as ledger:
                    ledger.start_trial(time.time())
                    controller = runner.Controller(ledger, time.time()+3600, market_open=True)
                    port = controller.port = Port(controller)
                    with patch.object(native_strategy, "AdaptiveStrategy", RestingEntry), \
                         patch.object(Ledger, "mark_to_market", mark), \
                         patch.object(native_adapter.NativeSession, "stop", stop):
                        outcome = asyncio.run(asyncio.wait_for(runner.run_native(controller, policy,
                            [{"symbol": "SPY"}], "cancel-dispatch-fixture", config, "100000"), 15))
                    return {"events": events, "cancel_calls": port.cancel_calls,
                            "confirmed_before_stop": port.confirmed_before_stop,
                            "active_at_stop": port.active_at_stop,
                            "unresolved": len(ledger.unresolved()),
                            "adapter_errors": outcome["adapter_errors"],
                            "cancellations": outcome.get("integrity_loss_cancellations"),
                            "status": outcome["status"], "elapsed": outcome["elapsed_seconds"]}
        finally:
            restore_default_stop(token)
