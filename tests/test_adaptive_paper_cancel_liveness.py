"""Owned SELL/recovery cancellation liveness: real SDK, synthetic HTTP only."""
import asyncio
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import sys
import time
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit
from uuid import UUID

SOURCE = Path(__file__).resolve().parents[1] / 'blueprints/us-equities/adaptive-paper'
sys.path.insert(0, str(SOURCE))
try:
    from alpaca.trading.client import TradingClient
    import requests
except ImportError:
    TradingClient = None
try:
    from . import test_adaptive_paper_overnight_arming as fixtures
    from .test_adaptive_paper_transport import FakeStream
    from .adaptive_paper_hermetic import patch_default_stop, restore_default_stop
except ImportError:
    import test_adaptive_paper_overnight_arming as fixtures
    from test_adaptive_paper_transport import FakeStream
    from adaptive_paper_hermetic import patch_default_stop, restore_default_stop

def setUpModule():
    global _token
    _token = patch_default_stop()

def tearDownModule():
    restore_default_stop(_token)

@unittest.skipUnless(TradingClient, 'requires pinned alpaca-py runtime')
class CancelLiveness(unittest.TestCase):
    def test_held_sell_cancel_at_cutoff_retries_once_then_recovery_reaches_flat(self):
        self._exercise(recovery_first=False)

    def test_held_recovery_cancel_releases_on_terminal_lookup_without_second_delete(self):
        self._exercise(recovery_first=True)

    def _exercise(self, *, recovery_first):
        from recovery import recover
        from runner import reconcile
        from safety import Ledger, Quote
        from transport import AlpacaPaperTransport, normalize_order
        native_record = Ledger.record_order
        buy_id, sell_id = str(UUID(int=2)), str(UUID(int=1))

        def seed(ledger, cid, oid, *args, **kwargs):
            return native_record(ledger, cid, buy_id if oid == 'synthetic-entry' else oid, *args, **kwargs)

        with patch.object(Ledger, 'record_order', seed):
            c, clock, _, bounds, _ = fixtures.OvernightArming._controller(self, held=True)
        initial = clock[0]
        c.ledger.reserve_intent('exit', 'SPY', 'sell', '1', '10',
            quote=Quote('SPY', '10', '10.01', initial), now=initial,
            market_open=True, session_close=bounds['boundary_at'])
        c.ledger.record_overnight_window('exit', bounds)
        c.ledger.record_order('exit', sell_id, 'accepted', '0', None, timestamp=initial)
        clock[0] = bounds['flatten_at']
        stamp = datetime.fromtimestamp(clock[0], timezone.utc).isoformat()
        common = {'symbol': 'SPY', 'qty': '1', 'updated_at': stamp, 'type': 'limit',
                  'time_in_force': 'day', 'extended_hours': True}
        rows = {'entry': {**common, 'id': buy_id, 'client_order_id': 'entry', 'side': 'buy',
                         'limit_price': '10.01', 'filled_qty': '1', 'filled_avg_price': '10.01', 'status': 'filled'},
                'exit': {**common, 'id': sell_id, 'client_order_id': 'exit', 'side': 'sell',
                         'limit_price': '10', 'filled_qty': '0', 'filled_avg_price': None, 'status': 'accepted'}}
        broker = {'cash': Decimal('9989.99'), 'qty': Decimal('1')}
        calls, refusals, ports = [], [], []
        cancel_clock = [0.0]
        # Confirmation must outlast the fixed5s reconciliation interval. The
        # virtual cancel clock accelerates that interval; real CI scheduling
        # must not end recovery before the test advances it.
        config = {'cleanup_seconds': 20, 'order_timeout_seconds': 6,
            'quote_max_age_seconds': 1, 'regular_session_only': False,
            'extended_hours_enabled': True, 'sessions': {'extended_hours': True, 'overnight_holds': False},
            'feed': 'boats', 'quote_source': 'boats_rest', 'overnight': {'enabled': True}}

        async def exercise():
            def make_port():
                with patch('transport._stream_classes', return_value=(FakeStream, FakeStream)):
                    port = AlpacaPaperTransport('synthetic-key', 'synthetic-secret', ['SPY'],
                        before_request=c.before_request, before_submit=c.before_submit, sink_observation=c.observe,
                        sink_status=c.trading_status, quote_timeout=3,
                        feed='boats', quote_source_mode='boats_rest', overnight_enabled=True,
                        extended_hours_allowed=True, history_start=datetime.fromtimestamp(initial, timezone.utc))
                ports.append(port)
                port._loop = asyncio.get_running_loop()
                port._cancel_clock = lambda: cancel_clock[0]
                http = HTTP(port)
                port._client._session._session.close()
                port._client._session._session = http

                async def start(on_quote, on_order):
                    port._started = True
                    port._on_quote, port._on_order = on_quote, on_order
                    port._auth = port._acks = {'orders': True, 'quotes': True}
                    port._quote_seen['SPY'] = time.monotonic()
                    quote = {'symbol': 'SPY', 'bid': '10', 'ask': '10.01', 'ts_ns': int(clock[0] * 1e9)}
                    port._quote_values['SPY'] = quote
                    on_quote(quote)
                    c.trading_status({'symbol': 'SPY', 'source': 'alpaca_assets', 'ts_ns': quote['ts_ns'],
                        'overnight_tradable': True, 'overnight_halted': False,
                        'tradable': True, 'asset_status': 'active'})
                port.start = start
                c.port = c.bind(port)
                return port

            class HTTP:
                def __init__(self, port):
                    self.port, self.closed = port, False

                def request(self, method, url, **kwargs):
                    path = urlsplit(url).path
                    calls.append((method, path, self.closed))
                    payload, code = None, 200
                    if method == 'DELETE':
                        code = 204
                        if sum(m == 'DELETE' for m, _, _ in calls) > 1:
                            rows['exit']['status'] = 'canceled'
                    elif path.endswith('orders:by_client_order_id'):
                        cid = kwargs['params']['client_order_id']
                        payload = dict(rows[cid])
                        if cid == 'exit' and not refusals:
                            observation = dict(normalize_order(payload), event='order_cancel_rejected')
                            asyncio.run_coroutine_threadsafe(self.port._observe(observation), self.port._loop).result(3)
                            refusals.append(True)
                    elif method == 'POST':
                        body = kwargs['json']
                        cid = body['client_order_id']
                        payload = {**common, **body, 'id': str(UUID(int=10 + len(rows))),
                            'status': 'filled', 'filled_qty': str(body['qty']),
                            'filled_avg_price': str(body['limit_price'])}
                        rows[cid] = payload
                        broker['qty'] -= Decimal(str(body['qty']))
                        broker['cash'] += Decimal(str(body['qty'])) * Decimal(str(body['limit_price']))
                    elif path.endswith('/account'):
                        payload = {'cash': str(broker['cash']), 'equity': '10000', 'buying_power': '10000'}
                    elif path.endswith('/positions'):
                        payload = [] if not broker['qty'] else [{'symbol': 'SPY', 'qty': str(broker['qty']), 'avg_entry_price': '10.01'}]
                    elif path.endswith('/orders'):
                        payload = list(rows.values())
                    elif path.endswith('/FEE'):
                        payload = []
                    else:
                        raise AssertionError('unexpected synthetic HTTP path')
                    response = requests.Response()
                    response.status_code = code
                    response._content = b'' if code == 204 else json.dumps(payload).encode()
                    return response

                def close(self):
                    self.closed = True

            port = make_port()
            task = None
            try:
                if recovery_first:
                    task = asyncio.create_task(recover(c,
                        {'trial_id': 'held-recovery', 'baseline_cash': '10000'}, config, reconcile_fn=reconcile))
                else:
                    await port.start(c.quote, c.observe)
                    port.adopt_intents([{k: row[k] for k in ('client_order_id', 'symbol', 'side', 'qty', 'limit_price',
                                                           'type', 'time_in_force', 'extended_hours')}
                                       for row in rows.values()])
                    port._observed = {cid: normalize_order(row) for cid, row in rows.items()}
                    c._overnight_cancel_pending.add('exit')
                    await port.cancel('exit')
                for _ in range(2000):
                    if refusals and not port.cancel_in_flight('exit'):
                        break
                    await asyncio.sleep(.001)
                self.assertEqual(len(refusals), 1)
                # Task.done() precedes scheduled add_done_callback handlers.
                # Settle completion before advancing the virtual cancel clock,
                # otherwise the callback may anchor its5s bound at4.99s.
                await asyncio.sleep(0)
                pending = getattr(port, 'cancel_pending', None)
                self.assertTrue(pending('exit') if callable(pending) else 'exit' in c._overnight_cancel_pending,
                                'a held SELL/recovery cancel must retain broker pending ownership')
                self.assertEqual(sum(m == 'DELETE' for m, _, _ in calls), 1)
                cancel_clock[0] = 4.99
                await asyncio.sleep(.1)
                self.assertEqual(sum(m == 'DELETE' for m, _, _ in calls), 1,
                                 'a held SELL/recovery cancellation permits no per-tick DELETE')
                if recovery_first:
                    rows['exit']['status'] = 'canceled'  # broker terminal at next independent lookup
                cancel_clock[0] = 5.0
                for _ in range(2000):
                    if c.ledger.intents()[1].terminal and not port.cancel_pending('exit'):
                        break
                    await asyncio.sleep(.001)
                self.assertEqual(sum(m == 'DELETE' for m, _, _ in calls), 1 if recovery_first else 2)
                self.assertFalse(port.cancel_pending('exit'),
                    {'stopping': port._stopping, 'recovery_done': task is not None and task.done(),
                     'cancel_clock': cancel_clock[0],
                     'next_lookup_at': port._cancel_book.current['exit'].next_lookup_at,
                     'local_completion_applied': port._cancel_book.current['exit'].finished,
                     'recovery_result': task.result() if task is not None and task.done() else None})
                counters = port.cancellation_counters()
                self.assertEqual(counters, {'held_unattributed_refusals': 1,
                                           'lookup_confirmed_retries': 0 if recovery_first else 1})
                if not recovery_first:
                    await port.stop()
                    port = make_port()  # recovery starts with its required fresh, unstarted transport
                    result = await recover(c, {'trial_id': 'held-sell', 'baseline_cash': '10000'},
                                           config, reconcile_fn=reconcile)
                else:
                    result = await asyncio.wait_for(task, 10)
                    self.assertEqual(result['cancellation_counters'], counters)
                self.assertTrue(result['flat'], result)
                self.assertEqual(c.ledger.positions(), {})
                self.assertEqual(c.ledger.unresolved(), [])
                self.assertEqual(sum(m == 'POST' for m, _, _ in calls), 1)
                self.assertTrue(all(not closed for _, _, closed in calls))
                print('held_sell_recovery', recovery_first, 'flat', result['flat'],
                      'deletes', sum(m == 'DELETE' for m, _, _ in calls), 'counters', counters, flush=True)
            finally:
                if task is not None:
                    await asyncio.gather(task, return_exceptions=True)
                for port in ports:
                    await port.stop()

        with patch('transport.time.time_ns', side_effect=lambda: int(clock[0] * 1e9)):
            asyncio.run(exercise())
