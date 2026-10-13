"""Synthetic extended-hours start readiness; strict wire freshness stays independent."""
from datetime import datetime, timezone
import json
import importlib.util
from pathlib import Path
import sys
import tempfile
import types
import asyncio
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
                             ('paper',SessionKind.RTH),('preflight',SessionKind.PRE),('recover',SessionKind.PRE)):
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

    def test_stream_benchmark_timeout_never_widens_order_wire_guard(self):
        port=self.port(extended_hours_allowed=True,start_timeout=30,benchmark_quote_timeout_seconds=5)
        port._started=True
        port._auth={k:True for k in ('orders','quotes')};port._acks=dict(port._auth)
        port._quote_seen={s:transport.time.monotonic()-4.05 for s in port.required_quote_symbols}
        port._quote_values={s:{'ts_ns':transport.time.time_ns()-4_050_000_000} for s in port.required_quote_symbols}
        self.assertTrue(port.health['fresh_quotes'])
        for side in ('buy','sell'):
            with self.subTest(side=side),self.assertRaises(transport.SubmissionNotSent):
                port._wire_guard({'symbol':port.required_quote_symbols[0],'side':side})
        self.assertEqual((port.start_timeout,port.quote_timeout,port.order_quote_max_age_ns),(30,3,3_000_000_000))
        port._quote_values['SPY']['ts_ns']=transport.time.time_ns()-6_000_000_000
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
                         't':datetime.fromtimestamp(transport.time.time()-4.05,timezone.utc)}
                    await port._quote_callback(raw)
                await asyncio.sleep(.03)
            finally:
                port._stopping=True;task.cancel();await asyncio.gather(task,return_exceptions=True)
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
        budget=Mock()
        with patch('requests.Session.request',side_effect=http), \
             patch.object(transport.time,'monotonic',side_effect=lambda:clock[0]), \
             patch.object(transport.time,'time_ns',side_effect=lambda:epoch+int(clock[0]*1e9)), \
             patch.object(transport.time,'sleep',side_effect=advance):
            result=transport.preflight('fixture-key','fixture-secret',['SPY'],before_request=budget,
                                      start_readiness=BLOCK,benchmark_symbols=['SPY'])
        self.assertEqual(reads,{'account':2,'quote':3})
        self.assertEqual(result['account']['cash'],'9999')
        self.assertEqual(result['start_readiness'],dict(BLOCK,quote_reads=3,account_state_refreshed=True))
        self.assertEqual(budget.call_count,len(calls))
        self.assertEqual(clock[0],2)
        self.assertLessEqual(len(calls),50)
        self.assertNotIn('fixture-account-id',json.dumps(result))

    @unittest.skipUnless(importlib.util.find_spec('alpaca'),'requires reviewed SDK; HTTP mocked')
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
            with self.subTest(stopped=stopped),patch.object(transport,'_sdk_client',side_effect=client), \
                 patch.object(transport.time,'monotonic',side_effect=lambda:clock[0]), \
                 patch.object(transport.time,'sleep',side_effect=advance):
                with self.assertRaisesRegex(transport.TransportError,'start_readiness_stopped' if stopped else 'benchmark_quotes_not_ready'):
                    transport.preflight('fixture-key','fixture-secret',['SPY'],before_request=lambda *a,**k:None,
                        start_readiness=BLOCK,benchmark_symbols=['SPY'],stop_requested=lambda:stopped)
            self.assertLessEqual(clock[0],30)


if __name__=='__main__':unittest.main()
