"""Specific negative admission inputs: removing a guard must fail its assertion."""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / "blueprints/us-equities/adaptive-paper"
sys.path.insert(0, str(SOURCE))
import paper_deployment as d


def load_json(path):
    return json.loads(Path(path).read_bytes())


class Guards(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir="/var/tmp")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        p = patch.object(d, "CANONICAL_STATE", self.root / "exploratory", create=True)
        p.start(); self.addCleanup(p.stop)
        p = patch("safety.DEFAULT_STOP", self.root / "STOP")
        p.start(); self.addCleanup(p.stop)
        p = patch.object(d, "account_writer", side_effect=lambda _: d.exclusive(self.root / "SYN-account.lock"))
        p.start(); self.addCleanup(p.stop)
        self.bundle = self.root / "bundle"
        specs = {stage: {"engine_kind": "adaptive", "session_kind": "RTH",
                         "config": str(SOURCE / "config-sip.json")} for stage in ["lev4", "lev2"]}
        d.build(self.bundle, deployment="guard-pass", order=list(specs), stage_specs=specs)
        self.plan = d.Deployment(self.bundle, self.root / "exploratory")
        self.now = datetime(2026, 10, 12, 15, 0, tzinfo=timezone.utc).timestamp()
        self.lane = patch.object(d, "lane_a_absent", return_value=True)
        self.lane.start(); self.addCleanup(self.lane.stop)
        self.proof = self.ready("lev4", "start")

    def ready(self, stage, trial):
        account = {"fingerprint": "a" * 64, "salt": "b" * 64}
        d.save(self.plan.instance(trial) / "account.private.json", account)
        commitment = hmac.new(bytes.fromhex(account["salt"]), account["fingerprint"].encode(), hashlib.sha256).hexdigest()
        value = {**d.LABEL, "status": "ready", "deployment": self.plan.deployment, "stage": stage,
                 "trial": trial, "bundle_sha256": self.plan.bundle_hash(),
                 "config_sha256": self.plan.stage(stage)["config_sha256"], "observed_at": self.now,
                 "session_kind": "RTH", "session_date": "2026-10-12", "flat": True, "positions": [],
                 "open_orders": [], "native_preflight": True, "writer_lock_checked": True,
                 "account_commitment": commitment}
        d.save(self.plan.instance(trial) / "readiness.json", value)
        return value

    def issue(self, **kwargs):
        return self.plan.issue("lev4", "start", previous=None, now=self.now, **kwargs)

    def test_issue_stop_hold_and_active_are_each_required(self):
        stop = self.plan.state.parent / "STOP"
        stop.touch()
        with self.assertRaisesRegex(d.Refused, "^STOP_present$"): self.issue(check_only=True)
        stop.unlink()
        hold = self.plan.state / "ISSUER-HOLD"; hold.touch()
        with self.assertRaisesRegex(d.Refused, "^issuer_hold$"): self.issue(check_only=True)
        hold.unlink()
        active = self.plan.active_path("foreign")
        d.save(active, {})
        with self.assertRaisesRegex(d.Refused, "^active_experiment_requires_recovery$"): self.issue(check_only=True)
        active.unlink()
        self.assertEqual(self.issue(check_only=True)["status"], "ready")

    def test_issue_requires_lane_a_check(self):
        with patch.object(d, "lane_a_absent", side_effect=d.Refused("lane_A_writer_active")):
            with self.assertRaisesRegex(d.Refused, "^lane_A_writer_active$"): self.issue(check_only=True)
        self.assertFalse((self.plan.slot("lev4") / "GO.sha256").exists())

    def test_each_readiness_binding_field_is_required(self):
        for field in ["paper_lane", "evidence_class", "status", "deployment", "stage", "trial",
                      "bundle_sha256", "config_sha256", "session_kind", "session_date",
                      "native_preflight", "writer_lock_checked"]:
            with self.subTest(field=field):
                wrong = dict(self.proof, **{field: "wrong"})
                d.save(self.plan.instance("start") / "readiness.json", wrong)
                with self.assertRaisesRegex(d.Refused, "^readiness_binding_mismatch$"):
                    self.issue(check_only=True)
        d.save(self.plan.instance("start") / "readiness.json", self.proof)
        self.assertEqual(self.issue(check_only=True)["status"], "ready")

    def test_readiness_account_and_each_flatness_field_is_required(self):
        for field, value in [("flat", False), ("positions", [{}]), ("open_orders", [{}])]:
            with self.subTest(field=field):
                d.save(self.plan.instance("start") / "readiness.json", dict(self.proof, **{field: value}))
                with self.assertRaisesRegex(d.Refused, "^account_not_flat$"): self.issue(check_only=True)
        d.save(self.plan.instance("start") / "readiness.json", dict(self.proof, account_commitment="c" * 64))
        with self.assertRaisesRegex(d.Refused, "^readiness_account_binding_mismatch$"): self.issue(check_only=True)

    def test_readiness_missing_stale_and_future_are_specific(self):
        path = self.plan.instance("start") / "readiness.json"
        path.unlink()
        with self.assertRaisesRegex(d.Refused, "^readiness_missing$"): self.issue(check_only=True)
        for delta in [-1, 31]:
            d.save(path, dict(self.proof, observed_at=self.now - delta))
            with self.assertRaisesRegex(d.Refused, "^readiness_stale$"): self.issue(check_only=True)

    def test_session_kind_and_headroom_are_independent_guards(self):
        with self.assertRaisesRegex(d.Refused, "^venue_session_not_ready$"):
            self.plan.session("lev4", datetime(2026, 10, 12, 21, 0, tzinfo=timezone.utc).timestamp())
        with self.assertRaisesRegex(d.Refused, "^insufficient_session_time$"):
            self.plan.session("lev4", datetime(2026, 10, 12, 19, 50, tzinfo=timezone.utc).timestamp())
        config = self.plan.config("lev4")
        with self.assertRaisesRegex(d.Refused, "^unsupported_session_kind$"):
            d.validate_sizing_and_scope(config, "adaptive", "PRE")
        changed = dict(config, sessions=dict(config["sessions"], overnight_holds=True))
        with self.assertRaisesRegex(d.Refused, "^unsupported_overnight_policy$"):
            d.validate_sizing_and_scope(changed, "adaptive", "RTH")

    def test_bundle_config_and_state_namespace_guards(self):
        path = self.plan.config_path("lev4")
        raw = path.read_bytes(); path.write_bytes(raw + b" ")
        with self.assertRaisesRegex(d.Refused, "^bundle_hash_mismatch$"): self.issue(check_only=True)
        with self.assertRaisesRegex(d.Refused, "^config_hash_mismatch$"): self.plan.config_path("lev4")
        path.write_bytes(raw)
        self.plan.stage("lev4")["state_namespace"] = "another"
        with self.assertRaisesRegex(d.Refused, "^stage_runtime_or_namespace_mismatch$"): self.plan.verify()

    def test_verify_source_inventory_label_and_native_effective_digest(self):
        self.plan.stage("lev4")["session_kind"] = "PRE"
        with self.assertRaisesRegex(d.Refused, "^unsupported_session_kind$"): self.plan.verify()
        self.plan.stage("lev4")["session_kind"] = "RTH"
        with patch.object(d, "config_hashes", return_value=(
                self.plan.stage("lev4")["config_file_sha256"], "c" * 64)):
            with self.assertRaisesRegex(d.Refused, "^effective_config_hash_mismatch$"): self.plan.verify()
        self.plan.manifest["paper_lane"] = "A"
        with self.assertRaisesRegex(d.Refused, "^exploratory_label_required$"): self.plan.verify()
        self.plan.manifest["paper_lane"] = "B"
        d.save(self.bundle / "source.json", {**d.LABEL, "source_kind": "SYN-unlisted"})
        with self.assertRaisesRegex(d.Refused, "^bundle_file_inventory_mismatch$"): self.plan.verify()

    def test_verify_t22_capability_and_engine_kind_cannot_fall_back(self):
        import runner
        real = runner.load_config
        self.plan.stage("lev4")["engine_kind"] = "t22"
        with self.assertRaisesRegex(d.Refused, "^t22_dispatch_not_available$"): self.plan.verify()
        self.plan.stage("lev4")["engine_kind"] = "adaptive"
        def t22(path):
            config, limits, policy = real(path)
            config["_t22"] = SimpleNamespace()
            return config, limits, policy
        with patch.object(runner, "load_config", side_effect=t22):
            with self.assertRaisesRegex(d.Refused, "^t22_engine_kind_required$"): self.plan.verify()

    def test_seal_includes_nested_checksum_files_and_rejects_symlinks(self):
        root = self.root / "sealing"
        (root / "source" / "nested").mkdir(parents=True)
        (root / "source" / "nested" / "SHA256SUMS").write_text("published source checksum bytes")
        (root / "source" / "plain").write_text("source")
        files = d.seal_inventory(root)
        self.assertIn(root / "source/nested/SHA256SUMS", files)
        self.assertIn("source/nested/SHA256SUMS", (root / "SHA256SUMS").read_text())
        self.assertNotIn(root / "SHA256SUMS", files)
        (root / "source" / "alias").symlink_to(self.bundle / "deployment.json")
        with self.assertRaisesRegex(d.Refused, "^bundle_symlink$"): d.seal_inventory(root)

    def test_private_file_size_and_growth_guards(self):
        path = self.root / "bounded"
        path.write_bytes(b"abcdef")
        with self.assertRaisesRegex(d.Refused, "^unsafe_input_file$"): d.read_bytes(path, limit=3)
        real_stat = d.os.fstat
        def small(fd):
            info = real_stat(fd)
            return SimpleNamespace(st_mode=info.st_mode, st_size=0)
        with patch.object(d.os, "fstat", side_effect=small):
            with self.assertRaisesRegex(d.Refused, "^input_too_large$"): d.read_bytes(path, limit=3)
        with self.assertRaisesRegex(d.Refused, "^unsafe_input_file$"): d.read_bytes(self.root)
        private = self.root / "private.json"; d.save(private, {"fixture": True})
        self.assertEqual(private.stat().st_mode & 0o777, 0o600)
        private.chmod(0o644)
        with self.assertRaisesRegex(d.Refused, "^unsafe_private_runtime_file$"): d.read_private_json(private)

    def test_cut_destination_and_source_archive_refusals(self):
        with self.assertRaisesRegex(d.Refused, "^protected_bundle_destination$"):
            d.bundle_destination(d.ACCOUNT_ROOT / "trials" / "denied")
        with self.assertRaisesRegex(d.Refused, "^deployment_directory_exists$"):
            d.cut(self.bundle, deployment="existing", order=["mover-max"], source_pin="HEAD")
        with self.assertRaisesRegex(d.Refused, "^rung_deployment_requires_registered_sizing_preset$"):
            d.cut(self.root / "rung", deployment="denied", order=["mover1"], source_pin="HEAD")
        import io, tarfile
        def archive(kind):
            data = io.BytesIO()
            with tarfile.open(fileobj=data, mode="w") as stream:
                member = tarfile.TarInfo("alias" if kind == "symlink" else
                    "blueprints/us-equities/adaptive-paper/" + ("other.py" if kind == "missing" else "paper_deployment.py"))
                if kind == "symlink":
                    member.type = tarfile.SYMTYPE; member.linkname = "../outside"; stream.addfile(member)
                else:
                    body = b"# SYN archive fixture, never executed\n"
                    member.size = len(body); stream.addfile(member, io.BytesIO(body))
            return data.getvalue()
        for case, reason in [("symlink", "source_archive_nonregular_entry"),
                             ("missing", "source_pin_has_no_deployment_helper"),
                             ("build", "frozen_config_build_refused")]:
            with patch.object(d.subprocess, "check_output", return_value="a" * 40 + "\n"), \
                    patch.object(d.subprocess, "run", side_effect=[
                        SimpleNamespace(stdout=archive(case), returncode=0),
                        SimpleNamespace(returncode=2, stdout="", stderr="")]):
                with self.assertRaisesRegex(d.Refused, "^" + reason + "$"):
                    d.cut(self.root / case, deployment="denied", order=["mover-max"], source_pin="HEAD")

    def test_managed_runtime_owner_markers_and_metadata_are_fixed_inputs(self):
        runtime_home = self.root / "SYN-home"
        runtime = runtime_home / "projects/us-equities-runtime"
        (runtime / ".venv").mkdir(parents=True)
        import shutil
        for filename in ["pyproject.toml", "uv.lock"]:
            shutil.copyfile(SOURCE.parent / "runtime-2604/trading-2604-runtime" / filename, runtime / filename)
        expected = {".trading-2604-owner": "native-stack-trading-2604-v1",
                    ".trading-2604-complete": "native-stack-trading-2604-no-dvc-r4"}
        for filename, value in expected.items(): (runtime / filename).write_text(value)
        with patch.object(Path, "home", return_value=runtime_home):
            d.verify_managed_runtime()
            for filename, value in expected.items():
                (runtime / filename).write_text("wrong")
                with self.assertRaisesRegex(d.Refused, "^runtime_marker_incomplete$"): d.verify_managed_runtime()
                (runtime / filename).write_text(value)
            (runtime / "uv.lock").write_text("changed")
            with self.assertRaisesRegex(d.Refused, "^runtime_metadata_differs$"): d.verify_managed_runtime()
            (runtime / ".venv").rmdir()
            with self.assertRaisesRegex(d.Refused, "^runtime_ownership_incomplete$"): d.verify_managed_runtime()

    def test_config_path_escape_label_and_budget_fields_are_required(self):
        spec = self.plan.stage("lev4")
        original = spec["config"]
        for path in ["../escape", str(self.root / "absolute")]:
            spec["config"] = path
            with self.assertRaisesRegex(d.Refused, "^unsafe_artifact_path$"): self.plan.config_path("lev4")
        spec["config"] = original
        config_path = self.plan.config_path("lev4")
        config = d.read_json(config_path)
        changed = dict(config, paper_lane="A")
        d.save(config_path, changed); spec["config_file_sha256"] = d.digest(config_path)
        with self.assertRaisesRegex(d.Refused, "^exploratory_label_required$"): self.plan.config("lev4")
        d.save(config_path, config); spec["config_file_sha256"] = d.digest(config_path)
        altered = dict(config, max_api_requests_per_minute=151)
        d.save(config_path, altered)
        spec["config_file_sha256"], spec["config_sha256"] = d.config_hashes(config_path, "adaptive")
        # Re-seal the changed bytes so the numerical guard is the one exercised.
        d.seal_inventory(self.bundle)
        with self.assertRaisesRegex(d.Refused, "^deployment_request_budget_exceeded$"): self.plan.verify()

    def test_observe_account_change_and_active_or_stop_never_writes_ready(self):
        counter = [0]
        def read(before_request, **kwargs):
            before_request("read"); counter[0] += 1
            return {"account_identity_sha256": ("a" if counter[0] == 1 else "c") * 64,
                    "positions": [], "orders": [], "open_orders_complete": True}
        with patch.object(d, "native_flat_observation", side_effect=read):
            with self.assertRaisesRegex(d.Refused, "^account_changed_during_readiness$"):
                self.plan.observe("lev4", "mismatched", now=self.now)
        self.assertFalse((self.plan.instance("mismatched") / "readiness.json").exists())
        d.save(self.plan.active_path("foreign"), {})
        with self.assertRaisesRegex(d.Refused, "^active_experiment_requires_recovery$"):
            self.plan.observe("lev4", "mismatched", now=self.now)
        self.plan.active_path("foreign").unlink()
        stop = self.plan.state.parent / "STOP"; stop.touch()
        with self.assertRaisesRegex(d.Refused, "^STOP_present$"):
            self.plan.observe("lev4", "mismatched", now=self.now)

    def test_account_last_drain_and_sql_authoritative_namespace_guards(self):
        d.save(self.plan.state / "account-last.json", {**d.LABEL, "flat": True, "finished_at": self.now - 59, "trial": "owned"})
        with self.assertRaisesRegex(d.Refused, "^request_window_not_drained$"): self.plan.account_window(self.now)
        with self.assertRaisesRegex(d.Refused, "^invalid_native_account_fingerprint$"):
            self.plan.namespace_ready("lev4", "not-a-fingerprint")
        from safety import Ledger
        state = self.plan.native_state() / ("a" * 64) / "adaptive"
        path = state / "trial.json"
        good = {**d.LABEL, "phase": "finished", "trial_id": "owned", "engine_kind": "adaptive",
                "config_sha256": self.plan.stage("lev4")["config_sha256"]}
        d.save(path, good)
        d.save(self.plan.state / "account-last.json", {**d.LABEL, "flat": True, "finished_at": self.now - 61, "trial": "owned"})
        module = SimpleNamespace(active_trial_metadata=lambda _: None)
        with patch.object(Ledger, "register_exploratory_config", create=True), patch.dict(sys.modules, {"exploration": module}):
            with self.assertRaisesRegex(d.Refused, "^native_lineage_missing$"):
                self.plan.namespace_ready("lev4", "a" * 64)
            for field, value, reason in [("trial_id", "foreign", "native_lineage_mismatch"),
                                        ("engine_kind", "unknown", "native_lineage_mismatch"),
                                        ("phase", "running", "existing_native_trial_requires_recovery"),
                                        ("paper_lane", "A", "native_state_label_required")]:
                module.active_trial_metadata = lambda _, field=field, value=value: dict(good, **{field: value})
                with self.assertRaisesRegex(d.Refused, "^" + reason + "$"): self.plan.namespace_ready("lev4", "a" * 64)
            module.active_trial_metadata = lambda _: good
            self.assertEqual(self.plan.namespace_ready("lev4", "a" * 64), "matching_native_namespace")
        path.rename(state / "actual.json"); path.symlink_to(state / "actual.json")
        with self.assertRaisesRegex(d.Refused, "^unsafe_native_state$"): self.plan.namespace_ready("lev4", "a" * 64)

    def test_observe_used_pending_partial_and_exhausted_budget_refuse(self):
        trial = "observation"
        self.plan.instance(trial).mkdir(parents=True)
        used = self.plan.instance(trial) / "GO.used.sha256"; used.write_text("SYN-consumed")
        with self.assertRaisesRegex(d.Refused, "^trial_reuse$"): self.plan.observe("lev4", trial, now=self.now)
        used.unlink()
        pending = self.plan.slot("lev4") / "GO.sha256"; pending.parent.mkdir(parents=True)
        pending.write_text("SYN-pending")
        with self.assertRaisesRegex(d.Refused, "^readiness_already_bound$"): self.plan.observe("lev4", trial, now=self.now)
        pending.unlink()
        good = {"account_identity_sha256": "a" * 64, "positions": [], "orders": [], "open_orders_complete": True}
        for key, value in [("positions", [{}]), ("orders", [{}]), ("open_orders_complete", False)]:
            with patch.object(d, "native_flat_observation", side_effect=[good, dict(good, **{key: value})]):
                with self.assertRaisesRegex(d.Refused, "^account_not_flat$"): self.plan.observe("lev4", trial, now=self.now)
        from safety import Ledger, RiskLimits
        ledger = Ledger(self.plan.state / "readiness-budget.sqlite3",
                        RiskLimits(max_rest_per_minute=50, max_submits_per_minute=20))
        try:
            for _ in range(50): self.assertEqual(ledger.request_budget(time.time(), "read"), 0)
        finally:
            ledger.close()
        def native(before, **kwargs):
            before("read"); return good
        with patch.object(d, "native_flat_observation", side_effect=native):
            with self.assertRaisesRegex(d.Refused, "^readiness_request_budget$"): self.plan.observe("lev4", trial, now=self.now)

    def test_effective_digest_can_differ_from_frozen_file_without_aliasing(self):
        config_path = self.plan.config_path("lev4")
        raw = d.digest(config_path)
        resolved, limits, _ = d.resolved_config(config_path, "adaptive")
        module = SimpleNamespace(config_digest=lambda config, data, **kwargs: "c" * 64)
        with patch.dict(sys.modules, {"exploration": module}):
            file_hash, native_hash = d.config_hashes(config_path, "adaptive")
        self.assertEqual(file_hash, raw)
        self.assertEqual(native_hash, "c" * 64)
        self.assertNotEqual(file_hash, native_hash)

    def test_go_pending_used_and_consumed_sequence_are_not_reusable(self):
        self.issue()
        with self.assertRaisesRegex(d.Refused, "^sequence_stage_or_trial$"): self.issue()
        used = self.plan.instance("start") / "GO.used.sha256"
        (self.plan.slot("lev4") / "GO.sha256").replace(used)
        cursor = load_json(self.plan.sequence_path())
        cursor["pending"] = None; d.save(self.plan.sequence_path(), cursor)
        with self.assertRaisesRegex(d.Refused, "^GO_pending_or_used$"): self.issue()

    def test_initial_sequence_stage_and_completed_pass_id_are_required(self):
        with self.assertRaisesRegex(d.Refused, "^sequence_stage_or_trial$"):
            self.plan.sequence_next("lev2", "second", None)
        d.save(self.plan.sequence_path(), {"next_index": len(self.plan.order), "passes": ["old"]})
        with self.assertRaisesRegex(d.Refused, "^pass_already_used$"):
            self.plan.sequence_next("lev4", "new", None, "old")

    def test_two_real_passes_reject_older_flat_predecessor_and_repeated_successor(self):
        def native(mode, stage, trial, output):
            d.save(output, {"status": "passed", "flat": True, "positions": [], "unresolved_orders": [],
                            "reconciliation": {"positions": 0, "open_orders": 0}})
            return 0
        with patch.object(self.plan, "native_call", side_effect=native):
            for stage, trial, previous, pass_id in [
                ("lev4", "p1-first", None, "one"), ("lev2", "p1-second", "p1-first", "one"),
                ("lev4", "p2-first", None, "two")]:
                self.ready(stage, trial)
                self.plan.issue(stage, trial, previous=previous, now=self.now, pass_id=pass_id)
                self.plan.run(stage, now=self.now)
                self.plan.recover(trial, now=self.now)
                self.now += 61
            self.ready("lev2", "p2-second")
            with self.assertRaisesRegex(d.Refused, "^sequence_stage_or_trial$"):
                self.plan.issue("lev2", "p2-second", previous="p1-first", now=self.now, pass_id="two")
            self.plan.issue("lev2", "p2-second", previous="p2-first", now=self.now, pass_id="two")
            self.ready("lev2", "repeat")
            with self.assertRaisesRegex(d.Refused, "^sequence_stage_or_trial$"):
                self.plan.issue("lev2", "repeat", previous="p2-first", now=self.now, pass_id="two")

    def test_each_previous_handoff_native_proof_config_and_drain_field_is_required(self):
        trial = "finished"
        native = self.plan.instance(trial) / "recover.json"
        good_native = {"status": "passed", "flat": True, "positions": [], "unresolved_orders": [],
                       "reconciliation": {"positions": 0, "open_orders": 0}}
        d.save(native, good_native)
        good = {**d.LABEL, "deployment": self.plan.deployment, "stage": "lev4", "trial": trial,
                "recover_rc": 0, "flat": True, "positions": 0, "open_orders": 0,
                "bundle_sha256": self.plan.bundle_hash(), "config_sha256": self.plan.stage("lev4")["config_sha256"],
                "native_recover_sha256": d.digest(native), "finished_at": self.now - 61}
        path = self.plan.instance(trial) / "handoff.json"
        for key, value in [("paper_lane", "A"), ("evidence_class", "SYN"), ("deployment", "different"),
                           ("stage", "lev2"), ("trial", "other"), ("recover_rc", 2), ("flat", False),
                           ("positions", 1), ("open_orders", 1), ("bundle_sha256", "c" * 64),
                           ("config_sha256", "c" * 64)]:
            d.save(path, dict(good, **{key: value}))
            with self.subTest(field=key):
                with self.assertRaisesRegex(d.Refused, "^previous_handoff_not_flat$"):
                    self.plan.previous("lev2", trial, self.now)
        d.save(path, dict(good, native_recover_sha256="c" * 64))
        with self.assertRaisesRegex(d.Refused, "^previous_native_recover_hash$"):
            self.plan.previous("lev2", trial, self.now)
        for key, value in [("status", "needs_attention"), ("flat", False), ("positions", [{}]),
                           ("unresolved_orders", [{}]), ("reconciliation", {"positions": 1, "open_orders": 0}),
                           ("reconciliation", {"positions": 0, "open_orders": 1})]:
            d.save(native, dict(good_native, **{key: value}))
            d.save(path, dict(good, native_recover_sha256=d.digest(native)))
            with self.assertRaisesRegex(d.Refused, "^previous_handoff_not_flat$"):
                self.plan.previous("lev2", trial, self.now)
        d.save(native, good_native)
        d.save(path, dict(good, finished_at=self.now - 59))
        with self.assertRaisesRegex(d.Refused, "^request_window_not_drained$"):
            self.plan.previous("lev2", trial, self.now)
        with self.assertRaisesRegex(d.Refused, "^previous_handoff_required$"):
            self.plan.previous("lev2", None, self.now)
        with self.assertRaisesRegex(d.Refused, "^unexpected_previous_handoff$"):
            self.plan.previous("lev4", trial, self.now)
        path.unlink()
        with self.assertRaisesRegex(d.Refused, "^previous_handoff_missing$"):
            self.plan.previous("lev2", trial, self.now)

    def test_each_go_binding_field_and_expiry_blocks_dispatch(self):
        self.issue()
        original = load_json(self.plan.slot("lev4") / "GO.json")
        for field in ["paper_lane", "evidence_class", "deployment", "stage", "bundle_sha256",
                      "config_sha256", "session_kind", "session_date", "order_sha256"]:
            with self.subTest(field=field):
                value = dict(original, **{field: "wrong"})
                d.save(self.plan.slot("lev4") / "GO.json", value)
                (self.plan.slot("lev4") / "GO.sha256").write_text(d.digest(self.plan.slot("lev4") / "GO.json"))
                with patch.object(self.plan, "native_call") as dispatch:
                    with self.assertRaisesRegex(d.Refused, "^GO_binding_or_expiry$"): self.plan.run("lev4", now=self.now)
                    self.assertEqual(dispatch.call_count, 0)
        for issued in [self.now + 1, self.now - 301]:
            d.save(self.plan.slot("lev4") / "GO.json", dict(original, issued_at=issued))
            (self.plan.slot("lev4") / "GO.sha256").write_text(d.digest(self.plan.slot("lev4") / "GO.json"))
            with self.assertRaisesRegex(d.Refused, "^GO_binding_or_expiry$"): self.plan.run("lev4", now=self.now)

    def test_run_stop_hold_active_and_ready_hash_block_dispatch(self):
        self.issue()
        slot = self.plan.slot("lev4")
        original = d.read_bytes(slot / "GO.sha256")
        def reset():
            (slot / "GO.sha256").write_bytes(original)
        stop = self.plan.state.parent / "STOP"; stop.touch()
        with self.assertRaisesRegex(d.Refused, "^STOP_present$"): self.plan.run("lev4", now=self.now)
        stop.unlink(); reset()
        hold = self.plan.state / "ISSUER-HOLD"; hold.touch()
        with self.assertRaisesRegex(d.Refused, "^issuer_hold$"): self.plan.run("lev4", now=self.now)
        hold.unlink(); reset()
        d.save(self.plan.active_path("other"), {})
        with self.assertRaisesRegex(d.Refused, "^active_experiment_requires_recovery$"): self.plan.run("lev4", now=self.now)
        self.plan.active_path("other").unlink(); reset()
        value = dict(self.proof, request_count=99)
        d.save(self.plan.instance("start") / "readiness.json", value)
        with self.assertRaisesRegex(d.Refused, "^readiness_hash_mismatch$"): self.plan.run("lev4", now=self.now)

    def test_writer_contention_owner_and_replaced_inode(self):
        path = self.root / "lock"
        with d.exclusive(path):
            with self.assertRaisesRegex(d.Refused, "^writer_busy$"):
                with d.exclusive(path): pass
        with patch.object(d.os, "getuid", return_value=os.getuid() + 1):
            with self.assertRaisesRegex(d.Refused, "^unsafe_writer_lock$"):
                with d.exclusive(path): pass
        with self.assertRaisesRegex(d.Refused, "^writer_lock_replaced$"):
            with d.exclusive(path):
                path.rename(self.root / "old"); path.touch()

    def test_recovery_lock_wait_is_bounded_and_can_finish_after_release(self):
        path = self.root / "wait-lock"
        held = threading.Event()
        def owner():
            with d.exclusive(path):
                held.set(); time.sleep(0.08)
        thread = threading.Thread(target=owner); thread.start(); held.wait(1)
        try:
            with d.exclusive(path, wait_seconds=1): pass
        finally:
            thread.join()

    def test_issue_run_observe_scan_and_recover_require_writer_context(self):
        self.issue()
        go = load_json(self.plan.slot("lev4") / "GO.json")
        with patch.object(self.plan, "native_call", side_effect=d.Refused("SYN_dispatch_tripwire")), \
             patch.object(d, "native_flat_observation", side_effect=d.Refused("SYN_broker_tripwire")), \
             d.exclusive(self.plan.state / "deployment-writer.lock"):
            with self.assertRaisesRegex(d.Refused, "^writer_busy$"): self.issue(check_only=True)
            with self.assertRaisesRegex(d.Refused, "^writer_busy$"): self.plan.run("lev4", now=self.now)
            with self.assertRaisesRegex(d.Refused, "^writer_busy$"): self.plan.observe("lev4", "new", now=self.now)
            d.save(self.plan.active_path("start"), go)
            # Keep the production recovery bound; advance its monotonic clock
            # in SYN so contention refusal takes no thirty-second wall wait.
            with patch.object(d.time, "monotonic", side_effect=[0, 31]):
                with self.assertRaisesRegex(d.Refused, "^writer_busy$"): self.plan.recover("start")
        self.plan.active_path("start").unlink()
        plan, packet, _ = self.mover_packet()
        with d.exclusive(plan.state / "deployment-writer.lock"):
            with self.assertRaisesRegex(d.Refused, "^writer_busy$"): plan.publish_scan("mover-max", packet, now=self.now)

    def test_private_capability_fields_token_age_and_go_single_use(self):
        self.issue()
        go = load_json(self.plan.slot("lev4") / "GO.json")
        d.save(self.plan.active_path("start"), go)
        (self.plan.slot("lev4") / "GO.sha256").replace(self.plan.instance("start") / "GO.used.sha256")
        secret = "SYN-private-capability"
        baseline = {**d.LABEL, "deployment": self.plan.deployment, "stage": "lev4", "trial": "start",
            "mode": "paper", "bundle_sha256": self.plan.bundle_hash(), "config_sha256": self.plan.stage("lev4")["config_sha256"],
            "active_sha256": d.digest(self.plan.active_path("start")), "account_commitment": go["account_commitment"],
            "issued_at": self.now, "token_sha256": hashlib.sha256(secret.encode()).hexdigest()}
        path = self.plan.instance("start") / "launch-paper.json"
        def call(value, supplied=secret):
            d.save(path, value)
            read, write = os.pipe(); os.write(write, supplied.encode()); os.close(write)
            with patch.object(d.time, "time", return_value=self.now):
                return self.plan.consume_capability("paper", "lev4", "start", read)
        for field in ["paper_lane", "evidence_class", "deployment", "stage", "trial", "mode", "bundle_sha256",
                      "config_sha256", "active_sha256", "account_commitment"]:
            with self.subTest(field=field):
                with self.assertRaisesRegex(d.Refused, "^native_launch_capability_mismatch$"):
                    call(dict(baseline, **{field: "wrong"}))
        for value, supplied in [(dict(baseline, issued_at=self.now - 31), secret),
                                (dict(baseline, issued_at=self.now + 1), secret), (baseline, "different")]:
            with self.assertRaisesRegex(d.Refused, "^native_launch_capability_mismatch$"): call(value, supplied)
        used = self.plan.instance("start") / "GO.used.sha256"
        raw = used.read_bytes(); used.unlink()
        with self.assertRaisesRegex(d.Refused, "^native_launch_not_single_use$"): call(baseline)
        used.write_bytes(raw)
        d.save(self.plan.instance("start") / "paper.json", {})
        with self.assertRaisesRegex(d.Refused, "^native_launch_not_single_use$"): call(baseline)
        (self.plan.instance("start") / "paper.json").unlink()
        used.write_text("c" * 64)
        with self.assertRaisesRegex(d.Refused, "^native_consumed_GO_mismatch$"): call(baseline)
        used.write_bytes(raw)
        for latch in [self.root / "STOP", self.plan.state / "ISSUER-HOLD"]:
            latch.touch()
            with self.assertRaisesRegex(d.Refused, "^native_control_latch$"): call(baseline)
            latch.unlink()
        with patch.object(d, "lane_a_absent", side_effect=d.Refused("SYN_lane_A_active")):
            with self.assertRaisesRegex(d.Refused, "^SYN_lane_A_active$"): call(baseline)
        for field in ["stage", "trial", "bundle_sha256", "config_sha256"]:
            d.save(self.plan.active_path("start"), dict(go, **{field: "wrong"}))
            # Keep the secondary capability hash valid: this isolates the
            # active-binding guard rather than another rejection downstream.
            value = dict(baseline, active_sha256=d.digest(self.plan.active_path("start")))
            with self.assertRaisesRegex(d.Refused, "^native_active_binding_mismatch$"): call(value)
            with patch.object(d.subprocess, "run") as child:
                with self.assertRaisesRegex(d.Refused, "^native_active_binding_mismatch$"):
                    self.plan.native_call("paper", "lev4", "start", self.plan.instance("start") / "paper.json")
                child.assert_not_called()
        d.save(self.plan.active_path("start"), go)
        self.assertEqual(call(baseline)["trial"], "start")

    def test_run_hash_sequence_handoff_scan_and_consumed_token_are_required(self):
        self.issue()
        slot = self.plan.slot("lev4")
        original_go = load_json(slot / "GO.json")
        original_cursor = load_json(self.plan.sequence_path())
        def reset(go=original_go):
            d.save(slot / "GO.json", go)
            (slot / "GO.sha256").write_text(d.digest(slot / "GO.json"))
        with patch.object(self.plan, "native_call") as child:
            (slot / "GO.sha256").write_text("wrong")
            with self.assertRaisesRegex(d.Refused, "^GO_hash_mismatch$"): self.plan.run("lev4", now=self.now)
            reset()
            for field, value in [("pending", "other"), ("pass_id", "other"), ("next_index", 1)]:
                d.save(self.plan.sequence_path(), dict(original_cursor, **{field: value}))
                with self.assertRaisesRegex(d.Refused, "^sequence_active_binding$"): self.plan.run("lev4", now=self.now)
                reset()
            d.save(self.plan.sequence_path(), original_cursor)
            reset(dict(original_go, previous_handoff_sha256="wrong"))
            with self.assertRaisesRegex(d.Refused, "^previous_handoff_binding$"): self.plan.run("lev4", now=self.now)
            reset(dict(original_go, scan_binding={"wrong": True}))
            with self.assertRaisesRegex(d.Refused, "^scan_binding_changed$"): self.plan.run("lev4", now=self.now)
            reset()
            (self.plan.instance("start") / "GO.used.sha256").write_text("already-used")
            with self.assertRaisesRegex(d.Refused, "^GO_already_used$"): self.plan.run("lev4", now=self.now)
            child.assert_not_called()

    def test_recover_config_and_sequence_binding_precede_native_and_stop_clear(self):
        self.issue()
        go = load_json(self.plan.slot("lev4") / "GO.json")
        with patch.object(self.plan, "native_call") as child:
            for field in ["bundle_sha256", "config_sha256"]:
                d.save(self.plan.active_path("start"), dict(go, **{field: "wrong"}))
                with self.assertRaisesRegex(d.Refused, "^recovery_config_binding_mismatch$"): self.plan.recover("start")
                self.assertTrue((self.root / "STOP").exists())
            d.save(self.plan.active_path("start"), go)
            cursor = load_json(self.plan.sequence_path()); cursor["pending"] = "other"
            d.save(self.plan.sequence_path(), cursor)
            with self.assertRaisesRegex(d.Refused, "^sequence_recovery_binding$"): self.plan.recover("start")
            self.assertTrue((self.root / "STOP").exists())
            child.assert_not_called()

    def test_expired_t22_packet_does_not_block_other_stage_or_recovery(self):
        import runner
        real = runner.load_config
        self.plan.stage("lev2")["engine_kind"] = "t22"
        def resolved(path, *, require_t22_packet=True):
            config, limits, settings = real(path)
            if Path(path) == self.plan.config_path("lev2"):
                if require_t22_packet: raise ValueError("SYN_packet_removed_after_trial")
                config["_t22"] = SimpleNamespace()
            return config, limits, settings
        expired = SimpleNamespace(validate_availability=lambda *_: (_ for _ in ()).throw(ValueError("t22_factors_unavailable_or_stale")))
        with patch.object(runner, "load_config", new=resolved), patch.dict(sys.modules, {"t22_dispatch": expired}):
            self.plan.verify()
            self.issue()
            go = load_json(self.plan.slot("lev4") / "GO.json")
            d.save(self.plan.active_path("start"), go)
            def native(mode, stage, trial, output):
                d.save(output, {"status": "passed", "flat": True, "positions": [], "unresolved_orders": [],
                                "reconciliation": {"positions": 0, "open_orders": 0}})
                return 0
            with patch.object(self.plan, "native_call", side_effect=native):
                self.assertEqual(self.plan.recover("start"), 0)
            with self.assertRaisesRegex(ValueError, "^SYN_packet_removed_after_trial$"):
                self.plan.availability("lev2")
        def packet_available(path, *, require_t22_packet=True):
            config, limits, settings = real(path)
            if Path(path) == self.plan.config_path("lev2"): config["_t22"] = SimpleNamespace()
            return config, limits, settings
        with patch.object(runner, "load_config", new=packet_available), patch.dict(sys.modules, {"t22_dispatch": expired}):
            with self.assertRaisesRegex(ValueError, "^t22_factors_unavailable_or_stale$"):
                self.plan.availability("lev2")
        stage_validator = SimpleNamespace(validate_stage=lambda *_: (_ for _ in ()).throw(ValueError("SYN_duration_cleanup_uncovered")))
        with patch.object(runner, "load_config", new=packet_available), patch.dict(sys.modules, {"t22_dispatch": stage_validator}):
            with self.assertRaisesRegex(ValueError, "^SYN_duration_cleanup_uncovered$"):
                self.plan.availability("lev2")

    def test_flat_child_budget_refuses_before_transport(self):
        from safety import Ledger, RiskLimits
        import transport
        ledger = Ledger(self.plan.state / "readiness-budget.sqlite3",
                        RiskLimits(max_rest_per_minute=50, max_submits_per_minute=20))
        try:
            for _ in range(50): self.assertEqual(ledger.request_budget(time.time(), "read"), 0)
        finally:
            ledger.close()
        def fixture_preflight(*args, before_request, **kwargs):
            before_request("read")
            return {"positions": [], "orders": [], "open_orders_complete": True}
        with patch.object(self.plan, "consume_capability", return_value={}), \
             patch.object(self.plan, "check_account", side_effect=lambda stage, trial, value, **kwargs: value), \
             patch.object(transport, "preflight", side_effect=fixture_preflight), \
             patch.dict(os.environ, {"APCA_API_KEY_ID": "SYN-placeholder", "APCA_API_SECRET_KEY": "SYN-placeholder"}):
            with self.assertRaisesRegex(d.Refused, "^readiness_request_budget$"):
                self.plan.native_child("flat", "lev4", "start")
        self.assertFalse((self.plan.instance("start") / "recover.json").exists())

    def test_flat_child_every_native_flatness_operand_is_required(self):
        import transport
        for field, value in [("positions", [{}]), ("orders", [{}]), ("open_orders_complete", False)]:
            fixture = dict(positions=[], orders=[], open_orders_complete=True, **{})
            fixture[field] = value
            with patch.object(self.plan, "consume_capability", return_value={}), \
                 patch.object(self.plan, "check_account", side_effect=lambda stage, trial, value, **kwargs: value), \
                 patch.object(transport, "preflight", return_value=fixture), \
                 patch.dict(os.environ, {"APCA_API_KEY_ID": "SYN-placeholder", "APCA_API_SECRET_KEY": "SYN-placeholder"}):
                with self.subTest(field=field):
                    self.assertEqual(self.plan.native_child("flat", "lev4", "start"), 2)
                    self.assertFalse(load_json(self.plan.instance("start") / "recover.json")["flat"])

    def test_native_main_exception_writes_safe_known_or_unknown_failure_receipt(self):
        import runner
        from safety import SafetyError
        # Stub the inventory resolver before the runtime child is reached;
        # the harness never resolves a real credential pointer or calls a loader.
        resolver = SimpleNamespace(expand_template=lambda *_: self.root / "SYN-loader-placeholder")
        for error, reason in [(SafetyError("no_owned_trial_to_recover"), "no_owned_trial_to_recover"),
                              (RuntimeError("SYN-private-error"), "RuntimeError")]:
            with patch.object(self.plan, "consume_capability", return_value={}, create=True), \
                 patch.dict(sys.modules, {"credential_status": resolver}), \
                 patch.object(runner, "main", side_effect=error):
                self.assertEqual(self.plan.native_child("recover", "lev4", "start"), 2)
                receipt = load_json(self.plan.instance("start") / "recover.json")
                self.assertEqual(receipt["reason"], reason)
                self.assertEqual(receipt["evidence_class"], "exploratory")
                self.assertNotIn("SYN-private-error", json.dumps(receipt))

    def test_admission_calls_integrity_lane_a_and_selected_availability(self):
        dispatch = patch.object(self.plan, "native_call", side_effect=d.Refused("SYN_dispatch_tripwire"))
        dispatch.start(); self.addCleanup(dispatch.stop)
        broker = patch.object(d, "native_flat_observation", side_effect=d.Refused("SYN_broker_tripwire"))
        broker.start(); self.addCleanup(broker.stop)
        self.issue()
        slot = self.plan.slot("lev4")
        token = (slot / "GO.sha256").read_bytes()
        (slot / "GO.sha256").unlink()
        cursor = load_json(self.plan.sequence_path()); cursor["pending"] = None
        d.save(self.plan.sequence_path(), cursor)
        with patch.object(d, "lane_a_absent", side_effect=d.Refused("SYN_lane_A_active")):
            with self.assertRaisesRegex(d.Refused, "^SYN_lane_A_active$"): self.plan.observe("lev4", "new", now=self.now)
        with patch.object(self.plan, "availability", side_effect=d.Refused("SYN_factors_expired")):
            with self.assertRaisesRegex(d.Refused, "^SYN_factors_expired$"): self.issue(check_only=True)
            cursor["pending"] = "start"; d.save(self.plan.sequence_path(), cursor)
            (slot / "GO.sha256").write_bytes(token)
            with self.assertRaisesRegex(d.Refused, "^SYN_factors_expired$"): self.plan.run("lev4", now=self.now)
        (slot / "GO.sha256").write_bytes(token)
        with patch.object(d, "lane_a_absent", side_effect=d.Refused("SYN_lane_A_active")):
            with self.assertRaisesRegex(d.Refused, "^SYN_lane_A_active$"): self.plan.run("lev4", now=self.now)
        config = self.plan.config_path("lev4"); config.write_bytes(config.read_bytes() + b" ")
        for action in [lambda: self.issue(check_only=True), lambda: self.plan.observe("lev4", "new", now=self.now),
                       lambda: self.plan.run("lev4", now=self.now), lambda: self.plan.recover("start")]:
            (slot / "GO.sha256").write_bytes(token)
            with self.assertRaisesRegex(d.Refused, "^bundle_hash_mismatch$"): action()
        plan, packet, _ = self.mover_packet()
        cfg = plan.config_path("mover-max"); cfg.write_bytes(cfg.read_bytes() + b" ")
        with self.assertRaisesRegex(d.Refused, "^bundle_hash_mismatch$"): plan.publish_scan("mover-max", packet, now=self.now)

    def test_observe_and_native_account_checks_take_account_mutex_and_namespace(self):
        observation = {"account_identity_sha256": "a" * 64, "positions": [], "orders": [], "open_orders_complete": True}
        with patch.object(d, "native_flat_observation", return_value=observation):
            with patch.object(self.plan, "namespace_ready", side_effect=d.Refused("SYN_namespace_requires_recovery")):
                with self.assertRaisesRegex(d.Refused, "^SYN_namespace_requires_recovery$"): self.plan.observe("lev4", "new", now=self.now)
            with d.exclusive(self.root / "SYN-account.lock"):
                with self.assertRaisesRegex(d.Refused, "^writer_busy$"): self.plan.observe("lev4", "new", now=self.now)
        self.issue()
        d.save(self.plan.active_path("start"), load_json(self.plan.slot("lev4") / "GO.json"))
        with d.exclusive(self.root / "SYN-account.lock"):
            with self.assertRaisesRegex(d.Refused, "^writer_busy$"): self.plan.check_account("lev4", "start", observation)
        with patch.object(self.plan, "namespace_ready", side_effect=d.Refused("SYN_namespace_requires_recovery")):
            with self.assertRaisesRegex(d.Refused, "^SYN_namespace_requires_recovery$"):
                self.plan.check_account("lev4", "start", observation)

    def test_lane_a_native_inventory_and_process_guards(self):
        self.lane.stop()
        answer = SimpleNamespace(returncode=0, stdout="")
        proc = self.root / "proc" / "1"; proc.mkdir(parents=True)
        (proc / "cmdline").write_bytes(b"unrelated\0")
        original_glob = Path.glob
        def glob(path, pattern):
            return iter([proc]) if str(path) == "/proc" else original_glob(path, pattern)
        with patch.object(d.subprocess, "run", return_value=answer), patch.object(Path, "glob", glob):
            self.assertTrue(d.lane_a_absent())
            answer.returncode = 1
            with self.assertRaisesRegex(d.Refused, "^lane_A_inventory_unavailable$"): d.lane_a_absent()
            answer.returncode = 0
            answer.stdout = "paper-rth-syn.service loaded active running description"
            with self.assertRaisesRegex(d.Refused, "^lane_A_writer_active$"): d.lane_a_absent()
            answer.stdout = ""
            launcher = Path.home() / ".local/state/native-agent-stack/alpaca-paper/trials/series-driver.sh"
            (proc / "cmdline").write_bytes(str(launcher).encode() + b"\0")
            with self.assertRaisesRegex(d.Refused, "^lane_A_writer_active$"): d.lane_a_absent()
        with patch.object(d.subprocess, "run", return_value=answer), patch.object(Path, "glob", return_value=iter([])):
            with self.assertRaisesRegex(d.Refused, "^lane_A_process_inventory_unavailable$"): d.lane_a_absent()
        good = SimpleNamespace(returncode=0, stdout="")
        for failed_type in ["--type=service", "--type=timer"]:
            def result(argv, **_):
                return SimpleNamespace(returncode=1, stdout="") if failed_type in argv else good
            with patch.object(d.subprocess, "run", side_effect=result), patch.object(Path, "glob", glob):
                (proc / "cmdline").write_bytes(b"unrelated\0")
                with self.assertRaisesRegex(d.Refused, "^lane_A_inventory_unavailable$"): d.lane_a_absent()
        def pending(argv, **_):
            return SimpleNamespace(returncode=0, stdout="paper-pre-syn.timer loaded active waiting description") if "--type=timer" in argv else good
        with patch.object(d.subprocess, "run", side_effect=pending), patch.object(Path, "glob", glob):
            with self.assertRaisesRegex(d.Refused, "^lane_A_timer_pending$"): d.lane_a_absent()

    def test_native_partial_flat_quote_and_clock_preflight_guards(self):
        cfg = self.plan.config("lev4")
        from runner import validate_preflight
        # The SDK/provider is the only substituted seam; real validation must
        # reject complete-but-nonflat, incomplete inventory and stale quotes.
        obs = {"account_identity_sha256": "a" * 64, "open_orders_complete": False}
        with patch.dict(d.os.environ, {"APCA_API_KEY_ID": "SYN", "APCA_API_SECRET_KEY": "SYN"}), \
                patch("transport.preflight", return_value=obs):
            with self.assertRaisesRegex(d.Refused, "^open_order_inventory_incomplete$"):
                d.native_flat_observation(lambda *_: None, config=cfg)
        from tests.test_adaptive_paper_runner import _paper_ready_observation
        import copy
        good = _paper_ready_observation(int(self.now * 1e9), symbols=tuple(cfg["benchmarks"]))
        good["open_orders_complete"] = True
        with patch.dict(d.os.environ, {"APCA_API_KEY_ID": "SYN", "APCA_API_SECRET_KEY": "SYN"}), \
                patch.object(d.time, "time", return_value=self.now):
            for field, value, reason in [
                ("positions", [{"symbol": "SPY", "qty": "1"}], "clean_native_start_requires_flat_account"),
                ("orders", [{}], "clean_native_start_requires_flat_account")]:
                altered = copy.deepcopy(good); altered[field] = value
                with patch("transport.preflight", return_value=altered):
                    from safety import SafetyError
                    with self.assertRaisesRegex(SafetyError, reason):
                        d.native_flat_observation(lambda *_: None, config=cfg)

    def mover_packet(self):
        bundle = self.root / "mover-bundle"
        d.build(bundle, deployment="scan-pass", order=["mover-max"])
        plan = d.Deployment(bundle, self.plan.state)
        packet = self.root / "packet"
        row = {"symbol": "SPY", "rank": 1, "price_at_t": "100", "dollar_volume_at_t": "10000000",
               "entry_bar_dollar_volume": "1000000", "gain_pct_at_t": "25"}
        d.save(packet / "scan.json", {"schema_version": 1, "kind": "mover_scan",
            "protocol": "mover-early-entry-v1-20260924", "rule": "10:00|G20|V1000000|any",
            "scan_time": "2026-10-12T15:00:00Z", "symbols": [row]})
        d.save(packet / "ranked-100.json", {**d.LABEL, "symbols": [row]})
        d.save(packet / "input.json", {**d.LABEL, "source": {"mode": "intraday",
            "signal_cutoff_utc": "2026-10-12T15:00:00Z", "observed_at": "2026-10-12T15:00:00Z"}})
        commitment = {**d.LABEL, "config_file_sha256": plan.stage("mover-max")["config_file_sha256"],
            "config_sha256": plan.stage("mover-max")["config_file_sha256"],
            "effective_config_sha256": plan.stage("mover-max")["config_sha256"],
            "scan_sha256": d.digest(packet / "scan.json"), "ranked_sha256": d.digest(packet / "ranked-100.json"),
            "input_sha256": d.digest(packet / "input.json"), "code_sha256": "a" * 64,
            "observed_at": "2026-10-12T15:00:00Z", "source_observed_at": "2026-10-12T15:00:00Z",
            "session_date": "2026-10-12"}
        d.save(packet / "commitment.json", commitment)
        return plan, packet, commitment

    def test_producer_replacement_never_changes_committed_trial_bytes(self):
        plan, packet, commitment = self.mover_packet()
        original = (packet / "scan.json").read_bytes()
        changed = json.loads(original); changed["regime"] = {"factor": "0.5"}
        real_read, real_digest = d.read_bytes, d.digest
        def replace():
            (packet / "scan.json").write_text(json.dumps(changed))
        def read(path, *args, **kwargs):
            body = real_read(path, *args, **kwargs)
            if Path(path) == packet / "input.json": replace()
            return body
        def digest(path):
            value = real_digest(path)
            if Path(path) == packet / "input.json": replace()
            return value
        with patch.object(d, "read_bytes", side_effect=read), patch.object(d, "digest", side_effect=digest):
            ready = plan.publish_scan("mover-max", packet, now=self.now)
        self.assertEqual(ready["engine_scan_sha256"], commitment["scan_sha256"])
        verified, body = plan.scan_binding("mover-max", self.now, return_bytes=True)
        self.assertEqual(hashlib.sha256(body).hexdigest(), commitment["scan_sha256"])
        self.assertEqual(body, original)

    def test_each_scan_commitment_config_clock_rank_and_retained_hash_is_required(self):
        plan, packet, good = self.mover_packet()
        for field, value, reason in [
            ("paper_lane", "A", "exploratory_label_required"),
            ("config_file_sha256", "c" * 64, "scan_config_binding_mismatch"),
            ("effective_config_sha256", "c" * 64, "scan_config_binding_mismatch"),
            ("scan_sha256", "c" * 64, "commitment_hash_mismatch"),
            ("ranked_sha256", "c" * 64, "commitment_hash_mismatch"),
            ("input_sha256", "c" * 64, "commitment_hash_mismatch"),
            ("code_sha256", "not-a-hash", "commitment_code_hash_missing"),
            ("session_date", "2026-10-11", "scan_session_mismatch"),
            ("observed_at", "2026-10-12T14:59:00Z", "input_observation_clock_mismatch"),
            ("source_observed_at", "2026-10-12T15:01:00Z", "input_observation_clock_mismatch")]:
            d.save(packet / "commitment.json", dict(good, **{field: value}))
            with self.subTest(field=field):
                with self.assertRaisesRegex(d.Refused, "^" + reason + "$"):
                    plan.publish_scan("mover-max", packet, now=self.now)
        d.save(packet / "commitment.json", good)
        ready = plan.publish_scan("mover-max", packet, now=self.now)
        retained = plan.state / "inputs" / ready["commitment_sha256"]
        wrong = dict(good, scan_sha256="c" * 64)
        d.save(retained / "commitment.json", wrong)
        # Even if the visible ready record is changed to its new digest, the
        # retained commitment's own scan hash must independently reject.
        snapshot = {name: d.read_bytes(retained / name) for name in
                    ["scan.json", "ranked-100.json", "input.json", "commitment.json"]}
        with self.assertRaisesRegex(d.Refused, "^commitment_hash_mismatch$"):
            plan.scan_snapshot("mover-max", snapshot, self.now)

    def test_scan_source_cutoff_cannot_be_restamped_or_rank_prefix_changed(self):
        plan, packet, good = self.mover_packet()
        original_input = (packet / "input.json").read_bytes()
        for source, reason in [
            ({"mode": "morning", "signal_cutoff_utc": "2026-10-12T15:00:00Z", "observed_at": good["source_observed_at"]},
             "unsupported_source_cutoff_mode"),
            ({"mode": "intraday", "signal_cutoff_utc": "2026-10-12T15:00:00", "observed_at": good["source_observed_at"]},
             "input_observation_clock_missing"),
            ({"mode": "intraday", "signal_cutoff_utc": "2026-10-12T14:54:00Z", "observed_at": good["source_observed_at"]},
             "input_data_stale")]:
            d.save(packet / "input.json", {**d.LABEL, "source": source})
            commitment = dict(good, input_sha256=d.digest(packet / "input.json"),
                              observed_at=source["signal_cutoff_utc"])
            d.save(packet / "commitment.json", commitment)
            with self.assertRaisesRegex(d.Refused, "^" + reason + "$"):
                plan.publish_scan("mover-max", packet, now=self.now)
        (packet / "input.json").write_bytes(original_input)
        wrong = d.read_json(packet / "ranked-100.json")
        wrong["symbols"][0]["symbol"] = "QQQ"
        d.save(packet / "ranked-100.json", wrong)
        d.save(packet / "commitment.json", dict(good, ranked_sha256=d.digest(packet / "ranked-100.json")))
        with self.assertRaisesRegex(d.Refused, "^ranked_top_scan_mismatch$"):
            plan.publish_scan("mover-max", packet, now=self.now)

    def test_scan_visibility_active_pending_collision_and_ready_are_guarded(self):
        with self.assertRaisesRegex(d.Refused, "^scan_requires_mover_stage$"):
            self.plan.publish_scan("lev4", self.root, now=self.now)
        plan, packet, good = self.mover_packet()
        d.save(plan.active_path("active"), {})
        with self.assertRaisesRegex(d.Refused, "^scan_already_bound_or_active$"):
            plan.publish_scan("mover-max", packet, now=self.now)
        plan.active_path("active").unlink()
        pending = plan.slot("mover-max") / "GO.sha256"; pending.parent.mkdir(parents=True); pending.write_text("SYN")
        with self.assertRaisesRegex(d.Refused, "^scan_already_bound_or_active$"):
            plan.publish_scan("mover-max", packet, now=self.now)
        pending.unlink()
        ready = plan.publish_scan("mover-max", packet, now=self.now)
        path = plan.slot("mover-max") / "SCAN-READY.json"
        d.save(path, dict(ready, commitment_sha256="../unsafe"))
        with self.assertRaisesRegex(d.Refused, "^unsafe_commitment_hash$"): plan.scan_binding("mover-max", self.now)
        d.save(path, dict(ready, stage="other"))
        with self.assertRaisesRegex(d.Refused, "^scan_ready_binding_mismatch$"): plan.scan_binding("mover-max", self.now)
        d.save(path, ready)
        retained = plan.state / "inputs" / ready["commitment_sha256"] / "scan.json"
        retained.write_text("changed")
        with self.assertRaisesRegex(d.Refused, "^immutable_input_collision$"):
            plan.publish_scan("mover-max", packet, now=self.now)

    def test_manifest_inventory_label_engine_session_and_runtime_are_required(self):
        for field, value, reason in [
            ("paper_lane", "A", "exploratory_label_required"), ("evidence_class", "SYN", "exploratory_label_required"),
            ("order", [], "invalid_stage_order"), ("order", ["lev4", "lev4"], "invalid_stage_order"),
            ("order", ["unknown"], "stage_inventory_mismatch")]:
            original = (self.bundle / "deployment.json").read_bytes()
            value_manifest = json.loads(original); value_manifest[field] = value
            d.save(self.bundle / "deployment.json", value_manifest)
            with self.assertRaisesRegex(d.Refused, "^" + reason + "$"): d.Deployment(self.bundle, self.plan.state)
            (self.bundle / "deployment.json").write_bytes(original)
        for field, value, reason in [("engine_kind", "other", "unsupported_engine_kind"),
                                    ("session_kind", "PRE", "unsupported_session_kind")]:
            original_bytes = (self.bundle / "deployment.json").read_bytes()
            original = load_json(self.bundle / "deployment.json")
            original["stages"]["lev4"][field] = value
            d.save(self.bundle / "deployment.json", original)
            with self.assertRaisesRegex(d.Refused, "^" + reason + "$"): d.Deployment(self.bundle, self.plan.state)
            (self.bundle / "deployment.json").write_bytes(original_bytes)
        with self.assertRaisesRegex(d.Refused, "^unknown_stage$"): self.plan.stage("unknown")
        for duration in [1319]:
            self.plan.stage("lev4")["runtime_max_seconds"] = duration
            if duration < 1320:
                with self.assertRaisesRegex(d.Refused, "^stage_runtime_or_namespace_mismatch$"): self.plan.verify()

    def test_missing_native_owner_fallback_is_only_get_and_rc_not_fabricated(self):
        d.save(self.plan.active_path("start"), {"stage": "lev4", "trial": "start",
            "bundle_sha256": self.plan.bundle_hash(), "config_sha256": self.plan.stage("lev4")["config_sha256"]})
        modes = []
        def native(mode, stage, trial, output):
            modes.append(mode)
            if mode == "recover":
                d.save(output, {"status": "refused", "reason": "no_owned_trial_to_recover"}); return 2
            d.save(output, {"status": "passed", "flat": True, "positions": [], "unresolved_orders": [],
                            "reconciliation": {"positions": 0, "open_orders": 0}}); return 0
        with patch.object(self.plan, "native_call", side_effect=native): self.plan.recover("start")
        self.assertEqual(modes, ["recover", "flat"])

    def test_identifiers_stage_lists_and_roots_are_not_word_checks(self):
        with self.assertRaisesRegex(d.Refused, "^unsafe_artifact_path$"):
            d.safe_path(self.root / ".." / "escaped")
        for bad in ["", "Bad", "../x", "x" * 49]:
            with self.assertRaisesRegex(d.Refused, "^invalid_identifier$"): d.identifier(bad)
        with self.assertRaisesRegex(d.Refused, "^invalid_native_trial$"): d.trial_identifier("x" * 25)
        for order in [[], ["mover-max", "mover-max"]]:
            with self.assertRaisesRegex(d.Refused, "^invalid_stage_order$"):
                d.build(self.root / "bad", deployment="valid", order=order)
        with self.assertRaisesRegex(d.Refused, "^unsupported_stage$"):
            d.build(self.root / "bad", deployment="valid", order=["unknown"])
        with self.assertRaisesRegex(d.Refused, "^exploratory_state_root_required$"):
            d.Deployment(self.bundle, self.root / "trials" / "exploratory")
        for bad in ["path with space", "percent%name"]:
            with self.assertRaisesRegex(d.Refused, "^unsupported_systemd_path$"): d.systemd_path(self.root / bad)

    def test_custom_pre_and_renamed_mover_rungs_are_refused(self):
        cfg = json.loads((SOURCE / "config-mover.json").read_text())
        for stage in ["mover1", "mover2"]:
            with self.assertRaisesRegex(d.Refused, "^unregistered_sizing_setting$"):
                d.build(self.root / stage, deployment="denied", order=[stage])
        spec = {"renamed": {"engine_kind": "mover", "session_kind": "RTH", "config": str(SOURCE / "config-mover.json")}}
        with self.assertRaisesRegex(d.Refused, "^unregistered_sizing_setting$"):
            d.build(self.root / "alias", deployment="denied", order=["renamed"], stage_specs=spec)
        spec["renamed"]["session_kind"] = "PRE"
        with self.assertRaisesRegex(d.Refused, "^unsupported_stage_kind$"):
            d.build(self.root / "premarket", deployment="denied", order=["renamed"], stage_specs=spec)
        with self.assertRaisesRegex(d.Refused, "^producer_rule_unsupported$"):
            d.build(self.root / "post", deployment="denied", order=["postmover-max"])
        for rung in [1, 2, 4]:
            spec["renamed"] = {"engine_kind": "adaptive", "session_kind": "RTH",
                              "config": str(SOURCE / ("config-leverage-" + str(rung) + "x.json"))}
            with self.assertRaisesRegex(d.Refused, "^unregistered_sizing_setting$"):
                d.build(self.root / ("adaptive-rung-" + str(rung)), deployment="denied",
                        order=["renamed"], stage_specs=spec)

    def test_t22_builder_inputs_and_absent_native_capability_fail_closed(self):
        native = d.read_json(SOURCE / "config-sip.json")
        producer = self.root / "t22-producer"
        producer.mkdir()
        cfg = producer / "config.json"
        factors = producer / "factors.json"
        factors.write_text('{"kind":"SYN_factor_fixture"}')
        block = {"family": "momentum_breakout", "preset": "conservative-v1", "instance_id": "SYN",
                 "cohort_sha256": "a" * 64, "factors_file": "factors.json", "factors_sha256": d.digest(factors)}
        spec = {"t22-one": {"engine_kind": "t22", "session_kind": "RTH", "config": str(cfg)}}
        d.save(cfg, native)
        with self.assertRaisesRegex(d.Refused, "^t22_config_required$"):
            d.build(self.root / "missing-t22", deployment="denied", order=["t22-one"], stage_specs=spec)
        for file in ["../outside.json", "/SYN-not-a-real-file"]:
            d.save(cfg, dict(native, t22=dict(block, factors_file=file)))
            with self.assertRaisesRegex(d.Refused, "^unsafe_artifact_path$"):
                d.build(self.root / ("abs" if file.startswith("/") else "up"), deployment="denied",
                        order=["t22-one"], stage_specs=spec)
        d.save(cfg, dict(native, t22=dict(block, factors_sha256="c" * 64)))
        with self.assertRaisesRegex(d.Refused, "^factor_hash_mismatch$"):
            d.build(self.root / "bad-factor", deployment="denied", order=["t22-one"], stage_specs=spec)
        d.save(cfg, dict(native, t22=block))
        dest = self.root / "collision"; (dest / "configs").mkdir(parents=True)
        (dest / "configs/factors.json").write_text("different")
        with self.assertRaisesRegex(d.Refused, "^factor_input_collision$"):
            d.build(dest, deployment="denied", order=["t22-one"], stage_specs=spec)
        with self.assertRaisesRegex(d.Refused, "^t22_dispatch_not_available$"):
            d.build(self.root / "no-native", deployment="denied", order=["t22-one"], stage_specs=spec)
        spec["t22-one"]["engine_kind"] = "other"
        with self.assertRaisesRegex(d.Refused, "^unsupported_stage_kind$"):
            d.build(self.root / "unknown-kind", deployment="denied", order=["t22-one"], stage_specs=spec)

    def test_no_output_recover_is_unknown_and_never_becomes_flat_completion(self):
        d.save(self.plan.active_path("start"), {"stage": "lev4", "trial": "start",
            "bundle_sha256": self.plan.bundle_hash(), "config_sha256": self.plan.stage("lev4")["config_sha256"]})
        with patch.object(self.plan, "native_call", return_value=2) as dispatch:
            with self.assertRaisesRegex(d.Refused, "^native_recovery_output_missing$"): self.plan.recover("start")
            self.assertEqual(dispatch.call_count, 1)
        self.assertTrue(self.plan.active_path("start").is_file())
        self.assertFalse((self.plan.instance("start") / "handoff.json").exists())

    def test_recover_each_flat_proof_operand_and_foreign_stop(self):
        good = {"status": "passed", "flat": True, "positions": [], "unresolved_orders": [],
                "reconciliation": {"positions": 0, "open_orders": 0}}
        changes = [("status", "needs_attention"), ("flat", False), ("positions", [{}]),
                   ("unresolved_orders", [{}]), ("reconciliation", {"positions": 1, "open_orders": 0}),
                   ("reconciliation", {"positions": 0, "open_orders": 1})]
        for key, value in changes:
            d.save(self.plan.active_path("start"), {"stage": "lev4", "trial": "start",
                "bundle_sha256": self.plan.bundle_hash(), "config_sha256": self.plan.stage("lev4")["config_sha256"]})
            def native(mode, stage, trial, output):
                d.save(output, dict(good, **{key: value})); return 0
            with patch.object(self.plan, "native_call", side_effect=native):
                with self.assertRaisesRegex(d.Refused, "^recovery_not_flat$"): self.plan.recover("start")
        def nonzero(mode, stage, trial, output):
            d.save(output, good); return 2
        with patch.object(self.plan, "native_call", side_effect=nonzero):
            with self.assertRaisesRegex(d.Refused, "^recovery_not_flat$"): self.plan.recover("start")
        stop = self.plan.state.parent / "STOP"
        stop.unlink()
        stop.touch()
        (self.plan.instance("start") / "stop-hook.json").unlink()
        def native(mode, stage, trial, output):
            d.save(output, good); return 0
        with patch.object(self.plan, "native_call", side_effect=native): self.plan.recover("start")
        self.assertTrue(stop.exists())


if __name__ == "__main__":
    unittest.main()
