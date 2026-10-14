"""Role-scoped models.json output budget, no model call or runtime install."""
import sys
from pathlib import Path
import unittest
import json
import subprocess
import tempfile
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/adoption'))
import runtime_profiles as profiles


def budget(value, route):
    providers = value['providers']
    return providers['anthropic']['modelOverrides'][profiles.CLAUDE_MODEL]['maxTokens'] \
        if route == 'claude' else providers['omniroute']['models'][0]['maxTokens']


class PiBuilderOutputTests(unittest.TestCase):
    def test_native_builder_budget_exceeds_old_cap_within_documented_ceiling(self):
        for route, maximum in [('claude', 128000), ('gpt', 128000)]:
            with self.subTest(route=route):
                model = profiles.pi_models(route, role_scope='builder')
                self.assertEqual(budget(model, route), 32768)
                self.assertLessEqual(budget(model, route), maximum)

    def test_reviewer_auditor_and_unscoped_metadata_keep_existing_budget(self):
        for route in ('claude', 'gpt'):
            for scope in (None, 'reviewer', 'auditor'):
                with self.subTest(route=route, role=scope):
                    self.assertEqual(budget(profiles.pi_models(route, role_scope=scope), route), 8192)

    def test_generated_native_models_file_raises_builder_and_researcher_only(self):
        for route in ('claude', 'gpt'):
            for scope, expected in [('builder', 32768), ('researcher', 32768),
                                    ('reviewer', 8192), ('auditor', 8192), (None, 8192)]:
                with self.subTest(route=route, scope=scope), tempfile.TemporaryDirectory(dir='/var/tmp') as td:
                    state = Path(td)
                    with mock.patch.object(profiles, 'verify_runtime_binary', return_value='1.1.0'), \
                            mock.patch.object(profiles, 'canonical_servers', return_value={'context-mode': {
                                'command': 'node', 'args': []}}), \
                            mock.patch.object(profiles.shutil, 'which', return_value='/fixture/rtk'), \
                            mock.patch.object(profiles.subprocess, 'check_output', side_effect=[
                                'rtk 0.51.0', 'e001f773f80b22b7dc4c7a79521b30e35aaef026']), \
                            mock.patch.object(profiles.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)):
                        profiles.render('pi-' + route, state=state, home=state, eco_root=state,
                                        templates=[], pi_bin=state / 'pi', opencode_bin=state / 'opencode',
                                        rtk_source=state, role_scope=scope)
                    root = state / ('pi-' + route)
                    if scope: root = root / 'roles' / scope
                    models = json.loads((root / 'agent/models.json').read_text())
                    self.assertEqual(budget(models, route), expected)


if __name__ == '__main__': unittest.main()
