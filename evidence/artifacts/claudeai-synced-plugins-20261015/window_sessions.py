"""plugin_loaded events per session in one window, with each session's client version (#27)."""
import calendar
import json
import sys
import time
import urllib.parse
import urllib.request

start, end = (calendar.timegm(time.strptime(x, "%Y-%m-%dT%H:%M:%SZ")) for x in sys.argv[1:3])
q = ('sum by (session_id, service_version) (count_over_time({service_name="claude-code"} | event_name="plugin_loaded" '
     f'[{end - start}s]))')
url = "http://127.0.0.1:21300/loki/api/v1/query?" + urllib.parse.urlencode({"query": q, "time": end * 10**9})
rows = json.load(urllib.request.urlopen(url, timeout=120))["data"]["result"]
per = {}
for r in rows:
    key = (r["metric"].get("service_version"), int(float(r["value"][1])))
    per[key] = per.get(key, 0) + 1
print(json.dumps({"window": sys.argv[1:3], "sessions": len(rows),
                  "sessions_by_version_and_plugin_count": {f"{v} loads {n}": c for (v, n), c in sorted(per.items())}}))
