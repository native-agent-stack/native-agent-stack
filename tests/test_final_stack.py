"""Tests for scripts/final_stack.py: the status rules, the W1b API (is_definitive, run_pin), the run-pin
precedence, the pin parser and --check. Every test builds its own temporary fixture root except the one that
checks the committed manifest."""

from __future__ import annotations

import contextlib
from datetime import date
import io
import json
import base64
import hashlib
import shutil
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from scripts import component_matrix as cm
from scripts import final_stack as fs
from scripts import host_receipts as hr
from scripts import host_name_scan

REPO_ROOT = Path(__file__).resolve().parents[1]
COMMIT_A = "1" * 40
COMMIT_B = "2" * 40


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, document) -> None:
    _write(path, json.dumps(document, indent=2) + "\n")


def _winner(component_id, *, repository=None, pin="1.0.0") -> dict:
    return {"component_id": component_id, "repository": repository or f"https://github.com/example/{component_id}",
            "pin": pin, "evidence_class": "native_proven"}


def _alternative(name) -> dict:
    return {"name": name, "repository": f"https://github.com/example/{name}", "disposition": "conditional",
            "evidence_class": "source_review"}


def _layer(layer_id, *, catalog="foundation", verdict_status="recorded", checked_at="2026-09-22", winners=(),
           alternatives=(), candidates=(), **extra) -> dict:
    return {"catalog": catalog, "layer_id": layer_id, "title": f"Title for {layer_id}",
            "verdict_status": verdict_status, "checked_at": checked_at, "lanes": {"agreement": "same_winner"},
            "winners": list(winners), "alternatives": list(alternatives), "candidates": list(candidates), **extra}


def _sweep(sweep_id, day, layers, *, status="completed", outcomes=None) -> dict:
    """A catalogs/saturation/ledger.json sweep; ``outcomes`` maps (catalog, layer_id) to proposed, survived and
    refuted repository URLs."""
    entries = []
    for catalog, layer_id in layers:
        lists = (outcomes or {}).get((catalog, layer_id), {})
        entries.append({"catalog": catalog, "layer_id": layer_id, "proposed": list(lists.get("proposed", [])),
                        "survived": [{"repo": repo} for repo in lists.get("survived", [])],
                        "refuted": [{"repo": repo} for repo in lists.get("refuted", [])]})
    return {"sweep_id": sweep_id, "date": day, "status": status,
            "manifest_ref": "catalogs/sota-convergence/manifest-" + day.replace("-", "") + ".json", "layers": entries}


def _lock(requirements: dict[str, str]) -> str:
    """A uv.lock with a virtual root package whose direct requirements are ``requirements``."""
    lines = ["version = 1", "revision = 3", 'requires-python = "==3.12.3"', "",
             "[[package]]", 'name = "fixture-runtime"', 'version = "0.1.0"', 'source = { virtual = "." }', "",
             "[package.metadata]",
             "requires-dist = [" + ", ".join(f'{{ name = "{name}", specifier = "=={version}" }}'
                                             for name, version in requirements.items()) + "]", ""]
    for name, version in requirements.items():
        lines += ["[[package]]", f'name = "{name}"', f'version = "{version}"',
                  'source = { registry = "https://pypi.org/simple" }', ""]
    return "\n".join(lines)


def _fixture(root: Path, *, foundation=(), us_equities=(), planned=(), sweeps=(), stack=(), pins_linux=(),
             pins_macos=(), lock=None, engine=None, research=None, matrix=None) -> None:
    """A repository root holding every input final_stack.py reads. Each matrix row agrees with the ledger through
    component_matrix's own rule unless ``matrix`` (layer_id -> convergence fields) overrides it."""
    landscape = root / "catalogs" / "landscape"
    rows = [*foundation, *us_equities]
    _write_json(landscape / "manifest.json", {"catalogs": {
        "foundation": "catalogs/landscape/foundation.json", "us-equities": "catalogs/landscape/us-equities.json"}})
    _write_json(landscape / "foundation.json", {"schema_version": 2, "layers": list(foundation)})
    _write_json(landscape / "us-equities.json", {"schema_version": 2, "layers": list(us_equities)})
    planned_document = {"schema_version": 1, "layers": list(planned)}
    if planned:
        review_path = "docs/decisions/2026-10-11-planned-layers-source-review.json"
        _write_json(root / review_path, {"schema_version": 1, "layers": list(planned)})
        planned_document["source_review"] = {
            "path": review_path, "sha256": hashlib.sha256((root / review_path).read_bytes()).hexdigest()}
    _write_json(landscape / "planned-layers.json", planned_document)
    _write_json(landscape / "research-state.json", {"layers": research if research is not None else [
        {"catalog": row["catalog"], "layer_id": row["layer_id"], "status": "comparison_required",
         "next_action": "Compare.", "decision_ref": "catalogs/landscape/foundation.json"} for row in rows]})
    _write_json(landscape / "skills-lifecycle.json", {"tasks": [
        {"layer_id": "skills-demo", "lifecycle_task": "demo", "requirement": "r", "overturn_when": "o"}]})
    ledger = {"schema_version": 1, "policy": {"K": 3, "min_gap_days": 7}, "sweeps": list(sweeps)}
    _write_json(root / "catalogs" / "saturation" / "ledger.json", ledger)
    for sweep in sweeps:
        _write_json(root / sweep["manifest_ref"], {"checked_at": sweep["date"]})
    _write_json(root / "catalogs" / "sota-convergence" / "layer-verdict-waves.json", {"waves": [
        {"run_id": "20260922", "path": "catalogs/sota-convergence/layer-verdicts-20260922.json", "sha256": "c" * 64}]})
    _write_json(root / "adoption" / "manifest.json", {"platform_profiles": []})
    _write_json(root / fs.SEEDS_DIR / "seeds-20260926.json", {row["layer_id"]: ["a seed"] for row in rows[:1]})
    for (platform, relative), tools in zip(fs.PIN_FILES, (pins_linux, pins_macos)):
        _write_json(root / relative, {"platform": platform, "tools": list(tools)})
    _write_json(root / fs.STACK, {"schema_version": 1, "components": list(stack)})
    _write_json(root / fs.RUNTIME_TARGET, {"engine": engine or {
        "repository": "https://github.com/example/engine", "requested_version": "1.0.0", "source_commit": COMMIT_A}})
    _write(root / fs.LOCKFILE, _lock(lock or {}))
    completed = cm.completed_sweeps(ledger)
    matrix_rows = []
    for row in rows:
        day = cm.parse_iso_date(row.get("checked_at"))
        later = [sweep for sweep in completed
                 if (row["catalog"], row["layer_id"]) in sweep["covers"] and (day is None or sweep["day"] > day)]
        state = cm.classify_layer_state(row, later)
        convergence = {"layer_state": state, "converged": 0, "in_use": 0, "components": [],
                       "reopened_by": ([{"sweep_id": sweep["sweep_id"], "date": sweep["date"]} for sweep in later]
                                       if state == "recorded_reopened" else [])}
        convergence.update((matrix or {}).get(row["layer_id"], {}))
        matrix_rows.append({"catalog": row["catalog"], "layer_id": row["layer_id"], "adjudication_ref": None,
                            "open_gaps": 0, "convergence": convergence})
    _write_json(landscape / "component-evidence-matrix.json", {"rows": matrix_rows, "summary": {
        "convergence": {"overall": {"converged": 0, "in_use": 0}}}})
    _write_json(root / "manifests" / "evidence.json", {"schema_version": 1, "receipts": [], "files": []})


def _planned(layer_id="planned-a", catalog="us-equities") -> dict:
    return {"catalog": catalog, "layer_id": layer_id, "title": "A planned layer",
            "source": {"record": "a dated plan", "approved": "2026-10-10", "section": "layers", "row": 1}}


class FixtureTestCase(unittest.TestCase):
    def root(self) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return Path(tmp.name).resolve()

    def build(self, **fixture) -> dict:
        root = self.root()
        _fixture(root, **fixture)
        return fs.build_document(root)

    @staticmethod
    def layer(document, layer_id) -> dict:
        return next(layer for layer in document["layers"] if layer["layer_id"] == layer_id)

    @staticmethod
    def run_main(root: Path, *args, native_scan=False, private_names=("fixture-private-account",)) -> tuple[int, str]:
        buffer = io.StringIO()
        with contextlib.ExitStack() as stack:
            stack.enter_context(contextlib.redirect_stdout(buffer))
            stack.enter_context(mock.patch.dict("os.environ", {host_name_scan.OVERRIDE: json.dumps(private_names)}))
            if not native_scan:
                stack.enter_context(mock.patch.object(host_name_scan, "scan_paths", return_value=[]))
            exit_code = fs.main(["--root", str(root), *args])
        return exit_code, buffer.getvalue()


class StatusTests(FixtureTestCase):
    def test_a_completed_sweep_after_the_verdict_reopens_the_layer(self):
        document = self.build(foundation=[_layer("layer-a", winners=[_winner("widget")])],
                              sweeps=[_sweep("sweep-0923", "2026-09-23", [("foundation", "layer-a")])])
        layer = self.layer(document, "layer-a")
        self.assertEqual(layer["status"], "reopened")
        self.assertEqual(layer["verdict"]["reopened_by"], [{"sweep_id": "sweep-0923", "date": "2026-09-23"}])
        self.assertEqual(layer["verdict"]["next_review"], "2026-10-22")

    def test_a_stopped_sweep_after_the_verdict_leaves_the_layer_current(self):
        # A completed sweep on the verdict's own date covers the layer without reopening it; the later stopped
        # sweep neither counts nor resets.
        document = self.build(foundation=[_layer("layer-a", winners=[_winner("widget")])], sweeps=[
            _sweep("sweep-0922", "2026-09-22", [("foundation", "layer-a")]),
            _sweep("sweep-0923-stopped", "2026-09-23", [("foundation", "layer-a")], status="stopped")])
        layer = self.layer(document, "layer-a")
        self.assertEqual(layer["status"], "current")
        self.assertEqual(layer["verdict"]["reopened_by"], [])

    def test_converged_needs_every_in_use_row_converged(self):
        layers = [_layer("all-in", winners=[_winner("widget")]), _layer("one-short", winners=[_winner("gadget")])]
        document = self.build(foundation=layers, sweeps=[
            _sweep("sweep-0922", "2026-09-22", [("foundation", "all-in"), ("foundation", "one-short")])], matrix={
            "all-in": {"converged": 2, "in_use": 2}, "one-short": {"converged": 1, "in_use": 2}})
        self.assertEqual(self.layer(document, "all-in")["status"], "converged")
        self.assertEqual(self.layer(document, "one-short")["status"], "current")

    def test_a_landscape_layer_no_completed_sweep_covers_is_unswept(self):
        document = self.build(foundation=[_layer("layer-a", winners=[_winner("widget")])], sweeps=[
            _sweep("sweep-0923-stopped", "2026-09-23", [("foundation", "layer-a")], status="stopped")])
        self.assertEqual(self.layer(document, "layer-a")["status"], "unswept")

    def test_pending_lanes_is_no_winner_without_a_next_review(self):
        document = self.build(us_equities=[_layer("execution", catalog="us-equities", verdict_status="pending_lanes")],
                              sweeps=[_sweep("sweep-0923", "2026-09-23", [("us-equities", "execution")])])
        layer = self.layer(document, "execution")
        self.assertEqual(layer["status"], "no-winner")
        self.assertIsNone(layer["verdict"]["next_review"])

    def test_reviewed_no_selection_and_empty_recorded_winners_keep_the_review_date(self):
        for status in ("no_selection", "recorded"):
            with self.subTest(verdict_status=status):
                document = self.build(foundation=[_layer("empty", verdict_status=status)],
                                      sweeps=[_sweep("covered", "2026-09-22", [("foundation", "empty")])])
                layer = self.layer(document, "empty")
                self.assertEqual((layer["status"], layer["verdict"]["next_review"]),
                                 ("no-winner", "2026-10-22"))
                self.assertEqual(layer["verdict"]["wave_doc"],
                                 {"path": "catalogs/sota-convergence/layer-verdicts-20260922.json", "sha256": "c" * 64})

    def test_a_planned_layer_is_unswept(self):
        document = self.build(foundation=[_layer("layer-a", winners=[_winner("widget")])], planned=[_planned()],
                              sweeps=[_sweep("sweep-0923", "2026-09-23", [("foundation", "layer-a")])])
        layer = self.layer(document, "planned-a")
        self.assertEqual((layer["status"], layer["verdict"], layer["winners"]), ("unswept", None, []))
        self.assertEqual(layer["source"], "catalogs/landscape/planned-layers.json#/layers/0")
        self.assertEqual(document["summary"]["status"],
                         {"unswept": 1, "no-winner": 0, "reopened": 1, "converged": 0, "current": 0})

    def test_planned_rows_require_the_reviewed_source_and_match_its_bytes(self):
        for mutation in ("missing_ref", "changed_requirement", "changed_review", "wrong_path"):
            with self.subTest(mutation=mutation):
                root = self.root()
                _fixture(root, planned=[_planned()])
                path = root / fs.PLANNED_LAYERS
                document = json.loads(path.read_bytes())
                if mutation == "missing_ref":
                    del document["source_review"]
                elif mutation == "changed_requirement":
                    document["layers"][0]["requirement"] = "A mistranscribed requirement."
                elif mutation == "changed_review":
                    review_path = root / document["source_review"]["path"]
                    review_path.write_bytes(review_path.read_bytes() + b" ")
                else:
                    document["source_review"]["path"] = "auth.json"
                _write_json(path, document)
                with self.assertRaisesRegex(fs.FinalStackError, "planned.*source review"):
                    fs.build_document(root)

    def test_committed_planned_rows_bind_a_checked_in_review_of_the_approved_plan(self):
        source = json.loads((REPO_ROOT / fs.PLANNED_LAYERS).read_bytes())
        self.assertIn("source_review", source)
        reference = source["source_review"]
        raw = (REPO_ROOT / reference["path"]).read_bytes()
        self.assertEqual(reference["sha256"], hashlib.sha256(raw).hexdigest())
        review = json.loads(raw)
        self.assertEqual(source["layers"], review["layers"])
        self.assertEqual(review["source"]["sha256"],
                         "fb4a95b19a00335c5831bce913cbf177f90d5bd2c17819013b6021d2dc585e5c")

    def test_a_completed_sweep_covering_a_planned_layer_is_no_winner(self):
        document = self.build(planned=[_planned()],
                              sweeps=[_sweep("planned-covered", "2026-09-23", [("us-equities", "planned-a")])])
        layer = self.layer(document, "planned-a")
        self.assertEqual((layer["status"], layer["winners"], layer["verdict"]), ("no-winner", [], None))

    def test_a_planned_layer_that_collides_with_a_landscape_row_fails(self):
        root = self.root()
        _fixture(root, foundation=[_layer("layer-a", winners=[_winner("widget")])],
                 planned=[_planned("layer-a", catalog="foundation")])
        with self.assertRaisesRegex(fs.FinalStackError, "planned layer foundation/layer-a collides"):
            fs.build_document(root)
        exit_code, output = self.run_main(root, "--write")
        self.assertEqual(exit_code, 1, output)
        self.assertFalse((root / fs.OUTPUT).exists())

    def test_funnel_and_survivors_follow_the_latest_completed_outcome(self):
        repo = "https://github.com/example/"
        outcomes = {("foundation", "layer-a"): {"proposed": [repo + "kept", repo + "dropped", repo + "early"],
                                                "survived": [repo + "kept", repo + "dropped"],
                                                "refuted": [repo + "early"]}}
        later = {("foundation", "layer-a"): {"proposed": [repo + "dropped"], "refuted": [repo + "dropped"]}}
        document = self.build(foundation=[_layer("layer-a", winners=[_winner("widget")])], stack=[
            {"id": "widget", "repository": repo + "widget", "version": "1.0.0"}], sweeps=[
            _sweep("sweep-0923", "2026-09-23", [("foundation", "layer-a")], outcomes=outcomes),
            _sweep("sweep-0924-stopped", "2026-09-24", [("foundation", "layer-a")], status="stopped",
                   outcomes={("foundation", "layer-a"): {"refuted": [repo + "kept"]}}),
            _sweep("sweep-0926", "2026-09-26", [("foundation", "layer-a")], outcomes=later)])
        layer = self.layer(document, "layer-a")
        self.assertEqual(layer["survivors"], [{"repository": "github.com/example/kept", "sweep_id": "sweep-0923",
                                               "date": "2026-09-23"}])
        self.assertEqual(layer["funnel"], {"found": 4, "refuted": 2, "surviving": 1, "trialled": 0, "adopted": 1})
        self.assertEqual(document["index"]["by_repository"]["github.com/example/kept"],
                         [{"catalog": "foundation", "layer_id": "layer-a", "role": "survivor"}])

    def test_shared_vote_document_is_read_once_per_build(self):
        root = self.root()
        repositories = ["https://github.com/example/first", "https://github.com/example/second"]
        returns = "catalogs/sota-convergence/returns-shared.json"
        sweep = _sweep("shared-votes", "2026-09-23", [("foundation", "layer-a")],
                       outcomes={("foundation", "layer-a"): {"proposed": repositories,
                                                             "refuted": repositories}})
        for entry in sweep["layers"][0]["refuted"]:
            entry.update(facts={"vote": "refuted", "ref": returns + "#/facts"},
                         fit={"vote": "refuted", "ref": returns + "#/fit"})
        _fixture(root, foundation=[_layer("layer-a")], sweeps=[sweep])
        _write_json(root / returns, {"facts": {"refuted": True}, "fit": {"refuted": True}})
        reads = []
        read_bytes = fs.Sources.read_bytes

        def counted_read(sources, relative):
            reads.append(relative)
            return read_bytes(sources, relative)

        with mock.patch.object(fs.Sources, "read_bytes", counted_read):
            for build_count in (1, 2):
                document = fs.build_document(root)
                self.assertEqual(reads.count(returns), build_count)
                self.assertEqual(document["sources"][returns], hashlib.sha256((root / returns).read_bytes()).hexdigest())

    def test_reproposed_chandra_with_only_a_missing_vote_reopens_a_prior_refutation(self):
        root = self.root()
        repository = "https://github.com/datalab-to/chandra"
        returns = "catalogs/sota-convergence/returns-chandra.json"
        earlier = _sweep("chandra-refuted", "2026-09-23", [("foundation", "document-retrieval")],
                         outcomes={("foundation", "document-retrieval"): {"proposed": [repository],
                                                                          "refuted": [repository]}})
        earlier["layers"][0]["refuted"][0]["lens_votes"] = [
            {"lens": 0, "vote": "not_refuted"}, {"lens": 1, "vote": "refuted"}]
        later = _sweep("chandra-reproposed", "2026-09-29", [("foundation", "document-retrieval")],
                       outcomes={("foundation", "document-retrieval"): {"proposed": [repository],
                                                                        "refuted": [repository]}})
        later["layers"][0]["refuted"][0].update(
            facts={"vote": "not_refuted", "ref": returns + "#/facts"},
            fit={"vote": "refuted", "ref": returns + "#/fit"})
        _fixture(root, foundation=[_layer("document-retrieval")], sweeps=[earlier, later])
        _write_json(root / returns, {
            "facts": {"refuted": False},
            "fit": {"refuted": True, "claude": {"refuted": False}, "gpt6": {"missing": True}}})

        layer = self.layer(fs.build_document(root), "document-retrieval")
        self.assertEqual(layer["survivors"], [
            {"repository": "github.com/datalab-to/chandra", "sweep_id": "chandra-reproposed",
             "date": "2026-09-29"}])
        self.assertEqual((layer["funnel"]["refuted"], layer["funnel"]["surviving"]), (0, 1))

    def test_missing_vote_only_candidate_survives_omission_until_a_returned_refutation(self):
        root = self.root()
        repository = "https://github.com/exa-labs/exa-mcp-server"
        returns = "catalogs/sota-convergence/returns-20260923.json"
        missing = _sweep("missing-fit", "2026-09-23", [("foundation", "layer-a")],
                         outcomes={("foundation", "layer-a"): {"proposed": [repository],
                                                               "refuted": [repository]}})
        missing["layers"][0]["refuted"][0].update(
            facts={"vote": "not_refuted", "ref": returns + "#/facts"},
            fit={"vote": "refuted", "ref": returns + "#/fit"})
        sweeps = [missing, _sweep("later-omission", "2026-09-26", [("foundation", "layer-a")])]
        _fixture(root, foundation=[_layer("layer-a")], sweeps=sweeps)
        _write_json(root / returns, {
            "facts": {"refuted": False},
            "fit": {"refuted": True, "claude": {"refuted": False}, "gpt6": {"missing": True}},
            "merit": {"refuted": True}})

        document = fs.build_document(root)
        self.assertEqual(self.layer(document, "layer-a")["survivors"], [
            {"repository": "github.com/exa-labs/exa-mcp-server", "sweep_id": "missing-fit",
             "date": "2026-09-23"}])
        self.assertEqual(self.layer(document, "layer-a")["funnel"]["surviving"], 1)
        self.assertEqual(document["index"]["by_repository"]["github.com/exa-labs/exa-mcp-server"], [
            {"catalog": "foundation", "layer_id": "layer-a", "role": "survivor"}])

        refuted = _sweep("returned-refutation", "2026-09-29", [("foundation", "layer-a")],
                         outcomes={("foundation", "layer-a"): {"proposed": [repository],
                                                               "refuted": [repository]}})
        refuted["layers"][0]["refuted"][0].update(
            facts={"vote": "refuted", "ref": returns + "#/merit"},
            fit={"vote": "not_refuted", "ref": returns + "#/facts"})
        _fixture(root, foundation=[_layer("layer-a")], sweeps=[*sweeps, refuted])
        self.assertEqual(self.layer(fs.build_document(root), "layer-a")["survivors"], [])

        missing_again = dict(missing, sweep_id="missing-fit-again", date="2026-09-30",
                             layers=[dict(missing["layers"][0], proposed=[])])
        _fixture(root, foundation=[_layer("layer-a")], sweeps=[*sweeps, refuted, missing_again])
        self.assertEqual(self.layer(fs.build_document(root), "layer-a")["survivors"], [])

    def test_trialled_funnel_deduplicates_positive_measured_evidence_across_roles(self):
        repository = "https://github.com/example/widget"
        document = self.build(foundation=[_layer("layer-a",
            winners=[dict(_winner("widget"), evidence_class="measured_comparison")],
            alternatives=[{"repository": repository + "/", "evidence_kind": "measured_comparison"}],
            candidates=[{"repository": repository, "disposition": "measured_tradeoff"}])],
            stack=[{"id": "widget", "repository": repository, "version": "1.0.0"}])
        self.assertEqual(self.layer(document, "layer-a")["funnel"],
                         {"found": 1, "refuted": 0, "surviving": 0, "trialled": 1, "adopted": 1})

    def test_skills_coverage_records_the_completed_lifecycle_sweep(self):
        document = self.build(sweeps=[_sweep("skills-covered", "2026-09-22", [(fs.SKILLS, "skills-demo")])])
        coverage = document["coverage"]["skills"]
        self.assertEqual([(row["layer_id"], row["lifecycle_task"], row["swept"]) for row in coverage],
                         [("skills-demo", "demo", True)])


class DefinitiveTests(FixtureTestCase):
    def setUp(self):
        self.document = self.build(
            foundation=[_layer("current-layer", winners=[_winner("widget")], alternatives=[_alternative("gizmo")]),
                        _layer("reopened-layer", winners=[_winner("relay")])],
            sweeps=[_sweep("sweep-0922", "2026-09-22", [("foundation", "current-layer")]),
                    _sweep("sweep-0923", "2026-09-23", [("foundation", "reopened-layer")])])

    def test_true_for_a_current_winner_within_next_review(self):
        answer = fs.is_definitive(self.document, "widget", date(2026, 10, 22))
        self.assertIs(bool(answer), True)
        self.assertEqual((answer.reason, answer.layers), (None, ("foundation/current-layer",)))
        self.assertTrue(fs.is_definitive(self.document, "https://github.com/example/widget", "2026-09-30"))

    def test_false_when_stale(self):
        answer = fs.is_definitive(self.document, "widget", date(2026, 10, 23))
        self.assertIs(bool(answer), False)
        self.assertEqual(answer.reason, "stale")

    def test_false_when_reopened(self):
        answer = fs.is_definitive(self.document, "relay", date(2026, 9, 30))
        self.assertEqual((bool(answer), answer.reason, answer.layers), (False, "reopened", ("foundation/reopened-layer",)))

    def test_false_for_an_alternate_and_for_an_untracked_component(self):
        alternate = fs.is_definitive(self.document, "https://github.com/example/gizmo", date(2026, 9, 30))
        self.assertEqual((bool(alternate), alternate.reason), (False, "not-winner"))
        untracked = fs.is_definitive(self.document, "https://github.com/example/unknown", date(2026, 9, 30))
        self.assertEqual((bool(untracked), untracked.reason), (False, "untracked"))

    def test_the_layer_argument_narrows_the_question(self):
        answer = fs.is_definitive(self.document, "widget", date(2026, 9, 30), layer="foundation/reopened-layer")
        self.assertEqual((bool(answer), answer.reason, answer.layers),
                         (False, "not-winner", ("foundation/current-layer",)))
        missing = fs.is_definitive(self.document, "missing", date(2026, 9, 30), layer="foundation/reopened-layer")
        self.assertEqual((missing.reason, missing.layers), ("untracked", ()))


class PinTests(unittest.TestCase):
    def test_package_names_follow_pep_503_normalization(self):
        self.assertEqual(fs.canonical_package("Widget_Lib.Name--CLI"), "widget-lib-name-cli")

    def test_parse_pin_accepts_only_the_declared_forms(self):
        cases = {
            "2.1.278": {"pin_parsed": {"version": "2.1.278", "commit": None}},
            "v0.44.0": {"pin_parsed": {"version": "0.44.0", "commit": None}},
            "2.0.0rc5": {"pin_parsed": {"version": "2.0.0rc5", "commit": None}},
            "255.4-1ubuntu8.17": {"pin_parsed": {"version": "255.4-1ubuntu8.17", "commit": None}},
            COMMIT_A: {"pin_parsed": {"version": None, "commit": COMMIT_A}},
            "2.0.0.dev0 @ " + COMMIT_A: {"pin_parsed": {"version": "2.0.0.dev0", "commit": COMMIT_A}},
            "v0.44.0; source " + COMMIT_A: {"pin_parsed": {"version": "0.44.0", "commit": COMMIT_A}},
            "unpinned": {"pin_parse": "unpinned"},
            "1.2.9; WalkForward source " + COMMIT_A: {"pin_parse": "unparsed"},
            "CLI rust-v0.155.1; Python openai-codex 0.154.0": {"pin_parse": "unparsed"},
            "inspect-ai0.3.266; source " + COMMIT_A: {"pin_parse": "unparsed"},
            "985ef30": {"pin_parse": "unparsed"},
            "b11057": {"pin_parse": "unparsed"},
            "1.2.3" + "a" * 60 + "!": {"pin_parse": "unparsed"},
            None: {"pin_parse": "unparsed"},
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(fs.parse_pin(text), expected)

    def test_a_separate_commit_merges_unless_it_contradicts_the_text(self):
        self.assertEqual(fs.record_pin("985ef30 with remediation", COMMIT_A),
                         {"pin_parsed": {"version": None, "commit": COMMIT_A}})
        self.assertEqual(fs.record_pin("1.0.0", COMMIT_A), {"pin_parsed": {"version": "1.0.0", "commit": COMMIT_A}})
        self.assertEqual(fs.record_pin("1.0.0 @ " + COMMIT_A, COMMIT_B), {"pin_parse": "unparsed"})
        self.assertEqual(fs.record_pin("1.0.0", "v1.0.0"), {
            "pin_parsed": {"version": "1.0.0", "commit": None},
            "source_pin": "v1.0.0", "source_pin_kind": "tag"})

    def test_compare_pins_is_three_valued(self):
        parsed = fs.parse_pin
        self.assertEqual(fs.compare_pins(parsed("v0.44.0; source " + COMMIT_A), parsed("0.44.0")), "same")
        self.assertEqual(fs.compare_pins(parsed("0.44.0"), parsed("0.45.0")), "differs")
        self.assertEqual(fs.compare_pins(parsed("0.44.0 @ " + COMMIT_A), parsed("0.44.0 @ " + COMMIT_B)), "differs")
        self.assertEqual(fs.compare_pins(parsed(COMMIT_A), parsed("0.44.0")), "unknown")
        self.assertEqual(fs.compare_pins(parsed("unpinned"), parsed("0.44.0")), "unknown")

    def test_identical_commit_pins_compare_equal_through_native_normalization(self):
        parsed = fs.parse_pin(COMMIT_A)
        self.assertEqual(hr.normalize_pin(COMMIT_A), COMMIT_A)
        self.assertEqual(fs.compare_pins(parsed, parsed), "same")


class RunTests(FixtureTestCase):
    def test_equal_version_only_lock_keeps_conflicting_lower_commit_sources_visible(self):
        for lower_commit, expected in ((COMMIT_A, []), (COMMIT_B, [
                {"source": "manifests/stack.json#/components/0", "pin": "1.0.0"},
                {"source": fs.RUNTIME_TARGET + "#" + fs.RUNTIME_ENGINE_POINTER, "pin": "1.0.0"}])):
            with self.subTest(lower_commit=lower_commit):
                document = self.build(lock={"widget": "1.0.0"},
                    stack=[{"id": "widget", "repository": "https://github.com/example/widget",
                            "version": "1.0.0", "source_pin": COMMIT_A}],
                    engine={"repository": "https://github.com/example/widget", "requested_version": "1.0.0",
                            "source_commit": lower_commit})
                run = fs.run_pin(document, "widget")
                self.assertEqual(run["pin_parsed"], {"version": "1.0.0", "commit": None})
                self.assertEqual(run["conflicts"], expected)

    def test_unreported_intake_names_future_paths_without_reading_them(self):
        document = self.build(foundation=[_layer("seeded")])
        self.assertEqual(document["intake"]["seeds"], {
            "path": "tools/sota-convergence/landscape-sweep/seeds-20260926.json", "date": "2026-09-26",
            "total": 1, "by_layer": {"foundation/seeded": 1}, "unmatched": []})
        for name, source in (("stars", fs.STARS_FILE), ("grand", fs.GRAND_COUNTS_FILE)):
            with self.subTest(intake=name):
                entry = document["intake"][name]
                self.assertEqual((entry["status"], entry["source"]), ("UNREPORTED", source))
                self.assertIn("future integration path", entry["reason"])
                self.assertNotIn(source, document["sources"])

    def test_a_subpath_editable_or_virtual_package_is_not_the_lock_root(self):
        for kind in ("editable", "virtual"):
            with self.subTest(source_kind=kind):
                root = self.root()
                _fixture(root)
                _write(root / fs.LOCKFILE, _lock({}).replace('virtual = "."', kind + ' = "packages/child"'))
                with self.assertRaisesRegex(fs.FinalStackError, "expected one root package, found 0"):
                    fs.build_document(root)

    def test_the_lock_root_accepts_dot_and_ignores_an_editable_child(self):
        for kind in ("editable", "virtual"):
            with self.subTest(source_kind=kind):
                root = self.root()
                _fixture(root, lock={"helper": "0.1.0"})
                text = _lock({"helper": "0.1.0"}).replace('virtual = "."', kind + ' = "."')
                text += '\n[[package]]\nname = "child"\nversion = "0.1.0"\nsource = { editable = "packages/child" }\n'
                _write(root / fs.LOCKFILE, text)
                document = fs.build_document(root)
                self.assertEqual(fs.run_pin(document, "helper")["pin"], "0.1.0")
                self.assertIsNone(fs.run_pin(document, "child"))

    def test_run_precedence_uses_rank_even_when_records_arrive_out_of_order(self):
        root = self.root()
        _fixture(root, stack=[{"id": "widget", "repository": "https://github.com/example/widget", "version": "1.0.0"}],
                 lock={"widget": "2.0.0"})
        records = fs.run_records(fs.Sources(root))
        run = next(run for run in fs.build_runs(list(reversed(records))) if run["id"] == "widget")
        self.assertEqual((run["pin"], run["source"]), ("2.0.0", fs.LOCKFILE + "#/package/1"))
        self.assertEqual(run["conflicts"], [{"source": fs.STACK + "#/components/0", "pin": "1.0.0"}])

    def test_a_lockfile_pin_beats_the_stack_and_the_conflict_is_listed(self):
        document = self.build(
            us_equities=[_layer("engines", catalog="us-equities", winners=[_winner("data-widget", repository=(
                "https://github.com/example/widget"), pin="v1.0.0; source " + COMMIT_A)])],
            stack=[{"id": "widget", "repository": "https://github.com/example/widget", "version": "1.0.0",
                    "source_pin": COMMIT_A}],
            lock={"widget": "2.0.0", "helper": "0.1.0"})
        run = fs.run_pin(document, "widget")
        self.assertEqual((run["pin"], run["source"]), ("2.0.0", fs.LOCKFILE + "#/package/1"))
        self.assertEqual(run["conflicts"], [{"source": "manifests/stack.json#/components/0", "pin": "1.0.0"}])
        winner = self.layer(document, "engines")["winners"][0]
        self.assertEqual((winner["run"], winner["run_reason"], winner["pin_drift"]), ("widget", None, "differs"))
        self.assertIs(fs.run_pin(document, "data-widget"), run)
        self.assertIs(fs.run_pin(document, "https://github.com/example/widget/"), run)
        # A requirement with no stack id or declared repository is still a run, keyed by its name.
        self.assertEqual(fs.run_pin(document, "helper")["repository"], None)
        self.assertIsNone(fs.run_pin(document, "nothing-runs-this"))

    def test_same_lock_and_verdict_version_has_no_drift(self):
        document = self.build(foundation=[_layer("layer-a", winners=[_winner("widget", pin="1.0.0")])],
                              stack=[{"id": "widget", "repository": "https://github.com/example/widget", "version": "1.0.0"}],
                              lock={"widget": "1.0.0"})
        winner = self.layer(document, "layer-a")["winners"][0]
        self.assertEqual((winner["run"], winner["pin_drift"]), ("widget", "same"))
        self.assertEqual(fs.run_pin(document, "widget")["source"], fs.LOCKFILE + "#/package/1")

    def test_a_repositoryless_winner_joins_a_repositoryless_run_by_component_id(self):
        winner = {"component_id": "helper", "repository": None, "pin": "0.1.0"}
        document = self.build(foundation=[_layer("layer-a", winners=[winner])], lock={"helper": "0.1.0"})
        joined = self.layer(document, "layer-a")["winners"][0]
        self.assertEqual((joined["run"], joined["pin_drift"]), ("helper", "same"))

    def test_the_linux_pin_file_leads_and_a_differing_macos_pin_is_a_conflict(self):
        document = self.build(
            foundation=[_layer("clients", winners=[_winner("client", pin="1.1.0")])],
            stack=[{"id": "client", "repository": "https://github.com/example/client", "version": "1.1.0"}],
            pins_linux=[{"id": "client", "version": "1.1.0", "url": "https://registry.example/client-1.1.0.tgz"}],
            pins_macos=[{"id": "client", "version": "1.0.0", "url": "https://registry.example/client-1.0.0.tgz"}])
        run = fs.run_pin(document, "client")
        self.assertEqual((run["pin"], run["platforms"]), ("1.1.0", ["linux-x86_64"]))
        self.assertEqual(run["conflicts"], [{"source": "adoption/pins-macos-arm64.json#/tools/0", "pin": "1.0.0"}])
        self.assertEqual(self.layer(document, "clients")["winners"][0]["pin_drift"], "same")

    def test_a_github_release_url_joins_a_pin_file_tool_to_its_repository(self):
        document = self.build(
            foundation=[_layer("cli", winners=[_winner("candidate:cli", repository="https://github.com/example/cli",
                                                      pin="unpinned")])],
            pins_linux=[{"id": "x", "version": "2.0.0",
                         "url": "https://github.com/example/cli/releases/download/v2.0.0/x.tar.gz"}])
        winner = self.layer(document, "cli")["winners"][0]
        self.assertEqual((winner["run"], winner["pin_parse"], winner["pin_drift"]), ("x", "unpinned", "unknown"))

    def test_unpinned_and_unparsed_pins_are_flagged_and_never_guessed(self):
        document = self.build(foundation=[_layer("layer-a", winners=[
            _winner("candidate:loose", pin="unpinned"),
            _winner("sdk", pin="CLI rust-v0.155.1; Python openai-codex 0.154.0")])],
            stack=[{"id": "sdk", "repository": "https://github.com/example/sdk", "version": "0.154.0"}])
        loose, sdk = self.layer(document, "layer-a")["winners"]
        self.assertEqual((loose["pin_parse"], loose["run"], loose["run_reason"]), ("unpinned", None, "unpinned"))
        self.assertNotIn("pin_parsed", sdk)
        self.assertEqual((sdk["pin_parse"], sdk["run"], sdk["pin_drift"]), ("unparsed", "sdk", "unknown"))
        self.assertEqual(document["summary"]["pin_parse"], {"parsed": 0, "unpinned": 1, "unparsed": 1})

    def test_unknown_drift_report_names_the_layer_component_and_both_pins(self):
        root = self.root()
        verdict = "1.2.9; WalkForward source " + COMMIT_A
        _fixture(root, foundation=[_layer("layer-a", winners=[_winner("widget", pin=verdict)])],
                 stack=[{"id": "widget", "repository": "https://github.com/example/widget", "version": "1.7.0"}])
        self.assertEqual(self.run_main(root, "--write")[0], 0)
        exit_code, output = self.run_main(root, "--check")
        self.assertEqual(exit_code, 0, output)
        self.assertIn("1 winner(s) whose pin drift is unknown", output)
        self.assertIn("foundation/layer-a widget: verdict " + verdict + ", run 1.7.0", output)

    def test_held_external_and_unresolved_reasons(self):
        fixture = dict(foundation=[_layer("layer-a", winners=[_winner("orphan")])], us_equities=[
            _layer("held-layer", catalog="us-equities", winners=[_winner("parked")],
                   current_adoption_status="held_not_in_selected_runtime")])
        document = self.build(**fixture)
        self.assertEqual(self.layer(document, "held-layer")["winners"][0]["run_reason"], "held")
        self.assertEqual(self.layer(document, "layer-a")["winners"][0]["run_reason"], "unresolved")
        with mock.patch.dict(fs.EXTERNAL_RUN_PINS, {"orphan": "a dated trading-repository record"}):
            document = self.build(**fixture)
        self.assertEqual(self.layer(document, "layer-a")["winners"][0]["run_reason"], "external")

    def test_only_the_engine_repository_version_and_commit_are_copied(self):
        document = self.build(engine={
            "repository": "https://github.com/example/engine", "requested_version": "3.0.0rc1",
            "source_commit": COMMIT_B, "install_command": "uv pip install --python \"$ENGINE_ENV/bin/python\" engine",
            "host": "fixture-host-name"})
        run = fs.run_pin(document, "https://github.com/example/engine")
        self.assertEqual((run["id"], run["pin"], run["pin_parsed"]),
                         ("engine", "3.0.0rc1", {"version": "3.0.0rc1", "commit": COMMIT_B}))
        text = fs.serialize(document)
        self.assertNotIn("ENGINE_ENV", text)
        self.assertNotIn("fixture-host-name", text)


class CheckTests(FixtureTestCase):
    def fixture_root(self) -> Path:
        root = self.root()
        _fixture(root, foundation=[_layer("layer-a", winners=[_winner("widget")])],
                 stack=[{"id": "widget", "repository": "https://github.com/example/widget", "version": "1.0.0"}],
                 sweeps=[_sweep("sweep-0923", "2026-09-23", [("foundation", "layer-a")])])
        return root

    def test_check_fails_before_write_and_passes_after_it(self):
        root = self.fixture_root()
        exit_code, output = self.run_main(root, "--check")
        self.assertEqual(exit_code, 1, output)
        self.assertIn("final-stack.json is missing", output)
        self.assertEqual(self.run_main(root, "--write")[0], 0)
        exit_code, output = self.run_main(root, "--check")
        self.assertEqual(exit_code, 0, output)
        registered = json.loads((root / "manifests" / "evidence.json").read_text(encoding="utf-8"))["files"]
        self.assertEqual([record["path"] for record in registered], [fs.OUTPUT])

    def test_byte_drift_fails_the_check(self):
        root = self.fixture_root()
        self.run_main(root, "--write")
        path = root / fs.OUTPUT
        path.write_text(path.read_text(encoding="utf-8").replace('"reopened"', '"current"'), encoding="utf-8")
        exit_code, output = self.run_main(root, "--check")
        self.assertEqual(exit_code, 1, output)
        self.assertIn("differs from the generated output", output)

    def test_a_changed_source_hash_is_named(self):
        root = self.fixture_root()
        self.run_main(root, "--write")
        _write_json(root / fs.STACK, {"schema_version": 1, "components": [
            {"id": "widget", "repository": "https://github.com/example/widget", "version": "1.0.1"}]})
        exit_code, output = self.run_main(root, "--check")
        self.assertEqual(exit_code, 1, output)
        self.assertIn("sources: manifests/stack.json sha256 changed", output)

    def test_a_layer_without_exactly_one_row_fails(self):
        layers = [_layer("layer-a", winners=[_winner("widget")]), _layer("layer-b")]
        cases = {
            "research-state.json has 2 rows for foundation/layer-a": dict(research=[
                {"catalog": "foundation", "layer_id": layer_id, "status": "comparison_required"}
                for layer_id in ("layer-a", "layer-a", "layer-b")]),
            "research-state.json has 0 rows for foundation/layer-b": dict(research=[
                {"catalog": "foundation", "layer_id": "layer-a", "status": "comparison_required"}]),
            "has no landscape row": dict(research=[
                {"catalog": "foundation", "layer_id": layer_id, "status": "comparison_required"}
                for layer_id in ("layer-a", "layer-b", "layer-gone")]),
            "foundation/layer-a has more than one landscape row": dict(foundation=[*layers, layers[0]]),
        }
        for message, override in cases.items():
            with self.subTest(message=message):
                root = self.root()
                _fixture(root, **{"foundation": layers, **override})
                with self.assertRaisesRegex(fs.FinalStackError, message):
                    fs.build_document(root)
        root = self.root()
        _fixture(root, foundation=layers)
        matrix = json.loads((root / fs.MATRIX).read_text(encoding="utf-8"))
        matrix["rows"] = matrix["rows"][:1]
        _write_json(root / fs.MATRIX, matrix)
        exit_code, output = self.run_main(root, "--check")
        self.assertEqual(exit_code, 1, output)
        self.assertIn("component-evidence-matrix.json has 0 rows for foundation/layer-b", output)

    def test_a_matrix_that_disagrees_with_the_ledger_fails(self):
        root = self.root()
        _fixture(root, foundation=[_layer("layer-a", winners=[_winner("widget")])],
                 sweeps=[_sweep("sweep-0923", "2026-09-23", [("foundation", "layer-a")])],
                 matrix={"layer-a": {"layer_state": "confirmed_current", "reopened_by": []}})
        with self.assertRaisesRegex(fs.FinalStackError, "component_matrix.py --write"):
            fs.build_document(root)

    def test_private_content_fails(self):
        root = self.root()
        layer = _layer("layer-a", winners=[_winner("widget")])
        layer["title"] = "Notes in " + "/" + "home" + "/" + "alice" + "/notes"
        _fixture(root, foundation=[layer])
        with self.assertRaises(SystemExit) as raised:
            self.run_main(root, "--write")
        self.assertIn("personal home path", str(raised.exception))
        self.assertFalse((root / fs.OUTPUT).exists())

    def _assert_private_text_is_refused_before_publication(self, payload, private_name="fixture-private-account",
                                                         spy_publication=True, expected_message=None):
        root = self.fixture_root()
        self.assertEqual(self.run_main(root, "--write")[0], 0)
        output_before = (root / fs.OUTPUT).read_bytes()
        registry_before = (root / "manifests/evidence.json").read_bytes()
        catalog = root / "catalogs/landscape/foundation.json"
        source = json.loads(catalog.read_text(encoding="utf-8"))
        source["layers"][0]["title"] = "Private note: " + payload
        _write_json(catalog, source)
        # Existing controls spy on publication I/O. Crossing regressions run
        # the complete native writer on disposable, synthetic-only fixtures.
        with contextlib.ExitStack() as stack:
            if spy_publication:
                write = stack.enter_context(mock.patch.object(Path, "write_text"))
                register = stack.enter_context(mock.patch.object(hr, "register_file"))
            with self.assertRaises(SystemExit) as refused:
                self.run_main(root, "--write", native_scan=True, private_names=(private_name,))
            if spy_publication:
                write.assert_not_called()
                register.assert_not_called()
        self.assertNotIn(payload, str(refused.exception))
        if expected_message:
            self.assertIn(expected_message, str(refused.exception))
        self.assertEqual((root / fs.OUTPUT).read_bytes(), output_before)
        self.assertEqual((root / "manifests/evidence.json").read_bytes(), registry_before)

    def test_private_email_is_refused_before_write_or_registration(self):
        self._assert_private_text_is_refused_before_publication("fixture-private@example.invalid")

    @unittest.skipUnless(shutil.which("betterleaks"), "native encoded email plants require Betterleaks 1.9.0")
    def test_native_scanner_refuses_encoded_email_without_an_account_name_match(self):
        email = "unlisted-contact@example.invalid"
        plants = {
            "percent_at": email.replace("@", "%40"),
            "percent_all": "".join("%" + format(byte, "02X") for byte in email.encode()),
            "unicode": "".join(r"\u" + format(ord(char), "04x") for char in email),
            "base64": base64.b64encode(email.encode()).decode(),
        }
        for form, payload in plants.items():
            with self.subTest(form=form):
                self._assert_private_text_is_refused_before_publication(payload)

    @unittest.skipUnless(shutil.which("betterleaks"), "native boundary plants require Betterleaks 1.9.0")
    def test_long_encoded_email_crossing_the_old_frame_is_refused(self):
        email = "a" * 64 + "@" + "b" * 63 + ".example.invalid"
        plants = ["".join("%" + format(byte, "02X") for byte in email.encode()),
                  "".join(r"\u" + format(ord(char), "04x") for char in email),
                  base64.b64encode(email.encode()).decode()]
        for encoded in plants:
            with self.subTest(encoded_bytes=len(encoded)):
                self._assert_private_text_is_refused_before_publication(" " * 3900 + encoded,
                                                                        spy_publication=False)

    @unittest.skipUnless(shutil.which("betterleaks"), "native boundary plants require Betterleaks 1.9.0")
    def test_nested_encoded_account_crossing_the_old_frame_is_refused(self):
        encoded = "fixture-private-account"
        for _ in range(2):
            encoded = "".join("%" + format(byte, "02X") for byte in encoded.encode())
        self._assert_private_text_is_refused_before_publication(" " * 3900 + encoded, spy_publication=False)

    @unittest.skipUnless(shutil.which("betterleaks"), "native fragment plants require Betterleaks 1.9.0")
    def test_native_fragment_crossing_plants_are_refused_before_publication(self):
        name = "fixture-private-account"
        email = "a" * 64 + "@" + "b" * 63 + ".example.invalid"
        encode = lambda value: "".join("%" + format(byte, "02X") for byte in value.encode())
        for payload in (name, encode(email), encode(encode(name))):
            with self.subTest(encoded_bytes=len(payload)):
                root = self.root()
                layers = [_layer(f"cut-{index:02}", winners=[_winner("widget")]) for index in range(20)]
                for layer in layers:
                    layer["title"] = "clean"
                layers[-1]["title"] = "CUT_PLANT_MARKER"
                _fixture(root, foundation=layers)
                offset = fs.serialize(fs.build_document(root)).index("CUT_PLANT_MARKER")
                padding = 90536 - len(payload) // 2 - offset
                self.assertGreaterEqual(padding, 0)
                quotient, remainder = divmod(padding, len(layers) - 1)
                for index, layer in enumerate(layers[:-1]):
                    layer["title"] += " " * (quotient + (index < remainder))
                _write_json(root / "catalogs/landscape/foundation.json",
                            {"schema_version": 2, "layers": layers})
                self.assertEqual(self.run_main(root, "--write")[0], 0)
                before = ((root / fs.OUTPUT).read_bytes(), (root / "manifests/evidence.json").read_bytes())
                layers[-1]["title"] = payload
                _write_json(root / "catalogs/landscape/foundation.json",
                            {"schema_version": 2, "layers": layers})
                text = fs.serialize(fs.build_document(root))
                self.assertEqual(text.index(payload), 90536 - len(payload) // 2)
                with self.assertRaises(SystemExit):
                    self.run_main(root, "--write", native_scan=True, private_names=(name,))
                self.assertEqual(((root / fs.OUTPUT).read_bytes(),
                                  (root / "manifests/evidence.json").read_bytes()), before)


    @unittest.skipUnless(shutil.which("betterleaks"), "native publication contract requires Betterleaks 1.9.0")
    def test_benign_entry_accepted_by_native_stdin_remains_publishable(self):
        root = self.fixture_root()
        catalog = root / "catalogs/landscape/foundation.json"
        source = json.loads(catalog.read_bytes())
        source["layers"][0]["title"] = "x" * 23000
        _write_json(catalog, source)
        try:
            exit_code, output = self.run_main(root, "--write", native_scan=True)
        except SystemExit as error:
            self.fail(f"Native-clean entry unexpectedly refused: {error}")
        self.assertEqual(exit_code, 0, output)
        self.assertEqual(json.loads((root / fs.OUTPUT).read_bytes())["layers"][0]["title"], "x" * 23000)
        registered = json.loads((root / "manifests/evidence.json").read_bytes())["files"]
        self.assertEqual(registered[0]["sha256"], hashlib.sha256((root / fs.OUTPUT).read_bytes()).hexdigest())

    @unittest.skipUnless(shutil.which("betterleaks"), "native entry guard requires Betterleaks 1.9.0")
    def test_oversized_actual_record_refuses_and_preserves_publication(self):
        self._assert_private_text_is_refused_before_publication(
            "x" * 25000, spy_publication=False, expected_message="publication entry too large")

    def test_oversized_record_reports_size_refusal_and_preserves_bytes(self):
        root = self.fixture_root()
        self.assertEqual(self.run_main(root, "--write")[0], 0)
        before = ((root / fs.OUTPUT).read_bytes(), (root / "manifests/evidence.json").read_bytes())
        with mock.patch.object(host_name_scan, "scan_paths", side_effect=
                               host_name_scan.PublicationEntryTooLarge("publication entry too large")):
            with self.assertRaisesRegex(SystemExit, "publication entry too large; aborting"):
                self.run_main(root, "--write", native_scan=True)
        self.assertEqual(((root / fs.OUTPUT).read_bytes(), (root / "manifests/evidence.json").read_bytes()), before)

    @unittest.skipUnless(shutil.which("betterleaks"), "native write privacy plant requires Betterleaks 1.9.0")
    def test_explicit_private_account_is_refused_before_write_or_registration(self):
        self._assert_private_text_is_refused_before_publication("fixture-private-account")

    @unittest.skipUnless(shutil.which("betterleaks"), "native write privacy plants require Betterleaks 1.9.0")
    def test_native_scanner_refuses_encoded_account_plants_before_publication(self):
        name = "fixture-private-account"
        plants = {
            "percent": "".join("%" + format(byte, "02X") for byte in name.encode()),
            "unicode": "".join(r"\u" + format(ord(char), "04x") for char in name),
            "base64": base64.b64encode(name.encode()).decode(),
            "hex": name.encode().hex(),
            "uppercase": name.upper(),
        }
        for form, payload in plants.items():
            with self.subTest(form=form):
                self._assert_private_text_is_refused_before_publication(payload)
        self._assert_private_text_is_refused_before_publication("fixtureéaccount", private_name="fixtureéaccount")

    def test_check_is_independent_of_root_account_and_native_scanner(self):
        root = self.fixture_root()
        self.assertEqual(self.run_main(root, "--write")[0], 0)
        with mock.patch.object(host_name_scan, "host_names", side_effect=AssertionError("host context read")), \
                mock.patch.object(host_name_scan, "scan_paths", side_effect=AssertionError("native scanner invoked")):
            exit_code, output = self.run_main(root, "--check", native_scan=True, private_names=("root",))
        self.assertEqual(exit_code, 0, output)

    def test_native_scanner_failure_preserves_output_and_registration(self):
        root = self.fixture_root()
        self.assertEqual(self.run_main(root, "--write")[0], 0)
        before = ((root / fs.OUTPUT).read_bytes(), (root / "manifests/evidence.json").read_bytes())
        with mock.patch.object(Path, "write_text") as write, mock.patch.object(hr, "register_file") as register, \
                mock.patch.object(host_name_scan, "scan_paths", side_effect=host_name_scan.HostNameScanError("native failure")):
            with self.assertRaisesRegex(SystemExit, "private publication scanner unavailable"):
                self.run_main(root, "--write", native_scan=True)
            write.assert_not_called()
            register.assert_not_called()
        self.assertEqual(((root / fs.OUTPUT).read_bytes(), (root / "manifests/evidence.json").read_bytes()), before)

    def test_native_scan_precedes_output_write_and_registration(self):
        root = self.fixture_root()
        events = []
        scanned = []

        def scan(paths, *, root, names, reject_email=False):
            events.append("scan")
            self.assertEqual(names, ("fixture-private-account",))
            self.assertTrue(reject_email)
            self.assertEqual(len(paths), 1)
            entries = [json.loads(path.read_bytes()) for path in paths]
            scanned.extend(entries)
            self.assertTrue(all(path != root / fs.OUTPUT for path in paths))
            self.assertEqual(paths[0].name, "candidate.json")
            self.assertTrue(all(path.read_bytes().startswith(b"{") and len(path.read_bytes()) < 25000
                                for path in paths))
            return []

        with mock.patch.object(host_name_scan, "scan_paths", side_effect=scan), \
                mock.patch.object(Path, "write_text", side_effect=lambda *a, **k: events.append("write")), \
                mock.patch.object(hr, "register_file", side_effect=lambda *a: events.append("register")):
            exit_code, output = self.run_main(root, "--write", native_scan=True)
        self.assertEqual(exit_code, 0, output)
        self.assertGreater(len(scanned), 1)
        self.assertIn("Title for layer-a", [entry.get("title") for entry in scanned])
        self.assertEqual(events, ["scan"] * len(scanned) + ["write", "register"])

    @unittest.skipUnless(shutil.which("betterleaks"), "native write privacy control requires Betterleaks 1.9.0")
    def test_native_write_scanner_preserves_unicode_alphanumeric_boundaries(self):
        root = self.fixture_root()
        source = root / "catalogs/landscape/foundation.json"
        document = json.loads(source.read_text())
        document["layers"][0]["title"] = "Afixture-private-accountZ"
        _write_json(source, document)
        exit_code, output = self.run_main(root, "--write", native_scan=True)
        self.assertEqual(exit_code, 0, output)
        self.assertIn("Afixture-private-accountZ", (root / fs.OUTPUT).read_text())

    def test_private_context_failure_preserves_output_and_registration(self):
        root = self.fixture_root()
        self.assertEqual(self.run_main(root, "--write")[0], 0)
        before = ((root / fs.OUTPUT).read_bytes(), (root / "manifests/evidence.json").read_bytes())
        with mock.patch.object(Path, "write_text") as write, mock.patch.object(hr, "register_file") as register, \
                mock.patch.object(host_name_scan, "host_names", side_effect=host_name_scan.HostNameScanError("unavailable")):
            with self.assertRaisesRegex(SystemExit, "private identity context unavailable"):
                self.run_main(root, "--write")
            write.assert_not_called()
            register.assert_not_called()
        self.assertEqual(((root / fs.OUTPUT).read_bytes(), (root / "manifests/evidence.json").read_bytes()), before)

    def test_builder_does_not_collect_private_host_context(self):
        root = self.fixture_root()
        with mock.patch.object(host_name_scan, "host_names", side_effect=AssertionError("host context accessed")):
            document = fs.build_document(root)
        self.assertEqual(len(document["layers"]), 1)

    def test_inconsistent_documents_are_named(self):
        root = self.fixture_root()
        document = fs.build_document(root)
        landscape = fs.landscape_rows(fs.Sources(root))
        self.assertEqual(fs.document_errors(document, landscape), [])
        document["index"]["by_repository"]["github.com/example/widget"].append(
            {"catalog": "foundation", "layer_id": "layer-gone", "role": "winner"})
        document["index"]["by_repository"]["github.com/example/stray"] = [
            {"catalog": "foundation", "layer_id": "layer-a", "role": "alternate"}]
        document["layers"][0]["winners"].append(dict(document["layers"][0]["winners"][0], component_id="ghost"))
        problems = fs.document_errors(document, landscape)
        self.assertIn("index github.com/example/widget points to the missing layer foundation/layer-gone", problems)
        self.assertIn("index github.com/example/stray names it a alternate of foundation/layer-a, which does not "
                      "list it", problems)
        self.assertIn("winner ghost of foundation/layer-a is absent from its landscape row", problems)

    def test_nothing_outside_the_root_is_read(self):
        root = self.fixture_root()
        self.run_main(root, "--write")
        opened, original_open = [], Path.open

        def recording_open(path, *args, **kwargs):
            opened.append(Path(path).resolve())
            return original_open(path, *args, **kwargs)

        with mock.patch.object(Path, "open", recording_open):
            exit_code, output = self.run_main(root, "--check")
        self.assertEqual(exit_code, 0, output)
        self.assertIn(root / fs.LOCKFILE, opened)
        self.assertEqual([path for path in opened if not path.is_relative_to(root)], [])

    def test_a_source_symlinked_out_of_the_root_is_refused(self):
        root = self.fixture_root()
        outside = self.root() / "research-state.json"
        _write_json(outside, {"layers": []})
        target = root / fs.RESEARCH_STATE
        target.unlink()
        target.symlink_to(outside)
        with self.assertRaisesRegex(fs.FinalStackError, "symlinks are forbidden"):
            fs.build_document(root)

    def test_check_flags_verdicts_past_next_review_and_exits_zero(self):
        root = self.fixture_root()
        self.run_main(root, "--write")
        exit_code, output = self.run_main(root, "--check", "--today", "2026-10-23")
        self.assertEqual(exit_code, 0, output)
        self.assertIn("--today 2026-10-23: 1 layer(s) past next_review: foundation/layer-a (2026-10-22)", output)
        exit_code, output = self.run_main(root, "--check", "--today", "2026-10-22")
        self.assertEqual(exit_code, 0, output)
        self.assertIn("--today 2026-10-22: 0 layer(s) past next_review", output)
        self.assertIn("next_review not evaluated", self.run_main(root, "--check")[1])

    def test_landscape_winner_readers_see_no_new_winner_pins(self):
        # scripts/host_receipts.py landscape_winners reads layers[].winners[] of every catalogs/landscape/*.json, so
        # the final-stack copies must leave its ids, pins and stack aliases unchanged.
        root = self.root()
        _fixture(root, foundation=[_layer("layer-a", winners=[_winner("widget", pin="1.0.0")])], stack=[
            {"id": "widget-cli", "repository": "https://github.com/example/widget", "version": "1.1.0"}])

        def readers():
            return (hr.landscape_component_ids(root), hr.winner_stack_aliases(root), hr.winner_pins(root, "widget"))

        before = readers()
        self.assertEqual(self.run_main(root, "--write")[0], 0)
        self.assertEqual(readers(), before)
        self.assertEqual(before, ({"widget"}, {"widget-cli": ("widget",)}, {"1.0.0"}))


def _angle_fixture() -> dict:
    """Synthetic, fully sourced convergence control, not a candidate measurement."""
    stamp = "2026-10-12T21:34:46Z"
    return {
        "schema_version": 1, "rule_version": "angle-convergence/2", "catalog": "foundation",
        "layer_id": "layer-a", "weights_stated_at": "2026-10-12T21:32:22Z",
        "weights": {"A1": .20, "A2": .20, "A3": .15, "A4": .15, "A5": .20, "A6": .10},
        "weight_reason": "Synthetic v2 default-weight control.", "published_evaluations_available": True,
        "disclosure": "Synthetic fixture; no real candidate score or runtime claim.",
        "resolution_inputs": [], "gaps": [], "final_evidence": [],
        "candidates": [{
            "id": "widget", "name": "Widget", "repository": "https://github.com/example/widget",
            "pin": COMMIT_A, "role": "fixture", "a1_screened": True, "a6_comparative": False,
            "confounds": ["Synthetic fixture."], "disqualifier": None,
            "verdict": "CONVERGED", "provisional": True, "measure_next": None,
            "angles": {angle: {"score": "+" if angle != "A6" else "U", "read_at": stamp,
                                "sources": [{"kind": "url", "url": "https://example.org/fixture",
                                             "read_at": stamp}] if angle != "A6" else [],
                                "note": "Synthetic source control."}
                       for angle in ("A1", "A2", "A3", "A4", "A5", "A6")},
        }],
    }


class AngleEnforcementTests(FixtureTestCase):
    def prepare(self, *, final=False, evidence_class="native_proven", run=True):
        root = self.root()
        _fixture(root, foundation=[_layer("layer-a", winners=[_winner("widget", pin=COMMIT_A)],
                                         terminal_state="FINAL" if final else None)],
                 stack=[{"id": "widget", "repository": "https://github.com/example/widget",
                         "version": "1.0.0", "source_pin": COMMIT_A}] if run else [],
                 sweeps=[_sweep("fixture", "2026-09-22", [("foundation", "layer-a")])])
        record = _angle_fixture()
        if final:
            c = record["candidates"][0]
            c.update(a6_comparative=True, provisional=False)
            paired = "evidence/artifacts/fixture/paired.json"
            c["angles"]["A6"].update(score="+", sources=[{"kind": "receipt", "path": paired}])
            arms = []
            for ident in ("a", "b"):
                native = f"evidence/artifacts/fixture/arm-{ident}.txt"
                _write(root / native, "Synthetic native result stand-in.\n")
                arms.append({"id": ident, "native_output": native})
            _write_json(root / paired, {"kind": "comparative", "evidence_class": "native_proven",
                "completed": True, "harness": "paired", "repository": c["repository"], "pin": c["pin"],
                "confounds": ["Synthetic policy control, not a real measured comparison."], "arms": arms})
        wave_path = "catalogs/sota-convergence/layer-verdicts-20260922.json"
        _write_json(root / wave_path, {"layers": [{"layer_id": "layer-a", "fixture": True}]})
        _write_json(root / "catalogs/sota-convergence/layer-verdict-waves.json", {"waves": [{
            "run_id": "20260922", "path": wave_path,
            "sha256": hashlib.sha256((root / wave_path).read_bytes()).hexdigest()}]})
        record["final_evidence"] = [{"candidate_id": "widget", "run_pin": COMMIT_A,
                                      "e2e_receipt": "evidence/artifacts/fixture/e2e.json",
                                      "invoke_receipt": "evidence/artifacts/fixture/invoke.json",
                                      "not_invoked_reason": None}]
        _write_json(root / "evidence/artifacts/fixture/e2e.json", {
            "kind": "upstream_e2e", "repository": "https://github.com/example/widget", "pin": COMMIT_A,
            "evidence_class": evidence_class, "success": True,
            "upstream_sources": [{"kind": "repo", "repository": "https://github.com/example/widget",
                                   "pin": COMMIT_A, "path": "README.md", "line": 1}],
            "commands": [{"phase": "install", "command": "fixture install", "exit_code": 0},
                         {"phase": "test", "command": "fixture test", "exit_code": 0}]})
        _write_json(root / "evidence/artifacts/fixture/invoke.json", {
            "kind": "invocation", "repository": "https://github.com/example/widget", "pin": COMMIT_A,
            "evidence_class": evidence_class, "window_start": "2026-10-12T21:32:22Z",
            "window_end": "2026-10-12T21:34:46Z", "calls": 1})
        directory = root / "catalogs/landscape/angles"
        directory.mkdir(parents=True, exist_ok=True)
        schema = REPO_ROOT / "catalogs/landscape/angles/schema.json"
        if schema.exists():
            shutil.copyfile(schema, directory / "schema.json")
        path = directory / "foundation-layer-a.json"
        _write_json(path, record)
        return root, path, record

    def assert_check_rejects(self, mutate, reason, *, final=False, run=True):
        root, path, record = self.prepare(final=final, run=run)
        _write(root / fs.OUTPUT, fs.serialize(fs.build_document(root)))
        mutate(record, root)
        _write_json(path, record)
        code, output = self.run_main(root, "--check")
        self.assertEqual(code, 1, output)
        self.assertIn(reason, output)

    def test_check_rejects_weight_sum(self):
        self.assert_check_rejects(lambda r, _: r["weights"].update(A1=.30), "weight sum must equal 1")

    def test_check_rejects_weights_stated_after_scoring(self):
        self.assert_check_rejects(lambda r, _: r.update(weights_stated_at="2026-10-12T21:34:47Z"), "before scoring")

    def test_check_rejects_score_without_source(self):
        self.assert_check_rejects(lambda r, _: r["candidates"][0]["angles"]["A3"].update(sources=[]), "score without source")

    def test_check_rejects_verdict_that_does_not_rederive(self):
        self.assert_check_rejects(lambda r, _: r["candidates"][0].update(verdict="REJECTED"), "stated verdict does not re-derive")

    def test_final_rejects_winner_without_convergence(self):
        def mutate(record, _):
            candidate = record["candidates"][0]
            candidate["angles"]["A3"]["score"] = "-"
            candidate.update(verdict="DISAGREE", provisional=False, measure_next="Compare the disagreement.")
        self.assert_check_rejects(mutate, "winner requires one CONVERGED angle verdict", final=True)

    def test_final_rejects_missing_evidence_class(self):
        root, path, record = self.prepare(final=True)
        _write(root / fs.OUTPUT, fs.serialize(fs.build_document(root)))
        source = root / "catalogs/landscape/foundation.json"
        doc = json.loads(source.read_bytes())
        del doc["layers"][0]["winners"][0]["evidence_class"]
        _write_json(source, doc)
        code, output = self.run_main(root, "--check")
        self.assertEqual(code, 1, output)
        self.assertIn("condition 1 winner has no evidence class", output)

    def test_final_rejects_missing_run_pin(self):
        root, _, _ = self.prepare(final=True, run=False)
        code, output = self.run_main(root, "--check")
        self.assertEqual(code, 1, output)
        self.assertIn("condition 2 winner requires a matching run pin", output)

    def test_final_rejects_missing_e2e_receipt(self):
        self.assert_check_rejects(lambda r, _: r["final_evidence"][0].update(e2e_receipt=None),
                                  "condition 3 requires e2e_receipt", final=True)

    def test_final_rejects_missing_invoke_evidence_and_reason(self):
        self.assert_check_rejects(lambda r, _: r["final_evidence"][0].update(invoke_receipt=None),
                                  "condition 4 requires invoke evidence or a recorded non-invocation reason", final=True)

    def test_final_accepts_bound_receipts_and_recorded_non_invocation_reason(self):
        for reason in (None, "The role is retained for recovery; it was not needed in this measured window."):
            with self.subTest(reason=reason):
                root, path, record = self.prepare(final=True)
                if reason:
                    record["final_evidence"][0].update(invoke_receipt=None, not_invoked_reason=reason)
                    _write_json(path, record)
                _write(root / fs.OUTPUT, fs.serialize(fs.build_document(root)))
                code, output = self.run_main(root, "--check")
                self.assertEqual(code, 0, output)

    def test_missing_records_are_reported_as_gaps(self):
        document = self.build(foundation=[_layer("layer-a")])
        self.assertEqual(self.layer(document, "layer-a")["angles"]["status"], "missing")
        self.assertEqual(document["summary"]["angles"]["missing"], 1)

    def test_final_rejects_receipts_for_another_pin_or_synthetic_execution(self):
        native_binding = "condition 3 receipt must bind native evidence to repository and complete FINAL pin identity"
        invoke_window = "condition 4 requires positive invocation calls in a measured window"
        for field, mutation, reason in (("e2e_receipt", {"pin": COMMIT_B}, native_binding),
                                        ("e2e_receipt", {"evidence_class": "synthetic"}, native_binding),
                                        ("invoke_receipt", {"calls": 0}, invoke_window),
                                        ("invoke_receipt", {"calls": True}, invoke_window),
                                        ("invoke_receipt", {"window_end": "2026-10-12T21:32:22Z"}, invoke_window)):
            with self.subTest(field=field, mutation=mutation):
                root, _, record = self.prepare(final=True)
                path = root / record["final_evidence"][0][field]
                receipt = json.loads(path.read_bytes())
                receipt.update(mutation)
                _write_json(path, receipt)
                # If a guard is removed, refresh the output so source drift
                # cannot stand in for the intended receipt rejection.
                try:
                    document = fs.build_document(root)
                except fs.FinalStackError:
                    pass
                else:
                    _write(root / fs.OUTPUT, fs.serialize(document))
                code, output = self.run_main(root, "--check")
                self.assertEqual(code, 1, output)
                self.assertIn(reason, output)

    def test_nonfinal_pin_and_review_flags_remain_report_only(self):
        root = self.root()
        _fixture(root, foundation=[_layer("layer-a", winners=[_winner("widget", pin=COMMIT_A)])],
                 sweeps=[_sweep("fixture", "2026-09-22", [("foundation", "layer-a")])])
        _write(root / fs.OUTPUT, fs.serialize(fs.build_document(root)))
        code, output = self.run_main(root, "--check", "--today", "2026-10-23")
        self.assertEqual(code, 0, output)
        self.assertIn("report-only", output)

    def test_a_comparative_flag_cannot_turn_a_smoke_receipt_into_a6(self):
        root, path, record = self.prepare()
        _write(root / fs.OUTPUT, fs.serialize(fs.build_document(root)))
        c = record["candidates"][0]
        c.update(a6_comparative=True, provisional=False)
        c["angles"]["A6"].update(score="+", sources=[
            {"kind": "receipt", "path": "evidence/artifacts/fixture/smoke.json"}])
        _write_json(root / "evidence/artifacts/fixture/smoke.json", {
            "kind": "smoke", "evidence_class": "native_proven", "success": True})
        _write_json(path, record)
        code, output = self.run_main(root, "--check")
        self.assertEqual(code, 1, output)
        self.assertIn("comparative upstream run", output)

    def test_comparative_a6_binds_and_tracks_native_outputs(self):
        root, path, record = self.prepare()
        c = record["candidates"][0]
        c.update(a6_comparative=True, provisional=False)
        receipt_path = "evidence/artifacts/fixture/paired.json"
        c["angles"]["A6"].update(score="+", sources=[{"kind": "receipt", "path": receipt_path}])
        native_paths = ["evidence/artifacts/fixture/arm-a.txt", "evidence/artifacts/fixture/arm-b.txt"]
        for native in native_paths:
            _write(root / native, "Synthetic stand-in for an upstream result artifact.\n")
        _write_json(root / receipt_path, {
            "kind": "comparative", "evidence_class": "native_proven", "completed": True,
            "harness": "paired", "repository": c["repository"], "pin": c["pin"],
            "confounds": ["Synthetic policy control, not a measured comparison."],
            "arms": [{"id": ident, "native_output": native} for ident, native in zip(("a", "b"), native_paths)]})
        _write_json(path, record)
        document = fs.build_document(root)
        self.assertTrue(all(p in document["sources"] for p in native_paths))
        self.assertFalse(self.layer(document, "layer-a")["angles"]["candidates"][0]["provisional"])


class RepositoryTests(unittest.TestCase):
    def test_real_noncommit_source_pins_are_retained_in_declared_runs(self):
        stack = json.loads((REPO_ROOT / fs.STACK).read_bytes())
        document = fs.build_document(REPO_ROOT)
        expected = {"postgresql": "sha256", "poppler": "sha256", "restic": "tag", "dagu": "tag"}
        for component in stack["components"]:
            if component["id"] in expected:
                with self.subTest(component=component["id"]):
                    run = fs.run_pin(document, component["id"])
                    self.assertEqual(run.get("source_pin"), component["source_pin"])
                    self.assertEqual(run.get("source_pin_kind"), expected[component["id"]])

    def test_committed_check_ignores_common_account_context(self):
        for account in ("root", "ubuntu", "node", "dev"):
            with self.subTest(account=account), mock.patch.dict("os.environ", {
                    host_name_scan.OVERRIDE: json.dumps([account])}), \
                    mock.patch.object(host_name_scan, "host_names", side_effect=AssertionError("host read")), \
                    mock.patch.object(host_name_scan, "scan_paths", side_effect=AssertionError("native scan")), \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(fs.main(["--root", str(REPO_ROOT), "--check"]), 0)

    def test_serializer_is_the_shared_first_party_callable(self):
        self.assertIs(fs.serialize, cm.serialize)
        self.assertEqual(fs.serialize({"z": 1, "a": []}), '{\n  "a": [],\n  "z": 1\n}\n')

    def test_review_days_uses_the_imported_shared_sweep_policy(self):
        import importlib
        from scripts import currency_due, sweep_policy
        try:
            with mock.patch.object(sweep_policy, "DEFAULT_SWEEP_CADENCE_DAYS", 45):
                importlib.reload(currency_due)
                importlib.reload(fs)
                self.assertEqual((currency_due.DEFAULT_SWEEP_CADENCE_DAYS, fs.REVIEW_DAYS), (45, 45))
        finally:
            importlib.reload(currency_due)
            importlib.reload(fs)

    def test_evidence_contribution_and_hot_file_guides_refresh_and_check_final_stack(self):
        for relative, writes in (("docs/contributing-evidence.md", 2), ("docs/lanes.md", 1)):
            with self.subTest(document=relative):
                document = " ".join((REPO_ROOT / relative).read_text(encoding="utf-8").split())
                self.assertGreaterEqual(document.count("python3 scripts/final_stack.py --write"), writes)
                self.assertIn("python3 scripts/final_stack.py --check", document)
                self.assertIn("catalogs/landscape/final-stack.json", document)

    def test_review_days_is_the_sweep_cadence(self):
        from scripts import currency_due
        self.assertEqual(fs.REVIEW_DAYS, currency_due.DEFAULT_SWEEP_CADENCE_DAYS)

    def test_committed_manifest_is_current(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            exit_code = fs.main(["--root", str(REPO_ROOT), "--check"])
        self.assertEqual(exit_code, 0, buffer.getvalue())


if __name__ == "__main__":
    unittest.main()
