#!/usr/bin/env python3
"""Read the overview page's sources through its declarative source map.

overview_sources.json names every source the overview reads: its section,
the source_policy.json role that grants it, its root, one exact path or one
glob, and the trigger that makes it present. Each declaration is checked
against its grant before any file is opened; a glob reads the newest match by
name. A missing source is pending with its trigger, never an error. Layer
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
def load_source_map(root: Path, state_root: Path, *, source_map: Path = SOURCE_MAP, policy_path: Path = SOURCE_POLICY_PATH) -> tuple[dict, Any, Any, dict]:
    """Parse the map and bind every declaration to its exact grant before any source read."""
    policy = load("source_policy")
    raw = policy._read_regular(Path(source_map), 1024 * 1024)
    document = load("build_pages").strict_json(raw)
    if not isinstance(document, dict) or document.get("schema") != MAP_SCHEMA or not isinstance(document.get("sources"), dict):
        raise policy.SourcePolicyError("overview source map must be a local-overview-sources/1 object with a sources map")
    architecture = policy.ArchitectureReads(root, state_root, policy_path=policy_path)
    overview = policy.OverviewReads(root, state_root, policy_path=policy_path)
    for key, entry in document["sources"].items():
        if not isinstance(entry, dict) or entry.get("section") not in SECTIONS or entry.get("root") not in ("repo", "state"):
            raise policy.SourcePolicyError(f"overview source {key} needs a known section and root")
        if not isinstance(entry.get("trigger"), str) or not entry["trigger"].strip() or not isinstance(entry.get("reads"), str):
            raise policy.SourcePolicyError(f"overview source {key} needs what it reads and its readiness trigger")
        role, path, glob = entry.get("role"), entry.get("path"), entry.get("glob")
        if not isinstance(role, str):
            raise policy.SourcePolicyError(f"overview source {key} needs a role")
        if role.startswith("architecture_"):
            if glob is not None or not isinstance(path, str) or (entry["root"], policy._relative(path)) not in architecture.allowed.get(role, set()):
                raise policy.SourcePolicyError("overview source has no exact Architecture grant: " + key)
        else:
            overview.validate(role, entry["root"], path=path, glob=glob)
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
    receipt = {"path": "tools/local-pages/" + Path(source_map).name, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
    return document, architecture, overview, receipt


def read_sources(document: dict, root: Path, state_root: Path, architecture: Any, overview: Any) -> dict[str, dict]:
    """Read each declared source once; record present, pending or unreadable."""
    pages = load("build_pages")
    bases = {"repo": Path(root).absolute(), "state": Path(state_root).absolute()}
    results = {}
    for key, entry in document["sources"].items():
        role, base = entry["role"], bases[entry["root"]]
        declared = entry.get("path") or entry.get("glob")
        result = {"id": key, "section": entry["section"], "role": role, "root": entry["root"], "declared": declared,
                  "name": PurePosixPath(declared).name, "trigger": entry["trigger"], "status": "pending", "entry": entry}
        if entry.get("glob"):
            matches = overview.match(role, entry["root"], entry["glob"])
            path = matches[-1] if matches else None
            result["matches"] = len(matches)
        else:
            path = base / entry["path"]
        if path is not None:
            reader = architecture if role.startswith("architecture_") else overview
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


def md_list(text: str, heading_contains: str, *, lead: bool = False) -> tuple[str | None, list[str]]:
    """The first heading whose text contains the key, and its numbered items up to the next heading.

    With lead, an item that opens with a bold span keeps only that span (the item's claim), and
    its continuation lines are dropped.
    """
    heading, items, inside, key, raw = None, [], False, heading_contains.casefold(), []
    for line in text.splitlines():
        match = _HEADING.match(line)
        if match:
            if inside:
                break
            inside = key in plain(match.group(2)).casefold()
            heading = plain(match.group(2)) if inside else heading
            continue
        if not inside:
            continue
        item = _ITEM.match(line)
        if item:
            raw.append(item.group(1))
            items.append(plain(item.group(1)))
        elif items and line.startswith((" ", "\t")) and line.strip():
            raw[-1] += " " + line.strip()
            items[-1] += " " + plain(line)
    if lead:
        # A lead that introduces its details ("Validation:") drops the trailing colon or comma.
        items = [plain(bold.group(1)).rstrip(":,; ") if (bold := re.match(r"\*\*(.+?)\*\*", source)) else item for source, item in zip(raw, items)]
    return heading, items


def md_items(text: str, heading_contains: str) -> list[str]:
    """Numbered items under the first heading whose text contains the key, up to the next heading."""
    return md_list(text, heading_contains)[1]


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
    """Rows of the newest finalize-all record, grouped by layer key."""
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
        groups.append({"label": band["label"], "catalog": band["catalog"], "page": band["page"], "rows": rows})
    source = sources["finalize_rows"]
    return {"status": "present", "groups": groups, "rows_pending": rows_pending,
            "rows_record": source["name"] if source["status"] == "present" else None, "rows_layers": len(rows_by_layer)}


def convergence(source: dict) -> dict:
    """A command-center convergence record: its table and its next steps, by record name."""
    if source["status"] != "present":
        return _pending(source)
    entry = source["entry"]
    table = table_with_column(source["content"], entry["table"])
    heading, items = md_list(source["content"], entry["list"], lead=bool(entry.get("list_lead"))) if entry.get("list") else (None, [])
    return {"status": "present", "name": source["name"], "root": source["root"], "path": source.get("path"), "table": table, "items": items,
            "column": entry["table"], "list_heading": heading or entry.get("list"), "list_key": entry.get("list")}


def _receipt_date(path: str) -> str | None:
    match = re.search(r"(20\d{2})(\d{2})(\d{2})(?!\d)", PurePosixPath(path).name)
    return "-".join(match.groups()) if match else None


def workers(document: dict, sources: dict, glance: dict) -> list[dict]:
    """Each worker's state and newest receipt from its named sources; no source, no claim."""
    states_by_layer = {f'{band["catalog"]}/{layer["layer_id"]}': layer["state"] for band in glance.get("bands") or [] for layer in band["layers"]}
    result = []
    for worker in document.get("workers", []):
        row = {"name": worker["name"], "role": worker.get("role"), "state": None, "receipt": None}
        binding = worker.get("state")
        if binding is None:
            row["state"] = {"status": "no source"}
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
            row["receipt"] = {"status": "no source"}
        else:
            source = sources[binding["source"]]
            if source["status"] != "present":
                row["receipt"] = {**_pending(source), "status": "pending"}
            elif "component_id" in binding:
                matches = [item["path"] for item in source["content"].get("receipts") or []
                           if isinstance(item, dict) and isinstance(item.get("path"), str) and binding["component_id"] in (item.get("component_ids") or [])]
                newest = max(matches, key=lambda path: (_receipt_date(path) or "", path), default=None)
                row["receipt"] = ({"status": "present", "path": newest, "date": _receipt_date(newest), "count": len(matches), "root": "repo"} if newest
                                  else {"status": "none", "reason": f'no receipt registered for {binding["component_id"]}'})
            else:
                as_of = _pointer(source["content"], binding["as_of"]) if binding.get("as_of") else None
                row["receipt"] = {"status": "present", "path": source["path"] if source["root"] == "repo" else source["name"], "date": as_of, "count": 1, "root": source["root"]}
        result.append(row)
    return result


def claude_code(source: dict) -> dict:
    if source["status"] != "present":
        return _pending(source)
    entry, text = source["entry"], source["content"]
    label = entry["pin_label"].casefold()
    pin = next((match.group(0) for line in text.splitlines() if label in line.casefold()
                for match in [re.search(r"\d+\.\d+\.\d+", line)] if match), None)
    tables = {name: table_under(text, heading) for name, heading in (entry.get("tables") or {}).items()}
    return {"status": "present", "name": source["name"], "root": source["root"], "path": source.get("path"), "pin": pin, "tables": tables,
            "headings": dict(entry.get("tables") or {})}


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
            private.append({"name": source["name"], "status": source["status"], "section": source["section"], "trigger": source["trigger"]})
    cited = sorted({row["receipt"]["path"] for row in worker_rows if (row.get("receipt") or {}).get("status") == "present" and row["receipt"].get("root") == "repo"})
    known = {row["path"] for row in repository}
    repository += [{"path": path, "status": "present", "section": "workers"} for path in cited if path not in known]
    pages = [{"page": band["page"], "title": band["title"]} for band in glance.get("bands") or []]
    return {"repository": repository, "private": private, "pages": pages}


def model(root: Path, state_root: Path, *, source_map: Path = SOURCE_MAP, policy_path: Path = SOURCE_POLICY_PATH, commit: str | None = None) -> dict:
    document, architecture_reads, overview_reads, map_receipt = load_source_map(root, state_root, source_map=source_map, policy_path=policy_path)
    sources = read_sources(document, root, state_root, architecture_reads, overview_reads)
    if commit is None:
        repo_records = {source["path"]: source["raw"] for source in sources.values() if source["root"] == "repo" and source.get("raw") is not None}
        commit = load("architecture_builder")._commit(Path(root), repo_records) if repo_records else None
    glance = architecture(sources, Path(root), commit)
    worker_rows = workers(document, sources, glance)
    return {"commit": commit, "source_map": map_receipt, "sources": sources, "architecture": glance,
            "feeds": convergence(sources["feeds_convergence"]), "strategies": convergence(sources["strategies_convergence"]),
            "workers": worker_rows, "repos": repos(sources, glance), "evidence": evidence(sources, worker_rows, glance),
            "claude_code": claude_code(sources["claude_code_practice"]), "github": github(sources["cc_now"]),
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
