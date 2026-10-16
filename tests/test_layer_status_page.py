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
        self.assertIn("run pin: c", missing)
        self.assertIn("E2E at current pin: b, c", missing)
        self.assertIn("invoke evidence", missing)
        self.assertIn("multi-angle record", missing)
        self.assertIn("2 carried survivors", missing)
        self.assertEqual(self.rows["foundation/model-routes"]["missing"], ["no completed sweep"])

    def test_winners_show_their_run_pins(self):
        self.assertEqual(self.rows["us-equities/backtesting-engine"]["winners"], ["b@abcdef012345", "c@no run pin"])

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
        self.assertEqual(len(dict(page.TIERS)["T1-harness"]), 18)


class FreshnessTests(unittest.TestCase):
    def test_checked_in_page_matches_final_stack(self):
        built = page.render(page.load(ROOT / page.SOURCE))
        self.assertEqual((ROOT / page.OUTPUT).read_text(encoding="utf-8"), built)


if __name__ == "__main__":
    unittest.main()
