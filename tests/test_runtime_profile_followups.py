"""Deferred #1033 transitions, exercised with synthetic native executables."""
import argparse
from contextlib import ExitStack, redirect_stdout
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/adoption'))
import runtime_profiles as profiles
import runtime_acceptance as acceptance


class RuntimeFollowupTests(unittest.TestCase):
    def fixture(self, base, profile):
        root, workspace = base / profile, base / 'workspace'
        root.mkdir(); workspace.mkdir()
        (root / 'profile.json').write_text(json.dumps({'status': 'trial',
            'model': 'fixture', 'effort': 'high', 'roles': {},
            'pi_bin': '/fixture/pi', 'opencode_bin': '/fixture/opencode',
            'mcp_server_names': ['context-mode']}))
        config = root / 'config/opencode/opencode.json'
        config.parent.mkdir(parents=True); config.write_text('{"agent":{}}')
        return root, workspace, argparse.Namespace(profile=profile, state_root=base,
            repository=base, role=None, print=True, prompt='fixture', timeout_seconds=1)

    def test_gpt_children_and_collector_exclude_unrelated_environment(self):
        for profile in ('pi-gpt', 'opencode-gpt'):
            for headless in (True, False):
                with self.subTest(profile=profile, headless=headless), tempfile.TemporaryDirectory(dir='/var/tmp') as temp:
                    base = Path(temp)
                    root, workspace, args = self.fixture(base, profile)
                    args.print = headless
                    observed = []
                    native_run = subprocess.run
                    def child(command, **kw):
                        # A real OS child checks an entirely synthetic env.
                        measured = native_run([sys.executable, '-I', '-c',
                            "import os,json;print(json.dumps('AWS_SESSION_TOKEN' in os.environ))"],
                            env=kw['env'],capture_output=True,text=True,check=True)
                        self.assertFalse(json.loads(measured.stdout))
                        observed.append(kw['env'])
                        if 'session' in command:
                            kw['stdout'].write('[]')
                        return subprocess.CompletedProcess(command, 0)
                    with mock.patch.dict(os.environ, {'HOME':str(base), 'PATH':os.defpath,
                            'AWS_SESSION_TOKEN': 'synthetic-unrelated',
                            'OPENCODE_CONFIG_CONTENT': 'synthetic-host-override'}, clear=True), \
                            mock.patch.object(profiles, 'verify_runtime_binary'), \
                            mock.patch.object(profiles, 'fresh_worktree', return_value=workspace), \
                            mock.patch.object(profiles, 'opencode_sandbox_command', side_effect=lambda c,*a:c), \
                            mock.patch.object(profiles.subprocess, 'run', side_effect=child), \
                            mock.patch.object(profiles.subprocess, 'check_output', return_value='a'*40), \
                            mock.patch.object(profiles, 'cleanup_worktree', return_value={'status':'removed'}), \
                            redirect_stdout(io.StringIO()):
                        self.assertEqual(profiles.launch(args), 0)
                    self.assertTrue(observed)
                    for env in observed:
                        self.assertNotIn('AWS_SESSION_TOKEN', env)
                        self.assertEqual(env['CLAUDE_CONFIG_DIR'], str(root/'claude'))
                        self.assertIn('PATH', env)
                        self.assertIn('HOME', env)
                        if profile.startswith('opencode'):
                            self.assertEqual(env['OPENCODE_DB'], str(root/'data/opencode/opencode.db'))
                        else:
                            self.assertNotIn('OPENCODE_CONFIG_CONTENT', env)

    def test_discovery_excludes_unrelated_environment_on_every_route(self):
        for profile in profiles.PROFILES:
            with self.subTest(profile=profile), tempfile.TemporaryDirectory(dir='/var/tmp') as temp:
                base = Path(temp)
                root, workspace, _ = self.fixture(base, profile)
                args = argparse.Namespace(state_root=base, workspace=workspace, out=base/'out',
                    role_scope=None, tokenizer_python=Path(sys.executable))
                observed = []
                def native(command, **kw):
                    observed.append((command, kw['env']))
                    return 0, '{}'
                with mock.patch.dict(os.environ, {'HOME':str(base), 'PATH':os.defpath,
                        'AWS_SESSION_TOKEN':'synthetic-unrelated'}, clear=True), \
                        mock.patch.object(acceptance, 'choose_slot', return_value='anthropic-api-4'), \
                        mock.patch.object(acceptance, 'native', side_effect=native), \
                        mock.patch.object(acceptance, 'discovered', return_value=[]), \
                        mock.patch.object(acceptance, 'skill_integrity', return_value={'managed_pass':True}), \
                        redirect_stdout(io.StringIO()):
                    acceptance.check(args, profile)
                for command, env in observed:
                    self.assertNotIn('AWS_SESSION_TOKEN', env)
                    if 'credential_run.py' not in ' '.join(command):
                        self.assertEqual(env['CLAUDE_CONFIG_DIR'], str(root/'claude'))

    def render(self, base, binary, *, fail=None, resume=False, profile='opencode-gpt', role_scope=None):
        def effect(command, **kw):
            if fail and fail(command):
                raise subprocess.CalledProcessError(7, command)
            if command[:2] == ['npm','install']:
                self.assertNotIn('AWS_SESSION_TOKEN', kw['env'])
            return subprocess.CompletedProcess(command, 0)
        with ExitStack() as stack:
            stack.enter_context(mock.patch.object(profiles, 'canonical_servers', return_value={'context-mode':{'command':'node','args':[]}}))
            stack.enter_context(mock.patch.object(profiles.shutil, 'which', return_value='/fixture/rtk'))
            stack.enter_context(mock.patch.object(profiles.subprocess, 'check_output', side_effect=['rtk 0.51.0','e001f773f80b22b7dc4c7a79521b30e35aaef026']))
            # Keep real binary admission; only controlled install effects are stubbed.
            original = subprocess.run
            stack.enter_context(mock.patch.object(profiles.subprocess, 'run', side_effect=lambda c,**kw: original(c,**kw) if '--version' in c else effect(c,**kw)))
            kwargs = {'resume':True} if resume else {}
            return profiles.render(profile,state=base,home=base,eco_root=base,
                templates=[],pi_bin=binary,opencode_bin=binary,rtk_source=base,role_scope=role_scope,**kwargs)

    def test_pi_package_failures_stay_nonlaunchable_until_resume(self):
        for package in ('superpowers','pi-otel'):
            with self.subTest(package=package), tempfile.TemporaryDirectory(dir='/var/tmp') as temp:
                base=Path(temp);binary=base/'pi'
                binary.write_text('#!/bin/sh\nprintf "1.1.0\\n"\n');binary.chmod(0o700)
                failure=lambda c: len(c)>2 and c[1]=='install' and package in c[2]
                with self.assertRaises(subprocess.CalledProcessError):
                    self.render(base,binary,profile='pi-gpt',role_scope='reviewer',fail=failure)
                root=base/'pi-gpt/roles/reviewer'
                self.assertEqual(json.loads((root/'profile.json').read_text())['status'],'preparing')
                self.render(base,binary,profile='pi-gpt',role_scope='reviewer',resume=True)
                self.assertEqual(json.loads((root/'profile.json').read_text())['status'],'trial')

    def test_resume_refuses_unowned_or_changed_identity_without_replacing_files(self):
        with tempfile.TemporaryDirectory(dir='/var/tmp') as temp:
            base=Path(temp);binary=base/'opencode'
            binary.write_text('#!/bin/sh\nprintf "1.18.35\\n"\n');binary.chmod(0o700)
            root=base/'opencode-gpt';root.mkdir()
            descriptor=root/'profile.json';descriptor.write_text('{"status":"preparing"}')
            keep=root/'keep.txt';keep.write_text('fixture')
            before=descriptor.read_bytes()
            with self.assertRaises(profiles.ProfileError):self.render(base,binary,resume=True)
            self.assertEqual(descriptor.read_bytes(),before)
            self.assertEqual(keep.read_text(),'fixture')

    def test_failed_prepare_is_not_launchable_and_explicit_resume_preserves_extra_files(self):
        for phase in ('install','rebuild','rtk'):
            with self.subTest(phase=phase), tempfile.TemporaryDirectory(dir='/var/tmp') as temp:
                base=Path(temp); binary=base/'opencode'
                binary.write_text('#!/bin/sh\nprintf "1.18.35\\n"\n'); binary.chmod(0o700)
                failure=lambda c: (c[:2]==['npm',phase] if phase!='rtk' else c[0]=='/fixture/rtk')
                with self.assertRaises(subprocess.CalledProcessError):self.render(base,binary,fail=failure)
                root=base/'opencode-gpt'
                self.assertEqual(json.loads((root/'profile.json').read_text())['status'],'preparing')
                args=argparse.Namespace(profile='opencode-gpt',state_root=base,repository=base,
                    role=None,print=True,prompt='fixture',timeout_seconds=1)
                with mock.patch.object(profiles,'fresh_worktree') as fresh:
                    with self.assertRaises(profiles.ProfileError):profiles.launch(args)
                    fresh.assert_not_called()
                extra=root/'keep.txt';extra.write_text('synthetic operator residue')
                self.render(base,binary,resume=True)
                self.assertEqual(json.loads((root/'profile.json').read_text())['status'],'trial')
                self.assertEqual(extra.read_text(),'synthetic operator residue')

    def test_relative_binary_remains_admitted_from_another_directory(self):
        with tempfile.TemporaryDirectory(dir='/var/tmp') as temp:
            base=Path(temp); binary=base/'opencode';other=base/'other';other.mkdir()
            binary.write_text('#!/bin/sh\nprintf "1.18.35\\n"\n');binary.chmod(0o700)
            previous=Path.cwd()
            try:
                os.chdir(base)
                self.render(base,Path('opencode'))
                meta=json.loads((base/'opencode-gpt/profile.json').read_text())
                os.chdir(other)
                self.assertTrue(Path(meta['opencode_bin']).is_absolute())
                self.assertEqual(profiles.verify_runtime_binary('opencode',Path(meta['opencode_bin'])),'1.18.35')
                args=argparse.Namespace(profile='opencode-gpt',state_root=base,repository=base,
                    role=None,print=True,prompt='fixture',timeout_seconds=1)
                with mock.patch.object(profiles,'fresh_worktree',side_effect=RuntimeError('admitted-worktree')) as fresh:
                    with self.assertRaisesRegex(RuntimeError,'admitted-worktree'):profiles.launch(args)
                    fresh.assert_called_once()
            finally:os.chdir(previous)

    def test_setup_failures_write_recovery_receipts_and_keep_original_failure(self):
        for profile in ('opencode-gpt','pi-claude'):
            for cleanup_status in ('removed','retained_dirty','retained_active'):
                with self.subTest(profile=profile,status=cleanup_status),tempfile.TemporaryDirectory(dir='/var/tmp') as temp:
                    base=Path(temp);root,workspace,args=self.fixture(base,profile)
                    failure=profiles.ProfileError('synthetic setup refusal')
                    with mock.patch.object(profiles,'verify_runtime_binary'), \
                            mock.patch.object(profiles,'fresh_worktree',return_value=workspace), \
                            mock.patch.object(profiles.shutil,'which',return_value=None), \
                            mock.patch.object(profiles,'choose_slot',side_effect=failure), \
                            mock.patch.object(profiles,'cleanup_worktree',return_value={'status':cleanup_status}) as cleanup:
                        with self.assertRaises(profiles.ProfileError) as caught:profiles.launch(args)
                    if profile=='pi-claude':self.assertIs(caught.exception,failure)
                    else:self.assertIn('filesystem boundary unavailable',str(caught.exception))
                    cleanup.assert_called_once_with(base,workspace)
                    receipts=list((root/'runs').glob('*/recovery-receipt.json'))
                    self.assertEqual(len(receipts),1)
                    receipt=json.loads(receipts[0].read_text())
                    self.assertEqual(receipt['worktree_cleanup']['status'],cleanup_status)
                    self.assertEqual(receipt['status'],'launch_failed')
                    self.assertNotIn('synthetic setup refusal',json.dumps(receipt))

    def test_clean_owned_runtime_branch_removed_but_other_and_dirty_branches_retained(self):
        with tempfile.TemporaryDirectory(dir='/var/tmp') as temp:
            base=Path(temp);repo=base/'repo';repo.mkdir()
            subprocess.run(['git','init','-q',str(repo)],check=True)
            subprocess.run(['git','-C',str(repo),'-c','user.name=Fixture',
                '-c','user.email=fixture@users.noreply.github.com','commit','-q','--allow-empty','-m','fixture'],check=True)
            for label,branch,dirty in [('owned','runtime/pi-gpt-0123456789ab',False),
                    ('other','operator-branch',False),('dirty','runtime/pi-gpt-fedcba987654',True),
                    ('active','runtime/pi-gpt-222222222222',False),
                    ('unmerged','runtime/pi-gpt-333333333333',False)]:
                workspace=base/label
                subprocess.run(['git','-C',str(repo),'worktree','add','-b',branch,str(workspace)],check=True,capture_output=True)
                if dirty:(workspace/'keep.txt').write_text('fixture')
                if label=='unmerged':
                    subprocess.run(['git','-C',str(workspace),'-c','user.name=Fixture',
                        '-c','user.email=fixture@users.noreply.github.com','commit','-q','--allow-empty','-m','keep'],check=True)
                with mock.patch.object(profiles,'active_worktree',return_value=label=='active'):
                    result=profiles.cleanup_worktree(repo,workspace)
                exists=subprocess.run(['git','-C',str(repo),'show-ref','--verify','--quiet','refs/heads/'+branch]).returncode==0
                self.assertEqual(exists,label!='owned')
                self.assertEqual(result['status'],'retained_dirty' if dirty else 'retained_active' if label=='active' else 'removed')
                if label=='unmerged':self.assertEqual(result['branch_cleanup'],'retained_unmerged_or_error')


if __name__=='__main__':unittest.main()
