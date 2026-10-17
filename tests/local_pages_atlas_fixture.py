"""Shared synthetic roots for the harness atlas suites (test_local_pages_atlas_data, _view and _build).

Fixtures are synthetic records in temporary repo, state and user roots, shaped like the overview suite's catalogs
(tests/test_local_pages_overview.py:38-63), which architecture_manifest.layer_manifest() accepts. The committed
source_policy.json grants paths relative to a root, so the same grants bind the fixture roots. Modules under test load
lazily, so a suite run before they exist fails test by test. No private record or value is used.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "tools/local-pages"
LATEST = "coordination/command-center/skills/token-rate-latest.json"
HISTORY = "coordination/command-center/skills/token-rate-history.json"
_CACHE = {}


def atlas():
    """tools/local-pages/atlas_data.py, loaded once per run; its helpers load through overview_data.load."""
    if "atlas" not in _CACHE:
        spec = importlib.util.spec_from_file_location("atlas_tests_atlas_data", HERE / "atlas_data.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        _CACHE["atlas"] = module
    return _CACHE["atlas"]


def policy():
    """source_policy as atlas_data loaded it, so its error classes match the ones atlas_data raises."""
    return atlas().load("source_policy")


def source_policy():
    """tools/local-pages/source_policy.py loaded on its own: the reader classes exist without atlas_data."""
    if "policy" not in _CACHE:
        spec = importlib.util.spec_from_file_location("atlas_tests_source_policy", HERE / "source_policy.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _CACHE["policy"] = module
    return _CACHE["policy"]


def final_stack():
    def layer(layer_id, title, winners, survivors=0, status="reopened"):
        return {"catalog": "foundation", "layer_id": layer_id, "title": title, "status": status,
                "verdict": {"status": "recorded", "wave": "20990101", "next_review": "2099-02-01", "comparison_id": None, "reopened_by": []},
                "winners": [{"component_id": component, "evidence_class": "native_proven", "verdict_pin": "1.0.0", "run": component, "pin_drift": "same"} for component in winners],
                "survivors": [{"repository": f"github.com/fixture/s{index}"} for index in range(survivors)]}
    return {"checked_at": "2099-01-01",
            "layers": [layer("durable-memory", "Durable memory", ["memory-tool"], survivors=2), layer("token-efficiency", "Context and usage efficiency", ["rtk-fixture"]),
                       layer("code-navigation", "Code navigation", ["nav-tool"]), {**layer("gamma", "Gamma layer", ["tool-d"]), "catalog": "us-equities"}],
            "runs": [{"id": "memory-tool", "pin": "2.4.1"}, {"id": "rtk-fixture", "pin": "a" * 40}, {"id": "nav-tool", "pin": "1.0.0"}, {"id": "tool-d", "pin": "3.0.0"}],
            "index": {"by_component_id": {}, "by_repository": {
                "github.com/fixture/memory-server": [{"catalog": "foundation", "layer_id": "durable-memory", "role": "winner"}],
                "github.com/fixture/nav-server": [{"catalog": "foundation", "layer_id": "code-navigation", "role": "alternate"}],
                "github.com/fixture/eval-server": [{"catalog": "foundation", "layer_id": "quality-evaluation", "role": "winner"}]}},
            "summary": {"final_layers": 0, "status": {"reopened": 4}}}


def matrix():
    def row(catalog, layer_id, components):
        return {"catalog": catalog, "layer_id": layer_id, "winners": [{"component_id": c, "platforms": {"linux-wsl2-x86_64": {"e2e_state": "pending"}}} for c in components],
                "convergence": {"invoke": None, "invoke_reason": "fixture reason"}}
    return {"rows": [row("foundation", "durable-memory", ["memory-tool"]), row("foundation", "token-efficiency", ["rtk-fixture"]),
                     row("foundation", "code-navigation", ["nav-tool"]), row("us-equities", "gamma", ["tool-d"])]}


def slots():
    return {"client_version": "9.9.1", "checked_at": "2099-01-01", "status_values": {"default": "fixture", "trial": "fixture"},
            "slots": [{"id": "auto-memory", "layer_id": "native-clients", "status": "default", "default": "Fixture memory default"},
                      {"id": "prompt-caching", "layer_id": "token-efficiency", "status": "default", "default": "Fixture caching default",
                       "route": "Main conversations get the 1-hour TTL; subagents get 5 minutes; switches invalidate the prefix"},
                      {"id": "hooks", "layer_id": "native-clients", "status": "trial", "default": "Fixture hooks default"}]}


def skill_row(name, digest):
    return {"name": name, "source": "fixture/skills", "ref": "b" * 40, "path": "skills/" + name, "tree_sha": "c" * 40, "skill_md_sha256": digest, "status": "trial"}


SKILL_BYTES = b"# fixture skill\n"
SKILL_SHA = hashlib.sha256(SKILL_BYTES).hexdigest()


def lane(tool_calls=10, mcp=None, **extra):
    return {"actors": 2, "actors_complete": 2, "tool_calls": tool_calls, "mcp": mcp if mcp is not None else {"memory-server": 4, "loose-server": 2},
            "mcp_other": 1, "rtk": {"rewrites": 3, "typed": 0, "shell_calls": 6}, "spawn": {"children": 2, "codex_subagent_sessions": None},
            "models": {"claude-opus-5-5": 9}, "usage": {"input": 10, "output": 5, "cache_read": 990, "cache_creation": 0, "cache_creation_5m": 0,
                                                       "cache_creation_1h": 0, "cache_creation_ttl_unknown": 0},
            "codex_usage": None, "runs": None, "unmeasured": None, "days_measured": 1, **extra}


def latest(days=1, last="2026-10-16"):
    return {"schema": "token-rate-daily/1", "generated_at": "2026-10-17T05:00:00Z",
            "rollup": {"days": 7, "since": "2026-10-10", "until": "2026-10-17", "days_present": days, "days_complete": days,
                       "lanes": {"claude:workflow": lane(), "gpt:codex": {**lane(mcp={}), "usage": None, "codex_usage": {"input": 100, "cached_input": 25, "cache_write": None, "output": 3, "reasoning_output": 1}},
                                 "muse:muse": {**lane(), "actors": None, "tool_calls": None, "mcp": None, "mcp_other": None, "usage": None, "unmeasured": "not_configured"}}},
            "partial_today": None, "measured": {"claude": True, "codex": True, "muse": False},
            "coverage": {"claude_actors": 2, "claude_actors_incomplete": 0, "codex_sessions": 2, "codex_usage_incomplete": 0, "muse_receipts": None},
            "servers": [{"name": "memory-server", "repository": "https://github.com/fixture/memory-server"},
                        {"name": "loose-server", "repository": "https://github.com/fixture/loose-server"},
                        {"name": "nav-server", "repository": "https://github.com/fixture/nav-server"}],
            "history": {"rows": days, "first_date": "2026-10-16", "last_date": last}}


def history(dates=("2026-10-16",)):
    return {"schema": "token-rate-history/1", "cap": 400, "rows": [{"date": day, "complete": True, "collectors": {"claude": "measured", "codex": "measured", "muse": "not_configured"},
                                                                     "lanes": {"claude:workflow": lane()}} for day in dates]}


class Fixture:
    def __init__(self, base: Path, *, projections=True, agents=("stack-verifier",)):
        self.root, self.state, self.user = base / "repo", base / "state", base / "user"
        files = {"catalogs/landscape/final-stack.json": final_stack(),
                 "catalogs/landscape/foundation.json": {"layers": [{"layer_id": "durable-memory", "title": "Durable memory", "requirement": "Keep fixture decisions available."},
                                                                   {"layer_id": "token-efficiency", "title": "Context and usage efficiency", "requirement": "Supply fixture context."},
                                                                   {"layer_id": "code-navigation", "title": "Code navigation", "requirement": "Retrieve fixture source."}]},
                 "catalogs/landscape/us-equities.json": {"layers": [{"layer_id": "gamma", "title": "Gamma layer"}]},
                 "catalogs/landscape/component-evidence-matrix.json": matrix(),
                 ".claude/skills/claude-native-practice/reference/slots.json": slots(),
                 "adoption/skills/manifest.json": {"skills": [skill_row(name, SKILL_SHA) for name in ("frontend-design", "tdd", "codebase-design", "claude-native-practice")]}}
        for relative, document in files.items():
            self.write(self.root / relative, json.dumps(document))
        for name in agents:
            self.write(self.root / f"adoption/agents/claude/{name}.md", f"---\nname: {name}\nmodel: sonnet\neffort: medium\n---\nBody.\n")
        self.write(self.root / ".claude/skills/claude-native-practice/SKILL.md", SKILL_BYTES.decode())
        self.state.mkdir(parents=True, exist_ok=True)
        if projections:
            self.write(self.state / LATEST, json.dumps(latest()))
            self.write(self.state / HISTORY, json.dumps(history()))

    @staticmethod
    def write(path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def model(self, **kwargs):
        return atlas().model(self.root, self.state, commit="0" * 40, user_root=self.user, **kwargs)

    def build(self, base: Path, **kwargs):
        output, receipt = base / "served", base / "custody/atlas/atlas-receipt.json"
        result = atlas().build_atlas_page(self.root, self.state, output, receipt, generated="2099-01-01T00:00:00Z", commit="0" * 40, user_root=self.user, **kwargs)
        return result, (output / "atlas.html").read_text(), receipt
