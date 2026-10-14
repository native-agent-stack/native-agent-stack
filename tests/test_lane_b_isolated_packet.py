"""SYN stage-end chain on exact launcher bytes; no broker/unit/host state."""
from contextlib import ExitStack
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / 'blueprints/us-equities/paper-lane-latch'
FLAT = ROOT / 'blueprints/us-equities/paper-flat-proof'
LATCH = ROOT / 'blueprints/us-equities/paper-readiness-seq3'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class IsolatedPacket(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.stack.enter_context(patch.object(sys, 'path', [str(self.root), str(LATCH), *sys.path]))
        self.stack.enter_context(patch.dict(sys.modules))
        self.builder = load('isolation_builder_test', CODE / 'recut.py')
        baseline = os.environ.get('PAPER_LATCH_BASELINE')
        candidate = os.environ.get('PAPER_LATCH_BUNDLE')
        if baseline or candidate:
            packet = Path(baseline or candidate)
            text = (packet / 'launch.py').read_text()
            issuer = (packet / 'issue_go.py').read_text()
        else:
            flat = load('flat_builder_test', FLAT / 'recut.py')
            text = flat.rewrite_launch((ROOT / 'tests/fixtures/pre_skip/launch_seq2.py').read_text(), '1' * 64)
            text = self.builder.isolate_launch(text, '2' * 64)
            issuer = self.builder.isolate_issuer((ROOT / 'tests/fixtures/seq2-issue-go.txt').read_text())
        (self.root / 'launch.py').write_text(text)
        (self.root / 'issue_go.py').write_text(issuer)
        self.launch = load('launch', self.root / 'launch.py')
        self.launch.STATE = self.root / 'state'
        self.host = self.root / 'operator/STOP'
        self.host.parent.mkdir()
        self.lane = self.host.parent / 'lane-b/STOP'
        self.launch.HOST_STOP = self.host
        self.launch.STOP = self.host if baseline else self.lane
        self.launch.verify_bundle = self.launch.verify_runtime = lambda: None
        self.launch.assert_seq2_watchers_retired = lambda: []
        (self.root / 'configs').mkdir()
        (self.root / 'configs/pre.json').write_text('{}\n')
        (self.root / 'SHA256SUMS').write_text('SYN packet manifest\n')
        request = {'issuer': 'CC through co-op', 'bundle_sha256': self.launch.sha(self.root / 'SHA256SUMS'),
                   'config_hashes': {'pre': self.launch.sha(self.root / 'configs/pre.json')}}
        self.launch.save(self.root / 'GO-BINDING-REQUEST.json', request)
        self.instance = self.launch.STATE / 'instances/syn-stage'
        self.instance.mkdir(parents=True, mode=0o700)
        self.active = {'trial': 'syn-stage', 'stage': 'pre', 'instance': str(self.instance),
                       'session_date': '2026-10-14', 'config_sha256': request['config_hashes']['pre'],
                       'bundle_sha256': request['bundle_sha256'], 'go_sha256': '3' * 64}
        self.launch.save(self.launch.STATE / 'active/pre.json', self.active)
        self.launch.keyed = lambda *a, **k: self.fail('unexpected keyed call')
        self.launch.native_recover = self.recovery
        self.flat = True

    @property
    def marker(self):
        return self.instance / '.stage-hook-latch'

    def recovery(self, stage, active):
        output = self.instance / 'recover.json'
        value = {'status': 'passed' if self.flat else 'needs_attention', 'flat': self.flat,
                 'positions': [] if self.flat else [{'SYN': 'position'}], 'unresolved_orders': [],
                 'reconciliation': {'positions': 0 if self.flat else 1, 'open_orders': 0}}
        self.launch.save(output, value)
        return 0 if self.flat else 3, output

    def test_stage_end_sets_own_marker_without_creating_shared_stop(self):
        self.launch.stop_mark('pre')
        self.assertFalse(self.host.exists(), 'lane B stage end created the shared host STOP')
        self.assertFalse(self.lane.exists())
        self.assertTrue(self.marker.exists())
        self.assertTrue(self.launch.stop_present())
        self.assertEqual(self.launch.recover_stage('pre'), 0)
        self.assertFalse(self.host.exists())
        self.assertFalse(self.lane.exists())
        self.assertFalse(self.marker.exists())

    def test_nonflat_recovery_keeps_own_latch_and_issuer_blocked(self):
        self.flat = False
        self.launch.stop_mark('pre')
        with self.assertRaisesRegex(self.launch.Refused, 'recovery_not_flat'):
            self.launch.recover_stage('pre')
        self.assertFalse(self.host.exists())
        self.assertTrue(self.marker.exists())
        self.assertTrue((self.launch.STATE / 'active/pre.json').exists())
        issuer = load('isolated_issuer_test', self.root / 'issue_go.py')
        self.launch.session_now = lambda: ('RTH', '2026-10-14')
        issuer.writer_units = lambda: []
        with patch.object(sys, 'version_info', (3, 12, 3)), self.assertRaisesRegex(
                self.launch.Refused, 'active_experiment_requires_recovery'):
            issuer.build('pre-skip', 'syn-refused', 'pre_window_passed')
        # Even an orphan private marker blocks a later issuer admission.
        (self.launch.STATE / 'active/pre.json').unlink()
        with patch.object(sys, 'version_info', (3, 12, 3)), self.assertRaisesRegex(self.launch.Refused, 'stop_present'):
            issuer.build('pre-skip', 'syn-refused', 'pre_window_passed')

    def test_operator_host_and_lane_stops_stay_byte_identical(self):
        for path in (self.host, self.lane):
            with self.subTest(path=path.name):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('SYN operator abort\n')
                before = path.stat()
                self.launch.stop_mark('pre')
                self.assertEqual(self.launch.recover_stage('pre'), 0)
                self.assertEqual(path.read_text(), 'SYN operator abort\n')
                self.assertEqual((path.stat().st_ino, path.stat().st_mtime_ns), (before.st_ino, before.st_mtime_ns))
                path.unlink()
                self.launch.save(self.launch.STATE / 'active/pre.json', self.active)

    def test_tampered_private_latch_never_clears_operator_or_marker(self):
        self.launch.stop_mark('pre')
        self.marker.write_text('SYN tampered marker\n')
        self.assertEqual(self.launch.recover_stage('pre'), 0)
        self.assertTrue(self.marker.exists())
        self.assertTrue(self.launch.stop_present())
        self.assertFalse(self.host.exists())

    def test_unit_transform_removes_touch_and_keeps_two_native_hooks(self):
        body = ('[Service]\nWorkingDirectory=/SYN/source\nExecStart=/SYN/source/launch.py run pre\n'
                'ExecStopPost=/SYN/source/launch.py stop-mark pre\n'
                "ExecStopPost=/usr/bin/bash -c '/usr/bin/touch /SYN/STOP'\n"
                'ExecStopPost=/SYN/source/launch.py recover pre\n')
        value, removed = self.builder.isolate_unit(body, Path('/SYN/source'), self.root)
        self.assertEqual(removed, 1)
        self.assertNotIn('/usr/bin/touch', value)
        self.assertEqual(value.count('ExecStopPost='), 2)

    def test_new_packet_retirement_requires_both_prior_generations(self):
        module = load('local_flat_retirement_test', CODE / 'flat_retirement.py')
        original_paths = module.original_retired.__globals__['PATHS']
        def inventory(command, **kwargs):
            paths = [x for x in command if x.endswith('.path')]
            rows = []
            for name in paths:
                state = 'enabled' if name == self.enabled else 'disabled'
                rows.append('Id=' + name + '\nLoadState=loaded\nActiveState=inactive\nUnitFileState=' + state)
            return SimpleNamespace(returncode=0, stdout='\n\n'.join(rows))
        with patch.object(module.original_retired.__globals__['subprocess'], 'run', side_effect=inventory):
            self.enabled = None
            self.assertEqual(len(module.assert_retired()), 22)
            for name in (*original_paths, *module.PATHS):
                self.enabled = name
                with self.assertRaisesRegex(ValueError, 'seq2_watchers_not_retired'):
                    module.assert_retired()
        self.assertEqual(module.original_retired.__globals__['PATHS'], original_paths)


if __name__ == '__main__':
    unittest.main()
