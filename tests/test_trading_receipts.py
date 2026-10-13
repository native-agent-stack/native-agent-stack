"""Receipt-to-observation public seam: no broker, credentials, or native state."""
import importlib.util
import json
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


if __name__ == "__main__":
    unittest.main()
