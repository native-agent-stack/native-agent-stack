#!/usr/bin/env python3
"""Render the overview page body from overview_data.model().

Eight sections in a fixed order, each the shortest form that answers its
question: the layer-stack figure (diagram-design 2.6.73, type-layers.md, drawn
with architecture_diagrams' primitives and the local-pages tokens), one count
strip of stat figures (dataviz: figures, not a chart; state by shape and label),
ruled tables and pending blocks that name their readiness trigger. Private state
records appear by name only. All text is escaped here.
"""
from __future__ import annotations

from html import escape
import importlib.util
from pathlib import Path
import re
from typing import Any

HERE = Path(__file__).resolve().parent
LEDE = "Where the stack stands, in eight short sections. Every fact names its record; the Foundation and North-star pages hold the layer detail."
STATE_TEXT = {"FINAL": "Final", "SCHEDULED": "Scheduled", "RETIRED": "Retired", "non-terminal": "Not terminal"}
SECTIONS = (("ov-architecture", "Architecture at a glance"), ("ov-feeds", "Data feeds"), ("ov-strategies", "Strategies"),
            ("ov-workers", "Runtime workers"), ("ov-repos", "Repositories by layer"), ("overview-evidence", "Evidence"),
            ("ov-claude-code", "Claude Code"), ("ov-github", "GitHub"))
_LOADED: dict[str, Any] = {}


def _module(name: str) -> Any:
    if name not in _LOADED:
        spec = importlib.util.spec_from_file_location("local_overview_view_" + name, HERE / (name + ".py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _LOADED[name] = module
    return _LOADED[name]


def esc(value: Any) -> str:
    return escape(_module("sanitization").text("" if value is None else value), quote=True)


def anchor(layer: str) -> str:
    """The layer pages' register anchor (architecture_view._anchor)."""
    return "layer-" + re.sub(r"[^a-z0-9-]+", "-", layer.casefold()).strip("-")


def glyph(state: str | None) -> str:
    diagrams = _module("architecture_diagrams")
    key = diagrams.STATE_GLYPH.get(state or "")
    inner = diagrams._glyph(7, 7, key) if key else '<rect x="3" y="3" width="8" height="8" rx="2" class="mf-g-none"/>'
    return f'<svg class="mf-glyph" viewBox="0 0 14 14" aria-hidden="true" focusable="false">{inner}</svg>'


def _section(ident: str, title: str, intro: str, content: str) -> str:
    return (f'<section class="mf-view ov-section" id="{ident}" aria-labelledby="{ident}-title"><h2 id="{ident}-title">{esc(title)}</h2>'
            + (f'<p class="ov-intro">{intro}</p>' if intro else "") + content + "</section>")


def _record(source: dict) -> str:
    """A record reference: repository path, or a private state record by name."""
    if source.get("root") == "state":
        return f'<code>{esc(source.get("name"))}</code> (private record, cited by name)'
    return f'<code>{esc(source.get("path") or source.get("declared"))}</code>'


def pending(source: dict, *, record: bool = True) -> str:
    """A pending block with its trigger; inside a record the section already names, the record row is left out."""
    state = "Unreadable" if source.get("status") == "unreadable" else "Pending"
    reason = f'<div><dt>Why</dt><dd>{esc(source["reason"])}</dd></div>' if source.get("reason") else ""
    named = f'<div><dt>Record</dt><dd>{_record(source)}</dd></div>' if record else ""
    return (f'<div class="ov-pending"><p class="ov-pending-state">{glyph("non-terminal")}{state}</p><dl class="lp-facts">'
            f'<div><dt>Ready when</dt><dd>{esc(source.get("trigger"))}</dd></div>{named}{reason}</dl></div>')


def _table(caption: str, header: list[str], rows: list[list[str]], cls: str = "", *, hide_caption: bool = False) -> str:
    """A ruled table; when a visible heading already names it, its caption stays for screen readers only."""
    head = "".join(f'<th scope="col">{esc(cell)}</th>' for cell in header)
    body = "".join("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows)
    caption_class = ' class="ov-sr"' if hide_caption else ""
    return (f'<div class="table-wrap ov-table{" " + cls if cls else ""}" tabindex="0" role="region" aria-label="{esc(caption)}"><table><caption{caption_class}>{esc(caption)}</caption>'
            f'<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>')


# ---------------------------------------------------------------- strip
def strip(data: dict) -> str:
    """One quiet strip: the FINAL count as a sentence, the states as figures, then the sources present."""
    glance, sources = data["architecture"], data["sources"]
    present = sum(1 for source in sources.values() if source["status"] == "present")
    if glance["status"] != "present":
        sentence = "The layer records are pending, so no layer state is shown."
        row = ""
    else:
        total, finalized = glance["total"], glance["finalized"]
        sentence = (f"No layer is final yet: none of the {total} catalog layers meets the resolution protocol." if not finalized
                    else f"{finalized} of {total} catalog layers are final under the resolution protocol.")
        row = "".join(f'<div class="lp-stat"><dt>{glyph(state)}{esc(STATE_TEXT[state])}</dt><dd>{glance["states"][state]}</dd></div>'
                      for state in ("non-terminal", "FINAL", "SCHEDULED", "RETIRED"))
    row += f'<div class="lp-stat ov-stat-sources"><dt>Sources present</dt><dd>{present} of {len(sources)}</dd></div>'
    commit = data.get("commit")
    provenance = (f'Committed records at <code title="{esc(commit)}">{esc(commit[:12])}</code>; state records as published.' if commit
                  else "The commit of the committed records is unrecorded.")
    return (f'<section class="lp-strip" aria-label="Where the stack stands"><p class="lp-verdict">{esc(sentence)}</p>'
            f'<dl class="lp-stats">{row}</dl><p class="lp-provenance">{provenance}</p></section>')


# ---------------------------------------------------------------- figure
def _glance_draw(bands: list[dict]):
    diagrams = _module("architecture_diagrams")
    _rect, _t, _wrap, _width, _num = diagrams._rect, diagrams._t, diagrams._wrap, diagrams._width, diagrams._num

    def draw(variant: str, width: int, ident: str) -> tuple[str, float]:
        r = diagrams.RAMP[variant]
        pad, index_w = r["pad"], 40 if variant == "n" else 56
        left, right = pad + index_w, width - pad
        inset = 12 if variant == "n" else 16
        cell, gap = (16, 5) if variant == "n" else (20, 6)
        # One layer is the same width in every band; the band with the most layers fills its row.
        most = max([len(band["layers"]) for band in bands] + [1])
        span = right - left - 2 * (12 if variant == "n" else 16)
        wide = max(cell, min(56, int((span - gap * (most - 1)) / most)))
        top = pad + 20
        fills, seams, text, marks, used = [], [], [], [], set()
        y = top
        for position, band in enumerate(bands):
            inner_l, inner_r = left + inset, right - inset
            states = band["states"]
            name = band["label"] + " layers"
            counts = f'{len(band["layers"])} layer{"" if len(band["layers"]) == 1 else "s"}: {states["FINAL"]} final, {states["non-terminal"]} not terminal' + "".join(
                f', {states[state]} {STATE_TEXT[state].lower()}' for state in ("SCHEDULED", "RETIRED") if states[state])
            source = band["catalog_path"]
            text.append(_t(inner_l, y + 24, name, r["head"], bold=True))
            sub = _wrap(counts + " (" + source + ")", r["sub"], inner_r - inner_l, mono=True)
            if _width(name, r["head"], bold=True) + 24 + _width(counts, r["sub"], mono=True) <= inner_r - inner_l:
                text.append(_t(inner_r, y + 24, counts, r["sub"], "mf-mono mf-muted", anchor="end"))
                content = y + 38
            else:
                for offset, line in enumerate(sub):
                    text.append(_t(inner_l, y + 40 + offset * 13, line, r["sub"], "mf-mono mf-muted"))
                content = y + 50 + 13 * (len(sub) - 1)
            cx, cy = inner_l, content
            for layer in band["layers"]:
                if cx + wide > inner_r + 0.5:
                    cx, cy = inner_l, cy + cell + gap
                key = diagrams.STATE_GLYPH.get(layer["state"], "planned")
                used.add(layer["state"])
                marks.append(_rect(cx, cy, wide, cell, f"mf-cell-mini mf-s-{key}", rx=3,
                                   inner=f'<title>{diagrams._esc(str(layer["title"]) + ": " + STATE_TEXT.get(layer["state"], "no state"))}</title>'))
                cx += wide + gap
            height = diagrams._grid((cy + cell if band["layers"] else content + 14) - y + inset)
            if not band["layers"]:
                text.append(_t(inner_l, content + 12, "No catalog layer recorded", r["item"], "mf-muted"))
            focal = position == 0
            fills.append(_rect(left, y, right - left, height, "mf-focus" if focal else "mf-band", rx=0))
            text.append(_t(pad + index_w / 2 - 4, y + 24, f"L{len(bands) - position}", r["brow"] + 1, "mf-mono mf-muted", anchor="middle"))
            y += height
            seams.append(f'<line x1="{_num(left)}" y1="{_num(y)}" x2="{_num(right)}" y2="{_num(y)}" class="mf-seam"/>')
        frame = _rect(left, top, right - left, y - top, "mf-frame", rx=8)
        direction = (f'<line x1="{_num(pad + 4)}" y1="{_num(y - 8)}" x2="{_num(pad + 4)}" y2="{_num(top + 10)}" class="mf-flow" marker-end="url(#{ident}-arrow)"/>'
                     + _t(pad, top - 10, "Trading builds on the foundation", r["brow"], brow=True))
        states = [state for state in ("FINAL", "SCHEDULED", "non-terminal", "RETIRED") if state in used]
        legend, legend_h = diagrams._state_legend(pad, y + 28, width - 2 * pad, states, r, focus="Focus: the trading layers", flow=None)
        return "".join(fills + seams[:-1] + [frame, direction] + marks + text) + legend, y + 28 + legend_h + pad
    return draw


def architecture(data: dict) -> str:
    glance = data["architecture"]
    if glance["status"] != "present":
        return "".join(pending(source) for source in glance["missing"])
    diagrams = _module("architecture_diagrams")
    bands = sorted(glance["bands"], key=lambda band: band["catalog"] != "us-equities")
    desc = (f'{len(bands)} layer bands, trading above foundation: '
            + "; ".join(f'{band["label"]}, {len(band["layers"])} layers, {band["finalized"]} final' for band in bands) + f'. {glance["finalized"]} of {glance["total"]} layers are final.')
    planned = [row for band in bands for row in band["planned"]]
    marks = {"FINAL": "a filled cell is final", "SCHEDULED": "a solid outline is scheduled", "non-terminal": "a dashed outline is not terminal",
             "RETIRED": "a dotted outline is retired"}
    drawn = [marks[state] for state in marks if any(layer["state"] == state for band in bands for layer in band["layers"])]
    caption = ("Layer stack, foundation at the bottom. Each cell is one catalog layer, in catalog order, with the state computed from "
               "catalogs/landscape/final-stack.json and the component evidence matrix" + (": " + ", ".join(drawn) if drawn else "")
               + ". The text view names every layer.")
    if planned:
        caption += f' final-stack.json also lists {len(planned)} planned layers outside the catalog files; they are not drawn.'
    figure = diagrams._figure("glance", "Architecture at a glance", desc, _glance_draw(bands), esc(caption))
    items = "".join(f'<li><strong>{esc(band["title"])}</strong> (<a href="{esc(band["page"])}">{esc(band["label"])} page</a>): '
                    + esc(", ".join(f'{layer["title"]} {STATE_TEXT.get(layer["state"], "no state").lower()}' for layer in band["layers"])) + ".</li>" for band in bands)
    links = '<p class="ov-links">Layer detail: ' + " and ".join(f'<a href="{esc(band["page"])}">{esc(band["title"])}</a>' for band in reversed(bands)) + ".</p>"
    return figure + diagrams._alt("Read the diagram as text", f"<ul>{items}</ul>") + links


# ---------------------------------------------------------------- sections
def statement(result: dict | None) -> str:
    """The section's plain statement until its result record exists; then that record, by name."""
    if not result:
        return ""
    if result["status"] == "present":
        return f'<p class="ov-record">{esc(result["label"])}: {_record(result)}.</p>'
    trigger = str(result["trigger"])
    return (f'<div class="ov-statement"><p class="lp-verdict">{esc(result["text"])}</p>'
            f'<p class="ov-trigger">That changes when {esc(trigger)}.</p></div>')


def _missing(parts: list[str]) -> str:
    return f'<p class="lp-empty">Not in the record: {esc(", ".join(parts))}.</p>' if parts else ""


def _items(rows: list[str], cls: str = "ov-rows") -> str:
    return f'<ul class="{cls}">' + "".join(f"<li>{esc(row)}</li>" for row in rows) + "</ul>" if rows else ""


WITHHELD = '<span class="ov-none">Withheld: it cites a path, digest or line</span>'
POINT_LABELS = {"baseline": "Baseline", "lagging": "Lagging or conditioning", "gated": "Gated"}


def feeds(data: dict) -> str:
    result = data["feeds"]
    if result["status"] != "present":
        return pending(result)
    out = f'<p class="ov-record">From the command center\'s WS2 convergence record {_record(result)}.</p>' + statement(result.get("statement"))
    missing = []
    table = result.get("table")
    if table:
        caption = result.get("caption") or f'Rows with a {result["column"]} column'
        rows = [[WITHHELD if cell is None else esc(cell) for cell in row] for row in table["rows"]]
        out += f'<h3>{esc(caption)}</h3>' + _table(caption, table["header"], rows, "ov-signals", hide_caption=True)
    else:
        missing.append(f'a table with a {result["column"]} column')
    points = result.get("points") or {}
    cells = []
    for key in ("baseline", "lagging", "gated"):
        point = points.get(key)
        if point is None:
            missing.append(f"the {key} item")
            continue
        body = (f'<p>{esc(" ".join(point["sentences"]))}</p>' if point["sentences"] else "") + _items(point["rows"])
        cells.append(f'<div><dt>{esc(point["lead"] or POINT_LABELS[key])}</dt><dd>{body}</dd></div>')
    if cells:
        out += f'<dl class="ov-points">{"".join(cells)}</dl>'
    if result.get("gaps"):
        out += ('<h3>Gaps in the first-hand live stack</h3><ul class="ov-gaps">'
                + "".join(f'<li><strong>{esc(gap["name"])}.</strong>' + (f' {esc(" ".join(gap["sentences"]))}' if gap["sentences"] else "") + "</li>"
                          for gap in result["gaps"]) + "</ul>")
    else:
        missing.append("the live-stack gaps")
    return out + entitlements(result.get("addendum")) + _missing(missing)


def entitlements(extra: dict | None) -> str:
    """The addendum's results under the gaps, by record name; a line with its trigger until it exists."""
    if not extra:
        return ""
    if extra["status"] == "other":
        return f'<p class="ov-trigger">The newest addendum, {_record(extra)}, belongs to another convergence record than {esc(extra["record"])}.</p>'
    if extra["status"] != "present":
        return f'<p class="ov-trigger">Entitlement results: {esc(extra["status"])}; ready when {esc(extra["trigger"])}.</p>'
    rows = "".join(f'<li><strong>{esc(row["subject"])}:</strong>' + (f' {esc(" ".join(row["sentences"]))}' if row["sentences"] else "") + "</li>"
                   for row in extra["results"])
    return (f'<h3>Entitlement results</h3><p class="ov-record">From the addendum {_record(extra)}.</p>'
            + (f'<ul class="ov-gaps">{rows}</ul>' if rows else '<p class="lp-empty">The addendum states no result.</p>'))


def strategies(data: dict) -> str:
    result = data["strategies"]
    if result["status"] != "present":
        return pending(result)
    out = f'<p class="ov-record">From the command center\'s WS5 convergence record {_record(result)}.</p>' + statement(result.get("statement"))
    missing, columns = [], []
    family = result.get("family")
    if family:
        claim = f'{esc(family["lead"])}.' if family["lead"] else WITHHELD
        out += f'<div class="ov-family"><h3>Shortlisted family</h3><p class="ov-claim">{claim}</p></div>'
        columns.append('<div><h3>Evidence caveats</h3>' + (_items(family["caveats"]) if family["caveats"] else '<p class="lp-empty">The record states no caveat for it.</p>') + "</div>")
    else:
        missing.append(f'an item whose lead names "{result["selectors"]["family"]}"')
    ablations = result.get("ablations")
    if ablations:
        intro = " ".join(part for part in ((ablations["lead"] + ".") if ablations["lead"] else "", ablations["intro"]) if part)
        columns.append(f'<div><h3>Ablations</h3><p>{esc(intro)}</p>{_items(ablations["rows"])}</div>')
    else:
        missing.append("the ablation rows")
    sizing = result.get("sizing")
    if sizing:
        columns.append(f'<div><h3>{esc(sizing["lead"] or "Selector and sizing")}</h3>{_items(sizing["rows"])}</div>')
    else:
        missing.append("the selector and sizing rule")
    if columns:
        out += f'<div class="ov-columns">{"".join(columns)}</div>'
    return out + _missing(missing)


def _state_cell(state: dict) -> str:
    if state["status"] == "no source":
        return '<span class="ov-none">No state source yet</span>'
    if state["status"] != "present":
        return f'Pending: {_record(state)}; ready when {esc(state["trigger"])}.' + (f' <small>{esc(state["reason"])}</small>' if state.get("reason") else "")
    detail = ""
    if state.get("layers"):
        detail = "<small>" + "; ".join(f'winner in <a href="{"architecture-foundation.html" if row["layer"].startswith("foundation/") else "architecture-north-star.html"}#{anchor(row["layer"])}">{esc(row["layer"])}</a>, '
                                      f'{esc(STATE_TEXT.get(row["state"], "no state").lower())}' for row in state["layers"]) + "</small>"
    elif state.get("as_of"):
        detail = f'<small>as of {esc(state["as_of"])}</small>'
    return esc(state["text"]) + detail


def _receipt_cell(receipt: dict) -> str:
    if receipt["status"] == "no source":
        return '<span class="ov-none">No receipt source yet</span>'
    if receipt["status"] == "none":
        return esc(receipt["reason"])
    if receipt["status"] != "present":
        return f'Pending: {_record(receipt)}; ready when {esc(receipt["trigger"])}.'
    date = f' <small>{esc(receipt["date"])}' + (f', newest of {receipt["count"]} registered' if receipt["count"] > 1 else "") + "</small>" if receipt.get("date") else ""
    return f'<code>{esc(receipt["path"])}</code>{date}'


def workers(data: dict) -> str:
    rows = [[f'<strong>{esc(row["name"])}</strong><small>{esc(row["role"])}</small>', _state_cell(row["state"]), _receipt_cell(row["receipt"])] for row in data["workers"]]
    return _table("Runtime workers, SDKs and harnesses", ["Worker", "State", "Newest receipt"], rows, "ov-workers", hide_caption=True)


def _pin(pin: Any) -> str:
    """A run pin; a full commit shows its first 12 characters with the whole pin in its title."""
    text = str(pin)
    if re.fullmatch(r"[0-9a-f]{40}", text):
        return f'<code title="{esc(text)}">{esc(text[:12])}</code>'
    return f"<code>{esc(text)}</code>"


def repos(data: dict) -> str:
    result = data["repos"]
    if result["status"] != "present":
        return "".join(pending(source) for source in result["missing"])
    note = (f'<p class="ov-record">Winners and run pins from <code>catalogs/landscape/final-stack.json</code>; next actions from {_record({"root": "state", "name": result["rows_record"]})}.</p>'
            if result["rows_record"] else "")
    out = note + (pending(result["rows_pending"]) if result.get("rows_pending") else "")
    for group in result["groups"]:
        # One state shared by every catalog layer is said once above the table instead of on every row.
        catalog_states = {row["state"] for row in group["rows"] if row["in_catalog"]}
        shared = next(iter(catalog_states)) if len(catalog_states) == 1 and None not in catalog_states else None
        rows = []
        for row in group["rows"]:
            planned = "" if row["in_catalog"] else " <small>planned, outside the catalog file" + (f'; {esc(row["status"])}' if shared and row["status"] else "") + "</small>"
            link = (f'<a href="{esc(row["page"])}#{anchor(row["layer"])}" title="{esc(row["layer"])}">{esc(row["title"])}</a>' if row["in_catalog"]
                    else f'<a href="{esc(row["page"])}" title="{esc(row["layer"])}">{esc(row["title"])}</a>{planned}')
            state = f'<span class="lp-state-cell">{glyph(row["state"])}{esc(STATE_TEXT[row["state"]])}</span>' if row["state"] else esc(row["status"] or "no state")
            winners = ", ".join(f'{esc(winner["component"])} {_pin(winner["run_pin"])}' if winner["run_pin"] else f'{esc(winner["component"])} <small>no run pin ({esc(winner["run_reason"])})</small>'
                                  for winner in row["winners"]) or '<span class="ov-none">No winner</span>'
            action = esc("; ".join(row["next_action"])) if row["next_action"] else ('<span class="ov-none">Pending</span>' if result.get("rows_pending") else '<span class="ov-none">Not in the rows</span>')
            rows.append([link] + ([] if shared else [state]) + [winners, str(row["survivors"]), action])
        header = ["Layer"] + ([] if shared else ["State"]) + ["Winners at run pin", "Survivors", "Next action"]
        count = sum(1 for row in group["rows"] if row["in_catalog"])
        summary = (f'<p class="ov-group-state">{glyph(shared)}{count} catalog layer{"s" if count != 1 else ""}, {"all " if count != 1 else ""}{esc(STATE_TEXT[shared].lower())}.</p>'
                   if shared else "")
        out += f'<h3>{esc(group["label"])}</h3>{summary}' + _table(f'{group["label"]} layers', header, rows, "ov-repos ov-shared" if shared else "ov-repos", hide_caption=True)
    return out


def evidence(data: dict) -> str:
    result = data["evidence"]
    status = {"present": "read", "pending": "pending", "unreadable": "unreadable"}
    repository = "".join(f'<li><code>{esc(row["path"])}</code> <small>{esc(status.get(row["status"], row["status"]))}</small></li>' for row in result["repository"])
    private = "".join(f'<li><code>{esc(row["name"])}</code> <small>{esc(status.get(row["status"], row["status"]))}</small></li>' for row in result["private"])
    pages = "".join(f'<li><a href="{esc(row["page"])}">{esc(row["title"])}</a></li>' for row in result["pages"])
    return (f'<div class="ov-evidence"><div><h3>Repository records</h3><ul class="lp-refs">{repository}</ul></div>'
            f'<div><h3>Private records, by name</h3><ul class="lp-refs">{private}</ul></div>'
            f'<div><h3>Layer detail</h3><ul class="lp-refs">{pages}</ul><p class="ov-intro">Source locations live in <code>{esc(data["source_map"]["path"])}</code>.</p></div></div>')


def claude_code(data: dict) -> str:
    result = data["claude_code"]
    if result["status"] != "present":
        return pending(result)
    out = f'<p class="ov-record">From {_record(result)}.</p><p class="lp-verdict">Pinned client {esc(result["pin"] or "not stated in the record")}</p>'
    for name, title in (("changelog", "CHANGELOG delta"), ("screen", "Best-practice screen")):
        table = result["tables"].get(name)
        out += (_table(title, table["header"], [[esc(cell) for cell in row] for row in table["rows"]]) if table
                else f'<p class="lp-empty">The record has no table under a heading naming "{esc(result["headings"].get(name))}".</p>')
    return out


def github(data: dict) -> str:
    result = data["github"]
    if result["status"] != "present":
        return pending(result)
    main = result["main_ci"]
    if main is None:
        main_html = pending({"status": "pending", "root": "state", "name": result["name"],
                             "trigger": f'the command center adds a {result["main_ci_key"]} entry to its current view'}, record=False)
    elif isinstance(main, dict):
        main_html = '<dl class="lp-facts">' + "".join(f'<div><dt>{esc(key)}</dt><dd>{esc(value)}</dd></div>' for key, value in main.items()) + "</dl>"
    else:
        main_html = f"<p>{esc(main)}</p>"
    review = _table("Pull requests in review", ["Pull request", "Head", "State", "Next gate"],
                    [[esc(row["pr"]), f'<code>{esc(row["head"])}</code>', esc(row["state"]), esc(row["next_gate"])] for row in result["in_review"]], "ov-review", hide_caption=True)
    queue = '<ol class="ov-queue">' + "".join(f"<li>{esc(item)}</li>" for item in result["landing_queue"]) + "</ol>" if result["landing_queue"] else '<p class="lp-empty">The landing queue is empty.</p>'
    return (f'<p class="ov-record">From {_record(result)}, updated {esc(result["updated_utc"])}.</p><h3>Main CI</h3>{main_html}'
            f'<h3>In review ({len(result["in_review"])})</h3>{review}<h3>Landing queue ({len(result["landing_queue"])})</h3>{queue}')


def render(data: dict) -> tuple[str, dict]:
    nav = '<nav class="mf-jump" aria-label="Page sections"><ul>' + "".join(f'<li><a href="#{ident}">{esc(title)}</a></li>' for ident, title in SECTIONS) + "</ul></nav>"
    body = [strip(data), nav,
            _section("ov-architecture", "Architecture at a glance", "The two landscape catalogs as layers, with each layer's state under the resolution protocol.", architecture(data)),
            _section("ov-feeds", "Converged data feeds for early entry on extreme movers", "The signals both blind judges converged on, and the gaps in the live stack.", feeds(data)),
            _section("ov-strategies", "Strategies", "The extreme-mover strategy shortlist both blind judges converged on.", strategies(data)),
            _section("ov-workers", "Runtime workers, SDKs and harnesses", "Each worker's recorded state and its newest receipt. A worker without a named source says so.", workers(data)),
            _section("ov-repos", "Repositories and candidates by layer", "Per layer: the winners at their run pins, the surviving candidates and the next action.", repos(data)),
            _section("overview-evidence", "Evidence", "The records this page read. Private records are named, never quoted.", evidence(data)),
            _section("ov-claude-code", "Claude Code", "The pinned client, the 2.1.295 to 2.1.300 CHANGELOG delta and the best-practice screen.", claude_code(data)),
            _section("ov-github", "GitHub", "Main CI and the open pull-request queue from the command center's current view.", github(data))]
    links = sorted(set(re.findall(r'href="(architecture-[a-z-]+\.html(?:#[a-z0-9-]+)?)"', "".join(body))))
    counts = {"sections": len(SECTIONS), "detail_links": links, "workers": len(data["workers"]),
              "pending_sections": [ident for ident, key in (("ov-feeds", "feeds"), ("ov-strategies", "strategies"), ("ov-claude-code", "claude_code"), ("ov-github", "github"))
                                   if data[key]["status"] != "present"]}
    return "".join(body), counts
