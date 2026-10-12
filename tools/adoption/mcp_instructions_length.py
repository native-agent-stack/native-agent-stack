#!/usr/bin/env python3
"""Length of the `instructions` text an MCP server sends in its `initialize` result, against the client's cap on server instructions:

  python3 tools/adoption/mcp_instructions_length.py URL [--cap N] [--marker LINE] [--json]

One JSON-RPC `initialize` request to a streamable-HTTP MCP endpoint (POST, Accept: application/json and text/event-stream). No tool is listed or called, no credential is sent and no session is kept. Printed: the
server's name and version, the length in characters and in UTF-8 bytes, and the first 16 hex digits of the text's sha256. With --marker LINE (a line that ends a self-contained core and starts detail, such as
ai-memory's "--- Detailed tool routing follows. ---") the core and detail lengths are printed too. With --cap N (Claude Code's limit on MCP server instructions: 4,096 characters since 2.1.296, CHANGELOG.md L65 of
anthropics/claude-code@3deb8736; CLAUDE_CODE_MAX_MCP_DESCRIPTION_LENGTH changes it for every server of a session, L1522) the part that must reach the model, the core when there is a marker and the whole text without
one, is compared with the cap. The text itself is never printed or written, and the server's reply is not echoed in an error message.
Exit 0: within the cap, or no cap given; 1: the part that must reach the model is longer than the cap; 2: the server could not be read or its reply is not an initialize result.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

REQUEST = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
           "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "mcp-instructions-length", "version": "1"}}}


class Unreadable(Exception):
    """The endpoint could not be read; the message is fixed text and never carries the reply."""


def fetch(url: str, timeout: float) -> dict:
    if urllib.parse.urlsplit(url).scheme not in ("http", "https"):
        raise Unreadable("the URL is not http or https")
    request = urllib.request.Request(url, data=json.dumps(REQUEST).encode(), method="POST",
                                     headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            kind = response.headers.get("content-type", "")
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        raise Unreadable(f"the endpoint answered HTTP {error.code}") from None
    except (urllib.error.URLError, OSError, UnicodeDecodeError):
        raise Unreadable("the endpoint could not be reached or read") from None
    try:
        if "text/event-stream" in kind:
            data = next(json.loads(line[5:].strip()) for line in raw.splitlines() if line.startswith("data:") and line[5:].strip().startswith("{"))
        else:
            data = json.loads(raw)
    except (ValueError, StopIteration):
        raise Unreadable("the reply is not JSON-RPC") from None
    result = data.get("result") if isinstance(data, dict) else None
    if not isinstance(result, dict):
        raise Unreadable("the reply is not an initialize result")
    return result


def measure(result: dict, marker: str | None) -> dict:
    text = result.get("instructions")
    text = text if isinstance(text, str) else ""
    info = result.get("serverInfo") if isinstance(result.get("serverInfo"), dict) else {}
    out = {"server": str(info.get("name", "")), "version": str(info.get("version", "")), "characters": len(text), "bytes": len(text.encode("utf-8")),
           "sha256_16": hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]}
    if marker:
        at = text.find(marker)
        if at >= 0:
            out.update({"marker": marker, "core": at, "detail": len(text) - at - len(marker)})
        else:
            out["marker"] = None
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("url")
    parser.add_argument("--cap", type=int)
    parser.add_argument("--marker")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args(argv)
    try:
        measured = measure(fetch(args.url, args.timeout), args.marker)
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
        print(f"server {measured['server']} {measured['version']}: instructions {measured['characters']} characters, {measured['bytes']} bytes, sha256 {measured['sha256_16']}")
        if "core" in measured:
            print(f"core before the marker {measured['core']} characters, detail after it {measured['detail']}")
        elif args.marker:
            print("the marker is not in the text")
        if args.cap is not None:
            print(f"cap {args.cap}: the part that must reach the model is {must_reach} characters, {'over' if over else 'within'} the cap; the whole text is "
                  f"{'over' if measured['characters'] > args.cap else 'within'} it by {abs(measured['characters'] - args.cap)}")
    return 1 if over else 0


if __name__ == "__main__":
    sys.exit(main())
