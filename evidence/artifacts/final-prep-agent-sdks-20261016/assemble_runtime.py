"""Project observed sequential recorder commands to public runtime receipts.

Only selected version/test summary/protocol output is published and hashed.
Raw scratch diagnostics and their digests remain outside public evidence.
"""
import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ARM = Path('/var/tmp/ns2604-g5-agent-sdks-run')
PIN = 'a956835d020762cb2b570053af06f643a11c0ecc'


def write(name, value):
    (HERE / name).write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def main():
    rows = [json.loads(line) for line in (ARM / 'steps.jsonl').read_text().splitlines()]
    assert len(rows) == 7 and rows[-1]['phase'] == 'invoke', 'Only assemble a completed sequential run'
    commands = []
    test_summary = None
    for i, row in enumerate(rows):
        assert row['n'] == i + 1
        assert not i or row['started'] >= rows[i - 1]['ended'], 'Recorder steps overlapped'
        raw = (ARM / row['log']).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == row['log_sha256'], 'Scratch log integrity mismatch'
        assert row['exit_code'] == 0, 'A failed native step remains a gap; do not relabel success'
        text = raw.decode('utf8', 'replace')
        if row['phase'] == 'test':
            selected = [line for line in text.splitlines() if re.match(r'^(PASS |FAIL |Test Suites:|Tests:|Snapshots:|Time:|Ran all test suites)', line)]
            test_summary = '\n'.join(selected) + '\n'
            assert '5 passed, 5 total' in test_summary and '48 passed, 48 total' in test_summary
            output = test_summary
        elif row['phase'] == 'invoke':
            value = json.loads(text)
            assert value['success'] is True and value['thread_or_turn_requests'] == 0
            output = json.dumps(value, sort_keys=True) + '\n'
        elif row['phase'] == 'verify':
            output = text
            if i == 1:
                assert output.strip() == PIN
            if i == 4:
                assert output.strip() == 'codex-cli 0.160.0'
        else:
            output = json.dumps({'phase': row['phase'], 'exit_code': row['exit_code'],
                                 'status': 'completed', 'scope': 'own scratch only'}) + '\n'
        assert not re.search(r'/home/|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', output)
        filename = f'output-{i+1:02d}.txt'
        (HERE / filename).write_text(output)
        commands.append({k: row[k] for k in ['n', 'phase', 'command', 'cwd', 'exit_code', 'started', 'ended', 'seconds']})
        commands[-1].update(output=filename, output_sha256=hashlib.sha256(output.encode()).hexdigest(),
                            output_projection='selected public native output; raw scratch bytes/digest not exported')
    sources = [
        {'repository': 'https://github.com/openai/codex', 'pin': PIN, 'path': 'README.md', 'line': 42,
         'why': 'Official npm CLI install at exact release'},
        {'repository': 'https://github.com/openai/codex', 'pin': PIN, 'path': '.github/workflows/sdk.yml', 'line': 127,
         'why': 'Frozen-lockfile vendor dependency install'},
        {'repository': 'https://github.com/openai/codex', 'pin': PIN, 'path': '.github/workflows/sdk.yml', 'line': 136,
         'why': 'Complete vendor SDK test-package target; no suite/test filter'},
        {'repository': 'https://github.com/openai/codex', 'pin': PIN, 'path': 'sdk/typescript/tests/testCodex.ts', 'line': 7,
         'why': 'Vendor executable override uses official release binary at same source pin'},
        {'repository': 'https://github.com/openai/codex', 'pin': PIN, 'path': 'sdk/typescript/tests/testCodex.ts', 'line': 24,
         'why': 'Vendor loopback mock provider; no paid model or credential connection'},
        {'repository': 'https://github.com/openai/codex', 'pin': PIN, 'path': 'codex-rs/app-server/tests/suite/v2/connection_handling_stdio_tests.rs', 'line': 72,
         'why': 'Native stdio initialize request and response contract'},
    ]
    for source in sources:
        lines = (ARM / 'work/codex' / source['path']).read_text().splitlines()
        assert len(lines) >= source['line']
    write('runtime-receipt.json', {
        'kind': 'upstream_e2e_preparation', 'layer': 'foundation/agent-sdks',
        'repository': 'https://github.com/openai/codex', 'pin': '0.160.0; source ' + PIN,
        'success': True, 'commands': commands, 'upstream_sources': sources,
        'counts': {'suites_passed': 5, 'suites_total': 5, 'tests_passed': 48, 'tests_total': 48, 'filtered_tests': 0},
        'evidence_class': 'local_integration',
        'native_component_execution': 'Real official Codex subprocesses; loopback vendor response fixtures and local protocol only',
        'provider_calls': 0, 'hostwide_install': False,
        'limits': ['The source checkout is the official TypeScript SDK implementation at the release commit; its package.json has0.0.0-dev, not a separately claimed npm SDK release.',
                   'Vendor mocked response tests do not prove real model quality or paid-provider operation.',
                   'No host-wide install, full production harness lifecycle, custom-tool/MCP/hook role qualification, comparative A6 or FINAL admission.',
                   'No third-party model, provider or credential store accessed; scratch processes had a closed environment and isolated HOME/CODEX_HOME.',
                   'Two npm-path attempts and a recorder-overlap/missing-home attempt preserved separately; final receipt uses only7 unique sequential successful steps.'],
        'retry_policy': 'No failed attempt or duplicate step suppressed in this fresh run'})
    invoke = commands[-1]
    write('invoke.json', {
        'kind': 'native_component_invoke', 'component_id': 'codex', 'layer': 'foundation/agent-sdks',
        'pin': '0.160.0; source ' + PIN, 'measured_window': {'start': invoke['started'], 'end': invoke['ended']},
        'command': invoke['command'], 'exit_code': invoke['exit_code'],
        'output': invoke['output'], 'output_sha256': invoke['output_sha256'],
        'method': 'initialize', 'provider_requests': 0, 'thread_or_turn_requests': 0,
        'scope': 'Actual native app-server process and JSON-RPC response, after full vendor SDK suite',
        'qualifies_adoption_window': False,
        'gap': 'Production/adoption-now SDK worker invoke with converged skills/MCP/hooks/memory/telemetry/roles remains unmeasured at this pin; this local handshake is narrow evidence, not a substitute',
        'upstream_source': sources[-1]})
    print(json.dumps({'success': True, 'steps': len(commands), 'tests_passed': 48, 'native_invoke_exit': invoke['exit_code']}))


if __name__ == '__main__':
    main()
