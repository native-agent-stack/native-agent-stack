"""Independent read-only capacity counts through alpaca-py, not the harness port.

Reuse adaptive-paper runner.credentials for inventory-format export/plain
env lines and its ownership/mode/location checks. No credential or exception
detail is printed. September's observer remains a historical capture.
Source: alpaca-py@cc4cb3b alpaca/trading/client.py:58,80-82,107,235.
"""

import argparse
from collections import Counter
from datetime import datetime
from decimal import Decimal
import json
from pathlib import Path
import sys

ADAPTIVE = Path(__file__).resolve().parents[2] / "adaptive-paper"
if str(ADAPTIVE) not in sys.path:
    sys.path.insert(0, str(ADAPTIVE))
from runner import credentials


def observe(client, receipt, request_type, statuses):
    prefix = (receipt.get("probe_plan") or {}).get("client_order_id_prefix") \
        or (receipt.get("config") or {}).get("client_order_id_prefix")
    if not isinstance(prefix, str) or not prefix:
        raise ValueError("missing_run_prefix")
    after = datetime.fromisoformat(receipt["started_at"])
    seen = {}
    while True:
        batch = client.get_orders(request_type(status=statuses.ALL, after=after,
                                               limit=500, direction="asc"))
        new = [order for order in batch if str(order.id) not in seen]
        for order in new:
            seen[str(order.id)] = order
        if len(batch) < 500:
            break
        if not new:
            raise ValueError("order_listing_did_not_advance")
        after = max(order.submitted_at for order in batch)
    mine = [order for order in seen.values() if str(order.client_order_id).startswith(prefix)]
    return {
        "orders_listed_since_start": len(seen),
        "orders_with_run_prefix": len(mine),
        "status_counts": dict(Counter(str(order.status.value) for order in mine)),
        "filled_qty_total": float(sum((Decimal(str(order.filled_qty or 0)) for order in mine), Decimal(0))),
        "positions_now": len(client.get_all_positions()),
        "open_orders_now": len(client.get_orders(request_type(status=statuses.OPEN))),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        key, secret = credentials(args.env_file)
    except Exception:
        # Refuse before constructing any SDK client; never print file content,
        # credential-guard exception context or user-provided paths.
        print("observer refused: credentials_unavailable", file=sys.stderr)
        return 2
    try:
        from alpaca.trading.client import TradingClient
        from alpaca.trading.requests import GetOrdersRequest
        from alpaca.trading.enums import QueryOrderStatus

        receipt = json.loads(args.receipt.read_text())
        # The SDK pins the paper origin; the env base URL is never an override.
        client = TradingClient(key, secret, paper=True)
        counts = observe(client, receipt, GetOrdersRequest, QueryOrderStatus)
        output = json.dumps(counts, sort_keys=True, allow_nan=False)
    except Exception:
        print("observer refused: observation_unavailable", file=sys.stderr)
        return 1
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
