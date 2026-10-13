"""Refusal before broker access; these tests do not exercise cleanup or fills."""
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


class PlaceOnlyRefusalTests(unittest.TestCase):
    def test_config_refusal_precedes_every_broker_method(self):
        port = mock.Mock(evidence_class='synthetic')
        for method in ('preflight', 'submit', 'cancel', 'cancel_all', 'list_orders', 'positions',
                       'latest_quote', 'start_stream'):
            getattr(port, method).side_effect = AssertionError('broker method entered')
        with tempfile.TemporaryDirectory(dir='/var/tmp') as td:
            result = c.CapacityRun(port, c.CapacityConfig(place_only=True),
                clock=fx.FakeClock(), stop_file=Path(td) / 'STOP').run()
        self.assertEqual(result['status'], 'refused')
        self.assertEqual(result['refusal_reason'], 'place_only_requires_qualified_flat_recovery')
        self.assertEqual(result['stage'], 'config')
        self.assertEqual(result['orders']['submit_attempts'], 0)
        self.assertEqual(result['probe_plan']['cancel'], 'not attempted: place-only refused before broker access')
        self.assertEqual(port.mock_calls, [])

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
