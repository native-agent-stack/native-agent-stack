"""Role-scoped zero-MCP preparation, using the real generator and native argv."""
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


class NoMcpRoleTests(unittest.TestCase):
    def render(self, base, profile, *, no_mcp=False, scope='reviewer', context=True, wsl=False):
        template=base/'template.json'
        servers={'ai-memory':{'command':'/fixture/mcp','args':[]},
                 'serena':{'command':'/fixture/mcp','args':[]}}
        if context:servers['context-mode']={'command':'node','args':[]}
        template.write_text(json.dumps({'mcpServers':servers}))
        with ExitStack() as stack:
            stack.enter_context(mock.patch.object(profiles,'verify_runtime_binary',return_value='fixture'))
            stack.enter_context(mock.patch.object(profiles.shutil,'which',return_value='/fixture/rtk'))
            stack.enter_context(mock.patch.object(profiles.subprocess,'check_output',side_effect=[
                'rtk 0.51.0','e001f773f80b22b7dc4c7a79521b30e35aaef026']))
            stack.enter_context(mock.patch.object(profiles.subprocess,'run',return_value=subprocess.CompletedProcess([],0)))
            if wsl:stack.enter_context(mock.patch.object(profiles,'render_wsl_mcp',return_value=dict(servers)))
            extra={'no_mcp':True} if no_mcp else {}
            return profiles.render(profile,state=base,home=base,eco_root=base,templates=[template],
                pi_bin=base/'pi',opencode_bin=base/'opencode',rtk_source=base,role_scope=scope,wsl=wsl,**extra)

    def test_flag_removes_servers_and_every_mcp_grant_preserving_native_tools_and_prompt(self):
        for profile in profiles.PROFILES:
            for wsl in (False,True):
                with self.subTest(profile=profile,wsl=wsl),tempfile.TemporaryDirectory(dir='/var/tmp') as temp:
                    base=Path(temp)
                    self.render(base,profile,no_mcp=True,wsl=wsl)
                    root=base/profile/'roles/reviewer'
                    descriptor=json.loads((root/'profile.json').read_text())
                    self.assertEqual(descriptor['mcp_server_names'],[])
                    self.assertTrue(descriptor['no_mcp'])
                    runtime=profile.split('-')[0]
                    native=['find','grep','read'] if runtime=='pi' else ['glob','grep','read']
                    for role in profiles.ROLES:
                        original,_=profiles.role_source(role)
                        builtins={'read','grep','find','glob','bash','edit','write','websearch','skill'}
                        expected=[t for t in profiles.granted_tools(original,runtime)[0] if t in builtins]
                        self.assertEqual(descriptor['roles'][role]['tools'],expected)
                    self.assertEqual(descriptor['roles']['evidence-reviewer']['tools'],native)
                    _,prompt=profiles.role_source('evidence-reviewer')
                    if runtime=='pi':
                        cfg=json.loads((root/'agent/mcp.json').read_text())
                        self.assertEqual(cfg['mcpServers'],{})
                        self.assertIn(prompt,(root/'agent/prompts/evidence-reviewer.md').read_text())
                    else:
                        cfg=json.loads((root/'config/opencode/opencode.json').read_text())
                        self.assertEqual(cfg['mcp'],{})
                        self.assertIn(prompt,cfg['agent']['evidence-reviewer']['prompt'])
                        for agent in cfg['agent'].values():
                            grants=agent.get('permission',{})
                            for tool,action in grants.items():
                                if tool in ('*','read','external_directory','skill'):continue
                                self.assertIn(tool,builtins)

    def test_context_mode_stays_required_without_flag_for_every_scope_and_runtime(self):
        for profile in profiles.PROFILES:
            for scope in (None,*profiles.ROLE_SCOPES):
                for wsl in (False,True):
                    with self.subTest(profile=profile,scope=scope,wsl=wsl),tempfile.TemporaryDirectory(dir='/var/tmp') as temp:
                        base=Path(temp)
                        with self.assertRaisesRegex(profiles.ProfileError,'must include Context Mode'):
                            self.render(base,profile,context=False,scope=scope,wsl=wsl)
                        self.assertFalse((base/profile).exists())

    def test_no_mcp_role_accepts_templates_without_context_mode(self):
        for profile in profiles.PROFILES:
            for wsl in (False,True):
                with self.subTest(profile=profile,wsl=wsl),tempfile.TemporaryDirectory(dir='/var/tmp') as temp:
                    base=Path(temp)
                    self.render(base,profile,no_mcp=True,context=False,wsl=wsl)
                    descriptor=json.loads((base/profile/'roles/reviewer/profile.json').read_text())
                    self.assertEqual(descriptor['mcp_server_names'],[])

    def test_unscoped_no_mcp_is_refused_without_writes(self):
        with tempfile.TemporaryDirectory(dir='/var/tmp') as temp:
            base=Path(temp)
            with self.assertRaisesRegex(profiles.ProfileError,'role scope'):
                self.render(base,'pi-claude',no_mcp=True,scope=None)
            self.assertFalse((base/'pi-claude').exists())

    def test_cli_applies_option_only_to_the_named_role_scope(self):
        args=['prepare','--state-root','/fixture','--eco-root','/fixture',
              '--mcp-template','/fixture/mcp.json','--pi-bin','/fixture/pi',
              '--opencode-bin','/fixture/opencode','--rtk-source','/fixture',
              '--no-mcp-role','reviewer']
        with mock.patch.object(profiles,'render',return_value={}) as render,redirect_stdout(io.StringIO()):
            self.assertEqual(profiles.main(args),0)
        self.assertEqual(len(render.call_args_list),20)
        for call in render.call_args_list:
            self.assertEqual(call.kwargs['no_mcp'],call.kwargs['role_scope']=='reviewer')
        with mock.patch.object(profiles,'render') as render,redirect_stdout(io.StringIO()):
            self.assertEqual(profiles.main(args+['--no-role-scoped']),2)
            render.assert_not_called()

    def test_pi_launch_uses_native_no_mcp_with_the_unchanged_review_builtins(self):
        with tempfile.TemporaryDirectory(dir='/var/tmp') as temp:
            base=Path(temp);self.render(base,'pi-claude',no_mcp=True)
            root=base/'pi-claude/roles/reviewer';workspace=base/'workspace';workspace.mkdir()
            args=argparse.Namespace(profile='pi-claude',state_root=base,repository=base,
                role='evidence-reviewer',print=True,prompt='hello',timeout_seconds=1)
            observed=[]
            def child(command,**kw):
                observed.append(command);return subprocess.CompletedProcess(command,0)
            with mock.patch.dict(os.environ,{'HOME':str(base),'PATH':os.defpath},clear=True), \
                    mock.patch.object(profiles,'verify_runtime_binary'), \
                    mock.patch.object(profiles,'fresh_worktree',return_value=workspace), \
                    mock.patch.object(profiles,'choose_slot',return_value='anthropic-api-4'), \
                    mock.patch.object(profiles.subprocess,'run',side_effect=child), \
                    mock.patch.object(profiles.subprocess,'check_output',return_value='a'*40), \
                    mock.patch.object(profiles,'cleanup_worktree',return_value={'status':'removed'}), \
                    redirect_stdout(io.StringIO()):
                self.assertEqual(profiles.launch(args),0)
            command=observed[0]
            self.assertIn('--no-mcp',command)
            self.assertEqual(command[command.index('--tools')+1],'find,grep,read')


if __name__=='__main__':unittest.main()
