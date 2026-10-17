#!/usr/bin/env python3
"""Read the overview page's sources through its declarative source map.

overview_sources.json names every source the overview reads: its section,
the source_policy.json role that grants it, its root, one exact path and
the trigger that makes it present. Each declaration is checked against its
exact grant before any file is opened; no filename family is read, so the path
is the explicit pointer to the current record. A missing source is pending
with its trigger, never an error. Layer
states and the FINAL count are architecture_manifest.layer_manifest() over
the same committed records the Foundation and North-star pages read; this
module adjudicates nothing.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import importlib.util
from pathlib import Path, PurePosixPath
import re
from typing import Any

HERE = Path(__file__).resolve().parent
SOURCE_MAP = HERE / "overview_sources.json"
SOURCE_POLICY_PATH = HERE / "source_policy.json"
MAP_SCHEMA = "local-overview-sources/1"
SCHEMA = "local-overview/1"
SECTIONS = ("architecture", "feeds", "strategies", "workers", "repos", "evidence", "claude_code", "github")
MAX_BYTES = 16 * 1024 * 1024
PAGE = "overview.html"
STYLE = HERE / "assets/overview.css"
MODULES = ("overview_data", "overview_view", "architecture_manifest", "architecture_diagrams", "source_policy", "sanitization", "build_pages")
_LOADED: dict[str, Any] = {}


def load(name: str) -> Any:
    if name not in _LOADED:
        spec = importlib.util.spec_from_file_location("local_overview_" + name, HERE / (name + ".py"))
        if spec is None or spec.loader is None:
            raise ValueError("local overview module unavailable")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _LOADED[name] = module
    return _LOADED[name]


# ---------------------------------------------------------------- source map
def _page_label(schema: str) -> str:
    """The page a source-map schema belongs to: local-overview-sources/1 is the overview's, local-atlas-sources/1 the atlas's."""
    return schema.split("/", 1)[0].removeprefix("local-").removesuffix("-sources")


def _reader(readers: dict, role: str) -> Any:
    """The reader whose role prefix the role carries; a role with no known prefix goes to the page's own grants, listed last,
    which refuse it (as the overview always did for a role that is not an Architecture role)."""
    return next((reader for prefix, reader in readers.items() if role.startswith(prefix)), list(readers.values())[-1])


def load_page_sources(root: Path, state_root: Path, *, source_map: Path, policy_path: Path, schema: str, sections: tuple,
                      readers: dict) -> tuple[dict, dict, dict]:
    """Parse a page's source map and bind every declaration to its exact grant before any source read.

    readers maps a role prefix to its source_policy reader class, the page's own grants last; each one is built over the
    two roots, and every declaration is checked by the reader its role prefix names. An Architecture role needs its exact
    Architecture grant and no glob. Returns the map, the built readers by prefix and the map's own custody record.
    """
    policy = load("source_policy")
    label = _page_label(schema)
    raw = policy._read_regular(Path(source_map), 1024 * 1024)
    document = load("build_pages").strict_json(raw)
    if not isinstance(document, dict) or document.get("schema") != schema or not isinstance(document.get("sources"), dict):
        raise policy.SourcePolicyError(f"{label} source map must be a {schema} object with a sources map")
    built = {prefix: reader(root, state_root, policy_path=policy_path) for prefix, reader in readers.items()}
    for key, entry in document["sources"].items():
        if not isinstance(entry, dict) or entry.get("section") not in sections or entry.get("root") not in ("repo", "state"):
            raise policy.SourcePolicyError(f"{label} source {key} needs a known section and root")
        if not isinstance(entry.get("trigger"), str) or not entry["trigger"].strip() or not isinstance(entry.get("reads"), str):
            raise policy.SourcePolicyError(f"{label} source {key} needs what it reads and its readiness trigger")
        role, path, glob = entry.get("role"), entry.get("path"), entry.get("glob")
        if not isinstance(role, str):
            raise policy.SourcePolicyError(f"{label} source {key} needs a role")
        if role.startswith("architecture_"):
            architecture = built.get("architecture_")
            if architecture is None or glob is not None or not isinstance(path, str) or (entry["root"], policy._relative(path)) not in architecture.allowed.get(role, set()):
                raise policy.SourcePolicyError(f"{label} source has no exact Architecture grant: " + key)
        else:
            _reader(built, role).validate(role, entry["root"], path=path, glob=glob)
    receipt = {"path": "tools/local-pages/" + Path(source_map).name, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
    return document, built, receipt


def load_source_map(root: Path, state_root: Path, *, source_map: Path = SOURCE_MAP, policy_path: Path = SOURCE_POLICY_PATH) -> tuple[dict, Any, Any, dict]:
    """Parse the map and bind every declaration to its exact grant before any source read."""
    policy = load("source_policy")
    document, readers, receipt = load_page_sources(root, state_root, source_map=source_map, policy_path=policy_path, schema=MAP_SCHEMA,
                                                   sections=SECTIONS, readers={"architecture_": policy.ArchitectureReads, "overview_": policy.OverviewReads})
    architecture, overview = readers["architecture_"], readers["overview_"]
    workers = document.get("workers", [])
    if not isinstance(workers, list):
        raise policy.SourcePolicyError("overview workers must be a list")
    for worker in workers:
        if not isinstance(worker, dict) or not isinstance(worker.get("name"), str):
            raise policy.SourcePolicyError("overview worker needs a name")
        for field in ("state", "receipt"):
            binding = worker.get(field)
            if binding is not None and (not isinstance(binding, dict) or binding.get("source") not in document["sources"]):
                raise policy.SourcePolicyError(f"overview worker {worker['name']} binds {field} to an undeclared source")
    return document, architecture, overview, receipt


def read_sources(document: dict, root: Path, state_root: Path, architecture: Any, overview: Any) -> dict[str, dict]:
    """Read each declared source once; record present, pending or unreadable."""
    return read_declared(document, root, state_root, {"architecture_": architecture, "overview_": overview})


def read_declared(document: dict, root: Path, state_root: Path, readers: dict) -> dict[str, dict]:
    """Read each declared source once through the reader its role prefix names; record present, pending or unreadable."""
    pages = load("build_pages")
    bases = {"repo": Path(root).absolute(), "state": Path(state_root).absolute()}
    results = {}
    for key, entry in document["sources"].items():
        role, base = entry["role"], bases[entry["root"]]
        declared = entry["path"]
        result = {"id": key, "section": entry["section"], "role": role, "root": entry["root"], "declared": declared,
                  "name": PurePosixPath(declared).name, "trigger": entry["trigger"], "status": "pending", "entry": entry}
        path = base / entry["path"]
        if path is not None:
            reader = _reader(readers, role)
            try:
                raw, record = reader.read(role, path, max_bytes=MAX_BYTES)
            except FileNotFoundError:
                raw = None
            if raw is not None:
                relative = path.relative_to(base).as_posix()
                result.update(status="present", path=relative, name=path.name, sha256=record["sha256"], bytes=record["bytes"], raw=raw)
                try:
                    result["content"] = pages.strict_json(raw) if path.suffix == ".json" else raw.decode("utf-8")
                except (ValueError, UnicodeError) as error:
                    result.update(status="unreadable", reason=f"the record does not parse ({type(error).__name__})")
        results[key] = result
    return results


# ---------------------------------------------------------------- markdown
_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_SEPARATOR = re.compile(r":?-{3,}:?")
_ITEM = re.compile(r"^\s*\d+[.)]\s+(.*)$")


def plain(text: str) -> str:
    """Markdown inline text as plain text: links keep their label; emphasis and code marks drop."""
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    return re.sub(r"\*\*|__|`", "", text).strip()


def _cells(line: str) -> list[str]:
    body = line.strip()
    body = body[1:] if body.startswith("|") else body
    body = body[:-1] if body.endswith("|") and not body.endswith("\\|") else body
    return [plain(cell.replace("\\|", "|")) for cell in re.split(r"(?<!\\)\|", body)]


def md_tables(text: str) -> list[dict]:
    """Every pipe table with the heading it sits under."""
    tables, heading, block = [], "", []

    def close():
        if len(block) >= 2 and all(_SEPARATOR.fullmatch(cell.strip()) for cell in _cells(block[1]) if cell.strip()):
            header = _cells(block[0])
            rows = [cells + [""] * (len(header) - len(cells)) for cells in (_cells(line) for line in block[2:])]
            tables.append({"heading": heading, "header": header, "rows": [row[:len(header)] for row in rows]})
        block.clear()

    for line in text.splitlines():
        match = _HEADING.match(line)
        if line.lstrip().startswith("|"):
            block.append(line)
            continue
        close()
        if match:
            heading = plain(match.group(2))
    close()
    return tables


_BULLET = re.compile(r"^(\s*)[-*+]\s+(.*)$")
_BOLD_LEAD = re.compile(r"^\*\*(.+?)\*\*\s*(.*)$")


def md_section(text: str, heading_contains: str) -> tuple[str | None, list[str]]:
    """The first heading whose text contains the key, and its lines up to the next heading."""
    heading, lines, key = None, [], heading_contains.casefold()
    for line in text.splitlines():
        match = _HEADING.match(line)
        if match:
            if heading is not None:
                break
            if key in plain(match.group(2)).casefold():
                heading = plain(match.group(2))
            continue
        if heading is not None:
            lines.append(line)
    return heading, lines


def outline(lines: list[str]) -> dict:
    """Nested bullets as a tree of nodes, each with its text and blocks (a text run or a list of nodes).

    A line indented deeper than a bullet's marker continues that bullet; a line at or left of the
    marker closes it. Blank lines and table lines are skipped; md_tables reads the tables.
    """
    root = {"text": "", "blocks": [], "indent": -1}
    stack = [root]
    for line in lines:
        if not line.strip() or line.lstrip().startswith("|"):
            continue
        indent = len(line) - len(line.lstrip())
        while len(stack) > 1 and indent <= stack[-1]["indent"]:
            stack.pop()
        node, bullet = stack[-1], _BULLET.match(line)
        if bullet:
            child = {"text": bullet.group(2).strip(), "blocks": [], "indent": indent}
            if not node["blocks"] or node["blocks"][-1][0] != "list":
                node["blocks"].append(("list", []))
            node["blocks"][-1][1].append(child)
            stack.append(child)
        elif not node["blocks"]:
            node["text"] = (node["text"] + " " + line.strip()).strip()
        elif node["blocks"][-1][0] == "text":
            node["blocks"][-1] = ("text", node["blocks"][-1][1] + " " + line.strip())
        else:
            node["blocks"].append(("text", line.strip()))
    return root


def _lead(text: str) -> tuple[str | None, str]:
    """An item's opening bold span (its claim) and the text after it."""
    bold = _BOLD_LEAD.match(text.strip())
    return (plain(bold.group(1)).rstrip(":,; ").strip(), bold.group(2)) if bold else (None, text)


def md_points(text: str, heading_contains: str) -> tuple[str | None, list[dict]]:
    """The numbered items under a heading: each with its bold lead, its outline and whether a table sits in it."""
    heading, lines = md_section(text, heading_contains)
    raw: list[dict] = []
    for line in lines:
        item = _ITEM.match(line)
        if item and not line[:1].isspace():
            raw.append({"first": item.group(1), "lines": [], "has_table": False})
        elif raw:
            raw[-1]["lines"].append(line)
            raw[-1]["has_table"] = raw[-1]["has_table"] or line.lstrip().startswith("|")
    points = []
    for item in raw:
        lead, rest = _lead(item["first"])
        points.append({"lead": lead, "tree": outline(([rest] if rest.strip() else []) + item["lines"]), "has_table": item["has_table"]})
    return heading, points


# A projected passage keeps no sentence that cites a path, a digest or a line, or names a declared label.
_PATH = re.compile(r"(?:^|[\s(\"'])~?/[^\s)]+|\b[\w.-]+\.(?:py|md|jsonl?|sh|toml|ya?ml|txt|lock|html|csv|parquet)\b")
_DIGEST = re.compile(r"\b(?=[0-9a-f]*[a-f])(?=[0-9a-f]*\d)[0-9a-f]{7,64}\b")
_LINE_REF = re.compile(r"\b[0-9a-f]{7,64}:\d+|\.[A-Za-z]{1,5}:\d+(?:-\d+)?\b")
_CROSS_REF = re.compile(r"\s*\((?:see )?(?:above|below)\)", re.I)
_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9(\"'$])")


def _terms(drop: list[str]) -> list[re.Pattern]:
    return [re.compile(r"(?<![A-Za-z0-9])" + re.escape(term) + r"(?![A-Za-z])", re.I) for term in drop if isinstance(term, str) and term]


def _withheld(text: str, terms: list[re.Pattern]) -> bool:
    return bool(_PATH.search(text) or _DIGEST.search(text) or _LINE_REF.search(text) or any(term.search(text) for term in terms))


_PAREN = re.compile(r"\s*\(([^()]*)\)")


def _uncited(text: str, terms: list[re.Pattern]) -> str:
    """The text without its parenthesised asides that cite a path, digest or line or name a declared label."""
    previous = None
    while previous != text:
        previous, text = text, _PAREN.sub(lambda match: "" if _withheld(match.group(1), terms) else match.group(0), text)
    return text


def raw_sentences(text: str, drop: list[str] = ()) -> list[str]:
    """The passage's sentences after citation asides are dropped, before any sentence is withheld."""
    terms = _terms(list(drop))
    return [part.strip() for part in _SENTENCE.split(_uncited(plain(_CROSS_REF.sub("", text)), terms)) if part.strip()]


def sentences(text: str, drop: list[str] = ()) -> list[str]:
    """The passage's plain sentences: a citation aside is dropped and the claim kept; a sentence that still cites a
    path, digest or line or names a declared label is withheld."""
    terms = _terms(list(drop))
    parts = (part.strip() for part in _SENTENCE.split(_uncited(plain(_CROSS_REF.sub("", text)), terms)))
    return [part for part in parts if part and not _withheld(part, terms)]


def _clean(text: str | None, terms: list[re.Pattern]) -> str | None:
    """A lead or caption as written; None when it cites a path, digest or line or names a declared label."""
    return text if text and not _withheld(text, terms) else None


def _cell(text: str, drop: list[str]) -> str | None:
    """A table cell's kept sentences; None when the cell has text and none of it is kept."""
    kept = " ".join(sentences(text, drop))
    return kept if kept or not text.strip() else None


def _row(text: str, drop: list[str]) -> str | None:
    """One list row as kept sentences, without a trailing separator; None when nothing is kept."""
    kept = " ".join(sentences(text, drop)).rstrip(";,. ").strip()
    return kept[:1].upper() + kept[1:] if kept else None


def _phrase(text: str | None, key: str) -> bool:
    return bool(text) and bool(re.search(r"(?<![A-Za-z])" + re.escape(key) + r"(?![A-Za-z])", text, re.I))


def _nodes(tree: dict):
    for kind, value in tree["blocks"]:
        if kind == "list":
            for node in value:
                yield node
                yield from _nodes(node)


def _rows(tree: dict, drop: list[str]) -> list[str]:
    """The kept text of the item's top-level list rows."""
    return [row for kind, value in tree["blocks"] if kind == "list" for node in value if (row := _row(node["text"], drop))]


def column_index(header: list[str], column: str) -> int | None:
    """The column named exactly, else the first whose name starts with the key ("Signal (feed we hold)" for "Signal")."""
    names, key = [cell.casefold().strip() for cell in header], column.casefold().strip()
    if key in names:
        return names.index(key)
    return next((index for index, name in enumerate(names) if name.startswith(key)), None)


def table_with_column(text: str, column: str) -> dict | None:
    return next((table for table in md_tables(text) if column_index(table["header"], column) is not None), None)


def table_under(text: str, heading_contains: str) -> dict | None:
    key = heading_contains.casefold()
    return next((table for table in md_tables(text) if key in table["heading"].casefold()), None)


# ---------------------------------------------------------------- sections
def _pointer(document: Any, pointer: str) -> Any:
    value = document
    for part in pointer.strip("/").split("/") if pointer.strip("/") else []:
        if isinstance(value, dict):
            value = value.get(part.replace("~1", "/").replace("~0", "~"))
        elif isinstance(value, list) and part.isdigit() and int(part) < len(value):
            value = value[int(part)]
        else:
            return None
    return value


def _pending(source: dict) -> dict:
    return {"status": source["status"], "name": source["name"], "declared": source["declared"], "root": source["root"],
            "trigger": source["trigger"], "reason": source.get("reason")}


def architecture(sources: dict, root: Path, commit: str | None) -> dict:
    """Both catalogs' layer states from layer_manifest(), the FINAL count and the per-layer register rows."""
    needed = ("final_stack", "foundation_catalog", "trading_catalog", "evidence_matrix")
    absent = [sources[key] for key in needed if sources[key]["status"] != "present" or not isinstance(sources[key].get("content"), dict)]
    if absent:
        return {"status": "pending", "missing": [_pending(source) for source in absent]}
    manifest_module, sanitizer = load("architecture_manifest"), load("sanitization")
    final_stack = sources["final_stack"]["content"]
    catalogs = {"foundation": sources["foundation_catalog"]["content"], "us-equities": sources["trading_catalog"]["content"]}
    bands = []
    for key, config in manifest_module.LAYER_PAGES.items():
        manifest = manifest_module.layer_manifest(root, key, final_stack, catalogs[config["catalog"]], sources["evidence_matrix"]["content"],
                                                  commit=commit, sources=[], flags=None)
        manifest = sanitizer.sanitize(manifest)
        bands.append({"key": key, "label": config["label"], "title": config["title"], "catalog": config["catalog"], "page": config["page"] + ".html",
                      "catalog_path": manifest_module.CATALOGS[config["catalog"]], "states": manifest["summary"]["states"],
                      "finalized": manifest["summary"]["finalized"], "layers": manifest["layers"], "planned": manifest["planned_layers"]})
    total = sum(len(band["layers"]) for band in bands)
    finalized = sum(band["finalized"] for band in bands)
    states = {state: sum(band["states"][state] for band in bands) for state in manifest_module.STATES}
    return {"status": "present", "bands": bands, "total": total, "finalized": finalized, "states": states,
            "checked_at": final_stack.get("checked_at"), "final_stack_status": dict((final_stack.get("summary") or {}).get("status") or {})}


def _finalize_rows(source: dict) -> tuple[dict, dict | None]:
    """Rows of the finalize-all record the source map names, grouped by layer key."""
    if source["status"] != "present":
        return {}, _pending(source)
    entry = source["entry"]
    table = table_with_column(source["content"], entry["table"])
    if table is None:
        return {}, {**_pending(source), "status": "unreadable", "reason": f'the record has no table with a "{entry["table"]}" column'}
    key_index = column_index(table["header"], entry["table"])
    columns = {name: index for name, label in (entry.get("columns") or {}).items() if (index := column_index(table["header"], label)) is not None}
    grouped: dict[str, dict] = {}
    for row in table["rows"]:
        layer = row[key_index].strip()
        if not layer:
            continue
        slot = grouped.setdefault(layer, {name: [] for name in columns})
        for name, index in columns.items():
            value = row[index].strip()
            if value and value not in slot[name]:
                slot[name].append(value)
    return grouped, None


def repos(sources: dict, glance: dict) -> dict:
    """Per layer: computed state, winners at their run pins, survivors and the next action."""
    rows_by_layer, rows_pending = _finalize_rows(sources["finalize_rows"])
    if glance["status"] != "present":
        return {"status": "pending", "missing": glance["missing"], "rows_pending": rows_pending}
    final_stack = sources["final_stack"]["content"]
    runs = {run.get("id"): run for run in final_stack.get("runs") or [] if isinstance(run, dict)}
    records = {(layer.get("catalog"), layer.get("layer_id")): layer for layer in final_stack.get("layers") or [] if isinstance(layer, dict)}
    groups = []
    for band in glance["bands"]:
        rows = []
        listed = [(layer["layer_id"], layer["title"], layer["state"], True) for layer in band["layers"]]
        listed += [(str(row["layer"]).split("/", 1)[-1], row["title"], None, False) for row in band["planned"]]
        for layer_id, title, state, in_catalog in listed:
            record = records.get((band["catalog"], layer_id)) or {}
            key = f'{band["catalog"]}/{layer_id}'
            winners = []
            for winner in record.get("winners") or []:
                if isinstance(winner, dict):
                    run = runs.get(winner.get("run"))
                    winners.append({"component": winner.get("component_id"), "run_pin": run.get("pin") if run else None,
                                    "run_reason": None if run else (winner.get("run_reason") or "unresolved")})
            found = rows_by_layer.get(key) or {}
            rows.append({"layer": key, "title": title, "state": state, "status": record.get("status"), "in_catalog": in_catalog,
                         "page": band["page"], "winners": winners, "survivors": len(record.get("survivors") or []),
                         "next_action": found.get("next_action") or [], "receipt_worker": found.get("receipt_worker") or []})
        # A layer the finalize-all record lists but neither the catalog file nor its planned rows hold (an unswept
        # layer has no verdict yet) is shown with the record's own state, so the three counts reconcile.
        shown = {row["layer"] for row in rows}
        for key in sorted(layer for layer in rows_by_layer if layer.split("/", 1)[0] == band["catalog"] and layer not in shown):
            found = rows_by_layer[key]
            rows.append({"layer": key, "title": key.split("/", 1)[-1], "state": None, "status": "; ".join(found.get("record_state") or []) or None,
                         "in_catalog": False, "rows_only": True, "page": band["page"], "winners": [], "survivors": 0,
                         "next_action": found.get("next_action") or [], "receipt_worker": found.get("receipt_worker") or []})
        groups.append({"label": band["label"], "catalog": band["catalog"], "page": band["page"], "rows": rows})
    source = sources["finalize_rows"]
    counted = {"catalog": sum(1 for group in groups for row in group["rows"] if row["in_catalog"]),
               "planned": sum(1 for group in groups for row in group["rows"] if not row["in_catalog"] and not row.get("rows_only")),
               "rows_only": sum(1 for group in groups for row in group["rows"] if row.get("rows_only"))}
    return {"status": "present", "groups": groups, "rows_pending": rows_pending, "counted": counted,
            "rows_record": source["name"] if source["status"] == "present" else None, "rows_layers": len(rows_by_layer)}


def _statement(sources: dict, key: str | None) -> dict | None:
    """The plain statement a section shows until its named result record exists, or that record by name."""
    if not key:
        return None
    source = sources[key]
    entry = source["entry"]
    if source["status"] == "present":
        return {"status": "present", "label": entry.get("label") or "Result", "name": source["name"], "root": source["root"], "path": source.get("path")}
    return {"status": "pending", "text": entry.get("statement") or "No result yet", "trigger": source["trigger"], "name": source["name"], "root": source["root"],
            "declared": source["declared"]}


def _record(source: dict) -> dict:
    return {"status": "present", "name": source["name"], "root": source["root"], "path": source.get("path")}


def _readiness(text: str, entry: dict) -> str:
    """A scheduled check said as its readiness trigger, never a date: each declared [pattern, trigger] rewrite applies."""
    for pattern, trigger in entry.get("readiness") or []:
        text = re.sub(pattern, trigger, text)
    return text


def addendum(sources: dict, key: str | None, record: dict) -> dict | None:
    """The addendum the source map names, when it belongs to the convergence record shown: each top-level "subject: result" bullet as its subject
    and the kept sentences of it and its nested bullets that name a declared result word, by record name only."""
    if not key:
        return None
    source = sources[key]
    if source["status"] != "present":
        return _pending(source)
    if not source["name"].startswith(PurePosixPath(record["name"]).stem + "."):
        return {**_record(source), "status": "other", "record": record["name"]}
    entry = source["entry"]
    drop, words = entry.get("drop_terms") or [], entry.get("results") or []
    terms = _terms(drop)
    _, lines = md_section(source["content"], entry["under"])
    results = []
    for kind, nodes in outline(lines)["blocks"]:
        for node in nodes if kind == "list" else []:
            label = re.match(r"([^:]{1,80}):\s+(.*)", plain(node["text"]))
            if not label:
                continue
            inner = re.search(r"\(([^()]+)\)\s*$", label.group(1))
            subject = _clean((inner.group(1) if inner else label.group(1)).strip(), terms)
            passages = [_readiness(text, entry) for text in [label.group(2)] + [child["text"] for child in _nodes(node)]]
            kept = [sentence for passage in passages for sentence in sentences(passage, drop) if any(_phrase(sentence, word) for word in words)]
            if subject:
                results.append({"subject": subject[:1].upper() + subject[1:], "sentences": kept})
    return {**_record(source), "results": results}


def feeds(sources: dict) -> dict:
    """The WS2 convergence as a sanitized projection: the $0 early-signal table, the baseline, the lagging or
    conditioning signals, the gated paid rows and the live-stack gaps, by record name only."""
    source = sources["feeds_convergence"]
    if source["status"] != "present":
        return _pending(source)
    entry, text = source["entry"], source["content"]
    drop = entry.get("drop_terms") or []
    terms = _terms(drop)
    heading, points = md_points(text, entry["under"])
    found = next((table for table in md_tables(text) if entry["under"].casefold() in table["heading"].casefold()
                  and column_index(table["header"], entry["table"]) is not None), None)
    # Cells pass the same filter as the list text; a cell with nothing kept is None (withheld).
    table = None if found is None else {**found, "rows": [[_cell(cell, drop) for cell in row] for row in found["rows"]]}
    caption = _clean(next((point["lead"] for point in points if point["has_table"] and point["lead"]), None), terms)
    projected = {}
    for key, phrase in (entry.get("points") or {}).items():
        point = next((point for point in points if _phrase(point["lead"], phrase)), None)
        projected[key] = None if point is None else {"lead": _clean(point["lead"], terms), "sentences": sentences(point["tree"]["text"], drop),
                                                     "rows": _rows(point["tree"], drop)}
    gap_spec = entry.get("gaps") or {}
    gaps = []
    if gap_spec:
        _, lines = md_section(text, gap_spec["under"])
        for node in _nodes(outline(lines)):
            lead, rest = _lead(node["text"])
            if not _phrase(lead, gap_spec["lead"]):
                continue
            name = re.sub(r"^" + re.escape(gap_spec["lead"]) + r"\s*\d*\s*[,:.]?\s*", "", lead, flags=re.I).strip(" .")
            details = sentences(rest, drop)
            if not name and details:
                name, details = details[0].rstrip(". "), details[1:]
            if name and not _withheld(name, terms):
                gaps.append({"name": name[:1].upper() + name[1:], "sentences": details})
    return {**_record(source), "table": table, "caption": caption, "column": entry["table"], "heading": heading, "points": projected,
            "gaps": gaps, "statement": _statement(sources, entry.get("result")), "addendum": addendum(sources, entry.get("addendum"), source)}


def strategies(sources: dict) -> dict:
    """The WS5 convergence as a sanitized projection: the shortlisted family with its evidence caveats, the
    ablation rows and the selector and sizing rule, by record name only."""
    source = sources["strategies_convergence"]
    if source["status"] != "present":
        return _pending(source)
    entry, text = source["entry"], source["content"]
    drop = entry.get("drop_terms") or []
    terms = _terms(drop)
    heading, points = md_points(text, entry["under"])
    family = next((point for point in points if _phrase(point["lead"], entry["family"])), None)
    caveats, withheld = [], 0
    if family is not None:
        passages = [family["tree"]["text"]] + [node["text"] for node in _nodes(family["tree"])]
        # Clause by clause: a citation withholds only its own clause, and a caveat clause that is still withheld is
        # counted, so a filtered projection never reads as a record without caveats.
        for sentence in (sentence for passage in passages for sentence in raw_sentences(passage, drop)):
            for clause in (clause.strip().rstrip(".") for clause in sentence.split("; ")):
                if not clause or not any(_phrase(clause, key) for key in entry.get("caveats") or []):
                    continue
                if _withheld(clause, terms):
                    withheld += 1
                    continue
                clause = clause[:1].upper() + clause[1:] + "."
                if clause not in caveats:
                    caveats.append(clause)
    ablations = None
    for point in points:
        blocks = point["tree"]["blocks"]
        for index, (kind, value) in enumerate(blocks):
            if kind == "text" and _phrase(value, entry["ablations"]) and index + 1 < len(blocks) and blocks[index + 1][0] == "list":
                ablations = {"lead": _clean(point["lead"], terms), "intro": " ".join(sentences(value, drop)),
                             "rows": [row for node in blocks[index + 1][1] if (row := _row(node["text"], drop))]}
                break
        if ablations:
            break
    sizing = next((point for point in points if _phrase(point["lead"], entry["sizing"])), None)
    return {**_record(source), "heading": heading,
            "family": {"lead": _clean(family["lead"], terms), "caveats": caveats, "withheld_caveats": withheld} if family else None,
            "ablations": ablations,
            "sizing": {"lead": _clean(sizing["lead"], terms), "rows": _rows(sizing["tree"], drop)} if sizing else None,
            "selectors": {key: entry.get(key) for key in ("family", "ablations", "sizing")}, "statement": _statement(sources, entry.get("result"))}


def _receipt_date(path: str) -> str | None:
    """The date a registered receipt's path carries: its file name's, else its nearest dated directory's
    (evidence/artifacts/<name>-<date>/receipt.json)."""
    for part in reversed(PurePosixPath(path).parts):
        match = re.search(r"(20\d{2})(\d{2})(\d{2})(?!\d)", part)
        if match:
            return "-".join(match.groups())
    return None


def workers(document: dict, sources: dict, glance: dict) -> list[dict]:
    """Each worker's state and newest receipt from its named sources; no source, no claim."""
    states_by_layer = {f'{band["catalog"]}/{layer["layer_id"]}': layer["state"] for band in glance.get("bands") or [] for layer in band["layers"]}
    result = []
    for worker in document.get("workers", []):
        row = {"name": worker["name"], "role": worker.get("role"), "state": None, "receipt": None}
        binding = worker.get("state")
        if binding is None:
            row["state"] = {"status": "no source", "trigger": worker.get("state_trigger")}
        else:
            source = sources[binding["source"]]
            if source["status"] != "present":
                row["state"] = {**_pending(source), "status": "pending"}
            elif "run" in binding:
                content = source["content"]
                run = next((item for item in content.get("runs") or [] if isinstance(item, dict) and item.get("id") == binding["run"]), None)
                index = ((content.get("index") or {}).get("by_component_id") or {}).get(binding["run"]) or []
                layers = [f'{entry.get("catalog")}/{entry.get("layer_id")}' for entry in index if isinstance(entry, dict) and entry.get("role") == "winner"]
                row["state"] = {"status": "present", "text": f'run pin {run.get("pin")}' if run else "no run pin recorded",
                                "layers": [{"layer": layer, "state": states_by_layer.get(layer)} for layer in layers], "source": source["declared"]}
            else:
                value = _pointer(source["content"], binding["pointer"])
                as_of = _pointer(source["content"], binding["as_of"]) if binding.get("as_of") else None
                row["state"] = ({"status": "present", "text": str(value), "as_of": as_of, "source": source["name"] if source["root"] == "state" else source["declared"],
                                 "root": source["root"]} if isinstance(value, (str, int, float)) and not isinstance(value, bool)
                                else {**_pending(source), "status": "pending", "reason": f'{binding["pointer"]} is absent from the record'})
        binding = worker.get("receipt")
        if binding is None:
            row["receipt"] = {"status": "no source", "trigger": worker.get("receipt_trigger")}
        else:
            source = sources[binding["source"]]
            if source["status"] != "present":
                row["receipt"] = {**_pending(source), "status": "pending"}
            elif "component_id" in binding:
                # Only the declared receipt kinds count (execution receipts, not indexes or inventories).
                kinds = binding.get("kinds")
                matches = [item["path"] for item in source["content"].get("receipts") or []
                           if isinstance(item, dict) and isinstance(item.get("path"), str) and binding["component_id"] in (item.get("component_ids") or [])
                           and (not kinds or item.get("kind") in kinds)]
                newest = max(matches, key=lambda path: (_receipt_date(path) or "", path), default=None)
                kind_text = " of kind " + " or ".join(kinds) if kinds else ""
                row["receipt"] = ({"status": "present", "path": newest, "date": _receipt_date(newest), "count": len(matches), "root": "repo", "kinds": kinds} if newest
                                  else {"status": "none", "reason": f'no receipt{kind_text} registered for {binding["component_id"]}'})
            else:
                as_of = _pointer(source["content"], binding["as_of"]) if binding.get("as_of") else None
                row["receipt"] = {"status": "present", "path": source["path"] if source["root"] == "repo" else source["name"], "date": as_of, "count": 1, "root": source["root"]}
        result.append(row)
    return result


_VERSION = re.compile(r"\b\d+\.\d+\.\d+\b")
_COMMIT = re.compile(r"\b[0-9a-f]{40}\b")


def _short(text: str, limit: int) -> str:
    """The text up to its first clause break, cut at a word boundary within the limit; an ellipsis marks a cut."""
    head = re.split(r":\s|;\s|\s[–—]\s", text, maxsplit=1)[0].strip()
    cut = head != text.strip()
    if len(head) > limit:
        head, cut = head[:limit].rsplit(" ", 1)[0], True
    head = head.rstrip(" ,;:.")
    return head + "…" if cut else head


def client_pin(sources: dict) -> dict:
    """The claude-code run pin in final-stack.json, and the prepared pin, proposed until final-stack.json carries it."""
    prep = sources["cc_floor_prep"]
    stack = sources["final_stack"]
    run_id = prep["entry"].get("run", "claude-code")
    content = stack.get("content") if stack["status"] == "present" else None
    run = next((item for item in (content or {}).get("runs") or [] if isinstance(item, dict) and item.get("id") == run_id), None) if isinstance(content, dict) else None
    current = {"pin": run.get("pin") if run else None, "run": run_id, "path": stack.get("path") or stack["declared"]}
    if prep["status"] != "present":
        return {"current": current, "proposed": _pending(prep)}
    _, lines = md_section(prep["content"], prep["entry"]["under"])
    body = plain(" ".join(lines))
    version, commit = _VERSION.search(body), _COMMIT.search(body)
    pinned = str(current["pin"] or "").split(";")[0].strip()
    return {"current": current, "proposed": {**_record(prep), "version": version.group(0) if version else None,
                                             "commit": commit.group(0) if commit else None, "carried": bool(version) and pinned == version.group(0)}}


def changelog(source: dict) -> dict:
    """Per version heading: the version, entries counted by their opening kind, and at most a few short items."""
    if source["status"] != "present":
        return _pending(source)
    entry = source["entry"]
    kinds, limit, chars = list(entry.get("kinds") or []), int(entry.get("items") or 0), int(entry.get("item_chars") or 90)
    versions, current = [], None
    for line in source["content"].splitlines():
        heading = _HEADING.match(line)
        if heading:
            version = _VERSION.search(heading.group(2))
            current = {"version": version.group(0), "counts": {kind: 0 for kind in kinds}, "other": 0, "entries": []} if version else None
            if current:
                versions.append(current)
            continue
        bullet = _BULLET.match(line)
        if current is None or not bullet or bullet.group(1):
            continue
        text = plain(bullet.group(2))
        kind = next((kind for kind in kinds if text.startswith(kind + " ")), None)
        if kind:
            current["counts"][kind] += 1
        else:
            current["other"] += 1
        current["entries"].append((kind, text))
    for version in versions:
        # The first kinds come first (Added before Fixed), each in record order; an entry naming a path is skipped.
        ordered = sorted((item for item in version.pop("entries") if item[0]), key=lambda item: kinds.index(item[0]))
        version["items"] = [_short(text, chars) for _, text in ordered if not _withheld(text, [])][:limit]
    return {**_record(source), "versions": versions}


def slots(source: dict) -> dict:
    """One compact row per practice slot: id, status, the default's first clause and the client version."""
    if source["status"] != "present":
        return _pending(source)
    content, entry = source["content"], source["entry"]
    if not isinstance(content, dict) or not isinstance(content.get("slots"), list):
        return {**_pending(source), "status": "unreadable", "reason": "the record has no slots list"}
    chars = int(entry.get("default_chars") or 110)
    rows = [{"slot": slot.get("id"), "status": slot.get("status"), "default": _short(plain(str(slot.get("default") or "")), chars),
             "client_version": slot.get("client_version") or content.get("client_version")} for slot in content["slots"] if isinstance(slot, dict)]
    order = list(content.get("status_values") or {})
    counts: dict[str, int] = {}
    for row in sorted(rows, key=lambda row: order.index(row["status"]) if row["status"] in order else len(order)):
        counts[str(row["status"])] = counts.get(str(row["status"]), 0) + 1
    return {"status": "present", "root": "repo", "path": source["path"], "name": source["name"], "rows": rows, "counts": counts,
            "client_version": content.get("client_version"), "checked_at": content.get("checked_at")}


def claude_code(sources: dict) -> dict:
    parts = {"client": client_pin(sources), "changelog": changelog(sources["cc_changelog"]), "slots": slots(sources["cc_slots"])}
    present = parts["client"]["current"]["pin"] or any(parts[key]["status"] == "present" for key in ("changelog", "slots"))
    return {"status": "present" if present else "pending", **parts}


# ---------------------------------------------------------------- finalize-all
def finalize(sources: dict) -> dict:
    """The finalize-all waves with their triggers, the F1 receipt counts by result and the F2 Claude-side counts."""
    plan_source, f1_source, f2_source = sources["finalize_plan"], sources["finalize_f1"], sources["finalize_f2"]
    plan = _pending(plan_source)
    if plan_source["status"] == "present":
        entry, lines = plan_source["entry"], plan_source["content"].splitlines()
        word, drop = entry.get("trigger_word", "Trigger:"), entry.get("drop_terms") or []
        waves = []
        for index, line in enumerate(lines):
            lead = re.match(r"^\*\*(F\d+)\.\s+(.+?)\.?\*\*\s*(.*)$", line)
            if not lead:
                continue
            paragraph = [lead.group(3)]
            for following in lines[index + 1:]:
                if not following.strip() or following.lstrip().startswith(("-", "*", "#")):
                    break
                paragraph.append(following.strip())
            text = " ".join(paragraph)
            after = text.split(word, 1)[1] if word in text else ""
            kept = sentences(after, drop)
            waves.append({"id": lead.group(1), "title": plain(lead.group(2)), "trigger": kept[0] if kept else None})
        plan = {**_record(plan_source), "waves": waves}
    f1 = _pending(f1_source)
    if f1_source["status"] == "present":
        arms = f1_source["content"] if isinstance(f1_source["content"], list) else []
        counts: dict[str, int] = {}
        for arm in (arm for arm in arms if isinstance(arm, dict)):
            # A pass meets the plan only at the exact run pin; a preview assembly or a version-only pin is not that.
            if "success" not in arm:
                result = str(arm.get("state") or "no receipt").replace("-", " ")
            elif arm["success"] is not True:
                result = "failed"
            elif arm.get("assembled") == "preview":
                result = "passed, preview assembly"
            elif arm.get("pin_ok") is True:
                result = "passed at the exact run pin"
            else:
                result = "passed, run pin not yet bound"
            counts[result] = counts.get(result, 0) + 1
        first = ("passed at the exact run pin", "passed, run pin not yet bound", "passed, preview assembly", "failed")
        ordered = {key: counts.pop(key) for key in first if key in counts} | dict(sorted(counts.items()))
        f1 = {**_record(f1_source), "arms": sum(ordered.values()), "counts": ordered}
    f2 = _pending(f2_source)
    if f2_source["status"] == "present":
        text, tables, groups, heading = f2_source["content"], md_tables(f2_source["content"]), [], None
        for line in text.splitlines():
            match = re.match(r"^##\s+(.*)$", line)
            if match:
                heading = plain(match.group(1))
                table = next((table for table in tables if table["heading"] == heading), None)
                groups.append({"label": re.sub(r"\s*\([^()]*\)", "", heading).strip(), "count": len(table["rows"]) if table else 0, "table": bool(table)})
            elif groups and not groups[-1]["table"] and re.match(r"^(?:[-*]\s+)?\*\*", line):
                groups[-1]["count"] += 1
        f2 = {**_record(f2_source), "groups": [{"label": group["label"], "count": group["count"]} for group in groups if group["count"]]}
    return {"plan": plan, "f1": f1, "f2": f2}


# ---------------------------------------------------------------- study provenance
_CLAUDE_MODEL = re.compile(r"\b(Opus|Sonnet|Haiku)\s(\d+(?:\.\d+)?)\b")
_CLAUDE_ID = re.compile(r"\bclaude-(opus|sonnet|haiku)-(\d+)-(\d+)\b")
_GPT_MODEL = re.compile(r"\bgpt-\d[a-z0-9.-]*[a-z0-9]\b", re.I)


def model_family(text: str) -> str | None:
    """The model family and model a route names, or None when it names none."""
    if match := _CLAUDE_MODEL.search(text):
        return f"Claude family ({match.group(1)} {match.group(2)})"
    if match := _CLAUDE_ID.search(text):
        return f"Claude family ({match.group(1).capitalize()} {match.group(2)}.{match.group(3)})"
    if match := _GPT_MODEL.search(text):
        return f"GPT family ({match.group(0)})"
    return None


def study(sources: dict, arms_key: str) -> dict:
    """Who produced a converged study: each research arm's worker and model family, the judges that converged it,
    the record's own claim and the section's statement; private records by name only."""
    arms_source = sources[arms_key]
    entry = arms_source["entry"]
    record_source = sources[entry["study"]]
    result = {"label": entry.get("label") or entry["study"], "record": _record(record_source) if record_source["status"] == "present" else _pending(record_source)}
    if arms_source["status"] == "present":
        columns = entry.get("columns") or {}
        table = table_with_column(arms_source["content"], columns.get("arm", "arm"))
        arms = []
        if table:
            index = {name: column_index(table["header"], label) for name, label in columns.items()}
            for row in table["rows"]:
                cell = lambda name: row[index[name]] if index.get(name) is not None else ""
                if cell("arm").strip():
                    arms.append({"worker": cell("arm").strip(), "model": model_family(cell("route") + " " + cell("notes"))})
        result["arms"] = {**_record(arms_source), "rows": arms}
    else:
        result["arms"] = _pending(arms_source)
    if record_source["status"] == "present":
        text = record_source["content"]
        _, lines = md_section(text, record_source["entry"].get("inputs", "Inputs"))
        judges = []
        for line in lines:
            match = re.match(r"^\s*[-*]\s+([A-Z][A-Za-z]*-family judge)\s*\(([^,;)]+)", plain(line))
            if match:
                judges.append(f"{match.group(1)} ({match.group(2).strip()})")
        claim = next((sentence for sentence in sentences(" ".join(text.split("\n## ", 1)[0].splitlines()[1:])) if re.search(r"\bclaims no\b", sentence)), None)
        # The section's plain statement ("No measured winner yet.") until a named result record exists, then that record.
        statement = _statement(sources, record_source["entry"].get("result"))
        result.update(judges=judges, blind=bool(re.search(r"\bblind judges?\b", text, re.I)), claim=claim,
                      result=None if statement is None else statement["text"] if statement["status"] != "present" else f'{statement["label"]}: {statement["name"]}.')
        addendum_key = record_source["entry"].get("addendum")
        extra = sources.get(addendum_key) if addendum_key else None
        if extra and extra["status"] == "present" and extra["name"].startswith(PurePosixPath(record_source["name"]).stem + "."):
            intro = extra["content"].split("\n- ", 1)[0]
            producer = re.search(r"(\S+)\s+" + re.escape(extra["entry"].get("producer", "measured these")), intro)
            kept = sentences(" ".join(intro.splitlines()[1:]), extra["entry"].get("drop_terms") or [])
            result["addendum"] = {**_record(extra), "producer": producer.group(1) if producer else None,
                                  "model": model_family(intro), "kind": next((sentence for sentence in kept if "author-run" in sentence), None)}
    return result


def github(source: dict) -> dict:
    if source["status"] != "present":
        return _pending(source)
    content, keys = source["content"], source["entry"].get("keys") or {}
    if not isinstance(content, dict) or content.get("schema") != "cc-now/1":
        return {**_pending(source), "status": "unreadable", "reason": "the record is not schema cc-now/1"}
    review = [row for row in content.get(keys.get("in_review", "in_review")) or [] if isinstance(row, dict)]
    queue = [row for row in content.get(keys.get("landing_queue", "landing_queue")) or [] if isinstance(row, str)]
    main_key = keys.get("main_ci", "main_ci")
    main = content.get(main_key)
    return {"status": "present", "name": source["name"], "root": source["root"], "path": source.get("path"), "updated_utc": content.get("updated_utc"),
            "in_review": [{field: row.get(field) for field in ("pr", "head", "state", "next_gate")} for row in review],
            "landing_queue": queue, "main_ci": main, "main_ci_key": main_key}


def evidence(sources: dict, worker_rows: list[dict], glance: dict) -> dict:
    """What the page drew on: repository paths, private records by name only, and the detail pages."""
    repository, private = [], []
    for source in sources.values():
        if source["root"] == "repo":
            repository.append({"path": source.get("path") or source["declared"], "status": source["status"], "section": source["section"]})
        else:
            private.append({"name": source["name"], "status": source["status"], "section": source["section"], "trigger": source["trigger"],
                            "label": source["entry"].get("label") if source["entry"].get("study") else None})
    cited = sorted({row["receipt"]["path"] for row in worker_rows if (row.get("receipt") or {}).get("status") == "present" and row["receipt"].get("root") == "repo"})
    known = {row["path"] for row in repository}
    # A worker's receipt is cited from its registry row; the page never opens the receipt itself.
    repository += [{"path": path, "status": "registered", "section": "workers"} for path in cited if path not in known]
    pages = [{"page": band["page"], "title": band["title"]} for band in glance.get("bands") or []]
    studies = [study(sources, key) for key, source in sources.items() if source["entry"].get("study")]
    return {"repository": repository, "private": private, "pages": pages, "studies": studies}


def model(root: Path, state_root: Path, *, source_map: Path = SOURCE_MAP, policy_path: Path = SOURCE_POLICY_PATH, commit: str | None = None) -> dict:
    document, architecture_reads, overview_reads, map_receipt = load_source_map(root, state_root, source_map=source_map, policy_path=policy_path)
    sources = read_sources(document, root, state_root, architecture_reads, overview_reads)
    if commit is None:
        repo_records = {source["path"]: source["raw"] for source in sources.values() if source["root"] == "repo" and source.get("raw") is not None}
        commit = load("architecture_builder")._commit(Path(root), repo_records) if repo_records else None
    glance = architecture(sources, Path(root), commit)
    worker_rows = workers(document, sources, glance)
    return {"commit": commit, "source_map": map_receipt, "sources": sources, "architecture": glance,
            "feeds": feeds(sources), "strategies": strategies(sources),
            "workers": worker_rows, "repos": {**repos(sources, glance), "finalize": finalize(sources)}, "evidence": evidence(sources, worker_rows, glance),
            "claude_code": claude_code(sources), "github": github(sources["cc_now"]),
            "policy": dict(architecture_reads.policy.receipt)}


def build_overview_page(root: Path, state_root: Path, output_dir: Path, receipt: Path, *, generated: str | None = None,
                        commit: str | None = None, source_map: Path = SOURCE_MAP, policy_path: Path = SOURCE_POLICY_PATH) -> dict:
    """Render overview.html from the source map and publish it with a receipt that lists present and pending sources."""
    pages, policy, view = load("build_pages"), load("source_policy"), load("overview_view")
    output_dir, receipt = pages.no_symlinks(output_dir), pages.no_symlinks(receipt)
    if receipt.is_relative_to(output_dir):
        raise ValueError("overview receipt must remain outside the served root")
    generated = generated or datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    data = model(root, state_root, source_map=source_map, policy_path=policy_path, commit=commit)
    body, counts = view.render(data)
    styles = b"".join(policy._read_regular(path, 1024 * 1024) for path in (HERE / "assets/architecture-manifest.css", STYLE))
    head = "\n  <style>\n" + styles.decode("utf-8") + "  </style>"
    final_stack = data["sources"]["final_stack"]
    present = [source for source in data["sources"].values() if source["status"] == "present"]
    scope = (f'{len(present)} of {len(data["sources"])} declared sources present; committed records at {data["commit"] or "an unrecorded commit"}'
             + (f'; cc-now updated {data["github"]["updated_utc"]}' if data["github"].get("status") == "present" else ""))
    html = pages.document("overview", "Overview", view.LEDE, scope, body, generated, final_stack.get("sha256") or "pending", [], head=head,
                          digest_label="final-stack.json SHA-256")
    outputs = {PAGE: html}
    for name in ("site.css", "site.js"):
        outputs["assets/" + name] = policy._read_regular(HERE / "assets" / name, 8 * 1024 * 1024)
    result = {"schema": SCHEMA, "generated_utc": generated, "commit": data["commit"], "page": PAGE,
              "source_map": data["source_map"], "source_policy": data["policy"],
              "sources": [{key: source.get(key) for key in ("id", "section", "role", "root", "declared", "status", "path", "name", "sha256", "bytes", "matches", "reason", "trigger")}
                          for source in data["sources"].values()],
              "present": sorted(source["id"] for source in present),
              "pending": sorted(source["id"] for source in data["sources"].values() if source["status"] != "present"),
              "counts": counts, "finalized": data["architecture"].get("finalized"), "layers": data["architecture"].get("total"),
              "modules": [{"path": str(HERE / (name + ".py")), "sha256": hashlib.sha256(policy._read_regular(HERE / (name + ".py"), 8 * 1024 * 1024)).hexdigest()}
                          for name in MODULES],
              "style": {"path": str(STYLE), "sha256": hashlib.sha256(policy._read_regular(STYLE, 1024 * 1024)).hexdigest()},
              "outputs": {name: {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)} for name, raw in outputs.items()},
              "limits": ["The page projects named records; it establishes no verdict, E2E, invoke or landing.",
                         "Private state records are shown by name; their digests stay in this nonserved receipt."]}
    pages.publish(output_dir, receipt, outputs, result)
    return result
