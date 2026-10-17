"""Offline regression checks; synthetic fixtures are never runtime receipts."""
import hashlib
import json
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load(name):
    return json.loads((HERE / name).read_text())


class EvidenceIntegrityTests(unittest.TestCase):
    def test_every_native_capture_is_bound_without_generated_status(self):
        rows = load('runtime-receipt.json')['commands']
        self.assertEqual([r['n'] for r in rows], list(range(1, 12)))
        for row in rows:
            raw = (HERE / row['output']).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), row['output_sha256'])
            self.assertEqual(row['capture_class'], 'deterministically_masked_native_capture')
            self.assertNotIn(b'"scope": "own scratch only"', raw)
        self.assertIn(b'added 3 packages', (HERE / 'output-03.txt').read_bytes())
        self.assertIn(b'Lockfile is up to date', (HERE / 'output-04.txt').read_bytes())
        self.assertNotEqual((HERE / 'output-03.txt').read_bytes(), (HERE / 'output-04.txt').read_bytes())

    def test_invoke_output_is_native_response_not_driver_summary(self):
        response = load('output-10.txt')
        self.assertEqual(response['id'], 1)
        self.assertIsInstance(response['result'], dict)
        self.assertNotIn('success', response)
        self.assertFalse(load('invoke.json')['qualifies_adoption_window'])

    def test_survivors_never_borrow_codex_runtime_and_no_numeric_scores(self):
        for candidate in load('multi-angle-draft.json')['candidates']:
            self.assertFalse(candidate['final_admitted'])
            self.assertTrue(candidate['pin_citation'])
            self.assertEqual(set(candidate['angles']), {'A1', 'A2', 'A3', 'A4', 'A5', 'A6'})
            for angle in candidate['angles'].values():
                self.assertEqual(angle['score'], 'U')
                self.assertFalse(angle['disputed'])
            if candidate['repository'] != 'https://github.com/openai/codex':
                self.assertNotIn('runtime-receipt.json', candidate['angles']['A1']['sources'])

    def test_pin_citation_supports_each_specific_pin(self):
        root = HERE.parents[2]
        for source in load('pin-reconciliation.json')['sources']:
            if source['kind'] not in {'winner_verdict', 'final_stack_winner', 'run', 'historical_manifest_packet'}:
                continue
            citation = source['citation']
            line = (root / citation['path']).read_text().splitlines()[citation['line'] - 1]
            self.assertIn(source['value'], line)

    def test_all_private_input_seals_stay_outside_public_receipt(self):
        for f in ['runtime-receipt.json', 'check-receipts.json', 'invoke.json']:
            text = (HERE / f).read_text()
            self.assertNotIn('log_sha256', text)
            self.assertNotIn('raw_sha256', text)
            self.assertNotIn('/home/', text)

    def test_historical_host_and_unsupported_snapshots_are_explicit(self):
        pins = load('pin-reconciliation.json')
        host = next(x for x in pins['sources'] if x['kind'] == 'committed_host_capture')
        self.assertEqual(host['value'], 'codex-cli 0.161.0')
        self.assertEqual(host['citation']['line'], 290)
        self.assertTrue(pins['reason_citations'])
        primary = load('primary-source-review.json')
        self.assertEqual(primary['public_snapshots'], [])
        self.assertIsNone(primary['official_docs'])
        self.assertTrue(primary['pin_rule_citation'])
        for candidate in load('multi-angle-draft.json')['candidates']:
            for key in ['A2', 'A3', 'A4']:
                self.assertIsNone(candidate['angles'][key]['note'])
                self.assertFalse(candidate['angles'][key]['sources'])


if __name__ == '__main__':
    unittest.main()
