"""Durable exit priority through the real strategy, policy and private Ledger.

The order factory and broker acknowledgements are synthetic; no broker or host
runtime state is used. Keep the exact TP-to-stop cases runnable on bare main.
"""
from dataclasses import replace
from decimal import Decimal as D
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
        self.assertEqual(t.ledger.exit_state('AAPL'), state)
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
        self.assertIn('reason=stop_loss', t.orders[0].tags)
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


if __name__ == '__main__':
    unittest.main()
