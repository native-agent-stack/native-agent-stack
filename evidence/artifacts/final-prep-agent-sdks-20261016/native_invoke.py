"""Credential-free native app-server handshake from the vendor stdio fixture.

No thread/turn/account/model request is sent. Only projected protocol status is
printed; native diagnostics stay outside the public evidence record.
"""
import json
import os
import selectors
import subprocess
from pathlib import Path

ARM = Path('/var/tmp/ns2604-g5-agent-sdks-run')
env = {
    'PATH': str(ARM / 'bin') + ':/usr/bin:/bin',
    'HOME': str(ARM / 'work/home'),
    'CODEX_HOME': str(ARM / 'work/invoke-codex-home'),
    'TMPDIR': str(ARM / 'tmp'),
    'CODEX_APP_SERVER_MANAGED_CONFIG_PATH': str(ARM / 'work/invoke-codex-home/managed_config.toml'),
}
with (ARM / 'out/invoke.stderr').open('w') as err:
    proc = subprocess.Popen(
        [str(ARM / 'work/tools/node_modules/.bin/codex'), '-c', 'features.plugins=false', 'app-server'],
        cwd=ARM / 'work', env=env, stdin=subprocess.PIPE,
        stdout=subprocess.PIPE, stderr=err, text=True)
    try:
        request = {'id': 1, 'method': 'initialize', 'params': {
            'clientInfo': {'name': 'final-prep-agent-sdks', 'version': '1'}}}
        proc.stdin.write(json.dumps(request) + '\n')
        proc.stdin.flush()
        with selectors.DefaultSelector() as selector:
            selector.register(proc.stdout, selectors.EVENT_READ)
            assert selector.select(20), 'native initialize timeout'
            response = json.loads(proc.stdout.readline())
        assert response.get('id') == 1 and 'result' in response, 'initialize failed'
        print(json.dumps({'method': 'initialize', 'request_id': 1,
                          'success': True, 'native_process': 'codex-cli 0.160.0 app-server',
                          'provider_requests': 0, 'thread_or_turn_requests': 0,
                          'credential_environment': 'closed allowlist',
                          'boundary': 'local protocol handshake only; no model inference'}))
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
