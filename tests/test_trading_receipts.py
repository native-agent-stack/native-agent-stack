"""Receipt-to-observation public seam: no broker, credentials, or native state."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class TradingReceiptTests(unittest.TestCase):
    def module(self):
        path = ROOT / "observability/trading_receipts.py"
        self.assertTrue(path.is_file(), "Trading receipt projection must exist")
        spec = importlib.util.spec_from_file_location("trading_receipts_test", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_paper_counts_rates_and_cash_basis_do_not_publish_extra_receipt_fields(self):
        m = self.module()
        receipt = {"elapsed_seconds": 120, "requests": [{"kind": "submit"}, {"kind": "read"},
                       {"kind": "submit"}, {"kind": "cancel"}], "native_fill_events": 3,
                   "accounting": {"held_symbols": 2, "realized_pnl_usd": "-1.00"},
                   "leverage": {"peak_gross_exposure_usd": "250", "broker_equity_at_start": "1000"},
                   "status": "passed", "ended_by": "duration",
                   "account_id": "PRIVATE_ACCOUNT_CANARY", "owner_text": "PRIVATE_OWNER_CANARY",
                   "environment": "PRIVATE_ENV_CANARY", "path": "/private/observer-canary"}
        row = m.paper_observation("A", receipt, source_unix=100, observed_unix=110)
        self.assertEqual((1, 1.5, .5), (row["orders_per_min"], row["fills_per_min"], row["cancels_per_min"]))
        self.assertEqual(.25, row["cash_use_ratio"])
        self.assertEqual((2, -1), (row["open_positions"], row["realized_pnl_usd"]))
        text = json.dumps(row)
        self.assertNotRegex(text, r"PRIVATE_|account_id|owner_text|environment|/private/")
        self.assertEqual(set(m.EXPORTED_FIELDS), set(row))

    def test_event_rates_use_real_fill_events_and_trailing_minute(self):
        m = self.module()
        events = [{"type": "preflight_ok", "t": 900, "equity": 1000},
                  {"type": "entry_order", "t": 970}, {"type": "exit_order", "t": 980},
                  {"type": "entry_fill", "t": 975}, {"type": "cancel_order", "t": 990},
                  {"type": "entry_order", "t": 800}, {"type": "entry_order", "t": 2000}]
        row = m.event_observation("lanea", events, {"positions": {"unexported": {"qty": 2, "entry": 100}},
                                                   "realized_usd": 12}, 1000, 990)
        self.assertEqual((2, 1, 1), (row["orders_per_min"], row["fills_per_min"], row["cancels_per_min"]))
        self.assertEqual((.2, 1, 12, 990), (row["cash_use_ratio"], row["open_positions"], row["realized_pnl_usd"], row["source_unix"]))
        self.assertNotIn("unexported", json.dumps(row))

    def test_latest_terminal_paper_receipt_survives_missing_optional_metrics(self):
        m = self.module()
        original = json.loads((ROOT / "blueprints/us-equities/adaptive-paper/trials/"
                               "20260923b-needs-attention/paper-output.json").read_text())
        # A public producer receipt supplies the outcome; optional numeric groups
        # must not decide which attempt is selected. No host receipt is opened.
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            previous, latest = root / "previous.json", root / "latest.json"
            previous.write_text(json.dumps(dict(original, status="passed")))
            latest.write_text(json.dumps({k: v for k, v in original.items()
                                          if k not in ("requests", "accounting")}))
            os.utime(previous, (100, 100))
            os.utime(latest, (200, 200))
            for paths in ([previous, latest], [latest]):
                with self.subTest(previous_present=len(paths) > 1):
                    row = m.paper_lane("A", paths, 300)
                    self.assertEqual(200, row["source_unix"])
                    self.assertEqual(m.paper_observation("A", original, 200, 300)["status_code"],
                                     row["status_code"])
                    self.assertEqual(-1, row["orders_per_min"])
                    self.assertEqual(-1, row["open_positions"])
                    self.assertEqual(m.UNKNOWN_PNL, row["realized_pnl_usd"])

    def test_public_native_paper_failure_receipts_map_to_blocked(self):
        m = self.module()
        for trial in ("20260923e-first-roundtrip", "20260923b-needs-attention",
                      "ladder-1x-20260924a-needs-attention"):
            with self.subTest(trial=trial):
                receipt = json.loads((ROOT / "blueprints/us-equities/adaptive-paper/trials" /
                                      trial / "paper-output.json").read_text())
                self.assertEqual(3, m.paper_observation("B", receipt, 100, 110)["status_code"])

    def test_correctness_record_binds_each_out_of_tree_producer_to_a_version_reference(self):
        record = (ROOT / "docs/decisions/2026-10-13-trading-lanes-dashboard.md").read_text()
        heading = "## Version-bound producer references"
        self.assertIn(heading, record)
        references = record.split(heading, 1)[1].split("\n## ", 1)[0]
        for name in ("calc_session.py", "ibkr_series4.sh", "series_line.py"):
            rows = [line.split("|") for line in references.splitlines()
                    if line.startswith("|") and name in line]
            self.assertTrue(rows, name)
            for cells in rows:
                self.assertRegex(cells[2], r"source-ref:[A-Za-z0-9-]+/[A-Za-z0-9-]+")
                self.assertRegex(cells[3], r"[0-9]+")

    def test_cash_is_not_equity_and_missing_data_never_becomes_zero(self):
        m = self.module()
        row = m.paper_observation("B", {"leverage": {"broker_cash_at_start": 1000,
                                    "peak_gross_exposure_usd": 250}}, 100, 110)
        self.assertEqual(-1, row["cash_use_ratio"])
        self.assertEqual(-1, row["fills_per_min"])
        self.assertEqual(m.UNKNOWN_PNL, row["realized_pnl_usd"])
        self.assertEqual(5, m.empty("I-llm", 110, 5)["status_code"])

    def test_ibkr_no_session_does_not_rename_cash_delta_as_realized_pnl(self):
        m = self.module()
        row = m.ibkr_observation({"elapsed_s": 120, "submits": 4, "fills": 2, "cancels": 6,
                                 "flat": True, "cash_delta_usd": 900, "wire_mean_per_s": 12,
                                 "wire_peak_per_s": 44, "cash_use_peak": .4}, 10, 1000)
        self.assertEqual((2, 1, 3), (row["orders_per_min"], row["fills_per_min"], row["cancels_per_min"]))
        self.assertEqual((4, 10, 0), (row["status_code"], row["source_unix"], row["open_positions"]))
        self.assertEqual(m.UNKNOWN_PNL, row["realized_pnl_usd"])
        self.assertEqual((12, 44), (row["wire_mean_per_s"], row["wire_peak_per_s"]))

    def test_ibkr_new_session_start_supersedes_ended_status_without_exporting_start_line(self):
        m = self.module()
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            status = root / "status"
            status.write_text('2026-10-13T10:00:00Z session k=1 end rc=0 {"elapsed_s":60,"submits":2}\n'
                              '2026-10-13T11:00:00Z session k=2 start ids=PRIVATE/PRIVATE state=/private/canary\n')
            row = m.ibkr_lane(status, root / "absent", m.timestamp("2026-10-13T11:01:00Z"))
            self.assertEqual(1, row["status_code"])
            self.assertEqual(m.timestamp("2026-10-13T11:00:00Z"), row["source_unix"])
            self.assertNotRegex(json.dumps(row), r"PRIVATE|/private/|ids=|state=")

    def test_native_final_flat_and_preflight_refused_are_terminal_before_staleness(self):
        # Native logger: calc_session.py:239 log; emitted witnesses in the
        # owner POST events: lanea lines35/57, laneb lines34/52 on2026-10-14.
        m = self.module()
        start = m.timestamp("2026-10-13T20:00:00Z")
        for event, expected in [("final_flat", 2), ("preflight_refused", 3)]:
            for now in (start + 1, start + 400):
                with self.subTest(event=event, now=now):
                    row = m.event_observation("lanea", [{"type": event, "t": "2026-10-13T20:00:00Z"}], {}, now, start)
                    self.assertEqual(expected, row["status_code"])

    def test_native_cancellation_types_count_in_the_recorded_minute(self):
        # calc_session.py:261 implements trail_cancelled; native emitted
        # run-rth/events.jsonl:58 trail_cancelled and:187 entry_cancelled.
        m = self.module()
        now = m.timestamp("2026-10-13T20:01:00Z")
        row = m.event_observation("C", [{"type": "trail_cancelled", "t": "2026-10-13T20:00:40Z"},
                                 {"type": "entry_cancelled", "t": "2026-10-13T20:00:50Z"}], {}, now, now - 10)
        self.assertEqual(2, row["cancels_per_min"])

    def test_overnight_receipt_stays_active_between_five_minute_rounds(self):
        # CC04:21Z: overnight rounds are ~5m12s apart; allow12 minutes,
        # while terminal/refused receipts remain authoritative at any age.
        m = self.module()
        start = m.timestamp("2026-10-14T04:17:24Z")
        events = [{"type": "preflight_ok", "t": "2026-10-14T04:17:24Z"}]
        for age, status in [(300, 1), (624, 1), (719, 1), (720, 6), (900, 6)]:
            with self.subTest(age=age):
                row = m.event_observation("C", events, {}, start + age, start)
                self.assertEqual(status, row["status_code"])
                self.assertEqual(start, row["source_unix"])
                self.assertEqual(0, row["orders_per_min"])
        for event, expected in [("final_flat", 2), ("preflight_refused", 3)]:
            with self.subTest(event=event):
                row = m.event_observation("C", [{"type": event, "t": "2026-10-14T04:17:24Z"}],
                                          {}, start + 300, start)
                self.assertEqual(expected, row["status_code"])

    def test_post_arms_use_their_own_measured_round_cadence_and_illm_is_unrecorded(self):
        m = self.module()
        start = m.timestamp("2026-10-14T04:17:24Z")
        events = [{"type": "preflight_ok", "t": "2026-10-14T04:17:24Z"}]
        for lane, age, expected in [("lanea", 1117, 1), ("lanea", 1199, 1), ("lanea", 1200, 6),
                                    ("laneb", 750, 1), ("laneb", 779, 1), ("laneb", 780, 6),
                                    ("I-llm", 1, 7), ("I-llm", 300, 7)]:
            with self.subTest(lane=lane, age=age):
                row = m.event_observation(lane, events, {}, start + age, start)
                self.assertEqual(expected, row["status_code"])
        # Unknown cadence cannot override authoritative completion/refusal.
        row = m.event_observation("I-llm", [{"type": "final_flat", "t": "2026-10-14T04:17:24Z"}],
                                  {}, start + 300, start)
        self.assertEqual(2, row["status_code"])

    def test_native_ibkr_no_receipt_end_stops_active_session_and_clears_old_metrics(self):
        # Native ibkr_series4.sh:43/45 and earlier series.sh:40/42.
        m = self.module()
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            status = root / "status"
            status.write_text('2026-10-13T10:00:00Z session k=1 end rc=0 {"elapsed_s":60,"submits":8}\n'
                              '2026-10-13T11:00:00Z session k=2 start ids=PRIVATE/PRIVATE state=/private/canary\n'
                              '2026-10-13T11:01:00Z session k=2 end rc=1 no receipt: UNPUBLISHED_ERROR_CANARY\n')
            row = m.ibkr_lane(status, root / "absent", m.timestamp("2026-10-14T00:00:00Z"))
            self.assertEqual(3, row["status_code"])
            self.assertEqual(m.timestamp("2026-10-13T11:01:00Z"), row["source_unix"])
            self.assertEqual(-1, row["orders_per_min"])
            self.assertNotIn("CANARY", json.dumps(row))

    def test_ibkr_accounting_uses_selected_summary_receipt_and_not_mtime(self):
        # series_line.py:12 writes the exact own receipt basename in summary.
        m = self.module()
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            receipts = root / "session" / "receipts"
            receipts.mkdir(parents=True)
            selected = receipts / "ibp-20261013-100000-paper.json"
            selected.write_text(json.dumps({"accounting": {"realized_pnl_usd": 11, "held_symbols": 1}}))
            newer = receipts / "ibp-20261013-110000-paper.json"
            newer.write_text(json.dumps({"accounting": {"realized_pnl_usd": 999, "held_symbols": 9}}))
            import os
            os.utime(selected, (100, 100))
            os.utime(newer, (200, 200))
            status = root / "status"
            status.write_text('2026-10-13T10:00:00Z session k=1 end rc=0 '
                              '{"receipt":"ibp-20261013-100000-paper.json","elapsed_s":60,"submits":2}\n')
            row = m.ibkr_lane(status, root, m.timestamp("2026-10-13T10:01:00Z"))
            self.assertEqual((11, 1, 2), (row["realized_pnl_usd"], row["open_positions"], row["orders_per_min"]))


if __name__ == "__main__":
    unittest.main()
