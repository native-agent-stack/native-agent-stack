"""Synthetic exploratory rotation: real account journal, no broker or credentials."""
from dataclasses import replace
from contextlib import closing
from decimal import Decimal
from pathlib import Path
import sys
import tempfile
import unittest
import asyncio
import contextlib
import hashlib
import json
from unittest.mock import AsyncMock, Mock, patch
from uuid import UUID

SOURCE = Path(__file__).resolve().parents[1] / "blueprints/us-equities/adaptive-paper"
sys.path.insert(0, str(SOURCE))
from safety import Ledger, Quote, RiskLimits, SafetyError
import runner
import mover_runner
import transport
import safety
from tests.adaptive_paper_hermetic import patch_default_stop, restore_default_stop

FIXTURE_FEE_ID = "1800000000::" + str(UUID(int=1))
_STOP_TOKEN = None


def setUpModule():
    global _STOP_TOKEN
    _STOP_TOKEN = patch_default_stop(safety, runner)


def tearDownModule():
    restore_default_stop(_STOP_TOKEN)


class ExploratoryLedgerRotation(unittest.TestCase):
    def test_completed_flat_rotation_preserves_fee_cash_and_request_history(self):
        with tempfile.TemporaryDirectory(dir="/var/tmp") as root:
            path = Path(root) / "ledger.sqlite3"
            first = RiskLimits()
            second = replace(first, max_order_qty=Decimal("2"))
            ledger = Ledger(path, first, exploratory=True)
            ledger.register_exploratory_config("a" * 64, first, 1800000000.)
            ledger.begin_next_trial(1800000000., "first")
            ledger.record_fees([{"id": FIXTURE_FEE_ID,
                                 "date": "2027-01-15", "net_amount": "-0.25", "sub_type": "REG"}], 1800000001.)
            quote=Quote('SPY','100','100.01',1800000001.)
            ledger.reserve_intent('first-buy','SPY','buy','1','100.02',quote=quote,now=1800000001.,
                                  market_open=True,session_close=1800003600.,stop_file=Path(root)/'STOP')
            ledger.record_order('first-buy','synthetic-buy','filled','1','100')
            ledger.reserve_intent('first-sell','SPY','sell','1','99.99',quote=quote,now=1800000001.,
                                  market_open=True,session_close=1800003600.,stop_file=Path(root)/'STOP')
            ledger.record_order('first-sell','synthetic-sell','filled','1','100')
            ledger.request_budget(1800000001., "read")
            before = ledger.accounting()
            ledger.close()
            ledger = Ledger(path, second, exploratory=True, rotation=True)
            self.assertEqual(ledger.limits, first)  # old limits remain until reconciled transition
            ledger.begin_next_trial(1800000002., "second",config_sha256='b'*64,limits=second)
            self.assertEqual(ledger.accounting().cash_delta_usd, before.cash_delta_usd)
            self.assertEqual(len(ledger.fees()), 1)
            self.assertEqual(ledger.limits, second)
            self.assertEqual(len(ledger.intents()),2)
            self.assertEqual(ledger.db.execute("SELECT COUNT(*) FROM requests").fetchone()[0], 1)
            ledger.close()
            with closing(Ledger(path, second, exploratory=True)) as reopened:
                self.assertEqual(reopened.accounting().cash_delta_usd, Decimal("-0.25"))
                self.assertEqual(reopened.exploratory_config_history(), ["a" * 64, "b" * 64])

    def test_lane_a_journal_cannot_be_adopted_by_exploratory_rotation(self):
        with tempfile.TemporaryDirectory(dir="/var/tmp") as root:
            path = Path(root) / "ledger.sqlite3"
            with closing(Ledger(path, RiskLimits())):
                pass
            with self.assertRaisesRegex(SafetyError, "exploratory_journal_required"):
                Ledger(path, RiskLimits(), exploratory=True)

    def test_default_lane_a_still_refuses_changed_limits(self):
        with tempfile.TemporaryDirectory(dir="/var/tmp") as root:
            path = Path(root) / "ledger.sqlite3"
            with closing(Ledger(path, RiskLimits())):
                pass
            with self.assertRaisesRegex(SafetyError, "persisted_risk_limits_differ"):
                Ledger(path, replace(RiskLimits(), max_order_qty=Decimal("2")))


class ExploratoryRunnerRotation(unittest.TestCase):
    def exercise(self, *, exploratory=True, cash="9999.75", phase="finished", changed=True,
                 command="paper", extra=(), unsafe_output=False, stopped=False, bad_lineage=False,
                 engine_kind='adaptive', recovery_limits_differ=False):
        with tempfile.TemporaryDirectory(dir="/var/tmp") as root:
            root = Path(root)
            state_root = root / "exploratory" / "account-state" if exploratory else root / "qualification"
            state_dir = state_root / ("0" * 64) / "adaptive"
            config, limits, policy = runner.load_config(SOURCE / "config.json")
            if exploratory:
                config.update(paper_lane="B", evidence_class="exploratory")
            config_file = root / "config.json"
            config_file.write_text(json.dumps({k:v for k,v in config.items() if not k.startswith("_")}))
            # The baseline does not expose config_digest or exploratory journal
            # registration; its fixture still drives the same main() contract.
            sha = hashlib.sha256(config_file.read_bytes()).hexdigest()
            if hasattr(runner, "config_digest"):
                sha = runner.config_digest(config, config_file.read_bytes(), limits=limits)
            b_kwargs = {"exploratory": True} if exploratory and hasattr(Ledger, "register_exploratory_config") else {}
            stored_limits=replace(limits,max_order_qty=Decimal(2)) if recovery_limits_differ else limits
            ledger = Ledger(state_dir / "ledger.sqlite3", stored_limits, **b_kwargs)
            ledger.begin_next_trial(1800000000., "first",
                **({'config_sha256':'a'*64 if changed else sha,'limits':stored_limits} if exploratory else {}))
            ledger.record_fees([{"id": FIXTURE_FEE_ID,
                                 "date": "2027-01-15", "net_amount": "-0.25", "sub_type": "REG"}], 1800000001.)
            ledger.close()
            metadata = {"trial_id":"first", "phase":phase, "config_sha256":"a"*64 if changed else sha,
                        "started_at":1800000000., "fee_window_start":1800000000., "baseline_cash":"10000"}
            if exploratory:
                metadata.update(paper_lane="A" if bad_lineage else "B", evidence_class="exploratory",
                                engine_kind=engine_kind)
            (state_dir / "trial.json").write_text(json.dumps(metadata))
            output = root / ("qualification" if unsafe_output else "exploratory") / "receipt.json"
            stop=root/'STOP'
            if stopped:
                stop.write_text('fixture-stop')
            observation = {"account_identity_sha256":"0"*64, "account":{"cash":cash}, "assets":[]}
            async def native(*args, **kwargs):
                self.assertEqual(args[5], "10000")
                return {"status":"completed_no_signals", "flat":True, "native_fill_events":0,
                        "evidence_class":"SYN"}
            argv=["runner.py",command,"--credentials","keychain-env","--config",str(config_file),
                  "--state-root",str(state_root),"--output",str(output),"--trial","second",*extra]
            with patch.object(sys,"argv",argv), patch.object(runner,"DEFAULT_STOP",stop), \
                 patch.object(runner,"load_config",return_value=(config,limits,policy)), \
                 patch.object(runner,"check_order_contract_boundary",return_value={}), \
                 patch.object(runner,"paper_credentials",return_value=(None,None)), \
                 patch.object(runner,"preflight",return_value=observation), \
                 patch.object(runner,"public_preflight",return_value={}), \
                 patch.object(runner,"validate_preflight",return_value=1800003600.), \
                 patch.object(runner,"account_lock_fingerprint",return_value=contextlib.nullcontext()), \
                 patch.object(runner,"fee_activities",return_value=[]), \
                 patch.object(runner,"AlpacaPaperTransport",return_value=Mock()), \
                 patch('recovery.recover',new=AsyncMock(return_value={'status':'passed','flat':True,
                       'native_fill_events':0,'evidence_class':'SYN'})), \
                 patch.object(runner,"run_native",side_effect=native), \
                 patch.object(runner.time,"time",return_value=1800000002.):
                try:
                    rc=runner.main()
                except ValueError:
                    if unsafe_output:
                        self.assertIsNone(runner.LAST_OUTPUT)
                        self.assertFalse(output.exists())
                    raise
            self.assertEqual(rc,0)
            result=json.loads(output.read_text())
            current=json.loads((state_dir/'trial.json').read_text())
            self.assertEqual(current['fee_window_start'],1800000000.)
            self.assertEqual(current['baseline_cash'],"10000")
            self.assertEqual(result.get('paper_lane'),"B")
            self.assertEqual(result.get('evidence_class'),"exploratory")
            self.assertEqual(result.get('execution_evidence_class'),"SYN")
            self.assertEqual(current['config_sha256'],sha)

    def test_changed_exploratory_config_keeps_original_cash_and_fee_lineage(self):
        self.exercise()

    def test_changed_lane_a_config_still_refuses(self):
        with self.assertRaisesRegex(SafetyError,"next_trial_config_differs_from_frozen_limits"):
            self.exercise(exploratory=False)

    def test_exploratory_cash_drift_still_refuses(self):
        with self.assertRaisesRegex(SafetyError,"next_trial_cash_mismatch"):
            self.exercise(cash="10000")

    def test_exploratory_unfinished_trial_still_requires_recovery(self):
        with self.assertRaisesRegex(SafetyError,"existing_trial_requires_explicit_recovery"):
            self.exercise(phase="starting")

    def test_recovery_still_requires_the_original_config(self):
        with self.assertRaisesRegex(SafetyError,"recovery_config_differs_from_frozen_trial"):
            self.exercise(command="recover")

    def test_qualification_proofs_are_refused_on_lane_b(self):
        with self.assertRaisesRegex(SafetyError,"exploratory_qualification_forbidden"):
            self.exercise(extra=["--gate-result","unused.json"])

    def test_lane_b_cannot_write_a_qualification_receipt(self):
        with self.assertRaisesRegex(ValueError,"exploratory_path_required"):
            self.exercise(unsafe_output=True)

    def test_lane_b_stop_latch_refuses_a_new_trial(self):
        with self.assertRaisesRegex(SafetyError,'global_stop_latched'):
            self.exercise(stopped=True)

    def test_runner_refuses_non_exploratory_trial_lineage(self):
        with self.assertRaisesRegex(SafetyError,'exploratory_trial_lineage_required'):
            self.exercise(bad_lineage=True)

    def test_runner_recovery_cannot_take_over_mover_trial(self):
        with self.assertRaisesRegex(SafetyError,'recovery_engine_differs_from_frozen_trial'):
            self.exercise(command='recover',changed=False,engine_kind='mover')


class ExploratoryJournalGuards(unittest.TestCase):
    def test_lane_a_cannot_reopen_a_lane_b_journal(self):
        with tempfile.TemporaryDirectory(dir='/var/tmp') as root:
            p=Path(root)/'ledger.sqlite3'
            ledger=Ledger(p,exploratory=True);ledger.close()
            with self.assertRaisesRegex(SafetyError,'exploratory_journal_requires_lane_b'):
                Ledger(p)

    def test_rotation_cannot_clear_a_latched_halt(self):
        with tempfile.TemporaryDirectory(dir='/var/tmp') as root:
            ledger=Ledger(Path(root)/'ledger.sqlite3',exploratory=True)
            ledger.begin_next_trial(1800000000.,'first')
            ledger.freeze('fixture_halt')
            with self.assertRaisesRegex(SafetyError,'next_trial_cannot_clear_risk_halt'):
                ledger.begin_next_trial(1800000001.,'second',config_sha256='a'*64,limits=RiskLimits())
            self.assertEqual(ledger.exploratory_config_history(),[])
            ledger.close()

    def test_rotation_cannot_lower_budget_below_accumulated_loss(self):
        with tempfile.TemporaryDirectory(dir='/var/tmp') as root:
            ledger=Ledger(Path(root)/'ledger.sqlite3',exploratory=True)
            ledger.begin_next_trial(1800000000.,'first')
            ledger.record_fees([{'id':FIXTURE_FEE_ID,'date':'2027-01-15','net_amount':'-7','sub_type':'REG'}],1800000001.)
            new=replace(RiskLimits(),max_gross_loss_usd=Decimal(5),max_drawdown_usd=Decimal(5))
            with self.assertRaisesRegex(SafetyError,'next_trial_risk_budget_exhausted'):
                ledger.begin_next_trial(1800000002.,'second',config_sha256='a'*64,limits=new)
            self.assertEqual(ledger.accounting().cash_delta_usd,Decimal(-7))
            self.assertEqual(ledger.exploratory_config_history(),[])
            ledger.close()

    def test_duplicate_trial_cannot_publish_new_limits_or_namespace(self):
        with tempfile.TemporaryDirectory(dir="/var/tmp") as root:
            path=Path(root)/'ledger.sqlite3';old=RiskLimits()
            ledger=Ledger(path,old,exploratory=True)
            ledger.begin_next_trial(1800000000.,'used')
            new=replace(old,max_order_qty=Decimal(2))
            with self.assertRaisesRegex(SafetyError,'trial_id_already_used'):
                ledger.begin_next_trial(1800000001.,'used',config_sha256='b'*64,limits=new)
            self.assertEqual(ledger.limits,old)
            self.assertEqual(ledger.exploratory_config_history(),[])
            ledger.close()
            ledger=Ledger(path,old,exploratory=True);ledger.close()

    def test_registration_cannot_clear_unresolved_orders(self):
        with tempfile.TemporaryDirectory(dir="/var/tmp") as root:
            root=Path(root)
            ledger=Ledger(root/'ledger.sqlite3',RiskLimits(),exploratory=True)
            ledger.begin_next_trial(1800000000.,'first')
            ledger.reserve_intent('owned-test','SPY','buy','1','100.02',
                                  quote=Quote('SPY','100','100.01',1800000000.),now=1800000000.,
                                  market_open=True,session_close=1800003600.,stop_file=root/'STOP')
            before=ledger.limits
            with self.assertRaisesRegex(SafetyError,'next_trial_requires_flat_and_terminal'):
                ledger.begin_next_trial(1800000001.,'second',config_sha256='b'*64,
                                        limits=replace(before,max_order_qty=Decimal(2)))
            self.assertEqual(ledger.limits,before)
            self.assertEqual(ledger.exploratory_config_history(),[])
            ledger.close()

    def test_exploratory_label_refusal_leaves_qualification_journal_bytes_unchanged(self):
        with tempfile.TemporaryDirectory(dir="/var/tmp") as root:
            p=Path(root)/'ledger.sqlite3'
            ledger=Ledger(p);ledger.close()
            before=p.read_bytes()
            with self.assertRaisesRegex(SafetyError,'exploratory_journal_required'):
                Ledger(p,exploratory=True)
            self.assertEqual(p.read_bytes(),before)


class ExploratoryMoverRotation(unittest.TestCase):
    def test_mover_uses_the_existing_account_journal_and_fee_window(self):
        self.exercise()

    def exercise(self,*,stopped=False,stop_at_lock=False,bad_lineage=False,command='paper',bad_engine=False,
                 recovery_limits_differ=False, stale_recovery_config=False):
        from tests.test_adaptive_paper_mover import scan_dict, MoverCommandSessionWiring
        fixture=MoverCommandSessionWiring()
        now=fixture.SERVER
        with tempfile.TemporaryDirectory(dir="/var/tmp") as root:
            root=Path(root)/"exploratory";root.mkdir()
            state=root/'account-state';state_dir=state/fixture.FINGERPRINT/'adaptive'
            old=RiskLimits()
            config=json.loads((SOURCE/'config-mover.json').read_text())
            config.update(paper_lane='B',evidence_class='exploratory')
            config['exploratory_exit_preset']={'version':'paper-exits-v1-20261012','name':'X3'}
            config_path=root/'config.json';config_path.write_text(json.dumps(config))
            config_loaded,new_limits,_=mover_runner.load_mover_config(config_path)
            new_sha=runner.config_digest(config_loaded,config_path.read_bytes(),limits=new_limits)
            if command=='recover':
                old=new_limits
                if recovery_limits_differ:
                    old=replace(old,max_order_qty=Decimal(1))
            kwargs={'exploratory':True} if hasattr(Ledger,'register_exploratory_config') else {}
            ledger=Ledger(state_dir/'ledger.sqlite3',old,**kwargs)
            old_sha=new_sha if command=='recover' else 'a'*64
            ledger.begin_next_trial(now-10,'baseline',config_sha256=old_sha,limits=old)
            ledger.record_fees([{'id':FIXTURE_FEE_ID,
                                'date':'2026-09-24','net_amount':'-0.25','sub_type':'REG'}],now-9)
            ledger.close()
            previous={'trial_id':'baseline','config_sha256':old_sha,'started_at':now-10,'fee_window_start':now-10,
                      'baseline_cash':'10000','phase':'finished','paper_lane':'A' if bad_lineage else 'B',
                      'evidence_class':'exploratory','engine_kind':'adaptive' if bad_engine else 'mover'}
            (state_dir/'trial.json').write_text(json.dumps(previous))
            if stale_recovery_config:
                # The published mover trial is bound to its original config;
                # this older recovery config differs without changing limits.
                config['mover']['max_scan_age_seconds']=299
                config_path.write_text(json.dumps(config))
            scan_path=root/'scan.json';scan_path.write_text(json.dumps(scan_dict(regime={'factor':'1'})))
            output=root/'receipt.json'
            obs=fixture.observation(['ABCD','WXYZ','SPY']);obs['account']['cash']='9999.75'
            async def native(*args,**_):
                self.assertEqual(args[3],'10000')
                return {'status':'completed_no_signals','flat':True,'native_fill_events':0,'legs':[]}
            checkpoint={'account':{'cash':'9999.75'},'fees':[]}
            stop=root/'STOP'
            if stopped:
                stop.write_text('fixture')
            @contextlib.contextmanager
            def lock(_):
                if stop_at_lock:
                    stop.write_text('fixture')
                yield
            with patch.object(mover_runner,'credentials',return_value=(None,None)), \
                 patch.object(safety,'DEFAULT_STOP',stop), \
                 patch.object(transport,'preflight',return_value=obs), \
                 patch.object(transport,'fee_checkpoint',return_value=checkpoint) as fees, \
                 patch.object(transport,'AlpacaPaperTransport',return_value=Mock()), \
                 patch.object(mover_runner,'validate_preflight',return_value=now+3600), \
                 patch.object(mover_runner,'account_lock_fingerprint',side_effect=lock), \
                 patch.object(mover_runner,'run_mover',side_effect=native), \
                 patch.object(mover_runner,'recover_mover',new=AsyncMock(return_value={
                     'status':'passed','flat':True,'native_fill_events':0,'evidence_class':'SYN'})), \
                 patch.object(mover_runner.time,'time',return_value=now):
                args=[command,'--env-file',str(root/'unused.env'),'--config',str(config_path),
                      '--state-root',str(state),'--output',str(output)]
                if command=='paper':
                    args+=['--scan',str(scan_path),'--trial','mover-second']
                rc=mover_runner.main(args)
            self.assertEqual(rc,0,json.loads(output.read_text()).get('reason'))
            if command=='recover':
                return
            result=json.loads(output.read_text());meta=json.loads((state_dir/'trial.json').read_text())
            self.assertEqual(result['exit_rule'],'X3')
            self.assertEqual(result['paper_lane'],'B')
            self.assertEqual(result['evidence_class'],'exploratory')
            self.assertEqual(meta['baseline_cash'],'10000')
            self.assertEqual(meta['fee_window_start'],now-10)
            self.assertEqual(meta['engine_kind'],'mover')
            self.assertEqual(fees.call_args.kwargs['after'].timestamp(),now-10)
            self.assertFalse((state/fixture.FINGERPRINT/'mover').exists())
            with closing(Ledger(state_dir/'ledger.sqlite3',old,exploratory=True,rotation=True)) as reopened:
                self.assertEqual(reopened.accounting().cash_delta_usd,Decimal('-.25'))
                self.assertEqual(reopened.exploratory_config_history(),['a'*64,meta['config_sha256']])

    def test_mover_stop_latch_refuses_before_a_new_trial(self):
        with self.assertRaisesRegex(SafetyError,'global_stop_latched'):
            self.exercise(stopped=True)

    def test_mover_stop_is_rechecked_under_the_account_lock(self):
        with self.assertRaisesRegex(SafetyError,'global_stop_latched'):
            self.exercise(stop_at_lock=True)

    def test_mover_refuses_non_exploratory_trial_lineage(self):
        with self.assertRaisesRegex(SafetyError,'exploratory_trial_lineage_required'):
            self.exercise(bad_lineage=True)

    def test_mover_recovery_cannot_take_over_adaptive_trial(self):
        with self.assertRaisesRegex(SafetyError,'recovery_engine_differs_from_frozen_trial'):
            self.exercise(command='recover',bad_engine=True)
