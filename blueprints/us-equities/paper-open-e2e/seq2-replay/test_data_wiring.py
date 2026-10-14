"""Native Fetcher/raw retention and Ledger budget with intercepted HTTP, SYN only."""
from datetime import datetime,timezone
import gzip
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs,urlparse

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import data_worker
sys.path.insert(0,str(ROOT/'frozen/blueprints/us-equities/mover-early-entry'))
import mover_scan
sys.path.insert(0,str(ROOT/'frozen/blueprints/us-equities/adaptive-paper'))
import sessions

class Reply:
    status=200
    def __init__(self,value):self.value=value
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def read(self):return json.dumps(self.value).encode()

class DataWiring(unittest.TestCase):
    def test_recorder_native_assets_and_three_snapshot_chunks_budget_and_raw_manifest(self):
        with tempfile.TemporaryDirectory() as folder:
            state=Path(folder)
            names=[f'X{i:04d}' for i in range(1001)]
            calls=[]
            def http(request,timeout):
                parsed=urlparse(request.full_url);calls.append(parsed.path)
                if parsed.path=='/v2/assets':
                    return Reply([{'symbol':s,'tradable':True,'exchange':'NASDAQ'} for s in names])
                self.assertEqual(parsed.path,'/v2/stocks/snapshots')
                q=parse_qs(parsed.query);self.assertEqual(q['feed'],['sip'])
                return Reply({s:{'latestQuote':{'bp':1,'ap':1.01}} for s in q['symbols'][0].split(',')})
            sequence=[SimpleNamespace(kind=SimpleNamespace(value='PRE'),session_date=datetime(2026,10,12).date()),
                      SimpleNamespace(kind=SimpleNamespace(value='PRE'),session_date=datetime(2026,10,12).date()),
                      SimpleNamespace(kind=SimpleNamespace(value='RTH'),session_date=datetime(2026,10,12).date())]
            with patch.object(data_worker,'STATE',state), \
                 patch.dict('os.environ',{'APCA_API_KEY_ID':'synthetic-id','APCA_API_SECRET_KEY':'synthetic-secret'}), \
                 patch.object(mover_scan.urllib.request,'urlopen',side_effect=http), \
                 patch.object(sessions,'session_at',side_effect=sequence), \
                 patch('builtins.print'):
                self.assertEqual(data_worker.work('record','fixture-record','2026-10-12'),0)
            self.assertEqual(calls,['/v2/assets']+['/v2/stocks/snapshots']*3)
            current=state/'data/record/fixture-record/pass-0000'
            receipt=json.loads((current/'receipt.json').read_text())
            self.assertEqual(receipt['returned_rows'],1001)
            self.assertEqual(receipt['orders'],0)
            self.assertEqual(len(list((current/'pages').glob('*.json.gz'))),3)
            self.assertEqual(len(list((state/'data/record/fixture-record/universe-pages').glob('*.json.gz'))),1)
            import sqlite3
            with sqlite3.connect(state/'data-budget.sqlite3') as db:
                self.assertEqual(db.execute('select count(*) from requests').fetchone()[0],4)
                self.assertEqual(db.execute('select count(*) from intents').fetchone()[0],0)
            self.assertTrue((current/'MANIFEST.sha256').is_file())
            self.assertFalse((state/'STOP').exists())

    def test_native_scanner_engine_gain_conversion_hash_and_READY_without_order_GO(self):
        with tempfile.TemporaryDirectory() as folder:
            state=Path(folder)
            stamp=datetime(2026,10,12,11,0,5,tzinfo=timezone.utc)
            class FixtureDateTime(datetime):
                @classmethod
                def now(cls,tz=None):return stamp
            def scanner(fetch,rule,now):
                self.assertEqual(rule,'07:00|G0.2|V1000000|any')
                return {'protocol':'mover-early-entry-v1-20260924','rule':rule,'scan_time_utc':stamp.isoformat(),
                        'regime_factor':1,'regime_detail':{'spy_prev_close':100,'mean20':90,'vol20':0.1,'vol20_median252':0.2},
                        'candidates':[]}
            with patch.object(data_worker,'STATE',state), \
                 patch.object(data_worker,'datetime',FixtureDateTime), \
                 patch.object(data_worker.time,'time',return_value=stamp.timestamp()), \
                 patch.dict('os.environ',{'APCA_API_KEY_ID':'synthetic-id','APCA_API_SECRET_KEY':'synthetic-secret'}), \
                 patch.object(mover_scan,'scan',side_effect=scanner), \
                 patch('builtins.print'):
                self.assertEqual(data_worker.work('scan','fixture-scan','2026-10-12'),0)
            slot=state/'ready/pre'
            scan=json.loads((slot/'scan.json').read_text())
            ready=json.loads((slot/'SCAN-READY.json').read_text())
            self.assertEqual(scan['rule'],'07:00|G20|V1000000|any')
            self.assertEqual(ready['engine_scan_sha256'],data_worker.digest(slot/'scan.json'))
            self.assertFalse((slot/'GO.sha256').exists())
            self.assertFalse((state/'STOP').exists())

if __name__=='__main__':unittest.main(verbosity=2)
