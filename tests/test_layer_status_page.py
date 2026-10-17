"""Tests for scripts/layer_status_page.py: each layer of final-stack.json gets one state (FINAL, TRIAL or GAP), the
missing evidence follows the four FINAL conditions of docs/decisions/2026-10-11-layer-resolution-protocol.md, the
trading-critical layers come first, and the checked-in page is fresh."""

from __future__ import annotations

import contextlib
import io
import json
import re
import tempfile
import unittest
from pathlib import Path

from scripts import layer_status_page as page

ROOT = Path(__file__).resolve().parents[1]


def layer(catalog, layer_id, status, winners=(), terminal=None, verdict=None, angles="missing", survivors=(),
          next_action=None):
    return {
        "catalog": catalog, "layer_id": layer_id, "status": status, "terminal_state": terminal,
        "verdict": verdict if verdict is not None else {"status": "recorded", "wave": "w", "next_review": "2026-11-01"},
        "angles": {"status": angles}, "survivors": [{"repository": r} for r in survivors],
        "research": {"next_action": next_action} if next_action else {}, "winners": list(winners),
    }


def winner(component, run=None, host_e2e="true", pin_current="true"):
    return {"component_id": component, "run": run,
            "factors": [{"host_e2e": host_e2e, "pin_current": pin_current}]}


STACK = {
    "checked_at": "2026-10-15",
    "runs": [{"id": "r-a", "pin": "1.2.3"}, {"id": "r-b", "pin": "abcdef0123456789"}],
    "layers": [
        layer("foundation", "zeta", "current", [winner("a", "r-a")], terminal="FINAL", angles="recorded"),
        layer("foundation", "model-routes", "unswept"),
        layer("us-equities", "execution-broker", "no-winner", survivors=("github.com/x/y",)),
        layer("us-equities", "backtesting-engine", "reopened",
              [winner("b", "r-b", pin_current="false"), winner("c", None)], survivors=("s1", "s2"),
              next_action="Freeze the oracles."),
    ],
}


class StateTests(unittest.TestCase):
    def setUp(self):
        self.rows = {r["layer"]: r for r in page.build_rows(STACK)}

    def test_each_layer_gets_one_state(self):
        self.assertEqual(self.rows["foundation/zeta"]["state"], "FINAL")
        self.assertEqual(self.rows["foundation/model-routes"]["state"], "GAP")
        self.assertEqual(self.rows["us-equities/execution-broker"]["state"], "GAP")
        self.assertEqual(self.rows["us-equities/backtesting-engine"]["state"], "TRIAL")

    def test_missing_evidence_follows_the_four_final_conditions(self):
        missing = self.rows["us-equities/backtesting-engine"]["missing"]
        run_pin = [m for m in missing if m.startswith("run pin: ")]
        self.assertEqual(len(run_pin), 1)
        self.assertIn("c (no run pin)", run_pin[0])
        self.assertIn("E2E at run pin: b, c", missing)
        self.assertIn("invoke evidence: b, c", missing)
        self.assertIn("multi-angle record", missing)
        self.assertIn("2 carried survivors", missing)
        self.assertEqual(self.rows["foundation/model-routes"]["missing"], ["no completed sweep"])

    def test_winners_show_their_run_pins(self):
        self.assertEqual(self.rows["us-equities/backtesting-engine"]["winners"], ["b@abcdef0123456789", "c@no run pin"])

    def test_next_action_comes_from_the_record(self):
        self.assertEqual(self.rows["us-equities/backtesting-engine"]["next_action"], "Freeze the oracles.")
        self.assertEqual(self.rows["foundation/model-routes"]["next_action"], "initial sweep scoped to the gap")


WAVE_STACK = {
    "checked_at": "2026-10-16",
    "runs": [],
    "layers": [
        layer("foundation", "zeta", "reopened"),
        layer("us-equities", "judgment-features", "unswept"),
        layer("foundation", "web-research", "reopened"),
        layer("foundation", "durable-memory", "reopened"),
        layer("foundation", "token-efficiency", "reopened"),
        layer("us-equities", "catalysts-sentiment", "unswept"),
        layer("us-equities", "market-data-reference", "reopened"),
        layer("us-equities", "portfolio-risk", "reopened"),
        layer("us-equities", "backtesting-engine", "reopened"),
        layer("us-equities", "execution-broker", "no-winner"),
    ],
}


class OrderTests(unittest.TestCase):
    def test_trading_capability_layers_come_first_then_harness_then_the_rest(self):
        rows = page.build_rows(WAVE_STACK)
        self.assertEqual([r["layer"] for r in rows], [
            "us-equities/execution-broker", "us-equities/backtesting-engine", "us-equities/portfolio-risk",
            "us-equities/market-data-reference", "us-equities/catalysts-sentiment",
            "foundation/token-efficiency", "foundation/durable-memory", "foundation/web-research",
            "foundation/zeta", "us-equities/judgment-features",
        ])
        self.assertEqual([r["tier"] for r in rows], ["T1-trading"] * 5 + ["T1-harness"] * 3 + ["T3"] * 2)

    def test_every_tier_layer_is_named_once(self):
        named = [key for _, keys in page.TIERS for key in keys]
        self.assertEqual(len(named), len(set(named)))
        self.assertEqual(len(dict(page.TIERS)["T1-trading"]), 6)
        self.assertEqual(len(dict(page.TIERS)["T1-harness"]), 19)

    def test_observability_hosting_is_harness_work_after_observation_inference(self):
        harness = dict(page.TIERS)["T1-harness"]
        self.assertEqual(harness.index("us-equities/observability-hosting"),
                         harness.index("foundation/observation-inference") + 1)

    def test_tradingview_continues_1182_in_t1_trading_after_catalysts_sentiment(self):
        self.assertEqual([(tier, after) for tier, after, _ in page.SWEEPS_WITHOUT_ROW],
                         [("T1-trading", "us-equities/catalysts-sentiment")])
        built = page.render(WAVE_STACK)
        note = built.index("TradingView automation")
        self.assertGreater(note, built.index(page._cell("us-equities/catalysts-sentiment")))
        line = built[built.rindex("\n", 0, note) + 1:built.index("\n", note)]
        self.assertIn("#1182", line)
        self.assertNotIn("initial sweep", line.lower())
        self.assertNotIn("Initial sweeps", built)
        self.assertNotIn("| TradingView", built)
        self.assertNotIn("| `TradingView", built)


PIN_STACK = {
    "checked_at": "2026-10-16",
    "runs": [
        {"id": "r-same", "pin": "2.1.300", "pin_parsed": {"commit": None, "version": "2.1.300"}},
        {"id": "r-drift", "pin": "0.51.0", "pin_parsed": {"commit": None, "version": "0.51.0"}},
        {"id": "r-commit", "pin": "985ef30 with patches",
         "pin_parsed": {"commit": "985ef30aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "version": None}},
    ],
    "layers": [{
        **layer("foundation", "native-clients", "reopened", angles="recorded"),
        "angles": {"status": "recorded", "path": "catalogs/landscape/angles/fixture.json"},
        "winners": [
            {**winner("bound", "r-same"), "repository": "https://github.com/x/bound", "verdict_pin": "2.1.300",
             "pin_drift": "same"},
            {**winner("drifted", "r-drift"), "repository": "https://github.com/x/drifted", "verdict_pin": "0.49.0",
             "pin_drift": "differs"},
            {**winner("unbound", "r-commit"), "repository": "https://github.com/x/unbound",
             "verdict_pin": "985ef30aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "pin_drift": "same"},
        ],
    }],
}
PIN_RECORDS = {"catalogs/landscape/angles/fixture.json": {
    "candidates": [
        {"id": "c-bound", "repository": "https://github.com/x/bound", "pin": "2.1.300"},
        {"id": "c-drifted", "repository": "https://github.com/x/drifted", "pin": "0.51.0"},
        {"id": "c-unbound", "repository": "https://github.com/x/unbound",
         "pin": "985ef30aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"},
    ],
    "final_evidence": [
        {"candidate_id": "c-bound", "run_pin": "2.1.300", "e2e_receipt": "evidence/receipts/bound-e2e.json"},
        {"candidate_id": "c-drifted", "run_pin": "0.51.0", "e2e_receipt": "evidence/receipts/drifted-e2e.json"},
    ],
}}


class FinalConditionTests(unittest.TestCase):
    """Conditions 2 and 3 come from the FINAL predicate's own inputs (scripts/final_stack.py enforce_final): a run pin
    whose pin_drift is "same" and whose complete identity matches the verdict pin, and an E2E receipt bound in the angle
    record's final_evidence at that run pin. The component-matrix factors host_e2e and pin_current bind no receipt."""

    def setUp(self):
        self.row = page.build_rows(PIN_STACK, PIN_RECORDS)[0]

    def test_condition_2_reports_a_verdict_pin_that_differs_from_the_run_pin(self):
        self.assertIn("run pin: drifted (verdict 0.49.0, run 0.51.0)", self.row["missing"])

    def test_condition_2_holds_for_a_matching_complete_pin(self):
        run_pin = [m for m in self.row["missing"] if m.startswith("run pin: ")]
        self.assertEqual(run_pin, ["run pin: drifted (verdict 0.49.0, run 0.51.0)"])

    def test_condition_3_without_a_readable_receipt_is_missing(self):
        # No root, so no bound receipt can be read and validated: a binding alone never clears condition 3.
        self.assertIn("E2E at run pin: bound, drifted, unbound", self.row["missing"])

    def test_pins_print_whole(self):
        self.assertEqual(self.row["winners"],
                         ["bound@2.1.300", "drifted@0.51.0", "unbound@985ef30 with patches"])


PINS = {"valid": "a" * 40, "missing": "b" * 40, "failed": "c" * 40, "otherpin": "d" * 40}


def _receipt(name, pin, **fields):
    return {"evidence_class": "native_proven", "repository": f"https://github.com/x/{name}", "pin": pin, **fields}


def _e2e(name, pin, test_exit=0):
    return _receipt(name, pin, kind="upstream_e2e", success=test_exit == 0,
                    upstream_sources=[{"kind": "repo", "repository": f"https://github.com/x/{name}", "pin": pin,
                                       "path": "README.md", "line": 1}],
                    commands=[{"phase": "install", "command": "install", "exit_code": 0},
                              {"phase": "test", "command": "test", "exit_code": test_exit}])


RECEIPT_STACK = {
    "checked_at": "2026-10-16",
    "runs": [{"id": f"r-{n}", "pin": c, "pin_parsed": {"commit": c, "version": None}} for n, c in PINS.items()],
    "layers": [{
        **layer("foundation", "workers", "reopened"),
        "angles": {"status": "recorded", "path": "angles.json"},
        "winners": [{**winner(n, f"r-{n}"), "repository": f"https://github.com/x/{n}", "verdict_pin": c,
                     "pin_drift": "same"} for n, c in PINS.items()],
    }],
}
RECEIPT_RECORDS = {"angles.json": {
    "candidates": [{"id": f"c-{n}", "repository": f"https://github.com/x/{n}", "pin": c} for n, c in PINS.items()],
    "final_evidence": [
        {"candidate_id": "c-valid", "run_pin": PINS["valid"], "e2e_receipt": "r/valid-e2e.json",
         "invoke_receipt": "r/valid-invoke.json"},
        {"candidate_id": "c-missing", "run_pin": PINS["missing"], "e2e_receipt": "r/absent.json",
         "not_invoked_reason": "no lane calls it yet"},
        {"candidate_id": "c-failed", "run_pin": PINS["failed"], "e2e_receipt": "r/failed-e2e.json"},
        {"candidate_id": "c-otherpin", "run_pin": PINS["otherpin"], "e2e_receipt": "r/otherpin-e2e.json",
         "invoke_receipt": "r/otherpin-invoke.json"},
    ],
}}
RECEIPT_FILES = {
    "r/valid-e2e.json": _e2e("valid", PINS["valid"]),
    "r/valid-invoke.json": _receipt("valid", PINS["valid"], kind="invocation", calls=3,
                                    window_start="2026-10-15T00:00:00Z", window_end="2026-10-16T00:00:00Z"),
    "r/failed-e2e.json": _e2e("failed", PINS["failed"], test_exit=1),
    "r/otherpin-e2e.json": _e2e("otherpin", "e" * 40),
    "r/otherpin-invoke.json": _receipt("otherpin", PINS["otherpin"], kind="invocation", calls=0,
                                       window_start="2026-10-15T00:00:00Z", window_end="2026-10-16T00:00:00Z"),
}


class ReceiptValidationTests(unittest.TestCase):
    """A bound receipt counts only when it exists, passed and sits at the winner's complete run pin, and condition 4
    reads the same bound final_evidence: a valid invocation receipt or a recorded not_invoked_reason
    (scripts/final_stack.py enforce_final, conditions 3 and 4)."""

    def setUp(self):
        import json
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        for rel, body in RECEIPT_FILES.items():
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_text(json.dumps(body), encoding="utf-8")
        schema = Path("catalogs/landscape/angles/schema.json")  # check_condition_3 validates against it
        (root / schema).parent.mkdir(parents=True, exist_ok=True)
        (root / schema).write_bytes((ROOT / schema).read_bytes())
        self.missing = page.build_rows(RECEIPT_STACK, RECEIPT_RECORDS, root=root)[0]["missing"]

    def tearDown(self):
        self.tmp.cleanup()

    def test_condition_3_needs_an_existing_passed_receipt_at_the_run_pin(self):
        self.assertIn("E2E at run pin: missing, failed, otherpin", self.missing)

    def test_condition_4_reads_invocation_receipts_and_non_invocation_reasons(self):
        self.assertIn("invoke evidence: failed, otherpin", self.missing)


# GPT FULL read of a3eaa62f, P2: a layer name, winner, pin or next action holding a pipe, a line ending or markup must
# stay literal text inside its own cell. The values are synthetic.
HOSTILE_STACK = {
    "checked_at": "2026-10-16\n\n# SYN heading <b>x</b>",
    "runs": [{"id": "r-h", "pin": "1.0|<b>2</b>"}],
    "layers": [
        layer("foundation", "synthetic|extra\nSYN row", "reopened", [winner("<em>SYN winner</em>", "r-h")],
              next_action="`x` <em>SYN action</em> [a](https://example.com) *b* &amp; \\| c\r\nd"),
    ],
}
# github/cmark-gfm 0.29.0.gfm.13 at 587a12bb54d95ac37241377e6ddc93ea0e45439b: its table scanner reads a backslash before
# an ASCII punctuation character as one escaped character, so only an unescaped pipe ends a cell
# (extensions/ext_scanners.re:32-35); inline parsing then renders each escaped character literally
# (test/spec.txt:5787-5795).
ESCAPED = re.compile(r"\\([!-/:-@\[-`{-~])")


def split_row(row: str) -> list[str]:
    cells, cell = [], ""
    for token in re.findall(r"\\[!-/:-@\[-`{-~]|.", row):
        if token == "|":
            cells.append(cell)
            cell = ""
        else:
            cell += token
    return [c.strip() for c in cells[1:]]


def literal(cell: str) -> str:
    return ESCAPED.sub(r"\1", cell)


class LiteralCellTests(unittest.TestCase):
    def setUp(self):
        self.built = page.render(HOSTILE_STACK)
        self.rows = [line for line in self.built.splitlines() if line.startswith("| 1 |")]

    def test_a_hostile_row_keeps_one_line_and_eight_cells(self):
        self.assertEqual(len(self.rows), 1)
        self.assertEqual(len(split_row(self.rows[0])), 8)
        self.assertEqual(sum(line.startswith("|") for line in self.built.splitlines()), 3)

    def test_hostile_values_render_as_their_literal_text(self):
        cells = [literal(c) for c in split_row(self.rows[0])]
        self.assertEqual(cells[2], "foundation/synthetic|extra SYN row")
        self.assertEqual(cells[5], "<em>SYN winner</em>@1.0|<b>2</b>")
        self.assertEqual(cells[7], "`x` <em>SYN action</em> [a](https://example.com) *b* &amp; \\| c d")

    def test_no_markup_survives_outside_an_escape(self):
        bare = ESCAPED.sub("", "\n".join(line for line in self.built.splitlines() if line.startswith("|")))
        for mark in ("<", ">", "`", "*", "[", "&"):
            self.assertNotIn(mark, bare)
        header = next(line for line in self.built.splitlines() if line.startswith("Generated by"))
        self.assertIn(literal(page._cell(HOSTILE_STACK["checked_at"])), literal(header))
        self.assertNotIn("<b>", ESCAPED.sub("", header))
        self.assertNotIn("\n# SYN heading", self.built)


def _candidate(cid, repository, version, **fields):
    return {"id": cid, "repository": repository, "pin": version, "verdict": "CONVERGED", "provisional": False,
            "a6_comparative": True, **fields}


COVERAGE_STACK = {
    "checked_at": "2026-10-16",
    "runs": [{"id": "r-a", "pin": "1.2.3", "pin_parsed": {"commit": None, "version": "1.2.3"}},
             {"id": "r-b", "pin": "4.5.6", "pin_parsed": {"commit": None, "version": "4.5.6"}}],
    "layers": [{
        **layer("foundation", "coverage-fixture", "reopened", angles="recorded"),
        "angles": {"status": "recorded", "path": "angles/coverage.json"},
        "winners": [
            {**winner("alpha", "r-a"), "repository": "https://github.com/x/alpha", "verdict_pin": "1.2.3",
             "pin_drift": "same"},
            {**winner("beta", "r-b"), "repository": "https://github.com/x/beta", "verdict_pin": "4.5.6",
             "pin_drift": "same"},
        ],
    }],
}


class WinnerCoverageTests(unittest.TestCase):
    """The co-op's local review of f1a97039 and GPT's cumulative micro of a3eaa62f..f1a97039 (P2, the CC's re-ruling of
    2026-10-16): the multi-angle gap clears only when the layer's angle record covers each selected winner as
    enforce_final requires it (final_stack.final_candidate): one candidate for the winner's repository at its complete
    run pin, final-eligible, CONVERGED, non-provisional and with comparative A6."""

    def missing(self, candidates):
        records = {"angles/coverage.json": {"candidates": candidates, "final_evidence": []}}
        return page.build_rows(COVERAGE_STACK, records)[0]["missing"]

    def test_a_record_covering_only_alternatives_leaves_the_gap(self):
        missing = self.missing([_candidate("other", "https://github.com/x/other", "9.9.9")])
        self.assertIn("multi-angle record: alpha, beta", missing)

    def test_a_record_covering_every_winner_clears_the_gap(self):
        missing = self.missing([_candidate("a", "https://github.com/x/alpha", "1.2.3"),
                                _candidate("b", "https://github.com/x/beta", "4.5.6")])
        self.assertFalse([m for m in missing if m.startswith("multi-angle record")])

    def test_wrong_pin_or_unqualified_coverage_leaves_the_winner_uncovered(self):
        for change in ({"pin": "1.2.4"}, {"provisional": True}, {"verdict": "DIVERGED"}, {"a6_comparative": False},
                       {"final_eligible": False}, {"entitlement": {"status": "pending"}}):
            with self.subTest(change=change):
                missing = self.missing([_candidate("a", "https://github.com/x/alpha", "1.2.3", **change),
                                        _candidate("b", "https://github.com/x/beta", "4.5.6")])
                self.assertIn("multi-angle record: alpha", missing)
        missing = self.missing([_candidate("a1", "https://github.com/x/alpha", "1.2.3"),
                                _candidate("a2", "https://github.com/x/alpha", "1.2.3"),
                                _candidate("b", "https://github.com/x/beta", "4.5.6")])
        self.assertIn("multi-angle record: alpha", missing)

    def test_agent_sdks_and_workers_report_their_uncovered_winners(self):
        stack = page.load(ROOT / page.SOURCE)
        rows = {r["layer"]: r for r in page.build_rows(stack, page.angle_records(stack, ROOT), ROOT)}
        self.assertIn("multi-angle record: codex", rows["foundation/agent-sdks"]["missing"])
        self.assertIn("multi-angle record: claude-code, worktrunk", rows["foundation/workers"]["missing"])


class TierInventoryTests(unittest.TestCase):
    def test_every_tier_layer_exists_in_final_stack(self):
        self.assertEqual(page.unknown_tier_layers(page.load(ROOT / page.SOURCE)), set())

    def test_a_renamed_layer_is_reported_not_silently_t3(self):
        # Control: rename one tiered layer in a copy of final-stack.json; the check must name the old key.
        stack = page.load(ROOT / page.SOURCE)
        renamed = [dict(item) for item in stack["layers"]]
        target = next(item for item in renamed if (item["catalog"], item["layer_id"]) == ("us-equities", "portfolio-risk"))
        target["layer_id"] = "portfolio-risk-renamed"
        self.assertEqual(page.unknown_tier_layers({**stack, "layers": renamed}), {"us-equities/portfolio-risk"})


SKILLS_STACK = {
    **WAVE_STACK,
    "coverage": {"skills": [
        {"layer_id": "skills-debug", "lifecycle_task": "debug", "swept": False, "saturation": None},
        {"layer_id": "skills-agent-docs", "lifecycle_task": "agent-docs", "swept": False, "saturation": None},
        {"layer_id": "skills-review", "lifecycle_task": "review", "swept": True, "saturation": None},
    ]},
}


class SkillsCoverageTests(unittest.TestCase):
    """The 13 skills layers of final-stack.json's coverage.skills[] (docs/decisions/2026-10-15-new-wsl-clean-install-plan.md:165-168
    and :182: each a GAP whose next action is an initial sweep scoped to its lifecycle task; T3, after every other layer)."""

    def test_skills_layers_are_gap_rows_in_t3_after_every_other_layer(self):
        rows = page.build_rows(SKILLS_STACK)
        self.assertEqual([r["layer"] for r in rows[-3:]],
                         ["skills/skills-agent-docs", "skills/skills-debug", "skills/skills-review"])
        self.assertEqual(rows[-4]["layer"], "us-equities/judgment-features")
        debug = rows[-2]
        self.assertEqual((debug["tier"], debug["status"], debug["state"], debug["winners"], debug["missing"]),
                         ("T3", "unswept", "GAP", [], ["no completed sweep"]))
        self.assertEqual(debug["next_action"], "initial sweep scoped to the debug lifecycle task")

    def test_a_swept_skills_layer_stays_gap_until_its_verdict(self):
        review = page.build_rows(SKILLS_STACK)[-1]
        self.assertEqual((review["status"], review["state"], review["missing"]), ("swept", "GAP", ["verdict"]))

    def test_the_page_counts_every_layer_and_every_skills_layer(self):
        stack = page.load(ROOT / page.SOURCE)
        rows = page.build_rows(stack, page.angle_records(stack, ROOT), ROOT)
        skills = stack["coverage"]["skills"]
        self.assertEqual(len(rows), len(stack["layers"]) + len(skills))
        keys = {r["layer"] for r in rows}
        self.assertTrue({f'skills/{task["layer_id"]}' for task in skills} <= keys)
        built = page.render(stack, page.angle_records(stack, ROOT), ROOT)
        counts = {state: sum(r["state"] == state for r in rows) for state in ("FINAL", "TRIAL", "GAP")}
        self.assertIn(f"**{len(rows)} layers:** {counts['FINAL']} FINAL, {counts['TRIAL']} TRIAL, {counts['GAP']} GAP.",
                      built)


class FreshnessTests(unittest.TestCase):
    def test_checked_in_page_matches_final_stack(self):
        stack = page.load(ROOT / page.SOURCE)
        built = page.render(stack, page.angle_records(stack, ROOT), ROOT)
        self.assertEqual((ROOT / page.OUTPUT).read_text(encoding="utf-8"), built)

    def _root(self, tmp: str) -> Path:
        root = Path(tmp)
        (root / page.SOURCE).parent.mkdir(parents=True)
        (root / page.SOURCE).write_text(json.dumps(STACK), encoding="utf-8")
        (root / page.OUTPUT).parent.mkdir(parents=True)
        return root

    def test_check_compares_bytes_so_a_crlf_only_change_is_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(tmp)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(page.main(["--root", str(root), "--write"]), 0)
                self.assertEqual(page.main(["--root", str(root), "--check"]), 0)
            output = root / page.OUTPUT
            output.write_bytes(output.read_bytes().replace(b"\n", b"\r\n"))
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(page.main(["--root", str(root), "--check"]), 1)

    def test_write_replaces_the_page_whole_and_leaves_no_temporary_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(tmp)
            (root / page.OUTPUT).write_text("stale\n" * 1000, encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(page.main(["--root", str(root), "--write"]), 0)
                self.assertEqual(page.main(["--root", str(root), "--check"]), 0)
            self.assertEqual(sorted(p.name for p in (root / page.OUTPUT).parent.iterdir()), [Path(page.OUTPUT).name])


if __name__ == "__main__":
    unittest.main()
