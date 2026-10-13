"""PRE/POST public admission and native lifecycle wiring, SYN external I/O.

Transport reference: alpaca-py 0.44.0 at cc4cb3b7ba50ae250e621983c2779047fb16bb28,
alpaca/trading/requests.py:346-364,509-536 (LIMIT, DAY and extended_hours).
Native engine reference: NAS d8f7e205 runner.load_config, sessions.session_at,
leverage.CANONICAL_V1_BLOCK/LeveragePolicy; no broker call is made by this suite.
"""
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import tests.test_paper_deployment as baseline

PAPER = baseline.PAPER
load_json = baseline.load_json

sys.path.insert(0, str(PAPER))
import paper_deployment as d


class ExtendedAdmission(unittest.TestCase):
    scratch = baseline.DeploymentContract.scratch
    account_proof = baseline.DeploymentContract.account_proof

    def plan(self, root):
        bundle = Path(root) / "bundle"
        d.build(bundle, deployment="prepost", order=["pre-1x", "post-1x"])
        return d.Deployment(bundle, Path(root) / "exploratory")

    def ready(self, plan, stage, trial, stamp):
        value = {**d.LABEL, "status": "ready", "deployment": plan.deployment,
                 "stage": stage, "trial": trial, "bundle_sha256": plan.bundle_hash(),
                 "config_sha256": plan.stage(stage)["config_sha256"], "observed_at": stamp,
                 "session_kind": plan.stage(stage)["session_kind"], "session_date": "2026-10-13",
                 "flat": True, "positions": [], "open_orders": [], "native_preflight": True,
                 "writer_lock_checked": True, "account_commitment": self.account_proof(plan, trial)}
        d.save(plan.instance(trial) / "readiness.json", value)

    def test_pre_and_post_build_native_extended_one_x_configs(self):
        # Native alpaca-py LimitOrderRequest exposes extended_hours and DAY;
        # session/1x ceilings are enforced by the existing NAS engine.
        from runner import load_config
        from sessions import order_extended_hours_flag, validate_session_policy
        from alpaca.trading.requests import LimitOrderRequest
        from alpaca.trading.enums import OrderSide, TimeInForce, OrderType
        with self.scratch() as root:
            plan = self.plan(root)
            for stage, timestamp in [("pre-1x", "2026-10-13T08:00:00+00:00"),
                                     ("post-1x", "2026-10-13T20:00:00+00:00")]:
                cfg, limits, policy = load_config(plan.config_path(stage))
                self.assertTrue(cfg["extended_hours_enabled"])
                self.assertFalse(cfg["regular_session_only"])
                self.assertFalse(cfg["sessions"]["overnight_holds"])
                self.assertEqual(cfg["max_leverage"], "1")
                self.assertEqual(limits.max_gross_exposure_usd, Decimal("10000"))
                self.assertTrue(order_extended_hours_flag(datetime.fromisoformat(timestamp), validate_session_policy(cfg)))
                order = LimitOrderRequest(symbol="SPY", qty=1, side=OrderSide.BUY,
                                          time_in_force=TimeInForce.DAY, limit_price=100,
                                          extended_hours=True)
                self.assertEqual(order.type, OrderType.LIMIT)
                self.assertEqual(order.time_in_force, TimeInForce.DAY)
                self.assertTrue(order.extended_hours)
                for regime, want in [("trend", Decimal("1")), ("range", Decimal("1")), ("risk_off", Decimal("0"))]:
                    self.assertEqual(cfg["_leverage_policy"].ceiling(session=plan.stage(stage)["session_kind"],
                        regime=regime, drawdown_fraction=Decimal("0"), kill_switch=False), want)
            self.assertEqual(plan.config("pre-1x"), plan.config("post-1x"))
            self.assertEqual(plan.native_state(), Path(root) / "exploratory/account-state")
            self.assertEqual(plan.stage("pre-1x")["state_namespace"], plan.stage("post-1x")["state_namespace"])
            plan.verify()

    def test_custom_alias_one_x_admission_and_namespace_keep_same_journal(self):
        with self.scratch() as root:
            config = Path(root) / "source.json"
            value = load_json(PAPER / "config-leverage-1x.json")
            config.write_text(json.dumps(value))
            specs = {name: {"engine_kind": "adaptive", "session_kind": session, "config": str(config)}
                     for name, session in [("early", "PRE"), ("late", "POST")]}
            d.build(Path(root) / "bundle", deployment="custom", order=list(specs), stage_specs=specs)
            plan = d.Deployment(Path(root) / "bundle", Path(root) / "exploratory")
            self.assertEqual(plan.native_state(), Path(root) / "exploratory/account-state")
            fingerprint = "a" * 64
            state = plan.native_state() / fingerprint / "adaptive/trial.json"
            d.save(state, {"phase": "finished", "config_sha256": plan.stage("early")["config_sha256"]})
            self.assertEqual(plan.namespace_ready("late", fingerprint), "matching_native_namespace")
            before = state.read_bytes()
            self.assertEqual(plan.namespace_ready("early", fingerprint), "matching_native_namespace")
            self.assertEqual(state.read_bytes(), before)

    def test_pre_post_go_native_cli_recover_and_serial_handoff(self):
        # External dispatch alone is intercepted. Native config parsing,
        # CLI spelling, session/GO/flat/recovery bindings execute normally.
        with self.scratch() as root, patch.object(d, "lane_a_absent", return_value=True):
            plan = self.plan(root)
            calls = []
            def native(mode, stage, trial, output):
                argv = plan.engine_arguments(mode, stage, trial, "SYN-loader-placeholder")
                self.assertEqual(argv[:2], ["runner.py", mode])
                self.assertEqual(Path(argv[argv.index("--state-root") + 1]), plan.native_state())
                self.assertEqual(Path(argv[argv.index("--config") + 1]), plan.config_path(stage))
                self.assertEqual(argv[argv.index("--trial") + 1], trial)
                calls.append((mode, stage, trial))
                d.save(output, {"status": "passed", "flat": True, "positions": [], "unresolved_orders": [],
                                "reconciliation": {"positions": 0, "open_orders": 0}})
                return 0
            with patch.object(plan, "native_call", side_effect=native):
                pre_time = datetime(2026, 10, 13, 8, 0, tzinfo=timezone.utc).timestamp()
                self.ready(plan, "pre-1x", "pre-trial", pre_time)
                plan.issue("pre-1x", "pre-trial", previous=None, now=pre_time)
                self.assertEqual(plan.run("pre-1x", now=pre_time), 0)
                self.assertEqual(plan.recover("pre-trial", now=pre_time + 1320), 0)
                prior = load_json(plan.instance("pre-trial") / "handoff.json")
                self.assertTrue(prior["flat"])
                self.assertEqual(prior["positions"], 0)
                self.assertEqual(prior["open_orders"], 0)
                post_time = datetime(2026, 10, 13, 20, 0, tzinfo=timezone.utc).timestamp()
                self.ready(plan, "post-1x", "post-trial", post_time)
                plan.issue("post-1x", "post-trial", previous="pre-trial", now=post_time)
                self.assertEqual(plan.run("post-1x", now=post_time), 0)
                self.assertEqual(plan.recover("post-trial", now=post_time + 1320), 0)
                self.assertFalse(any((plan.state / "active").glob("*.json")))
                self.assertEqual(load_json(plan.instance("post-trial") / "handoff.json")["evidence_class"], "exploratory")
            self.assertEqual(calls, [("paper", "pre-1x", "pre-trial"), ("recover", "pre-1x", "pre-trial"),
                                     ("paper", "post-1x", "post-trial"), ("recover", "post-1x", "post-trial")])

    def test_pre_post_wrong_session_late_window_and_unsafe_configs_refuse(self):
        with self.scratch() as root:
            plan = self.plan(root)
            at_rth = datetime(2026, 10, 13, 15, 0, tzinfo=timezone.utc).timestamp()
            for stage in plan.order:
                with self.assertRaisesRegex(d.Refused, "^venue_session_not_ready$"): plan.session(stage, at_rth)
            for stage, stamp in [("pre-1x", "2026-10-13T13:00:00+00:00"),
                                 ("post-1x", "2026-10-13T23:30:00+00:00")]:
                with self.assertRaisesRegex(d.Refused, "^insufficient_session_time$"):
                    plan.session(stage, datetime.fromisoformat(stamp).timestamp())
            config = plan.config("pre-1x")
            for key, value in [("max_leverage", "2"), ("max_gross_exposure_usd", "20000"),
                               ("max_order_notional_usd", "2000"), ("max_gross_loss_usd", "50"),
                               ("max_drawdown_usd", "50"), ("max_order_quantity", 101)]:
                with self.subTest(key=key), self.assertRaisesRegex(d.Refused, "^unregistered_sizing_setting$"):
                    d.validate_sizing_and_scope(dict(config, **{key: value}), "adaptive", "PRE")
            with self.assertRaisesRegex(d.Refused, "^unregistered_sizing_setting$"):
                d.validate_sizing_and_scope(config, "adaptive", "RTH")
            with self.assertRaisesRegex(d.Refused, "^unsupported_overnight_policy$"):
                d.validate_sizing_and_scope(dict(config, sessions=dict(config["sessions"], overnight_holds=True)), "adaptive", "PRE")
            from copy import deepcopy
            changed = deepcopy(config); changed["leverage_policy"]["schedule"]["PRE"]["trend"] = "2"
            with self.assertRaisesRegex(d.Refused, "^unregistered_sizing_setting$"):
                d.validate_sizing_and_scope(changed, "adaptive", "PRE")
            changed = dict(config, extended_hours_enabled=False)
            with self.assertRaisesRegex(d.Refused, "^extended_session_config_required$"):
                d.validate_sizing_and_scope(changed, "adaptive", "POST")

    def test_failed_pre_recovery_cannot_hand_account_to_post(self):
        with self.scratch() as root, patch.object(d, "lane_a_absent", return_value=True):
            plan = self.plan(root)
            pre_time = datetime(2026, 10, 13, 8, 0, tzinfo=timezone.utc).timestamp()
            self.ready(plan, "pre-1x", "failed-pre", pre_time)
            plan.issue("pre-1x", "failed-pre", previous=None, now=pre_time)
            def native(mode, stage, trial, output):
                d.save(output, {"status": "needs_attention", "flat": False, "positions": [{}],
                                "unresolved_orders": [], "reconciliation": {"positions": 1, "open_orders": 0}})
                return 3
            with patch.object(plan, "native_call", side_effect=native):
                plan.run("pre-1x", now=pre_time)
                with self.assertRaisesRegex(d.Refused, "^recovery_not_flat$"):
                    plan.recover("failed-pre", now=pre_time + 1320)
            post_time = datetime(2026, 10, 13, 20, 0, tzinfo=timezone.utc).timestamp()
            self.ready(plan, "post-1x", "blocked-post", post_time)
            with self.assertRaisesRegex(d.Refused, "^STOP_present$"):
                plan.issue("post-1x", "blocked-post", previous="failed-pre", now=post_time)
            self.assertFalse((plan.slot("post-1x") / "GO.sha256").exists())
            self.assertTrue(plan.active_path("failed-pre").exists())


if __name__ == "__main__":
    unittest.main()
