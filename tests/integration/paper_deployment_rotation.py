"""Explicit real landed-rotation composition, SYN journal and no broker I/O."""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "blueprints/us-equities/adaptive-paper"))


def main():
    import paper_deployment as d
    from runner import load_config
    from safety import Ledger
    from exploration import active_trial_metadata
    from tests.test_paper_deployment import DeploymentContract
    if not callable(getattr(Ledger, "register_exploratory_config", None)):
        raise RuntimeError("landed_rotation_source_required")
    with DeploymentContract().scratch() as directory:
        root = Path(directory)
        source = root / "alternate.json"
        config = json.loads((d.SOURCE / "config-sip.json").read_bytes())
        config["minimum_edge_bps"] = 2
        source.write_text(json.dumps(config))
        specs = {"first": {"engine_kind": "adaptive", "session_kind": "RTH", "config": str(d.SOURCE / "config-sip.json")},
                 "second": {"engine_kind": "adaptive", "session_kind": "RTH", "config": str(source)}}
        d.build(root / "bundle", deployment="rotation-proof", order=list(specs), stage_specs=specs)
        plan = d.Deployment(root / "bundle", root / "exploratory")
        fingerprint = "a" * 64
        state = plan.native_state() / fingerprint / "adaptive"
        state.mkdir(parents=True)
        _, limits, _ = load_config(plan.config_path("first"))
        now = 1800000000.
        metadata = {**d.LABEL, "trial_id": "first", "engine_kind": "adaptive", "phase": "starting",
                    "config_sha256": plan.stage("first")["config_sha256"], "baseline_cash": "10000",
                    "started_at": now, "fee_window_start": now}
        ledger = Ledger(state / "ledger.sqlite3", limits, exploratory=True)
        try:
            ledger.begin_next_trial(now, "first", config_sha256=metadata["config_sha256"], limits=limits, metadata=metadata)
            metadata["phase"] = "finished"
            ledger.update_exploratory_trial(metadata)
        finally:
            ledger.close()
        d.save(state / "trial.json", metadata)
        d.save(plan.state / "account-last.json", {**d.LABEL, "trial": "first", "flat": True, "finished_at": now})
        before = (state / "ledger.sqlite3").read_bytes()
        with d.account_writer(fingerprint):
            if active_trial_metadata(state) != metadata:
                raise RuntimeError("native_sql_lineage_mismatch")
            if plan.namespace_ready("first", fingerprint) != "matching_native_namespace":
                raise RuntimeError("matching_namespace_refused")
            if plan.namespace_ready("second", fingerprint) != "native_rotation_supported":
                raise RuntimeError("native_rotation_not_ready")
        if (state / "ledger.sqlite3").read_bytes() != before:
            raise RuntimeError("readiness_mutated_account_journal")
    print(json.dumps({"paper_lane": "B", "evidence_class": "synthetic", "status": "passed",
                      "checks": 3, "broker_execution": "NOT_RUN"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
