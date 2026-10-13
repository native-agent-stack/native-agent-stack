"""Review round two: real trade-update shape, session halts and owner-tick deadlines."""
import asyncio
import io
from dataclasses import replace
from datetime import datetime, time as dtime, timezone
import json
from pathlib import Path
import queue
import sys
import unittest
from unittest.mock import patch

SOURCE=Path(__file__).resolve().parents[1]/'blueprints/us-equities/adaptive-paper'
sys.path.insert(0,str(SOURCE))
try:
    from . import test_adaptive_paper_overnight_arming as fixtures
    from .adaptive_paper_hermetic import patch_default_stop, restore_default_stop
except ImportError:
    import test_adaptive_paper_overnight_arming as fixtures
    from adaptive_paper_hermetic import patch_default_stop, restore_default_stop

def setUpModule():
    global _token
    _token=patch_default_stop()

def tearDownModule():
    restore_default_stop(_token)

class OvernightRoundTwo(unittest.TestCase):
    def test_cancel_budget_expires_without_blocking_tick_and_allows_retry(self):
        import runner
        c,clock,_,bounds,_=fixtures.OvernightArming._controller(self)
        async def exercise():
            started=asyncio.Event()
            release=asyncio.Event()
            finished=asyncio.Event()
            calls=[]
            async def blocked_cancel(cid):
                calls.append(cid)
                started.set()
                try:
                    await release.wait()
                finally:
                    finished.set()
            c.port.cancel=blocked_cancel
            tick=asyncio.create_task(c.overnight_tick(bounds['flatten_at']))
            try:
                await asyncio.wait_for(started.wait(),2)
                self.assertTrue(tick.done(),'cancel budget must run outside the owner tick')
                try:
                    await asyncio.wait_for(finished.wait(),2)
                except TimeoutError:
                    self.fail('tracked cancellation exceeded its fixture budget')
                await asyncio.sleep(0)
                self.assertNotIn('entry',c._overnight_cancel_pending)
                self.assertTrue(any(e['type']=='overnight_cancel_refused' for e in c.events))
                await c.overnight_tick(bounds['flatten_at'])
                await asyncio.sleep(0)
                self.assertEqual(calls,['entry','entry'])
            finally:
                release.set()
                await asyncio.gather(tick,return_exceptions=True)
                if hasattr(c,'stop_overnight_cancels'):
                    await c.stop_overnight_cancels()
        with patch.object(runner,'OVERNIGHT_CANCEL_TIMEOUT_SECONDS',.01,create=True):
            asyncio.run(exercise())

    def test_actual_trade_update_cancel_rejection_retries_live_entry(self):
        from transport import AlpacaPaperTransport
        c,clock,cancels,bounds,_=fixtures.OvernightArming._controller(self)
        clock[0]=bounds['flatten_at']
        async def exercise():
            await c.overnight_tick(clock[0])
            await asyncio.sleep(0)
            self.assertEqual(cancels,['entry'])
            port=AlpacaPaperTransport.__new__(AlpacaPaperTransport)
            port._events=queue.Queue()
            port._stopping=False
            port._stream_seen=set()
            port._pending_stream={}
            port._observed={}
            port._executions={}
            port._observation_lock=asyncio.Lock()
            port.sink_observation=c.observe
            async def delivered(order):
                port._stopping=True
            port._on_order=delivered
            port.freeze_health=lambda reason:self.fail('stream callback failed: '+reason)
            port._events.put(('order',{'stream':'trade_updates','data':{
                'event':'order_cancel_rejected',
                'order':{'id':'synthetic-entry','client_order_id':'entry','symbol':'SPY',
                         'side':'buy','status':'accepted','qty':'1','filled_qty':'0',
                         'limit_price':'10.01','updated_at':datetime.fromtimestamp(clock[0],timezone.utc).isoformat()}}}))
            await port._consume_events()
            self.assertNotIn('entry',c._overnight_cancel_pending,
                             'actual Alpaca cancel rejection must release retry latch')
            await c.overnight_tick(clock[0])
            await asyncio.sleep(0)
            self.assertEqual(cancels,['entry','entry'])
            if hasattr(c,'stop_overnight_cancels'):
                await c.stop_overnight_cancels()
        asyncio.run(exercise())

    def test_cancel_shutdown_joins_waiter_and_suppresses_duplicate_delete(self):
        c,clock,_,bounds,_=fixtures.OvernightArming._controller(self)
        async def exercise():
            started=asyncio.Event()
            release=asyncio.Event()
            stopped=asyncio.Event()
            calls=[]
            async def blocked_cancel(cid):
                calls.append(cid)
                started.set()
                try:
                    await release.wait()
                finally:
                    stopped.set()
            c.port.cancel=blocked_cancel
            tick=asyncio.create_task(c.overnight_tick(bounds['flatten_at']))
            try:
                await asyncio.wait_for(started.wait(),2)
                self.assertTrue(tick.done(),'tick must not wait for the tracked DELETE task')
                await c.overnight_tick(bounds['flatten_at'])
                self.assertEqual(calls,['entry'])
                try:
                    await asyncio.wait_for(c.stop_overnight_cancels(),2)
                except TimeoutError:
                    self.fail('shutdown did not join cancellation within its fixture budget')
                self.assertTrue(stopped.is_set(),'shutdown must cancel and join the in-flight DELETE')
                self.assertNotIn('entry',c._overnight_cancel_pending)
                self.assertEqual(c._overnight_cancel_tasks,{})
            finally:
                release.set()
                await asyncio.gather(tick,return_exceptions=True)
                if hasattr(c,'stop_overnight_cancels'):
                    await c.stop_overnight_cancels()
        asyncio.run(exercise())

    def test_overnight_rule_opt_in_keeps_daytime_default_and_window_bounds(self):
        import mover
        for hhmm in ('20:00','23:59','00:00','03:59'):
            with self.subTest(allowed=hhmm):
                try:
                    parsed=mover.parse_rule(hhmm+'|G20|V1000000|any',overnight=True)
                except (TypeError,ValueError) as exc:
                    self.fail('overnight rule opt-in refused: '+str(exc))
                self.assertEqual(parsed.at_et.strftime('%H:%M'),hhmm)
        for hhmm in ('04:00','19:59'):
            with self.subTest(refused=hhmm),self.assertRaises(ValueError):
                try:
                    mover.parse_rule(hhmm+'|G20|V1000000|any',overnight=True)
                except TypeError as exc:
                    self.fail('overnight rule opt-in unavailable: '+str(exc))
        with self.assertRaises(ValueError):
            mover.parse_rule('20:00|G20|V1000000|any')


    def test_overnight_scan_uses_trade_date_and_cross_midnight_rule_order(self):
        import mover
        try:
            from . import test_adaptive_paper_mover as scans
        except ImportError:
            import test_adaptive_paper_mover as scans
        _,_,original=mover.load_mover_config(scans.CONFIG)
        rule=replace(original.rule,text='20:00|G20|V1000000|any',at_et=dtime(20,0))
        settings=replace(original,rule=rule,session_scope='overnight_only')
        for stamp in ('2026-03-11T00:30:05Z','2026-03-11T05:00:05Z'):
            with self.subTest(scan_time=stamp):
                raw=scans.scan_bytes(rule=rule.text,scan_time=stamp,session_date='2026-03-11')
                now=datetime.fromisoformat(stamp.replace('Z','+00:00')).timestamp()
                try:
                    scan=mover.load_scan(raw,settings,now=now)
                except (ValueError,mover.MoverRefusal) as exc:
                    self.fail('valid overnight scan refused: '+str(exc))
                self.assertEqual(scan.session_date.isoformat(),'2026-03-11')

    def test_daytime_owned_exit_ignores_venue_halt_but_keeps_standing_halt(self):
        c,clock,_,_,_=fixtures.OvernightArming._controller(self,held=True)
        for hour in (8,15,21):
            with self.subTest(utc_hour=hour):
                clock[0]=datetime(2026,3,11,hour,tzinfo=timezone.utc).timestamp()
                c.quote({'symbol':'SPY','bid':'10','ask':'10.01','ts_ns':int(clock[0]*1e9)})
                c.trading_status({'symbol':'SPY','source':'alpaca_assets','ts_ns':int(clock[0]*1e9),
                                  'asset_status':'active','tradable':True,
                                  'overnight_tradable':True,'overnight_halted':True})
                self.assertFalse(c.is_halted('SPY'),'overnight venue halt must not block daytime residual')
                c.port.overnight_check('SPY',clock[0],'sell')
                c.halted_symbols.add('SPY')
                self.assertTrue(c.is_halted('SPY'))
                with self.assertRaisesRegex(RuntimeError,'exit_asset_halted'):
                    c.port.overnight_check('SPY',clock[0],'sell')
                c.halted_symbols.clear()

    def test_owner_tick_reaches_cutoff_and_expiry_while_cancel_waits(self):
        from safety import Quote
        c,clock,_,bounds,_=fixtures.OvernightArming._controller(self)
        now=clock[0]
        c.ledger.reserve_intent('other','QQQ','buy','1','10.01',
            quote=Quote('QQQ','10','10.01',now),now=now,market_open=True,session_close=bounds['boundary_at'])
        c.ledger.record_order('other','synthetic-other','filled','1','10.01',timestamp=now)
        async def exercise():
            started=asyncio.Event()
            release=asyncio.Event()
            async def blocked_cancel(cid):
                started.set()
                await release.wait()
            c.port.cancel=blocked_cancel
            clock[0]=bounds['flatten_at']
            tick=asyncio.create_task(c.overnight_tick(clock[0]))
            try:
                await asyncio.wait_for(started.wait(),2)
                self.assertTrue(tick.done(),'owner tick must return while broker cancellation is still blocked')
                self.assertTrue(tick.result(),'cutoff must force flatten before broker cancel completes')
                clock[0]=bounds['day_expiry']
                self.assertTrue(await c.overnight_tick(clock[0]))
                self.assertEqual(c.ledger.accounting().halted_reason,'overnight_day_expiry')
                self.assertEqual(c.ledger.positions()['QQQ'].qty,1)
            finally:
                release.set()
                await asyncio.gather(tick,return_exceptions=True)
                if hasattr(c,'stop_overnight_cancels'):
                    await c.stop_overnight_cancels()
        asyncio.run(exercise())


ROUND_TWO_MUTANTS=(
 ('actual-cancel-event','runner','Controller.observe','order.get("event") == "order_cancel_rejected"',
  'order.get("event") == "cancel_rejected"','test_actual_trade_update_cancel_rejection_retries_live_entry'),
 ('venue-session','runner','Controller.is_halted',
  'and session_at(datetime.fromtimestamp(self.clock(), timezone.utc)).kind == SessionKind.OVERNIGHT',
  'and True','test_daytime_owned_exit_ignores_venue_halt_but_keeps_standing_halt'),
 ('owner-cancel-task','runner','Controller.overnight_tick',
  'self._overnight_cancel_tasks[cid] = asyncio.create_task(\n                        self._cancel_overnight_entry(cid, reason, now))',
  'await self._cancel_overnight_entry(cid, reason, now)','test_owner_tick_reaches_cutoff_and_expiry_while_cancel_waits'),
 ('cancel-budget','runner','Controller._cancel_overnight_entry',
  'asyncio.timeout(OVERNIGHT_CANCEL_TIMEOUT_SECONDS)','asyncio.timeout(None)',
  'test_cancel_budget_expires_without_blocking_tick_and_allows_retry'),
 ('cancel-shutdown','runner','Controller.stop_overnight_cancels','task.cancel()','None',
  'test_cancel_shutdown_joins_waiter_and_suppresses_duplicate_delete'),
 ('scan-trade-date','mover','load_scan','session_date = info.session_date','session_date = local.date()',
  'test_overnight_scan_uses_trade_date_and_cross_midnight_rule_order'),
 ('scan-rule-order','mover','load_scan',
  'overnight_minute(local.time()) < overnight_minute(settings.rule.at_et)',
  'local.time() < settings.rule.at_et','test_overnight_scan_uses_trade_date_and_cross_midnight_rule_order'),
 ('rule-window','mover','parse_rule','not 0 <= overnight_minute(at) < 480','False',
  'test_overnight_rule_opt_in_keeps_daytime_default_and_window_bounds'),
)

class RoundTwoMutants(unittest.TestCase):
    def test_round_two_guards_fail_by_assertion_when_removed(self):
        import importlib
        try:
            from .test_adaptive_paper_overnight_transition import delete_in_definition
        except ImportError:
            from test_adaptive_paper_overnight_transition import delete_in_definition
        modules={name:importlib.import_module(name) for name in ('runner','mover')}
        original={name:dict(module.__dict__) for name,module in modules.items()}
        sources={name:(SOURCE/(name+'.py')).read_text() for name in modules}
        for name,module,definition,old,new,test in ROUND_TWO_MUTANTS:
            with self.subTest(mutant=name):
                try:
                    changed=delete_in_definition(sources[module],definition,old,new)
                    exec(compile(changed,'<round-two-mutant:'+name+'>','exec'),modules[module].__dict__)
                    suite=unittest.defaultTestLoader.loadTestsFromName('OvernightRoundTwo.'+test,sys.modules[__name__])
                    output=io.StringIO()
                    result=unittest.TextTestRunner(stream=output).run(suite)
                    self.assertGreater(len(result.failures),0,output.getvalue())
                    self.assertEqual(result.errors,[],output.getvalue())
                    print('round_two_mutant',name,'assertion_failures',len(result.failures),'errors',len(result.errors))
                finally:
                    for key,target in modules.items():
                        target.__dict__.clear()
                        target.__dict__.update(original[key])
