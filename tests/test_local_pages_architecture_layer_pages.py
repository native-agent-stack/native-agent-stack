"""Foundation and North-star layer pages: protocol conditions, read boundary and rendered sections.

The pages split the Architecture view by landscape catalog. They read the
committed scripts/final_stack.py output through the dedicated
architecture_final_stack role, show its --check flags through the script's own
flags(), and claim FINAL only where docs/decisions/2026-10-11-layer-resolution-protocol.md
allows it.
"""
from contextlib import redirect_stdout
from datetime import date
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


def load(name, path=None):
    spec = importlib.util.spec_from_file_location("layer_pages_" + name, path or HERE / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


MANIFEST, DIAGRAMS, POLICY, BUILDER, PAGES = (load(name) for name in ("architecture_manifest", "architecture_diagrams", "source_policy", "architecture_builder", "build_pages"))
sys.path.insert(0, str(ROOT / "scripts"))
FINAL_STACK = load("final_stack", ROOT / "scripts/final_stack.py")
sys.path.remove(str(ROOT / "scripts"))


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
        self.assertIn("Invoke: 0 of 1 winners", missing)
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

    def test_scheduled_needs_a_recorded_comparison_and_no_selection_without_one_is_not_terminal(self):
        self.assertEqual(MANIFEST.layer_state(layer(status="no-winner", winners=0, comparison="cmp-1"), []), ("SCHEDULED", []))
        state, missing = MANIFEST.layer_state(layer(status="no-winner", winners=0), [])
        self.assertEqual(state, "non-terminal")
        self.assertTrue(any("no scheduled comparison" in reason for reason in missing))

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


class CommittedBuildTests(unittest.TestCase):
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

    def test_each_page_covers_its_catalog_layers_exactly(self):
        for key, catalog in (("foundation", "foundation"), ("north-star", "us-equities")):
            expected = [row["layer_id"] for row in json.loads((ROOT / MANIFEST.CATALOGS[catalog]).read_text())["layers"]]
            self.assertEqual([row["layer_id"] for row in self.manifests[key]["layers"]], expected)
            self.assertEqual(self.result["pages"][key]["rendered_layer_count"], len(expected))
        self.assertEqual(len(self.manifests["foundation"]["layers"]), 20)
        self.assertEqual(len(self.manifests["north-star"]["layers"]), 12)

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
        self.assertEqual(len(self.manifests["north-star"]["decisions"]["rows"]), len(MANIFEST.DATA_DECISIONS))

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


class ComposerTests(unittest.TestCase):
    def test_build_pages_renders_only_the_layer_pages_on_request(self):
        with tempfile.TemporaryDirectory() as base:
            output, receipt = Path(base) / "served", Path(base) / "custody/receipt.json"
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = PAGES.main(["--layer-pages-only", "--output-dir", str(output), "--receipt", str(receipt), "--state-root", str(Path(base) / "state")])
            self.assertEqual(code, 0)
            summary = json.loads(stdout.getvalue())
            self.assertEqual({value["rendered_layer_count"] for value in summary["pages"].values()}, {20, 12})
            names = {path.name for path in output.iterdir()}
            self.assertLessEqual({"architecture-foundation.html", "architecture-north-star.html", "architecture-foundation-manifest.json", "architecture-north-star-manifest.json"}, names)
            self.assertTrue(receipt.is_file())

    def test_navigation_lists_both_pages_and_the_default_footer_label_is_unchanged(self):
        html = PAGES.document("index", "Home", "", "scope", "", "2026-10-14T00:00:00Z", "a" * 64, []).decode()
        self.assertIn('href="architecture-foundation.html"', html)
        self.assertIn('href="architecture-north-star.html"', html)
        self.assertIn("Native readiness manifest SHA-256", html)


if __name__ == "__main__":
    unittest.main()
