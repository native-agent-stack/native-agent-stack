"""Fail-first sequencing regressions; SYN roots, intercepted keyed/systemd calls."""
from datetime import timedelta
import json
from pathlib import Path
from unittest.mock import patch
import unittest

from test_wiring import Wiring
import launch
import launch_data
import issue_go
REAL_RECORD_UNITS = getattr(launch,'record_units',None)

class Sequencing(Wiring):
    def setUp(self):
        super().setUp()
        self.unit_patch=patch.object(launch,'record_units',return_value=[
            {'Id':'paper-ready-record-8c95a50d.service','ActiveState':'inactive'}],create=True)
        self.unit_patch.start();self.addCleanup(self.unit_patch.stop)

    def skip_go(self,reason='pre_window_passed'):
        self.kind='RTH'
        slot=self.state/'ready/pre-skip'
        slot.mkdir(parents=True,exist_ok=True)
        trial='fixture-skip'
        value={'schema_version':1,'purpose':'GET_ONLY_PRE_SKIP',
               'bundle_sha256':launch.sha(self.bundle/'SHA256SUMS'),
               'config_sha256':launch.sha(launch.config('pre')),'trial':trial,
               'session_kind':self.kind,'session_date':'2026-10-12','issued_at_utc':self.now.isoformat(),
               'state_root':str(self.state/'instances'/trial/'native-state'),'skip_reason':reason}
        launch.save(slot/'GO.json',value)
        (slot/'GO.sha256').write_text(launch.sha(slot/'GO.json'))
        return value

    def quiet(self):
        self.assertEqual(launch.record_quiescence(),0)
        self.monotonic+=61

    def test_skipped_pre_flat_probe_handoff_starts_sip(self):
        self.skip_go()
        self.assertEqual(launch.skip_stage(),0)
        handoff=launch.safe_json(self.state/'completed/2026-10-12/pre.json')
        self.assertEqual(handoff['skipped'],'pre_window_passed')
        self.assertIs(handoff['pre_did_not_trade'],True)
        self.assertEqual(handoff['recover_rc'],0)
        self.assertTrue(handoff['flat'])
        self.assertEqual((handoff['positions'],handoff['open_orders']),(0,0))
        self.assertEqual(len(self.calls),1)
        self.assertIn('observe_flat.py',' '.join(self.calls[0][0]))
        self.assertFalse(self.stop.exists())
        self.quiet();self.token('sip')
        self.assertEqual(launch.run_stage('sip'),0)
        self.assertIn('scheduled_trial.sh',' '.join(self.calls[-1][0]))

    def test_nonflat_skip_proof_refused(self):
        self.skip_go()
        def nonflat(command,**kwargs):
            argv=list(map(str,command));output=Path(argv[argv.index('--output')+1])
            output.write_text(json.dumps({'status':'needs_attention','flat':False,'positions':[{}],
                'unresolved_orders':[],'reconciliation':{'positions':1,'open_orders':0}}))
            return 2
        with patch.object(launch,'keyed',side_effect=nonflat):
            with self.assertRaisesRegex(launch.Refused,'skip_probe_not_flat'):
                launch.skip_stage()
        self.assertFalse((self.state/'completed/2026-10-12/pre.json').exists())
        self.token('sip')
        with self.assertRaises(launch.Refused):launch.run_stage('sip')

    def test_failed_pre_recover_cannot_be_skipped_or_start_sip(self):
        self.token('pre');launch.run_stage('pre');launch.stop_mark('pre')
        def failed(stage,active):
            output=Path(active['instance'])/'recover.json'
            output.write_text(json.dumps({'status':'needs_attention','flat':False,'positions':[{}],
               'unresolved_orders':[],'reconciliation':{'positions':1,'open_orders':0}}))
            return 3,output
        with patch.object(launch,'native_recover',side_effect=failed):
            with self.assertRaises(launch.Refused):launch.recover_stage('pre')
        self.skip_go()
        with self.assertRaises(launch.Refused):launch.skip_stage()
        self.assertTrue(self.stop.exists())
        self.assertTrue((self.state/'active/pre.json').exists())
        self.token('sip')
        with self.assertRaises(launch.Refused):launch.run_stage('sip')

    def test_failed_record_starts_sip_only_after_quiescent_window(self):
        launch.save(self.state/'data-completed/record.json',{
            'session_date':'2026-10-12','finished':True,'service_result':'exit-code'})
        self.skip_go();launch.skip_stage()
        self.monotonic+=61  # isolate the recorder gate from the PRE probe gate
        self.unit_patch.stop()
        failed_unit=patch.object(launch,'record_units',return_value=[
            {'Id':'paper-ready-record-8c95a50d.service','ActiveState':'failed'}])
        failed_unit.start();self.addCleanup(failed_unit.stop)
        self.assertEqual(launch.record_quiescence(),0)
        self.token('sip')
        with self.assertRaisesRegex(launch.Refused,'record_request_window_not_drained'):
            launch.run_stage('sip')
        self.monotonic+=61
        self.assertEqual(launch.run_stage('sip'),0)

    def test_quiescence_refuses_active_or_pending_record_and_changed_evidence(self):
        self.kind='RTH'
        launch.save(self.state/'active-data/record.json',{'trial':'active'})
        with self.assertRaises(launch.Refused):launch.record_quiescence()
        (self.state/'active-data/record.json').unlink()
        slot=self.state/'ready/record';slot.mkdir(parents=True)
        (slot/'GO.sha256').write_text('0'*64)
        with self.assertRaises(launch.Refused):launch.record_quiescence()
        (slot/'GO.sha256').unlink()
        self.assertEqual(launch.record_quiescence(),0);self.monotonic+=61
        launch.save(self.state/'data-completed/record.json',{'session_date':'2026-10-12','finished':True})
        with self.assertRaisesRegex(launch.Refused,'record_quiescence_evidence_changed'):
            launch.record_window_drained('2026-10-12')

    def test_quiescence_missing_wrong_boot_and_future_are_refused(self):
        self.kind='RTH'
        with self.assertRaises(Exception):launch.record_window_drained('2026-10-12')
        self.quiet()
        p=self.state/'record-quiescence/2026-10-12.json'
        original=launch.safe_json(p)
        for field,value in [('boot_id','wrong'),('quiet_monotonic',self.monotonic+1)]:
            launch.save(p,dict(original,**{field:value}))
            with self.assertRaises(launch.Refused):launch.record_window_drained('2026-10-12')

    def test_skip_go_wrong_purpose_expired_stop_and_refused_pre_never_probes(self):
        self.skip_go()
        slot=self.state/'ready/pre-skip'
        original=launch.safe_json(slot/'GO.json')
        for field,value in [('purpose','GET_ONLY_RECORD'),
                            ('issued_at_utc',(self.now-timedelta(seconds=301)).isoformat())]:
            launch.save(slot/'GO.json',dict(original,**{field:value}))
            (slot/'GO.sha256').write_text(launch.sha(slot/'GO.json'))
            with self.assertRaises(launch.Refused):launch.skip_stage()
        self.skip_go();self.stop.touch()
        with self.assertRaises(launch.Refused):launch.skip_stage()
        self.stop.unlink()
        launch.save(self.state/'ready/pre/GO.refused.1.json',{
            'stage':'pre','session_date':'2026-10-12'})
        with self.assertRaisesRegex(launch.Refused,'PRE_already_admitted_or_refused'):
            launch.skip_stage()
        self.assertEqual(self.calls,[])

    def test_skip_handoff_native_tamper_or_failed_rc_is_refused(self):
        self.skip_go();launch.skip_stage();self.quiet()
        native=self.state/'instances/fixture-skip/flat-probe.json'
        native.write_text('{}')
        self.token('sip')
        with self.assertRaises(launch.Refused):launch.run_stage('sip')

    def issuer_fixture(self):
        request={'bundle_sha256':launch.sha(self.bundle/'SHA256SUMS'),'issuer':'CC through co-op',
                 'config_hashes':{s:launch.sha(launch.config(s)) for s in launch.STAGES}}
        launch.save(self.bundle/'GO-BINDING-REQUEST.json',request)
        auth=self.root/'auth.md';auth.write_text('SYN CC binding '+request['bundle_sha256'])
        outer=self
        from datetime import datetime
        class Clock(datetime):
            @classmethod
            def now(cls,tz=None):return outer.now
        for controller in [patch.object(issue_go,'writer_units',return_value=[]),
                           patch.object(issue_go,'datetime',Clock)]:
            controller.start();self.addCleanup(controller.stop)
        return auth

    def test_issuer_to_skip_launcher_then_entire_rth_chain(self):
        self.kind='RTH';auth=self.issuer_fixture()
        before=set(self.state.rglob('*'))
        checked=issue_go.issue('pre-skip','e2e-skip',auth,launch.sha(auth),True,'pre_window_passed')
        self.assertEqual(checked['GO_schema']['purpose'],'GET_ONLY_PRE_SKIP')
        self.assertEqual(set(self.state.rglob('*')),before)
        issue_go.issue('pre-skip','e2e-skip',auth,launch.sha(auth),False,'pre_window_passed')
        self.assertEqual(launch.skip_stage(),0)
        self.quiet()
        for stage in launch.STAGES[1:]:
            issue_go.issue(stage,'e2e-'+stage,auth,launch.sha(auth),True)
            issue_go.issue(stage,'e2e-'+stage,auth,launch.sha(auth),False)
            self.assertEqual(launch.run_stage(stage),0)
            self.finish(stage)
        self.assertEqual(len(self.calls),15)  # one GET probe + seven trial/recover pairs
        self.assertEqual(len(list((self.state/'completed/2026-10-12').glob('*.json'))),8)

    def test_nonflat_skip_handoff_refused_by_issuer_and_launcher(self):
        self.skip_go();launch.skip_stage();self.quiet()
        path=self.state/'completed/2026-10-12/pre.json'
        prior=launch.safe_json(path);prior['flat']=False;prior['positions']=1
        launch.save(path,prior)
        auth=self.issuer_fixture()
        with self.assertRaisesRegex(launch.Refused,'previous_not_flat'):
            issue_go.issue('sip','blocked-sip',auth,launch.sha(auth),True)
        self.token('sip')
        with self.assertRaisesRegex(launch.Refused,'previous_not_flat'):launch.run_stage('sip')

    def test_original_c738_handoff_is_accepted_without_relabelling_or_reset(self):
        self.token('pre');launch.run_stage('pre');self.finish('pre')
        p=self.state/'completed/2026-10-12/pre.json';prior=launch.safe_json(p)
        prior.pop('bundle_sha256')  # actual predecessor handoff schema
        launch.save(p,prior)
        active=self.state/'instances/fixture-pre/active.finished.json'
        original=launch.safe_json(active);original['bundle_sha256']=launch.PREDECESSOR_BUNDLE
        launch.save(active,original)
        native=self.state/'instances/fixture-pre/recover.json'
        hashes={str(f):launch.sha(f) for f in [p,active,native]}
        self.kind='RTH';self.quiet();self.token('sip')
        self.assertEqual(launch.run_stage('sip'),0)
        self.assertEqual(hashes,{str(f):launch.sha(f) for f in [p,active,native]})

    def test_clean_failed_pre_with_native_recover_continues_sip(self):
        self.token('pre')
        with patch.object(launch,'keyed',return_value=7):self.assertEqual(launch.run_stage('pre'),7)
        self.finish('pre')
        self.kind='RTH';self.quiet();self.token('sip')
        self.assertEqual(launch.run_stage('sip'),0)
        self.assertNotIn('pre_did_not_trade',launch.safe_json(self.state/'completed/2026-10-12/pre.json'))

    def test_native_record_unit_inventory_error_active_and_empty_fail_closed(self):
        self.unit_patch.stop()
        from types import SimpleNamespace
        for rc,text in [(1,''),(0,''),(0,'paper-ready-record-x.service loaded active running description\n')]:
            with patch.object(launch.subprocess,'run',return_value=SimpleNamespace(returncode=rc,stdout=text)):
                with self.assertRaises(launch.Refused):REAL_RECORD_UNITS()

    def test_refused_record_GO_is_not_relaxed_to_clean_record_failure(self):
        self.kind='RTH'
        launch.save(self.state/'ready/record/GO.refused.1.json',{
            'purpose':'GET_ONLY_RECORD','session_date':'2026-10-12','trial':'bad-record'})
        with self.assertRaisesRegex(launch.Refused,'record_GO_was_refused'):launch.record_quiescence()

# Lifecycle tests run in their own suite; this subclass only adds regressions.
for name in Wiring.__dict__:
    if name.startswith('test_') and name not in Sequencing.__dict__:
        setattr(Sequencing,name,None)

if __name__=='__main__':unittest.main(verbosity=2)
