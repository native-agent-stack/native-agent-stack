"""Lane-B selection and state/receipt boundaries; no broker I/O or numeric sizing."""
from pathlib import Path
import hashlib
import json
import sqlite3

PRESET_VERSION = "paper-exits-v1-20261012"


def apply_exit_preset(config, engine):
    if "resolved_exploratory_exit_preset" in config:
        raise ValueError("resolved_preset_is_engine_output")
    selection = config.get("exploratory_exit_preset")
    if selection is None:
        return
    if not is_exploratory(config):
        raise ValueError("exploratory_preset_requires_lane_b")
    if (not isinstance(selection, dict) or set(selection) != {"version", "name"}
            or selection["version"] != PRESET_VERSION or type(selection["name"]) is not str):
        raise ValueError("unregistered_exploratory_exit_preset")
    path = Path(__file__).with_name("exploratory-exit-presets.json")
    raw = path.read_bytes()
    registry = json.loads(raw)
    if registry["version"] != PRESET_VERSION or selection["name"] not in registry[engine]:
        raise ValueError("unregistered_exploratory_exit_preset")
    values = dict(registry[engine][selection["name"]])
    if engine == "adaptive":
        # Full effective policy is fixed by the registered version, including
        # disabled/default candidate knobs; caller overrides cannot sneak in.
        defaults = {"vol_stop_multiplier": 1.0, "vol_reference_bps": 20.0,
                    "stop_min_bps": None, "stop_max_bps": None,
                    "trailing_min_bps": None, "trailing_max_bps": None,
                    "take_profit_fraction": 1.0, "time_decay_start_seconds": None,
                    "time_decay_min_multiplier": 1.0}
        values = {**registry[engine]["baseline"], **defaults, **values}
        config.update(values)
    else:
        config["mover"].update(values)
    config["resolved_exploratory_exit_preset"] = {
        **selection, "engine": engine, "parameters": values,
        "registry_sha256": hashlib.sha256(raw).hexdigest(),
        "historical_selection": "NOT_RUN"}


def config_digest(config, raw, *, limits=None):
    if not is_exploratory(config):
        return hashlib.sha256(raw).hexdigest()
    effective = {k: v for k, v in config.items() if not k.startswith("_")}
    if limits is not None:
        effective["effective_risk_limits"] = json.loads(limits.frozen_json())
    return hashlib.sha256(json.dumps(effective, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def active_trial_metadata(state_dir):
    """Read SQLite's active admission before using the JSON projection.

    Pre-change B state can be read only when its JSON identity and registered
    limits match the active journal. Historical namespaces alone are insufficient.
    A projection without a journal binding refuses; only state with no prior
    trial in either artifact can bootstrap.
    This performs no writes; the account lock protects the caller's second read.
    """
    from safety import SafetyError
    state_dir=Path(state_dir)
    db_path=state_dir/'ledger.sqlite3'
    projection=state_dir/'trial.json'
    projection_unreadable=False
    try:
        metadata=json.loads(projection.read_text()) if projection.exists() else None
    except (OSError,ValueError):
        metadata=None
        projection_unreadable=True
    if not db_path.exists() or db_path.stat().st_size == 0:
        if metadata is not None or projection_unreadable:
            raise SafetyError('active_trial_projection_unbound')
        return None
    if db_path.is_symlink():
        raise SafetyError('ledger_symlink_refused')
    db=sqlite3.connect(db_path.resolve().as_uri()+'?mode=ro',uri=True)
    try:
        if not db.execute("SELECT 1 FROM sqlite_master WHERE name='meta'").fetchone():
            if metadata is not None or projection_unreadable:
                raise SafetyError('active_trial_projection_unbound')
            return None
        rows=dict(db.execute('SELECT key,value FROM meta'))
        record=rows.get('exploratory_active_trial')
        if record is not None:
            active=json.loads(record)
            if (active.get('trial_id') != rows.get('trial_id')
                    or rows.get('exploratory_config:'+str(active.get('config_sha256'))) != rows.get('limits')):
                raise SafetyError('active_trial_journal_mismatch')
            return active
        if rows.get('trial_id') is not None:
            if (not isinstance(metadata,dict) or metadata.get('trial_id') != rows['trial_id']
                    or rows.get('exploratory_config:'+str(metadata.get('config_sha256'))) != rows.get('limits')):
                raise SafetyError('active_trial_projection_unbound')
        elif metadata is not None or projection_unreadable:
            raise SafetyError('active_trial_projection_unbound')
        return metadata
    finally:
        db.close()


def publish_trial_projection(ledger, path, metadata, save):
    """Commit active phase/lineage to SQLite, then publish the recoverable JSON copy."""
    if ledger.exploratory is True:
        ledger.update_exploratory_trial(metadata)
    save(path,metadata)


def is_exploratory(config):
    lane = config.get("paper_lane")
    evidence = config.get("evidence_class")
    if lane is None and evidence is None:
        return False
    if lane != "B" or evidence != "exploratory":
        raise ValueError("invalid_exploratory_labels")
    return True


def receipt_labels(config):
    if not is_exploratory(config):
        return {}
    labels = {"paper_lane": "B", "evidence_class": "exploratory", "qualification_evidence": False}
    if config.get("resolved_exploratory_exit_preset") is not None:
        labels["exit_preset"] = config["resolved_exploratory_exit_preset"]
    return labels


def validate_exploratory_paths(config, state_root, output, *, live_dir=None):
    if not is_exploratory(config):
        return
    if live_dir is not None:
        raise ValueError("exploratory_live_diagnostics_not_registered")
    for path in (state_root, output, live_dir):
        if path is None:
            continue
        parts = Path(path).resolve().parts
        if "exploratory" not in parts or any(p in parts for p in ("trials", "qualification", "evidence")):
            raise ValueError("exploratory_path_required")
