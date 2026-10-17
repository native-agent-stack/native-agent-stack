#!/usr/bin/env python3
"""Render the harness atlas body from atlas_data.model().

Design (tools/local-pages/design-plan.md "Atlas page"; frontend-design SKILL.md at the manifest pin
33375500bcea98d610eb30ce10ac4e59b89c390d, SHA-256 d91970639e9f…10c1d3, cited below as FD:<line>):
- Nine sections in a fixed order that is not a sequence, so no section carries a number (FD:30).
- The one bold element is the seven-layer by family matrix (FD:59); everything around it is quiet ruled text and
  tables, never a card kit (FD:42). The FINAL count is a sentence, not a hero figure (FD:17).
- No figure and no chart: no diagram or dataviz skill is pinned in adoption/skills/manifest.json. Every table
  carries its exact values for the next session.
- A state is a glyph and a label, never color alone (design-plan.md:80-84); pending blocks name what is missing
  and what makes it present (FD:61-71). Copy is sentence case, plain verbs, active voice (FD:61-71).
- Private state records appear by name only; their digests stay in the nonserved receipt.
All text passes overview_view.esc, which applies sanitization.text (sanitization.py:107-122).
"""
from __future__ import annotations

from datetime import date, timedelta as _timedelta
import importlib.util
from pathlib import Path
import re
from typing import Any

_date = date.fromisoformat

HERE = Path(__file__).resolve().parent
LEDE = "What each model family runs at each harness layer, what is settled, and what measurement shows the lanes used, each fact with its record."
SECTIONS = (("atlas-terms", "What the terms mean"), ("atlas-layers", "Seven layers by family"), ("atlas-stacks", "Three stacks"),
            ("atlas-measured", "Measured use"), ("atlas-routing", "Model routing"), ("atlas-monitoring", "How to watch it"),
            ("atlas-rules", "Standing rules"), ("atlas-changes", "What changed"), ("atlas-evidence", "Sources and skills"))
LANE_LABELS = {"claude:main": "Claude main sessions", "claude:agent_tool": "Claude Agent-tool subagents", "claude:workflow": "Claude Workflow agents",
               "gpt:codex": "Codex sessions", "muse:muse": "Muse fenced runs"}
MODEL_UNITS = {"claude": ("message", "messages"), "gpt": ("turn", "turns"), "muse": ("run", "runs")}
REASON_TEXT = {"collector_failed": "the collector did not run", "not_configured": "no Muse receipt root is configured",
               "no_usage_keys": "Muse receipts carry no token counts", "no_rows_in_window": "no rows in the window",
               "unreported": "the projection gives no known reason"}
FAMILY_LABELS = {"claude": "Claude", "gpt": "GPT", "muse": "Muse"}
DAILY_VISIBLE = 14
CHANGES_VISIBLE = 10
_LOADED: dict[str, Any] = {}


def _module(name: str) -> Any:
    if name not in _LOADED:
        spec = importlib.util.spec_from_file_location("local_atlas_view_" + name, HERE / (name + ".py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _LOADED[name] = module
    return _LOADED[name]


def ov() -> Any:
    """overview_view: esc, glyph, _section, pending, _table, anchor, STATE_TEXT, _pin and _record (overview_view.py:21-81, :325-330)."""
    return _module("overview_view")


def esc(value: Any) -> str:
    return ov().esc(value)


def _none(text: str) -> str:
    return f'<span class="ov-none">{esc(text)}</span>'


def _cite_list(items: list) -> str:
    """Citations as repository path:line, never a link (repository links are text on this page)."""
    if not items:
        return ""
    refs = [f'<code>{esc(item["path"])}:{int(item["line"])}</code>' for item in items]
    joined = refs[0] if len(refs) == 1 else ", ".join(refs[:-1]) + " and " + refs[-1]
    return f'<p class="atlas-cite">From {joined}.</p>'


def _state(state: str | None) -> str:
    text = ov().STATE_TEXT.get(state or "", "No state")
    return f'<span class="lp-state-cell">{ov().glyph(state)}{esc(text)}</span>'


def _winners(row: dict) -> str:
    if not row.get("winners"):
        return _none("No winner")
    return ", ".join(f'{esc(winner["component"])} {ov()._pin(winner["run_pin"])}' if winner["run_pin"]
                     else f'{esc(winner["component"])} <small>no run pin ({esc(winner["run_reason"] or "unresolved")})</small>' for winner in row["winners"])


def _layer_link(row: dict) -> str:
    page = row.get("page") or ("architecture-foundation.html" if row["layer"].startswith("foundation/") else "architecture-north-star.html")
    target = f'{page}#{ov().anchor(row["layer"])}' if row.get("in_catalog") else page
    return f'<a href="{esc(target)}" title="{esc(row["layer"])}">{esc(row.get("title") or row["layer"])}</a>'


def _number(value: Any) -> str:
    return f"{value:,}" if isinstance(value, int) and not isinstance(value, bool) else _none("Not measured")


def _share(value: float | None, *, missing: str = "No data") -> str:
    return f"{value * 100:.1f}%" if isinstance(value, float) else _none(missing)


def _per100(part: int | None, whole: int | None) -> str:
    if part is None:
        return _none("Not measured")
    if part == 0:
        return "0"
    if not whole:
        return f'{part:,}<small>{esc("No data per 100")}</small>'
    return f'{part:,}<small>{100 * part / whole:.1f} per 100</small>'


def _plural(count: Any, word: str) -> str:
    return f'{_number(count)} {word}{"" if count == 1 else "s"}'


# A cell that spans the rest of its row. _table writes each cell as <td>{cell}</td>; escaped text can never contain
# "<!--", so only this marker turns into a colspan.
_SPAN = "<!--atlas-span-->"


def _spanning(table: str, columns: int) -> str:
    return table.replace("<td>" + _SPAN, f'<td colspan="{columns}">')


# ---------------------------------------------------------------- strip and terms
def strip(data: dict) -> str:
    """One quiet strip: the FINAL count as a sentence (overview_view.py:92-93), the states as figures, the measured days
    and what changed since the previous ledger row."""
    glance = data["architecture"]
    if glance["status"] != "present":
        sentence, row = "The layer records are pending, so no layer state is shown.", ""
    else:
        total, finalized = glance["total"], glance["finalized"]
        sentence = (f"No layer is final yet: none of the {total} catalog layers meets the resolution protocol." if not finalized
                    else f"{finalized} of {total} catalog layers are final under the resolution protocol.")
        row = "".join(f'<div class="lp-stat"><dt>{ov().glyph(state)}{esc(ov().STATE_TEXT[state])}</dt><dd>{glance["states"][state]}</dd></div>'
                      for state in ("non-terminal", "FINAL", "SCHEDULED", "RETIRED"))
    measured, ledger = data["measured"], data.get("ledger") or {}
    history = (measured.get("latest") or {}).get("history") or {}
    days = history.get("rows")
    row += f'<div class="lp-stat atlas-stat-rule"><dt>Measured days</dt><dd>{days if isinstance(days, int) else "Pending"}</dd></div>'
    row += f'<div class="lp-stat"><dt>Last measured day</dt><dd>{esc(history.get("last_date")) if history.get("last_date") else "Pending"}</dd></div>'
    last = (ledger.get("history") or [None])[-1]
    if ledger.get("status") == "unreported":
        changed = "Unavailable"
    elif ledger.get("status") == "appended" and last is not None:
        changed = str(len(last["changes"])) if last["seq"] > 1 else "First row"
    else:
        changed = "None"
    row += f'<div class="lp-stat"><dt>Changes since the previous row</dt><dd>{esc(changed)}</dd></div>'
    commit = data.get("commit")
    provenance = (f'Committed records at <code title="{esc(commit)}">{esc(commit[:12])}</code>; state records as published.' if commit
                  else "The commit of the committed records is unrecorded.")
    planned = data.get("planned") or 0
    if planned:
        provenance += f' final-stack.json also lists {planned} planned layer{"s" if planned != 1 else ""} outside the catalog files.'
    return (f'<section class="lp-strip" aria-label="Where the harness stands"><p class="lp-verdict">{esc(sentence)}</p>'
            f'<dl class="lp-stats">{row}</dl><p class="lp-provenance">{provenance}</p></section>')


def _slot_line(slot: dict) -> str:
    if slot.get("missing"):
        return f'<li><code>{esc(slot["slot"])}</code> {_none("not in slots.json")}</li>'
    default = slot["default"]
    text = esc(default["text"]) if default.get("text") else _none("Withheld: it names a path, URL or token") if default.get("withheld") else ""
    return f'<li><code>{esc(slot["slot"])}</code> <span class="atlas-status">{esc(slot["status"])}</span>{": " + text if text else ""}</li>'


def terms(data: dict) -> str:
    items = []
    for entry in data["definitions"]:
        if entry.get("stack"):
            parts = []
            for part in entry["parts"]:
                if part["missing"]:
                    parts.append(f'<li><code>{esc(part["layer"])}</code> {_none("is not in final-stack.json")}</li>')
                elif part["requirement"]:
                    parts.append(f'<li><strong>{esc(part["title"])}.</strong> {esc(part["requirement"])}</li>')
                else:
                    parts.append(f'<li><strong>{esc(part["title"])}.</strong> ' + _none("Withheld: it names a path, URL or token" if part["withheld"] else "No requirement recorded") + "</li>")
            slots = "".join(_slot_line(slot) for slot in entry["slots"])
            body = (f'<ul class="ov-rows">{"".join(parts)}</ul>' + (f'<h4 class="atlas-sub">Claude practice slots</h4><ul class="ov-rows">{slots}</ul>' if slots else "")
                    + '<p class="atlas-cite">From <code>catalogs/landscape/foundation.json</code> requirements'
                    + (' and <code>.claude/skills/claude-native-practice/reference/slots.json</code>.' if slots else ".") + "</p>")
        else:
            body = f'<p>{esc(entry["text"])}</p>' + _cite_list(entry["cites"])
        items.append(f'<div><dt>{esc(entry["term"])}</dt><dd>{body}</dd></div>')
    return f'<dl class="lp-defs atlas-terms">{"".join(items)}</dl>'


# ---------------------------------------------------------------- the matrix
def _cell(cell: dict) -> str:
    if cell["kind"] == "gap":
        return f'<p class="atlas-gap">{_none("No recorded mechanism")}</p>'
    if cell["kind"] == "text":
        return f'<p>{esc(cell["text"])}</p>' + _cite_list(cell["cites"])
    if cell.get("pending"):
        return ov().pending(cell["pending"])
    slots = cell["slots"]
    names = "".join(f'<li><code>{esc(slot["slot"])}</code> ' + (_none("not in slots.json") if slot.get("missing") else f'<span class="atlas-status">{esc(slot["status"])}</span>') + "</li>"
                    for slot in slots)
    defaults = "".join(_slot_line(slot) for slot in slots if not slot.get("missing"))
    more = f'<details class="lp-more"><summary>What each slot sets</summary><ul class="ov-rows">{defaults}</ul></details>' if defaults else ""
    return f'<ul class="atlas-slots">{names}</ul>{more}<p class="atlas-cite">From <code>.claude/skills/claude-native-practice/reference/slots.json</code>.</p>'


def _foot(catalog: list) -> str:
    if not catalog:
        return '<p class="atlas-foot-line">No catalog layer: receipts are kept per tool and per run, as each cell names.</p>'
    lines = []
    for row in catalog:
        if row.get("missing"):
            lines.append(f'<p class="atlas-foot-line"><code>{esc(row["layer"])}</code> {_none("is not in final-stack.json")}</p>')
            continue
        survivors = row.get("survivors") or 0
        lines.append(f'<p class="atlas-foot-line">Catalog layer {_layer_link(row)}: {_state(row.get("state"))} ({esc(row.get("status") or "no status")}). '
                     f'Winners at run pin: {_winners(row)}. {survivors} surviving candidate{"s" if survivors != 1 else ""}.</p>')
    return "".join(lines)


def matrix(data: dict) -> str:
    families = {row["id"]: row for row in data["joins"]["families"]}

    # The fence pins one Muse model (tools/muse_file_fence.py:24, read through the map's model_cite); the other families'
    # models vary by role and are in the routing section.
    muse_model = next((row["model"] for row in data["routing"]["rows"] if row["family"] == "muse" and row.get("model")), None)

    def route(family: dict) -> str:
        verb = family.get("route_verb")
        text = f'{esc(family["client"])}, {esc(verb)} <code>{esc(family["route"])}</code>' if verb else f'{esc(family["client"])}, {esc(family["route"])}'
        return text + (f', running <code>{esc(muse_model)}</code>' if family["id"] == "muse" and muse_model else "")

    head = '<th scope="col">Layer</th>' + "".join(
        f'<th scope="col">{esc(families[family]["label"])}<small>{route(families[family])}</small></th>' for family in ("claude", "gpt", "muse"))
    groups = []
    for row in data["harness"]:
        cells = "".join(f'<td>{_cell(row["cells"][family])}</td>' for family in ("claude", "gpt", "muse"))
        groups.append(f'<tbody id="atlas-layer-{esc(row["id"])}"><tr><th scope="row" rowspan="2">{esc(row["title"])}</th>{cells}</tr>'
                      f'<tr class="atlas-foot"><td colspan="3">{_foot(row["catalog"])}</td></tr></tbody>')
    caption = "Seven harness layers by model family"
    route_cites = "".join(_cite_list(families[family]["cites"]) for family in ("claude", "gpt", "muse"))
    return (f'<div class="table-wrap ov-table atlas-matrix" tabindex="0" role="region" aria-label="{esc(caption)}"><table>'
            f'<caption class="ov-sr">{esc(caption)}</caption><thead><tr>{head}</tr></thead>{"".join(groups)}</table></div>'
            f'<div class="atlas-routes">{route_cites}</div>')


# ---------------------------------------------------------------- stacks
def stacks_view(data: dict) -> str:
    out = []
    measured = data["measured"]
    for stack in data["stacks"]:
        rows = []
        for layer in stack["layers"]:
            if layer.get("missing"):
                rows.append([f'<code>{esc(layer["layer"])}</code>', _none("Not in final-stack.json"), "", "", ""])
                continue
            requirement = layer["requirement"]
            text = esc(requirement["text"]) if requirement["text"] else _none("Withheld: it names a path, URL or token" if requirement["withheld"] else "No requirement recorded")
            rows.append([_layer_link(layer), text, _state(layer.get("state")) + f'<small>{esc(layer.get("status") or "no status")}</small>', _winners(layer), str(layer.get("survivors") or 0)])
        table = ov()._table(f'{stack["title"]} layers', ["Layer", "Requirement", "State", "Winners at run pin", "Survivors"], rows, "atlas-stack", hide_caption=True)
        slots = "".join(_slot_line(slot) for slot in stack["slots"])
        slot_html = (f'<h4 class="atlas-sub">Claude practice slots</h4><ul class="ov-rows">{slots}</ul>' if slots and stack["slots_status"] == "present"
                     else "" if not stack["slots"] else f'<p class="ov-trigger">The practice slots are pending.</p>')
        if stack["servers"] is None:
            servers = (f'<p class="ov-trigger">The MCP servers this stack uses appear once the daily token projection is published and readable; '
                       f'ready when {esc(measured.get("source", {}).get("trigger") or "the projection is published")}.</p>')
        elif stack["servers"]:
            servers = ('<h4 class="atlas-sub">MCP servers the lanes call in this stack</h4><ul class="ov-rows">'
                       + "".join(f'<li><code>{esc(row["name"])}</code>: {esc(row["role"])} in <code>{esc(row["layer"])}</code></li>' for row in stack["servers"]) + "</ul>")
        else:
            servers = '<p class="lp-empty">No listed MCP server joins a layer of this stack.</p>'
        out.append(f'<h3 id="atlas-stack-{esc(stack["id"])}">{esc(stack["title"])}</h3>{table}{slot_html}{servers}')
    return "".join(out) + '<p class="atlas-cite">Layers, winners and survivors from <code>catalogs/landscape/final-stack.json</code>; server roles from its <code>index.by_repository</code>.</p>'


# ---------------------------------------------------------------- measured
def _lane_cells(lane_key: str, lane: dict | None, *, days: bool = False) -> list[str]:
    label = f'<strong>{esc(LANE_LABELS[lane_key])}</strong>'
    if lane is None:
        return [label, _SPAN + _none("Not measured: this lane is not in the projection")]
    reason = lane.get("unmeasured")
    if reason in ("collector_failed", "not_configured", "unreported") and lane.get("actors") is None:
        return [label, _SPAN + _none(f"Not measured: {REASON_TEXT[reason]}")]
    note = f'<small>{esc(REASON_TEXT[reason])}</small>' if reason else ""
    if days and isinstance(lane.get("days_measured"), int):
        note = f'<small>{_plural(lane["days_measured"], "measured day")}</small>' + note
    metrics = lane.get("metrics") or {}
    mcp = metrics.get("mcp") or {}
    tools = lane.get("tool_calls")
    actors = lane.get("actors")
    complete = lane.get("actors_complete")
    agents = (f'{complete:,} of {actors:,}' if isinstance(actors, int) and isinstance(complete, int) else _number(actors))
    rtk = lane.get("rtk") or {}
    shell, rewrites, typed = rtk.get("shell_calls"), rtk.get("rewrites"), rtk.get("typed")
    # Claude's RTK hook rewrites shell calls; Codex runs no rewrite hook, so its count is calls typed with the rtk prefix.
    if isinstance(shell, int) and isinstance(rewrites, int):
        rtk_cell = f'{rewrites:,} of {shell:,}<small>rewritten by the hook' + (f'; {typed:,} typed' if isinstance(typed, int) else "") + "</small>"
    elif isinstance(shell, int) and isinstance(typed, int):
        rtk_cell = f'{typed:,} of {shell:,}<small>typed with the rtk prefix</small>'
    else:
        rtk_cell = _none("Not measured")
    spawn = lane.get("spawn") or {}
    if lane_key == "claude:main":
        spawned = _none("Not a spawn lane")
    elif lane_key == "gpt:codex":
        spawned = _number(spawn.get("codex_subagent_sessions")) + "<small>Codex subagent sessions</small>"
    elif lane_key == "muse:muse":
        runs = lane.get("runs") or {}
        spawned = (f'{runs["total"]:,}<small>{runs["completed"]:,} completed, {runs["failed"]:,} failed</small>' if isinstance(runs.get("total"), int) else _none("Not measured"))
    else:
        spawned = _number(spawn.get("children")) + "<small>agents spawned</small>"
    usage, codex = lane.get("usage"), lane.get("codex_usage")
    if codex is not None:
        five = one = _none("No TTL split")
        unknown = _number(codex.get("cache_write"))
    elif usage is not None:
        five, one, unknown = (_number(usage.get(key)) for key in ("cache_creation_5m", "cache_creation_1h", "cache_creation_ttl_unknown"))
    else:
        five = one = unknown = _none("Not measured")
    share_missing = "Not measured" if usage is None and codex is None else "No data"
    return [label + note, agents, _number(tools)] + [_per100(mcp.get(key), tools) for key in ("token_efficiency", "memory_rag", "code_intel", "other")] + [
        rtk_cell, spawned, _share(metrics.get("cache_read_share"), missing=share_missing), five, one, unknown]


MEASURED_HEADER = ["Lane", "Agents with complete usage, of all", "Tool calls", "MCP: token efficiency", "MCP: memory and retrieval",
                   "MCP: code intelligence", "MCP: other", "RTK, of shell calls", "Spawned", "Prompt-cache read share",
                   "Cache writes, 5 minutes", "Cache writes, 1 hour", "Cache writes, TTL unknown"]


def measured_view(data: dict) -> str:
    result = data["measured"]
    ttl = result.get("ttl_note")
    ttl_line = ""
    if ttl:
        route = esc(ttl["route"]["text"]) if ttl["route"].get("text") else _none("route withheld")
        ttl_line = (f'<p class="atlas-note">The <code>prompt-caching</code> practice slot is <span class="atlas-status">{esc(ttl["status"])}</span>; '
                    f'its route reads: {route}.</p>')
    if result["status"] == "unreadable":
        source = {**result["source"], "trigger": "the next run of token-rate.timer publishes a projection that parses"}
        return ('<div class="ov-statement"><p class="lp-verdict">Not measured: the daily token projection does not parse, so it is kept for inspection.</p></div>'
                + ov().pending(source) + ttl_line)
    if result["status"] != "present":
        return (f'<div class="ov-statement"><p class="lp-verdict">Not measured yet: the daily token projection has not run.</p></div>' + ov().pending(result["source"])
                + '<p class="ov-trigger">The CC installs <code>token-rate.timer</code> after this change lands; until then nothing here is a zero.</p>' + ttl_line)
    latest = result["latest"]
    rollup = latest["rollup"]
    out = [f'<p class="ov-record">From <code>token-rate-latest.json</code> (private record, cited by name), generated {esc(latest["generated_at"] or "at an unrecorded time")}.</p>']
    window = ""
    if rollup.get("since") and rollup.get("until"):
        # The rollup window is [since, until): its last day is the one before until.
        last = (_date(rollup["until"]) - _timedelta(days=1)).isoformat()
        window = f'{esc(rollup["since"])} through {esc(last)}: '
    present, complete = rollup.get("days_present"), rollup.get("days_complete")
    out.append(f'<h3>The {esc(rollup.get("days") or 7)} closed days</h3><p class="atlas-note">{window}{_plural(present, "day")} present, {_number(complete)} complete. '
               'Shares are computed here from the summed numerators; none is averaged.</p>')
    rows = [_lane_cells(lane, rollup["lanes"].get(lane), days=True) for lane in ("claude:main", "claude:agent_tool", "claude:workflow", "gpt:codex", "muse:muse")]
    out.append(_spanning(ov()._table("Measured use per lane over the closed days", MEASURED_HEADER, rows, "atlas-measured", hide_caption=True), 12))
    out.append(ttl_line)
    out.append('<p class="atlas-note">MCP columns count calls with their rate per 100 tool calls; a server outside the three stacks, one that joins no catalog entry and every unlisted server count as other. '
               'Codex reports cache writes without a TTL split, so they appear under TTL unknown.</p>')
    partial = latest.get("partial_today")
    if partial:
        out.append(f'<h3>Today so far</h3><p class="atlas-note">A partial day, {esc(partial.get("since"))} to {esc(partial.get("until"))}; it never enters the history.</p>')
        out.append(_spanning(ov()._table("Measured use per lane today so far", MEASURED_HEADER,
                                         [_lane_cells(lane, partial["lanes"].get(lane)) for lane in ("claude:main", "claude:agent_tool", "claude:workflow", "gpt:codex", "muse:muse")],
                                         "atlas-measured", hide_caption=True), 12))
    else:
        out.append('<h3>Today so far</h3><p class="lp-empty">Not measured: the latest run recorded no partial day.</p>')
    out.append(daily(result))
    out.append(coverage(latest))
    return "".join(out)


def daily(result: dict) -> str:
    history = result.get("history")
    if history is None:
        return '<h3>Daily rows</h3>' + ov().pending(result["history_source"])
    rows = list(reversed(history["rows"]))
    skipped = 0

    def table(day_rows: list, caption: str) -> str:
        nonlocal skipped
        cells = []
        for row in day_rows:
            for lane in ("claude:main", "claude:agent_tool", "claude:workflow", "gpt:codex", "muse:muse"):
                values = row["lanes"].get(lane)
                if values is not None and values.get("unmeasured") == "not_configured":
                    skipped += 1
                    continue
                state = "" if row["complete"] else "<small>incomplete day</small>"
                cells.append([f'<time datetime="{esc(row["date"])}">{esc(row["date"])}</time>{state}'] + _lane_cells(lane, values))
        return _spanning(ov()._table(caption, ["Date"] + MEASURED_HEADER, cells, "atlas-daily", hide_caption=True), 12)

    out = '<h3>Daily rows</h3>'
    if not rows:
        return out + '<p class="lp-empty">The history holds no closed day yet.</p>'
    out += table(rows[:DAILY_VISIBLE], "Daily rows, newest first")
    if rows[DAILY_VISIBLE:]:
        out += f'<details class="lp-more"><summary>{len(rows) - DAILY_VISIBLE} older closed days</summary>{table(rows[DAILY_VISIBLE:], "Older daily rows")}</details>'
    if skipped:
        out += '<p class="atlas-note">Muse rows are left out while no Muse receipt root is configured.</p>'
    return out


def coverage(latest: dict) -> str:
    cover = latest["coverage"]
    parts = []
    if isinstance(cover.get("claude_actors"), int):
        parts.append(f'{cover["claude_actors"]:,} Claude agents, {_number(cover.get("claude_actors_incomplete"))} of them with incomplete usage, left out of the token sums')
    if isinstance(cover.get("codex_sessions"), int):
        parts.append(f'{cover["codex_sessions"]:,} Codex sessions, {_number(cover.get("codex_usage_incomplete"))} of them with incomplete usage')
    parts.append(f'{cover["muse_receipts"]:,} Muse runs' if isinstance(cover.get("muse_receipts"), int) else "Muse runs not measured")
    advised = [((latest["rollup"]["lanes"].get(lane) or {}).get("advisor") or {}) for lane in ("claude:main", "claude:agent_tool", "claude:workflow")]
    advisor = {key: sum(row[key] for row in advised if isinstance(row.get(key), int)) for key in ("input", "output")}
    advisor_line = ""
    if any(isinstance(row.get(key), int) for row in advised for key in ("input", "output")):
        advisor_line = (f'<p class="atlas-note">Advisor sub-inference, which the kernel counts apart, adds {advisor["input"]:,} input and {advisor["output"]:,} '
                        'output tokens for the complete agents; it is in neither the token columns nor the cache-read share. '
                        '<code>ccusage claude daily</code> counts it and the incomplete agents too, so its totals run higher.</p>')
    measured = latest["measured"]
    clients = ", ".join(f'{name} {"measured" if measured[key] else "not measured"}' for key, name in (("claude", "Claude"), ("codex", "Codex"), ("muse", "Muse")))
    return (f'<h3>Coverage and unknowns</h3><p class="atlas-note">Over the closed days: {"; ".join(parts)}. The latest run: {esc(clients)}.</p>' + advisor_line
            + '<p class="atlas-note">Workflow-tool runs are not counted: the kernel counts the agents a Workflow spawns, not its calls. '
            'Lanes are spawn kinds, never named sessions, and the Claude root covers every project on the host.</p>')


# ---------------------------------------------------------------- routing, monitoring, rules, changes, evidence
def _value(value: str | None, missing: str = "Not declared") -> str:
    if value is None:
        return _none(missing)
    if value == "UNREPORTED":
        return '<span class="atlas-status">UNREPORTED</span>'
    return f"<code>{esc(value)}</code>"


def routing_view(data: dict) -> str:
    result = data["routing"]
    order = {"claude": 0, "gpt": 1, "muse": 2}
    rows = []
    for row in sorted(result["rows"], key=lambda item: (order[item["family"]], item["role"])):
        family = f'{esc(FAMILY_LABELS[row["family"]])} <small>in {esc(row["client"])}</small>'
        if row["status"] != "present":
            rows.append([f'<code>{esc(row["role"])}</code>', family, _none("Pending: the definition is not in the checkout"), ""])
            continue
        rows.append([f'<code>{esc(row["role"])}</code>', family, _value(row["model"]),
                     _value(row["effort"], "Not declared" if row["family"] != "muse" else "Not set by the fence")])
    out = ov()._table("Declared model routing", ["Role", "Family and client", "Declared model", "Declared effort"], rows, "atlas-routing", hide_caption=True)
    out += ('<p class="atlas-cite">Declared in <code>adoption/agents/claude/*.md</code> frontmatter, <code>adoption/agents/codex/**/*.toml</code> and, for Muse, '
            f'<code>{esc(next((row["path"] for row in result["rows"] if row["family"] == "muse"), "tools/muse_file_fence.py"))}:'
            f'{esc(next((row.get("line") for row in result["rows"] if row["family"] == "muse"), ""))}</code>.</p>')
    observed = result["observed"]
    if not observed:
        return out + '<h3>Observed models</h3><p class="ov-trigger">The observed models appear once the daily token projection is published and readable.</p>'
    rows = []
    for lane in ("claude:main", "claude:agent_tool", "claude:workflow", "gpt:codex", "muse:muse"):
        models = observed.get(lane) or {}
        unit = MODEL_UNITS[lane.split(":", 1)[0]]
        if not models:
            rows.append([esc(LANE_LABELS[lane]), _none("None observed"), ""])
        for name, number in sorted(models.items(), key=lambda item: (-item[1], item[0])):
            rows.append([esc(LANE_LABELS[lane]), f"<code>{esc(name)}</code>", f"{number:,} {unit[0] if number == 1 else unit[1]}"])
    return (out + '<h3>Observed models over the closed days</h3>'
            + ov()._table("Observed models over the closed days", ["Lane", "Model", "Count"], rows, "atlas-observed", hide_caption=True)
            + '<p class="atlas-note">Declared and observed models stay apart: lanes are spawn kinds, not roles. '
              'Claude counts messages per model; Codex counts turns per configured model, since its rollouts carry no per-message model; Muse counts runs.</p>')


def monitoring_view(data: dict) -> str:
    entries = {row["id"]: row for row in data["monitoring"]}
    rows = []
    for row in data["monitoring"]:
        opened = row.get("open") or {}
        if opened.get("links"):
            how = ", ".join(f'<a href="{esc(link)}">{esc(link)}</a>' for link in opened["links"])
        elif opened.get("url"):
            how = f'<a href="{esc(opened["url"])}">{esc(opened["url"])}</a>'
        elif opened.get("commands"):
            how = "".join(f'<code class="atlas-command">{esc(command)}</code><br>' for command in opened["commands"]).removesuffix("<br>")
        elif opened.get("via") in entries:
            target = entries[opened["via"]]
            how = f'Through the {esc(target["title"])}' + (f': <a href="{esc(target["open"]["url"])}">{esc(target["open"]["url"])}</a>' if (target.get("open") or {}).get("url") else "")
        else:
            how = _none("No route recorded")
        record = ", ".join(f'<code>{esc(item["path"])}:{int(item["line"])}</code>' for item in row.get("cites") or [])
        rows.append([f'<strong>{esc(row["title"])}</strong>', esc(row["shows"]), how, record])
    out = ov()._table("Monitoring surfaces", ["Surface", "What it shows", "How to open it", "Record"], rows, "atlas-monitoring", hide_caption=True)
    note = data.get("port_note")
    if note:
        out += f'<p class="atlas-note">{esc(note["text"])}</p>' + _cite_list(note.get("cites") or [])
    return out


def rules_view(data: dict) -> str:
    rows = []
    for rule in data["rules"]:
        recorded = ", ".join(f'<code>{esc(item["path"])}:{int(item["line"])}</code>' for item in rule["recorded_in"]) or _none("No ruling record yet")
        if rule["related"]:
            recorded += '<small>Related: ' + ", ".join(f'<code>{esc(item["path"])}:{int(item["line"])}</code>' for item in rule["related"]) + "</small>"
        mechanism = ", ".join(f'<code>{esc(item["path"])}:{int(item["line"])}</code>' for item in rule["mechanism"]) or _none("No mechanism recorded")
        if rule.get("mechanism_note"):
            mechanism += f'<small>{esc(rule["mechanism_note"])}</small>'
        state = (f'<span class="lp-state-cell">{ov().glyph("FINAL")}Recorded</span>' if rule["state"] == "recorded"
                 else f'<span class="lp-state-cell">{ov().glyph("non-terminal")}Pending</span><small>Ready when {esc(rule["trigger"])}.</small>')
        rows.append([esc(rule["text"]), recorded, mechanism, state])
    return (ov()._table("Standing rules", ["Rule", "Recorded in", "Mechanism", "State"], rows, "atlas-rules", hide_caption=True)
            + '<p class="atlas-note">Each rule is a paraphrase of the owner\'s standing direction; no owner message is quoted. A rule without a ruling record stays pending until the CC names one.</p>')


def _change_text(change: dict) -> str:
    before = "none" if change["from"] is None else str(change["from"])
    after = "none" if change["to"] is None else str(change["to"])
    return f'<code>{esc(change["kind"])}</code> {esc(change["key"])}: {esc(before)} to {esc(after)}'


def changes_view(data: dict) -> str:
    ledger = data.get("ledger") or {}
    if ledger.get("status") == "unreported":
        return (f'<div class="ov-pending"><p class="ov-pending-state">{ov().glyph("non-terminal")}History unavailable: the ledger failed its check; it is kept for inspection.</p>'
                f'<dl class="lp-facts"><div><dt>Why</dt><dd>{esc(ledger.get("reason"))}</dd></div><div><dt>Record</dt><dd><code>atlas-ledger.json</code> (private record, cited by name)</dd></div>'
                '<div><dt>Ready when</dt><dd>the CC inspects the ledger and restores or retires it; this build appended nothing.</dd></div></dl></div>')
    rows = list(reversed(ledger.get("history") or []))
    if not rows:
        return '<p class="lp-empty">The ledger has no row yet: the first build that publishes this page writes one.</p>'
    if ledger.get("status") == "appended":
        head = f'This build appended row {rows[0]["seq"]}' + (" and starts the ledger." if rows[0]["seq"] == 1 and not ledger.get("dropped", {}).get("rows") else f' with {len(rows[0]["changes"])} change{"s" if len(rows[0]["changes"]) != 1 else ""}.')
    else:
        checks = ledger.get("checks_since_row")
        head = f'Nothing changed: this build matched row {rows[0]["seq"]}' + (f', checked {checks} time{"s" if checks != 1 else ""} since it was written.' if isinstance(checks, int) else ".")
    dropped = (ledger.get("dropped") or {}).get("rows") or 0
    chain = f'{len(rows)} row{"s" if len(rows) != 1 else ""}, every digest and link verified' + (f'; {dropped} older rows dropped past the cap, the last one anchored by its digest.' if dropped else ".")
    table_rows = []
    for row in rows[:CHANGES_VISIBLE]:
        listed = row["changes"]
        text = ('<ul class="ov-rows ov-tight">' + "".join(f"<li>{_change_text(change)}</li>" for change in listed[:12]) + "</ul>"
                + (f'<small>{len(listed) - 12} more in the ledger</small>' if len(listed) > 12 else "")) if listed else _none("The starting state" if row["seq"] == 1 else "No field changed")
        table_rows.append([str(row["seq"]), f'<time datetime="{esc(row["generated_utc"])}">{esc(row["generated_utc"])}</time>', text])
    return (f'<div class="ov-statement"><p class="lp-verdict">{esc(head)}</p></div><p class="atlas-note">Ledger <code>atlas-ledger.json</code> (private record, cited by name): {esc(chain)} '
            'A row is written only when the state changes: a new measured day, a catalog, slot, routing, rule-record or skill-pin change.</p>'
            + ov()._table("Ledger rows, newest first", ["Row", "Written", "What changed"], table_rows, "atlas-changes", hide_caption=True))


def evidence_view(data: dict) -> str:
    status = {"present": "read", "pending": "pending", "unreadable": "unreadable"}

    def item(source: dict) -> str:
        return f'<li><code>{esc(source.get("path") or source["declared"])}</code> <small>{esc(status.get(source["status"], source["status"]))}</small></li>'

    records = [source for source in data["sources"].values() if source["root"] == "repo"]
    agents = [source for source in records if source["section"] == "routing"]
    repository = "".join(item(source) for source in records if source["section"] != "routing")
    if agents:
        read = sum(1 for source in agents if source["status"] == "present")
        repository += (f'<li>{len(agents)} agent definitions under <code>adoption/agents/</code> <small>{read} read</small>'
                       f'<details class="lp-more"><summary>List them</summary><ul class="lp-refs">{"".join(item(source) for source in agents)}</ul></details></li>')
    private = "".join(f'<li><code>{esc(source["name"])}</code> <small>{esc(status.get(source["status"], source["status"]))}</small></li>'
                      for source in data["sources"].values() if source["root"] == "state")
    private += '<li><code>atlas-receipt.json</code> and <code>atlas-ledger.json</code> <small>written beside the refresh receipt, never served</small></li>'
    skills = data["skills"]
    rows = []
    for row in skills["rows"]:
        source = (f'{esc(row["source"])} at {ov()._pin(row["ref"])}' if row["source"] and row["ref"]
                  else _none("Source or pin withheld" if row["in_manifest"] else "Not in the manifest"))
        if row["path"]:
            source += f'<small><code>{esc(row["path"])}</code></small>'
        pin = ov()._pin(row["pin_sha256"]) if row["pin_sha256"] else _none("No pinned digest")
        match = ("Yes" if row["match"] else "No") if row["match"] is not None else (_none("No installed copy") if row["installed_reason"] == "not installed"
                                                                                       else _none("Installed copy unreadable") if row["installed_reason"] else _none("No pinned digest"))
        rows.append([f'<strong>{esc(row["name"])}</strong>', source, pin, match, esc(row["use"])])
    table = ov()._table("Skills at their pins", ["Skill", "Source at pin", "SKILL.md SHA-256", "Installed copy matches", "Use on this page"], rows, "atlas-skills", hide_caption=True)
    return (f'<div class="ov-evidence"><div><h3>Repository records</h3><ul class="lp-refs">{repository}</ul></div>'
            f'<div><h3>Private records, by name</h3><ul class="lp-refs">{private}</ul></div></div>'
            f'<h3>Skills at their pins</h3>{table}<p class="atlas-cite">Pins from <code>adoption/skills/manifest.json</code>; installed copies hashed through their exact grants. '
            f'Source locations live in <code>{esc(data["source_map"]["path"])}</code> and reviewed joins in <code>{esc(data["atlas_map"]["path"])}</code>.</p>')


def render(data: dict) -> tuple[str, dict]:
    nav = '<nav class="mf-jump" aria-label="Page sections"><ul>' + "".join(f'<li><a href="#{ident}">{esc(title)}</a></li>' for ident, title in SECTIONS) + "</ul></nav>"
    section = ov()._section
    body = [strip(data), nav,
            section("atlas-terms", "What the terms mean", "Four definitions; the three stacks are generated from their catalog requirements and practice slots.", terms(data)),
            section("atlas-layers", "Seven layers by family", "What each family runs at each harness layer, with the catalog record below each layer.", matrix(data)),
            section("atlas-stacks", "Three stacks", "Memory and retrieval, code intelligence and token efficiency, layer by layer.", stacks_view(data)),
            section("atlas-measured", "Measured use", "Per lane, from the daily token projection: MCP calls by stack, RTK use, spawned agents and prompt caching.", measured_view(data)),
            section("atlas-routing", "Model routing", "Each role's declared model and effort, then the models the lanes actually used.", routing_view(data)),
            section("atlas-monitoring", "How to watch it", "Each monitoring surface, what it shows and how to open it.", monitoring_view(data)),
            section("atlas-rules", "Standing rules", "The owner's standing rules, the record each is written in and the mechanism that carries it.", rules_view(data)),
            section("atlas-changes", "What changed", "The ledger this page keeps: one row each time the projected state changes.", changes_view(data)),
            section("atlas-evidence", "Sources and skills", "Every record this page read, private records by name, and the skills that shaped it at their pins.", evidence_view(data))]
    html = "".join(body)
    links = sorted(set(re.findall(r'href="(architecture-[a-z-]+\.html(?:#[a-z0-9-]+)?)"', html)))
    counts = {"sections": len(SECTIONS), "harness_layers": len(data["harness"]), "families": len(data["joins"]["families"]), "detail_links": links,
              "pending_sections": [ident for ident, ready in (("atlas-layers", data["architecture"]["status"] == "present"),
                                                              ("atlas-measured", data["measured"]["status"] == "present"),
                                                              ("atlas-evidence", data["skills"]["status"] == "present")) if not ready]}
    return html, counts
