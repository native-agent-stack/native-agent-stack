"""Complete lifecycle wiring drill, scratch GO/state/latch and intercepted keyed calls.

Never starts systemd, reads a credential, or sends a broker/data request.
Native CLI bodies are separately tested from the same sealed source archive.
"""
from datetime import datetime,timezone,timedelta
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import launch
import launch_data

class Wiring(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.bundle=self.root/'bundle'
        self.bundle.mkdir()
        shutil.copytree(ROOT/'configs',self.bundle/'configs')
        (self.bundle/'input.txt').write_text('immutable fixture\n')
        digest=launch.sha(self.bundle/'input.txt')
        (self.bundle/'SHA256SUMS').write_text(digest+'  input.txt\n')
        self.state=self.root/'state'
        self.state.mkdir()
        self.stop=self.root/'STOP'
        self.calls=[]
        self.kind='PRE'
        self.now=datetime(2026,10,12,11,0,tzinfo=timezone.utc)
        self.monotonic=1000.0
        for name,value in [('ROOT',self.bundle),('STATE',self.state),('STOP',self.stop)]:
            controller=patch.object(launch,name,value)
            controller.start();self.addCleanup(controller.stop)
        for controller in [patch.object(launch,'session_now',side_effect=lambda:(self.kind,'2026-10-12')),
                           patch.object(launch,'verify_runtime',return_value=None),
                           patch.object(launch,'record_units',return_value=[
                               {'Id':'paper-ready-record-fixture.service','ActiveState':'inactive'}]),
                           patch.object(launch.time,'time',side_effect=lambda:self.now.timestamp()),
                           patch.object(launch.time,'monotonic',side_effect=lambda:self.monotonic),
                           patch.object(launch,'keyed',side_effect=self.keyed)]:
            controller.start();self.addCleanup(controller.stop)
        launch.save(self.state/'reference-trading-last.json',
                    {'boot_id':launch.boot_id(),'finished_monotonic':900.0})

    def keyed(self,command,*,timeout,environment=None):
        argv=list(map(str,command));self.calls.append((argv,timeout))
        self.assertNotIn('install-trading-2604.sh',' '.join(argv))
        if 'recover' in argv or 'observe_flat.py' in ' '.join(argv):
            output=Path(argv[argv.index('--output')+1])
            output.write_text(json.dumps({'status':'passed','flat':True,'positions':[],
                                         'unresolved_orders':[],
                                         'reconciliation':{'positions':0,'open_orders':0}}))
        return 0

    def token(self,stage,**overrides):
        slot=self.state/'ready'/stage
        slot.mkdir(parents=True,exist_ok=True)
        trial='fixture-'+stage
        value={'schema_version':1,'bundle_sha256':launch.sha(self.bundle/'SHA256SUMS'),
               'config_sha256':launch.sha(launch.config(stage)),'stage':stage,'trial':trial,
               'session_kind':self.kind,'session_date':'2026-10-12','issued_at_utc':self.now.isoformat(),
               'state_root':str(self.state/'instances'/trial/'native-state'),
               'scan_sha256':None,'previous_recover_sha256':None}
        if stage=='pre':
            (slot/'scan.json').write_text('{"kind":"synthetic_hash_fixture"}\n')
            value['scan_sha256']=launch.sha(slot/'scan.json')
        elif stage in launch.STAGES:
            previous=launch.STAGES[launch.STAGES.index(stage)-1]
            path=self.state/'completed/2026-10-12'/(previous+'.json')
            if path.exists():value['previous_recover_sha256']=launch.sha(path)
        value.update(overrides)
        (slot/'GO.json').write_text(json.dumps(value))
        (slot/'GO.sha256').write_text(launch.sha(slot/'GO.json')+'\n')
        return value

    def finish(self,stage):
        launch.stop_mark(stage)
        self.stop.touch()  # Actual native unit's touch, scratch latch only.
        self.assertEqual(launch.recover_stage(stage),0)
        self.assertFalse(self.stop.exists())
        self.monotonic+=61

    def test_whole_pre_then_seven_rth_config_sequence_with_recover_between(self):
        for stage in launch.STAGES:
            self.kind='PRE' if stage=='pre' else 'RTH'
            if stage=='sip':
                launch.save(self.state/'data-completed/record.json',
                            {'session_date':'2026-10-12','finished':True})
                launch.record_quiescence();self.monotonic+=61
            self.token(stage)
            self.assertEqual(launch.run_stage(stage),0)
            self.assertTrue((self.state/'active'/(stage+'.json')).is_file())
            self.finish(stage)
        self.assertEqual(len(self.calls),16)
        self.assertIn('mover_runner.py',' '.join(self.calls[0][0]))
        for index in range(2,16,2):self.assertIn('scheduled_trial.sh',' '.join(self.calls[index][0]))
        for index in range(1,16,2):self.assertIn('recover',self.calls[index][0])
        self.assertEqual(len(list((self.state/'completed/2026-10-12').glob('*.json'))),8)

    def test_go_missing_wrong_hash_expired_future_or_wrong_session_never_calls_keyed(self):
        for mutation in ['hash','expired','future','session','state','config']:
            with self.subTest(mutation=mutation):
                value=self.token('pre')
                slot=self.state/'ready/pre'
                if mutation=='hash':(slot/'GO.sha256').write_text('0'*64)
                elif mutation=='expired':self.token('pre',issued_at_utc=(self.now-timedelta(seconds=301)).isoformat())
                elif mutation=='future':self.token('pre',issued_at_utc=(self.now+timedelta(seconds=1)).isoformat())
                elif mutation=='session':self.token('pre',session_kind='RTH')
                elif mutation=='state':self.token('pre',state_root='/unowned')
                elif mutation=='config':self.token('pre',config_sha256='0'*64)
                with self.assertRaises(launch.Refused):launch.run_stage('pre')
        self.assertEqual(self.calls,[])
        self.assertFalse(self.stop.exists())

    def test_bundle_tampering_refuses_before_go_or_keyed_command(self):
        self.token('pre')
        (self.bundle/'input.txt').write_text('changed')
        with self.assertRaisesRegex(launch.Refused,'bundle_hash_mismatch'):launch.run_stage('pre')
        self.assertEqual(self.calls,[])

    def test_prior_recovery_and_recorder_completion_are_real_handoff_inputs(self):
        self.kind='RTH';self.token('sip')
        with self.assertRaisesRegex(launch.Refused,'previous_recover'):launch.run_stage('sip')
        self.assertEqual(self.calls,[])

    def test_actual_request_window_must_drain_before_independent_next_journal(self):
        self.token('pre');launch.run_stage('pre');self.finish('pre')
        self.monotonic-=61
        self.kind='RTH';self.token('sip')
        with self.assertRaisesRegex(launch.Refused,'request_window'):launch.run_stage('sip')
        self.assertEqual(len(self.calls),2)

    def test_writer_excludes_competing_entry_and_scan_hash_tamper_refuses(self):
        self.token('pre')
        with launch.writer():
            with self.assertRaisesRegex(launch.Refused,'writer_busy'):launch.run_stage('pre')
        (self.state/'ready/pre/scan.json').write_text('changed')
        with self.assertRaisesRegex(launch.Refused,'scan_binding'):launch.run_stage('pre')
        self.assertEqual(self.calls,[])

    def test_process_death_still_has_durable_active_and_own_hook_recovers(self):
        self.token('pre')
        with patch.object(launch,'keyed',side_effect=TimeoutError('synthetic process death')):
            with self.assertRaises(TimeoutError):launch.run_stage('pre')
        self.assertTrue((self.state/'active/pre.json').is_file())
        self.finish('pre')
        self.assertEqual(len(self.calls),1)

    def test_foreign_existing_stop_is_not_cleared_by_our_flat_recovery(self):
        self.token('pre');launch.run_stage('pre')
        self.stop.touch()
        launch.stop_mark('pre')
        self.assertEqual(launch.recover_stage('pre'),0)
        self.assertTrue(self.stop.exists())

    def test_nonflat_recovery_does_not_clear_stop_or_publish_completed(self):
        self.token('pre');launch.run_stage('pre');launch.stop_mark('pre')
        def not_flat(stage,active):
            output=Path(active['instance'])/'recover.json'
            output.write_text(json.dumps({'status':'needs_attention','flat':False,'positions':[{}],
                                        'unresolved_orders':[],'reconciliation':{'positions':1,'open_orders':0}}))
            return 3,output
        with patch.object(launch,'native_recover',side_effect=not_flat):
            with self.assertRaisesRegex(launch.Refused,'recovery_not_flat'):launch.recover_stage('pre')
        self.assertTrue(self.stop.exists())
        self.assertTrue((self.state/'active/pre.json').exists())
        self.assertFalse((self.state/'completed/2026-10-12/pre.json').exists())

    def test_owned_recover_receipt_is_saved_before_stop_can_be_cleared(self):
        self.token('pre');launch.run_stage('pre');launch.stop_mark('pre')
        original=Path.unlink
        def observed_unlink(path,*args,**kwargs):
            if path==self.stop:
                proof=self.state/'instances/fixture-pre/recover-validation.json'
                self.assertTrue(proof.is_file(),'own recover validation must precede STOP unlink')
                self.assertTrue(json.loads(proof.read_text())['flat'])
            return original(path,*args,**kwargs)
        with patch.object(Path,'unlink',observed_unlink):
            self.assertEqual(launch.recover_stage('pre'),0)

    def test_no_owned_trial_uses_get_only_flat_proof_and_own_receipt(self):
        self.token('pre');launch.run_stage('pre');launch.stop_mark('pre')
        def no_owner(stage,active):
            output=Path(active['instance'])/'recover.json'
            output.write_text(json.dumps({'reason':'no_owned_trial_to_recover'}))
            return 3,output
        with patch.object(launch,'native_recover',side_effect=no_owner):
            self.assertEqual(launch.recover_stage('pre'),0)
        self.assertIn('observe_flat.py',' '.join(self.calls[-1][0]))
        self.assertFalse(self.stop.exists())

    def test_data_go_cannot_dispatch_order_command_or_touch_stop(self):
        slot=self.state/'ready/record';slot.mkdir(parents=True)
        value={'schema_version':1,'purpose':'GET_ONLY_RECORD','bundle_sha256':launch.sha(self.bundle/'SHA256SUMS'),
               'config_sha256':launch.sha(launch.config('pre')),'trial':'fixture-record','session_kind':'PRE',
               'session_date':'2026-10-12','issued_at_utc':self.now.isoformat()}
        (slot/'GO.json').write_text(json.dumps(value));(slot/'GO.sha256').write_text(launch.sha(slot/'GO.json'))
        self.assertEqual(launch_data.run('record'),0)
        argv=self.calls[-1][0]
        self.assertIn('data_worker.py',' '.join(argv));self.assertNotIn('paper',argv)
        launch_data.finished('record')
        self.assertTrue((self.state/'data-completed/record.json').is_file())
        self.assertFalse(self.stop.exists())

    def test_refused_path_token_is_retained_without_infinite_retrigger(self):
        self.token('pre');(self.state/'ready/pre/GO.sha256').write_text('0'*64)
        with patch.object(sys,'argv',['launch.py','run','pre']):self.assertEqual(launch.main(),2)
        self.assertFalse((self.state/'ready/pre/GO.sha256').exists())
        self.assertEqual(len(list((self.state/'ready/pre').glob('GO.refused.*.sha256'))),1)
        archived=list((self.state/'ready/pre').glob('GO.refused.*.json'))
        self.assertEqual(len(archived),1)
        self.assertEqual(json.loads(archived[0].read_text())['stage'],'pre')
        self.assertEqual(self.calls,[])

if __name__=='__main__':unittest.main(verbosity=2)
