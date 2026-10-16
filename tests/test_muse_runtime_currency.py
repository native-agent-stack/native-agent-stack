"""Version-only fail-first control using the real retained vendor ELF; no model."""
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import unittest
from unittest import mock

from tools import muse_file_fence as fence_module


class MuseRuntimeCurrencyTests(unittest.TestCase):
    def test_vendor_script_bytes_kept_out_of_public_tree(self):
        root = Path(__file__).resolve().parents[1]
        vendor = root / 'notes/muse-requal-149-20261015/vendor'
        self.assertFalse((vendor / 'install.sh').exists())
        self.assertFalse((vendor / 'muse-launcher.sh').exists())

    def test_version_spoof_refused_before_runtime_or_log_creation(self):
        with tempfile.TemporaryDirectory(prefix='muse-identity-', dir='/var/tmp') as tmp:
            root = Path(tmp)
            work = root / 'work'
            work.mkdir()
            brief = root / 'brief.md'
            brief.write_text('Public identity fixture.\n')
            auth = root / 'synthetic-auth.json'
            auth.write_text('{}\n')
            ran = work / 'runtime-ran'
            runtime = root / 'version-spoof'
            runtime.write_text('#!/usr/bin/python3\nfrom pathlib import Path\n'
                               + 'Path(' + repr(str(ran)) + ').touch()\n'
                               + "print('Muse Code synthetic (1.4.9-R6297.1)')\n")
            runtime.chmod(0o700)
            logs = root / 'logs'
            argv = ['fence', '--probe-only', '--runtime', str(runtime),
                    '--auth', str(auth), str(work), str(brief), str(logs)]
            with mock.patch('sys.argv', argv), \
                    mock.patch.object(fence_module, 'native_argv', return_value=[]), \
                    mock.patch.object(fence_module, 'probe', return_value={'pass': True}):
                with self.assertRaisesRegex(ValueError, '^runtime sha256 mismatch$'):
                    fence_module.main()
            self.assertFalse(ran.exists(), 'identity must be checked before any runtime execution')
            self.assertFalse(logs.exists(), 'identity must be checked before log creation')

    def test_currency_markdown_commitments_resolve_to_public_sources(self):
        """Private coordination citations carry names, not content commitments."""
        root = Path(__file__).resolve().parents[1]
        evidence = json.loads((root / 'manifests/evidence.json').read_text())
        public = {row['sha256'] for row in evidence['files']}
        # Vendor source identities may remain public with URL pins while the
        # byte snapshots are held in the explicitly private horizon repository.
        source_refs = json.loads((root / 'notes/muse-requal-149-20261015/source-captures/http-provenance.json').read_text())
        public.update(row['capture_sha256'] for row in source_refs['sources']
                      if row['requested_url'] in {'https://dev.meta.ai/install.sh',
                                                 'https://api.meta.ai/muse-launcher.sh'})
        # Published Git identities cited by this bounded currency record.
        public.update({'5bab63233ef90260bec4a8ee0cec4f5e4431776c',
                       '48251c58433848fd0f795d79ab8e1bb32fcf0f7f',
                       'cdc7988db099b4bfbb973edcb68ad9749dc51e1e', '8053f14e7e0817d2502dff2bb284bfb7e1b0152f',
                       '124c4cdf4321f63ef17a1cb0ce8f9dd45bd7adbe'})
        notes = root / 'notes/muse-requal-149-20261015'
        for name in ('manifest-147.json', 'manifest-149.json'):
            manifest = json.loads((notes / 'vendor' / name).read_text())
            public.update(row['checksum'] for row in manifest['artifacts'].values())
        records = [root / 'docs/decisions/2026-10-15-muse-149-requalification.md',
                   *notes.glob('*.md')]
        for path in records:
            for line, text in enumerate(path.read_text().splitlines(), 1):
                for match in re.finditer(r'\b[0-9a-fA-F]{7,64}\b', text):
                    value = match.group().lower()
                    if not re.search('[a-f]', value):
                        continue
                    with self.subTest(path=path.relative_to(root), line=line):
                        self.assertTrue(any(digest.startswith(value) for digest in public),
                                        'unresolved publication commitment (value withheld)')

    @unittest.skipUnless(os.environ.get('MUSE_FENCE_NATIVE_PROBE') == '1',
                         'explicit retained-client model-free qualification')
    def test_old_pin_refuses_new_elf_then_current_pin_passes(self):
        runtime = (Path.home() / '.local/share/native-agent-stack/muse-fence/runtimes'
                   / '1.4.9-R6297.1/muse-bin')
        self.assertEqual(hashlib.sha256(runtime.read_bytes()).hexdigest(),
                         'a228010021276e112aa8422eb56ae82c0375405701950f6529bed4c9fe8abe05')
        with tempfile.TemporaryDirectory(prefix='muse-currency-', dir='/var/tmp') as tmp:
            root = Path(tmp)
            work = root / 'work'
            work.mkdir()
            brief = root / 'brief.md'
            brief.write_text('Public model-free version qualification.\n')
            auth = root / 'synthetic-sign-in.json'
            auth.write_text('{}\n')

            def argv(logs):
                return ['muse_file_fence.py', '--probe-only', '--runtime', str(runtime),
                        '--auth', str(auth), str(work), str(brief), str(logs)]

            rejected = root / 'rejected'
            with mock.patch.object(fence_module, 'VERSION', '1.4.7-R6101.1'), \
                    mock.patch('sys.argv', argv(rejected)):
                with self.assertRaisesRegex(ValueError, '^runtime pin mismatch$'):
                    fence_module.main()
            self.assertEqual((rejected / 'muse-exec.jsonl').stat().st_size, 0)
            self.assertEqual((rejected / 'probe-echo.jsonl').stat().st_size, 0)
            with mock.patch('sys.argv', argv(root / 'accepted')):
                self.assertEqual(fence_module.main(), 0)
