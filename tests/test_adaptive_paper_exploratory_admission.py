"""Synthetic SQLite/JSON crash boundary; no broker, credentials or real state."""
from contextlib import ExitStack, nullcontext
from pathlib import Path
from unittest.mock import Mock, patch
from datetime import datetime, timezone
import json
import sys
import tempfile
import unittest

SOURCE=Path(__file__).resolve().parents[1]/'blueprints/us-equities/adaptive-paper'
sys.path.insert(0,str(SOURCE))
import runner
import mover_runner
import exploration
import recovery
import safety
import transport
from tests import test_adaptive_paper_mover as mover_fixture


class AdmissionPublicationCrash(unittest.TestCase):
    def exercise(self, engine, *, final_run_fault=False, final_recovery_fault=False):
        fixture=mover_fixture.MoverCommandSessionWiring();now=fixture.SERVER
        with tempfile.TemporaryDirectory(dir='/var/tmp') as directory:
            root=Path(directory)/'exploratory';root.mkdir()
            state=root/'account-state';sd=state/fixture.FINGERPRINT/'adaptive'
            old=json.loads((SOURCE/'config.json').read_text())
            old.update(paper_lane='B',evidence_class='exploratory')
            new=({**old,'max_order_quantity':2} if engine=='adaptive'
                 else {**json.loads((SOURCE/'config-mover.json').read_text()),
                       'paper_lane':'B','evidence_class':'exploratory'})
            old_path=root/'old.json';new_path=root/'new.json'
            old_path.write_text(json.dumps(old));new_path.write_text(json.dumps(new))
            old_config,old_limits,_=runner.load_config(old_path)
            new_config,new_limits,_=(runner.load_config if engine=='adaptive' else mover_runner.load_mover_config)(new_path)
            old_sha=exploration.config_digest(old_config,old_path.read_bytes(),limits=old_limits)
            new_sha=exploration.config_digest(new_config,new_path.read_bytes(),limits=new_limits)
            ledger=safety.Ledger(sd/'ledger.sqlite3',old_limits,exploratory=True)
            ledger.begin_next_trial(now-10,'first',config_sha256=old_sha,limits=old_limits);ledger.close()
            prior={'trial_id':'first','phase':'finished','config_sha256':old_sha,'started_at':now-10,
                   'fee_window_start':now-10,'baseline_cash':'10000','paper_lane':'B',
                   'evidence_class':'exploratory','engine_kind':'adaptive'}
            (sd/'trial.json').write_text(json.dumps(prior))
            scan=root/'scan.json';scan.write_text(json.dumps(mover_fixture.scan_dict(regime={'factor':'1'})))
            obs=fixture.observation(['ABCD','WXYZ','SPY']);obs['account']['cash']='10000'
            obs['positions']=[];obs['orders']=[]
            save=runner.save
            def interrupted(path,data):
                if Path(path)==sd/'trial.json' and (not final_run_fault or data.get('phase')=='finished'):
                    raise OSError('injected_before_metadata_publish')
                return save(path,data)
            recovered=[]
            async def recover_spy(controller,metadata,config):
                recovered.append((metadata,controller.ledger.limits))
                return {'status':'passed','flat':True,'native_fill_events':0,'evidence_class':'SYN'}
            async def completed(*args,**kwargs):
                return {'status':'completed_no_signals','flat':True,'native_fill_events':0,'legs':[]}
            common=['--state-root',str(state),'--output',str(root/'receipt.json')]
            adaptive=lambda config,command: ['runner.py',command,'--credentials','keychain-env',
                                             '--config',str(config),*common,'--trial','second']
            mover=lambda command: [command,'--env-file',str(root/'unused.env'),'--config',str(new_path),
                                   *common,*(['--scan',str(scan),'--trial','second'] if command=='paper' else [])]
            with ExitStack() as stack:
                patches=[(runner,'DEFAULT_STOP',root/'STOP'),(safety,'DEFAULT_STOP',root/'STOP'),
                         (runner,'check_order_contract_boundary',lambda *_:{}),
                         (runner,'paper_credentials',lambda *_:(None,None)),
                         (runner,'preflight',lambda *_,**__:obs),
                         (transport,'preflight',lambda *_,**__:obs),
                         (runner,'public_preflight',lambda *_:{}),
                         (mover_runner,'public_preflight',lambda *_:{}),
                         (runner,'validate_preflight',lambda *_,**__:now+3600),
                         (mover_runner,'validate_preflight',lambda *_,**__:now+3600),
                         (runner,'account_lock_fingerprint',lambda *_:nullcontext()),
                         (mover_runner,'account_lock_fingerprint',lambda *_:nullcontext()),
                         (runner,'fee_activities',lambda *_,**__:[]),
                         (mover_runner,'credentials',lambda *_:(None,None)),
                         (transport,'fee_checkpoint',lambda *_,**__:{'account':{'cash':'10000'},'fees':[]}),
                         (runner,'AlpacaPaperTransport',Mock()),(transport,'AlpacaPaperTransport',Mock()),
                         (runner.time,'time',lambda:now), (recovery,'recover',recover_spy),
                         (runner,'run_native',completed),(mover_runner,'run_mover',completed),
                         (mover_runner,'recover_mover',recover_spy)]
                for obj,name,value in patches:
                    stack.enter_context(patch.object(obj,name,value))
                stack.enter_context(patch('builtins.print'))
                with patch.object(runner,'save',interrupted),patch.object(mover_runner,'save',interrupted):
                    with self.assertRaisesRegex(OSError,'injected_before_metadata_publish'):
                        if engine=='adaptive':
                            with patch.object(sys,'argv',adaptive(new_path,'paper')):
                                runner.main()
                        else:
                            mover_runner.main(mover('paper'))
                if final_run_fault:
                    active=exploration.active_trial_metadata(sd)
                    self.assertEqual(active['phase'],'finished')
                    self.assertEqual(active['trial_id'],'second')
                    self.assertEqual(json.loads((sd/'trial.json').read_text())['phase'],'starting')
                    return
                self.assertEqual(json.loads((sd/'trial.json').read_text())['trial_id'],'first')
                # The old config must never enter recovery once SQLite committed second.
                with patch.object(sys,'argv',adaptive(old_path,'recover')):
                    with self.assertRaises(safety.SafetyError):
                        runner.main()
                self.assertEqual(recovered,[])
                if final_recovery_fault:
                    def failed_final_projection(path,data):
                        if Path(path)==sd/'trial.json' and data.get('phase')=='finished':
                            raise OSError('injected_final_recovery_publish')
                        return save(path,data)
                    with patch.object(runner,'save',failed_final_projection), \
                         patch.object(mover_runner,'save',failed_final_projection):
                        with self.assertRaisesRegex(OSError,'injected_final_recovery_publish'):
                            if engine=='adaptive':
                                with patch.object(sys,'argv',adaptive(new_path,'recover')):
                                    runner.main()
                            else:
                                mover_runner.main(mover('recover'))
                    active=exploration.active_trial_metadata(sd)
                    self.assertEqual(active['phase'],'finished')
                    self.assertEqual(active['trial_id'],'second')
                    self.assertEqual(json.loads((sd/'trial.json').read_text())['trial_id'],'first')
                    return
                if engine=='adaptive':
                    with patch.object(sys,'argv',adaptive(new_path,'recover')):
                        rc=runner.main()
                else:
                    rc=mover_runner.main(mover('recover'))
                self.assertEqual(rc,0)
                self.assertEqual(len(recovered),1)
                metadata,limits=recovered[0]
                self.assertEqual(metadata['trial_id'],'second')
                self.assertEqual(metadata['config_sha256'],new_sha)
                self.assertEqual(metadata['engine_kind'],engine)
                self.assertEqual(metadata['baseline_cash'],'10000')
                self.assertEqual(metadata['fee_window_start'],now-10)
                self.assertEqual(limits,new_limits)
                projected=json.loads((sd/'trial.json').read_text())
                self.assertEqual(projected['trial_id'],'second')
                self.assertEqual(projected['phase'],'finished')

    def test_adaptive_crash_binds_old_and_new_recovery_to_committed_trial(self):
        self.exercise('adaptive')

    def test_adaptive_to_mover_crash_binds_engine_and_recovery_lineage(self):
        self.exercise('mover')

    def test_empty_preexisting_journal_can_bootstrap_lane_b(self):
        with tempfile.TemporaryDirectory(dir='/var/tmp') as root:
            path=Path(root)/'ledger.sqlite3';path.touch()
            ledger=safety.Ledger(path,exploratory=True)
            ledger.begin_next_trial(1800000000.,'first',config_sha256='a'*64,limits=safety.RiskLimits())
            self.assertEqual(ledger.exploratory_config_history(),['a'*64])
            ledger.close()
