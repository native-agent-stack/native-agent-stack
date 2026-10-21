#!/usr/bin/env python3
"""tools/list of a streamable-HTTP MCP endpoint: the number of tools and the lengths of their descriptions, as counts only (no description text is printed or stored): tools_list_lengths.py URL [--json] [--timeout S].

The lifecycle is initialize, the `notifications/initialized` notification (basic/lifecycle.mdx L107), then tools/list, following `nextCursor` (server/tools.mdx L57-L97), all under
modelcontextprotocol/modelcontextprotocol@1f520964 docs/specification/2025-06-18/. Every request after initialize carries `MCP-Protocol-Version` with the version the server answered initialize with (basic/transports.mdx L240-L250, a MUST) and the `Mcp-Session-Id` the server gave, if
it gave one. The HTTP exchange is the one of tools/adoption/mcp_instructions_length.py, which reads an event stream until the response with the request's id. Exit 0, or 2 when the endpoint cannot be read (a fixed
message, never the reply). Needs this repository's tool: run it from a checkout. ASCII only."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tools" / "adoption"))
import mcp_instructions_length as shared  # noqa: E402

MAX_PAGES = 20


def list_tools(url, timeout):
    """The tools of the endpoint: initialize, the initialized notification, then tools/list page by page."""
    found, headers = shared.exchange(url, shared.REQUEST, timeout)
    negotiated = shared.result_of(found).get("protocolVersion")
    extra = {"MCP-Protocol-Version": negotiated if isinstance(negotiated, str) and negotiated else shared.PROTOCOL_VERSION}
    if headers.get("Mcp-Session-Id"):
        extra["Mcp-Session-Id"] = headers["Mcp-Session-Id"]
    shared.exchange(url, {"jsonrpc": "2.0", "method": "notifications/initialized"}, timeout, extra)
    tools, cursor = [], None
    for page in range(MAX_PAGES):
        params = {"cursor": cursor} if cursor else {}
        found, _ = shared.exchange(url, {"jsonrpc": "2.0", "id": 2 + page, "method": "tools/list", "params": params}, timeout, extra)
        listing = shared.result_of(found)
        if not isinstance(listing.get("tools"), list):
            raise shared.Unreadable("the reply is not a tools/list result")
        tools += [tool for tool in listing["tools"] if isinstance(tool, dict)]
        cursor = listing.get("nextCursor")
        if not cursor:
            return tools
    raise shared.Unreadable("the tool list has more pages than this probe follows")


def summary_of(tools):
    lengths = [(str(tool.get("name", "")), len(tool.get("description") or "")) for tool in tools]
    if not lengths:
        return {"tools": 0, "description_characters": 0, "median": 0, "max": 0, "largest": []}
    return {"tools": len(tools), "description_characters": sum(n for _, n in lengths), "median": sorted(n for _, n in lengths)[len(lengths) // 2], "max": max(n for _, n in lengths),
            "largest": sorted(lengths, key=lambda x: -x[1])[:6]}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Counts of the tools of an MCP endpoint and the lengths of their descriptions.")
    parser.add_argument("url")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args(argv)
    try:
        summary = summary_of(list_tools(args.url, args.timeout))
    except shared.Unreadable as error:
        print(f"tools_list_lengths: {error}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(summary, indent=1))
    else:
        print("tools:", summary["tools"], "| description characters: total", summary["description_characters"], "| median", summary["median"], "| max", summary["max"])
        for name, n in summary["largest"]:
            print(f"  {name:32s} {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
