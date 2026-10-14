"""Retained startup requests and cap transitions; synthetic, no broker I/O."""
import contextlib
from dataclasses import replace
from pathlib import Path
import sys
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import Mock

SOURCE = Path(__file__).resolve().parents[1] / 'blueprints/us-equities/adaptive-paper'
sys.path.insert(0, str(SOURCE))
import runner
from safety import Ledger, RiskLimits, SafetyError
import transport


class ReadinessHandoff(unittest.TestCase):
    def handoff(self,ledger,attempts,path,now):
        if hasattr(ledger,'import_request_window'):
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
                    ledger.import_request_window(path,1002)
                self.assertEqual(ledger.db.execute('SELECT COUNT(*) FROM requests').fetchone()[0],0)
                ledger.db.execute('DROP TRIGGER fail_second')
                ledger.import_request_window(path,1002)
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
                    ledger.import_request_window(path,1001)
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


if __name__ == '__main__':
    unittest.main()
