#!/usr/bin/env python3
"""Join the recorded verdicts, sweeps and run pins into one per-layer final-stack manifest,
``catalogs/landscape/final-stack.json``.

This never selects a winner, runs a lane or reads anything outside the repository root. It joins what the
landscape catalogs named by ``catalogs/landscape/manifest.json#/catalogs`` and
``catalogs/landscape/planned-layers.json``, the committed ``catalogs/landscape/component-evidence-matrix.json``,
the completed sweeps of ``catalogs/saturation/ledger.json`` (and its report in ``scripts/saturation_ledger.py``),
``catalogs/landscape/research-state.json``, ``catalogs/landscape/skills-lifecycle.json``, the verdict-wave
registry, the newest landscape-sweep seeds file and the run-pin sources (an allowlisted lockfile, the adoption pin
files, ``manifests/stack.json`` and ``catalogs/us-equities/runtime-target.json#/engine``) already say. The output is
deterministic: sorted keys and no clock. ``checked_at`` is the schema date; staleness is computed only at check
time, from ``--today``.

Modes: ``--check`` (default) rebuilds the document in memory and exits 1 when the committed file differs, a
recorded source hash changed, a landscape, research-state or matrix layer does not have exactly one row, a planned
layer collides with a landscape row, the document is internally inconsistent or private content appears.
Winners without a run pin, pin drift and, with ``--today``, verdicts past ``next_review`` are printed as flags and
exit 0 in v1. ``--write`` rebuilds, writes and registers the file in ``manifests/evidence.json``.

W1b reads the document through ``is_definitive(doc, ident, today)`` and ``run_pin(doc, ident)``.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile
import tomllib

try:
    from . import component_matrix, host_receipts, host_name_scan, saturation_ledger
    from .catalog_decisions import InvalidDecisionIndex, safe_file, unique_json
    from .sweep_policy import DEFAULT_SWEEP_CADENCE_DAYS
except ImportError:  # running as a plain script, not a package
    import component_matrix
    import host_receipts
    import host_name_scan
    import saturation_ledger
    from catalog_decisions import InvalidDecisionIndex, safe_file, unique_json
    from sweep_policy import DEFAULT_SWEEP_CADENCE_DAYS

ROOT = Path(__file__).resolve().parents[1]
TOOL_DIR = ROOT / "tools" / "sota-convergence"
if str(TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(TOOL_DIR))
# The verdict tools own the wave rule (a row's lanes.sealed_base, else the 2026-09-22 wave) and the registry path.
from build_verdicts import WAVE_REGISTRY, row_run_id  # noqa: E402


# The date the scope and the JSON schema below were last checked (the W4 design, 2026-10-11). It is never a build
# date: the generator reads no clock, and only --check --today evaluates staleness.
CHECKED_AT = "2026-10-11"
SCHEMA_VERSION = 1
SCOPE = (
    "One row per layer of the final stack: the landscape verdict rows and the planned layers, each with its status, "
    "verdict wave and next review, winners with their verdict and run pins, alternates, unadjudicated sweep "
    "survivors, open gaps, research state, saturation and the found-to-adopted funnel; the run pins; the intake; and "
    "a repository and component index. A read-only join of evidence recorded elsewhere; it selects nothing."
)
OUTPUT = "catalogs/landscape/final-stack.json"
LANDSCAPE_MANIFEST = "catalogs/landscape/manifest.json"
PLANNED_LAYERS = "catalogs/landscape/planned-layers.json"
RESEARCH_STATE = saturation_ledger.RESEARCH_STATE
SKILLS_CATALOG = saturation_ledger.SKILLS_CATALOG
SKILLS = saturation_ledger.SKILLS
MATRIX = component_matrix.OUTPUT_JSON
LEDGER = saturation_ledger.LEDGER
ADOPTION = saturation_ledger.ADOPTION
SEEDS_DIR = "tools/sota-convergence/landscape-sweep"
SEEDS_NAME = re.compile(r"seeds-(\d{4})(\d{2})(\d{2})\.json")
STARS_FILE = "catalogs/convergence-practice/starred-seeds-20261010.json"
GRAND_COUNTS_FILE = "catalogs/landscape/grand-catalog-counts.json"
# Import the shared policy without pulling currency_due's host-oriented closure into this generator.
REVIEW_DAYS = DEFAULT_SWEEP_CADENCE_DAYS

# First matching rule wins (see DEFINITIONS); this is also the order of the summary counts.
STATUS_ORDER = ("unswept", "no-winner", "reopened", "converged", "current")
DEFINITIVE_STATUSES = ("current", "converged")
RUN_REASONS = ("unpinned", "held", "external", "unresolved")
ROLES = ("winner", "alternate", "survivor", "candidate")
PIN_DRIFT_VALUES = ("same", "differs", "unknown")
# Reason codes of is_definitive, closest to definitive first.
NOT_DEFINITIVE_REASONS = ("stale", "reopened", "no-winner", "unswept", "not-winner", "untracked")
# A verdict that was recorded (a winner set or an explicit no selection) is reviewed; pending lanes have none yet.
REVIEWED_VERDICTS = ("recorded", "no_selection")
# Landscape rows that count as trialled until W5's comparison ledger exists: measured_comparison evidence
# (scripts/landscape.py WINNER_EVIDENCE_CLASSES, EVIDENCE_KINDS) or a measured_tradeoff disposition.
MEASURED_EVIDENCE = (("evidence_class", "measured_comparison"), ("evidence_kind", "measured_comparison"),
                     ("disposition", "measured_tradeoff"))

# Run-pin sources, highest precedence first. A component is the normalized repository (or, without one, its id).
LOCKFILE = "blueprints/us-equities/runtime-2604/trading-2604-runtime/uv.lock"
PIN_FILES = (("linux-x86_64", "adoption/pins-linux-x86_64.json"), ("macos-arm64", "adoption/pins-macos-arm64.json"))
STACK = component_matrix.STACK_FILE
RUNTIME_TARGET = "catalogs/us-equities/runtime-target.json"
RUNTIME_ENGINE_POINTER = "/engine"
RUN_PIN_SOURCES_TEXT = (f"the allowlisted lockfile {LOCKFILE} (its root package's direct requirements), "
                        + ", ".join(path for _platform, path in PIN_FILES)
                        + f" tools[].version, {STACK} version/source_pin and {RUNTIME_TARGET}#{RUNTIME_ENGINE_POINTER}")
# The lockfile records no repository. A requirement whose name is a manifests/stack.json id takes that component's
# repository; these are the repositories of the other requirements that a landscape winner records for the same
# package (catalogs/landscape/us-equities.json data-mlflow and data-pandera).
LOCKFILE_REPOSITORIES = {
    "mlflow": "https://github.com/mlflow/mlflow",
    "pandera": "https://github.com/unionai-oss/pandera",
}
# Winners whose only run pin lives in the private trading repository: component_id -> the record that says so.
# No file in this repository declares one yet, so v1 reports such winners as unresolved.
EXTERNAL_RUN_PINS: dict[str, str] = {}

# Free-text pins parse only in these exact forms; anything else is flagged, never guessed. A leading "v" is the
# tag spelling of the version (scripts/host_receipts.py normalize_pin drops it the same way).
VERSION = r"v?(?P<version>\d+(?:\.\d+)+(?:[A-Za-z][0-9A-Za-z]*)?(?:[-.+~][0-9A-Za-z]+)*)"
COMMIT = r"(?P<commit>[0-9a-f]{40})"
COMMIT_PATTERN = re.compile(COMMIT)
PIN_FORMS = tuple(re.compile(form) for form in (
    VERSION, COMMIT, VERSION + " @ " + COMMIT, VERSION + "; source " + COMMIT))
UNPINNED = "unpinned"
PIN_FORMS_TEXT = "<version>, <commit>, <version> @ <commit> and <version>; source <commit> (a 40-hex commit)"

DEFINITIONS = (
    ("status",
     "First rule that matches, in this order: unswept (no completed sweep in " + LEDGER + " covers the layer); "
     "no-winner (the verdict is pending_lanes or no_selection, or there are no winners); reopened (a completed sweep "
     "covering the layer is dated after the verdict's checked_at, component_matrix layer_state recorded_reopened); "
     "converged (layer_state confirmed_current and the matrix converged count equals its in_use count, which is "
     "above 0); current (otherwise)."),
    ("verdict.next_review",
     "The verdict's checked_at plus policy.review_days, for a recorded or no_selection verdict; null for pending "
     "lanes and planned layers. It is a date, never a staleness: --check --today D flags a layer when D is past it."),
    ("winners[].pin_parsed",
     "The verdict pin parsed in one of the forms " + PIN_FORMS_TEXT + "; otherwise pin_parse is unpinned (the text "
     "'unpinned') or unparsed. Free text is flagged, never guessed."),
    ("runs",
     "One entry per component a run-pin source pins, keyed by normalized repository (or by id without one). "
     "Precedence: " + RUN_PIN_SOURCES_TEXT + "; the first source is the run pin and every other source whose parsed "
     "pin differs is listed under conflicts. platforms lists the adoption pin files that install the same pin."),
    ("winners[].run",
     "The runs[] id whose repository is the winner's (a run without a repository joins only by the same id), or "
     "null with run_reason held (the layer's current_adoption_status is held), external (scripts/final_stack.py "
     "EXTERNAL_RUN_PINS), unpinned (the verdict pin is 'unpinned') or unresolved."),
    ("winners[].pin_drift",
     "same when the verdict and run pins share a parsed field (version with version, commit with commit) and every "
     "shared field matches (scripts/host_receipts.py pin_matches); differs when one does not; unknown when they "
     "share none, including an unpinned or unparsed pin; null without a run."),
    ("funnel",
     "Cumulative distinct normalized repositories over the completed sweeps (stopped sweeps excluded). found: ledger "
     "proposed plus the landscape candidates, alternatives and winners; refuted: the latest ledger appearance is in "
     "refuted; surviving: the latest appearance is in survived, dated after the verdict; trialled: landscape rows "
     "with measured_comparison evidence or a measured_tradeoff disposition; adopted: winners with a run pin."),
    ("survivors", "The surviving repositories of the funnel, each with the sweep and date of its latest survival."),
    ("index",
     "by_repository (normalized) and by_component_id (winners) map to every layer and role (winner, alternate, "
     "survivor, candidate) that names them."),
)


class FinalStackError(ValueError):
    """An input that cannot be joined one-to-one, or a document that is internally inconsistent."""


# --------------------------------------------------------------------------- loading


class Sources:
    """Reads repository files through catalog_decisions.safe_file and records each one's sha256."""

    def __init__(self, root: Path):
        self.root = root
        self.hashes: dict[str, str] = {}

    def path(self, relative: str) -> Path:
        try:
            return safe_file(self.root, relative)
        except InvalidDecisionIndex as error:
            raise FinalStackError(f"{relative}: {error}") from error

    def read_bytes(self, relative: str) -> bytes:
        path = self.path(relative)
        if not path.is_file():
            raise FinalStackError(f"{relative} is missing")
        raw = path.read_bytes()
        self.hashes[relative] = hashlib.sha256(raw).hexdigest()
        return raw

    def json(self, relative: str):
        raw = self.read_bytes(relative)
        try:
            return json.loads(raw.decode("utf-8"), object_pairs_hook=unique_json)
        except (UnicodeError, ValueError) as error:
            raise FinalStackError(f"{relative}: cannot read JSON ({error})") from error

    def toml(self, relative: str) -> dict:
        raw = self.read_bytes(relative)
        try:
            return tomllib.loads(raw.decode("utf-8"))
        except (UnicodeError, ValueError) as error:
            raise FinalStackError(f"{relative}: cannot read TOML ({error})") from error


def _dicts(value) -> list[dict]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def layer_key(catalog: str, layer_id: str) -> str:
    return f"{catalog}/{layer_id}"


def landscape_rows(sources: Sources) -> dict[tuple[str, str], dict]:
    """(catalog, layer_id) -> {"row", "source"} for every layer of the catalogs manifest.json names; a layer named
    twice is an error."""
    manifest = sources.json(LANDSCAPE_MANIFEST)
    catalogs = manifest.get("catalogs") if isinstance(manifest, dict) else None
    if not isinstance(catalogs, dict) or not catalogs:
        raise FinalStackError(f"{LANDSCAPE_MANIFEST}: catalogs must name the landscape catalog files")
    rows: dict[tuple[str, str], dict] = {}
    for catalog, relative in sorted(catalogs.items()):
        document = sources.json(relative)
        layers = document.get("layers") if isinstance(document, dict) else None
        if not isinstance(layers, list):
            raise FinalStackError(f"{relative}: layers must be a list")
        for index, row in enumerate(layers):
            if not isinstance(row, dict) or not isinstance(row.get("layer_id"), str):
                raise FinalStackError(f"{relative}: layers[{index}] needs a layer_id")
            key = (catalog, row["layer_id"])
            if key in rows:
                raise FinalStackError(f"{layer_key(*key)} has more than one landscape row; each layer needs exactly one")
            rows[key] = {"row": row, "source": f"{relative}#/layers/{index}"}
    return rows


def planned_rows(sources: Sources, landscape: dict) -> dict[tuple[str, str], dict]:
    document = sources.json(PLANNED_LAYERS)
    layers = document.get("layers") if isinstance(document, dict) else None
    if not isinstance(layers, list):
        raise FinalStackError(f"{PLANNED_LAYERS}: layers must be a list")
    rows: dict[tuple[str, str], dict] = {}
    for index, row in enumerate(layers):
        if not isinstance(row, dict) or not isinstance(row.get("catalog"), str) or not isinstance(row.get("layer_id"), str):
            raise FinalStackError(f"{PLANNED_LAYERS}: layers[{index}] needs a catalog and a layer_id")
        key = (row["catalog"], row["layer_id"])
        if key in landscape:
            raise FinalStackError(f"planned layer {layer_key(*key)} collides with the landscape row "
                                  f"{landscape[key]['source']}; remove it from {PLANNED_LAYERS}")
        if key in rows:
            raise FinalStackError(f"planned layer {layer_key(*key)} is listed more than once")
        rows[key] = {"row": row, "source": f"{PLANNED_LAYERS}#/layers/{index}"}
    return rows


def one_row_each(name: str, rows, landscape: dict) -> dict[tuple[str, str], dict]:
    """(catalog, layer_id) -> the one row of ``rows`` for each landscape layer. A landscape layer with no row or
    several rows, or a row with no landscape layer, is an error."""
    by_key: dict[tuple[str, str], list[dict]] = {}
    for row in _dicts(rows):
        by_key.setdefault((row.get("catalog"), row.get("layer_id")), []).append(row)
    problems = [f"{name} has {len(by_key.get(key, []))} rows for {layer_key(*key)}; it needs exactly one"
                for key in sorted(landscape) if len(by_key.get(key, [])) != 1]
    problems += [f"{name} row {key[0]}/{key[1]} has no landscape row"
                 for key in sorted(by_key, key=lambda item: (str(item[0]), str(item[1]))) if key not in landscape]
    if problems:
        raise FinalStackError("; ".join(problems))
    return {key: by_key[key][0] for key in landscape}


def wave_registry(sources: Sources) -> dict[str, dict]:
    document = sources.json(WAVE_REGISTRY)
    return {wave["run_id"]: wave for wave in _dicts(document.get("waves") if isinstance(document, dict) else None)
            if isinstance(wave.get("run_id"), str)}


# --------------------------------------------------------------------------- pins


def parse_pin(text) -> dict:
    """{"pin_parsed": {"version", "commit"}} for a pin in one of PIN_FORMS, else {"pin_parse": "unpinned"} for the
    text 'unpinned' or {"pin_parse": "unparsed"}."""
    if text == UNPINNED:
        return {"pin_parse": UNPINNED}
    if isinstance(text, str):
        for form in PIN_FORMS:
            match = form.fullmatch(text)
            if match:
                groups = match.groupdict()
                return {"pin_parsed": {"version": groups.get("version"), "commit": groups.get("commit")}}
    return {"pin_parse": "unparsed"}


def record_pin(text, commit=None) -> dict:
    """parse_pin(text) with a separately recorded commit field (a 40-hex source_pin or commit) merged in. A commit
    that contradicts the one in the text leaves the pin unparsed."""
    parsed = parse_pin(text)
    if isinstance(commit, str) and COMMIT_PATTERN.fullmatch(commit):
        current = parsed.get("pin_parsed")
        if current is None:
            return {"pin_parsed": {"version": None, "commit": commit}}
        if current["commit"] is None:
            return {"pin_parsed": {**current, "commit": commit}}
        if current["commit"] != commit:
            return {"pin_parse": "unparsed"}
    return parsed


def compare_pins(left: dict, right: dict) -> str:
    """same, differs or unknown (PIN_DRIFT_VALUES) for two parse results."""
    left, right = left.get("pin_parsed"), right.get("pin_parsed")
    if not left or not right:
        return "unknown"
    results = [host_receipts.pin_matches(left[field], right[field]) for field in ("version", "commit")
               if left.get(field) and right.get(field)]
    if not results:
        return "unknown"
    return "same" if all(results) else "differs"


def canonical_package(name: str) -> str:
    """The PEP 503 normalized form of a Python package name."""
    return re.sub(r"[-_.]+", "-", name).lower()


def github_repository(url) -> str | None:
    return (host_receipts.normalize_repository(url)
            if isinstance(url, str) and host_receipts.GITHUB_REPOSITORY_PATTERN.match(url.strip().lower()) else None)


def run_records(sources: Sources) -> list[dict]:
    """Every run-pin record, in precedence order: rank, then platform order, then position in its source."""
    stack = sources.json(STACK)
    stack_components = _dicts(stack.get("components") if isinstance(stack, dict) else None)
    stack_repository = {component["id"]: host_receipts.normalize_repository(component.get("repository"))
                        for component in stack_components if isinstance(component.get("id"), str)}
    records = []

    lock = sources.toml(LOCKFILE)
    packages = _dicts(lock.get("package"))
    # uv 0.12.17 (635500036e1705961315e86447f0fab0a8ddb309),
    # crates/uv-lock/src/lock/mod.rs:3600-3607: editable/virtual roots have the empty
    # workspace-relative path, serialized as "." in uv.lock; a child path is not the root.
    roots = [package for package in packages if isinstance(package.get("source"), dict)
             and any(package["source"].get(kind) == "." for kind in ("virtual", "editable"))]
    if len(roots) != 1:
        raise FinalStackError(f"{LOCKFILE}: expected one root package, found {len(roots)}")
    requirements = sorted({canonical_package(requirement["name"])
                           for requirement in _dicts((roots[0].get("metadata") or {}).get("requires-dist"))
                           if isinstance(requirement.get("name"), str)})
    for name in requirements:
        matches = [(index, package) for index, package in enumerate(packages)
                   if isinstance(package.get("name"), str) and canonical_package(package["name"]) == name]
        if len(matches) != 1:
            raise FinalStackError(f"{LOCKFILE}: {len(matches)} package entries for requirement {name}")
        index, package = matches[0]
        repository = stack_repository.get(name) or host_receipts.normalize_repository(LOCKFILE_REPOSITORIES.get(name))
        records.append({"rank": 0, "id": name, "repository": repository, "pin": package.get("version"),
                        "parsed": record_pin(package.get("version")), "source": f"{LOCKFILE}#/package/{index}",
                        "platform": None})

    for platform_order, (platform, relative) in enumerate(PIN_FILES):
        document = sources.json(relative)
        for index, tool in enumerate(document.get("tools") if isinstance(document, dict) else []):
            if not isinstance(tool, dict) or not isinstance(tool.get("id"), str):
                raise FinalStackError(f"{relative}: tools[{index}] needs an id")
            repository = stack_repository.get(tool["id"]) or github_repository(tool.get("url"))
            records.append({"rank": 1 + platform_order, "id": tool["id"], "repository": repository,
                            "pin": tool.get("version"), "parsed": record_pin(tool.get("version"), tool.get("commit")),
                            "source": f"{relative}#/tools/{index}", "platform": platform})

    for index, component in enumerate(stack_components):
        if not isinstance(component.get("id"), str):
            raise FinalStackError(f"{STACK}: components[{index}] needs an id")
        records.append({"rank": 1 + len(PIN_FILES), "id": component["id"],
                        "repository": stack_repository[component["id"]], "pin": component.get("version"),
                        "parsed": record_pin(component.get("version"), component.get("source_pin")),
                        "source": f"{STACK}#/components/{index}", "platform": None})

    runtime = sources.json(RUNTIME_TARGET)
    engine = runtime.get("engine") if isinstance(runtime, dict) else None
    if not isinstance(engine, dict):
        raise FinalStackError(f"{RUNTIME_TARGET}#{RUNTIME_ENGINE_POINTER} must be an object")
    # Only the repository, version and commit are copied: the record also carries host and environment detail.
    repository = host_receipts.normalize_repository(engine.get("repository"))
    records.append({"rank": 2 + len(PIN_FILES), "id": (repository or "engine").rsplit("/", 1)[-1],
                    "repository": repository, "pin": engine.get("requested_version"),
                    "parsed": record_pin(engine.get("requested_version"), engine.get("source_commit")),
                    "source": f"{RUNTIME_TARGET}#{RUNTIME_ENGINE_POINTER}", "platform": None})
    return records


def build_runs(records: list[dict]) -> list[dict]:
    """One runs[] entry per component; its id is the manifests/stack.json id when the stack lists it."""
    groups: dict[str, list[dict]] = {}
    for record in records:
        groups.setdefault(record["repository"] or "id:" + record["id"], []).append(record)
    stack_rank = 1 + len(PIN_FILES)
    runs, ids = [], set()
    for members in groups.values():
        members.sort(key=lambda record: record["rank"])
        chosen = members[0]
        stack_ids = [record["id"] for record in members if record["rank"] == stack_rank]
        run_id = stack_ids[0] if stack_ids else chosen["id"]
        if run_id in ids:
            raise FinalStackError(f"run id {run_id} names two components; give one of them a repository")
        ids.add(run_id)
        platforms = sorted({record["platform"] for record in members if record["platform"] is not None
                            and (record is chosen or record["pin"] == chosen["pin"]
                                 or compare_pins(record["parsed"], chosen["parsed"]) == "same")})
        runs.append({
            "id": run_id,
            "repository": chosen["repository"],
            "pin": chosen["pin"],
            **chosen["parsed"],
            "source": chosen["source"],
            "platforms": platforms,
            "conflicts": [{"source": record["source"], "pin": record["pin"]} for record in members[1:]
                          if compare_pins(record["parsed"], chosen["parsed"]) == "differs"],
        })
    return sorted(runs, key=lambda run: run["id"])


# --------------------------------------------------------------------------- sweeps


def completed_sweeps(ledger: dict) -> list[dict]:
    """The completed sweeps (component_matrix.completed_sweeps, which validates them), each with its raw record."""
    ordered = component_matrix.completed_sweeps(ledger)
    raw = [sweep for sweep in ledger["sweeps"] if sweep.get("status") == component_matrix.COMPLETED_SWEEP]
    # The same stable sort key as component_matrix.completed_sweeps, so both lists are in the same order.
    raw.sort(key=lambda sweep: (component_matrix.parse_iso_date(sweep["date"]),
                                sweep["sweep_id"] if isinstance(sweep.get("sweep_id"), str) else ""))
    for sweep, record in zip(ordered, raw, strict=True):
        sweep["record"] = record
    return ordered


def sweep_outcomes(sweeps: list[dict]) -> dict[tuple[str, str], dict]:
    """(catalog, layer_id) -> {"proposed": set, "latest": {repository: (outcome, sweep_id, date)}} over the completed
    sweeps in date order; within one sweep a refutation is later than a survival."""
    outcomes: dict[tuple[str, str], dict] = {}
    for sweep in sweeps:
        for position, layer in enumerate(sweep["record"]["layers"]):
            where = f"{LEDGER}: {sweep['sweep_id']}: layers[{position}]"
            entry = outcomes.setdefault((layer["catalog"], layer["layer_id"]), {"proposed": set(), "latest": {}})
            proposed = layer.get("proposed") or []
            if not isinstance(proposed, list) or not all(isinstance(item, str) for item in proposed):
                raise FinalStackError(where + ": proposed must be a list of repositories")
            entry["proposed"].update(filter(None, map(host_receipts.normalize_repository, proposed)))
            for outcome in ("survived", "refuted"):
                items = layer.get(outcome) or []
                if not isinstance(items, list) or not all(isinstance(item, dict) and isinstance(item.get("repo"), str)
                                                          for item in items):
                    raise FinalStackError(f"{where}: {outcome} must be a list of objects with a repo")
                for item in items:
                    repository = host_receipts.normalize_repository(item["repo"])
                    if repository is not None:
                        entry["latest"][repository] = (outcome, sweep["sweep_id"], sweep["date"])
    return outcomes


def trialled_repositories(row: dict) -> set[str]:
    found = set()
    for role in ("winners", "alternatives", "candidates"):
        for entry in _dicts(row.get(role)):
            if any(entry.get(field) == value for field, value in MEASURED_EVIDENCE):
                repository = host_receipts.normalize_repository(entry.get("repository"))
                if repository is not None:
                    found.add(repository)
    return found


# --------------------------------------------------------------------------- layers


def build_verdict(row: dict, matrix_row: dict, registry: dict, reopened_by: list[dict]) -> dict:
    verdict_day = component_matrix.parse_iso_date(row.get("checked_at"))
    wave = row_run_id(row)
    registered = registry.get(wave)
    reviewed = row.get("verdict_status") in REVIEWED_VERDICTS and verdict_day is not None
    return {
        "status": row.get("verdict_status"),
        "wave": wave,
        "date": verdict_day.isoformat() if verdict_day else None,
        "wave_doc": {"path": registered.get("path"), "sha256": registered.get("sha256")} if registered else None,
        "agreement": (row.get("lanes") or {}).get("agreement"),
        "adjudication_ref": matrix_row.get("adjudication_ref"),
        "reopened_by": reopened_by,
        "comparison_id": None,
        "next_review": (verdict_day + timedelta(days=REVIEW_DAYS)).isoformat() if reviewed else None,
    }


def build_winner(winner: dict, matrix_row: dict, runs_by_repository: dict, runs_by_id: dict, held: bool) -> dict:
    component_id = winner.get("component_id")
    parsed = parse_pin(winner.get("pin"))
    repository = host_receipts.normalize_repository(winner.get("repository"))
    run = runs_by_repository.get(repository) if repository else None
    if run is None and (runs_by_id.get(component_id) or {}).get("repository", "") is None:
        run = runs_by_id[component_id]  # a run without a repository joins only by the same id
    if run is not None:
        reason = None
    elif held:
        reason = "held"
    elif component_id in EXTERNAL_RUN_PINS:
        reason = "external"
    elif parsed.get("pin_parse") == UNPINNED:
        reason = "unpinned"
    else:
        reason = "unresolved"
    factors = [{"id": component.get("id"), **{factor: component.get(factor) for factor in
                                             (*component_matrix.CONVERGENCE_FACTORS, "converged")}}
               for component in _dicts((matrix_row.get("convergence") or {}).get("components"))
               if component_id in (component.get("winner_ids") or [])]
    return {
        "component_id": component_id,
        "repository": winner.get("repository"),
        "verdict_pin": winner.get("pin"),
        **parsed,
        "evidence_class": winner.get("evidence_class"),
        "factors": sorted(factors, key=lambda factor: str(factor["id"])),
        "run": run["id"] if run else None,
        "run_reason": reason,
        "pin_drift": compare_pins(parsed, run) if run else None,
    }


def layer_status(covered: bool, state: str | None, convergence: dict) -> str:
    """STATUS_ORDER, first rule that matches."""
    if not covered:
        return "unswept"
    if state is None or state in ("pending_lanes", "no_selection"):
        return "no-winner"
    if state == "recorded_reopened":
        return "reopened"
    in_use, converged = convergence.get("in_use"), convergence.get("converged")
    if isinstance(in_use, int) and in_use > 0 and converged == in_use:
        return "converged"
    return "current"


def build_document(root: Path) -> dict:
    sources = Sources(root)
    landscape = landscape_rows(sources)
    planned = planned_rows(sources, landscape)
    research_state, matrix, skills, ledger = (sources.json(relative)
                                             for relative in (RESEARCH_STATE, MATRIX, SKILLS_CATALOG, LEDGER))
    for relative, value in ((RESEARCH_STATE, research_state), (MATRIX, matrix), (SKILLS_CATALOG, skills),
                            (LEDGER, ledger)):
        if not isinstance(value, dict):
            raise FinalStackError(f"{relative} must be an object")
    research = one_row_each(RESEARCH_STATE, research_state.get("layers"), landscape)
    matrix_rows = one_row_each(MATRIX, matrix.get("rows"), landscape)
    sweeps = completed_sweeps(ledger)
    outcomes = sweep_outcomes(sweeps)
    registry = wave_registry(sources)
    # saturation_ledger.build_report reads these itself; they are recorded so a change to them is a source change.
    sources.read_bytes(ADOPTION)
    manifest_ref = saturation_ledger.latest_manifest_ref(ledger)
    if manifest_ref:
        sources.read_bytes(manifest_ref)
    try:
        report = saturation_ledger.build_report(root, ledger)
    except (saturation_ledger.LedgerError, OSError, ValueError) as error:
        raise FinalStackError(f"saturation report: {error}") from error
    saturation = {(layer["catalog"], layer["layer_id"]): {
        "clean_count": layer["clean_count"], "saturation_candidate": layer["saturation_candidate"],
        "last_sweep": layer["last_sweep"]} for layer in report["layers"]}

    runs = build_runs(run_records(sources))
    runs_by_repository = {run["repository"]: run for run in runs if run["repository"]}
    runs_by_id = {run["id"]: run for run in runs}

    layers = []
    for key in sorted(set(landscape) | set(planned)):
        catalog, layer_id = key
        entry = landscape.get(key) or planned[key]
        row = entry["row"]
        is_landscape = key in landscape
        matrix_row = matrix_rows.get(key) or {}
        convergence = matrix_row.get("convergence") or {}
        covering = [sweep for sweep in sweeps if key in sweep["covers"]]
        verdict_day = component_matrix.parse_iso_date(row.get("checked_at")) if is_landscape else None
        state, reopened_by = None, []
        if is_landscape:
            # component_matrix.build_layer_convergence's rule: a sweep on the verdict's own date is not after it.
            later = [sweep for sweep in covering if verdict_day is None or sweep["day"] > verdict_day]
            state = component_matrix.classify_layer_state(row, later)
            reopened_by = ([{"sweep_id": sweep["sweep_id"], "date": sweep["date"]} for sweep in later]
                           if state == "recorded_reopened" else [])
            recorded = (convergence.get("layer_state"), convergence.get("reopened_by") or [])
            if recorded != (state, reopened_by):
                raise FinalStackError(f"{MATRIX} is stale for {layer_key(*key)}: layer_state {recorded[0]!r}, "
                                      f"reopened by {recorded[1]!r}; the ledger gives {state!r}, {reopened_by!r}. "
                                      "Run python3 scripts/component_matrix.py --write first")
        held = isinstance(row.get("current_adoption_status"), str) and row["current_adoption_status"].startswith("held")
        winners = [build_winner(winner, matrix_row, runs_by_repository, runs_by_id, held)
                   for winner in _dicts(row.get("winners"))] if is_landscape else []
        layer_outcomes = outcomes.get(key, {"proposed": set(), "latest": {}})
        survivors = sorted(({"repository": repository, "sweep_id": sweep_id, "date": day}
                            for repository, (outcome, sweep_id, day) in layer_outcomes["latest"].items()
                            if outcome == "survived" and (verdict_day is None or date.fromisoformat(day) > verdict_day)),
                           key=lambda survivor: survivor["repository"])
        recorded_repositories = {host_receipts.normalize_repository(item.get("repository"))
                                 for role in ("winners", "alternatives", "candidates") for item in _dicts(row.get(role))}
        layers.append({
            "catalog": catalog,
            "layer_id": layer_id,
            "title": row.get("title"),
            "source": entry["source"],
            "status": layer_status(bool(covering), state if is_landscape else None, convergence),
            "verdict": build_verdict(row, matrix_row, registry, reopened_by) if is_landscape else None,
            "winners": winners,
            "alternates": [{field: alternative.get(field) for field in
                            ("name", "repository", "disposition", "evidence_class")}
                           for alternative in _dicts(row.get("alternatives"))],
            "survivors": survivors,
            "open_gaps": matrix_row.get("open_gaps"),
            "research": ({"status": research[key].get("status"), "next_action": research[key].get("next_action")}
                         if is_landscape else None),
            "saturation": saturation.get(key),
            "funnel": {
                "found": len((layer_outcomes["proposed"] | recorded_repositories) - {None}),
                "refuted": sum(1 for outcome, _sweep, _day in layer_outcomes["latest"].values() if outcome == "refuted"),
                "surviving": len(survivors),
                "trialled": len(trialled_repositories(row)),
                "adopted": len({host_receipts.normalize_repository(winner["repository"]) for winner in winners
                                if winner["run"] is not None} - {None}),
            },
        })

    skills_coverage = []
    for task in _dicts(skills.get("tasks")):
        if not isinstance(task.get("layer_id"), str):
            continue
        key = (SKILLS, task["layer_id"])
        skills_coverage.append({"layer_id": task["layer_id"], "lifecycle_task": task.get("lifecycle_task"),
                                "swept": any(key in sweep["covers"] for sweep in sweeps),
                                "saturation": saturation.get(key)})
    skills_coverage.sort(key=lambda task: task["layer_id"])

    document = {
        "schema_version": SCHEMA_VERSION,
        "checked_at": CHECKED_AT,
        "scope": SCOPE,
        "definitions": [{"term": term, "definition": text} for term, text in DEFINITIONS],
        "policy": {"review_days": REVIEW_DAYS, "K": (ledger.get("policy") or {}).get("K"),
                   "min_gap_days": (ledger.get("policy") or {}).get("min_gap_days")},
        "layers": layers,
        "coverage": {"skills": skills_coverage},
        "runs": runs,
        "intake": build_intake(sources, layers),
        "index": build_index(layers, landscape),
        "summary": build_summary(layers, runs, skills_coverage, matrix),
    }
    document["sources"] = dict(sorted(sources.hashes.items()))
    problems = document_errors(document, landscape)
    if problems:
        raise FinalStackError("internally inconsistent document: " + "; ".join(problems))
    return document


def build_intake(sources: Sources, layers: list[dict]) -> dict:
    directory = sources.path(SEEDS_DIR)
    dated = sorted(((match.group(1, 2, 3), path.name) for path in (directory.iterdir() if directory.is_dir() else [])
                    if (match := SEEDS_NAME.fullmatch(path.name))))
    seeds = None
    if dated:
        (year, month, day), name = dated[-1]
        relative = f"{SEEDS_DIR}/{name}"
        document = sources.json(relative)
        if not isinstance(document, dict) or not all(isinstance(value, list) for value in document.values()):
            raise FinalStackError(f"{relative}: seeds must map layer ids to lists")
        catalogs_of: dict[str, list[str]] = {}
        for layer in layers:
            catalogs_of.setdefault(layer["layer_id"], []).append(layer_key(layer["catalog"], layer["layer_id"]))
        by_layer = {}
        for layer_id, items in document.items():
            keys = catalogs_of.get(layer_id, [])
            if len(keys) == 1:
                by_layer[keys[0]] = len(items)
        seeds = {"path": relative, "date": f"{year}-{month}-{day}", "total": sum(map(len, document.values())),
                 "by_layer": dict(sorted(by_layer.items())),
                 "unmatched": sorted(layer_id for layer_id in document if len(catalogs_of.get(layer_id, [])) != 1)}
    return {
        "seeds": seeds,
        "stars": {"status": "UNREPORTED", "source": STARS_FILE,
                  "reason": "future integration path for the starred-seeds intake (#978); v1 does not read it"},
        "grand": {"status": "UNREPORTED", "source": GRAND_COUNTS_FILE,
                  "reason": "future integration path for the grand-catalog counts snapshot (W4 PR 3); v1 does not read it"},
    }


def build_index(layers: list[dict], landscape: dict) -> dict:
    by_repository: dict[str, set] = {}
    by_component_id: dict[str, set] = {}

    def add(repository, catalog, layer_id, role):
        normalized = host_receipts.normalize_repository(repository)
        if normalized is not None:
            by_repository.setdefault(normalized, set()).add((catalog, layer_id, role))

    for layer in layers:
        catalog, layer_id = layer["catalog"], layer["layer_id"]
        for winner in layer["winners"]:
            add(winner["repository"], catalog, layer_id, "winner")
            if isinstance(winner["component_id"], str):
                by_component_id.setdefault(winner["component_id"], set()).add((catalog, layer_id, "winner"))
        for alternate in layer["alternates"]:
            add(alternate["repository"], catalog, layer_id, "alternate")
        for survivor in layer["survivors"]:
            add(survivor["repository"], catalog, layer_id, "survivor")
        for candidate in _dicts((landscape.get((catalog, layer_id)) or {}).get("row", {}).get("candidates")):
            add(candidate.get("repository"), catalog, layer_id, "candidate")

    def entries(values):
        return [{"catalog": catalog, "layer_id": layer_id, "role": role}
                for catalog, layer_id, role in sorted(values, key=lambda item: (item[0], item[1], ROLES.index(item[2])))]

    return {"by_repository": {key: entries(values) for key, values in sorted(by_repository.items())},
            "by_component_id": {key: entries(values) for key, values in sorted(by_component_id.items())}}


def build_summary(layers: list[dict], runs: list[dict], skills_coverage: list[dict], matrix: dict) -> dict:
    winners = [winner for layer in layers for winner in layer["winners"]]
    overall = ((matrix.get("summary") or {}).get("convergence") or {}).get("overall") or {}
    return {
        "layers": len(layers),
        "status": {status: sum(1 for layer in layers if layer["status"] == status) for status in STATUS_ORDER},
        "winners": len(winners),
        "pin_parse": {"parsed": sum(1 for winner in winners if "pin_parsed" in winner),
                      **{value: sum(1 for winner in winners if winner.get("pin_parse") == value)
                         for value in (UNPINNED, "unparsed")}},
        "winners_with_run": sum(1 for winner in winners if winner["run"] is not None),
        "run_reasons": {reason: sum(1 for winner in winners if winner["run_reason"] == reason) for reason in RUN_REASONS},
        "pin_drift": {value: sum(1 for winner in winners if winner["pin_drift"] == value) for value in PIN_DRIFT_VALUES},
        "runs": len(runs),
        "runs_with_conflicts": sum(1 for run in runs if run["conflicts"]),
        "alternates": sum(len(layer["alternates"]) for layer in layers),
        "survivors": sum(len(layer["survivors"]) for layer in layers),
        "skills_layers": len(skills_coverage),
        "skills_swept": sum(1 for task in skills_coverage if task["swept"]),
        "matrix_convergence": {"converged": overall.get("converged"), "in_use": overall.get("in_use")},
    }


def document_errors(document: dict, landscape: dict) -> list[str]:
    """Index entries that point to a missing layer or role, winners absent from their landscape row, and runs
    that a winner names but runs[] lacks."""
    layers = {(layer["catalog"], layer["layer_id"]): layer for layer in document["layers"]}
    runs = {run["id"] for run in document["runs"]}
    problems = []
    for repository, entries in document["index"]["by_repository"].items():
        for entry in entries:
            key = (entry["catalog"], entry["layer_id"])
            layer = layers.get(key)
            if layer is None:
                problems.append(f"index {repository} points to the missing layer {layer_key(*key)}")
                continue
            role = entry["role"]
            named = ([item.get("repository") for item in layer["winners"]] if role == "winner"
                     else [item.get("repository") for item in layer["alternates"]] if role == "alternate"
                     else [item.get("repository") for item in layer["survivors"]] if role == "survivor"
                     else [item.get("repository") for item in _dicts((landscape.get(key) or {}).get("row", {}).get("candidates"))])
            if repository not in {host_receipts.normalize_repository(item) for item in named}:
                problems.append(f"index {repository} names it a {role} of {layer_key(*key)}, which does not list it")
    for component_id, entries in document["index"]["by_component_id"].items():
        for entry in entries:
            layer = layers.get((entry["catalog"], entry["layer_id"]))
            if layer is None or component_id not in {winner["component_id"] for winner in layer["winners"]}:
                problems.append(f"index {component_id} points to a missing winner of {entry['catalog']}/{entry['layer_id']}")
    for key, layer in layers.items():
        recorded = {(winner.get("component_id"), winner.get("repository"))
                    for winner in _dicts((landscape.get(key) or {}).get("row", {}).get("winners"))}
        for winner in layer["winners"]:
            if (winner["component_id"], winner["repository"]) not in recorded:
                problems.append(f"winner {winner['component_id']} of {layer_key(*key)} is absent from its landscape row")
            if winner["run"] is not None and winner["run"] not in runs:
                problems.append(f"winner {winner['component_id']} of {layer_key(*key)} names the missing run {winner['run']}")
    return problems


# --------------------------------------------------------------------------- W1b API


@dataclass(frozen=True)
class Definitive:
    """is_definitive's answer: true iff ``definitive``; otherwise ``reason`` is a NOT_DEFINITIVE_REASONS code.
    ``layers`` names the layers that decided it."""

    definitive: bool
    reason: str | None
    layers: tuple[str, ...]

    def __bool__(self) -> bool:
        return self.definitive


def index_entries(document: dict, ident: str) -> list[dict]:
    """The index entries for a winner component id, else for a repository in any spelling normalize_repository
    accepts."""
    index = document["index"]
    if ident in index["by_component_id"]:
        return index["by_component_id"][ident]
    return index["by_repository"].get(host_receipts.normalize_repository(ident), [])


def is_definitive(document: dict, ident: str, today, *, layer: str | None = None) -> Definitive:
    """Is ``ident`` (a winner component id or a repository) the current winner of a layer, not past that layer's
    next_review on ``today``? True iff it is a winner in a layer whose status is current or converged and today is
    on or before next_review. ``layer`` ("<catalog>/<layer_id>") narrows the question to one layer."""
    today = date.fromisoformat(today) if isinstance(today, str) else today
    tracked = index_entries(document, ident)
    entries = [entry for entry in tracked
               if layer is None or layer_key(entry["catalog"], entry["layer_id"]) == layer]
    if not entries:
        if tracked:
            return Definitive(False, "not-winner",
                              tuple(sorted({layer_key(entry["catalog"], entry["layer_id"]) for entry in tracked})))
        return Definitive(False, "untracked", ())
    winner_keys = sorted({(entry["catalog"], entry["layer_id"]) for entry in entries if entry["role"] == "winner"})
    if not winner_keys:
        return Definitive(False, "not-winner",
                          tuple(sorted({layer_key(entry["catalog"], entry["layer_id"]) for entry in entries})))
    layers = {(row["catalog"], row["layer_id"]): row for row in document["layers"]}
    reasons: dict[str, list[str]] = {}
    for key in winner_keys:
        row = layers[key]
        next_review = (row.get("verdict") or {}).get("next_review")
        if row["status"] not in DEFINITIVE_STATUSES:
            reasons.setdefault(row["status"], []).append(layer_key(*key))
        elif next_review is None or today > date.fromisoformat(next_review):
            reasons.setdefault("stale", []).append(layer_key(*key))
        else:
            reasons.setdefault(None, []).append(layer_key(*key))
    if None in reasons:
        return Definitive(True, None, tuple(reasons[None]))
    reason = min(reasons, key=NOT_DEFINITIVE_REASONS.index)
    return Definitive(False, reason, tuple(reasons[reason]))


def run_pin(document: dict, ident: str) -> dict | None:
    """Do we run ``ident``, and at which pin? The runs[] entry for a run id, a winner component id or a repository;
    None when no run-pin source pins it."""
    runs = {run["id"]: run for run in document["runs"]}
    if ident in runs:
        return runs[ident]
    for layer in document["layers"]:
        for winner in layer["winners"]:
            if winner["component_id"] == ident and winner["run"] is not None:
                return runs[winner["run"]]
    repository = host_receipts.normalize_repository(ident)
    return next((run for run in document["runs"] if repository and run["repository"] == repository), None)


# --------------------------------------------------------------------------- flags and output


def flags(document: dict, today: date | None) -> dict:
    """The v1 report-only findings: winners without a run pin, pin drift and (with ``today``) verdicts past
    next_review."""
    winners = [(layer_key(layer["catalog"], layer["layer_id"]), winner)
               for layer in document["layers"] for winner in layer["winners"]]
    stale = None
    if today is not None:
        stale = [{"layer": layer_key(layer["catalog"], layer["layer_id"]), "next_review": layer["verdict"]["next_review"]}
                 for layer in document["layers"]
                 if (layer["verdict"] or {}).get("next_review") and today > date.fromisoformat(layer["verdict"]["next_review"])]
    return {
        "without_run": {reason: [f"{key} {winner['component_id']}" for key, winner in winners
                                 if winner["run_reason"] == reason] for reason in RUN_REASONS},
        "pin_drift": [f"{key} {winner['component_id']}: verdict {winner['verdict_pin']}, run "
                      f"{run_pin(document, winner['run'])['pin']}" for key, winner in winners
                      if winner["pin_drift"] == "differs"],
        "pin_drift_unknown": [f"{key} {winner['component_id']}: verdict {winner['verdict_pin']}, run "
                              f"{run_pin(document, winner['run'])['pin']}" for key, winner in winners
                              if winner["pin_drift"] == "unknown"],
        "past_next_review": stale,
        "today": today.isoformat() if today else None,
    }


def render_flags(found: dict) -> list[str]:
    without = found["without_run"]
    lines = [f"flag (report-only): {sum(map(len, without.values()))} winner(s) without a run pin: "
             + "; ".join(f"{reason} {len(items)}" + (f" ({', '.join(items)})" if items else "")
                         for reason, items in without.items()),
             f"flag (report-only): {len(found['pin_drift'])} winner(s) whose run pin differs from the verdict pin"
             + (": " + "; ".join(found["pin_drift"]) if found["pin_drift"] else ""),
             f"flag (report-only): {len(found['pin_drift_unknown'])} winner(s) whose pin drift is unknown "
             "(an unpinned or unparsed pin, or no shared field)"
             + (": " + "; ".join(found["pin_drift_unknown"]) if found["pin_drift_unknown"] else "")]
    if found["past_next_review"] is None:
        lines.append("flag (report-only): next_review not evaluated; pass --today YYYY-MM-DD")
    else:
        lines.append(f"flag (report-only): --today {found['today']}: {len(found['past_next_review'])} layer(s) past "
                     "next_review" + (": " + ", ".join(f"{item['layer']} ({item['next_review']})"
                                                     for item in found["past_next_review"])
                                      if found["past_next_review"] else ""))
    return lines


serialize = component_matrix.serialize


def check_problems(root: Path, document: dict, text: str) -> list[str]:
    """Why the committed file is not the generated one: a changed source hash, then byte drift."""
    path = root / OUTPUT
    if not path.is_file():
        return [f"{OUTPUT} is missing; run python3 scripts/final_stack.py --write"]
    committed_text = path.read_text(encoding="utf-8")
    if committed_text == text:
        return []
    problems = []
    try:
        committed = json.loads(committed_text).get("sources") or {}
    except (ValueError, AttributeError):
        committed = {}
    current = document["sources"]
    for relative in sorted(set(committed) | set(current)):
        if committed.get(relative) != current.get(relative):
            problems.append(f"sources: {relative} " + (
                "is no longer read" if relative not in current else "is a new source" if relative not in committed
                else f"sha256 changed ({str(committed[relative])[:12]} -> {current[relative][:12]})"))
    problems.append(f"{OUTPUT} differs from the generated output; run python3 scripts/final_stack.py --write "
                    "and commit it with the change to its sources")
    return problems


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    parser.add_argument("--root", type=Path, default=ROOT)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="Rebuild and compare with the committed file (default).")
    mode.add_argument("--write", action="store_true", help="Rebuild, write and register the file.")
    parser.add_argument("--today", type=date.fromisoformat,
                        help="UTC date YYYY-MM-DD for the report-only next_review flags; without it none is evaluated.")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    root = args.root.resolve()
    try:
        document = build_document(root)
    except FinalStackError as error:
        print(f"final_stack: {error}")
        return 1
    text = serialize(document)
    component_matrix.assert_no_private_content(text, reject_email=True)
    status = {"layers": len(document["layers"]), "status_counts": document["summary"]["status"]}
    if args.write:
        try:
            private_names = host_name_scan.host_names(root)
        except host_name_scan.HostNameScanError:
            raise SystemExit("final_stack: private identity context unavailable; aborting") from None
        # validate.py --scan-file and the pre-push hook use this same native
        # scanner. Its upstream decoders and literal-boundary rules replace the
        # former substring matcher; never publish native text or diagnostics.
        try:
            with tempfile.TemporaryDirectory(prefix="final-stack-publication-") as temporary:
                candidate = Path(temporary) / "candidate.json"
                candidate.write_bytes(text.encode("utf-8"))
                findings = host_name_scan.scan_paths([candidate], root=root, names=private_names, reject_email=True)
        except (host_name_scan.HostNameScanError, OSError):
            raise SystemExit("final_stack: private publication scanner unavailable; aborting") from None
        if findings:
            raise SystemExit("final_stack: native scanner refused private publication content; aborting")
        (root / OUTPUT).write_text(text, encoding="utf-8")
        host_receipts.register_file(root, OUTPUT)
        print(json.dumps({"status": "written", **status}, sort_keys=True))
    else:
        problems = check_problems(root, document, text)
        if problems:
            print("\n".join(problems))
            return 1
        print(json.dumps({"status": "checked", **status}, sort_keys=True))
    print("\n".join(render_flags(flags(document, args.today))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
