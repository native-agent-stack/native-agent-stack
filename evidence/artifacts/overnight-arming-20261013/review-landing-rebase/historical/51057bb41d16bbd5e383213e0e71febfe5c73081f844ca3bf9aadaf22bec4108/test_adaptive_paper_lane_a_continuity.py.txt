"""Synthetic lane-A session-only continuity; no broker or account state."""
import asyncio
import contextlib
from contextlib import closing
from copy import deepcopy
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from uuid import UUID
from unittest.mock import AsyncMock, Mock, patch

SOURCE=Path(__file__).resolve().parents[1]/"blueprints/us-equities/adaptive-paper"
sys.path.insert(0,str(SOURCE))
import runner
from safety import Ledger, Quote, SafetyError
from tests.adaptive_paper_hermetic import patch_default_stop, restore_default_stop

TOKEN=None
# Worked from the shipped 1x fixture with only the three session flags omitted.
ONE_X_FROZEN_SHA256="933e4753e231f6aadbaaed0c2810adc336dad0baa5be54e48617597584a0ef49"


def setUpModule():
    global TOKEN
    TOKEN=patch_default_stop()


def tearDownModule():
    restore_default_stop(TOKEN)


class LaneASessionContinuity(unittest.TestCase):
    def exercise(self,*,command="paper",change="session",phase="finished",cash="9999.75",halt=None,
                 unresolved=False,stored_binding=None,unknown_prior=False,second_trial=False,
                 race=None,interrupted_then_recover=False):
        with tempfile.TemporaryDirectory(dir="/var/tmp") as directory:
            root=Path(directory)
            old_path=SOURCE/"config-leverage-1x.json"
            original=json.loads(old_path.read_text())
            changed=json.loads(old_path.read_text())
            if change in ("session","session-risk","session-stop"):
                changed["regular_session_only"]=False
                changed["extended_hours_enabled"]=True
                changed["sessions"]["extended_hours"]=True
                if change=="session-risk":
                    changed["max_gross_loss_usd"]="26"
                elif change=="session-stop":
                    changed["stop_bps"]+=1
            elif change=="timeout":
                changed["order_timeout_seconds"]+=1
            elif change=="stop":
                changed["stop_bps"]+=1
            elif change=="universe":
                changed["symbols"]=changed["symbols"][:-1]
            elif change=="rung":
                changed=json.loads((SOURCE/"config-leverage-2x.json").read_text())
            elif change=="added-key":
                changed["continuity_note"]="synthetic"
            elif change=="removed-key":
                del changed["notes"]
            elif change=="type":
                changed["max_order_notional_usd"]=1000
            elif change=="nesting":
                changed["notes"]={"text":changed["notes"]}
            config_path=root/"config.json"
            if change=="exact":
                config_path.write_bytes(old_path.read_bytes())
            else:
                config_path.write_text(json.dumps(changed))
            admitted_bytes=config_path.read_bytes()
            config,limits,pc=runner.load_config(config_path)
            real_load=runner.load_config
            executions=[]
            recovery_calls=0
            def load_with_path_edit(path,**kwargs):
                if race:
                    edited=json.loads(Path(path).read_bytes())
                    if race=="stop":
                        edited["stop_bps"]=2500
                    elif race=="universe":
                        edited["symbols"]=edited["symbols"][:-1]
                    Path(path).write_text(json.dumps(edited))
                return real_load(path,**kwargs)
            _,old_limits,_=runner.load_config(old_path)
            state_root=root/"account-state"
            state=state_root/("0"*64)/"adaptive"
            state.mkdir(parents=True)
            now=1800028800.  # 2027-01-15 16:00Z, inside the synthetic RTH session.
            old_meta={"trial_id":"prior","phase":phase,"config_sha256":hashlib.sha256(old_path.read_bytes()).hexdigest(),
                      "started_at":now,"fee_window_start":now,"baseline_cash":"10000"}
            if unknown_prior:
                old_meta["config_sha256"]="f"*64
            if stored_binding is not None:
                old_meta["frozen_trading_config_sha256"]=stored_binding
            with closing(Ledger(state/"ledger.sqlite3",old_limits)) as ledger:
                ledger.begin_next_trial(now,"prior")
                ledger.request_budget(now,"read")
                ledger.record_fees([{"id":"1800000000::"+str(UUID(int=2)),
                    "date":"2027-01-15","net_amount":"-0.25","sub_type":"REG"}],now+1)
                if unresolved:
                    ledger.reserve_intent("owned-synthetic","SPY","buy","1","100.02",
                        quote=Quote("SPY","100","100.01",now),now=now,
                        market_open=True,session_close=now+3600)
                if halt:
                    ledger.freeze(halt)
            (state/"trial.json").write_text(json.dumps(old_meta))
            output=root/"receipt.json"
            argv=["runner.py",command,"--credentials","keychain-env","--config",str(config_path),
                  "--output",str(output),"--trial","next","--state-root",str(state_root)]
            observe={"account_identity_sha256":"0"*64,"account":{"cash":cash},"assets":[]}
            async def native(*args,**kwargs):
                executions.append((args[4],args[1]))
                if interrupted_then_recover and len(executions)==2:
                    args[0].ledger.reserve_intent("interrupted-synthetic","SPY","buy","1","100.02",
                        quote=Quote("SPY","100","100.01",now+2),now=now+2,
                        market_open=True,session_close=now+3600)
                    return {"status":"needs_attention","flat":False,"native_fill_events":0}
                return {"status":"completed_no_signals","flat":True,"native_fill_events":0}
            async def recover(*args,**kwargs):
                nonlocal recovery_calls
                recovery_calls+=1
                executions.append((args[2],None))
                if interrupted_then_recover:
                    if recovery_calls==1:
                        raise SafetyError("synthetic_forced_recovery_failure")
                    args[0].ledger.record_order("interrupted-synthetic","synthetic-broker-order",
                                               "canceled","0",None,timestamp=now+2)
                return {"status":"passed","flat":True,"positions":[],"unresolved_orders":[],
                        "reconciliation":{"positions":0,"open_orders":0}}
            with patch.object(sys,"argv",argv), \
                 patch.object(runner,"load_config",side_effect=load_with_path_edit), \
                 patch.object(runner,"check_order_contract_boundary",return_value={}), \
                 patch.object(runner,"paper_credentials",return_value=(None,None)), \
                 patch.object(runner,"preflight",return_value=observe), \
                 patch.object(runner,"public_preflight",return_value={}), \
                 patch.object(runner,"validate_preflight",return_value=now+3600), \
                 patch.object(runner,"account_lock_fingerprint",return_value=contextlib.nullcontext()), \
                 patch.object(runner,"fee_activities",return_value=[]), \
                 patch.object(runner,"AlpacaPaperTransport",return_value=Mock()), \
                 patch("recovery.recover",side_effect=recover), \
                 patch.object(runner,"run_native",side_effect=native), \
                 patch.object(runner.time,"time",return_value=now+2):
                rc=runner.main()
                if interrupted_then_recover:
                    self.assertEqual(rc,0)
                    first=json.loads((state/"trial.json").read_text())
                    self.assertEqual(first["frozen_trading_config_sha256"],ONE_X_FROZEN_SHA256)
                    self.assertFalse(any(hashlib.sha256(p.read_bytes()).hexdigest()==first["config_sha256"]
                                         for p in SOURCE.glob("config*.json")))
                    argv[argv.index("--trial")+1]="interrupted"
                    with self.assertRaisesRegex(SafetyError,"^synthetic_forced_recovery_failure$"):
                        runner.main()
                    interrupted=json.loads((state/"trial.json").read_text())
                    self.assertEqual(interrupted["phase"],"starting")
                    self.assertEqual(interrupted["config_sha256"],hashlib.sha256(admitted_bytes).hexdigest())
                    argv[1]="recover"
                    self.assertEqual(runner.main(),0)
                    recovered=json.loads((state/"trial.json").read_text())
                    self.assertEqual(recovered["phase"],"finished")
                    self.assertEqual(recovered["config_sha256"],hashlib.sha256(admitted_bytes).hexdigest())
                    config_path.write_bytes(old_path.read_bytes())
                    argv[1]="paper"
                    argv[argv.index("--trial")+1]="after-recovery"
                    rc=runner.main()
                    self.assertEqual(interrupted["frozen_trading_config_sha256"],ONE_X_FROZEN_SHA256)
                    self.assertEqual(recovered["frozen_trading_config_sha256"],ONE_X_FROZEN_SHA256)
                    self.assertEqual(recovery_calls,2)
                if second_trial:
                    self.assertEqual(rc,0)
                    first=json.loads((state/"trial.json").read_text())
                    self.assertEqual(first["frozen_trading_config_sha256"],ONE_X_FROZEN_SHA256)
                    # The first supplied PRE/POST config is not shipped, so the
                    # next RTH trial must consume the newly persisted binding.
                    self.assertFalse(any(hashlib.sha256(p.read_bytes()).hexdigest()==first["config_sha256"]
                                         for p in SOURCE.glob("config*.json")))
                    config_path.write_bytes(old_path.read_bytes())
                    argv[argv.index("--trial")+1]="next-two"
                    rc=runner.main()
            self.assertEqual(rc,0)
            latest=json.loads((state/"trial.json").read_text())
            self.assertEqual(latest["fee_window_start"],now)
            self.assertEqual(latest["baseline_cash"],"10000")
            expected_bytes=admitted_bytes if race else config_path.read_bytes()
            if race:
                self.assertNotEqual(config_path.read_bytes(),admitted_bytes)
                self.assertEqual(len(executions),1)
                executed,policy=executions[0]
                self.assertEqual(executed["stop_bps"],25)
                self.assertEqual(executed["symbols"],original["symbols"])
                if policy is not None:
                    self.assertEqual(policy.stop_bps,25)
                    self.assertEqual(policy.symbols,tuple(original["symbols"]))
            self.assertEqual(latest["config_sha256"],hashlib.sha256(expected_bytes).hexdigest())
            if command=="paper":
                self.assertEqual(latest["frozen_trading_config_sha256"],ONE_X_FROZEN_SHA256)
            elif stored_binding is not None:
                self.assertEqual(latest["frozen_trading_config_sha256"],stored_binding)
            with closing(Ledger(state/"ledger.sqlite3",limits)) as ledger:
                self.assertEqual(ledger.accounting().cash_delta_usd,Decimal("-0.25"))
                self.assertEqual(len(ledger.fees()),1)
                self.assertGreaterEqual(ledger.db.execute("SELECT COUNT(*) FROM requests").fetchone()[0],1)
            return latest

    def test_session_fields_only_start_continues_existing_risk_and_cash_lineage(self):
        self.exercise()

    def test_path_edit_before_real_loader_cannot_change_admitted_stop_or_universe(self):
        for race in ("stop","universe"):
            with self.subTest(race=race):
                self.exercise(race=race)

    def test_path_edit_cannot_change_recovery_execution_or_raw_provenance(self):
        for race in ("stop","universe"):
            with self.subTest(race=race):
                self.exercise(command="recover",change="exact",race=race,stored_binding=ONE_X_FROZEN_SHA256)

    def test_session_fields_only_recovery_refuses_changed_trial_bytes(self):
        with self.assertRaisesRegex(SafetyError,"^recovery_config_differs_from_frozen_trial$"):
            self.exercise(command="recover")

    def test_recovery_refuses_a_changed_non_risk_timeout(self):
        with self.assertRaisesRegex(SafetyError,"^recovery_config_differs_from_frozen_trial$"):
            self.exercise(command="recover",change="timeout")

    def test_recovery_refuses_formatting_only_change(self):
        with self.assertRaisesRegex(SafetyError,"^recovery_config_differs_from_frozen_trial$"):
            self.exercise(command="recover",change="format")

    def test_recovery_accepts_exact_trial_bytes(self):
        self.exercise(command="recover",change="exact")

    def test_recovery_does_not_add_a_new_next_trial_binding(self):
        latest=self.exercise(command="recover",change="exact")
        self.assertNotIn("frozen_trading_config_sha256",latest)

    def test_recovery_preserves_the_existing_next_trial_binding(self):
        latest=self.exercise(command="recover",change="exact",stored_binding="e"*64)
        self.assertEqual(latest["frozen_trading_config_sha256"],"e"*64)

    def test_interrupted_unshipped_trial_recovers_exact_bytes_then_admits_rth(self):
        latest=self.exercise(interrupted_then_recover=True)
        self.assertEqual(latest["trial_id"],"after-recovery")

    def test_next_trial_consumes_the_binding_written_by_the_previous_trial(self):
        latest=self.exercise(second_trial=True)
        self.assertEqual(latest["trial_id"],"next-two")

    def test_stored_binding_mismatch_refuses_even_when_legacy_bytes_match(self):
        with self.assertRaisesRegex(SafetyError,"^next_trial_config_differs_from_frozen_limits$"):
            self.exercise(stored_binding="e"*64)

    def test_unknown_legacy_config_refuses_through_main(self):
        with self.assertRaisesRegex(SafetyError,"^next_trial_config_differs_from_frozen_limits$"):
            self.exercise(unknown_prior=True)

    def test_session_change_cannot_bypass_unresolved_orders(self):
        with self.assertRaisesRegex(SafetyError,"^next_trial_requires_recovery$"):
            self.exercise(unresolved=True)

    def test_combined_session_and_risk_changes_still_refuse(self):
        for change,reason in (("session-risk","persisted_risk_limits_differ"),
                              ("session-stop","next_trial_config_differs_from_frozen_limits")):
            with self.subTest(change=change),self.assertRaisesRegex(SafetyError,"^"+reason+"$"):
                self.exercise(change=change)

    def test_added_removed_typed_and_nested_fields_stay_frozen_through_main(self):
        for change in ("added-key","removed-key","type","nesting"):
            with self.subTest(change=change),self.assertRaisesRegex(SafetyError,"^next_trial_config_differs_from_frozen_limits$"):
                self.exercise(change=change)

    def test_trading_fields_and_rung_changes_still_refuse(self):
        for change,reason in (("stop","next_trial_config_differs_from_frozen_limits"),
                              ("universe","next_trial_config_differs_from_frozen_limits"),
                              ("rung","persisted_risk_limits_differ")):
            with self.subTest(change=change),self.assertRaisesRegex(SafetyError,"^"+reason+"$"):
                self.exercise(change=change)

    def test_unfinished_cash_drift_and_latched_halt_cannot_be_evaded_by_a_session_change(self):
        for kwargs,reason in (({"phase":"starting"},"existing_trial_requires_explicit_recovery"),
                              ({"cash":"10001"},"next_trial_cash_mismatch"),
                              ({"halt":"drawdown_cap_reached"},"next_trial_cannot_clear_risk_halt")):
            with self.subTest(kwargs=kwargs),self.assertRaisesRegex(SafetyError,"^"+reason+"$"):
                self.exercise(**kwargs)

    def test_new_binding_is_deterministic_and_freezes_every_other_field(self):
        raw=json.loads((SOURCE/"config-leverage-1x.json").read_text())
        old=runner.frozen_trading_config_sha256(raw)
        changed=json.loads(json.dumps(raw))
        changed.update(regular_session_only=False,extended_hours_enabled=True)
        changed["sessions"]["extended_hours"]=True
        self.assertEqual(runner.frozen_trading_config_sha256(changed),old)
        self.assertEqual(runner.frozen_trading_config_sha256(dict(reversed(list(raw.items())))),old)
        for key,value in (("feed","iex"),("stop_bps",26),("max_order_notional_usd","999"),
                          ("max_gross_loss_usd","24"),("max_api_requests_per_minute",199),
                          ("duration_seconds",301)):
            with self.subTest(key=key):
                self.assertNotEqual(runner.frozen_trading_config_sha256({**changed,key:value}),old)
        changed["sessions"]["overnight_holds"]=True
        self.assertNotEqual(runner.frozen_trading_config_sha256(changed),old)

    def test_each_shipped_scalar_leaf_is_frozen_except_the_three_session_flags(self):
        path=SOURCE/"config-leverage-1x.json"
        raw=json.loads(path.read_bytes())
        legacy={"config_sha256":hashlib.sha256(path.read_bytes()).hexdigest()}
        stored={**legacy,"frozen_trading_config_sha256":ONE_X_FROZEN_SHA256}
        session_paths={("regular_session_only",),("extended_hours_enabled",),("sessions","extended_hours")}
        def leaves(value,path=()):
            if isinstance(value,dict):
                for key,item in value.items():
                    yield from leaves(item,path+(key,))
            elif isinstance(value,list):
                for index,item in enumerate(value):
                    yield from leaves(item,path+(index,))
            else:
                yield path,value
        for keys,value in leaves(raw):
            changed=deepcopy(raw)
            parent=changed
            for key in keys[:-1]:
                parent=parent[key]
            parent[keys[-1]]=(not value if type(value) is bool else
                             value+1 if isinstance(value,(int,float)) else str(value)+"_changed")
            for metadata in (legacy,stored):
                with self.subTest(path=keys,stored="frozen_trading_config_sha256" in metadata):
                    self.assertEqual(runner.lane_a_config_continues(metadata,changed),keys in session_paths)

    def test_unknown_legacy_config_cannot_infer_or_replace_its_original_envelope(self):
        raw=json.loads((SOURCE/"config-leverage-1x.json").read_text())
        self.assertFalse(runner.lane_a_config_continues({"config_sha256":"f"*64},raw))
        digest=runner.frozen_trading_config_sha256(raw)
        self.assertTrue(runner.lane_a_config_continues(
            {"config_sha256":"f"*64,"frozen_trading_config_sha256":digest},raw))
        self.assertFalse(runner.lane_a_config_continues(
            {"config_sha256":"f"*64,"frozen_trading_config_sha256":"e"*64},raw))
