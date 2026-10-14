"""Synthetic issuer readiness and atomic GO proof; never activates a native unit."""
from datetime import datetime,timezone,timedelta
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
import issue_go

class Issuer(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.bundle=self.root/'bundle';self.bundle.mkdir()
        shutil.copytree(ROOT/'configs',self.bundle/'configs')
        (self.bundle/'SHA256SUMS').write_text('synthetic bundle binding\n')
        request={'bundle_sha256':launch.sha(self.bundle/'SHA256SUMS'),'issuer':'CC through co-op',
                 'config_hashes':{s:launch.sha(self.bundle/'configs'/(s+'.json')) for s in launch.STAGES}}
        (self.bundle/'GO-BINDING-REQUEST.json').write_text(json.dumps(request))
        self.state=self.root/'state';self.state.mkdir();self.stop=self.root/'STOP'
        self.auth=self.root/'auth.md';self.auth.write_text('Synthetic CC record binds '+request['bundle_sha256'])
        self.kind='PRE';self.stamp=datetime(2026,10,12,11,1,30,tzinfo=timezone.utc)
        class Clock(datetime):
            @classmethod
            def now(cls,tz=None):return self.stamp
        for name,value in [('ROOT',self.bundle),('STATE',self.state),('STOP',self.stop)]:
            p=patch.object(launch,name,value);p.start();self.addCleanup(p.stop)
        for p in [patch.object(launch,'verify_bundle',return_value=None),patch.object(launch,'verify_runtime',return_value=None),
                  patch.object(launch,'session_now',side_effect=lambda:(self.kind,'2026-10-12')),
                  patch.object(launch,'record_units',return_value=[{'Id':'paper-ready-record-fixture.service',
                                                                 'ActiveState':'inactive'}]),
                  patch.object(issue_go,'writer_units',return_value=[]),patch.object(issue_go,'datetime',Clock),
                  patch.object(issue_go.time,'time',return_value=self.stamp.timestamp()),
                  patch.object(issue_go.time,'monotonic',return_value=1000.0)]:
            p.start();self.addCleanup(p.stop)

    def scan(self):
        slot=self.state/'ready/pre';slot.mkdir(parents=True)
        scan={'schema_version':1,'kind':'mover_scan','protocol':'mover-early-entry-v1-20260924',
              'rule':'07:00|G20|V1000000|any','scan_time':'2026-10-12T11:01:00Z','symbols':[]}
        (slot/'scan.json').write_text(json.dumps(scan))
        launch.save(slot/'SCAN-READY.json',{'config_sha256':launch.sha(launch.config('pre')),
                    'engine_scan_sha256':launch.sha(slot/'scan.json')})
        launch.save(self.state/'reference-trading-last.json',{'boot_id':launch.boot_id(),'finished_monotonic':900.0})

    def test_record_check_writes_nothing_and_issue_sets_payload_before_digest(self):
        before=set(self.state.rglob('*'))
        answer=issue_go.issue('record','fixture-record',self.auth,launch.sha(self.auth),True)
        self.assertEqual(answer['status'],'ready_check_passed')
        self.assertEqual(set(self.state.rglob('*')),before)
        output=issue_go.issue('record','fixture-record',self.auth,launch.sha(self.auth),False)
        payload=self.state/'ready/record/GO.json';digest=self.state/'ready/record/GO.sha256'
        self.assertEqual(digest.read_text().strip(),launch.sha(payload))
        self.assertEqual(json.loads(payload.read_text())['purpose'],'GET_ONLY_RECORD')
        self.assertEqual(output['go_sha256'],launch.sha(payload))
        self.assertEqual(digest.stat().st_mode&0o777,0o600)

    def test_pre_needs_fresh_scan_and_exact_issued_schema(self):
        self.scan()
        answer=issue_go.issue('pre','fixture-pre',self.auth,launch.sha(self.auth),True)
        self.assertEqual(set(answer['GO_schema']),{'schema_version','bundle_sha256','config_sha256','stage','trial',
            'session_kind','session_date','issued_at_utc','state_root','scan_sha256','previous_recover_sha256'})
        scan=self.state/'ready/pre/scan.json';data=json.loads(scan.read_text());data['scan_time']='2026-10-12T10:00:00Z';scan.write_text(json.dumps(data))
        with self.assertRaises(Exception):issue_go.issue('pre','fixture-other',self.auth,launch.sha(self.auth),True)

    def test_wrong_authority_session_rule_STOP_and_lane_writer_refuse(self):
        with self.assertRaisesRegex(launch.Refused,'authorization_hash'):
            issue_go.issue('record','fixture',self.auth,'0'*64,True)
        self.auth.write_text('wrongbundle')
        with self.assertRaisesRegex(launch.Refused,'does_not_bind'):
            issue_go.issue('record','fixture',self.auth,launch.sha(self.auth),True)
        self.auth.write_text(launch.sha(self.bundle/'SHA256SUMS'))
        self.kind='CLOSED'
        with self.assertRaisesRegex(launch.Refused,'session_not_ready'):
            issue_go.issue('record','fixture',self.auth,launch.sha(self.auth),True)
        self.kind='PRE';self.scan();self.stop.touch()
        with self.assertRaisesRegex(launch.Refused,'STOP_present'):
            issue_go.issue('pre','fixture',self.auth,launch.sha(self.auth),True)
        self.stop.unlink()
        with patch.object(issue_go,'writer_units',side_effect=launch.Refused('lane_A_active')):
            with self.assertRaisesRegex(launch.Refused,'lane_A_active'):
                issue_go.issue('pre','fixture',self.auth,launch.sha(self.auth),True)

    def test_rth_previous_native_recover_file_is_checked_not_just_summary(self):
        self.kind='RTH'
        instance=self.state/'instances/previous-pre';instance.mkdir(parents=True)
        native=instance/'recover.json';native.write_text(json.dumps({'status':'passed','flat':True,'positions':[],
             'unresolved_orders':[],'reconciliation':{'positions':0,'open_orders':0}}))
        handoff={'stage':'pre','session_date':'2026-10-12','trial':'previous-pre','config_sha256':launch.sha(launch.config('pre')),
                 'bundle_sha256':launch.sha(self.bundle/'SHA256SUMS'),
                 'recover_rc':0,'native_recover_sha256':launch.sha(native),'flat':True,'positions':0,'open_orders':0,
                 'boot_id':launch.boot_id(),'recover_finished_monotonic':900.0}
        launch.save(self.state/'completed/2026-10-12/pre.json',handoff)
        launch.save(self.state/'data-completed/record.json',{'session_date':'2026-10-12','finished':True})
        with patch.object(launch.time,'monotonic',return_value=900.0):launch.record_quiescence()
        answer=issue_go.issue('sip','fixture-sip',self.auth,launch.sha(self.auth),True)
        self.assertEqual(answer['GO_schema']['previous_recover_sha256'],launch.sha(self.state/'completed/2026-10-12/pre.json'))
        native.write_text('{}')
        with self.assertRaisesRegex(launch.Refused,'native_recover_hash'):
            issue_go.issue('sip','fixture-sip',self.auth,launch.sha(self.auth),True)

if __name__=='__main__':unittest.main(verbosity=2)
