"""Synthetic regression for the sealed producer's rung-window rate contract.

Source: V4-CHANGES.md section 1, cases A, B and E, at fd2c7218.
The documented two-second examples supply the expected literal rates. Test only
ladder_rungs(receipt, rows); no private receipt, helper or current clock is used.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


SOURCE = Path(__file__).resolve().parents[1] / (
    "evidence/artifacts/ibkr-pacing-20261013/generate_ibkr_pacing_evidence.py"
)
SPEC = importlib.util.spec_from_file_location("ibkr_pacing_generator", SOURCE)
GENERATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GENERATOR)


class RungWindowMeanTests(unittest.TestCase):
    def fixture(self, cancel_times, *, second_rung=False, repeated_cancel=False):
        """Build invented syn-N rows, fixed UTC timestamps and receipt slots."""
        def row(event, when, **fields):
            seconds = int(when)
            micros = round((when - seconds) * 1_000_000)
            return {
                "event": event, "step": "S4",
                "utc": f"2000-01-01T00:00:{seconds:02d}.{micros:06d}+00:00",
                **fields,
            }

        rows = [row("step_enter", 0)]
        for index, (submitted, canceled) in enumerate(
            zip((0.1, 0.2, 0.3, 0.4), cancel_times), start=1
        ):
            fields = {"coid": f"syn-{index}", "rung": 10}
            rows += [row("submit", submitted, **fields),
                     row("order_accepted", submitted + 0.01, **fields),
                     row("cancel", canceled, reason="accepted", **fields)]
        rungs = [{
            "target_msgs_per_s": 10, "submits": 4, "skipped_slots": 0,
            "per_second_msgs": [6, 0], "mean_msgs_per_s": 3,
        }]
        if second_rung:
            for index, (submitted, canceled) in enumerate(
                zip((2.1, 2.15, 2.3, 2.4), (2.6, 2.7, 2.8, 2.9)), start=5
            ):
                fields = {"coid": f"syn-{index}", "rung": 20}
                rows += [row("submit", submitted, **fields),
                         row("order_accepted", submitted + 0.01, **fields),
                         row("cancel", canceled, reason="accepted", **fields)]
            rungs.append({
                "target_msgs_per_s": 20, "submits": 4, "skipped_slots": 0,
                "per_second_msgs": [10, 0], "mean_msgs_per_s": 5,
            })
        if repeated_cancel:
            rows.append(row("cancel", 1.2, coid="syn-1", rung=10, reason="accepted"))
            rungs[0].update(per_second_msgs=[8, 1], mean_msgs_per_s=4.5)
        receipt = {"frozen": {"s4": {"rung_s": 2}}, "ladder": {"rungs": rungs}}
        return receipt, sorted(rows, key=lambda item: item["utc"])

    def assert_rates(self, rung, expected):
        self.assertEqual(
            (rung["wire_est_refined_msgs_per_s_mean"],
             rung["wire_est_upper_bound_msgs_per_s_mean"]), expected,
        )

    def test_cross_rung_cancels_are_charged_to_the_window_that_sent_them(self):
        receipt, rows = self.fixture((0.5, 0.6, 2.2, 2.5), second_rung=True)
        first, second = GENERATOR.ladder_rungs(receipt, rows)
        # Case A: the two windows contain 8 and 16 wire messages over 2 s;
        # order attribution incorrectly gives 12 / 2 = 6 for each rung.
        self.assert_rates(first, (4.0, 4.0))
        self.assert_rates(second, (8.0, 8.0))
        self.assertEqual(first["cancels_sent_in_other_rung_window"], 2)
        self.assertEqual(second["cancels_sent_in_own_window"], 4)
        self.assertTrue(first["receipt_slots_replayed_from_journal"]["equal"])
        self.assertTrue(second["receipt_slots_replayed_from_journal"]["equal"])

    def test_post_ladder_cancels_do_not_inflate_the_rung_window_mean(self):
        receipt, rows = self.fixture((0.5, 0.6, 2.4, 2.8))
        rung, = GENERATOR.ladder_rungs(receipt, rows)
        # Case B: 4 submits + 2 accepted cancels = 8 wire messages inside
        # [0, 2); the two later cancels must not produce the old 6 msgs/s.
        self.assert_rates(rung, (4.0, 4.0))
        self.assertEqual(rung["cancels_sent_outside_rung_windows"], 2)
        self.assertTrue(rung["receipt_slots_replayed_from_journal"]["equal"])

    def test_repeated_cancel_counts_each_message_inside_the_window(self):
        receipt, rows = self.fixture((0.5, 0.6, 0.7, 0.8), repeated_cancel=True)
        rung, = GENERATOR.ladder_rungs(receipt, rows)
        # Case E: the retry adds 2 wire messages, so 14 / 2 = 7 msgs/s;
        # one-cancel-per-order attribution incorrectly remains at 6.
        self.assert_rates(rung, (7.0, 7.0))
        self.assertEqual(rung["cancels_sent"], 4)
        self.assertEqual(rung["cancels_sent_in_own_window"], 4)
        self.assertTrue(rung["receipt_slots_replayed_from_journal"]["equal"])


if __name__ == "__main__":
    unittest.main()
