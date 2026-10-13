"""L2 vendor subclasses; imports only when the caller explicitly loads them.

No credential or broker is selected here. Acceptance supplies fabricated
configuration, injected data and SDK client; live designation is out of scope.
"""
import json
import os
from pathlib import Path

from governor import Intent, Decision, GuardRefusal
from guarded_api import GuardedApi


def read_inbox(path):
    path = Path(path)
    if path.is_symlink():
        raise GuardRefusal("inbox")
    result = []
    for raw in path.read_text().splitlines():
        try:
            row = json.loads(raw)
            if not isinstance(row, dict) or set(row) != {"symbol", "side", "sizing"}:
                raise ValueError()
            if any(type(value) is not str for value in row.values()):
                raise ValueError()
            result.append(Intent(**row))
        except (ValueError, TypeError):
            raise GuardRefusal("inbox") from None
    return tuple(result)


def load_classes():
    required = {"LUMIBOT_DISABLE_DOTENV": "1", "LUMIBOT_DISABLE_DOTENV_LOCAL": "1",
                "LUMIBOT_LAZY_CREDENTIALS": "1", "LUMIBOT_CONNECT_STREAM": "false",
                "LUMIBOT_START_ORDERS_THREAD": "false", "LUMIBOT_TELEMETRY": "0"}
    if any(os.environ.get(key) != value for key, value in required.items()):
        raise GuardRefusal("environment")
    if any(os.environ.get(key) for key in ("LUMIBOT_STRATEGY_PARAMETERS", "BACKTESTING_PARAMETERS", "LUMIWEALTH_API_KEY", "DISCORD_WEBHOOK_URL", "LISTENER_WRITE_URL")):
        raise GuardRefusal("environment")      # these override the closed inbox or send positions to a third party
    from lumibot.brokers import Alpaca
    from lumibot.strategies import Strategy
    from lumibot.entities import Order, Asset

    class StockOnlyAlpaca(Alpaca):
        def __init__(self, config, *, governor, clock, data_source, session=None, clock_ns=None, **kwargs):
            # No PAPER is a refusal, not a repair of a live-default config.
            if (not isinstance(config, dict) or config.get("PAPER") is not True
                    or any("paper" in str(key).lower() and key != "PAPER" for key in config)):
                governor.reject("paper_required")
            if kwargs:
                governor.reject("construction_options")
            if session not in governor.caps["sessions"]:
                governor.reject("session")
            now=clock()
            if type(now) is not int or type(clock_ns) is not int or not 0 <= now-clock_ns <= 250_000_000:
                governor.reject("clock")
            self.governor = governor
            self._guard_installed = False
            super().__init__(dict(config), connect_stream=False, start_orders_thread=False,
                             data_source=data_source)
            client = self.api
            if self.is_paper is not True:
                governor.reject("paper_required")
            base = getattr(client, "_base_url", "")
            if getattr(base, "value", base) != "https://paper-api.alpaca.markets":
                governor.reject("paper_url")
            proxy = GuardedApi(client, governor, clock)
            self._api = proxy
            # Vendor construction keeps plaintext credential attributes. Clear
            # these after the isolated parent-side SDK client is encapsulated.
            for name in ("api_key", "api_secret", "oauth_token"):
                setattr(self, name, "")
            for name,value in tuple(vars(self).items()):
                if isinstance(value,dict):
                    setattr(self,name,{key:item for key,item in value.items()
                                       if key not in ("API_KEY","API_SECRET","OAUTH_TOKEN")})
            self._guard_installed = True

        @property
        def api(self):
            if self._guard_installed:
                return self._api
            return Alpaca.api.fget(self)

        @api.setter
        def api(self, value):
            self.governor.reject("api_replacement")

        def _create_trading_client(self):
            if self._guard_installed:
                self.governor.reject("client_recreation")
            return super()._create_trading_client()

        def _deny(self, *args, **kwargs):
            with self.governor.lock:
                self.governor.reject("broker_seam")

        _submit_orders = _deny
        _submit_multileg_order = _deny
        _modify_order = _deny
        sell_all = _deny
        close_position = _deny
        close_positions = _deny

        def _submit_order(self, order):
            if not isinstance(order, Order) or order.asset.asset_type != Asset.AssetType.STOCK:
                self.governor.reject("stock_only")
            if order.custom_params:
                self.governor.reject("custom_params")
            if (order.order_type != "limit" or order.order_class not in (None, "simple")
                    or getattr(order, "smart_limit", None)):
                self.governor.reject("order_type")
            if order.time_in_force != "day":
                self.governor.reject("time_in_force")
            if order.side not in ("buy", "sell"):
                self.governor.reject("side")
            if order.quantity <= 0 or order.quantity != int(order.quantity):
                self.governor.reject("quantity")
            return super()._submit_order(order)

        def submit_decision(self, decision, *, strategy):
            if not isinstance(decision, Decision):
                self.governor.reject("reservation")
            # Lumibot identifies tracked orders and fill subscribers by this
            # name (4.6.18/730d5608 strategy.py:894-895, broker.py:2567-2582,
            # :2908-2922,:3262-3297); preserve the originating strategy.
            order = Order(strategy, Asset(decision.symbol, asset_type="stock"),
                          decision.qty, decision.side, order_type="limit",
                          time_in_force="day", limit_price=decision.limit_price)
            self.api.bind(decision)
            return self.submit_order(order)

    class IntentStrategy(Strategy):
        """Trusted fixed strategy. There is no agent object/network-tool runtime."""
        def initialize(self, inbox, governor, snapshot, clock):
            self._closed_intents = iter(read_inbox(inbox))
            self._governor, self._snapshot, self._clock = governor, snapshot, clock

        @property
        def agents(self):
            self.broker.governor.reject("agent_runtime")

        @agents.setter
        def agents(self, value):
            # Lumibot assigns its lazy agent component during construction.
            # Discard it without ever exposing/instantiating an AgentManager.
            from lumibot.strategies._strategy import _LazyStrategyComponent
            if not isinstance(value,_LazyStrategyComponent):
                self.broker.governor.reject("agent_runtime")

        def on_trading_iteration(self):
            intent = next(self._closed_intents, None)
            if intent is None:
                return None
            quote, account = self._snapshot(intent.symbol)
            decision = self._governor.decide(intent, quote, account, self._clock())
            if isinstance(decision, Decision):
                return self.broker.submit_decision(decision, strategy=self.name)
            return decision

    return StockOnlyAlpaca, IntentStrategy
