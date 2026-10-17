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
    """Only recorded is adopted; an old FINAL claim has no current qualification."""
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
                                "host_e2e": state,
                                "status": "unreported" if verdict == "FINAL" else winner_status(state)})
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


# ---------------------------------------------------------------- layer pages
# The Foundation and North-star pages split the per-layer view by landscape
# catalog. Verdicts, run pins and pin drift come from scripts/final_stack.py's
# committed output; host E2E state and invoke evidence from the component
# evidence matrix; requirement text from the catalog. Nothing here re-derives a
# verdict: the four FINAL conditions and the terminal states are read off those
# records as docs/decisions/2026-10-11-layer-resolution-protocol.md defines them.
LAYER_SCHEMA = "local-architecture-layer-manifest/1"
PROTOCOL = "docs/decisions/2026-10-11-layer-resolution-protocol.md"
FINAL_STACK = "catalogs/landscape/final-stack.json"
MATRIX = "catalogs/landscape/component-evidence-matrix.json"
CATALOGS = {"foundation": "catalogs/landscape/foundation.json", "us-equities": "catalogs/landscape/us-equities.json"}
CONDITIONS = (
    ("verdict", "Verdict", "A recorded verdict with its evidence class, verdict wave and next_review."),
    ("run_pin", "Run pin", "Each winner has a run pin in catalogs/landscape/final-stack.json runs[]."),
    ("e2e", "E2E at pin", "An E2E receipt through the upstream's own install and test path, at that run pin."),
    ("invoke", "Invoke", "Invoke evidence in the measured window, or a recorded reason it is not invoked."),
)
STATES = ("FINAL", "SCHEDULED", "RETIRED", "non-terminal")
STATE_RULES = {
    "FINAL": "final_stack.py reports the layer current or converged and every winner meets all four conditions.",
    "SCHEDULED": "No winner, and final-stack.json records the preregistered comparison the layer waits on: its comparison id, "
                 "preregistration hash, readiness trigger and decision rule (verdict.comparison_id, preregistration_sha256, "
                 "readiness_trigger and decision_rule).",
    "RETIRED": "The role is retired with a recorded reason. final-stack.json v1 has no retirement field, so no layer can be shown retired yet.",
    "non-terminal": "Everything else: reopened, unswept, pending lanes or no winner without a scheduled comparison, or a missing condition.",
}
# What a scheduled comparison retains before its run, per the protocol's SCHEDULED rule.
PREREGISTRATION = (("comparison_id", "comparison id"), ("preregistration_sha256", "preregistration hash"),
                   ("readiness_trigger", "readiness trigger"), ("decision_rule", "decision rule"))
DEFINITIVE = ("current", "converged")
E2E_ACCEPTED = ("accepted", "host_verified")
LAYER_PAGES = {
    "foundation": {"catalog": "foundation", "page": "architecture-foundation", "label": "Foundation",
                   "title": "Foundation architecture", "manifest": "architecture-foundation-manifest.json"},
    "north-star": {"catalog": "us-equities", "page": "architecture-north-star", "label": "North star",
                   "title": "North-star trading architecture", "manifest": "architecture-north-star-manifest.json"},
}

# What runs on the workstation, as nodes of the Foundation topology. Each node
# names the foundation layers it belongs to, the run ids whose pins its chips
# show, and repository files that record it. A cited path absent from the
# checkout is reported, never silently kept.
TOPOLOGY = {
    "zones": (("host", "WSL host"), ("remote", "Model providers"), ("github", "GitHub")),
    "nodes": (
        {"id": "lanes", "zone": "host", "name": "CC and lanes", "sub": "Claude lanes; Codex over hcom",
         "layers": ("native-clients", "workers"),
         "chips": (("Claude Code", "claude-code"), ("Codex CLI", "codex"), ("hcom bus", None)),
         "evidence": ("docs/decisions/2026-10-13-command-center-god-view.md", "adoption/new-wsl/client-config-map.json")},
        {"id": "gateway", "zone": "host", "name": "OmniRoute gateway", "sub": "routes every model call", "layers": (), "focal": True,
         "chips": (("OmniRoute", "omniroute"),),
         "evidence": ("adoption/templates/codex.omniroute.config.toml", "blueprints/convergence-practice/omniroute-routing-20260928/README.md")},
        {"id": "providers", "zone": "remote", "name": "Provider slots", "sub": "reached through OmniRoute", "layers": (),
         "chips": (("Codex / GPT", None), ("muse-code", None), ("Anthropic API slots", None)),
         "evidence": ("docs/decisions/2026-10-12-model-effort-routing.md", "docs/decisions/2026-10-12-harbor-parallel-runtimes.md", "tools/adoption/runtime_profiles.py")},
        {"id": "workers", "zone": "host", "name": "Runtime workers", "sub": "SDK workers, ns-run profiles", "layers": ("agent-sdks",),
         "chips": (("OpenHands SDK", None, "github.com/openhands/software-agent-sdk"), ("Codex SDK", "codex"), ("Pi / OpenCode", None), ("DeerFlow", None, "github.com/bytedance/deer-flow"), ("GPT Researcher", None)),
         "evidence": ("blueprints/runtime-workers/openhands/README.md", "blueprints/runtime-workers/skills/README.md", "tools/adoption/runtime_profiles.py", "docs/decisions/2026-10-01-new-wsl-definitive-defaults.md")},
        {"id": "scheduling", "zone": "host", "name": "Scheduling", "sub": "timers and supervised jobs", "layers": ("scheduling-supervision",),
         "chips": (("Dagu", "dagu"), ("systemd", "systemd")),
         "evidence": ("adoption/new-wsl-profile.json", "docs/decisions/2026-10-05-dagu-mise-pin-move.md")},
        {"id": "mcp", "zone": "host", "name": "MCP and memory", "sub": "shared tools and recall", "layers": ("mcp-surfaces", "durable-memory", "semantic-rag"),
         "chips": (("mcporter", "mcporter"), ("ai-memory", "ai-memory"), ("Hindsight", "hindsight"), ("Qdrant", "qdrant")),
         "evidence": ("adoption/new-wsl/client-config-map.json", "adoption/manifest.json")},
        {"id": "telemetry", "zone": "host", "name": "Telemetry", "sub": "OTel, metrics, logs", "layers": ("observation-inference",),
         "chips": (("OTel collector", "opentelemetry-collector-contrib"), ("Prometheus", "prometheus"), ("Loki", "loki"), ("Grafana", "grafana")),
         "evidence": ("adoption/new-wsl-profile.json", "evidence/artifacts/new-wsl-install-plan-20261002/install-plan.json")},
        {"id": "backup", "zone": "host", "name": "Backup", "sub": "off-host snapshots", "layers": ("recovery-portability",),
         "chips": (("restic", "restic"),),
         "evidence": ("adoption/lifecycle.md",)},
        {"id": "github", "zone": "github", "name": "GitHub automation", "sub": "pull requests, checks, ruleset", "layers": ("git-github-automation", "ci-supply-chain"),
         "chips": (("gh", "gh"), ("Actions workflows", None), ("main ruleset", None)),
         "evidence": (".github/main-ruleset.json", ".github/workflows/validate.yml")},
    ),
    # (from, to, label); the view draws a connector only where it stays orthogonal and clear.
    "edges": (("lanes", "gateway", "MODEL CALLS"), ("gateway", "providers", "HTTPS"), ("lanes", "workers", "DISPATCH"), ("scheduling", "workers", "TIMERS")),
    "focal_edge": ("gateway", "providers"),
}

# The north-star data flow: lanes are the paths data takes, steps run left to right.
FLOW = {
    "lanes": (("collector", "Owned collector"), ("account-c", "Account C"), ("ibkr", "IBKR"), ("history", "History")),
    "steps": ("Feeds", "Collect", "Rank", "Trade", "Broker"),
    "focal_step": 2,
    "nodes": (
        {"id": "feeds", "lane": "collector", "step": 0, "name": "Feeds", "sub": "Alpaca SIP and OPRA", "tool": "FINRA free data", "layers": ("market-data-reference",),
         "evidence": ("catalogs/us-equities/ns-movers-phase0-decisions-20261009.json", "blueprints/us-equities/incentive-monitor/README.md")},
        {"id": "l0", "lane": "collector", "step": 1, "name": "L0 raw log", "sub": "owned collector", "layers": ("storage-compute",), "evidence": ()},
        {"id": "k1", "lane": "collector", "step": 2, "name": "K1 ranking", "sub": "reads the L0 log", "layers": ("research-factors-ml",), "focal": True, "evidence": ()},
        {"id": "lanes-ab", "lane": "collector", "step": 3, "name": "Lanes A and B", "sub": "adaptive-paper", "tool": "NautilusTrader", "layers": ("execution-broker",),
         "evidence": ("blueprints/us-equities/adaptive-paper/README.md", "docs/decisions/2026-10-13-lane-a-frozen-field-continuity.md", "docs/decisions/2026-10-13-lane-b-concurrent-presets.md")},
        {"id": "alpaca", "lane": "collector", "step": 4, "name": "Alpaca", "sub": "paper accounts", "tool": "alpaca-py", "layers": ("execution-broker",),
         "evidence": ("catalogs/us-equities/runtime-target.json", "docs/paper-lane-policy.md")},
        {"id": "account-c", "lane": "account-c", "step": 3, "name": "MCP trader and calc", "sub": "account C", "layers": ("agents-models-workers",),
         "evidence": ("evidence/artifacts/trading-handbook-20261013/agent-lane-calculator-policy-spec-v1-20261013.md",)},
        {"id": "ibkr-feed", "lane": "ibkr", "step": 0, "name": "IBKR data", "sub": "TWS API", "tool": "market data", "layers": ("market-data-reference",),
         "evidence": ("catalogs/us-equities/runtime-target.json",)},
        {"id": "ibkr-lane", "lane": "ibkr", "step": 3, "name": "IBKR lane", "sub": "NautilusTrader", "tool": "IBKR adapter", "layers": ("execution-broker",),
         "evidence": ("blueprints/us-equities/engine-nautilus/ibkr-paper-orders/README.md",)},
        {"id": "ibkr-broker", "lane": "ibkr", "step": 4, "name": "IBKR", "sub": "paper account", "tool": "TWS API", "layers": ("execution-broker",),
         "evidence": ("catalogs/us-equities/runtime-target.json", "docs/paper-lane-policy.md")},
        {"id": "history", "lane": "history", "step": 1, "name": "History", "sub": "historical bars", "tool": "Alpaca SIP", "layers": ("storage-compute",),
         "evidence": ("blueprints/us-equities/alpaca-historical/README.md",)},
        {"id": "templates", "lane": "history", "step": 2, "name": "Strategy templates", "sub": "backtest and paper", "tool": "risk presets", "layers": ("backtesting-engine",),
         "evidence": ("blueprints/us-equities/strategies/README.md",)},
        {"id": "backtest", "lane": "history", "step": 3, "name": "BacktestNode", "sub": "NautilusTrader", "tool": "history replay", "layers": ("backtesting-engine",),
         "evidence": ("blueprints/us-equities/runtime-2604/receipts/backtest-pipeline-20261008.json",)},
    ),
    "edges": (("feeds", "l0", None), ("l0", "k1", None), ("k1", "lanes-ab", "RANKED"), ("lanes-ab", "alpaca", None), ("account-c", "alpaca", None),
              ("ibkr-feed", "ibkr-lane", None), ("ibkr-lane", "ibkr-broker", None), ("history", "templates", None), ("templates", "backtest", None)),
    "focal_edge": ("k1", "lanes-ab"),
}

# The data-layer decisions of 2026-10-14 are recorded in a sealed private
# command-center convergence record and its first addendum, cited by name only.
# Each row paraphrases one recorded decision, in record order, and names the
# data-flow element it bears on (None for a decision about the research process).
# Cited files are repository leads at the build commit, not the decision text.
DECISION_RECORDS = {
    "record": "CONVERGENCE-CC-20261014.md",
    "addendum-01": "CONVERGENCE-CC-20261014.addendum-01.md",
}
# (id, record key, topic, paraphrase, flow node, repository leads)
DATA_DECISIONS = (
    ("CC-1", "record", "hub", "The owned hub stays the plan for the agreed zero-spend tier: one collector per stream allowance "
     "writes the L0 raw log first and the NautilusTrader catalog is built from it, the K1 ranker runs outside NautilusTrader nodes, "
     "one versioned state serves the traders and the exit gateway, and the data vendor does not change.", "l0", ()),
    ("CC-2", "record", "tier-1-additions", "Four zero-spend additions follow, each as its own reviewed pull request through the hub gates: "
     "news for every symbol once the pre-market probe shows it does not use the stock allowance, TRF/ADF print features in K1, "
     "EDGAR filing discovery as a catalyst input within the SEC fair-access limit, and the borrow check on the IBKR lane.", "feeds", ()),
    ("CC-3", "record", "tier-spend", "Nothing is bought from the paid tiers (2 and 3) now; each purchase first needs a measured gap, "
     "and paying for it is for the owner to approve.", "feeds", ()),
    ("CC-4", "record", "engine-pin", "NautilusTrader remains the engine. Its v2.0.0rc6 release cannot take the in-house Alpaca "
     "transport through the v2 API, so that release is used for screening only.", "lanes-ab",
     ("blueprints/us-equities/engine-nautilus/ibkr-paper-orders/README.md",)),
    ("CC-5", "record", "ranking-target", "Ranking the whole market within 1 s is a target that K1 has to measure, not a claim.", "k1", ()),
    ("CC-6", "record", "fourth-arm", "The fourth research arm joins through an addendum after its re-run, with the blind judging "
     "repeated over four arms; the record itself stays sealed.", None, ()),
    ("A01-1", "addendum-01", "disconnect-events", "The full-session probe and the shadow L0 and K1 run log every 406 and 407 "
     "rejection as well as reconnect gaps.", "l0", ()),
    ("A01-2", "addendum-01", "tier-1-later", "Two more zero-spend additions are queued as later hub items, each a reviewed pull "
     "request: FINRA short interest as a free daily reference join, and a bounded OPRA set for candidate underlyings within the "
     "plan's option-quote subscriptions, only once the stock collector is accepted.", "feeds", ()),
    ("A01-3", "addendum-01", "allowance-topology", "An observation in production, not yet a measurement, supports one stream "
     "allowance per paper account: two lanes streamed SIP at the same time on their own accounts with no 406 reported. The formal "
     "measurement still counts 406s for concurrent connections across accounts.", "feeds", ()),
    ("A01-4", "addendum-01", "unchanged", "Everything else stands: no paid-tier purchase, NautilusTrader kept with rc6 for "
     "screening only, the 1 s whole-market ranking still a target K1 measures, and only the public alpaca-py API.", "alpaca", ()),
)
PENDING_STUDY = {
    "title": "Pre-ranked feeds and overlap study: pending",
    "trigger": "The sealed WS2 arms and the WS3 records exist.",
    "content": "Arrives in a follow-up pull request once the trigger holds; no result is shown before then.",
}


def _present(root: Path, refs, tracked: frozenset | None = None) -> tuple[list[str], list[str]]:
    """Split repository references into present and absent files; anchors are kept.

    With `tracked`, the paths of the cited commit's tree, presence is read at that
    commit; without it, from the checkout.
    """
    present, absent = [], []
    for ref in refs or ():
        if not isinstance(ref, str) or not ref or ref.startswith(("/", "~", "http:", "https:")) or ".." in ref.split("#", 1)[0].split("/"):
            continue
        path = ref.split("#", 1)[0]
        found = path in tracked if tracked is not None else (root / path).is_file()
        (present if found else absent).append(ref)
    return present, absent


def _matrix_index(matrix: dict) -> dict:
    index = {}
    for row in _list(matrix.get("rows")):
        if isinstance(row, dict):
            index[(row.get("catalog"), row.get("layer_id"))] = row
    return index


def winner_conditions(layer: dict, winner: dict, run: dict | None, matrix_row: dict) -> dict:
    """The four FINAL conditions for one winner, each with what holds or is missing."""
    verdict = layer.get("verdict") or {}
    absent = [label for label, value in (("verdict recorded", verdict.get("status") == "recorded"), ("evidence class", winner.get("evidence_class")),
                                         ("verdict wave", verdict.get("wave")), ("next_review", verdict.get("next_review"))) if not value]
    verdict_detail = (f"{winner.get('evidence_class')}, wave {verdict.get('wave')}, next review {verdict.get('next_review')}" if not absent
                      else "missing " + ", ".join(absent) + f" (verdict {verdict.get('status') or 'absent'})")
    run_detail = (f"{run['id']} {run.get('pin')} from {run.get('source')}" if run
                  else f"no run pin ({winner.get('run_reason') or 'unresolved'})")
    platform = {}
    for row in _list(matrix_row.get("winners")):
        if isinstance(row, dict) and row.get("component_id") == winner.get("component_id"):
            platforms = row.get("platforms") if isinstance(row.get("platforms"), dict) else {}
            platform = platforms.get(PLATFORM) if isinstance(platforms.get(PLATFORM), dict) else {}
            break
    state, drift = platform.get("e2e_state"), winner.get("pin_drift")
    e2e_met = state in E2E_ACCEPTED and drift == "same"
    if e2e_met:
        e2e_detail = f"{state} on {PLATFORM} at the verdict pin, which the run pin matches"
    elif state not in E2E_ACCEPTED:
        e2e_detail = f"{PLATFORM} E2E state {state or 'unreported'}"
    elif run is None:
        e2e_detail = f"{state} at verdict pin {winner.get('verdict_pin')}; no run pin to bind it to"
    else:
        e2e_detail = f"{state} at verdict pin {winner.get('verdict_pin')}; run pin {run.get('pin')} " + ("differs" if drift == "differs" else "drift unknown")
    convergence = matrix_row.get("convergence") if isinstance(matrix_row.get("convergence"), dict) else {}
    invoke, not_invoked = convergence.get("invoke"), convergence.get("not_invoked_reason")
    calls = invoke.get("calls") if isinstance(invoke, dict) else invoke
    called = isinstance(calls, int) and not isinstance(calls, bool) and calls > 0
    excused = isinstance(not_invoked, str) and bool(not_invoked.strip())
    invoke_met = called or excused
    if called:
        invoke_detail = f"{calls} recorded calls in the matrix"
    elif excused:
        invoke_detail = "not invoked; the matrix records the reason: " + not_invoked.strip()
    else:
        invoke_detail = ("zero recorded calls, a wiring defect or a role to retire" if calls == 0 and invoke is not None
                         else "no invoke evidence; the matrix records: " + str(convergence.get("invoke_reason") or "no reason"))
    return {"verdict": {"met": not absent, "detail": verdict_detail}, "run_pin": {"met": run is not None, "detail": run_detail},
            "e2e": {"met": e2e_met, "detail": e2e_detail}, "invoke": {"met": invoke_met, "detail": invoke_detail}}


def layer_state(layer: dict, conditions: list[dict]) -> tuple[str, list[str]]:
    """Terminal state per the resolution protocol, and what keeps the layer from FINAL."""
    status, verdict, winners = layer.get("status"), layer.get("verdict") or {}, layer.get("winners") or []
    met = {key: bool(conditions) and all(row[key]["met"] for row in conditions) for key, _, _ in CONDITIONS}
    if winners and status in DEFINITIVE and all(met.values()):
        return "FINAL", []
    preregistration = [label for field, label in PREREGISTRATION if not verdict.get(field)]
    if not winners and not preregistration:
        return "SCHEDULED", []
    missing = []
    if not winners and verdict.get("comparison_id"):
        missing.append(f"comparison {verdict['comparison_id']} lacks its " + ", ".join(preregistration))
    if status == "reopened":
        missing.append("reopened by " + ", ".join(sweep.get("sweep_id", "a sweep") for sweep in verdict.get("reopened_by") or []) if verdict.get("reopened_by") else "reopened by a later sweep")
    elif status == "unswept":
        missing.append("no completed sweep covers the layer")
    elif status == "no-winner":
        missing.append(f"no winner and no scheduled comparison (verdict {verdict.get('status') or 'absent'})")
    if not winners:
        missing.append("no recorded winner to meet the four conditions")
    for key, label, _ in CONDITIONS:
        if winners and not met[key]:
            if key == "invoke":
                # Invoke evidence is recorded per layer in the matrix, so its reason is stated once.
                missing.append(f"{label}: {conditions[0][key]['detail']}")
            else:
                missing.append(f"{label}: {sum(1 for row in conditions if row[key]['met'])} of {len(conditions)} winners")
    return "non-terminal", missing


def layer_manifest(root: Path, page: str, final_stack: dict, catalog: dict, matrix: dict, *, commit: str | None,
                   sources: list[dict], flags: dict | None, tracked: frozenset | None = None) -> dict:
    """Project one page's layers, items, diagram nodes and drift flags from the read records.

    `tracked` holds the paths of `commit`'s tree; evidence presence is read there
    when given, and from the checkout otherwise (recorded as evidence_checked_at).
    """
    config = LAYER_PAGES[page]
    catalog_id = config["catalog"]
    current = [layer for layer in _list(final_stack.get("layers"))
               if isinstance(layer, dict) and layer.get("catalog") == catalog_id]
    current += _list(catalog.get("layers"))
    current += [row for row in _list(matrix.get("rows"))
                if isinstance(row, dict) and row.get("catalog") == catalog_id]
    if any(isinstance(layer, dict) and "FINAL" in (layer.get("terminal_state"), layer.get("verdict_status"),
                                                  (layer.get("verdict") or {}).get("status"))
           for layer in current):
        raise ValueError("FINAL snapshot requires a successful current admission check")
    catalog_rows = {row.get("layer_id"): (index, row) for index, row in enumerate(_list(catalog.get("layers"))) if isinstance(row, dict)}
    runs = {run.get("id"): run for run in _list(final_stack.get("runs")) if isinstance(run, dict)}
    matrix_rows = _matrix_index(matrix)
    layers, items, planned = [], [], []
    # Catalog order, so the page reads like the catalog; planned layers keep final-stack order after it.
    ordered = sorted(enumerate(_list(final_stack.get("layers"))), key=lambda pair: (catalog_rows.get(pair[1].get("layer_id"), (len(catalog_rows),))[0]
                                                                                if isinstance(pair[1], dict) else len(catalog_rows), pair[0]))
    for position, layer in ordered:
        if not isinstance(layer, dict) or layer.get("catalog") != catalog_id:
            continue
        key = f"{catalog_id}/{layer.get('layer_id')}"
        if layer.get("layer_id") not in catalog_rows:
            planned.append({"layer": key, "title": layer.get("title"), "status": layer.get("status"), "source": layer.get("source")})
            continue
        index, row = catalog_rows[layer["layer_id"]]
        matrix_row = matrix_rows.get((catalog_id, layer["layer_id"])) or {}
        winners = [winner for winner in _list(layer.get("winners")) if isinstance(winner, dict)]
        conditions = [winner_conditions(layer, winner, runs.get(winner.get("run")), matrix_row) for winner in winners]
        state, missing = layer_state(layer, conditions)
        verdict = layer.get("verdict") or {}
        wave_doc = (verdict.get("wave_doc") or {}).get("path")
        layer_refs = [f"{CATALOGS[catalog_id]}#/layers/{index}", f"{FINAL_STACK}#/layers/{position}", MATRIX] + ([wave_doc] if wave_doc else [])
        cited, outside = _present(root, row.get("evidence_refs"), tracked)
        present, absent = _present(root, layer_refs, tracked)
        gaps = [gap for gap in _list(row.get("open_gaps")) if isinstance(gap, str)]
        record = {"layer": key, "layer_id": layer["layer_id"], "title": layer.get("title") or row.get("title"),
                  "current_choice": row.get("current_choice"), "final_stack_status": layer.get("status"),
                  "verdict": {"status": verdict.get("status"), "wave": verdict.get("wave"), "date": verdict.get("date"),
                              "next_review": verdict.get("next_review"), "comparison_id": verdict.get("comparison_id"),
                              "reopened_by": [sweep.get("sweep_id") for sweep in verdict.get("reopened_by") or [] if isinstance(sweep, dict)]},
                  "overturn_when": row.get("overturn_when"), "open_gaps": gaps, "open_gap_count": len(gaps),
                  "conditions": {condition: bool(conditions) and all(entry[condition]["met"] for entry in conditions) for condition, _, _ in CONDITIONS},
                  "state": state, "missing": missing, "evidence_refs": present + cited, "absent_refs": absent,
                  "refs_outside_repository": len(outside) + len([ref for ref in row.get("evidence_refs") or [] if isinstance(ref, str) and ref.startswith(("/", "~", "http"))]),
                  "winners": []}
        for winner, entry in zip(winners, conditions):
            run = runs.get(winner.get("run"))
            run_refs, _ = _present(root, [run.get("source")] if run else [], tracked)
            winner_record = {"component": winner.get("component_id"), "repository": winner.get("repository"),
                             "pin": {"verdict": winner.get("verdict_pin"), "run": run.get("pin") if run else None, "run_id": winner.get("run"),
                                     "run_source": run.get("source") if run else None, "pin_drift": winner.get("pin_drift"), "run_reason": winner.get("run_reason")},
                             "evidence_class": winner.get("evidence_class"), "conditions": entry,
                             "missing": [label for key, label, _ in CONDITIONS if not entry[key]["met"]]}
            record["winners"].append(winner_record)
            items.append({"layer": key, "component": winner_record["component"], "repository": winner_record["repository"],
                          "pin": winner_record["pin"], "evidence_class": winner_record["evidence_class"],
                          "evidence_refs": present + run_refs + cited, "state": state,
                          "missing_conditions": [key for key, _, _ in CONDITIONS if not entry[key]["met"]],
                          "missing": [entry[key]["detail"] for key, _, _ in CONDITIONS if not entry[key]["met"]] + [reason for reason in missing if not reason.split(":", 1)[0] in {label for _, label, _ in CONDITIONS}]})
        if not winners:
            items.append({"layer": key, "component": None, "repository": None, "pin": None, "evidence_class": None,
                          "evidence_refs": present + cited, "state": state, "missing_conditions": [key for key, _, _ in CONDITIONS], "missing": missing})
        layers.append(record)
    prefix = catalog_id + "/"
    drift = {}
    if isinstance(flags, dict):
        drift = {"pin_drift": [line for line in flags.get("pin_drift") or [] if line.startswith(prefix)],
                 "pin_drift_unknown": [line for line in flags.get("pin_drift_unknown") or [] if line.startswith(prefix)],
                 "without_run": {reason: [line for line in lines if line.startswith(prefix)] for reason, lines in (flags.get("without_run") or {}).items()},
                 "past_next_review": [row for row in flags.get("past_next_review") or [] if isinstance(row, dict) and str(row.get("layer", "")).startswith(prefix)] if flags.get("past_next_review") is not None else None,
                 "today": flags.get("today"),
                 "totals": {"pin_drift": len(flags.get("pin_drift") or []), "pin_drift_unknown": len(flags.get("pin_drift_unknown") or []),
                            "without_run": sum(len(lines) for lines in (flags.get("without_run") or {}).values())}}
    states = {state: sum(1 for layer in layers if layer["state"] == state) for state in STATES}
    document = {"schema": LAYER_SCHEMA, "page": config["page"], "catalog": catalog_id, "commit": commit,
                "evidence_checked_at": commit if tracked is not None and commit else "checkout",
                "protocol": PROTOCOL, "producer": "scripts/final_stack.py (committed output and its --check flags)",
                "definitions": {"conditions": [{"key": key, "label": label, "rule": rule} for key, label, rule in CONDITIONS],
                                "states": [{"state": state, "rule": STATE_RULES[state]} for state in STATES]},
                "sources": sources,
                "summary": {"layers": len(layers), "states": states, "finalized": states["FINAL"],
                            "conditions_met": {key: sum(1 for layer in layers if layer["conditions"][key]) for key, _, _ in CONDITIONS},
                            "items": len(items)},
                "layers": layers, "items": items, "planned_layers": planned, "flags": drift}
    layer_states = {layer["layer_id"]: layer["state"] for layer in layers}
    run_pins = {run_id: run.get("pin") for run_id, run in runs.items()}
    run_repositories = {run_id: run.get("repository") for run_id, run in runs.items()}
    by_repository = ((final_stack.get("index") or {}).get("by_repository") or {}) if isinstance(final_stack.get("index"), dict) else {}
    rank = {role: position for position, role in enumerate(("winner", "alternate", "survivor", "candidate"))}

    def catalog_role(repository: str | None) -> dict:
        """The chip's strongest role in final-stack.json's index, this page's catalog first."""
        entries = [entry for entry in _list(by_repository.get(repository)) if isinstance(entry, dict) and entry.get("role") in rank] if repository else []
        here = [entry for entry in entries if entry.get("catalog") == catalog_id]
        chosen = min(here or entries, key=lambda entry: (rank[entry["role"]], entry.get("layer_id", "")), default=None)
        if chosen is None:
            return {"role": None, "layer": None, "winner_here": False}
        return {"role": chosen["role"], "layer": f"{chosen.get('catalog')}/{chosen.get('layer_id')}", "winner_here": bool(here) and chosen["role"] == "winner"}

    def nodes(spec_nodes, chips: bool):
        projected = []
        for node in spec_nodes:
            present, absent = _present(root, node.get("evidence"), tracked)
            states_here = [layer_states[layer] for layer in node.get("layers", ()) if layer in layer_states]
            entry = {key: node.get(key) for key in ("id", "zone", "lane", "step", "name", "sub", "tool") if node.get(key) is not None}
            entry.update(layers=list(node.get("layers", ())), state=(min(states_here, key=STATES.index) if states_here and len(set(states_here)) == 1 else "non-terminal" if states_here else None),
                         focal=bool(node.get("focal")), evidence_refs=present, absent_refs=absent, recorded=bool(present))
            if chips:
                entry["chips"] = []
                for chip in node.get("chips", ()):
                    name, run_id = chip[0], chip[1]
                    repository = run_repositories.get(run_id) if run_id else (chip[2] if len(chip) > 2 else None)
                    entry["chips"].append({"name": name, "run_id": run_id, "pin": run_pins.get(run_id) if run_id else None,
                                           "repository": repository, **catalog_role(repository)})
            projected.append(entry)
        return projected

    if page == "foundation":
        document["topology"] = {"catalog": catalog_id, "zones": [{"id": key, "label": label} for key, label in TOPOLOGY["zones"]],
                                "nodes": nodes(TOPOLOGY["nodes"], True),
                                "edges": [{"from": a, "to": b, "label": label} for a, b, label in TOPOLOGY["edges"]],
                                "focal_edge": list(TOPOLOGY["focal_edge"])}
    else:
        document["flow"] = {"lanes": [{"id": key, "label": label} for key, label in FLOW["lanes"]], "steps": list(FLOW["steps"]),
                            "focal_step": FLOW["focal_step"], "nodes": nodes(FLOW["nodes"], False),
                            "edges": [{"from": a, "to": b, "label": label} for a, b, label in FLOW["edges"]], "focal_edge": list(FLOW["focal_edge"])}
        names = {node["id"]: node["name"] for node in FLOW["nodes"]}
        decisions = []
        for ident, record, topic, text, node, refs in DATA_DECISIONS:
            present, absent = _present(root, refs, tracked)
            decisions.append({"id": ident, "topic": topic, "decision": text, "element": names.get(node, node) if node else None,
                              "recorded_in": DECISION_RECORDS[record], "evidence_refs": present, "absent_refs": absent})
        document["decisions"] = {"date": "2026-10-14", "records": list(DECISION_RECORDS.values()),
                                 "citation": "private command-center records, cited by name; each row is a paraphrase", "rows": decisions}
        document["pending_study"] = dict(PENDING_STUDY)
    return document


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
