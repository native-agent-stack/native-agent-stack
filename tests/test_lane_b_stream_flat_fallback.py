"""Persistent stream refusal uses the actual GET observer on SYN HTTP answers."""
from contextlib import ExitStack, contextmanager
import asyncio
import importlib.util
import io
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from tests import test_pre_skip_flat_probe as observer_fixtures
from tests import test_lane_b_r3_launcher as launcher_fixtures

ROOT = Path(__file__).resolve().parents[1]
LATCH = ROOT / 'blueprints/us-equities/paper-readiness-seq3'
STREAM_ERROR = 'stream authentication/subscription/quote readiness failed (quotes_disconnected,start_not_ready)'


class StreamFlatFallback(unittest.TestCase):
    @contextmanager
    def scenario(self, *, error=STREAM_ERROR, preflight_positions=0, preflight_orders=0, preflight_submissions=0):
        with ExitStack() as stack:
            fixture = observer_fixtures.FlatProbe()
            fixture.setUp()
            stack.callback(fixture.doCleanups)
            stack.enter_context(patch.object(sys, 'path', [str(LATCH), *sys.path]))
            spec = importlib.util.spec_from_file_location('stream_flat_builder',
                ROOT / 'blueprints/us-equities/paper-lane-latch/recut.py')
            builder = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(builder)
            launch_file = fixture.bundle / 'launch.py'
            launch_file.write_text(builder.isolate_launch(launch_file.read_text(), '1' * 64))
            launch = observer_fixtures.load('stream_flat_launch', launch_file)
            fixture.launch = launch
            launch.STATE = fixture.state
            launch.HOST_STOP = fixture.root / 'operator-STOP'
            launch.STOP = fixture.root / 'lane-STOP'
            launch.verify_bundle = Mock()
            launch.verify_runtime = Mock()
            launch.keyed = Mock(side_effect=fixture.execute)
            instance = fixture.state / 'instances/syn-persistent-stream'
            instance.mkdir(parents=True)
            active = {'stage': 'pre', 'trial': 'syn-persistent-stream', 'session_date': '2026-10-14',
                      'config_sha256': launch.sha(launch.config('pre')),
                      'bundle_sha256': launch.sha(fixture.bundle / 'SHA256SUMS'),
                      'go_sha256': '2' * 64, 'instance': str(instance),
                      'state_root': str(instance / 'native-state')}
            launch.save(fixture.state / 'active/pre.json', active)
            launch.stop_mark('pre')
            native = instance / 'recover.json'
            launch.save(native, {'mode': 'official_sdk_recovery', 'status': 'needs_attention', 'flat': False,
                'preflight': {'position_count': preflight_positions, 'open_order_count': preflight_orders,
                              'orders_submitted': preflight_submissions},
                'positions': [], 'unresolved_orders': [], 'broker_positions_last_observed': None,
                'reconciliation': None, 'errors': ['TransportError'],
                'error_details': [{'code': 'TransportError', 'type': 'TransportError', 'message': error}],
                'cancel_attempt_client_ids': [], 'exit_attempt_client_ids': [], 'buy_submissions': 0})
            launch.native_recover = Mock(return_value=(3, native))
            yield fixture, launch, instance, native

    def test_persistent_stream_error_zero_preflight_rest_flat_records_flat(self):
        with self.scenario() as (fixture, launch, instance, native):
            original = native.read_bytes()
            self.assertEqual(launch.recover_stage('pre'), 0)
            launch.native_recover.assert_called_once()  # No native retry or stream reconnection.
            launch.keyed.assert_called_once()
            self.assertIn(('GET', '/positions'), fixture.calls)
            self.assertIn(('GET', '/orders'), fixture.calls)
            handoff = launch.safe_json(instance / 'handoff.json')
            self.assertTrue(handoff['flat'])
            self.assertEqual((handoff['positions'], handoff['open_orders'], handoff['recover_rc']), (0, 0, 0))
            self.assertEqual(native.read_bytes(), original)
            self.assertFalse((fixture.state / 'active/pre.json').exists())
            self.assertEqual(launch.HOST_STOP.read_bytes(), fixture.stop_bytes)

    def test_stream_error_rest_not_flat_or_failing_refuses(self):
        for variant in ('position', 'order', 'http-failure'):
            with self.subTest(variant=variant), self.scenario() as (fixture, launch, instance, native):
                if variant == 'position':
                    fixture.positions = [{'symbol': 'SPY', 'qty': '1', 'side': 'long', 'market_value': '100'}]
                elif variant == 'order':
                    fixture.orders = [{'id': 'SYN order', 'symbol': 'SPY', 'status': 'new'}]
                else:
                    answer = fixture.answer
                    def fail_positions(path):
                        if path == '/positions':
                            raise ConnectionError('SYN final REST read unavailable')
                        return answer(path)
                    fixture.answer = fail_positions
                with self.assertRaisesRegex(launch.Refused, 'recovery_not_flat'):
                    launch.recover_stage('pre')
                launch.keyed.assert_called_once()
                self.assertIn(('GET', '/positions'), fixture.calls)
                handoff = launch.safe_json(instance / 'handoff.json')
                self.assertFalse(handoff['flat'])
                if variant == 'http-failure':
                    self.assertEqual(handoff['recover_rc'], 3)
                    self.assertIsNone(handoff['positions'])
                self.assertTrue((fixture.state / 'active/pre.json').exists())
                self.assertEqual(launch.HOST_STOP.read_bytes(), fixture.stop_bytes)

    def test_flat_stage_with_no_traded_symbols_recovers_through_rest(self):
        with self.scenario() as (fixture, launch, instance, native):
            recovery = observer_fixtures.load('empty_symbol_recovery', fixture.paper / 'recovery.py')
            class EmptyPort:
                def adopt_intents(port, intents):
                    self.assertEqual(intents, [])
                async def start(port, quote, order):
                    raise fixture.transport.TransportError(STREAM_ERROR)
                async def stop(port):
                    pass
            ledger = SimpleNamespace(limits=SimpleNamespace(cleanup_seconds=1), intents=lambda: [],
                                     positions=lambda: {}, unresolved=lambda: [], begin_recovery=lambda now: None)
            controller = SimpleNamespace(ledger=ledger, port=EmptyPort(), stop=False, clock=lambda: 0)
            result = asyncio.run(recovery.recover(controller, {'trial_id': 'syn-empty', 'baseline_cash': 0},
                {'cleanup_seconds': 1, 'order_timeout_seconds': 0.01,
                 'regular_session_only': True, 'extended_hours_enabled': False},
                reconcile_fn=lambda *args: self.fail('no stream snapshot')))
            result['preflight'] = {'position_count': 0, 'open_order_count': 0, 'orders_submitted': 0}
            launch.save(native, result)
            self.assertFalse(result['flat'])
            self.assertEqual(result['positions'], [])
            self.assertEqual(result['unresolved_orders'], [])
            self.assertEqual(launch.recover_stage('pre'), 0)
            self.assertTrue(launch.safe_json(instance / 'handoff.json')['flat'])
            self.assertIn(('GET', '/positions'), fixture.calls)
            self.assertIn(('GET', '/orders'), fixture.calls)

    def test_nonstream_or_nonzero_preflight_refuses_without_rest(self):
        for kwargs in ({'error': 'snapshot incomplete; admissions remain frozen'},
                       {'error': 'stream authentication/subscription/quote readiness failed (queue_overflow,start_not_ready)'},
                       {'preflight_positions': 1}, {'preflight_orders': 1},
                       {'preflight_submissions': 1}, {'preflight_positions': False}):
            with self.subTest(kwargs=kwargs), self.scenario(**kwargs) as (fixture, launch, instance, native):
                with self.assertRaisesRegex(launch.Refused, 'recovery_not_flat'):
                    launch.recover_stage('pre')
                launch.keyed.assert_not_called()
                self.assertEqual(fixture.calls, [])
                self.assertFalse(launch.safe_json(instance / 'handoff.json')['flat'])
                self.assertTrue((fixture.state / 'active/pre.json').exists())


class EmptyScanOutcome(unittest.TestCase):
    def test_empty_scan_returns_zero_and_records_info_no_trade_counts(self):
        fixture = launcher_fixtures.Acceptance()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        launch, instance = fixture.launch, fixture.instance
        config = fixture.root / 'configs/pre.json'
        config.parent.mkdir()
        config.write_text('{}\n')
        scan = instance / 'scan.json'
        launch.save(scan, {'symbols': []})
        fixture.value['config_sha256'] = launch.sha(config)
        def no_trade(command, **kwargs):
            output = instance / 'paper.json'
            launch.save(output, {'kind': 'mover_trial_receipt', 'status': 'not_started',
                'reason': 'scan_empty', 'stage': 'validation', 'orders_submitted': 0,
                'config_sha256': launch.sha(config), 'scan_sha256': launch.sha(scan)})
            return 2  # The immutable native runner's documented no-start return.
        launch.keyed = no_trade
        stdout = io.StringIO()
        with patch('sys.stdout', stdout):
            self.assertEqual(launch.run_stage('pre'), 0)
        event = launch.safe_json(instance / 'no-trade.json')
        self.assertEqual((event['level'], event['event'], event['reason']), ('INFO', 'no_trade', 'scan_empty'))
        self.assertEqual(event['evaluated_counts'], {'selected_symbols': 0, 'orders_submitted': 0})
        self.assertIs(event['trial_evidence'], False)
        self.assertIn('INFO', stdout.getvalue())
        self.assertNotIn('refused', stdout.getvalue())
        self.assertFalse((launch.STATE / 'completed').exists())


if __name__ == '__main__':
    unittest.main()
