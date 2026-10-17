"""Shared runner sell chunks through real policy, quantities and durable Ledger.

Synthetic dispatch simulates the broker-facing submit/fill boundary. No credentials or
broker/GO calls; paper/account state is confined to the temporary root.
"""
from dataclasses import replace
import asyncio
from datetime import datetime, timezone
from decimal import Decimal as D
import builtins
import importlib.util
import io
import os
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / 'blueprints/us-equities/adaptive-paper'
sys.path.insert(0, str(SOURCE))
NATIVE = importlib.util.find_spec('nautilus_trader') is not None


def setUpModule():
    # Lexical comparison only: even a failing isolation test must never stat,
    # open, read or write the host latch. Guard below pathlib as well as open().
    host_latch = str(Path.home() / '.local/state/native-agent-stack/alpaca-paper/STOP')
    attempted = []

    def guard(original):
        def checked(path, *args, **kwargs):
            if not isinstance(path, int) and os.path.abspath(os.fsdecode(path)) == host_latch:
                attempted.append(original.__name__)
                raise AssertionError('test attempted filesystem access to the live STOP latch')
            return original(path, *args, **kwargs)
        return checked

    for module, name in ((os, 'stat'), (os, 'lstat'), (os, 'open'),
                         (io, 'open'), (builtins, 'open')):
        blocker = patch.object(module, name, guard(getattr(module, name)))
        blocker.start()
        unittest.addModuleCleanup(blocker.stop)

    def assert_no_live_latch_access():
        if attempted:
            raise AssertionError(f'blocked live STOP operations: {attempted}')
    unittest.addModuleCleanup(assert_no_live_latch_access)


if NATIVE:
    from native_strategy import AdaptiveStrategy
    from runner import load_config
    from safety import Ledger, Quote, SafetyError
    import safety
    from strategies import AdaptivePolicy

    class CapturedOrderFactory:
        def limit(self, instrument_id, side, quantity, price, *, time_in_force, client_order_id, tags):
            return SimpleNamespace(instrument_id=instrument_id, side=side, quantity=quantity,
                                   price=price, client_order_id=client_order_id, tags=tags)

    class NativeDispatch(AdaptiveStrategy):
        @property
        def order_factory(self):
            return self.captured_factory

    class NativeExitProbe(AdaptiveStrategy):
        """Observe real submissions without replacing the factory or RiskEngine."""
        def submit_order(self, order, *args, **kwargs):
            self.observed_orders.append(order)
            return super().submit_order(order, *args, **kwargs)

        def on_order_denied(self, event):
            self.observed_denials.append(str(event.reason))
            return super().on_order_denied(event)

        def on_order_rejected(self, event):
            self.observed_denials.append(str(event.reason))
            return super().on_order_rejected(event)


@unittest.skipUnless(NATIVE, 'requires pinned native runtime')
class AdaptiveSellChunks(unittest.TestCase):
    def setUp(self):
        from tests.adaptive_paper_hermetic import patch_default_stop, restore_default_stop
        token = patch_default_stop()
        self.addCleanup(restore_default_stop, token)
        self.tmp = tempfile.TemporaryDirectory(dir='/var/tmp')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.now = datetime(2026, 10, 13, 15, 0, tzinfo=timezone.utc).timestamp()
        self.clock = [self.now]
        stop = patch.object(safety, 'DEFAULT_STOP', self.root / 'STOP')
        stop.start()
        self.addCleanup(stop.stop)
        config, limits, policy = load_config(SOURCE / 'config-leverage-1x.json')
        limits = replace(limits, capital_usd=D('20000'), max_gross_exposure_usd=D('20000'),
                         max_order_notional_usd=D('10000'), max_order_qty=D(100))
        self.ledger = Ledger(self.root / 'ledger.sqlite3', limits)
        self.addCleanup(self.ledger.close)
        self.ledger.start_trial(self.now - 60)
        self.ledger.reserve_intent('entry', 'AAPL', 'buy', '100', '100',
                                   quote=Quote('AAPL', '100', '100', self.now - 60),
                                   now=self.now - 60, market_open=True, session_close=self.now + 3600)
        self.ledger.record_order('entry', 'fixture-entry', 'filled', '100', '100', timestamp=self.now - 60)
        policy = replace(policy, capital=20000, gross_cap=20000, max_order_notional=10000)
        self.policy = AdaptivePolicy(policy, leverage_policy=config['_leverage_policy'])
        self.strategy = NativeDispatch(self.policy, self.ledger, 'fixture',
                                       stop_file=self.root / 'STOP', clock=lambda: self.clock[0],
                                       account_multiplier=D(4))
        self.strategy.captured_factory = CapturedOrderFactory()
        self.strategy.started = True
        self.strategy.enabled = False  # this fixture observes exits only
        self.orders, self.denials = [], []
        self.fill_immediately = True
        self.strategy.submit_order = self.submit
        self.strategy.cancel_order = lambda client_id: None
        self.policy.sync_positions(self.strategy.positions(), self.now - 60)
        for i in range(40):
            for symbol in policy.symbols:
                self.policy.observe(symbol, 100, 100, self.now - 40 + i)

    def tick(self, bid='110', *, force_exit=False):
        self.clock[0] += 3
        for symbol in self.policy.config.symbols:
            price = float(bid) if symbol == 'AAPL' else 100
            self.policy.observe(symbol, price, price, self.clock[0])
        return self.strategy.rebalance(self.clock[0], force_exit=force_exit)

    def submit(self, order):
        self.orders.append(order)
        side = order.side.name.lower()
        symbol = str(order.instrument_id).split('.')[0]
        cid = str(order.client_order_id)
        price, qty = str(order.price), str(order.quantity)
        bid = str(self.policy.latest[symbol].bid)
        try:
            self.ledger.reserve_intent(cid, symbol, side, qty, price,
                                       quote=Quote(symbol, bid, bid, self.clock[0]),
                                       now=self.clock[0], market_open=True,
                                       session_close=self.now + 3600, stop_file=self.root / 'STOP')
        except SafetyError as error:
            self.denials.append(str(error))
            self.strategy.on_order_denied(SimpleNamespace(client_order_id=order.client_order_id))
            return
        if self.fill_immediately:
            self.ledger.record_order(cid, 'fixture-' + cid, 'filled', qty, price, timestamp=self.clock[0])
            self.strategy.on_order_filled(SimpleNamespace(client_order_id=order.client_order_id))

    def assert_no_denials(self):
        self.assertEqual(self.denials, [])
        self.assertEqual(self.strategy.native_rejections, 0)
        self.assertEqual(self.strategy.callback_faults, [])

    def test_appreciated_at_cap_take_profit_splits_and_flattens_without_denial(self):
        decision = self.tick()
        self.assertEqual(decision.exits.get('AAPL'), 'take_profit')
        self.assert_no_denials()
        self.assertEqual(D(str(self.orders[0].quantity)), 90)
        self.assertEqual(self.ledger.positions()['AAPL'].qty, D(10))
        self.tick()
        self.assert_no_denials()
        self.assertEqual([D(str(o.quantity)) for o in self.orders], [D(90), D(10)])
        self.assertEqual(self.ledger.positions(), {})
        self.assertTrue(all(D(str(o.quantity)) * D(str(o.price)) <= 10000 for o in self.orders))

    def test_pending_sell_blocks_second_chunk_until_terminal(self):
        self.fill_immediately = False
        self.tick()
        self.assert_no_denials()
        self.tick()
        self.assertEqual(len(self.orders), 1)
        order = self.orders[0]
        self.ledger.record_order(str(order.client_order_id), 'fixture-first', 'filled',
                                 str(order.quantity), str(order.price), timestamp=self.clock[0])
        self.strategy.on_order_filled(SimpleNamespace(client_order_id=order.client_order_id))
        self.fill_immediately = True
        self.tick()
        self.assertEqual(self.ledger.positions(), {})
        self.assert_no_denials()

    def test_exit_does_not_use_policy_entry_share_cap(self):
        self.policy.config = replace(self.policy.config, max_shares=1)
        self.tick()
        self.assert_no_denials()
        self.assertEqual(D(str(self.orders[0].quantity)), 90)

    def test_fixed_qty_mode_floors_notional_capacity_to_whole_shares(self):
        self.ledger.close()
        # A distinct fixture ledger is intentional; no running journal is reset.
        self.ledger = Ledger(self.root / 'fixed.sqlite3', replace(self.ledger.limits, max_order_qty_mode='fixed'))
        self.addCleanup(self.ledger.close)
        self.ledger.start_trial(self.now - 60)
        self.ledger.reserve_intent('entry', 'AAPL', 'buy', '100', '100',
                                   quote=Quote('AAPL', '100', '100', self.now - 60),
                                   now=self.now - 60, market_open=True, session_close=self.now + 3600)
        self.ledger.record_order('entry', 'fixture-entry', 'filled', '100', '100', timestamp=self.now - 60)
        self.strategy.ledger = self.ledger
        self.tick()
        self.assert_no_denials()
        quantity = D(str(self.orders[0].quantity))
        self.assertEqual(quantity, 90)
        self.assertEqual(self.orders[0].quantity.precision, 0)
        self.assertLessEqual(quantity * D(str(self.orders[0].price)), 10000)
        self.assertEqual(quantity.as_tuple().exponent, 0)
        self.tick()
        self.assertEqual(self.ledger.positions(), {})
        self.assert_no_denials()

    def test_replacement_is_chunked_at_ack_quote_and_preserves_gap_remainder(self):
        self.clock[0] += 3
        self.policy.observe('AAPL', 110, 110, self.clock[0])
        replacement = {'symbol': 'AAPL', 'quantity': D(100), 'reason': 'gap_risk_stop',
                       'price_rule': 'market'}
        self.strategy._submit_replacement_exit(replacement, self.clock[0])
        self.assert_no_denials()
        self.assertEqual(D(str(self.orders[0].quantity)), 90)
        self.assertNotIn('AAPL', self.strategy._gap_stop_applied)
        self.assertEqual(self.ledger.positions()['AAPL'].qty, D(10))

    def test_direct_gap_stop_protects_remainder_until_final_chunk(self):
        from sessions import SessionKind
        self.policy.config = replace(self.policy.config, gap_stop_enabled=True)
        # A previously armed stop is fixture state; the real per-tick trigger,
        # dispatch and fire-once guards execute on both ticks.
        self.strategy._last_session_kind = SessionKind.RTH
        self.strategy._gap_risk_stop_price['AAPL'] = D(111)
        self.tick()
        self.assert_no_denials()
        self.assertNotIn('AAPL', self.strategy._gap_stop_applied)
        self.assertEqual(self.ledger.positions()['AAPL'].qty, D(10))
        self.tick()
        self.assert_no_denials()
        self.assertEqual(self.ledger.positions(), {})
        self.assertIn('AAPL', self.strategy._gap_stop_applied)
        self.assertEqual([D(str(o.quantity)) for o in self.orders], [D(90), D(10)])

    def test_replacement_clamps_staged_delta_to_current_owned_position(self):
        self.tick()  # first bounded sell leaves 10 shares
        self.assert_no_denials()
        self.strategy._submit_replacement_exit(
            {'symbol': 'AAPL', 'quantity': D(100), 'reason': 'take_profit', 'price_rule': 'market'},
            self.clock[0])
        self.assert_no_denials()
        self.assertEqual(D(str(self.orders[-1].quantity)), 10)
        self.assertEqual(self.ledger.positions(), {})

    def test_oversize_entry_is_still_refused(self):
        with self.assertRaisesRegex(SafetyError, 'order_size_cap_exceeded'):
            self.ledger.reserve_intent('too-big', 'MSFT', 'buy', '100', '110',
                                       quote=Quote('MSFT', '110', '110', self.now),
                                       now=self.now, market_open=True, session_close=self.now + 3600,
                                       stop_file=self.root / 'STOP')


@unittest.skipUnless(NATIVE, 'requires pinned native runtime')
class CommittedExitRegressions(unittest.TestCase):
    """Astra reviewer cases plus journal replay, partial target and retry bounds."""
    def setUp(self):
        self.f = AdaptiveSellChunks()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)

    def test_every_pinned_native_denial_has_an_explicit_policy_and_safe_fallback(self):
        import json
        rows = json.loads((SOURCE.parents[2] / 'tests/fixtures/native-denial-reasons-1b0a49d2.json').read_text())['members']
        definitive = {
            'PRICE_PRECISION_EXCEEDS_MAXIMUM', 'QUANTITY_PRECISION_EXCEEDS_MAXIMUM',
            'INVALID_MAX_NOTIONAL_PER_ORDER', 'MISSING_EXPIRE_TIME',
            'MISSING_TRAILING_OFFSET_TYPE', 'UNSUPPORTED_TRAILING_OFFSET_TYPE',
            'MISSING_TRIGGER_TYPE', 'MISSING_TRAILING_OFFSET', 'CLIENT_VENUE_MISMATCH',
            'INVALID_CLIENT_ORDER_ID', 'UNSUPPORTED_ORDER_LIST', 'UNSUPPORTED_ORDER_TYPE',
            'UNSUPPORTED_REDUCE_ONLY', 'UNSUPPORTED_TIME_IN_FORCE', 'UNSUPPORTED_TP_SL'}
        t = self.f
        for index, row in enumerate(rows + [{'code': 'FUTURE_NATIVE_DENIAL'}]):
            code = row['code']
            with self.subTest(code=code):
                t.ledger.record_exit_state('AAPL', {}, transition='fixture_new_denial')
                cid = 'native-denial-' + str(index)
                t.strategy.pending[cid] = {'symbol': 'AAPL', 'side': 'sell', 'created': t.clock[0]}
                t.strategy.on_order_denied(SimpleNamespace(client_order_id=cid,
                    reason=code + ': opaque fixture diagnostic must not be persisted'))
                refusal = t.ledger.exit_state('AAPL')['refusal']
                if code in definitive:
                    self.assertEqual(refusal['classification'], 'definitive')
                    self.assertFalse(t.ledger.exit_retry_allowed('AAPL', t.clock[0] + 120))
                else:
                    self.assertEqual(refusal['classification'], 'transient')
                    self.assertEqual(refusal['reconciliation'], 'native_denied_never_sent')
                    self.assertFalse(t.ledger.exit_retry_allowed('AAPL', t.clock[0] + 1))
                    self.assertTrue(t.ledger.exit_retry_allowed('AAPL', t.clock[0] + 120))
                self.assertNotIn('opaque fixture diagnostic', str(refusal))
        table = getattr(safety, 'NATIVE_DENIAL_POLICY', {})
        self.assertEqual(set(table), {r['code'] for r in rows})
        self.assertEqual({code for code, policy in table.items()
                          if policy == 'definitive'}, definitive)

    def test_reviewer_take_profit_reversal_finishes_original_target(self):
        t = self.f
        t.tick('100.5')
        for _ in range(3):
            t.tick('100.35')
        self.assertEqual(t.ledger.positions(), {})
        self.assertEqual([D(str(o.quantity)) for o in t.orders], [D(99), D(1)])
        self.assertEqual(t.ledger.exit_state('AAPL')['target'], '0')

    def target(self, quantity):
        """Feed an explicit allocation decision through real rebalance and Ledger."""
        self.f.policy.decide = lambda *args, **kwargs: SimpleNamespace(
            targets={'AAPL': quantity}, exits={}, signals=[], regime='fixture',
            effective_leverage=1)

    def test_same_reason_lower_rebalance_target_reduces_again(self):
        t = self.f
        self.target(50)
        t.tick('100')
        self.target(25)
        t.tick('100')
        self.assertEqual([D(str(o.quantity)) for o in t.orders], [D(50), D(25)])
        self.assertEqual(t.ledger.positions()['AAPL'].qty, D(25))
        t.assert_no_denials()

    def test_completed_rebalance_does_not_sell_a_later_scale_in(self):
        t = self.f
        t.strategy.enabled = True
        self.target(50)
        t.tick('100')
        self.target(99)
        t.tick('100')
        t.tick('100')
        self.assertEqual([(o.side.name.lower(), D(str(o.quantity))) for o in t.orders],
                         [('sell', D(50)), ('buy', D(49))])
        self.assertEqual(t.ledger.positions()['AAPL'].qty, D(99))
        t.assert_no_denials()
        # A later absolute reduction starts a new completed-target cycle.
        self.target(75)
        t.tick('100')
        self.assertEqual(D(str(t.orders[-1].quantity)), D(24))
        self.assertEqual(t.ledger.positions()['AAPL'].qty, D(75))

    def test_reconciled_flat_fill_without_callback_allows_new_entry(self):
        t = self.f
        t.fill_immediately = False
        self.target(0)
        t.tick('100')
        order = t.orders[0]
        t.ledger.record_order(str(order.client_order_id), 'fixture-reconciled', 'filled',
                              '100', str(order.price), timestamp=t.clock[0])
        self.assertEqual(t.ledger.positions(), {})
        self.restore_strategy()
        t.fill_immediately = True
        t.strategy.enabled = True
        self.target(10)
        t.tick('100')
        self.assertEqual([(o.side.name.lower(), D(str(o.quantity))) for o in t.orders],
                         [('sell', D(100)), ('buy', D(10))])
        self.assertEqual(t.ledger.positions()['AAPL'].qty, D(10))
        t.assert_no_denials()

    def test_final_wire_integrity_refusal_requires_a_fresh_recovery_session(self):
        import threading
        import transport
        from runner import Controller
        t = self.f
        controller = Controller(t.ledger, t.now + 3600, market_open=True,
                                clock=lambda: t.clock[0], stop_file=t.root / 'STOP')
        controller.quotes['AAPL'] = Quote('AAPL', '110', '110', t.clock[0])
        damaged = SimpleNamespace(_state_lock=threading.RLock(), _reasons={'queue_overflow'})
        payload = {'client_order_id': 'integrity-exit', 'symbol': 'AAPL', 'side': 'sell',
                   'qty': '1', 'limit_price': '109.98', 'type': 'limit',
                   'time_in_force': 'day', 'extended_hours': False}
        controller.before_submit(payload)
        session = transport.GuardedSession(origin=transport.PAPER_URL,
            before_request=lambda kind, **kwargs: asyncio.run(controller.before_request(kind, **kwargs)),
            before_send=lambda order: transport.AlpacaPaperTransport._wire_guard(damaged, order))
        self.addCleanup(session.close)
        envelope = transport.order_envelope(payload)
        session.expect_submission(envelope)
        with patch.object(session._session, 'request') as http:
            with self.assertRaises(transport.SubmissionNotSent) as caught:
                session.request('POST', transport.PAPER_URL + '/v2/orders', json=envelope['intent'])
            http.assert_not_called()
        reason = transport.exit_not_sent_reason(caught.exception)
        self.assertEqual(reason, 'exit_submission_not_sent:recovery_observation_integrity_lost')
        refusal = t.ledger.record_exit_refusal('AAPL', reason, t.clock[0])
        self.assertEqual(refusal['classification'], 'integrity_lost')
        self.assertFalse(t.ledger.exit_retry_allowed('AAPL', t.clock[0] + 1000))

    def test_reviewer_definitive_refusal_is_retained_not_repeated(self):
        t = self.f
        def refuse(order):
            t.orders.append(order)
            t.strategy.on_order_denied(SimpleNamespace(client_order_id=order.client_order_id,
                reason='only_USD_equity_limit_DAY_supported'))
        t.strategy.submit_order = refuse
        for _ in range(4):
            t.tick()
        self.assertLessEqual(len(t.orders), 1)
        self.assertEqual(t.ledger.positions()['AAPL'].qty, D(100))
        self.assertIn('only_USD_equity_limit_DAY_supported', t.strategy._exit_pending_attention['AAPL'])
        self.assertEqual(t.ledger.exit_state('AAPL')['refusal']['classification'], 'definitive')
        # Explicit reconciliation is the only release, not a price change.
        t.ledger.reconcile_exit_refusal('AAPL', reason='fixture adapter contract repaired and reconciled')
        t.strategy.submit_order = t.submit
        t.tick('100.35')
        t.tick('100.35')
        self.assertEqual(t.ledger.positions(), {})

    def test_reviewer_appreciated_one_owned_share_uses_logged_whole_share_exception(self):
        t = self.f
        t.ledger.close()
        t.ledger = Ledger(t.root / 'small.sqlite3', replace(t.ledger.limits, max_order_notional_usd=D(100)))
        t.addCleanup(t.ledger.close)
        t.ledger.start_trial(t.now - 60)
        t.ledger.reserve_intent('entry', 'AAPL', 'buy', '1', '100',
            quote=Quote('AAPL', '100', '100', t.now - 60), now=t.now - 60,
            market_open=True, session_close=t.now + 3600)
        t.ledger.record_order('entry', 'fixture', 'filled', '1', '100', timestamp=t.now - 60)
        t.strategy.ledger = t.ledger
        t.policy.config = replace(t.policy.config, max_order_notional=100)
        for _ in range(3):
            t.tick()
        self.assertEqual(t.ledger.positions(), {})
        self.assertEqual([D(str(o.quantity)) for o in t.orders], [D(1)])
        self.assertEqual(t.orders[0].quantity.precision, 0)
        self.assertEqual(t.ledger.db.execute("SELECT count(*) FROM events WHERE kind='exit_cap_exceeded_reduce_only'").fetchone()[0], 1)
        with self.assertRaisesRegex(SafetyError, 'order_size_cap_exceeded'):
            t.ledger.reserve_intent('new-entry', 'AAPL', 'buy', '1', '110',
                quote=Quote('AAPL', '110', '110', t.clock[0]), now=t.clock[0],
                market_open=True, session_close=t.now + 3600)

    def restore_strategy(self):
        t = self.f
        limits, path = t.ledger.limits, t.ledger.path
        t.ledger.close()
        t.ledger = Ledger(path, limits)
        t.addCleanup(t.ledger.close)
        t.strategy = NativeDispatch(t.policy, t.ledger, 'fixture', stop_file=t.root / 'STOP',
                                    clock=lambda: t.clock[0], account_multiplier=D(4))
        t.strategy.captured_factory = CapturedOrderFactory()
        t.strategy.started = True
        t.strategy.submit_order = t.submit
        t.strategy.cancel_order = lambda client_id: None

    def test_commitment_restores_and_outstanding_partial_fill_serializes(self):
        t = self.f
        t.fill_immediately = False
        t.tick()
        order = t.orders[0]
        cid = str(order.client_order_id)
        t.ledger.record_order(cid, 'fixture', 'partially_filled', '40', str(order.price), timestamp=t.clock[0])
        t.strategy.on_order_filled(SimpleNamespace(client_order_id=order.client_order_id))
        self.restore_strategy()
        t.tick('100.35')
        self.assertEqual(len(t.orders), 1)
        t.ledger.record_order(cid, 'fixture', 'canceled', '40', str(order.price), timestamp=t.clock[0])
        t.fill_immediately = True
        t.tick('100.35')
        self.assertEqual([D(str(o.quantity)) for o in t.orders], [D(90), D(60)])
        self.assertEqual(t.ledger.positions(), {})

    def test_partial_take_profit_preserves_original_partial_target(self):
        t = self.f
        t.ledger.close()
        t.ledger = Ledger(t.root / 'partial.sqlite3', replace(t.ledger.limits, max_order_notional_usd=D(1000)))
        t.addCleanup(t.ledger.close)
        t.ledger.start_trial(t.now - 60)
        for i in range(10):
            cid = 'entry-' + str(i)
            t.ledger.reserve_intent(cid, 'AAPL', 'buy', '10', '100',
                quote=Quote('AAPL', '100', '100', t.now - 60), now=t.now - 60,
                market_open=True, session_close=t.now + 3600)
            t.ledger.record_order(cid, cid, 'filled', '10', '100', timestamp=t.now - 60)
        t.strategy.ledger = t.ledger
        t.policy.config = replace(t.policy.config, take_profit_fraction=.5)
        t.tick('100.5')
        self.assertEqual(t.ledger.exit_state('AAPL')['target'], '50')
        for _ in range(8):
            t.tick('100.35')
        self.assertEqual(t.ledger.positions()['AAPL'].qty, D(50))
        self.assertEqual(sum(D(str(o.quantity)) for o in t.orders), D(50))
        # A still-active same take-profit cannot repeatedly halve the remainder.
        for _ in range(3):
            t.tick('100.5')
        self.assertEqual(t.ledger.positions()['AAPL'].qty, D(50))

    def partial_take_profit_then_scale_in(self, *, fill=True, fill_callback=True, added=50):
        t = self.f
        t.policy.config = replace(t.policy.config, take_profit_fraction=.5)
        if not fill_callback:
            t.strategy.on_order_filled = lambda event: None
        decision = t.tick('100.5')
        self.assertEqual(decision.exits['AAPL'], 'take_profit')
        self.assertEqual(t.ledger.positions()['AAPL'].qty, D(50))
        self.assertEqual([D(str(o.quantity)) for o in t.orders], [D(50)])
        t.ledger.reserve_intent('scale-in', 'AAPL', 'buy', str(added), '100.5',
            quote=Quote('AAPL', '100.5', '100.5', t.clock[0]), now=t.clock[0],
            market_open=True, session_close=t.now + 3600)
        if fill:
            t.ledger.record_order('scale-in', 'fixture-scale-in', 'filled', str(added), '100.5',
                                  timestamp=t.clock[0])
            self.assertEqual(t.ledger.positions()['AAPL'].qty, D(50 + added))
        return t

    def test_scale_in_rearms_completed_partial_take_profit(self):
        t = self.partial_take_profit_then_scale_in()
        decision = t.tick('101')
        self.assertEqual(decision.exits['AAPL'], 'take_profit')
        self.assertEqual([D(str(o.quantity)) for o in t.orders], [D(50), D(50)])
        self.assertEqual(t.ledger.positions()['AAPL'].qty, D(50))
        # Replaying the cumulative buy fill cannot re-arm the target twice.
        t.ledger.record_order('scale-in', 'fixture-scale-in', 'filled', '50', '100.5',
                              timestamp=t.clock[0])
        t.tick('101')
        self.assertEqual(t.ledger.positions()['AAPL'].qty, D(50))
        self.assertEqual(len(t.orders), 2)
        t.assert_no_denials()

    def test_scale_in_after_reconciled_partial_fill_rearms_across_restart(self):
        t = self.partial_take_profit_then_scale_in(fill_callback=False, added=25)
        self.restore_strategy()
        t.tick('101')
        self.assertEqual([D(str(o.quantity)) for o in t.orders], [D(50), D(37)])
        self.assertEqual(t.ledger.positions()['AAPL'].qty, D(38))
        t.assert_no_denials()

    def test_unfilled_scale_in_does_not_rearm_partial_take_profit(self):
        t = self.partial_take_profit_then_scale_in(fill=False)
        t.ledger.record_order('scale-in', 'fixture-scale-in', 'canceled', '0', None,
                              timestamp=t.clock[0])
        t.tick('101')
        self.assertEqual([D(str(o.quantity)) for o in t.orders], [D(50)])
        self.assertEqual(t.ledger.positions()['AAPL'].qty, D(50))

    def test_scale_in_preserves_an_unfinished_partial_target(self):
        t = self.f
        state = {'target': '50', 'reason': 'take_profit', 'completed': False}
        t.ledger.record_exit_state('AAPL', state, transition='fixture_commit')
        t.ledger.reserve_intent('scale-in', 'AAPL', 'buy', '50', '100',
            quote=Quote('AAPL', '100', '100', t.clock[0]), now=t.clock[0],
            market_open=True, session_close=t.now + 3600)
        t.ledger.record_order('scale-in', 'fixture-scale-in', 'filled', '50', '100',
                              timestamp=t.clock[0])
        self.assertEqual(t.ledger.exit_state('AAPL'), state)
        t.policy.config = replace(t.policy.config, take_profit_fraction=.5)
        for _ in range(3):
            t.tick('100.5')
        self.assertEqual(sum(D(str(o.quantity)) for o in t.orders), D(100))
        self.assertEqual(t.ledger.positions()['AAPL'].qty, D(50))
        t.assert_no_denials()

    def test_stop_loss_still_sells_after_partial_take_profit_and_scale_in(self):
        t = self.partial_take_profit_then_scale_in()
        decision = t.tick('99.9')
        self.assertEqual(decision.exits['AAPL'], 'stop_loss')
        self.assertEqual(D(str(t.orders[-1].quantity)), D(100))
        self.assertEqual(t.ledger.positions(), {})
        t.assert_no_denials()

    def test_time_exit_still_sells_after_partial_take_profit_and_scale_in(self):
        t = self.partial_take_profit_then_scale_in()
        t.policy.config = replace(t.policy.config, max_hold_seconds=60)
        decision = t.tick('100.4')
        self.assertEqual(decision.exits['AAPL'], 'time_exit')
        for _ in range(2):
            t.tick('100.4')
        self.assertEqual(sum(D(str(o.quantity)) for o in t.orders[1:]), D(100))
        self.assertEqual(t.ledger.positions(), {})
        t.assert_no_denials()

    def test_transient_pacing_and_attention_survive_reopen(self):
        t = self.f
        def refuse(order):
            t.orders.append(order)
            t.strategy.on_order_denied(SimpleNamespace(client_order_id=order.client_order_id, reason='quote_stale'))
        t.strategy.submit_order = refuse
        for _ in range(12):
            t.tick()
        self.assertEqual(len(t.orders), 6)
        self.assertEqual(t.ledger.exit_state('AAPL')['refusal']['attempts'], 6)
        self.assertTrue(t.ledger.exit_state('AAPL')['refusal']['needs_attention'])
        self.restore_strategy()
        t.clock[0] += 1  # last attempt was at +33, retry_at remains +38 after reopen
        t.strategy.rebalance(t.clock[0])
        self.assertEqual(len(t.orders), 6)
        self.assertTrue(t.ledger.exit_retry_allowed('AAPL', t.clock[0] + 100))
        self.assertEqual(t.ledger.exit_state('AAPL')['refusal']['reason'], 'quote_stale')
        self.assertTrue(t.ledger.exit_state('AAPL')['refusal']['needs_attention'])
        t.tick()
        t.tick()
        self.assertEqual(t.ledger.positions(), {})

    def test_pre_wire_safety_refusal_is_blocked_after_restore(self):
        t = self.f
        def refuse(order):
            t.orders.append(order)
            t.strategy.on_order_denied(SimpleNamespace(client_order_id=order.client_order_id,
                                                      reason='invalid_price_increment'))
        t.strategy.submit_order = refuse
        t.tick()
        self.restore_strategy()
        for _ in range(3):
            t.tick('100.35')
        self.assertEqual(len(t.orders), 1)
        self.assertEqual(t.ledger.positions()['AAPL'].qty, D(100))
        self.assertIn('invalid_price_increment', t.strategy._exit_pending_attention['AAPL'])

    def test_controller_quote_not_fresh_refusal_retries_after_fresh_quotes(self):
        """Local reviewer reproduction: quote ages between tick and pre-wire guard."""
        from runner import Controller
        from native_adapter import NativeOrderRejected
        t = self.f
        controller = Controller(t.ledger, t.now + 3600, market_open=True,
                                clock=lambda: t.clock[0], stop_file=t.root / 'STOP')
        refused = []
        def dispatch(order):
            if not refused:
                # The strategy observed a fresh quote; the transport's own
                # observation has aged by the final pre-wire reservation.
                controller.quotes['AAPL'] = Quote('AAPL', '110', '110', t.clock[0] - 10)
                payload = {'client_order_id': str(order.client_order_id), 'symbol': 'AAPL',
                           'side': 'sell', 'qty': str(order.quantity), 'limit_price': str(order.price)}
                try:
                    controller.before_submit(payload)
                except NativeOrderRejected as error:
                    refused.append(str(error))
                    t.orders.append(order)
                    # The adapter forwards definitive pre-wire failures as
                    # OrderRejected, preserving this exact reason string.
                    t.strategy.on_order_rejected(SimpleNamespace(client_order_id=order.client_order_id,
                                                                 reason=str(error)))
                    return
                self.fail('stale pre-wire observation was unexpectedly admitted')
            t.submit(order)
        t.strategy.submit_order = dispatch
        t.tick()
        self.assertEqual(refused, ['quote_not_fresh'])
        self.assertEqual(t.ledger.positions()['AAPL'].qty, D(100))
        classification = t.ledger.exit_state('AAPL')['refusal']['classification']
        t.tick()  # fresh, but still inside the five-second retry delay
        self.assertEqual(len(t.orders), 1)
        t.tick()  # fresh and the bounded retry is now eligible
        t.tick()  # next committed chunk reaches flat
        self.assertEqual(t.strategy.native_rejections, 1)
        self.assertEqual(t.ledger.positions(), {})
        self.assertEqual([D(str(o.quantity)) for o in t.orders], [D(90), D(90), D(10)])
        self.assertEqual(classification, 'transient')
        self.assertEqual(t.strategy.callback_faults, [])
        self.assertNotIn('refusal', t.ledger.exit_state('AAPL'))
        self.assertTrue(t.ledger.exit_retry_allowed('AAPL', t.clock[0]))  # recovery shares this gate

    def test_exit_entry_cap_exemption_never_sells_unowned_shares(self):
        t = self.f
        t.ledger.close()
        t.ledger = Ledger(t.root / 'exception.sqlite3', replace(t.ledger.limits, max_order_notional_usd=D(100)))
        t.addCleanup(t.ledger.close)
        t.ledger.start_trial(t.now - 60)
        self.assertEqual(t.ledger.owned_exit_quantity(100, 100, 110, 110), D(1))
        with self.assertRaisesRegex(SafetyError, 'sell_exceeds_owned_unreserved_position'):
            t.ledger.reserve_intent('unowned', 'AAPL', 'sell', '1', '110',
                quote=Quote('AAPL', '110', '110', t.clock[0]), now=t.clock[0],
                market_open=True, session_close=t.now + 3600)

        with self.assertRaisesRegex(SafetyError, 'sell_exceeds_owned_unreserved_position'):
            t.ledger.reserve_intent('two-share', 'AAPL', 'sell', '2', '110',
                quote=Quote('AAPL', '110', '110', t.clock[0]), now=t.clock[0],
                market_open=True, session_close=t.now + 3600)

    def exercise_final_http_guard(self, mode, *, duration=0):
        """Real controller, HTTP guard and adapter forwarding; HTTP/fills simulated."""
        from runner import Controller
        from native_adapter import AlpacaExecutionClient
        from nautilus_trader.model import OrderType, TimeInForce
        import transport
        t = self.f
        controller = Controller(t.ledger, t.now + 3600, market_open=True,
                                clock=lambda: t.clock[0], stop_file=t.root / 'STOP')
        attempts = []
        attempt_times = []
        release_at = t.clock[0] + 3 + duration
        def admit(kind, client_id=None):
            return asyncio.run(controller.before_request(kind, client_id=client_id))
        session = transport.GuardedSession(origin=transport.PAPER_URL, before_request=admit)
        self.addCleanup(session.close)
        http = patch.object(session._session, 'request', return_value=SimpleNamespace(status_code=200, headers={}))
        wire = http.start()
        self.addCleanup(http.stop)
        class Port:
            async def submit(inner, payload):
                controller.quotes['AAPL'] = Quote('AAPL', '110', '110', t.clock[0])
                controller.before_submit(payload)
                if len(attempts) == 1 or (duration and mode == 'stale' and t.clock[0] < release_at):
                    if mode == 'stale':
                        # The reservation succeeded; only the final guard sees staleness.
                        controller.quotes['AAPL'] = Quote('AAPL', '110', '110', t.clock[0] - 10)
                    else:
                        # Exhaust the real shared request budget, without mocking its gate.
                        for _ in range(t.ledger.limits.max_rest_per_minute + 1):
                            if t.ledger.request_budget(t.clock[0], 'read'):
                                break
                envelope = transport.order_envelope(payload)
                session.expect_submission(envelope)
                try:
                    await asyncio.to_thread(session.request, 'POST', transport.PAPER_URL + '/v2/orders',
                                            json=envelope['intent'])
                finally:
                    session.withdraw_submission(payload['client_order_id'])
                return dict(payload, id='fixture-' + payload['client_order_id'], status='filled',
                            filled_qty=payload['qty'], filled_avg_price=payload['limit_price'])
        def rejected(order, reason, *args):
            t.strategy.on_order_rejected(SimpleNamespace(client_order_id=order.client_order_id, reason=reason))
        def observe(row):
            if duration:
                t.ledger.record_order(row['client_order_id'], row['id'], 'accepted', '0', None,
                                      timestamp=t.clock[0])
                self.assertNotIn('refusal', t.ledger.exit_state('AAPL'), 'reset on acceptance before any fill')
            t.ledger.record_order(row['client_order_id'], row['id'], 'filled', row['filled_qty'],
                                  row['filled_avg_price'], timestamp=t.clock[0])
            t.strategy.on_order_filled(SimpleNamespace(client_order_id=row['client_order_id']))
        client = SimpleNamespace(session=SimpleNamespace(errors=[], instruments={'AAPL': None},
                                 session_policy={}, port=Port(), fail=lambda reason: self.fail(reason)),
                                 orders={}, clock=SimpleNamespace(timestamp_ns=lambda: int(t.clock[0]*1e9)),
                                 generate_order_submitted=lambda order: None,
                                 generate_order_rejected=rejected, generate_order_denied=rejected,
                                 observe=observe)
        def dispatch(order):
            attempts.append(order)
            attempt_times.append(t.clock[0])
            order.order_type, order.time_in_force, order.strategy_id = OrderType.LIMIT, TimeInForce.DAY, 'ADAPTIVE-001'
            asyncio.run(AlpacaExecutionClient._submit_order(client, SimpleNamespace(order=order)))
        t.strategy.submit_order = dispatch
        t.tick()
        self.assertEqual(t.strategy.native_rejections, 1)
        self.assertEqual(wire.call_count, 0)
        self.assertEqual(t.ledger.positions()['AAPL'].qty, D(100))
        if duration:
            # Real durable budget / final HTTP quote gate at a continuous 2s
            # strategy cadence; never skip directly past the refusal window.
            for _ in range((duration + 20) // 2):
                t.clock[0] += 2
                for symbol in t.policy.config.symbols:
                    price = 110 if symbol == 'AAPL' else 100
                    t.policy.observe(symbol, price, price, t.clock[0])
                t.strategy.rebalance(t.clock[0])
                if not t.ledger.positions():
                    break
            self.assertEqual(t.ledger.positions(), {}, 'paced retries must eventually sell all 100 shares')
            refused_times = attempt_times[:-2]
            self.assertTrue(all(b - a >= 5 for a, b in zip(refused_times, attempt_times[1:])))
            self.assertEqual(wire.call_count, 2)
            self.assertNotIn('refusal', t.ledger.exit_state('AAPL'))
            if mode == 'stale':
                self.assertEqual(t.ledger.db.execute(
                    "SELECT count(*) FROM events WHERE kind='needs_attention' "
                    "AND json_extract(payload,'$.reason')='exit_transient_refusals'").fetchone()[0], 1)
            self.assertEqual(t.strategy.callback_faults, [])
            return attempt_times
        if mode == 'budget':
            t.clock[0] += 61  # the real durable minute budget becomes available again
        else:
            t.tick()  # fresh quote, but inside the five-second retry bound
            self.assertEqual(len(attempts), 1)
        t.tick()
        t.tick()
        self.assertEqual(t.ledger.positions(), {}, 'all 100 owned shares must exit after guard recovery')
        self.assertEqual(t.strategy.native_rejections, 1)
        self.assertEqual(wire.call_count, 2)
        self.assertEqual([D(str(o.quantity)) for o in attempts], [D(90), D(90), D(10)])
        self.assertEqual(t.strategy.callback_faults, [])

    def test_sixty_second_budget_deferral_at_two_second_ticks_eventually_exits(self):
        times = self.exercise_final_http_guard('budget', duration=60)
        self.assertGreaterEqual(times[1] - times[0], 60, 'carry the real budget wait through the native reason')

    def test_thirty_second_stale_quote_eventually_exits_without_reconciliation(self):
        times = self.exercise_final_http_guard('stale', duration=30)
        self.assertGreater(len(times), 3)

    def test_transient_attempts_remain_paced_beyond_three_refusals(self):
        times = self.exercise_final_http_guard('stale', duration=40)
        self.assertGreater(len(times), 5)
        self.assertTrue(all(b - a >= 5 for a, b in zip(times[:-2], times[1:])))

    def test_final_http_guard_stale_after_reservation_resumes_full_exit(self):
        self.exercise_final_http_guard('stale')

    def test_final_http_guard_budget_deferral_resumes_full_exit(self):
        self.exercise_final_http_guard('budget')

    def exercise_owned_cap_probe(self, shares):
        """#1095 core exit_probe boundary, isolated from its unmerged arming layer."""
        from runner import Controller
        t = self.f
        t.ledger.close()
        t.ledger = Ledger(t.root / 'exit-probe.sqlite3', replace(t.ledger.limits,
            max_order_notional_usd=D(1000), max_order_qty=D(1), max_order_qty_mode='fixed'))
        t.addCleanup(t.ledger.close)
        t.ledger.start_trial(t.now - 60)
        for i in range(shares):
            cid = 'probe-entry-' + str(i)
            t.ledger.reserve_intent(cid, 'SPY', 'buy', '1', '999.99',
                quote=Quote('SPY', '999.98', '999.99', t.now - 60), now=t.now - 60,
                market_open=True, session_close=t.now + 3600, stop_file=t.root / 'STOP')
            t.ledger.record_order(cid, cid, 'filled', '1', '999.99', timestamp=t.now - 60)
        controller = Controller(t.ledger, t.now + 3600, market_open=True,
                                clock=lambda: t.clock[0], stop_file=t.root / 'STOP')
        controller.quotes['SPY'] = Quote('SPY', '1000.10', '1000.11', t.clock[0])
        controller.before_submit({'client_order_id': 'owned-exit-probe', 'symbol': 'SPY',
            'side': 'sell', 'qty': str(shares), 'limit_price': '1000.10', 'reduce_only': True,
            'extended_hours': True, 'type': 'limit', 'time_in_force': 'day'})
        self.assertEqual(next(i for i in t.ledger.intents() if i.client_id == 'owned-exit-probe').qty, D(shares))
        self.assertEqual(t.ledger.positions()['SPY'].qty, D(shares))  # admitted, not falsely booked

    def test_1095_one_share_appreciated_exit_probe_is_accepted(self):
        self.exercise_owned_cap_probe(1)

    def test_owned_two_share_reduction_is_exempt_from_entry_size_caps(self):
        self.exercise_owned_cap_probe(2)

    def permanent_http_guard(self, code, *, qty='1', price='100', symbol='AAPL', market_open=True,
                             classification='definitive'):
        import transport
        t = self.f
        def guard(kind, client_id=None):
            if code == 'global_stop_latched':
                raise SafetyError(code)  # local STOP policy, never touch the host latch
            t.ledger.reserve_intent('permanent-fixture', symbol, 'sell', qty, price,
                quote=Quote(symbol, '110', '110', t.clock[0]), now=t.clock[0],
                market_open=market_open, session_close=t.now + 3600)
        session = transport.GuardedSession(origin=transport.PAPER_URL, before_request=guard)
        self.addCleanup(session.close)
        payload = {'symbol': symbol, 'side': 'sell', 'qty': qty, 'limit_price': price,
                   'client_order_id': 'permanent-fixture', 'type': 'limit',
                   'time_in_force': 'day', 'extended_hours': False}
        envelope = transport.order_envelope(payload)
        session.expect_submission(envelope)
        with patch.object(session._session, 'request') as http:
            with self.assertRaises(transport.SubmissionNotSent) as caught:
                session.request('POST', transport.PAPER_URL + '/v2/orders', json=envelope['intent'])
            http.assert_not_called()
        self.assertEqual(caught.exception.refusal_code, code)
        state = t.ledger.record_exit_refusal('AAPL', transport.exit_not_sent_reason(caught.exception), t.clock[0])
        self.assertEqual(state['classification'], classification)
        self.assertFalse(t.ledger.exit_retry_allowed('AAPL', t.clock[0] + 100))

    def test_host_stop_latch_is_a_named_permanent_pre_wire_refusal(self):
        self.permanent_http_guard('global_stop_latched')

    def test_qty_and_notional_cap_are_not_permanent_pre_wire_exit_reasons(self):
        import transport
        for code in ('order_size_cap_exceeded', 'sell_exceeds_owned_unreserved_position'):
            with self.subTest(code=code):
                reason = transport.exit_not_sent_reason(transport.SubmissionNotSent(code))
                state = self.f.ledger.record_exit_refusal('AAPL', reason, self.f.clock[0])
                self.assertEqual(state['classification'], 'transient')
        self.assertEqual(self.f.ledger.record_exit_refusal('SPY', 'order_size_cap_exceeded',
                         self.f.clock[0])['classification'], 'transient')

    def test_closed_session_is_a_named_session_scoped_pre_wire_refusal(self):
        self.permanent_http_guard('outside_allowed_session', market_open=False,
                                  classification='session_closed')
        t = self.f
        self.assertFalse(t.ledger.exit_retry_allowed('AAPL', t.clock[0],
                         market_open=False, session_close=t.clock[0] + 3600))
        self.assertFalse(t.ledger.exit_retry_allowed('AAPL', t.clock[0],
                         market_open=True, session_close=t.clock[0] + .5))
        self.assertTrue(t.ledger.exit_retry_allowed('AAPL', t.clock[0],
                        market_open=True, session_close=t.clock[0] + 3600))

    def test_any_unenumerated_submission_not_sent_remains_transient_after_many_refusals(self):
        import transport
        t = self.f
        reason = transport.exit_not_sent_reason(transport.SubmissionNotSent('an unenumerated pre-wire condition'))
        for attempt in range(10):
            state = t.ledger.record_exit_refusal('AAPL', reason, t.clock[0] + 6*attempt)
            self.assertEqual(state['classification'], 'transient')
        self.assertTrue(state['needs_attention'])
        self.assertEqual(state['attempts'], 10)
        self.assertTrue(t.ledger.exit_retry_allowed('AAPL', t.clock[0] + 100))

    def test_native_acceptance_resets_consecutive_refusals_before_a_fill(self):
        from nautilus_trader.model import ClientOrderId
        t = self.f
        for attempt in range(4):
            t.ledger.record_exit_refusal('AAPL', 'quote_not_fresh', t.clock[0] + 6 * attempt)
        t.strategy.pending['accepted-exit'] = {'symbol': 'AAPL', 'side': 'sell'}
        t.strategy.on_order_accepted(SimpleNamespace(client_order_id=ClientOrderId('accepted-exit')))
        self.assertNotIn('refusal', t.ledger.exit_state('AAPL'))
        self.assertEqual(t.ledger.positions()['AAPL'].qty, D(100))
        state = t.ledger.record_exit_refusal('AAPL', 'quote_not_fresh', t.clock[0] + 30)
        self.assertEqual(state['attempts'], 1)
        self.assertFalse(state['needs_attention'])

    def test_transient_wait_bridge_is_numeric_and_does_not_weaken_permanent_causes(self):
        import transport
        t = self.f
        for wait in (float('nan'), float('inf'), -1, 'private text', True):
            with self.subTest(wait=type(wait).__name__):
                reason = transport.exit_not_sent_reason(transport.SubmissionNotSent('temporary', retry_after=wait))
                self.assertEqual(reason, 'exit_submission_not_sent:temporary')
                state = t.ledger.record_exit_refusal('SPY', reason, t.clock[0])
                self.assertEqual(state['retry_at'], t.clock[0] + 5)
        reason = transport.exit_not_sent_reason(transport.SubmissionNotSent('global_stop_latched', retry_after=60))
        state = t.ledger.record_exit_refusal('AAPL', reason, t.clock[0])
        self.assertEqual(state['classification'], 'definitive')
        self.assertFalse(t.ledger.exit_retry_allowed('AAPL', t.clock[0] + 100))

    def test_pre_wire_entry_is_dropped_without_exit_retry_state(self):
        from native_adapter import AlpacaExecutionClient
        from nautilus_trader.model import ClientOrderId, InstrumentId, OrderSide, OrderType, Price, Quantity, TimeInForce
        import transport
        t = self.f
        cid = ClientOrderId('entry-prewire')
        order = SimpleNamespace(instrument_id=InstrumentId.from_str('MSFT.ALPACA'), side=OrderSide.BUY,
            order_type=OrderType.LIMIT, time_in_force=TimeInForce.DAY, tags=[], strategy_id='ADAPTIVE-001',
            client_order_id=cid, quantity=Quantity.from_int(1), price=Price.from_str('100.00'))
        t.strategy.pending[str(cid)] = {'symbol': 'MSFT', 'side': 'buy', 'created': t.clock[0]}
        reasons = []
        class Port:
            async def submit(inner, payload):
                raise transport.SubmissionNotSent('submission prevented before HTTP request')
        def rejected(native_order, reason, *args):
            reasons.append(reason)
            t.strategy.on_order_rejected(SimpleNamespace(client_order_id=cid, reason=reason))
        client = SimpleNamespace(session=SimpleNamespace(errors=[], instruments={'MSFT': None},
                    session_policy={}, port=Port()), orders={},
                    clock=SimpleNamespace(timestamp_ns=lambda: int(t.clock[0]*1e9)),
                    generate_order_submitted=lambda native_order: None, generate_order_rejected=rejected)
        asyncio.run(AlpacaExecutionClient._submit_order(client, SimpleNamespace(order=order)))
        self.assertEqual(reasons, ['submission prevented before HTTP request'])
        self.assertNotIn(str(cid), t.strategy.pending)
        self.assertEqual(t.ledger.exit_state('MSFT'), {})

    def test_named_local_codes_survive_submission_not_sent_subclasses(self):
        import transport
        from safety import NAMED_EXIT_LOCAL_REFUSALS, PERMANENT_EXIT_LOCAL_REFUSALS
        self.assertEqual(PERMANENT_EXIT_LOCAL_REFUSALS, {
            'global_stop_latched', 'recovery_observation_integrity_lost'})
        self.assertEqual(NAMED_EXIT_LOCAL_REFUSALS, {
            'global_stop_latched', 'outside_allowed_session', 'recovery_observation_integrity_lost'})
        for code in NAMED_EXIT_LOCAL_REFUSALS:
            with self.subTest(code=code):
                error = transport.OrderContractRefused(code)
                self.assertEqual(error.refusal_code, code)
                self.assertEqual(transport.exit_not_sent_reason(error), 'exit_submission_not_sent:' + code)


@unittest.skipUnless(NATIVE, 'requires pinned native runtime')
class NativeSellRisk(unittest.TestCase):
    """Real rc5 LiveNode risk with synthetic quotes and broker fills only."""

    def test_native_sizing_fixture_isolates_every_stop_binding(self):
        from tests.adaptive_paper_hermetic import patch_default_stop, restore_default_stop
        token = patch_default_stop()
        self.addCleanup(restore_default_stop, token)
        # Model an active canonical latch entirely under a private fixture root.
        (Path(token[0].name) / 'STOP').write_text('fixture active latch\n')
        self.exercise_exit('fixed')

    def test_native_rate_limit_expiry_retries_the_owned_exit(self):
        from native_adapter import build_node
        from runner import Controller
        import runner
        import native_strategy
        from simulation import SimulatedPort
        from tests.adaptive_paper_hermetic import FixtureClock, patch_default_stop, restore_default_stop
        from nautilus_trader.model import ClientOrderId, InstrumentId, OrderSide, Price, Quantity, TimeInForce
        token = patch_default_stop()
        self.addCleanup(restore_default_stop, token)
        host_latch = Path.home() / '.local/state/native-agent-stack/alpaca-paper/STOP'
        for module in (safety, runner, native_strategy):
            self.assertNotEqual(module.DEFAULT_STOP.resolve(), host_latch)
            self.assertTrue(module.DEFAULT_STOP.resolve().is_relative_to(Path(token[0].name).resolve()))
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            clock = FixtureClock(datetime(2026, 10, 13, 15, tzinfo=timezone.utc).timestamp())
            config, limits, pc = load_config(SOURCE / 'config-leverage-1x.json')
            limits = replace(limits, capital_usd=D(20000), max_gross_exposure_usd=D(20000),
                             max_order_notional_usd=D(10000), max_order_qty=D(100))
            pc = replace(pc, capital=20000, gross_cap=20000, max_order_notional=10000,
                         rebalance_seconds=.01, min_hold_seconds=.001)
            with clock.patched():
                ledger = Ledger(root / 'ledger.sqlite', limits)
                self.addCleanup(ledger.close)
                ledger.start_trial(clock.time() - 60)
                controller = Controller(ledger, clock.time() + 3600, market_open=True,
                                        stop_file=root / 'STOP', clock=clock.time)
                port = controller.port = SimulatedPort(controller, pc.symbols, price=lambda s, t: D('99.97'))
                policy = AdaptivePolicy(pc, leverage_policy=config['_leverage_policy'])
                strategy = NativeExitProbe(policy, ledger, 'rate-regression', stop_file=root / 'STOP',
                                           clock=clock.time, account_multiplier=D(4))
                strategy.enabled = False
                strategy.observed_orders, strategy.observed_denials = [], []
                for i in range(40):
                    for symbol in pc.symbols:
                        policy.observe(symbol, 100, 100, clock.time() - 40 + i)
                session = build_node(port, [{'symbol': s} for s in pc.symbols], [strategy],
                                     max_order_submit_rate='1/00:00:02')

                async def wait(predicate):
                    end = time.monotonic() + 5
                    while not predicate():
                        self.assertLess(time.monotonic(), end, 'native event not observed')
                        await asyncio.sleep(.01)

                async def exercise():
                    task = asyncio.create_task(session.run_async())
                    try:
                        await wait(lambda: strategy.started and strategy.received_quotes >= len(pc.symbols))
                        buy = strategy.order_factory.limit(InstrumentId.from_str('AAPL.ALPACA'),
                            OrderSide.BUY, Quantity.from_int(1), Price.from_str('100.00'),
                            time_in_force=TimeInForce.DAY, client_order_id=ClientOrderId('rate-entry'))
                        strategy.submit_order(buy)
                        await wait(lambda: strategy.native_fills == 1)
                        port.price = lambda symbol, tick: D('110.01') if symbol == 'AAPL' else D('100.01')
                        await wait(lambda: policy.latest['AAPL'].bid == 110)
                        strategy.rebalance(clock.time())
                        await wait(lambda: bool(strategy.observed_denials))
                        self.assertEqual(strategy.observed_denials, ['RATE_LIMIT_EXCEEDED'])
                        future_retry = ledger.exit_retry_allowed('AAPL', clock.time() + 120)
                        await asyncio.sleep(6.2)  # Expire the real native window and durable pacing.
                        strategy.rebalance(clock.time())
                        await asyncio.sleep(.2)
                        print('NATIVE_RATE_MEASUREMENT', {'reason': strategy.observed_denials[0],
                            'retry_at_120s': future_retry,
                            'held_after_expiry': {s: str(p.qty) for s, p in ledger.positions().items()}})
                        self.assertEqual(ledger.positions(), {}, 'expired native throttle stranded the exit')
                        self.assertTrue(future_retry)
                    finally:
                        session.stop()
                        try:
                            await asyncio.wait_for(task, 5)
                        except (asyncio.TimeoutError, asyncio.CancelledError):
                            task.cancel()
                            await asyncio.gather(task, return_exceptions=True)

                asyncio.run(exercise())

    def test_integrity_loss_hands_off_held_position_without_spending_exit_budget(self):
        self.exercise_integrity_handoff()

    def test_integrity_handoff_requests_entry_cancellation_before_node_stop(self):
        self.exercise_integrity_handoff(resting_entry=True)

    def exercise_integrity_handoff(self, *, resting_entry=False):
        import json
        import threading
        import native_strategy
        import runner
        import transport
        from recovery import recover
        from simulation import SimulatedPort, invoke
        from tests.adaptive_paper_hermetic import FixtureClock, patch_default_stop, restore_default_stop

        lifecycle = []

        class ObservedStrategy(native_strategy.AdaptiveStrategy):
            def cancel_order(self, order, *args, **kwargs):
                lifecycle.append('cancel_requested')
                return super().cancel_order(order, *args, **kwargs)

            def on_stop(self):
                lifecycle.append('node_stop')
                return super().on_stop()

        class LossPort(SimulatedPort):
            loss_at = None

            async def cancel(self, client_id):
                await self.controller.before_request('cancel', client_id=client_id)
                result = dict(self.orders[client_id], status='canceled', updated_at_ns=time.time_ns())
                self.orders[client_id] = result
                await invoke(self.sink_observation, dict(result))
                await invoke(self.on_order, dict(result))
                return result

            async def submit(self, payload):
                if self.loss_at is not None:
                    self.controller.before_submit(payload)
                    await self.controller.before_request('submit', client_id=payload['client_order_id'])
                    transport.AlpacaPaperTransport._wire_guard(self, payload)
                if resting_entry and payload['symbol'] == 'MSFT':
                    self.controller.before_submit(payload)
                    await self.controller.before_request('submit', client_id=payload['client_order_id'])
                    result = dict(payload, id='sim-resting-entry', status='new', filled_qty='0',
                                  filled_avg_price=None, updated_at_ns=time.time_ns())
                    self.orders[payload['client_order_id']] = result
                    await invoke(self.sink_observation, dict(result))
                    await invoke(self.on_order, dict(result))
                else:
                    result = await super().submit(payload)
                if payload['side'] == 'buy' and (not resting_entry or payload['symbol'] == 'MSFT'):
                    self.loss_at = time.monotonic()
                    self._state_lock = threading.RLock()
                    self._reasons = {'queue_overflow'}
                    self.health.update(frozen=True, ready=False, reasons=['queue_overflow'])
                return result

        with tempfile.TemporaryDirectory(dir='/var/tmp') as name:
            root = Path(name)
            clock = FixtureClock(datetime(2026, 10, 13, 15, 0, tzinfo=timezone.utc).timestamp())
            token = patch_default_stop()
            self.addCleanup(restore_default_stop, token)
            config, limits, policy = load_config(SOURCE / 'config.json')
            config.update(duration_seconds=3, cleanup_seconds=1, order_timeout_seconds=.1)
            limits = replace(limits, trial_seconds=3, cleanup_seconds=1)
            with clock.patched():
                ledger = Ledger(root / 'ledger.sqlite', limits)
                self.addCleanup(ledger.close)
                ledger.start_trial(clock.time())
                controller = runner.Controller(ledger, clock.time() + 3600, market_open=True,
                                               clock=clock.time, stop_file=root / 'STOP')
                port = controller.port = LossPort(controller, policy.symbols)
                calls, phase = [], ['native']
                budget = ledger.request_budget

                def measured_budget(now, kind, *args, **kwargs):
                    wait = budget(now, kind, *args, **kwargs)
                    if kind == 'submit' and port.loss_at is not None:
                        calls.append((phase[0], wait))
                    return wait

                def allocation(*args, **kwargs):
                    exiting = kwargs.get('force_exit', False)
                    targets = {'AAPL': 1, 'MSFT': 1} if resting_entry else {'AAPL': 1}
                    return SimpleNamespace(targets={} if exiting else targets,
                        exits={'AAPL': 'trial_end'} if exiting else {}, signals=[], regime='fixture',
                        effective_leverage=1)

                async def exercise():
                    with patch.object(ledger, 'request_budget', side_effect=measured_budget), \
                         patch.object(native_strategy, 'AdaptiveStrategy', ObservedStrategy), \
                         patch.object(runner.AdaptivePolicy, 'decide', side_effect=allocation):
                        outcome = await runner.run_native(controller, policy,
                            [{'symbol': s} for s in policy.symbols], 'integrity-fixture', config, '100000')
                        elapsed = time.monotonic() - port.loss_at if port.loss_at is not None else float('inf')
                        held = {s: str(p.qty) for s, p in ledger.positions().items()}
                        fresh = SimulatedPort(controller, policy.symbols)
                        fresh.orders, fresh.positions = dict(port.orders), dict(port.positions)
                        fresh.executions, fresh.cash = dict(port.executions), port.cash
                        fresh.adopt_intents = lambda intents: None
                        controller.port = fresh
                        phase[0] = 'recovery'
                        cleanup = await recover(controller,
                            {'trial_id': 'integrity-fixture', 'baseline_cash': '100000'}, config)
                        return outcome, cleanup, elapsed, held

                outcome, cleanup, elapsed, held = asyncio.run(exercise())
                metrics = {'loss_to_handoff_seconds': round(elapsed, 3), 'held_at_handoff': held,
                           'post_loss_submit_budget_calls': calls, 'recovery_status': cleanup['status']}
                if resting_entry:
                    metrics.update(lifecycle=lifecycle, recovery_errors=cleanup['errors'])
                print('F1_MEASUREMENT ' + json.dumps(metrics, sort_keys=True))
                self.assertEqual(held, {'AAPL': '1'})
                self.assertIn(outcome['status'], ('stream_frozen', 'needs_attention'))
                self.assertLess(elapsed, 2, metrics)
                if resting_entry:
                    self.assertIn('cancel_requested', lifecycle, lifecycle)
                    self.assertLess(lifecycle.index('cancel_requested'), lifecycle.index('node_stop'))
                self.assertEqual([c for c in calls if c[0] == 'native'], [])
                self.assertEqual([c for c in calls if c[0] == 'recovery'], [('recovery', 0)])
                self.assertEqual(cleanup['status'], 'passed', cleanup['errors'])
                self.assertEqual(ledger.positions(), {})

    def exercise_exit(self, quantity_mode, *, owned=100, cap=10000):
        from native_adapter import build_node
        from runner import Controller
        from simulation import SimulatedPort
        from tests.adaptive_paper_hermetic import FixtureClock, patch_default_stop, restore_default_stop
        from nautilus_trader.model import ClientOrderId, InstrumentId, OrderSide, Price, Quantity, TimeInForce

        with tempfile.TemporaryDirectory(dir='/var/tmp') as root:
            root = Path(root)
            token = patch_default_stop()
            self.addCleanup(restore_default_stop, token)
            # Resolve fixture paths only. The host latch is a lexical comparison
            # value and is never inspected.
            import runner
            import native_strategy
            host_latch = Path.home() / '.local/state/native-agent-stack/alpaca-paper/STOP'
            for module in (safety, runner, native_strategy):
                self.assertNotEqual(module.DEFAULT_STOP.resolve(), host_latch)
                self.assertTrue(module.DEFAULT_STOP.resolve().is_relative_to(Path(token[0].name).resolve()))
            # Fix the fixture to RTH while advancing normally for quote age,
            # pacing and fills. The real native risk engine keeps its own clock.
            fixture_clock = FixtureClock(datetime(2026, 10, 13, 15, 0, tzinfo=timezone.utc).timestamp())
            now = fixture_clock.time()
            config, limits, policy_config = load_config(SOURCE / 'config-leverage-1x.json')
            limits = replace(limits, capital_usd=D('20000'), max_gross_exposure_usd=D('20000'),
                             max_order_notional_usd=D(cap), max_order_qty=D(100),
                             max_order_qty_mode=quantity_mode)
            policy_config = replace(policy_config, capital=20000, gross_cap=20000,
                                    max_order_notional=cap, rebalance_seconds=.01, min_hold_seconds=.001)
            with fixture_clock.patched(), patch.object(safety, 'DEFAULT_STOP', root / 'STOP'):
                ledger = Ledger(root / 'ledger.sqlite3', limits)
                self.addCleanup(ledger.close)
                ledger.start_trial(now - 60)
                controller = Controller(ledger, now + 3600, market_open=True, stop_file=root / 'STOP',
                                        clock=fixture_clock.time)
                # Mid 110.01 gives bid 110.00 and the actual sell limit 109.98.
                port = SimulatedPort(controller, policy_config.symbols,
                                     price=lambda symbol, tick: D('99.97'))
                controller.port = port
                policy = AdaptivePolicy(policy_config, leverage_policy=config['_leverage_policy'])
                strategy = NativeExitProbe(policy, ledger, 'native-risk', stop_file=root / 'STOP',
                                           clock=fixture_clock.time, account_multiplier=D(4))
                strategy.enabled = False
                strategy.observed_orders, strategy.observed_denials = [], []
                policy.sync_positions(strategy.positions(), now - 60)
                for i in range(40):
                    for symbol in policy_config.symbols:
                        policy.observe(symbol, 100, 100, now - 40 + i)
                session = build_node(port, [{'symbol': s} for s in policy_config.symbols], [strategy])

                async def wait_until(predicate):
                    deadline = time.monotonic() + 5
                    while not predicate():
                        if time.monotonic() >= deadline:
                            self.fail('native fixture did not reach its expected event')
                        await asyncio.sleep(.01)

                async def exercise():
                    running = asyncio.create_task(session.run_async())
                    try:
                        await wait_until(lambda: strategy.started and strategy.received_quotes >= len(policy_config.symbols))
                        # The adapter requires flat startup. Acquire the 100 shares
                        # through the same real factory, risk engine and fill path.
                        entry = strategy.order_factory.limit(
                            InstrumentId.from_str('AAPL.ALPACA'), OrderSide.BUY, Quantity.from_int(owned),
                            Price.from_str('100.00'), time_in_force=TimeInForce.DAY,
                            client_order_id=ClientOrderId('native-entry'))
                        strategy.submit_order(entry)
                        await wait_until(lambda: strategy.native_fills == 1 or strategy.observed_denials)
                        self.assertEqual(strategy.observed_denials, [])
                        self.assertEqual(ledger.positions()['AAPL'].qty, D(owned))
                        port.price = lambda symbol, tick: D('110.01') if symbol == 'AAPL' else D('100.01')
                        await wait_until(lambda: policy.latest['AAPL'].bid == 110)
                        decision = strategy.rebalance(fixture_clock.time())
                        self.assertEqual(decision.exits.get('AAPL'), 'take_profit')
                        await wait_until(lambda: strategy.observed_denials or not ledger.positions()
                                         or ledger.positions()['AAPL'].qty < owned)
                        first_remaining = ledger.positions().get('AAPL')
                        first_remaining = first_remaining.qty if first_remaining else D(0)
                        if not strategy.observed_denials and ledger.positions():
                            await asyncio.sleep(.03)
                            strategy.rebalance(fixture_clock.time())
                            await wait_until(lambda: strategy.observed_denials or not ledger.positions())
                        return first_remaining
                    finally:
                        session.stop()
                        await asyncio.wait_for(running, timeout=5)

                first_remaining = asyncio.run(exercise())
                self.assertEqual(strategy.observed_denials, [], 'real rc5 risk refused the exit')
                self.assertEqual(session.errors, [])
                self.assertEqual(strategy.callback_faults, [])
                self.assertEqual(strategy.native_rejections, 0)
                self.assertEqual(first_remaining, D(10) if owned == 100 else D(0))
                sells = [o for o in strategy.observed_orders if o.side == OrderSide.SELL]
                self.assertEqual([D(str(o.quantity)) for o in sells], [D(90), D(10)] if owned == 100 else [D(1)])
                self.assertTrue(all(o.quantity.precision == 0 for o in sells))
                self.assertEqual(str(sells[0].price), '109.98')
                self.assertGreater(D(owned) * D(str(sells[0].price)), cap)
                self.assertEqual(len(port.orders), 3 if owned == 100 else 2)
                if owned == 100:
                    self.assertTrue(all(D(o['qty']) * D(o['limit_price']) <= cap for o in port.orders.values()))
                else:
                    self.assertEqual(ledger.db.execute("SELECT count(*) FROM events WHERE kind='exit_cap_exceeded_reduce_only'").fetchone()[0], 1)
                self.assertEqual(strategy.native_fills, 3 if owned == 100 else 2)
                self.assertEqual(ledger.positions(), {})
                self.assertEqual(ledger.unresolved(), [])

    def test_fixed_quantity_exit_reduces_position_through_native_risk(self):
        self.exercise_exit('fixed')

    def test_above_cap_take_profit_splits_across_ticks_without_native_refusal(self):
        self.exercise_exit('notional')

    def test_minimum_one_owned_share_passes_real_native_risk(self):
        self.exercise_exit('notional', owned=1, cap=100)


if __name__ == '__main__':
    unittest.main()
