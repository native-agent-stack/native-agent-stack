"""Recover one authenticated predecessor GET-only skip; never access STOP.

This entry point uses launch's credential_run boundary, writer lock and fsynced
receipt writer. It cannot call native trading recovery, order/cancel/flatten.
"""
from datetime import datetime, timezone
from pathlib import Path
import re
import subprocess
import time


def recover(launch):
    launch.verify_bundle()
    launch.verify_runtime()
    with launch.writer():
        active_path = launch.STATE / 'active/pre-skip.json'
        if not active_path.exists() and not active_path.is_symlink():
            return 0
        active = launch.safe_json(active_path)
        origin = launch.safe_json(launch.ROOT / 'PREDECESSOR-RECOVERY.json')
        source = Path(origin['source'])
        if (source.is_symlink() or not source.is_absolute()
                or launch.sha(source / 'SHA256SUMS') != origin['bundle_sha256']):
            raise launch.Refused('pre_skip_predecessor_seal_mismatch')
        checked = subprocess.run(['/usr/bin/sha256sum', '--strict', '--quiet', '-c', 'SHA256SUMS'],
                                 cwd=source, capture_output=True)
        if checked.returncode:
            raise launch.Refused('pre_skip_predecessor_manifest_refused')
        required = {'schema_version', 'purpose', 'bundle_sha256', 'config_sha256', 'trial',
                    'session_kind', 'session_date', 'issued_at_utc', 'state_root', 'skip_reason',
                    'instance', 'go_sha256'}
        if (set(active) != required or active['schema_version'] != 1
                or active['purpose'] != 'GET_ONLY_PRE_SKIP'
                or active['skip_reason'] not in launch.SKIP_REASONS
                or not isinstance(active['trial'], str)
                or not re.fullmatch('[a-z0-9-]{1,24}', active['trial'])
                or active['session_kind'] not in ('PRE', 'RTH')
                or not isinstance(active['session_date'], str)
                or not re.fullmatch('[0-9]{4}-[0-9]{2}-[0-9]{2}', active['session_date'])
                or active['bundle_sha256'] != origin['bundle_sha256']
                or active['config_sha256'] != origin['config_sha256']
                or origin['source_config'] != 'configs/pre.json'
                or launch.sha(source / origin['source_config']) != origin['config_sha256']
                or launch.sha(launch.config('pre')) != origin['config_sha256']):
            raise launch.Refused('pre_skip_active_binding_mismatch')
        issued_at = datetime.fromisoformat(active['issued_at_utc'])
        if issued_at.tzinfo is None:
            raise launch.Refused('pre_skip_original_issue_time_invalid')
        instance = launch.STATE / 'instances' / active['trial']
        if (active['instance'] != str(instance) or instance.is_symlink() or not instance.is_dir()
                or active['state_root'] != str(instance / 'native-state')):
            raise launch.Refused('pre_skip_instance_binding_mismatch')
        if (instance / 'active.finished.json').exists() or (instance / 'active.finished.json').is_symlink():
            raise launch.Refused('pre_skip_already_finished_conflict')
        slot = launch.STATE / 'ready/pre-skip'
        token = slot / (active['trial'] + '.GO.used.sha256')
        issued = launch.safe_json(slot / 'GO.json')
        if (token.is_symlink() or not token.is_file()
                or token.read_text().strip() != active['go_sha256']
                or launch.sha(slot / 'GO.json') != active['go_sha256']
                or issued != {key: value for key, value in active.items() if key not in ('instance', 'go_sha256')}
                or (slot / 'GO.sha256').exists() or (slot / 'GO.sha256').is_symlink()):
            raise launch.Refused('pre_skip_original_GO_binding_mismatch')
        # No fresh GO and no risk-reducing order path: native observer reads only.
        output = instance / 'flat-probe.json'
        if output.is_symlink():
            raise launch.Refused('pre_skip_unsafe_proof_destination')
        before = output.stat() if output.exists() else None
        rc, result, proof, proof_hash, error = None, {}, {}, None, None
        phase = 'observer'
        try:
            rc = launch.keyed([launch.PY, '-E', '-s', '-B', launch.ROOT / 'observe_flat.py', 'pre',
                               '--config', launch.config('pre'), '--output', output], timeout=120)
            phase = 'native_proof'
            after = output.stat()
            if before is not None and (before.st_ino, before.st_mtime_ns, before.st_ctime_ns, before.st_size) == (
                    after.st_ino, after.st_mtime_ns, after.st_ctime_ns, after.st_size):
                raise ValueError('stale_native_proof')
            candidate = launch.safe_json(output)
            counts = candidate.get('reconciliation') if isinstance(candidate, dict) else None
            if (not isinstance(counts, dict)
                    or any(type(counts.get(key)) is not int or counts[key] < 0 for key in ('positions', 'open_orders'))
                    or candidate.get('config_sha256') != active['config_sha256']
                    or candidate.get('status') not in ('passed', 'needs_attention')
                    or type(candidate.get('flat')) is not bool
                    or type(candidate.get('open_orders_complete')) is not bool
                    or not isinstance(candidate.get('positions'), list)
                    or not isinstance(candidate.get('unresolved_orders'), list)):
                raise ValueError('invalid_native_proof')
            result, proof, proof_hash = candidate, counts, launch.sha(output)
        except Exception as exc:
            # Exception text may contain private paths/provider response data.
            # Actual rc is null when execution raised (e.g. TimeoutExpired).
            error = {'phase': phase, 'error_class': type(exc).__name__}
        if rc != 0 and error is None:
            error = {'phase': 'observer', 'error_class': 'NonzeroExit'}
        flat = (error is None and rc == 0 and result.get('status') == 'passed' and result.get('flat') is True
                and result.get('config_sha256') == active['config_sha256']
                and result.get('open_orders_complete') is True
                and result.get('positions') == [] and result.get('unresolved_orders') == []
                and proof.get('positions') == 0 and proof.get('open_orders') == 0)
        receipt = {'stage': 'pre', 'trial': active['trial'], 'session_date': active['session_date'],
                   'config_sha256': active['config_sha256'], 'go_sha256': active['go_sha256'],
                   'predecessor_bundle_sha256': active['bundle_sha256'],
                   'original_active_sha256': launch.sha(active_path),
                   'bundle_sha256': launch.sha(launch.ROOT / 'SHA256SUMS'),
                   'native_recover_sha256': proof_hash, 'recover_rc': rc,
                   'native_proof_present': proof_hash is not None, 'observation_error': error,
                   'status': 'passed' if flat else 'needs_attention', 'flat': flat,
                   'positions': proof.get('positions'), 'open_orders': proof.get('open_orders'),
                   'skipped': active['skip_reason'], 'pre_did_not_trade': True,
                   'broker_orders_submitted': 0, 'stop_cleared': False,
                   'boot_id': launch.boot_id(), 'recover_finished_monotonic': time.monotonic(),
                   'recover_finished_at_utc': datetime.now(timezone.utc).isoformat()}
        launch.save(instance / 'recover-validation.json', receipt)
        launch.save(instance / 'handoff.json', receipt)
        if not flat:
            return 2
        launch.save(launch.STATE / 'completed' / active['session_date'] / 'pre.json', receipt)
        active_path.rename(instance / 'active.finished.json')
        return 0
