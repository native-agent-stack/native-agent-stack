"""CC ruling-f1-meta-fence-dirbind-20261015.md items 1-4, model-free."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

from tools import muse_file_fence as fence_module


class MuseToolchainDirectoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='muse-toolchain-test-', dir='/var/tmp')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.work = self.root / 'work'
        self.log = self.root / 'logs'
        self.toolchain = self.root / 'toolchain/version'
        for path in (self.work, self.log, self.toolchain):
            path.mkdir(parents=True)
        for name in ('tmp', 'data', 'state', 'cache'):
            (self.log / name).mkdir()
        self.brief = self.root / 'brief.md'
        self.brief.write_text('Public synthetic model-free fixture.\n')
        self.auth = self.root / 'synthetic-auth.json'
        self.auth.write_text('{}\n')
        self.runtime = Path('/usr/bin/python3').resolve()

    def fence(self, directories):
        return fence_module.Fence(self.work, self.brief, self.log,
                                  self.runtime, self.auth, toolchain_dirs=directories)

    def refusal(self):
        return getattr(fence_module, 'ToolchainDirectoryRefused', ValueError)

    def test_outside_explicit_allowlist_refused(self):
        with self.assertRaises(self.refusal()):
            self.fence([self.toolchain])

    def test_symlink_components_refused(self):
        alias = self.root / 'alias'
        alias.symlink_to(self.toolchain.parent, target_is_directory=True)
        for path in (alias / self.toolchain.name, self.toolchain / 'back' / '..'):
            with self.subTest(path=path):
                if path.name == '..':
                    (self.toolchain / 'back').symlink_to(self.toolchain, target_is_directory=True)
                with mock.patch.object(fence_module, 'TOOLCHAIN_DIRECTORY_ALLOWLIST', {path}):
                    with self.assertRaises(self.refusal()):
                        self.fence([path])

    def test_symlink_entry_refuses_entire_root(self):
        (self.toolchain / 'nested').symlink_to(self.root, target_is_directory=True)
        with mock.patch.object(fence_module, 'TOOLCHAIN_DIRECTORY_ALLOWLIST', {self.toolchain}):
            with self.assertRaises(self.refusal()):
                self.fence([self.toolchain])

    def test_store_root_refused_even_if_allowlisted(self):
        for name in ('.ssh', '.codex', '.config', 'state', 'credentials'):
            path = self.root / name
            path.mkdir()
            with self.subTest(name=name), mock.patch.object(
                    fence_module, 'TOOLCHAIN_DIRECTORY_ALLOWLIST', {path}):
                with self.assertRaises(self.refusal()):
                    self.fence([path])

    def test_root_containing_store_refused_without_reading_contents(self):
        for name in ('.ssh', '.aws', '.azure', '.gnupg', '.kube', '.codex',
                     '.claude', '.hcom', '.config', '.local', '.cache', '.git',
                     '.muse', 'sessions', 'state', 'auth.json', 'credentials',
                     'credentials.json', '.netrc', '.npmrc', '.git-credentials'):
            with self.subTest(name=name):
                marker = self.toolchain / name
                marker.touch(mode=0)
                try:
                    with mock.patch.object(fence_module, 'TOOLCHAIN_DIRECTORY_ALLOWLIST', {self.toolchain}):
                        with self.assertRaises(self.refusal()):
                            self.fence([self.toolchain])
                finally:
                    marker.unlink()

    def test_root_inside_store_refused(self):
        with mock.patch.object(Path, 'home', return_value=self.root):
            path = self.root / '.local/state/toolchain/version'
            path.mkdir(parents=True)
            with mock.patch.object(fence_module, 'TOOLCHAIN_DIRECTORY_ALLOWLIST', {path}):
                with self.assertRaises(self.refusal()):
                    self.fence([path])

    def test_root_containing_named_auth_or_settings_refused(self):
        for attribute in ('auth', 'settings'):
            path = self.toolchain / 'opaque-file'
            path.touch()
            with self.subTest(attribute=attribute):
                kwargs = {attribute: path}
                with mock.patch.object(fence_module, 'TOOLCHAIN_DIRECTORY_ALLOWLIST', {self.toolchain}):
                    with self.assertRaises(self.refusal()):
                        fence_module.Fence(self.work, self.brief, self.log, self.runtime,
                                          kwargs.get('auth', self.auth),
                                          kwargs.get('settings'), toolchain_dirs=[self.toolchain])

    def test_root_beneath_store_outside_home_refused(self):
        path = self.root / '.ssh/toolchain/version'
        path.mkdir(parents=True)
        with mock.patch.object(fence_module, 'TOOLCHAIN_DIRECTORY_ALLOWLIST', {path}):
            with self.assertRaises(self.refusal()):
                self.fence([path])

    def test_writable_overlap_refused_in_both_directions(self):
        for writable in ('work', 'log'):
            for relation in ('equal', 'writable-child', 'toolchain-child'):
                with self.subTest(writable=writable, relation=relation):
                    writable_path = self.toolchain
                    directory = self.toolchain
                    if relation == 'writable-child':
                        writable_path /= 'writable'
                    elif relation == 'toolchain-child':
                        directory /= 'child'
                    writable_path.mkdir(exist_ok=True)
                    directory.mkdir(exist_ok=True)
                    with mock.patch.object(self, writable, writable_path), mock.patch.object(
                            fence_module, 'TOOLCHAIN_DIRECTORY_ALLOWLIST', {directory}):
                        with self.assertRaises(self.refusal()):
                            self.fence([directory])

    def test_policy_revalidated_before_artifact_creation(self):
        with mock.patch.object(fence_module, 'TOOLCHAIN_DIRECTORY_ALLOWLIST', {self.toolchain}):
            fence = self.fence([self.toolchain])
            (self.toolchain / '.ssh').mkdir()
            with self.assertRaises(self.refusal()):
                with fence.prepared():
                    self.fail('policy must refuse before preparation')
            self.assertEqual(sorted(p.name for p in self.log.iterdir()),
                             ['cache', 'data', 'state', 'tmp'])

    def toolchain_readonly_control(self, directory, expected_version):
        fence = self.fence([directory, directory])
        script = f'''
import errno, json, tempfile
from pathlib import Path
root = Path({str(directory)!r})
result = {{'version': (root / 'VERSION').read_text().splitlines()[0]}}
try:
    with tempfile.NamedTemporaryFile(dir=root, prefix='.muse-toolchain-ro-probe-'):
        result['read-only'] = False
except OSError as exc:
    result['read-only'] = exc.errno in (errno.EROFS, errno.EACCES)
print(json.dumps(result))
'''
        before = set(directory.iterdir())
        with fence.prepared() as command:
            # The final mount plan has one named root, and no writable child.
            grants = [command[i + 1:i + 3] for i, arg in enumerate(command) if arg == '--ro-bind']
            self.assertEqual(grants.count([str(directory), str(directory)]), 1)
            for i, arg in enumerate(command):
                if arg == '--bind':
                    self.assertTrue(fence_module.disjoint(directory, Path(command[i + 2])))
            result = subprocess.run(command + [str(self.runtime), '-I', '-c', script],
                                    env={}, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout),
                             {'version': expected_version, 'read-only': True})
            if directory == next(iter(fence_module.TOOLCHAIN_DIRECTORY_ALLOWLIST)) and expected_version == 'go1.25.12':
                version = subprocess.run(command + [str(directory / 'bin/go'), 'version'],
                                         env={}, capture_output=True, text=True, timeout=30)
                self.assertEqual(version.returncode, 0, version.stderr)
                self.assertIn('go version go1.25.12 ', version.stdout)
        self.assertEqual(set(directory.iterdir()), before)

    @unittest.skipUnless(shutil.which('bwrap'), 'bubblewrap not installed')
    def test_synthetic_toolchain_readonly_positive_control(self):
        (self.toolchain / 'VERSION').write_text('synthetic-toolchain-1\n')
        with mock.patch.object(fence_module, 'TOOLCHAIN_DIRECTORY_ALLOWLIST', {self.toolchain}):
            self.toolchain_readonly_control(self.toolchain, 'synthetic-toolchain-1')

    @unittest.skipUnless(os.environ.get('MUSE_FENCE_TOOLCHAIN_PROBE') == '1',
                         'explicit installed toolchain OS probe')
    def test_installed_go_readonly_positive_control(self):
        self.toolchain_readonly_control(
            Path.home() / '.local/share/mise/installs/go/1.25.12', 'go1.25.12')

    @unittest.skipUnless(os.environ.get('MUSE_FENCE_NATIVE_PROBE') == '1'
                         and os.environ.get('MUSE_FENCE_TOOLCHAIN_PROBE') == '1',
                         'explicit installed-client and toolchain model-free probe')
    def test_native_echo_probe_with_installed_toolchain(self):
        directory = Path.home() / '.local/share/mise/installs/go/1.25.12'
        runtime = Path.home() / f'.local/bin/muse-bin-{fence_module.VERSION}'
        fence = fence_module.Fence(self.work, self.brief, self.log, runtime,
                                   self.auth, toolchain_dirs=[directory])
        argv = fence_module.native_argv(fence_module.DEFAULT_LANE, runtime,
                                       self.work, self.brief, self.log, 'reader', 2)
        with fence.prepared() as command:
            result = fence_module.probe(fence, command, argv)
        self.assertTrue(result['pass'], result)
        self.assertTrue(result['checks']['toolchain-ro:' + str(directory)])


if __name__ == '__main__':
    unittest.main()
