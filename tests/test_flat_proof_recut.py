"""Small native seal fixture; runtime/config bytes and required kwargs matter."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / 'blueprints/us-equities/paper-flat-proof'
spec = importlib.util.spec_from_file_location('flat_proof_recut_test', CODE / 'recut.py')
recut = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recut)


class Recut(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source'
        self.source.mkdir()
        self.output = self.root / 'output'
        files = {
            'launch.py': (ROOT / 'tests/fixtures/pre_skip/launch_seq2.py').read_bytes(),
            'observe_flat.py': (ROOT / 'tests/fixtures/pre_skip/observe_flat_seq2.py').read_bytes(),
            'issue_go.py': b'# SYN native issuer\n',
            'configs/pre.json': b'{"benchmarks":["SPY"],"feed":"iex"}\n',
            'frozen/blueprints/us-equities/adaptive-paper/transport.py':
                b'def preflight(key, secret, symbols, *, feed="iex", before_request): pass\n',
        }
        for n in range(11):
            stem = 'units/paper-ready-syn' + str(n) + '-seq2'
            files[stem + '.service'] = ('[Service]\nWorkingDirectory=' + str(self.source) + '\nExecStart=' +
                                       str(self.source) + '/launch.py\n').encode()
            files[stem + '.path'] = ('[Path]\nUnit=paper-ready-syn' + str(n) + '-seq2.service\n').encode()
        for name, raw in files.items():
            p = self.source / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(raw)
        (self.source / 'SHA256SUMS').write_text(''.join(
            hashlib.sha256(raw).hexdigest() + '  ' + name + '\n' for name, raw in sorted(files.items())))
        (self.source / 'GO-BINDING-REQUEST.json').write_text('{}\n')
        self.original_seal = (self.source / 'SHA256SUMS').read_bytes()
        self.expected = recut.sha(self.original_seal)

    def test_new_seal_preserves_original_runtime_and_config(self):
        receipt = recut.recut(self.source, self.output, self.expected, '1' * 40)
        self.assertEqual((self.source / 'SHA256SUMS').read_bytes(), self.original_seal)
        self.assertEqual((self.output / 'configs/pre.json').read_bytes(), (self.source / 'configs/pre.json').read_bytes())
        self.assertEqual((self.output / 'frozen/blueprints/us-equities/adaptive-paper/transport.py').read_bytes(),
                         (self.source / 'frozen/blueprints/us-equities/adaptive-paper/transport.py').read_bytes())
        self.assertEqual(receipt['unit_count'], 22)
        self.assertFalse(any('-seq2.' in p.name for p in (self.output / 'units').iterdir()))
        self.assertEqual(receipt['transport_calls'][0]['missing'], [])
        self.assertEqual(json.loads((self.output / 'PREDECESSOR-RECOVERY.json').read_text())['bundle_sha256'], self.expected)

    def test_wrong_expected_seal_refuses_without_destination(self):
        with self.assertRaisesRegex(ValueError, 'predecessor_seal_mismatch'):
            recut.recut(self.source, self.output, '2' * 64, '1' * 40)
        self.assertFalse(self.output.exists())

    def test_changed_source_member_refuses_without_destination(self):
        (self.source / 'observe_flat.py').write_text('# changed\n')
        with self.assertRaisesRegex(ValueError, 'predecessor_manifest_refused'):
            recut.recut(self.source, self.output, self.expected, '1' * 40)
        self.assertFalse(self.output.exists())


if __name__ == '__main__':
    unittest.main()
