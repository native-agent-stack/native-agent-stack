"""Exploratory T22 dispatch: fixtures never contact a broker."""
import importlib
import importlib.util
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import asyncio
from decimal import Decimal
import time
import sys
import contextlib
import io
from unittest.mock import Mock, patch

SOURCE = Path(__file__).resolve().parents[1] / "blueprints/us-equities/adaptive-paper"
sys.path.insert(0, str(SOURCE))


@contextlib.contextmanager
def dispatch_rth_context():
    """One fixed synthetic session window for nested calendar lookups.

    Native event/quote clocks stay real. The shared fixture shifts a window
    for each queried timestamp; a nested PRE lookup otherwise reconstructs
    an already expired close after the real regular session ends.
    """
    from datetime import datetime, timezone
    from tests.test_us_equities_strategies import synthetic_rth_context
    modules = [importlib.import_module("blueprints.us-equities.adaptive-paper.sessions"),
               importlib.import_module("sessions")]
    with synthetic_rth_context(), contextlib.ExitStack() as stack:
        window = modules[0].session_at(datetime.now(timezone.utc))
        for module in {id(m): m for m in modules}.values():
            stack.enter_context(patch.object(module, "session_at", return_value=window))
        yield


def packet_config(directory, *, stamp=None, until=None):
    now = time.time_ns()
    stamp = now - 301_000_000_000 if stamp is None else stamp
    until = now + 600_000_000_000 if until is None else until
    data = dict(instrument_id="SPY.ALPACA", cohort_sha256="a" * 64,
                ts_event=stamp, ts_init=stamp, valid_until_ns=until, evidence_class="exploratory",
                halted=False, values={"atr_price": "0.2", "entry_trigger": "100",
                "momentum_20": "0.03", "range_breakout": "1.02", "tight_range_state": "0.02"})
    source_bytes = json.dumps(data).encode()
    (directory / "source.json").write_bytes(source_bytes)
    producer = importlib.import_module("t22_producer")
    raw, receipt = producer.produce(source_bytes)
    (directory / "producer.json").write_bytes(receipt)
    (directory / "factors.json").write_bytes(raw)
    config = json.loads((SOURCE / "config.json").read_text())
    config.update(paper_lane="B", evidence_class="exploratory", symbols=["SPY"], benchmarks=["SPY"],
                  max_held_symbols=1, feed="sip")
    config["t22"] = dict(family="momentum_breakout", preset="conservative-v1", instance_id="trial_one",
                         cohort_sha256="a" * 64, factors_file="factors.json",
                         factors_sha256=hashlib.sha256(raw).hexdigest())
    config["t22"].update(source_file="source.json", producer_receipt="producer.json")
    path = directory / "config.json"
    path.write_text(json.dumps(config))
    return path


class ExploratoryContract(unittest.TestCase):
    def test_recovery_preflight_does_not_validate_an_absent_execution_packet(self):
        runner = importlib.import_module("runner")
        from tests.test_adaptive_paper_runner import _paper_ready_observation
        with tempfile.TemporaryDirectory(dir="/var/tmp") as temporary:
            path = packet_config(Path(temporary))
            config, _, policy = runner.load_config(path, require_t22_packet=False)
            policy = importlib.import_module("sessions").validate_session_policy(config)
            observation = _paper_ready_observation(time.time_ns())
            runner.validate_preflight(observation, config, require_open=False, allow_existing=True, session_policy=policy)
            with self.assertRaisesRegex(importlib.import_module("safety").SafetyError, "t22_packet_required_for_execution"):
                runner.validate_preflight(observation, config, require_open=False, allow_existing=False, session_policy=policy)

    def test_unsupported_venue_cannot_pass_a_matching_symbol(self):
        dispatch = importlib.import_module("t22_dispatch")
        with tempfile.TemporaryDirectory(dir="/var/tmp") as temporary:
            root = Path(temporary)
            path = packet_config(root)
            config = json.loads(path.read_text())
            packet = json.loads((root / "factors.json").read_text())
            packet["instrument_id"] = "SPY.OTHER"
            raw = json.dumps(packet).encode()
            (root / "factors.json").write_bytes(raw)
            with self.assertRaisesRegex(ValueError, "^t22_factor_scope_mismatch$"):
                dispatch.load_dispatch(config | {"symbols": ["SPY.OTHER"], "t22": config["t22"] |
                    {"factors_sha256": hashlib.sha256(raw).hexdigest()}}, path)
    def test_relative_source_and_receipt_guards_have_independent_witnesses(self):
        dispatch = importlib.import_module("t22_dispatch")
        with tempfile.TemporaryDirectory(dir="/var/tmp") as temporary:
            parent = Path(temporary).resolve()
            for value in (1, "/fixture.json", "../fixture.json", "fixture.txt"):
                with self.subTest(value=value), self.assertRaisesRegex(ValueError, "^t22_relative_json_packet_required$"):
                    dispatch.relative_file(parent, value)
            with tempfile.TemporaryDirectory(dir="/var/tmp") as outside:
                target = Path(outside) / "source.json"
                target.write_text("{}")
                (parent / "escape.json").symlink_to(target)
                with self.assertRaisesRegex(ValueError, "^t22_packet_outside_config_directory$"):
                    dispatch.relative_file(parent, "escape.json")

    def test_producer_registry_and_import_origin_are_binding(self):
        from types import SimpleNamespace
        dispatch = importlib.import_module("t22_dispatch")
        with tempfile.TemporaryDirectory(dir="/var/tmp") as temporary:
            root = Path(temporary)
            path = packet_config(root)
            config = json.loads(path.read_text())
            packet = (root / "factors.json").read_bytes()
            snapshot = dispatch.contracts.FactorSnapshot.from_json(json.loads(packet))
            entry = json.loads(dispatch.PRODUCER_REGISTRY.read_bytes())
            item = entry["producers"]["t22-source-normalizer-v1"]
            registry = root / "registry.json"
            for mode in ("escape", "changed_code", "module"):
                changed = json.loads(json.dumps(entry))
                if mode == "escape": changed["producers"]["t22-source-normalizer-v1"]["code_path"] = str(path)
                if mode == "changed_code": changed["producers"]["t22-source-normalizer-v1"]["code_path"] = "tests/test_t22_paper_dispatch.py"
                if mode == "escape":
                    digest = hashlib.sha256(path.read_bytes()).hexdigest()
                    changed["producers"]["t22-source-normalizer-v1"]["code_sha256"] = digest
                    receipt_path = root / "producer.json"
                    receipt = json.loads(receipt_path.read_text())
                    receipt["code_sha256"] = digest
                    receipt_path.write_text(json.dumps(receipt))
                else:
                    receipt_path = root / "producer.json"
                    receipt = json.loads(receipt_path.read_text())
                    receipt["code_sha256"] = item["code_sha256"]
                    receipt_path.write_text(json.dumps(receipt))
                registry.write_text(json.dumps(changed))
                expected = "t22_registered_producer_module_mismatch" if mode == "module" else "t22_registered_producer_code_mismatch"
                with self.subTest(mode=mode), patch.object(dispatch, "PRODUCER_REGISTRY", registry):
                    if mode == "module":
                        with patch.object(dispatch.importlib, "import_module", return_value=SimpleNamespace(__file__=str(path), produce=Mock(return_value=(packet, b"")))):
                            with self.assertRaisesRegex(ValueError, "^" + expected + "$"):
                                dispatch.validate_producer(config["t22"], root, packet, snapshot)
                    else:
                        with self.assertRaisesRegex(ValueError, "^" + expected + "$"):
                            dispatch.validate_producer(config["t22"], root, packet, snapshot)
    def test_producer_source_receipt_and_code_guards_each_refuse(self):
        dispatch = importlib.import_module("t22_dispatch")
        for kind, expected in [
            ("source_hash", "t22_source_hash_mismatch"),
            ("source_path", "t22_relative_json_packet_required"),
            ("receipt_path", "t22_relative_json_packet_required"),
            ("receipt_schema", "t22_producer_receipt_invalid"),
            ("receipt_bool_schema", "t22_producer_receipt_invalid"),
            ("receipt_type", "t22_producer_receipt_invalid"),
            ("receipt extra fields", "t22_producer_receipt_invalid"),
            ("producer", "t22_producer_code_not_reviewed"),
            ("code", "t22_producer_code_not_reviewed"),
            ("receipt_source", "t22_producer_receipt_binding_mismatch"),
            ("receipt_packet", "t22_producer_receipt_binding_mismatch"),
            ("packet", "t22_packet_differs_from_deterministic_source"),
        ]:
            with self.subTest(kind=kind), tempfile.TemporaryDirectory(dir="/var/tmp") as temporary:
                root = Path(temporary)
                path = packet_config(root)
                config = json.loads(path.read_text())
                receipt_path = root / "producer.json"
                receipt = json.loads(receipt_path.read_text())
                if kind == "source_hash":
                    (root / "source.json").write_bytes((root / "source.json").read_bytes() + b" ")
                elif kind.endswith("path"):
                    config["t22"]["source_file" if kind == "source_path" else "producer_receipt"] = "../outside.json"
                elif kind == "receipt_schema": receipt["schema_version"] = 2
                elif kind == "receipt_bool_schema": receipt["schema_version"] = True
                elif kind == "receipt_type": receipt = list(receipt)
                elif kind == "receipt extra fields": receipt["extra"] = True
                elif kind == "producer": receipt["producer"] = "unreviewed"
                elif kind == "code": receipt["code_sha256"] = "a" * 64
                elif kind == "receipt_source": receipt["source_sha256"] = "a" * 64
                elif kind == "receipt_packet": receipt["packet_sha256"] = "a" * 64
                elif kind == "packet":
                    snapshot = json.loads((root / "factors.json").read_text())
                    snapshot["values"]["momentum_20"] = "0.04"
                    raw = json.dumps(snapshot).encode()
                    (root / "factors.json").write_bytes(raw)
                    config["t22"]["factors_sha256"] = receipt["packet_sha256"] = hashlib.sha256(raw).hexdigest()
                receipt_path.write_text(json.dumps(receipt))
                with self.assertRaisesRegex(ValueError, "^" + expected + "$"):
                    dispatch.load_dispatch(config, path)

    def test_loader_each_guard_has_a_specific_negative_witness(self):
        dispatch = importlib.import_module("t22_dispatch")
        with tempfile.TemporaryDirectory(dir="/var/tmp") as temporary:
            root = Path(temporary)
            path = packet_config(root)
            original = json.loads(path.read_text())
            negative = [
                ({"paper_lane": "A"}, "invalid_t22_exploratory_configuration"),
                ({"evidence_class": "synthetic"}, "invalid_t22_exploratory_configuration"),
                ({"exploratory_exit_preset": {"name": "baseline"}}, "invalid_t22_exploratory_configuration"),
                ({"t22": list(original["t22"])}, "invalid_t22_exploratory_configuration"),
                ({"t22": original["t22"] | {"extra": True}}, "invalid_t22_exploratory_configuration"),
                ({"sessions": {"overnight_holds": True}}, "invalid_t22_exploratory_configuration"),
                ({"rotation": {"enabled": True}}, "invalid_t22_exploratory_configuration"),
                ({"max_leverage": "2"}, "invalid_t22_exploratory_configuration"),
                ({"max_leverage": None}, "invalid_t22_exploratory_configuration"),
                ({"max_leverage": Decimal("1")}, "invalid_t22_exploratory_configuration"),
                ({"t22": original["t22"] | {"family": "unknown"}}, "invalid_t22_exploratory_configuration"),
                ({"t22": original["t22"] | {"preset": "unknown"}}, "invalid_t22_exploratory_configuration"),
                ({"t22": original["t22"] | {"factors_file": 1}}, "invalid_t22_exploratory_configuration"),
                ({"exit_quote_max_age_seconds": True}, "t22_preset_exit_age_exceeds_interim_constraint"),
                ({"exit_quote_max_age_seconds": "3"}, "t22_preset_exit_age_exceeds_interim_constraint"),
                ({"exit_quote_max_age_seconds": float("nan")}, "t22_preset_exit_age_exceeds_interim_constraint"),
                ({"exit_quote_max_age_seconds": float("inf")}, "t22_preset_exit_age_exceeds_interim_constraint"),
                ({"exit_quote_max_age_seconds": 0}, "t22_preset_exit_age_exceeds_interim_constraint"),
                ({"t22": original["t22"] | {"factors_sha256": 1}}, "t22_factor_hash_required"),
                ({"t22": original["t22"] | {"factors_sha256": "a" * 63}}, "t22_factor_hash_required"),
                ({"t22": original["t22"] | {"factors_file": "../factors.json"}}, "t22_relative_json_packet_required"),
                ({"t22": original["t22"] | {"factors_file": "factors.txt"}}, "t22_relative_json_packet_required"),
                ({"symbols": []}, "t22_single_instrument_required"),
                ({"symbols": ("SPY",)}, "t22_single_instrument_required"),
                ({"symbols": ["SPY", "QQQ"]}, "t22_single_instrument_required"),
            ]
            for updates, reason in negative:
                with self.subTest(reason=reason, updates=updates):
                    with self.assertRaisesRegex(ValueError, "^" + reason + "$"):
                        dispatch.load_dispatch(original | updates, path)
            for age in (1, 10):
                self.assertIsNotNone(dispatch.load_dispatch(original | {"exit_quote_max_age_seconds": age}, path))
            # Test the symlink traversal guard with a real outside fixture.
            with tempfile.TemporaryDirectory(dir="/var/tmp") as outside:
                target = Path(outside) / "packet.json"
                target.write_bytes((root / "factors.json").read_bytes())
                (root / "escape.json").symlink_to(target)
                with self.assertRaisesRegex(ValueError, "^t22_packet_outside_config_directory$"):
                    dispatch.load_dispatch(original | {"t22": original["t22"] | {"factors_file": "escape.json"}}, path)
            for key in ("source_file", "producer_receipt"):
                for value in (1, "/fixture.json", "../fixture.json", "fixture.txt"):
                    with self.subTest(key=key, value=value), self.assertRaisesRegex(ValueError, "^t22_relative_json_packet_required$"):
                        dispatch.load_dispatch(original | {"t22": original["t22"] | {key: value}}, path, read_packet=False)

    def test_packet_scope_required_and_positive_factors_each_refuse(self):
        dispatch = importlib.import_module("t22_dispatch")
        with tempfile.TemporaryDirectory(dir="/var/tmp") as temporary:
            root = Path(temporary)
            path = packet_config(root)
            config = json.loads(path.read_text())
            snapshot = json.loads((root / "factors.json").read_text())
            cases = [({"instrument_id": "SPY.OTHER"}, "t22_factor_scope_mismatch"),
                     ({"instrument_id": "QQQ.ALPACA"}, "t22_factor_scope_mismatch"),
                     ({"cohort_sha256": "c" * 64}, "t22_factor_scope_mismatch"),
                     ({"cohort_member": False}, "t22_factor_scope_mismatch"),
                     ({"evidence_class": "synthetic"}, "t22_factor_scope_mismatch")]
            for key in snapshot["values"]:
                absent = dict(snapshot["values"])
                del absent[key]
                cases.append(({"values": absent}, "t22_required_factor_missing"))
            for key in ("atr_price", "entry_trigger"):
                for value in ("0", "-1"):
                    cases.append(({"values": snapshot["values"] | {key: value}}, "t22_positive_price_factor_required"))
            for changes, reason in cases:
                raw = json.dumps(snapshot | changes).encode()
                (root / "factors.json").write_bytes(raw)
                modified = config | {"t22": config["t22"] | {"factors_sha256": hashlib.sha256(raw).hexdigest()}}
                with self.subTest(changes=changes), self.assertRaisesRegex(ValueError, "^" + reason + "$"):
                    dispatch.load_dispatch(modified, path)

    def test_availability_and_stage_boundaries_are_inclusive(self):
        from dataclasses import replace
        dispatch = importlib.import_module("t22_dispatch")
        with tempfile.TemporaryDirectory(dir="/var/tmp") as temporary:
            root = Path(temporary)
            path = packet_config(root, stamp=100, until=200)
            d = dispatch.load_dispatch(json.loads(path.read_text()), path)
            dispatch.validate_availability(d, 100)
            dispatch.validate_availability(d, 200)
            for now in (99, 201):
                with self.assertRaisesRegex(ValueError, "^t22_factors_unavailable_or_stale$"):
                    dispatch.validate_availability(d, now)
            with self.assertRaisesRegex(ValueError, "^t22_packet_required_for_execution$"):
                dispatch.validate_availability(replace(d, snapshot=None), 100)
            end = 100 + 2_000_000_000
            dispatch.validate_stage(replace(d, snapshot=replace(d.snapshot, valid_until_ns=end)),
                                    {"duration_seconds": 1, "cleanup_seconds": 1}, 100)
            with self.assertRaisesRegex(ValueError, "^t22_packet_does_not_cover_stage$"):
                dispatch.validate_stage(replace(d, snapshot=replace(d.snapshot, valid_until_ns=end-1)),
                                        {"duration_seconds": 1, "cleanup_seconds": 1}, 100)

    def test_script_launch_from_another_cwd_loads_local_package_before_mocked_credentials(self):
        import subprocess
        with tempfile.TemporaryDirectory(dir="/var/tmp") as temporary:
            root = Path(temporary) / "exploratory"
            root.mkdir()
            path = packet_config(root)
            driver = """import runpy,sys
from unittest.mock import patch
import pathlib
sys.path.insert(0,sys.argv[1])
import runner
def boundary(*args,**kwargs):
    raise RuntimeError('fixture_credential_boundary_reached')
sys.argv=['runner.py','preflight','--credentials','keychain-env','--config',sys.argv[2],'--output',sys.argv[3],'--state-root',sys.argv[4]]
with patch.object(runner,'paper_credentials',boundary):
    try: runner.main()
    except RuntimeError as e:
        if str(e)!='fixture_credential_boundary_reached': raise
        print('fixture_boundary_reached')
"""
            probe = subprocess.run([sys.executable, "-E", "-s", "-B", "-c", driver,
                str(SOURCE), str(path), str(root / "receipt.json"), str(root / "state")], cwd=Path(temporary),
                capture_output=True, text=True, timeout=15)
            self.assertEqual(probe.returncode, 0, probe.stderr)
            self.assertEqual(probe.stdout.strip(), "fixture_boundary_reached")

    def test_landed_exploratory_digest_is_equal_for_static_and_packet_loading(self):
        runner = importlib.import_module("runner")
        exploration = importlib.import_module("exploration")
        with tempfile.TemporaryDirectory(dir="/var/tmp") as temporary:
            root = Path(temporary) / "exploratory"
            root.mkdir()
            path = packet_config(root)
            normal, limits, _ = runner.load_config(path)
            expected = exploration.config_digest(normal, path.read_bytes(), limits=limits)
            static, static_limits, _ = runner.load_config(path, require_t22_packet=False)
            self.assertEqual(exploration.config_digest(static, path.read_bytes(), limits=static_limits), expected)
            for name in ("source.json", "producer.json", "factors.json"):
                (root / name).unlink()
            missing, missing_limits, _ = runner.load_config(path, require_t22_packet=False)
            self.assertEqual(exploration.config_digest(missing, path.read_bytes(), limits=missing_limits), expected)
            self.assertIsNone(missing["_t22"].snapshot)
    def test_recover_routes_past_missing_or_corrupt_packet_without_reading_it(self):
        runner = importlib.import_module("runner")
        for missing in (True, False):
            with self.subTest(missing=missing), tempfile.TemporaryDirectory(dir="/var/tmp") as temporary:
                root = Path(temporary) / "exploratory"
                root.mkdir()
                path = packet_config(root)
                if missing:
                    (root / "factors.json").unlink()
                else:
                    (root / "factors.json").write_text("corrupt fixture packet")
                argv = ["runner.py", "recover", "--credentials", "keychain-env", "--config", str(path),
                        "--output", str(root / "receipt.json"), "--state-root", str(root / "state")]
                broker = Mock(side_effect=RuntimeError("fixture_preflight_reached"))
                with patch.object(sys, "argv", argv), patch.object(runner, "paper_credentials", return_value=(None, None)), \
                     patch.object(runner, "preflight", broker), contextlib.redirect_stdout(io.StringIO()):
                    with self.assertRaisesRegex(RuntimeError, "fixture_preflight_reached"):
                        runner.main()
                broker.assert_called_once()

    def test_public_preflight_refuses_expired_or_future_factor_packet(self):
        runner = importlib.import_module("runner")
        from tests.test_adaptive_paper_runner import _paper_ready_observation
        for future in (False, True):
            with self.subTest(future=future), tempfile.TemporaryDirectory(dir="/var/tmp") as temporary:
                root = Path(temporary) / "exploratory"
                root.mkdir()
                now = time.time_ns()
                stamp = now + 600_000_000_000 if future else now - 600_000_000_000
                until = now + 1200_000_000_000 if future else now - 1
                path = packet_config(root, stamp=stamp, until=until)
                output = root / "receipt.json"
                argv = ["runner.py", "preflight", "--credentials", "keychain-env", "--config", str(path),
                        "--output", str(output), "--state-root", str(root / "state")]
                with patch.object(sys, "argv", argv), patch.object(runner, "paper_credentials", return_value=(None, None)), \
                     patch.object(runner, "preflight", return_value=_paper_ready_observation(time.time_ns())), \
                     contextlib.redirect_stdout(io.StringIO()):
                    code = runner.main()
                self.assertEqual(code, 2)
                self.assertEqual(json.loads(output.read_text())["status"], "not_ready")

    def test_forward_exploratory_factors_are_distinct_from_development(self):
        contracts = importlib.import_module("blueprints.us-equities.strategies.contracts")
        values = dict(instrument_id="SPY.ALPACA", cohort_sha256="a" * 64,
                      source_sha256="b" * 64, ts_event=1_900_000_000_000_000_000,
                      ts_init=1_900_000_000_000_000_000,
                      valid_until_ns=1_900_000_001_000_000_000,
                      values=(("momentum_20", "0.03"),), halted=False)
        snapshot = contracts.FactorSnapshot(**values, evidence_class="exploratory")
        self.assertEqual(snapshot.evidence_class, "exploratory")
        with self.assertRaisesRegex(ValueError, "development_cutoff_exceeded"):
            contracts.FactorSnapshot(**values, evidence_class="development")
        spec = contracts.StrategySpec(instrument_id="SPY.ALPACA",
                                      cohort_sha256="a" * 64,
                                      evidence_class="exploratory")
        self.assertEqual(spec.evidence_class, "exploratory")
        with self.assertRaisesRegex(ValueError, "measured_exit_policy"):
            contracts.StrategySpec(instrument_id="SPY.ALPACA",
                                   cohort_sha256="a" * 64, evidence_class="development")

    def test_runner_loads_hash_bound_exploratory_family_and_refuses_wrong_inputs(self):
        import sys
        source = Path(__file__).resolve().parents[1] / "blueprints/us-equities/adaptive-paper"
        sys.path.insert(0, str(source))
        runner = importlib.import_module("runner")
        with tempfile.TemporaryDirectory(dir="/var/tmp") as root:
            root = Path(root)
            snapshot = dict(instrument_id="SPY.ALPACA", cohort_sha256="a" * 64,
                            source_sha256="b" * 64, ts_event=1, ts_init=1,
                            valid_until_ns=2, values={"atr_price": "1", "entry_trigger": "100",
                            "momentum_20": "0.03", "range_breakout": "1.02",
                            "tight_range_state": "0.02"}, evidence_class="exploratory", halted=False)
            snapshot.pop("source_sha256")
            source_bytes = json.dumps(snapshot).encode()
            (root / "source.json").write_bytes(source_bytes)
            raw, receipt = importlib.import_module("t22_producer").produce(source_bytes)
            (root / "producer.json").write_bytes(receipt)
            (root / "factors.json").write_bytes(raw)
            config = json.loads((source / "config.json").read_text())
            config.update(paper_lane="B", evidence_class="exploratory", symbols=["SPY"], benchmarks=["SPY"],
                          max_held_symbols=1, feed="sip")
            config["t22"] = dict(family="momentum_breakout", preset="conservative-v1",
                                 instance_id="trial_one", cohort_sha256="a" * 64,
                                 factors_file="factors.json", factors_sha256=hashlib.sha256(raw).hexdigest())
            config["t22"].update(source_file="source.json", producer_receipt="producer.json")
            path = root / "config.json"
            path.write_text(json.dumps(config))
            loaded, _, _ = runner.load_config(path)
            self.assertEqual(loaded["_t22"].snapshot.instrument_id, "SPY.ALPACA")
            for updates in ({"paper_lane": "A"}, {"evidence_class": "synthetic"},
                            {"feed": "iex"},
                            {"t22": config["t22"] | {"factors_file": str(root / "factors.json")}},
                            {"exit_quote_max_age_seconds": 11},
                            {"exploratory_exit_preset": {"name": "baseline"}},
                            {"sessions": {"extended_hours": False, "overnight_holds": True,
                                          "overnight_gross_multiple": "1.0"}}):
                with self.subTest(updates=updates):
                    path.write_text(json.dumps(config | updates))
                    with self.assertRaises(ValueError):
                        runner.load_config(path)
            path.write_text(json.dumps(config))
            (root / "factors.json").write_bytes(raw + b" ")
            with self.assertRaisesRegex(ValueError, "t22_factor_hash_mismatch"):
                runner.load_config(path)


@unittest.skipUnless(importlib.util.find_spec("nautilus_trader"), "requires pinned native runtime")
class DispatchLifecycleContract(unittest.TestCase):
    def test_publish_rechecks_selected_stage_window(self):
        self.exercise("delivery_expired")
        self.exercise("delivery_short")

    def test_force_admission_reconciliation_and_teardown_boundaries(self):
        for mode in ("normal", "stop", "errors", "halted", "duration", "close",
                     "seed", "defer", "not_ready", "gap", "stale", "mark_fault",
                     "pending", "unresolved", "inactive", "reconcile_gap", "fault",
                     "wire", "no_fresh", "no_mark_method", "before_interval", "task_done",
                     "flat", "flat_pending", "flat_unresolved", "status", "frozen", "exception", "delivery_expired",
                     "boundary", "close_equal", "defer_equal", "interval_equal", "quote_equal"):
            with self.subTest(mode=mode):
                self.exercise(mode)

    def exercise(self, mode):
        from types import SimpleNamespace
        from dataclasses import replace
        dispatch = importlib.import_module("t22_dispatch")
        runner = importlib.import_module("runner")
        adapter = importlib.import_module("native_adapter")
        safety = importlib.import_module("safety")
        clock = [100.0]
        observed, reconciliation_admissions = [], []
        stop_event = asyncio.Event()
        controller = SimpleNamespace(stop=mode == "stop", events=[], quotes={
            "SPY": safety.Quote("SPY", "100", "100.01", 100),
            "QQQ": safety.Quote("QQQ", "100", "100.01", 90)},
            clock=lambda: clock[0], close=100.125 if mode == "close_equal" else 100.1 if mode == "close" else 1000,
            defer_until=100 if mode == "defer_equal" else 200 if mode == "defer" else 0, requests=[],
            start_halt_seed=Mock(), stop_halt_seed=Mock(side_effect=lambda: original_sleep(0)),
            halt_seed_pending=lambda: mode == "seed", stop_requested=lambda: controller.stop)
        ledger = SimpleNamespace(accounting=lambda: SimpleNamespace(halted_reason="fixture" if mode == "halted" else None),
            halted_reason=lambda: "fixture" if mode in {"halted", "gap", "reconcile_gap"} else None,
            positions=lambda: [] if mode.startswith("flat") else ["fixture_owned_position"],
            unresolved=lambda: ["fixture_intent"] if mode in {"unresolved", "flat_unresolved"} else [],
            freeze=Mock(), mark_to_market=Mock())
        controller.ledger = ledger
        if mode == "quote_equal":
            controller.quotes.update(BOUND=safety.Quote("BOUND", "100", "100.01", 97),
                                     EARLY=safety.Quote("EARLY", "100", "100.01", 100.25))
        if mode == "mark_fault": ledger.mark_to_market.side_effect = safety.SafetyError("fixture_risk_fault")
        strategy = SimpleNamespace(enabled=False, allow_entries=False, faulted=mode == "frozen",
            is_running=lambda: mode != "inactive", pending="fixture_pending" if mode in {"pending", "flat_pending"} else None,
            spec=dispatch.contracts.StrategySpec("SPY.ALPACA", "a"*64, evidence_class="exploratory",
                entry_deadline_ns=200_000_000_000, exit_deadline_ns=200_000_000_000),
            clock=SimpleNamespace(timestamp_ns=lambda: int(clock[0]*1e9)),
            publish_data=Mock(), fault_sink=Mock(), trace=[], callback_faults=[], flags=set(),
            instrument_id=SimpleNamespace(symbol="SPY"), client_id_prefix="t22-fixture-",
            _halt_reason=lambda now: None)
        snapshot = dispatch.contracts.FactorSnapshot("SPY.ALPACA", "a"*64, "b"*64,
            1, 1, 600_000_000_000, (), evidence_class="exploratory", halted=False)
        strategy.snapshot = snapshot
        original_fault_sink = strategy.fault_sink
        if mode == "delivery_expired": strategy.clock.timestamp_ns = lambda: 601_000_000_000
        if mode == "delivery_short": strategy.clock.timestamp_ns = lambda: 599_900_000_000
        port = SimpleNamespace(ready=mode != "not_ready", health={"reasons":
            ["stream_integrity_gap"] if mode == "gap" else ["quote_stale"] if mode == "stale" else [],
            "fresh_quotes": mode != "no_fresh"}, snapshot=Mock(side_effect=lambda: snapshot_async()),
            start=Mock(side_effect=lambda *args: original_sleep(0)),
            stop=Mock(side_effect=lambda: original_sleep(0)), mark_reconciled=Mock())
        controller.port = port
        status_chain = []
        if mode == "status":
            async def prior_status(row): status_chain.append("prior")
            port.sink_status = prior_status
        if mode == "no_mark_method": del port.mark_reconciled
        session = SimpleNamespace(errors=["fixture_error"] if mode == "errors" else [],
            execution_stats={}, reconciliation=None, fail=Mock(), on_status=Mock(), native_assertions=lambda: {})
        async def run_session():
            await port.start(lambda row: None, lambda row: None)
            if mode == "fault": strategy.fault_sink("fixture_callback_fault")
            if mode == "task_done": return
            if mode == "exception": raise RuntimeError("fixture_startup_failure")
            if mode == "status":
                row = {"symbol": "SPY", "halted": True, "ts_ns": 100_000_000_000}
                await port.sink_status(row)
                self.assertEqual(status_chain, ["prior"])
                session.on_status.assert_called_once_with(row)
            if mode == "wire":
                good = {"symbol": "SPY", "client_order_id": "t22-fixture-1", "side": "buy"}
                self.assertEqual(port.before_wire(good), (1, strategy.spec.entry_deadline_ns-1))
                for case in ("symbol", "client", "snapshot", "halt", "stop", "fault", "deadline", "expiry"):
                    row = dict(good)
                    if case == "symbol": row["symbol"] = "QQQ"
                    if case == "client": row["client_order_id"] = "another-family"
                    if case == "snapshot": strategy.snapshot = None
                    if case == "halt": strategy._halt_reason = lambda now: "fixture_halt"
                    if case == "stop": controller.stop = True
                    if case == "fault": strategy.faulted = True
                    if case == "deadline": strategy.spec = replace(strategy.spec, entry_deadline_ns=int(clock[0]*1e9))
                    if case == "expiry":
                        clock[0] = 601
                        row["side"] = "sell"
                    expected = "t22_selected_packet_identity_mismatch" if case in {"symbol", "client", "snapshot"} else "t22_halt_state_prevents_submission" if case == "halt" else "t22_factors_unavailable_or_stale" if case == "expiry" else "t22_entry_admission_closed"
                    with self.subTest(wire=case), self.assertRaisesRegex(ValueError, "^"+expected+"$"):
                        port.before_wire(row)
                    strategy.snapshot = snapshot
                    strategy._halt_reason = lambda now: None
                    controller.stop = False
                    strategy.faulted = False
                    strategy.spec = replace(strategy.spec, entry_deadline_ns=200_000_000_000)
                    clock[0] = 100.05
                controller.stop = True
                self.assertEqual(port.before_wire(good | {"side": "sell"}), (1, snapshot.valid_until_ns))
                controller.stop = False
            await stop_event.wait()
        session.run_async = run_session
        def stop_session():
            self.assertFalse(strategy.enabled)
            self.assertFalse(strategy.allow_entries)
            self.assertTrue(controller.stop)
            stop_event.set()
        session.stop = Mock(side_effect=stop_session)
        async def snapshot_async(): return {}
        original_sleep = asyncio.sleep
        original_wait_for = asyncio.wait_for
        async def bounded_wait(awaitable, timeout):
            return await original_wait_for(awaitable, min(timeout, .01))
        async def tick(delay):
            if not observed and mode == "reconcile_gap":
                ledger.freeze.assert_called_once_with("t22_stream_integrity_gap")
            if not observed and mode == "interval_equal": self.assertEqual(recon.call_count, 1)
            if not observed and mode == "quote_equal":
                self.assertEqual([q.symbol for q in ledger.mark_to_market.call_args.args[0]], ["SPY", "BOUND", "EARLY"])
            observed.append((strategy.enabled, strategy.allow_entries, strategy.spec.exit_deadline_ns, controller.stop))
            clock[0] += .0625 if mode == "boundary" else .05
            await original_sleep(0)
        def reconcile(*args):
            reconciliation_admissions.append(strategy.allow_entries)
            self.assertFalse(strategy.allow_entries)
            if clock[0] >= 100.2:
                self.assertFalse(strategy.enabled)
                self.assertTrue(controller.stop)
            if mode == "reconcile_gap": port.health["reasons"] = ["stream_integrity_gap"]
            return {"positions_match": True, "cash_match": True}
        fake_time = SimpleNamespace(time=lambda: clock[0], time_ns=lambda: int(clock[0]*1e9),
                                    monotonic=lambda: clock[0])
        config = {"_t22": dispatch.T22Dispatch("momentum_breakout", "conservative-v1", "fixture", "c"*64, snapshot),
                  "symbols": ["SPY"], "duration_seconds": .001 if mode == "duration" else .1,
                  "cleanup_seconds": .2, "quote_max_age_seconds": 3}
        if mode in {"boundary", "close_equal"}: config.update(duration_seconds=.125, cleanup_seconds=.125)
        with patch.object(dispatch, "build_strategy", return_value=strategy), \
             patch.object(adapter, "build_node", return_value=session), \
             patch("sessions.validate_session_policy", return_value=SimpleNamespace()), \
             patch.object(runner, "reconcile", side_effect=reconcile) as recon, \
             patch.object(runner, "RECONCILE_EVERY_SECONDS", 100 if mode == "before_interval" else 0 if mode == "interval_equal" else -.001), \
             patch.object(runner, "_stream_health", return_value=None), \
             patch.object(runner, "_finalize_status_and_financing"), \
             patch.dict(sys.modules, {"time": fake_time}), patch.object(asyncio, "sleep", side_effect=tick), \
             patch.object(asyncio, "wait_for", side_effect=bounded_wait):
            if mode in {"exception", "delivery_expired", "delivery_short"}:
                error, message = (RuntimeError, "fixture_startup_failure") if mode == "exception" else (ValueError, "t22_packet_does_not_cover_stage" if mode == "delivery_short" else "t22_factors_unavailable_or_stale")
                with self.assertRaisesRegex(error, "^"+message+"$"):
                    asyncio.run(dispatch.run(controller, [], config, "100000"))
                outcome = {}
            else: outcome = asyncio.run(dispatch.run(controller, [], config, "100000"))
        self.assertTrue(controller.stop)
        self.assertFalse(strategy.enabled)
        self.assertFalse(strategy.allow_entries)
        controller.start_halt_seed.assert_called_once_with(["SPY"])
        controller.stop_halt_seed.assert_called_once()
        session.stop.assert_called_once()
        port.stop.assert_called_once()
        self.assertIsNone(port.before_wire)
        if mode in {"delivery_expired", "delivery_short"}: return
        if mode == "fault":
            session.fail.assert_called_once_with("fixture_callback_fault")
            original_fault_sink.assert_called_once_with("fixture_callback_fault")
        self.assertTrue(observed)
        self.assertTrue(ledger.mark_to_market.called)
        self.assertEqual([q.symbol for q in ledger.mark_to_market.call_args.args[0]], ["SPY", "EARLY"] if mode == "quote_equal" else ["SPY"])
        self.assertEqual(strategy.publish_data.call_count, 0 if mode == "inactive" else 1)
        forced = mode in {"stop", "errors", "halted", "close", "close_equal", "gap", "mark_fault", "reconcile_gap"}
        if forced:
            self.assertFalse(observed[0][1])
            self.assertLessEqual(observed[0][2], 100_000_000_000)
        elif mode in {"seed", "defer", "not_ready", "inactive", "frozen"}:
            self.assertFalse(observed[0][1])
        else:
            self.assertTrue(observed[0][1])
        self.assertEqual(observed[0][0], mode not in {"inactive", "frozen"})
        if mode not in {"task_done", "exception"}: self.assertLessEqual(strategy.spec.exit_deadline_ns, 100_150_000_000)
        if mode == "task_done": self.assertEqual(len(observed), 2)
        if mode == "boundary":
            self.assertEqual(len(observed), 4)
            self.assertFalse(observed[2][1])
        if mode == "flat": self.assertEqual(len(observed), 3)
        if mode in {"flat_pending", "flat_unresolved"}: self.assertGreater(len(observed), 3)
        if mode in {"pending", "unresolved", "inactive", "flat_pending", "flat_unresolved"}:
            # Inactive/pending/unresolved engines cannot run periodic reconciliation.
            self.assertEqual(recon.call_count, 1 if mode == "inactive" else 0)
            port.mark_reconciled.assert_not_called()
        elif mode == "before_interval":
            self.assertEqual(recon.call_count, 1)
            port.mark_reconciled.assert_not_called()
        elif mode == "no_fresh": port.mark_reconciled.assert_not_called()
        elif mode in {"normal", "stale"}: self.assertTrue(port.mark_reconciled.called)
        if forced: self.assertEqual(recon.call_count, 2 if mode == "reconcile_gap" else 1)
        if mode == "mark_fault": self.assertTrue(observed[0][3])
        if mode == "frozen": self.assertEqual(outcome["status"], "needs_attention")
        if mode in {"gap", "reconcile_gap"}:
            self.assertTrue(observed[0][3])
            ledger.freeze.assert_called_with("t22_stream_integrity_gap")
            self.assertEqual(outcome["status"], "needs_attention")


@unittest.skipUnless(importlib.util.find_spec("nautilus_trader"), "requires pinned native runtime")
class NativeDispatch(unittest.TestCase):
    def test_each_family_entry_admission_check_is_independently_effective(self):
        from types import SimpleNamespace
        families = importlib.import_module("blueprints.us-equities.strategies.families")
        contracts = importlib.import_module("blueprints.us-equities.strategies.contracts")
        presets = importlib.import_module("blueprints.us-equities.strategies.presets")
        from nautilus_trader.model import OrderSide, InstrumentId
        spec = contracts.StrategySpec("SPY.ALPACA", "a"*64, preset="aggressive-v1", evidence_class="exploratory")
        entry = SimpleNamespace(allow_entries=False, snapshot=SimpleNamespace(cohort_member=True, valid_until_ns=200),
            spec=spec, preset=presets.PRESETS["aggressive-v1"], FAMILY="gap_premarket", entry_condition=Mock(return_value=True))
        session = SimpleNamespace(kind=SimpleNamespace(name="RTH"))
        self.assertFalse(families.FamilyStrategy._entry_allowed(entry, 100, session))
        entry.entry_condition.assert_not_called()
        entry.allow_entries = True
        self.assertTrue(families.FamilyStrategy._entry_allowed(entry, 100, session))
        submit = SimpleNamespace(allow_entries=False, faulted=False, enabled=True,
            clock=SimpleNamespace(timestamp_ns=lambda: 100), _halt_reason=lambda now: None,
            quantity=Decimal(1), sequence=0, client_id_prefix="t22-fixture-", spec=spec, FAMILY="gap_premarket",
            instrument_id=InstrumentId.from_str("SPY.ALPACA"), cache=SimpleNamespace(instrument=lambda _:SimpleNamespace(price_precision=4)),
            order_factory=SimpleNamespace(limit=Mock(return_value=SimpleNamespace())),
            preset=SimpleNamespace(exit_policy=None), _entry_order_deadline=lambda:200,
            _record=Mock(), submit_order=Mock(), _arm_pending_entry_alert=Mock())
        families.FamilyStrategy._submit(submit, OrderSide.BUY, Decimal(1), Decimal(100), "entry", "fixture")
        submit.submit_order.assert_not_called()
        self.assertEqual(submit.sequence, 0)
        families.FamilyStrategy._submit(submit, OrderSide.SELL, Decimal(1), Decimal(100), "exit", "fixture")
        submit.submit_order.assert_called_once()
        pending = SimpleNamespace(allow_entries=False, faulted=False, enabled=True,
            clock=SimpleNamespace(timestamp_ns=lambda:100), _halt_reason=lambda now:None,
            pending=SimpleNamespace(client_order_id="t22-fixture-1"), pending_role="entry", pending_since_ns=100,
            pending_policy_deadline_ns=None, cancel_requested=False, quantity=Decimal(0),
            spec=SimpleNamespace(entry_timeout_ns=1000, exit_timeout_ns=1000, exit_deadline_ns=None, entry_deadline_ns=None),
            _clear_halt_hold=Mock(), _record=Mock(), cancel_order=Mock())
        families.FamilyStrategy._drive(pending)
        pending.cancel_order.assert_called_once_with("t22-fixture-1")

    def test_post_cutoff_marks_use_fresh_account_quotes_and_stop_admissions(self):
        from types import SimpleNamespace
        safety = importlib.import_module("safety")
        dispatch = importlib.import_module("t22_dispatch")
        with tempfile.TemporaryDirectory(dir="/var/tmp") as temporary:
            path = packet_config(Path(temporary))
            config = json.loads(path.read_text())
            d = dispatch.load_dispatch(config, path)
            now = time.time()
            mark = Mock()
            controller = SimpleNamespace(clock=lambda: now, close=now+3600, stop=False, events=[],
                is_halted=lambda symbol: False,
                quotes={"SPY": safety.Quote("SPY", "100", "100.01", now),
                        "QQQ": safety.Quote("QQQ", "100", "100.01", now-10),
                        "BOUND": safety.Quote("BOUND", "100", "100.01", now-config["quote_max_age_seconds"]),
                        "EARLY": safety.Quote("EARLY", "100", "100.01", now+.25),
                        "FUTR": safety.Quote("FUTR", "100", "100.01", now+.5)},
                ledger=SimpleNamespace(limits=safety.RiskLimits(), mark_to_market=mark))
            strategy = dispatch.build_strategy(d, controller, config, time.time_ns())
            strategy.post_cutoff_fill_sink(strategy, None, 0)
            self.assertEqual([q.symbol for q in mark.call_args.args[0]], ["SPY", "BOUND", "EARLY"])
            self.assertEqual(mark.call_args.args[1], now)
            self.assertTrue(controller.stop)
            self.assertFalse(strategy.enabled)
            strategy.notice_sink("held_halted")
            self.assertEqual(controller.events[-1]["type"], "t22_notice")
            controller.stop = False
            strategy.fault_sink("fixture_callback_fault")
            self.assertEqual(controller.events[-1]["type"], "t22_fault")
            self.assertTrue(controller.stop)

    def test_launch_rechecks_sip_and_local_module_origin(self):
        from types import SimpleNamespace
        dispatch = importlib.import_module("t22_dispatch")
        with tempfile.TemporaryDirectory(dir="/var/tmp") as temporary:
            path = packet_config(Path(temporary))
            config = json.loads(path.read_text())
            d = dispatch.load_dispatch(config, path)
            with self.assertRaisesRegex(ValueError, "^t22_ongoing_halt_channel_requires_sip$"):
                dispatch.build_strategy(d, SimpleNamespace(), config | {"feed": "iex"}, time.time_ns())
            with patch.object(dispatch.importlib, "import_module", return_value=SimpleNamespace(__file__=str(path))):
                with self.assertRaisesRegex(ValueError, "^t22_source_module_outside_expected_root$"):
                    dispatch.local_module("blueprints.us-equities.strategies.families")
    def test_status_validation_and_real_subscription_cache(self):
        from types import SimpleNamespace
        adapter = importlib.import_module("native_adapter")
        from nautilus_trader.model import MarketStatusAction, InstrumentId
        for changes in ({"halted": 1}, {"ts_ns": True}, {"ts_ns": 0}, {"ts_ns": -1}, {"symbol": "QQQ"}):
            session = adapter.NativeSession(SimpleNamespace(), [{"symbol": "SPY"}])
            session.data = SimpleNamespace(clock=SimpleNamespace(timestamp_ns=lambda: 100), _handle_data=lambda row: None)
            session.on_status({"symbol": "SPY", "halted": True, "ts_ns": 90} | changes)
            self.assertEqual(len(session.errors), 1)
            self.assertTrue(session.errors[0].startswith("status_"))
        observed = []
        session = adapter.NativeSession(SimpleNamespace(), [{"symbol": "SPY"}])
        session.data = SimpleNamespace(clock=SimpleNamespace(timestamp_ns=lambda: 100), _handle_data=observed.append)
        session.on_status({"symbol": "SPY", "halted": True, "ts_ns": 90})
        session.on_status({"symbol": "SPY", "halted": False, "ts_ns": 90})
        self.assertEqual(session.statuses["SPY"].action, MarketStatusAction.HALT)
        self.assertEqual(observed, [])
        client = SimpleNamespace(session=session, _handle_data=observed.append)
        command = SimpleNamespace(instrument_id=InstrumentId.from_str("SPY.ALPACA"))
        asyncio.run(adapter.AlpacaDataClient._subscribe_instrument_status(client, command))
        self.assertEqual([s.action for s in observed], [MarketStatusAction.HALT])
        session.on_status({"symbol": "SPY", "halted": False, "ts_ns": 91})
        self.assertEqual([s.action for s in observed], [MarketStatusAction.HALT, MarketStatusAction.TRADING])
        with self.assertRaisesRegex(ValueError, "^unknown_instrument$"):
            asyncio.run(adapter.AlpacaDataClient._subscribe_instrument_status(client,
                SimpleNamespace(instrument_id=InstrumentId.from_str("QQQ.ALPACA"))))
        now = [100]
        rollback = adapter.NativeSession(SimpleNamespace(), [{"symbol": "SPY"}])
        rollback.data = SimpleNamespace(clock=SimpleNamespace(timestamp_ns=lambda: now[0]), _handle_data=lambda row: None)
        rollback.on_status({"symbol": "SPY", "halted": True, "ts_ns": 90})
        now[0] = 99
        rollback.on_status({"symbol": "SPY", "halted": False, "ts_ns": 91})
        self.assertEqual(rollback.statuses["SPY"].action, MarketStatusAction.HALT)
        now[0] = 100
        rollback.on_status({"symbol": "SPY", "halted": False, "ts_ns": 100})
        self.assertEqual(rollback.statuses["SPY"].action, MarketStatusAction.TRADING)
    def test_not_ready_admission_gate_still_allows_owned_exit(self):
        self.exercise_dispatch(not_ready=True)

    def test_fault_while_holding_stops_promptly_then_existing_recovery_flattens(self):
        self.exercise_dispatch(fault_after_fill=True)
    def test_short_packet_is_refused_before_node_start(self):
        runner = importlib.import_module("runner")
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory(dir="/var/tmp") as temporary:
            root = Path(temporary)
            config, _, _ = runner.load_config(packet_config(root, until=time.time_ns() + 1_000_000_000))
            with patch("native_adapter.build_node") as node:
                with self.assertRaisesRegex(ValueError, "t22_packet_does_not_cover_stage"):
                    asyncio.run(runner.run_native(SimpleNamespace(), None, [], "fixture", config, "100000"))
                node.assert_not_called()
    def test_subdollar_dispatch_prices_cross_the_quote(self):
        self.exercise_dispatch(penny=True)
    def test_stale_or_future_packet_never_starts_native_dispatch(self):
        import sys
        from types import SimpleNamespace
        from unittest.mock import patch
        source = Path(__file__).resolve().parents[1] / "blueprints/us-equities/adaptive-paper"
        sys.path.insert(0, str(source))
        runner = importlib.import_module("runner")
        dispatch = importlib.import_module("t22_dispatch")
        contracts = importlib.import_module("blueprints.us-equities.strategies.contracts")
        now = time.time_ns()
        for stamp, until in ((now - 10_000_000_000, now - 1),
                             (now + 10_000_000_000, now + 20_000_000_000)):
            snapshot = contracts.FactorSnapshot("SPY.ALPACA", "a" * 64, "b" * 64,
                        stamp, stamp, until, (), evidence_class="exploratory", halted=False)
            config = {"_t22": dispatch.T22Dispatch("momentum_breakout", "conservative-v1",
                        "trial_one", "c" * 64, snapshot)}
            with patch("native_adapter.build_node") as node:
                with self.assertRaisesRegex(ValueError, "t22_factors_unavailable_or_stale"):
                    asyncio.run(runner.run_native(SimpleNamespace(), None, [], "fixture", config, "100000"))
                node.assert_not_called()

    def test_family_dispatch_places_owned_stock_limits_and_exits_flat(self):
        self.exercise_dispatch()

    def test_ranked_mover_family_uses_same_guarded_dispatch(self):
        self.exercise_dispatch(family="gap_premarket", preset="aggressive-v1")

    def test_stop_latch_suppresses_entry_without_clearing_it(self):
        self.exercise_dispatch(stopped=True)

    def test_explicit_halt_suppresses_entry(self):
        self.exercise_dispatch(halted=True)

    def test_stream_integrity_gap_suppresses_entry(self):
        self.exercise_dispatch(gap=True)

    def test_durable_startup_freeze_remains_needs_attention_when_flat(self):
        self.exercise_dispatch(frozen=True)

    def exercise_dispatch(self, *, stopped=False, halted=False, gap=False, frozen=False, penny=False,
                          not_ready=False, fault_after_fill=False,
                          family="momentum_breakout", preset="conservative-v1"):
        from tests.adaptive_paper_hermetic import patch_default_stop, restore_default_stop
        from tests.test_us_equities_strategies import synthetic_rth_context
        source = Path(__file__).resolve().parents[1] / "blueprints/us-equities/adaptive-paper"
        import sys
        sys.path.insert(0, str(source))
        runner = importlib.import_module("runner")
        safety = importlib.import_module("safety")
        dispatch = importlib.import_module("t22_dispatch")
        contracts = importlib.import_module("blueprints.us-equities.strategies.contracts")
        simulation = importlib.import_module("simulation")
        token = patch_default_stop()
        self.addCleanup(restore_default_stop, token)
        if stopped:
            safety.DEFAULT_STOP.write_text("fixture stop\n")
        with tempfile.TemporaryDirectory(dir="/var/tmp") as root:
            limits = safety.RiskLimits(max_order_qty=Decimal(1))
            ledger = safety.Ledger(Path(root) / "ledger.db", limits)
            self.addCleanup(ledger.close)
            ledger.start_trial(time.time())
            if frozen:
                ledger.freeze("fixture_integrity_fault")
            controller = runner.Controller(ledger, time.time() + 3600, market_open=True)
            captured = []
            adapter = importlib.import_module("native_adapter")
            build_node = adapter.build_node
            def capture(*args, **kwargs):
                captured.extend(args[2])
                return build_node(*args, **kwargs)
            class PennyPort(simulation.SimulatedPort):
                async def start(self, on_quote, on_order):
                    self.on_quote, self.on_order = on_quote, on_order
                    self.started += 1
                    self.ready = True
                    async def feed():
                        while self.ready:
                            await simulation.invoke(on_quote, {"symbol": "SPY", "bid": "0.1234", "ask": "0.1235",
                                "bid_size": "1000", "ask_size": "1000", "ts_ns": time.time_ns()})
                            await asyncio.sleep(.02)
                    self.task = asyncio.create_task(feed())

                async def submit(self, order):
                    if order["side"] == "buy":
                        self.test.assertGreaterEqual(Decimal(order["limit_price"]), Decimal("0.1235"))
                    else:
                        self.test.assertLessEqual(Decimal(order["limit_price"]), Decimal("0.1234"))
                    return await super().submit(order)

            class AdmissionPort(simulation.SimulatedPort):
                async def start(self, on_quote, on_order):
                    await super().start(on_quote, on_order)
                    # A quote stream remains live even while entry admission
                    # is paused; SimulatedPort's default loop couples these.
                    self.task.cancel()
                    await asyncio.gather(self.task, return_exceptions=True)
                    self.feed_active = True
                    async def feed():
                        while self.feed_active:
                            row = {"symbol": "SPY", "bid": "99.99", "ask": "100.01", "bid_size": "1000",
                                   "ask_size": "1000", "ts_ns": time.time_ns()}
                            controller.quote(row)
                            await simulation.invoke(on_quote, row)
                            await asyncio.sleep(.02)
                    self.task = asyncio.create_task(feed())

                async def submit(self, order):
                    answer = await super().submit(order)
                    if order["side"] == "buy":
                        if not_ready:
                            self.ready = False
                            self.health["reasons"] = ["quote_stale"]
                        if fault_after_fill:
                            async def fault():
                                await asyncio.sleep(.1)
                                captured[0]._freeze("fixture_callback_fault")
                            self.fault_task = asyncio.create_task(fault())
                    return answer

                async def stop(self):
                    self.feed_active = False
                    self.ready = True  # Permit the fixture's standard teardown.
                    await super().stop()

            port_class = PennyPort if penny else AdmissionPort if not_ready or fault_after_fill else simulation.SimulatedPort
            port = port_class(controller, ("SPY",))
            if penny:
                port.test = self
            if gap:
                port.health["reasons"] = ["stream_integrity_gap"]
            controller.port = port
            stamp = time.time_ns()
            snapshot = contracts.FactorSnapshot("SPY.ALPACA", "a" * 64, "b" * 64,
                stamp - 301_000_000_000, stamp - 301_000_000_000, stamp + 600_000_000_000,
                tuple(sorted({"momentum_20": "0.03", "range_breakout": "1.02",
                              "tight_range_state": "0.02", "atr_price": "0.002" if penny else "0.2",
                              "overnight_gap": "0.05", "premarket_return": "0.02",
                              "premarket_activity": "2",
                              "entry_trigger": "0.1235" if penny else "100"}.items())), evidence_class="exploratory", halted=halted)
            config = json.loads((source / "config.json").read_text())
            config.update(duration_seconds=2, cleanup_seconds=3, symbols=["SPY"],
                          benchmarks=["SPY"], max_held_symbols=1, feed="sip")
            config["_t22"] = dispatch.T22Dispatch(family, preset, "trial_one", "c" * 64, snapshot)
            if fault_after_fill:
                config.update(duration_seconds=20, cleanup_seconds=5, order_timeout_seconds=1)
            with dispatch_rth_context():
                async def run():
                    with patch.object(adapter, "build_node", side_effect=capture):
                        result = await asyncio.wait_for(runner.run_native(controller, None,
                            [{"symbol": "SPY"}], "t22-fixture", config, "100000"), 8)
                    if fault_after_fill:
                        self.assertLess(result["elapsed_seconds"], 5)
                        self.assertFalse(result["flat"], result)
                        fresh = simulation.SimulatedPort(controller, ("SPY",))
                        fresh.positions, fresh.cash = dict(port.positions), port.cash
                        fresh.orders, fresh.executions = dict(port.orders), dict(port.executions)
                        fresh.adopt_intents = lambda intents: None  # All prior intents terminal.
                        controller.port = controller.bind(fresh)
                        recovery = importlib.import_module("recovery")
                        fixed = await recovery.recover(controller, {"trial_id": "t22-fixture", "baseline_cash": "100000"}, config)
                        self.assertTrue(fixed["flat"], fixed)
                    return result
                result = asyncio.run(run())
            self.assertEqual(result["paper_lane"], "B")
            self.assertEqual(result["evidence_class"], "exploratory")
            self.assertEqual(result["t22"]["family"], family)
            self.assertEqual(result["adapter_errors"], ["fixture_callback_fault"] if fault_after_fill else
                             ["startup_ledger_halted_requires_reconciliation"] if frozen or gap else [], result)
            self.assertEqual(result["callback_faults"], [], result)
            self.assertEqual(result["flat"], not fault_after_fill, result)
            self.assertEqual([i.side for i in ledger.intents()], [] if stopped or halted or gap or frozen else ["buy", "sell"], result)
            self.assertEqual(result["native_fill_events"], 0 if stopped or halted or gap or frozen else 1 if fault_after_fill else 2, result)
            if not stopped and not halted and not gap and not frozen:
                self.assertTrue(all("family=" + family in order["tags"] for order in port.orders.values()), result)
            if result["reconciliation"] is not None:
                self.assertTrue(result["reconciliation"]["positions_match"])
                self.assertTrue(result["reconciliation"]["cash_match"])
            if stopped:
                self.assertTrue(safety.DEFAULT_STOP.exists())
            if frozen:
                self.assertEqual(result["status"], "needs_attention", result)
            if gap:
                self.assertEqual(result["status"], "needs_attention", result)
                self.assertEqual(runner.trial_phase_and_exit_code(result), ("needs_attention", 3))

    def test_status_adapter_delivers_explicit_halt_and_resume_without_fabricating_state(self):
        from types import SimpleNamespace
        adapter = importlib.import_module("native_adapter")
        from nautilus_trader.model import MarketStatusAction
        session = adapter.NativeSession(SimpleNamespace(), [{"symbol": "SPY"}])
        observed = []
        session.data = SimpleNamespace(clock=SimpleNamespace(timestamp_ns=lambda: 100),
                                       _handle_data=observed.append)
        session.status_subscriptions.add("SPY")
        session.on_status({"symbol": "SPY", "ts_ns": 90, "halted": None})
        self.assertEqual(observed, [])
        session.on_status({"symbol": "SPY", "ts_ns": 91, "halted": True})
        session.on_status({"symbol": "SPY", "ts_ns": 92, "halted": False})
        self.assertEqual([s.action for s in observed], [MarketStatusAction.HALT, MarketStatusAction.TRADING])
        self.assertEqual([s.ts_event for s in observed], [91, 92])
        self.assertEqual(session.errors, [])
        # Negative status is observed immediately; an earlier/future resume
        # cannot erase it from the subscription startup cache.
        session.on_status({"symbol": "SPY", "ts_ns": 110, "halted": True})
        session.on_status({"symbol": "SPY", "ts_ns": 95, "halted": False})
        session.on_status({"symbol": "SPY", "ts_ns": 120, "halted": False})
        self.assertEqual(session.statuses["SPY"].action, MarketStatusAction.HALT)
        self.assertEqual(len(observed), 3)


@unittest.skipUnless(importlib.util.find_spec("nautilus_trader"), "requires pinned native runtime")
class FinalSubmissionGuards(unittest.TestCase):
    def test_wire_window_shape_bounds_and_owner_timeout_are_protective(self):
        from types import SimpleNamespace
        transport = importlib.import_module("transport")
        order = {"symbol": "SPY", "side": "buy"}
        def wire(window, now):
            result = SimpleNamespace(_quote_values={"SPY":{"ts_ns":now}}, exit_quote_max_age_ns=1000,
                order_quote_max_age_ns=1000, _stopping=False, _started=True, ready=True,
                before_wire=lambda row:window, freeze_health=Mock())
            result._on_owner = Mock(side_effect=lambda callback,row,**kwargs:callback(row))
            return result
        for window, now in [((0,0),0), ((0,100),0), ((0,100),100)]:
            with self.subTest(window=window, now=now), patch.object(transport.time,"time_ns",return_value=now):
                transport.AlpacaPaperTransport._wire_guard(wire(window,now),order)
        for window, now in [([0,100],0), ((0,100,200),0), ((False,100),0), ((-1,100),0), ((1,100),0), ((0,100),101)]:
            with self.subTest(window=window, now=now), patch.object(transport.time,"time_ns",return_value=now):
                with self.assertRaises(transport.SubmissionNotSent):
                    transport.AlpacaPaperTransport._wire_guard(wire(window,now),order)
        timed = wire((0,100),0)
        timed._on_owner.side_effect = TimeoutError("fixture callback timeout")
        with patch.object(transport.time,"time_ns",return_value=0), self.assertRaises(transport.SubmissionNotSent):
            transport.AlpacaPaperTransport._wire_guard(timed,order)
        self.assertEqual(timed._on_owner.call_args.kwargs, {"_owner_timeout":.25,"_freeze_timeout":False})
        timed.freeze_health.assert_not_called()

    def test_transport_constructor_keeps_its_selected_policy_callback(self):
        transport = importlib.import_module("transport")
        callback = lambda row:(0,100)
        wire = transport.AlpacaPaperTransport("fixture-key","fixture-secret",["SPY"],
            before_request=lambda *a,**kw:None, before_submit=lambda row:None,
            sink_observation=lambda row:None, before_wire=callback)
        self.assertIs(wire.before_wire,callback)
        self.addCleanup(wire._client._session._session.close)

    def test_window_is_rechecked_after_owner_callback(self):
        from types import SimpleNamespace
        transport = importlib.import_module("transport")
        now = [100]
        wire = SimpleNamespace(_quote_values={"SPY": {"ts_ns": 100}},
            exit_quote_max_age_ns=3_000_000_000, order_quote_max_age_ns=3_000_000_000,
            _stopping=False, _started=True, ready=True, before_wire=lambda order: (1, 200))
        def owner(callback, order, **kwargs):
            window = callback(order)
            now[0] = 201  # Eligibility expires while the callback reply returns.
            wire._quote_values["SPY"]["ts_ns"] = 201
            return window
        wire._on_owner = owner
        with patch.object(transport.time, "time_ns", side_effect=lambda: now[0]):
            with self.assertRaises(transport.SubmissionNotSent):
                transport.AlpacaPaperTransport._wire_guard(wire, {"symbol": "SPY", "side": "buy"})

    def test_delayed_controller_seed_prevents_timed_sell(self):
        outcome, ledger, sent, before_resume = self.exercise("seed")
        self.assertEqual([row["side"] for row in sent], ["buy"], outcome)
        self.assertTrue(all(not row["controller_halted"] for row in sent), sent)
        self.assertFalse(outcome["flat"])
        self.assertEqual(ledger["positions"], 1)

    def test_explicit_resume_clears_seed_without_thawing_frozen_family(self):
        # A fault now ends the native session immediately. Exercise resume on
        # the controller/family boundary without waiting inside a stopped run.
        runner = importlib.import_module("runner")
        safety = importlib.import_module("safety")
        dispatch = importlib.import_module("t22_dispatch")
        with tempfile.TemporaryDirectory(dir="/var/tmp") as temporary:
            root = Path(temporary)
            config, limits, _ = runner.load_config(packet_config(root))
            with contextlib.closing(safety.Ledger(root / "ledger.db", limits)) as ledger:
                controller = runner.Controller(ledger, time.time() + 3600, market_open=True)
                strategy = dispatch.build_strategy(config["_t22"], controller, config, time.time_ns())
                stamp = time.time_ns()
                controller.apply_halt_seed({"source": "fixture_halt_source", "halts": {
                    "SPY": {"halted_at_ns": stamp, "reason_code": "T1"}}})
                self.assertIsNotNone(strategy._halt_reason(stamp))
                adapter = importlib.import_module("native_adapter")
                simulation = importlib.import_module("simulation")
                session = adapter.build_node(simulation.SimulatedPort(controller, ("SPY",)),
                    [{"symbol": "SPY"}], [strategy])
                self.addCleanup(session.node.dispose)
                strategy._freeze("fixture_seed_halt")
                controller.trading_status({"symbol": "SPY", "ts_ns": stamp + 1, "halted": False})
                self.assertFalse(controller.is_halted("SPY"))
                self.assertTrue(strategy.faulted)

    def test_entry_delayed_across_packet_expiry_never_reaches_final_send(self):
        outcome, ledger, sent, before_resume = self.exercise("expiry")
        self.assertEqual(sent, [], outcome)
        self.assertEqual(ledger["positions"], 0, outcome)
        self.assertEqual(ledger["unresolved"], 0, outcome)

    def test_expiry_after_risk_and_budget_still_prevents_final_send(self):
        outcome, ledger, sent, before_resume = self.exercise("expiry_budget")
        self.assertEqual(sent, [], outcome)
        self.assertEqual(ledger["positions"], 0, outcome)
        self.assertEqual(ledger["unresolved"], 0, outcome)

    def exercise(self, kind):
        from tests.adaptive_paper_hermetic import patch_default_stop, restore_default_stop
        from tests.test_us_equities_strategies import synthetic_rth_context
        from types import SimpleNamespace
        runner = importlib.import_module("runner")
        safety = importlib.import_module("safety")
        dispatch = importlib.import_module("t22_dispatch")
        transport = importlib.import_module("transport")
        simulation = importlib.import_module("simulation")
        token = patch_default_stop()
        self.addCleanup(restore_default_stop, token)
        sent, before_resume = [], []
        with tempfile.TemporaryDirectory(dir="/var/tmp") as temporary:
            root = Path(temporary)
            path = packet_config(root, until=time.time_ns() + (7_000_000_000 if kind.startswith("expiry") else 600_000_000_000))
            config, limits, policy = runner.load_config(path)
            config.update(duration_seconds=3, cleanup_seconds=3)
            expiry = config["_t22"].snapshot.valid_until_ns
            ledger = safety.Ledger(root / "ledger.db", limits)
            self.addCleanup(ledger.close)
            ledger.start_trial(time.time())
            controller = runner.Controller(ledger, time.time() + 3600, market_open=True)

            class WirePort(simulation.SimulatedPort):
                async def start(self, on_quote, on_order):
                    self.loop = asyncio.get_running_loop()
                    self.operation = asyncio.Lock()
                    self.raw_quotes = {}
                    async def quote(row):
                        self.raw_quotes[row["symbol"]] = row
                        await simulation.invoke(on_quote, row)
                    await super().start(quote, on_order)

                async def submit(self, payload):
                    async with self.operation:
                        self.selected = payload
                        if kind == "expiry" and payload["side"] == "buy":
                            await asyncio.sleep(max(0, (expiry - time.time_ns()) / 1e9) + .15)
                        answer = await super().submit(payload)
                        if payload["side"] == "buy" and kind in {"seed", "resume"}:
                            controller.apply_halt_seed({"source": "fixture_halt_source", "halts": {
                                "SPY": {"halted_at_ns": time.time_ns(), "reason_code": "T1"}}})
                            if kind == "resume":
                                async def resume():
                                    await asyncio.sleep(3.1)
                                    before_resume.append(len([r for r in sent if r["side"] == "sell"]))
                                    await self.sink_status({"symbol": "SPY", "ts_ns": time.time_ns(), "halted": False})
                                self.resume_task = asyncio.create_task(resume())
                        return answer

                async def final_wire(self):
                        payload = self.selected
                        wire = SimpleNamespace(_quote_values=self.raw_quotes,
                            exit_quote_max_age_ns=3_000_000_000, order_quote_max_age_ns=3_000_000_000,
                            _stopping=False, _started=True, ready=True, _loop=self.loop,
                            before_wire=getattr(self, "before_wire", None),
                            freeze_health=lambda reason: self.loop.call_soon_threadsafe(self.freeze_health, reason))
                        wire._invoke = lambda callback, *a, **kw: transport.AlpacaPaperTransport._invoke(wire, callback, *a, **kw)
                        wire._on_owner = lambda callback, *a, **kw: transport.AlpacaPaperTransport._on_owner(wire, callback, *a, **kw)
                        await asyncio.to_thread(transport.AlpacaPaperTransport._wire_guard, wire, payload)
                        sent.append({"side": payload["side"], "controller_halted": controller.is_halted("SPY")})

                async def cancel(self, client_id):
                    async with self.operation:
                        if client_id not in self.orders:
                            raise transport.SubmissionNotSent("fixture order was not sent")
                        return await super().cancel(client_id)

                async def stop(self):
                    await super().stop()
                    task = getattr(self, "resume_task", None)
                    if task is not None and not task.done():
                        task.cancel()
                        await asyncio.gather(task, return_exceptions=True)

            port = WirePort(controller, ("SPY",))
            before_request = controller.before_request
            async def budget_then_wire(kind_name, client_id=None):
                await before_request(kind_name, client_id=client_id)
                if kind_name == "submit":
                    if kind == "expiry_budget":
                        # The SDK worker re-checks after the owner callback.
                        # Advance only its guard clock; avoid extending this
                        # fixture past the bounded cleanup cancellation window.
                        with patch.object(transport.time, "time_ns", return_value=expiry + 1):
                            await port.final_wire()
                    else:
                        await port.final_wire()
            controller.before_request = budget_then_wire
            port.sink_status = controller.trading_status
            controller.port = controller.bind(port)
            with dispatch_rth_context():
                result = asyncio.run(asyncio.wait_for(runner.run_native(controller, policy,
                    [{"symbol": "SPY"}], "guard-fixture", config, "100000"), 15))
            summary = {"positions": len(ledger.positions()), "unresolved": len(ledger.unresolved()),
                       "halted_now": controller.is_halted("SPY")}
        return result, summary, sent, before_resume[0] if before_resume else None
