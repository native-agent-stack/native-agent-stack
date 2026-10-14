"""Retained startup requests and cap transitions; synthetic, no broker I/O."""
import contextlib
from dataclasses import replace
from pathlib import Path
import sys
import sqlite3
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'blueprints/us-equities/adaptive-paper'
sys.path.insert(0, str(SOURCE))
import runner
from safety import Ledger, RiskLimits, SafetyError


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


if __name__ == '__main__':
    unittest.main()
