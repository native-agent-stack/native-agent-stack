"""Overview page: generated facts, pending sources, the cc-now queue and the read boundary.

Fixtures are synthetic records written into temporary repo and state roots; no
private record or its content is used. The committed source_policy.json grants
paths relative to a root, so the same grants bind the fixture roots.
"""
from contextlib import redirect_stdout
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "tools/local-pages"
STATE_DIR = "coordination/command-center/research-cc-role-20261008"


def load(name):
    spec = importlib.util.spec_from_file_location("overview_tests_" + name, HERE / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


DATA, PAGES = load("overview_data"), load("build_pages")
POLICY = DATA.load("source_policy")  # the module overview_data raises from, so its error class matches


def final_stack(status="reopened"):
    def layer(catalog, layer_id, title, winners, layer_status=status, survivors=0):
        return {"catalog": catalog, "layer_id": layer_id, "title": title, "status": layer_status,
                "verdict": {"status": "recorded", "wave": "20990101", "next_review": "2099-02-01", "comparison_id": None, "reopened_by": []},
                "winners": [{"component_id": component, "evidence_class": "native_proven", "verdict_pin": "1.0.0", "run": component, "pin_drift": "same"}
                            for component in winners],
                "survivors": [{"repository": f"github.com/fixture/s{index}"} for index in range(survivors)]}
    return {"checked_at": "2099-01-01",
            "layers": [layer("foundation", "alpha", "Alpha layer", ["tool-a"], survivors=2),
                       layer("foundation", "beta", "Beta layer", ["tool-b", "tool-c"]),
                       layer("us-equities", "gamma", "Gamma layer", ["tool-d"], survivors=5),
                       layer("us-equities", "planned-delta", "Planned delta", [], layer_status="unswept")],
            "runs": [{"id": "tool-a", "pin": "1.0.0", "source": "manifests/stack.json#/components/0"},
                     {"id": "tool-b", "pin": "2.0.0", "source": "manifests/stack.json#/components/1"},
                     {"id": "tool-d", "pin": "a" * 40, "source": "manifests/stack.json#/components/2"}],
            "index": {"by_component_id": {"tool-a": [{"catalog": "foundation", "layer_id": "alpha", "role": "winner"}]}},
            "summary": {"status": {"reopened": 3, "unswept": 1}}}


def matrix(invoke=None, e2e="pending"):
    def row(catalog, layer_id, components):
        return {"catalog": catalog, "layer_id": layer_id,
                "winners": [{"component_id": component, "platforms": {"linux-wsl2-x86_64": {"e2e_state": e2e}}} for component in components],
                "convergence": {"invoke": invoke, "invoke_reason": "fixture reason"}}
    return {"rows": [row("foundation", "alpha", ["tool-a"]), row("foundation", "beta", ["tool-b", "tool-c"]), row("us-equities", "gamma", ["tool-d"])]}


CC_NOW = {"schema": "cc-now/1", "updated_utc": "2099-01-01T00:00:00Z",
          "in_review": [{"pr": "#9001", "head": "abc12345", "state": "fixture review state", "next_gate": "fixture gate"}],
          "landing_queue": ["#9002 fixture landing item", "#9003 second fixture item"],
          "api_credit": {"routing": "fixture routing text", "read_utc": "2099-01-01T00:00:00Z"}}
ROWS_OLD = "| layer | state | winner | closes by | F1 receipt worker |\n|---|---|---|---|---|\n| foundation/alpha | reopened | tool-a | OLD ACTION | lane x |\n"
ROWS_NEW = "| layer | state | winner | closes by | F1 receipt worker |\n|---|---|---|---|---|\n| foundation/alpha | reopened | tool-a | fixture next action | lane y |\n| us-equities/gamma | reopened | tool-d | gamma action | lane z |\n"
WS2 = ("# Fixture convergence\n\n## Converged\n\n| # | Signal (feed we hold) | Leads or lags |\n|---|---|---|\n| 1 | fixture signal one | leads |\n| 2 | fixture signal two | lags |\n\n"
       "## Next, by readiness trigger\n1. When fixture A holds: step one.\n2. Now: step two\n   continued.\n")


class Fixture:
    def __init__(self, base: Path, *, stack=None, matrix_doc=None, cc_now=CC_NOW, ws2=True, rows=True):
        self.root, self.state = base / "repo", base / "state"
        files = {
            "catalogs/landscape/final-stack.json": stack or final_stack(),
            "catalogs/landscape/foundation.json": {"layers": [{"layer_id": "alpha", "title": "Alpha layer"}, {"layer_id": "beta", "title": "Beta layer"}]},
            "catalogs/landscape/us-equities.json": {"layers": [{"layer_id": "gamma", "title": "Gamma layer"}]},
            "catalogs/landscape/component-evidence-matrix.json": matrix_doc or matrix(),
            "manifests/evidence.json": {"receipts": [{"path": "evidence/receipts/tool-a-smoke-20990101.json", "component_ids": ["codex"]},
                                                     {"path": "evidence/receipts/tool-a-smoke-20990305.json", "component_ids": ["codex", "claude-code"]},
                                                     {"path": "evidence/receipts/other-20991231.json", "component_ids": ["other"]}]},
            "notes/runtime-profiles-20261012/receipts/qualification.json": {"status": "trial", "tool_read_utc": "2099-01-02T00:00:00Z"},
        }
        for relative, document in files.items():
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(document))
        state_files = {}
        if cc_now is not None:
            state_files["coordination/command-center/pages/cc-now.json"] = json.dumps(cc_now)
        if rows:
            state_files[f"{STATE_DIR}/finalize-all-20261014/ROWS-aaaa1111.md"] = ROWS_OLD
            state_files[f"{STATE_DIR}/finalize-all-20261014/ROWS-bbbb2222.md"] = ROWS_NEW
        if ws2:
            state_files[f"{STATE_DIR}/ranked-feeds-20261014/CONVERGENCE-WS2-20990101.md"] = WS2
        for relative, text in state_files.items():
            path = self.state / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        self.state.mkdir(parents=True, exist_ok=True)

    def build(self, base: Path):
        output, receipt = base / "served", base / "custody/overview.json"
        result = DATA.build_overview_page(self.root, self.state, output, receipt, generated="2099-01-01T00:00:00Z", commit="0" * 40)
        return result, (output / "overview.html").read_text()


class OverviewCase(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()


class GeneratedFactsTests(OverviewCase):
    def test_counts_come_from_the_fixture_final_stack(self):
        fixture = Fixture(self.base)
        data = DATA.model(fixture.root, fixture.state, commit="0" * 40)
        glance = data["architecture"]
        self.assertEqual(glance["total"], 3)
        self.assertEqual({band["catalog"]: len(band["layers"]) for band in glance["bands"]}, {"foundation": 2, "us-equities": 1})
        self.assertEqual(glance["states"]["non-terminal"], 3)
        self.assertEqual(glance["finalized"], 0)
        planned = [row["layer"] for band in glance["bands"] for row in band["planned"]]
        self.assertEqual(planned, ["us-equities/planned-delta"])
        result, html = fixture.build(self.base)
        self.assertEqual((result["layers"], result["finalized"]), (3, 0))
        self.assertIn("2 layers: 0 final, 2 not terminal", html)
        self.assertIn("1 layer: 0 final, 1 not terminal", html)

    def test_no_final_is_claimed_at_zero(self):
        _, html = Fixture(self.base).build(self.base)
        self.assertIn("No layer is final yet: none of the 3 catalog layers meets the resolution protocol.", html)
        self.assertNotIn("are final under the resolution protocol", html)
        self.assertNotIn("mf-cell-mini mf-s-built", html)
        self.assertNotIn("a filled cell is final", html)

    def test_final_appears_only_when_status_and_all_four_conditions_hold(self):
        stack = final_stack()
        stack["layers"][0]["status"] = "current"
        fixture = Fixture(self.base, stack=stack, matrix_doc=matrix(invoke={"calls": 3}, e2e="host_verified"))
        result, html = fixture.build(self.base)
        self.assertEqual(result["finalized"], 1)
        self.assertIn("1 of 3 catalog layers are final under the resolution protocol.", html)
        self.assertEqual(html.count("mf-cell-mini mf-s-built"), 3)  # one cell in each of the three figure variants

    def test_register_rows_join_run_pins_survivors_and_the_newest_rows_record(self):
        fixture = Fixture(self.base)
        data = DATA.model(fixture.root, fixture.state, commit="0" * 40)
        rows = {row["layer"]: row for group in data["repos"]["groups"] for row in group["rows"]}
        self.assertEqual(rows["foundation/alpha"]["winners"], [{"component": "tool-a", "run_pin": "1.0.0", "run_reason": None}])
        self.assertEqual(rows["foundation/alpha"]["survivors"], 2)
        self.assertEqual(rows["foundation/alpha"]["next_action"], ["fixture next action"])
        self.assertEqual(rows["us-equities/gamma"]["survivors"], 5)
        self.assertEqual(rows["foundation/beta"]["winners"][1], {"component": "tool-c", "run_pin": None, "run_reason": "unresolved"})
        self.assertFalse(rows["us-equities/planned-delta"]["in_catalog"])
        self.assertEqual(data["repos"]["rows_record"], "ROWS-bbbb2222.md")
        _, html = fixture.build(self.base)
        self.assertNotIn("OLD ACTION", html)
        self.assertIn('href="architecture-foundation.html#layer-foundation-alpha"', html)
        self.assertIn(f'<code title="{"a" * 40}">{"a" * 12}</code>', html)

    def test_workers_cite_named_sources_and_never_invent_a_receipt(self):
        fixture = Fixture(self.base)
        rows = {row["name"]: row for row in DATA.model(fixture.root, fixture.state, commit="0" * 40)["workers"]}
        self.assertEqual(rows["Codex"]["receipt"]["path"], "evidence/receipts/tool-a-smoke-20990305.json")
        self.assertEqual(rows["Codex"]["receipt"]["count"], 2)
        self.assertEqual(rows["Codex"]["state"]["text"], "no run pin recorded")
        self.assertEqual(rows["Claude API slots"]["state"]["text"], "fixture routing text")
        self.assertEqual(rows["pi and OpenCode"]["state"]["text"], "trial")
        for name in ("Meta Wonder Full", "GPT kit"):
            self.assertEqual(rows[name]["state"]["status"], "no source")
            self.assertEqual(rows[name]["receipt"]["status"], "no source")
        _, html = fixture.build(self.base)
        self.assertEqual(html.count("No receipt source yet"), 3)
        self.assertEqual(html.count("No state source yet"), 2)


class PendingTests(OverviewCase):
    def test_missing_sources_render_pending_with_their_trigger_and_the_receipt_lists_them(self):
        fixture = Fixture(self.base, ws2=False, rows=False, cc_now=None)
        result, html = fixture.build(self.base)
        source_map = json.loads((HERE / "overview_sources.json").read_text())["sources"]
        for key in ("feeds_convergence", "strategies_convergence", "claude_code_practice", "finalize_rows", "cc_now"):
            self.assertIn(key, result["pending"])
            self.assertIn(source_map[key]["trigger"], html)
        self.assertIn("final_stack", result["present"])
        self.assertEqual({row["id"]: row["status"] for row in result["sources"]}["cc_now"], "pending")
        self.assertIn("CONVERGENCE-WS5-*.md", html)
        self.assertNotIn("Traceback", html)

    def test_a_present_convergence_record_renders_its_table_and_next_steps(self):
        fixture = Fixture(self.base)
        _, html = fixture.build(self.base)
        self.assertIn("fixture signal two", html)
        self.assertIn("Signal (feed we hold)", html)
        self.assertIn("Now: step two continued.", html)
        self.assertIn("CONVERGENCE-WS2-20990101.md", html)


    def test_a_list_only_shortlist_renders_each_items_bold_lead_under_the_records_heading(self):
        fixture = Fixture(self.base)
        record = ("# Fixture shortlist\n\n## Inputs\n1. **Not this.** input\n\n## Converged by both judges\n"
                  "1. **Lead one.** long detail\n   - nested detail\n2. **Lead two:** more detail\n3. An item without a lead\n\n## Disputed\n1. **Not this either.**\n")
        path = fixture.state / f"{STATE_DIR}/extreme-mover-strategies-20261014/CONVERGENCE-WS5-20990101.md"
        path.parent.mkdir(parents=True)
        path.write_text(record)
        result, html = fixture.build(self.base)
        self.assertIn("strategies_convergence", result["present"])
        section = html[html.index('id="ov-strategies"'):html.index('id="ov-workers"')]
        self.assertIn("<h3>Converged by both judges</h3>", section)
        for text in ("<li>Lead one.</li>", "<li>Lead two</li>", "<li>An item without a lead</li>"):
            self.assertIn(text, section)
        for text in ("long detail", "nested detail", "Not this"):
            self.assertNotIn(text, section)
        self.assertEqual(DATA.md_list(record, "Converged", lead=True), ("Converged by both judges", ["Lead one.", "Lead two", "An item without a lead"]))


    def test_a_present_claude_code_record_shows_its_pin_and_both_tables(self):
        fixture = Fixture(self.base)
        record = ("# Fixture client record\n\nPinned client: 9.9.9 (fixture)\n\n## CHANGELOG delta 9.9.8 to 9.9.9\n| Version | Change |\n|---|---|\n| 9.9.9 | fixture change |\n\n"
                  "## Best-practice screen\n| Practice | Verdict |\n|---|---|\n| fixture practice | fixture verdict |\n")
        path = fixture.state / f"{STATE_DIR}/cc-native-practice-20261014/CLIENT-20990101.md"
        path.parent.mkdir(parents=True)
        path.write_text(record)
        result, html = fixture.build(self.base)
        self.assertIn("claude_code_practice", result["present"])
        section = html[html.index('id="ov-claude-code"'):html.index('id="ov-github"')]
        self.assertIn("Pinned client 9.9.9", section)
        for text in ("fixture change", "fixture verdict", "From <code>CLIENT-20990101.md</code> (private record, cited by name)."):
            self.assertIn(text, section)


class QueueTests(OverviewCase):
    def test_cc_now_queue_and_a_pending_main_ci(self):
        _, html = Fixture(self.base).build(self.base)
        for text in ("#9001", "abc12345", "fixture review state", "fixture gate", "#9002 fixture landing item", "#9003 second fixture item"):
            self.assertIn(text, html)
        self.assertIn("In review (1)", html)
        self.assertIn("From <code>cc-now.json</code> (private record, cited by name), updated 2099-01-01T00:00:00Z.", html)
        self.assertIn("Landing queue (2)", html)
        self.assertIn("the command center adds a main_ci entry to its current view", html)

    def test_a_published_main_ci_entry_replaces_the_pending_block(self):
        cc_now = copy.deepcopy(CC_NOW)
        cc_now["main_ci"] = {"conclusion": "fixture green", "head": "def67890"}
        _, html = Fixture(self.base, cc_now=cc_now).build(self.base)
        self.assertIn("fixture green", html)
        self.assertNotIn("adds a main_ci entry", html)

    def test_a_cc_now_of_another_schema_is_unreadable_not_an_error(self):
        _, html = Fixture(self.base, cc_now={"schema": "other/1"}).build(self.base)
        self.assertIn("the record is not schema cc-now/1", html)


class PrivacyTests(OverviewCase):
    def test_private_records_appear_by_name_and_their_digests_stay_in_the_receipt(self):
        fixture = Fixture(self.base)
        result, html = fixture.build(self.base)
        for row in result["sources"]:
            if row["root"] == "state" and row["status"] == "present":
                self.assertNotIn(row["sha256"], html)
                self.assertNotIn(str(fixture.state), html)
        self.assertNotRegex(html, r"/home/[A-Za-z]|/Users/[A-Za-z]")
        self.assertIn("private record, cited by name", html)


class SourceMapPolicyTests(unittest.TestCase):
    def test_every_committed_declaration_has_its_exact_grant(self):
        with tempfile.TemporaryDirectory() as state:
            document, _, _, receipt = DATA.load_source_map(ROOT, Path(state))
        self.assertEqual(receipt["path"], "tools/local-pages/overview_sources.json")
        self.assertEqual({entry["section"] for entry in document["sources"].values()}, set(DATA.SECTIONS) - {"evidence"})
        self.assertEqual(document["sources"]["final_stack"]["role"], "architecture_final_stack")

    def mutated(self, base: Path, change):
        document = json.loads((HERE / "overview_sources.json").read_text())
        change(document)
        path = base / "sources.json"
        path.write_text(json.dumps(document))
        return path

    def test_an_ungranted_path_or_glob_is_refused_before_any_read(self):
        changes = {
            "path": lambda doc: doc["sources"]["cc_now"].update(path="coordination/command-center/pages/other.json"),
            "glob": lambda doc: doc["sources"]["finalize_rows"].update(glob=f"{STATE_DIR}/finalize-all-20261014/*.md"),
            "role": lambda doc: doc["sources"]["final_stack"].update(role="overview_registry"),
            "both": lambda doc: doc["sources"]["cc_now"].update(glob="x/*.json"),
            "worker": lambda doc: doc["workers"][0].update(receipt={"source": "undeclared"}),
        }
        with tempfile.TemporaryDirectory() as base:
            for name, change in changes.items():
                with self.subTest(change=name), self.assertRaises(POLICY.SourcePolicyError):
                    DATA.load_source_map(ROOT, Path(base), source_map=self.mutated(Path(base), change))

    def test_overview_policy_refuses_final_stack_wide_families_and_symlinked_members(self):
        policy = json.loads((HERE / "source_policy.json").read_text())
        with tempfile.TemporaryDirectory() as base:
            base = Path(base)
            for name, change in (("final-stack", lambda doc: doc["overview"]["overview_registry"].append({"root": "repo", "path": "catalogs/landscape/final-stack.json"})),
                                 ("wildcard", lambda doc: doc["overview_families"]["overview_finalize_rows"].update(prefix=".*")),
                                 ("suffix", lambda doc: doc["overview_families"]["overview_finalize_rows"].update(suffix=".py")),
                                 ("role", lambda doc: doc["overview"].update(architecture_x=[]))):
                document = copy.deepcopy(policy)
                change(document)
                path = base / f"{name}.json"
                path.write_text(json.dumps(document))
                with self.subTest(change=name), self.assertRaises(POLICY.SourcePolicyError):
                    POLICY.OverviewReads(ROOT, base, policy_path=path)
            reads = POLICY.OverviewReads(ROOT, base / "state")
            directory = base / "state" / STATE_DIR / "finalize-all-20261014"
            directory.mkdir(parents=True)
            (base / "target.md").write_text("| layer |\n|---|\n")
            (directory / "ROWS-link.md").symlink_to(base / "target.md")
            (directory / "notes.md").write_text("not a family member")
            matches = reads.match("overview_finalize_rows", "state", f"{STATE_DIR}/finalize-all-20261014/ROWS-*.md")
            self.assertEqual([path.name for path in matches], ["ROWS-link.md"])
            with self.assertRaises(POLICY.SourcePolicyError):
                reads.read("overview_finalize_rows", matches[0])
            with self.assertRaises(POLICY.SourcePolicyError):
                reads.read("overview_finalize_rows", directory / "notes.md")


class MarkdownTests(unittest.TestCase):
    def test_tables_match_a_column_by_name_or_prefix_and_keep_their_heading(self):
        table = DATA.table_with_column(WS2, "Signal")
        self.assertEqual(table["header"], ["#", "Signal (feed we hold)", "Leads or lags"])
        self.assertEqual(table["heading"], "Converged")
        self.assertEqual(len(table["rows"]), 2)
        self.assertIsNone(DATA.table_with_column(WS2, "Strategy"))
        self.assertEqual(DATA.md_items(WS2, "Next"), ["When fixture A holds: step one.", "Now: step two continued."])
        self.assertEqual(DATA.plain("**bold** `code` [label](https://example.invalid)"), "bold code label")


class ComposerTests(unittest.TestCase):
    def test_overview_only_mode_renders_the_page_and_its_links_resolve_into_the_layer_pages(self):
        with tempfile.TemporaryDirectory() as base:
            output, receipt = Path(base) / "served", Path(base) / "custody/overview.json"
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = PAGES.main(["--overview-only", "--output-dir", str(output), "--receipt", str(receipt), "--state-root", str(Path(base) / "state")])
            self.assertEqual(code, 0)
            summary = json.loads(stdout.getvalue())
            self.assertIn("cc_now", summary["pending"])
            self.assertIn("final_stack", summary["present"])
            html = (output / "overview.html").read_text()
            links = re.findall(r'href="(architecture-(?:foundation|north-star)\.html)(?:#([a-z0-9-]+))?"', html)
            self.assertTrue(links)
            for page, fragment in links:
                target = (output / page).read_text()
                if fragment:
                    self.assertIn(f'id="{fragment}"', target, (page, fragment))
            self.assertEqual(json.loads(receipt.read_text())["schema"], DATA.SCHEMA)

    def test_navigation_lists_the_overview(self):
        html = PAGES.document("index", "Home", "", "scope", "", "2099-01-01T00:00:00Z", "a" * 64, []).decode()
        self.assertIn('href="overview.html"', html)
        overview = PAGES.document("overview", "Overview", "", "scope", "", "2099-01-01T00:00:00Z", "a" * 64, []).decode()
        self.assertIn('href="#overview-evidence"', overview)


if __name__ == "__main__":
    unittest.main()
