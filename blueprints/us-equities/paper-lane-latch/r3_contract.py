"""Apply the canonical launcher contract and enclosing unit budgets to NEW bytes."""
import ast
import shlex

# r3 cb0e7d348d564520eb0911476d9d4b0f227952ea transport.py:973;
# recovery.py:94-98,223,329: 50*(5+5) preflight +120 order work +10 teardown.
RECOVERY_GRACE_SECONDS = 50 * (5 + 5) + 120 + 10
ENVELOPE_MARGIN_SECONDS = 30
TEARDOWN_SECONDS = 10


def scheduler(text, bundle):
    """Generate separate deployment glue; never alter the frozen input script."""
    old_root = 'here="$(cd "$(dirname "$0")" && pwd)"'
    if (text.count(old_root) != 1 or text.count('timeout 900 "$PY"') != 1
            or text.count('timeout 120 ') != 2):
        raise ValueError('scheduled_script_source_shape')
    native = bundle / 'frozen/blueprints/us-equities/adaptive-paper'
    text = text.replace(old_root, 'here=' + shlex.quote(str(native)))
    # These are read-only ingestion/qualification steps, before any runner.
    # Give them real hard bounds so the outer ordering proof is arithmetic.
    # Deployed uutils/coreutils 0.10.0, 28b6856d7b215bf844b4223589cb54ade84f5223:
    # src/uu/timeout/src/platform/unix.rs:47-54 creates the separate group;
    # :64-81 installs child PDEATHSIG; :99-119 calls child/group signal APIs.
    # Group KILL has a uucore error-path caveat documented in the decision.
    # src/uucore/src/lib/features/process/unix.rs:119-144 ignores repeated
    # TERM during kill-after without resetting its deadline (:139,143).
    text = text.replace('timeout 120 ', 'timeout --kill-after=1s 120 ')
    after = RECOVERY_GRACE_SECONDS + TEARDOWN_SECONDS + ENVELOPE_MARGIN_SECONDS
    return text.replace('timeout 900 "$PY"', 'timeout --kill-after=' + str(after) + 's 900 "$PY"')


def launcher(text, canonical):
    """Keep source admission/latch/bindings; graft canonical stage contracts."""
    expected = ast.parse(canonical)
    all_methods = {node.name: ast.get_source_segment(canonical, node) for node in expected.body
                   if isinstance(node, ast.FunctionDef)}
    methods = {name: all_methods[name] for name in ('keyed', 'run_stage') if name in all_methods}
    if set(methods) != {'keyed', 'run_stage'}:
        raise ValueError('canonical_launcher_contract_missing')
    nodes = [node for node in ast.parse(text).body if isinstance(node, ast.FunctionDef)
             and node.name in methods]
    if len(nodes) != 2 or {node.name for node in nodes} != set(methods):
        raise ValueError('predecessor_launcher_contract_shape')
    lines = text.splitlines(keepends=True)
    for node in sorted(nodes, key=lambda item: item.lineno, reverse=True):
        lines[node.lineno - 1:node.end_lineno] = [methods[node.name] + '\n']
    result = ''.join(lines)
    helper = all_methods.get('rest_flat_after_stream_failure')
    call = '        rc, output = native_recover(stage, active)\n'
    entry = 'def recover_stage(stage):\n'
    if helper is None or result.count(call) != 1 or result.count(entry) != 1:
        raise ValueError('predecessor_stream_fallback_shape')
    result = result.replace(call, call + '        rc, output = rest_flat_after_stream_failure(stage, active, rc, output)\n')
    result = result.replace(entry, helper + '\n\n' + entry)
    ast.parse(result)
    return result


def unit_envelopes(text):
    starts = [line for line in text.splitlines() if line.startswith('ExecStart=')]
    if len(starts) != 1 or '/launch.py ' not in starts[0]:
        return text
    args = starts[0].split()
    if len(args) < 3 or args[-2] not in ('run', 'skip'):
        return text
    stage = args[-1]
    normal = 4490 if stage == 'pre' else 120 if stage == 'pre-skip' else 1190
    runtime = normal + RECOVERY_GRACE_SECONDS + ENVELOPE_MARGIN_SECONDS
    # The stage recovery hook can do native recovery, then its GET-only
    # no-owned-trial fallback. Leave both child budgets plus teardown/margin.
    stop = (720 + RECOVERY_GRACE_SECONDS) + (120 + RECOVERY_GRACE_SECONDS) + TEARDOWN_SECONDS + ENVELOPE_MARGIN_SECONDS
    updates = {'RuntimeMaxSec': runtime}
    if stage != 'pre-skip':
        updates['TimeoutStopSec'] = stop
    lines, seen = [], set()
    for line in text.splitlines():
        key, separator, raw = line.partition('=')
        if key in updates and separator:
            # Refuse unsupported duration syntax rather than silently shorten it.
            seconds = raw.removesuffix('s')
            if not seconds.isdecimal():
                raise ValueError('unit_duration_seconds_required')
            line = key + '=' + str(max(int(seconds), updates[key])) + 's'
            seen.add(key)
        lines.append(line)
    for key in updates.keys() - seen:
        lines.append(key + '=' + str(updates[key]) + 's')
    return '\n'.join(lines) + '\n'
