"""Synthetic extended-hours start readiness; strict wire freshness stays independent."""
from datetime import datetime, timezone
import json
import importlib.util
from pathlib import Path
import sys
import tempfile
import types
import asyncio
import contextlib
import threading
import ast
import unittest
from unittest.mock import Mock, patch

SOURCE=Path(__file__).resolve().parents[1]/'blueprints/us-equities/adaptive-paper'
sys.path.insert(0,str(SOURCE))
import runner
import transport
from tests import test_adaptive_paper_mover as mover_fixtures
from tests import test_adaptive_paper_transport as transport_fixtures

BLOCK={'window_seconds':30,'benchmark_quote_timeout_seconds':5}


class StartReadiness(unittest.TestCase):
    def budget_probe(self, root, *, readiness=True, refresh_case=None):
        """Astra's budget probe: real HTTP guard, preflight and durable Ledger."""
        clock=[0.0];epoch=transport.timestamp_ns('2026-10-14T08:00:00Z')
        attempts=[];wire=[];quote_reads=[0];snapshots={'account':0,'positions':0,'orders':0}
        def client(*args,**kwargs):
            auth=args[2];c=Mock()
            def get(path,value,data=False):
                def call(*a,**k):
                    guard=object.__new__(transport.GuardedSession)
                    guard.origin=transport.DATA_URL if data else transport.PAPER_URL
                    guard.before_request=auth;guard.lock=threading.Lock();guard.observer=None
                    guard.read_only=True;guard._session=Mock()
                    def sent(*a,**k):wire.append(path);return types.SimpleNamespace(status_code=200)
                    guard._session.request.side_effect=sent
                    guard.request('GET',guard.origin+path)
                    return value() if callable(value) else value
                return call
            def account():
                snapshots['account']+=1
                return {'id':'changed-fixture' if refresh_case=='identity' and snapshots['account']>1 else 'fixture-account-id',
                        'cash':'10000','equity':'20000','buying_power':'20000'}
            c.get_account.side_effect=get('/v2/account',account)
            c.get_clock.side_effect=get('/v2/clock',{'is_open':False,'timestamp':'2026-10-14T08:00:00Z',
                'next_close':'2026-10-14T20:00:00Z','next_open':'2026-10-14T13:30:00Z'})
            def collection(kind):
                snapshots[kind]+=1
                if snapshots[kind]>1 and refresh_case and refresh_case.startswith(kind):
                    return None if refresh_case.endswith('null') else {}
                return []
            c.get_all_positions.side_effect=get('/v2/positions',lambda:collection('positions'))
            c.get.side_effect=get('/v2/orders',lambda:collection('orders'))
            c.get_asset.side_effect=get('/v2/assets/SPY',{'symbol':'SPY','status':'active','tradable':True,'attributes':[]})
            def quotes():
                quote_reads[0]+=1;age=8 if quote_reads[0]==1 else 1
                return {'SPY':{'bp':100,'ap':100.01,'bs':1,'as':1,
                    't':datetime.fromtimestamp(epoch/1e9+clock[0]-age,timezone.utc)}}
            c.get_stock_latest_quote.side_effect=get('/v2/stocks/quotes/latest',quotes,True)
            return c
        _,limits,_=runner.load_config(SOURCE/'config.json')
        # At the fail-before head, execute the actual nested observer/replay
        # statements, as the review probe did, rather than substitute a policy.
        main=next(n for n in ast.parse((SOURCE/'runner.py').read_text()).body
                  if isinstance(n,ast.FunctionDef) and n.name=='main')
        prior_observer=next(n for n in ast.walk(main) if isinstance(n,ast.FunctionDef) and n.name=='observe_request') if not hasattr(runner,'preflight_request_observer') else None
        prior_replay=next(n for n in ast.walk(main) if isinstance(n,ast.For) and isinstance(n.iter,ast.Name)
                          and n.iter.id=='attempts') if not hasattr(runner,'replay_preflight_requests') else None
        def advance(seconds):clock[0]+=seconds
        with self.sdk_imports(),patch.object(transport,'_sdk_client',side_effect=client), \
             patch.object(transport.time,'monotonic',side_effect=lambda:clock[0]), \
             patch.object(transport.time,'time',side_effect=lambda:epoch/1e9+clock[0]), \
             patch.object(transport.time,'time_ns',side_effect=lambda:epoch+int(clock[0]*1e9)), \
             patch.object(transport.time,'sleep',side_effect=advance):
            window=(runner.readiness_request_window(root,limits,enabled=readiness)
                    if hasattr(runner,'readiness_request_window') else contextlib.nullcontext(None))
            with window as budget:
                if prior_observer is not None:
                    ns={'attempts':attempts,'time':transport.time,'SafetyError':runner.SafetyError}
                    exec(compile(ast.fix_missing_locations(ast.Module(body=[prior_observer],type_ignores=[])),
                                 'review-observer','exec'),ns)
                    observe=ns['observe_request']
                else:observe=runner.preflight_request_observer(attempts,budget)
                try:
                    result=transport.preflight('fixture-key','fixture-secret',['SPY'],before_request=observe,
                        **({'start_readiness':BLOCK,'benchmark_symbols':['SPY']} if readiness else {}))
                except transport.TransportError:
                    if refresh_case is None:self.assertEqual(wire,[])
                    raise
        with contextlib.closing(runner.Ledger(root/'trading.sqlite3',limits)) as ledger:
            if prior_replay is not None:
                exec(compile(ast.fix_missing_locations(ast.Module(body=[prior_replay],type_ignores=[])),
                             'review-replay','exec'),{'ledger':ledger,'attempts':attempts,'SafetyError':runner.SafetyError})
            else:runner.replay_preflight_requests(ledger,attempts,readiness=readiness,
                    readiness_path=root/'readiness-requests.sqlite3' if readiness else None,now=epoch/1e9+clock[0])
            rows=dict(ledger.db.execute('SELECT kind,COUNT(*) FROM requests GROUP BY kind'))
        return attempts,wire,result,rows

    def test_readiness_twelve_gets_persist_in_both_windows(self):
        with tempfile.TemporaryDirectory(dir='/var/tmp') as directory:
            root=Path(directory)
            attempts,wire,result,rows=self.budget_probe(root)
            self.assertEqual((len(attempts),len(wire),result['start_readiness']['quote_reads']),(12,12,3))
            self.assertEqual(rows,{'read':9,'data_read':3})
            with contextlib.closing(runner.Ledger(root/'readiness-requests.sqlite3')) as budget:
                self.assertEqual(dict(budget.db.execute('SELECT kind,COUNT(*) FROM requests GROUP BY kind')),rows)

    def test_exhausted_readiness_window_refuses_before_get_and_survives_retry(self):
        with tempfile.TemporaryDirectory(dir='/var/tmp') as directory:
            root=Path(directory);epoch=transport.timestamp_ns('2026-10-14T08:00:00Z')/1e9
            with contextlib.closing(runner.Ledger(root/'readiness-requests.sqlite3')) as budget:
                for _ in range(200):self.assertEqual(budget.request_budget(epoch,'data_read'),0)
            for _ in range(2):
                with self.assertRaisesRegex(transport.TransportError,'readiness_request_budget_exhausted'):
                    self.budget_probe(root)
                with contextlib.closing(runner.Ledger(root/'readiness-requests.sqlite3')) as budget:
                    self.assertEqual(budget.db.execute('SELECT COUNT(*) FROM requests').fetchone()[0],200)

    def test_default_data_requests_keep_existing_policy(self):
        with tempfile.TemporaryDirectory(dir='/var/tmp') as directory:
            root=Path(directory);attempts,wire,result,rows=self.budget_probe(root,readiness=False)
            self.assertEqual((len(attempts),len(wire)),(6,6))
            self.assertEqual(rows,{'read':5})
            self.assertFalse((root/'readiness-requests.sqlite3').exists())

    def test_changed_identity_and_malformed_final_snapshot_refuse(self):
        for case in ('identity','positions-object','positions-null','orders-object','orders-null'):
            with self.subTest(case=case),tempfile.TemporaryDirectory(dir='/var/tmp') as directory:
                with self.assertRaisesRegex(transport.TransportError,
                        'preflight_account_changed' if case=='identity' else 'incomplete_readiness_snapshot'):
                    self.budget_probe(Path(directory),refresh_case=case)

    def test_main_opted_budget_refuses_before_http_and_retains_retry_window(self):
        from sessions import SessionKind
        with tempfile.TemporaryDirectory(dir='/var/tmp') as directory:
            root=Path(directory);state=root/'state';p=root/'config.json';p.write_text(json.dumps(self.config()))
            _,limits,_=runner.load_config(p);now=transport.timestamp_ns('2026-10-14T08:00:00Z')/1e9
            with contextlib.closing(runner.Ledger(state/'readiness-requests.sqlite3',limits)) as ledger:
                for _ in range(200):ledger.request_budget(now,'read')
            wire=Mock(side_effect=AssertionError('GET reached with exhausted durable readiness window'))
            def get(*args,**kwargs):
                guard=object.__new__(transport.GuardedSession)
                guard.origin=transport.PAPER_URL;guard.read_only=True;guard.before_request=kwargs['before_request']
                guard.lock=threading.Lock();guard.observer=None;guard._session=Mock();guard._session.request=wire
                guard.request('GET',transport.PAPER_URL+'/v2/account')
            argv=['runner.py','paper','--credentials','keychain-env','--config',str(p),
                  '--state-root',str(state),'--output',str(root/'receipt.json'),'--trial','fixture']
            for _ in range(2):
                with patch.object(sys,'argv',argv),patch.object(runner,'paper_credentials',return_value=('fixture-key','fixture-secret')), \
                     patch.object(runner,'check_order_contract_boundary',return_value={}), \
                     patch.object(runner,'session_at',return_value=types.SimpleNamespace(kind=SessionKind.PRE)), \
                     patch.object(runner.time,'time',return_value=now),patch.object(runner,'preflight',side_effect=get):
                    self.assertEqual(runner.main(),2)
                self.assertEqual(json.loads((root/'receipt.json').read_text())['reason'],'readiness_request_budget_exhausted')
                wire.assert_not_called()
                with contextlib.closing(runner.Ledger(state/'readiness-requests.sqlite3',limits)) as ledger:
                    self.assertEqual(ledger.db.execute('SELECT COUNT(*) FROM requests').fetchone()[0],200)

    def sdk_imports(self):
        enums=types.ModuleType('alpaca.data.enums');enums.DataFeed=lambda value:value
        requests=types.ModuleType('alpaca.data.requests')
        requests.StockLatestQuoteRequest=lambda **kwargs:types.SimpleNamespace(**kwargs)
        return patch.dict(sys.modules,{'alpaca':types.ModuleType('alpaca'),
            'alpaca.data':types.ModuleType('alpaca.data'),'alpaca.data.enums':enums,
            'alpaca.data.requests':requests})

    def port(self,**changes):
        enums=types.ModuleType('alpaca.data.enums');enums.DataFeed=lambda value:value
        stubs={'alpaca':types.ModuleType('alpaca'),'alpaca.data':types.ModuleType('alpaca.data'),
               'alpaca.data.enums':enums}
        with patch.dict(sys.modules,stubs),patch.object(transport,'_sdk_client',return_value=Mock()), \
             patch.object(transport,'_protocol_factory',return_value=None), \
             patch.object(transport,'_stream_classes',return_value=(Mock,Mock)):
            return transport.AlpacaPaperTransport('fixture-key','fixture-secret',['SPY','AAPL'],
                before_request=lambda *a,**k:None,before_submit=lambda *a:None,
                sink_observation=lambda *a:None,required_quote_symbols=['SPY'],
                quote_timeout=3,order_quote_max_age_seconds=3,**changes)

    def config(self,block=BLOCK):
        c=json.loads((SOURCE/'config.json').read_text())
        c.update(regular_session_only=False,extended_hours_enabled=True,benchmarks=['SPY','QQQ'])
        c['sessions']['extended_hours']=True
        c['extended_hours_start_readiness']=block
        return c

    def load(self,raw):
        with tempfile.TemporaryDirectory(dir='/var/tmp') as root:
            p=Path(root)/'config.json';p.write_text(json.dumps(raw));return runner.load_config(p)

    def test_unsupported_readiness_values_refuse_at_load(self):
        for block in (None,[],{}, {'window_seconds':30},dict(BLOCK,extra=1),
                      dict(BLOCK,window_seconds=True),dict(BLOCK,window_seconds=31),
                      dict(BLOCK,benchmark_quote_timeout_seconds=6),
                      dict(BLOCK,benchmark_quote_timeout_seconds=5.0)):
            with self.subTest(block=block),self.assertRaisesRegex(ValueError,'invalid_extended_hours_start_readiness'):
                self.load(self.config(block))

    def test_config_is_extended_hours_only_and_default_configs_unchanged(self):
        c=self.config();c['regular_session_only']=True;c['extended_hours_enabled']=False;c['sessions']['extended_hours']=False
        with self.assertRaisesRegex(ValueError,'extended_hours_start_readiness_requires_extended_hours'):
            self.load(c)
        _,default,_=runner.load_config(SOURCE/'config.json')
        self.assertEqual(default.quote_max_age_seconds,3)
        self.assertEqual(runner.start_readiness_settings(self.config(),'preflight','PRE'),{})
        self.assertEqual(runner.start_readiness_settings(self.config(),'recover','PRE'),{})
        self.assertEqual(runner.start_readiness_settings(self.config(),'paper','RTH'),{})
        self.assertEqual(runner.start_readiness_settings(self.config(),'paper','PRE'),BLOCK)

    def test_main_forwards_readiness_only_for_actual_extended_paper(self):
        from types import SimpleNamespace
        from sessions import SessionKind
        for command,kind in (('paper',SessionKind.PRE),('paper',SessionKind.POST),
                             ('paper',SessionKind.RTH),('paper',SessionKind.OVERNIGHT),
                             ('preflight',SessionKind.PRE),('recover',SessionKind.PRE)):
            with self.subTest(command=command,kind=kind),tempfile.TemporaryDirectory(dir='/var/tmp') as directory:
                root=Path(directory);p=root/'config.json';p.write_text(json.dumps(self.config()))
                argv=['runner.py',command,'--credentials','keychain-env','--config',str(p),
                      '--state-root',str(root/'state'),'--output',str(root/'receipt.json'),'--trial','fixture']
                network=Mock(side_effect=runner.TransportError('fixture_no_network'))
                with patch.object(sys,'argv',argv),patch.object(runner,'paper_credentials',return_value=('fixture-key','fixture-secret')), \
                     patch.object(runner,'check_order_contract_boundary',return_value={}), \
                     patch.object(runner,'preflight',network), \
                     patch.object(runner,'session_at',return_value=SimpleNamespace(kind=kind)):
                    self.assertEqual(runner.main(),2)
                expected=command=='paper' and kind in (SessionKind.PRE,SessionKind.POST)
                self.assertEqual('start_readiness' in network.call_args.kwargs,expected)
                if expected:
                    self.assertEqual(network.call_args.kwargs['start_readiness'],BLOCK)
                    self.assertEqual(network.call_args.kwargs['benchmark_symbols'],['SPY','QQQ'])
                self.assertFalse((root/'state').exists())

    def test_preflight_benchmark_age_405_qualifies_only_for_extended_paper(self):
        c,_,_=self.load(self.config())
        fixture=mover_fixtures.MoverCommandSessionWiring();obs=fixture.observation(c['symbols'])
        now=fixture.SERVER
        for q in obs['quotes']:q['ts_ns']=int((now-4.05)*1e9)
        with patch.object(runner.time,'time',return_value=now):
            with self.assertRaisesRegex(runner.SafetyError,'benchmark_quotes_not_ready'):
                runner.validate_preflight(obs,c,require_open=True,session_policy=runner.validate_session_policy(c))
            runner.validate_preflight(obs,c,require_open=True,session_policy=runner.validate_session_policy(c),
                                      benchmark_quote_timeout_seconds=5)

    def test_unregistered_benchmark_age_override_refuses(self):
        c,_,_=self.load(self.config());fixture=mover_fixtures.MoverCommandSessionWiring()
        obs=fixture.observation(c['symbols']);now=fixture.SERVER
        for quote in obs['quotes']:quote['ts_ns']=int(now*1e9)
        with patch.object(runner.time,'time',return_value=now),self.assertRaisesRegex(runner.SafetyError,'invalid_start_readiness_scope'):
            runner.validate_preflight(obs,c,require_open=True,session_policy=runner.validate_session_policy(c),
                                      benchmark_quote_timeout_seconds=6)

    def test_stream_benchmark_timeout_never_widens_order_wire_guard(self):
        port=self.port(extended_hours_allowed=True,start_timeout=30,benchmark_quote_timeout_seconds=5)
        port._started=True
        port._auth={k:True for k in ('orders','quotes')};port._acks=dict(port._auth)
        port._quote_seen={s:95.95 for s in port.required_quote_symbols}
        port._quote_values={s:{'ts_ns':95_950_000_000} for s in port.required_quote_symbols}
        with patch.object(transport.time,'monotonic',return_value=100),patch.object(transport.time,'time_ns',return_value=100_000_000_000):
            self.assertTrue(port.health['fresh_quotes'])
            for side in ('buy','sell'):
                with self.subTest(side=side),self.assertRaises(transport.SubmissionNotSent):
                    port._wire_guard({'symbol':port.required_quote_symbols[0],'side':side})
            self.assertEqual((port.start_timeout,port.quote_timeout,port.order_quote_max_age_ns),(30,3,3_000_000_000))
            port._quote_values['SPY']['ts_ns']=94_000_000_000
            self.assertFalse(port.health['fresh_quotes'])

    def test_constructor_default_and_unsupported_stream_scope(self):
        p=self.port(extended_hours_allowed=False)
        self.assertEqual((p.start_timeout,p.quote_timeout,p.benchmark_quote_timeout_seconds),(15,3,None))
        for changes in ({'extended_hours_allowed':False,'start_timeout':30,'benchmark_quote_timeout_seconds':5},
                        {'extended_hours_allowed':True,'start_timeout':15,'benchmark_quote_timeout_seconds':5},
                        {'extended_hours_allowed':True,'start_timeout':30,'benchmark_quote_timeout_seconds':6}):
            with self.subTest(changes=changes),self.assertRaisesRegex(transport.TransportError,'invalid_extended_hours_start_readiness'):
                self.port(**changes)

    @unittest.skipUnless(importlib.util.find_spec('nautilus_trader'),'requires pinned native config model')
    def test_native_connection_window_outlives_stream_start_and_default_stays_10(self):
        import native_adapter
        for timeout,port,session in ((10,self.port(),{}),(40,self.port(extended_hours_allowed=True,
                start_timeout=30,benchmark_quote_timeout_seconds=5),{'extended_hours':True})):
            with self.subTest(timeout=timeout),patch.object(native_adapter.LiveNode,'build',return_value=Mock()) as build:
                native_adapter.build_node(port,[{'symbol':'SPY'}],[],session_policy=session,
                                          connection_timeout_seconds=timeout)
                self.assertEqual(build.call_args.args[1].timeout_connection_secs,timeout)
        with self.assertRaisesRegex(ValueError,'invalid_native_start_readiness_window'):
            native_adapter.build_node(self.port(),[{'symbol':'SPY'}],[],connection_timeout_seconds=40)

    def test_only_required_benchmark_quotes_use_the_readiness_age(self):
        port=self.port(extended_hours_allowed=True,start_timeout=30,benchmark_quote_timeout_seconds=5)
        seen=[];port._on_quote=seen.append
        async def exercise():
            task=asyncio.create_task(port._consume_events())
            try:
                for symbol in ['SPY','AAPL']:
                    raw={'S':symbol,'bp':100,'ap':100.01,'bs':1,'as':1,
                         't':datetime.fromtimestamp(95.95,timezone.utc)}
                    await port._quote_callback(raw)
                await asyncio.sleep(.03)
            finally:
                port._stopping=True;task.cancel();await asyncio.gather(task,return_exceptions=True)
        with patch.object(transport.time,'time_ns',return_value=100_000_000_000):
            asyncio.run(exercise())
        self.assertEqual([q['symbol'] for q in seen],['SPY'])
        self.assertEqual(port.order_quote_max_age_ns,3_000_000_000)

    @unittest.skipUnless(importlib.util.find_spec('alpaca'),'requires reviewed SDK; HTTP mocked')
    def test_real_sdk_readiness_wait_refreshes_account_proof_and_bounds_requests(self):
        clock=[0.0];reads={'account':0,'quote':0};calls=[]
        epoch=transport.timestamp_ns('2026-10-13T08:00:00Z')
        def advance(seconds):clock[0]+=seconds
        def http(method,url,**kwargs):
            self.assertEqual(method,'GET');path=transport.urlsplit(url).path;calls.append(path)
            if path=='/v2/account':
                reads['account']+=1
                payload={'id':'fixture-account-id','cash':'10000' if reads['account']==1 else '9999',
                         'equity':'20000','buying_power':'20000'}
            elif path=='/v2/clock':payload={'is_open':False,'timestamp':'2026-10-13T08:00:00Z',
                    'next_close':'2026-10-13T20:00:00Z','next_open':'2026-10-13T13:30:00Z'}
            elif path in ('/v2/positions','/v2/orders'):payload=[]
            elif path=='/v2/assets/SPY':payload={'symbol':'SPY','status':'active','tradable':True,'attributes':[]}
            elif path=='/v2/stocks/quotes/latest':
                reads['quote']+=1
                age=8 if reads['quote']==1 else 4.05
                stamp=datetime.fromtimestamp((epoch/1e9)+clock[0]-age,timezone.utc).isoformat()
                payload={'quotes':{'SPY':{'bp':100,'ap':100.01,'bs':1,'as':1,'t':stamp}}}
            else:raise AssertionError('unexpected read endpoint')
            return transport_fixtures.response(payload)
        with tempfile.TemporaryDirectory(dir='/var/tmp') as directory, \
             patch('requests.Session.request',side_effect=http), \
             patch.object(transport.time,'monotonic',side_effect=lambda:clock[0]), \
             patch.object(transport.time,'time',side_effect=lambda:epoch/1e9+clock[0]), \
             patch.object(transport.time,'time_ns',side_effect=lambda:epoch+int(clock[0]*1e9)), \
             patch.object(transport.time,'sleep',side_effect=advance):
            root=Path(directory);_,limits,_=runner.load_config(SOURCE/'config.json');attempts=[]
            with runner.readiness_request_window(root,limits,enabled=True) as reserve:
                budget=Mock(wraps=runner.preflight_request_observer(attempts,reserve))
                result=transport.preflight('fixture-key','fixture-secret',['SPY'],before_request=budget,
                                          start_readiness=BLOCK,benchmark_symbols=['SPY'])
            for name in ('readiness-requests.sqlite3','trading.sqlite3'):
                with contextlib.closing(runner.Ledger(root/name,limits)) as ledger:
                    if name=='trading.sqlite3':runner.replay_preflight_requests(ledger,attempts,readiness=True,
                        readiness_path=root/'readiness-requests.sqlite3',now=epoch/1e9+clock[0])
                    self.assertEqual(dict(ledger.db.execute('SELECT kind,COUNT(*) FROM requests GROUP BY kind')),
                                     {'read':9,'data_read':3})
        self.assertEqual(reads,{'account':2,'quote':3})
        self.assertEqual(result['account']['cash'],'9999')
        self.assertEqual(result['start_readiness'],dict(BLOCK,quote_reads=3,account_state_refreshed=True))
        self.assertEqual(budget.call_count,len(calls))
        self.assertEqual(clock[0],2)
        self.assertLessEqual(len(calls),50)
        self.assertNotIn('fixture-account-id',json.dumps(result))

    def test_readiness_deadline_and_stop_refuse_before_account_admission(self):
        from types import SimpleNamespace
        # Official client helper boundary is stubbed here; the previous test
        # verifies real SDK request authorization and response parsing.
        def client(*args,**kwargs):
            c=Mock()
            c.get_account.return_value={'id':'fixture-account-id','cash':'10000','equity':'20000','buying_power':'20000'}
            c.get_clock.return_value={'is_open':False,'timestamp':'2026-10-13T08:00:00Z',
                                     'next_close':'2026-10-13T20:00:00Z','next_open':'2026-10-13T13:30:00Z'}
            c.get_all_positions.return_value=[];c.get.return_value=[]
            c.get_asset.return_value={'symbol':'SPY','status':'active','tradable':True,'attributes':[]}
            c.get_stock_latest_quote.return_value={}
            return c
        for stopped in (False,True):
            clock=[0.0]
            def advance(seconds):clock[0]+=seconds
            with self.subTest(stopped=stopped),self.sdk_imports(),patch.object(transport,'_sdk_client',side_effect=client), \
                 patch.object(transport.time,'monotonic',side_effect=lambda:clock[0]), \
                 patch.object(transport.time,'sleep',side_effect=advance):
                with self.assertRaisesRegex(transport.TransportError,'start_readiness_stopped' if stopped else 'benchmark_quotes_not_ready'):
                    transport.preflight('fixture-key','fixture-secret',['SPY'],before_request=lambda *a,**k:None,
                        start_readiness=BLOCK,benchmark_symbols=['SPY'],stop_requested=lambda:stopped)
            self.assertLessEqual(clock[0],30)

    def test_pre_stage_cannot_cross_regular_open(self):
        c,_,_=self.load(self.config())
        fixture=mover_fixtures.MoverCommandSessionWiring();obs=fixture.observation(c['symbols'])
        now=datetime(2026,10,14,13,29,tzinfo=timezone.utc).timestamp()
        obs['clock'].update(timestamp_ns=int(now*1e9),received_at_ns=int(now*1e9))
        for q in obs['quotes']:q['ts_ns']=int(now*1e9)
        with patch.object(runner.time,'time',return_value=now),self.assertRaisesRegex(
                runner.SafetyError,'start_readiness_pre_crosses_rth'):
            runner.validate_preflight(obs,c,require_open=True,session_policy=runner.validate_session_policy(c),
                                      benchmark_quote_timeout_seconds=5)

    def test_stage_watchdog_freezes_after_five_seconds(self):
        port=self.port(extended_hours_allowed=True,start_timeout=30,benchmark_quote_timeout_seconds=5)
        port._ever_ready=True
        port._quote_seen={'SPY':100.0};port._quote_values={'SPY':{'ts_ns':100_000_000_000}}
        port._started=True;port._auth={'orders':True,'quotes':True};port._acks=dict(port._auth)
        async def exercise():
            for now,stale in ((104.99,False),(105.01,True)):
                async def one_iteration(delay):port._stopping=True
                port._stopping=False
                with patch.object(transport.time,'monotonic',return_value=now), \
                     patch.object(transport.time,'time_ns',return_value=int(now*1e9)), \
                     patch.object(transport.asyncio,'sleep',side_effect=one_iteration):
                    await port._watchdog()
                self.assertEqual('quote_stale' in port.health['reasons'],stale)
        asyncio.run(exercise())

    def test_request_bound_writes_not_started_without_state(self):
        from sessions import SessionKind
        with tempfile.TemporaryDirectory(dir='/var/tmp') as directory:
            root=Path(directory);p=root/'config.json';p.write_text(json.dumps(self.config()))
            argv=['runner.py','paper','--credentials','keychain-env','--config',str(p),
                  '--state-root',str(root/'state'),'--output',str(root/'receipt.json'),'--trial','fixture']
            def bounded(*args,**kwargs):
                for _ in range(51):kwargs['before_request']('read')
            with patch.object(sys,'argv',argv),patch.object(runner,'paper_credentials',return_value=('fixture-key','fixture-secret')), \
                 patch.object(runner,'check_order_contract_boundary',return_value={}), \
                 patch.object(runner,'session_at',return_value=types.SimpleNamespace(kind=SessionKind.RTH)), \
                 patch.object(runner,'preflight',side_effect=bounded):
                self.assertEqual(runner.main(),2)
            receipt=json.loads((root/'receipt.json').read_text())
            self.assertEqual((receipt['status'],receipt['reason'],receipt['orders_submitted']),
                             ('not_started','preflight_request_bound',0))
            self.assertFalse((root/'state').exists())

    def _extended_request_bound(self, kind):
        with tempfile.TemporaryDirectory(dir='/var/tmp') as directory:
            root=Path(directory);p=root/'config.json';p.write_text(json.dumps(self.config()))
            _,limits,_=runner.load_config(p)
            argv=['runner.py','paper','--credentials','keychain-env','--config',str(p),
                  '--state-root',str(root/'state'),'--output',str(root/'receipt.json'),'--trial','fixture']
            def bounded(*args,**kwargs):
                for _ in range(51):kwargs['before_request']('data_read')
            with patch.object(sys,'argv',argv),patch.object(runner,'paper_credentials',return_value=('fixture-key','fixture-secret')), \
                 patch.object(runner,'check_order_contract_boundary',return_value={}), \
                 patch.object(runner,'session_at',return_value=types.SimpleNamespace(kind=kind)), \
                 patch.object(runner,'preflight',side_effect=bounded):
                self.assertEqual(runner.main(),2)
            receipt=json.loads((root/'receipt.json').read_text())
            self.assertEqual((receipt['status'],receipt['reason']),('not_started','preflight_request_bound'))
            with contextlib.closing(runner.Ledger(root/'state'/'readiness-requests.sqlite3',limits)) as ledger:
                self.assertEqual(dict(ledger.db.execute('SELECT kind,COUNT(*) FROM requests GROUP BY kind')),{'data_read':50})
            self.assertEqual(list((root/'state').glob('*/adaptive/ledger.sqlite3')),[])

    def test_request_bound_pre_retains_durable_readiness_journal(self):
        from sessions import SessionKind
        self._extended_request_bound(SessionKind.PRE)

    def test_request_bound_post_retains_durable_readiness_journal(self):
        from sessions import SessionKind
        self._extended_request_bound(SessionKind.POST)

    def test_thirty_symbol_poll_reserves_final_snapshot_requests(self):
        clock=[0.0];calls=[];snapshots={'account':0,'clock':0,'positions':0,'orders':0}
        epoch=transport.timestamp_ns('2026-10-14T08:00:00Z')
        symbols=['SPY']+['A'+chr(65+i//26)+chr(65+i%26) for i in range(29)]
        def client(*args,**kwargs):
            authorize=args[2];c=Mock()
            def read(value,kind=None):
                def call(*a,**k):
                    authorize('read');calls.append(clock[0])
                    if kind:snapshots[kind]+=1
                    return value() if callable(value) else value
                return call
            c.get_account.side_effect=read(lambda:{'id':'fixture-account-id',
                'cash':'10000' if snapshots['account']==1 else '9999','equity':'20000','buying_power':'20000'},'account')
            c.get_clock.side_effect=read({'is_open':False,'timestamp':'2026-10-14T08:00:00Z',
                'next_close':'2026-10-14T20:00:00Z','next_open':'2026-10-14T13:30:00Z'},'clock')
            c.get_all_positions.side_effect=read([],'positions');c.get.side_effect=read([],'orders')
            c.get_asset.side_effect=read({'symbol':'SPY','status':'active','tradable':True,'attributes':[]})
            def quotes():
                age=1 if clock[0]>=22 else 8
                return {'SPY':{'bp':100,'ap':100.01,'bs':1,'as':1,
                    't':datetime.fromtimestamp(epoch/1e9+clock[0]-age,timezone.utc)}}
            c.get_stock_latest_quote.side_effect=read(quotes)
            return c
        def budget(*a,**k):
            if len(calls)>=50:raise runner.SafetyError('preflight_request_bound')
        def advance(seconds):clock[0]+=seconds
        with self.sdk_imports(),patch.object(transport,'_sdk_client',side_effect=client), \
             patch.object(transport.time,'monotonic',side_effect=lambda:clock[0]), \
             patch.object(transport.time,'time_ns',side_effect=lambda:epoch+int(clock[0]*1e9)), \
             patch.object(transport.time,'sleep',side_effect=advance):
            result=transport.preflight('fixture-key','fixture-secret',symbols,before_request=budget,
                                      start_readiness=BLOCK,benchmark_symbols=['SPY'])
        self.assertTrue(result['start_readiness']['account_state_refreshed'])
        self.assertEqual(result['account']['cash'],'9999')
        self.assertEqual(snapshots,{'account':2,'clock':2,'positions':2,'orders':2})
        self.assertLessEqual(len(calls),50)
        self.assertGreaterEqual(clock[0],22);self.assertLess(clock[0],30)


if __name__=='__main__':unittest.main()
