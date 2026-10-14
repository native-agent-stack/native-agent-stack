"""Real pinned SDK acknowledgement followed by a live lookup; synthetic HTTP only."""
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from uuid import UUID

SOURCE = Path(__file__).resolve().parents[1] / 'blueprints/us-equities/adaptive-paper'
sys.path.insert(0, str(SOURCE))
try:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.enums import OrderStatus
    import requests
except ImportError:
    TradingClient = None
try:
    from . import test_adaptive_paper_overnight_arming as fixtures
    from .adaptive_paper_hermetic import patch_default_stop, restore_default_stop
except ImportError:
    import test_adaptive_paper_overnight_arming as fixtures
    from adaptive_paper_hermetic import patch_default_stop, restore_default_stop

def setUpModule():
    global _token
    _token = patch_default_stop()

def tearDownModule():
    restore_default_stop(_token)

@unittest.skipUnless(TradingClient, 'requires pinned alpaca-py runtime')
class CancelAcknowledgement(unittest.TestCase):
    def test_three_ticks_keep_acknowledged_live_cancel_pending_until_terminal(self):
        for status in (OrderStatus.ACCEPTED, OrderStatus.NEW, OrderStatus.PENDING_CANCEL):
            for terminal_source in ('stream', 'lookup'):
                with self.subTest(status=status.value, terminal_source=terminal_source):
                    self._exercise(status, terminal_source)

    def _exercise(self, status, terminal_source):
        from native_strategy import AdaptiveStrategy
        from mover import MoverBook
        from safety import Ledger
        from transport import AlpacaPaperTransport, GuardedSession, PAPER_URL, normalize_order
        broker_id = str(UUID(int=1))
        record_order = Ledger.record_order

        def seed(ledger, cid, oid, *args, **kwargs):
            return record_order(ledger, cid, broker_id if oid == 'synthetic-entry' else oid,
                                *args, **kwargs)

        with patch.object(Ledger, 'record_order', seed):
            c, clock, _, bounds, _ = fixtures.OvernightArming._controller(self)

        async def exercise():
            payload = {'id': broker_id, 'client_order_id': 'entry', 'symbol': 'SPY', 'side': 'buy',
                'qty': '1', 'limit_price': '10.01', 'filled_qty': '0', 'filled_avg_price': None,
                'status': status.value,
                'updated_at': datetime.fromtimestamp(clock[0], timezone.utc).isoformat()}
            calls, closed, frozen = [], [], []

            class HTTP:
                def request(self, method, url, **kwargs):
                    calls.append((method, bool(closed)))
                    response = requests.Response()
                    response.status_code = 204 if method == 'DELETE' else 200
                    response._content = b'' if method == 'DELETE' else json.dumps(payload).encode()
                    return response

                def close(self):
                    closed.append(True)

            guarded = GuardedSession(origin=PAPER_URL, before_request=lambda *a, **k: None)
            guarded._session.close()
            guarded._session = HTTP()
            client = TradingClient('synthetic-key', 'synthetic-secret', paper=True, raw_data=True)
            client._session.close()
            client._session = guarded
            port = AlpacaPaperTransport.__new__(AlpacaPaperTransport)
            port._operation_lock, port._observation_lock = asyncio.Lock(), asyncio.Lock()
            port._loop, port._client = asyncio.get_running_loop(), client
            port._intents = {'entry': {k: payload[k] for k in
                ('client_order_id', 'symbol', 'side', 'qty', 'limit_price')}}
            port._observed, port._executions = {'entry': normalize_order(payload)}, {}
            port._terminal_stream_health = {}
            port._orders_stream = port._quotes_stream = None
            port._tasks, port._threads, port._boats_clients = [], [], {}
            port.quote_source_mode, port.feed = 'boats_rest', 'boats'
            port._started, port._stopping = True, False
            from overnight import BoatsQuoteSource
            port._boats_source = BoatsQuoteSource(['SPY'], lambda s: None, lambda s: None)
            port.overnight_enabled, port.flatten_minutes_before_pre = True, 10
            port.freeze_health, port.sink_observation = frozen.append, c.observe
            port.before_request = c.before_request
            guarded.before_request = port._budget_sync
            c.port = c.bind(port)
            clock[0] = bounds['flatten_at']
            info = {'side': 'buy', 'symbol': 'SPY', 'created': clock[0], 'cancel_requested': False}
            engine_cancels = []
            adaptive = SimpleNamespace(pending={'entry': info}, transport=port,
                _halted=c.is_halted, cancel_order=lambda cid: engine_cancels.append(str(cid)))
            record = SimpleNamespace(client_id='entry', side='buy', created=clock[0],
                cancel_requested=False, overnight_cancel_requested=False, cancel_reason=None)
            mover = SimpleNamespace(open_orders=lambda symbol: [record], _halted=c.is_halted,
                _cancel_pending=c._overnight_cancel_pending.__contains__, events=lambda event: None,
                plan=SimpleNamespace(timing=SimpleNamespace(
                    entry_timeout_seconds=float('inf'), exit_timeout_seconds=float('inf'))))
            leg = SimpleNamespace(exit_reason=None)

            def strategies():
                AdaptiveStrategy.cancel_expired(adaptive, clock[0], float('inf'))
                self.assertEqual(MoverBook._cancels(mover, leg, 'SPY', clock[0], None), [])

            states = []
            try:
                for _ in range(3):
                    await c.overnight_tick(clock[0])
                    strategies()
                    await asyncio.gather(*list(c._overnight_cancel_tasks.values()))
                    await asyncio.sleep(0)
                    strategies()
                    states.append({'deletes': sum(method == 'DELETE' for method, _ in calls),
                        'controller_pending': 'entry' in c._overnight_cancel_pending,
                        'adaptive_pending': info['cancel_requested'],
                        'mover_pending': record.cancel_requested})
                print('ack_three_ticks', status.value, terminal_source, json.dumps(states), flush=True)
                self.assertEqual([s['deletes'] for s in states], [1, 1, 1],
                                 'an acknowledged live cancellation must not send another DELETE')
                self.assertTrue(all(s['controller_pending'] and s['adaptive_pending'] and s['mover_pending']
                                    for s in states), 'broker acknowledgement must retain all pending marks')
                self.assertEqual(sum(r['kind'] == 'cancel' for r in c.requests), 1)
                self.assertEqual(frozen, [])
                self.assertEqual(engine_cancels, [])
                self.assertEqual(len(c.ledger.unresolved()), 1)
                self.assertFalse(port.cancel_in_flight('entry'), 'the local SDK operation has finished')
                payload['status'] = OrderStatus.CANCELED.value
                if terminal_source == 'lookup':
                    await port._lookup('entry')
                else:
                    await port._observe(normalize_order(payload))
                strategies()
                self.assertNotIn('entry', c._overnight_cancel_pending)
                self.assertFalse(info['cancel_requested'])
                self.assertFalse(record.cancel_requested)
                self.assertEqual(c.ledger.unresolved(), [])
                await c.overnight_tick(clock[0])
                self.assertEqual(sum(method == 'DELETE' for method, _ in calls), 1)
            finally:
                await c.stop_overnight_cancels()
                await port.stop()
                self.assertTrue(all(not after_close for _, after_close in calls))

        asyncio.run(exercise())
