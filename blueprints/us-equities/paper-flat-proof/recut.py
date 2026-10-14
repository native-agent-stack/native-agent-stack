"""Seal a new seq2 flat-proof hotfix; no installation/credentials/broker/state.

Adopts the predecessor's native sha256sum seal contract and systemd unit files.
Only captured authenticated runtime bytes supply the output seal.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def rewrite_launch(text, predecessor_sha256):
    # Original seq2 launcher is captured by the source seal, not a public digest.
    text, count = re.subn(r'^PREDECESSOR_BUNDLE = .*$',
                          'PREDECESSOR_BUNDLE = ' + repr(predecessor_sha256), text, count=1, flags=re.M)
    if count != 1:
        raise ValueError('predecessor_assignment_shape')
    old = "    if len(sys.argv) != 3 or sys.argv[2] not in STAGES:\n"
    new = """    if sys.argv[1:] == ['recover', 'pre-skip']:
        try:
            from recover_pre_skip import recover
            return recover(sys.modules[__name__])
        except Exception as exc:
            print('refused:' + (str(exc) if isinstance(exc, Refused) else type(exc).__name__))
            return 2
""" + old
    if text.count(old) != 1:
        raise ValueError('seq2_recovery_dispatch_shape')
    text = text.replace(old, new)
    ast.parse(text)
    return text


def variant_check(bundle):
    """Enumerate direct native transport calls, refusing absent required kwargs.

    Both imported functions and constructors are resolved from frozen ASTs.
    Dynamic **kwargs cannot satisfy absent explicit required keywords.
    """
    bundle = Path(bundle)
    paper = bundle / 'frozen/blueprints/us-equities/adaptive-paper'
    transport = ast.parse((paper / 'transport.py').read_text())
    signatures = {}
    for node in transport.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            signatures[node.name] = {arg.arg for arg, default in zip(node.args.kwonlyargs, node.args.kw_defaults)
                                     if default is None}
        if isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(child, ast.FunctionDef) and child.name == '__init__':
                    signatures[node.name] = {arg.arg for arg, default in zip(child.args.kwonlyargs, child.args.kw_defaults)
                                             if default is None}
    calls = []
    for path in sorted([*bundle.glob('*.py'), *paper.glob('*.py')]):
        if path == paper / 'transport.py':
            continue
        tree = ast.parse(path.read_text())
        aliases, modules = {}, set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == 'transport':
                aliases.update({item.asname or item.name: item.name for item in node.names})
            elif isinstance(node, ast.Import):
                modules.update(item.asname or item.name for item in node.names if item.name == 'transport')
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = None
            if isinstance(node.func, ast.Name):
                name = aliases.get(node.func.id)
            elif (isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name)
                  and node.func.value.id in modules):
                name = node.func.attr
            if name not in signatures:
                continue
            given = {kw.arg for kw in node.keywords if kw.arg is not None}
            calls.append({'file': path.relative_to(bundle).as_posix(), 'line': node.lineno,
                          'function': name, 'required_keyword_only': sorted(signatures[name]),
                          'supplied_keywords': sorted(given),
                          'missing': sorted(signatures[name] - given),
                          'dynamic_kwargs': any(kw.arg is None for kw in node.keywords)})
    return calls


def recut(source, output, expected, source_commit):
    source, output = Path(source).resolve(), Path(output).resolve()
    if not re.fullmatch('[0-9a-f]{64}', expected) or not re.fullmatch('[0-9a-f]{40}', source_commit):
        raise ValueError('explicit_source_bindings_required')
    if output.exists() or output.is_relative_to(source):
        raise ValueError('new_bundle_destination_required')
    if any(char.isspace() for char in str(output)):
        raise ValueError('unit_destination_whitespace_refused')
    inventory = (source / 'SHA256SUMS').read_bytes()
    if sha(inventory) != expected:
        raise ValueError('predecessor_seal_mismatch')
    check = subprocess.run(['/usr/bin/sha256sum', '--strict', '--quiet', '-c', 'SHA256SUMS'],
                           cwd=source, capture_output=True)
    if check.returncode:
        raise ValueError('predecessor_manifest_refused')
    verified = {}
    for row in inventory.decode().splitlines():
        digest, name = row.split('  ', 1)
        if (not re.fullmatch('[0-9a-f]{64}', digest) or Path(name).is_absolute()
                or '..' in Path(name).parts or name in verified or (source / name).is_symlink()):
            raise ValueError('predecessor_inventory_schema')
        raw = (source / name).read_bytes()
        if sha(raw) != digest:
            raise ValueError('predecessor_capture_changed')
        verified[name] = raw
    if not {'launch.py', 'observe_flat.py', 'issue_go.py', 'configs/pre.json'} <= verified.keys():
        raise ValueError('required_predecessor_members_missing')
    output.mkdir(mode=0o700, parents=True)
    payloads = dict(verified)
    payloads['launch.py'] = rewrite_launch(verified['launch.py'].decode(), expected).encode()
    for name in ('observe_flat.py', 'recover_pre_skip.py'):
        payloads[name] = Path(__file__).with_name(name).read_bytes()
    for name in ('DEPLOYMENT.md', 'GO-PROCEDURE.md'):
        payloads[name] = Path(__file__).with_name('README.md').read_bytes()
    origin = {'source': str(source), 'bundle_sha256': expected,
              'config_sha256': sha(verified['configs/pre.json']), 'source_config': 'configs/pre.json'}
    payloads['PREDECESSOR-RECOVERY.json'] = (json.dumps(origin, indent=2) + '\n').encode()
    roots = set()
    for name, raw in payloads.items():
        if name.startswith('units/') and name.endswith('.service'):
            roots.update(re.findall(r'^WorkingDirectory=(.+)$', raw.decode(), re.M))
    if len(roots) != 1:
        raise ValueError('unit_source_root_ambiguous')
    old_root = roots.pop()
    unit_names = []
    for name in list(payloads):
        if not name.startswith('units/'):
            continue
        raw = payloads.pop(name)
        new_name = name.replace('-seq2.', '-seq2-flat.')
        payloads[new_name] = raw.decode().replace(old_root + '/', str(output) + '/').replace(
            'WorkingDirectory=' + old_root + '\n', 'WorkingDirectory=' + str(output) + '\n').replace(
            '-seq2.', '-seq2-flat.').encode()
        unit_names.append(new_name)
    if len(unit_names) != 22:
        raise ValueError('unit_inventory_changed')
    for name, raw in payloads.items():
        path = output / name
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        path.write_bytes(raw)
        original = source / name
        path.chmod(original.stat().st_mode & 0o555 if original.is_file() else 0o400)
    calls = variant_check(output)
    if any(call['missing'] for call in calls):
        raise ValueError('transport_call_contract_refused')
    manifest = ''.join(sha(raw) + '  ' + name + '\n' for name, raw in sorted(payloads.items())).encode()
    (output / 'SHA256SUMS').write_bytes(manifest)
    (output / 'SHA256SUMS').chmod(0o400)
    check = subprocess.run(['/usr/bin/sha256sum', '--strict', '--quiet', '-c', 'SHA256SUMS'],
                           cwd=output, capture_output=True)
    if check.returncode:
        raise ValueError('generated_manifest_refused')
    request = json.loads((source / 'GO-BINDING-REQUEST.json').read_text())
    request.update(bundle_sha256=sha(manifest), predecessor_bundle_sha256=expected,
                   bundle_file_count=len(payloads), deployment_revision='sequencing-v2-flat-proof',
                   native_units_installed=False, native_units_started=False,
                   new_authorization_required=True,
                   recut_reason='CC-authorized GET-only flat proof and predecessor pre-skip recovery hotfix',
                   activation='WAIT for two micro PASS and explicit CC changeover authorization')
    (output / 'GO-BINDING-REQUEST.json').write_text(json.dumps(request, indent=2) + '\n')
    receipt = {'status': 'sealed', 'evidence_class': 'local_integration', 'source_commit': source_commit,
               'predecessor_bundle_sha256': expected, 'bundle_sha256': sha(manifest),
               'manifest_entries': len(payloads), 'unit_count': len(unit_names),
               'frozen_runtime_and_configs_unchanged': True, 'transport_calls': calls,
               'strict_manifest_rc': check.returncode, 'broker_calls': 0, 'credential_reads': 0,
               'unit_installation': False, 'GO_issued': False}
    (output / 'RECUT-RECEIPT.json').write_text(json.dumps(receipt, indent=2) + '\n')
    for name in ('GO-BINDING-REQUEST.json', 'RECUT-RECEIPT.json'):
        (output / name).chmod(0o400)
    for directory in sorted((p for p in output.rglob('*') if p.is_dir()), reverse=True):
        directory.chmod(0o500)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--predecessor-sha256', required=True)
    parser.add_argument('--source-commit', required=True)
    args = parser.parse_args()
    receipt = recut(args.source, args.output, args.predecessor_sha256, args.source_commit)
    print(json.dumps({'status': receipt['status'], 'manifest_entries': receipt['manifest_entries'],
                      'broker_calls': 0, 'unit_installation': False}))


if __name__ == '__main__':
    main()
