"""Tests for scripts/layer_status_page.py: each layer of final-stack.json gets one state (FINAL, TRIAL or GAP), the
missing evidence follows the four FINAL conditions of docs/decisions/2026-10-11-layer-resolution-protocol.md, the
trading-critical layers come first, and the checked-in page is fresh."""

from __future__ import annotations

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
        self.assertIn("invoke evidence", missing)
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

    def test_tradingview_is_a_t1_trading_initial_sweep_after_catalysts_sentiment(self):
        self.assertEqual([(tier, after) for tier, after, _ in page.SWEEPS_WITHOUT_ROW],
                         [("T1-trading", "us-equities/catalysts-sentiment")])
        built = page.render(WAVE_STACK)
        note = built.index("TradingView automation")
        self.assertGreater(note, built.index("`us-equities/catalysts-sentiment`"))
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

    def test_condition_3_needs_an_e2e_receipt_bound_at_the_run_pin(self):
        # drifted's receipt is bound at its run pin, so only condition 2 fails for it; unbound has no final_evidence.
        self.assertIn("E2E at run pin: unbound", self.row["missing"])

    def test_pins_print_whole(self):
        self.assertEqual(self.row["winners"],
                         ["bound@2.1.300", "drifted@0.51.0", "unbound@985ef30 with patches"])


class TierInventoryTests(unittest.TestCase):
    def test_every_tier_layer_exists_in_final_stack(self):
        stack = page.load(ROOT / page.SOURCE)
        layers = {f'{item["catalog"]}/{item["layer_id"]}' for item in stack["layers"]}
        named = {key for _, keys in page.TIERS for key in keys}
        self.assertEqual(named - layers, set())


class FreshnessTests(unittest.TestCase):
    def test_checked_in_page_matches_final_stack(self):
        stack = page.load(ROOT / page.SOURCE)
        built = page.render(stack, page.angle_records(stack, ROOT))
        self.assertEqual((ROOT / page.OUTPUT).read_text(encoding="utf-8"), built)


if __name__ == "__main__":
    unittest.main()
