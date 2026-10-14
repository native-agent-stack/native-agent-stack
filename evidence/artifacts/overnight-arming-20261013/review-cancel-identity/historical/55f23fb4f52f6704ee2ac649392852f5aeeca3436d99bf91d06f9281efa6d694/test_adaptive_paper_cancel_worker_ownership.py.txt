"""Pinned SDK cancellation ownership; synthetic HTTP and budget boundaries only."""
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch
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
class CancelWorkerOwnership(unittest.TestCase):
    def test_sdk_delete_survives_timeout_and_is_joined_before_session_close(self):
        self._exercise('http', 5.0)

    def test_budget_wait_retains_one_operation_and_shutdown_joins_it(self):
        self._exercise('budget', .05)

    def test_late_completion_cannot_launch_a_duplicate_delete(self):
        self._exercise('http', .05, shutdown_before_release=False)

    def test_shutdown_cancels_an_operation_still_waiting_for_the_owner_lock(self):
        self._exercise('queued', .05)

    def test_failed_halt_delete_clears_strategy_mark_and_retries_before_flatten(self):
        self._exercise('refusal', .05, shutdown_before_release=False)

    def _exercise(self, boundary, timeout, shutdown_before_release=True):
        import runner
        from transport import AlpacaPaperTransport, GuardedSession, PAPER_URL, normalize_order
        from safety import Ledger
        record_order = Ledger.record_order
        broker_id = str(UUID(int=1))

        def seed_order(ledger, cid, oid, *args, **kwargs):
            # Give the durable synthetic seed the UUID required by the real SDK.
            return record_order(ledger, cid, broker_id if oid == 'synthetic-entry' else oid,
                                *args, **kwargs)

        with patch.object(Ledger, 'record_order', seed_order):
            c, clock, _, bounds, _ = fixtures.OvernightArming._controller(self)

        async def exercise():
            entered, release = threading.Event(), threading.Event()
            worker_calls, finished, http_calls, closed = [], [], [], []
            payload = {'id': broker_id,
                       'client_order_id': 'entry', 'symbol': 'SPY', 'side': 'buy',
                       'qty': '1', 'limit_price': '10.01', 'filled_qty': '0',
                       'filled_avg_price': None, 'status': 'accepted',
                       'updated_at': datetime.fromtimestamp(clock[0], timezone.utc).isoformat()}

            class HTTP:
                def request(self, method, url, **kwargs):
                    http_calls.append((method, bool(closed)))
                    if method == 'DELETE' and boundary in ('http', 'refusal'):
                        entered.set()
                        if not release.wait(15):
                            raise RuntimeError('synthetic HTTP boundary was not released')
                    response = requests.Response()
                    refuse = boundary == 'refusal' and len(worker_calls) == 1
                    response.status_code = (422 if refuse else 204) if method == 'DELETE' else 200
                    response._content = (json.dumps({'message': 'synthetic DELETE refusal'}).encode()
                        if method == 'DELETE' and refuse else b'' if method == 'DELETE' else
                        json.dumps({**payload, 'status': 'accepted' if refuse else 'canceled'}).encode())
                    return response

                def close(self):
                    closed.append(True)

            guarded = GuardedSession(origin=PAPER_URL, before_request=lambda *a, **k: None)
            guarded._session.close()
            guarded._session = HTTP()
            client = TradingClient('synthetic-key', 'synthetic-secret', paper=True, raw_data=True)
            client._session.close()
            client._session = guarded
            sdk_cancel = client.cancel_order_by_id

            def tracked_cancel(order_id):
                worker_calls.append(order_id)
                try:
                    return sdk_cancel(order_id)
                finally:
                    finished.append(bool(closed))

            client.cancel_order_by_id = tracked_cancel
            port = AlpacaPaperTransport.__new__(AlpacaPaperTransport)
            port._operation_lock, port._observation_lock = asyncio.Lock(), asyncio.Lock()
            port._loop = asyncio.get_running_loop()
            port._client = client
            port._intents = {'entry': {k: payload[k] for k in
                ('client_order_id', 'symbol', 'side', 'qty', 'limit_price')}}
            port._observed, port._executions = {'entry': normalize_order(payload)}, {}
            port._terminal_stream_health = {}
            port._orders_stream = port._quotes_stream = None
            port._tasks, port._threads, port._boats_clients = [], [], {}
            port.quote_source_mode, port.feed = 'boats_rest', 'boats'
            port._started, port._stopping = True, False
            from overnight import BoatsQuoteSource
            port._boats_source = BoatsQuoteSource(['SPY'], lambda symbol: None, lambda symbol: None)
            port.overnight_enabled, port.flatten_minutes_before_pre = True, 10
            frozen = []
            port.freeze_health = frozen.append
            port.sink_observation = c.observe

            async def before_request(kind, client_id=None):
                if kind == 'cancel' and boundary == 'budget':
                    entered.set()
                    while not release.is_set():
                        await asyncio.sleep(.001)
                return await c.before_request(kind, client_id=client_id)

            port.before_request = before_request
            guarded.before_request = port._budget_sync
            c.port = c.bind(port)
            engine_cancels, retry_tasks = [], []
            info = {'side': 'buy', 'symbol': 'SPY', 'created': clock[0], 'cancel_requested': False}

            def engine_cancel(cid):
                self.assertFalse(info['cancel_requested'], 'resolved background failure must clear the strategy mark')
                engine_cancels.append(str(cid))
                retry_tasks.append(asyncio.create_task(port.cancel(str(cid))))

            owner = SimpleNamespace(pending={'entry': info}, transport=port,
                                    _halted=c.is_halted, cancel_order=engine_cancel)
            if boundary == 'refusal':
                from native_strategy import AdaptiveStrategy
            stop_task = None
            if boundary == 'queued':
                await port._operation_lock.acquire()
            try:
                with patch.object(runner, 'OVERNIGHT_CANCEL_TIMEOUT_SECONDS', timeout):
                    clock[0] = info['created'] + 10 if boundary == 'refusal' else bounds['flatten_at']
                    if boundary == 'refusal':
                        c.trading_status({'symbol': 'SPY', 'source': 'alpaca_assets',
                            'ts_ns': int(clock[0] * 1e9), 'overnight_tradable': True,
                            'overnight_halted': True, 'tradable': True, 'asset_status': 'active'})
                    force = await asyncio.wait_for(c.overnight_tick(clock[0]), 1)
                    if boundary == 'refusal':
                        AdaptiveStrategy.cancel_expired(owner, clock[0], 60)
                        self.assertTrue(info['cancel_requested'])
                    else:
                        self.assertTrue(force)
                    if boundary == 'queued':
                        await asyncio.sleep(.02)
                        await c.stop_overnight_cancels()
                        stop_task = asyncio.create_task(port.stop())
                        await asyncio.sleep(.05)
                        self.assertTrue(stop_task.done(), 'shutdown must cancel an operation not yet started')
                        self.assertEqual(worker_calls, [])
                        self.assertEqual(http_calls, [])
                        await stop_task
                        self.assertTrue(closed)
                        return
                    for _ in range(1000):
                        if entered.is_set():
                            break
                        await asyncio.sleep(.001)
                    self.assertTrue(entered.is_set())
                    await asyncio.sleep(timeout + .05)
                    live_pending = 'entry' in c._overnight_cancel_pending
                    if boundary == 'refusal':
                        clock[0] = info['created'] + 130
                        c.trading_status({'symbol': 'SPY', 'source': 'alpaca_assets',
                            'ts_ns': int(clock[0] * 1e9), 'overnight_tradable': True,
                            'overnight_halted': False, 'tradable': True, 'asset_status': 'active'})
                        await c.overnight_tick(clock[0])
                        AdaptiveStrategy.cancel_expired(owner, clock[0], 60)
                        self.assertEqual(engine_cancels, [], 'strategy must not overlap the live SDK operation')
                        release.set()
                        for _ in range(1000):
                            if finished:
                                break
                            await asyncio.sleep(.001)
                        await asyncio.sleep(.05)
                        self.assertNotIn('entry', c._overnight_cancel_pending)
                        AdaptiveStrategy.cancel_expired(owner, clock[0], 60)
                        self.assertEqual(engine_cancels, ['entry'],
                                         'halt clear plus order timeout must retry before flatten_at')
                        self.assertTrue(live_pending, 'controller must retain ownership beyond the wrapper timeout')
                        self.assertIn('cancellation_unresolved', frozen)
                        await asyncio.gather(*retry_tasks)
                        self.assertEqual(len(worker_calls), 2)
                        self.assertEqual(c.ledger.unresolved(), [])
                        return
                    self.assertTrue(await asyncio.wait_for(c.overnight_tick(clock[0]), 1))
                    await asyncio.sleep(.05)
                    self.assertEqual(len(worker_calls), 1,
                                     'one in-flight SDK DELETE must survive wrapper timeout; no second worker')
                    self.assertTrue(live_pending, 'controller must retain ownership beyond the wrapper timeout')
                    if boundary == 'http':
                        c.observe(normalize_order({**payload, 'status': 'canceled'}))
                        self.assertIn('entry', c._overnight_cancel_pending,
                                      'a terminal stream observation must not abandon an active SDK worker')
                    if not shutdown_before_release:
                        release.set()
                        for _ in range(1000):
                            if not c.ledger.unresolved():
                                break
                            await asyncio.sleep(.001)
                        await asyncio.sleep(.05)
                        self.assertEqual(len(worker_calls), 1,
                                         'late completion must not release a queued duplicate DELETE')
                    c.stop = True
                    await c.stop_overnight_cancels()
                    stop_task = asyncio.create_task(port.stop())
                    await asyncio.sleep(.05)
                    if shutdown_before_release:
                        self.assertFalse(stop_task.done(), 'shutdown must join the started SDK operation')
                        self.assertFalse(closed, 'the HTTP session must stay open while a worker owns it')
                    release.set()
                    await asyncio.wait_for(stop_task, 3)
                    self.assertEqual(len(worker_calls), 1)
                    self.assertEqual(finished, [False], 'worker must finish before session close')
                    self.assertTrue(closed)
                    self.assertTrue(all(not after_close for _, after_close in http_calls))
                    self.assertEqual(sum(r['kind'] == 'cancel' for r in c.requests), 1)
                    self.assertEqual(c.ledger.unresolved(), [])
                    self.assertNotIn('entry', c._overnight_cancel_pending)
            finally:
                release.set()
                if boundary == 'queued' and port._operation_lock.locked():
                    port._operation_lock.release()
                await c.stop_overnight_cancels()
                if stop_task is not None:
                    await asyncio.gather(stop_task, return_exceptions=True)
                else:
                    await port.stop()

        asyncio.run(exercise())
