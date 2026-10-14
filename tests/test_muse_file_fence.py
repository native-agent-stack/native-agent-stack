"""Model-free OS boundary regressions; no real credential or network request."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from tools.muse_file_fence import (Fence, sanitized_settings, clean_env, native_argv,
                                  probe, DEFAULT_LANE, VERSION)


class MuseFenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='muse-file-fence-test-', dir='/var/tmp')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.work = self.root / 'work'
        self.logs = self.root / 'logs'
        self.work.mkdir()
        self.logs.mkdir()
        for name in ('tmp', 'data', 'state', 'cache'):
            (self.logs / name).mkdir()
        self.brief = self.root / 'brief.md'
        self.brief.write_text('A harmless probe.\n')
        self.auth = self.root / 'synthetic-sign-in.json'
        self.auth.write_text('{}\n')
        self.settings = self.root / 'settings.json'
        self.settings.write_text(json.dumps({
            'schema_version': 1, 'mcpServers': {'bad': {'command': '/bin/false'}},
            'mcp_servers': {'bad': {'command': '/bin/false'}},
            'hooks': {'SessionStart': [{'command': '/bin/false'}]},
            'managed_hooks_path': '/outside/hooks.json', 'plugins': ['outside'],
            'managed_plugins_path': '/outside/plugins',
            'contributor_mode_enabled': True, 'unknown_future_plugin': '/bad',
            'contributor_mode_disclosure_acknowledged': True}))
        self.runtime = Path('/usr/bin/python3').resolve()
        self.fence = Fence(self.work, self.brief, self.logs, self.runtime,
                           self.auth, self.settings)

    def run_fenced(self, script):
        with self.fence.prepared() as command:
            return subprocess.run(command + [str(self.runtime), '-I', '-c', script],
                                  env={}, capture_output=True, text=True, timeout=30)

    @unittest.skipUnless(shutil.which('bwrap'), 'bubblewrap not installed')
    def test_unfenced_canary_read_fenced_denial(self):
        """FAIL-FIRST: same payload reads the planted host file without bwrap."""
        canary = self.root / 'outside-worktree-canary'
        canary.write_text('PUBLIC SYNTHETIC CANARY\n')
        script = 'from pathlib import Path; Path(' + repr(str(canary)) + ').read_bytes()'
        before = subprocess.run([str(self.runtime), '-I', '-c', script], capture_output=True)
        self.assertEqual(before.returncode, 0, 'unfenced positive control must read canary')
        after = self.run_fenced(script)
        self.assertNotEqual(after.returncode, 0, 'fence must deny the identical read')
        self.assertIn('FileNotFoundError', after.stderr)

    @unittest.skipUnless(shutil.which('bwrap'), 'bubblewrap not installed')
    def test_named_masks_and_only_declared_writes(self):
        home = str(Path.home())
        # Test existence/read attempts only, never inspect real secret content.
        masks = {n: str(Path(home) / n) for n in (
            '.ssh', '.codex', '.claude', '.hcom', '.local/state', 'code',
            '.local/state/native-agent-stack/coordination/ns2604-coop',
            '.local/state/native-agent-stack/coordination/command-center')}
        masks.update({'host-run-user': '/run/user', 'windows-mounts': '/mnt',
                      'other-var-tmp': str(self.root), 'staging-siblings': str(self.settings)})
        script = f'''
import json, os
from pathlib import Path
out = {{}}
for name, path in {masks!r}.items():
    p = Path(path)
    if name == 'other-var-tmp':
        out[name] = sorted(x.name for x in p.iterdir()) == ['brief.md', 'logs', 'work']
    else:
        out[name] = not p.exists()
for name, path in {{'worktree-rw': {str(self.work)!r}, 'log-rw': {str(self.logs)!r}}}.items():
    p = Path(path) / 'write-marker'; p.write_text('public'); out[name] = p.read_text() == 'public'
out['brief-ro'] = not os.access({str(self.brief)!r}, os.W_OK)
out['runtime-ro'] = not os.access({str(self.runtime)!r}, os.W_OK)
out['auth-ro'] = not os.access({str(Path.home()/'.config/muse/auth.json')!r}, os.W_OK)
out['settings-ro'] = not os.access({str(Path.home()/'.config/muse/settings.json')!r}, os.W_OK)
out['project-muse-empty-ro'] = not list(Path({str(self.work/'.muse')!r}).iterdir()) and not os.access({str(self.work/'.muse')!r}, os.W_OK)
for name, path in {{'home-ro': {home!r}, 'root-ro': '/', 'etc-ro': '/etc'}}.items():
    try:
        (Path(path) / 'muse-file-fence-no-write').write_text('public'); out[name] = False
    except OSError:
        out[name] = True
out['environment-clean'] = 'META_API_KEY' not in os.environ and 'MUSE_PERMISSION_PROFILE_FAIL_OPEN' not in os.environ
print(json.dumps(out))
'''
        result = self.run_fenced(script)
        self.assertEqual(result.returncode, 0, result.stderr)
        facts = json.loads(result.stdout)
        self.assertTrue(all(facts.values()), facts)
        self.assertTrue((self.work / 'write-marker').exists())
        self.assertTrue((self.logs / 'write-marker').exists())

    def test_sanitizer_allowlists_inert_preferences(self):
        self.assertEqual(sanitized_settings(self.settings), {
            'schema_version': 1, 'contributor_mode_enabled': False,
            'contributor_mode_disclosure_acknowledged': True})

    def test_symlink_config_mount_refused(self):
        (self.work / '.muse').symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(ValueError), self.fence.prepared():
            pass

    def test_credential_or_runtime_overlap_refused(self):
        for path in (self.work / 'auth.json', self.logs / 'auth.json'):
            path.write_text('{}')
            with self.assertRaises(ValueError):
                Fence(self.work, self.brief, self.logs, self.runtime, path)

    def test_symlink_dependency_refused(self):
        link = self.root / 'alias'
        link.symlink_to(self.brief)
        with self.assertRaises(ValueError):
            Fence(self.work, link, self.logs, self.runtime, self.auth)

    def test_protected_home_input_refused(self):
        # The actual contents of the chosen existing protected config are not read.
        with self.assertRaises(ValueError):
            Fence(self.work, self.brief, self.logs, self.runtime, self.auth,
                  inputs=[Path.home()/'.config/muse/settings.json'])

    def test_environment_does_not_forward_injection(self):
        env = clean_env(Path.home(), self.logs)
        for name in ('META_API_KEY', 'LD_PRELOAD', 'PYTHONPATH', 'MUSE_AUTH_PATH',
                     'MUSE_TRANSPORT_TRACE', 'MUSE_PERMISSION_PROFILE_FAIL_OPEN',
                     'HTTP_PROXY', 'CODEX_HOME', 'XDG_CONFIG_HOME'):
            self.assertNotIn(name, env)

    @unittest.skipUnless(os.environ.get('MUSE_FENCE_NATIVE_PROBE') == '1',
                         'explicit installed-client model-free integration')
    def test_native_echo_cannot_start_extensions(self):
        runtime = Path.home() / f'.local/bin/muse-bin-{VERSION}'
        def hooks(marker):
            return {'SessionStart': [{'hooks': [{'type': 'command', 'command':
                '/usr/bin/touch ' + str(self.logs / marker)}]}]}
        doc = {'schema_version': 1, 'hooks': hooks('user-hook-fired'),
               'managed_hooks_path': str(self.root / 'managed-hooks.json'),
               'mcpServers': {'fence-probe': {'transport': 'stdio',
                   'command': '/bin/sh', 'args': ['-c', '/usr/bin/touch ' +
                                                str(self.logs / 'mcp-fired') + '; exit 0'],
                   'enabled': True, 'mode': 'optional'}}}
        self.settings.write_text(json.dumps(doc))
        (self.root / 'managed-hooks.json').write_text(json.dumps({'hooks': hooks('managed-hook-fired')}))
        (self.work / '.muse').mkdir()
        (self.work / '.muse/hooks.json').write_text(json.dumps({'hooks': hooks('project-hook-fired')}))
        argv = native_argv(DEFAULT_LANE, runtime, self.work, self.brief, self.logs, 'reader', 2)
        # Positive control: native startup sees the planted executable config.
        control_home = self.root / 'control-home'
        config = control_home / '.config/muse'
        config.mkdir(parents=True)
        shutil.copyfile(self.settings, config / 'settings.json')
        echo_argv = list(argv)
        for flag in ('--model', '--reasoning-effort'):
            index = echo_argv.index(flag); del echo_argv[index:index+2]
        before = subprocess.run(echo_argv + ['--provider', 'echo', '--disable-reminders'],
                                env=clean_env(control_home, self.logs), cwd=self.work,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(before.returncode, 0, before.stderr)
        for name in ('mcp-fired', 'user-hook-fired', 'project-hook-fired', 'managed-hook-fired'):
            marker = self.logs / name
            self.assertTrue(marker.exists(), name + ' control absent: ' + before.stderr)
            marker.unlink()
        fence = Fence(self.work, self.brief, self.logs, runtime, self.auth, self.settings)
        with fence.prepared() as command:
            try:
                result = probe(fence, command, argv)
            except ValueError:
                self.fail((self.logs / 'fence-probe.json').read_text() +
                          (self.logs / 'probe-echo.stderr.log').read_text())
        self.assertTrue(result['pass'], result)

    @unittest.skipUnless(os.environ.get('MUSE_FENCE_NATIVE_PROBE') == '1',
                         'explicit installed launcher model-free integration')
    def test_unfenced_launcher_canary_read_fenced_denial(self):
        canary = self.root / 'outside-worktree-canary'
        canary.write_text('public synthetic planted file')
        shim = self.root / 'muse-probe-runtime'
        shim.write_text('''#!/usr/bin/python3
import json, sys
from pathlib import Path
if '--version' in sys.argv:
 print('synthetic model-free read probe'); raise SystemExit(0)
try:
 Path(''' + repr(str(canary)) + ''').read_bytes(); readable = True
except FileNotFoundError:
 readable = False
print(json.dumps({'outside_readable': readable}))
''')
        shim.chmod(0o700)
        env = {**clean_env(Path.home(), self.logs), 'MUSE_BIN': str(shim)}
        unfenced_logs = self.root / 'unfenced-logs'
        before = subprocess.run(['/bin/bash', str(DEFAULT_LANE), '--role', 'reader',
                                 str(self.work), str(self.brief), str(unfenced_logs)],
                                env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual(before.returncode, 0, before.stderr)
        self.assertEqual(json.loads((unfenced_logs / 'muse-exec.jsonl').read_text()),
                         {'outside_readable': True})
        argv = native_argv(DEFAULT_LANE, shim, self.work, self.brief, self.logs, 'reader', 2)
        fence = Fence(self.work, self.brief, self.logs, shim, self.auth, self.settings)
        with fence.prepared() as command:
            after = subprocess.run(command + argv, env={}, capture_output=True, text=True, timeout=30)
        self.assertEqual(after.returncode, 0, after.stderr)
        self.assertEqual(json.loads(after.stdout), {'outside_readable': False})


if __name__ == '__main__':
    unittest.main()
