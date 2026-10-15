"""Bounded F2 attribution adapter; counts native completed items, emits no command text.

Reuses the repository's codex_counter owner/dedup/argv semantics. This supplements,
not replaces, its MCP measurement. CLI attribution accepts only a single literal
command without shell operators, redirections, expansions or wrapper traversal.
Nested scripts, wrapper children and hooks stay unknown.
"""
from collections import Counter, defaultdict
from pathlib import Path
import importlib.util
import json
import os
import re
import shlex

REPO = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('counter', REPO / 'tools/invocation-monitoring/codex_counter.py')
counter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(counter)
START = counter.instant('2026-10-13T23:58:06Z')
END = counter.instant('2026-10-14T23:58:06Z')
CLI = {'wt': 'worktrunk', 'gh': 'candidate:cli-cli', 'uv': 'candidate:astral-sh-uv',
       'rtk': 'rtk', 'gitleaks': 'gitleaks', 'difft': 'difftastic', 'qmd': 'qmd',
       'ai-memory': 'ai-memory', 'headroom': 'headroom', 'promptfoo': 'promptfoo',
       'mcporter': 'mcporter', 'mcp-inspector': 'mcp-inspector', 'ccusage': 'ccusage',
       'agent-browser': 'agent-browser', 'restic': 'restic', 'syft': 'syft',
       'zizmor': 'zizmor', 'dagu': 'dagu', 'systemctl': 'systemd',
       'systemd-run': 'systemd', 'pdftotext': 'poppler', 'markitdown': 'markitdown',
       'tavily': 'tavily-cli', 'tvly': 'tavily-cli', 'openresearch': 'openresearch',
       'orx': 'openresearch', 'playwright': 'playwright-test', 'codex': 'codex'}

def executable(command):
    text, unresolved = counter._USAGE.resolve_command(command)
    if unresolved or '\n' in text:
        return [], 'multiline_or_non_posix'
    # Bash performs redirection and expansion before starting a command.
    # shlex is lexical analysis; parent rc0 cannot prove a child started after
    # a failed redirect masked by || true or a compact function definition.
    # Reject these forms even inside quoted arguments: false negatives are
    # acceptable for this bounded attribution; false positives are not.
    if any(char in text for char in '\n\r;&|<>(){}$`\\*?[]#'):
        return [], 'ambiguous_shell_execution'
    try:
        words = shlex.split(text, posix=True)
    except ValueError:
        return [], 'unparsed_shell_command'
    if not words:
        return [], None
    name = os.path.basename(words[0])
    if name in {'env', 'timeout', 'systemd-run'} or '=' in words[0]:
        return [], 'wrapper_or_assignment_unmeasured'
    return [CLI[name]] if name in CLI else [], None

def main():
    roots, aliases, parents = counter.registry('~/.hcom/hcom.db', None)
    homes = counter.discover('~/.codex/sessions', '~/.local/state/native-agent-stack')
    files = sorted({p for home in homes for p in home.rglob('rollout-*.jsonl')})
    metas = {}
    for path in files:
        meta = counter.metadata(path)
        if not meta.get('id'):
            continue
        parent = meta.get('parent_thread_id') or counter._USAGE.thread_spawn_source(meta).get('parent_thread_id')
        if parent:
            parents[meta['id']] = parent
        metas[path] = meta
    def canonical(own):
        visited = set()
        while own not in roots:
            if own in visited:
                return None
            visited.add(own)
            own = parents.get(own) or aliases.get(own)
            if not own:
                return None
        return own
    seen = set()
    counts, mcp, client_versions, diagnostics = Counter(), Counter(), Counter(), Counter()
    samples, pin_labels = defaultdict(list), defaultdict(Counter)
    window_threads = set()
    unregistered_threads = set()
    for path, meta in metas.items():
        own = meta['id']; canon = canonical(own)
        if counter.source_class(path, '~/.codex/sessions') not in {'default_native', 'private_native_home'}:
            continue
        marker = meta.get('subagent_history_start_ordinal')
        snapshot_size = path.stat().st_size
        with path.open(errors='replace') as stream:
            while stream.tell() < snapshot_size:
                line = stream.readline()
                if not line:
                    break
                # Drop irrelevant native record classes before decoding large
                # prompts/results. The final parsed type checks remain below.
                if '"item_completed"' not in line or '"event_msg"' not in line:
                    continue
                if '"CommandExecution"' not in line and '"McpToolCall"' not in line:
                    continue
                stamp_match = re.search(r'"timestamp"\s*:\s*"([^\"]+)"', line[:512])
                if stamp_match:
                    try:
                        if not START <= counter.instant(stamp_match.group(1)) < END:
                            continue
                    except (ValueError, TypeError):
                        pass
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                ordinal = row.get('ordinal')
                if isinstance(marker, int) and (not isinstance(ordinal, int) or 0 < ordinal < marker):
                    continue
                try:
                    stamp = counter.instant(row.get('timestamp', ''))
                except (ValueError, TypeError):
                    continue
                if not START <= stamp < END:
                    continue
                payload = row.get('payload') or {}; item = payload.get('item') or {}
                if row.get('type') != 'event_msg' or payload.get('type') != 'item_completed':
                    continue
                kind, ident = item.get('type'), item.get('id')
                if not ident:
                    continue
                key = (canon or own, kind, ident)
                if key in seen:
                    continue
                seen.add(key); window_threads.add(own)
                if not canon:
                    unregistered_threads.add(own)
                # Calls are completed native tool/command attempts, not assistant text.
                if kind in {'CommandExecution', 'McpToolCall'}:
                    client_versions[meta.get('cli_version') or 'unknown'] += 1
                if kind == 'McpToolCall':
                    server = str(item.get('server'))
                    mcp[server] += 1
                    if len(samples['mcp:' + server]) < 3:
                        samples['mcp:' + server].append({'thread_id': own, 'item_id': ident, 'timestamp': row['timestamp']})
                if kind != 'CommandExecution':
                    continue
                if type(item.get('exit_code')) is not int or item['exit_code'] != 0:
                    diagnostics['non_successful_parent_not_attributed'] += 1
                    continue
                found, unresolved = executable(item.get('command', ''))
                diagnostics['command_completed'] += 1
                if unresolved:
                    diagnostics[unresolved] += 1
                if not found:
                    diagnostics['not_attributed_to_winner'] += 1
                for winner in found:
                    counts[winner] += 1
                    # A version-qualified absolute executable is additional native identity.
                    first = counter._USAGE.shell_script(item.get('command', '')).split(' ', 1)[0]
                    if first.startswith('/'):
                        pin_labels[winner]['absolute_executable'] += 1
                    if len(samples[winner]) < 3:
                        samples[winner].append({'thread_id': own, 'item_id': ident, 'timestamp': row['timestamp']})
    print(json.dumps({'window_start': START.isoformat().replace('+00:00', 'Z'),
                      'window_end': END.isoformat().replace('+00:00', 'Z'),
                      'scope': 'all default/private native roots; current registry aliases for dedup; no organic-use claim',
                      'cli_scope': 'single literal successful parent commands only; child binary identity remains unverified',
                      'cli_execution_verified': False, 'cli_counts': {},
                      'unvalidated_cli_prefix_matches': counts,
                      'mcp_counts': mcp, 'client_tool_calls_by_version': client_versions,
                      'diagnostics': diagnostics,
                      'files_considered': len(metas), 'window_threads': len(window_threads),
                      'unregistered_window_threads': len(unregistered_threads)}, sort_keys=True))

if __name__ == '__main__':
    main()
