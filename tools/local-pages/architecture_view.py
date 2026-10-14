"""Render only builder-projected landscape/inventory facts as local HTML.

Source contracts are read by architecture_sources and architecture_inventory.
Design provenance is recorded from the installed skill manifest, not copied.
"""
from __future__ import annotations

from html import escape
import hashlib
import importlib.util
import json
import math
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


_SANITIZER = None
_DIAGRAMS = None


def _sanitizer():
    """Reuse the maintained local-pages projection on values, never markup."""
    global _SANITIZER
    if _SANITIZER is None:
        spec = importlib.util.spec_from_file_location("architecture_text_projection", Path(__file__).with_name("sanitization.py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _SANITIZER = module
    return _SANITIZER


def _diagrams():
    """Manifest figures render from the builder's projection; no file is read here."""
    global _DIAGRAMS
    if _DIAGRAMS is None:
        spec = importlib.util.spec_from_file_location("architecture_manifest_figures", Path(__file__).with_name("architecture_diagrams.py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _DIAGRAMS = module
    return _DIAGRAMS


def _portable(item: Any) -> Any:
    # JSON object keys can contain source paths too. Project them before JSON
    # string escaping makes encoded source identities part of the payload.
    if isinstance(item, dict):
        return {_sanitizer().text(key): _portable(child) for key, child in item.items()}
    if isinstance(item, (list, tuple)):
        return [_portable(child) for child in item]
    return _sanitizer().sanitize(item)


def esc(value: Any) -> str:
    return escape(_sanitizer().text(value), quote=True)


def value(item: Any) -> str:
    if item is None or item == "" or item == [] or item == {}:
        return "UNREPORTED"
    return json.dumps(_portable(item), ensure_ascii=False, sort_keys=True) if isinstance(item, (dict, list)) else _sanitizer().text(item)


def repo_key(raw: Any) -> str | None:
    if not isinstance(raw, str):
        return None
    if raw.startswith("https://github.com/"):
        parts = urlsplit(raw).path.strip("/").split("/")
    elif re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", raw):
        parts = raw.split("/")
    else:
        return None
    if len(parts) < 2:
        return None
    return "/".join(parts[:2]).removesuffix(".git").casefold()


def _repositories(layer: dict) -> set[str]:
    found = set()
    for key in ("candidates", "winners", "alternatives", "rejected", "g5_candidates"):
        for item in layer.get(key, []) or []:
            if isinstance(item, dict):
                normalized = repo_key(item.get("repository") or item.get("repo"))
                if normalized:
                    found.add(normalized)
    return found


def join_inventory(model: dict, inventory: dict) -> tuple[dict[str, list[dict]], list[dict]]:
    """Retain canonical catalog joins and explicit reviewed mappings."""
    layers = model["layers"]
    mapping = {layer["key"]: [] for layer in layers}
    repositories = {layer["key"]: _repositories(layer) for layer in layers}
    unmapped = []
    for original in inventory.get("items", []):
        if original.get("status") == "UNAPPROVED":
            continue
        row = dict(original)
        explicit = row.get("layer_id")
        keys = row.get("layer_keys") or []
        if not isinstance(keys, list):
            keys = []
        matches = [layer["key"] for layer in layers if any(key in (layer["key"], layer["catalog"] + "/" + layer["layer_id"]) for key in keys)]
        if not matches and explicit:
            matches = [layer["key"] for layer in layers if explicit in (layer["key"], layer["layer_id"]) and row.get("catalog", layer["catalog"]) == layer["catalog"]]
        if not matches:
            repository = repo_key(row.get("repository"))
            if repository:
                matches = [key for key, values in repositories.items() if repository in values]
        if matches:
            row["mapping_basis"] = row.get("mapping_reason") or ("explicit layer ID" if explicit or keys else "exact repository identity")
            for key in matches:
                mapping[key].append(row)
        else:
            row["unmapped_reason"] = row.get("unmapped_reason") or "No canonical component/repository join or reviewed mapping matches this item"
            unmapped.append(row)
    return mapping, unmapped


def _table(caption: str, headers: list[str], rows: list[list[str]]) -> str:
    head = "".join(f'<th scope="col">{esc(header)}</th>' for header in headers)
    body = "".join('<tr><th scope="row">' + row[0] + '</th>' + "".join(f'<td>{cell}</td>' for cell in row[1:]) + '</tr>' for row in rows)
    return f'<div class="table-wrap architecture-table" tabindex="0" role="region" aria-label="{esc(caption)}"><table><caption>{esc(caption)}</caption><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def _source_refs(item: dict) -> str:
    return esc(value(item.get("source_refs") or item.get("evidence_refs") or item.get("primary_sources") or item.get("source_pointer")))


def _invoke_text(item: dict, model: dict | None) -> str:
    observed = item.get("invoke")
    if not isinstance(observed, dict) or observed.get("status") == "unmeasured":
        reason = observed.get("reason") if isinstance(observed, dict) else None
        return "unmeasured: " + str(reason or "No attached producer observation matches this component identity")
    descriptions = []
    for row in observed.get("roles") or []:
        if not isinstance(row, dict):
            continue
        owner = row.get("role") or "owning role unmeasured (producer attribution absent)"
        if owner == "native-agent-stack-1a":
            owner = "owner session (reports to CC)"
        client = row.get("client")
        label = f'{client} {owner}' if client else str(owner)
        if row.get("server"):
            label += f' ({row["server"]})'
        calls = row.get("calls")
        measured = isinstance(calls, int) and not isinstance(calls, bool) and calls >= 0
        hours = row.get("window_hours", observed.get("window_hours"))
        timed = isinstance(hours, (int, float)) and not isinstance(hours, bool) and math.isfinite(hours) and hours > 0
        unit = "sessions" if observed.get("measure") == "sessions" else "calls"
        text = f'{label}: {calls} recorded {unit}' if measured else f'{label}: unmeasured (published count absent)'
        text += f'; {calls / hours:.3f} {unit}/hour' if measured and timed else '; rate unmeasured (window duration absent)'
        for field, population in (("sessions", "session"), ("conversations", "conversation")):
            if field in row:
                count = row[field]
                count_text = str(count) if isinstance(count, int) and not isinstance(count, bool) and count >= 0 else "unmeasured (producer count absent or invalid)"
                text += f'; published {population} count: {count_text}'
        if row.get("aggregation_scope"):
            text += '; ' + str(row["aggregation_scope"])
        descriptions.append(text)
    return "; ".join(descriptions) if descriptions else "unmeasured: " + str(observed.get("reason") or "Producer supplied no owning-role observations")


def _e2e_text(item: dict) -> str:
    evidence = item.get("e2e") or item.get("upstream_e2e")
    if not isinstance(evidence, dict):
        return "no upstream E2E evidence: no registered receipt matches this component identity"
    recorded = evidence.get("path") and evidence.get("sha256") and (evidence.get("verified") or evidence.get("receipt_verified") or evidence.get("kind"))
    if not recorded:
        return "no upstream E2E evidence: " + str(evidence.get("reason") or "No digest-bound E2E receipt is registered for this component")
    scope = evidence.get("evidence_scope") or evidence.get("source_scope")
    label = {"native_host": "native E2E on this host", "vendor_test_suite": "vendor test-suite run", "local": "local host E2E receipt"}.get(scope, str(scope or "recorded E2E receipt"))
    if evidence.get("kind") in ("historical_inventory", "compatibility_attempt"):
        label = "not E2E; " + str(evidence["kind"])
    elif evidence.get("kind") == "artifact_measurement":
        label = "measurement receipt"
    elif evidence.get("kind") == "upstream_provenance":
        label = "source provenance receipt"
    details = [label, f'kind: {value(evidence.get("kind") or evidence.get("evidence_class"))}', f'UTC date: {value(evidence.get("date"))}', f'result: {value(evidence.get("result"))}', f'receipt: {evidence["path"]}#{evidence["sha256"]}', f'command: {value(evidence.get("command"))}']
    if evidence.get("command_count") is not None:
        details.append(f'commands: {evidence["command_count"]}; programs: {value(evidence.get("command_programs"))}')
    if evidence.get("date_original") and not evidence.get("date"):
        details.append(f'recorded date: {value(evidence["date_original"])}; timezone: {value(evidence.get("date_timezone"))}')
    for key in ("evidence_class", "selected_pin", "observed_pin", "reason"):
        if evidence.get(key):
            details.append(f'{key}: {value(evidence[key])}')
    return "; ".join(details)


def _candidate_table(items: list[Any], caption: str, model: dict | None = None) -> str:
    rows = []
    for item in items:
        if isinstance(item, str):
            rows.append([esc(item), "UNREPORTED", "UNREPORTED", "UNREPORTED", "UNREPORTED", "UNREPORTED", "unmeasured", "no upstream E2E evidence"])
            continue
        if not isinstance(item, dict):
            continue
        name = item.get("name") or item.get("id") or item.get("repository") or "UNREPORTED"
        repository = item.get("repository") or item.get("repo")
        pin = item.get("revision") or item.get("pin") or item.get("source_pin") or item.get("commit")
        reason = item.get("rationale") or item.get("reason") or item.get("disposition") or item.get("requirement_fit") or item.get("recorded_disposition") or item.get("decision_scope")
        quality = item.get("quality_evidence") or item.get("criteria") or item.get("source_findings")
        rows.append([esc(name), esc(value(repository)), esc(value(pin)), esc(value(reason)), _source_refs(item), esc(value(quality)), esc(_invoke_text(item, model)), esc(_e2e_text(item))])
    return _table(caption, ["Tool / repository", "Upstream", "Pin", "Recorded reason", "Evidence sources", "Upstream quality evidence", "Invoke rate per owning role", "Latest upstream E2E evidence"], rows) if rows else '<p>UNREPORTED in this source.</p>'


def _inventory_table(items: list[dict], caption: str, model: dict | None = None) -> str:
    rows = [[esc(item.get("name", "UNREPORTED")), esc(value(item.get("kind"))), esc(value(item.get("path"))), esc(value(item.get("repository"))), esc(value(item.get("pin"))), esc(value(item.get("sha256"))), esc(value(item.get("status"))), esc(value(item.get("mapping_basis") or item.get("unmapped_reason"))) + ("; source: " + esc(value(item["mapping_source"])) if item.get("mapping_source") else ""), esc(_invoke_text(item, model)), esc(_e2e_text(item))] for item in items]
    return _table(caption, ["Name", "Inventory", "Path", "Upstream", "Pin", "SHA-256", "Metadata state", "Layer binding", "Invoke rate per owning role", "Latest upstream E2E evidence"], rows) if rows else '<p>No source-bound inventory item is reported for this layer.</p>'


def _rates(candidate: dict, adoption: dict) -> list[dict]:
    # Exact native server names only; plugin aliases mirror adoption_view's producer.
    names = {value.casefold() for value in (candidate.get("name"), candidate.get("id"), candidate.get("component_id")) if isinstance(value, str)}
    repository = repo_key(candidate.get("repository") or candidate.get("repo"))
    if repository:
        names.add(repository.split("/")[1])
    canonical = {"plugin_context-mode_context-mode": "context-mode", "plugin_socraticode_socraticode": "socraticode"}
    rows = []
    hours = adoption.get("window_hours")
    for client, field, population in (("Claude", "claude_by_role", "sessions"), ("Codex", "codex_by_lane", "conversations")):
        for role, record in (adoption.get(field) or {}).items():
            if not isinstance(record, dict):
                continue
            matches = [entry.get("calls") for server, entry in (record.get("servers") or {}).items() if (server.casefold() in names or canonical.get(server) in names) and isinstance(entry, dict)]
            if matches:
                count = None if any(number is None for number in matches) else sum(matches)
                rate = count / hours if count is not None and isinstance(hours, (int, float)) and hours > 0 else None
                rows.append({"client": client, "role": "owner session (reports to CC)" if role == "native-agent-stack-1a" else role, "calls": count, "calls_per_hour": rate, "population": record.get(population)})
    return rows


def _tool_progress(items: list[Any], model: dict) -> str:
    program = model.get("adoption_program") or {}
    stages = program.get("global_stages") or []
    adoption = model.get("adoption_observation") or {}
    tool_rows = []
    seen = set()
    for candidate in items:
        if not isinstance(candidate, dict):
            continue
        identifier = (candidate.get("name") or candidate.get("id"), candidate.get("repository"))
        if identifier in seen:
            continue
        seen.add(identifier)
        stage_state = candidate.get("stages") or candidate.get("adoption_stage") or "UNREPORTED per tool; no completed stage inferred"
        tool_rows.append([esc(value(identifier[0])), esc(value(stage_state)), esc(_invoke_text(candidate, model)), esc(_e2e_text(candidate))])
    labels = '<ol class="architecture-stages">' + "".join(f'<li>{esc(stage)}</li>' for stage in stages) + '</ol>' if stages else '<p>Stage labels are UNREPORTED in the CC source.</p>'
    return labels + _table("Per-candidate stage and recorded role use", ["Candidate", "Recorded stage", "Invoke rate per owning role", "Latest upstream E2E evidence"], tool_rows) + f'<p class="source-note">Invoke snapshot {esc(value(adoption.get("generated_utc")))}; {esc(value(adoption.get("window_hours")))} hours. Observed calls are not evidence of completed clean install, fresh-session acceptance or a final selection.</p>'


def _closed(label: str, count: int, content: str) -> str:
    return f'<details><summary>{esc(label)} · {count} records</summary>{content}</details>'


def _layer_detail(row: dict, items: list[dict], model: dict) -> str:
    candidates, grand = row.get("candidates") or [], row.get("g5_candidates") or []
    content = '<p class="source-note">Detail for ' + esc(value(row.get("title"))) + ' · ' + esc(row["key"]) + '</p>'
    content += _closed("Recorded winners", len(row.get("winners") or []), _candidate_table(row.get("winners") or [], "Winners and retained pins", model))
    content += _closed("Full landscape candidates and reasons", len(candidates), _candidate_table(candidates, "Landscape candidates", model))
    for field, label in (("alternatives", "Alternatives"), ("rejected", "Rejected records")):
        content += _closed(label, len(row.get(field) or []), _candidate_table(row.get(field) or [], label, model))
    content += _closed("G5 upstream quality candidates", len(grand), '<p class="g5-boundary">' + esc(value((model.get("g5") or {}).get("candidate_label") or "candidate, PENDING G5")) + '</p>' + _candidate_table(grand, "Grand catalog candidate identities", model) + '<pre class="architecture-quality">' + esc(value(row.get("source_quality"))) + '</pre>')
    content += _closed("Inventory mapped by sources", len(items), _inventory_table(items, "Skills, agents, automation, SDKs, actions and pinned repositories", model))
    content += _closed("Adoption stages and use per role", len(grand or candidates), _tool_progress(grand or candidates, model))
    return content


def _deferred(key: str, label: str, content: str, outputs: dict[str, bytes] | None) -> str:
    if outputs is None:
        return content
    raw = content.encode("utf-8")
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", _sanitizer().text(key)).strip("-") or "detail"
    path = f'architecture/layers/{slug}-{hashlib.sha256(raw).hexdigest()[:16]}.html'
    outputs[path] = raw
    return f'<details class="architecture-detail" data-layer-src="{esc(path)}"><summary>{esc(label)}</summary><div class="architecture-detail-content" aria-live="polite"><p>Expand to load these component tables. <a href="{esc(path)}">Open the detail page</a>.</p></div></details>'


def _local_host_receipts(host: dict) -> str:
    items = host.get("items") or []
    rows = [[esc(value(item.get("title"))), "local host receipt (state root)", esc(value(item.get("path"))), esc(value(item.get("sha256"))), esc(value(item.get("bytes"))), esc(value(item.get("mtime_utc")))] for item in items]
    note = '<p>The sanitized index does not supply execution date, command or result. Receipt hashes are index-declared; mtime is file metadata. Referenced receipt bodies are not read, and this metadata does not establish native E2E or selected-pin acceptance.</p>'
    table = _table("State-root host receipt metadata", ["Receipt title", "Scope", "Index-provided path", "SHA-256 (index-declared)", "Bytes (index)", "mtime UTC (index)"], rows) if rows else '<p>' + esc(value((host.get("coverage") or {}).get("status") or "Sanitized local receipt index unavailable")) + '</p>'
    return _closed("Local host receipt metadata", len(items), note + table)


# ---------------------------------------------------------------- layer pages
_STATE_TEXT = {"FINAL": "Final", "SCHEDULED": "Scheduled", "RETIRED": "Retired", "non-terminal": "Not terminal"}


def _glyph_svg(state: str | None) -> str:
    key = _diagrams().STATE_GLYPH.get(state or "")
    inner = _diagrams()._glyph(7, 7, key) if key else '<rect x="3" y="3" width="8" height="8" rx="2" class="mf-g-none"/>'
    return f'<svg class="mf-glyph" viewBox="0 0 14 14" aria-hidden="true" focusable="false">{inner}</svg>'


def _mark(met: bool, label: str | None = None) -> str:
    glyph = '<rect x="3" y="3" width="8" height="8" rx="1" class="mf-g-built"/>' if met else '<circle cx="7" cy="7" r="3.6" class="mf-g-candidate"/>'
    return f'<span class="lp-mark lp-mark--{"met" if met else "missing"}"><svg class="mf-glyph" viewBox="0 0 14 14" aria-hidden="true" focusable="false">{glyph}</svg>{esc(label or ("Met" if met else "Missing"))}</span>'


def _anchor(key: str) -> str:
    return "layer-" + re.sub(r"[^a-z0-9-]+", "-", key.casefold()).strip("-")


def _refs(refs: list[str]) -> str:
    return "<ul class=\"lp-refs\">" + "".join(f"<li><code>{esc(ref)}</code></li>" for ref in refs) + "</ul>" if refs else "<p>No repository file is cited.</p>"


def _number(index: int) -> str:
    """The protocol numbers its FINAL conditions (1) to (4); the pages keep that numbering."""
    return f'<span class="lp-n">{index}</span>'


def _count_strip(manifest: dict) -> str:
    """One quiet strip: the finalized count as a sentence, the states in one row, then each condition as a meter (dataviz: meters, no chart)."""
    summary = manifest["summary"]
    total, states, finalized = summary["layers"], summary["states"], summary["finalized"]
    sentence = f"None of the {total} layers is finalized yet." if not finalized else f"{finalized} of {total} layers are finalized."
    commit = manifest.get("commit")
    source = manifest["sources"][0]["path"] if manifest.get("sources") else "catalogs/landscape/final-stack.json"
    provenance = (f'Read from <code>{esc(source)}</code> at commit <code title="{esc(commit)}">{esc(commit[:12])}</code>.' if commit
                  else f'Read from <code>{esc(source)}</code>; the commit is unrecorded.')
    row = "".join(f'<div class="lp-stat"><dt>{_glyph_svg(state)}{esc(_STATE_TEXT[state])}</dt><dd>{states[state]}</dd></div>'
                  for state in ("non-terminal", "FINAL", "SCHEDULED", "RETIRED"))
    meters = ""
    for index, condition in enumerate(manifest["definitions"]["conditions"], 1):
        count = summary["conditions_met"][condition["key"]]
        share = 0 if not total else round(100 * count / total, 1)
        meters += (f'<div class="lp-meter"><dt>{_number(index)}{esc(condition["label"])}</dt><dd><span class="lp-meter-value">{count} of {total}</span>'
                   f'<span class="lp-meter-track" role="img" aria-label="Condition {index}, {esc(condition["label"])}: {count} of {total} layers meet it">'
                   f'<span class="lp-meter-fill" style="width: {share}%"></span></span></dd></div>')
    return (f'<section class="lp-strip" aria-label="Where the layers stand"><p class="lp-verdict">{esc(sentence)}</p>'
            f'<dl class="lp-stats">{row}</dl><p class="lp-provenance">{provenance}</p>'
            f'<p class="lp-quiet">Layers where every winner meets each condition</p><dl class="lp-meters">{meters}</dl></section>')


def _condition_key(manifest: dict) -> str:
    """The four conditions in the protocol's words, visible beside the rail rather than behind a hover."""
    return ('<dl class="lp-key-list">' + "".join(f'<div><dt>{_number(index)}{esc(condition["label"])}</dt><dd>{esc(condition["rule"])}</dd></div>'
                                                  for index, condition in enumerate(manifest["definitions"]["conditions"], 1)) + "</dl>")


def _rail(manifest: dict) -> str:
    conditions = manifest["definitions"]["conditions"]
    head = '<th scope="col">Layer</th>' + "".join(f'<th scope="col" class="lp-rail-head">{_number(index)}{esc(c["label"])}</th>' for index, c in enumerate(conditions, 1)) + '<th scope="col">Computed state</th>'
    rows = []
    for layer in manifest["layers"]:
        cells = []
        for condition in conditions:
            met = layer["conditions"][condition["key"]]
            count = sum(1 for winner in layer["winners"] if winner["conditions"][condition["key"]]["met"])
            label = "Met" if met else (f"{count} of {len(layer['winners'])}" if layer["winners"] else "No winner")
            cells.append(f'<td class="lp-rail-cell lp-rail-cell--{"met" if met else "missing"}">{_mark(met, label)}</td>')
        rows.append(f'<tr><th scope="row"><a href="#{_anchor(layer["layer"])}">{esc(layer["title"])}</a></th>{"".join(cells)}'
                    f'<td class="lp-state-cell">{_glyph_svg(layer["state"])}{esc(_STATE_TEXT[layer["state"]])}</td></tr>')
    return (f'<div class="table-wrap lp-rail" tabindex="0" role="region" aria-label="Four FINAL conditions by layer"><table><caption>Four FINAL conditions by layer. '
            f'A condition is met for a layer only when every winner meets it.</caption><thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>')


def _condition_cell(key: str, entry: dict, pin: dict) -> str:
    """A winner's condition with only what is specific to that winner; layer-wide facts are stated once above the table."""
    met = entry["met"]
    if key == "verdict":
        detail = "" if met else entry["detail"]
    elif key == "run_pin":
        detail = (pin.get("run_source") or "") if met else entry["detail"]
    elif key == "invoke":
        detail = ""
    else:
        detail = entry["detail"]
    return _mark(met) + (f"<small>{esc(detail)}</small>" if detail else "")


def _winners_table(layer: dict, conditions: list[dict]) -> str:
    caption = "Winners of " + str(layer["title"])
    rows = []
    for winner in layer["winners"]:
        pin = winner["pin"]
        run = f'<code>{esc(pin["run"])}</code> <small>{esc(pin["run_id"])}</small>' if pin["run"] else f'none ({esc(pin["run_reason"] or "unresolved")})'
        cells = [f'<code>{esc(pin["verdict"])}</code>', run, esc(pin["pin_drift"] or "no run"), esc(winner["evidence_class"] or "unreported")]
        cells += [_condition_cell(c["key"], winner["conditions"][c["key"]], pin) for c in conditions]
        rows.append(f'<tr><th scope="row">{esc(winner["component"])}</th>' + "".join(f"<td>{cell}</td>" for cell in cells) + "</tr>")
    labels = ("Component", "Verdict pin", "Run pin", "Pin drift", "Evidence class")
    group_start = {1: ' class="lp-group-start"'}
    head = ('<tr><th scope="colgroup" colspan="5">Winner and pins</th><th scope="colgroup" colspan="4" class="lp-group-start">FINAL conditions</th></tr><tr>'
            + "".join(f'<th scope="col">{esc(label)}</th>' for label in labels)
            + "".join(f'<th scope="col"{group_start.get(index, "")}>{_number(index)}{esc(c["label"])}</th>' for index, c in enumerate(conditions, 1)) + "</tr>")
    columns = "".join(f'<col class="lp-col-{index}">' for index in range(1, len(labels) + len(conditions) + 1))
    return (f'<div class="table-wrap architecture-table" tabindex="0" role="region" aria-label="{esc(caption)}"><table><caption>{esc(caption)}</caption>'
            f'<colgroup>{columns}</colgroup><thead>{head}</thead><tbody>{"".join(rows)}</tbody></table></div>')


def _layer_article(layer: dict, manifest: dict) -> str:
    conditions = manifest["definitions"]["conditions"]
    verdict = layer["verdict"]
    winners = (_winners_table(layer, conditions) if layer["winners"]
               else '<p class="lp-empty">No recorded winner. ' + esc(f'Verdict {verdict["status"] or "absent"}; final_stack.py status {layer["final_stack_status"]}.') + '</p>')
    missing = ("<ul class=\"lp-missing\">" + "".join(f"<li>{esc(reason)}</li>" for reason in layer["missing"]) + "</ul>") if layer["missing"] else "<p>Nothing is missing.</p>"
    gaps = "<ol>" + "".join(f"<li>{esc(gap)}</li>" for gap in layer["open_gaps"]) + "</ol>" if layer["open_gaps"] else "<p>The catalog lists no open gap.</p>"
    facts = (f'<dl class="lp-facts"><div><dt>Next review</dt><dd>{esc(verdict["next_review"] or "none recorded")}</dd></div>'
             f'<div><dt>Verdict</dt><dd>{esc(verdict["status"] or "absent")}, wave {esc(verdict["wave"] or "none")}, dated {esc(verdict["date"] or "undated")}</dd></div>'
             f'<div><dt>final_stack.py status</dt><dd>{esc(layer["final_stack_status"])}</dd></div></dl>')
    outside = f'<p class="source-note">{layer["refs_outside_repository"]} cited references point outside this repository and are not listed.</p>' if layer["refs_outside_repository"] else ""
    return (f'<article class="lp-layer" id="{_anchor(layer["layer"])}" aria-labelledby="{_anchor(layer["layer"])}-title">'
            f'<header class="lp-layer-head"><h3 id="{_anchor(layer["layer"])}-title">{esc(layer["title"])}</h3><p class="lp-key"><code>{esc(layer["layer"])}</code></p>'
            f'<p class="lp-state lp-state--{esc(layer["state"].casefold())}">{_glyph_svg(layer["state"])}{esc(_STATE_TEXT[layer["state"]])}</p></header>'
            f'<p class="lp-choice">{esc(layer["current_choice"] or "No current choice recorded.")}</p>{facts}'
            f'<div class="lp-missing-wrap"><h4>What keeps it from FINAL</h4>{missing}</div>{winners}'
            f'<details class="lp-more"><summary>Open gaps ({layer["open_gap_count"]})</summary>{gaps}</details>'
            f'<details class="lp-more"><summary>Overturn when</summary><p>{esc(layer["overturn_when"] or "Not recorded.")}</p></details>'
            f'<details class="lp-more"><summary>Evidence files ({len(layer["evidence_refs"])})</summary>{_refs(layer["evidence_refs"])}{outside}</details></article>')


def _flags(manifest: dict) -> str:
    flags = manifest.get("flags") or {}
    if not flags:
        return '<section class="mf-view" id="lp-flags"><h2>Drift flags</h2><p class="mf-unreported">The final_stack.py flags were not produced for this build.</p></section>'
    totals = flags["totals"]

    def block(title: str, lines: list[str]) -> str:
        return f'<details class="lp-more" open><summary>{esc(title)} ({len(lines)})</summary>' + ("<ul class=\"lp-flag-list\">" + "".join(f"<li><code>{esc(line)}</code></li>" for line in lines) + "</ul>" if lines else "<p>None on this page.</p>") + "</details>"

    without = [line + f" ({reason})" for reason, lines in (flags.get("without_run") or {}).items() for line in lines]
    review = flags.get("past_next_review")
    review_text = (f'{len(review)} layers past next_review on {esc(flags.get("today"))}.' if review is not None else "next_review was not evaluated.")
    return ('<section class="mf-view" id="lp-flags" aria-labelledby="lp-flags-title"><h2 id="lp-flags-title">Drift flags from final_stack.py --check</h2>'
            f'<p>Report-only flags, produced by the script\'s own <code>flags()</code> on the committed final-stack.json. Across both catalogs it reports '
            f'{totals["pin_drift"]} winners whose run pin differs from the verdict pin, {totals["pin_drift_unknown"]} whose drift is unknown and {totals["without_run"]} without a run pin; '
            f'this page lists its own catalog\'s share. {review_text}</p>'
            + block("Run pin differs from the verdict pin", flags.get("pin_drift") or []) + block("Pin drift unknown", flags.get("pin_drift_unknown") or [])
            + block("Winner without a run pin", without) + "</section>")


def _figure_text(manifest: dict, drawn: dict) -> str:
    spec = manifest.get("topology") or manifest.get("flow") or {}
    names = {node["id"]: node["name"] for node in spec.get("nodes", [])}
    items = []
    catalog = manifest.get("catalog") or "this catalog"

    def role(chip: dict) -> str:
        if not chip.get("role"):
            return "not in the catalogs"
        return f'{chip["role"]} in {chip["layer"]}'

    for node in spec.get("nodes", []):
        chips = "; ".join(f'{chip["name"]} ({"pin " + str(chip["pin"]) if chip.get("pin") else "no run pin"}; {role(chip)})' for chip in node.get("chips", []))
        layers = ", ".join(node["layers"]) or f"no {catalog} layer"
        state = _STATE_TEXT.get(node.get("state"), "no layer state")
        refs = ", ".join(node["evidence_refs"]) or "no repository record at this commit"
        detail = " ".join(part for part in (node.get("sub"), node.get("tool")) if part)
        items.append(f'<li><strong>{esc(node["name"])}</strong> ({esc(detail)}). Layers: {esc(layers)}; state: {esc(state)}.' + (f' Chips: {esc(chips)}.' if chips else "")
                     + f' Records: <code>{esc(refs)}</code>.' + (f' Absent at this commit: <code>{esc(", ".join(node["absent_refs"]))}</code>.' if node["absent_refs"] else "") + '</li>')
    edges = []
    for edge in spec.get("edges", []):
        shown = [variant for variant, pairs in drawn.items() if (edge["from"], edge["to"]) in pairs]
        where = {"w": "wide", "m": "medium", "n": "narrow"}
        edges.append(f'<li>{esc(names.get(edge["from"], edge["from"]))} to {esc(names.get(edge["to"], edge["to"]))}'
                     + (f' ({esc(edge["label"].lower())})' if edge.get("label") else "") + f'; drawn in the {esc(", ".join(where[v] for v in shown) or "text view only")}{" view" if shown else ""}.</li>')
    return f'<h3>Parts</h3><ul>{"".join(items)}</ul><h3>Connections</h3><ul>{"".join(edges)}</ul>'


def render_layer_page(manifest: dict) -> tuple[str, dict]:
    """Body of the Foundation or North-star page from its layer manifest."""
    figure, drawn = _diagrams().layer_figure(manifest)
    north = bool(manifest.get("flow"))
    summary = manifest["summary"]
    finalized = summary["finalized"]
    jumps = [("lp-figure", "Data flow" if north else "Topology")] + ([("lp-decisions", "Data-layer decisions"), ("lp-pending", "Pending study")] if north else []) + [
        ("lp-rail-title", "Conditions by layer"), ("lp-register", "Layer register"), ("lp-flags", "Drift flags"), ("layer-sources", "Manifest and sources")]
    nav = '<nav class="mf-jump" aria-label="Page sections"><ul>' + "".join(f'<li><a href="#{anchor}">{esc(label)}</a></li>' for anchor, label in jumps) + "</ul></nav>"
    title = "How the trading data flows" if north else "What runs on the workstation"
    intro = ("Feeds, the owned collector, the trading lanes, the brokers and the history path, with each node tied to its trading layer." if north
             else "The lanes, the gateway and its provider slots, the runtime workers and the services around them, with each node tied to its foundation layer.")
    body = [_count_strip(manifest), nav,
            f'<section class="mf-view mf-hero" id="lp-figure" aria-labelledby="lp-figure-title"><h2 id="lp-figure-title">{title}</h2><p>{esc(intro)}</p>{figure}'
            + _diagrams()._alt("Read the diagram as text", _figure_text(manifest, drawn)) + "</section>"]
    if north:
        decisions = manifest["decisions"]
        rows = [[esc(row["decision"]), esc(row["element"]), _refs(row["evidence_refs"]) if row["evidence_refs"] else "None at this commit", esc(row["status"])] for row in decisions["rows"]]
        body.append('<section class="mf-view" id="lp-decisions" aria-labelledby="lp-decisions-title"><h2 id="lp-decisions-title">Data-layer decisions of 2026-10-14</h2>'
                    f'<p>The decisions are recorded in the {esc(decisions["record"])}. Each row names the element of the data flow it settles; the cited files are repository leads at this commit, not the decision text.</p>'
                    + _table("Data-layer decisions", ["Decision", "Data-flow element", "Repository evidence", "Status"], rows) + "</section>")
        pending = manifest["pending_study"]
        body.append(f'<section class="mf-view lp-pending" id="lp-pending" aria-labelledby="lp-pending-title"><h2 id="lp-pending-title">{esc(pending["title"])}</h2>'
                    f'<dl class="lp-facts"><div><dt>Readiness trigger</dt><dd>{esc(pending["trigger"])}</dd></div><div><dt>Content</dt><dd>{esc(pending["content"])}</dd></div></dl></section>')
    body.append(f'<section class="mf-view" aria-labelledby="lp-rail-title"><h2 id="lp-rail-title">Conditions by layer</h2>'
                '<p>A layer is FINAL only when final_stack.py reports it current or converged and every winner meets all four conditions. '
                'Rows link to the register entry.</p>' + _condition_key(manifest) + _rail(manifest) + "</section>")
    planned = manifest.get("planned_layers") or []
    planned_note = (f'<p class="source-note">final-stack.json also lists {len(planned)} planned layers outside this catalog file: '
                    + ", ".join(f'<code>{esc(row["layer"])}</code> ({esc(row["status"])})' for row in planned) + ".</p>") if planned else ""
    body.append('<section class="mf-view" id="lp-register" aria-labelledby="lp-register-title"><h2 id="lp-register-title">Layer register</h2>'
                '<p>Catalog order. Each entry gives the winners with their verdict and run pins, evidence class and the four conditions per winner, then the open gaps, the overturn rule and the evidence files.</p>'
                + planned_note + "".join(_layer_article(layer, manifest) for layer in manifest["layers"]) + "</section>")
    body.append(_flags(manifest))
    sources = "".join(f'<div><dt><code>{esc(source["path"])}</code></dt><dd>SHA-256 <code>{esc(source["sha256"])}</code>, {esc(source["bytes"])} bytes</dd></div>' for source in manifest.get("sources") or [])
    config = manifest.get("page_file") or {}
    body.append('<section class="mf-view" id="layer-sources" aria-labelledby="layer-sources-title"><h2 id="layer-sources-title">Manifest and sources</h2>'
                f'<p>The machine-readable manifest for this page is <a href="{esc(config.get("manifest") or "")}"><code>{esc(config.get("manifest") or "")}</code></a> '
                f'(schema <code>{esc(manifest["schema"])}</code>): one item per layer and winner with its repository, pins, evidence files at commit <code>{esc(manifest.get("commit") or "unrecorded")}</code>, state and missing conditions. '
                f'Conditions and states follow <code>{esc(manifest["protocol"])}</code>.</p><dl class="lp-sources">{sources}</dl>'
                + _diagrams()._alt("How the conditions and states are read", "<dl class=\"lp-defs\">" + "".join(f'<div><dt>{esc(c["label"])}</dt><dd>{esc(c["rule"])}</dd></div>' for c in manifest["definitions"]["conditions"])
                                   + "".join(f'<div><dt>{esc(_STATE_TEXT[s["state"]])}</dt><dd>{esc(s["rule"])}</dd></div>' for s in manifest["definitions"]["states"]) + "</dl>") + "</section>")
    counts = {"rendered_layer_count": len(manifest["layers"]), "items": len(manifest["items"]), "finalized": finalized, "drawn_connectors": {key: len(value) for key, value in drawn.items()}}
    return "".join(body), counts


def render(model: dict, inventory: dict, first_layer: str | None = None,
           detail_outputs: dict[str, bytes] | None = None) -> tuple[str, dict]:
    mapped, unmapped = join_inventory(model, inventory)
    all_layers = model["layers"]
    selected = [row for row in all_layers if first_layer in (None, row["key"], row["layer_id"], row["catalog"] + "/" + row["layer_id"])]
    toc = '<nav class="architecture-index" aria-label="Architecture layers"><ul>' + "".join(f'<li><a href="#layer-{esc(row["key"])}">{esc(row["title"])}</a></li>' for row in selected) + '</ul></nav>'
    sections = []
    for row in selected:
        key = row["key"]
        candidates = row.get("candidates") or []
        grand = row.get("g5_candidates") or []
        observation = model.get("adoption_observation") or {}
        observation_source = observation if observation.get("sha256") else model.get("adoption_source") or next((source for source in model.get("sources", []) if "adoption-now" in str(source.get("path"))), {})
        both = sum(1 for item in candidates if isinstance(item, dict) and (item.get("invoke") or {}).get("calls", 0) is not None and (item.get("invoke") or {}).get("calls", 0) > 0 and (item.get("e2e") or {}).get("verified", False))
        body = f'<section class="architecture-layer" id="layer-{esc(key)}" data-layer="{esc(key)}"><header><h2>{esc(row["title"])}</h2><p class="architecture-layer-id">{esc(row["catalog"])} / {esc(row["layer_id"])}</p><p class="architecture-observation">Invoke snapshot {esc(value(observation.get("generated_utc")))} · SHA-256 <code>{esc(value(observation_source.get("sha256")))}</code></p><p><strong>{both} of {len(candidates)}</strong> source components with both recorded organic use and upstream E2E evidence.</p></header><dl class="architecture-choice"><div><dt>Current choice</dt><dd>{esc(value(row.get("current_choice")))}</dd></div><div><dt>Recorded verdict</dt><dd>{esc(value(row.get("verdict_status") or row.get("decision")))}</dd></div><div><dt>Requirement</dt><dd>{esc(value(row.get("requirement")))}</dd></div><div><dt>Reason</dt><dd>{esc(value(row.get("rationale")))}</dd></div></dl>'
        counts_text = f'Component tables · {len(row.get("winners") or [])} winners · {len(candidates)} landscape candidates · {len(grand)} G5 candidates · {len(mapped[key])} inventory items'
        body += _deferred(key, counts_text, _layer_detail(row, mapped[key], model), detail_outputs)
        body += '<p class="source-note">Catalog date ' + esc(value(row.get("checked_at"))) + '; source references ' + _source_refs(row) + '</p></section>'
        sections.append(body)
    design = model.get("design") or {}
    design_text = esc(value({key: design.get(key) for key in ("path", "source", "ref", "tree_sha", "skill_md_sha256")}))
    sources = [source for source in (model.get("sources") or []) + (inventory.get("sources") or [])
               if isinstance(source, dict) and source.get("status") != "UNAPPROVED"]
    custody = _table("Architecture input custody", ["Source path", "SHA-256", "Source date / state"], [[esc(value(source.get("path"))), esc(value(source.get("sha256"))), esc(value(source.get("checked_at") or source.get("generated_utc") or source.get("status")))] for source in sources])
    manifest = _diagrams().render(model.get("manifest")) if first_layer is None else ""
    ledger = '<h2 id="architecture-ledger">Layer ledger</h2><p>Every layer in catalog order, with its recorded choice, alternatives, inventory and evidence tables.</p>' if manifest else ""
    body = manifest + ledger + f'<div class="architecture-summary"><p><strong>{len(selected)}</strong> rendered sections / <strong>{len(all_layers)}</strong> canonical landscape layers.</p><p>Invoke counts are observational (organic use, not a controlled trial). Client counts measure sessions; Bash-run CLI invocations are outside the producer’s MCP counters. Native host E2E, local receipts and vendor test-suite runs retain their distinct scopes.</p></div>' + toc + '<div class="architecture-sections">' + "".join(sections) + '</div>'
    coverage = inventory.get("coverage") or {}
    projection = coverage.get("automation_projection") or {}
    limits = projection.get("limits") or coverage.get("automation_limits") or []
    automation = '<p>Hooks: ' + esc(value(coverage.get("client_hook_wiring"))) + '. Cron: ' + esc(value(coverage.get("cron_status"))) + '.</p>'
    automation += '<ul>' + ''.join('<li>' + esc(str(limit)) + '</li>' for limit in limits) + '</ul>' if limits else ''
    body += '<section id="architecture-automation"><h2>Automation observation</h2>' + automation + '</section>'
    host = model.get("host_receipts") or {}
    local_items = host.get("items") or []
    local_source = next(iter(host.get("sources") or []), {})
    local_intro = f'<p>{len(local_items)} local host receipts · index <code>{esc(value(local_source.get("path")))}#{esc(value(local_source.get("sha256")))}</code></p>'
    body += '<section id="architecture-local-host-receipts"><h2>Local host receipts</h2>' + local_intro + _deferred("local-host-receipts", f'Local host receipt metadata · {len(local_items)} records', _local_host_receipts(host), detail_outputs) + '</section>'
    unmapped_detail = _closed("Unmapped observed items", len(unmapped), _inventory_table(unmapped, "Unmapped observed items", model))
    body += '<section id="architecture-unmapped"><h2>Unmapped inventory</h2><p>' + str(len(unmapped)) + ' items remain outside canonical joins and the committed mapping; each carries its specific reason.</p>' + (_deferred("unmapped", f'Unmapped observed items · {len(unmapped)} records', unmapped_detail, detail_outputs) if unmapped else '') + '</section>'
    unapproved = inventory.get("unapproved_counts") or {}
    unapproved_total = unapproved.get("total")
    counts_list = '<ul>' + ''.join(
        '<li>' + esc(value(row.get("root"))) + ' / ' + esc(value(row.get("kind"))) + ': ' + esc(value(row.get("count"))) + '</li>'
        for row in unapproved.get("by_kind_root", []) if isinstance(row, dict)
    ) + '</ul>'
    body += '<section id="architecture-unapproved"><h2>Unapproved discoveries</h2><p>' + esc(value(unapproved_total)) + ' unapproved inventory entries; individual names and paths withheld, metadata and content unread. Unavailable directory inventories remain UNREPORTED.</p>' + counts_list + '</section>'
    excluded = [row for row in model.get("excluded_supplements") or [] if isinstance(row, dict)]
    exclusions = ('<p>Landscape files excluded by the source policy and never opened: ' + "; ".join(f'<code>{esc(row.get("path"))}</code> ({esc(row.get("reason"))})' for row in excluded) + '.</p>') if excluded else ''
    custody_detail = '<p>Installed frontend-design metadata: <code>' + design_text + '</code></p>' + exclusions + _closed("Architecture input custody", len(sources), custody)
    body += '<section id="architecture-custody"><h2>Builder sources and design provenance</h2>' + _deferred("custody", f'Source custody · {len(sources)} records', custody_detail, detail_outputs) + '</section>'
    receipt = {"canonical_layer_count": len(all_layers), "rendered_layer_count": len(selected), "layer_keys": [row["key"] for row in selected], "mapped_inventory_occurrences": sum(len(items) for items in mapped.values()), "unmapped_inventory_items": len(unmapped), "unapproved_inventory_items": unapproved_total}
    return body, receipt
