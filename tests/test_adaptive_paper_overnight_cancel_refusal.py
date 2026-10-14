"""Real cancellation implementation, synthetic SDK I/O; no broker or credentials."""
import asyncio
from datetime import datetime,timezone
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

SOURCE=Path(__file__).resolve().parents[1]/'blueprints/us-equities/adaptive-paper'
sys.path.insert(0,str(SOURCE))
try:
    from . import test_adaptive_paper_overnight_arming as fixtures
    from .adaptive_paper_hermetic import patch_default_stop,restore_default_stop
except ImportError:
    import test_adaptive_paper_overnight_arming as fixtures
    from adaptive_paper_hermetic import patch_default_stop,restore_default_stop

def setUpModule():
    global _token
    _token=patch_default_stop()

def tearDownModule():
    restore_default_stop(_token)

class OvernightCancelRefusal(unittest.TestCase):
    def test_422_live_lookup_releases_latch_retries_and_stops_entry_at_cutoff(self):
        from transport import AlpacaPaperTransport,normalize_order
        c,clock,_,bounds,_=fixtures.OvernightArming._controller(self)
        async def exercise():
            observed=asyncio.Event()
            deletes=[]
            delivered=[]
            reasons=[]
            wire=AlpacaPaperTransport.__new__(AlpacaPaperTransport)
            wire._operation_lock=asyncio.Lock()
            wire._observation_lock=asyncio.Lock()
            wire._executions={}
            payload={'id':'synthetic-entry','client_order_id':'entry','symbol':'SPY','side':'buy',
                     'qty':'1','limit_price':'10.01','filled_qty':'0','filled_avg_price':None,
                     'status':'accepted','updated_at':datetime.fromtimestamp(clock[0],timezone.utc).isoformat()}
            wire._intents={'entry':{k:payload[k] for k in ('client_order_id','symbol','side','qty','limit_price')}}
            wire._observed={'entry':normalize_order(payload)}
            wire.freeze_health=reasons.append
            class Refused(RuntimeError):
                status_code=422
            def delete(broker_id):
                deletes.append(broker_id)
                if len(deletes)==1:
                    raise Refused('synthetic DELETE refusal')
            def lookup(client_id):
                return {**payload,'status':'accepted' if len(deletes)==1 else 'canceled',
                        'updated_at':datetime.fromtimestamp(clock[0]+len(deletes)*.1,timezone.utc).isoformat()}
            def observe(order):
                delivered.append(order)
                c.observe(order)
                observed.set()
            wire.sink_observation=observe
            wire._client=SimpleNamespace(cancel_order_by_id=delete,get_order_by_client_id=lookup,
                _session=SimpleNamespace(announce_cancel=lambda *args:None,withdraw_cancel=lambda:None))
            c.port.cancel=wire.cancel
            clock[0]=bounds['flatten_at']
            try:
                self.assertTrue(await c.overnight_tick(clock[0]))
                await asyncio.wait_for(observed.wait(),5)
                await asyncio.gather(*list(c._overnight_cancel_tasks.values()))
                self.assertNotIn('entry',c.port.overnight_cancel_pending,
                                 'REST422 with a live lookup must release cutoff retry latch')
                self.assertEqual(c.ledger.unresolved()[0].status,'accepted')
                self.assertIn('cancellation_unresolved',reasons)
                observed.clear()
                self.assertTrue(await c.overnight_tick(clock[0]))
                await asyncio.wait_for(observed.wait(),5)
                await asyncio.gather(*list(c._overnight_cancel_tasks.values()))
                self.assertEqual(deletes,['synthetic-entry','synthetic-entry'])
                self.assertEqual(c.ledger.intents()[0].status,'canceled')
                self.assertEqual(c.ledger.unresolved(),[])
                self.assertTrue(all(order.get('event') is None for order in delivered),
                                'the retry must work without a separate rejection stream event')
            finally:
                await c.stop_overnight_cancels()
        asyncio.run(exercise())
