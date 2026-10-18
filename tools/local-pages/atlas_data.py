#!/usr/bin/env python3
"""Read the harness atlas's sources through its declarative source map and project its model.

atlas_sources.json names every source the atlas reads: its section, the source_policy.json role that grants it,
its root, one exact path, what is read and the trigger that makes it present. atlas_map.json holds the reviewed
joins and paraphrases, each with its citation. Every declaration is bound to its exact grant before any file opens
(overview_data.load_page_sources): repository records through the existing Architecture and overview grants, the
two private token projections through source_policy.AtlasReads. A missing source is pending with its trigger, never
an error and never zero. Layer states and the FINAL count are overview_data.architecture(), that is
architecture_manifest.layer_manifest() over the committed records the layer pages read; this module adjudicates
nothing.

The page compounds: each build reduces the model to a timestamp-free state and compares its digest with the last row
of a hash-chained ledger kept beside the nonserved receipt. A row is appended only when the state changed (a new
measured day, a catalog, slot, routing, rule-record or skill-pin change); every build writes a receipt naming the
row it matched. A ledger that fails its check is left untouched for inspection and nothing is appended.

Every helper is the shipped module, loaded through overview_data.load (overview_data.py:36-44); nothing is copied.
Python 3.13 references: fcntl.flock, os.open(dir_fd, O_NOFOLLOW), tomllib and json at docs.python.org/3.13.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import tomllib
from typing import Any

HERE = Path(__file__).resolve().parent
SOURCE_MAP = HERE / "atlas_sources.json"
ATLAS_MAP = HERE / "atlas_map.json"
SOURCE_POLICY_PATH = HERE / "source_policy.json"
MAP_SCHEMA = "local-atlas-sources/1"
JOIN_SCHEMA = "local-atlas-map/1"
SCHEMA = "local-atlas/1"
LEDGER_SCHEMA = "local-atlas-ledger/1"
LATEST_SCHEMA = "token-rate-daily/1"
HISTORY_SCHEMA = "token-rate-history/1"
SECTIONS = ("layers", "stacks", "measured", "routing", "skills")
PAGE = "atlas.html"
STYLES = (HERE / "assets/architecture-manifest.css", HERE / "assets/overview.css", HERE / "assets/atlas.css")
MODULES = ("atlas_data", "atlas_view", "overview_data", "overview_view", "architecture_manifest", "architecture_diagrams",
           "architecture_sources", "architecture_view", "fleet_data", "source_policy", "sanitization", "build_pages")
LEDGER_NAME, LOCK_NAME = "atlas-ledger.json", ".atlas.lock"
LEDGER_CAP = 400
MAX_HTML = 1_500_000
FAMILIES = ("claude", "gpt", "muse")
LANES = ("claude:main", "claude:agent_tool", "claude:workflow", "gpt:codex", "muse:muse")
REASONS = ("collector_failed", "not_configured", "no_usage_keys", "no_rows_in_window")
COLLECTOR_STATES = ("measured", "collector_failed", "not_configured")
CLAUDE_USAGE = ("input", "output", "cache_read", "cache_creation", "cache_creation_5m", "cache_creation_1h", "cache_creation_ttl_unknown")
CODEX_USAGE = ("input", "cached_input", "cache_write", "output", "reasoning_output")
COVERAGE = ("claude_actors", "claude_actors_incomplete", "codex_sessions", "codex_usage_incomplete", "muse_receipts")
LEDGER_KINDS = ("layers", "slots", "routing", "rules", "skills", "measured")
# The installed copy each named skill is hashed from, through the existing user-root and repository grants
# (architecture_sources.py:449-458 reads the frontend-design copy the same way).
SKILL_PATHS = {"frontend-design": ("architecture_design", "user", ".agents/skills/frontend-design/SKILL.md"),
               "tdd": ("architecture_inventory", "user", ".agents/skills/tdd/SKILL.md"),
               "codebase-design": ("architecture_inventory", "user", ".agents/skills/codebase-design/SKILL.md"),
               "claude-native-practice": ("architecture_inventory", "repo", ".claude/skills/claude-native-practice/SKILL.md")}
ROLE_ORDER = {"winner": 0, "alternate": 1, "survivor": 2, "candidate": 3}
MAX_SERVERS, MAX_MODELS, MAX_ROWS = 64, 32, 400
_SERVER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,100}\Z")
_MODEL = re.compile(r"(claude|gpt|muse)-[a-z0-9][a-z0-9.\-]{0,60}\Z")
_MODEL_ALIASES = ("opus", "sonnet", "haiku", "inherit")
# Declared efforts per client: Claude Code's (examples/claude-native/workflows/child-usage.mjs:47) and Codex's ReasoningEffort
# at rust-v0.157.1, as tools/skill-usage/skill_usage.py:867-870 records it (protocol/src/openai_models.rs:59-72).
_CLAUDE_EFFORTS = ("low", "medium", "high", "xhigh", "max")
_CODEX_EFFORTS = ("none", "minimal", "low", "medium", "high", "xhigh", "max", "ultra", "persistent")
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}\Z")
_HEX40, _HEX64 = re.compile(r"[0-9a-f]{40}\Z"), re.compile(r"[0-9a-f]{64}\Z")
_LOOPBACK = re.compile(r"http://127\.0\.0\.1:\d{2,5}(?:/[A-Za-z0-9._~/-]*)?\Z")
# A monitoring link is a page in this served folder (a relative .html name, optionally in subfolders, with a plain fragment); never a scheme or a path out.
_PAGE_LINK = re.compile(r"(?:[A-Za-z0-9][A-Za-z0-9._-]*/)*[A-Za-z0-9][A-Za-z0-9._-]*\.html(?:#[A-Za-z0-9_-]+)?\Z")
_QUOTED = re.compile(r'"([^"]+)"')
# overview_data.repos() needs a finalize-all rows source; the atlas reads none, so it gets this pending stand-in.
NOT_READ = {"status": "pending", "name": "finalize-all rows", "declared": "not an atlas source", "root": "repo", "trigger": "not read by the atlas"}
LIMITS = ["The page projects named records; it establishes no verdict, E2E, invoke or landing.",
          "Private state records are shown by name; their digests stay in this nonserved receipt.",
          "Measured values are the daily projection's aggregates; unknown stays unknown and is never zero."]
_OVERVIEW: Any = None


class LedgerCheckError(ValueError):
    """The ledger file failed a check; it is kept for inspection and nothing is appended."""


def _overview_data() -> Any:
    global _OVERVIEW
    if _OVERVIEW is None:
        spec = importlib.util.spec_from_file_location("local_atlas_overview_data", HERE / "overview_data.py")
        if spec is None or spec.loader is None:
            raise ValueError("local atlas module unavailable")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _OVERVIEW = module
    return _OVERVIEW


def load(name: str) -> Any:
    """A shipped local-pages module, loaded once through overview_data.load, so error classes match across modules."""
    return _overview_data() if name == "overview_data" else _overview_data().load(name)


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


# ---------------------------------------------------------------- source map and joins
def load_sources(root: Path, state_root: Path, *, source_map: Path = SOURCE_MAP, policy_path: Path = SOURCE_POLICY_PATH) -> tuple[dict, dict, dict]:
    """The atlas source map, every declaration bound to its exact grant before any read (overview_data.load_page_sources)."""
    policy = load("source_policy")
    return load("overview_data").load_page_sources(root, state_root, source_map=source_map, policy_path=policy_path, schema=MAP_SCHEMA,
                                                    sections=SECTIONS, readers={"architecture_": policy.ArchitectureReads,
                                                                                "overview_": policy.OverviewReads, "atlas_": policy.AtlasReads})


def cites(value: Any) -> list[dict]:
    """Every {path, line, anchor} citation a map value holds."""
    found = []
    if isinstance(value, dict):
        if {"path", "line", "anchor"} <= set(value):
            found.append(value)
        for child in value.values():
            found += cites(child)
    elif isinstance(value, list):
        for child in value:
            found += cites(child)
    return found


def load_map(path: Path = ATLAS_MAP) -> tuple[dict, dict]:
    """The reviewed joins: three families, seven harness layers, three stacks and citations with a repository path,
    a positive line and an anchor. Facts a catalog holds are read at build time, never from this map."""
    policy, pages = load("source_policy"), load("build_pages")
    raw = policy._read_regular(Path(path), 1024 * 1024)
    document = pages.strict_json(raw)
    if not isinstance(document, dict) or document.get("schema") != JOIN_SCHEMA:
        raise policy.SourcePolicyError("atlas map must be a local-atlas-map/1 object")
    families = [row.get("id") for row in document.get("families") or [] if isinstance(row, dict)]
    layers = [row for row in document.get("harness_layers") or [] if isinstance(row, dict)]
    if families != list(FAMILIES) or len(layers) != 7 or len({row.get("id") for row in layers}) != 7:
        raise policy.SourcePolicyError("atlas map needs the three families and the seven harness layers")
    for row in layers:
        if not isinstance(row.get("title"), str) or not isinstance(row.get("catalog_layers"), list) or not isinstance(row.get("slots"), list):
            raise policy.SourcePolicyError("atlas harness layer needs a title, catalog layers and slots")
    for cite in cites(document):
        policy._relative(cite["path"])
        if isinstance(cite["line"], bool) or not isinstance(cite["line"], int) or cite["line"] < 1 or not isinstance(cite["anchor"], str) or not cite["anchor"].strip():
            raise policy.SourcePolicyError("atlas citation needs a repository path, a positive line and an anchor")
    for entry in document.get("monitoring") or []:
        opened = entry.get("open") if isinstance(entry.get("open"), dict) else {}
        if "url" in opened and not _LOOPBACK.fullmatch(str(opened["url"])):
            raise policy.SourcePolicyError("atlas monitoring URLs are loopback URLs only")
        if "links" in opened and (not isinstance(opened["links"], list)
                                  or not all(isinstance(link, str) and (_PAGE_LINK.fullmatch(link) or _LOOPBACK.fullmatch(link)) for link in opened["links"])):
            raise policy.SourcePolicyError("atlas monitoring links are page names in this folder or loopback URLs only")
    return document, {"path": "tools/local-pages/" + Path(path).name, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}


# ---------------------------------------------------------------- privacy helpers
def _private(text: str, *, opaque: bool = True) -> bool:
    """Whether text names a home path, URL or UUID (fleet_data._PRIVATE_LABEL), an email, secret or host label
    (architecture_manifest._EMAIL, _SECRET, _HOST) or, unless opaque is False, a token-shaped run (fleet_data._OPAQUE).
    The one screen every projected string passes; only a run pin sets opaque=False, to keep its 40-hex commit."""
    fleet, manifest = load("fleet_data"), load("architecture_manifest")
    patterns = (fleet._PRIVATE_LABEL, manifest._EMAIL, manifest._SECRET, manifest._HOST) + ((fleet._OPAQUE,) if opaque else ())
    return any(pattern.search(text) for pattern in patterns)


def _plain(value: Any, limit: int, *, clauses: int = 0) -> dict:
    """Catalog or slot text as plain text cut to its first clause (overview_data.plain and _short), or to its first
    `clauses` semicolon clauses; withheld when it names a home path, URL, UUID, email, host label or token (fleet_data
    _PRIVATE_LABEL/_OPAQUE, architecture_manifest _EMAIL/_SECRET/_HOST)."""
    if not isinstance(value, str) or not value.strip():
        return {"text": None, "withheld": False}
    overview = load("overview_data")
    text = "; ".join(overview.plain(value).split("; ")[:clauses]) if clauses else overview._short(overview.plain(value), limit)
    text = text if len(text) <= limit else overview._short(text, limit)
    return {"text": None, "withheld": True} if _private(text) else {"text": text, "withheld": False}


def _identifier(value: Any) -> str | None:
    """An identifier that passes fleet_data._identifier and the shared private-text screen."""
    value = load("fleet_data")._identifier(value)
    return value if value and not _private(value) else None


def _pin12(pin: Any) -> str:
    text = str(pin) if pin is not None else "none"
    return text[:12] if _HEX40.fullmatch(text) else text


def _label(value: Any) -> str | None:
    """Catalog text shown whole (a title): kept only when it names no home path, URL, UUID, email, host label or token."""
    if not isinstance(value, str) or not value.strip() or len(value) > 200:
        return None
    return None if _private(value) else value


def _pin_value(value: Any) -> str | None:
    """A run pin as final-stack.json records it (a version, a commit, or either with a short note): printable, at most
    120 characters, and naming no email, secret, host label or private path. Unlike _identifier it keeps a 40-hex
    commit, which fleet_data._OPAQUE would otherwise reject."""
    if not isinstance(value, str) or not value.strip() or len(value) > 120 or not value.isprintable():
        return None
    return None if _private(value, opaque=False) else value


# ---------------------------------------------------------------- catalog layers, harness and stacks
def layer_rows(sources: dict, glance: dict) -> dict:
    """Per catalog layer key: title, computed state, final-stack status, winners at run pins and survivors, from
    overview_data.repos() (overview_data.py:417-457) over the same records; requirement text from the catalog."""
    if glance.get("status") != "present":
        return {}
    result = load("overview_data").repos({**sources, "finalize_rows": NOT_READ}, glance)
    requirements = {}
    for catalog_key in ("foundation_catalog", "trading_catalog"):
        source = sources[catalog_key]
        content = source.get("content") if source["status"] == "present" else None
        name = "foundation" if catalog_key == "foundation_catalog" else "us-equities"
        for layer in (content or {}).get("layers") or []:
            if isinstance(layer, dict) and isinstance(layer.get("layer_id"), str):
                requirements[f"{name}/{layer['layer_id']}"] = layer.get("requirement")
    rows = {}
    for group in result.get("groups") or []:
        for row in group["rows"]:
            key = _identifier(row["layer"])
            if key is None:
                continue
            winners = []
            for winner in row["winners"]:
                pin = _pin_value(winner["run_pin"]) if winner["run_pin"] is not None else None
                reason = "withheld" if winner["run_pin"] is not None and pin is None else (_identifier(winner["run_reason"]) if winner["run_reason"] else None)
                winners.append({"component": _identifier(winner["component"]) or "UNREPORTED", "run_pin": pin, "run_reason": reason})
            rows[key] = {"layer": key, "title": _label(row["title"]) or key, "state": row["state"], "status": _identifier(row["status"]),
                         "in_catalog": row["in_catalog"], "page": row["page"], "survivors": row["survivors"],
                         "requirement": _plain(requirements.get(key), 220), "winners": winners}
    return rows


def _slot(by_slot: dict, slot_id: str) -> dict:
    row = by_slot.get(slot_id)
    if row is None:
        return {"slot": slot_id, "missing": True}
    return {"slot": slot_id, "status": _identifier(row.get("status")) or "UNREPORTED", "default": _plain(row.get("default"), 200), "missing": False}


def harness(joins: dict, layers: dict, slots: dict) -> list[dict]:
    """The seven harness layers by family: a recorded mechanism with its citations, the Claude practice slots read from
    slots.json, or no recorded mechanism (a gap); with each layer's catalog record."""
    by_slot = {row["slot"]: row for row in slots.get("rows") or []} if slots.get("status") == "present" else {}
    rows = []
    for layer in joins["harness_layers"]:
        cells = {}
        for family in FAMILIES:
            given = (layer.get("cells") or {}).get(family)
            if family == "claude" and given is None and layer["slots"]:
                cells[family] = {"kind": "slots", "pending": slots if slots.get("status") != "present" else None,
                                 "slots": [_slot(by_slot, slot_id) for slot_id in layer["slots"]]}
            elif given is None:
                cells[family] = {"kind": "gap"}
            else:
                cells[family] = {"kind": "text", "text": given["text"], "cites": given.get("cites") or []}
        catalog = [layers.get(key) or {"layer": key, "missing": True} for key in layer["catalog_layers"]]
        rows.append({"id": layer["id"], "title": layer["title"], "cells": cells, "catalog": catalog})
    return rows


def _server_classes(servers: list, final_stack: dict | None, stacks: list) -> dict:
    """Each listed server whose repository joins final-stack.json index.by_repository (a committed catalog), with its stack,
    layer and role there (the strongest role in a stack layer, else anywhere). A server that joins no entry stays unnamed."""
    by_repository = (((final_stack or {}).get("index") or {}).get("by_repository") or {}) if isinstance(final_stack, dict) else {}
    stack_of = {key: stack["id"] for stack in stacks for key in stack["catalog_layers"]}
    classes = {}
    for server in servers:
        entries = [entry for entry in by_repository.get(server["repository_key"]) or [] if isinstance(entry, dict)]
        joined = sorted((ROLE_ORDER.get(entry.get("role"), 9), f'{entry.get("catalog")}/{entry.get("layer_id")}', str(entry.get("role")))
                        for entry in entries)
        if not joined:
            classes[server["name"]] = {"named": False, "stack": None, "layer": None, "role": None}
            continue
        in_stack = [item for item in joined if item[1] in stack_of]
        rank, layer, role = (in_stack or joined)[0]
        classes[server["name"]] = {"named": True, "stack": stack_of.get(layer) if in_stack else None, "layer": layer, "role": role}
    return classes


def stacks(joins: dict, layers: dict, slots: dict, measured: dict) -> list[dict]:
    """The memory and retrieval, code-intelligence and token-efficiency stacks: each catalog layer with its requirement,
    state, winners and survivors; the practice slots; and the MCP servers the lanes called in each, with their role. The
    projection's servers[] is only the publish allowlist, so a server with no recorded call (summed over every window) is not listed."""
    by_slot = {row["slot"]: row for row in slots.get("rows") or []} if slots.get("status") == "present" else {}
    classes = measured.get("classes") or {}
    called = set(measured.get("called") or [])
    result = []
    for stack in joins["stacks"]:
        servers = sorted(({"name": name, "layer": info["layer"], "role": info["role"]} for name, info in classes.items() if info["stack"] == stack["id"] and name in called),
                         key=lambda row: (ROLE_ORDER.get(row["role"], 9), row["name"]))
        result.append({"id": stack["id"], "title": stack["title"], "layers": [layers.get(key) or {"layer": key, "missing": True} for key in stack["catalog_layers"]],
                       "slots": [_slot(by_slot, slot_id) for slot_id in stack["slots"]], "slots_status": slots.get("status"),
                       "servers": servers if measured.get("status") == "present" else None})
    return result


def definitions(joins: dict, stack_rows: list) -> list[dict]:
    """The terms as a visible key: the reviewed paraphrase for the harness, and each stack generated from its catalog
    layers' requirement text and its slots' default text."""
    by_stack = {row["id"]: row for row in stack_rows}
    result = []
    for entry in joins.get("definitions") or []:
        if entry.get("stack") in by_stack:
            stack = by_stack[entry["stack"]]
            parts = [{"layer": layer["layer"], "title": layer.get("title"), "requirement": (layer.get("requirement") or {}).get("text"),
                      "withheld": (layer.get("requirement") or {}).get("withheld", False), "missing": layer.get("missing", False)} for layer in stack["layers"]]
            result.append({"term": entry["term"], "stack": stack["id"], "parts": parts, "slots": stack["slots"]})
        else:
            result.append({"term": entry["term"], "text": entry.get("text"), "cites": entry.get("cites") or []})
    return result


# ---------------------------------------------------------------- measured projection
def _counts(value: Any, keep, limit: int) -> dict | None:
    if not isinstance(value, dict):
        return None
    count = load("fleet_data")._count
    kept = {}
    for name, number in list(value.items())[:limit]:
        if isinstance(name, str) and keep(name) and count(number) is not None:
            kept[name] = count(number)
    return dict(sorted(kept.items()))


def _fields(value: Any, keys: tuple) -> dict | None:
    count = load("fleet_data")._count
    return {key: count(value.get(key)) for key in keys} if isinstance(value, dict) else None


def _model_id(name: str) -> bool:
    """A model id the page may show: a full MODEL match that passes the shared private-text screen (a host label above all)."""
    return bool(_MODEL.fullmatch(name)) and not _private(name)


def _lane(raw: Any, servers: set) -> dict | None:
    """One lane's numerators, whitelisted as fleet_data._skill_usage does (fleet_data.py:892-920): counts through _count,
    server names only from the file's own servers list, model ids by full match, unknown keys ignored, null kept None."""
    if not isinstance(raw, dict):
        return None
    count = load("fleet_data")._count
    reason = raw.get("unmeasured")
    return {"actors": count(raw.get("actors")), "actors_complete": count(raw.get("actors_complete")), "tool_calls": count(raw.get("tool_calls")),
            "mcp": _counts(raw.get("mcp"), lambda name: name in servers, MAX_SERVERS), "mcp_other": count(raw.get("mcp_other")),
            "rtk": _fields(raw.get("rtk"), ("rewrites", "typed", "shell_calls")),
            "spawn": _fields(raw.get("spawn"), ("children", "codex_subagent_sessions")) or {"children": None, "codex_subagent_sessions": None},
            "models": _counts(raw.get("models"), _model_id, MAX_MODELS) or {},
            "usage": _fields(raw.get("usage"), CLAUDE_USAGE), "advisor": _fields(raw.get("advisor"), ("input", "output")),
            "codex_usage": _fields(raw.get("codex_usage"), CODEX_USAGE),
            "runs": _fields(raw.get("runs"), ("total", "completed", "failed")),
            "unmeasured": reason if reason in REASONS else None if reason is None else "unreported",
            "days_measured": count(raw.get("days_measured"))}


def _lanes(raw: Any, servers: set) -> dict:
    lanes = raw if isinstance(raw, dict) else {}
    return {lane: _lane(lanes[lane], servers) for lane in LANES if lane in lanes}


def projection(raw: Any) -> dict | None:
    """The token-rate-daily/1 projection, rebuilt from named fields only; None for any other schema."""
    if not isinstance(raw, dict) or raw.get("schema") != LATEST_SCHEMA:
        return None
    fleet, view = load("fleet_data"), load("architecture_view")
    servers = []
    for row in (raw.get("servers") if isinstance(raw.get("servers"), list) else [])[:MAX_SERVERS]:
        if isinstance(row, dict) and isinstance(row.get("name"), str) and _SERVER.fullmatch(row["name"]) and not _private(row["name"]):
            key = view.repo_key(row.get("repository"))
            if key:
                servers.append({"name": row["name"], "repository_key": "github.com/" + key})
    names = {row["name"] for row in servers}
    rollup = raw.get("rollup") if isinstance(raw.get("rollup"), dict) else {}
    partial = raw.get("partial_today") if isinstance(raw.get("partial_today"), dict) else None
    measured = raw.get("measured") if isinstance(raw.get("measured"), dict) else {}
    history = raw.get("history") if isinstance(raw.get("history"), dict) else {}
    day = lambda value: value if isinstance(value, str) and _DATE.fullmatch(value) else None
    return {"generated_at": fleet._stamp(raw.get("generated_at")), "servers": servers,
            "rollup": {"days": fleet._count(rollup.get("days")), "since": day(rollup.get("since")), "until": day(rollup.get("until")),
                       "days_present": fleet._count(rollup.get("days_present")), "days_complete": fleet._count(rollup.get("days_complete")),
                       "lanes": _lanes(rollup.get("lanes"), names)},
            "partial_today": None if partial is None else {"since": fleet._stamp(partial.get("since")), "until": fleet._stamp(partial.get("until")),
                                                           "lanes": _lanes(partial.get("lanes"), names)},
            "measured": {client: measured.get(client) is True for client in ("claude", "codex", "muse")},
            "coverage": _fields(raw.get("coverage"), COVERAGE) or dict.fromkeys(COVERAGE),
            "history": {"rows": fleet._count(history.get("rows")), "first_date": day(history.get("first_date")), "last_date": day(history.get("last_date"))}}


def history_projection(raw: Any, servers: set) -> dict | None:
    """token-rate-history/1 rows, newest last, at most 400, rebuilt from named fields only; None for any other schema."""
    if not isinstance(raw, dict) or raw.get("schema") != HISTORY_SCHEMA or not isinstance(raw.get("rows"), list):
        return None
    rows = []
    for row in raw["rows"][-MAX_ROWS:]:
        if not isinstance(row, dict) or not isinstance(row.get("date"), str) or not _DATE.fullmatch(row["date"]):
            continue
        collectors = row.get("collectors") if isinstance(row.get("collectors"), dict) else {}
        rows.append({"date": row["date"], "complete": row.get("complete") is True,
                     "collectors": {client: collectors.get(client) if collectors.get(client) in COLLECTOR_STATES else None for client in ("claude", "codex", "muse")},
                     "lanes": _lanes(row.get("lanes"), servers)})
    return {"rows": sorted(rows, key=lambda row: row["date"])}


def measured(sources: dict, joins: dict) -> dict:
    """The daily token projection, whitelisted; pending (never zeros) until the producer has published. Each lane gets
    its display metrics from its numerators: MCP calls by stack and the prompt-cache read share."""
    latest_source, history_source = sources["token_rate_latest"], sources["token_rate_history"]
    ttl = _ttl_note(sources["cc_slots"])
    if latest_source["status"] == "unreadable":
        # The file exists but does not parse: the producer has run, so the page says so and keeps the record for inspection.
        return {"status": "unreadable", "source": latest_source, "history_source": history_source, "ttl_note": ttl}
    if latest_source["status"] != "present":
        return {"status": "pending", "source": latest_source, "history_source": history_source, "ttl_note": ttl}
    latest = projection(latest_source.get("content"))
    if latest is None:
        return {"status": "unreadable", "source": {**latest_source, "status": "unreadable", "reason": "the record is not schema token-rate-daily/1"},
                "history_source": history_source, "ttl_note": ttl}
    names = {row["name"] for row in latest["servers"]}
    history = history_projection(history_source.get("content"), names) if history_source["status"] == "present" else None
    final_stack = sources["final_stack"].get("content") if sources["final_stack"]["status"] == "present" else None
    classes = _server_classes(latest["servers"], final_stack, joins["stacks"])
    windows = [latest["rollup"]["lanes"], (latest["partial_today"] or {}).get("lanes") or {}] + [row["lanes"] for row in (history or {}).get("rows") or []]
    for lanes in windows:
        for lane in lanes.values():
            if lane is not None:
                lane["metrics"] = {"mcp": mcp_classes(lane, classes), "cache_read_share": cache_read_share(lane)}
    return {"status": "present", "latest": latest, "history": history, "history_source": history_source, "classes": classes,
            "called": called_servers(windows), "ttl_note": ttl}


def called_servers(windows: list) -> list[str]:
    """The servers whose calls, summed over every window, are above zero: the allowlist alone never says a server was called."""
    totals: dict = {}
    for lanes in windows:
        for lane in lanes.values():
            for name, number in ((lane or {}).get("mcp") or {}).items():
                totals[name] = totals.get(name, 0) + number
    return sorted(name for name, number in totals.items() if number > 0)


def _ttl_note(source: dict) -> dict | None:
    """The prompt-caching slot's status and route text (slots.json:664-668), stated beside the TTL columns without a judgment."""
    content = source.get("content") if source["status"] == "present" and isinstance(source.get("content"), dict) else None
    slot = next((row for row in (content or {}).get("slots") or [] if isinstance(row, dict) and row.get("id") == "prompt-caching"), None)
    if slot is None:
        return None
    return {"slot": "prompt-caching", "status": _identifier(slot.get("status")) or "UNREPORTED", "route": _plain(slot.get("route"), 260, clauses=2)}


def ratio(part: Any, whole: Any) -> float | None:
    """A share from its numerators; None (no data) when either is unknown or the denominator is zero."""
    return None if part is None or whole is None or whole == 0 else part / whole


def cache_read_share(lane: dict) -> float | None:
    """Claude: cache_read / (input + cache_creation + cache_read); Codex: cached_input / input, since its input already
    includes the cached part. The two clients' categories keep their own inclusion semantics and are never added."""
    usage, codex = lane.get("usage"), lane.get("codex_usage")
    if usage:
        parts = [usage.get(key) for key in ("input", "cache_creation", "cache_read")]
        return None if any(part is None for part in parts) else ratio(usage["cache_read"], sum(parts))
    if codex:
        return ratio(codex.get("cached_input"), codex.get("input"))
    return None


def mcp_classes(lane: dict, classes: dict) -> dict:
    """A lane's MCP calls by stack (token efficiency, memory and retrieval, code intelligence) and other: a server outside
    every stack layer, one that joins no catalog entry, and every unlisted server count as other."""
    if lane.get("mcp") is None:
        return dict.fromkeys(("token_efficiency", "memory_rag", "code_intel", "other"))
    # An unknown mcp_other leaves the other class unknown too: unknown is never counted as zero.
    totals = {"token_efficiency": 0, "memory_rag": 0, "code_intel": 0, "other": lane.get("mcp_other")}
    for name, number in lane["mcp"].items():
        info = classes.get(name) or {}
        key = info.get("stack") if info.get("stack") in totals else "other"
        totals[key] = None if totals[key] is None else totals[key] + number
    return totals


# ---------------------------------------------------------------- routing, rules, monitoring and skills
def parse_agent(text: str, suffix: str) -> tuple[str | None, str | None]:
    """The declared model and effort only: a Markdown definition's frontmatter model: and effort: lines, or a TOML
    definition's top-level model and model_reasoning_effort keys. A value outside the whitelist is UNREPORTED."""
    model = effort = None
    if suffix == ".md":
        lines = text.splitlines()
        if lines and lines[0].strip() == "---":
            for line in lines[1:]:
                if line.strip() == "---":
                    break
                match = re.match(r"(model|effort):\s*(.*?)\s*$", line)
                if match:
                    value = match.group(2).strip("'\"")
                    model, effort = (value, effort) if match.group(1) == "model" else (model, value)
    else:
        try:
            document = tomllib.loads(text)
        except tomllib.TOMLDecodeError:
            return "UNREPORTED", "UNREPORTED"
        model, effort = document.get("model"), document.get("model_reasoning_effort")
        model, effort = (model if model is None or isinstance(model, str) else repr(model)), (effort if effort is None or isinstance(effort, str) else repr(effort))
    model = None if model is None else model if model in _MODEL_ALIASES or _MODEL.fullmatch(model) else "UNREPORTED"
    efforts = _CLAUDE_EFFORTS if suffix == ".md" else _CODEX_EFFORTS
    effort = None if effort is None else effort if effort in efforts else "UNREPORTED"
    return model, effort


def routing(sources: dict, joins: dict, measured_data: dict) -> dict:
    """Each role's declared model and effort, beside the models the projection observed per lane; never merged."""
    clients = {row["id"]: row["client"] for row in joins["families"]}
    rows = []
    for source in sources.values():
        if source["section"] != "routing":
            continue
        family = "claude" if source["declared"].startswith("adoption/agents/claude/") else "gpt"
        row = {"family": family, "client": clients[family], "role": _identifier(PurePosixPath(source["declared"]).stem) or "UNREPORTED",
               "path": source["declared"], "status": source["status"]}
        if source["status"] == "present" and isinstance(source.get("content"), str):
            row["model"], row["effort"] = parse_agent(source["content"], PurePosixPath(source["declared"]).suffix)
        else:
            row.update(model=None, effort=None, trigger=source["trigger"], reason=source.get("reason"))
        rows.append(row)
    muse = next(row for row in joins["families"] if row["id"] == "muse")
    cite = muse.get("model_cite") or {}
    quoted = _QUOTED.search(str(cite.get("anchor") or ""))
    model = quoted.group(1) if quoted and _MODEL.fullmatch(quoted.group(1)) else None
    rows.append({"family": "muse", "client": muse["client"], "role": "reader", "path": cite.get("path"), "line": cite.get("line"),
                 "status": "present" if model else "pending", "model": model, "effort": None})
    observed = {}
    if measured_data.get("status") == "present":
        observed = {lane: values.get("models") or {} for lane, values in measured_data["latest"]["rollup"]["lanes"].items()}
    return {"rows": rows, "observed": observed}


def rules(joins: dict) -> list[dict]:
    """The owner's standing rules as paraphrased in the map, with the record each is written in; a rule without a ruling
    record is pending with its trigger. The page never invents a citation."""
    return [{"id": rule["id"], "text": rule["text"], "recorded_in": rule.get("recorded_in") or [], "related": rule.get("related") or [],
             "mechanism": rule.get("mechanism") or [], "mechanism_note": rule.get("mechanism_note"), "trigger": rule.get("trigger"),
             "state": "recorded" if rule.get("recorded_in") else "pending"} for rule in joins.get("standing_rules") or []]


def skills(sources: dict, joins: dict, root: Path, state_root: Path, *, policy_path: Path, user_root: Path | None) -> dict:
    """The skills that shaped the page, at their manifest pins, with the installed copy's digest and whether it matches."""
    manifest = sources["skill_manifest"]
    content = manifest.get("content") if manifest["status"] == "present" and isinstance(manifest.get("content"), dict) else None
    by_name = {row["name"]: row for row in (content or {}).get("skills") or [] if isinstance(row, dict) and isinstance(row.get("name"), str)}
    policy, helpers = load("source_policy"), load("architecture_sources")
    reads = policy.ArchitectureReads(root, state_root, policy_path=policy_path, user_root=user_root)
    rows = []
    for item in joins.get("skills_used") or []:
        name, row = item["name"], by_name.get(item["name"]) or {}
        role, base, relative = SKILL_PATHS[name]
        installed, reason = None, None
        try:
            # architecture_sources._receipt (architecture_sources.py:81-83): the exact role's bounded no-symlink read.
            installed = helpers._receipt(reads.roots[base] / relative, relative, reads, role)["sha256"]
        except FileNotFoundError:
            reason = "not installed"
        except (OSError, ValueError):
            reason = "unreadable"
        pin = row.get("skill_md_sha256") if isinstance(row.get("skill_md_sha256"), str) and _HEX64.fullmatch(row["skill_md_sha256"]) else None
        rows.append({"name": name, "use": item.get("use"), "source": _identifier(row.get("source")), "path": _identifier(row.get("path")),
                     "ref": row.get("ref") if isinstance(row.get("ref"), str) and _HEX40.fullmatch(row["ref"]) else None,
                     "tree": row.get("tree_sha") if isinstance(row.get("tree_sha"), str) and _HEX40.fullmatch(row["tree_sha"]) else None,
                     "status": _identifier(row.get("status")), "in_manifest": bool(row), "pin_sha256": pin, "installed_sha256": installed,
                     "installed_reason": reason, "match": None if pin is None or installed is None else installed == pin})
    return {"status": "present" if content is not None else "pending", "source": manifest, "rows": rows}


# ---------------------------------------------------------------- model
def model(root: Path, state_root: Path, *, source_map: Path = SOURCE_MAP, atlas_map: Path = ATLAS_MAP, policy_path: Path = SOURCE_POLICY_PATH,
          commit: str | None = None, user_root: Path | None = None) -> dict:
    overview = load("overview_data")
    document, readers, map_receipt = load_sources(root, state_root, source_map=source_map, policy_path=policy_path)
    joins, joins_receipt = load_map(atlas_map)
    sources = overview.read_declared(document, root, state_root, readers)
    if commit is None:
        repo_records = {source["path"]: source["raw"] for source in sources.values() if source["root"] == "repo" and source.get("raw") is not None}
        commit = load("architecture_builder")._commit(Path(root), repo_records) if repo_records else None
    glance = overview.architecture(sources, Path(root), commit)
    slot_rows = overview.slots(sources["cc_slots"])
    layers = layer_rows(sources, glance)
    measured_data = measured(sources, joins)
    stack_rows = stacks(joins, layers, slot_rows, measured_data)
    return {"commit": commit, "source_map": map_receipt, "atlas_map": joins_receipt, "policy": dict(readers["atlas_"].policy.receipt),
            "sources": sources, "joins": joins, "architecture": glance, "slots": slot_rows, "layers": layers,
            "planned": sum(1 for row in layers.values() if not row["in_catalog"]),
            "harness": harness(joins, layers, slot_rows), "stacks": stack_rows, "definitions": definitions(joins, stack_rows),
            "measured": measured_data, "routing": routing(sources, joins, measured_data), "rules": rules(joins),
            "monitoring": joins.get("monitoring") or [], "port_note": joins.get("port_note"),
            "skills": skills(sources, joins, Path(root), Path(state_root), policy_path=policy_path, user_root=user_root)}


# ---------------------------------------------------------------- ledger
def ledger_state(data: dict) -> dict:
    """The timestamp-free state a ledger row records. It holds no time and no partial-day value, so a new row means a
    new measured day or a catalog, slot, routing, rule-record or skill-pin change."""
    layers = {key: {"status": row["status"], "state": row["state"], "winners": [f'{winner["component"]}@{_pin12(winner["run_pin"])}' for winner in row["winners"]]}
              for key, row in sorted(data["layers"].items())}
    slots = {str(row["slot"]): str(row["status"]) for row in data["slots"].get("rows") or []} if data["slots"].get("status") == "present" else {}
    routing_state = {f'{row["family"]}/{row["role"]}': f'{row.get("model") or "null"}/{row.get("effort") or "null"}' for row in data["routing"]["rows"]}
    skill_state = {row["name"]: f'{(row["ref"] or "none")[:12]}:{(row["pin_sha256"] or "none")[:12]}:{"absent" if row["match"] is None else "match" if row["match"] else "differs"}'
                   for row in data["skills"]["rows"]}
    latest = (data["measured"].get("latest") or {}) if data["measured"].get("status") == "present" else {}
    history = latest.get("history") or {}
    return {"layers": layers, "slots": dict(sorted(slots.items())), "routing": dict(sorted(routing_state.items())),
            "rules": {rule["id"]: rule["state"] for rule in data["rules"]}, "skills": skill_state,
            "measured": {"last_closed_day": history.get("last_date"), "history_rows": history.get("rows")}}


def _flat(state: dict | None) -> dict:
    flat = {}
    for kind in LEDGER_KINDS:
        for key, value in ((state or {}).get(kind) or {}).items():
            if isinstance(value, dict):
                for field, item in value.items():
                    flat[(kind, f"{key} {field}")] = ", ".join(item) if isinstance(item, list) else item
            else:
                flat[(kind, key)] = value
    return flat


def changes(previous: dict | None, state: dict) -> list[dict]:
    """What differs from the previous row's state, field by field; the first row records none."""
    if previous is None:
        return []
    before, after = _flat(previous), _flat(state)
    return [{"kind": kind, "key": key, "from": before.get((kind, key)), "to": after.get((kind, key))}
            for kind, key in sorted(set(before) | set(after)) if before.get((kind, key)) != after.get((kind, key))]


def verify_ledger(raw: bytes) -> dict:
    """The ledger with every row's digest, state digest, sequence and previous-row link checked; LedgerCheckError otherwise."""
    try:
        document = load("build_pages").strict_json(raw)
    except (ValueError, UnicodeError) as error:
        raise LedgerCheckError("the ledger does not parse") from error
    rows, dropped = (document.get("rows"), document.get("dropped")) if isinstance(document, dict) else (None, None)
    if not isinstance(document, dict) or document.get("schema") != LEDGER_SCHEMA or not isinstance(rows, list) or not isinstance(dropped, dict):
        raise LedgerCheckError("the ledger is not a local-atlas-ledger/1 document")
    count = load("fleet_data")._count
    previous, seq = dropped.get("last_row_sha256"), count(dropped.get("rows"))
    if seq is None or not (previous is None or isinstance(previous, str) and _HEX64.fullmatch(previous)) or (seq == 0) != (previous is None):
        raise LedgerCheckError("the ledger's dropped-row anchor does not verify")
    for row in rows:
        if not isinstance(row, dict) or row.get("row_sha256") != digest({key: value for key, value in row.items() if key != "row_sha256"}):
            raise LedgerCheckError("a ledger row's digest does not verify")
        if row.get("state_sha256") != digest(row.get("state")) or row.get("previous_row_sha256") != previous or row.get("seq") != seq + 1:
            raise LedgerCheckError("the ledger's chain does not verify")
        previous, seq = row["row_sha256"], row["seq"]
    return document


def _read_optional(path: Path, limit: int) -> bytes | None:
    try:
        return load("source_policy")._read_regular(path, limit)
    except FileNotFoundError:
        return None


def advance(ledger_path: Path, receipt: Path, state: dict, *, generated: str, commit: str | None, sources: dict, cap: int = LEDGER_CAP) -> dict:
    """Compare the state with the ledger's last row: append a chained row when it changed, else count one more check of
    the matched row (from the previous receipt). A ledger that fails its check is left byte-identical and reported."""
    pages, policy = load("build_pages"), load("source_policy")
    state_sha = digest(state)
    try:
        raw = _read_optional(ledger_path, 64 * 1024 * 1024)
        document = verify_ledger(raw) if raw is not None else {"schema": LEDGER_SCHEMA, "cap": cap, "dropped": {"rows": 0, "last_row_sha256": None}, "rows": []}
    except (LedgerCheckError, policy.SourcePolicyError, OSError) as error:
        reason = str(error) if isinstance(error, LedgerCheckError) else "the ledger could not be read as a regular file"
        return {"path": str(ledger_path), "status": "unreported", "rows": None, "row_sha256": None, "previous_row_sha256": None,
                "checks_since_row": None, "reason": reason, "history": [], "raw": None, "dropped": None}
    rows = document["rows"]
    last = rows[-1] if rows else None
    if last is not None and last["state_sha256"] == state_sha:
        try:
            previous_receipt = pages.strict_json(_read_optional(receipt, 8 * 1024 * 1024) or b"{}")
        except (ValueError, UnicodeError, policy.SourcePolicyError, OSError):
            previous_receipt = {}
        prior = (previous_receipt.get("ledger") or {}) if isinstance(previous_receipt, dict) else {}
        checks = load("fleet_data")._count(prior.get("checks_since_row"))
        checks = checks + 1 if prior.get("row_sha256") == last["row_sha256"] and checks is not None else 1
        return {"path": str(ledger_path), "status": "unchanged", "rows": len(rows), "row_sha256": last["row_sha256"],
                "previous_row_sha256": last["previous_row_sha256"], "checks_since_row": checks, "reason": None,
                "history": rows, "raw": None, "dropped": document["dropped"]}
    dropped = dict(document["dropped"])
    row = {"seq": (last["seq"] if last else dropped["rows"]) + 1, "generated_utc": generated, "commit": commit, "state_sha256": state_sha,
           "state": state, "changes": changes(last["state"] if last else None, state), "sources": sources,
           "previous_row_sha256": last["row_sha256"] if last else dropped["last_row_sha256"]}
    row["row_sha256"] = digest(row)
    rows = rows + [row]
    while len(rows) > cap:
        gone = rows.pop(0)
        dropped = {"rows": dropped["rows"] + 1, "last_row_sha256": gone["row_sha256"]}
    updated = {"schema": LEDGER_SCHEMA, "cap": cap, "dropped": dropped, "rows": rows}
    return {"path": str(ledger_path), "status": "appended", "rows": len(rows), "row_sha256": row["row_sha256"],
            "previous_row_sha256": row["previous_row_sha256"], "checks_since_row": 0, "reason": None, "history": rows, "dropped": dropped,
            "raw": (json.dumps(updated, indent=1, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")}


@contextmanager
def _locked(directory_path: Path):
    """One exclusive flock on <receipt dir>/.atlas.lock for the whole read-modify-publish, as fleet_data._actions
    coordinates its cache (fleet_data.py:484-493): a no-symlink directory walk, O_NOFOLLOW and mode 0600."""
    fleet = load("fleet_data")
    with fleet._directory(directory_path, create=True) as directory:
        # New directories are made 0700; one that already exists looser (the ledger and receipt live here) is tightened through its descriptor.
        if stat.S_IMODE(os.fstat(directory).st_mode) & 0o077:
            os.fchmod(directory, 0o700)
        fleet._destination(directory, LOCK_NAME)
        lock = os.open(LOCK_NAME, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, mode=0o600, dir_fd=directory)
        try:
            if not stat.S_ISREG(os.fstat(lock).st_mode):
                raise OSError("nonregular atlas lock rejected")
            fcntl.flock(lock, fcntl.LOCK_EX)
            yield
        finally:
            os.close(lock)


# ---------------------------------------------------------------- page
def build_atlas_page(root: Path, state_root: Path, output_dir: Path, receipt: Path, *, generated: str | None = None,
                     commit: str | None = None, user_root: Path | None = None, source_map: Path = SOURCE_MAP,
                     atlas_map: Path = ATLAS_MAP, policy_path: Path = SOURCE_POLICY_PATH) -> dict:
    """Render atlas.html, append the ledger row its state needs and publish both, the receipt last."""
    pages, policy, view = load("build_pages"), load("source_policy"), load("atlas_view")
    output_dir, receipt = pages.no_symlinks(output_dir), pages.no_symlinks(receipt)
    if receipt.is_relative_to(output_dir):
        raise ValueError("atlas receipt must remain outside the served root")
    ledger_path = pages.no_symlinks(receipt.with_name(LEDGER_NAME))
    generated = generated or datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    with _locked(receipt.parent):
        data = model(root, state_root, source_map=source_map, atlas_map=atlas_map, policy_path=policy_path, commit=commit, user_root=user_root)
        sources = data["sources"]
        ledger = advance(ledger_path, receipt, ledger_state(data), generated=generated, commit=data["commit"],
                         sources={key: sources[key].get("sha256") for key in ("final_stack", "cc_slots", "token_rate_history")})
        data["ledger"] = ledger
        body, counts = view.render(data)
        styles = b"".join(policy._read_regular(path, 1024 * 1024) for path in STYLES)
        head = "\n  <style>\n" + styles.decode("utf-8") + "  </style>"
        present = [source for source in sources.values() if source["status"] == "present"]
        scope = (f'{len(present)} of {len(sources)} declared sources present; committed records at {data["commit"] or "an unrecorded commit"}'
                 + (f'; daily token projection generated {data["measured"]["latest"]["generated_at"]}' if data["measured"]["status"] == "present" else ""))
        html = pages.document("atlas", "Harness atlas", view.LEDE, scope, body, generated, sources["final_stack"].get("sha256") or "pending", [],
                              head=head, digest_label="final-stack.json SHA-256")
        # architecture_builder.py:198-199 caps the initial Architecture HTML the same way.
        if len(html) >= MAX_HTML:
            raise ValueError("atlas HTML must be under 1500000 bytes")
        outputs = {PAGE: html}
        for name in ("site.css", "site.js"):
            outputs["assets/" + name] = policy._read_regular(HERE / "assets" / name, 8 * 1024 * 1024)
        rules_state = [rule["state"] for rule in data["rules"]]
        result = {"schema": SCHEMA, "generated_utc": generated, "commit": data["commit"], "page": PAGE,
                  "source_map": data["source_map"], "atlas_map": data["atlas_map"], "source_policy": data["policy"],
                  "sources": [{key: source.get(key) for key in ("id", "section", "role", "root", "declared", "status", "path", "name", "sha256", "bytes", "reason", "trigger")}
                              for source in sources.values()],
                  "installed_skills": [{key: row[key] for key in ("name", "pin_sha256", "installed_sha256", "match")} for row in data["skills"]["rows"]],
                  "present": sorted(source["id"] for source in present),
                  "pending": sorted(source["id"] for source in sources.values() if source["status"] != "present"),
                  "counts": {**counts, "catalog_layers": data["architecture"].get("total"), "final": data["architecture"].get("finalized"),
                             "planned_layers": data["planned"], "measured_days": len(((data["measured"].get("history") or {}).get("rows")) or []),
                             "rules_recorded": rules_state.count("recorded"), "rules_pending": rules_state.count("pending"), "bytes": len(html)},
                  "ledger": {key: ledger[key] for key in ("path", "status", "rows", "row_sha256", "previous_row_sha256", "checks_since_row", "reason")},
                  "modules": [{"path": str(HERE / (name + ".py")), "sha256": hashlib.sha256(policy._read_regular(HERE / (name + ".py"), 8 * 1024 * 1024)).hexdigest()}
                              for name in MODULES],
                  "style": [{"path": str(path), "sha256": hashlib.sha256(policy._read_regular(path, 1024 * 1024)).hexdigest()} for path in STYLES],
                  "outputs": {name: {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)} for name, raw in outputs.items()},
                  "limits": LIMITS}
        pages.publish(output_dir, receipt, outputs, result, nonserved={ledger_path: ledger["raw"]} if ledger["status"] == "appended" else None)
    return result
