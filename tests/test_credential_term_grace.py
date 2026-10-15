"""Per-caller watchdog grace on existing SYN group fixtures; no key/store reads."""
import contextlib
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import types
import unittest
from unittest import mock
from tests import test_credential_run as fixtures

runner = fixtures.run_mod


class TermGrace(unittest.TestCase):
    setUp = fixtures.WatchdogTests.setUp
    cleanup = fixtures.WatchdogTests.cleanup

    def group(self, code):
        # Reuse the existing group fixture with an empty child environment.
        native_popen = subprocess.Popen
        def empty_environment(*args, **kwargs):
            return native_popen(*args, **dict(kwargs, env={}))
        with mock.patch.object(subprocess, 'Popen', side_effect=empty_environment):
            return fixtures.WatchdogTests.group(self, code)

    def ready(self, path):
        deadline = time.monotonic() + 10
        while not path.exists():
            if time.monotonic() >= deadline:
                self.fail('SYN child did not arm its handler')
            time.sleep(0.005)

    def watchdog(self, pid, *, grace=None):
        try:
            value = runner.Watchdog(pid) if grace is None else runner.Watchdog(pid, term_grace=grace)
        except TypeError:
            self.fail('watchdog has no per-caller TERM grace')
        self.assertIsNotNone(value.process)
        self.processes.append(value.process)
        self.addCleanup(value.close_pipe)
        return value

    def test_opt_in_handler_finishes_after_term_without_being_killed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            code = ('import signal,time\nfrom pathlib import Path\nroot=Path(' + repr(str(root)) + ')\n'
                    'def finish(*args):\n (root/"term").write_text("SYN TERM")\n time.sleep(0.08)\n'
                    ' (root/"finished").write_text("SYN recovered")\n raise SystemExit(0)\n'
                    'signal.signal(signal.SIGTERM,finish)\n(root/"ready").write_text("SYN ready")\ntime.sleep(60)\n')
            child = self.group(code)
            self.ready(root / 'ready')
            dog = self.watchdog(child.pid, grace=1)
            dog.close_pipe()
            self.assertEqual(child.wait(timeout=10), 0)
            self.assertTrue((root / 'term').exists())
            self.assertTrue((root / 'finished').exists())
            self.assertEqual(dog.process.wait(timeout=10), 1)

    def test_opt_in_ignoring_child_is_killed_only_after_grace(self):
        with tempfile.TemporaryDirectory() as directory:
            ready = Path(directory) / 'ready'
            child = self.group('import signal,time\nfrom pathlib import Path\n'
                               'signal.signal(signal.SIGTERM,signal.SIG_IGN)\n'
                               'Path(' + repr(str(ready)) + ').write_text("SYN ready")\ntime.sleep(60)\n')
            self.ready(ready)
            dog = self.watchdog(child.pid, grace=1)
            # A watchdog silently using the default 2.0 must fail this test,
            # even though its later KILL would satisfy the lower time bound.
            self.assertEqual(dog.process.args[-1], '1')
            started = time.monotonic()
            dog.close_pipe()
            self.assertEqual(child.wait(timeout=10), -signal.SIGKILL)
            self.assertGreaterEqual(time.monotonic() - started, 1)
            self.assertEqual(dog.process.wait(timeout=10), 1)

    def test_no_flag_keeps_existing_default_watchdog_argv_and_grace(self):
        with tempfile.TemporaryDirectory() as directory:
            ready = Path(directory) / 'ready'
            child = self.group('import signal,time\nfrom pathlib import Path\n'
                               'signal.signal(signal.SIGTERM,signal.SIG_IGN)\n'
                               'Path(' + repr(str(ready)) + ').write_text("SYN ready")\ntime.sleep(60)\n')
            self.ready(ready)
            dog = self.watchdog(child.pid)
            self.assertEqual(dog.process.args[-1], str(runner.TERM_GRACE_SECONDS))
            self.assertEqual(runner.TERM_GRACE_SECONDS, 2.0)
            started = time.monotonic()
            dog.close_pipe()
            self.assertEqual(child.wait(timeout=10), -signal.SIGKILL)
            self.assertGreaterEqual(time.monotonic() - started, runner.TERM_GRACE_SECONDS)
            self.assertEqual(dog.process.wait(timeout=10), 1)

    def test_successful_release_still_signals_nothing_with_override(self):
        child = self.group('import time\ntime.sleep(60)\n')
        dog = self.watchdog(child.pid, grace=630)
        dog.release()
        self.assertEqual(dog.process.returncode, 0)
        self.assertIsNone(child.poll())

    def test_cli_parses_override_without_loading_any_inventory(self):
        with mock.patch.object(runner, 'load_inventory', side_effect=AssertionError('no inventory reads')):
            for value in ('1', '630', '3600'):
                parsed = runner.parse_args(['tavily', '--term-grace', value, '--', 'SYN-command'])
                self.assertEqual(parsed[:4], ('tavily', [], False, ['SYN-command']))
                self.assertEqual(parsed[4], int(value))
        default = runner.parse_args(['tavily', '--', 'SYN-command'])
        self.assertIsNone(default[4])

    def test_cli_rejects_unsafe_graces_without_echoing_arguments(self):
        for value in ('0', '-1', '0.5', 'nan', 'inf', '1e999', '3601', 'SYN-not-a-number'):
            with self.subTest(value=value), self.assertRaises(runner.UsageError) as caught:
                runner.parse_args(['tavily', '--term-grace', value, '--', 'SYN-command'])
            self.assertEqual(str(caught.exception), '--term-grace needs an integer from 1 to 3600')
        for argv in (['tavily', '--term-grace'], ['tavily', '--term-grace', '1', '--term-grace', '2', '--', 'SYN'],
                     ['tavily', '--term-grace', '630', '--check']):
            with self.subTest(argv=argv), self.assertRaises(runner.UsageError):
                runner.parse_args(argv)

    def test_api_routes_opt_in_to_only_its_own_watchdog(self):
        for signum in (*runner.FORWARDED, signal.SIGCHLD):
            self.addCleanup(signal.signal, signum, signal.getsignal(signum))
        native = runner.Watchdog
        created = []
        def watch(pid, **kwargs):
            created.append(kwargs)
            return native(pid, **kwargs)
        try:
            with mock.patch.object(runner, 'Watchdog', side_effect=watch):
                self.assertEqual(runner.run_command([sys.executable, '-I', '-c', 'pass'], {}, [], term_grace=630), 0)
                self.assertEqual(runner.run_command([sys.executable, '-I', '-c', 'pass'], {}, []), 0)
        except TypeError:
            self.fail('per-caller grace is not routed through the native process API')
        self.assertEqual(created, [{'term_grace': 630}, {}])


class GuardTermGrace(unittest.TestCase):
    def test_only_separate_bounded_integer_form_is_accepted(self):
        from scripts.hooks import secret_path_guard as guard
        prefix = 'python3 tools/credentials/credential_run.py tavily '
        for value in ('1', '630', '3600'):
            with self.subTest(value=value):
                self.assertIsNone(guard.check(prefix + '--term-grace ' + value + ' -- python3 collect.py'))

    def test_bad_grace_grammar_is_refused(self):
        from scripts.hooks import secret_path_guard as guard
        prefix = 'python3 tools/credentials/credential_run.py tavily '
        variants = ['--term-grace ' + value + ' -- python3 collect.py'
                    for value in ('0', '-1', '3601', '1.5', 'nan', 'SYN-invalid')]
        variants += ['--term-grace 1 --term-grace 2 -- python3 collect.py',
                     '--term-grace=630 -- python3 collect.py', '--term-grace -- python3 collect.py',
                     '--term-grace 630 --check', '--term-grace 630 python3 collect.py']
        for text in variants:
            with self.subTest(text=text):
                self.assertEqual(guard.check(prefix + text), 'credential_run_usage')
        self.assertEqual(guard.check('python3 tools/credentials/credential_run.py --term-grace 630 -- python3 collect.py'),
                         'credential_run_usage')

    def test_child_arguments_are_not_runner_options(self):
        from scripts.hooks import secret_path_guard as guard
        self.assertIsNone(guard.check('python3 tools/credentials/credential_run.py tavily -- python3 collect.py --term-grace=anything'))

    def test_existing_guard_rules_keep_their_behavior(self):
        from scripts.hooks import secret_path_guard as guard
        from tests.test_secret_path_guard import K4_CASES
        # Reuse the established command-text fixtures. Assert decisions rather
        # than freezing unrelated source, comments, imports or future rules.
        groups = ('runner_start_and_inline_order', 'runner_environment_and_mentions',
                  'runner_usage_and_documentation')
        for group in groups:
            for text, reason in K4_CASES[group]:
                with self.subTest(group=group, text=text):
                    self.assertEqual(guard.check(text), reason)

    def test_option_parity_adds_exactly_the_one_opt_in_flag(self):
        import ast
        import inspect
        from scripts.hooks import secret_path_guard as guard
        options = {node.value for node in ast.walk(ast.parse(inspect.getsource(runner.parse_args)))
                   if isinstance(node, ast.Constant) and isinstance(node.value, str)
                   and node.value.startswith('-') and ' ' not in node.value}
        self.assertEqual(options, {'--only', '--check', '-h', '--help', '--', '--term-grace'})
        self.assertEqual(guard.K4_RUNNER_OPTIONS, options)

class CredentialPolicyCompatibility(unittest.TestCase):
    @staticmethod
    def pinned_baseline():
        # A historical source is a fixed control, never an equality constraint
        # on today's file. As in test_workflow_hardening's baseline control,
        # run the contract against it instead of comparing source bytes.
        root = Path(__file__).resolve().parents[1]
        source = subprocess.check_output(['git', '-C', str(root), 'show',
            '0f4ee075b2ab3af1b099d5ca1ecb8cae02ee3f5b:tools/credentials/credential_run.py'], text=True)
        module = types.ModuleType('credential_grace_baseline')
        module.__file__ = str(root / 'tools/credentials/credential_run.py')
        with mock.patch.dict(sys.modules, {module.__name__: module}):
            exec(compile(source, module.__file__, 'exec'), module.__dict__)
        return module

    def policy_contract(self, module):
        # Only synthetic values from the existing fixture; no inventory/store
        # read, environment lookup or credential output is involved.
        value = fixtures.fake()
        entry = {'id': 'syn-entry', 'variables': ['SYN_SELECTED'], 'optional_variables': [],
                 'pointer_variables': ['SYN_POINTER']}
        other = {'variables': ['SYN_OTHER'], 'optional_variables': ['SYN_OPTIONAL'],
                 'pointer_variables': ['SYN_OTHER_POINTER']}
        inventory = {'must_not_be_set': ['SYN_FORBIDDEN'], 'entries': [entry, other]}
        data = ('export SYN_SELECTED=' + value + '\n').encode('ascii')
        values = module.parse('syn-entry', data, entry)
        self.assertTrue(values == {'SYN_SELECTED': value}, 'declared synthetic value must parse without expansion')
        module.require(entry, values)
        with self.assertRaises(module.Refused):
            module.require(entry, {})
        inherited = dict.fromkeys(('SYN_SELECTED', 'SYN_OTHER', 'SYN_OPTIONAL', 'SYN_FORBIDDEN',
                                   'SYN_POINTER', 'SYN_OTHER_POINTER', 'SYN_KEEP'), 'SYN inherited')
        environment = module.child_environment(inventory, entry, values, inherited)
        self.assertTrue(environment == {'SYN_SELECTED': value, 'SYN_POINTER': 'SYN inherited',
                                       'SYN_KEEP': 'SYN inherited'}, 'strip other names, forbidden names and pointers')
        masker = module.Masker(module.needles_for(values, ['SYN_SELECTED']))
        output = masker.feed(value.encode('ascii') + b'\n', time.monotonic()) + masker.close()
        self.assertNotIn(value.encode('ascii'), output)
        self.assertIn(b'[REDACTED:SYN_SELECTED]', output)

    def test_credential_policy_preserves_synthetic_contract(self):
        self.policy_contract(runner)

    def test_pinned_base_satisfies_synthetic_policy_contract(self):
        self.policy_contract(self.pinned_baseline())


if __name__ == '__main__':
    unittest.main()
