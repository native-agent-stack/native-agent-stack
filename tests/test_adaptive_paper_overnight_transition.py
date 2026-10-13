"""Same-controller boundary, independent asset delivery and per-symbol polling."""
import ast
import asyncio
from datetime import datetime, timezone
from decimal import Decimal
import io
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

SOURCE = Path(__file__).resolve().parents[1] / "blueprints/us-equities/adaptive-paper"
sys.path.insert(0, str(SOURCE))
try:
    from . import test_adaptive_paper_overnight_arming as fixtures
    from . import test_adaptive_paper_overnight_guard_pins as pins
    from .test_adaptive_paper_overnight_guard_mutations import delete_in_definition
except ImportError:
    import test_adaptive_paper_overnight_arming as fixtures
    import test_adaptive_paper_overnight_guard_pins as pins
    from test_adaptive_paper_overnight_guard_mutations import delete_in_definition


class OvernightTransition(unittest.TestCase):
    def boundary(self):
        c, clock, _, bounds, _ = fixtures.OvernightArming._controller(self, held=True,
            now=datetime(2026,3,11,7,49,tzinfo=timezone.utc).timestamp())
        clock[0] = bounds["boundary_at"]+1
        c.quote({"symbol":"SPY","bid":"10","ask":"10.01","ts_ns":int(clock[0]*1e9)})
        c.trading_status({"symbol":"SPY","source":"alpaca_assets","ts_ns":int(clock[0]*1e9),
            "overnight_tradable":False,"overnight_halted":False,"tradable":True,"asset_status":"active"})
        return c,clock,bounds

    def order(self):
        return pins.OvernightGuardPins.order(self)

    def test_same_controller_reserves_pre_exit_without_manual_close(self):
        c,clock,bounds = self.boundary()
        self.assertEqual(c.close,bounds["boundary_at"])
        with pins.OvernightGuardPins.rejection(self):
            try:
                c.before_submit(self.order())
            except Exception as error:
                self.fail("same-controller residual refused: "+str(error))
        self.assertEqual(c.ledger.positions()["SPY"].qty,Decimal(1))
        self.assertEqual(c.ledger.overnight_windows()["pin-exit"],bounds)

    def test_pending_exit_revalidates_at_boundary_on_original_controller(self):
        c,clock,_,bounds,_=fixtures.OvernightArming._controller(self,held=True,
            now=datetime(2026,3,11,7,49,tzinfo=timezone.utc).timestamp())
        with pins.OvernightGuardPins.rejection(self):
            c.before_submit(self.order())
        self.assertEqual(c.close,bounds["boundary_at"])
        clock[0]=bounds["boundary_at"]+1
        c.quote({"symbol":"SPY","bid":"10","ask":"10.01","ts_ns":int(clock[0]*1e9)})
        c.trading_status({"symbol":"SPY","source":"alpaca_assets","ts_ns":int(clock[0]*1e9),
            "overnight_tradable":False,"overnight_halted":False,"tradable":True,"asset_status":"active"})
        try:
            asyncio.run(c.before_request("submit",client_id="pin-exit"))
        except Exception as error:
            self.fail("pending residual refused at crossing: "+str(error))
        self.assertEqual(c.ledger.overnight_windows()["pin-exit"],bounds)

    def test_same_controller_refreshes_before_automatic_recovery(self):
        from recovery import recover
        from safety import Quote
        c,clock,bounds=self.boundary()
        original=c.ledger.intents()[0]
        cash=Decimal("10000")-original.filled_qty*original.average_price
        class Port:
            ready=False
            health={"reasons":[]}
            symbols=("SPY",)
            submissions=[]
            def adopt_intents(self,rows):
                self.adopted=list(rows)
            async def start(self,on_quote,on_order):
                self.on_order=on_order
                on_quote({"symbol":"SPY","bid":"10","ask":"10.01","ts_ns":int(clock[0]*1e9)})
            async def snapshot(self):
                return {"complete":True,"orders":self.rows,"positions":self.positions,"account":{"cash":str(self.cash)}}
            async def submit(self,payload):
                with pins.OvernightGuardPins.rejection(outer):
                    c.before_submit(payload)
                    await c.before_request("submit",client_id=payload["client_order_id"])
                self.submissions.append(payload)
                self.cash+=Decimal(payload["qty"])*Decimal(payload["limit_price"])
                self.positions=[]
                row={**payload,"id":"synthetic-recovery","status":"filled","filled_qty":payload["qty"],
                     "filled_avg_price":payload["limit_price"],"updated_at_ns":int(clock[0]*1e9)}
                self.rows.append(row)
                self.on_order(row)
                return row
            async def stop(self):
                pass
        outer=self
        port=Port()
        port.rows=[{"client_order_id":"entry","symbol":"SPY","side":"buy","qty":"1","limit_price":"10.01",
                    "id":"synthetic-entry","status":"filled","filled_qty":"1","filled_avg_price":"10.01",
                    "updated_at_ns":int((bounds["boundary_at"]-660)*1e9)}]
        port.positions=[{"symbol":"SPY","qty":"1"}]
        port.cash=cash
        for name in ("overnight_enabled","feed","quote_source_mode","extended_hours_allowed",
                     "flatten_minutes_before_pre","quote_timeout"):
            setattr(port,name,getattr(c.port,name))
        c.port=c.bind(port)
        config={"feed":"boats","quote_source":"boats_rest","overnight":{"enabled":True},
                "regular_session_only":False,"extended_hours_enabled":True,
                "sessions":{"extended_hours":True,"overnight_holds":False},
                "cleanup_seconds":60,"order_timeout_seconds":1,"quote_max_age_seconds":3}
        result=asyncio.run(recover(c,{"trial_id":"held","baseline_cash":"10000"},config))
        self.assertEqual((result["status"],result["flat"]),("passed",True),result["errors"])
        self.assertEqual(len(port.submissions),1)
        self.assertIs(port.submissions[0]["reduce_only"],True)

    def test_residual_admission_is_checked_before_resting_exit_reprice(self):
        import exits
        node=pins.method_source("native_strategy.py","AdaptiveStrategy._session_exit_decision")
        scope={"ExitDecision":exits.ExitDecision,"ExitContext":exits.ExitContext,
               "DEFAULT_PLAN":SimpleNamespace(evaluate=lambda *args:SimpleNamespace(submit=True,reason="actionable")),
               "sell_quote_age_seconds":lambda config:3,"QUOTE_FUTURE_TOLERANCE_SECONDS":.25}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),"<production-session-exit>","exec"),scope)
        for session in ("PRE","RTH","POST"):
            for reason in ("overnight_status_stale","overnight_status_unknown","exit_asset_not_tradable"):
                with self.subTest(session=session,reason=reason):
                    def refused(*args):
                        raise RuntimeError(reason)
                    owner=SimpleNamespace(_exit_session_at=True,_exit_session=lambda now:session,
                        transport=SimpleNamespace(overnight_enabled=True,overnight_check=refused),
                        policy=SimpleNamespace(latest={"SPY":SimpleNamespace(timestamp=100,bid=10,ask=10.01)},
                                               config=SimpleNamespace()))
                    decision=scope["_session_exit_decision"](owner,"SPY",100,"force_flatten")
                    self.assertFalse(decision.submit)
                    self.assertEqual(decision.reason,reason)

    def test_successful_halt_delivered_even_when_quote_fails_or_rate_limits(self):
        from overnight import BoatsQuoteSource
        async def exercise(rate_limited):
            c,clock,cancels,_,_=fixtures.OvernightArming._controller(self)
            now=clock[0]
            class QuoteFailure(RuntimeError):
                status_code=429 if rate_limited else 500
            async def asset(symbol):
                return {"symbol":symbol,"source":"alpaca_assets","ts_ns":int(now*1e9),
                        "overnight_tradable":True,"overnight_halted":True}
            async def quote(symbol):
                raise QuoteFailure()
            source=BoatsQuoteSource(("SPY",),quote,asset)
            try:
                delivered=[]
                # The production poller supplies this callback independently.
                if "on_asset" not in __import__("inspect").signature(source.sweep).parameters:
                    rows=await source.sweep(1)
                    for row in rows:
                        c.trading_status(row["asset"])
                else:
                    await source.sweep(1,on_asset=lambda status:(delivered.append(status),c.trading_status(status)))
                self.assertTrue(c.is_halted("SPY"))
                with self.assertRaisesRegex(RuntimeError,"overnight_halted"):
                    c.port.overnight_check("SPY",now,"buy")
                await c.overnight_tick(now)
                self.assertEqual(cancels,["entry"])
                self.assertEqual(source.retry_at["SPY"],3 if rate_limited else 2)
                held,held_clock,held_cancels,bounds,_=fixtures.OvernightArming._controller(self,held=True)
                with pins.OvernightGuardPins.rejection(self):
                    held.before_submit(self.order())
                held.ledger.record_order("pin-exit","resting-exit","accepted","0",None,timestamp=held_clock[0])
                held.trading_status(source.assets["SPY"])
                await held.overnight_tick(held_clock[0])
                self.assertEqual(held_cancels,[])
                self.assertEqual(held.ledger.unresolved()[0].status,"accepted")
            finally:
                await source.close()
        for rate in (False,True):
            with self.subTest(rate_limited=rate):
                asyncio.run(exercise(rate))

    def test_healthy_symbol_delivered_before_other_symbol_finishes(self):
        from overnight import BoatsQuoteSource
        async def exercise():
            slow=asyncio.Event()
            healthy=asyncio.Event()
            async def asset(symbol):
                return {"symbol":symbol,"ts_ns":1}
            async def quote(symbol):
                if symbol=="SLOW":
                    await slow.wait()
                return {"symbol":symbol,"ts_ns":1}
            source=BoatsQuoteSource(("FAST","SLOW"),quote,asset)
            task=None
            try:
                if "on_quote" not in __import__("inspect").signature(source.sweep).parameters:
                    task=asyncio.create_task(source.sweep(1))
                else:
                    task=asyncio.create_task(source.sweep(1,on_quote=lambda row:healthy.set() if row["symbol"]=="FAST" else None))
                for _ in range(20):
                    if healthy.is_set():
                        break
                    await asyncio.sleep(0)
                self.assertTrue(healthy.is_set(),"completed healthy observation held behind slow symbol")
                self.assertFalse(task.done())
            finally:
                slow.set()
                if task is not None:
                    await task
                await source.close()
        asyncio.run(exercise())

    def test_production_poller_reschedules_fast_symbol_while_slow_request_waits(self):
        import transport
        from overnight import BoatsQuoteSource
        async def exercise():
            slow=asyncio.Event()
            twice=asyncio.Event()
            reads={"FAST":0,"SLOW":0}
            async def asset(symbol):
                return {"symbol":symbol,"ts_ns":1}
            async def quote(symbol):
                reads[symbol]+=1
                if symbol=="SLOW":
                    await slow.wait()
                if reads["FAST"]>=2:
                    twice.set()
                return {"symbol":symbol,"ts_ns":1}
            source=BoatsQuoteSource(("FAST","SLOW"),quote,asset)
            owner=SimpleNamespace(_stopping=False,_boats_source=source,_enqueue=Mock(),
                                  _authorized=Mock(),_ack=Mock())
            task=asyncio.create_task(transport.AlpacaPaperTransport._poll_boats(owner))
            try:
                done,_=await asyncio.wait([asyncio.create_task(twice.wait())],timeout=1.5)
                self.assertTrue(twice.is_set(),"healthy symbol cannot repoll while another SDK read waits")
                self.assertEqual(reads["SLOW"],1)
            finally:
                owner._stopping=True
                slow.set()
                await task
                await source.close()
        asyncio.run(exercise())


TRANSITION_MUTANTS = (
    ("reserve-current-close","runner","Controller.before_submit",'if order["side"] == "sell":\n                self.refresh_exit_session()', "if False:\n                self.refresh_exit_session()",
     "test_same_controller_reserves_pre_exit_without_manual_close"),
    ("pending-current-close","runner","Controller.before_request",'if intent.side == "sell":\n                        self.refresh_exit_session()', "if False:\n                        self.refresh_exit_session()",
     "test_pending_exit_revalidates_at_boundary_on_original_controller"),
    ("recovery-current-close","recovery","recover",'controller.refresh_exit_session()', "None",
     "test_same_controller_refreshes_before_automatic_recovery"),
    ("residual-reprice-admission","native_strategy","AdaptiveStrategy._session_exit_decision",
     'if getattr(getattr(self, "transport", None), "overnight_enabled", False) is True:',
     'if self._exit_session(now) == "OVERNIGHT" and getattr(getattr(self, "transport", None), "overnight_enabled", False) is True:',
     "test_residual_admission_is_checked_before_resting_exit_reprice"),
    ("independent-asset-delivery","overnight","BoatsQuoteSource.sweep",'on_asset(self.assets[symbol])',"None",
     "test_successful_halt_delivered_even_when_quote_fails_or_rate_limits"),
    ("independent-quote-delivery","overnight","BoatsQuoteSource.sweep",'on_quote(row)',"None",
     "test_healthy_symbol_delivered_before_other_symbol_finishes"),
    ("per-symbol-reschedule","transport","AlpacaPaperTransport._poll_boats",'symbols=(symbol,)',
     'symbols=self._boats_source.symbols',"test_production_poller_reschedules_fast_symbol_while_slow_request_waits"),
)


class TransitionMutants(unittest.TestCase):
    def test_each_transition_guard_deletion_fails_by_assertion(self):
        import importlib
        modules={n:importlib.import_module(n) for n in ("runner","recovery","overnight","transport")}
        sources={n:(SOURCE/(n+".py")).read_text() for n in (*modules,"native_strategy")}
        originals={n:dict(m.__dict__) for n,m in modules.items()}
        for name,module,definition,old,new,test in TRANSITION_MUTANTS:
            with self.subTest(mutant=name):
                # Two recovery refresh sites intentionally share the same
                # mechanism: remove both to model the original stale controller.
                if name=="recovery-current-close":
                    changed=sources[module].replace(old,new)
                else:
                    changed=delete_in_definition(sources[module],definition,old,new)
                real_read=Path.read_text
                def read(path,*args,**kwargs):
                    if path==SOURCE/(module+".py"):
                        return changed
                    return real_read(path,*args,**kwargs)
                try:
                    if module in modules:
                        exec(compile(changed,"<transition-mutant:"+name+">","exec"),modules[module].__dict__)
                    with patch.object(Path,"read_text",read):
                        suite=unittest.defaultTestLoader.loadTestsFromName("OvernightTransition."+test,sys.modules[__name__])
                        output=io.StringIO()
                        result=unittest.TextTestRunner(stream=output).run(suite)
                    self.assertGreater(len(result.failures),0,output.getvalue())
                    self.assertEqual(result.errors,[],output.getvalue())
                    print("transition_mutant",name,"assertion_failures",len(result.failures),"errors",len(result.errors))
                finally:
                    for n,m in modules.items():
                        m.__dict__.clear()
                        m.__dict__.update(originals[n])
