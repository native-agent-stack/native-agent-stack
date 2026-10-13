"""Explicit managed-runtime smoke, not an ordinary unittest-discovery module.

Run with the installed paper runtime; absence/wrong version is a failure, never
a skip. No broker client or credentials are constructed. Production projection:
alpaca-py0.44.0 cc4cb3b7ba50ae250e621983c2779047fb16bb28 requests.py346-364,
509-536; NAS transport.order_envelope -> limit_order_request.
"""
from importlib.metadata import version
import json
from pathlib import Path
import sys


def main():
    if version("alpaca-py") != "0.44.0":
        raise RuntimeError("managed_sdk_version_mismatch")
    source = Path(__file__).resolve().parents[2] / "blueprints/us-equities/adaptive-paper"
    sys.path.insert(0, str(source))
    from transport import order_envelope, limit_order_request, check_wire_submission
    from alpaca.trading.enums import OrderType, TimeInForce
    for side in ("buy", "sell"):
        intent = {"symbol": "SPY", "qty": "1", "side": side, "limit_price": "100",
                  "client_order_id": "syn-prepost-" + side, "extended_hours": True}
        envelope = order_envelope(intent, extended_hours_allowed=True)
        request = limit_order_request(envelope)
        if request.type != OrderType.LIMIT or request.time_in_force != TimeInForce.DAY or request.extended_hours is not True:
            raise RuntimeError("native_sdk_projection_mismatch")
        body = dict(intent, type="limit", time_in_force="day")
        check_wire_submission({intent["client_order_id"]: envelope}, body)
    print(json.dumps({"paper_lane": "B", "evidence_class": "local_integration",
                      "status": "passed", "sdk_version": "0.44.0", "checks": 2,
                      "broker_execution": "NOT_RUN"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
