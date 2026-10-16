"""Derive claims from published masked captures; never generate native output.

CPython 3.13 json, re, hashlib and pathlib. This is derived metadata, not a
native receipt. The full native captures remain the independently checked inputs.
"""
import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent


def read(name):
    return json.loads((HERE / name).read_text())


def dump(name, value):
    (HERE / name).write_text(json.dumps(value, indent=2) + '\n')


def cite(name, needle):
    lines = (HERE / name).read_text().splitlines()
    return {'path': str(HERE.relative_to(HERE.parents[2]) / name),
            'line': next(i + 1 for i, s in enumerate(lines) if needle in s)}


def main():
    receipt = read('runtime-receipt.json')
    rows = receipt['commands']
    assert len(rows) == 11 and all(r['exit_code'] == 0 for r in rows)
    for row in rows:
        assert hashlib.sha256((HERE / row['output']).read_bytes()).hexdigest() == row['output_sha256']
    tests = (HERE / 'output-09.txt').read_text()
    suites = re.search(r'Test Suites:\s+(\d+) passed, (\d+) total', tests)
    counts = re.search(r'Tests:\s+(\d+) passed, (\d+) total', tests)
    assert suites and counts
    assert suites.groups() == ('5', '5') and counts.groups() == ('48', '48')
    native = read('output-10.txt')
    assert native['id'] == 1 and isinstance(native['result'], dict)
    pin = (HERE / 'output-02.txt').read_text().strip()
    assert pin == 'a956835d020762cb2b570053af06f643a11c0ecc'
    binary = (HERE / 'output-07.txt').read_text().split()[0]
    # Existing public adoption record supplies the comparison digest.
    root = HERE.parents[2]
    adoption = json.loads((root / 'adoption/pins-linux-x86_64.json').read_text())
    codex = next(x for x in adoption['tools'] if x['id'] == 'codex')
    assert binary in codex['install_note']
    lock = read('output-06.txt')
    packages = lock['packages']
    assert packages['node_modules/@openai/codex']['version'] == '0.160.0'
    assert packages['node_modules/@openai/codex-linux-x64']['version'] == '0.160.0-linux-x64'
    assert packages['node_modules/@openai/codex-linux-x64']['integrity']
    assert (HERE / 'output-08.txt').read_bytes() == (HERE / 'output-11.txt').read_bytes() == b''
    dump('invoke.json', {
        'kind': 'derived_native_invoke_index', 'evidence_class': 'local_integration',
        'component_id': 'codex', 'pin': pin,
        'native_capture': 'output-10.txt', 'native_capture_citation': cite('output-10.txt', '"result"'),
        'output_sha256': rows[9]['output_sha256'], 'capture_class': rows[9]['capture_class'],
        'command_with_marked_placeholders': rows[9]['command_with_marked_placeholders'],
        'exit_code': rows[9]['exit_code'], 'started': rows[9]['started'], 'ended': rows[9]['ended'],
        'driver_source': 'native_invoke.py', 'recorder_source': 'recorder.py',
        'qualifies_adoption_window': False,
        'gap': 'No production SDK worker invocation with all converged harness layers; no account/model/thread/turn request.',
        'boundary': 'Captured initialize bytes only; driver rc0 is distinct from terminated app-server process status',
    })
    dump('claim-sources.json', {
        'kind': 'derived_metadata_not_native_output',
        'source_pin': {'value': pin, 'citation': cite('output-02.txt', pin)},
        'version': {'value': 'codex-cli 0.160.0', 'citation': cite('output-05.txt', 'codex-cli')},
        'frozen_lock_install': {'citation': cite('output-04.txt', 'Lockfile is up to date'), 'command_source': 'runtime-receipt.json'},
        'suite_counts': {'passed': 5, 'total': 5, 'citation': cite('output-09.txt', 'Test Suites:')},
        'test_counts': {'passed': 48, 'total': 48, 'citation': cite('output-09.txt', 'Tests:')},
        'binary': {'observed_sha256': binary, 'citation': cite('output-07.txt', binary),
                   'comparison_source': 'adoption/pins-linux-x86_64.json:59',
                   'limit': 'Byte identity with prior public pinned binary; no independent release-signing attestation claim'},
        'source_unchanged': {'outputs': ['output-08.txt', 'output-11.txt'],
                             'support': 'Both full native git diff --exit-code outputs are empty and each rc is0 in runtime-receipt.json'},
        'vendor_contracts': [
            {'repository': 'openai/codex', 'pin': pin, 'path': '.github/workflows/sdk.yml', 'line': 127, 'claim': 'frozen-lockfile install'},
            {'repository': 'openai/codex', 'pin': pin, 'path': '.github/workflows/sdk.yml', 'line': 136, 'claim': 'full SDK package test target'},
            {'repository': 'openai/codex', 'pin': pin, 'path': 'sdk/typescript/tests/testCodex.ts', 'line': 7, 'claim': 'CODEX_EXEC_PATH override'},
            {'repository': 'openai/codex', 'pin': pin, 'path': 'sdk/typescript/tests/testCodex.ts', 'line': 24, 'claim': 'mock-provider fixture'},
            {'repository': 'openai/codex', 'pin': pin, 'path': 'codex-rs/app-server/tests/suite/v2/connection_handling_stdio_tests.rs', 'line': 72, 'claim': 'initialize contract'},
        ],
        'gaps': ['Full production/adoption-window F2', 'Matched comparative A6', 'Survivor runtime qualification',
                 'Undated community snapshot capture metadata', 'Exact-pin net usage', 'Matched published evaluations'],
    })
    # Cite each retained angle observation directly; unknowns remain unknown.
    draft = read('multi-angle-draft.json')
    for candidate in draft['candidates']:
        for key, angle in candidate['angles'].items():
            assert angle['score'] == 'U'
            refs = []
            for source in angle['sources']:
                for i, line in enumerate((HERE / source).read_text().splitlines(), 1):
                    if key == 'A2' and any(t in line for t in ['"conclusion"', '"name"', '"head_sha"']):
                        refs.append({'path': str(HERE.relative_to(root) / source), 'line': i})
                    if key == 'A3' and any(t in line for t in ['"stars"', '"forks"']):
                        refs.append({'path': str(HERE.relative_to(root) / source), 'line': i})
                    if key == 'A4' and any(t in line for t in ['"downloads"', '"package"', '"start"', '"end"']):
                        refs.append({'path': str(HERE.relative_to(root) / source), 'line': i})
            angle['observation_citations'] = refs
    dump('multi-angle-draft.json', draft)
    print('Derived counts, native invoke index, binary comparison and exact observation citations from full captures')


if __name__ == '__main__':
    main()
