"""Render the Architecture manifest as inline SVG figures and HTML text views.

Diagram grammar follows the diagram-design skill (Claude Code plugin
diagram-design 2.6.73: SKILL.md sections 6, 7, 9 and 12, with references
type-layers.md, type-deployment.md, type-data-flow.md, primitives-core.md,
output-spec.md and style-guide.md); the page shell follows frontend-design.
Colors come from the local-pages tokens through assets/architecture-manifest.css
and fonts are the system stacks, so nothing is fetched. Each view ships wide,
medium and narrow variants that a container query selects; every variant has
its own title, desc and marker IDs. All text comes from the manifest projection
and is escaped here.
"""
from __future__ import annotations

from html import escape
import importlib.util
import math
from pathlib import Path
import re
from typing import Any, Callable

VARIANTS = (("w", 1200), ("m", 720), ("n", 400))
RAMP = {
    "w": {"pad": 40, "head": 14, "name": 12, "item": 11, "sub": 9, "brow": 8, "line": 15},
    "m": {"pad": 32, "head": 14, "name": 12, "item": 11, "sub": 9, "brow": 8, "line": 15},
    "n": {"pad": 16, "head": 15, "name": 13, "item": 12, "sub": 10, "brow": 9, "line": 16},
}
STATUS_LABEL = {"built": "Built", "adopted": "Adopted", "candidate": "Candidate", "planned": "Planned"}
STATUS_RULE = {
    "built": "A record establishes it on this host: a gate marked established, or a verdict winner whose linux-wsl2-x86_64 E2E is accepted or host-verified.",
    "adopted": "Selected by a recorded verdict or by the install plan's default run, without a host-established record in that view.",
    "candidate": "Still under comparison: the layer's verdict lanes are pending.",
    "planned": "Recorded but not yet in place: a gate not established, a paid entitlement or user decision, or a plan row the default run skips.",
}
DESIGN = {"diagram_design": "diagram-design 2.6.73 (types: layer stack, deployment, data flow)",
          "frontend_design": "frontend-design (page shell)", "font_source": "system", "variants": [width for _, width in VARIANTS]}
_SANITIZER = None


def _sanitizer():
    global _SANITIZER
    if _SANITIZER is None:
        spec = importlib.util.spec_from_file_location("architecture_diagram_text", Path(__file__).with_name("sanitization.py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _SANITIZER = module
    return _SANITIZER


def _esc(value: Any) -> str:
    return escape(_sanitizer().text(value), quote=True)


def _num(value: float) -> str:
    value = round(value, 1)
    return str(int(value)) if value == int(value) else f"{value:.1f}"


def _grid(value: float) -> int:
    return int(math.ceil(value / 4.0) * 4)


def _width(text: str, size: float, *, mono: bool = False, bold: bool = False) -> float:
    return len(text) * size * (0.62 if mono else 0.6 if bold else 0.56)


def _brow_width(text: str, size: float) -> float:
    """Uppercase eyebrow text: the mono advance plus its 0.14em tracking."""
    return len(text) * size * (0.62 + 0.14)


def _split_token(token: str, cap: int) -> list[str]:
    """Split one over-long identifier at - _ / where possible, else at the cap."""
    parts, line = [], ""
    for piece in re.findall(r"[^\-/_]+[\-/_]*|[\-/_]+", token):
        while len(piece) > cap:
            if line:
                parts.append(line)
                line = ""
            parts.append(piece[:cap])
            piece = piece[cap:]
        if len(line) + len(piece) <= cap:
            line += piece
        else:
            parts.append(line)
            line = piece
    return parts + ([line] if line else [])


def _wrap(text: str, size: float, limit: float, *, mono: bool = False, bold: bool = False, lines: int = 2) -> list[str]:
    """Wrap at spaces; an identifier longer than a line breaks at its own separators."""
    cap = max(3, int(limit / (size * (0.62 if mono else 0.6 if bold else 0.56))))
    if len(text) <= cap:
        return [text]
    out, line = [], ""
    for word in text.split():
        candidate = f"{line} {word}" if line else word
        if len(candidate) <= cap:
            line = candidate
            continue
        if line:
            out.append(line)
        if len(word) <= cap:
            line = word
        else:
            *full, line = _split_token(word, cap)
            out += full
    if line:
        out.append(line)
    if len(out) > lines:
        out = out[:lines]
        out[-1] = out[-1][:cap - 1].rstrip() + "…"
    return out


def _rect(x: float, y: float, w: float, h: float, cls: str, rx: float = 6, inner: str = "") -> str:
    body = f'<rect x="{_num(x)}" y="{_num(y)}" width="{_num(w)}" height="{_num(h)}" rx="{_num(rx)}" class="{cls}"'
    return body + (f'>{inner}</rect>' if inner else '/>')


def _t(x: float, y: float, text: str, size: float, cls: str = "", *, anchor: str = "start", bold: bool = False, brow: bool = False) -> str:
    attrs = f' x="{_num(x)}" y="{_num(y)}" font-size="{_num(size)}"'
    if anchor != "start":
        attrs += f' text-anchor="{anchor}"'
    if bold:
        attrs += ' font-weight="600"'
    if brow:
        text, cls = text.upper(), (cls + " mf-brow").strip()
    if cls:
        attrs += f' class="{cls}"'
    return f"<text{attrs}>{_esc(text)}</text>"


def _glyph(cx: float, cy: float, status: str | None) -> str:
    if status == "built":
        return _rect(cx - 4, cy - 4, 8, 8, "mf-g-built", rx=1)
    if status == "adopted":
        return f'<circle cx="{_num(cx)}" cy="{_num(cy)}" r="4" class="mf-g-adopted"/>'
    if status == "candidate":
        return f'<circle cx="{_num(cx)}" cy="{_num(cy)}" r="3.6" class="mf-g-candidate"/>'
    if status == "planned":
        return _rect(cx - 3.5, cy - 3.5, 7, 7, "mf-g-planned", rx=0)
    if status == "focus":
        return _rect(cx - 6, cy - 4, 12, 8, "mf-g-focus", rx=2)
    return ""


def _defs(ident: str) -> str:
    marker = '<marker id="{0}" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><path d="M0,0 L8,3 L0,6 Z" class="{1}"/></marker>'
    return "<defs>" + marker.format(ident + "-arrow", "mf-arrowhead") + marker.format(ident + "-arrow-focus", "mf-arrowhead-focus") + "</defs>"


def _legend(x: float, y: float, width: float, keys: list[str], ramp: dict, flow_marker: str | None = None) -> tuple[str, float]:
    """Bottom legend strip (primitives-core.md): only the marks this view uses."""
    size, out = ramp["sub"] + 1, [f'<line x1="{_num(x)}" y1="{_num(y)}" x2="{_num(x + width)}" y2="{_num(y)}" class="mf-seam"/>']
    out.append(_t(x, y + 20, "Legend", ramp["brow"], brow=True))
    start = x + _brow_width("LEGEND", ramp["brow"]) + 24
    cx, row = start, y + 20
    items = [(key, STATUS_LABEL.get(key, "Focus")) for key in keys] + ([("flow", "Flow")] if flow_marker else [])
    for key, label in items:
        span = 18 + _width(label, size) + 24
        if cx + span > x + width and cx > start:
            cx, row = start, row + 20
        if key == "flow":
            out.append(f'<line x1="{_num(cx - 2)}" y1="{_num(row - 4)}" x2="{_num(cx + 12)}" y2="{_num(row - 4)}" class="mf-flow" marker-end="url(#{flow_marker})"/>')
        else:
            out.append(_glyph(cx + 5, row - 4, key))
        out.append(_t(cx + 18, row, label, size, "mf-muted"))
        cx += span
    return "".join(out), row - y + 12


def _figure(slug: str, title: str, desc: str, draw: Callable[[str, int, str], tuple[str, float]], caption: str) -> str:
    parts = [f'<figure class="mf-figure" id="mf-{slug}-figure">']
    for variant, width in VARIANTS:
        ident = f"mf-{slug}-{variant}"
        body, height = draw(variant, width, ident)
        height = _grid(height)
        parts.append(f'<svg class="mf-svg mf-v mf-v--{variant}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="{ident}-title {ident}-desc">'
                     f'<title id="{ident}-title">{_esc(title)}</title><desc id="{ident}-desc">{_esc(desc)}</desc>{_defs(ident)}'
                     f'<rect class="mf-paper" width="{width}" height="{height}"/>{body}</svg>')
    parts.append(f"<figcaption>{caption}</figcaption></figure>")
    return "".join(parts)


def _flow(chips: list[dict], left: float, right: float, top: float, ramp: dict, gap: float = 8) -> tuple[list[dict], float]:
    """Place two-line chips left to right, wrapping rows inside the band."""
    name, sub, height = ramp["name"], ramp["sub"], 36 if ramp["name"] == 12 else 40
    placed, x, y = [], left, top
    for chip in chips:
        lead = 18 if chip.get("status") else 12
        width = min(right - left, _grid(lead + max(_width(chip["name"], name, bold=True), _width(chip.get("sub") or "", sub, mono=True)) + 12))
        spacing = 28 if chip.get("arrow_from_previous") else gap
        if placed and x + spacing + width > right:
            x, y = left, y + height + 8
            chip = {**chip, "arrow_from_previous": False}
        elif placed:
            x += spacing
        placed.append({**chip, "x": x, "y": y, "w": width, "h": height, "lead": lead})
        x += width
    return placed, (y + height - top) if chips else 0


def _chip(chip: dict, ramp: dict) -> str:
    cls = "mf-chip mf-focus" if chip.get("focus") else "mf-chip" + (f" mf-s-{chip['status']}" if chip.get("status") else "")
    x, y, w, lead = chip["x"], chip["y"], chip["w"], chip["lead"]
    out = [_rect(x, y, w, chip["h"], cls, rx=4)]
    if chip.get("status"):
        out.append(_glyph(x + 9, y + 12, chip["status"]))
    room = w - lead - 6
    out.append(_t(x + lead, y + 15, _wrap(chip["name"], ramp["name"], room, bold=True, lines=1)[0], ramp["name"], bold=True))
    if chip.get("sub"):
        out.append(_t(x + lead, y + 29 + (2 if ramp["name"] > 12 else 0), _wrap(chip["sub"], ramp["sub"], room, mono=True, lines=1)[0], ramp["sub"], "mf-mono mf-muted"))
    return "".join(out)


def _join(*parts: str | None) -> str:
    return ", ".join(part for part in parts if part)


def _day(label: str, value: str | None) -> str | None:
    return f"{label} {value}" if value else None


# ---------------------------------------------------------------- overview
def overview_bands(views: dict) -> list[dict]:
    """The six layers, bottom to top, as fixed names over recorded values."""
    plan, handbook, orch = views.get("plan"), views.get("handbook"), views.get("orchestration") or {}
    matrix, ruleset, gates, runtime = views.get("matrix"), views.get("ruleset"), views.get("gates"), views.get("runtime")
    pages = views.get("pages") or {}
    services = {row["slot"]: row for row in (plan or {}).get("services", [])}

    def service(slot: str, role: str) -> dict | None:
        row = services.get(slot)
        return {"name": row["name"], "sub": f"{role} :{row['port']}" if row["port"] else role, "status": row["status"]} if row else None

    host = []
    if handbook:
        host.append({"name": "Windows host", "sub": f"WSL {handbook['wsl_minimum']} or later" if handbook.get("wsl_minimum") else "WSL release target"})
    if plan:
        host += [{"name": "WSL2 distribution", "sub": plan.get("base") or "base unreported"},
                 {"name": "User services", "sub": f"{len(plan['services'])} in the install plan"}]
        host += [chip for chip in (service("gpt-gateway", "gateway"), service("memory-owner", "memory")) if chip]
        observed = [services[slot]["name"] for slot in ("otel-collector-contrib", "prometheus", "loki") if slot in services]
        if observed:
            host.append({"name": "Observability", "sub": ", ".join(observed)})
    hours = orch.get("window_hours")
    agents = [{"name": tier["label"], "sub": "command-center role", "key": tier["key"]} for tier in orch.get("tiers", [])]
    if orch.get("codex_lanes") is not None:
        conversations = orch.get("codex_conversations")
        agents.append({"name": "Codex lanes", "sub": f"{orch['codex_lanes']} lanes, {conversations if conversations is not None else 'unmeasured'} conversations / {hours} h",
                       "arrow_from_previous": bool(agents and agents[-1].get("key") == "co_op")})
    if orch.get("claude_roles") is not None:
        sessions = orch.get("claude_sessions")
        agents.append({"name": "Claude roles", "sub": f"{orch['claude_roles']} roles, {sessions if sessions is not None else 'unmeasured'} sessions / {hours} h"})
    automation = []
    if ruleset:
        checks = ruleset.get("checks", [])
        automation.append({"name": "Required checks", "sub": f"{len(checks)} on " + (", ".join(branch.removeprefix("refs/heads/") for branch in ruleset.get("branches", [])) or "the target")})
        if "verdict-review-gate" in checks:
            automation.append({"name": "Verdict review gate", "sub": "required check"})
        if ruleset.get("merge_methods") == ["squash"]:
            automation.append({"name": "Squash merges only", "sub": "pull request rule"})
        if ruleset.get("linear_history"):
            automation.append({"name": "Linear history", "sub": "no force push" if ruleset.get("no_force_push") else "required"})
        if ruleset.get("thread_resolution"):
            approvals = ruleset.get("approvals")
            automation.append({"name": "Review threads resolved", "sub": f"{approvals} approvals required" if approvals is not None else "required"})
        automation += [{"name": scan["tool"], "sub": "alerts " + (scan.get("threshold") or "recorded").replace("_", " ")} for scan in ruleset.get("code_scanning", [])]
    desk = []
    winners = {winner["id"]: winner for row in (matrix or {}).get("rows", []) for winner in row["winners"]}
    gate_rows = (gates or {}).get("gates", [])
    if runtime and runtime["engine"].get("name"):
        engine = runtime["engine"]
        desk.append({"name": f"{engine['name']} {engine.get('version') or ''}".strip(), "sub": (engine.get("decision") or "recorded").replace("_", " "),
                     "status": (winners.get("nautilustrader") or {}).get("status")})
    for broker in (runtime or {}).get("brokers", []):
        gate = next((row for row in gate_rows if row["id"].startswith(broker + "-") and row["layer"] == "execution-broker"), None)
        desk.append({"name": {"alpaca": "Alpaca paper", "ibkr": "IBKR paper"}.get(broker, broker), "sub": f"gate {gate['id']}" if gate else "no gate recorded",
                     "status": gate["status"] if gate else None})
    if runtime and runtime.get("policies"):
        desk.append({"name": "Adaptive policies", "sub": f"{len(runtime['policies'])} in the runtime target"})
    if gates:
        desk.append({"name": "Gate ladder", "sub": f"{gates['established']} of {len(gate_rows)} established"})
    watch = [chip for chip in (service("grafana", "dashboards"), service("alerting", "alerts"), service("session-analytics", "sessions")) if chip]
    if pages.get("names"):
        watch.append({"name": "Local pages", "sub": f"{len(pages['names'])} pages"})
    cells = [{"title": row["title"], "status": row["status"], "group": row["catalog"], "verdict": row["verdict_status"]} for row in (matrix or {}).get("rows", [])]
    verdicts = (matrix or {}).get("verdicts") or {}
    return [
        {"index": "L1", "name": "Host and runtime", "anchor": "mf-host", "chips": host,
         "source": _join(_day("install plan", (plan or {}).get("revised")), _day("handbook", (handbook or {}).get("as_of")))},
        {"index": "L2", "name": "Agents and orchestration", "chips": agents,
         "source": _join(_day("cc-now", orch.get("cc_updated")), _day("adoption snapshot", orch.get("snapshot")))},
        {"index": "L3", "name": "Foundation layers", "anchor": "mf-layers", "cells": cells,
         "source": _join(_day("matrix", (matrix or {}).get("checked_at")), ", ".join(f"{count} {name.replace('_', ' ')}" for name, count in verdicts.items()))},
        {"index": "L4", "name": "GitHub automation", "chips": automation,
         "source": ".github/main-ruleset.json" + (f", {ruleset['enforcement']}" if ruleset and ruleset.get("enforcement") else "") if ruleset else None},
        {"index": "L5", "name": "North-star trading desk", "anchor": "mf-desk", "chips": desk, "focus": True,
         "source": _join(_day("gate ladder", (gates or {}).get("checked_at")), _day("runtime target", (runtime or {}).get("reviewed_at")))},
        {"index": "L6", "name": "Monitoring and local pages", "chips": watch,
         "source": _join(_day("install plan", (plan or {}).get("revised")), _day("pages refresh", pages.get("refresh")))},
    ]


def _overview_draw(bands: list[dict]) -> Callable[[str, int, str], tuple[str, float]]:
    def draw(variant: str, width: int, ident: str) -> tuple[str, float]:
        r = RAMP[variant]
        pad, index_w = r["pad"], 40 if variant == "n" else 56
        left, right = pad + index_w, width - pad
        inset = 12 if variant == "n" else 16
        top = pad + 20
        fills, seams, text, marks, arrows, used = [], [], [], [], [], set()
        y = top
        for band in reversed(bands):
            name, source = band["name"], band.get("source") or "record unavailable"
            inner_l, inner_r = left + inset, right - inset
            same_line = _width(name, r["head"], bold=True) + 24 + _width(source, r["sub"], mono=True) <= inner_r - inner_l
            text.append(_t(inner_l, y + 24, name, r["head"], bold=True))
            if same_line:
                text.append(_t(inner_r, y + 24, source, r["sub"], "mf-mono mf-muted", anchor="end"))
                content = y + 38
            else:
                for offset, line in enumerate(_wrap(source, r["sub"], inner_r - inner_l, mono=True)):
                    text.append(_t(inner_l, y + 40 + offset * 13, line, r["sub"], "mf-mono mf-muted"))
                content = y + 50 + 13 * (len(_wrap(source, r["sub"], inner_r - inner_l, mono=True)) - 1)
            if band.get("cells") is not None:
                cell, gap = (16, 5) if variant == "n" else (18, 6)
                grouped: dict[str, list[dict]] = {}
                for item in band["cells"]:
                    grouped.setdefault(item["group"], []).append(item)
                x, top_y, bottom = inner_l, content, content
                for group, members in grouped.items():
                    span = len(members) * (cell + gap) - gap
                    if x > inner_l and x + span > inner_r:
                        x, top_y = inner_l, bottom + 10
                    text.append(_t(x, top_y + 9, f"{group} {len(members)}", r["brow"], brow=True))
                    cx, cy = x, top_y + 16
                    for item in members:
                        if cx + cell > inner_r:
                            cx, cy = inner_l, cy + cell + gap
                        status = item["status"] if item["status"] in STATUS_LABEL else None
                        used.add(status)
                        marks.append(_rect(cx, cy, cell, cell, f"mf-cell-mini mf-s-{status or 'planned'}", rx=3,
                                           inner=f"<title>{_esc(item['title'] + ': ' + item['verdict'].replace('_', ' '))}</title>"))
                        cx += cell + gap
                    bottom = max(bottom, cy + cell)
                    x = cx - gap + 16 if cy == top_y + 16 else inner_r + 1
                if band["cells"]:
                    height = bottom + 4 - y
                else:
                    text.append(_t(inner_l, content + 14, "Component evidence matrix unavailable", r["item"], "mf-muted"))
                    height = content + 24 - y
            else:
                placed, flow_h = _flow(band["chips"], inner_l, inner_r, content, r)
                for previous, chip in zip([None] + placed, placed):
                    if chip.get("arrow_from_previous") and previous and previous["y"] == chip["y"]:
                        y_mid = chip["y"] + chip["h"] / 2
                        arrows.append(f'<line x1="{_num(previous["x"] + previous["w"])}" y1="{_num(y_mid)}" x2="{_num(chip["x"] - 2)}" y2="{_num(y_mid)}" class="mf-flow" marker-end="url(#{ident}-arrow)"/>')
                    used.add(chip.get("status"))
                    marks.append(_chip(chip, r))
                if not placed:
                    text.append(_t(inner_l, content + 14, "Record unavailable in this checkout", r["item"], "mf-muted"))
                height = (flow_h if placed else 24) + content - y + 2
            height = _grid(height + inset)
            cls = "mf-focus" if band.get("focus") else "mf-band"
            fills.append(_rect(left, y, right - left, height, cls, rx=0))
            text.append(_t(pad + index_w / 2 - 4, y + 24, band["index"], r["brow"] + 1, "mf-mono mf-muted", anchor="middle"))
            if band.get("focus"):
                used.add("focus")
            y += height
            seams.append(f'<line x1="{_num(left)}" y1="{_num(y)}" x2="{_num(right)}" y2="{_num(y)}" class="mf-seam"/>')
        frame = _rect(left, top, right - left, y - top, "mf-frame", rx=8)
        direction = (f'<line x1="{_num(pad + 4)}" y1="{_num(y - 8)}" x2="{_num(pad + 4)}" y2="{_num(top + 10)}" class="mf-flow" marker-end="url(#{ident}-arrow)"/>'
                     + _t(pad, top - 10, "Each layer builds on the one below", r["brow"], brow=True))
        keys = [key for key in ("built", "adopted", "candidate", "planned", "focus") if key in used]
        legend, legend_h = _legend(pad, y + 28, width - 2 * pad, keys, r)
        return "".join(fills + seams[:-1] + [frame, direction] + arrows + marks + text) + legend, y + 28 + legend_h + pad
    return draw


# ---------------------------------------------------------------- layers by area
def _humanize(group: str) -> str:
    words = group.replace("_", "-").split("-")
    return (words[0].capitalize() + (" and " + " ".join(words[1:]) if len(words) > 1 else "")) if words else group


def areas(matrix: dict) -> list[dict]:
    """Group matrix rows by their recorded catalog and, where recorded, catalog group."""
    result: dict[tuple, dict] = {}
    for row in matrix.get("rows", []):
        if row["catalog"] == "foundation":
            key, label = ("foundation",), "Foundation catalog"
        else:
            group = row.get("group")
            key = (row["catalog"], group or "")
            label = ("Trading: " + _humanize(group)) if group and row["catalog"] == "us-equities" else (row["catalog"] + (": " + _humanize(group) if group else ""))
        result.setdefault(key, {"label": label, "rows": []})["rows"].append(row)
    return list(result.values())


def _layers_draw(matrix: dict) -> Callable[[str, int, str], tuple[str, float]]:
    groups = areas(matrix)

    def draw(variant: str, width: int, ident: str) -> tuple[str, float]:
        r = RAMP[variant]
        pad, inset = r["pad"], 12 if variant == "n" else 16
        cols, gap = {"w": 5, "m": 3, "n": 2}[variant], 8 if variant == "n" else 12
        left, right = pad, width - pad
        cell_w = (right - left - 2 * inset - (cols - 1) * gap) / cols
        body, used, y = [], set(), pad
        for area in groups:
            rows = area["rows"]
            body.append(_t(left + inset, y + 24, area["label"], r["head"], bold=True))
            body.append(_t(right - inset, y + 24, f"{len(rows)} layer" + ("" if len(rows) == 1 else "s"), r["sub"], "mf-mono mf-muted", anchor="end"))
            content, cells = y + 38, []
            for start in range(0, len(rows), cols):
                chunk, layouts = rows[start:start + cols], []
                for row in chunk:
                    title = _wrap(row["title"], r["name"], cell_w - 34, bold=True)
                    names = ", ".join(winner["id"] for winner in row["winners"]) or "no recorded winner"
                    winners = _wrap(names, r["item"] - 0.5, cell_w - 24, lines=5)
                    layouts.append((row, title, winners))
                tallest = max(len(title) * r["line"] + len(winners) * (r["line"] - 2) for _, title, winners in layouts)
                cell_h = _grid(tallest + 42)
                for column, (row, title, winners) in enumerate(layouts):
                    x = left + inset + column * (cell_w + gap)
                    status = row["status"] if row["status"] in STATUS_LABEL else None
                    used.add(status)
                    cls = "mf-chip mf-s-candidate" if status == "candidate" else "mf-chip"
                    cells.append(_rect(x, content, cell_w, cell_h, cls, rx=6))
                    cells.append(_glyph(x + 13, content + 15, status))
                    line_y = content + 19
                    for line in title:
                        cells.append(_t(x + 24, line_y, line, r["name"], bold=True))
                        line_y += r["line"]
                    line_y += 2
                    for line in winners:
                        cells.append(_t(x + 12, line_y, line, r["item"] - 0.5, "mf-muted"))
                        line_y += r["line"] - 2
                    built = sum(1 for winner in row["winners"] if winner["status"] == "built")
                    footer = (f"{built} of {len(row['winners'])} host E2E" if row["winners"] else row["verdict_status"].replace("_", " "))
                    if built:
                        used.add("built")
                        cells.append(_glyph(x + 16, content + cell_h - 13, "built"))
                    cells.append(_t(x + (26 if built else 12), content + cell_h - 9, footer, r["sub"], "mf-mono mf-muted"))
                content += cell_h + gap
            height = _grid(content - gap + inset - y)
            body.insert(0, _rect(left, y, right - left, height, "mf-band", rx=8))
            body.extend(cells)
            y += height + 12
        keys = [key for key in ("built", "adopted", "candidate", "planned") if key in used]
        legend, legend_h = _legend(pad, y + 16, width - 2 * pad, keys, r)
        return "".join(body) + legend, y + 16 + legend_h + pad
    return draw


# ---------------------------------------------------------------- deployment
def deployment_groups(plan: dict, titles: dict[str, str]) -> list[dict]:
    """Install-plan services grouped by their recorded layer, largest group first."""
    groups: dict[str, list[dict]] = {}
    for row in plan.get("services", []):
        groups.setdefault(row["layer"], []).append(row)
    order = {layer: index for index, layer in enumerate(groups)}
    return [{"layer": layer, "title": titles.get(layer), "services": rows}
            for layer, rows in sorted(groups.items(), key=lambda item: (-len(item[1]), order[item[0]]))]


def _deployment_draw(plan: dict, handbook: dict | None, titles: dict[str, str]) -> Callable[[str, int, str], tuple[str, float]]:
    groups = deployment_groups(plan, titles)

    def node(x: float, y: float, w: float, group: dict, chip_cols: int, r: dict, used: set, title_lines: int = 1) -> tuple[str, float]:
        out = []
        tag = group["layer"]
        tag_w = _grid(_width(tag, r["brow"], mono=True) + 12)
        title = _wrap(group["title"] or tag, r["name"], w - 24, bold=True, lines=2)
        out.append(_rect(x + 12, y + 10, min(tag_w, w - 24), 14, "mf-tag", rx=2))
        out.append(_t(x + 18, y + 20.5, _wrap(tag, r["brow"], w - 36, mono=True, lines=1)[0], r["brow"], "mf-mono mf-muted"))
        for offset, line in enumerate(title):
            out.append(_t(x + 12, y + 44 + offset * r["line"], line, r["name"], bold=True))
        chip_w = (w - 24 - (chip_cols - 1) * 8) / chip_cols
        chip_h = 40 if r["name"] == 12 else 44
        top = y + 56 + (max(len(title), title_lines) - 1) * r["line"]
        for index, service in enumerate(group["services"]):
            cx = x + 12 + (index % chip_cols) * (chip_w + 8)
            cy = top + (index // chip_cols) * (chip_h + 8)
            focus = service["slot"] == "gpt-gateway"
            status = service["status"] if service["status"] in STATUS_LABEL else None
            used.add("focus" if focus else status)
            if focus:
                used.add(status)
            out.append(_rect(cx, cy, chip_w, chip_h, "mf-chip mf-focus" if focus else "mf-chip" + (f" mf-s-{status}" if status else ""), rx=4))
            out.append(_glyph(cx + 10, cy + 13, status))
            out.append(_t(cx + 20, cy + 17, _wrap(service["name"], r["name"], chip_w - 28, bold=True, lines=1)[0], r["name"], bold=True))
            detail = (service.get("release") or "release unreported") + "  " + (f":{service['port']}" if service["port"] else "no TCP port")
            out.append(_t(cx + 20, cy + 32 + (2 if chip_h > 40 else 0), _wrap(detail, r["sub"], chip_w - 28, mono=True, lines=1)[0], r["sub"], "mf-mono mf-muted"))
        rows = math.ceil(len(group["services"]) / chip_cols)
        height = top - y + rows * chip_h + (rows - 1) * 8 + 12
        return _rect(x, y, w, height, "mf-node", rx=6) + "".join(out), height

    def draw(variant: str, width: int, ident: str) -> tuple[str, float]:
        r = RAMP[variant]
        pad = r["pad"]
        nested = 12 if variant == "n" else 24
        used: set = set()
        win_l, win_r, top = pad, width - pad, pad + 4
        body = []
        y = top + 28
        platform_w = min(win_r - win_l - 2 * nested, 360)
        version = (handbook or {}).get("wsl_minimum")
        platform = [_rect(win_l + nested, y, platform_w, 52, "mf-node", rx=6),
                    _rect(win_l + nested + 12, y + 10, _grid(_brow_width("PLATFORM", r["brow"]) + 12), 14, "mf-tag", rx=2),
                    _t(win_l + nested + 18, y + 20.5, "platform", r["brow"], brow=True),
                    _t(win_l + nested + 12, y + 42, f"WSL {version} or later" if version else "WSL release target unreported", r["name"], bold=True)]
        if handbook and handbook.get("as_of"):
            platform.append(_t(win_l + nested + platform_w - 12, y + 42, f"handbook {handbook['as_of']}", r["sub"], "mf-mono mf-muted", anchor="end"))
        y += 52 + 24
        wsl_l, wsl_r, wsl_top = win_l + nested, win_r - nested, y
        y += 32
        inner_l, inner_r = wsl_l + nested, wsl_r - nested
        node_cols, chip_cols = {"w": 3, "m": 2, "n": 1}[variant], {"w": 4, "m": 2, "n": 1}[variant]
        nodes = []
        large = [group for group in groups if len(group["services"]) > 3]
        small = [group for group in groups if len(group["services"]) <= 3]
        for group in large:
            markup, height = node(inner_l, y, inner_r - inner_l, group, chip_cols, r, used)
            nodes.append(markup)
            y += height + 16
        node_w = (inner_r - inner_l - (node_cols - 1) * 16) / node_cols
        for start in range(0, len(small), node_cols):
            row = small[start:start + node_cols]
            lines = max(len(_wrap(group["title"] or group["layer"], r["name"], node_w - 24, bold=True, lines=2)) for group in row)
            heights = []
            for column, group in enumerate(row):
                markup, height = node(inner_l + column * (node_w + 16), y, node_w, group, 1, r, used, title_lines=lines)
                nodes.append(markup)
                heights.append(height)
            y += max(heights) + 16
        wsl_bottom = y + nested - 16
        base = plan.get("base") or "base unreported"
        wsl_label = f"WSL2 distribution: {base}"
        win_bottom = wsl_bottom + nested
        room = wsl_r - wsl_l - 40
        wsl_text = wsl_label if _brow_width(wsl_label, r["brow"]) <= room else _wrap(wsl_label, r["brow"] * 1.23, room, mono=True, lines=1)[0]
        zones = [_rect(win_l, top, win_r - win_l, win_bottom - top, "mf-zone", rx=8),
                 _rect(win_l + 12, top - 6, _grid(_brow_width("WINDOWS HOST", r["brow"]) + 16), 14, "mf-mask", rx=2),
                 _t(win_l + 20, top + 4.5, "Windows host", r["brow"], brow=True),
                 _rect(wsl_l, wsl_top, wsl_r - wsl_l, wsl_bottom - wsl_top, "mf-zone", rx=8),
                 _rect(wsl_l + 12, wsl_top - 6, _grid(_brow_width(wsl_text, r["brow"]) + 16), 14, "mf-mask", rx=2),
                 _t(wsl_l + 20, wsl_top + 4.5, wsl_text, r["brow"], brow=True)]
        keys = [key for key in ("adopted", "planned", "focus") if key in used]
        legend, legend_h = _legend(pad, win_bottom + 24, width - 2 * pad, keys, r)
        return "".join(zones + platform + nodes) + legend, win_bottom + 24 + legend_h + pad
    return draw


# ---------------------------------------------------------------- desk
def _desk_items(stage: dict, r: dict, width: float) -> list[tuple[dict, list[str]]]:
    return [(item, _wrap(item["name"], r["item"], width - 24, lines=3)) for item in stage["items"]]


def _desk_draw(desk: dict) -> Callable[[str, int, str], tuple[str, float]]:
    stages, cross = desk["stages"], desk["cross"]

    def item_block(x: float, y: float, item: dict, lines: list[str], r: dict, used: set) -> tuple[str, float]:
        status = item["status"] if item["status"] in STATUS_LABEL else None
        used.add(status)
        out = [_glyph(x + 5, y + 4, status)]
        for index, line in enumerate(lines):
            out.append(_t(x + 16, y + 8 + index * (r["line"] - 1), line, r["item"]))
        sub_y = y + 8 + len(lines) * (r["line"] - 1) + 1
        out.append(_t(x + 16, sub_y, item["kind"], r["sub"] - 0.5, "mf-mono mf-muted"))
        return "".join(out), sub_y - y + 10

    def cross_strip(x: float, y: float, w: float, layer: dict, r: dict, used: set) -> tuple[str, float]:
        out = [_t(x + 12, y + 20, layer["title"] + " (cross-cutting)", r["name"], bold=True)]
        cursor_x, cursor_y, row_h = x + 12, y + 32, 0
        for item in layer["items"]:
            name = "Layer verdict" if item["kind"].startswith("verdict") else item["name"]
            lines = _wrap(name, r["item"], 200, lines=1)
            span = 16 + max(_width(lines[0], r["item"]), _width(item["kind"], r["sub"] - 0.5, mono=True)) + 24
            if cursor_x + span > x + w - 12 and cursor_x > x + 12:
                cursor_x, cursor_y = x + 12, cursor_y + row_h + 6
            block, block_h = item_block(cursor_x, cursor_y, item, lines, r, used)
            out.append(block)
            row_h = max(row_h, block_h)
            cursor_x += span
        height = _grid(cursor_y + row_h + 8 - y)
        return _rect(x, y, w, height, "mf-band", rx=6) + "".join(out), height

    def draw(variant: str, width: int, ident: str) -> tuple[str, float]:
        r = RAMP[variant]
        pad, used, out = r["pad"], set(), []
        focus = desk.get("focus")
        if variant == "w":
            columns, gap = len(stages), 32
            column_w = (width - 2 * pad - (columns - 1) * gap) / columns
            label_lines = max(len(_wrap(stage["label"], r["name"], column_w, bold=True)) for stage in stages)
            node_top = pad + 30 + label_lines * r["line"] + 8
            blocks, heights = [], []
            for index, stage in enumerate(stages):
                x = pad + index * (column_w + gap)
                cy, chunk = node_top + 12, []
                for item, lines in _desk_items(stage, r, column_w - 12):
                    block, block_h = item_block(x + 10, cy, item, lines, r, used)
                    chunk.append(block)
                    cy += block_h + 6
                heights.append(cy - node_top + 4)
                blocks.append((x, stage, chunk))
            node_h = _grid(max(heights))
            for index, (x, stage, chunk) in enumerate(blocks):
                is_focus = stage["key"] == focus
                center = x + column_w / 2
                out.append(_rect(center - 16, pad, 32, 16, "mf-step mf-focus" if is_focus else "mf-step", rx=8))
                out.append(_t(center, pad + 12, f"{index + 1:02d}", r["sub"], "mf-mono" + (" mf-focus-text" if is_focus else ""), anchor="middle"))
                for offset, line in enumerate(_wrap(stage["label"], r["name"], column_w, bold=True)):
                    out.append(_t(center, pad + 34 + offset * r["line"], line, r["name"], "mf-focus-text" if is_focus else "", anchor="middle", bold=True))
                if index:
                    arrow_y = node_top + 24
                    style, marker = ("mf-flow-focus", ident + "-arrow-focus") if is_focus else ("mf-flow", ident + "-arrow")
                    out.insert(0, f'<line x1="{_num(x - gap)}" y1="{_num(arrow_y)}" x2="{_num(x - 2)}" y2="{_num(arrow_y)}" class="{style}" marker-end="url(#{marker})"/>')
                out.append(_rect(x, node_top, column_w, node_h, "mf-node mf-focus" if is_focus else "mf-node", rx=6))
                out.extend(chunk)
            y = node_top + node_h + 24
        else:
            index_w = 44 if variant == "m" else 0
            columns = 3 if variant == "m" else 1
            y = pad
            for index, stage in enumerate(stages):
                is_focus = stage["key"] == focus
                out.append(_rect(pad, y, 32, 16, "mf-step mf-focus" if is_focus else "mf-step", rx=8))
                out.append(_t(pad + 16, y + 12, f"{index + 1:02d}", r["sub"], "mf-mono" + (" mf-focus-text" if is_focus else ""), anchor="middle"))
                out.append(_t(pad + 44, y + 13, stage["label"], r["head"], "mf-focus-text" if is_focus else "", bold=True))
                box_l = pad + index_w
                box_w = width - pad - box_l
                cell_w = (box_w - 20 - (columns - 1) * 12) / columns
                top, chunk, row_h, cy = y + 28, [], 0, y + 40
                for position, (item, lines) in enumerate(_desk_items(stage, r, cell_w)):
                    if position and position % columns == 0:
                        cy, row_h = cy + row_h + 6, 0
                    block, block_h = item_block(box_l + 10 + (position % columns) * (cell_w + 12), cy, item, lines, r, used)
                    chunk.append(block)
                    row_h = max(row_h, block_h)
                box_h = _grid(cy + row_h + 8 - top)
                out.append(_rect(box_l, top, box_w, box_h, "mf-node mf-focus" if is_focus else "mf-node", rx=6))
                out.extend(chunk)
                y = top + box_h
                if index < len(stages) - 1:
                    next_focus = stages[index + 1]["key"] == focus
                    style, marker = ("mf-flow-focus", ident + "-arrow-focus") if next_focus else ("mf-flow", ident + "-arrow")
                    out.append(f'<line x1="{_num(pad + 16)}" y1="{_num(y + 4)}" x2="{_num(pad + 16)}" y2="{_num(y + 22)}" class="{style}" marker-end="url(#{marker})"/>')
                    y += 28
                else:
                    y += 24
        for layer in cross:
            strip, strip_h = cross_strip(pad, y, width - 2 * pad, layer, r, used)
            out.append(strip)
            y += strip_h + 12
        used.add("focus")
        keys = [key for key in ("built", "adopted", "candidate", "planned", "focus") if key in used]
        legend, legend_h = _legend(pad, y + 12, width - 2 * pad, keys, r, ident + "-arrow")
        return "".join(out) + legend, y + 12 + legend_h + pad
    return draw


# ---------------------------------------------------------------- layer-page figures
# Terminal states of the resolution protocol reuse the status glyph shapes, so a
# state reads by shape and label as well as color.
STATE_GLYPH = {"FINAL": "built", "SCHEDULED": "adopted", "non-terminal": "candidate", "RETIRED": "planned"}
STATE_LEGEND = {"FINAL": "Final", "SCHEDULED": "Scheduled", "non-terminal": "Not terminal", "RETIRED": "Retired"}


MARK_LEGEND = {"chip-winner": "Layer winner", "chip-other": "Not a layer winner", "unrecorded": "No repository record yet"}


def _state_legend(x: float, y: float, width: float, states: list[str], ramp: dict, *, focus: str | None, flow: str | None,
                  link: str | None = None, marks: list[str] | None = None) -> tuple[str, float]:
    size, out = ramp["sub"] + 1, [f'<line x1="{_num(x)}" y1="{_num(y)}" x2="{_num(x + width)}" y2="{_num(y)}" class="mf-seam"/>']
    out.append(_t(x, y + 20, "Legend", ramp["brow"], brow=True))
    start = x + _brow_width("LEGEND", ramp["brow"]) + 24
    cx, row = start, y + 20
    items = [(STATE_GLYPH[state], STATE_LEGEND[state]) for state in states if state in STATE_GLYPH]
    items += [("nolayer", "No layer in this catalog")] if "none" in states else []
    items += [(mark, MARK_LEGEND[mark]) for mark in marks or [] if mark in MARK_LEGEND]
    if focus:
        items.append(("focus", focus))
    if flow:
        items.append(("flow", flow))
    if link:
        items.append(("link", link))
    for key, label in items:
        span = 18 + _width(label, size) + 24
        if cx + span > x + width and cx > start:
            cx, row = start, row + 20
        if key in ("flow", "link"):
            out.append(f'<line x1="{_num(cx - 2)}" y1="{_num(row - 4)}" x2="{_num(cx + 12)}" y2="{_num(row - 4)}" class="{"mf-flow" if key == "flow" else "mf-flow-link"}"/>')
        elif key == "nolayer":
            out.append(_rect(cx + 1, row - 8, 8, 8, "mf-g-none", rx=2))
        elif key in ("chip-winner", "chip-other"):
            out.append(_rect(cx - 2, row - 10, 14, 10, "mf-art" if key == "chip-winner" else "mf-art mf-art--other", rx=2))
        elif key == "unrecorded":
            out.append(_rect(cx - 2, row - 10, 14, 10, "mf-node mf-unrecorded", rx=2))
        else:
            out.append(_glyph(cx + 5, row - 4, key))
        out.append(_t(cx + 18, row, label, size, "mf-muted"))
        cx += span
    return "".join(out), row - y + 12


def _blocked(segment: tuple[float, float, float, float], boxes: list[tuple[float, float, float, float]]) -> bool:
    """True when an axis-aligned segment passes through any box other than its endpoints (§6 rule 5)."""
    x1, y1, x2, y2 = segment
    left, right, top, bottom = min(x1, x2), max(x1, x2), min(y1, y2), max(y1, y2)
    return any(left < bx + bw and right > bx and top < by + bh and bottom > by for bx, by, bw, bh in boxes)


def _label(x: float, y: float, text: str, ramp: dict, *, anchor: str = "middle") -> str:
    """Arrow label on an opaque mask; the caller keeps a 6-10px gap from the stroke."""
    size = ramp["brow"]
    width = _grid(_brow_width(text, size) + 8)
    left = x - width / 2 if anchor == "middle" else x - 4
    return _rect(left, y - size - 1, width, size + 5, "mf-mask", rx=2) + _t(x if anchor == "middle" else x, y, text, size, anchor=anchor, brow=True)


TOPOLOGY_LAYOUT = {
    "w": {"cols": 3, "rows": (("lanes", "gateway", None), ("workers", "scheduling", "mcp"), ("telemetry", "backup", None)), "side": 248},
    "m": {"cols": 2, "rows": (("lanes", "gateway"), ("workers", "scheduling"), ("mcp", "telemetry"), ("backup", None)), "side": 0},
    "n": {"cols": 1, "rows": (("lanes",), ("gateway",), ("workers",), ("scheduling",), ("mcp",), ("telemetry",), ("backup",)), "side": 0},
}


def _topology_draw(topology: dict) -> Callable[[str, int, str], tuple[str, float]]:
    nodes = {node["id"]: node for node in topology.get("nodes", [])}
    zones = {zone["id"]: zone["label"] for zone in topology.get("zones", [])}
    focal_edge = tuple(topology.get("focal_edge") or ())
    catalog = topology.get("catalog") or "catalog"

    def node_height(node: dict) -> int:
        return _grid(72 + len(node.get("chips") or []) * 30 + 6)

    def draw_node(node: dict, x: float, y: float, w: float, r: dict, used: set) -> str:
        state = node.get("state")
        used.add(state or "none")
        cls = "mf-node mf-focus" if node.get("focal") else "mf-node"
        out = [_rect(x, y, w, node_height(node), cls, rx=6)]
        tag = node["layers"][0] + (f" +{len(node['layers']) - 1}" if len(node["layers"]) > 1 else "") if node.get("layers") else f"no {catalog} layer"
        tag_w = min(_grid(_width(tag, r["brow"] + 0.5, mono=True) + 12), w - 40)
        out.append(_rect(x + 12, y + 10, tag_w, 15, "mf-tag", rx=2))
        out.append(_t(x + 18, y + 21, _wrap(tag, r["brow"] + 0.5, tag_w - 10, mono=True, lines=1)[0], r["brow"] + 0.5, "mf-mono mf-muted"))
        if state:
            out.append(_glyph(x + w - 16, y + 17, STATE_GLYPH.get(state)))
        else:
            out.append(_rect(x + w - 20, y + 13, 8, 8, "mf-g-none", rx=2))
        out.append(_t(x + 12, y + 44, _wrap(node["name"], r["name"] + 1, w - 24, bold=True, lines=1)[0], r["name"] + 1, bold=True))
        out.append(_t(x + 12, y + 59, _wrap(node.get("sub") or "", r["sub"], w - 24, mono=True, lines=1)[0], r["sub"], "mf-mono mf-muted"))
        cy = y + 70
        for chip in node.get("chips") or []:
            used.add("chip-winner" if chip.get("winner_here") else "chip-other")
            out.append(_rect(x + 12, cy, w - 24, 24, "mf-art" if chip.get("winner_here") else "mf-art mf-art--other", rx=4))
            pin = str(chip["pin"]) if chip.get("pin") else "no pin"
            pin_text = _wrap(pin, r["sub"], (w - 24) * 0.55, mono=True, lines=1)[0]
            room = w - 24 - 16 - _width(pin_text, r["sub"], mono=True) - 8
            out.append(_t(x + 20, cy + 16, _wrap(chip["name"], r["item"], room, lines=1)[0], r["item"]))
            out.append(_t(x + w - 20, cy + 16, pin_text, r["sub"], "mf-mono mf-muted", anchor="end"))
            cy += 30
        return "".join(out)

    def draw(variant: str, width: int, ident: str) -> tuple[str, float]:
        r, layout = RAMP[variant], TOPOLOGY_LAYOUT[variant]
        pad, inset, gap_x, gap_y = r["pad"], (12 if variant == "n" else 24), (0 if variant == "n" else 96), 40
        side = layout["side"]
        host_l, host_r = pad, width - pad - (side + 24 if side else 0)
        top = pad + 8
        inner_l, inner_r = host_l + inset, host_r - inset
        col_w = (inner_r - inner_l - (layout["cols"] - 1) * gap_x) / layout["cols"]
        boxes, used, body, arrows, labels = {}, set(), [], [], []
        y = top + 28
        for row in layout["rows"]:
            height = max((node_height(nodes[ident_]) for ident_ in row if ident_ in nodes), default=0)
            for column, ident_ in enumerate(row):
                if ident_ in nodes:
                    boxes[ident_] = (inner_l + column * (col_w + gap_x), y, col_w, node_height(nodes[ident_]))
            y += height + gap_y
        host_bottom = y - gap_y + inset
        zone_rects = [("host", host_l, top, host_r - host_l, host_bottom - top)]
        if side:
            side_l = host_r + 24
            first = boxes.get("lanes", (0, top + 28, 0, 0))[1]
            provider_h = node_height(nodes["providers"]) if "providers" in nodes else 0
            boxes["providers"] = (side_l + 16, first, side - 32, provider_h)
            zone_rects.append(("remote", side_l, top, side, first + provider_h + 20 - top))
            github_top = first + provider_h + 56
            if "github" in nodes:
                boxes["github"] = (side_l + 16, github_top + 28, side - 32, node_height(nodes["github"]))
                zone_rects.append(("github", side_l, github_top, side, node_height(nodes["github"]) + 48))
            bottom = max(host_bottom, github_top + node_height(nodes.get("github", {"chips": []})) + 48)
        else:
            cursor = host_bottom + 32
            for zone, node_id in (("remote", "providers"), ("github", "github")):
                if node_id in nodes:
                    boxes[node_id] = (host_l + inset, cursor + 28, min(col_w, host_r - host_l - 2 * inset), node_height(nodes[node_id]))
                    zone_rects.append((zone, host_l, cursor, host_r - host_l, node_height(nodes[node_id]) + 48))
                    cursor += node_height(nodes[node_id]) + 48 + 32
            bottom = cursor - 32
        for zone, zx, zy, zw, zh in zone_rects:
            label = zones.get(zone, zone)
            body.append(_rect(zx, zy, zw, zh, "mf-zone", rx=8))
            body.append(_rect(zx + 12, zy - 6, _grid(_brow_width(label, r["brow"]) + 16), 14, "mf-mask", rx=2))
            body.append(_t(zx + 20, zy + 4.5, label, r["brow"], brow=True))
        drawn = []
        for edge in topology.get("edges", []):
            a, b = boxes.get(edge["from"]), boxes.get(edge["to"])
            if not a or not b:
                continue
            others = [box for key, box in boxes.items() if key not in (edge["from"], edge["to"])]
            focal = (edge["from"], edge["to"]) == focal_edge
            cross = next((zone for zone, node in (("remote", "providers"), ("github", "github")) if node in (edge["from"], edge["to"])), None)
            style, marker = ("mf-flow-focus", ident + "-arrow-focus") if focal else (("mf-flow-link", ident + "-arrow-link") if cross else ("mf-flow", ident + "-arrow"))
            if abs(a[1] - b[1]) < 1 and (a[0] + a[2] <= b[0] or b[0] + b[2] <= a[0]):
                line_y = a[1] + 32
                x1, x2 = (a[0] + a[2], b[0]) if a[0] < b[0] else (a[0], b[0] + b[2])
                segment = (x1, line_y, x2 - (2 if x2 > x1 else -2), line_y)
                if _blocked(segment, others):
                    continue
                arrows.append(f'<line x1="{_num(segment[0])}" y1="{_num(line_y)}" x2="{_num(segment[2])}" y2="{_num(line_y)}" class="{style}" marker-end="url(#{marker})"/>')
                if edge.get("label") and abs(x2 - x1) >= _brow_width(edge["label"], r["brow"]) + 20:
                    labels.append(_label((x1 + x2) / 2, line_y - 10, edge["label"], r))
                drawn.append(edge)
            elif abs(a[0] - b[0]) < 1 and (a[1] + a[3] <= b[1] or b[1] + b[3] <= a[1]):
                line_x = a[0] + 32
                y1, y2 = (a[1] + a[3], b[1]) if a[1] < b[1] else (a[1], b[1] + b[3])
                segment = (line_x, y1, line_x, y2 - (2 if y2 > y1 else -2))
                if _blocked(segment, others):
                    continue
                arrows.append(f'<line x1="{_num(line_x)}" y1="{_num(segment[1])}" x2="{_num(line_x)}" y2="{_num(segment[3])}" class="{style}" marker-end="url(#{marker})"/>')
                if edge.get("label") and abs(y2 - y1) >= 20:
                    labels.append(_label(line_x + 10, (y1 + y2) / 2 + 4, edge["label"], r, anchor="start"))
                drawn.append(edge)
        node_marks = [draw_node(nodes[key], *box[:3], r, used) for key, box in boxes.items() if key in nodes]
        states = [state for state in ("FINAL", "SCHEDULED", "RETIRED", "non-terminal") if state in used] + (["none"] if "none" in used else [])
        legend, legend_h = _state_legend(pad, bottom + 28, width - 2 * pad, states, r, focus="Focal: the model gateway", flow="Call or trigger",
                                         link="Crosses a zone" if any(edge["to"] in ("providers", "github") for edge in drawn if (edge["from"], edge["to"]) != focal_edge) else None,
                                         marks=[mark for mark in ("chip-winner", "chip-other") if mark in used])
        draw.drawn[variant] = [(edge["from"], edge["to"]) for edge in drawn]
        return "".join(body + arrows + node_marks + labels) + legend, bottom + 28 + legend_h + pad
    draw.drawn = {}
    return draw


def _flow_draw(flow: dict) -> Callable[[str, int, str], tuple[str, float]]:
    lanes = flow.get("lanes", [])
    steps = flow.get("steps", [])
    nodes = flow.get("nodes", [])
    focal_step, focal_edge = flow.get("focal_step"), tuple(flow.get("focal_edge") or ())

    def node_mark(node: dict, x: float, y: float, w: float, h: float, r: dict, used: set, *, size: float | None = None, wrap: int = 1) -> str:
        state = node.get("state")
        used.add(state or "none")
        size = size or r["name"]
        # A node no repository file records yet keeps its place in the flow, drawn dashed.
        unrecorded = not node.get("recorded", True)
        if unrecorded:
            used.add("unrecorded")
        out = [_rect(x, y, w, h, ("mf-node mf-focus" if node.get("focal") else "mf-node") + (" mf-unrecorded" if unrecorded else ""), rx=6)]
        if state:
            out.append(_glyph(x + 11, y + 14, STATE_GLYPH.get(state)))
        else:
            out.append(_rect(x + 7, y + 10, 8, 8, "mf-g-none", rx=2))
        line_y = y + 18
        for line in _wrap(node["name"], size, w - 24, bold=True, lines=2):
            out.append(_t(x + 22, line_y, line, size, bold=True))
            line_y += size + 3
        sub_size = r["sub"] - (0.5 if wrap > 1 else 0)
        for text, lines in ((node.get("sub"), wrap), (node.get("tool"), 1)):
            if text:
                for line in _wrap(text, sub_size, w - 28, mono=True, lines=lines):
                    out.append(_t(x + 22, line_y + 2, line, sub_size, "mf-mono mf-muted"))
                    line_y += sub_size + 4
        return "".join(out)

    def draw(variant: str, width: int, ident: str) -> tuple[str, float]:
        r = RAMP[variant]
        pad, used, bg, out, arrows, labels = r["pad"], set(), [], [], [], []
        if variant == "n":
            y = pad
            node_w, node_h = width - 2 * pad - 24, 58
            lane_names = dict((lane["id"], lane["label"]) for lane in lanes)
            for index, label in enumerate(steps):
                focus = index == focal_step
                out.append(_rect(pad, y, 32, 16, "mf-step mf-focus" if focus else "mf-step", rx=8))
                out.append(_t(pad + 16, y + 12, f"{index + 1:02d}", r["sub"], "mf-mono" + (" mf-focus-text" if focus else ""), anchor="middle"))
                out.append(_t(pad + 44, y + 13, label, r["head"], "mf-focus-text" if focus else "", bold=True))
                y += 28
                for node in [node for node in nodes if node["step"] == index]:
                    shown = {**node, "tool": lane_names.get(node["lane"], node["lane"]) + " lane"}
                    out.append(node_mark(shown, pad + 24, y, node_w, node_h, r, used))
                    y += node_h + 8
                if index < len(steps) - 1:
                    arrows.append(f'<line x1="{_num(pad + 16)}" y1="{_num(y)}" x2="{_num(pad + 16)}" y2="{_num(y + 16)}" class="mf-flow" marker-end="url(#{ident}-arrow)"/>')
                    y += 24
            bottom = y
            draw.drawn[variant] = []
        else:
            label_w, header = (128, 48) if variant == "w" else (72, 48)
            slot = (width - pad - label_w - 16) / len(steps)
            node_w = _grid(slot - 64) if variant == "w" else slot - 16
            lane_h, node_h = (100, 72) if variant == "w" else (112, 96)
            left = pad + label_w
            centers = [left + index * slot + slot / 2 for index in range(len(steps))]
            boxes = {node["id"]: (centers[node["step"]] - node_w / 2, pad + header + [lane["id"] for lane in lanes].index(node["lane"]) * lane_h + (lane_h - node_h) / 2, node_w, node_h) for node in nodes}
            for index, label in enumerate(steps):
                focus = index == focal_step
                bg.append(_rect(centers[index] - 16, pad, 32, 16, "mf-step mf-focus" if focus else "mf-step", rx=8))
                bg.append(_t(centers[index], pad + 12, f"{index + 1:02d}", r["sub"], "mf-mono" + (" mf-focus-text" if focus else ""), anchor="middle"))
                bg.append(_t(centers[index], pad + 34, label, r["name"], "mf-focus-text" if focus else "", anchor="middle", bold=True))
            for position, lane in enumerate(lanes):
                lane_top = pad + header + position * lane_h
                if position % 2 == 0:
                    bg.append(_rect(pad, lane_top, width - 2 * pad, lane_h, "mf-band", rx=0))
                bg.append(f'<line x1="{_num(pad)}" y1="{_num(lane_top)}" x2="{_num(width - pad)}" y2="{_num(lane_top)}" class="mf-seam"/>')
                for offset, line in enumerate(_wrap(lane["label"], r["brow"], label_w - 16, mono=True, lines=2)):
                    bg.append(_t(pad + 8, lane_top + lane_h / 2 + offset * 12, line, r["brow"], brow=True))
            bottom = pad + header + len(lanes) * lane_h
            drawn = []
            for edge in flow.get("edges", []):
                a, b = boxes.get(edge["from"]), boxes.get(edge["to"])
                if not a or not b:
                    continue
                others = [box for key, box in boxes.items() if key not in (edge["from"], edge["to"])]
                focal = (edge["from"], edge["to"]) == focal_edge
                style, marker = ("mf-flow-focus", ident + "-arrow-focus") if focal else ("mf-flow", ident + "-arrow")
                if abs(a[1] - b[1]) < 1:
                    line_y = a[1] + a[3] / 2
                    segment = (a[0] + a[2], line_y, b[0] - 2, line_y)
                    if _blocked(segment, others):
                        continue
                    arrows.append(f'<line x1="{_num(segment[0])}" y1="{_num(line_y)}" x2="{_num(segment[2])}" y2="{_num(line_y)}" class="{style}" marker-end="url(#{marker})"/>')
                    if edge.get("label") and b[0] - (a[0] + a[2]) >= _brow_width(edge["label"], r["brow"]) + 12:
                        labels.append(_label((a[0] + a[2] + b[0]) / 2, line_y - 10, edge["label"], r))
                    drawn.append(edge)
                else:
                    # Single bend: exit right, run to the target's centre line, then turn toward it.
                    corner_x, start_y = b[0] + b[2] / 2, a[1] + a[3] / 2
                    end_y = b[1] + b[3] if b[1] < a[1] else b[1]
                    rise = -1 if end_y < start_y else 1
                    first = (a[0] + a[2], start_y, corner_x, start_y)
                    second = (corner_x, start_y, corner_x, end_y)
                    if _blocked(first, others) or _blocked(second, others) or corner_x - 8 <= a[0] + a[2]:
                        continue
                    path = (f"M{_num(first[0])},{_num(start_y)} L{_num(corner_x - 8)},{_num(start_y)} "
                            f"Q{_num(corner_x)},{_num(start_y)} {_num(corner_x)},{_num(start_y + 8 * rise)} L{_num(corner_x)},{_num(end_y - 2 * rise)}")
                    arrows.append(f'<path d="{path}" class="{style}" marker-end="url(#{marker})"/>')
                    drawn.append(edge)
            out.extend(node_mark(node, *boxes[node["id"]], r, used, size=r["name"] if variant == "w" else r["name"] - 1, wrap=1 if variant == "w" else 2) for node in nodes)
            draw.drawn[variant] = [(edge["from"], edge["to"]) for edge in drawn]
        states = [state for state in ("FINAL", "SCHEDULED", "RETIRED", "non-terminal") if state in used] + (["none"] if "none" in used else [])
        legend, legend_h = _state_legend(pad, bottom + 24, width - 2 * pad, states, r, focus="Focal: the K1 ranking step", flow="Data moves",
                                         marks=["unrecorded"] if "unrecorded" in used else [])
        return "".join(bg) + "".join(arrows) + "".join(out) + "".join(labels) + legend, bottom + 24 + legend_h + pad
    draw.drawn = {}
    return draw


def _defs_link(ident: str) -> str:
    return f'<marker id="{ident}-arrow-link" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><path d="M0,0 L8,3 L0,6 Z" class="mf-arrowhead-link"/></marker>'


def layer_figure(manifest: dict) -> tuple[str, dict]:
    """The page's system figure (topology or data flow) and the connectors each variant could draw."""
    if manifest.get("topology"):
        topology = manifest["topology"]
        draw = _topology_draw(topology)
        nodes = topology["nodes"]
        chips = [chip for node in nodes for chip in node.get("chips") or []]
        desc = (f"{len(nodes)} parts of the foundation stack in {len(topology['zones'])} zones: the lanes on the WSL host call OmniRoute, "
                "which reaches the provider slots; runtime workers, scheduling, MCP and memory, telemetry and backup run beside them, and GitHub hosts the automation.")
        caption = ("Deployment, faithful detail. Each node names its foundation layer and shows that layer's computed state; each chip shows the run pin "
                   "catalogs/landscape/final-stack.json records for it.")
        if any(chip.get("winner_here") for chip in chips) and any(not chip.get("winner_here") for chip in chips):
            caption += " A solid chip is a winner of a foundation layer; a dashed chip is an alternate, a candidate or not in the catalogs."
        if any(not node.get("layers") for node in nodes):
            caption += " A hollow square marks a node with no foundation layer."
        caption += " Connectors are drawn only where they stay orthogonal and clear of other nodes; the text view lists every connection."
        html = _figure("topology", "Foundation topology", desc, draw, caption)
    else:
        flow = manifest["flow"]
        draw = _flow_draw(flow)
        nodes = flow["nodes"]
        desc = ("Feeds enter the owned collector, which writes the L0 raw log that K1 ranking reads; the ranking drives lanes A and B to the Alpaca "
                "paper broker, account C trades through its MCP trader and calc, the IBKR lane runs to IBKR, and history runs through the strategy "
                "templates in the BacktestNode.")
        caption = "Data flow: lanes are the paths data takes and steps run left to right. Each node shows the computed state of the trading layer it belongs to."
        if any(not node.get("recorded", True) for node in nodes):
            caption += " Dashed nodes have no repository record at this commit; the decisions below cite their record by name."
        if any(not node.get("layers") for node in nodes):
            caption += " A hollow square marks a node with no trading layer."
        caption += " The narrow view lists steps in order; the text view lists every connection."
        html = _figure("flow", "North-star data flow", desc, draw, caption)
    # Link-coloured cross-zone arrows need their own marker; add it to every variant's defs.
    html = re.sub(r'<defs>(<marker id="(mf-[a-z]+-[wmn])-arrow")', lambda match: "<defs>" + _defs_link(match.group(2)) + match.group(1), html)
    return html, dict(draw.drawn)


# ---------------------------------------------------------------- HTML
def _table(caption: str, headers: list[str], rows: list[list[str]]) -> str:
    head = "".join(f'<th scope="col">{_esc(header)}</th>' for header in headers)
    body = "".join("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows)
    return f'<div class="table-wrap" tabindex="0" role="region" aria-label="{_esc(caption)}"><table><caption>{_esc(caption)}</caption><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def _alt(summary: str, content: str) -> str:
    return f'<details class="mf-alt"><summary>{_esc(summary)}</summary>{content}</details>'


def _glyph_html(status: str) -> str:
    return f'<svg class="mf-glyph" viewBox="0 0 14 14" aria-hidden="true" focusable="false">{_glyph(7, 7, status)}</svg>'


def _status_text(status: str | None) -> str:
    return _esc(STATUS_LABEL.get(status or "", "Not marked"))


def _unreported(views: dict, name: str, label: str, unreported: dict) -> str:
    reason = unreported.get(name) or "no projection was produced"
    return f'<p class="mf-unreported">{_esc(label)} is not drawn: {_esc(reason)}. The view returns when the record is restored at main.</p>'


def render(manifest: dict | None) -> str:
    """Return the manifest sections, or an empty string when no projection exists."""
    if not isinstance(manifest, dict) or not isinstance(manifest.get("views"), dict):
        return ""
    views, unreported = manifest["views"], manifest.get("unreported") or {}
    matrix, plan, handbook, gates, runtime = (views.get(name) for name in ("matrix", "plan", "handbook", "gates", "runtime"))
    desk = views.get("desk") or {"stages": [], "cross": []}
    titles = dict((handbook or {}).get("layer_titles") or {})
    titles.update({row["layer_id"]: row["title"] for row in (matrix or {}).get("rows", []) if row["catalog"] == "foundation"})
    records = [(label, path, day) for label, path, day in (
        ("Layer verdicts", "component evidence matrix", (matrix or {}).get("checked_at")),
        ("Host services", "new-WSL install plan, revised", (plan or {}).get("revised")),
        ("WSL target", "new-WSL handbook, as of", (handbook or {}).get("as_of")),
        ("Desk gates", "us-equities gate ladder, checked", (gates or {}).get("checked_at")),
        ("Desk runtime", "us-equities runtime target, reviewed", (runtime or {}).get("reviewed_at")),
        ("Landing rules", ".github/main-ruleset.json", "current" if views.get("ruleset") else None),
        ("Orchestration", "command-center view, updated", (views.get("orchestration") or {}).get("cc_updated")),
    )]
    record_list = "".join(f"<div><dt>{_esc(label)}</dt><dd>{_esc(path)} {_esc(day) if day else '(not reported)'}</dd></div>" for label, path, day in records)
    key = "".join(f"<div><dt>{_glyph_html(status)}{_esc(STATUS_LABEL[status])}</dt><dd>{_esc(STATUS_RULE[status])}</dd></div>" for status in STATUS_LABEL)
    key += f"<div><dt>{_glyph_html('focus')}Focus</dt><dd>One violet element per view marks what that view turns on: the trading desk, the gateway, the paper-execution step.</dd></div>"
    nav = '<nav class="mf-jump" aria-label="Manifest views"><ul>' + "".join(f'<li><a href="#{anchor}">{_esc(label)}</a></li>' for anchor, label in (
        ("mf-stack", "The stack"), ("mf-layers", "Foundation layers"), ("mf-host", "Host deployment"), ("mf-desk", "North-star desk"), ("architecture-ledger", "Layer ledger"), ("architecture-custody", "Sources and custody"))) + "</ul></nav>"
    html = ['<section class="mf" id="architecture-manifest" aria-label="Architecture manifest">',
            '<p class="mf-summary">One workstation, read from the bottom up: the host, the agents on it, the recorded layer verdicts, the GitHub gates, the trading desk they serve and the views that watch them. Every mark comes from a named record; the custody table at the end lists each input with its SHA-256.</p>', nav]
    bands = overview_bands(views)
    stack_desc = "Six layers from the Windows host and WSL distribution up through agents, the recorded foundation layers, GitHub gates and the trading desk to the monitoring views, each listing its recorded components."
    stack_caption = "Layer stack, bottom to top. Each band names its record and date on the right; hover a foundation cell for its layer and verdict."
    stack_text = "<ol>" + "".join(f"<li><strong>{_esc(band['index'] + ' ' + band['name'])}</strong>: " + (_esc("; ".join(f"{chip['name']} ({chip['sub']})" if chip.get("sub") else chip["name"] for chip in band.get("chips") or [])) if band.get("chips") is not None else _esc(f"{len(band.get('cells') or [])} layer verdicts")) + (f" <small>({_esc(band['source'])})</small>" if band.get("source") else "") + "</li>" for band in reversed(bands)) + "</ol>"
    html.append('<section class="mf-view mf-hero" id="mf-stack" aria-labelledby="mf-stack-title"><h2 id="mf-stack-title">The stack, bottom to top</h2>'
                + _figure("stack", "Architecture stack", stack_desc, _overview_draw(bands), stack_caption) + _alt("Read the stack as text", stack_text) + "</section>")
    html.append(f'<section class="mf-key" aria-labelledby="mf-key-title"><h2 id="mf-key-title">Reading the marks</h2><dl>{key}</dl></section>')
    if matrix and matrix.get("rows"):
        layer_rows = [[_esc(area["label"]), _esc(row["title"]) + f' <code>{_esc(row["layer_id"])}</code>',
                       "<br>".join(f'{_esc(winner["id"])} <code>{_esc(winner["pin"] or "pin unreported")}</code>' for winner in row["winners"]) or "None recorded",
                       _status_text(row["status"]) + " (" + _esc(row["verdict_status"].replace("_", " ")) + ")",
                       _esc((row.get("independent_review") or "unreported").replace("_", " ")),
                       _esc(", ".join(f'{winner["id"]}: {(winner["host_e2e"] or "unreported").replace("_", " ")}' for winner in row["winners"]) or "not applicable")]
                      for area in areas(matrix) for row in area["rows"]]
        verdicts = matrix.get("verdicts") or {}
        layers_desc = f"{len(matrix['rows'])} layer verdicts grouped by catalog area: " + ", ".join(f"{count} {name.replace('_', ' ')}" for name, count in verdicts.items()) + "."
        html.append('<section class="mf-view" id="mf-layers" aria-labelledby="mf-layers-title"><h2 id="mf-layers-title">Foundation layers by area</h2>'
                    f'<p>All {len(matrix["rows"])} layer verdicts from the component evidence matrix, grouped by the catalog and, for trading layers, the catalog group each layer records. Pending layers are dashed.</p>'
                    + _figure("layers", "Layer verdicts by area", layers_desc, _layers_draw(matrix),
                              f'Layer stack by area. Source: catalogs/landscape/component-evidence-matrix.json, checked {_esc(matrix.get("checked_at") or "date unreported")}; winners and host E2E state on linux-wsl2-x86_64 as the matrix records them.')
                    + _alt("Read the layers as a table", _table("Layer verdicts", ["Area", "Layer", "Winners and pins", "Status", "Independent review", "Host E2E (linux-wsl2-x86_64)"], layer_rows)) + "</section>")
    else:
        html.append('<section class="mf-view" id="mf-layers" aria-labelledby="mf-layers-title"><h2 id="mf-layers-title">Foundation layers by area</h2>' + _unreported(views, "matrix", "The layer stack", unreported) + "</section>")
    if plan and plan.get("services"):
        groups = deployment_groups(plan, titles)
        service_rows = [[_esc(group["title"] or "Cross-layer") + f' <code>{_esc(group["layer"])}</code>', _esc(service["name"]), f'<code>{_esc(service.get("release") or "unreported")}</code>',
                         f'<code>127.0.0.1:{service["port"]}</code>' if service["port"] else "No TCP port recorded", _status_text(service["status"])]
                        for group in groups for service in group["services"]]
        ports = sum(1 for service in plan["services"] if service["port"])
        host_desc = f"The Windows host runs a WSL2 distribution whose install plan places {len(plan['services'])} user services in {len(groups)} layers, {ports} of them on loopback ports."
        html.append('<section class="mf-view" id="mf-host" aria-labelledby="mf-host-title"><h2 id="mf-host-title">Host deployment</h2>'
                    "<p>Where the services run, by layer, with the loopback port each one is configured for. These are the install plan's own settings and flags, not a live reading; host receipts are listed further down.</p>"
                    + _figure("host", "Host deployment", host_desc, _deployment_draw(plan, handbook, titles),
                              f'Deployment. Sources: evidence/artifacts/new-wsl-install-plan-20261002/install-plan.json, revised {_esc(plan.get("revised") or "date unreported")}; docs/new-wsl-handbook.json for the WSL release target.')
                    + _alt("Read the services as a table", _table("Install-plan services", ["Layer", "Service", "Release", "Loopback port", "Plan status"], service_rows)) + "</section>")
    else:
        html.append('<section class="mf-view" id="mf-host" aria-labelledby="mf-host-title"><h2 id="mf-host-title">Host deployment</h2>' + _unreported(views, "plan", "The deployment view", unreported) + "</section>")
    if desk.get("stages") and any(stage["items"] for stage in desk["stages"]):
        desk_rows = [[f"{index + 1:02d} {_esc(stage['label'])}", _esc(item["name"]), _esc(item["kind"]), _status_text(item["status"]),
                      _esc(item.get("title") or (item.get("host_e2e") or "").replace("_", " ") or "")]
                     for index, stage in enumerate(desk["stages"]) for item in stage["items"]]
        desk_rows += [[_esc("Cross-cutting: " + layer["title"]), _esc(item["name"]), _esc(item["kind"]), _status_text(item["status"]), _esc(item.get("title") or "")] for layer in desk["cross"] for item in layer["items"]]
        established = (gates or {}).get("established")
        desk_desc = "Six steps from data sources through ingestion, research, strategy and risk to paper execution, each listing its selected components and the gates that mark it built or planned."
        html.append('<section class="mf-view" id="mf-desk" aria-labelledby="mf-desk-title"><h2 id="mf-desk-title">North-star desk</h2>'
                    f"<p>The trading desk as a data flow. Each step lists the layer winners the matrix records and the gate-ladder gates that decide whether it is built or still planned ({established if established is not None else 'unreported'} of {len((gates or {}).get('gates', []))} gates established). Live trading stays outside this view.</p>"
                    + _figure("desk", "North-star desk data flow", desk_desc, _desk_draw(desk),
                              f'Data flow. Sources: catalogs/us-equities/gates-20260922.json, checked {_esc((gates or {}).get("checked_at") or "date unreported")}; catalogs/us-equities/runtime-target.json for the adaptive policies; the component evidence matrix for winners. No record names a separate risk governor; the risk step shows the portfolio-risk layer and its leverage-ladder gates.')
                    + _alt("Read the desk as a table", _table("Desk steps", ["Step", "Item", "Kind", "Status", "Recorded detail"], desk_rows)) + "</section>")
    else:
        html.append('<section class="mf-view" id="mf-desk" aria-labelledby="mf-desk-title"><h2 id="mf-desk-title">North-star desk</h2>' + _unreported(views, "gates", "The desk data flow", unreported) + "</section>")
    html.append('<section class="mf-view" id="mf-records" aria-labelledby="mf-records-title"><h2 id="mf-records-title">Records behind these views</h2>'
                f'<dl class="mf-records">{record_list}</dl></section>')
    html.append("</section>")
    return "".join(html)
