"""Held-position notice state in the existing ledger metadata/session boundary.

The real Ledger supplies its existing BEGIN IMMEDIATE/FULL-synchronous SQLite
transaction and meta accessors. Minimal synthetic ports retain a single-session
view; those ports do not establish durability across a process restart.
"""

from __future__ import annotations

import json

INTERVAL_NS = 600_000_000_000


def _durable(ledger):
    return all(
        callable(getattr(ledger, name, None))
        for name in ("_get", "_set", "_transaction")
    )


def _key(instrument_id, prefix):
    return "t22-held-notice-v1:" + instrument_id + ":" + (prefix or "session")


def _validate(value, instrument_id, prefix, *, durable):
    if value is None:
        return None
    if (
        not isinstance(value, dict)
        or type(value.get("schema_version")) is not int
        or value["schema_version"] != 1
        or value.get("instrument_id") != instrument_id
        or value.get("reason") not in {"held_halted", "held_halt_state_unknown"}
        or type(value.get("active")) is not bool
    ):
        raise ValueError("invalid_held_notice_state")
    stored_prefix = value.get("client_id_prefix")
    if stored_prefix != prefix and (durable or stored_prefix is not None):
        raise ValueError("held_notice_identity_mismatch")
    if durable and (not isinstance(prefix, str) or not prefix):
        raise ValueError("held_notice_stable_identity_required")
    last = value.get("last_notice_ns")
    if type(last) is not int or not 0 <= last < 2**63 - INTERVAL_NS:
        raise ValueError("invalid_held_notice_delivery_time")
    if (
        type(value.get("next_due_ns")) is not int
        or value["next_due_ns"] != last + INTERVAL_NS
    ):
        raise ValueError("invalid_held_notice_deadline")
    order = value.get("client_order_id")
    if order is not None and (not isinstance(order, str) or not order):
        raise ValueError("invalid_held_notice_order_identity")
    if durable and order is not None and not order.startswith(prefix):
        raise ValueError("held_notice_order_identity_mismatch")
    return dict(value)


def load(ledger, instrument_id, prefix):
    durable = _durable(ledger)
    if durable:
        with ledger._transaction():
            raw = ledger._get(_key(instrument_id, prefix))
        value = None if raw is None else json.loads(raw)
    else:
        states = getattr(ledger, "_t22_held_notices", {})
        value = states.get(
            _key(instrument_id, prefix), states.get(_key(instrument_id, None))
        )
    return _validate(value, instrument_id, prefix, durable=durable)


def save(ledger, value):
    durable = _durable(ledger)
    instrument, prefix = value["instrument_id"], value["client_id_prefix"]
    value = _validate(value, instrument, prefix, durable=durable)
    key = _key(instrument, prefix)
    if durable:
        with ledger._transaction():
            ledger._set(key, json.dumps(value, sort_keys=True, separators=(",", ":")))
    else:
        if not hasattr(ledger, "_t22_held_notices"):
            ledger._t22_held_notices = {}
        ledger._t22_held_notices[key] = value


def clear(ledger, instrument_id, prefix):
    if _durable(ledger):
        with ledger._transaction():
            ledger._set(_key(instrument_id, prefix), "null")
    else:
        states = getattr(ledger, "_t22_held_notices", {})
        states.pop(_key(instrument_id, prefix), None)
        states.pop(_key(instrument_id, None), None)


def restore(strategy, *, arm=False):
    value = load(
        strategy.ledger,
        strategy.spec.instrument_id,
        getattr(strategy, "client_id_prefix", None),
    )
    strategy.active_halt_notice = value
    strategy.restored_halt_notice = value
    if value is None:
        return
    strategy.last_halt_notice_ns = value["last_notice_ns"]
    strategy.last_halt_notice_reason = value["reason"]
    if not value["active"]:
        return
    strategy.flags.add(value["reason"])
    if arm:
        now = strategy.clock.timestamp_ns()
        due = value["next_due_ns"]
        if now >= due:
            # One immediate overdue notice; coalesce missed intervals and
            # restart the cadence from this actual delivery, without a burst.
            strategy._notify_halt_hold(now, value["reason"])
        else:
            strategy._retire_halt_notice_alert()
            strategy.clock.set_time_alert_ns(
                "t22-halt-hold", due, callback=strategy._on_watchdog
            )
