"""Native GET-only flat proof for a trial refused before ownership was created.

Called only by deployment glue, through credential_run. No ledger/order adoption.
Reuses the frozen mover runner's bounded synchronous preflight request observer.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
PAPER = ROOT / 'frozen/blueprints/us-equities/adaptive-paper'
sys.path.insert(0, str(PAPER))
from runtime_lock import runtime_read_lock


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage')
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    from transport import preflight
    from mover_runner import _preflight_observer
    config = json.loads(args.config.read_text())
    symbols = config.get('symbols', config['benchmarks'])
    try:
        # Frozen mover_runner.py:620-625,695-697,908-914; runner.py:2345-2357.
        observation = preflight(os.environ['APCA_API_KEY_ID'], os.environ['APCA_API_SECRET_KEY'],
                                symbols, feed=config['feed'], before_request=_preflight_observer([]))
        positions, orders = observation['positions'], observation['orders']
        flat = not positions and not orders and observation['open_orders_complete'] is True
        result = {'status': 'passed' if flat else 'needs_attention', 'flat': flat,
                  'kind': 'native_GET_flat_proof_after_no_owned_trial',
                  'observed_at': datetime.now(timezone.utc).isoformat(),
                  'config_sha256': hashlib.sha256(args.config.read_bytes()).hexdigest(),
                  'positions': [] if flat else [{'observed_position_count': len(positions)}],
                  'unresolved_orders': [] if flat else [{'observed_open_order_count': len(orders)}],
                  'reconciliation': {'positions': len(positions), 'open_orders': len(orders)},
                  'open_orders_complete': observation['open_orders_complete'],
                  'broker_orders_submitted': 0}
        args.output.write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps({'status': result['status'], 'flat': flat}))
        return 0 if flat else 2
    except Exception as exc:
        print(json.dumps({'status': 'refused', 'error_class': type(exc).__name__}))
        return 2


if __name__ == '__main__':
    with runtime_read_lock():
        raise SystemExit(main())
