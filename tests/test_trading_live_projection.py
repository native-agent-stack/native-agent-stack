"""FIELDS-v1 public seam; synthetic journals only, never native journal capture."""
import importlib.util
import json
import os
import shutil
import socket
import subprocess
from pathlib import Path
import stat
import tempfile
import time
import unittest
import urllib.parse
import urllib.request
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
STAMP = "2026-10-14T12:00:00.000Z"
MILLIS = 1791979200000
ENVELOPE = {"v", "lane", "kind", "t_ms", "run", "session", "observed_ms", "row_id"}


def module():
    path = ROOT / "observability/trading_live.py"
    if not path.exists():
        raise AssertionError("live projector is absent")
    spec = importlib.util.spec_from_file_location("trading_live_test", path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def ib(kind, **values):
    return dict(dict(t_utc=STAMP, seq=1, lane="IBKR", trial="sample", session="day", kind=kind), **values)


def calc(kind, **values):
    return dict(t=STAMP, type=kind, segment="day", calc_version="3.17.5", eid="abcdef01", **values)


class LiveProjectionTests(unittest.TestCase):
    def test_01_each_frozen_kind_has_exactly_its_envelope_and_listed_fields(self):
        m = module()
        p = m.Projector()
        ibkr = {
            "submit": ({"order_id": 12, "symbol": "BRK.B", "side": "BUY", "qty": "2", "limit_price": 9,
                        "outside_rth": True}, "order_key symbol side qty limit_price outside_rth"),
            "ack": ({"order_id": 12, "status": "Submitted"}, "order_key status"),
            "status": ({"order_id": 12, "status": "Filled", "filled": 2, "remaining": 0,
                        "avg_fill_price": 9, "last_fill_price": 9},
                       "order_key status filled remaining avg_fill_price last_fill_price"),
            "cancel_sent": ({"order_id": 12}, "order_key"),
            "cancel_ack": ({"order_id": 12}, "order_key"),
            "fill": ({"order_id": 12, "exec_id": "fill-token", "symbol": "BRK.B", "side": "buy", "exec_qty": 2,
                      "exec_price": 9, "cum_qty": 2}, "order_key symbol side exec_qty exec_price cum_qty"),
            "commission": ({"exec_id": "fill-token", "commission": 1, "commission_currency": "USD", "realized_pnl": 3},
                           "order_key commission commission_currency realized_pnl"),
            "reject": ({"order_id": 12, "code": 201}, "order_key code"),
            "error": ({"req_id": 18, "code": 1}, "code"),
            "account": ({"net_liquidation": 100, "total_cash_value": 80}, "net_liquidation total_cash_value"),
            "position": ({"symbol": "BRK.B", "qty": 2, "avg_cost": 9}, "symbol qty avg_cost"),
            "pnl": ({"daily_pnl": 1, "unrealized_pnl": 2, "realized_pnl": 3}, "daily_pnl unrealized_pnl realized_pnl"),
            "pnl_single": ({"symbol": "BRK.B", "position": 2, "daily_pnl": 1, "unrealized_pnl": 2,
                            "realized_pnl": 3, "value": 18}, "symbol position daily_pnl unrealized_pnl realized_pnl value"),
            "wire": ({"messages": 2, "peak_per_second": 1, "total": 9}, "messages peak_per_second total"),
        }
        for kind, (values, fields) in ibkr.items():
            with self.subTest(lane="IBKR", kind=kind):
                rows = p.project("IBKR", ib(kind, **values), observed_ms=MILLIS)
                self.assertEqual(1, len(rows))
                self.assertEqual(ENVELOPE | {"seq"} | set(fields.split()), set(rows[0]))
                self.assertEqual(MILLIS, rows[0]["t_ms"])
        rank_numbers = "score move_pct rvol spread_bps quote_age_s trade_age_s vwap last bid ask band_pct range_pct fade_pct stop_pct trail_pct session_dollar_vol vol_session ref_close ret_3m_pct ret_ytd_pct"
        c = {
            "rank_round": ({"slots": 1, "held": 0, "held_symbols": ["BRK.B"], "added_by_group": {"impulse": 1, "trend": 2},
                            "round_seconds": 1, "round_tool_calls": 3},
                           "round_key slots held held_symbols added_impulse added_trend round_seconds round_tool_calls"),
            "rank_row": (dict(rank=1, symbol="BRK.B", eligible=True, group="impulse", asset_class="equity", halt_prone=False,
                              reasons=[], reason_count=0, **{k: 1 for k in rank_numbers.split()}),
                         "round_key rank symbol eligible group asset_class halt_prone reasons reason_count " + rank_numbers),
            "no_selection_round": ({"eligible": 0, "ranked": 2, "top": ["BRK.B score=9"], "round_seconds": 1,
                                    "round_tool_calls": 3}, "eligible ranked top_symbols round_seconds round_tool_calls"),
            "size_check": (dict(symbol="BRK.B", ok=True, qty=2, cap_binding="equity", refusals=[],
                                **{k: 1 for k in "limit_price notional equity_cap drift_pct drift_ref_last quote_bid quote_ask quote_mid quote_age_s".split()}),
                           "symbol ok qty cap_binding refusals limit_price notional equity_cap drift_pct drift_ref_last quote_bid quote_ask quote_mid quote_age_s"),
            "entry_order": ({"order_id": "order-token", "symbol": "BRK.B", "qty": 2, "limit_price": 9,
                             "move_pct": 1, "rvol": 2, "score": 3, "catalyst": "omitted"},
                            "order_key symbol qty limit_price move_pct rvol score catalyst_present"),
            "entry_fill": ({"order_id": "order-token", "symbol": "BRK.B", "qty": 2, "price": 9,
                            "booked_qty": 2, "booked_avg": 9, "delta_qty": 2, "delta_price": 9, "repeat": False},
                           "order_key symbol qty price booked_qty booked_avg delta_qty delta_price repeat"),
            "trail_order": ({"order_id": "order-token", "symbol": "BRK.B"}, "order_key symbol"),
            "exit_order": ({"order_id": "order-token", "symbol": "BRK.B", "qty": 2, "limit_price": 9, "reason": "risk"},
                           "order_key symbol qty limit_price reason"),
            "exit_fill": ({"order_id": "order-token", "symbol": "BRK.B", "qty": 2, "price": 9, "realized_usd": 3,
                           "reason": "risk", "position_closed": True, "remaining_qty": 0, "booked_qty": 2,
                           "booked_avg": 9, "delta_qty": 2, "delta_price": 9, "repeat": False},
                          "order_key symbol qty price realized_usd reason position_closed remaining_qty booked_qty booked_avg delta_qty delta_price repeat"),
            "reconcile": ({"match": True, "exit_mode": "trail", "held": [], "mismatches": [], "resting_exits": []},
                          "match exit_mode held_count mismatch_count resting_exit_count"),
            "preflight_ok": ({"equity": 100, "adopted_symbols": ["BRK.B"], "clock": "ok"}, "equity adopted_symbols clock"),
            "preflight_refused": ({"equity": 100, "mismatches": [], "clock": "ok"}, "equity mismatch_count clock"),
            "flatten_done": ({"open_orders": 0, "positions": 0}, "open_orders positions"),
            "final_flat": ({"fills": 1, "orders": 2, "realized_usd": {"BRK.B": 3}, "exit_reason_counts": {"risk": 1}},
                           "fills orders realized_total_usd exit_reason_counts"),
        }
        for kind, (values, fields) in c.items():
            with self.subTest(lane="C", kind=kind):
                rows = p.project("C", calc(kind, **values), run="sample", observed_ms=MILLIS)
                self.assertEqual(1, len(rows))
                self.assertEqual(ENVELOPE | {"calc_version", "event_key"} | set(fields.split()), set(rows[0]))
                self.assertEqual(MILLIS, rows[0]["t_ms"])
        nested = p.project("C", calc("rank_round", rows=[dict(c["rank_row"][0])]), run="sample", observed_ms=MILLIS)
        self.assertEqual(["rank_round", "rank_row"], [r["kind"] for r in nested])
        self.assertEqual(nested[0]["round_key"], nested[1]["round_key"])

    def test_02_unlisted_output_key_refuses_whole_row_and_counts_refusal(self):
        m = module()
        p = m.Projector()
        row = p.project("IBKR", ib("error", code=1), observed_ms=MILLIS)[0]
        with tempfile.TemporaryDirectory() as scratch:
            spool = Path(scratch) / "live.jsonl"
            self.assertFalse(p.append(spool, [dict(row, unexpected="suppressed")]))
            self.assertEqual(1, p.refused)
            self.assertFalse(spool.exists())
            self.assertTrue(p.append(spool, [row]))
            self.assertEqual([row], [json.loads(s) for s in spool.read_text().splitlines()])

    def test_03_symbol_is_a_format_check_and_account_shape_never_reaches_spool(self):
        m = module()
        p = m.Projector()
        forbidden = "DU" + str(10**6 + 19)
        with tempfile.TemporaryDirectory() as scratch:
            spool = Path(scratch) / "live.jsonl"
            for value, expected in (("BRK.B", "BRK.B"), (forbidden, "OTHER"), ("lower", "OTHER"), ("TOOLONG", "OTHER")):
                row = p.project("IBKR", ib("position", symbol=value, qty=1), observed_ms=MILLIS)[0]
                self.assertEqual(expected, row["symbol"])
                self.assertTrue(p.append(spool, [row]))
            self.assertNotIn(forbidden, spool.read_text())

    def test_04_restart_rebuilds_order_and_exec_joins_without_reemitting_lines(self):
        m = module()
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            journal, spool, state = root / "journal.jsonl", root / "live.jsonl", root / "state"
            source = [ib("submit", order_id=44, client_order_id="order-token", perm_id=55, symbol="BRK.B"),
                      ib("fill", seq=2, order_id=44, exec_id="fill-token", symbol="BRK.B", exec_qty=2)]
            journal.write_text("".join(json.dumps(r) + "\n" for r in source))
            before = journal.read_bytes(), journal.stat().st_mtime_ns
            first = m.Tailer(state, spool)
            first.poll("IBKR", journal, observed_ms=MILLIS)
            initial = spool.read_bytes()
            again = m.Tailer(state, spool)
            again.poll("IBKR", journal, observed_ms=MILLIS + 1)
            self.assertEqual(initial, spool.read_bytes())
            # Recovery ports restart seq at1 in the same inode. It is not a dedup key.
            with journal.open("a") as stream:
                stream.write(json.dumps(ib("commission", exec_id="fill-token", commission="1.25")) + "\n")
            again.poll("IBKR", journal, observed_ms=MILLIS + 2)
            rows = [json.loads(s) for s in spool.read_text().splitlines()]
            self.assertEqual(["sample/o1"] * 3, [r["order_key"] for r in rows])
            self.assertEqual([1, 2, 1], [r["seq"] for r in rows])
            self.assertEqual(1.25, rows[-1]["commission"])
            self.assertEqual(before[0], journal.read_bytes()[:len(before[0])])
            public = spool.read_text()
            for key in ("order_id", "perm_id", "exec_id", "client_order_id", "order-token", "fill-token"):
                self.assertNotIn(key, public)
            checkpoint = (state / "checkpoint.json").read_text()
            self.assertNotIn("order-token", checkpoint)
            self.assertNotIn("fill-token", checkpoint)
            # A new inode at the same path is a new source, emitted from0.
            replacement = root / "replacement.jsonl"
            replacement.write_text(json.dumps(ib("error", code=1)) + "\n")
            replacement.replace(journal)
            again.poll("IBKR", journal, observed_ms=MILLIS + 3)
            self.assertEqual(4, len(spool.read_text().splitlines()))

    def test_05_nonfinite_unset_and_overbound_numbers_are_omitted(self):
        m = module()
        for value in (1.7976931348623157e308, "NaN", "inf", float("-inf"), 10**12 + 1, True, [], {}):
            with self.subTest(value=value):
                row = m.Projector().project("IBKR", ib("position", symbol="BRK.B", qty=value), observed_ms=MILLIS)[0]
                self.assertNotIn("qty", row)
        row = m.Projector().project("IBKR", ib("position", symbol="BRK.B", qty="1.25"), observed_ms=MILLIS)[0]
        self.assertEqual(1.25, row["qty"])

    def test_06_calc_reasons_drop_unsafe_text_and_mask_templates(self):
        m = module()
        reasons = ["BRK.B score 123 below 45", "bad/segment", "bad@segment", "bad\\segment",
                   'bad"segment', "bad'segment", "bad\nsegment", "x" * 100, "safe"]
        row = m.Projector().project("C", calc("size_check", symbol="BRK.B", refusals=reasons),
                                    run="sample", observed_ms=MILLIS)[0]
        self.assertEqual(["SYM score # below #", "x" * 80], row["refusals"])

    def test_07_eastern_execution_and_iso_quote_times_are_explicit(self):
        m = module()
        for text, expected in (("20261014 08:00:00 US/Eastern", MILLIS), ("20261014 08:00:00", None)):
            row = m.Projector().project("IBKR", ib("fill", exec_time=text), observed_ms=MILLIS)[0]
            self.assertEqual(expected, row.get("exec_time_ms"))
        row = m.Projector().project("IBKR", ib("submit", pricing_observation={"bid": 10, "ask": 11,
                                      "arrival_utc": "2026-10-14T11:59:59.000Z", "id": "never-forward"}),
                                    observed_ms=MILLIS)[0]
        self.assertEqual((10, 11, MILLIS - 1000, 1000),
                         tuple(row[k] for k in ("quote_bid", "quote_ask", "quote_arrival_ms", "quote_age_ms")))
        self.assertNotIn("never-forward", json.dumps(row))
        row = m.Projector().project("C", calc("size_check", quote_time=STAMP), run="sample", observed_ms=MILLIS)[0]
        self.assertEqual(MILLIS, row["quote_time_ms"])

    def test_08_spool_over_eight_mib_is_truncated_with_private_mode(self):
        m = module()
        with tempfile.TemporaryDirectory() as scratch:
            spool = Path(scratch) / "live.jsonl"
            with spool.open("wb") as stream:
                stream.truncate(8 * 1024 * 1024 + 1)
            spool.chmod(0o644)
            row = m.Projector().project("IBKR", ib("error", code=1), observed_ms=MILLIS)[0]
            self.assertTrue(m.Projector().append(spool, [row]))
            self.assertEqual([row], [json.loads(s) for s in spool.read_text().splitlines()])
            self.assertEqual(0o600, stat.S_IMODE(spool.stat().st_mode))

    def test_09_isolated_transport_preserves_every_existing_receiver_transform_and_pipeline(self):
        overlay = ROOT / "observability/trading-live-collector.yaml"
        self.assertTrue(overlay.is_file(), "separate live transport is absent")
        # These existing bytes are the published main assets, not a journal fixture.
        for relative in ("observability/paper-trading-live/collector-paper-trading.yaml",
                         "evidence/artifacts/new-wsl-install-plan-20261002/config/otel.yaml"):
            original = subprocess.check_output(["git", "show", "a339425ca:" + relative], cwd=ROOT)
            self.assertEqual(original, (ROOT / relative).read_bytes())
        if not shutil.which("otelcol-contrib"):
            self.skipTest("native Collector transport requires installed contrib0.162.0")
        import yaml
        base = ROOT / "evidence/artifacts/new-wsl-install-plan-20261002/config/otel.yaml"
        legacy = ROOT / "observability/paper-trading-live/collector-paper-trading.yaml"
        legacy_paths = [legacy]
        if os.environ.get("TRADING_PROJECTION_CONFIG"):
            legacy_paths.append(Path(os.environ["TRADING_PROJECTION_CONFIG"]))
        with tempfile.TemporaryDirectory() as scratch:
            env = dict(os.environ, NS2604_OBSERVABILITY_DATA=scratch)
            def effective(paths):
                result = subprocess.run(["otelcol-contrib", "print-config", "--mode=unredacted",
                                         *["--config=" + str(p) for p in paths]],
                                        env=env, capture_output=True, text=True)
                self.assertEqual(0, result.returncode, result.stderr)
                return yaml.safe_load(result.stdout)
            before, after = effective([base, *legacy_paths]), effective([base, *legacy_paths, overlay])
            for group in ("receivers", "processors"):
                for name, value in before[group].items():
                    self.assertEqual(value, after[group][name], (group, name))
            for name, value in before["service"]["pipelines"].items():
                self.assertEqual(value, after["service"]["pipelines"][name], name)

    def test_envelopes_require_valid_sequence_run_time_and_kind(self):
        m = module()
        for delta in ({"seq": None}, {"seq": True}, {"trial": "bad run"}, {"t_utc": "bad"}, {"kind": "reserved"}):
            p = m.Projector()
            self.assertEqual([], p.project("IBKR", dict(ib("error"), **delta), observed_ms=MILLIS), delta)
            self.assertEqual(1, p.refused)

    def test_account_shapes_in_run_and_session_are_never_exported(self):
        m = module()
        token = "DU" + str(10**6 + 23)
        p = m.Projector()
        self.assertEqual([], p.project("IBKR", ib("error", trial=token), observed_ms=MILLIS))
        row = p.project("IBKR", ib("error", session=token), observed_ms=MILLIS)[0]
        self.assertNotIn("session", row)
        row = p.project("C", calc("preflight_ok", clock=token.lower()), run="sample", observed_ms=MILLIS)[0]
        self.assertEqual("OTHER", row["clock"])
        row = p.project("C", calc("final_flat", realized_usd={}), run="sample", observed_ms=MILLIS)[0]
        self.assertEqual(0, row["realized_total_usd"])

    def test_public_append_refuses_invalid_optional_envelope_values(self):
        m = module()
        row = m.Projector().project("C", calc("flatten_done"), run="sample", observed_ms=MILLIS)[0]
        with tempfile.TemporaryDirectory() as scratch:
            for delta in ({"seq": 1}, {"session": "bad session"}, {"calc_version": "bad"}, {"event_key": "bad"}):
                p = m.Projector()
                self.assertFalse(p.append(Path(scratch) / "live.jsonl", [dict(row, **delta)]), delta)
                self.assertEqual(1, p.refused)

    def test_pending_append_recovers_after_checkpoint_replace_failure(self):
        m = module()
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            journal, spool, state = root / "journal.jsonl", root / "live.jsonl", root / "state"
            journal.write_text(json.dumps(ib("error", code=1)) + "\n")
            tailer = m.Tailer(state, spool)
            real_replace = os.replace
            def failing_replace(source, target):
                if Path(target).name == "checkpoint.json":
                    raise OSError("synthetic storage failure")
                return real_replace(source, target)
            with mock.patch.object(m.os, "replace", failing_replace):
                with self.assertRaises(OSError):
                    tailer.poll("IBKR", journal, observed_ms=MILLIS)
            first_bytes = spool.read_bytes()
            recovered = m.Tailer(state, spool)
            recovered.poll("IBKR", journal, observed_ms=MILLIS + 1)
            self.assertEqual(first_bytes, spool.read_bytes())
            self.assertFalse((state / "pending.json").exists())

    def test_partial_line_waits_and_unknown_kind_refuses_once(self):
        m = module()
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            journal, spool, state = root / "journal.jsonl", root / "live.jsonl", root / "state"
            journal.write_text(json.dumps(ib("error", code=1)))
            t = m.Tailer(state, spool)
            t.poll("IBKR", journal, observed_ms=MILLIS)
            self.assertFalse(spool.exists())
            with journal.open("a") as stream:
                stream.write("\n" + json.dumps(ib("reserved")) + "\n")
            self.assertEqual(1, t.poll("IBKR", journal, observed_ms=MILLIS)["refused"])
            self.assertEqual(1, m.Tailer(state, spool).poll("IBKR", journal, observed_ms=MILLIS)["refused"])
            self.assertEqual(1, len(spool.read_text().splitlines()))

    @unittest.skipUnless(shutil.which("otelcol-contrib"), "native contrib0.162.0 is required")
    def test_native_collector_exports_only_live_resource_labels_and_json_body(self):
        import yaml
        m = module()
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            spool, output, harness = root / "trading-lanes/live.jsonl", root / "export.jsonl", root / "harness.yaml"
            row = m.Projector().project("IBKR", ib("submit", order_id=12, symbol="BRK.B", qty=2), observed_ms=MILLIS)[0]
            spool.parent.mkdir()
            # An input canary checks the independent Collector privacy boundary.
            spool.write_text(json.dumps(dict(row, extra_canary="suppressed")) + "\n")
            harness.write_text(yaml.safe_dump({
                "extensions": {"file_storage": {"directory": str(root / "queue"), "create_directory": True}},
                "processors": {"memory_limiter": {"check_interval": "1s", "limit_mib": 64}, "batch": {"timeout": "100ms"}},
                "exporters": {"file/fixture": {"path": str(output), "flush_interval": "100ms"}},
                "service": {"extensions": ["file_storage"], "telemetry": {"metrics": {"level": "none"}, "logs": {"level": "error"}},
                            "pipelines": {"logs/trading_live": {"exporters": ["file/fixture"]}}},
            }))
            process = subprocess.Popen(["otelcol-contrib", "--config=" + str(ROOT / "observability/trading-live-collector.yaml"),
                                        "--config=" + str(harness)], env=dict(os.environ, NS2604_OBSERVABILITY_DATA=scratch),
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline and process.poll() is None:
                    if output.exists() and output.stat().st_size:
                        break
                    time.sleep(.05)
            finally:
                process.terminate()
                stdout, stderr = process.communicate(timeout=10)
            self.assertEqual(0, process.returncode, stderr[-2000:])
            records = [json.loads(s) for s in output.read_text().splitlines()]
            resources = [r for item in records for r in item["resourceLogs"]]
            self.assertEqual(1, len(resources))
            attrs = {a["key"]: a["value"]["stringValue"] for a in resources[0]["resource"]["attributes"]}
            self.assertEqual({"service.name": "trading-lanes", "stream": "live"}, attrs)
            log = resources[0]["scopeLogs"][0]["logRecords"][0]
            self.assertEqual(row, json.loads(log["body"]["stringValue"]))
            self.assertFalse(log.get("attributes"))
            self.assertNotIn("extra_canary", output.read_text())

    def test_cli_discovers_only_named_source_files_and_is_restart_safe(self):
        m = module()
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            journal = root / "sample/events/ibkr-events.jsonl"
            journal.parent.mkdir(parents=True)
            journal.write_text(json.dumps(ib("error", code=1)) + "\n")
            index = root / "events-index.jsonl"
            index.write_text(json.dumps({"journal": str(journal), "state_dir": str(journal.parents[1])}) + "\n")
            c = root / "calc/run-sample/events.jsonl"
            c.parent.mkdir(parents=True)
            c.write_text(json.dumps(calc("final_flat", fills=0, orders=0)) + "\n")
            spool = root / "live.jsonl"
            args = ["--state", str(root / "state"), "--spool", str(spool), "--ibkr-index", str(index),
                    "--calc-root", str(root / "calc")]
            self.assertEqual(0, m.main(args))
            initial = spool.read_bytes()
            self.assertEqual(0, m.main(args))
            self.assertEqual(initial, spool.read_bytes())
            self.assertEqual({"IBKR", "C"}, {r["lane"] for r in map(json.loads, spool.read_text().splitlines())})

    def test_addendum_timestamp_bounds_signed_age_and_offset_row_ids(self):
        m = module()
        for stamp in ("2017-01-01T00:00:00Z", "2101-01-01T00:00:00Z"):
            p = m.Projector()
            self.assertEqual([], p.project("IBKR", ib("error", t_utc=stamp), observed_ms=MILLIS))
        row = m.Projector().project("IBKR", ib("submit", pricing_observation={"arrival_utc": "2026-10-14T12:00:01Z"}),
                                    observed_ms=MILLIS, source_offset=123)[0]
        self.assertEqual(-1000, row["quote_age_ms"])
        self.assertEqual("sample:123", row["row_id"])
        row = m.Projector().project("IBKR", ib("submit", pricing_observation={"arrival_utc": "2101-01-01T00:00:00Z"}),
                                    observed_ms=MILLIS)[0]
        self.assertNotIn("quote_arrival_ms", row)
        rows = m.Projector().project("C", calc("rank_round", rows=[{"symbol": "BRK.B"}, {"symbol": "IBM"}]),
                                     run="sample", observed_ms=MILLIS, source_offset=64)
        self.assertEqual(["sample:64", "sample:64:0", "sample:64:1"], [r["row_id"] for r in rows])
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            journal = root / "journal.jsonl"
            line = json.dumps(ib("error", code=1)) + "\n"
            journal.write_text(line + line)
            m.Tailer(root / "state", root / "live.jsonl").poll("IBKR", journal, observed_ms=MILLIS)
            actual = [json.loads(s)["row_id"] for s in (root / "live.jsonl").read_text().splitlines()]
            self.assertEqual(["sample:0", "sample:" + str(len(line.encode()))], actual)

    @unittest.skipUnless(shutil.which("loki"), "native Loki3.7.8 is required")
    def test_native_loki_indexes_only_service_and_live_stream(self):
        import yaml
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            sockets = [socket.socket(), socket.socket()]
            for sock in sockets:
                sock.bind(("127.0.0.1", 0))
            http_port, grpc_port = [s.getsockname()[1] for s in sockets]
            for sock in sockets:
                sock.close()
            config = yaml.safe_load((ROOT / "evidence/artifacts/new-wsl-install-plan-20261002/config/loki.yaml").read_text())
            config["server"].update(http_listen_port=http_port, grpc_listen_port=grpc_port, log_level="error")
            config["common"]["path_prefix"] = str(root / "data")
            config["pattern_ingester"]["enabled"] = False
            policy = yaml.safe_load((ROOT / "observability/trading-live-loki.yaml").read_text())
            config["limits_config"].update(policy["limits_config"])
            path = root / "loki.yaml"
            path.write_text(yaml.safe_dump(config))
            process = subprocess.Popen(["loki", "-config.file=" + str(path)], cwd=root,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            url = "http://127.0.0.1:" + str(http_port)
            try:
                deadline = time.monotonic() + 30
                ready = False
                while time.monotonic() < deadline and process.poll() is None:
                    try:
                        with urllib.request.urlopen(url + "/ready", timeout=.5) as response:
                            ready = response.status == 200
                        if ready:
                            break
                    except OSError:
                        time.sleep(.1)
                self.assertTrue(ready, "isolated Loki did not become ready")
                now = time.time_ns()
                body = json.dumps({"lane": "IBKR", "kind": "submit", "symbol": "BRK.B", "order_key": "sample/o1"})
                payload = {"resourceLogs": [{"resource": {"attributes": [
                    {"key": "service.name", "value": {"stringValue": "trading-lanes"}},
                    {"key": "stream", "value": {"stringValue": "live"}}]},
                    "scopeLogs": [{"scope": {"name": "trading-live"}, "logRecords": [{"timeUnixNano": str(now),
                        "observedTimeUnixNano": str(now), "body": {"stringValue": body}}]}]}]}
                request = urllib.request.Request(url + "/otlp/v1/logs", data=json.dumps(payload).encode(),
                                                 headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(request, timeout=5) as response:
                    self.assertIn(response.status, (200, 204))
                query = urllib.parse.urlencode({"match[]": '{service_name="trading-lanes",stream="live"}',
                                                "start": str(now - 10**9), "end": str(now + 10**9)})
                with urllib.request.urlopen(url + "/loki/api/v1/series?" + query, timeout=5) as response:
                    series = json.load(response)["data"]
                self.assertEqual([{"service_name": "trading-lanes", "stream": "live"}], series)
            finally:
                process.terminate()
                try:
                    process.communicate(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.communicate(timeout=5)


if __name__ == "__main__":
    unittest.main()
