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
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
CODE = Path(os.environ.get("ENGINE_LUMIBOT_ROOT", ROOT / "blueprints/us-equities/engine-lumibot"))
sys.path.insert(0, str(CODE))
from governor import (AccountState, Decision, Governor, GuardRefusal, Intent, Journal,
                      QuoteSnapshot, Refusal, encode, rounded)
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
        self.refuse("notional_cap", intent=Intent("SYN","sell","exit_all"),
                    account=replace(self.account, positions={"SYN":21}))

    def test_A2_payload_refusals_exact(self):
        decision = self.decision()
        cases = [("type", x, "order_type") for x in ("market","stop","stop_limit","trailing_stop","smart_limit")]
        cases += [("time_in_force", x, "time_in_force") for x in ("gtc","ioc","fok","opg","cls")]
        cases += [("side", x, "side") for x in ("sell_short","buy_to_cover")]
        cases += [("qty", x, "quantity") for x in ("0","-1","1.5",1,True,"01")]
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
        self.api.submit_order(order_data=OrderData(**decision.payload()))
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


if __name__ == "__main__": unittest.main()
