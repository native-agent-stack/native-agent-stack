"""Count Claude Code invocations of finalize-all winners in Loki over pin-bound windows (F2, Claude side).

Count of record: docs/decisions/2026-09-26-tool-invoke-rates.md. The Collector copies the MCP server name, the MCP tool name
and a derived shell_rtk boolean from Claude Code's tool events; no command text is stored. Each window is a closed interval
[window_start, window_end] counted in 24-hour chunks with count_over_time at the chunk end, summed. Prints JSON only:
aggregate counts, never log lines.
"""
import calendar
import json
import sys
import time
import urllib.parse
import urllib.request

LOKI = "http://127.0.0.1:21300"
CHUNK = 86400
BASE = '{service_name="claude-code"}'


def epoch(text):
    return calendar.timegm(time.strptime(text, "%Y-%m-%dT%H:%M:%SZ"))


def utc(seconds):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(seconds))


def count(selector, start, end):
    """Lines matching selector with timestamps in (start, end], in chunks of at most CHUNK seconds."""
    total, cursor = 0, start
    while cursor < end:
        stop = min(cursor + CHUNK, end)
        query = f"sum(count_over_time({selector} [{stop - cursor}s]))"
        url = LOKI + "/loki/api/v1/query?" + urllib.parse.urlencode({"query": query, "time": stop * 10**9})
        result = json.load(urllib.request.urlopen(url, timeout=300))["data"]["result"]
        total += int(result[0]["value"][1]) if result else 0
        cursor = stop
    return total


SPECS = [
    # id, selector filter after BASE, window_start, window_end ("read" = read time)
    ("claude-code@2.1.295/tool_result", '| event_name="tool_result" | service_version="2.1.295"', "2026-10-08T20:12:18Z", "2026-10-10T05:04:41Z"),
    ("claude-code@2.1.295/api_request", '| event_name="api_request" | service_version="2.1.295"', "2026-10-08T20:12:18Z", "2026-10-10T05:04:41Z"),
    ("claude-code@2.1.300/tool_result", '| event_name="tool_result" | service_version="2.1.300"', "2026-10-14T20:16:22Z", "read"),
    ("claude-code@2.1.300/api_request", '| event_name="api_request" | service_version="2.1.300"', "2026-10-14T20:16:22Z", "read"),
    ("serena@c6fbd1c5", '| event_name="tool_result" | mcp_server_name="serena"', "2026-10-05T16:09:44Z", "read"),
    ("qmd@2.8.3", '| event_name="tool_result" | mcp_server_name="qmd"', "2026-10-05T10:22:24Z", "read"),
    ("headroom@0.40.0", '| event_name="tool_result" | mcp_server_name="headroom"', "2026-10-08T05:05:42Z", "read"),
    ("rtk@0.51.0", '| event_name="tool_result" | tool_name="Bash" | shell_rtk="true"', "2026-10-05T19:04:27Z", "read"),
    ("promptfoo@0.123.1", '| event_name="tool_result" | mcp_server_name="promptfoo"', "2026-10-04T15:44:42Z", "2026-10-08T04:54:52Z"),
    ("socraticode@1.15.0", '| event_name="tool_result" | mcp_server_name="socraticode"', "2026-10-04T15:44:42Z", "2026-10-07T02:24:47Z"),
    ("ai-memory@pre-2.6.0", '| event_name="tool_result" | mcp_server_name="ai-memory"', "2026-10-04T15:44:42Z", "2026-10-08T05:18:10Z"),
    ("ai-memory@2.6.3", '| event_name="tool_result" | mcp_server_name="ai-memory"', "2026-10-10T22:09:02Z", "read"),
    ("socraticode@1.16.0", '| event_name="tool_result" | mcp_server_name="socraticode"', "2026-10-07T20:34:02Z", "read"),
    ("skill:iterative-retrieval", '| event_name="skill_activated" | skill_name="iterative-retrieval"', "2026-10-04T15:44:42Z", "read"),
    ("skill:search-first", '| event_name="skill_activated" | skill_name="search-first"', "2026-10-04T15:44:42Z", "read"),
    ("skill:typesafe-ai", '| event_name="skill_activated" | skill_name="typesafe-ai"', "2026-10-04T15:44:42Z", "read"),
    ("skill:gh-fix-ci", '| event_name="skill_activated" | skill_name="gh-fix-ci"', "2026-10-04T15:44:42Z", "read"),
    ("skill:gh-address-comments", '| event_name="skill_activated" | skill_name="gh-address-comments"', "2026-10-04T15:44:42Z", "read"),
]


def main():
    read = int(sys.argv[1]) if len(sys.argv) > 1 else int(time.time()) // 60 * 60
    rows = []
    for spec_id, selector, start, end in SPECS:
        end_s = read if end == "read" else epoch(end)
        start_s = epoch(start)
        rows.append({"id": spec_id, "logql": f"{BASE} {selector}", "window_start": utc(start_s), "window_end": utc(end_s),
                     "calls": count(f"{BASE} {selector}", start_s, end_s)})
    print(json.dumps({"loki": LOKI, "read_utc": utc(int(time.time())), "chunk_seconds": CHUNK, "rows": rows}, indent=1))


if __name__ == "__main__":
    main()
