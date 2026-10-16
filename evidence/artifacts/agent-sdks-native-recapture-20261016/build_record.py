"""Build this layer's bounded offline FINAL-preparation evidence projection.

No catalog mutation, model dispatch or selection. Scratch inputs are locally
generated executions and allowlisted public primary-source observations.
"""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BASE = '65d66a370d9a5f129662d14c84f2820e940b3a83'
PIN = 'a956835d020762cb2b570053af06f643a11c0ecc'
SOURCES = {}


def read(rel):
    p = ROOT / rel
    b = p.read_bytes()
    SOURCES[rel] = {'sha256': hashlib.sha256(b).hexdigest(), 'bytes': len(b)}
    return b.decode()


def load(rel):
    return json.loads(read(rel))


def cite(rel, needle):
    lines = read(rel).splitlines()
    found = next((i + 1 for i, line in enumerate(lines) if needle in line), None)
    assert found, (rel, needle)
    return {'path': rel, 'line': found, 'base': BASE}


def cite_after(rel, anchor, needle):
    lines = read(rel).splitlines()
    start = next(i for i, line in enumerate(lines) if line.strip() == anchor)
    found = next(i + 1 for i in range(start, len(lines)) if needle in lines[i])
    return {'path': rel, 'line': found, 'base': BASE}


def write(name, obj):
    (HERE / name).write_text(json.dumps(obj, indent=2, sort_keys=True) + '\n')


def pointer(ref):
    path, _, fragment = ref.partition('#')
    obj = load(path)
    for part in fragment.strip('/').split('/') if fragment.strip('/') else []:
        obj = obj[int(part)] if isinstance(obj, list) else obj[part]
    return obj


def main(run_root, primary_root, packet_file):
    RUN = run_root
    PRIMARY = primary_root
    final = load('catalogs/landscape/final-stack.json')
    fi, layer = next((i, l) for i, l in enumerate(final['layers'])
                     if l['catalog'] == 'foundation' and l['layer_id'] == 'agent-sdks')
    ci, catalog = next((i, l) for i, l in enumerate(load('catalogs/landscape/foundation.json')['layers'])
                       if l['layer_id'] == 'agent-sdks')
    run_index, run = next((i, r) for i, r in enumerate(final['runs']) if r['id'] == 'codex')
    assert layer['terminal_state'] is None
    wave = load('catalogs/sota-convergence/layer-verdict-waves.json')
    for w in wave['waves']:
        read(w['path'])
        assert SOURCES[w['path']]['sha256'] == w['sha256']
    ledger = load('catalogs/saturation/ledger.json')
    history = []
    latest = {}
    for si, sweep in enumerate(ledger['sweeps']):
        for li, row in enumerate(sweep['layers']):
            if row['catalog'] != 'foundation' or row['layer_id'] != 'agent-sdks':
                continue
            read(sweep['manifest_ref'])
            if sweep.get('returns_ref'):
                read(sweep['returns_ref'])
            for disposition in ('survived', 'refuted'):
                for candidate in row[disposition]:
                    for vote in ('facts', 'fit'):
                        if candidate.get(vote, {}).get('ref'):
                            pointer(candidate[vote]['ref'])
                    if candidate.get('source_review'):
                        read(candidate['source_review'])
                    latest[candidate['repo'].lower().removesuffix('/')] = {
                        'disposition': disposition, 'sweep_id': sweep['sweep_id'],
                        'ref': f'catalogs/saturation/ledger.json#/sweeps/{si}/layers/{li}'}
            history.append({'sweep_id': sweep['sweep_id'], 'status': sweep['status'],
                            'manifest_ref': sweep['manifest_ref'], 'returns_ref': sweep.get('returns_ref'),
                            'layer_ref': f'catalogs/saturation/ledger.json#/sweeps/{si}/layers/{li}',
                            'survived': row['survived'], 'reopen': row['reopen'], 'votes': row['votes']})
    survivors = sorted(k for k, v in latest.items() if v['disposition'] == 'survived')
    assert survivors == ['https://github.com/agentproto/ts', 'https://github.com/github/copilot-sdk']
    for ref in catalog['evidence_refs'] + catalog['winners'][0]['evidence_refs']:
        read(ref.split('#')[0])
    prior_angles = load('catalogs/landscape/angles/foundation-agent-sdks.json')
    plan = 'docs/decisions/2026-10-15-new-wsl-clean-install-plan.md'
    read(plan)
    pin_inputs = [
        {'kind': 'winner_verdict', 'value': catalog['winners'][0]['pin'],
         'citation': cite_after('catalogs/landscape/foundation.json', '"layer_id": "agent-sdks",', '"pin": "0.155.1"'),
         'json_pointer': f'catalogs/landscape/foundation.json#/layers/{ci}/winners/0'},
        {'kind': 'final_stack_winner', 'value': layer['winners'][0]['verdict_pin'],
         'citation': cite_after('catalogs/landscape/final-stack.json', '"layer_id": "agent-sdks",', '"verdict_pin": "0.155.1"'),
         'json_pointer': f'catalogs/landscape/final-stack.json#/layers/{fi}/winners/0'},
        {'kind': 'run', 'value': run['pin'],
         'citation': cite_after('catalogs/landscape/final-stack.json', '"id": "codex",', '"pin": "0.160.0"'),
         'adoption_citation': cite('adoption/pins-linux-x86_64.json', '"version": "0.160.0"'),
         'json_pointer': f'catalogs/landscape/final-stack.json#/runs/{run_index}'},
        {'kind': 'other_platform_conflict', 'value': run['conflicts'],
         'citation': cite_after('adoption/pins-macos-arm64.json', '"id": "codex",', '0.155.1')},
        {'kind': 'plan_layer_row', 'value': 'reopened; codex; two carried survivors; F1 drift and E2E/invoke gaps',
         'citation': cite(plan, '| `foundation/agent-sdks` |')},
        {'kind': 'plan_observed_cli', 'value': '0.162.1, native installer row unpinned',
         'citation': cite(plan, 'Codex: codex-cli 0.162.1')},
        {'kind': 'historical_original_native_worker', 'value': 'Python openai-codex0.154.0 driving native0.155.1; historical task, not this pin',
         'citation': cite('blueprints/us-equities/workers/receipt.json', '0.155.1')},
        {'kind': 'later_committed_sdk_review_candidate', 'value': 'Python SDK0.160.0 with bundled native CLI0.160.0; historical B3 candidate receipt, not a new runtime adoption',
         'citation': cite('evidence/receipts/omniroute-sdk-worker-0160-20261003.json', '"sdk": "0.160.0"'),
         'source_citation': cite('evidence/receipts/omniroute-sdk-worker-0160-20261003.json', 'a956835d020762cb2b570053af06f643a11c0ecc'),
         'limit': 'The published Python candidate shares this native source pin; this fresh upstream TypeScript test package does not replace or qualify its separate Python worker integration'},
    ]
    pin_inputs.append({'kind': 'read_only_host_version', 'value': None,
                       'gap': 'Earlier observation not captured; no installed-version receipt claimed here. Plan observation has its own source citation.'})
    packet = json.loads(packet_file.read_text())
    packet_winner = next(c for c in packet['candidates'] if c['repository'] == 'https://github.com/openai/codex')
    pin_inputs.append({'kind': 'historical_manifest_packet', 'value': packet_winner.get('pin'),
         'citation': cite_after('catalogs/sota-convergence/manifest-20260929.json', '"layer": "agent-sdks",', '"pin": "0.157.1"'),
                       'limit': 'Historical packet pin differs from current F1 run; packet is a source index, not pin authority'})
    write('pin-reconciliation.json', {
        'base': BASE, 'layer': 'foundation/agent-sdks', 'component': 'codex',
        'proposed_run_pin': '0.160.0; source ' + PIN,
        'reason': 'Preserve current linux F1 run version and exact upstream release commit; newly qualify this assigned run without silently adopting host0.162.1. A unified newer-version change requires its own explicit reconciliation and evidence.',
        'sources': pin_inputs,
        'historical_f1': 'Exact release mapping is cited from the committed SDK source receipt; native source-pin capture independently records the checked-out release commit.',
        'drifts': ['verdict0.155.1 versus run0.160.0', 'macOS0.155.1 versus linux0.160.0',
                    'plan-observed0.162.1 versus run0.160.0; current installed version not captured',
                   'historical packet0.157.1 versus run0.160.0',
                   'historical Python SDK0.154.0 and later Python0.160.0 candidate are distinct wrappers from the official TypeScript SDK source tested here'],
        'catalog_mutated': False, 'FINAL_admitted': False})
    selected_packet = []
    for candidate in packet['candidates']:
        if candidate['repository'].lower() not in {r.lower() for r in survivors} | {'https://github.com/openai/codex'}:
            continue
        selected_packet.append({k: candidate[k] for k in ('name', 'repository', 'pin', 'evidence_refs') if k in candidate})
    write('lane-packet-projection.json', {
        'generated_by': 'tools/sota-convergence/lane_packets.py at ' + BASE,
        'command': 'python3 tools/sota-convergence/lane_packets.py --root . --out <PACKET_SCRATCH> --catalog foundation --manifest catalogs/sota-convergence/manifest-20260929.json --checked-at 2026-10-16 --registered-receipts --manifest-newcomers',
        'generator_output': 'packet-generation.txt',
        'generator_status_capture': 'check-receipts.json',
        'projection': 'Only assigned layer winner and cumulative survivors; no other layer dispatched or researched',
        'layer': 'foundation/agent-sdks', 'requirement': catalog['requirement'],
        'candidates': selected_packet, 'read_dispatch': 'co-op only; no self-dispatched model read'})
    write('resolution.json', {'base': BASE, 'catalog_ref': f'catalogs/landscape/foundation.json#/layers/{ci}',
          'wave': wave, 'covering_sweeps': history, 'latest_sweep': history[-1]['sweep_id'],
          'cumulative_survivors': survivors, 'latest_candidate_outcomes': latest,
          'survivor_disposition': 'carried and disputed, not re-adjudicated; co-op two-family review decides the bounded next comparison or gap disposition',
          'newer_unappended_sweep': 'None supplied or referenced in these current committed inputs; newly retained evidence supersedes before dispatch',
          'preexisting_open_gaps': catalog['open_gaps'],
          'final_admission': 'closed; no terminal-state or angle-registry edit',
          'gate_chain': '#1163 then #1167 then PIN-RULES then opening PR, per common brief; not declared landed here'})

    primary = []
    for filename in sorted(PRIMARY.glob('*-ci.json')) + sorted(PRIMARY.glob('*-community.json')) + sorted(PRIMARY.glob('*-usage.json')):
        value = json.loads(filename.read_text())
        write('sources/' + filename.name, value)
        primary.append('sources/' + filename.name)
    source_candidates = [
        ('openai/codex', PIN, RUN / 'work/codex/sdk/typescript/README.md', 'sdk/typescript/README.md', [5, 10, 21, 22, 31, 100, 104, 105]),
        ('agentproto/ts', '08605fbe43a5c71e65f9561fd1d2b92abcbe9c4c', PRIMARY / 'agentproto-ts.README.md', 'README.md', [5, 26, 52, 169, 170]),
        ('github/copilot-sdk', 'f5d9685f55286061e12763ed15a73c4469609881', PRIMARY / 'copilot-sdk.README.md', 'README.md', [14, 16, 22, 23]),
    ]
    source_records = []
    for repo, pin, path, rel, numbers in source_candidates:
        pin_citation = None
        if repo != 'openai/codex':
            source_file = 'evidence/artifacts/landscape-sweep-20260929/' + ('agentproto-ts.json' if repo == 'agentproto/ts' else 'github-copilot-sdk.json')
            assert load(source_file)['reviewed_commit'] == pin
            pin_citation = cite(source_file, '"reviewed_commit"')
        lines = path.read_text().splitlines()
        excerpts = [{'line': n, 'text': lines[n-1]} for n in numbers if n <= len(lines)]
        source_records.append({'repository': repo, 'pin': pin, 'pin_citation': pin_citation, 'path': rel, 'excerpts': excerpts,
                               'evidence_class': 'source_review', 'target_installed': repo == 'openai/codex'})
    write('primary-source-review.json', {'kind': 'source_review', 'sources': source_records,
          'public_snapshots': primary,
          'official_docs': 'https://developers.openai.com/codex/sdk (fetched; official Node18+ TypeScript thread install/start/continue/resume documentation)',
          'pin_rule': 'Exact upstream release source and vendor tests outrank current mutable docs; snapshots at other times do not prove pin capability'})
    draft = []
    pins = {r[0]: r[1] for r in source_candidates}
    for repo in ['openai/codex', 'agentproto/ts', 'github/copilot-sdk']:
        is_winner = repo == 'openai/codex'
        key = {'openai/codex': 'codex', 'agentproto/ts': 'agentproto', 'github/copilot-sdk': 'copilot'}[repo]
        draft.append({'repository': 'https://github.com/' + repo, 'pin': pins[repo],
            'pin_citation': (source_records[['openai/codex', 'agentproto/ts', 'github/copilot-sdk'].index(repo)]['pin_citation'] if not is_winner else cite('evidence/receipts/omniroute-sdk-worker-0160-20261003.json', 'a956835d020762cb2b570053af06f643a11c0ecc')),
            'role': 'existing winner, pin drift under qualification' if is_winner else 'cumulative survivor, unqualified alternative',
            'screen_status': 'narrow SDK source screen and credential-free execution only' if is_winner else 'retained source review; no new installation screen or runtime test',
            'angles': {
                'A1': {'score': 'U', 'disputed': True, 'sources': ['primary-source-review.json'] + (['runtime-receipt.json'] if is_winner else []),
                       'note': 'Supported CLI-backed TypeScript start/run/resume seam; local mock tests separate from full live harness, custom-tool/MCP/hook/isolation coverage' if is_winner else 'Pinned source advertises required orchestration/session seam; independently qualify same-role fit before promotion'},
                'A2': {'score': 'U', 'disputed': True, 'sources': ['sources/' + key + '-ci.json'],
                       'note': {'codex': 'Recorded release workflow success is not SDK CI success.', 'agentproto': 'Recorded CI success and skipped agent-command workflows have different roles.', 'copilot': 'Recorded Issue Classification Agent succeeds; SDK build/test and CodeQL fail; no cause/capability conclusion follows.'}[key] + ' Historical bounded observations only; no all-history claim or score.'},
                'A3': {'score': 'U', 'disputed': True, 'sources': ['sources/' + key + '-community.json'],
                       'note': 'Historical undated stars/forks snapshot; no at-time or independent consensus claim; fresh capture prerequisite remains'},
                'A4': {'score': 'U', 'disputed': True, 'sources': ['sources/' + key + '-usage.json'] if key != 'agentproto' else [],
                       'note': 'Historical registry requests across versions, not unique users/net usage. Published SDK package is not exact source0.0.0-dev/native CLI artifact; no artifact equivalence. Agentproto row unverified.'},
                'A5': {'score': 'U', 'disputed': True, 'sources': [],
                       'note': 'No matched published evaluation verified at this exact pin for required structured events/custom tools/session control; unknown is not absence, retain fixed weight'},
                'A6': {'score': 'U', 'disputed': True, 'sources': ['runtime-receipt.json', 'invoke.json'] if is_winner else [],
                       'note': 'Fresh local upstream tests and local invoke are A1/local-integration, not comparative A6. Historical workers comparison unresolved and publication-ineligible. No new model/comparison executed'},
            }, 'proposed_disposition': 'GAP pending two-family review, exact pin E2E scope and measured adoption invoke',
            'final_admitted': False, 'score_computed': False})
    write('multi-angle-draft.json', {'kind': 'multi_angle_record_draft', 'catalog': 'foundation',
          'layer_id': 'agent-sdks', 'rule_version': 'angle-convergence/2',
          'weights': prior_angles['weights'], 'weight_citations': {key: cite('catalogs/landscape/angles/foundation-agent-sdks.json', '"' + key + '": ' + str(value)) for key, value in prior_angles['weights'].items()}, 'new_weight_choice': False,
          'published_evaluations_available': None, 'candidates': draft,
          'existing_record_gap': 'Committed angle file covers deep-agents and strands, not the Codex winner plus carried survivors. Preserve it, propose this role-complete delta to co-op.',
          'supersedes_existing_verdict': False, 'adjudication': 'NOT_RUN; two-family reads owned by co-op'})
    write('source-seals.json', {'base': BASE, 'public_repository_inputs': SOURCES,
                               'privacy': 'Only committed public input bytes sealed; no co-op/CC/private record hashes'})
    print(json.dumps({'status': 'prepared', 'winner': 'codex', 'proposed_pin': PIN,
                      'survivors': len(survivors), 'public_inputs': len(SOURCES)}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-root', type=Path, required=True, help='Private native capture root')
    parser.add_argument('--primary-root', type=Path, required=True, help='Private retained primary-source input root')
    parser.add_argument('--packet-file', type=Path, required=True, help='Native generated packet for this layer')
    args = parser.parse_args()
    (HERE / 'sources').mkdir(exist_ok=True)
    main(args.run_root, args.primary_root, args.packet_file)
