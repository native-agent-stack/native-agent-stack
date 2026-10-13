"""Offline evidence for the one-node concurrent-preset proposal, not a runner.

Uses selected native build_node/Strategy/Ledger APIs with intercepted external
I/O. It never imports a credential loader or constructs a broker client.
Managed Nautilus2.0.0rc5 is required; absent runtime is a failure, not a skip.
"""
import asyncio
from decimal import Decimal
from importlib.metadata import version
import json
from pathlib import Path
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "blueprints/us-equities/adaptive-paper"))


def native_probe(*, duplicate_tags=False):
    from tests.test_adaptive_paper_native import ADAPTER, FakePort
    from nautilus_trader.config import StrategyConfig
    from nautilus_trader.trading import Strategy
    from nautilus_trader.model import InstrumentId, OrderSide, Quantity, TimeInForce

    completed = set()
    class Preset(Strategy):
        def __init__(self, config=None):
            super().__init__(config)
            self.label, self.entry, self.fills = str(config.order_id_tag), None, 0

        def on_start(self):
            self.subscribe_quotes(InstrumentId.from_str("SPY.ALPACA"))

        def on_quote(self, tick):
            if self.entry is None:
                self.entry = self.order_factory.limit(tick.instrument_id, OrderSide.BUY, Quantity.from_int(1),
                      tick.ask_price, time_in_force=TimeInForce.DAY, tags=["preset=" + self.label])
                self.submit_order(self.entry)

        def on_order_filled(self, event):
            self.fills += 1
            if event.order_side == OrderSide.BUY:
                self.submit_order(self.order_factory.limit(event.instrument_id, OrderSide.SELL,
                         Quantity.from_int(1), event.last_px, time_in_force=TimeInForce.DAY,
                         tags=["preset=" + self.label]))
            else:
                completed.add(self.label)
                if len(completed) == 2:
                    self.shutdown_system("SYN two-preset proposal complete")

    port = FakePort()
    strategies = [Preset(StrategyConfig(order_id_tag=tag, log_events=False, log_commands=False))
                  for tag in ["A1", "A1" if duplicate_tags else "B2"]]
    session = ADAPTER.build_node(port, [{"symbol": "SPY"}], strategies)
    async def run():
        await asyncio.wait_for(session.run_async(), timeout=8)
    asyncio.run(run())
    if session.errors or len(completed) != 2 or port.qty != 0:
        raise AssertionError("native_two_strategy_roundtrips_not_flat")
    if port.started != 1 or port.stopped != 1 or len(port.submissions) != 4:
        raise AssertionError("single_shared_execution_session_not_established")
    clients = {str(row["strategy"]) for row in port.submissions}
    ids = [row["client_order_id"] for row in port.submissions]
    if len(clients) != 2 or len(set(ids)) != 4 or [s.fills for s in strategies] != [2, 2]:
        raise AssertionError("native_attribution_collision")
    return {"strategies": 2, "execution_clients": 1, "port_starts": port.started,
            "port_stops": port.stopped, "submissions": 4, "fills_per_strategy": [2, 2],
            "flat": port.qty == 0, "distinct_strategy_ids": len(clients),
            "distinct_order_ids": len(set(ids)), "data": "SYN_SAME_SYMBOL_QUOTES"}


def ledger_probe(*, separate_budgets=False):
    from safety import Ledger, RiskLimits, Quote, SafetyError
    # Independent preset counters are the unsafe comparator: 100 requests each
    # plus one more would admit201. The account Ledger must deny the201st.
    with tempfile.TemporaryDirectory(dir="/var/tmp") as scratch:
        root = Path(scratch)
        limits = RiskLimits(max_gross_exposure_usd=Decimal("150"),
                            max_order_notional_usd=Decimal("150"))
        ledger = Ledger(root / "account.sqlite3", limits)
        now = 1800000000.
        try:
            ledger.begin_next_trial(now, "concurrent-probe")
            if separate_budgets:
                other = Ledger(root / "unsafe-preset-budget.sqlite3", limits)
                try:
                    admitted = sum(ledger.request_budget(now, "read") == 0 for _ in range(101))
                    admitted += sum(other.request_budget(now, "read") == 0 for _ in range(100))
                finally:
                    other.close()
                if admitted > 200:
                    raise AssertionError("unsafe_separate_preset_counters_admit_201")
            delays = [ledger.request_budget(now, "read" if i % 2 else "cancel") for i in range(200)]
            if any(delays) or ledger.request_budget(now, "read") <= 0:
                raise AssertionError("shared_account_budget_failed")
            ledger.close()
            ledger = Ledger(root / "account.sqlite3", limits)
            if ledger.request_budget(now + 1, "read") <= 0:
                raise AssertionError("restart_refunded_account_budget")
            if ledger.request_budget(now + 61, "read") != 0:
                raise AssertionError("rolling_window_did_not_release")
            quote = Quote("SPY", "100", "100.01", now + 61)
            stop = root / "unused-SYN-stop"
            ledger.reserve_intent("first-buy", "SPY", "buy", "1", "100.01", quote=quote,
                                  now=now + 61, market_open=True, session_close=now + 3600, stop_file=stop)
            try:
                ledger.reserve_intent("second-buy", "SPY", "buy", "1", "100.01", quote=quote,
                                      now=now + 61, market_open=True, session_close=now + 3600, stop_file=stop)
            except SafetyError as error:
                gross_refusal = str(error)
            else:
                raise AssertionError("aggregate_pending_gross_not_enforced")
            if ledger.accounting().pending_buy_notional_usd != Decimal("100.01"):
                raise AssertionError("refused_order_changed_pending_gross")
        finally:
            ledger.close()
    return {"same_account_requests_admitted": 200, "request_201_deferred": True,
            "budget_survives_reopen": True, "window_after_61s_releases": True,
            "individual_order_notional": "100.01", "account_gross_cap": "150",
            "second_individually_valid_order_refused": gross_refusal,
            "pending_after_refusal": "100.01", "data": "SYN_QUOTES_AND_REQUEST_CLOCK"}


def main():
    if version("nautilus_trader") != "2.0.0rc5":
        raise RuntimeError("selected_native_runtime_required")
    duplicate = "--duplicate-tags" in sys.argv
    result = native_probe(duplicate_tags=duplicate)
    budget = ledger_probe(separate_budgets="--separate-budgets" in sys.argv)
    print("PROPOSAL_RESULT=" + json.dumps({"paper_lane": "B", "evidence_class": "synthetic",
          "scope": "proposal feasibility, not concurrent broker acceptance",
          "native_version": "2.0.0rc5", "native": result, "account_ledger": budget,
          "broker_execution": "NOT_RUN", "status": "passed"}, sort_keys=True))


if __name__ == "__main__":
    main()
