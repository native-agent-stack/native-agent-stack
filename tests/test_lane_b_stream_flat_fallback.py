"""Persistent stream refusal uses the actual GET observer on SYN HTTP answers."""
from contextlib import ExitStack, contextmanager, nullcontext
import asyncio
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import time
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from tests import test_pre_skip_flat_probe as observer_fixtures

ROOT = Path(__file__).resolve().parents[1]
LATCH = ROOT / 'blueprints/us-equities/paper-readiness-seq3'
STREAM_ERROR = 'stream authentication/subscription/quote readiness failed (quotes_disconnected,start_not_ready)'


def actual_rth_cli_receipt(fixture, output, *, passed=False, stage='lev1'):
    """Run the real recover parser/config/summary/projection/save path.

    Only account/credential/network/engine boundaries are fixtures. In
    particular, do not fabricate or postprocess the public mode decoration.
    """
    runner = observer_fixtures.load('runner', fixture.paper / 'runner.py')
    recovery = observer_fixtures.load('recovery', fixture.paper / 'recovery.py')
    safety = sys.modules['safety']
    config_path = fixture.bundle / 'configs' / (stage + '.json')
    config_doc = json.loads((fixture.paper / 'config.json').read_text())
    config_path.write_text(json.dumps(config_doc))
    config, limits, _ = runner.load_config(config_path)
    fingerprint = 'syn-cli-account'
    state_root = output.parent / 'native-state'
    state_dir = state_root / fingerprint / 'adaptive'
    state_dir.mkdir(parents=True)
    ledger = safety.Ledger(state_dir / 'ledger.sqlite3', limits)
    ledger.close()
    config_sha = runner.config_digest(config, config_path.read_bytes(), limits=limits)
    runner.save(state_dir / 'trial.json', {
        'trial_id': 'syn-cli-trial', 'phase': 'running', 'status': 'running',
        'started_at': time.time() - 1, 'baseline_cash': '100000', 'config_sha256': config_sha})
    observation = {
        'account': {'status': 'ACTIVE', 'currency': 'USD', 'cash': '100000', 'equity': '100000',
                    'buying_power': '100000', 'trading_blocked': False, 'account_blocked': False,
                    'trade_suspended_by_user': False},
        'account_identity_sha256': fingerprint,
        'clock': {'is_open': True, 'received_at_ns': time.time_ns(), 'timestamp_ns': time.time_ns(),
                  'next_close_ns': time.time_ns() + 3600 * 10**9},
        'positions': [], 'orders': [], 'open_orders_complete': True,
        'assets': [{'symbol': symbol, 'status': 'active', 'tradable': True} for symbol in config['symbols']],
        'quotes': [{'symbol': symbol, 'ts_ns': time.time_ns()} for symbol in config['symbols']], 'quote_errors': {}}
    answer = fixture.answer
    def complete_quote_fixture(path):
        if path == '/stocks/quotes/latest':
            return {symbol: {'bp': '100', 'ap': '101', 'bs': 10, 'as': 10, 't': '2026-10-14T14:00:00Z'}
                    for symbol in config['symbols']}
        return answer(path)
    fixture.answer = complete_quote_fixture
    inner = {'mode': 'official_sdk_recovery', 'status': 'passed' if passed else 'needs_attention',
             'flat': passed, 'positions': [], 'unresolved_orders': [],
             'broker_positions_last_observed': [] if passed else None,
             'reconciliation': {'positions': 0, 'open_orders': 0} if passed else None,
             'errors': [] if passed else ['TransportError'],
             'error_details': [] if passed else [{'code': 'TransportError', 'type': 'TransportError',
                                                 'message': STREAM_ERROR}],
             'cancel_attempt_client_ids': [], 'exit_attempt_client_ids': [], 'buy_submissions': 0}
    argv = ['runner.py', 'recover', '--credentials', 'keychain-env', '--config', str(config_path),
            '--output', str(output), '--state-root', str(state_root)]
    with ExitStack() as stack:
        for obj, name, value in [
                (runner, 'paper_credentials', lambda *_: (None, None)),
                (runner, 'check_order_contract_boundary', lambda *_: {}),
                (runner, 'preflight', lambda *_, **__: observation),
                (runner, 'validate_preflight', lambda *_, **__: time.time() + 3600),
                (runner, 'account_lock_fingerprint', lambda *_: nullcontext()),
                (runner, 'AlpacaPaperTransport', Mock()),
                (runner, 'DEFAULT_STOP', fixture.root / 'SYN-STOP'),
                (safety, 'DEFAULT_STOP', fixture.root / 'SYN-STOP'),
                (recovery, 'recover', AsyncMock(return_value=inner)),
                (runner.signal, 'signal', Mock())]:
            stack.enter_context(patch.object(obj, name, value))
        stack.enter_context(patch.object(sys, 'argv', argv))
        stack.enter_context(patch('sys.stdout', io.StringIO()))
        rc = runner.main()
    return rc, json.loads(output.read_text())


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
    def native_empty_scan(self, exploratory, *, tamper=None):
        with StreamFlatFallback().scenario() as (fixture, launch, instance, native):
            mover = observer_fixtures.load('mover_runner', fixture.paper / 'mover_runner.py')
            config = launch.config('pre')
            document = json.loads((fixture.paper / 'config-mover.json').read_text())
            if exploratory:
                document.update(paper_lane='B', evidence_class='exploratory')
            config.write_text(json.dumps(document))
            instance = fixture.root / 'exploratory' / 'syn-empty-scan'
            instance.mkdir(parents=True)
            args = SimpleNamespace(trial='syn-empty-scan', config=config, scan=instance / 'scan.json',
                state_root=instance / 'native-state', output=instance / 'paper.json',
                live_dir=None, gate_result=None, snapshot=None)
            launch.save(args.scan, {'schema_version': 1, 'kind': 'mover_scan',
                'protocol': document['protocol'], 'rule': document['mover']['rule'],
                'scan_time': '2026-10-14T12:00:00Z', 'symbols': []})
            launch.binding = Mock(return_value={'instance': str(instance), 'trial': args.trial,
                'state_root': str(args.state_root), 'config_sha256': launch.sha(config)})
            (fixture.state / 'active/pre.json').unlink()  # No active SYN trial at admission.
            def empty_scan(command, **kwargs):
                # Real config/path/scan validation, effective digest and no-start
                # serializer, before any native credential or broker boundary.
                with patch.object(mover.time, 'time', return_value=1791979200), \
                     patch.object(sys.modules['safety'], 'DEFAULT_STOP', fixture.root / 'absent-STOP'), \
                     patch.object(mover, 'credentials', side_effect=AssertionError('credential boundary')):
                    rc = mover.command_paper(args)
                if tamper == 'raw-config-digest':
                    receipt = launch.safe_json(args.output)
                    receipt['config_sha256'] = launch.sha(config)
                    launch.save(args.output, receipt)
                elif tamper == 'scan':
                    args.scan.write_text('{"symbols": []}\n')
                return rc
            launch.keyed = Mock(side_effect=empty_scan)
            with patch('sys.stdout', io.StringIO()):
                if tamper:
                    reason = ('empty_scan_config_digest_mismatch' if tamper == 'raw-config-digest'
                              else 'empty_scan_receipt_binding_mismatch')
                    with self.assertRaisesRegex(launch.Refused, reason):
                        launch.run_stage('pre')
                    self.assertFalse((instance / 'no-trade.json').exists())
                    return
                self.assertEqual(launch.run_stage('pre'), 0)
            receipt = launch.safe_json(args.output)
            if exploratory:
                self.assertNotEqual(receipt['config_sha256'], launch.sha(config))
            else:
                self.assertEqual(receipt['config_sha256'], launch.sha(config))
            event = launch.safe_json(instance / 'no-trade.json')
            self.assertEqual((event['level'], event['reason']), ('INFO', 'scan_empty'))
            self.assertIs(event['trial_evidence'], False)
            self.assertEqual(event['native_exit_code'], 2)
            self.assertEqual(event['evaluated_counts'], {'selected_symbols': 0, 'orders_submitted': 0})
            self.assertFalse((fixture.state / 'completed').exists())

    def test_native_exploratory_empty_scan_returns_info_without_trial_evidence(self):
        self.native_empty_scan(True)

    def test_empty_scan_returns_zero_and_records_info_no_trade_counts(self):
        self.native_empty_scan(False)

    def test_exploratory_raw_digest_or_changed_scan_cannot_claim_clean_no_trade(self):
        for tamper in ('raw-config-digest', 'scan'):
            with self.subTest(tamper=tamper):
                self.native_empty_scan(True, tamper=tamper)


class NativeCLIRewriteContract(unittest.TestCase):
    def test_next_stage_regression_can_run_on_python_313_review_host(self):
        # The host-interpreter admission rule has its own native tests. This
        # scratch issuer regression must traverse proof admission on 3.13 too.
        with patch.object(sys, 'path', [str(LATCH), *sys.path]):
            import lane_latch
        review_host = SimpleNamespace(implementation=SimpleNamespace(name='cpython'), version_info=(3, 13))
        with patch.object(lane_latch, 'sys', review_host):
            self.test_actual_rth_cli_fallback_proof_admits_next_stage_and_rejects_tampering()

    def test_partial_nonmatching_stream_proof_allows_matching_native_recovery(self):
        with StreamFlatFallback().scenario() as (fixture, launch, instance, native):
            rc, result = actual_rth_cli_receipt(fixture, native, passed=True)
            active = launch.safe_json(fixture.state / 'active/pre.json')
            active.update(stage='lev1', config_sha256=launch.sha(launch.config('lev1')))
            launch.save(fixture.state / 'active/lev1.json', active)
            (fixture.state / 'active/pre.json').unlink()
            launch.native_recover = Mock(return_value=(rc, native))
            with patch.object(launch.time, 'monotonic', return_value=100):
                self.assertEqual(launch.recover_stage('lev1'), 0)
            partial = instance / 'stream-flat-probe.json'
            partial.write_text('{"status":')
            with patch.object(launch.time, 'monotonic', return_value=161):
                _, handoff, selected = launch.verify_handoff('lev1', '2026-10-14')
            self.assertEqual(selected, native)
            self.assertTrue(handoff['flat'])
            self.assertEqual(partial.read_text(), '{"status":')
            launch.keyed.assert_not_called()

    def test_successful_runner_cli_output_survives_direct_seq3_fixture_rewrite(self):
        with StreamFlatFallback().scenario() as (fixture, launch, instance, native):
            rc, result = actual_rth_cli_receipt(fixture, native, passed=True)
            self.assertEqual((rc, result['mode']), (0, 'adaptive_paper'))
            upstream = observer_fixtures.load('direct_seq3_rewriter', LATCH / 'recut.py')
            canonical = (ROOT / 'tests/fixtures/seq2-launch.txt').read_text()
            text = upstream.rewrite_launch(canonical, '1' * 64, hashlib.sha256(canonical.encode()).hexdigest())
            launch_file = fixture.bundle / 'launch.py'
            launch_file.write_text(text)
            direct = observer_fixtures.load('direct_seq3_launch', launch_file)
            for name in ('STATE', 'HOST_STOP', 'STOP', 'verify_bundle', 'verify_runtime', 'keyed'):
                setattr(direct, name, getattr(launch, name))
            active_path = fixture.state / 'active/pre.json'
            active = direct.safe_json(active_path)
            active.update(stage='lev1', config_sha256=direct.sha(direct.config('lev1')))
            direct.save(fixture.state / 'active/lev1.json', active)
            active_path.unlink()  # SYN fixture has exactly one active RTH stage.
            direct.native_recover = Mock(return_value=(rc, native))
            self.assertEqual(direct.recover_stage('lev1'), 0)
            self.assertTrue(direct.safe_json(instance / 'handoff.json')['flat'])
            direct.keyed.assert_not_called()

    def test_actual_rth_recover_cli_stream_failure_reaches_rest_and_records_flat(self):
        with StreamFlatFallback().scenario() as (fixture, launch, instance, native):
            rc, result = actual_rth_cli_receipt(fixture, native)
            self.assertEqual((rc, result['mode']), (3, 'adaptive_paper'))
            self.assertEqual(tuple(result['preflight'][k] for k in
                                   ('position_count', 'open_order_count', 'orders_submitted')), (0, 0, 0))
            active = launch.safe_json(fixture.state / 'active/pre.json')
            active.update(stage='lev1', config_sha256=launch.sha(launch.config('lev1')))
            launch.save(fixture.state / 'active/lev1.json', active)
            (fixture.state / 'active/pre.json').unlink()
            launch.native_recover = Mock(return_value=(rc, native))
            self.assertEqual(launch.recover_stage('lev1'), 0)
            launch.keyed.assert_called_once()
            self.assertIn(('GET', '/positions'), fixture.calls)
            self.assertIn(('GET', '/orders'), fixture.calls)
            handoff = launch.safe_json(instance / 'handoff.json')
            self.assertTrue(handoff['flat'])
            self.assertEqual((handoff['positions'], handoff['open_orders']), (0, 0))

    def test_actual_rth_cli_fallback_proof_admits_next_stage_and_rejects_tampering(self):
        with StreamFlatFallback().scenario() as (fixture, launch, instance, native):
            rc, result = actual_rth_cli_receipt(fixture, native)
            self.assertEqual((rc, result['mode']), (3, 'adaptive_paper'))
            active = launch.safe_json(fixture.state / 'active/pre.json')
            active.update(stage='lev1', config_sha256=launch.sha(launch.config('lev1')))
            launch.save(fixture.state / 'active/lev1.json', active)
            (fixture.state / 'active/pre.json').unlink()
            launch.native_recover = Mock(return_value=(rc, native))
            with patch.object(launch.time, 'monotonic', return_value=100):
                self.assertEqual(launch.recover_stage('lev1'), 0)
            probe = instance / 'stream-flat-probe.json'
            original = probe.read_bytes()
            # A stale legacy candidate must not take priority over the exact
            # proof fingerprint carried by this handoff.
            launch.save(instance / 'flat-probe.json', {'status': 'passed', 'flat': True,
                'positions': [], 'unresolved_orders': [], 'reconciliation': {'positions': 0, 'open_orders': 0},
                'kind': 'SYN stale legacy proof'})
            launch.config('lev2').write_bytes(launch.config('lev1').read_bytes())
            request = {'issuer': 'CC through co-op', 'bundle_sha256': launch.sha(fixture.bundle / 'SHA256SUMS'),
                       'config_hashes': {stage: launch.sha(launch.config(stage)) for stage in ('lev1', 'lev2')}}
            launch.save(fixture.bundle / 'GO-BINDING-REQUEST.json', request)
            authority = fixture.root / 'SYN-authority.md'
            authority.write_text('SYN authority for ' + request['bundle_sha256'])
            # The pre-existing scratch operator file remains untouched. This
            # scenario's admission controls are separate absent scratch paths.
            launch.HOST_STOP = fixture.root / 'admission-host-STOP'
            launch.assert_seq2_watchers_retired = Mock(return_value=[])
            launch.session_now = lambda: ('RTH', '2026-10-14')
            issuer_path = fixture.bundle / 'issue_go.py'
            spec = importlib.util.spec_from_file_location('next_stage_builder',
                ROOT / 'blueprints/us-equities/paper-lane-latch/recut.py')
            builder = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(builder)
            issuer_path.write_text(builder.isolate_issuer((ROOT / 'tests/fixtures/seq2-issue-go.txt').read_text()))
            with patch.dict(sys.modules, {'launch': launch}), \
                 patch.object(launch.time, 'monotonic', return_value=161), \
                 patch('lane_latch.assert_issuer_python', return_value=None):
                issuer = observer_fixtures.load('next_stage_real_issuer', issuer_path)
                issuer.writer_units = Mock(return_value=[])
                answer = issuer.issue('lev2', 'syn-next-lev2', authority, launch.sha(authority), False)
                slot = fixture.state / 'ready/lev2'
                self.assertEqual((slot / 'GO.sha256').read_text().strip(), launch.sha(slot / 'GO.json'))
                self.assertEqual(launch.safe_json(fixture.state / 'ready/lev2/GO.json')['previous_recover_sha256'],
                                 launch.sha(fixture.state / 'completed/2026-10-14/lev1.json'))
                damaged = launch.safe_json(probe)
                damaged['SYN_tampered'] = True
                launch.save(probe, damaged)
                with self.assertRaisesRegex(launch.Refused, 'previous_native_recover_hash'):
                    issuer.issue('lev2', 'syn-next-check', authority, launch.sha(authority), True)
                probe.write_bytes(original)  # Restore only this SYN fixture for the binding check.
                value = launch.binding('lev2')
                self.assertEqual(value['trial'], 'syn-next-lev2')


if __name__ == '__main__':
    unittest.main()
