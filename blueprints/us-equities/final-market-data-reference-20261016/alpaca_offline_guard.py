"""Pytest plugin: stop the process BEFORE any outbound socket/DNS attempt.

Applies to the upstream mock suite, including its broker/order fixtures.
No fixture can remove a Python audit hook. The hard exit makes a network
attempt observable even if a test would catch an ordinary exception.
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
# stays under this installed package, while upstream flat helper imports work.
import alpaca
import exchange_calendars

print(alpaca.__file__, flush=True)
print(exchange_calendars.__file__, flush=True)
