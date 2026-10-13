"""Default-off rate probes and fail-closed unavailable place-only admission."""
from pathlib import Path
import sys
import tempfile
import unittest
import json
import contextlib
import io
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'blueprints/us-equities/order-throughput'))
import capacity as c
import capacity_fixture as fx
import alpaca_capacity_port as native
import transport
import runner


class ProbeModeTests(unittest.TestCase):
    def run_mode(self, *, place=False, probe=False, broker=None, clock=None, **changes):
        clock = clock or fx.FakeClock()
        broker = broker or fx.FakeBroker(clock, bid='10.00', ask='10.02')
        config = c.CapacityConfig(**dict({'max_duration_seconds': 70, 'required_windows': 1,
            'max_orders': 350, 'max_open_orders': 100, 'max_open_notional_usd': '10000',
            'place_only': place, 'probe_limit': probe}, **changes))
        with tempfile.TemporaryDirectory(dir='/var/tmp') as temp:
            run = c.CapacityRun(broker, config, clock=clock, executor=c.InlineExecutor(),
                                stop_file=Path(temp) / 'STOP')
            return run.run(), run, broker

    def test_place_only_is_refused_before_order_or_bulk_admission(self):
        receipt, _, broker = self.run_mode(place=True)
        self.assertEqual(receipt['status'], 'refused')
        self.assertEqual(receipt['refusal_reason'], 'place_only_requires_qualified_flat_recovery')
        self.assertEqual(broker.submit_count, 0)
        self.assertEqual(broker.cancel_all_calls, 0)
        self.assertFalse(receipt['acceptance']['passed'])

    def test_probe_limit_hits_first_429_then_restores_safe_cleanup(self):
        receipt, run, _ = self.run_mode(probe=True, configured_cap_per_minute=250)
        self.assertEqual(receipt['stop_reason'], 'probe_first_http_429')
        self.assertEqual(receipt['probe_modes']['first_429']['status'], 429)
        self.assertEqual(receipt['probe_modes']['first_429']['headers']['x-ratelimit-limit'], '200')
        self.assertIn('x-ratelimit-reset', receipt['probe_modes']['first_429']['headers'])
        self.assertTrue(receipt['cleanup']['verified_zero_open'])
        self.assertEqual(receipt['rate']['budget_per_minute'], 180)
        self.assertFalse(receipt['acceptance']['passed'])
        self.assertFalse(any(a['t'] > receipt['probe_modes']['first_429']['at_monotonic']
                             and a['kind'] == 'submit' for a in run.actions))

    def test_bulk_capability_is_not_exposed_by_the_native_port(self):
        with mock.patch.object(transport, 'data_feed', return_value='iex'):
            port = native.AlpacaCapacityPort('fixture', 'fixture', 'SPY')
            self.assertFalse(port.supports_cancel_all)
            with self.assertRaises(transport.TransportError): port.cancel_all()
            with self.assertRaises(transport.TransportError):
                native.AlpacaCapacityPort('fixture', 'fixture', 'SPY', place_only=True)

    def test_native_sdk_cancel_all_is_denied_before_http_send(self):
        try:
            import requests
            from alpaca.trading.requests import LimitOrderRequest  # noqa: F401
        except ImportError:
            self.skipTest('requires isolated reviewed alpaca-py runtime')
        client = transport._sdk_client('fixture', 'fixture', lambda *a, **k: None)
        with mock.patch.object(requests.Session, 'request') as wire:
            with self.assertRaises(transport.TransportError): client.cancel_orders()
            wire.assert_not_called()
        client._session.close()

    def test_place_only_cannot_bypass_refusal_with_probe_limit(self):
        receipt, _, broker = self.run_mode(place=True, probe=True, configured_cap_per_minute=250)
        self.assertEqual(receipt['status'], 'refused')
        self.assertEqual(broker.submit_count, 0)
        self.assertIsNone(receipt['probe_modes']['first_429'])

    def test_foreign_order_is_retained_without_any_request(self):
        clock = fx.FakeClock()
        broker = fx.FakeBroker(clock, bid='10', ask='10.02', foreign_open_orders=1)
        before = json.dumps(broker.orders, sort_keys=True)
        receipt, _, _ = self.run_mode(place=True, broker=broker, clock=clock)
        self.assertEqual(receipt['status'], 'refused')
        self.assertEqual(json.dumps(broker.orders, sort_keys=True), before)

    def test_default_modes_and_ordinary_governor_remain_disabled(self):
        args = c.build_parser().parse_args(['offline', '--output', '/fixture/receipt.json'])
        config = c.config_from_args(args)
        self.assertFalse(config.place_only); self.assertFalse(config.probe_limit)
        self.assertNotIn('place_only', config.public()); self.assertNotIn('probe_limit', config.public())
        receipt, _, broker = self.run_mode()
        self.assertEqual(broker.cancel_all_calls, 0)
        self.assertGreater(receipt['orders']['cancel_requests'], 0)
        self.assertEqual(receipt['rate']['budget_per_minute'], 180)
        self.assertNotIn('probe_modes', receipt)

    def test_bad_probe_mode_configuration_is_refused_before_any_order(self):
        for fields in ({'max_duration_seconds': 120}, {'configured_cap_per_minute': 251}, {'qty': 2}):
            with self.subTest(fields=fields):
                with self.assertRaises(c.HarnessRefusal):
                    c.CapacityConfig(**dict({'probe_limit': True, 'max_duration_seconds': 70}, **fields)).validate()

    def test_flagged_journal_retains_latency_samples_and_recovery_still_parses(self):
        clock = fx.FakeClock(); broker = fx.FakeBroker(clock, bid='10', ask='10.02')
        with tempfile.TemporaryDirectory(dir='/var/tmp') as temp:
            cfg = c.CapacityConfig(probe_limit=True, max_duration_seconds=10, required_windows=1)
            journal = Path(temp) / 'run.journal.jsonl'
            run = c.CapacityRun(broker, cfg, clock=clock, executor=c.InlineExecutor(),
                               stop_file=Path(temp) / 'STOP', journal_path=journal)
            receipt = run.run()
            rows = [json.loads(line) for line in journal.read_text().splitlines()]
            samples = [r['submit_rest_ack_ms'] for r in rows
                       if r['type'] == 'probe_latency' and r['submit_rest_ack_ms'] is not None]
            self.assertEqual(round(c.percentile(samples, 90), 3), receipt['latency']['submit_rest_ack']['p90_ms'])
            self.assertEqual(len(c.read_journal(journal)['intents']), len(run.probes))
            self.assertTrue(c.read_journal(journal)['end']['verified_zero_open'])
            self.assertTrue(all('id' not in r for r in rows if r['type'] == 'probe_latency'))

    def test_recovery_cli_cannot_enable_probe_admission_with_otherwise_valid_arguments(self):
        for command in ('recover', 'audit'):
            for flag in ('--place-only', '--probe-limit'):
                with self.subTest(command=command, flag=flag):
                    with mock.patch.object(runner, 'credentials', side_effect=AssertionError('loader called')) as loader:
                        with contextlib.redirect_stderr(io.StringIO()) as errors, self.assertRaises(SystemExit) as caught:
                            c.main([command, '--output', '/fixture/output.json', '--env-file',
                                    '/fixture/never-read.env', '--journal', '/fixture/journal.jsonl', flag])
                    self.assertEqual(caught.exception.code, 2)
                    self.assertIn('exploratory flags are only for paper/offline rungs', errors.getvalue())
                    loader.assert_not_called()

    def test_bulk_delete_is_denied_on_paper_readonly_and_data_sessions(self):
        try:
            import requests
        except ImportError:
            self.skipTest('requires Requests in the isolated reviewed alpaca-py runtime')
        for origin, readonly in ((transport.PAPER_URL, False), (transport.PAPER_URL, True),
                                 (transport.DATA_URL, False)):
            with self.subTest(origin=origin, readonly=readonly):
                session = transport.GuardedSession(origin=origin, read_only=readonly,
                                                    before_request=lambda *a, **k: None)
                with mock.patch.object(requests.Session, 'request') as wire:
                    with self.assertRaises(transport.TransportError):
                        session.request('DELETE', origin + '/v2/orders')
                    wire.assert_not_called()
                session.close()

    def test_experimental_flags_require_exact_boolean_types(self):
        import rate_governor
        for value in (1, 0, 'yes', None):
            with self.subTest(value=value):
                with self.assertRaises(c.HarnessRefusal): c.CapacityConfig(probe_limit=value).validate()
                with self.assertRaises(c.HarnessRefusal): c.CapacityConfig(place_only=value).validate()
                with self.assertRaises(rate_governor.GovernorError):
                    rate_governor.RateGovernor(200, probe_limit=value)
                with self.assertRaises(transport.TransportError):
                    native.AlpacaCapacityPort('fixture', 'fixture', 'SPY', place_only=value)

    def test_existing_governor_is_unclamped_only_for_flagged_measurement(self):
        import rate_governor
        clock = fx.FakeClock()
        for flag, budget in ((False, 180), (True, 250)):
            governor = rate_governor.RateGovernor(250, clock=clock.monotonic, wall=clock.time, probe_limit=flag)
            governor.observe_limit(200)
            self.assertEqual(governor.budget, budget)


if __name__ == '__main__': unittest.main()
