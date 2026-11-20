"""Unit & Hypothesis property tests for native-agent-stack v3.0.0 convergence lock."""

from __future__ import annotations

import copy

from hypothesis import given
from hypothesis import strategies as st

from native_agent_stack.umbrella import evaluate_convergence_lock, load_default_lock

HEX_DIGITS = frozenset("0123456789abcdef")


def test_default_lock_passes_all_invariants() -> None:
    lock = load_default_lock()
    ok, errors = evaluate_convergence_lock(lock)
    assert ok, f"Default lock failed validation: {errors}"
    assert len(lock["publicUnlimitedActionsTier"]) == 9
    assert len(lock["privateProprietaryExecutionAndVaultTier"]) == 9
    assert len(lock["coldArchivedSupersededTier"]) == 4
    assert lock["schemaVersion"] == "3.10.11"
    assert lock["dualWorkstationMesh"]["primarySovereignHost"] == "stationary_noesis_win32"
    assert lock["dualWorkstationMesh"]["portableCockpitAndFailover"] == "portable_mac_m5_max"
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
    v3103 = lock["v3103Shared24x5LosslessFoundationAndMeritHarnessSeal"]
    assert v3103["adr"] == "ADR-0031"
    assert v3103["goalId"] == "G_SOTA_DUAL_MACHINE_MERIT_TO_LOSSLESS_LIVE_24X5"
    assert v3103["paperAndLiveShareSame24x5Foundation"] is True
    assert v3103["simLanesNeverGated"] == 2
    assert v3103["paperAccountsNeverGated"] == 4
    assert v3103["alpacaPaperAccounts"] == 3
    assert v3103["ibkrPaperAccounts"] == 1
    assert v3103["liveStage5LosslessLanes"] == 1
    assert v3103["canonicalWorkflowsTotal"] == 20
    v3105 = lock["v3105FullEcosystemSevenDomainOrcaLanesAndStationaryNoesisSeal"]
    assert v3105["adr"] == "ADR-0032"
    assert v3105["primarySovereignWorkstation"] == "stationary_noesis_win32"
    assert v3105["portableCockpitAndFailover"] == "portable_mac_m5_max"
    assert v3105["singleActiveBrokerHostOnly"] is True
    assert v3105["dedicatedLiveExtGuardianPort"] == 8796
    assert v3105["canonicalOrcaLaneLeadsReadOnlyT5"] is True
    assert v3105["dualMachineOrcaFolderHubsTotal"] == 18
    assert v3105["dualMachineOrcaAutomationsTotal"] == 14
    assert len(v3105["sevenDomainOrcaLaneHubs"]) == 7
    v3106 = lock["v3106PreIpoP0ShieldClosureAndTenLeadMultiModelOrcaSeal"]
    assert v3106["adr"] == "ADR-0033"
    assert v3106["adr0035UnifiedShieldActive"] is True
    assert v3106["failClosed8796DirectCallDefault"] is True
    assert v3106["noesis24x5KeepaliveSupervisorShipped"] is True
    assert v3106["canonicalOrcaLaneLeadsTotal"] == 10
    assert v3106["sevenDomainHubsFullyStaffed"] is True
    v3107 = lock["v3107AdvancedComputerUseAndSeamlessWorkstationLandingSeal"]
    assert v3107["adr"] == "ADR-0034"
    assert v3107["computerUseSchema"] == "sota-computer-use-5layer.v1.0"
    assert v3107["win32BackgroundUiaTarget"] == "mediar-ai/terminator"
    assert v3107["hardInvariantsFailClosed"] is True
    assert v3107["humanTrustGatesNeverBypassed"] is True
    v3108 = lock["v3108OrcaSotaDefaultsRedteamSkillEvalAnd415StarredSeal"]
    assert v3108["adr"] == "ADR-0035"
    assert v3108["canonicalSkillsTotal"] == 60
    assert v3108["canonicalWorkflowsTotal"] == 21
    assert v3108["dualMachineOrcaAutomationsTotal"] == 15
    assert v3108["ownerStarredTotalAudited"] == 415
    assert v3108["beyondStarredAnchorsTotal"] == 8
    assert v3108["skillEvaluatorAllPassed"] is True
    assert v3108["zeroStaleAndZeroKimiEnforced"] is True
    v3109 = lock["v3109LandscapeAndDualMachineOrcaManifestSeal"]
    assert v3109["adr"] == "ADR-0037"
    assert v3109["crossOsOrcaYamlReposTotal"] == 18
    assert v3109["dualMachineOrcaLaneHubsTotal"] == 9
    assert v3109["sotaDoctorChecksTotal"] == 18
    assert v3109["rtx4090CudaSidecarPort"] == 8794
    v31010 = lock["v31010PostIpoConsolidationUniversal4xLosslessAndCausalTcaSeal"]
    assert v31010["adr"] == "ADR-0038"
    assert v31010["postIpoSymbol"] == "ANT"
    assert v31010["newIssue30dSeasoningEndDateEt"] == "2026-12-19"
    assert v31010["seasonedLargeCapDateEt"] == "2026-12-20"
    assert v31010["universalZeroGap4xLosslessLiveActive"] is True
    assert v31010["crossProcessExitLockAndComingledDebit"] is True
    assert v31010["wholeMarketSotaOpportunityRanking"] is True
    assert v31010["causalMarkoutTcaAndQueueParityActive"] is True
    assert v31010["hlzTrialsCompleted"] >= 103
    v31010_audit = lock["v31010CrossVendorLandscapeAuditAnd8RuntimeFirewallSeal"]
    assert v31010_audit["adr"] == "ADR-0039"
    assert v31010_audit["eightRuntimeNativeFirewallsCount"] == 8
    assert v31010_audit["explicitAllowFailClosedJsTsWrappers"] is True
    assert v31010_audit["tier3FullManifestSkillMountParity"] is True
    assert v31010_audit["skillMountsVerifiedCount"] == 8
    assert v31010_audit["wsl2DoctorSixOfSixPass"] is True
    assert v31010_audit["dag10OfflineFallbackFailClosedE1"] is True
    assert v31010_audit["codexRedteamP0P1OpenCount"] == 0
    assert len(v31010_audit["landedShas"]) == 4
    assert lock["v31011LandscapeTerminalConvergenceAndDec6ReadinessSeal"]["adr"] == "ADR-0040"


def test_v31011_landscape_terminal_convergence_and_dec6_readiness_seal() -> None:
    lock = load_default_lock()
    seal = lock["v31011LandscapeTerminalConvergenceAndDec6ReadinessSeal"]
    assert len(seal) == 20
    assert seal["adr"] == "ADR-0040"

    # Shelf ADR-0017 owns the taxonomy; the umbrella holds a pointer (owner, hash, counts) only.
    assert seal["terminalPlatformTaxonomyOwner"] == "sota-upstream-shelf-lock"
    assert seal["terminalPlatformTaxonomyOwner"] in lock["publicUnlimitedActionsTier"]
    taxonomy_sha = seal["terminalPlatformTaxonomySha256"]
    assert taxonomy_sha == "2c81665b9dba2590db3649f00dae309bf5c33704d641faa19160741c54b8c61d"
    assert len(taxonomy_sha) == 64 and set(taxonomy_sha) <= HEX_DIGITS
    assert seal["terminalPlatformTaxonomyClasses"] == 4
    assert seal["terminalPlatformTaxonomyNamedSurfaces"] == 14
    assert seal["immutableCorePinsPreserved"] == 18

    # Lab ADR-0026: one-sided collar advisory that never gates a paper lane.
    assert seal["collarRecalibrationNeverLoosensBeyondPrewallPrior"] is True
    assert seal["collarRecalibrationPaperNeverGatedAdvisory"] is True

    # Promotion-track non-interference boundary: visual artifacts hold no decision authority.
    assert seal["cockpitOverlaysPromotionTrack"] == "VISUAL_TELEMETRY_OR_GOVERNANCE"
    assert seal["cockpitOverlaysDecisionAuthority"] == "NONE"
    assert seal["cockpitOverlaysStandaloneAlphaClaim"] is False
    assert seal["alphaPromotionRequiresMinorBumpAndPreregisteredTrial"] is True
    assert seal["hlzTrialsCompleted"] == 103
    assert seal["nextHlzTHurdle"] == 4.2063
    assert seal["trial104Consumed"] is False

    # The Dec 6 cutover is a readiness contract after the pre-wall cutoff, never an active flag.
    assert seal["sip23x5CutoverDateEt"] == "2026-12-06"
    assert seal["sip23x5CutoverStatus"] == "PRE_CUTOVER_READINESS_CONTRACT"
    assert seal["sip23x5CutoverDateEt"] > lock["hardInvariants"]["prewall_study_cutoff"]

    # Dual-pool compute standard: API secrets may exist in public-tier CI only.
    assert seal["dualPoolComputeGovernanceSchema"] == "sota-anthropic-keybank.v1"
    assert seal["publicCiOnlyApiSecretFirewall"] is True
    assert lock["hardInvariants"]["private_github_actions_enabled"] is False

    landed = seal["landedShas"]
    assert landed == {
        "sota-upstream-shelf-lock": "546cdef91ba72c7679969a8bd879058c51e70ec0",
        "sota-compounding-lab": "69c86acf8701979d47b03eb173796e97bfd46160",
        "sota-mover-ranker": "a58c1b8dc29fcb4fcae9867ef37890d45479d3f5",
        "sota-multi-model-workflows": "fbd6fdb7d43da5ed001ef0f995d05da28a136889",
    }
    active = set(lock["publicUnlimitedActionsTier"]) | set(lock["privateProprietaryExecutionAndVaultTier"])
    for repo, sha in landed.items():
        assert repo in active
        assert len(sha) == 40 and set(sha) <= HEX_DIGITS
    assert "sota-mover-ranker" in lock["privateProprietaryExecutionAndVaultTier"]


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
