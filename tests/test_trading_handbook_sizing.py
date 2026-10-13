"""Public loss-halt guidance must agree with the native, offline safety fixture.

Source contract: native-agent-stack@993cc890b3ff3fc95fa7cdba51edd726565f9ace,
blueprints/us-equities/adaptive-paper/safety.py:1003-1034 and :1065-1092.
The BUY branches refuse risk halts; SELL retains owned-quantity validation.
No broker, credentials, external state or vendor connection is involved.
"""
from pathlib import Path
import hashlib
import json
import re
import unittest

try:  # Package runner and root test discovery both execute this module.
    from . import test_adaptive_paper_safety as native_safety
except ImportError:
    import test_adaptive_paper_safety as native_safety


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "docs/trading-handbook/portfolio-sizing.md"
OVERNIGHT = ROOT / "docs/trading-handbook/boats-overnight-facts.md"
CAPTURE = ROOT / "tests/fixtures/adaptive_paper_citations/us_docs_245-trading_20261013.md"
PROVENANCE = ROOT / "tests/fixtures/adaptive_paper_citations/245-trading-20261013-source.json"


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
                    # Admit an entry before the halt so the final BUY branch,
                    # as well as new-entry reservation, is tested after it.
                    fixture.reserve("pending-entry")
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
                    with self.assertRaisesRegex(native_safety.s.SafetyError, halt):
                        fixture.validate("pending-entry", quote=quote)
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
                      "order notional, price, quote, session and cleanup checks.", guidance)
        self.assertIn("safety.py#L1003-L1034", guidance)
        self.assertIn("safety.py#L1065-L1092", guidance)

    def test_aggregate_cap_describes_total_held_and_pending_exposure(self):
        guidance = re.sub(r"\s+", " ", PAGE.read_text(encoding="utf-8"))
        self.assertIn("caps total exposure after the order", guidance)
        self.assertIn("held and pending", guidance)
        self.assertNotIn("caps new exposure", guidance)

    def test_exit_bounds_keep_order_notional(self):
        guidance = re.sub(r"\s+", " ", PAGE.read_text(encoding="utf-8"))
        self.assertIn("Quantity, order notional, price, quote freshness, session "
                      "and cleanup bounds still apply to risk-reducing exits", guidance)
        self.assertIn("safety.py#L993-L996", guidance)

    def test_lumibot_is_a_conditional_second_engine_candidate(self):
        guidance = re.sub(r"\s+", " ", PAGE.read_text(encoding="utf-8"))
        self.assertIn("Lumibot is a second-engine candidate", guidance)
        self.assertNotIn("Lumibot is a comparator path", guidance)
        self.assertIn("no accepted sizing or portfolio-parity result", guidance)

    def test_overnight_limits_cite_a_retained_vendor_recapture(self):
        guidance = re.sub(r"\s+", " ", OVERNIGHT.read_text(encoding="utf-8"))
        self.assertIn("Only limit orders are supported overnight", guidance)
        self.assertIn("20:00 ET of the trade date", guidance)
        self.assertIn("Day Trading Buying Power does not apply overnight", guidance)
        self.assertIn("2x maximum", guidance)
        self.assertIn("https://docs.alpaca.markets/us/docs/245-trading", guidance)
        self.assertIn(CAPTURE.name, guidance)
        raw = CAPTURE.read_bytes()
        source = json.loads(PROVENANCE.read_text(encoding="utf-8"))
        self.assertEqual(source["url"], "https://docs.alpaca.markets/us/docs/245-trading.md")
        self.assertEqual(source["capture"], CAPTURE.name)
        self.assertEqual(source["sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(source["bytes"], len(raw))
        text = raw.decode("utf-8")
        self.assertIn("Only `limit` orders are supported", text)
        self.assertIn("the order is canceled at 8:00 PM ET", text)
        self.assertIn("Day Trading Buying Power (DTBP) does not apply", text)
        self.assertIn("2x multiplier is the max margin buying power", text)
        for heading in source["sections"]:
            self.assertIn("### " + heading, text)


if __name__ == "__main__":
    unittest.main()
