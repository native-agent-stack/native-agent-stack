# ADR-0022: `v3.9.6` CTA/UTP Single-Session Guard (`ADR-0021`), Partial-Fill FIFO Attribution (`8e01ec17`) & Zero-Lease 22-Repo Final Seal

- **Status:** Accepted
- **Date:** 2026-11-18
- **Layer:** Organization Umbrella, Dual-Desktop CTA/UTP Session Ownership, Broker FIFO Attribution & 22-Repo Convergence (`L0–L13` × `P0–P5` × `T0–T8`)
- **Evidence Grade:** E4 (`sota-mover-ranker @ 8e01ec178404fc5f18e33a2f3328083be7e35eb4` `94/94` `pytest`, `merge_gate.py` & `gitleaks` `0` Leaks)
- **GitHub Evidence:** https://github.com/native-agent-stack/native-agent-stack, https://github.com/native-agent-stack/.github, https://github.com/native-agent-stack/sota-mover-ranker, https://github.com/native-agent-stack/sota-private-vault
- **Revisit Trigger:** 2026-12-06 (`23/5` SIP cutover) or next `ALPHA_STRATEGY_MINOR` promotion (`t >= 4.1858`, `DSR >= 0.95`)

## Context and Problem Statement

Following `ADR-0021` (`v3.9.5`), peers `ad7807ca` and `7ebd8356` landed and released the final two in-flight `sota-mover-ranker` commits: `ADR-0021` (`7de8ce22c57f`: CTA/UTP single-session guard, auto-parking idle secondary TradingView Desktop & `/api/tv/handoff`) and `8e01ec178404` (`94/94` `pytest`: partial-fill canceled order `filled_qty > 0` FIFO attribution & early-volume/climax fast collars).

## Decision Outcome

1. **Advance `ECOSYSTEM_CONVERGENCE_LOCK.json` to `schemaVersion = "3.9.6"` (`22` Umbrella ADRs):**
   - Record `v396CtaSessionGuardAndPartialFillFifoSeal` binding `sotaMoverRankerAdr0021AndFifoSha = "8e01ec178404fc5f18e33a2f3328083be7e35eb4"`, `lessonsCount = 77`, and `threeSurfaceSyncedCheckouts = 54`.

## Alternatives Considered

1. **Leave Umbrella lock at `v3.9.5` (`fd572c09`) with 2-commit `sota-mover-ranker` drift:** Rejected — zero-drift SHA parity across all `22` repositories is non-negotiable.

## Verification Witness

- `.venv/bin/python scripts/merge_gate.py` (`architecture_catalog --check`, `umbrella --check`, `ruff`, `ty`, `pytest`) -> `PASS`.
- `gitleaks` -> `0` leaks.
