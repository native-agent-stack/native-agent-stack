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

    def test_rejection_during_lookup_releases_pending_and_allows_one_retry(self):
        for status in (OrderStatus.ACCEPTED, OrderStatus.NEW, OrderStatus.PENDING_CANCEL):
            for terminal_source in ('stream', 'lookup'):
                with self.subTest(status=status.value, terminal_source=terminal_source):
                    self._exercise(status, terminal_source, reject_first=True)

    def test_old_refusal_never_releases_a_newer_acknowledged_cancel(self):
        # Astra's delayed/replay probe, including missing broker request identity.
        # One refusal may permit B, never C. Unknown stream provenance permits none.
        for mode in ('replay', 'delayed'):
            for identified in (False, True):
                for delivery in ('lookup', 'completed'):
                    with self.subTest(mode=mode, identified=identified, delivery=delivery):
                        self._exercise(OrderStatus.ACCEPTED, 'stream', reject_first=True,
                                       replay=mode, identified=identified, delivery=delivery)
        # A failed A with no observed broker key makes a later unchanged marker
        # ambiguous, even if B's lookup and delayed A refusal now carry it.
        self._exercise(OrderStatus.ACCEPTED, 'stream', reject_first=True,
                       replay='delayed', missing_first_marker=True)

    def test_http_acknowledgement_survives_a_failed_followup_lookup(self):
        self._exercise(OrderStatus.ACCEPTED, 'stream', lookup_failure=True)

    def test_held_cancel_reconciles_on_a_fixed_bound_before_any_retry(self):
        for status in ('canceled', 'accepted', 'pending_cancel'):
            with self.subTest(lookup_status=status):
                self._exercise(OrderStatus.ACCEPTED, 'stream', reject_first=True,
                               identified=False, reconcile_status=status)

    def test_cutoff_held_entry_reconciles_then_owned_position_flattens(self):
        self._exercise(OrderStatus.ACCEPTED, 'stream', reject_first=True,
                       identified=False, reconcile_status='accepted', cutoff_flat=True)

    def _exercise(self, status, terminal_source, reject_first=False, *, replay=None,
                  identified=True, delivery='lookup', missing_first_marker=False,
                  lookup_failure=False, reconcile_status=None, cutoff_flat=False):
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
        if cutoff_flat:
            from safety import Quote
            now = clock[0]
            held = c.ledger.reserve_intent('held', 'SPY', 'buy', '1', '10.01',
                quote=Quote('SPY', '10', '10.01', now), now=now, market_open=True,
                session_close=bounds['boundary_at'])
            c.ledger.record_overnight_window(held.client_id, bounds)
            c.ledger.record_order('held', str(UUID(int=2)), 'filled', '1', '10.01', timestamp=now)

        async def exercise():
            payload = {'id': broker_id, 'client_order_id': 'entry', 'symbol': 'SPY', 'side': 'buy',
                'qty': '1', 'limit_price': '10.01', 'filled_qty': '0', 'filled_avg_price': None,
                'status': status.value,
                'updated_at': datetime.fromtimestamp(clock[0], timezone.utc).isoformat()}
            calls, closed, frozen, rejections = [], [], [], []
            first_refusal = []

            async def deliver(observation):
                await port._observe(dict(observation))

            def stream_refusal():
                observation = dict(first_refusal[0])
                asyncio.run_coroutine_threadsafe(deliver(observation), port._loop).result(3)
                rejections.append(True)

            class HTTP:
                def request(self, method, url, **kwargs):
                    calls.append((method, bool(closed)))
                    deletes = sum(m == 'DELETE' for m, _ in calls)
                    if method == 'DELETE' and identified:
                        # Broker-owned request marker, distinct from updated_at.
                        # The latter intentionally stays EQUAL across all attempts.
                        payload['cancel_requested_at'] = datetime.fromtimestamp(
                            clock[0] + (1 if missing_first_marker else deletes) / 1000,
                            timezone.utc).isoformat()
                    if method == 'DELETE' and not first_refusal:
                        first_refusal.append(dict(normalize_order(payload), event='order_cancel_rejected'))
                    should_reject = (not rejections or (replay == 'replay' and len(rejections) < 2))
                    if replay == 'delayed':
                        should_reject = not rejections and deletes >= 2
                    if method == 'GET' and reject_first and should_reject and delivery == 'lookup':
                        # Deliver the real normalized stream observation while
                        # the synchronous SDK getter/follow-up lookup is live.
                        stream_refusal()
                    response = requests.Response()
                    response.status_code = 204 if method == 'DELETE' else 200
                    if lookup_failure and method == 'GET':
                        response.status_code = 500
                    if method == 'DELETE' and deletes == 1 and (replay == 'delayed' or delivery == 'completed'):
                        response.status_code = 422
                    response._content = b'' if method == 'DELETE' else json.dumps(payload).encode()
                    if method == 'GET' and deletes == 1 and missing_first_marker:
                        response._content = json.dumps({k: v for k, v in payload.items()
                                                       if k != 'cancel_requested_at'}).encode()
                    if response.status_code == 422:
                        response._content = json.dumps({'message': 'synthetic cancellation refused', 'code': 42210000}).encode()
                    if response.status_code == 500:
                        response._content = json.dumps({'message': 'synthetic lookup failure'}).encode()
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
            cancel_clock = [0.0]
            port._cancel_clock = lambda: cancel_clock[0]
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
                    if delivery == 'completed' and len(states) == 1:
                        await deliver(first_refusal[0])
                        await deliver(first_refusal[0])  # duplicate after B's task is gone
                        rejections.extend((True, True))
                    strategies()
                    states.append({'deletes': sum(method == 'DELETE' for method, _ in calls),
                        'controller_pending': 'entry' in c._overnight_cancel_pending,
                        'adaptive_pending': info['cancel_requested'],
                        'mover_pending': record.cancel_requested})
                print('ack_three_ticks', status.value, terminal_source, 'refusal', reject_first, json.dumps(states), flush=True)
                retry = reject_first and (identified or replay == 'delayed' or delivery == 'completed')
                expected = [1, 2, 2] if retry else [1, 1, 1]
                self.assertEqual([s['deletes'] for s in states], expected,
                                 'a refusal permits one retry; an acknowledged live cancellation permits none')
                expected_pending = [False, True, True] if retry else [True, True, True]
                for key in ('controller_pending', 'adaptive_pending', 'mover_pending'):
                    self.assertEqual([s[key] for s in states], expected_pending, key)
                self.assertEqual(sum(r['kind'] == 'cancel' for r in c.requests), 2 if retry else 1)
                self.assertEqual(len(rejections), (2 if delivery == 'completed' or replay == 'replay' and retry else int(reject_first)))
                self.assertEqual(frozen, ['cancel_finality_unobserved'] if lookup_failure else
                    ['cancellation_unresolved'] if replay == 'delayed' or delivery == 'completed' else [])
                self.assertEqual(engine_cancels, [])
                self.assertEqual(len(c.ledger.unresolved()), 1)
                self.assertFalse(port.cancel_in_flight('entry'), 'the local SDK operation has finished')
                if reconcile_status is not None:
                    gets = sum(m == 'GET' for m, _ in calls)
                    payload['status'] = reconcile_status
                    cancel_clock[0] = 4.99
                    await asyncio.sleep(.1)
                    self.assertEqual(sum(m == 'GET' for m, _ in calls), gets)
                    cancel_clock[0] = 5.0
                    expected_gets = gets + (2 if reconcile_status == 'accepted' else 1)
                    for _ in range(2000):
                        if sum(m == 'GET' for m, _ in calls) >= expected_gets and not port.cancel_in_flight('entry'):
                            break
                        await asyncio.sleep(.001)
                    self.assertEqual(sum(m == 'GET' for m, _ in calls), expected_gets,
                                     'a held cancellation needs autonomous lookup even without owner ticks')
                    if reconcile_status == 'accepted':
                        self.assertEqual(sum(m == 'DELETE' for m, _ in calls), 2)
                        for _ in range(3):
                            await c.overnight_tick(clock[0])
                            await asyncio.sleep(0)
                        self.assertEqual(sum(m == 'DELETE' for m, _ in calls), 2,
                                         'one lookup-confirmed retry per bound, never per tick')
                    elif reconcile_status == 'pending_cancel':
                        self.assertIn('entry', c._overnight_cancel_pending)
                        self.assertEqual(sum(m == 'DELETE' for m, _ in calls), 1)
                    else:
                        self.assertNotIn('entry', c._overnight_cancel_pending)
                        self.assertEqual(c.ledger.unresolved(), [])
                    counters = port.cancellation_counters()
                    self.assertEqual(counters['held_unattributed_refusals'], 1)
                    self.assertEqual(counters['lookup_confirmed_retries'],
                                     int(reconcile_status == 'accepted'))
                    from runner import _stream_health
                    end = _stream_health(port)
                    self.assertEqual({key: end[key] for key in counters}, counters,
                                     'nonzero cancellation counters must survive into the stage-end receipt')
                    print('cancel_stage_end', json.dumps(counters, sort_keys=True), flush=True)
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
                self.assertEqual(sum(method == 'DELETE' for method, _ in calls),
                                 2 if reconcile_status == 'accepted' else expected[-1])
                if cutoff_flat:
                    # Real cutoff controller/SDK held-cancel above, then the
                    # production deterministic recovery exit loop with the
                    # repository's synthetic fill/position oracle. No live I/O.
                    from decimal import Decimal
                    from recovery import recover
                    try:
                        from .test_adaptive_paper_recovery import FakePort, proof
                    except ImportError:
                        from test_adaptive_paper_recovery import FakePort, proof
                    self.assertEqual(c.ledger.positions()['SPY'].qty, Decimal('1'))
                    await port.stop()
                    simulated = FakePort(c)
                    simulated.rows = {'entry': normalize_order(payload), 'held': {
                        **normalize_order(payload), 'id': str(UUID(int=2)),
                        'client_order_id': 'held', 'status': 'filled',
                        'filled_qty': '1', 'filled_avg_price': '10.01'}}
                    simulated.qty = Decimal('1')
                    simulated.cash = Decimal('10000') + c.ledger.accounting().cash_delta_usd
                    c.port = simulated
                    config = {'cleanup_seconds': 3, 'order_timeout_seconds': .1,
                        'quote_max_age_seconds': 1, 'regular_session_only': False,
                        'extended_hours_enabled': True,
                        'sessions': {'extended_hours': True, 'overnight_holds': False}}
                    result = await recover(c, {'trial_id': 'cutoff-held', 'baseline_cash': '10000'},
                                           config, reconcile_fn=proof)
                    self.assertTrue(result['flat'], result)
                    self.assertEqual(c.ledger.positions(), {})
                    self.assertEqual(c.ledger.unresolved(), [])
                    self.assertEqual(len(simulated.submissions), 1)
                    self.assertEqual(simulated.submissions[0]['side'], 'sell')
            finally:
                await c.stop_overnight_cancels()
                await port.stop()
                self.assertTrue(all(not after_close for _, after_close in calls))

        asyncio.run(exercise())
