"""Opt-in lane B caller for the unchanged T22 equity strategy/guarded node.

Nautilus rc5@1b0a49d2: crates/common/src/python/actor.rs:1453-1456
publishes CustomData to native subscribers; existing native_adapter.build_node
owns execution/risk. No provider, credential, GO or STOP writer lives here.
"""
from dataclasses import dataclass, replace
from decimal import Decimal
import hashlib
import importlib
import json
from pathlib import Path
import re
import sys

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def local_module(name):
    module = importlib.import_module(name)
    expected = REPO_ROOT.joinpath(*name.split(".")).with_suffix(".py")
    if Path(module.__file__).resolve() != expected.resolve():
        raise ValueError("t22_source_module_outside_expected_root")
    return module

contracts = local_module("blueprints.us-equities.strategies.contracts")
FAMILY_INPUTS = {
    "momentum_breakout": ("momentum_20", "range_breakout", "tight_range_state"),
    "gap_premarket": ("overnight_gap", "premarket_return", "premarket_activity"),
}
PRODUCER_REGISTRY = Path(__file__).with_name("t22-producers.json")


def relative_file(parent, text):
    if not isinstance(text, str):
        raise ValueError("t22_relative_json_packet_required")
    path = Path(text)
    if path.is_absolute() or ".." in path.parts or path.suffix != ".json":
        raise ValueError("t22_relative_json_packet_required")
    resolved = (parent / path).resolve()
    if not resolved.is_relative_to(parent):
        raise ValueError("t22_packet_outside_config_directory")
    return resolved


def validate_producer(block, parent, raw_packet, snapshot):
    source = relative_file(parent, block["source_file"]).read_bytes()
    if hashlib.sha256(source).hexdigest() != snapshot.source_sha256:
        raise ValueError("t22_source_hash_mismatch")
    receipt = json.loads(relative_file(parent, block["producer_receipt"]).read_bytes())
    if (not isinstance(receipt, dict) or set(receipt) != {
            "schema_version", "producer", "code_sha256", "source_sha256", "packet_sha256"}
            or type(receipt["schema_version"]) is not int or receipt["schema_version"] != 1):
        raise ValueError("t22_producer_receipt_invalid")
    registry = json.loads(PRODUCER_REGISTRY.read_bytes())
    entry = registry["producers"].get(receipt["producer"])
    if entry is None or receipt["code_sha256"] != entry["code_sha256"]:
        raise ValueError("t22_producer_code_not_reviewed")
    code = REPO_ROOT / entry["code_path"]
    if not code.resolve().is_relative_to(REPO_ROOT) or hashlib.sha256(code.read_bytes()).hexdigest() != entry["code_sha256"]:
        raise ValueError("t22_registered_producer_code_mismatch")
    if receipt["source_sha256"] != snapshot.source_sha256 or receipt["packet_sha256"] != hashlib.sha256(raw_packet).hexdigest():
        raise ValueError("t22_producer_receipt_binding_mismatch")
    producer = importlib.import_module("t22_producer")
    if Path(producer.__file__).resolve() != code.resolve():
        raise ValueError("t22_registered_producer_module_mismatch")
    produced, _ = producer.produce(source)
    if produced != raw_packet:
        raise ValueError("t22_packet_differs_from_deterministic_source")


@dataclass(frozen=True)
class T22Dispatch:
    family: str
    preset: str
    instance_id: str
    factors_sha256: str
    snapshot: contracts.FactorSnapshot | None


def load_dispatch(config, config_path, *, read_packet=True):
    """Freeze one producer-owned factor packet; receipts expose hashes only."""
    block = config["t22"]
    required = {"family", "preset", "instance_id", "cohort_sha256", "factors_file", "factors_sha256",
                "source_file", "producer_receipt"}
    if (not isinstance(block, dict) or set(block) != required
            or config.get("paper_lane") != "B" or config.get("evidence_class") != "exploratory"
            or config.get("feed") != "sip"
            or config.get("sessions", {}).get("overnight_holds", False)
            or config.get("rotation", {}).get("enabled", False)
            or "exploratory_exit_preset" in config
            or type(config.get("max_leverage", "1")) not in (str, int, float)
            or str(config.get("max_leverage", "1")) not in {"1", "1.0"}
            or block["family"] not in FAMILY_INPUTS or block["preset"] not in {"conservative-v1", "aggressive-v1"}
            or not isinstance(block["factors_file"], str)):
        raise ValueError("invalid_t22_exploratory_configuration")
    exit_age = config.get("exit_quote_max_age_seconds", config["quote_max_age_seconds"])
    # The bounded comparison also refuses NaN and either infinity.
    if type(exit_age) not in (int, float) or not 0 < exit_age <= 10:
        raise ValueError("t22_preset_exit_age_exceeds_interim_constraint")
    if not isinstance(block["factors_sha256"], str) or not re.fullmatch("[a-f0-9]{64}", block["factors_sha256"]):
        raise ValueError("t22_factor_hash_required")
    for name in ("source_file", "producer_receipt"):
        # Shape is checked even for recovery, without reading those files.
        value = block[name]
        if not isinstance(value, str) or Path(value).is_absolute() or ".." in Path(value).parts or Path(value).suffix != ".json":
            raise ValueError("t22_relative_json_packet_required")
    relative = Path(block["factors_file"])
    if relative.is_absolute() or ".." in relative.parts or relative.suffix != ".json":
        raise ValueError("t22_relative_json_packet_required")
    if not isinstance(config["symbols"], list) or len(config["symbols"]) != 1:
        raise ValueError("t22_single_instrument_required")
    contracts.StrategySpec(config["symbols"][0] + ".ALPACA", block["cohort_sha256"],
                           preset=block["preset"], instance_id=block["instance_id"],
                           evidence_class="exploratory")
    if not read_packet:
        # Recovery consumes only frozen config/ledger state. Keep the marker
        # so accidentally dispatching this config cannot fall back to baseline.
        return T22Dispatch(block["family"], block["preset"], block["instance_id"],
                           block["factors_sha256"], None)
    parent = Path(config_path).parent.resolve()
    path = parent / relative
    if not path.resolve().is_relative_to(parent):
        raise ValueError("t22_packet_outside_config_directory")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != block["factors_sha256"]:
        raise ValueError("t22_factor_hash_mismatch")
    snapshot = contracts.FactorSnapshot.from_json(json.loads(raw))
    symbol = snapshot.instrument_id.removesuffix(".ALPACA")
    if (snapshot.instrument_id != symbol + ".ALPACA" or config["symbols"] != [symbol]
            or snapshot.evidence_class != "exploratory" or not snapshot.cohort_member
            or snapshot.cohort_sha256 != block["cohort_sha256"]):
        raise ValueError("t22_factor_scope_mismatch")
    for key in ("atr_price", "entry_trigger", *FAMILY_INPUTS[block["family"]]):
        if snapshot.value(key) is None:
            raise ValueError("t22_required_factor_missing")
    if snapshot.value("atr_price") <= 0 or snapshot.value("entry_trigger") <= 0:
        raise ValueError("t22_positive_price_factor_required")
    validate_producer(block, parent, raw, snapshot)
    # Validate identity without manufacturing development qualification.
    contracts.StrategySpec(snapshot.instrument_id, snapshot.cohort_sha256,
                           preset=block["preset"], instance_id=block["instance_id"],
                           evidence_class="exploratory")
    return T22Dispatch(block["family"], block["preset"], block["instance_id"],
                       block["factors_sha256"], snapshot)


def validate_availability(dispatch, now_ns):
    snapshot = dispatch.snapshot
    if snapshot is None:
        raise ValueError("t22_packet_required_for_execution")
    if not snapshot.ts_event <= snapshot.ts_init <= now_ns <= snapshot.valid_until_ns:
        raise ValueError("t22_factors_unavailable_or_stale")


def validate_stage(dispatch, config, now_ns):
    validate_availability(dispatch, now_ns)
    required_until = now_ns + int((config["duration_seconds"] + config["cleanup_seconds"]) * 1e9)
    if dispatch.snapshot.valid_until_ns < required_until:
        raise ValueError("t22_packet_does_not_cover_stage")


def build_strategy(dispatch, controller, config, now_ns):
    """Numbers come from the existing frozen limits/preset and bounded stage."""
    validate_stage(dispatch, config, now_ns)
    if config.get("feed") != "sip":
        raise ValueError("t22_ongoing_halt_channel_requires_sip")
    families = local_module("blueprints.us-equities.strategies.families")
    limits = controller.ledger.limits
    duration = config["duration_seconds"]
    deadline = min(now_ns + int(duration * 1e9), int(controller.close * 1e9))
    spec = contracts.StrategySpec(
        dispatch.snapshot.instrument_id, dispatch.snapshot.cohort_sha256,
        preset=dispatch.preset, instance_id=dispatch.instance_id,
        evidence_class="exploratory", position_cap_usd=str(limits.max_order_notional_usd),
        exit_policy="after-hours-v1" if config.get("sessions", {}).get("extended_hours", False) else "regular-close-v1",
        cash_cap_usd=str(limits.capital_usd), loss_cap_usd=str(limits.max_gross_loss_usd),
        max_quantity=min(100, int(limits.max_order_qty)),
        quote_max_age_ns=min(3_000_000_000, int(config["quote_max_age_seconds"] * 1e9)),
        entry_timeout_ns=int(config["order_timeout_seconds"] * 1e9),
        exit_timeout_ns=int(config["order_timeout_seconds"] * 1e9),
        entry_deadline_ns=deadline, exit_deadline_ns=deadline,
    )

    def fault(reason):
        controller.stop = True
        controller.events.append({"type": "t22_fault", "reason": reason,
                                  "paper_lane": "B", "evidence_class": "exploratory"})

    def notice(reason):
        controller.events.append({"type": "t22_notice", "notice": reason,
                                  "paper_lane": "B", "evidence_class": "exploratory"})

    def post_cutoff(strategy, event, cutoff):
        # Durable execution booking precedes this callback in the shared adapter.
        # Refresh the complete account risk view synchronously and end admissions;
        # bounded exit/recovery remains with the existing account writer.
        now = controller.clock()
        controller.ledger.mark_to_market([q for q in controller.quotes.values()
            if -.25 <= now - q.timestamp <= config["quote_max_age_seconds"]], now)
        controller.stop = True

    strategy = families.FAMILIES[dispatch.family](spec, ledger=controller.ledger,
        fault_sink=fault, notice_sink=notice, post_cutoff_fill_sink=post_cutoff,
        halted=controller.is_halted)
    strategy.enabled = False  # The owner loop admits only after native startup.
    return strategy


async def run(controller, assets, config, baseline_cash, *, account_fingerprint="simulation", log_directory=None):
    import asyncio
    import time
    from native_adapter import build_node
    from nautilus_trader.model import CustomData
    from runner import reconcile, _stream_health, _finalize_status_and_financing, RECONCILE_EVERY_SECONDS
    from sessions import validate_session_policy
    from safety import SafetyError
    families = local_module("blueprints.us-equities.strategies.families")
    dispatch = config["_t22"]
    now_ns = time.time_ns()
    strategy = build_strategy(dispatch, controller, config, now_ns)
    policy = validate_session_policy(config)
    port = controller.port
    start = port.start
    previous_wire_gate = getattr(port, "before_wire", None)

    def policy_gate(order):
        now_ns = time.time_ns()
        if (order.get("symbol") != str(strategy.instrument_id.symbol)
                or not str(order.get("client_order_id", "")).startswith(strategy.client_id_prefix)):
            raise ValueError("t22_selected_packet_identity_mismatch")
        validate_availability(dispatch, now_ns)
        if strategy.snapshot != dispatch.snapshot:
            raise ValueError("t22_selected_packet_identity_mismatch")
        if strategy._halt_reason(now_ns) is not None:
            raise ValueError("t22_halt_state_prevents_submission")
        until = dispatch.snapshot.valid_until_ns
        if order.get("side") == "buy":
            if controller.stop_requested() or strategy.faulted or now_ns >= strategy.spec.entry_deadline_ns:
                raise ValueError("t22_entry_admission_closed")
            until = min(until, strategy.spec.entry_deadline_ns - 1)
        return (dispatch.snapshot.ts_init, until)

    port.before_wire = policy_gate

    async def start_with_quotes(on_quote, on_order):
        def quote(row):
            controller.quote(row)
            on_quote(row)
        return await start(quote, on_order)

    port.start = start_with_quotes
    metadata = [{"symbol": a["symbol"], "price_precision": 4,
                 "price_increment": "0.0001", "lot_size": "1"} for a in assets]
    session = build_node(port, metadata, [strategy], session_policy=policy,
        account_id="ALPACA-PAPER",
        max_order_submit_rate="180/00:01:00", log_directory=log_directory)
    fault_sink = strategy.fault_sink
    def fail_session(reason):
        try:
            fault_sink(reason)
        finally:
            session.fail(reason)
    strategy.fault_sink = fail_session
    prior_status_sink = getattr(port, "sink_status", None)

    async def status_sink(row):
        import inspect
        if prior_status_sink is not None:
            result = prior_status_sink(row)
            if inspect.isawaitable(result):
                await result
        session.on_status(row)

    port.sink_status = status_sink
    task = asyncio.create_task(session.run_async())
    started = time.monotonic()
    published = False
    reconciliation = None
    last_reconciliation = time.monotonic()
    try:
        controller.start_halt_seed(config["symbols"])
        while time.monotonic() - started < config["duration_seconds"] + config["cleanup_seconds"]:
            if task.done():
                # Preserve startup/callback failures; never convert them to flat success.
                await task
                break
            now = time.time()
            active = strategy.is_running()
            force = (controller.stop_requested() or bool(session.errors)
                     or bool(controller.ledger.accounting().halted_reason)
                     or time.monotonic() - started >= config["duration_seconds"]
                     or controller.close - now <= config["cleanup_seconds"])
            health = getattr(port, "health", {})
            if any("stale" not in str(reason) for reason in health.get("reasons", [])):
                controller.stop = True
                controller.ledger.freeze("t22_stream_integrity_gap")
                force = True
            try:
                controller.ledger.mark_to_market([
                    q for q in controller.quotes.values()
                    if -.25 <= now - q.timestamp <= config["quote_max_age_seconds"]], now)
            except SafetyError as error:
                if str(error) != "held_position_mark_stale":
                    controller.stop = True
                    force = True
            if (active and not force and not controller.ledger.unresolved() and strategy.pending is None
                    and time.monotonic() - last_reconciliation >= RECONCILE_EVERY_SECONDS):
                strategy.allow_entries = False
                reconcile(controller.ledger, await port.snapshot(), baseline_cash)
                health = getattr(port, "health", {})
                if any("stale" not in str(reason) for reason in health.get("reasons", [])):
                    controller.stop = True
                    controller.ledger.freeze("t22_stream_integrity_gap")
                    force = True
                elif health.get("fresh_quotes") and hasattr(port, "mark_reconciled"):
                    port.mark_reconciled()
                last_reconciliation = time.monotonic()
            if active and not published:
                validate_stage(dispatch, config, strategy.clock.timestamp_ns())
                kind = families.snapshot_data_type(dispatch.snapshot.instrument_id)
                strategy.publish_data(kind, CustomData(kind, dispatch.snapshot))
                published = True
            if force:
                strategy.spec = replace(strategy.spec,
                    entry_deadline_ns=min(strategy.spec.entry_deadline_ns, int(now * 1e9)),
                    exit_deadline_ns=min(strategy.spec.exit_deadline_ns, int(now * 1e9)))
            strategy.enabled = bool(active and not strategy.faulted)
            strategy.allow_entries = bool(strategy.enabled and port.ready and not force)
            # Session errors already close admissions through force above.
            if controller.halt_seed_pending() or now < controller.defer_until:
                strategy.allow_entries = False
            if force and not controller.ledger.positions() and not controller.ledger.unresolved() and strategy.pending is None:
                break
            await asyncio.sleep(.05)
        strategy.enabled = False
        strategy.allow_entries = False
        controller.stop = True
        if not controller.ledger.unresolved() and strategy.pending is None:
            reconciliation = reconcile(controller.ledger, await port.snapshot(), baseline_cash)
    finally:
        strategy.enabled = False
        strategy.allow_entries = False
        controller.stop = True
        try:
            await controller.stop_halt_seed()
            session.stop()
            try:
                await asyncio.wait_for(task, 20)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
        finally:
            try:
                await port.stop()
            finally:
                port.before_wire = previous_wire_gate
    outcome = {
        "engine": "NautilusTrader LiveNode 2.0.0rc5", "paper_lane": "B", "evidence_class": "exploratory",
        "t22": {"family": dispatch.family, "preset": dispatch.preset, "instance_id": dispatch.instance_id,
                "cohort_sha256": dispatch.snapshot.cohort_sha256, "factors_sha256": dispatch.factors_sha256},
        "native_fill_events": len([r for r in strategy.trace if r["event"] == "fill"]),
        "adapter_errors": list(session.errors), "callback_faults": list(strategy.callback_faults),
        "flags": sorted(strategy.flags), "events": controller.events,
        "trace": strategy.trace, "reconciliation": reconciliation, "startup_reconciliation": session.reconciliation,
        "execution_stats": dict(session.execution_stats), "native_assertions": session.native_assertions(),
        "flat": not controller.ledger.positions() and not controller.ledger.unresolved(),
        "stream_health": _stream_health(port), "requests": controller.requests,
        "elapsed_seconds": time.monotonic() - started,
    }
    _finalize_status_and_financing(reconciliation, session.errors, outcome["native_fill_events"],
        outcome, policy, config, controller.ledger, baseline_cash, time.time())
    if strategy.faulted or controller.ledger.halted_reason() is not None:
        outcome["status"] = "needs_attention"
    return outcome
