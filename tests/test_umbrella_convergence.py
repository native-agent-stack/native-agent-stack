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
    assert lock["schemaVersion"] == "3.10.2"
    v380 = lock["v380RankingDatafeedsAndCompoundingVersioningSeal"]
    assert v380["adr"] == "ADR-0015"
    assert v380["rankingFeedSchema"] == "sota-ranking-datafeeds.v3.8"
    assert v380["canonicalRankingFeeds"] == 9
    v390 = lock["v390DualMachineLaneHubV2AndH091Seal"]
    assert v390["adr"] == "ADR-0016"
    assert v390["dualMachineLanesSchema"] == "sota-dual-machine-lanes.v2"
    assert v390["orcaLaneHubSchema"] == "sota-orca-lane-hub.v2"
    assert len(v390["prewallLakeSha256"]) == 64
    v391 = lock["v391OvernightWhipsawLawAndLiveE2ESeal"]
    assert v391["adr"] == "ADR-0017"
    assert v391["hlzTrialsCompleted"] >= 93
    v392 = lock["v392DualDesktopCoexistenceAnd22RepoZeroDriftSeal"]
    assert v392["adr"] == "ADR-0018"
    assert v392["threeSurfaceSyncedCheckouts"] == 54
    v393 = lock["v393StarredVisualCraftDualTvAndCompoundingSeal"]
    assert v393["adr"] == "ADR-0019"
    assert v393["starredVisualCraftReposManifested"] == 24
    assert v393["dualNativeTradingViewCoexistence"] is True
    v394 = lock["v394NoesisMainTradingViewDisplayAndKeepUpSeal"]
    assert v394["adr"] == "ADR-0020"
    assert v394["primaryTradingViewDisplayHost"] == "noesis_4k_main_display"
    assert v394["autoKeepUpIntervalMinutes"] == 15
    v395 = lock["v395AllGapsH094And46Skill17WorkflowSeal"]
    assert v395["adr"] == "ADR-0021"
    assert v395["hlzTrialsCompleted"] == 94
    assert v395["sotaSkillsTotal"] == 46
    assert v395["canonicalWorkflowsTotal"] == 17
    v398 = lock["v398H096DryPowderCollarAnd18WorkflowM1M4Seal"]
    assert v398["adr"] == "ADR-0025"
    assert v398["hlzTrialsCompleted"] == 96
    assert v398["canonicalWorkflowsTotal"] == 18
    assert v398["threeSurfaceSyncedCheckouts"] == 54
    v399 = lock["v399SmartTaskModelRouter413StarAnd22RepoSeal"]
    assert v399["adr"] == "ADR-0026"
    assert v399["smartTaskSuitabilityProfiles"] == 8
    assert v399["ownerTotalStarsAudited"] >= 413
    v399_final = lock["v399Complete18RepoPostRestartCoopSeal"]
    assert v399_final["adr"] == "ADR-0027"
    assert v399_final["qmdEmbeddedVectorsTotal"] == 2325
    assert v399_final["threeSurfaceSyncedCheckouts"] == 54
    v3100 = lock["v3100QualityDirective3PowerhouseAnd1To1FableMixSeal"]
    assert v3100["adr"] == "ADR-0028"
    assert v3100["targetClaudeFableShare"] == 0.5
    assert v3100["haikuSprawlTarget"] == 0.0
    assert v3100["threeSurfaceSyncedCheckouts"] == 54
    v3102 = lock["v3102AdvancedResearchConvergence12FeedAndOrcaLeadE2ESeal"]
    assert v3102["adr"] == "ADR-0029"
    assert v3102["symbolRankingSchema"] == "sota-symbol-ranking-datafeeds.v3.10"
    assert v3102["canonicalSymbolRankingFeeds"] == 12
    assert v3102["autoStrategyRoutesCount"] == 6
    assert v3102["canonicalWorkflowsTotal"] == 19
    assert v3102["beyondStarredFrontierRepos"] == 6


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
