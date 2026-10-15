"""Durable exit priority through the real strategy, policy and private Ledger.

The order factory and broker acknowledgements are synthetic; no broker or host
runtime state is used. Keep the exact TP-to-stop cases runnable on bare main.
"""
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal as D
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tests import test_adaptive_paper_sell_chunks as sell_chunks

setUpModule = sell_chunks.setUpModule


@unittest.skipUnless(sell_chunks.NATIVE, 'requires pinned native runtime')
class CommittedExitPriority(unittest.TestCase):
    def setUp(self):
        self.f = sell_chunks.AdaptiveSellChunks()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        # Main lacks durable sell chunking. Its entry share cap keeps the first
        # TP within the same $10,000 envelope as the patch's 99-share chunk.
        self.f.policy.config = replace(self.f.policy.config,
                                       max_shares=99,
                                       exit_replace_enabled=True)
        self.f.fill_immediately = False
        self.cancels = []
        self.f.strategy.cancel_order = lambda cid: self.cancels.append(str(cid))

    def start_take_profit(self, tolerance=100):
        t = self.f
        t.policy.config = replace(t.policy.config,
                                  exit_replace_tolerance_bps=tolerance)
        decision = t.tick('100.50')
        self.assertEqual(decision.exits['AAPL'], 'take_profit')
        t.assert_no_denials()
        self.assertEqual(len(t.orders), 1)
        order = t.orders[0]
        self.assertEqual(D(str(order.quantity)), D(99))
        self.assertEqual(D(str(order.price)), D('100.48'))
        self.assertEqual(t.ledger.positions()['AAPL'].qty, D(100))
        return order

    def acknowledge_cancel(self, order):
        t = self.f
        t.ledger.record_order(str(order.client_order_id), 'fixture-cancel',
                              'canceled', '0', None, timestamp=t.clock[0])
        t.strategy.on_order_canceled(SimpleNamespace(client_order_id=order.client_order_id))

    def assert_stop_replaces_unfinished_take_profit(self, tolerance):
        t = self.f
        order = self.start_take_profit(tolerance)
        decision = t.tick('99.70')
        self.assertEqual(decision.exits['AAPL'], 'stop_loss')
        self.assertEqual(self.cancels, [str(order.client_order_id)])
        self.assertEqual(len(t.orders), 1, 'replacement must wait for cancellation')
        staged = t.strategy.pending[str(order.client_order_id)]['replace_with']
        self.assertEqual(staged['reason'], 'stop_loss')
        self.assertEqual(staged['price_rule'], 'stop')
        t.fill_immediately = True
        self.acknowledge_cancel(order)
        self.assertEqual(D(str(t.orders[-1].price)), D('99.68'))
        self.assertIn('reason=stop_loss', t.orders[-1].tags)
        t.tick('99.70')  # bare main caps the replacement at 99, leaving one share
        self.assertEqual(t.ledger.positions(), {})
        t.assert_no_denials()

    def test_unfinished_full_take_profit_promotes_stop_at_zero_tolerance(self):
        self.assert_stop_replaces_unfinished_take_profit(0)

    def test_unfinished_full_take_profit_promotes_stop_inside_price_tolerance(self):
        self.assert_stop_replaces_unfinished_take_profit(100)

    def test_stop_arriving_during_cancel_promotes_replacement_at_ack(self):
        t = self.f
        order = self.start_take_profit(0)
        t.tick('100.60')
        self.assertEqual(self.cancels, [str(order.client_order_id)])
        self.assertEqual(t.strategy.pending[str(order.client_order_id)]['replace_with']['reason'],
                         'take_profit')
        decision = t.tick('99.70')
        self.assertEqual(decision.exits['AAPL'], 'stop_loss')
        self.assertEqual(self.cancels, [str(order.client_order_id)])
        self.assertEqual(len(t.orders), 1)
        t.fill_immediately = True
        self.acknowledge_cancel(order)
        self.assertIn('reason=stop_loss', t.orders[-1].tags)
        self.assertIn('price_rule=stop', t.orders[-1].tags)
        self.assertEqual(D(str(t.orders[-1].price)), D('99.68'))
        t.tick('99.70')
        self.assertEqual(t.ledger.positions(), {})
        t.assert_no_denials()

    def test_stop_gap_and_corporate_action_strengthen_same_flat_target(self):
        t = self.f
        self.start_take_profit()
        # Keep the resting order unresolved so every transition concerns the
        # same unfinished commitment. Guard outcomes are synthetic inputs.
        t.policy.config = replace(t.policy.config, exit_replace_enabled=False)
        t.tick('99.70')
        self.assertEqual(t.ledger.exit_state('AAPL')['reason'], 'stop_loss')
        with patch.object(t.strategy, '_gap_risk_stop_symbols', return_value={'AAPL'}):
            t.tick('100.50')
        self.assertEqual(t.ledger.exit_state('AAPL')['reason'], 'gap_risk_stop')
        with patch.object(t.strategy, '_corporate_action_guard_symbols',
                          return_value=(set(), {'AAPL'})):
            t.tick('100.50')
        state = t.ledger.exit_state('AAPL')
        self.assertEqual(state['reason'], 'corporate_action_flatten')
        self.assertEqual(state['target'], '0')
        # Reopen the actual journal; a later weaker policy signal must not
        # overwrite its strongest unfinished reason after process recovery.
        from safety import Ledger
        path, limits = t.ledger.path, t.ledger.limits
        t.ledger.close()
        t.ledger = Ledger(path, limits)
        t.addCleanup(t.ledger.close)
        t.strategy.ledger = t.ledger
        t.tick('99.70')
        restored = t.ledger.exit_state('AAPL')
        for key in ('target', 'reason', 'completed'):
            self.assertEqual(restored[key], state[key])
        self.assertEqual(len(t.orders), 1)
        t.assert_no_denials()

    def test_lower_target_does_not_downgrade_stronger_reason(self):
        t = self.f
        t.ledger.record_exit_state('AAPL',
            {'target': '50', 'reason': 'stop_loss', 'completed': False},
            transition='fixture_partial_risk_reduction')
        t.policy.decide = lambda *args, **kwargs: SimpleNamespace(
            targets={'AAPL': 25}, exits={}, signals=[], regime='fixture',
            effective_leverage=1)
        t.tick('100')
        self.assertEqual(t.ledger.exit_state('AAPL')['target'], '25')
        self.assertEqual(t.ledger.exit_state('AAPL')['reason'], 'stop_loss')
        self.assertEqual(D(str(t.orders[0].quantity)), D(75))
        self.assertIn('reason=rebalance', t.orders[0].tags)
        self.assertEqual(t.strategy.pending[str(t.orders[0].client_order_id)]['price_rule'], 'market')
        t.assert_no_denials()

    def test_stronger_reason_does_not_relax_committed_target(self):
        t = self.f
        self.start_take_profit()
        # A synthetic partial stop isolates the independent target/reason axes.
        t.policy.decide = lambda *args, **kwargs: SimpleNamespace(
            targets={'AAPL': 50}, exits={'AAPL': 'stop_loss'}, signals=[],
            regime='fixture', effective_leverage=1)
        t.tick('99.70')
        state = t.ledger.exit_state('AAPL')
        self.assertEqual(state['target'], '0')
        self.assertEqual(state['reason'], 'stop_loss')
        staged = t.strategy.pending[str(t.orders[0].client_order_id)]['replace_with']
        self.assertEqual(staged['quantity'], D(100))
        self.assertEqual(staged['reason'], 'stop_loss')
        t.assert_no_denials()

    def test_completed_stop_allows_a_new_take_profit_cycle(self):
        from safety import Quote
        t = self.f
        t.ledger.limits = replace(t.ledger.limits,
                                  max_gross_loss_usd=D(100), max_drawdown_usd=D(100))
        t.fill_immediately = True
        decision = t.tick('99.70')
        self.assertEqual(decision.exits['AAPL'], 'stop_loss')
        self.assertEqual(t.ledger.positions(), {})
        self.assertTrue(t.ledger.exit_state('AAPL')['completed'])
        t.ledger.reserve_intent('new-position', 'AAPL', 'buy', '100', '100',
            quote=Quote('AAPL', '100', '100', t.clock[0]), now=t.clock[0],
            market_open=True, session_close=t.now + 3600, stop_file=t.root / 'STOP')
        t.ledger.record_order('new-position', 'fixture-new-position', 'filled', '100', '100',
                              timestamp=t.clock[0])
        t.fill_immediately = False
        decision = t.tick('100.50')
        self.assertEqual(decision.exits['AAPL'], 'take_profit')
        state = t.ledger.exit_state('AAPL')
        self.assertEqual(state['target'], '0')
        self.assertEqual(state['reason'], 'take_profit')
        self.assertFalse(state['completed'])
        t.assert_no_denials()


@unittest.skipUnless(sell_chunks.NATIVE, 'requires pinned native runtime')
class ExitPricingBasisRegressions(unittest.TestCase):
    def exercise_market_commitment(self, initial_reason, next_reason, tolerance):
        t = sell_chunks.AdaptiveSellChunks()
        try:
            t.setUp()
            t.fill_immediately = False
            t.policy.config = replace(t.policy.config, max_shares=99,
                exit_replace_enabled=True, exit_replace_tolerance_bps=tolerance)
            cancels = []
            t.strategy.cancel_order = lambda cid: cancels.append(str(cid))
            if initial_reason == 'quote_stale':
                # Real policy commits an exit, but its stale quote cannot be used.
                t.clock[0] += 4
                decision = t.strategy.rebalance(t.clock[0])
                self.assertEqual(decision.exits['AAPL'], 'quote_stale')
            else:
                # A temporary halt holds dispatch while the real action path
                # commits the injected risk/guard signal, then clears next tick.
                with patch.object(t.strategy, '_halted', return_value=True):
                    if initial_reason == 'risk_off':
                        with patch.object(t.policy, '_regime_and_signals',
                                return_value=({}, True, True, 'risk_off', [])):
                            t.tick('100.50')
                    elif initial_reason == 'gap_risk_stop':
                        with patch.object(t.strategy, '_gap_risk_stop_symbols',
                                          return_value={'AAPL'}):
                            t.tick('100.50')
                    else:
                        with patch.object(t.strategy, '_corporate_action_guard_symbols',
                                          return_value=(set(), {'AAPL'})):
                            t.tick('100.50')
            self.assertEqual(t.ledger.exit_state('AAPL')['reason'], initial_reason)
            self.assertEqual(t.orders, [])
            decision = t.tick('100.50')
            self.assertEqual(decision.exits['AAPL'], 'take_profit')
            self.assertEqual(len(t.orders), 1)
            order = t.orders[0]
            self.assertEqual(D(str(order.quantity)), D(99))
            self.assertEqual(D(str(order.price)), D('100.48'))
            price = '99.70' if next_reason == 'stop_loss' else '100.30'
            decision = t.tick(price)
            self.assertEqual(decision.exits['AAPL'], next_reason)
            self.assertEqual(t.ledger.exit_state('AAPL')['target'], '0')
            self.assertEqual(t.ledger.exit_state('AAPL')['reason'], initial_reason)
            self.assertEqual(cancels, [str(order.client_order_id)])
            self.assertEqual(len(t.orders), 1, 'wait for the cancel acknowledgement')
            staged = t.strategy.pending[str(order.client_order_id)]['replace_with']
            expected_rule = 'stop' if next_reason == 'stop_loss' else 'trailing'
            self.assertEqual(staged['price_rule'], expected_rule)
            t.fill_immediately = True
            t.ledger.record_order(str(order.client_order_id), 'fixture-cancel',
                                  'canceled', '0', None, timestamp=t.clock[0])
            t.strategy.on_order_canceled(SimpleNamespace(client_order_id=order.client_order_id))
            self.assertIn('price_rule=' + expected_rule, t.orders[-1].tags)
            t.tick(price)
            self.assertEqual(t.ledger.positions(), {})
            t.assert_no_denials()
        finally:
            t.doCleanups()

    def test_current_stop_and_trailing_replace_market_reason_commitments(self):
        for initial in ('quote_stale', 'risk_off', 'gap_risk_stop', 'corporate_action_flatten'):
            for current in ('stop_loss', 'trailing_stop'):
                for tolerance in (0, 100):
                    with self.subTest(durable=initial, current=current, tolerance=tolerance):
                        self.exercise_market_commitment(initial, current, tolerance)

    def test_volatility_preset_stop_then_trailing_changes_price_basis(self):
        for tolerance in (0, 100):
            with self.subTest(tolerance=tolerance):
                t = sell_chunks.AdaptiveSellChunks()
                try:
                    t.setUp()
                    preset = json.loads((sell_chunks.SOURCE / 'exploratory-exit-presets.json')
                                        .read_text())['adaptive']['volatility']
                    t.policy.config = replace(t.policy.config, **preset,
                        exit_replace_enabled=True, exit_replace_tolerance_bps=tolerance)
                    t.fill_immediately = False
                    cancels, volatility = [], [5]
                    t.strategy.cancel_order = lambda cid: cancels.append(str(cid))
                    # Real exit rules consume the preset and changing volatility.
                    # Only the upstream feature observation is a controlled input.
                    with patch.object(t.policy, '_regime_and_signals', side_effect=lambda now:
                            ({'AAPL': {'vol': volatility[0]}}, True, False, 'range', [])):
                        warm = t.tick('100.35')
                        self.assertNotIn('AAPL', warm.exits)
                        self.assertEqual(t.orders, [])
                        first = t.tick('99.70')
                        self.assertEqual(first.exits['AAPL'], 'stop_loss')
                        self.assertEqual(len(t.orders), 1)
                        order = t.orders[0]
                        self.assertEqual(t.strategy.pending[str(order.client_order_id)]['price_rule'], 'stop')
                        volatility[0] = 20
                        second = t.tick('99.75')
                        self.assertEqual(second.exits['AAPL'], 'trailing_stop')
                    self.assertEqual(t.ledger.exit_state('AAPL')['reason'], 'stop_loss')
                    self.assertEqual(t.ledger.exit_state('AAPL')['target'], '0')
                    self.assertEqual(cancels, [str(order.client_order_id)])
                    staged = t.strategy.pending[str(order.client_order_id)]['replace_with']
                    self.assertEqual(staged['price_rule'], 'trailing')
                    t.assert_no_denials()
                finally:
                    t.doCleanups()

    def test_weaker_partial_profit_changes_basis_without_relaxing_full_stop(self):
        for tolerance in (0, 100):
            with self.subTest(tolerance=tolerance):
                t = sell_chunks.AdaptiveSellChunks()
                try:
                    t.setUp()
                    t.policy.config = replace(t.policy.config, take_profit_fraction=.5,
                        exit_replace_enabled=True, exit_replace_tolerance_bps=tolerance)
                    t.fill_immediately = False
                    cancels = []
                    t.strategy.cancel_order = lambda cid: cancels.append(str(cid))
                    self.assertEqual(t.tick('99.70').exits['AAPL'], 'stop_loss')
                    order = t.orders[0]
                    self.assertEqual(t.tick('100.50').exits['AAPL'], 'take_profit')
                    state = t.ledger.exit_state('AAPL')
                    self.assertEqual(state['target'], '0')
                    self.assertEqual(state['reason'], 'stop_loss')
                    self.assertFalse(state['completed'])
                    self.assertEqual(cancels, [str(order.client_order_id)])
                    self.assertEqual(len(t.orders), 1)
                    staged = t.strategy.pending[str(order.client_order_id)]['replace_with']
                    self.assertEqual(staged['quantity'], D(100))
                    self.assertEqual(staged['price_rule'], 'take_profit')
                    t.assert_no_denials()
                finally:
                    t.doCleanups()

    def test_second_basis_change_during_cancel_uses_confirmed_residual(self):
        for tolerance in (0, 100):
            with self.subTest(tolerance=tolerance):
                t = sell_chunks.AdaptiveSellChunks()
                try:
                    t.setUp()
                    preset = json.loads((sell_chunks.SOURCE / 'exploratory-exit-presets.json')
                                        .read_text())['adaptive']['volatility']
                    t.policy.config = replace(t.policy.config, **preset,
                        exit_replace_enabled=True, exit_replace_tolerance_bps=tolerance)
                    t.fill_immediately = False
                    cancels, volatility = [], [5]
                    t.strategy.cancel_order = lambda cid: cancels.append(str(cid))
                    with patch.object(t.policy, '_regime_and_signals', side_effect=lambda now:
                            ({'AAPL': {'vol': volatility[0]}}, True, False, 'range', [])):
                        self.assertEqual(t.tick('100.50').exits['AAPL'], 'take_profit')
                        order = t.orders[0]
                        self.assertEqual(t.tick('99.70').exits['AAPL'], 'stop_loss')
                        volatility[0] = 20
                        self.assertEqual(t.tick('99.75').exits['AAPL'], 'trailing_stop')
                    self.assertEqual(cancels, [str(order.client_order_id)])
                    self.assertEqual(len(t.orders), 1, 'no sell while cancel remains outstanding')
                    # The terminal cancel proves 40 shares filled before it; the
                    # acknowledgement must use the now-owned 60, not staged 100.
                    t.ledger.record_order(str(order.client_order_id), 'fixture-cancel',
                        'canceled', '40', str(order.price), timestamp=t.clock[0])
                    self.assertEqual(t.ledger.positions()['AAPL'].qty, D(60))
                    t.strategy.on_order_canceled(SimpleNamespace(client_order_id=order.client_order_id))
                    self.assertEqual(len(t.orders), 2)
                    self.assertEqual(D(str(t.orders[-1].quantity)), D(60))
                    self.assertIn('price_rule=trailing', t.orders[-1].tags)
                    self.assertEqual(len(t.ledger.unresolved()), 1)
                    t.assert_no_denials()
                finally:
                    t.doCleanups()

    def test_stronger_target_during_cancel_rereads_the_entire_residual(self):
        for tolerance in (0, 100):
            with self.subTest(tolerance=tolerance):
                t = sell_chunks.AdaptiveSellChunks()
                try:
                    t.setUp()
                    t.policy.config = replace(t.policy.config, take_profit_fraction=.5,
                        exit_replace_enabled=True, exit_replace_tolerance_bps=tolerance)
                    t.fill_immediately = False
                    session, cancels = ['RTH'], []
                    t.strategy._exit_session_at = lambda now: session[0]
                    t.strategy.cancel_order = lambda cid: cancels.append(str(cid))
                    t.tick('100.50')
                    order = t.orders[0]
                    self.assertEqual(D(str(order.quantity)), D(50))
                    # A synthetic session transition changes the price rule
                    # without changing the committed partial target.
                    session[0] = 'POST'
                    t.tick('100.50')
                    self.assertEqual(cancels, [str(order.client_order_id)])
                    staged = t.strategy.pending[str(order.client_order_id)]['replace_with']
                    self.assertEqual(staged['quantity'], D(50))
                    session[0] = 'RTH'
                    self.assertEqual(t.tick('99.70').exits['AAPL'], 'stop_loss')
                    self.assertEqual(t.ledger.exit_state('AAPL')['target'], '0')
                    self.assertEqual(len(t.orders), 1)
                    self.assertEqual(len(cancels), 1)
                    t.ledger.record_order(str(order.client_order_id), 'fixture-cancel',
                                          'canceled', '0', None, timestamp=t.clock[0])
                    t.strategy.on_order_canceled(SimpleNamespace(client_order_id=order.client_order_id))
                    self.assertEqual(D(str(t.orders[-1].quantity)), D(100))
                    self.assertIn('price_rule=stop', t.orders[-1].tags)
                    self.assertEqual(len(t.ledger.unresolved()), 1)
                    t.assert_no_denials()
                finally:
                    t.doCleanups()

    def test_no_new_exit_keeps_the_last_basis_across_journal_reopen(self):
        from safety import Ledger
        for tolerance in (0, 100):
            with self.subTest(tolerance=tolerance):
                t = sell_chunks.AdaptiveSellChunks()
                try:
                    t.setUp()
                    t.policy.config = replace(t.policy.config,
                        exit_replace_enabled=True, exit_replace_tolerance_bps=tolerance)
                    t.fill_immediately = False
                    t.clock[0] += 4
                    t.strategy.rebalance(t.clock[0])
                    t.tick('100.50')
                    order = t.orders[0]
                    t.ledger.record_order(str(order.client_order_id), 'fixture-cancel',
                                          'canceled', '0', None, timestamp=t.clock[0])
                    t.strategy.on_order_canceled(SimpleNamespace(client_order_id=order.client_order_id))
                    path, limits = t.ledger.path, t.ledger.limits
                    t.ledger.close()
                    t.ledger = Ledger(path, limits)
                    t.addCleanup(t.ledger.close)
                    t.strategy = sell_chunks.NativeDispatch(t.policy, t.ledger, 'fixture',
                        stop_file=t.root / 'STOP', clock=lambda: t.clock[0], account_multiplier=D(4))
                    t.strategy.captured_factory = sell_chunks.CapturedOrderFactory()
                    t.strategy.started, t.strategy.enabled = True, False
                    t.strategy.submit_order = t.submit
                    t.strategy.cancel_order = lambda cid: None
                    decision = t.tick('100.36')
                    self.assertNotIn('AAPL', decision.exits)
                    self.assertEqual(len(t.orders), 2)
                    pending = t.strategy.pending[str(t.orders[-1].client_order_id)]
                    self.assertEqual(pending['price_rule'], 'take_profit')
                    self.assertEqual(t.ledger.exit_state('AAPL')['target'], '0')
                    self.assertEqual(t.ledger.exit_state('AAPL')['reason'], 'quote_stale')
                    t.assert_no_denials()
                finally:
                    t.doCleanups()


@unittest.skipUnless(sell_chunks.NATIVE, 'requires pinned native runtime')
class ClosedSessionExitRegressions(unittest.TestCase):
    def test_refusal_at_close_rearms_strategy_at_next_session_open(self):
        from safety import Quote, SafetyError
        from transport import SubmissionNotSent, exit_not_sent_reason
        t = sell_chunks.AdaptiveSellChunks()
        t.setUp()
        self.addCleanup(t.doCleanups)
        close = datetime(2026, 10, 13, 20, tzinfo=timezone.utc).timestamp()
        next_open = datetime(2026, 10, 14, 13, 30, tzinfo=timezone.utc).timestamp()
        window = {'open': True, 'close': close}
        t.strategy._exit_session_window = lambda now: (window['open'], window['close'])
        t.clock[0] = close - 3.5

        def close_before_wire(order):
            t.orders.append(order)
            with self.assertRaisesRegex(SafetyError, 'outside_allowed_session') as caught:
                t.ledger.reserve_intent(str(order.client_order_id), 'AAPL', 'sell',
                    str(order.quantity), str(order.price),
                    quote=Quote('AAPL', '100.50', '100.50', t.clock[0]), now=t.clock[0],
                    market_open=True, session_close=close, stop_file=t.root / 'STOP')
            reason = exit_not_sent_reason(SubmissionNotSent(str(caught.exception)))
            t.strategy.on_order_denied(SimpleNamespace(client_order_id=order.client_order_id,
                                                       reason=reason))

        t.strategy.submit_order = close_before_wire
        t.tick('100.50')
        self.assertEqual(len(t.orders), 1)
        self.assertEqual(t.ledger.positions()['AAPL'].qty, D(100))
        self.assertTrue(t.ledger.exit_state('AAPL').get('refusal'))
        window['open'] = False
        t.clock[0] = close + 60
        t.tick('100.50')
        self.assertEqual(len(t.orders), 1)
        t.ledger.resume_held_trial(next_open, 'next-session-fixture')
        t.now, t.clock[0] = next_open, next_open - 3
        window.update(open=True, close=next_open + 6.5 * 3600)
        t.strategy.submit_order = t.submit
        with patch.object(t.ledger, 'reconcile_exit_refusal',
                          side_effect=AssertionError('must not need a manual reconcile')):
            t.tick('100.50')
            t.tick('100.50')
        self.assertEqual(t.ledger.positions(), {})
        self.assertNotIn('refusal', t.ledger.exit_state('AAPL'))


if __name__ == '__main__':
    unittest.main()
