"""Tests for scripts/final_stack.py: the status rules, the W1b API (is_definitive, run_pin), the run-pin
precedence, the pin parser and --check. Every test builds its own temporary fixture root except the one that
checks the committed manifest."""

from __future__ import annotations

import contextlib
from datetime import date
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from scripts import component_matrix as cm
from scripts import final_stack as fs
from scripts import host_receipts as hr

REPO_ROOT = Path(__file__).resolve().parents[1]
COMMIT_A = "a" * 40
COMMIT_B = "b" * 40


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
    _write_json(landscape / "planned-layers.json", {"schema_version": 1, "layers": list(planned)})
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
    def run_main(root: Path, *args) -> tuple[int, str]:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
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

    def test_a_planned_layer_is_unswept(self):
        document = self.build(foundation=[_layer("layer-a", winners=[_winner("widget")])], planned=[_planned()],
                              sweeps=[_sweep("sweep-0923", "2026-09-23", [("foundation", "layer-a")])])
        layer = self.layer(document, "planned-a")
        self.assertEqual((layer["status"], layer["verdict"], layer["winners"]), ("unswept", None, []))
        self.assertEqual(layer["source"], "catalogs/landscape/planned-layers.json#/layers/0")
        self.assertEqual(document["summary"]["status"],
                         {"unswept": 1, "no-winner": 0, "reopened": 1, "converged": 0, "current": 0})

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
        self.assertEqual(answer.reason, "untracked")


class PinTests(unittest.TestCase):
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
        self.assertEqual(fs.record_pin("1.0.0", "v1.0.0"), {"pin_parsed": {"version": "1.0.0", "commit": None}})

    def test_compare_pins_is_three_valued(self):
        parsed = fs.parse_pin
        self.assertEqual(fs.compare_pins(parsed("v0.44.0; source " + COMMIT_A), parsed("0.44.0")), "same")
        self.assertEqual(fs.compare_pins(parsed("0.44.0"), parsed("0.45.0")), "differs")
        self.assertEqual(fs.compare_pins(parsed("0.44.0 @ " + COMMIT_A), parsed("0.44.0 @ " + COMMIT_B)), "differs")
        self.assertEqual(fs.compare_pins(parsed(COMMIT_A), parsed("0.44.0")), "unknown")
        self.assertEqual(fs.compare_pins(parsed("unpinned"), parsed("0.44.0")), "unknown")


class RunTests(FixtureTestCase):
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


class RepositoryTests(unittest.TestCase):
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
