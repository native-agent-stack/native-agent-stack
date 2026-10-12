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
import math
from pathlib import Path
import re

contracts = importlib.import_module("blueprints.us-equities.strategies.contracts")
FAMILY_INPUTS = {
    "momentum_breakout": ("momentum_20", "range_breakout", "tight_range_state"),
    "gap_premarket": ("overnight_gap", "premarket_return", "premarket_activity"),
}


@dataclass(frozen=True)
class T22Dispatch:
    family: str
    preset: str
    instance_id: str
    factors_sha256: str
    snapshot: contracts.FactorSnapshot


def load_dispatch(config, config_path):
    """Freeze one producer-owned factor packet; receipts expose hashes only."""
    block = config["t22"]
    required = {"family", "preset", "instance_id", "cohort_sha256", "factors_file", "factors_sha256"}
    if (not isinstance(block, dict) or set(block) != required
            or config.get("paper_lane") != "B" or config.get("evidence_class") != "exploratory"
            or config.get("sessions", {}).get("overnight_holds", False)
            or config.get("rotation", {}).get("enabled", False)
            or "exploratory_exit_preset" in config
            or Decimal(str(config.get("max_leverage", "1"))) != 1
            or block["family"] not in FAMILY_INPUTS or block["preset"] not in {"conservative-v1", "aggressive-v1"}
            or not isinstance(block["factors_file"], str)):
        raise ValueError("invalid_t22_exploratory_configuration")
    exit_age = config.get("exit_quote_max_age_seconds", config["quote_max_age_seconds"])
    if type(exit_age) not in (int, float) or not math.isfinite(exit_age) or not 0 < exit_age <= 10:
        raise ValueError("t22_preset_exit_age_exceeds_interim_constraint")
    if not isinstance(block["factors_sha256"], str) or not re.fullmatch("[a-f0-9]{64}", block["factors_sha256"]):
        raise ValueError("t22_factor_hash_required")
    relative = Path(block["factors_file"])
    if relative.is_absolute() or ".." in relative.parts or relative.suffix != ".json":
        raise ValueError("t22_relative_json_packet_required")
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
    # Validate identity without manufacturing development qualification.
    contracts.StrategySpec(snapshot.instrument_id, snapshot.cohort_sha256,
                           preset=block["preset"], instance_id=block["instance_id"],
                           evidence_class="exploratory")
    return T22Dispatch(block["family"], block["preset"], block["instance_id"],
                       block["factors_sha256"], snapshot)


def validate_availability(dispatch, now_ns):
    snapshot = dispatch.snapshot
    if not snapshot.ts_event <= snapshot.ts_init <= now_ns <= snapshot.valid_until_ns:
        raise ValueError("t22_factors_unavailable_or_stale")


def build_strategy(dispatch, controller, config, now_ns):
    """Numbers come from the existing frozen limits/preset and bounded stage."""
    validate_availability(dispatch, now_ns)
    families = importlib.import_module("blueprints.us-equities.strategies.families")
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
        controller.ledger.mark_to_market(list(controller.quotes.values()), now)
        controller.stop = True

    strategy = families.FAMILIES[dispatch.family](spec, ledger=controller.ledger,
        fault_sink=fault, notice_sink=notice, post_cutoff_fill_sink=post_cutoff)
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
    families = importlib.import_module("blueprints.us-equities.strategies.families")
    dispatch = config["_t22"]
    now_ns = time.time_ns()
    strategy = build_strategy(dispatch, controller, config, now_ns)
    policy = validate_session_policy(config)
    port = controller.port
    start = port.start

    async def start_with_quotes(on_quote, on_order):
        def quote(row):
            controller.quote(row)
            on_quote(row)
        return await start(quote, on_order)

    port.start = start_with_quotes
    metadata = [{"symbol": a["symbol"], "price_precision": 2,
                 "price_increment": "0.01", "lot_size": "1"} for a in assets]
    session = build_node(port, metadata, [strategy], session_policy=policy,
        account_id="ALPACA-PAPER",
        max_order_submit_rate="180/00:01:00", log_directory=log_directory)
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
                strategy.enabled = False
                reconcile(controller.ledger, await port.snapshot(), baseline_cash)
                health = getattr(port, "health", {})
                if any("stale" not in str(reason) for reason in health.get("reasons", [])):
                    controller.stop = True
                    force = True
                elif health.get("fresh_quotes") and hasattr(port, "mark_reconciled"):
                    port.mark_reconciled()
                last_reconciliation = time.monotonic()
            if active and not published:
                validate_availability(dispatch, strategy.clock.timestamp_ns())
                kind = families.snapshot_data_type(dispatch.snapshot.instrument_id)
                strategy.publish_data(kind, CustomData(kind, dispatch.snapshot))
                published = True
            if force:
                strategy.spec = replace(strategy.spec,
                    entry_deadline_ns=min(strategy.spec.entry_deadline_ns, int(now * 1e9)),
                    exit_deadline_ns=min(strategy.spec.exit_deadline_ns, int(now * 1e9)))
            strategy.enabled = bool(active and port.ready and not strategy.faulted)
            if active and (session.errors or controller.halt_seed_pending() or now < controller.defer_until):
                strategy.enabled = False
            if force and not controller.ledger.positions() and not controller.ledger.unresolved() and strategy.pending is None:
                break
            await asyncio.sleep(.05)
        strategy.enabled = False
        controller.stop = True
        if not controller.ledger.unresolved() and strategy.pending is None:
            reconciliation = reconcile(controller.ledger, await port.snapshot(), baseline_cash)
    finally:
        strategy.enabled = False
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
            await port.stop()
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
