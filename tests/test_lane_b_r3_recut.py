"""The emitted launcher and unit envelopes must carry the r3 contract."""
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch
from tests import test_lane_b_r3_launcher as contracts

ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / 'blueprints/us-equities/paper-lane-latch'
LATCH = ROOT / 'blueprints/us-equities/paper-readiness-seq3'


class RecutR3(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('lane_b_r3_recut_fixture', CODE / 'recut.py')
        self.builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.builder)

    def test_actual_recutter_refuses_recovery_only_from_old_launcher_input(self):
        fixture = contracts.Acceptance()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        original = (ROOT / 'tests/fixtures/pre_skip/launch_seq2.py').read_text()
        text = self.builder.isolate_launch(original, '1' * 64)
        module = types.ModuleType('new_r3_launch')
        module.__file__ = str(fixture.root / 'launch.py')
        with patch.object(sys, 'path', [str(LATCH), *sys.path]):
            exec(compile(text, module.__file__, 'exec'), module.__dict__)
        old = fixture.launch
        for name in ('ROOT', 'FROZEN', 'STATE', 'binding', 'verify_bundle', 'verify_runtime',
                     'writer', 'credential_pointer'):
            setattr(module, name, getattr(old, name))
        fixture.launch = module
        module.keyed = fixture.keyed
        for stage in ('pre', 'sip'):
            with self.subTest(stage=stage), self.assertRaisesRegex(module.Refused, 'recovery_only'):
                module.run_stage(stage)

    def test_generated_units_cover_timeout_plus_recovery_grace(self):
        for stage, normal, runtime in [('pre', 4490, 5150), ('sip', 1190, 1850),
                                       ('lev1', 1190, 1850), ('pre-skip', 120, 780)]:
            with self.subTest(stage=stage):
                action = 'skip' if stage == 'pre-skip' else 'run'
                text = ('[Service]\nWorkingDirectory=/SYN/source\n'
                        'ExecStart=/SYN/source/launch.py ' + action + ' ' + stage + '\n'
                        'RuntimeMaxSec=' + str(normal + 10) + 's\nTimeoutStopSec=900s\n')
                emitted, _ = self.builder.isolate_unit(text, Path('/SYN/source'), Path('/SYN/output'))
                fields = dict(line.split('=', 1) for line in emitted.splitlines() if '=' in line)
                self.assertGreaterEqual(int(fields['RuntimeMaxSec'].removesuffix('s')), runtime)
                if stage != 'pre-skip':
                    self.assertGreaterEqual(int(fields['TimeoutStopSec'].removesuffix('s')), 1380)


if __name__ == '__main__':
    unittest.main()
