"""T1-T6: synthetic authority/phase guards, no broker or live state."""
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from contextlib import closing
import json
import sys
import tempfile
import unittest

SOURCE=Path(__file__).resolve().parents[1]/'blueprints/us-equities/adaptive-paper'
sys.path.insert(0,str(SOURCE))
import exploration
from safety import Ledger,RiskLimits,SafetyError
from tests import test_adaptive_paper_exploratory_rotation as rotation
from tests import test_adaptive_paper_exploratory_admission as admission

NOW=1800000000.
A='a'*64
B='b'*64


def metadata(trial='first',config=A):
    return {'trial_id':trial,'config_sha256':config,'engine_kind':'adaptive','paper_lane':'B',
            'evidence_class':'exploratory','started_at':NOW,'fee_window_start':NOW,
            'baseline_cash':'10000','phase':'starting'}


def seeded(root):
    ledger=Ledger(Path(root)/'ledger.sqlite3',exploratory=True)
    ledger.begin_next_trial(NOW,'first',config_sha256=A,limits=RiskLimits(),metadata=metadata())
    (Path(root)/'trial.json').write_text(json.dumps(metadata()))
    return ledger


class ExploratoryAuthorityGuards(unittest.TestCase):
    def test_t1_rotation_is_explicit_and_never_enabled_by_recovery(self):
        with tempfile.TemporaryDirectory(dir='/var/tmp') as root:
            path=Path(root)/'ledger.sqlite3'
            with closing(seeded(root)):
                pass
            changed=replace(RiskLimits(),max_order_qty=Decimal(2))
            with self.assertRaisesRegex(SafetyError,'persisted_risk_limits_differ'):
                Ledger(path,changed,exploratory=True)
            with closing(Ledger(path,changed,exploratory=True,rotation=True)) as ledger:
                self.assertEqual(ledger.limits,RiskLimits())
        with self.subTest(engine='adaptive'):
            with self.assertRaisesRegex(SafetyError,'persisted_risk_limits_differ'):
                rotation.ExploratoryRunnerRotation().exercise(command='recover',changed=False,
                                                               recovery_limits_differ=True)
        with self.subTest(engine='mover'):
            with self.assertRaisesRegex(SafetyError,'persisted_risk_limits_differ'):
                rotation.ExploratoryMoverRotation().exercise(command='recover',recovery_limits_differ=True)

    def test_t2_read_authority_refuses_inconsistent_legacy_and_symlink_records(self):
        for case in ('trial','namespace','pre-change','symlink'):
            with self.subTest(case=case), tempfile.TemporaryDirectory(dir='/var/tmp') as root:
                root=Path(root)
                ledger=seeded(root)
                record=metadata()
                if case=='trial':
                    record['trial_id']='another'
                    ledger.db.execute("UPDATE meta SET value=? WHERE key='exploratory_active_trial'",
                                      (json.dumps(record),))
                elif case=='namespace':
                    record['config_sha256']=B
                    ledger.db.execute("UPDATE meta SET value=? WHERE key='exploratory_active_trial'",
                                      (json.dumps(record),))
                elif case=='pre-change':
                    ledger.db.execute("DELETE FROM meta WHERE key='exploratory_active_trial'")
                    (root/'trial.json').write_text(json.dumps(metadata('stale')))
                ledger.close()
                if case=='symlink':
                    (root/'ledger.sqlite3').rename(root/'retained.sqlite3')
                    (root/'ledger.sqlite3').symlink_to(root/'retained.sqlite3')
                reason={'trial':'active_trial_journal_mismatch','namespace':'active_trial_journal_mismatch',
                        'pre-change':'active_trial_projection_unbound','symlink':'ledger_symlink_refused'}[case]
                with self.assertRaisesRegex(SafetyError,reason):
                    exploration.active_trial_metadata(root)

    def test_t3_sql_authority_refuses_changed_identity_and_lineage_atomically(self):
        bad_fields={'trial_id':'another','config_sha256':'c'*64,'paper_lane':'A','evidence_class':'synthetic',
                    'started_at':NOW+1,'fee_window_start':NOW+1,'baseline_cash':'10001',
                    'engine_kind':'mover'}
        for field,value in bad_fields.items():
            with self.subTest(field=field),tempfile.TemporaryDirectory(dir='/var/tmp') as root:
                ledger=seeded(root)
                bad={**metadata(),field:value}
                with self.assertRaises(SafetyError):
                    ledger.update_exploratory_trial(bad)
                self.assertEqual(exploration.active_trial_metadata(root),metadata())
                ledger.close()
        # A registered alternative config is still immutable within one trial.
        with tempfile.TemporaryDirectory(dir='/var/tmp') as root:
            ledger=seeded(root)
            ledger.db.execute('INSERT INTO meta VALUES (?,?)',('exploratory_config:'+B,RiskLimits().frozen_json()))
            with self.assertRaisesRegex(SafetyError,'active_trial_lineage_changed'):
                ledger.update_exploratory_trial(metadata(config=B))
            for field in ('trial_id','config_sha256','started_at','fee_window_start','baseline_cash'):
                with self.subTest(admission_field=field):
                    next_meta=metadata('second',B)
                    next_meta[field]={'trial_id':'another','config_sha256':'c'*64,'started_at':NOW+1,
                                     'fee_window_start':NOW+1,'baseline_cash':'10001'}[field]
                    with self.assertRaises(SafetyError):
                        ledger.begin_next_trial(NOW+1,'second',config_sha256=B,limits=RiskLimits(),metadata=next_meta)
                    self.assertEqual(exploration.active_trial_metadata(root),metadata())
            ledger.close()

    def test_t4_run_and_recovery_phase_commit_before_json_publication(self):
        for engine in ('adaptive','mover'):
            for phase in ('run','recover'):
                with self.subTest(engine=engine,phase=phase):
                    admission.AdmissionPublicationCrash().exercise(engine,final_run_fault=phase=='run',
                                                                   final_recovery_fault=phase=='recover')

    def test_t5_standalone_registration_is_bootstrap_only(self):
        with tempfile.TemporaryDirectory(dir='/var/tmp') as root:
            ledger=seeded(root)
            with self.assertRaisesRegex(SafetyError,'configuration_registration_requires_atomic_admission'):
                ledger.register_exploratory_config(B,RiskLimits(),NOW+1)
            self.assertEqual(ledger.exploratory_config_history(),[A])
            ledger.close()

    def test_t6_mover_recovery_refuses_the_previous_configuration(self):
        with self.assertRaisesRegex(SafetyError,'recovery_config_differs_from_frozen_trial'):
            rotation.ExploratoryMoverRotation().exercise(command='recover',stale_recovery_config=True)
