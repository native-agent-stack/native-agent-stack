"""A1-A8 hermetic shared-core/proxy checks; stdlib CI, fabricated values only."""
import ast
from dataclasses import replace
from decimal import Decimal as D
import gc
import importlib
import json
import os
from pathlib import Path
import random
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
CODE = Path(os.environ.get("ENGINE_LUMIBOT_ROOT", ROOT / "blueprints/us-equities/engine-lumibot"))
sys.path.insert(0, str(CODE))
from governor import (AccountState, Decision, Governor, GuardRefusal, Intent, Journal,
                      QuoteSnapshot, Refusal, dec, encode, rounded)
import governor as governor_module
from guarded_api import GuardedApi

NOW = 100_000_000_000


class OrderData:
    def __init__(self, **kwargs): self.__dict__.update(kwargs)
    def to_request_fields(self): return self.__dict__


class FakeSDK:
    _base_url = "https://paper-api.alpaca.markets"
    _retry = 3
    def __init__(self): self.writes, self.reads = [], []
    def submit_order(self, *, order_data):
        self.writes.append(("submit", dict(vars(order_data))))
        return SimpleNamespace(id="synthetic-order", status="new")
    def cancel_order_by_id(self, key): self.writes.append(("cancel", key))
    def get_account(self): self.reads.append("account"); return SimpleNamespace()
    def get_clock(self): self.reads.append("clock"); return SimpleNamespace()
    def get(self, path): self.reads.append(path); return {}


class CoreCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="lumibot-accept-", dir="/var/tmp")
        self.root = Path(self.temp.name)
        self.journal = Journal(self.root / "journal.jsonl")
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(lambda: self.journal.close())
        self.gov = Governor(CODE / "caps-a6-diagnostic.json", self.journal)
        self.sdk = FakeSDK()
        self.api = GuardedApi(self.sdk, self.gov, lambda: NOW)
        self.intent = Intent("SYN", "buy")
        self.quote = QuoteSnapshot(D("9.99"), D("10"), NOW, NOW, "RTH", NOW)
        self.account = AccountState(D("1000"), {})

    def decision(self, **kwargs):
        result = self.gov.decide(kwargs.get("intent", self.intent), kwargs.get("quote", self.quote),
                                 kwargs.get("account", self.account), kwargs.get("now", NOW))
        self.assertIsInstance(result, Decision)
        return result

    def refuse(self, code, **kwargs):
        result = self.gov.decide(kwargs.get("intent", self.intent), kwargs.get("quote", self.quote),
                                 kwargs.get("account", self.account), kwargs.get("now", NOW))
        self.assertEqual(result, Refusal(code))
        self.assertFalse(self.sdk.writes)
        self.assertTrue(self.journal.rows,"A refusal must be journaled")
        self.assertEqual(self.journal.rows[-1]["reason"], code)

    def test_A1_payload_equals_decision_and_one_use(self):
        decision = self.decision()
        self.api.submit_order(order_data=OrderData(**decision.payload()))
        self.assertEqual(self.sdk.writes, [("submit", decision.payload())])
        with self.assertRaisesRegex(GuardRefusal, "^reservation$"):
            self.api.submit_order(order_data=OrderData(**decision.payload()))
        self.assertEqual(len(self.sdk.writes), 1)

    def test_A1_native_missing_fields_bridge(self):
        decision = self.decision(); self.api.bind(decision)
        payload = decision.payload(); payload.pop("extended_hours"); payload.pop("client_order_id")
        payload["limit_price"] = "10.0"
        self.api.submit_order(order_data=OrderData(**payload))
        self.assertEqual(self.sdk.writes[0][1], decision.payload())

    def test_A1_all_sessions(self):
        for session in ("PRE", "RTH", "POST", "OVERNIGHT"):
            with self.subTest(session=session):
                decision = self.decision(quote=replace(self.quote, session=session))
                self.api.submit_order(order_data=OrderData(**decision.payload()))
                self.assertIs(self.sdk.writes[-1][1]["extended_hours"], session != "RTH")
                self.gov.reconcile(decision.client_order_id, terminal="filled", account=self.account)

    def test_A2_assets_and_closed_intent(self):
        for kind in ("option", "crypto", "future", "multileg"):
            self.refuse("stock_only", intent=replace(self.intent, asset_type=kind))
        for side in ("sell_short", "buy_to_cover", "buy_to_open", "sell_to_close"):
            self.refuse("intent", intent=replace(self.intent, side=side))
            self.refuse("intent", intent=replace(self.intent, side=side, sizing="exit_all"))
        self.refuse("intent", intent=replace(self.intent, sizing="quantity"))
        self.refuse("stock_only", intent=replace(self.intent, symbol="BAD/PAIR"))

    def test_A2_quote_clocks_and_session(self):
        self.refuse("session", quote=replace(self.quote, session="CLOSED"))
        self.refuse("clock", quote=replace(self.quote, clock_ns=NOW-250_000_001))
        self.refuse("clock", quote=replace(self.quote, clock_ns=NOW+1))
        self.refuse("stale_quote", quote=replace(self.quote, quote_ns=NOW-60_000_000_001))
        self.refuse("stale_trade", quote=replace(self.quote, trade_ns=NOW-120_000_000_001))
        self.refuse("stale_quote", quote=replace(self.quote, quote_ns=NOW+1))

    def test_A2_caps_account_and_short_refusals(self):
        self.refuse("account_reconciliation", account=replace(self.account, reconciled=False))
        self.refuse("account_reconciliation", account=replace(self.account, open_orders=("pending",)))
        self.refuse("ask_band", quote=replace(self.quote, bid=D("4.99"), ask=D("5")-D(".001")))
        self.refuse("ask_band", quote=replace(self.quote, ask=D("201")))
        self.refuse("spread", quote=replace(self.quote, bid=D("9")))
        self.refuse("quote_account", quote=replace(self.quote, bid=D("11")))
        self.refuse("quote_account", account=replace(self.account, equity=D("0")))
        self.refuse("name_cap", account=replace(self.account, positions={"X":1,"Y":1}))
        self.refuse("existing_position", account=replace(self.account, positions={"SYN":1}))
        self.refuse("position", account=replace(self.account, positions={"X":D(".5")}))
        self.refuse("position", account=replace(self.account, positions={"X":-1}))
        self.refuse("quantity", account=replace(self.account, equity=D("1")))
        self.refuse("quantity", intent=Intent("SYN","sell","exit_all"))
        result=self.gov.decide(Intent("SYN","sell","exit_all"),self.quote,
                               replace(self.account,positions={"SYN":21}),NOW)
        self.assertIsInstance(result,Decision);self.assertEqual(result.qty,21)

    def test_A2_payload_refusals_exact(self):
        decision = self.decision()
        cases = [("type", x, "order_type") for x in ("market","stop","stop_limit","trailing_stop","smart_limit")]
        cases += [("time_in_force", x, "time_in_force") for x in ("gtc","ioc","fok","opg","cls")]
        cases += [("side", x, "side") for x in ("sell_short","buy_to_cover")]
        cases += [("qty", x, "quantity") for x in ("0","-1","1.5",1,True,"01")]
        cases += [("symbol","ZZZZ","reservation"),("qty","7","reservation"),("side","sell","reservation")]
        cases += [("limit_price", "10.01", "price_equality"),
                  ("extended_hours", True, "session_flag"),
                  ("extended_hours", "false", "session_flag"),
                  ("client_order_id", "unknown", "reservation")]
        for key, value, reason in cases:
            with self.subTest(key=key,value=value):
                payload = decision.payload(); payload[key] = value
                with self.assertRaisesRegex(GuardRefusal, "^"+reason+"$"):
                    self.api.submit_order(order_data=OrderData(**payload))
        for key in ("custom_params", "order_class", "legs", "stop_price"):
            payload = dict(decision.payload(), **{key: "forbidden"})
            with self.assertRaisesRegex(GuardRefusal, "^payload_keys$"):
                self.api.submit_order(order_data=OrderData(**payload))
        self.assertFalse(self.sdk.writes)

    def test_A2_proxy_capabilities_and_cancel_ownership(self):
        denied = ("post","put","patch","delete","_request","_session","_client","_api",
                  "replace_order_by_id","cancel_orders","close_position","close_all_positions",
                  "exercise_options_position","set_account_configurations","create_watchlist",
                  "update_watchlist_by_id","delete_watchlist_by_id")
        for name in denied:
            with self.subTest(name=name), self.assertRaisesRegex(GuardRefusal,"^api_capability$"):
                getattr(self.api, name)
        with self.assertRaisesRegex(GuardRefusal,"^api_capability$"):
            self.api.submit_order = lambda **kw: None
        with self.assertRaisesRegex(GuardRefusal,"^cancel_ownership$"):
            self.api.cancel_order_by_id("unowned")
        self.assertFalse(self.sdk.writes)

    def test_A2_owned_cancel_and_mediated_read(self):
        decision=self.decision(); self.api.submit_order(order_data=OrderData(**decision.payload()))
        self.api.cancel_order_by_id("synthetic-order")
        self.assertEqual(self.sdk.writes[-1],("cancel","synthetic-order"))
        self.api.get_clock(); self.api.get("/clock")
        for path in ("https://untrusted.invalid/", "/orders/../account/configurations"):
            with self.assertRaisesRegex(GuardRefusal,"^read_path$"): self.api.get(path)
        with self.assertRaisesRegex(GuardRefusal,"^read_path$"):
            self.api.get_account(base_url="https://untrusted.invalid")

    def test_A2_rate_budget_request_and_submit(self):
        self.gov.requests=[NOW]*197
        with self.assertRaisesRegex(GuardRefusal,"^request_budget$"): self.api.get_clock()
        self.gov.requests=[]; self.gov.submits=[NOW]*177
        decision=self.decision()
        with self.assertRaisesRegex(GuardRefusal,"^request_budget$"):
            self.api.submit_order(order_data=OrderData(**decision.payload()))
        self.assertFalse(self.sdk.writes)

    def test_A2_collar_uses_rounded_final_price(self):
        # A narrow registered collar is an injected-data test, not live config.
        self.gov.caps["collar"]["regular_bps"]=D("0.1")
        self.refuse("collar")

    def test_A3_seeded_model_numbers_never_change_size_or_price(self):
        # Durability is exercised against real fsync in A6. This 500-case
        # numerical sweep keeps actual append bytes but avoids 2000 disk flushes.
        flush=patch("governor.os.fsync"); flush.start(); self.addCleanup(flush.stop)
        rng=random.Random(260413); expected=None
        for index in range(500):
            hints={"qty":rng.uniform(-1e9,1e9),"limit_price":rng.random(),
                   "secret_hint":"never-journal-this", "nested":[float("nan"),None]}
            decision=self.decision(intent=replace(self.intent, model_hints=hints))
            if expected is None: expected=(decision.qty,decision.limit_price)
            self.assertEqual((decision.qty,decision.limit_price),expected)
            self.api.submit_order(order_data=OrderData(**decision.payload()))
            self.assertEqual((self.sdk.writes[-1][1]["qty"],D(self.sdk.writes[-1][1]["limit_price"])),
                             (str(expected[0]),expected[1]))
            self.gov.reconcile(decision.client_order_id,terminal="filled",account=self.account)
            # Advance the injected clock rather than reset the counters.
            self.gov.requests.clear(); self.gov.submits.clear()
        self.assertNotIn("never-journal-this",self.journal.path.read_text())

    def test_A4_directional_rounding_boundary_and_whole_floor(self):
        for price,buy,sell in [("1.009","1.00","1.01"),("0.99999","0.9999","1.0000"),
                               ("0.00019","0.0001","0.0002")]:
            self.assertEqual(rounded(D(price),"buy"),D(buy))
            self.assertEqual(rounded(D(price),"sell"),D(sell))
        decision=self.decision(quote=replace(self.quote,bid=D("5.98"),ask=D("5.999")))
        self.assertEqual(decision.qty,33); self.assertEqual(decision.limit_price,D("5.99"))
        self.assertLessEqual(decision.qty*decision.limit_price,D("200"))

    def test_A5_caps_and_journal_fail_closed(self):
        with self.assertRaisesRegex(GuardRefusal,"^caps$"):
            Governor(None,self.journal)
        caps=json.loads((CODE/"caps-a6-diagnostic.json").read_text())
        for key in caps:
            broken=dict(caps); del broken[key]; p=self.root/"bad-caps.json";p.write_bytes(encode(broken))
            with self.subTest(key=key), self.assertRaisesRegex(GuardRefusal,"^caps$"):
                Governor(p,self.journal)
        with self.assertRaisesRegex(GuardRefusal,"^journal$"): Journal(self.root)
        with self.assertRaisesRegex(GuardRefusal,"^journal$"): Journal(self.journal.path)
        for key,value in [("max_names",0),("whole_shares",False),("short_sales",True),
                          ("max_notional_usd_per_name","NaN"),("max_spread_bps","-1"),
                          ("collar",None),("collar",[]),("sessions",None),
                          ("sessions",{"PRE":1,"RTH":False,"POST":True,"OVERNIGHT":True})]:
            broken=dict(caps);broken[key]=value;p=self.root/"bad-caps.json";p.write_bytes(encode(broken))
            with self.subTest(key=key),self.assertRaisesRegex(GuardRefusal,"^caps$"):
                Governor(p,self.journal)

    def test_A5_no_plain_client_attribute(self):
        for name in ("client","_client","real_client","_api","api","__dict__"):
            with self.assertRaises(GuardRefusal): getattr(self.api,name)
        self.assertNotIn(self.sdk,[x for x in gc.get_referents(self.api) if not callable(x)])

    def test_A5_proxy_paper_url_and_retry_cap_independently(self):
        self.sdk._base_url="https://api.alpaca.markets"
        with self.assertRaisesRegex(GuardRefusal,"^paper_url$"):
            GuardedApi(self.sdk,self.gov,lambda:NOW)
        self.sdk._base_url="https://paper-api.alpaca.markets"
        self.sdk._retry=4
        with self.assertRaisesRegex(GuardRefusal,"^retry_cap$"):
            GuardedApi(self.sdk,self.gov,lambda:NOW)

    def test_A2_decision_reservation_expires_before_transport(self):
        late=GuardedApi(self.sdk,self.gov,lambda:NOW+60_000_000_001)
        decision=self.decision()
        with self.assertRaisesRegex(GuardRefusal,"^reservation_expired$"):
            late.submit_order(order_data=OrderData(**decision.payload()))
        self.assertFalse(self.sdk.writes)

    def test_A6_hash_chain_unknown_restart_and_no_retry(self):
        decision=self.decision()
        def unknown(**kwargs): raise RuntimeError("private upstream detail")
        self.sdk.submit_order=unknown
        with self.assertRaisesRegex(GuardRefusal,"^unknown_outcome$"):
            self.api.submit_order(order_data=OrderData(**decision.payload()))
        self.refuse("reconciliation_required")
        before=self.journal.path.read_bytes(); self.journal.close()
        self.journal=Journal(self.root/"journal.jsonl")
        self.gov=Governor(CODE/"caps-a6-diagnostic.json",self.journal)
        self.refuse("reconciliation_required")
        self.assertTrue(self.journal.path.read_bytes().startswith(before))
        self.gov.reconcile(decision.client_order_id,terminal="not_sent",account=self.account)
        self.assertIsInstance(self.gov.decide(self.intent,self.quote,self.account,NOW),Decision)
        self.assertNotIn("private upstream detail",self.journal.path.read_text())

    def test_A6_tampered_chain_refuses(self):
        self.gov.refuse("synthetic"); self.journal.close()
        self.journal.path.write_bytes(b'{"previous":"broken"}\n')
        with self.assertRaisesRegex(GuardRefusal,"^journal$"): Journal(self.journal.path)
        self.journal=Journal(self.root/"replacement.jsonl")

    def test_A6_journal_before_sdk_and_all_decisions_refusals(self):
        sync=patch("governor.os.fsync", wraps=os.fsync)
        fsync=sync.start();self.addCleanup(sync.stop)
        self.refuse("intent",intent=replace(self.intent,side="bad"))
        decision=self.decision()
        def observed(*,order_data):
            self.assertEqual(self.journal.rows[-1]["event"],"submit")
            self.assertIn(decision.client_order_id,self.journal.path.read_text())
            self.assertGreaterEqual(fsync.call_count,4)
            return SimpleNamespace(id="synthetic-order")
        self.sdk.submit_order=observed
        try:self.api.submit_order(order_data=OrderData(**decision.payload()))
        except GuardRefusal as error:self.fail("Durable pre-submit observations must permit SDK success: "+str(error))
        self.assertTrue(all(x["caps_sha256"]==self.gov.caps_hash for x in self.journal.rows))
        self.assertEqual(self.journal.rows[-1]["outcome"],"accepted_response")

    def test_A6_restart_caps_binding_and_budget_not_reset(self):
        self.gov.budget(NOW,submit=True,units=4)
        self.journal.close();self.journal=Journal(self.root/"journal.jsonl")
        gov=Governor(CODE/"caps-a6-diagnostic.json",self.journal)
        self.assertEqual(len(gov.requests),4);self.assertEqual(len(gov.submits),4)
        with self.assertRaisesRegex(GuardRefusal,"^clock$"):gov.budget(NOW-1)
        path=self.root/"changed-caps.json"
        caps=json.loads((CODE/"caps-a6-diagnostic.json").read_text());caps["max_names"]=1
        path.write_bytes(encode(caps))
        with self.assertRaisesRegex(GuardRefusal,"^journal_caps_binding$"):Governor(path,self.journal)

    def test_A8_inventory_every_row_has_named_enforcement(self):
        inventory=json.loads((CODE/"write-boundaries.json").read_text())
        expected={*["S"+str(x) for x in range(1,10)],"X1","C1",
                  *["G"+str(x) for x in range(1,5)],*["B"+str(x) for x in range(1,8)],
                  *["A"+str(x) for x in range(1,6)],*["K"+str(x) for x in range(1,6)]}
        self.assertEqual({row["id"] for row in inventory["boundaries"]},expected)
        for row in inventory["boundaries"]:
            self.assertIn(row["layer"],("L0","L1","L2","process")); self.assertTrue(row["test"])


class ReviewerAdditions(CoreCase):
    """R1-R12 from the authenticated trading-cc proposal, with exact codes."""
    def submit(self, decision):
        self.api.submit_order(order_data=OrderData(**decision.payload()))

    def test_R1_journal_write_failure_refuses_and_nothing_is_admitted(self):
        with patch.object(governor_module.os,"write",side_effect=OSError("disk full")):
            with self.assertRaisesRegex(GuardRefusal,"^journal_write$"):
                self.gov.decide(self.intent,self.quote,self.account,NOW)
        self.assertEqual(self.gov.reservations,{})
        self.assertFalse(self.sdk.writes)

    def test_R2_second_decision_waits_for_the_first_outcome_to_be_reconciled(self):
        first=self.decision();self.submit(first)
        self.assertEqual(self.gov.decide(Intent("OTHER","buy"),self.quote,self.account,NOW),Refusal("pending_outcome"))
        self.gov.reconcile(first.client_order_id,terminal="filled",account=self.account)
        self.assertIsInstance(self.gov.decide(Intent("OTHER","buy"),self.quote,self.account,NOW),Decision)

    def test_R3_reconcile_needs_terminal_reconciled_account_and_known_order(self):
        decision=self.decision();self.submit(decision);cid=decision.client_order_id
        for terminal,account,key in [("bogus",self.account,cid),("filled",replace(self.account,reconciled=False),cid),
                                     ("filled",replace(self.account,open_orders=(cid,)),cid),
                                     ("filled",self.account,"a6-unknown")]:
            with self.subTest(terminal=terminal,known=key==cid),self.assertRaisesRegex(GuardRefusal,"^reconciliation_required$"):
                self.gov.reconcile(key,terminal=terminal,account=account)
        self.assertIn(cid,self.gov.outstanding)
        # CC ruling 2026-10-13 12:30Z (c): an UNKNOWN open order (no arm prefix, not in the journal) never blocks the reconcile of our own order
        self.gov.reconcile(cid,terminal="filled",account=replace(self.account,open_orders=("working",)))
        self.assertNotIn(cid,self.gov.outstanding)

    def test_R4_dec_refuses_float_bool_none_text_and_non_finite(self):
        for bad in (1.5,True,None,"abc","NaN","Infinity","-Infinity",[1]):
            with self.subTest(bad=repr(bad)),self.assertRaisesRegex(GuardRefusal,"^number$"):dec(bad)

    def test_R5_journal_group_world_permissions_refuse(self):
        loose=self.root/"loose.jsonl";loose.write_bytes(b"");os.chmod(loose,0o644)
        with self.assertRaisesRegex(GuardRefusal,"^journal$"):Journal(loose)

    def test_R6_exit_above_entry_cap_admitted(self):
        for bid,ask in [("10.04","10.05"),("10.40","10.41"),("11.00","11.01")]:
            with self.subTest(bid=bid):
                result=self.gov.decide(Intent("SYN","sell","exit_all"),replace(self.quote,bid=D(bid),ask=D(ask)),
                                       replace(self.account,positions={"SYN":20}),NOW)
                self.assertIsInstance(result,Decision)
                self.gov.reconcile(result.client_order_id,terminal="not_sent",account=self.account)

    def test_R7_failed_cancel_unknown_outcome_blocks_admission(self):
        decision=self.decision();self.submit(decision)
        def broken(key):raise RuntimeError("network")
        self.sdk.cancel_order_by_id=broken
        try:self.api.cancel_order_by_id("synthetic-order")
        except Exception as error:
            self.assertIsInstance(error,GuardRefusal)
            self.assertEqual(str(error),"unknown_outcome")
        else:self.fail("Failed cancel must produce an unknown-outcome refusal")
        self.assertTrue(self.gov.recovery_required)
        self.assertEqual(self.journal.rows[-1]["outcome"],"unknown")

    def test_R8_session_flag_is_actual_bool(self):
        decision=self.decision()
        with self.assertRaisesRegex(GuardRefusal,"^session_flag$"):
            self.api.submit_order(order_data=OrderData(**dict(decision.payload(),extended_hours=0)))
        self.assertFalse(self.sdk.writes)

    def test_R9_refused_native_bridge_does_not_wedge_later_submits(self):
        def native(decision):
            row=decision.payload();row.pop("extended_hours");row.pop("client_order_id");return row
        first=self.decision();self.api.bind(first);self.gov.requests=[NOW]*197
        with self.assertRaisesRegex(GuardRefusal,"^request_budget$"):
            self.api.submit_order(order_data=OrderData(**native(first)))
        self.gov.requests=[];self.gov.reconcile(first.client_order_id,terminal="not_sent",account=self.account)
        second=self.decision();self.api.bind(second)
        self.api.submit_order(order_data=OrderData(**native(second)))
        self.assertEqual(len(self.sdk.writes),1)

    def test_R10_sdk_serialization_cannot_add_foreign_class_fields(self):
        sent=[]
        class Sneaky(OrderData):
            def to_request_fields(self):return dict(self.__dict__,order_class="bracket",take_profit={"limit_price":1.0})
        self.sdk.submit_order=lambda *,order_data:(sent.append(order_data.to_request_fields()),SimpleNamespace(id="synthetic-order"))[1]
        decision=self.decision()
        try:self.api.submit_order(order_data=Sneaky(**decision.payload()))
        except GuardRefusal:return
        self.assertEqual(sent,[decision.payload()])

    def test_R11_symlinked_inbox_refused(self):
        from stock_only_alpaca import read_inbox
        target=self.root/"real-inbox.jsonl";target.write_text('{"symbol":"SYN","side":"buy","sizing":"entry"}\n')
        link=self.root/"inbox-link.jsonl";link.symlink_to(target)
        with self.assertRaisesRegex(GuardRefusal,"^inbox$"):read_inbox(link)

    def test_R12_nonhermetic_environment_refused(self):
        from stock_only_alpaca import load_classes
        from types import ModuleType
        package=ModuleType("lumibot");package.__path__=[]
        brokers=ModuleType("lumibot.brokers");brokers.Alpaca=object
        strategies=ModuleType("lumibot.strategies");strategies.Strategy=object
        entities=ModuleType("lumibot.entities");entities.Order=object;entities.Asset=object
        with patch.dict(sys.modules,{"lumibot":package,"lumibot.brokers":brokers,
                                     "lumibot.strategies":strategies,"lumibot.entities":entities}), \
             patch.dict(os.environ,{"LUMIBOT_TELEMETRY":"1"}):
            with self.assertRaisesRegex(GuardRefusal,"^environment$"):load_classes()


class Lying(str):
    def __eq__(self, other):
        return True

    def __ne__(self, other):
        return False

    __hash__ = str.__hash__


HERMETIC = {"LUMIBOT_DISABLE_DOTENV": "1", "LUMIBOT_DISABLE_DOTENV_LOCAL": "1", "LUMIBOT_LAZY_CREDENTIALS": "1",
            "LUMIBOT_CONNECT_STREAM": "false", "LUMIBOT_START_ORDERS_THREAD": "false", "LUMIBOT_TELEMETRY": "0"}
OVERRIDES = ("LUMIBOT_STRATEGY_PARAMETERS", "BACKTESTING_PARAMETERS", "LUMIWEALTH_API_KEY", "DISCORD_WEBHOOK_URL", "LISTENER_WRITE_URL")


class RestageAdditions(CoreCase):
    def test_R13_str_subclass_values_never_reach_the_sdk_or_the_journal(self):
        """Either outcome is acceptable (a refusal, or an admission that sends the reservation's own text); a forged value in the body or in the journal is not."""
        for field, forged in (("symbol", "ZZZZ"), ("qty", "999"), ("side", "sell"), ("type", "market"), ("time_in_force", "gtc"), ("client_order_id", "a6-FORGED")):
            with self.subTest(field=field):
                decision = self.decision()
                payload = decision.payload()
                if field == "client_order_id":
                    token_hash = hash(decision.client_order_id)

                    class LyingId(Lying):
                        def __hash__(self):
                            return token_hash
                    payload[field] = LyingId(forged)
                else:
                    payload[field] = Lying(forged)
                before = len(self.sdk.writes)
                try:
                    self.api.submit_order(order_data=OrderData(**payload))
                except GuardRefusal:
                    pass
                for _, body in self.sdk.writes[before:]:
                    self.assertEqual(json.dumps(body, sort_keys=True), json.dumps(decision.payload(), sort_keys=True), "the body must be the reservation's own text")
                self.assertNotIn(forged, json.dumps(self.journal.rows, default=str), "the forged text must not be journaled either")
                try:
                    self.gov.reconcile(decision.client_order_id, terminal="not_sent", account=self.account)
                except GuardRefusal:
                    pass

    def test_R13b_the_admitted_body_holds_only_plain_values_equal_to_the_reservation(self):
        decision = self.decision()
        self.api.submit_order(order_data=OrderData(**decision.payload()))
        body = self.sdk.writes[-1][1]
        self.assertEqual({key: type(value) for key, value in body.items()},
                         {"symbol": str, "qty": str, "side": str, "type": str, "time_in_force": str, "limit_price": str, "extended_hours": bool, "client_order_id": str})
        self.assertEqual(json.dumps(body, sort_keys=True), json.dumps(decision.payload(), sort_keys=True))

    def test_R14_environment_overrides_of_the_real_constructor_refuse(self):
        from stock_only_alpaca import load_classes
        package = ModuleType("lumibot"); package.__path__ = []
        brokers = ModuleType("lumibot.brokers"); brokers.Alpaca = object
        strategies = ModuleType("lumibot.strategies"); strategies.Strategy = object
        entities = ModuleType("lumibot.entities"); entities.Order = object; entities.Asset = object
        stubs = {"lumibot": package, "lumibot.brokers": brokers, "lumibot.strategies": strategies, "lumibot.entities": entities}
        for name in OVERRIDES:
            with self.subTest(variable=name), patch.dict(sys.modules, stubs), patch.dict(os.environ, {**HERMETIC, name: "x"}):
                with self.assertRaisesRegex(GuardRefusal, "^environment$"):
                    load_classes()
        with self.subTest(control="hermetic environment without any override"), patch.dict(sys.modules, stubs), patch.dict(os.environ, HERMETIC):
            for name in OVERRIDES:
                os.environ.pop(name, None)
            try:
                load_classes()
            except GuardRefusal as error:
                self.fail(f"the control must not be refused: {error}")
            except Exception:
                pass      # the stubs are too thin to build the classes; only the environment gate is under test

    # ---------------------------------------------------------------- the CC's exit rulings
    def exit_quote(self, **changes):
        return replace(self.quote, bid=D("10.04"), ask=D("10.05"), **changes)

    def sell(self, positions, quote=None, now=NOW):
        return self.gov.decide(Intent("SYN", "sell", "exit_all"), quote or self.exit_quote(), replace(self.account, positions=positions), now)

    def test_E5_an_exit_needs_a_fresh_quote_not_a_recent_trade(self):
        for session in ("RTH", "PRE", "POST", "OVERNIGHT"):
            for age_s in (121, 600, 3600):
                with self.subTest(session=session, last_trade_age_s=age_s):
                    result = self.sell({"SYN": 20}, self.exit_quote(session=session, trade_ns=NOW - age_s * 10**9))
                    self.assertIsInstance(result, Decision, result)
                    self.assertEqual((result.side, result.qty, result.limit_price), ("sell", 20, D("10.04")))
                    self.gov.reconcile(result.client_order_id, terminal="not_sent", account=self.account)
        # controls: a stale QUOTE still refuses an exit; an entry still needs a recent trade
        self.refuse("stale_quote", intent=Intent("SYN", "sell", "exit_all"), quote=self.exit_quote(quote_ns=NOW - 61 * 10**9), account=replace(self.account, positions={"SYN": 20}))
        self.refuse("stale_trade", quote=replace(self.quote, trade_ns=NOW - 121 * 10**9))

    def test_E5b_an_exits_reservation_deadline_comes_from_the_quote(self):
        old_print = self.exit_quote(trade_ns=NOW - 3600 * 10**9)
        first = self.sell({"SYN": 20}, old_print)
        self.assertIsInstance(first, Decision, first)
        self.assertEqual(self.gov.deadlines[first.client_order_id], NOW + 60 * 10**9)
        self.gov.consume(first.payload(), first.client_order_id, NOW + 60 * 10**9)      # exactly at the quote's deadline: allowed
        self.gov.reconcile(first.client_order_id, terminal="filled", account=self.account)
        second = self.sell({"SYN": 20}, replace(old_print,clock_ns=NOW + 60*10**9), now=NOW + 60*10**9)
        self.assertIsInstance(second, Decision, second)
        with self.assertRaisesRegex(GuardRefusal, "^reservation_expired$"):
            self.gov.consume(second.payload(), second.client_order_id, NOW + 60 * 10**9 + 2)

    def test_E6_an_exit_needs_an_integral_quantity_only_for_its_own_symbol(self):
        result = self.sell({"SYN": 20, "OTHER": D("0.5")})
        self.assertIsInstance(result, Decision, result)
        self.assertEqual(result.qty, 20)
        self.gov.reconcile(result.client_order_id, terminal="not_sent", account=self.account)
        self.refuse("position", intent=Intent("SYN", "sell", "exit_all"), quote=self.exit_quote(), account=replace(self.account, positions={"SYN": D("20.5")}))
        self.refuse("position", quote=self.quote, account=replace(self.account, positions={"OTHER": D("0.5")}))      # an entry keeps the account-wide check

    def restarted(self, listed):
        """Close the journal, reopen it as a new process would, and build a new Governor and a new proxy over an SDK that lists `listed` as open orders."""
        self.journal.close()
        self.journal = Journal(self.root / "journal.jsonl")
        governor = Governor(CODE / "caps-a6-diagnostic.json", self.journal)
        sdk = FakeSDK()
        sdk.get_orders = lambda *args, **kwargs: list(listed)
        return governor, sdk

    def test_E7_after_a_restart_the_old_working_order_can_be_cancelled_and_the_exit_proceeds(self):
        decision = self.decision()
        self.api.submit_order(order_data=OrderData(**decision.payload()))
        cid = decision.client_order_id
        later = NOW + 5 * 10**9
        governor, sdk = self.restarted([{"id": "synthetic-order", "client_order_id": cid, "status": "new"},
                                        {"id": "foreign-9", "client_order_id": "manual-1", "status": "new"},
                                        {"id": "spoof-3", "client_order_id": "a6-000000000999", "status": "new"}])
        self.assertTrue(governor.recovery_required)
        self.assertIn(cid, governor.outstanding)
        api = GuardedApi(sdk, governor, lambda: later)
        for foreign in ("foreign-9", "spoof-3", "never-listed"):
            with self.subTest(order=foreign), self.assertRaisesRegex(GuardRefusal, "^cancel_ownership$"):
                api.cancel_order_by_id(foreign)      # not in the journal: never ours to cancel
        api.cancel_order_by_id("synthetic-order")      # re-derived from the journal and the broker's open orders
        self.assertEqual(sdk.writes[-1], ("cancel", "synthetic-order"))
        account = AccountState(D("1000"), {"SYN": 20}, ("manual-1",), True)      # the foreign order is still open
        self.assertTrue(governor.is_ours(cid))
        self.assertFalse(governor.is_ours("manual-1"))
        try:
            governor.reconcile(cid, terminal="canceled", account=account)
        except GuardRefusal as error:
            self.fail(f"an unknown order must not block reconciliation: {error}")
        self.assertFalse(governor.recovery_required)
        quote = QuoteSnapshot(D("10.04"), D("10.05"), later, later, "RTH", later)
        exit_result = governor.decide(Intent("SYN", "sell", "exit_all"), quote, account, later)
        self.assertIsInstance(exit_result, Decision, exit_result)
        self.assertEqual((exit_result.side, exit_result.qty), ("sell", 20))
        governor.reconcile(exit_result.client_order_id, terminal="not_sent", account=account)
        self.assertEqual(governor.decide(Intent("SYN", "buy"), QuoteSnapshot(D("9.99"), D("10"), later, later, "RTH", later), replace(account, positions={}), later),
                         Refusal("account_reconciliation"))      # an unknown open order still refuses an ENTRY

    def test_E7b_an_unreadable_order_list_after_a_restart_fails_closed(self):
        decision = self.decision()
        self.api.submit_order(order_data=OrderData(**decision.payload()))
        governor, sdk = self.restarted([])

        def unreadable(*args, **kwargs):
            raise RuntimeError("network")
        sdk.get_orders = unreadable
        try:
            GuardedApi(sdk, governor, lambda: NOW + 5 * 10**9)
        except Exception as error:
            self.assertIs(type(error), GuardRefusal)
            self.assertEqual(str(error), "restart_orders_unreadable")
        else:
            self.fail("an unreadable restart order list must refuse")

    def test_E7c_open_order_ownership_requires_both_prefix_and_journal_submission(self):
        decision = self.decision()
        self.api.submit_order(order_data=OrderData(**decision.payload()))
        # Synthetic legacy submit: the journal alone is insufficient without
        # the current arm prefix. A prefix alone is insufficient too.
        legacy = "manual-1"
        self.gov.record("submit", client_order_id=legacy,
                        payload=dict(decision.payload(), client_order_id=legacy))
        self.gov.submitted.add(legacy)
        self.sdk.get_orders = lambda: [
            {"id": "legacy-order", "client_order_id": legacy},
            {"id": "lookalike-order", "client_order_id": "a6-unlisted"},
            {"id": "synthetic-order", "client_order_id": decision.client_order_id}]
        api = GuardedApi(self.sdk, self.gov, lambda: NOW)
        for entry in (legacy, {"client_order_id": legacy},
                      SimpleNamespace(client_order_id=legacy), "a6-unlisted"):
            with self.subTest(entry=type(entry).__name__):
                self.assertFalse(self.gov.is_ours(entry))
        self.assertTrue(self.gov.is_ours(decision.client_order_id))
        for order in ("legacy-order", "lookalike-order"):
            with self.subTest(order=order), self.assertRaisesRegex(GuardRefusal, "^cancel_ownership$"):
                api.cancel_order_by_id(order)
        api.cancel_order_by_id("synthetic-order")
        self.assertEqual(self.sdk.writes[-1], ("cancel", "synthetic-order"))

    def test_E8_a_failed_cancel_wedges_the_arm_only_while_its_order_is_outstanding(self):
        def failing_cancel(key):
            raise RuntimeError("order is already terminal")
        self.sdk.cancel_order_by_id = failing_cancel
        first = self.decision()
        self.api.submit_order(order_data=OrderData(**first.payload()))
        self.gov.reconcile(first.client_order_id, terminal="filled", account=self.account)
        with self.assertRaisesRegex(GuardRefusal, "^unknown_outcome$"):
            self.api.cancel_order_by_id("synthetic-order")      # its order is already reconciled
        self.assertFalse(self.gov.recovery_required, "a terminal order must not wedge the arm")
        second = self.decision()      # the arm still admits
        self.api.submit_order(order_data=OrderData(**second.payload()))
        with self.assertRaisesRegex(GuardRefusal, "^unknown_outcome$"):
            self.api.cancel_order_by_id("synthetic-order")      # same broker id in the fake, now mapped to the outstanding second order
        self.assertTrue(self.gov.recovery_required)
        self.gov.reconcile(second.client_order_id, terminal="canceled", account=self.account)
        self.assertFalse(self.gov.recovery_required)


class ReviewRecovery(CoreCase):
    def test_J7_malformed_final_prices_are_journaled_before_refusal(self):
        for value,code in [("NaN","number"),("text","number"),(None,"number")]:
            with self.subTest(value=value):
                decision=self.decision()
                payload=dict(decision.payload(),limit_price=value)
                before=len(self.journal.rows)
                try:
                    with self.assertRaisesRegex(GuardRefusal,"^"+code+"$"):
                        self.api.submit_order(order_data=OrderData(**payload))
                    self.assertEqual(len(self.journal.rows),before+1)
                    self.assertEqual(self.journal.rows[-1]["event"],"refusal")
                    self.assertEqual(self.journal.rows[-1]["reason"],code)
                    self.assertFalse(self.sdk.writes)
                    self.assertIn(decision.reservation,self.gov.reservations)
                finally:self.gov.reconcile(decision.client_order_id,terminal="not_sent",account=self.account)

    def test_J1_journal_failure_latches_and_prevents_later_submit(self):
        for mode in ("fsync", "short", "write"):
            with self.subTest(mode=mode):
                journal=Journal(self.root/(mode+".jsonl"))
                try:
                    gov=Governor(CODE/"caps-a6-diagnostic.json",journal)
                    sdk=FakeSDK();api=GuardedApi(sdk,gov,lambda:NOW)
                    write=os.write
                    def short(fd,raw):return write(fd,raw[:max(1,len(raw)//2)])
                    target="governor.os.fsync" if mode=="fsync" else "governor.os.write"
                    with patch(target,side_effect=OSError("synthetic")) if mode!="short" else patch(target,side_effect=short):
                        with self.assertRaisesRegex(GuardRefusal,"^journal_write$"):
                            gov.decide(self.intent,self.quote,self.account,NOW)
                    before=journal.path.read_bytes()
                    with self.assertRaisesRegex(GuardRefusal,"^journal_write$"):
                        result=gov.decide(self.intent,self.quote,self.account,NOW)
                        if isinstance(result,Decision):api.submit_order(order_data=OrderData(**result.payload()))
                    self.assertEqual(journal.path.read_bytes(),before)
                    self.assertFalse(sdk.writes)
                finally:journal.close()

    def test_J2_consume_refuses_clock_rollback_before_sdk(self):
        decision=self.decision()
        times=iter((NOW+61*10**9,NOW+59*10**9))
        api=GuardedApi(self.sdk,self.gov,lambda:next(times))
        with self.assertRaisesRegex(GuardRefusal,"^clock$"):
            api.submit_order(order_data=OrderData(**decision.payload()))
        self.assertFalse(self.sdk.writes)
        self.assertFalse(any(r["event"]=="submit" for r in self.journal.rows))
        self.assertIn(decision.reservation,self.gov.reservations)

    def test_J3_restart_finds_owned_order_beyond_default_page(self):
        decision=self.decision();self.api.submit_order(order_data=OrderData(**decision.payload()))
        self.journal.close();self.journal=Journal(self.root/"journal.jsonl")
        gov=Governor(CODE/"caps-a6-diagnostic.json",self.journal)
        sdk=FakeSDK();sdk.get_orders=lambda:[{"id":str(i),"client_order_id":"foreign-"+str(i)} for i in range(50)]
        looked=[]
        def lookup(cid):
            looked.append(cid)
            return SimpleNamespace(id="old-owned",client_order_id=cid,status="new")
        sdk.get_order_by_client_id=lookup
        before=len(gov.requests)
        api=GuardedApi(sdk,gov,lambda:NOW)
        try:api.cancel_order_by_id("old-owned")
        except GuardRefusal as error:self.fail(f"retained owned order must remain cancellable: {error}")
        self.assertEqual(looked,[decision.client_order_id])
        self.assertEqual(sdk.writes,[("cancel","old-owned")])
        self.assertEqual(len(gov.requests)-before,12)  # list + direct lookup + cancel

    def test_J4_restart_direct_lookup_fails_closed(self):
        decision=self.decision();self.api.submit_order(order_data=OrderData(**decision.payload()))
        for result in (None,SimpleNamespace(id="bad",client_order_id="foreign"),RuntimeError("unreadable")):
            with self.subTest(shape=type(result).__name__):
                sdk=FakeSDK();sdk.get_orders=lambda:[]
                def lookup(cid):
                    if isinstance(result,Exception):raise result
                    return result
                sdk.get_order_by_client_id=lookup
                try:GuardedApi(sdk,self.gov,lambda:NOW)
                except Exception as error:
                    self.assertIs(type(error),GuardRefusal)
                    self.assertEqual(str(error),"restart_orders_unreadable")
                else:self.fail("missing/foreign/unreadable direct order must refuse")

    def test_J6_runtime_pins_and_package_sources_are_required(self):
        import importlib.util
        spec=importlib.util.spec_from_file_location("review_runtime",CODE/"acceptance/runtime_snapshot.py")
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        current={"runtime":{"python":"3.12.4","lumibot":"4.6.11","alpaca-py":"0.44.0"}}
        module.verify(current,current)
        bad={"runtime":dict(current["runtime"],lumibot="4.6.18")}
        with self.assertRaisesRegex(SystemExit,"^acceptance_runtime_pin_mismatch$"):
            module.verify(bad,bad)
        class EmptyDistribution:
            files=[]
        with patch.object(module.metadata,"distributions",return_value=[]), \
             patch.object(module.metadata,"distribution",return_value=EmptyDistribution()):
            try:module.observe()
            except BaseException as error:
                self.assertIs(type(error),SystemExit)
                self.assertEqual(str(error),"runtime_sources_missing")
            else:self.fail("empty installed source inventory must refuse")

    def test_J5_export_refuses_a_different_acceptance_runtime(self):
        import importlib.util
        import hashlib
        import copy
        import subprocess
        current_acceptance=Path(__file__).resolve().parents[1]/"blueprints/us-equities/engine-lumibot/acceptance"
        with patch.object(sys,"path",[str(CODE/"acceptance"),str(current_acceptance),*sys.path]):
            spec=importlib.util.spec_from_file_location("review_export",CODE/"acceptance/export_receipt.py")
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        expected={"runtime":{"python":"3.12.4","lumibot":"4.6.11","alpaca-py":"0.44.0"},
                  "interpreter_sha256":"1"*64,"distributions":[["lumibot","4.6.11"]],
                  "package_sources":[{"package":"lumibot","sha256":"2"*64,"files":1}]}
        root=CODE.parents[2];out=CODE/"acceptance"
        sources=[*CODE.glob("*.py"),*out.glob("*.py"),CODE/"caps-a6-diagnostic.json",CODE/"write-boundaries.json",
                 root/"tests/test_engine_lumibot_governor.py",root/"tests/test_engine_lumibot_native.py"]
        inputs=[{"role":p.name,"sha256":hashlib.sha256(p.read_bytes()).hexdigest()} for p in sources]
        log=b"test_synthetic (synthetic.Case.test_synthetic) ... ok\n\nRan 1 test in 0.001s\n\nOK\n"
        (self.root/"synthetic.log").write_bytes(log)
        receipt={"input_hashes":inputs,"runtime_binding":expected,"runtime_environment":{},
                 "started_at":"synthetic","finished_at":"synthetic","commands":[{
                 "command":["synthetic"],"exit_code":0,"raw_output":{"role":"synthetic_private_log",
                 "sha256":hashlib.sha256(log).hexdigest()}}]}
        summary={"survived":0,"not_applied":0,"invalid_runs":0,"baseline_failures":0,"killed":0,
                 "source_sha256":{},"check_source_sha256":{}}
        (self.root/"summary.json").write_text(json.dumps(summary))
        args=SimpleNamespace(private_run=self.root,mutations=self.root,runtime_python=Path("synthetic-python"))
        for component in ("runtime","interpreter_sha256","distributions","package_sources"):
            with self.subTest(component=component):
                observed=copy.deepcopy(expected)
                if component=="runtime":observed[component]["python"]="3.12.3"
                else:observed[component]="changed"
                (self.root/"receipt.private.json").write_text(json.dumps(receipt))
                with patch.object(module.argparse.ArgumentParser,"parse_args",return_value=args), \
                     patch.object(module,"capture",return_value=observed,create=True), \
                     patch.object(subprocess,"check_output",side_effect=[json.dumps(expected["runtime"]),"[]"]):
                    try:module.main()
                    except BaseException as error:
                        self.assertIs(type(error),SystemExit)
                        self.assertEqual(str(error),"acceptance_runtime_mismatch")
                    else:self.fail("different runtime must refuse before export")


class ExitPolicyMatrix(CoreCase):
    """CC B1 ruling: six admitted exit cases across all four sessions."""
    SESSIONS=("RTH","PRE","POST","OVERNIGHT")
    EXIT_CASES=(("10.04","10.05",20),("11.00","11.01",20),("4.97","4.98",20),
                ("209.00","209.50",1),("9.50","10.00",20),("10.00","10.60",21))

    def test_E1_exit_at_touch_in_every_session(self):
        for session in self.SESSIONS:
            for bid,ask,qty in self.EXIT_CASES:
                with self.subTest(session=session,bid=bid,ask=ask,qty=qty):
                    result=self.gov.decide(Intent("SYN","sell","exit_all"),
                                           replace(self.quote,bid=D(bid),ask=D(ask),session=session),
                                           replace(self.account,positions={"SYN":qty}),NOW)
                    self.assertIsInstance(result,Decision)
                    self.assertEqual((result.side,result.qty,result.limit_price),("sell",qty,D(bid)))
                    self.assertIs(result.extended_hours,session!="RTH")
                    self.gov.reconcile(result.client_order_id,terminal="not_sent",account=self.account)

    def test_E2_entry_keeps_ask_band_and_spread_refusals(self):
        for session in self.SESSIONS:
            for bid,ask,code in [("4.97","4.98","ask_band"),("209.00","209.50","ask_band"),("9.50","10.00","spread")]:
                with self.subTest(session=session,code=code):
                    result=self.gov.decide(self.intent,replace(self.quote,bid=D(bid),ask=D(ask),session=session),self.account,NOW)
                    self.assertEqual(result,Refusal(code))

    def test_E3_entry_whole_size_remains_inside_notional_cap(self):
        for session in self.SESSIONS:
            result=self.gov.decide(self.intent,replace(self.quote,bid=D("10.04"),ask=D("10.05"),session=session),self.account,NOW)
            self.assertIsInstance(result,Decision);self.assertLessEqual(result.qty*result.limit_price,D("200"))
            self.gov.reconcile(result.client_order_id,terminal="not_sent",account=self.account)

    def test_E4b_exit_does_not_depend_on_account_equity_in_any_session(self):
        # Astra B1 at ca52c176: a reconciled long position stays exitable at zero or negative equity in every session; an entry at the same equity is still refused
        for session in self.SESSIONS:
            for equity in ("0", "-1"):
                with self.subTest(session=session, equity=equity):
                    account = replace(self.account, equity=D(equity), positions={"SYN": 20})
                    quote = replace(self.quote, bid=D("10.00"), ask=D("10.01"), session=session)
                    result = self.gov.decide(Intent("SYN", "sell", "exit_all"), quote, account, NOW)
                    self.assertIsInstance(result, Decision)
                    self.assertEqual((result.side, result.qty, result.limit_price), ("sell", 20, D("10.00")))
                    self.assertIs(result.extended_hours, session != "RTH")
                    self.gov.reconcile(result.client_order_id, terminal="not_sent", account=account)
                    self.assertEqual(self.gov.decide(self.intent, replace(self.quote, session=session), replace(self.account, equity=D(equity)), NOW), Refusal("quote_account"))

    def test_E4_exit_still_requires_long_position_and_fresh_quote(self):
        quote=replace(self.quote,bid=D("10.04"),ask=D("10.05"))
        self.assertEqual(self.gov.decide(Intent("SYN","sell","exit_all"),quote,self.account,NOW),Refusal("quantity"))
        self.assertEqual(self.gov.decide(Intent("SYN","sell","exit_all"),replace(quote,quote_ns=NOW-60_000_000_001),
                                        replace(self.account,positions={"SYN":20}),NOW),Refusal("stale_quote"))


def load_tests(loader,tests,pattern):
    suite=unittest.TestSuite()
    for cls in (CoreCase,ReviewerAdditions,ExitPolicyMatrix,RestageAdditions,ReviewRecovery):
        suite.addTests(cls(name) for name in vars(cls) if name.startswith("test_"))
    return suite


if __name__ == "__main__": unittest.main()
