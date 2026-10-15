"""F2 format adapter, based on the cited Claude-side write_receipts.py and FINAL fixture.

Emits an artifact map; native file edits materialize it. No session store access,
config access, invocation, installation, service change or repository mutation.
"""
from pathlib import Path
import hashlib
import json
import re

HERE = Path(__file__).resolve().parent
ALIASES = {'foundation-ai-memory': 'ai-memory', 'foundation-socraticode': 'socraticode',
           'codex-native-sdk': 'codex'}
PIN_IDS = {'candidate:cli-cli': 'gh', 'candidate:astral-sh-uv': 'uv',
           'nautilustrader': 'nautilus-trader', 'data-pandera': 'pandera',
           'data-duckdb': 'duckdb', 'data-mlflow': 'mlflow', 'data-alpaca-py': 'alpaca-py',
           'data-edgartools': 'edgartools', 'data-exchange-calendars': 'exchange-calendars'}
HOST_IDS = {'worktrunk': 'wt', 'candidate:cli-cli': 'gh', 'candidate:astral-sh-uv': 'uv',
            'difftastic': 'difft', 'systemd': 'systemctl'}
MCP = {'serena', 'qmd', 'ai-memory', 'headroom', 'promptfoo', 'socraticode'}
CLI = {'worktrunk', 'candidate:cli-cli', 'candidate:astral-sh-uv', 'rtk', 'gitleaks',
       'difftastic', 'mcporter', 'mcp-inspector', 'ccusage', 'agent-browser', 'restic',
       'syft', 'zizmor', 'dagu', 'systemd', 'poppler', 'markitdown', 'tavily-cli',
       'openresearch', 'playwright-test'}

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def normalized(repository):
    return repository.lower().removeprefix('https://').removeprefix('http://').removesuffix('.git').rstrip('/')

def main():
    inputs = json.loads((HERE / 'input-provenance.json').read_text())
    counts = json.loads((HERE / 'native-cli-counts.json').read_text())
    host = json.loads((HERE / 'host-versions.json').read_text())
    pins = {p['component']: p for p in inputs['pins']}
    files = {}; decisions = []; table = []
    for ident, row in sorted(inputs['winners'].items()):
        component = ALIASES.get(ident, ident)
        run = row.get('run') or {}; canonical = run.get('pin_parsed') or {}
        pending = pins.get(PIN_IDS.get(component, component)) or {}
        version = pending.get('version') or canonical.get('version')
        commit = pending.get('peeled_commit') if pending.get('status') == 'resolved' else canonical.get('commit')
        pin = (f'{version}; source {commit}' if version and commit else commit or run.get('pin'))
        pending_identity = bool(pending.get('status') == 'resolved' and
                                (canonical.get('commit') != commit or canonical.get('version') != version))
        observation = host.get(HOST_IDS.get(component, component)) or {}
        host_version = (observation.get('version_tokens') or [None])[0]
        mcp_calls = sum(n for server, n in counts['mcp_counts'].items()
                        if server.replace('_', '-').lower() == component.lower()
                        or component == 'socraticode' and server.lower().endswith('_socraticode')) if component in MCP else 0
        cli_calls = counts['cli_counts'].get(component, 0)
        calls = mcp_calls + cli_calls
        if component == 'codex':
            # The client labels its own completed native items with cli_version.
            calls = counts['client_tool_calls_by_version'].get(canonical.get('version'), 0)
        if ident == 'codex-native-sdk':
            # A native client event is not proof its SDK was the caller.
            calls = 0
        scope = 'Codex MCP registration' if component in MCP else 'Codex shell/CLI role' if component in CLI else 'Codex client' if ident == 'codex' else 'runtime SDK caller' if ident == 'codex-native-sdk' else 'skill-loader role' if 'instructions-skills' in ' '.join(row['layers']) else 'runtime/service/CI consumer'
        callable_on_codex = component in MCP or component in CLI or ident == 'codex'
        version_matches = host_version == version if version else False
        positive = calls > 0 and callable_on_codex and bool(pin) and version_matches
        slug = re.sub(r'[^a-z0-9]+', '-', ident.lower()).strip('-')
        measurement = {'counter': 'tools/invocation-monitoring/codex_counter.py',
                       'counter_sha256': '06b569826c76c2dc9455fccd3e004329e71f791483b42b33571fad21910dc8e3',
                       'counter_summary': 'counter-summary.json',
                       'attribution': 'measure_cli.py', 'attribution_sha256': digest(HERE / 'measure_cli.py'),
                       'counts_file': 'native-cli-counts.json', 'counts_sha256': digest(HERE / 'native-cli-counts.json'),
                       'host_versions_file': 'host-versions.json', 'host_versions_sha256': digest(HERE / 'host-versions.json'),
                       'scope': counts['scope'], 'count_is_lower_bound': bool(cli_calls),
                       'organic_use_claim': False}
        base = {'component_id': ident, 'repository': normalized(row['repository']), 'client': 'codex',
                'window_start': counts['window_start'], 'window_end': counts['window_end'],
                'run_id': row.get('run_id'), 'frozen_run_pin': run.get('pin'),
                'frozen_run_pin_parsed': canonical, 'host_version': host_version,
                'host_differs_from_frozen_run': bool(host_version and canonical.get('version') and host_version != canonical['version']),
                'layers': row['layers'], 'consumer': scope,
                'observed_mcp_calls': mcp_calls, 'observed_cli_calls_lower_bound': cli_calls,
                'measurement': measurement}
        if positive:
            path = f'receipts/invoke-{slug}.json'
            value = {**base, 'kind': 'invocation', 'pin': pin, 'calls': calls,
                     'evidence_class': 'native_proven',
                     'unit': 'completed native MCP/CLI attempts; CLI first-executable attribution is a lower bound',
                     'registration_pending': pending_identity, 'pin_pending': not bool(commit),
                     'binds_frozen_run': not pending_identity,
                     'pin_binding': ('Native completed item identity plus installed version/source metadata predating the window; source identity is the retained upstream tag completion. MCP events have no per-call binary-version label; historical registration continuity is not independently attested.' + (' Serena uv-receipt revision c6fbd1c5932df2494ffa0020af5a9fbe80b82143; receipt SHA256 d24fa8ed952a35cddcbabd9018773e1d83deda3715c96a95ac80e12ef06be163; mtime 2026-10-05T16:09:43.989908Z.' if component == 'serena' else '')),
                     'source_pin_table_sha256': inputs['pin_resolution_sha256'],
                     'same_observation_as': component if component != ident else None,
                     'sample_ids': counts['sample_ids'].get('mcp:' + component, []) or counts['sample_ids'].get(component, []),
                     'not_evidence': 'installation alone, organic use, upstream quality, or unseen nested/hook/library execution'}
            disposition = 'invoke-pending-registration' if pending_identity else 'invoke'
        else:
            path = f'reasons/not-invoked-{slug}.json'
            if ident == 'codex':
                reason = ('Consumer Codex client: no current-host invocation receipt binds the frozen run version; '
                          f'initial session metadata version counts are {counts["client_tool_calls_by_version"]}. '
                          'A session header is not a per-call version attestation after resume. '
                          'Missing wiring is run-identity synchronization, not client invocation. Bind a newly screened current client run; do not credit newer-version events to the old pin.')
                disposition = 'host-run-drift'
            elif ident == 'codex-native-sdk':
                reason = 'Consumer runtime SDK worker: native Codex client/exec completion does not identify an SDK caller. No SDK-specific invoke identity is retained by this counter; SDK-worker owner must supply its invoke receipt. Do not infer SDK use from the client being installed or running.'
                disposition = 'other-consumer-attribution-gap'
            elif calls > 0 and not version_matches:
                reason = f'Consumer {scope}: {calls} completed attempts are observed, but current host version {host_version} does not bind the target version {version}. Synchronize the screened run identity or retain this explicit version gap; no invocation receipt at the mismatched run pin is claimed.'
                disposition = 'host-run-drift' if host_version else 'host-identity-unverified'
            elif component in MCP:
                reason = f'Consumer Codex MCP registration: zero completed {component} MCP calls and zero directly attributed CLI calls in the measured native window. Missing recorded wiring is a Codex dispatcher invocation of this enabled endpoint; where the slot row names Codex, this is the CC-defined wiring flag for the owner to fix or retire. Hook/service activity is not represented by this endpoint counter, and is not silently credited.'
                disposition = 'codex-dispatch-wiring-flag'
            elif component in CLI:
                reason = f'Consumer Codex shell/CLI role: zero directly attributed {component} first-executable calls. Nested shell, Python subprocesses and native hooks are not counted by this bounded adapter, so actual execution remains unknown. Missing instrumentation is completed child/hook identity at its run pin. If a slot explicitly names Codex and a complete counter confirms zero, the owner must wire that role or retire it; this partial view alone does not establish a wiring defect.'
                disposition = 'cli-attribution-gap'
            else:
                consumer = 'Claude Code native client/worker slots' if ident == 'claude-code' else 'skills loader' if scope == 'skill-loader role' else 'runtime workers, service or CI roles in ' + ', '.join(row['layers'])
                reason = f'Consumer {consumer}: no Codex MCP/CLI consumer is established for this winner by the frozen row or current Codex registration. This counter does not instrument that consumer; its Codex-call count is not a non-use verdict. Retain the owning consumer receipt or this scoped reason; do not retire a shared role on a Codex zero.'
                if not row.get('run_id'):
                    reason += ' The frozen winner also lacks a run identity, so an exact-pin receipt cannot yet be formed.'
                disposition = 'other-consumer'
            value = {**base, 'kind': 'non_invocation_reason', 'calls': 0,
                     'calls_definition': 'zero eligible calls at the target identity; observed lower bounds retained separately',
                     'not_invoked_reason': reason, 'disposition': disposition, 'target_pin': pin,
                     'source_pin_table_sha256': inputs['pin_resolution_sha256']}
        files[path] = json.dumps(value, indent=2, sort_keys=True) + '\n'
        decisions.append({'id': ident, 'scope': scope, 'calls': calls, 'disposition': disposition,
                          'path': path, 'pin': pin, 'host_version': host_version})
        table.append(f'| {ident} | {scope} | {calls} | {run.get("pin") or "NO RUN"} | {host_version or "unverified/not this client"} | {disposition} | {path} |')
    files['winner-decisions.json'] = json.dumps(decisions, indent=2, sort_keys=True) + '\n'
    files['CODEX-WINNERS.md'] = ('# Frozen winners and Codex consumers\n\n'
        'Inventory: 252babe4040e39173cc178317c67699371806df6, 57 unique component IDs. '
        'Includes every winner so exclusion of a runtime/service/Claude/skill-loader role is explicit. '
        'Codex-side callable winners are the six enabled winner MCP registrations, the native client, '
        'and the named CLI/hook roles. No consumer field was found in the inspected frozen landscape '
        'and installation tables; current Codex registration proves only its MCP consumers. '
        'The CC consumer-scoped zero rule applies only to a slot that explicitly names Codex. '
        'A zero in incomplete CLI instrumentation is not a proved execution zero. '
        'Alias rows use the same observation, and their counts must not be summed.\n\n'
        '| Winner | Consumer/scope reasoning | Eligible/observed calls | Frozen run | Host version | Disposition | Artifact |\n'
        '| --- | --- | ---: | --- | --- | --- | --- |\n' + '\n'.join(table) + '\n')
    print('ARTIFACTS_JSON:' + json.dumps(files, separators=(',', ':')))

if __name__ == '__main__':
    main()
