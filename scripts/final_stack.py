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
    from . import angle_records, component_matrix, complete_run_pins, host_receipts, host_name_scan, saturation_ledger
    from .catalog_decisions import InvalidDecisionIndex, pointer, safe_file, unique_json
    from .landscape import FINAL_ADMISSION_REFUSAL, refuse_final
    from .sweep_policy import DEFAULT_SWEEP_CADENCE_DAYS
except ImportError:  # running as a plain script, not a package
    import angle_records
    import component_matrix
    import complete_run_pins
    import host_receipts
    import host_name_scan
    import saturation_ledger
    from catalog_decisions import InvalidDecisionIndex, pointer, safe_file, unique_json
    from landscape import FINAL_ADMISSION_REFUSAL, refuse_final
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
    "a repository and component index; sourced angle summaries and explicit FINAL checks. A read-only join of "
    "evidence recorded elsewhere; it selects nothing."
)
OUTPUT = "catalogs/landscape/final-stack.json"
LANDSCAPE_MANIFEST = "catalogs/landscape/manifest.json"
PLANNED_LAYERS = "catalogs/landscape/planned-layers.json"
PLANNED_SOURCE_REVIEW = "docs/decisions/2026-10-11-planned-layers-source-review.json"
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
REVIEWED_VERDICTS = ("recorded", "no_selection", "FINAL")
# Landscape rows that count as trialled until W5's comparison ledger exists: measured_comparison evidence
# (scripts/landscape.py WINNER_EVIDENCE_CLASSES, EVIDENCE_KINDS) or a measured_tradeoff disposition.
MEASURED_EVIDENCE = (("evidence_class", "measured_comparison"), ("evidence_kind", "measured_comparison"),
                     ("disposition", "measured_tradeoff"))

# Run-pin sources, highest precedence first. A component is the normalized repository (or, without one, its id).
LOCKFILE = "blueprints/us-equities/runtime-2604/trading-2604-runtime/uv.lock"
LOCKFILE_SOURCES = "catalogs/landscape/lockfile-source-identities.json"
# Compatibility for the source observation already published by #1197. New
# PIN-DATA entries carry source_proof explicitly; no commit is hardcoded here.
LOCKFILE_SOURCE_PROOFS = {
    ("nautilus-trader", "2.0.0rc5"): "evidence/artifacts/pin-source-rules-20261016/nautilus-tag-proof.json",
}
PIN_FILES = (("linux-x86_64", "adoption/pins-linux-x86_64.json"), ("macos-arm64", "adoption/pins-macos-arm64.json"))
STACK = component_matrix.STACK_FILE
RUNTIME_TARGET = "catalogs/us-equities/runtime-target.json"
RUNTIME_ENGINE_POINTER = "/engine"
RUN_PIN_SOURCES_TEXT = (f"the allowlisted lockfile {LOCKFILE} (its root package's direct requirements, with exact "
                        + f"version/artifact source identities from {LOCKFILE_SOURCES}), "
                        + ", ".join(path for _platform, path in PIN_FILES)
                        + f" tools[].version, {STACK} version/source_pin and {RUNTIME_TARGET}#{RUNTIME_ENGINE_POINTER}")
# The lockfile records no repository. A requirement whose name is a manifests/stack.json id takes that component's
# repository; these are the repositories of the other requirements that a landscape winner records for the same
# package (catalogs/landscape/us-equities.json data-mlflow and data-pandera).
# Keep this fallback limited to missing stack identities; the other F1 packages
# already have canonical repositories in the stack and need no redundant map.
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
     "above 0); current (otherwise). For an explicit FINAL claim, a later sweep reopens only with a named, "
     "retained change reference; a date-only matrix reopening does not revoke FINAL."),
    ("verdict.next_review",
     "The verdict's checked_at plus policy.review_days, for a recorded or no_selection verdict; null for pending "
     "lanes and planned layers. It is a date, never a staleness: --check --today D flags a layer when D is past it."),
    ("winners[].pin_parsed",
     "The verdict pin parsed in one of the forms " + PIN_FORMS_TEXT + "; otherwise pin_parse is unpinned (the text "
     "'unpinned') or unparsed. Free text is flagged, never guessed."),
    ("runs",
     "One entry per component a run-pin source pins, keyed by normalized repository (or by id without one). "
     "Precedence: " + RUN_PIN_SOURCES_TEXT + "; the first source is the run pin and every other source whose parsed "
     "pin differs is listed under conflicts. Fields absent from that first source are compared between lower "
     "sources too. platforms lists the adoption pin files that install the same pin."),
    ("runs[].source_pin and runs[].source_pin_kind",
     "When the chosen source supplies a nonempty noncommit source pin, source_pin retains its original text. "
     "source_pin_kind is sha256 for a 64-hex artifact digest and tag for other retained values. A 40-hex Git "
     "source pin is merged into pin_parsed.commit instead. No missing source pin is invented."),
    ("runs[].source",
     "The pointer to the record supplying the complete run pin. For an exact lock-source supplement match, "
     "this points into " + LOCKFILE_SOURCES + " bindings; that binding's source points back to the unchanged "
     "lock entry whose version and complete artifact hash set were matched. The lock itself records no Git commit."),
    ("runs[].source_commit_claim and runs[].source_proof_status",
     "A commit claimed by an adoption, stack or runtime source without matching retained proof remains "
     "informational as source_commit_claim, with source_proof_status not_verified and no pin_parsed.commit. "
     "It cannot complete any receipt, including a version-only receipt. Matching source_proof is required "
     "for every run-pin source."),
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
     "proposed plus the landscape candidates, alternatives and winners; refuted: the latest refutation without "
     "a later survival or missing-vote-only re-proposal; surviving: an unresolved survival or missing-vote proposal dated after the "
     "verdict; trialled: landscape rows "
     "with measured_comparison evidence or a measured_tradeoff disposition; adopted: winners with a run pin."),
    ("survivors", "The unresolved repositories of the funnel, with their latest survival or the missing-vote-only sweep and date that opened or reopened them. "
     "For explicit FINAL claims, replay the cumulative set without a verdict-date filter: only retained substantive "
     "refutation or an explicit retained verdict disposition settles a survivor, never age or omission."),
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
        self._json_cache: dict[str, object] = {}

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
        if relative in self._json_cache:
            return self._json_cache[relative]
        raw = self.read_bytes(relative)
        try:
            document = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_json)
        except (UnicodeError, ValueError) as error:
            raise FinalStackError(f"{relative}: cannot read JSON ({error})") from error
        self._json_cache[relative] = document
        return document

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
    if layers:
        reference = document.get("source_review")
        if not isinstance(reference, dict) or reference.get("path") != PLANNED_SOURCE_REVIEW:
            raise FinalStackError("planned layers need the checked-in source review")
        review = sources.json(PLANNED_SOURCE_REVIEW)
        if reference.get("sha256") != sources.hashes[PLANNED_SOURCE_REVIEW]:
            raise FinalStackError("planned layers source review hash differs")
        if not isinstance(review, dict) or review.get("layers") != layers:
            raise FinalStackError("planned layers differ from the checked-in source review")
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
    """Parse the release pin and retain its separately recorded source pin.

    A 40-hex Git commit merges into pin_parsed; a contradictory commit leaves
    the pin unparsed. Noncommit pins retain raw source_pin and its kind.
    """
    parsed = parse_pin(text)
    if isinstance(commit, str) and commit and not COMMIT_PATTERN.fullmatch(commit):
        # source_pin includes artifact SHA256 and upstream tags, not just Git
        # commits (foundation-layer-map-20261008.md:34-36). Retain its meaning.
        kind = "sha256" if re.fullmatch(r"[0-9a-fA-F]{64}", commit) else "tag"
        return {**parsed, "source_pin": commit, "source_pin_kind": kind}
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


def lock_source_proof(sources: Sources, binding: dict, *, component_ids=()) -> str | None:
    """Match a source claim to its retained exact-version Git observation offline."""
    reference = binding.get("source_proof")
    if reference is None:
        reference = LOCKFILE_SOURCE_PROOFS.get((binding.get("package"), binding.get("version")))
    if not isinstance(reference, str):
        return None
    path, separator, selector = reference.partition("#")
    if not path.startswith("evidence/artifacts/") or not path.endswith(".json"):
        return None
    try:
        proof = sources.json(path)
        if separator:
            proof = pointer(proof, selector)
    except (FinalStackError, InvalidDecisionIndex, OSError, ValueError):
        return None
    if not isinstance(proof, dict) or proof.get("component") not in {binding.get("package"), *component_ids}:
        return None
    if binding.get("version") is None and binding.get("commit"):
        return complete_run_pins.verified_commit_object(
            proof, proof["component"], binding["commit"],
            host_receipts.normalize_repository(binding.get("repository")))
    return complete_run_pins.verified_commit(
        proof, proof["component"], binding.get("version"),
        host_receipts.normalize_repository(binding.get("repository")))


def proof_backed_record_pin(sources: Sources, text, commit, *, component, repository, reference, component_ids=()):
    """Keep an unproved commit as information, never as a receipt-binding commit."""
    parsed = record_pin(text, commit)
    identity = parsed.get("pin_parsed")
    if not identity or not identity.get("commit"):
        return parsed
    claimed = identity["commit"]
    binding = {"package": component, "version": identity.get("version"),
               "commit": claimed, "repository": repository, "source_proof": reference}
    if reference is not None and lock_source_proof(sources, binding, component_ids=component_ids) == claimed:
        return parsed
    return {**parsed, "pin_parsed": {**identity, "commit": None},
            "source_commit_claim": claimed, "source_proof_status": "not_verified"}


def run_records(sources: Sources) -> list[dict]:
    """Every run-pin record, in precedence order: rank, then platform order, then position in its source."""
    stack = sources.json(STACK)
    stack_components = _dicts(stack.get("components") if isinstance(stack, dict) else None)
    stack_repository = {component["id"]: host_receipts.normalize_repository(component.get("repository"))
                        for component in stack_components if isinstance(component.get("id"), str)}
    records = []

    lock = sources.toml(LOCKFILE)
    bindings = {}
    if sources.path(LOCKFILE_SOURCES).exists():
        supplement = sources.json(LOCKFILE_SOURCES)
        if (not isinstance(supplement, dict) or supplement.get("schema_version") != 1
                or supplement.get("lockfile") != LOCKFILE or not isinstance(supplement.get("bindings"), list)):
            raise FinalStackError(f"{LOCKFILE_SOURCES}: unknown schema or lockfile")
        for binding_index, binding in enumerate(supplement["bindings"]):
            if not isinstance(binding, dict) or not isinstance(binding.get("source"), str):
                raise FinalStackError(f"{LOCKFILE_SOURCES}: binding requires a source pointer")
            if binding["source"] in bindings:
                raise FinalStackError(f"{LOCKFILE_SOURCES}: duplicate source identity")
            bindings[binding["source"]] = (binding_index, binding)
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
        source = f"{LOCKFILE}#/package/{index}"
        pin = package.get("version")
        parsed = record_pin(pin)
        if source in bindings:
            binding_index, binding = bindings[source]
            artifacts = sorted({artifact["hash"] for artifact in
                                [package.get("sdist", {}), *package.get("wheels", [])] if artifact.get("hash")})
            if (binding.get("package") == name and binding.get("version") == pin
                    and artifacts and binding.get("artifact_sha256") == artifacts
                    and repository is not None
                    and host_receipts.normalize_repository(binding.get("repository")) == repository
                    and isinstance(binding.get("commit"), str) and COMMIT_PATTERN.fullmatch(binding["commit"])
                    and lock_source_proof(sources, binding, component_ids=(
                        component["id"] for component in stack_components
                        if host_receipts.normalize_repository(component.get("repository")) == repository)) == binding["commit"]):
                parsed = record_pin(pin, binding["commit"])
                pin = f"{pin}; source {binding['commit']}"
                source = f"{LOCKFILE_SOURCES}#/bindings/{binding_index}"
            else:
                parsed = {"pin_parse": "unparsed"}
        records.append({"rank": 0, "id": name, "repository": repository, "pin": pin,
                        "parsed": parsed, "source": source,
                        "platform": None})

    for platform_order, (platform, relative) in enumerate(PIN_FILES):
        document = sources.json(relative)
        for index, tool in enumerate(document.get("tools") if isinstance(document, dict) else []):
            if not isinstance(tool, dict) or not isinstance(tool.get("id"), str):
                raise FinalStackError(f"{relative}: tools[{index}] needs an id")
            repository = stack_repository.get(tool["id"]) or github_repository(tool.get("url"))
            records.append({"rank": 1 + platform_order, "id": tool["id"], "repository": repository,
                            "pin": tool.get("version"), "parsed": proof_backed_record_pin(
                                sources, tool.get("version"), tool.get("commit"), component=tool["id"],
                                repository=repository, reference=tool.get("source_proof"), component_ids=(
                                    component["id"] for component in stack_components
                                    if host_receipts.normalize_repository(component.get("repository")) == repository)),
                            "source": f"{relative}#/tools/{index}", "platform": platform})

    for index, component in enumerate(stack_components):
        if not isinstance(component.get("id"), str):
            raise FinalStackError(f"{STACK}: components[{index}] needs an id")
        records.append({"rank": 1 + len(PIN_FILES), "id": component["id"],
                        "repository": stack_repository[component["id"]], "pin": component.get("version"),
                        "parsed": proof_backed_record_pin(
                            sources, component.get("version"), component.get("source_pin"), component=component["id"],
                            repository=stack_repository[component["id"]], reference=component.get("source_proof"),
                            component_ids=(candidate["id"] for candidate in stack_components
                                           if stack_repository.get(candidate.get("id"))
                                           == stack_repository[component["id"]])),
                        "source": f"{STACK}#/components/{index}", "platform": None})

    runtime = sources.json(RUNTIME_TARGET)
    engine = runtime.get("engine") if isinstance(runtime, dict) else None
    if not isinstance(engine, dict):
        raise FinalStackError(f"{RUNTIME_TARGET}#{RUNTIME_ENGINE_POINTER} must be an object")
    # Only the repository, version and commit are copied: the record also carries host and environment detail.
    repository = host_receipts.normalize_repository(engine.get("repository"))
    records.append({"rank": 2 + len(PIN_FILES), "id": (repository or "engine").rsplit("/", 1)[-1],
                    "repository": repository, "pin": engine.get("requested_version"),
                    "parsed": proof_backed_record_pin(
                        sources, engine.get("requested_version"), engine.get("source_commit"),
                        component=(repository or "engine").rsplit("/", 1)[-1], repository=repository,
                        reference=engine.get("source_proof"), component_ids=(
                            component["id"] for component in stack_components
                            if stack_repository.get(component.get("id")) == repository)),
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
        absent_fields = [field for field in ("version", "commit")
                         if not chosen["parsed"].get("pin_parsed", {}).get(field)]
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
                          if compare_pins(record["parsed"], chosen["parsed"]) == "differs"
                          or any(compare_pins({"pin_parsed": {
                              field: record["parsed"].get("pin_parsed", {}).get(field)
                              for field in absent_fields}}, other["parsed"]) == "differs"
                              for other in members if other is not record)],
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


def sweep_outcomes(sweeps: list[dict], sources: Sources) -> dict[tuple[str, str], dict]:
    """(catalog, layer_id) -> {"proposed": set, "latest": {repository: (outcome, sweep_id, date)}} over the completed
    sweeps in date order; missing-vote-only re-proposals reopen earlier refutations, while earlier survivals keep
    their provenance. Within one sweep a substantive refutation is later than a survival."""
    outcomes: dict[tuple[str, str], dict] = {}
    target_of = saturation_ledger.ref_resolver(sources.json)
    for sweep in sweeps:
        for position, layer in enumerate(sweep["record"]["layers"]):
            where = f"{LEDGER}: {sweep['sweep_id']}: layers[{position}]"
            entry = outcomes.setdefault((layer["catalog"], layer["layer_id"]), {"proposed": set(), "latest": {}})
            proposed = layer.get("proposed") or []
            if not isinstance(proposed, list) or not all(isinstance(item, str) for item in proposed):
                raise FinalStackError(where + ": proposed must be a list of repositories")
            proposed_repositories = set(filter(None, map(host_receipts.normalize_repository, proposed)))
            entry["proposed"].update(proposed_repositories)
            for outcome in ("survived", "refuted"):
                items = layer.get(outcome) or []
                if not isinstance(items, list) or not all(isinstance(item, dict) and isinstance(item.get("repo"), str)
                                                          for item in items):
                    raise FinalStackError(f"{where}: {outcome} must be a list of objects with a repo")
                for item in items:
                    repository = host_receipts.normalize_repository(item["repo"])
                    if repository is not None:
                        if outcome == "refuted" and saturation_ledger.refuted_by_absence(item, target_of):
                            previous = entry["latest"].get(repository)
                            if previous is None or (
                                    previous[0] == "refuted" and repository in proposed_repositories
                                    and (previous[2], previous[1]) < (sweep["date"], sweep["sweep_id"])):
                                entry["latest"][repository] = ("survived", sweep["sweep_id"], sweep["date"])
                        else:
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


def build_verdict(row: dict, matrix_row: dict, registry: dict, reopened_by: list[dict], *, root: Path = None) -> dict:
    refuse_final(row, error_type=FinalStackError)
    verdict_day = component_matrix.parse_iso_date(row.get("checked_at"))
    wave = row_run_id(row, root=root)
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


def terminal_state(row: dict, angle: dict) -> str | None:
    refuse_final(row, error_type=FinalStackError)
    refuse_final(angle, error_type=FinalStackError)
    claims = [state for state in (row.get("terminal_state"), angle.get("terminal_state"),
                                 "FINAL" if row.get("verdict_status") == "FINAL" else None) if state]
    if len(set(claims)) > 1:
        raise FinalStackError("conflicting terminal-state claims")
    return claims[0] if claims else None


def retained_final_reference(sources: Sources, ref, reason: str):
    """A FINAL lifecycle decision must point at retained, hash-bound evidence."""
    try:
        if not isinstance(ref, str) or not ref:
            raise ValueError
        path, _, pointer = ref.partition("#")
        value = (saturation_ledger.resolve_pointer(sources.json(path), pointer) if pointer
                 else sources.read_bytes(path))
        if not value:
            raise ValueError
        return value
    except (FinalStackError, saturation_ledger.LedgerError, TypeError, ValueError):
        raise FinalStackError(reason) from None


def final_reopened_by(sources: Sources, key: tuple[str, str], later: list[dict],
                      baseline: dict | None) -> list[dict]:
    """FINAL admits only explicitly complete, unchanged retained post-anchor rows."""
    baseline_row = next((row for row in baseline["record"]["layers"]
                         if (row["catalog"], row["layer_id"]) == key), {}) if baseline else {}
    fields = ("requirement_sha256", "platform_profiles_sha256")
    if (baseline is None or baseline["record"].get("status") != "completed"
        or not all(isinstance(baseline_row.get(field), str)
                   and saturation_ledger.HEX64.fullmatch(baseline_row[field]) for field in fields)):
        raise FinalStackError("FINAL baseline requires retained complete scope hashes")
    reopened = []
    for sweep in later:
        admitted = sweep["record"].get("status") == "completed"
        for row in sweep["record"]["layers"]:
            if (row["catalog"], row["layer_id"]) != key:
                continue
            admitted = admitted and len([candidate for candidate in sweep["record"]["layers"]
                if (candidate["catalog"], candidate["layer_id"]) == key]) == 1
            markers = row.get("reopen")
            if not isinstance(markers, list):
                raise FinalStackError("FINAL reopening requires retained change evidence")
            for marker in markers:
                if not isinstance(marker, dict) or marker.get("trigger") not in saturation_ledger.REOPEN_TRIGGERS:
                    raise FinalStackError("FINAL reopening requires retained change evidence")
                retained_final_reference(sources, marker.get("ref"),
                                         "FINAL reopening requires retained change evidence")
            admitted = admitted and all(isinstance(row.get(field), str)
                and saturation_ledger.HEX64.fullmatch(row[field])
                and row[field] == baseline_row[field] for field in fields)
            admitted = admitted and not markers and not saturation_ledger.material_pending(row)
        if not admitted:
            reopened.append({"sweep_id": sweep["sweep_id"], "date": sweep["date"]})
    return reopened


def final_covering_sweeps(ledger: dict, key: tuple[str, str]) -> list[dict]:
    """Retained FINAL history in ledger order, without date/status/cutoff filtering."""
    covering = []
    seen = set()
    for ledger_index, record in enumerate(ledger["sweeps"]):
        layers = record.get("layers")
        if not isinstance(layers, list) or not layers or not all(isinstance(row, dict)
                and isinstance(row.get("catalog"), str) and isinstance(row.get("layer_id"), str)
                for row in layers):
            raise FinalStackError("FINAL sweep history requires retained layer records")
        if any((row.get("catalog"), row.get("layer_id")) == key for row in layers):
            sweep_id = record.get("sweep_id")
            if not isinstance(sweep_id, str) or not sweep_id or sweep_id in seen:
                raise FinalStackError("FINAL sweep history requires unique retained sweep ids")
            seen.add(sweep_id)
            covering.append({"ledger_index": ledger_index, "sweep_id": sweep_id, "date": record.get("date"),
                             "manifest_ref": record.get("manifest_ref"), "record": record})
    return covering


def final_v2_refutes_on_merit(sources: Sources, entry: dict, layer: dict) -> bool:
    """Recognize native retained V2 screens by recomputing their supported outcome."""
    target_of = saturation_ledger.ref_resolver(sources.json)
    try:
        discovery = target_of(layer.get("discovery_ref"))
        source = discovery.get("source_field") if isinstance(discovery, dict) else None
        documents = discovery.get("screen_judgments") if isinstance(discovery, dict) else None
        if (not isinstance(source, dict) or source.get("contract_version") != 2
            or not isinstance(documents, dict) or set(documents) != set(saturation_ledger.ROLES)
            or not all(isinstance(documents[role], list) for role in saturation_ledger.ROLES)
            or any(source.get(field) != layer.get(field) for field in
                   ("contract_version", "catalog", "layer_id", "requirement_sha256", "platform_profiles_sha256"))
            or saturation_ledger.v2_field_sha256(source) != source.get("field_sha256")):
            return False
        members = [member for member in _dicts(source.get("eligible_field"))
                   if member.get("candidate_key") == entry.get("candidate_key")]
        if (len(members) != 1 or members[0].get("repository") != entry.get("repository")
            or members[0].get("evidence_key") != entry.get("evidence_key")):
            return False
        member = members[0]
        if host_receipts.normalize_repository(entry.get("repo")) != host_receipts.normalize_repository(
                member["repository"]):
            return False
        conflict = saturation_ledger.v2_provenance_conflict(documents)
        screens = {role: saturation_ledger.v2_screen(role, documents[role], member, source, conflict)
                   for role in saturation_ledger.ROLES}
        outcome = saturation_ledger.v2_member_outcome(member, screens)
        if (outcome.get("status") != "not_credible" or outcome.get("disposition") != "refuted"
            or any(entry.get(field) != value for field, value in outcome.items())):
            return False
        for role in saturation_ledger.ROLES:
            vote = entry.get(role)
            if not isinstance(vote, dict) or vote.get("vote") != screens[role]["status"]:
                return False
            expected = {"contract_version": 2, "role": role, "candidate_key": member["candidate_key"],
                        "repository": member["repository"], "evidence_key": member["evidence_key"],
                        "judgments": documents[role], **screens[role]}
            if target_of(vote.get("ref")) != expected:
                return False
        return True
    except (FinalStackError, saturation_ledger.LedgerError, KeyError, TypeError, ValueError):
        return False


def final_disposition_index(sources: Sources, references: list, sweep_indices: dict) -> int | None:
    """A recorder-preserved evidence ref must name a known covering ledger event."""
    positions = []
    target_of = saturation_ledger.ref_resolver(sources.json)
    for reference in references:
        retained_final_reference(sources, reference, "FINAL survivor disposition requires retained evidence")
        try:
            target = target_of(reference)
        except (FinalStackError, saturation_ledger.LedgerError, TypeError, ValueError):
            continue
        if isinstance(target, dict):
            position = sweep_indices.get(target.get("sweep_id"))
            if position is not None:
                positions.append(position)
    return max(positions) if positions else None


def final_unresolved_survivors(sources: Sources, row: dict, covering: list[dict]) -> list[dict]:
    """Replay all survivor history; age, omission and a missing vote never settle it."""
    pending = {}
    pending_positions = {}
    sweep_indices = {sweep["sweep_id"]: sweep["ledger_index"] for sweep in covering}

    def mark_pending(identity, sweep):
        pending[identity] = {"repository": identity, "sweep_id": sweep["sweep_id"], "date": sweep["date"]}
        pending_positions[identity] = sweep["ledger_index"]

    def retained_merit(entry, layer) -> bool:
        if layer.get("contract_version") == 2:
            return final_v2_refutes_on_merit(sources, entry, layer)
        if "lens_votes" in entry:
            votes = entry.get("lens_votes") or []
        else:
            votes = [entry.get(role) for role in saturation_ledger.ROLES]
        for vote in votes:
            if not isinstance(vote, dict) or vote.get("vote") != "refuted":
                continue
            try:
                target = saturation_ledger.ref_resolver(sources.json)(vote.get("ref"))
            except (FinalStackError, saturation_ledger.LedgerError, TypeError, ValueError):
                continue
            if saturation_ledger.refutes_on_merit(target) is True:
                return True
        return False

    for sweep in covering:
        for layer in sweep["record"]["layers"]:
            if (layer["catalog"], layer["layer_id"]) != (row["catalog"], row["layer_id"]):
                continue
            for candidate in saturation_ledger.material_pending(layer):
                repo = host_receipts.normalize_repository(candidate.get("repository", candidate.get("repo")))
                identity = repo or candidate.get("candidate_key")
                if identity:
                    mark_pending(identity, sweep)
            answered = {host_receipts.normalize_repository(candidate.get("repo"))
                        for field in ("survived", "refuted") for candidate in _dicts(layer.get(field))}
            for proposal in layer.get("proposed") or []:
                repo = host_receipts.normalize_repository(proposal)
                if repo and repo not in answered:
                    mark_pending(repo, sweep)
            for candidate in _dicts(layer.get("survived")):
                repo = host_receipts.normalize_repository(candidate.get("repo"))
                if repo:
                    mark_pending(repo, sweep)
            for candidate in _dicts(layer.get("refuted")):
                repo = host_receipts.normalize_repository(candidate.get("repo"))
                if not repo:
                    continue
                if retained_merit(candidate, layer):
                    pending.pop(repo, None)
                    pending_positions.pop(repo, None)
                else:
                    mark_pending(repo, sweep)
    settled = {}
    for winner in _dicts(row.get("winners")):
        repo = host_receipts.normalize_repository(winner.get("repository"))
        position = final_disposition_index(sources, winner.get("evidence_refs") or [], sweep_indices)
        if repo and position is not None:
            settled[repo] = position
    for alternative in _dicts(row.get("alternatives")):
        refs = alternative.get("evidence_refs")
        if (alternative.get("disposition") not in {"observed_failure", "measured_tradeoff", "overlap", "out_of_scope",
                                                    "unqualified", "conditional"}
            or not isinstance(alternative.get("why_not_default"), str) or not alternative["why_not_default"].strip()
            or not isinstance(refs, list) or not refs):
            continue
        repo = host_receipts.normalize_repository(alternative.get("repository"))
        position = final_disposition_index(sources, refs, sweep_indices)
        if repo and position is not None:
            settled[repo] = max(settled.get(repo, -1), position)
    return sorted((survivor for repo, survivor in pending.items() if not (
        repo in settled and settled[repo] >= pending_positions[repo])),
        key=lambda survivor: survivor["repository"])


def complete_final_pin(text, run: dict) -> bool:
    """FINAL uses the complete recorded run identity, not shared-field drift matching.

    A supplied commit must be present in runs[]. A receipt cannot drop a
    recorded commit and rely on a matching release name instead.
    """
    if run.get("source_commit_claim") is not None or run.get("source_proof_status") == "not_verified":
        return False
    parsed = parse_pin(text).get("pin_parsed")
    canonical = run.get("pin_parsed")
    if not parsed or not canonical:
        return False
    if canonical.get("commit"):
        if parsed.get("commit") != canonical["commit"]:
            return False
    elif parsed.get("commit"):
        return False
    return all(canonical.get(key) == value for key, value in parsed.items() if value is not None)


def enforce_final(sources: Sources, layers: list[dict], runs: list[dict], angle_inputs: dict) -> None:
    """Refuse every explicit FINAL claim while admission is under redesign.

    The historical predicates below remain inactive until a separate redesign.
    A matrix 'converged' status is a different concept.
    """
    # Keep the enforcement entry point fail-closed for direct callers too.
    for layer in layers:
        refuse_final(layer, error_type=FinalStackError)
    by_run = {run["id"]: run for run in runs}
    for layer in layers:
        if layer["terminal_state"] != "FINAL":
            continue
        key = (layer["catalog"], layer["layer_id"])

        def fail(reason):
            raise FinalStackError(f"FINAL {layer_key(*key)}: {reason}")

        if layer["status"] not in DEFINITIVE_STATUSES:
            fail("reopened sweep delta must be adjudicated before FINAL"
                 if layer["status"] == "reopened"
                 else f"non-definitive status {layer['status']} cannot be FINAL")
        if layer["survivors"]:
            fail("cumulative unresolved survivors require retained dispositions before FINAL")
        entry = angle_inputs.get(key)
        if entry is None or not layer["winners"]:
            fail("requires winners and a CONVERGED angle record")
        verdict = layer["verdict"] or {}
        wave = verdict.get("wave_doc") or {}
        if not all(verdict.get(k) for k in ("date", "wave", "next_review")) or not wave.get("path"):
            fail("condition 1 requires a recorded verdict, wave and next_review")
        try:
            raw = sources.read_bytes(wave["path"])
        except FinalStackError:
            fail("condition 1 verdict wave is not retained")
        if hashlib.sha256(raw).hexdigest() != wave.get("sha256"):
            fail("condition 1 verdict wave hash does not match")
        record = entry["record"]
        bound = {e["candidate_id"]: e for e in record["final_evidence"]}
        for winner in layer["winners"]:
            repository = host_receipts.normalize_repository(winner["repository"])
            run = by_run.get(winner["run"])
            if not winner.get("evidence_class"):
                fail("condition 1 winner has no evidence class")
            if run is None or not run.get("pin") or winner["pin_drift"] != "same":
                fail("condition 2 winner requires a matching run pin in runs[]")
            if not complete_final_pin(winner["verdict_pin"], run):
                fail("condition 2 requires a complete FINAL pin identity in runs[]")
            candidates = [c for c in record["candidates"]
                          if host_receipts.normalize_repository(c["repository"]) == repository
                          and complete_final_pin(c["pin"], run)]
            if len(candidates) != 1:
                fail("winner requires one CONVERGED angle verdict at its complete FINAL pin identity")
            candidate = candidates[0]
            if candidate.get("final_eligible") is False:
                fail("final_eligible is false for this winner")
            if (candidate.get("entitlement") or {}).get("status") in ("pending", "unverified"):
                fail("entitlement remains unverified for this winner")
            if candidate["verdict"] != "CONVERGED":
                fail("winner requires one CONVERGED angle verdict at its run pin")
            if candidate["provisional"] or not candidate["a6_comparative"]:
                fail("winner requires NON-provisional CONVERGED evidence with comparative A6")
            evidence = bound.get(candidate["id"]) or {}
            if not complete_final_pin(evidence.get("run_pin"), run):
                fail("FINAL evidence requires the complete FINAL pin identity")

            def receipt(field, condition):
                path = evidence.get(field)
                if not path:
                    fail(f"condition {condition} requires {field}")
                try:
                    value = sources.json(path)
                except FinalStackError:
                    fail(f"condition {condition} receipt is unavailable")
                if (not isinstance(value, dict) or value.get("evidence_class") != "native_proven"
                    or host_receipts.normalize_repository(value.get("repository")) != repository
                    or not complete_final_pin(value.get("pin"), run)):
                    fail(f"condition {condition} receipt must bind native evidence to repository and complete FINAL pin identity")
                return value

            e2e = receipt("e2e_receipt", 3)
            schema = sources.json(angle_records.SCHEMA)
            contract = {"$schema": schema["$schema"], "$defs": schema["$defs"],
                        "$ref": "#/$defs/upstream_e2e"}
            validator = angle_records.Draft202012Validator(contract)
            if next(validator.iter_errors(e2e), None) is not None:
                fail("condition 3 receipt has invalid commands or citations")
            phases = {c.get("phase") for c in _dicts(e2e.get("commands"))
                      if c.get("command") and type(c.get("exit_code")) is int and c["exit_code"] == 0}
            cited = e2e.get("upstream_sources") or []
            upstream = [s for s in _dicts(cited) if s.get("kind") == "repo" and s.get("path") and s.get("line")
                        and host_receipts.normalize_repository(s.get("repository")) == repository
                        and complete_final_pin(s.get("pin"), run)]
            if (e2e.get("kind") != "upstream_e2e" or e2e.get("success") is not True
                or not {"install", "test"}.issubset(phases) or not upstream
                or any(c.get("exit_code") != 0 for c in _dicts(e2e.get("commands")))):
                fail("condition 3 requires successful upstream install and test commands with pinned citations")
            if evidence.get("invoke_receipt"):
                invoke = receipt("invoke_receipt", 4)
                try:
                    start, end = (angle_records.timestamp(invoke[k]) for k in ("window_start", "window_end"))
                    valid_window = start.tzinfo is not None and end.tzinfo is not None and start < end
                except (KeyError, TypeError, ValueError):
                    valid_window = False
                if (invoke.get("kind") != "invocation" or not valid_window
                    or type(invoke.get("calls")) is not int or invoke["calls"] <= 0):
                    fail("condition 4 requires positive invocation calls in a measured window")
            elif not (evidence.get("not_invoked_reason") or "").strip():
                fail("condition 4 requires invoke evidence or a recorded non-invocation reason")


def build_document(root: Path) -> dict:
    sources = Sources(root)
    try:
        angle_inputs = angle_records.load_records(sources)
    except angle_records.AngleRecordError as error:
        raise FinalStackError(str(error)) from error
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
    outcomes = sweep_outcomes(sweeps, sources)
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
    for key in sorted(set(landscape) | set(planned) | set(angle_inputs)):
        catalog, layer_id = key
        entry = landscape.get(key) or planned.get(key) or {
            "row": {"title": layer_id, "candidates": []}, "source": angle_inputs[key]["path"]}
        row = entry["row"]
        is_landscape = key in landscape
        resolved_terminal = terminal_state(row, (angle_inputs.get(key) or {}).get("record") or {})
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
            if resolved_terminal == "FINAL":
                # Preserve the matrix's ordinary dated metric, then apply the
                # protocol's consumed-sweep anchor in retained append-only order.
                covering = final_covering_sweeps(ledger, key)
                consumed = (registry.get(row_run_id(row)) or {}).get("manifest")
                matches = [sweep for sweep in covering if isinstance(consumed, str) and consumed
                           and sweep["manifest_ref"] == consumed]
                if len(matches) != 1:
                    raise FinalStackError("FINAL baseline requires one retained consumed covering sweep")
                sources.read_bytes(consumed)
                baseline = matches[0]
                later = [sweep for sweep in covering if sweep["ledger_index"] > baseline["ledger_index"]]
                reopened_by = final_reopened_by(sources, key, later, baseline)
                if reopened_by:
                    state = "recorded_reopened"
                elif state == "recorded_reopened":
                    state = "confirmed_current"
        held = isinstance(row.get("current_adoption_status"), str) and row["current_adoption_status"].startswith("held")
        winners = [build_winner(winner, matrix_row, runs_by_repository, runs_by_id, held)
                   for winner in _dicts(row.get("winners"))] if is_landscape else []
        layer_outcomes = outcomes.get(key, {"proposed": set(), "latest": {}})
        survivors = sorted(({"repository": repository, "sweep_id": sweep_id, "date": day}
                            for repository, (outcome, sweep_id, day) in layer_outcomes["latest"].items()
                            if outcome == "survived" and (verdict_day is None or date.fromisoformat(day) > verdict_day)),
                           key=lambda survivor: survivor["repository"])
        if resolved_terminal == "FINAL":
            survivors = final_unresolved_survivors(sources, {**row, "catalog": catalog}, covering)
        recorded_repositories = {host_receipts.normalize_repository(item.get("repository"))
                                 for role in ("winners", "alternatives", "candidates") for item in _dicts(row.get(role))}
        layers.append({
            "catalog": catalog,
            "layer_id": layer_id,
            "title": row.get("title"),
            "source": entry["source"],
            "status": layer_status(bool(covering), state if is_landscape else None, convergence),
            "terminal_state": resolved_terminal,
            "angles": angle_records.summary(angle_inputs.get(key)),
            "verdict": build_verdict(row, matrix_row, registry, reopened_by, root=root) if is_landscape else None,
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

    enforce_final(sources, layers, runs, angle_inputs)

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
        "angles": {status: sum(layer["angles"]["status"] == status for layer in layers)
                   for status in ("recorded", "missing")},
        "final_layers": sum(layer["terminal_state"] == "FINAL" for layer in layers),
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


def publication_entries(document: dict):
    """Actual report records, with each repository/component index mapping separate.

    No byte splitting: a record too large for the native fragment contract is
    refused by the shared scanner. All string values and variable keys remain
    covered; the constant list keys definitions, layers and runs are omitted.
    """
    for key, value in document.items():
        if key == "index":
            for index_key, mappings in value.items():
                for identity, references in mappings.items():
                    yield {key: {index_key: {identity: references}}}
        elif isinstance(value, list):
            for entry in value:
                yield entry if isinstance(entry, dict) else {key: entry}
        else:
            yield {key: value}


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
                findings = []
                for entry in publication_entries(document):
                    candidate.write_bytes(json.dumps(entry, ensure_ascii=True, separators=(",", ":")).encode("utf-8"))
                    findings.extend(host_name_scan.scan_paths([candidate], root=root, names=private_names,
                                                              reject_email=True))
        except host_name_scan.PublicationEntryTooLarge:
            raise SystemExit("final_stack: publication entry too large; aborting") from None
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
