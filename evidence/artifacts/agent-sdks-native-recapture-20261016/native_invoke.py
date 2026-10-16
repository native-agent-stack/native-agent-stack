"""Capture native initialize response bytes verbatim; no driver status summary.

Contract: openai/codex a956835d020762cb2b570053af06f643a11c0ecc,
codex-rs/app-server/tests/suite/v2/connection_handling_stdio_tests.rs:72-86.
Only initialize is sent. No account, thread, turn or model request.
"""
import os
import selectors
import subprocess
import sys
import json
from pathlib import Path


def main():
    arm = Path(sys.argv[1]).resolve()
    env = dict(os.environ)
    env['CODEX_HOME'] = str(arm / 'work/invoke-codex-home')
    env['CODEX_APP_SERVER_MANAGED_CONFIG_PATH'] = str(arm / 'work/invoke-codex-home/managed_config.toml')
    with (arm / 'logs/native-invoke.stderr').open('wb') as err:
        proc = subprocess.Popen(
            [str(arm / 'work/tools/node_modules/.bin/codex'), '-c', 'features.plugins=false', 'app-server'],
            cwd=arm / 'work', env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=err)
        try:
            request = {'id': 1, 'method': 'initialize', 'params': {
                'clientInfo': {'name': 'agent-sdks-native-capture', 'version': '1'}}}
            proc.stdin.write(json.dumps(request).encode() + b'\n')
            proc.stdin.flush()
            with selectors.DefaultSelector() as selector:
                selector.register(proc.stdout, selectors.EVENT_READ)
                if not selector.select(20):
                    raise TimeoutError('native initialize response not captured')
                raw = proc.stdout.readline()
            # Capture native bytes even if contract validation fails afterward.
            sys.stdout.buffer.write(raw)
            sys.stdout.buffer.flush()
            response = json.loads(raw)
            if response.get('id') != 1 or 'result' not in response:
                raise ValueError('native initialize contract failed')
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()


if __name__ == '__main__':
    main()
