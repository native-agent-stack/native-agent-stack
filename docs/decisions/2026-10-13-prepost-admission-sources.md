# PRE/POST admission: retained primary-source spans

Evidence class: source_review. These captures support the helper's existing
order and policy contracts, not broker acceptance or attained leverage.
Full-blob hashes below were computed from exact `git show PIN:PATH` bytes.
No private paths, account identities or credential material are captured.

## Alpaca request projection

Repository: https://github.com/alpacahq/alpaca-py
Pin: cc4cb3b7ba50ae250e621983c2779047fb16bb28 (managed package0.44.0).
File: alpaca/trading/requests.py.
Full blob SHA256:3290cc8b0d90cae87bc67b1e108b1a67b74d5ecc719dd7bb38026a99b6301552.

Lines346-347 state:

```text
        time_in_force (TimeInForce): The expiration logic of the order.
        extended_hours (Optional[bool]): Whether the order can be executed during extended hours.
```

Lines356-364 contain the actual fields:

```python
    symbol: Optional[str] = None
    qty: Optional[float] = None
    notional: Optional[float] = None
    side: Optional[OrderSide] = None
    type: OrderType
    time_in_force: TimeInForce
    order_class: Optional[OrderClass] = None
    extended_hours: Optional[bool] = None
```

Lines509-511 declare `class LimitOrderRequest(OrderRequest)` and "Used to submit
a limit order." Lines520-521 document time_in_force and extended_hours for that
class. This provides the vendor-supported model; native transport below owns
the actual production projection.

## Native engine order boundary

Repository: https://github.com/native-agent-stack/native-agent-stack
Pin: d8f7e2051b61bde6361a85b64f41413798015353, retained local Git object.
File: blueprints/us-equities/adaptive-paper/transport.py.
Full blob SHA256:14f30b03548bde1bdb3330db95eeb8565b1970152967c7b0f877036f80a98257.

Lines163-166 project only validated fields:

```python
        fields = {key: intent[key] for key in ("symbol", "qty", "side", "client_order_id", "limit_price")}
        fields.update(type="limit", time_in_force="day", extended_hours=intent.get("extended_hours", False))
        return order_contract.build_envelope(fields, fractional_sell_qty=True,
                                             extended_hours_allowed=bool(extended_hours_allowed))
```

Lines173-181 build the SDK request from that envelope:

```python
def limit_order_request(envelope):
    """The alpaca-py request built only from a validated envelope's intent."""
    from alpaca.trading.requests import LimitOrderRequest
    intent = envelope["intent"]
    try:
        return LimitOrderRequest(symbol=intent["symbol"], qty=intent["qty"], side=intent["side"],
                                 type="limit", time_in_force="day", limit_price=intent["limit_price"],
                                 client_order_id=intent["client_order_id"],
                                 extended_hours=intent["extended_hours"])
```

Ordinary tests exercise order_envelope and check_wire_submission without an SDK
import. The explicit managed-runtime smoke
`tests/integration/paper_prepost_order_projection.py` requires0.44.0 and exercises
order_envelope→limit_order_request for buys and sells. Missing/wrong SDK fails;
there is no skip, client construction, credential read or HTTP submission.

## Native session ceilings

Same NAS pin, file blueprints/us-equities/adaptive-paper/leverage.py.
Full blob SHA256:6a72d9f66b5c6de176cb9ff6fca235908e151d9c0107f631dc9f8aa0100ad753.
Lines58-61 of CANONICAL_V1_BLOCK:

```python
        "RTH":    {"trend": "4", "range": "1", "risk_off": "0", "unavailable": "0"},
        "PRE":    {"trend": "1", "range": "1", "risk_off": "0", "unavailable": "0"},
        "POST":   {"trend": "1", "range": "1", "risk_off": "0", "unavailable": "0"},
        "CLOSED": {"trend": "0", "range": "0", "risk_off": "0", "unavailable": "0"},
```

The helper compares the complete native canonical block rather than replacing
this engine policy. PRE always requires the registered1x limits; POST also
retains the explicitly pinned conservative SIP control. Namespace/GO/recovery
remain the parent's account-continuity mechanisms.

## Review limitations and follow-ups

- A refused build can retain unsealed config files because native validation
  follows staging. Such residue is not a sealed bundle, GO or trading receipt.
  Atomic temporary-bundle publication/cleanup is a follow-up before automated
  retryable cuts, inherited from the parent; no claim of universal no-residue
  refusal is made here.
- Main's exploration/SQL-lineage composition is exercised separately from the
  older PR base. Reviewed landing and the complete actual-pin wiring dry run
  remain prerequisites to activation.
- Inherited expired OSV ignores belong to the existing advisory-policy owner;
  no ignores, dependency manifests or scanner configuration change in this PR.
- Exact red/green, source, scan and merge receipts are retained for review and
  refreshed after the parent's fix/rebase. Synthetic wiring is not broker or
  qualification evidence.
