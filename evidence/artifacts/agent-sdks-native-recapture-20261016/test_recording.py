"""Recorder/masking regression tests using synthetic subprocess fixtures only.

No vendor or provider is invoked. Temporary fixture output is never native
component evidence. Reference: CPython3.13 subprocess, tempfile and unittest.
"""
import contextlib
import hashlib
import io
import json
import sys
import tempfile
import unittest
import warnings
from pathlib import Path
from unittest.mock import patch

import recorder
import record_aux
from mask_capture import masked_aux


class AuxMaskTests(unittest.TestCase):
    def test_every_root_and_nonmatching_byte_preserved(self):
        raw = b'\xff/private/run/a\r\n/private/repo/b  \n/private/check/c\x00'
        rules = [(b'/private/run', b'<RUN>'), (b'/private/repo', b'<REPO>'),
                 (b'/private/check', b'<CHECK>')]
        expected = b'\xff<RUN>/a\r\n<REPO>/b  \n<CHECK>/c\x00'
        self.assertEqual(masked_aux(raw, rules), expected)
        self.assertEqual(masked_aux(expected, rules), expected)

    def test_identity_without_roots(self):
        raw = b'full output\nwarning\r\n\x00'
        self.assertEqual(masked_aux(raw, []), raw)


class RecorderTests(unittest.TestCase):
    def test_subprocess_rc_full_bytes_and_sequence_bound_to_ledger(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            root = Path(tmp)
            cmd = [sys.executable, '-c', 'import sys; sys.stdout.buffer.write(b"fixture\\r\\n"); sys.stderr.write("warning\\n"); sys.exit(7)']
            self.assertEqual(recorder.main([tmp, 'fixture', '--', *cmd]), 7)
            self.assertEqual(recorder.main([tmp, 'second', '--', sys.executable, '-c', 'pass']), 0)
            rows = [json.loads(x) for x in (root / 'steps.jsonl').read_text().splitlines()]
            self.assertEqual([r['n'] for r in rows], [1, 2])
            raw = (root / rows[0]['log']).read_bytes()
            self.assertIn(b'fixture\r\n', raw)
            self.assertIn(b'warning\n', raw)
            self.assertEqual(hashlib.sha256(raw).hexdigest(), rows[0]['log_sha256'])
            self.assertEqual(rows[0]['exit_code'], 7)

    def test_cwd_escape_rejected_before_command(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(recorder.main([tmp, 'bad', '--cwd', '/', '--', sys.executable, '-c', 'raise RuntimeError()']), 2)
            self.assertFalse((Path(tmp) / 'steps.jsonl').exists())

    def test_usage_names_committed_script(self):
        with contextlib.redirect_stderr(io.StringIO()) as out:
            self.assertEqual(recorder.main([]), 2)
        self.assertIn('recorder.py', out.getvalue())
        self.assertNotIn('f1_step.py', out.getvalue())

    def test_missing_command_records_failure_not_success(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(recorder.main([tmp, 'missing', '--', str(Path(tmp) / 'absent')]), 127)
            row = json.loads((Path(tmp) / 'steps.jsonl').read_text())
            self.assertEqual(row['exit_code'], 127)
            self.assertIn(b'recorder: command not found:', (Path(tmp) / row['log']).read_bytes())

    def test_existing_ledger_handle_is_closed(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            with warnings.catch_warnings(record=True) as observed:
                warnings.simplefilter('always', ResourceWarning)
                for phase in ['first', 'second']:
                    self.assertEqual(recorder.main([tmp, phase, '--', sys.executable, '-c', 'pass']), 0)
            self.assertFalse([w for w in observed if issubclass(w.category, ResourceWarning)])


class AuxiliaryRecorderTests(unittest.TestCase):
    def test_output_rc_and_exact_command_retained(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            root = Path(tmp)
            cmd = [sys.executable, '-c', 'import sys; sys.stdout.buffer.write(b"aux fixture\\r\\n");sys.exit(3)']
            argv = ['record_aux.py', tmp, 'fixture', tmp, *cmd]
            with patch.object(sys, 'argv', argv):
                self.assertEqual(record_aux.main(), 3)
            row = json.loads((root / 'checks.jsonl').read_text())
            self.assertEqual(row['command'], cmd)
            self.assertEqual(row['exit_code'], 3)
            self.assertEqual((root / row['log']).read_bytes(), b'aux fixture\r\n')
            self.assertEqual(hashlib.sha256((root / row['log']).read_bytes()).hexdigest(), row['raw_sha256'])
            with patch.object(sys, 'argv', argv), self.assertRaises(FileExistsError):
                record_aux.main()
            self.assertEqual(len((root / 'checks.jsonl').read_text().splitlines()), 1)

    def test_invalid_name_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(sys, 'argv', ['record_aux.py', tmp, '../escape', tmp, sys.executable]), self.assertRaises(ValueError):
                record_aux.main()


if __name__ == '__main__':
    unittest.main()
