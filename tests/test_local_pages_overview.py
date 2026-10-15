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
import os
from pathlib import Path
import re
import sys
import tempfile
import unittest
import unittest.mock

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
# Synthetic records in the shape of the WS2 and WS5 convergence records; each carries a path, a digest, a
# line reference or a declared drop term that the projection must withhold.
WS2 = ("# Fixture convergence\n\nTwo blind judges scored the arms. It claims no fixture return and no measured winner.\n\n"
       "## Inputs\n- Fixture packet /var/tmp/fixture/packet (SHA256SUMS abc1234d...).\n"
       "- Claude-family judge (Opus 9.9, fixture subagent): /var/tmp/fixture/judge.md, sha256 abc1234d...\n"
       "- GPT-family judge (gpt-9-fixture xhigh, fixture runner): /var/tmp/fixture/verdict.md\n\n"
       "## Converged by both judges (fixture note)\n"
       "1. **Every fixture list lags by construction.** Lists are a baseline that fixture signals must beat. The list\n"
       "   comes from /var/tmp/fixture/lists.json.\n"
       "2. **Fixture replay needs capture.** Ranks cannot be replayed.\n"
       "3. **The early fixture candidates cost $0.** Each is a separate fixture detector:\n\n"
       "| # | Signal (feed we hold) | Leads or lags | Replay | False-alarm profile |\n|---|---|---|---|---|\n"
       "| 1 | fixture signal one | leads by fixture | see /var/tmp/fixture/replay.md | few fixture flags |\n"
       "| 2 | fixture signal two | lags. Measured in probe.py beef1234:12-14. | Derive | noisy fixture |\n\n"
       "4. **Lagging or conditioning only, not entry rows:** fixture pause; fixture prints.\n"
       "5. **Paid and conditional; no purchase until a measured gap justifies it:**\n   - Fixture vendor A: $1 a month.\n   - Fixture vendor B: no API.\n\n"
       "## First-hand live stack: what we hold, and the gaps\n- **Held:** fixture feeds.\n"
       "- **Gap 1, the fixture connection allowance.** Measured on paper-x, which shares a slot. A whole-fixture capture\n"
       "  needs its own connection. Its capacity is unmeasured.\n- **Gap 2:** fixture entitlement checks (above).\n\n"
       "## Next, by readiness trigger\n1. When fixture A holds: step one.\n")
WS5 = ("# Fixture shortlist\n\n## Inputs\n1. **The one input shortlist family is not this.** input\n\n## Converged by both judges\n"
       "1. **The one strict shortlist family is the fixture breakout on the top fixture names,**\n   from doi:10.0000/fixture.\n"
       "   - Source rules:\n     - Fixture rule one.\n"
       "   - Source result: fixture stocks, 2001-2002. Top 5 returned 10% net; commission was $0.01/share. There was **no sealed\n"
       "     out-of-sample test and no fixture slippage model.** The fixture recreation covers 2001 only, inside the sample.\n"
       "     Kept at /var/tmp/fixture/result.md.\n"
       "2. **Fixture selector inside the breakout.** Detail.\n"
       "3. **The other fixture templates lack results:**\n   - Fixture template X: none.\n"
       "   They enter only as on/off ablations of the fixture row:\n   - fixture filter one;\n   - a fixture gate (see cafe1234).\n"
       "4. **Selector and sizing (fixture):**\n   - eligibility before fixture ranking;\n   - at most 2 fixture names, an account-level setting.\n\n"
       "## Disputed\n1. **Not this either.**\n")
ADDENDUM = ("# Fixture convergence, ADDENDUM-01: fixture measurements (fixture record)\n\n"
            "This is a new record. fixture-lane measured these on fixture-paper over REST, opening no new stream. All four results are author-run measurements with receipts.\n"
            "- Dispute #1 (fixture statuses entitlement): SETTLED, confirmed. The server said ok\n  (probe-1.json, abcdef12...).\n"
            "- Dispute #2 (fixture overnight coverage): SETTLED, no overnight history.\n"
            "  - Fixture bars: 3 of 90 in the window (fixture-overnight.json, 1234abcd...).\n"
            "  - Row 9's overnight part is therefore a fixture forward capture only.\n"
            "- Dispute #3 (fixture BOATS entitlement): SETTLED, real-time confirmed.\n  - A fixture snapshot returned 5 of 5 symbols.\n"
            "- FIXTURE-OPRA: historical access confirmed (HTTP 200; fixture-opra.json). Real-time is NOT yet\n"
            "  proven; the one-shot fixture check settles it.\nEffect: fixture rows are entitled.\n")

PREP = ("# Fixture floor 9.9.2 prep\n\n## Signed manifest\n| Item | Value |\n|---|---|\n| Manifest | sha256 `" + "e" * 64 + "` |\n\n"
        "## Source commit for the run pin\n\nThe fixture commit whose log first carries `## 9.9.2` is `" + "c" * 40 + "`. The one before, `"
        + "d" * 40 + "`, tops at 9.9.1.\n")
CHANGELOG = ("## 9.9.2\n\n- Added fixture alpha: with its detail\n- Fixed fixture bug one\n- Added fixture beta\n- Changed fixture gamma\n"
             "- Improved fixture delta\n- Added fixture path note in ~/.fixture/x.md\n- Added fixture epsilon\n- Added fixture zeta\n\n"
             "## 9.9.1\n\n- Fixed fixture bug two\n")
SLOTS = {"client_version": "9.9.1", "checked_at": "2099-01-01", "status_values": {"default": "fixture", "trial": "fixture"},
         "slots": [{"id": "slot-a", "status": "trial", "default": "Fixture default A; with a long tail"},
                   {"id": "slot-b", "status": "default", "default": "Fixture default B", "client_version": "9.9.2"}]}
PLAN = ("# Fixture plan\n\n## Waves\n**F1. Fixture receipts.** Trigger: inputs exist now. More text.\n\n"
        "**F2. Fixture invoke.** Trigger: #9001 lands, then the fixture\nfollow-up lands. Detail.\n- a bullet\n\n**F3. Fixture no trigger.** Owners: fixture.\n")
F1_INDEX = [{"spec": "a", "success": True, "pin_ok": True, "assembled": "v2", "receipt": "x"}, {"spec": "b", "success": True, "pin_ok": False, "assembled": "v2"},
            {"spec": "b2", "success": True, "pin_ok": False, "assembled": "preview"}, {"spec": "c", "success": False},
            {"spec": "d", "state": "running"}, {"spec": "e", "state": "not-started"}]
F2 = ("# Fixture F2\n\n**Top:** ignored.\n\n## Receipts (directory `receipts/`)\n| Receipt | Calls |\n|---|---|\n| r1 | 1 |\n| r2 | 2 |\n\n"
      "**Inputs:**\n\n| File | sha |\n|---|---|\n| f | 1 |\n\n## Findings (no receipt)\n- **one:** x\n  - nested\n- **two:** y\n\n## Empty\nnothing here\n")
ARMS = ("# Fixture arms\n\n| arm | file(s) | route and provenance | notes |\n|---|---|---|---|\n"
        "| FixtureFlow | a.md | tools/fixture/dispatch as fixture-agent; run.x | none |\n| Fixture Codex | b.md | lane on cx/gpt-9-fixture max | ok |\n"
        "| fixture-claude | c.md | ns-run (Opus 9.9, slot api-9) | ok |\n| Fixture Researcher | d.md | ~/.config/fixture/gpt-researcher.sh | sources 3 |\n")


def write(base: Path, relative: str, text: str) -> None:
    path = base / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


class Fixture:
    def __init__(self, base: Path, *, stack=None, matrix_doc=None, cc_now=CC_NOW, ws2=True, rows=True):
        self.root, self.state = base / "repo", base / "state"
        files = {
            "catalogs/landscape/final-stack.json": stack or final_stack(),
            "catalogs/landscape/foundation.json": {"layers": [{"layer_id": "alpha", "title": "Alpha layer"}, {"layer_id": "beta", "title": "Beta layer"}]},
            "catalogs/landscape/us-equities.json": {"layers": [{"layer_id": "gamma", "title": "Gamma layer"}]},
            "catalogs/landscape/component-evidence-matrix.json": matrix_doc or matrix(),
            "manifests/evidence.json": {"receipts": [{"path": "evidence/receipts/tool-a-smoke-20990101.json", "kind": "native_cli_e2e", "component_ids": ["codex"]},
                                                     {"path": "evidence/receipts/tool-a-smoke-20990305.json", "kind": "native_model_e2e", "component_ids": ["codex", "claude-code"]},
                                                     {"path": "docs/decisions/index-20991231.json", "kind": "historical_inventory", "component_ids": ["codex", "claude-code"]},
                                                     {"path": "evidence/receipts/other-20991231.json", "kind": "native_cli_e2e", "component_ids": ["other"]}]},
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
            state_files[f"{STATE_DIR}/finalize-all-20261014/ROWS-252babe4.md"] = ROWS_NEW
        if ws2:
            state_files[f"{STATE_DIR}/ranked-feeds-20261014/CONVERGENCE-WS2-20261014.md"] = WS2
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
        repos = html[html.index('id="ov-repos"'):html.index('id="overview-evidence"')]
        self.assertEqual(repos.count('<th scope="col">State</th>'), 1)  # the foundation group's states differ, so only it keeps the column

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
        self.assertEqual(data["repos"]["rows_record"], "ROWS-252babe4.md")
        _, html = fixture.build(self.base)
        # One state shared by a group's catalog layers is said once; the planned row carries its own status.
        self.assertIn("2 catalog layers, all not terminal.", html)
        self.assertIn("1 catalog layer, not terminal.", html)
        self.assertIn("planned, outside the catalog file; unswept", html)
        self.assertNotIn('<th scope="col">State</th>', html[html.index('id="ov-repos"'):html.index('id="overview-evidence"')])
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
        self.assertNotIn("index-20991231", html)  # an inventory is not an execution receipt

    def test_a_receipt_dated_by_its_directory_is_ranked_by_that_date(self):
        # The local review's P2 at e1f72b230: only the file name was searched, so evidence/artifacts/<name>-<date>/
        # receipt.json had no date and ranked behind any older dated file name.
        fixture = Fixture(self.base)
        manifest = fixture.root / "manifests/evidence.json"
        document = json.loads(manifest.read_text())
        document["receipts"].append({"path": "evidence/artifacts/tool-a-run-20990401/receipt.json", "kind": "native_cli_e2e",
                                     "component_ids": ["codex"]})
        manifest.write_text(json.dumps(document))
        rows = {row["name"]: row for row in DATA.model(fixture.root, fixture.state, commit="0" * 40)["workers"]}
        self.assertEqual((rows["Codex"]["receipt"]["path"], rows["Codex"]["receipt"]["date"]),
                         ("evidence/artifacts/tool-a-run-20990401/receipt.json", "2099-04-01"))

    def test_a_receipt_cited_from_the_registry_is_never_said_to_be_read(self):
        # The local review's P2 at e1f72b230: the page reads the registry row, not the receipt, so wherever the page
        # renders that receipt it says it is a registry reference, never a read.
        fixture = Fixture(self.base)
        data = DATA.model(fixture.root, fixture.state, commit="0" * 40)["evidence"]
        cited = next(row for row in data["repository"] if row["path"] == "evidence/receipts/tool-a-smoke-20990305.json")
        self.assertEqual(cited["status"], "registered")
        _, html = fixture.build(self.base)
        receipt = "<code>evidence/receipts/tool-a-smoke-20990305.json</code> "
        evidence = html[html.index('id="overview-evidence"'):]
        self.assertIn(receipt + "<small>registry reference, not opened</small>", evidence)
        self.assertNotIn(receipt + "<small>read</small>", evidence)
        workers = html[html.index('id="ov-workers"'):html.index('id="ov-workers"') + 20000]
        self.assertIn(receipt + "<small>2099-03-05, newest of 2 registered; registry reference, not opened</small>", workers)


class PendingTests(OverviewCase):
    def test_missing_sources_render_pending_with_their_trigger_and_the_receipt_lists_them(self):
        fixture = Fixture(self.base, ws2=False, rows=False, cc_now=None)
        result, html = fixture.build(self.base)
        source_map = json.loads((HERE / "overview_sources.json").read_text())["sources"]
        for key in ("feeds_convergence", "strategies_convergence", "finalize_rows", "cc_now", "cc_floor_prep", "cc_changelog", "cc_slots",
                    "finalize_plan", "finalize_f1", "finalize_f2"):
            self.assertIn(key, result["pending"])
            self.assertIn(source_map[key]["trigger"], html)
        self.assertIn("final_stack", result["present"])
        self.assertEqual({row["id"]: row["status"] for row in result["sources"]}["cc_now"], "pending")
        self.assertIn("CONVERGENCE-WS5-20261015.md", html)
        self.assertNotIn("Traceback", html)

    def test_the_ws2_record_renders_as_a_sanitized_projection(self):
        fixture = Fixture(self.base)
        data = DATA.model(fixture.root, fixture.state, commit="0" * 40)["feeds"]
        self.assertEqual(data["caption"], "The early fixture candidates cost $0.")
        self.assertEqual(data["table"]["header"], ["#", "Signal (feed we hold)", "Leads or lags", "Replay", "False-alarm profile"])
        self.assertEqual(data["table"]["rows"], [["1", "fixture signal one", "leads by fixture", None, "few fixture flags"],
                                                 ["2", "fixture signal two", "lags.", "Derive", "noisy fixture"]])
        self.assertEqual(data["points"]["baseline"], {"lead": "Every fixture list lags by construction.", "sentences": ["Lists are a baseline that fixture signals must beat."], "rows": []})
        self.assertEqual(data["points"]["lagging"]["sentences"], ["fixture pause; fixture prints."])
        self.assertEqual(data["points"]["gated"], {"lead": "Paid and conditional; no purchase until a measured gap justifies it", "sentences": [],
                                                   "rows": ["Fixture vendor A: $1 a month", "Fixture vendor B: no API"]})
        self.assertEqual(data["gaps"], [{"name": "The fixture connection allowance", "sentences": ["A whole-fixture capture needs its own connection.", "Its capacity is unmeasured."]},
                                        {"name": "Fixture entitlement checks", "sentences": []}])
        _, html = fixture.build(self.base)
        section = html[html.index('id="ov-feeds"'):html.index('id="ov-strategies"')]
        source_map = json.loads((HERE / "overview_sources.json").read_text())["sources"]
        for text in ("No measured winner yet.", source_map["feeds_battery"]["trigger"], "<code>CONVERGENCE-WS2-20261014.md</code> (private record, cited by name)",
                     "Withheld: it cites a path, digest or line", "<li><strong>Fixture entitlement checks.</strong></li>"):
            self.assertIn(text, section)
        for text in ("/var/tmp/fixture", "abc1234d", "beef1234", "probe.py", "paper-x", "(above)", "step one", "Every row is a test candidate"):
            self.assertNotIn(text, section)

    def test_the_ws2_addendum_renders_its_entitlement_results_by_name(self):
        fixture = Fixture(self.base)
        directory = fixture.state / STATE_DIR / "ranked-feeds-20261014"
        (directory / "CONVERGENCE-WS2-20261014.addendum-01.md").write_text(ADDENDUM)
        data = DATA.model(fixture.root, fixture.state, commit="0" * 40)["feeds"]
        self.assertEqual(data["addendum"]["results"], [
            {"subject": "Fixture statuses entitlement", "sentences": ["SETTLED, confirmed."]},
            {"subject": "Fixture overnight coverage", "sentences": ["SETTLED, no overnight history.", "Row 9's overnight part is therefore a fixture forward capture only."]},
            {"subject": "Fixture BOATS entitlement", "sentences": ["SETTLED, real-time confirmed."]},
            {"subject": "FIXTURE-OPRA", "sentences": ["historical access confirmed.", "Real-time is NOT yet proven; the one-shot fixture check settles it."]}])
        result, html = fixture.build(self.base)
        self.assertIn("feeds_addendum", result["present"])
        section = html[html.index('id="ov-feeds"'):html.index('id="ov-strategies"')]
        for text in ("<code>CONVERGENCE-WS2-20261014.addendum-01.md</code> (private record, cited by name)",
                     "<li><strong>Fixture statuses entitlement:</strong> SETTLED, confirmed.</li>",
                     "<li><strong>Fixture BOATS entitlement:</strong> SETTLED, real-time confirmed.</li>",
                     "<li><strong>FIXTURE-OPRA:</strong> historical access confirmed. Real-time is NOT yet proven; the one-shot fixture check settles it.</li>"):
            self.assertIn(text, section)
        for text in ("probe-1.json", "abcdef12", "1234abcd", "fixture-opra.json", "fixture-paper", "3 of 90", "5 of 5", "The server said ok", "Effect:"):
            self.assertNotIn(text, section)
        # Only the exact path the source map names is read: an unlisted later addendum changes nothing.
        (directory / "CONVERGENCE-WS2-20261014.addendum-02.md").write_text(ADDENDUM.replace("Fixture statuses entitlement", "Unlisted subject"))
        _, again = fixture.build(self.base)
        self.assertNotIn("Unlisted subject", again)
        self.assertIn("Fixture statuses entitlement", again)

    def test_the_ws5_record_renders_the_family_caveats_ablations_and_sizing(self):
        fixture = Fixture(self.base)
        path = fixture.state / f"{STATE_DIR}/extreme-mover-strategies-20261014/CONVERGENCE-WS5-20261015.md"
        path.parent.mkdir(parents=True)
        path.write_text(WS5)
        data = DATA.model(fixture.root, fixture.state, commit="0" * 40)["strategies"]
        self.assertEqual(data["family"], {"lead": "The one strict shortlist family is the fixture breakout on the top fixture names",
                                          "caveats": ["Commission was $0.01/share.", "There was no sealed out-of-sample test and no fixture slippage model.",
                                                      "The fixture recreation covers 2001 only, inside the sample."], "withheld_caveats": 0})
        self.assertEqual(data["ablations"], {"lead": "The other fixture templates lack results", "intro": "They enter only as on/off ablations of the fixture row:",
                                             "rows": ["Fixture filter one", "A fixture gate"]})  # the cited digest aside is dropped
        self.assertEqual(data["sizing"], {"lead": "Selector and sizing (fixture)", "rows": ["Eligibility before fixture ranking"]})
        result, html = fixture.build(self.base)
        self.assertIn("strategies_convergence", result["present"])
        section = html[html.index('id="ov-strategies"'):html.index('id="ov-workers"')]
        for text in ("No live result; replication next.", "<h3>Evidence caveats</h3>", "<h3>Ablations</h3>", "<h3>Selector and sizing (fixture)</h3>",
                     "<code>CONVERGENCE-WS5-20261015.md</code> (private record, cited by name)"):
            self.assertIn(text, section)
        for text in ("doi:10.0000", "/var/tmp/fixture", "cafe1234", "account-level", "not this"):
            self.assertNotIn(text, section)

    def test_a_present_result_record_replaces_the_plain_statement(self):
        fixture = Fixture(self.base)
        for relative in ("ranked-feeds-20261014/BATTERY-WS2-20261014.md", "extreme-mover-strategies-20261014/REPLICATION-WS5-20261015.md",
                         "extreme-mover-strategies-20261014/CONVERGENCE-WS5-20261015.md"):
            path = fixture.state / STATE_DIR / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(WS5 if "CONVERGENCE" in relative else "# fixture result\n")
        result, html = fixture.build(self.base)
        self.assertIn("feeds_battery", result["present"])
        self.assertIn("Measured battery result: <code>BATTERY-WS2-20261014.md</code> (private record, cited by name).", html)
        self.assertIn("Replication record: <code>REPLICATION-WS5-20261015.md</code> (private record, cited by name).", html)
        for text in ("No measured winner yet.", "No live result; replication next."):
            self.assertNotIn(text, html)


    def test_claude_code_shows_the_run_pin_the_proposed_pin_the_changelog_counts_and_the_slots(self):
        stack = final_stack()
        stack["runs"].append({"id": "claude-code", "pin": "9.9.1", "source": "manifests/stack.json#/components/3"})
        fixture = Fixture(self.base, stack=stack)
        write(fixture.state, "coordination/cc-native-practice-20261009/floor-2300-20261014/FLOOR-2300-prep-20261014.md", PREP)
        write(fixture.state, "coordination/cc-native-practice-20261009/floor-2300-20261014/changelog-2.1.296-2.1.300.md", CHANGELOG)
        write(fixture.root, ".claude/skills/claude-native-practice/reference/slots.json", json.dumps(SLOTS))
        data = DATA.model(fixture.root, fixture.state, commit="0" * 40)["claude_code"]
        self.assertEqual(data["client"]["current"]["pin"], "9.9.1")
        self.assertEqual({key: data["client"]["proposed"][key] for key in ("version", "commit", "carried")}, {"version": "9.9.2", "commit": "c" * 40, "carried": False})
        self.assertEqual(data["changelog"]["versions"], [
            {"version": "9.9.2", "counts": {"Added": 5, "Fixed": 1, "Changed": 1}, "other": 1, "items": ["Added fixture alpha…", "Added fixture beta", "Added fixture epsilon"]},
            {"version": "9.9.1", "counts": {"Added": 0, "Fixed": 1, "Changed": 0}, "other": 0, "items": ["Fixed fixture bug two"]}])
        self.assertEqual(data["slots"]["rows"], [{"slot": "slot-a", "status": "trial", "default": "Fixture default A…", "client_version": "9.9.1"},
                                                 {"slot": "slot-b", "status": "default", "default": "Fixture default B", "client_version": "9.9.2"}])
        result, html = fixture.build(self.base)
        for key in ("cc_floor_prep", "cc_changelog", "cc_slots"):
            self.assertIn(key, result["present"])
        section = html[html.index('id="ov-claude-code"'):html.index('id="ov-github"')]
        commit = "c" * 40
        for text in (f'<code title="{commit}">{commit[:12]}</code>: proposed, lands with its pin PR.', "<code>FLOOR-2300-prep-20261014.md</code> (private record, cited by name)",
                     "CHANGELOG delta 9.9.1 to 9.9.2", "2 slots, 1 default, 1 trial", "<code>slot-a</code>"):
            self.assertIn(text, section)
        for text in ("e" * 64, "d" * 40, ".fixture/x.md"):
            self.assertNotIn(text, section)
        stack["runs"][-1]["pin"] = "9.9.2"  # final-stack.json now carries the prepared pin
        write(fixture.root, "catalogs/landscape/final-stack.json", json.dumps(stack))
        _, html = fixture.build(self.base)
        self.assertIn("9.9.2 has landed as the run pin.", html)
        self.assertNotIn("proposed, lands with its pin PR", html)

    def test_finalize_all_shows_the_waves_the_f1_counts_and_the_f2_summary(self):
        fixture = Fixture(self.base)
        write(fixture.state, f"{STATE_DIR}/finalize-all-20261014/PLAN-finalize-all-20261014.md", PLAN)
        write(fixture.state, "coordination/ns2604-coop/work-20261012/finalize-f1-20261014/INDEX.json", json.dumps(F1_INDEX))
        write(fixture.state, "coordination/cc-native-practice-20261009/finalize-f2-20261014/F2-claude-side-20261014.md", F2)
        data = DATA.model(fixture.root, fixture.state, commit="0" * 40)["repos"]["finalize"]
        self.assertEqual(data["plan"]["waves"], [{"id": "F1", "title": "Fixture receipts", "trigger": "inputs exist now."},
                                                 {"id": "F2", "title": "Fixture invoke", "trigger": "#9001 lands, then the fixture follow-up lands."},
                                                 {"id": "F3", "title": "Fixture no trigger", "trigger": None}])
        # A pass meets the plan only at the exact run pin; the split keeps a version-only pin and a preview apart.
        self.assertEqual((data["f1"]["arms"], data["f1"]["counts"]),
                         (6, {"passed at the exact run pin": 1, "passed, run pin not yet bound": 1, "passed, preview assembly": 1,
                              "failed": 1, "not started": 1, "running": 1}))
        self.assertEqual(data["f2"]["groups"], [{"label": "Receipts", "count": 2}, {"label": "Findings", "count": 2}])
        _, html = fixture.build(self.base)
        section = html[html.index('id="ov-repos"'):html.index('id="overview-evidence"')]
        for text in ("<strong>F2 Fixture invoke.</strong> Starts when: #9001 lands, then the fixture follow-up lands.", "6 arms: 1 passed at the exact run pin; 1 passed, run pin not yet bound; 1 passed, preview assembly; 1 failed; 1 not started; 1 running.",
                     "<li>Receipts: 2</li>", "<code>F2-claude-side-20261014.md</code> (private record, cited by name)"):
            self.assertIn(text, section)

    def test_each_study_names_its_arms_workers_model_families_and_judges_without_a_winner(self):
        fixture = Fixture(self.base)
        write(fixture.state, f"{STATE_DIR}/ranked-feeds-20261014/README.md", ARMS)
        write(fixture.state, f"{STATE_DIR}/ranked-feeds-20261014/CONVERGENCE-WS2-20261014.addendum-01.md", ADDENDUM)
        studies = {item["label"]: item for item in DATA.model(fixture.root, fixture.state, commit="0" * 40)["evidence"]["studies"]}
        ws2 = studies["WS2 data feeds for early entry"]
        self.assertEqual(ws2["arms"]["rows"], [{"worker": "FixtureFlow", "model": None}, {"worker": "Fixture Codex", "model": "GPT family (gpt-9-fixture)"},
                                               {"worker": "fixture-claude", "model": "Claude family (Opus 9.9)"}, {"worker": "Fixture Researcher", "model": None}])
        self.assertEqual(ws2["judges"], ["Claude-family judge (Opus 9.9)", "GPT-family judge (gpt-9-fixture xhigh)"])
        self.assertEqual((ws2["result"], ws2["claim"]), ("No measured winner yet.", "It claims no fixture return and no measured winner."))
        self.assertEqual({key: ws2["addendum"][key] for key in ("producer", "model", "kind")},
                         {"producer": "fixture-lane", "model": None, "kind": "All four results are author-run measurements with receipts."})
        self.assertEqual(studies["WS5 extreme-mover strategies"]["record"]["status"], "pending")
        _, html = fixture.build(self.base)
        section = html[html.index('id="overview-evidence"'):html.index('id="ov-claude-code"')]
        for text in ("Converged by 2 blind judges: Claude-family judge (Opus 9.9) and GPT-family judge (gpt-9-fixture xhigh).",
                     "<strong>No measured winner yet.</strong>", "not stated in the record", "measured by fixture-lane; model not stated in the record."):
            self.assertIn(text, section)
        for text in ("api-9", "run.x", ".config", "tools/fixture", "/var/tmp/fixture", "abc1234d", "fixture-paper"):
            self.assertNotIn(text, section)


class QueueTests(OverviewCase):
    def test_cc_now_queue_and_a_pending_main_ci(self):
        _, html = Fixture(self.base).build(self.base)
        for text in ("#9001", "abc12345", "fixture review state", "fixture gate", "#9002 fixture landing item", "#9003 second fixture item"):
            self.assertIn(text, html)
        self.assertIn("In review (1)", html)
        self.assertIn("From <code>cc-now.json</code> (private record, cited by name), updated 2099-01-01T00:00:00Z.", html)
        self.assertIn("Landing queue (2)", html)
        self.assertIn("the command center adds a main_ci entry to its current view", html)
        self.assertNotIn("<dt>Record</dt>", html[html.index('id="ov-github"'):])  # the section line already names cc-now.json

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
        self.assertEqual({entry["section"] for entry in document["sources"].values()}, set(DATA.SECTIONS))
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

    def test_overview_policy_is_exact_paths_only_and_refuses_symlinked_records(self):
        policy = json.loads((HERE / "source_policy.json").read_text())
        self.assertNotIn("overview_families", policy)
        with tempfile.TemporaryDirectory() as base:
            base = Path(base)
            family = {"overview_finalize_rows": {"root": "state", "directory": f"{STATE_DIR}/finalize-all-20261014", "prefix": "ROWS-", "suffix": ".md"}}
            for name, change in (("final-stack", lambda doc: doc["overview"]["overview_registry"].append({"root": "repo", "path": "catalogs/landscape/final-stack.json"})),
                                 ("families", lambda doc: doc.update(overview_families=family)),
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
            (directory / "ROWS-252babe4.md").symlink_to(base / "target.md")
            with self.assertRaises(POLICY.SourcePolicyError):
                reads.read("overview_finalize_rows", directory / "ROWS-252babe4.md")

    def test_a_file_beside_a_granted_record_is_refused_however_it_is_named(self):
        # Astra's reproduction at 0a87d376: a family grant admitted ROWS-unreviewed.md with no exact grant.
        with tempfile.TemporaryDirectory() as base:
            reads = POLICY.OverviewReads(ROOT, Path(base) / "state")
            directory = Path(base) / "state" / STATE_DIR / "finalize-all-20261014"
            directory.mkdir(parents=True)
            for name in ("ROWS-unreviewed.md", "ROWS-252babe4.md.bak", "notes.md"):
                (directory / name).write_text("| layer |\n|---|\n")
                with self.subTest(name=name), self.assertRaises(POLICY.SourcePolicyError):
                    reads.read("overview_finalize_rows", directory / name)
            (directory / "ROWS-252babe4.md").write_text("| layer |\n|---|\n")
            raw, _ = reads.read("overview_finalize_rows", directory / "ROWS-252babe4.md")
            self.assertEqual(raw, b"| layer |\n|---|\n")

    def test_every_overview_grant_is_declared_by_the_source_map_and_no_more(self):
        policy = json.loads((HERE / "source_policy.json").read_text())
        with tempfile.TemporaryDirectory() as state:
            document, _, _, _ = DATA.load_source_map(ROOT, Path(state))
        declared = {(entry["role"], entry["root"], entry["path"]) for entry in document["sources"].values() if entry["role"].startswith("overview_")}
        granted = {(role, record["root"], record["path"]) for role, records in policy["overview"].items() for record in records}
        self.assertEqual(declared, granted)

class MarkdownTests(unittest.TestCase):
    def test_tables_match_a_column_by_name_or_prefix_and_keep_their_heading(self):
        table = DATA.table_with_column(WS2, "Signal")
        self.assertEqual(table["header"][:3], ["#", "Signal (feed we hold)", "Leads or lags"])
        self.assertEqual(table["heading"], "Converged by both judges (fixture note)")
        self.assertEqual(len(table["rows"]), 2)
        self.assertIsNone(DATA.table_with_column(WS2, "Strategy"))
        self.assertEqual(DATA.plain("**bold** `code` [label](https://example.invalid)"), "bold code label")

    def test_points_keep_their_leads_and_sentences_drop_paths_digests_lines_and_labels(self):
        heading, points = DATA.md_points(WS2, "Converged")
        self.assertEqual(heading, "Converged by both judges (fixture note)")
        self.assertEqual([point["lead"] for point in points], ["Every fixture list lags by construction.", "Fixture replay needs capture.", "The early fixture candidates cost $0.",
                                                             "Lagging or conditioning only, not entry rows", "Paid and conditional; no purchase until a measured gap justifies it"])
        self.assertEqual([point["has_table"] for point in points], [False, False, True, False, False])
        text = "Kept. See /var/tmp/x/y.md for it. Digest abc1234f here. A probe.py:12 line. Named paper-z slot. Plain end (above)."
        self.assertEqual(DATA.sentences(text, ["paper"]), ["Kept.", "Plain end."])


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

    def test_overview_only_never_overwrites_the_refresh_receipt(self):
        # The Architecture refresh rejects any other receipt kind, so a default --overview-only run that wrote the refresh
        # receipt would leave the next full refresh UNREPORTED (the defect #1122 fixed for --layer-pages-only).
        with tempfile.TemporaryDirectory() as base:
            state, output = Path(base) / "state", Path(base) / "served"
            refresh = state / "research/fullspeed-20261008/g5-stars-gap/local-pages/refresh-receipt.json"
            refresh.parent.mkdir(parents=True)
            refresh.write_text('{"schema": "full refresh"}\n')
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = PAGES.main(["--overview-only", "--output-dir", str(output), "--state-root", str(state)])
            self.assertEqual(code, 0)
            self.assertEqual(refresh.read_text(), '{"schema": "full refresh"}\n')
            written = refresh.parent / "overview/overview-receipt.json"
            self.assertEqual(json.loads(stdout.getvalue())["receipt"], str(written))
            self.assertEqual(json.loads(written.read_text())["schema"], DATA.SCHEMA)
            self.assertTrue((refresh.parent / "architecture/layer-pages-receipt.json").exists())
            named = Path(base) / "elsewhere/refresh-receipt.json"
            with redirect_stdout(io.StringIO()), unittest.mock.patch("sys.stderr", io.StringIO()), \
                    self.assertRaises(SystemExit) as raised:
                PAGES.main(["--overview-only", "--output-dir", str(output), "--state-root", str(state), "--receipt", str(named)])
            self.assertEqual(raised.exception.code, 2)
            self.assertFalse(named.exists())

    def test_navigation_lists_the_overview(self):
        html = PAGES.document("index", "Home", "", "scope", "", "2099-01-01T00:00:00Z", "a" * 64, []).decode()
        self.assertIn('href="overview.html"', html)
        overview = PAGES.document("overview", "Overview", "", "scope", "", "2099-01-01T00:00:00Z", "a" * 64, []).decode()
        self.assertIn('href="#overview-evidence"', overview)


class MicroFixTests(OverviewCase):
    """The CC FULL micro and the local review at 0a87d376; each test failed on that commit's modules."""

    def test_the_rows_record_is_the_one_the_source_map_names_never_a_newer_or_higher_name(self):
        # The CC micro's P2-1 and the local review: a name carries no order. The source map's exact path is the pointer.
        fixture = Fixture(self.base, rows=False)
        write(fixture.state, f"{STATE_DIR}/finalize-all-20261014/ROWS-252babe4.md", ROWS_NEW)
        write(fixture.state, f"{STATE_DIR}/finalize-all-20261014/ROWS-ffffffff.md", ROWS_OLD)  # later and higher, unlisted
        data = DATA.model(fixture.root, fixture.state, commit="0" * 40)["repos"]
        self.assertEqual(data["rows_record"], "ROWS-252babe4.md")
        alpha = next(row for group in data["groups"] for row in group["rows"] if row["layer"] == "foundation/alpha")
        self.assertEqual(alpha["next_action"], ["fixture next action"])

    def test_a_layer_only_the_finalize_all_record_lists_is_shown_with_its_state(self):
        fixture = Fixture(self.base, rows=False)
        write(fixture.state, f"{STATE_DIR}/finalize-all-20261014/ROWS-252babe4.md",
              ROWS_NEW + "| foundation/omega | unswept | - | F5 delta sweep -> F4 adjudication | - |\n")
        data = DATA.model(fixture.root, fixture.state, commit="0" * 40)["repos"]
        omega = next(row for group in data["groups"] for row in group["rows"] if row["layer"] == "foundation/omega")
        self.assertEqual((omega["rows_only"], omega["in_catalog"], omega["status"], omega["next_action"]),
                         (True, False, "unswept", ["F5 delta sweep -> F4 adjudication"]))
        self.assertEqual(data["counted"], {"catalog": 3, "planned": 1, "rows_only": 1})
        _, html = fixture.build(self.base)
        section = html[html.index('id="ov-repos"'):html.index('id="overview-evidence"')]
        self.assertIn("3 catalog layers, 1 planned outside the catalog files and 1 listed only in the finalize-all record.", section)
        self.assertIn("in the finalize-all record only, not yet in the catalog file", section)
        self.assertIn("F5 delta sweep -&gt; F4 adjudication", section)
        # The fixture's catalog layers share one state, so the State column is dropped and the record's own state must
        # be said in the layer's row (the Astra and local-review P2 at 487fc280c).
        self.assertIn("ov-shared", section)
        at = section.index('title="foundation/omega"')
        row = section[section.rindex("<tr", 0, at):section.index("</tr>", at)]
        self.assertIn("in the finalize-all record only, not yet in the catalog file; unswept", row)

    def test_a_scheduled_check_is_said_as_its_readiness_trigger_never_a_date(self):
        fixture = Fixture(self.base)
        directory = fixture.state / STATE_DIR / "ranked-feeds-20261014"
        dated = ADDENDUM.replace("the one-shot fixture check settles it", "the one-shot fixture-check-x at 2099-01-01 14:00Z settles it")
        self.assertNotEqual(dated, ADDENDUM)
        (directory / "CONVERGENCE-WS2-20261014.addendum-01.md").write_text(dated)
        data = DATA.model(fixture.root, fixture.state, commit="0" * 40)["feeds"]
        opra = next(item for item in data["addendum"]["results"] if item["subject"] == "FIXTURE-OPRA")
        self.assertIn("Real-time is NOT yet proven; it settles at the first regular-hours check after its run.", opra["sentences"])
        _, html = fixture.build(self.base)
        self.assertNotIn("2099-01-01 14:00Z", html)

    def test_a_cited_or_withheld_caveat_never_becomes_a_no_caveat_claim(self):
        fixture = Fixture(self.base)
        directory = fixture.state / STATE_DIR / "extreme-mover-strategies-20261014"
        cases = {
            "kept": ("   - Evidence: No out-of-sample validation; see study.md.\n", ["Evidence: No out-of-sample validation."], 0),
            "withheld": ("   - Evidence: in-sample result kept at /var/tmp/fixture/study.md.\n", [], 1),
        }
        for name, (line, caveats, withheld) in cases.items():
            with self.subTest(case=name):
                record = ("# Fixture\n\n## Converged by both judges\n1. **The one shortlist family is a synthetic strategy.**\n" + line)
                directory.mkdir(parents=True, exist_ok=True)
                (directory / "CONVERGENCE-WS5-20261015.md").write_text(record)
                family = DATA.model(fixture.root, fixture.state, commit="0" * 40)["strategies"]["family"]
                self.assertEqual((family["caveats"], family["withheld_caveats"]), (caveats, withheld))
                _, html = fixture.build(self.base)
                section = html[html.index('id="ov-strategies"'):html.index('id="ov-workers"')]
                self.assertNotIn("states no caveat", section)
                self.assertNotIn("No caveat was found", section)
                if withheld:
                    self.assertIn("1 more caveat withheld from this projection because it cites a path, digest or line", section)

    def test_a_worker_without_a_source_names_its_readiness_trigger(self):
        fixture = Fixture(self.base)
        _, html = fixture.build(self.base)
        section = html[html.index('id="ov-workers"'):html.index('id="ov-repos"')]
        for text in ("Ready when its fence is accepted (#1120).", "Ready when its first F1 paired-sample receipt is registered after the fence is accepted.",
                     "Ready when a registered receipt or runtime profile names the GPT kit.",
                     "Ready when the finalize-all F1 receipts pull request registers the API-slot runs&#x27; receipts."):
            self.assertIn(text, section)

    def failing(self, module, function, error):
        stub, real = type("Stub", (), {function: staticmethod(lambda *args, **kwargs: (_ for _ in ()).throw(error))}), PAGES.load_local
        return unittest.mock.patch.object(PAGES, "load_local", side_effect=lambda name, *rest: stub if name == module else real(name, *rest))

    def test_a_full_refresh_publishes_an_overview_placeholder_when_the_overview_fails(self):
        for previous in (False, True):
            with self.subTest(previous=previous), tempfile.TemporaryDirectory() as base:
                output = Path(base) / "served"
                output.mkdir()
                if previous:
                    (output / "overview.html").write_text("previous page\n")
                outputs, receipt_doc = {}, {"outputs": {}}
                with self.failing("overview_data", "build_overview_page", ValueError("bad")):
                    PAGES.refresh_overview(ROOT, Path(base) / "state", output, Path(base) / "custody/refresh-receipt.json",
                                           "2099-01-01T00:00:00Z", "a" * 64, outputs, receipt_doc)
                status = receipt_doc["overview"]
                self.assertEqual((status["status"], status["reason"]), ("UNREPORTED", "Overview unavailable (ValueError)"))
                if previous:
                    self.assertEqual((status["page_status"], outputs), ("previous page retained without a new observation", {}))
                else:
                    self.assertEqual(status["page_status"], "unreported placeholder")
                    placeholder = outputs["overview.html"].decode()
                    self.assertIn("UNREPORTED", placeholder)
                    self.assertIn('id="overview-evidence"', placeholder)

    def test_overview_only_renders_the_overview_when_the_layer_pages_fail(self):
        with tempfile.TemporaryDirectory() as base:
            output, receipt = Path(base) / "served", Path(base) / "custody/overview.json"
            stdout = io.StringIO()
            with self.failing("architecture_builder", "build_layer_pages", ValueError("bad")), redirect_stdout(stdout):
                code = PAGES.main(["--overview-only", "--output-dir", str(output), "--receipt", str(receipt), "--state-root", str(Path(base) / "state")])
            self.assertEqual(code, 1)
            summary = json.loads(stdout.getvalue())
            self.assertEqual((summary["layer_pages"], summary["layer_pages_status"]), ([], "UNREPORTED (layer pages unavailable: ValueError)"))
            self.assertTrue((output / "overview.html").exists())
            for page in ("architecture-foundation", "architecture-north-star"):
                self.assertIn("UNREPORTED", (output / f"{page}.html").read_text())


if __name__ == "__main__":
    unittest.main()
