"""Execute the native observer, transport and both launcher call paths on SYN state.

PAPER_FLAT_BASELINE selects the untouched sealed predecessor for fail-first runs.
Only SDK/HTTP answers and host runtime checks are fixtures; preflight is real.
"""
import ast
from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
CODE = REPO / 'blueprints/us-equities/paper-flat-proof'
FIXTURE = REPO / 'tests/fixtures/pre_skip'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class FlatProbe(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.temp = self.stack.enter_context(tempfile.TemporaryDirectory())
        self.root = Path(self.temp)
        self.bundle = self.root / 'bundle'
        self.bundle.mkdir()
        baseline = os.environ.get('PAPER_FLAT_BASELINE')
        self.baseline = Path(baseline) if baseline else None
        candidate = Path(os.environ['PAPER_FLAT_BUNDLE']) if os.environ.get('PAPER_FLAT_BUNDLE') else None
        frozen = Path(os.environ['PAPER_FLAT_FROZEN']) if os.environ.get('PAPER_FLAT_FROZEN') else (
            self.baseline / 'frozen' if baseline else REPO)
        (self.bundle / 'frozen').symlink_to(frozen, target_is_directory=True)
        self.paper = frozen / 'blueprints/us-equities/adaptive-paper'
        self.stack.enter_context(patch.object(sys, 'path', [str(self.bundle), str(self.paper), *sys.path]))
        # Isolate native imports from other unittest modules and restore afterwards.
        local_names = {p.stem for p in self.paper.glob('*.py')} | {
            'flat_builder_fixture', 'flat_launch_fixture', 'flat_observer_fixture', 'recover_pre_skip',
            'alpaca.data.enums', 'alpaca.data.requests'}
        saved = {name: sys.modules[name] for name in local_names if name in sys.modules}
        def restore_local_modules():
            for name in local_names:
                sys.modules.pop(name, None)
            sys.modules.update(saved)
        self.stack.callback(restore_local_modules)
        for name in local_names:
            sys.modules.pop(name, None)
        launcher = self.baseline / 'launch.py' if baseline else (
            candidate / 'launch.py' if candidate else FIXTURE / 'launch_seq2.py')
        text = launcher.read_text()
        if not baseline and not candidate:
            builder = load('flat_builder_fixture', CODE / 'recut.py')
            text = builder.rewrite_launch(text, '1' * 64)
        (self.bundle / 'launch.py').write_text(text)
        observer = self.baseline / 'observe_flat.py' if baseline else (
            candidate / 'observe_flat.py' if candidate else CODE / 'observe_flat.py')
        shutil.copyfile(observer, self.bundle / 'observe_flat.py')
        if not baseline:
            shutil.copyfile((candidate or CODE) / 'recover_pre_skip.py', self.bundle / 'recover_pre_skip.py')
        self.launch = load('flat_launch_fixture', self.bundle / 'launch.py')
        self.state = self.root / 'state'
        self.state.mkdir()
        self.launch.STATE = self.state
        self.launch.STOP = self.root / 'operator-STOP'
        self.launch.STOP.write_text('SYN operator latch must remain unchanged\n')
        self.stop_bytes = self.launch.STOP.read_bytes()
        (self.bundle / 'configs').mkdir()
        (self.bundle / 'configs/pre.json').write_text(json.dumps({'benchmarks': ['SPY'], 'feed': 'iex'}))
        (self.bundle / 'SHA256SUMS').write_text('SYN new sealed bundle inventory\n')
        self.stack.enter_context(patch.object(self.launch, 'verify_bundle'))
        self.stack.enter_context(patch.object(self.launch, 'verify_runtime'))
        self.stack.enter_context(patch.object(self.launch, 'skip_available'))
        self.stack.enter_context(patch.object(self.launch, 'session_now', return_value=('RTH', '2026-10-14')))
        self.stack.enter_context(patch.object(self.launch, 'keyed', side_effect=self.execute))
        self.transport = load('transport', self.paper / 'transport.py')
        self.positions = []
        self.orders = []
        self.calls = []
        self.stdout = []
        self.clients = []
        if os.environ.get('PAPER_FLAT_REAL_SDK') == '1':
            # Exercise the pinned SDK and native GuardedSession, mocking only
            # the final network send. No credentials or external requests.
            import requests
            self.stack.enter_context(patch.object(requests.Session, 'request', side_effect=self.http))
            real_client = self.transport._sdk_client
            def native_client(key, secret, before_request, observer=None, **kwargs):
                result = real_client(key, secret, before_request, observer, **kwargs)
                self.clients.append((result, before_request))
                return result
            self.stack.enter_context(patch.object(self.transport, '_sdk_client', side_effect=native_client))
        else:
            # Standard-library-only CI executes the real frozen preflight with
            # SDK value types/HTTP answers as fixtures. The native mode above
            # additionally traverses alpaca-py and its guarded HTTP session.
            enums = types.ModuleType('alpaca.data.enums')
            enums.DataFeed = lambda feed: feed
            requests = types.ModuleType('alpaca.data.requests')
            requests.StockLatestQuoteRequest = lambda **kwargs: types.SimpleNamespace(**kwargs)
            sys.modules['alpaca.data.enums'] = enums
            sys.modules['alpaca.data.requests'] = requests
            self.stack.enter_context(patch.object(self.transport, '_sdk_client', side_effect=self.client))

    def answer(self, path):
        if path == '/account':
            return {'id': 'SYN account', 'cash': '10000', 'equity': '10000', 'buying_power': '10000'}
        if path == '/clock':
            return {'is_open': True, 'timestamp': '2026-10-14T14:00:00Z',
                    'next_open': '2026-10-15T13:30:00Z', 'next_close': '2026-10-14T20:00:00Z'}
        if path == '/positions':
            return self.positions
        if path == '/orders':
            return self.orders
        if path.startswith('/assets/'):
            return {'symbol': path.split('/')[-1], 'status': 'active', 'tradable': True, 'attributes': []}
        if path == '/stocks/quotes/latest':
            return {'SPY': {'bp': '100', 'ap': '101', 'bs': 10, 'as': 10, 't': '2026-10-14T14:00:00Z'}}
        raise AssertionError('Unexpected read: ' + path)

    def http(self, method, url, **kwargs):
        import requests
        from urllib.parse import urlsplit
        self.assertEqual(method, 'GET', 'No order/cancel/close transport method is allowed')
        path = urlsplit(url).path.removeprefix('/v2')
        self.calls.append((method, path))
        value = self.answer(path)
        if path == '/stocks/quotes/latest':
            value = {'quotes': value}
        result = requests.Response()
        result.status_code = 200
        result._content = json.dumps(value).encode()
        result.headers = {'content-type': 'application/json'}
        return result

    def client(self, key, secret, before_request, observer=None, *, data=False, read_only=False, lock=None):
        self.assertTrue(read_only)
        test = self
        class Session:
            def close(self):
                pass
        class Client:
            _session = Session()
            def get(self, path, params=None):
                before_request('data_read' if data else 'read')
                test.calls.append(('GET', path))
                return test.answer(path)
            def get_account(self):
                return self.get('/account')
            def get_clock(self):
                return self.get('/clock')
            def get_all_positions(self):
                return self.get('/positions')
            def get_asset(self, symbol):
                return self.get('/assets/' + symbol)
            def get_stock_latest_quote(self, request):
                return self.get('/stocks/quotes/latest')
            def __getattr__(self, name):
                raise AssertionError('Order/cancel/close method is forbidden: ' + name)
        result = Client()
        self.clients.append((result, before_request))
        return result

    def execute(self, command, **kwargs):
        argv = list(map(str, command))
        self.assertIn('observe_flat.py', argv[4])
        observer = load('flat_observer_fixture', Path(argv[4]))
        output = io.StringIO()
        with patch.object(sys, 'argv', argv[4:]), patch.dict(os.environ, {
                'APCA_API_KEY_ID': 'SYN key', 'APCA_API_SECRET_KEY': 'SYN secret'}), patch('sys.stdout', output):
            rc = observer.main()
        self.stdout.append(output.getvalue())
        return rc

    def skip_go(self):
        slot = self.state / 'ready/pre-skip'
        slot.mkdir(parents=True)
        value = {'schema_version': 1, 'purpose': 'GET_ONLY_PRE_SKIP',
                 'bundle_sha256': self.launch.sha(self.bundle / 'SHA256SUMS'),
                 'config_sha256': self.launch.sha(self.launch.config('pre')), 'trial': 'syn-pre-skip',
                 'session_kind': 'RTH', 'session_date': '2026-10-14',
                 'issued_at_utc': datetime.now(timezone.utc).isoformat(),
                 'state_root': str(self.state / 'instances/syn-pre-skip/native-state'),
                 'skip_reason': 'pre_window_passed'}
        self.launch.save(slot / 'GO.json', value)
        (slot / 'GO.sha256').write_text(self.launch.sha(slot / 'GO.json'))
        return value

    def test_skip_executes_observer_against_real_transport(self):
        self.launch.STOP.unlink()  # SYN only; no production latch access.
        self.skip_go()
        try:
            rc = self.launch.skip_stage()
        except FileNotFoundError:
            self.fail('Missing native flat-probe after observer: ' + ''.join(self.stdout))
        self.assertEqual(rc, 0)
        proof = self.launch.safe_json(self.state / 'completed/2026-10-14/pre.json')
        self.assertTrue(proof['flat'])
        self.assertFalse((self.state / 'active/pre-skip.json').exists())
        self.assertIn(('GET', '/positions'), self.calls)
        self.assertIn(('GET', '/orders'), self.calls)
        hook = self.clients[0][1]
        for _ in range(50):
            try:
                hook('read')
            except Exception as exc:
                self.assertEqual(str(exc), 'preflight_request_bound')
                break
        else:
            self.fail('native preflight hook did not enforce its 50-request bound')

    def test_no_owned_trial_hook_executes_observer_against_real_transport(self):
        instance = self.state / 'instances/syn-refused'
        instance.mkdir(parents=True)
        active = {'config_sha256': self.launch.sha(self.launch.config('pre')),
                  'bundle_sha256': self.launch.sha(self.bundle / 'SHA256SUMS'),
                  'trial': 'syn-refused', 'session_date': '2026-10-14', 'go_sha256': '2' * 64,
                  'instance': str(instance), 'state_root': str(instance / 'native-state')}
        self.launch.save(self.state / 'active/pre.json', active)
        self.launch.save(instance / 'stop-hook.json', {'created_by_hook': False})
        output = instance / 'recover.json'
        self.launch.save(output, {'reason': 'no_mover_trial_to_recover'})
        with patch.object(self.launch, 'native_recover', return_value=(2, output)):
            try:
                rc = self.launch.recover_stage('pre')
            except FileNotFoundError:
                self.fail('Missing native recovery flat-probe after observer: ' + ''.join(self.stdout))
        self.assertEqual(rc, 0)
        self.assertTrue(self.launch.safe_json(instance / 'flat-probe.json')['flat'])
        self.assertEqual(self.launch.STOP.read_bytes(), self.stop_bytes)

    def stuck_skip(self):
        value = self.skip_go()
        slot = self.state / 'ready/pre-skip'
        instance = self.state / 'instances' / value['trial']
        instance.mkdir(parents=True)
        token = slot / (value['trial'] + '.GO.used.sha256')
        (slot / 'GO.sha256').rename(token)
        # Original bundle is independently sealed and retained, never modified.
        source = self.root / 'original'
        source.mkdir()
        (source / 'configs').mkdir()
        shutil.copyfile(self.launch.config('pre'), source / 'configs/pre.json')
        (source / 'SHA256SUMS').write_text(self.launch.sha(source / 'configs/pre.json') + '  configs/pre.json\n')
        predecessor = self.launch.sha(source / 'SHA256SUMS')
        value['bundle_sha256'] = predecessor
        self.launch.save(slot / 'GO.json', value)
        token.write_text(self.launch.sha(slot / 'GO.json'))
        active = dict(value, instance=str(instance), go_sha256=token.read_text())
        self.launch.save(self.state / 'active/pre-skip.json', active)
        self.launch.save(self.bundle / 'PREDECESSOR-RECOVERY.json', {
            'source': str(source), 'bundle_sha256': predecessor,
            'config_sha256': value['config_sha256'], 'source_config': 'configs/pre.json'})
        return active, instance

    def recover_skip(self):
        with patch.object(sys, 'argv', [str(self.bundle / 'launch.py'), 'recover', 'pre-skip']):
            return self.launch.main()

    def test_recover_pre_skip_retires_matching_original_binding_get_only(self):
        active, instance = self.stuck_skip()
        original = (self.state / 'active/pre-skip.json').read_bytes()
        self.assertEqual(self.recover_skip(), 0)
        self.assertFalse((self.state / 'active/pre-skip.json').exists())
        self.assertEqual((instance / 'active.finished.json').read_bytes(), original)
        receipt = self.launch.safe_json(instance / 'handoff.json')
        self.assertEqual(receipt['predecessor_bundle_sha256'], active['bundle_sha256'])
        self.assertEqual(receipt['bundle_sha256'], self.launch.sha(self.bundle / 'SHA256SUMS'))
        self.assertEqual(receipt['recover_rc'], 0)
        self.assertIs(receipt['flat'], True)
        self.assertEqual((receipt['positions'], receipt['open_orders']), (0, 0))
        self.assertEqual(self.launch.STOP.read_bytes(), self.stop_bytes)
        self.assertEqual({method for method, _ in self.calls}, {'GET'})
        self.assertIn(('GET', '/positions'), self.calls)
        self.assertIn(('GET', '/orders'), self.calls)

    def test_nonflat_pre_skip_retains_original_marker(self):
        active, instance = self.stuck_skip()
        original = (self.state / 'active/pre-skip.json').read_bytes()
        self.positions = [{'symbol': 'SPY', 'qty': '1', 'avg_entry_price': '100'}]
        self.assertEqual(self.recover_skip(), 2)
        self.assertEqual((self.state / 'active/pre-skip.json').read_bytes(), original)
        receipt = self.launch.safe_json(instance / 'handoff.json')
        self.assertEqual(receipt['status'], 'needs_attention')
        self.assertIs(receipt['flat'], False)
        self.assertFalse((self.state / 'completed/2026-10-14/pre.json').exists())
        self.assertEqual(self.launch.STOP.read_bytes(), self.stop_bytes)

    def test_open_orders_alone_are_not_flat(self):
        _, instance = self.stuck_skip()
        synthetic_id = '-'.join(['0' * 8, '0' * 4, '0' * 4, '0' * 4, '0' * 11 + '1'])
        self.orders = [{'id': synthetic_id, 'client_order_id': 'syn-order',
                        'symbol': 'SPY', 'side': 'buy', 'qty': '1', 'filled_qty': '0',
                        'type': 'limit', 'time_in_force': 'day', 'status': 'new', 'limit_price': '100'}]
        self.assertEqual(self.recover_skip(), 2)
        self.assertTrue((self.state / 'active/pre-skip.json').exists())
        self.assertFalse(self.launch.safe_json(instance / 'handoff.json')['flat'])

    def test_forged_original_binding_refuses_before_any_get(self):
        for key in ['bundle_sha256', 'config_sha256', 'go_sha256', 'instance', 'state_root', 'trial']:
            with self.subTest(key=key):
                active, _ = self.stuck_skip() if not (self.state / 'active/pre-skip.json').exists() else (
                    self.launch.safe_json(self.state / 'active/pre-skip.json'), None)
                original = dict(active)
                active[key] = 'forged'
                self.launch.save(self.state / 'active/pre-skip.json', active)
                self.assertEqual(self.recover_skip(), 2)
                self.assertEqual(self.calls, [])
                self.assertTrue((self.state / 'active/pre-skip.json').exists())
                self.launch.save(self.state / 'active/pre-skip.json', original)

    def test_full_order_page_is_incomplete_and_never_flat(self):
        self.stuck_skip()
        # Empty normalized order list cannot override the transport completeness flag.
        real = self.transport.preflight
        def incomplete(*args, **kwargs):
            value = real(*args, **kwargs)
            value['open_orders_complete'] = False
            return value
        with patch.object(self.transport, 'preflight', side_effect=incomplete):
            self.assertEqual(self.recover_skip(), 2)
        self.assertTrue((self.state / 'active/pre-skip.json').exists())

    def test_variant_required_keyword_only_contracts(self):
        builder = load('flat_variant_fixture', CODE / 'recut.py')
        calls = builder.variant_check(self.bundle)
        self.assertTrue(any(c['file'] == 'observe_flat.py' and c['function'] == 'preflight' for c in calls))
        self.assertFalse([c for c in calls if c['missing']])

    def test_predecessor_bytes_changed_refuse_without_get(self):
        self.stuck_skip()
        (self.root / 'original/configs/pre.json').write_text('{"tampered":true}\n')
        self.assertEqual(self.recover_skip(), 2)
        self.assertEqual(self.calls, [])
        self.assertTrue((self.state / 'active/pre-skip.json').exists())

    def test_foreign_get_only_recovery_cannot_construct_order_transport(self):
        self.stuck_skip()
        with patch.object(self.transport, 'AlpacaPaperTransport', side_effect=AssertionError('write transport forbidden')):
            self.assertEqual(self.recover_skip(), 0)
        self.assertEqual({method for method, _ in self.calls}, {'GET'})

    def test_genuine_flat_handoff_is_admissible_after_real_quiet_interval(self):
        self.stuck_skip()
        self.assertEqual(self.recover_skip(), 0)
        receipt = self.launch.safe_json(self.state / 'completed/2026-10-14/pre.json')
        with patch.object(self.launch.time, 'monotonic', return_value=receipt['recover_finished_monotonic'] + 61):
            _, value, _ = self.launch.verify_handoff('pre', '2026-10-14')
        self.assertIs(value['pre_did_not_trade'], True)


if __name__ == '__main__':
    unittest.main()
