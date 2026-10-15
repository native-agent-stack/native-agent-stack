"""SDK-free F3-F5 regressions; synthetic HTTP/ports and FIFO, no network."""
import asyncio
import inspect
import io
from pathlib import Path
import sys
import threading
import textwrap
import unittest
from unittest.mock import Mock, patch

SOURCE=Path(__file__).resolve().parents[1]/'blueprints/us-equities/adaptive-paper'
sys.path.insert(0,str(SOURCE))
import transport
from tests.adaptive_paper_hermetic import patch_default_stop, restore_default_stop

_hermetic=None
def setUpModule():
    global _hermetic
    _hermetic=patch_default_stop()
def tearDownModule():restore_default_stop(_hermetic)


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



if __name__=='__main__':unittest.main()
