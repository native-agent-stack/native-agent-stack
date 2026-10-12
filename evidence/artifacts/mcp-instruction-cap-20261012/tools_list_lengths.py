#!/usr/bin/env python3
"""tools/list of a streamable-HTTP MCP endpoint: the number of tools and the lengths of their descriptions, as counts only (no description text is printed or stored): tools_list_lengths.py <url>. ASCII only."""
import json
import sys
import urllib.request

url = sys.argv[1]

def post(payload, session=None):
    headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
    if session:
        headers["Mcp-Session-Id"] = session
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST", headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read().decode("utf-8")
        kind = r.headers.get("content-type", "")
        sid = r.headers.get("Mcp-Session-Id")
    if not raw.strip():
        return None, sid
    if "text/event-stream" in kind:
        return next(json.loads(l[5:].strip()) for l in raw.splitlines() if l.startswith("data:") and l[5:].strip().startswith("{")), sid
    return json.loads(raw), sid

init, sid = post({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "probe", "version": "1"}}})
post({"jsonrpc": "2.0", "method": "notifications/initialized"}, sid)
listing, _ = post({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, sid)
tools = listing["result"]["tools"]
lengths = [(t["name"], len(t.get("description") or "")) for t in tools]
print("tools:", len(tools), "| description characters: total", sum(n for _, n in lengths), "| median", sorted(n for _, n in lengths)[len(lengths) // 2], "| max", max(n for _, n in lengths))
for name, n in sorted(lengths, key=lambda x: -x[1])[:6]:
    print(f"  {name:32s} {n}")
