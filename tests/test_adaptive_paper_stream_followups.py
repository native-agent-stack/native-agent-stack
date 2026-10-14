"""F1-F5 seam regressions; synthetic HTTP/ports, real journals, no network."""
import asyncio
import contextlib
import inspect
import io
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
import sys
import tempfile
import threading
import textwrap
import time
import types
import unittest
from unittest.mock import AsyncMock, Mock, patch

SOURCE=Path(__file__).resolve().parents[1]/'blueprints/us-equities/adaptive-paper'
sys.path.insert(0,str(SOURCE))
import runner
import transport
from safety import Ledger, Quote, RiskLimits
from tests.adaptive_paper_hermetic import patch_default_stop, restore_default_stop

try:
    import nautilus_trader
    import alpaca
    import msgpack
    NATIVE = True
except ImportError:
    NATIVE = False

_hermetic=None
def setUpModule():
    global _hermetic
    _hermetic=patch_default_stop()
def tearDownModule():restore_default_stop(_hermetic)


def integrity_handoff_probe():
    """Real run_native loop/GuardedSession/Ledger; synthetic native lifecycle.

    Virtual three-second envelope, one held share before the injected loss.
    The fresh recovery port uses the same journal and real recovery routine.
    This is not a broker or full Rust-node timing measurement.
    """
    import native_adapter
    import native_strategy
    from recovery import recover
    from tests import test_adaptive_paper_recovery as fixtures
    epoch=1800000000.0;clock=[0.0];refused=[];freeze_at=[]
    actual_sleep=asyncio.sleep
    with tempfile.TemporaryDirectory(dir='/var/tmp') as directory:
        with contextlib.closing(Ledger(Path(directory)/'ledger.sqlite3',
                                      RiskLimits(trial_seconds=1,cleanup_seconds=2))) as ledger:
            ledger.start_trial(epoch)
            ledger.reserve_intent('entry-1','SPY','buy','1','100.01',
                quote=Quote('SPY','100','100.01',epoch),now=epoch,
                market_open=True,session_close=epoch+10000)
            ledger.request_budget(epoch,'submit',client_id='entry-1')
            ledger.record_order('entry-1','fixture-entry','filled','1','100.01',timestamp=epoch)
            controller=runner.Controller(ledger,epoch+10000,market_open=True,clock=lambda:epoch+clock[0])
            controller.quotes={'SPY':Quote('SPY','100','100.01',epoch)}
            wire_port=object.__new__(transport.AlpacaPaperTransport)
            wire_port._state_lock=threading.RLock();wire_port._reasons=set()
            session=object.__new__(transport.GuardedSession)
            session.origin=transport.PAPER_URL;session.read_only=False
            session.lock=threading.Lock();session.observer=None;session._envelopes={}
            session._session=Mock()
            session._session.request.side_effect=AssertionError('frozen port must not send')
            session.before_request=lambda kind,client_id=None:ledger.request_budget(
                epoch+clock[0],kind,client_id=client_id)
            session.before_send=wire_port._wire_guard
            port=types.SimpleNamespace(ready=True,health={'reasons':[]},
                start=AsyncMock(),stop=AsyncMock(),snapshot=AsyncMock(return_value={}),
                stream_health=lambda:{'frozen':bool(wire_port._reasons),'reasons':sorted(wire_port._reasons)})
            controller.port=port
            class Strategy:
                def __init__(self,policy,*args,**kwargs):
                    self.policy=policy;self.started=True;self.enabled=False
                    self.pending={};self.corporate_action_guard=None
                    self.received_quotes=self.native_fills=self.native_rejections=0
                    self.callback_faults=[];self.n=0
                    self._ca_ever_flagged=set()
                def cancel_expired(self,*args,**kwargs):pass
                def rebalance(self,now,*,force_exit=False):
                    if not force_exit:return None
                    self.n+=1;cid=f'refused-exit-{self.n}'
                    payload={'client_order_id':cid,'symbol':'SPY','side':'sell','qty':'1',
                             'limit_price':'100','extended_hours':False}
                    controller.before_submit(payload)
                    envelope=transport.order_envelope(payload);session.expect_submission(envelope)
                    body=dict(envelope['intent'])
                    try:session.request('POST',transport.PAPER_URL+'/v2/orders',json=body)
                    except transport.SubmissionNotSent as exc:
                        refused.append(str(exc));ledger.mark_not_sent(cid,'local_refusal')
                    finally:session.withdraw_submission(cid)
                    return None
            class NativeSession:
                def __init__(self):
                    self.errors=[];self.reconciliation=None;self.execution_stats={}
                    self.average_invariant_mismatches=[];self.done=asyncio.Event()
                async def run_async(self):await self.done.wait()
                def stop(self):self.done.set()
                def fail(self,reason):self.errors.append(reason)
                def native_assertions(self):return {}
            async def advance(seconds):
                clock[0]+=seconds
                controller.quotes['SPY']=Quote('SPY','100','100.01',epoch+clock[0])
                if not freeze_at:
                    freeze_at.append(clock[0]);wire_port._reasons.add('queue_overflow')
                    port.health={'reasons':['queue_overflow']};port.ready=False
                await actual_sleep(0)
            config,_,policy=runner.load_config(SOURCE/'config.json')
            config.update(duration_seconds=1,cleanup_seconds=2)
            async def exercise():
                outcome=await runner.run_native(controller,policy,[{'symbol':'SPY'}],
                                                 'integrity-fixture',config,'10000')
                at_handoff=clock[0]
                spent=ledger.db.execute("SELECT COUNT(*) FROM requests WHERE kind='submit' AND client_id LIKE 'refused-exit-%'").fetchone()[0]
                active=ledger.db.execute("SELECT COUNT(*) FROM requests WHERE kind='submit' AND at>?",(epoch+clock[0]-60,)).fetchone()[0]
                recovery_controller=fixtures.Controller(ledger)
                class RecoveryPort(fixtures.FakePort):
                    async def submit(self,payload):
                        self.first_exit_at=clock[0]
                        return await super().submit(payload)
                fresh=recovery_controller.port=RecoveryPort(recovery_controller)
                fresh.qty=Decimal('1');fresh.cash=Decimal('9899.99')
                fresh.rows={'entry-1':{'client_order_id':'entry-1','id':'fixture-entry',
                    'symbol':'SPY','side':'buy','qty':'1','limit_price':'100.01','filled_qty':'1',
                    'filled_avg_price':'100.01','status':'filled','updated_at_ns':int(epoch*1e9)}}
                recovered=await recover(recovery_controller,{'trial_id':'fault-test','baseline_cash':'10000'},
                    {'cleanup_seconds':2,'quote_max_age_seconds':3,'order_timeout_seconds':.05,
                     'regular_session_only':True,'extended_hours_enabled':False,
                     'sessions':{'extended_hours':False,'overnight_holds':False,'overnight_gross_multiple':'1.0'}},
                    reconcile_fn=fixtures.proof)
                return {'freeze_at':freeze_at[0],'handoff_at':at_handoff,
                    'refused_exit_count':len(refused),'refused_exit_submit_reservations':spent,
                    'active_submits_before_recovery':active,
                    'submit_limit':ledger.limits.max_submits_per_minute,
                    'recovery_first_exit_at':getattr(fresh,'first_exit_at',None),
                    'recovery_exit_count':len(fresh.submissions),'recovery_status':recovered['status'],
                    'recovery_flat':recovered['flat'],'frozen_outcome':outcome['stream_health']}
            with patch.object(native_strategy,'AdaptiveStrategy',Strategy), \
                 patch.object(native_adapter,'build_node',side_effect=lambda *a,**k:NativeSession()), \
                 patch.object(runner,'reconcile',return_value={'positions':1,'open_orders':0}), \
                 patch.object(time,'time',side_effect=lambda:epoch+clock[0]), \
                 patch.object(time,'time_ns',side_effect=lambda:int((epoch+clock[0])*1e9)), \
                 patch.object(time,'monotonic',side_effect=lambda:clock[0]), \
                 patch.object(asyncio,'sleep',side_effect=advance):
                return asyncio.run(exercise())


class StreamFollowups(unittest.TestCase):
    def test_opted_counter_control_rejects_missing_union_counter(self):
        from tests import test_adaptive_paper_readiness_backpressure as combined
        original=transport.AlpacaPaperTransport._consume_events
        source=textwrap.dedent(inspect.getsource(original))
        counter='                    with self._state_lock:\n                        self._skipped_stale_quotes += 1\n'
        self.assertIn(counter,source)
        namespace={}
        exec(compile(source.replace(counter,''),'<counter_removed_parent>','exec'),
             original.__globals__,namespace)
        with patch.object(transport.AlpacaPaperTransport,'_consume_events',namespace['_consume_events']):
            result=unittest.TextTestRunner(stream=io.StringIO()).run(
                unittest.defaultTestLoader.loadTestsFromModule(combined))
        self.assertFalse(result.wasSuccessful(),'opted combined test failed to detect counter removal')
        self.assertEqual(len(result.failures),1)
        self.assertEqual(result.errors,[])

    @unittest.skipUnless(NATIVE, "requires pinned combined native runtime")
    def test_integrity_loss_with_held_position_hands_off_before_refused_exits(self):
        result=integrity_handoff_probe()
        self.assertLessEqual(result['handoff_at']-result['freeze_at'],.1,result)
        self.assertEqual(result['refused_exit_submit_reservations'],0,result)
        self.assertEqual((result['recovery_status'],result['recovery_flat']),('passed',True),result)
        self.assertEqual(result['recovery_exit_count'],1,result)

    def test_real_submit_keeps_integrity_refusal_reason_without_http(self):
        wire=object.__new__(transport.AlpacaPaperTransport)
        wire._state_lock=threading.RLock();wire._reasons={'queue_overflow'}
        guard=object.__new__(transport.GuardedSession)
        guard.origin=transport.PAPER_URL;guard.read_only=False;guard.lock=threading.Lock()
        guard._envelopes={};guard.observer=None;guard._session=Mock()
        guard.before_request=Mock(return_value=0);guard.before_send=wire._wire_guard
        payload={'client_order_id':'fixture-exit','symbol':'SPY','side':'sell','qty':'1',
                 'limit_price':'100','extended_hours':False}
        envelope=transport.order_envelope(payload);guard.expect_submission(envelope)
        with self.assertRaisesRegex(transport.SubmissionNotSent,'^recovery_observation_integrity_lost$'):
            guard.request('POST',transport.PAPER_URL+'/v2/orders',json=dict(envelope['intent']))
        guard._session.request.assert_not_called()
        guard.before_request.assert_called_once_with('submit',client_id='fixture-exit')


class StreamFollowupsAsync(unittest.IsolatedAsyncioTestCase):
    async def test_order_update_queue_latency_is_measured_behind_quotes(self):
        from datetime import datetime,timezone
        from tests.test_adaptive_paper_stream_backpressure import StreamBackpressure
        from tests.test_adaptive_paper_transport import order
        port=StreamBackpressure().port(queue_size=4,quote_timeout=30)
        port._started=True;clock=[0.0];epoch=1800000000;seen=[]
        gate=asyncio.Event();entered=asyncio.Event()
        async def quote_sink(quote):
            if not entered.is_set():entered.set();await gate.wait()
        port._on_quote=quote_sink;port._on_order=seen.append
        raw={'S':'SPY','bp':'100','ap':'100.01','bs':1,'as':1,
             't':datetime.fromtimestamp(epoch,timezone.utc)}
        with patch.object(transport.time,'monotonic',side_effect=lambda:clock[0]), \
             patch.object(transport.time,'time_ns',side_effect=lambda:int((epoch+clock[0])*1e9)):
            await port._quote_callback(raw)
            consumer=asyncio.create_task(port._consume_events())
            try:
                for _ in range(20):
                    if entered.is_set():break
                    await asyncio.sleep(0)
                self.assertTrue(entered.is_set())
                clock[0]=.5;await port._quote_callback(raw)
                clock[0]=1;await port._order_callback({'data':{'event':'new','order':order()}})
                self.assertEqual(seen,[])
                clock[0]=5;gate.set()
                for _ in range(30):
                    if seen:break
                    await asyncio.sleep(0)
                self.assertEqual(len(seen),1)
                measured=port.stream_health()
                self.assertEqual(measured.get('order_updates_dequeued'),1,measured)
                self.assertEqual(measured['order_update_queue_latency_seconds_max'],4)
                self.assertEqual(measured['order_update_callback_to_consumer_seconds_max'],4)
                type(self).last_latency_measurement=measured
            finally:
                consumer.cancel();await asyncio.gather(consumer,return_exceptions=True)

    @unittest.skipUnless(NATIVE, "requires pinned combined native runtime")
    async def test_sdk_batch_stops_after_one_integrity_loss_deadline(self):
        import msgpack
        from alpaca.data.live.websocket import DataStream
        from tests.test_adaptive_paper_stream_backpressure import StreamBackpressure
        port=StreamBackpressure().port(queue_size=1,start_timeout=30)
        port._events.put_nowait(('quote',{}))
        sdk=DataStream('fixture-key','fixture-secret','wss://fixture.invalid',raw_data=True)
        port._quotes_stream=sdk;clock=[0.0];receives=[];intervals=[]
        async def callback(message):
            start=clock[0];await port._quote_callback(message);intervals.append((start,clock[0]))
        sdk._handlers['quotes']['SPY']=callback
        class Socket:
            async def recv(self):
                receives.append(clock[0])
                if len(receives)==1:return msgpack.packb([{'T':'q','S':'SPY','bp':100,'ap':100.01}]*3)
                raise asyncio.CancelledError()
            async def close(self):pass
        sdk._ws=Socket();sdk._running=True
        async def advance(seconds):clock[0]+=seconds
        with patch.object(transport.time,'monotonic',side_effect=lambda:clock[0]), \
             patch.object(transport.asyncio,'sleep',side_effect=advance):
            try:await sdk._consume()
            except asyncio.CancelledError:pass
        self.assertLessEqual(clock[0],8.001,(receives,intervals))
        self.assertEqual(len(intervals),3)
        self.assertEqual(port.stream_health()['backpressure_waits'],1)
        self.assertFalse(sdk._running)
        self.assertIn('queue_overflow',port.health['reasons'])


if __name__=='__main__':unittest.main()
