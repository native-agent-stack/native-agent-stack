"""P1 controls at the public run/CLI/native-port seams; synthetic brokers only."""
from decimal import Decimal
import json
from pathlib import Path
import sys
import tempfile
import signal
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'blueprints/us-equities/order-throughput'))
import capacity as c
import capacity_fixture as fx
import alpaca_capacity_port as native
import runner


class PartialBulk(fx.FakeBroker):
    def cancel_all(self):
        self.cancel_all_calls += 1
        return c.Response(207, {'x-ratelimit-limit': '200'})


class Bulk429(fx.FakeBroker):
    def cancel_all(self):
        self.cancel_all_calls += 1
        return c.Response(429, {'x-ratelimit-remaining': '0', 'x-ratelimit-reset': '1790258460'})


class BulkException(fx.FakeBroker):
    def cancel_all(self):
        self.cancel_all_calls += 1
        raise RuntimeError('synthetic bulk failure')


class IncompleteGuard(fx.FakeBroker):
    def list_orders(self, *args, **kwargs):
        orders, complete, observations = super().list_orders(*args, **kwargs)
        if self.submit_count:
            complete = False
        return orders, complete, observations


class ForeignLate(fx.FakeBroker):
    def submit(self, *args):
        response = super().submit(*args)
        if self.submit_count == 1:
            self._create('foreign-late', 'SPY', '9')
        return response


class MarketMoves(fx.FakeBroker):
    fill_qty = '1'
    def latest_quote(self):
        if self.clock.monotonic() >= 1002:
            self.bid, self.ask = '9.00', '9.02'
            for order in self.orders.values():
                if order['status'] == 'new' and Decimal(order['limit_price']) >= Decimal(self.ask):
                    order.update(status='filled' if self.fill_qty == '1' else 'partially_filled',
                                 filled_qty=self.fill_qty)
                    self._emit('fill' if self.fill_qty == '1' else 'partial_fill', order)
        return super().latest_quote()


class PartialFill(MarketMoves):
    fill_qty = '0.5'


class PlaceOnlyRefusalTests(unittest.TestCase):
    def run_case(self, kind):
        clock = fx.FakeClock()
        broker = kind(clock, bid='10', ask='10.02')
        with tempfile.TemporaryDirectory(dir='/var/tmp') as td:
            run = c.CapacityRun(broker, c.CapacityConfig(place_only=True,
                max_duration_seconds=10, required_windows=1, max_orders=5, requote_seconds=5),
                clock=clock, executor=c.InlineExecutor(), stop_file=Path(td) / 'STOP',
                prefix='cap-20260924t140000-123456-')
            receipt = run.run()
        # Flat comes from an independent broker read, not the receipt's label.
        positions, _ = broker.positions()
        self.assertEqual(sum(Decimal(p['qty']) for p in positions), Decimal('0'))
        self.assertEqual(len(broker.open_orders_with_prefix(run.prefix)), 0)
        self.assertEqual(broker.submit_count, 0)
        self.assertEqual(broker.cancel_all_calls, 0)
        self.assertEqual(receipt['status'], 'refused')
        self.assertEqual(receipt['refusal_reason'], 'place_only_requires_qualified_flat_recovery')
        self.assertEqual(receipt['stage'], 'config')
        self.assertEqual(receipt['probe_plan']['cancel'], 'not attempted: place-only refused before broker access')

    def test_partial_207_leaves_zero_owned_orders_and_flat(self): self.run_case(PartialBulk)
    def test_bulk_429_leaves_zero_owned_orders_and_flat(self): self.run_case(Bulk429)
    def test_bulk_exception_leaves_zero_owned_orders_and_flat(self): self.run_case(BulkException)
    def test_incomplete_guard_leaves_zero_owned_orders_and_flat(self): self.run_case(IncompleteGuard)
    def test_late_foreign_arrival_leaves_zero_owned_orders_and_flat(self): self.run_case(ForeignLate)
    def test_delayed_market_move_full_fill_leaves_flat(self): self.run_case(MarketMoves)
    def test_delayed_market_move_partial_fill_leaves_flat(self): self.run_case(PartialFill)

    def test_foreign_orders_are_untouched_by_refusal(self):
        clock = fx.FakeClock()
        broker = fx.FakeBroker(clock, foreign_open_orders=1)
        before = json.dumps(broker.orders, sort_keys=True)
        result = c.CapacityRun(broker, c.CapacityConfig(place_only=True), clock=clock).run()
        self.assertEqual(result['status'], 'refused')
        self.assertEqual(json.dumps(broker.orders, sort_keys=True), before)
        self.assertEqual(broker.submit_count, 0)

    def test_paper_cli_refuses_before_credential_loader_and_writes_receipt(self):
        with tempfile.TemporaryDirectory(dir='/var/tmp') as td:
            output = Path(td) / 'receipt.json'
            handlers = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}
            try:
                with mock.patch.object(runner, 'credentials', side_effect=AssertionError('loader called')) as loader:
                    code = c.main(['paper', '--place-only', '--duration', '10', '--env-file', '/fixture/never-read.env',
                                   '--output', str(output)])
            finally:
                for sig, handler in handlers.items():
                    signal.signal(sig, handler)
            loader.assert_not_called()
            receipt = json.loads(output.read_text())
            self.assertEqual(code, 2)
            self.assertEqual(receipt['refusal_reason'], 'place_only_requires_qualified_flat_recovery')
            self.assertEqual(receipt['orders']['submit_attempts'], 0)
            self.assertTrue(receipt['probe_modes']['place_only'])

    def test_native_port_refuses_without_initializing_sdk_clients(self):
        with mock.patch.object(native.transport, '_sdk_client', side_effect=AssertionError('client created')) as sdk:
            with self.assertRaisesRegex(native.transport.TransportError, 'qualified flat recovery'):
                native.AlpacaCapacityPort('fixture', 'fixture', 'SPY', place_only=True)
            sdk.assert_not_called()


if __name__ == '__main__': unittest.main()
