"""Compose the landed #1087 private latch with immutable #1117 flat proofs.

Build-only: no credentials, broker, GO, installation, unit or account action.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[3]
LANDED = '943d5ba27b21aba01df1c2df6f63ef4b7e10fd36'
FLAT_HEAD = '1ebb4d25e140dc1c8bce1b7f2e53c8c74ff575d8'
LATCH = ROOT / 'blueprints/us-equities/paper-readiness-seq3'
FLAT = ROOT / 'blueprints/us-equities/paper-flat-proof'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


upstream = load('landed_latch_recut', LATCH / 'recut.py')
flat = load('fixed_flat_recut', FLAT / 'recut.py')
r3 = load('lane_b_r3_contract', Path(__file__).with_name('r3_contract.py'))


def isolate_launch(text, predecessor, *, canonical=None):
    scoped = upstream.rewrite_launch(text, predecessor, flat.sha(text.encode()))
    canonical = (ROOT / 'tests/fixtures/seq2-launch.txt').read_text() if canonical is None else canonical
    return r3.launcher(scoped, canonical)


def isolate_issuer(text):
    return upstream.rewrite_issuer(text)


def isolate_unit(text, old_root, new_root):
    # #1117 named its generation seq2-flat; normalize before the landed adapter.
    scoped, removed = upstream.rewrite_unit(text.replace('-seq2-flat', '-seq2'), old_root, new_root)
    return r3.unit_envelopes(scoped), removed


def pinned_file(pin, path):
    result = subprocess.run(['git', '-C', str(ROOT), 'cat-file', 'blob', pin + ':' + path],
                            capture_output=True, env={**__import__('os').environ, 'GIT_NO_LAZY_FETCH': '1'})
    if result.returncode:
        raise ValueError('required_published_source_missing')
    return result.stdout


def seal(source, installed, output, source_sha256, installed_sha256, source_commit):
    source, installed, output = Path(source).resolve(), Path(installed).resolve(), Path(output).resolve()
    if installed == output or output.is_relative_to(installed):
        raise ValueError('installed_generation_is_immutable')
    # Bind the reused algorithms/helpers to their reviewed Git pins, not memory.
    for path in ('recut.py', 'lane_latch.py', 'seq2_retirement.py'):
        name = 'blueprints/us-equities/paper-readiness-seq3/' + path
        if (ROOT / name).read_bytes() != pinned_file(LANDED, name):
            raise ValueError('landed_latch_source_pin_mismatch')
    for path in ('recut.py', 'recover_pre_skip.py', 'observe_flat.py', 'README.md'):
        name = 'blueprints/us-equities/paper-flat-proof/' + path
        if (ROOT / name).read_bytes() != pinned_file(FLAT_HEAD, name):
            raise ValueError('flat_fix_source_pin_mismatch')
    if not re.fullmatch('[0-9a-f]{64}', installed_sha256):
        raise ValueError('installed_seal_required')
    installed_inventory = (installed / 'SHA256SUMS').read_bytes()
    if flat.sha(installed_inventory) != installed_sha256:
        raise ValueError('installed_generation_seal_mismatch')
    check = subprocess.run(['sha256sum', '--strict', '--quiet', '-c', 'SHA256SUMS'],
                           cwd=installed, capture_output=True)
    if check.returncode:
        raise ValueError('installed_generation_manifest_refused')
    for name in ('recut.py', 'flat_retirement.py', 'README.md', 'r3_contract.py'):
        path = 'blueprints/us-equities/paper-lane-latch/' + name
        if (ROOT / path).read_bytes() != pinned_file(source_commit, path):
            raise ValueError('recut_commit_binding_mismatch')
    canonical = pinned_file(source_commit, 'tests/fixtures/seq2-launch.txt').decode()
    # Existing #1117 builder authenticates/captures ORIGINAL runtime/config bytes.
    flat.recut(source, output, source_sha256, source_commit)
    payloads = {}
    for line in (output / 'SHA256SUMS').read_text().splitlines():
        digest, name = line.split('  ', 1)
        raw = (output / name).read_bytes()
        if flat.sha(raw) != digest:
            raise ValueError('intermediate_verified_bytes_changed')
        payloads[name] = raw
    for name, raw in payloads.items():
        if name.startswith(('frozen/', 'configs/')):
            if not (installed / name).is_file() or (installed / name).read_bytes() != raw:
                raise ValueError('installed_runtime_or_config_differs')
    payloads['launch.py'] = isolate_launch(payloads['launch.py'].decode(), installed_sha256,
                                         canonical=canonical).encode()
    payloads['issue_go.py'] = isolate_issuer(payloads['issue_go.py'].decode()).encode()
    for name in ('lane_latch.py', 'seq2_retirement.py'):
        payloads[name] = (LATCH / name).read_bytes()
    payloads['flat_retirement.py'] = Path(__file__).with_name('flat_retirement.py').read_bytes()
    # The shared seq3 inventory remains untouched for its separately assigned PR.
    payloads['launch.py'] = payloads['launch.py'].replace(
        b'from seq2_retirement import assert_retired', b'from flat_retirement import assert_retired')
    notes = Path(__file__).with_name('README.md').read_bytes()
    for name in ('DEPLOYMENT.md', 'GO-PROCEDURE.md'):
        payloads[name] = notes
    units = [name for name in payloads if name.startswith('units/')]
    removed = 0
    for name in units:
        text, count = isolate_unit(payloads.pop(name).decode(), output, output)
        removed += count
        new_name = name.replace('-seq2-flat.', '-seq3.')
        payloads[new_name] = text.encode()
    if removed != 8:
        raise ValueError('expected_eight_host_touches')
    # The intermediate packet belongs solely to this new build destination.
    # Only verified payload snapshots are used; final digest never certifies a reread.
    for directory in sorted((p for p in output.rglob('*') if p.is_dir())):
        directory.chmod(0o700)
    for name in units:
        (output / name).unlink()
    for name, raw in payloads.items():
        path = output / name
        if path.exists():
            path.chmod(0o600)
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        path.write_bytes(raw)
        original = source / name
        path.chmod(original.stat().st_mode & 0o555 if original.is_file() else 0o400)
    inventory = ''.join(flat.sha(raw) + '  ' + name + '\n' for name, raw in sorted(payloads.items())).encode()
    manifest = output / 'SHA256SUMS'
    manifest.chmod(0o600)
    manifest.write_bytes(inventory)
    manifest.chmod(0o400)
    check = subprocess.run(['sha256sum', '--strict', '--quiet', '-c', 'SHA256SUMS'],
                           cwd=output, capture_output=True)
    if check.returncode:
        raise ValueError('final_latch_seal_refused')
    request_path = output / 'GO-BINDING-REQUEST.json'
    request = json.loads(request_path.read_text())
    request.update(bundle_sha256=flat.sha(inventory), predecessor_bundle_sha256=installed_sha256,
                   bundle_file_count=len(payloads), deployment_revision='lane-b-private-stage-latch',
                   activation='TONIGHT SESSION BOUNDARY only after Astra + CC micro and explicit CC authorization',
                   retirement='Retire every seq2 AND seq2-flat path/service first; no active trial or pending GO')
    request_path.chmod(0o600)
    request_path.write_text(json.dumps(request, indent=2) + '\n')
    request_path.chmod(0o400)
    receipt = {'status': 'sealed', 'source_commit': source_commit, 'latch_source_commit': LANDED,
               'flat_proof_source_commit': FLAT_HEAD, 'bundle_sha256': flat.sha(inventory),
               'predecessor_bundle_sha256': installed_sha256, 'original_source_sha256': source_sha256,
               'manifest_entries': len(payloads), 'removed_host_touches': removed,
               'runtime_and_configs_equal_installed': True, 'broker_calls': 0, 'unit_installation': False}
    receipt_path = output / 'RECUT-RECEIPT.json'
    receipt_path.chmod(0o600)
    receipt_path.write_text(json.dumps(receipt, indent=2) + '\n')
    receipt_path.chmod(0o400)
    for directory in sorted((p for p in output.rglob('*') if p.is_dir()), reverse=True):
        directory.chmod(0o500)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'installed', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    for name in ('source-sha256', 'installed-sha256', 'source-commit'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    result = seal(args.source, args.installed, args.output, args.source_sha256, args.installed_sha256, args.source_commit)
    print(json.dumps({'status': result['status'], 'manifest_entries': result['manifest_entries'],
                      'removed_host_touches': result['removed_host_touches'], 'unit_installation': False}))


if __name__ == '__main__':
    main()
