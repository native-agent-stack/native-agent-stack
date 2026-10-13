"""Synthetic SDK-style bursts at the real callback/consumer seam; no broker I/O."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import os
from pathlib import Path
import sys
import time
import types
import unittest
from unittest.mock import Mock,patch

SOURCE=Path(os.environ.get('ADAPTIVE_SOURCE_ROOT',str(Path(__file__).resolve().parents[1]/'blueprints/us-equities/adaptive-paper')))
sys.path.insert(0,str(SOURCE))
import transport as t
import runner


class StreamBackpressure(unittest.IsolatedAsyncioTestCase):
    def port(self,**kwargs):
        enums=types.ModuleType('alpaca.data.enums')
        enums.DataFeed=lambda value:value
        stubs={'alpaca':types.ModuleType('alpaca'),'alpaca.data':types.ModuleType('alpaca.data'),
               'alpaca.data.enums':enums}
        with patch.dict(sys.modules,stubs),patch.object(t,'_sdk_client',return_value=Mock()), \
                patch.object(t,'_protocol_factory',return_value=None), \
                patch.object(t,'_stream_classes',return_value=(Mock,Mock)):
            port=t.AlpacaPaperTransport('fixture-key','fixture-secret',['SPY'],
                before_request=lambda *a,**k:None,before_submit=lambda *a:None,
                sink_observation=lambda *a:None,**kwargs)
        return port

    async def test_1025_quote_startup_burst_waits_for_blocked_consumer_without_loss(self):
        port=self.port(quote_timeout=30)
        gate=asyncio.Event()
        entered=asyncio.Event()
        seen=[]
        async def sink(quote):
            seen.append(quote['bid'])
            if len(seen)==1:
                entered.set()
                await gate.wait()
        port._on_quote=sink
        port._on_order=lambda row:None
        raw={'S':'SPY','bp':'100.00','ap':'100.01','bs':1,'as':1,'t':datetime.now(timezone.utc)}
        await port._quote_callback(raw)
        consumer=asyncio.create_task(port._consume_events())
        await asyncio.wait_for(entered.wait(),2)
        def sdk_burst():
            async def produce():
                for _ in range(1025):await port._quote_callback(raw)
            asyncio.run(produce())
        executor=ThreadPoolExecutor(max_workers=1)
        producer=executor.submit(sdk_burst)
        try:
            async def full():
                while port._events.qsize()!=1024:await asyncio.sleep(0.001)
            await asyncio.wait_for(full(),2)
            await asyncio.sleep(0.01)
            self.assertFalse(producer.done(),'SDK callback must backpressure instead of dropping the 1025th event')
            self.assertNotIn('queue_overflow',port._reasons)
            gate.set()
            await asyncio.wait_for(asyncio.wrap_future(producer),5)
            async def drained():
                while len(seen)!=1026:await asyncio.sleep(0.001)
            await asyncio.wait_for(drained(),5)
            self.assertEqual(port._events.qsize(),0)
            self.assertEqual(port._reasons,set())
        finally:
            gate.set()
            port._stopping=True
            consumer.cancel()
            await asyncio.gather(consumer,return_exceptions=True)
            await asyncio.wait_for(asyncio.wrap_future(producer),5)
            executor.shutdown(wait=True)

    async def test_each_sdk_channel_backpressures_then_preserves_the_waiting_event(self):
        for kind in ('quote','order','status','luld'):
            port=self.port(queue_size=1)
            callback=getattr(port,'_'+kind+'_callback')
            await callback({'first':True})
            task=asyncio.create_task(callback({'second':True}))
            try:
                await asyncio.sleep(0.02)
                self.assertFalse(task.done(),kind)
                self.assertEqual(port._events.get_nowait(),(kind,{'first':True}))
                await asyncio.wait_for(task,2)
                self.assertEqual(port._events.get_nowait(),(kind,{'second':True}))
                self.assertEqual(port._reasons,set())
            finally:
                port._stopping=True
                await asyncio.gather(task,return_exceptions=True)

    async def test_sdk_thread_waits_while_owner_loop_is_synchronously_blocked(self):
        import threading

        port=self.port(quote_timeout=30)
        attempted=threading.Event()
        seen=[]
        port._on_quote=seen.append
        raw={'S':'SPY','bp':'100.00','ap':'100.01','bs':1,'as':1,'t':datetime.now(timezone.utc)}
        def sdk_burst():
            async def produce():
                for n in range(1025):
                    if n==1024:attempted.set()
                    await port._quote_callback(raw)
            asyncio.run(produce())
        executor=ThreadPoolExecutor(max_workers=1)
        producer=executor.submit(sdk_burst)
        consumer=None
        try:
            # Deliberately block THIS owner loop until the independent SDK
            # thread attempts event 1025, just as synchronous startup can.
            self.assertTrue(attempted.wait(2))
            self.assertEqual(port._events.qsize(),1024)
            self.assertFalse(producer.done())
            self.assertEqual(port._reasons,set())
            consumer=asyncio.create_task(port._consume_events())
            await asyncio.wait_for(asyncio.wrap_future(producer),5)
            async def drained():
                while len(seen)!=1025:await asyncio.sleep(0.001)
            await asyncio.wait_for(drained(),5)
            self.assertEqual(port._reasons,set())
        finally:
            port._stopping=True
            if consumer:
                consumer.cancel()
                await asyncio.gather(consumer,return_exceptions=True)
            await asyncio.wait_for(asyncio.wrap_future(producer),5)
            executor.shutdown(wait=True)

    async def test_stalled_consumer_still_freezes_on_bounded_enqueue_deadline(self):
        port=self.port(queue_size=1,start_timeout=0.03)
        await port._quote_callback({'first':True})
        await asyncio.wait_for(port._quote_callback({'second':True}),1)
        self.assertIn('queue_overflow',port._reasons)
        self.assertEqual(port._events.qsize(),1)

    async def test_stop_unblocks_a_backpressured_sdk_callback(self):
        port=self.port(queue_size=1)
        await port._quote_callback({'first':True})
        task=asyncio.create_task(port._quote_callback({'second':True}))
        await asyncio.sleep(0.02)
        port._stopping=True
        await asyncio.wait_for(task,1)
        self.assertEqual(port._events.qsize(),1)

    async def test_cancelled_waiting_callback_explicitly_freezes_before_shutdown(self):
        port=self.port(queue_size=1)
        await port._order_callback({'first':True})
        task=asyncio.create_task(port._order_callback({'second':True}))
        await asyncio.sleep(0.02)
        task.cancel()
        await asyncio.gather(task,return_exceptions=True)
        self.assertIn('queue_enqueue_cancelled',port._reasons)
        port._events.get_nowait()
        port._auth={kind:True for kind in ('orders','quotes')}
        port._acks=dict(port._auth)
        port._quote_seen={'SPY':time.monotonic()}
        with self.assertRaisesRegex(t.TransportError,'event loss requires'):
            port.mark_reconciled()

    def reconciliable(self,port):
        port._started=True
        port._auth={kind:True for kind in ('orders','quotes')}
        port._acks=dict(port._auth)
        port._quote_seen={'SPY':time.monotonic()}

    async def test_waiting_order_blocks_ack_until_it_is_enqueued_and_processed(self):
        port=self.port(queue_size=1)
        self.reconciliable(port)
        port.freeze_health('quote_stale')
        await port._quote_callback({'queued_quote':True})
        task=asyncio.create_task(port._order_callback({'received_fill':True}))
        try:
            await asyncio.sleep(0.02)
            self.assertFalse(task.done())
            with self.assertRaisesRegex(t.TransportError,'not ready for reconciliation'):
                port.mark_reconciled()
            self.assertIn('quote_stale',port.health['reasons'])
            self.assertFalse(port.ready)
            self.assertEqual(port._events.get_nowait(),('quote',{'queued_quote':True}))
            await asyncio.wait_for(task,2)
            with self.assertRaises(t.TransportError):port.mark_reconciled()
            self.assertEqual(port._events.get_nowait(),('order',{'received_fill':True}))
            port.mark_reconciled()
            self.assertTrue(port.ready)
        finally:
            port._stopping=True
            await asyncio.gather(task,return_exceptions=True)

    async def test_every_concurrent_waiting_order_remains_visible_after_one_enqueues(self):
        port=self.port(queue_size=1)
        self.reconciliable(port)
        port.freeze_health('quote_stale')
        await port._quote_callback({'queued_quote':True})
        tasks=[asyncio.create_task(port._order_callback({'update':n})) for n in (1,2)]
        try:
            await asyncio.sleep(0.02)
            with self.assertRaises(t.TransportError):port.mark_reconciled()
            port._events.get_nowait()
            async def first_enqueued():
                while not any(t.done() for t in tasks):await asyncio.sleep(0.001)
            await asyncio.wait_for(first_enqueued(),2)
            self.assertEqual(sum(t.done() for t in tasks),1)
            with self.assertRaises(t.TransportError):port.mark_reconciled()
            port._events.get_nowait()
            # The queue is empty now, but one received update still waits.
            with self.assertRaises(t.TransportError):port.mark_reconciled()
            await asyncio.wait_for(asyncio.gather(*tasks),2)
            port._events.get_nowait()
            port.mark_reconciled()
            self.assertTrue(port.ready)
        finally:
            port._stopping=True
            await asyncio.gather(*tasks,return_exceptions=True)


class FrozenStreamReceipt(unittest.TestCase):
    def test_frozen_stream_is_distinct_from_no_signals_even_when_flat(self):
        for native_fills in (0,1):
            outcome={'stream_health':{'frozen':True,'reasons':['queue_overflow']}}
            status=runner._run_native_status({'positions':0,'open_orders':0},[],native_fills,
                                            outcome,{'overnight_holds':False},0)
            self.assertEqual(status,'stream_frozen')

    def test_stream_freeze_survives_recovery_and_remains_needs_attention(self):
        for recovery_status in ('passed','needs_attention'):
            outcome={'status':'stream_frozen','flat':False,'stream_health':{'frozen':True,'reasons':['queue_overflow']}}
            result=runner._apply_forced_recovery_outcome(outcome,{'status':recovery_status,'flat':True})
            self.assertEqual(result['status'],'stream_frozen')
            self.assertEqual(runner.trial_phase_and_exit_code(result),('needs_attention',3))

    def test_healthy_flat_no_fill_run_retains_no_signal_status(self):
        self.assertEqual(runner._run_native_status({'positions':0,'open_orders':0},[],0,
            {'stream_health':{'frozen':False,'reasons':[]}}, {'overnight_holds':False},0),'completed_no_signals')
