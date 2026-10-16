"""Preregistered native-role boundary checks; no Meta model request.

The loopback case characterizes the existing shared network. A passing
characterization test is not a hostile-network qualification.
"""
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import unittest

from tools.muse_file_fence import (
    DEFAULT_LANE, DEFAULT_RUNTIME, VERSION, Fence, clean_env, native_argv,
    probe, verify_runtime_identity,
)


@unittest.skipUnless(shutil.which('bwrap'), 'bubblewrap not installed')
class MuseNativeRoleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='muse-native-roles-', dir='/var/tmp')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / 'source'
        self.source.mkdir()
        self.git('init', '--quiet', '--initial-branch=main', str(self.source))
        (self.source / 'fixture.py').write_text('VALUE = 1\n')
        self.git('-C', str(self.source), 'add', 'fixture.py')
        self.git('-C', str(self.source), '-c', 'user.name=Native Muse fixture',
                 '-c', 'user.email=native-muse-fixture@users.noreply.github.com',
                 'commit', '--quiet', '-m', 'Synthetic qualification fixture')
        self.brief = self.root / 'brief.md'
        self.brief.write_text('Offline native-role qualification.\n')
        self.input = self.root / 'supplied-input.txt'
        self.input.write_text('Public synthetic input.\n')
        self.auth = self.root / 'synthetic-sign-in.json'
        self.auth.write_text('{}\n')
        self.settings = self.root / 'synthetic-settings.json'
        self.settings.write_text('{"schema_version": 1}\n')
        self.python = Path('/usr/bin/python3').resolve()

    def git(self, *args):
        return subprocess.run(['git', '-c', 'core.hooksPath=/dev/null', *args],
                              check=True, capture_output=True, text=True, timeout=20)

    def fixture(self, role, runtime=None):
        work = self.root / (role + '-clone')
        self.git('clone', '--quiet', '--no-local', str(self.source), str(work))
        logs = self.root / (role + '-logs')
        logs.mkdir()
        for name in ('tmp', 'data', 'state', 'cache'):
            (logs / name).mkdir()
        fence = Fence(work, self.brief, logs, runtime or self.python,
                      self.auth, self.settings, inputs=[self.input])
        return work, logs, fence

    def fenced_python(self, fence, payload):
        with fence.prepared() as command:
            return subprocess.run(command + [str(self.python), '-I', '-c', payload],
                                  env={}, capture_output=True, text=True, timeout=20)

    def test_external_file_and_workspace_symlink_denied(self):
        canary = self.root / 'public-outside-canary'
        canary.write_text('Public qualification canary.\n')
        payload = 'from pathlib import Path; print(Path(' + repr(str(canary)) + ').read_text())'
        control = subprocess.run([str(self.python), '-I', '-c', payload],
                                 capture_output=True, text=True, timeout=20)
        self.assertEqual(control.returncode, 0, control.stderr)
        for role in ('builder', 'reviewer'):
            with self.subTest(role=role):
                work, _, fence = self.fixture(role)
                (work / 'outside-link').symlink_to(canary)
                paths = [str(canary), str(work / 'outside-link')]
                result = self.fenced_python(fence, f'''
import json
from pathlib import Path
facts = {{}}
for path in {paths!r}:
    try:
        Path(path).read_bytes()
    except FileNotFoundError:
        facts[path] = True
    else:
        facts[path] = False
print(json.dumps(facts))
''')
                self.assertEqual(result.returncode, 0, result.stderr)
                facts = json.loads(result.stdout)
                self.assertEqual(set(facts), set(paths))
                self.assertTrue(all(facts.values()), facts)
        self.assertEqual(canary.read_text(), 'Public qualification canary.\n')

    def test_shell_payload_respects_declared_writes_and_metadata(self):
        for role in ('builder', 'reviewer'):
            with self.subTest(role=role):
                work, logs, fence = self.fixture(role)
                original_head = (work / '.git/HEAD').read_bytes()
                denied = {'git': work / '.git/HEAD', 'brief': self.brief,
                          'input': self.input,
                          'synthetic-sign-in': Path.home() / '.config/muse/auth.json'}
                payload = f'''
import errno, json, os
from pathlib import Path
facts = {{}}
for name, path in {dict((k, str(v)) for k, v in denied.items())!r}.items():
    try:
        fd = os.open(path, os.O_WRONLY | os.O_APPEND)
    except OSError as exc:
        facts[name + '-readonly'] = exc.errno in (errno.EROFS, errno.EACCES)
    else:
        os.close(fd)
        facts[name + '-readonly'] = False
for name, path in {{'worktree': {str(work)!r}, 'logs': {str(logs)!r}}}.items():
    marker = Path(path) / 'owned-public-marker'
    marker.write_text('public')
    facts[name + '-writable'] = marker.read_text() == 'public'
print(json.dumps(facts))
'''
                result = self.fenced_python(fence, payload)
                self.assertEqual(result.returncode, 0, result.stderr)
                facts = json.loads(result.stdout)
                self.assertTrue(all(facts.values()), facts)
                self.assertEqual((work / '.git/HEAD').read_bytes(), original_head)
        self.assertEqual(self.auth.read_text(), '{}\n')  # Synthetic fixture only.
        self.assertEqual(self.input.read_text(), 'Public synthetic input.\n')

    def test_shared_network_reaches_owned_loopback(self):
        """Acceptance gap: an owned listener remains reachable with this policy."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(('127.0.0.1', 0))
            listener.listen(3)
            listener.settimeout(3)
            address = listener.getsockname()
            payload = ('import socket; '
                       's = socket.create_connection(' + repr(address) + ', timeout=2); '
                       "s.sendall(b'PUBLIC-QUALIFICATION-MARKER'); s.close()")
            control = subprocess.run([str(self.python), '-I', '-c', payload],
                                     capture_output=True, text=True, timeout=10)
            self.assertEqual(control.returncode, 0, control.stderr)
            with listener.accept()[0] as connection:
                self.assertEqual(connection.recv(64), b'PUBLIC-QUALIFICATION-MARKER')
            for role in ('builder', 'reviewer'):
                with self.subTest(role=role):
                    _, _, fence = self.fixture(role)
                    result = self.fenced_python(fence, payload)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    with listener.accept()[0] as connection:
                        self.assertEqual(connection.recv(64), b'PUBLIC-QUALIFICATION-MARKER')

    def test_host_process_is_not_visible_in_fenced_proc(self):
        # Only this test process's public PID is inspected. No process command
        # lines, environments or unrelated host process details are read.
        host_pid = os.getpid()
        self.assertTrue(Path('/proc', str(host_pid)).is_dir())
        for role in ('builder', 'reviewer'):
            with self.subTest(role=role):
                _, _, fence = self.fixture(role)
                payload = ('import json; from pathlib import Path; print(json.dumps('
                           + "{'host-test-process-hidden': not Path('/proc', "
                           + repr(str(host_pid)) + ').exists()}))')
                result = self.fenced_python(fence, payload)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout), {'host-test-process-hidden': True})

    @unittest.skipUnless(os.environ.get('MUSE_FENCE_NATIVE_PROBE') == '1',
                         'explicit installed-client offline integration')
    def test_native_role_echo_cannot_start_extensions(self):
        runtime = DEFAULT_RUNTIME
        verify_runtime_identity(runtime)
        for role in ('builder', 'reviewer'):
            with self.subTest(role=role):
                work, logs, fence = self.fixture(role, runtime)
                def hooks(marker):
                    return {'SessionStart': [{'hooks': [{'type': 'command', 'command':
                        '/usr/bin/touch ' + str(logs / marker)}]}]}
                self.settings.write_text(json.dumps({
                    'schema_version': 1, 'hooks': hooks('user-hook-fired'),
                    'managed_hooks_path': str(self.root / 'managed-hooks.json'),
                    'mcpServers': {'role-probe': {'transport': 'stdio', 'command': '/bin/sh',
                        'args': ['-c', '/usr/bin/touch ' + str(logs / 'mcp-fired') + '; exit 0'],
                        'enabled': True, 'mode': 'optional'}}}))
                (self.root / 'managed-hooks.json').write_text(
                    json.dumps({'hooks': hooks('managed-hook-fired')}))
                (work / '.muse').mkdir()
                (work / '.muse/hooks.json').write_text(
                    json.dumps({'hooks': hooks('project-hook-fired')}))
                argv = native_argv(DEFAULT_LANE, runtime, work, self.brief, logs, role, 2)
                self.assertIn('--disable-web-tools', argv)
                self.assertEqual(argv[argv.index('--contributor-mode') + 1], 'off')
                self.assertEqual(argv[argv.index('--reasoning-effort') + 1], 'max')
                if role == 'builder':
                    self.assertEqual(argv[argv.index('--approval-mode') + 1], 'never')
                else:
                    self.assertEqual(argv[argv.index('--permission-profile') + 1], ':read-only')
                echo = list(argv)
                for flag in ('--model', '--reasoning-effort'):
                    index = echo.index(flag)
                    del echo[index:index + 2]
                echo += ['--provider', 'echo', '--disable-reminders']
                control_home = self.root / (role + '-control-home')
                config = control_home / '.config/muse'
                config.mkdir(parents=True)
                shutil.copyfile(self.settings, config / 'settings.json')
                control = subprocess.run(echo, env=clean_env(control_home, logs), cwd=work,
                                         capture_output=True, text=True, timeout=45)
                self.assertEqual(control.returncode, 0, control.stderr)
                for name in ('mcp-fired', 'user-hook-fired', 'project-hook-fired', 'managed-hook-fired'):
                    marker = logs / name
                    self.assertTrue(marker.exists(), role + ' positive control missing: ' + name)
                    marker.unlink()
                with fence.prepared() as command:
                    version = subprocess.run(command + [str(runtime), '--version'], env={},
                        capture_output=True, text=True, check=True, timeout=20)
                    self.assertIn('(' + VERSION + ')', version.stdout)
                    receipt = probe(fence, command, argv)
                self.assertTrue(receipt['pass'], receipt)
                self.assertEqual(receipt['echo']['exit_code'], 0)
                self.assertEqual(receipt['echo']['terminal_counts'].get('run.terminal.completed'), 1)
                print(json.dumps({'native_role': role, 'model_request': False,
                    'probe_checks': len(receipt['checks']), 'probe_pass': receipt['pass'],
                    'echo': receipt['echo'], 'version': version.stdout.strip()}))


if __name__ == '__main__':
    unittest.main()
