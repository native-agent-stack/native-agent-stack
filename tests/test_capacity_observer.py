"""Read-only observer fixtures: fake 0600 env files, stub SDK, no network."""

import contextlib
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
import runpy
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "blueprints/us-equities/order-throughput/evidence"
SCRIPT = EVIDENCE / "observe-capacity-20261013.py"


class CapacityObserverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Import real reader dependencies before patch.dict restores sys.modules;
        # native NumPy extensions cannot be freshly initialized for each fixture.
        adaptive = ROOT / "blueprints/us-equities/adaptive-paper"
        if str(adaptive) not in sys.path:
            sys.path.insert(0, str(adaptive))
        import runner

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir="/var/tmp", prefix="observer-fixture-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.env = self.root / "paper.env"
        self.receipt = self.root / "receipt.json"
        self.prefix = "cap-fixture-"
        self.receipt.write_text(json.dumps({"started_at": "2026-10-13T08:00:00+00:00",
                                           "probe_plan": {"client_order_id_prefix": self.prefix}}))
        self.calls = []
        owner = self

        class Client:
            def __init__(self, key, secret, *, paper):
                owner.calls.append(("client", key, secret, paper))

            def get_orders(self, request):
                owner.calls.append(("orders", request.status))
                if request.status == "open":
                    return []
                return [SimpleNamespace(id="fixture-id", client_order_id=owner.prefix + "1",
                                        status=SimpleNamespace(value="canceled"), filled_qty="0",
                                        submitted_at=datetime(2026, 10, 13, 8, 1, tzinfo=timezone.utc))]

            def get_all_positions(self):
                owner.calls.append(("positions",))
                return []

        self.modules = {name: ModuleType(name) for name in
                        ("alpaca", "alpaca.trading", "alpaca.trading.client",
                         "alpaca.trading.requests", "alpaca.trading.enums")}
        self.modules["alpaca"].__version__ = "fixture"
        self.modules["alpaca.trading.client"].TradingClient = Client
        self.modules["alpaca.trading.requests"].GetOrdersRequest = lambda **kwargs: SimpleNamespace(**kwargs)
        self.modules["alpaca.trading.enums"].QueryOrderStatus = SimpleNamespace(ALL="all", OPEN="open")

    def invoke(self, content, *, script=SCRIPT, mode=0o600):
        self.env.write_text(content)
        self.env.chmod(mode)
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.dict(sys.modules, self.modules), \
                patch.object(sys, "argv", [str(script), "--env-file", str(self.env),
                                          "--receipt", str(self.receipt)]), \
                patch("socket.create_connection", side_effect=AssertionError("network forbidden")), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            try:
                runpy.run_path(str(script), run_name="__main__")
            except SystemExit as result:
                code = result.code
            else:
                code = 0
        return code, stdout.getvalue(), stderr.getvalue()

    def assert_counts(self, content, *, script=SCRIPT):
        code, stdout, stderr = self.invoke(content, script=script)
        self.assertEqual(code, 0, stderr)
        result = json.loads(stdout)
        for name, expected in {"orders_listed_since_start": 1, "orders_with_run_prefix": 1,
                               "status_counts": {"canceled": 1}, "filled_qty_total": 0,
                               "positions_now": 0, "open_orders_now": 0}.items():
            self.assertEqual(result[name], expected)
        self.assertEqual(self.calls[0], ("client", "fixturekey", "fixturesecret", True))
        self.assertNotIn("fixturekey", stdout + stderr)
        self.assertNotIn("fixturesecret", stdout + stderr)

    def test_export_format_passes(self):
        self.assert_counts("export APCA_API_KEY_ID=fixturekey\nexport APCA_API_SECRET_KEY=fixturesecret\n")

    def test_plain_format_passes(self):
        self.assert_counts("APCA_API_KEY_ID=fixturekey\nAPCA_API_SECRET_KEY=fixturesecret\n")

    def test_quotes_and_comments_pass(self):
        self.assert_counts("# ignored\nexport APCA_API_KEY_ID='fixturekey' # key\n"
                           'APCA_API_SECRET_KEY="fixturesecret" # secret\n')

    def test_missing_key_is_a_bounded_refusal_before_the_sdk(self):
        code, stdout, stderr = self.invoke("export APCA_API_KEY_ID=fixturekey\n")
        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "observer refused: credentials_unavailable\n")
        self.assertEqual(self.calls, [])

    def test_unsafe_file_mode_is_refused_before_the_sdk(self):
        code, stdout, stderr = self.invoke("APCA_API_KEY_ID=fixturekey\nAPCA_API_SECRET_KEY=fixturesecret\n",
                                           mode=0o644)
        self.assertEqual((code, stdout, stderr), (2, "", "observer refused: credentials_unavailable\n"))
        self.assertEqual(self.calls, [])

    def test_malformed_quotes_are_a_bounded_refusal(self):
        code, stdout, stderr = self.invoke("export APCA_API_KEY_ID='fixturekey\n"
                                          "export APCA_API_SECRET_KEY=fixturesecret\n")
        self.assertEqual((code, stdout, stderr), (2, "", "observer refused: credentials_unavailable\n"))
        self.assertEqual(self.calls, [])

    def test_success_prints_only_counts(self):
        code, stdout, stderr = self.invoke("APCA_API_KEY_ID=fixturekey\nAPCA_API_SECRET_KEY=fixturesecret\n")
        self.assertEqual(code, 0, stderr)
        self.assertEqual(set(json.loads(stdout)), {"orders_listed_since_start", "orders_with_run_prefix",
                                                 "status_counts", "filled_qty_total", "positions_now",
                                                 "open_orders_now"})

    def test_sdk_failure_never_prints_exception_or_key_material(self):
        def refused_client(*args, **kwargs):
            raise RuntimeError("fixturesecret private diagnostic")

        self.modules["alpaca.trading.client"].TradingClient = refused_client
        code, stdout, stderr = self.invoke("APCA_API_KEY_ID=fixturekey\nAPCA_API_SECRET_KEY=fixturesecret\n")
        self.assertEqual((code, stdout, stderr), (1, "", "observer refused: observation_unavailable\n"))

    def test_missing_receipt_prefix_refuses_without_an_order_read(self):
        self.receipt.write_text(json.dumps({"started_at": "2026-10-13T08:00:00+00:00"}))
        code, stdout, stderr = self.invoke("APCA_API_KEY_ID=fixturekey\nAPCA_API_SECRET_KEY=fixturesecret\n")
        self.assertEqual((code, stdout, stderr), (1, "", "observer refused: observation_unavailable\n"))
        self.assertEqual([call[0] for call in self.calls], ["client"])

    def test_full_page_without_new_ids_never_prints_partial_counts(self):
        original = self.modules["alpaca.trading.client"].TradingClient

        class RepeatingPageClient(original):
            def get_orders(self, request):
                return super().get_orders(request) * 500

        self.modules["alpaca.trading.client"].TradingClient = RepeatingPageClient
        code, stdout, stderr = self.invoke("APCA_API_KEY_ID=fixturekey\nAPCA_API_SECRET_KEY=fixturesecret\n")
        self.assertEqual((code, stdout, stderr), (1, "", "observer refused: observation_unavailable\n"))
        self.assertEqual([call[0] for call in self.calls], ["client", "orders", "orders"])


if __name__ == "__main__":
    unittest.main()
