"""Contracts for the consolidated command-center page and its composer wiring."""

from __future__ import annotations

import copy
from datetime import datetime, timezone
import hashlib
import html
from html.parser import HTMLParser
import importlib.util
import json
import os
from pathlib import Path
import re
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.parse import unquote

from tests import test_local_pages as composer_fixture


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("local_pages_command_center_view", ROOT / "tools/local-pages/command_center_view.py")
view = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(view)
POLICY_SPEC = importlib.util.spec_from_file_location("local_pages_command_center_policy", ROOT / "tools/local-pages/source_policy.py")
FLEET_SPEC = importlib.util.spec_from_file_location("local_pages_command_center_fleet", ROOT / "tools/local-pages/fleet_data.py")
fleet_data = importlib.util.module_from_spec(FLEET_SPEC)
FLEET_SPEC.loader.exec_module(fleet_data)
policy = importlib.util.module_from_spec(POLICY_SPEC)
POLICY_SPEC.loader.exec_module(policy)
BUILDER = composer_fixture.BUILDER
SYNTHETIC_HOME = "/".join(["", "home", "synthetic-user", "work"])
# The last five forms are the #1012 Claude read's B1 cases: an HTML5 entity, encoded dots,
# double percent-encoding and a semicolon-less numeric reference.
AT = "@"  # joined at run time, so the repository holds no email-shaped literal
SYNTHETIC_EMAILS = ("owner" + AT + "example.org", "owner%40example.org", "owner&#64;example.org", "owner&commat;example.org",
                    "owner" + AT + "example%2Eorg", "owner" + AT + "example&#46;org", "owner%2540example.org", "owner&#64example.org")
PLAIN_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
HOSTILE = '<script>alert(1)</script>"><img src=x onerror=alert(2)>'
PANELS = ("cc-sessions", "cc-orchestration", "cc-prs", "cc-landscape", "cc-skills", "cc-tokens", "cc-research", "cc-manifests", "cc-owner")
REFRESHED = "2026-10-11T16:00:00Z"


QUOTED_PROBE = '"reviewer"' + AT + 'example.org'  # Astra's first read of a737ef98, review_probes.py:24
# Local parts RFC 5322 allows that the a737ef98 mask missed in whole or in part; each part is unique, so a test can
# assert that no part of the address survives without using any address grammar.
WHOLE_ADDRESS_FORMS = ('"zqlocalone"' + AT + "zqdomainone.example.org", '"zqlocal two"' + AT + "zqdomaintwo.example.org", "%22zqlocalthree%22%40zqdomainthree.example.org",
                       "&quot;zqlocal four&quot;&#64;zqdomainfour.example.org", "zq!localfive" + AT + "zqdomainfive.example.org", "{zqlocalsix}" + AT + "zqdomainsix.example.org",
                       "zq'localseven%40zqdomainseven.example.org")
WHOLE_ADDRESS_PARTS = ("zqlocal", "zqdomain")


def decoded_text(markup: str) -> str:
    """The whole page as a reader sees it after two rounds of HTML and percent decoding, not split into tokens."""
    for _ in range(2):
        markup = html.unescape(unquote(markup))
    return markup


def surviving_parts(markup: str) -> list[str]:
    """Which planted address parts remain anywhere in the decoded page."""
    text = decoded_text(markup)
    return [part for part in WHOLE_ADDRESS_PARTS if part in text]


def leaked_emails(markup: str) -> list[str]:
    """Emails in the page after decoding each token twice, as a browser or a copy-paste could."""
    found = []
    for token in re.findall(r"[^\s<>\"']+", markup):
        decoded = token
        for _ in range(2):
            decoded = html.unescape(unquote(decoded))
        found.extend(PLAIN_EMAIL.findall(decoded))
    return found


class Tables(HTMLParser):
    """Collect each table's caption and its rows of cell text."""

    def __init__(self) -> None:
        super().__init__()
        self.tables: dict[str, list[list[str]]] = {}
        self.caption: str | None = None
        self.rows: list[list[str]] | None = None
        self.cell: str | None = None
        self.in_caption = False

    def handle_starttag(self, tag: str, attributes: list) -> None:
        if tag == "table":
            self.rows, self.caption = [], ""
        elif tag == "caption":
            self.in_caption = True
        elif tag == "tr" and self.rows is not None:
            self.rows.append([])
        elif tag in ("th", "td") and self.rows is not None:
            self.cell = ""
        elif self.cell is not None:
            self.cell += " "

    def handle_endtag(self, tag: str) -> None:
        if tag == "caption":
            self.in_caption = False
        elif tag in ("th", "td") and self.cell is not None and self.rows:
            self.rows[-1].append(" ".join(self.cell.split()))
            self.cell = None
        elif tag == "table" and self.rows is not None:
            self.tables[self.caption] = self.rows
            self.rows = None
        elif self.cell is not None:
            self.cell += " "

    def handle_data(self, data: str) -> None:
        if self.in_caption:
            self.caption += data
        elif self.cell is not None:
            self.cell += data


def tables(markup: str) -> dict[str, list[list[str]]]:
    parser = Tables()
    parser.feed(markup)
    return parser.tables


def table(markup: str, prefix: str) -> list[list[str]]:
    found = [rows for caption, rows in tables(markup).items() if caption.startswith(prefix)]
    if len(found) != 1:
        raise AssertionError(f"expected one table starting {prefix!r}, found {len(found)}")
    return found[0]


def section(markup: str, anchor: str) -> str:
    start = markup.index(f'<section class="cc-panel" id="{anchor}"')
    return markup[start:markup.index("</section>", start)]


def current_fixture() -> dict:
    return {
        "schema": "cc-now/1", "updated_utc": "2026-10-11T13:58:58Z", "headline": "Fixture command-center headline",
        "in_review": [
            {"pr": "#101", "what": "fixture recorded row", "state": "micro running", "head": "abc12345", "round": 3,
             "next_gate": "Astra micro at abc12345", "blockers": ["P2 reinstall race"], "follow_ups": ["one re-pin", "sync live copy"]},
            {"pr": "#102", "what": "fixture unrecorded row", "state": "reads queued"},
            {"pr": "#103 / #104", "what": "fixture empty lists", "state": "clean", "blockers": [], "follow_ups": []},
            {"pr": "#105", "what": "fixture unsupported values", "state": "odd", "head": 7.5, "round": -1, "blockers": 5, "follow_ups": {"x": 1}},
        ],
        "landings_today": ["#90", "#91 (G6a)"],
        "cc_agents": {"running": ["cc-fixture-builder (#101 round 3, resumed)", {"name": "cc-fixture-micro", "task": "#102 micro", "model": "claude-opus-5-5"}, "cc-bare"]},
        "waiting_on_owner": [
            {"what": "Approve the fixture lane", "by_utc": "2026-10-12T13:00:00Z"},
            {"what": "Rotate a fixture token", "since_utc": "2026-10-11T05:29:00Z", "detail": "Run the fixture command"},
            {"what": "Read the fixture note"},
        ],
        "token_efficiency": {"rtk": {"commands": "1200", "input_tokens": "10.0M", "tokens_saved": {"value": "2.5M", "share_percent": 25.0}},
                             "rtk_hook_audit_7d": {"invocations": 9, "rewrites": 4, "skips": 5}, "headroom_24h": "no calls in 24 h",
                             "fix": "Fixture CC note"},
        "token_use_24h": {"source": "fixture Prometheus increase()", "window": "2026-10-10T00:00:00Z to 2026-10-11T00:00:00Z",
                          "codex_top_lanes_M": [["lane-a", 40.0], ["lane-b", 10.0], ["bad"], ["lane-c", -1]],
                          "note": "Fixture usage note"},
        "orchestration": {"slot": "orchestration-frameworks", "default": "native composition without a framework layer", "state": "adjudicated default",
                          "evidence": "slots-final.json row", "next": "paired-ao-prcycle preregistered"},
        "landing_queue": [{"pr": "uet#78", "head": "4b472bcd", "state": "CI on the rebased head", "since_utc": "15:38Z"},
                          {"pr": "#1004", "head": "23cd8e7a", "state": "waits for the GPT micro", "since_utc": "2026-10-11T15:00:00Z"}],
        "program": [{"ws": "WS1", "title": "Stars finalized", "owner": "g5-stars-gap lane", "state": "blocked on #978", "gate": "#978 lands", "reopen": "a new star"},
                    {"ws": "WS2", "title": "Second stream", "state": "running"}],
        "mirrors": {"count": 112, "manifest_rows": 112, "synced_utc": "2026-10-11T15:28:49Z", "failed": [],
                    "pins": {"openai/codex": {"ref": "rust-v0.155.1", "commit": "abcdef123456", "synced_at_utc": "2026-10-11T15:28:33Z"},
                             "Fixture/Drifted": {"ref": "v2.0.0", "commit": "0123456789ab", "synced_at_utc": "2026-10-11T15:28:30Z"}}},
        "rulings": [{"file": "ruling-995-unknown-efforts-20261011.md", "utc": "05:59Z", "summary": "unknown request effort"}],
    }


def rate(lane: str, status: str, value, reason: str | None = None) -> dict:
    return {"lane": lane, "clients": [{"client": "codex", "rates": [
        {"family": "mcp_calls", "label": "MCP calls", "status": "reported", "value": 0.5, "unit": "calls/s"},
        {"family": "skill_invocations", "label": "Skill invocations", "status": status, "value": value, "unit": "calls/s",
         "reason": reason, "window_seconds": 300, "source_sample_utc": "2026-10-11T14:00:00Z" if value is not None else None}]}]}


def fleet_fixture() -> dict:
    reported = {"status": "reported", "source": "direct", "read_utc": "2026-10-11T14:01:52Z", "reason": None}
    return {
        "schema": "local-fleet/1", "fleet_source": "direct native", "at": "2026-10-11T14:01:52Z",
        "availability": {name: dict(reported) for name in ("lanes_live", "lanes_parked", "claude_sessions", "exec_reads_in_flight")},
        "lanes_live": [{"lane": "lane-one", "status": "active", "tier": "default", "cli_version": "0.162.1", "lane_model": "gpt-fixture", "subagent_models": {"gpt-mini": 2}},
                       {"lane": "lane-two", "status": "listening", "tier": "fast", "cli_version": "0.162.1", "lane_model": None, "subagent_models": {}}],
        "lanes_parked": [{"lane": "parked-one", "tier": "standard", "cli_version": None, "expected_cli_version": "0.162.1"}],
        "claude_sessions": [{"name": "native-agent-stack-1a", "status": "idle"}, {"name": "session-two", "status": "busy"}],
        "exec_reads_in_flight": [{"name": "read-pr101", "tier": "standard"}],
        "tracking": {"schema": "fleet-tracking/1", "observed_utc": "2026-10-11T14:01:53Z",
                     "hcom": {"status": "reported", "read_utc": "2026-10-11T14:01:53Z", "agents": [
                         {"name": "lane-one-abcd", "base_name": "abcd", "tag": "lane-one", "tool": "codex", "status": "active", "status_age_seconds": 18.0},
                         {"name": "stray-agent", "base_name": "stray", "tag": "elsewhere", "tool": "claude", "status": "blocked", "status_age_seconds": 900.0}]},
                     "lanes": [rate("abcd", "UNKNOWN", None, "No qualified producer."), rate("efgh", "reported", 0), rate("ijkl", "lower bound", 0)]},
    }


def adoption_fixture() -> dict:
    return {"schema": "adoption-now/1", "generated_utc": "2026-10-11T15:00:00Z", "window_hours": 24,
            "layers": {"session context and token efficiency": {"servers": {
                "context-mode": {"claude_calls": 0, "claude_sessions": 0, "codex_calls": 17899, "codex_conversations": 301},
                "plugin_context-mode_context-mode": {"claude_calls": 1786, "claude_sessions": 10, "codex_calls": 0, "codex_conversations": 0}}}},
            "orchestration": {"claude_by_role": {"native-agent-stack-1a": {"SendMessage": 4}, "trading-cc": {"Agent": 7, "Workflow": 1}},
                              "codex_by_role": {"convergence-practice": {"spawn_agent": 3, "instances": ["zuro"]}}}}


def skill(name: str, uses, reads, mentions=0, *, enabled=True, status="trial", installed="2026-09-25T00:00:00Z") -> dict:
    return {"name": name, "status": status, "installed_at": installed, "claude": {"uses": uses, "in_table": uses is not None, "last_used": "today" if uses else None},
            "codex": {"enabled": enabled, "counts": {"7": {"skill_md_reads": reads, "name_mentions": mentions}, "30": {"skill_md_reads": reads, "name_mentions": mentions}}}}


def pinned(name: str, ref: str = "0123456789abcdef0123456789abcdef01234567", url: str | None = None) -> dict:
    return {"name": name, "source": "fixture/skills", "url": url or f"https://github.com/fixture/skills/tree/{ref}/skills/{name}", "ref": ref,
            "path": f"skills/{name}", "tree_sha": "f" * 40, "status": "trial"}


def record(document, label="fixture", **extra) -> dict:
    raw = json.dumps(document).encode() if not isinstance(document, str) else document.encode()
    return {"status": "read", "label": label, "role": "command_center_fixture", "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw),
            "file_utc": "2026-10-11T15:30:00Z", "document": document, **extra}


def missing(label: str, reason: str = "not present in the state root") -> dict:
    return {"status": "missing", "label": label, "reason": reason}


def readiness_layer() -> dict:
    def field(value, status="RECORDED", reason=None):
        return {"status": status, "value": value, **({"reason": reason} if reason else {})}
    return {"id": "agent-sdks", "inventory_date": field("2026-09-21"), "title": field("Agent SDKs and runtime workers"),
            "selected_tools": [{"id": "codex", "fields": {"pin": field("0.155.1"), "evidence_class": field("native_proven"), "recorded_stack_pin": field("0.155.1"),
                                                          "install_receipt": field(None, "UNVERIFIED", "registered support is not a current install"),
                                                          "fresh_session_invoke": field(None, "UNVERIFIED", "no fresh-session binding")}}]}


def inputs_fixture() -> dict:
    readiness = {"summary": {"gates": 2, "layers": 3, "sdk_items": 1, "recorded_claims": 40, "unverified_claims": 2, "unverified_sources": 0},
                 "gates": [{"id": "G1", "fields": {"state": {"status": "RECORDED", "value": "MET"}}}, {"id": "G2", "fields": {"state": {"status": "UNVERIFIED"}}}],
                 "open_items": [{"id": "O1", "fields": {"state": {"status": "RECORDED", "value": "MET"}}}, {"id": "O2", "fields": {}}],
                 "layers": [readiness_layer()]}
    evidence = {"files": [{"path": "a"}, {"path": "b"}, {"path": "c"}], "receipts": [{"id": "r"}], "convergence_records": []}
    platforms = {"linux-wsl2-x86_64": {"e2e_state": "host_verified"}, "macos-arm64": {"e2e_state": "untested"}}
    matrix = {"checked_at": "2026-09-27", "summary": {"convergence": {"overall": {"converged": 1, "layers": 2, "in_use": 5},
                                                                      "layer_states": {"recorded_reopened": 1, "confirmed_current": 1}}},
              "rows": [{"catalog": "foundation", "layer_id": "agent-sdks", "title": "Agent SDKs", "verdict_status": "recorded", "independent_review": "dual_lane_same_winner",
                        "open_gaps": 14, "open_executable_now_gaps": 12,
                        "convergence": {"layer_state": "recorded_reopened", "verdict_checked_at": "2026-09-22", "invoke": None, "invoke_reason": "no post-fix invoke receipt yet",
                                        "components": [{"id": "codex", "host_e2e": "true", "pin_current": "false"}]},
                        "winners": [{"component_id": "codex", "evidence_class": "native_proven", "pin": "0.155.1", "repository": "https://github.com/openai/codex", "platforms": platforms,
                                     "lifecycle_stages": [{"stage": "recovery", "status": "accepted_within_scope"}, {"stage": "use", "status": "accepted_within_scope"}, {"stage": "install", "status": "pending"}]},
                                    {"component_id": "drifted", "evidence_class": "local_integration", "pin": "1.0.0", "repository": "https://github.com/fixture/drifted", "platforms": {}, "lifecycle_stages": []},
                                    {"component_id": "unmirrored", "evidence_class": "synthetic", "pin": "2.0.0.dev0 @ c6fbd1c5932df2494ffa0020af5a9fbe80b82143", "repository": "https://github.com/fixture/none", "platforms": {}, "lifecycle_stages": []}]},
                       {"catalog": "us-equities", "layer_id": "risk", "title": "Portfolio risk", "verdict_status": "recorded", "independent_review": "dual_lane_adjudicated",
                        "open_gaps": 0, "open_executable_now_gaps": 0, "convergence": {"layer_state": "confirmed_current", "invoke": "fixture invoke receipt"}, "winners": []}]}
    grand = {"layers": [{"catalog": "foundation", "layer_id": "agent-sdks", "winners": [{"component_id": "codex", "pin_behind_upstream": True, "upstream_latest": "rust-v0.156.0"}]},
                        {"catalog": "us-equities", "layer_id": "risk", "winners": [{"component_id": "riskfolio", "pin_behind_upstream": False}]}]}
    research_state = {"checked_at": "2026-09-21", "resume_order": ["Read AGENTS.md first", "Choose one layer"]}
    token_window = {"kind": "token-window", "window_start_utc": "2026-10-10T16:00:00Z", "eval_time_utc": "2026-10-11T15:58:00Z", "window_seconds": 86280,
                    "rule": "increase() is an extrapolated estimate; classes are never summed",
                    "native": {"codex_tokens_by_type": {"values": {"cached_input": 1.7e9, "input": 1.8e9}},
                               "codex_total_tokens_by_lane": {"values": {f"lane-{index:02d}": float(100 - index) * 1e6 for index in range(17)} | {"idle-lane": 0.0}},
                               "claude_tokens_by_type": {"values": {"cacheRead": 1.34e10, "input": 7e7}},
                               "claude_cost_usd_by_model": {"values": {"claude-opus-5-5": 2022.794}},
                               "claude_cost_usd_by_lane": {"values": {"trading-cc": 12.5}}},
                    "tool_reports": {"rtk gain (global scope, lifetime on this host; the tool's own estimate)": {"commands": "167957", "tokens_saved": {"value": "218.5M", "share_percent": 16.7}},
                                     "rtk hook-audit (Claude sessions launched with the audit switch, last 7 days)": {"invocations": 263, "rewrites": 72, "skips": 191}}}
    token_tools = {"schema": "token-tools-now/1", "generated_utc": "2026-10-11T15:59:22Z", "tools": [
        {"tool": "RTK", "command": "rtk gain --format json", "label": "lifetime on this host, the tool's own estimate", "version": "rtk 0.51.0", "rc": 0, "started_utc": "2026-10-11T15:59:07Z", "seconds": 1.62,
         "estimate": {"total_saved": 222382401, "avg_savings_pct": 16.98, "total_commands": 168688, "total_input": 1309306534, "total_output": 1086961158}},
        {"tool": "Headroom", "command": "headroom agent-savings --check-perf --hours 24 --format json", "label": "proxy logs", "version": "headroom, version 0.40.0", "rc": 1, "started_utc": "2026-10-11T15:59:09Z", "seconds": 9.28,
         "estimate": None, "message": "Error: 0.0% savings below 90.0% target for agent-90", "note": "exits 1 when savings fall below the profile target"},
        {"tool": "Headroom", "command": "headroom output-savings", "label": "shaper", "version": "headroom, version 0.40.0", "rc": 0, "started_utc": "2026-10-11T15:59:19Z", "seconds": 1.41,
         "estimate": {"report": "No output-savings data yet."}, "note": "counterfactual unless an A/B holdout is set (HEADROOM_OUTPUT_HOLDOUT>0)"},
        {"tool": "context-mode", "command": "context-mode doctor", "label": "checks", "version": "context-mode 1.0.169", "rc": 0, "started_utc": "2026-10-11T15:59:21Z", "seconds": 0.47,
         "estimate": {"checks": {"PASS": 18, "SKIP": 1}}, "note": "savings are the MCP tool ctx_stats; there is no CLI report"}]}
    host = {"kind": "skill_invoke_rate_report", "generated_at": "2026-10-11T15:45:00.809697+00:00", "windows_days": [7, 30],
            "claude": {"measured": True}, "codex": {"measured": True},
            "skills": [skill("search-first", 100, 606), skill("idle-skill", 0, 0, status="kept"), skill("unlisted-skill", None, 4),
                       skill("codex-off", 3, 0, enabled=False), skill("mention-only", 0, 0, 2), skill("absent-skill", None, 0, installed=None)]}
    manifest = {"skills": [pinned(name) for name in ("search-first", "idle-skill", "unlisted-skill", "codex-off", "mention-only", "absent-skill")]
                + [pinned("http-only", url="http://example.org/skill"), pinned("never-reported")]}
    codex_lanes = {"kind": "codex_lane_usage_report", "generated_at": "2026-10-11T15:50:00+00:00", "window": {"since": "2026-10-04T16:00:00Z", "until": "2026-10-11T16:00:00Z"},
                   "groups": {"workers": {"sessions": 40, "sessions_with_skill_md_read": 7, "skill_md_reads": {"search-first": 30, "tdd": 2}},
                              "negative_controls": {"sessions": 5, "sessions_with_skill_md_read": 0, "skill_md_reads": {}},
                              "workers_by_role": {"explorer": {"sessions": 9, "sessions_with_skill_md_read": 1, "skill_md_reads": {"tdd": 1}}}}}
    claude_lanes = {"kind": "claude_child_lane_usage", "window": {"since": "2026-10-04T15:49:20.000Z", "until": "2026-10-11T15:49:20.000Z"},
                    "main": {"children": 1650, "children_with_skill_call": 549, "skill_calls": {"search-first": 10, "plugin:extra": 4}},
                    "groups": {"all": {"children": 3626, "children_with_skill_call": 659, "skill_calls": {"search-first": 202}},
                               "by_agent_type": {"cc-fixture-builder": {"children": 3, "children_with_skill_call": 2, "skill_calls": {"search-first": 5}},
                                                 "quiet-type": {"children": 4, "children_with_skill_call": 0, "skill_calls": {}}}}}
    slots = {"checked_at": "2026-10-09", "client_version": "2.1.295", "slots": [
        {"id": "client-core", "layer_id": "native-clients", "status": "default", "default": "Native installer build"},
        {"id": "orchestration-frameworks", "layer_id": "workers", "status": "default", "default": "Native composition without a framework layer",
         "overturn_when": "A paired same-task run shows a framework ahead", "notes": "Adjudicated: native composition stands."}]}
    read_queue = {"updated_utc": "2026-10-11T15:55:00Z", "slots": 7,
                  "running": [{"read": "fix1", "pr": "nas#1004", "head": "23cd8e7a", "tier": "sol-high", "started_utc": "2026-10-11T15:08:24Z"}],
                  "waiting": [{"pr": "uet#74", "head": "0390d6dd", "kind": "confirmation", "gates": "landing uet#74"}]}
    queue = ("# Research queue (fixture rule 8). A review finding lands here.\n"
             "date_utc\tlayer_id\tquestion\tsource_pr\tevidence\tstatus\trouted_to\n"
             "2026-10-11\tfoundation/agent-sdks\tShould X replace Y?\t#1001\tfixture evidence\topen\tconvergence-practice\n"
             "2026-10-11\tfoundation/risk\tShort row\n"
             "2026-10-11\tfoundation/risk\tExtra\t#1\te\topen\trouted\tspill-over\n")
    return {"readiness": record(readiness, "repo:catalogs/north-star/readiness.json"), "evidence": record(evidence, "repo:manifests/evidence.json"),
            "skills_manifest": record(manifest, "repo:adoption/skills/manifest.json"),
            "matrix": record(matrix), "grand_list": record(grand), "research_state": record(research_state),
            "final_stack": missing("repo:catalogs/landscape/final-stack.json", "not present in the selected checkout"),
            "token_window": record(token_window), "token_tools": record(token_tools),
            "skills_daily": missing("state:coordination/command-center/skills/skill-invoke-rate-latest.json"),
            "skills_host": record(host), "skills_codex_lanes": record(codex_lanes), "skills_claude_lanes": record(claude_lanes),
            "practice_slots": record(slots), "research_queue": record(queue), "read_queue": record(read_queue)}


def daily_fixture() -> dict:
    """#970's skill-invoke-rate-daily/1 projection, read from its branch's daily_skill_usage.py project_reports schema."""
    return {"schema": "skill-invoke-rate-daily/1", "generated_at": "2026-10-11T15:40:00+00:00", "window_days": 7,
            "host": [{"name": "search-first", "claude_uses_lifetime": 100, "codex_use": 9, "codex_skill_md_reads": 606, "codex_name_mentions": 0},
                     {"name": "idle-skill", "claude_uses_lifetime": 0, "codex_use": None, "codex_skill_md_reads": None, "codex_name_mentions": None}],
            "lanes": [{"client": "claude", "lane": "main", "skills": [{"name": "search-first", "count": 10}], "metric": "skill_calls"},
                      {"client": "claude", "lane": "workflow:cc-x", "skills": [{"name": "search-first", "count": 7}], "metric": "skill_calls"},
                      {"client": "codex", "lane": "workers", "skills": [{"name": "search-first", "count": 9, "raw_reads": 30}], "metric": "use"}],
            "measured": {"host": True, "codex": False, "claude": True}}


def prohibited_names() -> list[str]:
    """The comma-separated LANDING_PROHIBITED_NAMES, read at test time so no name enters the repository (#975)."""
    return [name.strip() for name in os.environ.get("LANDING_PROHIBITED_NAMES", "").split(",") if name.strip()]


def identity_hits(text: str, names: list[str]) -> int:
    return sum(len(re.findall(r"(?<![A-Za-z0-9])" + re.escape(name) + r"(?![A-Za-z0-9])", text, re.I)) for name in names)


class CommandCenterViewTests(unittest.TestCase):
    def render(self, current=None, fleet=None, inputs=None, adoption=None, refreshed=REFRESHED):
        return view.render(current_fixture() if current is None else current, fleet_fixture() if fleet is None else fleet,
                           inputs_fixture() if inputs is None else inputs, adoption=adoption_fixture() if adoption is None else adoption, refreshed=refreshed)

    def test_fixture_renders_every_panel_with_stated_status(self):
        markup, statuses = self.render()
        for anchor in PANELS:
            self.assertIn(f'id="{anchor}"', markup)
        for anchor in ("cc-prs", "cc-owner", "cc-sessions", "cc-tokens", "cc-orchestration", "cc-landscape", "cc-skills"):
            self.assertIn(f'<a href="#{anchor}"><strong>', markup)
        self.assertEqual({anchor: row["status"] for anchor, row in statuses.items()},
                         {"cc-sessions": "wired", "cc-orchestration": "wired", "cc-prs": "wired", "cc-landscape": "partial", "cc-skills": "wired",
                          "cc-tokens": "partial", "cc-research": "wired", "cc-manifests": "partial", "cc-owner": "wired"})
        lanes = {row[0]: row for row in table(markup, "Live Codex lanes")[1:]}
        self.assertEqual(lanes["lane-one"][1:3], ["active", "18 s hcom lane-one-abcd, active"])
        self.assertIn("gpt-fixture", lanes["lane-one"][3])
        self.assertEqual(lanes["lane-two"][2:4], ["not recorded", "not recorded"])
        self.assertIn("owner session (reports to CC)", markup)
        self.assertNotIn("native-agent-stack-1a", markup)
        subagents = {row[0]: row for row in table(markup, "Command-center subagents running")[1:]}
        self.assertEqual(subagents["cc-fixture-micro"][1:], ["#102 micro", "claude-opus-5-5"])
        self.assertIn("<summary>1 parked lane</summary>", markup)
        counts = re.findall(r'<strong>([^<]+)</strong> <span>([^<]+)</span>', markup[markup.index('class="cc-counts"'):])
        self.assertIn(("1", "GPT reads running"), counts)
        self.assertIn(("1 of 2", "layers converged"), counts)
        self.assertIn(("3 of 6 measured", "skills with no 7-day call"), counts)
        self.assertIn(("222M", "tokens saved (RTK estimate)"), counts)
        self.assertIn("Partial because of not wired: Token-report manifest", statuses["cc-tokens"]["detail"])
        self.assertIn("Partial because of not wired: North-star ten-layer plan", statuses["cc-landscape"]["detail"])
        for anchor in ("cc-manifests", "cc-landscape"):
            self.assertIn("Partial because of unread records: final-stack.json (not present in the selected checkout).", statuses[anchor]["detail"])
        self.assertEqual({anchor: row["not_wired"] for anchor, row in statuses.items() if row["not_wired"]}, {"cc-tokens": ["token_report"], "cc-landscape": ["north_star"]})
        for anchor, row in statuses.items():
            with self.subTest(anchor=anchor):
                self.assertEqual(row["status"] == "partial", "Partial because" in row["detail"])

    def test_pr_optional_fields_render_values_absences_and_unsupported_values(self):
        markup, statuses = self.render()
        rows = table(markup, "Pull requests in review")
        self.assertEqual(rows[0], ["PR", "Work", "Head", "Round", "Next gate", "Blockers", "Follow-ups", "Recorded state"])
        rows = {row[0]: row for row in rows[1:]}
        self.assertEqual(rows["#101"][2:7], ["abc12345", "3", "Astra micro at abc12345", "P2 reinstall race", "one re-pin sync live copy"])
        self.assertEqual(rows["#102"][2:7], ["not recorded"] * 5)
        self.assertEqual(rows["#103 / #104"][5:7], ["none", "none"])
        self.assertEqual(rows["#105"][2:7], ["not recorded unsupported value"] * 2 + ["not recorded"] + ["not recorded unsupported value"] * 2)
        self.assertIn('<td class="cc-pr-next-gate"><strong>Astra micro at abc12345</strong></td>', markup)
        self.assertEqual(statuses["cc-prs"]["status"], "wired")
        unrecorded = current_fixture()
        unrecorded["in_review"] = [{"pr": "#102", "what": "w", "state": "s"}]
        markup, statuses = self.render(current=unrecorded)
        self.assertEqual(statuses["cc-prs"]["status"], "partial")
        self.assertIn("head, round, next gate, blockers, follow-ups", statuses["cc-prs"]["detail"])

    def test_section_status_follows_every_rendered_gap(self):
        # B2 at b209afe8: Sessions read wired with reads and parked lanes missing, and PR waves read
        # wired without landings_today; a rendered gap now always makes its section partial.
        fleet = fleet_fixture()
        fleet["exec_reads_in_flight"], fleet["lanes_parked"] = None, None
        current = current_fixture()
        del current["landings_today"]
        markup, statuses = self.render(current=current, fleet=fleet)
        self.assertEqual(statuses["cc-sessions"]["status"], "partial")
        self.assertIn("missing input: fleet exec_reads_in_flight; fleet lanes_parked", statuses["cc-sessions"]["detail"])
        self.assertEqual(statuses["cc-prs"]["status"], "partial")
        self.assertIn("missing input: cc-now.json#/landings_today", statuses["cc-prs"]["detail"])
        for status, label in (("UNKNOWN", "Optional tracking collection is UNKNOWN (TypeError)."), ("UNREPORTED", "Fleet adapter failed (OSError)")):
            with self.subTest(status=status):
                fleet = fleet_fixture()
                fleet["tracking"] = {"schema": "fleet-tracking/1", "status": status, "reason": label}
                markup, statuses = self.render(fleet=fleet)
                self.assertIn("missing input: fleet tracking (" + status + "): " + label, section(markup, "cc-skills"))
                self.assertIn(label, statuses["cc-skills"]["detail"])
                self.assertEqual(statuses["cc-skills"]["status"], "partial")

    def test_an_unavailable_hcom_roster_is_a_stated_gap_and_sessions_is_partial(self):
        # Codex :156 and the micro's (a)1 at 50977b00: fleet_data's own UNKNOWN roster left Sessions `wired`
        # with the reason dropped. The shape here is the producer's, from fleet_data._tracking_hcom.
        def unavailable(*_, **__):
            raise OSError("synthetic hcom failure")
        roster = fleet_data._tracking_hcom(unavailable, datetime(2026, 10, 11, 14, 1, 53, tzinfo=timezone.utc).timestamp())
        self.assertEqual((roster["status"], roster["agents"], roster["reason"]), ("UNKNOWN", None, "Native hcom roster is UNKNOWN (OSError)."))
        fleet = fleet_fixture()
        fleet["tracking"]["hcom"] = roster
        markup, statuses = self.render(fleet=fleet)
        panel = section(markup, "cc-sessions")
        self.assertIn("missing input: fleet tracking hcom roster (UNKNOWN): Native hcom roster is UNKNOWN (OSError).", panel)
        self.assertIn("hcom roster unavailable at", panel)
        self.assertEqual(statuses["cc-sessions"]["status"], "partial")
        self.assertIn("Partial because of missing input: fleet tracking hcom roster (UNKNOWN)", statuses["cc-sessions"]["detail"])
        self.assertEqual(table(markup, "Live Codex lanes")[1][2], "not recorded")
        self.assertNotIn("synthetic hcom failure", markup)
        unreported = fleet_fixture()
        unreported["tracking"] = {"schema": "fleet-tracking/1", "status": "UNREPORTED", "reason": "Fleet adapter failed (OSError)"}
        markup, statuses = self.render(fleet=unreported)
        self.assertIn("missing input: fleet tracking hcom roster (not reported)", section(markup, "cc-sessions"))
        self.assertEqual(statuses["cc-sessions"]["status"], "partial")
        empty = fleet_fixture()
        empty["tracking"]["hcom"]["agents"] = []
        self.assertEqual(self.render(fleet=empty)[1]["cc-sessions"]["status"], "wired")

    def test_the_count_strip_takes_the_rtk_figure_only_from_an_rtk_report(self):
        # Codex :1144 and the micro's (a)3 at 50977b00: without an RTK row in token-tools-now.json, the strip took the
        # first token-window report, whichever tool it was, and labelled its figure "RTK estimate".
        def strip(markup):
            start = markup.index('class="cc-counts"')
            return markup[start:markup.index("</ul>", start)]
        inputs = inputs_fixture()
        inputs["token_tools"]["document"]["tools"][0].update(rc=None, error="command not found", estimate=None)
        window = inputs["token_window"]["document"]
        window["tool_reports"] = {"headroom proxy (24 h; the tool's own estimate)": {"tokens_saved": {"value": "999M", "share_percent": 90.0}}, **window["tool_reports"]}
        markup, _ = self.render(inputs=inputs)
        self.assertIn('<strong>218.5M</strong> <span>tokens saved (RTK estimate)</span>', strip(markup))
        self.assertNotIn("999M", strip(markup))
        window["tool_reports"] = {"headroom proxy (24 h; the tool's own estimate)": {"tokens_saved": {"value": "999M"}}}
        markup, _ = self.render(inputs=inputs)
        self.assertIn('<strong>2.5M</strong> <span>tokens saved (RTK estimate)</span>', strip(markup))
        current = current_fixture()
        del current["token_efficiency"]
        markup, _ = self.render(current=current, inputs=inputs)
        self.assertIn('<strong>UNKNOWN</strong> <span>tokens saved (RTK estimate)</span>', strip(markup))
        self.assertNotIn("999M", strip(markup))

    def test_values_dropped_after_masking_are_counted_on_the_page(self):
        # The fail-closed residue guard drops a value whole; the page states how many, and the section reads partial.
        current = current_fixture()
        current["in_review"][0]["state"] = '"zqsp" ' + AT + "zqdsp.example.org"
        current["waiting_on_owner"][2]["what"] = '"zq' + "w" * 300 + '"' + AT + "zqdlong.example.org"
        markup, statuses = self.render(current=current)
        self.assertNotIn("zqsp", markup)
        self.assertNotIn("zqdlong", markup)
        self.assertIn("missing input: 2 values omitted because an at sign beside a word remained after masking", markup)
        self.assertEqual(statuses["cc-prs"]["status"], "partial")
        self.assertIn("1 value omitted after masking", statuses["cc-prs"]["detail"])
        self.assertIn("1 value omitted after masking", statuses["cc-owner"]["detail"])
        clean, _ = self.render()
        self.assertNotIn("omitted because an at sign", clean)

    def test_long_tokens_dropped_for_private_decoded_text_are_counted_on_the_page(self):
        # The GPT fix3 verdict at 38302cd2, BLOCKER 2 (fix3-pr1012-38302cd2a/VERDICT.md): a token over 4,096 characters
        # whose decoded text is private is omitted whole; the page states how many, and the section reads partial.
        current = current_fixture()
        current["in_review"][0]["state"] = "x" * 4100 + "%2F".join(SYNTHETIC_HOME.split("/")) + "%2Fnotes"
        markup, statuses = self.render(current=current)
        self.assertNotIn("synthetic-user", decoded_text(markup))
        self.assertIn("missing input: 1 long token omitted because the decoded text is private", markup)
        self.assertEqual(statuses["cc-prs"]["status"], "partial")
        self.assertIn("1 long token omitted for private text once decoded", statuses["cc-prs"]["detail"])

    def test_malformed_pr_rows_are_rejected_with_a_stated_gap(self):
        # Astra's first read of a737ef98 (P2, review_probes.py:31): rows that are not objects rendered "No pull requests
        # in review." as wired, while the strip counted them as two PRs.
        current = current_fixture()
        current["in_review"] = [None, "invalid row"]
        markup, statuses = self.render(current=current)
        panel = section(markup, "cc-prs")
        self.assertNotIn("No pull requests in review.", panel)
        self.assertIn("missing input: cc-now.json#/in_review: 2 rows are not PR objects and not shown", panel)
        self.assertEqual(statuses["cc-prs"]["status"], "partial")
        self.assertIn("Partial because of missing input: cc-now.json#/in_review: 2 rows are not PR objects", statuses["cc-prs"]["detail"])
        self.assertIn('<strong>0</strong> <span>in review</span>', markup)
        mixed = current_fixture()
        mixed["in_review"] = [mixed["in_review"][0], 7, None]
        markup, statuses = self.render(current=mixed)
        self.assertEqual([row[0] for row in table(markup, "Pull requests in review")[1:]], ["#101"])
        self.assertIn("missing input: cc-now.json#/in_review: 2 rows are not PR objects and not shown", section(markup, "cc-prs"))
        self.assertEqual(statuses["cc-prs"]["status"], "partial")
        self.assertIn('<strong>1</strong> <span>in review</span>', markup)
        empty = current_fixture()
        empty["in_review"] = []
        markup, statuses = self.render(current=empty)
        self.assertIn("<p>No pull requests in review.</p>", markup)
        self.assertEqual(statuses["cc-prs"]["status"], "wired")

    def test_skill_defects_are_unknown_without_a_measured_seven_day_column(self):
        # Astra's first read of a737ef98 (P2, review_probes.py:40): with no 7-day measurement the view still published
        # defects 0 in the receipt, the summary and the strip.
        inputs = inputs_fixture()
        inputs["skills_host"]["document"]["codex"]["measured"] = False
        for name in ("skills_daily", "skills_claude_lanes", "skills_codex_lanes"):
            inputs[name] = missing("state:" + name)
        markup, statuses = self.render(inputs=inputs)
        self.assertIsNone(statuses["cc-skills"]["defects"])
        self.assertEqual(statuses["cc-skills"]["measured_skills"], 0)
        self.assertIn('<strong>UNKNOWN</strong> <span>skills with no 7-day call</span>', markup)
        self.assertIn("No pinned skill has a measured 7-day column, so the number with no call is UNKNOWN.", statuses["cc-skills"]["detail"])
        self.assertNotIn("wiring defect</span>", section(markup, "cc-skills"))
        full = inputs_fixture()
        full["skills_manifest"]["document"]["skills"] = [entry for entry in full["skills_manifest"]["document"]["skills"] if entry["name"] not in ("http-only", "never-reported")]
        markup, statuses = self.render(inputs=full)
        self.assertEqual((statuses["cc-skills"]["defects"], statuses["cc-skills"]["measured_skills"], statuses["cc-skills"]["pinned_skills"]), (3, 6, 6))
        self.assertIn('<strong>3</strong> <span>skills with no 7-day call</span>', markup)
        self.assertIn("3 of 6 pinned skills recorded no call in any measured 7-day column", statuses["cc-skills"]["detail"])

    def test_missing_inputs_render_stated_gaps_without_raising(self):
        failed_fleet = {"fleet_source": "not reported", "at": None, "lanes_live": None, "lanes_parked": None, "claude_sessions": None,
                        "exec_reads_in_flight": None, "availability": {name: {"status": "UNKNOWN"} for name in ("lanes_live", "lanes_parked", "claude_sessions")},
                        "tracking": {"schema": "fleet-tracking/1", "status": "UNREPORTED", "hcom": {"agents": [], "status": "UNKNOWN"}, "lanes": []}}
        absent = {name: missing("state:" + name) for name in inputs_fixture()}
        for current, fleet, inputs in (({"schema": "cc-now/1"}, failed_fleet, absent), ({}, {}, {}), (None, None, None)):
            with self.subTest(fleet=bool(fleet), inputs=bool(inputs)):
                markup, statuses = view.render(current, fleet, inputs, adoption=None, refreshed=None)
                for name in ("cc-now.json#/in_review", "cc-now.json#/landings_today", "cc-now.json#/waiting_on_owner", "cc-now.json#/orchestration",
                             "cc-now.json#/landing_queue", "cc-now.json#/program", "cc-now.json#/mirrors", "cc-now.json#/rulings",
                             "cc-now.json#/cc_agents/running", "fleet lanes_live", "fleet claude_sessions", "adoption-now.json orchestration"):
                    self.assertIn("missing input: " + name, markup)
                for anchor in ("cc-sessions", "cc-prs", "cc-tokens", "cc-skills", "cc-manifests", "cc-owner", "cc-landscape", "cc-research", "cc-orchestration"):
                    self.assertEqual(statuses[anchor]["status"], "missing", anchor)
                self.assertIn('<strong>UNKNOWN</strong> <span>in review</span>', markup)
                self.assertIn('<strong>UNKNOWN</strong> <span>skills with no 7-day call</span>', markup)
        markup, _ = view.render({}, {}, absent)
        for name in ("token_window", "token_tools", "skills_host", "read_queue", "research_queue", "matrix", "skills_manifest", "practice_slots"):
            self.assertIn("missing input: state:" + name + ": not present in the state root", markup)

    def test_a_bad_field_degrades_only_its_own_section(self):
        # B3 at b209afe8: a scalar codex_top_lanes_M (TypeError) or an integer above 1e308 (OverflowError)
        # replaced all six sections with the placeholder. Each of these hostile types now stays in its section.
        huge = 10 ** 400
        cases = {
            "cc-tokens": lambda current, fleet, inputs: (current["token_use_24h"].__setitem__("codex_top_lanes_M", 3.5), inputs.__setitem__("token_window", missing("w")),
                                                         inputs["token_tools"]["document"]["tools"][0]["estimate"].__setitem__("total_saved", huge)),
            "cc-sessions": lambda current, fleet, inputs: fleet["lanes_live"][0].__setitem__("subagent_models", {"m": huge}),
            "cc-orchestration": lambda current, fleet, inputs: inputs["read_queue"]["document"].__setitem__("slots", huge),
            "cc-prs": lambda current, fleet, inputs: current["in_review"][0].__setitem__("round", huge),
            "cc-landscape": lambda current, fleet, inputs: inputs["matrix"]["document"]["rows"][0].__setitem__("open_gaps", huge),
            "cc-skills": lambda current, fleet, inputs: inputs["skills_host"]["document"]["skills"][0]["claude"].__setitem__("uses", huge),
            "cc-research": lambda current, fleet, inputs: inputs.__setitem__("research_queue", record("date_utc\tq\n" + str(huge) + "\tx\n")),
            "cc-manifests": lambda current, fleet, inputs: inputs["readiness"]["document"]["summary"].__setitem__("gates", huge),
            "cc-owner": lambda current, fleet, inputs: current["waiting_on_owner"].append({"what": "big", "by_utc": str(huge)}),
        }
        for anchor, mutate in cases.items():
            with self.subTest(anchor=anchor):
                current, fleet, inputs = current_fixture(), fleet_fixture(), inputs_fixture()
                mutate(current, fleet, inputs)
                markup, statuses = self.render(current=current, fleet=fleet, inputs=inputs)
                self.assertNotIn("could not render", markup)
                self.assertTrue(all(f'id="{other}"' in markup for other in PANELS))
        broken = view.render.__globals__["_tokens"]
        for name in ("_tokens", "_landscape", "_counts"):
            with self.subTest(guard=name), patch.dict(view.render.__globals__, {name: lambda *args, **kwargs: (_ for _ in ()).throw(TypeError("guard-probe-message"))}):
                markup, statuses = self.render()
                if name == "_counts":
                    self.assertIn("missing input: count strip (TypeError)", markup)
                    self.assertEqual({row["status"] for row in statuses.values()} - {"wired", "partial"}, set())
                else:
                    anchor = {"_tokens": "cc-tokens", "_landscape": "cc-landscape"}[name]
                    self.assertEqual(statuses[anchor]["status"], "missing")
                    self.assertIn("could not render (TypeError)", statuses[anchor]["detail"])
                    self.assertNotIn("guard-probe-message", markup)
                    self.assertEqual(sum(row["status"] == "missing" for row in statuses.values()), 1)
        self.assertIs(view.render.__globals__["_tokens"], broken)

    def test_skills_join_the_manifest_with_counts_and_flags(self):
        markup, statuses = self.render()
        rows = table(markup, "The 8 skills pinned in adoption/skills/manifest.json")
        self.assertEqual(rows[0], ["Skill", "Upstream source@pin", "Claude uses, lifetime", "Claude calls in main sessions, 7 d", "Claude calls in subagents, 7 d", "Codex use, 7 d",
                                   "Codex SKILL.md reads, 7 d", "Codex name mentions, 7 d", "Flags"])
        rows = {row[0].split(" ")[0]: row for row in rows[1:]}
        self.assertEqual(rows["search-first"][1], "fixture/skills@0123456789ab skills/search-first")
        self.assertEqual(rows["search-first"][2:9], ["100", "10", "202", "not measured", "606", "0", "in use"])
        self.assertIn("wiring defect", rows["idle-skill"][8])
        self.assertIn("wiring defect", rows["codex-off"][8])
        self.assertEqual(rows["unlisted-skill"][2], "not measured")
        self.assertEqual(rows["codex-off"][5:8], ["not measured", "0", "0"])
        self.assertIn("not enabled for Codex in the manifest", rows["codex-off"][8])
        self.assertEqual(rows["mention-only"][8], "in use")
        self.assertIn("not installed", rows["absent-skill"][8])
        self.assertIn("wiring defect", rows["absent-skill"][8])
        self.assertEqual(rows["never-reported"][2:9], ["not measured"] * 6 + ["not measured"])
        self.assertIn('<a href="https://github.com/fixture/skills/tree/0123456789abcdef0123456789abcdef01234567/skills/search-first" rel="noreferrer">fixture/skills@0123456789ab</a>', markup)
        self.assertNotIn('href="http://example.org/skill"', markup)
        self.assertIn("fixture/skills@0123456789ab", rows["http-only"][1])
        self.assertEqual(statuses["cc-skills"]["defects"], 3)
        self.assertIn("3 of the 6 pinned skills with a measured 7-day column recorded no call (zero calls = wiring defect); 2 of the 8 pinned skills have no 7-day measurement.", statuses["cc-skills"]["detail"])
        self.assertEqual((statuses["cc-skills"]["measured_skills"], statuses["cc-skills"]["pinned_skills"]), (6, 8))
        no_manifest = inputs_fixture()
        no_manifest["skills_manifest"] = missing("repo:adoption/skills/manifest.json", "not present in the selected checkout")
        unknown_markup, unknown = self.render(inputs=no_manifest)
        self.assertIn('<strong>UNKNOWN</strong> <span>skills with no 7-day call</span>', unknown_markup)
        self.assertIsNone(unknown["cc-skills"]["defects"])
        self.assertIn("missing input: repo:adoption/skills/manifest.json: not present in the selected checkout", unknown_markup)
        unpinned = {row[0]: row for row in table(markup, "Skills with recorded calls that the manifest does not pin")[1:]}
        self.assertEqual(sorted(unpinned), ["plugin:extra", "tdd"])
        self.assertEqual(unpinned["plugin:extra"][1:], ["4", "0", "0", "unpinned"])
        groups = {row[0]: row for row in table(markup, "Codex rollout groups")[1:]}
        self.assertEqual(groups["workers"][1:4], ["40", "7", "32"])
        self.assertEqual(groups["workers by role: explorer"][4], "tdd 1")
        self.assertEqual(list({row[0]: row for row in table(markup, "Claude subagent types")[1:]}), ["cc-fixture-builder"])
        slots = table(markup, "One default per role slot")
        self.assertEqual(slots[2][:2], ["orchestration-frameworks workers", "default"])
        self.assertIn('<tr class="cc-ao-row">', markup)

    def test_skill_counts_and_install_state_follow_what_the_producer_measured(self):
        # skill_usage.py counts Codex reads for every manifest skill (codex.enabled is the manifest's flag), and writes
        # "not-measured" for Claude when /skill-doctor did not run (tools/skill-usage/skill_usage.py:603, :615 and :652 at 900835c6).
        inputs = inputs_fixture()
        host = inputs["skills_host"]["document"]
        host["claude"] = {"measured": False}
        host["skills"].append(skill("system-copy", None, 158, 2, enabled=False))
        for row in host["skills"]:
            row["claude"] = "not-measured"
        inputs["skills_manifest"]["document"]["skills"].append(pinned("system-copy"))
        markup, statuses = self.render(inputs=inputs)
        rows = {row[0].split(" ")[0]: row for row in table(markup, "The 9 skills pinned")[1:]}
        self.assertEqual(rows["system-copy"][2:8], ["not measured", "0", "0", "not measured", "158", "2"])
        self.assertIn("in use", rows["system-copy"][8])
        self.assertIn("not enabled for Codex in the manifest", rows["system-copy"][8])
        self.assertEqual(rows["search-first"][2], "not measured")
        self.assertIn("install state not measured", rows["absent-skill"][8])
        self.assertNotIn("not installed", rows["absent-skill"][8])
        self.assertNotIn("install state not measured", rows["search-first"][8])

    def test_lane_counts_survive_a_host_report_without_the_skill(self):
        # The Claude micro at 38302cd2, (b) (pr1012-claude-micro-38302cd2.md): a skill the lane reports measured keeps
        # those counts when the host report has no row for it; its other columns stay unmeasured.
        inputs = inputs_fixture()
        host = inputs["skills_host"]["document"]
        host["skills"] = [row for row in host["skills"] if row["name"] != "search-first"]
        markup, _ = self.render(inputs=inputs)
        rows = {row[0].split(" ")[0]: row for row in table(markup, "The 8 skills pinned")[1:]}
        self.assertEqual(rows["search-first"][2:9], ["not measured", "10", "202", "not measured", "not measured", "not measured", "in use"])

    def test_a_current_daily_projection_makes_absent_or_stale_hourly_reports_no_gap(self):
        # The Claude micro at 38302cd2, (b): the daily projection replaces the hourly reports while it is current, so an
        # absent or stale hourly report it replaces reads "not used" and leaves the section wired.
        inputs = inputs_fixture()
        inputs["skills_daily"] = record(daily_fixture())
        inputs["skills_codex_lanes"] = missing("state:coordination/command-center/skills/skill-usage-codex-lanes-latest.json")
        inputs["skills_claude_lanes"]["document"]["window"]["until"] = "2026-10-11T09:00:00.000Z"
        markup, statuses = self.render(inputs=inputs)
        self.assertEqual(statuses["cc-skills"]["status"], "wired")
        sources = {row[0].split(" (")[0]: " ".join(row) for row in table(markup, "Skill-count sources")[1:]}
        for producer in ("skill_usage.py --lanes, 7 days", "child-usage.mjs --lanes-sweep, 7 days"):
            self.assertIn("not used: the current daily projection above replaces this report", sources[producer])
        self.assertIn("min old at this refresh", sources["skill_usage.py --run-skill-doctor --window 7"])
        stale = copy.deepcopy(inputs)
        stale["skills_daily"]["document"]["generated_at"] = "2026-10-09T00:00:00+00:00"
        markup, statuses = self.render(inputs=stale)
        self.assertEqual(statuses["cc-skills"]["status"], "partial")
        self.assertIn("missing input: state:coordination/command-center/skills/skill-usage-codex-lanes-latest.json", markup)

    def test_skills_accept_the_daily_projection_and_keep_unscanned_roots_unknown(self):
        inputs = inputs_fixture()
        inputs["skills_daily"] = record(daily_fixture())
        markup, statuses = self.render(inputs=inputs)
        self.assertIn("Counts use the daily projection", markup)
        rows = {row[0].split(" ")[0]: row for row in table(markup, "The 8 skills pinned")[1:]}
        self.assertEqual(rows["search-first"][2:8], ["100", "10", "7", "9", "606", "0"])
        self.assertEqual(rows["idle-skill"][5:8], ["not measured"] * 3)
        self.assertIn("wiring defect", rows["idle-skill"][8])
        groups = {row[0]: row for row in table(markup, "Codex rollout groups")[1:]}
        self.assertEqual(groups["workers"][1:5], ["not measured"] * 4)
        measured = inputs_fixture()
        measured["skills_daily"] = record(dict(daily_fixture(), measured={"host": True, "codex": True, "claude": True}))
        markup, _ = self.render(inputs=measured)
        groups = {row[0]: row for row in table(markup, "Codex rollout groups")[1:]}
        self.assertEqual(groups["workers"][1:5], ["not measured", "not measured", "9", "search-first 9"])
        stale = inputs_fixture()
        stale["skills_daily"] = record(dict(daily_fixture(), generated_at="2026-10-09T00:00:00+00:00"))
        markup, _ = self.render(inputs=stale)
        self.assertNotIn("Counts use the daily projection", markup)
        wrong = inputs_fixture()
        wrong["skills_daily"] = record({"schema": "skill-invoke-rate-daily/9"})
        markup, statuses = self.render(inputs=wrong)
        self.assertIn("unsupported report skill-invoke-rate-daily/9, expected skill-invoke-rate-daily/1", markup)
        self.assertEqual(statuses["cc-skills"]["status"], "partial")

    def test_stale_reports_are_labelled_with_their_age(self):
        stale = inputs_fixture()
        stale["skills_host"]["document"]["generated_at"] = "2026-10-10T14:35:21+00:00"
        stale["token_window"]["document"]["eval_time_utc"] = "2026-10-11T09:00:00Z"
        stale["read_queue"]["document"]["updated_utc"] = "not a time"
        markup, statuses = self.render(inputs=stale)
        sources = {row[0].split(" (")[0]: row for row in table(markup, "Skill-count sources")[1:]}
        self.assertIn("stale : 25.4 h old at this refresh (limit 3.0 h)", sources["skill_usage.py --run-skill-doctor --window 7"][3])
        self.assertIn("10 min old at this refresh", " ".join(sources["skill_usage.py --lanes, 7 days"]))
        self.assertEqual(statuses["cc-skills"]["status"], "partial")
        self.assertIn("1 stale report", statuses["cc-skills"]["detail"])
        self.assertIn("stale</strong>: 7.0 h old at this refresh", section(markup, "cc-tokens"))
        self.assertIn("age unknown: no parseable generation time", section(markup, "cc-orchestration"))

    def test_prometheus_skill_rates_keep_unknown_distinct_from_zero(self):
        markup, _ = self.render()
        rows = {row[0]: row for row in table(markup, "Skill invocations per published lane, 300 s rate window")[1:]}
        self.assertTrue(rows["abcd"][2].startswith("UNKNOWN"))
        self.assertIn("No qualified producer.", rows["abcd"][2])
        self.assertTrue(rows["efgh"][2].startswith("0 calls/s (reported)"))
        self.assertIn("0 means no recorded calls", rows["efgh"][2])
        self.assertTrue(rows["ijkl"][2].startswith("UNKNOWN"))
        self.assertNotIn("0 means no recorded calls", rows["ijkl"][2])

    def test_token_tools_keep_each_command_exit_and_estimate(self):
        markup, statuses = self.render()
        rows = table(markup, "Token tools run end to end by tools/local-pages/token_tools_now.py")
        self.assertEqual(rows[0], ["Tool", "Command", "Exit code", "Ran", "The tool's own estimate"])
        rtk, agent, output, doctor = rows[1:]
        self.assertEqual(rtk[0], "RTK rtk 0.51.0")
        self.assertEqual(rtk[2], "0")
        self.assertIn("222M tokens saved (17% average)", rtk[4])
        self.assertEqual(agent[2], "1")
        self.assertIn("Error: 0.0% savings below 90.0% target for agent-90", agent[4])
        self.assertIn("counterfactual unless an A/B holdout is set", output[4])
        self.assertIn("18 PASS, 1 SKIP", doctor[4])
        self.assertIn("savings are the MCP tool ctx_stats", doctor[4])
        cache = table(markup, "Prompt-cache reads")
        self.assertEqual([row[:2] for row in cache[1:]], [["Claude", "13.4B"], ["Codex", "1.7B"]])
        self.assertIn("<h3>Client counters</h3>", markup)
        bars = table(markup, "Codex tokens by lane, largest 15 of 18")[1:]
        self.assertEqual([row[:2] for row in bars[:2]], [["lane-00", "100M"], ["lane-01", "99M"]])
        self.assertEqual(table(markup, "Codex tokens by lane, every lane")[-1][:2], ["idle-lane", "0"])
        recorded = table(markup, "Recorded tool reports and invocations")[1:]
        self.assertEqual([row[0] for row in recorded], ["RTK", "RTK", "Context Mode", "Context Mode", "Headroom"])
        unknown = inputs_fixture()
        unknown["token_tools"]["document"]["tools"][0].update(rc=None, error="command not found", estimate=None)
        markup, _ = self.render(inputs=unknown)
        self.assertIn("not recorded command not found", table(markup, "Token tools run end to end")[1][2])
        self.assertIn('<strong>218.5M</strong> <span>tokens saved (RTK estimate)</span>', markup)
        wrong = inputs_fixture()
        wrong["token_tools"] = record({"schema": "token-tools-now/0", "tools": copy.deepcopy(inputs_fixture()["token_tools"]["document"]["tools"])})
        markup, statuses = self.render(inputs=wrong)
        self.assertIn("unsupported schema token-tools-now/0", markup)
        self.assertNotIn("Token tools run end to end", markup)
        fallback = inputs_fixture()
        fallback["token_window"] = missing("state:coordination/command-center/pages/token-window-now.json")
        markup, _ = self.render(inputs=fallback)
        self.assertEqual([row[:2] for row in table(markup, "Codex tokens by lane, millions")[1:]], [["lane-a", "40"], ["lane-b", "10"]])
        self.assertEqual(table(markup, "Recorded tool reports and invocations")[1][4], "cc-now.json token_efficiency (fallback)")

    def test_landscape_shows_w6_columns_mirrors_and_never_infers_a_terminal_state(self):
        markup, statuses = self.render()
        rows = {row[0].split(" foundation/")[0].split(" us-equities/")[0]: row for row in table(markup, "Foundation and trading layers with the W6 final criteria")[1:]}
        sdk = rows["Agent SDKs"]
        self.assertIn("open gaps: 12 executable now of 14", sdk[0])
        self.assertIn("codex @ 0.155.1 native_proven accepted within scope: recovery, use pending: install platforms: linux-wsl2-x86_64 host verified, macos-arm64 untested upstream latest rust-v0.156.0; pin behind upstream mirror rust-v0.155.1 at abcdef123456", sdk[1])
        self.assertIn("matches the pin", sdk[1])
        self.assertIn("unmirrored @ 2.0.0.dev0 @ c6fbd1c5932df2494ffa0020af5a9fbe80b82143 synthetic", sdk[1])
        self.assertIn("no mirror for https://github.com/fixture/none", sdk[1])
        self.assertEqual(sdk[2], "recorded recorded reopened; dual_lane_same_winner; checked 2026-09-22")
        self.assertEqual(sdk[3], "codex: pending final-stack.json drifted: pending final-stack.json unmirrored: pending final-stack.json")
        self.assertIn("codex: host E2E true, pin current false", sdk[4])
        self.assertEqual(sdk[5], "not recorded no post-fix invoke receipt yet")
        self.assertEqual(sdk[6], "pending #1007 (#1008 landed 2026-10-11 21:34:23Z)")
        self.assertEqual(rows["Portfolio risk"][5], "fixture invoke receipt")
        self.assertIn("1 winner has no upstream mirror", section(markup, "cc-landscape"))
        self.assertIn("drifted @ 1.0.0", sdk[1])
        self.assertIn("mirror v2.0.0 at 0123456789ab, synced 2026-10-11T15:28:30Z; differs from the pin", sdk[1])
        north = table(markup, "North-star readiness layers")[1]
        self.assertEqual(north[1], "codex @ 0.155.1 native_proven")
        self.assertEqual(north[2:7], ["not recorded the readiness manifest has no verdict field", "codex: 0.155.1", "codex: not recorded registered support is not a current install",
                                      "codex: not recorded no fresh-session binding", "not recorded"])
        final = inputs_fixture()
        final["final_stack"] = record({"checked_at": "2026-10-11", "summary": {"layers": 1, "status": {"reopened": 1}},
                                       "runs": [{"id": "codex", "pin": "0.155.1"}],
                                       "layers": [{"catalog": "foundation", "layer_id": "agent-sdks", "status": "reopened"}]})
        markup, _ = self.render(inputs=final)
        rows = {row[0].split(" foundation/")[0].split(" us-equities/")[0]: row for row in table(markup, "Foundation and trading layers with the W6 final criteria")[1:]}
        self.assertEqual(rows["Agent SDKs"][6], "reopened")
        self.assertEqual(rows["Agent SDKs"][3], "codex: 0.155.1 drifted: not recorded unmirrored: not recorded")
        self.assertEqual(rows["Portfolio risk"][6], "not recorded absent from final-stack.json")
        for pin, relation in ((None, "no pin recorded to compare"), ("unpinned", "no pin recorded to compare"), ("v2.0.0", "matches the pin"), ("2.0.0 @ 0123456789ab", "matches the pin"), ("2.0.1", "differs from the pin"), ("HEAD", "differs from the pin")):
            with self.subTest(pin=pin):
                pinned_inputs = inputs_fixture()
                pinned_inputs["matrix"]["document"]["rows"][0]["winners"][1]["pin"] = pin
                drifted = table(self.render(inputs=pinned_inputs)[0], "Foundation and trading layers")[1][1]
                self.assertIn("mirror v2.0.0 at 0123456789ab, synced 2026-10-11T15:28:30Z; " + relation, drifted)
        self.assertEqual([view._tag_version(ref) for ref in ("rust-v0.155.1", "v1.30.1", "release-1.2", "v2.0.0-rc.1", "HEAD", "main", "codex-cli-v2", "2")],
                         ["0.155.1", "1.30.1", "1.2", "2.0.0-rc.1", "HEAD", "main", "codex-cli-v2", "2"])
        published = current_fixture()
        published["north_star_layers"] = [{"n": 1, "name": "Market-side data", "target": "one point-in-time store", "lane": "ingestion-b", "acceptance": "source receipts", "state": "due 10-12"}]
        markup, statuses = self.render(current=published)
        self.assertEqual(table(markup, "North-star ten-layer plan the CC publishes")[1], ["1", "Market-side data", "one point-in-time store", "ingestion-b", "source receipts", "due 10-12"])
        self.assertNotIn("North-star ten-layer plan</strong>: not wired", markup)
        self.assertEqual(statuses["cc-landscape"]["not_wired"], [])
        self.assertEqual(statuses["cc-landscape"]["status"], "partial")
        self.assertIn("Partial because of unread records: final-stack.json (not present in the selected checkout).", statuses["cc-landscape"]["detail"])
        no_pins = current_fixture()
        del no_pins["mirrors"]["pins"]
        markup, statuses = self.render(current=no_pins)
        self.assertIn("missing input: cc-now.json#/mirrors/pins", markup)
        self.assertEqual(table(markup, "Workstreams WS1 to WS6")[2], ["WS2", "Second stream", "not recorded", "running", "not recorded", "not recorded"])
        self.assertEqual(table(markup, "Rulings and adjudications")[1][1], "05:59Z as recorded")

    def test_run_pins_follow_the_final_stack_winner_run_field(self):
        # The Claude micro at 38302cd2, (b) (pr1012-claude-micro-38302cd2.md): a run pin is resolved through the same-layer
        # final-stack winner's run field, whose id can differ from the matrix component id, and a winner without a run
        # shows its recorded run_reason.
        inputs = inputs_fixture()
        inputs["final_stack"] = record({"checked_at": "2026-10-11", "summary": {"layers": 1, "status": {"reopened": 1}},
                                        "runs": [{"id": "codex-cli", "pin": "0.155.1"}, {"id": "drifted", "pin": "9.9.9"}],
                                        "layers": [{"catalog": "foundation", "layer_id": "agent-sdks", "status": "reopened",
                                                    "winners": [{"component_id": "codex", "run": "codex-cli", "run_reason": None},
                                                                {"component_id": "drifted", "run": None, "run_reason": "unpinned"}]}]})
        markup, _ = self.render(inputs=inputs)
        rows = {row[0].split(" foundation/")[0].split(" us-equities/")[0]: row for row in table(markup, "Foundation and trading layers with the W6 final criteria")[1:]}
        self.assertEqual(rows["Agent SDKs"][3], "codex: 0.155.1 drifted: not recorded unpinned unmirrored: not recorded")

    def test_an_undated_read_queue_leaves_orchestration_partial(self):
        # The Claude micro at 38302cd2, (b): only a read queue with a current generation time counts as recorded.
        inputs = inputs_fixture()
        inputs["read_queue"]["document"]["updated_utc"] = "not a time"
        markup, statuses = self.render(inputs=inputs)
        self.assertEqual(statuses["cc-orchestration"]["status"], "partial")
        self.assertIn("read-queue-now.json has no parseable updated_utc", statuses["cc-orchestration"]["detail"])
        self.assertIn("age unknown: no parseable generation time", section(markup, "cc-orchestration"))

    def test_token_efficiency_rows_keep_their_own_mechanism(self):
        # The Claude micro at 38302cd2, (b): an Adoption server row is labelled by its case-folded name, RTK included.
        adoption = adoption_fixture()
        adoption["layers"]["session context and token efficiency"]["servers"].update({
            "rtk": {"claude_calls": 5, "claude_sessions": 2, "codex_calls": 3, "codex_conversations": 1},
            "Headroom-Proxy": {"claude_calls": 1, "claude_sessions": 1, "codex_calls": 0, "codex_conversations": 0}})
        markup, _ = self.render(adoption=adoption)
        recorded = {row[1]: row[0] for row in table(markup, "Recorded tool reports and invocations")[1:]}
        self.assertEqual(recorded["rtk invocations"], "RTK")
        self.assertEqual(recorded["Headroom-Proxy invocations"], "Headroom")
        self.assertNotIn("headroom_24h", recorded)

    def test_orchestration_shows_the_recorded_resolution_queues_and_role_counts(self):
        markup, statuses = self.render()
        panel = section(markup, "cc-orchestration")
        self.assertIn("<dt>Default</dt><dd>native composition without a framework layer</dd>", panel)
        self.assertIn("<dt>Overturned when</dt><dd>A paired same-task run shows a framework ahead</dd>", panel)
        landing = table(markup, "Pull requests queued to land")
        self.assertEqual(landing[1], ["uet#78", "4b472bcd", "CI on the rebased head", "15:38Z as recorded"])
        self.assertEqual(table(markup, "Reads waiting")[1], ["uet#74", "0390d6dd", "confirmation", "landing uet#74"])
        roles = {row[0]: row for row in table(markup, "Native orchestration tool calls by role, 24 h")[1:]}
        self.assertEqual(roles["trading-cc"][1:], ["Claude", "Agent 7, Workflow 1"])
        empty = inputs_fixture()
        empty["read_queue"]["document"].update(slots=None, running=[])
        markup, _ = self.render(inputs=empty)
        self.assertIn('Slots: <span class="cc-unrecorded">not measured</span>.', markup)
        self.assertIn('<strong>0</strong> <span>GPT reads running</span>', markup)

    def test_research_queue_rows_and_resume_order(self):
        markup, statuses = self.render()
        rows = table(markup, "Research queue rows")
        self.assertEqual(rows[0], ["date utc", "layer id", "question", "source pr", "evidence", "status", "routed to"])
        self.assertEqual(rows[2][3:], ["not recorded"] * 4)
        self.assertEqual(rows[3][6], "routed spill-over")
        self.assertIn('<ol class="cc-steps"><li>Read AGENTS.md first</li><li>Choose one layer</li></ol>', markup)

    def test_hostile_strings_are_escaped_in_every_section(self):
        current = current_fixture()
        for row in current["landing_queue"] + current["program"] + current["rulings"]:
            for key in list(row):
                row[key] = HOSTILE
        current["orchestration"] = {key: HOSTILE for key in ("slot", "default", "state", "evidence", "next")}
        current["mirrors"] = {"count": HOSTILE, "synced_utc": HOSTILE, "failed": [HOSTILE], "pins": {HOSTILE: {"ref": HOSTILE}}}
        current["north_star_layers"] = [{"n": HOSTILE, "name": HOSTILE}]
        inputs = inputs_fixture()
        inputs["research_queue"] = record("date_utc\t" + HOSTILE + "\n" + HOSTILE + "\t" + HOSTILE + "\n")
        inputs["read_queue"]["document"]["running"][0] = {key: HOSTILE for key in ("read", "pr", "head", "tier", "started_utc")}
        inputs["skills_host"]["document"]["skills"].append(skill(HOSTILE, 1, 1))
        inputs["skills_manifest"]["document"]["skills"].append(pinned(HOSTILE, ref=HOSTILE, url="javascript:" + HOSTILE))
        inputs["skills_claude_lanes"]["document"]["groups"]["by_agent_type"][HOSTILE] = {"children": 1, "children_with_skill_call": 1, "skill_calls": {HOSTILE: 1}}
        inputs["practice_slots"]["document"]["slots"].append({"id": HOSTILE, "status": HOSTILE, "default": HOSTILE})
        inputs["token_window"]["document"]["native"]["codex_total_tokens_by_lane"]["values"][HOSTILE] = 5.0
        inputs["token_tools"]["document"]["tools"].append({"tool": HOSTILE, "command": HOSTILE, "version": HOSTILE, "rc": 3, "message": HOSTILE, "note": HOSTILE})
        inputs["matrix"]["document"]["rows"][0]["title"] = HOSTILE
        inputs["matrix"]["document"]["rows"][0]["winners"][0].update(component_id=HOSTILE, repository="https://github.com/" + HOSTILE)
        inputs["readiness"]["document"]["layers"][0]["selected_tools"][0]["id"] = HOSTILE
        markup, _ = self.render(current=current, inputs=inputs)
        audit = composer_fixture.DocumentAudit()
        audit.feed(markup)
        self.assertFalse({"script", "img"} & set(audit.tags))
        self.assertFalse(any(name.startswith("on") for attributes in audit.attributes for name in attributes))
        self.assertFalse(any(value and value.startswith("javascript:") for attributes in audit.attributes for value in attributes.values()))
        self.assertGreater(markup.count("&lt;script&gt;alert(1)&lt;/script&gt;"), 20)

    def test_private_values_never_render_from_any_section(self):
        identity = "-".join(["dummy", "synthetic", "account"])
        current = current_fixture()
        current["headline"] = "headline " + SYNTHETIC_HOME + " " + " ".join(SYNTHETIC_EMAILS)
        current["in_review"][0]["state"] = " ".join(SYNTHETIC_EMAILS) + " worker_" + identity + "_read"
        current["in_review"][0]["blockers"] = [SYNTHETIC_HOME + "/blocker"]
        current["waiting_on_owner"][1]["detail"] = "mail " + SYNTHETIC_EMAILS[3] + " at " + SYNTHETIC_HOME
        current["waiting_on_owner"][0]["link"] = "https://example.org/" + SYNTHETIC_EMAILS[0]
        current["cc_agents"]["running"].append(identity + " (" + SYNTHETIC_EMAILS[6] + ")")
        current["rulings"][0]["summary"] = SYNTHETIC_HOME + " " + SYNTHETIC_EMAILS[5]
        current["program"][0]["owner"] = identity + " " + SYNTHETIC_EMAILS[7]
        # The micro's (a)4: a token over 4,096 characters is not decoded, so its encoded at sign is matched in place.
        current["program"][1]["title"] = "x" * 4100 + SYNTHETIC_EMAILS[1] + " " + "y" * 4100 + SYNTHETIC_EMAILS[2]
        fleet = fleet_fixture()
        fleet["lanes_live"][0]["lane_model"] = SYNTHETIC_EMAILS[4]
        inputs = inputs_fixture()
        inputs["research_queue"] = record("date_utc\tquestion\n2026-10-11\t" + SYNTHETIC_HOME + " " + " ".join(SYNTHETIC_EMAILS) + " " + identity + "\n")
        inputs["read_queue"]["document"]["waiting"][0]["gates"] = SYNTHETIC_EMAILS[2]
        inputs["token_tools"]["document"]["tools"][1]["message"] = "ledger at " + SYNTHETIC_HOME + " for " + SYNTHETIC_EMAILS[1]
        inputs["practice_slots"]["document"]["slots"][0]["default"] = SYNTHETIC_EMAILS[3]
        current["program"][1]["owner"] = " ".join(WHOLE_ADDRESS_FORMS) + " " + QUOTED_PROBE
        with patch.object(view._sanitization.Path, "home", return_value=Path("/synthetic") / identity):
            markup, _ = view.render(current, fleet, inputs, adoption=adoption_fixture(), refreshed=REFRESHED)
        self.assertEqual(leaked_emails(markup), [])
        self.assertEqual(surviving_parts(markup), [])
        self.assertNotIn(QUOTED_PROBE, decoded_text(markup))
        self.assertNotIn("synthetic-user", markup)
        self.assertNotIn(identity, markup)
        self.assertIn("[email omitted]", markup)
        self.assertNotIn('href="https://example.org/', markup)
        names = prohibited_names()
        if names:
            self.assertEqual(identity_hits(markup, names), 0)
            for path in ("tools/local-pages/command_center_view.py", "tools/local-pages/token_tools_now.py", "tools/skill-usage/render_units.py",
                         "tools/skill-usage/systemd/native-agent-skill-usage.service.in"):
                self.assertEqual(identity_hits((ROOT / path).read_text(), names), 0, path)


class CommandCenterPolicyTests(unittest.TestCase):
    def test_command_center_roles_are_exact_and_cannot_widen(self):
        committed = json.loads((ROOT / "tools/local-pages/source_policy.json").read_text())
        roles = committed["command_center"]
        granted = {(entry["root"], entry["path"]) for entries in roles.values() for entry in entries}
        expected = {(base, relative) for _, base, relative, _, _ in BUILDER.COMMAND_CENTER_INPUTS}
        self.assertEqual(granted, expected)
        self.assertEqual({role for _, _, _, role, _ in BUILDER.COMMAND_CENTER_INPUTS}, set(roles))
        for name, base, relative, role, _ in BUILDER.COMMAND_CENTER_INPUTS:
            self.assertIn({"root": base, "path": relative}, roles[role], name)
        reads = policy.CommandCenterReads(ROOT, Path("/synthetic-state"), ROOT / "tools/local-pages/source_policy.json")
        self.assertEqual(reads.authorize("command_center_manifests", ROOT / "manifests/evidence.json"), ROOT / "manifests/evidence.json")
        for role, path in (("command_center_manifests", ROOT / "manifests/stack.json"), ("command_center_skills", Path("/synthetic-state/coordination/command-center/skills/skill-usage-host-20261010T1435Z.json")),
                           ("command_center_usage", ROOT / "manifests/evidence.json"), ("command_center_queues", Path("/synthetic-state/coordination/ns2604-coop/research-queue.tsv.bak"))):
            with self.subTest(role=role, path=path.name), self.assertRaises(policy.SourcePolicyError):
                reads.authorize(role, path)
        for bad in ({"command_center_x": [{"root": "user", "path": "notes.json"}]}, {"wrong_prefix": []}, {"command_center_x": [{"root": "state", "path": "../escape.json"}]},
                    {"command_center_x": [{"root": "state", "path": "coordination/credentials.json"}]}):
            with self.subTest(bad=bad):
                broken = dict(committed, command_center=bad)
                path = Path(self.enterContext(__import__("tempfile").TemporaryDirectory())) / "policy.json"
                path.write_text(json.dumps(broken))
                with self.assertRaises(policy.SourcePolicyError):
                    policy.CommandCenterReads(ROOT, Path("/synthetic-state"), path)


class CommandCenterComposerTests(unittest.TestCase):
    """The real composer publishes, links and degrades the page."""

    write_json = staticmethod(composer_fixture.LocalPagesTests.write_json)
    refresh = composer_fixture.LocalPagesTests.refresh

    def setUp(self):
        composer_fixture.LocalPagesTests.setUp(self)
        self.assertIn("command_center", json.loads(self.policy_path.read_text()))

    def add_sections(self):
        fixture = current_fixture()
        for key in ("in_review", "landings_today", "cc_agents", "token_efficiency", "token_use_24h", "orchestration", "landing_queue", "program", "mirrors", "rulings"):
            self.current[key] = copy.deepcopy(fixture[key])
        self.write_json(self.current_path, self.current)

    def write_inputs(self) -> dict:
        documents = inputs_fixture()
        digests = {}
        for name, base, relative, _, kind in BUILDER.COMMAND_CENTER_INPUTS:
            document = documents[name].get("document")
            if document is None:
                continue
            path = {"repo": self.root, "state": self.state}[base] / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(document if kind == "text" else json.dumps(document))
            digests[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        return digests

    def test_page_builds_from_fixture_and_is_linked_from_index_nav_and_sources(self):
        self.add_sections()
        digests = self.write_inputs()
        receipt = self.refresh()
        page = (self.output / "command-center.html").read_text()
        for anchor in PANELS:
            self.assertIn(f'id="{anchor}"', page)
        for value in (digests["readiness"], digests["evidence"], "3 files, 1 receipt, 0 convergence records", "fixture-lane", "Should X replace Y?", "nas#1004", "lane-00",
                      "rtk gain --format json", "orchestration-frameworks", "fixture/skills@0123456789ab"):
            self.assertIn(value, page)
        index = (self.output / "index.html").read_text()
        overview = index[index.index('<ul class="page-index">'):]
        self.assertTrue(overview.startswith('<ul class="page-index"><li><a href="command-center.html">Command center</a>'))
        for name in ("index", "readiness", "fleet", "sources", "command-center"):
            self.assertIn('<a href="command-center.html"', (self.output / (name + ".html")).read_text())
        self.assertIn('href="sources.html#command-center"', page)
        sources = (self.output / "sources.html").read_text()
        self.assertIn('<section id="command-center" class="panel"><h2>Command center</h2>', sources)
        for role in ("command_center_manifests", "command_center_queues", "command_center_skills", "command_center_usage", "command_center_landscape"):
            self.assertIn("read under the exact <code>" + role + "</code> grant", sources)
        record = receipt["command_center"]
        self.assertEqual(record["status"], "RECORDED")
        self.assertEqual(set(record["panels"]), set(PANELS))
        self.assertEqual(record["inputs"]["readiness"]["sha256"], digests["readiness"])
        self.assertEqual(record["inputs"]["final_stack"]["status"], "missing")
        self.assertNotIn("document", record["inputs"]["readiness"])
        for name, _, _, role, _ in BUILDER.COMMAND_CENTER_INPUTS:
            if name in digests:
                self.assertEqual(receipt["inputs"]["command_center:" + name]["role"], role)
        self.assertIn("module:command_center_view", receipt["inputs"])
        self.assertEqual(set(record["not_wired"]), {"token_report", "north_star"})
        self.assertIn(html.escape(BUILDER.load_local("command_center_view").NOT_WIRED["north_star"].split(";")[0], quote=True), sources)

    def test_a_published_projection_replaces_its_not_wired_record(self):
        self.add_sections()
        self.write_inputs()
        self.current["north_star_layers"] = [{"n": 1, "name": "Market-side data", "target": "t", "lane": "ingestion-b", "acceptance": "a", "state": "s"}]
        self.write_json(self.current_path, self.current)
        receipt = self.refresh()
        reasons = BUILDER.load_local("command_center_view").NOT_WIRED
        self.assertEqual(receipt["command_center"]["not_wired"], {"token_report": reasons["token_report"]})
        sources = (self.output / "sources.html").read_text()
        self.assertNotIn(html.escape(reasons["north_star"].split(";")[0], quote=True), sources)
        self.assertIn("Market-side data", (self.output / "command-center.html").read_text())

    def test_missing_sections_and_inputs_render_gaps_and_still_publish(self):
        receipt = self.refresh()
        page = (self.output / "command-center.html").read_text()
        for name in ("cc-now.json#/in_review", "cc-now.json#/orchestration", "cc-now.json#/cc_agents/running",
                     "repo:catalogs/north-star/readiness.json: not present in the selected checkout",
                     "state:coordination/ns2604-coop/read-queue-now.json: not present in the state root",
                     "state:coordination/command-center/pages/token-tools-now.json: not present in the state root",
                     "state:coordination/command-center/skills/skill-usage-host-latest.json: not present in the state root"):
            self.assertIn("missing input: " + name, page)
        self.assertIn("pending #1007 (#1008 landed 2026-10-11 21:34:23Z)", page)
        self.assertNotIn("#1008/#1007", page)
        self.assertEqual(receipt["command_center"]["inputs"]["readiness"]["status"], "missing")
        self.assertNotIn("command_center:readiness", receipt["inputs"])
        self.assertIn("Review a source", page)

    def test_quoted_and_rfc_local_parts_leave_no_part_of_the_address(self):
        # Astra's first read of a737ef98 (P1, review_probes.py:23): the quoted local part in her probe survived the
        # whole composer. Every assertion here reads the decoded page text, with no address grammar of its own.
        self.add_sections()
        self.write_inputs()
        self.current["in_review"][0]["state"] = "Reply to " + QUOTED_PROBE + " and " + " ; ".join(WHOLE_ADDRESS_FORMS)
        self.current["waiting_on_owner"].append({"what": "Write to " + WHOLE_ADDRESS_FORMS[1], "detail": WHOLE_ADDRESS_FORMS[3]})
        self.write_json(self.current_path, self.current)
        receipt = self.refresh()
        page = (self.output / "command-center.html").read_text()
        self.assertNotIn(QUOTED_PROBE, decoded_text(page))
        self.assertNotIn('"reviewer"', decoded_text(page))
        self.assertEqual(surviving_parts(page), [])
        self.assertIn("[email omitted]", page)
        self.assertEqual(surviving_parts(json.dumps(receipt)), [])

    def test_empty_quoted_and_punctuation_only_addresses_never_reach_the_page(self):
        # Astra's read of 51f85b5b, P1 1, with her probe inputs (review_probes.py): both stayed readable on the page.
        self.add_sections()
        self.write_inputs()
        for address in ('""' + AT + "example.target", "!!!" + AT + "example.target"):
            with self.subTest(address=address):
                self.current["in_review"][0]["state"] = "Reply to " + address
                self.write_json(self.current_path, self.current)
                self.refresh()
                page = decoded_text((self.output / "command-center.html").read_text())
                self.assertNotIn(address, page)
                self.assertNotIn(AT + "example.target", page)

    def test_slash_and_backtick_local_parts_never_reach_the_page_or_receipt(self):
        # Astra's read of 3d7b1e7a, P1 1 (review_probes.py): a real composer fixture with a slash or backtick address in
        # in_review[0].state published the complete address in command-center.html. The parts are unique, so the
        # assertions need no address grammar; the encoded forms are the neighbours the token decoding must still reach.
        self.add_sections()
        self.write_inputs()
        domain = AT + "zqdomain.example.org"
        forms = ("/" + domain, "x/" + domain, "`" + domain, "zqlocal/" + domain, "`zqlocal" + domain, "zqlocal`" + domain, "a/zqlocalb" + domain, "zqlocal//" + domain,
                 "%2F%40zqdomain.example.org", "x%2F" + domain, "&#47;&#64;zqdomain.example.org", "%60%40zqdomain.example.org", "&#96;" + domain)
        # The last two are natural address path segments (gcloud's one directory per account, and x/ plus an address plus /y):
        # the path-segment exemption needs a slash right before the at sign, so both mask, directory prefix included.
        pairs = [(form, "[email omitted]") for form in forms] + [("`a/zqlocal" + domain + "`", "`[email omitted]`"),
                                                                 ("legacy_credentials/zqlocal" + domain + "/adc.json", "[email omitted]/adc.json"),
                                                                 ("x/zqlocal" + domain + "/y", "[email omitted]/y")]
        for form, shown in pairs:
            with self.subTest(form=form):
                self.current["in_review"][0]["state"] = "Reply to " + form
                self.current["waiting_on_owner"] = [{"what": "Write to " + form, "detail": form}]
                self.write_json(self.current_path, self.current)
                receipt = self.refresh()
                page = (self.output / "command-center.html").read_text()
                self.assertNotIn("zqdomain", decoded_text(page))
                self.assertNotIn("zqlocal", decoded_text(page))
                self.assertEqual(re.findall(r"Reply to ([^<]*)<", page), [shown])
                self.assertEqual(re.findall(r"Write to ([^<]*)<", page), [shown])
                self.assertNotIn("zqdomain", decoded_text(json.dumps(receipt)))
        public = "imports `" + AT + "AGENTS.md` and https://medium.com/" + AT + "someone.handle/a-post"
        self.current["in_review"][0]["state"] = public
        self.write_json(self.current_path, self.current)
        self.refresh()
        self.assertIn(html.escape(public, quote=True), (self.output / "command-center.html").read_text())

    def test_entity_local_parts_in_long_tokens_never_reach_the_page_or_receipt(self):
        # The GPT fix3 verdict at 38302cd2, BLOCKER 2 (fix3-pr1012-38302cd2a/VERDICT.md): no token over 4,096 characters
        # reaches the page unchecked. The parts are unique, so the assertions need no address grammar.
        self.add_sections()
        self.write_inputs()
        for entity in ("&#47;", "&#96;", "&#65;", "&sol;"):
            for value in ("x" * 4100 + ":" + entity + AT + "zqdomain.example.org", "x" * 4100 + ":" + entity + "&#122;&#113;local" + AT + "zqdomain.example.org"):
                with self.subTest(entity=entity, neighbour="local" in value):
                    self.current["in_review"][0]["state"] = value
                    self.current["waiting_on_owner"] = [{"what": value, "detail": value}]
                    self.write_json(self.current_path, self.current)
                    receipt = self.refresh()
                    page = decoded_text((self.output / "command-center.html").read_text())
                    self.assertNotIn("zq", page)
                    self.assertIn("[email omitted]", page)
                    self.assertNotIn("zq", decoded_text(json.dumps(receipt)))

    def test_composer_pages_withhold_every_digest_the_receipt_marks_private(self):
        # Astra's read of 51f85b5b, P1 2 (#161): sources.html published the SHA-256 of research-queue.tsv's raw bytes, so a
        # guessed private line could be confirmed. The command-center state inputs and cc-now.json are marked private and
        # keep their digests in the nonserved receipt only. Scope: the pages this composer builds; the architecture
        # builder's pages follow the same rule in test_local_pages_architecture_read_boundary.py. Every other state-root
        # input follows the same class rule in test_command_center_and_sources_serve_only_digests_of_published_bytes.
        self.add_sections()
        self.write_inputs()
        queue = self.state / "coordination/ns2604-coop/research-queue.tsv"
        raw = ("date_utc\tquestion\n2026-10-11\tContact zqprivate" + AT + "example.org\n").encode()
        queue.write_bytes(raw)
        receipt = self.refresh()
        private = {"command_center:" + name: hashlib.sha256(((self.state if base == "state" else self.root) / relative).read_bytes()).hexdigest()
                   for name, base, relative, _, _ in BUILDER.COMMAND_CENTER_INPUTS if base == "state" and ((self.state / relative).is_file())}
        # cc-now.json is the CC's private state too; the composer's notes and custody rows keep its digest in the receipt.
        private["cc_now"] = hashlib.sha256(self.current_path.read_bytes()).hexdigest()
        self.assertIn("command_center:research_queue", private)
        for name, digest in private.items():
            with self.subTest(input=name):
                self.assertEqual(receipt["inputs"][name]["sha256"], digest)
                self.assertTrue(receipt["inputs"][name]["private"])
        pages = sorted(self.output.rglob("*.html"))
        self.assertIn("sources.html", [page.name for page in pages])
        for page in pages:
            text = page.read_text()
            with self.subTest(page=page.name):
                self.assertEqual([name for name, digest in private.items() if digest in text], [])
                self.assertNotIn("zqprivate", decoded_text(text))
        sources = (self.output / "sources.html").read_text()
        self.assertIn("private, not published (host state)", sources)
        for name in ("readiness", "evidence"):
            self.assertIn(hashlib.sha256((self.root / dict((n, r) for n, _, r, _, _ in BUILDER.COMMAND_CENTER_INPUTS)[name]).read_bytes()).hexdigest(), sources)

    def test_command_center_and_sources_serve_only_digests_of_published_bytes(self):
        # Astra's read of 3d7b1e7a, P1 2 (#161): the footer of the new page served the SHA-256 of the native builder's render
        # of the state root, whose raw bytes held a private address (the gate owner), and sources.html served the raw digests
        # of the gate receipt, the gap board and the roadmap inputs. A digest of private bytes confirms a guessed value
        # offline. The class rule: bytes read from the state root are private, whatever their name, and keep their digest in
        # the nonserved receipt only; a digest on these two pages is that of bytes the repository publishes.
        self.add_sections()
        self.write_inputs()
        private = "zqprivate" + AT + "example.org"  # built at run time: the repository holds no address literal
        gate = json.loads(self.gate.read_text())
        gate["owner"] = private
        self.write_json(self.gate, gate)
        self.gaps["gaps"][0]["owner"] = private
        self.write_json(self.gaps_path, self.gaps)
        self.write_json(self.road_inputs, {"board_base": str(self.state / "coordination/ns2604-coop/readiness-20261005/jobs/board.json"), "handbook_commit": private})
        queue = self.state / "coordination/ns2604-coop/research-queue.tsv"
        queue.write_bytes(("date_utc\tquestion\n2026-10-11\tContact " + private + "\n").encode())
        receipt = self.refresh()
        native, _ = BUILDER.load_native(self.root)
        raw = native.render(native.build(self.root, self.state, self.source_index))
        self.assertIn(private.encode(), raw)  # the oracle is real: the raw native manifest holds the private value
        manifest = hashlib.sha256(raw).hexdigest()
        self.assertEqual(receipt["native_readiness_manifest_sha256"], manifest)  # the nonserved receipt keeps it
        state = {name: item for name, item in receipt["inputs"].items() if item.get("sha256") and Path(item["path"].split("#")[0]).is_relative_to(self.state)}
        for name in ("readiness:gate", "gaps", "roadmap", "roadmap_inputs", "cc_now", "adoption", "command_center:research_queue"):
            self.assertIn(name, state)
        for name, item in state.items():
            with self.subTest(input=name):
                self.assertTrue(item.get("private"))
                self.assertEqual(item["sha256"], hashlib.sha256(Path(item["path"]).read_bytes()).hexdigest())  # the receipt keeps it
        published = {item["sha256"] for name, item in receipt["inputs"].items() if item.get("sha256") and name not in state}
        self.assertIn(hashlib.sha256((self.root / "tools/north-star/sources.json").read_bytes()).hexdigest(), published)
        private_digests = {item["sha256"] for item in state.values()} | {manifest}
        for name in ("command-center", "sources"):
            page = (self.output / (name + ".html")).read_text()
            with self.subTest(page=name):
                served = set(re.findall(r"\b[0-9a-f]{64}\b", page))
                self.assertEqual(served & private_digests, set())
                self.assertEqual(served - published, set(), "a digest on this page is not that of bytes the repository publishes")
                self.assertNotIn("zqprivate", decoded_text(page))
                self.assertIn("<strong>Native readiness manifest SHA-256:</strong> <code>private, not published (host state)</code>", page)
        # Every published output, not only these two pages, withholds every private digest and any 7-character prefix of
        # one (the GPT fix3 verdict at 38302cd2, BLOCKER 1); absence of the 7-character prefix covers every longer one.
        outputs = sorted(path for path in self.output.rglob("*") if path.is_file())
        self.assertEqual(len(outputs), len(receipt["outputs"]))
        for path in outputs:
            with self.subTest(everywhere=path.name):
                text = path.read_text()
                self.assertEqual([digest for digest in private_digests if digest[:7] in text], [])
        heading = re.search(r'<h2 id="manifest-title"[^>]*>(.*?)</h2>', (self.output / "readiness.html").read_text()).group(1)
        self.assertIn("private, not published (host state)", heading)
        sources = (self.output / "sources.html").read_text()
        for name in ("readiness", "evidence"):
            self.assertIn(hashlib.sha256((self.root / dict((n, r) for n, _, r, _, _ in BUILDER.COMMAND_CENTER_INPUTS)[name]).read_bytes()).hexdigest(), sources)
        self.assertEqual(receipt["outputs"]["command-center.html"]["sha256"], hashlib.sha256((self.output / "command-center.html").read_bytes()).hexdigest())

    def test_content_addressed_names_of_private_inputs_withhold_their_digest_prefix(self):
        # The Claude micro at 38302cd2, (d)3 (pr1012-claude-micro-38302cd2.md): a state-root receipt named by its own
        # SHA-256 carried a 16-character prefix of a private digest onto the pages. No page carries one now, names included.
        raw = self.gate.read_bytes()
        named = self.state / ("gate-" + hashlib.sha256(raw).hexdigest()[:16] + ".json")
        named.write_bytes(raw)
        self.source_spec["sources"]["gate"] = {"root": "state", "path": named.name}
        self.write_json(self.source_index, self.source_spec)
        policy_document = json.loads(self.policy_path.read_text())
        policy_document["sources"]["gate"] = [{"root": "state", "path": named.name}]
        self.write_json(self.policy_path, policy_document)
        receipt = self.refresh()
        digest = hashlib.sha256(raw).hexdigest()
        self.assertEqual(receipt["inputs"]["readiness:gate"]["sha256"], digest)  # the nonserved receipt keeps it
        for page in sorted(self.output.rglob("*.html")):
            with self.subTest(page=page.name):
                self.assertNotIn(digest[:7], page.read_text())
        self.assertIn("state:gate-[digest prefix withheld].json", (self.output / "sources.html").read_text())

    def test_registry_metadata_digests_of_the_state_root_are_withheld_on_sources(self):
        # The same class rule for the Fleet source notes: the role projection's registry files are read from the state root.
        registry = self.state / "coordination/ns2604-coop/lanes/hcom-lanes.json"
        self.write_json(registry, {"zqlane": "zqprivate" + AT + "example.org"})
        digest = hashlib.sha256(registry.read_bytes()).hexdigest()
        projection = {"document": self.adoption, "window": {}, "sources": [{"path": str(registry), "sha256": digest, "read_utc": REFRESHED, "mtime_utc": REFRESHED}],
                      "source_errors": [], "instances": {"role_map": {}}, "orchestration": {"claude_by_role": {}, "codex_by_role": {}, "codex_unattributed": {}}, "sdk": {"status": "UNREPORTED"}}
        role_module = SimpleNamespace(project=lambda *unused: projection)
        original = BUILDER.load_local
        with patch.object(BUILDER, "load_local", side_effect=lambda name: role_module if name == "adoption_roles" else original(name)):
            receipt = self.refresh()
        self.assertEqual(receipt["adoption_role_attribution"]["sources"][0]["sha256"], digest)  # the nonserved receipt keeps it
        sources = (self.output / "sources.html").read_text()
        self.assertIn("registry metadata SHA-256 <code>private, not published (host state)</code>", sources)
        self.assertNotIn(digest, "\n".join(page.read_text() for page in self.output.rglob("*.html")))

    def test_unapproved_input_is_a_gap_not_a_stop(self):
        self.write_inputs()
        document = json.loads(self.policy_path.read_text())
        document["command_center"]["command_center_manifests"] = [entry for entry in document["command_center"]["command_center_manifests"] if entry["path"] != "catalogs/north-star/readiness.json"]
        self.write_json(self.policy_path, document)
        receipt = self.refresh()
        self.assertEqual(receipt["command_center"]["inputs"]["readiness"]["reason"], "unreadable (SourcePolicyError)")
        self.assertEqual(receipt["command_center"]["inputs"]["evidence"]["status"], "read")
        self.assertIn("unreadable (SourcePolicyError)", (self.output / "command-center.html").read_text())

    def test_failed_fleet_adapter_keeps_the_page_with_stated_gaps(self):
        with patch.object(BUILDER, "collect_fleet", side_effect=OSError("synthetic adapter failure")):
            receipt = self.refresh()
        page = (self.output / "command-center.html").read_text()
        self.assertIn("missing input: fleet lanes_live", page)
        self.assertNotIn("synthetic adapter failure", page)
        self.assertEqual(receipt["command_center"]["panels"]["cc-sessions"]["status"], "missing")

    def test_view_failure_publishes_a_placeholder_and_every_other_page(self):
        original = BUILDER.load_local
        def broken(*_, **__):
            raise ValueError("synthetic view failure")
        def load(name):
            module = original(name)
            return SimpleNamespace(render=broken, NOT_WIRED=module.NOT_WIRED) if name == "command_center_view" else module
        with patch.object(BUILDER, "load_local", side_effect=load):
            receipt = self.refresh()
        page = (self.output / "command-center.html").read_text()
        self.assertIn("Command center view unavailable (ValueError)", page)
        self.assertNotIn("synthetic view failure", page)
        self.assertEqual(receipt["command_center"]["status"], "UNREPORTED")
        self.assertNotIn("not_wired", receipt["command_center"])
        for name in ("index", "readiness", "gaps", "roadmap", "fleet", "sources"):
            self.assertTrue((self.output / (name + ".html")).is_file())

    def test_composed_page_masks_private_values(self):
        self.add_sections()
        self.write_inputs()
        home_name = Path.home().name
        self.current["in_review"][0]["state"] = "see " + SYNTHETIC_HOME + " and " + " ".join(SYNTHETIC_EMAILS)
        self.current["waiting_on_owner"].append({"what": "Owner item for worker_" + home_name + "_read", "detail": "/".join(["", "home", home_name, "notes"])})
        self.current["cc_agents"]["running"].append("cc-" + home_name + " (" + SYNTHETIC_EMAILS[3] + ")")
        self.current["rulings"].append({"file": "ruling-" + home_name + ".md", "utc": "06:00Z", "summary": SYNTHETIC_EMAILS[7]})
        self.write_json(self.current_path, self.current)
        queue = self.state / "coordination/ns2604-coop/research-queue.tsv"
        queue.write_text("date_utc\tquestion\n2026-10-11\t" + "/".join(["", "home", home_name, "q"]) + " " + " ".join(SYNTHETIC_EMAILS) + "\n")
        self.refresh()
        for name in ("command-center", "index", "readiness", "sources"):
            page = (self.output / (name + ".html")).read_text()
            self.assertEqual(leaked_emails(page), [], name)
            self.assertNotIn("synthetic-user", page)
            self.assertNotRegex(page, r"/(?:home|Users)/[^/\s\"'<>$]")
            if len(home_name) >= 3:
                self.assertEqual(identity_hits(page, [home_name]), 0)
            names = prohibited_names()
            if names:
                self.assertEqual(identity_hits(page, names), 0)


if __name__ == "__main__":
    unittest.main()
