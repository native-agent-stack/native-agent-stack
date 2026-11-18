# ADR-0023: `v3.9.7` Trial `#95` (`H095` Two-Stage Collar Bifurcation), `:8787`/`:8799` `ADR-0022`/`0019`, `27/27` Runtimes & 22-Repo Final Seal

- **Status:** Accepted
- **Date:** 2026-11-18
- **Layer:** Organization Umbrella, Pre-Wall Microstructure (`H095`), Multi-Runtime Orca Hub & 22-Repo Convergence (`L0–L13` × `P0–P5` × `T0–T8`)
- **Evidence Grade:** E4 (`95` HLZ Trials, `sota-mover-ranker @ 29cf82d375ae`, `sota-dynamic-trail-c @ 3cd4ceac9cc1`, `27/27` Runtimes & `54/54` Synced Checkouts)
- **GitHub Evidence:** https://github.com/native-agent-stack/native-agent-stack, https://github.com/native-agent-stack/.github, https://github.com/native-agent-stack/sota-mover-ranker, https://github.com/native-agent-stack/sota-dynamic-trail-c, https://github.com/native-agent-stack/sota-compounding-lab, https://github.com/native-agent-stack/canon
- **Revisit Trigger:** 2026-12-06 (`23/5` SIP cutover) or next `ALPHA_STRATEGY_MINOR` promotion (`t >= 4.1882`, `DSR >= 0.95`)

## Context and Problem Statement

Following `ADR-0022` (`v3.9.6`), all `15` sibling repositories converged on `v3.9.7` (`Trial #95` `H095` two-stage `15s` lit-to-`<=10 bps` collar bifurcation & sweep-toxicity law across `canon` `0182`, `meridian` `0062`, `sota-compounding-lab` `ADR-0013`, `sota-harness-foundation` `ADR-0033`, `astrolabe` `ADR-0011`, `sota-mover-ranker` `ADR-0022`, `sota-dynamic-trail-c` `ADR-0019`, and `cc-sota-harness` `4/4` Win32 MCP + `27/27` runtime parity).

## Decision Outcome

1. **Advance `ECOSYSTEM_CONVERGENCE_LOCK.json` to `schemaVersion = "3.9.7"` (`23` Umbrella ADRs):**
   - Record `v397H095CollarBifurcationBlotterAnd27RuntimeSeal` binding `hlzTrialsCompleted = 95`, `nextHlzTHurdle = 4.1882`, `sotaMoverRankerAdr0022Sha = "29cf82d375ae1a1061b133064cb891b3e68ffccc"`, `sotaDynamicTrailCAdr0019Sha = "3cd4ceac9cc1aaeb377e150db5ccd2faae8ca802"`, `runtimeFleetBinariesVerified = 27`, and `threeSurfaceSyncedCheckouts = 54`.

## Alternatives Considered

1. **Leave Umbrella lock at `v3.9.6` with `13`-repo `v3.9.7` drift:** Rejected — zero-drift `22/22` SHA parity is mandatory.

## Verification Witness

- `uv run --frozen --all-groups --all-extras python scripts/merge_gate.py` -> `PASS`.
- `gitleaks` -> `0` leaks.
