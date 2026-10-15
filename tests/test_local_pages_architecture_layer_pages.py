"""Foundation and North-star layer pages: protocol conditions, read boundary and rendered sections.

The pages split the Architecture view by landscape catalog. They read the
committed scripts/final_stack.py output through the dedicated
architecture_final_stack role, show its --check flags through the script's own
flags(), and claim FINAL only where docs/decisions/2026-10-11-layer-resolution-protocol.md
allows it.
"""
from contextlib import redirect_stdout
from datetime import date
from html import escape
import importlib.util
import io
import json
from pathlib import Path
import re
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "tools/local-pages"


def load(name, path=None):
    spec = importlib.util.spec_from_file_location("layer_pages_" + name, path or HERE / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


MANIFEST, DIAGRAMS, POLICY, BUILDER, PAGES = (load(name) for name in ("architecture_manifest", "architecture_diagrams", "source_policy", "architecture_builder", "build_pages"))
_SAVED_PATH = list(sys.path)
sys.path.insert(0, str(ROOT / "scripts"))
FINAL_STACK = load("final_stack", ROOT / "scripts/final_stack.py")
sys.path[:] = _SAVED_PATH
PREREGISTERED = {"comparison_id": "cmp-1", "preregistration_sha256": "f" * 64, "readiness_trigger": "both arms sealed", "decision_rule": "higher score wins"}


def decisions_section(html):
    start = html.index('id="lp-decisions"')
    return html[start:html.index("</section>", start)]


def layer(status="current", winners=1, comparison=None):
    return {"catalog": "foundation", "layer_id": "fixture", "status": status,
            "verdict": {"status": "recorded", "wave": "20260922", "next_review": "2026-10-22", "comparison_id": comparison, "reopened_by": []},
            "winners": [{"component_id": f"c{index}", "evidence_class": "native_proven", "verdict_pin": "1.0.0", "run": f"c{index}", "pin_drift": "same"}
                        for index in range(winners)]}


def matrix_row(e2e="host_verified", invoke=None):
    return {"winners": [{"component_id": f"c{index}", "platforms": {MANIFEST.PLATFORM: {"e2e_state": e2e}}} for index in range(3)],
            "convergence": {"invoke": invoke, "invoke_reason": "no post-fix invoke receipt yet"}}


class ConditionTests(unittest.TestCase):
    def conditions(self, record, row):
        return [MANIFEST.winner_conditions(record, winner, {"id": winner["run"], "pin": "1.0.0", "source": "manifests/stack.json#/components/0"} if winner.get("run") else None, row)
                for winner in record["winners"]]

    def test_final_needs_a_definitive_status_and_all_four_conditions(self):
        record = layer()
        conditions = self.conditions(record, matrix_row(invoke={"calls": 3}))
        self.assertEqual(MANIFEST.layer_state(record, conditions), ("FINAL", []))
        reopened = layer(status="reopened")
        state, missing = MANIFEST.layer_state(reopened, self.conditions(reopened, matrix_row(invoke={"calls": 3})))
        self.assertEqual(state, "non-terminal")
        self.assertTrue(any(reason.startswith("reopened") for reason in missing))

    def test_missing_invoke_evidence_blocks_final_and_names_the_recorded_reason(self):
        record = layer()
        conditions = self.conditions(record, matrix_row(invoke=None))
        state, missing = MANIFEST.layer_state(record, conditions)
        self.assertEqual(state, "non-terminal")
        self.assertIn("Invoke: no invoke evidence; the matrix records: no post-fix invoke receipt yet", missing)
        self.assertIn("no post-fix invoke receipt yet", conditions[0]["invoke"]["detail"])

    def test_e2e_at_the_verdict_pin_does_not_count_when_the_run_pin_differs(self):
        record = layer()
        record["winners"][0]["pin_drift"] = "differs"
        condition = self.conditions(record, matrix_row(invoke={"calls": 1}))[0]
        self.assertFalse(condition["e2e"]["met"])
        self.assertIn("differs", condition["e2e"]["detail"])
        record["winners"][0].update(run=None, run_reason="unpinned", pin_drift=None)
        condition = self.conditions(record, matrix_row(invoke={"calls": 1}))[0]
        self.assertFalse(condition["run_pin"]["met"])
        self.assertIn("unpinned", condition["run_pin"]["detail"])

    def test_scheduled_needs_the_full_preregistration_and_no_selection_without_one_is_not_terminal(self):
        scheduled = layer(status="no-winner", winners=0)
        scheduled["verdict"].update(PREREGISTERED)
        self.assertEqual(MANIFEST.layer_state(scheduled, []), ("SCHEDULED", []))
        state, missing = MANIFEST.layer_state(layer(status="no-winner", winners=0), [])
        self.assertEqual(state, "non-terminal")
        self.assertTrue(any("no scheduled comparison" in reason for reason in missing))
        # A comparison id alone is not a preregistered comparison (protocol, SCHEDULED).
        for field in ("preregistration_sha256", "readiness_trigger", "decision_rule"):
            partial = layer(status="no-winner", winners=0)
            partial["verdict"].update({key: value for key, value in PREREGISTERED.items() if key != field})
            state, missing = MANIFEST.layer_state(partial, [])
            self.assertEqual(state, "non-terminal", field)
            self.assertTrue(any(reason.startswith("comparison cmp-1 lacks its") for reason in missing), field)

    def test_invoke_counts_only_calls_above_zero_or_a_recorded_reason_it_is_not_invoked(self):
        record = layer()
        for invoke, met in (({"calls": 0}, False), (0, False), ({"calls": True}, False), ({"note": "seen"}, False), ({"calls": 2}, True), (5, True)):
            with self.subTest(invoke=invoke):
                self.assertIs(self.conditions(record, matrix_row(invoke=invoke))[0]["invoke"]["met"], met)
        self.assertIn("zero recorded calls", self.conditions(record, matrix_row(invoke={"calls": 0}))[0]["invoke"]["detail"])
        row = matrix_row(invoke=None)
        row["convergence"]["not_invoked_reason"] = "role retired with the hub move"
        excused = self.conditions(record, row)[0]["invoke"]
        self.assertTrue(excused["met"])
        self.assertIn("role retired with the hub move", excused["detail"])
        self.assertEqual(MANIFEST.layer_state(record, self.conditions(record, row)), ("FINAL", []))

    def test_retired_is_never_inferred_from_final_stack_v1(self):
        for status in ("current", "converged", "reopened", "unswept", "no-winner"):
            for winners in (0, 2):
                record = layer(status=status, winners=winners)
                state, _ = MANIFEST.layer_state(record, self.conditions(record, matrix_row()))
                self.assertNotEqual(state, "RETIRED")


class PolicyTests(unittest.TestCase):
    def test_committed_policy_grants_final_stack_only_through_its_dedicated_role(self):
        policy = json.loads((HERE / "source_policy.json").read_text())
        self.assertEqual(policy["architecture"]["architecture_final_stack"], [{"root": "repo", "path": "catalogs/landscape/final-stack.json"}])
        others = {row["path"] for role, rows in policy["architecture"].items() if role != "architecture_final_stack" for row in rows}
        self.assertNotIn("catalogs/landscape/final-stack.json", others)
        self.assertIn("catalogs/landscape/final-stack.json", {row["path"] for row in policy["architecture_supplement_exclusions"]})
        with tempfile.TemporaryDirectory() as state:
            reads = POLICY.ArchitectureReads(ROOT, Path(state), policy_path=HERE / "source_policy.json")
            raw, record = reads.read("architecture_final_stack", ROOT / "catalogs/landscape/final-stack.json", max_bytes=16 * 1024 * 1024)
            self.assertEqual(record["bytes"], len(raw))
            for role in ("architecture_supplement", "architecture_catalog", "architecture_static"):
                with self.assertRaises(POLICY.SourcePolicyError):
                    reads.read(role, ROOT / "catalogs/landscape/final-stack.json")
            with self.assertRaises(POLICY.SourcePolicyError):
                reads.read("architecture_final_stack", ROOT / "catalogs/landscape/foundation.json")

    def test_dedicated_role_refuses_any_other_path(self):
        document = json.loads((HERE / "source_policy.json").read_text())
        with tempfile.TemporaryDirectory() as base:
            for rows in ([{"root": "repo", "path": "catalogs/landscape/foundation.json"}],
                         [{"root": "repo", "path": "catalogs/landscape/final-stack.json"}, {"root": "repo", "path": "manifests/stack.json"}],
                         [{"root": "state", "path": "catalogs/landscape/final-stack.json"}]):
                with self.subTest(rows=rows):
                    document["architecture"]["architecture_final_stack"] = rows
                    path = Path(base) / "policy.json"
                    path.write_text(json.dumps(document))
                    with self.assertRaises(POLICY.SourcePolicyError):
                        POLICY.ArchitectureReads(ROOT, Path(base), policy_path=path)


class GeometryTests(unittest.TestCase):
    def test_blocked_detects_a_segment_through_a_box_but_not_beside_it(self):
        self.assertTrue(DIAGRAMS._blocked((0, 50, 200, 50), [(80, 20, 40, 60)]))
        self.assertFalse(DIAGRAMS._blocked((0, 10, 200, 10), [(80, 20, 40, 60)]))
        self.assertFalse(DIAGRAMS._blocked((0, 50, 70, 50), [(80, 20, 40, 60)]))


class BuiltPages(unittest.TestCase):
    """Builds both pages once from the committed records for the test classes below."""

    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        base = Path(cls.temporary.name)
        cls.output, cls.receipt = base / "served", base / "custody/layer-pages.json"
        cls.result = BUILDER.build_layer_pages(ROOT, cls.output, cls.receipt, state_root=base / "state", today=date(2026, 10, 14),
                                               commit="0" * 40, generated="2026-10-14T00:00:00Z")
        cls.manifests = {key: json.loads((cls.output / config["manifest"]).read_text()) for key, config in MANIFEST.LAYER_PAGES.items()}
        cls.html = {key: (cls.output / (config["page"] + ".html")).read_text() for key, config in MANIFEST.LAYER_PAGES.items()}
        cls.final_stack = json.loads((ROOT / "catalogs/landscape/final-stack.json").read_text())

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()


class CommittedBuildTests(BuiltPages):
    def test_each_page_covers_its_catalog_layers_exactly(self):
        for key, catalog in (("foundation", "foundation"), ("north-star", "us-equities")):
            expected = [row["layer_id"] for row in json.loads((ROOT / MANIFEST.CATALOGS[catalog]).read_text())["layers"]]
            self.assertEqual([row["layer_id"] for row in self.manifests[key]["layers"]], expected)
            self.assertEqual(self.result["pages"][key]["rendered_layer_count"], len(expected))
        self.assertEqual(len(self.manifests["foundation"]["layers"]), 21)
        self.assertEqual(len(self.manifests["north-star"]["layers"]), 12)
        registration = next(row for row in self.manifests["foundation"]["layers"]
                            if row["layer_id"] == "model-routes")
        self.assertEqual(registration["winners"], [])
        self.assertNotEqual(registration["state"], "FINAL")
        source = next(row for row in self.final_stack["layers"] if row["layer_id"] == "model-routes")
        self.assertEqual(source["verdict"]["status"], "pending_lanes")
        self.assertIsNone(source["verdict"]["wave"])

    def test_finalized_is_claimed_only_where_status_and_all_four_conditions_hold(self):
        statuses = {(row["catalog"], row["layer_id"]): row["status"] for row in self.final_stack["layers"]}
        for manifest in self.manifests.values():
            for row in manifest["layers"]:
                definitive = statuses[(manifest["catalog"], row["layer_id"])] in ("current", "converged")
                all_met = bool(row["winners"]) and all(row["conditions"].values())
                self.assertEqual(row["state"] == "FINAL", definitive and all_met, row["layer"])
                if row["state"] != "FINAL":
                    self.assertTrue(row["missing"], row["layer"])
            self.assertEqual(manifest["summary"]["finalized"], sum(1 for row in manifest["layers"] if row["state"] == "FINAL"))

    def test_manifest_items_carry_the_required_fields_and_repository_paths(self):
        for manifest in self.manifests.values():
            self.assertEqual(manifest["schema"], MANIFEST.LAYER_SCHEMA)
            self.assertEqual(manifest["commit"], "0" * 40)
            self.assertTrue(manifest["items"])
            for item in manifest["items"]:
                self.assertLessEqual({"layer", "component", "repository", "pin", "evidence_refs", "state", "missing_conditions"}, set(item))
                self.assertIn(item["state"], MANIFEST.STATES)
                for ref in item["evidence_refs"]:
                    self.assertFalse(ref.startswith(("/", "~")), ref)
                    self.assertTrue((ROOT / ref.split("#", 1)[0]).is_file(), ref)
            for source in manifest["sources"]:
                self.assertTrue((ROOT / source["path"]).is_file())
                self.assertRegex(source["sha256"], r"\A[0-9a-f]{64}\Z")

    def test_flags_are_final_stack_check_flags_split_by_catalog(self):
        expected = FINAL_STACK.flags(self.final_stack, date(2026, 10, 14))
        for manifest in self.manifests.values():
            self.assertEqual(manifest["flags"]["totals"]["pin_drift"], len(expected["pin_drift"]))
            self.assertEqual(manifest["flags"]["totals"]["pin_drift_unknown"], len(expected["pin_drift_unknown"]))
        for field in ("pin_drift", "pin_drift_unknown"):
            self.assertEqual(sorted(self.manifests["foundation"]["flags"][field] + self.manifests["north-star"]["flags"][field]), sorted(expected[field]))

    def test_pages_render_every_section_and_the_pending_study(self):
        for key, html in self.html.items():
            for anchor in ("lp-figure", "lp-rail-title", "lp-register", "lp-flags", "layer-sources"):
                self.assertIn(f'id="{anchor}"', html, (key, anchor))
            self.assertEqual(html.count('class="lp-layer"'), len(self.manifests[key]["layers"]))
            self.assertIn(MANIFEST.LAYER_PAGES[key]["manifest"], html)
            for ident in re.findall(r'aria-labelledby="(mf-[a-z]+-[wmn])-title \1-desc"', html):
                self.assertIn(f'id="{ident}-title"', html)
                self.assertIn(f'id="{ident}-desc"', html)
        north = self.html["north-star"]
        self.assertIn('id="lp-decisions"', north)
        self.assertIn("Pre-ranked feeds and overlap study: pending", north)
        self.assertIn("The sealed WS2 arms and the WS3 records exist.", north)

    def test_diagram_nodes_cite_present_files_and_name_known_layers(self):
        for key, spec in (("foundation", "topology"), ("north-star", "flow")):
            layers = {row["layer_id"] for row in self.manifests[key]["layers"]}
            for node in self.manifests[key][spec]["nodes"]:
                self.assertEqual(node["absent_refs"], [], node["id"])
                self.assertLessEqual(set(node["layers"]), layers, node["id"])
        for row in self.manifests["north-star"]["decisions"]["rows"]:
            self.assertEqual(row["absent_refs"], [], row["id"])

    def test_published_files_hold_no_home_paths_emails_or_digests_of_private_records(self):
        for name in list(self.html) + list(self.manifests):
            text = self.html.get(name) or json.dumps(self.manifests[name])
            self.assertNotRegex(text, r"/home/[A-Za-z]|/Users/[A-Za-z]")
            self.assertNotRegex(text, r"[^\s<>\"']+@[^\s<>\"']+\.[A-Za-z]{2,}")
        self.assertIn("cited by name", self.html["north-star"])
        # The private decision records appear by name, with no digest, line number or quoted text beside them.
        for text in (decisions_section(self.html["north-star"]), json.dumps(self.manifests["north-star"]["decisions"])):
            for name in ("CONVERGENCE-CC-20261014.md", "CONVERGENCE-CC-20261014.addendum-01.md"):
                self.assertIn(name, text)
            self.assertNotRegex(text, r"\b[0-9a-f]{12,}\b")
            self.assertNotRegex(text, r"\.md:\d|\bline \d|“")


class CritiqueRegressionTests(BuiltPages):
    """Findings of the frontend-design critique pass; each failed on the first commit of these pages."""

    def chip(self, name):
        return next(chip for node in self.manifests["foundation"]["topology"]["nodes"] for chip in node.get("chips", []) if chip["name"] == name)

    def test_topology_chips_carry_their_final_stack_index_role(self):
        omniroute = self.chip("OmniRoute")
        self.assertEqual((omniroute["role"], omniroute["winner_here"]), ("alternate", False))
        self.assertTrue(omniroute["layer"].startswith("us-equities/"))
        self.assertEqual((self.chip("Grafana")["role"], self.chip("Grafana")["winner_here"]), ("alternate", False))
        self.assertTrue(self.chip("Loki")["winner_here"])
        self.assertIsNone(self.chip("GPT Researcher")["role"])
        html = self.html["foundation"]
        self.assertNotIn("no catalog layer", html)
        self.assertIn("no foundation layer", html)
        self.assertIn("mf-art--other", html)

    def test_flow_nodes_without_a_repository_record_are_marked(self):
        nodes = {node["id"]: node for node in self.manifests["north-star"]["flow"]["nodes"]}
        self.assertEqual({key for key, node in nodes.items() if not node["recorded"]}, {"l0", "k1"})
        self.assertEqual(nodes["account-c"]["evidence_refs"], ["evidence/artifacts/trading-handbook-20261013/agent-lane-calculator-policy-spec-v1-20261013.md"])
        self.assertNotIn("no repository record at this commit", json.dumps(self.manifests["north-star"]))
        self.assertIn("mf-unrecorded", self.html["north-star"])
        self.assertIn("No repository record yet", self.html["north-star"])

    def test_captions_name_only_marks_the_figure_draws(self):
        self.assertNotIn("hollow square", self.html["north-star"])
        self.assertIn("hollow square", self.html["foundation"])

    def test_layer_wide_invoke_reason_is_stated_once_per_layer(self):
        for key, manifest in self.manifests.items():
            reason = "no post-fix invoke receipt yet"
            layers = sum(1 for row in manifest["layers"] if row["winners"] and not row["conditions"]["invoke"])
            self.assertEqual(self.html[key].count(reason), layers, key)

    def test_strip_adds_no_headings_and_conditions_are_defined_visibly(self):
        for html in self.html.values():
            strip = html[html.index('class="lp-strip"'):html.index("</section>", html.index('class="lp-strip"'))]
            self.assertNotIn("<h2", strip)
            self.assertNotIn("Hover", html)
            self.assertEqual(html.count('class="lp-key-list"'), 1)
            for condition in MANIFEST.CONDITIONS:
                self.assertIn(escape(condition[2], quote=True), html)

    def test_branch_builds_cite_the_main_commit_whose_records_match(self):
        records = {relative: (ROOT / relative).read_bytes() for relative in (MANIFEST.FINAL_STACK, MANIFEST.MATRIX)}
        commit = BUILDER._commit(ROOT, records)
        if commit is None:
            self.skipTest("not a Git checkout")
        for relative, raw in records.items():
            shown = BUILDER._git(ROOT, "show", f"{commit}:{relative}")
            self.assertEqual(shown, raw.decode("utf-8").strip())
        self.assertEqual(BUILDER._commit(ROOT, {MANIFEST.FINAL_STACK: b"changed\n"}), BUILDER._git(ROOT, "rev-parse", "HEAD"))


class ComposerTests(unittest.TestCase):
    def test_build_pages_renders_only_the_layer_pages_on_request(self):
        with tempfile.TemporaryDirectory() as base:
            output, receipt = Path(base) / "served", Path(base) / "custody/receipt.json"
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = PAGES.main(["--layer-pages-only", "--output-dir", str(output), "--receipt", str(receipt), "--state-root", str(Path(base) / "state")])
            self.assertEqual(code, 0)
            summary = json.loads(stdout.getvalue())
            self.assertEqual({value["rendered_layer_count"] for value in summary["pages"].values()}, {21, 12})
            names = {path.name for path in output.iterdir()}
            self.assertLessEqual({"architecture-foundation.html", "architecture-north-star.html", "architecture-foundation-manifest.json", "architecture-north-star-manifest.json"}, names)
            self.assertTrue(receipt.is_file())

    def test_navigation_lists_both_pages_and_the_default_footer_label_is_unchanged(self):
        html = PAGES.document("index", "Home", "", "scope", "", "2026-10-14T00:00:00Z", "a" * 64, []).decode()
        self.assertIn('href="architecture-foundation.html"', html)
        self.assertIn('href="architecture-north-star.html"', html)
        self.assertIn("Native readiness manifest SHA-256", html)


class FixRoundTests(BuiltPages):
    """Findings of the command-center micro at ee725cc1; each test failed on that commit's modules."""

    RECORD, ADDENDUM = "CONVERGENCE-CC-20261014.md", "CONVERGENCE-CC-20261014.addendum-01.md"

    def test_decisions_are_the_recorded_ones_cited_by_record_name(self):
        decisions = self.manifests["north-star"]["decisions"]
        self.assertEqual(decisions["records"], [self.RECORD, self.ADDENDUM])
        by_record = {}
        for row in decisions["rows"]:
            by_record.setdefault(row["recorded_in"], []).append(row["id"])
        # The sealed record has six decisions and addendum-01 four, in record order.
        self.assertEqual(by_record, {self.RECORD: [f"CC-{n}" for n in range(1, 7)], self.ADDENDUM: [f"A01-{n}" for n in range(1, 5)]})
        topics = {row["topic"]: row["decision"] for row in decisions["rows"]}
        self.assertIn("paid tiers", topics["tier-spend"])
        self.assertIn("rc6", topics["engine-pin"])
        self.assertIn("within 1 s is a target", topics["ranking-target"])
        section = decisions_section(self.html["north-star"])
        for row in decisions["rows"]:
            self.assertIn(escape(row["decision"], quote=True), section)
        self.assertNotIn("brief-architecture-pages", section + json.dumps(decisions))
        # Data-flow restatements without a counterpart in the record are not decisions.
        self.assertNotRegex(section + json.dumps(decisions), r"DL-\d")

    def test_lede_counts_are_generated_from_the_rendered_layers(self):
        self.assertTrue(BUILDER._lede("foundation", 7).startswith("The 7 foundation layers,"))
        self.assertTrue(BUILDER._lede("us-equities", 3).startswith("The 3 trading layers,"))
        for key, config in MANIFEST.LAYER_PAGES.items():
            lede = BUILDER._lede(config["catalog"], len(self.manifests[key]["layers"]))
            self.assertIn(f'<p class="lede">{escape(lede)}</p>', self.html[key])

    def test_final_stack_flags_leave_sys_path_as_found(self):
        added = {str(ROOT), str(ROOT / "scripts"), str(ROOT / "tools/sota-convergence"), "", "."}
        saved = list(sys.path)
        sys.path[:] = [entry for entry in saved if entry not in added]
        before = list(sys.path)
        try:
            BUILDER._final_stack_flags(self.final_stack, date(2026, 10, 14))
            after = list(sys.path)
        finally:
            sys.path[:] = saved
        self.assertEqual(after, before)

    def test_evidence_presence_is_read_at_the_cited_commit(self):
        present, absent = MANIFEST._present(ROOT, ["tools/local-pages/README.md", "catalogs/landscape/final-stack.json#/runs"],
                                            frozenset({"catalogs/landscape/final-stack.json"}))
        self.assertEqual((present, absent), (["catalogs/landscape/final-stack.json#/runs"], ["tools/local-pages/README.md"]))
        catalog, matrix = (json.loads((ROOT / path).read_text()) for path in (MANIFEST.CATALOGS["us-equities"], MANIFEST.MATRIX))
        manifest = MANIFEST.layer_manifest(ROOT, "north-star", self.final_stack, catalog, matrix, commit="1" * 40, sources=[], flags=None, tracked=frozenset())
        self.assertEqual(manifest["evidence_checked_at"], "1" * 40)
        self.assertFalse(any(node["recorded"] for node in manifest["flow"]["nodes"]))
        # The shared build cites a commit that is not in the repository, so it says it read the checkout.
        self.assertEqual(self.manifests["north-star"]["evidence_checked_at"], "checkout")
        self.assertIn("present in the checkout", self.html["north-star"])
        head = BUILDER._git(ROOT, "rev-parse", "HEAD")
        if head is None:
            self.skipTest("not a Git checkout")
        self.assertIn(MANIFEST.FINAL_STACK, BUILDER._tracked(ROOT, head))
        self.assertIsNone(BUILDER._tracked(ROOT, "0" * 40))


class ComposerFixRoundTests(unittest.TestCase):
    """Composer findings of the command-center micro at ee725cc1; each test failed on that commit's modules."""

    def failing_builder(self, error):
        """Patch only the layer-page builder; every other local module (the sanitizer too) loads as usual."""
        def build_layer_pages(*args, **kwargs):
            raise error
        stub, real = SimpleNamespace(build_layer_pages=build_layer_pages), PAGES.load_local
        return mock.patch.object(PAGES, 'load_local', side_effect=lambda name, *rest: stub if name == 'architecture_builder' else real(name, *rest))

    def test_layer_pages_only_never_overwrites_the_refresh_receipt(self):
        with tempfile.TemporaryDirectory() as base:
            state, output = Path(base) / "state", Path(base) / "served"
            refresh = state / "research/fullspeed-20261008/g5-stars-gap/local-pages/refresh-receipt.json"
            refresh.parent.mkdir(parents=True)
            refresh.write_text('{"schema": "full refresh"}\n')
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = PAGES.main(["--layer-pages-only", "--root", str(ROOT), "--output-dir", str(output), "--state-root", str(state)])
            self.assertEqual(code, 0)
            self.assertEqual(refresh.read_text(), '{"schema": "full refresh"}\n')
            written = refresh.parent / "architecture/layer-pages-receipt.json"
            self.assertEqual(json.loads(stdout.getvalue())["receipt"], str(written))
            self.assertEqual(json.loads(written.read_text())["schema"], "local-architecture-layer-pages/1")
            named = Path(base) / "elsewhere/refresh-receipt.json"
            with redirect_stdout(io.StringIO()), mock.patch("sys.stderr", io.StringIO()), self.assertRaises(SystemExit) as raised:
                PAGES.main(["--layer-pages-only", "--root", str(ROOT), "--output-dir", str(output), "--state-root", str(state), "--receipt", str(named)])
            self.assertEqual(raised.exception.code, 2)
            self.assertFalse(named.exists())

    def test_layer_pages_only_reports_overflow_and_recursion_errors(self):
        for error in (OverflowError("big"), RecursionError("deep")):
            with self.subTest(error=type(error).__name__), tempfile.TemporaryDirectory() as base:
                stderr = io.StringIO()
                with self.failing_builder(error), mock.patch("sys.stderr", stderr), \
                        self.assertRaises(SystemExit) as raised:
                    PAGES.main(["--layer-pages-only", "--output-dir", str(Path(base) / "served"), "--state-root", str(Path(base) / "state")])
                self.assertEqual(raised.exception.code, 1)
                self.assertIn(type(error).__name__, stderr.getvalue())

    def test_refresh_keeps_navigation_whole_when_the_layer_pages_fail(self):
        for error in (OverflowError("big"), RecursionError("deep"), ValueError("bad")):
            with self.subTest(error=type(error).__name__), tempfile.TemporaryDirectory() as base:
                output = Path(base) / "served"
                output.mkdir()
                (output / "architecture-north-star.html").write_text("previous page\n")
                outputs, receipt_doc = {}, {"outputs": {}}
                with self.failing_builder(error):
                    PAGES.refresh_layer_pages(ROOT, Path(base) / "state", output, Path(base) / "custody/refresh-receipt.json",
                                              "2026-10-14T00:00:00Z", "a" * 64, outputs, receipt_doc)
                status = receipt_doc["architecture_layer_pages"]
                self.assertEqual((status["status"], status["reason"]), ("UNREPORTED", f"Layer pages unavailable ({type(error).__name__})"))
                self.assertEqual(status["page_status"], {"architecture-foundation": "unreported placeholder",
                                                         "architecture-north-star": "previous page retained without a new observation"})
                self.assertEqual(set(outputs), {"architecture-foundation.html"})
                placeholder = outputs["architecture-foundation.html"].decode()
                self.assertIn("UNREPORTED", placeholder)
                self.assertIn('id="layer-sources"', placeholder)
                self.assertIn("architecture-foundation.html", receipt_doc["outputs"])


if __name__ == "__main__":
    unittest.main()
