"""Exploratory deployment public seams; no credentials, endpoints or host units."""
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

PAPER = Path(__file__).resolve().parents[1] / "blueprints/us-equities/adaptive-paper"
sys.path.insert(0, str(PAPER))


class DeploymentContract(unittest.TestCase):
    def test_old_native_state_cannot_rotate_config_before_go(self):
        import paper_deployment as deployment
        from unittest.mock import patch
        with tempfile.TemporaryDirectory(dir="/var/tmp") as directory:
            plan = self.plan(directory)
            fingerprint = "a" * 64
            metadata = plan.native_state() / fingerprint / "adaptive" / "trial.json"
            deployment.save(metadata, {"phase": "finished", "config_sha256": "0" * 64})
            with self.assertRaisesRegex(deployment.Refused, "rotation_source_not_ready"):
                plan.namespace_ready("lev4", fingerprint)
            deployment.save(metadata, {"phase": "running", "config_sha256": plan.stage("lev4")["config_sha256"]})
            with self.assertRaisesRegex(deployment.Refused, "existing_native_trial_requires_recovery"):
                plan.namespace_ready("lev4", fingerprint)
            self.assertFalse((plan.slot("lev4") / "GO.sha256").exists())

    def test_units_dispatch_only_after_go_and_bound_trial_cleanup(self):
        import paper_deployment as deployment
        with tempfile.TemporaryDirectory(dir="/var/tmp") as directory:
            root = Path(directory)
            deployment.build(root, deployment="mover-units", order=["mover1", "postmover1"])
            units = sorted((root / "units").glob("*"))
            self.assertEqual(len(units), 4)
            service = next(p for p in units if p.suffix == ".service")
            body = service.read_text()
            for directive in ["RuntimeMaxSec=1500s", "TimeoutStopSec=900s", "CPUWeight=50", "UMask=0077",
                              "ExecCondition=/usr/bin/sha256sum --strict --quiet -c SHA256SUMS"]:
                self.assertIn(directive, body)
            self.assertIn("deployment_issue_go.py run", body)
            self.assertIn("paper_deployment.py recover", body)
            self.assertNotIn("CPUQuota", body)
            for path in (root / "units").glob("*.path"):
                self.assertIn("/GO.sha256", path.read_text())
                self.assertNotIn("OnCalendar=", path.read_text())

    def test_scan_commitment_is_verified_before_ready_and_consumed_with_go(self):
        import paper_deployment as deployment
        from unittest.mock import patch
        with tempfile.TemporaryDirectory(dir="/var/tmp") as directory:
            root = Path(directory)
            deployment.build(root, deployment="mover-scan", order=["mover1"])
            plan = deployment.Deployment(root, root / "exploratory")
            now = datetime(2026, 10, 12, 15, 0, tzinfo=timezone.utc).timestamp()
            packet = root / "producer"
            row = {"symbol": "SPY", "rank": 1, "price_at_t": "100",
                   "dollar_volume_at_t": "10000000", "entry_bar_dollar_volume": "1000000", "gain_pct_at_t": "25"}
            deployment.save(packet / "scan.json", {"schema_version": 1, "kind": "mover_scan",
                "protocol": "mover-early-entry-v1-20260924", "rule": "10:00|G20|V1000000|any",
                "scan_time": "2026-10-12T15:00:00Z", "symbols": [row]})
            deployment.save(packet / "ranked-100.json", {**deployment.LABEL, "symbols": [row]})
            deployment.save(packet / "input.json", {**deployment.LABEL, "observed_at": "2026-10-12T15:00:00Z"})
            commitment = {**deployment.LABEL, "config_sha256": plan.stage("mover1")["config_sha256"],
                          "scan_sha256": deployment.digest(packet / "scan.json"),
                          "ranked_sha256": deployment.digest(packet / "ranked-100.json"),
                          "input_sha256": deployment.digest(packet / "input.json"),
                          "code_sha256": "a" * 64, "observed_at": "2026-10-12T15:00:00Z",
                          "session_date": "2026-10-12"}
            deployment.save(packet / "commitment.json", commitment)
            with patch.object(deployment, "lane_a_absent", return_value=True):
                ready = plan.publish_scan("mover1", packet, now=now)
                self.assertEqual(ready["engine_scan_sha256"], commitment["scan_sha256"])
                self.assertFalse((plan.slot("mover1") / "GO.sha256").exists())
                (packet / "ranked-100.json").write_text("{}")
                with self.assertRaisesRegex(deployment.Refused, "commitment_hash_mismatch"):
                    plan.publish_scan("mover1", packet, now=now)

    def test_mover_rungs_and_after_hours_use_native_validated_caps(self):
        import paper_deployment as deployment
        from mover import load_mover_config
        with tempfile.TemporaryDirectory(dir="/var/tmp") as directory:
            root = Path(directory)
            deployment.build(root, deployment="mover-one", order=["mover4", "mover2", "mover1", "postmover1"])
            plan = deployment.Deployment(root, root / "exploratory")
            for stage in plan.order:
                config, limits, settings = load_mover_config(plan.config_path(stage))
                self.assertEqual(plan.stage(stage)["engine_kind"], "mover")
                self.assertEqual(settings.session_scope, "any_session")
                self.assertEqual(config["duration_seconds"], 1200)
                self.assertLessEqual(limits.max_order_notional_usd, 10000)
                self.assertLessEqual(settings.max_entry_notional_usd, 1000)
                self.assertEqual(settings.max_symbols, 5)
            self.assertEqual(plan.stage("postmover1")["session_kind"], "POST")
            self.assertEqual(plan.config("postmover1")["mover"]["rule"], "16:05|G20|V1000000|any")

    def test_failed_recover_stop_and_short_post_window_refuse(self):
        import paper_deployment as deployment
        from unittest.mock import patch
        with tempfile.TemporaryDirectory(dir="/var/tmp") as directory:
            plan = self.plan(directory)
            for stamp in [datetime(2026, 10, 12, 19, 50, tzinfo=timezone.utc).timestamp(),
                          datetime(2026, 10, 13, 0, 50, tzinfo=timezone.utc).timestamp()]:
                with self.assertRaises(deployment.Refused):
                    plan.issue("lev4" if datetime.fromtimestamp(stamp, timezone.utc).hour == 19 else "post1",
                               "late-trial", previous=None, now=stamp, check_only=True)
            now = datetime(2026, 10, 12, 15, 0, tzinfo=timezone.utc).timestamp()
            deployment.save(plan.active_path("failed-trial"), {
                **deployment.LABEL, "stage": "lev4", "trial": "failed-trial",
                "bundle_sha256": plan.bundle_hash(), "config_sha256": plan.stage("lev4")["config_sha256"]})
            def fail(mode, stage, trial, output):
                deployment.save(output, {"status": "needs_attention", "flat": False, "positions": [{}],
                                         "unresolved_orders": [], "reconciliation": {"positions": 1, "open_orders": 0}})
                return 3
            with patch.object(plan, "native_call", side_effect=fail):
                with self.assertRaisesRegex(deployment.Refused, "recovery_not_flat"):
                    plan.recover("failed-trial", now=now)
            self.assertTrue((plan.state.parent / "STOP").exists())
            self.assertTrue(plan.active_path("failed-trial").exists())

    def test_native_result_is_labelled_and_private_fields_are_not_published(self):
        import paper_deployment as deployment
        private = {"status": "passed", "account_identity_sha256": "a" * 64,
                   "source": str(Path.home() / "private-state"), "nested": {"account_id": "fixture"}}
        result = deployment.public_result(private)
        self.assertEqual(result["paper_lane"], "B")
        self.assertEqual(result["evidence_class"], "exploratory")
        self.assertNotIn("account_identity_sha256", json.dumps(result))
        self.assertNotIn("account_id", json.dumps(result))
        self.assertNotIn(str(Path.home()), json.dumps(result))

    def test_issuer_to_native_trial_recover_and_next_order_uses_explicit_trial(self):
        import paper_deployment as deployment
        from unittest.mock import patch
        with tempfile.TemporaryDirectory(dir="/var/tmp") as directory:
            plan = self.plan(directory)
            now = datetime(2026, 10, 12, 15, 0, tzinfo=timezone.utc).timestamp()
            calls = []
            def native(mode, stage, trial, output):
                calls.append((mode, stage, trial))
                value = {"status": "passed", "flat": True, "positions": [], "unresolved_orders": [],
                         "reconciliation": {"positions": 0, "open_orders": 0}}
                deployment.save(output, value)
                return 0
            def proof(stage, trial, stamp):
                deployment.save(plan.instance(trial) / "readiness.json", {
                    **deployment.LABEL, "status": "ready", "deployment": "explore-one",
                    "stage": stage, "trial": trial, "bundle_sha256": plan.bundle_hash(),
                    "config_sha256": plan.stage(stage)["config_sha256"], "observed_at": stamp,
                    "session_kind": "RTH", "session_date": "2026-10-12", "flat": True,
                    "positions": [], "open_orders": [], "native_preflight": True, "writer_lock_checked": True})
            with patch.object(deployment, "lane_a_absent", return_value=True), \
                    patch.object(plan, "native_call", side_effect=native):
                proof("lev4", "pass-two-first", now)
                plan.issue("lev4", "pass-two-first", previous=None, now=now)
                self.assertEqual(plan.run("lev4", now=now), 0)
                self.assertEqual(plan.recover("pass-two-first", now=now + 1200), 0)
                handoff = json.loads((plan.instance("pass-two-first") / "handoff.json").read_text())
                self.assertEqual(handoff["paper_lane"], "B")
                self.assertTrue(handoff["flat"])
                next_time = now + 1261
                proof("lev2", "pass-two-second", next_time)
                result = plan.issue("lev2", "pass-two-second", previous="pass-two-first",
                                    now=next_time, check_only=True)
                self.assertEqual(result["status"], "ready")
                with self.assertRaises(deployment.Refused):
                    plan.issue("lev2", "pass-two-second", previous="another-pass",
                               now=next_time, check_only=True)
            self.assertEqual(calls, [("paper", "lev4", "pass-two-first"),
                                     ("recover", "lev4", "pass-two-first")])

    def plan(self, directory):
        import paper_deployment
        root = Path(directory)
        paper_deployment.build(root, deployment="explore-one", order=["lev4", "lev2", "lev1", "post1"])
        return paper_deployment.Deployment(root, root / "exploratory")

    def test_native_observation_is_fresh_flat_budgeted_and_never_exposes_account(self):
        import paper_deployment as deployment
        from unittest.mock import patch
        with tempfile.TemporaryDirectory(dir="/var/tmp") as directory:
            plan = self.plan(directory)
            now = datetime(2026, 10, 12, 15, 0, tzinfo=timezone.utc).timestamp()
            called = []
            def native_read(before_request, **kwargs):
                before_request("read")
                called.append(True)
                return {"account_identity_sha256": "a" * 64, "positions": [], "orders": [],
                        "open_orders_complete": True, "ready": True}
            with patch.object(deployment, "native_flat_observation", side_effect=native_read), \
                    patch.object(deployment, "lane_a_absent", return_value=True), \
                    patch.object(deployment, "account_writer",
                                 side_effect=lambda _: deployment.exclusive(Path(directory) / "SYN-account.lock")):
                proof = plan.observe("lev4", "native-proof", now=now)
            self.assertEqual(len(called), 2)
            self.assertTrue(proof["native_preflight"])
            self.assertTrue(proof["writer_lock_checked"])
            self.assertEqual(proof["request_count"], 2)
            self.assertNotIn("account_identity_sha256", json.dumps(proof))
            self.assertNotIn(str(Path.home()), json.dumps(proof))
            self.assertEqual(proof["paper_lane"], "B")
            self.assertEqual(proof["evidence_class"], "exploratory")

    def test_standing_lane_b_issue_requires_fresh_first_trial_flat_read(self):
        import paper_deployment as deployment
        from unittest.mock import patch
        with tempfile.TemporaryDirectory(dir="/var/tmp") as directory:
            plan = self.plan(directory)
            now = datetime(2026, 10, 12, 15, 0, tzinfo=timezone.utc).timestamp()
            proof = {**deployment.LABEL, "status": "ready", "deployment": "explore-one",
                     "stage": "lev4", "trial": "first-trial",
                     "bundle_sha256": plan.bundle_hash(), "config_sha256": plan.stage("lev4")["config_sha256"],
                     "observed_at": now, "session_kind": "RTH", "session_date": "2026-10-12",
                     "flat": True, "positions": [], "open_orders": [], "request_count": 9,
                     "native_preflight": True, "writer_lock_checked": True}
            deployment.save(plan.instance("first-trial") / "readiness.json", proof)
            with patch.object(deployment, "lane_a_absent", return_value=True):
                result = plan.issue("lev4", "first-trial", previous=None, now=now, check_only=True)
                self.assertEqual(result["status"], "ready")
                self.assertFalse((plan.slot("lev4") / "GO.sha256").exists())
                for delta in (31, -1):
                    with self.assertRaisesRegex(deployment.Refused, "readiness_stale"):
                        plan.issue("lev4", "first-trial", previous=None, now=now + delta, check_only=True)
                for field, value in (("flat", False), ("positions", [{"symbol": "SPY", "qty": "1"}]),
                                     ("open_orders", [{"symbol": "SPY"}])):
                    deployment.save(plan.instance("first-trial") / "readiness.json", {**proof, field: value})
                    with self.assertRaisesRegex(deployment.Refused, "account_not_flat"):
                        plan.issue("lev4", "first-trial", previous=None, now=now, check_only=True)
                deployment.save(plan.instance("first-trial") / "readiness.json", proof)
                result = plan.issue("lev4", "first-trial", previous=None, now=now)
                self.assertEqual(result["paper_lane"], "B")
                self.assertEqual(result["evidence_class"], "exploratory")
                self.assertTrue((plan.slot("lev4") / "GO.sha256").is_file())
                self.assertNotIn(str(Path.home()), json.dumps(result))

    def test_counterbalanced_order_and_post_are_deployment_inputs(self):
        import paper_deployment
        with tempfile.TemporaryDirectory(dir="/var/tmp") as directory:
            root = Path(directory)
            paper_deployment.build(root, deployment="explore-one", order=["lev4", "lev2", "lev1", "post1"])
            plan = paper_deployment.Deployment(root, root / "exploratory")
            self.assertEqual(plan.order, ["lev4", "lev2", "lev1", "post1"])
            self.assertEqual(plan.stage("post1")["session_kind"], "POST")
            self.assertEqual(plan.stage("lev4")["duration_seconds"], 1200)
            self.assertEqual(plan.stage("lev4")["runtime_max_seconds"], 1500)
            self.assertEqual(plan.manifest["paper_lane"], "B")
            self.assertEqual(plan.manifest["evidence_class"], "exploratory")
            for stage in plan.order:
                config = plan.config(stage)
                self.assertEqual(config["max_order_quantity"], 100)
                self.assertEqual(config["max_order_qty_mode"], "notional")
                self.assertEqual(config["duration_seconds"], 1200)
            self.assertTrue(plan.config("post1")["sessions"]["extended_hours"])
            self.assertFalse(plan.config("post1")["sessions"]["overnight_holds"])


if __name__ == "__main__":
    unittest.main()
