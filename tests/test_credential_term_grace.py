"""Per-caller watchdog grace on existing SYN group fixtures; no key/store reads."""
import contextlib
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
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
                     '--term-grace=630 -- python3 collect.py', '--term-grace -- python3 collect.py']
        for text in variants:
            with self.subTest(text=text):
                self.assertEqual(guard.check(prefix + text), 'credential_run_usage')

    def test_child_arguments_are_not_runner_options(self):
        from scripts.hooks import secret_path_guard as guard
        self.assertIsNone(guard.check('python3 tools/credentials/credential_run.py tavily -- python3 collect.py --term-grace=anything'))

    def test_every_other_guard_rule_is_byte_identical_to_base(self):
        import ast
        from scripts.hooks import secret_path_guard as guard
        root = Path(__file__).resolve().parents[1]
        before = subprocess.check_output(['git', '-C', str(root), 'show',
            '0f4ee075b2ab3af1b099d5ca1ecb8cae02ee3f5b:scripts/hooks/secret_path_guard.py'], text=True)
        after = Path(guard.__file__).read_text()
        def unchanged(source):
            skip = set()
            for node in ast.parse(source).body:
                allowed = isinstance(node, ast.FunctionDef) and node.name == 'k4_runner_usage_reason'
                allowed |= (isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'K4_RUNNER_OPTIONS'
                                                               for t in node.targets))
                if allowed:
                    skip.update(range(node.lineno - 1, node.end_lineno))
            return ''.join(line for i, line in enumerate(source.splitlines(keepends=True)) if i not in skip)
        self.assertTrue(unchanged(before) == unchanged(after), 'a guard rule outside the permitted grammar region changed')
        def original_usage_rules(source):
            function = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef)
                            and n.name == 'k4_runner_usage_reason')
            loop = next(n for n in function.body if isinstance(n, ast.For))
            help_check = next(n for n in loop.body if isinstance(n, ast.If))
            usage_check = next(n for n in loop.body if isinstance(n, ast.If)
                               and ast.get_source_segment(source, n.test).startswith('not arguments or'))
            lines = source.splitlines(keepends=True)
            return ''.join(lines[function.lineno - 1:help_check.end_lineno] + lines[usage_check.lineno - 1:function.end_lineno])
        self.assertTrue(original_usage_rules(before) == original_usage_rules(after),
                        'an existing rule inside runner-usage grammar changed')

    def test_option_parity_adds_exactly_the_one_opt_in_flag(self):
        import ast
        import inspect
        from scripts.hooks import secret_path_guard as guard
        options = {node.value for node in ast.walk(ast.parse(inspect.getsource(runner.parse_args)))
                   if isinstance(node, ast.Constant) and isinstance(node.value, str)
                   and node.value.startswith('-') and ' ' not in node.value}
        self.assertEqual(options, {'--only', '--check', '-h', '--help', '--', '--term-grace'})
        self.assertEqual(guard.K4_RUNNER_OPTIONS, options)

    def test_credential_policy_and_watchdog_program_are_byte_identical(self):
        import ast
        root = Path(__file__).resolve().parents[1]
        before = subprocess.check_output(['git', '-C', str(root), 'show',
            '0f4ee075b2ab3af1b099d5ca1ecb8cae02ee3f5b:tools/credentials/credential_run.py'], text=True)
        after = Path(runner.__file__).read_text()
        changed = {'Watchdog', 'parse_args', 'term_grace_seconds', 'run_command', '_main'}
        def nodes(source):
            result = {}
            for node in ast.parse(source).body:
                name = getattr(node, 'name', None)
                if isinstance(node, ast.Assign):
                    name = next((target.id for target in node.targets if isinstance(target, ast.Name)), None)
                if name is not None and name not in changed and name != 'USAGE':
                    result[name] = ast.get_source_segment(source, node)
            return result
        old, new = nodes(before), nodes(after)
        self.assertEqual(set(old), set(new))
        self.assertFalse([name for name in old if old[name] != new[name]], 'credential policy or watchdog code changed')
        # Within _main, only the option unpack/dispatch can differ. All store
        # lookup, parsing, must_not_be_set, child scrubbing and masking remain.
        def loading(source):
            node = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == '_main')
            skip = set()
            for part in node.body:
                if isinstance(part, ast.Assign) and any(isinstance(t, ast.Tuple) for t in part.targets):
                    skip.update(range(part.lineno - 1, part.end_lineno))
                if isinstance(part, ast.If) and any(isinstance(n, ast.Name) and n.id == 'term_grace' for n in ast.walk(part.test)):
                    skip.update(range(part.lineno - 1, part.end_lineno))
            return ''.join(line for i, line in enumerate(source.splitlines(keepends=True))
                           if node.lineno - 1 <= i < node.end_lineno and i not in skip)
        self.assertTrue(loading(before) == loading(after), 'credential loading/dispatch changed outside option routing')


if __name__ == '__main__':
    unittest.main()
