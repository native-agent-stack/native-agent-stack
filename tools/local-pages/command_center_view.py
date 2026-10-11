"""Present one consolidated command-center view from inputs the composer already reads.

Source contracts: cc-now/1 (in_review, landings_today, cc_agents, waiting_on_owner,
orchestration, landing_queue, program, mirrors, rulings, token_efficiency and
token_use_24h), the local-fleet/1 and adoption-now/1 observations every refresh
already makes, and the files build_pages.py reads under exact command_center_*
roles in source_policy.json: committed manifests and landscape records, the
skill-usage reports (skill_usage.py, child-usage.mjs, or #970's daily
projection), the token window and token-tools reports, the practice slots and
the co-op research and read queues. This module opens no file; absent or
malformed inputs render as stated gaps, and each section renders in its own
guard. Text passes the shared sanitizer, which also omits email addresses.
Design references: the Claude Code 2.1.296 bundled dataviz skill
(choosing-a-form.md, marks-and-anatomy.md, anti-patterns.md) and
anthropics/skills frontend-design at 33375500bcea98d610eb30ce10ac4e59b89c390d.
"""
from __future__ import annotations

from collections import Counter
from html import escape, unescape
import importlib.util
import math
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlsplit


def _load(name: str):
    spec = importlib.util.spec_from_file_location("local_command_center_" + name, Path(__file__).with_name(name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_sanitization = _load("sanitization")
_current_view = _load("current_view")
_fleet_view = _load("fleet_view")

OWNER_SESSION = "native-agent-stack-1a"
PR_FIELDS = ("head", "round", "next_gate", "blockers", "follow_ups")
STATUS_PILLS = {"wired": ("p-ok", "wired"), "partial": ("p-warn", "partial"), "missing": ("p-crit", "missing input")}
NOT_WIRED = {
    "token_report": "tools/token-report writes its manifest to a private state directory outside the page roots, and its README keeps raw reports private; a sanitized receipt is a follow-up.",
    "north_star": "No committed record holds the owner's ten-layer plan table; the committed north-star readiness layers are above, and the CC can publish the plan as cc-now.json north_star_layers (README schema).",
}
NOT_WIRED_TITLES = {"token_report": "Token-report manifest", "north_star": "North-star ten-layer plan"}
FINAL_STACK = "pending #1008/#1007: catalogs/landscape/final-stack.json is not in the selected checkout yet; its grant is in place."
DAILY_SCHEMA = "skill-invoke-rate-daily/1"
RAW_KINDS = {"skills_host": "skill_invoke_rate_report", "skills_codex_lanes": "codex_lane_usage_report", "skills_claude_lanes": "claude_child_lane_usage"}
TOOLS_SCHEMA = "token-tools-now/1"
SEVERITY = {"wired": 0, "partial": 1, "missing": 2}
# A bad field degrades only its own section: these are the failures a section can raise on unexpected shapes.
PANEL_ERRORS = (ValueError, TypeError, KeyError, AttributeError, IndexError, OverflowError, RecursionError)
# A report older than this at the page refresh is labelled stale: three hours
# for hourly producers, 30 hours for the daily Codex lanes report, and an hour
# for the co-op's live read queue.
STALE_AFTER = {"skills_host": 3 * 3600, "skills_codex_lanes": 30 * 3600, "skills_claude_lanes": 3 * 3600, "skills_daily": 30 * 3600,
               "token_window": 3 * 3600, "token_tools": 3 * 3600, "read_queue": 3600}


def text(value: Any) -> str:
    """The shared sanitizer, which also omits email addresses in their decoded forms."""
    return _sanitization.text(value)


def esc(value: Any) -> str:
    return escape(text(value), quote=True)


def _time(value: Any) -> str:
    return _current_view.observation_time(value)


def _count(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _finite(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        return value if math.isfinite(value) else None
    except OverflowError:  # an integer beyond the float range has no finite float value
        return None


def _figure(value: Any) -> str:
    """Numbers keep their source precision; text values are shown verbatim."""
    number = _finite(value)
    if number is not None or isinstance(value, int) and not isinstance(value, bool):
        return esc(format(value, ","))
    if isinstance(value, str) and value.strip():
        return esc(value)
    return _unrecorded()


def _unrecorded(reason: str = "") -> str:
    return '<span class="cc-unrecorded">not recorded</span>' + ('<small>' + esc(reason) + '</small>' if reason else '')


def _gap(name: str) -> str:
    return '<p class="cc-gap">missing input: ' + esc(name) + '</p>'


def _not_wired(key: str) -> str:
    return '<p class="cc-gap cc-not-wired" data-cc-not-wired="' + key + '"><strong>' + esc(NOT_WIRED_TITLES[key]) + '</strong>: not wired. ' + esc(NOT_WIRED[key]) + '</p>'


def _unread(*records: tuple[str, Any, dict]) -> str:
    """Name each record a section could not read, with the composer's reason."""
    unread = [label + " (" + str(item.get("reason") or "not read") + ")" for label, document, item in records if not isinstance(document, dict)]
    return " Partial because of unread records: " + "; ".join(unread) + "." if unread else ""


def _humanize(key: Any) -> str:
    return str(key).replace("_", " ").strip()


def _plural(count: int, singular: str, plural: str) -> str:
    return f"{count:,} " + (singular if count == 1 else plural)


def _table(caption: str, headers: list[str], rows: list[str], *, css: str = "", numeric: tuple[int, ...] = ()) -> str:
    head = "".join(('<th scope="col" class="cc-num">' if index in numeric else '<th scope="col">') + esc(header) + '</th>' for index, header in enumerate(headers))
    return (f'<div class="table-wrap cc-table-wrap" tabindex="0" role="region" aria-label="{esc(caption)}">'
            f'<table class="cc-table{" " + css if css else ""}"><caption>{esc(caption)}</caption>'
            f'<thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>')


def _duration(seconds: Any) -> str | None:
    value = _finite(seconds)
    if value is None or value < 0:
        return None
    if value < 120:
        return f"{value:g} s"
    if value < 7200:
        return f"{value / 60:.0f} min"
    return f"{value / 3600:.1f} h"


def _known(fleet: dict, name: str) -> bool:
    """Mirror fleet_view: a section counts only when its source reported it."""
    rows = fleet.get(name)
    availability = fleet.get("availability") if isinstance(fleet.get("availability"), dict) else {}
    section = availability.get(name)
    status = section.get("status") if isinstance(section, dict) else None
    reported = fleet.get("fleet_source") not in (None, "", "not reported")
    return isinstance(rows, list) and (status in ("reported", "snapshot fallback") if status is not None else reported)


def _hcom(fleet: dict) -> tuple[list[dict], Any]:
    tracking = fleet.get("tracking") if isinstance(fleet.get("tracking"), dict) else {}
    hcom = tracking.get("hcom") if isinstance(tracking.get("hcom"), dict) else {}
    agents = hcom.get("agents") if hcom.get("status") == "reported" and isinstance(hcom.get("agents"), list) else []
    return [agent for agent in agents if isinstance(agent, dict)], hcom.get("read_utc")


def _in_state(agent: dict | None) -> str:
    duration = _duration(agent.get("status_age_seconds")) if agent else None
    if duration is None:
        return _unrecorded()
    return esc(duration) + '<small>hcom ' + esc(agent.get("name")) + ', ' + esc(agent.get("status")) + '</small>'


def _agent_row(value: Any) -> tuple[str, str | None, str | None] | None:
    """cc_agents.running rows are "name (task)" text or {name, task, model} objects."""
    if isinstance(value, str) and value.strip():
        match = re.fullmatch(r"\s*([^\s(]+)\s*(?:\((.*)\))?\s*", value, re.S)
        return (match.group(1), match.group(2), None) if match else (value, None, None)
    if isinstance(value, dict) and isinstance(value.get("name"), str) and value["name"].strip():
        task = next((value[key] for key in ("task", "what", "type") if isinstance(value.get(key), str)), None)
        return value["name"], task, value.get("model") if isinstance(value.get("model"), str) else None
    return None


def _sessions(current: dict, fleet: dict) -> tuple[str, str, str, str]:
    agents, hcom_read = _hcom(fleet)
    parts, missing = [], []
    claimed: set[int] = set()
    def agent_for(*names: Any) -> dict | None:
        for index, agent in enumerate(agents):
            if any(isinstance(name, str) and name and name in (agent.get("tag"), agent.get("name"), agent.get("base_name")) for name in names):
                claimed.add(index)
                return agent
        return None
    if _known(fleet, "lanes_live"):
        rows = []
        for row in fleet["lanes_live"]:
            if not isinstance(row, dict):
                continue
            models = row.get("subagent_models") if isinstance(row.get("subagent_models"), dict) else {}
            model = esc(row["lane_model"]) if isinstance(row.get("lane_model"), str) and row["lane_model"] else _unrecorded()
            if models:
                model += '<small>subagents: ' + esc(", ".join(f"{name} {count}" for name, count in models.items())) + '</small>'
            tier = "standard" if row.get("tier") == "default" else row.get("tier")
            rows.append('<tr data-cc-lane="' + esc(row.get("lane")) + '"><th scope="row">' + esc(row.get("lane")) + '</th><td>' + _fleet_view.text(row.get("status")) + '</td><td>' + _in_state(agent_for(row.get("lane"))) + '</td><td>' + model + '</td><td>' + _fleet_view.text(tier) + '</td><td>' + _fleet_view.text(row.get("cli_version")) + '</td></tr>')
        parts.append(_table("Live Codex lanes", ["Lane", "State", "In this state for", "Model", "Tier", "CLI"], rows) if rows else '<p>No live Codex lanes reported.</p>')
    else:
        missing.append("fleet lanes_live")
        parts.append(_gap("fleet lanes_live"))
    pair = []
    if _known(fleet, "claude_sessions"):
        rows = []
        for row in fleet["claude_sessions"]:
            if not isinstance(row, dict):
                continue
            name = "owner session (reports to CC)" if row.get("name") == OWNER_SESSION else row.get("name")
            rows.append('<tr><th scope="row">' + esc(name) + '</th><td>' + _fleet_view.text(row.get("status")) + '</td><td>' + _in_state(agent_for(row.get("name"))) + '</td><td>' + _unrecorded() + '</td></tr>')
        pair.append(_table("Claude sessions", ["Session", "State", "In this state for", "Model"], rows) if rows else '<p>No Claude sessions reported.</p>')
    else:
        missing.append("fleet claude_sessions")
        pair.append(_gap("fleet claude_sessions"))
    if _known(fleet, "exec_reads_in_flight"):
        rows = []
        for item in fleet["exec_reads_in_flight"]:
            name, tier = (item.get("name"), item.get("tier")) if isinstance(item, dict) else (item, None)
            rows.append('<tr><th scope="row">' + esc(name) + '</th><td>' + _fleet_view.text(tier) + '</td></tr>')
        pair.append(_table("Reads in flight", ["Read", "Tier"], rows) if rows else '<p>No reads in flight.</p>')
    else:
        pair.append(_gap("fleet exec_reads_in_flight"))
    others = ['<tr><th scope="row">' + esc(agent.get("name")) + '</th><td>' + esc(agent.get("tool") or "not reported") + '</td><td>' + esc(agent.get("status") or "not reported") + '</td><td>' + _in_state(agent) + '</td></tr>' for index, agent in enumerate(agents) if index not in claimed]
    if others:
        pair.append(_table("Other hcom agents", ["Agent", "Client", "State", "In this state for"], others))
    parts.append('<div class="cc-pair">' + "".join(pair) + '</div>')
    cc_agents = current.get("cc_agents") if isinstance(current.get("cc_agents"), dict) else {}
    running = cc_agents.get("running")
    if isinstance(running, list):
        rows = []
        for value in running:
            row = _agent_row(value)
            if row is None:
                continue
            name, task, model = row
            rows.append('<tr><th scope="row">' + esc(name) + '</th><td>' + (esc(task) if task else _unrecorded()) + '</td><td>' + (esc(model) if model else _unrecorded()) + '</td></tr>')
        parts.append(_table("Command-center subagents running", ["Subagent", "Task", "Model"], rows) if rows else '<p>No command-center subagents listed as running.</p>')
    else:
        missing.append("cc-now.json#/cc_agents/running")
        parts.append(_gap("cc-now.json#/cc_agents/running"))
    if _known(fleet, "lanes_parked"):
        parked = [row for row in fleet["lanes_parked"] if isinstance(row, dict)]
        items = "".join('<li><strong>' + esc(row.get("lane")) + '</strong> <small>' + _fleet_view.text(row.get("tier")) + ', expected CLI ' + _fleet_view.text(row.get("expected_cli_version")) + '</small></li>' for row in parked)
        parts.append(f'<details class="cc-parked"><summary>{_plural(len(parked), "parked lane", "parked lanes")}</summary><ul>{items}</ul></details>')
    else:
        parts.append(_gap("fleet lanes_parked"))
    status = "missing" if len(missing) == 3 else "partial" if missing else "wired"
    detail = "Missing: " + ", ".join(missing) + "." if missing else ""
    detail += (" " if detail else "") + "Last activity is the hcom state age; no other source records it. Models appear only where the fleet records one."
    source = ('Fleet: ' + esc(fleet.get("fleet_source") or "not reported") + ' at ' + _time(fleet.get("at")) + '. hcom roster read ' + _time(hcom_read)
              + '. Subagents: cc-now.json at ' + _time(current.get("updated_utc")) + '. <a href="fleet.html">Fleet page</a> has rates, pool and spend.')
    return status, detail, source, "".join(parts)


def _list_cell(value: Any, present: bool) -> str:
    if not present or value is None:
        return _unrecorded()
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        return _unrecorded("unsupported value")
    if not value:
        return 'none'
    return '<ul>' + "".join('<li>' + esc(item) + '</li>' for item in value) + '</ul>'


def _scalar_cell(value: Any, present: bool, *, code: bool = False) -> str:
    if not present or value is None:
        return _unrecorded()
    if isinstance(value, bool) or not isinstance(value, (str, int)) or isinstance(value, str) and not value.strip():
        return _unrecorded("unsupported value")
    if isinstance(value, int) and value < 0:
        return _unrecorded("unsupported value")
    return '<code>' + esc(value) + '</code>' if code else esc(value)


def _prs(current: dict) -> tuple[str, str, str, str]:
    rows = current.get("in_review")
    source = 'cc-now.json in_review and landings_today at ' + _time(current.get("updated_utc")) + '.'
    table_rows, recorded = [], Counter()
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        for field in PR_FIELDS:
            recorded[field] += row.get(field) is not None
        cells = [
            _scalar_cell(row.get("head"), "head" in row, code=True),
            _scalar_cell(row.get("round"), "round" in row),
            '<strong>' + esc(row["next_gate"]) + '</strong>' if isinstance(row.get("next_gate"), str) and row["next_gate"].strip() else _scalar_cell(row.get("next_gate"), "next_gate" in row),
            _list_cell(row.get("blockers"), "blockers" in row),
            _list_cell(row.get("follow_ups"), "follow_ups" in row),
        ]
        table_rows.append('<tr data-cc-pr="' + esc(row.get("pr")) + '"><th scope="row">' + esc(row.get("pr")) + '</th><td>' + esc(row.get("what")) + '</td>' + "".join(f'<td class="cc-pr-{field.replace("_", "-")}">{cell}</td>' for field, cell in zip(PR_FIELDS, cells)) + '<td>' + esc(row.get("state")) + '</td></tr>')
    if not isinstance(rows, list):
        body = _gap("cc-now.json#/in_review")
    else:
        body = _table("Pull requests in review, in the CC's order", ["PR", "Work", "Head", "Round", "Next gate", "Blockers", "Follow-ups", "Recorded state"], table_rows, css="cc-prs") if table_rows else '<p>No pull requests in review.</p>'
    landed = current.get("landings_today")
    if isinstance(landed, list):
        items = "".join('<li>' + esc(item) + '</li>' for item in landed if isinstance(item, (str, int)) and not isinstance(item, bool))
        body += f'<details class="cc-landed"><summary>{len(landed)} landed today</summary><ul>{items}</ul></details>'
    else:
        body += _gap("cc-now.json#/landings_today")
    unrecorded = [{"next_gate": "next gate", "follow_ups": "follow-ups"}.get(field, field) for field in PR_FIELDS if not recorded[field]]
    status = "missing" if not isinstance(rows, list) else "partial" if unrecorded and table_rows else "wired"
    detail = ("Not recorded on any row yet: " + ", ".join(unrecorded) + ". The CC can add them to in_review; see the README schema.") if unrecorded and table_rows else ""
    return status, detail, source, body


def _window(key: str) -> str:
    match = re.search(r"_(\d+)(h|d)$", key)
    if not match:
        return "not stated in source"
    amount, unit = match.groups()
    return amount + (" h" if unit == "h" else " days") + " (from the field name)"


def _values(value: Any) -> str:
    if isinstance(value, dict):
        pairs = [_figure(child) + ' ' + esc(_humanize(key)) for key, child in value.items() if _finite(child) is not None or isinstance(child, str)]
        return ", ".join(pairs) if pairs else _unrecorded()
    return _figure(value)


def _when(value: Any) -> str:
    """A full timestamp in New York and UTC; other recorded text (such as '15:38Z') verbatim, never completed."""
    if not isinstance(value, str) or not value.strip():
        return _unrecorded()
    try:
        return _current_view.time_label(value)
    except (ValueError, TypeError, OverflowError):
        return esc(value) + '<small>as recorded</small>'


def _input(inputs: dict, name: str) -> tuple[Any, dict]:
    """Return a read input's document (or text) and its record; None when it was not read."""
    item = inputs.get(name) if isinstance(inputs.get(name), dict) else {}
    return (item.get("document") if item.get("status") == "read" else None), item


def _input_gap(item: dict, name: str) -> str:
    return _gap(str(item.get("label") or name) + ": " + str(item.get("reason") or "not read"))


def _age(value: Any, refreshed: Any) -> float | None:
    try:
        return (_current_view.parse_time(refreshed) - _current_view.parse_time(value)).total_seconds()
    except (ValueError, TypeError, AttributeError, OverflowError):
        return None


def _freshness(value: Any, refreshed: Any, limit: int) -> tuple[str, bool]:
    """Describe a report's age at this refresh; a missing or unparseable time is never fresh."""
    age = _age(value, refreshed)
    if age is None:
        return 'age unknown: no parseable generation time', False
    label = esc(_duration(max(age, 0)))
    if age > limit:
        return f'<strong class="cc-stale">stale</strong>: {label} old at this refresh (limit {esc(_duration(limit))})', False
    return f'{label} old at this refresh', True


def _compact(value: Any) -> str:
    """Auto-compact large counts (1,284 / 12.9K / 4.2M / 8.92B); text stays verbatim."""
    number = _finite(value)
    if number is None:
        return _figure(value)
    for size, suffix in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(number) >= size:
            return esc(f"{number / size:.3g}{suffix}")
    return esc(format(int(number), ",") if float(number).is_integer() else format(round(number, 2), ","))


def _cell_count(value: Any) -> str:
    """A measured count, or 'not measured' when the source has none; zero stays zero."""
    count = _count(value)
    return esc(format(count, ",")) if count is not None else '<span class="cc-unrecorded">not measured</span>'


def _top(counts: Any, limit: int = 6) -> str:
    if not isinstance(counts, dict):
        return _unrecorded()
    pairs = sorted(((name, count) for name, count in counts.items() if _count(count) is not None), key=lambda pair: (-pair[1], str(pair[0])))
    if not pairs:
        return 'none'
    shown = ", ".join(esc(name) + ' ' + esc(format(count, ",")) for name, count in pairs[:limit])
    return shown + (f'<small>and {len(pairs) - limit} more</small>' if len(pairs) > limit else '')


def _bars(caption: str, pairs: list[tuple[str, float]], header: str, *, shown: int = 15) -> str:
    """One series, one hue: bars beside the numbers in the same table (dataviz marks spec)."""
    pairs = sorted(pairs, key=lambda pair: (-pair[1], pair[0]))
    top = max((value for _, value in pairs), default=0) or 1
    def rows(subset):
        return ['<tr><th scope="row">' + esc(name) + '</th><td class="cc-num">' + _compact(value) + '</td><td class="cc-bar-cell" aria-hidden="true"><span class="cc-bar" style="inline-size: ' + f'{100 * value / top:.1f}' + '%"></span></td></tr>' for name, value in subset]
    markup = _table(caption + (f", largest {shown} of {len(pairs)}" if len(pairs) > shown else ""), ["Lane", header, "Relative to the largest"], rows(pairs[:shown]), css="cc-bars", numeric=(1,))
    if len(pairs) > shown:
        markup += f'<details class="cc-more"><summary>All {len(pairs)} lanes</summary>' + _table(caption + ", every lane", ["Lane", header, "Relative to the largest"], rows(pairs), css="cc-bars", numeric=(1,)) + '</details>'
    return markup


def _token_values(section: Any) -> dict:
    values = section.get("values") if isinstance(section, dict) else None
    return values if isinstance(values, dict) else {}


def _tool_estimate(row: dict) -> str:
    """A tool's own estimate as the producer recorded it: RTK's summary, Headroom's report, context-mode's checks."""
    estimate = row.get("estimate")
    if row.get("rc") is None:
        return _unrecorded(str(row.get("error") or "not run"))
    if not isinstance(estimate, dict):
        return (esc(row["message"]) if isinstance(row.get("message"), str) and row["message"] else _unrecorded()) + ('<small>exit ' + esc(row.get("rc")) + '</small>' if row.get("rc") else '')
    if "total_saved" in estimate:
        share = _finite(estimate.get("avg_savings_pct"))
        return (_compact(estimate.get("total_saved")) + ' tokens saved' + (f' ({esc(format(share, ".3g"))}% average)' if share is not None else '')
                + '<small>' + _compact(estimate.get("total_commands")) + ' commands, ' + _compact(estimate.get("total_input")) + ' input and ' + _compact(estimate.get("total_output")) + ' output tokens</small>')
    if isinstance(estimate.get("checks"), dict):
        return ", ".join(_figure(count) + ' ' + esc(name) for name, count in sorted(estimate["checks"].items())) or _unrecorded()
    if isinstance(estimate.get("report"), str):
        return '<span class="cc-pre">' + esc(estimate["report"]) + '</span>'
    return _values(estimate)


def _tokens(current: dict, inputs: dict, adoption: dict, refreshed: Any) -> tuple[str, str, str, str]:
    window_doc, window_item = _input(inputs, "token_window")
    window_doc = window_doc if isinstance(window_doc, dict) else None
    tools_doc, tools_item = _input(inputs, "token_tools")
    efficiency = current.get("token_efficiency") if isinstance(current.get("token_efficiency"), dict) else None
    use = current.get("token_use_24h") if isinstance(current.get("token_use_24h"), dict) else None
    native = window_doc.get("native") if window_doc and isinstance(window_doc.get("native"), dict) else {}
    span = ('window ' + esc(window_doc.get("window_start_utc")) + ' to ' + esc(window_doc.get("eval_time_utc"))) if window_doc else ''
    parts = ['<h3>Each tool\'s own report</h3>']
    if isinstance(tools_doc, dict) and tools_doc.get("schema") == TOOLS_SCHEMA and isinstance(tools_doc.get("tools"), list):
        fresh, _ok = _freshness(tools_doc.get("generated_utc"), refreshed, STALE_AFTER["token_tools"])
        rows = []
        for row in tools_doc["tools"]:
            if not isinstance(row, dict):
                continue
            exit_cell = _unrecorded(str(row.get("error") or "")) if row.get("rc") is None else esc(row.get("rc"))
            rows.append('<tr><th scope="row">' + esc(row.get("tool")) + '<small>' + esc(row.get("version") or "version not recorded") + '</small></th><td><code>' + esc(row.get("command")) + '</code><small>' + esc(row.get("label") or "") + '</small></td><td class="cc-num">' + exit_cell
                        + '</td><td>' + _when(row.get("started_utc")) + ('<small>' + esc(format(row["seconds"], "g")) + ' s</small>' if _finite(row.get("seconds")) is not None else '') + '</td><td>' + _tool_estimate(row) + ('<small>' + esc(row["note"]) + '</small>' if isinstance(row.get("note"), str) else '') + '</td></tr>')
        parts.append('<p class="cc-source">token-tools-now.json generated ' + _when(tools_doc.get("generated_utc")) + '; ' + fresh + '. Each number is that tool\'s own estimate from its own command; tools are never summed with each other or with client counters.</p>'
                     + _table("Token tools run end to end by tools/local-pages/token_tools_now.py", ["Tool", "Command", "Exit code", "Ran", "The tool's own estimate"], rows, css="cc-tools"))
    else:
        parts.append(_input_gap(tools_item, "token_tools") if not isinstance(tools_doc, dict) else _gap(str(tools_item.get("label") or "token_tools") + ": unsupported schema " + str(tools_doc.get("schema")) + ", expected " + TOOLS_SCHEMA))
    parts.append(_not_wired("token_report"))
    rows = []
    if window_doc and isinstance(window_doc.get("tool_reports"), dict):
        for name, values in window_doc["tool_reports"].items():
            mechanism = "RTK" if "rtk" in str(name).casefold() else _humanize(str(name).split(" ")[0])
            if isinstance(values, dict) and isinstance(values.get("tokens_saved"), dict):
                saved = values["tokens_saved"]
                share = _finite(saved.get("share_percent"))
                value = _figure(saved.get("value")) + ' saved' + (f' ({esc(format(share, "g"))}% share, as reported)' if share is not None else '')
                rest = {key: child for key, child in values.items() if key != "tokens_saved"}
                value += ('<small>' + _values(rest) + '</small>') if rest else ''
            else:
                value = _values(values)
            rows.append('<tr><th scope="row">' + esc(mechanism) + '</th><td>' + esc(name) + '</td><td>' + value + '</td><td>stated in the report name</td><td>token-window-now.json tool_reports</td></tr>')
    elif efficiency is not None:
        for key, value in efficiency.items():
            if key == "fix":
                continue
            rows.append('<tr><th scope="row">' + esc({"rtk": "RTK", "rtk_hook_audit_7d": "RTK", "context_mode_24h": "Context Mode", "headroom_24h": "Headroom"}.get(key, _humanize(key))) + '</th><td>' + esc(key) + '</td><td>' + _values(value.get("tokens_saved", value) if key == "rtk" and isinstance(value, dict) else value) + '</td><td>' + esc(_window(key)) + '</td><td>cc-now.json token_efficiency (fallback)</td></tr>')
    layers = adoption.get("layers") if isinstance(adoption.get("layers"), dict) else {}
    hours = adoption.get("window_hours")
    adoption_window = (esc(hours) + ' h ending ' + esc(adoption.get("generated_utc"))) if _count(hours) is not None else 'not stated in source'
    servers = {}
    for layer in layers.values():
        if isinstance(layer, dict) and isinstance(layer.get("servers"), dict):
            servers.update({name: row for name, row in layer["servers"].items() if any(word in name.casefold() for word in ("context-mode", "headroom", "rtk", "jcodemunch"))})
    for name, row in sorted(servers.items()):
        if not isinstance(row, dict):
            continue
        mechanism = "Headroom" if "headroom" in name else "jCodeMunch" if "jcodemunch" in name else "Context Mode"
        calls = ('Claude ' + _cell_count(row.get("claude_calls")) + ' calls in ' + _cell_count(row.get("claude_sessions")) + ' sessions; Codex ' + _cell_count(row.get("codex_calls")) + ' calls in ' + _cell_count(row.get("codex_conversations")) + ' conversations')
        rows.append('<tr><th scope="row">' + esc(mechanism) + '</th><td>' + esc(name) + ' invocations</td><td>' + calls + '</td><td>' + adoption_window + '</td><td>adoption-now.json layers</td></tr>')
    if efficiency is not None and isinstance(efficiency.get("headroom_24h"), str) and not any("headroom" in name for name in servers):
        rows.append('<tr><th scope="row">Headroom</th><td>headroom_24h</td><td>' + esc(efficiency["headroom_24h"]) + '</td><td>24 h (from the field name)</td><td>cc-now.json token_efficiency</td></tr>')
    parts.append('<h3>Token-efficiency tool use, as recorded</h3>' + (_table("Recorded tool reports and invocations, each with its own window; nothing is summed", ["Mechanism", "Measure", "Value", "Window", "Source"], rows) if rows else _gap("token-window-now.json tool_reports and cc-now.json#/token_efficiency")))
    if efficiency is not None and isinstance(efficiency.get("fix"), str):
        parts.append('<p class="cc-note"><strong>CC note:</strong> ' + esc(efficiency["fix"]) + '</p>')
    parts.append('<h3>Client counters</h3>')
    if window_doc is not None:
        fresh, _ok = _freshness(window_doc.get("eval_time_utc"), refreshed, STALE_AFTER["token_window"])
        parts.append('<p class="cc-source">The clients\' own counters in token-window-now.json: ' + span + ' (' + esc(_count(window_doc.get("window_seconds")) or "unstated") + ' s); ' + fresh + '. Rule: ' + esc(window_doc.get("rule") or "not stated") + '</p>')
        cache = []
        for client, key, token in (("Claude", "claude_tokens_by_type", "cacheRead"), ("Codex", "codex_tokens_by_type", "cached_input")):
            values = _token_values(native.get(key))
            if token in values:
                cache.append('<tr><th scope="row">' + esc(client) + '</th><td class="cc-num">' + _compact(values[token]) + '</td><td>native.' + esc(key) + '.' + esc(token) + '</td></tr>')
        parts.append(_table("Prompt-cache reads: tokens served from the cache (billed at a discount, not removed)", ["Client", "Tokens", "Counter"], cache, numeric=(1,)) if cache else _gap("token-window-now.json prompt-cache counters"))
        lanes = [(str(name), float(value)) for name, value in _token_values(native.get("codex_total_tokens_by_lane")).items() if _finite(value) is not None and value >= 0]
        parts.append(_bars("Codex tokens by lane", lanes, "Tokens") if lanes else _gap("token-window-now.json native.codex_total_tokens_by_lane"))
        groups = []
        for key, caption, header in (("claude_cost_usd_by_lane", "Claude cost by lane, USD", "USD"), ("codex_tokens_by_type", "Codex tokens by class; classes overlap and are never summed", "Tokens"),
                                     ("claude_tokens_by_type", "Claude tokens by class", "Tokens"), ("claude_cost_usd_by_model", "Claude cost by model, USD", "USD")):
            values = _token_values(native.get(key))
            if values:
                ordered = sorted(values.items(), key=lambda pair: (-(_finite(pair[1]) or 0), str(pair[0])))
                groups.append(_table(caption, ["Lane" if "lane" in key else "Model" if "model" in key else "Class", header], ['<tr><th scope="row">' + esc(name) + '</th><td class="cc-num">' + (_compact(value) if header == "Tokens" else _figure(round(value, 2) if _finite(value) is not None else value)) + '</td></tr>' for name, value in ordered], numeric=(1,)))
        if groups:
            parts.append('<div class="cc-pair">' + "".join(groups) + '</div>')
    elif use is not None:
        parts.append(_input_gap(window_item, "token_window") + '<p class="cc-source">Fallback: the CC copy in cc-now.json token_use_24h, window ' + esc(use.get("window") or "not stated in source") + '.</p>')
        listed = use.get("codex_top_lanes_M") if isinstance(use.get("codex_top_lanes_M"), list) else []
        lanes = [(row[0], float(row[1])) for row in listed if isinstance(row, (list, tuple)) and len(row) == 2 and isinstance(row[0], str) and _finite(row[1]) is not None and row[1] >= 0]
        if lanes:
            parts.append(_bars("Codex tokens by lane, millions, as the CC lists them", lanes, "Tokens (M)"))
        if isinstance(use.get("note"), str):
            parts.append('<p class="cc-note"><strong>CC note:</strong> ' + esc(use["note"]) + '</p>')
    else:
        parts.append(_input_gap(window_item, "token_window"))
        parts.append(_gap("cc-now.json#/token_use_24h"))
    status = "missing" if window_doc is None and efficiency is None and use is None and not isinstance(tools_doc, dict) else "partial"
    detail = "Each tool's number is its own estimate from its own command, and the client counters are the clients' own; nothing is summed across tools, windows or evidence classes. Prompt-cache reads are a billing discount, not removed tokens."
    source = 'token-tools-now.json (each tool\'s own command), token-window-now.json (hourly client counters), adoption-now.json (Loki counts) and cc-now.json token_efficiency.'
    return status, detail, source, "".join(parts)


def _report_time(name: str, document: Any) -> Any:
    if not isinstance(document, dict):
        return None
    if name == "skills_claude_lanes":
        window = document.get("window") if isinstance(document.get("window"), dict) else {}
        return window.get("until")
    return document.get("generated_at")


def _report_window(name: str, document: Any) -> str:
    if not isinstance(document, dict):
        return 'not stated in source'
    if name == "skills_daily":
        days = _count(document.get("window_days"))
        return f"{days} days" if days is not None else 'not stated in source'
    if name == "skills_host":
        days = [day for day in document.get("windows_days") or [] if _count(day) is not None]
        return ('Codex counts over ' + " and ".join(f"{day} days" for day in days) + '; Claude uses are lifetime (/skill-doctor)') if days else 'not stated in source'
    window = document.get("window") if isinstance(document.get("window"), dict) else {}
    return esc(window.get("since") or "unbounded") + ' to ' + esc(window.get("until") or "the run")


def _skill_counts(document: Any, path: tuple[str, ...]) -> dict | None:
    value = document
    for key in path:
        value = value.get(key) if isinstance(value, dict) else None
    return value if isinstance(value, dict) else None


SKILL_PRODUCERS = {
    "skills_daily": "daily_skill_usage.py (#970), one projection of all three reports",
    "skills_host": "skill_usage.py --run-skill-doctor --window 7 (Claude /skill-doctor and Codex rollouts)",
    "skills_codex_lanes": "skill_usage.py --lanes, 7 days (Codex rollout groups, refreshed daily)",
    "skills_claude_lanes": "child-usage.mjs --lanes-sweep, 7 days (Claude main sessions and subagents)",
}
SKILL_COLUMNS = ("claude_lifetime", "claude_main", "claude_sub", "codex_use", "codex_reads", "codex_mentions")


def _skill_model(inputs: dict, refreshed: Any) -> dict:
    """Normalize either producer into per-skill counts; an unmeasured value stays None, never 0."""
    documents, sources, fresh = {}, [], {}
    for name, producer in SKILL_PRODUCERS.items():
        document, item = _input(inputs, name)
        expected = DAILY_SCHEMA if name == "skills_daily" else RAW_KINDS[name]
        found = (document or {}).get("schema" if name == "skills_daily" else "kind") if isinstance(document, dict) else None
        if not isinstance(document, dict):
            sources.append((producer, None, _input_gap(item, name)))
        elif found != expected:
            sources.append((producer, None, _gap(str(item.get("label") or name) + ": unsupported report " + str(found) + ", expected " + expected)))
        else:
            documents[name] = document
            when = _report_time(name, document)
            label, fresh[name] = _freshness(when, refreshed, STALE_AFTER[name])
            sources.append((producer, (_report_window(name, document), _when(when), label), None))
    if "skills_daily" not in documents and "skills_host" in documents and _input(inputs, "skills_daily")[1].get("status") != "read":
        # #970's daily projection is an alternative producer: its absence is not a gap while the hourly reports exist.
        sources[0] = (sources[0][0], ('not present: the #970 daily producer is not installed; the hourly reports below are used', '', ''), None)
    model = {"sources": sources, "rows": {}, "groups": [], "types": [], "lanes_seen": {}, "producer": None,
             "installed": {}, "fresh": fresh, "documents": documents, "lane_counts": {"claude_main": None, "claude_sub": None, "codex_workers": None}}
    daily = documents.get("skills_daily")
    # The daily projection (#970) is preferred when current, or when no hourly host report exists.
    if daily is not None and (fresh.get("skills_daily") or "skills_host" not in documents):
        model["producer"] = "skills_daily"
        measured = daily.get("measured") if isinstance(daily.get("measured"), dict) else {}
        claude_main, claude_sub = {}, {}
        for lane in daily.get("lanes") or []:
            if not isinstance(lane, dict) or not isinstance(lane.get("skills"), list):
                continue
            counts = {row["name"]: _count(row.get("count")) for row in lane["skills"] if isinstance(row, dict) and isinstance(row.get("name"), str)}
            if lane.get("client") == "claude" and measured.get("claude") is True:
                target = claude_main if lane.get("lane") == "main" else claude_sub
                for skill, value in counts.items():
                    if value is not None:
                        target[skill] = target.get(skill, 0) + value
                if lane.get("lane") != "main":
                    model["types"].append((str(lane.get("lane")), None, None, counts))
            elif lane.get("client") == "codex":
                model["groups"].append((str(lane.get("lane")), None, None, counts if measured.get("codex") is True else None))
            model["lanes_seen"].update({skill: True for skill, value in counts.items() if value})
        model["lane_counts"] = {"claude_main": claude_main if measured.get("claude") is True else None,
                                "claude_sub": claude_sub if measured.get("claude") is True else None,
                                "codex_workers": next((counts for label, _, _, counts in model["groups"] if label == "workers"), None) if measured.get("codex") is True else None}
        for row in daily.get("host") or []:
            if isinstance(row, dict) and isinstance(row.get("name"), str):
                claude_known = measured.get("claude") is True
                model["rows"][row["name"]] = {
                    "claude_lifetime": _count(row.get("claude_uses_lifetime")) if measured.get("host") is True else None,
                    "claude_main": claude_main.get(row["name"], 0) if claude_known else None,
                    "claude_sub": claude_sub.get(row["name"], 0) if claude_known else None,
                    "codex_use": _count(row.get("codex_use")), "codex_reads": _count(row.get("codex_skill_md_reads")),
                    "codex_mentions": _count(row.get("codex_name_mentions"))}
        return model
    host, codex_lanes, claude_lanes = (documents.get(name) if fresh.get(name) is not None else None for name in ("skills_host", "skills_codex_lanes", "skills_claude_lanes"))
    model["producer"] = "raw" if host or codex_lanes or claude_lanes else None
    claude_main = _skill_counts(claude_lanes, ("main", "skill_calls"))
    claude_sub = _skill_counts(claude_lanes, ("groups", "all", "skill_calls"))
    for skill in (host or {}).get("skills") or []:
        if not isinstance(skill, dict) or not isinstance(skill.get("name"), str):
            continue
        claude = skill.get("claude") if isinstance(skill.get("claude"), dict) else {}
        codex = skill.get("codex") if isinstance(skill.get("codex"), dict) else {}
        week = (codex.get("counts") or {}).get("7") if isinstance(codex.get("counts"), dict) else None
        week = week if isinstance(week, dict) else {}
        codex_known = isinstance(host.get("codex"), dict) and host["codex"].get("measured") is True
        model["rows"][skill["name"]] = {
            "claude_lifetime": _count(claude.get("uses")),
            "claude_main": _count(claude_main.get(skill["name"], 0)) if claude_main is not None else None,
            "claude_sub": _count(claude_sub.get(skill["name"], 0)) if claude_sub is not None else None,
            "codex_use": None,
            "codex_reads": _count(week.get("skill_md_reads")) if codex_known and "skill_md_reads" in week else None,
            "codex_mentions": _count(week.get("name_mentions")) if codex_known and "name_mentions" in week else None,
            "codex_disabled": codex.get("enabled") is False}
        # Installed means a skills-lock record or a row in Claude's /skill-doctor table. Without a
        # measured table (skill_usage.py:556 writes "not-measured"), a skill with no lock record is unknown.
        claude_measured = isinstance(host.get("claude"), dict) and host["claude"].get("measured") is True and bool(claude)
        model["installed"][skill["name"]] = True if skill.get("installed_at") or claude.get("in_table") is True else False if claude_measured else None
    groups = codex_lanes.get("groups") if isinstance(codex_lanes, dict) and isinstance(codex_lanes.get("groups"), dict) else {}
    for label, group in groups.items():
        members = [(label.replace("_", " "), group)] if isinstance(group, dict) and "skill_md_reads" in group else [
            (label.replace("_", " ") + ": " + str(sub), subgroup) for sub, subgroup in (group.items() if isinstance(group, dict) else []) if isinstance(subgroup, dict) and "skill_md_reads" in subgroup]
        for name, member in members:
            reads = member.get("skill_md_reads") if isinstance(member.get("skill_md_reads"), dict) else None
            model["groups"].append((name, _count(member.get("sessions")), _count(member.get("sessions_with_skill_md_read")), reads))
            model["lanes_seen"].update({skill: True for skill, value in (reads or {}).items() if _count(value)})
    for name, group in (_skill_counts(claude_lanes, ("groups", "by_agent_type")) or {}).items():
        if isinstance(group, dict):
            model["types"].append((str(name), _count(group.get("children")), _count(group.get("children_with_skill_call")), group.get("skill_calls") if isinstance(group.get("skill_calls"), dict) else None))
    for counts in (claude_main, claude_sub):
        model["lanes_seen"].update({skill: True for skill, value in (counts or {}).items() if _count(value)})
    model["lane_counts"] = {"claude_main": claude_main, "claude_sub": claude_sub,
                            "codex_workers": next((counts for label, _, _, counts in model["groups"] if label == "workers"), None)}
    return model


def _safe_link(url: Any, label: str) -> str:
    """Link only an https URL that the shared sanitizer leaves unchanged; otherwise plain text."""
    if not isinstance(url, str) or text(url) != url or _sanitization.is_account_url(url):
        return esc(label)
    try:
        parsed = urlsplit(url)
    except ValueError:
        return esc(label)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        return esc(label)
    return f'<a href="{esc(url)}" rel="noreferrer">{esc(label)}</a>'


def _skills(fleet: dict, inputs: dict, refreshed: Any) -> tuple[str, str, str, str, int | None]:
    model = _skill_model(inputs, refreshed)
    parts = []
    rows = ['<tr><th scope="row">' + esc(producer) + '</th>' + (f'<td colspan="3">{gap}</td>' if gap else '<td>' + cells[0] + '</td><td>' + cells[1] + '</td><td>' + cells[2] + '</td>') + '</tr>' for producer, cells, gap in model["sources"]]
    parts.append(_table("Skill-count sources: the repository's measurement tools", ["Producer", "Window", "Generated", "Age"], rows))
    if model["producer"] == "skills_daily":
        parts.append('<p class="cc-source">Counts use the daily projection; the hourly reports are its inputs.</p>')
    manifest, manifest_item = _input(inputs, "skills_manifest")
    pinned = [skill for skill in (manifest.get("skills") or [] if isinstance(manifest, dict) else []) if isinstance(skill, dict) and isinstance(skill.get("name"), str)]
    defects = 0 if model["rows"] and pinned else None
    if pinned:
        table_rows = []
        for skill in pinned:
            name = skill["name"]
            counts = model["rows"].get(name)
            ref = str(skill.get("ref") or "unpinned")
            short = ref[:12] if re.fullmatch(r"[0-9a-f]{40}", ref) else ref  # a full commit SHA shows its 12-character prefix
            upstream = _safe_link(skill.get("url"), str(skill.get("source") or "source not recorded") + "@" + short) + '<small>' + esc(skill.get("path") or "path not recorded") + '</small>'
            cells, flags = [], []
            if counts is None:
                cells = ['<span class="cc-unrecorded">not measured</span>'] * len(SKILL_COLUMNS)
            else:
                for column in SKILL_COLUMNS:
                    value = counts.get(column)
                    cells.append(_cell_count(value))
                week = [counts.get(column) for column in SKILL_COLUMNS[1:] if counts.get(column) is not None]
                if week and all(value == 0 for value in week):
                    flags.append('<span class="pill p-crit">wiring defect</span><small>no recorded call in any measured 7-day column</small>')
                    defects += 1
                elif week:
                    flags.append('in use')
                else:
                    flags.append('<span class="cc-unrecorded">calls not measured</span>')
            if counts is not None and counts.get("codex_disabled"):
                flags.append('<small>not enabled for Codex in the manifest</small>')
            if name in model["installed"] and model["installed"][name] is None:
                flags.append('<small>install state not measured: no skills-lock record, and Claude\'s /skill-doctor table was not measured</small>')
            if model["installed"].get(name) is False:
                flags.append('<span class="pill p-warn">not installed</span><small>no skills-lock record and not in Claude\'s /skill-doctor table</small>')
            table_rows.append('<tr data-cc-skill="' + esc(name) + '"><th scope="row">' + esc(name) + '<small>' + esc(skill.get("status") or "status not recorded") + '</small></th><td>' + upstream + '</td>'
                              + "".join('<td class="cc-num">' + cell + '</td>' for cell in cells) + '<td>' + (" ".join(flags) or '<span class="cc-unrecorded">not measured</span>') + '</td></tr>')
        parts.append('<h3>Per skill and client</h3>' + _table("The " + str(len(pinned)) + " skills pinned in adoption/skills/manifest.json, with counts from the repository's measurement tools",
                                                             [label.replace(" 7 d", " 7" + chr(0xA0) + "d") for label in ("Skill", "Upstream source@pin", "Claude uses, lifetime", "Claude main sessions, 7 d", "Claude subagents, 7 d", "Codex use, 7 d", "Codex SKILL.md reads, 7 d", "Codex name mentions, 7 d", "Flags")],
                                                             table_rows, css="cc-skill-matrix", numeric=(2, 3, 4, 5, 6, 7)))
    else:
        parts.append('<h3>Per skill and client</h3>' + _input_gap(manifest_item, "skills_manifest"))
    names = {skill["name"] for skill in pinned}
    unpinned = sorted(skill for skill in model["lanes_seen"] if skill not in names)
    if pinned and model["producer"]:
        def count_in(counts, skill):
            return _cell_count(counts.get(skill, 0)) if isinstance(counts, dict) else '<span class="cc-unrecorded">not measured</span>'
        main, sub, workers = (model["lane_counts"][key] for key in ("claude_main", "claude_sub", "codex_workers"))
        rows = ['<tr><th scope="row">' + esc(skill) + '</th><td class="cc-num">' + count_in(main, skill) + '</td><td class="cc-num">' + count_in(sub, skill) + '</td><td class="cc-num">' + count_in(workers, skill) + '</td><td><span class="pill p-warn">unpinned</span></td></tr>' for skill in unpinned]
        parts.append(_table("Skills with recorded calls that the manifest does not pin; an installed skill that never ran is not visible to these reports", ["Skill", "Claude main sessions, 7 d", "Claude subagents, 7 d", "Codex workers, 7 d", "Flag"], rows, numeric=(1, 2, 3)) if rows else '<p>Every skill with a recorded call is pinned in the manifest.</p>')
    lane_rows = []
    for label, sessions, with_read, reads in model["groups"]:
        total = sum(value for value in (reads or {}).values() if _count(value) is not None) if reads is not None else None
        lane_rows.append('<tr><th scope="row">' + esc(label) + '</th><td class="cc-num">' + _cell_count(sessions) + '</td><td class="cc-num">' + _cell_count(with_read) + '</td><td class="cc-num">' + _cell_count(total) + '</td><td>' + (_top(reads) if reads is not None else _cell_count(None)) + '</td></tr>')
    if model["groups"] or model["documents"].get("skills_codex_lanes") is not None:
        parts.append('<h3>Per Codex lane group</h3>' + (_table("Codex rollout groups; counts are summed per group within one window", ["Group", "Sessions", "Sessions with a SKILL.md read", "Skill reads or uses", "Skills most used"], lane_rows, numeric=(1, 2, 3)) if lane_rows else '<p>No Codex rollout group reports skill use.</p>')
                     + '<p class="cc-source">The reports group sessions by kind and role; they do not attribute them to hcom lane names.</p>')
    active = sorted(((with_call or 0, name, children, with_call, calls) for name, children, with_call, calls in model["types"] if (with_call or 0) > 0 or (calls and any(_count(value) for value in calls.values()))), key=lambda row: (-row[0], row[1]))
    if model["types"]:
        rows = ['<tr><th scope="row">' + esc(name) + '</th><td class="cc-num">' + _cell_count(children) + '</td><td class="cc-num">' + _cell_count(with_call) + '</td><td>' + _top(calls) + '</td></tr>' for _, name, children, with_call, calls in active]
        parts.append('<h3>Per Claude subagent type</h3>' + (_table("Claude subagent types with at least one skill call", ["Subagent type", "Children", "Children with a skill call", "Skills called most"], rows, numeric=(1, 2)) if rows else '<p>No Claude subagent type recorded a skill call in the window.</p>')
                     + f'<p class="cc-source">{len(model["types"]) - len(active)} other subagent types recorded no skill call in the window.</p>')
    slots, slots_item = _input(inputs, "practice_slots")
    if isinstance(slots, dict) and isinstance(slots.get("slots"), list):
        rows = ['<tr' + (' class="cc-ao-row"' if slot.get("id") == "orchestration-frameworks" else '') + '><th scope="row">' + esc(slot.get("id")) + '<small>' + esc(slot.get("layer_id") or "layer not recorded") + '</small></th><td>' + esc(slot.get("status") or "not recorded") + '</td><td>' + esc(slot.get("default") or "not recorded") + '</td></tr>'
                for slot in slots["slots"] if isinstance(slot, dict)]
        parts.append('<h3>Claude practice slots</h3><p class="cc-source">cc-native-practice slots-final.json, checked ' + esc(slots.get("checked_at") or "not recorded") + ' for Claude Code ' + esc(slots.get("client_version") or "version not recorded") + '; the orchestration-frameworks row is the AO slot.</p>'
                     + _table("One default per role slot", ["Slot", "Status", "Default"], rows, css="cc-slots"))
    else:
        parts.append('<h3>Claude practice slots</h3>' + _input_gap(slots_item, "practice_slots"))
    tracking = fleet.get("tracking") if isinstance(fleet.get("tracking"), dict) else None
    if tracking is not None and tracking.get("schema") == "fleet-tracking/1" and tracking.get("status") not in ("UNKNOWN", "UNREPORTED"):
        found = []
        for lane in tracking.get("lanes") or []:
            if not isinstance(lane, dict):
                continue
            for client in lane.get("clients") or []:
                if not isinstance(client, dict):
                    continue
                found.extend((lane.get("lane"), client.get("client"), item) for item in client.get("rates") or [] if isinstance(item, dict) and item.get("family") == "skill_invocations")
        # A reason every row shares is stated once instead of on each row.
        reasons = {item.get("reason") for _, _, item in found}
        shared = next(iter(reasons)) if len(reasons) == 1 and isinstance(next(iter(reasons)), str) else None
        windows = {_count(item.get("window_seconds")) for _, _, item in found}
        window = next(iter(windows)) if len(windows) == 1 else None
        rows = []
        for lane, client, item in found:
            reading = _fleet_view._reading(dict(item, reason=None) if shared else item)
            if _finite(item.get("value")) == 0 and item.get("status") == "reported":
                reading += '<small>0 means no recorded calls in the window.</small>'
            if window is None and _count(item.get("window_seconds")) is not None:
                reading += '<small>' + esc(f'{item["window_seconds"]} s window') + '</small>'
            rows.append('<tr data-cc-skill-lane="' + esc(lane) + '"><th scope="row">' + esc(lane) + '</th><td>' + esc(client or "not reported") + '</td><td>' + reading + '</td><td>' + _time(item.get("source_sample_utc")) + '</td></tr>')
        caption = "Skill invocations per published lane" + (f", {window} s rate window" if window is not None else "")
        rates = _table(caption, ["Lane", "Client", "Rate", "Source sample"], rows, css="cc-skills-table") if rows else '<p>No published lane reports a skill-invocation family.</p>'
        if shared and rows:
            rates += '<p class="cc-note"><strong>Every row:</strong> ' + esc(shared) + '</p>'
    else:
        reason = (tracking or {}).get("reason") if isinstance((tracking or {}).get("reason"), str) else "not reported"
        rates = _gap("fleet tracking (" + str((tracking or {}).get("status") or "absent") + "): " + reason)
    parts.append('<details class="cc-more"><summary>Prometheus skill-invocation rates (Fleet tracking, strict)</summary><p class="cc-source">Separate from the counts above: a rate is shown only where a qualified producer reports it, and UNKNOWN is never zero. Evaluated ' + _time((tracking or {}).get("observed_utc")) + '.</p>' + rates + '</details>')
    read = len(model["documents"])
    status = "missing" if read == 0 and not pinned else "wired" if model["producer"] and all(model["fresh"].get(name) for name in (("skills_daily",) if model["producer"] == "skills_daily" else ("skills_host", "skills_codex_lanes", "skills_claude_lanes"))) else "partial"
    detail = (f"{defects:,} of {len(pinned):,} pinned skills recorded no call in any measured 7-day column (zero calls = wiring defect). " if defects is not None and pinned else "") + "Counts come from the repository's measurement tools, not from Fleet's Prometheus rates."
    return status, detail, 'adoption/skills/manifest.json joined with the skill-usage reports under coordination/command-center/skills/ and the cc-native-practice slots.', "".join(parts), defects


def _states(document: dict, section: str) -> Counter:
    counts = Counter()
    for row in document.get(section) or []:
        field = (row.get("fields") or {}).get("state") if isinstance(row, dict) and isinstance(row.get("fields"), dict) else None
        if not isinstance(field, dict):
            counts["no state field"] += 1
        elif field.get("status") == "RECORDED" and isinstance(field.get("value"), str):
            counts[field["value"]] += 1
        else:
            counts["UNVERIFIED"] += 1
    return counts


def _manifest_identity(item: dict) -> str:
    return '<code>' + esc(item.get("label")) + '</code><small>SHA-256 <code>' + esc(item.get("sha256")) + '</code>, ' + esc(format(item.get("bytes") or 0, ",")) + ' bytes</small>'


def _manifests(inputs: dict) -> tuple[str, str, str, str]:
    parts, read = [], 0
    readiness_doc, readiness = _input(inputs, "readiness")
    evidence_doc, evidence = _input(inputs, "evidence")
    final_doc, final = _input(inputs, "final_stack")
    rows = []
    document = readiness_doc if isinstance(readiness_doc, dict) else None
    if document is not None:
        read += 1
        summary = document.get("summary") if isinstance(document.get("summary"), dict) else {}
        counts = ", ".join(_figure(summary[key]) + ' ' + esc(_humanize(key)) for key in ("gates", "layers", "sdk_items", "recorded_claims", "unverified_claims", "unverified_sources") if _count(summary.get(key)) is not None)
        rows.append('<tr><th scope="row">Readiness manifest</th><td>' + _manifest_identity(readiness) + '</td><td>' + (counts or _unrecorded()) + '</td></tr>')
    else:
        rows.append('<tr><th scope="row">Readiness manifest</th><td colspan="2">' + _input_gap(readiness, "readiness") + '</td></tr>')
    files = evidence_doc if isinstance(evidence_doc, dict) else None
    if files is not None:
        read += 1
        counts = ", ".join(_plural(len(files[key]), singular, plural) for key, singular, plural in (("files", "file", "files"), ("receipts", "receipt", "receipts"), ("convergence_records", "convergence record", "convergence records")) if isinstance(files.get(key), list))
        rows.append('<tr><th scope="row">Evidence manifest</th><td>' + _manifest_identity(evidence) + '</td><td>' + (esc(counts) or _unrecorded()) + '</td></tr>')
    else:
        rows.append('<tr><th scope="row">Evidence manifest</th><td colspan="2">' + _input_gap(evidence, "evidence") + '</td></tr>')
    if isinstance(final_doc, dict):
        read += 1
        summary = final_doc.get("summary") if isinstance(final_doc.get("summary"), dict) else {}
        states = summary.get("status") if isinstance(summary.get("status"), dict) else {}
        counts = ", ".join(_figure(count) + ' ' + esc(state) for state, count in states.items() if _count(count) is not None)
        rows.append('<tr><th scope="row">Final-stack manifest</th><td>' + _manifest_identity(final) + '<small>checked ' + esc(final_doc.get("checked_at") or "not recorded") + '</small></td><td>' + (_figure(summary.get("layers")) + ' layers by status: ' + counts if counts else _unrecorded()) + '</td></tr>')
    elif final.get("reason") == "not present in the selected checkout":
        rows.append('<tr><th scope="row">Final-stack manifest</th><td colspan="2">' + esc(FINAL_STACK) + '</td></tr>')
    else:
        rows.append('<tr><th scope="row">Final-stack manifest</th><td colspan="2">' + _input_gap(final, "final_stack") + '</td></tr>')
    parts.append(_table("Manifest identities and counts", ["Manifest", "Identity", "Counts"], rows, css="cc-manifest"))
    if document is not None:
        gates, items = _states(document, "gates"), _states(document, "open_items")
        states = sorted(set(gates) | set(items), key=lambda state: (-(gates[state] + items[state]), state.casefold()))
        state_rows = ['<tr><th scope="row">' + esc(state) + '</th><td class="cc-num">' + str(gates[state]) + '</td><td class="cc-num">' + str(items[state]) + '</td></tr>' for state in states]
        parts.append(_table("Readiness manifest counts by recorded state", ["State", "Gates", "Open items"], state_rows, numeric=(1, 2)))
    status = "missing" if read == 0 else "wired" if read == 3 else "partial"
    detail = "The footer's native manifest SHA-256 is the native builder's render of the state root, a different document from the committed readiness manifest above."
    if status == "partial":
        detail += _unread(("readiness.json", readiness_doc, readiness), ("evidence.json", evidence_doc, evidence), ("final-stack.json", final_doc, final))
    return status, detail, 'Committed manifests in the selected checkout, read under exact source_policy.json grants.', "".join(parts)


def _stages(winner: dict) -> str:
    """Lifecycle stages grouped by their recorded status, in stage order."""
    groups: dict[str, list[str]] = {}
    for stage in winner.get("lifecycle_stages") or []:
        if isinstance(stage, dict) and isinstance(stage.get("stage"), str):
            groups.setdefault(str(stage.get("status") or "status not recorded"), []).append(stage["stage"])
    return "".join('<small>' + esc(status.replace("_", " ")) + ': ' + esc(", ".join(names)) + '</small>' for status, names in groups.items())


def _layer_key(row: Any) -> tuple[str, str] | None:
    return (row["catalog"], row["layer_id"]) if isinstance(row, dict) and isinstance(row.get("catalog"), str) and isinstance(row.get("layer_id"), str) else None


def _dl(pairs: list[tuple[str, str]]) -> str:
    return '<dl class="cc-facts">' + "".join(f'<div><dt>{esc(label)}</dt><dd>{value}</dd></div>' for label, value in pairs) + '</dl>'


def _rows_table(caption: str, rows: Any, fields: list[tuple[str, str]], *, missing: str, times: tuple[str, ...] = (), lists: tuple[str, ...] = ()) -> str:
    """A CC projection list rendered field by field; absent fields read 'not recorded'."""
    if not isinstance(rows, list):
        return _gap(missing)
    cells = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        values = []
        for key, _ in fields:
            if key in times:
                values.append(_when(row.get(key)))
            elif key in lists:
                values.append(_list_cell(row.get(key), key in row))
            else:
                values.append(_scalar_cell(row.get(key), key in row, code=key == "head"))
        cells.append('<tr><th scope="row">' + values[0] + '</th>' + "".join(f'<td>{value}</td>' for value in values[1:]) + '</tr>')
    return _table(caption, [label for _, label in fields], cells) if cells else '<p>None recorded.</p>'


def _repository_key(value: Any) -> str | None:
    """'owner/name' of a github.com repository URL, compared case-insensitively."""
    if not isinstance(value, str):
        return None
    match = re.match(r"https://github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+?)(?:\.git)?/?$", value)
    return match.group(1).casefold() if match else None


def _tag_version(ref: str) -> str:
    """The dotted version a release tag names: v1.30.1 and rust-v0.155.1 name 1.30.1 and 0.155.1.

    A ref without a dotted version (HEAD, main, codex-cli-v2) stays as written.
    """
    match = re.fullmatch(r"(?:[A-Za-z][A-Za-z0-9_]*(?:-[A-Za-z0-9_]+)*-)?v?(\d+(?:\.\d+)+[0-9A-Za-z.+-]*)", ref)
    return match.group(1) if match else ref


def _mirror(winner: dict, pins: dict | None) -> str:
    if pins is None:
        return '<small>mirror: not recorded (cc-now.json mirrors.pins absent)</small>'
    key = _repository_key(winner.get("repository"))
    entry = pins.get(key) if key else None
    if not isinstance(entry, dict):
        return '<small><span class="cc-stale">no mirror</span> for ' + esc(winner.get("repository") or "an unrecorded repository") + '</small>'
    pin, ref, commit = str(winner.get("pin") or ""), str(entry.get("ref") or ""), str(entry.get("commit") or "")
    # Exact text comparison only: the pin's version equals the version the mirror's tag names, or a
    # commit in the pin shares the mirror commit's prefix.
    version = pin.split(" @ ")[0].strip()
    hexes = re.findall(r"\b[0-9a-f]{7,40}\b", pin)
    same = bool(version) and bool(ref) and _tag_version(version) == _tag_version(ref) or bool(commit) and any(value.startswith(commit) or commit.startswith(value) for value in hexes)
    # The matrix writes "unpinned" for a winner without a pin.
    relation = "no pin recorded to compare" if pin.strip().casefold() in ("", "unpinned") else "matches the pin" if same else "differs from the pin"
    return '<small>mirror ' + esc(ref or "ref not recorded") + ' at ' + esc(commit or "commit not recorded") + ', synced ' + esc(entry.get("synced_at_utc") or "not recorded") + '; ' + relation + '</small>'


def _platforms(winner: dict) -> str:
    platforms = winner.get("platforms") if isinstance(winner.get("platforms"), dict) else {}
    pairs = [esc(name) + ' ' + esc(str(row.get("e2e_state") or row.get("derived_status") or "state not recorded").replace("_", " ")) for name, row in platforms.items() if isinstance(row, dict)]
    return '<small>platforms: ' + (", ".join(pairs) if pairs else "not recorded") + '</small>'


def _recorded(field: Any) -> str:
    """A readiness-manifest field: its value when RECORDED, otherwise 'not recorded' with the reason."""
    if isinstance(field, dict) and field.get("status") == "RECORDED" and field.get("value") not in (None, ""):
        value = field["value"]
        return esc(", ".join(map(str, value)) if isinstance(value, list) else value)
    reason = field.get("reason") if isinstance(field, dict) and isinstance(field.get("reason"), str) else ""
    return _unrecorded(reason)


def _landscape(current: dict, inputs: dict) -> tuple[str, str, str, str]:
    matrix, matrix_item = _input(inputs, "matrix")
    grand, grand_item = _input(inputs, "grand_list")
    final, final_item = _input(inputs, "final_stack")
    readiness, readiness_item = _input(inputs, "readiness")
    parts = []
    final_layers = {key: row for row in (final.get("layers") or [] if isinstance(final, dict) else []) if (key := _layer_key(row))}
    runs = {row["id"]: row for row in (final.get("runs") or [] if isinstance(final, dict) else []) if isinstance(row, dict) and isinstance(row.get("id"), str)}
    grand_layers = {key: row for row in (grand.get("layers") or [] if isinstance(grand, dict) else []) if (key := _layer_key(row))}
    mirrors = current.get("mirrors") if isinstance(current.get("mirrors"), dict) else {}
    pins = {str(name).casefold(): entry for name, entry in mirrors["pins"].items()} if isinstance(mirrors.get("pins"), dict) else None
    no_mirror = 0
    if isinstance(matrix, dict) and isinstance(matrix.get("rows"), list):
        summary = ((matrix.get("summary") or {}).get("convergence") or {}) if isinstance(matrix.get("summary"), dict) else {}
        overall = summary.get("overall") if isinstance(summary.get("overall"), dict) else {}
        states = summary.get("layer_states") if isinstance(summary.get("layer_states"), dict) else {}
        parts.append('<p class="cc-detail">' + _figure(overall.get("converged")) + ' of ' + _figure(overall.get("layers")) + ' layers converged; ' + _figure(overall.get("in_use")) + ' components in use. Layer states: ' + (", ".join(_figure(count) + ' ' + esc(str(state).replace("_", " ")) for state, count in states.items()) or 'not recorded') + '. Matrix checked ' + esc(matrix.get("checked_at") or "not recorded") + '.</p>')
        rows = []
        for row in matrix["rows"]:
            key = _layer_key(row)
            if key is None:
                continue
            convergence = row.get("convergence") if isinstance(row.get("convergence"), dict) else {}
            components = {item.get("id"): item for item in convergence.get("components") or [] if isinstance(item, dict)}
            grand_winners = {winner.get("component_id"): winner for winner in (grand_layers.get(key) or {}).get("winners") or [] if isinstance(winner, dict)}
            winners = [winner for winner in row.get("winners") or [] if isinstance(winner, dict)]
            cells, e2e, run_pins = [], [], []
            for winner in winners:
                component = winner.get("component_id")
                upstream = grand_winners.get(component) or {}
                behind = ('<small>upstream latest ' + esc(upstream.get("upstream_latest") or "not recorded") + ('; pin behind upstream' if upstream.get("pin_behind_upstream") is True else '') + '</small>') if upstream else ''
                mirror = _mirror(dict(winner, repository=winner.get("repository") or upstream.get("repository")), pins)
                no_mirror += "no mirror" in mirror
                cells.append('<li>' + esc(component) + ' @ ' + esc(winner.get("pin") or "unpinned") + '<small>' + esc(winner.get("evidence_class") or "class not recorded") + '</small>' + _stages(winner) + _platforms(winner) + behind + mirror + '</li>')
                state = components.get(component) or {}
                e2e.append('<li>' + esc(component) + ': host E2E ' + esc(state.get("host_e2e") or "not recorded") + ', pin current ' + esc(state.get("pin_current") or "not recorded") + '</li>')
                run = runs.get(component)
                run_pins.append('<li>' + esc(component) + ': ' + (esc(run.get("pin") or "unpinned") if isinstance(run, dict) else ('not recorded' if final is not None else 'pending final-stack.json')) + '</li>')
            terminal = final_layers.get(key)
            terminal_cell = ('<strong>' + esc(terminal.get("status")) + '</strong>' if isinstance(terminal, dict) and isinstance(terminal.get("status"), str)
                             else _unrecorded("absent from final-stack.json") if final is not None else 'pending #1008/#1007')
            invoke = convergence.get("invoke")
            invoke_cell = esc(invoke) if invoke not in (None, "") else _unrecorded(convergence.get("invoke_reason") if isinstance(convergence.get("invoke_reason"), str) else "")
            verdict = esc(row.get("verdict_status") or "not recorded") + '<small>' + esc(str(convergence.get("layer_state") or "state not recorded").replace("_", " ")) + '; ' + esc(row.get("independent_review") or "review not recorded") + '; checked ' + esc(convergence.get("verdict_checked_at") or "not recorded") + '</small>'
            rows.append('<tr data-cc-layer="' + esc(key[0] + "/" + key[1]) + '"><th scope="row">' + esc(row.get("title") or key[1]) + '<small>' + esc(key[0] + "/" + key[1]) + '</small><small>open gaps: ' + _cell_count(row.get("open_executable_now_gaps")) + ' executable now of ' + _cell_count(row.get("open_gaps")) + '</small></th>'
                        + '<td>' + ('<ul>' + "".join(cells) + '</ul>' if cells else 'none recorded') + '</td><td>' + verdict + '</td><td>' + ('<ul>' + "".join(run_pins) + '</ul>' if run_pins else _unrecorded()) + '</td><td>'
                        + ('<ul>' + "".join(e2e) + '</ul>' if e2e else _unrecorded()) + '</td><td>' + invoke_cell + '</td><td>' + terminal_cell + '</td></tr>')
        parts.append(_table("Foundation and trading layers with the W6 final criteria: the component evidence matrix, the new-host grand list, the upstream mirrors and the final stack",
                            ["Layer", "Winners: pin, class, lifecycle, platforms, mirror", "Verdict", "Run pin", "Upstream E2E at the pin", "Invoke evidence", "Terminal state"], rows, css="cc-layers"))
        if pins is not None and no_mirror:
            parts.append('<p class="cc-note">' + _plural(no_mirror, "winner has", "winners have") + ' no upstream mirror in cc-now.json mirrors.pins.</p>')
        if grand is None:
            parts.append(_input_gap(grand_item, "grand_list"))
        if pins is None:
            parts.append(_gap("cc-now.json#/mirrors/pins"))
    else:
        parts.append(_input_gap(matrix_item, "matrix"))
    if final is None and final_item.get("reason") != "not present in the selected checkout":
        parts.append(_input_gap(final_item, "final_stack"))
    layers = readiness.get("layers") if isinstance(readiness, dict) and isinstance(readiness.get("layers"), list) else None
    if layers is not None:
        rows = []
        for layer in layers:
            if not isinstance(layer, dict):
                continue
            tools = [tool for tool in layer.get("selected_tools") or [] if isinstance(tool, dict)]
            def each(field):
                return '<ul>' + "".join('<li>' + esc(tool.get("id")) + ': ' + _recorded((tool.get("fields") or {}).get(field)) + '</li>' for tool in tools) + '</ul>' if tools else _unrecorded()
            names = '<ul>' + "".join('<li>' + esc(tool.get("id")) + ' @ ' + _recorded((tool.get("fields") or {}).get("pin")) + '<small>' + _recorded((tool.get("fields") or {}).get("evidence_class")) + '</small></li>' for tool in tools) + '</ul>' if tools else 'none recorded'
            title = layer.get("title")
            rows.append('<tr><th scope="row">' + (_recorded(title) if isinstance(title, dict) else esc(title or layer.get("id"))) + '<small>' + esc(layer.get("id")) + '</small></th><td>' + names + '</td><td>' + _unrecorded("the readiness manifest has no verdict field") + '</td><td>'
                        + each("recorded_stack_pin") + '</td><td>' + each("install_receipt") + '</td><td>' + each("fresh_session_invoke") + '</td><td>' + _unrecorded() + '</td></tr>')
        parts.append('<h3>North-star layers</h3><p class="cc-source">The committed north-star readiness manifest, catalogs/north-star/readiness.json; each value is its RECORDED claim, otherwise not recorded with the manifest\'s reason.</p>'
                     + _table("North-star readiness layers with the same W6 columns", ["Layer", "Selected tools: pin, class", "Verdict", "Run pin (recorded stack pin)", "Upstream E2E at the pin (install receipt)", "Invoke evidence (fresh session)", "Terminal state"], rows, css="cc-layers"))
    else:
        parts.append('<h3>North-star layers</h3>' + _input_gap(readiness_item, "readiness"))
    north = current.get("north_star_layers")
    if north is not None:
        parts.append(_rows_table("North-star ten-layer plan the CC publishes", north, [("n", "Layer"), ("name", "Name"), ("target", "Target"), ("lane", "Lane"), ("acceptance", "Acceptance"), ("state", "State")], missing="cc-now.json#/north_star_layers"))
    else:
        parts.append(_not_wired("north_star"))
    parts.append('<h3>Program</h3>' + _rows_table("Workstreams WS1 to WS6", current.get("program"), [("ws", "Workstream"), ("title", "Title"), ("owner", "Owner"), ("state", "State"), ("gate", "Gate"), ("reopen", "Reopens when")], missing="cc-now.json#/program"))
    if isinstance(current.get("mirrors"), dict):
        failed = mirrors.get("failed")
        parts.append('<h3>Upstream mirrors</h3>' + _dl([("Mirrors", _cell_count(mirrors.get("count"))), ("Manifest rows", _cell_count(mirrors.get("manifest_rows")) if "manifest_rows" in mirrors else _unrecorded()), ("Last sync", _when(mirrors.get("synced_utc"))), ("Failed syncs", _list_cell(failed, "failed" in mirrors))]))
    else:
        parts.append('<h3>Upstream mirrors</h3>' + _gap("cc-now.json#/mirrors"))
    parts.append('<h3>Rulings</h3>' + _rows_table("Rulings and adjudications the CC records", current.get("rulings"), [("file", "Record"), ("utc", "Time"), ("summary", "Summary")], missing="cc-now.json#/rulings", times=("utc",)))
    read = sum(isinstance(document, dict) for document in (matrix, grand, final, readiness))
    status = "missing" if read == 0 else "wired" if read == 4 else "partial"
    detail = "Terminal states come only from final-stack.json; until it exists they read pending #1008/#1007. No state is inferred."
    if status == "partial":
        detail += _unread(("component-evidence-matrix.json", matrix, matrix_item), ("new-host-grand-list.json", grand, grand_item), ("final-stack.json", final, final_item), ("readiness.json", readiness, readiness_item))
    return status, detail, 'Committed catalogs/landscape and catalogs/north-star records in the selected checkout, and cc-now.json program, mirrors and rulings.', "".join(parts)


def _orchestration(current: dict, inputs: dict, adoption: dict, refreshed: Any) -> tuple[str, str, str, str]:
    parts, recorded = [], 0
    resolution = current.get("orchestration")
    if isinstance(resolution, dict):
        recorded += 1
        parts.append('<h3>Orchestration slot</h3>' + _dl([(label, _scalar_cell(resolution.get(key), key in resolution)) for key, label in (("slot", "Slot"), ("default", "Default"), ("state", "State"), ("evidence", "Evidence"), ("next", "Next"))]))
    else:
        parts.append('<h3>Orchestration slot</h3>' + _gap("cc-now.json#/orchestration"))
    slots, slots_item = _input(inputs, "practice_slots")
    slot = next((row for row in slots.get("slots") or [] if isinstance(row, dict) and row.get("id") == "orchestration-frameworks"), None) if isinstance(slots, dict) else None
    if slot is not None:
        parts.append('<p class="cc-source">The same slot in cc-native-practice slots-final.json, checked ' + esc(slots.get("checked_at") or "not recorded") + ':</p>'
                     + _dl([(label, _scalar_cell(slot.get(key), key in slot)) for key, label in (("status", "Status"), ("default", "Default"), ("overturn_when", "Overturned when"), ("notes", "Notes"))]))
    else:
        parts.append(_input_gap(slots_item, "practice_slots") if slots is None else _gap("slots-final.json orchestration-frameworks slot"))
    landing = current.get("landing_queue")
    recorded += isinstance(landing, list)
    parts.append('<h3>Landing queue</h3>' + _rows_table("Pull requests queued to land, in the CC's order", landing, [("pr", "PR"), ("head", "Head"), ("state", "State"), ("since_utc", "Since")], missing="cc-now.json#/landing_queue", times=("since_utc",)))
    queue, queue_item = _input(inputs, "read_queue")
    if isinstance(queue, dict):
        recorded += 1
        fresh, _ok = _freshness(queue.get("updated_utc"), refreshed, STALE_AFTER["read_queue"])
        slots = queue.get("slots")
        parts.append('<h3>GPT read queue</h3><p class="cc-source">read-queue-now.json updated ' + _when(queue.get("updated_utc")) + '; ' + fresh + '. Slots: ' + (_cell_count(slots) if not isinstance(slots, str) else esc(slots)) + '.</p>')
        parts.append(_rows_table("Reads running", queue.get("running"), [("read", "Read"), ("pr", "PR"), ("head", "Head"), ("tier", "Tier"), ("started_utc", "Started")], missing="read-queue-now.json running", times=("started_utc",)))
        parts.append(_rows_table("Reads waiting", queue.get("waiting"), [("pr", "PR"), ("head", "Head"), ("kind", "Kind"), ("gates", "Gates")], missing="read-queue-now.json waiting", lists=("gates",)))
    else:
        parts.append('<h3>GPT read queue</h3>' + _input_gap(queue_item, "read_queue"))
    orchestration = adoption.get("orchestration") if isinstance(adoption.get("orchestration"), dict) else None
    if orchestration is not None:
        rows = []
        for client, field in (("Claude", "claude_by_role"), ("Codex", "codex_by_role")):
            for role, counts in (orchestration.get(field) or {}).items():
                if isinstance(counts, dict):
                    tools = {name: count for name, count in counts.items() if name != "instances"}
                    rows.append('<tr><th scope="row">' + esc("owner session (reports to CC)" if role == OWNER_SESSION else role) + '</th><td>' + esc(client) + '</td><td>' + _top(tools, limit=8) + '</td></tr>')
        hours = adoption.get("window_hours")
        parts.append('<h3>Orchestration tool calls by role</h3>' + _table("Native orchestration tool calls by role, " + (f"{hours} h" if _count(hours) is not None else "window not stated") + ", from adoption-now.json", ["Role", "Client", "Calls by tool"], rows))
    else:
        parts.append('<h3>Orchestration tool calls by role</h3>' + _gap("adoption-now.json orchestration"))
    status = "missing" if recorded == 0 and orchestration is None else "wired" if recorded == 3 else "partial"
    detail = "The orchestration slot's resolution is the CC's record; this page shows it and decides nothing."
    return status, detail, 'cc-now.json orchestration and landing_queue, the co-op read-queue-now.json and adoption-now.json.', "".join(parts)


def _research(inputs: dict, refreshed: Any) -> tuple[str, str, str, str]:
    raw, item = _input(inputs, "research_queue")
    state, state_item = _input(inputs, "research_state")
    parts = []
    if isinstance(raw, str):
        notes, header, rows = [], None, []
        for line in raw.splitlines():
            if not line.strip():
                continue
            if line.startswith("#"):
                notes.append(line.lstrip("#").strip())
            elif header is None:
                header = line.split("\t")
            else:
                cells = line.split("\t")
                cells = cells[:len(header) - 1] + ["\t".join(cells[len(header) - 1:])] if len(cells) > len(header) else cells + [""] * (len(header) - len(cells))
                rows.append(cells)
        parts.extend('<p class="cc-note">' + esc(note) + '</p>' for note in notes)
        if header:
            table_rows = ['<tr><th scope="row">' + esc(cells[0] or "not recorded") + '</th>' + "".join('<td>' + (esc(cell) if cell else _unrecorded()) + '</td>' for cell in cells[1:]) + '</tr>' for cells in rows]
            parts.append(_table("Research queue rows, in the co-op's order", [column.replace("_", " ") for column in header], table_rows, css="cc-queue") if table_rows else '<p>The research queue has no rows.</p>')
        else:
            parts.append(_gap("research-queue.tsv header row"))
        parts.append('<p class="cc-source">File modified ' + _time(item.get("file_utc")) + ' (file metadata; the queue carries no snapshot time).</p>')
    else:
        parts.append(_input_gap(item, "research_queue"))
    order = state.get("resume_order") if isinstance(state, dict) else None
    if isinstance(order, list) and order:
        parts.append('<h3>Resume order</h3><p class="cc-source">catalogs/landscape/research-state.json, checked ' + esc(state.get("checked_at") or "not recorded") + '.</p><ol class="cc-steps">' + "".join('<li>' + esc(step) + '</li>' for step in order) + '</ol>')
    else:
        parts.append('<h3>Resume order</h3>' + (_input_gap(state_item, "research_state") if state is None else _gap("research-state.json resume_order")))
    read = isinstance(raw, str) + isinstance(state, dict)
    return ("missing" if read == 0 else "wired" if read == 2 else "partial"), "", 'The co-op research queue and the committed research-state resume order.', "".join(parts)


def _owner_link(item: dict) -> str:
    """current_view.owner_link through this module's esc, so the shared sanitizer applies to the text."""
    original = item.get("link", "")
    link = text(original)
    try:
        parsed = urlsplit(link)
    except ValueError:
        return esc(item.get("what"))
    if isinstance(original, str) and link == original and not _sanitization.is_account_url(original) and parsed.scheme == "https" and parsed.netloc and not parsed.username and not parsed.password:
        return f'<a href="{esc(link)}">{esc(item.get("what"))}</a>'
    return esc(item.get("what"))


def _owner(current: dict) -> tuple[str, str, str, str]:
    items = current.get("waiting_on_owner")
    source = 'cc-now.json waiting_on_owner at ' + _time(current.get("updated_utc")) + ', in the CC\'s order.'
    if not isinstance(items, list):
        return "missing", "", source, _gap("cc-now.json#/waiting_on_owner")
    rows = []
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("what"), str):
            continue
        dates = []
        for key, label in (("by_utc", "By"), ("since_utc", "Since")):
            if item.get(key):
                dates.append('<span class="owner-date">' + label + ' ' + _time(item[key]) + '</span>')
        detail = '<small class="cc-owner-detail">' + esc(item["detail"]) + '</small>' if isinstance(item.get("detail"), str) and item["detail"].strip() else ''
        rows.append('<li><span class="owner-mark" aria-hidden="true">□</span><div class="owner-action">' + _owner_link(item) + "".join(dates) + detail + '</div></li>')
    body = '<ul class="owner-checklist cc-owner-list">' + "".join(rows) + '</ul>' if rows else '<p>Nothing is waiting on you.</p>'
    return "wired", "", source, body


def _counts(current: dict, fleet: dict, inputs: dict, statuses: dict) -> str:
    def size(value: Any, known: bool = True) -> str:
        return f"{len(value):,}" if known and isinstance(value, list) else "UNKNOWN"
    cc_agents = current.get("cc_agents") if isinstance(current.get("cc_agents"), dict) else {}
    tools, _ = _input(inputs, "token_tools")
    rtk = next((row for row in tools.get("tools") or [] if isinstance(row, dict) and row.get("tool") == "RTK" and row.get("rc") == 0), None) if isinstance(tools, dict) and tools.get("schema") == TOOLS_SCHEMA else None
    saved = (rtk.get("estimate") or {}).get("total_saved") if isinstance(rtk, dict) and isinstance(rtk.get("estimate"), dict) else None
    if saved is None:
        window, _ = _input(inputs, "token_window")
        report = next(iter(window["tool_reports"].values()), None) if isinstance(window, dict) and isinstance(window.get("tool_reports"), dict) and window["tool_reports"] else None
        if not isinstance(report, dict):
            efficiency = current.get("token_efficiency") if isinstance(current.get("token_efficiency"), dict) else {}
            report = efficiency.get("rtk") if isinstance(efficiency.get("rtk"), dict) else {}
        saved = report.get("tokens_saved")
        saved = saved.get("value") if isinstance(saved, dict) else saved
    saved_text = re.sub(r"<[^>]+>", "", _compact(saved)) if _finite(saved) is not None else text(saved) if isinstance(saved, str) and saved.strip() else "UNKNOWN"
    queue, _ = _input(inputs, "read_queue")
    matrix, _ = _input(inputs, "matrix")
    overall = (((matrix.get("summary") or {}).get("convergence") or {}).get("overall") or {}) if isinstance(matrix, dict) and isinstance(matrix.get("summary"), dict) else {}
    converged = (f'{overall["converged"]:,} of {overall["layers"]:,}' if _count(overall.get("converged")) is not None and _count(overall.get("layers")) is not None else "UNKNOWN")
    defects = statuses.get("cc-skills", {}).get("defects")
    items = [
        ("cc-prs", size(current.get("in_review")), "in review"),
        ("cc-prs", size(current.get("landings_today")), "landed today"),
        ("cc-owner", size(current.get("waiting_on_owner")), "waiting on you"),
        ("cc-sessions", size(fleet.get("lanes_live"), _known(fleet, "lanes_live")), "live Codex lanes"),
        ("cc-sessions", size(fleet.get("claude_sessions"), _known(fleet, "claude_sessions")), "Claude sessions"),
        ("cc-sessions", size(cc_agents.get("running")), "CC subagents running"),
        ("cc-orchestration", size(queue.get("running")) if isinstance(queue, dict) else "UNKNOWN", "GPT reads running"),
        ("cc-landscape", converged, "layers converged"),
        ("cc-skills", f"{defects:,}" if isinstance(defects, int) else "UNKNOWN", "skills with no 7-day call"),
        ("cc-tokens", saved_text, "tokens saved (RTK estimate)"),
    ]
    return '<ul class="cc-counts" aria-label="Counts; each links to its section">' + "".join(f'<li><a href="#{anchor}"><strong>{escape(value)}</strong> <span>{escape(label)}</span></a></li>' for anchor, value, label in items) + '</ul>'


_RENDERED_GAP = re.compile(r'<p class="cc-gap">missing input: (.*?)</p>', re.S)
_RENDERED_NOT_WIRED = re.compile(r'<p class="cc-gap cc-not-wired" data-cc-not-wired="[a-z_]+"><strong>(.*?)</strong>', re.S)


def _derive(status: str, detail: str, body: str) -> tuple[str, str]:
    """A section's status follows what it renders: any stated gap, not-wired input or stale report makes it partial."""
    plain = [unescape(re.sub(r"<[^>]+>", "", match)) for match in _RENDERED_GAP.findall(body)]
    not_wired = [unescape(re.sub(r"<[^>]+>", "", match)) for match in _RENDERED_NOT_WIRED.findall(body)]
    stale = body.count('class="cc-stale">stale<')
    reasons = (["missing input: " + "; ".join(plain)] if plain else []) + (["not wired: " + ", ".join(not_wired)] if not_wired else []) + ([_plural(stale, "stale report", "stale reports")] if stale else [])
    derived = "partial" if reasons else "wired"
    final = max(status, derived, key=SEVERITY.__getitem__)
    if reasons and final != "wired":
        detail = (detail + " " if detail else "") + "Partial because of " + "; ".join(reasons) + "."
    return final, detail


def render(current: Any, fleet: Any, inputs: Any, *, adoption: Any = None, refreshed: Any = None) -> tuple[str, dict]:
    """Return the page markup and a per-section status record for the receipt.

    Each section and the count strip render inside their own guard, so a bad
    field degrades only the part that reads it.
    """
    current = current if isinstance(current, dict) else {}
    fleet = fleet if isinstance(fleet, dict) else {}
    inputs = inputs if isinstance(inputs, dict) else {}
    adoption = adoption if isinstance(adoption, dict) else {}
    defects = None
    def skills():
        nonlocal defects
        *result, defects = _skills(fleet, inputs, refreshed)
        return tuple(result)
    panels = [
        ("cc-sessions", "Sessions and lanes", lambda: _sessions(current, fleet)),
        ("cc-orchestration", "Orchestration", lambda: _orchestration(current, inputs, adoption, refreshed)),
        ("cc-prs", "PR waves", lambda: _prs(current)),
        ("cc-landscape", "Resolution landscape", lambda: _landscape(current, inputs)),
        ("cc-skills", "SOTA skill invoke rates", skills),
        ("cc-tokens", "Tokens saved", lambda: _tokens(current, inputs, adoption, refreshed)),
        ("cc-research", "Research queue", lambda: _research(inputs, refreshed)),
        ("cc-manifests", "Compounding manifests", lambda: _manifests(inputs)),
        ("cc-owner", "Waiting on you", lambda: _owner(current)),
    ]
    sections, statuses = [], {}
    for anchor, title, build in panels:
        try:
            status, detail, source, body = build()
            status, detail = _derive(status, detail, body)
        except PANEL_ERRORS as error:
            status, source = "missing", "This section could not render from its inputs."
            detail = title + " could not render (" + type(error).__name__ + "); the other sections are unaffected."
            body = _gap(title + " (" + type(error).__name__ + ")")
        css, label = STATUS_PILLS[status]
        statuses[anchor] = {"title": title, "status": status, "detail": detail, "not_wired": re.findall(r'data-cc-not-wired="([a-z_]+)"', body)}
        sections.append(f'<section class="cc-panel" id="{anchor}" aria-labelledby="{anchor}-title"><div class="cc-panel-head"><h2 id="{anchor}-title">{esc(title)}</h2><span class="pill {css}">{label}</span></div>'
                        f'<p class="cc-source">{source}</p>' + (f'<p class="cc-detail">{esc(detail)}</p>' if detail else '') + body + '</section>')
    statuses["cc-skills"]["defects"] = defects
    try:
        counts = _counts(current, fleet, inputs, statuses)
    except PANEL_ERRORS as error:
        counts = _gap("count strip (" + type(error).__name__ + ")")
    try:
        stamp = 'Current view snapshot ' + _time(current.get("updated_utc"))
        headline = '<p class="now-headline">' + esc(current["headline"]) + '</p>' if isinstance(current.get("headline"), str) else _gap("cc-now.json#/headline")
    except PANEL_ERRORS as error:
        stamp, headline = 'Current view snapshot not reported', _gap("cc-now.json#/headline (" + type(error).__name__ + ")")
    markup = (f'<section id="cc-view" class="cc-view" aria-labelledby="cc-title"><header class="page-header"><h1 id="cc-title">Command center</h1><p class="current-stamp">{stamp}</p>{headline}</header>'
              + counts + '<div class="cc-grid">' + "".join(sections) + '</div></section>')
    return markup, statuses
