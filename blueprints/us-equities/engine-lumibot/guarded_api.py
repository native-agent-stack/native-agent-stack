"""L1 capability mediation of the four Lumibot Alpaca SDK write sites.

Lumibot86250405 brokers/alpaca.py:1090,1262,1344,1394. The original
client lives only in function closure cells, never a broker/proxy attribute.
Python reflection is not an isolation boundary: acceptance's process audit
hook separately prevents a second client from reaching the network.
"""
import re
from governor import GuardRefusal, PAYLOAD_KEYS, dec

READS = frozenset({"get_clock", "get_account", "get_open_position", "get_all_positions",
                   "get_order_by_id", "get_orders", "get_portfolio_history", "get"})
RAW_READ_PATHS = frozenset({"/clock", "/account", "/positions", "/orders", "/account/portfolio/history"})


class ReservedOrderData:
    """Proxy-owned serialization, never dispatch to a caller-supplied class."""
    def __init__(self, payload):
        self.__dict__.update(payload)

    def to_request_fields(self):
        return dict(self.__dict__)


class GuardedApi:
    __slots__ = ("_invoke",)

    def __init__(self, real_client, governor, clock):
        base = getattr(real_client, "_base_url", "")
        if getattr(base, "value", base) != "https://paper-api.alpaca.markets":
            governor.reject("paper_url")
        retries = getattr(real_client, "_retry", 3)
        if type(retries) is not int or not 0 <= retries <= 3:
            governor.reject("retry_cap")
        units = retries + 1
        owned = set()
        bridge = {}

        def invoke(name, *args, **kwargs):
            with governor.lock:
                if name == "bind":
                    for stale in tuple(bridge):
                        if stale not in governor.reservations:
                            bridge.pop(stale)
                    decision = args[0]
                    expected = governor.reservations.get(decision.reservation)
                    if expected is None or expected != decision.payload():
                        governor.reject("reservation")
                    bridge[decision.reservation] = decision
                    return None
                if name == "submit_order":
                    if args or set(kwargs) != {"order_data"}:
                        governor.reject("payload_keys")
                    order = kwargs["order_data"]
                    if not hasattr(order, "__dict__"):
                        governor.reject("payload_keys")
                    payload = dict(vars(order))
                    # Lumibot's default SIMPLE class is a no-child marker,
                    # not an allowed broker payload extension. Strip only it.
                    if payload.get("order_class") == "simple":
                        payload.pop("order_class")
                    # Only the native single-order bridge can supply the two
                    # fields Lumibot omits. Never accept arbitrary custom_params.
                    if set(payload) == PAYLOAD_KEYS - {"extended_hours", "client_order_id"}:
                        if len(bridge) != 1:
                            governor.reject("reservation")
                        decision = next(iter(bridge.values()))
                        payload.update(extended_hours=decision.extended_hours,
                                       client_order_id=decision.client_order_id)
                    if set(payload) != PAYLOAD_KEYS:
                        governor.reject("payload_keys")
                    if payload["type"] != "limit":
                        governor.reject("order_type")
                    if payload["time_in_force"] != "day":
                        governor.reject("time_in_force")
                    if payload["side"] not in ("buy", "sell"):
                        governor.reject("side")
                    if not isinstance(payload["qty"], str) or not re.fullmatch(r"[1-9][0-9]*", payload["qty"]):
                        governor.reject("quantity")
                    if type(payload["extended_hours"]) is not bool:
                        governor.reject("session_flag")
                    token = payload["client_order_id"]
                    expected = governor.reservations.get(token)
                    if expected is None:
                        governor.reject("reservation")
                    if dec(payload["limit_price"]) != dec(expected["limit_price"]):
                        governor.reject("price_equality")
                    if payload["extended_hours"] != expected["extended_hours"]:
                        governor.reject("session_flag")
                    # Native float stringification may drop trailing zeros;
                    # equality is exact Decimal, forwarded bytes canonical.
                    payload["limit_price"] = expected["limit_price"]
                    if payload != expected:
                        governor.reject("reservation")
                    try:
                        governor.budget(clock(), submit=True, units=units)
                        governor.consume(payload, token, clock())
                    finally:
                        bridge.pop(token, None)
                    # alpaca-py consumes to_request_fields(), not vars(). Use
                    # only our own serializer of the checked reserved fields.
                    safe_order = ReservedOrderData(payload)
                    try:
                        response = real_client.submit_order(order_data=safe_order)
                    except Exception:
                        governor.outcome(token, "unknown")
                        raise GuardRefusal("unknown_outcome") from None
                    governor.outcome(token, "accepted_response")
                    if getattr(response, "id", None) is not None:
                        owned.add(str(response.id))
                    return response
                if name == "cancel_order_by_id":
                    if kwargs or len(args) != 1 or str(args[0]) not in owned:
                        governor.reject("cancel_ownership")
                    governor.budget(clock(), units=units)
                    governor.record("cancel", outcome="pending")
                    try:
                        result = real_client.cancel_order_by_id(args[0])
                    except Exception:
                        governor.record("cancel", outcome="unknown")
                        governor.recovery_required = True
                        raise GuardRefusal("unknown_outcome") from None
                    governor.record("cancel", outcome="accepted_response")
                    return result
                if name in READS:
                    if name == "get":
                        if len(args) != 1 or args[0] not in RAW_READ_PATHS or kwargs:
                            governor.reject("read_path")
                    elif any(key in kwargs for key in ("base_url", "url_override", "headers")):
                        governor.reject("read_path")
                    governor.budget(clock(), units=units)
                    return getattr(real_client, name)(*args, **kwargs)
                governor.reject("api_capability")
        object.__setattr__(self, "_invoke", invoke)

    def __getattr__(self, name):
        if name in READS or name in ("submit_order", "cancel_order_by_id"):
            return lambda *args, **kwargs: self._invoke(name, *args, **kwargs)
        self._invoke("refused_attribute")

    def bind(self, decision):
        return self._invoke("bind", decision)

    def __setattr__(self, name, value):
        self._invoke("refused_attribute")
