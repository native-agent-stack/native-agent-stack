"""The single qualified market data feed vocabulary for this paper lane.

Both the trading transport and the shadow research lane import this module, so
the qualified set is defined once and cannot drift between them. It has no SDK,
credential, network, account or order surface, so importing it adds no execution
capability to either caller.
"""
from __future__ import annotations

# alpaca-py 0.44.0, cc4cb3b7ba50ae250e621983c2779047fb16bb28,
# alpaca/data/enums.py:56-73: BOATS is the venue feed; OVERNIGHT is derived.
# Naming a feed does not establish entitlement or streaming acceptance.
DATA_FEEDS = ("iex", "sip", "boats")
# The pinned SDK's StockDataStream accepts only these feeds:
# alpacahq/alpaca-py@cc4cb3b7ba50ae250e621983c2779047fb16bb28,
# alpaca/data/live/stock.py:47-48. REST vocabulary is a separate boundary.
STREAM_FEEDS = ("iex", "sip")


def is_qualified_feed(value):
    """Accept only a plain ``str`` naming a qualified feed.

    ``type(value) is str`` is deliberate rather than ``isinstance``. An
    ``alpaca.data.enums.DataFeed`` member is a ``str`` subclass that compares
    equal to its value but formats as ``DataFeed.IEX``, which would silently
    build a malformed ``.../v2/DataFeed.IEX`` endpoint. Enum members are
    therefore refused; callers pass the configured plain string and convert to
    the SDK enum themselves.
    """
    return type(value) is str and value in DATA_FEEDS


def require_qualified_stream(value):
    """Refuse unsupported paper streams before either loader admits a trial.

    A named REST feed does not establish live-stream support. Keep the pinned
    SDK's allow-list separate so adding a data feed cannot admit its stream.
    """
    if not is_qualified_feed(value):
        raise ValueError("unqualified_data_feed")
    if value not in STREAM_FEEDS:
        raise ValueError(f"{value}_stream_unqualified_sdk")


def require_qualified_quote_source(value, mode="stream"):
    """Admit BOATS only through the reviewed SDK REST path, explicitly chosen."""
    if mode == "stream":
        require_qualified_stream(value)
    elif mode != "boats_rest" or type(value) is not str or value != "boats":
        raise ValueError("unqualified_quote_source")
