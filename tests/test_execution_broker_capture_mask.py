"""Synthetic publication-boundary controls; not broker/E2E evidence."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'tools/sota-convergence/mask_execution_broker_capture.py'


class CaptureMask(unittest.TestCase):
    def test_cli_preserves_bytes_except_exact_private_path_substitutions(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            raw, output, mapping = [root / name for name in ('raw.bin', 'masked.bin', 'mapping.json')]
            # SYN paths: no credential or real host identity appears in this test.
            raw.write_bytes(b'/private-syn/tree/sub/a\r\nrc=2\x00\xff /private-syn/tree\n')
            mapping.write_text(json.dumps({'/private-syn/tree': '<WORKTREE>',
                                           '/private-syn/tree/sub': '<SUBTREE>'}))
            result = subprocess.run([sys.executable, str(SCRIPT), '--mapping', str(mapping),
                                     '--input', str(raw), '--output', str(output)], capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(output.read_bytes(), b'<SUBTREE>/a\r\nrc=2\x00\xff <WORKTREE>\n')

    def test_invalid_map_refuses_without_emitting_derivative(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            raw, output, mapping = [root / name for name in ('raw', 'out', 'map')]
            raw.write_bytes(b'SYN native bytes\n')
            mapping.write_text(json.dumps({'': '<EMPTY>'}))
            result = subprocess.run([sys.executable, str(SCRIPT), '--mapping', str(mapping),
                                     '--input', str(raw), '--output', str(output)], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(output.exists())

    def test_literal_engine_does_not_rescan_inserted_replacement_bytes(self):
        spec = importlib.util.spec_from_file_location('capture_mask', SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        # Deliberately insert the second key. A sequential replacer would
        # incorrectly produce '<B> <B> untouched' instead of '/b <B> untouched'.
        self.assertEqual(module.replace_literals(b'/a /b untouched', {b'/a': b'/b', b'/b': b'<B>'}),
                         b'/b <B> untouched')
        self.assertEqual(module.mask_bytes(b'unchanged\r\n\x00\xff', {'/a': '<A>'}),
                         b'unchanged\r\n\x00\xff')

    def test_literal_engine_swaps_original_keys_in_either_mapping_order(self):
        spec = importlib.util.spec_from_file_location('capture_mask_swap', SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for values in ({b'/a': b'/b', b'/b': b'/a'},
                       {b'/b': b'/a', b'/a': b'/b'}):
            with self.subTest(order=list(values)):
                self.assertEqual(module.replace_literals(b'/a /b untouched', values),
                                 b'/b /a untouched')

    def test_declared_unpublished_build_digest_is_masked_without_summarizing_stream(self):
        spec = importlib.util.spec_from_file_location('capture_mask_digest', SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        digest = '1' * 64  # Synthetic digest, never a real artifact fingerprint.
        raw = b'Created wheel: sha256=' + digest.encode() + b'\nSuccessfully built example\n'
        self.assertEqual(module.mask_bytes(raw, {digest: '<UNPUBLISHED_BUILD_SHA256>'}),
                         b'Created wheel: sha256=<UNPUBLISHED_BUILD_SHA256>\nSuccessfully built example\n')

    def test_declared_pip_private_source_cache_key_is_masked_preserving_install_line(self):
        spec = importlib.util.spec_from_file_location('capture_mask_cache', SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        # Synthetic counterpart of ibflex-install/stdout.txt:73. pip's key is
        # sha224 over source URL/interpreter inputs, not a wheel's sha256.
        key = '2' * 56
        raw = (b'  Stored in directory: /private-syn/pip-ephem-wheel-cache/wheels/'
               b'22/22/22/' + key[6:].encode() + b'\nSuccessfully built ibflex\n')
        self.assertEqual(module.mask_bytes(raw, {
            '/private-syn': '<FOLD_SCRATCH>',
            key: '<PRIVATE_SOURCE_CACHE_KEY>',
        }), b'  Stored in directory: <FOLD_SCRATCH>/pip-ephem-wheel-cache/wheels/'
            b'<PRIVATE_SOURCE_CACHE_KEY>\nSuccessfully built ibflex\n')
        self.assertEqual(module.mask_bytes(b'key=' + key.encode() + b'\r\n\x00\xff', {
            key: '<PRIVATE_SOURCE_CACHE_KEY>',
        }), b'key=<PRIVATE_SOURCE_CACHE_KEY>\r\n\x00\xff')


if __name__ == '__main__':
    unittest.main()
