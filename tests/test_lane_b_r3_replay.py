"""Emitted-packet replay contracts, SYN only; archived replay sources stay intact."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / 'blueprints/us-equities/paper-lane-latch'
REPLAY = ROOT / 'blueprints/us-equities/paper-open-e2e/seq2-replay'


def source_packet(root):
    source = root / 'source'
    source.mkdir()
    files = {
        'launch.py': (ROOT / 'tests/fixtures/pre_skip/launch_seq2.py').read_bytes(),
        'observe_flat.py': (ROOT / 'tests/fixtures/pre_skip/observe_flat_seq2.py').read_bytes(),
        'issue_go.py': (ROOT / 'tests/fixtures/seq2-issue-go.txt').read_bytes(),
        'dry_run.py': (ROOT / 'blueprints/us-equities/paper-readiness-seq3/dry_run.py').read_bytes(),
        'launch_data.py': b'# SYN unused data launcher in this narrow contract probe\n',
        'data_worker.py': b'# SYN unused data worker in this narrow contract probe\n',
        'frozen/blueprints/us-equities/adaptive-paper/transport.py': b'# SYN no transport calls\n',
        'frozen/blueprints/us-equities/adaptive-paper/scheduled_trial.sh':
            (ROOT / 'blueprints/us-equities/adaptive-paper/scheduled_trial.sh').read_bytes(),
    }
    files.update({p.name: p.read_bytes() for p in REPLAY.glob('test_*.py')})
    stages = ('record', 'scan', 'pre', 'pre-skip', 'sip', 'lev1', 'lev2', 'lev4', 'edge2', 'edge8', 'iex')
    for stage in stages:
        files['configs/' + stage + '.json'] = b'{}\n'
        name = 'paper-ready-' + stage + '-8c95a50d-seq2'
        trading = stage not in ('record', 'scan', 'pre-skip')
        action = 'run ' + stage if trading else 'skip pre-skip'
        command = 'launch.py ' + action if stage not in ('record', 'scan') else 'launch_data.py ' + stage
        service = ('[Unit]\nOnFailure=paper-alert@%n.service\n[Service]\nWorkingDirectory=' + str(source) +
                   '\nCPUWeight=50\nUMask=0077\nKillMode=control-group\nRuntimeMaxSec=' +
                   ('4500s' if stage == 'pre' else '1200s') + '\nTimeoutStopSec=900s\nExecStart=' +
                   str(source) + '/' + command + '\n')
        if trading:
            service += ('ExecStopPost=' + str(source) + '/launch.py stop-mark ' + stage + '\n'
                        "ExecStopPost=/usr/bin/bash -c '/usr/bin/touch /SYN/STOP'\n"
                        'ExecStopPost=' + str(source) + '/launch.py recover ' + stage + '\n')
        files['units/' + name + '.service'] = service.encode()
        files['units/' + name + '.path'] = ('[Path]\nPathChanged=/SYN/ready/' + stage +
                                          '/GO.sha256\nUnit=' + name + '.service\n').encode()
    for name, raw in files.items():
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    (source / 'SHA256SUMS').write_text(''.join(hashlib.sha256(raw).hexdigest() + '  ' + name + '\n'
                                            for name, raw in sorted(files.items())))
    (source / 'GO-BINDING-REQUEST.json').write_text('{}\n')
    return source


class RetainedReplay(unittest.TestCase):
    def test_emitted_packet_retained_lifecycle_and_unit_contracts(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = source_packet(root)
            spec = importlib.util.spec_from_file_location('r3_replay_builder', CODE / 'recut.py')
            builder = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(builder)
            digest = hashlib.sha256((source / 'SHA256SUMS').read_bytes()).hexdigest()
            output = root / 'new-uninstalled-packet'
            # Bind current uncommitted generator bytes only in this SYN fixture.
            # The real private-context drill uses actual Git bindings separately.
            with patch.object(builder, 'pinned_file', side_effect=lambda pin, path: (ROOT / path).read_bytes()):
                builder.seal(source, source, output, digest, digest, '1' * 40)
            for name in ('test_wiring.py', 'test_go_issuer.py', 'test_sequencing.py',
                         'test_unit_contracts.py', 'test_data_wiring.py'):
                self.assertEqual((output / name).read_bytes(), (source / name).read_bytes())
            # Import the complete unchanged source inventory, but run the three
            # retained contracts affected by r3. Data implementations are inert
            # placeholders in this narrow fixture; no data test is selected.
            script = '''import json,sys,types,unittest
from pathlib import Path
sys.dont_write_bytecode=True
sys.path.insert(0,sys.argv[1])
for name in ('data_worker','mover_scan','sessions'):
    sys.modules[name]=types.ModuleType(name)
    sys.modules[name].__file__=str(Path(sys.argv[1])/(name+'.py'))
import dry_run
assert dry_run.MINIMUM_EXPECTED_CASES == 49
class FocusedLoader(unittest.TestLoader):
    def loadTestsFromModule(self,module,*args,**kwargs):
        if module.__name__ == 'test_wiring':
            return self.loadTestsFromName('Wiring.test_whole_pre_then_seven_rth_config_sequence_with_recover_between',module)
        if module.__name__ == 'test_unit_contracts':
            return self.loadTestsFromName('Units.test_all_order_services_bind_correct_stage_bounds_and_stop_recovery_order',module)
        if module.__name__ == 'test_sequencing':
            return self.loadTestsFromName('Sequencing.test_skipped_pre_flat_probe_handoff_starts_sip',module)
        return unittest.TestSuite()
unittest.defaultTestLoader=FocusedLoader()
dry_run.MINIMUM_EXPECTED_CASES=3
receipt=dry_run.run(Path(sys.argv[1]))
print(json.dumps(receipt))
raise SystemExit(0 if receipt['status']=='passed' else 1)
'''
            result = subprocess.run([sys.executable, '-E', '-s', '-B', '-c', script, str(output)],
                                    capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stderr)
            receipt = json.loads(result.stdout)
            self.assertEqual(receipt['cases'], 3)
            self.assertEqual(receipt['keyed_tripwire_hits'], 0)
            self.assertEqual(receipt['subprocess_tripwire_hits'], 0)
            self.assertEqual(receipt['services_started'], 0)


if __name__ == '__main__':
    unittest.main()
