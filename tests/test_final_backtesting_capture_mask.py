"""Synthetic masking fixtures only; these are not E2E/invoke receipts."""
import gzip
import hashlib
import importlib.util
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET
import subprocess
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
RULE = ROOT / "evidence/artifacts/final-wave-backtesting-engine-20261016/mask_capture.py"


def load_mask():
    spec = importlib.util.spec_from_file_location("final_backtesting_mask", RULE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class NativeCaptureMaskTests(unittest.TestCase):
    def test_declared_host_spec_fields_are_masked_without_losing_results(self):
        raw = (b'CPU architecture: fixture-cpu\r\nCPU(s): 7 @ 19 MHz\r\n'
               b'OS: fixture-os\r\nRAM-Total: 23.5 GiB\r\nSwap-Used: 11.25 GiB\r\n'
               b'Data elements: 0\r\nTotal orders: 0\r\nCOMMAND_EXIT_CODE="0"\r\n')
        masked = load_mask().mask_bytes(raw, hostname='fixture-host')
        self.assertNotIn(b'fixture-cpu', masked)
        self.assertNotIn(b'fixture-os', masked)
        self.assertNotIn(b'23.5', masked)
        self.assertNotIn(b'11.25', masked)
        self.assertEqual(5, masked.count(b'[HOST_SPEC]'))
        self.assertEqual(raw.count(b'\r\n'), masked.count(b'\r\n'))
        self.assertIn(b'Data elements: 0\r\nTotal orders: 0\r\n', masked)
        self.assertIn(b'COMMAND_EXIT_CODE="0"', masked)

    def test_hostname_is_required_instead_of_implicit_host_discovery(self):
        with self.assertRaises(TypeError):
            load_mask().mask_bytes(b'fixture text')

    def test_mask_bytes_tolerates_unrelated_live_dependency_edits(self):
        module = load_mask()
        original_read = Path.read_bytes
        def changed_dependency(path):
            raw = original_read(path)
            if path == ROOT / 'scripts/validate.py':
                return raw + b'\n# unrelated synthetic main edit\n'
            return raw
        with mock.patch.object(Path, 'read_bytes', changed_dependency):
            self.assertEqual(b'47 passed\r\n', module.mask_bytes(
                b'47 passed\r\n', hostname='fixture-host'))

    def test_host_mask_preserves_assertion_diagnostics(self):
        raw = b"AssertionError: b'CPU(s): 7 @ 19 MHz\\r\\nTotal orders: 0'\n"
        self.assertEqual(raw, load_mask().mask_bytes(raw, hostname='fixture-host'))

    def test_cli_rejects_unpinned_source_before_publishing(self):
        module = load_mask()
        with tempfile.TemporaryDirectory(prefix='mask-cli-guard-') as directory:
            directory = Path(directory)
            raw, out, context = (directory / name for name in ['raw', 'out', 'context'])
            raw.write_bytes(b'47 passed\r\n')
            context.write_text(json.dumps({'hostname': 'fixture-host', 'home': '', 'username': ''}))
            with mock.patch.object(module, 'SANITIZER_SHA256', '0' * 64):
                with self.assertRaisesRegex(ValueError, 'sanitizer source'):
                    module.main(['--raw', str(raw), '--raw-name', 'fixture',
                                 '--out', str(out), '--context', str(context)])
            self.assertFalse(out.exists())

    def test_publication_contains_the_masking_rule(self):
        self.assertTrue(RULE.is_file(), "Published native derivatives require the reproducible rule")

    def test_masks_only_declared_identity_fields_preserving_observation(self):
        synthetic_uuid = '-'.join(['12345678', '1234', '1234', '1234', '123456789abc'])
        raw = ('Script started: COMMAND="run /private/fixture"\r\n'
               '47 passed in 3.31s\r\n'
               'GIL failure; total=0; PID: 12345\r\n'
               f'fixture-host event={synthetic_uuid}\r\n'
               'raw_digest=' + 'a' * 64 + '\r\n'
               'Script done: COMMAND_EXIT_CODE="7"\r\n').encode()
        result = load_mask().mask_bytes(raw, [("/private/fixture", "<PREFIX>")],
                                 hostname="fixture-host")
        self.assertIn(b'COMMAND="run <PREFIX>"\r\n', result)
        self.assertIn(b'47 passed in 3.31s\r\n', result)
        self.assertIn(b'GIL failure; total=0;', result)
        self.assertIn(b'COMMAND_EXIT_CODE="7"\r\n', result)
        self.assertEqual(raw.count(b'\r\n'), result.count(b'\r\n'))
        for private in [b'/private/fixture', b'fixture-host', b'12345', b'a' * 64]:
            self.assertNotIn(private, result)

    def test_untouched_native_bytes_are_not_summarized_or_truncated(self):
        raw = b'first\r\n' + b'x' * 20000 + b'\r\nlast\r\n'
        self.assertEqual(raw, load_mask().mask_bytes(raw, hostname="fixture-host"))

    def test_empty_mapping_refuses(self):
        with self.assertRaises(ValueError):
            load_mask().mask_bytes(b'actual output', [("", "invented")], hostname='fixture-host')

    def test_native_xml_counter_capture_stays_parseable_after_identity_mask(self):
        raw = b'<run computerName="fixture-host"><Counters executed="0" passed="0"/></run>'
        masked = load_mask().mask_bytes(raw, hostname="fixture-host")
        root = ET.fromstring(masked)
        self.assertEqual({'executed': '0', 'passed': '0'}, root.find('Counters').attrib)

    def test_published_native_bytes_survive_git_eol_filters(self):
        with tempfile.TemporaryDirectory(prefix="native-eol-fixture-") as directory:
            directory = Path(directory)
            def git(*args):
                return subprocess.check_output(['git', '-C', str(directory), *args],
                                               stderr=subprocess.DEVNULL)
            git('init', '-q')
            git('config', 'core.autocrlf', 'true')
            attributes = RULE.parent / 'native/.gitattributes'
            (directory / '.gitattributes').write_bytes(attributes.read_bytes())
            native = b'47 passed\r\nCOMMAND_EXIT_CODE="0"\r\n'
            (directory / 'fixture.capture').write_bytes(native)
            git('add', '--', '.gitattributes', 'fixture.capture')
            self.assertEqual(native, git('show', ':fixture.capture'))

    def test_cli_hashes_only_deterministic_published_bytes_and_keeps_raw(self):
        with tempfile.TemporaryDirectory(prefix="mask-fixture-") as directory:
            directory = Path(directory)
            raw = directory / 'raw.capture'
            raw.write_bytes(b'2 passed\r\nCOMMAND_EXIT_CODE="0"\r\n')
            before = raw.read_bytes()
            out = directory / 'masked.capture.gz'
            context = directory / 'context.json'
            context.write_text(json.dumps({'hostname': 'fixture-host', 'home': '', 'username': ''}))
            args = ['--raw', str(raw), '--raw-name', 'fixture.capture', '--out', str(out),
                    '--context', str(context)]
            captured = io.StringIO()
            module = load_mask()
            # This fixture exercises output encoding/hashing. The real CLI
            # provenance refusal is independently checked above; ordinary CI
            # must allow later unrelated edits to the helper dependencies.
            with mock.patch.object(module, 'verify_sanitizer_sources'), contextlib.redirect_stdout(captured):
                module.main(args)
            first = out.read_bytes()
            metadata = json.loads(captured.getvalue())
            self.assertEqual(hashlib.sha256(first).hexdigest(), metadata['published_sha256'])
            self.assertEqual('masked_derivative_of_native_capture', metadata['representation'])
            with mock.patch.object(module, 'verify_sanitizer_sources'), contextlib.redirect_stdout(io.StringIO()):
                module.main(args)
            self.assertEqual(first, out.read_bytes())
            self.assertEqual(before, raw.read_bytes())
            self.assertEqual(before, gzip.decompress(first))
