"""Public loss-halt guidance must agree with the native, offline safety fixture.

Source contract: native-agent-stack@993cc890b3ff3fc95fa7cdba51edd726565f9ace,
blueprints/us-equities/adaptive-paper/safety.py:1003-1034 and :1065-1092.
The BUY branches refuse risk halts; SELL retains owned-quantity validation.
No broker, credentials, external state or vendor connection is involved.
"""
from pathlib import Path
import re
import unittest

try:  # Package runner and root test discovery both execute this module.
    from . import test_adaptive_paper_safety as native_safety
except ImportError:
    import test_adaptive_paper_safety as native_safety


PAGE = Path(__file__).resolve().parents[1] / "docs/trading-handbook/portfolio-sizing.md"


class HandbookSizingTests(unittest.TestCase):
    def test_loss_halts_block_entries_without_blocking_owned_exits(self):
        for halt in ("gross_loss_cap_reached", "drawdown_cap_reached"):
            with self.subTest(halt=halt):
                fixture = native_safety.SafetyTests(
                    "test_wide_quote_values_held_loss_but_does_not_block_owned_exit")
                fixture.setUp()
                try:
                    fixture.reserve()
                    fixture.fill()
                    if halt == "drawdown_cap_reached":
                        fixture.ledger.mark_to_market(
                            [fixture.quote(bid="120", ask="120.01")], fixture.now)
                        quote = fixture.quote(bid="95", ask="95.01")
                        price = "94.99"
                    else:
                        quote = fixture.quote(bid="74", ask="74.01")
                        price = "73.99"
                    state = fixture.ledger.mark_to_market([quote], fixture.now)
                    self.assertEqual(state.halted_reason, halt)
                    with self.assertRaisesRegex(native_safety.s.SafetyError, halt):
                        fixture.reserve("new-entry", price=str(quote.ask), quote=quote)
                    fixture.reserve("owned-exit", side="sell", price=price, quote=quote)
                    fixture.validate("owned-exit", quote=quote)
                finally:
                    fixture.tearDown()
                    fixture.doCleanups()

        guidance = re.sub(r"\s+", " ", PAGE.read_text(encoding="utf-8"))
        self.assertNotRegex(
            guidance, r"session,? loss and cleanup bounds still apply to risk-reducing exits",
            "The handbook must not make loss ceilings block owned exits")
        self.assertIn("Loss and drawdown halts block new entries;", guidance)
        self.assertIn("owned-position exits remain permitted subject to the quantity, "
                      "price, quote, session and cleanup checks.", guidance)
        self.assertIn("safety.py#L1003-L1034", guidance)
        self.assertIn("safety.py#L1065-L1092", guidance)


if __name__ == "__main__":
    unittest.main()
