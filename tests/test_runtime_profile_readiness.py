"""Prepare/launch/collection readiness contracts from #1033's open threads."""
import argparse
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/adoption"))
import runtime_profiles as profiles


class RuntimeReadinessTests(unittest.TestCase):
    def test_default_prepare_creates_every_descriptor_required_by_native_launchers(self):
        with tempfile.TemporaryDirectory(dir="/var/tmp") as temporary:
            state = Path(temporary)
            args = ['prepare','--state-root',str(state),'--home',str(state),'--eco-root',str(state),
                    '--mcp-template','fixture.json','--pi-bin','/fixture/pi','--opencode-bin','/fixture/opencode',
                    '--rtk-source',str(state)]
            def render(profile, **kwargs):
                root = state / profile
                if kwargs['role_scope']:
                    root = root / 'roles' / kwargs['role_scope']
                root.mkdir(parents=True)
                (root / 'profile.json').write_text('{"status":"trial"}')
                return {}
            with mock.patch.object(profiles,'render',side_effect=render),redirect_stdout(io.StringIO()):
                self.assertEqual(profiles.main(args),0)
            for profile in profiles.PROFILES:
                for role, scope in [('isolated-builder','builder'),('evidence-reviewer','reviewer'),
                                    ('security-reviewer','auditor'),('stack-researcher','researcher')]:
                    with self.subTest(profile=profile,role=role):
                        launch = profiles.parser().parse_args(['launch',profile,'--state-root',str(state),
                                                              '--repository',str(state),'--role',role])
                        self.assertTrue((launch.state_root/profile/'roles'/scope/'profile.json').is_file())

    def test_absent_wrong_and_correct_runtime_versions_are_checked_without_native_user_state(self):
        with tempfile.TemporaryDirectory(dir="/var/tmp") as temporary:
            root = Path(temporary)
            for runtime, expected in [('pi','1.1.0'),('opencode','1.18.35')]:
                with self.subTest(runtime=runtime):
                    absent = root/runtime
                    with self.assertRaises(profiles.ProfileError):
                        profiles.verify_runtime_binary(runtime, absent)
                    absent.write_text('#!/bin/sh\nprintf "wrong-version\\n"\n'); absent.chmod(0o700)
                    with self.assertRaises(profiles.ProfileError):
                        profiles.verify_runtime_binary(runtime, absent)
                    absent.write_text('#!/bin/sh\nprintf "'+expected+'\\n"\n')
                    self.assertEqual(profiles.verify_runtime_binary(runtime, absent),expected)

    def test_installed_public_runtime_versions_match_the_qualified_releases(self):
        import os
        supplied={'pi':os.environ.get('NS_PI_TEST_BIN'),'opencode':os.environ.get('NS_OPENCODE_TEST_BIN')}
        if not all(supplied.values()):self.skipTest('explicit installed public binary paths required')
        self.assertEqual(profiles.verify_runtime_binary('pi',Path(supplied['pi'])),'1.1.0')
        self.assertEqual(profiles.verify_runtime_binary('opencode',Path(supplied['opencode'])),'1.18.35')

    def test_changed_runtime_binding_refuses_launch_before_creating_worktree(self):
        with tempfile.TemporaryDirectory(dir="/var/tmp") as temporary:
            state=Path(temporary);root=state/'opencode-gpt/roles/builder';root.mkdir(parents=True)
            binary=state/'opencode';binary.write_text('#!/bin/sh\nprintf "wrong-version\\n"\n');binary.chmod(0o700)
            (root/'profile.json').write_text(json.dumps({'status':'trial','model':'fixture','effort':'high',
                'opencode_bin':str(binary),'roles':{'isolated-builder':{'tools':[]}}}))
            args=argparse.Namespace(profile='opencode-gpt',state_root=state,repository=state,
                                    role='isolated-builder',print=False,prompt=None)
            with mock.patch.object(profiles,'fresh_worktree') as fresh:
                with self.assertRaises(profiles.ProfileError):profiles.launch(args)
                fresh.assert_not_called()

    def test_nonexistent_binary_is_refused_before_renderer_writes_trial_state(self):
        with tempfile.TemporaryDirectory(dir='/var/tmp') as temporary:
            root=Path(temporary)
            with self.assertRaises(profiles.ProfileError):
                profiles.render('opencode-gpt',state=root,home=root,eco_root=root,templates=[],
                    pi_bin=root/'missing-pi',opencode_bin=root/'missing-opencode',rtk_source=root)
            self.assertFalse((root/'opencode-gpt').exists())

    def test_dependency_directory_ancestors_of_home_are_refused(self):
        with tempfile.TemporaryDirectory(dir='/var/tmp') as temporary:
            base=Path(temporary);home=base/'home';home.mkdir()
            root=home/'profile';workspace=base/'workspace';root.mkdir();workspace.mkdir()
            config=root/'config/opencode/opencode.json';config.parent.mkdir(parents=True)
            config.write_text('{"agent":{}}')
            for dependency in (home,home/'.local',base):
                dependency.mkdir(exist_ok=True)
                with self.subTest(dependency=dependency.name),mock.patch.object(Path,'home',return_value=home):
                    with self.assertRaisesRegex(profiles.ProfileError,'unqualified broad dependency'):
                        profiles.opencode_filesystem_roots(root,workspace,
                            {'opencode_bin':'/usr/bin/true','qualified_auxiliary_read_paths':[str(dependency)]},None)

    def test_interactive_collection_errors_are_failed_measurements_with_retry_state(self):
        for failure, code in [('listing',7),('export',8)]:
            with self.subTest(failure=failure),tempfile.TemporaryDirectory(dir='/var/tmp') as temporary:
                state=Path(temporary);root=state/'opencode-gpt/roles/builder';root.mkdir(parents=True)
                workspace=state/'workspace';workspace.mkdir()
                (root/'profile.json').write_text(json.dumps({'status':'trial','model':'fixture','effort':'high',
                    'opencode_bin':'/fixture/opencode','roles':{'isolated-builder':{'tools':[]}}}))
                config=root/'config/opencode/opencode.json';config.parent.mkdir(parents=True);config.write_text('{"agent":{}}')
                args=argparse.Namespace(profile='opencode-gpt',state_root=state,repository=state,
                                       role='isolated-builder',print=False,prompt=None)
                def run(command,**kwargs):
                    if command[:3]==['/fixture/opencode','session','list']:
                        kwargs['stdout'].write(json.dumps([{'id':'fixture','directory':str(workspace)}]))
                        return subprocess.CompletedProcess(command,code if failure=='listing' else 0)
                    if command[:2]==['/fixture/opencode','export']:
                        return subprocess.CompletedProcess(command,code)
                    return subprocess.CompletedProcess(command,0)
                with mock.patch.object(profiles,'fresh_worktree',return_value=workspace), \
                        mock.patch.object(profiles,'verify_runtime_binary',return_value='1.18.35',create=True), \
                        mock.patch.object(profiles,'opencode_sandbox_command',side_effect=lambda command,*a:command), \
                        mock.patch.object(profiles,'cleanup_worktree') as cleanup, \
                        mock.patch.object(profiles.subprocess,'run',side_effect=run),redirect_stdout(io.StringIO()):
                    self.assertEqual(profiles.launch(args),code)
                    cleanup.assert_not_called()
                measurement=json.loads(next(root.glob('runs/*/invocations.json')).read_text())
                self.assertFalse(measurement['measured'])
                self.assertEqual(measurement['status'],'collection_failed')
                receipt=json.loads(next(root.glob('runs/*/collection-receipt.json')).read_text())
                self.assertEqual(receipt['exit_code'],code)
                self.assertTrue(workspace.is_dir())


if __name__=='__main__':unittest.main()
