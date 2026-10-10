"""Project source-bound facts for the Architecture manifest views.

Inputs are exact records that tools/local-pages/source_policy.json already
grants, read through the builder's ArchitectureReads. Every read is
existence-gated, so an absent record leaves its view UNREPORTED, while a policy
refusal still raises. A malformed record also leaves its view UNREPORTED, so a
shape error never freezes the published page. Only allowlisted fields leave this
module: names, identifiers, versions, integer ports, statuses, counts and record
dates. Free text such as notes, port settings, unit proposals and role
descriptions is never projected, because it carries host and session labels.
"""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import re
from typing import Any

SCHEMA = "local-architecture-manifest/1"
STATUSES = ("built", "adopted", "candidate", "planned")
PLATFORM = "linux-wsl2-x86_64"
_LIMIT = 8 * 1024 * 1024
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:/+-]{0,119}\Z")
_PRINTABLE = re.compile(r"[^\x00-\x1f\x7f]+\Z")
_EMAIL = re.compile(r"[^\s<>]+@[^\s<>]+\.[A-Za-z]{2,}")
_SECRET = re.compile(r"(?i)\bBearer\s+\S+|\bsk-[A-Za-z0-9_-]{12,}|\bgh[pousr]_[A-Za-z0-9_]+|\bgithub_pat_[A-Za-z0-9_]+")
_HOST_VALUE = re.compile(r"[A-Za-z][A-Za-z0-9-]{2,62}\Z")
_DATE = re.compile(r"(\d{4}-\d{2}-\d{2})(?:T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})?)?\Z")
# Defense in depth for host labels in projected fields; labels a record names
# as a host are added at run time.
_HOST = re.compile(r"(?i)nativestack[a-z0-9_-]*|(?<![a-z0-9])ns\d{4}(?![0-9])")


def _list(value: Any) -> list:
    return value if isinstance(value, list) else []

# Fixed vocabulary for recorded command-center role keys; values are not read.
COMMAND_ROLES = (("foundation_cc", "Foundation command center"),
                 ("trading_command_center", "Trading command center"),
                 ("co_op", "Co-op dispatcher"))

# The desk view's six steps, in order. Each step lists the us-equities catalog
# layers whose recorded titles name that step; the two cross-cutting layers are
# drawn beside the steps. Tests require this map to cover the catalog exactly.
DESK_STAGES = (
    ("data", "Data sources", ("market-data-reference",)),
    ("ingestion", "Ingestion", ("storage-compute", "identity-provenance", "data-quality-orchestration")),
    ("research", "Research layers", ("research-factors-ml", "evaluation-experiments", "agents-models-workers")),
    ("strategy", "Strategy families", ("backtesting-engine",)),
    ("risk", "Risk", ("portfolio-risk",)),
    ("paper", "Paper execution", ("execution-broker",)),
)
DESK_CROSS = ("security-supply-chain", "observability-hosting")
RUNGS = ("sim", "paper", "live")


def layer_status(verdict_status: Any) -> str:
    """Matrix verdict_status: recorded is adopted, pending_lanes is candidate, no_selection is planned."""
    return {"recorded": "adopted", "pending_lanes": "candidate", "no_selection": "planned"}.get(verdict_status, "unreported")


def winner_status(e2e_state: Any) -> str:
    """A verdict winner is built when its linux-wsl2-x86_64 e2e_state is accepted or host_verified."""
    return "built" if e2e_state in ("accepted", "host_verified") else "adopted"


def gate_status(status: Any) -> str:
    """Gate ladder: established is built; not_established, paid_entitlement and user_decision are planned."""
    if status == "established":
        return "built"
    return "planned" if status in ("not_established", "paid_entitlement", "user_decision") else "unreported"


def plan_status(installed: Any) -> str:
    """Install plan: a row its default run installs is adopted; a row it skips is planned."""
    return "adopted" if installed is True else "planned" if installed is False else "unreported"


def _date(value: Any) -> str | None:
    match = _DATE.fullmatch(value) if isinstance(value, str) else None
    return match.group(1) if match else None


class _Projector:
    def __init__(self) -> None:
        self.hosts: set[str] = set()

    def learn_hosts(self, document: Any, depth: int = 0) -> None:
        """Collect values a record labels as a host, so no projection can show them."""
        if depth > 6:
            return
        if isinstance(document, dict):
            for key, value in document.items():
                if key == "host" and isinstance(value, str) and _HOST_VALUE.fullmatch(value) and value.casefold() != "localhost":
                    self.hosts.add(value.casefold())
                else:
                    self.learn_hosts(value, depth + 1)
        elif isinstance(document, list):
            for value in document[:2000]:
                self.learn_hosts(value, depth + 1)

    def private(self, value: str) -> bool:
        folded = value.casefold()
        return bool(_HOST.search(value)) or any(host in folded for host in self.hosts)

    def ident(self, value: Any) -> str | None:
        return value if isinstance(value, str) and _ID.fullmatch(value) and not self.private(value) else None

    def text(self, value: Any, limit: int = 160) -> str | None:
        if not isinstance(value, str):
            return None
        value = " ".join(value.split())
        if len(value) > limit:
            value = value[:limit - 1].rstrip() + "…"
        if not value or self.private(value) or _EMAIL.search(value) or _SECRET.search(value):
            return None
        return value if _PRINTABLE.fullmatch(value) else None

    # Each projection raises on a shape it cannot read; build() reports that view.
    def matrix(self, document: dict, order: list[str]) -> dict:
        rows = document["rows"]
        if not isinstance(rows, list):
            raise TypeError("matrix rows")
        projected, withheld = [], 0
        for row in rows:
            catalog = self.ident(row.get("catalog")) if isinstance(row, dict) else None
            layer_id = self.ident(row.get("layer_id")) if isinstance(row, dict) else None
            verdict = row.get("verdict_status") if isinstance(row, dict) else None
            if not catalog or not layer_id or not isinstance(verdict, str):
                withheld += 1
                continue
            winners = []
            for winner in _list(row.get("winners")):
                identity = self.ident(winner.get("component_id")) if isinstance(winner, dict) else None
                if not identity:
                    continue
                platforms = winner.get("platforms") if isinstance(winner.get("platforms"), dict) else {}
                platform = platforms.get(PLATFORM) if isinstance(platforms.get(PLATFORM), dict) else {}
                state = self.ident(platform.get("e2e_state"))
                winners.append({"id": identity, "pin": self.text(winner.get("pin"), 200),
                                "host_e2e": state, "status": winner_status(state)})
            projected.append({"key": f"{catalog}:{layer_id}", "catalog": catalog, "layer_id": layer_id,
                              "title": self.text(row.get("title"), 120) or layer_id,
                              "verdict_status": self.ident(verdict) or "unreported",
                              "status": layer_status(verdict),
                              "independent_review": self.ident(row.get("independent_review")),
                              "winners": winners})
        rank = {key: index for index, key in enumerate(order)}
        projected.sort(key=lambda row: (rank.get(row["key"], len(rank)), row["key"]))
        verdicts = Counter(row["verdict_status"] for row in projected)
        return {"checked_at": _date(document.get("checked_at")), "rows": projected, "withheld_rows": withheld,
                "verdicts": dict(sorted(verdicts.items())),
                "pending": [row["layer_id"] for row in projected if row["verdict_status"] == "pending_lanes"]}

    def plan(self, document: dict) -> dict:
        owners = document["owners"]
        if not isinstance(owners, list):
            raise TypeError("install plan owners")
        services = []
        for owner in owners:
            service = owner.get("service") if isinstance(owner, dict) else None
            if not isinstance(service, dict) or not service:
                continue
            port = service.get("port")
            port = port if isinstance(port, int) and not isinstance(port, bool) and 0 < port < 65536 else None
            installed = owner.get("installed") if isinstance(owner.get("installed"), bool) else None
            slot = self.ident(owner.get("slot"))
            if not slot:
                continue
            services.append({"slot": slot, "name": self.text(owner.get("owner"), 60) or slot,
                             "layer": self.ident(owner.get("layer")) or "unreported",
                             "release": self.text(owner.get("release"), 40), "port": port,
                             "installed": installed, "status": plan_status(installed)})
        return {"base": self.text(document.get("base"), 60), "revised": _date(document.get("revised_at_utc")),
                "generated": _date(document.get("generated_at_utc")), "services": services}

    def handbook(self, document: dict) -> dict:
        rows = _list(document["profile"]["host_prerequisites"])
        target = next(row for row in rows if isinstance(row, dict) and row.get("id") == "wsl-release-target")
        requirement = target.get("requirement") if isinstance(target.get("requirement"), str) else ""
        match = re.search(r"\bWSL (\d+(?:\.\d+){1,3}) or later\b", requirement)
        titles = {}
        for layer in _list(document.get("layers")):
            identity = self.ident(layer.get("layer_id")) if isinstance(layer, dict) else None
            title = self.text(layer.get("title"), 80) if identity else None
            if title:
                titles[identity] = title
        return {"as_of": _date(document.get("as_of")), "wsl_minimum": match.group(1) if match else None,
                "title": self.text(target.get("title"), 120), "layer_titles": titles}

    def ruleset(self, document: dict) -> dict:
        rules = document["rules"]
        if not isinstance(rules, list):
            raise TypeError("ruleset rules")
        by_type = {rule["type"]: rule.get("parameters") if isinstance(rule.get("parameters"), dict) else {}
                   for rule in rules if isinstance(rule, dict) and isinstance(rule.get("type"), str)}
        checks = _list(by_type.get("required_status_checks", {}).get("required_status_checks"))
        pull = by_type.get("pull_request", {})
        scanning = _list(by_type.get("code_scanning", {}).get("code_scanning_tools"))
        conditions = document.get("conditions") if isinstance(document.get("conditions"), dict) else {}
        refs = _list(conditions["ref_name"].get("include")) if isinstance(conditions.get("ref_name"), dict) else []
        approvals = pull.get("required_approving_review_count")
        return {"name": self.text(document.get("name"), 80), "enforcement": self.ident(document.get("enforcement")),
                "branches": [ref for ref in (self.ident(value) for value in refs) if ref],
                "checks": [check for check in (self.ident(row.get("context")) for row in checks if isinstance(row, dict)) if check],
                "merge_methods": [method for method in (self.ident(value) for value in _list(pull.get("allowed_merge_methods"))) if method],
                "linear_history": "required_linear_history" in by_type, "no_force_push": "non_fast_forward" in by_type,
                "no_deletion": "deletion" in by_type, "thread_resolution": pull.get("required_review_thread_resolution") is True,
                "approvals": approvals if isinstance(approvals, int) and not isinstance(approvals, bool) else None,
                "code_scanning": [{"tool": self.text(row.get("tool"), 40), "threshold": self.ident(row.get("security_alerts_threshold"))}
                                  for row in scanning if isinstance(row, dict) and self.text(row.get("tool"), 40)]}

    def gates(self, document: dict) -> dict:
        gates = document["gates"]
        if not isinstance(gates, list):
            raise TypeError("gate ladder")
        rows = []
        for gate in gates:
            identity = self.ident(gate.get("id")) if isinstance(gate, dict) else None
            if not identity or gate.get("rung") not in RUNGS:
                continue
            recorded = self.ident(gate.get("status")) or "unreported"
            rows.append({"id": identity, "rung": gate["rung"], "layer": self.ident(gate.get("layer")) or "unreported",
                         "title": self.text(gate.get("title"), 200), "recorded": recorded,
                         "status": gate_status(recorded), "required": gate.get("required") is True})
        return {"checked_at": _date(document.get("checked_at")), "gates": rows,
                "established": sum(1 for row in rows if row["recorded"] == "established")}

    def runtime(self, document: dict) -> dict:
        engine = document["engine"]
        practice = document.get("adaptive_practice") if isinstance(document.get("adaptive_practice"), dict) else {}
        repository = engine.get("repository") if isinstance(engine.get("repository"), str) else ""
        brokers = document.get("broker_boundaries") if isinstance(document.get("broker_boundaries"), list) else []
        return {"reviewed_at": _date(document.get("reviewed_at")),
                "engine": {"name": "NautilusTrader" if repository.rstrip("/").endswith("/nautilus_trader") else None,
                           "version": self.text(engine.get("requested_version"), 40), "decision": self.ident(engine.get("decision"))},
                "policies": [policy for policy in (self.ident(value) for value in _list(practice.get("policies"))) if policy],
                "brokers": [broker for broker in (self.ident(row.get("id")) for row in brokers if isinstance(row, dict)) if broker]}


def _orchestration(model: dict) -> dict:
    roles = model.get("command_roles") if isinstance(model.get("command_roles"), dict) else {}
    keys = set(roles.get("keys") or [])
    observation = model.get("adoption_observation") if isinstance(model.get("adoption_observation"), dict) else {}
    verified = observation.get("verified") is True
    rows = [row for row in observation.get("roles") or [] if isinstance(row, dict)] if verified else []

    def total(client: str, field: str) -> int | None:
        values = [row.get(field) for row in rows if row.get("client") == client]
        return sum(values) if verified and all(isinstance(value, int) and not isinstance(value, bool) and value >= 0 for value in values) else None

    hours = observation.get("window_hours")
    lanes = roles.get("lane_count")
    return {"tiers": [{"key": key, "label": label} for key, label in COMMAND_ROLES if key in keys],
            "lane_purposes": lanes if isinstance(lanes, int) and not isinstance(lanes, bool) else None,
            "cc_updated": _date(roles.get("updated_utc")), "snapshot": _date(observation.get("generated_utc")) if verified else None,
            "window_hours": hours if verified and isinstance(hours, int) and not isinstance(hours, bool) else None,
            "codex_lanes": sum(1 for row in rows if row.get("client") == "Codex") if verified else None,
            "codex_conversations": total("Codex", "conversations"),
            "claude_roles": sum(1 for row in rows if row.get("client") == "Claude") if verified else None,
            "claude_sessions": total("Claude", "sessions"),
            "status": "recorded" if keys or verified else "UNREPORTED"}


def _desk(matrix: dict | None, gates: dict | None, runtime: dict | None) -> dict:
    rows = {row["layer_id"]: row for row in (matrix or {}).get("rows", []) if row["catalog"] == "us-equities"}
    by_layer: dict[str, list[dict]] = {}
    for gate in (gates or {}).get("gates", []):
        by_layer.setdefault(gate["layer"], []).append(gate)
    placed = {layer for _, _, layers in DESK_STAGES for layer in layers} | set(DESK_CROSS)

    def items(layer_ids):
        result = []
        for layer_id in layer_ids:
            row = rows.get(layer_id)
            if row and row["verdict_status"] != "recorded":
                result.append({"name": row["title"], "kind": "verdict " + row["verdict_status"].replace("_", " "), "status": row["status"], "layer": layer_id})
            for winner in (row or {}).get("winners", []):
                result.append({"name": winner["id"], "kind": "winner", "status": winner["status"], "layer": layer_id, "host_e2e": winner["host_e2e"]})
            for gate in by_layer.get(layer_id, []):
                result.append({"name": gate["id"], "kind": gate["rung"] + " gate", "status": gate["status"], "layer": layer_id, "title": gate["title"], "recorded": gate["recorded"]})
        return result

    stages = []
    for key, label, layer_ids in DESK_STAGES:
        entries = items(layer_ids)
        if key == "strategy":
            entries += [{"name": policy, "kind": "adaptive policy", "status": None, "layer": "runtime-target"} for policy in (runtime or {}).get("policies", [])]
        if key == "paper":
            entries += [{"name": gate["id"], "kind": gate["rung"] + " gate", "status": gate["status"], "layer": gate["layer"], "title": gate["title"], "recorded": gate["recorded"]}
                        for layer, group in sorted(by_layer.items()) if layer not in placed for gate in group]
        stages.append({"key": key, "label": label, "layers": list(layer_ids), "items": entries})
    cross = [{"layer_id": layer_id, "title": (rows.get(layer_id) or {}).get("title") or layer_id, "items": items((layer_id,))} for layer_id in DESK_CROSS]
    return {"stages": stages, "cross": cross, "focus": "paper",
            "covered_layers": sorted(placed & set(rows)), "unplaced_layers": sorted(set(rows) - placed)}


def build(root: Path, model: dict, reads, sources: tuple, *, pages: dict | None = None, refresh_utc: str | None = None) -> dict:
    """Read the granted manifest records once and project every view's facts."""
    projector, documents, receipts, unreported = _Projector(), {}, [], {}
    for name, relative, role in sources:
        path = root / relative
        if not path.is_file():
            unreported[name] = "record absent from this checkout: " + relative
            continue
        raw, captured = reads.read(role, path, max_bytes=_LIMIT)
        receipt = {"path": relative, "sha256": captured["sha256"], "bytes": captured["bytes"], "role": role,
                   "file_utc": captured.get("file_utc"), "status": "independently authorized Architecture input"}
        try:
            document = json.loads(raw)
        except (UnicodeError, ValueError):
            document = None
        if not isinstance(document, dict):
            unreported[name] = "record is not a JSON object: " + relative
            receipts.append(receipt)
            continue
        documents[name] = document
        receipts.append(receipt)
        projector.learn_hosts(document)
    order = [layer["key"] for layer in model.get("layers", []) if isinstance(layer, dict) and isinstance(layer.get("key"), str)]
    groups = {layer["key"]: layer.get("group") for layer in model.get("layers", []) if isinstance(layer, dict) and isinstance(layer.get("key"), str)}
    views: dict[str, Any] = {}
    for name, project in (("matrix", lambda doc: projector.matrix(doc, order)), ("plan", projector.plan),
                          ("handbook", projector.handbook), ("ruleset", projector.ruleset),
                          ("gates", projector.gates), ("runtime", projector.runtime)):
        if name not in documents:
            continue
        try:
            views[name] = project(documents[name])
        except (KeyError, TypeError, AttributeError, ValueError, StopIteration):
            unreported[name] = "record shape differs from the projected fields"
    for receipt in receipts:
        name = next((key for key, relative, _ in sources if relative == receipt["path"]), None)
        view = views.get(name) or {}
        receipt["checked_at"] = view.get("checked_at") or view.get("revised") or view.get("as_of") or view.get("reviewed_at")
    if "matrix" in views:
        for row in views["matrix"]["rows"]:
            group = groups.get(row["key"])
            row["group"] = projector.ident(group) if isinstance(group, str) else None
    views["orchestration"] = _orchestration(model)
    views["pages"] = {"names": [projector.text(label, 40) for label in (pages or {}).values() if projector.text(label, 40)],
                      "refresh": _date(refresh_utc)}
    views["desk"] = _desk(views.get("matrix"), views.get("gates"), views.get("runtime"))
    matrix = views.get("matrix") or {}
    plan = views.get("plan") or {}
    gates = views.get("gates") or {}
    receipt = {"schema": SCHEMA, "sources": [{key: row.get(key) for key in ("path", "sha256", "bytes", "role", "checked_at")} for row in receipts],
               "unreported": dict(sorted(unreported.items())),
               "layer_cells": len(matrix.get("rows", [])), "verdicts": matrix.get("verdicts"), "pending_layers": matrix.get("pending"),
               "services": len(plan.get("services", [])), "loopback_ports": sum(1 for row in plan.get("services", []) if row["port"]),
               "gates": len(gates.get("gates", [])), "gates_established": gates.get("established")}
    return {"schema": SCHEMA, "views": views, "sources": receipts, "unreported": dict(sorted(unreported.items())), "receipt": receipt}
