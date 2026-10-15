"""Run the frozen FINAL receipt predicates; explicitly separate prospective F1 binding.

Reference: Claude-side check_receipts.py SHA256 ddee6f90123072a4f4f580c418607cd32e9aa5b0e3dd30b902e0b3884afa8c33.
This does not promote a layer or run the whole FINAL stack protocol.
"""
from pathlib import Path
import ast
import hashlib
import json
import re
import subprocess
import sys
import types

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[3]
REF = '252babe4040e39173cc178317c67699371806df6'

def main():
    sys.path.insert(0, str(REPO / 'scripts'))
    # Use the pinned protocol's own sibling dependencies, without checkout or
    # changing the held worktree. These modules are loaded from git objects.
    for name in ('host_receipts', 'angle_records'):
        source = subprocess.run(['git', 'show', REF + ':scripts/' + name + '.py'], cwd=REPO,
                                capture_output=True, check=True).stdout
        dependency = types.ModuleType(name)
        dependency.__file__ = str(REPO / 'scripts' / (name + '.py'))
        sys.modules[name] = dependency
        exec(compile(source, dependency.__file__, 'exec'), dependency.__dict__)
    sys.path.insert(0, str(REPO / 'scripts'))
    raw = subprocess.run(['git', 'show', REF + ':scripts/final_stack.py'], cwd=REPO,
                         capture_output=True, check=True).stdout
    module = types.ModuleType('frozen_f2_final_stack')
    module.__file__ = str(REPO / 'scripts/final_stack.py')
    sys.modules[module.__name__] = module
    # Execute the verbatim pinned functions and their pin grammar, without
    # importing unrelated generator dependencies from this older worktree.
    tree = ast.parse(raw)
    names = {'VERSION', 'COMMIT', 'COMMIT_PATTERN', 'PIN_FORMS', 'UNPINNED'}
    nodes = [node for node in tree.body if
             isinstance(node, ast.FunctionDef) and node.name in {'parse_pin', 'complete_final_pin'}
             or isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id in names for target in node.targets)]
    module.__dict__.update(re=re, angle_records=sys.modules['angle_records'], host_receipts=sys.modules['host_receipts'])
    exec(compile(ast.Module(body=nodes, type_ignores=[]), module.__file__, 'exec'), module.__dict__)
    inputs = json.loads((HERE / 'input-provenance.json').read_text())
    decisions = json.loads((HERE / 'winner-decisions.json').read_text())
    pins = {p['component']: p for p in inputs['pins']}
    import build_packet
    failures = []; checked = []; controls = []
    for decision in decisions:
        ident = decision['id']; source = inputs['winners'][ident]
        value = json.loads((HERE / decision['path']).read_text())
        if not decision['path'].startswith('receipts/'):
            if not isinstance(value.get('not_invoked_reason'), str) or not value['not_invoked_reason'].strip():
                failures.append(ident + ': empty non-invocation reason')
            continue
        frozen = source['run']
        component = build_packet.ALIASES.get(ident, ident)
        pin_row = pins.get(build_packet.PIN_IDS.get(component, component)) or {}
        prospective = dict(frozen)
        if pin_row.get('status') == 'resolved':
            prospective['pin_parsed'] = {'version': pin_row['version'], 'commit': pin_row['peeled_commit']}
            prospective['pin'] = f'{pin_row["version"]}; source {pin_row["peeled_commit"]}'
        run = prospective if value.get('registration_pending') else frozen
        try:
            start, end = (module.angle_records.timestamp(value[k]) for k in ('window_start', 'window_end'))
            valid_window = start.tzinfo is not None and end.tzinfo is not None and start < end
        except (KeyError, TypeError, ValueError, module.angle_records.AngleRecordError):
            valid_window = False
        ok = (value.get('kind') == 'invocation' and value.get('evidence_class') == 'native_proven'
              and module.host_receipts.normalize_repository(value.get('repository')) == module.host_receipts.normalize_repository(source['repository'])
              and module.complete_final_pin(value.get('pin'), run)
              and valid_window and value['window_start'].endswith('Z') and value['window_end'].endswith('Z')
              and type(value.get('calls')) is int and value['calls'] > 0)
        frozen_match = module.complete_final_pin(value.get('pin'), frozen)
        if not ok:
            failures.append(ident + ': condition-4 predicate failure')
        if value.get('binds_frozen_run') != frozen_match:
            failures.append(ident + ': frozen binding flag differs from native predicate')
        checked.append({'id': ident, 'status': 'PASS' if ok else 'FAIL', 'calls': value['calls'],
                        'matches_frozen_run': frozen_match,
                        'matches_prospective_F1_run': module.complete_final_pin(value.get('pin'), prospective)})
        parsed = run.get('pin_parsed') or {}
        if parsed.get('commit'):
            bare = parsed.get('version') or '0.0.0'
            controls.append({'id': ident, 'omitted_commit_rejected': not module.complete_final_pin(bare, run),
                             'wrong_commit_rejected': not module.complete_final_pin(bare + '; source ' + '0' * 40, run)})
    if len(decisions) != len(inputs['winners']) or {x['id'] for x in decisions} != set(inputs['winners']):
        failures.append('winner coverage mismatch')
    if any(not x['omitted_commit_rejected'] or not x['wrong_commit_rejected'] for x in controls):
        failures.append('negative pin control accepted')
    print(json.dumps({'checked_against': REF, 'final_stack_source_sha256': hashlib.sha256(raw).hexdigest(),
                      'receipts': checked, 'non_invocation_reasons': len(decisions) - len(checked),
                      'negative_controls': controls, 'failures': failures,
                      'limit': 'predicate/shape validation only; pending pin records are not registered FINAL evidence'}, sort_keys=True))
    return bool(failures)

if __name__ == '__main__':
    sys.exit(main())
