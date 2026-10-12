#!/usr/bin/env python3
"""Length of the `instructions` text an MCP server sends in its `initialize` result, against the client's cap on server instructions:

  python3 tools/adoption/mcp_instructions_length.py URL [--cap N] [--marker LINE] [--bullet PREFIX] [--json] [--timeout SECONDS]

One JSON-RPC `initialize` request to a streamable-HTTP MCP endpoint (POST, Accept: application/json and text/event-stream). No tool is listed or called, no credential is sent and no session is kept. Printed: the
server's name and version, the protocol version it answered with, the length in characters (Unicode code points) and in UTF-16 code units (the unit of a JavaScript string's length), the UTF-8 bytes, the number of characters
outside the Basic Multilingual Plane, and the first 16 hex digits of the text's sha256. With --marker LINE (a line that ends a self-contained core and starts detail, such as
ai-memory's "--- Detailed tool routing follows. ---") the core and detail lengths are printed too; with --bullet PREFIX as well, the number of detail lines that start with PREFIX
and, with --cap, how many of them start under the cap and how many the cap cuts through (counts only). With --cap N (Claude Code's limit on MCP server instructions: 4,096 characters since 2.1.296, CHANGELOG.md L65 of
anthropics/claude-code@3deb8736; CLAUDE_CODE_MAX_MCP_DESCRIPTION_LENGTH changes it for every server of a session, L1522) the part that must reach the model, the core when there is a marker and the whole text without
one, is compared with the cap. The text itself is never printed or written, and the server's reply is not echoed in an error message.
A reply that is an event stream may carry server requests and notifications before the response to the POST (modelcontextprotocol/modelcontextprotocol@1f520964 docs/specification/2025-06-18/basic/transports.mdx
L104-L106), so it is read event by event until the response with the request's id; anything else in it (a message with a `method`, a response to another id) is skipped, and the stream is not read to its end.
--timeout bounds each read and the whole reply (default 30 s).
Exit 0: within the cap, or no cap given; 1: the part that must reach the model is longer than the cap; 2: the server could not be read, the URL is not an http or https URL, or its reply holds no initialize result.
"""
from __future__ import annotations

import argparse
import hashlib
import http.client
import io
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

PROTOCOL_VERSION = "2025-06-18"
REQUEST = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
           "params": {"protocolVersion": PROTOCOL_VERSION, "capabilities": {}, "clientInfo": {"name": "mcp-instructions-length", "version": "1"}}}
MAX_REPLY = 16 * 1024 * 1024    # bytes (JSON) or characters (event stream) read from one reply
MAX_LINE = 1024 * 1024          # characters in one line of an event stream


class Unreadable(Exception):
    """The endpoint could not be read; the message is fixed text and never carries the reply."""


def check_url(url: str) -> None:
    """Refuse (Unreadable) what is not an http or https URL with a host and a valid port; urlsplit raises ValueError for a malformed one, and its message would echo the input."""
    try:
        parts = urllib.parse.urlsplit(url)
        host, _ = parts.hostname, parts.port      # .port raises ValueError for a port that is not a number or out of range
    except ValueError:
        raise Unreadable("the URL is not valid") from None
    if parts.scheme not in ("http", "https") or not host:
        raise Unreadable("the URL is not http or https with a host")


def pick(data, request_id):
    """The JSON-RPC response to `request_id` among `data` (a decoded message, or a list of them), or None. A message with a `method` is a request or notification of the server, whatever its id, and a response
    to another id is not ours: both are skipped. A boolean is not an id (True == 1 in Python)."""
    for item in data if isinstance(data, list) else [data]:
        if (isinstance(item, dict) and "method" not in item and not isinstance(item.get("id"), bool) and item.get("id") == request_id
                and ("result" in item or "error" in item)):
            return item
    return None


def in_event_stream(reply, request_id, deadline):
    """Read the server-sent events of `reply` (https://html.spec.whatwg.org/multipage/server-sent-events.html#parsing-an-event-stream: a line ends with LF, CR or CRLF; `data:` lines of an event are joined with
    LF, one optional space after the colon is dropped; a blank line dispatches the event; comments and the other fields are ignored) until one holds the response to `request_id`; None at the end of the stream.
    Line ends are translated by universal-newline decoding, which holds back a bare CR at the end of what has arrived until the next byte shows whether an LF follows: an event that a server ends with CR CR and
    then leaves open is read at the next byte or the end of the stream (LF and CRLF streams are read as they arrive)."""
    stream = io.TextIOWrapper(reply, encoding="utf-8", newline=None)
    data, seen = [], 0
    try:
        while True:
            line = stream.readline(MAX_LINE + 1)
            if len(line) > MAX_LINE:
                raise Unreadable("a line of the event stream is longer than 1 MiB")
            seen += len(line)
            if seen > MAX_REPLY:
                raise Unreadable("the reply is longer than 16 MiB")
            if time.monotonic() > deadline:
                raise Unreadable("the endpoint did not finish its reply in time")
            end = line == ""                              # readline returns "" only at the end of the stream
            if line.startswith("data:"):
                value = line[5:].rstrip("\n")
                data.append(value[1:] if value.startswith(" ") else value)
            elif line.rstrip("\n") == "":                 # a blank line, or the end of the stream, dispatches the event
                if data:
                    try:
                        found = pick(json.loads("\n".join(data)), request_id)
                    except ValueError:
                        found = None                      # an event that is not JSON (an empty priming event, say) is skipped
                    data = []
                    if found is not None:
                        return found
                if end:
                    return None
    finally:
        stream.detach()                                   # leave the connection to the caller's `with`


def exchange(url: str, message: dict, timeout: float, headers: dict | None = None):
    """POST one JSON-RPC message (Streamable HTTP: modelcontextprotocol/modelcontextprotocol@1f520964 docs/specification/2025-06-18/basic/transports.mdx L84-L110) and return (the response to it, the HTTP
    response headers). A notification gets HTTP 202 and no body, so its response is None. A request gets one JSON object or an event stream (see the module text). Every failure is `Unreadable` with fixed text."""
    check_url(url)
    request = urllib.request.Request(url, data=json.dumps(message).encode(), method="POST",
                                     headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream", **(headers or {})})
    deadline = time.monotonic() + timeout
    try:
        with urllib.request.urlopen(request, timeout=timeout) as reply:
            if "id" not in message:
                reply.read(MAX_REPLY)
                return None, reply.headers
            if "text/event-stream" in reply.headers.get("content-type", ""):
                return in_event_stream(reply, message["id"], deadline), reply.headers
            raw = reply.read(MAX_REPLY + 1)
            if len(raw) > MAX_REPLY:
                raise Unreadable("the reply is longer than 16 MiB")
            return pick(json.loads(raw.decode("utf-8")), message["id"]), reply.headers
    except urllib.error.HTTPError as error:
        raise Unreadable(f"the endpoint answered HTTP {error.code}") from None
    except (urllib.error.URLError, OSError, http.client.HTTPException):
        raise Unreadable("the endpoint could not be reached or read") from None
    except ValueError:                                    # JSON that does not parse, bytes that are not UTF-8
        raise Unreadable("the reply is not JSON-RPC") from None


def result_of(found) -> dict:
    """The `result` object of a response from `exchange`, or Unreadable."""
    if found is None:
        raise Unreadable("the reply holds no response to the request")
    if "error" in found:
        raise Unreadable("the server answered with a JSON-RPC error")
    if not isinstance(found.get("result"), dict):
        raise Unreadable("the reply is not an initialize result")
    return found["result"]


def fetch(url: str, timeout: float) -> dict:
    return result_of(exchange(url, REQUEST, timeout)[0])


def measure(result: dict, marker: str | None, bullet: str | None = None, cap: int | None = None) -> dict:
    text = result.get("instructions")
    text = text if isinstance(text, str) else ""
    info = result.get("serverInfo") if isinstance(result.get("serverInfo"), dict) else {}
    out = {"server": str(info.get("name", "")), "version": str(info.get("version", "")), "protocol_version": str(result.get("protocolVersion", "")), "characters": len(text),
           "utf16_units": len(text.encode("utf-16-le")) // 2, "outside_bmp": sum(1 for char in text if ord(char) > 0xFFFF), "bytes": len(text.encode("utf-8")),
           "sha256_16": hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]}
    if marker:
        at = text.find(marker)
        if at >= 0:
            out.update({"marker": marker, "core": at, "detail": len(text) - at - len(marker)})
            if bullet:
                detail_start = at + len(marker)
                starts = [detail_start + found.start() for found in re.finditer(r"(?m)^" + re.escape(bullet), text[detail_start:])]
                out["bullet"] = bullet
                out["bullets"] = len(starts)
                if cap is not None:
                    ends = starts[1:] + [len(text)]
                    out["bullets_started_under_cap"] = sum(1 for start in starts if start < cap)
                    out["bullets_cut_by_cap"] = sum(1 for start, end in zip(starts, ends) if start < cap < end)
        else:
            out["marker"] = None
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("url")
    parser.add_argument("--cap", type=int)
    parser.add_argument("--marker")
    parser.add_argument("--bullet")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args(argv)
    try:
        measured = measure(fetch(args.url, args.timeout), args.marker, args.bullet, args.cap)
    except Unreadable as error:
        print(f"mcp_instructions_length: {error}", file=sys.stderr)
        return 2
    must_reach = measured.get("core") if measured.get("core") is not None else measured["characters"]
    over = args.cap is not None and must_reach > args.cap
    if args.cap is not None:
        measured.update({"cap": args.cap, "must_reach_the_model": must_reach, "over_the_cap": over})
    if args.json:
        print(json.dumps(measured, indent=1))
    else:
        print(f"server {measured['server']} {measured['version']} (protocol {measured['protocol_version']}): instructions {measured['characters']} characters, {measured['utf16_units']} UTF-16 units, "
              f"{measured['bytes']} bytes, {measured['outside_bmp']} outside the BMP, sha256 {measured['sha256_16']}")
        if "core" in measured:
            print(f"core before the marker {measured['core']} characters, detail after it {measured['detail']}")
            if "bullets" in measured:
                print(f"{measured['bullets']} detail lines start with {measured['bullet']!r}" + (f"; {measured['bullets_started_under_cap']} start under the cap and {measured['bullets_cut_by_cap']} is cut by it"
                      if "bullets_started_under_cap" in measured else ""))
        elif args.marker:
            print("the marker is not in the text")
        if args.cap is not None:
            print(f"cap {args.cap}: the part that must reach the model is {must_reach} characters, {'over' if over else 'within'} the cap; the whole text is "
                  f"{'over' if measured['characters'] > args.cap else 'within'} it by {abs(measured['characters'] - args.cap)}")
    return 1 if over else 0


if __name__ == "__main__":
    sys.exit(main())
