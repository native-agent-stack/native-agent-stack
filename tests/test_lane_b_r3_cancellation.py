"""SYN cancellation/timeout boundaries; no credentials, runtime locks or units."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from tests import test_lane_b_r3_launcher as fixtures

ROOT = Path(__file__).resolve().parents[1]


class Cancellation(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.KillBudget()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root, self.launch = self.fixture.root, self.fixture.launch
        self.launch.binding = lambda stage: {'instance': str(self.root / 'instance'),
            'state_root': str(self.root / 'native-state'), 'trial': 'syn-cancel'}

    def command(self, script):
        recorded = []
        with patch.object(self.launch, 'keyed', side_effect=lambda command, **kw: recorded.append(command) or 3):
            self.launch.run_stage('sip')
        command = list(recorded[0])
        command[-1] = script
        return command

    def test_term_or_int_after_qualification_never_starts_paper(self):
        spec = importlib.util.spec_from_file_location('cancellation_r3_contract',
            ROOT / 'blueprints/us-equities/paper-lane-latch/r3_contract.py')
        contract = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(contract)
        paper = self.root / 'frozen/blueprints/us-equities/adaptive-paper'
        data = paper.parent / 'data'
        paper.mkdir(parents=True)
        data.mkdir()
        (data / 'ingest_snapshot.py').write_text('pass\n')
        (data / 'promotion_gate.py').write_text('''import os,signal
from pathlib import Path
root=Path(os.environ['SYN_EVENTS'])
(root/'qualified').write_text('SYN qualified')
os.kill(int(os.environ['SYN_SHELL_PID']),getattr(signal,os.environ['SYN_SIGNAL']))
''')
        (paper / 'runner.py').write_text('''import os
from pathlib import Path
(Path(os.environ['SYN_EVENTS'])/'paper-started').write_text('SYN started')
''')
        script = self.root / 'scheduled_trial_r3.sh'
        source = (ROOT / 'blueprints/us-equities/adaptive-paper/scheduled_trial.sh').read_text()
        script.write_text(contract.scheduler(source, self.root))
        config = self.root / 'config.json'
        config.write_text('{}\n')
        for name, expected in (('SIGTERM', 143), ('SIGINT', 130)):
            with self.subTest(signal=name):
                events = self.root / name
                events.mkdir()
                env = {'HOME': str(events / 'empty-home'), 'PATH': os.defpath,
                       'TRIAL': 'syn-cancel', 'ENV_FILE': '/SYN/not-opened.env',
                       'STATE_ROOT': str(events / 'native'), 'OUT_DIR': str(events / 'output'),
                       'CONFIG': str(config), 'PY': sys.executable, 'GATE_PY': sys.executable,
                       'SYN_EVENTS': str(events), 'SYN_SIGNAL': name}
                command = self.command(script)
                command[2] = 'export SYN_SHELL_PID=$$; ' + command[2]
                result = subprocess.run(list(map(str, command)), env=env, capture_output=True,
                                        text=True, timeout=10)
                self.assertTrue((events / 'qualified').exists())
                self.assertFalse((events / 'paper-started').exists(), 'cancelled qualification started paper')
                self.assertEqual(result.returncode, expected)

    def test_native_relay_waits_for_nested_timeout_recovery_then_starts_nothing_else(self):
        loader = self.launch.FROZEN / 'tools/credentials/credential_run.py'
        loader.parent.mkdir(parents=True)
        native = ROOT / 'tools/credentials/credential_run.py'
        loader.write_text('import runpy,sys\napi=runpy.run_path(' + repr(str(native)) +
                          ')\nraise SystemExit(api["run_command"](sys.argv[sys.argv.index("--")+1:], {}, []))\n')
        child = self.root / 'deferred.py'
        child.write_text('''import signal,sys,time
from pathlib import Path
root=Path(sys.argv[1])
signal.pthread_sigmask(signal.SIG_BLOCK,{signal.SIGTERM})
(root/'ready').write_text('SYN ready')
time.sleep(2.5)
signal.signal(signal.SIGTERM,lambda *args:(root/'term-seen').write_text('SYN TERM'))
signal.pthread_sigmask(signal.SIG_UNBLOCK,{signal.SIGTERM})
time.sleep(0.1)
(root/'recovery-finished').write_text('SYN flat')
''')
        script = self.root / 'nested.sh'
        import shlex
        child_command = shlex.join([sys.executable, '-I', '-B', str(child), str(self.root)])
        later = shlex.join([sys.executable, '-I', '-c',
                           'from pathlib import Path; Path(' + repr(str(self.root / 'later-command')) + ').touch()'])
        script.write_text('/usr/bin/timeout --kill-after=3s 1 ' + child_command + '\n' + later + '\n')
        # Native process API only, empty child env: no inventory/store access.
        budget = fixtures.KillBudget()
        budget.root = self.root
        with patch.object(self.launch.subprocess, 'Popen',
                          side_effect=budget.ready_child(subprocess.Popen)):
            rc = self.launch.keyed(self.command(script), timeout=0.4)
        self.assertEqual(rc, 124)
        self.assertTrue((self.root / 'term-seen').exists())
        self.assertTrue((self.root / 'recovery-finished').exists())
        self.assertFalse((self.root / 'later-command').exists(), 'deferred cancellation resumed the scheduler')


class TimeoutGrace(unittest.TestCase):
    def test_term_during_kill_after_wait_does_not_trigger_immediate_kill(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            child = root / 'ignore-term.py'
            child.write_text('''import signal,sys,time
from pathlib import Path
root=Path(sys.argv[1])
signal.signal(signal.SIGTERM,lambda *args:(root/'term-seen').write_text('SYN ignored TERM'))
(root/'ready').write_text('SYN ready')
time.sleep(60)
''')
            started = time.monotonic()
            process = subprocess.Popen(['/usr/bin/timeout', '-k3', '1', sys.executable,
                                        '-I', '-B', str(child), str(root)], env={},
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                       start_new_session=True)
            try:
                deadline = time.monotonic() + 10
                while not (root / 'term-seen').exists():
                    if process.poll() is not None or time.monotonic() > deadline:
                        self.fail('timeout did not reach its initial TERM/grace phase')
                    time.sleep(0.005)
                grace_started = time.monotonic()
                process.send_signal(signal.SIGTERM)
                with self.assertRaises(subprocess.TimeoutExpired):
                    process.wait(timeout=0.3)
                returncode = process.wait(timeout=10)
                self.measurement = {'returncode': returncode,
                    'elapsed_seconds': time.monotonic() - started,
                    'elapsed_after_first_term_seconds': time.monotonic() - grace_started}
                self.assertIn(returncode, (-signal.SIGKILL, 128 + signal.SIGKILL))
                self.assertGreaterEqual(self.measurement['elapsed_after_first_term_seconds'], 2.7)
                self.assertGreaterEqual(self.measurement['elapsed_seconds'], 3.8)
            finally:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait(timeout=10)


class ParsedBytes(unittest.TestCase):
    def test_recovery_receipt_hashes_the_bytes_that_were_parsed(self):
        fixture = fixtures.Acceptance()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        native_loads = json.loads
        expected = []
        def substitute_after_read(raw, *args, **kwargs):
            if isinstance(raw, bytes):
                expected.append(hashlib.sha256(raw).hexdigest())
                (fixture.instance / 'paper.json').write_text('{"status":"SYN substituted"}\n')
            return native_loads(raw, *args, **kwargs)
        with patch.object(fixture.launch.json, 'loads', side_effect=substitute_after_read):
            with self.assertRaisesRegex(fixture.launch.Refused, 'paper_start_recovery_only'):
                fixture.launch.run_stage('pre')
        self.assertEqual(len(expected), 1)
        receipt = fixture.launch.safe_json(fixture.instance / 'recovery-run.json')
        self.assertEqual(receipt['native_output_sha256'], expected[0])


if __name__ == '__main__':
    unittest.main()
