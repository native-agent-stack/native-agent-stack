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
import secrets
import hmac
from contextlib import contextmanager

SOURCE = Path(__file__).resolve().parent
LABEL = {"paper_lane": "B", "evidence_class": "exploratory"}
CANONICAL_STATE = Path.home() / ".local/state/native-agent-stack/alpaca-paper/exploratory"
ACCOUNT_ROOT = Path.home() / ".local/state/native-agent-stack/alpaca-paper"


def safe_path(path):
    path = Path(path).absolute()
    if ".." in path.parts:
        raise Refused("unsafe_artifact_path")
    for item in [*reversed(path.parents), path]:
        if item.is_symlink():
            raise Refused("symlink_path")
    return path


def bundle_destination(path):
    path = safe_path(path)
    account_root = ACCOUNT_ROOT
    qualification = SOURCE.parents[2] / "evidence"
    if path.is_relative_to(account_root) or path.is_relative_to(qualification):
        raise Refused("protected_bundle_destination")
    return path


def read_bytes(path, limit=1048576):
    path = safe_path(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
            raise Refused("unsafe_input_file")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            data = stream.read(limit + 1)
        if len(data) > limit:
            raise Refused("input_too_large")
        return data
    finally:
        os.close(fd)


def read_json(path):
    return json.loads(read_bytes(path))


def read_private_json(path):
    path = safe_path(path)
    info = path.lstat()
    if info.st_uid != os.getuid() or not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
        raise Refused("unsafe_private_runtime_file")
    return read_json(path)


def seal_inventory(root):
    root = safe_path(root)
    files = sorted(p for p in root.rglob("*") if p.is_file() and p != root / "SHA256SUMS")
    if any(p.is_symlink() for p in root.rglob("*")):
        raise Refused("bundle_symlink")
    (root / "SHA256SUMS").write_text("".join(digest(p) + "  " + str(p.relative_to(root)) + "\n" for p in files))
    return files


def stop_path():
    from safety import DEFAULT_STOP
    # The canonical root makes this the native global account latch. Tests
    # substitute the native default along with the isolated canonical root.
    return safe_path(DEFAULT_STOP)


class Refused(ValueError):
    """A fixed reason code suitable for a labelled refusal receipt."""


def digest(path):
    return hashlib.sha256(read_bytes(path, 64 * 1024 * 1024)).hexdigest()


def save(path, value):
    path = safe_path(path)
    missing = []
    parent = path.parent
    while not parent.exists():
        missing.append(parent)
        parent = parent.parent
    for directory in reversed(missing):
        directory.mkdir(mode=0o700)
    temporary = path.with_name(path.name + "." + secrets.token_hex(8) + ".tmp")
    descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w") as stream:
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
def exclusive(path, *, wait_seconds=0):
    path = safe_path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid():
            raise Refused("unsafe_writer_lock")
        deadline = time.monotonic() + wait_seconds
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise Refused("writer_busy") from None
                time.sleep(min(0.05, max(0, deadline - time.monotonic())))
        yield
        if path.stat().st_ino != st.st_ino or path.stat().st_dev != st.st_dev:
            raise Refused("writer_lock_replaced")
    finally:
        os.close(fd)


def lane_a_absent():
    patterns = ["paper-pre-*.service", "paper-ext-*.service", "paper-n2-open-*.service",
                "paper-n2-ctl-*.service", "paper-recover-a2-*.service", "paper-rth-*.service",
                "paper-n2-gate-*.service", "paper-n2-wake-*.service", "paper-ready-*.service"]
    result = subprocess.run(["/usr/bin/systemctl", "--user", "list-units", "--all", "--type=service",
                             "--no-legend", "--plain", *patterns], capture_output=True, text=True)
    if result.returncode:
        raise Refused("lane_A_inventory_unavailable")
    for line in result.stdout.splitlines():
        fields = line.split()
        if len(fields) < 4 or fields[2] in ("active", "activating", "deactivating"):
            raise Refused("lane_A_writer_active")
    timers = subprocess.run(["/usr/bin/systemctl", "--user", "list-units", "--all", "--type=timer",
                             "--no-legend", "--plain", "paper-pre-*", "paper-ext-*", "paper-rth-*",
                             "paper-n2-*"], capture_output=True, text=True)
    if timers.returncode:
        raise Refused("lane_A_inventory_unavailable")
    for line in timers.stdout.splitlines():
        fields = line.split()
        if len(fields) < 4 or fields[2] in ("activating", "deactivating") or (
                fields[2] == "active" and fields[3] != "elapsed"):
            raise Refused("lane_A_timer_pending")
    engine = Path.home() / ".local/state/native-agent-stack/alpaca-paper/engines"
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


def resolved_config(path, kind):
    if kind == "mover":
        from mover import load_mover_config
        return load_mover_config(path)
    from runner import load_config
    return load_static_config(load_config, path)


def load_static_config(loader, path):
    """Use the reviewed caller's config-only seam when it is available.

    Old callers have no T22 dispatch. Integrity/recovery must never depend on
    an expiring producer artifact, even when a different stage owns the account.
    """
    import inspect
    if "require_t22_packet" in inspect.signature(loader).parameters:
        return loader(path, require_t22_packet=False)
    return loader(path)


def config_hashes(path, kind):
    config, limits, _ = resolved_config(path, kind)
    raw = read_bytes(path)
    try:
        from exploration import config_digest
    except ImportError:
        effective = hashlib.sha256(raw).hexdigest()
    else:
        effective = config_digest(config, raw, limits=limits)
    return hashlib.sha256(raw).hexdigest(), effective


def validate_sizing_and_scope(config, kind, session):
    if session not in ("RTH", "POST"):
        raise Refused("unsupported_session_kind")
    if config.get("sessions", {}).get("overnight_holds") is not False:
        raise Refused("unsupported_overnight_policy")
    if kind == "adaptive" and ("leverage_policy" in config or float(config["max_leverage"]) > 1
                              or float(config["max_gross_exposure_usd"]) > 5000):
        raise Refused("unregistered_sizing_setting")
    if kind == "mover":
        required = {"capital_usd": "10000", "max_leverage": "4", "max_gross_exposure_usd": "40000",
                    "max_order_notional_usd": "10000", "max_order_quantity": 100,
                    "max_order_qty_mode": "notional", "max_gross_loss_usd": "100",
                    "max_drawdown_usd": "100", "duration_seconds": 1200}
        mover = config["mover"]
        if (any(config.get(k) != v for k, v in required.items())
                or mover.get("max_entry_notional_usd") != "1000" or mover.get("max_symbols") != 5
                or any(row["rung"] != "4" for row in mover["rung_schedule"])):
            raise Refused("unregistered_sizing_setting")
        repository = SOURCE.parents[2]
        import importlib.util
        spec = importlib.util.spec_from_file_location("deployment_scan_rules",
                    repository / "blueprints/us-equities/mover-early-entry/rules.py")
        rules = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(rules)
        if mover["rule"].split("|")[0] not in rules.TIMES:
            raise Refused("producer_rule_unsupported")


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
    if not re.fullmatch(r"[A-Za-z0-9._/-]+", str(path)):
        raise Refused("unsupported_systemd_path")
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
            "StartLimitIntervalSec=300s\nStartLimitBurst=1\n"
            "[Service]\nType=exec\nUMask=0077\nCPUWeight=50\nKillMode=control-group\n"
            "WorkingDirectory=" + bundle + "\n"
            "ExecCondition=/usr/bin/sha256sum --strict --quiet -c SHA256SUMS\n"
            "ExecStart=" + python + " -E -s -B " + source + "/deployment_issue_go.py run" + arguments + "\n"
            "ExecStopPost=" + python + " -E -s -B " + source + "/paper_deployment.py recover" + arguments + "\n"
            "RuntimeMaxSec=" + str(manifest["stages"][stage]["runtime_max_seconds"]) + "s\n"
            "TimeoutStartSec=120s\nTimeoutStopSec=900s\n"
            "UnsetEnvironment=PYTHONPATH PYTHONHOME PYTHONSTARTUP LD_PRELOAD LD_LIBRARY_PATH HTTP_PROXY HTTPS_PROXY ALL_PROXY"
            " NO_PROXY REQUESTS_CA_BUNDLE CURL_CA_BUNDLE SSL_CERT_FILE"
            " pythonpath pythonhome pythonstartup ld_preload ld_library_path http_proxy https_proxy all_proxy"
            " no_proxy requests_ca_bundle curl_ca_bundle ssl_cert_file\n"
            "StandardOutput=journal\nStandardError=journal\n")
        (units / (name + ".path")).write_text(
            "[Unit]\nDescription=Watch lane B exploratory " + stage + "\n[Path]\n"
            "PathExists=" + state + "/deployments/" + manifest["deployment"] + "/ready/" + stage + "/GO.sha256\n"
            "Unit=" + name + ".service\n"
            "[Install]\nWantedBy=default.target\n")


def build(root, *, deployment, order, stage_specs=None):
    """Freeze existing adaptive configs; never modifies the shipped presets."""
    from runner import load_config
    root = bundle_destination(root)
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
        if custom:
            original = read_json(config_source)
            config["max_order_quantity"] = original["max_order_quantity"]
            config["max_order_qty_mode"] = original.get("max_order_qty_mode", "fixed")
        config["notes"] = "Lane B exploratory; native limits; no qualification claim."
        kind = custom["engine_kind"] if custom else ("mover" if "mover" in stage else "adaptive")
        session = custom["session_kind"] if custom else ("POST" if stage.startswith("post") else "RTH")
        if kind not in ("adaptive", "mover", "t22") or session not in ("RTH", "POST"):
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
        validate_sizing_and_scope(config, kind, session)
        raw_hash, effective_hash = config_hashes(path, kind)
        stages[stage] = {**LABEL, "config": str(path.relative_to(root)),
                         "config_file_sha256": raw_hash, "config_sha256": effective_hash,
                         "engine_kind": kind, "session_kind": session,
                         "duration_seconds": 1200,
                         "runtime_max_seconds": 1200 + int(config["cleanup_seconds"]) + 180,
                         "cleanup_bound_seconds": 900,
                         "state_namespace": "exploratory_config:" + effective_hash}
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
    root = bundle_destination(root)
    systemd_path(root)
    if any(stage in {"lev1", "lev2", "lev4", "mover1", "mover2", "mover4", "post1", "postmover1"}
           for stage in order):
        raise Refused("rung_deployment_requires_registered_sizing_preset")
    if root.exists():
        raise Refused("deployment_directory_exists")
    repository = SOURCE.parents[2]
    pin = subprocess.check_output(["/usr/bin/git", "rev-parse", source_pin + "^{commit}"],
                                  cwd=repository, text=True).strip()
    archive = subprocess.run(["/usr/bin/git", "archive", "--format=tar", pin], cwd=repository,
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
    files = seal_inventory(root)
    for path in files:
        path.chmod(path.stat().st_mode & ~0o222)
    (root / "SHA256SUMS").chmod(0o400)
    return {**LABEL, "status": "sealed", "deployment": deployment, "source_commit": pin,
            "bundle_sha256": digest(root / "SHA256SUMS"), "file_count": len(files)}


class Deployment:
    def __init__(self, root, state):
        self.root, self.state = safe_path(root), safe_path(state)
        if self.state != safe_path(CANONICAL_STATE):
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
            if self.stage(stage).get("session_kind") not in ("RTH", "POST"):
                raise Refused("unsupported_session_kind")
            self.config(stage)

    def stage(self, stage):
        if stage not in self.order:
            raise Refused("unknown_stage")
        return self.manifest["stages"][stage]

    def config_path(self, stage):
        relative = self.stage(stage)["config"]
        path = safe_path(self.root / relative)
        if not path.is_relative_to(self.root):
            raise Refused("unsafe_artifact_path")
        if digest(path) != self.stage(stage)["config_file_sha256"]:
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
        result = subprocess.run(["/usr/bin/sha256sum", "--strict", "--quiet", "-c", "SHA256SUMS"],
                                cwd=self.root, capture_output=True, text=True)
        if result.returncode:
            raise Refused("bundle_hash_mismatch")
        if (self.root / "source.json").is_file():
            expected = {line.split("  ", 1)[1] for line in read_bytes(self.root / "SHA256SUMS", 64 * 1024 * 1024).decode().splitlines()}
            actual = {str(path.relative_to(self.root)) for path in self.root.rglob("*")
                      if path.is_file() and path != self.root / "SHA256SUMS"}
            if expected != actual:
                raise Refused("bundle_file_inventory_mismatch")
        if any(self.manifest.get(k) != v for k, v in LABEL.items()):
            raise Refused("exploratory_label_required")
        for stage in self.order:
            config = self.config(stage)
            kind = self.stage(stage)["engine_kind"]
            validate_sizing_and_scope(config, kind, self.stage(stage)["session_kind"])
            raw_hash, effective_hash = config_hashes(self.config_path(stage), kind)
            if (raw_hash != self.stage(stage)["config_file_sha256"]
                    or effective_hash != self.stage(stage)["config_sha256"]):
                raise Refused("effective_config_hash_mismatch")
            if kind == "mover":
                from mover import load_mover_config
                load_mover_config(self.config_path(stage))
            else:
                from runner import load_config
                resolved, _, _ = load_static_config(load_config, self.config_path(stage))
                if kind == "t22":
                    if "_t22" not in resolved:
                        raise Refused("t22_dispatch_not_available")
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
        return safe_path(self.state / "deployments" / self.deployment / "instances" / trial_identifier(trial))

    def native_state(self):
        # Reve's B rotation API keeps a SINGLE persistent account ledger and
        # registers effective-config namespaces inside it. No reset per trial.
        return safe_path(self.state / "account-state")

    def sequence_path(self):
        return safe_path(self.state / "deployments" / self.deployment / "sequence.json")

    def availability(self, stage):
        # A factor's clock gates this stage's admission, never integrity checks
        # or cleanup of an already owned trial (including another stage).
        if self.stage(stage)["engine_kind"] == "t22":
            from runner import load_config
            import t22_dispatch
            resolved, _, _ = load_config(self.config_path(stage))
            validator = getattr(t22_dispatch, "validate_stage", None)
            if callable(validator):
                validator(resolved["_t22"], resolved, time.time_ns())
            else:
                t22_dispatch.validate_availability(resolved["_t22"], time.time_ns())

    def sequence_next(self, stage, trial, previous, pass_id=None):
        index = self.order.index(stage)
        path = self.sequence_path()
        current = read_json(path) if path.is_file() else None
        if not current or current["next_index"] == len(self.order):
            pass_id = identifier(pass_id or trial)
            history = current.get("passes", []) if current else []
            if pass_id in history:
                raise Refused("pass_already_used")
            current = {"deployment": self.deployment, "pass_id": pass_id, "next_index": 0,
                       "last_trial": None, "pending": None, "passes": history + [pass_id]}
        if (current["pending"] is not None or current["next_index"] != index
                or current["last_trial"] != previous
                or (pass_id is not None and current["pass_id"] != pass_id)):
            raise Refused("sequence_stage_or_trial")
        return current

    def account_window(self, now):
        path = self.state / "account-last.json"
        if path.is_file():
            prior = read_json(path)
            if prior.get("flat") is not True or not 60 <= now - prior["finished_at"]:
                raise Refused("request_window_not_drained")

    def namespace_ready(self, stage, fingerprint):
        from safety import Ledger
        if not re.fullmatch(r"[0-9a-f]{64}", fingerprint):
            raise Refused("invalid_native_account_fingerprint")
        rotation = callable(getattr(Ledger, "register_exploratory_config", None))
        engine = self.stage(stage)["engine_kind"]
        directory = "adaptive" if rotation or engine != "mover" else "mover"
        state_dir = safe_path(self.native_state() / fingerprint / directory)
        path = state_dir / "trial.json"
        if rotation:
            try:
                from exploration import active_trial_metadata
            except ImportError:
                raise Refused("rotation_lineage_api_not_ready") from None
            previous = active_trial_metadata(state_dir)
            if previous is None:
                if path.exists():
                    raise Refused("native_lineage_missing")
                return "new_native_namespace"
            last_path = self.state / "account-last.json"
            if (not last_path.is_file() or previous.get("trial_id", previous.get("trial")) != read_json(last_path).get("trial")
                    or previous.get("engine_kind") not in ("adaptive", "mover")):
                raise Refused("native_lineage_mismatch")
        else:
            if not path.exists():
                return "new_native_namespace"
            if path.is_symlink():
                raise Refused("unsafe_native_state")
            previous = read_json(path)
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
        self.verify()
        now = time.time() if now is None else now
        date = self.session(stage, now)
        config, _, _ = resolved_config(self.config_path(stage), self.stage(stage)["engine_kind"])
        instance = self.instance(trial)
        instance.mkdir(parents=True, exist_ok=True, mode=0o700)
        if (instance / "GO.used.sha256").exists():
            raise Refused("trial_reuse")
        # This read-only worker never issues GO. Its 50/min budget plus every
        # native trial's 150/min ceiling stays within the 200/min account cap.
        with exclusive(self.state / "deployment-writer.lock"):
            if any((self.state / "active").glob("*.json")):
                raise Refused("active_experiment_requires_recovery")
            if (stop_path()).exists() or (stop_path()).is_symlink():
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
                    salt = secrets.token_hex(32)
                    account = {"fingerprint": final["account_identity_sha256"], "salt": salt}
                    save(instance / "account.private.json", account)
                    proof["account_commitment"] = hmac.new(bytes.fromhex(salt),
                        account["fingerprint"].encode(), hashlib.sha256).hexdigest()
                    save(instance / "readiness.json", proof)
                    return proof
            finally:
                ledger.close()

    def slot(self, stage):
        self.stage(stage)
        return safe_path(self.state / "deployments" / self.deployment / "ready" / stage)

    def scan_snapshot(self, stage, snapshot, now):
        """Validate hashes and meaning on the exact bytes retained for dispatch."""
        from mover import load_mover_config, load_scan
        commitment = json.loads(snapshot["commitment.json"])
        spec = self.stage(stage)
        if any(commitment.get(k) != v for k, v in LABEL.items()):
            raise Refused("exploratory_label_required")
        if (commitment.get("config_file_sha256", commitment.get("config_sha256")) != spec["config_file_sha256"]
                or commitment.get("effective_config_sha256", commitment.get("config_sha256")) != spec["config_sha256"]):
            raise Refused("scan_config_binding_mismatch")
        for name, field in [("scan.json", "scan_sha256"), ("ranked-100.json", "ranked_sha256"),
                            ("input.json", "input_sha256")]:
            if hashlib.sha256(snapshot[name]).hexdigest() != commitment.get(field):
                raise Refused("commitment_hash_mismatch")
        if not re.fullmatch(r"[0-9a-f]{64}", commitment.get("code_sha256", "")):
            raise Refused("commitment_code_hash_missing")
        _, _, settings = load_mover_config(self.config_path(stage))
        parsed = load_scan(snapshot["scan.json"], settings, now=now)
        date = self.session(stage, now)
        if parsed.session_date.isoformat() != date or commitment.get("session_date") != date:
            raise Refused("scan_session_mismatch")
        scan = json.loads(snapshot["scan.json"])
        ranked = json.loads(snapshot["ranked-100.json"])
        inputs = json.loads(snapshot["input.json"])
        cutoff = inputs.get("source") or {}
        if cutoff and cutoff.get("mode") != "intraday":
            raise Refused("unsupported_source_cutoff_mode")
        original_clock = cutoff.get("signal_cutoff_utc")
        if original_clock is None:
            # A plain native scan evaluates the frozen rule cutoff, even when
            # its producer captured it later. Acquisition cannot restamp data.
            from sessions import NY
            day = parsed.session_date.isoformat()
            rule_time = settings.rule.text.split("|")[0]
            original_clock = day + "T" + ("09:28" if rule_time == "09:30" else rule_time) + ":00"
            data_at = datetime.fromisoformat(original_clock).replace(tzinfo=NY).timestamp()
        else:
            moment = datetime.fromisoformat(original_clock.replace("Z", "+00:00"))
            if moment.tzinfo is None:
                raise Refused("input_observation_clock_missing")
            data_at = moment.timestamp()
        observed = datetime.fromisoformat(commitment["observed_at"].replace("Z", "+00:00"))
        acquired = datetime.fromisoformat(commitment["source_observed_at"].replace("Z", "+00:00"))
        source_clock = cutoff.get("observed_at", commitment["source_observed_at"])
        source_at = datetime.fromisoformat(source_clock.replace("Z", "+00:00"))
        if (observed.tzinfo is None or acquired.tzinfo is None or observed.timestamp() != data_at
                or source_at.tzinfo is None or source_at.timestamp() != acquired.timestamp()
                or not data_at <= parsed.scan_time or not data_at <= acquired.timestamp() <= now + 0.25):
            raise Refused("input_observation_clock_mismatch")
        if not 0 <= now - data_at <= settings.max_scan_age_seconds:
            raise Refused("input_data_stale")
        rows = ranked.get("symbols")
        if (not isinstance(rows, list) or len(rows) > 100
                or rows[:len(scan["symbols"])] != scan["symbols"]):
            raise Refused("ranked_top_scan_mismatch")
        return {**LABEL, "schema_version": 1, "deployment": self.deployment, "stage": stage,
                "session_date": date, "config_file_sha256": spec["config_file_sha256"],
                "config_sha256": spec["config_sha256"],
                "engine_scan_sha256": commitment["scan_sha256"],
                "commitment_sha256": hashlib.sha256(snapshot["commitment.json"]).hexdigest(),
                "observed_at": commitment["observed_at"], "source_observed_at": acquired.isoformat(),
                "ranked_sha256": commitment["ranked_sha256"], "input_sha256": commitment["input_sha256"]}

    def publish_scan(self, stage, packet, *, now=None):
        self.verify()
        now = time.time() if now is None else now
        if self.stage(stage)["engine_kind"] != "mover":
            raise Refused("scan_requires_mover_stage")
        names = ["scan.json", "ranked-100.json", "input.json", "commitment.json"]
        snapshot = {name: read_bytes(Path(packet) / name) for name in names}
        ready = self.scan_snapshot(stage, snapshot, now)
        with exclusive(self.state / "deployment-writer.lock"):
            slot = self.slot(stage)
            if (slot / "GO.sha256").exists() or any((self.state / "active").glob("*.json")):
                raise Refused("scan_already_bound_or_active")
            retained = safe_path(self.state / "inputs" / ready["commitment_sha256"])
            retained.mkdir(parents=True, exist_ok=True, mode=0o700)
            for name, body in snapshot.items():
                dest = safe_path(retained / name)
                if dest.exists() and read_bytes(dest) != body:
                    raise Refused("immutable_input_collision")
                if not dest.exists():
                    with dest.open("xb") as stream:
                        stream.write(body); stream.flush(); os.fsync(stream.fileno())
            save(slot / "SCAN-READY.json", ready)
        return ready

    def scan_binding(self, stage, now, *, return_bytes=False):
        if self.stage(stage)["engine_kind"] != "mover":
            return (None, None) if return_bytes else None
        ready = read_json(self.slot(stage) / "SCAN-READY.json")
        commitment_hash = ready["commitment_sha256"]
        if not re.fullmatch(r"[0-9a-f]{64}", commitment_hash):
            raise Refused("unsafe_commitment_hash")
        retained = safe_path(self.state / "inputs" / commitment_hash)
        snapshot = {name: read_bytes(retained / name) for name in
                    ["scan.json", "ranked-100.json", "input.json", "commitment.json"]}
        checked = self.scan_snapshot(stage, snapshot, now)
        if checked != ready:
            raise Refused("scan_ready_binding_mismatch")
        return (ready, snapshot["scan.json"]) if return_bytes else ready

    def session(self, stage, now):
        from sessions import session_at
        observed = session_at(datetime.fromtimestamp(now, timezone.utc))
        spec = self.stage(stage)
        if observed.kind.value != spec["session_kind"]:
            raise Refused("venue_session_not_ready")
        if observed.seconds_to_close is None or observed.seconds_to_close < (
                spec["runtime_max_seconds"] + 2 * spec["cleanup_bound_seconds"]):
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
        private = read_private_json(self.instance(trial) / "account.private.json")
        commitment = hmac.new(bytes.fromhex(private["salt"]), private["fingerprint"].encode(), hashlib.sha256).hexdigest()
        if proof.get("account_commitment") != commitment:
            raise Refused("readiness_account_binding_mismatch")
        return digest(path)

    def previous(self, stage, previous, now):
        index = self.order.index(stage)
        if not index:
            if previous is not None:
                raise Refused("unexpected_previous_handoff")
            self.account_window(now)
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

    def issue(self, stage, trial, *, previous, now=None, check_only=False, pass_id=None):
        trial_identifier(trial)
        self.verify()
        now = time.time() if now is None else now
        with exclusive(self.state / "deployment-writer.lock"):
            stop = stop_path()
            if stop.exists() or stop.is_symlink():
                raise Refused("STOP_present")
            if (self.state / "ISSUER-HOLD").exists():
                raise Refused("issuer_hold")
            if any((self.state / "active").glob("*.json")):
                raise Refused("active_experiment_requires_recovery")
            lane_a_absent()
            date = self.session(stage, now)
            self.availability(stage)
            sequence = self.sequence_next(stage, trial, previous, pass_id)
            prior = self.previous(stage, previous, now)
            readiness = self.readiness(stage, trial, now)
            scan = self.scan_binding(stage, now)
            slot = self.slot(stage)
            if (slot / "GO.sha256").exists() or (self.instance(trial) / "GO.used.sha256").exists():
                raise Refused("GO_pending_or_used")
            value = {**LABEL, "schema_version": 1, "deployment": self.deployment,
                     "stage": stage, "trial": trial, "bundle_sha256": self.bundle_hash(),
                     "pass_id": sequence["pass_id"],
                     "config_sha256": self.stage(stage)["config_sha256"],
                     "session_kind": self.stage(stage)["session_kind"], "session_date": date,
                     "issued_at": now, "readiness_sha256": readiness,
                     "account_commitment": json.loads((self.instance(trial) / "readiness.json").read_text())["account_commitment"],
                     "previous_trial": previous, "previous_handoff_sha256": prior,
                     "scan_binding": scan,
                     "order_sha256": hashlib.sha256(json.dumps(self.order).encode()).hexdigest()}
            if check_only:
                return {**LABEL, "status": "ready", "binding": value}
            save(slot / "GO.json", value)
            save(self.instance(trial) / "issue.json", {**value, "status": "GO_issued",
                                                      "go_sha256": digest(slot / "GO.json")})
            sequence["pending"] = trial
            save(self.sequence_path(), sequence)
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
        secret = secrets.token_hex(32)
        capability = {**LABEL, "deployment": self.deployment, "stage": stage, "trial": trial,
                      "bundle_sha256": self.bundle_hash(), "config_sha256": self.stage(stage)["config_sha256"],
                      "mode": mode, "issued_at": time.time(), "token_sha256": hashlib.sha256(secret.encode()).hexdigest()}
        active = json.loads(self.active_path(trial).read_text())
        if (active.get("stage") != stage or active.get("trial") != trial
                or active.get("bundle_sha256") != self.bundle_hash()
                or active.get("config_sha256") != self.stage(stage)["config_sha256"]):
            raise Refused("native_active_binding_mismatch")
        capability["active_sha256"] = digest(self.active_path(trial))
        capability["account_commitment"] = active.get("account_commitment")
        path = self.instance(trial) / ("launch-" + mode + ".json")
        save(path, capability)
        argv = ["/usr/bin/python3", "-I", "-B", str(credential_run), "alpaca-paper", "--",
                sys.executable, "-E", "-s", "-B", str(SOURCE / "paper_deployment.py"),
                "native", "--bundle", str(self.root), "--state", str(self.state),
                "--stage", stage, "--trial", trial, "--native-mode", mode, "--launch-fd", "0"]
        # No command line, credential pointer, provider exception or native
        # output reaches the agent's console/journal. Fixed result only.
        bound = self.stage(stage)["runtime_max_seconds"] - 10 if mode == "paper" else 840
        # The credential runner forwards stdin unchanged (Popen stdin=None).
        # Extra descriptors close at that boundary, so the random private
        # capability crosses only the inherited stdin pipe, never argv/env.
        result = subprocess.run(argv, input=secret.encode(), stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, timeout=bound)
        return result.returncode

    def consume_capability(self, mode, stage, trial, descriptor):
        if descriptor is None:
            raise Refused("native_launch_capability_missing")
        secret = os.read(descriptor, 128)
        os.close(descriptor)
        path = self.instance(trial) / ("launch-" + mode + ".json")
        capability = read_private_json(path)
        active_path = self.active_path(trial)
        active = json.loads(active_path.read_text())
        if (active.get("stage") != stage or active.get("trial") != trial
                or active.get("bundle_sha256") != self.bundle_hash()
                or active.get("config_sha256") != self.stage(stage)["config_sha256"]):
            raise Refused("native_active_binding_mismatch")
        expected = {**LABEL, "deployment": self.deployment, "stage": stage, "trial": trial,
                    "mode": mode, "bundle_sha256": self.bundle_hash(),
                    "config_sha256": self.stage(stage)["config_sha256"],
                    "active_sha256": digest(active_path), "account_commitment": active.get("account_commitment")}
        if (any(capability.get(k) != v for k, v in expected.items())
                or hashlib.sha256(secret).hexdigest() != capability["token_sha256"]
                or not 0 <= time.time() - capability["issued_at"] < 30):
            raise Refused("native_launch_capability_mismatch")
        if mode == "paper":
            used = self.instance(trial) / "GO.used.sha256"
            if not used.is_file() or (self.instance(trial) / "paper.json").exists():
                raise Refused("native_launch_not_single_use")
            if used.read_text().strip() != digest(self.slot(stage) / "GO.json"):
                raise Refused("native_consumed_GO_mismatch")
            if (stop_path()).exists() or (self.state / "ISSUER-HOLD").exists():
                raise Refused("native_control_latch")
            self.session(stage, time.time())
            lane_a_absent()
        path.rename(path.with_name(path.name + ".consumed." + str(time.time_ns())))
        return active

    def check_account(self, stage, trial, observation, *, recovering=False):
        account = read_private_json(self.instance(trial) / "account.private.json")
        active = json.loads(self.active_path(trial).read_text())
        actual = observation.get("account_identity_sha256")
        commitment = hmac.new(bytes.fromhex(account["salt"]), str(actual).encode(), hashlib.sha256).hexdigest()
        if actual != account["fingerprint"] or commitment != active.get("account_commitment"):
            raise Refused("native_account_binding_mismatch")
        with account_writer(actual):
            if not recovering:
                self.namespace_ready(stage, actual)
        return observation

    def engine_arguments(self, mode, stage, trial, pointer):
        kind = self.stage(stage)["engine_kind"]
        module = "mover_runner.py" if kind == "mover" else "runner.py"
        output = self.instance(trial) / (mode + ".json")
        argv = [module, mode, "--env-file", str(pointer), "--config", str(self.config_path(stage)),
                "--state-root", str(self.native_state()), "--output", str(output)]
        if kind != "mover" or mode == "paper":
            argv += ["--trial", trial]
        if kind == "mover" and mode == "paper":
            argv += ["--scan", str(self.instance(trial) / "scan.json")]
        return argv

    def native_child(self, mode, stage, trial, *, launch_fd=None):
        """Runtime child called ONLY by credential_run, never an agent probe."""
        active = self.consume_capability(mode, stage, trial, launch_fd)
        import contextlib
        import sys
        import runner
        import transport
        original_preflight = transport.preflight
        def checked_preflight(*args, **kwargs):
            return self.check_account(stage, trial, original_preflight(*args, **kwargs), recovering=mode != "paper")
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
                value = checked_preflight(os.environ["APCA_API_KEY_ID"], os.environ["APCA_API_SECRET_KEY"],
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
        argv = self.engine_arguments(mode, stage, trial, pointer)
        original_save = native_module.save
        def labelled_save(path, value):
            original_save(path, public_result(value) if Path(path) == output else value)
        native_module.save = labelled_save
        transport.preflight = checked_preflight
        old_argv = sys.argv
        try:
            sys.argv = argv
            with open(os.devnull, "w") as quiet, contextlib.redirect_stdout(quiet), contextlib.redirect_stderr(quiet):
                try:
                    return native_module.main()
                except Exception as exc:
                    from safety import SafetyError
                    reason = str(exc) if isinstance(exc, SafetyError) and str(exc) == "no_owned_trial_to_recover" else type(exc).__name__
                    save(output, {**LABEL, "status": "refused", "reason": reason,
                                  "orders_submitted": 0})
                    return 2
        finally:
            transport.preflight = original_preflight
            native_module.save = original_save
            sys.argv = old_argv

    def active_path(self, trial):
        return safe_path(self.state / "active" / (identifier(trial) + ".json"))

    def run(self, stage, *, now=None):
        try:
            return self.run_bound(stage, now=now)
        except Exception as exc:
            slot = self.slot(stage)
            if (slot / "GO.sha256").is_file():
                stamp = str(time.time_ns())
                (slot / "GO.sha256").rename(slot / ("GO.refused." + stamp + ".sha256"))
                save(slot / ("refusal." + stamp + ".json"), {**LABEL, "status": "refused",
                     "deployment": self.deployment, "stage": stage,
                     "reason": str(exc) if isinstance(exc, Refused) else type(exc).__name__, "orders_dispatched": 0})
            raise

    def run_bound(self, stage, *, now=None):
        self.verify()
        now = time.time() if now is None else now
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
                stop = stop_path()
                if stop.exists() or stop.is_symlink():
                    raise Refused("STOP_present")
                if (self.state / "ISSUER-HOLD").exists():
                    raise Refused("issuer_hold")
                lane_a_absent()
                self.availability(stage)
                sequence = read_json(self.sequence_path())
                if (sequence.get("pending") != trial or sequence.get("pass_id") != go.get("pass_id")
                        or sequence.get("next_index") != self.order.index(stage)):
                    raise Refused("sequence_active_binding")
                if self.readiness(stage, trial, now) != go["readiness_sha256"]:
                    raise Refused("readiness_hash_mismatch")
                if self.previous(stage, go["previous_trial"], now) != go["previous_handoff_sha256"]:
                    raise Refused("previous_handoff_binding")
                scan, scan_bytes = self.scan_binding(stage, now, return_bytes=True)
                if scan != go.get("scan_binding"):
                    raise Refused("scan_binding_changed")
                if scan:
                    source = self.state / "inputs" / scan["commitment_sha256"] / "scan.json"
                    target = self.instance(trial) / "scan.json"
                    with target.open("xb") as stream:
                        stream.write(scan_bytes); stream.flush(); os.fsync(stream.fileno())
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
        stop = stop_path()
        prior = self.instance(trial) / "stop-hook.json"
        if prior.is_file() and stop.exists():
            hook = json.loads(prior.read_text())
            st = stop.lstat()
            if hook.get("identity") == [st.st_dev, st.st_ino, st.st_mtime_ns, st.st_ctime_ns]:
                return
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
        clock_offset = 0 if now is None else now - time.time()
        self.verify()
        self.stop_mark(trial)
        with exclusive(self.state / "deployment-writer.lock", wait_seconds=30):
            active = self.active_path(trial)
            if not active.exists():
                return 0
            go = json.loads(active.read_text())
            stage = go["stage"]
            if go["bundle_sha256"] != self.bundle_hash() or go["config_sha256"] != self.stage(stage)["config_sha256"]:
                raise Refused("recovery_config_binding_mismatch")
            sequence_path = self.sequence_path()
            sequence = read_json(sequence_path) if sequence_path.is_file() else None
            if sequence is not None and sequence.get("pending") != trial:
                raise Refused("sequence_recovery_binding")
            output = self.instance(trial) / "recover.json"
            rc = self.native_call("recover", stage, trial, output)
            if not output.is_file():
                save(self.instance(trial) / "recovery-refusal.json", {**LABEL, "status": "refused",
                     "reason": "native_recovery_output_missing", "recover_rc": rc})
                raise Refused("native_recovery_output_missing")
            if output.is_file():
                value = json.loads(output.read_text())
                if rc in (2, 3) and value.get("reason") == "no_owned_trial_to_recover":
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
                       "finished_at": time.time() + clock_offset, "stop_cleared": False,
                       "paper_outcome_sha256": digest(self.instance(trial) / "paper.json") if (self.instance(trial) / "paper.json").is_file() else None}
            save(self.instance(trial) / "recover-validation.json", receipt)
            if flat:
                stop = stop_path()
                st = stop.lstat()
                hook = json.loads((self.instance(trial) / "stop-hook.json").read_text())
                if hook["created_by_hook"] and hook["identity"] == [st.st_dev, st.st_ino, st.st_mtime_ns, st.st_ctime_ns]:
                    stop.unlink()
                    receipt["stop_cleared"] = True
                save(self.instance(trial) / "handoff.json", receipt)
                if sequence is not None:
                    sequence.update(pending=None, next_index=sequence["next_index"] + 1, last_trial=trial)
                    receipt["pass_id"] = sequence["pass_id"]
                    save(self.instance(trial) / "handoff.json", receipt)
                    save(sequence_path, sequence)
                save(self.state / "account-last.json", {**LABEL, "deployment": self.deployment,
                     "trial": trial, "flat": True, "finished_at": receipt["finished_at"],
                     "handoff_sha256": digest(self.instance(trial) / "handoff.json")})
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
    parser.add_argument("--pass-id")
    parser.add_argument("--input-packet", type=Path)
    parser.add_argument("--native-mode", choices=["paper", "recover", "flat"])
    parser.add_argument("--launch-fd", type=int)
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
                result = plan.issue(args.stage, args.trial, previous=args.previous,
                                    check_only=args.command == "check", pass_id=args.pass_id)
            elif args.command == "observe":
                result = plan.observe(args.stage, args.trial)
            elif args.command == "publish-scan":
                result = plan.publish_scan(args.stage, args.input_packet)
            elif args.command == "run":
                return plan.run(args.stage)
            elif args.command == "native":
                return plan.native_child(args.native_mode, args.stage, args.trial, launch_fd=args.launch_fd)
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
    try:
        from runtime_lock import runtime_read_lock
        with runtime_read_lock():
            code = main()
    except Exception as exc:
        print(json.dumps({**LABEL, "status": "refused", "reason": type(exc).__name__}))
        code = 2
    raise SystemExit(code)
