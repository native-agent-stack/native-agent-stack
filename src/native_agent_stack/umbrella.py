"""Fail-closed validator for the v3.0.0 native-agent-stack Ecosystem Convergence Lock."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

DEFAULT_LOCK_PATH = Path(__file__).resolve().parents[2] / "ECOSYSTEM_CONVERGENCE_LOCK.json"


def load_default_lock(path: Path = DEFAULT_LOCK_PATH) -> dict[str, Any]:
    """Load the JSON convergence lock from disk."""
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def evaluate_convergence_lock(lock: dict[str, Any]) -> tuple[bool, list[str]]:
    """Verify Two-Tier disjointness, single-owner layer bijection, supersession, and trading firewall."""
    errors: list[str] = []

    pub = [str(x) for x in lock.get("publicUnlimitedActionsTier", [])]
    priv = [str(x) for x in lock.get("privateProprietaryExecutionAndVaultTier", [])]
    arch = [str(x) for x in lock.get("coldArchivedSupersededTier", [])]

    pub_set, priv_set, arch_set = set(pub), set(priv), set(arch)
    if len(pub) != len(pub_set) or len(priv) != len(priv_set) or len(arch) != len(arch_set):
        errors.append("Duplicate repository entry inside a tier list.")

    if pub_set & priv_set:
        errors.append(f"PUBLIC/PRIVATE overlap detected: {sorted(pub_set & priv_set)}")
    if pub_set & arch_set:
        errors.append(f"PUBLIC/ARCHIVED overlap detected: {sorted(pub_set & arch_set)}")
    if priv_set & arch_set:
        errors.append(f"ACTIVE-PRIVATE/ARCHIVED overlap detected: {sorted(priv_set & arch_set)}")

    must_never_be_public = {
        "sota-mover-ranker",
        "sota-dynamic-trail-c",
        "cc-sota-harness",
        "sota-private-vault",
        "meridian",
        "canon",
        "tsl",
        "trading-sota",
        "ecosystem-records",
        "legacy-agent-stack-202610",
    }
    exposed = pub_set & must_never_be_public
    if exposed:
        errors.append(f"Protected proprietary/archive repo in PUBLIC tier: {sorted(exposed)}")

    active_repos = pub_set | priv_set
    layer_map = lock.get("layerSingleOwnerMap")
    if not isinstance(layer_map, dict) or not layer_map:
        errors.append("Missing or empty layerSingleOwnerMap.")
    else:
        seen_owners: set[str] = set()
        for layer, owner_obj in layer_map.items():
            owner = str(owner_obj)
            if owner in arch_set:
                errors.append(f"Layer '{layer}' assigned to cold-archived repo '{owner}'.")
            if owner not in active_repos:
                errors.append(f"Layer '{layer}' assigned to unknown repo '{owner}'.")
            if owner in seen_owners:
                errors.append(f"Duplicate primary layer owner '{owner}' violates One-Owner-Per-Layer.")
            seen_owners.add(owner)

    invariants = lock.get("hardInvariants")
    if not isinstance(invariants, dict):
        errors.append("Missing hardInvariants section.")
    else:
        if invariants.get("prewall_study_cutoff") != "2026-10-15":
            errors.append("prewall_study_cutoff must equal '2026-10-15'.")
        max_stop = invariants.get("adr_0022_max_stop_pct")
        if not isinstance(max_stop, (int, float)) or not (0.0 < float(max_stop) <= 2.0):
            errors.append(f"ADR-0022 stop cap violated: {max_stop}")
        if invariants.get("ibkr_paper_port") != 4002:
            errors.append(f"IBKR paper port must be 4002 (got {invariants.get('ibkr_paper_port')}).")
        if invariants.get("live_capital_hard_refused") is not True:
            errors.append("live_capital_hard_refused must be True.")
        if invariants.get("private_github_actions_enabled") is not False:
            errors.append("private_github_actions_enabled must be False (zero paid quota burn).")

    return (len(errors) == 0), errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify native-agent-stack v3.0.0 convergence lock")
    parser.add_argument("--check", action="store_true", help="Run fail-closed lock verification")
    parser.add_argument("--lock-path", type=Path, default=DEFAULT_LOCK_PATH)
    args = parser.parse_args()

    lock = load_default_lock(args.lock_path)
    ok, errs = evaluate_convergence_lock(lock)
    if not ok:
        for e in errs:
            print(f"[UMBRELLA-LOCK FAIL] {e}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "status": "PASS",
                "schemaVersion": lock.get("schemaVersion"),
                "public_repos": len(lock.get("publicUnlimitedActionsTier", [])),
                "active_private_repos": len(lock.get("privateProprietaryExecutionAndVaultTier", [])),
                "cold_archived_repos": len(lock.get("coldArchivedSupersededTier", [])),
                "single_owner_layers": len(lock.get("layerSingleOwnerMap", {})),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
