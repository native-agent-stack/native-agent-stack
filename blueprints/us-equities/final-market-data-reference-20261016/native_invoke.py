"""Native offline SDK calls; output is returned values, not pass summaries.

No client, network acquisition, broker or order calls. The public upstream
fixture path is supplied explicitly. SDK checks do not qualify publication time.
"""

from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
import socket
import sys


def blocked(*args, **kwargs):
    raise RuntimeError("network is not authorized for this offline invocation")


socket.socket.connect = blocked
socket.socket.connect_ex = blocked
socket.create_connection = blocked
socket.getaddrinfo = blocked

from edgar.sgml.sgml_header import FilingHeader
from alpaca.data.requests import StockBarsRequest
from alpaca.data.enums import DataFeed, Adjustment
from alpaca.data.timeframe import TimeFrame
import exchange_calendars as xcals

for distribution in ["edgartools", "alpaca-py", "exchange-calendars"]:
    print(distribution, version(distribution))
header = FilingHeader.parse_from_sgml_text(Path(sys.argv[1]).read_text())
print(header.acceptance_datetime)
assert header.acceptance_datetime == datetime(2023, 6, 7, 16, 10, 23)
request = StockBarsRequest(
    symbol_or_symbols=["FIXTURE"], timeframe=TimeFrame.Day,
    start=datetime(2024, 1, 2, tzinfo=timezone.utc),
    end=datetime(2024, 1, 3, tzinfo=timezone.utc),
    feed=DataFeed.IEX, adjustment=Adjustment.RAW,
)
print(request)
assert request.feed == DataFeed.IEX
calendar = xcals.get_calendar("XNYS")
print(calendar.is_session("2024-07-03"))
print(calendar.is_session("2024-07-04"))
print(calendar.session_close("2024-07-03"))
assert calendar.is_session("2024-07-03")
assert not calendar.is_session("2024-07-04")
assert calendar.session_close("2024-07-03").isoformat() == "2024-07-03T17:00:00+00:00"
