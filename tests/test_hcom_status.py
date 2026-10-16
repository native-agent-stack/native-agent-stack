"""Metadata bridge contract; local synthetic inputs, not upstream acceptance."""
import importlib.util
import json
import runpy
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / 'observability/grand-dashboard'
UNIT = ROOT / 'evidence/artifacts/new-wsl-install-plan-20261002/config/ns2604-research-progress.service'
sys.path.insert(0, str(DIRECTORY))
SPEC = importlib.util.spec_from_file_location('hcom_status', DIRECTORY / 'hcom_status.py')
H = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(H)
CANARY = 'owner-keystrokes-canary'
# Stands in for hcom 0.7.28: an explicit --name without a live instance exits 1
# (aannoo/hcom@b2a7c192 src/bootstrap.rs:25-30, src/identity.rs:58). `term --json`
# prints one compact object per answering PTY instance, including the input text and
# screen lines, a blank line between answers, and "[<name>] not responding (port N)"
# for a silent instance, still exiting 0 (src/commands/term.rs:365-384).
FAKE_HCOM = f'''#!/usr/bin/env python3
import json, sys
if "--name" in sys.argv:
    print("Error: Instance 'gore' not found. Run 'hcom start --as gore' to reclaim your identity.", file=sys.stderr)
    sys.exit(1)
if sys.argv[1] == "list":
    print(json.dumps([{{"session_id": "{UUID(int=1)}", "name": "angle-records-benu", "base_name": "benu",
                        "tool": "codex", "status": "listening",
                        "status_context": "tui:prompt-has-text", "status_age_seconds": 10800, "unread_count": 8,
                        "tag": "angle-records", "description": "free text"}}]))
elif sys.argv[1] == "term":
    print("[lupe] not responding (port 41234)")
    print(json.dumps({{"name": "benu", "ready": True, "prompt_empty": False, "input_text": "{CANARY}",
                      "lines": ["{CANARY}"], "size": [40, 120], "cursor": [1, 1]}}))
    print()
    print(json.dumps({{"name": "zuro", "ready": True, "prompt_empty": True, "input_text": "", "lines": []}}))
'''


class HcomStatusTests(unittest.TestCase):
    def test_bridge_lists_without_an_hcom_identity(self):
        """Regression: the default --name gore made every 30 s snapshot exit 1 once that instance stopped."""
        with tempfile.TemporaryDirectory() as directory:
            fake = Path(directory) / 'hcom'
            fake.write_text(FAKE_HCOM)
            fake.chmod(0o700)
            result = subprocess.run([sys.executable, str(DIRECTORY / 'hcom_status.py'), '--hcom-bin', str(fake)],
                                    capture_output=True, text=True, timeout=30)
        self.assertEqual(0, result.returncode, result.stderr)
        rows = json.loads(result.stdout)
        self.assertEqual([('angle-records-benu', 'benu', 'listening', 'tui:prompt-has-text', 8, 'angle-records', True)],
                         [(r['name'], r['base_name'], r['status'], r['status_context'], r['unread_count'], r['tag'],
                           r['prompt_has_text']) for r in rows])
        self.assertNotIn(CANARY, result.stdout)
        self.assertNotIn('description', rows[0])

    def test_installed_unit_template_passes_no_identity(self):
        renderer = runpy.run_path(str(UNIT.parent / 'observability_config.py'))
        command = next(line for line in renderer['render_ports'](UNIT.read_text(), renderer['service_ports']()).splitlines()
                       if 'hcom_status.py' in line)
        self.assertNotIn('--name', command)
        self.assertIn('--push', command)
        self.assertIn('--otlp-url http://127.0.0.1:21318/v1/metrics', command)

    def test_prompt_state_keeps_only_the_boolean(self):
        output = '\n'.join([json.dumps({'name': 'benu', 'prompt_empty': False, 'input_text': CANARY, 'lines': [CANARY]}),
                            '', json.dumps({'name': 'zuro', 'prompt_empty': True}),
                            '', json.dumps({'name': 'bad name', 'prompt_empty': False}),
                            '', json.dumps({'name': 'lupe', 'prompt_empty': 'no'}), '{"name": "trailing"'])
        self.assertEqual({'benu': True, 'zuro': False}, H.prompt_states(output))
        rows = H.snapshot([{'session_id': str(UUID(int=1)), 'name': 'benu', 'status': 'listening',
                            'unread_count': 8}], prompts=H.prompt_states(output))
        text = json.dumps(H.payload(rows, 1_000_000_000))
        self.assertIs(True, rows[0]['prompt_has_text'])
        for forbidden in (CANARY, 'input_text', 'lines'):
            self.assertNotIn(forbidden, text)

    def test_listening_gate_context_is_kept_and_free_text_is_not(self):
        rows = H.snapshot([{'session_id': str(UUID(int=1)), 'name': 'benu', 'status_context': 'tui:prompt-has-text',
                            'tag': 'angle-records'},
                           {'session_id': str(UUID(int=2)), 'name': 'zuro', 'status_context': 'tui:has spaces',
                            'tag': 'free text tag'}])
        self.assertEqual(['tui:prompt-has-text', 'omitted'], [r['status_context'] for r in rows])
        self.assertEqual(['angle-records', None], [r['tag'] for r in rows])
        self.assertEqual(['unknown', 'unknown'], [r['prompt_has_text'] for r in rows])

    def test_a_silent_instance_does_not_hide_the_next_prompt_state(self):
        """Regression: decoding stopped at hcom's not-responding line, so every later PTY lost its state."""
        output = '\n'.join([json.dumps({'name': 'benu', 'prompt_empty': False, 'input_text': CANARY}), '',
                            '[lupe] not responding (port 41234)',
                            json.dumps({'name': 'zuro', 'prompt_empty': True}), ''])
        self.assertEqual({'benu': True, 'zuro': False}, H.prompt_states(output))
        self.assertEqual({'zuro': False}, H.prompt_states('[lupe] not responding (port 41234)\n'
                                                           + json.dumps({'name': 'zuro', 'prompt_empty': True})))

    def test_an_unanswered_prompt_is_unknown_not_empty(self):
        """Regression: a lane without a PTY answer exported null, which Loki renders as "" and the board as 0."""
        rows = H.snapshot([{'session_id': str(UUID(int=1)), 'name': 'tag-benu', 'base_name': 'benu'},
                           {'session_id': str(UUID(int=2)), 'name': 'zuro'}], prompts={'zuro': False})
        self.assertEqual(['unknown', False], [r['prompt_has_text'] for r in rows])
        record = json.loads(H.payload(rows, 1_000_000_000)['streams'][0]['values'][0][1])
        self.assertEqual('unknown', record['prompt_has_text'])

    def test_a_registry_only_row_joins_on_the_bare_instance_name(self):
        """Regression: registry-only rows used the tagged display name {tag}-{name} as base_name."""
        registry = {'canonical_roots': [{'root_id': str(UUID(int=1)), 'lane': 'one', 'name': 'one-abcd'},
                                        {'root_id': str(UUID(int=2)), 'lane': 'two', 'name': 'zeta'}]}
        self.assertEqual(['abcd', 'zeta'], [r['base_name'] for r in H.snapshot([], registry)])

    def test_freshness_gauge_is_one_otlp_json_point(self):
        body = H.gauge_payload(19, 1_000_000_000)
        resource = body['resourceMetrics'][0]
        metric = resource['scopeMetrics'][0]['metrics'][0]
        self.assertEqual({'service.name': 'agent-stack-lanes', 'service.instance.id': 'hcom-status'},
                         {a['key']: a['value']['stringValue'] for a in resource['resource']['attributes']})
        self.assertEqual(('agent_stack_lanes.records', [{'asInt': '19', 'timeUnixNano': '1000000000'}]),
                         (metric['name'], metric['gauge']['dataPoints']))
        self.assertEqual('http://127.0.0.1:21318/v1/metrics', H.otlp_metrics_url('http://127.0.0.1:21318/v1/metrics'))
        for bad in ('http://example.org:21318/v1/metrics', 'http://127.0.0.1:21318/v1/logs'):
            with self.assertRaises(ValueError):
                H.otlp_metrics_url(bad)

    def test_missing_registered_root_is_unknown_and_native_status_joins_by_id(self):
        one = str(UUID(int=1))
        two = str(UUID(int=2))
        roots = {'canonical_roots': [{'root_id': one, 'lane': 'one', 'name': 'one-abcd'},
                                     {'root_id': two, 'lane': 'two', 'name': 'two-efgh'}]}
        native = [{'session_id': one, 'name': 'one-abcd', 'tool': 'codex', 'status': 'active',
                   'status_context': 'tool:list', 'status_age_seconds': 4, 'unread_count': 1,
                   'directory': '/private', 'description': 'unselected'}]
        rows = {row['identity']: row for row in H.snapshot(native, roots)}
        self.assertEqual(2, len(rows))
        self.assertEqual(('one', 'active', 4, 1),
                         tuple(rows[one][key] for key in ('lane', 'status', 'status_age_seconds', 'unread_count')))
        self.assertEqual('unknown', rows[two]['status'])
        self.assertIsNone(rows[two]['unread_count'])
        self.assertNotIn('directory', rows[one])
        self.assertNotIn('description', rows[one])

    def test_arbitrary_context_and_invalid_numbers_are_not_exported(self):
        rows = H.snapshot([{'session_id': str(UUID(int=1)),
                            'name': 'one-abcd', 'status_context': 'arbitrary private text',
                            'status_age_seconds': True, 'unread_count': -1}])
        self.assertEqual('omitted', rows[0]['status_context'])
        self.assertIsNone(rows[0]['status_age_seconds'])
        self.assertIsNone(rows[0]['unread_count'])
        with self.assertRaises(ValueError):
            H.snapshot({'unexpected': []})

    def test_present_then_missing_root_keeps_latest_complete_null_row(self):
        identity = str(UUID(int=1))
        registry = {'canonical_roots': [{'root_id': identity, 'lane': 'one', 'name': 'one-abcd'}]}
        present = H.snapshot([{'session_id': identity, 'name': 'one-abcd', 'tool': 'codex',
                              'status': 'active', 'status_age_seconds': 4, 'unread_count': 7}], registry)
        missing = H.snapshot([], registry)
        import json
        old = json.loads(H.payload(present, 1_000_000_000)['streams'][0]['values'][0][1])
        latest = json.loads(H.payload(missing, 2_000_000_000)['streams'][0]['values'][0][1])
        self.assertEqual(set(old), set(latest))
        self.assertGreater(latest['observed_unix'], old['observed_unix'])
        self.assertEqual('unknown', latest['status'])
        self.assertIsNone(latest['status_age_seconds'])
        self.assertIsNone(latest['unread_count'])

    def test_valid_number_then_unknown_native_number_stays_null(self):
        identity = str(UUID(int=1))
        observed = H.snapshot([{'session_id': identity, 'status': 'active',
                               'status_age_seconds': 0, 'unread_count': 0}])[0]
        unknown = H.snapshot([{'session_id': identity, 'status': 'unknown',
                              'status_age_seconds': None, 'unread_count': None}])[0]
        self.assertEqual(0, observed['unread_count'])
        self.assertIsNone(unknown['unread_count'])
        self.assertIsNone(unknown['status_age_seconds'])


if __name__ == '__main__':
    unittest.main()
