"""A1/A2/A4/A5/A7 pinned-native seams, plus AST seam tests in stdlib CI."""
import ast
from dataclasses import replace
from decimal import Decimal as D
import importlib.metadata
import os
from pathlib import Path
import socket
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from test_engine_lumibot_governor import CODE, CoreCase, FakeSDK, NOW, OrderData
from governor import Decision, GuardRefusal, Intent
from guarded_api import GuardedApi
from stock_only_alpaca import load_classes, read_inbox


def installed():
    try: return importlib.metadata.version("lumibot") == "4.6.11"
    except importlib.metadata.PackageNotFoundError: return False


class SeamCI(CoreCase):
    def test_A2_each_committed_seam_override_independently(self):
        tree=ast.parse((CODE/"stock_only_alpaca.py").read_text())
        function=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=="load_classes")
        klass=next(x for x in function.body if isinstance(x,ast.ClassDef) and x.name=="StockOnlyAlpaca")
        class Parent:
            def _submit_orders(self,*a,**k):return "UNGUARDED"
            _submit_multileg_order=_submit_orders
            _modify_order=_submit_orders
            sell_all=_submit_orders
            close_position=_submit_orders
            close_positions=_submit_orders
        ns={"Alpaca":Parent,"GuardedApi":GuardedApi,"Decision":Decision,"Order":object,"Asset":object}
        exec(compile(ast.Module([klass],type_ignores=[]),"committed-L2-seams","exec"),ns)
        broker=ns["StockOnlyAlpaca"].__new__(ns["StockOnlyAlpaca"]);broker.governor=self.gov
        for name in ("_submit_orders","_submit_multileg_order","_modify_order","sell_all","close_position","close_positions"):
            with self.subTest(name=name),self.assertRaisesRegex(GuardRefusal,"^broker_seam$"):
                getattr(broker,name)(None)

    def test_A5_stub_constructor_no_paper_and_wrong_url(self):
        # Execute committed class source with vendor-shaped stubs; no engine
        # package is required in CI. NativeCase repeats the actual inheritance.
        tree=ast.parse((CODE/"stock_only_alpaca.py").read_text())
        function=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=="load_classes")
        klass=next(x for x in function.body if isinstance(x,ast.ClassDef) and x.name=="StockOnlyAlpaca")
        class Parent:
            created=0
            def __init__(self,config,**kwargs):
                Parent.created+=1; self.is_paper=True; self._api=FakeSDK()
            @property
            def api(self):return self._api
            def _create_trading_client(self):return FakeSDK()
        # This constructor test isolates L2's own check. L1 independently
        # tests its defensive URL verification, so it must not mask L2.
        ns={"Alpaca":Parent,"GuardedApi":lambda *args:object(),"Decision":Decision,
            "Order":object,"Asset":object}
        exec(compile(ast.Module([klass],type_ignores=[]),"committed-L2-seam","exec"),ns)
        Broker=ns["StockOnlyAlpaca"]
        for config in ({},{"PAPER":False},{"PAPER":1},{"PAPER":True,"is_paper":True}):
            with self.assertRaisesRegex(GuardRefusal,"^paper_required$"):
                Broker(config,governor=self.gov,clock=lambda:NOW,data_source=object())
        self.assertEqual(Parent.created,0)
        with patch.object(FakeSDK,"_base_url","https://api.alpaca.markets"):
            with self.assertRaisesRegex(GuardRefusal,"^paper_url$"):
                Broker({"PAPER":True},governor=self.gov,clock=lambda:NOW,data_source=object(),
                       session="RTH",clock_ns=NOW)
        for session,stamp,reason in [(None,NOW,"session"),("CLOSED",NOW,"session"),
                                     ("RTH",None,"clock"),("RTH",NOW-250_000_001,"clock")]:
            with self.assertRaisesRegex(GuardRefusal,"^"+reason+"$"):
                Broker({"PAPER":True},governor=self.gov,clock=lambda:NOW,data_source=object(),
                       session=session,clock_ns=stamp)

    def test_A2_inbox_is_closed_and_has_no_model_numeric_fields(self):
        path=self.root/"inbox.jsonl"
        path.write_text('{"symbol":"SYN","side":"buy","sizing":"entry"}\n')
        self.assertEqual(read_inbox(path),(Intent("SYN","buy"),))
        for row in ({"symbol":"SYN","side":"buy","sizing":"entry","qty":2},
                    {"symbol":"SYN","side":"buy","sizing":1}):
            import json
            path.write_text(json.dumps(row)+"\n")
            with self.assertRaisesRegex(GuardRefusal,"^inbox$"):read_inbox(path)


@unittest.skipUnless(installed(),"isolated Lumibot4.6.11 runtime required")
class NativeCase(CoreCase):
    def make_broker(self,config=None,url=None):
        import lumibot.brokers.alpaca as vendor
        from lumibot.data_sources import DataSource
        class StubData(DataSource):
            SOURCE="SYNTHETIC"
            def get_chains(self,*args,**kwargs):return {}
            def get_last_price(self,*args,**kwargs):return D("10")
            def get_historical_prices(self,*args,**kwargs):return None
        Broker,_=load_classes()
        def factory(*args,**kwargs):
            if url:self.sdk._base_url=url
            return self.sdk
        with patch.object(vendor,"TradingClient",factory):
            return Broker(config if config is not None else {"API_KEY":"synthetic-placeholder",
                          "API_SECRET":"synthetic-placeholder","PAPER":True},
                          governor=self.gov,clock=lambda:NOW,data_source=StubData(),session="RTH",clock_ns=NOW)

    def test_A1_real_vendor_single_payload_each_session(self):
        broker=self.make_broker()
        for session in ("PRE","RTH","POST","OVERNIGHT"):
            decision=self.decision(quote=replace(self.quote,session=session))
            broker.submit_decision(decision)
            self.assertEqual(self.sdk.writes[-1][1],decision.payload())
            self.gov.reconcile(decision.client_order_id,terminal="filled",account=self.account)

    def test_A5_native_missing_paper(self):
        with self.assertRaisesRegex(GuardRefusal,"^paper_required$"):
            self.make_broker({"API_KEY":"synthetic-placeholder","API_SECRET":"synthetic-placeholder"})
        self.assertFalse(self.sdk.writes)

    def test_A5_native_false_paper(self):
        with self.assertRaisesRegex(GuardRefusal,"^paper_required$"):
            self.make_broker({"API_KEY":"synthetic-placeholder","API_SECRET":"synthetic-placeholder","PAPER":False})

    def test_A5_native_resolved_nonpaper_url(self):
        with self.assertRaisesRegex(GuardRefusal,"^paper_url$"):
            self.make_broker(url="https://api.alpaca.markets")

    def test_A5_native_false_is_paper(self):
        import lumibot.brokers.alpaca as vendor
        with patch.object(vendor.Alpaca,"_update_attributes_from_config",
                          lambda obj,c: (setattr(obj,"api_key","synthetic"),
                                         setattr(obj,"api_secret","synthetic"),setattr(obj,"is_paper",False))):
            with self.assertRaisesRegex(GuardRefusal,"^paper_required$"):
                self.make_broker()

    def test_A2_native_seams(self):
        broker=self.make_broker()
        for name in ("_submit_orders","_submit_multileg_order","_modify_order",
                     "sell_all","close_position","close_positions"):
            with self.subTest(name=name),self.assertRaisesRegex(GuardRefusal,"^broker_seam$"):
                getattr(broker,name)(None)
        from lumibot.entities import Order,Asset
        for kind in ("market","stop","stop_limit","trailing_stop","smart_limit"):
            prices = {"limit_price":10}
            if kind=="stop":prices={"stop_price":9}
            if kind=="stop_limit":prices={"stop_price":9,"stop_limit_price":9}
            if kind=="trailing_stop":prices={"trail_price":1}
            if kind=="smart_limit":prices={"limit_price":10}
            order=Order("synthetic",Asset("SYN"),1,"buy",order_type=kind,**prices)
            with self.assertRaisesRegex(GuardRefusal,"^order_type$"):broker._submit_order(order)
        order=Order("synthetic",Asset("SYN"),1,"buy",order_type="limit",limit_price=10,
                    time_in_force="day",custom_params={"extended_hours":True})
        with self.assertRaisesRegex(GuardRefusal,"^custom_params$"):broker._submit_order(order)
        for asset in (Asset("BTC",asset_type="crypto"),
                      Asset("SYN",asset_type="option",expiration=__import__('datetime').date(2026,10,16),strike=10,right="CALL")):
            order=Order("synthetic",asset,1,"buy",order_type="limit",limit_price=10,time_in_force="day",
                        quote=Asset("USD",asset_type="forex"))
            with self.assertRaisesRegex(GuardRefusal,"^stock_only$"):broker._submit_order(order)
        for tif in ("gtc","ioc","fok","opg","cls"):
            order=Order("synthetic",Asset("SYN"),1,"buy",order_type="limit",limit_price=10,time_in_force=tif)
            with self.assertRaisesRegex(GuardRefusal,"^time_in_force$"):broker._submit_order(order)
        for klass in ("bracket","oco","oto"):
            order=Order("synthetic",Asset("SYN"),1,"buy",order_type="limit",limit_price=10,
                        time_in_force="day")
            order.order_class=klass
            with self.assertRaisesRegex(GuardRefusal,"^order_type$"):broker._submit_order(order)
        order=Order("synthetic",Asset("SYN"),D(".5"),"buy",order_type="limit",limit_price=10,time_in_force="day")
        with self.assertRaisesRegex(GuardRefusal,"^quantity$"):broker._submit_order(order)
        with self.assertRaisesRegex(GuardRefusal,"^api_replacement$"):broker.api=self.sdk
        with self.assertRaisesRegex(GuardRefusal,"^client_recreation$"):broker._create_trading_client()
        self.assertFalse(self.sdk.writes)

    def test_A5_no_original_client_or_credential_plain_attributes(self):
        broker=self.make_broker()
        self.assertFalse(any(value is self.sdk for value in vars(broker).values()))
        for name in ("api_key","api_secret","oauth_token"):self.assertFalse(getattr(broker,name))
        self.assertIsInstance(broker.api,GuardedApi)

    def test_A5_actual_sdk_constructor_resolves_paper_without_any_request(self):
        from alpaca.trading.client import TradingClient
        client=TradingClient("synthetic-placeholder","synthetic-placeholder",paper=True)
        base=getattr(client._base_url,"value",client._base_url)
        self.assertEqual(base,"https://paper-api.alpaca.markets")
        proxy=GuardedApi(client,self.gov,lambda:NOW)
        self.assertIsInstance(proxy,GuardedApi)

    def test_A1_closed_inbox_native_strategy_routes_only_governor_decision(self):
        broker=self.make_broker();_,Strategy=load_classes()
        inbox=self.root/"inbox.jsonl"
        inbox.write_text('{"symbol":"SYN","side":"buy","sizing":"entry"}\n')
        # The real vendor class is used; avoid its unrelated setup/account
        # queries by exercising the committed initialized lifecycle directly.
        strategy=Strategy.__new__(Strategy);strategy.broker=broker
        strategy.initialize(inbox=inbox,governor=self.gov,
                            snapshot=lambda symbol:(self.quote,self.account),clock=lambda:NOW)
        strategy.on_trading_iteration()
        self.assertEqual(self.sdk.writes[-1][1]["qty"],"20")
        with self.assertRaisesRegex(GuardRefusal,"^agent_runtime$"):strategy.agents
        self.assertIsNone(strategy.on_trading_iteration())

    def test_A7_audit_guard_blocks_second_sdk_and_secret_open(self):
        import sitecustomize
        if not getattr(sitecustomize,"ACTIVE",False):self.skipTest("acceptance offline process required")
        with self.assertRaisesRegex(RuntimeError,"ENGINE_QUAL_NETWORK_DENIED"):
            socket.getaddrinfo("localhost",443)
        with self.assertRaisesRegex(RuntimeError,"ENGINE_QUAL_CREDENTIAL_FILE_DENIED"):
            open(self.root/".env","rb")
        from alpaca.trading.client import TradingClient
        client=TradingClient("synthetic-placeholder","synthetic-placeholder",paper=True)
        with self.assertRaises(RuntimeError):client.get_account()


def load_tests(loader, tests, pattern):
    suite=unittest.TestSuite()
    for cls in (SeamCI,NativeCase):
        suite.addTests(cls(name) for name in vars(cls) if name.startswith("test_"))
    return suite


if __name__=="__main__":unittest.main()
