"""Contracts for the consolidated command-center page and its composer wiring."""

from __future__ import annotations

import copy
import hashlib
from html.parser import HTMLParser
import importlib.util
import json
import os
from pathlib import Path
import re
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tests import test_local_pages as composer_fixture


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("local_pages_command_center_view", ROOT / "tools/local-pages/command_center_view.py")
view = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(view)
BUILDER = composer_fixture.BUILDER
SYNTHETIC_HOME = "/".join(["", "home", "synthetic-user", "work"])
SYNTHETIC_EMAILS = ("owner@example.org", "owner%40example.org", "owner&#64;example.org")
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+(?:@|%40|&#0*64;|&#x0*40;)[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}", re.I)
PANELS = ("cc-sessions", "cc-prs", "cc-tokens", "cc-skills", "cc-manifests", "cc-owner")


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
                          "codex_tokens_M": {"input": 50.0, "output": 2.5}, "claude_cost_usd_by_model": {"claude-opus-5-5": 12.5},
                          "note": "Fixture usage note"},
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


def manifests_fixture() -> dict:
    readiness = {"summary": {"gates": 2, "layers": 3, "sdk_items": 1, "recorded_claims": 40, "unverified_claims": 2, "unverified_sources": 0},
                 "gates": [{"id": "G1", "fields": {"state": {"status": "RECORDED", "value": "MET"}}}, {"id": "G2", "fields": {"state": {"status": "UNVERIFIED"}}}],
                 "open_items": [{"id": "O1", "fields": {"state": {"status": "RECORDED", "value": "MET"}}}, {"id": "O2", "fields": {}}]}
    evidence = {"files": [{"path": "a"}, {"path": "b"}, {"path": "c"}], "receipts": [{"id": "r"}], "convergence_records": []}
    return {"readiness": {"status": "read", "label": "repo:catalogs/north-star/readiness.json", "sha256": "1" * 64, "bytes": 1234, "document": readiness},
            "evidence": {"status": "read", "label": "repo:manifests/evidence.json", "sha256": "2" * 64, "bytes": 5678, "document": evidence}}


def prohibited_names() -> list[str]:
    """The comma-separated LANDING_PROHIBITED_NAMES, read at test time so no name enters the repository (#975)."""
    return [name.strip() for name in os.environ.get("LANDING_PROHIBITED_NAMES", "").split(",") if name.strip()]


def identity_hits(text: str, names: list[str]) -> int:
    return sum(len(re.findall(r"(?<![A-Za-z0-9])" + re.escape(name) + r"(?![A-Za-z0-9])", text, re.I)) for name in names)


class CommandCenterViewTests(unittest.TestCase):
    def render(self, current=None, fleet=None, manifests=None):
        return view.render(current_fixture() if current is None else current, fleet_fixture() if fleet is None else fleet,
                           manifests_fixture() if manifests is None else manifests)

    def test_fixture_renders_every_panel_with_stated_status(self):
        markup, statuses = self.render()
        for anchor in PANELS:
            self.assertIn(f'id="{anchor}"', markup)
        for anchor in ("cc-prs", "cc-owner", "cc-sessions", "cc-tokens"):
            self.assertIn(f'<a href="#{anchor}"><strong>', markup)
        self.assertEqual({anchor: row["status"] for anchor, row in statuses.items()},
                         {"cc-sessions": "wired", "cc-prs": "wired", "cc-tokens": "partial", "cc-skills": "partial", "cc-manifests": "partial", "cc-owner": "wired"})
        found = tables(markup)
        lanes = {row[0]: row for row in found["Live Codex lanes"][1:]}
        self.assertEqual(lanes["lane-one"][1:3], ["active", "18 s hcom lane-one-abcd, active"])
        self.assertIn("gpt-fixture", lanes["lane-one"][3])
        self.assertEqual(lanes["lane-one"][4], "standard")
        self.assertEqual(lanes["lane-two"][2:4], ["not recorded", "not recorded"])
        self.assertIn("owner session (reports to CC)", markup)
        self.assertNotIn("native-agent-stack-1a", markup)
        self.assertEqual(found["Other hcom agents"][1][:3], ["stray-agent", "claude", "blocked"])
        subagents = {row[0]: row for row in found["Command-center subagents running"][1:]}
        self.assertEqual(subagents["cc-fixture-builder"][1:], ["#101 round 3, resumed", "not recorded"])
        self.assertEqual(subagents["cc-fixture-micro"][1:], ["#102 micro", "claude-opus-5-5"])
        self.assertEqual(subagents["cc-bare"][1:], ["not recorded", "not recorded"])
        self.assertIn("<summary>1 parked lane</summary>", markup)
        self.assertIn("<summary>2 landed today</summary>", markup)
        manifests = {row[0]: row for row in found["Manifest identities and counts"][1:]}
        self.assertIn("1" * 64, manifests["Readiness manifest"][1])
        self.assertIn("2 gates, 3 layers, 1 sdk items, 40 recorded claims, 2 unverified claims, 0 unverified sources", manifests["Readiness manifest"][2])
        self.assertEqual(manifests["Evidence manifest"][2], "3 files, 1 receipt, 0 convergence records")
        self.assertIn("pending #1007", manifests["Final-stack manifest"][1])
        self.assertIn("not wired", manifests["Research queue"][1])
        states = {row[0]: row[1:] for row in found["Readiness manifest counts by recorded state"][1:]}
        self.assertEqual(states, {"MET": ["1", "1"], "UNVERIFIED": ["1", "0"], "no state field": ["0", "1"]})
        owner = markup[markup.index('id="cc-owner"'):]
        self.assertLess(owner.index("Approve the fixture lane"), owner.index("Rotate a fixture token"))
        self.assertIn("Run the fixture command", owner)
        self.assertIn("Read the fixture note", owner)

    def test_pr_optional_fields_render_values_absences_and_unsupported_values(self):
        markup, statuses = self.render()
        rows = {row[0]: row for row in tables(markup)["Pull requests in review, in the CC's order"][1:]}
        self.assertEqual(tables(markup)["Pull requests in review, in the CC's order"][0],
                         ["PR", "Work", "Head", "Round", "Next gate", "Blockers", "Follow-ups", "Recorded state"])
        self.assertEqual(rows["#101"][2:7], ["abc12345", "3", "Astra micro at abc12345", "P2 reinstall race", "one re-pin sync live copy"])
        self.assertEqual(rows["#102"][2:7], ["not recorded"] * 5)
        self.assertEqual(rows["#103 / #104"][5:7], ["none", "none"])
        self.assertEqual(rows["#105"][2:7], ["not recorded unsupported value"] * 2 + ["not recorded"] + ["not recorded unsupported value"] * 2)
        self.assertEqual(rows["#102"][7], "reads queued")
        self.assertIn('<td class="cc-pr-next-gate"><strong>Astra micro at abc12345</strong></td>', markup)
        self.assertEqual(statuses["cc-prs"]["status"], "wired")
        unrecorded = current_fixture()
        unrecorded["in_review"] = [{"pr": "#102", "what": "w", "state": "s"}]
        markup, statuses = self.render(current=unrecorded)
        self.assertEqual(statuses["cc-prs"]["status"], "partial")
        self.assertIn("head, round, next gate, blockers, follow-ups", statuses["cc-prs"]["detail"])

    def test_missing_inputs_render_stated_gaps_without_raising(self):
        failed_fleet = {"fleet_source": "not reported", "at": None, "lanes_live": None, "lanes_parked": None, "claude_sessions": None,
                        "exec_reads_in_flight": None, "availability": {name: {"status": "UNKNOWN"} for name in ("lanes_live", "lanes_parked", "claude_sessions")},
                        "tracking": {"schema": "fleet-tracking/1", "status": "UNREPORTED", "hcom": {"agents": [], "status": "UNKNOWN"}, "lanes": []}}
        missing = {"readiness": {"status": "missing", "reason": "not present in the selected checkout"}, "evidence": {"status": "missing", "reason": "unreadable (ValueError)"}}
        for current, fleet, manifests in (({"schema": "cc-now/1"}, failed_fleet, missing), ({}, {}, {}), (None, None, None)):
            with self.subTest(fleet=bool(fleet)):
                markup, statuses = view.render(current, fleet, manifests)
                for name in ("cc-now.json#/in_review", "cc-now.json#/landings_today", "cc-now.json#/token_efficiency", "cc-now.json#/token_use_24h", "cc-now.json#/waiting_on_owner",
                             "cc-now.json#/cc_agents/running", "fleet lanes_live", "fleet claude_sessions", "readiness manifest"):
                    self.assertIn("missing input: " + name, markup)
                self.assertEqual(statuses["cc-sessions"]["status"], "missing")
                for anchor in ("cc-prs", "cc-tokens", "cc-manifests", "cc-owner"):
                    self.assertEqual(statuses[anchor]["status"], "missing")
                self.assertIn('<strong>UNKNOWN</strong> <span>in review</span>', markup)
        self.assertIn("not present in the selected checkout", view.render({}, {}, missing)[0])
        self.assertEqual(view.render({}, {"tracking": None}, {})[1]["cc-skills"]["status"], "missing")

    def test_skill_rates_keep_unknown_distinct_from_zero(self):
        markup, _ = self.render()
        rows = {row[0]: row for row in tables(markup)["Skill invocations per published lane, 300 s rate window"][1:]}
        self.assertTrue(rows["abcd"][2].startswith("UNKNOWN"))
        self.assertIn("No qualified producer.", rows["abcd"][2])
        self.assertTrue(rows["efgh"][2].startswith("0 calls/s (reported)"))
        self.assertIn("0 means no recorded calls", rows["efgh"][2])
        self.assertTrue(rows["ijkl"][2].startswith("UNKNOWN"))
        self.assertNotIn("0 means no recorded calls", rows["ijkl"][2])
        self.assertIn("skill_usage.py reports", markup)
        shared = fleet_fixture()
        shared["tracking"]["lanes"] = [rate("abcd", "UNKNOWN", None, "Shared reason."), rate("efgh", "UNKNOWN", None, "Shared reason.")]
        markup, _ = self.render(fleet=shared)
        self.assertEqual(markup.count("Shared reason."), 1)
        self.assertIn("<strong>Every row:</strong> Shared reason.", markup)

    def test_token_panel_labels_reported_values_and_windows(self):
        markup, statuses = self.render()
        saved = {row[0]: row for row in tables(markup)["Savings the CC reports in token_efficiency; this page measures none"][1:]}
        self.assertTrue(saved["RTK tokens saved rtk.tokens_saved"][1].startswith("2.5M"))
        self.assertEqual(saved["RTK tokens saved rtk.tokens_saved"][2], "not stated in source")
        self.assertEqual(saved["RTK hook audit rtk_hook_audit_7d"][1:], ["9 invocations, 4 rewrites, 5 skips", "7 days (from the field name)"])
        self.assertEqual(saved["Headroom headroom_24h"][2], "24 h (from the field name)")
        self.assertIn('<meter class="cc-meter" min="0" max="100" value="25"', markup)
        self.assertIn("Fixture CC note", markup)
        self.assertIn("Window: 2026-10-10T00:00:00Z to 2026-10-11T00:00:00Z", markup)
        bars = tables(markup)["Codex tokens by lane, millions, in the CC's order"]
        self.assertEqual([row[:2] for row in bars[1:]], [["lane-a", "40.0"], ["lane-b", "10.0"]])
        self.assertIn('style="inline-size: 100.0%"', markup)
        self.assertIn('style="inline-size: 25.0%"', markup)
        self.assertIn("Token-report manifest", markup)
        self.assertEqual(statuses["cc-tokens"]["status"], "partial")

    def test_private_values_never_render_from_any_panel(self):
        identity = "-".join(["dummy", "synthetic", "account"])
        current = current_fixture()
        current["headline"] = "headline " + SYNTHETIC_HOME + " " + SYNTHETIC_EMAILS[0]
        current["in_review"][0]["state"] = " ".join(SYNTHETIC_EMAILS) + " worker_" + identity + "_read"
        current["in_review"][0]["blockers"] = [SYNTHETIC_HOME + "/blocker"]
        current["waiting_on_owner"][1]["detail"] = "mail " + SYNTHETIC_EMAILS[1] + " at " + SYNTHETIC_HOME
        current["waiting_on_owner"][0]["link"] = "https://example.org/" + SYNTHETIC_EMAILS[0]
        current["cc_agents"]["running"].append(identity + " (" + SYNTHETIC_EMAILS[2] + ")")
        current["token_use_24h"]["note"] = identity + " " + SYNTHETIC_EMAILS[0]
        fleet = fleet_fixture()
        fleet["lanes_live"][0]["lane_model"] = SYNTHETIC_EMAILS[0]
        with patch.object(view._sanitization.Path, "home", return_value=Path("/synthetic") / identity):
            markup, _ = view.render(current, fleet, manifests_fixture())
        self.assertEqual(EMAIL.findall(markup), [])
        self.assertNotIn("synthetic-user", markup)
        self.assertNotIn(identity, markup)
        self.assertIn("[email omitted]", markup)
        self.assertNotIn('href="https://example.org/', markup)
        names = prohibited_names()
        if names:
            self.assertEqual(identity_hits(markup, names), 0)
            self.assertEqual(identity_hits((ROOT / "tools/local-pages/command_center_view.py").read_text(), names), 0)


class CommandCenterComposerTests(unittest.TestCase):
    """The real composer publishes, links and degrades the page."""

    write_json = staticmethod(composer_fixture.LocalPagesTests.write_json)
    refresh = composer_fixture.LocalPagesTests.refresh

    def setUp(self):
        composer_fixture.LocalPagesTests.setUp(self)

    def add_sections(self):
        fixture = current_fixture()
        for key in ("in_review", "landings_today", "cc_agents", "token_efficiency", "token_use_24h"):
            self.current[key] = copy.deepcopy(fixture[key])
        self.write_json(self.current_path, self.current)

    def write_manifests(self):
        readiness = manifests_fixture()["readiness"]["document"]
        evidence = manifests_fixture()["evidence"]["document"]
        self.write_json(self.root / "catalogs/north-star/readiness.json", readiness)
        self.write_json(self.root / "manifests/evidence.json", evidence)
        return {name: hashlib.sha256((self.root / path).read_bytes()).hexdigest() for name, path in (("readiness", "catalogs/north-star/readiness.json"), ("evidence", "manifests/evidence.json"))}

    def test_page_builds_from_fixture_and_is_linked_from_index_nav_and_sources(self):
        self.add_sections()
        digests = self.write_manifests()
        receipt = self.refresh()
        page = (self.output / "command-center.html").read_text()
        for anchor in PANELS:
            self.assertIn(f'id="{anchor}"', page)
        self.assertIn(digests["readiness"], page)
        self.assertIn(digests["evidence"], page)
        self.assertIn("3 files, 1 receipt, 0 convergence records", page)
        self.assertIn("fixture-lane", page)
        index = (self.output / "index.html").read_text()
        overview = index[index.index('<ul class="page-index">'):]
        overview = overview[:overview.index("</ul>")]
        self.assertTrue(overview.startswith('<ul class="page-index"><li><a href="command-center.html">Command center</a>'))
        for name in ("index", "readiness", "fleet", "sources", "command-center"):
            self.assertIn('<a href="command-center.html"', (self.output / (name + ".html")).read_text())
        self.assertIn('aria-current="page">Command center</a>', page)
        self.assertIn('href="sources.html#command-center"', page)
        sources = (self.output / "sources.html").read_text()
        self.assertIn('<section id="command-center" class="panel"><h2>Command center</h2>', sources)
        self.assertIn("read under the existing <code>architecture_readiness</code> grant", sources)
        self.assertIn("repo:catalogs/north-star/readiness.json", sources)
        record = receipt["command_center"]
        self.assertEqual(record["status"], "RECORDED")
        self.assertEqual(set(record["panels"]), set(PANELS))
        self.assertEqual(record["manifests"]["readiness"]["sha256"], digests["readiness"])
        self.assertNotIn("document", record["manifests"]["readiness"])
        self.assertEqual(receipt["inputs"]["command_center:readiness"]["role"], "architecture_readiness")
        self.assertEqual(receipt["inputs"]["command_center:evidence"]["role"], "architecture_registry")
        self.assertIn("module:command_center_view", receipt["inputs"])
        self.assertIn("command-center.html", receipt["outputs"])
        self.assertEqual(set(record["not_wired"]), {"token_report", "skill_usage", "research_queue", "final_stack"})

    def test_missing_sections_and_manifests_render_gaps_and_still_publish(self):
        receipt = self.refresh()
        page = (self.output / "command-center.html").read_text()
        for name in ("cc-now.json#/in_review", "cc-now.json#/token_efficiency", "cc-now.json#/cc_agents/running",
                     "readiness manifest (catalogs/north-star/readiness.json): not present in the selected checkout",
                     "evidence manifest (manifests/evidence.json): not present in the selected checkout"):
            self.assertIn("missing input: " + name, page)
        self.assertEqual(receipt["command_center"]["manifests"]["readiness"], {"status": "missing", "reason": "not present in the selected checkout"})
        self.assertNotIn("command_center:readiness", receipt["inputs"])
        self.assertIn("Review a source", page)

    def test_unapproved_manifest_is_a_gap_not_a_stop(self):
        self.write_manifests()
        policy = json.loads(self.policy_path.read_text())
        policy["architecture"]["architecture_readiness"] = []
        self.write_json(self.policy_path, policy)
        receipt = self.refresh()
        self.assertEqual(receipt["command_center"]["manifests"]["readiness"], {"status": "missing", "reason": "unreadable (SourcePolicyError)"})
        self.assertEqual(receipt["command_center"]["manifests"]["evidence"]["status"], "read")
        self.assertIn("unreadable (SourcePolicyError)", (self.output / "command-center.html").read_text())

    def test_failed_fleet_adapter_keeps_the_page_with_stated_gaps(self):
        with patch.object(BUILDER, "collect_fleet", side_effect=OSError("synthetic adapter failure")):
            receipt = self.refresh()
        page = (self.output / "command-center.html").read_text()
        self.assertIn("missing input: fleet lanes_live", page)
        self.assertIn("missing input: fleet claude_sessions", page)
        self.assertNotIn("synthetic adapter failure", page)
        self.assertEqual(receipt["command_center"]["panels"]["cc-sessions"]["status"], "missing")

    def test_view_failure_publishes_a_placeholder_and_every_other_page(self):
        original = BUILDER.load_local
        def broken(*_):
            raise ValueError("synthetic view failure")
        def load(name):
            module = original(name)
            return SimpleNamespace(render=broken, NOT_WIRED=module.NOT_WIRED, FINAL_STACK=module.FINAL_STACK) if name == "command_center_view" else module
        with patch.object(BUILDER, "load_local", side_effect=load):
            receipt = self.refresh()
        page = (self.output / "command-center.html").read_text()
        self.assertIn("Command center view unavailable (ValueError)", page)
        self.assertNotIn("synthetic view failure", page)
        self.assertEqual(receipt["command_center"]["status"], "UNREPORTED")
        for name in ("index", "readiness", "gaps", "roadmap", "fleet", "sources"):
            self.assertTrue((self.output / (name + ".html")).is_file())

    def test_composed_page_masks_private_values(self):
        self.add_sections()
        home_name = Path.home().name
        self.current["in_review"][0]["state"] = "see " + SYNTHETIC_HOME + " and " + " ".join(SYNTHETIC_EMAILS)
        self.current["waiting_on_owner"].append({"what": "Owner item for worker_" + home_name + "_read", "detail": "/".join(["", "home", home_name, "notes"])})
        self.current["cc_agents"]["running"].append("cc-" + home_name + " (" + SYNTHETIC_EMAILS[0] + ")")
        self.write_json(self.current_path, self.current)
        self.refresh()
        page = (self.output / "command-center.html").read_text()
        self.assertEqual(EMAIL.findall(page), [])
        self.assertNotIn("synthetic-user", page)
        self.assertNotRegex(page, r"/(?:home|Users)/[^/\s\"'<>$]")
        if len(home_name) >= 3:
            self.assertEqual(identity_hits(page, [home_name]), 0)
        names = prohibited_names()
        if names:
            self.assertEqual(identity_hits(page, names), 0)


if __name__ == "__main__":
    unittest.main()
