"""Pytest diagnostic plugin: refuse the listed Python socket/DNS audit events.

Applies to the upstream mock suite, including its broker/order fixtures.
The hard exit makes those observed Python events visible even if a test would
catch an ordinary exception. CPython audit hooks are NOT a sandbox or proof of
complete network/process isolation; native extensions can bypass these events.
Reference: CPython 3.12 sys.addaudithook and socket audit events.
https://docs.python.org/3.12/library/sys.html#sys.addaudithook
"""

import os
import sys


def refuse_network(event, args):
    if event in {"socket.connect", "socket.getaddrinfo", "socket.gethostbyname"}:
        print("OUTBOUND_NETWORK_ATTEMPT_REFUSED " + event, file=sys.stderr, flush=True)
        os._exit(86)


sys.addaudithook(refuse_network)

# Load the installed, hash-pinned SDK before pytest's default upstream test
# collection prepends helper/package directories. All submodule resolution then
# normally follows this installed package during the observed tests; this is
# import-order evidence, not an enforced isolation boundary.
import alpaca
import exchange_calendars

print(alpaca.__file__, flush=True)
print(exchange_calendars.__file__, flush=True)
