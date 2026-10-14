"""Read the materialized units, prove stage/hook/bounds and absence of timers."""
from pathlib import Path
import shlex
import tempfile
import shutil
import unittest

ROOT=Path(__file__).resolve().parent

class Units(unittest.TestCase):
    def test_runtime_contract_refuses_incomplete_marker_or_metadata(self):
        import launch
        with tempfile.TemporaryDirectory() as folder:
            runtime=Path(folder)/'runtime';(runtime/'.venv').mkdir(parents=True)
            for name,value in {'.trading-2604-owner':'native-stack-trading-2604-v1',
                               '.trading-2604-complete':'native-stack-trading-2604-no-dvc-r4'}.items():
                (runtime/name).write_text(value+'\n')
            for name in ['pyproject.toml','uv.lock']:
                shutil.copyfile(ROOT/'frozen/blueprints/us-equities/runtime-2604/trading-2604-runtime'/name,runtime/name)
            launch.verify_runtime(runtime)
            (runtime/'.trading-2604-complete').unlink()
            with self.assertRaisesRegex(launch.Refused,'runtime_marker'):launch.verify_runtime(runtime)
            (runtime/'.trading-2604-complete').write_text('native-stack-trading-2604-no-dvc-r4\n')
            (runtime/'uv.lock').write_text('partial')
            with self.assertRaisesRegex(launch.Refused,'runtime_metadata'):launch.verify_runtime(runtime)

    def test_all_order_services_bind_correct_stage_bounds_and_stop_recovery_order(self):
        for stage in ['pre','sip','lev1','lev2','lev4','edge2','edge8','iex']:
            name='paper-ready-'+stage+'-8c95a50d-seq2'
            service=(ROOT/'units'/(name+'.service')).read_text().splitlines()
            fields=[line for line in service if '=' in line and not line.startswith('#')]
            self.assertIn('RuntimeMaxSec='+('4500s' if stage=='pre' else '1200s'),fields)
            for expected in ['CPUWeight=50','UMask=0077','KillMode=control-group',
                             'OnFailure=paper-alert@%n.service','TimeoutStopSec=900s']:
                self.assertIn(expected,fields)
            starts=[line for line in fields if line.startswith('ExecStart=')]
            self.assertEqual(len(starts),1)
            self.assertTrue(starts[0].endswith('launch.py run '+stage))
            hooks=[line for line in fields if line.startswith('ExecStopPost=')]
            self.assertEqual(len(hooks),3)
            self.assertTrue(hooks[0].endswith('stop-mark '+stage))
            self.assertIn('touch --no-dereference',hooks[1])
            self.assertTrue(hooks[2].endswith('recover '+stage))
            path=(ROOT/'units'/(name+'.path')).read_text()
            self.assertIn('/ready/'+stage+'/GO.sha256',path)
            self.assertIn('Unit='+name+'.service',path)

    def test_data_units_cannot_touch_stop_or_call_order_launcher_and_no_timers_exist(self):
        for kind in ['record','scan']:
            service=(ROOT/'units'/('paper-ready-'+kind+'-8c95a50d-seq2.service')).read_text()
            self.assertIn('launch_data.py '+kind,service)
            commands='\n'.join(line for line in service.splitlines() if not line.startswith('#'))
            self.assertNotIn('touch',commands)
            self.assertNotIn('launch.py run',service)
        skip=(ROOT/'units/paper-ready-pre-skip-8c95a50d-seq2.service').read_text()
        self.assertIn('launch.py skip pre-skip',skip)
        self.assertNotIn('ExecStopPost=',skip)
        self.assertNotIn('launch.py run',skip)
        self.assertEqual(len(list((ROOT/'units').glob('*.service'))),11)
        self.assertEqual(len(list((ROOT/'units').glob('*.path'))),11)
        self.assertEqual(list((ROOT/'units').glob('*.timer')),[])
        for file in (ROOT/'units').iterdir():self.assertNotIn('OnCalendar=',file.read_text())

if __name__=='__main__':unittest.main(verbosity=2)
