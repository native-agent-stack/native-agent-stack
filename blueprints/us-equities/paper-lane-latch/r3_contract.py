"""Apply the canonical launcher contract and enclosing unit budgets to NEW bytes."""
import ast

RECOVERY_GRACE_SECONDS = 50 * (5 + 5) + 120 + 10
ENVELOPE_MARGIN_SECONDS = 30


def launcher(text, canonical):
    """Keep source admission/latch/bindings; replace only keyed and run_stage."""
    expected = ast.parse(canonical)
    methods = {node.name: ast.get_source_segment(canonical, node) for node in expected.body
               if isinstance(node, ast.FunctionDef) and node.name in ('keyed', 'run_stage')}
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
    stop = 720 + RECOVERY_GRACE_SECONDS + ENVELOPE_MARGIN_SECONDS
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
