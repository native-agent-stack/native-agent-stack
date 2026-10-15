"""Public F2 packet regressions for Astra full1 findings 1–3/local v4 1–3.

Protocol source: native-agent-stack@252babe4040e39173cc178317c67699371806df6,
scripts/final_stack.py:706-721,818-829. Shell mechanism: Bash 5.2 manual,
3.6 Redirections, 3.2.5.3 Grouping Commands and 3.3 Shell Functions;
Python 3.13 shlex documents lexical analysis rather than execution evidence.
"""
from contextlib import redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / 'evidence/artifacts/finalize-f2-codex-20261014'


def adapter():
    spec = importlib.util.spec_from_file_location('f2_adapter_control', PACKET / 'measure_cli.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FinalizeF2CorrectionsTests(unittest.TestCase):
    def test_astra_1_name_only_installation_provenance_in_free_text(self):
        source = (PACKET / 'build_packet.py').read_text()
        receipt = json.loads((PACKET / 'receipts/invoke-serena.json').read_text())
        for text in (source, receipt['pin_binding']):
            # A free-text binding does not escape the public-byte-only rule.
            # Never print a finding value or its prefix in an assertion.
            private_provenance = 'uv-receipt' in text and re.search(r'receipt SHA256\s+[0-9a-f]{64}', text)
            self.assertFalse(bool(private_provenance), 'cited finding 1 provenance must be name-only')

    def test_astra_2_local_1_builder_uses_actual_public_inputs(self):
        counts = json.loads((PACKET / 'native-cli-counts.json').read_text())
        self.assertNotIn('sample_ids', counts)
        result = subprocess.run([sys.executable, '-B', str(PACKET / 'build_packet.py')],
                                cwd=ROOT, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, 'public builder must complete without private samples')
        output = json.loads(result.stdout.removeprefix('ARTIFACTS_JSON:'))
        decisions = json.loads(output['winner-decisions.json'])
        self.assertEqual(len(decisions), 57)
        self.assertEqual({row['id'] for row in decisions},
                         set(json.loads((PACKET / 'input-provenance.json').read_text())['winners']))
        for row in decisions:
            value = json.loads(output[row['path']])
            self.assertEqual((PACKET / row['path']).read_text(), output[row['path']],
                             'published output must match the reproducible artifact map')
            self.assertNotIn('sample_ids', value)
            if row['path'].startswith('receipts/'):
                self.assertGreater(value['calls'], 0)
            else:
                self.assertTrue(value['not_invoked_reason'].strip())

    def test_local_2_validator_runs_without_git_history_or_checkout_scripts(self):
        with tempfile.TemporaryDirectory(prefix='f2-check-') as tmp:
            target = Path(tmp) / 'evidence/artifacts/packet'
            shutil.copytree(PACKET, target, ignore=shutil.ignore_patterns('__pycache__'))
            environment = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1',
                           'GIT_DIR': str(Path(tmp) / 'no-git-objects')}
            result = subprocess.run([sys.executable, '-B', str(target / 'check_receipts.py')],
                                    cwd=tmp, env=environment, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, 'retained validator must not need coordination refs')
            summary = json.loads(result.stdout)
            self.assertEqual(summary['failures'], [])
            self.assertTrue(summary['receipts'])

    def test_astra_3_redirection_failure_is_not_a_cli_invocation(self):
        module = adapter()
        with tempfile.TemporaryDirectory(prefix='f2-shell-') as tmp:
            root = Path(tmp); marker = root / 'started'; program = root / 'rtk'
            program.write_text('#!/bin/sh\ntouch "' + str(marker) + '"\n')
            program.chmod(0o700)
            command = str(program) + ' --version > ' + str(root / 'missing/output') + ' || true'
            shell = subprocess.run(['bash', '-c', command], capture_output=True, text=True)
            self.assertEqual(shell.returncode, 0)
            self.assertFalse(marker.exists())
            session = root / 'sessions'; session.mkdir()
            meta = {'id': 'control-owner', 'cli_version': 'control'}
            rows = [{'timestamp': '2026-10-14T12:00:00Z', 'type': 'session_meta', 'payload': meta},
                    {'timestamp': '2026-10-14T12:00:01Z', 'type': 'event_msg',
                     'payload': {'type': 'item_completed', 'item': {'type': 'CommandExecution',
                         'id': 'control-command', 'command': ['bash', '-c', command], 'exit_code': 0}}}]
            (session / 'rollout-control.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))
            stdout = io.StringIO()
            with mock.patch.object(module.counter, 'registry', return_value=({'control-owner': {'lane': 'control'}}, {}, {})), \
                 mock.patch.object(module.counter, 'discover', return_value=[session]), \
                 mock.patch.object(module.counter, 'source_class', return_value='default_native'), redirect_stdout(stdout):
                module.main()
            measured = json.loads(stdout.getvalue())
            self.assertEqual(measured['cli_counts'].get('rtk', 0), 0)
            self.assertEqual(measured.get('unvalidated_cli_prefix_matches', {}).get('rtk', 0), 0)

    def test_local_3_compact_functions_are_not_invocations(self):
        module = adapter()
        for command in ['rtk (){ :; }', 'rtk(){ :; }', 'rtk () { :; }', 'function rtk { :; }']:
            with self.subTest(case=command):
                self.assertEqual(subprocess.run(['bash', '-c', command], capture_output=True).returncode, 0)
                self.assertEqual(module.executable(command)[0], [])

    def test_retained_literal_command_controls(self):
        module = adapter()
        controls = json.loads((PACKET / 'prefix-controls.json').read_text())
        for row in controls['vectors']:
            with self.subTest(case=row['id']):
                self.assertEqual(module.executable(row['command'])[0], row['expected_components'])


if __name__ == '__main__':
    unittest.main()
