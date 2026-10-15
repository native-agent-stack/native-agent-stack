"""SYN launcher acceptance and child lifecycle; no credentials/broker/units."""
from contextlib import nullcontext
import importlib.util
import json
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'blueprints/us-equities/paper-readiness-seq3'


def launcher(root):
    module = types.ModuleType('r3_launcher_fixture')
    module.__file__ = str(root / 'launch.py')
    exec(compile((ROOT / 'tests/fixtures/seq2-launch.txt').read_text(), module.__file__, 'exec'), module.__dict__)
    module.ROOT, module.FROZEN, module.STATE = root, root / 'frozen', root / 'state'
    module.STATE.mkdir()
    module.verify_bundle = module.verify_runtime = lambda: None
    module.writer = nullcontext
    module.credential_pointer = lambda: Path('/SYN/no-credential.env')
    return module


class Acceptance(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.launch = launcher(self.root)
        self.instance = self.root / 'state/instances/syn-trial'
        self.instance.mkdir(parents=True)
        self.value = {'instance': str(self.instance), 'state_root': str(self.instance / 'native-state'),
                      'trial': 'syn-trial'}
        self.launch.binding = lambda stage: self.value
        self.native_status = 'recovery_only'
        self.native_rc = 0
        self.calls = []
        self.launch.keyed = self.keyed

    def keyed(self, command, *, timeout, environment=None):
        argv = list(map(str, command))
        self.calls.append((argv, timeout))
        if '--output' in argv:
            output = Path(argv[argv.index('--output') + 1])
        else:
            output = Path(environment['OUT_DIR']) / 'paper-output.json'
            output.parent.mkdir(parents=True)
        self.launch.save(output, {'status': self.native_status, 'recovery_status': 'passed', 'started_as': 'paper'})
        return self.native_rc

    def test_pre_recovery_only_exit_zero_is_refused_as_trial(self):
        with self.assertRaisesRegex(self.launch.Refused, 'recovery_only'):
            self.launch.run_stage('pre')
        receipt = self.launch.safe_json(self.instance / 'recovery-run.json')
        self.assertEqual(receipt['status'], 'recovery_only')
        self.assertIs(receipt['trial_evidence'], False)
        self.assertEqual(receipt['native_exit_code'], 0)
        self.assertFalse((self.launch.STATE / 'completed').exists())

    def test_scheduled_recovery_only_exit_zero_is_refused_as_trial(self):
        with self.assertRaisesRegex(self.launch.Refused, 'recovery_only'):
            self.launch.run_stage('sip')
        self.assertIs(self.launch.safe_json(self.instance / 'recovery-run.json')['trial_evidence'], False)

    def test_passed_trial_is_still_accepted(self):
        self.native_status = 'passed'
        for stage in ('pre', 'sip'):
            with self.subTest(stage=stage):
                self.assertEqual(self.launch.run_stage(stage), 0)
        self.assertFalse((self.instance / 'recovery-run.json').exists())

    def test_nonzero_exit_remains_nonzero(self):
        self.native_status, self.native_rc = 'needs_attention', 3
        self.assertEqual(self.launch.run_stage('pre'), 3)


class KillBudget(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.launch = launcher(self.root)

    def ready_child(self, native_popen):
        def spawn(*args, **kwargs):
            child = native_popen(*args, **kwargs)
            deadline = time.monotonic() + 10
            while not (self.root / 'ready').exists():
                if child.poll() is not None or time.monotonic() >= deadline:
                    child.kill()
                    child.wait()
                    self.fail('SYN child did not reach its signal-blocked handshake')
                time.sleep(0.005)
            return child
        return spawn

    def test_timeout_allows_late_armed_child_to_finish_recovery(self):
        loader = self.launch.FROZEN / 'tools/credentials/credential_run.py'
        loader.parent.mkdir(parents=True)
        # Fake credential-run child: TERM is blocked before the handler is
        # armed, matching the r3 exec handoff. No real credential loader runs.
        loader.write_text('''import signal,sys,time
from pathlib import Path
root=Path(sys.argv[-1])
signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM})
(root/'ready').write_text('SYN ready')
time.sleep(0.3)
signal.signal(signal.SIGTERM, lambda *args: (root/'term-seen').write_text('SYN TERM'))
signal.pthread_sigmask(signal.SIG_UNBLOCK, {signal.SIGTERM})
time.sleep(0.05)
(root/'recovery-finished').write_text('SYN flat')
''')
        try:
            with patch.object(self.launch.subprocess, 'Popen', side_effect=self.ready_child(subprocess.Popen)):
                rc = self.launch.keyed(['SYN-late-arm', self.root], timeout=0.2)
        except subprocess.TimeoutExpired:
            self.fail('timeout killed the child before its recovery handler was armed')
        self.assertNotEqual(rc, 0, 'a timed-out trial cannot become accepted trial evidence')
        self.assertTrue((self.root / 'ready').exists())
        self.assertTrue((self.root / 'term-seen').exists())
        self.assertTrue((self.root / 'recovery-finished').exists())

    def test_kill_only_follows_term_and_full_630_second_grace(self):
        events = []
        class Child:
            returncode = -signal.SIGKILL
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def wait(self, timeout=None):
                events.append(('wait', timeout))
                if timeout is not None:
                    raise subprocess.TimeoutExpired('SYN child', timeout)
                return self.returncode
            def terminate(self): events.append(('TERM',))
            def kill(self): events.append(('KILL',))
            def communicate(self, input=None, timeout=None):
                self.wait(timeout)
                return None, None
        with patch.object(self.launch.subprocess, 'Popen', return_value=Child()):
            try:
                rc = self.launch.keyed(['SYN-stubborn'], timeout=1190)
            except subprocess.TimeoutExpired:
                self.fail('SIGKILL preceded the recovery grace')
        self.assertNotEqual(rc, 0)
        self.assertEqual(events[:4], [('wait', 1190), ('TERM',), ('wait', 630), ('KILL',)])

    def test_native_loader_keeps_scheduled_recovery_group_alive(self):
        loader = self.launch.FROZEN / 'tools/credentials/credential_run.py'
        loader.parent.mkdir(parents=True)
        native_loader = ROOT / 'tools/credentials/credential_run.py'
        # Exercise only the maintained process relay API with empty SYN env,
        # never its credential inventory or command-line credential loader.
        loader.write_text('import runpy,sys\napi=runpy.run_path(' + repr(str(native_loader)) +
                          ')\nraise SystemExit(api["run_command"](sys.argv[sys.argv.index("--")+1:], {}, []))\n')
        child = self.root / 'late-child.py'
        child.write_text('''import signal,sys,time
from pathlib import Path
root=Path(sys.argv[1])
signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM})
(root/'ready').write_text('SYN ready')
time.sleep(2.5)
signal.signal(signal.SIGTERM, lambda *args: (root/'term-seen').write_text('SYN TERM'))
signal.pthread_sigmask(signal.SIG_UNBLOCK, {signal.SIGTERM})
(root/'recovery-finished').write_text('SYN flat')
''')
        script = self.root / 'scheduled.sh'
        script.write_text('"' + sys.executable + '" -I -B "' + str(child) + '" "' + str(self.root) + '"\n')
        # The exact production scheduler wrapper comes from the launcher.
        recorded = []
        actual_keyed = self.launch.keyed
        self.launch.binding = lambda stage: {'instance': str(self.root), 'state_root': str(self.root / 'native'), 'trial': 'syn'}
        def record(command, **kwargs):
            recorded.append(command)
            return 3
        with patch.object(self.launch, 'keyed', side_effect=record):
            self.launch.run_stage('sip')
        command = list(recorded[0])
        command[-1] = script
        try:
            with patch.object(self.launch.subprocess, 'Popen', side_effect=self.ready_child(subprocess.Popen)):
                rc = actual_keyed(command, timeout=0.7)
        except subprocess.TimeoutExpired:
            self.fail('launcher killed the native credential relay during recovery')
        self.assertEqual(rc, 124)
        self.assertTrue((self.root / 'ready').exists())
        self.assertTrue((self.root / 'term-seen').exists())
        self.assertTrue((self.root / 'recovery-finished').exists())


if __name__ == '__main__':
    unittest.main()
