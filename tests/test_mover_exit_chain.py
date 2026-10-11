"""Interim mover exit policy at the config/evaluator/receipt seams; synthetic only."""
from dataclasses import replace
from datetime import datetime
from decimal import Decimal as D
import itertools
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from tests.test_adaptive_paper_mover import (
    SOURCE, SCAN_TIME, config_data, load, mover, mover_runner, scan_bytes,
)
from safety import Position, Quote


class MoverExitChainTests(unittest.TestCase):
    def make_plan(self, data):
        _, limits, settings = load(data)
        scan = mover.load_scan(scan_bytes(), settings, now=SCAN_TIME + 20)
        session = mover.plan_session(None, equity=D(10000), rung_schedule=settings.rung_schedule)
        plan = mover.build_plan(settings, limits, scan, session, trial_id='exit-chain',
                                evidence_class='SYN', t0=SCAN_TIME + 25, equity=D(10000))
        return limits, settings, plan

    def test_trail_or_time_chain_uses_adaptive_priority_in_each_input_order(self):
        for chain in itertools.permutations(('X3', 'X2')):
            data = config_data()
            data['mover']['exit'] = list(chain)
            _, _, settings = load(data)
            timing = mover.Timing(1000, 1030, 60, 10, 99999, 99999, None, 3600)
            args = dict(entry_price=D(10), running_high=D(10), first_fill_at=1000, timing=timing)
            with self.subTest(chain=chain):
                self.assertIsNone(mover.rule_exit_reason(settings.exit_rule, now=4599, bid=D(9), **args))
                self.assertEqual(mover.rule_exit_reason(settings.exit_rule, now=4599, bid=D('8.5'), **args), 'x3_trail')
                self.assertEqual(mover.rule_exit_reason(settings.exit_rule, now=4600, bid=D(9), **args), 'x2_time')
                self.assertEqual(mover.rule_exit_reason(settings.exit_rule, now=4600, bid=D('8.5'), **args), 'x3_trail')
                self.assertEqual(mover.rule_exit_reason(settings.exit_rule, now=4600, bid=None, **args), 'x2_time')

    def test_exit_parameters_reach_timing_and_receipt(self):
        data = config_data()
        data['mover'].update(x2_hold_seconds=900, x3_trail_fraction='0.90',
                             x4_stop_fraction='0.90', x4_target_fraction='1.25')
        _, settings, plan = self.make_plan(data)
        self.assertEqual(settings.x2_hold_seconds, 900)
        self.assertEqual(settings.x3_trail_fraction, D('0.90'))
        self.assertEqual(settings.x4_stop_fraction, D('0.90'))
        self.assertEqual(settings.x4_target_fraction, D('1.25'))
        self.assertEqual(plan.timing.x2_hold_seconds, 900.0)
        self.assertEqual(mover_runner.plan_receipt(plan)['exit_parameters'], {
            'rule': 'X2', 'x1_flatten_at_et': '15:58', 'x2_hold_seconds': 900,
            'x3_trail_fraction': '0.90', 'x4_stop_fraction': '0.90', 'x4_target_fraction': '1.25',
        })

    def test_configured_trail_and_hold_reach_the_book_exit_events(self):
        for bid, offset, expected in [('3.60', 3, 'x3_trail'), ('4', 901, 'x2_time')]:
            with self.subTest(expected=expected):
                data = config_data()
                data['duration_seconds'] = 1800
                data['mover'].update(exit=['X3', 'X2'], x2_hold_seconds=900, x3_trail_fraction='0.90')
                limits, _, plan = self.make_plan(data)
                positions, quotes, events = {}, {}, []
                book = mover.MoverBook(plan, positions=lambda: positions.copy(), quote=quotes.get,
                                       limits=limits, trial_id='exit-chain', event_sink=events.append)
                t0 = plan.timing.trial_start
                quotes['ABCD'] = Quote('ABCD', '3.20', '3.21', t0)
                actions = book.evaluate(t0, entries_enabled=True)
                buy = next(a.record for a in actions if a.kind == 'submit' and a.record.side == 'buy')
                positions['ABCD'] = Position('ABCD', buy.qty, buy.qty * D('3.21'))
                book.on_fill(buy.client_id, t0 + 0.1, buy.qty, D('3.21'))
                quotes['ABCD'] = Quote('ABCD', '4', '4.01', t0 + 1)
                book.evaluate(t0 + 1, entries_enabled=False)
                quotes['ABCD'] = Quote('ABCD', bid, str(D(bid) + D('0.01')), t0 + offset)
                book.evaluate(t0 + offset, entries_enabled=False)
                triggered = [e['reason'] for e in events if e['type'] == 'mover_exit_triggered']
                self.assertEqual(triggered, [expected])

    def test_configured_x4_stop_and_target_are_used_by_the_evaluator(self):
        data = config_data()
        data['mover'].update(exit='X4', x4_stop_fraction='0.90', x4_target_fraction='1.25')
        _, _, plan = self.make_plan(data)
        args = dict(now=plan.timing.trial_start + 1, entry_price=D(10), running_high=D(10),
                    first_fill_at=plan.timing.trial_start, timing=plan.timing,
                    x3_trail_fraction=plan.x3_trail_fraction, x4_stop_fraction=plan.x4_stop_fraction,
                    x4_target_fraction=plan.x4_target_fraction)
        self.assertEqual(mover.rule_exit_reason(plan.exit_rule, bid=D('9.00'), **args), 'x4_stop')
        self.assertIsNone(mover.rule_exit_reason(plan.exit_rule, bid=D('9.01'), **args))
        self.assertEqual(mover.rule_exit_reason(plan.exit_rule, bid=D('12.50'), **args), 'x4_target')

    def test_explicit_defaults_reproduce_receipts_and_frozen_ledger_bytes(self):
        original = config_data()
        defaulted = config_data()
        defaulted['mover'].update(x2_hold_seconds=3600, x3_trail_fraction='0.850',
                                  x4_stop_fraction='0.850', x4_target_fraction='1.5')
        limits_a, _, plan_a = self.make_plan(original)
        limits_b, _, plan_b = self.make_plan(defaulted)
        self.assertEqual(limits_a.frozen_json().encode(), limits_b.frozen_json().encode())
        self.assertEqual(json.dumps(mover_runner.plan_receipt(plan_a), sort_keys=True),
                         json.dumps(mover_runner.plan_receipt(plan_b), sort_keys=True))
        receipt = json.loads((SOURCE / 'trials/rth-20260929/mover-paper-1.json').read_text())
        self.assertEqual(mover_runner.plan_receipt(plan_b)['exit_parameters'], receipt['exit_parameters'])
        args = dict(now=5000, bid=D('8.5'), entry_price=D(10), running_high=D(10),
                    first_fill_at=1000, timing=mover.Timing(1000, 1030, 60, 10, 99999, 99999, 4000, 3600))
        for rule in ('X1', 'X2', 'X3', 'X4'):
            self.assertEqual(mover.rule_exit_reason(rule, **args), mover.rule_exit_reason(rule, **args,
                            x3_trail_fraction=plan_b.x3_trail_fraction, x4_stop_fraction=plan_b.x4_stop_fraction,
                            x4_target_fraction=plan_b.x4_target_fraction))

    def test_all_chain_input_orders_preserve_force_stop_profit_trail_time_priority(self):
        timing = mover.Timing(1000, 1030, 60, 10, 99999, 99999, 4000, 3600)
        for chain in itertools.permutations(('X1', 'X2', 'X3', 'X4')):
            data = config_data()
            data['mover'].update(exit=list(chain), session_scope='any_session', trial_end_et='16:00')
            _, _, settings = load(data)
            args = dict(now=5000, bid=D(8), entry_price=D(10), running_high=D(10),
                        first_fill_at=1000, timing=timing)
            with self.subTest(chain=chain):
                self.assertEqual(mover.rule_exit_reason(settings.exit_rule, **args), 'x1_close')
                args['timing'] = replace(timing, x1_at=6000)
                self.assertEqual(mover.rule_exit_reason(settings.exit_rule, **args), 'x4_stop')
                args.update(bid=D(15), running_high=D(20))
                self.assertEqual(mover.rule_exit_reason(settings.exit_rule, **args), 'x4_target')
                args.update(bid=D(9), running_high=D(11))
                self.assertEqual(mover.rule_exit_reason(settings.exit_rule, **args), 'x3_trail')
                args.update(bid=D(10), running_high=D(10))
                self.assertEqual(mover.rule_exit_reason(settings.exit_rule, **args), 'x2_time')

    def test_invalid_chain_is_refused_after_a_valid_chain_is_accepted(self):
        data = config_data()
        data['mover']['exit'] = ['X3', 'X2']
        load(data)
        for invalid in ([], ['X2', 'X2'], ['X5'], [None], [True], [['X3']], 'X3,X2', None):
            with self.subTest(invalid=invalid):
                data['mover']['exit'] = invalid
                with self.assertRaisesRegex(ValueError, 'invalid_mover_setting:exit$'):
                    load(data)

    def test_registered_bounds_nonfinite_and_nonpositive_are_refused_not_clamped(self):
        bad = {
            'x2_hold_seconds': [0, -1, 899, 3601, 900.0, True, '900', float('nan'), float('inf')],
            'x3_trail_fraction': ['0', '-1', '0.7999', '0.9701', 'NaN', 'Infinity', '-Infinity', True, 0.85],
            'x4_stop_fraction': ['0', '-1', '1', '2', '0.8499', '0.9001', 'NaN', 'Infinity', '-Infinity', 'bad', None],
            'x4_target_fraction': ['0', '-1', '0.5', '1', '1.2499', '1.5001', 'NaN', 'Infinity', '-Infinity', 'bad', None],
        }
        for key, values in bad.items():
            for value in values:
                with self.subTest(key=key, value=value):
                    data = config_data()
                    data['mover'][key] = value
                    with self.assertRaisesRegex(ValueError, 'invalid_mover_setting:' + key + '$'):
                        load(data)

    def test_registered_grid_endpoints_are_accepted(self):
        endpoints = {'x2_hold_seconds': (900, 3600), 'x3_trail_fraction': ('0.80', '0.97'),
                     'x4_stop_fraction': ('0.85', '0.90'), 'x4_target_fraction': ('1.25', '1.50')}
        for key, values in endpoints.items():
            for value in values:
                with self.subTest(key=key, value=value):
                    data = config_data()
                    data['mover'][key] = value
                    _, _, settings = load(data)
                    self.assertEqual(getattr(settings, key), value if isinstance(value, int) else D(value))

    def test_nondefault_chain_receipt_records_effective_order_and_all_parameters(self):
        data = config_data()
        data['mover'].update(exit=['X2', 'X3', 'X4'], x2_hold_seconds=900,
                             x3_trail_fraction='0.97', x4_stop_fraction='0.90', x4_target_fraction='1.25')
        _, _, plan = self.make_plan(data)
        recorded = json.loads(json.dumps(mover_runner.plan_receipt(plan)))['exit_parameters']
        self.assertEqual(recorded, {'rule': ['X4', 'X3', 'X2'], 'x1_flatten_at_et': '15:58',
                                    'x2_hold_seconds': 900, 'x3_trail_fraction': '0.97',
                                    'x4_stop_fraction': '0.90', 'x4_target_fraction': '1.25'})
        # A consumer needs no hidden constants to reproduce the configured exit.
        timing = replace(plan.timing, x2_hold_seconds=recorded['x2_hold_seconds'])
        self.assertEqual(mover.rule_exit_reason(recorded['rule'], now=1000, bid=D(9),
                         entry_price=D(10), running_high=D(10), first_fill_at=0, timing=timing,
                         x3_trail_fraction=D(recorded['x3_trail_fraction']),
                         x4_stop_fraction=D(recorded['x4_stop_fraction']),
                         x4_target_fraction=D(recorded['x4_target_fraction'])), 'x4_stop')

    def test_retained_default_run_receipt_reemits_identical_bytes(self):
        data = config_data()
        data['mover'].update(x2_hold_seconds=3600, x3_trail_fraction='0.850',
                             x4_stop_fraction='0.850', x4_target_fraction='1.5')
        _, _, settings = load(data)
        path = SOURCE / 'trials/rth-20260929/mover-paper-1.json'
        original = path.read_bytes()
        receipt = json.loads(original)
        t, s, z = receipt['timing'], receipt['session'], receipt['sizing']
        def epoch(value):
            return None if value is None else datetime.fromisoformat(value).timestamp()
        timing = mover.Timing(epoch(t['trial_start']), epoch(t['entry_deadline']),
                              t['entry_timeout_seconds'], t['exit_order_timeout_seconds'],
                              epoch(t['hard_flatten_at']), epoch(t['sell_window_end']),
                              epoch(t['x1_flatten_at']), t['x2_hold_seconds'])
        session = SimpleNamespace(number=s['number'], rung=D(s['rung']), equity_peak_usd=D(s['equity_peak_usd']),
                                  drawdown_fraction=D(s['drawdown_fraction']), drawdown_factor=D(s['drawdown_factor']),
                                  paused=s['paused'], pause_sessions_remaining_after=s['pause_sessions_remaining_after'], reason=s['reason'])
        plan = SimpleNamespace(timing=timing, session=session, exit_rule=receipt['exit_rule'],
                               regime_factor=D(z['regime_factor']), regime_source=z['regime_source'],
                               leverage=D(z['leverage_L']), engine_leverage_multiple=D(z['engine_leverage_multiple']),
                               sizing_equity_usd=D(z['sizing_equity_usd']), gross_budget_usd=D(z['gross_budget_usd']),
                               appreciation_allowance=D(z['appreciation_allowance']), gross_guard_usd=D(z['gross_guard_usd']),
                               entry_cap_bps=D(z['entry_limit_cap_bps']), exit_cap_bps=D(z['exit_limit_cap_bps']),
                               max_entry_notional_usd=D(z['max_entry_notional_usd']),
                               ledger_max_order_notional_usd=D(z['ledger_max_order_notional_usd']),
                               x2_hold_seconds=settings.x2_hold_seconds, x3_trail_fraction=settings.x3_trail_fraction,
                               x4_stop_fraction=settings.x4_stop_fraction, x4_target_fraction=settings.x4_target_fraction)
        # Replay the changed receipt projection into the retained full run envelope;
        # orders/outcomes remain the original fixture, not a new broker run.
        receipt.update(mover_runner.plan_receipt(plan))
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / 'receipt.json'
            mover_runner.save(output, receipt)
            self.assertEqual(output.read_bytes(), original)

    def test_synthetic_chain_preserves_x1_clock_activation(self):
        data = config_data()
        data['mover'].update(exit=['X1', 'X3'], session_scope='any_session', trial_end_et='16:00')
        _, _, settings = load(data)
        timing = mover_runner.synthetic_timing(1000, hold_seconds=10, exit_rule=settings.exit_rule)
        self.assertEqual(timing.x1_at, 1010)

    def test_trail_high_is_still_seeded_from_fill_price(self):
        data = config_data()
        data['mover'].update(exit=['X3', 'X2'])
        limits, _, plan = self.make_plan(data)
        positions, quotes, events = {}, {}, []
        book = mover.MoverBook(plan, positions=lambda: positions.copy(), quote=quotes.get,
                               limits=limits, trial_id='exit-chain', event_sink=events.append)
        t0 = plan.timing.trial_start
        quotes['ABCD'] = Quote('ABCD', '3.20', '3.21', t0)
        buy = next(a.record for a in book.evaluate(t0, entries_enabled=True)
                   if a.kind == 'submit' and a.record.side == 'buy')
        positions['ABCD'] = Position('ABCD', buy.qty, buy.qty * D(4))
        book.on_fill(buy.client_id, t0 + 0.1, buy.qty, D(4))
        quotes['ABCD'] = Quote('ABCD', '3.40', '3.41', t0 + 1)
        book.evaluate(t0 + 1, entries_enabled=False)
        self.assertEqual([e['reason'] for e in events if e['type'] == 'mover_exit_triggered'], ['x3_trail'])

    @unittest.skipUnless(importlib.util.find_spec('nautilus_trader') and importlib.util.find_spec('alpaca'),
                         'optional native runtime')
    def test_native_chain_exits_on_trail_or_time_whichever_fires_first(self):
        from tests import test_adaptive_paper_mover_native as native
        for hold, expected in [(1.5, 'x2_time'), (6.0, 'x3_trail')]:
            with self.subTest(expected=expected):
                points = {'AAA': [(0, D(10), D('0.02')), (1, D(10), D('0.02')),
                                  (2, D(12), D('0.02')), (3.5, D('9.80'), D('0.02'))]}
                receipt, _, held, unresolved = native.MoverNativeEndToEnd.run_trial(
                    self, [native.row('AAA', 1, '10.00')], points,
                    exit_rule=['X3', 'X2'], hold=hold, flatten=8, window=12)
                self.assertTrue(receipt['flat'])
                self.assertEqual(held, {})
                self.assertEqual(unresolved, 0)
                legs = native.MoverNativeEndToEnd.legs(self, receipt)
                self.assertEqual(legs['AAA']['exit_reason'], expected)


if __name__ == '__main__':
    unittest.main()
