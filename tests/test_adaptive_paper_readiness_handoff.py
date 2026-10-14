"""Retained startup requests and cap transitions; synthetic, no broker I/O."""
import contextlib
from dataclasses import replace
from pathlib import Path
import sys
import sqlite3
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock,patch

SOURCE = Path(__file__).resolve().parents[1] / 'blueprints/us-equities/adaptive-paper'
sys.path.insert(0, str(SOURCE))
import runner
from safety import Ledger, RiskLimits, SafetyError
import transport


class ReadinessHandoff(unittest.TestCase):
    def startup_probe(self, root, ledger_path, *, readiness):
        from tests.test_adaptive_paper_start_readiness import StartReadiness
        sends=[]
        original=transport.GuardedSession.request
        def request(guard,*args,**kwargs):
            result=original(guard,*args,**kwargs)
            sends.append(args[0])
            return result
        outcome=None
        try:
            with patch.object(transport.GuardedSession,'request',request):
                StartReadiness().budget_probe(root,readiness=readiness,ledger_path=ledger_path,
                                             refresh_case='budget')
        except (transport.TransportError,SafetyError) as exc:
            outcome=str(exc)
        return sends,outcome

    def test_bound_nonreadiness_start_reserves_before_any_startup_get(self):
        epoch=transport.timestamp_ns('2026-10-14T08:00:00Z')/1e9
        limits=runner.load_config(SOURCE/'config.json')[1]
        with tempfile.TemporaryDirectory(dir='/var/tmp') as directory:
            root=Path(directory);path=root/'readiness-requests.sqlite3'
            trading=root/('a'*64)/'adaptive/ledger.sqlite3'
            with contextlib.closing(Ledger(path)) as source:
                for _ in range(192):source.request_budget(epoch-30,'read')
            with contextlib.closing(Ledger(trading,limits)) as ledger:
                self.handoff(ledger,[],path,epoch-30)
                for _ in range(8):self.assertEqual(ledger.request_budget(epoch-30,'read'),0)
            sends,outcome=self.startup_probe(root,trading,readiness=False)
            self.assertEqual(sends,[],'bound RTH/recover startup sent outside exhausted root window')
            self.assertEqual(outcome,'readiness_request_budget_exhausted')
            with contextlib.closing(Ledger(path)) as source:
                self.assertEqual(source.db.execute('SELECT COUNT(*) FROM requests').fetchone()[0],200)

    def test_first_opted_start_imports_199_trading_spends_before_http(self):
        epoch=transport.timestamp_ns('2026-10-14T08:00:00Z')/1e9
        limits=runner.load_config(SOURCE/'config.json')[1]
        with tempfile.TemporaryDirectory(dir='/var/tmp') as directory:
            root=Path(directory);trading=root/('a'*64)/'adaptive/ledger.sqlite3'
            with contextlib.closing(Ledger(trading,limits)) as ledger:
                for _ in range(199):ledger.request_budget(epoch-30,'read')
            sends,outcome=self.startup_probe(root,trading,readiness=True)
            self.assertLessEqual(len(sends),1,'first opted adoption sent before counting retained trading spends')
            self.assertEqual(outcome,'readiness_request_budget_exhausted')
            with contextlib.closing(Ledger(root/'readiness-requests.sqlite3')) as source:
                self.assertEqual(source.db.execute('SELECT COUNT(*) FROM requests').fetchone()[0],200)

    def test_bound_nonreadiness_success_imports_reserved_startup_only_once(self):
        from tests.test_adaptive_paper_start_readiness import StartReadiness
        epoch=transport.timestamp_ns('2026-10-14T08:00:00Z')/1e9
        limits=runner.load_config(SOURCE/'config.json')[1]
        with tempfile.TemporaryDirectory(dir='/var/tmp') as directory:
            root=Path(directory);path=root/'readiness-requests.sqlite3'
            trading=root/('a'*64)/'adaptive/ledger.sqlite3'
            with contextlib.closing(Ledger(path)) as source:
                for _ in range(7):source.request_budget(epoch-30,'read')
            with contextlib.closing(Ledger(trading,limits)) as ledger:
                self.handoff(ledger,[],path,epoch-30)
            attempts,wire,_,rows=StartReadiness().budget_probe(root,readiness=False,ledger_path=trading)
            self.assertEqual(len(wire),6)
            self.assertTrue(all(a['root_reserved'] for a in attempts))
            self.assertEqual(rows,{'read':12,'data_read':1})
            with contextlib.closing(Ledger(trading,limits)) as ledger:
                self.handoff(ledger,attempts,path,epoch)
                self.assertEqual(ledger.db.execute('SELECT COUNT(*) FROM requests').fetchone()[0],13)
            with contextlib.closing(Ledger(path)) as source:
                self.assertEqual(source.db.execute('SELECT COUNT(*) FROM requests').fetchone()[0],13)

    def test_first_adoption_binds_an_already_open_trading_handle_before_send(self):
        limits=runner.load_config(SOURCE/'config.json')[1]
        with tempfile.TemporaryDirectory(dir='/var/tmp') as directory:
            root=Path(directory);trading=root/('a'*64)/'adaptive/ledger.sqlite3'
            with contextlib.closing(Ledger(trading,limits)) as old:
                for _ in range(199):old.request_budget(1000,'read')
                with patch.object(time,'time',return_value=1030):
                    with runner.readiness_request_window(root,limits,enabled=True) as reserve:
                        reserve(1030,'read')
                        self.assertGreater(old.request_budget(1030,'read'),0)
                        with self.assertRaisesRegex(transport.TransportError,'readiness_request_budget_exhausted'):
                            reserve(1030,'read')

    def test_missing_bound_source_refuses_without_recreating_a_budget(self):
        limits=runner.load_config(SOURCE/'config.json')[1]
        with tempfile.TemporaryDirectory(dir='/var/tmp') as directory:
            root=Path(directory);path=root/'readiness-requests.sqlite3'
            with contextlib.closing(Ledger(path)) as source:source.request_budget(1000,'read')
            with contextlib.closing(Ledger(root/('a'*64)/'adaptive/ledger.sqlite3',limits)) as ledger:
                self.handoff(ledger,[],path,1000)
            path.unlink()
            for enabled in (False,True):
                with self.assertRaisesRegex(SafetyError,'readiness_request_journal_required'):
                    with runner.readiness_request_window(root,limits,enabled=enabled):pass
                self.assertFalse(path.exists())

    def test_recovery_startup_keeps_retained_caps_after_rotation(self):
        original=runner.load_config(SOURCE/'config.json')[1]
        request_limits=RiskLimits()
        lower=replace(request_limits,max_rest_per_minute=150,max_submits_per_minute=50)
        with tempfile.TemporaryDirectory(dir='/var/tmp') as directory:
            root=Path(directory);path=root/'readiness-requests.sqlite3'
            with contextlib.closing(Ledger.open_request_window(path,request_limits,1000,exploratory=True)) as source:
                source.request_budget(1000,'read')
            trading=root/('a'*64)/'adaptive/ledger.sqlite3'
            with contextlib.closing(Ledger(trading,original,exploratory=True)) as ledger:
                self.handoff(ledger,[],path,1000)
            with contextlib.closing(Ledger.open_request_window(path,lower,1060,exploratory=True)) as source:
                source.request_budget(1060,'read')
            with patch.object(time,'time',return_value=1061):
                with runner.readiness_request_window(root,original,enabled=False,exploratory=True) as reserve:
                    reserve(1061,'read')
            with contextlib.closing(Ledger(path,lower,exploratory=True)) as source:
                self.assertEqual(source.limits.max_rest_per_minute,150)
                self.assertEqual(source.db.execute('SELECT COUNT(*) FROM requests WHERE at>1001').fetchone()[0],2)
            with contextlib.closing(Ledger(trading,original,exploratory=True)) as ledger:
                self.assertEqual(ledger.limits.frozen_json(),original.frozen_json())

    def test_recovery_source_open_follows_cap_rotation_after_metadata_probe(self):
        lower=replace(RiskLimits(),max_rest_per_minute=150,max_submits_per_minute=50)
        with tempfile.TemporaryDirectory(dir='/var/tmp') as directory:
            path=Path(directory)/'readiness-requests.sqlite3'
            with contextlib.closing(Ledger.open_request_window(path,RiskLimits(),1000,exploratory=True)) as source:
                source.request_budget(1000,'read')
            original=Ledger.__init__;rotated=[]
            def interleaved(instance,*args,**kwargs):
                if not rotated:
                    rotated.append(True)
                    with contextlib.closing(Ledger.open_request_window(path,lower,1060,exploratory=True)) as current:
                        current.request_budget(1060,'read')
                original(instance,*args,**kwargs)
            with patch.object(Ledger,'__init__',interleaved):
                with contextlib.closing(Ledger.open_request_window(path,RiskLimits(),1061,
                                        exploratory=True,follow_caps=True)) as recovery:
                    self.assertEqual(recovery.limits.max_rest_per_minute,150)
                    self.assertEqual(recovery.request_budget(1061,'read'),0)

    def test_startup_keeps_lower_frozen_trading_cap_when_source_cap_increases(self):
        original=replace(runner.load_config(SOURCE/'config.json')[1],
                         max_rest_per_minute=30,max_submits_per_minute=10)
        low_request=replace(RiskLimits(),max_rest_per_minute=30,max_submits_per_minute=10)
        with tempfile.TemporaryDirectory(dir='/var/tmp') as directory:
            root=Path(directory);path=root/'readiness-requests.sqlite3'
            with contextlib.closing(Ledger.open_request_window(path,low_request,1000,exploratory=True)) as source:
                source.request_budget(1000,'read')
            with contextlib.closing(Ledger(root/('a'*64)/'adaptive/ledger.sqlite3',original,exploratory=True)) as ledger:
                self.handoff(ledger,[],path,1000)
            with contextlib.closing(Ledger.open_request_window(path,RiskLimits(),1060,exploratory=True)) as source:
                for _ in range(30):source.request_budget(1060,'read')
            with patch.object(time,'time',return_value=1061):
                with runner.readiness_request_window(root,original,enabled=False,exploratory=True) as reserve:
                    with self.assertRaisesRegex(transport.TransportError,'readiness_request_budget_exhausted'):
                        reserve(1061,'read')
            with contextlib.closing(Ledger(path,RiskLimits(),exploratory=True)) as source:
                self.assertEqual(source.db.execute('SELECT COUNT(*) FROM requests WHERE at>1001').fetchone()[0],30)

    def handoff(self,ledger,attempts,path,now):
        if hasattr(ledger,'import_request_window'):
            with patch.object(time,'time',return_value=now):
                runner.replay_preflight_requests(ledger,attempts,readiness=True,readiness_path=path,now=now)
        else:
            runner.replay_preflight_requests(ledger,attempts,readiness=True)

    def test_180_failed_plus_12_successful_start_all_count_before_trading(self):
        with tempfile.TemporaryDirectory(dir='/var/tmp') as directory:
            root = Path(directory)
            with contextlib.closing(Ledger(root/'readiness-requests.sqlite3')) as source:
                for _ in range(180):
                    source.request_budget(1000, 'read')
                for _ in range(9):
                    source.request_budget(1001, 'read')
                for _ in range(3):
                    source.request_budget(1001, 'data_read')
            attempts = [{'timestamp':1001,'kind':kind} for kind in ['read']*9+['data_read']*3]
            with contextlib.closing(Ledger(root/'trading.sqlite3')) as ledger:
                self.handoff(ledger,attempts,root/'readiness-requests.sqlite3',1002)
                self.assertEqual(ledger.db.execute('SELECT COUNT(*) FROM requests').fetchone()[0],192)
                allowed = sum(ledger.request_budget(1002,'read') == 0 for _ in range(30))
                self.assertEqual(allowed,8)
                self.assertEqual(ledger.db.execute('SELECT COUNT(*) FROM requests').fetchone()[0],200)
                self.handoff(ledger,attempts,root/'readiness-requests.sqlite3',1002)
                self.assertEqual(ledger.db.execute('SELECT COUNT(*) FROM requests').fetchone()[0],200)
            # Reopening and another import cannot duplicate the same source rows.
            with contextlib.closing(Ledger(root/'trading.sqlite3')) as ledger:
                self.handoff(ledger,attempts,root/'readiness-requests.sqlite3',1003)
                self.assertGreater(ledger.request_budget(1003,'read'),0)
                self.assertEqual(ledger.db.execute('SELECT COUNT(*) FROM requests').fetchone()[0],200)

    def test_cap_rotation_refuses_active_window_then_preserves_history_after_expiry(self):
        with tempfile.TemporaryDirectory(dir='/var/tmp') as directory:
            root=Path(directory);old=RiskLimits();new=replace(old,max_rest_per_minute=180,max_submits_per_minute=160)
            with contextlib.closing(Ledger(root/'readiness-requests.sqlite3',old,exploratory=True)) as source:
                source.request_budget(1000,'data_read')
            with self.assertRaisesRegex(SafetyError,'readiness_cap_change_requires_expired_window'):
                with runner.readiness_request_window(root,new,enabled=True,exploratory=True) as reserve:
                    reserve(1059.999,'read')
            with runner.readiness_request_window(root,new,enabled=True,exploratory=True) as reserve:
                reserve(1060,'read')
            with contextlib.closing(Ledger(root/'readiness-requests.sqlite3',new,exploratory=True)) as source:
                self.assertEqual(source.limits.max_rest_per_minute,180)
                self.assertEqual(source.db.execute('SELECT COUNT(*) FROM requests').fetchone()[0],2)
                self.assertEqual(source.db.execute('SELECT MIN(at) FROM requests').fetchone()[0],1000)

    def test_lane_a_cap_change_stays_strict_after_expiry(self):
        with tempfile.TemporaryDirectory(dir='/var/tmp') as directory:
            root=Path(directory);new=replace(RiskLimits(),max_rest_per_minute=180,max_submits_per_minute=160)
            with contextlib.closing(Ledger(root/'readiness-requests.sqlite3')) as source:
                source.request_budget(1000,'read')
            with self.assertRaisesRegex(SafetyError,'persisted_risk_limits_differ'):
                with runner.readiness_request_window(root,new,enabled=True) as reserve:
                    reserve(1061,'read')

    def test_cap_rotation_can_reopen_after_window_expiry(self):
        with tempfile.TemporaryDirectory(dir='/var/tmp') as directory:
            root=Path(directory);new=replace(RiskLimits(),max_rest_per_minute=150,max_submits_per_minute=130)
            with contextlib.closing(Ledger(root/'readiness-requests.sqlite3',exploratory=True)) as source:
                source.request_budget(1000,'read')
            with runner.readiness_request_window(root,new,enabled=True,exploratory=True) as reserve:
                reserve(2000,'data_read')
            with contextlib.closing(Ledger(root/'readiness-requests.sqlite3',new,exploratory=True)) as source:
                self.assertEqual(source.db.execute('SELECT COUNT(*) FROM requests').fetchone()[0],2)

    def test_request_import_and_provenance_rollback_together_on_fault(self):
        with tempfile.TemporaryDirectory(dir='/var/tmp') as directory:
            root=Path(directory);path=root/'readiness-requests.sqlite3'
            with contextlib.closing(Ledger(path)) as source:
                source.request_budget(1000,'read');source.request_budget(1001,'data_read')
            with contextlib.closing(Ledger(root/'trading.sqlite3')) as ledger:
                ledger.db.execute("CREATE TRIGGER fail_second BEFORE INSERT ON requests WHEN NEW.kind='data_read' "
                                  "BEGIN SELECT RAISE(ABORT,'synthetic_import_fault'); END")
                with self.assertRaisesRegex(sqlite3.IntegrityError,'synthetic_import_fault'):
                    with patch.object(time,'time',return_value=1002):ledger.import_request_window(path,1002)
                self.assertEqual(ledger.db.execute('SELECT COUNT(*) FROM requests').fetchone()[0],0)
                ledger.db.execute('DROP TRIGGER fail_second')
                with patch.object(time,'time',return_value=1002):ledger.import_request_window(path,1002)
                self.assertEqual(ledger.db.execute('SELECT COUNT(*) FROM requests').fetchone()[0],2)
                self.assertEqual(ledger.db.execute('SELECT COUNT(*) FROM request_imports').fetchone()[0],2)

    def test_expired_rows_are_retained_but_not_imported_as_active(self):
        with tempfile.TemporaryDirectory(dir='/var/tmp') as directory:
            root=Path(directory)
            with contextlib.closing(Ledger(root/'readiness-requests.sqlite3')) as source:
                source.request_budget(1000,'read');source.request_budget(1001,'data_read')
            with contextlib.closing(Ledger(root/'trading.sqlite3')) as ledger:
                self.handoff(ledger,[],root/'readiness-requests.sqlite3',1060)
                self.assertEqual(dict(ledger.db.execute('SELECT kind,COUNT(*) FROM requests GROUP BY kind')),{'data_read':1})
            with contextlib.closing(Ledger(root/'readiness-requests.sqlite3')) as source:
                self.assertEqual(source.db.execute('SELECT COUNT(*) FROM requests').fetchone()[0],2)

    def test_import_refuses_symlink_or_future_history_without_partial_import(self):
        with tempfile.TemporaryDirectory(dir='/var/tmp') as directory:
            root=Path(directory);path=root/'readiness-requests.sqlite3'
            with contextlib.closing(Ledger(path)) as source:
                source.request_budget(1000,'read');source.request_budget(1002,'data_read')
            (root/'link.sqlite3').symlink_to(path)
            with contextlib.closing(Ledger(root/'trading.sqlite3')) as ledger:
                with self.assertRaisesRegex(SafetyError,'readiness_request_journal_required'):
                    ledger.import_request_window(root/'link.sqlite3',1003)
                with self.assertRaisesRegex(SafetyError,'invalid_readiness_request_history'):
                    with patch.object(time,'time',return_value=1001):ledger.import_request_window(path,1001)
                self.assertEqual(ledger.db.execute('SELECT COUNT(*) FROM requests').fetchone()[0],0)

    def test_opted_handoff_cannot_fall_back_to_current_invocation_only(self):
        with tempfile.TemporaryDirectory(dir='/var/tmp') as directory:
            with contextlib.closing(Ledger(Path(directory)/'trading.sqlite3')) as ledger:
                with self.assertRaisesRegex(SafetyError,'readiness_request_journal_required'):
                    runner.replay_preflight_requests(ledger,[{'timestamp':1000,'kind':'read'}],readiness=True)
                self.assertEqual(ledger.db.execute('SELECT COUNT(*) FROM requests').fetchone()[0],0)

    def test_request_window_cannot_open_or_import_trading_state(self):
        with tempfile.TemporaryDirectory(dir='/var/tmp') as directory:
            root=Path(directory);path=root/'readiness-requests.sqlite3'
            with contextlib.closing(Ledger(path)) as source:
                source.begin_next_trial(1000,'owned-trial')
            with self.assertRaisesRegex(SafetyError,'request_only_journal_required'):
                with runner.readiness_request_window(root,RiskLimits(),enabled=True) as reserve:
                    reserve(1001,'read')
            with contextlib.closing(Ledger(root/'trading.sqlite3')) as ledger:
                with self.assertRaisesRegex(SafetyError,'request_only_journal_required'):
                    ledger.import_request_window(path,1001)

    def test_import_cannot_mix_lane_a_and_b(self):
        with tempfile.TemporaryDirectory(dir='/var/tmp') as directory:
            root=Path(directory);path=root/'readiness-requests.sqlite3'
            with contextlib.closing(Ledger(path,exploratory=True)) as source:
                source.request_budget(1000,'read')
            with contextlib.closing(Ledger(root/'trading.sqlite3')) as ledger:
                with self.assertRaisesRegex(SafetyError,'readiness_request_lane_mismatch'):
                    ledger.import_request_window(path,1001)
                self.assertEqual(ledger.db.execute('SELECT COUNT(*) FROM requests').fetchone()[0],0)

    def test_empty_request_file_can_bootstrap_without_prior_state(self):
        with tempfile.TemporaryDirectory(dir='/var/tmp') as directory:
            root=Path(directory);path=root/'readiness-requests.sqlite3';path.touch()
            with runner.readiness_request_window(root,RiskLimits(),enabled=True) as reserve:
                reserve(1000,'read')
            with contextlib.closing(Ledger(path)) as source:
                self.assertEqual(source.db.execute('SELECT COUNT(*) FROM requests').fetchone()[0],1)

    def test_stale_open_handle_refuses_each_reservation_after_lower_cap_rotation(self):
        with tempfile.TemporaryDirectory(dir='/var/tmp') as directory:
            path=Path(directory)/'readiness-requests.sqlite3'
            old=Ledger.open_request_window(path,RiskLimits(),1000,exploratory=True)
            try:
                old.request_budget(1000,'read')
                lower=replace(RiskLimits(),max_rest_per_minute=30,max_submits_per_minute=10)
                with contextlib.closing(Ledger.open_request_window(path,lower,1060,exploratory=True)) as current:
                    self.assertEqual(current.request_budget(1060,'read'),0)
                    guard=object.__new__(transport.GuardedSession)
                    guard.origin=transport.PAPER_URL;guard.read_only=True;guard.lock=threading.Lock()
                    guard.observer=None;guard._session=Mock()
                    guard.before_request=lambda kind:old.request_budget(1060,kind)
                    with self.assertRaisesRegex(SafetyError,'readiness_request_limits_changed'):
                        guard.request('GET',transport.PAPER_URL+'/v2/account')
                    guard._session.request.assert_not_called()
                    for _ in range(40):
                        with self.assertRaisesRegex(SafetyError,'readiness_request_limits_changed'):
                            old.request_budget(1060,'read')
                    self.assertEqual(current.db.execute('SELECT COUNT(*) FROM requests WHERE at>?',(1000,)).fetchone()[0],1)
                    for _ in range(29):self.assertEqual(current.request_budget(1060,'read'),0)
                    self.assertGreater(current.request_budget(1060,'read'),0)
                    self.assertEqual(current.db.execute('SELECT COUNT(*) FROM requests WHERE at>?',(1000,)).fetchone()[0],30)
            finally:
                old.close()

    def test_handoff_and_new_readiness_start_share_one_200_request_window(self):
        with tempfile.TemporaryDirectory(dir='/var/tmp') as directory:
            root=Path(directory);path=root/'readiness-requests.sqlite3'
            with contextlib.closing(Ledger(path)) as source:
                for _ in range(192):source.request_budget(1000,'read')
            with contextlib.closing(Ledger(root/'trading.sqlite3')) as ledger:
                self.handoff(ledger,[],path,1001)
                for _ in range(8):self.assertEqual(ledger.request_budget(1001,'read'),0)
                with runner.readiness_request_window(root,RiskLimits(),enabled=True) as reserve:
                    with self.assertRaisesRegex(transport.TransportError,'readiness_request_budget_exhausted'):
                        reserve(1002,'read')
                self.assertEqual(ledger.db.execute('SELECT COUNT(*) FROM requests').fetchone()[0],200)
                self.handoff(ledger,[],path,1003)
                self.assertEqual(ledger.db.execute('SELECT COUNT(*) FROM requests').fetchone()[0],200)

    def test_source_write_at_handoff_is_in_authoritative_window(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory(dir='/var/tmp') as directory:
            root=Path(directory);path=root/'readiness-requests.sqlite3'
            with contextlib.closing(Ledger(path)) as source:
                for _ in range(192):source.request_budget(1000,'read')
            with contextlib.closing(Ledger(root/'trading.sqlite3')) as ledger:
                transaction=ledger._transaction
                @contextlib.contextmanager
                def late_write():
                    with contextlib.closing(Ledger(path)) as late:late.request_budget(1001,'read')
                    with transaction():yield
                with patch.object(ledger,'_transaction',late_write):self.handoff(ledger,[],path,1001)
                self.assertEqual(ledger.db.execute('SELECT COUNT(*) FROM requests').fetchone()[0],193)
                self.assertEqual(sum(ledger.request_budget(1002,'read')==0 for _ in range(8)),7)

    def test_stale_200_handle_cannot_admit_151st_after_rotation_to_150(self):
        with tempfile.TemporaryDirectory(dir='/var/tmp') as directory:
            path=Path(directory)/'readiness-requests.sqlite3'
            with contextlib.closing(Ledger(path,exploratory=True)) as source:source.request_budget(1000,'read')
            with contextlib.closing(Ledger.open_request_window(path,RiskLimits(),2000,exploratory=True)) as old:
                lower=replace(RiskLimits(),max_rest_per_minute=150,max_submits_per_minute=130)
                with contextlib.closing(Ledger.open_request_window(path,lower,2000,exploratory=True)) as new:
                    for _ in range(150):self.assertEqual(new.request_budget(2000,'read'),0)
                    with self.assertRaisesRegex(SafetyError,'readiness_request_limits_changed'):old.request_budget(2000,'read')
                    self.assertEqual(new.db.execute('SELECT COUNT(*) FROM requests WHERE at>1940').fetchone()[0],150)

    def test_linked_trading_reopen_and_readiness_share_retained_spends(self):
        with tempfile.TemporaryDirectory(dir='/var/tmp') as directory:
            root=Path(directory);path=root/'readiness-requests.sqlite3'
            with contextlib.closing(Ledger(path)) as source:
                for _ in range(199):source.request_budget(1000,'read')
            with contextlib.closing(Ledger(root/'trading.sqlite3')) as ledger:self.handoff(ledger,[],path,1001)
            with contextlib.closing(Ledger(root/'trading.sqlite3')) as ledger:
                self.assertEqual(ledger.request_budget(1001,'cancel'),0)
                with runner.readiness_request_window(root,RiskLimits(),enabled=True) as reserve:
                    with self.assertRaisesRegex(transport.TransportError,'readiness_request_budget_exhausted'):
                        reserve(1002,'data_read')
                self.assertGreater(ledger.request_budget(1002,'read'),0)

    def test_source_commit_before_destination_fault_stays_spent_and_imports_once(self):
        with tempfile.TemporaryDirectory(dir='/var/tmp') as directory:
            root=Path(directory);path=root/'readiness-requests.sqlite3'
            with contextlib.closing(Ledger(path)) as source:source.request_budget(1000,'read')
            with contextlib.closing(Ledger(root/'trading.sqlite3')) as ledger:
                self.handoff(ledger,[],path,1001)
                ledger.db.execute("CREATE TRIGGER fail_mirror BEFORE INSERT ON requests WHEN NEW.kind='cancel' "
                                  "BEGIN SELECT RAISE(ABORT,'synthetic_mirror_fault'); END")
                with self.assertRaisesRegex(sqlite3.IntegrityError,'synthetic_mirror_fault'):
                    ledger.request_budget(1001,'cancel')
                ledger.db.execute('DROP TRIGGER fail_mirror')
                self.handoff(ledger,[],path,1002)
                self.handoff(ledger,[],path,1002)
                self.assertEqual(dict(ledger.db.execute('SELECT kind,COUNT(*) FROM requests GROUP BY kind')),
                                 {'read':1,'cancel':1})
            with contextlib.closing(Ledger(path)) as source:
                self.assertEqual(source.db.execute('SELECT COUNT(*) FROM requests').fetchone()[0],2)

    def test_source_writer_cannot_race_snapshot_and_then_is_counted_authoritatively(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory(dir='/var/tmp') as directory:
            root=Path(directory);path=root/'readiness-requests.sqlite3'
            with contextlib.closing(Ledger(path)) as source:
                for _ in range(199):source.request_budget(1000,'read')
            real_connect=sqlite3.connect;blocked=[]
            def connect(*args,**kwargs):
                db=real_connect(*args,**kwargs)
                if str(args[0]).startswith(path.resolve().as_uri()):
                    def trace(statement):
                        if statement.startswith('SELECT id,at,kind FROM requests'):
                            other=real_connect(path,timeout=0)
                            try:
                                with self.assertRaisesRegex(sqlite3.OperationalError,'locked'):
                                    other.execute("INSERT INTO requests(at,kind) VALUES (1001,'read')")
                                blocked.append(True)
                            finally:other.close()
                    db.set_trace_callback(trace)
                return db
            with contextlib.closing(Ledger(root/'trading.sqlite3')) as ledger:
                with patch.object(sqlite3,'connect',side_effect=connect):self.handoff(ledger,[],path,1001)
                self.assertEqual(blocked,[True])
                with runner.readiness_request_window(root,RiskLimits(),enabled=True) as reserve:reserve(1002,'read')
                self.assertGreater(ledger.request_budget(1002,'read'),0)

    def test_valid_concurrent_row_is_checked_at_locked_snapshot_time(self):
        with tempfile.TemporaryDirectory(dir='/var/tmp') as directory:
            root=Path(directory);path=root/'readiness-requests.sqlite3'
            with contextlib.closing(Ledger(path)) as source:source.request_budget(1001.001,'read')
            with contextlib.closing(Ledger(root/'trading.sqlite3')) as ledger:
                with patch.object(time,'time',return_value=1001.002):
                    ledger.import_request_window(path,1001)
                self.assertEqual(ledger.db.execute('SELECT COUNT(*) FROM requests').fetchone()[0],1)

    def test_budget_telemetry_reads_live_authoritative_source(self):
        import metrics,live_manifest
        with tempfile.TemporaryDirectory(dir='/var/tmp') as directory:
            root=Path(directory);path=root/'readiness-requests.sqlite3';dest=root/'trading.sqlite3'
            with contextlib.closing(Ledger(path)) as source:
                source.request_budget(1000,'read');source.request_budget(1000,'read')
            with contextlib.closing(Ledger(dest)) as ledger:
                self.handoff(ledger,[],path,1001)
                with runner.readiness_request_window(root,RiskLimits(),enabled=True) as reserve:
                    for _ in range(198):reserve(1002,'read')
                self.assertGreater(ledger.request_budget(1002,'read'),0)
                rendered=metrics.render_metrics(dest,root/'trial.json',now=1002)
                self.assertIn('paper_request_budget_remaining{kind="rest"} 0',rendered)
                with patch.object(live_manifest.time,'time',return_value=1002):
                    report=live_manifest.read_ledger(dest)
                self.assertTrue(report['available'])
                self.assertEqual(report['requests_last_minute'],200)

    def test_cap_rotation_does_not_block_recovery_cancel_and_flatten(self):
        import asyncio
        from decimal import Decimal
        from tests import test_adaptive_paper_recovery as fixtures
        from recovery import recover
        from safety import Quote
        with tempfile.TemporaryDirectory(dir='/var/tmp') as directory:
            root=Path(directory);source=root/'readiness-requests.sqlite3';dest=root/'trading.sqlite3'
            now=time.time();old=now-120;limits=RiskLimits(cleanup_seconds=3)
            with contextlib.closing(Ledger(source,exploratory=True)) as startup:startup.request_budget(old,'read')
            with contextlib.closing(Ledger(dest,limits,exploratory=True)) as ledger:
                ledger.start_trial(old)
                controller=fixtures.Controller(ledger)
                class BudgetPort(fixtures.FakePort):
                    async def cancel(self,cid):
                        self.c.ledger.request_budget(self.c.clock(),'cancel')
                        return await super().cancel(cid)
                port=controller.port=BudgetPort(controller)
                ledger.reserve_intent('entry-1','SPY','buy','1','100.01',quote=Quote('SPY','100','100.01',old),
                    now=old,market_open=True,session_close=controller.close)
                ledger.request_budget(old,'submit',client_id='entry-1')
                row={'client_order_id':'entry-1','id':'broker-entry-1','symbol':'SPY','side':'buy','qty':'1',
                     'limit_price':'100.01','filled_qty':'0.5','filled_avg_price':'100.01',
                     'status':'partially_filled','updated_at_ns':int(old*1e9)}
                port.rows['entry-1']=row;port.qty=Decimal('0.5');port.cash-=Decimal('50.005')
                controller.observe(row)
                ledger.import_request_window(source,old+1)
            lower=replace(RiskLimits(),max_rest_per_minute=150,max_submits_per_minute=130)
            with runner.readiness_request_window(root,lower,enabled=True,exploratory=True) as reserve:
                reserve(time.time(),'read')  # another opted start, then refuses its flat gate
            with contextlib.closing(Ledger(dest,limits,exploratory=True)) as ledger:
                controller=fixtures.Controller(ledger);port.c=controller;controller.port=port
                runner.replay_preflight_requests(ledger,[{'timestamp':time.time(),'kind':'read'}])
                result=asyncio.run(recover(controller,{'trial_id':'fault-test','baseline_cash':'10000'},
                    {'cleanup_seconds':3,'quote_max_age_seconds':1,'order_timeout_seconds':.05,
                     'regular_session_only':True,'extended_hours_enabled':False,
                     'sessions':{'extended_hours':False,'overnight_holds':False,'overnight_gross_multiple':'1.0'}},
                    reconcile_fn=fixtures.proof))
                self.assertEqual((result['status'],result['flat']),('passed',True))
                self.assertEqual(port.cancelled,['entry-1'])
                self.assertEqual(len(port.submissions),1)
                self.assertEqual(ledger.limits.max_rest_per_minute,200)


if __name__ == '__main__':
    unittest.main()
