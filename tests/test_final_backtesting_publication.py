"""Publication custody and recorded-input controls; no engine qualification."""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / 'evidence/artifacts/final-wave-backtesting-engine-20261016'


class BacktestingPublicationTests(unittest.TestCase):
    def test_third_party_code_copies_are_excluded_from_public_artifacts(self):
        names = ['lean-AlpacaBrokerageModelTests.cs.txt', 'nautilus-conftest.py.txt',
                 'nautilus-test_backtest_configs.py.txt',
                 'nautilus-test_backtest_engine_default_ids.py.txt',
                 'nautilus-test_backtest_engine_statistics.py.txt']
        self.assertEqual([], [name for name in names if (ARTIFACT / 'upstream' / name).exists()])

    def test_packet_is_the_current_manifest_generator_output(self):
        packet = json.loads((ARTIFACT / 'layer-packet.json').read_text())
        self.assertNotIn('latest_completed_sweep', packet,
                         'authored sweep paraphrases must not stand in for recorded fields')
        receipt = (ARTIFACT / 'native/lane-packets-oct13.capture').read_text()
        self.assertIn('manifest-20261013.json', receipt.splitlines()[0])
        self.assertIn('COMMAND_EXIT_CODE="0"', receipt.splitlines()[-1])
