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
                    self.assertGreaterEqual(int(fields['TimeoutStopSec'].removesuffix('s')), 2140)

    def test_every_outer_boundary_exceeds_worst_case_recovery_chain(self):
        grace, teardown = 50 * (5 + 5) + 120 + 10, 10
        scheduler = (ROOT / 'blueprints/us-equities/adaptive-paper/scheduled_trial.sh').read_text()
        adapter = getattr(self.builder, 'r3', None)
        if adapter is not None and hasattr(adapter, 'scheduler'):
            scheduler = adapter.scheduler(scheduler, Path('/SYN/bundle'))
        import shlex
        command = next(line for line in scheduler.splitlines() if line.startswith('timeout ') and '900 ' in line)
        words = shlex.split(command.rstrip().removesuffix('\\'))
        after = next((int(w.split('=', 1)[1].removesuffix('s')) for w in words if w.startswith('--kill-after=')), 0)
        paper_hard = 900 + after
        with self.subTest(boundary='timeout wrapper'):
            self.assertGreater(paper_hard, 900 + grace + teardown)
        # Two read-only ingest/gate commands precede the paper runner.
        preparatory = [shlex.split(line.rstrip().removesuffix('\\')) for line in scheduler.splitlines()
                       if line.startswith('timeout ') and '120 ' in line]
        self.assertEqual(len(preparatory), 2)
        prelude_hard = 0
        for index, words in enumerate(preparatory):
            kill_after = next((int(w.split('=', 1)[1].removesuffix('s')) for w in words if w.startswith('--kill-after=')), 0)
            with self.subTest(boundary='read-only prelude hard bound', command=index):
                self.assertGreater(kill_after, 0)
            prelude_hard += 120 + kill_after
        import ast
        canonical = (ROOT / 'tests/fixtures/seq2-launch.txt').read_text()
        functions = {n.name: n for n in ast.parse(canonical).body if isinstance(n, ast.FunctionDef)}
        keyed = functions['keyed']
        def child_timeouts(name):
            return sorted(kw.value.value for n in ast.walk(functions[name]) if isinstance(n, ast.Call)
                          and isinstance(n.func, ast.Name) and n.func.id == 'keyed'
                          for kw in n.keywords if kw.arg == 'timeout' and isinstance(kw.value, ast.Constant))
        stage_deadlines = child_timeouts('run_stage')
        self.assertEqual(stage_deadlines, [1190, 4490])
        native_recovery, = child_timeouts('native_recover')
        fallback, = child_timeouts('recover_stage')
        waits = [kw.value for n in ast.walk(keyed) if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Attribute) and n.func.attr == 'wait'
                 for kw in n.keywords if kw.arg == 'timeout' and isinstance(kw.value, ast.BinOp)]
        actual_grace = 0
        if len(waits) == 1:
            self.assertTrue(all(isinstance(n, (ast.BinOp, ast.Constant, ast.Add, ast.Mult)) for n in ast.walk(waits[0])))
            actual_grace = eval(compile(ast.Expression(waits[0]), 'SYN budget expression', 'eval'), {'__builtins__': {}})
        loader_hard = stage_deadlines[0] + actual_grace
        with self.subTest(boundary='loader'):
            self.assertEqual(actual_grace, grace)
            self.assertGreater(loader_hard, prelude_hard + 900 + grace + teardown)
            self.assertGreater(loader_hard, prelude_hard + paper_hard)
        for stage, runtime, stop in [('pre', 5150, 2140), ('sip', 1850, 2140)]:
            text = ('[Service]\nWorkingDirectory=/SYN/source\nExecStart=/SYN/source/launch.py run ' + stage +
                    '\nRuntimeMaxSec=1200s\nTimeoutStopSec=900s\n')
            emitted, _ = self.builder.isolate_unit(text, Path('/SYN/source'), Path('/SYN/output'))
            fields = dict(line.split('=', 1) for line in emitted.splitlines() if '=' in line)
            main_hard = stage_deadlines[stage == 'pre'] + grace
            recovery_chain = (native_recovery + grace) + (fallback + grace)
            with self.subTest(boundary='RuntimeMaxSec', stage=stage):
                self.assertGreater(int(fields['RuntimeMaxSec'].removesuffix('s')), main_hard + teardown)
            with self.subTest(boundary='TimeoutStopSec', stage=stage):
                self.assertGreater(int(fields['TimeoutStopSec'].removesuffix('s')), recovery_chain + teardown)

    def test_new_scheduler_retains_frozen_script_and_correct_native_root(self):
        import subprocess
        original = (ROOT / 'blueprints/us-equities/adaptive-paper/scheduled_trial.sh').read_text()
        actual = self.builder.r3.scheduler(original, Path('/SYN/new-packet'))
        self.assertIn('here=/SYN/new-packet/frozen/blueprints/us-equities/adaptive-paper', actual)
        self.assertIn('timeout --kill-after=670s 900 "$PY"', actual)
        self.assertEqual(actual.count('timeout --kill-after=1s 120 '), 2)
        self.assertIn('timeout 900 "$PY"', original)
        result = subprocess.run(['/usr/bin/bash', '-n'], input=actual, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
