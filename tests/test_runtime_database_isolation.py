"""Native private DB fixture; no model/auth call or real account DB.

anomalyco/opencode@e3c4eb24:packages/core/src/flag/flag.ts:47 and
packages/core/src/database/database.ts:43-55 give the override precedence.
"""
import argparse
from contextlib import closing, redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
source = Path(os.environ.get('NS_RUNTIME_DB_BASELINE_SOURCE', ROOT/'tools/adoption/runtime_profiles.py'))
spec = importlib.util.spec_from_file_location('db_override_profiles', source)
profiles = importlib.util.module_from_spec(spec)
spec.loader.exec_module(profiles)
profiles.ROOT = ROOT
REAL_RUN = subprocess.run


class NativeDatabaseIsolationTests(unittest.TestCase):
    def test_actual_collector_preserves_shared_fixture_and_initializes_private_db(self):
        binary = os.environ.get('NS_OPENCODE_TEST_BIN')
        if not binary:
            self.skipTest('explicit installed public OpenCode binary required')
        for profile in ('opencode-gpt', 'opencode-claude'):
            for existing in (False, True):
                with self.subTest(profile=profile, existing=existing), tempfile.TemporaryDirectory(dir='/var/tmp') as temporary:
                    state = Path(temporary)
                    root = state/profile/'roles/builder'
                    root.mkdir(parents=True)
                    workspace = state/'workspace'
                    workspace.mkdir()
                    outside = state/'shared.db'
                    if existing:
                        with closing(sqlite3.connect(outside)) as database:
                            database.execute('VACUUM')
                    before = outside.read_bytes() if existing else None
                    (root/'profile.json').write_text(json.dumps({
                        'status':'trial','model':'fixture','effort':'high','opencode_bin':binary,
                        'roles':{'isolated-builder':{'tools':[]}},
                    }))
                    config = root/'config/opencode/opencode.json'
                    config.parent.mkdir(parents=True)
                    config.write_text('{"agent":{},"plugin":[]}')
                    args = argparse.Namespace(profile=profile,state_root=state,repository=state,
                                              role='isolated-builder',print=False,prompt=None)
                    environment = {'HOME':str(state),'PATH':os.defpath,'TMPDIR':str(state),
                                   'OPENCODE_DB':str(outside),'OPENCODE_DISABLE_AUTOUPDATE':'1',
                                   'OPENCODE_DISABLE_MODELS_FETCH':'1'}
                    observed = []
                    diagnostics = []
                    def run(command, **kwargs):
                        if command[:3] == [binary, 'session', 'list']:
                            with tempfile.TemporaryFile(mode='w+') as errors:
                                result = REAL_RUN(command, **{**kwargs,'stderr':errors}, timeout=25)
                                errors.seek(0)
                                diagnostics.append(errors.read()[-2000:] if result.returncode else '')
                            observed.append(result.returncode)
                            return result
                        return subprocess.CompletedProcess(command, 0)
                    with mock.patch.dict(os.environ,environment,clear=True), \
                            mock.patch.object(tempfile,'tempdir','/var/tmp'), \
                            mock.patch.object(profiles,'fresh_worktree',return_value=workspace), \
                            mock.patch.object(profiles,'verify_runtime_binary',return_value='1.19.3'), \
                            mock.patch.object(profiles,'choose_slot',return_value='fixture-slot'), \
                            mock.patch.object(profiles,'opencode_sandbox_command',side_effect=lambda command,*args:command), \
                            mock.patch.object(profiles,'cleanup_worktree',return_value={'status':'removed'}), \
                            mock.patch.object(profiles.subprocess,'run',side_effect=run), redirect_stdout(io.StringIO()):
                        profiles.launch(args)
                    self.assertEqual(observed,[0],'native session list did not execute successfully: '+str(diagnostics))
                    if existing:
                        self.assertTrue(outside.read_bytes()==before,'collector changed synthetic shared database')
                    else:
                        self.assertFalse(outside.exists(),'collector created synthetic shared database')
                    self.assertFalse(Path(str(outside)+'-wal').exists())
                    self.assertFalse(Path(str(outside)+'-shm').exists())
                    databases = list((root/'data').rglob('*.db'))
                    self.assertTrue(databases,'normal private database was not initialized')
                    for path in databases:
                        with closing(sqlite3.connect('file:'+str(path)+'?mode=ro',uri=True)) as database:
                            self.assertEqual(database.execute('PRAGMA integrity_check').fetchone()[0],'ok')


class DatabaseEnvironmentPolicyTests(unittest.TestCase):
    def test_headless_native_child_uses_private_database_for_each_route(self):
        for profile in ('opencode-gpt','opencode-claude'):
            with self.subTest(profile=profile),tempfile.TemporaryDirectory(dir='/var/tmp') as temporary:
                state=Path(temporary);root=state/profile/'roles/builder';root.mkdir(parents=True)
                workspace=state/'workspace';workspace.mkdir();outside=state/'shared.db'
                (root/'profile.json').write_text(json.dumps({'status':'trial','model':'fixture','effort':'high',
                    'opencode_bin':'/fixture/opencode','roles':{'isolated-builder':{'tools':[]}}}))
                config=root/'config/opencode/opencode.json';config.parent.mkdir(parents=True)
                config.write_text('{"agent":{}}')
                args=argparse.Namespace(profile=profile,state_root=state,repository=state,
                                       role='isolated-builder',print=True,prompt=None,timeout_seconds=5,
                                       ledger=state/'ledger.jsonl')
                observed=[]
                def run(command,**kwargs):
                    if profile.endswith('-claude'):
                        index=command.index('env')
                        child={item.split('=',1)[0]:item.split('=',1)[1] for item in command[index+1:]
                               if '=' in item and not item.startswith('--')}
                    else:child=kwargs['env']
                    observed.append(child.get('OPENCODE_DB'))
                    return subprocess.CompletedProcess(command,0)
                with mock.patch.dict(os.environ,{'HOME':str(state),'PATH':os.defpath,
                                                  'TMPDIR':'/var/tmp','OPENCODE_DB':str(outside)},clear=True), \
                        mock.patch.object(profiles,'fresh_worktree',return_value=workspace), \
                        mock.patch.object(profiles,'verify_runtime_binary',return_value='1.19.3'), \
                        mock.patch.object(profiles,'choose_slot',return_value='fixture-slot'), \
                        mock.patch.object(profiles,'opencode_sandbox_command',side_effect=lambda command,*args:command), \
                        mock.patch.object(profiles,'cleanup_worktree',return_value={'status':'removed'}), \
                        mock.patch.object(profiles.subprocess,'check_output',return_value='a'*40), \
                        mock.patch.object(profiles.subprocess,'run',side_effect=run),redirect_stdout(io.StringIO()):
                    self.assertEqual(profiles.launch(args),0)
                self.assertEqual(len(observed),1)
                self.assertTrue(observed[0],'native child DB binding missing')
                self.assertTrue(Path(observed[0]).is_absolute())
                self.assertTrue(Path(observed[0]).is_relative_to(root))
                self.assertFalse(outside.exists())

    def test_discovery_commands_use_private_database_in_every_profile_scope(self):
        sys_path=str(ROOT/'tools/adoption')
        import sys
        sys.path.insert(0,sys_path)
        import runtime_acceptance as acceptance
        for profile in ('opencode-gpt','opencode-claude'):
            for scope in (None,*profiles.ROLE_SCOPES):
                with self.subTest(profile=profile,scope=scope),tempfile.TemporaryDirectory(dir='/var/tmp') as temporary:
                    state=Path(temporary);root=state/profile
                    if scope:root=root/'roles'/scope
                    root.mkdir(parents=True);workspace=state/'workspace';workspace.mkdir();outside=state/'shared.db'
                    (root/'profile.json').write_text(json.dumps({'opencode_bin':'/fixture/opencode',
                                                               'mcp_server_names':['fixture']}))
                    args=argparse.Namespace(state_root=state,role_scope=scope,workspace=workspace,
                                           out=state/'receipts',tokenizer_python=sys.executable)
                    observed=[]
                    def native(command,**kwargs):
                        observed.append(kwargs['env'].get('OPENCODE_DB'))
                        return 0,'[]'
                    with mock.patch.dict(os.environ,{'HOME':str(state),'PATH':os.defpath,
                                                      'TMPDIR':'/var/tmp','OPENCODE_DB':str(outside)},clear=True), \
                            mock.patch.object(acceptance,'profile_environment',profiles.profile_environment), \
                            mock.patch.object(acceptance,'choose_slot',return_value='fixture-slot'), \
                            mock.patch.object(acceptance,'native',side_effect=native), \
                            mock.patch.object(acceptance,'skill_integrity',return_value={'managed_pass':True}), \
                            mock.patch.object(acceptance,'managed_rows',return_value={}), \
                            mock.patch.object(acceptance,'opencode_statuses',return_value={'fixture':'connected'}), \
                            redirect_stdout(io.StringIO()):
                        self.assertTrue(acceptance.check(args,profile))
                    self.assertGreaterEqual(len(observed),2)
                    for selected in observed:
                        self.assertTrue(selected,'discovery DB binding missing')
                        self.assertTrue(Path(selected).is_absolute())
                        self.assertTrue(Path(selected).is_relative_to(root))
                    self.assertFalse(outside.exists())


if __name__ == '__main__':
    unittest.main()

