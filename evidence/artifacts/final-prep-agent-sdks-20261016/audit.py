"""Offline consistency gates for this one-layer preparation record."""
import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def load(name):
    return json.loads((HERE / name).read_text())


def main():
    checks = []
    pins = load('pin-reconciliation.json')
    assert pins['proposed_run_pin'] == '0.160.0; source a956835d020762cb2b570053af06f643a11c0ecc'
    assert pins['FINAL_admitted'] is False and pins['catalog_mutated'] is False
    assert len(pins['drifts']) == 5
    for source in pins['sources']:
        if 'citation' in source:
            citation = source['citation']
            assert citation['base'] == pins['base']
            assert len((ROOT / citation['path']).read_text().splitlines()) >= citation['line']
    checks.append('complete role-distinct pin sources, five drifts and existing run retained')
    resolution = load('resolution.json')
    assert resolution['latest_sweep'] == 'landscape-sweep-20260929'
    assert resolution['cumulative_survivors'] == ['https://github.com/agentproto/ts', 'https://github.com/github/copilot-sdk']
    packet = load('lane-packet-projection.json')
    assert len(packet['candidates']) == 3 and packet['generator_exit_code'] == 0
    checks.append('native packet delta matches winner plus both cumulative survivors')
    draft = load('multi-angle-draft.json')
    assert len(draft['candidates']) == 3
    for candidate in draft['candidates']:
        assert set(candidate['angles']) == {'A1', 'A2', 'A3', 'A4', 'A5', 'A6'}
        assert all(a['disputed'] is True for a in candidate['angles'].values())
        assert candidate['final_admitted'] is False and candidate['score_computed'] is False
    checks.append('all six angles disputed, fixed weights, no verdict promotion or new score')
    runtime = load('runtime-receipt.json')
    assert runtime['success'] is True and len(runtime['commands']) == 7
    assert runtime['counts'] == {'suites_passed': 5, 'suites_total': 5, 'tests_passed': 48, 'tests_total': 48, 'filtered_tests': 0}
    commands = runtime['commands']
    for i, command in enumerate(commands):
        assert command['n'] == i + 1 and command['exit_code'] == 0
        assert not i or command['started'] >= commands[i-1]['ended']
        assert hashlib.sha256((HERE / command['output']).read_bytes()).hexdigest() == command['output_sha256']
    checks.append('seven unique sequential successful commands with published-output hashes')
    invoke = load('invoke.json')
    assert invoke['exit_code'] == 0 and invoke['qualifies_adoption_window'] is False
    assert invoke['thread_or_turn_requests'] == invoke['provider_requests'] == 0
    assert hashlib.sha256((HERE / invoke['output']).read_bytes()).hexdigest() == invoke['output_sha256']
    checks.append('actual native handshake output bound, adoption-window gap not erased')
    for path, seal in load('source-seals.json')['public_repository_inputs'].items():
        raw = (ROOT / path).read_bytes()
        assert len(raw) == seal['bytes'] and hashlib.sha256(raw).hexdigest() == seal['sha256']
    checks.append('all consumed public committed inputs retain exact hashes')
    for path in HERE.rglob('*'):
        if path.is_file() and path.suffix in ('.json', '.md', '.txt'):
            assert not re.search(r'/home/|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', path.read_text())
    checks.append('no home paths or generated session identifiers in publication projections')
    record = {'kind': 'local_integration', 'checks': checks, 'passed': len(checks), 'failed': 0,
              'boundary': 'Evidence consistency only; no model comparison or FINAL admission'}
    (HERE / 'audit.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record))


if __name__ == '__main__':
    main()
