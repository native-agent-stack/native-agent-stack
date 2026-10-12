"""Lane B readiness/deployment glue around the existing native paper engine.

No numeric strategy or broker order implementation lives here. Native mechanisms:
runner.py / safety.py at d8f7e205; systemd path/service e846bbad; alpaca-py cc4cb3b7.
Only the co-op issuer calls the GO writer; agent harnesses use synthetic observations.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import os
import stat
import time
import subprocess
import fcntl
from contextlib import contextmanager

SOURCE = Path(__file__).resolve().parent
LABEL = {"paper_lane": "B", "evidence_class": "exploratory"}


class Refused(ValueError):
    """A fixed reason code suitable for a labelled refusal receipt."""


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    import os
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,47}", value):
        raise Refused("invalid_identifier")
    return value


def trial_identifier(value):
    identifier(value)
    if len(value) > 24:
        raise Refused("invalid_native_trial")
    return value


def public_result(value):
    """Publish labelled native outcomes without account ids or private paths."""
    private_keys = {"account_id", "account_identity_sha256", "api_key", "secret_key", "env_file"}
    def clean(item):
        if isinstance(item, dict):
            return {k: clean(v) for k, v in item.items() if k not in private_keys}
        if isinstance(item, list):
            return [clean(v) for v in item]
        if isinstance(item, str) and (item.startswith("/") or str(Path.home()) in item):
            return "<private-path>"
        return item
    return {**clean(value), **LABEL}


@contextmanager
def exclusive(path):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid():
            raise Refused("unsafe_writer_lock")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise Refused("writer_busy") from None
        yield
    finally:
        os.close(fd)


def lane_a_absent():
    patterns = ["paper-pre-*.service", "paper-ext-*.service", "paper-n2-open-*.service",
                "paper-n2-ctl-*.service", "paper-recover-a2-*.service"]
    result = subprocess.run(["systemctl", "--user", "list-units", "--all", "--type=service",
                             "--no-legend", "--plain", *patterns], capture_output=True, text=True)
    if result.returncode:
        raise Refused("lane_A_inventory_unavailable")
    for line in result.stdout.splitlines():
        fields = line.split()
        if len(fields) < 4 or fields[2] in ("active", "activating", "deactivating"):
            raise Refused("lane_A_writer_active")
    engine = (Path.home() / ".local/state/native-agent-stack/alpaca-paper/engines" /
              "dca821cca85dce3647fa7b488d5a23fbe5b85d4a")
    launcher = Path.home() / ".local/state/native-agent-stack/alpaca-paper/trials/series-driver.sh"
    processes = list(Path("/proc").glob("[0-9]*"))
    if not processes:
        raise Refused("lane_A_process_inventory_unavailable")
    for process in processes:
        try:
            args = (process / "cmdline").read_bytes().split(b"\0")
        except (FileNotFoundError, ProcessLookupError):
            continue
        except OSError:
            raise Refused("lane_A_process_inventory_unavailable") from None
        if any(arg.decode(errors="replace") == str(launcher)
               or arg.decode(errors="replace") == str(engine)
               or arg.decode(errors="replace").startswith(str(engine) + "/") for arg in args):
            raise Refused("lane_A_writer_active")
    return True


def native_flat_observation(before_request, *, config=None):
    """Runtime-only native GET through credential_run's injected environment.

    No raw account or credential is persisted. Agent harnesses replace this seam.
    """
    from transport import preflight
    from runner import validate_preflight
    from sessions import validate_session_policy
    probe = dict(config, symbols=list(config["benchmarks"]))
    observation = preflight(os.environ["APCA_API_KEY_ID"], os.environ["APCA_API_SECRET_KEY"],
                            probe["symbols"], feed=probe["feed"], before_request=before_request,
                            include_margin="leverage_policy" in probe)
    if observation.get("open_orders_complete") is not True:
        raise Refused("open_order_inventory_incomplete")
    validate_preflight(observation, probe, require_open=True,
                       session_policy=validate_session_policy(probe))
    return observation


def account_writer(fingerprint):
    from safety import account_lock_fingerprint
    return account_lock_fingerprint(fingerprint)


def verify_managed_runtime():
    runtime = Path.home() / "projects/us-equities-runtime"
    if (not runtime.is_dir() or runtime.stat().st_uid != os.getuid()
            or (runtime / ".venv").is_symlink() or not (runtime / ".venv").is_dir()):
        raise Refused("runtime_ownership_incomplete")
    for name, expected in {".trading-2604-owner": "native-stack-trading-2604-v1",
                           ".trading-2604-complete": "native-stack-trading-2604-no-dvc-r4"}.items():
        path = runtime / name
        if path.is_symlink() or not path.is_file() or path.read_text().strip() != expected:
            raise Refused("runtime_marker_incomplete")
    for name in ["pyproject.toml", "uv.lock"]:
        expected = SOURCE.parent / "runtime-2604/trading-2604-runtime" / name
        if (runtime / name).is_symlink() or digest(runtime / name) != digest(expected):
            raise Refused("runtime_metadata_differs")


def systemd_path(path):
    path = Path(path).resolve()
    if path.is_relative_to(Path.home()):
        return "%h/" + str(path.relative_to(Path.home()))
    return str(path)


def materialize_units(root, manifest):
    root = Path(root)
    bundle = systemd_path(root)
    state = "%h/.local/state/native-agent-stack/alpaca-paper/exploratory"
    python = "%h/projects/us-equities-runtime/.venv/bin/python"
    source = bundle + "/source/blueprints/us-equities/adaptive-paper"
    units = root / "units"
    units.mkdir(parents=True, exist_ok=True, mode=0o700)
    for stage in manifest["order"]:
        identifier(stage)
        name = "paper-b-" + manifest["deployment"] + "-" + stage
        arguments = " --bundle " + bundle + " --state " + state + " --stage " + stage
        (units / (name + ".service")).write_text(
            "[Unit]\nDescription=Lane B exploratory " + stage + "\nOnFailure=paper-alert@%n.service\n"
            "[Service]\nType=exec\nUMask=0077\nCPUWeight=50\nKillMode=control-group\n"
            "WorkingDirectory=" + bundle + "\n"
            "ExecCondition=/usr/bin/sha256sum --strict --quiet -c SHA256SUMS\n"
            "ExecStart=" + python + " -E -s -B " + source + "/deployment_issue_go.py run" + arguments + "\n"
            "ExecStopPost=" + python + " -E -s -B " + source + "/paper_deployment.py recover" + arguments + "\n"
            "RuntimeMaxSec=" + str(manifest["stages"][stage]["runtime_max_seconds"]) + "s\n"
            "TimeoutStartSec=120s\nTimeoutStopSec=900s\n"
            "UnsetEnvironment=PYTHONPATH PYTHONHOME PYTHONSTARTUP LD_PRELOAD LD_LIBRARY_PATH HTTP_PROXY HTTPS_PROXY ALL_PROXY"
            " pythonpath pythonhome pythonstartup ld_preload ld_library_path http_proxy https_proxy all_proxy\n"
            "StandardOutput=journal\nStandardError=journal\n")
        (units / (name + ".path")).write_text(
            "[Unit]\nDescription=Watch lane B exploratory " + stage + "\n[Path]\n"
            "PathExists=" + state + "/deployments/" + manifest["deployment"] + "/ready/" + stage + "/GO.sha256\n"
            "Unit=" + name + ".service\nMakeDirectory=true\nDirectoryMode=0700\n"
            "[Install]\nWantedBy=default.target\n")


def build(root, *, deployment, order, stage_specs=None):
    """Freeze existing adaptive configs; never modifies the shipped presets."""
    from runner import load_config
    root = Path(root)
    deployment = identifier(deployment)
    if not order or len(set(order)) != len(order):
        raise Refused("invalid_stage_order")
    names = {"lev1": "config-leverage-1x.json", "lev2": "config-leverage-2x.json",
             "lev4": "config-leverage-4x.json", "post1": "config-leverage-1x.json",
             "mover1": "config-mover.json", "mover2": "config-mover.json",
             "mover4": "config-mover.json", "postmover1": "config-mover.json",
             "mover-max": "config-mover.json", "postmover-max": "config-mover.json"}
    stages = {}
    stage_specs = stage_specs or {}
    for stage in order:
        custom = stage_specs.get(stage)
        if stage not in names and custom is None:
            raise Refused("unsupported_stage")
        identifier(stage)
        config_source = Path(custom["config"]) if custom else SOURCE / names[stage]
        config = json.loads(config_source.read_text())
        config.update(LABEL, duration_seconds=1200, max_order_quantity=100,
                      max_order_qty_mode="notional", max_api_requests_per_minute=150,
                      max_submit_requests_per_minute=120)
        config["notes"] = "Lane B exploratory; native limits; no qualification claim."
        kind = custom["engine_kind"] if custom else ("mover" if "mover" in stage else "adaptive")
        session = custom["session_kind"] if custom else ("POST" if stage.startswith("post") else "RTH")
        if kind not in ("adaptive", "mover", "t22") or session not in ("PRE", "RTH", "POST"):
            raise Refused("unsupported_stage_kind")
        mover = kind == "mover"
        post = session == "POST"
        if mover and not custom:
            rung = 4 if stage.endswith("-max") else int(stage[-1])
            canonical = json.loads((SOURCE / ("config-leverage-" + str(rung) + "x.json")).read_text())
            config.update(leverage_policy=canonical["leverage_policy"], max_leverage=str(rung),
                          max_gross_exposure_usd=str(10000 * rung), max_order_notional_usd="10000",
                          max_gross_loss_usd=str(25 * rung), max_drawdown_usd=str(25 * rung),
                          cleanup_seconds=120)
            config["mover"].update(rule=("16:05" if post else "10:00") + "|G20|V1000000|any",
                                   session_scope="any_session", trial_end_et="19:55" if post else "15:55",
                                   exit="X3", max_entry_notional_usd="1000",
                                   rung_schedule=[{"from_session": 1, "to_session": 1000, "rung": str(rung)}])
        if stage == "post1":
            config["regular_session_only"] = False
            config["extended_hours_enabled"] = True
            config["sessions"].update(extended_hours=True, overnight_holds=False)
        path = root / "configs" / (stage + ".json")
        if kind == "t22":
            block = config.get("t22")
            if not isinstance(block, dict):
                raise Refused("t22_config_required")
            factors = Path(block["factors_file"])
            if factors.is_absolute() or ".." in factors.parts:
                raise Refused("unsafe_artifact_path")
            origin = config_source.parent / factors
            if origin.is_symlink() or digest(origin) != block["factors_sha256"]:
                raise Refused("factor_hash_mismatch")
            destination = path.parent / factors
            destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            if destination.exists() and destination.read_bytes() != origin.read_bytes():
                raise Refused("factor_input_collision")
            if not destination.exists():
                destination.write_bytes(origin.read_bytes())
        save(path, config)
        if mover:
            from mover import load_mover_config
            load_mover_config(path)
        else:
            resolved, _, _ = load_config(path)
            if kind == "t22" and "_t22" not in resolved:
                raise Refused("t22_dispatch_not_available")
        stages[stage] = {**LABEL, "config": str(path.relative_to(root)),
                         "config_sha256": digest(path),
                         "engine_kind": kind, "session_kind": session,
                         "duration_seconds": 1200,
                         "runtime_max_seconds": 1200 + int(config["cleanup_seconds"]) + 180,
                         "cleanup_bound_seconds": 900,
                         "state_namespace": "exploratory_config:" + digest(path)}
    manifest = {**LABEL, "schema_version": 1, "deployment": deployment,
                "order": order, "stages": stages, "inventory_id": "alpaca-paper",
                "authority": "standing_lane_B_validity"}
    save(root / "deployment.json", manifest)
    materialize_units(root, manifest)
    files = sorted(p for p in (root / "configs").rglob("*") if p.is_file()) + sorted((root / "units").glob("*")) + [root / "deployment.json"]
    (root / "SHA256SUMS").write_text("".join(digest(p) + "  " + str(p.relative_to(root)) + "\n" for p in files))


def cut(root, *, deployment, order, source_pin, stage_spec=None):
    """Use git's supported archive, then freeze source/config/unit bytes."""
    import io
    import tarfile
    root = Path(root)
    if any(stage in {"lev1", "lev2", "lev4", "mover1", "mover2", "mover4", "post1", "postmover1"}
           for stage in order):
        raise Refused("rung_deployment_requires_registered_sizing_preset")
    if root.exists():
        raise Refused("deployment_directory_exists")
    repository = SOURCE.parents[2]
    pin = subprocess.check_output(["git", "rev-parse", source_pin + "^{commit}"],
                                  cwd=repository, text=True).strip()
    archive = subprocess.run(["git", "archive", "--format=tar", pin], cwd=repository,
                             capture_output=True, check=True).stdout
    root.mkdir(parents=True, mode=0o700)
    source = root / "source"
    with tarfile.open(fileobj=io.BytesIO(archive)) as stream:
        if any(not (member.isfile() or member.isdir()) for member in stream.getmembers()):
            raise Refused("source_archive_nonregular_entry")
        stream.extractall(source, filter="data")
    if not (source / "blueprints/us-equities/adaptive-paper/paper_deployment.py").is_file():
        raise Refused("source_pin_has_no_deployment_helper")
    # Build using this pin's own helper and shipped native config validators.
    import sys
    args = [sys.executable, "-E", "-s", "-B",
            str(source / "blueprints/us-equities/adaptive-paper/paper_deployment.py"),
            "build", "--bundle", str(root), "--deployment", deployment, "--order", *order]
    if stage_spec:
        args += ["--stage-spec", str(Path(stage_spec).resolve())]
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode:
        raise Refused("frozen_config_build_refused")
    save(root / "source.json", {**LABEL, "source_commit": pin, "source_kind": "git_archive",
                               "deployment": deployment})
    files = sorted(p for p in root.rglob("*") if p.is_file() and p.name != "SHA256SUMS")
    if any(p.is_symlink() for p in files):
        raise Refused("bundle_symlink")
    (root / "SHA256SUMS").write_text("".join(digest(p) + "  " + str(p.relative_to(root)) + "\n" for p in files))
    for path in files:
        path.chmod(path.stat().st_mode & ~0o222)
    (root / "SHA256SUMS").chmod(0o400)
    return {**LABEL, "status": "sealed", "deployment": deployment, "source_commit": pin,
            "bundle_sha256": digest(root / "SHA256SUMS"), "file_count": len(files)}


class Deployment:
    def __init__(self, root, state):
        self.root, self.state = Path(root), Path(state)
        if "exploratory" not in self.state.parts:
            raise Refused("exploratory_state_root_required")
        self.manifest = json.loads((self.root / "deployment.json").read_text())
        if any(self.manifest.get(k) != v for k, v in LABEL.items()):
            raise Refused("exploratory_label_required")
        self.deployment = identifier(self.manifest["deployment"])
        self.order = self.manifest["order"]
        if not self.order or len(set(self.order)) != len(self.order):
            raise Refused("invalid_stage_order")
        if set(self.order) != set(self.manifest["stages"]):
            raise Refused("stage_inventory_mismatch")
        for stage in self.order:
            identifier(stage)
            if self.stage(stage).get("engine_kind") not in ("adaptive", "mover", "t22"):
                raise Refused("unsupported_engine_kind")
            if self.stage(stage).get("session_kind") not in ("PRE", "RTH", "POST"):
                raise Refused("unsupported_session_kind")
            self.config(stage)

    def stage(self, stage):
        if stage not in self.order:
            raise Refused("unknown_stage")
        return self.manifest["stages"][stage]

    def config_path(self, stage):
        relative = self.stage(stage)["config"]
        if Path(relative).is_absolute() or ".." in Path(relative).parts:
            raise Refused("unsafe_artifact_path")
        path = self.root / relative
        if not path.resolve().is_relative_to(self.root.resolve()) or path.is_symlink():
            raise Refused("unsafe_artifact_path")
        if digest(path) != self.stage(stage)["config_sha256"]:
            raise Refused("config_hash_mismatch")
        return path

    def config(self, stage):
        value = json.loads(self.config_path(stage).read_text())
        if any(value.get(k) != v for k, v in LABEL.items()):
            raise Refused("exploratory_label_required")
        return value

    def bundle_hash(self):
        return digest(self.root / "SHA256SUMS")

    def verify(self):
        result = subprocess.run(["sha256sum", "--strict", "--quiet", "-c", "SHA256SUMS"],
                                cwd=self.root, capture_output=True, text=True)
        if result.returncode:
            raise Refused("bundle_hash_mismatch")
        if any(self.manifest.get(k) != v for k, v in LABEL.items()):
            raise Refused("exploratory_label_required")
        for stage in self.order:
            config = self.config(stage)
            kind = self.stage(stage)["engine_kind"]
            if kind == "mover":
                from mover import load_mover_config
                load_mover_config(self.config_path(stage))
            else:
                from runner import load_config
                resolved, _, _ = load_config(self.config_path(stage))
                if kind == "t22":
                    if "_t22" not in resolved:
                        raise Refused("t22_dispatch_not_available")
                    from t22_dispatch import validate_availability
                    validate_availability(resolved["_t22"], time.time_ns())
                elif "_t22" in resolved:
                    raise Refused("t22_engine_kind_required")
            if (config["max_api_requests_per_minute"] > 150
                    or config["max_submit_requests_per_minute"] > 120):
                raise Refused("deployment_request_budget_exceeded")
            spec = self.stage(stage)
            if (spec["duration_seconds"] != config["duration_seconds"]
                    or spec["runtime_max_seconds"] < config["duration_seconds"] + config["cleanup_seconds"]
                    or spec["cleanup_bound_seconds"] != 900
                    or spec["state_namespace"] != "exploratory_config:" + spec["config_sha256"]):
                raise Refused("stage_runtime_or_namespace_mismatch")

    def instance(self, trial):
        return self.state / "deployments" / self.deployment / "instances" / trial_identifier(trial)

    def native_state(self):
        # Reve's B rotation API keeps a SINGLE persistent account ledger and
        # registers effective-config namespaces inside it. No reset per trial.
        return self.state / "account-state"

    def namespace_ready(self, stage, fingerprint):
        from safety import Ledger
        if not re.fullmatch(r"[0-9a-f]{64}", fingerprint):
            raise Refused("invalid_native_account_fingerprint")
        rotation = callable(getattr(Ledger, "register_exploratory_config", None))
        engine = self.stage(stage)["engine_kind"]
        directory = "adaptive" if rotation or engine != "mover" else "mover"
        path = self.native_state() / fingerprint / directory / "trial.json"
        if not path.exists():
            return "new_native_namespace"
        if path.is_symlink():
            raise Refused("unsafe_native_state")
        previous = json.loads(path.read_text())
        if previous.get("phase") != "finished":
            raise Refused("existing_native_trial_requires_recovery")
        if rotation and any(previous.get(k) != v for k, v in LABEL.items()):
            raise Refused("native_state_label_required")
        if previous.get("config_sha256") != self.stage(stage)["config_sha256"]:
            if not rotation:
                raise Refused("rotation_source_not_ready")
            return "native_rotation_supported"
        return "matching_native_namespace"

    def observe(self, stage, trial, *, now=None):
        from safety import Ledger, RiskLimits
        provided_now = now
        now = time.time() if now is None else now
        self.verify()
        date = self.session(stage, now)
        config = self.config(stage)
        instance = self.instance(trial)
        instance.mkdir(parents=True, exist_ok=True, mode=0o700)
        if (instance / "GO.used.sha256").exists():
            raise Refused("trial_reuse")
        # This read-only worker never issues GO. Its 50/min budget plus every
        # native trial's 150/min ceiling stays within the 200/min account cap.
        with exclusive(self.state / "deployment-writer.lock"):
            if any((self.state / "active").glob("*.json")):
                raise Refused("active_experiment_requires_recovery")
            if (self.state.parent / "STOP").exists() or (self.state.parent / "STOP").is_symlink():
                raise Refused("STOP_present")
            lane_a_absent()
            if (self.slot(stage) / "GO.sha256").exists() or (instance / "issue.json").exists():
                raise Refused("readiness_already_bound")
            old_proof = instance / "readiness.json"
            if old_proof.exists():
                old_proof.rename(instance / ("readiness.superseded." + str(time.time_ns()) + ".json"))
            ledger = Ledger(self.state / "readiness-budget.sqlite3",
                            RiskLimits(max_rest_per_minute=50, max_submits_per_minute=20))
            count = 0
            def budget(kind, **_):
                nonlocal count
                if ledger.request_budget(time.time(), "read"):
                    raise Refused("readiness_request_budget")
                count += 1
            try:
                initial = native_flat_observation(budget, config=config)
                with account_writer(initial["account_identity_sha256"]):
                    namespace = self.namespace_ready(stage, initial["account_identity_sha256"])
                    final = native_flat_observation(budget, config=config)
                    if initial["account_identity_sha256"] != final["account_identity_sha256"]:
                        raise Refused("account_changed_during_readiness")
                    if (final["positions"] or final["orders"]
                            or final.get("open_orders_complete") is not True):
                        raise Refused("account_not_flat")
                    proof = {**LABEL, "status": "ready", "deployment": self.deployment,
                             "stage": stage, "trial": trial, "bundle_sha256": self.bundle_hash(),
                             "config_sha256": self.stage(stage)["config_sha256"],
                             "observed_at": provided_now if provided_now is not None else time.time(),
                             "session_kind": self.stage(stage)["session_kind"], "session_date": date,
                             "flat": True, "positions": [], "open_orders": [], "request_count": count,
                             "native_preflight": True, "writer_lock_checked": True}
                    proof["native_namespace_status"] = namespace
                    save(instance / "readiness.json", proof)
                    return proof
            finally:
                ledger.close()

    def slot(self, stage):
        self.stage(stage)
        return self.state / "deployments" / self.deployment / "ready" / stage

    def publish_scan(self, stage, packet, *, now=None):
        from mover import load_mover_config, load_scan
        now = time.time() if now is None else now
        packet = Path(packet)
        self.verify()
        if self.stage(stage)["engine_kind"] != "mover":
            raise Refused("scan_requires_mover_stage")
        date = self.session(stage, now)
        commitment = json.loads((packet / "commitment.json").read_text())
        if any(commitment.get(k) != v for k, v in LABEL.items()):
            raise Refused("exploratory_label_required")
        if commitment.get("config_sha256") != self.stage(stage)["config_sha256"]:
            raise Refused("scan_config_binding_mismatch")
        for name, field in [("scan.json", "scan_sha256"), ("ranked-100.json", "ranked_sha256"),
                            ("input.json", "input_sha256")]:
            if (packet / name).is_symlink() or digest(packet / name) != commitment.get(field):
                raise Refused("commitment_hash_mismatch")
        if not re.fullmatch(r"[0-9a-f]{64}", commitment.get("code_sha256", "")):
            raise Refused("commitment_code_hash_missing")
        _, _, settings = load_mover_config(self.config_path(stage))
        parsed = load_scan((packet / "scan.json").read_bytes(), settings, now=now)
        if parsed.session_date.isoformat() != date or commitment.get("session_date") != date:
            raise Refused("scan_session_mismatch")
        observed = datetime.fromisoformat(commitment["observed_at"].replace("Z", "+00:00"))
        if observed.tzinfo is None or observed.timestamp() != parsed.scan_time:
            raise Refused("scan_observation_clock_mismatch")
        scan = json.loads((packet / "scan.json").read_text())
        ranked = json.loads((packet / "ranked-100.json").read_text())
        inputs = json.loads((packet / "input.json").read_text())
        original_clock = inputs.get("scan_time", inputs.get("observed_at"))
        if not isinstance(original_clock, str):
            raise Refused("input_observation_clock_missing")
        original = datetime.fromisoformat(original_clock.replace("Z", "+00:00"))
        if original.tzinfo is None or original.timestamp() != parsed.scan_time:
            raise Refused("input_observation_clock_mismatch")
        rows = ranked.get("symbols")
        if not isinstance(rows, list) or len(rows) > 100 or rows[:len(scan["symbols"])] != scan["symbols"]:
            raise Refused("ranked_top_scan_mismatch")
        ready = {**LABEL, "schema_version": 1, "deployment": self.deployment, "stage": stage,
                 "session_date": date, "config_sha256": self.stage(stage)["config_sha256"],
                 "engine_scan_sha256": digest(packet / "scan.json"),
                 "commitment_sha256": digest(packet / "commitment.json"), "observed_at": commitment["observed_at"],
                 "ranked_sha256": commitment["ranked_sha256"], "input_sha256": commitment["input_sha256"]}
        with exclusive(self.state / "deployment-writer.lock"):
            slot = self.slot(stage)
            if (slot / "GO.sha256").exists() or any((self.state / "active").glob("*.json")):
                raise Refused("scan_already_bound_or_active")
            slot.mkdir(parents=True, exist_ok=True, mode=0o700)
            # Content-addressed retention avoids losing the prior scan during
            # repeated passes. Readiness references exactly these bytes.
            retained = self.state / "inputs" / ready["commitment_sha256"]
            retained.mkdir(parents=True, exist_ok=True, mode=0o700)
            for name in ["scan.json", "ranked-100.json", "input.json", "commitment.json"]:
                body = (packet / name).read_bytes()
                dest = retained / name
                if dest.exists() and dest.read_bytes() != body:
                    raise Refused("immutable_input_collision")
                if not dest.exists():
                    with dest.open("xb") as stream:
                        stream.write(body); stream.flush(); os.fsync(stream.fileno())
            save(slot / "SCAN-READY.json", ready)
        return ready

    def scan_binding(self, stage, now):
        if self.stage(stage)["engine_kind"] != "mover":
            return None
        from mover import load_mover_config, load_scan
        ready = json.loads((self.slot(stage) / "SCAN-READY.json").read_text())
        expected = {**LABEL, "deployment": self.deployment, "stage": stage,
                    "config_sha256": self.stage(stage)["config_sha256"],
                    "session_date": self.session(stage, now)}
        if any(ready.get(k) != v for k, v in expected.items()):
            raise Refused("scan_ready_binding_mismatch")
        commitment_hash = ready["commitment_sha256"]
        if not re.fullmatch(r"[0-9a-f]{64}", commitment_hash):
            raise Refused("unsafe_commitment_hash")
        retained = self.state / "inputs" / commitment_hash
        if digest(retained / "commitment.json") != commitment_hash:
            raise Refused("commitment_hash_mismatch")
        for name, field in [("scan.json", "engine_scan_sha256"), ("ranked-100.json", "ranked_sha256"),
                            ("input.json", "input_sha256")]:
            if digest(retained / name) != ready[field]:
                raise Refused("scan_input_hash_mismatch")
        _, _, settings = load_mover_config(self.config_path(stage))
        load_scan((retained / "scan.json").read_bytes(), settings, now=now)
        return ready

    def session(self, stage, now):
        from sessions import session_at
        observed = session_at(datetime.fromtimestamp(now, timezone.utc))
        spec = self.stage(stage)
        if observed.kind.value != spec["session_kind"]:
            raise Refused("venue_session_not_ready")
        if observed.seconds_to_close is None or observed.seconds_to_close < (
                spec["runtime_max_seconds"] + spec["cleanup_bound_seconds"]):
            raise Refused("insufficient_session_time")
        return observed.session_date.isoformat()

    def readiness(self, stage, trial, now):
        path = self.instance(trial) / "readiness.json"
        if not path.is_file() or path.is_symlink():
            raise Refused("readiness_missing")
        proof = json.loads(path.read_text())
        wanted = {**LABEL, "status": "ready", "deployment": self.deployment, "stage": stage,
                  "trial": trial, "bundle_sha256": self.bundle_hash(),
                  "config_sha256": self.stage(stage)["config_sha256"],
                  "session_kind": self.stage(stage)["session_kind"],
                  "session_date": self.session(stage, now), "native_preflight": True,
                  "writer_lock_checked": True}
        if any(proof.get(k) != v for k, v in wanted.items()):
            raise Refused("readiness_binding_mismatch")
        if not 0 <= now - proof["observed_at"] <= 30:
            raise Refused("readiness_stale")
        if proof.get("flat") is not True or proof.get("positions") != [] or proof.get("open_orders") != []:
            raise Refused("account_not_flat")
        return digest(path)

    def previous(self, stage, previous, now):
        index = self.order.index(stage)
        if not index:
            if previous is not None:
                raise Refused("unexpected_previous_handoff")
            return None
        if previous is None:
            raise Refused("previous_handoff_required")
        path = self.instance(previous) / "handoff.json"
        if not path.is_file() or path.is_symlink():
            raise Refused("previous_handoff_missing")
        receipt = json.loads(path.read_text())
        expected = {**LABEL, "deployment": self.deployment, "stage": self.order[index - 1],
                    "trial": previous, "recover_rc": 0, "flat": True,
                    "positions": 0, "open_orders": 0, "bundle_sha256": self.bundle_hash(),
                    "config_sha256": self.stage(self.order[index - 1])["config_sha256"]}
        if any(receipt.get(k) != v for k, v in expected.items()):
            raise Refused("previous_handoff_not_flat")
        native = self.instance(previous) / "recover.json"
        if digest(native) != receipt.get("native_recover_sha256"):
            raise Refused("previous_native_recover_hash")
        proof = json.loads(native.read_text())
        if (proof.get("flat") is not True or proof.get("positions") != []
                or proof.get("unresolved_orders") != [] or proof.get("status") != "passed"
                or proof.get("reconciliation", {}).get("positions") != 0
                or proof.get("reconciliation", {}).get("open_orders") != 0):
            raise Refused("previous_handoff_not_flat")
        if not 60 <= now - receipt["finished_at"]:
            raise Refused("request_window_not_drained")
        return digest(path)

    def issue(self, stage, trial, *, previous, now=None, check_only=False):
        now = time.time() if now is None else now
        trial_identifier(trial)
        self.verify()
        with exclusive(self.state / "deployment-writer.lock"):
            stop = self.state.parent / "STOP"
            if stop.exists() or stop.is_symlink():
                raise Refused("STOP_present")
            if (self.state / "ISSUER-HOLD").exists():
                raise Refused("issuer_hold")
            if any((self.state / "active").glob("*.json")):
                raise Refused("active_experiment_requires_recovery")
            lane_a_absent()
            date = self.session(stage, now)
            prior = self.previous(stage, previous, now)
            readiness = self.readiness(stage, trial, now)
            scan = self.scan_binding(stage, now)
            slot = self.slot(stage)
            if (slot / "GO.sha256").exists() or (self.instance(trial) / "GO.used.sha256").exists():
                raise Refused("GO_pending_or_used")
            value = {**LABEL, "schema_version": 1, "deployment": self.deployment,
                     "stage": stage, "trial": trial, "bundle_sha256": self.bundle_hash(),
                     "config_sha256": self.stage(stage)["config_sha256"],
                     "session_kind": self.stage(stage)["session_kind"], "session_date": date,
                     "issued_at": now, "readiness_sha256": readiness,
                     "previous_trial": previous, "previous_handoff_sha256": prior,
                     "scan_binding": scan,
                     "order_sha256": hashlib.sha256(json.dumps(self.order).encode()).hexdigest()}
            if check_only:
                return {**LABEL, "status": "ready", "binding": value}
            save(slot / "GO.json", value)
            save(self.instance(trial) / "issue.json", {**value, "status": "GO_issued",
                                                      "go_sha256": digest(slot / "GO.json")})
            temporary = slot / "GO.sha256.tmp"
            with temporary.open("x") as stream:
                stream.write(digest(slot / "GO.json") + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            temporary.replace(slot / "GO.sha256")
            fd = os.open(slot, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
            return {**LABEL, "status": "GO_issued", "deployment": self.deployment, "stage": stage,
                    "trial": trial, "go_sha256": digest(slot / "GO.json")}

    def native_call(self, mode, stage, trial, output):
        """Invoke the existing CLI only through id-based credential injection."""
        import sys
        repository = SOURCE.parents[2]
        credential_run = repository / "tools/credentials/credential_run.py"
        argv = ["/usr/bin/python3", "-I", "-B", str(credential_run), "alpaca-paper", "--",
                sys.executable, "-E", "-s", "-B", str(SOURCE / "paper_deployment.py"),
                "native", "--bundle", str(self.root), "--state", str(self.state),
                "--stage", stage, "--trial", trial, "--native-mode", mode]
        # No command line, credential pointer, provider exception or native
        # output reaches the agent's console/journal. Fixed result only.
        bound = self.stage(stage)["runtime_max_seconds"] - 10 if mode == "paper" else 840
        result = subprocess.run(argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=bound)
        return result.returncode

    def native_child(self, mode, stage, trial):
        """Runtime child called ONLY by credential_run, never an agent probe."""
        import contextlib
        import sys
        import runner
        output = self.instance(trial) / ("recover.json" if mode == "flat" else mode + ".json")
        if mode == "flat":
            from safety import Ledger, RiskLimits
            ledger = Ledger(self.state / "readiness-budget.sqlite3",
                            RiskLimits(max_rest_per_minute=50, max_submits_per_minute=20))
            def before(kind, **_):
                if ledger.request_budget(time.time(), "read"):
                    raise Refused("readiness_request_budget")
            try:
                from transport import preflight
                cfg = self.config(stage)
                value = preflight(os.environ["APCA_API_KEY_ID"], os.environ["APCA_API_SECRET_KEY"],
                                  cfg["benchmarks"], feed=cfg["feed"], before_request=before)
                flat = not value["positions"] and not value["orders"] and value.get("open_orders_complete") is True
                save(output, {**LABEL, "kind": "native_GET_only_flat_proof",
                              "status": "passed" if flat else "needs_attention", "flat": flat,
                              "positions": [] if flat else [{"observed_count": len(value["positions"])}],
                              "unresolved_orders": [] if flat else [{"observed_count": len(value["orders"])}],
                              "reconciliation": {"positions": len(value["positions"]), "open_orders": len(value["orders"])},
                              "orders_submitted": 0})
                return 0 if flat else 2
            finally:
                ledger.close()
        # Inventory pointer resolution happens exclusively inside the injected
        # runtime child; actual content is read ONLY by runner's native loader.
        repository = SOURCE.parents[2]
        sys.path.insert(0, str(repository / "scripts"))
        import credential_status
        inventory = json.loads((repository / "adoption/credential-inventory.json").read_text())
        entry = next(row for row in inventory["entries"] if row["id"] == "alpaca-paper")
        pointer = credential_status.expand_template(entry["store"]["path_template"], os.environ)
        native_module = runner
        if self.stage(stage)["engine_kind"] == "mover":
            import mover_runner
            native_module = mover_runner
        argv = [native_module.__name__ + ".py", mode, "--env-file", str(pointer), "--config", str(self.config_path(stage)),
                "--trial", trial, "--state-root", str(self.native_state()), "--output", str(output)]
        if native_module.__name__ == "mover_runner" and mode == "paper":
            argv += ["--scan", str(self.instance(trial) / "scan.json")]
        original_save = native_module.save
        def labelled_save(path, value):
            original_save(path, public_result(value) if Path(path) == output else value)
        native_module.save = labelled_save
        old_argv = sys.argv
        try:
            sys.argv = argv
            with open(os.devnull, "w") as quiet, contextlib.redirect_stdout(quiet), contextlib.redirect_stderr(quiet):
                return native_module.main()
        finally:
            native_module.save = original_save
            sys.argv = old_argv

    def active_path(self, trial):
        return self.state / "active" / (identifier(trial) + ".json")

    def run(self, stage, *, now=None):
        now = time.time() if now is None else now
        self.verify()
        with exclusive(self.state / "deployment-writer.lock"):
            slot = self.slot(stage)
            try:
                go = json.loads((slot / "GO.json").read_text())
                token = slot / "GO.sha256"
                if token.is_symlink() or digest(slot / "GO.json") != token.read_text().strip():
                    raise Refused("GO_hash_mismatch")
                trial = identifier(go["trial"])
                required = {**LABEL, "schema_version": 1, "deployment": self.deployment, "stage": stage,
                            "bundle_sha256": self.bundle_hash(), "config_sha256": self.stage(stage)["config_sha256"],
                            "session_kind": self.stage(stage)["session_kind"], "session_date": self.session(stage, now),
                            "order_sha256": hashlib.sha256(json.dumps(self.order).encode()).hexdigest()}
                if any(go.get(k) != v for k, v in required.items()) or not 0 <= now - go["issued_at"] < 300:
                    raise Refused("GO_binding_or_expiry")
                if any((self.state / "active").glob("*.json")):
                    raise Refused("active_experiment_requires_recovery")
                stop = self.state.parent / "STOP"
                if stop.exists() or stop.is_symlink():
                    raise Refused("STOP_present")
                lane_a_absent()
                if self.readiness(stage, trial, now) != go["readiness_sha256"]:
                    raise Refused("readiness_hash_mismatch")
                if self.previous(stage, go["previous_trial"], now) != go["previous_handoff_sha256"]:
                    raise Refused("previous_handoff_binding")
                scan = self.scan_binding(stage, now)
                if scan != go.get("scan_binding"):
                    raise Refused("scan_binding_changed")
                if scan:
                    source = self.state / "inputs" / scan["commitment_sha256"] / "scan.json"
                    target = self.instance(trial) / "scan.json"
                    with target.open("xb") as stream:
                        stream.write(source.read_bytes()); stream.flush(); os.fsync(stream.fileno())
                used = self.instance(trial) / "GO.used.sha256"
                if used.exists():
                    raise Refused("GO_already_used")
                token.replace(used)
                save(self.active_path(trial), go)
                output = self.instance(trial) / "paper.json"
                rc = self.native_call("paper", stage, trial, output)
                if output.is_file():
                    save(output, public_result(json.loads(output.read_text())))
                return rc
            except Exception as exc:
                if (slot / "GO.sha256").is_file():
                    stamp = str(time.time_ns())
                    (slot / "GO.sha256").rename(slot / ("GO.refused." + stamp + ".sha256"))
                    save(slot / ("refusal." + stamp + ".json"),
                         {**LABEL, "status": "refused", "reason": str(exc) if isinstance(exc, Refused) else type(exc).__name__,
                          "deployment": self.deployment, "stage": stage, "orders_dispatched": 0})
                raise

    def stop_mark(self, trial):
        active = self.active_path(trial)
        if not active.is_file():
            return
        stop = self.state.parent / "STOP"
        try:
            fd = os.open(stop, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
            os.close(fd)
            owned = True
        except FileExistsError:
            owned = False
        st = stop.lstat()
        save(self.instance(trial) / "stop-hook.json",
             {**LABEL, "created_by_hook": owned, "identity": [st.st_dev, st.st_ino, st.st_mtime_ns, st.st_ctime_ns]})

    def recover(self, trial, *, now=None):
        now = time.time() if now is None else now
        self.verify()
        with exclusive(self.state / "deployment-writer.lock"):
            active = self.active_path(trial)
            if not active.exists():
                return 0
            go = json.loads(active.read_text())
            stage = go["stage"]
            if go["bundle_sha256"] != self.bundle_hash() or go["config_sha256"] != self.stage(stage)["config_sha256"]:
                raise Refused("recovery_config_binding_mismatch")
            self.stop_mark(trial)
            output = self.instance(trial) / "recover.json"
            rc = self.native_call("recover", stage, trial, output)
            if output.is_file():
                value = json.loads(output.read_text())
                if rc in (2, 3) and value.get("reason") in ("no_owned_trial_to_recover", "no_mover_trial_to_recover"):
                    rc = self.native_call("flat", stage, trial, output)
            value = json.loads(output.read_text())
            save(output, public_result(value))
            value = json.loads(output.read_text())
            proof = value.get("reconciliation") or {}
            flat = (rc == 0 and value.get("status") == "passed" and value.get("flat") is True
                    and value.get("positions") == [] and value.get("unresolved_orders") == []
                    and proof.get("positions") == 0 and proof.get("open_orders") == 0)
            receipt = {**LABEL, "deployment": self.deployment, "stage": stage, "trial": trial,
                       "bundle_sha256": self.bundle_hash(), "config_sha256": self.stage(stage)["config_sha256"],
                       "native_recover_sha256": digest(output), "recover_rc": rc, "flat": flat,
                       "positions": proof.get("positions"), "open_orders": proof.get("open_orders"),
                       "finished_at": now, "stop_cleared": False}
            save(self.instance(trial) / "recover-validation.json", receipt)
            if flat:
                stop = self.state.parent / "STOP"
                st = stop.lstat()
                hook = json.loads((self.instance(trial) / "stop-hook.json").read_text())
                if hook["created_by_hook"] and hook["identity"] == [st.st_dev, st.st_ino, st.st_mtime_ns, st.st_ctime_ns]:
                    stop.unlink()
                    receipt["stop_cleared"] = True
                save(self.instance(trial) / "handoff.json", receipt)
                active.replace(self.instance(trial) / "active.finished.json")
                return 0
            save(self.instance(trial) / "handoff.json", receipt)
            raise Refused("recovery_not_flat")


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["cut", "build", "publish-scan", "observe", "check", "issue", "run", "recover", "native"])
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--state", type=Path)
    parser.add_argument("--deployment")
    parser.add_argument("--source-pin", default="HEAD")
    parser.add_argument("--stage-spec", type=Path)
    parser.add_argument("--order", nargs="+")
    parser.add_argument("--stage")
    parser.add_argument("--trial")
    parser.add_argument("--previous")
    parser.add_argument("--input-packet", type=Path)
    parser.add_argument("--native-mode", choices=["paper", "recover", "flat"])
    args = parser.parse_args()
    try:
        if args.command == "cut":
            result = cut(args.bundle, deployment=args.deployment, order=args.order,
                         source_pin=args.source_pin, stage_spec=args.stage_spec)
        elif args.command == "build":
            specs = None
            if args.stage_spec:
                specs = json.loads(args.stage_spec.read_text())
                for spec in specs.values():
                    spec["config"] = str(args.stage_spec.parent / spec["config"])
            build(args.bundle, deployment=args.deployment, order=args.order, stage_specs=specs)
            result = {**LABEL, "status": "built", "deployment": args.deployment}
        else:
            verify_managed_runtime()
            plan = Deployment(args.bundle, args.state)
            if args.command in ("check", "issue"):
                result = plan.issue(args.stage, args.trial, previous=args.previous, check_only=args.command == "check")
            elif args.command == "observe":
                result = plan.observe(args.stage, args.trial)
            elif args.command == "publish-scan":
                result = plan.publish_scan(args.stage, args.input_packet)
            elif args.command == "run":
                return plan.run(args.stage)
            elif args.command == "native":
                return plan.native_child(args.native_mode, args.stage, args.trial)
            else:
                trials = [args.trial] if args.trial else [
                    p.stem for p in (plan.state / "active").glob("*.json")
                    if json.loads(p.read_text()).get("stage") == args.stage]
                for trial in trials:
                    rc = plan.recover(trial)
                    if rc:
                        return rc
                result = {**LABEL, "status": "recovered", "stage": args.stage}
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception as exc:
        print(json.dumps({**LABEL, "status": "refused",
                          "reason": str(exc) if isinstance(exc, Refused) else type(exc).__name__}))
        return 2


if __name__ == "__main__":
    from runtime_lock import runtime_read_lock
    with runtime_read_lock():
        raise SystemExit(main())
