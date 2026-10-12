"""Exploratory deployment public seams; no credentials, endpoints or host units."""
from datetime import datetime, timezone
import importlib.util
import json
import hmac
from pathlib import Path
import sys
import tempfile
import unittest
from contextlib import contextmanager

PAPER = Path(__file__).resolve().parents[1] / "blueprints/us-equities/adaptive-paper"
sys.path.insert(0, str(PAPER))
sys.path.insert(0, str(PAPER.parents[2] / "scripts"))


def load_json(path):
    return json.loads(Path(path).read_bytes())


class DeploymentContract(unittest.TestCase):
    def account_proof(self, plan, trial):
        import paper_deployment as deployment
        account = {"fingerprint": "a" * 64, "salt": "b" * 64}
        deployment.save(plan.instance(trial) / "account.private.json", account)
        return hmac.new(bytes.fromhex(account["salt"]), account["fingerprint"].encode(), deployment.hashlib.sha256).hexdigest()

    def test_sequence_cursor_rejects_older_real_pass_handoff_and_second_successor(self):
        import paper_deployment as deployment
        from unittest.mock import patch
        with self.scratch() as directory:
            plan = self.plan(directory)
            now = datetime(2026, 10, 12, 15, 0, tzinfo=timezone.utc).timestamp()
            def proof(stage, trial):
                deployment.save(plan.instance(trial) / "readiness.json", {
                    **deployment.LABEL, "status": "ready", "deployment": plan.deployment, "stage": stage, "trial": trial,
                    "bundle_sha256": plan.bundle_hash(), "config_sha256": plan.stage(stage)["config_sha256"],
                    "observed_at": now, "session_kind": "RTH", "session_date": "2026-10-12", "flat": True,
                    "positions": [], "open_orders": [], "native_preflight": True, "writer_lock_checked": True,
                    "account_commitment": self.account_proof(plan, trial)})
            with patch.object(deployment, "lane_a_absent", return_value=True):
                proof("lev4", "first")
                plan.issue("lev4", "first", previous=None, now=now)
                proof("lev4", "new-first")
                with self.assertRaisesRegex(deployment.Refused, "sequence_stage_or_trial"):
                    plan.issue("lev4", "new-first", previous=None, now=now)
                # An otherwise valid older handoff is not the durable cursor predecessor.
                proof("lev2", "successor")
                with self.assertRaisesRegex(deployment.Refused, "sequence_stage_or_trial"):
                    plan.issue("lev2", "successor", previous="first", now=now)

    @contextmanager
    def scratch(self):
        import paper_deployment as deployment
        from unittest.mock import patch
        with tempfile.TemporaryDirectory(dir="/var/tmp") as directory, \
                patch.object(deployment, "CANONICAL_STATE", Path(directory) / "exploratory", create=True), \
                patch("safety.DEFAULT_STOP", Path(directory) / "STOP"), \
                patch.object(deployment, "account_writer", side_effect=lambda _: deployment.exclusive(Path(directory) / "SYN-account.lock")):
            yield directory

    def test_symlinked_exploratory_root_and_descendant_never_write_protected_target(self):
        import paper_deployment as deployment
        with self.scratch() as directory:
            root = Path(directory)
            deployment.build(root, deployment="path-root", order=["mover-max"])
            protected = root / "qualification"
            protected.mkdir()
            (root / "exploratory").symlink_to(protected, target_is_directory=True)
            with self.assertRaisesRegex(deployment.Refused, "symlink_path"):
                deployment.Deployment(root, root / "exploratory")
            self.assertEqual(list(protected.iterdir()), [])
            (root / "exploratory").unlink()
            (root / "exploratory").mkdir()
            plan = deployment.Deployment(root, root / "exploratory")
            (plan.state / "deployments").symlink_to(protected, target_is_directory=True)
            with self.assertRaisesRegex(deployment.Refused, "symlink_path"):
                deployment.save(plan.instance("denied") / "readiness.json", {})
            self.assertEqual(list(protected.iterdir()), [])

    def test_changed_native_account_refuses_before_namespace_or_engine_dispatch(self):
        import paper_deployment as deployment
        from unittest.mock import patch
        with self.scratch() as directory:
            plan = self.plan(directory)
            deployment.save(plan.instance("bound") / "account.private.json",
                            {"fingerprint": "a" * 64, "salt": "b" * 64})
            expected = hmac.new(bytes.fromhex("b" * 64), ("a" * 64).encode(), deployment.hashlib.sha256).hexdigest()
            deployment.save(plan.active_path("bound"), {"account_commitment": expected})
            deployment.save(plan.native_state() / ("c" * 64) / "adaptive/trial.json", {
                "phase": "finished", "config_sha256": plan.stage("lev4")["config_sha256"],
                **deployment.LABEL})
            with patch.object(plan, "namespace_ready") as namespace:
                with self.assertRaisesRegex(deployment.Refused, "native_account_binding_mismatch"):
                    plan.check_account("lev4", "bound", {"account_identity_sha256": "c" * 64})
                self.assertEqual(namespace.call_count, 0)

    def test_mover_recover_argv_uses_the_real_parser_without_trial(self):
        import paper_deployment as deployment, mover_runner
        with self.scratch() as directory:
            root = Path(directory)
            deployment.build(root, deployment="parser-mover", order=["mover-max"])
            plan = deployment.Deployment(root, root / "exploratory")
            argv = plan.engine_arguments("recover", "mover-max", "owned", Path(directory) / "SYN-loader")
            parsed = mover_runner.build_parser().parse_args(argv[1:])
            self.assertEqual(parsed.command, "recover")
            self.assertNotIn("--trial", argv)

    def test_recovery_retry_keeps_own_stop_identity_and_finishes_after_native_call(self):
        import paper_deployment as deployment
        from unittest.mock import patch
        with self.scratch() as directory:
            plan = self.plan(directory)
            now = datetime(2026, 10, 12, 15, 0, tzinfo=timezone.utc).timestamp()
            deployment.save(plan.active_path("retry"), {"stage": "lev4", "trial": "retry",
                "bundle_sha256": plan.bundle_hash(), "config_sha256": plan.stage("lev4")["config_sha256"]})
            clock = [now]
            flat = [False]
            def native(mode, stage, trial, output):
                clock[0] += 120
                deployment.save(output, {"status": "passed" if flat[0] else "needs_attention", "flat": flat[0],
                    "positions": [] if flat[0] else [{}], "unresolved_orders": [],
                    "reconciliation": {"positions": 0 if flat[0] else 1, "open_orders": 0}})
                return 0 if flat[0] else 3
            with patch.object(plan, "native_call", side_effect=native), patch.object(deployment.time, "time", side_effect=lambda: clock[0]):
                with self.assertRaisesRegex(deployment.Refused, "recovery_not_flat"): plan.recover("retry")
                flat[0] = True
                self.assertEqual(plan.recover("retry"), 0)
            receipt = json.loads((plan.instance("retry") / "handoff.json").read_text())
            self.assertEqual(receipt["finished_at"], now + 240)
            self.assertFalse((plan.state.parent / "STOP").exists())

    def test_public_native_command_requires_consumed_go_capability(self):
        import paper_deployment as deployment
        from unittest.mock import patch
        with self.scratch() as directory:
            plan = self.plan(directory)
            import runner, credential_status
            with patch.object(credential_status, "expand_template", return_value=Path(directory) / "SYN-loader"), \
                    patch.object(runner, "main", return_value=73) as dispatch:
                with self.assertRaisesRegex(deployment.Refused, "native_launch_capability_missing"):
                    plan.native_child("paper", "lev4", "ungated")
                self.assertEqual(dispatch.call_count, 0)

    def test_old_native_state_cannot_rotate_config_before_go(self):
        import paper_deployment as deployment
        from unittest.mock import patch
        with self.scratch() as directory:
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
        with self.scratch() as directory:
            root = Path(directory)
            deployment.build(root, deployment="mover-units", order=["mover-max"])
            units = sorted((root / "units").glob("*"))
            self.assertEqual(len(units), 2)
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
        with self.scratch() as directory:
            root = Path(directory)
            deployment.build(root, deployment="mover-scan", order=["mover-max"])
            plan = deployment.Deployment(root, root / "exploratory")
            now = datetime(2026, 10, 12, 15, 0, tzinfo=timezone.utc).timestamp()
            packet = root / "producer"
            row = {"symbol": "SPY", "rank": 1, "price_at_t": "100",
                   "dollar_volume_at_t": "10000000", "entry_bar_dollar_volume": "1000000", "gain_pct_at_t": "25"}
            deployment.save(packet / "scan.json", {"schema_version": 1, "kind": "mover_scan",
                "protocol": "mover-early-entry-v1-20260924", "rule": "10:00|G20|V1000000|any",
                "scan_time": "2026-10-12T15:00:00Z", "symbols": [row]})
            deployment.save(packet / "ranked-100.json", {**deployment.LABEL, "symbols": [row]})
            deployment.save(packet / "input.json", {**deployment.LABEL, "source": {
                "mode": "intraday", "signal_cutoff_utc": "2026-10-12T15:00:00Z", "observed_at": "2026-10-12T15:00:00Z"}})
            commitment = {**deployment.LABEL, "config_sha256": plan.stage("mover-max")["config_sha256"],
                          "scan_sha256": deployment.digest(packet / "scan.json"),
                          "ranked_sha256": deployment.digest(packet / "ranked-100.json"),
                          "input_sha256": deployment.digest(packet / "input.json"),
                          "code_sha256": "a" * 64, "observed_at": "2026-10-12T15:00:00Z",
                          "source_observed_at": "2026-10-12T15:00:00Z",
                          "session_date": "2026-10-12"}
            deployment.save(packet / "commitment.json", commitment)
            with patch.object(deployment, "lane_a_absent", return_value=True):
                ready = plan.publish_scan("mover-max", packet, now=now)
                self.assertEqual(ready["engine_scan_sha256"], commitment["scan_sha256"])
                self.assertFalse((plan.slot("mover-max") / "GO.sha256").exists())
                (packet / "ranked-100.json").write_text("{}")
                with self.assertRaisesRegex(deployment.Refused, "commitment_hash_mismatch"):
                    plan.publish_scan("mover-max", packet, now=now)

    def test_mover_alias_rungs_and_unsupported_post_are_refused_by_content(self):
        import paper_deployment as deployment
        from mover import load_mover_config
        with self.scratch() as directory:
            root = Path(directory)
            for stage in ["mover1", "mover2"]:
                with self.assertRaisesRegex(deployment.Refused, "unregistered_sizing_setting"):
                    deployment.build(root / stage, deployment="denied", order=[stage])
            with self.assertRaisesRegex(deployment.Refused, "producer_rule_unsupported"):
                deployment.build(root / "post", deployment="denied", order=["postmover-max"])
            deployment.build(root, deployment="mover-one", order=["mover-max"])
            plan = deployment.Deployment(root, root / "exploratory")
            for stage in plan.order:
                config, limits, settings = load_mover_config(plan.config_path(stage))
                self.assertEqual(plan.stage(stage)["engine_kind"], "mover")
                self.assertEqual(settings.session_scope, "any_session")
                self.assertEqual(config["duration_seconds"], 1200)
                self.assertLessEqual(limits.max_order_notional_usd, 10000)
                self.assertLessEqual(settings.max_entry_notional_usd, 1000)
                self.assertEqual(settings.max_symbols, 5)

    def test_failed_recover_stop_and_short_post_window_refuse(self):
        import paper_deployment as deployment
        from unittest.mock import patch
        with self.scratch() as directory:
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
        with self.scratch() as directory:
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
                value = load_json(plan.instance(trial) / "readiness.json")
                value["account_commitment"] = self.account_proof(plan, trial)
                deployment.save(plan.instance(trial) / "readiness.json", value)
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
        specs = {stage: {"engine_kind": "adaptive", "session_kind": "POST" if stage == "post1" else "RTH",
                         "config": str(PAPER / "config-sip.json")} for stage in ["lev4", "lev2", "lev1", "post1"]}
        paper_deployment.build(root, deployment="explore-one", order=list(specs), stage_specs=specs)
        return paper_deployment.Deployment(root, root / "exploratory")

    def test_native_observation_is_fresh_flat_budgeted_and_never_exposes_account(self):
        import paper_deployment as deployment
        from unittest.mock import patch
        with self.scratch() as directory:
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
        with self.scratch() as directory:
            plan = self.plan(directory)
            now = datetime(2026, 10, 12, 15, 0, tzinfo=timezone.utc).timestamp()
            proof = {**deployment.LABEL, "status": "ready", "deployment": "explore-one",
                     "stage": "lev4", "trial": "first-trial",
                     "bundle_sha256": plan.bundle_hash(), "config_sha256": plan.stage("lev4")["config_sha256"],
                     "observed_at": now, "session_kind": "RTH", "session_date": "2026-10-12",
                     "flat": True, "positions": [], "open_orders": [], "request_count": 9,
                     "native_preflight": True, "writer_lock_checked": True}
            proof["account_commitment"] = self.account_proof(plan, "first-trial")
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
        with self.scratch() as directory:
            root = Path(directory)
            plan = self.plan(directory)
            self.assertEqual(plan.order, ["lev4", "lev2", "lev1", "post1"])
            self.assertEqual(plan.stage("post1")["session_kind"], "POST")
            self.assertEqual(plan.stage("lev4")["duration_seconds"], 1200)
            self.assertEqual(plan.stage("lev4")["runtime_max_seconds"], 1500)
            self.assertEqual(plan.manifest["paper_lane"], "B")
            self.assertEqual(plan.manifest["evidence_class"], "exploratory")
            for stage in plan.order:
                config = plan.config(stage)
                self.assertEqual(config["max_order_quantity"], 1)
                self.assertEqual(config["max_order_qty_mode"], "fixed")
                self.assertEqual(config["duration_seconds"], 1200)
            self.assertTrue(plan.config("post1")["sessions"]["extended_hours"])
            self.assertFalse(plan.config("post1")["sessions"]["overnight_holds"])


if __name__ == "__main__":
    unittest.main()
