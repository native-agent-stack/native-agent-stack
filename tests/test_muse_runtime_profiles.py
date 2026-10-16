"""Model-free admission checks for the named Muse harness trial profiles."""
from pathlib import Path
import argparse
from contextlib import redirect_stdout
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/adoption'))
import runtime_profiles as profiles


class MuseRuntimeProfileTests(unittest.TestCase):
    def test_pi_muse_preserves_native_context_package_alongside_role_package(self):
        with tempfile.TemporaryDirectory(dir='/var/tmp') as tmp:
            state = Path(tmp)
            servers = {'context-mode': {'type': 'stdio', 'command': '/fixture/node'}}
            with mock.patch.object(profiles, 'verify_runtime_binary', return_value='1.1.0'), \
                 mock.patch.object(profiles, 'canonical_servers', return_value=servers), \
                 mock.patch.object(profiles.shutil, 'which', return_value='/fixture/rtk'), \
                 mock.patch.object(profiles.subprocess, 'check_output', side_effect=[
                     'rtk 0.51.0\n', 'e001f773f80b22b7dc4c7a79521b30e35aaef026\n']), \
                 mock.patch.object(profiles.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)):
                profiles.render('pi-muse', state=state, home=state, eco_root=state,
                                templates=[], pi_bin=state/'pi', opencode_bin=state/'opencode',
                                rtk_source=state, role_scope='builder')
            root = state/'pi-muse/roles/builder'
            settings = json.loads((root/'agent/settings.json').read_text())
            self.assertEqual(settings['packages'], [str(profiles.context_mode_package(root)),
                             'git:github.com/obra/superpowers@'+profiles.SUPERPOWERS])
            metadata = json.loads((root/'profile.json').read_text())
            self.assertIn('ctx_execute', metadata['roles']['isolated-builder']['tools'])

    def test_pi_muse_uses_vendor_context_mode_bridge_names_without_extra_grants(self):
        metadata, _ = profiles.role_source('isolated-builder')
        tools, _ = profiles.granted_tools(metadata, 'pi', native_context_mode=True)
        context_tools = {tool for tool in tools if tool.startswith('ctx_')}
        self.assertEqual(context_tools, {'ctx_execute', 'ctx_execute_file', 'ctx_search', 'ctx_batch_execute'})
        self.assertFalse(any(tool.startswith('mcp__context_mode__') for tool in tools))
        self.assertNotIn('ctx_fetch_and_index', tools)

    def test_muse_child_environment_keeps_only_process_context(self):
        with mock.patch.dict(os.environ, {'HOME': '/fixture/home', 'PATH': '/usr/bin',
                                        'OPENAI_API_KEY': 'fixture-secret',
                                        'ANTHROPIC_AUTH_TOKEN': 'fixture-secret',
                                        'UNRELATED_PRIVATE_VALUE': 'fixture-secret'}, clear=True):
            environment = profiles.muse_child_environment({'PI_CODING_AGENT_DIR': '/fixture/agent'})
        self.assertEqual(environment, {'HOME': '/fixture/home', 'PATH': '/usr/bin',
                                       'PI_CODING_AGENT_DIR': '/fixture/agent'})

    @unittest.skipUnless(shutil.which('bwrap'), 'native namespace fixture requires bubblewrap')
    def test_opencode_admits_only_the_named_mcp_executable_alias(self):
        with tempfile.TemporaryDirectory(dir='/var/tmp') as tmp:
            state = Path(tmp)
            root, workspace = state / 'profile', state / 'workspace'
            (root / 'config/opencode').mkdir(parents=True)
            (root / 'tmp').mkdir()
            workspace.mkdir()
            target = state / 'mcp-native'
            target.write_text('#!/bin/sh\necho MCP_READY\n')
            target.chmod(0o700)
            alias = state / 'aliases/mcp-tool'
            alias.parent.mkdir()
            alias.symlink_to(target)
            sibling = alias.parent / 'not-granted'
            sibling.write_text('public ungranted canary')
            (root / 'config/opencode/opencode.json').write_text(json.dumps({
                'agent': {}, 'mcp': {'fixture': {'type': 'local', 'command': [str(alias)]}}}))
            meta = {'opencode_bin': '/bin/true'}
            command = profiles.opencode_sandbox_command([str(alias)], root, workspace, meta, None)
            result = subprocess.run(command, env={}, capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), 'MCP_READY')
            check = profiles.opencode_sandbox_command(['/usr/bin/test', '!', '-e', str(sibling)],
                                                       root, workspace, meta, None)
            self.assertEqual(subprocess.run(check, env={}).returncode, 0)

    @unittest.skipUnless(shutil.which('bwrap'), 'native namespace fixture requires bubblewrap')
    def test_opencode_executes_qualified_target_not_unmounted_alias(self):
        with tempfile.TemporaryDirectory(dir='/var/tmp') as tmp:
            state = Path(tmp)
            root = state / 'opencode-muse'
            workspace = state / 'workspace'
            workspace.mkdir()
            subprocess.run(['git', 'init', '--quiet', str(workspace)], check=True)
            subprocess.run(['git', '-C', str(workspace), '-c', 'user.name=Fixture',
                            '-c', 'user.email=fixture@invalid', 'commit', '--allow-empty', '--quiet', '-m', 'fixture'], check=True)
            binary = state / 'native-opencode'
            binary.write_text('#!/bin/sh\nif [ "$1" = "--version" ]; then echo 1.18.35; '
                              'else echo \'{"type":"step_finish","part":{"tokens":{}}}\'; fi\n')
            binary.chmod(0o700)
            alias = state / 'aliases/opencode'
            alias.parent.mkdir()
            alias.symlink_to(binary)
            (root / 'config/opencode').mkdir(parents=True)
            (root / 'tmp').mkdir()
            (root / 'config/opencode/opencode.json').write_text('{"agent":{}}')
            (root / 'profile.json').write_text(json.dumps({
                'status': 'trial', 'model': profiles.MUSE_MODEL, 'effort': 'max',
                'runtime_version': '1.18.35', 'opencode_bin': str(alias), 'roles': {}}))
            args = argparse.Namespace(profile='opencode-muse', state_root=state, repository=workspace,
                                      role=None, print=True, prompt='synthetic', timeout_seconds=10, resume=None)
            with mock.patch.object(profiles, 'fresh_worktree', return_value=workspace), \
                    mock.patch.object(profiles, 'cleanup_worktree', return_value={'status': 'retained_fixture'}), \
                    redirect_stdout(io.StringIO()):
                rc = profiles.launch(args)
            self.assertEqual(rc, 0, 'the real namespace must execute the admitted target')

    def test_named_pi_and_opencode_muse_profiles_are_admitted(self):
        for name in ('pi-muse', 'opencode-muse'):
            with self.subTest(profile=name):
                self.assertIn(name, profiles.PROFILES)

    def test_pi_uses_exact_muse_code_provider_model(self):
        config = profiles.pi_models('muse', role_scope='builder')
        provider = config['providers']['omniroute']
        self.assertEqual(provider['baseUrl'], profiles.GATEWAY)
        self.assertEqual(provider['api'], 'openai-responses')
        self.assertEqual([model['id'] for model in provider['models']],
                         ['mc/muse-wonder-full-1.0'])
        self.assertEqual(provider['models'][0]['thinkingLevelMap']['max'], 'max')

    def test_opencode_uses_exact_muse_code_provider_model(self):
        config = profiles.opencode_provider('muse')['omniroute']
        self.assertEqual(config['npm'], '@ai-sdk/openai')
        self.assertEqual(config['options']['baseURL'], profiles.GATEWAY)
        self.assertEqual(list(config['models']), ['mc/muse-wonder-full-1.0'])
        self.assertEqual(config['models']['mc/muse-wonder-full-1.0']['variants']['max']['reasoningEffort'], 'max')

    def test_unrecognized_route_cannot_fall_back_to_gpt(self):
        for renderer in (profiles.pi_models, profiles.opencode_provider):
            with self.subTest(renderer=renderer.__name__):
                with self.assertRaises(profiles.ProfileError):
                    renderer('muse-typo')

    def test_pi_identity_uses_runtime_message_and_labels_normalization(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            log = root / 'events.jsonl'
            log.write_text(json.dumps({'type': 'message_end', 'message': {
                'role': 'assistant', 'model': 'mc/muse-wonder-full-1.0'}}) + '\n')
            facts = profiles.muse_model_identity([log], 'pi', {'model': profiles.MUSE_MODEL}, root, {})
            self.assertEqual(facts['runtime_reported_model_ids'], [profiles.MUSE_MODEL])
            self.assertIn('upstream identity unverified', facts['model_identity_basis'])

    def test_opencode_identity_uses_only_own_session_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            log = root / 'events.jsonl'
            log.write_text(json.dumps({'type': 'step_finish', 'sessionID': 'ses_fixture'}) + '\n')

            def export(command, **kwargs):
                json.dump({'info': {'id': 'ses_fixture'}, 'messages': [
                    {'info': {'role': 'assistant', 'sessionID': 'ses_fixture', 'modelID': profiles.MUSE_MODEL}},
                    {'info': {'role': 'assistant', 'sessionID': 'ses_foreign', 'modelID': 'foreign'}}]}, kwargs['stdout'])
                return subprocess.CompletedProcess(command, 0)

            with mock.patch.object(profiles.subprocess, 'run', side_effect=export):
                facts = profiles.muse_model_identity([log], 'opencode',
                                                    {'model': profiles.MUSE_MODEL, 'opencode_bin': '/fixture/opencode'}, root, {})
            self.assertEqual(facts['runtime_reported_model_ids'], [profiles.MUSE_MODEL])
