"""Synthetic D6-b envelopes; no broker, credential, GO or shared state calls."""
from dataclasses import replace
from decimal import Decimal as D
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / 'blueprints/us-equities/adaptive-paper'
sys.path.insert(0, str(SOURCE))
import runner
import mover
import safety


class ConfigurableCeilings(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir='/var/tmp')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.now = 1791903600.0  # synthetic 2026-10-13 11:00 ET
        self.stop = patch.object(safety, 'DEFAULT_STOP', self.root / 'STOP')
        self.stop.start()
        self.addCleanup(self.stop.stop)

    def load(self, raw, *, engine='adaptive'):
        path = self.root / 'config.json'
        path.write_text(json.dumps(raw))
        return (runner.load_config if engine == 'adaptive' else mover.load_mover_config)(path)

    def acct(self):
        raw = json.loads((SOURCE / 'config-leverage-4x.json').read_text())
        raw.update(capital_usd='119000', max_gross_exposure_usd='476000',
                   max_order_notional_usd='40000', max_order_quantity=1000,
                   risk_ceilings={'max_order_notional_usd': '40000', 'max_order_quantity': 1000})
        return raw

    def ledger(self, limits):
        ledger = safety.Ledger(self.root / 'ledger.sqlite3', limits)
        self.addCleanup(ledger.close)
        ledger.start_trial(self.now)
        return ledger

    def reserve(self, ledger, qty, price):
        quote = safety.Quote('SPY', price, price, self.now)
        return ledger.reserve_intent('entry', 'SPY', 'buy', str(qty), str(price),
                                     quote=quote, now=self.now, market_open=True,
                                     session_close=self.now + 3600, stop_file=self.root / 'STOP')

    def test_acct_40000_loads_and_ledger_enforces_exact_boundary(self):
        _, limits, policy = self.load(self.acct())
        self.assertEqual(policy.max_order_notional, 40000)
        self.assertEqual(policy.max_shares, 1000)
        ledger = self.ledger(limits)
        with self.assertRaisesRegex(safety.SafetyError, 'order_size_cap_exceeded'):
            self.reserve(ledger, 1, 40001)
        self.assertEqual(ledger.intents(), [])
        self.assertTrue(self.reserve(ledger, 1000, 40).newly_reserved)
        self.assertEqual(ledger.accounting().pending_buy_notional_usd, D('40000'))

    def test_default_10000_notional_boundary_is_unchanged(self):
        limits = safety.RiskLimits(capital_usd='20000', max_gross_exposure_usd='20000',
                                   max_order_notional_usd='10000', max_order_qty=100)
        with self.assertRaisesRegex(safety.SafetyError, 'risk_limit_out_of_bounds'):
            replace(limits, max_order_notional_usd=D('10001'))
        ledger = self.ledger(limits)
        with self.assertRaisesRegex(safety.SafetyError, 'order_size_cap_exceeded'):
            self.reserve(ledger, 1, 10001)
        self.assertTrue(self.reserve(ledger, 100, 100).newly_reserved)

    def test_control_config_and_frozen_ledger_bytes_are_unchanged(self):
        # Captured at base 24a209016178, before any production edit.
        snapshots = {
            'config.json': ('2b555982034af02b9d0d2e1d20e17d22c1e83f2b0c4d60b61d91307ebec63562',
                            '49537b38ebc2f60b784462f8e4fc20cae1aed3fe71d9ee9338c99bebcc133096'),
            'config-sip.json': ('3587653104e68fdfc9bbb9170825c611abcf7e2e1be1004327a056031c34555a',
                                '49537b38ebc2f60b784462f8e4fc20cae1aed3fe71d9ee9338c99bebcc133096'),
            'config-leverage-1x.json': ('2138f6f7ec12be4969c2309f808d5333bc050becf8ad33b343485f3d817b2218',
                                      '28865bb4052c14b543d2a842237b42a5bbcdc7cb8fa8c45eec20c8dc1dbdf080'),
            'config-leverage-2x.json': ('f46309303cd997a1892a1a26c8531bda24c312c50e658cfc7ebac7cb2760fca3',
                                      '9f76e01b290636e72f2d795ba572db35536e102fa8b520b4d48971b529971938'),
            'config-leverage-4x.json': ('4cd2bbf11ccd7af4db62c2786b0d02390ae55afa44a75e774f5649e8997e5e04',
                                      '980f178ffbc13a49b9fcb71b9efa014aaf36d03d49cf0463cc6462be51794c0d'),
        }
        for name, (config_hash, limits_hash) in snapshots.items():
            with self.subTest(config=name):
                path = SOURCE / name
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), config_hash)
                _, limits, _ = runner.load_config(path)
                self.assertEqual(hashlib.sha256(limits.frozen_json().encode()).hexdigest(), limits_hash)
        default = safety.RiskLimits()
        for values in ({'capital_usd': '1000001'}, {'max_order_qty': 101}):
            with self.assertRaisesRegex(safety.SafetyError, 'risk_limit_out_of_bounds'):
                replace(default, **values)

    def test_quantity_ceiling_changes_fixed_and_notional_caps(self):
        raw = self.acct()
        raw['risk_ceilings']['max_order_quantity'] = 200
        raw['max_order_quantity'] = 200
        for mode in ('fixed', 'notional'):
            with self.subTest(mode=mode):
                raw['max_order_qty_mode'] = mode
                _, limits, policy = self.load(raw)
                self.assertEqual(limits.effective_max_order_qty('100'), 200)
                self.assertEqual(limits.effective_max_order_qty('100', quote_price='400'),
                                 100 if mode == 'notional' else 200)
                self.assertEqual(policy.max_shares, 200)
        raw['max_order_quantity'] = 201
        with self.assertRaisesRegex(safety.SafetyError, 'risk_limit_out_of_bounds'):
            self.load(raw)

    def test_capital_ceiling_is_explicit_and_bounded(self):
        raw = self.acct()
        raw.update(capital_usd='2000000', max_gross_exposure_usd='4000000')
        raw['risk_ceilings']['capital_usd'] = '2000000'
        _, limits, _ = self.load(raw)
        self.assertEqual(limits.capital_usd, D('2000000'))
        raw['capital_usd'] = '2000001'
        with self.assertRaisesRegex(safety.SafetyError, 'risk_limit_out_of_bounds'):
            self.load(raw)

    def test_invalid_ceiling_objects_and_values_are_refused(self):
        bad = [None, [], '40000', {'typo': '40000'},
               *({'max_order_notional_usd': v} for v in [0, -1, True, 40000.0, 'NaN', 'Infinity', '1000000001']),
               *({'max_order_quantity': v} for v in [0, -1, True, 100.5, '100', 1000000001]),
               *({'capital_usd': v} for v in [0, -1, True, 'NaN'])]
        for value in bad:
            with self.subTest(value=value):
                raw = json.loads((SOURCE / 'config.json').read_text())
                raw['risk_ceilings'] = value
                with self.assertRaises((ValueError, safety.SafetyError)):
                    self.load(raw)

    def test_empty_or_dollar_only_override_keeps_baseline_policy_10_shares(self):
        for block in ({}, {'max_order_notional_usd': '40000'}):
            raw = json.loads((SOURCE / 'config.json').read_text())
            raw.update(risk_ceilings=block, max_order_quantity=11)
            with self.assertRaisesRegex(ValueError, 'invalid_policy_bounds'):
                self.load(raw)
        raw['risk_ceilings']['max_order_quantity'] = 20
        _, limits, policy = self.load(raw)
        self.assertEqual(policy.max_shares, 11)
        self.assertEqual(limits.max_order_qty, 11)

    def test_explicit_ceilings_are_frozen_and_reopen_requires_same_values(self):
        _, limits, _ = self.load(self.acct())
        ledger = self.ledger(limits)
        frozen = ledger._get('limits')
        ledger.close()
        reopened = safety.Ledger(self.root / 'ledger.sqlite3', limits)
        self.addCleanup(reopened.close)
        self.assertEqual(reopened._get('limits'), frozen)
        with self.assertRaisesRegex(safety.SafetyError, 'persisted_risk_limits_differ'):
            safety.Ledger(self.root / 'ledger.sqlite3',
                          replace(limits, order_notional_ceiling_usd=D('50000')))
        # Lane-B rotation reconstructs its OLD frozen envelope before registering
        # the next one; this must retain the old explicit ceilings too.
        bpath = self.root / 'lane-b.sqlite3'
        old = safety.Ledger(bpath, limits, exploratory=True)
        old.close()
        rotated = safety.Ledger(bpath, replace(limits, order_notional_ceiling_usd=D('50000')),
                               exploratory=True, rotation=True)
        self.addCleanup(rotated.close)
        self.assertEqual(rotated.limits.frozen_json(), frozen)

    def test_mover_loader_accepts_explicit_shared_ceilings(self):
        raw = json.loads((SOURCE / 'config-mover.json').read_text())
        raw.update(capital_usd='119000', max_gross_exposure_usd='119000',
                   max_order_notional_usd='40000', max_order_quantity=1000,
                   risk_ceilings={'max_order_notional_usd': '40000', 'max_order_quantity': 1000})
        raw['mover']['max_entry_notional_usd'] = '4000'  # unchanged 10x exit headroom
        _, limits, settings = self.load(raw, engine='mover')
        self.assertEqual(limits.max_order_notional_usd, D('40000'))
        self.assertEqual(settings.max_entry_notional_usd, D('4000'))
        self.assertEqual(limits.effective_max_order_qty('40'), 1000)


if __name__ == '__main__':
    unittest.main()
