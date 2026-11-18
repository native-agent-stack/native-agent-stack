"""Unit & Hypothesis property tests for native-agent-stack v3.0.0 convergence lock."""

from __future__ import annotations

import copy

from hypothesis import given
from hypothesis import strategies as st

from native_agent_stack.umbrella import evaluate_convergence_lock, load_default_lock


def test_default_lock_passes_all_invariants() -> None:
    lock = load_default_lock()
    ok, errors = evaluate_convergence_lock(lock)
    assert ok, f"Default lock failed validation: {errors}"
    assert len(lock["publicUnlimitedActionsTier"]) == 9
    assert len(lock["privateProprietaryExecutionAndVaultTier"]) == 9
    assert len(lock["coldArchivedSupersededTier"]) == 4
    assert lock["schemaVersion"] == "3.8.0"
    v380 = lock["v380RankingDatafeedsAndCompoundingVersioningSeal"]
    assert v380["adr"] == "ADR-0015"
    assert v380["rankingFeedSchema"] == "sota-ranking-datafeeds.v3.8"
    assert v380["canonicalRankingFeeds"] == 9
    assert v380["nextHlzTHurdle"] == 4.176


def test_exposing_proprietary_repo_fails_closed() -> None:
    lock = copy.deepcopy(load_default_lock())
    lock["publicUnlimitedActionsTier"].append("sota-mover-ranker")
    ok, errors = evaluate_convergence_lock(lock)
    assert not ok
    assert any("sota-mover-ranker" in err for err in errors)


def test_assigning_layer_to_archived_repo_fails_closed() -> None:
    lock = copy.deepcopy(load_default_lock())
    lock["layerSingleOwnerMap"]["L1_ecosystem_umbrella_and_supersession_lock"] = "legacy-agent-stack-202610"
    ok, errors = evaluate_convergence_lock(lock)
    assert not ok
    assert any("cold-archived" in err for err in errors)


@given(stop_pct=st.floats(min_value=-10.0, max_value=25.0, allow_nan=False, allow_infinity=False))
def test_adr_0022_stop_cap_property(stop_pct: float) -> None:
    lock = copy.deepcopy(load_default_lock())
    lock["hardInvariants"]["adr_0022_max_stop_pct"] = stop_pct
    ok, _ = evaluate_convergence_lock(lock)
    assert ok == (0.0 < stop_pct <= 2.0)
