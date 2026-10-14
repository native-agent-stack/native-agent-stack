"""Trading receipt projections, queried through the existing native Loki source."""

LANES = ("A", "B", "C", "lanea", "laneb", "IBKR", "I-llm")
SOURCE = {"type": "loki", "uid": "ns2604-loki"}
STATUS = {0: "Missing receipt", 1: "Active", 2: "Ended", 3: "Blocked", 4: "No session", 5: "Not live", 6: "Stale receipt", 99: "Other status"}
ENDED = {0: "Not recorded", 1: "Duration", 2: "Session end", 3: "Stopped", 4: "Risk limit", 5: "Error", 6: "No session", 99: "Other / unknown"}


def expression(lane, field):
    # Parse only the lane and one numeric value, not every changing JSON field.
    # Native unwrap removes the extracted value from the remaining stream labels.
    return (f'last_over_time({{service_name="trading-lanes"}} | json lane="lane", {field}="{field}" '
            f'| lane="{lane}" | keep lane, {field} | unwrap {field} | __error__="" [10m])')


def dashboard():
    panels = [{"id": 1, "type": "text", "title": "Receipt observations · paper only",
               "gridPos": {"x": 0, "y": 0, "w": 24, "h": 3},
               "options": {"mode": "markdown", "content":
                 "Read-only projections of each lane's own receipts. Refreshed by the existing observer. "
                 "Rates for A/B and IBKR are receipt stage averages; C and POST arms use the trailing minute of "
                 "recorded events. Submissions are not fills. **Unavailable** means the source does not record the metric. "
                 "Receipt time and status expose stale/ended runs; a fresh observation does not make a prior session live. "
                 "IBKR has no session tonight; its last session is retained. I-llm stays not live until wired."}}]
    specs = (("orders_per_min", "Orders/min", "suffix:orders/min"), ("fills_per_min", "Fills/min", "suffix:fills/min"),
             ("cancels_per_min", "Cancels/min", "suffix:cancels/min"), ("cash_use_ratio", "Cash use / equity", "percentunit"),
             ("open_positions", "Open positions", "short"), ("realized_pnl_usd", "Realized P&L", "currencyUSD"),
             ("status_code", "Status", "short"), ("ended_by_code", "Ended by", "short"))
    y, identifier = 3, 2
    for lane in LANES:
        panels.append({"id": identifier, "type": "row", "title": lane, "collapsed": False,
                       "gridPos": {"x": 0, "y": y, "w": 24, "h": 1}, "panels": []})
        identifier += 1
        for index, (field, title, unit) in enumerate(specs):
            values = STATUS if field == "status_code" else ENDED if field == "ended_by_code" else {-1: "Unavailable"}
            mappings = [{"type": "value", "options": {str(value): {"text": text} for value, text in values.items()}}]
            if field == "realized_pnl_usd":
                # Real P&L can equal -1; availability uses a separate impossible sentinel.
                mappings = [{"type": "value", "options": {"-9007199254740991": {"text": "Not recorded"},
                             "-1e+100": {"text": "Not recorded"}}}]
            if field in ("orders_per_min", "fills_per_min", "cancels_per_min"):
                title += " (last stage)" if lane in ("A", "B") else " (last session)" if lane == "IBKR" else " (last minute)"
            panels.append({"id": identifier, "type": "stat", "title": lane + " · " + title,
                           "description": "Latest receipt-derived observation in ten minutes. See receipt time and status for historical/stale sessions.",
                           "datasource": SOURCE, "gridPos": {"x": index * 3, "y": y + 1, "w": 3, "h": 4},
                           "fieldConfig": {"defaults": {"unit": unit, "mappings": mappings, "noValue": "Not recorded",
                              "thresholds": {"mode": "absolute", "steps": [{"color": "blue", "value": None}]}}, "overrides": []},
                           "options": {"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
                                       "colorMode": "value", "graphMode": "none", "textMode": "auto"},
                           "targets": [{"refId": "A", "expr": expression(lane, field), "queryType": "instant"}]})
            identifier += 1
        panels.append({"id": identifier, "type": "stat", "title": lane + (" · No session since / last receipt" if lane == "IBKR" else " · Last receipt time"),
                       "description": "IBKR: no session since this receipt time. I-llm: source Unix seconds, Not recorded until live. Other lanes: source timestamp, not observation time.",
                       "datasource": SOURCE, "gridPos": {"x": 0, "y": y + 5, "w": 24, "h": 2},
                       "fieldConfig": {"defaults": {"unit": "none" if lane == "I-llm" else "dateTimeAsIso", "noValue": "Not recorded", "mappings": [{"type": "value", "options": {"-1" if lane == "I-llm" else "-1000": {"text": "Not recorded"}}}]}, "overrides": []},
                       "options": {"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}, "graphMode": "none", "textMode": "value"},
                       "targets": [{"refId": "A", "expr": expression(lane, "source_unix") + ("" if lane == "I-llm" else " * 1000"), "queryType": "instant"}]})
        identifier += 1
        y += 7
        if lane == "IBKR":
            panels.append({"id": identifier, "type": "timeseries", "title": "IBKR wire messages/s", "datasource": SOURCE,
                           "description": "Own last-session wire mean/peak. No session tonight; these are retained receipt values. 45/s governor, 50/s broker cap are constants.",
                           "gridPos": {"x": 0, "y": y, "w": 24, "h": 5},
                           "fieldConfig": {"defaults": {"unit": "ops", "min": 0,
                              "thresholds": {"mode": "absolute", "steps": [{"color": "green", "value": None}, {"color": "orange", "value": 45}, {"color": "red", "value": 50}]},
                              "custom": {"thresholdsStyle": {"mode": "line"}}}, "overrides": []},
                           "targets": [{"refId": code, "expr": expression(lane, field), "legendFormat": label, "queryType": "range"}
                                       for code, field, label in [("A", "wire_mean_per_s", "Session mean"), ("B", "wire_peak_per_s", "Session peak")]],
                           "options": {"legend": {"showLegend": True, "displayMode": "list", "placement": "bottom"}, "tooltip": {"mode": "multi"}}})
            identifier += 1
            y += 5
    return {"uid": "trading-lanes", "title": "Trading lanes", "schemaVersion": 41, "version": 1,
            "editable": False, "timezone": "browser", "refresh": "30s", "time": {"from": "now-10m", "to": "now"},
            "tags": ["paper", "trading", "receipts"], "panels": panels, "templating": {"list": []},
            "annotations": {"list": []}, "links": []}
