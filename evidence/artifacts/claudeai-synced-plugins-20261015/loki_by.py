"""Sum 24-hour count_over_time chunks by one field over the Loki retention (#27 synced-plugin inventory)."""
import calendar
import json
import sys
import time
import urllib.parse
import urllib.request

LOKI = "http://127.0.0.1:21300"
field, selector, start = sys.argv[1], sys.argv[2], sys.argv[3]
t = calendar.timegm(time.strptime(start, "%Y-%m-%dT%H:%M:%SZ"))
end = int(time.time())
totals = {}
while t < end:
    stop = min(t + 86400, end)
    q = f"sum by ({field}) (count_over_time({selector} [{stop - t}s]))"
    url = LOKI + "/loki/api/v1/query?" + urllib.parse.urlencode({"query": q, "time": stop * 10**9})
    for r in json.load(urllib.request.urlopen(url, timeout=120))["data"]["result"]:
        k = r["metric"].get(field, "")
        totals[k] = totals.get(k, 0) + int(float(r["value"][1]))
    t = stop
print(json.dumps({"field": field, "selector": selector, "start": start,
                  "end_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(end)),
                  "totals": dict(sorted(totals.items(), key=lambda x: -x[1]))}))
