"""Offline evidence for the one-node concurrent-preset proposal, not a runner.

Uses selected native build_node/Strategy/Ledger APIs with intercepted external
I/O. It never imports a credential loader or constructs a broker client.
Managed Nautilus2.0.0rc5 is required; absent runtime is a failure, not a skip.
"""
import asyncio
from decimal import Decimal
from functools import wraps
from importlib.metadata import version
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "blueprints/us-equities/adaptive-paper"))


def hermetic_probe(function):
    """Isolate every imported canonical latch; restore even on a failed probe."""
    @wraps(function)
    def run(*args, **kwargs):
        # Import bindings before the shared helper captures them. Passing a
        # private stop_file alone does not isolate canonical DEFAULT_STOP.
        import safety
        import runner
        import native_strategy
        from tests.adaptive_paper_hermetic import patch_default_stop, restore_default_stop
        with patch.object(tempfile, "tempdir", "/var/tmp"):
            token = patch_default_stop(safety, runner, native_strategy)
        try:
            return function(*args, **kwargs)
        finally:
            restore_default_stop(token)
    return run


@hermetic_probe
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


@hermetic_probe
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
                if gross_refusal != "aggregate_exposure_cap_exceeded":
                    raise AssertionError("unexpected_aggregate_gross_refusal") from error
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


@hermetic_probe
def adaptive_controls():
    """A: actual class cannot register twice. B: identity-only repair is unsafe.

    B inherits the real rebalance/minting path and native submit/cache operation.
    Only registration identity and policy decisions are fixtures. The node is
    never run: no port starts, broker I/O, credential access or external state.
    """
    from tests.test_adaptive_paper_native import ADAPTER, FakePort
    from native_strategy import AdaptiveStrategy
    from strategies import AdaptivePolicy, PolicyConfig
    from safety import Ledger, RiskLimits
    from nautilus_trader.config import StrategyConfig
    from nautilus_trader.model import StrategyId
    from nautilus_trader.trading import Strategy

    class IdentityOnly(AdaptiveStrategy):
        def __new__(cls, policy, ledger, trial_id, **kwargs):
            tag = "A1" if policy.config.symbols[0] == "SPY" else "B2"
            return Strategy.__new__(cls, StrategyConfig(strategy_id=StrategyId("ADAPTIVE-" + tag),
                order_id_tag=tag, log_events=False, log_commands=False, manage_stop=False))

        def submit_order(self, order):
            self.minted_order = order
            Strategy.submit_order(self, order)

    with tempfile.TemporaryDirectory(dir="/var/tmp") as scratch:
        ledger = Ledger(Path(scratch) / "account.sqlite3", RiskLimits())
        now = 1800000000.
        ledger.begin_next_trial(now, "shared-trial")
        def make(cls, symbol):
            universe = (symbol,) + tuple(s for s in ("SPY", "QQQ", "IWM", "DIA", "AAPL", "MSFT") if s != symbol)
            policy = AdaptivePolicy(PolicyConfig(symbols=universe, max_positions=6))
            policy.observe(symbol, 100, 100.01, now)
            return cls(policy, ledger, "shared-trial", stop_file=Path(scratch) / "unused-SYN-stop",
                       clock=lambda: now)
        try:
            port_a = FakePort()
            try:
                ADAPTER.build_node(port_a, [{"symbol": "SPY"}],
                                   [make(AdaptiveStrategy, "SPY"), make(AdaptiveStrategy, "QQQ")])
            except RuntimeError as error:
                refusal = str(error)
                if refusal != "Strategy ADAPTIVE-001-A is already registered":
                    raise AssertionError("unexpected_control_A_refusal:" + refusal) from error
            else:
                raise AssertionError("actual_adaptive_duplicate_identity_was_admitted")

            port_b = FakePort()
            siblings = [make(IdentityOnly, symbol) for symbol in ("SPY", "QQQ")]
            ADAPTER.build_node(port_b, [{"symbol": s} for s in ("SPY", "QQQ")], siblings)
            owners = []
            for sibling, symbol in zip(siblings, ("SPY", "QQQ")):
                sibling.started = sibling.enabled = True
                decision = SimpleNamespace(timestamp=now, regime="SYN", targets={symbol: 1},
                    signals=(), exits={}, effective_leverage=1, reason="SYN_ID_COLLISION")
                with patch.object(sibling.policy, "decide", return_value=decision):
                    sibling.rebalance(now)
                owners.append(str(sibling.cache.strategy_id_for_order(sibling.minted_order.client_order_id)))
            ids = [str(s.minted_order.client_order_id) for s in siblings]
            cached = siblings[0].cache.order(siblings[0].minted_order.client_order_id)
            if ids != ["adp-shared-trial-0000001"] * 2 or owners != ["ADAPTIVE-A1", "ADAPTIVE-B2"]:
                raise AssertionError("identity_only_collision_not_reproduced:" + repr((ids, owners)))
            if str(cached.instrument_id) != "QQQ.ALPACA":
                raise AssertionError("second_order_did_not_replace_first_cache_entry")
            if any((port_a.started, port_b.started, port_a.submissions, port_b.submissions)):
                raise AssertionError("adaptive_controls_reached_external_io")
        finally:
            ledger.close()
    return {"A": {"expected_refusal": refusal, "actual_class": "AdaptiveStrategy"},
            "B": {"fixture": "identity-only subclass; inherited production rebalance and IDs",
                  "ids": ids, "cache_owner_after_each_submit": owners,
                  "cached_instrument_after_second_submit": "QQQ.ALPACA",
                  "unsafe_cache_replacement_reproduced": True},
            "port_starts": 0, "external_submissions": 0}


@hermetic_probe
def coupling_probe():
    """Exercise the real shared Controller and 429 freeze methods, no SDK client."""
    from runner import Controller
    from safety import Ledger, SafetyError
    from native_adapter import NativeOrderRejected
    from transport import AlpacaPaperTransport

    class SharedPort:
        request_observer = None
        freeze_health = AlpacaPaperTransport.freeze_health
        _response_sync = AlpacaPaperTransport._response_sync
        def __init__(self):
            self._state_lock, self._reasons = threading.Lock(), set()
        @property
        def ready(self):
            return not self._reasons

    with tempfile.TemporaryDirectory(dir="/var/tmp") as scratch:
        ledger = Ledger(Path(scratch) / "account.sqlite3")
        now = 1800000000.
        ledger.begin_next_trial(now, "coupling")
        controller = Controller(ledger, now + 3600, market_open=True, clock=lambda: now,
                                stop_file=Path(scratch) / "unused-SYN-stop")
        controller.port = SharedPort()
        try:
            orders = []
            for tag, symbol in (("A1", "SPY"), ("B2", "QQQ")):
                controller.quote({"symbol": symbol, "bid": "100", "ask": "100.01", "ts_ns": int(now * 1e9)})
                order = {"client_order_id": "coupling-" + tag, "symbol": symbol,
                         "side": "buy", "qty": "1", "limit_price": "100.03", "strategy": tag}
                controller.before_submit(order)
                orders.append(order)
            if any(ledger.request_budget(now, "submit") for _ in range(180)):
                raise AssertionError("account_submit_reservation_failed")
            refusals = []
            for order in orders:
                try:
                    asyncio.run(controller.before_request("submit", order["client_order_id"]))
                except SafetyError as error:
                    if str(error) != "submission_rate_deferred":
                        raise
                    refusals.append(str(error))
                else:
                    raise AssertionError("sibling_bypassed_shared_submit_window")
            if controller.defer_until <= now or any(ledger.request_budget(now, "cancel") for _ in range(20)):
                raise AssertionError("shared_deferral_or_cancel_headroom_failed")
            controller.port._response_sync({"status": 429})
            frozen = []
            for order in orders:
                try:
                    controller.before_submit({**order, "client_order_id": order["client_order_id"] + "-after429"})
                except NativeOrderRejected as error:
                    if str(error) != "admissions_not_ready":
                        raise
                    frozen.append(str(error))
                else:
                    raise AssertionError("sibling_buy_bypassed_shared_429_freeze")
            if controller.port._reasons != {"rate_limited"}:
                raise AssertionError("unexpected_shared_429_freeze_reason")
        finally:
            ledger.close()
    return {"submit_refusals_by_preset": refusals, "shared_defer_until_advanced": True,
            "reserved_cancel_slots_admitted": 20, "http_429_reason": "rate_limited",
            "buy_refusals_by_preset_after_429": frozen,
            "scope": "actual Controller/transport methods; fixture health shell, no HTTP or node"}


def main():
    if version("nautilus_trader") != "2.0.0rc5":
        raise RuntimeError("selected_native_runtime_required")
    duplicate = "--duplicate-tags" in sys.argv
    if duplicate:
        try:
            native_probe(duplicate_tags=True)
        except RuntimeError as error:
            if str(error) != "Strategy Preset-A1 is already registered":
                raise AssertionError("unexpected_duplicate_tag_refusal") from error
            print("EXPECTED_CONTROL=Strategy Preset-A1 is already registered")
            print('CONTROL_RECEIPT={"paper_lane":"B","evidence_class":"synthetic",'
                  '"strategy_version":"concurrent-presets-proposal-v2","status":"expected_refusal"}')
            return 1
        raise AssertionError("duplicate_tag_control_was_admitted")
    if "--separate-budgets" in sys.argv:
        try:
            ledger_probe(separate_budgets=True)
        except AssertionError as error:
            if str(error) != "unsafe_separate_preset_counters_admit_201":
                raise
            print("EXPECTED_CONTROL=unsafe_separate_preset_counters_admit_201")
            print('CONTROL_RECEIPT={"paper_lane":"B","evidence_class":"synthetic",'
                  '"strategy_version":"concurrent-presets-proposal-v2","status":"expected_refusal"}')
            return 1
        raise AssertionError("separate_budget_control_did_not_violate_account_cap")
    result = native_probe(duplicate_tags=duplicate)
    budget = ledger_probe()
    controls = adaptive_controls()
    coupling = coupling_probe()
    print("PROPOSAL_RESULT=" + json.dumps({"paper_lane": "B", "evidence_class": "synthetic",
          "strategy_version": "concurrent-presets-proposal-v2",
          "presets": [{"preset_id": "A1", "version": "SYN-roundtrip-v1"},
                      {"preset_id": "B2", "version": "SYN-roundtrip-v1"}],
          "scope": "proposal feasibility, not concurrent broker acceptance",
          "native_version": "2.0.0rc5", "native": result, "account_ledger": budget,
          "adaptive_controls": controls,
          "shared_coupling": coupling,
          "broker_execution": "NOT_RUN", "status": "passed"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
