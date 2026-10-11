"""Present one consolidated command-center view from inputs the composer already reads.

Source contracts: cc-now/1 (in_review, landings_today, cc_agents, waiting_on_owner,
token_efficiency, token_use_24h), the local-fleet/1 projection from fleet_data.py,
and the committed readiness and evidence manifests that build_pages.py reads
under their existing source_policy.json grants. This module opens no file;
absent or malformed sections render as stated gaps. Design references: the
Claude Code 2.1.296 bundled dataviz skill (choosing-a-form.md, marks-and-anatomy.md,
anti-patterns.md) and anthropics/skills frontend-design at
33375500bcea98d610eb30ce10ac4e59b89c390d.
"""
from __future__ import annotations

from collections import Counter
from html import escape
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

# The shared projection masks home paths, session and task handles, account
# URLs and the home name. This page also never renders an email address,
# including its percent-encoded and HTML-entity forms.
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+(?:@|%40|&#0*64;|&#x0*40;)[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}", re.I)
OWNER_SESSION = "native-agent-stack-1a"
PR_FIELDS = ("head", "round", "next_gate", "blockers", "follow_ups")
STATUS_PILLS = {"wired": ("p-ok", "wired"), "partial": ("p-warn", "partial"), "missing": ("p-crit", "missing input")}
NOT_WIRED = {
    "token_report": "tools/token-report writes its manifest to a private state directory outside the page roots, and no source_policy.json role grants it.",
    "skill_usage": "No source_policy.json role grants the tools/skill-usage/skill_usage.py reports under coordination/command-center/skills/.",
    "research_queue": "No source_policy.json role grants coordination/ns2604-coop/research-queue.tsv.",
}
FINAL_STACK = "pending #1007: the final-stack manifest is not on main yet. Showing it needs a source_policy.json grant after it lands."


def text(value: Any) -> str:
    return _EMAIL.sub("[email omitted]", _sanitization.text(value))


def esc(value: Any) -> str:
    return escape(text(value), quote=True)


def _time(value: Any) -> str:
    return _current_view.observation_time(value)


def _count(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _finite(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    return value


def _figure(value: Any) -> str:
    """Numbers keep their source precision; text values are shown verbatim."""
    number = _finite(value)
    if number is not None:
        return esc(format(number, ","))
    if isinstance(value, str) and value.strip():
        return esc(value)
    return _unrecorded()


def _unrecorded(reason: str = "") -> str:
    return '<span class="cc-unrecorded">not recorded</span>' + ('<small>' + esc(reason) + '</small>' if reason else '')


def _gap(name: str) -> str:
    return '<p class="cc-gap">missing input: ' + esc(name) + '</p>'


def _not_wired(name: str, reason: str) -> str:
    return '<p class="cc-gap cc-not-wired"><strong>' + esc(name) + '</strong>: not wired. ' + esc(reason) + '</p>'


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


def _tokens(current: dict) -> tuple[str, str, str, str]:
    efficiency = current.get("token_efficiency") if isinstance(current.get("token_efficiency"), dict) else None
    use = current.get("token_use_24h") if isinstance(current.get("token_use_24h"), dict) else None
    saved, used = ['<h3>Saved</h3>'], ['<h3>Used</h3>']
    if efficiency is None:
        saved.append(_gap("cc-now.json#/token_efficiency"))
    else:
        labels = {"rtk": "RTK", "rtk_hook_audit_7d": "RTK hook audit", "context_mode_24h": "Context Mode", "headroom_24h": "Headroom"}
        rows, notes = [], []
        for key, value in efficiency.items():
            if key == "fix" and isinstance(value, str):
                notes.append(value)
                continue
            field = '<small>' + esc(key) + '</small>'
            if key == "rtk" and isinstance(value, dict):
                tokens = value.get("tokens_saved")
                share = _finite(tokens.get("share_percent")) if isinstance(tokens, dict) else None
                amount = _figure(tokens.get("value")) if isinstance(tokens, dict) else _figure(tokens)
                if share is not None and 0 <= share <= 100:
                    amount += f' <meter class="cc-meter" min="0" max="100" value="{share:g}" aria-hidden="true">{share:g}%</meter> <span class="cc-share">{esc(format(share, "g"))}% share, as reported</span>'
                rows.append('<tr><th scope="row">RTK tokens saved<small>rtk.tokens_saved</small></th><td>' + amount + '</td><td>not stated in source</td></tr>')
                for child, figure in value.items():
                    if child != "tokens_saved":
                        rows.append('<tr><th scope="row">RTK ' + esc(_humanize(child)) + '<small>rtk.' + esc(child) + '</small></th><td>' + _values(figure) + '</td><td>not stated in source</td></tr>')
                continue
            rows.append('<tr><th scope="row">' + esc(labels.get(key, _humanize(key))) + field + '</th><td>' + _values(value) + '</td><td>' + esc(_window(key)) + '</td></tr>')
        saved.append(_table("Savings the CC reports in token_efficiency; this page measures none", ["Measure", "Value", "Window"], rows) if rows else '<p>No token savings recorded.</p>')
        saved.extend('<p class="cc-note"><strong>CC note:</strong> ' + esc(note) + '</p>' for note in notes)
    saved.append(_not_wired("Token-report manifest", NOT_WIRED["token_report"]))
    if use is None:
        used.append(_gap("cc-now.json#/token_use_24h"))
    else:
        window = use.get("window") if isinstance(use.get("window"), str) else None
        used.append('<p class="cc-source">Window: ' + (esc(window) if window else 'not stated in source') + '. Reported by the CC; its stated source: ' + (esc(use["source"]) if isinstance(use.get("source"), str) else 'not stated') + '.</p>')
        lanes = [(row[0], _finite(row[1])) for row in use.get("codex_top_lanes_M") or [] if isinstance(row, (list, tuple)) and len(row) == 2 and isinstance(row[0], str) and _finite(row[1]) is not None and row[1] >= 0]
        if lanes:
            top = max(value for _, value in lanes) or 1
            bars = ['<tr><th scope="row">' + esc(lane) + '</th><td class="cc-num">' + esc(format(value, ",")) + '</td><td class="cc-bar-cell" aria-hidden="true"><span class="cc-bar" style="inline-size: ' + f'{100 * value / top:.1f}' + '%"></span></td></tr>' for lane, value in lanes]
            used.append(_table("Codex tokens by lane, millions, in the CC's order", ["Lane", "Tokens (M)", "Relative to the largest"], bars, css="cc-bars", numeric=(1,)))
        groups = []
        for key, caption, header in (("codex_tokens_M", "Codex tokens by class, millions; classes overlap and are never summed", "Tokens (M)"), ("claude_tokens_M", "Claude tokens by class, millions", "Tokens (M)"), ("claude_cost_usd_by_model", "Claude cost by model, USD", "USD")):
            values = use.get(key)
            if isinstance(values, dict):
                groups.append(_table(caption, ["Class" if key != "claude_cost_usd_by_model" else "Model", header], ['<tr><th scope="row">' + esc(name) + '</th><td class="cc-num">' + _figure(value) + '</td></tr>' for name, value in values.items()], numeric=(1,)))
        if groups:
            used.append('<div class="cc-pair">' + "".join(groups) + '</div>')
        if isinstance(use.get("note"), str):
            used.append('<p class="cc-note"><strong>CC note:</strong> ' + esc(use["note"]) + '</p>')
    status = "missing" if efficiency is None and use is None else "partial"
    detail = "Values are as the CC reports them; no source is summed with another."
    body = '<div class="cc-split"><div>' + "".join(saved) + '</div><div>' + "".join(used) + '</div></div>'
    return status, detail, 'cc-now.json token_efficiency and token_use_24h at ' + _time(current.get("updated_utc")) + '.', body


def _skills(fleet: dict) -> tuple[str, str, str, str]:
    tracking = fleet.get("tracking") if isinstance(fleet.get("tracking"), dict) else None
    parts = []
    if tracking is None or tracking.get("schema") != "fleet-tracking/1":
        parts.append(_gap("fleet tracking (fleet-tracking/1)"))
        status = "missing"
    else:
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
        parts.append(_table(caption, ["Lane", "Client", "Rate", "Source sample"], rows, css="cc-skills-table") if rows else '<p>No published lane reports a skill-invocation family.</p>')
        if shared and rows:
            parts.append('<p class="cc-note"><strong>Every row:</strong> ' + esc(shared) + '</p>')
        status = "partial"
    parts.append(_not_wired("skill_usage.py reports", NOT_WIRED["skill_usage"]))
    parts.append('<p class="cc-source">MCP server and orchestration counts by role are on the <a href="fleet.html#adoption-native-tools">Fleet page</a>.</p>')
    detail = "UNKNOWN stays distinct from zero: a rate is shown only where a qualified producer reports it."
    source = 'Fleet tracking evaluated ' + _time((tracking or {}).get("observed_utc")) + '.'
    return status, detail, source, "".join(parts)


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


def _manifests(manifests: dict) -> tuple[str, str, str, str]:
    parts, read = [], 0
    readiness = manifests.get("readiness") if isinstance(manifests.get("readiness"), dict) else {}
    evidence = manifests.get("evidence") if isinstance(manifests.get("evidence"), dict) else {}
    rows = []
    document = readiness.get("document") if readiness.get("status") == "read" and isinstance(readiness.get("document"), dict) else None
    if document is not None:
        read += 1
        summary = document.get("summary") if isinstance(document.get("summary"), dict) else {}
        counts = ", ".join(_figure(summary[key]) + ' ' + esc(_humanize(key)) for key in ("gates", "layers", "sdk_items", "recorded_claims", "unverified_claims", "unverified_sources") if _count(summary.get(key)) is not None)
        rows.append('<tr><th scope="row">Readiness manifest</th><td>' + _manifest_identity(readiness) + '</td><td>' + (counts or _unrecorded()) + '</td></tr>')
    else:
        rows.append('<tr><th scope="row">Readiness manifest</th><td colspan="2">' + _gap("readiness manifest (catalogs/north-star/readiness.json): " + str(readiness.get("reason") or "not read")) + '</td></tr>')
    files = evidence.get("document") if evidence.get("status") == "read" and isinstance(evidence.get("document"), dict) else None
    if files is not None:
        read += 1
        counts = ", ".join(_plural(len(files[key]), singular, plural) for key, singular, plural in (("files", "file", "files"), ("receipts", "receipt", "receipts"), ("convergence_records", "convergence record", "convergence records")) if isinstance(files.get(key), list))
        rows.append('<tr><th scope="row">Evidence manifest</th><td>' + _manifest_identity(evidence) + '</td><td>' + (esc(counts) or _unrecorded()) + '</td></tr>')
    else:
        rows.append('<tr><th scope="row">Evidence manifest</th><td colspan="2">' + _gap("evidence manifest (manifests/evidence.json): " + str(evidence.get("reason") or "not read")) + '</td></tr>')
    rows.append('<tr><th scope="row">Final-stack manifest</th><td colspan="2">' + esc(FINAL_STACK) + '</td></tr>')
    rows.append('<tr><th scope="row">Research queue</th><td colspan="2">not wired. ' + esc(NOT_WIRED["research_queue"]) + '</td></tr>')
    parts.append(_table("Manifest identities and counts", ["Manifest", "Identity", "Counts"], rows, css="cc-manifest"))
    if document is not None:
        gates, items = _states(document, "gates"), _states(document, "open_items")
        states = sorted(set(gates) | set(items), key=lambda state: (-(gates[state] + items[state]), state.casefold()))
        state_rows = ['<tr><th scope="row">' + esc(state) + '</th><td class="cc-num">' + str(gates[state]) + '</td><td class="cc-num">' + str(items[state]) + '</td></tr>' for state in states]
        parts.append(_table("Readiness manifest counts by recorded state", ["State", "Gates", "Open items"], state_rows, numeric=(1, 2)))
    status = "missing" if read == 0 else "partial"
    detail = "The footer's native manifest SHA-256 is the native builder's render of the state root, a different document from the committed readiness manifest above."
    return status, detail, 'Committed manifests in the selected checkout, read under their existing source_policy.json grants.', "".join(parts)


def _owner_link(item: dict) -> str:
    """current_view.owner_link with this page's email mask applied to the text."""
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


def _counts(current: dict, fleet: dict) -> str:
    def size(value: Any, known: bool = True) -> str:
        return f"{len(value):,}" if known and isinstance(value, list) else "UNKNOWN"
    cc_agents = current.get("cc_agents") if isinstance(current.get("cc_agents"), dict) else {}
    efficiency = current.get("token_efficiency") if isinstance(current.get("token_efficiency"), dict) else {}
    rtk = efficiency.get("rtk") if isinstance(efficiency.get("rtk"), dict) else {}
    saved = rtk.get("tokens_saved")
    saved = saved.get("value") if isinstance(saved, dict) else saved
    saved_text = text(format(saved, ",")) if _finite(saved) is not None else text(saved) if isinstance(saved, str) and saved.strip() else "UNKNOWN"
    items = [
        ("cc-prs", size(current.get("in_review")), "in review"),
        ("cc-prs", size(current.get("landings_today")), "landed today"),
        ("cc-owner", size(current.get("waiting_on_owner")), "waiting on you"),
        ("cc-sessions", size(fleet.get("lanes_live"), _known(fleet, "lanes_live")), "live Codex lanes"),
        ("cc-sessions", size(fleet.get("claude_sessions"), _known(fleet, "claude_sessions")), "Claude sessions"),
        ("cc-sessions", size(cc_agents.get("running")), "CC subagents running"),
        ("cc-tokens", saved_text, "tokens saved by RTK"),
    ]
    return '<ul class="cc-counts" aria-label="Counts; each links to its section">' + "".join(f'<li><a href="#{anchor}"><strong>{escape(value)}</strong> <span>{escape(label)}</span></a></li>' for anchor, value, label in items) + '</ul>'


def render(current: Any, fleet: Any, manifests: Any) -> tuple[str, dict]:
    """Return the page markup and a per-panel status record for the receipt."""
    current = current if isinstance(current, dict) else {}
    fleet = fleet if isinstance(fleet, dict) else {}
    manifests = manifests if isinstance(manifests, dict) else {}
    panels = [
        ("cc-sessions", "Sessions and lanes", _sessions(current, fleet)),
        ("cc-prs", "PR waves", _prs(current)),
        ("cc-tokens", "Tokens saved", _tokens(current)),
        ("cc-skills", "SOTA skill invoke rates", _skills(fleet)),
        ("cc-manifests", "Compounding manifests", _manifests(manifests)),
        ("cc-owner", "Waiting on you", _owner(current)),
    ]
    sections, statuses = [], {}
    for anchor, title, (status, detail, source, body) in panels:
        css, label = STATUS_PILLS[status]
        statuses[anchor] = {"title": title, "status": status, "detail": detail}
        sections.append(f'<section class="cc-panel" id="{anchor}" aria-labelledby="{anchor}-title"><div class="cc-panel-head"><h2 id="{anchor}-title">{esc(title)}</h2><span class="pill {css}">{label}</span></div>'
                        f'<p class="cc-source">{source}</p>' + (f'<p class="cc-detail">{esc(detail)}</p>' if detail else '') + body + '</section>')
    stamp = 'Current view snapshot ' + _time(current.get("updated_utc"))
    headline = '<p class="now-headline">' + esc(current["headline"]) + '</p>' if isinstance(current.get("headline"), str) else _gap("cc-now.json#/headline")
    markup = (f'<section id="cc-view" class="cc-view" aria-labelledby="cc-title"><header class="page-header"><h1 id="cc-title">Command center</h1><p class="current-stamp">{stamp}</p>{headline}</header>'
              + _counts(current, fleet) + '<div class="cc-grid">' + "".join(sections) + '</div></section>')
    # Defense in depth: fragments from sibling views pass the same email mask.
    return _EMAIL.sub("[email omitted]", markup), statuses
