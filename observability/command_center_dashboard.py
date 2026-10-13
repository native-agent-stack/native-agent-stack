"""Command center god view (uid cc-god-view) for NativeStack2604's Grafana.

One board over the platforms' own data: Loki and Prometheus fed by the OTel Collector, the hcom
status records that observability/grand-dashboard/hcom_status.py publishes, and OmniRoute's routing
spans. Session-level detail stays in agentsview (http://127.0.0.1:21808); this board links to it.
Panels that already exist on `ecosystem-native` and `cc-lanes` are copied with their queries
unchanged (`reuse`); the new panels add the lane key to the same native events and counters.

Sources at the deployed pins:
- grafana/grafana v13.2.3 (6193dc03): instant queries arrive as table frames whose value column is
  `Value #<refId>`; `merge` joins frames on the fields every frame shares and merges rows whose other
  fields do not conflict (packages/grafana-data/src/transformations/transformers/merge.ts:25-95,189-205);
  `organize` orders, then renames by display name (organize.ts:36-46, rename.ts:43-68). An empty
  Prometheus table frame keeps no label columns and stops `merge` from finding a key, so merged tables
  are Loki-only (empty Loki results return no frame) and Prometheus measures get their own panels.
- grafana/loki v3.7.8 (09e6ce2f): `__timestamp__` and `unixEpoch` in label_format templates
  (pkg/logql/log/fmt.go:21,117,122) and the on/unless/or vector operators (pkg/logql/syntax/lex.go:41-49).
- prometheus/prometheus v3.15.0: label_replace and increase.
- aannoo/hcom v0.7.28 (b2a7c192): status values active*, listening, blocked*, launching, inactive
  (src/commands/status.rs:192-197); listening gate context tui:prompt-has-text
  (src/instance_lifecycle.rs:597).
- openai/codex rust-v0.162.1 (092d3acd): codex.skill.injected (codex-rs/core/src/skills.rs:66-72),
  codex.turn.e2e_duration_ms (codex-rs/otel/src/metrics/names.rs:35).
- OmniRoute c1e30b76 open-sse/services/routing/otel.ts:193-216 routing span attributes, through the
  Collector's spanmetrics connector (opentelemetry-collector-contrib v0.162.0).
The coverage and gap record is docs/decisions/2026-10-13-command-center-god-view.md.
"""
import copy

LOKI = {"type": "loki", "uid": "ns2604-loki"}
PROMETHEUS = {"type": "prometheus", "uid": "ns2604-prometheus"}
AGENTSVIEW = "http://127.0.0.1:21808"
NOTE = "docs/decisions/2026-10-13-command-center-god-view.md"
NOTE_URL = "https://github.com/native-agent-stack/native-agent-stack/blob/main/" + NOTE

CLIENTS = '{service_name=~"codex-app-server|codex_exec|codex_cli_rs|claude-code"}'
CLAUDE = '{service_name="claude-code"}'
RUNTIMES = '{service_name=~"pi|opencode|goose|qwen-code|oh-my-pi|ns-opencode-.+|ns-pi-.+|codex_sdk_ts"}'
HCOM = '{service_name="agent-stack-lanes",record_kind="hcom"}'
RUNTIME_JOBS = 'pi|opencode|goose|qwen-code|oh-my-pi'
TOOL_EVENTS = '| event_name=~"tool_result|codex.tool_result" | tool_family!="code_mode"'
CLIENT_KEY = ('| label_format kind=`{{ if eq .service_name "claude-code" }}Claude session'
              '{{ else }}Codex lane{{ end }}`, lane=`{{ or .ecosystem_lane "unattributed" }}`')
RUNTIME_KEY = ('| label_format kind=`{{ if eq .service_name "codex_sdk_ts" }}SDK worker'
               '{{ else }}runtime worker{{ end }}`, lane=`{{ or .ecosystem_lane .service_name }}`')
CLAUDE_KEY = '| label_format kind="Claude session", lane=`{{ or .ecosystem_lane "unattributed" }}`'
HCOM_KEY = '| json | label_format lane="{{ or .base_name .name }}"'
PROMPT = '(or (eq .prompt_has_text "1") (eq .status_context "tui:prompt-has-text"))'
STUCK = f'{{{{ if and (ne .unread_count "") (ne .unread_count "0") {PROMPT} }}}}1{{{{ else }}}}0{{{{ end }}}}'
PROMPT_FLAG = f'{{{{ if {PROMPT} }}}}1{{{{ else }}}}0{{{{ end }}}}'
LAST_EVENT = '| label_format last_unix=`{{ __timestamp__ | unixEpoch }}` | unwrap last_unix | __error__=""'
WIRING_GAP = [{"type": "value", "options": {"0": {"text": "0 · wiring gap", "color": "red", "index": 0}}},
              {"type": "special", "options": {"match": "null", "result": {"text": "—", "color": "transparent",
                                                                          "index": 1}}}]
CAVEAT = ('A zero row is a lane with tool results and no such call in the hour: flagged as a wiring gap, '
          'which proves non-use only once exposure and a full window are qualified.')


def prom_lane(expr, kind="Codex lane"):
    """Prometheus series keyed like the Loki rows: lane (unattributed when ecosystem_lane is empty) and kind."""
    keyed = (f'label_replace(label_replace({expr}, "lane", "$1", "ecosystem_lane", "(.+)"), '
             f'"lane", "unattributed", "ecosystem_lane", "")')
    return f'label_replace(sum by (lane) ({keyed}), "kind", "{kind}", "", "")'


def loki(expr, name, ref):
    """One instant LogQL query; `name` titles its `Value #<ref>` column after the merge."""
    return {"refId": ref, "expr": expr, "queryType": "instant", "datasource": LOKI, "legendFormat": name}


def prom(expr, name, ref):
    return {"refId": ref, "expr": expr, "instant": True, "range": False, "format": "table",
            "datasource": PROMETHEUS, "legendFormat": name}


def merged(targets, order, rename=None):
    """Instant table frames to one row per key: drop Time, merge on shared label columns, title value columns."""
    names = dict(rename or {})
    for target in targets:
        names[f'Value #{target["refId"]}'] = target["legendFormat"]
        if len(targets) == 1:
            names["Value"] = target["legendFormat"]
    # organize orders before it renames (organize.ts:36-46), so the order uses the pre-rename names.
    original = {title: name for name, title in names.items() if name != "Value"}
    return [{"id": "organize", "options": {"excludeByName": {"Time": True}}},
            {"id": "merge", "options": {}},
            {"id": "organize", "options": {"renameByName": names,
                                           "indexByName": {original.get(name, name): i
                                                           for i, name in enumerate(order)}}}]


def override(name, **properties):
    return {"matcher": {"id": "byName", "options": name},
            "properties": [{"id": key.replace("__", "."), "value": value} for key, value in properties.items()]}


def color_cells(name, mappings, thresholds=None):
    props = {"mappings": mappings, "custom__cellOptions": {"type": "color-background"}}
    if thresholds:
        props.update(thresholds={"mode": "absolute", "steps": thresholds}, color={"mode": "thresholds"})
    return override(name, **props)


def dashboard(native, lanes):
    """Compose from the rendered `ecosystem-native` and `cc-lanes` boards (both already retargeted)."""
    panels = []
    sources = {"ecosystem-native": {p["id"]: p for p in native["panels"]},
               "cc-lanes": {p["title"]: p for p in lanes["panels"]}}

    def place(item, x, y, w, h):
        item["id"] = len(panels) + 1
        item["gridPos"] = {"x": x, "y": y, "w": w, "h": h}
        panels.append(item)
        return item

    def reuse(board, key, x, y, w, h):
        item = copy.deepcopy(sources[board][key])
        item["description"] = (item.get("description", "") +
                               f" Reused unchanged from the {board} dashboard.").strip()
        return place(item, x, y, w, h)

    def row(title, y):
        return place({"type": "row", "title": title, "collapsed": False, "panels": []}, 0, y, 24, 1)

    def text(title, content, x, y, w, h):
        return place({"type": "text", "title": title,
                      "options": {"mode": "markdown", "content": content}}, x, y, w, h)

    def table(title, description, targets, layout, x, y, w, h, overrides=(), datasource=LOKI):
        order, rename, sort = layout
        transformations = merged(targets, order, rename)
        if sort:
            transformations.append({"id": "sortBy", "options": {"sort": [{"field": sort, "desc": True}]}})
        return place({"type": "table", "title": title, "description": description, "datasource": datasource,
                      "targets": targets, "transformations": transformations,
                      "fieldConfig": {"defaults": {"noValue": "—", "custom": {"minWidth": 60}},
                                      "overrides": list(overrides)},
                      "options": {"showHeader": True, "cellHeight": "sm"}}, x, y, w, h)

    def layout(order, rename=None, sort=None):
        return order, rename, sort

    text("Command center", (
        'One view of every lane and worker from the platforms\' own data: Codex lanes and Claude sessions '
        '(OTel Collector to Loki and Prometheus), hcom status records, runtime workers that export OTLP, and '
        'OmniRoute routing spans. **No data** or **—** means the source sent nothing in the window, never zero '
        'use. Claude sessions without `ecosystem.lane` show as **unattributed**; peer Claude sessions and '
        'subagents that share a coordinator\'s writer appear only through `query_source` and `subagent_type`.\n\n'
        f'Session level: [agentsview]({AGENTSVIEW}) (`/sessions/<agent>/<session id>`) · '
        '[Lanes](/d/cc-lanes) · [Native agent ecosystem](/d/ecosystem-native) · [Token layer](/d/token-layer) · '
        '[Gateway usage](http://127.0.0.1:21128/dashboard/analytics) · '
        f'[Coverage and gaps]({NOTE_URL})'), 0, 0, 24, 4)

    # (a) Lane roster ---------------------------------------------------------------------------------
    row("Lane roster", 4)
    hcom_active = f'max by (lane) (count_over_time({HCOM} {HCOM_KEY} | status=~"active.*" [2m]))'
    events_20m = (f'max by (lane) (count_over_time({CLIENTS} | ecosystem_lane!="" '
                  f'| label_format lane="{{{{.ecosystem_lane}}}}" [20m]))')
    state = (f'(({hcom_active} unless on (lane) {events_20m}) * 0 + 3)'
             f' or ({hcom_active} * 0 + 2)'
             f' or (max by (lane) (count_over_time({HCOM} {HCOM_KEY} | status="listening" [2m])) * 0 + 1)'
             f' or (max by (lane) (count_over_time({HCOM} {HCOM_KEY} [2m])) * 0)')
    roster = [
        loki(f'((max by (kind, lane, role) (max_over_time({CLIENTS} {CLIENT_KEY}, role=" " {LAST_EVENT} [1h]))) or '
             f'(max by (kind, lane, role) (max_over_time({RUNTIMES} {RUNTIME_KEY}, role=" " {LAST_EVENT} '
             '[24h])))) * 1000', "Last event", "A"),
        loki(f'(sum by (kind, lane, model) (count_over_time({CLIENTS} | model!="" {CLIENT_KEY} [1h]))) or '
             f'(sum by (kind, lane, model) (count_over_time({RUNTIMES} | model!="" {RUNTIME_KEY} [24h])))',
             "Model events", "B"),
        loki(f'count by (kind, lane) (sum by (kind, lane, sid) (count_over_time({CLIENTS} {CLIENT_KEY}, '
             'sid=`{{ or .conversation_id .session_id }}` | sid!="" [1h])))', "Sessions (1 h)", "C"),
        loki(f'(sum by (kind, lane) (count_over_time({CLIENTS} {CLIENT_KEY} [20m]))) or '
             f'(sum by (kind, lane) (count_over_time({RUNTIMES} {RUNTIME_KEY} [20m])))', "Events (20 min)", "D"),
        loki(f'max by (lane, hcom_status, tag) (max_over_time({HCOM} {HCOM_KEY}, hcom_status="{{{{.status}}}}" '
             '| unwrap status_age_seconds | __error__="" [1m]))', "hcom status age", "E"),
        loki(state, "State", "F")]
    table(
        "Lane roster · kind, lane, model, last event and state",
        'One row per lane, plus one unattributed row per client kind (a lane with a second model in the window '
        'shows a second row). Last event, model and sessions: Codex and Claude events in the last hour, runtime '
        'and SDK workers in the last 24 h (low volume). State joins hcom with telemetry: STALE = hcom status '
        'active* and no Codex or Claude event for the lane in 20 min; ACTIVE = hcom active* with events; '
        'LISTENING = hcom listening (idle, waiting for messages); "no hcom record" = no hcom snapshot for the '
        'lane in 2 min. The join key is the hcom instance name (base_name), which is what a lane exports as '
        'ecosystem.lane. Role: no recorded role source exists in telemetry or hcom, so the column stays blank; '
        'the hcom tag recorded at launch is shown beside it. Kinds come from service.name: codex-* = Codex lane '
        '(the Codex SDK worker runs codex app-server and shows here), claude-code = Claude session (the Claude '
        'Agent SDK too), codex_sdk_ts = SDK worker, other OTLP runtimes = runtime worker.',
        roster,
        layout(["kind", "lane", "role", "tag", "model", "Model events", "Last event", "Sessions (1 h)",
                "Events (20 min)", "hcom_status", "hcom status age", "State"],
               {"role": "Role", "tag": "Tag (hcom)", "hcom_status": "hcom status", "model": "Model"}),
        0, 5, 24, 11,
        [override("Last event", unit="dateTimeFromNow"),
         override("hcom status age", unit="s"),
         color_cells("Events (20 min)", [{"type": "special", "options": {"match": "null", "result": {
             "text": "none · idle ≥ 20 min", "color": "orange", "index": 0}}}],
             [{"color": "green", "value": None}]),
         color_cells("State", [{"type": "value", "options": {
             "0": {"text": "OTHER (hcom)", "color": "blue", "index": 0},
             "1": {"text": "LISTENING", "color": "green", "index": 1},
             "2": {"text": "ACTIVE", "color": "green", "index": 2},
             "3": {"text": "STALE", "color": "red", "index": 3}}},
             {"type": "special", "options": {"match": "null", "result": {
                 "text": "no hcom record", "color": "transparent", "index": 4}}}])])

    hcom = reuse("cc-lanes", "Latest recorded hcom status and root-name lookup", 0, 16, 12, 9)
    group = next(t for t in hcom["transformations"] if t["id"] == "groupBy")
    for key in ("base_name", "tag", "prompt_has_text"):
        group["options"]["fields"][key] = {"operation": "aggregate", "aggregations": ["last"]}
    hcom["description"] += (' Command center adds base_name (the instance name that ecosystem.lane uses), the '
                            'recorded hcom tag and the prompt_has_text boolean (hcom term prompt_empty, never the '
                            'input text).')

    stuck = [
        loki(f'max by (lane) (max_over_time({HCOM} {HCOM_KEY} | unwrap unread_count | __error__="" [1m]))',
             "Unread", "A"),
        loki(f'max by (lane) (max_over_time({HCOM} {HCOM_KEY}, prompt_flag=`{PROMPT_FLAG}` '
             '| unwrap prompt_flag | __error__="" [1m]))', "Prompt has text", "B"),
        loki(f'max by (lane, status_context) (max_over_time({HCOM} {HCOM_KEY} | unwrap status_age_seconds '
             '| __error__="" [1m]))', "Status age", "C"),
        loki(f'(min by (lane) (min_over_time({HCOM} {HCOM_KEY}, stuck=`{STUCK}` | unwrap stuck | __error__="" '
             f'[10m])) == 1) and on (lane) (sum by (lane) (count_over_time({HCOM} {HCOM_KEY} [10m])) >= 15)',
             "Stuck ≥ 10 min", "D")]
    table(
        "STUCK lanes · undelivered messages behind prompt text (10 min)",
        'A lane is STUCK when, in every hcom snapshot of the last 10 minutes (at least 15 of the 30-second '
        'snapshots), unread_count > 0 and its PTY prompt holds text: hcom term reports prompt_empty=false or '
        'hcom list reports the listening gate context tui:prompt-has-text. Queued messages then wait behind '
        'uncommitted keystrokes. Only booleans and counts leave hcom; input text never does. Unread and prompt '
        'columns are the last minute. No data: the hcom snapshot did not reach Loki in the window.',
        stuck,
        layout(["lane", "Unread", "Prompt has text", "status_context", "Status age", "Stuck ≥ 10 min"],
               {"status_context": "hcom gate context"}, "Unread"),
        12, 16, 12, 9,
        [override("Status age", unit="s"),
         color_cells("Unread", [], [{"color": "transparent", "value": None}, {"color": "orange", "value": 1}]),
         color_cells("Prompt has text", [{"type": "value", "options": {
             "0": {"text": "empty", "color": "transparent", "index": 0},
             "1": {"text": "text in prompt", "color": "orange", "index": 1}}}]),
         color_cells("Stuck ≥ 10 min", [{"type": "value", "options": {
             "1": {"text": "STUCK", "color": "red", "index": 0}}},
             {"type": "special", "options": {"match": "null", "result": {
                 "text": "", "color": "transparent", "index": 1}}}])],
        datasource=LOKI)

    # (b) Progress ------------------------------------------------------------------------------------
    row("Progress · last hour", 25)
    table(
        "Turns and tool calls per lane (1 h)",
        'Started user turns (user_prompt and codex.user_prompt events, the cc-lanes contract; completed Codex '
        'turns per minute are in the next panel) and tool calls (tool_result and codex.tool_result events, '
        'without Codex code-mode wrappers whose inner calls are counted).',
        [loki(f'sum by (kind, lane) (count_over_time({CLIENTS} | event_name=~"user_prompt|codex.user_prompt" '
              f'{CLIENT_KEY} [1h]))', "Started turns", "A"),
         loki(f'sum by (kind, lane) (count_over_time({CLIENTS} {TOOL_EVENTS} {CLIENT_KEY} [1h]))',
              "Tool calls", "B")],
        layout(["kind", "lane", "Started turns", "Tool calls"], sort="Tool calls"),
        0, 26, 8, 9, [override(name, decimals=0) for name in ("Started turns", "Tool calls")], datasource=LOKI)
    reuse("ecosystem-native", 40, 8, 26, 6, 9)
    reuse("cc-lanes", "Per-lane native tool-result rate", 14, 26, 6, 9)
    table(
        "Runtime worker tool calls (24 h)",
        'Execute-tool spans (gen_ai.tool.name set) that pi, OpenCode, goose, Qwen Code and oh-my-pi export '
        'themselves, counted by the Collector spanmetrics connector; their logs carry no ecosystem.lane, so '
        'service.name is the lane.',
        [prom(f'sum by (service_name) (increase(traces_span_metrics_calls_total{{service_name=~"{RUNTIME_JOBS}",'
              'gen_ai_tool_name!=""}[24h]))', "Tool calls", "A")],
        layout(["service_name", "Tool calls"], {"service_name": "Runtime worker"}, "Tool calls"),
        20, 26, 4, 9, [override("Tool calls", decimals=0)], datasource=PROMETHEUS)

    # (c) Invoke rates --------------------------------------------------------------------------------
    row("Invoke rates · skills, MCP and subagents per lane", 35)
    tools = f'sum by (kind, lane) (count_over_time({CLIENTS} {TOOL_EVENTS} {CLIENT_KEY} [1h]))'
    claude_tools = f'sum by (kind, lane) (count_over_time({CLAUDE} | event_name="tool_result" {CLAUDE_KEY} [1h]))'
    codex_turns = prom_lane('increase(codex_turn_e2e_duration_ms_milliseconds_count[1h])')
    gap_columns = ("MCP calls", "Claude skills", "Subagent launches")
    table(
        "Skills, MCP and subagent calls per lane (1 h) · zero = wiring gap",
        'MCP: tool results whose family is mcp (Claude needs OTEL_LOG_TOOL_DETAILS=1 for server names). Claude '
        'skills: skill_activated events (Codex skills are the next panel). Subagents: accepted Claude '
        'Agent/Task decisions and Codex spawn messages. ' + CAVEAT,
        [loki(f'(sum by (kind, lane) (count_over_time({CLIENTS} {TOOL_EVENTS} | tool_family="mcp" {CLIENT_KEY} '
              f'[1h]))) or (0 * {tools})', "MCP calls", "A"),
         loki(f'(sum by (kind, lane) (count_over_time({CLAUDE} | event_name="skill_activated" {CLAUDE_KEY} '
              f'[1h]))) or (0 * {claude_tools})', "Claude skills", "B"),
         loki(f'(sum by (kind, lane) (count_over_time({CLIENTS} | (event_name="tool_decision" and decision="accept" '
              f'and tool_name=~"Agent|Task") or (event_name="codex.agent_communication" and kind="spawn" and '
              f'state="send") {CLIENT_KEY} [1h]))) or (0 * {tools})', "Subagent launches", "C"),
         loki(tools, "Tool calls", "D")],
        layout(["kind", "lane", "Tool calls", "MCP calls", "Claude skills", "Subagent launches"], sort="Tool calls"),
        0, 36, 12, 9,
        [color_cells(name, WIRING_GAP, [{"color": "green", "value": None}]) for name in gap_columns],
        datasource=LOKI)
    table(
        "Codex skill injections per lane (1 h) · zero = wiring gap",
        'codex.skill.injected counters (openai/codex rust-v0.162.1 core/src/skills.rs:66-72), with a zero row '
        'for each Codex lane that completed a turn in the hour. ' + CAVEAT,
        [prom(f'({prom_lane("increase(codex_skill_injected_total[1h])")}) or (0 * {codex_turns})',
              "Codex skills", "A")],
        layout(["lane", "Codex skills"], {"lane": "Codex lane"}),
        12, 36, 4, 9, [color_cells("Codex skills", WIRING_GAP, [{"color": "green", "value": None}]),
                       override("kind", custom__hidden=True)], datasource=PROMETHEUS)
    table(
        "MCP calls per lane and server (1 h)",
        'Native MCP server names per lane, Codex and Claude. A Claude row without a server name is a session '
        'started without OTEL_LOG_TOOL_DETAILS=1 (see the integrity panel below).',
        [loki(f'sum by (kind, lane, mcp_server_name) (count_over_time({CLIENTS} {TOOL_EVENTS} | tool_family="mcp" '
              f'{CLIENT_KEY} [1h]))', "MCP calls", "A")],
        layout(["kind", "lane", "mcp_server_name", "MCP calls"], {"mcp_server_name": "MCP server"}, "MCP calls"),
        16, 36, 8, 9, datasource=LOKI)
    reuse("ecosystem-native", 31, 0, 45, 8, 8)
    reuse("ecosystem-native", 32, 8, 45, 8, 8)
    reuse("ecosystem-native", 33, 16, 45, 8, 8)
    reuse("ecosystem-native", 37, 0, 53, 24, 5)

    # (d) Errors --------------------------------------------------------------------------------------
    row("Errors · tool and MCP failures, gateway status, usage limits", 58)
    reuse("ecosystem-native", 41, 0, 59, 8, 8)
    reuse("ecosystem-native", 42, 8, 59, 8, 8)
    claude_failed = (f'sum by (lane) (count_over_time({CLAUDE} | event_name="tool_result" | success="false" '
                     f'{CLAUDE_KEY} [1h]))')
    claude_all = f'sum by (lane) (count_over_time({CLAUDE} | event_name="tool_result" {CLAUDE_KEY} [1h]))'
    place({"type": "bargauge", "title": "Claude tool failure share by lane (1 h)", "datasource": LOKI,
           "description": 'Claude tool_result events with success=false over all tool results in the hour, '
                          'by lane. The red step matches the Codex lane alert threshold (10%).',
           "targets": [{"refId": "A", "expr": f'({claude_failed} or (0 * {claude_all})) / {claude_all}',
                        "queryType": "instant", "legendFormat": "{{lane}}", "datasource": LOKI}],
           "fieldConfig": {"defaults": {"unit": "percentunit", "min": 0, "max": 1, "noValue": "no data",
                                        "thresholds": {"mode": "absolute", "steps": [
                                            {"color": "green", "value": None}, {"color": "red", "value": 0.1}]},
                                        "color": {"mode": "thresholds"}}, "overrides": []},
           "options": {"orientation": "horizontal", "displayMode": "basic", "showUnfilled": True,
                       "reduceOptions": {"values": False, "calcs": ["lastNotNull"], "fields": ""}}},
          16, 59, 8, 8)
    reuse("ecosystem-native", 43, 0, 67, 6, 8)
    reuse("cc-lanes", "Native API errors and rate limits", 6, 67, 6, 8)
    gateway = 'traces_span_metrics_calls_total{service_name="omniroute"'

    def share(cls):
        return (f'sum(increase({gateway},omniroute_routing_status=~"{cls}.."}}[1h])) / '
                f'sum(increase({gateway}}}[1h]))')
    table(
        "Gateway 4xx and 5xx by provider (1 h)",
        'OmniRoute routing spans with a 4xx or 5xx omniroute.routing.status: 429 is a usage limit, 499 a client '
        'cancel, 502 an upstream failure. The gateway does not set span status, so the vendor status attribute '
        'is used, not status_code.',
        [prom(f'sum by (gen_ai_provider_name, omniroute_routing_status) (increase({gateway},'
              'omniroute_routing_status=~"[45].."}[1h]))', "Requests", "A")],
        layout(["gen_ai_provider_name", "omniroute_routing_status", "Requests"],
               {"gen_ai_provider_name": "Provider", "omniroute_routing_status": "HTTP status"}, "Requests"),
        12, 67, 6, 8, [override("Requests", decimals=0)], datasource=PROMETHEUS)
    place({"type": "stat", "title": "Gateway 4xx and 5xx share of routed requests (1 h)", "datasource": PROMETHEUS,
           "description": 'Share of all OmniRoute-routed requests in the hour whose routing status was 4xx '
                          '(usage limits included) or 5xx.',
           "targets": [{"refId": cls, "expr": share(cls[0]), "instant": True, "range": False,
                        "legendFormat": f"{cls} share", "datasource": PROMETHEUS} for cls in ("4xx", "5xx")],
           "fieldConfig": {"defaults": {"unit": "percentunit", "decimals": 1, "noValue": "no data",
                                        "thresholds": {"mode": "absolute", "steps": [
                                            {"color": "green", "value": None}, {"color": "red", "value": 0.05}]},
                                        "color": {"mode": "thresholds"}}, "overrides": []},
           "options": {"reduceOptions": {"values": False, "calcs": ["lastNotNull"], "fields": ""},
                       "textMode": "value_and_name", "colorMode": "background"}},
          18, 67, 6, 8)

    # (e) Gateway -------------------------------------------------------------------------------------
    row("Gateway · provider and model (GPT, Muse, Claude)", 75)
    family = f'increase({gateway}}}[1h])'
    for name, pattern in (("GPT", ".*gpt.*"), ("Muse", ".*muse.*"), ("Claude", ".*claude.*")):
        family = f'label_replace({family}, "family", "{name}", "gen_ai_request_model", "(?i){pattern}")'
    family = f'label_replace({family}, "family", "other", "family", "")'
    table(
        "Gateway requests by family, provider and model (1 h)",
        'OmniRoute routing spans per requested model, grouped into GPT, Muse and Claude by model name. The '
        'muse-code provider is the Muse Code route; Muse Code itself exports no OTLP and is not in agentsview '
        '(coverage row below). Gateway spans carry no lane, so these totals are not assigned to lanes.',
        [prom(f'sum by (family, gen_ai_provider_name, gen_ai_request_model) ({family})', "Requests", "A")],
        layout(["family", "gen_ai_provider_name", "gen_ai_request_model", "Requests"],
               {"family": "Family", "gen_ai_provider_name": "Provider", "gen_ai_request_model": "Model"},
               "Requests"),
        0, 76, 8, 9, [override("Requests", decimals=0)], datasource=PROMETHEUS)
    reuse("cc-lanes", "Gateway routing rate by provider and model", 8, 76, 8, 9)
    reuse("cc-lanes", "Gateway routing rate by outcome and HTTP status", 16, 76, 8, 9)

    # (f) Coverage ------------------------------------------------------------------------------------
    row("Coverage · which runtimes reach this board", 85)
    table(
        "OTLP log records per service (live)",
        'What reached the Collector as logs: 24 h for the low-volume runtimes and SDK, 1 h for Codex and '
        'Claude. A runtime missing here and in the span table sends no OTLP to this host; see the coverage '
        'table for agentsview and the vendor options.',
        [loki(f'sum by (service_name) (count_over_time({RUNTIMES} [24h]))', "Log records (24 h)", "A"),
         loki(f'sum by (service_name) (count_over_time({CLIENTS} [1h]))', "Log records (1 h)", "B")],
        layout(["service_name", "Log records (1 h)", "Log records (24 h)"], {"service_name": "service.name"}),
        0, 86, 7, 12, [override(name, decimals=0) for name in ("Log records (1 h)", "Log records (24 h)")],
        datasource=LOKI)
    table(
        "OTLP span calls per service (24 h)",
        'Spans that reached the Collector and its spanmetrics connector, per service.name, in 24 h.',
        [prom('sum by (service_name) (increase(traces_span_metrics_calls_total[24h]))', "Span calls", "A")],
        layout(["service_name", "Span calls"], {"service_name": "service.name"}, "Span calls"),
        7, 86, 4, 12, [override("Span calls", decimals=0)], datasource=PROMETHEUS)
    text("Runtime coverage · recorded 2026-10-13", COVERAGE, 11, 86, 13, 14)

    board = {
        "uid": "cc-god-view", "title": "Command center", "editable": False,
        "tags": ["native", "command-center", "lanes"], "timezone": "utc", "refresh": "1m",
        "schemaVersion": native.get("schemaVersion", 39), "version": 1,
        "time": {"from": "now-1h", "to": "now"},
        "description": ("Every lane and worker on one board: roster, progress, invoke rates, errors, gateway "
                        "routing and telemetry coverage, from Loki, Prometheus, hcom records and OmniRoute spans."),
        "links": [{"type": "link", "title": "agentsview sessions", "url": AGENTSVIEW, "targetBlank": True},
                  {"type": "link", "title": "Lanes", "url": "/d/cc-lanes", "targetBlank": False},
                  {"type": "link", "title": "Native agent ecosystem", "url": "/d/ecosystem-native",
                   "targetBlank": False},
                  {"type": "link", "title": "Gateway usage", "url": "http://127.0.0.1:21128/dashboard/analytics",
                   "targetBlank": True}],
        "templating": copy.deepcopy(lanes["templating"]),
        "panels": panels,
    }
    return board


# Observed 2026-10-13T02:2xZ: Loki service_name values (7 d), Prometheus job values (24 h) and the
# agentsview /api/v1/agents counts with one-shot and automated sessions included. Vendor options were
# read from the upstream mirrors at the listed commits; the decision note keeps the citations.
COVERAGE = """| Runtime (installed) | OTLP on this host | agentsview sessions (with children) | Vendor telemetry option |
|---|---|---|---|
| Codex 0.162.1 | yes: codex_exec, codex_cli_rs, codex-app-server, codex_sdk_ts | 3299 | `[otel]` exporter in config.toml ([otel README](https://github.com/openai/codex/blob/092d3acd/codex-rs/otel/README.md)) |
| Claude Code | yes: claude-code | 6482 | `CLAUDE_CODE_ENABLE_TELEMETRY` + OTLP env ([monitoring](https://code.claude.com/docs/en/monitoring-usage)) |
| pi 1.1.0 | yes: pi (through the pi-otel extension) | 1 | no built-in exporter; adapter API ([telemetry README](https://github.com/earendil-works/pi/blob/04566631/packages/telemetry/README.md)) |
| OpenCode 2.0.27 | yes: opencode, ns-opencode-claude/gpt/muse | 6 | OTLP endpoint and resource env ([otlp.ts](https://github.com/anomalyco/opencode/blob/a3496182/packages/util/src/observability/otlp.ts)) |
| goose 1.54.0 | yes: goose | 1 | `OTEL_EXPORTER_OTLP_ENDPOINT` ([env vars](https://github.com/aaif-goose/goose/blob/4617040c/documentation/docs/guides/environment-variables.md)) |
| Qwen Code 0.25.1 | yes: qwen-code | 1 | `telemetry.otlpEndpoint` ([telemetry](https://github.com/QwenLM/qwen-code/blob/aaf97b86/docs/developers/development/telemetry.md)) |
| oh-my-pi 18.10.2 | yes: oh-my-pi | 1 | `OTEL_EXPORTER_OTLP_ENDPOINT` ([env vars §11](https://github.com/can1357/oh-my-pi/blob/5d0aaffa/docs/environment-variables.md)) |
| Hermes 0.21.7 | **no**: agentsview only | 1 | gateway-daemon health only (`monitoring.export.otlp`), no per-run export ([gateway monitoring](https://github.com/NousResearch/hermes-agent/blob/3569e846/website/docs/developer-guide/gateway-monitoring.md)) |
| Cline 3.0.70 | **no**: agentsview only | 3 | `CLINE_OTEL_TELEMETRY_ENABLED` + `CLINE_OTEL_EXPORTER_OTLP_ENDPOINT` ([override](https://github.com/cline/cline/blob/8eba11b2/docs/enterprise-solutions/monitoring/opentelemetry_override.mdx)) |
| Kilo | **no**: agentsview only | 2 | not checked (no mirror, not installed) |
| Muse Code 1.4.6 | **no**: neither (only the gateway route `muse-code`) | 0 | not documented: no OTLP option in `muse --help`; local traces only (`muse trace inspect`) |
| OmniRoute 3.8.51 | yes: routing spans (omniroute) | — | built-in GenAI OTLP trace sink |

Gaps and the follow-ups (Claude `OTEL_RESOURCE_ATTRIBUTES=ecosystem.lane=<name>`, the hcom unit re-render,
agentsview `pg push`) are in the decision note. No exporter is hand-rolled here."""
